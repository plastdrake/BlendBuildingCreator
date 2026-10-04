"""Crown top-down: orrery center + bridge-door clearance."""
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
apply_preset(props, 'MAGE_TOWER_T2')
props.has_interior_furnishing = True
bpy.ops.building.create_fantasy_building()

pt_data = bpy.data.lights.new(name="FillLight", type='POINT')
pt_data.energy = 2500.0
pt_obj = bpy.data.objects.new(name="FillLight", object_data=pt_data)
bpy.context.scene.collection.objects.link(pt_obj)
pt_obj.location = (0.0, 0.0, 26.0)

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

cam_data = bpy.data.cameras.new(name="CrownTopCam")
cam_data.lens = 16
cam_obj = bpy.data.objects.new(name="CrownTopCam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

for name, yaw in (("crown_top0.png", 0), ("crown_top180.png", 180)):
    cam_obj.location = (0.0, 0.0, 28.2)
    cam_obj.rotation_euler = (math.radians(42), 0, math.radians(yaw))
    bpy.context.scene.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)
    print("Rendered", name)
