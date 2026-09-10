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

world = bpy.data.worlds.new("VerificationWorld")
scene.world = world
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.75, 0.82, 0.90, 1.0)
    bg.inputs['Strength'].default_value = 0.9
    
sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_data.energy = 3.5
sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = Euler((math.radians(50), math.radians(20), math.radians(-40)), 'XYZ')

fill_data = bpy.data.lights.new(name="Fill", type='SUN')
fill_data.energy = 1.5
fill_obj = bpy.data.objects.new(name="Fill", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = Euler((math.radians(45), 0, math.radians(140)), 'XYZ')

int_light = bpy.data.lights.new(name="IntLight", type='POINT')
int_light.energy = 450.0
int_obj = bpy.data.objects.new(name="IntLight", object_data=int_light)
scene.collection.objects.link(int_obj)
int_obj.location = (0.0, 0.0, 1.8)

# Building setup
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.width = 6.0
props.depth = 6.0
props.num_floors = 2
props.has_stairs = False
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.mini_wing_width = 2.4
props.mini_wing_depth = 1.6
props.mini_wing_roof = 'LEAN_TO'
bpy.ops.building.regenerate()

cam_data = bpy.data.cameras.new(name="Camera")
cam_data.lens = 40
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# View 4: Exterior full view of outcrop mini-wing
cam_obj.location = (-7.5, -4.8, 3.2)
cam_obj.rotation_euler = (math.radians(72), 0, math.radians(-55))
scene.render.filepath = os.path.join(out_dir, "round8_view4_miniwing_exterior.png")
bpy.ops.render.render(write_still=True)

# View 7: Interior walk-in view through archway into mini-wing
cam_obj.location = (0.5, 0.0, 1.3)
cam_obj.rotation_euler = (math.radians(90), 0, math.radians(90))
scene.render.filepath = os.path.join(out_dir, "round8_view7_interior_walkin_miniwing.png")
bpy.ops.render.render(write_still=True)

print("Views 4 and 7 rendered successfully!")
