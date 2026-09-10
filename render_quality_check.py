"""Higher quality single exterior render for style assessment."""
import os
import bpy
import math

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

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.num_floors = 2
props.has_cantilever = True
props.has_dormers = True
props.has_chimney = True
bpy.ops.building.regenerate()

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.2
sun_data.color = (1.0, 0.93, 0.85)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.62, 0.74, 0.86, 1.0)
    bg_node.inputs["Strength"].default_value = 1.1

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 850

cam_data = bpy.data.cameras.new(name="Cam")
cam_data.lens = 32
cam_obj = bpy.data.objects.new(name="Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (8.5, -10.0, 5.5)
import mathutils
direction = mathutils.Vector((0, 0, 2.6)) - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam_obj

scene.render.filepath = os.path.join(script_dir, "preview_quality.png")
bpy.ops.render.render(write_still=True)
print("DONE_QUALITY_RENDER")
