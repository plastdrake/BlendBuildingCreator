"""Phase-2b verification: plot-fit measurement + high-angle layout audit."""
import bpy
import math
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.presets import apply_preset, PRESETS

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings

PLOTS = {'MAGE_TOWER_T1': 16.0, 'MAGE_TOWER_T2': 20.0, 'MAGE_TOWER_T3': 24.0}

for preset, plot in PLOTS.items():
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.name.startswith("Fantasy"):
            bpy.data.objects.remove(obj, do_unlink=True)
    apply_preset(props, preset)
    props.has_interior_furnishing = True
    bpy.ops.building.create_fantasy_building()
    obj = bpy.context.active_object
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    print(f"{preset}: verts={len(xs)} X[{min(xs):.2f},{max(xs):.2f}] "
          f"Y[{min(ys):.2f},{max(ys):.2f}] plot={plot} "
          f"overX={max(max(xs), -min(xs)) - plot / 2:.2f} "
          f"overY={max(max(ys), -min(ys)) - plot / 2:.2f}")
    # Sample the worst offenders on +X beyond the plot line
    far = [(v.co.x, v.co.y, v.co.z) for v in obj.data.vertices
           if abs(v.co.x) > plot / 2][:8]
    for f in far:
        print(f"   beyond-plot vert: ({f[0]:.2f}, {f[1]:.2f}, {f[2]:.2f})")

# Rebuild T1/T2 for high-angle layout shots
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(45))

pt_data = bpy.data.lights.new(name="FillLight", type='POINT')
pt_data.energy = 2000.0
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
cam_data.lens = 16
cam_obj = bpy.data.objects.new(name="Phase2Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj


def build(preset):
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.name.startswith("Fantasy"):
            bpy.data.objects.remove(obj, do_unlink=True)
    apply_preset(props, preset)
    props.has_interior_furnishing = True
    bpy.ops.building.create_fantasy_building()


def shoot(name, cam_z, yaw_deg):
    cam_obj.location = (0.0, 0.0, cam_z)
    cam_obj.rotation_euler = (math.radians(50), 0, math.radians(yaw_deg))
    pt_obj.location = (0.0, 0.0, cam_z - 1.0)
    bpy.context.scene.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)
    print("Rendered", name)


build('MAGE_TOWER_T1')
shoot("phase2b_t1_ground_top0.png", 4.0, 0)
shoot("phase2b_t1_ground_top180.png", 4.0, 180)
shoot("phase2b_t1_library_top0.png", 9.4, 0)
shoot("phase2b_t1_library_top180.png", 9.4, 180)

build('MAGE_TOWER_T2')
shoot("phase2b_t2_ench_top0.png", 16.0, 0)
shoot("phase2b_t2_ench_top180.png", 16.0, 180)
