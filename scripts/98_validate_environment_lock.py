"""Write or verify the environment freeze before pool-system development.

The baseline fingerprints authored room/bar/patina/patron geometry, all
materials those objects use, every non-pool light, linked image assets, and
global scene colour management. Pool-table collections, balls, pool fixture
objects, cameras and pool-beam atmosphere intentionally remain outside the
lock so the next phase can change them.
"""
import bpy
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402


LOCK_VERSION = 1
LOCK_COLLECTIONS = (
    "01_ARCHITECTURE", "04_BAR", "06_SET_DRESSING", "06_PATINA",
    "06_PATRON_FOOTPRINTS",
)
REPORT = os.path.join(C.ROOT, "reports", "environment_lock.json")


def _round(value):
    return round(float(value), 7)


def _simple(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _round(value)
    if hasattr(value, "to_dict"):
        try:
            return {str(k): _simple(v) for k, v in
                    sorted(value.to_dict().items())}
        except Exception:
            pass
    if hasattr(value, "keys") and not isinstance(value, str):
        try:
            return {str(k): _simple(value[k]) for k in sorted(value.keys())}
        except Exception:
            pass
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_simple(v) for v in value]
        except Exception:
            pass
    return str(value)


def _sha(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _custom_props(owner):
    return {str(key): _simple(owner[key]) for key in sorted(owner.keys())
            if key != "_RNA_UI"}


def _modifier_payload(modifier):
    result = {"name": modifier.name, "type": modifier.type,
              "show_render": modifier.show_render}
    for key in ("width", "segments", "limit_method", "angle_limit",
                "operation", "solver", "thickness", "offset",
                "levels", "render_levels"):
        if hasattr(modifier, key):
            try:
                result[key] = _simple(getattr(modifier, key))
            except Exception:
                pass
    if hasattr(modifier, "object") and modifier.object is not None:
        result["object"] = modifier.object.name
    if hasattr(modifier, "node_group") and modifier.node_group is not None:
        result["node_group"] = modifier.node_group.name
    return result


def _mesh_payload(mesh):
    return {
        "vertices": [[_round(c) for c in vertex.co]
                     for vertex in mesh.vertices],
        "edges": [list(edge.vertices) for edge in mesh.edges],
        "polygons": [list(poly.vertices) for poly in mesh.polygons],
        "smooth": [bool(poly.use_smooth) for poly in mesh.polygons],
        "uv_layers": {
            layer.name: [[_round(v) for v in loop.uv] for loop in layer.data]
            for layer in mesh.uv_layers
        },
    }


def _curve_payload(curve):
    splines = []
    for spline in curve.splines:
        row = {"type": spline.type,
               "cyclic_u": bool(spline.use_cyclic_u), "points": []}
        if spline.type == "BEZIER":
            row["points"] = [{
                "co": [_round(v) for v in p.co],
                "left": [_round(v) for v in p.handle_left],
                "right": [_round(v) for v in p.handle_right],
            } for p in spline.bezier_points]
        else:
            row["points"] = [[_round(v) for v in p.co]
                             for p in spline.points]
        splines.append(row)
    return {"dimensions": curve.dimensions,
            "resolution_u": curve.resolution_u,
            "bevel_depth": _round(curve.bevel_depth),
            "bevel_resolution": curve.bevel_resolution,
            "splines": splines}


def _light_payload(light):
    result = {"light_type": light.type,
              "color": [_round(v) for v in light.color],
              "energy": _round(light.energy),
              "use_shadow": bool(light.use_shadow)}
    for key in ("shadow_soft_size", "size", "size_y", "spread",
                "spot_size", "spot_blend"):
        if hasattr(light, key):
            try:
                result[key] = _simple(getattr(light, key))
            except Exception:
                pass
    return result


def _object_payload(ob):
    data = None
    if ob.type == "MESH":
        data = _mesh_payload(ob.data)
    elif ob.type == "CURVE":
        data = _curve_payload(ob.data)
    elif ob.type == "LIGHT":
        data = _light_payload(ob.data)
    result = {
        "name": ob.name,
        "type": ob.type,
        "matrix_world": [_round(v) for row in ob.matrix_world for v in row],
        "hide_render": bool(ob.hide_render),
        "materials": [slot.material.name if slot.material else None
                      for slot in ob.material_slots],
        "modifiers": [_modifier_payload(m) for m in ob.modifiers],
        "custom_properties": _custom_props(ob),
        "data": data,
    }
    return result


def _socket_value(socket):
    if not hasattr(socket, "default_value"):
        return None
    try:
        return _simple(socket.default_value)
    except Exception:
        return None


def _node_tree_payload(tree):
    if tree is None:
        return None
    nodes = []
    assets = {}
    for node in sorted(tree.nodes, key=lambda n: n.name):
        row = {"name": node.name, "type": node.bl_idname,
               "mute": bool(node.mute),
               "inputs": [{"identifier": socket.identifier,
                            "value": _socket_value(socket)}
                           for socket in node.inputs if not socket.is_linked]}
        if hasattr(node, "image") and node.image is not None:
            path = bpy.path.abspath(node.image.filepath)
            row["image"] = os.path.realpath(path) if path else node.image.name
            if path and os.path.isfile(path):
                with open(path, "rb") as handle:
                    assets[os.path.relpath(path, C.ROOT)] = hashlib.sha256(
                        handle.read()).hexdigest()
        nodes.append(row)
    links = sorted((link.from_node.name, link.from_socket.identifier,
                    link.to_node.name, link.to_socket.identifier)
                   for link in tree.links)
    return {"nodes": nodes, "links": links, "assets": assets}


def _material_payload(material):
    return {"name": material.name,
            "use_nodes": material.node_tree is not None,
            "custom_properties": _custom_props(material),
            "node_tree": _node_tree_payload(material.node_tree)}


def _environment_objects():
    objects = {}
    for collection_name in LOCK_COLLECTIONS:
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            raise RuntimeError("missing lock collection: " + collection_name)
        for ob in collection.all_objects:
            objects[ob.name] = ob
    lights = bpy.data.collections.get("07_LIGHTS")
    if lights is None:
        raise RuntimeError("missing light collection: 07_LIGHTS")
    for ob in lights.all_objects:
        if not ob.name.startswith("LGT_Pool_"):
            objects[ob.name] = ob
    return [objects[name] for name in sorted(objects)]


def _scene_payload():
    scene = bpy.context.scene
    view = scene.view_settings
    result = {
        "render_engine": scene.render.engine,
        "view_transform": view.view_transform,
        "look": view.look,
        "exposure": _round(view.exposure),
        "gamma": _round(view.gamma),
        "world_color": [_round(v) for v in scene.world.color]
        if scene.world else None,
        "world_nodes": _node_tree_payload(scene.world.node_tree)
        if scene.world and scene.world.node_tree is not None else None,
    }
    return result


def snapshot():
    objects = _environment_objects()
    object_rows = {}
    materials = {}
    material_users = set()
    for ob in objects:
        payload = _object_payload(ob)
        object_rows[ob.name] = {
            "sha256": _sha(payload), "type": ob.type,
            "collection": sorted(c.name for c in ob.users_collection)[0],
        }
        for slot in ob.material_slots:
            if slot.material:
                material_users.add(slot.material.name)
    assets = {}
    for name in sorted(material_users):
        material = bpy.data.materials.get(name)
        payload = _material_payload(material)
        materials[name] = _sha(payload)
        node_assets = (payload.get("node_tree") or {}).get("assets", {})
        assets.update(node_assets)
    scene_payload = _scene_payload()
    world_assets = (scene_payload.get("world_nodes") or {}).get("assets", {})
    assets.update(world_assets)
    core = {"objects": object_rows, "materials": materials,
            "assets": dict(sorted(assets.items())),
            "scene_sha256": _sha(scene_payload)}
    core["aggregate_sha256"] = _sha(core)
    return core


def apply_guards(lock_id):
    """Make core environment collections unselectable in the saved master."""
    for name in LOCK_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            collection.hide_select = True
            collection["environment_lock_id"] = lock_id
            collection["environment_lock_scope"] = "geometry_materials_transforms"


def _differences(old, new):
    result = {}
    for section in ("objects", "materials", "assets"):
        before, after = old.get(section, {}), new.get(section, {})
        result[section] = {
            "added": sorted(set(after) - set(before)),
            "removed": sorted(set(before) - set(after)),
            "changed": sorted(k for k in set(before) & set(after)
                              if before[k] != after[k]),
        }
    result["scene_changed"] = old.get("scene_sha256") != new.get(
        "scene_sha256")
    return result


def run(write=False, output=None):
    output = output or REPORT
    current = snapshot()
    if write:
        report = {
            "version": LOCK_VERSION,
            "status": "LOCKED_BASELINE",
            "scope": {
                "locked_collections": list(LOCK_COLLECTIONS),
                "locked_lights": "07_LIGHTS except LGT_Pool_*",
                "locked_scene_state": "render engine, colour management, world",
                "intentionally_excluded": [
                    "02_TABLE_VISIBLE", "03_TABLE_ENGINEERING",
                    "05_HERO_PROPS", "LGT_Pool_*", "08_CAMERAS",
                    "09_ATMOSPHERE", "99_REFERENCE_LOCKED",
                ],
            },
            "summary": {
                "object_count": len(current["objects"]),
                "material_count": len(current["materials"]),
                "asset_count": len(current["assets"]),
                "aggregate_sha256": current["aggregate_sha256"],
            },
            "snapshot": current,
        }
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        apply_guards(current["aggregate_sha256"])
        if bpy.data.filepath:
            bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
        print("  [environment lock] BASELINE WRITTEN %d objects, %d materials, "
              "%d assets" % (len(current["objects"]),
                              len(current["materials"]),
                              len(current["assets"])))
        print("  [environment lock] %s" % current["aggregate_sha256"])
        return True

    if not os.path.exists(output):
        print("  [environment lock] FAIL missing baseline: " + output)
        return False
    with open(output, "r", encoding="utf-8") as handle:
        baseline = json.load(handle)
    old = baseline.get("snapshot", {})
    ok = (baseline.get("version") == LOCK_VERSION and
          old.get("aggregate_sha256") == current.get("aggregate_sha256"))
    if ok:
        apply_guards(current["aggregate_sha256"])
        print("  [environment lock] PASS %d objects unchanged (%s)" %
              (len(current["objects"]), current["aggregate_sha256"][:16]))
        return True
    differences = _differences(old, current)
    print("  [environment lock] FAIL environment drift detected")
    print(json.dumps(differences, indent=2))
    return False


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sys.exit(0 if run(write="--write" in args) else 1)
