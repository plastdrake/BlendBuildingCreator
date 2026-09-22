"""Diagnostic close-up renders for gaps: pillars, bands, stairwell."""
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


def shot(loc, target, name, lens=50, rx=640, ry=640):
    cam_data = bpy.data.cameras.new("Cam" + name)
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam" + name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    scn = bpy.context.scene
    scn.render.resolution_x = rx
    scn.render.resolution_y = ry
    scn.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    clear()
    bpy.ops.building.create_fantasy_building()
    bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T3')

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

    props = bpy.context.scene.fantasy_building_settings
    found_h = props.foundation_height if props.has_foundation else 0.5
    level_h = max(4.6, props.floor_height)
    levels = max(3, props.num_floors)
    crown_z = found_h + (levels - 1) * level_h

    # Fill lights inside so the stairwell interior is readable.
    for i, (loc, e) in enumerate([((0.5, -0.4, 2.6), 1500.0),
                                  ((0.0, -1.5, crown_z - 1.1), 2500.0),
                                  ((0.0, 0.0, crown_z + 0.6), 2500.0)]):
        pl = bpy.data.lights.new("Fill%d" % i, type='POINT')
        pl.energy = e
        pl.shadow_soft_size = 1.0
        ob = bpy.data.objects.new("Fill%d" % i, pl)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc

    # Bottom shaft storey exterior (pillar visibility).
    shot((2.0, -22.0, 3.6), (0.0, 0.0, 3.2), "gaps_base", lens=58)
    # Storey-0/1 band crossing a seam pillar (pillar at -67.5 deg).
    shot((2.4, -12.0, 7.2), (1.72, -4.16, 6.35), "gaps_band", lens=90)
    # Top-floor stairwell opening seen from inside, above and behind.
    shot((0.4, 1.6, crown_z + 2.6), (2.9, -2.1, crown_z - 0.3),
         "gaps_stair_top", lens=38)
    # Same opening looking UP from the storey below.
    shot((0.0, 0.0, crown_z - 2.2), (2.9, -2.1, crown_z - 0.1),
         "gaps_stair_under", lens=30)
    # Very close at the junction of the top step and the floor edge.
    shot((2.0, -4.4, crown_z + 1.1), (3.4, -1.4, crown_z - 0.3),
         "gaps_stair_edge", lens=62)


if __name__ == "__main__":
    main()
