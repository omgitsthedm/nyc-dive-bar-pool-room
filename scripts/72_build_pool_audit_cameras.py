"""Add reproducible geometry-proof cameras without clearing authored cameras."""
import bpy
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402
import lib as L  # noqa: E402


CAMS = "08_CAMERAS"
CX, CY = C.TABLE_CENTRE[0], C.TABLE_CENTRE[1]
ORTHOGRAPHIC_SCALES = {
    # At the audit renderer's 16:9 aspect this leaves margin around both the
    # floor and ceiling while retaining the full table length.
    "CAM_PoolAudit_Fixture_SideElevation": 6.0,
}

SPEC = (
    # Inside the room, above the billiard fixture but below the ceiling. The
    # fixture meshes are hidden only while rendering this diagnostic view.
    ("CAM_PoolAudit_Top_24mm", 24.0, (CX, CY, 2.86),
     (CX, CY, C.BED_Z), 11.0),
    ("CAM_PoolAudit_Corner_85mm", 85.0,
     (CX + 0.34, CY - 0.55, 1.18),
     (CX - C.PLAY_W / 2.0 - 0.018,
      CY - C.PLAY_L / 2.0 - 0.018, C.BED_Z - 0.005), 16.0),
    ("CAM_PoolAudit_Side_85mm", 85.0,
     (CX - 0.42, CY - 0.32, 1.17),
     (CX + C.PLAY_W / 2.0 + 0.045, CY, C.BED_Z - 0.006), 16.0),
    # Pocket-specific construction proofs. Top views establish the open mouth
    # against a regulation ball; underside views establish that the welt,
    # casting, straps and basket are one attached assembly rather than a cup
    # placed on top of the rail.
    ("CAM_PoolAudit_CornerTop_70mm", 70.0,
     (CX - 0.635, CY - 1.275, 1.55),
     (CX - 0.635, CY - 1.275, C.BED_Z - 0.015), 16.0),
    ("CAM_PoolAudit_SideTop_70mm", 70.0,
     (CX + 0.70, CY, 1.55),
     (CX + 0.70, CY, C.BED_Z - 0.015), 16.0),
    ("CAM_PoolAudit_CornerUnderside_55mm", 50.0,
     (CX - 1.02, CY - 1.66, 0.53),
     (CX - 0.66, CY - 1.30, C.BED_Z - 0.005), 16.0),
    ("CAM_PoolAudit_SideUnderside_55mm", 50.0,
     (CX + 1.18, CY, 0.53),
     (CX + 0.70, CY, C.BED_Z - 0.005), 16.0),
    # True X-axis elevation from the open east/pool aisle. Orthographic
    # framing proves the floor-to-table-to-fixture relationship, all three
    # shades, the spine, both chain pairs and the ceiling canopy in one view.
    ("CAM_PoolAudit_Fixture_SideElevation", 50.0,
     (C.ROOM_W / 2.0 - 0.18, CY, C.ROOM_H / 2.0),
     (CX, CY, C.ROOM_H / 2.0), 16.0),
    # Plausible standing-eye view from the open front-east aisle. The 24 mm
    # lens keeps the full table and the complete suspended fixture in frame.
    ("CAM_PoolAudit_Fixture_ThreeQuarter_24mm", 24.0,
     (CX + 2.50, CY - 3.20, 1.65),
     (CX, CY, C.ROOM_H / 2.0), 16.0),
)


def _remove(name):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and getattr(data, "users", 1) == 0:
            if isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)


def build(mats=None):
    made = []
    for name, lens, location, aim, fstop in SPEC:
        _remove(name)
        _remove(name + "_AIM")
        target = bpy.data.objects.new(name + "_AIM", None)
        L.link(target, CAMS)
        target.location = aim
        target.empty_display_size = 0.025
        camera_data = bpy.data.cameras.new(name)
        camera_data.lens = lens
        ortho_scale = ORTHOGRAPHIC_SCALES.get(name)
        if ortho_scale is not None:
            camera_data.type = "ORTHO"
            camera_data.ortho_scale = ortho_scale
        camera_data.sensor_width = 36.0
        camera_data.clip_start = 0.015
        camera_data.clip_end = 20.0
        camera_data.dof.use_dof = True
        camera_data.dof.focus_object = target
        camera_data.dof.aperture_fstop = fstop
        camera = bpy.data.objects.new(name, camera_data)
        L.link(camera, CAMS)
        camera.location = location
        track = camera.constraints.new("TRACK_TO")
        track.target = target
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        made.append(camera)
    print("  [pool audit cameras] %d built" % len(made))
    return made


if __name__ == "__main__":
    build()
