"""50_set_dress.py — lived-in neighborhood-bar history and pool-room props.

The art is original project material, not copied brands or Simpsons imagery.
Its reference target is the accumulated, slightly funny fatigue of a 1980s/
1990s local tavern: crooked flyers, a league photo, stickers, score beads,
scarred fixtures, and practical clutter with real contact points.

Owns: 06_SET_DRESSING.
"""
import math
import os
import random
import sys
from math import radians

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

D = "06_SET_DRESSING"
HW, HL = C.ROOM_W / 2.0, C.ROOM_L / 2.0


def _wood_chair(name, x, y, rotation, mats, ladder=True):
    """Scarred cafe chair with floor contact and a real rung/back system."""
    seat_z = 0.46
    seat = L.box(name + "_Seat", (0.38, 0.39, 0.055), (x, y, seat_z), D,
                 mats["bar_wood"], rotation=(0, 0, rotation), bevel=0.018,
                 bevel_segments=2)
    seat["furniture_variant"] = "ladderback_wood" if ladder else \
        "painted_wood"
    for sx in (-0.14, 0.14):
        for sy in (-0.14, 0.14):
            dx = math.cos(rotation) * sx - math.sin(rotation) * sy
            dy = math.sin(rotation) * sx + math.cos(rotation) * sy
            L.cylinder(name + "_Leg_%s_%s" %
                       ("E" if sx > 0 else "W", "N" if sy > 0 else "S"),
                       0.017, 0.44, (x + dx, y + dy, 0.22), D,
                       mats["bar_wood"], segments=10)
    # Back is on local +Y.
    bx = x - math.sin(rotation) * 0.165
    by = y + math.cos(rotation) * 0.165
    for sx in (-0.14, 0.14):
        px = bx + math.cos(rotation) * sx
        py = by + math.sin(rotation) * sx
        L.cylinder(name + "_BackPost_%s" % ("E" if sx > 0 else "W"),
                   0.018, 0.48, (px, py, 0.70), D, mats["bar_wood"],
                   segments=10)
    for i, z in enumerate((0.68, 0.79, 0.90) if ladder else (0.80,)):
        L.box(name + "_BackSlat_%d" % i,
              (0.31, 0.038, 0.052 if ladder else 0.17),
              (bx, by, z), D,
              mats["bar_wood"] if ladder else mats["paint_door"],
              rotation=(0, 0, rotation), bevel=0.012)
    # Two side rungs keep the chair structurally legible.
    for side in (-0.14, 0.14):
        a = (x + math.cos(rotation) * side - math.sin(rotation) * -0.14,
             y + math.sin(rotation) * side + math.cos(rotation) * -0.14,
             0.24)
        b = (x + math.cos(rotation) * side - math.sin(rotation) * 0.14,
             y + math.sin(rotation) * side + math.cos(rotation) * 0.14,
             0.24)
        L.cylinder_between(name + "_SideRung_%s" %
                           ("E" if side > 0 else "W"), 0.010, a, b, D,
                           mats["bar_wood"], segments=8)


def _metal_chair(name, x, y, rotation, mats):
    """Cheap vinyl-and-tube chair acquired in a different decade."""
    seat_z = 0.45
    seat = L.box(name + "_Seat", (0.39, 0.38, 0.060), (x, y, seat_z), D,
                 mats["vinyl_red"], rotation=(0, 0, rotation), bevel=0.030,
                 bevel_segments=3)
    seat["furniture_variant"] = "vinyl_tube_chair"
    for sx in (-0.145, 0.145):
        for sy in (-0.13, 0.13):
            dx = math.cos(rotation) * sx - math.sin(rotation) * sy
            dy = math.sin(rotation) * sx + math.cos(rotation) * sy
            L.cylinder(name + "_Leg_%s_%s" %
                       ("E" if sx > 0 else "W", "N" if sy > 0 else "S"),
                       0.012, 0.43, (x + dx, y + dy, 0.215), D,
                       mats["blacksteel"], segments=10)
    bx = x - math.sin(rotation) * 0.165
    by = y + math.cos(rotation) * 0.165
    for sx in (-0.14, 0.14):
        px = bx + math.cos(rotation) * sx
        py = by + math.sin(rotation) * sx
        L.cylinder(name + "_BackPost_%s" % ("E" if sx > 0 else "W"),
                   0.012, 0.45, (px, py, 0.69), D, mats["blacksteel"],
                   segments=10)
    L.box(name + "_BackPad", (0.32, 0.055, 0.18),
          (bx, by, 0.80), D, mats["vinyl_red"],
          rotation=(0, 0, rotation), bevel=0.035, bevel_segments=3)


def _folding_chair(name, x, y, rotation, mats):
    """Painted steel folding chair, a plausible cheap replacement acquisition."""
    seat = L.box(name + "_Seat", (0.36, 0.34, 0.040),
                 (x, y, 0.45), D, mats["paint_door"],
                 rotation=(0, 0, rotation), bevel=0.018, bevel_segments=3)
    seat["furniture_variant"] = "steel_folding"
    # Two X frames on the chair sides make the folding mechanism explicit.
    # The lower tube centrelines sit one projected radius above the slab so the
    # diagonal cylinders touch the floor instead of penetrating it.
    foot_z = 0.0065
    for side in (-0.145, 0.145):
        p0x = x + math.cos(rotation) * side
        p0y = y + math.sin(rotation) * side
        dyx, dyy = -math.sin(rotation) * 0.13, math.cos(rotation) * 0.13
        L.cylinder_between(name + "_XFrame_%s_A" %
                           ("E" if side > 0 else "W"), 0.011,
                           (p0x - dyx, p0y - dyy, foot_z),
                           (p0x + dyx, p0y + dyy, 0.46), D,
                           mats["blacksteel"], segments=10)
        L.cylinder_between(name + "_XFrame_%s_B" %
                           ("E" if side > 0 else "W"), 0.011,
                           (p0x + dyx, p0y + dyy, foot_z),
                           (p0x - dyx, p0y - dyy, 0.46), D,
                           mats["blacksteel"], segments=10)
    bx = x - math.sin(rotation) * 0.15
    by = y + math.cos(rotation) * 0.15
    L.box(name + "_Back", (0.31, 0.040, 0.16),
          (bx, by, 0.78), D, mats["paint_door"],
          rotation=(0, 0, rotation), bevel=0.025, bevel_segments=3)


def _cafe_table(name, x, y, radius, mats, square=False, yaw=0.0):
    if square:
        top = L.box(name + "_Top", (radius * 1.78, radius * 1.62, 0.045),
                    (x, y, 0.735), D, mats["bar_wood"],
                    rotation=(0, 0, yaw), bevel=0.016, bevel_segments=3)
        top["furniture_variant"] = "square_four_leg_table"
        for sx in (-radius * 0.58, radius * 0.58):
            for sy in (-radius * 0.50, radius * 0.50):
                px = x + math.cos(yaw) * sx - math.sin(yaw) * sy
                py = y + math.sin(yaw) * sx + math.cos(yaw) * sy
                L.box(name + "_Leg_%s_%s" %
                      ("E" if sx > 0 else "W", "N" if sy > 0 else "S"),
                      (0.035, 0.035, 0.69), (px, py, 0.345), D,
                      mats["bar_wood"], rotation=(0, 0, yaw), bevel=0.004)
    else:
        top = L.cylinder(name + "_Top", radius, 0.045, (x, y, 0.735), D,
                         mats["bar_wood"], segments=36)
        top["furniture_variant"] = "round_pedestal_table"
        L.cylinder(name + "_Post", 0.038, 0.69, (x, y, 0.365), D,
                   mats["blacksteel"], segments=16)
        L.cylinder(name + "_Foot", radius * 0.58, 0.025,
                   (x, y, 0.0125), D, mats["blacksteel"], segments=28)


def _frame_east(name, y, z, width, height, mats):
    """Four-piece dark frame on the east wall."""
    x = HW - 0.040
    rail = 0.035
    for dz in (-height / 2.0, height / 2.0):
        L.box("PROP_%s_Frame_%s" % (name, "B" if dz < 0 else "T"),
              (0.025, width + rail * 2.0, rail), (x, y, z + dz), D,
              mats["frame_dark"], bevel=0.003)
    for dy in (-width / 2.0, width / 2.0):
        L.box("PROP_%s_Frame_%s" % (name, "S" if dy < 0 else "N"),
              (0.025, rail, height), (x, y + dy, z), D,
              mats["frame_dark"], bevel=0.003)


def _frame_rear(name, x, z, width, height, mats):
    """Four-piece dark frame on the rear wall."""
    y = HL - 0.040
    rail = 0.035
    for dz in (-height / 2.0, height / 2.0):
        L.box("PROP_%s_Frame_%s" % (name, "B" if dz < 0 else "T"),
              (width + rail * 2.0, 0.025, rail), (x, y, z + dz), D,
              mats["frame_dark"], bevel=0.003)
    for dx in (-width / 2.0, width / 2.0):
        L.box("PROP_%s_Frame_%s" % (name, "W" if dx < 0 else "E"),
              (rail, 0.025, height), (x + dx, y, z), D,
              mats["frame_dark"], bevel=0.003)


def build_wall_art(mats):
    """Paper history bonded directly to the wall, never a clean gallery."""
    art_mats = {
        "payphones": mats["art_payphones"],
        "tuesday_8ball": mats["art_tuesday_8ball"],
        "sticker_wall": mats["art_sticker_wall"],
        "pool_team": mats["art_pool_team"],
    }
    for name, wall, horizontal, z, width, height, tilt in C.DD_WALL_ART_LAYOUT:
        if wall == "east":
            ob = L.image_plane("PROP_Art_" + name, width, height,
                               (HW - 0.006, horizontal, z), D,
                               art_mats[name], wall_axis="X",
                               rotation=(radians(tilt), 0, 0),
                               face_inward=True)
            ob["mounting_method"] = "wheat_pasted_directly_to_wall"
            ob["relief_mm"] = 0.0
        else:
            ob = L.image_plane("PROP_Art_" + name, width, height,
                               (horizontal, HL - 0.006, z), D,
                               art_mats[name], wall_axis="Y",
                               rotation=(0, radians(tilt), 0),
                               face_inward=False)
            ob["mounting_method"] = "wheat_pasted_directly_to_wall"
            ob["relief_mm"] = 0.0

    # Smaller orphaned notices share the same flush condition. Their history
    # is visible as fading and torn imagery, not as thick floating rectangles.
    scraps = [
        (1.74, 1.30, -0.7, 0.28, 0.34, "paper_aged"),
        (3.65, 1.42, 1.3, 0.22, 0.30, "paper_red"),
        (-1.58, 1.56, -2.0, 0.30, 0.21, "paper_aged"),
    ]
    for i, (y, z, tilt, width, height, mk) in enumerate(scraps):
        ob = L.image_plane("PROP_WallNotice_%02d" % i, width, height,
                           (HW - 0.0055, y, z), D, mats[mk], wall_axis="X",
                           rotation=(radians(tilt), 0, 0), face_inward=True)
        ob["mounting_method"] = "wheat_pasted_directly_to_wall"


def build_memory_wall(mats):
    """A photo accretion pasted almost flush into the west-wall paint."""
    x, y, z = -HW + 0.006, 1.58, 2.02
    collage = L.image_plane("PROP_MemoryCollage_00", 2.32, 1.39,
                            (x, y, z), D,
                            mats["art_memory_wall"], wall_axis="X",
                            rotation=(radians(-0.7), 0, 0),
                            face_inward=False)
    collage["mounting_method"] = "wheat_pasted_directly_to_wall"
    collage["relief_mm"] = 0.0

    # Orphaned snapshots are also paper-thin; none carries a frame or pin that
    # would throw the floating shadows the prior wall treatment produced.
    pieces = (
        (-0.38, 1.74, 0.33, 0.25, -4.0, "old_snapshot"),
        (3.08, 2.25, 0.31, 0.22, 3.0, "old_snapshot"),
        (3.46, 1.68, 0.22, 0.28, -5.0, "paper_aged"),
        (3.74, 2.13, 0.27, 0.19, 2.0, "old_snapshot"),
    )
    for i, (py, pz, width, height, tilt, mat) in enumerate(pieces, 1):
        print_ob = L.image_plane("PROP_MemoryPrint_%02d" % i,
                                 width, height, (x, py, pz), D, mats[mat],
                                 wall_axis="X",
                                 rotation=(radians(tilt), 0, 0),
                                 face_inward=False)
        print_ob["mounting_method"] = "wheat_pasted_directly_to_wall"
        if i == 3:
            # Faded handwritten rows keep this small notice from reading as a
            # freshly mounted blank rectangle. They remain illegible at room
            # distance, as a decades-old phone list or score note would.
            for line, (dy, dz, length) in enumerate((
                    (-0.010, 0.070, 0.135), (0.015, 0.025, 0.115),
                    (-0.005, -0.020, 0.145), (0.020, -0.065, 0.090))):
                L.box("PROP_MemoryNoticeInk_%d" % line,
                      (0.0008, length, 0.004),
                      (x + 0.001, py + dy, pz + dz), D,
                      mats["paper_red"],
                      rotation=(radians(tilt), 0, 0), bevel=0.0003)

    # Hooks and permanently forgotten coats occupy the last strip before the
    # rear doors, with weight visibly hanging from the rail.
    for i, y in enumerate((4.58, 4.88, 5.18)):
        L.cylinder("PROP_CoatHook_%d" % i, 0.014, 0.12,
                   (-HW + 0.095, y, 1.67), D, mats["brass"], segments=12,
                   rotation=(0, radians(90), 0))
        if i != 1:
            L.box("PROP_HangingCoat_%d" % i, (0.13, 0.34, 0.78),
                  (-HW + 0.13, y, 1.20), D,
                  mats["paint_door"] if i == 0 else mats["bar_wood"],
                  rotation=(radians(-4 + i * 5), 0, 0), bevel=0.055,
                  bevel_segments=3)


def build_dartboard_and_clock(mats):
    # Dartboard on the east wall, outside the table's cue envelope.
    x, y, z = HW - 0.055, 4.20, 1.72
    L.cylinder("PROP_Dartboard_Back", 0.255, 0.040, (x, y, z), D,
               mats["frame_dark"], segments=48,
               rotation=(0, radians(90), 0))
    for i, (radius, mat) in enumerate(((0.225, mats["paper_aged"]),
                                       (0.158, mats["blacksteel"]),
                                       (0.096, mats["paper_red"]),
                                       (0.035, mats["wall_panel"]))):
        L.cylinder("PROP_Dartboard_Ring_%d" % i, radius, 0.008,
                   (x - 0.026 - i * 0.003, y, z), D, mat, segments=48,
                   rotation=(0, radians(90), 0))
    wire_x = x - 0.061
    for ring_i, radius in enumerate((0.092, 0.154, 0.192, 0.221)):
        L.ring("PROP_Dartboard_WireRing_%d" % ring_i,
               radius - 0.003, radius + 0.003, 0.004,
               (wire_x, y, z), D, mats["brass"], segments=64,
               rotation=(0, radians(90), 0))
    for spoke in range(20):
        angle = 2.0 * math.pi * spoke / 20.0
        L.cylinder_between("PROP_Dartboard_Spoke_%02d" % spoke, 0.0022,
                           (wire_x - 0.003, y, z),
                           (wire_x - 0.003, y + math.cos(angle) * 0.221,
                            z + math.sin(angle) * 0.221), D,
                           mats["brass"], segments=6, smooth=False)

    # Slow old clock above the rear chair rail.
    cx, cy, cz = -0.96, HL - 0.050, 2.35
    L.cylinder("PROP_WallClock_Frame", 0.205, 0.050, (cx, cy, cz), D,
               mats["frame_dark"], segments=48,
               rotation=(radians(90), 0, 0))
    L.cylinder("PROP_WallClock_Face", 0.176, 0.012,
               (cx, cy - 0.030, cz), D, mats["paper_aged"], segments=48,
               rotation=(radians(90), 0, 0))
    for hour in range(12):
        angle = 2.0 * math.pi * hour / 12.0
        r0, r1 = 0.137, 0.156
        L.cylinder_between("PROP_WallClock_Mark_%02d" % hour, 0.003,
                           (cx + math.sin(angle) * r0, cy - 0.039,
                            cz + math.cos(angle) * r0),
                           (cx + math.sin(angle) * r1, cy - 0.039,
                            cz + math.cos(angle) * r1), D,
                           mats["blacksteel"], segments=6, smooth=False)
    L.box("PROP_WallClock_Hand_Hour", (0.016, 0.014, 0.100),
          (cx - 0.022, cy - 0.041, cz + 0.040), D, mats["blacksteel"],
          rotation=(0, radians(-28), 0), bevel=0.003)
    L.box("PROP_WallClock_Hand_Minute", (0.014, 0.014, 0.145),
          (cx + 0.045, cy - 0.042, cz - 0.010), D, mats["blacksteel"],
          rotation=(0, radians(58), 0), bevel=0.003)
    L.cylinder("PROP_WallClock_CentrePin", 0.009, 0.014,
               (cx, cy - 0.045, cz), D, mats["brass"], segments=14,
               rotation=(radians(90), 0, 0))


def build_pool_wall(mats):
    # Wall cue rack and five full-length cues on the rear wall.
    rack_y = HL - 0.080
    rack_x = 0.00
    L.box("PROP_CueRack_Top", (1.08, 0.085, 0.105),
          (rack_x, rack_y, 1.76), D, mats["bar_wood"], bevel=0.012)
    L.box("PROP_CueRack_Bottom", (1.08, 0.11, 0.075),
          (rack_x, rack_y, 0.36), D, mats["bar_wood"], bevel=0.010)
    cue_specs = ((-0.43, -0.018, 1.405), (-0.22, 0.012, 1.385),
                 (0.00, -0.009, 1.415), (0.23, 0.020, 1.365),
                 (0.43, -0.014, 1.398))
    for i, (x, lean, cue_h) in enumerate(cue_specs):
        start = (rack_x + x, rack_y - 0.045, 0.39)
        end = (rack_x + x + lean, rack_y - 0.045, 0.39 + cue_h)
        L.cylinder_between("PROP_WallCue_%d" % i, 0.012, start, end, D,
                           mats["bar_wood"], segments=14)
        L.cylinder_between("PROP_WallCueTip_%d" % i, 0.010, end,
                           (end[0] + lean * 0.02, end[1], end[2] + 0.030),
                           D, mats["paper_aged"], segments=12)
        L.box("PROP_CueRack_Clip_%d" % i, (0.042, 0.028, 0.035),
              (rack_x + x, rack_y - 0.092, 1.76), D, mats["blacksteel"],
              bevel=0.008)
    L.box("PROP_ChalkShelf", (0.62, 0.16, 0.040),
          (rack_x, rack_y - 0.025, 1.16), D, mats["bar_wood"], bevel=0.006)
    for i, (dx, dy, yaw) in enumerate(((-0.18, -0.012, -8),
                                       (-0.08, 0.006, 4),
                                       (0.06, -0.020, 13),
                                       (0.16, 0.011, -3))):
        L.box("PROP_ChalkCube_%d" % i, (0.026, 0.026, 0.026),
              (rack_x + dx, rack_y - 0.060 + dy, 1.193), D,
              mats["wall_panel"], rotation=(0, 0, radians(yaw)),
              bevel=0.003)

    # Three rows of old wooden score beads on the east wall.
    sx, sy, sz = HW - 0.078, 3.52, 2.36
    bead_offsets = (
        (-0.37, -0.31, -0.25, -0.19, 0.10, 0.16, 0.22, 0.28, 0.34,
         0.37, 0.40),
        (-0.37, -0.31, 0.00, 0.06, 0.12, 0.18, 0.24, 0.30, 0.34,
         0.38, 0.41),
        (-0.40, -0.36, -0.32, -0.28, -0.24, -0.20, 0.18, 0.24, 0.30,
         0.36, 0.40),
    )
    for row in range(3):
        z = sz - row * 0.105
        L.cylinder("PROP_ScoreRod_%d" % row, 0.008, 0.86,
                   (sx, sy, z), D, mats["brass"], segments=12,
                   rotation=(radians(90), 0, 0))
        # Two wall plates and short spacers make the scoring rods a mounted
        # fixture instead of three lines hovering 78 mm off the masonry.
        for side, tag in ((-1, "S"), (1, "N")):
            mount_y = sy + side * 0.40
            L.box("PROP_ScorePlate_%d_%s" % (row, tag),
                  (0.012, 0.055, 0.055),
                  (HW - 0.006, mount_y, z), D, mats["blacksteel"],
                  bevel=0.006)
            L.cylinder_between("PROP_ScoreBracket_%d_%s" % (row, tag),
                               0.008,
                               (HW - 0.012, mount_y, z),
                               (sx, mount_y, z), D, mats["brass"],
                               segments=10)
        for bead, offset in enumerate(bead_offsets[row]):
            by = sy + offset
            L.uv_sphere("PROP_ScoreBead_%d_%02d" % (row, bead), 0.019,
                        (sx - 0.016, by, z), D,
                        mats["paper_red"] if (bead + row) % 3 == 0 else
                        mats["bar_wood"], segments=18, rings=10)


def build_bar_clutter(mats):
    """A wiped working bar top: fruit, napkins and a tip jar, not debris."""
    bar_x = C.DD_BAR_TOP_X
    bar_y = C.DD_BAR_CENTRE_Y
    # BAR_Top's modeled upper face is 0.5 mm above the nominal 42-inch datum.
    top = C.BAR_HEIGHT + 0.0005
    clutter = random.Random(91)

    # A shallow old enamel bowl contains unmistakable whole fruit. Each piece
    # has a stem and a slightly different silhouette, so no pale sphere can be
    # mistaken for an egg. The remaining counter is deliberately open.
    bowl_y = bar_y - 0.78
    # Close both the underside and the enamelled basin at the rotation axis.
    # The earlier ring-only profile began 55 mm away from the axis and was
    # then placed 6 mm above the counter; together those choices made the bowl
    # itself read as hovering even after the fruit was correctly contained.
    bowl_profile = ((0.000, 0.000), (0.055, 0.000), (0.145, 0.008),
                    (0.190, 0.030), (0.205, 0.065), (0.190, 0.082),
                    (0.178, 0.064), (0.135, 0.032), (0.052, 0.015),
                    (0.000, 0.015))
    bowl = L.revolved_surface("PROP_BarFruitBowl", bowl_profile, D,
                              mats["enamel_green"], segments=48,
                              location=(bar_x, bowl_y, top),
                              close_profile=True)
    bowl["counter_state"] = "clean_and_wiped"
    bowl["support_z"] = round(top, 5)
    bowl["rim_z"] = round(top + 0.082, 5)
    bowl["interior_support"] = "sloped_enamel_basin"

    def basin_height(radial):
        """Piecewise inner-basin height at a fruit's radial location."""
        knots = ((0.000, 0.015), (0.052, 0.015),
                 (0.135, 0.032), (0.178, 0.064))
        for (r0, z0), (r1, z1) in zip(knots, knots[1:]):
            if radial <= r1:
                t = (radial - r0) / max(r1 - r0, 1e-9)
                return z0 + max(0.0, min(1.0, t)) * (z1 - z0)
        return knots[-1][1]
    # Five fruit sit in the basin and three nest on the lower cluster. The old
    # four-plus-four staging raised every lowest point above the rim, which is
    # why the entire arrangement visibly floated.
    fruit = (
        (-0.095, -0.055, 0.050, "fruit_apple", 0.96, 1.00, 0),
        (0.000, -0.082, 0.047, "garnish_orange", 1.03, 0.98, 0),
        (0.095, -0.045, 0.044, "fruit_lemon", 0.92, 1.18, 0),
        (-0.065, 0.045, 0.045, "garnish_orange", 1.04, 0.96, 0),
        (0.045, 0.045, 0.049, "fruit_apple", 0.98, 1.05, 0),
        (-0.045, -0.025, 0.043, "fruit_lemon", 0.90, 1.20, 1),
        (0.047, -0.008, 0.044, "garnish_orange", 1.02, 0.97, 1),
        (0.008, 0.065, 0.045, "fruit_apple", 0.97, 1.04, 1),
    )
    for i, (dx, dy, radius, mat, sx, sz, layer) in enumerate(fruit):
        radial = math.hypot(dx, dy)
        if layer == 0:
            support_z = top + basin_height(radial)
            # Two millimetres of deliberate mesh engagement prevents a
            # renderer-scale daylight seam without visibly burying the fruit.
            z = support_z + radius * sz - 0.002
        else:
            support_z = None
            z = top + 0.145 + (i % 2) * 0.003
        ob = L.uv_sphere("PROP_BarFruit_%02d" % i, radius,
                         (bar_x + dx, bowl_y + dy, z), D, mats[mat],
                         segments=28, rings=16)
        ob.scale = (sx, 1.0, sz)
        # Bake only the deliberate fruit silhouette, preserving the authored
        # world location. ``apply_transforms`` would bake location as well and
        # can read a stale matrix before Blender updates the dependency graph.
        for vertex in ob.data.vertices:
            vertex.co.x *= sx
            vertex.co.z *= sz
        ob.scale = (1.0, 1.0, 1.0)
        ob["food_type"] = "whole_fruit_not_eggs"
        ob["service_state"] = "fresh_and_presentable"
        ob["fruit_layer"] = layer
        ob["support_state"] = "bowl_interior" if layer == 0 else \
            "nested_on_lower_fruit"
        ob["nominal_radius_m"] = radius
        ob["owning_container"] = bowl.name
        if support_z is not None:
            ob["support_z"] = round(support_z, 5)
        L.cylinder("PROP_BarFruitStem_%02d" % i, 0.0045, 0.026,
                   (bar_x + dx, bowl_y + dy, z + radius * sz + 0.009), D,
                   mats["bar_wood"], segments=9,
                   rotation=(radians(-7 + i * 2), 0, radians(i * 29)))

    L.box("PROP_NapkinHolder", (0.12, 0.16, 0.15),
          (bar_x + 0.01, bar_y + 0.32, top + 0.075), D,
          mats["blacksteel"], bevel=0.010)
    for i in range(7):
        L.box("PROP_Napkin_%d" % i, (0.095, 0.120, 0.004),
              (bar_x + 0.015 + clutter.uniform(-0.004, 0.004),
               bar_y + 0.32 + clutter.uniform(-0.006, 0.006),
               top + 0.155 + i * 0.003), D, mats["paper_aged"],
              rotation=(0, 0, radians(-7 + i * 1.7)))

    # A repurposed open glass jar at the end is the only other loose counter
    # object. It has real wall/base thickness and folded bills inside; the old
    # solid transparent cylinder read as an implausible opaque metal can in a
    # grazing barware view.
    jar_x, jar_y = bar_x + 0.02, bar_y - 1.50
    jar_profile = ((0.048, 0.000), (0.060, 0.006), (0.060, 0.155),
                   (0.057, 0.170), (0.053, 0.170), (0.056, 0.012),
                   (0.045, 0.012))
    jar = L.revolved_surface("PROP_TipJar", jar_profile, D,
                             mats["glass_clear"], segments=40,
                             location=(jar_x, jar_y, top),
                             close_profile=True)
    jar["counter_state"] = "clean_and_wiped"
    jar["container_type"] = "repurposed_open_glass_tip_jar"
    for i, (dx, dy, z, yaw, tilt) in enumerate((
            (-0.012, -0.005, 0.032, -18, 12),
            (0.014, 0.008, 0.052, 21, -9),
            (-0.004, 0.004, 0.074, 6, 16),
            (0.010, -0.010, 0.090, -27, -12))):
        bill = L.box("PROP_TipJar_Bill_%d" % i,
                     (0.046, 0.024, 0.0010),
                     (jar_x + dx, jar_y + dy, top + z), D,
                     mats["paper_aged"],
                     rotation=(radians(tilt), radians(5 - i * 2),
                               radians(yaw)), bevel=0.0004)
        bill["payment_state"] = "folded_tip_inside_jar"


def build_front_seating(mats):
    """Two tiny front-room tables with chairs bought years apart."""
    for i, (x, y, radius) in enumerate(C.DD_CAFE_TABLE_LAYOUT):
        name = "PROP_CafeTable_%d" % i
        _cafe_table(name, x, y, radius, mats, square=(i == 1),
                    yaw=radians(7 if i else 0))
        if i == 0:
            _wood_chair("PROP_CafeChair_0_Wood", x - 0.51, y - 0.05,
                        radians(82), mats, ladder=True)
            _metal_chair("PROP_CafeChair_0_Metal", x + 0.39, y + 0.13,
                         radians(-104), mats)
        else:
            _folding_chair("PROP_CafeChair_1_Folding", x - 0.46, y - 0.17,
                           radians(101), mats)
            _wood_chair("PROP_CafeChair_1_Wood", x + 0.39, y + 0.10,
                        radians(-77), mats, ladder=False)
        if i == 0:
            L.cylinder(name + "_Ashtray", 0.065, 0.025,
                       (x + 0.10, y - 0.06, 0.770), D, mats["stainless"],
                       segments=24)
        else:
            # Folded matchbook and one sugar jar make the second table a
            # different moment rather than a copied tabletop vignette.
            L.box(name + "_Matchbook", (0.055, 0.035, 0.008),
                  (x + 0.11, y + 0.04, 0.762), D, mats["paper_red"],
                  rotation=(0, 0, radians(21)), bevel=0.003)


def build_west_wall_vignette(mats):
    """Clearance-safe neighborhood-bar life along the otherwise blank wall."""
    wall_x = -HW

    # Heavy wall payphone, present long enough to have outlived its dial tone.
    py, pz = 0.20, 1.56
    L.box("PROP_WallPayphone_Body", (0.115, 0.31, 0.46),
          (wall_x + 0.072, py, pz), D, mats["blacksteel"], bevel=0.020,
          bevel_segments=3)
    L.box("PROP_WallPayphone_Face", (0.018, 0.225, 0.285),
          (wall_x + 0.139, py, pz + 0.045), D, mats["paper_aged"],
          bevel=0.008)
    L.box("PROP_WallPayphone_CoinSlot", (0.020, 0.052, 0.070),
          (wall_x + 0.151, py, pz + 0.145), D, mats["brass"], bevel=0.006)
    for dz in (-0.135, 0.135):
        L.cylinder("PROP_WallPayphone_Handset_%s" %
                   ("B" if dz < 0 else "T"), 0.035, 0.105,
                   (wall_x + 0.170, py - 0.185, pz + dz), D,
                   mats["blacksteel"], segments=16)
    L.box("PROP_WallPayphone_HandsetGrip", (0.075, 0.055, 0.265),
          (wall_x + 0.170, py - 0.185, pz), D, mats["blacksteel"],
          bevel=0.025, bevel_segments=3)
    cord_points = []
    for i in range(12):
        t = i / 11.0
        cord_points.append((wall_x + 0.155 + 0.010 * math.sin(t * math.pi),
                            py - 0.175 + 0.020 * math.sin(t * 8 * math.pi),
                            pz - 0.22 - 0.46 * t + 0.035 *
                            math.sin(t * 4 * math.pi)))
    L.curve_tube("PROP_WallPayphone_Cord", cord_points, 0.0055, D,
                 mats["blacksteel"])

    # Switched-off late-1980s CRT on a brutally practical steel wall bracket.
    ty, tz = 4.05, 2.42
    L.box("PROP_CRT_Bracket", (0.48, 0.10, 0.075),
          (wall_x + 0.24, ty, 2.13), D, mats["blacksteel"], bevel=0.010)
    for sy in (-0.22, 0.22):
        L.cylinder_between("PROP_CRT_BracketBrace_%s" %
                           ("S" if sy < 0 else "N"), 0.014,
                           (wall_x + 0.03, ty + sy, 1.98),
                           (wall_x + 0.43, ty + sy, 2.13), D,
                           mats["blacksteel"], segments=10)
    L.box("PROP_CRT_Body", (0.46, 0.72, 0.48),
          (wall_x + 0.25, ty, tz), D, mats["paint_door"], bevel=0.080,
          bevel_segments=4)
    L.box("PROP_CRT_Screen", (0.025, 0.56, 0.33),
          (wall_x + 0.492, ty, tz + 0.015), D, mats["tv_screen"],
          bevel=0.055, bevel_segments=4)
    for i in range(3):
        L.cylinder("PROP_CRT_Knob_%d" % i, 0.018, 0.018,
                   (wall_x + 0.510, ty + 0.25, tz - 0.105 + i * 0.075), D,
                   mats["blacksteel"], segments=14,
                   rotation=(0, radians(90), 0))
    L.curve_tube("PROP_CRT_PowerCable",
                 ((wall_x + 0.15, ty + 0.30, tz - 0.20),
                  (wall_x + 0.08, ty + 0.34, 2.08),
                  (wall_x + 0.04, ty + 0.38, 1.78),
                  (wall_x + 0.03, ty + 0.40, 1.22)), 0.006, D,
                 mats["blacksteel"])

    # Two compact NYC-style wall bays, not a continuous banquette. Each pair
    # of benches runs out from the west wall along X. Patrons enter at the open
    # east/pool end, slide toward the wall and face one another across Y.
    # Their upholstered backs separate the bays naturally; there are no tall
    # freestanding divider walls stealing floor area or inventing a corridor.
    for booth, (by, run_x, bay_w) in enumerate(C.DD_BOOTH_LAYOUT):
        prefix = "PROP_Booth_%d" % booth
        wall_gap = 0.115 if booth == 0 else 0.105
        bench_x = wall_x + wall_gap + run_x / 2.0
        open_edge_x = wall_x + wall_gap + run_x
        seat_depth = 0.42 if booth == 0 else 0.44
        back_t = 0.14
        back_h = 0.58 if booth == 0 else 0.51
        back_offset = bay_w / 2.0 - back_t / 2.0
        seat_offset = back_offset - 0.17
        back_z = 0.49 + back_h / 2.0 - 0.015
        upholstery = mats["vinyl_red"] if booth == 0 else mats["vinyl_green"]
        base_mat = mats["wall_panel"] if booth == 0 else mats["paint_door"]
        variant = "channel_vinyl_1940s" if booth == 0 \
            else "reupholstered_bottle_green_1960s"

        for side in (-1, 1):
            tag = "South" if side < 0 else "North"
            seat_y = by + side * seat_offset
            back_y = by + side * back_offset
            base = L.box(prefix + "_Bench%s_Base" % tag,
                         (run_x, seat_depth - 0.035, 0.43),
                         (bench_x, seat_y, 0.215), D, base_mat,
                         bevel=0.020)
            base["furniture_variant"] = variant
            base["seat_facing"] = "north" if side < 0 else "south"
            L.box(prefix + "_Bench%s_Seat" % tag,
                  (run_x + 0.025, seat_depth, 0.13),
                  (bench_x + 0.010, seat_y - side * 0.010, 0.49), D,
                  upholstery, bevel=0.050, bevel_segments=4)
            L.box(prefix + "_Bench%s_Back" % tag,
                  (run_x + 0.015, back_t, back_h),
                  (bench_x, back_y, back_z), D, upholstery,
                  rotation=(radians(-side * (4.0 if booth == 0 else 2.5)),
                            0, 0),
                  bevel=0.055, bevel_segments=4)

            # The old raised seam strips were deleted: from a close camera they
            # cast implausible black bars. This reupholstery reads as a plain
            # continuous panel, with fine checking supplied by the patina pass.
            L.box(prefix + "_Bench%s_AisleEndCap" % tag,
                  (0.052, back_t + 0.025, back_h + 0.055),
                  (open_edge_x - 0.026, back_y, back_z), D,
                  mats["bar_wood"], bevel=0.008)

        # The table's short edge is cleated to the wall and one pedestal bears
        # the open end. This leaves the pool-side mouth unobstructed for entry.
        table_run = 0.88 if booth == 0 else 0.84
        table_w = 0.46 if booth == 0 else 0.48
        table_x = wall_x + wall_gap + table_run / 2.0
        top = L.box(prefix + "_TableTop", (table_run, table_w, 0.050),
                    (table_x, by, 0.735), D, mats["bar_wood"], bevel=0.018)
        top["access_side"] = "east_pool_table_aisle"
        top["bench_axis"] = "X_perpendicular_to_west_wall"
        top["patron_facing_axis"] = "Y_face_to_face"
        top["wall_relationship"] = "short_edge_cleated_to_west_wall"
        top["open_entry_x"] = round(open_edge_x, 4)
        L.box(prefix + "_TableWallCleat", (0.085, table_w + 0.07, 0.11),
              (wall_x + 0.048, by, 0.675), D, mats["blacksteel"],
              bevel=0.006)
        post_x = table_x + table_run * 0.25
        L.cylinder(prefix + "_TablePost", 0.039 if booth == 0 else 0.044,
                   0.69, (post_x, by, 0.365), D, mats["blacksteel"],
                   segments=16)
        if booth == 0:
            L.cylinder(prefix + "_TableFoot", 0.165, 0.025,
                       (post_x, by, 0.0125), D, mats["blacksteel"],
                       segments=24)
        else:
            L.box(prefix + "_TableFoot", (0.34, 0.38, 0.025),
                  (post_x, by, 0.0125), D, mats["blacksteel"],
                  bevel=0.020, bevel_segments=3)

        if booth != 0:
            # One overlapping field repair on the inner face of the north
            # back. It follows the upholstery plane instead of floating near it.
            repair_y = by + back_offset - (back_t / 2.0 + 0.008)
            for strip, (dx, dz, length, angle) in enumerate((
                    (-0.012, -0.035, 0.145, -3.0),
                    (0.004, 0.000, 0.160, 1.5),
                    (-0.008, 0.035, 0.132, -1.0))):
                patch = L.box(prefix + "_NorthBackRepairTape_%d" % strip,
                              (length, 0.009, 0.038),
                              (bench_x + 0.12 + dx, repair_y,
                               back_z + 0.03 + dz), D, mats["tape_black"],
                              rotation=(0, radians(angle), 0), bevel=0.004)
                patch["repair_method"] = "overlapping_black_vinyl_tape"


def build(mats):
    L.clear_collection(D)
    build_wall_art(mats)
    build_memory_wall(mats)
    build_dartboard_and_clock(mats)
    build_pool_wall(mats)
    build_bar_clutter(mats)
    build_front_seating(mats)
    build_west_wall_vignette(mats)
    n = len(L.get_collection(D).objects)
    print("  [set dressing] %d objects (period art, pool wall, bar clutter)" % n)
    return True


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
