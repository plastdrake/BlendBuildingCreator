"""
Renders 3 images corresponding to the user's 3 viewpoints:
1. upper_stair_opening.png (matching Screenshot 1)
2. ground_stair_view.png (matching Screenshot 2)
3. front_door_view.png (matching Screenshot 3)
"""

import os
import sys
import math
import bpy
from mathutils import Vector

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

# Create Tavern building
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="TAVERN")
props = bpy.context.scene.fantasy_building_settings
props.door_angle = 45.0
bpy.ops.building.regenerate()

# Lighting setup
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(45))

# Ambient world light
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.7, 0.75, 0.85, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Interior point light on ground floor
light_data = bpy.data.lights.new(name="IntLight0", type='POINT')
light_data.energy = 120.0
light_data.color = (1.0, 0.88, 0.70)
light_obj = bpy.data.objects.new(name="IntLight0", object_data=light_data)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.location = (0.0, 0.0, 2.0)

# Interior point light on upper floor
light_data1 = bpy.data.lights.new(name="IntLight1", type='POINT')
light_data1.energy = 100.0
light_data1.color = (1.0, 0.90, 0.75)
light_obj1 = bpy.data.objects.new(name="IntLight1", object_data=light_data1)
bpy.context.scene.collection.objects.link(light_obj1)
light_obj1.location = (0.0, 0.0, 4.5)

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

# Function to render a view with target tracking
def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 22
    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(loc)
    direction = (Vector(target) - cam_obj.location).normalized()
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    
    out_path = os.path.join(addon_dir, out_name)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED: {out_name}")

# View 1: Upper stair opening (standing on Floor 1 looking down at stair opening, railing, and landing)
render_camera_at("CamUpperStair", (-0.8, -0.2, 4.8), (-2.5, 1.0, 3.4), "preview_upper_stair.png")

# View 2: Ground stair view (standing on ground floor looking up the flight of stairs toward ceiling)
render_camera_at("CamGroundStair", (0.2, -1.5, 1.2), (-2.5, 0.4, 2.2), "preview_ground_stair.png")

# View 3: Front door and window facade (looking straight at front door from outside)
render_camera("CamFrontDoor", (0.5, -4.8, 1.4), (math.radians(88), 0, math.radians(0)), "preview_front_door.png")

print("ALL PREVIEWS FINISHED!")
