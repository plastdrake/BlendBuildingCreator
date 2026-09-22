"""Apply arbitrary presets by key and report geometry (no render).

blender --background --factory-startup --python scratch/smoke_presets.py -- KEY1 KEY2 ...
"""
import os
import sys
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

for o in list(bpy.context.scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.building.create_fantasy_building()

keys = []
if "--" in sys.argv:
    keys = sys.argv[sys.argv.index("--") + 1:]

bad = False
for key in keys:
    t0 = time.time()
    bpy.ops.building.apply_preset(preset_key=key)
    obj = bpy.context.active_object
    v = len(obj.data.vertices)
    p = len(obj.data.polygons)
    verts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [q.x for q in verts]
    ys = [q.y for q in verts]
    zs = [q.z for q in verts]
    over = max(abs(min(xs)), abs(max(xs)), abs(min(ys)), abs(max(ys))) - 20.0
    print(f"{key:26s} v={v:7d} p={p:7d} "
          f"X[{min(xs):6.1f},{max(xs):6.1f}] Y[{min(ys):6.1f},{max(ys):6.1f}] "
          f"Z[{min(zs):5.1f},{max(zs):5.1f}] over={over:+.2f} {time.time()-t0:6.1f}s",
          flush=True)
    if v < 200 or over > 0.05:
        bad = True

print("SMOKE OK" if not bad else "SMOKE FAIL", flush=True)
