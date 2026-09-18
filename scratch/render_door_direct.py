import bpy
import os
import math
from mathutils import Vector
import sys

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\6ca21b3a-1668-4b5e-a23d-29160ba8b515"

sys.path.insert(0, r"d:\BlendBuildingCreator")
import blend_building_creator
blend_building_creator.register()

try:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.building.create_fantasy_building()
    bpy.ops.building.apply_preset(preset_key='INFANTRY_BARRACKS_T3')

    # Direct straight-on shot of the bastion arched entrance doorway
    # Door is at (-17.9, -20.25, 1.08) on the east face of the left bastion
    # Camera placed directly in front of doorway at (-15.0, -20.25, 1.45)
    cam_data = bpy.data.cameras.new("DoorCam")
    cam_data.lens = 42
    cam_obj = bpy.data.objects.new("DoorCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    cam_loc = (-14.5, -17.0, 2.2)
    cam_target = (-17.9, -20.25, 1.35)
    cam_obj.location = cam_loc
    dir_vec = Vector(cam_target) - Vector(cam_loc)
    cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

    light_data = bpy.data.lights.new(name="SunLight", type='SUN')
    light_data.energy = 4.0
    light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.rotation_euler = (math.radians(35), math.radians(15), math.radians(-30))

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
    print("Rendered straight-on door view ->", out_path, flush=True)

except Exception as e:
    print("ERROR:", e, flush=True)
    import traceback
    traceback.print_exc()

finally:
    bpy.ops.wm.quit_blender()
