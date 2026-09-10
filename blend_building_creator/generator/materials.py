"""
Stylized Procedural Shader Generator and Material Slot Manager for Blender 5.2.
Creates warm, hand-crafted stylized materials with soft noise, ambient occlusions,
edge highlights, and rich fantasy palettes.
"""

import bpy

# Material slot index constants (11 canonical slots)
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

# Alias for backwards compatibility
MAT_INDEX_TIMBER = MAT_INDEX_TIMBER_FRAME

def _set_bsdf_input(bsdf, input_name, value):
    """Safely sets input on Principled BSDF across Blender versions."""
    sock = bsdf.inputs.get(input_name)
    if sock is not None:
        sock.default_value = value

def _apply_crevice_ao(tree, bsdf, color_socket, strength=0.45, distance=0.15):
    """
    Darkens base color in geometric crevices (between logs, beams, stone courses) via
    Ambient Occlusion, giving surfaces a hand-painted, less flat/plastic look.
    """
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

def create_stylized_stone(name="M_Building_Stone", color=(0.42, 0.40, 0.38, 1.0)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    
    # Output & BSDF
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    # Stylized noise variation
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
    # Darker stone crevice vs lighter surface
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
    
    # Soft organic mottled noise
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
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    # Stretched noise along UV coordinate V (beam length axis)
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-500, 0)
    # Stretches grain along V (length)
    mapping.inputs["Scale"].default_value = (4.0, 0.4, 1.0)
    tree.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-300, 0)
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 3.0
    tree.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    c_bark = (color[0] * 0.65, color[1] * 0.65, color[2] * 0.65, 1.0)
    c_grain = (min(1.0, color[0] * 1.2), min(1.0, color[1] * 1.2), min(1.0, color[2] * 1.15), 1.0)
    ramp.color_ramp.elements[0].color = c_bark
    ramp.color_ramp.elements[1].color = c_grain
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    _apply_crevice_ao(tree, bsdf, ramp.outputs["Color"], strength=0.40, distance=0.12)
    
    _set_bsdf_input(bsdf, "Roughness", 0.75)
    return mat

def create_stylized_floorboards(name="M_Building_Floorboards", color=(0.42, 0.28, 0.16, 1.0)):
    """Procedural floorboards with repeating parallel planks and edge groove separations."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (450, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (150, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-750, 0)
    
    # Wave texture along Y for repeating floor plank strips
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-550, 60)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.wave_profile = 'SAW'
    wave.inputs["Scale"].default_value = 3.5
    wave.inputs["Distortion"].default_value = 0.25
    tree.links.new(tex_coord.outputs["Object"], wave.inputs["Vector"])
    
    # Subtle wood grain noise across the planks
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-550, -180)
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 2.0
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    
    mix_rgb = tree.nodes.new("ShaderNodeMix")
    mix_rgb.location = (-300, 0)
    mix_rgb.data_type = 'RGBA'
    mix_rgb.inputs["Factor"].default_value = 0.35
    tree.links.new(wave.outputs["Fac"], mix_rgb.inputs["A"])
    tree.links.new(noise.outputs["Fac"], mix_rgb.inputs["B"])
    
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    c_gap = (color[0] * 0.40, color[1] * 0.38, color[2] * 0.35, 1.0)
    c_shadow = (color[0] * 0.80, color[1] * 0.78, color[2] * 0.75, 1.0)
    c_highlight = (min(1.0, color[0] * 1.15), min(1.0, color[1] * 1.15), min(1.0, color[2] * 1.10), 1.0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = c_gap
    ramp.color_ramp.elements[1].position = 0.15
    ramp.color_ramp.elements[1].color = c_shadow
    el_hi = ramp.color_ramp.elements.new(0.85)
    el_hi.color = c_highlight
    
    tree.links.new(mix_rgb.outputs["Result"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.70)
    return mat

def create_stylized_log_ends(name="M_Building_Log_End", color=(0.48, 0.32, 0.18, 1.0)):
    """Procedural annual growth rings for cut ends of horizontal timber logs."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    
    node_out = tree.nodes.new("ShaderNodeOutputMaterial")
    node_out.location = (450, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (150, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-750, 0)
    
    # Center UV at (0.5, 0.5) for radial rings
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-550, 0)
    mapping.inputs["Location"].default_value = (-0.5, -0.5, 0.0)
    tree.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    
    # Concentric rings wave texture
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-320, 0)
    wave.wave_type = 'RINGS'
    wave.rings_direction = 'SPHERICAL'
    wave.wave_profile = 'SAW'
    wave.inputs["Scale"].default_value = 18.0
    wave.inputs["Distortion"].default_value = 1.2
    wave.inputs["Detail"].default_value = 2.0
    tree.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-80, 0)
    c_ring_dark = (color[0] * 0.55, color[1] * 0.52, color[2] * 0.45, 1.0)
    c_ring_light = (min(1.0, color[0] * 1.15), min(1.0, color[1] * 1.15), min(1.0, color[2] * 1.10), 1.0)
    ramp.color_ramp.elements[0].color = c_ring_dark
    ramp.color_ramp.elements[1].color = c_ring_light
    tree.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _set_bsdf_input(bsdf, "Roughness", 0.85)
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
    
    # Tile color nuance
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
    node_out.location = (400, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    tree.links.new(bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    
    # Wave texture for horizontal logs
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.location = (-450, 50)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    wave.inputs["Scale"].default_value = 3.2
    wave.inputs["Distortion"].default_value = 1.2
    wave.inputs["Detail"].default_value = 2.0
    tree.links.new(tex_coord.outputs["Object"], wave.inputs["Vector"])
    
    # Soft wood noise
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-450, -150)
    noise.inputs["Scale"].default_value = 6.0
    tree.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
    
    # Mix wave and noise
    mix = tree.nodes.new("ShaderNodeMix")
    mix.location = (-250, 0)
    mix.data_type = 'FLOAT'
    mix.inputs["Factor"].default_value = 0.25
    tree.links.new(wave.outputs["Color"], mix.inputs[2])
    tree.links.new(noise.outputs["Fac"], mix.inputs[3])
    
    # Color ramp for rich bark and wood tones
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-50, 0)
    c_crevice = (color[0] * 0.55, color[1] * 0.55, color[2] * 0.50, 1.0)
    c_highlight = (min(1.0, color[0] * 1.3), min(1.0, color[1] * 1.3), min(1.0, color[2] * 1.25), 1.0)
    ramp.color_ramp.elements[0].color = c_crevice
    ramp.color_ramp.elements[1].color = c_highlight
    tree.links.new(mix.outputs["Result"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
    _set_bsdf_input(bsdf, "Roughness", 0.85)
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
    
    # Wave texture for crisp horizontal weatherboard planks
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
    Ensures that the 11 canonical stylized material slots are populated on the object,
    configured according to the chosen Material Tier or custom user material overrides:
    0: Stone, 1: Ext Wall, 2: Int Wall, 3: Timber Frame, 4: Floorboards,
    5: Shingles, 6: Glass, 7: Door, 8: Iron, 9: General Wood, 10: Log End Rings.
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

    # 3. Timber Framing (external structural posts, horizontal wall plates, diagonal braces)
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

    # 4. Interior Floorboards
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

    # 9. General Wood Carpentry (stairs, railings, roof trim, window frames)
    clr_wood = getattr(props, 'color_timber', (0.32, 0.20, 0.11, 1.0))
    custom_wood = getattr(props, 'custom_timber', None)
    if custom_wood:
        mat_wood = custom_wood
    else:
        mat_wood = create_stylized_timber("M_Building_Wood", color=clr_wood)

    # 10. Cut Log Ends (concentric annual tree growth rings)
    clr_log_end = getattr(props, 'color_log_end', (0.48, 0.32, 0.18, 1.0))
    custom_log_end = getattr(props, 'custom_log_end', None)
    if custom_log_end:
        mat_log_end = custom_log_end
    else:
        mat_log_end = create_stylized_log_ends("M_Building_Log_End", color=clr_log_end)

    required_mats = [
        mat_stone,          # 0
        mat_plaster_ext,    # 1
        mat_plaster_int,    # 2
        mat_timber_frame,   # 3
        mat_floor,          # 4
        mat_shingles,       # 5
        mat_glass,          # 6
        mat_door,           # 7
        mat_iron,           # 8
        mat_wood,           # 9
        mat_log_end,        # 10
    ]
    
    obj.data.materials.clear()
    for m in required_mats:
        obj.data.materials.append(m)
