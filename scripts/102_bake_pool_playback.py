"""Build the derived gameplay scene and bake a solver trajectory into Blender.

Run from the locked static preview.  The script creates only ``11_GAMEPLAY``
objects and a GAMEPLAY view layer, leaving the four locked pool/environment
collections and all of their datablocks untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import config as C  # noqa: E402
import lib as L  # noqa: E402
from trajectory_contract import verify_trajectory_sha256  # noqa: E402


GAME = "11_GAMEPLAY"
VIEW_LAYER = "GAMEPLAY"
STATIC_BALL_COLLECTION = "05_HERO_PROPS"
DEFAULT_SHOT = ROOT / "assets" / "data" / "shots" / "break_control.json"
DEFAULT_OUTPUT = ROOT / "blend" / "poolroom_gameplay_preview.blend"
MARKINGS_PATH = ROOT / "assets" / "data" / "game_ball_markings.json"
PROFILE_PATH = ROOT / "assets" / "data" / "pool_physics_profile.json"
GEOMETRY_PATH = ROOT / "assets" / "data" / "table_wpa_geometry.json"


def parse_args() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", type=Path, default=DEFAULT_SHOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(values)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pool_to_world(position) -> Vector:
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


def validate_shot_contract(shot, profile) -> None:
    verified = verify_trajectory_sha256(shot)
    if shot.get("profile_sha256") != sha256(PROFILE_PATH):
        raise ValueError("trajectory/profile hash mismatch")
    if shot.get("geometry_contract_sha256") != sha256(GEOMETRY_PATH):
        raise ValueError("trajectory/table geometry hash mismatch")
    expected = expected_ball_parameters(profile)
    actual = shot.get("ball_parameters", {})
    failures = [
        key for key, value in expected.items()
        if key not in actual or abs(float(actual[key]) - value) > 1e-12
    ]
    if failures:
        raise ValueError("trajectory ball parameters mismatch: " + ", ".join(failures))
    if shot.get("sample_rate_hz") != profile["solver"]["sample_rate_hz"]:
        raise ValueError("trajectory sample rate does not match profile")
    if verified != shot["trajectory_sha256"]:
        raise ValueError("trajectory identity verification failed")


def scalar_material(name, color, roughness=0.35, metallic=0.0):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def ball_material(number: int, texture_path: Path):
    name = "MAT_GameBall_Cue" if number == 0 else "MAT_GameBall_%02d" % number
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Roughness"].default_value = 0.105
    shader.inputs["IOR"].default_value = 1.51
    try:
        shader.inputs["Coat Weight"].default_value = 0.42
        shader.inputs["Coat Roughness"].default_value = 0.055
    except KeyError:
        pass
    image = bpy.data.images.load(str(texture_path), check_existing=True)
    image.colorspace_settings.name = "sRGB"
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    coordinates = tree.nodes.new("ShaderNodeTexCoord")
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 260.0
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.48
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.035
    bump.inputs["Distance"].default_value = 0.00011
    tree.links.new(coordinates.outputs["Generated"], noise.inputs["Vector"])
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material["physical_material"] = "cast phenolic resin"
    material["surface_finish"] = "unwaxed polished"
    material["texture_path"] = str(texture_path.relative_to(ROOT))
    return material


def set_linear_keys(obj) -> None:
    animation = obj.animation_data
    if animation is None or animation.action is None:
        return
    action = animation.action
    # Blender 5.2 stores newly inserted object curves in layered channel bags.
    # ``action.fcurves`` remains available for legacy actions; use both APIs.
    curves = []
    if hasattr(action, "fcurves"):
        try:
            curves.extend(list(action.fcurves))
        except Exception:
            pass
    if not curves and hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        curves.extend(list(strip.channelbag(slot).fcurves))
                    except Exception:
                        continue
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"


def key_transform(obj, frame: float) -> None:
    obj.keyframe_insert(data_path="location", frame=frame, group="Solver Location")
    obj.keyframe_insert(data_path="rotation_quaternion", frame=frame,
                        group="Solver Orientation")


def bake_transform_samples(obj, rows) -> None:
    """Write exact fractional-frame F-curves without key-merge heuristics."""
    if not rows:
        raise ValueError("transform bake requires at least one row")
    first_frame, first_location, first_quaternion = rows[0]
    obj.location = first_location
    obj.rotation_quaternion = first_quaternion
    # Create the layered Blender 5.2 action/slot/channel bag, then replace its
    # points in bulk.  High-level repeated insertion merges keys within about
    # 0.01 frame, which is too coarse for near-simultaneous rack contacts.
    key_transform(obj, first_frame)
    action = obj.animation_data.action
    curves = []
    if hasattr(action, "layers") and action.layers:
        strip = action.layers[0].strips[0]
        bag = strip.channelbag(action.slots[0])
        curves = list(bag.fcurves)
    elif hasattr(action, "fcurves"):
        curves = list(action.fcurves)
    by_channel = {(curve.data_path, curve.array_index): curve
                  for curve in curves}
    expected = {("location", index) for index in range(3)} | \
        {("rotation_quaternion", index) for index in range(4)}
    if set(by_channel) != expected:
        raise RuntimeError("unexpected transform action channels on %s" % obj.name)

    for data_path, width in (("location", 3), ("rotation_quaternion", 4)):
        for component in range(width):
            curve = by_channel[(data_path, component)]
            curve.keyframe_points.clear()
            curve.keyframe_points.add(len(rows))
            values = []
            for frame, location, quaternion in rows:
                vector = location if data_path == "location" else quaternion
                values.extend((float(frame), float(vector[component])))
            curve.keyframe_points.foreach_set("co", values)
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
            # ``FCurve.update()`` deduplicates keys inside roughly 0.01 frame,
            # destroying distinct high-speed event samples.  Sorting plus
            # handle recalculation keeps all Float32-distinguishable times and
            # evaluates correctly without that destructive merge.
            curve.keyframe_points.sort()
            curve.keyframe_points.handles_recalc()


def build_balls(shot, profile, markings):
    made = []
    impact_frame = float(profile["playback"]["impact_frame"])
    fps = float(profile["playback"]["fps"])
    params = shot["ball_parameters"]
    radius = float(params["R"])
    mass = float(params["m"])
    inertia = 0.4 * mass * radius * radius
    for ball_id, trajectory in shot["balls"].items():
        number = int(trajectory["number"])
        filename = "ball_cue.png" if number == 0 else "ball_%02d.png" % number
        texture_path = ROOT / "assets" / "textures" / "balls_game" / filename
        if not texture_path.exists():
            raise FileNotFoundError(texture_path)
        name = "PT_GameBall_Cue" if number == 0 else "PT_GameBall_%02d" % number
        first = trajectory["samples"][0]
        material = ball_material(number, texture_path)
        ball = L.uv_sphere(
            name, radius, pool_to_world(first["p"]), GAME, material,
            segments=96, rings=48,
        )
        ball.rotation_mode = "QUATERNION"
        ball.rotation_quaternion = Quaternion(first["q"])
        ball["ball_id"] = str(ball_id)
        ball["ball_number"] = number
        ball["diameter_m"] = 2.0 * radius
        ball["mass_kg"] = mass
        ball["solid_sphere_inertia_kg_m2"] = inertia
        ball["sliding_friction"] = float(params["u_s"])
        ball["rolling_friction"] = float(params["u_r"])
        ball["spinning_friction"] = float(params["u_sp_proportionality"]) * radius
        ball["ball_ball_friction"] = float(params["u_b"])
        ball["ball_ball_restitution"] = float(params["e_b"])
        ball["cushion_restitution_parameter"] = float(params["e_c"])
        ball["cushion_friction"] = float(params["f_c"])
        ball["physics_authority"] = "pooltool 0.6.0 event trajectory"
        ball["blender_rigid_body_intentional"] = False
        ball["decal_asset"] = str(texture_path.relative_to(ROOT))
        mark = markings["assets"][str(texture_path.relative_to(ROOT))]
        ball["decal_sha256"] = mark["sha256"]
        ball["marking_class"] = mark["class"]
        ball["opposed_number_circles"] = mark["opposed_number_circles"]
        ball["duplicate_number_inverted"] = mark["duplicate_number_inverted"]
        ball["number_underscored"] = mark["underscored"]
        ball["pocket_id"] = trajectory["pocket_id"] or ""

        # Hold the physical setup before contact, then replay every regular and
        # exact event sample at fractional frames.  Linear interpolation is
        # essential; Bezier handles would invent accelerations between samples.
        rows = [
            (1.0, pool_to_world(first["p"]), Quaternion(first["q"])),
            (impact_frame, pool_to_world(first["p"]), Quaternion(first["q"])),
        ]
        rows.extend(
            (
                impact_frame + float(sample["t"]) * fps,
                pool_to_world(sample["p"]),
                Quaternion(sample["q"]),
            )
            for sample in trajectory["samples"][1:]
        )
        bake_transform_samples(ball, rows)
        made.append(ball)
    return made


def parent_keep_world(obj, parent) -> None:
    # Newly-created datablock geometry may not have an evaluated matrix_world
    # until the dependency graph has advanced.  Reading it immediately can
    # therefore return identity and collapse the child to the parent's origin
    # after save/reload.  Force evaluation before preserving the transform.
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def build_cue(shot, profile):
    cue_row = profile["cue"]
    impact = float(profile["playback"]["impact_frame"])
    fps = float(profile["playback"]["fps"])
    phi = math.radians(float(shot["cue"]["phi_deg"]))
    theta = math.radians(float(shot["cue"]["theta_deg"]))
    forward = Vector((
        math.cos(phi) * math.cos(theta),
        math.sin(phi) * math.cos(theta),
        -math.sin(theta),
    )).normalized()
    left = Vector((-math.sin(phi), math.cos(phi), 0.0)).normalized()
    cue_up = forward.cross(left).normalized()
    cue_ball = shot["balls"]["cue"]["samples"][0]["p"]
    center = pool_to_world(cue_ball)
    radius = float(shot["ball_parameters"]["R"])
    side_a = float(shot["cue"]["a"])
    vertical_b = float(shot["cue"]["b"])
    radial_sq = 1.0 - side_a * side_a - vertical_b * vertical_b
    if radial_sq <= 0.0:
        raise ValueError("cue contact offsets lie outside the cue ball")
    tip_contact = (
        center
        - forward * (radius * math.sqrt(radial_sq))
        + left * (side_a * radius)
        + cue_up * (vertical_b * radius)
    )
    length = float(cue_row["length_m"])

    maple = scalar_material("MAT_GameCue_Maple", (0.63, 0.43, 0.23), 0.27)
    dark_maple = scalar_material("MAT_GameCue_Butt", (0.105, 0.045, 0.024), 0.24)
    wrap = scalar_material("MAT_GameCue_Wrap", (0.025, 0.020, 0.018), 0.48)
    ferrule = scalar_material("MAT_GameCue_Ferrule", (0.82, 0.80, 0.71), 0.22)
    chalk = scalar_material("MAT_GameCue_ChalkTip", (0.025, 0.105, 0.19), 0.72)
    metal = scalar_material("MAT_GameCue_Joint", (0.28, 0.29, 0.27), 0.18, 0.72)

    root = bpy.data.objects.new("PT_GameCueRoot", None)
    L.link(root, GAME)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.10
    root["mass_kg"] = float(cue_row["mass_kg"])
    root["length_m"] = length
    root["tip_diameter_m"] = 2.0 * float(cue_row["shaft_radius_at_tip_m"])
    root["impact_speed_mps"] = float(shot["cue"]["V0_mps"])
    root["phi_deg"] = float(shot["cue"]["phi_deg"])
    root["theta_deg"] = float(shot["cue"]["theta_deg"])
    root["a"] = side_a
    root["b"] = vertical_b
    root["strike_direction_world"] = [float(value) for value in forward]
    root["tip_contact_world_m"] = [float(value) for value in tip_contact]

    bumper_length = 0.008
    # Dimensions, including the rubber bumper, add to the authored 58 inches.
    sections = (
        ("Tip", 0.0065, 0.006, chalk),
        ("Ferrule", 0.0065, 0.025, ferrule),
        ("ShaftFront", 0.0068, 0.620, maple),
        ("ShaftBack", 0.0095, 0.315, maple),
        ("Joint", 0.0110, 0.022, metal),
        ("Wrap", 0.0165, 0.285, wrap),
        ("Butt", 0.0190, length - 1.273 - bumper_length, dark_maple),
    )
    cursor = tip_contact
    parts = []
    for label, part_radius, part_length, material in sections:
        end = cursor - forward * part_length
        part = L.cylinder_between(
            "PT_GameCue_%s" % label, part_radius, cursor, end,
            GAME, material, segments=32,
        )
        part["component_length_m"] = part_length
        parent_keep_world(part, root)
        parts.append(part)
        cursor = end

    bumper = L.cylinder_between(
        "PT_GameCue_Bumper", 0.0195, cursor,
        cursor - forward * bumper_length, GAME, wrap, segments=32,
    )
    bumper["component_length_m"] = bumper_length
    parent_keep_world(bumper, root)
    parts.append(bumper)

    cue_speed = float(shot["cue"]["V0_mps"])
    pullback = 0.29
    stroke_time = 2.0 * pullback / cue_speed
    acceleration = cue_speed / stroke_time
    offsets = [
        (1.0, -0.18),
        (impact - 14.0, -0.18),
        (impact - 8.0, -pullback),
        (impact - stroke_time * fps, -pullback),
    ]
    # A sampled constant-acceleration forward stroke reaches the solver's
    # exact cue speed at impact.  The final 1 ms segment is authored with an
    # exact V0 slope and remains wider than Blender's key-merge threshold.
    for fraction in (0.75, 0.50, 0.25, 0.05):
        time_s = -stroke_time * fraction
        distance = cue_speed * time_s + 0.5 * acceleration * time_s * time_s
        offsets.append((impact + time_s * fps, distance))
    terminal_dt = 0.001
    offsets.extend([
        (impact - terminal_dt * fps, -cue_speed * terminal_dt),
        (impact, 0.0),
    ])
    post_speed = (
        (float(cue_row["mass_kg"]) - float(shot["ball_parameters"]["m"]))
        / (float(cue_row["mass_kg"]) + float(shot["ball_parameters"]["m"]))
        * cue_speed
    )
    offsets.extend([
        (impact + fps * 0.020, post_speed * 0.020),
        (impact + fps * 0.080, 0.17),
        (impact + fps * 0.160, 0.21),
        # Withdraw the cue after the follow-through so it cannot linger over
        # the live table while the break resolves.
        (impact + fps * 0.42, -0.30),
        (impact + fps * 0.75, -1.25),
    ])
    root["terminal_stroke_segment_s"] = terminal_dt
    root["post_impact_speed_estimate_mps"] = post_speed
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Quaternion()
    for frame, distance in offsets:
        root.location = forward * distance
        root.keyframe_insert(data_path="location", frame=frame,
                             group="Cue Stroke")
    set_linear_keys(root)
    return root, parts


def bar_between(name, first, second, width, height, z, material):
    first, second = Vector(first), Vector(second)
    delta = second - first
    midpoint = (first + second) * 0.5
    angle = math.atan2(delta.y, delta.x)
    return L.box(
        name,
        (delta.length, width, height),
        (midpoint.x, midpoint.y, z),
        GAME,
        material,
        rotation=(0.0, 0.0, angle),
        bevel=0.004,
        bevel_segments=3,
    )


def build_triangle_rack(shot, profile):
    positions = shot["rack"]["positions_pool_xy_m"]
    radius = float(shot["ball_parameters"]["R"])
    apex = Vector((*positions["1"], 0.0))
    rear = [Vector((*positions[key], 0.0)) for key in ("5", "12")]
    rear.sort(key=lambda point: point.x)
    left, right = rear
    # Rail centrelines sit outside the ball envelope with a few millimetres of
    # real rack clearance; the opening remains visibly and physically hollow.
    apex_tip = Vector((apex.x, apex.y + radius + 0.028, 0.0))
    left_base = Vector((left.x - radius - 0.022, left.y - radius - 0.018, 0.0))
    right_base = Vector((right.x + radius + 0.022, right.y - radius - 0.018, 0.0))
    world = [pool_to_world(point) for point in (apex_tip, left_base, right_base)]
    z = C.BED_Z + 0.026
    wood = scalar_material("MAT_GameRack_OldMaple", (0.27, 0.13, 0.055), 0.34)
    root = bpy.data.objects.new("PT_GameRackRoot", None)
    L.link(root, GAME)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.12
    root["rack_type"] = "wooden triangular eight-ball rack"
    root["apex_pool_xy_m"] = [float(apex.x), float(apex.y)]
    root["ball_gap_ratio"] = float(shot["rack"]["contact_gap_ratio"])
    root["eight_ball_centered"] = True
    root["rear_corners_solid_stripe"] = True
    bars = [
        bar_between("PT_GameRack_LeftRail", world[0], world[1], 0.019, 0.052, z, wood),
        bar_between("PT_GameRack_RightRail", world[0], world[2], 0.019, 0.052, z, wood),
        bar_between("PT_GameRack_BaseRail", world[1], world[2], 0.019, 0.052, z, wood),
    ]
    for bar in bars:
        parent_keep_world(bar, root)
    impact = float(profile["playback"]["impact_frame"])
    keyframes = (
        (1.0, (0.0, 0.0, 0.0)),
        (impact - 22.0, (0.0, 0.0, 0.0)),
        (impact - 14.0, (0.10, 0.0, 0.16)),
        # The unseen racker carries it laterally off the playing surface.
        # It remains a real mesh in the scene, but is clear before the stroke.
        (impact - 6.0, (1.40, 0.0, 0.35)),
        (impact, (2.60, 0.0, 0.25)),
    )
    for frame, location in keyframes:
        root.location = location
        root.keyframe_insert(data_path="location", frame=frame,
                             group="Rack Removal")
    set_linear_keys(root)
    return root, bars


def look_at(camera, target) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def gameplay_camera(name, location, target, lens):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36.0
    data.dof.use_dof = False
    camera = bpy.data.objects.new(name, data)
    L.link(camera, GAME)
    camera.location = location
    look_at(camera, target)
    return camera


def build_cameras():
    cx, cy = C.TABLE_CENTRE[:2]
    bed = C.BED_Z
    overhead = gameplay_camera(
        "PT_GameCamera_Overhead",
        # Below the three-shade fixture and ceiling, so neither occludes the
        # diagnostic plan view.
        (cx, cy, bed + 0.88),
        (cx, cy, bed),
        32.0,
    )
    overhead.data.type = "ORTHO"
    overhead.data.ortho_scale = 3.28
    overhead.data.clip_start = 0.01
    # Put the 100-inch axis across the 16:9 frame so the complete table and
    # every settled ball remain visible without wasting most of the image.
    overhead.rotation_euler[2] = math.radians(90.0)
    break_camera = gameplay_camera(
        "PT_GameCamera_Break",
        (cx + 1.28, cy + 1.56, bed + 0.93),
        (cx, cy - 0.20, bed + 0.035),
        46.0,
    )
    pocket = gameplay_camera(
        "PT_GameCamera_Pocket",
        (cx - 1.02, cy - 1.58, bed + 0.45),
        (cx - C.PLAY_W * 0.5, cy - C.PLAY_L * 0.5, bed + 0.01),
        62.0,
    )
    return overhead, break_camera, pocket


def layer_collection(root, name):
    if root.collection.name == name:
        return root
    for child in root.children:
        found = layer_collection(child, name)
        if found is not None:
            return found
    return None


def build_view_layer(scene):
    existing = scene.view_layers.get(VIEW_LAYER)
    if existing is not None:
        scene.view_layers.remove(existing)
    view_layer = scene.view_layers.new(VIEW_LAYER)
    for name in (STATIC_BALL_COLLECTION, "00_GUIDES", "99_REFERENCE_LOCKED",
                 "10_PHYSICS_PROXIES"):
        layer = layer_collection(view_layer.layer_collection, name)
        if layer is not None:
            layer.exclude = True
    game_layer = layer_collection(view_layer.layer_collection, GAME)
    if game_layer is None or game_layer.exclude:
        raise RuntimeError("gameplay collection is not visible in GAMEPLAY layer")
    static_layer = layer_collection(view_layer.layer_collection,
                                    STATIC_BALL_COLLECTION)
    if static_layer is None or not static_layer.exclude:
        raise RuntimeError("static balls remain visible in GAMEPLAY layer")
    return view_layer


def main() -> int:
    args = parse_args()
    shot = load_json(args.shot)
    profile = load_json(PROFILE_PATH)
    markings = load_json(MARKINGS_PATH)
    if shot.get("schema") != "pool-shot-trajectory/v1":
        raise ValueError("unsupported trajectory schema")
    validate_shot_contract(shot, profile)
    if len(shot["balls"]) != 16:
        raise ValueError("gameplay shot must contain 16 balls")
    if any(obj.rigid_body is not None for obj in bpy.data.objects):
        raise RuntimeError("source preview no longer has intentional zero rigid bodies")

    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    L.clear_collection(GAME)
    balls = build_balls(shot, profile, markings)
    cue_root, cue_parts = build_cue(shot, profile)
    rack_root, rack_parts = build_triangle_rack(shot, profile)
    overhead, break_camera, pocket_camera = build_cameras()
    scene = bpy.context.scene
    scene.render.fps = int(profile["playback"]["fps"])
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = math.ceil(
        float(profile["playback"]["impact_frame"]) +
        float(shot["duration_s"]) * scene.render.fps
    ) + 1
    scene.camera = break_camera
    scene["physics_authority"] = "Pooltool 0.6.0 event solver"
    scene["trajectory_sha256"] = shot["trajectory_sha256"]
    scene["physics_profile_sha256"] = shot["profile_sha256"]
    scene["geometry_contract_sha256"] = shot["geometry_contract_sha256"]
    scene["zero_blender_rigid_bodies_intentional"] = True
    scene["solver_sample_rate_hz"] = int(shot["sample_rate_hz"])
    scene["gameplay_collection"] = GAME
    scene["gameplay_view_layer"] = VIEW_LAYER
    scene["gameplay_ball_count"] = len(balls)
    scene["gameplay_cue_component_count"] = len(cue_parts)
    scene["gameplay_rack_component_count"] = len(rack_parts)
    scene["gameplay_camera_count"] = 3
    build_view_layer(scene)
    scene.frame_set(1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out))
    print("  [gameplay bake] %d balls, %d cue parts, %d rack rails" %
          (len(balls), len(cue_parts), len(rack_parts)))
    print("  [trajectory] %s" % shot["trajectory_sha256"])
    print("  [saved] %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
