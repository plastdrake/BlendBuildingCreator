"""Dev verification for the new preset families: geometry + plot fit + render.

Run:  blender --background --factory-startup --python scratch/verify_new_presets.py
"""
import os
import sys
import math
import time

import bpy
from mathutils import Vector

REPO = r"D:\BlendBuildingCreator"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import blend_building_creator
blend_building_creator.register()

OUT = os.path.join(REPO, "scratch", "new_previews")
os.makedirs(OUT, exist_ok=True)
props = bpy.context.scene.fantasy_building_settings

PRESETS = [
    # (preset key, plot half-size X, plot half-size Y)
    ('ARCHERY_RANGE_T1', 20.0, 20.0),
    ('ARCHERY_RANGE_T2', 20.0, 20.0),
    ('ARCHERY_RANGE_T3', 20.0, 20.0),
    ('KNIGHTS_MANOR_T1', 20.0, 20.0),
    ('KNIGHTS_MANOR_T2', 20.0, 20.0),
    ('KNIGHTS_MANOR_T3', 20.0, 20.0),
    ('HEALERS_CHAPEL_T1', 20.0, 20.0),
    ('HEALERS_CHAPEL_T2', 20.0, 20.0),
    ('HEALERS_CHAPEL_T3', 20.0, 20.0),
    ('MAGE_TOWER_T1', 10.0, 10.0),
    ('MAGE_TOWER_T2', 10.0, 10.0),
    ('MAGE_TOWER_T3', 10.0, 10.0),
]


def _clear():
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def _frame_and_render(obj, name):
    verts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    cz = (min(zs) + max(zs)) * 0.5
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    dist = max(8.0, span * 1.5)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 35
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (cx + dist * 0.75, cy - dist * 0.95, cz + span * 0.55)
    direction = Vector((cx, cy, cz)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    bpy.context.scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    _clear()
    bpy.ops.building.create_fantasy_building()

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 4.0
    sun_data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48), math.radians(20), math.radians(40))

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.62, 0.74, 0.9, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.device = 'CPU'
    scn.cycles.samples = 12
    scn.cycles.use_denoising = False
    scn.render.resolution_x = 640
    scn.render.resolution_y = 480
    scn.render.film_transparent = False

    filters = []
    argv = sys.argv
    if "--" in argv:
        filters = [a.upper() for a in argv[argv.index("--") + 1:]]

    results = []
    for key, hx, hy in PRESETS:
        if filters and not any(key.startswith(f) for f in filters):
            continue
        t0 = time.time()
        bpy.ops.building.apply_preset(preset_key=key)
        obj = bpy.context.active_object
        dt = time.time() - t0

        verts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]
        over_x = max(abs(min(xs)), abs(max(xs))) - hx
        over_y = max(abs(min(ys)), abs(max(ys))) - hy
        msg = (f"{key:22s} v={len(obj.data.vertices):7d} "
               f"X[{min(xs):7.2f},{max(xs):7.2f}] Y[{min(ys):7.2f},{max(ys):7.2f}] "
               f"Z[{min(zs):6.2f},{max(zs):6.2f}] "
               f"over=({over_x:+.2f},{over_y:+.2f}) {dt:5.1f}s")
        print(msg, flush=True)
        results.append((key, over_x, over_y, len(obj.data.vertices)))

        if key.endswith('_T3') or key.endswith('_T1'):
            _frame_and_render(obj, key)

    print("\n=== SUMMARY ===", flush=True)
    bad = False
    for key, ox, oy, v in results:
        if v < 200:
            print(f"  EMPTY GEOMETRY: {key} ({v})")
            bad = True
        if ox > 0.05 or oy > 0.05:
            print(f"  PLOT OVERFLOW: {key} over=({ox:+.2f},{oy:+.2f})")
            bad = True
    print("ALL OK" if not bad else "ISSUES FOUND", flush=True)


if __name__ == "__main__":
    main()
