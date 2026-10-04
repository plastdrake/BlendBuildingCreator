import bpy
import math
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.generator.materials import setup_building_material_slots
from blend_building_creator.generator.accessories.interior_furniture import (
    build_spellbook_pedestal,
    build_alchemy_station,
    build_magic_cauldron,
    build_scrying_pool,
    build_bunk_bed,
    build_desk,
    build_chair,
    build_sofa,
    build_armchair,
    build_round_table,
    build_rug,
)
from blend_building_creator.generator.accessories.mage_furnishing import (
    _local_to_world,
    _chair_ang_facing,
)
import bmesh

# Reset scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Enable add-on to ensure properties exist
blend_building_creator.register()

mesh = bpy.data.meshes.new("PropsShowcaseMesh")
obj = bpy.data.objects.new("PropsShowcase", mesh)
bpy.context.scene.collection.objects.link(obj)

props_dummy = bpy.context.scene.fantasy_building_settings
setup_building_material_slots(obj, props_dummy)

bm = bmesh.new()

from blend_building_creator.generator.poly import create_beveled_box
from blend_building_creator.generator.materials import MAT_INDEX_WOOD

# Wood plank floor
create_beveled_box(bm, size=(24.0, 24.0, 0.2), location=(0.0, 0.0, -0.1), mat_index=MAT_INDEX_WOOD)

# 1. Scrying Pool at (0, 0, 0)
build_scrying_pool(bm, x=0.0, y=0.0, z_ground=0.0, radius=0.95)

# 2. Bunk Bed at (5.0, 0.0, 0.0)
build_bunk_bed(bm, x=5.0, y=0.0, z_ground=0.0, ang=0.0, length=2.05, width=1.05)

# 3. Desk and properly oriented Chair at (-5.0, 0.0, 0.0)
desk_pos = ( -5.0, 0.0 )
desk_ang = 0.35
build_desk(bm, x=desk_pos[0], y=desk_pos[1], z_ground=0.0, ang=desk_ang, width=1.4)
c_pos = _local_to_world(bpy.context.scene.cursor.location.__class__((*desk_pos, 0.0)), desk_ang, 0.0, -0.60)
c_ang = _chair_ang_facing(desk_pos[0], desk_pos[1], c_pos.x, c_pos.y)
build_chair(bm, x=c_pos.x, y=c_pos.y, z_ground=0.0, ang=c_ang)

# 4. Salon with Sofa, Table, and Armchairs at (0.0, 6.0, 0.0)
salon_center = (0.0, 6.0)
build_rug(bm, x=salon_center[0], y=salon_center[1], z_ground=0.0, width=2.4, length=2.8, rug_style=1)
build_round_table(bm, x=salon_center[0], y=salon_center[1], z_ground=0.0, radius=0.45)
sofa_pos = _local_to_world(bpy.context.scene.cursor.location.__class__((*salon_center, 0.0)), 0.0, 0.0, -0.80)
sofa_ang = _chair_ang_facing(salon_center[0], salon_center[1], sofa_pos.x, sofa_pos.y)
build_sofa(bm, x=sofa_pos.x, y=sofa_pos.y, z_ground=0.0, ang=sofa_ang, length=1.9)
arm1_pos = _local_to_world(bpy.context.scene.cursor.location.__class__((*salon_center, 0.0)), 0.0, 0.90, 0.10)
arm1_ang = _chair_ang_facing(salon_center[0], salon_center[1], arm1_pos.x, arm1_pos.y)
build_armchair(bm, x=arm1_pos.x, y=arm1_pos.y, z_ground=0.0, ang=arm1_ang)

bm.to_mesh(mesh)
bm.free()

# Lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(45))

fill_data = bpy.data.lights.new(name="FillLight", type='POINT')
fill_data.energy = 800.0
fill_data.color = (1.0, 0.95, 0.9)
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
bpy.context.scene.collection.objects.link(fill_obj)

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720

out_dir = os.path.join(repo_root, "renders")
os.makedirs(out_dir, exist_ok=True)

cam_data = bpy.data.cameras.new(name="PropCam")
cam_data.lens = 38
cam_obj = bpy.data.objects.new(name="PropCam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Shot 1: Scrying Pool close-up showing hollow font and floating crystal
cam_obj.location = (0.0, -2.5, 1.85)
cam_obj.rotation_euler = (math.radians(62), 0, 0)
fill_obj.location = (0.0, -1.5, 2.2)
bpy.context.scene.render.filepath = os.path.join(out_dir, "showcase_scrying_pool.png")
bpy.ops.render.render(write_still=True)
print("Rendered showcase_scrying_pool.png")

# Shot 2: Bunk Bed close-up
cam_obj.location = (5.0, -3.0, 2.0)
cam_obj.rotation_euler = (math.radians(62), 0, 0)
fill_obj.location = (5.0, -1.8, 2.4)
bpy.context.scene.render.filepath = os.path.join(out_dir, "showcase_bunk_bed.png")
bpy.ops.render.render(write_still=True)
print("Rendered showcase_bunk_bed.png")

# Shot 3: Desk & Chair alignment
cam_obj.location = (-5.0, -2.8, 1.80)
cam_obj.rotation_euler = (math.radians(62), 0, 0)
fill_obj.location = (-5.0, -1.8, 2.2)
bpy.context.scene.render.filepath = os.path.join(out_dir, "showcase_desk_chair.png")
bpy.ops.render.render(write_still=True)
print("Rendered showcase_desk_chair.png")

# Shot 4: Salon Sofa & Armchair facing table
cam_obj.location = (0.0, 3.2, 2.0)
cam_obj.rotation_euler = (math.radians(65), 0, 0)
fill_obj.location = (0.0, 4.8, 2.5)
bpy.context.scene.render.filepath = os.path.join(out_dir, "showcase_salon_seating.png")
bpy.ops.render.render(write_still=True)
print("Rendered showcase_salon_seating.png")
