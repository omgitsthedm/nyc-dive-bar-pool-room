"""
lib.py — shared Blender helpers. Data-API first, minimal operator dependence.

Every builder stage owns exactly one collection and is idempotent: rerunning a
stage wipes and rebuilds its own collection and touches nothing else.
"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix

import config as C


# ------------------------------------------------------------ collections ---
def scene_root():
    return bpy.context.scene.collection


def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    parent = parent or scene_root()
    if col.name not in parent.children:
        parent.children.link(col)
    return col


def clear_collection(name):
    """Remove a collection's objects and their data. Idempotent stage reset."""
    col = bpy.data.collections.get(name)
    if col is None:
        return get_collection(name)
    for ob in list(col.all_objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        for store in (bpy.data.meshes, bpy.data.curves, bpy.data.lights,
                      bpy.data.cameras):
            if data is not None and data.users == 0:
                try:
                    store.remove(data)
                except (TypeError, ReferenceError):
                    pass
                break
    return col


def link(ob, collection_name):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    get_collection(collection_name).objects.link(ob)
    return ob


# ----------------------------------------------------------------- meshes ---
def mesh_object(name, verts, faces, collection, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(verbose=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    if mat is not None:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def box(name, size, location, collection, mat=None, rotation=None, bevel=0.0,
        bevel_segments=2):
    """Axis-aligned box built from data, then optionally bevelled."""
    sx, sy, sz = (s / 2.0 for s in size)
    verts = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
             (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    ob = mesh_object(name, verts, faces, collection, mat)
    ob.location = location
    if rotation:
        ob.rotation_euler = rotation
    if bevel:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = bevel_segments
        m.limit_method = "ANGLE"
        m.angle_limit = math.radians(30)
    return ob


def cylinder(name, radius, depth, location, collection, mat=None,
             segments=48, rotation=None, smooth=True):
    verts, faces = [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        x, y = radius * math.cos(a), radius * math.sin(a)
        verts.append((x, y, -depth / 2.0))
        verts.append((x, y, depth / 2.0))
    for i in range(segments):
        a0, a1 = 2 * i, 2 * ((i + 1) % segments)
        faces.append((a0, a1, a1 + 1, a0 + 1))
    faces.append(tuple(range(0, 2 * segments, 2))[::-1])
    faces.append(tuple(range(1, 2 * segments, 2)))
    ob = mesh_object(name, verts, faces, collection, mat, smooth=False)
    if smooth:
        for p in ob.data.polygons:
            if len(p.vertices) == 4:
                p.use_smooth = True
    ob.location = location
    if rotation:
        ob.rotation_euler = rotation
    return ob


def cylinder_between(name, radius, start, end, collection, mat=None,
                     segments=16, smooth=True):
    """Cylinder whose axis follows two world-space endpoints.

    Useful for hardware arms, wall brackets and furniture braces where a
    vertical primitive rotated by eye would not visibly connect its supports.
    """
    a, b = Vector(start), Vector(end)
    vector = b - a
    if vector.length <= 1e-8:
        raise ValueError("cylinder endpoints must be distinct")
    ob = cylinder(name, radius, vector.length, (a + b) / 2.0, collection,
                  mat, segments=segments, smooth=smooth)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(
        vector.normalized())
    return ob


def curve_tube(name, points, radius, collection, mat=None, resolution=2):
    """Bevelled 3D poly spline for cords, hoses and irregular old wiring."""
    if len(points) < 2:
        raise ValueError("curve_tube requires at least two points")
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1.0)
    ob = bpy.data.objects.new(name, curve)
    link(ob, collection)
    if mat is not None:
        curve.materials.append(mat)
    return ob


def ring(name, inner_radius, outer_radius, depth, location, collection,
         mat=None, segments=64, rotation=None):
    """A true annular ring with an open centre; unlike ``cylinder`` it never
    places a cap across the hole. Used for pocket irons and stool foot rings.
    """
    if inner_radius <= 0 or outer_radius <= inner_radius:
        raise ValueError("ring radii must satisfy 0 < inner < outer")
    z0, z1 = -depth / 2.0, depth / 2.0
    verts, faces = [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        verts.extend([
            (outer_radius * ca, outer_radius * sa, z0),
            (outer_radius * ca, outer_radius * sa, z1),
            (inner_radius * ca, inner_radius * sa, z0),
            (inner_radius * ca, inner_radius * sa, z1),
        ])
    for i in range(segments):
        j = (i + 1) % segments
        a, b = i * 4, j * 4
        faces.extend([
            (a, b, b + 1, a + 1),              # outer wall
            (a + 2, a + 3, b + 3, b + 2),      # inner wall
            (a + 1, b + 1, b + 3, a + 3),      # top
            (a, a + 2, b + 2, b),              # underside
        ])
    ob = mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = location
    if rotation:
        ob.rotation_euler = rotation
    return ob


def revolved_surface(name, profile, collection, mat=None, segments=64,
                     location=(0, 0, 0), close_profile=False):
    """Revolve a profile around Z without capping the axis.

    ``close_profile`` joins the final profile point back to the first, which
    makes a hollow manufactured shell such as an enamel billiard-light shade.
    """
    verts, faces = [], []
    n = len(profile)
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for radius, z in profile:
            verts.append((radius * ca, radius * sa, z))
    span = n if close_profile else n - 1
    for i in range(segments):
        j = (i + 1) % segments
        for k in range(span):
            k2 = (k + 1) % n
            faces.append((i * n + k, j * n + k, j * n + k2,
                          i * n + k2))
    ob = mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = location
    return ob


def image_plane(name, width, height, location, collection, mat=None,
                wall_axis="X", rotation=None, face_inward=True):
    """A UV-mapped wall plane. ``wall_axis`` is the plane normal (X or Y)."""
    if wall_axis == "X":
        verts = [(0, -width / 2, -height / 2),
                 (0, width / 2, -height / 2),
                 (0, width / 2, height / 2),
                 (0, -width / 2, height / 2)]
    elif wall_axis == "Y":
        verts = [(-width / 2, 0, -height / 2),
                 (width / 2, 0, -height / 2),
                 (width / 2, 0, height / 2),
                 (-width / 2, 0, height / 2)]
    else:
        raise ValueError("wall_axis must be X or Y")
    face = (3, 2, 1, 0) if face_inward else (0, 1, 2, 3)
    ob = mesh_object(name, verts, [face], collection, mat)
    ob.location = location
    if rotation:
        ob.rotation_euler = rotation
    uv = ob.data.uv_layers.new(name="UVMap")
    # Loop order follows the selected face winding; map from bottom-left to
    # top-right while preserving the scan's original orientation.
    if wall_axis == "X" and face_inward:
        # We are viewing the back of an east-wall sheet from inside the room;
        # reverse U once so printed words do not appear mirrored.
        coords = ((1, 1), (0, 1), (0, 0), (1, 0))
    else:
        coords = ((0, 1), (1, 1), (1, 0), (0, 0)) if face_inward else \
                 ((0, 0), (1, 0), (1, 1), (0, 1))
    for loop, coord in zip(ob.data.polygons[0].loop_indices, coords):
        uv.data[loop].uv = coord
    return ob


def lathe(name, profile, collection, mat=None, segments=64, location=(0, 0, 0)):
    """
    Revolve a 2D profile [(radius, z), ...] about Z. Used for turned legs,
    which is how a real leg is made on a lathe.
    """
    verts, faces = [], []
    n = len(profile)
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in profile:
            verts.append((r * ca, r * sa, z))
    for i in range(segments):
        j = (i + 1) % segments
        for k in range(n - 1):
            faces.append((i * n + k, j * n + k, j * n + k + 1, i * n + k + 1))
    # caps
    faces.append(tuple(i * n for i in range(segments))[::-1])
    faces.append(tuple(i * n + (n - 1) for i in range(segments)))
    ob = mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = location
    return ob


def extrude_profile(name, path, normals, profile, collection, mat=None,
                    smooth=False):
    """
    Sweep a cross-section along a path. `profile` is [(back, height), ...]
    where `back` is distance behind the path point along -normal.
    Used for cushions and rail bodies so they follow the pocket jaws.
    """
    verts, faces = [], []
    n = len(profile)
    for p, nrm in zip(path, normals):
        b = Vector((-nrm.x, -nrm.y, 0.0))
        for (d, z) in profile:
            verts.append((p.x + b.x * d, p.y + b.y * d, p.z + z))
    for i in range(len(path) - 1):
        a, c = i * n, (i + 1) * n
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((a + k, a + k2, c + k2, c + k))
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple(range(len(verts) - n, len(verts))))
    return mesh_object(name, verts, faces, collection, mat, smooth=smooth)


def uv_sphere(name, radius, location, collection, mat=None, segments=64,
              rings=32):
    """An exact sphere: every vertex is `radius` from the centre."""
    verts, faces = [], []
    verts.append((0.0, 0.0, radius))
    for r in range(1, rings):
        phi = math.pi * r / rings
        z, rr = radius * math.cos(phi), radius * math.sin(phi)
        for s in range(segments):
            th = 2.0 * math.pi * s / segments
            verts.append((rr * math.cos(th), rr * math.sin(th), z))
    verts.append((0.0, 0.0, -radius))
    last = len(verts) - 1
    for s in range(segments):
        faces.append((0, 1 + s, 1 + (s + 1) % segments))
    for r in range(rings - 2):
        base, nxt = 1 + r * segments, 1 + (r + 1) * segments
        for s in range(segments):
            s2 = (s + 1) % segments
            faces.append((base + s, nxt + s, nxt + s2, base + s2))
    base = 1 + (rings - 2) * segments
    for s in range(segments):
        faces.append((last, base + (s + 1) % segments, base + s))
    ob = mesh_object(name, verts, faces, collection, mat, smooth=True)
    ob.location = location
    # Equirectangular UVs so a lat/long decal map lands correctly. Computed
    # from each vertex's own direction, so U/V follow the true sphere.
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            r = max(1e-9, co.length)
            u = 0.5 + math.atan2(co.y, co.x) / (2.0 * math.pi)
            v = 0.5 - math.asin(max(-1.0, min(1.0, co.z / r))) / math.pi
            uv.data[li].uv = (u, 1.0 - v)
    return ob


def boolean(target, cutter, operation="DIFFERENCE"):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = operation
    m.object = cutter
    m.solver = "EXACT"
    # Construction cuts belong to the raw manufactured part. Put the Boolean
    # ahead of presentation bevels/solidify modifiers so applying it cannot
    # bake or reorder an unrelated finish operation.
    modifier_index = target.modifiers.find(m.name)
    if modifier_index > 0:
        target.modifiers.move(modifier_index, 0)
    bpy.context.view_layer.objects.active = target
    try:
        bpy.ops.object.modifier_apply(modifier=m.name)
        return True
    except RuntimeError:
        target.modifiers.remove(m)
        return False


def clean_boolean_mesh(target, tolerance=1e-7):
    """Remove exact-solver zero-length artifacts without moving real edges."""
    if tolerance <= 0.0:
        raise ValueError("Boolean cleanup tolerance must be positive")
    bm = bmesh.new()
    bm.from_mesh(target.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=tolerance)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=tolerance)
    bm.normal_update()
    bm.to_mesh(target.data)
    bm.free()
    target.data.update()
    return target


def orient_closed_mesh_outward(target):
    """Flip an otherwise closed mesh only when its signed volume is inward."""
    bm = bmesh.new()
    bm.from_mesh(target.data)
    if not bm.faces or any(not edge.is_manifold for edge in bm.edges):
        bm.free()
        raise ValueError("mesh must be closed and manifold: %s" % target.name)
    volume = bm.calc_volume(signed=True)
    if volume < 0.0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.normal_update()
        bm.to_mesh(target.data)
        target.data.update()
        volume = -volume
    bm.free()
    target["closed_mesh_outward"] = True
    return volume


def shade_auto_smooth(ob, angle_deg=30.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    m = ob.modifiers.new("smooth_by_angle", "NODES")
    try:
        ng = bpy.data.node_groups.get("Smooth by Angle")
        if ng:
            m.node_group = ng
        else:
            ob.modifiers.remove(m)
    except Exception:
        ob.modifiers.remove(m)


def apply_transforms(ob):
    """Bake location/rotation/scale into the mesh so scale stays (1,1,1)."""
    me = ob.data
    if not hasattr(me, "vertices"):
        return
    mw = ob.matrix_world.copy()
    for v in me.vertices:
        v.co = mw @ v.co
    ob.matrix_world = Matrix.Identity(4)
    me.update()
