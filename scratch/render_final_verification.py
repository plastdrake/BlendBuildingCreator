import bpy
import os
import math
from mathutils import Vector
import sys

# Ensure addon is in sys.path and registered
repo_root = r"d:\BlendBuildingCreator"
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
blend_building_creator.register()

# Setup scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='INFANTRY_BARRACKS_T3')

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\6ca21b3a-1668-4b5e-a23d-29160ba8b515"

def setup_cam_and_light(cam_loc, cam_target, lens=38):
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    cam_obj.location = cam_loc
    dir_vec = Vector(cam_target) - Vector(cam_loc)
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

    light_data = bpy.data.lights.new(name="SunLight", type='SUN')
    light_data.energy = 4.0
    light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-35))

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.85, 0.90, 0.96, 1.0)
        bg.inputs[1].default_value = 1.0

def render(filename):
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    path = os.path.join(out_dir, filename)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("Rendered:", path)

def cleanup():
    if bpy.context.scene.camera:
        bpy.data.objects.remove(bpy.context.scene.camera, do_unlink=True)
    sun = bpy.data.objects.get("SunLight")
    if sun:
        bpy.data.objects.remove(sun, do_unlink=True)

# 1. Archery Target: target is at (8.32, -15.65, 1.25)
# Look at it from (8.32, -13.2, 1.40)
setup_cam_and_light((8.32, -13.2, 1.40), (8.32, -15.65, 1.25), lens=42)
render("final_archery_target.png")
cleanup()

# 2. Weapon Rack: rack is at (5.72, -11.58, 0.0)
# Look at it from (5.72, -9.2, 1.25)
setup_cam_and_light((5.72, -9.2, 1.25), (5.72, -11.58, 1.0), lens=40)
render("final_weapon_rack.png")
cleanup()

# 3. Training Quintain: dummy is at (-5.72, -11.58, 1.5)
# Look at it from (-5.72, -9.0, 1.55)
setup_cam_and_light((-5.72, -9.0, 1.55), (-5.72, -11.58, 1.35), lens=40)
render("final_training_dummy.png")
cleanup()

# 4. Bastion Courtyard Entrance: left bastion is at (-19.5, -20.25), entrance is at (-19.5, -18.65)
# Look from (-15.0, -16.0, 2.2) towards (-19.5, -18.65, 1.5)
setup_cam_and_light((-15.0, -16.0, 2.2), (-19.5, -18.65, 1.5), lens=34)
render("final_bastion_entrance.png")
cleanup()

# 5. Full Drill Yard Overview from front palisade gate (0.0, -20.25, 4.2)
setup_cam_and_light((0.0, -20.25, 4.2), (0.0, -11.0, 1.6), lens=28)
render("final_drill_yard.png")
cleanup()

print("All final verification renders complete!")
