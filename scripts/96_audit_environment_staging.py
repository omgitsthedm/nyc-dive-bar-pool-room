"""96_audit_environment_staging.py — exhaustive pre-physics staging gate.

The realism inventory classifies every visible component. This gate adds the
room-wide placement questions that can still hide behind a correct object
count: is geometry valid, is it inside the authored shell, does loose furniture
meet the floor, do guest objects fit on their tables, do wall objects reach a
real wall plane, and does each high-risk logical item have explicit support
evidence? Pool geometry is inventoried here only as a staged obstacle; cushion,
pocket and rigid-body correctness remain the next phase.
"""
import bpy
import importlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402

R = importlib.import_module("95_audit_realism")

REPORT = os.path.join(C.ROOT, "reports", "environment_staging_audit.json")
HIGH_RISK_CATEGORIES = {
    "bottle_stock", "door_hardware", "fixed_seating", "movable_seating",
    "patron_service", "patron_table", "wall_or_table_prop",
}


def _round(values, places=5):
    if isinstance(values, (float, int)):
        return round(float(values), places)
    return [round(float(v), places) for v in values]


def _bbox(ob):
    return R._world_bbox(ob)


def _group_bbox(members):
    boxes = [_bbox(ob) for ob in members]
    return [min(b[0] for b in boxes), max(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes),
            min(b[4] for b in boxes), max(b[5] for b in boxes)]


def _finite(ob):
    values = [v for row in ob.matrix_world for v in row]
    values.extend(ob.dimensions)
    return all(math.isfinite(float(v)) for v in values)


def _has_render_geometry(ob):
    if ob.type == "MESH":
        return len(ob.data.vertices) > 0 and len(ob.data.polygons) > 0
    if ob.type == "CURVE":
        return len(ob.data.splines) > 0
    if ob.type == "FONT":
        return bool(ob.data.body)
    return ob.type == "LIGHT"


def _has_material(ob):
    if ob.type not in {"MESH", "CURVE", "FONT"}:
        return True
    return any(slot.material is not None for slot in ob.material_slots)


def _inside_scene_envelope(ob):
    b = _bbox(ob)
    # Includes 100 mm floor slab, the exterior street card and small practical
    # spill offsets while remaining tight enough to catch a misplaced asset.
    return (b[0] >= -C.ROOM_W / 2.0 - 0.30 and
            b[1] <= C.ROOM_W / 2.0 + 0.30 and
            b[2] >= -C.ROOM_L / 2.0 - 0.65 and
            b[3] <= C.ROOM_L / 2.0 + 0.30 and
            b[4] >= -0.16 and b[5] <= C.ROOM_H + 0.22)


def _wall_gap(b):
    hw, hl = C.ROOM_W / 2.0, C.ROOM_L / 2.0
    return min(abs(b[0] + hw), abs(b[1] - hw),
               abs(b[2] + hl), abs(b[3] - hl))


def _xy_inside(inner, outer, margin=0.0):
    return (inner[0] >= outer[0] - margin and
            inner[1] <= outer[1] + margin and
            inner[2] >= outer[2] - margin and
            inner[3] <= outer[3] + margin)


def _xy_center_inside(inner, outer, margin=0.0):
    x = (inner[0] + inner[1]) / 2.0
    y = (inner[2] + inner[3]) / 2.0
    return (outer[0] - margin <= x <= outer[1] + margin and
            outer[2] - margin <= y <= outer[3] + margin)


def _bbox_overlap(a, b, margin=0.0):
    return not (a[1] < b[0] - margin or a[0] > b[1] + margin or
                a[3] < b[2] - margin or a[2] > b[3] + margin or
                a[5] < b[4] - margin or a[4] > b[5] + margin)


def _surface_for_guest(logical):
    if logical.startswith("PATRON_Bar_"):
        return bpy.data.objects.get("BAR_Top")
    match = re.match(r"PATRON_Booth(\d+)_", logical)
    if match:
        return bpy.data.objects.get("PROP_Booth_%s_TableTop" % match.group(1))
    match = re.match(r"PATRON_Cafe(\d+)_", logical)
    if match:
        return bpy.data.objects.get("PROP_CafeTable_%s_Top" % match.group(1))
    return None


def _guest_support(logical, members):
    surface = _surface_for_guest(logical)
    if surface is None:
        return False, "missing_guest_surface"
    item, top = _group_bbox(members), _bbox(surface)
    contact = abs(item[4] - top[5]) <= 0.0021
    contained = _xy_inside(item, top, margin=0.002)
    return contact and contained, (
        "guest_surface_contact_and_footprint" if contact and contained else
        "guest_surface_gap_or_overhang")


def _bottle_support(members):
    roots = [ob for ob in members if "support_z" in ob and
             (ob.get("bottle_family", "") or ob.get("stock_bottle", False))]
    if len(roots) != 1:
        return False, "missing_or_ambiguous_bottle_root"
    root = roots[0]
    ok = abs(_bbox(root)[4] - float(root["support_z"])) <= 0.002
    return ok, "recorded_shelf_contact" if ok else "bottle_support_gap"


def _table_top_for_secret(index):
    names = ("PROP_Booth_0_TableTop", "PROP_Booth_1_TableTop",
             "PROP_CafeTable_0_Top", "PROP_CafeTable_1_Top")
    return bpy.data.objects.get(names[index]) if 0 <= index < len(names) else None


def _authored_prop_support(logical, members, all_groups):
    item = _group_bbox(members)
    if _wall_gap(item) <= 0.090:
        return True, "wall_or_casing_contact"

    if logical == "PROP_BarFruitBowl":
        support = bpy.data.objects.get("BAR_Top")
        ok = support is not None and _xy_inside(item, _bbox(support), 0.0) and \
            abs(item[4] - _bbox(support)[5]) <= 0.002
        return ok, "bar_top_contact" if ok else "fruit_bowl_floating"

    fruit_match = re.fullmatch(r"PROP_BarFruit_(\d+)", logical)
    if fruit_match:
        fruit = members[0]
        if int(fruit.get("fruit_layer", -1)) == 0:
            ok = "support_z" in fruit and \
                abs(_bbox(fruit)[4] - float(fruit["support_z"])) <= 0.003
            return ok, "basin_contact" if ok else "lower_fruit_support_gap"
        lowers = [ob for ob in bpy.data.objects
                  if ob.name.startswith("PROP_BarFruit_") and
                  "Stem" not in ob.name and int(ob.get("fruit_layer", -1)) == 0]
        radius = float(fruit.get("nominal_radius_m", 0.0))
        ok = any((fruit.location - lower.location).length <= 1.08 *
                 (radius + float(lower.get("nominal_radius_m", 0.0)))
                 for lower in lowers)
        return ok, "nested_fruit_contact" if ok else "upper_fruit_floating"

    stem_match = re.fullmatch(r"PROP_BarFruitStem_(\d+)", logical)
    if stem_match:
        fruit = bpy.data.objects.get("PROP_BarFruit_%s" % stem_match.group(1))
        ok = fruit is not None and _bbox_overlap(item, _bbox(fruit), 0.006)
        return ok, "stem_engages_fruit" if ok else "detached_fruit_stem"

    if logical == "PROP_NapkinHolder":
        support = bpy.data.objects.get("BAR_Top")
        ok = support is not None and abs(item[4] - _bbox(support)[5]) <= 0.002
        return ok, "bar_top_contact" if ok else "napkin_holder_support_gap"
    napkin_match = re.fullmatch(r"PROP_Napkin_(\d+)", logical)
    if napkin_match:
        index = int(napkin_match.group(1))
        below = bpy.data.objects.get("PROP_NapkinHolder" if index == 0 else
                                     "PROP_Napkin_%d" % (index - 1))
        ok = below is not None and _xy_center_inside(item, _bbox(below), 0.010) \
            and item[4] <= _bbox(below)[5] + 0.004
        return ok, "napkin_stack_contact" if ok else "detached_napkin"

    if logical == "PROP_TipJar":
        support = bpy.data.objects.get("BAR_Top")
        ok = support is not None and abs(item[4] - _bbox(support)[5]) <= 0.002
        return ok, "bar_top_contact" if ok else "tip_jar_support_gap"
    if logical.startswith("PROP_TipJar_Bill_"):
        jar = bpy.data.objects.get("PROP_TipJar")
        ok = jar is not None and _xy_inside(item, _bbox(jar), 0.0) and \
            item[4] >= _bbox(jar)[4] and item[5] <= _bbox(jar)[5]
        return ok, "contained_in_tip_jar" if ok else "bill_outside_tip_jar"

    if logical.startswith("PROP_ChalkCube_"):
        shelf = bpy.data.objects.get("PROP_ChalkShelf")
        ok = shelf is not None and _xy_inside(item, _bbox(shelf), 0.0) and \
            abs(item[4] - _bbox(shelf)[5]) <= 0.002
        return ok, "chalk_shelf_contact" if ok else "chalk_support_gap"
    if logical == "PROP_ChalkShelf":
        ok = _wall_gap(item) <= 0.18
        return ok, "rear_wall_shelf_fastened" if ok else "chalk_shelf_detached"

    edge_match = re.fullmatch(r"PROP_FurnitureEdgeWear_(\d+)", logical)
    if edge_match:
        owners = ("PROP_CafeChair_0_Wood", "PROP_CafeChair_0_Metal",
                  "PROP_CafeChair_1_Folding", "PROP_CafeChair_1_Wood")
        owner = all_groups.get(owners[int(edge_match.group(1))], [])
        ok = bool(owner) and _bbox_overlap(item, _group_bbox(owner), 0.012)
        return ok, "chair_finish_engagement" if ok else "detached_chair_wear"

    initial_match = re.match(r"PROP_Secret_TableInitial_(\d+)_", logical)
    if initial_match:
        top = _table_top_for_secret(int(initial_match.group(1)))
        ok = top is not None and _xy_inside(item, _bbox(top), 0.0) and \
            abs(item[4] - _bbox(top)[5]) <= 0.005
        return ok, "table_finish_engagement" if ok else "detached_table_initial"

    if logical.startswith("PROP_Secret_BeamPoolTally_"):
        beams = [ob for ob in bpy.data.objects
                 if re.fullmatch(r"ENV_CrossBeam_\d+", ob.name)]
        ok = any(_bbox_overlap(item, _bbox(beam), 0.015) for beam in beams)
        return ok, "beam_underside_contact" if ok else "detached_beam_tally"

    # Coat hooks, coats, wall notices, wheatpaste, the old casing key and the
    # removed-sign ghost are allowed to project farther than flat posters but
    # must still remain within 100 mm of the wall/casing they belong to.
    if logical.startswith(("PROP_CoatHook_", "PROP_HangingCoat_",
                           "PROP_WallNotice_", "PROP_Wheatpaste_",
                           "PROP_Secret_OldKey", "PROP_Secret_RemovedSign")):
        ok = _wall_gap(item) <= 0.100
        return ok, "wall_or_casing_contact" if ok else "detached_wall_prop"

    return False, "no_named_support_evidence"


def _staging_evidence(logical, members, category, contract, all_groups):
    item = _group_bbox(members)
    if contract == "floor_contact":
        ok = abs(item[4]) <= 0.0021
        return ok, "floor_contact" if ok else "floor_gap"
    if contract == "guest_surface_contact_and_seat_reach":
        return _guest_support(logical, members)
    if contract == "shelf_or_speed_rail_contact":
        return _bottle_support(members)
    if contract == "wall_fastened":
        ok = _wall_gap(item) <= 0.055
        return ok, "wall_plane_contact" if ok else "wall_mount_gap"
    if contract == "rack_retained":
        rack = all_groups.get("PROP_CueRack", [])
        ok = bool(rack) and _bbox_overlap(item, _group_bbox(rack), 0.006)
        return ok, "cue_rack_engagement" if ok else "cue_outside_rack"
    if contract == "door_or_frame_fastened":
        ok = abs(item[4]) <= 0.0021 and _wall_gap(item) <= 0.10
        return ok, "opening_plane_and_floor_contact" if ok else \
            "door_opening_or_floor_gap"
    if contract == "visible_fixture_or_documented_opening":
        lights = [ob for ob in members if ob.type == "LIGHT"]
        ok = all(ob.get("motivation", "") for ob in lights)
        return ok, "motivated_light_or_visible_fixture_geometry" if ok else \
            "unmotivated_light"
    if contract == "authored_surface_contact":
        return _authored_prop_support(logical, members, all_groups)
    if contract in {"bar_assembly_contact", "building_assembly",
                    "pool_table_assembly", "assembly_owned"}:
        return True, "deterministic_owned_assembly"
    return False, "unknown_support_contract"


def _add(checks, name, passed, measured, expected):
    checks.append({"check": name, "status": "PASS" if passed else "FAIL",
                   "measured": measured, "expected": expected,
                   "required": True})


def run(output=None):
    objects = [ob for ob in bpy.data.objects if ob.type != "EMPTY" and
               not ob.hide_render and R._collection(ob) in R.PRODUCTION_COLLECTIONS]
    groups = defaultdict(list)
    for ob in objects:
        groups[R._logical_item(ob.name)].append(ob)

    invalid = sorted(ob.name for ob in objects
                     if not _finite(ob) or not _has_render_geometry(ob))
    unmaterialed = sorted(ob.name for ob in objects if not _has_material(ob))
    outside = sorted(ob.name for ob in objects if not _inside_scene_envelope(ob))

    rows = []
    for logical, members in sorted(groups.items()):
        category = R._category(members[0].name, logical)
        contract = R._support_contract(members[0].name, category)
        passed, evidence = _staging_evidence(
            logical, members, category, contract, groups)
        rows.append({
            "logical_item": logical,
            "category": category,
            "component_count": len(members),
            "support_contract": contract,
            "staging_status": "PASS" if passed else "FAIL",
            "support_evidence": evidence,
            "world_bbox_m": _round(_group_bbox(members)),
        })

    high_risk = [row for row in rows if row["category"] in HIGH_RISK_CATEGORIES]
    high_risk_failures = [row for row in high_risk
                          if row["staging_status"] == "FAIL"]

    guest_rows = [row for row in rows if row["category"] == "patron_service"]
    guest_collisions = []
    for index, first in enumerate(guest_rows):
        a = first["world_bbox_m"]
        for second in guest_rows[index + 1:]:
            b = second["world_bbox_m"]
            xy_overlap = min(a[1], b[1]) - max(a[0], b[0]) > 0.001 and \
                min(a[3], b[3]) - max(a[2], b[2]) > 0.001
            z_overlap = min(a[5], b[5]) - max(a[4], b[4]) > 0.0002
            if xy_overlap and z_overlap:
                guest_collisions.append([first["logical_item"],
                                         second["logical_item"]])

    furniture_roots = [ob for ob in objects if re.fullmatch(
        r"(?:BAR_Stool_Seat_\d+|PROP_CafeChair_\d+_(?:Wood|Metal|Folding)_Seat)",
        ob.name)]
    signatures = defaultdict(list)
    for ob in furniture_roots:
        signature = tuple(round(float(v), 5)
                          for row in ob.matrix_world for v in row)
        signatures[signature].append(ob.name)
    duplicate_furniture = sorted(names for names in signatures.values()
                                 if len(names) > 1)

    stock_roots = [ob for ob in objects if ob.get("bottle_family", "")]
    shelf_surfaces = [ob for ob in objects if
                      re.fullmatch(r"BAR_BackShelf_\d+(?:_[NS])?", ob.name)]
    speed_rail = bpy.data.objects.get("BAR_SpeedRail_Bottom")
    bottle_footprints = []
    bottle_footprint_failures = []
    for root in stock_roots:
        candidates = shelf_surfaces if root.get("stock_bottle", False) else \
            ([speed_rail] if speed_rail is not None else [])
        fitted = any(abs(_bbox(surface)[5] - float(root["support_z"])) <= 0.002
                     and _xy_inside(_bbox(root), _bbox(surface), 0.002)
                     for surface in candidates)
        if fitted:
            bottle_footprints.append(root.name)
        else:
            bottle_footprint_failures.append(root.name)
    minimum_bottle_clearance = math.inf
    bottle_overlaps = []
    for index, first in enumerate(stock_roots):
        for second in stock_roots[index + 1:]:
            if abs(float(first["support_z"]) -
                   float(second["support_z"])) > 0.003:
                continue
            distance = math.hypot(first.location.x - second.location.x,
                                  first.location.y - second.location.y)
            clearance = distance - (float(first["nominal_radius_m"]) +
                                    float(second["nominal_radius_m"]))
            minimum_bottle_clearance = min(minimum_bottle_clearance,
                                           clearance)
            if clearance < -0.001:
                bottle_overlaps.append([first.name, second.name,
                                        round(clearance, 5)])
    upper_stock_names = ("BAR_Junk_RadioBody", "BAR_Junk_TrophyBase",
                         "BAR_Junk_CoffeeTin", "BAR_Junk_PickleJar")
    upper_stock = [bpy.data.objects.get(name) for name in upper_stock_names]
    upper_stock_ok = [ob for ob in upper_stock if ob is not None and
                      "support_z" in ob and
                      abs(_bbox(ob)[4] - float(ob["support_z"])) <= 0.002]

    lights = [ob for ob in objects if ob.type == "LIGHT"]
    motivated = [ob for ob in lights if ob.get("motivation", "")]
    rigid_bodies = [ob.name for ob in bpy.data.objects if ob.rigid_body]

    checks = []
    _add(checks, "every_visible_component_has_finite_render_geometry",
         not invalid, invalid, [])
    _add(checks, "every_visible_mesh_or_curve_has_a_material",
         not unmaterialed, unmaterialed, [])
    _add(checks, "every_visible_component_stays_inside_authored_scene_envelope",
         not outside, outside, [])
    _add(checks, "every_logical_item_is_classified_and_support_routed",
         all(row["category"] != "other" and row["support_contract"]
             for row in rows), len(rows), len(rows))
    _add(checks, "every_high_risk_logical_item_has_physical_staging_evidence",
         not high_risk_failures,
         {"passed": len(high_risk) - len(high_risk_failures),
          "total": len(high_risk),
          "failures": [row["logical_item"] for row in high_risk_failures]},
         {"passed": len(high_risk), "total": len(high_risk), "failures": []})
    _add(checks, "all_patron_footprints_are_supported_and_contained",
         all(row["staging_status"] == "PASS" for row in guest_rows),
         sum(row["staging_status"] == "PASS" for row in guest_rows),
         len(guest_rows))
    _add(checks, "separate_patron_footprints_do_not_interpenetrate",
         not guest_collisions, guest_collisions, [])
    _add(checks, "loose_furniture_has_no_exact_duplicate_transform",
         not duplicate_furniture, duplicate_furniture, [])
    _add(checks, "every_stock_bottle_root_meets_recorded_support",
         len(stock_roots) >= 200 and all(
             "support_z" in ob and
             abs(_bbox(ob)[4] - float(ob["support_z"])) <= 0.002
             for ob in stock_roots),
         {"supported": sum(
             "support_z" in ob and
             abs(_bbox(ob)[4] - float(ob["support_z"])) <= 0.002
             for ob in stock_roots),
          "total": len(stock_roots)},
         {"supported": "all", "total": ">=200"})
    _add(checks, "every_bottle_footprint_fits_its_shelf_or_speed_rail",
         len(bottle_footprints) == len(stock_roots),
         {"fitted": len(bottle_footprints),
          "total": len(stock_roots),
          "failures": bottle_footprint_failures},
         {"fitted": len(stock_roots), "total": len(stock_roots),
          "failures": []})
    _add(checks, "separate_bottle_roots_do_not_interpenetrate",
         not bottle_overlaps,
         {"minimum_clearance_m": round(minimum_bottle_clearance, 5),
          "overlaps": bottle_overlaps},
         {"minimum_clearance_m": ">=-0.001", "overlaps": []})
    _add(checks, "upper_backbar_junk_has_a_real_display_ledge",
         len(upper_stock_ok) == len(upper_stock_names),
         [ob.name for ob in upper_stock_ok], list(upper_stock_names))
    _add(checks, "every_blender_light_has_authored_motivation",
         len(motivated) == len(lights), len(motivated), len(lights))
    _add(checks, "pre_physics_master_contains_no_rigid_bodies",
         not rigid_bodies, rigid_bodies, [])

    report = {
        "summary": {
            "render_visible_components": len(objects),
            "logical_items": len(rows),
            "high_risk_logical_items": len(high_risk),
            "required_checks": len(checks),
            "required_failures": sum(check["status"] == "FAIL"
                                     for check in checks),
            "high_risk_item_failures": len(high_risk_failures),
            "evidence_types": dict(sorted(Counter(
                row["support_evidence"] for row in rows).items())),
        },
        "scope": {
            "machine_review": "every render-visible production component and logical item",
            "high_risk_review": sorted(HIGH_RISK_CATEGORIES),
            "pool_phase_boundary": "pool objects classified as staged obstacles; cushion, pocket and rigid-body physics deferred",
            "scene_envelope_m": {
                "x": _round([-C.ROOM_W / 2.0 - 0.30,
                             C.ROOM_W / 2.0 + 0.30]),
                "y": _round([-C.ROOM_L / 2.0 - 0.65,
                             C.ROOM_L / 2.0 + 0.30]),
                "z": [-0.16, round(C.ROOM_H + 0.22, 5)],
            },
        },
        "required_contracts": checks,
        "logical_items": rows,
    }
    output = output or REPORT
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print("  [staging] %d components -> %d logical items; %d high-risk; %d required failures" %
          (len(objects), len(rows), len(high_risk),
           report["summary"]["required_failures"]))
    print("  [staging] wrote " + output)
    return report


if __name__ == "__main__":
    result = run()
    raise SystemExit(1 if result["summary"]["required_failures"] else 0)
