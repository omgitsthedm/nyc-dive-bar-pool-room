"""Render six gameplay proof frames from the derived scene."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "renders" / "physics_proof"
DEFAULT_REPORT = ROOT / "reports" / "physics_render_timing.json"


def parse_args():
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("eevee", "cycles"), default="cycles")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--only", nargs="*", default=None,
        help="optional proof names to render, for example 01_rack_setup",
    )
    return parser.parse_args(values)


def main() -> int:
    args = parse_args()
    if not args.out.is_absolute():
        args.out = ROOT / args.out
    if not args.report.is_absolute():
        args.report = ROOT / args.report
    scene = bpy.context.scene
    view_layer = scene.view_layers.get("GAMEPLAY")
    if view_layer is None:
        raise RuntimeError("GAMEPLAY view layer is missing")
    bpy.context.window.view_layer = view_layer
    for layer in scene.view_layers:
        layer.use = layer == view_layer

    if args.engine == "cycles":
        scene.render.engine = "CYCLES"
        engine_label = "Blender 5.2 Cycles"
        samples = args.samples or 48
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.device = "GPU"
    else:
        scene.render.engine = "BLENDER_EEVEE"
        engine_label = "Blender 5.2 Eevee Next draft"
        samples = args.samples or 16
        # Match the project's established Eevee sweep compensation.  The room
        # is authored for Cycles and relies on bounce from small practicals;
        # these temporary render-process changes are never saved to the blend.
        scene.view_settings.exposure = 2.35
        for obj in bpy.data.objects:
            if obj.type == "LIGHT":
                obj.data.energy *= 2.6

    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    args.out.mkdir(parents=True, exist_ok=True)

    all_shots = (
        ("01_rack_setup", 1, "PT_GameCamera_Overhead"),
        ("02_rack_lift", 16, "PT_GameCamera_Break"),
        ("03_cue_contact", 30, "PT_GameCamera_Break"),
        ("04_first_rack_impact", 33, "PT_GameCamera_Break"),
        ("05_opening_spread", 48, "PT_GameCamera_Overhead"),
        ("06_settled_table", scene.frame_end - 1, "PT_GameCamera_Overhead"),
    )
    shots = all_shots
    if args.only:
        requested = set(args.only)
        shots = tuple(row for row in shots if row[0] in requested)
        missing = requested.difference(row[0] for row in shots)
        if missing:
            raise ValueError("unknown proof names: " + ", ".join(sorted(missing)))
    rows = []
    for name, frame, camera_name in shots:
        camera = bpy.data.objects.get(camera_name)
        if camera is None:
            raise RuntimeError("missing gameplay camera: " + camera_name)
        scene.camera = camera
        scene.frame_set(int(frame))
        output = args.out / (name + ".png")
        scene.render.filepath = str(output)
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True, layer="GAMEPLAY")
        elapsed = time.perf_counter() - started
        rows.append({
            "name": name,
            "frame": int(frame),
            "camera": camera_name,
            "path": str(output.relative_to(ROOT)),
            "seconds": elapsed,
        })
        print("  [physics proof] %s %.2fs" % (name, elapsed))

    report_rows = rows
    if args.only and args.report.exists():
        previous = json.loads(args.report.read_text(encoding="utf-8"))
        compatible = (
            previous.get("schema") == "pool-physics-render-timing/v1"
            and previous.get("engine") == engine_label
            and previous.get("samples_requested") == samples
            and previous.get("resolution") == [args.width, args.height]
        )
        if compatible:
            merged = {row["name"]: row for row in previous.get("renders", [])}
            merged.update({row["name"]: row for row in rows})
            report_rows = [
                merged[name] for name, _frame, _camera in all_shots
                if name in merged
            ]

    report = {
        "schema": "pool-physics-render-timing/v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "engine": engine_label,
        "samples_requested": samples,
        "resolution": [args.width, args.height],
        "view_layer": "GAMEPLAY",
        "total_seconds": sum(row["seconds"] for row in report_rows),
        "renders": report_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    scene.frame_set(1)
    print("  [physics proof report] %s" % args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
