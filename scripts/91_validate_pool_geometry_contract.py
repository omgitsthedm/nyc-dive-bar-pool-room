"""Pure-Python acceptance test for the shared pool geometry contract.

Pocket mouths have three related measurements: the span of the raw
transition-fillet endpoints, the evaluated theoretical sharp-line mouth before
those fillets, and the nominal target for the finished cushion facings.  The
raw span remains physically distinct, while the evaluated mouth is deliberately
locked to the WPA-range midpoint used as the finished-facing target.

Run without arguments for a read-only check.  Pass ``--write`` to also write
the deterministic report to ``reports/pool_geometry_contract_audit.json``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import pool_geometry_contract as geometry  # noqa: E402


REPORT_PATH = os.path.join(
    ROOT, "reports", "pool_geometry_contract_audit.json")
SOURCE_RELATIVE_PATH = "assets/data/table_wpa_geometry.json"
SCHEMA_VERSION = 3

# This is an acceptance fingerprint, not merely informational metadata.  A
# deliberate source re-export must be reviewed and then update this value.
EXPECTED_SOURCE_SHA256 = (
    "afe868b3788218f0ba29dbe9d5caee81157c088b2b7fbbb00ed5f2faf89f04ad"
)

EXPECTED_PLAYFIELD_M = {"width": 1.270, "length": 2.540}
EXPECTED_BED_HEIGHT_M = 0.762
EXPECTED_BALL_RADIUS_M = 0.028575
EXPECTED_NOSE_HEIGHT_M = 0.03629025
EXPECTED_COUNTS = {
    "pockets": 6,
    "linears": 18,
    "arcs": 12,
    "main_linears": 6,
    "jaw_linears": 12,
}

# Raw spans between the jaw endpoints where the transition fillets begin.
# Preserve the current export's per-pocket values rather than hiding its
# sub-femtometre mirror-pair differences behind one kind-level constant.
EXPECTED_RAW_FILLET_ENDPOINT_SPAN_M = {
    "corner_NE": 0.11412925113180429,
    "corner_NW": 0.11412925113180421,
    "corner_SE": 0.11412925113180429,
    "corner_SW": 0.11412925113180421,
    "side_E": 0.1256162802144467,
    "side_W": 0.1256162802144467,
}

# The evaluated sharp-line mouths are intentionally set at the midpoints of
# the current WPA permitted ranges.  No separate under-minimum side-pocket
# allowance is accepted here.
EVALUATED_SHARP_MOUTH_TARGET_M = {
    "corner": 0.1158875,
    "side": 0.1285875,
}

# Midpoints of the WPA permitted finished-facing ranges.
FINISHED_FACING_NOMINAL_MOUTH_M = {
    "corner": 0.1158875,
    "side": 0.1285875,
}

EXPECTED_CUT_ANGLE_DEG = {"corner": 142.0, "side": 104.0}
LENGTH_TOLERANCE_M = 1e-9
ANGLE_TOLERANCE_DEG = 0.01
MOUTH_TOLERANCE_M = 1e-9
EXPECTED_SHELF_M = {"corner": 1.625 * 0.0254,
                    "side": 0.1875 * 0.0254}


def _close(actual, expected, tolerance):
    return abs(float(actual) - float(expected)) <= tolerance


def _check(checks, name, actual, expected, passed, **metadata):
    row = {
        "check": name,
        "actual": actual,
        "expected": expected,
        "status": "PASS" if passed else "FAIL",
    }
    row.update(metadata)
    checks.append(row)
    return passed


def _check_close(checks, name, actual, expected, tolerance, unit):
    return _check(
        checks,
        name,
        actual,
        expected,
        _close(actual, expected, tolerance),
        tolerance=tolerance,
        unit=unit,
    )


def _jaw_cut_angle_deg(jaw, pocket_kind):
    """Return the included facing angle against the adjacent main rail.

    Corner jaws use the nearer of the two perpendicular rail axes.  Side
    pockets interrupt a long rail, so their adjacent main-rail axis is the
    playfield Y axis.  This distinction turns the approximately 14-degree
    side-jaw heading into the intended approximately 104-degree included cut,
    rather than the unrelated 166-degree supplement against the X axis.
    """
    tangent = jaw["tangent"]
    if pocket_kind == "side":
        axis_alignment = abs(tangent[1])
    else:
        axis_alignment = max(abs(tangent[0]), abs(tangent[1]))
    axis_alignment = min(1.0, max(0.0, axis_alignment))
    acute = math.degrees(math.acos(axis_alignment))
    return 180.0 - acute


def _raw_fillet_endpoint_span_m(lines, arcs, pocket):
    """Measure between the two jaw-side transition-fillet endpoints."""
    jaws = [
        row for row in lines
        if row["kind"] == "jaw" and
        row["pocket"]["id"] == pocket["id"]
    ]
    arcs_by_jaw = {row["jaw_id"]: row for row in arcs}
    if len(jaws) != 2 or any(row["id"] not in arcs_by_jaw for row in jaws):
        raise ValueError(
            "pocket %s does not own two fillet endpoints" % pocket["id"])
    endpoints = [arcs_by_jaw[row["id"]]["path"][-1] for row in jaws]
    return geometry.distance(endpoints[0], endpoints[1])


def build_report():
    data = geometry.load()
    source_sha256 = geometry.file_sha256()
    source_path = os.path.relpath(
        os.path.realpath(geometry.DATA_PATH), os.path.realpath(ROOT))
    lines = geometry.linear_rows(data)
    arcs = geometry.arc_rows(data)
    pockets = geometry.pocket_rows(data)
    metrics = geometry.pocket_metrics(data)
    checks = []

    _check(
        checks,
        "source_path",
        source_path,
        SOURCE_RELATIVE_PATH,
        source_path == SOURCE_RELATIVE_PATH,
    )
    _check(
        checks,
        "source_sha256",
        source_sha256,
        EXPECTED_SOURCE_SHA256,
        source_sha256 == EXPECTED_SOURCE_SHA256,
    )

    source_counts = {
        "pockets": len(pockets),
        "linears": len(lines),
        "arcs": len(arcs),
        "main_linears": sum(row["kind"] == "main" for row in lines),
        "jaw_linears": sum(row["kind"] == "jaw" for row in lines),
    }
    for name in sorted(EXPECTED_COUNTS):
        _check(
            checks,
            "source_count_" + name,
            source_counts[name],
            EXPECTED_COUNTS[name],
            source_counts[name] == EXPECTED_COUNTS[name],
            unit="count",
        )

    _check_close(
        checks, "playfield_width", float(data["w"]),
        EXPECTED_PLAYFIELD_M["width"], LENGTH_TOLERANCE_M, "m")
    _check_close(
        checks, "playfield_length", float(data["l"]),
        EXPECTED_PLAYFIELD_M["length"], LENGTH_TOLERANCE_M, "m")
    _check_close(
        checks, "bed_height", float(data["bed"]), EXPECTED_BED_HEIGHT_M,
        LENGTH_TOLERANCE_M, "m")
    _check_close(
        checks, "ball_radius", float(data["ball_R"]),
        EXPECTED_BALL_RADIUS_M, LENGTH_TOLERANCE_M, "m")
    _check_close(
        checks, "cushion_nose_height", float(data["nose"]),
        EXPECTED_NOSE_HEIGHT_M, LENGTH_TOLERANCE_M, "m")

    wpa_ranges = {
        kind: [float(value) for value in geometry.WPA_MOUTH_RANGES_M[kind]]
        for kind in ("corner", "side")
    }
    finished_nominal = {
        kind: sum(wpa_ranges[kind]) / 2.0
        for kind in ("corner", "side")
    }
    for kind in ("corner", "side"):
        _check_close(
            checks,
            "finished_facing_nominal_target_" + kind,
            finished_nominal[kind],
            FINISHED_FACING_NOMINAL_MOUTH_M[kind],
            LENGTH_TOLERANCE_M,
            "m",
        )

    mouth_rows = {}
    pockets_by_name = {row["name"]: row for row in pockets}
    for pocket_name in sorted(metrics):
        metric = metrics[pocket_name]
        pocket = pockets_by_name[pocket_name]
        kind = metric["kind"]
        raw_span = _raw_fillet_endpoint_span_m(lines, arcs, pocket)
        theoretical = float(metric["mouth_m"])
        nominal = finished_nominal[kind]
        mouth_rows[pocket_name] = {
            "kind": kind,
            "raw_fillet_endpoint_span_m": raw_span,
            "raw_fillet_endpoint_span_mm": raw_span * 1000.0,
            "evaluated_sharp_line_mouth_m": theoretical,
            "evaluated_sharp_line_mouth_mm": theoretical * 1000.0,
            "finished_facing_nominal_target_m": nominal,
            "finished_facing_nominal_target_mm": nominal * 1000.0,
            "raw_to_evaluated_mm": (theoretical - raw_span) * 1000.0,
            "evaluated_to_finished_nominal_mm": (
                nominal - theoretical) * 1000.0,
        }
        _check_close(
            checks,
            "raw_fillet_endpoint_span_" + pocket_name,
            raw_span,
            EXPECTED_RAW_FILLET_ENDPOINT_SPAN_M[pocket_name],
            LENGTH_TOLERANCE_M,
            "m",
        )
        _check_close(
            checks,
            "evaluated_sharp_line_mouth_" + pocket_name,
            theoretical,
            EVALUATED_SHARP_MOUTH_TARGET_M[kind],
            MOUTH_TOLERANCE_M,
            "m",
        )
        _check(
            checks,
            "raw_and_evaluated_mouth_distinct_" + pocket_name,
            {"raw_m": raw_span, "evaluated_m": theoretical},
            "raw fillet span differs from evaluated sharp-line mouth",
            not _close(raw_span, theoretical, MOUTH_TOLERANCE_M),
            unit="m",
        )
        _check_close(
            checks,
            "evaluated_mouth_matches_finished_nominal_" + pocket_name,
            theoretical,
            nominal,
            MOUTH_TOLERANCE_M,
            unit="m",
        )

    cut_rows = []
    for jaw in sorted(
            (row for row in lines if row["kind"] == "jaw"),
            key=lambda row: int(row["id"])):
        pocket = jaw["pocket"]
        kind = pocket["kind"]
        angle = _jaw_cut_angle_deg(jaw, kind)
        expected = EXPECTED_CUT_ANGLE_DEG[kind]
        cut_rows.append({
            "jaw_id": jaw["id"],
            "pocket": pocket["name"],
            "kind": kind,
            "measured_deg": angle,
            "expected_deg": expected,
        })
        _check_close(
            checks,
            "jaw_%s_%s_cut_angle" % (jaw["id"], pocket["name"]),
            angle,
            expected,
            ANGLE_TOLERANCE_DEG,
            "deg",
        )

    shelf_rows = []
    for pocket in pockets:
        target = EXPECTED_SHELF_M[pocket["kind"]]
        shelf = geometry.pocket_shelf_cut_details(data, pocket, target)
        outline, _centroid, _mouth_edge = geometry.pocket_outline_details(
            data, pocket)
        edge = shelf["shelf_edge"]
        start = shelf["outline"][edge]
        end = shelf["outline"][(edge + 1) % len(shelf["outline"])]
        span = geometry.distance(start, end)
        simple = not geometry._polygon_crossings(shelf["outline"])
        contained = all(geometry._point_in_polygon(point, outline)
                        for point in shelf["outline"])
        shelf_rows.append({
            "pocket": pocket["name"],
            "kind": pocket["kind"],
            "measured_m": shelf["shelf_m"],
            "target_m": target,
            "drop_edge_span_m": span,
            "drop_outline_vertices": len(shelf["outline"]),
            "simple": simple,
            "contained_in_rail_opening": contained,
        })
        _check_close(
            checks, "pocket_shelf_" + pocket["name"],
            shelf["shelf_m"], target, LENGTH_TOLERANCE_M, "m")
        _check(
            checks, "pocket_shelf_drop_admits_ball_" + pocket["name"],
            span, ">= %.9f" % (EXPECTED_BALL_RADIUS_M * 2),
            span >= EXPECTED_BALL_RADIUS_M * 2,
            unit="m",
        )
        _check(
            checks, "pocket_shelf_outline_valid_" + pocket["name"],
            {"simple": simple, "contained": contained},
            {"simple": True, "contained": True},
            simple and contained,
        )

    failed = sum(row["status"] == "FAIL" for row in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "validator": "scripts/91_validate_pool_geometry_contract.py",
        "status": "PASS" if failed == 0 else "FAIL",
        "source": {
            "path": source_path,
            "sha256": source_sha256,
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "counts": source_counts,
        },
        "geometry": {
            "playfield_m": {
                "width": float(data["w"]),
                "length": float(data["l"]),
                "bed_height": float(data["bed"]),
            },
            "ball_radius_m": float(data["ball_R"]),
            "cushion_nose_height_m": float(data["nose"]),
            "cut_angles": cut_rows,
            "pocket_shelves": shelf_rows,
        },
        "mouth_semantics": {
            "raw_fillet_endpoint_span": {
                "definition": (
                    "distance between the two jaw-side endpoints of the "
                    "main-to-jaw transition fillets"
                ),
                "expected_by_pocket_m": EXPECTED_RAW_FILLET_ENDPOINT_SPAN_M,
            },
            "evaluated_sharp_line_mouth": {
                "definition": (
                    "distance between the infinite-line intersections of "
                    "each jaw with its connected main cushion before fillets"
                ),
                "target_by_kind_m": EVALUATED_SHARP_MOUTH_TARGET_M,
                "tolerance_m": MOUTH_TOLERANCE_M,
            },
            "finished_facing_nominal_target": {
                "definition": (
                    "midpoint of the permitted WPA finished-facing mouth range"
                ),
                "wpa_range_by_kind_m": wpa_ranges,
                "by_kind_m": finished_nominal,
            },
            "pockets": mouth_rows,
        },
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - failed,
            "failed": failed,
        },
        "checks": checks,
    }


def _serialize(report):
    return json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=True,
        allow_nan=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate the Blender-free pool geometry contract.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write reports/pool_geometry_contract_audit.json",
    )
    args = parser.parse_args(argv)

    try:
        report = build_report()
    except Exception as error:
        report = {
            "schema_version": SCHEMA_VERSION,
            "validator": "scripts/91_validate_pool_geometry_contract.py",
            "status": "FAIL",
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
    output = _serialize(report)
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(output)
    sys.stdout.write(output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
