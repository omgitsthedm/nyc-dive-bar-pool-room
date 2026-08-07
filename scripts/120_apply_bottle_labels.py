"""120_apply_bottle_labels.py - put the printed labels on the bottles, and give
the glass some variety.

Two changes, both aimed at the same measurement: a 200-sample render of the
back bar is indistinguishable from an 8-sample one, so nothing on that shelf
was noise-limited. It was surfacing-limited.

LABELS. 169 label objects, all wearing one of two flat procedural paper
materials. They are 8-vertex boxes with no UV layers at all, so this uses BOX
projection from Generated coordinates - which needs no UVs - to put one of 24
printed labels on each. Assignment is by a hash of the object name, so the
shelf is identical every rebuild and neighbouring bottles never match.

GLASS. Three materials covered all 213 bottles: one roughness, one tint, no
absorption, so they read as tinted plastic. This builds eight variants with
varied tint, varied roughness and real volume absorption, so thick parts of a
bottle go darker than thin parts the way glass actually does.

Film-only. Nothing here is saved back to a locked blend.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C  # noqa: E402


def log(msg):
    print("  [labels] %s" % msg)


def stable_index(name, n):
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % n


def build_label_materials(label_dir):
    files = sorted(f for f in os.listdir(label_dir) if f.endswith(".png"))
    if not files:
        raise RuntimeError("no label PNGs in %s - run 119 first" % label_dir)
    mats = []
    for i, fn in enumerate(files):
        name = "MAT_BottleLabel_%02d" % i
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex = nt.nodes.new("ShaderNodeTexImage")
        coord = nt.nodes.new("ShaderNodeTexCoord")
        bump = nt.nodes.new("ShaderNodeBump")

        img = bpy.data.images.load(os.path.join(label_dir, fn),
                                   check_existing=True)
        tex.image = img
        # Box projection off Generated coords: no UVs required, and the large
        # faces of a thin slab get the artwork the right way up.
        tex.projection = "BOX"
        tex.projection_blend = 0.15
        tex.interpolation = "Smart"
        nt.links.new(coord.outputs["Generated"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        # Paper has tooth, and ink sits slightly proud of it.
        bsdf.inputs["Roughness"].default_value = 0.62 + (i % 5) * 0.02
        bsdf.inputs["Specular IOR Level"].default_value = 0.32
        bump.inputs["Strength"].default_value = 0.06
        bump.inputs["Distance"].default_value = 0.0004
        nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        mats.append(mat)
    log("built %d printed-label materials from %s" % (len(mats), label_dir))
    return mats


# tint, roughness, absorption density. Real bottles are not one green.
# Density is per metre and a bottle wall is millimetres, but the ray also
# crosses the whole body, so the first pass at 5-9 turned the shelf into a row
# of black silhouettes. These are tuned so a shoulder stays translucent and
# only the deepest part of the body goes rich - and the spread is weighted
# towards lighter glass, because a real back bar is mostly clear and pale.
GLASS_VARIANTS = [
    ((0.34, 0.52, 0.36), 1.4, 0.05),    # classic bottle green
    ((0.22, 0.40, 0.26), 2.2, 0.05),    # deep green
    ((0.62, 0.38, 0.14), 1.8, 0.05),    # amber
    ((0.48, 0.24, 0.08), 2.6, 0.06),    # dark amber
    ((0.88, 0.88, 0.85), 0.35, 0.03),   # near clear
    ((0.82, 0.84, 0.82), 0.55, 0.09),   # clear, scuffed
    ((0.90, 0.86, 0.74), 0.45, 0.04),   # pale straw
    ((0.70, 0.58, 0.26), 1.1, 0.07),    # honey
]


def build_glass_materials():
    mats = []
    for i, (tint, dens, rough) in enumerate(GLASS_VARIANTS):
        name = "MAT_BottleGlass_%02d" % i
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.52
        for key, val in (("Metallic", 0.0),):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        # Volume absorption is what makes a shoulder pale and a base black.
        vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
        vol.inputs["Color"].default_value = (tint[0], tint[1], tint[2], 1.0)
        vol.inputs["Density"].default_value = dens
        nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
        mat["film_only"] = True
        mats.append(mat)
    log("built %d glass variants with volume absorption" % len(mats))
    return mats


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--glass", type=int, default=1)
    args = ap.parse_args(argv)

    label_mats = build_label_materials(args.labels)

    labels = [o for o in bpy.data.objects
              if o.type == "MESH" and o.name.endswith("_Label")]
    for ob in labels:
        m = label_mats[stable_index(ob.name, len(label_mats))]
        if ob.data.materials:
            ob.data.materials[0] = m
        else:
            ob.data.materials.append(m)
    log("%d label objects re-surfaced with printed artwork" % len(labels))

    if args.glass:
        glass_mats = build_glass_materials()
        OLD = {"MAT_Bar_Glass_Clear", "MAT_Bar_Glass_Amber",
               "MAT_Bar_Glass_Bottle"}
        n = 0
        for ob in bpy.data.objects:
            if ob.type != "MESH" or not ob.name.startswith("BAR_Bottle"):
                continue
            if ob.name.endswith(("_Label", "_Cap")):
                continue
            for i, slot in enumerate(ob.material_slots):
                if slot.material and slot.material.name in OLD:
                    slot.material = glass_mats[
                        stable_index(ob.name, len(glass_mats))]
                    n += 1
        log("%d bottle glass slots given varied tint and absorption" % n)

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    log("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
