"""Render pool-system proof views without modifying production reports."""
import argparse
import bpy
import os
import sys
import time

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402
import pool_geometry_contract as G  # noqa: E402


AUDIT_CAMERAS = (
    "CAM_PoolAudit_Top_24mm",
    "CAM_PoolAudit_Corner_85mm",
    "CAM_PoolAudit_Side_85mm",
    "CAM_PoolAudit_CornerTop_70mm",
    "CAM_PoolAudit_SideTop_70mm",
    "CAM_PoolAudit_CornerUnderside_55mm",
    "CAM_PoolAudit_SideUnderside_55mm",
    "CAM_PoolAudit_Fixture_SideElevation",
    "CAM_PoolAudit_Fixture_ThreeQuarter_24mm",
    "CAM_Table_ThreeQuarter_50mm",
    "CAM_Rack_Detail_85mm",
)
QUALITY_MODES = {
    # Preserve the original script defaults for fast proof renders.
    "audit": {
        "samples": 32,
        "resolution": (1280, 720),
        "top_resolution": (1200, 1200),
    },
    # Match the project's established final-checkpoint quality on local hardware.
    "final": {
        "samples": 512,
        "resolution": (3840, 2160),
        "top_resolution": (3840, 3840),
    },
}


def _fixture_meshes():
    return [ob for ob in bpy.data.objects
            if ob.name.startswith("LGT_Pool_") and ob.type != "LIGHT"]


def _scale_ball_location(camera_name):
    names = {
        "CAM_PoolAudit_CornerTop_70mm": "corner_SW",
        "CAM_PoolAudit_SideTop_70mm": "side_E",
    }
    pocket_name = names.get(camera_name)
    if pocket_name is None:
        return None
    pocket = next(row for row in G.pocket_rows()
                  if row["name"] == pocket_name)
    center = Vector(pocket["center"])
    inward = -center.normalized()
    point = center + inward * (pocket["radius"] + C.BALL_R + 0.022)
    return C.playfield_to_world(point.x, point.y, C.BALL_R)


def render(samples=32, only=None, resolution=(1280, 720),
           top_resolution=(1200, 1200)):
    scene = bpy.context.scene
    scene.cycles.samples = samples
    output = os.path.join(C.ROOT, "renders", "pool_system_audit")
    os.makedirs(output, exist_ok=True)
    selected = only or AUDIT_CAMERAS
    for name in selected:
        camera = bpy.data.objects.get(name)
        if camera is None:
            raise RuntimeError("missing pool audit camera: " + name)
        top = name == "CAM_PoolAudit_Top_24mm"
        width, height = top_resolution if top else resolution
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        hidden = []
        audit_light = None
        scale_ball = bpy.data.objects.get("PT_Ball_Cue")
        scale_ball_matrix = None
        scale_location = _scale_ball_location(name)
        if scale_location is not None:
            if scale_ball is None:
                raise RuntimeError("missing PT_Ball_Cue for pocket scale proof")
            scale_ball_matrix = scale_ball.matrix_world.copy()
            scale_ball.location = scale_location
        if top:
            # Diagnostic plan view only: preserve the actual lights but hide
            # their shade/chain meshes between camera and table.
            for ob in _fixture_meshes():
                hidden.append((ob, ob.hide_render))
                ob.hide_render = True
        if "Underside" in name:
            # Engineering cutaway: the apron/slate load path normally hides
            # the pocket suspension from any real outboard viewpoint. Remove
            # only those occluders for this diagnostic render; the source
            # blend is restored immediately afterward.
            cutaway_prefixes = (
                "PT_Apron_", "PT_Slate_", "PT_SlateLiner_",
                "PT_Sill_", "PT_CrossSill_", "PT_CentreBeam_",
                "PT_Cloth_Bed",
            )
            for ob in bpy.data.objects:
                if ob.name.startswith(cutaway_prefixes):
                    hidden.append((ob, ob.hide_render))
                    ob.hide_render = True
            light_data = bpy.data.lights.new(
                name="TMP_PocketAudit_Fill", type="POINT")
            light_data.energy = 70.0
            light_data.color = (1.0, 0.82, 0.68)
            light_data.shadow_soft_size = 0.22
            audit_light = bpy.data.objects.new(
                "TMP_PocketAudit_Fill", light_data)
            scene.collection.objects.link(audit_light)
            audit_light.location = camera.location + Vector((0.0, 0.0, 0.24))
        scene.camera = camera
        scene.render.filepath = os.path.join(output, name + ".png")
        started = time.time()
        try:
            bpy.ops.render.render(write_still=True)
        finally:
            for ob, state in hidden:
                ob.hide_render = state
            if scale_ball_matrix is not None:
                scale_ball.matrix_world = scale_ball_matrix
            if audit_light is not None:
                light_data = audit_light.data
                bpy.data.objects.remove(audit_light, do_unlink=True)
                if light_data.users == 0:
                    bpy.data.lights.remove(light_data)
        print("  [pool audit render] %-34s %.1fs" %
              (name, time.time() - started))


def _positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _resolution(value):
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("use WIDTHxHEIGHT, for example 1920x1080")
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("width and height must be positive")
    return width, height


def _parse_cli(argv):
    parser = argparse.ArgumentParser(
        prog="83_render_pool_audit.py",
        description="Render deterministic pool-system audit views.",
    )
    parser.add_argument(
        "--quality", choices=tuple(QUALITY_MODES), default="audit",
        help="audit: 32 spp proof; final: 512 spp 4K (default: audit)",
    )
    parser.add_argument("--samples", type=_positive_int,
                        help="override samples per pixel")
    parser.add_argument(
        "--resolution", type=_resolution, metavar="WIDTHxHEIGHT",
        help="override every camera resolution",
    )
    parser.add_argument(
        "--top-resolution", type=_resolution, metavar="WIDTHxHEIGHT",
        help="override only the diagnostic top view",
    )
    parser.add_argument("cameras", nargs="*", metavar="CAMERA",
                        help="optional camera names; default renders all")
    args, unknown = parser.parse_known_args(argv)

    preset = QUALITY_MODES[args.quality]
    resolution = args.resolution or preset["resolution"]
    top_resolution = args.top_resolution or (
        args.resolution or preset["top_resolution"]
    )
    requested = [
        name for name in (*args.cameras, *unknown) if name in AUDIT_CAMERAS
    ]
    return {
        "samples": args.samples or preset["samples"],
        "resolution": resolution,
        "top_resolution": top_resolution,
        "only": requested or None,
    }


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    render(**_parse_cli(argv))
