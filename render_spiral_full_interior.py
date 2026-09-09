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

# Lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 2.5
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(35))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.8, 0.85, 0.9, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

# Create Wizard Tower (3 floors, spiral stairs)
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.width = 5.0
props.depth = 5.0
props.num_floors = 3
props.stair_style = 'SPIRAL'
bpy.ops.building.regenerate()

# Interior light
light_data = bpy.data.lights.new(name="InteriorPoint", type='POINT')
light_data.energy = 200.0
light_data.color = (1.0, 0.95, 0.88)
light_obj = bpy.data.objects.new(name="InteriorPoint", object_data=light_data)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.location = (0.5, -0.5, 4.0)

# Camera looking at spiral stairs on Floor 1 & Floor 2
cam_data = bpy.data.cameras.new(name="CamInterior")
cam_data.lens = 22
cam_obj = bpy.data.objects.new(name="CamInterior", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = Vector((1.4, -1.4, 4.5))
direction = (Vector((-1.2, 1.0, 3.8)) - cam_obj.location).normalized()
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

out_path = os.path.join(addon_dir, "preview_spiral_full_interior.png")
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("RENDERED: preview_spiral_full_interior.png")
