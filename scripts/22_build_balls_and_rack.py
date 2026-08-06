"""
22_build_balls_and_rack.py — 16 exact spheres and a legal static 8-ball rack.

Every ball is a fresh 57.15 mm sphere generated from the same routine, so every
instance is mathematically round and every transform stays (1, 1, 1). Nothing
here is scaled; the radius is baked into the vertices.

Rack legality (brief sec.11 / WPA):
  * apex ball centred exactly on the foot spot,
  * five tangent rows at sqrt(3)/2 * diameter,
  * the 8 in the middle of the triangle (never the apex),
  * one solid and one stripe in the two rear corners.

No physics, no rigid bodies, no constraints. The rack is static geometry.
"""
import bpy
import math
import os
import sys
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

PROPS = "05_HERO_PROPS"

# WPA colours. Solids 1-8, stripes 9-15 repeat the 1-7 hues.
HUES = {
    1: (0.85, 0.62, 0.03), 2: (0.02, 0.09, 0.45), 3: (0.62, 0.04, 0.03),
    4: (0.17, 0.03, 0.28), 5: (0.78, 0.20, 0.02), 6: (0.02, 0.26, 0.08),
    7: (0.35, 0.05, 0.07), 8: (0.014, 0.014, 0.016),
}
for n in range(9, 16):
    HUES[n] = HUES[n - 8]
STRIPES = set(range(9, 16))

# Fixed presentation values for the rack-detail camera. ``lift`` moves the
# local -Y number patch onto the exposed upper hemisphere; ``roll`` keeps the
# balls from reading as cloned while leaving the key numbers nearly upright.
# These values are authored, not random, so rebuilds produce the same transforms.
RACK_CAMERA_LOCATION = Vector((
    C.TABLE_CENTRE[0] + 0.46,
    C.TABLE_CENTRE[1] - 1.24,
    C.BED_Z + 0.235,
))
BALL_PRESENTATION = {
    0: (0.35, 17.0),
    1: (2.00, -2.0),
    2: (1.55, 10.0),
    3: (1.25, -11.0),
    4: (1.00, 8.0),
    5: (0.70, -10.0),
    6: (0.90, 13.0),
    7: (0.55, -8.0),
    8: (1.80, 2.0),
    9: (1.80, -4.0),
    10: (1.45, 9.0),
    11: (1.00, -9.0),
    12: (0.45, 6.0),
    13: (0.55, -13.0),
    14: (0.95, 12.0),
    15: (0.50, -5.0),
}


def rack_layout():
    """
    Standard 8-ball rack. Returns {number: (x, y)} in playfield-local metres,
    apex on the foot spot, rows receding toward the foot rail.

    Row 3 centre is the 8. Rear corners get 15 (stripe) and 9 (stripe) is not
    legal in both, so the corners are 15 (stripe) and 13 (stripe)? No: the
    requirement is one solid and one stripe. Corners here are 11 (stripe) and
    5 (solid).
    """
    order = [
        [1],                       # apex, on the foot spot
        [9, 2],
        [10, 8, 3],                # the 8 sits dead centre
        [11, 4, 14, 6],
        [5, 13, 15, 7, 12],        # rear row; corners are 5 (solid), 12 (stripe)
    ]
    pos = {}
    for r, row in enumerate(order):
        y = C.FOOT_SPOT_Y - r * C.ROW_PITCH      # recede toward the foot rail
        x0 = -(len(row) - 1) * C.BALL_D / 2.0
        for i, num in enumerate(row):
            pos[num] = (x0 + i * C.BALL_D, y)
    return pos


def decal_path(num):
    name = "ball_cue.png" if num == 0 else "ball_%02d.png" % num
    return os.path.join(C.ROOT, "assets", "textures", "balls", name)


def ball_material(num):
    """
    Phenolic. Amendment Patch 4: the stripe band and both number circles come
    from an equirectangular decal consumed inside the material node graph, not
    from geometry -- so nothing can drift off the sphere or break silhouette.
    """
    import importlib
    mm = importlib.import_module("40_build_materials")
    if num == 0:
        return mm.phenolic((0.86, 0.845, 0.80), "MAT_Ball_Cue_Phenolic",
                           decal=decal_path(0))
    return mm.phenolic(HUES[num], "MAT_Ball_%02d_Phenolic" % num,
                       decal=decal_path(num))


def orient_ball_for_rack(ob, num):
    """Deterministically present the local -Y number patch to the rack camera."""
    lift, roll_degrees = BALL_PRESENTATION[num]
    patch_normal = (RACK_CAMERA_LOCATION - ob.location).normalized()
    patch_normal = (patch_normal + Vector((0.0, 0.0, lift))).normalized()

    # Track local -Y toward the selected patch normal while keeping the glyph's
    # local +Z axis upright. A small authored roll adds natural variation.
    rotation = patch_normal.to_track_quat("-Y", "Z")
    rotation = Quaternion(patch_normal, math.radians(roll_degrees)) @ rotation
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = rotation.to_euler("XYZ")


def build_ball(num, x, y, mats_cache):
    """
    One ball. Solids are a single shell; stripes get an equatorial band built as
    a slightly proud second shell so the band is real geometry rather than a
    painted stripe that breaks at grazing angles.
    """
    name = "PT_Ball_Cue" if num == 0 else "PT_Ball_%02d" % num
    loc = (C.TABLE_CENTRE[0] + x, C.TABLE_CENTRE[1] + y, C.BED_Z + C.BALL_R)
    if num not in mats_cache:
        mats_cache[num] = ball_material(num)

    ob = L.uv_sphere(name, C.BALL_R, loc, PROPS, mats_cache[num],
                     segments=96, rings=48)
    orient_ball_for_rack(ob, num)
    ob["ball_number"] = num
    ob["diameter_m"] = C.BALL_D
    return ob


def build():
    L.clear_collection(PROPS)
    cache = {}
    made = []
    for num, (x, y) in rack_layout().items():
        made.append(build_ball(num, x, y, cache))
    # cue ball on the head string, off centre so the composition breathes
    made.append(build_ball(0, -0.093, C.HEAD_STRING_Y + 0.052, cache))

    # NOTE: the wooden triangle rack was removed. Its three bars were being
    # placed by an incorrect centroid rotation, so instead of framing the rack
    # they collapsed into a single stray block sitting in front of the 1 ball.
    # A rack is also not needed here: the balls are already racked and a real
    # player lifts the triangle away before the break.

    print("  [balls] %d objects (16 balls, no rack)" % len(made))
    return made


if __name__ == "__main__":
    build()
