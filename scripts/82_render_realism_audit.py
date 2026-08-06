"""Render close evidence for the object-by-object realism pass."""
import bpy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402


CAMS = [
    "CAM_Audit_Entrance_35mm",
    "CAM_Audit_BarWorkflow_45mm",
    "CAM_Audit_FrontSeating_40mm",
    "CAM_Audit_Booths_45mm",
    "CAM_Audit_Lighting_35mm",
    "CAM_Audit_BoothPatina_60mm",
    "CAM_Audit_CleanBar_50mm",
    "CAM_Audit_PatronBarware_55mm",
    "CAM_Audit_StreetNeon_35mm",
    "CAM_Audit_WallHistory_45mm",
    "CAM_Audit_BathroomDoor_50mm",
]


def render(draft=False, only=None):
    scene = bpy.context.scene
    if draft:
        scene.cycles.samples = 32
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        out = os.path.join(C.ROOT, "renders", "realism_audit_drafts")
    else:
        scene.cycles.samples = 96
        scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        out = os.path.join(C.ROOT, "renders", "realism_audit")
    os.makedirs(out, exist_ok=True)
    timings = {}
    for name in (only or CAMS):
        camera = bpy.data.objects.get(name)
        if camera is None:
            raise RuntimeError("missing realism audit camera: " + name)
        scene.camera = camera
        scene.render.filepath = os.path.join(out, name + ".png")
        start = time.time()
        bpy.ops.render.render(write_still=True)
        timings[name] = round(time.time() - start, 1)
        print("  [realism-render] %-34s %6.1fs" %
              (name, timings[name]))
    entry = {
        "samples": scene.cycles.samples,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "draft": draft,
        "seconds_per_camera": timings,
    }
    path = os.path.join(C.ROOT, "reports", "realism_render_timing.json")
    report = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)
        # Migrate the original single-run schema without discarding evidence.
        if "seconds_per_camera" in existing:
            old_key = "draft" if existing.get("draft") else "preview"
            report[old_key] = existing
        else:
            report = existing
    key = "draft" if draft else "preview"
    previous_times = report.get(key, {}).get("seconds_per_camera", {})
    previous_times.update(timings)
    entry["seconds_per_camera"] = previous_times
    report[key] = entry
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return timings


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    selected = [name for name in args if name in CAMS]
    render(draft="--draft" in args, only=selected or None)
