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

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 20
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 26
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

# Create building
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings

# 1. Facade view (Screenshot 2 comparison: diagonal braces & angled shutters)
props.num_floors = 2
props.has_cantilever = True
props.overhang_mode = 'SECOND_FLOOR_ONLY'
props.has_shutters = True
props.timber_diagonals = True
bpy.ops.building.regenerate()

render_camera_at("CamFacade", (0.5, -6.5, 3.2), (0.0, -2.5, 2.8), "preview_diagonal_shutters.png")

# 2. Roof eave corner view (Screenshot 3 comparison: solid 12cm thick timber deck & sealed wall/roof)
render_camera_at("CamRoofCorner", (-3.6, -3.8, 6.2), (-2.8, -2.2, 5.8), "preview_roof_corner_sealed.png")

# 3. Spiral stairs upper floor view (Screenshot 1 comparison: landing, alignment, solid guardrail)
props.stair_style = 'SPIRAL'
props.num_floors = 3
bpy.ops.building.regenerate()

# Interior light for stairwell
stair_light = bpy.data.lights.new(name="StairLight", type='POINT')
stair_light.energy = 150.0
stair_light.color = (1.0, 0.95, 0.85)
stair_light_obj = bpy.data.objects.new(name="StairLight", object_data=stair_light)
bpy.context.scene.collection.objects.link(stair_light_obj)
stair_light_obj.location = (-0.5, 0.5, 4.5)

# Camera looking down into spiral stairwell from upper floor (similar to Screenshot 1)
# Center of spiral stairs is in the back-left corner
spiral_r = min(1.15, props.stair_width * 1.05)
fl0_ix_min = -props.width * 0.5 + 0.28 * 0.5
fl0_iy_max = props.depth * 0.5 - 0.28 * 0.5
spiral_cx = fl0_ix_min + spiral_r + 0.15
spiral_cy = fl0_iy_max - spiral_r - 0.15

render_camera_at("CamSpiralWell", (spiral_cx + 1.2, spiral_cy - 1.2, 4.2), (spiral_cx, spiral_cy, 3.1), "preview_spiral_aligned.png")

print("ROUND 3 VERIFICATION VIEWS COMPLETED!")
