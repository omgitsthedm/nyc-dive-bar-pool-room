"""Current-shift barware and seat-scaled evidence of patrons.

The room is worn, not abandoned. Ten actively served drinks sit where a real
person can reach them from an authored stool, booth bench or cafe chair. Fill
levels, straw angles and coaster use vary, but no dirty empties or food debris
are introduced.

Owns: 06_PATRON_FOOTPRINTS.
"""
import math
import os
import sys
from math import radians

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402


D = "06_PATRON_FOOTPRINTS"
PINT_H = C.DD_PINT_GLASS_H
PINT_R = C.DD_PINT_GLASS_D / 2.0
ROCKS_H = C.DD_ROCKS_GLASS_H
ROCKS_R = C.DD_ROCKS_GLASS_D / 2.0


def _tag_component(ob, owner, role):
    ob["owning_drink"] = owner
    ob["component_role"] = role
    ob["current_shift_state"] = "active_tidy_service"
    return ob


def _coaster(prefix, x, y, surface_z, mats, empty=False):
    coaster = L.cylinder(prefix + "_Coaster", C.DD_SERVICE_COASTER_D / 2.0,
                         C.DD_SERVICE_COASTER_T,
                         (x, y, surface_z + C.DD_SERVICE_COASTER_T / 2.0),
                         D, mats["coaster_pulp"], segments=40)
    coaster["patron_footprint"] = True
    coaster["coaster_state"] = "dry_current_service"
    coaster["supports_active_drink"] = not empty
    coaster["current_shift_state"] = "active_tidy_service"
    ink = L.ring(prefix + "_CoasterInk", 0.033, 0.040, 0.00024,
                 (x, y, surface_z + C.DD_SERVICE_COASTER_T + 0.00012),
                 D, mats["coaster_print"], segments=40)
    ink["owning_coaster"] = coaster.name
    ink["current_shift_state"] = "active_tidy_service"
    return surface_z + C.DD_SERVICE_COASTER_T


def _direct_condensation_ring(prefix, x, y, surface_z, mats):
    ring = L.ring(prefix + "_FreshCondensationRing", 0.035, 0.040,
                  0.00020, (x, y, surface_z + 0.00010), D,
                  mats["condensation"], segments=48)
    ring["patron_footprint"] = True
    ring["surface_state"] = "fresh_wipeable_condensation_not_stain"
    ring["current_shift_state"] = "active_tidy_service"
    return surface_z


def _condensation(prefix, x, y, support_z, glass_h, glass_r, mats, phase):
    for i in range(3):
        a = phase + i * 2.14
        z = support_z + glass_h * (0.24 + i * 0.17)
        r = 0.0018 + 0.00045 * ((i + phase) % 2)
        drop = L.uv_sphere(prefix + "_Condensation_%d" % i, r,
                           (x + (glass_r + 0.0008) * math.cos(a),
                            y + (glass_r + 0.0008) * math.sin(a), z),
                           D, mats["condensation"], segments=10, rings=6)
        _tag_component(drop, prefix, "fresh_condensation_droplet")


def _metadata(glass, prefix, style, zone, seat, support_z, coaster_mode,
              fill_fraction):
    reach = math.hypot(glass.location.x - seat[0],
                       glass.location.y - seat[1])
    glass["served_drink"] = True
    glass["drink_id"] = prefix
    glass["drink_style"] = style
    glass["service_zone"] = zone
    glass["seat_anchor_x"] = round(seat[0], 5)
    glass["seat_anchor_y"] = round(seat[1], 5)
    glass["human_reach_m"] = round(reach, 5)
    glass["support_z"] = round(support_z, 5)
    glass["coaster_mode"] = coaster_mode
    glass["fill_fraction"] = fill_fraction
    glass["current_shift_state"] = "active_tidy_service"
    glass["glassware_source"] = "Libbey_Foodservice_manufacturer_dimensions"
    glass["patron_footprint"] = True


def _pint(prefix, x, y, support_z, zone, seat, coaster_mode,
          fill_fraction, mats, phase=0.0):
    # 16 oz Libbey 1639HT mixing glass: a heavy base and a gentle flare from
    # 3.5-inch mouth to a narrower lower wall. The return path creates actual
    # wall and base thickness rather than a transparent solid cylinder.
    profile = (
        (0.0330, 0.0000), (0.0390, 0.0055),
        (0.0400, PINT_H * 0.90), (PINT_R, PINT_H),
        (PINT_R - 0.0026, PINT_H),
        (0.0373, PINT_H * 0.89), (0.0365, 0.0090), (0.0290, 0.0090),
    )
    glass = L.revolved_surface(prefix + "_Glass", profile, D,
                               mats["glass_clear"], segments=48,
                               location=(x, y, support_z), close_profile=True)
    _metadata(glass, prefix, "pint_beer", zone, seat, support_z,
              coaster_mode, fill_fraction)
    glass["official_height_m"] = round(PINT_H, 6)
    glass["official_diameter_m"] = round(C.DD_PINT_GLASS_D, 6)

    liquid_bottom = 0.010
    liquid_top = 0.014 + (PINT_H - 0.027) * fill_fraction
    liquid_h = liquid_top - liquid_bottom
    liquid = L.cylinder(prefix + "_Beer", 0.0374, liquid_h,
                        (x, y, support_z + liquid_bottom + liquid_h / 2.0),
                        D, mats["beer_amber"], segments=48)
    _tag_component(liquid, prefix, "beer")
    foam_h = 0.007 + 0.003 * fill_fraction
    foam = L.cylinder(prefix + "_FoamHead", 0.0381, foam_h,
                      (x, y, support_z + liquid_top + foam_h / 2.0),
                      D, mats["beer_foam"], segments=48)
    _tag_component(foam, prefix, "beer_foam_head")
    for i, (dx, dy, rr) in enumerate((
            (-0.013, -0.006, 0.0018), (0.002, -0.012, 0.0021),
            (0.014, 0.002, 0.0016), (-0.005, 0.012, 0.0020),
            (0.010, 0.013, 0.0015))):
        bubble = L.uv_sphere(prefix + "_FoamBubble_%d" % i, rr,
                             (x + dx, y + dy,
                              support_z + liquid_top + foam_h * 0.78),
                             D, mats["beer_foam"], segments=14, rings=8)
        _tag_component(bubble, prefix, "beer_foam_bubble")
    _condensation(prefix, x, y, support_z, PINT_H, PINT_R, mats, phase)
    return glass


def _lime_wheel(prefix, x, y, z, angle, mats):
    # Wheel centre clips the rim; its axis is horizontal/radial and its plane
    # remains vertical. Pulp and radial membranes make it read as cut citrus.
    nx, ny = math.cos(angle), math.sin(angle)
    cx, cy = x + 0.041 * nx, y + 0.041 * ny
    outer = L.cylinder_between(prefix + "_LimeRind", 0.021,
                               (cx - nx * 0.0020, cy - ny * 0.0020, z),
                               (cx + nx * 0.0020, cy + ny * 0.0020, z),
                               D, mats["garnish_lime"], segments=32)
    _tag_component(outer, prefix, "lime_rind")
    pulp = L.cylinder_between(prefix + "_LimePulp", 0.0172,
                              (cx - nx * 0.0022, cy - ny * 0.0022, z),
                              (cx + nx * 0.0022, cy + ny * 0.0022, z),
                              D, mats["lime_pulp"], segments=32)
    _tag_component(pulp, prefix, "lime_pulp")
    tx, ty = -ny, nx
    face = (nx * 0.00235, ny * 0.00235, 0.0)
    for i, a in enumerate((-0.92, -0.30, 0.34, 0.96)):
        end = (cx + face[0] + tx * 0.015 * math.cos(a),
               cy + face[1] + ty * 0.015 * math.cos(a),
               z + 0.015 * math.sin(a))
        spoke = L.cylinder_between(prefix + "_LimeMembrane_%d" % i,
                                   0.00065,
                                   (cx + face[0], cy + face[1], z), end,
                                   D, mats["garnish_lime"], segments=7)
        _tag_component(spoke, prefix, "lime_membrane")


def _rocks(prefix, x, y, support_z, zone, seat, coaster_mode,
           fill_fraction, mats, phase=0.0, straw_red=False):
    # 10 oz Libbey 15232 Gibraltar rocks glass: eight flat facets and the
    # manufacturer's 3.5 x 3.88 inch envelope.
    profile = (
        (0.0355, 0.0000), (0.0395, 0.0065),
        (0.0410, ROCKS_H * 0.83), (ROCKS_R, ROCKS_H),
        (ROCKS_R - 0.0028, ROCKS_H),
        (0.0380, ROCKS_H * 0.81), (0.0365, 0.0100), (0.0305, 0.0100),
    )
    glass = L.revolved_surface(prefix + "_Glass", profile, D,
                               mats["glass_clear"], segments=8,
                               location=(x, y, support_z), close_profile=True)
    for polygon in glass.data.polygons:
        polygon.use_smooth = False
    _metadata(glass, prefix, "rocks_lime", zone, seat, support_z,
              coaster_mode, fill_fraction)
    glass["official_height_m"] = round(ROCKS_H, 6)
    glass["official_diameter_m"] = round(C.DD_ROCKS_GLASS_D, 6)
    glass["glass_profile"] = "eight_sided_Gibraltar"

    liquid_bottom = 0.010
    liquid_top = 0.015 + (ROCKS_H - 0.032) * fill_fraction
    liquid_h = liquid_top - liquid_bottom
    liquid = L.cylinder(prefix + "_Cocktail", 0.0370, liquid_h,
                        (x, y, support_z + liquid_bottom + liquid_h / 2.0),
                        D, mats["cocktail_amber"], segments=8, smooth=False)
    _tag_component(liquid, prefix, "cocktail")

    ice_specs = ((-0.011, -0.004, 10.0), (0.010, 0.007, -13.0),
                 (-0.002, 0.014, 31.0))
    for i, (dx, dy, yaw) in enumerate(ice_specs):
        cube = L.box(prefix + "_Ice_%d" % i,
                     (0.024, 0.023, 0.022 + i * 0.001),
                     (x + dx, y + dy,
                      support_z + 0.040 + i * 0.015), D, mats["ice"],
                     rotation=(radians(4 - i * 3), radians(i * 5),
                               radians(yaw)), bevel=0.003,
                     bevel_segments=2)
        _tag_component(cube, prefix, "cocktail_ice")

    straw_end = (x + 0.017 * math.cos(phase),
                 y + 0.017 * math.sin(phase),
                 support_z + ROCKS_H + 0.052)
    straw = L.cylinder_between(prefix + "_Straw", 0.0027,
                               (x - 0.007, y + 0.004,
                                support_z + 0.032), straw_end,
                               D, mats["straw_red" if straw_red else
                                       "straw_black"], segments=10)
    _tag_component(straw, prefix, "cocktail_straw")
    _lime_wheel(prefix, x, y, support_z + ROCKS_H * 0.91,
                phase + 0.62, mats)
    _condensation(prefix, x, y, support_z, ROCKS_H, ROCKS_R, mats, phase)
    return glass


def _serve(spec, mats):
    (prefix, style, x, y, surface_z, zone, seat, coaster_mode,
     fill_fraction, phase) = spec
    if coaster_mode == "coaster":
        support_z = _coaster(prefix, x, y, surface_z, mats)
    else:
        support_z = _direct_condensation_ring(prefix, x, y, surface_z, mats)
    if style == "pint_beer":
        return _pint(prefix, x, y, support_z, zone, seat, coaster_mode,
                     fill_fraction, mats, phase)
    return _rocks(prefix, x, y, support_z, zone, seat, coaster_mode,
                  fill_fraction, mats, phase, straw_red=int(phase * 10) % 2 == 0)


def build(mats):
    L.clear_collection(D)

    # Bar anchors follow the four deliberately misaligned stools. Three people
    # have drinks; the fourth has stepped over to the pool table and left a dry
    # coaster and open tab. Nothing is arranged in a showroom-straight row.
    stools = [(C.DD_BAR_TOP_X + 0.72 + pull,
               C.DD_BAR_CENTRE_Y + oy)
              for oy, pull, _yaw, _variant in C.DD_BAR_STOOL_LAYOUT]
    bar_z = C.BAR_HEIGHT + 0.0005

    booth0_x = -C.ROOM_W / 2.0 + 0.115 + 0.88 / 2.0
    booth1_x = -C.ROOM_W / 2.0 + 0.105 + 0.84 / 2.0
    b0_y, b1_y = C.DD_BOOTH_LAYOUT[0][0], C.DD_BOOTH_LAYOUT[1][0]

    c0x, c0y, _ = C.DD_CAFE_TABLE_LAYOUT[0]
    c1x, c1y, _ = C.DD_CAFE_TABLE_LAYOUT[1]

    specs = (
        ("PATRON_Bar_00_Pint", "pint_beer", -1.345, stools[0][1] - 0.07,
         bar_z, "bar", stools[0], "direct_guest_placement", 0.88, 0.31),
        ("PATRON_Bar_01_Rocks", "rocks_lime", -1.335, stools[1][1] + 0.04,
         bar_z, "bar", stools[1], "coaster", 0.72, 1.18),
        ("PATRON_Bar_02_Pint", "pint_beer", -1.350, stools[2][1] - 0.03,
         bar_z, "bar", stools[2], "coaster", 0.63, 2.04),

        ("PATRON_Booth0_03_Rocks", "rocks_lime", booth0_x - 0.16,
         b0_y - 0.12, 0.761, "booth", (booth0_x - 0.11, b0_y - 0.42),
         "coaster", 0.81, 0.72),
        ("PATRON_Booth0_04_Pint", "pint_beer", booth0_x + 0.16,
         b0_y + 0.12, 0.761, "booth", (booth0_x + 0.10, b0_y + 0.42),
         "coaster", 0.77, 1.56),
        ("PATRON_Booth1_05_Pint", "pint_beer", booth1_x - 0.14,
         b1_y + 0.13, 0.761, "booth", (booth1_x - 0.08, b1_y + 0.43),
         "coaster", 0.91, 2.42),
        ("PATRON_Booth1_06_Rocks", "rocks_lime", booth1_x + 0.15,
         b1_y - 0.13, 0.761, "booth", (booth1_x + 0.09, b1_y - 0.43),
         "coaster", 0.66, 2.94),

        ("PATRON_Cafe0_07_Rocks", "rocks_lime", c0x - 0.16, c0y + 0.03,
         0.759, "cafe", (c0x - 0.51, c0y - 0.05), "coaster", 0.74, 0.96),
        ("PATRON_Cafe0_08_Pint", "pint_beer", c0x + 0.16, c0y + 0.05,
         0.759, "cafe", (c0x + 0.39, c0y + 0.13), "coaster", 0.83, 2.18),
        ("PATRON_Cafe1_09_Rocks", "rocks_lime", c1x - 0.14, c1y - 0.04,
         0.759, "cafe", (c1x - 0.46, c1y - 0.17), "coaster", 0.69, 2.72),
    )

    for spec in specs:
        _serve(spec, mats)

    # Dry place setting and a folded open tab imply that stool four's patron
    # is shooting, not that staff have abandoned dirty glassware.
    empty_x, empty_y = -1.340, stools[3][1] + 0.025
    _coaster("PATRON_Bar_03_Away", empty_x, empty_y, bar_z, mats, empty=True)
    tab = L.box("PATRON_Bar_03_OpenTab", (0.070, 0.115, 0.0012),
                (-1.445, empty_y + 0.085, bar_z + 0.0006), D,
                mats["paper_aged"], rotation=(0, 0, radians(-11)),
                bevel=0.001)
    tab["patron_footprint"] = True
    tab["service_state"] = "open_tab_patron_temporarily_at_pool_table"
    tab["current_shift_state"] = "active_tidy_service"

    # One clean folded cocktail napkin is a service cue, not table litter.
    napkin = L.box("PATRON_Booth0_03_CleanNapkin",
                   (0.085, 0.085, 0.0012),
                   (booth0_x - 0.06, b0_y - 0.06, 0.7616), D,
                   mats["paper_aged"], rotation=(0, 0, radians(8)),
                   bevel=0.001)
    napkin["patron_footprint"] = True
    napkin["service_state"] = "clean_current_service_napkin"
    napkin["current_shift_state"] = "active_tidy_service"

    print("  [patron footprints] 10 active drinks; 5 pints, 5 rocks, "
          "10 dry coasters, 1 direct fresh condensation placement")
    return True


if __name__ == "__main__":
    raise RuntimeError("run through build_all.py so shared materials are supplied")
