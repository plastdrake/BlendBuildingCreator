import sys, os, math
import bpy
from mathutils import Vector

repo_root = r'd:\BlendBuildingCreator'
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass


def setup_render():
    sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
    sun_data.energy = 4.0
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.render.resolution_x = 1000
    bpy.context.scene.render.resolution_y = 700
    bpy.context.scene.display.shading.light = 'STUDIO'
    bpy.context.scene.display.shading.color_type = 'MATERIAL'


def render_view(name, cam_loc, target, lens=30):
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = cam_loc
    direction = Vector(target) - Vector(cam_loc)
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    out = os.path.join(repo_root, "scratch", name)
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("RENDERED -> " + out, flush=True)


for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='ARTISAN_FISHER_T2')

setup_render()
render_view('fisher_front.png', (0.0, -16.0, 4.0), (0.0, 0.0, 1.6), lens=40)
render_view('fisher_door.png', (0.0, -9.0, 1.6), (0.0, -2.0, 1.4), lens=45)
print("FISHER RENDER DONE")
