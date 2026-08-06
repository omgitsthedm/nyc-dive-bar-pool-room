"""Render the ordered, visual-only opening chapter from one saved scene."""
import argparse
import bpy
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402


SHOT_SEQUENCE = (
    ("01", "CAM_Audit_StreetNeon_35mm"),
    ("02", "CAM_Cinematic_Threshold_Low_32mm"),
    ("03", "CAM_FrontRoom_22mm"),
    ("04", "CAM_Bar_Reverse_35mm"),
    ("05", "CAM_Audit_CleanBar_50mm"),
    ("06", "CAM_Audit_PatronBarware_55mm"),
    ("07", "CAM_Audit_Booths_45mm"),
    ("08", "CAM_Audit_BoothPatina_60mm"),
    ("09", "CAM_Audit_WallHistory_45mm"),
    ("10", "CAM_Audit_BathroomDoor_50mm"),
    ("11", "CAM_Audit_Lighting_35mm"),
    ("12", "CAM_Hero_Entry_30mm"),
    ("13", "CAM_Table_ThreeQuarter_50mm"),
    ("14", "CAM_Cinematic_BreakLine_70mm"),
    ("15", "CAM_Rack_Detail_85mm"),
)

QUALITY = {
    "draft": (32, (1280, 720)),
    "preview": (96, (1600, 900)),
    "final": (512, (3840, 2160)),
}


def _positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def _resolution(value):
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (AttributeError, TypeError, ValueError):
        raise argparse.ArgumentTypeError("use WIDTHxHEIGHT")
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("resolution must be positive")
    return width, height


def _validate_cameras(sequence):
    names = [name for _index, name in sequence]
    if len(names) != len(set(names)):
        raise RuntimeError("cinematic sequence contains duplicate cameras")
    problems = []
    for _index, name in sequence:
        camera = bpy.data.objects.get(name)
        if camera is None or camera.type != "CAMERA":
            problems.append(name + " missing or not a camera")
            continue
        match = re.search(r"_(\d+)mm$", name)
        if match and camera.data.type == "PERSP":
            expected = float(match.group(1))
            if abs(camera.data.lens - expected) > 0.01:
                problems.append("%s lens %.3f != %.3f" %
                                (name, camera.data.lens, expected))
    if problems:
        raise RuntimeError("; ".join(problems))


def render(mode="preview", samples=None, resolution=None, only=None):
    sequence = SHOT_SEQUENCE
    if only:
        requested = set(only)
        known = {name for _index, name in SHOT_SEQUENCE}
        unknown = sorted(requested - known)
        if unknown:
            raise RuntimeError("unknown cinematic cameras: " +
                               ", ".join(unknown))
        sequence = tuple(row for row in SHOT_SEQUENCE if row[1] in requested)
    _validate_cameras(sequence)

    default_samples, default_resolution = QUALITY[mode]
    samples = samples or default_samples
    width, height = resolution or default_resolution
    scene = bpy.context.scene
    scene.cycles.samples = samples
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    output = os.path.join(C.ROOT, "renders", "cinematic_stills")
    os.makedirs(output, exist_ok=True)

    timing = {}
    for index, name in sequence:
        scene.camera = bpy.data.objects[name]
        filename = "%s-%s.png" % (index, name)
        scene.render.filepath = os.path.join(output, filename)
        started = time.time()
        bpy.ops.render.render(write_still=True)
        seconds = round(time.time() - started, 1)
        timing[name] = seconds
        print("  [cinematic still] %s %-38s %6.1fs" %
              (index, name, seconds))

    report_path = os.path.join(C.ROOT, "reports",
                               "cinematic_stills_timing.json")
    report = {}
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    previous = report.get(mode, {}).get("seconds_per_camera", {})
    previous.update(timing)
    report[mode] = {
        "device": scene.cycles.device,
        "samples": samples,
        "resolution": [width, height],
        "shot_count": len(SHOT_SEQUENCE),
        "seconds_per_camera": previous,
    }
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return timing


def _parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", choices=tuple(QUALITY),
                        default="preview")
    parser.add_argument("--samples", type=_positive_int)
    parser.add_argument("--resolution", type=_resolution)
    parser.add_argument("cameras", nargs="*")
    args = parser.parse_args(argv)
    return args


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = _parse(argv)
    render(mode=args.quality, samples=args.samples,
           resolution=args.resolution, only=args.cameras or None)
