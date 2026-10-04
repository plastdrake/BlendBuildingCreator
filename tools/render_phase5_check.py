"""Phase-5 verification: alchemy tome + flasks, pedestal spikes, bookcase rail."""
import bpy
import math
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import bmesh
import blend_building_creator
from blend_building_creator.generator.materials import (
    setup_building_material_slots, MAT_INDEX_WOOD)
from blend_building_creator.generator.poly import create_beveled_box
from blend_building_creator.generator.mesh_utils import apply_box_uvs
from blend_building_creator.generator.accessories.interior_furniture import (
    build_alchemy_station,
    build_spellbook_pedestal,
    build_grand_bookcase,
)

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

blend_building_creator.register()

mesh = bpy.data.meshes.new("Phase5Mesh")
obj = bpy.data.objects.new("Phase5", mesh)
bpy.context.scene.collection.objects.link(obj)

props_dummy = bpy.context.scene.fantasy_building_settings
setup_building_material_slots(obj, props_dummy)

bm = bmesh.new()
create_beveled_box(bm, size=(24.0, 24.0, 0.2), location=(0.0, 0.0, -0.1),
                   mat_index=MAT_INDEX_WOOD)

build_alchemy_station(bm, x=0.0, y=0.0, z_ground=0.0, ang=0.0,
                      length=1.75, width=0.76)
build_spellbook_pedestal(bm, x=3.0, y=0.0, z_ground=0.0, ang=-0.4)
build_grand_bookcase(bm, x=-3.2, y=0.0, z_ground=0.0, ang=0.0,
                     width=2.1, height=3.2)

apply_box_uvs(bm, scale=1.0)
bm.to_mesh(mesh)
bm.free()

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

cam_data = bpy.data.cameras.new(name="Phase5Cam")
cam_data.lens = 42
cam_obj = bpy.data.objects.new(name="Phase5Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Shot 1: alchemy bench from the front (tome, mortar+pestle, flasks)
cam_obj.location = (0.0, -2.2, 1.7)
cam_obj.rotation_euler = (math.radians(62), 0, math.radians(0))
fill_obj.location = (0.0, -1.2, 2.0)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase5_alchemy_bench.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase5_alchemy_bench.png")

# Shot 2: pedestal front (grimoire, spikes holding candles)
cam_obj.location = (3.0, -2.0, 1.6)
cam_obj.rotation_euler = (math.radians(64), 0, math.radians(0))
fill_obj.location = (3.0, -1.0, 1.9)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase5_pedestal.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase5_pedestal.png")

# Shot 3: bookcase front (rail, straps, ladder)
cam_obj.location = (-3.2, -3.4, 1.9)
cam_obj.rotation_euler = (math.radians(64), 0, math.radians(0))
fill_obj.location = (-3.2, -2.0, 2.2)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase5_bookcase.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase5_bookcase.png")
