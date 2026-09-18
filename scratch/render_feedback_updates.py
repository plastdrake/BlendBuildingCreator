import bpy
import os
import math
import bmesh
from mathutils import Vector
import sys

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\6ca21b3a-1668-4b5e-a23d-29160ba8b515"
sys.path.insert(0, r"d:\BlendBuildingCreator")

from blend_building_creator.generator.accessories.bastion import build_bastion_tower
from blend_building_creator.generator.accessories.military_props import build_weapon_rack
from blend_building_creator.generator.accessories.banner import build_banner_pole
from blend_building_creator.generator.materials import setup_building_material_slots

import blend_building_creator
blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings

def setup_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.78, 0.85, 0.92, 1.0)
        bg.inputs[1].default_value = 1.0
        
    light_data = bpy.data.lights.new(name="SunLight", type='SUN')
    light_data.energy = 3.8
    light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-35))

# -------------------------------------------------------------
# 1. Render Overhauled Bastion Tower (Full View: Merlons + Doorway + Interior)
# -------------------------------------------------------------
setup_scene()
mesh = bpy.data.meshes.new("Bastion_Mesh")
obj = bpy.data.objects.new("Bastion_Obj", mesh)
bpy.context.scene.collection.objects.link(obj)
setup_building_material_slots(obj, props)

bm = bmesh.new()
# Door facing North +Y (0.0, 1.0)
build_bastion_tower(bm, 0.0, 0.0, z_ground=0.0, base_size=3.2, height=8.2,
                    talus_height=2.2, talus_flare=0.55, door_dir=(0.0, 1.0))
bm.to_mesh(mesh)
bm.free()

cam_data = bpy.data.cameras.new("TowerCam")
cam_data.lens = 38
cam_obj = bpy.data.objects.new("TowerCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Position camera looking at doorway and upper merlons from the courtyard (+Y, +X offset)
cam_loc = (4.8, 6.2, 5.0)
cam_target = (0.0, 0.6, 4.0)
cam_obj.location = cam_loc
dir_vec = Vector(cam_target) - Vector(cam_loc)
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
out_tower = os.path.join(out_dir, "tower_overhaul_verified.png")
bpy.context.scene.render.filepath = out_tower
bpy.ops.render.render(write_still=True)
print("Rendered tower overhaul ->", out_tower)

# -------------------------------------------------------------
# 1b. Close-up of Tower Walk-In Doorway & Hollow Interior
# -------------------------------------------------------------
cam_loc_door = (1.8, 4.4, 1.6)
cam_target_door = (0.0, 1.2, 1.3)
cam_obj.location = cam_loc_door
dir_vec_door = Vector(cam_target_door) - Vector(cam_loc_door)
cam_obj.rotation_euler = dir_vec_door.to_track_quat('-Z', 'Y').to_euler()

out_door = os.path.join(out_dir, "tower_door_interior_verified.png")
bpy.context.scene.render.filepath = out_door
bpy.ops.render.render(write_still=True)
print("Rendered tower door & interior ->", out_door)

# -------------------------------------------------------------
# 1c. Close-up of Open Rooftop Platform with Crenellated Merlons
# -------------------------------------------------------------
cam_loc_top = (3.6, 3.8, 9.4)
cam_target_top = (0.0, 0.0, 7.3)
cam_obj.location = cam_loc_top
dir_vec_top = Vector(cam_target_top) - Vector(cam_loc_top)
cam_obj.rotation_euler = dir_vec_top.to_track_quat('-Z', 'Y').to_euler()

out_top = os.path.join(out_dir, "tower_rooftop_merlons_verified.png")
bpy.context.scene.render.filepath = out_top
bpy.ops.render.render(write_still=True)
print("Rendered tower rooftop & merlons ->", out_top)

# -------------------------------------------------------------
# 2. Render Weapon Rack (Only Spears, Leaning Against Board)
# -------------------------------------------------------------
setup_scene()
mesh_rack = bpy.data.meshes.new("Rack_Mesh")
obj_rack = bpy.data.objects.new("Rack_Obj", mesh_rack)
bpy.context.scene.collection.objects.link(obj_rack)
setup_building_material_slots(obj_rack, props)

bm_rack = bmesh.new()
build_weapon_rack(bm_rack, 0.0, 0.0, z_ground=0.0, ang=0.0)
bm_rack.to_mesh(mesh_rack)
bm_rack.free()

cam_rack_data = bpy.data.cameras.new("RackCam")
cam_rack_data.lens = 50
cam_rack_obj = bpy.data.objects.new("RackCam", cam_rack_data)
bpy.context.scene.collection.objects.link(cam_rack_obj)
bpy.context.scene.camera = cam_rack_obj

# Side-angle camera showing spears touching the top rest board
cam_rack_loc = (1.6, 2.2, 1.4)
cam_rack_target = (0.0, 0.08, 1.1)
cam_rack_obj.location = cam_rack_loc
dir_vec_rack = Vector(cam_rack_target) - Vector(cam_rack_loc)
cam_rack_obj.rotation_euler = dir_vec_rack.to_track_quat('-Z', 'Y').to_euler()

out_rack = os.path.join(out_dir, "weapon_rack_spears_verified.png")
bpy.context.scene.render.filepath = out_rack
bpy.ops.render.render(write_still=True)
print("Rendered weapon rack ->", out_rack)

# -------------------------------------------------------------
# 3. Render Banner Standard (Alpha Transparency & Golden Border)
# -------------------------------------------------------------
setup_scene()
mesh_ban = bpy.data.meshes.new("Banner_Mesh")
obj_ban = bpy.data.objects.new("Banner_Obj", mesh_ban)
bpy.context.scene.collection.objects.link(obj_ban)
setup_building_material_slots(obj_ban, props)

bm_ban = bmesh.new()
build_banner_pole(bm_ban, 0.0, 0.0, z_ground=0.0, height=4.6, flag_dir=(0.0, -1.0))
bm_ban.to_mesh(mesh_ban)
bm_ban.free()

cam_ban_data = bpy.data.cameras.new("BannerCam")
cam_ban_data.lens = 45
cam_ban_obj = bpy.data.objects.new("BannerCam", cam_ban_data)
bpy.context.scene.collection.objects.link(cam_ban_obj)
bpy.context.scene.camera = cam_ban_obj

# Camera looking straight at the banner cloth facing forward (flag_dir = 0, -1)
cam_ban_loc = (0.0, -3.2, 4.0)
cam_ban_target = (0.0, 0.0, 4.0)
cam_ban_obj.location = cam_ban_loc
dir_vec_ban = Vector(cam_ban_target) - Vector(cam_ban_loc)
cam_ban_obj.rotation_euler = dir_vec_ban.to_track_quat('-Z', 'Y').to_euler()

out_ban = os.path.join(out_dir, "banner_alpha_gold_verified.png")
bpy.context.scene.render.filepath = out_ban
bpy.ops.render.render(write_still=True)
print("Rendered banner ->", out_ban)

bpy.ops.wm.quit_blender()
