"""
20_build_pool_table.py — the hero 9-foot, six-leg, unbranded slate table.

Every real component is a separate object, because it is separate in the real
table: three slate slabs, six rail bodies, six cushions, six pocket assemblies,
six turned legs, the sill frame, the transverse sills, the centre beam, aprons,
liners, levelers, sights.

Geometry authority, in order: WPA equipment specs -> Olhausen outside
dimensions -> Brunswick Metro assembly logic -> US3263996 load path. Internal
member sizes that no source publishes come from config.DD_* and are recorded
in docs/DESIGN_DECISIONS.md as design decisions, never as specifications.

Owns: 02_TABLE_VISIBLE, 03_TABLE_ENGINEERING.
"""
import bpy
import bmesh
import math
import os
import sys
from bisect import bisect_right
from math import radians, cos, sin, tan
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402
import pool_geometry_contract as G  # noqa: E402

VIS = "02_TABLE_VISIBLE"
ENG = "03_TABLE_ENGINEERING"
PHYS = "10_PHYSICS_PROXIES"

# playfield half-extents, cushion-nose to cushion-nose
HW = C.PLAY_W / 2.0
HL = C.PLAY_L / 2.0
CX, CY = C.TABLE_CENTRE[0], C.TABLE_CENTRE[1]


def pf(x, y, z=0.0):
    """playfield-local -> world"""
    return Vector((CX + x, CY + y, C.BED_Z + z))


def _orient_sweep_mesh(ob, path, profile):
    """Orient each non-folding sweep segment from its horizontal top face."""
    mesh = ob.data
    mesh.update()
    profile_count = len(profile)
    segment_count = len(path) - 1
    top_height = max(point[1] for point in profile)
    top_edges = [index for index, point in enumerate(profile)
                 if abs(point[1] - top_height) <= 1e-9 and
                 abs(profile[(index + 1) % profile_count][1] -
                     top_height) <= 1e-9]
    if len(top_edges) != 1:
        raise RuntimeError("sweep %s has no unique top profile edge" % ob.name)
    top_edge = top_edges[0]

    # Winding depends on local path direction relative to the play-side
    # normal. Curved jaw sweeps can change that relationship, so repair each
    # manufactured segment from its unambiguous horizontal top face instead
    # of blanket normal recalculation on the concave shell.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    for segment in range(segment_count):
        top_face = bm.faces[segment * profile_count + top_edge]
        if top_face.normal.z < 0.0:
            first = segment * profile_count
            bmesh.ops.reverse_faces(
                bm, faces=[bm.faces[first + index]
                           for index in range(profile_count)])
    bm.normal_update()

    # The two end caps are last in L.extrude_profile's face list.
    first_cap = bm.faces[segment_count * profile_count]
    last_cap = bm.faces[segment_count * profile_count + 1]
    first_direction = (Vector(path[0]) - Vector(path[1])).normalized()
    last_direction = (Vector(path[-1]) - Vector(path[-2])).normalized()
    if first_cap.normal.dot(first_direction) < 0.0:
        first_cap.normal_flip()
    if last_cap.normal.dot(last_direction) < 0.0:
        last_cap.normal_flip()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    if any(mesh.polygons[segment * profile_count + top_edge].normal.z < 0.5
           for segment in range(segment_count)):
        raise RuntimeError("sweep %s top faces are not outward" % ob.name)
    return ob


def _extrude_profile(*args, **kwargs):
    """Table-local sweep with deterministic segment winding."""
    ob = L.extrude_profile(*args, **kwargs)
    path = args[1] if len(args) > 1 else kwargs["path"]
    profile = args[3] if len(args) > 3 else kwargs["profile"]
    return _orient_sweep_mesh(ob, path, profile)


def _extrude_variable_profile(name, path, normals, profile, widths,
                              collection, mat=None, smooth=False):
    """Sweep a profile whose safe back width can vary along tight fillets."""
    if len(path) != len(normals) or len(path) != len(widths):
        raise ValueError("variable sweep inputs must have equal lengths")
    reference = max(distance for distance, _height in profile)
    if reference <= 0.0 or any(width <= 0.0 for width in widths):
        raise ValueError("variable sweep widths must be positive")
    verts, faces = [], []
    count = len(profile)
    for point, normal, width in zip(path, normals, widths):
        back = Vector((-normal.x, -normal.y, 0.0))
        scale = width / reference
        for distance, height in profile:
            verts.append((point.x + back.x * distance * scale,
                          point.y + back.y * distance * scale,
                          point.z + height))
    for index in range(len(path) - 1):
        first = index * count
        following = (index + 1) * count
        for profile_index in range(count):
            nxt = (profile_index + 1) % count
            faces.append((first + profile_index, first + nxt,
                          following + nxt, following + profile_index))
    faces.append(tuple(range(count))[::-1])
    faces.append(tuple(range(len(verts) - count, len(verts))))
    ob = L.mesh_object(name, verts, faces, collection, mat, smooth=smooth)
    ob["variable_profile_min_width_m"] = min(widths)
    ob["variable_profile_max_width_m"] = max(widths)
    ob["sweep_path_count"] = len(path)
    ob["sweep_profile_count"] = count
    return _orient_sweep_mesh(ob, path, profile)


MAIN_NAMES = {
    "3": "Long_W_S", "6": "Long_W_N",
    "15": "Long_E_S", "12": "Long_E_N",
    "18": "End_Foot", "9": "End_Head",
}


def _contract():
    data = G.load()
    G.validate_against_config(C, data)
    return data


def k66_profile():
    """
    K-66-class cloth-covered envelope constrained by the measured nose, the
    published rubber height/face angle and the actual rail cap. Returned as
    (distance behind nose, height above bed). This does not claim a proprietary
    manufacturer's extrusion drawing.
    """
    nose = C.CUSHION_NOSE
    top = C.RAIL_TOP_Z - C.BED_Z
    base = top - C.K66_HEIGHT
    back = C.CUSHION_COVERED_W
    t = tan(radians(C.K66_ANGLE))
    return [
        (0.0, nose),                          # the nose: what the ball strikes
        ((top - nose) / t, top),              # short upper face
        (back, top),                           # flat top under the rail
        (back, base),                          # back face
        ((nose - base) / t, base),            # lower 66 degree face
    ]


def rail_profile():
    """Structural hardwood below the separate continuous finished cap."""
    cushion_back = C.CUSHION_COVERED_W
    top = C.RAIL_TOP_Z - C.BED_Z
    bottom = -C.CLOTH_T
    support_top = top - C.DD_RAIL_CAP_T
    return [
        (cushion_back, bottom),
        (cushion_back, support_top),
        (C.RAIL_PLAN_W, support_top),
        (C.RAIL_PLAN_W, bottom),
    ]


def _prism_polygon(name, polygon, z0, z1, collection, mat):
    """Closed positive-volume prism from one CCW plan polygon."""
    count = len(polygon)
    verts = [(CX + x, CY + y, z0) for x, y in polygon]
    verts.extend((CX + x, CY + y, z1) for x, y in polygon)
    faces = [tuple(range(count))[::-1],
             tuple(count + index for index in range(count))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))
    result = L.mesh_object(name, verts, faces, collection, mat)
    bm = bmesh.new()
    bm.from_mesh(result.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(result.data)
    bm.free()
    result.data.update()
    return result


def build_rail_caps(mats):
    """Six serviceable cap boards with mitered seams and correct grain axes."""
    outer_x, outer_y = C.OUT_W / 2.0, C.OUT_L / 2.0
    inner_x = HW + C.CUSHION_COVERED_W
    inner_y = HL + C.CUSHION_COVERED_W
    z1 = C.RAIL_TOP_Z
    z0 = z1 - C.DD_RAIL_CAP_T
    boards = (
        ("Long_W_S", [(-outer_x, -outer_y), (-inner_x, -inner_y),
                       (-inner_x, 0.0), (-outer_x, 0.0)], "long"),
        ("Long_W_N", [(-outer_x, 0.0), (-inner_x, 0.0),
                       (-inner_x, inner_y), (-outer_x, outer_y)], "long"),
        ("Long_E_S", [(inner_x, -inner_y), (outer_x, -outer_y),
                       (outer_x, 0.0), (inner_x, 0.0)], "long"),
        ("Long_E_N", [(inner_x, 0.0), (outer_x, 0.0),
                       (outer_x, outer_y), (inner_x, inner_y)], "long"),
        ("End_Foot", [(-outer_x, -outer_y), (outer_x, -outer_y),
                       (inner_x, -inner_y), (-inner_x, -inner_y)], "cross"),
        ("End_Head", [(-inner_x, inner_y), (inner_x, inner_y),
                       (outer_x, outer_y), (-outer_x, outer_y)], "cross"),
    )
    made = []
    for tag, polygon, grain in boards:
        material = (mats.get("walnut_cross", mats["walnut"])
                    if grain == "cross" else mats["walnut"])
        cap = _prism_polygon("PT_RailCap_" + tag, polygon, z0, z1,
                             VIS, material)
        cap["cap_thickness_m"] = C.DD_RAIL_CAP_T
        cap["pocket_cut_source"] = os.path.relpath(G.DATA_PATH, C.ROOT)
        cap["grain_axis"] = "world_x" if grain == "cross" else "world_y"
        made.append(cap)
    return made


def build_cap_horns(mats, data):
    """Twelve wood horns continuing the cap boards along the jaw cuts.

    On the reference tables the finished rail top runs past the cushion
    terminal and its routed edge follows the jaw cut down to the pocket
    iron.  The six cap boards are straight-edged, so the strip between each
    board edge and the upholstered jaw band needs its own exact wood piece;
    without it every mouth flank reads as an open well and the cloth has to
    flare into the V-shaped wedges this revision removes.  Each horn is
    built as a closed prism, so no Boolean pass is required or applied.
    """
    rows = G.linear_rows(data)
    rows_by_id = {row["id"]: row for row in rows}
    arcs = G.arc_rows(data, steps=16)
    mains_by_id = {row["id"]: row for row in rows if row["kind"] == "main"}
    z1 = C.RAIL_TOP_Z
    z0 = z1 - C.DD_RAIL_CAP_T
    gap = 0.0006
    made = []
    for arc in arcs:
        jaw = rows_by_id[arc["jaw_id"]]
        main = mains_by_id[arc["main_id"]]
        pocket = jaw["pocket"]
        center = Vector(pocket["center"][:2])
        near = Vector(arc["path"][-1][:2])
        endpoints = (Vector(jaw["p1"][:2]), Vector(jaw["p2"][:2]))
        raw_far = max(endpoints, key=lambda point: (point - near).length)
        far = Vector(G._segment_circle_intersection(
            tuple(near), tuple(raw_far), pocket["center"],
            pocket["radius"])[:2])
        toward_main = (near - far).normalized()
        taper_length = min(C.DD_CUSHION_JAW_TAPER_L,
                           (near - far).length * 0.45)
        taper_start = near - toward_main * taper_length
        back = -Vector(jaw["normal"][:2]).normalized()
        radial = far - center
        projection = radial.dot(back)
        inner_welt_r = (pocket["radius"] +
                        C.DD_POCKET_WELT_MAJOR_OFFSET -
                        C.DD_POCKET_WELT_R)
        reach = (-projection +
                 math.sqrt(projection * projection +
                           inner_welt_r ** 2 - pocket["radius"] ** 2) +
                 C.DD_CUSHION_JAW_WELT_OVERLAP)
        band = max(arc["profile_width"], reach)
        seat_r = (pocket["radius"] +
                  C.DD_POCKET_WELT_MAJOR_OFFSET +
                  C.DD_POCKET_WELT_R + 0.0015)
        # Inner edge tracks the upholstery exactly: jaw band beside the
        # facing zone, cloth taper width at the transition.
        # Keep the horn a 0.2 mm reveal inside the seat cut so no horn face
        # is ever coincident with the cap's Boolean cut surface.
        horn_r = seat_r - 0.0002
        far_in = far + back * (band + gap)
        ts_in = taper_start + back * (band + gap)
        near_in = near + back * (arc["profile_width"] + gap)
        if (far_in - center).length > horn_r:
            far_in = center + (far_in - center).normalized() * horn_r
        # Outer edge lies on the owning board line one covered width behind
        # the nose, from the transition out to where the ring seat cut ends
        # that board.
        n_main = Vector(main["normal"][:2]).normalized()
        p1_main = Vector(main["p1"][:2])
        denom = back.dot(n_main)
        if abs(denom) < 1e-6:
            raise RuntimeError("jaw %s runs parallel to its board edge" %
                               jaw["id"])
        s = (-C.CUSHION_COVERED_W -
             (near_in - p1_main).dot(n_main)) / denom
        e = near_in + back * s
        if (e - center).length >= horn_r:
            g_away = e
        else:
            d = Vector((-n_main.y, n_main.x))
            half_b = (e - center).dot(d)
            half_c = (e - center).length_squared - horn_r * horn_r
            disc = half_b * half_b - half_c
            if disc <= 0.0:
                raise RuntimeError("board edge misses the ring seat at jaw "
                                   + jaw["id"])
            roots = (-half_b - math.sqrt(disc), -half_b + math.sqrt(disc))
            # Both crossings exist; keep the one on this jaw's flank so the
            # outer edge never walks across the open mouth.
            ref = near_in - center
            candidates = [e + d * t for t in roots]
            same_side = [g for g in candidates if (g - center).dot(ref) > 0.0]
            g_away = (min(same_side, key=lambda g: (g - e).length)
                      if same_side else
                      min(candidates, key=lambda g: (g - e).length))
        a0 = math.atan2((g_away - center).y, (g_away - center).x)
        a1 = math.atan2((far_in - center).y, (far_in - center).x)
        sweep = a1 - a0
        while sweep <= -math.pi:
            sweep += 2.0 * math.pi
        while sweep > math.pi:
            sweep -= 2.0 * math.pi
        arc_pts = []
        steps = 12
        for i in range(1, steps):
            ang = a0 + sweep * i / steps
            arc_pts.append(center + Vector((math.cos(ang), math.sin(ang))) *
                           horn_r)
        polygon = [tuple(far_in), tuple(ts_in), tuple(near_in), tuple(e),
                   tuple(g_away)] + [tuple(p) for p in arc_pts]
        name = MAIN_NAMES[main["id"]]
        material = (mats.get("walnut_cross", mats["walnut"])
                    if name.startswith("End_") else mats["walnut"])
        horn = _prism_polygon("PT_CapHorn_%s_%s" % (pocket["name"],
                                                    jaw["id"]),
                              polygon, z0, z1, VIS, material)
        horn["cap_thickness_m"] = C.DD_RAIL_CAP_T
        horn["grain_axis"] = ("world_x" if name.startswith("End_")
                              else "world_y")
        horn["jaw_contract_id"] = jaw["id"]
        horn["band_width_m"] = band
        horn["seat_radius_m"] = seat_r
        bevel = horn.modifiers.new("PT_CapHorn_EdgeEase", "BEVEL")
        bevel.width = 0.0015
        bevel.segments = 3
        bevel.limit_method = "ANGLE"
        bevel.angle_limit = radians(22.5)
        horn["edge_ease_m"] = 0.0015
        made.append(horn)
    if len(made) != 12:
        raise RuntimeError("expected twelve cap horns, built %d" % len(made))
    return made


def _path(row, p1=None, p2=None):
    a = p1 if p1 is not None else row["p1"]
    b = p2 if p2 is not None else row["p2"]
    return [pf(a[0], a[1]), pf(b[0], b[1])]


def _normal(row):
    n = row["normal"]
    return Vector((n[0], n[1], 0.0))


def _append_path(path, normals, points, point_normals,
                 widths=None, point_widths=None):
    """Append one connected segment without duplicate capped junctions."""
    if widths is not None and point_widths is None:
        raise ValueError("point widths are required for a variable path")
    values = point_widths if point_widths is not None else [None] * len(points)
    for point, normal, width in zip(points, point_normals, values):
        point = Vector(point)
        normal = Vector((normal[0], normal[1], 0.0))
        if path and (point - path[-1]).length <= 1e-8:
            blended = normals[-1] + normal
            normals[-1] = blended.normalized() if blended.length else normal
            if widths is not None:
                widths[-1] = min(widths[-1], width)
            continue
        path.append(point)
        normals.append(normal.normalized())
        if widths is not None:
            widths.append(width)


def _continuous_cushion_path(main, rows_by_id, arcs):
    """Return one terminal-to-terminal path for a manufactured rail."""
    connected = [arc for arc in arcs if arc["main_id"] == main["id"]]
    if len(connected) != 2:
        raise RuntimeError("main rail %s must own two transition arcs" %
                           main["id"])
    p1, p2 = Vector(main["p1"]), Vector(main["p2"])
    connected.sort(key=lambda arc: (Vector(arc["path"][0]) - p1).length)
    first, second = connected
    if (Vector(first["path"][0]) - p1).length > 1e-7 or \
            (Vector(second["path"][0]) - p2).length > 1e-7:
        raise RuntimeError("rail %s arc endpoints do not match main" %
                           main["id"])

    def jaw_route(arc, reverse):
        jaw = rows_by_id[arc["jaw_id"]]
        near = Vector(arc["path"][-1])
        endpoints = (Vector(jaw["p1"]), Vector(jaw["p2"]))
        raw_far = max(endpoints, key=lambda point: (point - near).length)
        pocket = jaw["pocket"]
        # Pooltool extends each analytic jaw slightly inside its capture
        # circle. That continuation belongs to collision math, not the
        # manufactured cushion. Stop the visible jaw at the true circle
        # crossing so no green tab intrudes into the pocket opening.
        far = Vector(G._segment_circle_intersection(
            tuple(near), tuple(raw_far), pocket["center"],
            pocket["radius"]))
        toward_main = (near - far).normalized()
        facing_end = far + toward_main * min(
            C.POCKET_FACING_T, (near - far).length * 0.35)
        taper_length = min(C.DD_CUSHION_JAW_TAPER_L,
                           (near - facing_end).length * 0.45)
        taper_start = near - toward_main * taper_length
        normal = _normal(jaw)
        back = -normal
        radial = far - Vector(pocket["center"])
        projection = radial.dot(back)
        inner_welt_r = (pocket["radius"] +
                        C.DD_POCKET_WELT_MAJOR_OFFSET -
                        C.DD_POCKET_WELT_R)
        discriminant = (projection * projection + inner_welt_r ** 2 -
                        pocket["radius"] ** 2)
        if discriminant <= 0.0:
            raise RuntimeError("jaw does not reach pocket welt: " +
                               jaw["id"])
        # The jaw is a constant-width upholstered band: the rail cloth strip
        # turns off the rail and follows the jaw cut into the mouth, exactly
        # as the reference tables read.  Flaring the band outward to the welt
        # ring makes each jaw a wedge whose sharp end points at the playfield
        # (the reported V).  The band only needs to reach the welt tube's
        # inner radius; the iron's open-U ends and mount ears cover that
        # seam, so no wider overlap is required.
        reach_width = (-projection + math.sqrt(discriminant) +
                       C.DD_CUSHION_JAW_WELT_OVERLAP)
        band_width = max(arc["profile_width"], reach_width)
        route = [far, facing_end, taper_start, near]
        route_widths = [band_width, band_width,
                        band_width, arc["profile_width"]]
        if not reverse:
            route.reverse()
            route_widths.reverse()
        return route, [normal] * len(route), route_widths

    path, normals, widths = [], [], []
    points, point_normals, point_widths = jaw_route(first, reverse=True)
    _append_path(path, normals, points, point_normals, widths, point_widths)
    _append_path(path, normals, list(reversed(first["path"])),
                 list(reversed(first["normals"])), widths,
                 [first["profile_width"]] * len(first["path"]))
    midpoint = (p1 + p2) * 0.5
    main_normal = _normal(main)
    tangent = (p2 - p1).normalized()
    blend_length = min(0.035, (p2 - p1).length * 0.20)
    main_points = [p1, p1 + tangent * blend_length, midpoint,
                   p2 - tangent * blend_length, p2]
    _append_path(path, normals, main_points,
                 [main_normal] * len(main_points), widths,
                 [first["profile_width"], C.CUSHION_COVERED_W,
                  C.CUSHION_COVERED_W, C.CUSHION_COVERED_W,
                  second["profile_width"]])
    _append_path(path, normals, second["path"], second["normals"], widths,
                 [second["profile_width"]] * len(second["path"]))
    points, point_normals, point_widths = jaw_route(second, reverse=False)
    _append_path(path, normals, points, point_normals, widths, point_widths)
    return ([pf(point.x, point.y) for point in path], normals, widths,
            connected)


def _featherstrip(name, path, normals, widths, mats):
    """Buried wood strip that clamps the finished rail cloth in its groove."""
    back = C.CUSHION_COVERED_W
    top = C.RAIL_TOP_Z - C.BED_Z
    profile = [(back - 0.004, top - 0.004),
               (back - 0.004, top - 0.001),
               (back + 0.002, top - 0.001),
               (back + 0.002, top - 0.004)]
    strip = _extrude_variable_profile(
        "PT_Featherstrip_" + name, path, normals, profile, widths,
        ENG, mats["walnut"])
    strip.hide_render = True
    strip["covered_by_rail_cloth"] = True
    return strip


def build_cushions_and_rails(mats, data):
    """Six upholstered rails over the shared solver contact geometry."""
    made = []
    cushion_prof = k66_profile()
    # The cloth-covered envelope reaches the featherstrip groove, while the
    # buried neoprene facing terminates at the published K-66-class rubber
    # face depth.  Do not give the core the full upholstered rail width.
    facing_prof = [(min(distance, C.K66_FACE), height)
                   for distance, height in cushion_prof]
    wood_prof = rail_profile()
    rows = G.linear_rows(data)
    rows_by_id = {row["id"]: row for row in rows}
    arcs = G.arc_rows(data, steps=16)

    # A real table has six manufactured cushion rails, not 30 separately
    # capped solver pieces.  Each visible cloth envelope runs continuously
    # from one pocket terminal through jaw, fillet and main to the opposite
    # terminal.  The linear/arc solver features remain separate below.
    for row in (item for item in rows if item["kind"] == "main"):
        name = MAIN_NAMES[row["id"]]
        cushion_path, cushion_normals, cushion_widths, connected = \
            _continuous_cushion_path(row, rows_by_id, arcs)
        cushion = _extrude_variable_profile(
            "PT_Cushion_" + name, cushion_path, cushion_normals,
            cushion_prof, cushion_widths, VIS, mats["cloth"])
        cushion["main_contract_id"] = row["id"]
        cushion["jaw_contract_ids"] = ",".join(
            sorted(arc["jaw_id"] for arc in connected))
        # Same nap-free worsted cloth, with a face-calibrated shader so the
        # steep wrap does not collapse to a false black insert under grazing
        # light.
        facing_material = mats["cloth_facing"]
        cushion.data.materials.append(facing_material)
        profile_count = len(cushion_prof)
        # Wrap the full pocket-facing zone, not only the planar end cap. A
        # real facing carries the same rail cloth around the final short jaw
        # segment; leaving that segment on the main cloth shader reads as a
        # black triangular insert under grazing light.
        first_terminal = set(range(2 * profile_count))
        last_terminal = set(range(len(cushion.data.vertices) -
                                  2 * profile_count,
                                  len(cushion.data.vertices)))
        facing_polygons = 0
        for polygon in cushion.data.polygons:
            vertices = set(polygon.vertices)
            if vertices.issubset(first_terminal) or \
                    vertices.issubset(last_terminal):
                polygon.material_index = 1
                facing_polygons += 1
        if facing_polygons != 12:
            raise RuntimeError("cushion %s does not have two wrapped facing zones" %
                               cushion.name)
        cushion["pocket_facing_cloth_polygons"] = facing_polygons
        # The terminal is a cloth-wrapped facing, not a razor-cut black tab.
        # Round only the two terminal profile rings; the exact solver nose
        # along the rail remains untouched.
        terminal_vertices = list(range(profile_count)) + list(range(
            len(cushion.data.vertices) - profile_count,
            len(cushion.data.vertices)))
        terminal_group = cushion.vertex_groups.new(
            name="PocketFacingEdge")
        terminal_group.add(terminal_vertices, 1.0, "REPLACE")
        terminal_bevel = cushion.modifiers.new(
            "PT_CushionTerminal_ClothEase", "BEVEL")
        terminal_bevel.limit_method = "VGROUP"
        terminal_bevel.vertex_group = terminal_group.name
        terminal_bevel.width = C.DD_CUSHION_TERMINAL_EDGE_RADIUS
        terminal_bevel.segments = 3
        if hasattr(terminal_bevel, "harden_normals"):
            terminal_bevel.harden_normals = True
        cushion["terminal_edge_radius_m"] = \
            C.DD_CUSHION_TERMINAL_EDGE_RADIUS
        made.append(cushion)
        made.append(_featherstrip(
            name, cushion_path, cushion_normals, cushion_widths, mats))

        # Six true structural rail bodies stop at the tangent transitions; no
        # full rail-width extension is allowed across a pocket mouth.
        path = _path(row)
        n = _normal(row)
        normals = [n, n]
        rail_material = (mats.get("walnut_cross", mats["walnut"])
                         if name.startswith("End_") else mats["walnut"])
        rail = _extrude_profile("PT_Rail_" + name, path, normals,
                                wood_prof, VIS, rail_material)
        rail["grain_axis"] = ("world_x" if name.startswith("End_")
                              else "world_y")
        made.append(rail)

    # The rail cloth wraps continuously over each jaw and its pocket-facing
    # pad.  The measured neoprene facing is therefore an engineering core,
    # not an exposed black patch on the finished playing surface.  Keeping
    # the core separate preserves the real assembly and WPA thickness while
    # the visible cushion remains one uninterrupted upholstered envelope.
    for row in (item for item in rows if item["kind"] == "jaw"):
        pocket = row["pocket"]
        a, b = Vector(row["p1"]), Vector(row["p2"])
        center = Vector(pocket["center"])
        if (a - center).length > (b - center).length:
            a, b = b, a
        a = Vector(G._segment_circle_intersection(
            tuple(b), tuple(a), pocket["center"], pocket["radius"]))
        tangent = (b - a).normalized()
        split = a + tangent * min(C.POCKET_FACING_T, (b - a).length * 0.35)
        n = _normal(row)
        facing_path = [pf(a.x, a.y), pf(split.x, split.y)]
        full_path = [pf(a.x, a.y), pf(b.x, b.y)]
        facing = _extrude_profile(
            "PT_PocketFacing_%s_%s" % (pocket["name"], row["id"]),
            facing_path, [n, n], facing_prof, ENG, mats["facing"])
        facing.hide_render = True
        facing["thickness_m"] = (split - a).length
        facing["covered_by_rail_cloth"] = True
        made.append(facing)
        subrail = _extrude_profile("PT_JawSubrail_" + row["id"],
                                   full_path, [n, n], wood_prof,
                                   ENG, mats["walnut"])
        subrail.hide_render = True
        made.append(subrail)

    # Pooltool's circular contacts remain explicit hidden support/inspection
    # geometry even though the visible upholstery is continuous.
    for arc in arcs:
        path = [pf(point[0], point[1]) for point in arc["path"]]
        normals = [Vector((n[0], n[1], 0.0)) for n in arc["normals"]]
        scale = arc["profile_width"] / C.CUSHION_COVERED_W
        arc_wood_profile = [(distance * scale, height)
                            for distance, height in wood_prof]
        subrail = _extrude_profile("PT_ArcSubrail_" + arc["id"], path,
                                   normals, arc_wood_profile, ENG,
                                   mats["walnut"], smooth=True)
        subrail.hide_render = True
        made.append(subrail)
    return made


def build_slate(mats):
    """Three touching slabs, seams crossing the short axis, with a liner."""
    made = []
    span = C.PLAY_L + 2 * C.RAIL_PLAN_W
    width = C.PLAY_W + 2 * C.RAIL_PLAN_W
    third = span / 3.0
    for i, tag in enumerate(("Foot", "Center", "Head")):
        y = -span / 2.0 + third * (i + 0.5)
        ob = L.box("PT_Slate_" + tag, (width, third, C.SLATE_T),
                   pf(0, y, -C.SLATE_T / 2.0 - C.CLOTH_T), VIS,
                   mats["slate"])
        ob["joint_gap_m"] = 0.0
        made.append(ob)
    # under-slate wooden liner (Uniliner-class support ledge)
    made.append(L.box("PT_SlateLiner_Perimeter",
                      (width + 0.02, span + 0.02, C.LINER_T),
                      pf(0, 0, -C.SLATE_T - C.LINER_T / 2.0 - C.CLOTH_T),
                      ENG, mats["walnut"]))
    return made


def build_cloth(mats):
    """Bed cloth: a thin skin over the slate, cut by the pockets."""
    span = C.PLAY_L + 2 * C.RAIL_PLAN_W
    width = C.PLAY_W + 2 * C.RAIL_PLAN_W
    return L.box("PT_Cloth_Bed", (width, span, C.CLOTH_T),
                 pf(0, 0, -C.CLOTH_T / 2.0), VIS, mats["cloth_bed"])


def build_sights(mats):
    """
    18 mother-of-pearl sights, WPA 12.5 in spacing, 3 11/16 in from the nose.
    Long rails carry 3 per half; short rails carry 3 across.
    """
    made = []
    off = C.SIGHT_OFFSET_FROM_NOSE
    top_z = C.RAIL_TOP_Z - C.BED_Z
    d = 0.0135
    sight_z = top_z - C.DD_SIGHT_T / 2.0
    for sx in (-1, 1):
        for i in range(1, 8):
            if i == 4:                       # the side pocket lives here
                continue
            y = -HL + C.PLAY_L * i / 8.0
            made.append(L.box("PT_Sight_Long_%s_%d" % ("W" if sx < 0 else "E", i),
                              (d, d, C.DD_SIGHT_T),
                              pf(sx * (HW + off), y, sight_z), VIS,
                              mats["pearl"], rotation=(0, 0, radians(45))))
    for sy in (-1, 1):
        for i in (1, 2, 3):
            x = -HW + C.PLAY_W * i / 4.0
            made.append(L.box("PT_Sight_End_%s_%d"
                              % ("Foot" if sy < 0 else "Head", i),
                              (d, d, C.DD_SIGHT_T),
                              pf(x, sy * (HL + off), sight_z), VIS,
                              mats["pearl"], rotation=(0, 0, radians(45))))
    return made


def _loop_fractions(points):
    lengths = [G.distance(points[index], points[(index + 1) % len(points)])
               for index in range(len(points))]
    perimeter = sum(lengths)
    if perimeter <= 1e-12:
        raise ValueError("closed loop has no perimeter")
    fractions = []
    travelled = 0.0
    for length in lengths:
        fractions.append(travelled / perimeter)
        travelled += length
    return fractions


def _sample_closed_loop(points, fractions, value):
    if value <= 1e-13:
        return points[0]
    index = max(0, bisect_right(fractions, value + 1e-14) - 1)
    if abs(value - fractions[index]) <= 1e-12:
        return points[index]
    following = (index + 1) % len(points)
    start = fractions[index]
    end = fractions[following] if following else 1.0
    amount = (value - start) / max(1e-14, end - start)
    return (points[index][0] +
            (points[following][0] - points[index][0]) * amount,
            points[index][1] +
            (points[following][1] - points[index][1]) * amount)


def _match_closed_loops(first, second):
    """Subdivide two perimeters at their combined arclength parameters.

    The source loop is not moved: its exact vertices remain anchors and only
    collinear subdivisions are added.  The buffered loop is likewise
    preserved.  Equal vertex counts then produce a closed manifold strip.
    """
    first_fractions = _loop_fractions(first)
    second_fractions = _loop_fractions(second)
    common = []
    for value in sorted(first_fractions + second_fractions):
        # Blender stores mesh coordinates as float32. Perimeter stations less
        # than 1e-7 apart can collapse to one vertex after mesh creation and
        # make an otherwise simple drafted loop report a self-crossing.
        if not common or abs(value - common[-1]) > 1e-7:
            common.append(value)
    first_ring = [_sample_closed_loop(first, first_fractions, value)
                  for value in common]
    second_ring = [_sample_closed_loop(second, second_fractions, value)
                   for value in common]
    return first_ring, second_ring, common, first_fractions


def _convex_hull(points):
    """Deterministic CCW hull for a conservative engineering clearance."""
    ordered = sorted(set((float(x), float(y)) for x, y in points))
    if len(ordered) < 3:
        raise ValueError("clearance hull needs at least three unique points")

    def cross(origin, first, second):
        return ((first[0] - origin[0]) * (second[1] - origin[1]) -
                (first[1] - origin[1]) * (second[0] - origin[0]))

    lower = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _subdivided_source_edge(common, source_fractions, source_edge):
    start = source_fractions[source_edge]
    end = (source_fractions[source_edge + 1]
           if source_edge + 1 < len(source_fractions) else 1.0)
    result = set()
    for index, value in enumerate(common):
        following = common[index + 1] if index + 1 < len(common) else 1.0
        midpoint = (value + following) / 2.0
        if start - 1e-12 <= midpoint <= end + 1e-12:
            result.add(index)
    if not result:
        raise ValueError("semantic source edge vanished during subdivision")
    return result


def _match_capture_arc_draft(top_ring, bottom_ring, capture_arc, center,
                             expansion):
    """Pair the visible round pocket wall along true radial draft lines.

    General polygon loops are matched by perimeter station, which is robust
    for manifold Boolean proofs but can twist a ruled render surface where a
    round capture arc occupies a different fraction of the buffered loop.
    The buffer of that circular arc has an exact radial correspondence.  Use
    it for the visible cloth wrap so the liner is a smooth drafted surface,
    not a sequence of shallow pleats.
    """
    centre = Vector(center)
    flags = []
    for point in top_ring:
        flags.append(any(
            G.point_segment_distance(point, capture_arc[edge],
                                     capture_arc[edge + 1]) <= 2e-6
            for edge in range(len(capture_arc) - 1)
        ))
    starts = [index for index, flag in enumerate(flags)
              if flag and not flags[index - 1]]
    if len(starts) != 1:
        raise ValueError("capture-arc liner must contain one contiguous run")
    indices = []
    index = starts[0]
    while flags[index]:
        indices.append(index)
        index = (index + 1) % len(flags)
        if index == starts[0]:
            break
    if len(indices) < len(capture_arc):
        raise ValueError("capture-arc draft correspondence is incomplete")

    # The underlying contract is a true circular capture arc.  Uniformly
    # resample that run instead of retaining the union of unrelated source-
    # and-buffer perimeter stations, which produces repeating narrow quads.
    angles = [math.atan2(point[1] - centre.y, point[0] - centre.x)
              for point in capture_arc]
    for offset in range(1, len(angles)):
        while angles[offset] - angles[offset - 1] > math.pi:
            angles[offset] -= 2.0 * math.pi
        while angles[offset] - angles[offset - 1] < -math.pi:
            angles[offset] += 2.0 * math.pi
    radius = sum((Vector(point) - centre).length
                 for point in capture_arc) / len(capture_arc)
    adjusted_top = list(top_ring)
    adjusted_bottom = list(bottom_ring)
    denominator = max(1, len(indices) - 1)
    for station, ring_index in enumerate(indices):
        amount = station / denominator
        angle = angles[0] + (angles[-1] - angles[0]) * amount
        direction = Vector((math.cos(angle), math.sin(angle)))
        adjusted_top[ring_index] = tuple(centre + direction * radius)
        adjusted_bottom[ring_index] = tuple(
            centre + direction * (radius + expansion))
    return adjusted_top, adjusted_bottom, len(indices)


def _tapered_pocket_cutter(name, outline, centroid):
    """Three-ring prism: vertical above bed, WPA back-draft below bed."""
    z_top = C.RAIL_TOP_Z - C.BED_Z + 0.020
    # The shelf datum is the first vertical cut at the slate top beneath the
    # cloth. Starting draft above this plane silently shortens the shelf.
    z_bed = -C.CLOTH_T
    z_bottom = -C.CLOTH_T - C.SLATE_T - 0.020
    draft_height = z_bed - z_bottom
    grow = draft_height * tan(radians(C.BACK_DRAFT))
    bottom_outline = G.outward_buffer(outline, grow)
    top_ring, bottom_ring, _common, _source = _match_closed_loops(
        outline, bottom_outline)
    rings = []
    for z, ring in ((z_top, top_ring), (z_bed, top_ring),
                    (z_bottom, bottom_ring)):
        rings.append([(CX + x, CY + y, C.BED_Z + z) for x, y in ring])
    n = len(top_ring)
    verts = [point for ring in rings for point in ring]
    faces = []
    for layer in range(2):
        a, b = layer * n, (layer + 1) * n
        for index in range(n):
            nxt = (index + 1) % n
            faces.append((a + index, a + nxt, b + nxt, b + index))
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple(2 * n + index for index in range(n)))
    cutter = L.mesh_object("CUT_" + name, verts, faces, ENG)
    # Boolean DIFFERENCE depends on a positively oriented closed volume.
    # The three rings are authored top-to-bottom, which can leave the raw
    # side winding inward even though the mesh is manifold.  An inverted
    # cutter makes Blender report a successful apply while only splitting
    # target faces and leaving the pocket physically capped.
    bm = bmesh.new()
    bm.from_mesh(cutter.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(cutter.data)
    bm.free()
    cutter.data.update()
    cutter["is_cutter"] = True
    cutter["back_draft_deg"] = C.BACK_DRAFT
    cutter["draft_height_m"] = draft_height
    cutter["bottom_expansion_m"] = grow
    cutter["source_outline_vertices"] = len(outline)
    cutter["buffer_outline_vertices"] = len(bottom_outline)
    cutter["matched_ring_vertices"] = n
    draft_angles = [math.degrees(math.atan(
        G.polygon_boundary_distance(point, outline) / draft_height))
        for point in bottom_ring]
    cutter["measured_draft_min_deg"] = min(draft_angles)
    cutter["measured_draft_max_deg"] = max(draft_angles)
    return cutter


def _annular_sector(name, center, inner, outer, depth, z, angle, sweep,
                    collection, mat, segments=36):
    """Open horseshoe sector used for a real below-bed pocket casting/lip."""
    verts, faces = [], []
    for index in range(segments + 1):
        a = angle - sweep / 2.0 + sweep * index / segments
        ca, sa = math.cos(a), math.sin(a)
        verts.extend(((inner * ca, inner * sa, -depth / 2.0),
                      (inner * ca, inner * sa, depth / 2.0),
                      (outer * ca, outer * sa, -depth / 2.0),
                      (outer * ca, outer * sa, depth / 2.0)))
    for index in range(segments):
        a, b = index * 4, (index + 1) * 4
        faces.extend(((a, b, b + 1, a + 1),
                      (a + 2, a + 3, b + 3, b + 2),
                      (a + 1, b + 1, b + 3, a + 3),
                      (a, a + 2, b + 2, b)))
    faces.extend(((0, 1, 3, 2),
                  (segments * 4, segments * 4 + 2,
                   segments * 4 + 3, segments * 4 + 1)))
    ob = L.mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = pf(center[0], center[1], z)
    return ob


def _torus_sector(name, center, major_radius, tube_radius, z, angle, sweep,
                  collection, mat, segments=48, tube_segments=12):
    """Closed, padded open-U tube for the leather-wrapped pocket iron."""
    if major_radius <= tube_radius or tube_radius <= 0.0:
        raise ValueError("pocket welt radii are invalid")
    verts, faces = [], []
    for station in range(segments + 1):
        a = angle - sweep / 2.0 + sweep * station / segments
        ca, sa = math.cos(a), math.sin(a)
        for ring in range(tube_segments):
            b = 2.0 * math.pi * ring / tube_segments
            radial = major_radius + tube_radius * math.cos(b)
            verts.append((radial * ca, radial * sa,
                          tube_radius * math.sin(b)))
    for station in range(segments):
        first = station * tube_segments
        following = (station + 1) * tube_segments
        for ring in range(tube_segments):
            nxt = (ring + 1) % tube_segments
            faces.append((first + ring, following + ring,
                          following + nxt, first + nxt))
    faces.append(tuple(range(tube_segments))[::-1])
    end = segments * tube_segments
    faces.append(tuple(end + ring for ring in range(tube_segments)))
    ob = L.mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = pf(center[0], center[1], z)
    L.orient_closed_mesh_outward(ob)
    ob["major_radius_m"] = major_radius
    ob["tube_radius_m"] = tube_radius
    ob["open_sweep_deg"] = math.degrees(sweep)
    ob["open_toward_playfield_deg"] = 360.0 - math.degrees(sweep)
    return ob


def _stitched_arc(name, center, radius, z, angle, sweep, collection, mat,
                  count=14):
    """One mesh containing discrete, slightly proud leather stitch dashes."""
    verts, faces = [], []
    dash_l = 0.0034
    dash_w = C.DD_POCKET_STITCH_W
    dash_h = C.DD_POCKET_STITCH_H
    box_faces = ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                 (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))
    for index in range(count):
        amount = (index + 0.75) / (count + 0.5)
        a = angle - sweep / 2.0 + sweep * amount
        tangent = Vector((-math.sin(a), math.cos(a), 0.0))
        radial = Vector((math.cos(a), math.sin(a), 0.0))
        centre = radial * radius
        base = len(verts)
        for tangent_sign, radial_sign, z_sign in (
                (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            point = (centre + tangent * (tangent_sign * dash_l / 2.0) +
                     radial * (radial_sign * dash_w / 2.0))
            verts.append((point.x, point.y, z_sign * dash_h / 2.0))
        faces.extend(tuple(base + vertex for vertex in face)
                     for face in box_faces)
    ob = L.mesh_object(name, verts, faces, collection, mat)
    ob.location = pf(center[0], center[1], z)
    ob["stitch_count"] = count
    return ob


def _open_ribbon_solid(name, inner_path, outer_path, z_bottom, z_top,
                       collection, mat):
    """Closed low-profile welt following an open manufactured pocket path."""
    if len(inner_path) != len(outer_path) or len(inner_path) < 2:
        raise ValueError("pocket welt paths must have equal useful lengths")
    if z_top <= z_bottom:
        raise ValueError("pocket welt must have positive height")
    count = len(inner_path)
    verts = []
    for z in (z_bottom, z_top):
        verts.extend((CX + point[0], CY + point[1], C.BED_Z + z)
                     for point in inner_path)
        verts.extend((CX + point[0], CY + point[1], C.BED_Z + z)
                     for point in outer_path)
    inner_bottom = 0
    outer_bottom = count
    inner_top = 2 * count
    outer_top = 3 * count
    faces = []
    for index in range(count - 1):
        nxt = index + 1
        faces.extend((
            (inner_top + index, outer_top + index,
             outer_top + nxt, inner_top + nxt),
            (inner_bottom + index, inner_bottom + nxt,
             outer_bottom + nxt, outer_bottom + index),
            (inner_bottom + index, inner_top + index,
             inner_top + nxt, inner_bottom + nxt),
            (outer_bottom + index, outer_bottom + nxt,
             outer_top + nxt, outer_top + index),
        ))
    faces.extend((
        (inner_bottom, outer_bottom, outer_top, inner_top),
        (inner_bottom + count - 1, inner_top + count - 1,
         outer_top + count - 1, outer_bottom + count - 1),
    ))
    result = L.mesh_object(name, verts, faces, collection, mat)
    L.orient_closed_mesh_outward(result)
    # The segmented inner/outer leather walls are one continuous molded
    # surface; keep the top/bottom landing faces planar while smoothing only
    # those two walls.
    for index, polygon in enumerate(result.data.polygons[:-2]):
        if index % 4 in (2, 3):
            polygon.use_smooth = True
    result["open_path_vertices"] = count
    return result


def _capture_arc_path(outline, center, radius, tolerance=2e-6):
    """Extract the one contiguous pocket-circle run from a canonical outline."""
    flags = [abs((Vector(point) - Vector(center)).length - radius) <= tolerance
             for point in outline]
    starts = [index for index, on_circle in enumerate(flags)
              if on_circle and not flags[(index - 1) % len(flags)]]
    if len(starts) != 1:
        raise RuntimeError("pocket outline must contain one capture-circle run")
    path = []
    index = starts[0]
    while flags[index]:
        path.append(outline[index])
        index = (index + 1) % len(outline)
        if index == starts[0]:
            break
    if len(path) < 3:
        raise RuntimeError("capture-circle run is too short")
    return path


def _ruled_pocket_wall(name, top_points, bottom_points, z_top, z_bottom,
                       collection, mat, smooth=False, skip_edges=None):
    """Open transition wall between two equal-count plan outlines."""
    if len(top_points) != len(bottom_points) or len(top_points) < 3:
        raise ValueError("pocket wall outlines must have equal point counts")
    count = len(top_points)
    skipped = set(skip_edges or ())
    if any(index < 0 or index >= count for index in skipped):
        raise ValueError("pocket wall skip edge is outside its ring")
    verts = [(CX + x, CY + y, C.BED_Z + z_top)
             for x, y in top_points]
    verts.extend((CX + x, CY + y, C.BED_Z + z_bottom)
                 for x, y in bottom_points)
    faces = []
    for index in range(count):
        if index in skipped:
            continue
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))
    result = L.mesh_object(name, verts, faces, collection, mat, smooth=smooth)
    result["ring_vertex_count"] = count
    result["open_edge_count"] = len(skipped)
    result["open_edge_indices"] = ",".join(str(index)
                                              for index in sorted(skipped))
    return result


def _pocket_outward(center, kind):
    """Return the physical rail-normal bisector, independent of table ratio."""
    if kind == "corner":
        return Vector((1.0 if center.x > 0.0 else -1.0,
                       1.0 if center.y > 0.0 else -1.0)).normalized()
    return center.normalized()


def build_pockets(mats, data):
    """Drafted cuts, rail-top horseshoe irons and leather drop pockets."""
    made = []
    for pocket in G.pocket_rows(data):
        key = pocket["name"]
        center = Vector(pocket["center"])
        outline, centroid, mouth_edge = G.pocket_outline_details(data, pocket)
        capture_arc = _capture_arc_path(
            outline, center, pocket["radius"])
        rail_cutter = _tapered_pocket_cutter(
            "Rail_" + key, outline, centroid)
        rail_cutter["cutter_role"] = "rail_opening"
        outward = _pocket_outward(center, pocket["kind"])
        # The cap boards keep their wood horns: the routed edge follows each
        # jaw cut down to the iron, as on the reference tables.  The only
        # extra wood removed is (a) a circular seat for the welt ring plus
        # its recessed iron, and (b) an outboard slot for the hardware that
        # hangs past the table edge.  A full-width rectangle here amputates
        # the horns and forces the cloth to fill the gap as the V-shaped
        # wedges the pocket revision is removing.
        seat_r = (pocket["radius"] +
                  C.DD_POCKET_WELT_MAJOR_OFFSET +
                  C.DD_POCKET_WELT_R + 0.0015)
        seat_outline = [
            (center.x + seat_r * math.cos(2.0 * math.pi * i / 48),
             center.y + seat_r * math.sin(2.0 * math.pi * i / 48))
            for i in range(48)
        ]
        seat_cutter = _tapered_pocket_cutter(
            "RailSeat_" + key, seat_outline, tuple(center))
        seat_cutter["cutter_role"] = "rail_outboard_clearance"
        seat_cutter["seat_radius_m"] = seat_r

        # WPA shelf is horizontal bed cloth/slate between the theoretical
        # sharp cushion-mouth line and the first vertical drop.  It is not the
        # rail opening and therefore needs its own cut loop.
        shelf_target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                        else C.SIDE_SHELF)
        shelf = G.pocket_shelf_cut_details(data, pocket, shelf_target)
        cut_outline = shelf["outline"]
        cut_centroid = shelf["centroid"]
        bed_cutter = _tapered_pocket_cutter(
            "Bed_" + key, cut_outline, cut_centroid)
        bed_cutter["cutter_role"] = "bed_drop"
        bed_cutter["shelf_target_m"] = shelf_target
        bed_cutter["shelf_measured_m"] = shelf["shelf_m"]
        bed_cutter["shelf_edge_index"] = shelf["shelf_edge"]
        cloth_cutter = _prism_polygon(
            "CUT_Cloth_" + key, cut_outline,
            C.BED_Z - C.CLOTH_T - 0.001,
            C.RAIL_TOP_Z + 0.020, ENG, None)
        cloth_cutter["is_cutter"] = True
        cloth_cutter["cutter_role"] = "cloth_drop"
        cloth_cutter["shelf_target_m"] = shelf_target
        cloth_cutter["shelf_measured_m"] = shelf["shelf_m"]
        cloth_cutter.hide_render = True

        basket_mouth_r = pocket["radius"] + 0.014

        # Cloth wraps over the cut slate edge; below that, an oxblood leather
        # throat funnels the non-circular WPA opening into the round drop
        # basket. These lit walls make depth legible instead of reading as a
        # flat black polygon in the hero camera.
        cloth_top = -C.CLOTH_T
        cloth_bottom = -C.CLOTH_T - C.SLATE_T - 0.006
        cloth_buffer = G.outward_buffer(
            cut_outline, (cloth_top - cloth_bottom) *
            tan(radians(C.BACK_DRAFT)))
        # Hidden wood must clear the actual drafted liner, not a guessed
        # circle around the basket.  Offset the exact bed cut to its
        # under-liner station, then add a 5 mm construction air gap.
        liner_bottom_local = -C.CLOTH_T - C.SLATE_T - C.LINER_T
        liner_expansion = (-C.CLOTH_T - liner_bottom_local) * \
            tan(radians(C.BACK_DRAFT))
        drafted_clearance = G.outward_buffer(
            cut_outline, liner_expansion + 0.005)
        assembly_radius = basket_mouth_r + C.DD_LEATHER_T + 0.008
        assembly_circle = [
            (center.x + math.cos(2.0 * math.pi * index / 48) *
             assembly_radius,
             center.y + math.sin(2.0 * math.pi * index / 48) *
             assembly_radius)
            for index in range(48)
        ]
        clearance_outline = _convex_hull(
            list(drafted_clearance) + assembly_circle)
        clearance_top = -C.CLOTH_T - C.SLATE_T + 0.010
        clearance_bottom = -C.DD_BASKET_DEPTH - 0.005
        clearance = _prism_polygon(
            "CUT_Engineering_" + key, clearance_outline,
            C.BED_Z + clearance_bottom, C.BED_Z + clearance_top,
            ENG, None)
        clearance["is_cutter"] = True
        clearance["cutter_role"] = "pocket_engineering_clearance"
        clearance["clearance_outline_vertices"] = len(clearance_outline)
        clearance["clearance_air_gap_m"] = 0.005
        clearance["assembly_clear_radius_m"] = assembly_radius
        clearance["clearance_bottom_z_m"] = C.BED_Z + clearance_bottom
        clearance.hide_render = True
        cloth_top_ring, cloth_bottom_ring, common, source_fractions = \
            _match_closed_loops(cut_outline, cloth_buffer)
        cloth_top_ring, cloth_bottom_ring, radial_pairs = \
            _match_capture_arc_draft(
            cloth_top_ring, cloth_bottom_ring, capture_arc, center,
            (cloth_top - cloth_bottom) * tan(radians(C.BACK_DRAFT)))
        shelf_edges = _subdivided_source_edge(
            common, source_fractions, shelf["shelf_edge"])
        cloth_liner = _ruled_pocket_wall(
            "PT_PocketLiner_" + key, cloth_top_ring,
            cloth_bottom_ring, cloth_top, cloth_bottom, VIS,
            mats["cloth_liner"],
            smooth=True)
        cloth_liner["source_shelf_edge_index"] = shelf["shelf_edge"]
        cloth_liner["subdivided_shelf_edge_indices"] = ",".join(
            str(index) for index in sorted(shelf_edges))
        cloth_liner["semantic_shelf_closed"] = True
        cloth_liner["shelf_target_m"] = shelf_target
        cloth_liner["shelf_measured_m"] = shelf["shelf_m"]
        cloth_liner["back_draft_deg"] = C.BACK_DRAFT
        cloth_liner["capture_arc_radial_pair_count"] = radial_pairs
        made.append(cloth_liner)
        throat_bottom = -0.052
        throat_ring = []
        for point in cloth_bottom_ring:
            direction = Vector((point[0] - center.x, point[1] - center.y))
            if direction.length:
                direction.normalize()
            throat_ring.append((center.x + direction.x * basket_mouth_r,
                                center.y + direction.y * basket_mouth_r))
        throat = _ruled_pocket_wall(
            "PT_PocketThroat_" + key, cloth_bottom_ring, throat_ring,
            cloth_bottom, throat_bottom, VIS,
            mats.get("leather_interior", mats["leather"]), smooth=True)
        throat["open_throat_radius_m"] = basket_mouth_r
        throat["semantic_shelf_closed"] = True
        made.append(throat)

        # The upper assembly is one manufactured U: a blackened cast iron at
        # rail-top height, a padded leather welt around it and mounting ears
        # extending under the two rail-cap ends.  It is deliberately not the
        # 243-254 degree capture arc used by the old near-circular collar.
        outward = _pocket_outward(center, pocket["kind"])
        angle = math.atan2(outward.y, outward.x)
        r = pocket["radius"]
        sweep_deg = (C.DD_POCKET_CORNER_SWEEP_DEG
                     if pocket["kind"] == "corner"
                     else C.DD_POCKET_SIDE_SWEEP_DEG)
        sweep = radians(sweep_deg)
        iron_sweep = radians(sweep_deg + C.DD_POCKET_IRON_SWEEP_EXTRA_DEG)
        iron_inner = r + 0.0012
        iron = _annular_sector(
            "PT_PocketIron_" + key, center, iron_inner,
            iron_inner + C.DD_POCKET_IRON_W, C.DD_POCKET_IRON_H,
            C.DD_POCKET_IRON_CENTRE_Z, angle, iron_sweep, ENG,
            mats["blacksteel"], segments=44)
        iron["opening_radius"] = iron_inner
        iron["outside_capture_circle_m"] = iron_inner - r
        iron["top_below_rail_top_m"] = (
            C.RAIL_TOP_Z - C.BED_Z -
            (C.DD_POCKET_IRON_CENTRE_Z + C.DD_POCKET_IRON_H / 2.0))
        iron["mounted_by_two_ears"] = True
        iron.hide_render = False
        made.append(iron)

        welt_z = C.RAIL_TOP_Z - C.BED_Z - C.DD_POCKET_WELT_R - 0.0012
        major_radius = r + C.DD_POCKET_WELT_MAJOR_OFFSET
        welt = _torus_sector(
            "PT_PocketLeatherWelt_" + key, center, major_radius,
            C.DD_POCKET_WELT_R, welt_z, angle, sweep, VIS,
            mats.get("leather_interior", mats["leather"]), segments=48)
        welt["leather_wrapped_iron"] = True
        welt["clear_radius_m"] = major_radius - C.DD_POCKET_WELT_R
        welt["top_below_rail_top_m"] = (
            C.RAIL_TOP_Z - C.BED_Z -
            (welt_z + C.DD_POCKET_WELT_R))
        made.append(welt)

        skirt_top = welt_z
        skirt_bottom = cloth_top
        skirt_inner = r + 0.0014
        skirt = _annular_sector(
            "PT_PocketLeatherSkirt_" + key, center, skirt_inner,
            skirt_inner + C.DD_POCKET_SKIRT_T,
            skirt_top - skirt_bottom, (skirt_top + skirt_bottom) / 2.0,
            angle, sweep, VIS,
            mats.get("leather_interior", mats["leather"]), segments=44)
        skirt["directs_impacts_downward"] = True
        skirt["clear_radius_m"] = skirt_inner
        made.append(skirt)

        stitches = _stitched_arc(
            "PT_PocketStitches_" + key, center, major_radius,
            welt_z + C.DD_POCKET_WELT_R + C.DD_POCKET_STITCH_H / 2.0,
            angle, sweep, VIS, mats["leather"])
        stitches["nonstructural_welt_seam"] = True
        made.append(stitches)

        # Two lugs continue the casting under the cap ends.  Photo 2 is a
        # removable carom plug, so none of its plug body is copied; only the
        # physically ordinary recessed-fastener logic is retained here.
        for ear_index, side in enumerate((-1.0, 1.0)):
            endpoint_angle = angle + side * iron_sweep / 2.0
            radial = Vector((math.cos(endpoint_angle),
                             math.sin(endpoint_angle)))
            tangent = Vector((-math.sin(endpoint_angle),
                              math.cos(endpoint_angle)))
            if pocket["kind"] == "corner":
                sx = 1.0 if center.x > 0.0 else -1.0
                sy = 1.0 if center.y > 0.0 else -1.0
                # Corner castings bolt into two perpendicular rail caps. The
                # leather U can end on a curved tangent, but each hidden lug
                # continues along its actual board axis toward the playfield.
                continuation = (Vector((-sx, 0.0))
                                if abs(radial.x) > abs(radial.y)
                                else Vector((0.0, -sy)))
            else:
                continuation = tangent * side
            endpoint = center + radial * (
                iron_inner + C.DD_POCKET_IRON_W / 2.0)
            ear_center = endpoint + continuation * (
                C.DD_POCKET_MOUNT_EAR_L / 2.0 -
                C.DD_POCKET_MOUNT_EAR_OVERLAP)
            if pocket["kind"] == "side":
                # The ring-seat rout ends the cap wood one welt radius past
                # the tube, so a tangential lug at the U tip floats over the
                # seat void.  Reach the lug outward under the horn wood.
                ear_center = ear_center + radial * 0.006
            ear_angle = math.atan2(continuation.y, continuation.x)
            ear = L.box(
                "PT_PocketMountEar_%s_%d" % (key, ear_index),
                (C.DD_POCKET_MOUNT_EAR_L, C.DD_POCKET_MOUNT_EAR_W,
                 C.DD_POCKET_MOUNT_EAR_H),
                pf(ear_center.x, ear_center.y,
                   C.DD_POCKET_IRON_CENTRE_Z),
                ENG, mats["blacksteel"], rotation=(0.0, 0.0, ear_angle),
                bevel=0.001, bevel_segments=2)
            ear["rail_cap_mount"] = True
            ear["iron_overlap_m"] = C.DD_POCKET_MOUNT_EAR_OVERLAP
            ear["pocket_kind"] = pocket["kind"]
            ear.hide_render = True
            made.append(ear)
            bolt_center = ear_center + continuation * (
                C.DD_POCKET_MOUNT_EAR_L * 0.22)
            bolt = L.cylinder(
                "PT_PocketMountBolt_%s_%d" % (key, ear_index),
                C.DD_POCKET_RIVET_R, C.DD_POCKET_RIVET_H,
                pf(bolt_center.x, bolt_center.y,
                   C.DD_POCKET_IRON_CENTRE_Z +
                   C.DD_POCKET_MOUNT_EAR_H / 2.0),
                ENG, mats["blacksteel"], segments=20)
            bolt["recessed_mount_fastener"] = True
            bolt.hide_render = True
            made.append(bolt)

        # Shield-style leather basket. The manufactured wall tapers, remains
        # open at the top and has enough true frustum volume for six balls.
        depth = C.DD_BASKET_DEPTH
        mouth_r = basket_mouth_r
        base_r = mouth_r * C.DD_BASKET_TAPER
        top_z = throat_bottom + 0.004
        bottom_z = -depth + C.DD_LEATHER_T
        profile = [(mouth_r, top_z),
                   (mouth_r, top_z - C.DD_BASKET_STRAIGHT_MAX * 0.45),
                   (base_r, bottom_z + 0.014),
                   (base_r * 0.86, bottom_z)]
        verts, faces, seg = [], [], 48
        for index in range(seg):
            a = 2.0 * math.pi * index / seg
            for rr, zz in profile:
                verts.append((math.cos(a) * rr, math.sin(a) * rr, zz))
        count = len(profile)
        for index in range(seg):
            nxt = (index + 1) % seg
            for level in range(count - 1):
                faces.append((index * count + level,
                              nxt * count + level,
                              nxt * count + level + 1,
                              index * count + level + 1))
        basket = L.mesh_object(
            "PT_PocketBasket_" + key, verts, faces, VIS,
            mats.get("leather_basket", mats["leather"]), smooth=True)
        basket.location = pf(center.x, center.y, 0.0)
        solidify = basket.modifiers.new("thickness", "SOLIDIFY")
        solidify.thickness = C.DD_LEATHER_T
        basket["basket_depth"] = depth
        basket["mouth_clear_radius_m"] = mouth_r - C.DD_LEATHER_T
        basket["base_clear_radius_m"] = base_r - C.DD_LEATHER_T
        made.append(basket)

        # A leather-backed catch pad closes the shield basket below normal
        # sightlines; no green rubber disk is exposed through the throat.
        catch_pad = L.cylinder(
            "PT_PocketBasketBase_" + key, base_r * 0.84, 0.004,
            pf(center.x, center.y, bottom_z + 0.001), VIS,
            mats.get("leather_shadow",
                     mats.get("leather_interior", mats["leather"])),
            segments=48, smooth=False)
        catch_pad["quiet_replaceable_wear_part"] = True
        made.append(catch_pad)

        iron_bottom = (C.DD_POCKET_IRON_CENTRE_Z -
                       C.DD_POCKET_IRON_H / 2.0)
        strap_top = iron_bottom + C.DD_POCKET_STRAP_OVERLAP
        strap_bottom = top_z - C.DD_POCKET_STRAP_OVERLAP
        strap_height = strap_top - strap_bottom
        strap_radius = r + 0.0125
        for index, offset in enumerate((-0.90, 0.0, 0.90)):
            a = angle + offset
            strap = L.box(
                "PT_PocketLeatherStrap_%s_%d" % (key, index),
                (C.DD_POCKET_STRAP_W, C.DD_POCKET_STRAP_T,
                 strap_height),
                pf(center.x + math.cos(a) * strap_radius,
                   center.y + math.sin(a) * strap_radius,
                   (strap_top + strap_bottom) / 2.0),
                ENG, mats["leather"], rotation=(0, 0, a),
                bevel=0.001, bevel_segments=2)
            strap["iron_overlap_m"] = C.DD_POCKET_STRAP_OVERLAP
            strap["basket_overlap_m"] = C.DD_POCKET_STRAP_OVERLAP
            strap["vegetable_tanned_suspension_strap"] = True
            strap.hide_render = False
            made.append(strap)
            rivet_z = strap_top - 0.006
            radial = Vector((math.cos(a), math.sin(a)))
            rivet_center = center + radial * strap_radius
            rivet = L.cylinder_between(
                "PT_PocketStrapRivet_%s_%d" % (key, index),
                0.0018,
                pf(rivet_center.x - radial.x * 0.0035,
                   rivet_center.y - radial.y * 0.0035, rivet_z),
                pf(rivet_center.x + radial.x * 0.0035,
                   rivet_center.y + radial.y * 0.0035, rivet_z),
                ENG, mats["blacksteel"], segments=16)
            rivet["strap_fastener"] = True
            rivet.hide_render = False
            made.append(rivet)
    return made


def build_frame(mats):
    """
    Hidden structure: perimeter sill, four transverse sills placed under both
    slate seams, a central bolt-through beam, and the apron panels.
    Load path is floor -> leg -> sill -> liner -> slate (US3263996 logic).
    """
    made = []
    span = C.PLAY_L + 2 * C.RAIL_PLAN_W
    width = C.PLAY_W + 2 * C.RAIL_PLAN_W
    liner_bottom = C.BED_Z - C.SLATE_T - C.LINER_T - C.CLOTH_T
    sill_z = (C.BED_Z - C.SLATE_T - C.LINER_T -
              C.DD_SILL_H / 2.0 - C.CLOTH_T)

    for sx in (-1, 1):
        made.append(L.box("PT_Sill_Long_%s" % ("W" if sx < 0 else "E"),
                          (C.DD_SILL_W, span, C.DD_SILL_H),
                          (CX + sx * (width / 2.0 - C.DD_SILL_W / 2.0),
                           CY, sill_z), ENG, mats["walnut"]))
    end_sill_length = width - 2 * C.DD_SILL_W
    for sy in (-1, 1):
        made.append(L.box("PT_Sill_End_%s" % ("Foot" if sy < 0 else "Head"),
                          (end_sill_length, C.DD_SILL_W, C.DD_SILL_H),
                          (CX, CY + sy * (span / 2.0 - C.DD_SILL_W / 2.0),
                           sill_z), ENG, mats["walnut"]))
    # four transverse sills: two under the slate seams, two intermediate
    seam = span / 6.0
    cross_z = liner_bottom - C.DD_CROSS_SILL_H / 2.0
    cross_inner_span = width - 2 * C.DD_SILL_W
    cross_half = (cross_inner_span - C.DD_BEAM_W) / 2.0
    cross_offset = C.DD_BEAM_W / 2.0 + cross_half / 2.0
    for i, y in enumerate((-span / 3.0, -seam, seam, span / 3.0)):
        for sx, side in ((-1, "W"), (1, "E")):
            made.append(L.box(
                "PT_CrossSill_%d_%s" % (i, side),
                (cross_half, C.DD_CROSS_SILL_W, C.DD_CROSS_SILL_H),
                (CX + sx * cross_offset, CY + y, cross_z),
                ENG, mats["walnut"]))
    # central bolt-through beam
    beam_z = liner_bottom - C.DD_BEAM_H / 2.0
    made.append(L.box("PT_CentreBeam", (C.DD_BEAM_W, span - 2 * C.DD_SILL_W,
                                        C.DD_BEAM_H),
                      (CX, CY, beam_z), ENG, mats["walnut"]))

    # flat aprons with a routed reveal, flush to the rail outer edge
    ap_z = sill_z - C.DD_SILL_H / 2.0 + C.DD_APRON_H / 2.0
    ax = C.OUT_W / 2.0 - C.DD_APRON_T / 2.0
    ay = C.OUT_L / 2.0 - C.DD_APRON_T / 2.0
    # Long aprons remain continuous below, but their upper boards have the
    # real clearance notch required by the centre drop pocket. A full-height
    # uninterrupted panel was visible through the pocket from player height
    # and could not physically coexist with its basket and iron.
    long_length = C.OUT_L - 2 * C.DD_APRON_T
    relief_w = C.DD_SIDE_POCKET_APRON_RELIEF_W
    relief_d = C.DD_SIDE_POCKET_APRON_RELIEF_D
    lower_h = C.DD_APRON_H - relief_d
    upper_length = (long_length - relief_w) / 2.0
    apron_bottom = ap_z - C.DD_APRON_H / 2.0
    apron_top = ap_z + C.DD_APRON_H / 2.0
    for sx in (-1, 1):
        side = "W" if sx < 0 else "E"
        lower = L.box(
            "PT_Apron_%s_Lower" % side,
            (C.DD_APRON_T, long_length, lower_h),
            (CX + sx * ax, CY, apron_bottom + lower_h / 2.0),
            VIS, mats["walnut"], bevel=0.003)
        lower["side_pocket_relief_width_m"] = relief_w
        lower["side_pocket_relief_depth_m"] = relief_d
        made.append(lower)
        for sy, end in ((-1, "Foot"), (1, "Head")):
            upper = L.box(
                "PT_Apron_%s_Upper_%s" % (side, end),
                (C.DD_APRON_T, upper_length, relief_d),
                (CX + sx * ax,
                 CY + sy * (relief_w / 2.0 + upper_length / 2.0),
                 apron_top - relief_d / 2.0),
                VIS, mats["walnut"], bevel=0.003)
            upper["side_pocket_relief_width_m"] = relief_w
            upper["side_pocket_relief_depth_m"] = relief_d
            made.append(upper)
    for sy in (-1, 1):
        made.append(L.box("PT_Apron_%s" % ("Foot" if sy < 0 else "Head"),
                          (C.OUT_W, C.DD_APRON_T, C.DD_APRON_H),
                          (CX, CY + sy * ay, ap_z), VIS,
                          mats.get("walnut_cross", mats["walnut"]),
                          bevel=0.003))
    return made


def build_fasteners(mats):
    """Eighteen vertical rail studs matching the Metro six-rail assembly."""
    made = []
    z0 = C.BED_Z - C.SLATE_T - 0.010
    z1 = C.RAIL_TOP_Z - 0.004
    depth = z1 - z0
    z = (z0 + z1) / 2.0
    offset = C.SIGHT_OFFSET_FROM_NOSE
    positions = []
    for sx in (-1, 1):
        for i in range(1, 8):
            if i != 4:
                positions.append((sx * (HW + offset),
                                  -HL + C.PLAY_L * i / 8.0))
    for sy in (-1, 1):
        for i in (1, 2, 3):
            positions.append((-HW + C.PLAY_W * i / 4.0,
                              sy * (HL + offset)))
    for index, (x, y) in enumerate(positions, 1):
        stud = L.cylinder("PT_RailStud_%02d" % index, 0.0045, depth,
                          (CX + x, CY + y, z), ENG, mats["blacksteel"],
                          segments=20)
        stud["metro_rail_stud_index"] = index
        made.append(stud)
    return made


def build_physics_proxies(mats, data):
    """Hidden diagnostic geometry from the exact pooltool contact contract."""
    made = []
    L.clear_collection(PHYS)
    for row in G.linear_rows(data):
        a = pf(row["p1"][0], row["p1"][1], C.CUSHION_NOSE)
        b = pf(row["p2"][0], row["p2"][1], C.CUSHION_NOSE)
        ob = L.cylinder_between("PTX_Linear_" + row["id"], 0.0012, a, b,
                                PHYS, mats["facing"], segments=10)
        ob["feature_kind"] = row["kind"]
        ob["contract_id"] = row["id"]
        ob["debug_visual_only"] = True
        ob["solver_surface_is_centerline"] = True
        ob["display_radius_m"] = 0.0012
        ob.hide_render = True
        ob.display_type = "WIRE"
        made.append(ob)
    for arc in G.arc_rows(data, steps=20):
        points = [pf(x, y, C.CUSHION_NOSE) for x, y in arc["path"]]
        ob = L.curve_tube("PTX_Arc_" + arc["id"], points, 0.0012,
                          PHYS, mats["facing"], resolution=1)
        ob["contract_id"] = arc["id"]
        ob["debug_visual_only"] = True
        ob["solver_surface_is_centerline"] = True
        ob["display_radius_m"] = 0.0012
        ob.hide_render = True
        ob.display_type = "WIRE"
        made.append(ob)
    for pocket in G.pocket_rows(data):
        center = pocket["center"]
        # Pooltool 0.6.0 captures against this continuous 2D circle; the
        # pocket shelf/backdraft below is static construction geometry and is
        # intentionally not mislabeled as the gameplay solver trigger.
        solver = L.cylinder(
            "PTX_SolverPocket_" + pocket["name"], pocket["radius"],
            pocket["depth"],
            pf(center[0], center[1], -pocket["depth"] / 2.0),
            PHYS, mats["facing"], segments=48)
        solver["pocket_id"] = pocket["id"]
        solver["trigger_only"] = True
        solver["collision_role"] = "pooltool_capture_sensor_not_solid"
        solver["trigger_metric"] = "ball_center_xy"
        solver["capture_condition"] = \
            "ball_center_crosses_circular_radius"
        solver["capture_center_x_m"] = center[0]
        solver["capture_center_y_m"] = center[1]
        solver["capture_radius_m"] = pocket["radius"]
        solver["capture_depth_m"] = pocket["depth"]
        solver["debug_visual_only"] = True
        solver.hide_render = True
        solver.display_type = "WIRE"
        made.append(solver)

        shelf_target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                        else C.SIDE_SHELF)
        shelf = G.pocket_shelf_cut_details(data, pocket, shelf_target)
        ob = _prism_polygon(
            "PTX_ShelfDrop_" + pocket["name"], shelf["outline"],
            C.BED_Z - pocket["depth"], C.BED_Z, PHYS, mats["facing"])
        ob["pocket_id"] = pocket["id"]
        ob["trigger_only"] = False
        ob["static_construction_diagnostic"] = True
        ob["collision_role"] = "shelf_drop_not_solver_trigger"
        ob["not_used_by_pooltool_solver"] = True
        ob["shelf_gated"] = True
        ob["shelf_target_m"] = shelf_target
        ob["shelf_drop_x"] = shelf["drop_mid"][0]
        ob["shelf_drop_y"] = shelf["drop_mid"][1]
        ob["shelf_outward_x"] = shelf["outward"][0]
        ob["shelf_outward_y"] = shelf["outward"][1]
        ob["debug_visual_only"] = True
        ob.hide_render = True
        ob.display_type = "WIRE"
        made.append(ob)
    collection = L.get_collection(PHYS)
    collection.hide_render = True
    return made


def turned_leg_profile(height):
    """A restrained lower turning: shoulder, cove, taper, and foot ring."""
    top, mid = C.DD_LEG_TOP / 2.0, C.DD_LEG_MIN / 2.0
    return [
        (top, height), (top, height - 0.075),
        (top * 0.94, height - 0.085),
        (mid * 1.30, height - 0.155),          # cove
        (mid * 1.12, height - 0.30),
        (mid, height * 0.42),                  # slim waist
        (mid * 1.14, 0.105),
        (mid * 1.30, 0.070),                   # foot ring
        (mid * 1.16, 0.036),
        (mid * 1.24, 0.012),
        (mid * 1.24, 0.0),
    ]


def build_legs(mats):
    """Six square-headed turned legs on exposed pads and threaded stems."""
    made = []
    leg_h = (C.BED_Z - C.SLATE_T - C.LINER_T - C.DD_SILL_H -
             C.CLOTH_T)
    turned_h = leg_h - C.DD_LEVELER_PAD_H - C.DD_LEG_HEAD_H
    if turned_h <= 0.30:
        raise RuntimeError("leg stack leaves no credible turned section")
    prof = turned_leg_profile(turned_h)
    inset = C.DD_LEG_TOP / 2.0
    xs = C.OUT_W / 2.0 - inset
    ys = C.OUT_L / 2.0 - inset
    spots = [(-xs, -ys, "Corner_SW"), (xs, -ys, "Corner_SE"),
             (-xs, ys, "Corner_NW"), (xs, ys, "Corner_NE"),
             (-xs, 0.0, "Mid_West"), (xs, 0.0, "Mid_East")]
    for (x, y, tag) in spots:
        turned = L.lathe(
            "PT_LegTurned_" + tag, prof, VIS, mats["walnut"], segments=48,
            location=(CX + x, CY + y, C.DD_LEVELER_PAD_H))
        turned["load_path_role"] = "turned_leg"
        made.append(turned)
        head = L.box(
            "PT_LegHead_" + tag,
            (C.DD_LEG_TOP, C.DD_LEG_TOP, C.DD_LEG_HEAD_H),
            (CX + x, CY + y, leg_h - C.DD_LEG_HEAD_H / 2.0),
            VIS, mats["walnut"], bevel=0.004)
        head["load_path_role"] = "square_head_block"
        made.append(head)

        # The pad bears on finished floor. A narrower threaded stem overlaps
        # the pad by 2 mm and continues inside the wood; no steel is buried
        # below the floor and the table bed height remains unchanged.
        pad = L.cylinder(
            "PT_LevelerPad_" + tag, C.DD_LEG_MIN * 0.30,
            C.DD_LEVELER_PAD_H,
            (CX + x, CY + y, C.DD_LEVELER_PAD_H / 2.0),
            VIS, mats["blacksteel"], segments=32)
        pad["load_path_role"] = "floor_bearing_pad"
        made.append(pad)
        stem = L.cylinder(
            "PT_LevelerStem_" + tag, 0.009,
            C.DD_LEVELER_STEM_H,
            (CX + x, CY + y,
             C.DD_LEVELER_PAD_H - 0.002 +
             C.DD_LEVELER_STEM_H / 2.0),
            ENG, mats["blacksteel"], segments=20)
        stem["load_path_role"] = "threaded_stem"
        made.append(stem)
    return made


def build(mats):
    data = _contract()
    L.clear_collection(VIS)
    L.clear_collection(ENG)
    L.clear_collection(PHYS)

    root = bpy.data.objects.new("PT_TableRoot", None)
    L.link(root, VIS)
    root.location = (CX, CY, 0.0)
    for k, v in (("play_w", C.PLAY_W), ("play_l", C.PLAY_L),
                 ("out_w", C.OUT_W), ("out_l", C.OUT_L),
                 ("bed_z", C.BED_Z), ("rail_top_z", C.RAIL_TOP_Z),
                 ("slate_t", C.SLATE_T), ("ball_d", C.BALL_D),
                 ("cushion_nose", C.CUSHION_NOSE),
                 ("corner_mouth", C.CORNER_MOUTH),
                 ("side_mouth", C.SIDE_MOUTH)):
        root[k] = v
    metrics = G.pocket_metrics(data)
    root["geometry_contract_sha256"] = G.file_sha256()
    root["geometry_contract_file"] = os.path.relpath(G.DATA_PATH, C.ROOT)
    root["solver_corner_theoretical_sharp_mouth_m"] = \
        metrics["corner_SW"]["mouth_m"]
    root["solver_side_theoretical_sharp_mouth_m"] = \
        metrics["side_W"]["mouth_m"]
    root["corner_cut_angle_deg"] = metrics["corner_SW"]["cut_angles_deg"][0]
    root["side_cut_angle_deg"] = metrics["side_W"]["cut_angles_deg"][0]
    root["back_draft_deg"] = C.BACK_DRAFT

    slate = build_slate(mats)
    cloth = build_cloth(mats)
    cushion_parts = build_cushions_and_rails(mats, data)
    rail_caps = build_rail_caps(mats)
    build_cap_horns(mats, data)
    build_sights(mats)
    build_pockets(mats, data)
    frame = build_frame(mats)
    build_fasteners(mats)
    legs = build_legs(mats)
    build_physics_proxies(mats, data)

    # Rail openings begin at the cushion mouth; bed/slate openings begin only
    # after the WPA shelf. They are deliberately separate Boolean contracts.
    # An EXACT Boolean against a material-less cutter can drop target material
    # slots, so remember each target's material and restore it afterwards.
    cutters = [o for o in bpy.data.objects if o.name.startswith("CUT_")]
    rail_cutters = [o for o in cutters if o.get("cutter_role") in
                    {"rail_opening", "rail_outboard_clearance"}]
    bed_cutters = [o for o in cutters
                   if o.get("cutter_role") == "bed_drop"]
    cloth_cutters = [o for o in cutters
                     if o.get("cutter_role") == "cloth_drop"]
    engineering_cutters = [o for o in cutters if o.get("cutter_role") ==
                           "pocket_engineering_clearance"]
    if len(rail_cutters) != 12 or len(bed_cutters) != 6 or \
            len(cloth_cutters) != 6 or \
            len(engineering_cutters) != 6:
        raise RuntimeError(
            "expected twelve rail plus six cloth, bed, and clearance cutters")
    engineering_targets = [o for o in slate + frame
                           if o.name.startswith("PT_SlateLiner_") or
                           o.name.startswith("PT_Sill_") or
                           o.name.startswith("PT_Apron_")]
    targets = [cloth] + rail_caps + slate + engineering_targets
    targets = list(dict.fromkeys(targets))
    intended = {t.name: (t.data.materials[0] if t.data.materials else None)
                for t in targets}
    target_cutters = [(cap, rail_cutters) for cap in rail_caps]
    target_cutters.append((cloth, cloth_cutters))
    target_cutters.extend((target, bed_cutters) for target in slate)
    target_cutters.extend((target, engineering_cutters)
                          for target in engineering_targets)
    for target, assigned_cutters in target_cutters:
        for cut in assigned_cutters:
            if not L.boolean(target, cut):
                raise RuntimeError("pocket Boolean failed: %s <- %s" %
                                   (target.name, cut.name))
        # Blender's exact solver can leave coincident, zero-length edges where
        # sequential pocket cuts meet a manufactured board.  Weld only at a
        # sub-micron tolerance so the WPA shelf and mouth geometry stay fixed.
        L.clean_boolean_mesh(target, tolerance=1e-7)
    # The cutter contributes its own (empty) slot to the target, so rebuild
    # each slot list down to just the intended material.
    for target in targets:
        want = intended.get(target.name)
        if want is not None:
            target.data.materials.clear()
            target.data.materials.append(want)
            for poly in target.data.polygons:
                poly.material_index = 0
    # Several raw boxes/lathed legs use inward source winding even though
    # their evaluated surfaces shade acceptably. Export and future collision
    # meshes require closed, positive-volume solids, so orient this table's
    # structural lane explicitly without touching the locked environment.
    for structural in frame + legs:
        if structural.type == "MESH":
            L.orient_closed_mesh_outward(structural)
    # Retain one hidden engineering proof volume per pocket.  The validator
    # can therefore inspect the actual manifold, positive-volume cutter and
    # measured back-draft instead of trusting a builder constant after the
    # Boolean source has vanished.
    for cut in cutters:
        role = cut.get("cutter_role")
        prefix = ("PTX_PocketClearance_"
                  if role == "pocket_engineering_clearance" else
                  "PTX_PocketClothCut_" if role == "cloth_drop" else
                  "PTX_PocketDraft_")
        cut.name = cut.name.replace("CUT_", prefix, 1)
        cut["boolean_proof_volume"] = True
        cut.hide_render = True
        cut.display_type = "WIRE"

    # Ease each manufactured cap only after the six routed pocket cuts exist.
    # A small three-pass edge replaces the razor-sharp Boolean silhouette
    # without changing the WPA nose or mouth geometry below it.
    cap_edge = 0.0015
    for rail_cap in rail_caps:
        bevel = rail_cap.modifiers.new("PT_RailCap_EdgeEase", "BEVEL")
        bevel.width = cap_edge
        bevel.segments = 3
        bevel.limit_method = "ANGLE"
        bevel.angle_limit = radians(22.5)
        rail_cap["edge_ease_m"] = cap_edge

    n = len(L.get_collection(VIS).objects) + len(L.get_collection(ENG).objects)
    print("  [table] %d components (visible + engineering), contract %s" %
          (n, G.file_sha256()[:12]))
    return root


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
