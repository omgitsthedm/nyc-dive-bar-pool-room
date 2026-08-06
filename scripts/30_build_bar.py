"""
30_build_bar.py — the bar, back bar, and stools, forward of the cue envelope.

The bar has a working bartender side: service counter, sink, speed rail, taps,
glass racks. It sits along the west wall in the front half so it never intrudes
on the 9-foot table's cue clearance.

Owns: 04_BAR.
"""
import bpy
import math
import os
import random
import sys
from math import cos, radians, sin

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

B = "04_BAR"
HW, HL = C.ROOM_W / 2.0, C.ROOM_L / 2.0
BAR_X = C.DD_BAR_TOP_X                # guest top centre, front zone only
BAR_Y = C.DD_BAR_CENTRE_Y            # centred south of cue envelope
BACK_X = C.DD_BACKBAR_X              # shallow wall-mounted backbar
SERVICE_X = C.DD_BAR_SERVICE_X        # east edge meets the inner bar die
BT = C.BAR_HEIGHT


def _local_xy(cx, cy, dx, dy, yaw):
    """Transform a furniture-local point by yaw around its floor contact."""
    return (cx + math.cos(yaw) * dx - math.sin(yaw) * dy,
            cy + math.sin(yaw) * dx + math.cos(yaw) * dy)


def _cash_register(mats):
    """Ornate 1900s barrel-front register, bartender equipment not décor.

    Modeled on the brass National-class machines used behind bars for the
    whole century: a cast base with the cash drawer, a convex drum front
    carrying columns of round ivory-capped keys, proud scrolled side cheeks,
    a glass-front indicator crown with flag cards, a working side crank and
    paw feet.  Every cast surface uses the chased-bronze relief material so
    the machine reads engraved, not sheet-metal.
    """
    bx = BACK_X
    x, y, z0 = bx + 0.20, BAR_Y, 0.92
    bronze = mats["bronze_ornate"]

    # Four paw feet under the base corners.
    for sx_, sy_ in ((-0.145, -0.185), (-0.145, 0.185),
                     (0.145, -0.185), (0.145, 0.185)):
        L.cylinder("BAR_CashRegister_Foot_%s%s" %
                   ("S" if sy_ < 0 else "N", "W" if sx_ < 0 else "E"),
                   0.024, 0.030, (x + sx_, y + sy_, z0 + 0.015), B,
                   mats["brass"], segments=16)

    # Cast base with the cash drawer facing +X into the bartender aisle.
    base = L.box("BAR_CashRegister_Base", (0.36, 0.44, 0.105),
                 (x, y, z0 + 0.0825), B, bronze, bevel=0.014,
                 bevel_segments=3)
    base["workflow_side"] = "backbar_facing_bartender"
    base["period_family"] = "early_mechanical_register"
    L.box("BAR_CashRegister_Drawer", (0.030, 0.36, 0.078),
          (x + 0.192, y, z0 + 0.078), B, bronze, bevel=0.006)
    L.box("BAR_CashRegister_DrawerPull", (0.018, 0.11, 0.024),
          (x + 0.213, y, z0 + 0.070), B, mats["brass"], bevel=0.006)

    # Body core behind the drum.
    L.box("BAR_CashRegister_Body", (0.24, 0.40, 0.25),
          (x - 0.05, y, z0 + 0.26), B, bronze, bevel=0.018,
          bevel_segments=3)

    # Convex drum front: the barrel the key columns wrap around.
    L.cylinder("BAR_CashRegister_Drum", 0.145, 0.40,
               (x + 0.010, y, z0 + 0.275), B, bronze, segments=48,
               rotation=(radians(90), 0, 0))

    # Five key columns follow the drum curve; each round brass key carries
    # an ivory cap, sitting normal to the barrel surface.
    drum_cx, drum_cz, drum_r = x + 0.010, z0 + 0.275, 0.145
    for col in range(5):
        ky = y - 0.14 + col * 0.07
        for rank in range(5):
            theta = radians(-28 + rank * 19)
            rx = drum_cx + cos(theta) * (drum_r + 0.008)
            rz = drum_cz + sin(theta) * (drum_r + 0.008)
            rot = (0, radians(90) - theta, 0)
            L.cylinder("BAR_CashRegister_Key_%d_%d" % (rank, col),
                       0.0135, 0.020, (rx, ky, rz), B, mats["brass"],
                       segments=16, rotation=rot)
            cx2 = drum_cx + cos(theta) * (drum_r + 0.020)
            cz2 = drum_cz + sin(theta) * (drum_r + 0.020)
            L.cylinder("BAR_CashRegister_KeyCap_%d_%d" % (rank, col),
                       0.0095, 0.006, (cx2, ky, cz2), B,
                       mats["ivory_key"], segments=14, rotation=rot)

    # Proud scrolled side cheeks close the drum ends completely: the cheek
    # must reach past the drum's front arc or the bare barrel end shows as
    # a dark disc beside the key field.
    for sy_ in (-1, 1):
        L.box("BAR_CashRegister_SideCheek_%s" % ("S" if sy_ < 0 else "N"),
              (0.37, 0.024, 0.315),
              (x - 0.005, y + sy_ * 0.212, z0 + 0.272), B, bronze,
              bevel=0.012, bevel_segments=3)

    # Indicator crown: glass front, five flag cards, cast cornice and ridge.
    L.box("BAR_CashRegister_IndicatorHousing", (0.125, 0.38, 0.150),
          (x - 0.065, y, z0 + 0.470), B, bronze, bevel=0.014,
          bevel_segments=3)
    L.box("BAR_CashRegister_IndicatorGlass", (0.014, 0.30, 0.100),
          (x + 0.002, y, z0 + 0.470), B, mats["tv_screen"], bevel=0.006)
    for col in range(5):
        L.box("BAR_CashRegister_DisplayCard_%d" % col,
              (0.007, 0.042, 0.062),
              (x + 0.010, y - 0.104 + col * 0.052, z0 + 0.468), B,
              mats["paper_aged"], bevel=0.002)
    L.box("BAR_CashRegister_Cornice", (0.155, 0.42, 0.028),
          (x - 0.065, y, z0 + 0.558), B, bronze, bevel=0.010,
          bevel_segments=3)
    L.box("BAR_CashRegister_CrownRidge", (0.100, 0.30, 0.020),
          (x - 0.065, y, z0 + 0.580), B, bronze, bevel=0.008)

    # Side crank on the machine's flank, mechanically connected.
    L.cylinder("BAR_CashRegister_CrankShaft", 0.013, 0.070,
               (drum_cx, y + 0.245, drum_cz), B, mats["blacksteel"],
               segments=14, rotation=(radians(90), 0, 0))
    L.cylinder_between("BAR_CashRegister_CrankArm", 0.011,
                       (drum_cx, y + 0.276, drum_cz),
                       (drum_cx + 0.075, y + 0.276, drum_cz - 0.045), B,
                       mats["blacksteel"], segments=12)
    L.cylinder("BAR_CashRegister_CrankGrip", 0.016, 0.085,
               (drum_cx + 0.075, y + 0.318, drum_cz - 0.045), B,
               mats["bar_wood"], segments=14,
               rotation=(radians(90), 0, 0))


def _stock_bottle(name, family, x, y, support_z, h, r, yaw, mats, rnd,
                  stock=True):
    """One supported bottle with a real shoulder/neck profile and front label."""
    profiles = {
        "round_whiskey": [(r * 0.92, 0.0), (r, 0.012), (r, h * 0.62),
                           (r * 0.92, h * 0.69), (r * 0.48, h * 0.78),
                           (r * 0.34, h * 0.82), (r * 0.34, h)],
        "longneck": [(r * 0.86, 0.0), (r, 0.012), (r, h * 0.58),
                     (r * 0.82, h * 0.66), (r * 0.40, h * 0.76),
                     (r * 0.30, h * 0.82), (r * 0.30, h)],
        "wine": [(r * 0.84, 0.0), (r, 0.015), (r, h * 0.60),
                 (r * 0.90, h * 0.69), (r * 0.48, h * 0.78),
                 (r * 0.28, h * 0.84), (r * 0.28, h)],
        "squat_liqueur": [(r * 0.88, 0.0), (r, 0.014), (r, h * 0.55),
                          (r * 0.78, h * 0.65), (r * 0.44, h * 0.74),
                          (r * 0.36, h * 0.80), (r * 0.36, h)],
        "bell_decanter": [(r * 0.72, 0.0), (r, 0.025),
                          (r * 0.94, h * 0.46), (r * 0.70, h * 0.62),
                          (r * 0.36, h * 0.75), (r * 0.32, h)],
    }
    bottle_mats = (mats["glass_bottle"], mats["glass_amber"],
                   mats["glass_clear"])
    bmat = bottle_mats[rnd.randrange(len(bottle_mats))]
    if family in profiles:
        body = L.lathe(name, profiles[family], B, bmat, segments=24,
                       location=(x, y, support_z))
    else:
        # Two rectangular families break the forest of round silhouettes.
        body_h = h * (0.70 if family == "square_whiskey" else 0.64)
        width = r * (1.80 if family == "square_whiskey" else 1.55)
        depth = r * (1.55 if family == "square_whiskey" else 1.20)
        body = L.box(name, (depth, width, body_h),
                     (x, y, support_z + body_h / 2.0), B, bmat,
                     rotation=(0, 0, yaw), bevel=r * 0.25,
                     bevel_segments=3)
        shoulder_z = support_z + body_h
        L.box(name + "_Shoulder", (depth * 0.76, width * 0.76, h * 0.10),
              (x, y, shoulder_z + h * 0.05), B, bmat,
              rotation=(0, 0, yaw), bevel=r * 0.22, bevel_segments=3)
        neck_h = h - body_h - h * 0.10
        L.cylinder(name + "_Neck", r * 0.32, neck_h,
                   (x, y, shoulder_z + h * 0.10 + neck_h / 2.0), B, bmat,
                   segments=16)
    body["stock_bottle"] = stock
    body["bottle_family"] = family
    body["support_z"] = support_z
    body["nominal_radius_m"] = r
    body["label_yaw_deg"] = round(math.degrees(yaw), 2)

    neck_r = r * (0.34 if family not in ("wine", "longneck") else 0.29)
    if stock:
        L.cylinder(name + "_Cap", neck_r * 1.05, 0.014,
                   (x, y, support_z + h + 0.007), B,
                   mats["brass"] if rnd.random() > 0.28 else
                   mats["paper_red"], segments=14)
    else:
        # Open well bottles use fitted speed pourers, not unopened caps.
        L.cylinder(name + "_PourCollar", neck_r * 1.10, 0.018,
                   (x, y, support_z + h + 0.009), B, mats["bar_rubber"],
                   segments=14)
        L.cylinder_between(name + "_PourSpout", 0.0055,
                           (x, y, support_z + h + 0.016),
                           (x + 0.022, y, support_z + h + 0.060), B,
                           mats["stainless"], segments=10)
    if rnd.random() > 0.16:
        label_h = h * rnd.uniform(0.18, 0.28)
        label_w = r * rnd.uniform(1.12, 1.48)
        lx = x + math.cos(yaw) * (r + 0.003)
        ly = y + math.sin(yaw) * (r + 0.003)
        label = L.box(name + "_Label", (0.004, label_w, label_h),
                      (lx, ly, support_z + h * rnd.uniform(0.38, 0.52)), B,
                      mats["paper_aged"] if rnd.random() > 0.28 else
                      mats["paper_red"], rotation=(0, 0, yaw), bevel=0.001)
        label["mounting_method"] = "paper_label_on_bottle"
    return body


def _accumulated_junk(mats, bx):
    """Objects retained for utility or sentiment, not placed as a matching set."""
    # Dust lips sit visibly behind bottle feet; the lowest run stops at the
    # register opening instead of passing through the machine.
    for shelf in range(C.DD_BAR_BOTTLE_SHELVES):
        # Rows 0 and 1 stop at the register opening; their shelves are split
        # around the machine, so a full-width dust lip would float in the bay.
        if shelf <= 1:
            gap = 0.82
            span = (C.BAR_LEN + 0.04 - gap) / 2.0
            for side in (-1, 1):
                sy = BAR_Y + side * (gap / 2.0 + span / 2.0)
                L.box("BAR_BackShelfDust_%d_%s" %
                      (shelf, "S" if side < 0 else "N"),
                      (0.22, span, 0.003),
                      (bx + 0.14, sy, 1.196 + shelf * 0.34), B,
                      mats["dust"])
        else:
            L.box("BAR_BackShelfDust_%d" % shelf,
                  (0.22, C.BAR_LEN + 0.04, 0.003),
                  (bx + 0.14, BAR_Y, 1.196 + shelf * 0.34), B, mats["dust"])

    # A deep, plainly constructed display ledge supports the accumulated junk.
    # These pieces previously occupied plausible-looking heights but had no
    # geometry beneath them. The ledge sits below the cornice and projects far
    # enough to carry every base without becoming a polished bottle display.
    display_top = 2.205
    display = L.box("BAR_UpperDisplayShelf", (0.38, C.BAR_LEN + 0.10, 0.050),
                    (bx + 0.165, BAR_Y, display_top - 0.025), B,
                    mats["bar_wood"], bevel=0.006)
    display["support_role"] = "upper_junk_display_ledge"

    # Old tabletop radio wedged above the back bar.
    radio = L.box("BAR_Junk_RadioBody", (0.22, 0.42, 0.22),
                  (bx + 0.20, BAR_Y + 1.55, display_top + 0.11), B,
                  mats["paint_door"], bevel=0.035, bevel_segments=3)
    radio["support_z"] = display_top
    L.box("BAR_Junk_RadioGrille", (0.018, 0.24, 0.13),
          (bx + 0.322, BAR_Y + 1.49, display_top + 0.11), B,
          mats["paper_aged"],
          bevel=0.012)
    for i in range(2):
        L.cylinder("BAR_Junk_RadioKnob_%d" % i, 0.024, 0.018,
                   (bx + 0.334, BAR_Y + 1.67,
                    display_top + 0.07 + i * 0.08), B,
                   mats["blacksteel"], segments=16,
                   rotation=(0, radians(90), 0))

    # Cheap league trophy, coffee tin, cloudy pickle jar and spare mugs.
    trophy = L.cylinder("BAR_Junk_TrophyBase", 0.060, 0.035,
                        (bx + 0.25, BAR_Y - 1.78,
                         display_top + 0.0175), B, mats["bar_wood"],
                        segments=24)
    trophy["support_z"] = display_top
    L.cylinder("BAR_Junk_TrophyStem", 0.018, 0.19,
               (bx + 0.25, BAR_Y - 1.78, display_top + 0.1275), B,
               mats["brass"],
               segments=16)
    L.ring("BAR_Junk_TrophyCup", 0.050, 0.060, 0.075,
           (bx + 0.25, BAR_Y - 1.78, display_top + 0.2325), B,
           mats["brass"], segments=28)
    coffee = L.cylinder("BAR_Junk_CoffeeTin", 0.070, 0.17,
                        (bx + 0.27, BAR_Y - 0.25,
                         display_top + 0.085), B, mats["paper_red"],
                        segments=24)
    coffee["support_z"] = display_top
    pickle = L.cylinder("BAR_Junk_PickleJar", 0.080, 0.22,
                        (bx + 0.26, BAR_Y + 0.55,
                         display_top + 0.11), B, mats["glass_clear"],
                        segments=28)
    pickle["support_z"] = display_top
    for i in range(7):
        angle = 2.0 * math.pi * i / 7.0
        L.uv_sphere("BAR_Junk_JarLime_%d" % i, 0.026,
                    (bx + 0.26, BAR_Y + 0.55 + math.sin(angle) * 0.040,
                     display_top + 0.039 + (i % 3) * 0.045), B,
                    mats["wall_panel"],
                    segments=16, rings=8)
    for i in range(5):
        L.cylinder("BAR_Junk_Mug_%d" % i, 0.042, 0.075,
                   (bx + 0.31, BAR_Y + 1.02 + i * 0.085, 1.235), B,
                   mats["enamel_white"] if i % 2 else mats["paper_aged"],
                   segments=20)


def _rubber_bar_mat(name, x, y, size_x, size_y, z, mats):
    """Old molded service mat with connected ribs and a wet-work purpose."""
    base = L.box(name + "_Base", (size_x, size_y, 0.007),
                 (x, y, z), B, mats["bar_rubber"], bevel=0.004)
    base["workflow_role"] = "wet_service_surface"
    for i in range(9):
        ry = y - size_y * 0.42 + i * size_y * 0.105
        L.box(name + "_RibY_%02d" % i, (size_x * 0.90, 0.008, 0.008),
              (x, ry, z + 0.007), B, mats["bar_rubber"], bevel=0.002)
    for i in range(4):
        rx = x - size_x * 0.36 + i * size_x * 0.24
        L.box(name + "_RibX_%02d" % i, (0.008, size_y * 0.90, 0.008),
              (rx, y, z + 0.007), B, mats["bar_rubber"], bevel=0.002)
    return base


def _underbar_workflow(mats):
    """Compact, visible bartender cockpit based on real underbar modules.

    The service side owns ice, open well bottles, a soda gun, garnish access,
    hand/utility washing, glass draining, wet mats, waste and refrigeration.
    It remains battered and modular rather than becoming a premium cocktail
    station, but every prop now has a recognizable operational reason.
    """
    ln = C.BAR_LEN
    service_x = SERVICE_X
    service_min = BAR_Y - (ln - 0.30) / 2.0
    service_max = BAR_Y + (ln - 0.30) / 2.0
    sink_x, sink_y = service_x, BAR_Y + 0.90
    ice_x, ice_y = service_x, BAR_Y - 0.60
    sink_half_y, ice_half_y = 0.34, 0.45

    # Counter pieces stop at the manufactured sink and ice openings. A single
    # solid slab under both would make those pieces decorative depressions.
    counter_spans = (
        (service_min, ice_y - ice_half_y - 0.035, "South"),
        (ice_y + ice_half_y + 0.035, sink_y - sink_half_y - 0.035, "Middle"),
        (sink_y + sink_half_y + 0.035, service_max, "North"),
    )
    for y0, y1, tag in counter_spans:
        L.box("BAR_ServiceCounter_" + tag, (0.36, y1 - y0, 0.04),
              (service_x, (y0 + y1) / 2.0, 0.90), B,
              mats["stainless"], bevel=0.004)

    # Open hand/utility sink: bottom, four walls, connected rim, drain and
    # faucet. Its under-shelf and four legs describe a buildable module.
    sink = L.box("BAR_Sink_BasinBottom", (0.30, 0.54, 0.025),
                 (sink_x, sink_y, 0.7275), B, mats["blacksteel"],
                 bevel=0.012)
    sink["workflow_role"] = "handwash_or_utility_sink"
    for tag, xoff in (("W", -0.145), ("E", 0.145)):
        L.box("BAR_Sink_BasinWall_" + tag, (0.025, 0.54, 0.16),
              (sink_x + xoff, sink_y, 0.815), B, mats["blacksteel"],
              bevel=0.010)
        L.box("BAR_Sink_Rim_" + tag, (0.055, 0.63, 0.025),
              (sink_x + (xoff / abs(xoff)) * 0.18, sink_y, 0.9075), B,
              mats["stainless"], bevel=0.006)
    for tag, yoff in (("S", -0.27), ("N", 0.27)):
        L.box("BAR_Sink_BasinWall_" + tag, (0.30, 0.025, 0.16),
              (sink_x, sink_y + yoff, 0.815), B, mats["blacksteel"],
              bevel=0.010)
        L.box("BAR_Sink_Rim_" + tag, (0.40, 0.055, 0.025),
              (sink_x, sink_y + (yoff / abs(yoff)) * 0.34, 0.9075), B,
              mats["stainless"], bevel=0.006)
    L.ring("BAR_Sink_Drain", 0.016, 0.036, 0.008,
           (sink_x, sink_y, 0.744), B, mats["stainless"], segments=24)
    for spoke in range(6):
        a = math.tau * spoke / 6.0
        L.box("BAR_Sink_DrainSpoke_%d" % spoke, (0.004, 0.045, 0.003),
              (sink_x + math.cos(a) * 0.006,
               sink_y + math.sin(a) * 0.006, 0.749), B,
              mats["stainless"], rotation=(0, 0, a), bevel=0.001)
    L.cylinder("BAR_Sink_FaucetBase", 0.030, 0.050,
               (sink_x - 0.13, sink_y + 0.27, 0.945), B,
               mats["stainless"], segments=18)
    L.cylinder_between("BAR_Sink_FaucetRiser", 0.012,
                       (sink_x - 0.13, sink_y + 0.27, 0.97),
                       (sink_x - 0.13, sink_y + 0.27, 1.16), B,
                       mats["stainless"], segments=14)
    L.cylinder_between("BAR_Sink_FaucetSpout", 0.012,
                       (sink_x - 0.13, sink_y + 0.27, 1.16),
                       (sink_x - 0.13, sink_y + 0.04, 1.12), B,
                       mats["stainless"], segments=14)
    L.box("BAR_UnderShelf_Sink", (0.36, 0.58, 0.028),
          (sink_x, sink_y, 0.44), B, mats["stainless"], bevel=0.004)
    for sx in (-0.14, 0.14):
        for sy in (-0.25, 0.25):
            L.cylinder("BAR_Sink_Leg_%s_%s" %
                       ("E" if sx > 0 else "W", "N" if sy > 0 else "S"),
                       0.013, 0.72, (sink_x + sx, sink_y + sy, 0.36), B,
                       mats["stainless"], segments=10)

    # A washed-grey towel is folded over the sink rim and hangs down the
    # bartender side; it is connected in two pieces instead of a floating flag.
    towel = L.box("BAR_Towel_Hanging", (0.022, 0.22, 0.27),
                  (sink_x + 0.205, sink_y + 0.13, 0.785), B,
                  mats["towel_dirty"], bevel=0.010)
    towel["workflow_role"] = "wipe_and_sanitation"
    L.box("BAR_Towel_OverRim", (0.10, 0.22, 0.016),
          (sink_x + 0.175, sink_y + 0.13, 0.925), B,
          mats["towel_dirty"], bevel=0.007)

    # Open insulated ice bin with visible ice, a partial sliding lid and a
    # scoop. The speed rail is fastened to its bartender-facing edge below.
    ice = L.box("BAR_IceBin_Bottom", (0.30, 0.82, 0.025),
                (ice_x, ice_y, 0.5925), B, mats["stainless"], bevel=0.008)
    ice["workflow_role"] = "ice_storage"
    for tag, xoff in (("W", -0.155), ("E", 0.155)):
        L.box("BAR_IceBin_Wall_" + tag, (0.030, 0.88, 0.30),
              (ice_x + xoff, ice_y, 0.75), B, mats["stainless"],
              bevel=0.008)
        L.box("BAR_IceBin_Rim_" + tag, (0.050, 0.92, 0.020),
              (ice_x + xoff, ice_y, 0.91), B, mats["stainless"],
              bevel=0.005)
    for tag, yoff in (("S", -0.425), ("N", 0.425)):
        L.box("BAR_IceBin_Wall_" + tag, (0.30, 0.030, 0.30),
              (ice_x, ice_y + yoff, 0.75), B, mats["stainless"],
              bevel=0.008)
        L.box("BAR_IceBin_Rim_" + tag, (0.36, 0.050, 0.020),
              (ice_x, ice_y + yoff, 0.91), B, mats["stainless"],
              bevel=0.005)
    L.box("BAR_IceBin_Interior", (0.275, 0.79, 0.018),
          (ice_x, ice_y, 0.615), B, mats["blacksteel"], bevel=0.008)
    ice_rnd = random.Random(203)
    for i in range(28):
        cube = ice_rnd.uniform(0.030, 0.046)
        L.box("BAR_IceCube_%02d" % i, (cube, cube * 0.92, cube * 0.88),
              (ice_x + ice_rnd.uniform(-0.105, 0.105),
               ice_y + ice_rnd.uniform(-0.315, 0.315),
               0.765 + ice_rnd.uniform(-0.035, 0.070)), B, mats["ice"],
              rotation=(radians(ice_rnd.uniform(-18, 18)),
                        radians(ice_rnd.uniform(-18, 18)),
                        radians(ice_rnd.uniform(0, 90))),
              bevel=0.005, bevel_segments=2)
    L.box("BAR_IceBin_SlidingCover", (0.34, 0.25, 0.018),
          (ice_x, ice_y - 0.305, 0.925), B, mats["stainless"],
          bevel=0.006)
    scoop = L.revolved_surface("BAR_IceScoop_Bowl",
                               ((0.030, 0.0), (0.050, 0.080)), B,
                               mats["stainless"], segments=24,
                               location=(ice_x + 0.025, ice_y + 0.05, 0.82))
    scoop.rotation_euler = (0, radians(68), radians(24))
    L.cylinder_between("BAR_IceScoop_Handle", 0.010,
                       (ice_x + 0.015, ice_y + 0.035, 0.84),
                       (ice_x + 0.10, ice_y + 0.27, 0.91), B,
                       mats["stainless"], segments=12)
    L.box("BAR_UnderShelf_IceBin", (0.36, 0.86, 0.028),
          (ice_x, ice_y, 0.44), B, mats["stainless"], bevel=0.004)
    for sx in (-0.14, 0.14):
        for sy in (-0.38, 0.38):
            L.cylinder("BAR_IceBin_Leg_%s_%s" %
                       ("E" if sx > 0 else "W", "N" if sy > 0 else "S"),
                       0.013, 0.59, (ice_x + sx, ice_y + sy, 0.295), B,
                       mats["stainless"], segments=10)

    # Four-bin garnish tray bridges the rear edge of the ice well. Its lid is
    # left partly open because this room is dressed mid-shift, not after close.
    garnish = L.box("BAR_GarnishStation_Base", (0.115, 0.58, 0.035),
                    (ice_x - 0.105, ice_y, 0.925), B, mats["stainless"],
                    bevel=0.005)
    garnish["workflow_role"] = "garnish_access"
    for i in range(5):
        gy = ice_y - 0.29 + i * 0.145
        L.box("BAR_GarnishStation_Divider_%d" % i, (0.12, 0.010, 0.065),
              (ice_x - 0.105, gy, 0.955), B, mats["stainless"],
              bevel=0.002)
    for i in range(8):
        compartment = i % 4
        gy = ice_y - 0.215 + compartment * 0.145 + (i // 4) * 0.025
        L.uv_sphere("BAR_Garnish_%02d" % i, 0.021,
                    (ice_x - 0.105 + (0.012 if i >= 4 else -0.012), gy,
                     0.970), B,
                    mats["garnish_lime"] if compartment < 2 else
                    mats["garnish_orange"], segments=14, rings=8)
    L.box("BAR_GarnishStation_Lid", (0.13, 0.27, 0.012),
          (ice_x - 0.105, ice_y - 0.15, 1.000), B, mats["stainless"],
          rotation=(radians(-8), 0, 0), bevel=0.004)

    # Mounted well trough: eight used bottles sit on its bottom and carry
    # actual speed pourers. It shares the ice-bin module's east/front wall.
    rail_x, rail_y, rail_z = ice_x + 0.235, ice_y, 0.72
    rail = L.box("BAR_SpeedRail_Bottom", (0.14, 0.96, 0.025),
                 (rail_x, rail_y, rail_z), B, mats["stainless"], bevel=0.004)
    rail["workflow_role"] = "well_bottle_access"
    for tag, xoff in (("Back", -0.058), ("Front", 0.058)):
        L.box("BAR_SpeedRail_" + tag, (0.025, 0.96, 0.13),
              (rail_x + xoff, rail_y, rail_z + 0.065), B,
              mats["stainless"], bevel=0.006)
    well_rnd = random.Random(31)
    well_families = ("round_whiskey", "longneck", "square_whiskey",
                     "squat_liqueur")
    for i in range(8):
        _stock_bottle("BAR_WellBottle_%02d" % i,
                      well_families[i % len(well_families)], rail_x,
                      rail_y - 0.37 + i * 0.106, rail_z + 0.014,
                      0.255 + 0.012 * (i % 3), 0.030 + 0.002 * (i % 2),
                      radians(-14 + i * 4), mats, well_rnd, stock=False)

    # Drop-in soda gun, perforated holster cup and a connected hose that falls
    # into the underbar chase. Its buttons sit on the handle, not in mid-air.
    gun_x, gun_y, gun_z, gun_yaw = ice_x + 0.10, ice_y + 0.50, 0.972, radians(-12)
    L.cylinder("BAR_SodaGun_DripCup", 0.052, 0.075,
               (gun_x, gun_y, 0.8725), B, mats["blacksteel"], segments=20)
    L.ring("BAR_SodaGun_HolsterRing", 0.045, 0.065, 0.012,
           (gun_x, gun_y, 0.916), B, mats["stainless"], segments=24)
    gun = L.box("BAR_SodaGun_Handle", (0.055, 0.18, 0.045),
                (gun_x, gun_y, gun_z), B, mats["bar_rubber"],
                rotation=(0, radians(-7), gun_yaw), bevel=0.018,
                bevel_segments=3)
    gun["workflow_role"] = "soda_dispense"
    for row in range(4):
        for col in range(2):
            bx, by = _local_xy(gun_x, gun_y, -0.014 + col * 0.028,
                               -0.050 + row * 0.034, gun_yaw)
            L.box("BAR_SodaGun_Button_%d_%d" % (row, col),
                  (0.013, 0.020, 0.006), (bx, by, gun_z + 0.025), B,
                  mats["paper_aged"] if (row + col) % 2 else mats["paper_red"],
                  rotation=(0, 0, gun_yaw), bevel=0.003)
    ns = _local_xy(gun_x, gun_y, 0.0, 0.085, gun_yaw)
    ne = _local_xy(gun_x, gun_y, 0.055, 0.155, gun_yaw)
    L.cylinder_between("BAR_SodaGun_Nozzle", 0.007,
                       (ns[0], ns[1], gun_z),
                       (ne[0], ne[1], gun_z - 0.020), B,
                       mats["stainless"], segments=10)
    hs = _local_xy(gun_x, gun_y, 0.0, -0.095, gun_yaw)
    L.curve_tube("BAR_SodaGun_Hose",
                 ((hs[0], hs[1], gun_z - 0.005),
                  (ice_x + 0.02, ice_y + 0.47, 0.82),
                  (ice_x - 0.13, ice_y + 0.37, 0.55),
                  (ice_x - 0.10, ice_y + 0.18, 0.34)),
                 0.009, B, mats["bar_rubber"], resolution=3)

    # Glass drainboard on the clear north counter. Five inverted bar glasses
    # have open rims down and bases up, the way clean glasses actually drain.
    drain_y = service_max - 0.22
    drain = L.box("BAR_Drainboard_Tray", (0.34, 0.40, 0.018),
                  (service_x, drain_y, 0.925), B, mats["stainless"],
                  bevel=0.006)
    drain["workflow_role"] = "glass_drain"
    for i in range(8):
        sy = drain_y - 0.17 + i * 0.049
        L.box("BAR_Drainboard_Slat_%02d" % i, (0.29, 0.012, 0.007),
              (service_x, sy, 0.938), B, mats["blacksteel"], bevel=0.002)
    for i in range(5):
        gx = service_x - 0.085 + (i % 3) * 0.085
        gy = drain_y - 0.085 + (i // 3) * 0.17
        L.revolved_surface("BAR_Drainboard_Glass_%d_Body" % i,
                           ((0.034, 0.0), (0.032, 0.060), (0.025, 0.110)),
                           B, mats["glass_clear"], segments=24,
                           location=(gx, gy, 0.945))
        L.cylinder("BAR_Drainboard_Glass_%d_Base" % i, 0.025, 0.006,
                   (gx, gy, 1.058), B, mats["glass_clear"], segments=22)

    # Dry waste bin between the ice and sink modules. Four walls and a liner
    # rim leave the top visibly open instead of treating waste as a solid box.
    trash_y = BAR_Y + 0.27
    trash = L.box("BAR_TrashStation_Bottom", (0.30, 0.38, 0.025),
                  (service_x, trash_y, 0.0125), B, mats["blacksteel"],
                  bevel=0.008)
    trash["workflow_role"] = "waste"
    for tag, xoff in (("W", -0.145), ("E", 0.145)):
        L.box("BAR_TrashStation_Wall_" + tag, (0.025, 0.38, 0.54),
              (service_x + xoff, trash_y, 0.27), B, mats["blacksteel"],
              bevel=0.010)
        L.box("BAR_TrashStation_Liner_" + tag, (0.018, 0.40, 0.035),
              (service_x + xoff, trash_y, 0.555), B, mats["bar_rubber"],
              bevel=0.006)
    for tag, yoff in (("S", -0.18), ("N", 0.18)):
        L.box("BAR_TrashStation_Wall_" + tag, (0.30, 0.025, 0.54),
              (service_x, trash_y + yoff, 0.27), B, mats["blacksteel"],
              bevel=0.010)
        L.box("BAR_TrashStation_Liner_" + tag, (0.32, 0.018, 0.035),
              (service_x, trash_y + yoff, 0.555), B, mats["bar_rubber"],
              bevel=0.006)

    _rubber_bar_mat("BAR_RubberMat_Service", service_x, trash_y,
                    0.34, 0.46, 0.925, mats)

    # The old two-door undercounter refrigerator fits the final south bay; its
    # body no longer intersects an imaginary continuous shelf.
    cooler_x, cooler_y = service_x - 0.03, BAR_Y - 1.47
    L.box("BAR_Cooler", (0.52, 0.78, 0.82), (cooler_x, cooler_y, 0.41), B,
          mats["stainless"])
    for side, yoff in (("S", -0.20), ("N", 0.20)):
        L.box("BAR_Cooler_Door_" + side, (0.018, 0.36, 0.68),
              (cooler_x + 0.270, cooler_y + yoff, 0.42), B,
              mats["stainless"], bevel=0.010)
        L.box("BAR_Cooler_Handle_" + side, (0.030, 0.16, 0.030),
              (cooler_x + 0.292, cooler_y + yoff, 0.63), B,
              mats["blacksteel"], bevel=0.006)
    for i in range(5):
        L.box("BAR_Cooler_Vent_%d" % i, (0.020, 0.050, 0.012),
              (cooler_x + 0.282, cooler_y - 0.10 + i * 0.05, 0.12), B,
              mats["blacksteel"])


def _round_wood_stool(i, sx, sy, yaw, mats, height):
    """Round oak stool with splayed legs, square stretchers and a paper shim."""
    r = C.DD_BAR_STOOL_SEAT_R
    seat = L.cylinder("BAR_Stool_Seat_%d" % i, r, 0.060,
                      (sx, sy, height), B, mats["bar_wood"], segments=32,
                      rotation=(0, 0, yaw))
    seat["furniture_variant"] = "round_oak"
    leg_r = r * 0.075
    inset = r * 0.56
    for lx in (-inset, inset):
        for ly in (-inset, inset):
            top = _local_xy(sx, sy, lx * 0.83, ly * 0.83, yaw)
            bottom = _local_xy(sx, sy, lx * 1.08, ly * 1.08, yaw)
            L.cylinder_between("BAR_Stool_Leg_%d_%s_%s" %
                               (i, "E" if lx > 0 else "W",
                                "N" if ly > 0 else "S"), leg_r,
                               (bottom[0], bottom[1], 0.0),
                               (top[0], top[1], height - 0.028), B,
                               mats["bar_wood"], segments=12)
    rail_z = C.DD_BAR_STOOL_FOOT_Z
    span = inset * 2.0
    for ly in (-inset, inset):
        a = _local_xy(sx, sy, -inset, ly, yaw)
        b = _local_xy(sx, sy, inset, ly, yaw)
        L.cylinder_between("BAR_Stool_StretcherX_%d_%s" %
                           (i, "N" if ly > 0 else "S"), leg_r * 0.72,
                           (a[0], a[1], rail_z), (b[0], b[1], rail_z), B,
                           mats["bar_wood"], segments=10)
    for lx in (-inset, inset):
        a = _local_xy(sx, sy, lx, -inset, yaw)
        b = _local_xy(sx, sy, lx, inset, yaw)
        L.cylinder_between("BAR_Stool_StretcherY_%d_%s" %
                           (i, "E" if lx > 0 else "W"), leg_r * 0.72,
                           (a[0], a[1], rail_z), (b[0], b[1], rail_z), B,
                           mats["bar_wood"], segments=10)
    shim = _local_xy(sx, sy, -inset * 1.08, -inset * 1.08, yaw)
    L.box("BAR_Stool_Shim_%d" % i, (0.055, 0.050, 0.006),
          (shim[0], shim[1], 0.003), B, mats["paper_aged"],
          rotation=(0, 0, yaw + radians(8)))


def _vinyl_tube_stool(i, sx, sy, yaw, mats, height):
    """1950s tube-frame vinyl stool, repaired and slightly skewed."""
    r = C.DD_BAR_STOOL_SEAT_R
    seat = L.cylinder("BAR_Stool_Seat_%d" % i, r, 0.070,
                      (sx, sy, height), B, mats["vinyl_red"], segments=32,
                      rotation=(0, 0, yaw))
    seat["furniture_variant"] = "vinyl_tube_back"
    inset = r * 0.56
    leg_r = r * 0.050
    for lx in (-inset, inset):
        for ly in (-inset, inset):
            top = _local_xy(sx, sy, lx * 0.86, ly * 0.86, yaw)
            bottom = _local_xy(sx, sy, lx * 1.04, ly * 1.04, yaw)
            L.cylinder_between("BAR_Stool_Leg_%d_%s_%s" %
                               (i, "E" if lx > 0 else "W",
                                "N" if ly > 0 else "S"), leg_r,
                               (bottom[0], bottom[1], 0.0),
                               (top[0], top[1], height - 0.030), B,
                               mats["blacksteel"], segments=10)
    L.ring("BAR_Stool_FootRing_%d" % i, r * 0.54, r * 0.59, 0.013,
           (sx, sy, C.DD_BAR_STOOL_FOOT_Z), B, mats["blacksteel"],
           segments=36, rotation=(0, 0, yaw))
    back_c = _local_xy(sx, sy, -r * 0.78, 0.0, yaw)
    for side in (-r * 0.70, r * 0.70):
        post = _local_xy(back_c[0], back_c[1], 0.0, side, yaw)
        L.cylinder("BAR_Stool_BackPost_%d_%s" %
                   (i, "N" if side > 0 else "S"), leg_r,
                   C.DD_BAR_STOOL_BACK_H,
                   (post[0], post[1],
                    height + C.DD_BAR_STOOL_BACK_H / 2.0),
                   B, mats["blacksteel"], segments=10)
    L.box("BAR_Stool_BackPad_%d" % i,
          (0.065, r * 1.55, C.DD_BAR_STOOL_BACK_H * 0.55),
          (back_c[0], back_c[1], height + C.DD_BAR_STOOL_BACK_H * 0.72), B,
          mats["vinyl_red"], rotation=(0, radians(-7), yaw), bevel=0.025,
          bevel_segments=3)
    # A small split exposes foam without turning the seat into theatrical ruin.
    tear = _local_xy(sx, sy, r * 0.15, -r * 0.30, yaw)
    L.box("BAR_Stool_Tear_%d" % i, (0.004, 0.085, 0.012),
          (tear[0], tear[1], height + 0.037), B, mats["foam_yellow"],
          rotation=(0, 0, yaw + radians(18)), bevel=0.002)


def _square_wood_stool(i, sx, sy, yaw, mats, height):
    """Square-seat replacement stool with square legs and one newer brace."""
    seat = L.box("BAR_Stool_Seat_%d" % i, (0.36, 0.34, 0.060),
                 (sx, sy, height), B, mats["bar_wood"],
                 rotation=(0, 0, yaw), bevel=0.016, bevel_segments=3)
    seat["furniture_variant"] = "square_wood"
    inset_x, inset_y = 0.13, 0.12
    for lx in (-inset_x, inset_x):
        for ly in (-inset_y, inset_y):
            p = _local_xy(sx, sy, lx, ly, yaw)
            L.box("BAR_Stool_Leg_%d_%s_%s" %
                  (i, "E" if lx > 0 else "W", "N" if ly > 0 else "S"),
                  (0.034, 0.034, height - 0.030),
                  (p[0], p[1], (height - 0.030) / 2.0), B,
                  mats["bar_wood"], rotation=(0, 0, yaw), bevel=0.004)
    for axis, fixed, tag in (("x", -inset_y, "S"), ("x", inset_y, "N"),
                             ("y", -inset_x, "W"), ("y", inset_x, "E")):
        if axis == "x":
            a = _local_xy(sx, sy, -inset_x, fixed, yaw)
            b = _local_xy(sx, sy, inset_x, fixed, yaw)
        else:
            a = _local_xy(sx, sy, fixed, -inset_y, yaw)
            b = _local_xy(sx, sy, fixed, inset_y, yaw)
        material = mats["paint_door"] if tag == "N" else mats["bar_wood"]
        L.cylinder_between("BAR_Stool_Stretcher%s_%d_%s" %
                           (axis.upper(), i, tag), 0.014,
                           (a[0], a[1], C.DD_BAR_STOOL_FOOT_Z),
                           (b[0], b[1], C.DD_BAR_STOOL_FOOT_Z), B,
                           material, segments=8, smooth=False)


def _pedestal_stool(i, sx, sy, yaw, mats, height):
    """Later swivel stool bolted to a circular pedestal base."""
    seat = L.cylinder("BAR_Stool_Seat_%d" % i, 0.19, 0.075,
                      (sx, sy, height), B, mats["vinyl_red"], segments=36,
                      rotation=(0, 0, yaw))
    seat["furniture_variant"] = "pedestal_swivel_back"
    L.cylinder("BAR_Stool_Base_%d" % i, 0.205, 0.025,
               (sx, sy, 0.0125), B, mats["blacksteel"], segments=40)
    L.cylinder("BAR_Stool_Pedestal_%d" % i, 0.035, height - 0.055,
               (sx, sy, (height - 0.055) / 2.0), B, mats["blacksteel"],
               segments=18)
    back = _local_xy(sx, sy, -0.16, 0.0, yaw)
    L.cylinder("BAR_Stool_BackPost_%d_W" % i, 0.018, 0.34,
               (back[0], back[1], height + 0.15), B, mats["blacksteel"],
               segments=12)
    L.box("BAR_Stool_BackPad_%d" % i, (0.075, 0.31, 0.17),
          (back[0], back[1], height + 0.29), B, mats["vinyl_red"],
          rotation=(0, radians(-6), yaw), bevel=0.030, bevel_segments=3)
    L.box("BAR_Stool_Patch_%d" % i, (0.008, 0.105, 0.055),
          (back[0] + 0.043, back[1], height + 0.29), B,
          mats["paint_door"], rotation=(0, radians(-6), yaw), bevel=0.004)


def build(mats):
    L.clear_collection(B)
    ln = C.BAR_LEN

    # ------------------------------------------------------- guest side ---
    L.box("BAR_Top", (0.62, ln, 0.045), (BAR_X, BAR_Y, BT - 0.022), B,
          mats["bartop"], bevel=0.006)
    L.box("BAR_Face", (0.055, ln, BT - 0.10), (BAR_X + 0.28, BAR_Y,
                                               (BT - 0.10) / 2), B,
          mats["bar_wood"], bevel=0.004)
    # The bartender-side bar die supports the other edge of the guest top and
    # gives the speed rail, opener and cap catcher a real mounting surface.
    L.box("BAR_InsideDie", (0.040, ln, BT - 0.10),
          (BAR_X - 0.29, BAR_Y, (BT - 0.10) / 2), B,
          mats["wall_panel"], bevel=0.004)
    L.box("BAR_Kick", (0.28, ln, 0.10), (BAR_X + 0.14, BAR_Y, 0.05), B,
          mats["paint_door"])

    # Recessed, unevenly worn front panels replace the monolithic premium
    # slab. The frame stays proud enough to catch warm grazing highlights.
    panel_h = BT * 0.60
    panel_z = 0.49
    panel_w = (ln - 0.22) / C.DD_BAR_FRONT_PANEL_COUNT
    face_x = BAR_X + 0.312
    for i in range(C.DD_BAR_FRONT_PANEL_COUNT):
        y = BAR_Y - ln / 2.0 + 0.11 + panel_w * (i + 0.5)
        L.box("BAR_FrontPanel_%02d" % i,
              (C.DD_BAR_PANEL_INSET_T, panel_w - 0.065, panel_h),
              (face_x, y, panel_z), B, mats["wall_panel"], bevel=0.006)
        for dz in (-panel_h / 2.0, panel_h / 2.0):
            L.box("BAR_FrontPanelRail_%02d_%s" %
                  (i, "B" if dz < 0 else "T"),
                  (C.DD_BAR_PANEL_INSET_T + 0.010, panel_w,
                   C.DD_BAR_PANEL_FRAME_W),
                  (face_x + 0.003, y, panel_z + dz), B,
                  mats["bar_wood"], bevel=0.003)
        for dy in (-panel_w / 2.0, panel_w / 2.0):
            L.box("BAR_FrontPanelStile_%02d_%s" %
                  (i, "S" if dy < 0 else "N"),
                  (C.DD_BAR_PANEL_INSET_T + 0.010, C.DD_BAR_PANEL_FRAME_W,
                   panel_h),
                  (face_x + 0.003, y + dy, panel_z), B,
                  mats["bar_wood"], bevel=0.003)
    # brass foot rail on stanchions
    L.cylinder("BAR_FootRail", 0.021, ln - 0.20,
               (BAR_X + 0.36, BAR_Y, 0.19), B, mats["brass"],
               rotation=(radians(90), 0, 0), segments=20)
    for i in range(4):
        y = BAR_Y - ln / 2 + 0.5 + i * (ln - 1.0) / 3.0
        L.cylinder("BAR_RailStanchion_%d" % i, 0.016, 0.19,
                   (BAR_X + 0.36, y, 0.095), B, mats["brass"], segments=14)

    # ---------------------------------------------------- bartender side ---
    _underbar_workflow(mats)

    # A cast opener and cap catcher are screwed to the inner bar die at hand
    # height. They are tools, not loose countertop decorations.
    opener_x, opener_y = BAR_X - 0.317, BAR_Y + 0.42
    opener = L.box("BAR_BottleOpener_Backplate", (0.012, 0.070, 0.120),
                   (opener_x, opener_y, 0.70), B, mats["cast_iron"],
                   bevel=0.008)
    opener["workflow_role"] = "bottle_opening"
    L.box("BAR_BottleOpener_Lip", (0.024, 0.040, 0.022),
          (opener_x - 0.014, opener_y, 0.715), B, mats["stainless"],
          bevel=0.004)
    catcher = L.box("BAR_CapCatcher_Box", (0.10, 0.18, 0.16),
                    (opener_x - 0.045, opener_y, 0.54), B,
                    mats["blacksteel"], bevel=0.012)
    catcher["workflow_role"] = "cap_waste"
    L.box("BAR_CapCatcher_OpenTop", (0.055, 0.14, 0.018),
          (opener_x - 0.096, opener_y, 0.605), B, mats["bar_rubber"],
          rotation=(0, radians(18), 0), bevel=0.005)

    # Four connected beer taps: column, manifold, spouts and hand pulls.
    tap_x, tap_y = BAR_X - 0.10, BAR_Y + 0.30
    L.cylinder("BAR_TapTower_Column", 0.055, 0.26,
               (tap_x, tap_y, BT + 0.13), B, mats["chrome"], segments=24)
    L.box("BAR_TapTower_Manifold", (0.085, 0.34, 0.075),
          (tap_x, tap_y, BT + 0.25), B, mats["chrome"], bevel=0.025,
          bevel_segments=3)
    # Spouts pour toward the bartender aisle, over the drip tray. The old
    # build aimed them across the guest rail, away from their own tray.
    for i in range(4):
        ty = tap_y - 0.12 + i * 0.08
        L.cylinder_between("BAR_TapSpout_%d" % i, 0.009,
                           (tap_x - 0.035, ty, BT + 0.24),
                           (tap_x - 0.10, ty, BT + 0.18), B,
                           mats["chrome"], segments=12)
        L.cylinder("BAR_TapHandle_%d" % i, 0.015, 0.12,
                   (tap_x + 0.015, ty, BT + 0.34), B,
                   mats["bar_wood"], segments=12)
    _rubber_bar_mat("BAR_RubberMat_Tap", BAR_X - 0.16, BAR_Y + 0.30,
                    0.20, 0.50, BT + 0.004, mats)
    drip = L.box("BAR_DripTray", (0.16, 0.34, 0.014),
                 (BAR_X - 0.16, BAR_Y + 0.30, BT + 0.012), B,
                 mats["stainless"], bevel=0.004)
    drip["workflow_role"] = "beer_service"

    # -------------------------------------------------------- back bar -----
    bx = BACK_X
    L.box("BAR_BackCabinet", (C.DD_BACKBAR_DEPTH, ln + 0.4, 0.92),
          (bx, BAR_Y, 0.46), B,
          mats["bar_wood"], bevel=0.004)

    # Three framed mirror bays with stained rails read as an old back bar,
    # not a single contemporary white feature wall.
    mirror_span = ln + 0.10
    bay_gap = 0.095
    bay_w = (mirror_span - bay_gap * 4.0) / 3.0
    for i in range(3):
        y = BAR_Y - mirror_span / 2.0 + bay_gap + bay_w / 2.0 + \
            i * (bay_w + bay_gap)
        L.box("BAR_BackMirror_%d" % i, (0.018, bay_w, 1.08),
              (bx + 0.111, y, 1.77), B, mats["mirror_aged"])
        for dz in (-0.56, 0.56):
            L.box("BAR_MirrorRail_%d_%s" % (i, "B" if dz < 0 else "T"),
                  (0.045, bay_w + bay_gap, 0.075),
                  (bx + 0.13, y, 1.77 + dz), B, mats["bar_wood"],
                  bevel=0.004)
        for dy in (-bay_w / 2.0 - bay_gap / 2.0,
                   bay_w / 2.0 + bay_gap / 2.0):
            L.box("BAR_MirrorStile_%d_%s" % (i, "S" if dy < 0 else "N"),
                  (0.045, 0.075, 1.20), (bx + 0.13, y + dy, 1.77), B,
                  mats["bar_wood"], bevel=0.004)
    register_gap = 0.82
    for i in range(3):
        shelf_z = 1.18 + i * 0.34
        # Rows 0 and 1 both split around the register: the machine's crown
        # ridge tops at 1.510 and row 1's lip spans 1.4725-1.5275, so an
        # unsplit row 1 runs straight through the indicator head. Row 2
        # (1.86) clears it and stays full width. The register never moves.
        if i <= 1:
            span = (ln + 0.1 - register_gap) / 2.0
            for side in (-1, 1):
                sy = BAR_Y + side * (register_gap / 2.0 + span / 2.0)
                tag = "S" if side < 0 else "N"
                L.box("BAR_BackShelf_%d_%s" % (i, tag),
                      (C.DD_BACKBAR_SHELF_DEPTH, span, 0.026),
                      (bx + 0.14, sy, shelf_z), B,
                      mats["bar_wood"])
                L.box("BAR_BackShelfLip_%d_%s" % (i, tag),
                      (0.055, span + 0.04, 0.055),
                      (bx + 0.26, sy, shelf_z - 0.02), B,
                      mats["bar_wood"], bevel=0.003)
        else:
            L.box("BAR_BackShelf_%d" % i,
                  (C.DD_BACKBAR_SHELF_DEPTH, ln + 0.1, 0.026),
                  (bx + 0.14, BAR_Y, shelf_z), B, mats["bar_wood"])
            L.box("BAR_BackShelfLip_%d" % i, (0.055, ln + 0.14, 0.055),
                  (bx + 0.26, BAR_Y, shelf_z - 0.02), B,
                  mats["bar_wood"], bevel=0.003)
    L.box("BAR_BackCornice", (0.30, ln + 0.48, 0.12),
          (bx + 0.04, BAR_Y, 2.40), B, mats["bar_wood"], bevel=0.012)

    # Two-deep stock made from seven bottle families. Each body meets its
    # shelf, labels face approximately into the room rather than forming bands,
    # and the register owns a real opening in the lowest shelf run.
    rnd = random.Random(7)
    families = ("round_whiskey", "longneck", "wine", "squat_liqueur",
                "bell_decanter", "square_whiskey", "flat_flask")
    for shelf in range(C.DD_BAR_BOTTLE_SHELVES):
        for depth in range(C.DD_BAR_BOTTLE_ROWS):
            z = 1.18 + shelf * 0.34 + 0.013
            row_x = bx + 0.10 + depth * 0.095
            # Runs reach the real shelf ends. The register bay costs rows 0
            # and 1 a 0.82 m stretch each, and a bartender restocks that
            # liquor onto the shelf that is left rather than losing it, so
            # the stock crowds out to the shelf edge instead of stopping
            # 0.17 m short. Widest bottle radius is 0.039 and the shelf half
            # width is 1.95, so a centre at 1.89 still sits 0.021 m inboard.
            y = BAR_Y - ln / 2 + 0.01 + rnd.uniform(0.0, 0.05)
            index = 0
            while y < BAR_Y + ln / 2 - 0.01:
                if shelf <= 1 and abs(y - BAR_Y) < register_gap * 0.52:
                    y = BAR_Y + register_gap * 0.52
                    continue
                family = families[rnd.randrange(len(families))]
                h = rnd.uniform(0.205, 0.305)
                if family in ("squat_liqueur", "bell_decanter"):
                    h *= 0.83
                r = rnd.uniform(0.026, 0.039)
                if shelf <= 1:
                    south_end = BAR_Y - register_gap / 2.0
                    north_start = BAR_Y + register_gap / 2.0
                    # Reserve the complete bottle base, not merely its centre,
                    # at the cash-register opening between the split shelves.
                    if y + r > south_end and y - r < north_start:
                        y = north_start + r + 0.006
                token = "%d_%d_%03d" % (shelf, depth, index)
                yaw = radians(rnd.uniform(-24.0, 24.0))
                _stock_bottle("BAR_Bottle_" + token, family, row_x, y, z,
                              h, r, yaw, mats, rnd)
                # Occasional deliberate gap where a regular's bottle lived.
                y += r * 2.0 + rnd.uniform(0.014, 0.038)
                if rnd.random() < 0.030:
                    y += rnd.uniform(0.05, 0.11)
                index += 1

    _accumulated_junk(mats, bx)
    _cash_register(mats)

    # ---------------------------------------------------------- stools -----
    # Four separate acquisitions, each left where a patron plausibly moved it.
    for i, (oy, pull, yaw_deg, variant) in enumerate(C.DD_BAR_STOOL_LAYOUT):
        h = C.DD_BAR_STOOL_SEAT_H + (0.012 if i == 2 else 0.0)
        sx, sy, yaw = BAR_X + 0.72 + pull, BAR_Y + oy, radians(yaw_deg)
        if variant == "round_oak":
            _round_wood_stool(i, sx, sy, yaw, mats, h)
        elif variant == "vinyl_tube_back":
            _vinyl_tube_stool(i, sx, sy, yaw, mats, h)
        elif variant == "square_wood":
            _square_wood_stool(i, sx, sy, yaw, mats, h)
        else:
            _pedestal_stool(i, sx, sy, yaw, mats, h)

    n = len(L.get_collection(B).objects)
    print("  [bar] %d objects (guest side, service side, back bar, stools)" % n)
    return True


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
