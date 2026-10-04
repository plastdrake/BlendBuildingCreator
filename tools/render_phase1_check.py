"""Phase-1 verification: cauldron hollow mouth, mortar hollow bowl, grimoire page UVs."""
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
    build_magic_cauldron,
    build_mortar_and_pestle,
    build_spellbook_pedestal,
)

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

blend_building_creator.register()

mesh = bpy.data.meshes.new("Phase1Mesh")
obj = bpy.data.objects.new("Phase1", mesh)
bpy.context.scene.collection.objects.link(obj)

props_dummy = bpy.context.scene.fantasy_building_settings
setup_building_material_slots(obj, props_dummy)

bm = bmesh.new()
create_beveled_box(bm, size=(24.0, 24.0, 0.2), location=(0.0, 0.0, -0.1),
                   mat_index=MAT_INDEX_WOOD)

build_magic_cauldron(bm, x=0.0, y=0.0, z_ground=0.0, radius=0.52, height=0.72)
build_mortar_and_pestle(bm, x=2.2, y=0.0, z_ground=0.0)
build_spellbook_pedestal(bm, x=-2.4, y=0.0, z_ground=0.0, ang=0.0)

# Exercise the finalize UV path so the mat-40 skip + face tags are verified,
# exactly as a real building build would.
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

cam_data = bpy.data.cameras.new(name="Phase1Cam")
cam_obj = bpy.data.objects.new(name="Phase1Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Shot 1: looking down into the cauldron mouth (hollow wall + glowing brew)
cam_data.lens = 40
cam_obj.location = (0.0, -1.7, 2.1)
cam_obj.rotation_euler = (math.radians(58), 0, 0)
fill_obj.location = (0.0, -1.0, 2.4)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase1_cauldron_mouth.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase1_cauldron_mouth.png")

# Shot 2: mortar & pestle hollow bowl close-up
cam_obj.location = (2.2, -1.1, 0.85)
cam_obj.rotation_euler = (math.radians(60), 0, 0)
fill_obj.location = (2.2, -0.6, 1.1)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase1_mortar_bowl.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase1_mortar_bowl.png")

# Shot 3: open grimoire top-down (page spread alignment)
cam_data.lens = 50
cam_obj.location = (-2.4, -0.9, 2.3)
cam_obj.rotation_euler = (math.radians(48), 0, 0)
fill_obj.location = (-2.4, -0.5, 2.0)
bpy.context.scene.render.filepath = os.path.join(out_dir, "phase1_grimoire_pages.png")
bpy.ops.render.render(write_still=True)
print("Rendered phase1_grimoire_pages.png")
