"""
Stylized Procedural Shader Generator and Material Slot Manager for Blender 5.2.
Creates warm, hand-crafted stylized materials with soft noise, ambient occlusions,
edge highlights, and rich fantasy palettes. MAXIMUM STYLIZED handpainted feel: knots, swirl rings, imperfections.
"""

import bpy

# Material slot index constants (16 canonical slots — fully split + shutter)
MAT_INDEX_STONE = 0
MAT_INDEX_PLASTER_EXT = 1
MAT_INDEX_PLASTER_INT = 2
MAT_INDEX_TIMBER_FRAME = 3
MAT_INDEX_FLOOR = 4
MAT_INDEX_SHINGLES = 5
MAT_INDEX_GLASS = 6
MAT_INDEX_DOOR = 7
MAT_INDEX_IRON = 8
MAT_INDEX_WOOD = 9
MAT_INDEX_LOG_END = 10
MAT_INDEX_LOG = 11
MAT_INDEX_STAIRS = 12
MAT_INDEX_RAILING = 13
MAT_INDEX_WINDOW_FRAME = 14
MAT_INDEX_SHUTTER = 15
MAT_INDEX_SHUTTER = 15

# Alias for backwards compatibility
MAT_INDEX_TIMBER = MAT_INDEX_TIMBER_FRAME

def _set_bsdf_input(bsdf, input_name, value):
    sock = bsdf.inputs.get(input_name)
    if sock is not None:
        sock.default_value = value

def _apply_crevice_ao(tree, bsdf, color_socket, strength=0.45, distance=0.15):
    ao = tree.nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (color_socket.node.location.x + 40, color_socket.node.location.y - 260)
    ao.inputs["Distance"].default_value = distance
    ramp_ao = tree.nodes.new("ShaderNodeValToRGB")
    ramp_ao.location = (ao.location.x + 180, ao.location.y)
    ramp_ao.color_ramp.elements[0].position = 0.0
    ramp_ao.color_ramp.elements[0].color = (1.0 - strength, 1.0 - strength, 1.0 - strength, 1.0)
    ramp_ao.color_ramp.elements[1].position = 1.0
    ramp_ao.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    tree.links.new(ao.outputs["AO"], ramp_ao.inputs["Fac"])
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (ramp_ao.location.x + 180, ramp_ao.location.y)
    mix.inputs["Factor"].default_value = 1.0
    tree.links.new(color_socket, mix.inputs["A"])
    tree.links.new(ramp_ao.outputs["Color"], mix.inputs["B"])
    tree.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])

def _add_knots(tree, coord_socket, strength=0.35, scale=6.0):
    vor = tree.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = 'SMOOTH_F1'
    vor.inputs["Scale"].default_value = scale
    vor.location = (coord_socket.node.location.x + 200, coord_socket.node.location.y - 200)
    tree.links.new(coord_socket, vor.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (vor.location.x + 180, vor.location.y)
    ramp.color_ramp.elements[0].position = 0.75
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    tree.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]

def create_stylized_stone(name="M_Building_Stone", color=(0.42, 0.40, 0.38, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.6
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    color_ramp = tree.nodes.new("ShaderNodeValToRGB")
    color_ramp.location = (-180, 0)
    c_dark = (color[0] * 0.7, color[1] * 0.7, color[2] * 0.7, 1.0)
    c_light = (min(1.0, color[0] * 1.15), min(1.0, color[1] * 1.15), min(1.0, color[2] * 1.15), 1.0)
    color_ramp.color_ramp.elements[0].color = c_dark
    color_ramp.color_ramp.elements[1].color = c_light
    tree.links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])
    _apply_crevice_ao(tree, bsdf, color_ramp.outputs["Color"], strength=0.40, distance=0.20)
    _set_bsdf_input(bsdf, "Roughness", 0.88)
    return mat

def create_stylized_plaster(name="M_Building_Plaster", color=(0.88, 0.82, 0.73, 1.0), is_interior=False):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 2.0
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-180, 0)
    mult = 1.05 if is_interior else 1.0
    c_base = (min(1.0, color[0] * mult), min(1.0, color[1] * mult), min(1.0, color[2] * mult), 1.0)
    c_shadow = (color[0] * 0.85, color[1] * 0.85, color[2] * 0.82, 1.0)
    ramp.color_ramp.elements[0].color = c_shadow
    ramp.color_ramp.elements[1].color = c_base
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    _apply_crevice_ao(tree, bsdf, ramp.outputs["Color"], strength=0.35, distance=0.15)
    _set_bsdf_input(bsdf, "Roughness", 0.92)
    return mat

def create_stylized_timber(name="M_Building_Timber", color=(0.28, 0.16, 0.09, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (500, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-500, 0)
    mapping.inputs["Scale"].default_value = (3.5, 0.5, 1.0)
    tree.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-300, 80)
    noise.inputs["Scale"].default_value = 5.5
    noise.inputs["Detail"].default_value = 3.5
    tree.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    vor = tree.nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-300, -120)
    vor.feature = 'SMOOTH_F1'
    vor.inputs["Scale"].default_value = 22.0
    tree.links.new(mapping.outputs["Vector"], vor.inputs["Vector"])
    mix_knot = tree.nodes.new("ShaderNodeMix")
    mix_knot.data_type = 'RGBA'
    mix_knot.blend_type = 'MIX'
    mix_knot.location = (-80, 0)
    mix_knot.inputs["Factor"].default_value = 0.30
    vor_ramp = tree.nodes.new("ShaderNodeValToRGB")
    vor_ramp.location = (-120, -120)
    vor_ramp.color_ramp.elements[0].position = 0.75
    vor_ramp.color_ramp.elements[0].color = (0,0,0,1)
    vor_ramp.color_ramp.elements[1].position = 0.85
    vor_ramp.color_ramp.elements[1].color = (1,1,1,1)
    tree.links.new(vor.outputs["Distance"], vor_ramp.inputs["Fac"])
    tree.links.new(vor_ramp.outputs["Color"], mix_knot.inputs["B"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (20, 0)
    c_bark = (color[0] * 0.60, color[1] * 0.60, color[2] * 0.58, 1.0)
    c_grain = (min(1.0, color[0] * 1.25), min(1.0, color[1] * 1.22), min(1.0, color[2] * 1.18), 1.0)
    c_knot = (color[0]*0.45, color[1]*0.35, color[2]*0.25, 1.0)
    ramp.color_ramp.elements[0].color = c_bark
    ramp.color_ramp.elements[1].color = c_grain
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], mix_knot.inputs["A"])
    knot_mix = tree.nodes.new("ShaderNodeMix")
    knot_mix.data_type = 'RGBA'
    knot_mix.blend_type = 'MULTIPLY'
    knot_mix.location = (120, -80)
    knot_mix.inputs["Factor"].default_value = 0.55
    tree.links.new(mix_knot.outputs["Result"], knot_mix.inputs["A"])
    tree.links.new(vor_ramp.outputs["Color"], knot_mix.inputs["Factor"])
    ramp_knot = tree.nodes.new("ShaderNodeValToRGB")
    ramp_knot.location = (80, -140)
    ramp_knot.color_ramp.elements[0].color = (1,1,1,1)
    ramp_knot.color_ramp.elements[1].color = c_knot
    tree.links.new(vor_ramp.outputs["Color"], ramp_knot.inputs["Fac"])
    tree.links.new(ramp_knot.outputs["Color"], knot_mix.inputs["B"])
    _apply_crevice_ao(tree, bsdf, knot_mix.outputs["Result"], strength=0.42, distance=0.12)
    _set_bsdf_input(bsdf, "Roughness", 0.78)
    return mat

def create_stylized_floorboards(name="M_Building_Floorboards", color=(0.42, 0.28, 0.16, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (500, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-750, 0)
    # Wave bands for plank strips + brick offset for irregular lengths (like reference)
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-550, 80)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.wave_profile = 'SAW'
    wave.inputs["Scale"].default_value = 2.0
    wave.inputs["Distortion"].default_value = 0.55
    tree.links.new(tex_coord.outputs["Object"], wave.inputs["Vector"])
    brick = tree.nodes.new("ShaderNodeTexBrick")
    brick.location = (-550, -30)
    try:
        brick.inputs["Scale"].default_value = 3.5
    except: pass
    for k,v in [("Offset",0.50),("Offset Frequency",3.0),("Squash",7.0),("Mortar Thickness",0.025),("Bias",0.0),("Brick Width",0.5),("Row Height",0.25)]:
        try: brick.inputs[k].default_value = v
        except: pass
    tree.links.new(tex_coord.outputs["Object"], brick.inputs["Vector"])
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-550, -180)
    noise.inputs["Scale"].default_value = 14.0
    noise.inputs["Detail"].default_value = 2.5
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    vor = tree.nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-550, -300)
    vor.inputs["Scale"].default_value = 28.0
    tree.links.new(tex_coord.outputs["Object"], vor.inputs["Vector"])
    mix_wave_brick = tree.nodes.new("ShaderNodeMix")
    mix_wave_brick.location = (-300, 60)
    mix_wave_brick.data_type = 'FLOAT'
    mix_wave_brick.inputs["Factor"].default_value = 0.35
    tree.links.new(wave.outputs["Fac"], mix_wave_brick.inputs[2])
    tree.links.new(brick.outputs["Fac"], mix_wave_brick.inputs[3])
    mix_noise = tree.nodes.new("ShaderNodeMix")
    mix_noise.location = (-300, -40)
    mix_noise.data_type = 'RGBA'
    mix_noise.inputs["Factor"].default_value = 0.28
    vor_ramp = tree.nodes.new("ShaderNodeValToRGB")
    vor_ramp.location = (-300, -300)
    vor_ramp.color_ramp.elements[0].position = 0.78
    vor_ramp.color_ramp.elements[0].color = (0,0,0,1)
    vor_ramp.color_ramp.elements[1].position = 0.88
    vor_ramp.color_ramp.elements[1].color = (1,1,1,1)
    tree.links.new(vor.outputs["Distance"], vor_ramp.inputs["Fac"])
    tree.links.new(noise.outputs["Fac"], mix_noise.inputs["B"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (0, 0)
    c_gap = (color[0] * 0.38, color[1] * 0.36, color[2] * 0.32, 1.0)
    c_dark = (color[0] * 0.78, color[1] * 0.76, color[2] * 0.70, 1.0)
    c_light = (min(1.0, color[0] * 1.22), min(1.0, color[1] * 1.20), min(1.0, color[2] * 1.15), 1.0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = c_gap
    ramp.color_ramp.elements[1].position = 0.18
    ramp.color_ramp.elements[1].color = c_dark
    el_hi = ramp.color_ramp.elements.new(0.85)
    el_hi.color = c_light
    # combine wave/brick + noise + knots
    tree.links.new(mix_wave_brick.outputs["Result"], ramp.inputs["Fac"])
    mix_final = tree.nodes.new("ShaderNodeMix")
    mix_final.location = (150, -20)
    mix_final.data_type = 'RGBA'
    mix_final.blend_type = 'OVERLAY'
    mix_final.inputs["Factor"].default_value = 0.18
    tree.links.new(ramp.outputs["Color"], mix_final.inputs["A"])
    tree.links.new(vor_ramp.outputs["Color"], mix_final.inputs["B"])
    # darken with noise grain
    mix_grain = tree.nodes.new("ShaderNodeMix")
    mix_grain.location = (250, 20)
    mix_grain.data_type = 'RGBA'
    mix_grain.blend_type = 'MULTIPLY'
    mix_grain.inputs["Factor"].default_value = 0.25
    tree.links.new(mix_final.outputs["Result"], mix_grain.inputs["A"])
    tree.links.new(noise.outputs["Fac"], mix_grain.inputs["B"])
    tree.links.new(mix_grain.outputs["Result"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.72)
    return mat

def create_stylized_log_ends(name="M_Building_Log_End", color=(0.48, 0.32, 0.18, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (550, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-750, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-550, 0)
    mapping.inputs["Location"].default_value = (-0.6, -0.9, 0.0)
    tree.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    noise_swirl = tree.nodes.new("ShaderNodeTexNoise")
    noise_swirl.location = (-550, -200)
    noise_swirl.inputs["Scale"].default_value = 0.200
    noise_swirl.inputs["Detail"].default_value = 1.300
    try: noise_swirl.inputs["Roughness"].default_value = 1.0
    except: pass
    try: noise_swirl.inputs["Lacunarity"].default_value = 2.800
    except: pass
    try: noise_swirl.inputs["Distortion"].default_value = 2.600
    except: pass
    tree.links.new(mapping.outputs["Vector"], noise_swirl.inputs["Vector"])
    mix_swirl = tree.nodes.new("ShaderNodeMix")
    mix_swirl.data_type = 'VECTOR'
    mix_swirl.location = (-350, 0)
    mix_swirl.inputs["Factor"].default_value = 0.350
    try: mix_swirl.clamp_factor = True
    except: pass
    tree.links.new(mapping.outputs["Vector"], mix_swirl.inputs["A"])
    tree.links.new(noise_swirl.outputs["Fac"], mix_swirl.inputs["B"])
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-150, 0)
    wave.wave_type = 'RINGS'
    wave.rings_direction = 'SPHERICAL'
    wave.wave_profile = 'SIN'
    wave.inputs["Scale"].default_value = 14.0
    wave.inputs["Distortion"].default_value = 0.900
    wave.inputs["Detail"].default_value = 4.0
    try: wave.inputs["Detail Scale"].default_value = 1.0
    except: pass
    try: wave.inputs["Detail Roughness"].default_value = 0.5
    except: pass
    tree.links.new(mix_swirl.outputs["Result"], wave.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (50, 0)
    c_ring_dark = (color[0] * 0.50, color[1] * 0.46, color[2] * 0.38, 1.0)
    c_ring_mid = (color[0]*0.75, color[1]*0.68, color[2]*0.55, 1.0)
    c_ring_light = (min(1.0, color[0] * 1.20), min(1.0, color[1] * 1.18), min(1.0, color[2] * 1.12), 1.0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = c_ring_dark
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = c_ring_mid
    el = ramp.color_ramp.elements.new(1.0)
    el.color = c_ring_light
    tree.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.82)
    return mat

def create_stylized_shingles(name="M_Building_Shingles", color=(0.20, 0.28, 0.45, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 8.0
    noise.inputs["Detail"].default_value = 2.0
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-180, 0)
    c1 = (color[0] * 0.75, color[1] * 0.78, color[2] * 0.82, 1.0)
    c2 = (min(1.0, color[0] * 1.25), min(1.0, color[1] * 1.2), min(1.0, color[2] * 1.15), 1.0)
    ramp.color_ramp.elements[0].color = c1
    ramp.color_ramp.elements[1].color = c2
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    _apply_crevice_ao(tree, bsdf, ramp.outputs["Color"], strength=0.35, distance=0.10)
    _set_bsdf_input(bsdf, "Roughness", 0.65)
    return mat

def create_stylized_glass(name="M_Building_Glass", color=(0.65, 0.82, 0.95, 0.4), emissive=False, emissive_glow=(1.0, 0.85, 0.45, 1.0), glow_strength=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    _set_bsdf_input(bsdf, "Base Color", (color[0], color[1], color[2], 1.0))
    _set_bsdf_input(bsdf, "Roughness", 0.1)
    _set_bsdf_input(bsdf, "IOR", 1.45)
    _set_bsdf_input(bsdf, "Alpha", color[3])
    if emissive or glow_strength > 0.01:
        _set_bsdf_input(bsdf, "Emission Color", (emissive_glow[0], emissive_glow[1], emissive_glow[2], 1.0))
        _set_bsdf_input(bsdf, "Emission Strength", glow_strength if glow_strength > 0.01 else 2.5)
    else:
        _set_bsdf_input(bsdf, "Emission Strength", 0.0)
    return mat

def create_stylized_iron(name="M_Building_Iron", color=(0.12, 0.12, 0.13, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    _set_bsdf_input(bsdf, "Base Color", color)
    _set_bsdf_input(bsdf, "Metallic", 0.9)
    _set_bsdf_input(bsdf, "Roughness", 0.45)
    return mat

def create_stylized_log_walls(name="M_Building_Log_Walls", color=(0.32, 0.20, 0.12, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (500, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-520, 0)
    mapping.inputs["Scale"].default_value = (0.5, 3.5, 1.0)
    tree.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    # Clean longitudinal grain along log length (V) — like reference log
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-350, 80)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.wave_profile = 'SIN'
    wave.inputs["Scale"].default_value = 6.0
    wave.inputs["Distortion"].default_value = 0.45
    wave.inputs["Detail"].default_value = 2.5
    tree.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-350, -80)
    noise.inputs["Scale"].default_value = 12.0
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.55
    tree.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    vor = tree.nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-350, -200)
    vor.feature = 'SMOOTH_F1'
    vor.inputs["Scale"].default_value = 14.0
    vor.inputs["Randomness"].default_value = 1.0
    tree.links.new(mapping.outputs["Vector"], vor.inputs["Vector"])
    mix1 = tree.nodes.new("ShaderNodeMix")
    mix1.location = (-260, 60)
    mix1.data_type = 'FLOAT'
    mix1.inputs["Factor"].default_value = 0.22
    tree.links.new(wave.outputs["Fac"], mix1.inputs[2])
    tree.links.new(noise.outputs["Fac"], mix1.inputs[3])
    vor_ramp = tree.nodes.new("ShaderNodeValToRGB")
    vor_ramp.location = (-260, -200)
    vor_ramp.color_ramp.elements[0].position = 0.78
    vor_ramp.color_ramp.elements[0].color = (0,0,0,1)
    vor_ramp.color_ramp.elements[1].position = 0.86
    vor_ramp.color_ramp.elements[1].color = (1,1,1,1)
    tree.links.new(vor.outputs["Distance"], vor_ramp.inputs["Fac"])
    mix2 = tree.nodes.new("ShaderNodeMix")
    mix2.location = (-80, 0)
    mix2.data_type = 'RGBA'
    mix2.blend_type = 'OVERLAY'
    mix2.inputs["Factor"].default_value = 0.18
    tree.links.new(mix1.outputs["Result"], mix2.inputs["A"])
    tree.links.new(vor_ramp.outputs["Color"], mix2.inputs["B"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (70, 0)
    c_crevice = (color[0] * 0.58, color[1] * 0.56, color[2] * 0.50, 1.0)
    c_highlight = (min(1.0, color[0] * 1.28), min(1.0, color[1] * 1.26), min(1.0, color[2] * 1.22), 1.0)
    ramp.color_ramp.elements[0].color = c_crevice
    ramp.color_ramp.elements[1].color = c_highlight
    tree.links.new(mix2.outputs["Result"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.78)
    return mat

def create_stylized_plank_siding(name="M_Building_Plank_Siding", color=(0.68, 0.58, 0.44, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-400, 0)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    wave.wave_profile = 'SAW'
    wave.inputs["Scale"].default_value = 5.0
    wave.inputs["Distortion"].default_value = 0.4
    tree.links.new(tex_coord.outputs["Object"], wave.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-150, 0)
    c_shadow = (color[0] * 0.70, color[1] * 0.70, color[2] * 0.68, 1.0)
    c_body = (color[0], color[1], color[2], 1.0)
    ramp.color_ramp.elements[0].color = c_shadow
    ramp.color_ramp.elements[1].color = c_body
    tree.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.78)
    return mat

def setup_building_material_slots(obj, props):
    """
    Ensures that the 15 canonical stylized material slots are populated on the object,
    now fully split: logs/beams/pillars/stairs/railing/window-frame each have own stylized shader with correct handpainted UV baselines.
    """
    tier = getattr(props, "material_tier", "TIER_3")
    is_palette = getattr(props, "color_palette", "CUSTOM") != "CUSTOM"
    if props.custom_stone:
        mat_stone = props.custom_stone
    elif is_palette:
        mat_stone = create_stylized_stone(f"M_Building_Stone_{tier}", color=props.color_stone)
    elif tier == 'TIER_1':
        mat_stone = create_stylized_stone("M_Building_Stone_T1", color=(0.32, 0.30, 0.28, 1.0))
    elif tier == 'TIER_2':
        mat_stone = create_stylized_stone("M_Building_Stone_T2", color=(0.42, 0.40, 0.38, 1.0))
    else:
        mat_stone = create_stylized_stone("M_Building_Stone_T3", color=props.color_stone)
    if props.custom_wall_ext:
        mat_plaster_ext = props.custom_wall_ext
    elif is_palette:
        mat_plaster_ext = create_stylized_plaster("M_Building_Plaster_Ext", color=props.color_wall_ext, is_interior=False)
    elif tier == 'TIER_1':
        mat_plaster_ext = create_stylized_log_walls("M_Building_Log_Ext", color=(0.32, 0.20, 0.12, 1.0))
    elif tier == 'TIER_2':
        mat_plaster_ext = create_stylized_plank_siding("M_Building_Plank_Ext", color=(0.68, 0.58, 0.44, 1.0))
    else:
        mat_plaster_ext = create_stylized_plaster("M_Building_Plaster_Ext", color=props.color_wall_ext, is_interior=False)
    if props.custom_wall_int:
        mat_plaster_int = props.custom_wall_int
    elif is_palette:
        mat_plaster_int = create_stylized_plaster("M_Building_Plaster_Int", color=props.color_wall_int, is_interior=True)
    elif tier == 'TIER_1':
        mat_plaster_int = create_stylized_timber("M_Building_Log_Int", color=(0.42, 0.30, 0.20, 1.0))
    elif tier == 'TIER_2':
        mat_plaster_int = create_stylized_plank_siding("M_Building_Plank_Int", color=(0.76, 0.68, 0.56, 1.0))
    else:
        mat_plaster_int = create_stylized_plaster("M_Building_Plaster_Int", color=props.color_wall_int, is_interior=True)
    clr_tf = getattr(props, 'color_timber_frame', (0.22, 0.13, 0.07, 1.0))
    custom_tf = getattr(props, 'custom_timber_frame', None)
    if custom_tf:
        mat_timber_frame = custom_tf
    elif is_palette:
        mat_timber_frame = create_stylized_timber("M_Building_Timber_Frame", color=clr_tf)
    elif tier == 'TIER_1':
        mat_timber_frame = create_stylized_timber("M_Building_Timber_Frame_T1", color=clr_tf)
    elif tier == 'TIER_2':
        mat_timber_frame = create_stylized_timber("M_Building_Timber_Frame_T2", color=clr_tf)
    else:
        mat_timber_frame = create_stylized_timber("M_Building_Timber_Frame_T3", color=clr_tf)
    if props.custom_floor:
        mat_floor = props.custom_floor
    else:
        mat_floor = create_stylized_floorboards("M_Building_Floorboards", color=props.color_floor)
    if props.custom_shingles:
        mat_shingles = props.custom_shingles
    elif is_palette:
        mat_shingles = create_stylized_shingles(f"M_Building_Shingles_{tier}", color=props.color_shingles)
    elif tier == 'TIER_1':
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T1", color=(0.28, 0.18, 0.11, 1.0))
    elif tier == 'TIER_2':
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T2", color=(0.30, 0.40, 0.48, 1.0))
    else:
        mat_shingles = create_stylized_shingles("M_Building_Shingles_T3", color=props.color_shingles)
    mat_glass = props.custom_glass if props.custom_glass else create_stylized_glass(
        glow_strength=props.window_glow_strength,
        emissive_glow=props.color_window_glow
    )
    mat_door = props.custom_door if props.custom_door else create_stylized_timber("M_Building_Door", color=props.color_door)
    mat_iron = props.custom_iron if props.custom_iron else create_stylized_iron()
    clr_wood = getattr(props, 'color_timber', (0.32, 0.20, 0.11, 1.0))
    custom_wood = getattr(props, 'custom_timber', None)
    if custom_wood:
        mat_wood = custom_wood
    else:
        mat_wood = create_stylized_timber("M_Building_Wood", color=clr_wood)
    clr_log_end = getattr(props, 'color_log_end', (0.48, 0.32, 0.18, 1.0))
    custom_log_end = getattr(props, 'custom_log_end', None)
    if custom_log_end:
        mat_log_end = custom_log_end
    else:
        mat_log_end = create_stylized_log_ends("M_Building_Log_End", color=clr_log_end)
    # Split materials — reuse distinct shades but keep UV baselines correct
    # LOGS: darker, rougher
    clr_log = (clr_tf[0]*0.88, clr_tf[1]*0.85, clr_tf[2]*0.80, 1.0)
    mat_log = create_stylized_timber("M_Building_Log", color=clr_log)
    # STAIRS: slightly warmer
    clr_stairs = (clr_wood[0]*1.02, clr_wood[1]*1.01, clr_wood[2]*0.98, 1.0)
    mat_stairs = create_stylized_timber("M_Building_Stairs", color=clr_stairs)
    # RAILING: lighter for visibility
    clr_rail = (min(1.0, clr_wood[0]*1.08), min(1.0, clr_wood[1]*1.06), min(1.0, clr_wood[2]*1.02), 1.0)
    mat_railing = create_stylized_timber("M_Building_Railing", color=clr_rail)
    clr_win = (min(1.0, clr_wood[0]*1.05), min(1.0, clr_wood[1]*1.02), clr_wood[2], 1.0)
    mat_window = create_stylized_timber("M_Building_Window_Frame", color=clr_win)
    clr_shutter = (clr_win[0]*0.92, clr_win[1]*0.90, clr_win[2]*0.88, 1.0)
    mat_shutter = create_stylized_timber("M_Building_Shutter", color=clr_shutter)
    try:
        mat_shutter.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.80
    except: pass
    required_mats = [
        mat_stone,          # 0
        mat_plaster_ext,    # 1
        mat_plaster_int,    # 2
        mat_timber_frame,   # 3 beams/pillars/corbel
        mat_floor,          # 4
        mat_shingles,       # 5
        mat_glass,          # 6
        mat_door,           # 7
        mat_iron,           # 8
        mat_wood,           # 9 general
        mat_log_end,        # 10
        mat_log,            # 11 logs
        mat_stairs,         # 12 stairs
        mat_railing,        # 13 railing
        mat_window,         # 14 window frame
        mat_shutter,        # 15 shutter
    ]
    obj.data.materials.clear()
    for m in required_mats:
        obj.data.materials.append(m)
