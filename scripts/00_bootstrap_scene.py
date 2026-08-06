"""
00_bootstrap_scene.py — units, collections, render defaults, locked reference.

Owns: 00_GUIDES, 99_REFERENCE_LOCKED, and scene-level settings.
Idempotent.
"""
import bpy
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402


def build():
    scene = bpy.context.scene

    # Purge Blender's startup scene. The default Cube spans -1..1 m, which is
    # exactly where this room's table sits -- it swallowed the 85 mm rack
    # camera whole and occluded the rack in the three-quarter view.
    for name in ("Cube", "Light", "Camera"):
        ob = bpy.data.objects.get(name)
        if ob is not None and not ob.name.startswith(("PT_", "ENV_", "BAR_",
                                                      "LGT_", "CAM_", "REF_")):
            bpy.data.objects.remove(ob, do_unlink=True)
            print("  [bootstrap] removed startup object %r" % name)

    # ------------------------------------------------------------- units ---
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    # --------------------------------------------------------- collections --
    for name in C.COLLECTIONS:
        L.get_collection(name)

    # ------------------------------------------------------------ render ---
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception as exc:                      # CPU fallback, reported
        print("  [bootstrap] Metal GPU unavailable (%s); using CPU" % exc)
        scene.cycles.device = "CPU"

    scene.cycles.samples = 512
    scene.cycles.preview_samples = 96
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
        scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    except Exception:
        pass
    scene.cycles.caustics_reflective = True
    scene.cycles.caustics_refractive = True

    scene.render.resolution_x = 3840
    scene.render.resolution_y = 2160
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"

    # AgX, Medium High Contrast (brief sec.14)
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        try:
            scene.view_settings.look = "Medium High Contrast"
        except TypeError:
            print("  [bootstrap] AgX look name not found; leaving default")
    # Calibrated from the 85 mm ball/detail camera: zero stops clipped the
    # white number circles and washed bottle-green cloth to mint. The room's
    # motivated practicals are balanced around this scene-wide exposure.
    scene.view_settings.exposure = -1.0
    scene.view_settings.gamma = 1.0

    # ----------------------------------------------- locked benchmark ------
    ref = L.clear_collection("99_REFERENCE_LOCKED")
    if os.path.exists(C.REFERENCE_GLB):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=C.REFERENCE_GLB)
        imported = [o for o in bpy.data.objects if o not in before]
        for ob in imported:
            ob.name = "REF_" + ob.name
            L.link(ob, "99_REFERENCE_LOCKED")
            ob.hide_render = True
            ob.hide_viewport = True
            ob.hide_select = True
        print("  [bootstrap] benchmark locked: %d objects" % len(imported))
    else:
        print("  [bootstrap] WARNING benchmark GLB not found at %s"
              % C.REFERENCE_GLB)

    # cue-clearance envelope: a wire guide, never rendered
    L.clear_collection("00_GUIDES")
    env = L.box("GUIDE_CueClearance",
                (C.CUE_ENVELOPE_W, C.CUE_ENVELOPE_L, 0.02),
                (C.TABLE_CENTRE[0], C.TABLE_CENTRE[1], 0.01), "00_GUIDES")
    env.display_type = "WIRE"
    env.hide_render = True

    # Excluded from every view layer so neither the benchmark nor the
    # clearance guide can leak into a render. hide_render alone is not enough:
    # a later stage or a reopened file can clear it, and the guide is a solid
    # box sitting right where the rack is.
    for vl in scene.view_layers:
        for name in ("99_REFERENCE_LOCKED", "00_GUIDES"):
            lc = vl.layer_collection.children.get(name)
            if lc:
                lc.exclude = True

    print("  [bootstrap] engine=%s device=%s  collections=%d"
          % (scene.render.engine, scene.cycles.device, len(C.COLLECTIONS)))
    return True


if __name__ == "__main__":
    build()
