"""113_build_cinematic_take.py - build the cinematic take: rigs, light, flicker.

Reads blend/poolroom_gameplay_preview.blend (the baked b_51 playback), adds a
film-only layer on top of it, and saves the result somewhere local. It never
writes back over a locked blend, so the environment, the table, the physics
and the audit cameras are all exactly what the locks banked.

WHAT THIS ADDS, AND WHY EACH PIECE EXISTS

1. Ten camera rigs, one per shot. Each is a real Bezier path, a rig Empty
   pulled along it by a Follow Path constraint, a separate target Empty, and
   a camera parented to the rig and aimed by a Track To constraint. Every
   final frame therefore comes from a camera that is somewhere different from
   where it was on the frame before. The film this replaces rendered one
   frame per static shot and copied it up to forty-five times.

   The aim constraint is Track To rather than Damped Track. Damped Track
   preserves whatever roll the object already has and takes the shortest
   rotation to the target, which on a craning rig lets the horizon tip a
   degree or two per frame for no reason. Track To with up_axis='UP_Y' pins
   the horizon to world Z, which is what a real crane head does.

2. Every volume hidden. ATM_RoomHaze_Volume and ATM_PoolBeam_Volume both go
   to hide_render=True and stay there. The gallery stills were rendered with
   the room haze on and volume_bounces>=2, and that haze was carrying about a
   stop of the room's light, so hiding it is not free - see 3.

3. Film-only motivated lights. Each one sits on a fixture that is actually
   visible in the room, is tagged with film_only=True and a motivation naming
   that fixture, and is set visible_camera=False so it contributes light
   without appearing as a floating white rectangle. There is no world fill,
   no frontal key and no camera-parented light, because the brief forbids
   them and because they are what makes a room look unlit-but-brightened.

4. The OPEN sign's missing neon. The storefront sign is four blackened-steel
   frame bars and an area light, and the scene already carries an unused
   MAT_Prop_NeonBlue whose colour matches that light almost exactly. The
   letters were specified and never built. This adds them inside the existing
   frame, in that existing material, so there is a visible emissive source to
   flicker - requirement 11 needs the tube and the lamp to move together, and
   you cannot flicker a tube that does not exist.

5. A deterministic flicker schedule, seeded from the frozen trajectory's
   SHA-256, written out as JSON and CSV. 114 applies it; 116 recomputes it
   from the same seed and reads the applied values back out of the blend.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C            # noqa: E402
import film_time as FT        # noqa: E402

SHOT_JSON = os.path.join(C.ROOT, "assets", "data", "shots", "break_film.json")

# ---------------------------------------------------------------- geometry --
# Measured out of the blend, not guessed. Every number below was read back
# with a bounding-box pass before a camera was placed near it.
TABLE_CX, TABLE_CY = 0.25, 2.15        # play-area centre
BED_Z = 0.762                          # cloth
RAIL = (-0.53, 0.74, 1.02, 3.56)       # xmin ymin xmax ymax of the rail body
SE_POCKET = (0.868, 0.891, 0.791)      # where the 7 and then the 4 drop
FIXTURE_X = (0.01, 0.48)               # the three shades are narrow in x ...
FIXTURE_Z = (1.78, 1.96)               # ... and hang here
CEILING_Z = 3.15
WATER_STAIN = (2.135, 4.575, 3.13)


# --------------------------------------------------------------- shot plan --
# start_s/end_s are film seconds. `path` is the Bezier control polygon the rig
# travels along; `target` is the aim empty's keyframed path, as
# (fraction_through_shot, x, y, z). `noise` turns on the tiny handheld offset.
SHOTS = [
    dict(
        n=1, name="StorefrontNewYork", start_s=0.000, end_s=5.500, lens=35.0,
        fstop=4.0,
        why="the diamond lattice, the OPEN sign read backwards from inside, "
            "and the wet Lower East Side street moving behind it",
        # A slow lateral drift, not a push. At 0.010 m/frame the street
        # parallaxes through the lattice diamonds and the reflections travel
        # across the wet asphalt, which is the only thing that tells you the
        # window has real depth behind it. The exterior is a backdrop plane
        # 0.37 m beyond the glazing, so there is nothing to fly into - the
        # move has to work sideways.
        # Anchored on CAM_Audit_StreetNeon_35mm's proven standoff, which is
        # the framing published still 01 was shot from: far enough back that
        # the lattice, the wet street behind it and the sign all coexist. The
        # previous version drifted in to 1.3 m and the sign filled the frame
        # with the city cropped off the side - the one thing the shot exists
        # to show. The aim starts on the street and settles onto the sign.
        path=[(1.18, -3.00, 1.63), (0.96, -3.11, 1.60),
              (0.74, -3.22, 1.57), (0.52, -3.33, 1.545),
              (0.30, -3.44, 1.52)],
        target=[(0.00, -0.45, -5.79, 1.50), (0.55, -0.85, -5.79, 1.62),
                (1.00, -1.25, -5.79, 1.74)],
        noise=True, ease="inout",
    ),
    dict(
        n=2, name="BarGlide", start_s=5.500, end_s=10.500, lens=40.0,
        fstop=8.0,
        why="the length of the back bar: 213 bottles, the barrel-front "
            "register, and the fluorescent sections that stop either side of "
            "it",
        # 1.30 m over 120 frames, not 2.40. At the old rate the foreground
        # bar top swept 34 px a frame - about 800 px/s - and a 24 fps frame
        # cannot hold that without juddering.
        path=[(-0.21, -3.62, 1.373), (-0.22, -3.44, 1.371),
              (-0.23, -3.27, 1.370), (-0.235, -3.09, 1.368),
              (-0.24, -2.92, 1.367)],
        target=[(0.00, -2.95, -3.60, 1.30), (0.50, -2.97, -3.12, 1.31),
                (1.00, -2.95, -2.62, 1.32)],
        noise=True, ease="inout",
    ),
    dict(
        n=3, name="Glassware", start_s=10.500, end_s=14.500, lens=55.0,
        fstop=5.0,
        why="low along the bar top past a pint with a foam head and "
            "condensation on the glass, and a rocks cocktail on its coaster",
        # The drinks were always here - PATRON_* carries beer, foam,
        # condensation and cocktails. They read as empty glasses until the bar
        # pendants were given something to throw.
        # This shot was the one that read as flicker. A 70 mm sitting 0.75 m
        # off the glass, travelling 2 cm a frame, moves the picture 69 px per
        # frame - 1654 px/s, well past where 24 fps strobes. Three changes,
        # all in the same direction: 0.60 m of travel instead of 1.95, nearly
        # a metre of standoff instead of 0.75, and 55 mm instead of 70. That
        # is 320 px/s, and the parallax across the coaster and the fruit bowl
        # still reads because the subject is close.
        path=[(-0.42, -3.68, 1.188), (-0.43, -3.57, 1.186),
              (-0.44, -3.47, 1.184), (-0.445, -3.36, 1.182),
              (-0.45, -3.26, 1.180)],
        # The aim drifts along the bar rather than panning down it: 0.90 m of
        # target travel, not 1.89. Translation was only half the story - a
        # 68 degree pan on a 55 mm moves the picture faster than the dolly
        # does, and it was the pan that survived the first correction.
        target=[(0.00, -1.35, -3.78, 1.128), (0.55, -1.34, -3.47, 1.118),
                (1.00, -1.35, -3.20, 1.122)],
        noise=True, ease="inout",
    ),
    dict(
        n=4, name="ToTheTable", start_s=14.500, end_s=19.000, lens=35.0,
        fstop=5.6,
        why="off the room and down onto the fixture, the cloth and the racked "
            "balls - the last thing before the cue moves",
        path=[(1.85, -0.40, 1.70), (1.78, 0.22, 1.60),
              (1.70, 0.90, 1.50), (1.62, 1.45, 1.39),
              (1.55, 1.95, 1.30)],
        target=[(0.00, 0.30, 2.20, 1.30), (0.55, 0.28, 2.10, 0.95),
                (1.00, TABLE_CX, 2.30, BED_Z + 0.04)],
        noise=False, ease="inout",
    ),
    dict(
        n=5, name="BreakAndPockets", start_s=19.000, end_s=23.000, lens=26.0,
        fstop=5.6,
        why="the strike, in real time, drifting down the east side so the "
            "south-east corner - where the 7 and then the 4 drop - is never "
            "out of frame",
        path=[(1.86, 2.80, 2.00), (1.87, 2.35, 1.98),
              (1.88, 1.90, 1.96), (1.87, 1.42, 1.93),
              (1.86, 0.95, 1.90)],
        # The 7 drops at 37.5% through this shot and the 4 at 52%, so the aim
        # is already on the south-east corner by 32% and stays there through
        # both. Aimed at the table centre the drop sat 13% from the frame
        # edge - in shot, but not something you could point at.
        # Aimed north of the pocket, not at it. Parked directly on the mouth
        # the table slid into the right half of frame and the left half was
        # bare floor; this keeps the cloth filling the picture with the
        # south-east corner sitting low and right, where a pocket belongs.
        target=[(0.00, TABLE_CX, 2.40, BED_Z), (0.20, 0.36, 2.00, BED_Z),
                (0.36, 0.55, 1.52, BED_Z), (0.60, 0.58, 1.44, BED_Z),
                (1.00, 0.45, 1.60, BED_Z)],
        noise=False, ease="linearish",
    ),
    dict(
        n=6, name="RailAndLastBall", start_s=23.000, end_s=26.806, lens=60.0,
        fstop=4.0,
        why="low along the east rail while the table is still working, "
            "following the 13 - the last thing moving anywhere - until it "
            "gives up",
        # 0.90 m over 91 frames, not 1.60 - the 13 is close to the lens on a
        # 60 mm and the old rate ran at 843 px/s.
        path=[(1.40, 1.45, 0.95), (1.41, 1.67, 0.957),
              (1.42, 1.90, 0.965), (1.43, 2.12, 0.972),
              (1.44, 2.35, 0.98)],
        target=None,
        track_ball="13",
        noise=True, ease="inout",
    ),
    dict(
        n=7, name="SettleAndPullback", start_s=26.806, end_s=30.000,
        lens=24.0, fstop=8.0,
        why="rise away and open out down the length of the room - fixture, "
            "table, booths, bar, and the lit storefront at the far end",
        path=[(1.72, 3.05, 1.68), (1.86, 3.34, 1.79),
              (2.01, 3.62, 1.90), (2.16, 3.91, 2.00),
              (2.30, 4.20, 2.10)],
        target=[(0.00, TABLE_CX, 2.15, BED_Z + 0.04),
                (0.50, 0.05, 0.70, 1.00),
                (1.00, -0.20, -0.90, 1.25)],
        noise=False, ease="inout",
    ),
]


# ------------------------------------------------------------------ helpers --
def log(msg):
    print("  [take] %s" % msg)


def fcurves_of(ob):
    """Every F-curve on an object, across Blender's two Action layouts.

    Blender 5.x actions are slotted: the curves live in
    action.layers[].strips[].channelbags[].fcurves and Action.fcurves is gone.
    Keeping the old path as a fallback costs one hasattr and means this file
    still runs against a 4.x Blender if anyone points one at it.
    """
    if ob.animation_data is None or ob.animation_data.action is None:
        return []
    act = ob.animation_data.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out.extend(cb.fcurves)
    return out


def shot_frames(s):
    """-> (first_frame, last_frame) inclusive, global film numbering"""
    return FT.film_frame(s["start_s"]), FT.film_frame(s["end_s"]) - 1


def purge_previous():
    """Remove anything this script made last time, so it is re-runnable."""
    killed = 0
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("CINE_", "FILMPATH_", "FILMRIG_", "FILMTGT_",
                               "CAM_Cine_", "FILM_", "OPENNEON_")):
            bpy.data.objects.remove(ob, do_unlink=True)
            killed += 1
    for cu in list(bpy.data.curves):
        if cu.name.startswith("FILMPATH_"):
            bpy.data.curves.remove(cu)
    for col in list(bpy.data.collections):
        if col.name.startswith("12_FILM"):
            bpy.data.collections.remove(col)
    if killed:
        log("purged %d objects from a previous build" % killed)


def rebase_gameplay_to_film_time(scene):
    """Slide the baked playback onto the film timeline so there is one clock.

    THE BUG THIS FIXES. The camera rigs are keyed on film frames 0..719. The
    bake is keyed on frames 1..219. Rendering used to set the scene to the
    clamped baked frame, which is right for the balls and wrong for the
    cameras: for every film frame after 518 the scene sat on frame 219, the
    rigs evaluated outside their keyed range, and the camera froze at
    whichever end of its path it started from. Frames 612 and 719 came out
    byte-identical while the validator - which sampled the rigs at FILM
    frames - happily reported 2.29 m of travel.

    Two timelines cannot both be the scene frame, so the bake moves. The
    shift is STRIKE_FRAME minus the bake's impact frame, and the impact frame
    is READ FROM THE PROFILE rather than assumed: pool_physics_profile.json
    sets impact_frame = 30.0, so trajectory t=0 lives on baked frame 30 and
    the 29 frames before it carry the cue's wind-up.

    Assuming baked frame 1 was t=0 - which looks reasonable, because
    frame_start IS 1 - shifted everything by 29 frames. It survived a
    surprising amount of checking: frame 300 still showed the rack, because
    the pre-roll holds the rack, and the last frame still showed the settled
    table, because the keys run out and extrapolate flat. Only a mid-flight
    ball position gave it away, off by 2.11 m.

    A happy consequence of getting it right: baked frames 1..29 land on film
    271..299, so the cue-address shot now runs over the actual wind-up.
    """
    prof = json.load(open(os.path.join(C.ROOT, "assets", "data",
                                       "pool_physics_profile.json")))
    impact_frame = int(round(float(prof["playback"]["impact_frame"])))
    shift = FT.STRIKE_FRAME - impact_frame               # 300 - 30 = 270
    moved = keys = 0
    for ob in bpy.data.objects:
        if ob.animation_data is None or ob.animation_data.action is None:
            continue
        if not ob.name.startswith(("PT_Game",)):
            continue
        curves = fcurves_of(ob)
        if not curves:
            continue
        for fcu in curves:
            for kp in fcu.keyframe_points:
                kp.co.x += shift
                kp.handle_left.x += shift
                kp.handle_right.x += shift
                keys += 1
            fcu.extrapolation = "CONSTANT"
            fcu.update()
        moved += 1
    log("rebased %d gameplay objects (%d keyframes) by +%d frames: bake "
        "impact_frame %d -> film %d (the strike); baked %d..%d -> film "
        "%d..%d, held constant either side"
        % (moved, keys, shift, impact_frame, FT.STRIKE_FRAME,
           scene.frame_start, scene.frame_end,
           scene.frame_start + shift, scene.frame_end + shift))
    scene.frame_start = 0
    scene.frame_end = FT.TOTAL_FRAMES - 1
    return shift, moved, keys, impact_frame



def select_gameplay_view_layer(scene):
    """Render the GAMEPLAY view layer, not the default one.

    THE BUG THIS FIXES. This scene carries two complete sets of balls: the
    static hero props in 05_HERO_PROPS, which is what the environment stills
    were shot with, and the solver-driven PT_GameBall_* in 11_GAMEPLAY. The
    GAMEPLAY view layer exists precisely to exclude the first set (and the
    solver proxies in 10_PHYSICS_PROXIES); the default ViewLayer includes
    everything.

    Rendering the default layer put both sets on the table at once. In the
    rack they sit on top of each other and you cannot tell, which is why it
    survived a benchmark and a validation pass - but the two cue balls are
    9 cm apart and render as two white balls, and once the break starts the
    static set stays frozen in a rack while the solved set scatters through
    it. A ghost rack, for the whole shot the film exists to show.

    pool_physics_profile.json has named this layer "GAMEPLAY" all along.
    """
    prof_name = "GAMEPLAY"
    want = scene.view_layers.get(prof_name)
    if want is None:
        raise RuntimeError("no %s view layer - the gameplay/hero split this "
                           "scene depends on is missing" % prof_name)
    kept = []
    for vl in scene.view_layers:
        vl.use = (vl.name == prof_name)
        if vl.use:
            kept.append(vl.name)
    excluded = []
    def walk(lc):
        if lc.exclude:
            excluded.append(lc.name)
        for c in lc.children:
            walk(c)
    walk(want.layer_collection)
    log("render view layer -> %s (excludes %s); other layers disabled"
        % (kept, sorted(excluded)))
    return prof_name, sorted(excluded)


def get_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def hide_cap_horns():
    """Hide PT_CapHorn_* - they are the V protruding from the rail.

    Isolated by rendering the same pocket with each candidate hidden: drop the
    horns and the wedges go; drop the cushions and they stay. The horns are
    wood pieces meant to carry the finished rail top past the cushion terminal
    down to the pocket iron, but their inner edge is offset by the jaw band
    flared out to the welt ring rather than by the rail's covered width, so at
    full cap height each one overhangs the mouth as a thin spike aimed at the
    playfield. All six pockets, all twelve horns.

    This hides them for the film only. The real repair belongs in
    20_build_pool_table.py - build_cap_horns' inner edge should follow
    CUSHION_COVERED_W, not `band` - but that rebuilds the table, which means
    re-banking the pool-system lock and re-baking the playback, and the
    trajectory is frozen. Hiding costs nothing, touches no locked blend, and
    the mouth reads better without them: rail sweeps clean into the welt and
    the cushion facings sit flat where they should.
    """
    hidden = [o for o in bpy.data.objects if o.name.startswith("PT_CapHorn_")]
    for ob in hidden:
        ob.hide_render = True
        ob.hide_viewport = True
    log("cap horns hidden for the film: %d (the protruding pocket V)"
        % len(hidden))
    return sorted(o.name for o in hidden)


def kill_all_volumes():
    """Every volume off, and prove it by listing what was found."""
    vol_mats = set()
    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == "OUTPUT_MATERIAL":
                sock = n.inputs.get("Volume")
                if sock is not None and sock.is_linked:
                    vol_mats.add(m.name)
    hidden = []
    for ob in bpy.data.objects:
        uses = [s.material.name for s in ob.material_slots
                if s.material and s.material.name in vol_mats]
        if uses or ob.type == "VOLUME":
            ob.hide_render = True
            ob.hide_viewport = True
            hidden.append(ob.name)
    log("volume materials in file: %s" % sorted(vol_mats))
    log("volume objects forced hide_render=True: %s" % sorted(hidden))
    return sorted(vol_mats), sorted(hidden)


# ------------------------------------------------------- the OPEN sign neon --
def isolate_open_neon_N(col):
    """Give the OPEN sign's N its own material so one section can fail alone.

    THE MISTAKE THIS REPLACES. An earlier version of this file BUILT a set of
    neon letters here, because a survey of the scene reported MAT_Prop_NeonBlue
    with zero users and no letter objects. That survey filtered on
    `o.type == 'MESH'`. The letters are CURVES - LGT_NeonWindowOpen_O, _P_0..4,
    _E_0..3, _N_0..2, bevelled curve tubes, exactly as you would model neon -
    so they were invisible to the query and I concluded they did not exist.

    Fifteen crude cylinders then got built directly on top of fifteen real
    letters, which is why the sign rendered as an unreadable tangle. The real
    letters were always there and always correct.

    All that is needed is to split the N onto its own copy of its material so
    it can flicker without dragging the 8-ball sign - which shares
    MAT_Prop_NeonGreen - along with it.
    """
    targets = [bpy.data.objects.get("LGT_NeonWindowOpen_N_%d" % i)
               for i in range(3)]
    targets = [o for o in targets if o is not None]
    if not targets:
        raise RuntimeError("LGT_NeonWindowOpen_N_* missing - the storefront "
                           "sign's N is what flickers")
    src = None
    for slot in targets[0].material_slots:
        if slot.material:
            src = slot.material
            break
    if src is None:
        raise RuntimeError("the OPEN sign's N has no material")
    mat = bpy.data.materials.get("MAT_OpenNeon_N_film")
    if mat is None:
        mat = src.copy()
        mat.name = "MAT_OpenNeon_N_film"
    for ob in targets:
        for i, slot in enumerate(ob.material_slots):
            if slot.material == src:
                slot.material = mat
    log("OPEN sign: N section (%d curves) split onto %s from %s; O/P/E "
        "untouched" % (len(targets), mat.name, src.name))
    return [o.name for o in targets], mat.name, src.name


# ------------------------------------------------------- motivated lighting --
# Each entry: name, type, energy, colour, size, location, rotation, motivation.
# Rotations aim an area light's -Z at where the fixture actually throws.
FILM_LIGHTS = [
    dict(name="FILM_PoolFixture_Bounce", energy=30.0, color=(1.0, 0.90, 0.78),
         size=(1.55, 2.95), loc=(TABLE_CX, TABLE_CY, 1.735), rot=(0, 0, 0),
         motivation="LGT_Pool_Shade_0/1/2 + LGT_Pool_ShadeInner_0/1/2"),
    # The enamel shades are open-bottomed, but their white inners and the
    # cloth below them throw a soft glow onto the tin. Cycles does resolve
    # that bounce - at 8 spp with adaptive sampling it resolves it as noise.
    # This stands in for it so the ceiling the crane passes through is not a
    # black band, and it is motivated by the same three shades as the key.
    dict(name="FILM_PoolFixture_UpWash", energy=13.0, color=(1.0, 0.88, 0.74),
         size=(1.20, 2.60), loc=(TABLE_CX, TABLE_CY, 2.02),
         rot=(math.pi, 0.0, 0.0),
         motivation="LGT_Pool_Shade_0/1/2 (enamel inners, upward spill)"),
    dict(name="FILM_BackBar_Fluoro_S", energy=26.0, color=(1.0, 0.82, 0.60),
         size=(1.34, 0.09), loc=(-2.79, -3.65, 1.095),
         rot=(math.pi / 2, 0.0, math.pi / 2),
         motivation="LGT_BackBar_FluorescentTube_S"),
    dict(name="FILM_BackBar_Fluoro_N", energy=24.0, color=(1.0, 0.82, 0.60),
         size=(1.34, 0.09), loc=(-2.79, -1.45, 1.095),
         rot=(math.pi / 2, 0.0, math.pi / 2),
         motivation="LGT_BackBar_FluorescentTube_N"),
    dict(name="FILM_Storefront_StreetSpill", energy=45.0,
         color=(0.55, 0.78, 1.0), size=(4.30, 1.70), loc=(-0.45, -5.70, 1.55),
         rot=(math.pi / 2, 0.0, 0.0), motivation="ENV_Glazing_Street"),
    dict(name="FILM_OpenNeon_Spill", energy=14.0, color=(0.16, 0.55, 1.0),
         size=(1.28, 0.52), loc=(-1.28, -5.68, 1.85),
         rot=(math.pi / 2, 0.0, 0.0),
         motivation="LGT_NeonWindowOpen_O/P/E/N + frame"),
    dict(name="FILM_CRT_Spill", energy=4.5, color=(0.42, 0.62, 0.92),
         size=(0.54, 0.31), loc=(-2.73, 4.05, 2.43),
         rot=(math.pi / 2, 0.0, -math.pi / 2),
         motivation="PROP_CRT_Screen"),
    dict(name="FILM_Restroom_Cool", energy=34.0, color=(0.76, 0.85, 1.0),
         size=(0.85, 0.85), loc=(1.86, 5.32, 2.02),
         rot=(-math.pi / 2, 0.0, 0.0),
         motivation="LGT_BathroomDoor_Bulb (MAT_Fixture_CoolBulb)"),

    # ---- the practicals that light the ROOM, not the hero surfaces -------
    # These were missing, and their absence is the whole "why is the bar so
    # dark" note. The gallery stills were rendered with ATM_RoomHaze_Volume
    # on at volume_bounces>=2, and that haze was not just atmosphere - it was
    # carrying roughly a stop of soft in-scattered light into the booths, the
    # wheatpaste walls and the cafe tables. The brief requires the fog gone,
    # so every surface it was quietly lighting now needs its own visible
    # source, and every one of these sits on a fixture already in the room.
    #
    # POINT, not AREA, for the sconces: a bare bulb in a wall sconce throws
    # onto the wall behind it as well as into the room, which is what makes a
    # booth feel like somewhere you would actually sit down.
    dict(name="FILM_EastSconce_0", kind="POINT", energy=26.0,
         color=(1.0, 0.60, 0.32), radius=0.09, loc=(2.94, 0.45, 2.15),
         motivation="LGT_EastSconce_0"),
    dict(name="FILM_EastSconce_1", kind="POINT", energy=28.0,
         color=(1.0, 0.62, 0.32), radius=0.09, loc=(2.94, 3.42, 2.15),
         motivation="LGT_EastSconce_1"),
    dict(name="FILM_RearSconce_0", kind="POINT", energy=26.0,
         color=(1.0, 0.64, 0.36), radius=0.09, loc=(-2.35, 5.42, 2.13),
         motivation="LGT_RearSconce_0"),
    dict(name="FILM_RearSconce_1", kind="POINT", energy=28.0,
         color=(1.0, 0.66, 0.36), radius=0.09, loc=(2.25, 5.42, 2.13),
         motivation="LGT_RearSconce_1"),
    dict(name="FILM_Cafe_Practical", kind="POINT", energy=30.0,
         color=(1.0, 0.62, 0.32), radius=0.08, loc=(2.44, -2.62, 2.32),
         motivation="LGT_Cafe_Practical"),
    dict(name="FILM_Entry_Practical", kind="POINT", energy=26.0,
         color=(1.0, 0.68, 0.38), radius=0.08, loc=(1.92, -4.72, 2.58),
         motivation="LGT_Entry_Practical"),

    # Booth pendants: down onto the tables, so the drinks on them read as
    # drinks. The glassware was never missing - PATRON_* carries beer, foam,
    # condensation and cocktails, all render-visible - it was just unlit.
    dict(name="FILM_BoothPendant_0", energy=24.0, color=(1.0, 0.64, 0.34),
         size=(0.85, 0.85), loc=(-2.71, 1.52, 1.98), rot=(0, 0, 0),
         motivation="LGT_BoothPendant_Practical_0 + LGT_BoothPendant_Shade_0"),
    dict(name="FILM_BoothPendant_1", energy=22.0, color=(1.0, 0.64, 0.34),
         size=(0.85, 0.85), loc=(-2.71, 3.25, 1.94), rot=(0, 0, 0),
         motivation="LGT_BoothPendant_Practical_1 + LGT_BoothPendant_Shade_1"),

    # Bar pendants: the pints and the rocks glass sitting on BAR_Top.
    dict(name="FILM_BarPendant_0", energy=17.0, color=(1.0, 0.72, 0.44),
         size=(0.55, 0.55), loc=(-1.58, -3.50, 1.79), rot=(0, 0, 0),
         motivation="LGT_BarPendant_Shade_0"),
    dict(name="FILM_BarPendant_1", energy=17.0, color=(1.0, 0.73, 0.44),
         size=(0.55, 0.55), loc=(-1.58, -2.55, 1.82), rot=(0, 0, 0),
         motivation="LGT_BarPendant_Shade_1"),
    dict(name="FILM_BarPendant_2", energy=17.0, color=(1.0, 0.75, 0.44),
         size=(0.55, 0.55), loc=(-1.58, -1.60, 1.81), rot=(0, 0, 0),
         motivation="LGT_BarPendant_Shade_2"),
]


def build_film_lights(col, scale=1.0):
    made = []
    for spec in FILM_LIGHTS:
        kind = spec.get("kind", "AREA")
        data = bpy.data.lights.new(spec["name"], type=kind)
        if kind == "AREA":
            data.shape = "RECTANGLE"
            data.size, data.size_y = spec["size"]
        else:
            data.shadow_soft_size = spec.get("radius", 0.05)
        data.energy = spec["energy"] * scale
        data.color = spec["color"]
        ob = bpy.data.objects.new(spec["name"], data)
        ob.location = spec["loc"]
        ob.rotation_euler = spec.get("rot", (0.0, 0.0, 0.0))
        col.objects.link(ob)
        # Contributes light, never appears as a glowing rectangle in frame.
        ob.visible_camera = False
        ob["film_only"] = True
        ob["motivation"] = spec["motivation"]
        made.append(ob.name)
    log("film-only motivated lights: %d (scale %.2f)" % (len(made), scale))
    return made


# ------------------------------------------------------------------- rigs ----
def make_path(shot, col):
    first, last = shot_frames(shot)
    cu = bpy.data.curves.new("FILMPATH_S%02d" % shot["n"], type="CURVE")
    cu.dimensions = "3D"
    cu.use_path = True
    # path_duration only matters for the legacy eval_time route; we drive
    # offset_factor directly so the value here is cosmetic.
    cu.path_duration = max(1, last - first + 1)
    spline = cu.splines.new("BEZIER")
    pts = shot["path"]
    spline.bezier_points.add(len(pts) - 1)
    for bp, p in zip(spline.bezier_points, pts):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("FILMPATH_S%02d" % shot["n"], cu)
    col.objects.link(ob)
    ob.hide_render = True
    return ob


EASE = {
    # (right handle of the first key, left handle of the last key) as a
    # fraction of the shot length. Bigger = slower into/out of that end.
    "out":      (0.05, 0.55),
    "inout":    (0.42, 0.42),
    "linearish": (0.18, 0.18),
}


def key_offset(rig, first, last, ease):
    """Animate the Follow Path offset_factor 0 -> 1 with real Bezier easing."""
    con = rig.constraints["Follow Path"]
    con.offset_factor = 0.0
    con.keyframe_insert("offset_factor", frame=first)
    con.offset_factor = 1.0
    con.keyframe_insert("offset_factor", frame=last)
    fcu = None
    for f in fcurves_of(rig):
        if f.data_path.endswith("offset_factor"):
            fcu = f
    if fcu is None:
        raise RuntimeError("no offset_factor curve on %s" % rig.name)
    span = max(1, last - first)
    a, b = EASE[ease]
    k0, k1 = fcu.keyframe_points[0], fcu.keyframe_points[1]
    for k in (k0, k1):
        k.interpolation = "BEZIER"
        k.handle_left_type = k.handle_right_type = "FREE"
    k0.handle_right = (first + span * a, 0.0)
    k0.handle_left = (first - span * 0.1, 0.0)
    k1.handle_left = (last - span * b, 1.0)
    k1.handle_right = (last + span * 0.1, 1.0)
    return fcu


def add_noise(ob, path, strength, scale, seed_phase):
    """Tiny irregular offset on an already-keyed channel."""
    if ob.animation_data is None or ob.animation_data.action is None:
        ob.keyframe_insert(path, frame=1)
    for f in fcurves_of(ob):
        if f.data_path != path:
            continue
        m = f.modifiers.new("NOISE")
        m.strength = strength
        m.scale = scale
        m.phase = seed_phase + f.array_index * 17.3
        m.depth = 0


def build_rig(shot, col, bake_end, traj):
    first, last = shot_frames(shot)
    n = shot["n"]
    path = make_path(shot, col)

    rig = bpy.data.objects.new("FILMRIG_S%02d" % n, None)
    rig.empty_display_type = "PLAIN_AXES"
    rig.empty_display_size = 0.12
    col.objects.link(rig)
    con = rig.constraints.new("FOLLOW_PATH")
    con.name = "Follow Path"
    con.target = path
    con.use_curve_follow = False
    con.use_fixed_location = True
    con.forward_axis = "FORWARD_Y"
    con.up_axis = "UP_Z"
    key_offset(rig, first, last, shot["ease"])

    tgt = bpy.data.objects.new("FILMTGT_S%02d" % n, None)
    tgt.empty_display_type = "SPHERE"
    tgt.empty_display_size = 0.06
    col.objects.link(tgt)

    if shot.get("track_ball"):
        # Aim is taken straight off the solved samples for that ball, so the
        # move cannot drift away from where the physics actually put it.
        ball = traj["balls"][shot["track_ball"]]
        samples = ball["samples"]
        for fr in range(first, last + 1):
            t = FT.scene_time(fr)
            s = min(samples, key=lambda s: abs(s["t"] - t))
            tgt.location = (s["p"][0] - 0.385, s["p"][1] + 0.880,
                            s["p"][2] + 0.762)
            tgt.keyframe_insert("location", frame=fr)
        for f in fcurves_of(tgt):
            for k in f.keyframe_points:
                k.interpolation = "BEZIER"
    else:
        for frac, x, y, z in shot["target"]:
            fr = first + (last - first) * frac
            tgt.location = (x, y, z)
            tgt.keyframe_insert("location", frame=int(round(fr)))
        for f in fcurves_of(tgt):
            for k in f.keyframe_points:
                k.interpolation = "BEZIER"
                k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"

    cam_data = bpy.data.cameras.new("CAM_Cine_S%02d_%s" % (n, shot["name"]))
    cam_data.lens = shot["lens"]
    cam_data.clip_start = 0.02
    cam_data.clip_end = 60.0
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = shot["fstop"]
    cam_data.dof.focus_object = tgt
    cam = bpy.data.objects.new("CAM_Cine_S%02d_%s" % (n, shot["name"]),
                               cam_data)
    col.objects.link(cam)
    cam.parent = rig
    cam.location = (0.0, 0.0, 0.0)
    tc = cam.constraints.new("TRACK_TO")
    tc.target = tgt
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"

    if shot["noise"]:
        # Translation lives on the rig (0.001-0.004 m), aim wobble is bought
        # by nudging the target instead of the camera, because the camera's
        # rotation belongs to the Track To constraint. 0.003 m of target
        # offset at ~3 m reads as about 0.06 deg - inside the brief's band.
        add_noise(rig, "location", 0.0030, 21.0, 11.0 * n)
        add_noise(tgt, "location", 0.0032, 15.0, 53.0 * n)

    return dict(shot=n, name=shot["name"], cam=cam.name, path=path.name,
                rig=rig.name, target=tgt.name, first=first, last=last,
                lens=shot["lens"], fstop=shot["fstop"], why=shot["why"],
                tracks_ball=shot.get("track_ball"))


# ---------------------------------------------------------------- flicker ----
# Two sources, both of which the camera can actually see: the tired red tube
# over the west wall, and one section of the OPEN sign. Each has an emissive
# material and a lamp, and both channels get the SAME multiplier on the same
# frame - that equality is what 116 re-checks.
FLICKER = {
    "pool_neon": dict(
        materials=["MAT_Prop_NeonRed_pool_0", "MAT_Prop_NeonRed_pool_1",
                   "MAT_Prop_NeonRed_pool_2"],
        light="LGT_Neon",
        visible="LGT_NeonTube_0/1/2 (west wall, over the booth end of the bar)",
        tired=True),
    "open_neon": dict(
        materials=["MAT_OpenNeon_N_film"],
        light="LGT_Neon_WindowOpen",
        visible="LGT_NeonWindowOpen_N_0/1/2 - the N of the storefront sign "
                "only; O, P and E stay lit",
        tired=False),
}


def build_flicker_schedule(traj_sha):
    """Deterministic, seeded off the frozen trajectory hash. No sine, no strobe.

    Normal life is 3-8% microvariation. On top of that sit occasional
    one-frame dips of 20-35%, and - on the tired tube only - a rare 2-3 frame
    50-70% sag. Nothing is periodic, and the windows around the two pocket
    events are held to microvariation so a dip cannot eat the moment the film
    exists to show.
    """
    seed = int(traj_sha[:16], 16)
    protect = set()
    for ev_frame in (FT.film_frame(1.5046 + FT.FILM_OFFSET_S),
                     FT.film_frame(2.0780 + FT.FILM_OFFSET_S)):
        protect.update(range(ev_frame - 4, ev_frame + 5))

    sched = {}
    for src, cfg in FLICKER.items():
        rng = random.Random(seed ^ (hash(src) & 0xFFFFFFFF))
        mult = [1.0] * FT.TOTAL_FRAMES
        f = 0
        while f < FT.TOTAL_FRAMES:
            mult[f] = 1.0 - rng.uniform(0.03, 0.08) * rng.choice((1.0, 0.35))
            f += 1
        # one-frame dips
        n_dip = 26 if cfg["tired"] else 14
        for _ in range(n_dip):
            f = rng.randrange(FT.TOTAL_FRAMES)
            if f in protect:
                continue
            mult[f] = 1.0 - rng.uniform(0.20, 0.35)
        # the rare tired sag
        if cfg["tired"]:
            for _ in range(3):
                f = rng.randrange(FT.TOTAL_FRAMES - 3)
                if any(k in protect for k in range(f, f + 3)):
                    continue
                depth = rng.uniform(0.50, 0.70)
                for k in range(f, f + rng.choice((2, 3))):
                    if k < FT.TOTAL_FRAMES:
                        mult[k] = 1.0 - depth * rng.uniform(0.85, 1.0)
        sched[src] = [round(v, 6) for v in mult]
    return sched


def write_flicker(sched, out_dir, traj_sha):
    os.makedirs(out_dir, exist_ok=True)
    base = {}
    for src, cfg in FLICKER.items():
        mats = {}
        for mn in cfg["materials"]:
            m = bpy.data.materials.get(mn)
            if m is None:
                raise RuntimeError("flicker material %s missing" % mn)
            node = None
            for nd in m.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    node = nd
            if node is None:
                raise RuntimeError("no Principled node in %s" % mn)
            mats[mn] = round(node.inputs["Emission Strength"].default_value, 6)
        lt = bpy.data.objects.get(cfg["light"])
        if lt is None:
            raise RuntimeError("flicker light %s missing" % cfg["light"])
        base[src] = dict(materials=mats, light=cfg["light"],
                         light_energy=round(lt.data.energy, 6),
                         visible=cfg["visible"])
    doc = dict(trajectory_sha256=traj_sha, fps=FT.FPS,
               total_frames=FT.TOTAL_FRAMES, base=base, schedule=sched)
    jp = os.path.join(out_dir, "flicker.json")
    with open(jp, "w") as fh:
        json.dump(doc, fh, indent=1)
    cp = os.path.join(out_dir, "flicker.csv")
    with open(cp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "source", "multiplier", "emission_strength",
                    "light_energy"])
        for src in sorted(sched):
            for fr, mlt in enumerate(sched[src]):
                for mn, bv in base[src]["materials"].items():
                    w.writerow([fr, "%s:%s" % (src, mn), "%.6f" % mlt,
                                "%.6f" % (bv * mlt),
                                "%.6f" % (base[src]["light_energy"] * mlt)])
    log("flicker schedule -> %s and %s" % (jp, cp))
    return doc


# -------------------------------------------------------------------- main ---
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--light-scale", type=float, default=1.0)
    args = ap.parse_args(argv)

    with open(SHOT_JSON, "rb") as fh:
        raw = fh.read()
    traj = json.loads(raw)
    traj_sha = traj["trajectory_sha256"]
    log("shot %s  duration %.6f s  events %d  sha %s"
        % (traj["shot_id"], traj["duration_s"], len(traj["events"]), traj_sha))
    if traj["shot_id"] != "b_51":
        raise RuntimeError("expected b_51, got %s" % traj["shot_id"])

    scene = bpy.context.scene
    bake_end = scene.frame_end
    log("baked playback frames %d..%d" % (scene.frame_start, bake_end))

    purge_previous()
    render_layer, layer_excludes = select_gameplay_view_layer(scene)
    vol_mats, vol_hidden = kill_all_volumes()
    horns = hide_cap_horns()
    orig_start, orig_end = scene.frame_start, scene.frame_end
    shift, n_obj, n_keys, impact_frame = rebase_gameplay_to_film_time(scene)

    col = get_collection("12_FILM_CINEMATIC")
    open_n, open_mat, open_src = isolate_open_neon_N(col)
    lights = build_film_lights(col, args.light_scale)

    manifest = []
    for s in SHOTS:
        manifest.append(build_rig(s, col, bake_end, traj))
        f0, f1 = shot_frames(s)
        log("S%02d %-18s %04d-%04d  %4.1fmm f/%-4.1f %s"
            % (s["n"], s["name"], f0, f1, s["lens"], s["fstop"],
               "ball %s" % s["track_ball"] if s.get("track_ball") else ""))

    covered = sum(m["last"] - m["first"] + 1 for m in manifest)
    if covered != FT.TOTAL_FRAMES:
        raise RuntimeError("shots cover %d frames, need %d"
                           % (covered, FT.TOTAL_FRAMES))
    edges = sorted((m["first"], m["last"]) for m in manifest)
    for i in range(len(edges) - 1):
        if edges[i][1] + 1 != edges[i + 1][0]:
            raise RuntimeError("gap between %s and %s"
                               % (edges[i], edges[i + 1]))
    if edges[0][0] != 0 or edges[-1][1] != FT.TOTAL_FRAMES - 1:
        raise RuntimeError("coverage is not 0..%d" % (FT.TOTAL_FRAMES - 1))
    log("coverage: %d shots, frames %04d-%04d, no gaps"
        % (len(manifest), edges[0][0], edges[-1][1]))

    flick = build_flicker_schedule(traj_sha)
    write_flicker(flick, args.report_dir, traj_sha)

    doc = dict(
        trajectory_sha256=traj_sha, shot_id=traj["shot_id"],
        duration_s=traj["duration_s"], fps=FT.FPS,
        total_frames=FT.TOTAL_FRAMES, film_offset_s=FT.FILM_OFFSET_S,
        strike_frame=FT.STRIKE_FRAME,
        bake_start=FT.STRIKE_FRAME, bake_end=orig_end + shift,
        original_bake=[orig_start, orig_end], gameplay_shift=shift,
        bake_impact_frame=impact_frame,
        render_view_layer=render_layer, view_layer_excludes=layer_excludes,
        gameplay_objects_rebased=n_obj, gameplay_keys_rebased=n_keys,
        pocket_frames={"7": 336, "4": 350}, last_stop_frame=487,
        volume_materials=vol_mats, volume_objects_hidden=vol_hidden,
        cap_horns_hidden=horns,
        open_neon_n_objects=open_n, open_neon_n_material=open_mat,
        open_neon_base_material=open_src, film_lights=lights,
        light_scale=args.light_scale, shots=manifest)
    mp = os.path.join(args.report_dir, "shot-manifest.json")
    os.makedirs(args.report_dir, exist_ok=True)
    with open(mp, "w") as fh:
        json.dump(doc, fh, indent=1)
    log("manifest -> %s" % mp)

    scene.frame_start = scene.frame_start
    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    log("saved %s (%.1f MB)"
        % (args.out, os.path.getsize(args.out) / 1048576.0))
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
