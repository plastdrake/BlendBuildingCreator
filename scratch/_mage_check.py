"""Quick close-up verification renders for the Mage Tower fixes."""
import os
import sys
import math

import bpy
from mathutils import Vector

REPO = r"D:\BlendBuildingCreator"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import blend_building_creator
blend_building_creator.register()

OUT = os.path.join(REPO, "scratch", "new_previews")
os.makedirs(OUT, exist_ok=True)


def clear():
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def setup_shot(loc, target, name, lens=50, span=6.0):
    cam_data = bpy.data.cameras.new("Cam" + name)
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam" + name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    clear()
    bpy.ops.building.create_fantasy_building()
    bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T3')
    obj = bpy.context.active_object

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 4.5
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(15), math.radians(30))
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.62, 0.74, 0.9, 1.0)

    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.device = 'CPU'
    scn.cycles.samples = 10
    scn.cycles.use_denoising = False
    scn.render.resolution_x = 560
    scn.render.resolution_y = 620

    props = bpy.context.scene.fantasy_building_settings
    found_h = props.foundation_height if props.has_foundation else 0.5
    level_h = max(4.6, props.floor_height)
    levels = max(3, props.num_floors)
    crown_z = found_h + (levels - 1) * level_h

    # Interior fill light so the tower's inside is readable.
    pl = bpy.data.lights.new("Fill", type='POINT')
    pl.energy = 1500.0
    pl.shadow_soft_size = 1.2
    pl_obj = bpy.data.objects.new("Fill", pl)
    bpy.context.scene.collection.objects.link(pl_obj)
    pl_obj.location = (0.5, -0.4, 2.6)
    pl2 = bpy.data.lights.new("Fill2", type='POINT')
    pl2.energy = 2500.0
    pl2.shadow_soft_size = 1.0
    pl2_obj = bpy.data.objects.new("Fill2", pl2)
    bpy.context.scene.collection.objects.link(pl2_obj)
    pl2_obj.location = (0.0, -1.5, crown_z - 1.1)

    # Full front view to spot the wall UV/shading band
    scn.render.resolution_x = 640
    scn.render.resolution_y = 960
    setup_shot((0.6, -30.0, 13.0), (0.0, 0.0, 12.5), "mage_wall", lens=62)
    # Front door
    setup_shot((-1.6, -14.0, 2.0), (0.0, -4.6, 1.5), "mage_door", lens=55)
    # Door from the interior
    setup_shot((0.4, 3.6, 2.2), (0.0, -4.4, 1.4), "mage_door_in", lens=48)


if __name__ == "__main__":
    main()
