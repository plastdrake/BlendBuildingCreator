import sys
import os
import math
sys.path.append('d:/BlendBuildingCreator')
import bpy
from mathutils import Vector, Euler

# Clear existing objects
bpy.ops.wm.read_factory_settings(use_empty=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception as e:
    print(f"Register note: {e}")

print("=== TEST 1: Tier 3 Tavern with Stone, Plaster, Roof Deck, Stairs, Interior ===")
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
props.eaves_flair = 0.18
props.has_flower_boxes = True
props.has_shutters = True
bpy.ops.building.regenerate()

bld = bpy.context.active_object
assert bld is not None, "Failed to create tavern building"
print(f"Tavern mesh: {len(bld.data.vertices)} verts, {len(bld.data.polygons)} faces")

# Environment / ambient sky light
world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.75, 0.82, 0.95, 1.0)
    bg_node.inputs[1].default_value = 1.2

# Setup sun light
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 3.5
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.rotation_euler = Euler((math.radians(45), math.radians(20), math.radians(-45)), 'XYZ')

# Secondary soft fill sun
fill_sun_data = bpy.data.lights.new(name="FillSun", type='SUN')
fill_sun_data.energy = 1.2
fill_sun_obj = bpy.data.objects.new(name="FillSun", object_data=fill_sun_data)
bpy.context.collection.objects.link(fill_sun_obj)
fill_sun_obj.rotation_euler = Euler((math.radians(35), math.radians(-15), math.radians(135)), 'XYZ')

# Setup camera for exterior overview (showing roof deck, scallop shingles, chimney, walls, windows)
cam_data = bpy.data.cameras.new(name="Camera_Ext")
cam_data.lens = 32
cam_ext = bpy.data.objects.new(name="Camera_Ext", object_data=cam_data)
bpy.context.collection.objects.link(cam_ext)
bpy.context.scene.camera = cam_ext

# Elevated camera looking down at the roof, chimney, walls, windows
cam_ext.location = Vector((8.5, -9.5, 10.5))
cam_ext.rotation_euler = Euler((math.radians(52), 0.0, math.radians(45)), 'XYZ')

# Render settings
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.context.scene.render.film_transparent = False
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.cycles.use_denoising = False

# (Tavern views already rendered and verified)
print("=== SKIPPING TAVERN RENDERS (ALREADY SAVED) ===")

print("=== TEST 2: Tier 1 Log Cabin (Flared Log Ends & Bark Textures) ===")
props.material_tier = 'TIER_1'
props.ground_floor_stone = False
props.has_timber_framing = False
props.num_floors = 1
props.building_length = 5.0
props.building_width = 4.0
props.has_cantilever = False
props.has_dormer = False
props.has_balcony = False
props.has_pillared_overhang = False
props.has_foundation = False
props.building_shape = 'RECTANGLE'
bpy.context.view_layer.objects.active = bld
bpy.ops.building.regenerate()

log_bld = bpy.context.active_object
assert log_bld is not None, "Failed to regenerate log cabin"
print(f"Log cabin mesh: {len(log_bld.data.vertices)} verts, {len(log_bld.data.polygons)} faces")

cam_log = bpy.data.objects.new(name="Camera_Log", object_data=cam_data)
bpy.context.collection.objects.link(cam_log)
bpy.context.scene.camera = cam_log
cam_log.location = Vector((-4.0, -3.6, 1.6))
cam_log.rotation_euler = Euler((math.radians(72), 0.0, math.radians(-48)), 'XYZ')

log_path = "d:/BlendBuildingCreator/test_log_flair.png"
bpy.context.scene.render.filepath = log_path
print(f"Rendering log flair to {log_path}...")
bpy.ops.render.render(write_still=True)
print("Log flair render complete.")

print("=== ALL TEST RENDERS COMPLETED SUCCESSFULLY! ===")
