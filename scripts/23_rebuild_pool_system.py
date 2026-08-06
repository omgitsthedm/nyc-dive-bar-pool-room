"""Rebuild only the pool system inside an approved environment master.

Invoke Blender with the current master as the input file. This stage reuses
the already-authored materials, verifies the frozen environment before and
after, rebuilds table/balls/cameras, and saves a derived preview by default.
It never overwrites ``poolroom_master.blend`` unless an operator explicitly
passes that exact path as ``--output``.
"""
import argparse
import bpy
import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)

import config as C  # noqa: E402


MATERIAL_NAMES = {
    "walnut": "MAT_Table_Walnut_Clearcoat",
    "cloth": "MAT_Table_Cloth_DarkTournamentGreen",
    "leather": "MAT_Pocket_Leather_Oxblood",
    "slate": "MAT_Table_Slate_Honed",
    "blacksteel": "MAT_Metal_BlackenedSteel",
    "pearl": "MAT_Inlay_MotherOfPearl",
    "facing": "MAT_Pocket_Facing_Rubber",
}


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=os.path.join(C.ROOT, "blend",
                             "poolroom_pool_rebuild_preview.blend"),
    )
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(argv)


def _materials():
    result, missing = {}, []
    for key, name in MATERIAL_NAMES.items():
        material = bpy.data.materials.get(name)
        if material is None:
            missing.append(name)
        else:
            result[key] = material
    if missing:
        raise RuntimeError("approved master is missing materials: " +
                           ", ".join(missing))

    cloth_principled = next(
        (node for node in result["cloth"].node_tree.nodes
         if node.type == "BSDF_PRINCIPLED"), None)
    if cloth_principled is None:
        raise RuntimeError("table cloth has no Principled shader")
    for link in list(cloth_principled.inputs["Roughness"].links):
        result["cloth"].node_tree.links.remove(link)
    cloth_principled.inputs["Roughness"].default_value = 0.68
    result["cloth"]["nap_free_worsted"] = True

    walnut_cross = bpy.data.materials.get("MAT_Table_Walnut_CrossGrain")
    if walnut_cross is None:
        walnut_cross = result["walnut"].copy()
        walnut_cross.name = "MAT_Table_Walnut_CrossGrain"
        tree = walnut_cross.node_tree
        texture_nodes = [node for node in tree.nodes
                         if node.bl_idname == "ShaderNodeTexCoord"]
        roots = [node for node in tree.nodes
                 if node.bl_idname == "ShaderNodeMapping" and
                 any(link.from_node in texture_nodes and
                     link.to_node == node for link in tree.links)]
        if len(roots) != 1:
            raise RuntimeError("walnut material has no unique root mapping")
        roots[0].inputs["Rotation"].default_value[2] = math.radians(90.0)
        walnut_cross["grain_axis"] = "world_x"
    result["walnut_cross"] = walnut_cross

    # These materials are intentionally rebuilt from their procedural source.
    # This keeps the bed history subtle and removes false high-frequency ribs
    # from steep pocket-facing and liner surfaces.
    materials = importlib.import_module("40_build_materials")
    importlib.reload(materials)
    cloth_facing = materials.cloth_pocket_facing()
    cloth_facing["derived_for_pocket_facing"] = True
    result["cloth_facing"] = cloth_facing
    result["cloth_bed"] = materials.cloth_bed()
    cloth_liner = materials.cloth_pocket_liner()
    cloth_liner["derived_for_pocket_liner"] = True
    result["cloth_liner"] = cloth_liner

    interior = bpy.data.materials.get("MAT_Pocket_Leather_Interior")
    if interior is None:
        interior = result["leather"].copy()
        interior.name = "MAT_Pocket_Leather_Interior"
        principled = next((node for node in interior.node_tree.nodes
                           if node.type == "BSDF_PRINCIPLED"), None)
        if principled is None:
            raise RuntimeError("pocket leather has no Principled shader")
        principled.inputs["Base Color"].default_value = \
            (0.034, 0.008, 0.004, 1.0)
        principled.inputs["Roughness"].default_value = 0.64
        interior["derived_for_pocket_throat"] = True
    result["leather_interior"] = interior

    shadow = bpy.data.materials.get("MAT_Pocket_Leather_DeepShadow")
    if shadow is None:
        shadow = interior.copy()
        shadow.name = "MAT_Pocket_Leather_DeepShadow"
    shadow_principled = next(
        (node for node in shadow.node_tree.nodes
         if node.type == "BSDF_PRINCIPLED"), None)
    if shadow_principled is None:
        raise RuntimeError("pocket shadow leather has no Principled shader")
    for socket_name in ("Base Color", "Roughness"):
        for link in list(shadow_principled.inputs[socket_name].links):
            shadow.node_tree.links.remove(link)
    shadow_principled.inputs["Base Color"].default_value = \
        (0.0025, 0.0012, 0.0008, 1.0)
    shadow_principled.inputs["Roughness"].default_value = 0.92
    shadow["deep_recess_not_open_void"] = True
    result["leather_shadow"] = shadow

    basket = bpy.data.materials.get("MAT_Pocket_Leather_Basket")
    if basket is None:
        basket = result["leather"].copy()
        basket.name = "MAT_Pocket_Leather_Basket"
        principled = next((node for node in basket.node_tree.nodes
                           if node.type == "BSDF_PRINCIPLED"), None)
        if principled is None:
            raise RuntimeError("pocket leather has no Principled shader")
        geometry = basket.node_tree.nodes.new("ShaderNodeNewGeometry")
        facing_mix = basket.node_tree.nodes.new("ShaderNodeMixRGB")
        facing_mix.blend_type = "MIX"
        facing_mix.inputs[1].default_value = (0.125, 0.034, 0.018, 1.0)
        facing_mix.inputs[2].default_value = (0.022, 0.005, 0.003, 1.0)
        basket.node_tree.links.new(geometry.outputs["Backfacing"],
                                   facing_mix.inputs["Fac"])
        basket.node_tree.links.new(facing_mix.outputs["Color"],
                                   principled.inputs["Base Color"])
        principled.inputs["Roughness"].default_value = 0.58
        basket["derived_for_two_sided_pocket_basket"] = True
    result["leather_basket"] = basket
    return result


def _environment_lock():
    module = importlib.import_module("98_validate_environment_lock")
    importlib.reload(module)
    if not module.run(write=False):
        raise RuntimeError("environment lock mismatch; pool rebuild aborted")


def _pool_light_tuning():
    """Apply the pool-only fill revision without rebuilding room practicals."""
    fill = bpy.data.objects.get("LGT_Pool_Fill")
    if fill is None or fill.type != "LIGHT":
        raise RuntimeError("approved master is missing LGT_Pool_Fill")
    fill.data.energy = 8.0
    fill["table_fill_revision"] = "continuous_rail_v2"


def main():
    args = _args()
    _environment_lock()
    mats = _materials()

    table = importlib.import_module("20_build_pool_table")
    importlib.reload(table)
    table.build(mats)

    balls = importlib.import_module("22_build_balls_and_rack")
    importlib.reload(balls)
    balls.build()

    cameras = importlib.import_module("70_build_cameras")
    importlib.reload(cameras)
    cameras.build()

    audit_cameras = importlib.import_module("72_build_pool_audit_cameras")
    importlib.reload(audit_cameras)
    audit_cameras.build()

    _pool_light_tuning()

    _environment_lock()
    output = os.path.realpath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=output)
    print("[pool rebuild] saved derived file: " + output)


if __name__ == "__main__":
    main()
