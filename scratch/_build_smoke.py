"""Headless build-only smoke test for the Mage Tower (no renders).

Builds every Mage Tower tier through the preset operator (the exact path the
user runs in Blender) and prints vertex/polygon counts and bounds so geometry
regressions show up without any rendering.
"""
import os
import sys

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

bad = False
for key in ("MAGE_TOWER_T1", "MAGE_TOWER_T2", "MAGE_TOWER_T3"):
    bpy.ops.building.apply_preset(preset_key=key)
    obj = bpy.context.active_object
    v = len(obj.data.vertices)
    p = len(obj.data.polygons)
    verts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [q.x for q in verts]
    ys = [q.y for q in verts]
    zs = [q.z for q in verts]
    print(f"{key:16s} v={v:7d} p={p:7d} "
          f"X[{min(xs):6.1f},{max(xs):6.1f}] Y[{min(ys):6.1f},{max(ys):6.1f}] "
          f"Z[{min(zs):5.1f},{max(zs):5.1f}]", flush=True)
    if v < 200 or len(obj.data.polygons) == 0:
        bad = True

print("SMOKE OK" if not bad else "SMOKE FAIL", flush=True)