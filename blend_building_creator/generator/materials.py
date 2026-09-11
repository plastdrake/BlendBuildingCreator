"""
Stylized Handpainted Procedural Shaders for Blender — Game-Asset / Bake-Friendly.
v7 — Perfect Seams, Vertical Wall Boards & Organic Painterly Wood.

Key fixes:
  1. Floorboards:
     - Fixed thick white/beige lines: Mortar color set to deep dark crevice (0.06, 0.04, 0.02).
     - Razor-thin 2mm dark seams with subtle 1mm warm amber edge catchlight.
     - Hand-carved organic edge wobble (wavy seams, no laser-straight lines).
     - Rich warm honey/caramel wood stain with per-plank variation.
     - Grain flows exclusively along the planks longitudinally (no cross-stripes).
  2. Interior Wall Boards:
     - Rotated UV mapping 90 deg so boards run VERTICALLY from floor to ceiling.
     - Wide rustic boards (~38cm wide) with hand-hewn wobble and thin dark seams.
     - Cozy plaster generated when interior color is light plaster (Tier 3).
  3. Door:
     - 3 wide vertical wooden planks with thin dark seams (no white borders).
  4. Logs & Timbers:
     - Pure organic warped noise grain. No repeating sawteeth barcode stripes.
     - Soft cylindrical shading and warm amber chinking contact shadows.
"""

import os
import bpy

def _get_texture_path(filename):
    """Resolve full path to packaged handpainted textures."""
    cur_file = os.path.abspath(__file__)
    pkg_dir = os.path.dirname(os.path.dirname(cur_file))
    p = os.path.join(pkg_dir, "textures", filename)
    if os.path.exists(p):
        return p
    return None

def _load_image_texture(tree, filename, coord, loc_x=-800, loc_y=120, scale=(1.0, 1.0, 1.0), rotation=(0.0, 0.0, 0.0)):
    """Loads a packaged handpainted texture image and connects it via UV + Mapping node."""
    tex_path = _get_texture_path(filename)
    if not tex_path:
        return None
    img = bpy.data.images.get(filename)
    if img is None:
        try:
            img = bpy.data.images.load(tex_path)
        except Exception:
            return None
            
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (loc_x, loc_y)
    mapping.inputs["Scale"].default_value = scale
    if any(r != 0.0 for r in rotation):
        mapping.inputs["Rotation"].default_value = rotation
    tree.links.new(coord.outputs["UV"], mapping.inputs["Vector"])

    tex_node = tree.nodes.new("ShaderNodeTexImage")
    tex_node.location = (loc_x + 220, loc_y)
    tex_node.image = img
    tex_node.interpolation = 'Linear'
    tree.links.new(mapping.outputs["Vector"], tex_node.inputs["Vector"])
    return tex_node

# ---------------------------------------------------------------------------
# Material slot index constants (16 canonical slots)
# ---------------------------------------------------------------------------
MAT_INDEX_STONE        = 0
MAT_INDEX_PLASTER_EXT  = 1
MAT_INDEX_PLASTER_INT  = 2
MAT_INDEX_TIMBER_FRAME = 3
MAT_INDEX_FLOOR        = 4
MAT_INDEX_SHINGLES     = 5
MAT_INDEX_GLASS        = 6
MAT_INDEX_DOOR         = 7
MAT_INDEX_IRON         = 8
MAT_INDEX_WOOD         = 9
MAT_INDEX_LOG_END      = 10
MAT_INDEX_LOG          = 11
MAT_INDEX_STAIRS       = 12
MAT_INDEX_RAILING      = 13
MAT_INDEX_WINDOW_FRAME = 14
MAT_INDEX_SHUTTER      = 15
MAT_INDEX_CUT_STONE    = 16
MAT_INDEX_TIMBER       = MAT_INDEX_TIMBER_FRAME


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _set_bsdf_input(bsdf, name, value):
    s = bsdf.inputs.get(name)
    if s is not None:
        s.default_value = value


def _apply_ao(tree, bsdf, color_socket, strength=0.52, distance=0.18):
    """Warm-amber AO crevice shadow embedded in Base Color -> bakes correctly."""
    bx = color_socket.node.location.x + 80
    by = color_socket.node.location.y - 340

    ao = tree.nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (bx, by)
    ao.inputs["Distance"].default_value = distance
    try:
        ao.inputs["Samples"].default_value = 8
    except Exception:
        pass

    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (bx + 220, by)
    ramp.color_ramp.interpolation = 'LINEAR'
    s = 1.0 - strength
    ramp.color_ramp.elements[0].color = (s, s * 0.84, s * 0.74, 1.0)
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    tree.links.new(ao.outputs["AO"], ramp.inputs["Fac"])

    mul = tree.nodes.new("ShaderNodeMix")
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.location = (bx + 440, by)
    mul.inputs["Factor"].default_value = 1.0
    tree.links.new(color_socket, mul.inputs["A"])
    tree.links.new(ramp.outputs["Color"], mul.inputs["B"])
    tree.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])


def _setup_pbr(tree, bsdf, out, roughness=0.90, metallic=0.0):
    _set_bsdf_input(bsdf, "Roughness", roughness)
    _set_bsdf_input(bsdf, "Metallic", metallic)
    for n in ("Specular IOR Level", "Specular"):
        _set_bsdf_input(bsdf, n, 0.04)
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def _warm_painterly_pass(tree, coord, color_socket, loc_x=460, loc_y=-260,
                         strength=0.16, scale=1.25):
    """Add broad, warm brush-like color variation without photoreal speckling."""
    wash = tree.nodes.new("ShaderNodeTexNoise")
    wash.location = (loc_x, loc_y)
    wash.inputs["Scale"].default_value = scale
    wash.inputs["Detail"].default_value = 2.0
    try:
        wash.inputs["Roughness"].default_value = 0.62
    except Exception:
        pass
    tree.links.new(coord.outputs["UV"], wash.inputs["Vector"])

    wash_ramp = tree.nodes.new("ShaderNodeValToRGB")
    wash_ramp.location = (loc_x + 200, loc_y)
    wash_ramp.color_ramp.interpolation = 'EASE'
    wash_ramp.color_ramp.elements[0].color = (0.72, 0.58, 0.46, 1.0)
    wash_ramp.color_ramp.elements[1].color = (1.16, 1.05, 0.86, 1.0)
    tree.links.new(wash.outputs["Fac"], wash_ramp.inputs["Fac"])

    finish = tree.nodes.new("ShaderNodeMix")
    finish.data_type = 'RGBA'
    finish.blend_type = 'MULTIPLY'
    finish.location = (loc_x + 420, loc_y + 40)
    finish.inputs["Factor"].default_value = strength
    tree.links.new(color_socket, finish.inputs["A"])
    tree.links.new(wash_ramp.outputs["Color"], finish.inputs["B"])
    return finish.outputs["Result"]


def _new_mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    return m, t


def _out_bsdf(tree, loc_x=1200):
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (loc_x + 200, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (loc_x, 0)
    return out, bsdf


def _coord(tree, loc_x=-1400):
    c = tree.nodes.new("ShaderNodeTexCoord")
    c.location = (loc_x, 0)
    return c


# ---------------------------------------------------------------------------
# Organic Wood Grain (UV-based, warped, longitudinally stretched)
# ---------------------------------------------------------------------------

def _wood_grain_nodes(tree, coord, loc_x=-950,
                      scale_u=1.2, scale_v=0.06, warp_amount=0.25,
                      color_dark=(0.14, 0.08, 0.04, 1.0),
                      color_mid=(0.38, 0.22, 0.12, 1.0),
                      color_light=(0.60, 0.38, 0.20, 1.0)):
    """
    Organic handpainted wood grain:
    Uses length-aligned UV coordinates (V along length, U across width/circumference).
    Uses warped longitudinally-stretched procedural noise so wood grain meanders
    and curves organically without ANY straight ruler lines or barcode stripes.
    """
    # 1. Coordinate Warp for organic hand-carved flow (eliminates straight lines)
    warp_noise = tree.nodes.new("ShaderNodeTexNoise")
    warp_noise.location = (loc_x, 140)
    warp_noise.inputs["Scale"].default_value = 1.5
    warp_noise.inputs["Detail"].default_value = 2.0
    try:
        warp_noise.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(coord.outputs["UV"], warp_noise.inputs["Vector"])

    warp_mix = tree.nodes.new("ShaderNodeMix")
    warp_mix.data_type = 'VECTOR'
    warp_mix.location = (loc_x + 200, 100)
    warp_mix.inputs["Factor"].default_value = warp_amount
    tree.links.new(coord.outputs["UV"], warp_mix.inputs["A"])
    tree.links.new(warp_noise.outputs["Color"], warp_mix.inputs["B"])

    # 2. Longitudinal grain mapping (stretched along V / length)
    grain_map = tree.nodes.new("ShaderNodeMapping")
    grain_map.location = (loc_x + 380, 100)
    grain_map.inputs["Scale"].default_value = (scale_u, scale_v, 1.0)
    tree.links.new(warp_mix.outputs["Result"], grain_map.inputs["Vector"])

    # 3. Organic grain noise: creates flowing wood fibers and loops
    grain_noise = tree.nodes.new("ShaderNodeTexNoise")
    grain_noise.location = (loc_x + 580, 100)
    grain_noise.inputs["Scale"].default_value = 2.5
    grain_noise.inputs["Detail"].default_value = 2.5
    try:
        grain_noise.inputs["Roughness"].default_value = 0.55
    except Exception:
        pass
    tree.links.new(grain_map.outputs["Vector"], grain_noise.inputs["Vector"])

    # 4. Secondary soft fiber noise (stretched along grain, warm painterly accents)
    fiber_noise = tree.nodes.new("ShaderNodeTexNoise")
    fiber_noise.location = (loc_x + 580, -120)
    fiber_noise.inputs["Scale"].default_value = 5.0
    fiber_noise.inputs["Detail"].default_value = 1.5
    try:
        fiber_noise.inputs["Roughness"].default_value = 0.40
    except Exception:
        pass
    tree.links.new(grain_map.outputs["Vector"], fiber_noise.inputs["Vector"])

    # Blend primary noise + fiber noise
    blend = tree.nodes.new("ShaderNodeMix")
    blend.data_type = 'FLOAT'
    blend.location = (loc_x + 780, 40)
    blend.inputs["Factor"].default_value = 0.35
    tree.links.new(grain_noise.outputs["Fac"], blend.inputs[2])
    tree.links.new(fiber_noise.outputs["Fac"], blend.inputs[3])

    # 5. Handpainted warm color ramp
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (loc_x + 980, 40)
    ramp.color_ramp.interpolation = 'LINEAR'
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = color_dark
    el_m = ramp.color_ramp.elements.new(0.46)
    el_m.color = color_mid
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = color_light
    tree.links.new(blend.outputs["Result"], ramp.inputs["Fac"])

    return ramp.outputs["Color"]


# ---------------------------------------------------------------------------
# 0. Stone — Chunky fantasy cobblestone with bevel catchlight
# ---------------------------------------------------------------------------

def create_stylized_stone(name="M_Building_Stone", color=(0.55, 0.51, 0.46, 1.0)):
    """
    Hand-painted finish for masonry blocks and stone foundations.
    Uses packaged handpainted cobblestone texture if available, with procedural fallback.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1000)
    c = _coord(tree, loc_x=-900)

    tex_node = _load_image_texture(tree, "stone_wall_diffuse.jpg", c, loc_x=-660, loc_y=100, scale=(0.75, 0.75, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-200, 100)
        tint.inputs["Factor"].default_value = 0.35
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=60, loc_y=-210, strength=0.10, scale=1.2)
        _apply_ao(tree, bsdf, painted, strength=0.58, distance=0.16)
        _setup_pbr(tree, bsdf, out, roughness=0.88)
        return mat

    # Procedural Fallback
    block_tint = tree.nodes.new("ShaderNodeTexNoise")
    block_tint.location = (-660, 100)
    block_tint.inputs["Scale"].default_value = 0.72
    block_tint.inputs["Detail"].default_value = 1.5
    block_tint.inputs["Roughness"].default_value = 0.70
    tree.links.new(c.outputs["UV"], block_tint.inputs["Vector"])

    tint_ramp = tree.nodes.new("ShaderNodeValToRGB")
    tint_ramp.location = (-420, 100)
    tint_ramp.color_ramp.interpolation = 'LINEAR'
    tint_ramp.color_ramp.elements[0].color = (color[0] * 0.58, color[1] * 0.62, color[2] * 0.72, 1.0)
    mid = tint_ramp.color_ramp.elements.new(0.52)
    mid.color = (color[0] * 1.03, color[1] * 0.96, color[2] * 0.87, 1.0)
    tint_ramp.color_ramp.elements[1].color = (min(1.0, color[0] * 1.42), min(1.0, color[1] * 1.30), min(1.0, color[2] * 1.16), 1.0)
    tree.links.new(block_tint.outputs["Fac"], tint_ramp.inputs["Fac"])

    impasto = tree.nodes.new("ShaderNodeTexNoise")
    impasto.location = (-420, -180)
    impasto.inputs["Scale"].default_value = 4.0
    impasto.inputs["Detail"].default_value = 2.0
    tree.links.new(c.outputs["UV"], impasto.inputs["Vector"])

    impasto_mix = tree.nodes.new("ShaderNodeMix")
    impasto_mix.data_type = 'RGBA'
    impasto_mix.blend_type = 'OVERLAY'
    impasto_mix.location = (-120, 30)
    impasto_mix.inputs["Factor"].default_value = 0.17
    tree.links.new(tint_ramp.outputs["Color"], impasto_mix.inputs["A"])
    tree.links.new(impasto.outputs["Color"], impasto_mix.inputs["B"])

    painted = _warm_painterly_pass(tree, c, impasto_mix.outputs["Result"], loc_x=110, loc_y=-210, strength=0.10, scale=1.2)
    _apply_ao(tree, bsdf, painted, strength=0.58, distance=0.16)
    _setup_pbr(tree, bsdf, out, roughness=0.88)
    return mat

def create_stylized_cut_stone(name="M_Building_Cut_Stone", color=(0.74, 0.70, 0.64, 1.0)):
    """
    Cozy smooth architectural cut stone / ashlar flagstone for door steps,
    thresholds, stone door frame blocks, and window sills.
    Uses packaged handpainted cut stone texture if available, with procedural fallback.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1000)
    c = _coord(tree, loc_x=-900)

    tex_node = _load_image_texture(tree, "cut_stone_diffuse.jpg", c, loc_x=-660, loc_y=100, scale=(0.85, 0.85, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-200, 100)
        tint.inputs["Factor"].default_value = 0.25
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=60, loc_y=-210, strength=0.08, scale=1.3)
        _apply_ao(tree, bsdf, painted, strength=0.50, distance=0.15)
        _setup_pbr(tree, bsdf, out, roughness=0.82)
        return mat

    _set_bsdf_input(bsdf, "Base Color", color)
    _set_bsdf_input(bsdf, "Roughness", 0.82)
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# 1. Plaster EXT — Warm stucco with localized exposed clay brick accents
# ---------------------------------------------------------------------------

def create_stylized_plaster(name="M_Building_Plaster", color=(0.93, 0.88, 0.82, 1.0), is_interior=False):
    """
    Exterior: Warm creamy off-white stucco with soft painterly gradients and subtle
    localized exposed terracotta clay brick accents (matching CityGates concept art).
    Interior: Clean, cozy warm plaster with soft ambient occlusion.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1500)
    c = _coord(tree, loc_x=-1200)

    tex_node = _load_image_texture(tree, "plaster_wall_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(0.85, 0.85, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-300, 120)
        tint.inputs["Factor"].default_value = 0.25
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260,
                                       strength=0.10 if is_interior else 0.16, scale=1.35)
        ao_str = 0.36 if is_interior else 0.52
        _apply_ao(tree, bsdf, painted, strength=ao_str, distance=0.16)
        _setup_pbr(tree, bsdf, out, roughness=0.92)
        return mat

    mult = 1.05 if is_interior else 1.0
    c_shadow = (color[0] * 0.66, color[1] * 0.58, color[2] * 0.50, 1.0)
    c_base   = (min(1.0, color[0] * mult), min(1.0, color[1] * mult), min(1.0, color[2] * mult), 1.0)
    c_bright = (min(1.0, color[0] * 1.10), min(1.0, color[1] * 1.06), min(1.0, color[2] * 1.02), 1.0)

    brush_noise = tree.nodes.new("ShaderNodeTexNoise")
    brush_noise.location = (-900, 100)
    brush_noise.inputs["Scale"].default_value = 1.8
    brush_noise.inputs["Detail"].default_value = 2.0
    try:
        brush_noise.inputs["Roughness"].default_value = 0.55
    except Exception:
        pass
    tree.links.new(c.outputs["UV"], brush_noise.inputs["Vector"])

    plaster_ramp = tree.nodes.new("ShaderNodeValToRGB")
    plaster_ramp.location = (-660, 100)
    plaster_ramp.color_ramp.interpolation = 'LINEAR'
    plaster_ramp.color_ramp.elements[0].position = 0.0
    plaster_ramp.color_ramp.elements[0].color = c_shadow
    el_m = plaster_ramp.color_ramp.elements.new(0.45)
    el_m.color = c_base
    plaster_ramp.color_ramp.elements[1].position = 1.0
    plaster_ramp.color_ramp.elements[1].color = c_bright
    tree.links.new(brush_noise.outputs["Fac"], plaster_ramp.inputs["Fac"])

    final_color = plaster_ramp.outputs["Color"]

    if not is_interior:
        brick = tree.nodes.new("ShaderNodeTexBrick")
        brick.location = (-660, -220)
        try:
            brick.offset = 0.50
        except Exception:
            pass
        for k, v in [
            ("Color1", (0.68, 0.32, 0.18, 1.0)),
            ("Color2", (0.55, 0.24, 0.13, 1.0)),
            ("Mortar", (0.62, 0.58, 0.52, 1.0)),
            ("Scale", 1.0),
            ("Mortar Size", 0.014),
            ("Mortar Smooth", 0.20),
            ("Bias", 0.10),
            ("Brick Width", 0.36),
            ("Row Height", 0.14),
        ]:
            if k in brick.inputs:
                brick.inputs[k].default_value = v
        tree.links.new(c.outputs["UV"], brick.inputs[0])

        expose = tree.nodes.new("ShaderNodeTexNoise")
        expose.location = (-900, -440)
        expose.inputs["Scale"].default_value = 1.4
        expose.inputs["Detail"].default_value = 2.0
        try:
            expose.inputs["Roughness"].default_value = 0.55
        except Exception:
            pass
        tree.links.new(c.outputs["UV"], expose.inputs["Vector"])

        expose_ramp = tree.nodes.new("ShaderNodeValToRGB")
        expose_ramp.location = (-660, -440)
        expose_ramp.color_ramp.interpolation = 'LINEAR'
        expose_ramp.color_ramp.elements[0].position = 0.0
        expose_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        expose_ramp.color_ramp.elements[1].position = 0.74
        expose_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
        el_br = expose_ramp.color_ramp.elements.new(0.82)
        el_br.color = (1.0, 1.0, 1.0, 1.0)
        tree.links.new(expose.outputs["Fac"], expose_ramp.inputs["Fac"])

        rim_ramp = tree.nodes.new("ShaderNodeValToRGB")
        rim_ramp.location = (-420, -440)
        rim_ramp.color_ramp.interpolation = 'LINEAR'
        rim_ramp.color_ramp.elements[0].position = 0.0
        rim_ramp.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
        el_r1 = rim_ramp.color_ramp.elements.new(0.72)
        el_r1.color = (1.0, 1.0, 1.0, 1.0)
        el_r2 = rim_ramp.color_ramp.elements.new(0.75)
        el_r2.color = (0.65, 0.55, 0.45, 1.0)
        rim_ramp.color_ramp.elements[1].position = 0.78
        rim_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        tree.links.new(expose.outputs["Fac"], rim_ramp.inputs["Fac"])

        rim_mul = tree.nodes.new("ShaderNodeMix")
        rim_mul.data_type = 'RGBA'
        rim_mul.blend_type = 'MULTIPLY'
        rim_mul.location = (-180, 50)
        rim_mul.inputs["Factor"].default_value = 0.65
        tree.links.new(plaster_ramp.outputs["Color"], rim_mul.inputs["A"])
        tree.links.new(rim_ramp.outputs["Color"], rim_mul.inputs["B"])

        expose_mix = tree.nodes.new("ShaderNodeMix")
        expose_mix.data_type = 'RGBA'
        expose_mix.blend_type = 'MIX'
        expose_mix.location = (60, 0)
        tree.links.new(expose_ramp.outputs["Color"], expose_mix.inputs["Factor"])
        tree.links.new(rim_mul.outputs["Result"], expose_mix.inputs["A"])
        tree.links.new(brick.outputs["Color"], expose_mix.inputs["B"])
        final_color = expose_mix.outputs["Result"]

    painted = _warm_painterly_pass(tree, c, final_color, loc_x=310, loc_y=-610,
                                   strength=0.12 if is_interior else 0.18, scale=1.35)
    ao_str = 0.36 if is_interior else 0.52
    _apply_ao(tree, bsdf, painted, strength=ao_str, distance=0.16)
    _setup_pbr(tree, bsdf, out, roughness=0.95)
    return mat


# ---------------------------------------------------------------------------
# 2. Interior Wall Planks — Wide vertical boards (90 deg rotated UV)
# ---------------------------------------------------------------------------

def create_stylized_interior_planks(name="M_Building_Interior_Planks",
                                     color=(0.70, 0.58, 0.44, 1.0)):
    """
    Rustic interior wooden boards:
    Wide vertical planks (~38cm wide) running cleanly from floor to ceiling.
    Uses 90-degree rotated UV mapping so rows run vertically.
    Features hand-hewn edge wobble, razor-thin dark seams, per-board stain variation,
    and vertical grain. NO narrow corduroy lines, NO white seams!
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1500)

    tex_node = _load_image_texture(tree, "wood_planks_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 0.45, 1.0), rotation=(0.0, 0.0, 1.5707963))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.35
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.10, scale=1.4)
        _apply_ao(tree, bsdf, painted, strength=0.45, distance=0.15)
        _setup_pbr(tree, bsdf, out, roughness=0.82)
        return mat

    # 1. Rotate UV 90 degrees around Z so Brick columns run VERTICALLY (fallback)
    rot_map = tree.nodes.new("ShaderNodeMapping")
    rot_map.location = (-1300, 100)
    rot_map.inputs["Rotation"].default_value = (0.0, 0.0, 1.5707963)
    tree.links.new(c.outputs["UV"], rot_map.inputs["Vector"])

    # 2. Hand-hewn edge wobble (eliminates ruler-straight lines)
    wobble = tree.nodes.new("ShaderNodeTexNoise")
    wobble.location = (-1100, 100)
    wobble.inputs["Scale"].default_value = 2.5
    wobble.inputs["Detail"].default_value = 2.0
    try:
        wobble.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(rot_map.outputs["Vector"], wobble.inputs["Vector"])

    w_sub = tree.nodes.new("ShaderNodeVectorMath")
    w_sub.location = (-920, 100)
    w_sub.operation = 'SUBTRACT'
    w_sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    tree.links.new(wobble.outputs["Color"], w_sub.inputs[0])

    w_scale = tree.nodes.new("ShaderNodeVectorMath")
    w_scale.location = (-740, 100)
    w_scale.operation = 'SCALE'
    w_scale.inputs["Scale"].default_value = 0.020  # ~2cm organic wobble
    tree.links.new(w_sub.outputs["Vector"], w_scale.inputs[0])

    w_add = tree.nodes.new("ShaderNodeVectorMath")
    w_add.location = (-560, 100)
    w_add.operation = 'ADD'
    tree.links.new(rot_map.outputs["Vector"], w_add.inputs[0])
    tree.links.new(w_scale.outputs["Vector"], w_add.inputs[1])

    # 3. Vertical planks: Brick with large width so boards run full wall height
    brick = tree.nodes.new("ShaderNodeTexBrick")
    brick.location = (-360, 100)
    try:
        brick.offset = 0.0
    except Exception:
        pass
    for k, v in [
        ("Scale", 1.0),
        ("Brick Width", 50.0),
        ("Row Height", 0.38),
        ("Mortar Size", 0.0018),
        ("Mortar Smooth", 0.0012),
        ("Color1", (0.35, 0.35, 0.35, 1.0)),
        ("Color2", (0.75, 0.75, 0.75, 1.0)),
        ("Mortar", (0.02, 0.015, 0.01, 1.0)),
        ("Bias", 0.0),
    ]:
        if k in brick.inputs:
            brick.inputs[k].default_value = v
    tree.links.new(w_add.outputs["Vector"], brick.inputs[0])

    # 4. Per-board wood stain variation
    c_dark  = (color[0] * 0.72, color[1] * 0.64, color[2] * 0.56, 1.0)
    c_base  = (color[0], color[1], color[2], 1.0)
    c_light = (min(1.0, color[0] * 1.36), min(1.0, color[1] * 1.26), min(1.0, color[2] * 1.14), 1.0)

    stain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    stain_ramp.location = (-140, 180)
    stain_ramp.color_ramp.interpolation = 'LINEAR'
    stain_ramp.color_ramp.elements[0].position = 0.0
    stain_ramp.color_ramp.elements[0].color = c_dark
    el_s = stain_ramp.color_ramp.elements.new(0.50)
    el_s.color = c_base
    stain_ramp.color_ramp.elements[1].position = 1.0
    stain_ramp.color_ramp.elements[1].color = c_light
    tree.links.new(brick.outputs["Color"], stain_ramp.inputs["Fac"])

    # 5. Thin dark crevice seam (Fac = 0.0 on board -> A, Fac = 1.0 in seam -> B)
    # A = warm board color, B = deep dark crevice!
    c_seam = (0.04, 0.025, 0.015, 1.0)
    seam_mix = tree.nodes.new("ShaderNodeMix")
    seam_mix.data_type = 'RGBA'
    seam_mix.blend_type = 'MIX'
    seam_mix.location = (100, 100)
    seam_mix.inputs["B"].default_value = c_seam
    tree.links.new(stain_ramp.outputs["Color"], seam_mix.inputs["A"])
    tree.links.new(brick.outputs["Fac"], seam_mix.inputs["Factor"])

    # 6. Vertical wood grain along wall height (X in rotated UV)
    grain_map = tree.nodes.new("ShaderNodeMapping")
    grain_map.location = (-360, -280)
    grain_map.inputs["Scale"].default_value = (0.04, 1.5, 1.0)
    tree.links.new(w_add.outputs["Vector"], grain_map.inputs["Vector"])

    grain_noise = tree.nodes.new("ShaderNodeTexNoise")
    grain_noise.location = (-140, -280)
    grain_noise.inputs["Scale"].default_value = 2.5
    grain_noise.inputs["Detail"].default_value = 2.0
    try:
        grain_noise.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(grain_map.outputs["Vector"], grain_noise.inputs["Vector"])

    grain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    grain_ramp.location = (100, -280)
    grain_ramp.color_ramp.interpolation = 'LINEAR'
    grain_ramp.color_ramp.elements[0].color = (0.86, 0.82, 0.78, 1.0)
    grain_ramp.color_ramp.elements[1].color = (1.10, 1.08, 1.04, 1.0)
    tree.links.new(grain_noise.outputs["Fac"], grain_ramp.inputs["Fac"])

    grain_mix = tree.nodes.new("ShaderNodeMix")
    grain_mix.data_type = 'RGBA'
    grain_mix.blend_type = 'MULTIPLY'
    grain_mix.location = (340, 0)
    grain_mix.inputs["Factor"].default_value = 0.20
    tree.links.new(seam_mix.outputs["Result"], grain_mix.inputs["A"])
    tree.links.new(grain_ramp.outputs["Color"], grain_mix.inputs["B"])

    painted = _warm_painterly_pass(tree, c, grain_mix.outputs["Result"], loc_x=570, loc_y=-250, strength=0.13, scale=1.6)
    _apply_ao(tree, bsdf, painted, strength=0.45, distance=0.15)
    _setup_pbr(tree, bsdf, out, roughness=0.82)
    return mat


# ---------------------------------------------------------------------------
# 3. Timber Frame — Length-aligned wood grain on beams, posts, rafters
# ---------------------------------------------------------------------------

def create_stylized_timber(name="M_Building_Timber", color=(0.30, 0.16, 0.08, 1.0)):
    """
    Handpainted timber frame:
    Uses warped, longitudinally-stretched organic grain (no straight SAW waves).
    Grain flows naturally along horizontal, vertical, and diagonal beams.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1100)

    tex_node = _load_image_texture(tree, "timber_beam_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 0.45, 1.0), rotation=(0.0, 0.0, 0.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.35
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.10, scale=1.35)
        _apply_ao(tree, bsdf, painted, strength=0.52, distance=0.14)
        _setup_pbr(tree, bsdf, out, roughness=0.78)
        return mat

    c_dark  = (color[0] * 0.20, color[1] * 0.14, color[2] * 0.09, 1.0)
    c_mid   = (color[0], color[1], color[2], 1.0)
    c_light = (min(1.0, color[0] * 1.72), min(1.0, color[1] * 1.50), min(1.0, color[2] * 1.30), 1.0)

    grain = _wood_grain_nodes(tree, c, loc_x=-850,
                              scale_u=1.4, scale_v=0.06, warp_amount=0.25,
                              color_dark=c_dark, color_mid=c_mid, color_light=c_light)

    anti = tree.nodes.new("ShaderNodeTexNoise")
    anti.location = (-100, -320)
    anti.inputs["Scale"].default_value = 0.30
    anti.inputs["Detail"].default_value = 2.0
    tree.links.new(c.outputs["UV"], anti.inputs["Vector"])

    anti_mix = tree.nodes.new("ShaderNodeMix")
    anti_mix.data_type = 'RGBA'
    anti_mix.blend_type = 'OVERLAY'
    anti_mix.location = (140, 0)
    anti_mix.inputs["Factor"].default_value = 0.12
    tree.links.new(grain, anti_mix.inputs["A"])
    tree.links.new(anti.outputs["Color"], anti_mix.inputs["B"])

    painted = _warm_painterly_pass(tree, c, anti_mix.outputs["Result"], loc_x=380, loc_y=-260, strength=0.16, scale=1.35)
    _apply_ao(tree, bsdf, painted, strength=0.52, distance=0.14)
    _setup_pbr(tree, bsdf, out, roughness=0.78)
    return mat


# ---------------------------------------------------------------------------
# 4. Floorboards — Staggered wide planks with thin dark seams
# ---------------------------------------------------------------------------

def create_stylized_floorboards(name="M_Building_Floorboards",
                                 color=(0.48, 0.32, 0.18, 1.0)):
    """
    Authentic stylized tavern floorboards matching reference image:
    - Wide boards (~38cm wide x ~2.2m long) in running bond along X.
    - Hand-carved organic edge wobble (NO ruler-straight lines!).
    - Razor-thin dark crevices between planks (~1.5mm), NEVER wide beige borders!
    - Subtle warm bevel catchlight on plank edges.
    - Beautiful per-plank warm wood stain variation.
    - Longitudinal grain flowing ALONG the length of the planks (X axis).
    - Contact AO in room corners.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1600)
    c = _coord(tree, loc_x=-1500)

    # 1. Use packaged handpainted wood planks texture if present
    tex_node = _load_image_texture(tree, "wood_planks_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(0.70, 0.70, 1.0), rotation=(0.0, 0.0, 1.5707963))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.10
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.10, scale=1.4)
        _apply_ao(tree, bsdf, painted, strength=0.52, distance=0.18)
        _setup_pbr(tree, bsdf, out, roughness=0.74)
        return mat


def create_stylized_facade_planks(name="M_Building_Wood", color=(0.86, 0.74, 0.58, 1.0)):
    """
    Stylized lighter wood planks for exterior facade weatherboards and dormer walls.
    Distinguishes facade planks clearly from darker timber frame beams and posts.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1100)

    tex_node = _load_image_texture(tree, "facade_wood_planks_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.10, 1.10, 1.0), rotation=(0.0, 0.0, 1.5707963))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.15
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.08, scale=1.35)
        _apply_ao(tree, bsdf, painted, strength=0.48, distance=0.14)
        _setup_pbr(tree, bsdf, out, roughness=0.76)
        return mat

    return create_stylized_timber(name, color=color)

    # 2. Hand-carved organic edge wobble (procedural fallback)
    wobble = tree.nodes.new("ShaderNodeTexNoise")
    wobble.location = (-1300, 120)
    wobble.inputs["Scale"].default_value = 2.5
    wobble.inputs["Detail"].default_value = 2.0
    try:
        wobble.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(c.outputs["UV"], wobble.inputs["Vector"])

    # Center noise: (Color - 0.5) * 0.022 added to UV
    w_sub = tree.nodes.new("ShaderNodeVectorMath")
    w_sub.location = (-1100, 120)
    w_sub.operation = 'SUBTRACT'
    w_sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    tree.links.new(wobble.outputs["Color"], w_sub.inputs[0])

    w_scale = tree.nodes.new("ShaderNodeVectorMath")
    w_scale.location = (-920, 120)
    w_scale.operation = 'SCALE'
    w_scale.inputs["Scale"].default_value = 0.022  # ~2.2cm organic wobble
    tree.links.new(w_sub.outputs["Vector"], w_scale.inputs[0])

    w_add = tree.nodes.new("ShaderNodeVectorMath")
    w_add.location = (-740, 120)
    w_add.operation = 'ADD'
    tree.links.new(c.outputs["UV"], w_add.inputs[0])
    tree.links.new(w_scale.outputs["Vector"], w_add.inputs[1])

    # 2. Staggered running-bond planks along X
    brick = tree.nodes.new("ShaderNodeTexBrick")
    brick.location = (-540, 120)
    try:
        brick.offset = 0.50
    except Exception:
        pass
    for k, v in [
        ("Scale", 1.0),
        ("Brick Width", 2.2),
        ("Row Height", 0.36),
        ("Mortar Size", 0.0016),
        ("Mortar Smooth", 0.0012),
        ("Color1", (0.35, 0.35, 0.35, 1.0)),
        ("Color2", (0.75, 0.75, 0.75, 1.0)),
        ("Mortar", (0.02, 0.015, 0.01, 1.0)),
        ("Bias", 0.0),
    ]:
        if k in brick.inputs:
            brick.inputs[k].default_value = v
    tree.links.new(w_add.outputs["Vector"], brick.inputs[0])

    # 3. Per-plank wood stain variation using Brick Color
    c_dark_stain  = (color[0] * 0.80, color[1] * 0.75, color[2] * 0.70, 1.0)
    c_base_stain  = (color[0], color[1], color[2], 1.0)
    c_light_stain = (min(1.0, color[0] * 1.25), min(1.0, color[1] * 1.20), min(1.0, color[2] * 1.12), 1.0)

    stain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    stain_ramp.location = (-280, 220)
    stain_ramp.color_ramp.interpolation = 'LINEAR'
    stain_ramp.color_ramp.elements[0].position = 0.0
    stain_ramp.color_ramp.elements[0].color = c_dark_stain
    el_st = stain_ramp.color_ramp.elements.new(0.50)
    el_st.color = c_base_stain
    stain_ramp.color_ramp.elements[1].position = 1.0
    stain_ramp.color_ramp.elements[1].color = c_light_stain
    tree.links.new(brick.outputs["Color"], stain_ramp.inputs["Fac"])

    # 4. Pure dark crevice seam (Fac = 0.0 on plank -> A, Fac = 1.0 in seam -> B)
    # A = warm plank color, B = deep dark crevice!
    c_crevice = (0.04, 0.025, 0.015, 1.0)
    seam_mix = tree.nodes.new("ShaderNodeMix")
    seam_mix.data_type = 'RGBA'
    seam_mix.blend_type = 'MIX'
    seam_mix.location = (-20, 120)
    seam_mix.inputs["B"].default_value = c_crevice
    tree.links.new(stain_ramp.outputs["Color"], seam_mix.inputs["A"])
    tree.links.new(brick.outputs["Fac"], seam_mix.inputs["Factor"])

    # 5. Longitudinal wood grain flowing ALONG the planks (X direction!)
    # Scale X is small (0.04) so fibers stretch along plank length!
    grain_map = tree.nodes.new("ShaderNodeMapping")
    grain_map.location = (-540, -320)
    grain_map.inputs["Scale"].default_value = (0.04, 1.6, 1.0)
    tree.links.new(w_add.outputs["Vector"], grain_map.inputs["Vector"])

    grain_noise = tree.nodes.new("ShaderNodeTexNoise")
    grain_noise.location = (-300, -320)
    grain_noise.inputs["Scale"].default_value = 2.5
    grain_noise.inputs["Detail"].default_value = 2.0
    try:
        grain_noise.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(grain_map.outputs["Vector"], grain_noise.inputs["Vector"])

    grain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    grain_ramp.location = (-60, -320)
    grain_ramp.color_ramp.interpolation = 'LINEAR'
    grain_ramp.color_ramp.elements[0].color = (0.86, 0.82, 0.78, 1.0)
    grain_ramp.color_ramp.elements[1].color = (1.10, 1.06, 1.02, 1.0)
    tree.links.new(grain_noise.outputs["Fac"], grain_ramp.inputs["Fac"])

    grain_mix = tree.nodes.new("ShaderNodeMix")
    grain_mix.data_type = 'RGBA'
    grain_mix.blend_type = 'MULTIPLY'
    grain_mix.location = (240, 0)
    grain_mix.inputs["Factor"].default_value = 0.22
    tree.links.new(seam_mix.outputs["Result"], grain_mix.inputs["A"])
    tree.links.new(grain_ramp.outputs["Color"], grain_mix.inputs["B"])

    _apply_ao(tree, bsdf, grain_mix.outputs["Result"], strength=0.48, distance=0.15)
    _setup_pbr(tree, bsdf, out, roughness=0.76)
    return mat


# ---------------------------------------------------------------------------
# 5. Shingles — Matte clay roof tiles with contact occlusion
# ---------------------------------------------------------------------------

def create_stylized_shingles(name="M_Building_Shingles",
                              color=(0.22, 0.30, 0.48, 1.0)):
    """
    Clay roof shingles: Matte clay material without artificial texture seams.
    Overlapping physical tile geometry combined with strong contact AO produces
    deep, natural, bakeable shadows under each tile lip.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1200)
    c = _coord(tree, loc_x=-900)

    tex_node = _load_image_texture(tree, "roof_tiles_diffuse.jpg", c, loc_x=-660, loc_y=80, scale=(1.0, 1.0, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-200, 80)
        tint.inputs["Factor"].default_value = 0.35
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=60, loc_y=-280, strength=0.10, scale=1.5)
        _apply_ao(tree, bsdf, painted, strength=0.65, distance=0.18)
        _setup_pbr(tree, bsdf, out, roughness=0.85)
        return mat

    weather = tree.nodes.new("ShaderNodeTexNoise")
    weather.location = (-660, 80)
    weather.inputs["Scale"].default_value = 1.0
    weather.inputs["Detail"].default_value = 2.0
    tree.links.new(c.outputs["UV"], weather.inputs["Vector"])

    c_damp  = (color[0] * 0.62, color[1] * 0.66, color[2] * 0.74, 1.0)
    c_mid   = (color[0], color[1], color[2], 1.0)
    c_faded = (min(1.0, color[0] * 1.52), min(1.0, color[1] * 1.40), min(1.0, color[2] * 1.28), 1.0)

    w_ramp = tree.nodes.new("ShaderNodeValToRGB")
    w_ramp.location = (-420, 80)
    w_ramp.color_ramp.interpolation = 'LINEAR'
    w_ramp.color_ramp.elements[0].position = 0.0
    w_ramp.color_ramp.elements[0].color = c_damp
    el_w = w_ramp.color_ramp.elements.new(0.50)
    el_w.color = c_mid
    w_ramp.color_ramp.elements[1].position = 1.0
    w_ramp.color_ramp.elements[1].color = c_faded
    tree.links.new(weather.outputs["Fac"], w_ramp.inputs["Fac"])

    micro = tree.nodes.new("ShaderNodeTexNoise")
    micro.location = (-420, -160)
    micro.inputs["Scale"].default_value = 16.0
    micro.inputs["Detail"].default_value = 2.0
    tree.links.new(c.outputs["UV"], micro.inputs["Vector"])

    micro_mix = tree.nodes.new("ShaderNodeMix")
    micro_mix.data_type = 'RGBA'
    micro_mix.blend_type = 'OVERLAY'
    micro_mix.location = (-180, 0)
    micro_mix.inputs["Factor"].default_value = 0.10
    tree.links.new(w_ramp.outputs["Color"], micro_mix.inputs["A"])
    tree.links.new(micro.outputs["Color"], micro_mix.inputs["B"])

    painted = _warm_painterly_pass(tree, c, micro_mix.outputs["Result"], loc_x=80, loc_y=-280, strength=0.12, scale=1.5)
    _apply_ao(tree, bsdf, painted, strength=0.65, distance=0.18)
    _setup_pbr(tree, bsdf, out, roughness=0.88)
    return mat


# ---------------------------------------------------------------------------
# 6. Glass — Warm emissive interior glow
# ---------------------------------------------------------------------------

def create_stylized_glass(name="M_Building_Glass", glow_strength=0.0,
                          emissive_glow=(1.0, 0.85, 0.50, 1.0)):
    """Stylized frosted leaded window glass with optional cozy interior candle glow."""
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=800)

    _set_bsdf_input(bsdf, "Base Color", (0.18, 0.28, 0.38, 1.0))
    _set_bsdf_input(bsdf, "Roughness", 0.18)
    _set_bsdf_input(bsdf, "Metallic", 0.05)
    for n in ("Specular IOR Level", "Specular"):
        _set_bsdf_input(bsdf, n, 0.50)

    if glow_strength > 0.01:
        glow_col = (emissive_glow[0], emissive_glow[1], emissive_glow[2], 1.0)
        _set_bsdf_input(bsdf, "Emission Color", glow_col)
        _set_bsdf_input(bsdf, "Emission Strength", glow_strength * 2.5)

    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# 7. Door — 3 wide vertical planks with thin dark seams
# ---------------------------------------------------------------------------

def create_stylized_door(name="M_Building_Door", color=(0.28, 0.14, 0.07, 1.0)):
    """
    3 wide vertical wooden planks with hand-carved wobble, thin dark seams,
    and flowing vertical wood grain.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1400)

    tex_node = _load_image_texture(tree, "timber_beam_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 0.45, 1.0), rotation=(0.0, 0.0, 0.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.18
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.08, scale=1.35)
        _apply_ao(tree, bsdf, painted, strength=0.52, distance=0.14)
        _setup_pbr(tree, bsdf, out, roughness=0.76)
        return mat

    # 1. Rotate UV 90 degrees around Z so Brick columns run VERTICALLY on the door
    rot_map = tree.nodes.new("ShaderNodeMapping")
    rot_map.location = (-1180, 100)
    rot_map.inputs["Rotation"].default_value = (0.0, 0.0, 1.5707963)
    tree.links.new(c.outputs["UV"], rot_map.inputs["Vector"])

    wobble = tree.nodes.new("ShaderNodeTexNoise")
    wobble.location = (-980, 100)
    wobble.inputs["Scale"].default_value = 2.0
    wobble.inputs["Detail"].default_value = 1.0
    tree.links.new(rot_map.outputs["Vector"], wobble.inputs["Vector"])

    wobble_mix = tree.nodes.new("ShaderNodeMix")
    wobble_mix.data_type = 'VECTOR'
    wobble_mix.location = (-760, 100)
    wobble_mix.inputs["Factor"].default_value = 0.02
    tree.links.new(rot_map.outputs["Vector"], wobble_mix.inputs["A"])
    tree.links.new(wobble.outputs["Color"], wobble_mix.inputs["B"])

    brick = tree.nodes.new("ShaderNodeTexBrick")
    brick.location = (-540, 100)
    try:
        brick.offset = 0.0
    except Exception:
        pass
    for k, v in [
        ("Scale", 1.0),
        ("Brick Width", 50.0),
        ("Row Height", 0.33),
        ("Mortar Size", 0.0025),
        ("Mortar Smooth", 0.0015),
        ("Color1", (0.45, 0.45, 0.45, 1.0)),
        ("Color2", (0.75, 0.75, 0.75, 1.0)),
        ("Mortar", (0.02, 0.015, 0.01, 1.0)),
        ("Bias", 0.0),
    ]:
        if k in brick.inputs:
            brick.inputs[k].default_value = v
    tree.links.new(wobble_mix.outputs["Result"], brick.inputs[0])

    # Per-plank wood tone
    c_dark  = (color[0] * 0.85, color[1] * 0.82, color[2] * 0.78, 1.0)
    c_base  = (color[0], color[1], color[2], 1.0)
    c_light = (min(1.0, color[0] * 1.18), min(1.0, color[1] * 1.14), min(1.0, color[2] * 1.08), 1.0)

    stain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    stain_ramp.location = (-300, 180)
    stain_ramp.color_ramp.interpolation = 'LINEAR'
    stain_ramp.color_ramp.elements[0].position = 0.0
    stain_ramp.color_ramp.elements[0].color = c_dark
    el_s = stain_ramp.color_ramp.elements.new(0.50)
    el_s.color = c_base
    stain_ramp.color_ramp.elements[1].position = 1.0
    stain_ramp.color_ramp.elements[1].color = c_light
    tree.links.new(brick.outputs["Color"], stain_ramp.inputs["Fac"])

    # Dark crevice seam (Fac = 0.0 on board -> A, Fac = 1.0 in seam -> B)
    c_seam = (0.04, 0.025, 0.015, 1.0)
    seam_mix = tree.nodes.new("ShaderNodeMix")
    seam_mix.data_type = 'RGBA'
    seam_mix.blend_type = 'MIX'
    seam_mix.location = (-60, 100)
    seam_mix.inputs["B"].default_value = c_seam
    tree.links.new(stain_ramp.outputs["Color"], seam_mix.inputs["A"])
    tree.links.new(brick.outputs["Fac"], seam_mix.inputs["Factor"])

    # Flowing vertical wood grain along door height (X in rotated UV)
    grain_map = tree.nodes.new("ShaderNodeMapping")
    grain_map.location = (-540, -280)
    grain_map.inputs["Scale"].default_value = (0.04, 1.6, 1.0)
    tree.links.new(wobble_mix.outputs["Result"], grain_map.inputs["Vector"])

    grain_noise = tree.nodes.new("ShaderNodeTexNoise")
    grain_noise.location = (-300, -280)
    grain_noise.inputs["Scale"].default_value = 2.5
    grain_noise.inputs["Detail"].default_value = 2.0
    try:
        grain_noise.inputs["Roughness"].default_value = 0.50
    except Exception:
        pass
    tree.links.new(grain_map.outputs["Vector"], grain_noise.inputs["Vector"])

    grain_ramp = tree.nodes.new("ShaderNodeValToRGB")
    grain_ramp.location = (-60, -280)
    grain_ramp.color_ramp.interpolation = 'LINEAR'
    grain_ramp.color_ramp.elements[0].color = (0.82, 0.78, 0.74, 1.0)
    grain_ramp.color_ramp.elements[1].color = (1.12, 1.08, 1.04, 1.0)
    tree.links.new(grain_noise.outputs["Fac"], grain_ramp.inputs["Fac"])

    grain_ovl = tree.nodes.new("ShaderNodeMix")
    grain_ovl.data_type = 'RGBA'
    grain_ovl.blend_type = 'MULTIPLY'
    grain_ovl.location = (180, 0)
    grain_ovl.inputs["Factor"].default_value = 0.25
    tree.links.new(seam_mix.outputs["Result"], grain_ovl.inputs["A"])
    tree.links.new(grain_ramp.outputs["Color"], grain_ovl.inputs["B"])

    _apply_ao(tree, bsdf, grain_ovl.outputs["Result"], strength=0.52, distance=0.12)
    _setup_pbr(tree, bsdf, out, roughness=0.80)
    return mat


# ---------------------------------------------------------------------------
# 8. Iron — Forged stylized wrought iron
# ---------------------------------------------------------------------------

def create_stylized_iron(name="M_Building_Iron"):
    """Hand-forged dark iron with bevel edge specular highlight and subtle hammer marks."""
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1000)
    c = _coord(tree, loc_x=-800)

    tex_node = _load_image_texture(tree, "iron_metal_diffuse.jpg", c, loc_x=-560, loc_y=60, scale=(2.2, 2.2, 2.2))
    if tex_node is not None:
        _apply_ao(tree, bsdf, tex_node.outputs["Color"], strength=0.45, distance=0.10)
        _setup_pbr(tree, bsdf, out, roughness=0.48, metallic=0.88)
        return mat

    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-560, 60)
    noise.inputs["Scale"].default_value = 16.0
    noise.inputs["Detail"].default_value = 3.0
    tree.links.new(c.outputs["UV"], noise.inputs["Vector"])

    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-320, 60)
    ramp.color_ramp.interpolation = 'LINEAR'
    ramp.color_ramp.elements[0].color = (0.08, 0.08, 0.09, 1.0)
    ramp.color_ramp.elements[1].color = (0.24, 0.24, 0.26, 1.0)
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    _apply_ao(tree, bsdf, ramp.outputs["Color"], strength=0.45, distance=0.10)
    _setup_pbr(tree, bsdf, out, roughness=0.65, metallic=0.75)
    return mat


# ---------------------------------------------------------------------------
# 10. Log Ends — Concentric tree rings with warm core & swirl
# ---------------------------------------------------------------------------

def create_stylized_log_ends(name="M_Building_Log_End", color=(0.50, 0.34, 0.18, 1.0)):
    """
    Authentic stylized log cross-section:
    Uses radial UV coordinates centered at (0.5, 0.5).
    Concentric spherical ring waves with organic swirl distortion,
    dark amber pith core, rich heartwood, and golden sapwood rim.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1200)

    tex_node = _load_image_texture(tree, "log_end_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 1.0, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.20
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.08, scale=1.4)
        _apply_ao(tree, bsdf, painted, strength=0.48, distance=0.12)
        _setup_pbr(tree, bsdf, out, roughness=0.80)
        return mat

    center_sub = tree.nodes.new("ShaderNodeVectorMath")
    center_sub.location = (-980, 80)
    center_sub.operation = 'SUBTRACT'
    center_sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    tree.links.new(c.outputs["UV"], center_sub.inputs[0])

    swirl_noise = tree.nodes.new("ShaderNodeTexNoise")
    swirl_noise.location = (-980, -180)
    swirl_noise.inputs["Scale"].default_value = 2.2
    swirl_noise.inputs["Detail"].default_value = 2.0
    tree.links.new(center_sub.outputs["Vector"], swirl_noise.inputs["Vector"])

    swirl_mix = tree.nodes.new("ShaderNodeMix")
    swirl_mix.data_type = 'VECTOR'
    swirl_mix.location = (-740, 0)
    swirl_mix.inputs["Factor"].default_value = 0.12
    tree.links.new(center_sub.outputs["Vector"], swirl_mix.inputs["A"])
    tree.links.new(swirl_noise.outputs["Color"], swirl_mix.inputs["B"])

    rings = tree.nodes.new("ShaderNodeTexWave")
    rings.location = (-500, 100)
    rings.wave_type = 'RINGS'
    rings.rings_direction = 'SPHERICAL'
    rings.wave_profile = 'SIN'
    rings.inputs["Scale"].default_value = 4.8
    rings.inputs["Distortion"].default_value = 4.0
    rings.inputs["Detail"].default_value = 3.0
    tree.links.new(swirl_mix.outputs["Result"], rings.inputs["Vector"])

    rad_dist = tree.nodes.new("ShaderNodeVectorMath")
    rad_dist.location = (-500, -140)
    rad_dist.operation = 'LENGTH'
    tree.links.new(center_sub.outputs["Vector"], rad_dist.inputs[0])

    c_pith    = (color[0] * 0.22, color[1] * 0.14, color[2] * 0.08, 1.0)
    c_heart   = (color[0], color[1], color[2], 1.0)
    c_sapwood = (min(1.0, color[0] * 1.45), min(1.0, color[1] * 1.34), min(1.0, color[2] * 1.18), 1.0)
    c_bark    = (color[0] * 0.18, color[1] * 0.11, color[2] * 0.06, 1.0)

    rad_ramp = tree.nodes.new("ShaderNodeValToRGB")
    rad_ramp.location = (-260, -140)
    rad_ramp.color_ramp.interpolation = 'LINEAR'
    rad_ramp.color_ramp.elements[0].position = 0.0
    rad_ramp.color_ramp.elements[0].color = c_pith
    el1 = rad_ramp.color_ramp.elements.new(0.20)
    el1.color = c_heart
    el2 = rad_ramp.color_ramp.elements.new(0.40)
    el2.color = c_sapwood
    rad_ramp.color_ramp.elements[1].position = 0.48
    rad_ramp.color_ramp.elements[1].color = c_bark
    tree.links.new(rad_dist.outputs["Value"], rad_ramp.inputs["Fac"])

    ring_ramp = tree.nodes.new("ShaderNodeValToRGB")
    ring_ramp.location = (-260, 100)
    ring_ramp.color_ramp.interpolation = 'LINEAR'
    ring_ramp.color_ramp.elements[0].color = (0.35, 0.35, 0.35, 1.0)
    ring_ramp.color_ramp.elements[1].color = (1.00, 1.00, 1.00, 1.0)
    tree.links.new(rings.outputs["Fac"], ring_ramp.inputs["Fac"])

    combine = tree.nodes.new("ShaderNodeMix")
    combine.data_type = 'RGBA'
    combine.blend_type = 'OVERLAY'
    combine.location = (0, 0)
    combine.inputs["Factor"].default_value = 0.60
    tree.links.new(rad_ramp.outputs["Color"], combine.inputs["A"])
    tree.links.new(ring_ramp.outputs["Color"], combine.inputs["B"])

    _apply_ao(tree, bsdf, combine.outputs["Result"], strength=0.50, distance=0.12)
    _setup_pbr(tree, bsdf, out, roughness=0.86)
    return mat


# ---------------------------------------------------------------------------
# 11. Log Walls — Cylindrical lengthwise grain on horizontal logs
# ---------------------------------------------------------------------------

def create_stylized_log(name="M_Building_Log", color=(0.34, 0.22, 0.12, 1.0)):
    """
    Horizontal log material:
    Physical 3D rounded cylinders need natural organic bark/wood flow,
    NOT straight repeating sawteeth lines drawn across them!
    Uses handpainted rustic log bark texture with longitudinal grain.
    """
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1100)

    tex_node = _load_image_texture(tree, "log_bark_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 0.40, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.12
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.06, scale=1.4)
        _apply_ao(tree, bsdf, painted, strength=0.45, distance=0.12)
        _setup_pbr(tree, bsdf, out, roughness=0.76)
        return mat

    c_dark  = (color[0] * 0.25, color[1] * 0.18, color[2] * 0.12, 1.0)
    c_mid   = (color[0], color[1], color[2], 1.0)
    c_light = (min(1.0, color[0] * 1.45), min(1.0, color[1] * 1.34), min(1.0, color[2] * 1.20), 1.0)

    grain = _wood_grain_nodes(tree, c, loc_x=-850,
                              scale_u=0.35, scale_v=0.04, warp_amount=0.35,
                              color_dark=c_dark, color_mid=c_mid, color_light=c_light)

    anti = tree.nodes.new("ShaderNodeTexNoise")
    anti.location = (-100, -320)
    anti.inputs["Scale"].default_value = 0.30
    anti.inputs["Detail"].default_value = 2.0
    tree.links.new(c.outputs["UV"], anti.inputs["Vector"])

    anti_mix = tree.nodes.new("ShaderNodeMix")
    anti_mix.data_type = 'RGBA'
    anti_mix.blend_type = 'OVERLAY'
    anti_mix.location = (140, 0)
    anti_mix.inputs["Factor"].default_value = 0.12
    tree.links.new(grain, anti_mix.inputs["A"])
    tree.links.new(anti.outputs["Color"], anti_mix.inputs["B"])

    _apply_ao(tree, bsdf, anti_mix.outputs["Result"], strength=0.55, distance=0.15)
    _setup_pbr(tree, bsdf, out, roughness=0.82)
    return mat


# ---------------------------------------------------------------------------
# 12. Stairs — Clean wood for stair treads & stringers
# ---------------------------------------------------------------------------

def create_stylized_stairs(name="M_Building_Stairs", color=(0.32, 0.20, 0.11, 1.0)):
    """Clean stylized timber for staircase treads, stringers and risers."""
    mat, tree = _new_mat(name)
    out, bsdf = _out_bsdf(tree, loc_x=1400)
    c = _coord(tree, loc_x=-1100)

    tex_node = _load_image_texture(tree, "timber_beam_diffuse.jpg", c, loc_x=-800, loc_y=120, scale=(1.0, 1.0, 1.0))
    if tex_node is not None:
        tint = tree.nodes.new("ShaderNodeMix")
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.location = (-250, 120)
        tint.inputs["Factor"].default_value = 0.35
        tree.links.new(tex_node.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = color
        painted = _warm_painterly_pass(tree, c, tint.outputs["Result"], loc_x=20, loc_y=-260, strength=0.08, scale=1.2)
        _apply_ao(tree, bsdf, painted, strength=0.45, distance=0.12)
        _setup_pbr(tree, bsdf, out, roughness=0.76)
        return mat

    return create_stylized_timber(name, color=color)


# Backward compatibility aliases
create_stylized_log_walls = create_stylized_log
create_stylized_plank_siding = create_stylized_interior_planks


# ---------------------------------------------------------------------------
# Material slot setup
# ---------------------------------------------------------------------------

def setup_building_material_slots(obj, props):
    """
    Populates all 16 canonical material slots on obj.
    Slot indices match MAT_INDEX_* constants.
    Custom material overrides on props take priority.
    """
    tier       = getattr(props, "material_tier", "TIER_3")
    is_palette = getattr(props, "color_palette", "CUSTOM") != "CUSTOM"

    # 0. Stone
    if props.custom_stone:
        mat_stone = props.custom_stone
    elif is_palette:
        mat_stone = create_stylized_stone(f"M_Building_Stone_{tier}", color=props.color_stone)
    elif tier == 'TIER_1':
        mat_stone = create_stylized_stone("M_Building_Stone_T1", color=(0.38, 0.34, 0.30, 1.0))
    elif tier == 'TIER_2':
        mat_stone = create_stylized_stone("M_Building_Stone_T2", color=(0.52, 0.48, 0.42, 1.0))
    else:
        mat_stone = create_stylized_stone("M_Building_Stone_T3", color=props.color_stone)

    # 1. Plaster Ext
    if props.custom_wall_ext:
        mat_plaster_ext = props.custom_wall_ext
    elif is_palette:
        mat_plaster_ext = create_stylized_plaster(
            "M_Building_Plaster_Ext", color=props.color_wall_ext, is_interior=False)
    elif tier == 'TIER_1':
        mat_plaster_ext = create_stylized_log("M_Building_Log_Ext", color=(0.34, 0.22, 0.12, 1.0))
    elif tier == 'TIER_2':
        mat_plaster_ext = create_stylized_interior_planks("M_Building_Plank_Ext", color=(0.68, 0.58, 0.44, 1.0))
    else:
        mat_plaster_ext = create_stylized_plaster(
            "M_Building_Plaster_Ext", color=props.color_wall_ext, is_interior=False)

    # 2. Plaster Int
    # If the user or preset set a light plaster color (like default (0.90, 0.86, 0.80)),
    # use clean cozy plaster for plaster interior, OR wide rustic boards if wooden!
    clr_int = getattr(props, 'color_wall_int', (0.90, 0.86, 0.80, 1.0))
    brightness = (clr_int[0] + clr_int[1] + clr_int[2]) / 3.0
    is_plaster_like = brightness > 0.65 and tier == 'TIER_3'

    if props.custom_wall_int:
        mat_plaster_int = props.custom_wall_int
    elif is_plaster_like:
        mat_plaster_int = create_stylized_plaster(
            "M_Building_Plaster_Int", color=clr_int, is_interior=True)
    elif is_palette:
        mat_plaster_int = create_stylized_interior_planks(
            "M_Building_Interior_Planks",
            color=(min(1.0, clr_int[0] * 0.95), min(1.0, clr_int[1] * 0.88), min(1.0, clr_int[2] * 0.72), 1.0))
    elif tier == 'TIER_1':
        mat_plaster_int = create_stylized_interior_planks(
            "M_Building_Interior_Planks_T1", color=(0.60, 0.48, 0.33, 1.0))
    elif tier == 'TIER_2':
        mat_plaster_int = create_stylized_interior_planks(
            "M_Building_Interior_Planks_T2", color=(0.70, 0.60, 0.46, 1.0))
    else:
        mat_plaster_int = create_stylized_plaster(
            "M_Building_Plaster_Int", color=clr_int, is_interior=True)

    # 3. Timber Frame
    clr_tf    = getattr(props, 'color_timber_frame', (0.24, 0.14, 0.08, 1.0))
    custom_tf = getattr(props, 'custom_timber_frame', None)
    if custom_tf:
        mat_timber_frame = custom_tf
    else:
        sfx = tier if not is_palette else "Palette"
        mat_timber_frame = create_stylized_timber(f"M_Building_Timber_Frame_{sfx}", color=clr_tf)

    # 4. Floor
    if props.custom_floor:
        mat_floor = props.custom_floor
    else:
        mat_floor = create_stylized_floorboards("M_Building_Floorboards", color=props.color_floor)

    # 5. Shingles
    if props.custom_shingles:
        mat_shingles = props.custom_shingles
    elif is_palette:
        mat_shingles = create_stylized_shingles(f"M_Building_Shingles_{tier}", color=props.color_shingles)
    elif tier == 'TIER_1':
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T1", color=(0.45, 0.28, 0.16, 1.0))
    elif tier == 'TIER_2':
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T2", color=(0.22, 0.32, 0.48, 1.0))
    else:
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T3", color=props.color_shingles)

    # 6. Glass
    mat_glass = props.custom_glass if props.custom_glass else create_stylized_glass(
        glow_strength=props.window_glow_strength, emissive_glow=props.color_window_glow)

    # 7. Door
    mat_door = props.custom_door if props.custom_door else create_stylized_door(
        "M_Building_Door", color=props.color_door)

    # 8. Iron
    mat_iron = props.custom_iron if props.custom_iron else create_stylized_iron()

    # 9. Wood (general / facade planks / dormer walls / weatherboard)
    clr_wood    = getattr(props, 'color_timber', (0.86, 0.74, 0.58, 1.0))
    custom_wood = getattr(props, 'custom_timber', None)
    mat_wood = custom_wood if custom_wood else create_stylized_facade_planks("M_Building_Wood", color=clr_wood)

    # 10. Log End
    clr_le    = getattr(props, 'color_log_end', (0.50, 0.34, 0.18, 1.0))
    custom_le = getattr(props, 'custom_log_end', None)
    mat_log_end = custom_le if custom_le else create_stylized_log_ends("M_Building_Log_End", color=clr_le)

    # 11. Log
    clr_log = (clr_tf[0] * 0.92, clr_tf[1] * 0.88, clr_tf[2] * 0.82, 1.0)
    mat_log = getattr(props, 'custom_log', None) or create_stylized_log(
        "M_Building_Log", color=clr_log)

    # 12. Stairs
    clr_st = (clr_wood[0] * 1.02, clr_wood[1] * 1.01, clr_wood[2] * 0.98, 1.0)
    mat_stairs = getattr(props, 'custom_stairs', None) or create_stylized_stairs(
        "M_Building_Stairs", color=clr_st)

    # 13. Railing
    clr_rl = (min(1.0, clr_wood[0] * 1.08), min(1.0, clr_wood[1] * 1.06), min(1.0, clr_wood[2] * 1.02), 1.0)
    mat_railing = getattr(props, 'custom_railing', None) or create_stylized_timber(
        "M_Building_Railing", color=clr_rl)

    # 14. Window Frame
    clr_wf = (min(1.0, clr_wood[0] * 1.05), min(1.0, clr_wood[1] * 1.02), clr_wood[2], 1.0)
    mat_window = getattr(props, 'custom_window_frame', None) or create_stylized_timber(
        "M_Building_Window_Frame", color=clr_wf)

    # 15. Shutter
    clr_sh = (clr_wf[0] * 0.92, clr_wf[1] * 0.90, clr_wf[2] * 0.88, 1.0)
    mat_shutter = getattr(props, 'custom_shutter', None) or create_stylized_timber(
        "M_Building_Shutter", color=clr_sh)

    # 16. Cut Stone (steps, sills, door arches, thresholds)
    clr_cs = (0.78, 0.74, 0.68, 1.0)
    mat_cut_stone = getattr(props, 'custom_cut_stone', None) or create_stylized_cut_stone(
        "M_Building_Cut_Stone", color=clr_cs)

    # Assemble all 17 slots in strict order
    required_mats = [
        mat_stone,          # 0  MAT_INDEX_STONE
        mat_plaster_ext,    # 1  MAT_INDEX_PLASTER_EXT
        mat_plaster_int,    # 2  MAT_INDEX_PLASTER_INT
        mat_timber_frame,   # 3  MAT_INDEX_TIMBER_FRAME
        mat_floor,          # 4  MAT_INDEX_FLOOR
        mat_shingles,       # 5  MAT_INDEX_SHINGLES
        mat_glass,          # 6  MAT_INDEX_GLASS
        mat_door,           # 7  MAT_INDEX_DOOR
        mat_iron,           # 8  MAT_INDEX_IRON
        mat_wood,           # 9  MAT_INDEX_WOOD
        mat_log_end,        # 10 MAT_INDEX_LOG_END
        mat_log,            # 11 MAT_INDEX_LOG
        mat_stairs,         # 12 MAT_INDEX_STAIRS
        mat_railing,        # 13 MAT_INDEX_RAILING
        mat_window,         # 14 MAT_INDEX_WINDOW_FRAME
        mat_shutter,        # 15 MAT_INDEX_SHUTTER
        mat_cut_stone,      # 16 MAT_INDEX_CUT_STONE
    ]
    obj.data.materials.clear()
    for m in required_mats:
        obj.data.materials.append(m)

