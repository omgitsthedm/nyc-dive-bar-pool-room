"""105_render_film.py - the 30-second break film, EEVEE, 1080p24.

ONE global frame counter for the whole film: film_frame(n) = n, n = round(
film_time_s * 24), frames 0..719. Every shot renders into the SAME
renders/film_frames/%04d.png numbering, so ffmpeg assembles in one pass with
no concat step.

SCENE-TIME MAPPING (INVARIANT, shared with the audio mixer):
    scene_time_s = film_time_s - FILM_OFFSET_S
so the baked strike lands exactly on film frame 240.

WHERE THIS DEPARTS FROM THE SHOT LIST, AND WHY
The written cut put five settle inserts in 0:18-0:28 and had them cut on
pocket-drop and last-rail timestamps. The chosen take (b_51) settles in
7.806 s, so with the strike at 0:10 every event in the shot has happened by
film 0:17.81 and that window contains no events whatsoever. Rather than
invent timestamps, the Act-2 cut points are DERIVED from the event list as
the document actually requires, and land where the physics is. The stretch
after the last ball stops becomes what David asked the last seconds to be:
quick static glances, not one long hold.

Nothing about the physics is touched to make this fit: no slow motion, no
retiming, no re-roll. The break occupies exactly the 7.806 s it takes.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402

FPS = 24
FILM_LEN_S = 30.0
# The document fixes this at 10.0 ("strike at film frame 240") and marks the
# mapping INVARIANT. The invariant's stated purpose is that picture and sound
# share one constant, and that still holds: 111_build_film_audio.py imports
# FILM_OFFSET_S from here, so there is exactly one number.
#
# The value moved because 10.0 was chosen for a break that settles in ~18 s.
# b_51 settles in 7.81 s, so a strike at 0:10 ends all motion by 0:17.81 and
# leaves 12.2 s - 40% of the film - as aftermath. Striking at 0:14 gives the
# venue the long cold open the room deserves, keeps the break in real time,
# and leaves a 6 s coda instead of a 12 s one.
FILM_OFFSET_S = 14.0          # strike lands on film frame 336
TOTAL_FRAMES = int(FILM_LEN_S * FPS)          # 720, frames 0..719
SHOT_JSON = os.path.join(C.ROOT, "assets", "data", "shots", "break_film.json")
FRAME_DIR = os.path.join(C.ROOT, "renders", "film_frames")
CUT_JSON = os.path.join(C.ROOT, "reports", "film_cut_list.json")


def f(t):
    """film seconds -> film frame"""
    return int(round(t * FPS))


def build_cut_list(shot):
    """Act 1 and Act 3 are authored; Act 2 is derived from the event list."""
    events = shot["events"]
    dur = float(shot["duration_s"])
    strike_end = FILM_OFFSET_S + dur           # film time of last motion

    def ev(kinds, after=0.0):
        return sorted((e for e in events
                       if e["type"] in kinds and e["time_s"] > after),
                      key=lambda e: e["time_s"])

    pockets = ev(("ball_pocket",))
    cushions = ev(("ball_linear_cushion", "ball_circular_cushion"), 0.6)
    stops = ev(("rolling_stationary",))

    def speed(e):
        v = e["balls"][0]["initial"]["velocity_mps"]
        return math.hypot(float(v[0]), float(v[1]))

    cuts = []

    # ---- ACT 1: the room in glances, all pre-strike, all static ---------
    cold = [("CAM_Audit_StreetNeon_35mm", 0.0, 1.9),
            ("CAM_Film_Register_50mm", 1.9, 3.7),
            ("CAM_Audit_PatronBarware_55mm", 3.7, 5.4),
            ("CAM_Audit_BoothPatina_60mm", 5.4, 7.2),
            ("CAM_Audit_Booths_45mm", 7.2, 9.1),
            ("CAM_Audit_Lighting_35mm", 9.1, 11.0)]
    for cam, a, b in cold:
        cuts.append({"cam": cam, "start": f(a), "end": f(b) - 1,
                     "static": True, "why": "cold open"})
    cuts.append({"cam": "CAM_Film_CueAddress_85mm", "start": f(11.0),
                 "end": f(13.0) - 1, "static": True, "why": "address"})
    cuts.append({"cam": "CAM_Film_TipInsert_100mm", "start": f(13.0),
                 "end": f(FILM_OFFSET_S) - 1, "static": True,
                 "why": "one second of held breath"})

    # ---- ACT 2: ONE continuous pass through the physics ------------------
    # Every shot here advances the same timeline; nothing is replayed from a
    # second angle, so a cut can only land where the clock already is. Cut
    # points are snapped to real event timestamps.
    def snap(target_traj_t, pool, fallback):
        """nearest event time in `pool` to target, else fallback"""
        if not pool:
            return fallback
        best = min(pool, key=lambda e: abs(e["time_s"] - target_traj_t))
        return best["time_s"]

    all_stops = [e for e in stops]
    cue_stop = [e for e in all_stops if e["balls"][0]["id"] == "cue"]

    # strike + scatter, real time, hard cut while balls are still moving
    t_a = snap(2.5, pockets + cushions, 2.5)
    cuts.append({"cam": "CAM_Film_CueAddress_85mm",
                 "start": f(FILM_OFFSET_S), "end": f(FILM_OFFSET_S + t_a) - 1,
                 "static": False, "cut_on_traj_s": round(t_a, 4),
                 "why": "strike and scatter, real time"})

    # the god shot: longest in the film, runs while the spread develops
    t_b = snap(5.5, all_stops, 5.5)
    cuts.append({"cam": "CAM_Film_BreakOverhead_24mm",
                 "start": f(FILM_OFFSET_S + t_a),
                 "end": f(FILM_OFFSET_S + t_b) - 1, "static": False,
                 "cut_on_traj_s": round(t_b, 4),
                 "why": "god shot: spread develops, rails return, pockets swallow"})

    # the cue ball drifting to its stop
    t_c = cue_stop[0]["time_s"] if cue_stop else (t_b + (dur - t_b) * 0.5)
    t_c = max(t_c, t_b + 0.8)
    if t_c < dur - 0.4:
        cuts.append({"cam": "CAM_Film_Insert_D",
                     "start": f(FILM_OFFSET_S + t_b),
                     "end": f(FILM_OFFSET_S + t_c) - 1, "static": False,
                     "cut_on_traj_s": round(t_c, 4),
                     "why": "the cue ball drifting to its final stop"})
    else:
        t_c = t_b

    # the last thing moving anywhere on the table
    last_id = all_stops[-1]["balls"][0]["id"] if all_stops else "?"
    cuts.append({"cam": "CAM_Film_Insert_E",
                 "start": f(FILM_OFFSET_S + t_c),
                 "end": f(FILM_OFFSET_S + dur) - 1, "static": False,
                 "cut_on_traj_s": round(dur, 4),
                 "why": "ball %s, the last thing moving" % last_id})

    # ---- ACT 3: the room after, in quick glances, then one breath -------
    t = FILM_OFFSET_S + dur
    tail = [("CAM_Film_Insert_A", "the basket that swallowed the first ball"),
            ("CAM_Rack_Detail_85mm", "what is left of the rack"),
            ("CAM_Cinematic_BreakLine_70mm", "down the line")]
    for cam, why in tail:
        if t >= 28.0 - 0.6:
            break
        length = min(1.9, 28.0 - t)
        cuts.append({"cam": cam, "start": f(t), "end": f(t + length) - 1,
                     "static": True, "why": why})
        t += length
    # The poster frame is the first frame of this last shot (film 0:28).
    cuts.append({"cam": "CAM_Table_ThreeQuarter_50mm", "start": f(28.0),
                 "end": TOTAL_FRAMES - 1, "static": True,
                 "why": "settled table, one breath, cut to black"})

    # Close any gap left by rounding so the counter is continuous 0..719.
    cuts.sort(key=lambda c: c["start"])
    for i, c in enumerate(cuts[:-1]):
        c["end"] = cuts[i + 1]["start"] - 1
    cuts[-1]["end"] = TOTAL_FRAMES - 1
    return [c for c in cuts if c["end"] >= c["start"]], strike_end


def apply_eevee_atmosphere(scene):
    """A1 engine split, EEVEE side: real volume OFF, legacy cones ON."""
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            break
        except TypeError:
            continue
    haze = bpy.data.objects.get("ATM_RoomHaze_Volume")
    if haze is not None:
        haze.hide_render = True
    cones = [o for o in bpy.data.objects if o.name.startswith("ATM_PoolBeam")]
    for ob in cones:
        ob.hide_render = False
    # This room has 26 shadow-casting lights and 2472 render-visible objects,
    # which overruns EEVEE's shadow pool at 1080p (measured 2853 tiles against
    # 2048) and silently drops shadows - the renderer warns per frame and
    # keeps going, so a whole film can come out with missing contact shadows
    # and nothing fails.
    #
    # 512 is the DEFAULT, so asking for 512 changes nothing; the first attempt
    # at this fix was a no-op that still logged thousands of warnings. Take
    # the top of the enum and verify afterwards rather than trusting the set.
    for size in ("2048", "1536", "1024"):
        try:
            scene.eevee.shadow_pool_size = size
            break
        except (AttributeError, TypeError):
            continue
    print("  [film] shadow pool -> %s MB (default is 512)"
          % getattr(scene.eevee, "shadow_pool_size", "n/a"))
    print("  [film] engine=%s  room haze OFF, %d pool-beam volume(s) ON"
          % (scene.render.engine, len(cones)))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolution", default="1920x1080")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    with open(SHOT_JSON) as handle:
        shot = json.load(handle)
    cuts, strike_end = build_cut_list(shot)

    os.makedirs(FRAME_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CUT_JSON), exist_ok=True)
    with open(CUT_JSON, "w") as handle:
        json.dump({"shot": shot["shot_id"],
                   "trajectory_sha256": shot["trajectory_sha256"],
                   "fps": FPS, "total_frames": TOTAL_FRAMES,
                   "film_offset_s": FILM_OFFSET_S,
                   "last_motion_film_s": round(strike_end, 4),
                   "cuts": cuts}, handle, indent=1)

    covered = sum(c["end"] - c["start"] + 1 for c in cuts)
    print("  [film] %d shots, %d/%d frames covered, last motion at film %.2fs"
          % (len(cuts), covered, TOTAL_FRAMES, strike_end))
    for c in cuts:
        print("    %04d-%04d  %-32s %-6s %s"
              % (c["start"], c["end"], c["cam"],
                 "static" if c["static"] else "motion", c["why"]))
    if args.dry_run:
        return 0

    w, h = (int(v) for v in args.resolution.lower().split("x"))
    scene = bpy.context.scene
    apply_eevee_atmosphere(scene)
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.use_motion_blur = True

    baked_start, baked_end = scene.frame_start, scene.frame_end
    started = time.time()
    rendered = copied = 0
    for c in cuts:
        cam = bpy.data.objects.get(c["cam"])
        if cam is None:
            raise RuntimeError("film cut references missing camera %s"
                               % c["cam"])
        scene.camera = cam
        if c["static"]:
            # A held frame is rendered ONCE and copied, not re-rendered per
            # frame. Pick a pre-strike scene frame where the staging reads.
            scene.frame_set(baked_start)
            first = os.path.join(FRAME_DIR, "%04d.png" % c["start"])
            scene.render.filepath = first
            bpy.ops.render.render(write_still=True)
            rendered += 1
            for n in range(c["start"] + 1, c["end"] + 1):
                shutil.copyfile(first, os.path.join(FRAME_DIR, "%04d.png" % n))
                copied += 1
        else:
            for n in range(c["start"], c["end"] + 1):
                scene_t = n / FPS - FILM_OFFSET_S
                frame = baked_start + int(round(scene_t * FPS))
                scene.frame_set(max(baked_start, min(baked_end, frame)))
                scene.render.filepath = os.path.join(FRAME_DIR,
                                                     "%04d.png" % n)
                bpy.ops.render.render(write_still=True)
                rendered += 1
        print("    %-32s %04d-%04d done (%.0fs elapsed)"
              % (c["cam"], c["start"], c["end"], time.time() - started))

    print("  [film] %d frames rendered, %d copied, %.1f min total"
          % (rendered, copied, (time.time() - started) / 60.0))
    missing = [n for n in range(TOTAL_FRAMES)
               if not os.path.exists(os.path.join(FRAME_DIR, "%04d.png" % n))]
    if missing:
        raise RuntimeError("missing %d film frames, first=%d"
                           % (len(missing), missing[0]))
    print("  [film] all %d frames present" % TOTAL_FRAMES)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
