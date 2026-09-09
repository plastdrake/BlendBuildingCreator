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

# Interior point light
int_light = bpy.data.lights.new(name="IntLight", type='POINT')
int_light.energy = 200.0
int_light.color = (1.0, 0.92, 0.82)
int_light_obj = bpy.data.objects.new(name="IntLight", object_data=int_light)
bpy.context.scene.collection.objects.link(int_light_obj)
int_light_obj.location = (0.0, 0.0, 3.5)

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 24
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

# 1. Roof view (bargeboard angle and shingle layers)
props.num_floors = 2
props.has_roof_shingles = True
props.roof_style = 'SWAY'
bpy.ops.building.regenerate()

render_camera_at("CamRoof", (-4.2, -4.5, 6.5), (-1.5, -1.0, 5.2), "preview_roof_shingles_clean.png")

# 2. Straight stairs interior view: dual-sided railings & L-shaped return railing
props.stair_style = 'STRAIGHT'
bpy.ops.building.regenerate()

# Position fill light right next to the stairs
stair_fill = bpy.data.lights.new(name="StairFill", type='POINT')
stair_fill.energy = 500.0
stair_fill.color = (1.0, 0.95, 0.90)
stair_fill_obj = bpy.data.objects.new(name="StairFill", object_data=stair_fill)
bpy.context.scene.collection.objects.link(stair_fill_obj)
stair_fill_obj.location = (-0.8, 0.0, 2.2)

# Position camera inside looking clearly at straight staircase with dual railings
render_camera_at("CamStraightStairs", (1.0, -1.0, 2.6), (-2.0, 0.5, 2.0), "preview_dual_railings.png")

# 3. Spiral stairs 3 floors view: smooth progression & landing alignment
props.stair_style = 'SPIRAL'
props.num_floors = 3
bpy.ops.building.regenerate()

fl0_ix_min = -props.width * 0.5 + 0.28 * 0.5
fl0_iy_max = props.depth * 0.5 - 0.28 * 0.5
spiral_r = min(1.15, props.stair_width * 1.05)
spiral_cx = fl0_ix_min + spiral_r + 0.15
spiral_cy = fl0_iy_max - spiral_r - 0.15

render_camera_at("CamSpiralMulti", (spiral_cx + 1.4, spiral_cy - 1.4, 4.0), (spiral_cx, spiral_cy, 2.9), "preview_spiral_multi_aligned.png")

print("ALL ROUND 4 VERIFICATION VIEWS COMPLETED!", flush=True)
