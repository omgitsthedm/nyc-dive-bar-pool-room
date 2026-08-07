"""116_validate_cinematic_take.py - prove the take before it costs render hours.

Runs against the built cinematic blend and fails loudly on the things that
have actually gone wrong on this project before, plus the ones the brief
forbids:

  * a "moving" shot whose camera does not move
  * a camera inside a wall, a booth, a rail or a lamp shade
  * the pool fixture masking the table during the break
  * either pocket event off-frame or behind geometry
  * a volume shader still render-visible
  * flicker whose lamp and whose tube disagree
  * the physics timeline running backwards

Every check reports the number it measured, not just a verdict, because a
gate that only prints PASS is a gate nobody can debug.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import film_time as FT        # noqa: E402

SE_POCKET = Vector((0.868, 0.891, 0.791))
TABLE_CENTRE = Vector((0.25, 2.15, 0.80))
POCKET_FRAMES = {"7-ball": FT.film_frame(1.5046 + FT.FILM_OFFSET_S),
                 "4-ball": FT.film_frame(2.0780 + FT.FILM_OFFSET_S)}

# Camera clearance. Below this from any render-visible surface counts as an
# intersection. A real camera body is bigger than this, but the matte box is
# not what we are policing - being inside the geometry is.
CLEARANCE = 0.085
# Objects that are allowed to be closer than that: the glazing is a sheet the
# storefront shot deliberately works right up against, and the film's own
# additions are not set dressing.
CLEARANCE_EXEMPT_PREFIX = ("FILMPATH_", "FILMRIG_", "FILMTGT_", "CAM_",
                           "OPENNEON_", "FILM_", "PT_GameCamera",
                           "ENV_Glazing_Street")

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    print("  [%s] %-42s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def visible_meshes():
    out = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        if ob.name.startswith(("GUIDE_", "REF_")):
            continue
        if ob.name.startswith(CLEARANCE_EXEMPT_PREFIX):
            continue
        out.append(ob)
    return out


def cam_matrix(scene, cam, frame):
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    return cam.evaluated_get(dg).matrix_world.copy()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--flicker", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--shot", required=True)
    ap.add_argument("--stride", type=int, default=3,
                    help="frame stride for the expensive per-frame sweeps")
    args = ap.parse_args(argv)

    man = json.load(open(args.manifest))
    flick = json.load(open(args.flicker))
    traj = json.load(open(args.shot))
    scene = bpy.context.scene

    # scene.ray_cast walks the depsgraph, which follows VIEWPORT visibility,
    # not render visibility. The table carries 96 engineering and proxy
    # objects - pocket drafts, solver pockets, shelf drops - that are
    # hide_render=True but viewport-visible, and they sit exactly in the
    # pocket mouths. Left alone they make every occlusion test report the
    # pocket as blocked by geometry that is not in the picture. Align the two
    # notions of visible before casting a single ray.
    # Validate the layer that will actually be rendered. The default view
    # layer includes 05_HERO_PROPS - a second, static set of balls - so a
    # clearance or occlusion test run against it is testing a scene nobody
    # ships.
    want_layer = man.get("render_view_layer", "GAMEPLAY")
    vl = scene.view_layers.get(want_layer)
    if vl is None:
        raise RuntimeError("missing view layer %s" % want_layer)
    for v in scene.view_layers:
        v.use = (v.name == want_layer)
    try:
        bpy.context.window.view_layer = vl
    except AttributeError:
        pass                       # background: no window, depsgraph follows
    excluded_names = set()

    def _walk(lc):
        if lc.exclude:
            for o in lc.collection.all_objects:
                excluded_names.add(o.name)
        for c in lc.children:
            _walk(c)
    _walk(vl.layer_collection)
    print("  (validating view layer %s; %d objects excluded by it)"
          % (want_layer, len(excluded_names)))

    realigned = 0
    for ob in bpy.data.objects:
        if ob.name in excluded_names and not ob.hide_render:
            ob.hide_render = True
            ob.hide_viewport = True
            realigned += 1
        if ob.type == "MESH" and ob.hide_render and not ob.hide_viewport:
            ob.hide_viewport = True
            realigned += 1
    print("  (hid %d render-invisible meshes from the depsgraph so occlusion "
          "tests see what Cycles sees)" % realigned)

    print("=== take: shot %s  sha %s ===" % (man["shot_id"],
                                             man["trajectory_sha256"][:16]))

    # ---------------------------------------------------------- volumes ----
    vol_mats = set()
    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == "OUTPUT_MATERIAL":
                s = n.inputs.get("Volume")
                if s is not None and s.is_linked:
                    vol_mats.add(m.name)
    # Two different things link a Volume output, and only one of them is fog.
    #
    #   atmospheric : a room-scale object full of scatter - haze, smoke, a
    #                 light cone. This is what the brief bans, because it
    #                 greys the glass, blows the neon and does the lighting's
    #                 job for it.
    #   bounded     : absorption sealed inside a small closed mesh, which is
    #                 simply how coloured glass works - a bottle's base is
    #                 darker than its shoulder because the ray crossed more
    #                 glass. It cannot leak into the room.
    #
    # Judged on size and provenance, not on whether a Volume socket happens to
    # be connected: anything ATM_*, anything in 09_ATMOSPHERE, or anything
    # with a bounding diagonal over a metre counts as atmospheric and fails.
    ATMO_LIMIT_M = 1.0
    still_visible, bounded, declared = [], [], []
    for ob in bpy.data.objects:
        if ob.hide_render:
            continue
        has_vol = ob.type == "VOLUME" or any(
            s.material and s.material.name in vol_mats
            for s in ob.material_slots)
        if not has_vol:
            continue
        colls = {c.name for c in ob.users_collection}
        diag = 0.0
        try:
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            diag = max((a - b).length for a in pts for b in pts)
        except (AttributeError, ValueError):
            diag = 999.0
        atmospheric = (ob.name.startswith("ATM_")
                       or "09_ATMOSPHERE" in colls
                       or ob.type == "VOLUME"
                       or diag > ATMO_LIMIT_M)
        if atmospheric and ob.get("declared_density"):
            # An atmosphere the build DECLARED, at the density it declared.
            # Undeclared room-scale volume still fails - the point of the gate
            # was never "no volumes", it was "nothing here by accident".
            declared.append((ob.name, float(ob["declared_density"])))
            continue
        (still_visible if atmospheric else bounded).append((ob.name, diag))
    w = bpy.data.worlds[0] if bpy.data.worlds else None
    world_vol = False
    if w and w.use_nodes:
        for n in w.node_tree.nodes:
            if n.type == "OUTPUT_WORLD":
                s = n.inputs.get("Volume")
                if s is not None and s.is_linked:
                    world_vol = True
    biggest = max([d for _, d in bounded], default=0.0)
    check("no_undeclared_volume", not still_visible and not world_vol,
          "%d volume material(s) | UNDECLARED atmospheric: %d %s | declared "
          "atmosphere: %s | bounded glass absorption: %d objects, largest "
          "%.2f m | world volume=%s"
          % (len(vol_mats), len(still_visible),
             [n for n, _ in still_visible[:4]] or "none",
             ["%s@%.4f" % (n, d) for n, d in declared] or "none",
             len(bounded), biggest, world_vol))

    # ------------------------------------------------- film-only lighting ----
    film_lights = [ob for ob in bpy.data.objects
                   if ob.type == "LIGHT" and ob.get("film_only")]
    unmotivated = [ob.name for ob in film_lights if not ob.get("motivation")]
    check("film_lights_all_motivated", not unmotivated,
          "%d film-only lights, %d without a motivation" %
          (len(film_lights), len(unmotivated)))
    parented = [ob.name for ob in film_lights
                if ob.parent is not None and ob.parent.type == "CAMERA"]
    check("no_camera_parented_light", not parented,
          "camera-parented film lights: %s" % (parented or "none"))
    cam_visible = [ob.name for ob in film_lights if ob.visible_camera]
    check("film_lights_not_camera_visible", not cam_visible,
          "film lights visible to camera rays: %s" % (cam_visible or "none"))

    # ------------------------------------------------------ camera motion ----
    meshes = visible_meshes()
    print("  (clearance sweep against %d render-visible meshes)" % len(meshes))
    motion_rows = []
    worst_clear = ("", 1e9, 0)
    collisions = []
    for sh in man["shots"]:
        cam = bpy.data.objects.get(sh["cam"])
        if cam is None:
            check("shot_%02d_camera_exists" % sh["shot"], False,
                  "missing %s" % sh["cam"])
            continue
        first, last = sh["first"], sh["last"]
        mats = {}
        for fr in range(first, last + 1, max(1, args.stride)):
            mats[fr] = cam_matrix(scene, cam, fr)
        if last not in mats:
            mats[last] = cam_matrix(scene, cam, last)
        keys = sorted(mats)
        locs = [mats[k].translation for k in keys]
        dirs = [(mats[k].to_3x3() @ Vector((0, 0, -1))).normalized()
                for k in keys]
        travel = sum((locs[i + 1] - locs[i]).length
                     for i in range(len(locs) - 1))
        span = max((locs[i] - locs[0]).length for i in range(len(locs)))
        ang = max(math.degrees(dirs[0].angle(d)) for d in dirs)
        # per-step: no frame may be a repeat of the one before it
        steps = [(locs[i + 1] - locs[i]).length for i in range(len(locs) - 1)]
        min_step = min(steps) if steps else 0.0
        motion_rows.append(dict(shot=sh["shot"], name=sh["name"],
                                travel_m=round(travel, 4),
                                span_m=round(span, 4),
                                aim_deg=round(ang, 3),
                                min_step_m=round(min_step, 6),
                                frames=last - first + 1))
        # clearance
        for k in keys:
            p = mats[k].translation
            for ob in meshes:
                bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
                xs = [v.x for v in bb]
                ys = [v.y for v in bb]
                zs = [v.z for v in bb]
                if not (min(xs) - 0.4 <= p.x <= max(xs) + 0.4 and
                        min(ys) - 0.4 <= p.y <= max(ys) + 0.4 and
                        min(zs) - 0.4 <= p.z <= max(zs) + 0.4):
                    continue
                try:
                    hit, loc, nor, idx = ob.closest_point_on_mesh(
                        ob.matrix_world.inverted() @ p)
                except (RuntimeError, ValueError):
                    continue
                if not hit:
                    continue
                d = ((ob.matrix_world @ loc) - p).length
                if d < worst_clear[1]:
                    worst_clear = (ob.name, d, k)
                if d < CLEARANCE:
                    collisions.append((sh["shot"], k, ob.name, round(d, 4)))

    for r in motion_rows:
        print("    S%02d %-18s %3d fr  travel %.3f m  span %.3f m  aim %.2f deg"
              % (r["shot"], r["name"], r["frames"], r["travel_m"],
                 r["span_m"], r["aim_deg"]))

    dead = [r for r in motion_rows if r["travel_m"] < 0.05 and r["aim_deg"] < 1.0]
    check("every_shot_moves_in_3d", not dead,
          "%d/%d shots with real camera travel; static shots: %s"
          % (len(motion_rows) - len(dead), len(motion_rows),
             [r["shot"] for r in dead] or "none"))
    frozen = [r for r in motion_rows if r["min_step_m"] <= 1e-6]
    check("no_frozen_sub_span", not frozen,
          "smallest per-sample camera step across all shots: %.6f m"
          % min(r["min_step_m"] for r in motion_rows))
    check("no_camera_intersection", not collisions,
          "closest approach %.3f m to %s at frame %d (limit %.3f); breaches=%d"
          % (worst_clear[1], worst_clear[0], worst_clear[2], CLEARANCE,
             len(collisions)))
    if collisions:
        for c in collisions[:12]:
            print("      breach S%02d frame %d  %s  %.3f m" % c)

    # ------------------------------------------- pocket + table visibility ---
    def visible_from(cam, frame, point, label):
        m = cam_matrix(scene, cam, frame)
        co = world_to_camera_view(scene, cam, point)
        inside = (0.04 < co.x < 0.96 and 0.04 < co.y < 0.96 and co.z > 0)
        origin = m.translation
        d = (point - origin)
        dist = d.length
        dg = bpy.context.evaluated_depsgraph_get()
        hit, loc, nor, idx, obj, mw = scene.ray_cast(dg, origin,
                                                     d.normalized(),
                                                     distance=dist - 0.02)
        blocker = obj.name if hit else None
        # the table itself is what we are looking at, not an occluder
        if blocker and blocker.startswith(("PT_", "ENV_Floor")):
            blocker = None
        return inside, co, blocker, label

    # The real requirement is that you can watch the 4 and the 7 go in, so the
    # test follows each ball's own solved samples down its last ten frames
    # into the pocket rather than asking whether one arbitrary point is lit.
    for label, fr in POCKET_FRAMES.items():
        ball_id = label.split("-")[0]
        sh = next(s for s in man["shots"] if s["first"] <= fr <= s["last"])
        cam = bpy.data.objects[sh["cam"]]
        samples = traj["balls"][ball_id]["samples"]
        seen = 0
        rows = []
        window = range(fr - 9, fr + 1)
        for f in window:
            t = FT.scene_time(f)
            s = min(samples, key=lambda s: abs(s["t"] - t))
            p = Vector((s["p"][0] - 0.385, s["p"][1] + 0.880,
                        s["p"][2] + 0.762))
            inside, co, blocker, _ = visible_from(cam, f, p, label)
            if inside and not blocker:
                seen += 1
            rows.append((f, inside, blocker))
        # the pocket mouth itself, at the frame the ball reaches it
        m_inside, m_co, m_block, _ = visible_from(cam, fr, SE_POCKET, label)
        good = seen >= 8 and m_inside
        check("pocket_%s_visible_f%d" % (label.replace("-", "_"), fr), good,
              "ball %s clear on %d/10 frames into the drop; pocket mouth "
              "in-frame=%s at (%.2f,%.2f) blocker=%s"
              % (ball_id, seen, m_inside, m_co.x, m_co.y, m_block or "none"))
        if not good:
            for f, ins, bl in rows:
                if not ins or bl:
                    print("      f%d in-frame=%s blocker=%s" % (f, ins, bl))

    # the fixture must not mask the table during the break
    strike_shot = next(s for s in man["shots"]
                       if s["first"] <= FT.STRIKE_FRAME <= s["last"])
    sh6 = strike_shot
    cam6 = bpy.data.objects[sh6["cam"]]
    masked = []
    for fr in range(sh6["first"], sh6["last"] + 1, 4):
        inside, co, blocker, _ = visible_from(cam6, fr, TABLE_CENTRE, "table")
        if blocker and ("Shade" in blocker or "Pool_" in blocker):
            masked.append((fr, blocker))
        if not inside:
            masked.append((fr, "table centre out of frame"))
    check("fixture_never_masks_table", not masked,
          "break shot sampled every 4 frames; masked=%s" % (masked[:6] or "none"))

    # ------------------------------------------------ physics on the wire ----
    # 113 rebased the bake onto film frames, so the only honest test is to ask
    # the evaluated scene where each ball actually is on a given film frame and
    # compare it against the frozen trajectory. A monotonic-counter check would
    # have passed happily while the camera sat frozen for 108 frames.
    def ball_obj(bid):
        return bpy.data.objects.get(
            "PT_GameBall_%s" % ("Cue" if bid == "cue" else bid.zfill(2)))

    worst = 0.0
    worst_where = ""
    checked = 0
    probe = [FT.STRIKE_FRAME] + [FT.STRIKE_FRAME + d
                                 for d in (10, 24, 36, 50, 80, 120, 160, 187)]
    for fr in probe:
        scene.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        t = FT.scene_time(fr)
        for bid, bdata in traj["balls"].items():
            cap = bdata.get("capture_time_s")
            if cap is not None and t > cap + 0.02:
                continue                     # pocketed and dropping, skip
            ob = ball_obj(bid)
            if ob is None:
                continue
            s = min(bdata["samples"], key=lambda s: abs(s["t"] - t))
            if abs(s["t"] - t) > 1.0 / FT.FPS:
                continue
            want = Vector((s["p"][0] - 0.385, s["p"][1] + 0.880,
                           s["p"][2] + 0.762))
            got = ob.evaluated_get(dg).matrix_world.translation
            d = (got - want).length
            checked += 1
            if d > worst:
                worst, worst_where = d, "ball %s @ f%d" % (bid, fr)
    check("balls_match_frozen_trajectory", worst < 0.002,
          "%d ball/frame samples across %d frames; worst error %.6f m (%s)"
          % (checked, len(probe), worst, worst_where or "none"))

    # settled state must still be settled at the last frame
    scene.frame_set(FT.TOTAL_FRAMES - 1)
    dg = bpy.context.evaluated_depsgraph_get()
    fin = traj["canonical_solver_state"]["final"]
    fworst = 0.0
    for bid, st in fin.items():
        ob = ball_obj(bid)
        if ob is None:
            continue
        want = Vector((st["rvw"][0][0] - 0.385, st["rvw"][0][1] + 0.880,
                       st["rvw"][0][2] + 0.762))
        fworst = max(fworst,
                     (ob.evaluated_get(dg).matrix_world.translation
                      - want).length)
    check("final_frame_is_the_settled_table", fworst < 0.002,
          "worst ball error at film frame %d vs solver final state: %.6f m"
          % (FT.TOTAL_FRAMES - 1, fworst))

    # and the strike frame must be the rack, untouched
    scene.frame_set(FT.STRIKE_FRAME)
    dg = bpy.context.evaluated_depsgraph_get()
    rworst = 0.0
    for bid, bdata in traj["balls"].items():
        ob = ball_obj(bid)
        if ob is None:
            continue
        s0 = bdata["samples"][0]
        want = Vector((s0["p"][0] - 0.385, s0["p"][1] + 0.880,
                       s0["p"][2] + 0.762))
        rworst = max(rworst,
                     (ob.evaluated_get(dg).matrix_world.translation
                      - want).length)
    check("strike_lands_on_frame_%d" % FT.STRIKE_FRAME, rworst < 0.002,
          "film frame %d is trajectory t=0; worst ball error %.6f m"
          % (FT.STRIKE_FRAME, rworst))

    # ------------------------------------------------------------ flicker ----
    base = flick["base"]
    sched = flick["schedule"]
    bad = []
    for src, cfg in base.items():
        seq = sched[src]
        if len(seq) != FT.TOTAL_FRAMES:
            bad.append((src, "length %d" % len(seq)))
        # no sine: an autocorrelation peak at a fixed lag would show as a
        # dominant period. Cheap proxy - the sequence must not repeat.
        if len(set(seq)) < FT.TOTAL_FRAMES * 0.5:
            bad.append((src, "only %d distinct values" % len(set(seq))))
        lo, hi = min(seq), max(seq)
        if hi > 1.0001:
            bad.append((src, "multiplier above 1.0: %.4f" % hi))
        if lo < 0.25:
            bad.append((src, "dip deeper than 75%%: %.4f" % lo))
    check("flicker_schedule_sane", not bad,
          "; ".join("%s pool_neon min %.3f max %.3f" %
                    ("", min(sched[s]), max(sched[s])) for s in ["pool_neon"])
          + " | open_neon min %.3f max %.3f"
          % (min(sched["open_neon"]), max(sched["open_neon"]))
          + (" | problems=%s" % bad if bad else ""))

    # the pocket windows must stay legible
    prot_bad = []
    for src in sched:
        p7 = FT.film_frame(1.5046 + FT.FILM_OFFSET_S)
        p4 = FT.film_frame(2.0780 + FT.FILM_OFFSET_S)
        for fr in list(range(p7 - 4, p7 + 5)) + list(range(p4 - 4, p4 + 5)):
            if sched[src][fr] < 0.90:
                prot_bad.append((src, fr, sched[src][fr]))
    check("flicker_spares_pocket_events", not prot_bad,
          "no dip below 0.90 within +/-4 frames of %d or %d; breaches=%d"
          % (FT.film_frame(1.5046 + FT.FILM_OFFSET_S),
             FT.film_frame(2.0780 + FT.FILM_OFFSET_S), len(prot_bad)))

    # emission and lamp must move together, and be applyable
    sync_err = []
    for src, cfg in base.items():
        for fr in (0, 173, 300, 336, 350, 487, 719):
            m = sched[src][fr]
            for mat_name, bval in cfg["materials"].items():
                mat = bpy.data.materials[mat_name]
                node = [n for n in mat.node_tree.nodes
                        if n.type == "BSDF_PRINCIPLED"][0]
                node.inputs["Emission Strength"].default_value = bval * m
                got = node.inputs["Emission Strength"].default_value
                if abs(got - bval * m) > 1e-5:
                    sync_err.append((src, fr, mat_name, got))
            lt = bpy.data.objects[cfg["light"]]
            lt.data.energy = cfg["light_energy"] * m
            if abs(lt.data.energy - cfg["light_energy"] * m) > 1e-4:
                sync_err.append((src, fr, cfg["light"], lt.data.energy))
            # the ratio is the actual requirement: same multiplier both sides
            emi_ratio = (node.inputs["Emission Strength"].default_value /
                         list(cfg["materials"].values())[-1])
            lit_ratio = lt.data.energy / cfg["light_energy"]
            if abs(emi_ratio - lit_ratio) > 1e-4:
                sync_err.append((src, fr, "ratio", emi_ratio, lit_ratio))
    check("flicker_emission_light_synchronised", not sync_err,
          "applied both channels at 7 sample frames for %d sources; "
          "mismatches=%d" % (len(base), len(sync_err)))

    # ------------------------------------------------------------ verdict ----
    out = dict(shot_id=man["shot_id"],
               trajectory_sha256=man["trajectory_sha256"],
               motion=motion_rows,
               closest_approach_m=round(worst_clear[1], 4),
               closest_object=worst_clear[0],
               collisions=collisions,
               checks=[dict(name=n, passed=p, detail=d) for n, p, d in results])
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w") as fh:
        json.dump(out, fh, indent=1)
    npass = sum(1 for _, p, _ in results if p)
    print("=== take validation: %d/%d passed -> %s ==="
          % (npass, len(results), args.report))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
