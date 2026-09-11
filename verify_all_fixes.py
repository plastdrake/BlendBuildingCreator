import sys
import os
sys.path.append('d:/BlendBuildingCreator')
import bpy

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

print("=== TEST 1: Default Fantasy Building ===")
res = bpy.ops.building.create_fantasy_building()
assert res == {'FINISHED'}, f"Failed to create building: {res}"
obj = bpy.context.active_object
print(f"Building created with {len(obj.data.vertices)} verts and {len(obj.data.polygons)} faces.")

print("=== TEST 2: Tavern Preset with Cantilever, Mini-Wing, Balcony & Pillared Overhang ===")
bpy.ops.building.apply_preset(preset_key="TAVERN")
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
bpy.ops.building.regenerate()

obj = bpy.context.active_object
print(f"Regenerated building with all features: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces.")
print("ALL TESTS PASSED SUCCESSFULLY!")
