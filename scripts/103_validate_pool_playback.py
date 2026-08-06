"""Validate the complete solver-to-Blender gameplay contract.

The trajectory JSON is the shot authority.  This audit independently hashes
that payload, verifies every referenced source asset, inspects Blender 5.2's
layered F-curves, and evaluates every exported solver sample in the scene.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import config as C  # noqa: E402
from trajectory_contract import (  # noqa: E402
    recompute_trajectory_sha256,
    verify_trajectory_sha256,
)


GAME = "11_GAMEPLAY"
VIEW_LAYER = "GAMEPLAY"
DEFAULT_SHOT = ROOT / "assets" / "data" / "shots" / "break_control.json"
DEFAULT_REPORT = ROOT / "reports" / "physics_playback_audit.json"
PROFILE_PATH = ROOT / "assets" / "data" / "pool_physics_profile.json"
GEOMETRY_PATH = ROOT / "assets" / "data" / "table_wpa_geometry.json"
MARKINGS_PATH = ROOT / "assets" / "data" / "game_ball_markings.json"

TRANSFORM_CHANNELS = {
    *(('location', index) for index in range(3)),
    *(('rotation_quaternion', index) for index in range(4)),
}
CUE_COMPONENT_NAMES = {
    "PT_GameCue_Tip",
    "PT_GameCue_Ferrule",
    "PT_GameCue_ShaftFront",
    "PT_GameCue_ShaftBack",
    "PT_GameCue_Joint",
    "PT_GameCue_Wrap",
    "PT_GameCue_Butt",
    "PT_GameCue_Bumper",
}


def parse_args():
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", type=Path, default=DEFAULT_SHOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(values)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def float32(value):
    """Return the exact value Blender stores in an F-curve point coordinate."""
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def close(actual, expected, tolerance=1e-12):
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


def pool_to_world(position):
    return Vector((
        float(position[0]) + C.TABLE_CENTRE[0] - C.PLAY_W * 0.5,
        float(position[1]) + C.TABLE_CENTRE[1] - C.PLAY_L * 0.5,
        float(position[2]) + C.BED_Z,
    ))


def expected_ball_parameters(profile):
    row = profile["ball"]
    gravity = float(row["gravity_mps2"])
    return {
        "m": float(row["mass_kg"]),
        "R": float(row["radius_m"]),
        "u_s": float(row["sliding_friction"]),
        "u_r": float(row["rolling_deceleration_mps2"]) / gravity,
        "u_sp_proportionality": (
            2.0 * float(row["sidespin_deceleration_rad_s2"])
            / (5.0 * gravity)
        ),
        "u_b": float(row["ball_ball_friction"]),
        "e_b": float(row["ball_ball_restitution"]),
        "e_c": float(row["cushion_restitution_parameter"]),
        "f_c": float(row["cushion_friction"]),
        "g": gravity,
    }


def marking_class(number):
    if number == 0:
        return "cue"
    return "solid" if number <= 8 else "stripe"


def layer_collection(root, name):
    if root.collection.name == name:
        return root
    for child in root.children:
        found = layer_collection(child, name)
        if found is not None:
            return found
    return None


def action_curves(obj):
    """Return the object's curves, preferring Blender 5.2 layered actions."""
    animation = obj.animation_data
    if animation is None or animation.action is None:
        return [], {"api": "missing", "layers": 0, "slots": 0, "bags": 0}
    action = animation.action
    curves = []
    bags = 0
    layer_count = len(action.layers) if hasattr(action, "layers") else 0
    slot_count = len(action.slots) if hasattr(action, "slots") else 0
    if layer_count and slot_count:
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        bag = strip.channelbag(slot)
                    except (AttributeError, RuntimeError, TypeError):
                        continue
                    if bag is None:
                        continue
                    bags += 1
                    curves.extend(list(bag.fcurves))
        if curves:
            # An action can expose a bag through more than one traversal path.
            curves = list({id(curve): curve for curve in curves}.values())
            return curves, {
                "api": "layered",
                "layers": layer_count,
                "slots": slot_count,
                "bags": bags,
            }
    if hasattr(action, "fcurves"):
        try:
            curves = list(action.fcurves)
        except (AttributeError, RuntimeError, TypeError):
            curves = []
    return curves, {
        "api": "legacy" if curves else "missing",
        "layers": layer_count,
        "slots": slot_count,
        "bags": bags,
    }


def set_scene_frame(scene, frame):
    integer = math.floor(float(frame))
    scene.frame_set(integer, subframe=float(frame) - integer)


def image_path(image):
    if image is None or not image.filepath:
        return None
    return Path(bpy.path.abspath(image.filepath)).resolve()


def cap_center(obj, direction, maximum):
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    projections = [point.dot(direction) for point in points]
    extreme = max(projections) if maximum else min(projections)
    selected = [
        point for point, projection in zip(points, projections)
        if abs(projection - extreme) <= 2e-6
    ]
    if not selected:
        raise ValueError("cue cap has no vertices")
    return sum(selected, Vector()) / len(selected)


def angle_difference_degrees(first, second):
    return abs((float(first) - float(second) + 180.0) % 360.0 - 180.0)


def main() -> int:
    args = parse_args()
    shot = load_json(args.shot)
    profile = load_json(PROFILE_PATH)
    geometry = load_json(GEOMETRY_PATH)
    markings = load_json(MARKINGS_PATH)
    scene = bpy.context.scene
    checks = []

    def check(name, condition, observed=None, expected=None):
        status = "PASS" if condition else "FAIL"
        row = {"id": name, "status": status, "observed": observed}
        if expected is not None:
            row["expected"] = expected
        checks.append(row)
        print("  [%s] %s" % (status, name))
        return condition

    # Identity is recomputed from authoritative payload fields.  Merely
    # comparing two copied digest strings would let a modified trajectory pass.
    trajectory_error = None
    try:
        recomputed_trajectory = recompute_trajectory_sha256(shot)
        verify_trajectory_sha256(shot)
    except (TypeError, ValueError) as exc:
        recomputed_trajectory = None
        trajectory_error = str(exc)
    stored_trajectory = shot.get("trajectory_sha256")
    profile_hash = sha256(PROFILE_PATH)
    geometry_hash = sha256(GEOMETRY_PATH)
    markings_hash = sha256(MARKINGS_PATH)
    check(
        "trajectory_payload_identity",
        trajectory_error is None and recomputed_trajectory == stored_trajectory,
        {
            "stored": stored_trajectory,
            "recomputed": recomputed_trajectory,
            "error": trajectory_error,
        },
    )
    check(
        "scene_trajectory_identity",
        trajectory_error is None
        and scene.get("trajectory_sha256") == recomputed_trajectory,
        scene.get("trajectory_sha256"),
        recomputed_trajectory,
    )
    check(
        "profile_file_identity",
        shot.get("profile_sha256") == profile_hash,
        {"trajectory": shot.get("profile_sha256"), "file": profile_hash},
    )
    check(
        "scene_profile_identity",
        scene.get("physics_profile_sha256") == profile_hash,
        scene.get("physics_profile_sha256"),
        profile_hash,
    )
    check(
        "geometry_file_identity",
        shot.get("geometry_contract_sha256") == geometry_hash,
        {
            "trajectory": shot.get("geometry_contract_sha256"),
            "file": geometry_hash,
        },
    )
    check(
        "scene_geometry_identity",
        scene.get("geometry_contract_sha256") == geometry_hash,
        scene.get("geometry_contract_sha256"),
        geometry_hash,
    )
    check(
        "asset_schemas",
        shot.get("schema") == "pool-shot-trajectory/v1"
        and profile.get("schema") == "pool-physics-profile/v1"
        and markings.get("schema") == "pool-ball-markings/v1",
        {
            "trajectory": shot.get("schema"),
            "profile": profile.get("schema"),
            "markings": markings.get("schema"),
        },
    )

    expected_parameters = expected_ball_parameters(profile)
    actual_parameters = shot.get("ball_parameters", {})
    parameter_errors = {
        key: abs(float(actual_parameters.get(key, math.inf)) - value)
        for key, value in expected_parameters.items()
    }
    check(
        "trajectory_ball_parameter_formulas",
        set(actual_parameters) == set(expected_parameters)
        and all(error <= 1e-12 for error in parameter_errors.values()),
        {"actual": actual_parameters, "absolute_errors": parameter_errors},
        expected_parameters,
    )
    check(
        "trajectory_sample_rate_contract",
        int(shot.get("sample_rate_hz", -1))
        == int(profile["solver"]["sample_rate_hz"])
        == int(scene.get("solver_sample_rate_hz", -2)),
        {
            "trajectory_hz": shot.get("sample_rate_hz"),
            "profile_hz": profile["solver"]["sample_rate_hz"],
            "scene_hz": scene.get("solver_sample_rate_hz"),
        },
    )
    check(
        "geometry_profile_and_scene_mapping",
        close(geometry.get("w"), C.PLAY_W)
        and close(geometry.get("l"), C.PLAY_L)
        and close(geometry.get("bed"), C.BED_Z)
        and close(geometry.get("ball_R"), profile["ball"]["radius_m"])
        and close(geometry.get("ball_R"), C.BALL_R)
        and close(geometry.get("nose"), C.CUSHION_NOSE),
        {
            "geometry_w_l_bed_radius_nose": [
                geometry.get("w"), geometry.get("l"), geometry.get("bed"),
                geometry.get("ball_R"), geometry.get("nose"),
            ],
            "scene_w_l_bed_radius_nose": [
                C.PLAY_W, C.PLAY_L, C.BED_Z, C.BALL_R, C.CUSHION_NOSE,
            ],
        },
    )

    effective_fps = float(scene.render.fps) / float(scene.render.fps_base)
    expected_fps = float(profile["playback"]["fps"])
    expected_frame_end = math.ceil(
        float(profile["playback"]["impact_frame"])
        + float(shot["duration_s"]) * expected_fps
    ) + 1
    check(
        "scene_fps_and_timebase",
        scene.render.fps == int(expected_fps)
        and close(scene.render.fps_base, 1.0, 1e-12)
        and close(effective_fps, expected_fps, 1e-12),
        {
            "fps": scene.render.fps,
            "fps_base": scene.render.fps_base,
            "effective_fps": effective_fps,
        },
        {"fps": int(expected_fps), "fps_base": 1.0},
    )
    check(
        "scene_playback_range",
        scene.frame_start == 1 and scene.frame_end == expected_frame_end,
        {"frame_start": scene.frame_start, "frame_end": scene.frame_end},
        {"frame_start": 1, "frame_end": expected_frame_end},
    )

    game = bpy.data.collections.get(GAME)
    check(
        "gameplay_collection",
        game is not None and scene.get("gameplay_collection") == GAME,
        {"collection": GAME if game else None,
         "scene_property": scene.get("gameplay_collection")},
    )
    rigid_bodies = [obj.name for obj in bpy.data.objects if obj.rigid_body is not None]
    check("zero_blender_rigid_bodies", not rigid_bodies, rigid_bodies)
    check(
        "intentional_zero_body_authority",
        bool(scene.get("zero_blender_rigid_bodies_intentional"))
        and scene.get("physics_authority") == "Pooltool 0.6.0 event solver",
        {
            "intentional": scene.get("zero_blender_rigid_bodies_intentional"),
            "authority": scene.get("physics_authority"),
        },
    )

    balls = {}
    for ball_id, row in shot["balls"].items():
        number = int(row["number"])
        name = "PT_GameBall_Cue" if number == 0 else "PT_GameBall_%02d" % number
        balls[ball_id] = bpy.data.objects.get(name)
    check(
        "sixteen_gameplay_balls",
        len(balls) == 16
        and all(ball is not None for ball in balls.values())
        and len({ball.name for ball in balls.values() if ball is not None}) == 16
        and int(scene.get("gameplay_ball_count", -1)) == 16,
        sorted(ball.name for ball in balls.values() if ball is not None),
    )

    impact = float(profile["playback"]["impact_frame"])
    expected_transform_frames = [1.0, impact] + [
        impact + float(sample["t"]) * expected_fps
        for sample in next(iter(shot["balls"].values()))["samples"][1:]
    ]
    expected_transform_frames_f32 = [float32(frame) for frame in expected_transform_frames]
    animation_audit = {}
    ball_asset_audit = {}
    scene.frame_set(1)

    for ball_id, ball in balls.items():
        trajectory = shot["balls"][ball_id]
        number = int(trajectory["number"])
        label = "cue" if number == 0 else "%02d" % number
        expected_name = "PT_GameBall_Cue" if number == 0 else "PT_GameBall_%02d" % number
        if ball is None:
            check("ball_%s_object_exists" % label, False, None, expected_name)
            continue
        check(
            "ball_%s_object_exists" % label,
            ball.name == expected_name and game is not None and ball.name in game.objects,
            {"name": ball.name, "collections": [col.name for col in ball.users_collection]},
            expected_name,
        )

        radius = float(actual_parameters["R"])
        diameter = radius * 2.0
        dimensions = [float(value) for value in ball.dimensions]
        scale = [float(value) for value in ball.scale]
        world_scale = [float(value) for value in ball.matrix_world.to_scale()]
        vertex_radius_error = math.inf
        if ball.type == "MESH" and ball.data.vertices:
            vertex_radius_error = max(
                abs(float(vertex.co.length) - radius)
                for vertex in ball.data.vertices
            )
        geometry_observed = {
            "type": ball.type,
            "dimensions_m": dimensions,
            "scale": scale,
            "world_scale": world_scale,
            "max_local_vertex_radius_error_m": vertex_radius_error,
            "modifiers": [modifier.name for modifier in ball.modifiers],
            "parent": ball.parent.name if ball.parent else None,
        }
        check(
            "ball_%s_actual_geometry" % label,
            ball.type == "MESH"
            and all(abs(value - diameter) <= 5e-6 for value in dimensions)
            and all(abs(value - 1.0) <= 1e-9 for value in scale)
            # Blender derives matrix scale from Float32 quaternion channels;
            # a unit object can therefore read a few 1e-7 away from one.
            and all(abs(abs(value) - 1.0) <= 1e-6 for value in world_scale)
            and vertex_radius_error <= 1e-7
            and len(ball.modifiers) == 0
            and ball.parent is None,
            geometry_observed,
            {"diameter_m": diameter, "scale": [1.0, 1.0, 1.0]},
        )

        inertia = 0.4 * float(actual_parameters["m"]) * radius * radius
        expected_metadata = {
            "ball_id": str(ball_id),
            "ball_number": number,
            "diameter_m": diameter,
            "mass_kg": float(actual_parameters["m"]),
            "solid_sphere_inertia_kg_m2": inertia,
            "sliding_friction": float(actual_parameters["u_s"]),
            "rolling_friction": float(actual_parameters["u_r"]),
            "spinning_friction": float(actual_parameters["u_sp_proportionality"]) * radius,
            "ball_ball_friction": float(actual_parameters["u_b"]),
            "ball_ball_restitution": float(actual_parameters["e_b"]),
            "cushion_restitution_parameter": float(actual_parameters["e_c"]),
            "cushion_friction": float(actual_parameters["f_c"]),
            "physics_authority": "pooltool 0.6.0 event trajectory",
            "blender_rigid_body_intentional": False,
            "pocket_id": trajectory.get("pocket_id") or "",
        }
        metadata_failures = []
        metadata_observed = {}
        for key, expected in expected_metadata.items():
            actual = ball.get(key)
            metadata_observed[key] = actual
            if isinstance(expected, float):
                valid = close(actual, expected, 1e-12)
            else:
                valid = actual == expected
            if not valid:
                metadata_failures.append(key)
        check(
            "ball_%s_physics_metadata" % label,
            not metadata_failures,
            {"failures": metadata_failures, "values": metadata_observed},
            expected_metadata,
        )

        filename = "ball_cue.png" if number == 0 else "ball_%02d.png" % number
        relative_texture = "assets/textures/balls_game/" + filename
        texture_path = ROOT / relative_texture
        record = markings.get("assets", {}).get(relative_texture)
        expected_marking = marking_class(number)
        marking_failures = []
        if record is None:
            marking_failures.append("manifest_record")
        else:
            record_expectations = {
                "number": number,
                "class": expected_marking,
                "width": 2048,
                "height": 1024,
                "opposed_number_circles": 0 if number == 0 else 2,
                "duplicate_number_inverted": number != 0,
                "underscored": number in (6, 9),
            }
            for key, expected in record_expectations.items():
                if record.get(key) != expected:
                    marking_failures.append("manifest:" + key)
        ball_mark_expectations = {
            "decal_asset": relative_texture,
            "marking_class": expected_marking,
            "opposed_number_circles": 0 if number == 0 else 2,
            "duplicate_number_inverted": number != 0,
            "number_underscored": number in (6, 9),
        }
        for key, expected in ball_mark_expectations.items():
            if ball.get(key) != expected:
                marking_failures.append("object:" + key)
        check(
            "ball_%s_marking_metadata" % label,
            not marking_failures,
            {
                "failures": marking_failures,
                "manifest": record,
                "object": {key: ball.get(key) for key in ball_mark_expectations},
            },
        )

        actual_texture_hash = sha256(texture_path) if texture_path.exists() else None
        expected_texture_hash = record.get("sha256") if record else None
        check(
            "ball_%s_texture_file_integrity" % label,
            texture_path.is_file()
            and actual_texture_hash == expected_texture_hash
            and ball.get("decal_sha256") == expected_texture_hash,
            {
                "path": relative_texture,
                "file_sha256": actual_texture_hash,
                "manifest_sha256": expected_texture_hash,
                "object_sha256": ball.get("decal_sha256"),
            },
        )

        expected_material_name = (
            "MAT_GameBall_Cue" if number == 0 else "MAT_GameBall_%02d" % number
        )
        materials = list(ball.data.materials) if ball.type == "MESH" else []
        material = materials[0] if len(materials) == 1 else None
        image_nodes = []
        principled_nodes = []
        output_nodes = []
        base_links = []
        surface_links = []
        connected_image_path = None
        connected_image_size = None
        connected_colorspace = None
        if material is not None and material.use_nodes and material.node_tree:
            tree = material.node_tree
            image_nodes = [node for node in tree.nodes if node.type == "TEX_IMAGE"]
            principled_nodes = [node for node in tree.nodes if node.type == "BSDF_PRINCIPLED"]
            output_nodes = [node for node in tree.nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output]
            if len(image_nodes) == 1 and image_nodes[0].image is not None:
                connected_image_path = image_path(image_nodes[0].image)
                connected_image_size = [int(value) for value in image_nodes[0].image.size]
                connected_colorspace = image_nodes[0].image.colorspace_settings.name
            if len(principled_nodes) == 1:
                base_socket = principled_nodes[0].inputs.get("Base Color")
                base_links = [link for link in tree.links if link.to_socket == base_socket]
            if len(output_nodes) == 1:
                surface_socket = output_nodes[0].inputs.get("Surface")
                surface_links = [link for link in tree.links if link.to_socket == surface_socket]
        material_ok = (
            len(materials) == 1
            and material is not None
            and material.name == expected_material_name
            and material.get("texture_path") == relative_texture
            and len(image_nodes) == 1
            and connected_image_path == texture_path.resolve()
            and connected_image_size == [2048, 1024]
            and connected_colorspace == "sRGB"
            and len(principled_nodes) == 1
            and len(output_nodes) == 1
            and len(base_links) == 1
            and base_links[0].from_node == image_nodes[0]
            and base_links[0].from_socket == image_nodes[0].outputs.get("Color")
            and len(surface_links) == 1
            and surface_links[0].from_node == principled_nodes[0]
            and surface_links[0].from_socket == principled_nodes[0].outputs.get("BSDF")
        )
        check(
            "ball_%s_exact_material_image_connection" % label,
            material_ok,
            {
                "material_slots": [value.name for value in materials],
                "expected_material": expected_material_name,
                "material_texture_path": material.get("texture_path") if material else None,
                "image_node_count": len(image_nodes),
                "connected_image": (
                    str(connected_image_path) if connected_image_path else None
                ),
                "connected_image_size": connected_image_size,
                "colorspace": connected_colorspace,
                "base_color_link_count": len(base_links),
                "surface_link_count": len(surface_links),
            },
        )

        curves, curve_details = action_curves(ball)
        channel_pairs = [(curve.data_path, int(curve.array_index)) for curve in curves]
        channel_map = {
            (curve.data_path, int(curve.array_index)): curve for curve in curves
        }
        channel_ok = (
            curve_details["api"] == "layered"
            and len(curves) == 7
            and len(channel_map) == 7
            and set(channel_map) == TRANSFORM_CHANNELS
            and ball.rotation_mode == "QUATERNION"
        )
        check(
            "ball_%s_layered_transform_channels" % label,
            channel_ok,
            {
                **curve_details,
                "rotation_mode": ball.rotation_mode,
                "channels": [list(value) for value in sorted(channel_pairs)],
            },
            {"api": "layered", "channel_count": 7},
        )
        key_counts = {
            "%s[%d]" % key: len(curve.keyframe_points)
            for key, curve in channel_map.items()
        }
        max_key_time_error = 0.0
        key_time_failures = []
        interpolation_failures = []
        for key, curve in channel_map.items():
            points = list(curve.keyframe_points)
            if len(points) != len(expected_transform_frames_f32):
                key_time_failures.append("%s[%d]:count" % key)
            else:
                for index, (point, expected_frame) in enumerate(
                    zip(points, expected_transform_frames_f32)
                ):
                    error = abs(float(point.co.x) - expected_frame)
                    max_key_time_error = max(max_key_time_error, error)
                    if error > 1e-7:
                        key_time_failures.append(
                            "%s[%d]:frame-%d" % (key[0], key[1], index)
                        )
                        break
            if any(point.interpolation != "LINEAR" for point in points):
                interpolation_failures.append("%s[%d]" % key)
        check(
            "ball_%s_transform_key_count_and_times" % label,
            channel_ok and not key_time_failures,
            {
                "expected_keys_per_channel": len(expected_transform_frames_f32),
                "key_counts": key_counts,
                "max_frame_error": max_key_time_error,
                "failures": key_time_failures,
                "expected_first_last_frame": [
                    expected_transform_frames_f32[0],
                    expected_transform_frames_f32[-1],
                ],
            },
        )
        check(
            "ball_%s_linear_interpolation" % label,
            channel_ok and not interpolation_failures,
            interpolation_failures,
            "LINEAR on every transform key",
        )
        animation_audit[label] = {
            **curve_details,
            "channels": len(channel_map),
            "expected_keys_per_channel": len(expected_transform_frames_f32),
            "key_counts": key_counts,
            "max_frame_error": max_key_time_error,
        }
        ball_asset_audit[label] = {
            "geometry": geometry_observed,
            "texture": relative_texture,
            "texture_sha256": actual_texture_hash,
            "material": material.name if material else None,
        }

    # The legal rack is proven from its ordered numbers and coordinates, not
    # from convenience booleans stored on the decorative rack object.
    rack = shot.get("rack", {})
    rack_order = rack.get("order", [])
    profile_order = profile["rack"]["order"]
    flat_order = [int(number) for row in rack_order for number in row]
    row_shape = [len(row) for row in rack_order]
    check(
        "rack_order_and_shape",
        rack_order == profile_order
        and row_shape == [1, 2, 3, 4, 5]
        and sorted(flat_order) == list(range(1, 16)),
        {"order": rack_order, "row_shape": row_shape, "flat": flat_order},
        profile_order,
    )
    eight_location = [
        [row_index, column]
        for row_index, row in enumerate(rack_order)
        for column, number in enumerate(row)
        if int(number) == 8
    ]
    check(
        "rack_eight_ball_actual_center",
        eight_location == [[2, 1]],
        eight_location,
        [[2, 1]],
    )
    rear_corners = []
    if len(rack_order) == 5 and len(rack_order[-1]) == 5:
        rear_corners = [int(rack_order[-1][0]), int(rack_order[-1][-1])]
    rear_classes = [marking_class(number) for number in rear_corners]
    check(
        "rack_actual_rear_corner_classes",
        sorted(rear_classes) == ["solid", "stripe"],
        {"numbers": rear_corners, "classes": rear_classes},
        ["solid", "stripe"],
    )

    rack_positions = {
        str(key): Vector((float(value[0]), float(value[1])))
        for key, value in rack.get("positions_pool_xy_m", {}).items()
    }
    gap_ratio = float(rack.get("contact_gap_ratio", math.nan))
    radius = float(actual_parameters["R"])
    step = 2.0 * radius * (1.0 + gap_ratio)
    pitch = math.sqrt(3.0) * step * 0.5
    apex = [float(value) for value in profile["rack"]["apex_pool_xy_m"]]
    expected_positions = {}
    if len(rack_order) == 5:
        for row_index, row in enumerate(rack_order):
            y = apex[1] - row_index * pitch
            x0 = apex[0] - (len(row) - 1) * step * 0.5
            for column, number in enumerate(row):
                expected_positions[str(number)] = Vector((x0 + column * step, y))
    position_errors = {
        key: (rack_positions[key] - expected).length
        for key, expected in expected_positions.items()
        if key in rack_positions
    }
    check(
        "rack_positions_from_profile_formula",
        set(rack_positions) == {str(number) for number in range(1, 16)}
        and set(position_errors) == set(rack_positions)
        and max(position_errors.values(), default=math.inf) <= 5e-8
        and close(gap_ratio, profile["rack"]["contact_gap_ratio"], 1e-12),
        {
            "max_position_error_m": max(position_errors.values(), default=None),
            "contact_gap_ratio": gap_ratio,
            "step_m": step,
            "pitch_m": pitch,
        },
    )
    initial_position_errors = {}
    for number in range(1, 16):
        key = str(number)
        if key not in rack_positions or key not in shot["balls"]:
            continue
        initial = Vector(shot["balls"][key]["samples"][0]["p"])
        target = Vector((rack_positions[key].x, rack_positions[key].y, radius))
        initial_position_errors[key] = (initial - target).length
    check(
        "rack_positions_match_actual_shot_balls",
        len(initial_position_errors) == 15
        and max(initial_position_errors.values(), default=math.inf) <= 5e-8,
        {
            "max_initial_position_error_m": max(
                initial_position_errors.values(), default=None
            ),
            "errors_m": initial_position_errors,
        },
    )

    contact_pairs = set()
    for row_index, row in enumerate(rack_order):
        for column in range(len(row) - 1):
            contact_pairs.add(tuple(sorted((str(row[column]), str(row[column + 1])))))
        if row_index > 0:
            previous = rack_order[row_index - 1]
            for column, number in enumerate(previous):
                contact_pairs.add(tuple(sorted((str(number), str(row[column])))))
                contact_pairs.add(tuple(sorted((str(number), str(row[column + 1])))))
    contact_distance_errors = {}
    for first, second in sorted(contact_pairs):
        if first in rack_positions and second in rack_positions:
            distance = (rack_positions[first] - rack_positions[second]).length
            contact_distance_errors[first + "-" + second] = abs(distance - step)
    all_pair_distances = []
    keys = sorted(rack_positions, key=int)
    for index, first in enumerate(keys):
        for second in keys[index + 1:]:
            all_pair_distances.append((rack_positions[first] - rack_positions[second]).length)
    minimum_pair_distance = min(all_pair_distances, default=-math.inf)
    check(
        "rack_thirty_neighbor_contact_distances",
        len(contact_pairs) == 30
        and len(contact_distance_errors) == 30
        and max(contact_distance_errors.values(), default=math.inf) <= 5e-8,
        {
            "contact_count": len(contact_distance_errors),
            "expected_distance_m": step,
            "max_contact_distance_error_m": max(
                contact_distance_errors.values(), default=None
            ),
        },
    )
    check(
        "rack_no_ball_overlap",
        minimum_pair_distance >= 2.0 * radius - 5e-8,
        {"minimum_pair_distance_m": minimum_pair_distance},
        {"minimum_m": 2.0 * radius},
    )
    check(
        "rack_inside_playfield",
        len(rack_positions) == 15
        and all(
            radius <= point.x <= float(geometry["w"]) - radius
            and radius <= point.y <= float(geometry["l"]) - radius
            for point in rack_positions.values()
        ),
        {
            "x_range_m": [
                min((point.x for point in rack_positions.values()), default=None),
                max((point.x for point in rack_positions.values()), default=None),
            ],
            "y_range_m": [
                min((point.y for point in rack_positions.values()), default=None),
                max((point.y for point in rack_positions.values()), default=None),
            ],
        },
    )
    rack_root = bpy.data.objects.get("PT_GameRackRoot")
    rack_parts = [
        obj for obj in game.objects
        if obj.name.startswith("PT_GameRack_")
    ] if game else []
    expected_rack_parts = {
        "PT_GameRack_LeftRail", "PT_GameRack_RightRail", "PT_GameRack_BaseRail"
    }
    check(
        "rack_actual_scene_components",
        rack_root is not None
        and {obj.name for obj in rack_parts} == expected_rack_parts
        and all(obj.parent == rack_root and obj.type == "MESH" for obj in rack_parts),
        {
            "root": rack_root.name if rack_root else None,
            "parts": sorted(obj.name for obj in rack_parts),
        },
    )

    # Measure the actual modeled cue at contact, including child transforms.
    cue_root = bpy.data.objects.get("PT_GameCueRoot")
    cue_parts = [
        obj for obj in game.objects if obj.name in CUE_COMPONENT_NAMES
    ] if game else []
    check(
        "cue_actual_scene_components",
        cue_root is not None
        and {obj.name for obj in cue_parts} == CUE_COMPONENT_NAMES
        and all(obj.parent == cue_root and obj.type == "MESH" for obj in cue_parts)
        and int(scene.get("gameplay_cue_component_count", -1)) == 8,
        {
            "root": cue_root.name if cue_root else None,
            "components": sorted(obj.name for obj in cue_parts),
            "scene_count": scene.get("gameplay_cue_component_count"),
        },
    )
    cue_audit = {}
    if cue_root is not None and {obj.name for obj in cue_parts} == CUE_COMPONENT_NAMES:
        cue_row = shot["cue"]
        profile_cue = profile["cue"]
        cue_metadata_expected = {
            "mass_kg": float(profile_cue["mass_kg"]),
            "length_m": float(profile_cue["length_m"]),
            "tip_diameter_m": 2.0 * float(profile_cue["shaft_radius_at_tip_m"]),
            "impact_speed_mps": float(cue_row["V0_mps"]),
            "phi_deg": float(cue_row["phi_deg"]),
            "theta_deg": float(cue_row["theta_deg"]),
            "a": float(cue_row["a"]),
            "b": float(cue_row["b"]),
        }
        cue_metadata_failures = [
            key for key, expected in cue_metadata_expected.items()
            if not close(cue_root.get(key), expected, 1e-9)
        ]
        check(
            "cue_authoritative_metadata",
            not cue_metadata_failures
            and close(cue_row["mass_kg"], profile_cue["mass_kg"], 1e-12)
            and close(cue_row["length_m"], profile_cue["length_m"], 1e-12),
            {
                "failures": cue_metadata_failures,
                "values": {key: cue_root.get(key) for key in cue_metadata_expected},
            },
            cue_metadata_expected,
        )

        set_scene_frame(scene, impact)
        bpy.context.view_layer.update()
        phi = math.radians(float(cue_row["phi_deg"]))
        theta = math.radians(float(cue_row["theta_deg"]))
        expected_forward = Vector((
            math.cos(phi) * math.cos(theta),
            math.sin(phi) * math.cos(theta),
            -math.sin(theta),
        )).normalized()
        tip_obj = bpy.data.objects["PT_GameCue_Tip"]
        bumper_obj = bpy.data.objects["PT_GameCue_Bumper"]
        actual_tip = cap_center(tip_obj, expected_forward, True)
        actual_butt = cap_center(bumper_obj, expected_forward, False)
        actual_forward = (actual_tip - actual_butt).normalized()
        axis_dot = min(1.0, max(-1.0, expected_forward.dot(actual_forward)))
        # atan2(cross, dot) remains accurate for nearly parallel Float32
        # vectors; acos(dot) loses the small-angle signal to cancellation.
        axis_error_deg = math.degrees(math.atan2(
            expected_forward.cross(actual_forward).length,
            axis_dot,
        ))

        projected_lengths = {}
        component_intervals = []
        metadata_length_sum = 0.0
        for part in cue_parts:
            points = [part.matrix_world @ vertex.co for vertex in part.data.vertices]
            projections = [point.dot(actual_forward) for point in points]
            measured = max(projections) - min(projections)
            projected_lengths[part.name] = measured
            component_intervals.append((min(projections), max(projections), part.name))
            metadata_length_sum += float(part.get("component_length_m", math.nan))
        component_intervals.sort()
        maximum_gap = max((
            max(0.0, second[0] - first[1])
            for first, second in zip(component_intervals, component_intervals[1:])
        ), default=0.0)
        component_projection_errors = {
            part.name: abs(
                projected_lengths[part.name]
                - float(part.get("component_length_m", math.inf))
            )
            for part in cue_parts
        }
        actual_span = (actual_tip - actual_butt).length
        check(
            "cue_component_total_and_projected_length",
            close(metadata_length_sum, profile_cue["length_m"], 1e-9)
            and abs(actual_span - float(profile_cue["length_m"])) <= 2e-5
            and max(component_projection_errors.values(), default=math.inf) <= 2e-5
            and maximum_gap <= 2e-5,
            {
                "metadata_component_sum_m": metadata_length_sum,
                "actual_tip_to_butt_span_m": actual_span,
                "projected_component_lengths_m": projected_lengths,
                "max_component_length_error_m": max(
                    component_projection_errors.values(), default=None
                ),
                "max_intercomponent_gap_m": maximum_gap,
            },
            {"cue_length_m": profile_cue["length_m"]},
        )
        check(
            "cue_actual_axis_phi_theta",
            axis_error_deg <= 0.001,
            {
                "axis_error_deg": axis_error_deg,
                "actual_forward_world": list(actual_forward),
                "expected_forward_world": list(expected_forward),
            },
        )

        cue_ball_center = balls["cue"].matrix_world.translation.copy()
        horizontal = math.hypot(actual_forward.x, actual_forward.y)
        actual_phi = math.degrees(math.atan2(actual_forward.y, actual_forward.x))
        actual_theta = math.degrees(math.asin(-actual_forward.z))
        actual_left = Vector((
            -actual_forward.y / horizontal,
            actual_forward.x / horizontal,
            0.0,
        ))
        actual_up = actual_forward.cross(actual_left).normalized()
        contact_delta = actual_tip - cue_ball_center
        actual_a = contact_delta.dot(actual_left) / radius
        actual_b = contact_delta.dot(actual_up) / radius
        actual_normal = -contact_delta.dot(actual_forward) / radius
        expected_left = Vector((-math.sin(phi), math.cos(phi), 0.0)).normalized()
        expected_up = expected_forward.cross(expected_left).normalized()
        radial_sq = 1.0 - float(cue_row["a"]) ** 2 - float(cue_row["b"]) ** 2
        expected_tip = (
            pool_to_world(shot["balls"]["cue"]["samples"][0]["p"])
            - expected_forward * (radius * math.sqrt(radial_sq))
            + expected_left * (float(cue_row["a"]) * radius)
            + expected_up * (float(cue_row["b"]) * radius)
        )
        contact_error = (actual_tip - expected_tip).length
        check(
            "cue_actual_tip_contact_point",
            contact_error <= 5e-6
            and abs(contact_delta.length - radius) <= 5e-6
            and abs(actual_normal - math.sqrt(radial_sq)) <= 2e-5,
            {
                "actual_world_m": list(actual_tip),
                "expected_world_m": list(expected_tip),
                "position_error_m": contact_error,
                "contact_radius_m": contact_delta.length,
                "normal_fraction": actual_normal,
            },
        )
        check(
            "cue_actual_a_b_theta_offsets",
            abs(actual_a - float(cue_row["a"])) <= 2e-5
            and abs(actual_b - float(cue_row["b"])) <= 2e-5
            and angle_difference_degrees(actual_phi, cue_row["phi_deg"]) <= 0.001
            and abs(actual_theta - float(cue_row["theta_deg"])) <= 0.001,
            {
                "actual_a": actual_a,
                "actual_b": actual_b,
                "actual_phi_deg": actual_phi,
                "actual_theta_deg": actual_theta,
            },
            {
                "a": cue_row["a"],
                "b": cue_row["b"],
                "phi_deg": cue_row["phi_deg"],
                "theta_deg": cue_row["theta_deg"],
            },
        )

        root_curves, root_curve_details = action_curves(cue_root)
        root_channel_map = {
            (curve.data_path, int(curve.array_index)): curve for curve in root_curves
        }
        location_channels = {("location", index) for index in range(3)}
        root_key_times = sorted({
            float(point.co.x)
            for curve in root_curves
            for point in curve.keyframe_points
        })
        previous_times = [value for value in root_key_times if value < impact]
        previous_frame = max(previous_times) if previous_times else None
        terminal_linear = False
        velocity = Vector((math.nan, math.nan, math.nan))
        terminal_dt_s = math.nan
        if (
            previous_frame is not None
            and set(root_channel_map) == location_channels
            and all(len(curve.keyframe_points) == len(root_key_times)
                    for curve in root_curves)
        ):
            terminal_linear = all(
                all(
                    point.interpolation == "LINEAR"
                    for point in curve.keyframe_points
                    if previous_frame - 1e-7 <= float(point.co.x) <= impact + 1e-7
                )
                for curve in root_curves
            )
            set_scene_frame(scene, previous_frame)
            previous_location = cue_root.matrix_world.translation.copy()
            set_scene_frame(scene, impact)
            impact_location = cue_root.matrix_world.translation.copy()
            terminal_dt_s = (impact - previous_frame) / effective_fps
            velocity = (impact_location - previous_location) / terminal_dt_s
        terminal_speed = velocity.length
        terminal_projected_speed = velocity.dot(actual_forward)
        velocity_cross_axis = (velocity - actual_forward * terminal_projected_speed).length
        check(
            "cue_terminal_root_animation_velocity",
            root_curve_details["api"] == "layered"
            and set(root_channel_map) == location_channels
            and previous_frame is not None
            and terminal_linear
            and abs(terminal_projected_speed - float(cue_row["V0_mps"])) <= 0.002
            and abs(terminal_speed - float(cue_row["V0_mps"])) <= 0.002
            and velocity_cross_axis <= 0.0002,
            {
                **root_curve_details,
                "channels": [list(value) for value in sorted(root_channel_map)],
                "terminal_start_frame": previous_frame,
                "impact_frame": impact,
                "terminal_dt_s": terminal_dt_s,
                "velocity_world_mps": list(velocity),
                "speed_mps": terminal_speed,
                "projected_speed_mps": terminal_projected_speed,
                "cross_axis_speed_mps": velocity_cross_axis,
                "linear": terminal_linear,
            },
            {"V0_mps": cue_row["V0_mps"]},
        )
        cue_audit = {
            "metadata_length_sum_m": metadata_length_sum,
            "actual_span_m": actual_span,
            "actual_tip_world_m": list(actual_tip),
            "expected_tip_world_m": list(expected_tip),
            "contact_error_m": contact_error,
            "actual_a": actual_a,
            "actual_b": actual_b,
            "actual_phi_deg": actual_phi,
            "actual_theta_deg": actual_theta,
            "terminal_speed_mps": terminal_speed,
            "terminal_velocity_world_mps": list(velocity),
        }
    else:
        check("cue_authoritative_metadata", False, "cue components unavailable")
        check("cue_component_total_and_projected_length", False, "cue components unavailable")
        check("cue_actual_axis_phi_theta", False, "cue components unavailable")
        check("cue_actual_tip_contact_point", False, "cue components unavailable")
        check("cue_actual_a_b_theta_offsets", False, "cue components unavailable")
        check("cue_terminal_root_animation_velocity", False, "cue components unavailable")

    view_layer = scene.view_layers.get(VIEW_LAYER)
    static_layer = layer_collection(view_layer.layer_collection, "05_HERO_PROPS") if view_layer else None
    game_layer = layer_collection(view_layer.layer_collection, GAME) if view_layer else None
    check(
        "gameplay_view_layer",
        view_layer is not None
        and scene.get("gameplay_view_layer") == VIEW_LAYER
        and static_layer is not None and static_layer.exclude
        and game_layer is not None and not game_layer.exclude,
        {
            "view_layer": VIEW_LAYER if view_layer else None,
            "static_balls_excluded": bool(static_layer.exclude) if static_layer else None,
            "gameplay_excluded": bool(game_layer.exclude) if game_layer else None,
        },
    )

    # Confirm that the export contains the full 240 Hz grid plus every exact
    # event sample, and that all 16 balls share that authoritative timeline.
    sample_rate = int(shot["sample_rate_hz"])
    ball_time_maps = {}
    timeline_failures = []
    for ball_id, trajectory in shot["balls"].items():
        times = [float(sample["t"]) for sample in trajectory["samples"]]
        if len(set(times)) != len(times) or any(
            second <= first for first, second in zip(times, times[1:])
        ):
            timeline_failures.append(ball_id + ":non-strict")
        ball_time_maps[ball_id] = {
            float(sample["t"]): sample for sample in trajectory["samples"]
        }
    reference_times = list(ball_time_maps["cue"])
    for ball_id, values in ball_time_maps.items():
        if list(values) != reference_times:
            timeline_failures.append(ball_id + ":different-timeline")
    check(
        "all_ball_exported_sample_timelines",
        not timeline_failures,
        {
            "failures": timeline_failures,
            "samples_per_ball": {
                ball_id: len(values) for ball_id, values in ball_time_maps.items()
            },
        },
    )
    regular_times = {
        round(index / sample_rate, 9)
        for index in range(int(math.floor(float(shot["duration_s"]) * sample_rate)) + 1)
    }
    reference_rounded = {round(value, 9) for value in reference_times}
    missing_regular_times = sorted(regular_times - reference_rounded)
    event_times = {round(float(event["time_s"]), 9) for event in shot["events"]}
    missing_event_times = sorted(event_times - reference_rounded)
    check(
        "regular_240hz_sample_coverage",
        not missing_regular_times and sample_rate == 240,
        {
            "sample_rate_hz": sample_rate,
            "regular_grid_count": len(regular_times),
            "missing_count": len(missing_regular_times),
            "first_missing": missing_regular_times[:10],
        },
    )
    check(
        "exact_event_sample_coverage",
        not missing_event_times,
        {
            "event_count": len(shot["events"]),
            "unique_event_times": len(event_times),
            "missing_count": len(missing_event_times),
            "first_missing": missing_event_times[:10],
        },
    )

    parity_by_ball = {
        ball_id: {
            "samples_evaluated": 0,
            "max_position_error_m": 0.0,
            "max_orientation_error_deg": 0.0,
            "worst_position_time_s": None,
            "worst_orientation_time_s": None,
        }
        for ball_id in balls
    }
    for time_s in reference_times:
        frame = impact + time_s * expected_fps
        set_scene_frame(scene, frame)
        for ball_id, ball in balls.items():
            if ball is None or time_s not in ball_time_maps[ball_id]:
                continue
            expected = ball_time_maps[ball_id][time_s]
            actual_position = ball.matrix_world.translation
            position_error = (actual_position - pool_to_world(expected["p"])).length
            expected_q = Quaternion(expected["q"]).normalized()
            actual_q = ball.matrix_world.to_quaternion().normalized()
            dot = min(1.0, abs(float(expected_q.dot(actual_q))))
            orientation_error = math.degrees(2.0 * math.acos(dot))
            row = parity_by_ball[ball_id]
            row["samples_evaluated"] += 1
            if position_error > row["max_position_error_m"]:
                row["max_position_error_m"] = position_error
                row["worst_position_time_s"] = time_s
            if orientation_error > row["max_orientation_error_deg"]:
                row["max_orientation_error_deg"] = orientation_error
                row["worst_orientation_time_s"] = time_s

    for ball_id, row in parity_by_ball.items():
        number = int(shot["balls"][ball_id]["number"])
        label = "cue" if number == 0 else "%02d" % number
        check(
            "ball_%s_every_sample_position_parity" % label,
            row["samples_evaluated"] == len(reference_times)
            and row["max_position_error_m"] <= 0.00025,
            {
                "samples_evaluated": row["samples_evaluated"],
                "max_error_m": row["max_position_error_m"],
                "worst_time_s": row["worst_position_time_s"],
            },
            {"samples": len(reference_times), "max_error_m": 0.00025},
        )
        check(
            "ball_%s_every_sample_orientation_parity" % label,
            row["samples_evaluated"] == len(reference_times)
            and row["max_orientation_error_deg"] <= 0.1,
            {
                "samples_evaluated": row["samples_evaluated"],
                "max_error_deg": row["max_orientation_error_deg"],
                "worst_time_s": row["worst_orientation_time_s"],
            },
            {"samples": len(reference_times), "max_error_deg": 0.1},
        )

    maximum_position_error = max(
        (row["max_position_error_m"] for row in parity_by_ball.values()),
        default=math.inf,
    )
    maximum_orientation_error = max(
        (row["max_orientation_error_deg"] for row in parity_by_ball.values()),
        default=math.inf,
    )
    total_sample_evaluations = sum(
        row["samples_evaluated"] for row in parity_by_ball.values()
    )
    check(
        "all_exported_samples_scene_parity",
        total_sample_evaluations == len(reference_times) * 16
        and maximum_position_error <= 0.00025
        and maximum_orientation_error <= 0.1,
        {
            "timeline_samples": len(reference_times),
            "ball_sample_evaluations": total_sample_evaluations,
            "max_position_error_m": maximum_position_error,
            "max_orientation_error_deg": maximum_orientation_error,
        },
    )

    maximum_step = 0.0
    pocket_failures = []
    capture_count = 0
    pocket_event_pairs = {
        (str(event["ids"][0]), str(event["ids"][1]), round(float(event["time_s"]), 9))
        for event in shot["events"]
        if event.get("type") == "ball_pocket" and len(event.get("ids", [])) >= 2
    }
    for ball_id, trajectory in shot["balls"].items():
        samples = trajectory["samples"]
        if len(samples) >= 2:
            maximum_step = max(maximum_step, max(
                math.dist(first["p"], second["p"])
                for first, second in zip(samples, samples[1:])
            ))
        capture = trajectory.get("capture_time_s")
        if capture is None:
            if trajectory.get("pocket_id") is not None:
                pocket_failures.append(ball_id + ":pocket-without-capture")
            continue
        capture_count += 1
        pocket_id = trajectory.get("pocket_id")
        tail = [sample for sample in samples if sample["t"] >= capture]
        if not tail:
            pocket_failures.append(ball_id + ":missing-tail")
            continue
        if any(second["p"][2] > first["p"][2] + 1e-9
               for first, second in zip(tail, tail[1:])):
            pocket_failures.append(ball_id + ":nonmonotonic-z")
        if tail[-1]["p"][2] >= 0.0:
            pocket_failures.append(ball_id + ":not-below-bed")
        if pocket_id not in geometry["pockets"]:
            pocket_failures.append(ball_id + ":unknown-pocket-id")
        if (str(ball_id), str(pocket_id), round(float(capture), 9)) not in pocket_event_pairs:
            pocket_failures.append(ball_id + ":missing-capture-event")
    check(
        "continuous_trajectory_steps",
        maximum_step <= 0.060,
        {
            "maximum_sample_step_m": maximum_step,
            "sample_period_s": 1.0 / sample_rate,
        },
    )
    check(
        "pocket_capture_and_drop_continuity",
        not pocket_failures,
        {"capture_count": capture_count, "failures": pocket_failures},
    )

    pool_probe = [float(value) for value in shot["balls"]["cue"]["samples"][0]["p"]]
    world_probe = (
        pool_probe[0] + C.TABLE_CENTRE[0] - C.PLAY_W * 0.5,
        pool_probe[1] + C.TABLE_CENTRE[1] - C.PLAY_L * 0.5,
        pool_probe[2] + C.BED_Z,
    )
    roundtrip = (
        world_probe[0] - C.TABLE_CENTRE[0] + C.PLAY_W * 0.5,
        world_probe[1] - C.TABLE_CENTRE[1] + C.PLAY_L * 0.5,
        world_probe[2] - C.BED_Z,
    )
    coordinate_error = math.dist(roundtrip, pool_probe)
    check(
        "coordinate_roundtrip",
        coordinate_error <= 1e-7,
        {"error_m": coordinate_error},
    )

    scene.frame_set(1)
    failed = [row for row in checks if row["status"] == "FAIL"]
    blend_path = Path(bpy.data.filepath)
    report = {
        "schema": "pool-physics-playback-audit/v2",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if not failed else "FAIL",
        "blend": str(blend_path.relative_to(ROOT)),
        "blend_sha256": sha256(blend_path),
        "trajectory": str(args.shot.relative_to(ROOT)),
        "identity": {
            "trajectory_stored_sha256": stored_trajectory,
            "trajectory_recomputed_sha256": recomputed_trajectory,
            "profile_file_sha256": profile_hash,
            "geometry_file_sha256": geometry_hash,
            "markings_file_sha256": markings_hash,
        },
        "animation": {
            "expected_transform_channels_per_ball": 7,
            "expected_keys_per_channel": len(expected_transform_frames_f32),
            "expected_first_frame": expected_transform_frames_f32[0],
            "expected_last_frame": expected_transform_frames_f32[-1],
            "balls": animation_audit,
        },
        "ball_assets": ball_asset_audit,
        "rack": {
            "order": rack_order,
            "contact_gap_ratio": gap_ratio,
            "neighbor_contact_count": len(contact_distance_errors),
            "max_neighbor_distance_error_m": max(
                contact_distance_errors.values(), default=None
            ),
            "minimum_pair_distance_m": minimum_pair_distance,
            "max_initial_position_error_m": max(
                initial_position_errors.values(), default=None
            ),
        },
        "cue": cue_audit,
        "parity": {
            "sample_rate_hz": sample_rate,
            "timeline_samples": len(reference_times),
            "ball_sample_evaluations": total_sample_evaluations,
            "max_position_error_m": maximum_position_error,
            "max_orientation_error_deg": maximum_orientation_error,
            "max_sample_step_m": maximum_step,
            "by_ball": parity_by_ball,
        },
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "checks": checks,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print("\nplayback audit: %d/%d passed -> %s" %
          (report["summary"]["passed"], report["summary"]["total"], args.report))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
