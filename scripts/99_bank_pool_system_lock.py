"""Bank or verify the physical pool-system candidate without editing Blender.

The lock covers the authored table, engineering, hero-ball and physics-proxy
collections; their transforms, raw mesh/curve data, modifiers and material
assignments; the material graphs and image assets those objects use; the pool
builder/validator sources; the shared pooltool geometry contract; the approved
environment-lock identity; and the current dimensional-audit report.

Running without arguments verifies ``reports/pool_system_lock.json`` and exits
nonzero on drift.  Passing ``--write`` is the only operation that writes a
file.  This script never changes scene data and never saves the open blend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

import bpy


HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)

import config as C  # noqa: E402
import pool_geometry_contract as G  # noqa: E402


LOCK_VERSION = 1
LOCK_COLLECTIONS = (
    "02_TABLE_VISIBLE",
    "03_TABLE_ENGINEERING",
    "05_HERO_PROPS",
    "10_PHYSICS_PROXIES",
)
SOURCE_FILES = (
    "assets/data/table_wpa_geometry.json",
    "scripts/config.py",
    "scripts/lib.py",
    "scripts/pool_geometry_contract.py",
    "scripts/20_build_pool_table.py",
    "scripts/22_build_balls_and_rack.py",
    "scripts/23_rebuild_pool_system.py",
    "scripts/40_build_materials.py",
    "scripts/90_validate_scene.py",
    "scripts/91_validate_pool_geometry_contract.py",
    "scripts/99_bank_pool_system_lock.py",
)
ENVIRONMENT_LOCK = os.path.join(C.ROOT, "reports", "environment_lock.json")
DIMENSION_AUDIT = os.path.join(C.ROOT, "reports", "dimension_audit.json")
REPORT = os.path.join(C.ROOT, "reports", "pool_system_lock.json")


def _round(value):
    return round(float(value), 9)


def _simple(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value in lock payload")
        return _round(value)
    if hasattr(value, "to_dict"):
        try:
            return {
                str(key): _simple(item)
                for key, item in sorted(value.to_dict().items())
            }
        except Exception:
            pass
    if hasattr(value, "keys") and not isinstance(value, str):
        try:
            return {
                str(key): _simple(value[key]) for key in sorted(value.keys())
            }
        except Exception:
            pass
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [_simple(item) for item in value]
        except Exception:
            pass
    return str(value)


def _canonical_sha(payload):
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path):
    real = os.path.realpath(path)
    root = os.path.realpath(C.ROOT)
    if os.path.commonpath((root, real)) == root:
        return os.path.relpath(real, root).replace(os.sep, "/")
    return real


def _read_json(path, label):
    if not os.path.isfile(path):
        raise RuntimeError("missing %s: %s" % (label, path))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as error:
        raise RuntimeError("invalid %s: %s" % (label, error)) from error
    if not isinstance(payload, dict):
        raise RuntimeError("%s root must be a JSON object" % label)
    return payload


def _custom_props(owner):
    return {
        str(key): _simple(owner[key])
        for key in sorted(owner.keys())
        if key != "_RNA_UI"
    }


def _vertex_groups_payload(ob):
    if ob.type != "MESH" or not ob.vertex_groups:
        return {}
    names = {group.index: group.name for group in ob.vertex_groups}
    result = {name: [] for name in sorted(names.values())}
    for vertex in ob.data.vertices:
        for assignment in sorted(vertex.groups, key=lambda row: row.group):
            name = names.get(assignment.group)
            if name is not None:
                result[name].append([vertex.index, _round(assignment.weight)])
    return result


def _mesh_payload(mesh):
    color_attributes = {}
    for attribute in getattr(mesh, "color_attributes", ()):
        values = []
        for item in attribute.data:
            if hasattr(item, "color_srgb"):
                values.append([_round(value) for value in item.color_srgb])
            elif hasattr(item, "color"):
                values.append([_round(value) for value in item.color])
            elif hasattr(item, "value"):
                values.append(_simple(item.value))
            elif hasattr(item, "vector"):
                values.append([_round(value) for value in item.vector])
        color_attributes[attribute.name] = {
            "domain": attribute.domain,
            "data_type": attribute.data_type,
            "values": values,
        }
    return {
        "custom_properties": _custom_props(mesh),
        "vertices": [[_round(value) for value in vertex.co]
                     for vertex in mesh.vertices],
        "edges": [{
            "vertices": list(edge.vertices),
            "seam": bool(getattr(edge, "use_seam", False)),
            "sharp": bool(getattr(edge, "use_edge_sharp", False)),
        } for edge in mesh.edges],
        "polygons": [{
            "vertices": list(polygon.vertices),
            "material_index": int(polygon.material_index),
            "smooth": bool(polygon.use_smooth),
        } for polygon in mesh.polygons],
        "uv_layers": {
            layer.name: [[_round(value) for value in loop.uv]
                         for loop in layer.data]
            for layer in mesh.uv_layers
        },
        "color_attributes": color_attributes,
    }


def _curve_payload(curve):
    splines = []
    for spline in curve.splines:
        row = {
            "type": spline.type,
            "cyclic_u": bool(spline.use_cyclic_u),
            "cyclic_v": bool(spline.use_cyclic_v),
            "resolution_u": int(spline.resolution_u),
            "order_u": int(spline.order_u),
            "points": [],
        }
        if spline.type == "BEZIER":
            row["points"] = [{
                "co": [_round(value) for value in point.co],
                "left": [_round(value) for value in point.handle_left],
                "right": [_round(value) for value in point.handle_right],
                "left_type": point.handle_left_type,
                "right_type": point.handle_right_type,
                "radius": _round(point.radius),
                "tilt": _round(point.tilt),
            } for point in spline.bezier_points]
        else:
            row["points"] = [{
                "co": [_round(value) for value in point.co],
                "radius": _round(point.radius),
                "tilt": _round(point.tilt),
                "weight_softbody": _round(point.weight_softbody),
            } for point in spline.points]
        splines.append(row)
    return {
        "custom_properties": _custom_props(curve),
        "dimensions": curve.dimensions,
        "resolution_u": int(curve.resolution_u),
        "render_resolution_u": int(curve.render_resolution_u),
        "bevel_depth": _round(curve.bevel_depth),
        "bevel_resolution": int(curve.bevel_resolution),
        "resolution_v": int(curve.resolution_v),
        "splines": splines,
    }


def _modifier_payload(modifier):
    result = {
        "name": modifier.name,
        "type": modifier.type,
        "show_render": bool(modifier.show_render),
        "show_viewport": bool(modifier.show_viewport),
    }
    keys = (
        "affect", "angle_limit", "boundary_smooth", "levels",
        "limit_method", "merge_threshold", "offset", "operation",
        "render_levels", "segments", "solver", "thickness",
        "use_clamp_overlap", "use_even_offset", "use_merge_vertices",
        "use_rim", "use_rim_only", "vertex_group", "width",
    )
    for key in keys:
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


def _constraint_payload(constraint):
    result = {
        "name": constraint.name,
        "type": constraint.type,
        "influence": _round(constraint.influence),
        "mute": bool(constraint.mute),
    }
    for key in ("track_axis", "up_axis", "owner_space", "target_space"):
        if hasattr(constraint, key):
            result[key] = _simple(getattr(constraint, key))
    if hasattr(constraint, "target") and constraint.target is not None:
        result["target"] = constraint.target.name
    return result


def _object_payload(ob):
    data = None
    if ob.type == "MESH":
        data = _mesh_payload(ob.data)
    elif ob.type == "CURVE":
        data = _curve_payload(ob.data)
    return {
        "name": ob.name,
        "type": ob.type,
        "collections": sorted(collection.name
                              for collection in ob.users_collection),
        "parent": ob.parent.name if ob.parent else None,
        "parent_type": ob.parent_type,
        "matrix_parent_inverse": [
            _round(value) for row in ob.matrix_parent_inverse for value in row
        ],
        "matrix_world": [
            _round(value) for row in ob.matrix_world for value in row
        ],
        "location": [_round(value) for value in ob.location],
        "rotation_mode": ob.rotation_mode,
        "rotation_euler": [_round(value) for value in ob.rotation_euler],
        "rotation_quaternion": [
            _round(value) for value in ob.rotation_quaternion
        ],
        "scale": [_round(value) for value in ob.scale],
        "hide_render": bool(ob.hide_render),
        "hide_viewport": bool(ob.hide_viewport),
        "materials": [
            slot.material.name if slot.material else None
            for slot in ob.material_slots
        ],
        "vertex_groups": _vertex_groups_payload(ob),
        "modifiers": [_modifier_payload(modifier)
                      for modifier in ob.modifiers],
        "constraints": [_constraint_payload(constraint)
                        for constraint in ob.constraints],
        "custom_properties": _custom_props(ob),
        "data": data,
    }


def _socket_value(socket):
    if not hasattr(socket, "default_value"):
        return None
    try:
        return _simple(socket.default_value)
    except Exception:
        return None


def _node_tree_payload(tree):
    if tree is None:
        return None, {}
    nodes = []
    assets = {}
    for node in sorted(tree.nodes, key=lambda item: item.name):
        row = {
            "name": node.name,
            "type": node.bl_idname,
            "mute": bool(node.mute),
            "inputs": [{
                "identifier": socket.identifier,
                "value": _socket_value(socket),
            } for socket in node.inputs if not socket.is_linked],
        }
        for key in (
                "blend_type", "data_type", "extension", "interpolation",
                "operation", "projection", "space", "vector_type"):
            if hasattr(node, key):
                try:
                    row[key] = _simple(getattr(node, key))
                except Exception:
                    pass
        if hasattr(node, "node_tree") and node.node_tree is not None:
            row["node_tree"] = node.node_tree.name
        if hasattr(node, "image") and node.image is not None:
            image = node.image
            path = bpy.path.abspath(image.filepath)
            image_row = {
                "name": image.name,
                "source": image.source,
                "filepath": _relative(path) if path else "",
            }
            if path and os.path.isfile(path):
                relative = _relative(path)
                digest = _file_sha(path)
                image_row["sha256"] = digest
                assets[relative] = digest
            row["image"] = image_row
        nodes.append(row)
    links = sorted(
        (link.from_node.name, link.from_socket.identifier,
         link.to_node.name, link.to_socket.identifier)
        for link in tree.links
    )
    return {
        "custom_properties": _custom_props(tree),
        "nodes": nodes,
        "links": links,
    }, assets


def _material_payload(material):
    node_tree, assets = _node_tree_payload(material.node_tree)
    payload = {
        "name": material.name,
        "use_nodes": bool(material.use_nodes),
        "diffuse_color": [_round(value) for value in material.diffuse_color],
        "metallic": _round(material.metallic),
        "roughness": _round(material.roughness),
        "custom_properties": _custom_props(material),
        "node_tree": node_tree,
    }
    return payload, assets


def _pool_objects():
    objects = {}
    membership = {}
    for collection_name in LOCK_COLLECTIONS:
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            raise RuntimeError("missing pool lock collection: " +
                               collection_name)
        names = set()
        for ob in collection.all_objects:
            existing = objects.get(ob.name)
            if existing is not None and existing != ob:
                raise RuntimeError("duplicate pool object name: " + ob.name)
            objects[ob.name] = ob
            names.add(ob.name)
        membership[collection_name] = sorted(names)
    if not objects:
        raise RuntimeError("pool lock scope contains no objects")
    return [objects[name] for name in sorted(objects)], membership


def _source_hashes():
    result = {}
    for relative in SOURCE_FILES:
        path = os.path.join(C.ROOT, *relative.split("/"))
        if not os.path.isfile(path):
            raise RuntimeError("missing pool source file: " + relative)
        result[relative] = _file_sha(path)
    return result


def _environment_reference():
    report = _read_json(ENVIRONMENT_LOCK, "environment lock")
    aggregate = (report.get("summary", {}).get("aggregate_sha256") or
                 report.get("snapshot", {}).get("aggregate_sha256"))
    if not isinstance(aggregate, str) or len(aggregate) != 64:
        raise RuntimeError("environment lock has no aggregate SHA-256")
    return {
        "path": _relative(ENVIRONMENT_LOCK),
        "version": report.get("version"),
        "aggregate_sha256": aggregate,
        "report_sha256": _canonical_sha(report),
    }


def _dimension_audit_reference():
    report = _read_json(DIMENSION_AUDIT, "dimension audit")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("dimension audit has no summary")
    required_failures = int(summary.get("required_failures", -1))
    if required_failures != 0:
        raise RuntimeError(
            "dimension audit has %d required failures" % required_failures)
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("dimension audit has no checks")
    stable_report = dict(report)
    # The validator records a human-readable run date.  It is evidence, not
    # pool geometry, and must not make an unchanged candidate drift tomorrow.
    stable_report.pop("generated", None)
    return {
        "path": _relative(DIMENSION_AUDIT),
        "sha256": _canonical_sha(stable_report),
        "generated": report.get("generated"),
        "engine": report.get("engine"),
        "resolution": _simple(report.get("resolution")),
        "summary": _simple(summary),
        "failed_required_checks": sorted(
            str(row.get("check")) for row in checks
            if row.get("required") and row.get("status") != "PASS"
        ),
    }


def _geometry_contract_reference():
    path = os.path.realpath(G.DATA_PATH)
    if not os.path.isfile(path):
        raise RuntimeError("missing shared geometry contract: " + path)
    validation = G.validate_geometry()
    G.validate_against_config(C)
    return {
        "path": _relative(path),
        "sha256": _file_sha(path),
        "validation_sha256": _canonical_sha(validation),
        "feature_counts": _simple(validation.get("feature_counts")),
    }


def _counts(objects, membership, material_names, assets, source_files):
    type_counts = {}
    vertices = edges = polygons = splines = curve_points = 0
    material_slots = 0
    for ob in objects:
        type_counts[ob.type] = type_counts.get(ob.type, 0) + 1
        material_slots += len(ob.material_slots)
        if ob.type == "MESH":
            vertices += len(ob.data.vertices)
            edges += len(ob.data.edges)
            polygons += len(ob.data.polygons)
        elif ob.type == "CURVE":
            splines += len(ob.data.splines)
            for spline in ob.data.splines:
                curve_points += (len(spline.bezier_points)
                                 if spline.type == "BEZIER"
                                 else len(spline.points))
    return {
        "objects": len(objects),
        "objects_by_collection": {
            name: len(membership[name]) for name in LOCK_COLLECTIONS
        },
        "objects_by_type": dict(sorted(type_counts.items())),
        "mesh_vertices": vertices,
        "mesh_edges": edges,
        "mesh_polygons": polygons,
        "curve_splines": splines,
        "curve_points": curve_points,
        "material_slots": material_slots,
        "materials": len(material_names),
        "material_assets": len(assets),
        "source_files": len(source_files),
    }


def snapshot():
    objects, membership = _pool_objects()
    object_rows = {}
    material_names = set()
    for ob in objects:
        payload = _object_payload(ob)
        object_rows[ob.name] = {
            "sha256": _canonical_sha(payload),
            "type": ob.type,
            "collections": sorted(
                name for name, members in membership.items()
                if ob.name in members
            ),
            "vertex_count": len(ob.data.vertices)
            if ob.type == "MESH" else 0,
            "polygon_count": len(ob.data.polygons)
            if ob.type == "MESH" else 0,
            "spline_count": len(ob.data.splines)
            if ob.type == "CURVE" else 0,
        }
        for slot in ob.material_slots:
            if slot.material is not None:
                material_names.add(slot.material.name)

    materials = {}
    assets = {}
    for name in sorted(material_names):
        material = bpy.data.materials.get(name)
        if material is None:
            raise RuntimeError("missing assigned material: " + name)
        payload, material_assets = _material_payload(material)
        materials[name] = _canonical_sha(payload)
        assets.update(material_assets)

    sources = _source_hashes()
    environment = _environment_reference()
    dimensions = _dimension_audit_reference()
    geometry = _geometry_contract_reference()
    counts = _counts(objects, membership, material_names, assets, sources)
    core = {
        "source_files": sources,
        "geometry_contract": geometry,
        "environment_lock": environment,
        "dimension_audit": dimensions,
        "collection_membership": membership,
        "objects": object_rows,
        "materials": materials,
        "assets": dict(sorted(assets.items())),
        "counts": counts,
    }
    core["aggregate_sha256"] = _canonical_sha(core)
    return core


def _mapping_difference(before, after):
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(
            key for key in set(before) & set(after)
            if before[key] != after[key]
        ),
    }


def _differences(old, new):
    result = {}
    for section in (
            "source_files", "objects", "materials", "assets",
            "collection_membership"):
        result[section] = _mapping_difference(
            old.get(section, {}), new.get(section, {}))
    for section in (
            "geometry_contract", "environment_lock", "dimension_audit",
            "counts"):
        result[section + "_changed"] = (
            old.get(section) != new.get(section))
    return result


def _report(current):
    return {
        "version": LOCK_VERSION,
        "status": "LOCKED_BASELINE",
        "scope": {
            "locked_collections": list(LOCK_COLLECTIONS),
            "locked_data": [
                "object transforms and custom properties",
                "raw mesh, curve and vertex-group data",
                "modifiers and constraints",
                "material assignments and material graphs",
                "referenced material image assets",
                "pool source files and shared geometry contract",
                "environment-lock identity and dimensional audit",
            ],
            "intentionally_excluded": [
                "environment collections already covered by environment_lock",
                "pool and room lights",
                "cameras and render settings",
                "atmosphere and reference collections",
                "evaluated meshes and render output",
            ],
        },
        "summary": {
            **current["counts"],
            "aggregate_sha256": current["aggregate_sha256"],
            "environment_lock_sha256": current[
                "environment_lock"]["aggregate_sha256"],
            "dimension_audit_sha256": current[
                "dimension_audit"]["sha256"],
            "geometry_contract_sha256": current[
                "geometry_contract"]["sha256"],
        },
        "snapshot": current,
    }


def run(write=False):
    try:
        current = snapshot()
    except Exception as error:
        print("  [pool system lock] FAIL " + str(error))
        return False

    if write:
        report = _report(current)
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True,
                      ensure_ascii=True, allow_nan=False)
            handle.write("\n")
        print("  [pool system lock] BASELINE WRITTEN %d objects, %d materials" %
              (current["counts"]["objects"],
               current["counts"]["materials"]))
        print("  [pool system lock] " + current["aggregate_sha256"])
        return True

    if not os.path.isfile(REPORT):
        print("  [pool system lock] FAIL missing baseline: " + REPORT)
        return False
    try:
        baseline = _read_json(REPORT, "pool system lock")
    except RuntimeError as error:
        print("  [pool system lock] FAIL " + str(error))
        return False
    old = baseline.get("snapshot", {})
    ok = (
        baseline.get("version") == LOCK_VERSION and
        old.get("aggregate_sha256") == current.get("aggregate_sha256")
    )
    if ok:
        print("  [pool system lock] PASS %d objects unchanged (%s)" %
              (current["counts"]["objects"],
               current["aggregate_sha256"][:16]))
        return True

    print("  [pool system lock] FAIL pool-system drift detected")
    print(json.dumps(_differences(old, current), indent=2, sort_keys=True))
    return False


def _args(argv):
    parser = argparse.ArgumentParser(
        description="Write or verify the deterministic pool-system lock.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write reports/pool_system_lock.json instead of verifying it",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    cli = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    arguments = _args(cli)
    sys.exit(0 if run(write=arguments.write) else 1)
