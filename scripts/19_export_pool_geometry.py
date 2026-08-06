"""Export the shared Pooltool/Blender 9-foot table geometry contract.

Run this with the project-adjacent Python 3.12 environment that contains the
pinned Pooltool 0.6.0 package.  The Pooltool ``*_pocket_width`` constructor
values are source parameters rather than evaluated cushion-mouth dimensions,
so this exporter solves those inputs until the built geometry measures the
WPA-range midpoints declared in :mod:`config`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pooltool as pt
from pooltool.objects.table.specs import PocketTableSpecs

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import config as C  # noqa: E402
import pool_geometry_contract as G  # noqa: E402


POOLTOOL_REQUIRED = "0.6.0"
DEFAULT_OUTPUT = os.path.join(
    ROOT, "assets", "data", "table_wpa_geometry.json")
MOUTH_TOLERANCE_M = 1e-12


def _specs(corner_source_width, side_source_width):
    return PocketTableSpecs(
        l=C.PLAY_L,
        w=C.PLAY_W,
        cushion_width=C.CUSHION_COVERED_W,
        cushion_height=C.CUSHION_NOSE,
        corner_pocket_width=corner_source_width,
        side_pocket_width=side_source_width,
        # Pooltool source angles calibrated to evaluated WPA cuts.
        corner_pocket_angle=7.0,
        side_pocket_angle=14.5,
        corner_pocket_depth=0.0417,
        corner_pocket_radius=0.062,
        corner_jaw_radius=0.02095,
        side_pocket_depth=0.0685,
        side_pocket_radius=0.0645,
        side_jaw_radius=0.00795,
        height=C.BED_Z,
        lights_height=C.BED_Z + C.FIXTURE_MIN_ABOVE_BED,
    )


def _export_table(table):
    return {
        "w": float(table.w),
        "l": float(table.l),
        "bed": C.BED_Z,
        "ball_R": C.BALL_R,
        "nose": C.CUSHION_NOSE,
        "cushion_width": C.CUSHION_COVERED_W,
        "linear": {
            key: {
                "p1": [float(value) for value in segment.p1],
                "p2": [float(value) for value in segment.p2],
            }
            for key, segment in table.cushion_segments.linear.items()
        },
        "circular": {
            key: {
                "center": [float(value) for value in segment.center],
                "radius": float(segment.radius),
            }
            for key, segment in table.cushion_segments.circular.items()
        },
        "pockets": {
            key: {
                "center": [float(value) for value in pocket.center],
                "radius": float(pocket.radius),
                "depth": float(pocket.depth),
            }
            for key, pocket in table.pockets.items()
        },
    }


def _build(corner_source_width, side_source_width):
    specs = _specs(corner_source_width, side_source_width)
    return _export_table(pt.Table.from_table_specs(specs))


def _measured_mouth(kind, corner_source_width, side_source_width):
    data = _build(corner_source_width, side_source_width)
    metrics = G.pocket_metrics(data)
    pocket = "corner_SW" if kind == "corner" else "side_W"
    return metrics[pocket]["mouth_m"]


def _solve_source_width(kind, target, corner_seed, side_seed):
    low = target - 0.006
    high = target + 0.006
    for _ in range(80):
        source = (low + high) / 2.0
        corner = source if kind == "corner" else corner_seed
        side = source if kind == "side" else side_seed
        measured = _measured_mouth(kind, corner, side)
        if measured < target:
            low = source
        else:
            high = source
    return (low + high) / 2.0


def build_contract():
    if pt.__version__ != POOLTOOL_REQUIRED:
        raise RuntimeError(
            "Pooltool %s is required, found %s" %
            (POOLTOOL_REQUIRED, pt.__version__))
    corner_source = _solve_source_width(
        "corner", C.CORNER_MOUTH, C.CORNER_MOUTH, C.SIDE_MOUTH)
    side_source = _solve_source_width(
        "side", C.SIDE_MOUTH, corner_source, C.SIDE_MOUTH)
    data = _build(corner_source, side_source)
    metrics = G.pocket_metrics(data)
    corner = metrics["corner_SW"]
    side = metrics["side_W"]
    if abs(corner["mouth_m"] - C.CORNER_MOUTH) > MOUTH_TOLERANCE_M or \
            abs(side["mouth_m"] - C.SIDE_MOUTH) > MOUTH_TOLERANCE_M:
        raise RuntimeError("evaluated pocket mouths missed their targets")
    if max(abs(value - C.CORNER_CUT_ANGLE)
           for value in corner["cut_angles_deg"]) > 0.01 or \
            max(abs(value - C.SIDE_CUT_ANGLE)
                for value in side["cut_angles_deg"]) > 0.01:
        raise RuntimeError("evaluated pocket jaw angles missed WPA targets")
    return data, corner_source, side_source


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = _parse_args()
    data, corner_source, side_source = build_contract()
    output = os.path.realpath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, allow_nan=False)
        handle.write("\n")
    metrics = G.pocket_metrics(data)
    print("[pool geometry] wrote " + output)
    print("  source widths: corner %.6f mm, side %.6f mm" %
          (corner_source * 1000.0, side_source * 1000.0))
    print("  evaluated mouths: corner %.6f mm, side %.6f mm" %
          (metrics["corner_SW"]["mouth_m"] * 1000.0,
           metrics["side_W"]["mouth_m"] * 1000.0))


if __name__ == "__main__":
    main()
