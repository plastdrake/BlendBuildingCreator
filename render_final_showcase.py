import os
import sys
import math
import bpy
from mathutils import Vector

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

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 4.5
sun_data.color = (1.0, 0.98, 0.94)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(-30))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
try:
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.85, 0.88, 0.94, 1.0)
        bg_node.inputs["Strength"].default_value = 1.2
except Exception:
    pass

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 14
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720

def render_camera_at(name, loc, target, out_name, lens=32):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = lens
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
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings

# 1. Arched Doorway Close-up (closed door with snug arch radius, stone voussoirs, spandrel masonry)
props.num_floors = 1
props.material_tier = 'TIER_3'
props.door_style = 'ARCHED'
props.door_open_angle = 0.0
props.has_roof_turret = False
props.has_dormers = False
bpy.ops.building.regenerate()

render_camera_at("CamArchDoor", (0.0, -6.5, 1.6), (0.0, -2.5, 1.5), "preview_arched_door_fit.png", lens=28)

# 2. Roof Turret & Dormer Close-up
props.num_floors = 2
props.material_tier = 'TIER_2'
props.roof_style = 'SWAY'
props.roof_flare = 0.35
props.has_dormers = True
props.has_roof_turret = True
props.roof_turret_style = 'OCTAGONAL'
bpy.ops.building.regenerate()

render_camera_at("CamTurretDormer", (5.0, -6.5, 7.8), (0.0, 0.0, 7.2), "preview_roof_turret_spire_closeup.png", lens=35)

print("ALL SHOWCASE RENDERS COMPLETE.")
