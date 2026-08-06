"""
85_render_sweep.py — render CAM_Sweep.

EEVEE with raytracing on. It resolves ~15x faster than Cycles here, which is
what makes a 288-frame move practical, but it gathers far less indirect light
from these small practical fixtures -- so the sweep carries its own exposure
and fixture-boost compensation. Both are applied at render time only and never
touch the Cycles still setup.

Nothing in the scene animates except the camera, so there is no source of
temporal flicker: no volumetric froxel crawl, no z-fighting (the slate sits a
cloth-thickness below the cloth), and TAA is high enough to resolve cleanly.
"""
import bpy, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C

EXPOSURE = 2.35            # stops, EEVEE-vs-Cycles compensation
LIGHT_BOOST = 2.6          # EEVEE loses the bounce these practicals rely on

def render(res=(1920, 1080), samples=128, start=None, end=None):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("CAM_Sweep")
    if cam is None:
        raise SystemExit("CAM_Sweep missing - run 75_build_sweep first")
    sc.camera = cam
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True),
                      ("use_volumetric_shadows", True)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = 24
    sc.view_settings.exposure = EXPOSURE
    for ob in bpy.data.objects:
        if ob.type == "LIGHT":
            ob.data.energy *= LIGHT_BOOST
    out = os.path.join(C.ROOT, "renders", "sweep")
    os.makedirs(out, exist_ok=True)
    sc.render.filepath = os.path.join(out, "s_")
    sc.frame_start = start or 1
    sc.frame_end = end or 288
    t = time.time()
    bpy.ops.render.render(animation=True)
    print("SWEEP DONE %d frames in %.0f s" % (sc.frame_end - sc.frame_start + 1,
                                              time.time() - t))

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    a = [int(x) for x in argv if x.isdigit()]
    render(start=a[0] if a else None, end=a[1] if len(a) > 1 else None)
