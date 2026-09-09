"""
Render verification views for:
1. Gable wall sealed under roof deck + elevated shingles (preview_gable_wall_sealed.png)
2. Straight stair balusters flush on treads with zero underside protrusion + floor bridging exterior wall (preview_stair_balusters_flush.png)
3. Compound L-Shape building with courtyard and cross-gable roof (preview_compound_l_shape.png)
4. Dynamic window scaling on wide facade (preview_dynamic_windows_wide.png)
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

# Sun light
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.2
sun_data.color = (1.0, 0.97, 0.92)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

# Interior light
int_data = bpy.data.lights.new(name="IntLight", type='POINT')
int_data.energy = 150.0
int_data.color = (1.0, 0.92, 0.82)
int_obj = bpy.data.objects.new(name="IntLight", object_data=int_data)
bpy.context.scene.collection.objects.link(int_obj)
int_obj.location = (0.0, 0.0, 4.0)

# World
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.75, 0.80, 0.88, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings (Cycles CPU, fast sample count for clean preview)
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 20
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720

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
    print(f"RENDERED: {out_name}")
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

# Create building
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings

# 1. GABLE WALL SEALED + ELEVATED SHINGLES
props.num_floors = 2
props.roof_style = 'SWAY'
props.roof_height = 2.8
props.has_roof_shingles = True
props.has_cantilever = True
props.building_shape = 'RECTANGLE'
bpy.ops.building.regenerate()

# View looking directly at the front gable wall, roof verge, bargeboards and eaves
render_camera_at("CamGable", (0.0, -8.5, 7.5), (0.0, -3.2, 7.2), "preview_gable_wall_sealed.png")

# 2. STAIR BALUSTERS FLUSH + EXT WALL TOP BRIDGED WITH FLOOR
props.num_floors = 2
props.has_stairs = True
props.stair_style = 'STRAIGHT'
bpy.ops.building.regenerate()

# Position camera inside ground floor looking at the straight staircase underside & railing
render_camera_at("CamStairs", (-0.5, -0.8, 1.6), (-2.2, 0.4, 2.2), "preview_stair_balusters_flush.png")

# 3. COMPOUND L-SHAPE BUILDING
props.building_shape = 'L_SHAPE'
props.wing_side = 'RIGHT'
props.wing_width = 3.2
props.wing_depth = 3.0
props.num_floors = 2
props.has_windows = True
props.has_front_door = True
bpy.ops.building.regenerate()

# Perspective overview showing the L-shape courtyard, cross-gable roof, entrance, and dynamic windows
render_camera_at("CamLShape", (-8.5, -9.5, 6.5), (0.5, -1.0, 3.5), "preview_compound_l_shape.png")

# 4. DYNAMIC WINDOWS SCALING ON WIDE FACADE
props.building_shape = 'RECTANGLE'
props.width = 9.5
props.depth = 6.0
props.num_floors = 2
bpy.ops.building.regenerate()

# Front facade view showing multiple dynamic windows distributed along the wide facade
render_camera_at("CamWideWindows", (0.0, -11.0, 4.0), (0.0, 0.0, 3.5), "preview_dynamic_windows_wide.png")

print("ALL VERIFICATION RENDERS COMPLETE!")
