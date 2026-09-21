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


def add_light(name, loc, energy, color=(1.0, 0.95, 0.9)):
    d = bpy.data.lights.new(name=name, type='POINT')
    d.energy = energy
    d.color = color
    d.shadow_soft_size = 0.5
    o = bpy.data.objects.new(name=name, object_data=d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc


def setup_render():
    sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
    sun_data.energy = 4.0
    sun_data.color = (1.0, 0.96, 0.90)
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))
    add_light("InteriorFill", (-1.5, 0.0, 2.4), 320.0)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.6, 0.75, 0.9, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'CPU'
    bpy.context.scene.cycles.samples = 16
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.render.resolution_x = 900
    bpy.context.scene.render.resolution_y = 600


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
    print(f"RENDERED -> {out}", flush=True)


for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='ARTISAN_BAKERY_T1')

setup_render()
OVEN = (-3.57, 0.0, 1.1)
# Top-down: chimney footprint over the oven
render_view('bakery_top.png', (0.0, 0.0, 30.0), (0.0, 0.0, 0.0), lens=35)
# Interior view of the oven and its rising flue
render_view('bakery_interior.png', (1.6, 1.6, 1.9), OVEN, lens=20)
render_view('bakery_interior2.png', (2.0, -1.8, 1.7), OVEN, lens=20)
# Exterior left wall: wall-mounted bread box
render_view('bakery_ext_left.png', (-13.0, -9.0, 5.5), (-4.5, 0.0, 1.0), lens=30)
render_view('bakery_box.png', (-9.5, 0.0, 1.4), (-4.75, 0.0, 0.9), lens=40)
print("BAKERY RENDER DONE")
