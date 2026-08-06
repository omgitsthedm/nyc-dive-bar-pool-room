"""
60_build_lighting.py — the three-shade billiard fixture and motivated practicals.

The table is the best-lit surface in the room, but the room stays a dark
after-hours bar. Every light in here is attached to a fixture or an opening;
there are no invisible cinematic rim lights.

WPA distinguishes movable and non-movable fixtures: a referee-movable light
may sit at 40 in above the bed, while a fixed rig must stay at 65 in. This
venue uses the lower chain-hung condition requested by art direction. The bed
and rails should still read evenly; Blender watts are not lux, so energy is
tuned visually and the placement is recorded explicitly.

Owns: 07_LIGHTS, 09_ATMOSPHERE.
"""
import bpy
import math
import os
import random
import sys
from math import radians

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

LG = "07_LIGHTS"
AT = "09_ATMOSPHERE"
CX, CY = C.TABLE_CENTRE[0], C.TABLE_CENTRE[1]

# Lowest part of a chain-hung, laterally movable venue fixture: 40 in above
# the bed, which lands around 1.78 m / 5 ft 10 in above this room's floor.
SHADE_BOTTOM_Z = C.BED_Z + C.FIXTURE_MIN_ABOVE_BED
SHADE_H = C.DD_POOL_SHADE_H


def area(name, energy, size, loc, rot=(0, 0, 0), colour=(1, 1, 1),
         shape="RECTANGLE", size_y=None, spread=None, motivation=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.shape = shape
    d.size = size
    if size_y is not None:
        d.size_y = size_y
    d.color = colour
    if spread is not None:
        try:
            d.spread = radians(spread)
        except Exception:
            pass
    o = bpy.data.objects.new(name, d)
    L.link(o, LG)
    o.location = loc
    o.rotation_euler = rot
    if motivation:
        o["motivation"] = motivation
    elif name.startswith("LGT_Pool_"):
        o["motivation"] = "visible_three_shade_billiard_fixture"
    elif name.startswith("LGT_BarPendant_"):
        o["motivation"] = "visible_bar_pendant"
    elif name.startswith("LGT_BackBar_"):
        o["motivation"] = "visible_old_shelf_fluorescent"
    elif name.startswith("LGT_Neon"):
        o["motivation"] = "visible_fictional_neon_tube"
    elif "Sconce" in name:
        o["motivation"] = "visible_wall_sconce_globe"
    elif name == "LGT_StreetSpill":
        o["motivation"] = "offscreen_street_through_storefront"
    elif name == "LGT_ServiceDoor_Spill":
        o["motivation"] = "back_of_house_light_through_14mm_door_gap"
    else:
        o["motivation"] = "documented_visible_fixture"
    return o


def point(name, energy, radius, loc, colour, motivation):
    """Omnidirectional source owned by a visible practical fixture."""
    d = bpy.data.lights.new(name, "POINT")
    d.energy = energy
    d.shadow_soft_size = radius
    d.color = colour
    o = bpy.data.objects.new(name, d)
    L.link(o, LG)
    o.location = loc
    o["motivation"] = motivation
    return o


def _neon_tube_variance():
    """A6 - give each neon tube its own emission level.

    Every POOL tube and every EXIT letter shares one material, so all of them
    burn at exactly the same brightness. Real tubes do not: gas pressure,
    transformer age and hours run all differ, and a matched sign is one of the
    tells that a room was generated rather than lit. Each tube gets a private
    copy of its material scaled +/-10-15%, and one POOL tube runs at 70% -
    tired, not dead, the one the owner keeps meaning to replace.

    Seeded so the same tube is tired in every rebuild. The film phase adds a
    flicker F-curve to that tube only; stills keep the static variance.
    """
    rnd = random.Random(6041)
    groups = {
        "POOL": [o for o in bpy.data.objects
                 if o.name.startswith("LGT_NeonTube_")],
        "EXIT": [],
    }
    # EXIT letters are multi-part; vary per LETTER so a letter stays internally
    # consistent and the sign still reads as four strokes, not eleven.
    letters = {}
    for o in bpy.data.objects:
        if not o.name.startswith("LGT_ExitSign_"):
            continue
        rest = o.name[len("LGT_ExitSign_"):]
        key = rest.split("_")[0]
        if key in ("E", "X", "I", "T"):
            letters.setdefault(key, []).append(o)
    tired = None
    if groups["POOL"]:
        groups["POOL"].sort(key=lambda o: o.name)
        tired = rnd.choice(groups["POOL"])
    varied = 0
    for ob in sorted(groups["POOL"], key=lambda o: o.name):
        factor = 0.70 if ob is tired else 1.0 + rnd.uniform(-0.15, 0.10)
        varied += _scale_emission(ob, factor, "pool_%s" % ob.name[-1])
    for key in sorted(letters):
        factor = 1.0 + rnd.uniform(-0.15, 0.10)
        for ob in sorted(letters[key], key=lambda o: o.name):
            varied += _scale_emission(ob, factor, "exit_%s" % key)
    if tired is not None:
        tired["neon_condition"] = "tired_tube_70_percent"
    print("  [lighting] A6 neon variance on %d tubes; tired tube = %s"
          % (varied, tired.name if tired else "none"))
    return varied


def _scale_emission(ob, factor, tag):
    """Private material copy for one tube, emission scaled by `factor`."""
    if not ob.data.materials:
        return 0
    src = ob.data.materials[0]
    name = "%s_%s" % (src.name, tag)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = src.copy()
        mat.name = name
        for node in mat.node_tree.nodes:
            if "Emission Strength" in getattr(node, "inputs", {}):
                node.inputs["Emission Strength"].default_value *= factor
    ob.data.materials[0] = mat
    ob["neon_emission_factor"] = round(factor, 4)
    return 1


def _neon_stroke(name, a, b, mat, radius=0.010):
    """One connected glass tube stroke with a dark mounting clip at each end."""
    tube = L.curve_tube(name, (a, b), radius, LG, mat, resolution=2)
    tube["fixture_type"] = "bent_glass_neon_tube"
    return tube


def _storefront_open_neon(mats):
    """A slightly irregular generic OPEN sign inside the storefront glass."""
    y = -C.ROOM_L / 2.0 + 0.055
    z0, h, w, gap = 1.64, 0.42, 0.23, 0.075
    total = 4 * w + 3 * gap
    start_x = -1.28 - total / 2.0
    letters = "OPEN"
    mat_by_letter = (mats["neon_blue"], mats["neon_green"],
                     mats["neon_blue"], mats["neon_green"])
    # Thin old frame and four real wall/window clips make the sign an object,
    # not unexplained emission floating in front of the glass.
    frame_x = start_x + total / 2.0
    for tag, x, z, sx, sz in (
            ("Top", frame_x, z0 + h + 0.075, total + 0.20, 0.024),
            ("Bottom", frame_x, z0 - 0.075, total + 0.20, 0.024),
            ("Left", start_x - 0.088, z0 + h / 2.0, 0.024, h + 0.17),
            ("Right", start_x + total + 0.088, z0 + h / 2.0,
             0.024, h + 0.17)):
        frame = L.box("LGT_NeonWindowOpen_Frame" + tag,
                      (sx, 0.028, sz), (x, y - 0.018, z), LG,
                      mats["blacksteel"], bevel=0.006)
        frame["fixture_type"] = "salvaged_window_neon_frame"

    for index, letter in enumerate(letters):
        x = start_x + index * (w + gap)
        yj = y + 0.002 * ((index % 2) * 2 - 1)
        mat = mat_by_letter[index]
        strokes = []
        if letter == "O":
            pts = ((x + 0.04, yj, z0), (x + w - 0.04, yj, z0),
                   (x + w, yj, z0 + 0.06), (x + w, yj, z0 + h - 0.06),
                   (x + w - 0.04, yj, z0 + h),
                   (x + 0.04, yj, z0 + h), (x, yj, z0 + h - 0.06),
                   (x, yj, z0 + 0.06), (x + 0.04, yj, z0))
            ob = L.curve_tube("LGT_NeonWindowOpen_O", pts, 0.010, LG, mat,
                              resolution=2)
            ob["fixture_type"] = "bent_glass_neon_tube"
            continue
        if letter == "P":
            strokes = (((x, yj, z0), (x, yj, z0 + h)),
                       ((x, yj, z0 + h), (x + w - 0.04, yj, z0 + h)),
                       ((x + w - 0.04, yj, z0 + h),
                        (x + w, yj, z0 + h - 0.07)),
                       ((x + w, yj, z0 + h - 0.07),
                        (x + w, yj, z0 + h * 0.58)),
                       ((x + w, yj, z0 + h * 0.58),
                        (x, yj, z0 + h * 0.58)))
        elif letter == "E":
            strokes = (((x, yj, z0), (x, yj, z0 + h)),
                       ((x, yj, z0 + h), (x + w, yj, z0 + h)),
                       ((x, yj, z0 + h * 0.52),
                        (x + w * 0.78, yj, z0 + h * 0.52)),
                       ((x, yj, z0), (x + w, yj, z0)))
        elif letter == "N":
            strokes = (((x, yj, z0), (x, yj, z0 + h)),
                       ((x, yj, z0 + h), (x + w, yj, z0)),
                       ((x + w, yj, z0), (x + w, yj, z0 + h)))
        for stroke, (a, b) in enumerate(strokes):
            _neon_stroke("LGT_NeonWindowOpen_%s_%d" % (letter, stroke),
                         a, b, mat)

    area("LGT_Neon_WindowOpen", 15.0, total + 0.12,
         (start_x + total / 2.0, y + 0.035, z0 + h / 2.0),
         rot=(radians(90), 0, 0), colour=(0.12, 0.62, 1.0),
         shape="RECTANGLE", size_y=h + 0.10, spread=130.0,
         motivation="visible_storefront_open_neon")


def _east_wall_eight_ball_neon(mats):
    """A repaired generic 8-ball neon; no beverage brand or cocktail cue."""
    x, y, z = C.ROOM_W / 2.0 - 0.075, -4.10, 2.18
    rot = (0, radians(90), 0)
    L.ring("LGT_Neon8Ball_BackRing", 0.225, 0.255, 0.028,
           (x, y, z), LG, mats["blacksteel"], segments=64, rotation=rot)
    outer = L.ring("LGT_Neon8Ball_OuterTube", 0.188, 0.202, 0.014,
                   (x - 0.018, y, z), LG, mats["neon_green"],
                   segments=64, rotation=rot)
    outer["fixture_type"] = "bent_glass_neon_tube"
    for i, dz in enumerate((-0.064, 0.064)):
        inner = L.ring("LGT_Neon8Ball_EightLoop_%d" % i,
                       0.047, 0.058, 0.012,
                       (x - 0.022, y, z + dz), LG, mats["neon_amber"],
                       segments=40, rotation=rot)
        inner["fixture_type"] = "bent_glass_neon_tube"
    for i, dy in enumerate((-0.18, 0.18)):
        L.cylinder_between("LGT_Neon8Ball_WallClip_%d" % i, 0.006,
                           (x, y + dy, z), (x - 0.085, y + dy, z), LG,
                           mats["blacksteel"], segments=8)
    area("LGT_Neon_8Ball", 8.0, 0.48,
         (x - 0.12, y, z), rot=(0, radians(-90), 0),
         colour=(0.12, 0.86, 0.34), shape="DISK", spread=130.0,
         motivation="visible_generic_eight_ball_neon")


def build(mats):
    L.clear_collection(LG)
    L.clear_collection(AT)

    # ------------------------------------------- three-shade fixture -------
    # centred over the playfield, parallel to the long axis
    span = C.FIXTURE_LEN
    canopy_z = C.ROOM_H - 0.02
    L.box("LGT_Pool_Canopy", (0.18, 0.46, 0.040),
          (CX, CY, canopy_z - 0.020), LG, mats["brass"], bevel=0.012)
    spine_z = SHADE_BOTTOM_Z + SHADE_H + 0.050
    spine = L.box("LGT_Pool_Spine", (C.DD_POOL_FIXTURE_BAR_W, span, 0.060),
                  (CX, CY, spine_z), LG, mats["brass"], bevel=0.012,
                  bevel_segments=3)
    spine["fixture_configuration"] = C.FIXTURE_CONFIGURATION

    shade_r = C.DD_POOL_SHADE_R
    shell_t = C.DD_POOL_SHADE_SHELL_T
    shade_profile = [
        (shade_r, 0.000),
        (shade_r * 0.985, 0.022),
        (shade_r * 0.53, SHADE_H * 0.82),
        (shade_r * 0.45, SHADE_H),
        (shade_r * 0.45 - shell_t, SHADE_H),
        (shade_r * 0.53 - shell_t, SHADE_H * 0.80),
        (shade_r - shell_t, 0.019),
        (shade_r - shell_t, 0.002),
    ]
    inner_profile = [
        (shade_r - shell_t * 1.25, 0.005),
        (shade_r * 0.53 - shell_t * 1.15, SHADE_H * 0.80),
    ]
    for k, off in enumerate((-C.DD_POOL_SHADE_SPACING, 0.0,
                              C.DD_POOL_SHADE_SPACING)):
        # Classic flared green-enamel billiard shade with a cream reflector.
        L.revolved_surface("LGT_Pool_Shade_%d" % k, shade_profile, LG,
                           mats["enamel_green"], segments=64,
                           location=(CX, CY + off, SHADE_BOTTOM_Z),
                           close_profile=True)
        L.revolved_surface("LGT_Pool_ShadeInner_%d" % k, inner_profile, LG,
                           mats["enamel_white"], segments=64,
                           location=(CX, CY + off, SHADE_BOTTOM_Z))
        L.cylinder("LGT_Pool_Socket_%d" % k, 0.022, 0.06,
                   (CX, CY + off, SHADE_BOTTOM_Z + SHADE_H - 0.01), LG,
                   mats["blacksteel"], segments=16)
        L.uv_sphere("LGT_Pool_Bulb_%d" % k, 0.030,
                    (CX, CY + off, SHADE_BOTTOM_Z + 0.060), LG,
                    mats["enamel_white"], segments=24, rings=14)
        # the emitter: a downward disc inside each shade
        area("LGT_Pool_Key_%d" % k, 16.0, shade_r * 1.52,
             (CX, CY + off, SHADE_BOTTOM_Z + 0.034),
             rot=(0, 0, 0), colour=(1.0, 0.906, 0.79), shape="DISK",
             spread=125.0)

    # Paired dark chains at the bar ends, instead of modern solid rods from
    # each shade. At this distance narrow faceted links read as old chain.
    chain_h = canopy_z - spine_z
    for i, off in enumerate((-C.DD_POOL_SHADE_SPACING,
                              C.DD_POOL_SHADE_SPACING)):
        for sx in (-1, 1):
            L.ring("LGT_Pool_CeilingHook_%d_%s" %
                   (i, "W" if sx < 0 else "E"), 0.018, 0.026, 0.010,
                   (CX + sx * 0.055, CY + off, canopy_z - 0.055), LG,
                   mats["blacksteel"], segments=20)
            L.cylinder("LGT_Pool_Chain_%d_%s" %
                       (i, "W" if sx < 0 else "E"),
                       C.DD_POOL_FIXTURE_CHAIN_R, chain_h,
                       (CX + sx * 0.055, CY + off,
                        spine_z + chain_h / 2.0), LG, mats["blacksteel"],
                       segments=8)

    # a soft wide fill so the rails and corners do not fall off
    pool_fill = area("LGT_Pool_Fill", 8.0, C.PLAY_W * 0.92,
                     (CX, CY, SHADE_BOTTOM_Z + 0.34),
                     colour=(1.0, 0.92, 0.82), shape="RECTANGLE",
                     size_y=C.PLAY_L * 0.86, spread=150.0)
    pool_fill["table_fill_revision"] = "continuous_rail_v2"

    # ------------------------------------------------ bar practicals -------
    pendant_x = C.DD_BAR_TOP_X - 0.05
    pendant_profile = [(0.115, 0.0), (0.105, 0.025), (0.052, 0.10),
                       (0.044, 0.10), (0.096, 0.020)]
    pendant_z = (1.855, 1.885, 1.870)
    pendant_tilt = (-1.2, 0.6, -0.4)
    for i, y in enumerate((C.DD_BAR_CENTRE_Y - 0.95,
                           C.DD_BAR_CENTRE_Y,
                           C.DD_BAR_CENTRE_Y + 0.95)):
        shade = L.revolved_surface("LGT_BarPendant_Shade_%d" % i,
                                   pendant_profile, LG, mats["brass"],
                                   segments=40,
                                   location=(pendant_x, y, pendant_z[i]),
                                   close_profile=True)
        shade.rotation_euler = (radians(pendant_tilt[i]), 0, 0)
        L.cylinder("LGT_BarPendant_Cord_%d" % i, 0.004,
                   C.ROOM_H - pendant_z[i] - 0.10,
                   (pendant_x, y,
                    (C.ROOM_H + pendant_z[i] + 0.10) / 2.0), LG,
                   mats["blacksteel"], segments=8)
        area("LGT_BarPendant_%d" % i, 28.0, 0.10,
             (pendant_x, y, pendant_z[i] - 0.02),
             colour=(1.0, 0.72 + i * 0.015, 0.44), shape="DISK",
             spread=140.0)
    # back-bar shelf glow, hidden behind the bottle line
    bx = C.DD_BACKBAR_X
    # The strip runs at z 1.090-1.105, inside the register drum's 1.05-1.34
    # band and on its centre line, so an unbroken run passed through the
    # machine and put a glow behind the drum. Both the tube and its steel
    # housing are split into flanking segments around the same 0.82 register
    # opening the back shelves use. Nothing lit sits behind the register.
    register_gap = 0.82
    for side in (-1, 1):
        tag = "S" if side < 0 else "N"
        house_span = (C.BAR_LEN - 0.08 - register_gap) / 2.0
        tube_span = (C.BAR_LEN - 0.22 - register_gap) / 2.0
        L.box("LGT_BackBar_FluorescentHousing_%s" % tag,
              (0.055, house_span, 0.065),
              (bx + 0.24,
               C.DD_BAR_CENTRE_Y + side * (register_gap / 2.0 + house_span / 2.0),
               1.105), LG,
              mats["blacksteel"], bevel=0.012)
        L.box("LGT_BackBar_FluorescentTube_%s" % tag,
              (0.035, tube_span, 0.024),
              (bx + 0.293,
               C.DD_BAR_CENTRE_Y + side * (register_gap / 2.0 + tube_span / 2.0),
               1.090), LG, mats["backbar_tube"],
              bevel=0.010, bevel_segments=3)
    area("LGT_BackBar_Glow", 18.0, 0.06,
         (bx + 0.30, C.DD_BAR_CENTRE_Y, 1.44),
         rot=(0, radians(-70), 0), colour=(1.0, 0.66, 0.38),
         shape="RECTANGLE", size_y=C.BAR_LEN - 0.20)

    # small fictional neon over the back bar: saturated, not clipping
    neon_y = C.DD_BAR_CENTRE_Y + 1.40
    L.box("LGT_NeonSign_Body", (0.03, 0.62, 0.20),
          (bx + 0.16, neon_y, 2.16),
          LG, mats["frame_dark"], bevel=0.012)
    for j, zoff in enumerate((-0.052, 0.0, 0.052)):
        L.box("LGT_NeonTube_%d" % j, (0.018, 0.50 - j * 0.07, 0.012),
              (bx + 0.182, neon_y + (0.025 if j == 1 else 0.0),
               2.16 + zoff), LG, mats["neon_red"],
              rotation=(radians(j * 8.0), 0, 0), bevel=0.005,
              bevel_segments=3)
    area("LGT_Neon", 7.5, 0.10, (bx + 0.22, neon_y, 2.16),
         rot=(0, radians(-90), 0), colour=(1.0, 0.16, 0.22),
         shape="RECTANGLE", size_y=0.60)

    _storefront_open_neon(mats)
    _east_wall_eight_ball_neon(mats)

    # ------------------------------------------ front-room practicals ----
    # The front door is part of the occupied egress path, so it cannot vanish
    # into cinematic black. A tired schoolhouse globe and a later caged-bulb
    # replacement make two localized pools without turning the room into a
    # uniformly lit restaurant.
    ex, ey = 1.92, -4.72
    L.cylinder("LGT_Entry_Canopy", 0.110, 0.035,
               (ex, ey, C.ROOM_H - 0.030), LG, mats["blacksteel"],
               segments=28)
    L.cylinder("LGT_Entry_Stem", 0.014, 0.115,
               (ex, ey, C.ROOM_H - 0.105), LG, mats["brass"], segments=12)
    L.cylinder("LGT_Entry_GlobeCap", 0.055, 0.050,
               (ex, ey, 2.985), LG, mats["brass"], segments=24)
    schoolhouse_profile = [
        (0.045, 0.000), (0.092, -0.035), (0.140, -0.110),
        (0.148, -0.170), (0.118, -0.235), (0.064, -0.285),
        (0.030, -0.305),
    ]
    globe = L.revolved_surface("LGT_Entry_SchoolhouseGlobe",
                               schoolhouse_profile, LG,
                               mats["enamel_white"], segments=48,
                               location=(ex, ey, 2.970))
    globe["fixture_type"] = "old_schoolhouse_egress_globe"
    L.uv_sphere("LGT_Entry_Bulb", 0.034, (ex, ey, 2.785), LG,
                mats["bulb_warm"], segments=24, rings=14)
    point("LGT_Entry_Practical", 92.0, 0.095, (ex, ey, 2.690),
          (1.0, 0.68, 0.38), "visible_schoolhouse_egress_globe")

    cx, cy = 2.44, -2.62
    L.cylinder("LGT_Cafe_Canopy", 0.090, 0.030,
               (cx, cy, C.ROOM_H - 0.025), LG, mats["blacksteel"],
               segments=24)
    L.cylinder("LGT_Cafe_Cord", 0.0045, 0.515,
               (cx, cy, C.ROOM_H - 0.290), LG, mats["blacksteel"],
               segments=8)
    L.cylinder("LGT_Cafe_PorcelainSocket", 0.044, 0.090,
               (cx, cy, 2.585), LG, mats["enamel_white"], segments=24)
    L.uv_sphere("LGT_Cafe_Bulb", 0.047, (cx, cy, 2.505), LG,
                mats["bulb_warm"], segments=24, rings=14)
    # Salvaged wire guard: rings and vertical ribs meet one another, unlike a
    # decorative floating cage.
    for ring_i, (radius, z) in enumerate(((0.072, 2.575), (0.125, 2.455),
                                          (0.105, 2.345))):
        L.ring("LGT_Cafe_CageRing_%d" % ring_i, radius - 0.005,
               radius + 0.005, 0.009, (cx, cy, z), LG,
               mats["blacksteel"], segments=32)
    for rib in range(6):
        angle = math.tau * rib / 6.0
        L.cylinder_between("LGT_Cafe_CageRib_%d" % rib, 0.0045,
                           (cx + math.cos(angle) * 0.068,
                            cy + math.sin(angle) * 0.068, 2.575),
                           (cx + math.cos(angle) * 0.101,
                            cy + math.sin(angle) * 0.101, 2.345), LG,
                           mats["blacksteel"], segments=8)
    point("LGT_Cafe_Practical", 72.0, 0.070, (cx, cy, 2.405),
          (1.0, 0.62, 0.32), "visible_caged_cafe_bulb")

    # The two booths were installed in different eras, but both have a real
    # downlight over their table instead of invisible fill. Heights and shade
    # finishes differ slightly to preserve that acquisition history.
    for i, ((y, _run_x, _bay_w), shade_z, mat_name, energy) in enumerate(zip(
            C.DD_BOOTH_LAYOUT,
            (2.080, 2.035),
            ("blacksteel", "enamel_green"),
            (58.0, 54.0))):
        x = C.DD_BOOTH_TABLE_X
        L.cylinder("LGT_BoothPendant_Canopy_%d" % i, 0.080, 0.028,
                   (x, y, C.ROOM_H - 0.024), LG, mats["blacksteel"],
                   segments=24)
        L.cylinder("LGT_BoothPendant_Cord_%d" % i, 0.004,
                   C.ROOM_H - shade_z - 0.13,
                   (x, y, (C.ROOM_H + shade_z + 0.13) / 2.0), LG,
                   mats["blacksteel"], segments=8)
        booth_profile = [(0.165, 0.000), (0.158, 0.018),
                         (0.080, 0.115), (0.050, 0.130),
                         (0.055, 0.130), (0.086, 0.105)]
        shade = L.revolved_surface("LGT_BoothPendant_Shade_%d" % i,
                                   booth_profile, LG, mats[mat_name],
                                   segments=40, location=(x, y, shade_z),
                                   close_profile=True)
        shade["fixture_type"] = "salvaged_booth_pendant_%d" % i
        L.uv_sphere("LGT_BoothPendant_Bulb_%d" % i, 0.027,
                    (x, y, shade_z + 0.034), LG, mats["bulb_warm"],
                    segments=20, rings=12)
        area("LGT_BoothPendant_Practical_%d" % i, energy, 0.245,
             (x, y, shade_z + 0.010), colour=(1.0, 0.64, 0.34),
             shape="DISK", spread=145.0,
             motivation="visible_salvaged_booth_pendant")

    # A small, battered illuminated sign is permanently fixed over the only
    # front exit. The letter strokes are geometry, not an unexplained red
    # rectangle, and the tiny area source is owned by the visible sign.
    sx, sy, sz = C.DD_FRONT_DOOR_X, -C.ROOM_L / 2.0 + 0.105, 2.305
    L.box("LGT_ExitSign_Housing", (0.500, 0.075, 0.190),
          (sx, sy, sz), LG, mats["blacksteel"], bevel=0.018,
          bevel_segments=3)
    L.box("LGT_ExitSign_Face", (0.430, 0.012, 0.125),
          (sx, sy + 0.044, sz), LG, mats["enamel_white"], bevel=0.008)
    letter_y, h, w = sy + 0.053, 0.078, 0.014
    # Looking toward the front wall from inside, screen-left is increasing
    # world X; assign E-X-I-T in that order so the legend reads correctly.
    centres = (sx + 0.150, sx + 0.050, sx - 0.050, sx - 0.150)
    # E
    L.box("LGT_ExitSign_E_V", (w, 0.009, h),
          (centres[0] + 0.025, letter_y, sz), LG, mats["exit_red"])
    for j, dz in enumerate((-h / 2.0, 0.0, h / 2.0)):
        L.box("LGT_ExitSign_E_H%d" % j,
              (0.058 if j != 1 else 0.050, 0.009, w),
              (centres[0], letter_y, sz + dz), LG, mats["exit_red"])
    # X
    for j, flip in enumerate((-1, 1)):
        L.cylinder_between("LGT_ExitSign_X_%d" % j, w / 2.0,
                           (centres[1] - 0.030, letter_y, sz - flip * h / 2.0),
                           (centres[1] + 0.030, letter_y, sz + flip * h / 2.0),
                           LG, mats["exit_red"], segments=8)
    # I and T
    L.box("LGT_ExitSign_I", (w, 0.009, h),
          (centres[2], letter_y, sz), LG, mats["exit_red"])
    L.box("LGT_ExitSign_T_Top", (0.066, 0.009, w),
          (centres[3], letter_y, sz + h / 2.0), LG, mats["exit_red"])
    L.box("LGT_ExitSign_T_Stem", (w, 0.009, h),
          (centres[3], letter_y, sz), LG, mats["exit_red"])
    area("LGT_ExitSign_Glow", 2.5, 0.35,
         (sx, sy + 0.063, sz), rot=(radians(90), 0, 0),
         colour=(1.0, 0.06, 0.025), shape="RECTANGLE", size_y=0.10,
         spread=130.0, motivation="visible_illuminated_exit_sign")

    # Old wall sconces lift the art in localized warm pools. Backplate, arm,
    # socket and opal globe form one connected assembly around each source.
    for i, x in enumerate((-2.35, 2.25)):
        y, z = C.ROOM_L / 2.0 - 0.08, 2.23
        L.cylinder("LGT_RearSconce_Backplate_%d" % i, 0.095, 0.030,
                   (x, y, z), LG, mats["brass"], segments=28,
                   rotation=(radians(90), 0, 0))
        L.cylinder_between("LGT_RearSconce_Arm_%d" % i, 0.014,
                           (x, y - 0.015, z), (x, y - 0.135, z - 0.045), LG,
                           mats["brass"], segments=12)
        L.cylinder("LGT_RearSconce_Socket_%d" % i, 0.030, 0.070,
                   (x, y - 0.155, z - 0.055), LG, mats["brass"], segments=18,
                   rotation=(radians(90), 0, 0))
        L.uv_sphere("LGT_RearSconce_Globe_%d" % i, 0.085,
                    (x, y - 0.205, z - 0.075), LG, mats["enamel_white"],
                    segments=28, rings=16)
        area("LGT_RearSconce_%d" % i, 29.0 + i * 2.0, 0.15,
             (x, y - 0.215, z - 0.075), rot=(radians(-90), 0, 0),
             colour=(1.0, 0.64 + i * 0.02, 0.36), shape="DISK",
             spread=115.0)

    for i, y in enumerate((0.45, 3.42)):
        x, z = C.ROOM_W / 2.0 - 0.08, 2.24
        L.cylinder("LGT_EastSconce_Backplate_%d" % i, 0.090, 0.030,
                   (x, y, z), LG, mats["brass"], segments=28,
                   rotation=(0, radians(90), 0))
        L.cylinder_between("LGT_EastSconce_Arm_%d" % i, 0.014,
                           (x - 0.015, y, z), (x - 0.135, y, z - 0.045), LG,
                           mats["brass"], segments=12)
        L.cylinder("LGT_EastSconce_Socket_%d" % i, 0.030, 0.070,
                   (x - 0.155, y, z - 0.055), LG, mats["brass"], segments=18,
                   rotation=(0, radians(90), 0))
        L.uv_sphere("LGT_EastSconce_Globe_%d" % i, 0.085,
                    (x - 0.205, y, z - 0.075), LG, mats["enamel_white"],
                    segments=28, rings=16)
        area("LGT_EastSconce_%d" % i, 24.0 + i * 2.0, 0.15,
             (x - 0.215, y, z - 0.075), rot=(0, radians(90), 0),
             colour=(1.0, 0.60 + i * 0.02, 0.32), shape="DISK",
             spread=115.0)

    # A real caged back-hall practical makes the stickered restroom door
    # legible without an invisible fill. Its old porcelain socket and bent
    # guard are mounted to the rear header, where a small bar would actually
    # need circulation light after closing time.
    bx, by, bz = C.DD_BATHROOM_DOOR_X, C.ROOM_L / 2.0 - 0.075, 2.34
    L.cylinder("LGT_BathroomDoor_Backplate", 0.080, 0.028,
               (bx, by, bz), LG, mats["blacksteel"], segments=24,
               rotation=(radians(90), 0, 0))
    L.cylinder_between("LGT_BathroomDoor_Arm", 0.012,
                       (bx, by - 0.015, bz),
                       (bx, by - 0.135, bz - 0.035), LG,
                       mats["blacksteel"], segments=10)
    L.cylinder("LGT_BathroomDoor_PorcelainSocket", 0.034, 0.072,
               (bx, by - 0.155, bz - 0.045), LG,
               mats["enamel_white"], segments=20,
               rotation=(radians(90), 0, 0))
    # A2: someone replaced this bulb with a daylight one out of the drawer,
    # which is what actually happens in a back hall nobody art-directs. The
    # cool globe is the visible motivator for the cool point light below and
    # separates the rear corridor from the amber room in front of it.
    L.uv_sphere("LGT_BathroomDoor_Bulb", 0.040,
                (bx, by - 0.205, bz - 0.055), LG,
                mats["bulb_cool"], segments=22, rings=12)
    for i, (radius, depth) in enumerate(((0.065, 0.010), (0.098, 0.010),
                                         (0.082, 0.010))):
        L.ring("LGT_BathroomDoor_CageRing_%d" % i,
               radius - 0.004, radius + 0.004, depth,
               (bx, by - 0.205 - i * 0.020,
                bz - 0.055), LG, mats["blacksteel"], segments=28,
               rotation=(radians(90), 0, 0))
    # Cool now, and quieter: a daylight bulb reads brighter than a warm one at
    # equal wattage, so the energy drops with the colour change.
    point("LGT_BathroomDoor_Practical", 58.0, 0.075,
          (bx, by - 0.235, bz - 0.075), (0.76, 0.85, 1.0),
          "visible_caged_restroom_door_cool_bulb")

    # ------------------------------------- street spill through the glass --
    # rainy sodium-free night: cool blue-green, motivated by the storefront
    area("LGT_StreetSpill", 62.0, C.ROOM_W - 1.2,
         (0, -C.ROOM_L / 2.0 - 0.06, 1.45), rot=(radians(90), 0, 0),
         colour=(0.55, 0.78, 1.0), shape="RECTANGLE", size_y=1.7,
         spread=120.0)
    # Moving cars and opposite shop boxes contaminate the glass with small
    # red and amber zones instead of one featureless blue exterior fill.
    area("LGT_StreetTailLightSpill", 18.0, 1.05,
         (-1.38, -C.ROOM_L / 2.0 - 0.055, 0.92),
         rot=(radians(90), 0, 0), colour=(1.0, 0.035, 0.012),
         shape="RECTANGLE", size_y=0.32, spread=115.0,
         motivation="visible_red_car_lights_in_street_backdrop")
    area("LGT_StreetShopSignSpill", 20.0, 1.25,
         (0.25, -C.ROOM_L / 2.0 - 0.055, 1.46),
         rot=(radians(90), 0, 0), colour=(1.0, 0.48, 0.12),
         shape="RECTANGLE", size_y=0.52, spread=120.0,
         motivation="visible_opposite_small_business_signs")
    # cooler contamination at the service door so the rear separates
    area("LGT_ServiceDoor_Spill", 5.0, 0.62,
         (C.DD_SERVICE_DOOR_X, C.ROOM_L / 2.0 - 0.10, 0.035),
         rot=(radians(-90), 0, 0), colour=(0.72, 0.86, 1.0),
         shape="RECTANGLE", size_y=0.025, spread=110.0)

    # ------------------------------------------------- A2 cool CRT spill ---
    # The CRT in the north corner is left in standby (PROP_CRT_Screen carries
    # MAT_Prop_CRT_ScreenStandby). This is its spill, and nothing else in that
    # corner is cold. Deliberately weak: it should tint the wall and the top
    # of the payphone run, not light the room.
    area("LGT_CRT_Spill", 3.2, 0.52,
         (-C.ROOM_W / 2.0 + 0.62, 4.05, 2.40),
         rot=(0, radians(90), 0), colour=(0.42, 0.62, 0.92),
         shape="RECTANGLE", size_y=0.34, spread=125.0,
         motivation="visible_crt_screen_in_standby")

    # ----------------------------------------- A6 per-tube neon variance ---
    # Real neon does not run matched. Each tube gets its own material copy so
    # the emission can differ per tube; one POOL tube runs tired at 70%. The
    # variance is seeded, so a rebuild reproduces the same imperfection.
    _neon_tube_variance()

    # -------------------------------------------------------- atmosphere ---
    # A low-density volume only where the pool beam lives, so the brightest
    # light picks up a hint of dust without turning the room smoky.
    # The volume must start ABOVE the rail top. A table-level camera that ends
    # up inside a scatter box renders to black, which is exactly what the
    # 85 mm rack camera did.
    vz0 = C.BED_Z + 0.62          # clears every table-level camera
    vz1 = C.ROOM_H - 0.05
    vol = L.box("ATM_PoolBeam_Volume",
                (C.PLAY_W + 0.9, C.PLAY_L + 0.9, vz1 - vz0),
                (CX, CY, (vz0 + vz1) / 2.0), AT, None)
    vol.hide_select = True
    m = bpy.data.materials.get("MAT_Atmosphere_Haze")
    if m is None:
        m = bpy.data.materials.new("MAT_Atmosphere_Haze")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    sc = nt.nodes.new("ShaderNodeVolumeScatter")
    sc.inputs["Density"].default_value = 0.0032        # deliberately faint
    sc.inputs["Anisotropy"].default_value = 0.35
    sc.inputs["Color"].default_value = (1.0, 0.95, 0.88, 1.0)
    nt.links.new(sc.outputs["Volume"], out.inputs["Volume"])
    vol.data.materials.append(m)

    # ------------------------------------------------- A1 whole-room haze ---
    # The single biggest lever on this room: air. Light in a bar is visible
    # because it travels through smoke and dust, and without a real medium
    # every fixture just deposits a pool on a surface and stops. This is an
    # interior cube fitted 10 cm short of the shell on every side, carrying a
    # Principled Volume.
    #
    # ENGINE SPLIT (INVARIANT). Cycles stills use THIS volume. EEVEE film does
    # not: this project measured EEVEE volumetrics as blocky froxel dots on
    # dark walls, and a camera inside a scatter box renders black - which is
    # exactly why ATM_PoolBeam_Volume above starts above rail height. Every
    # camera in the room sits inside this cube, so EEVEE must never see it.
    #
    # The split is implemented ONLY through hide_render, and the SAVED state
    # of every blend keeps this volume hidden - EEVEE-safe by default, and the
    # locks fingerprint that hidden state. The render entry scripts flip it in
    # memory and never save.
    hz_inset = 0.10
    hz0, hz1 = hz_inset, C.ROOM_H - hz_inset
    haze = L.box("ATM_RoomHaze_Volume",
                 (C.ROOM_W - hz_inset * 2.0,
                  C.ROOM_L - hz_inset * 2.0,
                  hz1 - hz0),
                 (0.0, 0.0, (hz0 + hz1) / 2.0), AT, None)
    haze.hide_select = True
    haze.hide_render = True          # SAVED STATE: off. Cycles path flips it.
    haze["engine_split"] = "cycles_only_real_volume"
    hm = bpy.data.materials.get("MAT_Atmosphere_RoomHaze")
    if hm is None:
        hm = bpy.data.materials.new("MAT_Atmosphere_RoomHaze")
    hm.use_nodes = True
    hnt = hm.node_tree
    hnt.nodes.clear()
    hout = hnt.nodes.new("ShaderNodeOutputMaterial")
    pv = hnt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density"].default_value = C.DD_ROOM_HAZE_DENSITY
    pv.inputs["Anisotropy"].default_value = 0.30
    pv.inputs["Color"].default_value = (1.0, 0.97, 0.92, 1.0)
    hnt.links.new(pv.outputs["Volume"], hout.inputs["Volume"])
    haze.data.materials.append(hm)

    n = len(L.get_collection(LG).objects)
    print("  [lighting] %d fixture/light objects, faint pool-beam volume" % n)
    return True


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
