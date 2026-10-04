"""Phase-4 verification: witch-hat continuous shingle courses (T1 spire)."""
import bpy
import math
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.presets import apply_preset

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings
apply_preset(props, 'MAGE_TOWER_T1')
props.has_interior_furnishing = True
bpy.ops.building.create_fantasy_building()
obj = bpy.context.active_object
print(f"T1 spire check: verts={len(obj.data.vertices)} dims=({obj.dimensions.x:.1f}, "
      f"{obj.dimensions.y:.1f}, {obj.dimensions.z:.1f})")

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

cam_data = bpy.data.cameras.new(name="SpireCam")
cam_data.lens = 55
cam_obj = bpy.data.objects.new(name="SpireCam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

top_z = obj.dimensions.z
# Shot 1: mid-bell courses
cam_obj.location = (0.0, -16.0, top_z * 0.72)
cam_obj.rotation_euler = (math.radians(68), 0, 0)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase4_spire_bell.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase4_spire_bell.png")

# Shot 2: needle tip courses
cam_obj.location = (0.0, -9.0, top_z * 0.94)
cam_obj.rotation_euler = (math.radians(72), 0, 0)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase4_spire_tip.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase4_spire_tip.png")
