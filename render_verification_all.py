import os
import sys
import math
import bpy
from mathutils import Vector

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

# Setup Lighting
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
    bg_node.inputs["Color"].default_value = (0.7, 0.75, 0.85, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Fill light
fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
fill_data.energy = 2.0
fill_data.color = (0.9, 0.95, 1.0)
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(35), math.radians(-30), math.radians(-60))

# Render settings - Ultra-fast preview mode
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 2
bpy.context.scene.cycles.max_bounces = 1
bpy.context.scene.cycles.diffuse_bounces = 1
bpy.context.scene.cycles.glossy_bounces = 0
bpy.context.scene.cycles.transparent_max_bounces = 1
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 720
bpy.context.scene.render.resolution_y = 540

def render_view(name, loc, target, filename):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 28
    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(loc)
    direction = (Vector(target) - cam_obj.location).normalized()
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    
    out_path = os.path.join(script_dir, filename)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED: {filename}", flush=True)

# Build 1: Building with Cantilever corbels, Mini-wing, and Balcony
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="TAVERN")
props = bpy.context.scene.fantasy_building_settings
props.building_archetype = 'NONE'
props.has_cantilever = True
props.cantilever_overhang = 0.35
props.has_pillared_overhang = False
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.has_balcony = True
props.balcony_side = 'FRONT'
props.balcony_floor = 2
props.ground_floor_stone = True
props.door_angle = 45.0
bpy.ops.building.regenerate()

# View 1: Overhang corbels touching beam and wall below (Screenshot 1)
render_view("CamCorbels", (2.8, -4.8, 1.8), (0.5, -2.8, 2.7), "preview_corbels_contact.png")

# View 2: Outcrop building roof with 3D physical shingles and flush header beam (Screenshots 2 & 3)
render_view("CamOutcrop", (-7.2, -2.8, 4.2), (-4.2, 0.0, 2.4), "preview_outcrop_shingles.png")

# View 3: Balcony support corbel touching wall (Screenshot 5)
render_view("CamBalcony", (-3.2, -5.8, 2.6), (-0.98, -3.4, 3.2), "preview_balcony_support.png")

# View 4: Wing floor junction covered by chunky belt beam (Screenshot 6)
render_view("CamWingBelt", (0.0, -8.5, 3.2), (0.0, 0.0, 2.8), "preview_wing_chunky_beams.png")

# Build 2: With Pillared Overhang to verify Issue 4 (exterior material ceiling cover)
props.has_pillared_overhang = True
props.pillared_overhang_side = 'FRONT'
bpy.ops.building.regenerate()

# View 5: Overhang ceiling covered by exterior stucco material (Screenshot 4)
render_view("CamCeiling", (-1.2, -5.2, 0.9), (0.0, -3.2, 2.7), "preview_overhang_ceiling.png")

print("ALL RENDERS COMPLETED SUCCESSFULLY!", flush=True)
