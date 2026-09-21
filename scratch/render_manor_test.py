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
    sun_obj.rotation_euler = (math.radians(48), math.radians(18), math.radians(30))
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.6, 0.75, 0.9, 1.0)
        bg.inputs["Strength"].default_value = 1.0
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'CPU'
    bpy.context.scene.cycles.samples = 10
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.render.resolution_x = 1100
    bpy.context.scene.render.resolution_y = 640


def render_view(name, cam_loc, target, lens=30):
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = cam_loc
    cam_obj.rotation_euler = (Vector(target) - Vector(cam_loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    out = os.path.join(repo_root, "scratch", name)
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED -> {out}", flush=True)


preset = 'NOBLE_MANOR_T1'
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key=preset)

setup_render()
render_view('manor_overview.png', (0.0, -78.0, 46.0), (0.0, -6.0, 2.0), lens=30)
render_view('manor_front.png', (48.0, -60.0, 24.0), (0.0, -6.0, 3.0), lens=30)
render_view('manor_top.png', (0.0, -12.0, 100.0), (0.0, -12.0, 0.0), lens=28)
print("MANOR RENDER DONE")
