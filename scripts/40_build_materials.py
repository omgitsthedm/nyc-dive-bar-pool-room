"""
40_build_materials.py — the material bible, built procedurally at real scale.

Every detail is physically scaled: pore size, weave pitch, and scratch density
are expressed in metres, not in arbitrary noise. Large visual change comes from
geometry and motivated masks, never from one grunge layer over everything.
"""
import bpy
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import config as C          # noqa: E402


def _new(name):
    """
    Reuse the existing datablock and rebuild its node tree in place. Removing
    and recreating the material would orphan every object already using it,
    which is exactly what happens when a later stage rebuilds a shared
    material like walnut.
    """
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def _tex_coord(nt, scale):
    """Object-space coordinates at a real-world scale (metres per tile)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def walnut():
    """
    MAT_Table_Walnut_Clearcoat — deep natural walnut, satin clear finish.
    Grain runs along the object's local Y; pores are at true wood-pore scale
    (~0.3 mm), so they only resolve in the 85 mm detail camera.
    """
    m, nt, b = _new("MAT_Table_Walnut_Clearcoat")
    b.inputs["Base Color"].default_value = (0.098, 0.048, 0.026, 1.0)
    b.inputs["Roughness"].default_value = 0.30
    b.inputs["IOR"].default_value = 1.52
    try:
        b.inputs["Coat Weight"].default_value = 0.55
        b.inputs["Coat Roughness"].default_value = 0.09
    except KeyError:
        pass

    mp = _tex_coord(nt, 9.0)
    stretch = nt.nodes.new("ShaderNodeMapping")     # stretch along the grain
    stretch.inputs["Scale"].default_value = (14.0, 0.65, 14.0)
    nt.links.new(mp.outputs["Vector"], stretch.inputs["Vector"])

    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Detail"].default_value = 11.0
    grain.inputs["Roughness"].default_value = 0.62
    nt.links.new(stretch.outputs["Vector"], grain.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (0.062, 0.030, 0.016, 1.0)
    ramp.color_ramp.elements[1].position = 0.66
    ramp.color_ramp.elements[1].color = (0.135, 0.070, 0.038, 1.0)
    nt.links.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])

    # open pores: fine, directional, shallow
    pore = nt.nodes.new("ShaderNodeTexNoise")
    pore.inputs["Scale"].default_value = 340.0
    pore.inputs["Detail"].default_value = 4.0
    nt.links.new(stretch.outputs["Vector"], pore.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.11
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(pore.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])

    # roughness breakup 0.22-0.38, hand-rubbed rather than sprayed
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.22
    rr.inputs["To Max"].default_value = 0.38
    nt.links.new(grain.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    return m


def walnut_cross_grain(source):
    """End-rail walnut with the board grain rotated across world Y."""
    material = source.copy()
    material.name = "MAT_Table_Walnut_CrossGrain"
    tree = material.node_tree
    texture_nodes = [node for node in tree.nodes
                     if node.bl_idname == "ShaderNodeTexCoord"]
    mappings = [node for node in tree.nodes
                if node.bl_idname == "ShaderNodeMapping"]
    roots = []
    for mapping in mappings:
        if any(link.from_node in texture_nodes and link.to_node == mapping
               for link in tree.links):
            roots.append(mapping)
    if len(roots) != 1:
        raise RuntimeError("walnut material has no unique root mapping")
    roots[0].inputs["Rotation"].default_value[2] = math.radians(90.0)
    material["grain_axis"] = "world_x"
    return material


def cloth():
    """
    MAT_Table_Cloth_DarkTournamentGreen — worsted, nap-free.
    Weave pitch is ~0.5 mm so it reads as fabric in the detail camera and as a
    flat colour from the entry camera; never a fuzzy carpet.
    """
    m, nt, b = _new("MAT_Table_Cloth_DarkTournamentGreen")
    b.inputs["Base Color"].default_value = (0.010, 0.048, 0.024, 1.0)
    b.inputs["Roughness"].default_value = 0.68
    try:
        b.inputs["Sheen Weight"].default_value = 0.28
        b.inputs["Sheen Roughness"].default_value = 0.32
    except KeyError:
        pass
    mp = _tex_coord(nt, 1.0)
    weave = nt.nodes.new("ShaderNodeTexWave")
    weave.wave_type = "BANDS"
    weave.bands_direction = "DIAGONAL"
    weave.inputs["Scale"].default_value = 2000.0
    weave.inputs["Distortion"].default_value = 1.6
    nt.links.new(mp.outputs["Vector"], weave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.07
    bump.inputs["Distance"].default_value = 0.00016
    nt.links.new(weave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def cloth_bed():
    """Maintained bar-table worsted with restrained tonal wear.

    Broad, low-contrast colour drift gives the bed the quiet chalk-cleaned
    history of a working table without stains, raised decals or displacement.
    The solver surface therefore remains perfectly flat.
    """
    m, nt, b = _new("MAT_Table_Cloth_BedWornWorsted")
    b.inputs["Roughness"].default_value = 0.69
    try:
        b.inputs["Sheen Weight"].default_value = 0.28
        b.inputs["Sheen Roughness"].default_value = 0.34
    except KeyError:
        pass
    mp = _tex_coord(nt, 1.0)
    wear = nt.nodes.new("ShaderNodeTexNoise")
    wear.inputs["Scale"].default_value = 2.4
    wear.inputs["Detail"].default_value = 5.0
    wear.inputs["Roughness"].default_value = 0.58
    nt.links.new(mp.outputs["Vector"], wear.inputs["Vector"])
    colour = nt.nodes.new("ShaderNodeValToRGB")
    colour.color_ramp.elements[0].position = 0.31
    colour.color_ramp.elements[0].color = (0.009, 0.043, 0.021, 1.0)
    colour.color_ramp.elements[1].position = 0.72
    colour.color_ramp.elements[1].color = (0.017, 0.061, 0.030, 1.0)
    nt.links.new(wear.outputs["Fac"], colour.inputs["Fac"])
    nt.links.new(colour.outputs["Color"], b.inputs["Base Color"])

    weave = nt.nodes.new("ShaderNodeTexWave")
    weave.wave_type = "BANDS"
    weave.bands_direction = "DIAGONAL"
    weave.inputs["Scale"].default_value = 2000.0
    weave.inputs["Distortion"].default_value = 1.6
    nt.links.new(mp.outputs["Vector"], weave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.055
    bump.inputs["Distance"].default_value = 0.00014
    nt.links.new(weave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m["wear_character"] = "restrained_tonal_history_no_stains"
    m["solver_surface_displacement_m"] = 0.0
    return m


def cloth_pocket_facing():
    """Same worsted cloth wrapped across the steep pocket-facing ends.

    The sub-pixel bed weave is suppressed on this near-vertical cut so the
    mitered jaw reads as green upholstery under grazing light, not a black
    triangular void.
    """
    m, _nt, b = _new("MAT_Table_Cloth_PocketFacing")
    b.inputs["Base Color"].default_value = (0.025, 0.095, 0.045, 1.0)
    b.inputs["Roughness"].default_value = 0.72
    try:
        b.inputs["Sheen Weight"].default_value = 0.32
        b.inputs["Sheen Roughness"].default_value = 0.38
    except KeyError:
        pass
    m["steep_wrap_alias_suppressed"] = True
    return m


def cloth_pocket_liner():
    """Worsted cloth folded down the pocket cut without vertical striping.

    The bed's 0.5 mm weave is physically appropriate on a broad horizontal
    field, but the same high-frequency wave shader turns into a false ribbed
    grille when projected across the steep drafted pocket wall.  The liner is
    still the same cloth colour and sheen; only its sub-pixel weave relief is
    suppressed so the routed drop reads as one continuous fabric wrap.
    """
    m, _nt, b = _new("MAT_Table_Cloth_PocketLiner")
    b.inputs["Base Color"].default_value = (0.012, 0.054, 0.027, 1.0)
    b.inputs["Roughness"].default_value = 0.72
    try:
        b.inputs["Sheen Weight"].default_value = 0.30
        b.inputs["Sheen Roughness"].default_value = 0.38
    except KeyError:
        pass
    return m


def leather():
    """MAT_Pocket_Leather_Oxblood — vegetable-tanned, dry creasing not ruin."""
    m, nt, b = _new("MAT_Pocket_Leather_Oxblood")
    # Kept dark and old, but lifted out of near-black so the hanging basket
    # and stitched lip remain readable under the table light.
    b.inputs["Base Color"].default_value = (0.125, 0.034, 0.018, 1.0)
    b.inputs["Roughness"].default_value = 0.48
    mp = _tex_coord(nt, 55.0)
    grain = nt.nodes.new("ShaderNodeTexVoronoi")
    grain.feature = "DISTANCE_TO_EDGE"
    grain.inputs["Scale"].default_value = 42.0
    nt.links.new(mp.outputs["Vector"], grain.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.34
    bump.inputs["Distance"].default_value = 0.0009
    nt.links.new(grain.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def leather_interior():
    """Dark, dry leather used inside the pocket throat, not rail-grain wood."""
    m, nt, b = _new("MAT_Pocket_Leather_Interior")
    b.inputs["Base Color"].default_value = (0.034, 0.008, 0.004, 1.0)
    b.inputs["Roughness"].default_value = 0.64
    mp = _tex_coord(nt, 70.0)
    grain = nt.nodes.new("ShaderNodeTexVoronoi")
    grain.feature = "DISTANCE_TO_EDGE"
    grain.inputs["Scale"].default_value = 56.0
    nt.links.new(mp.outputs["Vector"], grain.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.20
    bump.inputs["Distance"].default_value = 0.00045
    nt.links.new(grain.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def leather_basket():
    """Oxblood outside with a dark, non-wood-reading basket interior."""
    m, nt, b = _new("MAT_Pocket_Leather_Basket")
    geometry = nt.nodes.new("ShaderNodeNewGeometry")
    facing_mix = nt.nodes.new("ShaderNodeMixRGB")
    facing_mix.blend_type = "MIX"
    facing_mix.inputs[1].default_value = (0.125, 0.034, 0.018, 1.0)
    facing_mix.inputs[2].default_value = (0.022, 0.005, 0.003, 1.0)
    nt.links.new(geometry.outputs["Backfacing"], facing_mix.inputs["Fac"])
    nt.links.new(facing_mix.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.58
    mp = _tex_coord(nt, 70.0)
    grain = nt.nodes.new("ShaderNodeTexVoronoi")
    grain.feature = "DISTANCE_TO_EDGE"
    grain.inputs["Scale"].default_value = 52.0
    nt.links.new(mp.outputs["Vector"], grain.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.24
    bump.inputs["Distance"].default_value = 0.00055
    nt.links.new(grain.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def phenolic(base_rgb, name, decal=None):
    """
    Phenolic resin: near-white core, IOR 1.5, thin clearcoat, micro-scratch.

    Amendment Patch 4: when `decal` is given it is an equirectangular map
    carrying the colour, stripe band, and both number circles. It is applied as
    a masked layer inside this node graph -- never as geometry -- so the
    numbers cannot drift off the sphere or break the silhouette.
    """
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    if decal and os.path.exists(decal):
        img = bpy.data.images.load(decal, check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Cubic"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.085
    b.inputs["IOR"].default_value = 1.50
    try:
        b.inputs["Coat Weight"].default_value = 0.85
        b.inputs["Coat Roughness"].default_value = 0.045
    except KeyError:
        pass
    mp = _tex_coord(nt, 900.0)
    scr = nt.nodes.new("ShaderNodeTexNoise")
    scr.inputs["Scale"].default_value = 260.0
    scr.inputs["Detail"].default_value = 8.0
    nt.links.new(mp.outputs["Vector"], scr.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.045
    bump.inputs["Distance"].default_value = 0.00004
    nt.links.new(scr.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def simple(name, rgb, rough, metal=0.0, ior=1.45):
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["IOR"].default_value = ior
    return m


def aged_simple(name, rgb, rough, metal=0.0, ior=1.45,
                colour_variation=0.24, micro_scale=58.0,
                bump_distance=0.0007):
    """A non-uniform finish for old painted, metal, rubber and paper goods.

    The former environment relied on many perfectly uniform ``simple``
    materials.  A century-old room does not have a uniform roughness value:
    hand contact burnishes high spots, dust dulls recesses and successive
    cleaning leaves fine directional abrasion.  This helper keeps the object
    legible while making those variations intrinsic to the surface.
    """
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["IOR"].default_value = ior

    mp = _tex_coord(nt, 1.0)
    macro = nt.nodes.new("ShaderNodeTexNoise")
    macro.inputs["Scale"].default_value = 2.6
    macro.inputs["Detail"].default_value = 7.0
    macro.inputs["Roughness"].default_value = 0.78
    nt.links.new(mp.outputs["Vector"], macro.inputs["Vector"])

    dark = tuple(max(0.0, c * (1.0 - colour_variation)) for c in rgb)
    light = tuple(min(1.0, c * (1.0 + colour_variation * 0.52) + 0.006)
                  for c in rgb)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.24
    ramp.color_ramp.elements[0].color = (*dark, 1.0)
    ramp.color_ramp.elements[1].position = 0.76
    ramp.color_ramp.elements[1].color = (*light, 1.0)
    nt.links.new(macro.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])

    rough_map = nt.nodes.new("ShaderNodeMapRange")
    rough_map.inputs["To Min"].default_value = max(0.08, rough - 0.16)
    rough_map.inputs["To Max"].default_value = min(0.99, rough + 0.18)
    nt.links.new(macro.outputs["Fac"], rough_map.inputs["Value"])
    nt.links.new(rough_map.outputs["Result"], b.inputs["Roughness"])

    micro = nt.nodes.new("ShaderNodeTexNoise")
    micro.inputs["Scale"].default_value = micro_scale
    micro.inputs["Detail"].default_value = 5.0
    micro.inputs["Roughness"].default_value = 0.68
    nt.links.new(mp.outputs["Vector"], micro.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.13
    bump.inputs["Distance"].default_value = bump_distance
    nt.links.new(micro.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m["age_layers"] = 3
    m["surface_state"] = "handled_faded_scoured"
    return m


def aged_vinyl(name, rgb):
    """Old upholstery with ground-in colour variation and fine checking."""
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = 0.58
    b.inputs["IOR"].default_value = 1.46
    try:
        b.inputs["Coat Weight"].default_value = 0.12
        b.inputs["Coat Roughness"].default_value = 0.44
    except KeyError:
        pass
    mp = _tex_coord(nt, 1.0)
    ground = nt.nodes.new("ShaderNodeTexNoise")
    ground.inputs["Scale"].default_value = 4.2
    ground.inputs["Detail"].default_value = 8.0
    ground.inputs["Roughness"].default_value = 0.78
    nt.links.new(mp.outputs["Vector"], ground.inputs["Vector"])
    ground_ramp = nt.nodes.new("ShaderNodeValToRGB")
    ground_ramp.color_ramp.elements[0].color = (
        max(0.0, rgb[0] * 0.42), max(0.0, rgb[1] * 0.42),
        max(0.0, rgb[2] * 0.42), 1.0)
    ground_ramp.color_ramp.elements[1].color = (
        min(1.0, rgb[0] * 1.18 + 0.006),
        min(1.0, rgb[1] * 1.18 + 0.006),
        min(1.0, rgb[2] * 1.18 + 0.006), 1.0)
    nt.links.new(ground.outputs["Fac"], ground_ramp.inputs["Fac"])

    check = nt.nodes.new("ShaderNodeTexVoronoi")
    check.feature = "DISTANCE_TO_EDGE"
    check.inputs["Scale"].default_value = 62.0
    nt.links.new(mp.outputs["Vector"], check.inputs["Vector"])
    crack = nt.nodes.new("ShaderNodeValToRGB")
    crack.color_ramp.elements[0].position = 0.003
    crack.color_ramp.elements[0].color = (0.52, 0.49, 0.45, 1.0)
    crack.color_ramp.elements[1].position = 0.011
    crack.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(check.outputs["Distance"], crack.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    nt.links.new(ground_ramp.outputs["Color"], mix.inputs[1])
    nt.links.new(crack.outputs["Color"], mix.inputs[2])
    nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])

    micro = nt.nodes.new("ShaderNodeTexNoise")
    micro.inputs["Scale"].default_value = 185.0
    micro.inputs["Detail"].default_value = 3.5
    nt.links.new(mp.outputs["Vector"], micro.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.19
    bump.inputs["Distance"].default_value = 0.00042
    nt.links.new(micro.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m["age_layers"] = 4
    m["surface_state"] = "checked_cracked_hand_burnished"
    return m


def clean_worn_bartop():
    """A sanitary service top whose finish, not clutter, carries its age."""
    m = aged_simple("MAT_Bar_Top_CleanWornWalnut",
                    (0.052, 0.021, 0.007), 0.43,
                    colour_variation=0.26, micro_scale=92.0,
                    bump_distance=0.00045)
    m["cleaning_state"] = "wiped_current_shift"
    m["historical_state"] = "decades_of_worn_finish"
    return m


def image_environment(name, filename, roughness=0.82, emission_strength=0.0):
    """Project-original environmental scan or luminous exterior plate."""
    m, nt, b = _new(name)
    b.inputs["Roughness"].default_value = roughness
    path = os.path.join(C.ROOT, "assets", "textures", "environment",
                        filename)
    if os.path.exists(path):
        img = bpy.data.images.load(path, check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        if emission_strength > 0.0:
            nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
            b.inputs["Emission Strength"].default_value = emission_strength
        else:
            bump = nt.nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.08
            bump.inputs["Distance"].default_value = 0.00025
            nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
            nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    m["source_asset"] = os.path.relpath(path, C.ROOT)
    m["project_original"] = True
    m["age_layers"] = 5 if emission_strength <= 0.0 else 2
    return m


def slate_mat():
    """Honed dark grey stone with a cut edge. No marble veining, no gloss."""
    m, nt, b = _new("MAT_Table_Slate_Honed")
    b.inputs["Base Color"].default_value = (0.055, 0.056, 0.060, 1.0)
    b.inputs["Roughness"].default_value = 0.74
    mp = _tex_coord(nt, 24.0)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 30.0
    n.inputs["Detail"].default_value = 6.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    nt.links.new(n.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def env_concrete_floor():
    """Neglected ground-floor slab: patched, stained, cracked, never polished."""
    m, nt, b = _new("MAT_Env_Floor_NeglectedConcrete")
    b.inputs["Roughness"].default_value = 0.91
    mp = _tex_coord(nt, 0.72)

    aggregate = nt.nodes.new("ShaderNodeTexNoise")
    aggregate.inputs["Scale"].default_value = 4.5
    aggregate.inputs["Detail"].default_value = 9.0
    aggregate.inputs["Roughness"].default_value = 0.78
    nt.links.new(mp.outputs["Vector"], aggregate.inputs["Vector"])
    base = nt.nodes.new("ShaderNodeValToRGB")
    base.color_ramp.elements[0].position = 0.26
    base.color_ramp.elements[0].color = (0.030, 0.027, 0.023, 1.0)
    base.color_ramp.elements[1].position = 0.74
    base.color_ramp.elements[1].color = (0.112, 0.103, 0.087, 1.0)
    nt.links.new(aggregate.outputs["Fac"], base.inputs["Fac"])

    # Large shrinkage cells produce a sparse network of recessed hairline
    # cracks; authored geometry below adds the few hero cracks that need shape.
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.distance = "EUCLIDEAN"
    vor.inputs["Scale"].default_value = 1.25
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    crack = nt.nodes.new("ShaderNodeValToRGB")
    crack.color_ramp.elements[0].position = 0.002
    crack.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    crack.color_ramp.elements[1].position = 0.008
    crack.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(vor.outputs["Distance"], crack.inputs["Fac"])

    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[2].default_value = (0.42, 0.39, 0.34, 1.0)
    nt.links.new(crack.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(base.outputs["Color"], mix.inputs[1])
    nt.links.new(mix.outputs["Color"], b.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = 0.14
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(crack.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])

    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.78
    rough.inputs["To Max"].default_value = 0.98
    nt.links.new(aggregate.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    return m


def tin_ceiling():
    """Old painted pressed tin: shallow stamped relief under many repaintings."""
    m, nt, b = _new("MAT_Env_TinCeiling_Painted")
    b.inputs["Base Color"].default_value = (0.082, 0.078, 0.069, 1.0)
    b.inputs["Roughness"].default_value = 0.58
    b.inputs["Metallic"].default_value = 0.28
    mp = _tex_coord(nt, 1.0)
    relief = nt.nodes.new("ShaderNodeTexVoronoi")
    relief.feature = "DISTANCE_TO_EDGE"
    relief.inputs["Scale"].default_value = 8.0
    nt.links.new(mp.outputs["Vector"], relief.inputs["Vector"])
    pits = nt.nodes.new("ShaderNodeTexNoise")
    pits.inputs["Scale"].default_value = 46.0
    pits.inputs["Detail"].default_value = 5.0
    nt.links.new(mp.outputs["Vector"], pits.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.22
    nt.links.new(relief.outputs["Distance"], mix.inputs[1])
    nt.links.new(pits.outputs["Fac"], mix.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.0022
    nt.links.new(mix.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def aged_bar_wood():
    """Old stained oak: waxy hand-polished high spots, dry open grain below."""
    m, nt, b = _new("MAT_Bar_OldStainedOak")
    b.inputs["Base Color"].default_value = (0.090, 0.044, 0.020, 1.0)
    b.inputs["Roughness"].default_value = 0.50
    mp = _tex_coord(nt, 7.5)
    stretch = nt.nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = (12.0, 0.70, 10.0)
    nt.links.new(mp.outputs["Vector"], stretch.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 8.0
    grain.inputs["Detail"].default_value = 10.0
    grain.inputs["Roughness"].default_value = 0.72
    nt.links.new(stretch.outputs["Vector"], grain.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.018, 0.007, 0.003, 1.0)
    ramp.color_ramp.elements[1].color = (0.090, 0.036, 0.013, 1.0)
    nt.links.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.32
    rough.inputs["To Max"].default_value = 0.62
    nt.links.new(grain.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.20
    bump.inputs["Distance"].default_value = 0.0011
    nt.links.new(grain.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def worn_stainless():
    """Old underbar steel: scoured, cloudy and scrubbed, never showroom chrome."""
    m, nt, b = _new("MAT_Bar_Stainless_Scoured")
    b.inputs["Base Color"].default_value = (0.42, 0.43, 0.42, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.48
    mp = _tex_coord(nt, 8.0)
    cloud = nt.nodes.new("ShaderNodeTexNoise")
    cloud.inputs["Scale"].default_value = 3.8
    cloud.inputs["Detail"].default_value = 6.0
    cloud.inputs["Roughness"].default_value = 0.72
    nt.links.new(mp.outputs["Vector"], cloud.inputs["Vector"])
    colour = nt.nodes.new("ShaderNodeValToRGB")
    colour.color_ramp.elements[0].color = (0.24, 0.25, 0.24, 1.0)
    colour.color_ramp.elements[1].color = (0.52, 0.53, 0.51, 1.0)
    nt.links.new(cloud.outputs["Fac"], colour.inputs["Fac"])
    nt.links.new(colour.outputs["Color"], b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.36
    rough.inputs["To Max"].default_value = 0.62
    nt.links.new(cloud.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    scour = nt.nodes.new("ShaderNodeTexNoise")
    scour.inputs["Scale"].default_value = 115.0
    scour.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], scour.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.00045
    nt.links.new(scour.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def painted_panel():
    """Deep bottle-green wall paneling with uneven old brush coats."""
    m, nt, b = _new("MAT_Env_Wainscot_OldGreen")
    b.inputs["Base Color"].default_value = (0.026, 0.064, 0.044, 1.0)
    b.inputs["Roughness"].default_value = 0.78
    mp = _tex_coord(nt, 3.0)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 6.0
    n.inputs["Detail"].default_value = 7.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.014, 0.034, 0.024, 1.0)
    ramp.color_ramp.elements[1].color = (0.048, 0.095, 0.062, 1.0)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.0010
    nt.links.new(n.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def image_paper(name, filename):
    """Matte project-internal scan used by a UV-mapped wall-art plane."""
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (0.38, 0.31, 0.22, 1.0)
    b.inputs["Roughness"].default_value = 0.79
    path = os.path.join(C.ROOT, "assets", "textures", "wall_art", filename)
    if os.path.exists(path):
        img = bpy.data.images.load(path, check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def old_snapshot():
    """Small abstract monochrome print used where individual faces are not read."""
    m, nt, b = _new("MAT_Prop_OldSnapshot")
    b.inputs["Roughness"].default_value = 0.86
    mp = _tex_coord(nt, 3.5)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.025, 0.021, 0.017, 1.0)
    ramp.color_ramp.elements[1].color = (0.48, 0.42, 0.32, 1.0)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def emissive(name, rgb, strength):
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = 0.28
    b.inputs["Emission Color"].default_value = (*rgb, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


def plaster():
    """Repeatedly patched plaster with faded paint and old moisture paths."""
    m, nt, b = _new("MAT_Env_Plaster_Tobacco")
    b.inputs["Roughness"].default_value = 0.91
    mp = _tex_coord(nt, 1.0)
    age = nt.nodes.new("ShaderNodeTexNoise")
    age.inputs["Scale"].default_value = 1.7
    age.inputs["Detail"].default_value = 9.0
    age.inputs["Roughness"].default_value = 0.82
    nt.links.new(mp.outputs["Vector"], age.inputs["Vector"])
    colour = nt.nodes.new("ShaderNodeValToRGB")
    colour.color_ramp.elements[0].position = 0.23
    colour.color_ramp.elements[0].color = (0.105, 0.081, 0.050, 1.0)
    colour.color_ramp.elements[1].position = 0.78
    colour.color_ramp.elements[1].color = (0.275, 0.225, 0.145, 1.0)
    nt.links.new(age.outputs["Fac"], colour.inputs["Fac"])
    nt.links.new(colour.outputs["Color"], b.inputs["Base Color"])

    tooth = nt.nodes.new("ShaderNodeTexNoise")
    tooth.inputs["Scale"].default_value = 38.0
    tooth.inputs["Detail"].default_value = 6.0
    tooth.inputs["Roughness"].default_value = 0.70
    nt.links.new(mp.outputs["Vector"], tooth.inputs["Vector"])
    br = nt.nodes.new("ShaderNodeBump")
    br.inputs["Strength"].default_value = 0.24
    br.inputs["Distance"].default_value = 0.0014
    nt.links.new(tooth.outputs["Fac"], br.inputs["Height"])
    nt.links.new(br.outputs["Normal"], b.inputs["Normal"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.82
    rr.inputs["To Max"].default_value = 0.98
    nt.links.new(age.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    m["age_layers"] = 4
    m["surface_state"] = "faded_repaired_never_freshly_painted"
    return m


def brick():
    """Irregular, dusty, mortar-rich reveal -- not a tiled red brick texture."""
    m, nt, b = _new("MAT_Env_Brick_Reveal")
    b.inputs["Base Color"].default_value = (0.092, 0.056, 0.042, 1.0)
    b.inputs["Roughness"].default_value = 0.92
    mp = _tex_coord(nt, 1.0)
    tex = nt.nodes.new("ShaderNodeTexBrick")
    tex.inputs["Scale"].default_value = 7.5
    tex.inputs["Mortar Size"].default_value = 0.022
    tex.inputs["Color1"].default_value = (0.108, 0.062, 0.046, 1.0)
    tex.inputs["Color2"].default_value = (0.078, 0.044, 0.034, 1.0)
    tex.inputs["Mortar"].default_value = (0.135, 0.128, 0.116, 1.0)
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    br = nt.nodes.new("ShaderNodeBump")
    br.inputs["Strength"].default_value = 0.55
    br.inputs["Distance"].default_value = 0.004
    nt.links.new(tex.outputs["Fac"], br.inputs["Height"])
    nt.links.new(br.outputs["Normal"], b.inputs["Normal"])
    return m


def glass(name, rough, tint):
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*tint, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.45
    b.inputs["Transmission Weight"].default_value = 0.92
    return m


def beverage(name, colour, rough=0.16, transmission=0.34):
    """A dense translucent liquid, not a second piece of tinted glass."""
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*colour, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.333
    b.inputs["Transmission Weight"].default_value = transmission
    return m


def frosted_door_glass():
    """Dirty safety glass that transmits street glow without becoming white."""
    m, nt, b = _new("MAT_Env_Glass_FrontDoorFrosted")
    b.inputs["Base Color"].default_value = (0.055, 0.085, 0.075, 1.0)
    b.inputs["Roughness"].default_value = 0.48
    b.inputs["IOR"].default_value = 1.45
    b.inputs["Transmission Weight"].default_value = 0.46
    return m


def mirror_aged():
    """Back-bar mirror: cleaned centre, desilvered perimeter."""
    m, nt, b = _new("MAT_Bar_Mirror_Desilvered")
    b.inputs["Base Color"].default_value = (0.46, 0.43, 0.37, 1.0)
    b.inputs["Metallic"].default_value = 0.92
    b.inputs["Roughness"].default_value = 0.13
    mp = _tex_coord(nt, 1.6)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 3.2
    n.inputs["Detail"].default_value = 7.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    colour = nt.nodes.new("ShaderNodeValToRGB")
    colour.color_ramp.elements[0].position = 0.36
    colour.color_ramp.elements[0].color = (0.045, 0.028, 0.018, 1.0)
    colour.color_ramp.elements[1].position = 0.67
    colour.color_ramp.elements[1].color = (0.42, 0.40, 0.35, 1.0)
    nt.links.new(n.outputs["Fac"], colour.inputs["Fac"])
    nt.links.new(colour.outputs["Color"], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.09
    rr.inputs["To Max"].default_value = 0.31      # desilvered patches scatter
    nt.links.new(n.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    metal = nt.nodes.new("ShaderNodeMapRange")
    metal.inputs["To Min"].default_value = 0.28
    metal.inputs["To Max"].default_value = 0.94
    nt.links.new(n.outputs["Fac"], metal.inputs["Value"])
    nt.links.new(metal.outputs["Result"], b.inputs["Metallic"])
    return m


def build():
    walnut_mat = walnut()
    mats = {
        "walnut": walnut_mat,
        "walnut_cross": walnut_cross_grain(walnut_mat),
        "cloth": cloth(),
        "cloth_bed": cloth_bed(),
        "cloth_facing": cloth_pocket_facing(),
        "cloth_liner": cloth_pocket_liner(),
        "leather": leather(),
        "leather_interior": leather_interior(),
        "leather_basket": leather_basket(),
        "slate": slate_mat(),
        "blacksteel": aged_simple("MAT_Metal_BlackenedSteel",
                                   (0.048, 0.046, 0.043), 0.48, metal=1.0,
                                   colour_variation=0.34, micro_scale=105.0,
                                   bump_distance=0.00035),
        "brass": aged_simple("MAT_Metal_AgedBrass",
                              (0.36, 0.26, 0.10), 0.40, metal=1.0,
                              colour_variation=0.38, micro_scale=82.0,
                              bump_distance=0.00035),
        "pearl": simple("MAT_Inlay_MotherOfPearl", (0.84, 0.83, 0.78), 0.11,
                        ior=1.53),
        "facing": simple("MAT_Pocket_Facing_Rubber", (0.022, 0.022, 0.024),
                         0.62),
        "chrome": simple("MAT_Metal_Chrome", (0.78, 0.79, 0.80), 0.10,
                         metal=1.0),
        "floor": env_concrete_floor(),
        "floor_crack": simple("MAT_Env_Floor_Crack", (0.010, 0.008, 0.006),
                              0.96),
        "concrete_patch": simple("MAT_Env_Floor_ExposedAggregate",
                                  (0.073, 0.069, 0.061), 0.98),
        "stain_dark": simple("MAT_Env_Floor_OilAndBeerStain",
                             (0.028, 0.017, 0.008), 0.48),
        "stain_rust": simple("MAT_Env_Floor_RustBloom", (0.12, 0.034, 0.010),
                             0.76),
        "stain_beer": simple("MAT_Env_Floor_DriedBeer", (0.070, 0.038, 0.010),
                             0.58),
        "floor_resin": simple("MAT_Env_Floor_OldResinPlug",
                               (0.20, 0.19, 0.16), 0.90),
        "dust": simple("MAT_Env_Dust", (0.16, 0.135, 0.098), 0.98),
        "cast_iron": simple("MAT_Prop_CastIron_OldRegister",
                            (0.028, 0.026, 0.024), 0.56, metal=0.86),
        # Chased cast bronze for the ornate register body: strong roughness
        # variation plus a deep fine bump so the surface reads as scrolled
        # relief rather than smooth sheet metal at render distance.
        "bronze_ornate": aged_simple("MAT_Prop_CastBronze_Ornate",
                                      (0.285, 0.185, 0.075), 0.34, metal=1.0,
                                      colour_variation=0.55,
                                      micro_scale=310.0,
                                      bump_distance=0.0013),
        "ivory_key": simple("MAT_Prop_IvoryKeyCap",
                            (0.78, 0.74, 0.63), 0.30),
        "bar_wood": aged_bar_wood(),
        "wall_panel": painted_panel(),
        "plaster": plaster(),
        "brick": brick(),
        "tin": tin_ceiling(),
        "paint_trim": aged_simple("MAT_Env_Paint_Trim",
                                   (0.055, 0.062, 0.058), 0.78,
                                   colour_variation=0.30),
        "paint_door": aged_simple("MAT_Env_Paint_Door",
                                   (0.048, 0.036, 0.032), 0.80,
                                   colour_variation=0.38),
        "paint_rad": aged_simple("MAT_Env_Paint_Radiator",
                                  (0.115, 0.108, 0.096), 0.74,
                                  colour_variation=0.31, micro_scale=76.0),
        "conduit": aged_simple("MAT_Env_Conduit",
                                (0.088, 0.086, 0.084), 0.55, metal=0.85,
                                colour_variation=0.30, micro_scale=118.0,
                                bump_distance=0.00030),
        "bartop": clean_worn_bartop(),
        "stainless": worn_stainless(),
        "vinyl_red": aged_vinyl("MAT_Bar_Vinyl_Oxblood",
                                 (0.105, 0.022, 0.020)),
        "vinyl_green": aged_vinyl("MAT_Bar_Vinyl_FadedBottleGreen",
                                   (0.018, 0.060, 0.041)),
        "bar_rubber": aged_simple("MAT_Bar_RubberMat_OldBlack",
                                   (0.012, 0.013, 0.012), 0.80,
                                   colour_variation=0.50, micro_scale=140.0,
                                   bump_distance=0.00032),
        "towel_dirty": aged_simple("MAT_Bar_Towel_WashedGrey",
                                    (0.31, 0.30, 0.27), 0.98,
                                    colour_variation=0.18,
                                    micro_scale=170.0,
                                    bump_distance=0.00055),
        "ice": glass("MAT_Bar_Ice_Cloudy", 0.18, (0.68, 0.82, 0.88)),
        "garnish_lime": aged_simple("MAT_Bar_Garnish_Lime",
                                     (0.055, 0.19, 0.025), 0.72,
                                     colour_variation=0.18,
                                     micro_scale=130.0,
                                     bump_distance=0.00028),
        "garnish_orange": aged_simple("MAT_Bar_Garnish_Orange",
                                       (0.42, 0.075, 0.012), 0.68,
                                       colour_variation=0.16,
                                       micro_scale=145.0,
                                       bump_distance=0.00035),
        "fruit_apple": aged_simple("MAT_Bar_Fruit_Apple",
                                    (0.28, 0.045, 0.025), 0.58,
                                    colour_variation=0.24,
                                    micro_scale=110.0,
                                    bump_distance=0.00030),
        "fruit_lemon": aged_simple("MAT_Bar_Fruit_Lemon",
                                    (0.46, 0.29, 0.025), 0.66,
                                    colour_variation=0.15,
                                    micro_scale=155.0,
                                    bump_distance=0.00036),
        "enamel_green": aged_simple("MAT_Fixture_Enamel_Green",
                                     (0.020, 0.062, 0.038), 0.40,
                                     colour_variation=0.30,
                                     micro_scale=96.0,
                                     bump_distance=0.00028),
        "enamel_white": aged_simple("MAT_Fixture_Enamel_White",
                                     (0.76, 0.72, 0.62), 0.52,
                                     colour_variation=0.24,
                                     micro_scale=88.0,
                                     bump_distance=0.00030),
        "glass_dirty": glass("MAT_Env_Glass_Storefront", 0.14,
                             (0.72, 0.78, 0.80)),
        "glass_door": frosted_door_glass(),
        "glass_bottle": glass("MAT_Bar_Glass_Bottle", 0.05,
                              (0.28, 0.34, 0.22)),
        "glass_amber": glass("MAT_Bar_Glass_Amber", 0.08,
                             (0.34, 0.13, 0.035)),
        "glass_clear": glass("MAT_Bar_Glass_Clear", 0.06,
                             (0.75, 0.78, 0.72)),
        "beer_amber": beverage("MAT_Service_Beer_Amber",
                                (0.66, 0.235, 0.018), 0.16, 0.12),
        "cocktail_amber": beverage("MAT_Service_Cocktail_Amber",
                                    (0.23, 0.052, 0.010), 0.15, 0.30),
        "beer_foam": aged_simple("MAT_Service_Beer_Foam",
                                   (0.90, 0.79, 0.58), 0.84,
                                   colour_variation=0.12,
                                   micro_scale=210.0,
                                   bump_distance=0.00018),
        "lime_pulp": aged_simple("MAT_Service_Lime_Pulp",
                                   (0.28, 0.48, 0.075), 0.69,
                                   colour_variation=0.12,
                                   micro_scale=180.0,
                                   bump_distance=0.00020),
        "straw_black": simple("MAT_Service_Straw_Black",
                                (0.008, 0.008, 0.007), 0.30),
        "straw_red": simple("MAT_Service_Straw_FadedRed",
                              (0.38, 0.018, 0.012), 0.32),
        "coaster_pulp": aged_simple("MAT_Service_Coaster_Pulp",
                                      (0.25, 0.18, 0.095), 0.94,
                                      colour_variation=0.16,
                                      micro_scale=195.0,
                                      bump_distance=0.00022),
        "coaster_print": aged_simple("MAT_Service_Coaster_FadedInk",
                                       (0.31, 0.025, 0.018), 0.88,
                                       colour_variation=0.12,
                                       micro_scale=160.0,
                                       bump_distance=0.00012),
        "condensation": glass("MAT_Service_Condensation", 0.035,
                               (0.78, 0.88, 0.92)),
        "paper_aged": aged_simple("MAT_Prop_Paper_Aged",
                                   (0.42, 0.34, 0.22), 0.91,
                                   colour_variation=0.34,
                                   micro_scale=165.0,
                                   bump_distance=0.00022),
        "paper_red": aged_simple("MAT_Prop_Paper_FadedRed",
                                  (0.30, 0.055, 0.035), 0.89,
                                  colour_variation=0.38,
                                  micro_scale=155.0,
                                  bump_distance=0.00022),
        "foam_yellow": aged_simple("MAT_Prop_ExposedSeatFoam",
                                    (0.32, 0.19, 0.045), 0.98,
                                    colour_variation=0.45,
                                    micro_scale=92.0,
                                    bump_distance=0.00090),
        "tape_black": aged_simple("MAT_Prop_OldBlackRepairTape",
                                   (0.018, 0.017, 0.015), 0.48,
                                   colour_variation=0.55,
                                   micro_scale=130.0,
                                   bump_distance=0.00025),
        "cork": aged_simple("MAT_Prop_OldCork", (0.18, 0.105, 0.045),
                             0.95, colour_variation=0.40,
                             micro_scale=82.0,
                             bump_distance=0.0010),
        "old_snapshot": old_snapshot(),
        "frame_dark": aged_simple("MAT_Prop_Frame_DarkWood",
                                   (0.035, 0.018, 0.010), 0.66,
                                   colour_variation=0.44,
                                   micro_scale=70.0,
                                   bump_distance=0.00075),
        "tv_screen": simple("MAT_Prop_CRT_ScreenOff", (0.010, 0.018, 0.021),
                            0.24, ior=1.48),
        "neon_red": emissive("MAT_Prop_NeonRed", (0.72, 0.025, 0.018), 5.0),
        "bulb_warm": emissive("MAT_Fixture_WarmBulb",
                                (0.92, 0.57, 0.24), 3.2),
        "exit_red": emissive("MAT_Fixture_ExitSignRed",
                               (0.88, 0.018, 0.008), 4.2),
        "art_payphones": image_paper("MAT_Art_Payphones_1988",
                                     "payphones_1988.png"),
        "art_tuesday_8ball": image_paper("MAT_Art_Tuesday8Ball_1993",
                                         "tuesday_8ball_1993.png"),
        "art_sticker_wall": image_paper("MAT_Art_StickerWall_1982_1999",
                                        "sticker_wall_1982_1999.png"),
        "art_pool_team": image_paper("MAT_Art_PoolTeam_1986",
                                     "pool_team_1986.png"),
        "art_memory_wall": image_paper("MAT_Art_MemoryWall_1978_1998",
                                        "memory_wall_1978_1998.png"),
        "sticker_bomb": image_environment(
            "MAT_Env_BathroomStickerBomb_1980_2005",
            "bathroom_sticker_bomb_v2.png", 0.86),
        "wheatpaste_history": image_environment(
            "MAT_Env_WheatpasteWallHistory",
            "wheatpaste_wall_history_v2.png", 0.92),
        "street_backdrop": image_environment(
            "MAT_Env_LESNightStreetBackdrop",
            "les_night_street_v2.png", 0.40, emission_strength=1.7),
        "plaster_crack": aged_simple("MAT_Env_PlasterCrack",
                                     (0.020, 0.014, 0.009), 0.98,
                                     colour_variation=0.28,
                                     micro_scale=150.0,
                                     bump_distance=0.0002),
        "plaster_exposed": aged_simple("MAT_Env_PlasterExposed",
                                       (0.215, 0.184, 0.128), 0.98,
                                       colour_variation=0.38,
                                       micro_scale=72.0,
                                       bump_distance=0.0011),
        "wall_watermark": aged_simple("MAT_Env_OldWatermark",
                                      (0.075, 0.053, 0.029), 0.92,
                                      colour_variation=0.40,
                                      micro_scale=64.0,
                                      bump_distance=0.00025),
        "beam_wood": aged_simple("MAT_Env_CrossBeam_OldTimber",
                                  (0.043, 0.024, 0.012), 0.78,
                                  colour_variation=0.48,
                                  micro_scale=46.0,
                                  bump_distance=0.0013),
        "wood_water_ring": aged_simple("MAT_Prop_WoodWaterRingGhost",
                                        (0.070, 0.035, 0.012), 0.82,
                                        colour_variation=0.10,
                                        micro_scale=145.0,
                                        bump_distance=0.00018),
        "wood_exposed": aged_simple("MAT_Prop_WoodFinishLoss",
                                     (0.080, 0.038, 0.013), 0.88,
                                     colour_variation=0.34,
                                     micro_scale=82.0,
                                     bump_distance=0.00048),
        "vinyl_crack": aged_simple("MAT_Prop_VinylCrack",
                                    (0.009, 0.006, 0.005), 0.93,
                                    colour_variation=0.20,
                                    micro_scale=180.0,
                                    bump_distance=0.0002),
        "vinyl_crack_red": aged_simple("MAT_Prop_VinylCrack_Oxblood",
                                        (0.040, 0.007, 0.006), 0.88,
                                        colour_variation=0.12,
                                        micro_scale=190.0,
                                        bump_distance=0.00012),
        "vinyl_crack_green": aged_simple("MAT_Prop_VinylCrack_Green",
                                          (0.006, 0.022, 0.012), 0.90,
                                          colour_variation=0.12,
                                          micro_scale=190.0,
                                          bump_distance=0.00012),
        "neon_blue": emissive("MAT_Prop_NeonBlue",
                               (0.018, 0.18, 0.82), 6.0),
        "neon_green": emissive("MAT_Prop_NeonGreen",
                                (0.025, 0.68, 0.22), 5.4),
        "neon_amber": emissive("MAT_Prop_NeonAmber",
                                (0.95, 0.24, 0.015), 5.2),
        "service_glow": emissive("MAT_Env_ServiceDoor_UnderGlow",
                                   (0.46, 0.64, 0.82), 1.8),
        "backbar_tube": emissive("MAT_Bar_OldFluorescentTube",
                                   (0.78, 0.54, 0.31), 2.8),
        "mirror_aged": mirror_aged(),
    }
    # The basket catch pads need the deep-shadow leather in EVERY build path.
    # It used to exist only via 23_rebuild_pool_system.py's derived injection,
    # so a full build_all reconstruction silently fell back to plain leather
    # and failed the basket-base validator. Same derivation, same values.
    shadow = bpy.data.materials.get("MAT_Pocket_Leather_DeepShadow")
    if shadow is None:
        shadow = mats["leather_interior"].copy()
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
    mats["leather_shadow"] = shadow
    print("  [materials] %d built" % len(mats))
    return mats


if __name__ == "__main__":
    build()
