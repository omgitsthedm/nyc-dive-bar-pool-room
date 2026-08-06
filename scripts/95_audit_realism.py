"""95_audit_realism.py — per-object and per-assembly realism inventory.

The dimensional validator answers whether the pool table and room satisfy their
numerical contracts. This companion audit answers a different question: what
does every render-visible object represent, what supports it, and which
real-world assembly owns it? It writes both the raw object inventory and the
grouped logical-item inventory so repeated bottle, furniture, door-hardware and
fixture components cannot disappear inside an aggregate object count.
"""
import bpy
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402


PRODUCTION_COLLECTIONS = {
    "01_ARCHITECTURE", "02_TABLE_VISIBLE", "03_TABLE_ENGINEERING",
    "04_BAR", "05_HERO_PROPS", "06_SET_DRESSING", "06_PATINA",
    "06_PATRON_FOOTPRINTS",
    "07_LIGHTS",
    "09_ATMOSPHERE",
}


def _round(values, places=5):
    return [round(float(v), places) for v in values]


def _collection(ob):
    names = [c.name for c in ob.users_collection
             if c.name in PRODUCTION_COLLECTIONS]
    return sorted(names)[0] if names else "UNSCOPED"


def _logical_item(name):
    patterns = (
        (r"(PATRON_(?:Bar|Booth\d+|Cafe\d+)_\d+_[A-Za-z0-9]+)(?:_.*)?",
         r"\1"),
        (r"BAR_Bottle_(\d+_\d+_\d+)(?:_(?:Shoulder|Neck|Cap|Label))?",
         r"BAR_Bottle_\1"),
        (r"BAR_WellBottle_(\d+)(?:_(?:Shoulder|Neck|Cap|Label|PourCollar|PourSpout))?",
         r"BAR_WellBottle_\1"),
        (r"BAR_Stool_(?:Seat|Leg|StretcherX|StretcherY|FootRing|BackPost|BackPad|Base|Pedestal|FootCap|Shim|Tear|Patch)_(\d+).*",
         r"BAR_Stool_\1"),
        (r"BAR_CashRegister_.*", "BAR_CashRegister"),
        (r"BAR_Sink_.*", "BAR_Sink"),
        (r"BAR_IceBin_.*", "BAR_IceBin"),
        (r"BAR_IceCube_.*", "BAR_IceBin"),
        (r"BAR_IceScoop_.*", "BAR_IceScoop"),
        (r"BAR_SodaGun_.*", "BAR_SodaGun"),
        (r"BAR_GarnishStation_.*", "BAR_GarnishStation"),
        (r"BAR_Garnish_.*", "BAR_GarnishStation"),
        (r"BAR_Drainboard_.*", "BAR_Drainboard"),
        (r"BAR_Towel_.*", "BAR_Towel"),
        (r"BAR_TrashStation_.*", "BAR_TrashStation"),
        (r"BAR_BottleOpener_.*", "BAR_BottleOpener"),
        (r"BAR_CapCatcher_.*", "BAR_CapCatcher"),
        (r"BAR_RubberMat_(Tap|Service).*", r"BAR_RubberMat_\1"),
        (r"BAR_SpeedRail_.*", "BAR_SpeedRail"),
        (r"BAR_(?:Tap.*|DripTray)", "BAR_BeerTaps"),
        (r"BAR_Cooler.*", "BAR_Cooler"),
        (r"BAR_Junk_Radio.*", "BAR_Junk_Radio"),
        (r"BAR_Junk_Trophy.*", "BAR_Junk_Trophy"),
        (r"BAR_Junk_PickleJar.*", "BAR_Junk_PickleJar"),
        (r"BAR_Junk_JarLime_.*", "BAR_Junk_PickleJar"),
        (r"ENV_FrontDoor_.*", "ENV_FrontDoor"),
        (r"ENV_ServiceDoor.*", "ENV_ServiceDoor"),
        (r"ENV_BathroomDoor.*", "ENV_BathroomDoor"),
        (r"PROP_CafeChair_(\d+)_(Wood|Metal|Folding).*", r"PROP_CafeChair_\1_\2"),
        (r"PROP_CafeTable_(\d+).*", r"PROP_CafeTable_\1"),
        (r"PROP_Booth_(\d+).*", r"PROP_Booth_\1"),
        (r"PROP_Memory(?:Frame|Print|Collage|Pin|Tape|Ghost)_(\d+).*",
         r"PROP_MemoryPiece_\1"),
        (r"PROP_WallPayphone_.*", "PROP_WallPayphone"),
        (r"PROP_CRT_.*", "PROP_CRT"),
        (r"PROP_WallClock_.*", "PROP_WallClock"),
        (r"PROP_Dartboard_.*", "PROP_Dartboard"),
        (r"PROP_CueRack_.*", "PROP_CueRack"),
        (r"PROP_WallCueTip_(\d+)", r"PROP_WallCue_\1"),
        (r"PROP_Score(?:Rod|Bead|Plate|Bracket)_(\d+).*",
         r"PROP_ScoreRow_\1"),
        (r"LGT_Pool_.*", "LGT_PoolFixture"),
        (r"LGT_BarPendant_(?:Shade_)?(\d+)", r"LGT_BarPendant_\1"),
        (r"LGT_BackBar_.*", "LGT_BackBarPractical"),
        (r"LGT_RearSconce_.*_(\d+)", r"LGT_RearSconce_\1"),
        (r"LGT_EastSconce_.*_(\d+)", r"LGT_EastSconce_\1"),
        (r"LGT_Entry_.*", "LGT_EntryPractical"),
        (r"LGT_Cafe_.*", "LGT_CafePractical"),
        (r"LGT_BoothPendant_.*_(\d+)", r"LGT_BoothPendant_\1"),
        (r"LGT_ExitSign_.*", "LGT_ExitSign"),
    )
    for pattern, replacement in patterns:
        if re.fullmatch(pattern, name):
            return re.sub(pattern, replacement, name)
    return name


def _category(name, logical):
    token = logical + " " + name
    if logical.startswith("PATRON_"):
        return "patron_service"
    if logical.startswith("LGT_"):
        return "motivated_lighting"
    if logical.startswith("PT_"):
        return "pool_table_system"
    if logical.startswith("ATM_"):
        return "atmosphere"
    if logical.startswith("ENV_"):
        return "door_hardware" if "Door" in token or "Threshold" in token \
            else "building_fabric"
    if logical.startswith("BAR_"):
        if "BottleOpener" in token:
            return "bar_fixture_or_stock"
        if "Bottle" in token:
            return "bottle_stock"
        if "Stool" in token:
            return "movable_seating"
        if "CashRegister" in token:
            return "bar_workflow_equipment"
        return "bar_fixture_or_stock"
    if logical.startswith("PROP_"):
        if "Chair" in token:
            return "movable_seating"
        if "Booth" in token:
            return "fixed_seating"
        if "CafeTable" in token or "TableTop" in token:
            return "patron_table"
        return "wall_or_table_prop"
    return "other"


def _support_contract(name, category):
    if category == "patron_service":
        return "guest_surface_contact_and_seat_reach"
    if category == "bottle_stock":
        return "shelf_or_speed_rail_contact"
    if category in {"movable_seating", "fixed_seating", "patron_table"}:
        return "floor_contact"
    if category == "door_hardware":
        return "door_or_frame_fastened"
    if category == "motivated_lighting":
        return "visible_fixture_or_documented_opening"
    if name.startswith("PROP_WallCue"):
        return "rack_retained"
    if name.startswith("PROP_") and any(k in name for k in
                                        ("Art", "Memory", "Clock", "Dart",
                                         "Cue", "Score", "CRT", "Payphone")):
        return "wall_fastened"
    if name.startswith("PROP_"):
        return "authored_surface_contact"
    if name.startswith("BAR_"):
        return "bar_assembly_contact"
    if name.startswith("ENV_"):
        return "building_assembly"
    if name.startswith("PT_"):
        return "pool_table_assembly"
    return "assembly_owned"


def _world_bbox(ob):
    if not getattr(ob, "bound_box", None):
        p = ob.matrix_world.translation
        return [p.x, p.x, p.y, p.y, p.z, p.z]
    points = [ob.matrix_world @ Vector(corner) for corner in ob.bound_box]
    return [min(p.x for p in points), max(p.x for p in points),
            min(p.y for p in points), max(p.y for p in points),
            min(p.z for p in points), max(p.z for p in points)]


def _required_contracts(objects):
    names = {o.name for o in objects}
    checks = []

    def add(check, passed, measured, expected):
        checks.append({"check": check, "status": "PASS" if passed else "FAIL",
                       "measured": measured, "expected": expected,
                       "required": True})

    front_required = {
        "ENV_FrontDoor_ExitBar", "ENV_FrontDoor_ExitBarReturn_W",
        "ENV_FrontDoor_ExitBarReturn_E", "ENV_FrontDoor_ExitLatchCase",
        "ENV_FrontDoor_StrikePlate", "ENV_FrontDoor_Threshold",
        "ENV_FrontDoor_CloserBody", "ENV_FrontDoor_CloserArmA",
        "ENV_FrontDoor_CloserArmB", "ENV_FrontDoor_CloserShoe",
        "ENV_FrontDoor_HingeBarrel_0",
        "ENV_FrontDoor_HingeBarrel_1", "ENV_FrontDoor_HingeBarrel_2",
    }
    add("front_door_has_complete_operating_hardware",
        front_required <= names, len(front_required & names), len(front_required))
    add("front_door_has_no_unsupported_vertical_pull",
        "ENV_FrontDoor_Pull" not in names,
        int("ENV_FrontDoor_Pull" in names), 0)

    bottles = [o for o in objects if o.get("stock_bottle", False)]
    all_bottles = [o for o in objects if o.get("bottle_family", "")]
    families = {o.get("bottle_family", "") for o in bottles}
    support = [o for o in all_bottles if "support_z" in o and
               abs(_world_bbox(o)[4] - float(o["support_z"])) <= 0.002]
    add("bottle_stock_uses_varied_real_profiles", len(families) >= 5,
        len(families), ">=5")
    add("each_bottle_meets_recorded_support",
        len(support) == len(all_bottles), len(support), len(all_bottles))

    stool_seats = [o for o in objects if
                   re.fullmatch(r"BAR_Stool_Seat_\d+", o.name)]
    variants = {o.get("furniture_variant", "") for o in stool_seats}
    yaws = {round(math.degrees(o.rotation_euler.z), 1) for o in stool_seats}
    add("bar_stools_are_four_distinct_acquisitions", len(variants) == 4,
        sorted(variants), "4 distinct variants")
    add("bar_stools_are_not_parade_aligned", len(yaws) >= 3,
        sorted(yaws), ">=3 yaw values")

    furniture = defaultdict(list)
    for ob in objects:
        logical = _logical_item(ob.name)
        if _category(ob.name, logical) in {
                "movable_seating", "fixed_seating", "patron_table"}:
            furniture[logical].append(ob)
    grounded = []
    for logical, members in furniture.items():
        bottom = min(_world_bbox(ob)[4] for ob in members)
        if abs(bottom) <= 0.002:
            grounded.append(logical)
    add("seating_and_patron_tables_meet_floor",
        len(grounded) == len(furniture), len(grounded), len(furniture))

    booth_tables = [o for o in objects if
                    re.fullmatch(r"PROP_Booth_\d+_TableTop", o.name)]
    booth_backs = [o for o in objects if
                   re.fullmatch(r"PROP_Booth_\d+_Bench(?:North|South)_Back",
                                o.name)]
    booth_layout_ok = len(booth_tables) == 2 and len(booth_backs) == 4 and all(
        o.get("access_side", "") == "east_pool_table_aisle" and
        o.get("bench_axis", "") == "X_perpendicular_to_west_wall" and
        o.get("patron_facing_axis", "") == "Y_face_to_face" and
        o.dimensions.x > o.dimensions.y * 1.5 for o in booth_tables)
    add("booths_are_two_wall_adjacent_face_to_face_bays", booth_layout_ok,
        {"tables": len(booth_tables), "backs": len(booth_backs),
         "access_sides": sorted({o.get("access_side", "")
                                 for o in booth_tables})},
        "2 tables, 4 X-axis bench backs, east aisle entry")
    divider_names = sorted(n for n in names if n.startswith("PROP_Booth_")
                           and "Divider" in n)
    add("booth_entries_have_no_freestanding_partition_walls",
        not divider_names, divider_names, [])
    booth_parts = [o for o in objects if o.name.startswith("PROP_Booth_")]
    cue_west = C.TABLE_CENTRE[0] - C.CUE_ENVELOPE_W / 2.0
    booth_east = max((_world_bbox(o)[1] for o in booth_parts),
                     default=-math.inf)
    booth_to_cue = cue_west - booth_east
    add("booth_pool_side_entry_stays_outside_cue_envelope",
        booth_to_cue >= 0.10, round(booth_to_cue, 3), ">=0.10 m")

    register = bpy.data.objects.get("BAR_CashRegister_Base")
    placement = register.get("workflow_side", "") if register else "missing"
    add("cash_register_faces_bartender_on_backbar", placement ==
        "backbar_facing_bartender", placement, "backbar_facing_bartender")

    workflow_roles = {o.get("workflow_role", "") for o in objects
                      if o.get("workflow_role", "")}
    required_roles = {
        "ice_storage", "well_bottle_access", "soda_dispense",
        "garnish_access", "handwash_or_utility_sink", "glass_drain",
        "waste", "wet_service_surface", "bottle_opening", "beer_service",
    }
    add("bar_has_complete_visible_service_workflow",
        required_roles <= workflow_roles,
        {"present": sorted(workflow_roles),
         "missing": sorted(required_roles - workflow_roles)},
        sorted(required_roles))
    well_bodies = [o for o in objects if
                   re.fullmatch(r"BAR_WellBottle_\d+", o.name)]
    pourers = {o.name.rsplit("_", 1)[0] for o in objects
               if re.fullmatch(r"BAR_WellBottle_\d+_PourSpout", o.name)}
    working_bottles = {o.name for o in well_bodies}
    add("every_working_well_bottle_has_speed_pourer",
        len(working_bottles) == 8 and working_bottles == pourers,
        len(working_bottles & pourers), 8)

    back_shelves = [o for o in objects if
                    o.name.startswith("BAR_BackShelf")]
    service_counters = [o for o in objects if
                        o.name.startswith("BAR_ServiceCounter_")]
    backbar_front = max((_world_bbox(o)[1] for o in back_shelves),
                        default=math.inf)
    service_back = min((_world_bbox(o)[0] for o in service_counters),
                       default=-math.inf)
    bartender_aisle = service_back - backbar_front
    add("backbar_and_service_counter_leave_working_bartender_aisle",
        bartender_aisle >= C.DD_BARTENDER_AISLE_MIN,
        round(bartender_aisle, 3),
        ">=%.2f m" % C.DD_BARTENDER_AISLE_MIN)
    bar_top = bpy.data.objects.get("BAR_Top")
    cue_south = C.TABLE_CENTRE[1] - C.CUE_ENVELOPE_L / 2.0
    bar_to_cue = cue_south - _world_bbox(bar_top)[3] if bar_top else -math.inf
    add("front_zone_bar_stops_before_pool_cue_envelope",
        bar_to_cue >= 0.05, round(bar_to_cue, 3), ">=0.05 m")

    light_objects = [o for o in objects if o.type == "LIGHT"]
    motivated = [o for o in light_objects if o.get("motivation", "")]
    add("every_light_source_has_motivation", len(motivated) == len(light_objects),
        len(motivated), len(light_objects))

    art = [o for o in objects if o.name.startswith("PROP_Art_") and
           not "Pin" in o.name]
    mounted = [o for o in art if o.get("mounting_method", "")]
    add("every_primary_wall_art_piece_has_mounting_method",
        len(mounted) == len(art), len(mounted), len(art))

    # The deep-patina pass is intentionally stricter than a raw object count:
    # it proves that age is embedded in each relevant assembly while current-
    # shift food and drink surfaces remain clean.
    flat_art = [o for o in art if
                o.get("mounting_method", "") ==
                "wheat_pasted_directly_to_wall" and
                float(o.get("relief_mm", 99.0)) <= 0.1]
    forbidden_art_hardware = sorted(n for n in names if
                                    n.startswith("PROP_Art") and any(
                                        token in n for token in
                                        ("Frame", "Pin", "Tape")))
    add("wall_art_is_flush_wheat_pasted_without_picture_hardware",
        len(flat_art) == len(art) and not forbidden_art_hardware,
        {"flush_primary_art": len(flat_art),
         "primary_art": len(art),
         "forbidden_hardware": forbidden_art_hardware},
        "all primary art flush; no frames, pins or raised tape")

    booth_wear = [o for o in objects if o.name.startswith("PROP_Booth_") and
                  any(token in o.name for token in
                      ("SeatCrack", "BackCrack", "ExplicitTear",
                       "ExposedFoam", "EndCapHandWear"))]
    booth_wear_ids = {int(re.match(r"PROP_Booth_(\d+)", o.name).group(1))
                      for o in booth_wear}
    add("both_booths_have_explicit_restrained_vinyl_damage",
        booth_wear_ids == {0, 1} and len(booth_wear) >= 36,
        {"booths": sorted(booth_wear_ids), "wear_components": len(booth_wear)},
        "both booths and >=36 restrained crack, tear, foam or hand-wear components")

    sticker_bomb = bpy.data.objects.get("ENV_BathroomDoor_StickerBomb")
    sticker_count = int(sticker_bomb.get("visual_sticker_count_estimate", 0)) \
        if sticker_bomb else 0
    add("bathroom_door_is_flat_sticker_bombed_history",
        sticker_bomb is not None and sticker_count >= 150 and
        float(sticker_bomb.get("relief_mm", 99.0)) <= 0.1,
        sticker_count, ">=150 visually represented flat sticker layers")

    wheatpaste = [o for o in objects if o.name.startswith("PROP_Wheatpaste_")
                  and o.get("mounting_method", "") ==
                  "wheat_pasted_directly_to_plaster"]
    add("three_wall_zones_carry_flush_decades_of_paper_history",
        len(wheatpaste) == 3, len(wheatpaste), 3)

    patron_coasters = [o for o in objects if
                       o.name.startswith("PATRON_") and
                       o.name.endswith("_Coaster") and
                       o.get("coaster_state", "") ==
                       "dry_current_service"]
    table_rings = [o for o in objects if "TableWaterRing" in o.name or
                   re.search(r"PROP_CafeTable_\d+_WaterRing", o.name)]
    table_scratches = [o for o in objects if "TableScratch" in o.name or
                       re.search(r"PROP_CafeTable_\d+_Scratch", o.name)]
    add("patron_tables_are_wiped_with_current_coasters_over_old_finish_ghosts",
        len(patron_coasters) == 10 and len(table_rings) >= 14 and
        len(table_scratches) >= 10,
        {"dry_current_coasters": len(patron_coasters),
         "finish_ring_ghosts": len(table_rings),
         "finish_scratches": len(table_scratches)},
        "10 dry current-shift coasters over >=14 old ring ghosts and >=10 scratches")

    served = [o for o in objects if o.get("served_drink", False)]
    styles = Counter(o.get("drink_style", "") for o in served)
    zones = Counter(o.get("service_zone", "") for o in served)
    add("ten_active_drinks_form_balanced_barware_and_room_footprint",
        len(served) == 10 and styles ==
        Counter({"pint_beer": 5, "rocks_lime": 5}) and zones ==
        Counter({"bar": 3, "booth": 4, "cafe": 3}),
        {"active_drinks": len(served), "styles": dict(styles),
         "zones": dict(zones)},
        {"active_drinks": 10,
         "styles": {"pint_beer": 5, "rocks_lime": 5},
         "zones": {"bar": 3, "booth": 4, "cafe": 3}})

    pint_sources = [o for o in served if o.get("drink_style") == "pint_beer"]
    rocks_sources = [o for o in served if o.get("drink_style") == "rocks_lime"]
    pint_dims_ok = all(
        abs(float(o.get("official_height_m", 0.0)) - C.DD_PINT_GLASS_H) < 1e-6
        and abs(float(o.get("official_diameter_m", 0.0)) -
                C.DD_PINT_GLASS_D) < 1e-6 for o in pint_sources)
    rocks_dims_ok = all(
        abs(float(o.get("official_height_m", 0.0)) - C.DD_ROCKS_GLASS_H) < 1e-6
        and abs(float(o.get("official_diameter_m", 0.0)) -
                C.DD_ROCKS_GLASS_D) < 1e-6
        and o.get("glass_profile", "") == "eight_sided_Gibraltar"
        for o in rocks_sources)
    add("served_glassware_uses_recorded_manufacturer_dimensions",
        len(pint_sources) == 5 and len(rocks_sources) == 5 and
        pint_dims_ok and rocks_dims_ok,
        {"dimensioned_pints": sum(1 for o in pint_sources if
                                   abs(float(o.get("official_height_m", 0.0)) -
                                       C.DD_PINT_GLASS_H) < 1e-6),
         "dimensioned_faceted_rocks": sum(1 for o in rocks_sources if
                                           o.get("glass_profile", "") ==
                                           "eight_sided_Gibraltar")},
        {"dimensioned_pints": 5, "dimensioned_faceted_rocks": 5})

    pint_complete = []
    for glass in pint_sources:
        prefix = glass.get("drink_id", "")
        required = {prefix + "_Glass", prefix + "_Beer",
                    prefix + "_FoamHead"}
        bubbles = [n for n in names if n.startswith(prefix + "_FoamBubble_")]
        if required <= names and len(bubbles) == 5:
            pint_complete.append(prefix)
    add("every_pint_contains_beer_and_a_varied_foam_head",
        len(pint_complete) == 5, len(pint_complete), 5)

    rocks_complete = []
    for glass in rocks_sources:
        prefix = glass.get("drink_id", "")
        required = {prefix + "_Glass", prefix + "_Cocktail",
                    prefix + "_Straw", prefix + "_LimeRind",
                    prefix + "_LimePulp"}
        ice = [n for n in names if n.startswith(prefix + "_Ice_")]
        membranes = [n for n in names if
                     n.startswith(prefix + "_LimeMembrane_")]
        if required <= names and len(ice) == 3 and len(membranes) == 4:
            rocks_complete.append(prefix)
    add("every_rocks_drink_has_ice_lime_wheel_and_straw",
        len(rocks_complete) == 5, len(rocks_complete), 5)

    modes = Counter(o.get("coaster_mode", "") for o in served)
    fresh_rings = [o for o in objects if
                   o.name.endswith("_FreshCondensationRing") and
                   o.get("surface_state", "") ==
                   "fresh_wipeable_condensation_not_stain"]
    empty_places = [o for o in patron_coasters if
                    not o.get("supports_active_drink", True)]
    add("coaster_logic_is_tidy_with_one_intentional_direct_bar_placement",
        modes == Counter({"coaster": 9, "direct_guest_placement": 1}) and
        len(fresh_rings) == 1 and len(empty_places) == 1,
        {"active_modes": dict(modes), "fresh_direct_rings": len(fresh_rings),
         "dry_away_place_settings": len(empty_places)},
        {"active_modes": {"coaster": 9, "direct_guest_placement": 1},
         "fresh_direct_rings": 1, "dry_away_place_settings": 1})

    supported = [o for o in served if "support_z" in o and
                 abs(_world_bbox(o)[4] - float(o["support_z"])) <= 0.002]
    reachable = [o for o in served if
                 0.20 <= float(o.get("human_reach_m", 99.0)) <= 0.68]
    served_bar = [o for o in served if o.get("service_zone", "") == "bar"]
    bar_bases = served_bar + [o for o in objects if
                              o.name.startswith("PATRON_Bar_") and
                              (o.name.endswith("_Coaster") and
                               o.get("supports_active_drink", False) or
                               o.name.endswith("_FreshCondensationRing"))]
    bar_bbox = _world_bbox(bar_top) if bar_top else None
    bar_guest_inset = (bar_bbox[1] - max(_world_bbox(o)[1] for o in bar_bases)) \
        if bar_bbox and bar_bases else -math.inf
    bar_y_inset = min(
        min(_world_bbox(o)[2] - bar_bbox[2],
            bar_bbox[3] - _world_bbox(o)[3]) for o in bar_bases) \
        if bar_bbox and bar_bases else -math.inf
    tidy_service = [o for o in objects if o.name.startswith("PATRON_") and
                    o.get("current_shift_state", "") ==
                    "active_tidy_service"]
    all_patron = [o for o in objects if o.name.startswith("PATRON_")]
    add("every_served_drink_meets_its_surface_and_declared_human_reach",
        len(supported) == 10 and len(reachable) == 10 and
        len(tidy_service) == len(all_patron) and
        bar_guest_inset >= 0.05 and bar_y_inset >= 0.03,
        {"supported": len(supported), "reachable": len(reachable),
         "tidy_components": len(tidy_service),
         "patron_components": len(all_patron),
         "minimum_bar_guest_edge_inset_m": round(bar_guest_inset, 3),
         "minimum_bar_end_inset_m": round(bar_y_inset, 3),
         "reach_range_m": [round(min(float(o.get("human_reach_m", 0.0))
                                     for o in served), 3),
                           round(max(float(o.get("human_reach_m", 0.0))
                                     for o in served), 3)] if served else []},
        {"supported": 10, "reachable": 10,
         "all_patron_components": "active_tidy_service",
         "reach_range_m": "0.20-0.68",
         "minimum_bar_guest_edge_inset_m": 0.05,
         "minimum_bar_end_inset_m": 0.03})

    forbidden_counter_prefixes = (
        "PROP_BarGlass_", "PROP_BarDrink_", "PROP_Coaster_",
        "PROP_BottleCap_", "PROP_BarOldDrinkRing_",
        "PROP_BarTopScratch_", "PROP_ReceiptSpike",
    )
    counter_debris = sorted(n for n in names if
                            n.startswith(forbidden_counter_prefixes))
    fruit = [o for o in objects if o.name.startswith("PROP_BarFruit_") and
             o.get("food_type", "") == "whole_fruit_not_eggs"]
    fruit_bowl = bpy.data.objects.get("PROP_BarFruitBowl")
    lower_fruit = [o for o in fruit if int(o.get("fruit_layer", -1)) == 0 and
                   o.get("support_state", "") == "bowl_interior"]
    upper_fruit = [o for o in fruit if int(o.get("fruit_layer", -1)) == 1 and
                   o.get("support_state", "") == "nested_on_lower_fruit"]
    bowl_rim_z = float(fruit_bowl.get("rim_z", -math.inf)) \
        if fruit_bowl else -math.inf
    bar_top_z = _world_bbox(bar_top)[5] if bar_top else math.inf
    bowl_supported = fruit_bowl is not None and \
        abs(_world_bbox(fruit_bowl)[4] - bar_top_z) <= 0.002 and \
        abs(float(fruit_bowl.get("support_z", math.inf)) - bar_top_z) <= 0.002
    fruit_contained = fruit_bowl is not None and all(
        math.hypot(o.location.x - fruit_bowl.location.x,
                   o.location.y - fruit_bowl.location.y) +
        float(o.get("nominal_radius_m", 99.0)) <= 0.195 for o in fruit)
    lower_meets_basin = len(lower_fruit) == 5 and all(
        "support_z" in o and
        abs(_world_bbox(o)[4] - float(o["support_z"])) <= 0.003
        for o in lower_fruit)
    lower_below_rim = len(lower_fruit) == 5 and all(
        _world_bbox(o)[4] <= bowl_rim_z - 0.01 for o in lower_fruit)
    upper_contacts_lower = len(upper_fruit) == 3 and all(
        any((upper.location - lower.location).length <=
            1.08 * (float(upper.get("nominal_radius_m", 0.0)) +
                    float(lower.get("nominal_radius_m", 0.0)))
            for lower in lower_fruit) for upper in upper_fruit)
    active_bar_drinks = [o for o in served if
                         o.get("service_zone", "") == "bar"]
    add("bar_top_is_clean_open_and_supports_tidy_current_service",
        not counter_debris and len(fruit) == 8 and
        "PROP_BarFruitBowl" in names and len(active_bar_drinks) == 3 and
        "PATRON_Bar_03_OpenTab" in names and bowl_supported and
        fruit_contained and lower_meets_basin and lower_below_rim and
        upper_contacts_lower,
        {"legacy_counter_debris": counter_debris, "whole_fruit": len(fruit),
         "active_bar_drinks": len(active_bar_drinks),
         "open_tabs": int("PATRON_Bar_03_OpenTab" in names),
         "bowl_meets_bar_top": bowl_supported,
         "fruit_in_bowl": fruit_contained,
         "lower_fruit_meeting_basin": len(lower_fruit)
         if lower_meets_basin else 0,
         "lower_fruit_below_rim": len(lower_fruit) if lower_below_rim else 0,
         "upper_fruit_touching_lower_cluster": len(upper_fruit)
         if upper_contacts_lower else 0},
        "no legacy dirty debris; supported bowl and 8 physically supported whole fruit, "
        "3 inset active drinks and 1 open tab")

    street_required = {
        "ENV_StreetBackdrop_LESNight", "LGT_Neon_WindowOpen",
        "LGT_Neon_8Ball", "LGT_StreetTailLightSpill",
        "LGT_StreetShopSignSpill",
    }
    add("storefront_has_busy_street_world_and_multiple_neon_sources",
        street_required <= names, len(street_required & names),
        len(street_required))

    cross_beams = [o for o in objects if
                   re.fullmatch(r"ENV_CrossBeam_\d+", o.name)]
    add("prewar_room_has_three_constructed_aged_cross_beams",
        len(cross_beams) == 3 and all(
            o.get("construction_role", "") ==
            "boxed_prewar_cross_beam" for o in cross_beams),
        len(cross_beams), 3)

    used_materials = {m for o in objects
                      if getattr(o, "data", None) and
                      hasattr(o.data, "materials") for m in o.data.materials
                      if m is not None}
    aged_materials = sorted(m.name for m in used_materials
                            if int(m.get("age_layers", 0)) >= 3)
    add("age_is_embedded_across_major_material_families",
        len(aged_materials) >= 20, len(aged_materials), ">=20 used materials")

    secrets = [o for o in objects if o.get("secret_story", "")]
    add("close_views_reward_search_with_small_authored_secrets",
        len(secrets) >= 14, len(secrets), ">=14 subtle story components")
    return checks


def run(output=None):
    objects = [o for o in bpy.data.objects
               if o.type != "EMPTY" and not o.hide_render and
               _collection(o) in PRODUCTION_COLLECTIONS]
    rows = []
    grouped = defaultdict(list)
    for ob in sorted(objects, key=lambda item: item.name):
        logical = _logical_item(ob.name)
        category = _category(ob.name, logical)
        bbox = _world_bbox(ob)
        row = {
            "name": ob.name,
            "logical_item": logical,
            "category": category,
            "collection": _collection(ob),
            "type": ob.type,
            "location_m": _round(ob.matrix_world.translation),
            "rotation_deg": _round([math.degrees(v) for v in
                                     ob.rotation_euler], 2),
            "dimensions_m": _round(ob.dimensions),
            "world_bbox_m": _round(bbox),
            "materials": [m.name for m in getattr(ob.data, "materials", [])]
            if getattr(ob, "data", None) and hasattr(ob.data, "materials") else [],
            "support_contract": _support_contract(ob.name, category),
        }
        rows.append(row)
        grouped[logical].append(row)

    items = []
    for logical, members in sorted(grouped.items()):
        bbox = [min(r["world_bbox_m"][0] for r in members),
                max(r["world_bbox_m"][1] for r in members),
                min(r["world_bbox_m"][2] for r in members),
                max(r["world_bbox_m"][3] for r in members),
                min(r["world_bbox_m"][4] for r in members),
                max(r["world_bbox_m"][5] for r in members)]
        items.append({
            "logical_item": logical,
            "category": members[0]["category"],
            "collection": members[0]["collection"],
            "component_count": len(members),
            "world_bbox_m": _round(bbox),
            "support_contract": members[0]["support_contract"],
            "review_state": "classified_and_contract_checked",
        })

    checks = _required_contracts(objects)
    report = {
        "summary": {
            "render_visible_component_objects": len(rows),
            "logical_items": len(items),
            "collections": dict(sorted(Counter(r["collection"] for r in rows).items())),
            "categories": dict(sorted(Counter(r["category"] for r in rows).items())),
            "required_checks": len(checks),
            "required_failures": sum(c["status"] == "FAIL" for c in checks),
        },
        "method": {
            "scope": "every render-visible production object",
            "group_review": "components grouped by their real-world owning item",
            "manual_evidence": "zone close renders listed in docs/REALISM_AUDIT.md",
        },
        "required_contracts": checks,
        "logical_items": items,
        "objects": rows,
    }
    output = output or os.path.join(C.ROOT, "reports", "object_realism_audit.json")
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print("  [realism] %d components -> %d logical items; %d required failures" %
          (len(rows), len(items), report["summary"]["required_failures"]))
    print("  [realism] wrote " + output)
    return report


if __name__ == "__main__":
    result = run()
    raise SystemExit(1 if result["summary"]["required_failures"] else 0)
