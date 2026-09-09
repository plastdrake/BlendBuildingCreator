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

# World background / sky
world = bpy.data.worlds.new("StylizedWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.05, 0.07, 0.12, 1.0) # Dusk / twilight fantasy atmosphere
    bg_node.inputs[1].default_value = 0.8

# Key Light
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 3.5
light_data.color = (1.0, 0.92, 0.82)
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-40))

# Fill Light
fill_data = bpy.data.lights.new(name="FillSun", type='SUN')
fill_data.energy = 1.2
fill_data.color = (0.55, 0.70, 0.95)
fill_obj = bpy.data.objects.new(name="FillSun", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(40), math.radians(-30), math.radians(130))

# Camera
cam_data = bpy.data.cameras.new("RenderCam")
cam_data.lens = 45
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# 1. RENDER PREVIEW: Log Cabin with Tree Rings End Material & Handcrafted Door + Lantern
print("Rendering preview: Log cabin with tree rings end material & handcrafted door...")
bpy.ops.building.create_fantasy_building()
bldg = bpy.context.active_object
props = scene.fantasy_building_settings
props.material_tier = 'TIER_1'
props.physical_siding = True
props.has_front_door = True
props.door_angle = 35.0
props.has_lanterns = True
props.has_front_steps = True
bpy.ops.building.regenerate()

cam_obj.location = (2.2, -4.8, 2.2)
cam_obj.rotation_euler = (math.radians(72), 0.0, math.radians(22))
scene.render.filepath = os.path.join(artifact_dir, "preview_log_ends_and_door.png")
bpy.ops.render.render(write_still=True)
print("Saved preview_log_ends_and_door.png")

# 2. RENDER PREVIEW: Warehouse with Hoist Beam & Forged J-Hook
print("Rendering preview: Warehouse hoist beam with curved forged J-hook...")
props.building_archetype = 'WAREHOUSE'
props.has_hoist_beam = True
bpy.ops.building.regenerate()

cam_obj.location = (0.0, -7.0, 6.8)
cam_obj.rotation_euler = (math.radians(64), 0.0, math.radians(0))
scene.render.filepath = os.path.join(artifact_dir, "preview_warehouse_hoist_hook.png")
bpy.ops.render.render(write_still=True)
print("Saved preview_warehouse_hoist_hook.png")

# 3. RENDER PREVIEW: Watchtower Open Fortified Lookout Deck (No Pitched Roof)
print("Rendering preview: Watchtower open fortified lookout deck...")
props.building_archetype = 'WATCHTOWER'
props.num_floors = 3
bpy.ops.building.regenerate()

cam_obj.location = (4.8, -6.5, 9.8)
cam_obj.rotation_euler = (math.radians(65), 0.0, math.radians(35))
scene.render.filepath = os.path.join(artifact_dir, "preview_watchtower_battlement.png")
bpy.ops.render.render(write_still=True)
print("Saved preview_watchtower_battlement.png")

# 4. RENDER PREVIEW: Tavern Veranda with Corner Signboard (No Wall Clipping)
print("Rendering preview: Tavern veranda with hanging trade sign...")
props.building_archetype = 'TAVERN'
props.num_floors = 2
props.material_tier = 'TIER_2'
bpy.ops.building.regenerate()

cam_obj.location = (3.8, -7.2, 2.6)
cam_obj.rotation_euler = (math.radians(75), 0.0, math.radians(28))
scene.render.filepath = os.path.join(artifact_dir, "preview_tavern_veranda_sign.png")
bpy.ops.render.render(write_still=True)
print("Saved preview_tavern_veranda_sign.png")

# 5. RENDER PREVIEW: Wizard Tower Interior Spiral Stair Floor Opening
print("Rendering preview: Wizard tower interior spiral stairs...")
props.building_shape = 'ROUND_TOWER'
props.building_archetype = 'AUTO'
props.num_floors = 2
props.has_stairs = True
props.stair_style = 'SPIRAL'
bpy.ops.building.regenerate()

cam_obj.location = (1.5, -2.4, 3.8)
cam_obj.rotation_euler = (math.radians(55), 0.0, math.radians(30))
scene.render.filepath = os.path.join(artifact_dir, "preview_wizard_tower_stair_opening.png")
bpy.ops.render.render(write_still=True)
print("Saved preview_wizard_tower_stair_opening.png")

print("All verification renders completed successfully!")
