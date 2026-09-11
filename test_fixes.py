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
    bg.inputs[0].default_value = (0.82, 0.86, 0.92, 1.0)
    bg.inputs[1].default_value = 1.3

sun = bpy.data.lights.new("Sun", 'SUN')
sun.energy = 4.0
sun_obj = bpy.data.objects.new("Sun", sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = Euler((math.radians(50), math.radians(15), math.radians(-30)), 'XYZ')

fill = bpy.data.lights.new("Fill", 'SUN')
fill.energy = 1.5
fill_obj = bpy.data.objects.new("Fill", fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.rotation_euler = Euler((math.radians(35), math.radians(-20), math.radians(150)), 'XYZ')

# Warm interior light for staircase illumination
lamp_data = bpy.data.lights.new("InteriorLight", 'POINT')
lamp_data.energy = 250.0
lamp_data.color = (1.0, 0.92, 0.78)
lamp_obj = bpy.data.objects.new("InteriorLight", lamp_data)
bpy.context.collection.objects.link(lamp_obj)

# Find door center coordinates from door vertices
door_coords = [v.co for f in bld.data.polygons if f.material_index == 7 for v in bld.data.vertices if v.index in f.vertices]
if door_coords:
    import numpy as np
    d_pts = np.array(door_coords)
    door_center = d_pts.mean(axis=0)
    print("Detected door center at:", door_center)
else:
    door_center = np.array([-2.0, -3.2, 1.5])

# Find stair center coordinates from stairs vertices
stair_coords = [v.co for f in bld.data.polygons if f.material_index == 12 for v in bld.data.vertices if v.index in f.vertices]
if stair_coords:
    import numpy as np
    s_pts = np.array(stair_coords)
    stair_center = s_pts.mean(axis=0)
    print("Detected stair center at:", stair_center)
    lamp_obj.location = Vector((stair_center[0], stair_center[1], stair_center[2] + 1.2))
else:
    stair_center = np.array([1.5, 0.5, 1.5])
    lamp_obj.location = Vector((1.5, 0.5, 2.5))

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 40
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 28
bpy.context.scene.cycles.use_denoising = False

out_dir = "C:/Users/Sebastian/.gemini/antigravity-ide/brain/5253d860-4647-4fa6-8b89-b37eba0335b5"

# 1. Door & Front Steps Closeup
dcx, dcy, dcz = door_center
cam.location = Vector((dcx, dcy - 2.6, dcz + 0.1))
cam.rotation_euler = Euler((math.radians(84), 0.0, math.radians(0)), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "test_door_steps_cutstone.png")
bpy.ops.render.render(write_still=True)
print("Rendered: test_door_steps_cutstone.png")

# 2. Interior Stairs Closeup (Standing at foot of stairs looking up steps, like user Image 1)
scx, scy, scz = stair_center
lamp_obj.location = Vector((scx, scy + 0.2, 1.8))
lamp_obj.data.energy = 800.0
cam_data.lens = 32
# Foot of stairs is at Y_min (-0.92), looking along +Y up the flight
cam.location = Vector((scx, -0.6, 1.35))
cam.rotation_euler = Euler((math.radians(55), 0.0, 0.0), 'XYZ')
bpy.context.scene.render.filepath = os.path.join(out_dir, "test_interior_stairs.png")
bpy.ops.render.render(write_still=True)
print("Rendered: test_interior_stairs.png")

print("=== VERIFICATION RENDERS COMPLETE ===")
