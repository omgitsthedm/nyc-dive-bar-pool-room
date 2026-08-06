"""108_render_candidate_proof.py - proof set for ONE break candidate.

Runs inside Blender against a THROWAWAY gameplay blend baked from a candidate
trajectory. Produces, into renders/break_candidates/<id>/:

  contact/0-5.png   six stills across the shot: address, strike, first spread,
                    mid-settle, late-settle, final rest
  overhead/*.png    the whole break from the locked-off top camera

The overhead is LOCKED OFF, not a flyover. Section 6.2 forbids camera moves in
the film, and for judging where balls actually land a static top-down is
strictly more readable than a move - a moving camera makes it harder to tell
whether the spread or the camera changed.
"""
import argparse
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402

FPS = 24
OVERHEAD_SECONDS = 10.0
OVERHEAD_CAM = "CAM_PoolAudit_Top_24mm"
CONTACT_CAM = "CAM_Table_ThreeQuarter_50mm"


def _eevee(scene):
    """EEVEE with the A1 engine split: real volume OFF, legacy cones ON."""
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            break
        except TypeError:
            continue
    haze = bpy.data.objects.get("ATM_RoomHaze_Volume")
    if haze is not None:
        haze.hide_render = True
    for ob in bpy.data.objects:
        if ob.name.startswith("ATM_PoolBeam"):
            ob.hide_render = False
    print("  [proof] engine=%s  room haze OFF (EEVEE path)"
          % scene.render.engine)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resolution", default="1280x720")
    args = ap.parse_args(argv)

    w, h = (int(v) for v in args.resolution.lower().split("x"))
    scene = bpy.context.scene
    _eevee(scene)
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    start, end = scene.frame_start, scene.frame_end
    span = max(end - start, 1)
    print("  [proof] %s baked frame range %d..%d" % (args.id, start, end))

    # Six contact stills spread across the actual baked range.
    contact_dir = os.path.join(args.out, "contact")
    os.makedirs(contact_dir, exist_ok=True)
    scene.camera = bpy.data.objects[CONTACT_CAM]
    for i in range(6):
        frame = start + round(span * (i / 5.0))
        scene.frame_set(int(frame))
        scene.render.filepath = os.path.join(contact_dir, "%d.png" % i)
        bpy.ops.render.render(write_still=True)
    print("  [proof] %s wrote 6 contact stills" % args.id)

    # The break, locked off from above, for the full ten seconds or the whole
    # baked shot if it is shorter.
    overhead_dir = os.path.join(args.out, "overhead")
    os.makedirs(overhead_dir, exist_ok=True)
    scene.camera = bpy.data.objects[OVERHEAD_CAM]
    last = min(end, start + int(OVERHEAD_SECONDS * FPS))
    scene.frame_start, scene.frame_end = start, last
    scene.render.filepath = os.path.join(overhead_dir, "")
    bpy.ops.render.render(animation=True)
    print("  [proof] %s wrote overhead frames %d..%d" % (args.id, start, last))
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
