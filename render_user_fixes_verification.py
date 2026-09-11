import sys
import os
import math
sys.path.append('d:/BlendBuildingCreator')
import bpy
from mathutils import Vector, Euler

bpy.ops.wm.read_factory_settings(use_empty=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception as e:
    print(f"Register note: {e}")

print("=== Generating Tavern for Visual Verification ===")
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="TAVERN")
props = bpy.context.scene.fantasy_building_settings
props.building_tier = 'TIER_3'
props.has_dormer = True
props.has_chimney = True
props.has_mini_wing = False
props.has_cantilever = True
props.cantilever_overhang = 0.35
props.roof_overhang = 0.50
props.has_flower_boxes = True
props.has_shutters = True
props.has_front_steps = True
props.has_foundation = True
props.door_shape = 'AUTO'
props.door_angle = 35.0
bpy.ops.building.regenerate()

bld = bpy.context.active_object
print(f"Building created: {len(bld.data.vertices)} verts, {len(bld.data.polygons)} faces")

# Setup lighting
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.84, 0.88, 0.94, 1.0)
    bg.inputs[1].default_value = 1.35

sun = bpy.data.lights.new("Sun", 'SUN')
sun.energy = 4.2
sun_obj = bpy.data.objects.new("Sun", sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = Euler((math.radians(52), math.radians(18), math.radians(-32)), 'XYZ')

fill = bpy.data.lights.new("Fill", 'SUN')
fill.energy = 1.6
fill_obj = bpy.data.objects.new("Fill", fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.rotation_euler = Euler((math.radians(35), math.radians(-20), math.radians(150)), 'XYZ')

# Warm interior light for staircase illumination
lamp_data = bpy.data.lights.new("InteriorLight", 'POINT')
lamp_data.energy = 300.0
lamp_data.color = (1.0, 0.92, 0.78)
lamp_obj = bpy.data.objects.new("InteriorLight", lamp_data)
bpy.context.collection.objects.link(lamp_obj)

# Camera setup
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 45
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 28
bpy.context.scene.cycles.use_denoising = False

out_dir = "C:/Users/Sebastian/.gemini/antigravity-ide/brain/5253d860-4647-4fa6-8b89-b37eba0335b5"

# 1. Floor Tiling view: looking down at the ground floor interior floorboards
floor_coords = [v.co for f in bld.data.polygons if f.material_index == 4 for v in bld.data.vertices if v.index in f.vertices and v.co.z < 1.0]
if floor_coords:
    import numpy as np
    pts = np.array(floor_coords)
    f_center = pts.mean(axis=0)
else:
    f_center = np.array([0.0, 0.0, 0.0])

lamp_obj.location = Vector((f_center[0], f_center[1], f_center[2] + 2.5))
cam.location = Vector((f_center[0] - 1.2, f_center[1] - 1.8, f_center[2] + 2.2))
cam.rotation_euler = Euler((math.radians(52), 0.0, math.radians(-35)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_floor_seamless.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_floor_seamless.png")

# 2. Roof overview & dormer view
roof_coords = [v.co for f in bld.data.polygons if f.material_index == 5 for v in bld.data.vertices if v.index in f.vertices]
if roof_coords:
    import numpy as np
    r_pts = np.array(roof_coords)
    r_center = r_pts.mean(axis=0)
else:
    r_center = np.array([0.0, 0.0, 5.5])

cam.location = Vector((r_center[0] + 3.8, r_center[1] - 6.2, r_center[2] + 4.5))
cam.rotation_euler = Euler((math.radians(60), 0.0, math.radians(28)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_roof_shingles.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_roof_shingles.png")

# 3. Front door steps & stone door frame
door_coords = [v.co for f in bld.data.polygons if f.material_index == 7 for v in bld.data.vertices if v.index in f.vertices]
if door_coords:
    import numpy as np
    d_pts = np.array(door_coords)
    d_center = d_pts.mean(axis=0)
else:
    d_center = np.array([-2.0, -3.2, 1.5])

cam.location = Vector((d_center[0] + 0.8, d_center[1] - 2.8, d_center[2] - 0.4))
cam.rotation_euler = Euler((math.radians(80), 0.0, math.radians(20)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_door_steps_cutstone.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_door_steps_cutstone.png")

# 4. Interior stairs side stringer and tread closeup
stair_coords = [v.co for f in bld.data.polygons if f.material_index == 12 for v in bld.data.vertices if v.index in f.vertices]
if stair_coords:
    import numpy as np
    s_pts = np.array(stair_coords)
    s_center = s_pts.mean(axis=0)
else:
    s_center = np.array([1.5, 0.5, 1.5])

lamp_obj.location = Vector((s_center[0], s_center[1], s_center[2] + 1.5))
# Side stringer diagonal view
cam.location = Vector((s_center[0] - 2.2, s_center[1] - 0.4, s_center[2] + 0.2))
cam.rotation_euler = Euler((math.radians(82), 0.0, math.radians(-80)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_stairs_stringer_side.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_stairs_stringer_side.png")

# 5. Stair tread top surface closeup
cam.location = Vector((s_center[0] - 0.6, s_center[1] - 0.9, s_center[2] + 0.7))
cam.rotation_euler = Euler((math.radians(55), 0.0, math.radians(-30)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_stairs_tread_closeup.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_stairs_tread_closeup.png")

# 6. Exterior Facade wood planks vs Timber Frame (Tier 2 building)
bpy.ops.building.apply_preset(preset_key="FARMHOUSE")
props = bpy.context.scene.fantasy_building_settings
props.building_tier = 'TIER_2'
props.physical_siding = True
props.plank_direction = 'HORIZONTAL'
bpy.ops.building.regenerate()
bld = bpy.context.active_object

bld_center = Vector((0.0, 0.0, 2.5))
cam.location = Vector((bld_center.x + 5.5, bld_center.y - 6.5, bld_center.z + 2.0))
cam.rotation_euler = Euler((math.radians(72), 0.0, math.radians(40)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "verify_facade_wood_planks.png")
bpy.ops.render.render(write_still=True)
print("Rendered: verify_facade_wood_planks.png")

print("=== All verification renders completed successfully ===")
