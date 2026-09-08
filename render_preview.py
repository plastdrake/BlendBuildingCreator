"""
Renders exterior and interior preview images using Blender 5.2.
"""

import os
import bpy
import math

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

# Create Tavern building
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="TAVERN")
building = bpy.context.active_object

# Open door slightly for walk-in feel
props = bpy.context.scene.fantasy_building_settings
props.door_angle = 50.0
bpy.ops.building.regenerate()

# Setup Lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.95, 0.88)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(40))

# Ambient world light
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.55, 0.70, 0.88, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings (Cycles on CPU works 100% headlessly without GPU window server)
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

# 1. Exterior Camera (Frame the entire building from roof to foundation)
cam_data = bpy.data.cameras.new(name="ExtCamera")
cam_data.lens = 28
cam_obj = bpy.data.objects.new(name="ExtCamera", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (15.0, -18.0, 10.0)
cam_obj.rotation_euler = (math.radians(63), 0, math.radians(40))
bpy.context.scene.camera = cam_obj

out_ext = os.path.join(os.path.dirname(__file__), "preview_exterior.png")
bpy.context.scene.render.filepath = out_ext
bpy.ops.render.render(write_still=True)
print("EXTERIOR RENDER COMPLETE:", out_ext)

# 2. Interior Camera (Standing just inside the ground floor looking toward staircase & ceiling beams)
cam_data_int = bpy.data.cameras.new(name="IntCamera")
cam_data_int.lens = 20 # Wide angle for interior
cam_obj_int = bpy.data.objects.new(name="IntCamera", object_data=cam_data_int)
bpy.context.scene.collection.objects.link(cam_obj_int)
# Inside looking back toward the staircase
cam_obj_int.location = (0.5, -1.2, 1.6)
cam_obj_int.rotation_euler = (math.radians(82), 0, math.radians(-35))
bpy.context.scene.camera = cam_obj_int

# Add a cozy warm interior point light
warm_light_data = bpy.data.lights.new(name="InteriorLight", type='POINT')
warm_light_data.energy = 80.0
warm_light_data.color = (1.0, 0.82, 0.55)
warm_light_obj = bpy.data.objects.new(name="InteriorLight", object_data=warm_light_data)
bpy.context.scene.collection.objects.link(warm_light_obj)
warm_light_obj.location = (0.0, 0.0, 2.3)

out_int = os.path.join(os.path.dirname(__file__), "preview_interior.png")
bpy.context.scene.render.filepath = out_int
bpy.ops.render.render(write_still=True)
print("INTERIOR RENDER COMPLETE:", out_int)
