import bpy
import math
import os

addon_dir = os.path.dirname(os.path.abspath(__file__))
artifact_dir = "C:/Users/Sebastian/.gemini/antigravity-ide/brain/1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

import sys
if addon_dir not in sys.path:
    sys.path.append(addon_dir)
import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 960

# World sky
world = bpy.data.worlds.new("StylizedWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.2, 0.35, 0.55, 1.0)
    bg_node.inputs[1].default_value = 1.0

# Key Light
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 4.5
light_data.color = (1.0, 0.96, 0.88)
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(-30))

# Fill Light
fill_data = bpy.data.lights.new(name="FillSun", type='SUN')
fill_data.energy = 2.0
fill_data.color = (0.6, 0.75, 0.95)
fill_obj = bpy.data.objects.new(name="FillSun", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(30), math.radians(-20), math.radians(150))

# Camera
cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 50
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Create building
bpy.ops.building.create_fantasy_building()
props = scene.fantasy_building_settings
props.material_tier = 'TIER_2'
props.has_front_door = True
props.door_angle = 35.0
props.has_lanterns = True
props.has_front_steps = True
props.has_hoist_beam = True
bpy.ops.building.regenerate()

# 1. Front door & lantern close-up
cam_obj.location = (0.35, -3.2, 1.35)
cam_obj.rotation_euler = (math.radians(82), 0.0, math.radians(8))
scene.render.filepath = os.path.join(artifact_dir, "preview_handcrafted_door_lantern.png")
bpy.ops.render.render(write_still=True)

# 2. Hoist beam & forged J-hook close-up
top_z = 0.2 + props.num_floors * props.floor_height
ridge_z = top_z + props.roof_height
front_y = -props.depth * 0.5 - props.roof_overhang
cam_obj.location = (0.0, front_y - 2.6, ridge_z - 0.7)
cam_obj.rotation_euler = (math.radians(72), 0.0, math.radians(0))
scene.render.filepath = os.path.join(artifact_dir, "preview_forged_cargo_hook.png")
bpy.ops.render.render(write_still=True)

print("Detail renders complete!")
