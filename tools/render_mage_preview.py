import bpy
import math
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.presets import apply_preset

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Enable add-on and create building
blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings
apply_preset(props, 'MAGE_TOWER_T1')
props.has_interior_furnishing = True
bpy.ops.building.create_fantasy_building()

obj = bpy.context.active_object
print(f"Generated Mage Tower with {len(obj.data.vertices)} vertices.")

# Setup lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

# Interior fill point light
point_data = bpy.data.lights.new(name="InteriorLight", type='POINT')
point_data.energy = 1500.0
point_data.color = (1.0, 0.88, 0.72)
point_obj = bpy.data.objects.new(name="InteriorLight", object_data=point_data)
bpy.context.scene.collection.objects.link(point_obj)
point_obj.location = (0.0, 0.0, 3.2)

# Camera looking across the ground floor interior at the grand bookcases, alchemy station, and ritual cauldron
cam_data = bpy.data.cameras.new(name="MageCamera")
cam_data.lens = 18
cam_obj = bpy.data.objects.new(name="MageCamera", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (0.0, -7.5, 2.2)
cam_obj.rotation_euler = (math.radians(82), 0, 0)
bpy.context.scene.camera = cam_obj

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 540

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

# 1. Ground floor render
out_path_ground = os.path.join(out_dir, "mage_tower_ground_preview.png")
bpy.context.scene.render.filepath = out_path_ground
bpy.ops.render.render(write_still=True)
print(f"[SUCCESS] Rendered Mage Tower ground floor to {out_path_ground}")

# 2. Library Floor Camera (Floor 1: z ~ 6.04)
cam_obj.location = (0.0, -7.0, 7.8)
cam_obj.rotation_euler = (math.radians(78), 0, 0)
point_obj.location = (0.0, 0.0, 8.5)
out_path_lib = os.path.join(out_dir, "mage_tower_library_preview.png")
bpy.context.scene.render.filepath = out_path_lib
bpy.ops.render.render(write_still=True)
print(f"[SUCCESS] Rendered Mage Tower library floor to {out_path_lib}")

# 3. Observatory Camera (Top floor: z ~ 11.44)
cam_obj.location = (0.0, -8.0, 13.0)
cam_obj.rotation_euler = (math.radians(78), 0, 0)
point_obj.location = (0.0, 0.0, 14.5)
out_path_obs = os.path.join(out_dir, "mage_tower_observatory_preview.png")
bpy.context.scene.render.filepath = out_path_obs
bpy.ops.render.render(write_still=True)
print(f"[SUCCESS] Rendered Mage Tower observatory to {out_path_obs}")

