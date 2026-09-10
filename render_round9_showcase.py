import bpy
import math
import os
import sys
from mathutils import Vector, Euler

sys.path.insert(0, r"d:\BlendBuildingCreator")
import blend_building_creator

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
    
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720

world = bpy.data.worlds.new("ShowcaseWorld")
scene.world = world
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.75, 0.82, 0.90, 1.0)
    bg.inputs['Strength'].default_value = 0.9
    
sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = Euler((math.radians(50), math.radians(20), math.radians(-40)), 'XYZ')

fill_data = bpy.data.lights.new(name="Fill", type='SUN')
fill_data.energy = 1.5
fill_data.color = (0.80, 0.88, 1.0)
fill_obj = bpy.data.objects.new(name="Fill", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = Euler((math.radians(45), 0, math.radians(140)), 'XYZ')

cam_data = bpy.data.cameras.new(name="Camera")
cam_data.lens = 38
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

def render_view(cam_pos, target_pos, filename):
    cam_obj.location = Vector(cam_pos)
    dir_vec = (Vector(target_pos) - cam_obj.location).normalized()
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()
    filepath = os.path.join(out_dir, filename)
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {filepath}")

# 1. Arched Door Showcase (Full Arch & Contoured Planks)
bpy.ops.building.create_fantasy_building()
props = scene.fantasy_building_settings
props.width = 6.0
props.depth = 6.0
props.num_floors = 2
props.ground_floor_stone = True
props.door_shape = 'ARCHED'
props.door_angle = 35.0
props.has_timber_framing = False # Clean stone facade to focus entirely on arched doorway masonry
bpy.ops.building.regenerate()

render_view(
    cam_pos=(0.0, -6.5, 1.8),
    target_pos=(0.0, -3.0, 1.4),
    filename="round9_view2_arched_door_fit.png"
)

# 2. Grounded Mini-Wing Outcrop (Full View: Foundation to Z=0, Pilaster Posts, Window Frame)
props.has_timber_framing = True
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.mini_wing_width = 2.4
props.mini_wing_depth = 1.6
props.mini_wing_roof = 'LEAN_TO'
bpy.ops.building.regenerate()

render_view(
    cam_pos=(-8.0, -4.5, 2.2),
    target_pos=(-4.2, 0.0, 1.2),
    filename="round9_view3_grounded_outcrop.png"
)

# 3. Wing Overhang Underneath View (Soffit Sealing Floor)
props.has_mini_wing = False
props.building_shape = 'L_SHAPE'
props.wing_side = 'LEFT'
props.wing_width = 3.6
props.wing_depth = 3.6
props.wing_floors = 2
props.num_floors = 2
props.has_cantilever = True
props.cantilever_overhang = 0.40
bpy.ops.building.regenerate()

render_view(
    cam_pos=(-2.2, -7.5, 0.6),
    target_pos=(-3.6, -5.0, 2.9),
    filename="round9_view5_wing_overhang_soffit.png"
)

print("SHOWCASE_COMPLETE")
