"""
10_build_architecture.py — the prewar tenement ground floor shell.

Real wall thickness, real reveals, real floor-to-wall contact. Nothing here is
an infinitely thin plane. The room is long and narrow: bar at the street end,
pool room at the rear, which is the actual footprint of a NYC storefront bar.

Owns: 01_ARCHITECTURE.
"""
import bpy
import math
import os
import sys
from math import radians

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

A = "01_ARCHITECTURE"
HW, HL = C.ROOM_W / 2.0, C.ROOM_L / 2.0
T = C.WALL_T


def _irregular_patch(name, centre, radii, material, z=0.0012):
    """Low-profile authored floor patch; uneven outline avoids decal circles."""
    verts = [(0.0, 0.0, 0.0)]
    count = len(radii)
    for i, radius in enumerate(radii):
        angle = 2.0 * math.pi * i / count
        verts.append((math.cos(angle) * radius,
                      math.sin(angle) * radius * 0.72, 0.0))
    faces = []
    for i in range(count):
        faces.append((0, 1 + i, 1 + ((i + 1) % count)))
    ob = L.mesh_object(name, verts, faces, A, material)
    ob.location = (centre[0], centre[1], z)
    return ob


def _crack_segment(name, start, end, material, width=0.009):
    """A nearly flush dark seam following an authored crack path."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    angle = math.atan2(dy, dx) - math.pi / 2.0
    return L.box(name, (width, length, 0.0015),
                 ((start[0] + end[0]) / 2.0,
                  (start[1] + end[1]) / 2.0, 0.0007), A, material,
                 rotation=(0, 0, angle), bevel=width * 0.35)


def _rear_door(name, x, width, height, mats, bathroom=False):
    """Closed rear door in a true wall opening, with casing and hardware."""
    y = HL - 0.018
    fw, fd = C.DD_DOOR_FRAME_W, C.DD_DOOR_FRAME_D
    bottom_gap = 0.008 if bathroom else 0.014
    leaf_h = height - fw * 0.65 - bottom_gap
    L.box(name, (width - fw * 1.15, 0.045, leaf_h),
          (x, y, bottom_gap + leaf_h / 2.0), A, mats["paint_door"],
          bevel=0.006)
    for sx in (-1, 1):
        L.box(name + "_Jamb_%s" % ("W" if sx < 0 else "E"),
              (fw, fd, height + fw),
              (x + sx * (width / 2.0 + fw / 2.0), y - 0.018,
               (height + fw) / 2.0), A, mats["paint_trim"], bevel=0.004)
    L.box(name + "_Head", (width + fw * 2.0, fd, fw),
          (x, y - 0.018, height + fw / 2.0), A, mats["paint_trim"],
          bevel=0.004)
    # Scuffed kick plate, three butt hinges with real knuckles, and hardware
    # appropriate to each use. The service lever and bathroom knob are not a
    # repeated kit.
    L.box(name + "_KickPlate", (width * 0.68, 0.012, 0.235),
          (x, y - 0.030, 0.16), A, mats["brass"], bevel=0.003)
    knob_x = x - width * 0.34
    L.box(name + "_LockEscutcheon", (0.060, 0.012, 0.180),
          (knob_x, y - 0.052, 1.02), A, mats["blacksteel"], bevel=0.014)
    if bathroom:
        L.uv_sphere(name + "_Knob", 0.035,
                    (knob_x, y - 0.070, 1.02), A, mats["brass"],
                    segments=24, rings=12)
    else:
        L.cylinder(name + "_Lever", 0.014, 0.115,
                   (knob_x - 0.042, y - 0.071, 1.02), A, mats["brass"],
                   segments=16, rotation=(0, radians(90), 0))
    for i, z in enumerate((0.34, 1.02, 1.70)):
        L.box(name + "_Hinge_%d" % i, (0.045, 0.018, 0.095),
              (x + width * 0.43, y - 0.045, z), A, mats["blacksteel"],
              bevel=0.003)
        L.cylinder(name + "_HingeBarrel_%d" % i, 0.010, 0.115,
                   (x + width * 0.455, y - 0.056, z), A,
                   mats["blacksteel"], segments=12)
    if not bathroom:
        # A narrow, visibly motivated light leak from unmodelled back-of-house;
        # unlike the old broad area light, it cannot shine through a solid leaf.
        L.box(name + "_UnderDoorGlow", (width * 0.76, 0.010, 0.009),
              (x, y - 0.030, 0.006), A, mats["service_glow"])
    if bathroom:
        # A small battered universal restroom plaque. The former oversized
        # heads-and-blocks read like electrical toggles in the close camera;
        # articulated arms and legs make these unmistakable person pictograms.
        plaque_y = y - 0.051
        icon_y = y - 0.066
        L.box(name + "_RestroomPlaque", (0.24, 0.014, 0.15),
              (x, plaque_y, 1.57), A, mats["blacksteel"], bevel=0.014)
        for sx in (-0.052, 0.052):
            tag = "L" if sx < 0 else "R"
            px = x + sx
            L.uv_sphere(name + "_SignHead_" + tag, 0.013,
                        (px, icon_y, 1.610), A, mats["paper_aged"],
                        segments=18, rings=10)
            L.box(name + "_SignBody_" + tag, (0.025, 0.008, 0.045),
                  (px, icon_y, 1.565), A, mats["paper_aged"], bevel=0.006)
            for limb, a, b in (
                    ("ArmOut", (px, icon_y, 1.578),
                     (px + (-0.025 if sx < 0 else 0.025), icon_y, 1.552)),
                    ("ArmIn", (px, icon_y, 1.578),
                     (px + (0.025 if sx < 0 else -0.025), icon_y, 1.552)),
                    ("LegOut", (px - 0.006, icon_y, 1.544),
                     (px + (-0.018 if sx < 0 else 0.018), icon_y, 1.515)),
                    ("LegIn", (px + 0.006, icon_y, 1.544),
                     (px + (0.018 if sx < 0 else -0.018), icon_y, 1.515))):
                L.cylinder_between(name + "_Sign%s_%s" % (limb, tag),
                                   0.0035, a, b, A, mats["paper_aged"],
                                   segments=8)
        # Individual placeholder rectangles were replaced by one dense,
        # project-original sticker scan in ``55_age_and_story``. Keeping both
        # would put blank cards over the readable accumulated door history.


def _build_front_door(mats):
    """Framed glazed storefront door assembled inside its masonry opening."""
    x, width, height = C.DD_FRONT_DOOR_X, C.DD_FRONT_DOOR_W, C.DD_FRONT_DOOR_H
    y = -HL + 0.020
    stile = 0.095
    for sx in (-1, 1):
        L.box("ENV_FrontDoor_Stile_%s" % ("W" if sx < 0 else "E"),
              (stile, 0.050, height),
              (x + sx * (width - stile) / 2.0, y, height / 2.0), A,
              mats["paint_door"], bevel=0.004)
    for tag, z, rail_h in (("Bottom", 0.10, 0.20), ("Lock", 0.82, 0.12),
                           ("Top", height - 0.08, 0.16)):
        L.box("ENV_FrontDoor_Rail_" + tag, (width, 0.050, rail_h),
              (x, y, z), A, mats["paint_door"], bevel=0.004)
    L.box("ENV_FrontDoor_LowerPanel", (width - 2 * stile, 0.038, 0.58),
          (x, y + 0.002, 0.44), A, mats["wall_panel"], bevel=0.008)
    L.box("ENV_FrontDoor_Glass", (width - 2 * stile, 0.012, 1.05),
          (x, y - 0.004, 1.42), A, mats["glass_door"])
    L.box("ENV_FrontDoor_TransomGlass", (width - 0.08, 0.012, 0.22),
          (x, y - 0.004, 2.30), A, mats["glass_door"])
    L.box("ENV_FrontDoor_TransomRail", (width, 0.050, 0.075),
          (x, y, 2.185), A, mats["paint_door"], bevel=0.004)
    # Interior egress hardware for a 36-inch commercial entrance: a horizontal
    # exit bar carried by two returns into a latch case. The earlier vertical
    # cylinder had no returns or latch relationship and therefore read as a
    # floating line rather than a usable pull.
    bar_z = C.DD_FRONT_EXIT_BAR_Z
    exit_bar = L.box("ENV_FrontDoor_ExitBar",
                     (C.DD_FRONT_EXIT_BAR_W, 0.050, 0.060),
                     (x - 0.025, y + 0.066, bar_z), A, mats["blacksteel"],
                     bevel=0.012, bevel_segments=3)
    exit_bar["hardware_type"] = "interior_narrow_stile_exit_bar"
    for sx in (-1, 1):
        L.box("ENV_FrontDoor_ExitBarReturn_%s" %
              ("W" if sx < 0 else "E"), (0.050, 0.075, 0.105),
              (x - 0.025 + sx * C.DD_FRONT_EXIT_BAR_W * 0.44,
               y + 0.048, bar_z), A, mats["blacksteel"], bevel=0.012)
    L.box("ENV_FrontDoor_ExitLatchCase", (0.105, 0.070, 0.185),
          (x - width * 0.38, y + 0.050, bar_z), A, mats["blacksteel"],
          bevel=0.016, bevel_segments=3)
    # The former interior key cylinder sat above the latch case at the glass
    # edge and therefore had no mechanism behind it. Interior operation is the
    # push rail; the mortise latch now terminates at a fixed jamb strike.
    L.box("ENV_FrontDoor_StrikePlate", (0.018, 0.060, 0.165),
          (x - width / 2.0 - 0.010, y + 0.042, bar_z), A,
          mats["stainless"], bevel=0.003)

    # Three hinge barrels define the actual swing axis at the east stile.
    hinge_x = x + width * 0.485
    for i, z in enumerate((0.34, 1.02, 1.72)):
        L.cylinder("ENV_FrontDoor_HingeBarrel_%d" % i, 0.012, 0.125,
                   (hinge_x, y + 0.040, z), A, mats["blacksteel"],
                   segments=14)
        L.box("ENV_FrontDoor_HingeLeaf_%d" % i, (0.072, 0.010, 0.100),
              (hinge_x - 0.030, y + 0.038, z), A, mats["blacksteel"],
              bevel=0.003)

    # Surface closer body and articulated two-piece arm. Every visible line
    # terminates in either the door or frame, exactly as real closer hardware.
    L.box("ENV_FrontDoor_CloserBody", (0.285, 0.065, 0.075),
          (x + 0.16, y + 0.055, 1.965), A, mats["blacksteel"],
          bevel=0.018, bevel_segments=3)
    L.cylinder_between("ENV_FrontDoor_CloserArmA", 0.010,
                       (x + 0.11, y + 0.091, 1.985),
                       (x - 0.015, y + 0.145, 2.085), A,
                       mats["blacksteel"], segments=12)
    L.cylinder_between("ENV_FrontDoor_CloserArmB", 0.010,
                       (x - 0.015, y + 0.145, 2.085),
                       (x - 0.245, y + 0.068, 2.145), A,
                       mats["blacksteel"], segments=12)
    L.box("ENV_FrontDoor_CloserShoe", (0.090, 0.030, 0.045),
          (x - 0.245, y + 0.050, 2.145), A, mats["blacksteel"],
          bevel=0.006)
    L.box("ENV_FrontDoor_Threshold", (width, 0.20, 0.025),
          (x, -HL + 0.01, 0.0125), A, mats["stainless"], bevel=0.003)


def build(mats):
    L.clear_collection(A)

    # ------------------------------------------------------------- floor ---
    L.box("ENV_Floor", (C.ROOM_W, C.ROOM_L, 0.10), (0, 0, -0.05), A,
          mats["floor"])

    # Permanent damage belongs to the slab, not to a generic grunge layer.
    # Long authored fractures cross traffic lanes; patched aggregate and
    # overlapping drink/oil blooms record different decades of neglect.
    crack_paths = (
        ((-2.62, -4.65), (-1.72, -3.82), (-1.18, -2.68), (-0.52, -1.96)),
        ((2.86, -1.62), (2.18, -0.72), (2.02, 0.32), (1.42, 1.24)),
        ((-0.98, 4.96), (-0.42, 4.23), (0.12, 3.82), (0.64, 3.08)),
        ((-1.72, 1.18), (-1.30, 1.64), (-1.10, 2.22)),
    )
    for pidx, points in enumerate(crack_paths):
        for sidx, (start, end) in enumerate(zip(points, points[1:])):
            _crack_segment("ENV_FloorCrack_%02d_%02d" % (pidx, sidx),
                           start, end, mats["floor_crack"],
                           width=0.007 + 0.002 * ((pidx + sidx) % 3))

    patches = (
        ("PatchEntry", (1.72, -4.82), (0.34, 0.27, 0.38, 0.24, 0.31, 0.22),
         "concrete_patch"),
        ("PatchBar", (-1.72, -2.70), (0.29, 0.38, 0.25, 0.34, 0.21, 0.32),
         "concrete_patch"),
        ("OilBar", (-1.42, -1.30), (0.24, 0.38, 0.31, 0.44, 0.28, 0.33, 0.25),
         "stain_dark"),
        ("BeerA", (1.52, 0.74), (0.18, 0.27, 0.22, 0.31, 0.21, 0.25),
         "stain_beer"),
        ("BeerB", (-0.68, 3.46), (0.19, 0.14, 0.23, 0.17, 0.26, 0.15),
         "stain_beer"),
        ("RustRadiator", (-2.84, -1.88), (0.22, 0.34, 0.25, 0.31, 0.20, 0.28),
         "stain_rust"),
    )
    for name, centre, radii, material in patches:
        _irregular_patch("ENV_Floor" + name, centre, radii, mats[material])

    # Small old resin/plug repairs close former fixture holes. These are part
    # of the floor's maintenance history, not litter sitting on its surface.
    resin_repairs = ((2.42, -4.30), (2.66, -3.76), (1.94, -2.82),
                     (-1.44, -3.58), (-1.20, -2.12), (2.72, -1.34),
                     (-2.72, 3.16), (1.76, 4.54))
    for i, (x, y) in enumerate(resin_repairs):
        L.cylinder("ENV_FloorResinPlug_%02d" % i,
                   0.018 + 0.003 * (i % 3), 0.002,
                   (x, y, 0.001), A, mats["floor_resin"], segments=12)

    # --------------------------------------------------------- walls -------
    # Solid slabs with thickness, not planes. The street wall is punched for
    # the storefront glazing; the rear wall carries the service door.
    L.box("ENV_Wall_West", (T, C.ROOM_L + 2 * T, C.ROOM_H),
          (-HW - T / 2, 0, C.ROOM_H / 2), A, mats["plaster"])
    L.box("ENV_Wall_East", (T, C.ROOM_L + 2 * T, C.ROOM_H),
          (HW + T / 2, 0, C.ROOM_H / 2), A, mats["brick"])
    # Rear masonry is segmented around two real openings: service/back-of-
    # house to the west and the restroom to the east. Both lead into the
    # unmodelled service depth of the tenement lot.
    rear_openings = (
        (C.DD_SERVICE_DOOR_X, C.DD_REAR_DOOR_W),
        (C.DD_BATHROOM_DOOR_X, C.DD_REAR_DOOR_W),
    )
    rear_edges = [(-HW, rear_openings[0][0] - rear_openings[0][1] / 2.0),
                  (rear_openings[0][0] + rear_openings[0][1] / 2.0,
                   rear_openings[1][0] - rear_openings[1][1] / 2.0),
                  (rear_openings[1][0] + rear_openings[1][1] / 2.0, HW)]
    for i, (x0, x1) in enumerate(rear_edges):
        L.box("ENV_Wall_RearPier_%d" % i,
              (x1 - x0, T, C.ROOM_H),
              ((x0 + x1) / 2.0, HL + T / 2.0, C.ROOM_H / 2.0), A,
              mats["plaster"])
    L.box("ENV_Wall_RearHeader", (C.ROOM_W + 2 * T, T,
                                   C.ROOM_H - C.DD_REAR_DOOR_H),
          (0, HL + T / 2.0,
           C.DD_REAR_DOOR_H + (C.ROOM_H - C.DD_REAR_DOOR_H) / 2.0), A,
          mats["plaster"])

    # Street wall built as masonry piers, a window bay, and a separate framed
    # entrance. The former build put a fake door in front of uninterrupted
    # glazing; this version has an actual floor-to-header door opening.
    sill, head = 0.62, 2.42
    west_pier_w = 0.55
    door_l = C.DD_FRONT_DOOR_X - C.DD_FRONT_DOOR_W / 2.0
    divider_w = 0.12
    window_l = -HW + west_pier_w
    window_r = door_l - divider_w
    east_pier_l = C.DD_FRONT_DOOR_X + C.DD_FRONT_DOOR_W / 2.0
    for name, x0, x1 in (("West", -HW, window_l),
                         ("Divider", window_r, door_l),
                         ("East", east_pier_l, HW)):
        L.box("ENV_StreetPier_" + name, (x1 - x0, T, C.ROOM_H),
              ((x0 + x1) / 2.0, -HL - T / 2.0, C.ROOM_H / 2.0), A,
              mats["plaster"])
    L.box("ENV_Header_Street", (east_pier_l - window_l,
                                 T, C.ROOM_H - head),
          ((window_l + east_pier_l) / 2.0, -HL - T / 2.0,
           head + (C.ROOM_H - head) / 2.0), A, mats["plaster"])
    window_w = window_r - window_l
    window_x = (window_l + window_r) / 2.0
    L.box("ENV_Sill_Street", (window_w, T, sill),
          (window_x, -HL - T / 2.0, sill / 2.0), A, mats["plaster"])
    L.box("ENV_Glazing_Street", (window_w - 0.06, 0.012, head - sill),
          (window_x, -HL - T / 2.0, sill + (head - sill) / 2.0), A,
          mats["glass_dirty"])

    # Interior diamond lattice: the strongest recognizable old-neighborhood-
    # tavern cue, built as real mullions rather than painted into the glass.
    lattice_y = -HL + C.DD_WINDOW_MULLION_D / 2.0
    for i, x in enumerate(C.DD_WINDOW_DIAMOND_X):
        for row, lattice_z in enumerate(C.DD_WINDOW_DIAMOND_Z):
            for sign in (-1, 1):
                L.box("ENV_WindowDiamond_%02d_%d_%s" %
                      (i, row, "A" if sign < 0 else "B"),
                      (C.DD_WINDOW_MULLION_W, C.DD_WINDOW_MULLION_D,
                       C.DD_WINDOW_DIAMOND_BAR_L),
                      (x, lattice_y, lattice_z), A, mats["paint_trim"],
                      rotation=(0, radians(sign * 45.0), 0), bevel=0.002)
    for x in (window_l + 0.025, window_r - 0.025):
        L.box("ENV_WindowJamb_%d" % int(x * 10),
              (C.DD_WINDOW_MULLION_W * 1.6, C.DD_WINDOW_MULLION_D,
               head - sill),
              (x, lattice_y, sill + (head - sill) / 2.0), A,
              mats["paint_trim"], bevel=0.002)

    # ----------------------------------------------------------- ceiling ---
    # pressed tin: repeated panels with edge trim, on a real slab
    L.box("ENV_Ceiling_Slab", (C.ROOM_W + 2 * T, C.ROOM_L + 2 * T, 0.08),
          (0, 0, C.ROOM_H + 0.04), A, mats["plaster"])
    panel = 0.61                                  # 2 ft pressed-tin panels
    nx = int(C.ROOM_W / panel)
    ny = int(C.ROOM_L / panel)
    x0 = -(nx - 1) * panel / 2.0
    y0 = -(ny - 1) * panel / 2.0
    for i in range(nx):
        for j in range(ny):
            L.box("ENV_TinCeiling_Panel_%02d_%02d" % (i, j),
                  (panel - 0.006, panel - 0.006, 0.014),
                  (x0 + i * panel, y0 + j * panel, C.ROOM_H - 0.007), A,
                  mats["tin"], bevel=0.002)

    # ------------------------------------------------- trim and services ---
    for sx in (-1, 1):
        L.box("ENV_Baseboard_%s" % ("W" if sx < 0 else "E"),
              (0.028, C.ROOM_L, 0.165), (sx * (HW - 0.014), 0, 0.0825), A,
              mats["paint_trim"])
    for i, (x0, x1) in enumerate(rear_edges):
        L.box("ENV_Baseboard_Rear_%d" % i, (x1 - x0, 0.028, 0.165),
              ((x0 + x1) / 2.0, HL - 0.014, 0.0825), A,
              mats["paint_trim"])

    # Deep green painted wainscot and scarred wood chair rail. The upper walls
    # retain tobacco plaster/brick, while the lower metre carries decades of
    # chairs, shoes, mop water, and patched paint.
    panel_z = C.DD_WAINSCOT_H / 2.0
    for sx, tag in ((-1, "West"), (1, "East")):
        x = sx * (HW - C.DD_WAINSCOT_T / 2.0)
        L.box("ENV_Wainscot_" + tag,
              (C.DD_WAINSCOT_T, C.ROOM_L, C.DD_WAINSCOT_H),
              (x, 0, panel_z), A, mats["wall_panel"])
        count = int(C.ROOM_L / C.DD_WAINSCOT_PANEL_PITCH)
        for i in range(count + 1):
            y = -HL + i * C.ROOM_L / count
            L.box("ENV_WainscotBatten_%s_%02d" % (tag, i),
                  (C.DD_WAINSCOT_T + 0.010, C.DD_BAR_PANEL_FRAME_W,
                   C.DD_WAINSCOT_H), (x - sx * 0.004, y, panel_z), A,
                  mats["bar_wood"], bevel=0.002)
        L.box("ENV_ChairRail_" + tag,
              (C.DD_CHAIR_RAIL_D, C.ROOM_L, C.DD_CHAIR_RAIL_H),
              (sx * (HW - C.DD_CHAIR_RAIL_D / 2.0), 0,
               C.DD_WAINSCOT_H + C.DD_CHAIR_RAIL_H / 2.0),
              A, mats["bar_wood"], bevel=0.004)

    for seg, (x0, x1) in enumerate(rear_edges):
        span = x1 - x0
        mid = (x0 + x1) / 2.0
        L.box("ENV_Wainscot_Rear_%d" % seg,
              (span, C.DD_WAINSCOT_T, C.DD_WAINSCOT_H),
              (mid, HL - C.DD_WAINSCOT_T / 2.0, panel_z), A,
              mats["wall_panel"])
        count = max(1, int(span / C.DD_WAINSCOT_PANEL_PITCH))
        for i in range(count + 1):
            x = x0 + i * span / count
            L.box("ENV_WainscotBatten_Rear_%d_%02d" % (seg, i),
                  (C.DD_BAR_PANEL_FRAME_W, C.DD_WAINSCOT_T + 0.010,
                   C.DD_WAINSCOT_H),
                  (x, HL - C.DD_WAINSCOT_T / 2.0, panel_z), A,
                  mats["bar_wood"], bevel=0.002)
        L.box("ENV_ChairRail_Rear_%d" % seg,
              (span, C.DD_CHAIR_RAIL_D, C.DD_CHAIR_RAIL_H),
              (mid, HL - C.DD_CHAIR_RAIL_D / 2.0,
               C.DD_WAINSCOT_H + C.DD_CHAIR_RAIL_H / 2.0), A,
              mats["bar_wood"], bevel=0.004)

    # exposed conduit running the east wall, with junction boxes
    L.cylinder("ENV_Conduit_Main", 0.019, C.ROOM_L - 0.4,
               (HW - 0.06, 0, C.ROOM_H - 0.22), A, mats["conduit"],
               rotation=(radians(90), 0, 0), segments=16)
    for y in (-3.2, 0.4, 3.6):
        L.box("ENV_JunctionBox_%d" % int(y * 10), (0.09, 0.09, 0.045),
              (HW - 0.06, y, C.ROOM_H - 0.22), A, mats["conduit"])

    # steam radiator + riser on the west wall
    rad_y = -2.2
    for i in range(11):
        L.cylinder("ENV_RadiatorFin_%02d" % i, 0.032, 0.62,
                   (-HW + 0.10, rad_y - 0.22 + i * 0.044, 0.34), A,
                   mats["paint_rad"], rotation=(0, 0, 0), segments=12)
    L.box("ENV_RadiatorFoot", (0.16, 0.52, 0.05),
          (-HW + 0.10, rad_y, 0.03), A, mats["paint_rad"])
    L.cylinder("ENV_SteamRiser", 0.021, C.ROOM_H,
               (-HW + 0.09, rad_y + 0.42, C.ROOM_H / 2), A, mats["paint_rad"],
               segments=16)

    # sprinkler line down the centre
    L.cylinder("ENV_SprinklerLine", 0.026, C.ROOM_L - 0.6,
               (0.9, 0, C.ROOM_H - 0.14), A, mats["conduit"],
               rotation=(radians(90), 0, 0), segments=16)

    # Doors are built inside the openings above; neither is pasted onto an
    # uninterrupted wall. The restroom is public, while the western opening
    # continues to storage/service depth beyond the rendered room.
    _rear_door("ENV_ServiceDoor", C.DD_SERVICE_DOOR_X,
               C.DD_REAR_DOOR_W, C.DD_REAR_DOOR_H, mats)
    _rear_door("ENV_BathroomDoor", C.DD_BATHROOM_DOOR_X,
               C.DD_REAR_DOOR_W, C.DD_REAR_DOOR_H, mats, bathroom=True)
    _build_front_door(mats)

    n = len(L.get_collection(A).objects)
    print("  [architecture] %d objects (shell, tin ceiling, services)" % n)
    return True


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
