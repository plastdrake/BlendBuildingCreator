"""Diagnostic: compare wall UVs in the opening bay vs a plain bay."""
import sys
import math

import bpy
from mathutils import Vector

REPO = r"D:\BlendBuildingCreator"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import blend_building_creator
blend_building_creator.register()

for o in list(bpy.context.scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T1')
obj = bpy.context.active_object
me = obj.data
mw = obj.matrix_world
names = [m.name for m in me.materials]
uvl = me.uv_layers.active

out_r = 4.048


def show(ang_deg, z):
    a = math.radians(ang_deg)
    probe = Vector((out_r * math.cos(a), out_r * math.sin(a), z))
    best = None
    for p in me.polygons:
        c = mw @ p.center
        n = (mw.to_3x3() @ p.normal).normalized()
        if (c - probe).length > 0.25:
            continue
        if n.x * c.x + n.y * c.y < 0.5 * out_r:
            continue
        best = p
    if best is None:
        print(f"  ang={ang_deg} z={z}: none", flush=True)
        return
    print(f"  ang={ang_deg} z={z}: mat={names[best.material_index]} smooth={best.use_smooth}", flush=True)
    for li in best.loop_indices:
        li_ = li
        v = me.vertices[me.loops[li_].vertex_index]
        co = mw @ v.co
        uv = uvl.data[li_].uv
        print(f"      v=({co.x:+.2f},{co.y:+.2f},{co.z:+.2f})  uv=({uv.x:+.3f},{uv.y:+.3f})", flush=True)


print("--- strip angles across height ---", flush=True)
for ang in (-111, -110, -109, -69, -68):
    for zz in (2.0, 5.0, 8.0):
        show(ang, zz)
