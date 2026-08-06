"""55_age_and_story.py — deep patina without active filth.

This stage turns the environment from a newly built themed bar into a room
whose finishes have been handled, repaired, wiped and repainted for decades.
Horizontal hospitality surfaces stay clean for the current shift; their age
comes from finish loss, pale glass rings, softened edges and old scratches.

Owns: 06_PATINA.
"""
import math
import os
import random
import sys
from math import radians

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402


P = "06_PATINA"
HW, HL = C.ROOM_W / 2.0, C.ROOM_L / 2.0


def _story(ob, note):
    ob["secret_story"] = note
    ob["surface_state"] = "old_but_currently_clean"
    return ob


def _irregular_wall_patch(name, axis, plane, horizontal, z, width, height,
                          mat, seed):
    """Nearly flush irregular paint/plaster loss on X- or Y-normal walls."""
    rnd = random.Random(seed)
    verts = []
    points = 12
    for i in range(points):
        angle = math.tau * i / points
        radius = rnd.uniform(0.74, 1.0)
        h = math.cos(angle) * width * 0.5 * radius
        v = math.sin(angle) * height * 0.5 * radius
        if axis == "X":
            verts.append((plane, horizontal + h, z + v))
        else:
            verts.append((horizontal + h, plane, z + v))
    ob = L.mesh_object(name, verts, [tuple(range(points))], P, mat)
    ob["wear_type"] = "paint_or_plaster_finish_loss"
    ob["relief_mm"] = 0.4
    return ob


def _irregular_image_patch(name, axis, plane, horizontal, z, width, height,
                           mat, seed):
    """UV-mapped torn perimeter that stays mathematically flush to a wall."""
    rnd = random.Random(seed)
    coords = []
    count = 7
    for i in range(count):
        coords.append((i / count, rnd.uniform(0.0, 0.035)))
    for i in range(count):
        coords.append((1.0 - rnd.uniform(0.0, 0.028), i / count))
    for i in range(count):
        coords.append((1.0 - i / count, 1.0 - rnd.uniform(0.0, 0.035)))
    for i in range(count):
        coords.append((rnd.uniform(0.0, 0.028), 1.0 - i / count))
    verts = []
    for u, v in coords:
        h = (u - 0.5) * width
        vertical = (v - 0.5) * height
        if axis == "X":
            verts.append((plane, horizontal + h, z + vertical))
        else:
            verts.append((horizontal + h, plane, z + vertical))
    ob = L.mesh_object(name, verts, [tuple(range(len(verts)))], P, mat)
    uv = ob.data.uv_layers.new(name="UVMap")
    for loop in ob.data.polygons[0].loop_indices:
        index = ob.data.loops[loop].vertex_index
        uv.data[loop].uv = coords[index]
    ob["relief_mm"] = 0.0
    return ob


def _horizontal_scratch(name, x, y, z, length, width, yaw, mat):
    ob = L.box(name, (length, min(width, 0.00065), 0.00006), (x, y, z), P, mat,
               rotation=(0, 0, radians(yaw)), bevel=0.00003)
    ob["wear_type"] = "old_finish_scratch"
    ob["cleanliness"] = "wiped_no_active_residue"
    return ob


def _drink_ring(name, x, y, z, radius, mat):
    ob = L.ring(name, max(0.004, radius - 0.00045), radius, 0.00006,
                (x, y, z), P, mat, segments=36)
    ob["wear_type"] = "pale_glass_ring_in_old_finish"
    ob["cleanliness"] = "historical_finish_mark_not_active_spill"
    return ob


def build_architectural_age(mats):
    # Boxed prewar cross beams are structurally plausible below the pressed tin
    # and visibly carry splits, old straps and repeated coats at their ends.
    beam_z = C.ROOM_H - 0.135
    for i, y in enumerate((-4.28, -0.48, 4.62)):
        beam = L.box("ENV_CrossBeam_%d" % i,
                     (C.ROOM_W - 0.18, 0.18, 0.22),
                     (0.0, y, beam_z), P, mats["beam_wood"],
                     rotation=(radians(0.20 * (i - 1)), 0,
                               radians((-0.18, 0.12, -0.09)[i])),
                     bevel=0.009, bevel_segments=2)
        beam["construction_role"] = "boxed_prewar_cross_beam"
        beam["surface_state"] = "old_finish_split_and_hand_repaired"
        split_y = y - 0.035 + i * 0.022
        points = [(-2.65, split_y, beam_z - 0.112),
                  (-1.62, split_y + 0.010, beam_z - 0.116),
                  (-0.45, split_y - 0.006, beam_z - 0.113),
                  (0.78, split_y + 0.012, beam_z - 0.115),
                  (2.42, split_y - 0.004, beam_z - 0.112)]
        crack = L.curve_tube("ENV_CrossBeam_%d_LongSplit" % i, points,
                             0.0022, P, mats["plaster_crack"], resolution=1)
        crack["wear_type"] = "old_timbersplit"
        for side in (-1, 1):
            strap = L.box("ENV_CrossBeam_%d_EndStrap_%s" %
                          (i, "W" if side < 0 else "E"),
                          (0.075, 0.205, 0.235),
                          (side * (HW - 0.19), y, beam_z), P,
                          mats["blacksteel"], bevel=0.004)
            strap["repair_type"] = "old_bolted_beam_strap"
            for zoff in (-0.065, 0.065):
                L.cylinder("ENV_CrossBeam_%d_Bolt_%s_%s" %
                           (i, "W" if side < 0 else "E",
                            "B" if zoff < 0 else "T"),
                           0.012, 0.010,
                           (side * (HW - 0.145), y - 0.102,
                            beam_z + zoff), P, mats["brass"], segments=12,
                           rotation=(radians(90), 0, 0))

    # Plaster loss is concentrated at old moisture paths and touch zones, not
    # uniformly sprayed across the room.
    patches = (
        ("X", -HW + 0.004, -4.42, 2.38, 0.62, 0.38, 11),
        ("X", -HW + 0.004, -1.78, 2.47, 0.72, 0.48, 12),
        ("X", -HW + 0.004, 0.86, 1.42, 0.42, 0.31, 13),
        ("X", -HW + 0.004, 4.86, 2.60, 0.54, 0.34, 14),
        ("X", HW - 0.004, -3.72, 1.42, 0.48, 0.32, 21),
        ("X", HW - 0.004, -0.02, 2.54, 0.58, 0.40, 22),
        ("X", HW - 0.004, 2.32, 1.28, 0.42, 0.28, 23),
        ("X", HW - 0.004, 4.76, 2.36, 0.64, 0.42, 24),
        ("Y", HL - 0.004, -2.78, 2.42, 0.52, 0.34, 31),
        ("Y", HL - 0.004, -0.58, 1.30, 0.50, 0.33, 32),
        ("Y", HL - 0.004, 0.84, 2.62, 0.70, 0.42, 33),
        ("Y", HL - 0.004, 2.74, 1.44, 0.48, 0.30, 34),
    )
    for i, (axis, plane, horizontal, z, w, h, seed) in enumerate(patches):
        _irregular_wall_patch("ENV_WallFinishLoss_%02d" % i, axis, plane,
                              horizontal, z, w, h,
                              mats["plaster_exposed"], seed)

    # Old pipe and roof-line moisture marks are broad, faint and dry.
    _irregular_wall_patch("ENV_WallDryWatermark_Riser", "X", -HW + 0.003,
                          -1.78, 2.60, 0.82, 0.74,
                          mats["wall_watermark"], 88)
    _irregular_wall_patch("ENV_WallDryWatermark_Rear", "Y", HL - 0.003,
                          -2.58, 2.71, 0.66, 0.46,
                          mats["wall_watermark"], 89)

    # Hairline cracks follow stress paths around openings and old repairs.
    crack_paths = (
        ((-HW + 0.002, -4.55, 2.92), (-HW + 0.002, -4.38, 2.62),
         (-HW + 0.002, -4.46, 2.31), (-HW + 0.002, -4.22, 2.02)),
        ((-HW + 0.002, -0.82, 2.88), (-HW + 0.002, -0.68, 2.57),
         (-HW + 0.002, -0.84, 2.28), (-HW + 0.002, -0.66, 1.98)),
        ((HW - 0.002, -2.20, 2.86), (HW - 0.002, -2.06, 2.61),
         (HW - 0.002, -2.18, 2.34), (HW - 0.002, -2.03, 2.08)),
        ((HW - 0.002, 4.78, 2.93), (HW - 0.002, 4.64, 2.67),
         (HW - 0.002, 4.74, 2.39), (HW - 0.002, 4.56, 2.18)),
        ((-2.72, HL - 0.002, 2.90), (-2.58, HL - 0.002, 2.64),
         (-2.66, HL - 0.002, 2.36), (-2.48, HL - 0.002, 2.12)),
        ((0.84, HL - 0.002, 2.92), (0.70, HL - 0.002, 2.70),
         (0.82, HL - 0.002, 2.46), (0.62, HL - 0.002, 2.21)),
    )
    for i, points in enumerate(crack_paths):
        ob = L.curve_tube("ENV_WallHairlineCrack_%02d" % i, points,
                          0.0015 + 0.0002 * (i % 2), P,
                          mats["plaster_crack"], resolution=1)
        ob["wear_type"] = "settlement_hairline"

    # Chair backs and shoes have polished and chipped only the lower wall.
    for i, (side, y, z, length, yaw) in enumerate((
            (-1, -3.28, 0.78, 0.32, 7), (-1, 0.92, 0.71, 0.28, -9),
            (-1, 3.92, 0.82, 0.38, 4), (1, -2.06, 0.68, 0.34, -6),
            (1, 1.36, 0.80, 0.30, 8), (1, 4.38, 0.74, 0.36, -4))):
        x = side * (HW - 0.004)
        L.box("ENV_WainscotChairScuff_%02d" % i,
              (0.001, length, 0.020), (x, y, z), P,
              mats["wood_exposed"],
              rotation=(radians(yaw if side > 0 else -yaw), 0, 0),
              bevel=0.0004)


def build_flat_history_and_street(mats):
    # The bathroom door is a single paper-thin accumulated sticker surface.
    # Its plaque, knob, kick plate and hinges remain proud and functional.
    sticker = L.image_plane("ENV_BathroomDoor_StickerBomb", 0.70, 1.72,
                            (C.DD_BATHROOM_DOOR_X, HL - 0.060, 1.02), P,
                            mats["sticker_bomb"], wall_axis="Y",
                            face_inward=False)
    sticker["mounting_method"] = "adhesive_layers_directly_on_door"
    sticker["visual_sticker_count_estimate"] = 180
    sticker["relief_mm"] = 0.0

    # Broad paper ghosts sit behind the smaller authored notices. They are
    # flush to plaster and therefore do not cast decorative picture shadows.
    paper_fields = (
        ("PROP_Wheatpaste_EastHistory", "X", HW - 0.007, -0.58, 1.86,
         2.80, 1.76, True),
        ("PROP_Wheatpaste_WestHistory", "X", -HW + 0.007, 1.58, 2.03,
         3.55, 1.86, False),
        ("PROP_Wheatpaste_RearHistory", "Y", HL - 0.007, 0.05, 1.90,
         2.88, 1.76, False),
    )
    for index, (name, axis, plane, horizontal, z, width, height,
                _inward) in enumerate(paper_fields):
        ob = _irregular_image_patch(name, axis, plane, horizontal, z,
                                    width, height,
                                    mats["wheatpaste_history"], 710 + index)
        ob["mounting_method"] = "wheat_pasted_directly_to_plaster"
        ob["relief_mm"] = 0.0
        ob["paper_age_span"] = "multiple_decades"

    # A luminous world now exists beyond the glass: opposite-store signs,
    # headlamps, tail lamps and wet-street reflections, not an empty void.
    west_pier_w = 0.55
    door_l = C.DD_FRONT_DOOR_X - C.DD_FRONT_DOOR_W / 2.0
    window_l = -HW + west_pier_w
    window_r = door_l - 0.12
    window_x = (window_l + window_r) / 2.0
    backdrop = L.image_plane("ENV_StreetBackdrop_LESNight",
                             window_r - window_l + 0.30, 2.78,
                             (window_x, -HL - C.WALL_T - 0.28, 1.48), P,
                             mats["street_backdrop"], wall_axis="Y",
                             face_inward=True)
    backdrop["environment_role"] = "opposite_small_businesses_and_car_lights"
    backdrop["source_type"] = "project_original_generated_texture"


def build_booth_damage(mats):
    rnd = random.Random(5519)
    wall_x = -HW
    for booth, (by, run_x, bay_w) in enumerate(C.DD_BOOTH_LAYOUT):
        prefix = "PROP_Booth_%d" % booth
        wall_gap = 0.115 if booth == 0 else 0.105
        bench_x = wall_x + wall_gap + run_x / 2.0
        open_edge_x = wall_x + wall_gap + run_x
        back_t = 0.14
        back_h = 0.58 if booth == 0 else 0.51
        back_offset = bay_w / 2.0 - back_t / 2.0
        seat_offset = back_offset - 0.17
        back_z = 0.49 + back_h / 2.0 - 0.015
        crack_mat = mats["vinyl_crack_red"] if booth == 0 \
            else mats["vinyl_crack_green"]

        for side in (-1, 1):
            tag = "South" if side < 0 else "North"
            seat_y = by + side * seat_offset
            back_y = by + side * back_offset
            # Fine checking on the seat: visible in close views, restrained in
            # the wide so the booth reads as maintained rather than destroyed.
            for crack_i in range(4):
                sx = bench_x - run_x * 0.36 + crack_i * run_x * 0.20 + \
                    rnd.uniform(-0.025, 0.025)
                points = ((sx - 0.025, seat_y - 0.016, 0.557),
                          (sx - 0.006, seat_y - 0.005, 0.5575),
                          (sx + 0.006, seat_y + 0.010, 0.557),
                          (sx + 0.029, seat_y + 0.018, 0.557))
                ob = L.curve_tube(prefix + "_Bench%s_SeatCrack_%d" %
                                  (tag, crack_i), points, 0.00022, P,
                                  crack_mat, resolution=1)
                ob["wear_type"] = "fine_vinyl_checking"

            # One small historic split per bench, with foam only at the narrow
            # opening. No broad shredded upholstery or active dirt.
            tear_x = bench_x + (-0.19 if side < 0 else 0.17) + \
                rnd.uniform(-0.035, 0.035)
            tear = L.box(prefix + "_Bench%s_ExplicitTear" % tag,
                         (0.068, 0.006, 0.002),
                         (tear_x, seat_y - side * 0.018, 0.558), P,
                         crack_mat,
                         rotation=(0, 0, radians(-10 * side)),
                         bevel=0.001)
            tear["wear_type"] = "small_repaired_seat_split"
            foam = L.box(prefix + "_Bench%s_ExposedFoam" % tag,
                         (0.025, 0.0035, 0.0012),
                         (tear_x + 0.008, seat_y - side * 0.018, 0.5575), P,
                         mats["foam_yellow"],
                         rotation=(0, 0, radians(-10 * side)),
                         bevel=0.001)
            foam["wear_type"] = "narrow_foam_at_old_split"

            # Backrest cracks follow the vertical plane and stop before seams.
            face_y = back_y - side * (back_t / 2.0 + 0.006)
            for crack_i in range(2):
                sx = bench_x - run_x * 0.22 + crack_i * run_x * 0.34
                z0 = back_z - back_h * 0.12 + crack_i * 0.055
                points = ((sx - 0.010, face_y, z0 - 0.022),
                          (sx + 0.004, face_y, z0 - 0.004),
                          (sx - 0.006, face_y, z0 + 0.020))
                ob = L.curve_tube(prefix + "_Bench%s_BackCrack_%d" %
                                  (tag, crack_i), points, 0.00020, P,
                                  crack_mat, resolution=1)
                ob["wear_type"] = "fine_vinyl_back_checking"

            # The aisle end cap has the hand-height finish loss expected where
            # generations of patrons have gripped it while sliding out.
            scuff = L.box(prefix + "_Bench%s_EndCapHandWear" % tag,
                          (0.001, 0.052, 0.205),
                          (open_edge_x + 0.001, back_y, back_z + 0.035), P,
                          mats["wood_exposed"], bevel=0.001)
            scuff["wear_type"] = "hand_polished_endcap_finish_loss"


def build_table_and_furniture_history(mats):
    # Booth tables: pale finish ghosts and fine scratches only. They have been
    # wiped today, but nobody protected them with coasters for forty years.
    for booth, (by, _run_x, _bay_w) in enumerate(C.DD_BOOTH_LAYOUT):
        wall_gap = 0.115 if booth == 0 else 0.105
        table_run = 0.88 if booth == 0 else 0.84
        table_x = -HW + wall_gap + table_run / 2.0
        top_z = 0.761
        offsets = ((-0.20, -0.12, 0.046), (0.02, 0.11, 0.039),
                   (0.22, -0.04, 0.051), (0.12, 0.14, 0.033))
        for i, (dx, dy, radius) in enumerate(offsets):
            _drink_ring("PROP_Booth_%d_TableWaterRing_%d" % (booth, i),
                        table_x + dx, by + dy, top_z,
                        radius + booth * 0.002, mats["wood_water_ring"])
        for i, (dx, dy, length, yaw) in enumerate((
                (-0.10, 0.02, 0.23, -8), (0.17, -0.09, 0.17, 13),
                (0.02, 0.15, 0.12, 4))):
            _horizontal_scratch("PROP_Booth_%d_TableScratch_%d" %
                                (booth, i), table_x + dx, by + dy, top_z,
                                length, 0.0035, yaw,
                                mats["wood_exposed"])
        # A pencilled date beneath one table and a lost old token beneath the
        # other are quiet discoveries, not countertop debris.
        if booth == 0:
            token = L.ring("PROP_Booth_0_HiddenTransitToken", 0.006, 0.018,
                           0.002, (table_x + 0.24, by - 0.17, 0.704), P,
                           mats["brass"], segments=24,
                           rotation=(radians(90), 0, 0))
            _story(token, "old_generic_transit_token_caught_under_table_cleat")
        else:
            mark = L.box("PROP_Booth_1_UndersidePencilDate",
                         (0.001, 0.090, 0.006),
                         (table_x - 0.17, by + 0.08, 0.708), P,
                         mats["paper_red"],
                         rotation=(0, radians(2), radians(-8)),
                         bevel=0.0004)
            _story(mark, "faded_pencilled_date_under_table")

    # The two cafe tables carry different decades of ring and edge wear.
    for table, (x, y, radius) in enumerate(C.DD_CAFE_TABLE_LAYOUT):
        top_z = 0.759
        for i, (dx, dy, rr) in enumerate(((-0.09, 0.05, 0.043),
                                          (0.10, -0.06, 0.037),
                                          (0.02, 0.11, 0.049))):
            _drink_ring("PROP_CafeTable_%d_WaterRing_%d" % (table, i),
                        x + dx, y + dy, top_z, rr,
                        mats["wood_water_ring"])
        for i, (dx, dy, length, yaw) in enumerate((
                (-0.04, -0.04, radius * 0.80, 12),
                (0.08, 0.08, radius * 0.58, -17))):
            _horizontal_scratch("PROP_CafeTable_%d_Scratch_%d" %
                                (table, i), x + dx, y + dy, top_z,
                                length, 0.0035, yaw, mats["wood_exposed"])

    # Bar stools and mismatched chairs show contact wear at hands, shoes and
    # seat edges without turning the seating into wreckage.
    for i, (oy, pull, yaw_deg, variant) in enumerate(C.DD_BAR_STOOL_LAYOUT):
        sx, sy = C.DD_BAR_TOP_X + 0.72 + pull, C.DD_BAR_CENTRE_Y + oy
        h = C.DD_BAR_STOOL_SEAT_H + (0.012 if i == 2 else 0.0)
        if "vinyl" in variant or "pedestal" in variant:
            slit = L.box("BAR_Stool_Tear_%d_Patina" % i,
                         (0.080, 0.006, 0.0025),
                         (sx + 0.015, sy - 0.035, h + 0.039), P,
                         mats["vinyl_crack"],
                         rotation=(0, 0, radians(yaw_deg - 9)),
                         bevel=0.001)
            slit["wear_type"] = "small_seat_edge_split"
        else:
            _horizontal_scratch("BAR_Stool_Seat_%d_PatinaWear" % i,
                                sx + 0.02, sy - 0.02, h + 0.030,
                                0.11, 0.004, yaw_deg + 14,
                                mats["wood_exposed"])

    # A few leg-height paint chips record vacuuming, shoes and chair movement.
    chair_scuffs = ((2.03, -3.53, 0.46), (2.93, -3.40, 0.45),
                    (2.00, -2.32, 0.45), (2.88, -2.05, 0.46))
    for i, (x, y, z) in enumerate(chair_scuffs):
        scuff = L.box("PROP_FurnitureEdgeWear_%d" % i,
                      (0.075, 0.006, 0.012), (x, y, z), P,
                      mats["wood_exposed"],
                      rotation=(0, 0, radians((-12, 8, 17, -6)[i])),
                      bevel=0.001)
        scuff["wear_type"] = "seat_edge_finish_loss"


def build_small_secrets(mats):
    # Subtle, placement-specific discoveries reward close cameras without
    # making the room unsanitary or cluttering service surfaces.
    key = L.box("PROP_Secret_OldKeyAboveBathroom", (0.065, 0.018, 0.008),
                (2.28, HL - 0.078, 2.13), P, mats["brass"],
                rotation=(0, radians(8), radians(-12)), bevel=0.002)
    _story(key, "old_key_left_on_bathroom_head_casing")
    L.ring("PROP_Secret_OldKeyBow", 0.010, 0.019, 0.006,
           (2.315, HL - 0.078, 2.13), P, mats["brass"], segments=20,
           rotation=(radians(90), 0, 0))["secret_story"] = \
        "old_key_left_on_bathroom_head_casing"

    # Four sets of initials are tiny finish scratches, not legible signage.
    initials = ((-2.75, 1.34, 0.764, 18), (-2.67, 3.11, 0.764, -11),
                (2.45, -3.48, 0.760, 7), (2.47, -2.08, 0.760, -16))
    for i, (x, y, z, yaw) in enumerate(initials):
        a = _horizontal_scratch("PROP_Secret_TableInitial_%02d_A" % i,
                                x, y, z, 0.045, 0.0025, yaw,
                                mats["wood_exposed"])
        b = _horizontal_scratch("PROP_Secret_TableInitial_%02d_B" % i,
                                x + 0.025, y + 0.010, z, 0.038, 0.0025,
                                yaw + 72, mats["wood_exposed"])
        _story(a, "old_initials_cut_into_table_finish")
        _story(b, "old_initials_cut_into_table_finish")

    # A ghost rectangle marks something removed years ago; a tiny tally under
    # a beam records a pool score only a tall regular might notice.
    ghost = L.image_plane("PROP_Secret_RemovedSignGhost", 0.54, 0.34,
                          (HW - 0.005, 2.72, 2.54), P,
                          mats["plaster_exposed"], wall_axis="X",
                          face_inward=True)
    ghost["mounting_method"] = "paint_fade_outline_of_removed_sign"
    _story(ghost, "ghost_rectangle_where_a_sign_hung_for_decades")
    for i in range(5):
        tally = L.box("PROP_Secret_BeamPoolTally_%d" % i,
                      (0.004, 0.055, 0.001),
                      (-0.18 + i * 0.017, -0.571, C.ROOM_H - 0.248), P,
                      mats["paper_aged"],
                      rotation=(radians(90), 0, radians(-9 + i * 4)),
                      bevel=0.0002)
        _story(tally, "faded_pool_tally_on_beam_underside")


def build(mats):
    L.clear_collection(P)
    build_architectural_age(mats)
    build_flat_history_and_street(mats)
    build_booth_damage(mats)
    build_table_and_furniture_history(mats)
    build_small_secrets(mats)
    n = len(L.get_collection(P).objects)
    print("  [patina] %d objects (age, repairs, flush paper, street, secrets)" % n)
    return True


if __name__ == "__main__":
    import importlib
    m = importlib.import_module("40_build_materials")
    build(m.build())
