"""Phase-2 verification: enlarged T1/T2 footprints + de-overlapped furnishing."""
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

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

pt_data = bpy.data.lights.new(name="FillLight", type='POINT')
pt_data.energy = 1500.0
pt_data.color = (1.0, 0.90, 0.75)
pt_obj = bpy.data.objects.new(name="FillLight", object_data=pt_data)
bpy.context.scene.collection.objects.link(pt_obj)

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

cam_data = bpy.data.cameras.new(name="Phase2Cam")
cam_data.lens = 20
cam_obj = bpy.data.objects.new(name="Phase2Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj


def shoot(name, cam_xy, cam_z, yaw_deg, fill_xy, fill_z):
    cam_obj.location = (cam_xy[0], cam_xy[1], cam_z)
    cam_obj.rotation_euler = (math.radians(80), 0, math.radians(yaw_deg))
    pt_obj.location = (fill_xy[0], fill_xy[1], fill_z)
    bpy.context.scene.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)
    print("Rendered", name)


def build(preset):
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.name.startswith("Fantasy"):
            bpy.data.objects.remove(obj, do_unlink=True)
    apply_preset(props, preset)
    props.has_interior_furnishing = True
    bpy.ops.building.create_fantasy_building()
    obj = bpy.context.active_object
    print(f"{preset}: verts={len(obj.data.vertices)} dims=({obj.dimensions.x:.1f}, "
          f"{obj.dimensions.y:.1f}, {obj.dimensions.z:.1f})")
    return obj


# T1: found 0.50, level 5.4 -> ground z~0.64, library z~6.04
build('MAGE_TOWER_T1')
shoot("phase2_t1_ground_a.png", (0.5, 0.5), 2.4, 225, (0, 0), 3.2)
shoot("phase2_t1_ground_b.png", (-0.5, -0.5), 2.4, 45, (0, 0), 3.2)
shoot("phase2_t1_library_a.png", (0.5, 0.5), 7.8, 225, (0, 0), 8.6)
shoot("phase2_t1_library_b.png", (-0.5, -0.5), 7.8, 45, (0, 0), 8.6)

# T2: found 0.65, level 5.8 -> ground z~0.79, enchanter (fl2) z~12.39
build('MAGE_TOWER_T2')
shoot("phase2_t2_ground_a.png", (0.5, 0.5), 2.6, 225, (0, 0), 3.4)
shoot("phase2_t2_enchanter_a.png", (0.5, 0.5), 14.1, 225, (0, 0), 14.9)
shoot("phase2_t2_enchanter_b.png", (-0.5, -0.5), 14.1, 45, (0, 0), 14.9)
