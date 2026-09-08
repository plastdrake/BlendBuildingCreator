"""
Stylized Procedural Shader Generator and Material Slot Manager for Blender 5.2.
Creates warm, hand-crafted stylized materials with soft noise, ambient occlusions,
edge highlights, and rich fantasy palettes.
"""

import bpy

# Material slot index constants
MAT_INDEX_STONE = 0
MAT_INDEX_PLASTER_EXT = 1
MAT_INDEX_PLASTER_INT = 2
MAT_INDEX_TIMBER = 3
MAT_INDEX_FLOOR = 4
MAT_INDEX_SHINGLES = 5
MAT_INDEX_GLASS = 6
MAT_INDEX_DOOR = 7
MAT_INDEX_IRON = 8

def _set_bsdf_input(bsdf, input_name, value):
    """Safely sets input on Principled BSDF across Blender versions."""
    sock = bsdf.inputs.get(input_name)
    if sock is not None:
        sock.default_value = value

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
    tree.links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
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
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
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
    
    # Stretched noise for wood grain
    tex_coord = tree.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.location = (-500, 0)
    mapping.inputs["Scale"].default_value = (0.5, 0.5, 4.0)
    tree.links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
    
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-300, 0)
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 3.0
    tree.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-100, 0)
    c_bark = (color[0] * 0.65, color[1] * 0.65, color[2] * 0.65, 1.0)
    c_grain = (min(1.0, color[0] * 1.2), min(1.0, color[1] * 1.2), min(1.0, color[2] * 1.15), 1.0)
    ramp.color_ramp.elements[0].color = c_bark
    ramp.color_ramp.elements[1].color = c_grain
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
    _set_bsdf_input(bsdf, "Roughness", 0.75)
    return mat

def create_stylized_floorboards(name="M_Building_Floorboards", color=(0.38, 0.24, 0.14, 1.0)):
    return create_stylized_timber(name=name, color=color)

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
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
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

def setup_building_material_slots(obj, props):
    """
    Ensures that the 9 canonical stylized material slots are populated on the object,
    using either user-specified custom material overrides or freshly created stylized procedural shaders.
    """
    # 0: Stone
    mat_stone = props.custom_stone if props.custom_stone else create_stylized_stone(color=props.color_stone)
    # 1: Plaster Exterior
    mat_plaster_ext = props.custom_wall_ext if props.custom_wall_ext else create_stylized_plaster("M_Building_Plaster_Ext", color=props.color_wall_ext, is_interior=False)
    # 2: Plaster Interior
    mat_plaster_int = props.custom_wall_int if props.custom_wall_int else create_stylized_plaster("M_Building_Plaster_Int", color=props.color_wall_int, is_interior=True)
    # 3: Timber Beams
    mat_timber = props.custom_timber if props.custom_timber else create_stylized_timber(color=props.color_timber)
    # 4: Floorboards
    mat_floor = props.custom_floor if props.custom_floor else create_stylized_floorboards(color=props.color_floor)
    # 5: Roof Shingles
    mat_shingles = props.custom_shingles if props.custom_shingles else create_stylized_shingles(color=props.color_shingles)
    # 6: Window Glass
    mat_glass = props.custom_glass if props.custom_glass else create_stylized_glass(
        glow_strength=props.window_glow_strength,
        emissive_glow=props.color_window_glow
    )
    # 7: Door
    mat_door = props.custom_door if props.custom_door else create_stylized_timber("M_Building_Door", color=props.color_door)
    # 8: Iron
    mat_iron = props.custom_iron if props.custom_iron else create_stylized_iron()
    
    required_mats = [
        mat_stone,
        mat_plaster_ext,
        mat_plaster_int,
        mat_timber,
        mat_floor,
        mat_shingles,
        mat_glass,
        mat_door,
        mat_iron
    ]
    
    obj.data.materials.clear()
    for m in required_mats:
        obj.data.materials.append(m)
