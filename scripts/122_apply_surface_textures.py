"""122_apply_surface_textures.py - hang the authored maps on the big surfaces.

None of this architecture has UV layers - not one wall, ceiling panel, bar top
or floor slab. Rather than unwrap 400 objects, each material gets BOX
projection driven from Object coordinates, which are already in metres, so a
tile size is a real measurement: plaster repeats every 2 m, tin every 2.44 m
(four 0.61 m pressed panels, matching the modelled panel pitch), oak every
1.1 m along a board.

Each material is rebuilt as colour + roughness + bump from the three maps 121
wrote. The procedural graphs they replace were the reason a 200-sample render
of this room looked identical to an 8-sample one: there was no detail present
for the extra samples to resolve.

Film-only. Nothing is written back to a locked blend.
"""
from __future__ import annotations

import argparse
import os
import sys

import bpy

# material name -> (texture set, tile metres, roughness gain, bump strength)
ASSIGNMENTS = {
    "MAT_Env_Plaster_Tobacco":      ("plaster_tobacco", 2.00, 1.00, 0.35),
    "MAT_Env_TinCeiling_Painted":   ("tin_ceiling",     2.44, 1.00, 0.55),
    "MAT_Env_TinCeiling_WaterStain": ("tin_ceiling",    2.44, 1.05, 0.55),
    "MAT_Bar_OldStainedOak":        ("oak_stained",     1.10, 1.00, 0.30),
    "MAT_Table_Walnut_Clearcoat":   ("oak_stained",     0.90, 0.55, 0.18),
    "MAT_Table_Walnut_CrossGrain":  ("oak_stained",     0.90, 0.55, 0.18),
    "MAT_Prop_Frame_DarkWood":      ("oak_stained",     0.70, 0.90, 0.25),
    "MAT_Bar_OldStainedOak_Worn":   ("oak_stained",     1.10, 1.15, 0.35),
}


def log(m):
    print("  [surf] %s" % m)


def image(tex_dir, name, colorspace):
    path = os.path.join(tex_dir, name)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def rebuild(mat, tex_dir, base, tile, rgain, bump_strength):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0 / tile,) * 3
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = image(tex_dir, "%s_col.png" % base, "sRGB")
    rgh = nt.nodes.new("ShaderNodeTexImage")
    rgh.image = image(tex_dir, "%s_rgh.png" % base, "Non-Color")
    hgt = nt.nodes.new("ShaderNodeTexImage")
    hgt.image = image(tex_dir, "%s_hgt.png" % base, "Non-Color")
    for n in (col, rgh, hgt):
        n.projection = "BOX"
        n.projection_blend = 0.25
        n.extension = "REPEAT"
        nt.links.new(mapping.outputs["Vector"], n.inputs["Vector"])

    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])

    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.0
    ramp.inputs["From Max"].default_value = 1.0
    ramp.inputs["To Min"].default_value = max(0.05, 0.18 * rgain)
    ramp.inputs["To Max"].default_value = min(1.0, 0.95 * rgain)
    nt.links.new(rgh.outputs["Color"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(hgt.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat["film_only_surfacing"] = True


def rebuild_mirror(mat, tex_dir):
    """A desilvered mirror should still be a mirror in the good patches.

    It was a flat grey-brown blur - the muddy smear behind the register in
    every bar frame. Real backbar glass that has lost its silvering reflects
    sharply where the coating survives and scatters where it has gone, so
    this drives roughness and a black-to-silver mix off the plaster height
    map: bright patches mirror the room, dark ones read as bare glass.
    """
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.55, 0.55, 0.55)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    pat = nt.nodes.new("ShaderNodeTexImage")
    pat.image = image(tex_dir, "plaster_tobacco_hgt.png", "Non-Color")
    pat.projection = "BOX"
    pat.projection_blend = 0.3
    nt.links.new(mapping.outputs["Vector"], pat.inputs["Vector"])

    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["To Min"].default_value = 0.04      # silvered: near mirror
    rng.inputs["To Max"].default_value = 0.55      # bare: scattered
    nt.links.new(pat.outputs["Color"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], bsdf.inputs["Roughness"])

    tint = nt.nodes.new("ShaderNodeMapRange")
    tint.inputs["To Min"].default_value = 0.18
    tint.inputs["To Max"].default_value = 0.86
    nt.links.new(pat.outputs["Color"], tint.inputs["Value"])
    mixc = nt.nodes.new("ShaderNodeMixRGB")
    mixc.inputs["Color1"].default_value = (0.20, 0.17, 0.14, 1.0)
    mixc.inputs["Color2"].default_value = (0.86, 0.84, 0.78, 1.0)
    nt.links.new(tint.outputs["Result"], mixc.inputs["Fac"])
    nt.links.new(mixc.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat["film_only_surfacing"] = True


FRUIT_MATS = ("MAT_Bar_Fruit_Apple", "MAT_Bar_Fruit_Lemon",
              "MAT_Bar_Garnish_Orange", "MAT_Bar_Fruit_Lime")


def improve_fruit():
    """Give the fruit skin, and let light through it.

    422-vertex spheres in a flat diffuse read as painted clay - which is
    exactly what they looked like sitting in the bowl on the bar. Citrus peel
    is pitted and scatters light; apple skin is waxy with a broad, soft
    highlight and a little translucency at the rim. Both are shader problems,
    not geometry problems, so nothing here re-meshes anything.
    """
    touched = []
    for name in FRUIT_MATS:
        mat = bpy.data.materials.get(name)
        if mat is None or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = None
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
        if bsdf is None:
            continue
        citrus = ("Lemon" in name or "Orange" in name or "Lime" in name)

        # Pitted peel / waxy skin, as a bump only.
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 220.0 if citrus else 90.0
        noise.inputs["Detail"].default_value = 6.0
        noise.inputs["Roughness"].default_value = 0.65
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.28 if citrus else 0.12
        bump.inputs["Distance"].default_value = 0.0009
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if not bsdf.inputs["Normal"].is_linked:
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

        if not bsdf.inputs["Roughness"].is_linked:
            bsdf.inputs["Roughness"].default_value = 0.44 if citrus else 0.28
        for key, val in (("Subsurface Weight", 0.22 if citrus else 0.10),
                         ("Subsurface Scale", 0.010 if citrus else 0.006),
                         ("Coat Weight", 0.0 if citrus else 0.30),
                         ("Coat Roughness", 0.22)):
            if key in bsdf.inputs and not bsdf.inputs[key].is_linked:
                bsdf.inputs[key].default_value = val
        mat["film_only_surfacing"] = True
        touched.append(name)
    log("fruit re-shaded (peel bump, subsurface, wax coat): %s"
        % (touched or "none found"))
    return touched


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--textures", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    done, missing = [], []
    for name, (base, tile, rgain, bs) in ASSIGNMENTS.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            missing.append(name)
            continue
        rebuild(mat, args.textures, base, tile, rgain, bs)
        done.append("%s<-%s@%.2fm" % (name, base, tile))
    improve_fruit()
    mir = bpy.data.materials.get("MAT_Bar_Mirror_Desilvered")
    if mir is not None:
        rebuild_mirror(mir, args.textures)
        done.append("MAT_Bar_Mirror_Desilvered<-patchy silvering")
    for d in done:
        log(d)
    if missing:
        log("not present in this scene (skipped): %s" % missing)
    log("%d materials re-surfaced from authored maps" % len(done))

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    log("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
