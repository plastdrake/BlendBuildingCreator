import bpy
import math
import os

addon_dir = os.path.dirname(os.path.abspath(__file__))
artifact_dir = "C:/Users/Sebastian/.gemini/antigravity-ide/brain/1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"

# Clear existing objects
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
    bg_node.inputs[0].default_value = (0.2, 0.35, 0.55, 1.0) # Bright daytime sky
    bg_node.inputs[1].default_value = 1.0

# Key Light
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 4.5
light_data.color = (1.0, 0.96, 0.88)
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(48), math.radians(18), math.radians(-35))

# Fill Light
fill_data = bpy.data.lights.new(name="FillSun", type='SUN')
fill_data.energy = 2.0
fill_data.color = (0.6, 0.75, 0.95)
fill_obj = bpy.data.objects.new(name="FillSun", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(35), math.radians(-25), math.radians(145))

# Camera
cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 50
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# 1. RENDER: Log Cabin Corner with Tree Rings and Handcrafted Front Door
bpy.ops.building.create_fantasy_building()
props = scene.fantasy_building_settings
props.material_tier = 'TIER_1'
props.physical_siding = True
props.has_front_door = True
props.door_angle = 35.0
props.has_lanterns = True
props.has_front_steps = True
bpy.ops.building.regenerate()

cam_obj.location = (4.6, -7.2, 3.2)
cam_obj.rotation_euler = (math.radians(72), 0.0, math.radians(32))
scene.render.filepath = os.path.join(artifact_dir, "preview_log_cabin_tree_rings.png")
bpy.ops.render.render(write_still=True)

# 2. RENDER: Front Door Detail (Multi-Plank Leaf, Strap Hinges, Lantern, Frame Clearance)
cam_obj.location = (1.5, -3.8, 1.6)
cam_obj.rotation_euler = (math.radians(82), 0.0, math.radians(20))
scene.render.filepath = os.path.join(artifact_dir, "preview_front_door_detailed.png")
bpy.ops.render.render(write_still=True)

# 3. RENDER: Warehouse Hoist Beam with Forged J-Hook and Pulley
props.material_tier = 'TIER_2'
props.has_hoist_beam = True
bpy.ops.building.regenerate()

cam_obj.location = (1.8, -5.2, 6.2)
cam_obj.rotation_euler = (math.radians(56), 0.0, math.radians(22))
scene.render.filepath = os.path.join(artifact_dir, "preview_hoist_beam_hook.png")
bpy.ops.render.render(write_still=True)

print("Focused renders completed successfully!")
