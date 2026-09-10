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

# Lighting setup
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(45))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.75, 0.8, 0.9, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings - EEVEE
try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    try:
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    except Exception:
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.device = 'CPU'
        bpy.context.scene.cycles.samples = 16

bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 28
    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(loc)
    direction = (Vector(target) - cam_obj.location).normalized()
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    
    out_path = os.path.join(addon_dir, out_name)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED: {out_name}", flush=True)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

# Create building
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.num_floors = 2
props.ground_floor_stone = True
props.door_angle = 45.0
props.door_shape = 'AUTO'
props.has_balcony = True
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.has_dormers = True
props.has_roof_shingles = True
bpy.ops.building.regenerate()

# 1. Front Arched Door view
render_camera_at("CamFrontDoor", (0.0, -5.5, 2.0), (0.0, -2.5, 1.8), "verif_front_door.png")

# 2. Balcony Door top view
render_camera_at("CamBalconyDoor", (0.0, -3.8, 5.2), (0.0, -2.5, 3.8), "verif_balcony_door.png")

# 3. Mini-Wing wall junction view
render_camera_at("CamMiniWing", (-5.6, -2.4, 2.5), (-4.1, -0.2, 1.9), "verif_mini_wing.png")

# 4. Dormer Roof rear view (wide angle showing junction with main roof)
render_camera_at("CamDormerRoof", (1.2, 2.5, 10.5), (-1.8, 0.9, 7.2), "verif_dormer_roof.png")

print("ALL VERIFICATION RENDERS COMPLETE!", flush=True)
