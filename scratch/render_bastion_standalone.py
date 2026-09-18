import bpy
import os
import math
import bmesh
from mathutils import Vector
import sys

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\6ca21b3a-1668-4b5e-a23d-29160ba8b515"

sys.path.insert(0, r"d:\BlendBuildingCreator")
from blend_building_creator.generator.accessories.bastion import build_bastion_tower
from blend_building_creator.generator.materials import setup_building_material_slots

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

mesh = bpy.data.meshes.new("Bastion_Showcase")
obj = bpy.data.objects.new("Bastion_Showcase", mesh)
bpy.context.scene.collection.objects.link(obj)

import blend_building_creator
blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings

setup_building_material_slots(obj, props)

bm = bmesh.new()
# Tower at (0, 0, 0) with door facing +X (1.0, 0.0) into the camera
build_bastion_tower(bm, 0.0, 0.0, z_ground=0.0, base_size=3.2, height=8.2,
                    talus_height=2.2, talus_flare=0.60, door_dir=(1.0, 0.0))
bm.to_mesh(mesh)
bm.free()

# Setup Camera looking directly at the arched entrance doorway on the +X face
cam_data = bpy.data.cameras.new("DoorCam")
cam_data.lens = 40
cam_obj = bpy.data.objects.new("DoorCam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Door is at x = +1.6, y = 0.0, z = 1.08. Camera placed at x = 5.2, y = 1.8, z = 2.4
cam_loc = (5.4, 2.0, 2.2)
cam_target = (1.6, 0.0, 1.35)
cam_obj.location = cam_loc
dir_vec = Vector(cam_target) - Vector(cam_loc)
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

light_data = bpy.data.lights.new(name="SunLight", type='SUN')
light_data.energy = 4.0
light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(-35))

world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.78, 0.86, 0.94, 1.0)
    bg.inputs[1].default_value = 1.0

bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
out_path = os.path.join(out_dir, "bastion_courtyard_entrance.png")
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("Rendered standalone bastion courtyard entrance ->", out_path)
bpy.ops.wm.quit_blender()
