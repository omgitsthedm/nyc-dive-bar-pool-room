"""80_render_checkpoints.py — render each required camera. Preview or final."""
import bpy, os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C

CAMS = ["CAM_Hero_Entry_30mm", "CAM_Table_ThreeQuarter_50mm",
        "CAM_Rack_Detail_85mm", "CAM_Bar_Reverse_35mm",
        "CAM_Environment_Wide_35mm", "CAM_FrontRoom_22mm"]

def render(final=False, draft=False, only=None):
    sc = bpy.context.scene
    if final:
        sc.cycles.samples = 512; sc.render.resolution_x = 3840
        sc.render.resolution_y = 2160
        out = os.path.join(C.ROOT, "renders", "final_png")
    elif draft:
        sc.cycles.samples = 32; sc.render.resolution_x = 1280
        sc.render.resolution_y = 720
        out = os.path.join(C.ROOT, "renders", "checkpoint_drafts")
    else:
        sc.cycles.samples = 96; sc.render.resolution_x = 1600
        sc.render.resolution_y = 900
        out = os.path.join(C.ROOT, "renders", "checkpoints")
    os.makedirs(out, exist_ok=True)
    timing = {}
    for name in (only or CAMS):
        cam = bpy.data.objects.get(name)
        if not cam: 
            print("  [render] MISSING %s" % name); continue
        sc.camera = cam
        sc.render.filepath = os.path.join(out, name + ".png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        timing[name] = round(dt, 1)
        print("  [render] %-32s %6.1fs  %dx%d @%d spp"
              % (name, dt, sc.render.resolution_x, sc.render.resolution_y,
                 sc.cycles.samples))
    p = os.path.join(C.ROOT, "reports", "render_timing.json")
    prev = json.load(open(p)) if os.path.exists(p) else {}
    key = "final" if final else ("draft" if draft else "preview")
    previous_times = prev.get(key, {}).get("seconds_per_camera", {})
    previous_times.update(timing)
    prev[key] = {
        "device": sc.cycles.device, "samples": sc.cycles.samples,
        "resolution": [sc.render.resolution_x, sc.render.resolution_y],
        "seconds_per_camera": previous_times}
    json.dump(prev, open(p, "w"), indent=2)
    return timing

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    selected = [name for name in argv if name in CAMS]
    render(final=("--final" in argv), draft=("--draft" in argv),
           only=selected or None)
