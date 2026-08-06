"""
75_build_sweep.py — a 12-second camera sweep of the table and room.

One continuous move, no cuts: it opens wide enough to read the room, arcs
around the foot of the table losing height, and settles low on the rack with
the bar glowing behind it. Nothing in the scene moves — this is a camera piece
over static geometry, which is exactly why it cannot flicker.

Smoothness comes from a Bezier-interpolated path with eased ends, and from
holding the focus on a target that travels with the move so the depth of field
never pops.

Owns: 08_CAMERAS (adds CAM_Sweep only; leaves the four required stills alone).
"""
import bpy
import math
import os
import sys
from math import radians, cos, sin

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402
import lib as L             # noqa: E402

CAMS = "08_CAMERAS"
FPS = 24
SECONDS = 12.0
F_END = int(FPS * SECONDS)          # 288 frames
CX, CY = C.TABLE_CENTRE[0], C.TABLE_CENTRE[1]


def key(ob, frame, loc=None, lens=None, interp="BEZIER"):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert("location", frame=frame)
    if lens is not None:
        ob.data.lens = lens
        ob.data.keyframe_insert("lens", frame=frame)
    for ad in (ob.animation_data, ob.data.animation_data):
        if not ad or not ad.action:
            continue
        for fc in _fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def _fcurves(action):
    """Blender 5.x slotted actions: fall through layers/strips/channelbags."""
    if hasattr(action, "fcurves") and len(action.fcurves):
        return action.fcurves
    out = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


def build(mats=None):
    scene = bpy.context.scene
    for nm in ("CAM_Sweep", "CAM_Sweep_AIM"):
        old = bpy.data.objects.get(nm)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    tgt = bpy.data.objects.new("CAM_Sweep_AIM", None)
    L.link(tgt, CAMS)
    tgt.empty_display_size = 0.05

    cd = bpy.data.cameras.new("CAM_Sweep")
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.02, 60.0
    cd.dof.use_dof = True
    cd.dof.focus_object = tgt
    cd.dof.aperture_fstop = 3.6
    cam = bpy.data.objects.new("CAM_Sweep", cd)
    L.link(cam, CAMS)
    t = cam.constraints.new("TRACK_TO")
    t.target = tgt
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"

    # An arc around the foot end of the table. Radius and height both fall,
    # so the move descends into the shot rather than orbiting flatly.
    beats = [
        # frame, angle(deg), radius, height, aim, lens
        (1,     -128.0, 3.35, 1.98, (CX, CY - 0.10, C.BED_Z + 0.10), 34.0),
        (72,    -104.0, 2.85, 1.66, (CX, CY - 0.25, C.BED_Z + 0.07), 38.0),
        (150,    -74.0, 2.15, 1.24, (CX, CY - 0.45, C.BED_Z + 0.05), 45.0),
        (222,    -48.0, 1.52, 0.98, (CX - 0.05, CY + C.FOOT_SPOT_Y + 0.30,
                                     C.BED_Z + 0.035), 52.0),
        (F_END,  -30.0, 1.06, 0.905, (CX, CY + C.FOOT_SPOT_Y + 0.05,
                                      C.BED_Z + 0.030), 62.0),
    ]
    for (f, ang, rad, h, aim, lens) in beats:
        a = radians(ang)
        key(cam, f, loc=(CX + cos(a) * rad, CY + sin(a) * rad, h), lens=lens)
        tgt.location = aim
        tgt.keyframe_insert("location", frame=f)
    for fc in _fcurves(tgt.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

    scene.frame_start, scene.frame_end = 1, F_END
    scene.render.fps = FPS
    print("  [sweep] CAM_Sweep built: %d frames (%.1f s at %d fps)"
          % (F_END, SECONDS, FPS))
    return cam


if __name__ == "__main__":
    build()
