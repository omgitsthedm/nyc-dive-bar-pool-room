"""114_render_cinematic_take.py - render the take, one frame at a time, resumably.

Every frame is rendered. There is no held-frame copy anywhere in this file,
which is the single biggest difference from 105_render_film.py: that script
rendered one image per static shot and shutil.copyfile'd it up to forty-five
times, so two thirds of the "film" was the same picture.

Per frame this sets, in order:

  1. the camera for whichever shot owns that frame
  2. the scene frame, which IS the film frame - 113 rebased the bake onto the
     film timeline so the rigs and the balls read the same clock
  3. the flicker multipliers for both neon sources - emissive material AND
     matching lamp, same number on both, from the schedule 113 wrote

then renders. Frames already on disk are skipped, so a run that dies at 400
picks up at 400.

DEVICES. Cycles ships configured for one device. On this machine that left
ten CPU cores idle behind the Metal GPU; enabling both measured 19.4 -> 9.9
s/frame at 720p. The device list is printed every run because "it used the
GPU" is an assumption worth re-checking after a Blender upgrade.

PERSISTENT DATA. Keeps the exported scene and its BVH between frames instead
of rebuilding 2400-odd static objects every time. It is worth roughly 2x here
and it is safe because only the sixteen balls and the cue move. It does mean
shader and lamp edits have to actually reach the depsgraph between frames -
--verify-flicker renders two adjacent frames with deliberately opposite
multipliers and prints their luminance so that assumption gets tested rather
than trusted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import film_time as FT        # noqa: E402


def log(msg):
    print("  [render] %s" % msg, flush=True)


def enable_devices(prefer="hybrid"):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        log("cycles addon preferences unavailable; leaving devices alone")
        return []
    for backend in ("METAL", "CUDA", "OPTIX", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            break
        except TypeError:
            continue
    prefs.get_devices()
    on = []
    for dev in prefs.devices:
        want = True
        if prefer == "gpu" and dev.type == "CPU":
            want = False
        if prefer == "cpu" and dev.type != "CPU":
            want = False
        dev.use = want
        if want:
            on.append("%s:%s" % (dev.type, dev.name))
    log("compute_device_type=%s  enabled=%s"
        % (getattr(prefs, "compute_device_type", "?"), on))
    return on


def configure(scene, args):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = args.adaptive_threshold
    scene.cycles.adaptive_min_samples = args.adaptive_min_samples
    scene.cycles.use_denoising = True
    scene.cycles.volume_bounces = 0
    scene.render.use_persistent_data = True
    scene.render.use_motion_blur = args.motion_blur
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = FT.FPS
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.cycles.device = "GPU" if args.devices != "cpu" else "CPU"
    log("engine=%s device=%s %d spp adaptive(thr=%.3f,min=%d) denoise=%s "
        "motion_blur=%s persistent=%s %dx%d"
        % (scene.render.engine, scene.cycles.device, scene.cycles.samples,
           scene.cycles.adaptive_threshold, scene.cycles.adaptive_min_samples,
           scene.cycles.use_denoising, scene.render.use_motion_blur,
           scene.render.use_persistent_data, args.width, args.height))


def configure_preview(scene, args):
    """Blocking preview: real motion, real timing, throwaway pixels.

    EEVEE by default. The brief allows it here and nowhere else, and the
    difference is the whole point of running a preview at all: this pass
    exists to catch a static shot, a camera inside a booth, a fixture over
    the table or a pocket out of frame, none of which are lighting questions.
    Cycles at 2 spp measured 3.5 s/frame - 42 minutes to block out a film
    that only takes 67 to render properly. EEVEE answers the same questions
    in a fraction of that.
    """
    if args.preview_engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = args.samples
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.4
        scene.cycles.adaptive_min_samples = 1
        scene.cycles.use_denoising = True
        scene.cycles.volume_bounces = 0
    else:
        for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = name
                break
            except TypeError:
                continue
        try:
            scene.eevee.taa_render_samples = max(4, args.samples * 4)
        except AttributeError:
            pass
    scene.render.use_persistent_data = True
    # Motion blur ON in the preview too. It costs almost nothing here and the
    # final render has it, so leaving it off made the preview judder in a way
    # the actual film would not - which is a preview lying about the thing it
    # exists to check.
    scene.render.use_motion_blur = bool(args.motion_blur)
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = FT.FPS
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    log("PREVIEW engine=%s %dx%d motion_blur=off (blocking only, never shipped)"
        % (scene.render.engine, args.width, args.height))


class Flicker:
    """Applies the schedule and can say exactly what it applied."""

    def __init__(self, path):
        doc = json.load(open(path))
        self.base = doc["base"]
        self.sched = doc["schedule"]
        self.nodes = {}
        for src, cfg in self.base.items():
            for mat_name in cfg["materials"]:
                mat = bpy.data.materials.get(mat_name)
                if mat is None:
                    raise RuntimeError("flicker material %s missing" % mat_name)
                node = None
                for n in mat.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED":
                        node = n
                if node is None:
                    raise RuntimeError("no Principled node in %s" % mat_name)
                self.nodes[mat_name] = node
            if bpy.data.objects.get(cfg["light"]) is None:
                raise RuntimeError("flicker light %s missing" % cfg["light"])
        log("flicker: %d sources, %d materials"
            % (len(self.base), len(self.nodes)))

    def apply(self, frame):
        applied = {}
        for src, cfg in self.base.items():
            m = self.sched[src][frame]
            for mat_name, bval in cfg["materials"].items():
                self.nodes[mat_name].inputs["Emission Strength"] \
                    .default_value = bval * m
            lt = bpy.data.objects[cfg["light"]]
            lt.data.energy = cfg["light_energy"] * m
            applied[src] = m
        return applied

    def force(self, value):
        for src, cfg in self.base.items():
            for mat_name, bval in cfg["materials"].items():
                self.nodes[mat_name].inputs["Emission Strength"] \
                    .default_value = bval * value
            bpy.data.objects[cfg["light"]].data.energy = \
                cfg["light_energy"] * value


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--flicker", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--adaptive-threshold", type=float, default=0.10)
    ap.add_argument("--adaptive-min-samples", type=int, default=4)
    ap.add_argument("--devices", choices=("hybrid", "gpu", "cpu"),
                    default="hybrid")
    ap.add_argument("--motion-blur", type=int, default=1)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--preview-engine", choices=("eevee", "cycles"),
                    default="eevee")
    ap.add_argument("--frames", default="",
                    help="comma list and/or a-b ranges; default all 720")
    ap.add_argument("--timing-json", default="")
    ap.add_argument("--force", action="store_true",
                    help="re-render frames that already exist")
    ap.add_argument("--verify-flicker", action="store_true")
    args = ap.parse_args(argv)

    man = json.load(open(args.manifest))
    scene = bpy.context.scene
    os.makedirs(args.out, exist_ok=True)

    # Refuse to render the wrong view layer. The default one carries BOTH the
    # static hero balls and the solver-driven ones; only GAMEPLAY excludes the
    # static set. Getting this wrong is invisible in the rack and catastrophic
    # once the break starts, so it is checked rather than assumed.
    want_layer = man.get("render_view_layer", "GAMEPLAY")
    enabled = [vl.name for vl in scene.view_layers if vl.use]
    if enabled != [want_layer]:
        for vl in scene.view_layers:
            vl.use = (vl.name == want_layer)
        enabled = [vl.name for vl in scene.view_layers if vl.use]
    if enabled != [want_layer]:
        raise RuntimeError("could not isolate view layer %s (enabled=%s)"
                           % (want_layer, enabled))
    log("render view layer: %s" % enabled[0])

    enable_devices(args.devices)
    (configure_preview if args.preview else configure)(scene, args)

    flick = Flicker(args.flicker)

    owner = {}
    for sh in man["shots"]:
        cam = bpy.data.objects.get(sh["cam"])
        if cam is None:
            raise RuntimeError("missing camera %s" % sh["cam"])
        for f in range(sh["first"], sh["last"] + 1):
            owner[f] = cam
    if len(owner) != FT.TOTAL_FRAMES:
        raise RuntimeError("shots own %d frames, expected %d"
                           % (len(owner), FT.TOTAL_FRAMES))

    if args.frames:
        wanted = []
        for part in args.frames.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")
                wanted.extend(range(int(a), int(b) + 1))
            elif part:
                wanted.append(int(part))
    else:
        wanted = list(range(FT.TOTAL_FRAMES))

    if args.verify_flicker:
        # Persistent data keeps the scene between frames. Prove that a shader
        # and lamp edit still lands by rendering the same frame twice with the
        # multiplier pinned high then low, and printing both luminances.
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        from pngstats import luminance_stats
        fr = wanted[0]
        scene.camera = owner[fr]
        scene.frame_set(fr)
        outs = {}
        for tag, val in (("hi", 1.0), ("lo", 0.15)):
            flick.force(val)
            p = os.path.join(args.out, "_flickcheck_%s.png" % tag)
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            outs[tag] = luminance_stats(p, stride_px=37)["mean"]
        log("FLICKER/PERSISTENT-DATA CHECK frame %d: mean(hi)=%.5f "
            "mean(lo)=%.5f  delta=%.5f  -> %s"
            % (fr, outs["hi"], outs["lo"], outs["hi"] - outs["lo"],
               "shader edits DO reach the render"
               if abs(outs["hi"] - outs["lo"]) > 1e-4
               else "*** SHADER EDITS ARE NOT REACHING THE RENDER ***"))
        return 0

    todo = [f for f in wanted
            if args.force or not os.path.exists(
                os.path.join(args.out, "%04d.png" % f))]
    log("%d frame(s) requested, %d to render, %d already on disk"
        % (len(wanted), len(todo), len(wanted) - len(todo)))

    times = []
    started = time.time()
    for i, f in enumerate(todo):
        cam = owner[f]
        scene.camera = cam
        # One clock. The gameplay was rebased onto film frames by 113, so
        # setting the film frame moves the rig AND the balls, and Cycles gets
        # real motion blur out of both.
        sf = f
        scene.frame_set(sf)
        applied = flick.apply(f)
        scene.render.filepath = os.path.join(args.out, "%04d.png" % f)
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        times.append(dict(frame=f, seconds=round(dt, 3), cam=cam.name,
                          scene_frame=sf,
                          flicker={k: round(v, 4) for k, v in applied.items()}))
        if i % 5 == 0 or i == len(todo) - 1:
            done = i + 1
            el = time.time() - started
            rate = el / done
            log("%4d/%4d  f%04d %-34s %5.1fs  (avg %.1fs, eta %.1f min)"
                % (done, len(todo), f, cam.name, dt, rate,
                   rate * (len(todo) - done) / 60.0))

    if times:
        secs = sorted(t["seconds"] for t in times)
        n = len(secs)
        med = secs[n // 2]
        p90 = secs[min(n - 1, int(0.90 * n))]
        log("rendered %d frames in %.1f min  median %.2fs  p90 %.2fs  "
            "max %.2fs" % (n, (time.time() - started) / 60.0, med, p90,
                           secs[-1]))
        if args.timing_json:
            os.makedirs(os.path.dirname(args.timing_json), exist_ok=True)
            with open(args.timing_json, "w") as fh:
                json.dump(dict(width=args.width, height=args.height,
                               samples=args.samples, devices=args.devices,
                               motion_blur=bool(args.motion_blur),
                               adaptive_threshold=args.adaptive_threshold,
                               adaptive_min_samples=args.adaptive_min_samples,
                               preview=args.preview,
                               median_s=med, p90_s=p90, max_s=secs[-1],
                               mean_s=round(sum(secs) / n, 3),
                               frames=times), fh, indent=1)
            log("timings -> %s" % args.timing_json)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
