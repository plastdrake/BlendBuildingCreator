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

# Register addon
blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings
apply_preset(props, 'MAGE_TOWER_T2')
props.has_interior_furnishing = True
bpy.ops.building.create_fantasy_building()

obj = bpy.context.active_object
print(f"Generated Mage Tower T2 with {len(obj.data.vertices)} vertices.")

# Setup sun lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 4.0
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

# Interior fill light
point_data = bpy.data.lights.new(name="InteriorLight", type='POINT')
point_data.energy = 2500.0
point_data.color = (1.0, 0.90, 0.75)
point_obj = bpy.data.objects.new(name="InteriorLight", object_data=point_data)
bpy.context.scene.collection.objects.link(point_obj)

cam_data = bpy.data.cameras.new(name="MageCamera")
cam_data.lens = 22
cam_obj = bpy.data.objects.new(name="MageCamera", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

# Shot 1: Exterior of Mage Tower T2 showing the soaring pointy witch-hat roof and whimsical outcrops
cam_obj.location = (0.0, -32.0, 24.0)
cam_obj.rotation_euler = (math.radians(65), 0, 0)
cam_data.lens = 28
bpy.context.scene.render.filepath = os.path.join(out_dir, "update_tower_t2_exterior.png")
bpy.ops.render.render(write_still=True)
print("Rendered T2 exterior.")

# Shot 2: Close-up of the soaring pointy witch-hat spire
cam_obj.location = (0.0, -18.0, 36.0)
cam_obj.rotation_euler = (math.radians(68), 0, 0)
cam_data.lens = 32
bpy.context.scene.render.filepath = os.path.join(out_dir, "update_roof_spire_closeup.png")
bpy.ops.render.render(write_still=True)
print("Rendered roof spire closeup.")

# Shot 3: Library Floor interior showing scrying pool with hollow basin and levitating crystal + armchairs
cam_data.lens = 18
cam_obj.location = (0.0, -5.2, 8.2)
cam_obj.rotation_euler = (math.radians(68), 0, 0)
point_obj.location = (0.0, 0.0, 9.5)
bpy.context.scene.render.filepath = os.path.join(out_dir, "update_scrying_pool_interior.png")
bpy.ops.render.render(write_still=True)
print("Rendered scrying pool interior.")
