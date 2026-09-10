import bpy
import math
import os
import sys
from mathutils import Vector, Euler

sys.path.insert(0, r"d:\BlendBuildingCreator")
import blend_building_creator
blend_building_creator.register()

def setup_render_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
        
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    
    world = bpy.data.worlds.new("VerificationWorld9")
    scene.world = world
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.75, 0.82, 0.90, 1.0)
        bg.inputs['Strength'].default_value = 0.9
        
    # Sun light
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.5
    sun_data.color = (1.0, 0.96, 0.90)
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = Euler((math.radians(50), math.radians(20), math.radians(-40)), 'XYZ')
    
    # Fill light
    fill_data = bpy.data.lights.new(name="Fill", type='SUN')
    fill_data.energy = 1.5
    fill_data.color = (0.80, 0.88, 1.0)
    fill_obj = bpy.data.objects.new(name="Fill", object_data=fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = Euler((math.radians(45), 0, math.radians(140)), 'XYZ')

    # Interior room point light
    int_light = bpy.data.lights.new(name="IntLight", type='POINT')
    int_light.energy = 300.0
    int_light.color = (1.0, 0.92, 0.82)
    int_obj = bpy.data.objects.new(name="IntLight", object_data=int_light)
    scene.collection.objects.link(int_obj)
    int_obj.location = (0.0, 0.0, 1.8)

    # Camera
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 45
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return cam_obj

def render_camera_target(cam_obj, cam_pos, target_pos, output_path):
    cam_obj.location = Vector(cam_pos)
    dir_vec = (Vector(target_pos) - cam_obj.location).normalized()
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"
os.makedirs(out_dir, exist_ok=True)

cam = setup_render_scene()

# -------------------------------------------------------------
# SCENE 1: Dormer Rear Wall Extension & Shingle Offset
# -------------------------------------------------------------
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.width = 6.0
props.depth = 6.0
props.num_floors = 2
props.has_dormers = True
props.roof_style = 'SWAY'
props.has_roof_shingles = True
bpy.ops.building.regenerate()

# View 1: Dormer cheek and rear wall meeting roof deck
render_camera_target(
    cam,
    cam_pos=(-4.6, 2.0, 8.4),
    target_pos=(-1.8, 1.2, 7.5),
    output_path=os.path.join(out_dir, "round9_view1_dormer_rear_roof.png")
)

# -------------------------------------------------------------
# SCENE 2: Arched Doorway Fit & Arched Planks
# -------------------------------------------------------------
props.has_dormers = False
props.door_shape = 'ARCHED'
props.door_angle = 35.0
props.ground_floor_stone = True
bpy.ops.building.regenerate()

# View 2: Front door head-on showing arched contour cut planks and snug stone surround
render_camera_target(
    cam,
    cam_pos=(0.0, -5.6, 1.4),
    target_pos=(0.0, -3.0, 1.2),
    output_path=os.path.join(out_dir, "round9_view2_arched_door_fit.png")
)

# -------------------------------------------------------------
# SCENE 3: Grounded Mini-Wing Outcrop (Foundation to Z=0, Pilasters, Casing Frame)
# -------------------------------------------------------------
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.mini_wing_width = 2.4
props.mini_wing_depth = 1.6
props.mini_wing_roof = 'LEAN_TO'
bpy.ops.building.regenerate()

# View 3: Grounded outcrop on Left wall showing foundation to ground, junction posts, window frame
render_camera_target(
    cam,
    cam_pos=(-7.2, -2.4, 2.2),
    target_pos=(-3.8, 0.0, 1.5),
    output_path=os.path.join(out_dir, "round9_view3_grounded_outcrop.png")
)

# -------------------------------------------------------------
# SCENE 4: Balcony (Multi-Plank Door, Extended Diagonal Struts, Shutter Clearance)
# -------------------------------------------------------------
props.has_mini_wing = False
props.has_balcony = True
props.balcony_side = 'BACK'
props.balcony_floor = 2
props.balcony_width = 2.4
props.balcony_depth = 1.4
props.has_shutters = True
bpy.ops.building.regenerate()

# View 4: Balcony on Back facade showing planks, extended diagonal braces, and clearance
render_camera_target(
    cam,
    cam_pos=(2.2, 7.2, 4.2),
    target_pos=(0.0, 3.8, 3.8),
    output_path=os.path.join(out_dir, "round9_view4_balcony_complete.png")
)

# -------------------------------------------------------------
# SCENE 5: Overhanging Wing Building Floor Soffit
# -------------------------------------------------------------
props.has_balcony = False
props.building_shape = 'L_SHAPE'
props.wing_side = 'LEFT'
props.wing_width = 3.6
props.wing_depth = 3.6
props.wing_floors = 2
props.num_floors = 2
props.has_cantilever = True
props.cantilever_overhang = 0.40
bpy.ops.building.regenerate()

# View 5: Low upward angle looking up at wing overhang underside sealed with timber soffit
render_camera_target(
    cam,
    cam_pos=(-4.5, -6.5, 0.8),
    target_pos=(-3.0, -4.5, 2.8),
    output_path=os.path.join(out_dir, "round9_view5_wing_overhang_soffit.png")
)

print("ALL_VIEWS_RENDERED_OK")
