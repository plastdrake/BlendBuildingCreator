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


def add_light(name, loc, energy):
    d = bpy.data.lights.new(name=name, type='POINT')
    d.energy = energy
    d.shadow_soft_size = 2.0
    o = bpy.data.objects.new(name=name, object_data=d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc


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
    bpy.context.scene.cycles.samples = 12
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.render.resolution_x = 1000
    bpy.context.scene.render.resolution_y = 620


def render_view(name, cam_loc, target, lens=32):
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


for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.has_stable = True
props.has_servant_quarters = True
props.has_estate_fountain = True
props.estate_awnings = True
props.outbuilding_offset_x = 24.0
props.outbuilding_offset_y = -10.0
props.plot_setback = 6.0
bpy.ops.building.regenerate()

setup_render()
render_view('estate_overview.png', (0.0, -55.0, 34.0), (0.0, -6.0, 0.0), lens=30)
render_view('estate_front.png', (34.0, -40.0, 18.0), (0.0, -6.0, 2.0), lens=30)
render_view('estate_top.png', (0.0, -6.0, 70.0), (0.0, -6.0, 0.0), lens=28)
print("ESTATE RENDER DONE")
