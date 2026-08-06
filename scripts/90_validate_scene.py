"""
90_validate_scene.py — measure the built geometry and report the truth.

This measures actual evaluated geometry. It never re-states the constants it is
supposed to be checking, and it does not round a failure into a pass.
Exits nonzero if any REQUIRED check fails.
"""
import bpy
import bmesh
import json
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import pool_geometry_contract as G  # noqa: E402

MM = 0.001


def _world_bbox(objs):
    xs, ys, zs = [], [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objs:
        e = ob.evaluated_get(dg)
        me = e.to_mesh()
        for v in me.vertices:
            w = e.matrix_world @ v.co
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
        e.to_mesh_clear()
    if not xs:
        return None
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def check(results, name, measured, expected, tol, unit="m", required=True):
    ok = measured is not None and abs(measured - expected) <= tol
    results.append({
        "check": name, "measured": measured, "expected": expected,
        "tolerance": tol, "unit": unit, "required": required,
        "status": "PASS" if ok else "FAIL",
        "delta": None if measured is None else measured - expected,
    })
    return ok


def _top_visible_table_hit(x, y):
    """Return the highest render-visible table mesh under one plan point."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    origin_world = Vector((x, y, C.RAIL_TOP_Z + 0.15))
    direction_world = Vector((0.0, 0.0, -1.0))
    best = None
    for source in bpy.data.objects:
        if source.type != "MESH" or source.hide_render:
            continue
        if not source.name.startswith("PT_"):
            continue
        evaluated = source.evaluated_get(depsgraph)
        inverse = evaluated.matrix_world.inverted()
        origin = inverse @ origin_world
        direction = (inverse.to_3x3() @ direction_world).normalized()
        hit, location, _normal, _face = evaluated.ray_cast(origin, direction)
        if not hit:
            continue
        world = evaluated.matrix_world @ location
        if world.z > origin_world.z + 1e-6:
            continue
        if best is None or world.z > best[0]:
            best = (world.z, source.name)
    return best


def _visible_table_segment_hit(start_world, end_world):
    """Nearest render-visible table hit along a finite world-space segment."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    best = None
    for source in bpy.data.objects:
        if source.type != "MESH" or source.hide_render:
            continue
        if not source.name.startswith("PT_") or \
                source.name.startswith("PT_Ball_"):
            continue
        evaluated = source.evaluated_get(depsgraph)
        inverse = evaluated.matrix_world.inverted()
        start = inverse @ start_world
        end = inverse @ end_world
        vector = end - start
        distance_local = vector.length
        if distance_local <= 1e-12:
            continue
        hit, location, _normal, _face = evaluated.ray_cast(
            start, vector.normalized(), distance=distance_local)
        if not hit:
            continue
        world = evaluated.matrix_world @ location
        travelled = (world - start_world).length
        if best is None or travelled < best[0]:
            best = (travelled, source.name, tuple(world))
    return best


def _object_vertical_hit(source, x, y, z_top=None, z_bottom=None):
    """Return the first evaluated hit on one object along a vertical ray."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    top = C.RAIL_TOP_Z + 0.10 if z_top is None else z_top
    bottom = C.BED_Z - 0.10 if z_bottom is None else z_bottom
    start_world = Vector((x, y, top))
    end_world = Vector((x, y, bottom))
    inverse = evaluated.matrix_world.inverted()
    start = inverse @ start_world
    end = inverse @ end_world
    vector = end - start
    hit, location, _normal, _face = evaluated.ray_cast(
        start, vector.normalized(), distance=vector.length)
    return evaluated.matrix_world @ location if hit else None


def _evaluated_bvh(source):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
    bvh = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
    evaluated.to_mesh_clear()
    return bvh


def _bbox_overlaps(first, second, tolerance=0.0):
    return not (first[1] < second[0] - tolerance or
                second[1] < first[0] - tolerance or
                first[3] < second[2] - tolerance or
                second[3] < first[2] - tolerance or
                first[5] < second[4] - tolerance or
                second[5] < first[4] - tolerance)


def _mesh_manifold_positive(mesh):
    probe = bmesh.new()
    probe.from_mesh(mesh)
    manifold = bool(probe.edges) and all(edge.is_manifold
                                         for edge in probe.edges)
    volume = probe.calc_volume(signed=True) if probe.faces else 0.0
    probe.free()
    return manifold, volume


def _wall_semantic_open_edges(ob, mouth_start, mouth_end):
    """Return expected and actually absent top-ring edges for a pocket wall."""
    count = int(ob.get("ring_vertex_count", 0))
    if count < 3 or len(ob.data.vertices) != 2 * count:
        return set(), set(), "invalid ring topology"
    top = []
    for index in range(count):
        world = ob.matrix_world @ ob.data.vertices[index].co
        top.append((world.x - C.TABLE_CENTRE[0],
                    world.y - C.TABLE_CENTRE[1]))
    expected = set()
    for index, first in enumerate(top):
        second = top[(index + 1) % count]
        if (G.point_segment_distance(first, mouth_start, mouth_end) <= 2e-6
                and G.point_segment_distance(second, mouth_start,
                                             mouth_end) <= 2e-6):
            expected.add(index)
    occupied = set()
    for poly in ob.data.polygons:
        vertices = set(poly.vertices)
        for index in range(count):
            if index in vertices and (index + 1) % count in vertices:
                occupied.add(index)
    actual = set(range(count)) - occupied
    return expected, actual, None


def run():
    R = []
    objs = {o.name: o for o in bpy.data.objects}

    # ---------------------------------------------------- playing surface --
    noses = [o for n, o in objs.items() if n.startswith("PT_Cushion_")]
    bb = _world_bbox(noses)
    if bb:
        # nose lines are the innermost faces; bbox spans the outer sweep, so
        # measure between opposing cushion objects instead
        west = _world_bbox([o for n, o in objs.items()
                            if n.startswith("PT_Cushion_Long_W")])
        east = _world_bbox([o for n, o in objs.items()
                            if n.startswith("PT_Cushion_Long_E")])
        foot = _world_bbox([o for n, o in objs.items()
                            if n.startswith("PT_Cushion_End_Foot")])
        head = _world_bbox([o for n, o in objs.items()
                            if n.startswith("PT_Cushion_End_Head")])
        if west and east:
            check(R, "playing_surface_width", east[0] - west[1], C.PLAY_W,
                  0.5 * MM)
        if foot and head:
            check(R, "playing_surface_length", head[2] - foot[3], C.PLAY_L,
                  0.5 * MM)
        # The nose is the forward-most point of the rubber, not the top of it.
        # Measure the z of the vertices that actually sit on the nose line.
        nose_z = None
        for ob in [o for n, o in objs.items()
                   if n.startswith("PT_Cushion_Long_E")]:
            xs = [(ob.matrix_world @ v.co) for v in ob.data.vertices]
            fwd = min(v.x for v in xs)
            zz = [v.z for v in xs if abs(v.x - fwd) < 1e-6]
            if zz:
                nose_z = max(zz) if nose_z is None else max(nose_z, max(zz))
        if nose_z is not None:
            ok = (C.CUSHION_NOSE_MIN <= nose_z - C.BED_Z <= C.CUSHION_NOSE_MAX)
            R.append({"check": "cushion_nose_height_in_wpa_range",
                      "measured": nose_z - C.BED_Z,
                      "expected": C.CUSHION_NOSE,
                      "permitted": [C.CUSHION_NOSE_MIN, C.CUSHION_NOSE_MAX],
                      "unit": "m", "required": True,
                      "status": "PASS" if ok else "FAIL"})

    # ------------------------------------------ shared solver/render contract --
    contract = G.load()
    metrics = G.pocket_metrics(contract)
    root = objs.get("PT_TableRoot")
    contract_sha = G.file_sha256()
    root_sha = root.get("geometry_contract_sha256") if root else None
    R.append({"check": "table_uses_approved_geometry_contract",
              "measured": root_sha, "expected": contract_sha,
              "unit": "sha256", "required": True,
              "status": "PASS" if root_sha == contract_sha else "FAIL"})

    lines = G.linear_rows(contract)
    arcs = G.arc_rows(contract)
    features = {
        "main": sum(row["kind"] == "main" for row in lines),
        "jaw": sum(row["kind"] == "jaw" for row in lines),
        "arc": len(arcs), "pocket": len(G.pocket_rows(contract)),
    }
    expected_features = {"main": 6, "jaw": 12, "arc": 12, "pocket": 6}
    R.append({"check": "physics_geometry_feature_counts",
              "measured": features, "expected": expected_features,
              "unit": "count", "required": True,
              "status": "PASS" if features == expected_features else "FAIL"})

    corner_rows = [row for row in metrics.values()
                   if row["kind"] == "corner"]
    side_rows = [row for row in metrics.values() if row["kind"] == "side"]
    corner_mouth = sum(row["mouth_m"] for row in corner_rows) / len(corner_rows)
    side_mouth = sum(row["mouth_m"] for row in side_rows) / len(side_rows)
    check(R, "corner_evaluated_mouth_at_finished_nominal", corner_mouth,
          C.CORNER_MOUTH, 0.25 * MM)
    check(R, "side_evaluated_mouth_at_finished_nominal", side_mouth,
          C.SIDE_MOUTH, 0.25 * MM)
    corner_angle_error = max(abs(angle - C.CORNER_CUT_ANGLE)
                             for row in corner_rows
                             for angle in row["cut_angles_deg"])
    side_angle_error = max(abs(angle - C.SIDE_CUT_ANGLE)
                           for row in side_rows
                           for angle in row["cut_angles_deg"])
    check(R, "corner_jaw_cut_angle_error", corner_angle_error, 0.0, 0.01,
          unit="deg")
    check(R, "side_jaw_cut_angle_error", side_angle_error, 0.0, 0.01,
          unit="deg")

    main_cushions = [o for n, o in objs.items()
                     if n.startswith("PT_Cushion_Long_") or
                     n.startswith("PT_Cushion_End_")]
    widths = []
    for row in (item for item in lines if item["kind"] == "main"):
        ob = next((candidate for candidate in main_cushions
                   if candidate.get("main_contract_id") == row["id"]), None)
        if ob is None:
            continue
        p1, p2 = Vector(row["p1"]), Vector(row["p2"])
        midpoint = (p1 + p2) * 0.5
        tangent = (p2 - p1).normalized()
        normal = Vector(row["normal"]).normalized()
        projections = []
        for vertex in ob.data.vertices:
            world = ob.matrix_world @ vertex.co
            local_plan = Vector((world.x - C.TABLE_CENTRE[0],
                                 world.y - C.TABLE_CENTRE[1]))
            delta = local_plan - midpoint
            if abs(delta.dot(tangent)) <= 1e-6 and delta.length <= 0.07:
                projections.append(delta.dot(normal))
        if projections:
            widths.append(max(projections) - min(projections))
    measured_width = sum(widths) / len(widths) if widths else None
    check(R, "cloth_covered_cushion_width", measured_width,
          C.CUSHION_COVERED_W, 0.25 * MM)
    cushion_footprint_offenders = []
    for cushion in main_cushions:
        path_count = int(cushion.get("sweep_path_count", 0))
        profile_count = int(cushion.get("sweep_profile_count", 0))
        if path_count < 2 or profile_count != 5 or \
                len(cushion.data.vertices) != path_count * profile_count:
            cushion_footprint_offenders.append(cushion.name + " topology")
            continue
        front = []
        back = []
        for index in range(path_count):
            first = cushion.matrix_world @ cushion.data.vertices[
                index * profile_count + 1].co
            second = cushion.matrix_world @ cushion.data.vertices[
                index * profile_count + 2].co
            front.append((first.x, first.y))
            back.append((second.x, second.y))
        footprint = front + list(reversed(back))
        crossings = G._polygon_crossings(footprint)
        top_faces = [cushion.data.polygons[
            index * profile_count + 1] for index in range(path_count - 1)]
        if crossings or any(face.normal.z < 0.5 for face in top_faces):
            cushion_footprint_offenders.append({
                "object": cushion.name, "crossings": crossings,
                "inverted_top_faces": sum(face.normal.z < 0.5
                                           for face in top_faces)})
    R.append({"check": "cushion_top_footprints_nonfolding",
              "measured": len(main_cushions) -
              len(cushion_footprint_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": cushion_footprint_offenders,
              "status": "PASS" if len(main_cushions) == 6 and
              not cushion_footprint_offenders else "FAIL"})
    cushion_topology_offenders = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for cushion in main_cushions:
        evaluated = cushion.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        manifold, volume = _mesh_manifold_positive(mesh)
        evaluated.to_mesh_clear()
        if not manifold or volume <= 0.0:
            cushion_topology_offenders.append({
                "object": cushion.name, "manifold": manifold,
                "signed_volume_m3": volume,
            })
    R.append({"check": "evaluated_cushions_manifold_outward",
              "measured": len(main_cushions) -
              len(cushion_topology_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": cushion_topology_offenders,
              "status": "PASS" if len(main_cushions) == 6 and
              not cushion_topology_offenders else "FAIL"})
    cushion_bounds = _world_bbox(noses)
    check(R, "cushion_top_not_above_rail", cushion_bounds[5]
          if cushion_bounds else None, C.RAIL_TOP_Z, 0.25 * MM)

    side_gaps = []
    for side in ("W", "E"):
        south = objs.get("PT_Rail_Long_%s_S" % side)
        north = objs.get("PT_Rail_Long_%s_N" % side)
        if south and north:
            sb, nb = _world_bbox([south]), _world_bbox([north])
            side_gaps.append(nb[2] - sb[3])
    min_side_gap = min(side_gaps) if side_gaps else None
    R.append({"check": "main_rails_do_not_overlap_side_pockets",
              "measured": min_side_gap, "expected": ">=0",
              "unit": "m", "required": True,
              "status": "PASS" if min_side_gap is not None and
              min_side_gap >= -0.1 * MM else "FAIL"})

    # ------------------------------------------------------ exterior size --
    ext = [o for n, o in objs.items()
           if n.startswith("PT_Rail_") or n.startswith("PT_RailCap_") or
           n.startswith("PT_Apron_")]
    bb = _world_bbox(ext)
    if bb:
        check(R, "exterior_width", bb[1] - bb[0], C.OUT_W, 3.0 * MM)
        check(R, "exterior_length", bb[3] - bb[2], C.OUT_L, 3.0 * MM)
        check(R, "rail_top_z", bb[5], C.RAIL_TOP_Z, 1.0 * MM)

    # A centre drop pocket cannot coexist with an uninterrupted full-height
    # long apron. Each side uses a continuous lower board plus two upper
    # boards, leaving a measured U-relief for the basket and attachment iron.
    long_apron_names = [
        "PT_Apron_W_Lower", "PT_Apron_W_Upper_Foot",
        "PT_Apron_W_Upper_Head", "PT_Apron_E_Lower",
        "PT_Apron_E_Upper_Foot", "PT_Apron_E_Upper_Head",
    ]
    long_aprons = [objs.get(name) for name in long_apron_names]
    missing_long_aprons = [name for name, ob in zip(long_apron_names,
                                                    long_aprons) if not ob]
    R.append({"check": "side_pocket_apron_relief_piece_count",
              "measured": 6 - len(missing_long_aprons), "expected": 6,
              "unit": "count", "required": True,
              "offenders": missing_long_aprons,
              "status": "PASS" if not missing_long_aprons else "FAIL"})
    relief_property_offenders = []
    for apron in (ob for ob in long_aprons if ob):
        width = float(apron.get("side_pocket_relief_width_m", -1.0))
        depth = float(apron.get("side_pocket_relief_depth_m", -1.0))
        if abs(width - C.DD_SIDE_POCKET_APRON_RELIEF_W) > 0.1 * MM or \
                abs(depth - C.DD_SIDE_POCKET_APRON_RELIEF_D) > 0.1 * MM:
            relief_property_offenders.append(apron.name)
    R.append({"check": "side_pocket_apron_relief_metadata",
              "measured": 6 - len(relief_property_offenders),
              "expected": 6, "unit": "count", "required": True,
              "offenders": relief_property_offenders,
              "status": "PASS" if not missing_long_aprons and
              not relief_property_offenders else "FAIL"})
    relief_widths, relief_depths = [], []
    for side in ("W", "E"):
        lower = objs.get("PT_Apron_%s_Lower" % side)
        foot = objs.get("PT_Apron_%s_Upper_Foot" % side)
        head = objs.get("PT_Apron_%s_Upper_Head" % side)
        if lower and foot and head:
            lower_bounds = _world_bbox([lower])
            foot_bounds = _world_bbox([foot])
            head_bounds = _world_bbox([head])
            relief_widths.append(head_bounds[2] - foot_bounds[3])
            relief_depths.append(head_bounds[5] - lower_bounds[5])
    check(R, "side_pocket_apron_relief_width",
          min(relief_widths) if relief_widths else None,
          C.DD_SIDE_POCKET_APRON_RELIEF_W, 0.5 * MM)
    check(R, "side_pocket_apron_relief_depth",
          min(relief_depths) if relief_depths else None,
          C.DD_SIDE_POCKET_APRON_RELIEF_D, 0.5 * MM)

    cloth = objs.get("PT_Cloth_Bed")
    if cloth:
        bb = _world_bbox([cloth])
        check(R, "playing_surface_z", bb[5], C.BED_Z, 0.5 * MM)
    bed_material = (cloth.data.materials[0] if cloth and
                    cloth.data.materials else None)
    bed_finish_ok = bool(
        bed_material and
        bed_material.name == "MAT_Table_Cloth_BedWornWorsted" and
        bed_material.get("wear_character") ==
        "restrained_tonal_history_no_stains" and
        float(bed_material.get("solver_surface_displacement_m", -1.0)) == 0.0
    )
    R.append({"check": "bed_cloth_wear_is_visual_only",
              "measured": bed_material.name if bed_material else None,
              "expected": "MAT_Table_Cloth_BedWornWorsted",
              "required": True,
              "status": "PASS" if bed_finish_ok else "FAIL"})

    slates = [o for n, o in objs.items() if n.startswith("PT_Slate_")]
    if slates:
        bb = _world_bbox(slates)
        check(R, "slate_thickness", bb[5] - bb[4], C.SLATE_T, 1.0 * MM)
        R.append({"check": "slate_piece_count", "measured": len(slates),
                  "expected": 3, "status": "PASS" if len(slates) == 3
                  else "FAIL", "required": True, "unit": "count"})
        ordered = sorted((_world_bbox([ob]) for ob in slates),
                         key=lambda bounds: bounds[2])
        joint_gaps = [ordered[index + 1][2] - ordered[index][3]
                      for index in range(len(ordered) - 1)]
        worst_gap = max((abs(gap) for gap in joint_gaps), default=None)
        check(R, "slate_joints_have_no_modelled_air_gap", worst_gap,
              0.0, 0.05 * MM)

    liner = objs.get("PT_SlateLiner_Perimeter")
    cross_sills = [o for n, o in objs.items() if n.startswith("PT_CrossSill_")]
    liner_bounds = _world_bbox([liner]) if liner else None
    contact_error = None
    if liner_bounds and cross_sills:
        contact_error = max(abs(_world_bbox([ob])[5] - liner_bounds[4])
                            for ob in cross_sills)
    check(R, "cross_sills_contact_slate_liner", contact_error, 0.0,
          0.05 * MM)

    long_sills = [o for n, o in objs.items() if n.startswith("PT_Sill_Long_")]
    end_sills = [o for n, o in objs.items() if n.startswith("PT_Sill_End_")]
    centre_beams = [o for n, o in objs.items() if n == "PT_CentreBeam"]
    frame_counts = {"long_sills": len(long_sills),
                    "end_sills": len(end_sills),
                    "cross_sill_halves": len(cross_sills),
                    "centre_beams": len(centre_beams)}
    expected_frame_counts = {"long_sills": 2, "end_sills": 2,
                             "cross_sill_halves": 8, "centre_beams": 1}
    R.append({"check": "frame_member_counts",
              "measured": frame_counts, "expected": expected_frame_counts,
              "unit": "count", "required": True,
              "status": "PASS" if frame_counts == expected_frame_counts
              else "FAIL"})

    def bbox_overlap_volume(first, second):
        return (max(0.0, min(first[1], second[1]) - max(first[0], second[0])) *
                max(0.0, min(first[3], second[3]) - max(first[2], second[2])) *
                max(0.0, min(first[5], second[5]) - max(first[4], second[4])))

    frame_overlap_offenders = []
    for first in long_sills:
        for second in end_sills:
            overlap = bbox_overlap_volume(_world_bbox([first]),
                                          _world_bbox([second]))
            if overlap > 1e-10:
                frame_overlap_offenders.append(
                    "%s/%s=%.9g" % (first.name, second.name, overlap))
    if centre_beams:
        beam_bounds = _world_bbox(centre_beams)
        for cross in cross_sills:
            overlap = bbox_overlap_volume(_world_bbox([cross]), beam_bounds)
            if overlap > 1e-10:
                frame_overlap_offenders.append(
                    "%s/PT_CentreBeam=%.9g" % (cross.name, overlap))
    R.append({"check": "frame_members_meet_without_raw_box_overlap",
              "measured": len(frame_overlap_offenders), "expected": 0,
              "unit": "pair", "required": True,
              "offenders": frame_overlap_offenders,
              "status": "PASS" if not frame_overlap_offenders else "FAIL"})

    pads = [o for n, o in objs.items() if n.startswith("PT_LevelerPad_")]
    stems = [o for n, o in objs.items() if n.startswith("PT_LevelerStem_")]
    turnings = [o for n, o in objs.items() if n.startswith("PT_LegTurned_")]
    heads = [o for n, o in objs.items() if n.startswith("PT_LegHead_")]
    leg_stack_offenders = []
    suffixes = sorted(name.removeprefix("PT_LevelerPad_")
                      for name in (ob.name for ob in pads))
    for suffix in suffixes:
        pad = objs.get("PT_LevelerPad_" + suffix)
        stem = objs.get("PT_LevelerStem_" + suffix)
        turning = objs.get("PT_LegTurned_" + suffix)
        head = objs.get("PT_LegHead_" + suffix)
        if not all((pad, stem, turning, head)):
            leg_stack_offenders.append(suffix + " missing component")
            continue
        pb, sb = _world_bbox([pad]), _world_bbox([stem])
        tb, hb = _world_bbox([turning]), _world_bbox([head])
        sill_bottom = liner_bounds[4] - C.DD_SILL_H if liner_bounds else None
        if (abs(pb[4]) > 0.25 * MM or
                abs(pb[5] - C.DD_LEVELER_PAD_H) > 0.25 * MM or
                abs(sb[4] - (C.DD_LEVELER_PAD_H - 0.002)) > 0.25 * MM or
                abs(sb[5] - (C.DD_LEVELER_PAD_H - 0.002 +
                             C.DD_LEVELER_STEM_H)) > 0.25 * MM or
                abs(tb[4] - C.DD_LEVELER_PAD_H) > 0.25 * MM or
                abs(tb[5] - hb[4]) > 0.25 * MM or
                abs(hb[5] - sill_bottom) > 0.25 * MM or
                abs((hb[1] - hb[0]) - C.DD_LEG_TOP) > 0.25 * MM or
                abs((hb[3] - hb[2]) - C.DD_LEG_TOP) > 0.25 * MM):
            leg_stack_offenders.append(suffix)
    R.append({"check": "leveler_leg_sill_load_path_contacts",
              "measured": 6 - len(leg_stack_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": leg_stack_offenders,
              "status": "PASS" if len(pads) == len(stems) ==
              len(turnings) == len(heads) == 6 and
              not leg_stack_offenders else "FAIL"})

    # Z contact alone can hide a decorative leg that misses the structure in
    # plan. Sample the evaluated, pocket-cut sill meshes across every head's
    # top footprint and require a substantial bearing patch. Corner heads
    # must additionally bridge onto their adjacent end sill.
    bearing_samples = 11
    bearing_total = bearing_samples * bearing_samples
    sill_bottom = liner_bounds[4] - C.DD_SILL_H if liner_bounds else None
    sill_top = liner_bounds[4] if liner_bounds else None
    long_bvhs = [_evaluated_bvh(ob) for ob in long_sills]
    end_bvhs = [_evaluated_bvh(ob) for ob in end_sills]

    def projected_bearing_fraction(head, supports):
        if sill_bottom is None or sill_top is None or not supports:
            return 0.0
        bounds = _world_bbox([head])
        hits = 0
        origin_z = sill_bottom - 0.002
        distance = sill_top - sill_bottom + 0.004
        for ix in range(bearing_samples):
            x = bounds[0] + (bounds[1] - bounds[0]) * \
                ((ix + 0.5) / bearing_samples)
            for iy in range(bearing_samples):
                y = bounds[2] + (bounds[3] - bounds[2]) * \
                    ((iy + 0.5) / bearing_samples)
                origin = Vector((x, y, origin_z))
                if any(tree.ray_cast(origin, Vector((0.0, 0.0, 1.0)),
                                     distance)[0] is not None
                       for tree in supports):
                    hits += 1
        return hits / bearing_total

    long_bearing = {}
    end_bearing = {}
    bearing_offenders = []
    for head in heads:
        suffix = head.name.removeprefix("PT_LegHead_")
        long_fraction = projected_bearing_fraction(head, long_bvhs)
        long_bearing[suffix] = long_fraction
        if long_fraction < 0.45:
            bearing_offenders.append(
                "%s long=%.3f (<0.450)" % (suffix, long_fraction))
        if suffix.startswith("Corner_"):
            end_fraction = projected_bearing_fraction(head, end_bvhs)
            end_bearing[suffix] = end_fraction
            if end_fraction < 0.08:
                bearing_offenders.append(
                    "%s end=%.3f (<0.080)" % (suffix, end_fraction))
    R.append({"check": "leg_heads_have_structural_plan_bearing",
              "measured": {"long_sill_fraction": long_bearing,
                           "corner_end_sill_fraction": end_bearing},
              "expected": {"long_sill_min": 0.45,
                           "corner_end_sill_min": 0.08},
              "unit": "fraction", "required": True,
              "offenders": bearing_offenders,
              "status": "PASS" if len(heads) == 6 and
              len(end_bearing) == 4 and not bearing_offenders else "FAIL"})

    structural_orientation = cross_sills + centre_beams + heads + turnings
    orientation_offenders = []
    for source in structural_orientation:
        evaluated = source.evaluated_get(
            bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        manifold, volume = _mesh_manifold_positive(mesh)
        evaluated.to_mesh_clear()
        if not manifold or volume <= 0.0 or \
                not source.get("closed_mesh_outward", False):
            orientation_offenders.append({
                "object": source.name, "manifold": manifold,
                "signed_volume_m3": volume,
                "orientation_marked": bool(source.get(
                    "closed_mesh_outward", False)),
            })
    R.append({"check": "frame_and_leg_solids_manifold_outward",
              "measured": len(structural_orientation) -
              len(orientation_offenders), "expected": 21,
              "unit": "count", "required": True,
              "offenders": orientation_offenders,
              "status": "PASS" if len(structural_orientation) == 21 and
              not orientation_offenders else "FAIL"})

    studs = [o for n, o in objs.items() if n.startswith("PT_RailStud_")]
    R.append({"check": "metro_rail_stud_count", "measured": len(studs),
              "expected": 18, "unit": "count", "required": True,
              "status": "PASS" if len(studs) == 18 else "FAIL"})
    sights = [o for n, o in objs.items() if n.startswith("PT_Sight_")]
    sight_offenders = [o.name for o in sights
                       if abs(_world_bbox([o])[5] - C.RAIL_TOP_Z) >
                       0.05 * MM]
    R.append({"check": "rail_sights_are_flush_inlays",
              "measured": len(sights) - len(sight_offenders),
              "expected": C.SIGHT_COUNT, "unit": "count",
              "required": True, "offenders": sight_offenders,
              "status": "PASS" if len(sights) == C.SIGHT_COUNT and
              not sight_offenders else "FAIL"})

    # -------------------------------------------------------------- balls --
    balls = [o for n, o in objs.items()
             if n.startswith("PT_Ball_") and not n.endswith("_Band")]
    R.append({"check": "ball_count", "measured": len(balls), "expected": 16,
              "status": "PASS" if len(balls) == 16 else "FAIL",
              "required": True, "unit": "count"})
    bad_d, bad_scale = [], []
    for ob in balls:
        d = ob.dimensions
        for axis in (d.x, d.y, d.z):
            if abs(axis - C.BALL_D) > 0.1 * MM:
                bad_d.append(ob.name)
                break
        if any(abs(s - 1.0) > 1e-6 for s in ob.scale):
            bad_scale.append(ob.name)
    R.append({"check": "ball_diameter_within_0.1mm",
              "measured": len(balls) - len(bad_d), "expected": len(balls),
              "status": "PASS" if not bad_d else "FAIL", "required": True,
              "offenders": bad_d[:8], "unit": "count"})
    R.append({"check": "ball_uniform_scale",
              "measured": len(balls) - len(bad_scale), "expected": len(balls),
              "status": "PASS" if not bad_scale else "FAIL", "required": True,
              "offenders": bad_scale[:8], "unit": "count"})

    # --------------------------------------------------------------- rack --
    apex = objs.get("PT_Ball_01")
    if apex:
        fx = C.TABLE_CENTRE[0]
        fy = C.TABLE_CENTRE[1] + C.FOOT_SPOT_Y
        d = math.hypot(apex.location.x - fx, apex.location.y - fy)
        check(R, "rack_apex_over_foot_spot", d, 0.0, 0.5 * MM)

    obj_balls = [o for o in balls if o.get("ball_number", 0) not in (0,)]
    worst = None
    for i, a in enumerate(obj_balls):
        for b in obj_balls[i + 1:]:
            gap = math.hypot(a.location.x - b.location.x,
                             a.location.y - b.location.y)
            worst = gap if worst is None else min(worst, gap)
    if worst is not None:
        ok = worst >= C.BALL_D - 0.1 * MM
        R.append({"check": "min_rack_center_spacing", "measured": worst,
                  "expected": C.BALL_D, "tolerance": 0.1 * MM, "unit": "m",
                  "required": True, "status": "PASS" if ok else "FAIL"})

    # ----------------------------------------- pocket construction assembly --
    blocked_capture_points = []
    for pocket in G.pocket_rows(contract):
        target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                  else C.SIDE_SHELF)
        shelf = G.pocket_shelf_cut_details(contract, pocket, target)
        drop = Vector(shelf["drop_mid"])
        outward = Vector(shelf["outward"])
        probe = drop + outward * 0.5 * MM
        x = C.TABLE_CENTRE[0] + probe.x
        y = C.TABLE_CENTRE[1] + probe.y
        hit = _top_visible_table_hit(x, y)
        # A real capture opening must ray below the slate/cloth plane.  The
        # basket floor is intentionally allowed; a cloth, slate or rail hit at
        # bed height means a Boolean silently left the pocket capped.
        if hit is not None and hit[0] >= C.BED_Z - 0.005:
            blocked_capture_points.append({
                "pocket": pocket["name"],
                "object": hit[1],
                "z_m": hit[0],
            })
    R.append({"check": "pocket_capture_openings_ray_below_bed",
              "measured": 6 - len(blocked_capture_points), "expected": 6,
              "unit": "count", "required": True,
              "offenders": blocked_capture_points,
              "status": "PASS" if not blocked_capture_points else "FAIL"})

    # Recover each shelf from the evaluated cloth mesh. Metadata and the
    # Blender-free clip are insufficient proof if a Boolean moves the drop.
    measured_shelves = []
    shelf_offenders = []
    if cloth is not None:
        for pocket in G.pocket_rows(contract):
            target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                      else C.SIDE_SHELF)
            shelf = G.pocket_shelf_cut_details(contract, pocket, target)
            mouth = Vector(shelf["mouth_mid"])
            outward = Vector(shelf["outward"])

            def supported(distance):
                point = mouth + outward * distance
                hit = _object_vertical_hit(
                    cloth, C.TABLE_CENTRE[0] + point.x,
                    C.TABLE_CENTRE[1] + point.y,
                    C.BED_Z + 0.010, C.BED_Z - C.CLOTH_T - 0.010)
                return hit is not None and abs(hit.z - C.BED_Z) <= 0.1 * MM

            low = max(0.1 * MM, target - 0.010)
            high = target + 0.010
            if not supported(low) or supported(high):
                shelf_offenders.append({
                    "pocket": pocket["name"], "target_m": target,
                    "supported_before": supported(low),
                    "open_after": not supported(high),
                })
                continue
            for _iteration in range(28):
                middle = (low + high) / 2.0
                if supported(middle):
                    low = middle
                else:
                    high = middle
            measured = (low + high) / 2.0
            measured_shelves.append({"pocket": pocket["name"],
                                     "measured_m": measured,
                                     "target_m": target})
            if abs(measured - target) > 0.5 * MM:
                shelf_offenders.append(measured_shelves[-1])
    R.append({"check": "pocket_shelves_measured_from_cloth_mesh",
              "measured": measured_shelves, "expected": {
                  "corner_m": C.CORNER_SHELF,
                  "side_m": C.SIDE_SHELF},
              "tolerance": 0.5 * MM, "unit": "m", "required": True,
              "offenders": shelf_offenders,
              "status": "PASS" if len(measured_shelves) == 6 and
              not shelf_offenders else "FAIL"})

    # The revised assembly vocabulary mirrors the actual manufactured stack:
    # routed cloth liner -> leather throat -> rail-top iron/welt/skirt ->
    # suspended basket/base.  Keep these prefixes exact so retired collar,
    # top-lip and catch-pad parts cannot silently satisfy a count.
    baskets = [o for n, o in objs.items()
               if n.startswith("PT_PocketBasket_")]
    basket_bases = [o for n, o in objs.items()
                    if n.startswith("PT_PocketBasketBase_")]
    irons = [o for n, o in objs.items() if n.startswith("PT_PocketIron_")]
    welts = [o for n, o in objs.items()
             if n.startswith("PT_PocketLeatherWelt_")]
    skirts = [o for n, o in objs.items()
              if n.startswith("PT_PocketLeatherSkirt_")]
    stitches = [o for n, o in objs.items()
                if n.startswith("PT_PocketStitches_")]
    mount_ears = [o for n, o in objs.items()
                  if n.startswith("PT_PocketMountEar_")]
    mount_bolts = [o for n, o in objs.items()
                   if n.startswith("PT_PocketMountBolt_")]
    straps = [o for n, o in objs.items()
              if n.startswith("PT_PocketLeatherStrap_")]
    strap_rivets = [o for n, o in objs.items()
                    if n.startswith("PT_PocketStrapRivet_")]
    facings = [o for n, o in objs.items()
               if n.startswith("PT_PocketFacing_")]
    exposed_facing_cores = [o.name for o in facings if not o.hide_render]
    featherstrips = [o for n, o in objs.items()
                     if n.startswith("PT_Featherstrip_")]
    exposed_featherstrips = [o.name for o in featherstrips
                             if not o.hide_render]
    pocket_liners = [o for n, o in objs.items()
                     if n.startswith("PT_PocketLiner_")]
    throats = [o for n, o in objs.items()
               if n.startswith("PT_PocketThroat_")]
    rail_caps = [o for n, o in objs.items()
                 if n.startswith("PT_RailCap_")]
    # Cap horns are finished rail-top wood continuing the boards along the
    # jaw cuts; the iron mount ears legitimately land on them.
    cap_horns = [o for n, o in objs.items()
                 if n.startswith("PT_CapHorn_")]

    component_counts = {
        "facings": len(facings),
        "liners": len(pocket_liners),
        "throats": len(throats),
        "irons": len(irons),
        "leather_welts": len(welts),
        "leather_skirts": len(skirts),
        "stitch_runs": len(stitches),
        "mount_ears": len(mount_ears),
        "mount_bolts": len(mount_bolts),
        "leather_straps": len(straps),
        "strap_rivets": len(strap_rivets),
        "baskets": len(baskets),
        "basket_bases": len(basket_bases),
        "serviceable_rail_caps": len(rail_caps),
        "cap_horns": len(cap_horns),
    }
    expected_counts = {
        "facings": 12,
        "liners": 6,
        "throats": 6,
        "irons": 6,
        "leather_welts": 6,
        "leather_skirts": 6,
        "stitch_runs": 6,
        "mount_ears": 12,
        "mount_bolts": 12,
        "leather_straps": 18,
        "strap_rivets": 18,
        "baskets": 6,
        "basket_bases": 6,
        "serviceable_rail_caps": 6,
        "cap_horns": 12,
    }
    R.append({"check": "pocket_construction_component_counts",
              "measured": component_counts, "expected": expected_counts,
              "unit": "count", "required": True,
              "status": "PASS" if component_counts == expected_counts
              else "FAIL"})

    retired_prefixes = (
        "PT_PocketLeatherRim_", "PT_PocketLeatherTopLip_",
        "PT_PocketLeatherLip_", "PT_PocketCatchPad_",
        "PT_PocketLeather_", "PT_PocketClothLiner_",
        "PT_PocketLeatherThroat_", "PT_PocketStrap_",
    )
    retired_parts = [name for name in objs
                     if name.startswith(retired_prefixes)]
    R.append({"check": "retired_pocket_component_vocabulary_absent",
              "measured": len(retired_parts), "expected": 0,
              "unit": "count", "required": True,
              "offenders": retired_parts,
              "status": "PASS" if not retired_parts else "FAIL"})

    shallow, capacity_fail = [], []
    for ob in baskets:
        bb = _world_bbox([ob])
        if not bb:
            continue
        depth = C.BED_Z - bb[4]
        if not (C.DD_BASKET_DEPTH_MIN <= depth <= C.DD_BASKET_DEPTH_MAX):
            shallow.append("%s=%.4f" % (ob.name, depth))
        # Conservative true frustum volume from the modelled clear radii,
        # rather than the old bounding-cylinder estimate.
        mouth = float(ob.get("mouth_clear_radius_m", 0.0))
        base = float(ob.get("base_clear_radius_m", 0.0))
        have = math.pi * depth * (mouth * mouth + mouth * base +
                                  base * base) / 3.0
        balls_volume = 6.0 * (4.0 / 3.0) * math.pi * (C.BALL_R ** 3)
        usable = have * 0.55
        if mouth <= C.BALL_R or base <= C.BALL_R or usable < balls_volume:
            ratio = usable / balls_volume if balls_volume else 0.0
            capacity_fail.append("%s=%.2fx" % (ob.name, ratio))
    R.append({"check": "basket_depth_in_range", "measured": len(baskets) -
              len(shallow), "expected": len(baskets), "unit": "count",
              "permitted": [C.DD_BASKET_DEPTH_MIN, C.DD_BASKET_DEPTH_MAX],
              "required": True, "offenders": shallow[:6],
              "status": "PASS" if len(baskets) == 6 and not shallow
              else "FAIL"})
    R.append({"check": "basket_admits_six_balls", "measured": len(baskets) -
              len(capacity_fail), "expected": len(baskets), "unit": "count",
              "required": True, "offenders": capacity_fail[:6],
              "status": "PASS" if len(baskets) == 6 and not capacity_fail
              else "FAIL"})

    wrong_liner_materials = [
        o.name for o in pocket_liners
        if not o.data.materials or
        o.data.materials[0].name != "MAT_Table_Cloth_PocketLiner"
    ]
    R.append({"check": "pocket_cloth_liner_material_assignment",
              "measured": len(pocket_liners) - len(wrong_liner_materials),
              "expected": 6, "unit": "count", "required": True,
              "offenders": wrong_liner_materials,
              "status": "PASS" if len(pocket_liners) == 6 and
              not wrong_liner_materials else "FAIL"})

    unpaired_capture_liners = [
        o.name for o in pocket_liners
        if int(o.get("capture_arc_radial_pair_count", 0)) < 12
    ]
    R.append({"check": "pocket_cloth_liner_capture_arc_is_smooth_draft",
              "measured": len(pocket_liners) -
              len(unpaired_capture_liners),
              "expected": 6, "unit": "count", "required": True,
              "offenders": unpaired_capture_liners,
              "status": "PASS" if len(pocket_liners) == 6 and
              not unpaired_capture_liners else "FAIL"})

    # Both drop walls close around the actual shelf edge.  The separate
    # rail-top U-shaped skirt remains open toward the playfield and is checked
    # below against its manufactured sweep, not against this closed drop loop.
    semantic_wall_offenders = []
    for pocket in G.pocket_rows(contract):
        target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                  else C.SIDE_SHELF)
        shelf = G.pocket_shelf_cut_details(contract, pocket, target)
        shelf_start = shelf["outline"][shelf["shelf_edge"]]
        shelf_end = shelf["outline"][
            (shelf["shelf_edge"] + 1) % len(shelf["outline"])]
        for prefix in ("PT_PocketLiner_", "PT_PocketThroat_"):
            ob = objs.get(prefix + pocket["name"])
            if ob is None:
                semantic_wall_offenders.append(prefix + pocket["name"] +
                                                " missing")
                continue
            _geometric, actual_open, error = _wall_semantic_open_edges(
                ob, shelf_start, shelf_end)
            recorded = {int(value) for value in
                        str(ob.get("open_edge_indices", "")).split(",")
                        if value}
            if (error or actual_open or recorded or
                    int(ob.get("open_edge_count", -1)) != 0 or
                    not ob.get("semantic_shelf_closed", False)):
                semantic_wall_offenders.append({
                    "object": ob.name,
                    "error": error,
                    "expected_open": [],
                    "actual_open": sorted(actual_open),
                    "recorded_open": sorted(recorded),
                })
    R.append({"check": "pocket_drop_liner_and_throat_topology",
              "measured": 12 - len(semantic_wall_offenders),
              "expected": 12, "unit": "count", "required": True,
              "offenders": semantic_wall_offenders[:6],
              "status": "PASS" if not semantic_wall_offenders else "FAIL"})

    # A vertical capture ray cannot see a retained vertical chord. Probe the
    # actual ball-centre corridor from the playfield through each mouth.
    blocked_mouth_corridors = []
    for pocket in G.pocket_rows(contract):
        outline, _centroid, mouth_edge = G.pocket_outline_details(
            contract, pocket)
        first = Vector(outline[mouth_edge])
        second = Vector(outline[(mouth_edge + 1) % len(outline)])
        midpoint = (first + second) * 0.5
        capture = Vector(pocket["center"])
        outward = (capture - midpoint).normalized()
        across = Vector((-outward.y, outward.x))
        for offset in (-0.35 * C.BALL_R, 0.0, 0.35 * C.BALL_R):
            start_local = midpoint - outward * C.BALL_D + across * offset
            end_local = capture + across * offset
            start = Vector((C.TABLE_CENTRE[0] + start_local.x,
                            C.TABLE_CENTRE[1] + start_local.y,
                            C.BED_Z + C.BALL_R))
            end = Vector((C.TABLE_CENTRE[0] + end_local.x,
                          C.TABLE_CENTRE[1] + end_local.y,
                          C.BED_Z + C.BALL_R))
            hit = _visible_table_segment_hit(start, end)
            if hit is not None:
                blocked_mouth_corridors.append({
                    "pocket": pocket["name"], "offset_m": offset,
                    "object": hit[1], "hit": hit[2],
                })
    R.append({"check": "ball_centre_corridors_clear_through_mouths",
              "measured": 18 - len(blocked_mouth_corridors),
              "expected": 18, "unit": "ray", "required": True,
              "offenders": blocked_mouth_corridors[:8],
              "status": "PASS" if not blocked_mouth_corridors else "FAIL"})

    # Retained hidden Boolean proof volumes make the actual cutter topology
    # and drafted lower loop independently measurable after construction.
    draft_proofs = [o for n, o in objs.items()
                    if n.startswith("PTX_PocketDraft_")]
    draft_topology_offenders = []
    draft_buffer_offenders = []
    worst_draft_error = 0.0
    role_counts = {}
    for ob in draft_proofs:
        role = str(ob.get("cutter_role", ""))
        role_counts[role] = role_counts.get(role, 0) + 1
        count = int(ob.get("matched_ring_vertices", 0))
        manifold, volume = _mesh_manifold_positive(ob.data)
        if count < 3 or len(ob.data.vertices) != 3 * count or \
                not manifold or volume <= 0.0:
            draft_topology_offenders.append({
                "object": ob.name, "ring_vertices": count,
                "mesh_vertices": len(ob.data.vertices),
                "manifold": manifold, "signed_volume_m3": volume,
            })
            continue
        top_ring = []
        bed_ring = []
        bottom_ring = []
        for index in range(count):
            top = ob.matrix_world @ ob.data.vertices[index].co
            bed = ob.matrix_world @ ob.data.vertices[count + index].co
            bottom = ob.matrix_world @ ob.data.vertices[2 * count + index].co
            top_ring.append((top.x - C.TABLE_CENTRE[0],
                             top.y - C.TABLE_CENTRE[1]))
            bed_ring.append((bed.x - C.TABLE_CENTRE[0],
                             bed.y - C.TABLE_CENTRE[1]))
            bottom_ring.append((bottom.x - C.TABLE_CENTRE[0],
                                bottom.y - C.TABLE_CENTRE[1]))
        vertical_through_cloth = (
            all(G.polygon_boundary_distance(point, bed_ring) <= 2e-6
                for point in top_ring) and
            all(G.polygon_boundary_distance(point, top_ring) <= 2e-6
                for point in bed_ring))
        simple = not G._polygon_crossings(bottom_ring)
        contains = all(G._point_in_polygon(point, bottom_ring)
                       for point in bed_ring)
        height = float(ob.get("draft_height_m", 0.0))
        if height <= 0.0:
            angles = []
        else:
            angles = [math.degrees(math.atan(
                G.polygon_boundary_distance(point, bed_ring) / height))
                for point in bottom_ring]
        error = max((abs(angle - C.BACK_DRAFT) for angle in angles),
                    default=999.0)
        worst_draft_error = max(worst_draft_error, error)
        if (not vertical_through_cloth or not simple or not contains or
                error > 0.05):
            draft_buffer_offenders.append({
                "object": ob.name,
                "vertical_through_cloth": vertical_through_cloth,
                "simple": simple, "contains_source": contains,
                "angle_range_deg": [min(angles, default=None),
                                    max(angles, default=None)],
            })
    R.append({"check": "pocket_draft_proofs_manifold_positive",
              "measured": len(draft_proofs) - len(draft_topology_offenders),
              "expected": 18, "unit": "count", "required": True,
              "offenders": draft_topology_offenders,
              "status": "PASS" if len(draft_proofs) == 18 and
              not draft_topology_offenders else "FAIL"})
    expected_roles = {"rail_opening": 6,
                      "rail_outboard_clearance": 6,
                      "bed_drop": 6}
    R.append({"check": "pocket_draft_proof_role_counts",
              "measured": role_counts, "expected": expected_roles,
              "unit": "count", "required": True,
              "status": "PASS" if role_counts == expected_roles else
              "FAIL"})
    R.append({"check": "pocket_backdraft_is_uniform_buffer",
              "measured": worst_draft_error, "expected": 0.0,
              "tolerance": 0.05, "unit": "deg", "required": True,
              "offenders": draft_buffer_offenders,
              "status": "PASS" if not draft_buffer_offenders and
              worst_draft_error <= 0.05 else "FAIL"})

    cloth_cut_proofs = [o for n, o in objs.items()
                        if n.startswith("PTX_PocketClothCut_")]
    clearance_proofs = [o for n, o in objs.items()
                        if n.startswith("PTX_PocketClearance_")]
    auxiliary_proof_offenders = []
    for ob in cloth_cut_proofs + clearance_proofs:
        manifold, volume = _mesh_manifold_positive(ob.data)
        if not manifold or volume <= 0.0:
            auxiliary_proof_offenders.append({
                "object": ob.name, "manifold": manifold,
                "signed_volume_m3": volume})
    R.append({"check": "pocket_auxiliary_cutters_manifold_positive",
              "measured": len(cloth_cut_proofs) + len(clearance_proofs) -
              len(auxiliary_proof_offenders), "expected": 12,
              "unit": "count", "required": True,
              "offenders": auxiliary_proof_offenders,
              "status": "PASS" if len(cloth_cut_proofs) == 6 and
              len(clearance_proofs) == 6 and
              not auxiliary_proof_offenders else "FAIL"})

    boolean_targets = [objs.get("PT_Cloth_Bed")] + rail_caps
    boolean_targets.extend(o for n, o in objs.items()
                           if n.startswith("PT_Slate_"))
    boolean_targets.append(objs.get("PT_SlateLiner_Perimeter"))
    boolean_targets = [ob for ob in boolean_targets if ob is not None]
    boolean_target_offenders = []
    for ob in (item for item in boolean_targets if item is not None):
        manifold, volume = _mesh_manifold_positive(ob.data)
        if not manifold or volume <= 0.0:
            boolean_target_offenders.append({
                "object": ob.name, "manifold": manifold,
                "signed_volume_m3": volume,
            })
    R.append({"check": "pocket_boolean_targets_manifold_positive",
              "measured": len(boolean_targets) -
              len(boolean_target_offenders), "expected": 11,
              "unit": "count", "required": True,
              "offenders": boolean_target_offenders,
              "status": "PASS" if len(boolean_targets) == 11 and
              not boolean_target_offenders else "FAIL"})

    base_clearances = []
    base_radii = []
    for ob in basket_bases:
        bb = _world_bbox([ob])
        if bb:
            base_clearances.append(C.BED_Z - bb[5])
            base_radii.append(min(bb[1] - bb[0], bb[3] - bb[2]) / 2.0)
    minimum_base_clearance = min(base_clearances, default=0.0)
    minimum_base_radius = min(base_radii, default=0.0)
    R.append({"check": "pocket_basket_bases_below_ball_path",
              "measured": minimum_base_clearance,
              "expected": ">=%.6f" % (1.5 * C.BALL_D), "unit": "m",
              "required": True,
              "status": "PASS" if len(base_clearances) == 6 and
              minimum_base_clearance >= 1.5 * C.BALL_D else "FAIL"})
    R.append({"check": "pocket_basket_bases_admit_ball",
              "measured": minimum_base_radius,
              "expected": ">%.6f" % C.BALL_R, "unit": "m",
              "required": True,
              "status": "PASS" if len(base_radii) == 6 and
              minimum_base_radius > C.BALL_R else "FAIL"})

    cap_offenders = []
    grain_counts = {"world_x": 0, "world_y": 0}
    for cap in rail_caps:
        bounds = _world_bbox([cap])
        bevels = [modifier for modifier in cap.modifiers
                  if modifier.name == "PT_RailCap_EdgeEase" and
                  modifier.type == "BEVEL"]
        grain = str(cap.get("grain_axis", ""))
        if grain in grain_counts:
            grain_counts[grain] += 1
        if (not bounds or
                abs((bounds[5] - bounds[4]) - C.DD_RAIL_CAP_T) > 0.1 * MM or
                abs(bounds[5] - C.RAIL_TOP_Z) > 0.1 * MM or
                abs(float(cap.get("edge_ease_m", 0.0)) - 0.0015) >
                0.1 * MM or len(bevels) != 1 or
                abs(bevels[0].width - 0.0015) > 0.1 * MM or
                bevels[0].segments != 3 or grain not in grain_counts):
            cap_offenders.append(cap.name)
    R.append({"check": "six_rail_caps_have_craft_geometry",
              "measured": len(rail_caps) - len(cap_offenders),
              "expected": 6, "unit": "count", "required": True,
              "offenders": cap_offenders,
              "status": "PASS" if len(rail_caps) == 6 and
              not cap_offenders else "FAIL"})
    R.append({"check": "rail_cap_grain_follows_board_axis",
              "measured": grain_counts,
              "expected": {"world_x": 2, "world_y": 4},
              "unit": "count", "required": True,
              "status": "PASS" if grain_counts ==
              {"world_x": 2, "world_y": 4} else "FAIL"})
    end_grain_names = ("PT_Rail_End_Foot", "PT_Rail_End_Head",
                       "PT_Apron_Foot", "PT_Apron_Head")
    end_grain_offenders = []
    for name in end_grain_names:
        ob = objs.get(name)
        if ob is None or not ob.data.materials or \
                ob.data.materials[0].name != "MAT_Table_Walnut_CrossGrain":
            end_grain_offenders.append(name)
    R.append({"check": "visible_end_boards_use_cross_table_grain",
              "measured": len(end_grain_names) - len(end_grain_offenders),
              "expected": 4, "unit": "count", "required": True,
              "offenders": end_grain_offenders,
              "status": "PASS" if not end_grain_offenders else "FAIL"})
    # The iron is a visible rail-top U under its padded welt.  It must remain
    # outside the Pooltool capture circle; the retired below-bed hidden-ring
    # assertion would reject the real construction shown by the references.
    iron_offenders = []
    welt_offenders = []
    skirt_offenders = []
    stitch_offenders = []
    sweep_rows = []
    pockets_by_name = {pocket["name"]: pocket
                       for pocket in G.pocket_rows(contract)}
    for key, pocket in pockets_by_name.items():
        iron = objs.get("PT_PocketIron_" + key)
        welt = objs.get("PT_PocketLeatherWelt_" + key)
        skirt = objs.get("PT_PocketLeatherSkirt_" + key)
        stitch = objs.get("PT_PocketStitches_" + key)

        if iron is None:
            iron_offenders.append(key + " missing iron")
        else:
            bounds = _world_bbox([iron])
            opening = float(iron.get("opening_radius", 0.0))
            outside = float(iron.get("outside_capture_circle_m", -999.0))
            measured_gap = (C.RAIL_TOP_Z - bounds[5]) if bounds else -999.0
            recorded_gap = float(iron.get("top_below_rail_top_m", -999.0))
            material_ok = (iron.data.materials and
                           iron.data.materials[0].name ==
                           "MAT_Metal_BlackenedSteel")
            if (not bounds or iron.hide_render or not material_ok or
                    opening <= pocket["radius"] + 0.5 * MM or
                    abs(outside - (opening - pocket["radius"])) > 0.05 * MM or
                    outside <= 0.5 * MM or
                    bounds[4] < C.BED_Z - 0.1 * MM or
                    not (0.5 * MM <= measured_gap <= 12.0 * MM) or
                    abs(recorded_gap - measured_gap) > 0.1 * MM or
                    not iron.get("mounted_by_two_ears", False)):
                iron_offenders.append({
                    "object": iron.name,
                    "opening_radius_m": opening,
                    "capture_radius_m": pocket["radius"],
                    "outside_capture_circle_m": outside,
                    "top_below_rail_top_m": measured_gap,
                    "visible": not iron.hide_render,
                    "material_ok": bool(material_ok),
                })

        if welt is None:
            welt_offenders.append(key + " missing welt")
        else:
            bounds = _world_bbox([welt])
            clear = float(welt.get("clear_radius_m", 0.0))
            measured_gap = (C.RAIL_TOP_Z - bounds[5]) if bounds else -999.0
            recorded_gap = float(welt.get("top_below_rail_top_m", -999.0))
            expected_sweep = (C.DD_POCKET_CORNER_SWEEP_DEG
                              if pocket["kind"] == "corner"
                              else C.DD_POCKET_SIDE_SWEEP_DEG)
            sweep = float(welt.get("open_sweep_deg", -999.0))
            opening = float(welt.get("open_toward_playfield_deg", -999.0))
            sweep_rows.append({"pocket": key, "kind": pocket["kind"],
                               "sweep_deg": sweep,
                               "playfield_opening_deg": opening})
            material_ok = (welt.data.materials and
                           welt.data.materials[0].name ==
                           "MAT_Pocket_Leather_Interior")
            if (not bounds or welt.hide_render or not material_ok or
                    not welt.get("leather_wrapped_iron", False) or
                    clear <= pocket["radius"] + 0.5 * MM or
                    abs(sweep - expected_sweep) > 0.05 or
                    abs(opening - (360.0 - expected_sweep)) > 0.05 or
                    opening < 120.0 or
                    not (0.5 * MM <= measured_gap <= 4.0 * MM) or
                    abs(recorded_gap - measured_gap) > 0.1 * MM):
                welt_offenders.append({
                    "object": welt.name, "clear_radius_m": clear,
                    "capture_radius_m": pocket["radius"],
                    "sweep_deg": sweep, "expected_sweep_deg": expected_sweep,
                    "playfield_opening_deg": opening,
                    "top_below_rail_top_m": measured_gap,
                    "material_ok": bool(material_ok),
                })

        if skirt is None:
            skirt_offenders.append(key + " missing skirt")
        else:
            bounds = _world_bbox([skirt])
            clear = float(skirt.get("clear_radius_m", 0.0))
            welt_bounds = _world_bbox([welt]) if welt else None
            material_ok = (skirt.data.materials and
                           skirt.data.materials[0].name ==
                           "MAT_Pocket_Leather_Interior")
            joined_to_welt = bool(bounds and welt_bounds and
                                  _bbox_overlaps(bounds, welt_bounds,
                                                 tolerance=0.1 * MM))
            if (not bounds or skirt.hide_render or not material_ok or
                    not skirt.get("directs_impacts_downward", False) or
                    clear <= pocket["radius"] + 0.5 * MM or
                    abs(bounds[4] - (C.BED_Z - C.CLOTH_T)) > 0.25 * MM or
                    bounds[5] > C.RAIL_TOP_Z or
                    not joined_to_welt):
                skirt_offenders.append({
                    "object": skirt.name, "clear_radius_m": clear,
                    "capture_radius_m": pocket["radius"],
                    "bottom_z_m": bounds[4] if bounds else None,
                    "top_z_m": bounds[5] if bounds else None,
                    "joined_to_welt": joined_to_welt,
                    "material_ok": bool(material_ok),
                })

        if stitch is None:
            stitch_offenders.append(key + " missing stitches")
        else:
            bounds = _world_bbox([stitch])
            material_ok = (stitch.data.materials and
                           stitch.data.materials[0].name ==
                           "MAT_Pocket_Leather_Oxblood")
            if (not bounds or stitch.hide_render or not material_ok or
                    int(stitch.get("stitch_count", 0)) != 14 or
                    not stitch.get("nonstructural_welt_seam", False) or
                    bounds[5] > C.RAIL_TOP_Z + 0.1 * MM):
                stitch_offenders.append({
                    "object": stitch.name,
                    "stitch_count": int(stitch.get("stitch_count", 0)),
                    "top_z_m": bounds[5] if bounds else None,
                    "material_ok": bool(material_ok),
                })

    R.append({"check": "pocket_irons_are_open_rail_top_castings",
              "measured": 6 - len(iron_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": iron_offenders,
              "status": "PASS" if not iron_offenders else "FAIL"})
    R.append({"check": "pocket_welts_leave_open_u_capture_clearance",
              "measured": 6 - len(welt_offenders), "expected": 6,
              "unit": "count", "required": True,
              "sweeps": sweep_rows, "offenders": welt_offenders,
              "status": "PASS" if not welt_offenders else "FAIL"})
    R.append({"check": "pocket_skirts_join_welts_to_bed_edge",
              "measured": 6 - len(skirt_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": skirt_offenders,
              "status": "PASS" if not skirt_offenders else "FAIL"})
    R.append({"check": "pocket_welts_have_discrete_stitch_runs",
              "measured": 6 - len(stitch_offenders), "expected": 6,
              "unit": "count", "required": True,
              "offenders": stitch_offenders,
              "status": "PASS" if not stitch_offenders else "FAIL"})

    hardware_offenders = []
    for key in pockets_by_name:
        owned_ears = [part for part in mount_ears if part.name.startswith(
            "PT_PocketMountEar_%s_" % key)]
        owned_bolts = [part for part in mount_bolts if part.name.startswith(
            "PT_PocketMountBolt_%s_" % key)]
        if len(owned_ears) != 2:
            hardware_offenders.append(key + " mount-ear count")
        if len(owned_bolts) != 2:
            hardware_offenders.append(key + " mount-bolt count")
        for ear in owned_ears:
            bounds = _world_bbox([ear])
            material_ok = (ear.data.materials and
                           ear.data.materials[0].name ==
                           "MAT_Metal_BlackenedSteel")
            if (not ear.hide_render or not material_ok or not bounds or
                    abs((bounds[5] - bounds[4]) -
                        C.DD_POCKET_MOUNT_EAR_H) > 0.1 * MM or
                    not ear.get("rail_cap_mount", False)):
                hardware_offenders.append(ear.name)
        for bolt in owned_bolts:
            bounds = _world_bbox([bolt])
            material_ok = (bolt.data.materials and
                           bolt.data.materials[0].name ==
                           "MAT_Metal_BlackenedSteel")
            if (not bolt.hide_render or not material_ok or not bounds or
                    abs((bounds[5] - bounds[4]) -
                        C.DD_POCKET_RIVET_H) > 0.1 * MM or
                    not bolt.get("recessed_mount_fastener", False)):
                hardware_offenders.append(bolt.name)
    R.append({"check": "pocket_irons_have_recessed_two_ear_mounts",
              "measured": 24 - len(hardware_offenders), "expected": 24,
              "unit": "part", "required": True,
              "offenders": hardware_offenders,
              "status": "PASS" if not hardware_offenders else "FAIL"})
    R.append({"check": "pocket_facing_cores_cloth_covered",
              "measured": len(facings) - len(exposed_facing_cores),
              "expected": 12, "unit": "count", "required": True,
              "offenders": exposed_facing_cores,
              "status": "PASS" if len(facings) == 12 and
              not exposed_facing_cores and
              all(o.get("covered_by_rail_cloth", False) for o in facings)
              else "FAIL"})
    R.append({"check": "rail_featherstrips_cloth_covered",
              "measured": len(featherstrips) - len(exposed_featherstrips),
              "expected": 6, "unit": "count", "required": True,
              "offenders": exposed_featherstrips,
              "status": "PASS" if len(featherstrips) == 6 and
              not exposed_featherstrips and
              all(o.get("covered_by_rail_cloth", False)
                  for o in featherstrips) else "FAIL"})
    terminal_bevel_offenders = []
    for cushion in noses:
        modifiers = [modifier for modifier in cushion.modifiers
                     if modifier.name == "PT_CushionTerminal_ClothEase" and
                     modifier.type == "BEVEL"]
        if (len(modifiers) != 1 or
                abs(modifiers[0].width -
                    C.DD_CUSHION_TERMINAL_EDGE_RADIUS) > 0.1 * MM or
                modifiers[0].segments != 3 or
                modifiers[0].limit_method != "VGROUP" or
                modifiers[0].vertex_group != "PocketFacingEdge"):
            terminal_bevel_offenders.append(cushion.name)
    R.append({"check": "cushion_terminals_have_cloth_edge_ease",
              "measured": len(noses) - len(terminal_bevel_offenders),
              "expected": 6, "unit": "count", "required": True,
              "offenders": terminal_bevel_offenders,
              "status": "PASS" if len(noses) == 6 and
              not terminal_bevel_offenders else "FAIL"})
    facing_cloth_offenders = []
    for cushion in noses:
        assigned = [polygon for polygon in cushion.data.polygons
                    if polygon.material_index == 1]
        facing_slot_ok = (len(cushion.data.materials) > 1 and
                          cushion.data.materials[1] and
                          cushion.data.materials[1].name ==
                          "MAT_Table_Cloth_PocketFacing" and
                          cushion.data.materials[1].get(
                              "steep_wrap_alias_suppressed", False))
        if not facing_slot_ok or len(assigned) != 12 or \
                int(cushion.get("pocket_facing_cloth_polygons", 0)) != 12:
            facing_cloth_offenders.append(cushion.name)
    R.append({"check": "cushion_terminal_zones_use_wrapped_worsted_cloth",
              "measured": len(noses) - len(facing_cloth_offenders),
              "expected": 6, "unit": "count", "required": True,
              "offenders": facing_cloth_offenders,
              "status": "PASS" if len(noses) == 6 and
              not facing_cloth_offenders else "FAIL"})
    wrong_throat_material = [o.name for o in throats
                             if not o.data.materials or
                             o.data.materials[0].name !=
                             "MAT_Pocket_Leather_Interior"]
    R.append({"check": "pocket_throats_use_dark_leather_not_wood",
              "measured": len(throats) - len(wrong_throat_material),
              "expected": 6, "unit": "count", "required": True,
              "offenders": wrong_throat_material,
              "status": "PASS" if len(throats) == 6 and
              not wrong_throat_material else "FAIL"})
    wrong_basket_material = [o.name for o in baskets
                             if not o.data.materials or
                             o.data.materials[0].name !=
                             "MAT_Pocket_Leather_Basket"]
    R.append({"check": "pocket_baskets_have_dark_interior_leather",
              "measured": len(baskets) - len(wrong_basket_material),
              "expected": 6, "unit": "count", "required": True,
              "offenders": wrong_basket_material,
              "status": "PASS" if len(baskets) == 6 and
              not wrong_basket_material else "FAIL"})
    wrong_base_material = [o.name for o in basket_bases
                           if not o.data.materials or
                           o.data.materials[0].name !=
                           "MAT_Pocket_Leather_DeepShadow"]
    R.append({"check": "pocket_basket_bases_use_deep_leather_shadow",
              "measured": len(basket_bases) - len(wrong_base_material),
              "expected": 6, "unit": "count", "required": True,
              "offenders": wrong_base_material,
              "status": "PASS" if len(basket_bases) == 6 and
              not wrong_base_material and
              all(o.get("quiet_replaceable_wear_part", False)
                  for o in basket_bases) else "FAIL"})

    strap_finish_offenders = []
    for strap in straps:
        material_ok = (strap.data.materials and
                       strap.data.materials[0].name ==
                       "MAT_Pocket_Leather_Oxblood")
        if (strap.hide_render or not material_ok or
                not strap.get("vegetable_tanned_suspension_strap", False) or
                abs(float(strap.get("iron_overlap_m", -999.0)) -
                    C.DD_POCKET_STRAP_OVERLAP) > 0.05 * MM or
                abs(float(strap.get("basket_overlap_m", -999.0)) -
                    C.DD_POCKET_STRAP_OVERLAP) > 0.05 * MM):
            strap_finish_offenders.append(strap.name)
    R.append({"check": "pocket_suspension_straps_are_visible_leather",
              "measured": len(straps) - len(strap_finish_offenders),
              "expected": 18, "unit": "count", "required": True,
              "offenders": strap_finish_offenders,
              "status": "PASS" if len(straps) == 18 and
              not strap_finish_offenders else "FAIL"})

    rivet_finish_offenders = []
    for rivet in strap_rivets:
        material_ok = (rivet.data.materials and
                       rivet.data.materials[0].name ==
                       "MAT_Metal_BlackenedSteel")
        if (rivet.hide_render or not material_ok or
                not rivet.get("strap_fastener", False)):
            rivet_finish_offenders.append(rivet.name)
    R.append({"check": "pocket_straps_have_visible_steel_rivets",
              "measured": len(strap_rivets) - len(rivet_finish_offenders),
              "expected": 18, "unit": "count", "required": True,
              "offenders": rivet_finish_offenders,
              "status": "PASS" if len(strap_rivets) == 18 and
              not rivet_finish_offenders else "FAIL"})

    # Evaluate actual manufactured contact and forbidden intersections. These
    # checks caught the earlier case where a visually open pocket still ran
    # through a solid slate liner and perimeter sill.
    bvh_cache = {}

    def meshes_overlap(first, second):
        first_bounds = _world_bbox([first])
        second_bounds = _world_bbox([second])
        if not _bbox_overlaps(first_bounds, second_bounds, tolerance=0.1 * MM):
            return False
        if first.name not in bvh_cache:
            bvh_cache[first.name] = _evaluated_bvh(first)
        if second.name not in bvh_cache:
            bvh_cache[second.name] = _evaluated_bvh(second)
        return bool(bvh_cache[first.name].overlap(bvh_cache[second.name]))

    aprons = [o for n, o in objs.items() if n.startswith("PT_Apron_")]
    engineering_wood = ([liner] if liner else []) + long_sills + end_sills + \
        cross_sills + centre_beams + aprons
    pocket_drop_parts = (pocket_liners + throats + baskets + basket_bases +
                         straps + strap_rivets)
    engineering_collisions = []
    for part in pocket_drop_parts:
        for structure in engineering_wood:
            if meshes_overlap(part, structure):
                engineering_collisions.append(
                    "%s/%s" % (part.name, structure.name))
    R.append({"check": "pocket_drop_clear_of_hidden_wood_and_aprons",
              "measured": len(engineering_collisions), "expected": 0,
              "unit": "pair", "required": True,
              "offenders": engineering_collisions[:24],
              "status": "PASS" if not engineering_collisions else "FAIL"})

    attachment_offenders = []
    expected_attachment_contacts = 0
    passed_attachment_contacts = 0

    def require_contact(label, first, second):
        nonlocal expected_attachment_contacts, passed_attachment_contacts
        expected_attachment_contacts += 1
        if first is None or second is None:
            attachment_offenders.append(label + " missing part")
        elif meshes_overlap(first, second):
            passed_attachment_contacts += 1
        else:
            attachment_offenders.append(label)

    for pocket in G.pocket_rows(contract):
        key = pocket["name"]
        iron = objs.get("PT_PocketIron_" + key)
        welt = objs.get("PT_PocketLeatherWelt_" + key)
        basket = objs.get("PT_PocketBasket_" + key)
        throat = objs.get("PT_PocketThroat_" + key)
        require_contact(key + " iron/welt", iron, welt)
        require_contact(key + " throat/basket", throat, basket)

        owned_ears = sorted(
            (ear for ear in mount_ears if ear.name.startswith(
                "PT_PocketMountEar_%s_" % key)), key=lambda ob: ob.name)
        owned_bolts = sorted(
            (bolt for bolt in mount_bolts if bolt.name.startswith(
                "PT_PocketMountBolt_%s_" % key)), key=lambda ob: ob.name)
        for index in range(2):
            ear = owned_ears[index] if index < len(owned_ears) else None
            bolt = owned_bolts[index] if index < len(owned_bolts) else None
            require_contact("%s ear%d/iron" % (key, index), ear, iron)
            require_contact("%s bolt%d/ear" % (key, index), bolt, ear)
            expected_attachment_contacts += 1
            if ear is not None and any(meshes_overlap(ear, cap)
                                       for cap in rail_caps + cap_horns):
                passed_attachment_contacts += 1
            else:
                attachment_offenders.append(
                    "%s ear%d/rail-cap" % (key, index))

        owned_straps = [strap for strap in straps if strap.name.startswith(
            "PT_PocketLeatherStrap_%s_" % key)]
        owned_rivets = [rivet for rivet in strap_rivets
                        if rivet.name.startswith(
                            "PT_PocketStrapRivet_%s_" % key)]
        owned_straps.sort(key=lambda ob: ob.name)
        owned_rivets.sort(key=lambda ob: ob.name)
        for index in range(3):
            strap = owned_straps[index] if index < len(owned_straps) else None
            rivet = owned_rivets[index] if index < len(owned_rivets) else None
            require_contact("%s strap%d/iron" % (key, index), strap, iron)
            require_contact("%s strap%d/basket" % (key, index), strap,
                            basket)
            require_contact("%s rivet%d/strap" % (key, index), rivet,
                            strap)
    R.append({"check": "pocket_assembly_attachment_contacts",
              "measured": passed_attachment_contacts,
              "expected": expected_attachment_contacts,
              "unit": "contact", "required": True,
              "offenders": attachment_offenders,
              "status": "PASS" if expected_attachment_contacts == 102 and
              passed_attachment_contacts == expected_attachment_contacts and
              not attachment_offenders else "FAIL"})

    # Environment dressing may be visually dense, but the future playable
    # pool setup still needs the full nominal 58-inch cue envelope clear.
    dress_collections = [bpy.data.collections.get(name) for name in
                         ("06_SET_DRESSING", "06_PATRON_FOOTPRINTS")]
    intruders = []
    if any(dress_collections):
        x0 = C.TABLE_CENTRE[0] - C.CUE_ENVELOPE_W / 2.0
        x1 = C.TABLE_CENTRE[0] + C.CUE_ENVELOPE_W / 2.0
        y0 = C.TABLE_CENTRE[1] - C.CUE_ENVELOPE_L / 2.0
        y1 = C.TABLE_CENTRE[1] + C.CUE_ENVELOPE_L / 2.0
        for dress in (c for c in dress_collections if c is not None):
            for ob in dress.all_objects:
                if ob.type != "MESH":
                    continue
                bb = _world_bbox([ob])
                if not bb or bb[5] <= 0.10:
                    continue
                overlaps_x = bb[1] > x0 and bb[0] < x1
                overlaps_y = bb[3] > y0 and bb[2] < y1
                if overlaps_x and overlaps_y:
                    intruders.append(ob.name)
    R.append({"check": "set_dressing_clear_of_cue_envelope",
              "measured": len(intruders), "expected": 0, "unit": "count",
              "required": True, "offenders": intruders[:12],
              "status": "PASS" if not intruders else "FAIL"})

    # ------------------------------------------------ environment contract --
    shades = [o for n, o in objs.items() if n.startswith("LGT_Pool_Shade_")]
    shade_bb = _world_bbox(shades)
    shade_above_bed = None if shade_bb is None else shade_bb[4] - C.BED_Z
    check(R, "movable_fixture_height_above_bed", shade_above_bed,
          C.FIXTURE_MIN_ABOVE_BED, 2.0 * MM)
    pool_fill = objs.get("LGT_Pool_Fill")
    fill_energy = (pool_fill.data.energy if pool_fill and
                   pool_fill.type == "LIGHT" else None)
    check(R, "pool_table_fill_revision_energy", fill_energy, 8.0, 0.01,
          unit="W")

    doors = [name for name in ("ENV_FrontDoor_Glass", "ENV_ServiceDoor",
                                "ENV_BathroomDoor") if name in objs]
    R.append({"check": "constructed_public_service_door_count",
              "measured": len(doors), "expected": 3, "unit": "count",
              "required": True, "status": "PASS" if len(doors) == 3
              else "FAIL"})

    stock = [o for o in bpy.data.objects if o.get("stock_bottle", False)]
    minimum_stock = 120
    R.append({"check": "bar_stock_bottle_density", "measured": len(stock),
              "expected": ">=%d" % minimum_stock, "unit": "count",
              "required": True, "status": "PASS" if len(stock) >= minimum_stock
              else "FAIL"})

    floor = objs.get("ENV_Floor")
    floor_mat = (floor.data.materials[0].name if floor and
                 floor.data.materials else None)
    R.append({"check": "floor_is_neglected_concrete", "measured": floor_mat,
              "expected": "MAT_Env_Floor_NeglectedConcrete", "unit": "name",
              "required": True,
              "status": "PASS" if floor_mat ==
              "MAT_Env_Floor_NeglectedConcrete" else "FAIL"})

    # -------------------------------- texel density (Amendment Patch 7) -----
    hero_names = ("PT_Ball_", "PT_Cloth_", "PT_Rail_", "PT_Cushion_")
    thin = []
    for img in bpy.data.images:
        if img.size[0] == 0:
            continue
        # decals are equirectangular over one ball: px per metre of UV space
        if "ball" in img.name.lower():
            ppm = img.size[0] / (math.pi * C.BALL_D)
            if ppm < C.TEXEL_HERO:
                thin.append("%s=%.0f" % (img.name, ppm))
    R.append({"check": "texel_density_hero_surfaces",
              "measured": len(bpy.data.images) - len(thin),
              "expected": len(bpy.data.images), "unit": "count",
              "floor_px_per_m": C.TEXEL_HERO, "required": False,
              "offenders": thin[:6],
              "status": "PASS" if not thin else "FAIL"})

    # ------------------------------------------------------------ hygiene --
    phys = [o.name for o in bpy.data.objects if o.rigid_body is not None]
    R.append({"check": "rigid_body_count", "measured": len(phys),
              "expected": 0, "status": "PASS" if not phys else "FAIL",
              "required": True, "unit": "count"})

    proxy_collection = bpy.data.collections.get("10_PHYSICS_PROXIES")
    proxies = (list(proxy_collection.all_objects)
               if proxy_collection is not None else [])
    proxy_counts = {
        "total": len(proxies),
        "linear": sum(o.name.startswith("PTX_Linear_") for o in proxies),
        "arc": sum(o.name.startswith("PTX_Arc_") for o in proxies),
        "solver_pocket": sum(
            o.name.startswith("PTX_SolverPocket_") for o in proxies),
        "shelf_drop": sum(
            o.name.startswith("PTX_ShelfDrop_") for o in proxies),
    }
    expected_proxy_counts = {"total": 42, "linear": 18, "arc": 12,
                             "solver_pocket": 6, "shelf_drop": 6}
    visible_proxies = [o.name for o in proxies if not o.hide_render]
    R.append({"check": "physics_proxy_feature_counts",
              "measured": proxy_counts, "expected": expected_proxy_counts,
              "required": True, "unit": "count",
              "status": "PASS" if proxy_counts == expected_proxy_counts
              else "FAIL"})
    R.append({"check": "physics_proxies_hidden_from_render",
              "measured": len(visible_proxies), "expected": 0,
              "required": True, "unit": "count",
              "offenders": visible_proxies,
              "status": "PASS" if not visible_proxies else "FAIL"})
    solver_pockets = [o for o in proxies
                      if o.name.startswith("PTX_SolverPocket_")]
    shelf_drops = [o for o in proxies
                   if o.name.startswith("PTX_ShelfDrop_")]
    contact_debug = [o for o in proxies if
                     o.name.startswith(("PTX_Linear_", "PTX_Arc_"))]
    contact_offset_offenders = [o.name for o in contact_debug
                                if not o.get("debug_visual_only", False) or
                                not o.get("solver_surface_is_centerline",
                                          False)]
    solver_pocket_offenders = []
    for pocket in G.pocket_rows(contract):
        solver = objs.get("PTX_SolverPocket_" + pocket["name"])
        if solver is None:
            solver_pocket_offenders.append(pocket["name"] + " missing")
            continue
        manifold, volume = _mesh_manifold_positive(solver.data)
        bounds = _world_bbox([solver])
        expected_center = (
            C.TABLE_CENTRE[0] + pocket["center"][0],
            C.TABLE_CENTRE[1] + pocket["center"][1],
        )
        measured_center = (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
        ) if bounds else (999.0, 999.0)
        measured_radii = (
            (bounds[1] - bounds[0]) / 2.0,
            (bounds[3] - bounds[2]) / 2.0,
        ) if bounds else (999.0, 999.0)
        center_error = math.dist(measured_center, expected_center)
        radius_error = max(abs(value - pocket["radius"])
                           for value in measured_radii)
        metadata_error = max(
            abs(float(solver.get("capture_center_x_m", -999.0)) -
                pocket["center"][0]),
            abs(float(solver.get("capture_center_y_m", -999.0)) -
                pocket["center"][1]),
            abs(float(solver.get("capture_radius_m", -999.0)) -
                pocket["radius"]),
            abs(float(solver.get("capture_depth_m", -999.0)) -
                pocket["depth"]),
        )
        if (not manifold or volume <= 0.0 or not bounds or
                center_error > 0.1 * MM or radius_error > 0.1 * MM or
                abs(bounds[4] - (C.BED_Z - pocket["depth"])) > 0.1 * MM or
                abs(bounds[5] - C.BED_Z) > 0.1 * MM or
                metadata_error > 0.1 * MM or
                solver.get("pocket_id") != pocket["id"] or
                not solver.get("trigger_only", False) or
                solver.get("collision_role") !=
                "pooltool_capture_sensor_not_solid" or
                solver.get("trigger_metric") != "ball_center_xy" or
                solver.get("capture_condition") !=
                "ball_center_crosses_circular_radius" or
                not solver.get("debug_visual_only", False)):
            solver_pocket_offenders.append({
                "object": solver.name, "manifold": manifold,
                "signed_volume_m3": volume,
                "center_error_m": center_error,
                "radius_error_m": radius_error,
                "metadata_error_m": metadata_error,
                "collision_role": solver.get("collision_role"),
                "trigger_metric": solver.get("trigger_metric"),
                "capture_condition": solver.get("capture_condition"),
            })
    R.append({"check": "solver_pocket_proxies_match_pooltool_circles",
              "measured": 6 - len(solver_pocket_offenders),
              "expected": 6, "required": True, "unit": "count",
              "offenders": solver_pocket_offenders,
              "status": "PASS" if len(solver_pockets) == 6 and
              not solver_pocket_offenders else "FAIL"})

    shelf_geometry_offenders = []
    for pocket in G.pocket_rows(contract):
        shelf_drop = objs.get("PTX_ShelfDrop_" + pocket["name"])
        target = (C.CORNER_SHELF if pocket["kind"] == "corner"
                  else C.SIDE_SHELF)
        shelf = G.pocket_shelf_cut_details(contract, pocket, target)
        if shelf_drop is None:
            shelf_geometry_offenders.append(pocket["name"] + " missing")
            continue
        count = len(shelf["outline"])
        manifold, volume = _mesh_manifold_positive(shelf_drop.data)
        bounds = _world_bbox([shelf_drop])
        top_ring = []
        if len(shelf_drop.data.vertices) == 2 * count:
            for index in range(count):
                world = shelf_drop.matrix_world @ shelf_drop.data.vertices[
                    count + index].co
                top_ring.append((world.x - C.TABLE_CENTRE[0],
                                 world.y - C.TABLE_CENTRE[1]))
        source_matches = (len(top_ring) == count and
                          all(G.polygon_boundary_distance(point, top_ring) <=
                              2e-6 for point in shelf["outline"]) and
                          all(G.polygon_boundary_distance(point,
                                                          shelf["outline"]) <=
                              2e-6 for point in top_ring))
        drop = shelf["drop_mid"]
        outward = shelf["outward"]
        inboard = (drop[0] - outward[0] * 0.5 * MM,
                   drop[1] - outward[1] * 0.5 * MM)
        outboard = (drop[0] + outward[0] * 0.5 * MM,
                    drop[1] + outward[1] * 0.5 * MM)
        gated = (top_ring and not G._point_in_polygon(inboard, top_ring) and
                 G._point_in_polygon(outboard, top_ring))
        if (not manifold or volume <= 0.0 or not bounds or
                abs(bounds[4] - (C.BED_Z - pocket["depth"])) > 0.1 * MM or
                abs(bounds[5] - C.BED_Z) > 0.1 * MM or
                not source_matches or not gated or
                shelf_drop.get("pocket_id") != pocket["id"] or
                shelf_drop.get("trigger_only", True) or
                not shelf_drop.get("static_construction_diagnostic", False) or
                shelf_drop.get("collision_role") !=
                "shelf_drop_not_solver_trigger" or
                not shelf_drop.get("not_used_by_pooltool_solver", False) or
                not shelf_drop.get("shelf_gated", False) or
                abs(float(shelf_drop.get("shelf_target_m", -999.0)) -
                    target) > 0.1 * MM or
                not shelf_drop.get("debug_visual_only", False)):
            shelf_geometry_offenders.append({
                "object": shelf_drop.name, "manifold": manifold,
                "signed_volume_m3": volume, "source_matches": source_matches,
                "inboard_outside_outboard_inside": bool(gated),
                "collision_role": shelf_drop.get("collision_role"),
                "not_used_by_pooltool_solver": shelf_drop.get(
                    "not_used_by_pooltool_solver")})
    R.append({"check": "shelf_drop_proxies_are_static_construction_only",
              "measured": 6 - len(shelf_geometry_offenders),
              "expected": 6, "required": True, "unit": "count",
              "offenders": shelf_geometry_offenders,
              "status": "PASS" if len(shelf_drops) == 6 and
              not shelf_geometry_offenders else "FAIL"})
    R.append({"check": "contact_proxy_radius_is_debug_only",
              "measured": len(contact_debug) - len(contact_offset_offenders),
              "expected": 30, "required": True, "unit": "count",
              "offenders": contact_offset_offenders[:8],
              "status": "PASS" if len(contact_debug) == 30 and
              not contact_offset_offenders else "FAIL"})

    nonuni = [o.name for o in bpy.data.objects
              if o.type == "MESH" and not o.name.startswith("REF_")
              and any(abs(s - 1.0) > 1e-5 for s in o.scale)]
    R.append({"check": "unapplied_scale_on_production_meshes",
              "measured": len(nonuni), "expected": 0,
              "status": "PASS" if not nonuni else "FAIL", "required": False,
              "offenders": nonuni[:10], "unit": "count"})

    empty_slots = [o.name for o in bpy.data.objects
                   if o.type == "MESH" and not o.name.startswith("REF_")
                   and not o.name.startswith("GUIDE_")
                   and not o.get("boolean_proof_volume", False)
                   and (not o.data.materials or
                        any(m is None for m in o.data.materials))]
    R.append({"check": "unassigned_material_slots", "measured":
              len(empty_slots), "expected": 0,
              "status": "PASS" if not empty_slots else "FAIL",
              "required": False, "offenders": empty_slots[:10],
              "unit": "count"})

    missing = [i.filepath for i in bpy.data.images
               if i.source == "FILE" and i.filepath and
               not os.path.exists(bpy.path.abspath(i.filepath))]
    R.append({"check": "missing_external_files", "measured": len(missing),
              "expected": 0, "status": "PASS" if not missing else "FAIL",
              "required": True, "offenders": missing[:10], "unit": "count"})

    ref_excluded = True
    for vl in bpy.context.scene.view_layers:
        for nm in ("99_REFERENCE_LOCKED", "00_GUIDES"):
            lc = vl.layer_collection.children.get(nm)
            if lc and not lc.exclude:
                ref_excluded = False
    R.append({"check": "reference_collection_excluded",
              "measured": ref_excluded, "expected": True,
              "status": "PASS" if ref_excluded else "FAIL",
              "required": True, "unit": "bool"})

    strays = [o.name for o in bpy.data.objects
              if not o.name.startswith(("PT_", "PTX_", "ENV_", "BAR_", "LGT_", "CAM_",
                                        "REF_", "GUIDE_", "ATM_", "PROP_",
                                        "PATRON_"))]
    R.append({"check": "no_stray_startup_objects", "measured": len(strays),
              "expected": 0, "unit": "count", "required": True,
              "offenders": strays[:10],
              "status": "PASS" if not strays else "FAIL"})

    # ------------------------------------------------------------- report --
    required_fail = [r for r in R if r.get("required") and r["status"] == "FAIL"]
    out = {
        "generated": "2026-08-05",
        "engine": bpy.context.scene.render.engine,
        "resolution": [bpy.context.scene.render.resolution_x,
                       bpy.context.scene.render.resolution_y],
        "wpa_flatness_metadata_not_simulated": {
            "lengthwise_m": C.FLATNESS_LENGTHWISE,
            "widthwise_m": C.FLATNESS_WIDTHWISE,
            "joint_coplanar_m": C.JOINT_COPLANAR,
            "centre_deflection_m": C.CENTRE_DEFLECTION,
        },
        "summary": {"total": len(R),
                    "passed": sum(1 for r in R if r["status"] == "PASS"),
                    "failed": sum(1 for r in R if r["status"] == "FAIL"),
                    "required_failures": len(required_fail)},
        "checks": R,
    }
    path = os.path.join(C.ROOT, "reports", "dimension_audit.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"), indent=2)

    for r in R:
        mark = "ok " if r["status"] == "PASS" else "FAIL"
        m = r.get("measured")
        ms = ("%.6f" % m) if isinstance(m, float) else str(m)
        print("  [%s] %-38s %s" % (mark, r["check"], ms))
    print("  [audit] %d/%d passed, %d required failures"
          % (out["summary"]["passed"], out["summary"]["total"],
             len(required_fail)))
    return len(required_fail) == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
