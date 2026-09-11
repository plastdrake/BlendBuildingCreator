import sys
import os
import math
sys.path.append('d:/BlendBuildingCreator')
import bpy
from mathutils import Vector, Euler

# Clean scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

# Create building with all features enabled to inspect
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.has_cantilever = True
props.cantilever_overhang = 0.35
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.has_balcony = True
props.balcony_side = 'FRONT'
props.balcony_floor = 2
props.has_pillared_overhang = True
props.pillared_overhang_side = 'FRONT'
props.ground_floor_stone = True
bpy.ops.building.regenerate()

obj = bpy.context.active_object
print(f"Mesh generated: {len(obj.data.vertices)} vertices, {len(obj.data.polygons)} polygons")

# Inspect Issue 1: Overhang corbel positions vs wall beam
print("=== Issue 1: Overhang Corbels ===")
from blend_building_creator.generator import walls
print(f"build_cantilever_corbels drop parameter default: {walls.build_cantilever_corbels.__defaults__}")

# Inspect Issue 2: Mini-wing header beam
print("=== Issue 2: Mini-wing Header Beam ===")
# Check where loc_fhead is in accessories.py

# Inspect Issue 3: Mini-wing Roof Shingles
print("=== Issue 3: Mini-wing Roof Shingles ===")

# Inspect Issue 4: Pillared overhang ceiling material
print("=== Issue 4: Pillared Overhang Ceiling ===")

# Inspect Issue 5: Balcony bracket position
print("=== Issue 5: Balcony Bracket ===")

print("Inspection completed.")
