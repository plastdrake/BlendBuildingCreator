import bpy
import os
import math
from mathutils import Vector
import sys

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\6ca21b3a-1668-4b5e-a23d-29160ba8b515"

def setup_camera_and_sun(cam_loc, cam_target, energy=3.5, lens=38):
    cam_data = bpy.data.cameras.new("ViewCam")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new("ViewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    cam_obj.location = cam_loc
    dir_vec = Vector(cam_target) - Vector(cam_loc)
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

    light_data = bpy.data.lights.new(name="SunLight", type='SUN')
    light_data.energy = energy
    light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(-40))

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.78, 0.86, 0.94, 1.0)
        bg.inputs[1].default_value = 1.0

def render_image(filename, res=1024):
    bpy.context.scene.render.resolution_x = res
    bpy.context.scene.render.resolution_y = res
    out_path = os.path.join(out_dir, filename)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print("Rendered successfully ->", out_path)

def clear_camera():
    if bpy.context.scene.camera:
        bpy.data.objects.remove(bpy.context.scene.camera, do_unlink=True)
    sun = bpy.data.objects.get("SunLight")
    if sun:
        bpy.data.objects.remove(sun, do_unlink=True)

sys.path.insert(0, r"d:\BlendBuildingCreator")
import blend_building_creator
blend_building_creator.register()

try:
    # 1. Clear and create building
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.building.create_fantasy_building()
    bpy.ops.building.apply_preset(preset_key='INFANTRY_BARRACKS_T3')

    # View 1: Archery Target (Target is at x=8.32, y=-15.65, z=1.25)
    # Camera at (8.32, -12.2, 1.45) looking straight at target
    print("Rendering Archery Target closeup...")
    setup_camera_and_sun(cam_loc=(8.32, -12.2, 1.45), cam_target=(8.32, -15.65, 1.25), lens=44)
    render_image("archery_target_closeup.png")
    clear_camera()

    # View 2: Weapon Rack (Rack is at x=5.72, y=-11.58, z=0.0)
    print("Rendering Weapon Rack closeup...", flush=True)
    setup_camera_and_sun(cam_loc=(5.72, -8.6, 1.35), cam_target=(5.72, -11.58, 1.1), lens=40)
    render_image("weapon_rack_closeup.png")
    clear_camera()

    # View 3: Training Dummy / Quintain (Dummy is at x=-5.72, y=-11.58, z=1.5)
    print("Rendering Training Dummy closeup...", flush=True)
    setup_camera_and_sun(cam_loc=(-5.72, -8.5, 1.6), cam_target=(-5.72, -11.58, 1.4), lens=40)
    render_image("training_dummy_closeup.png")
    clear_camera()

    # View 4: Bastion Tower Courtyard Entrance
    # Left bastion at (-19.5, -20.25). Entrance door at (-17.9, -20.25, 1.08) facing +X into courtyard.
    # Camera at (-13.5, -18.8, 1.8) looking at doorway
    print("Rendering Bastion Tower Courtyard Entrance...", flush=True)
    setup_camera_and_sun(cam_loc=(-13.5, -18.8, 1.8), cam_target=(-17.9, -20.25, 1.35), lens=36)
    render_image("bastion_courtyard_entrance.png")
    clear_camera()

    # View 5: Full Drill Yard Overview from Courtyard Front
    print("Rendering Full Drill Yard Overview...", flush=True)
    setup_camera_and_sun(cam_loc=(0.0, -21.0, 4.5), cam_target=(0.0, -11.0, 1.5), lens=26)
    render_image("courtyard_drill_yard.png")
    clear_camera()

    print("ALL 5 PERFECT VIEWS COMPLETED!", flush=True)

except Exception as e:
    print("ERROR RENDERING VIEWS:", e)
    import traceback
    traceback.print_exc()

finally:
    bpy.ops.wm.quit_blender()
