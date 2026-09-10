"""
Diagnostic close-up renders to inspect reported issues:
corner pillar thickness, cantilever corbels, balcony braces, chimney/dormer overlap, door detail.
"""
import os
import bpy
import math

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings

# Configure to trigger all reported issue areas at once
props.num_floors = 3
props.has_cantilever = True
props.cantilever_overhang = 0.40
props.has_balcony = True
props.has_chimney = True
props.has_dormers = True
props.has_foundation = True
bpy.ops.building.regenerate()
building = bpy.context.active_object

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(55), math.radians(15), math.radians(35))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.55, 0.70, 0.88, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 900
scene.render.resolution_y = 700

out_dir = os.path.join(script_dir, "renders_diag")
os.makedirs(out_dir, exist_ok=True)

def render_from(name, location, target=(0, 0, 2.0), lens=35):
    cam_data = bpy.data.cameras.new(name=f"Cam_{name}")
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new(f"Cam_{name}", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = location
    direction = (
        target[0] - location[0],
        target[1] - location[1],
        target[2] - location[2],
    )
    import mathutils
    dirvec = mathutils.Vector(direction)
    rot_quat = dirvec.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()
    scene.camera = cam_obj
    scene.render.filepath = os.path.join(out_dir, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

# Corner pillar close-up
render_from("corner_pillar", (3.2, -4.0, 1.2), target=(1.8, -1.8, 1.0), lens=50)
# Cantilever corbel underside close-up
render_from("cantilever_corbel", (2.5, -3.5, 2.9), target=(0.5, -1.8, 3.1), lens=45)
# Balcony close-up
render_from("balcony", (3.0, -3.0, 4.5), target=(0.0, -1.6, 4.6), lens=40)
# Chimney/dormer roof close-up
render_from("chimney_dormer", (3.5, -1.0, 7.0), target=(0.5, 0.5, 6.2), lens=40)
# Door close-up
render_from("door_front", (0.0, -3.5, 1.2), target=(0.0, -1.9, 1.1), lens=45)
# Full exterior overview
render_from("overview", (7.0, -8.0, 4.5), target=(0.0, 0.0, 3.0), lens=32)

print("DONE_DIAG_RENDER")
