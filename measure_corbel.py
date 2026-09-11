import sys
sys.path.append('d:/BlendBuildingCreator')
import bpy
import bmesh
from mathutils import Vector

# Clean scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
blend_building_creator.register()

# Let's inspect FantasyBuildingSettings defaults
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.has_cantilever = True
props.cantilever_overhang = 0.35
props.ground_floor_stone = True
props.has_pillared_overhang = False
props.has_mini_wing = False
props.has_balcony = False
props.wonkiness = 0.0  # Zero wonkiness for exact coordinate check
bpy.ops.building.regenerate()

obj = bpy.context.active_object
mesh = obj.data

# Find corbel faces/vertices and stone wall vertices around the front wall
# Front wall base_d is props.depth = 5.4 or 6.0
# Let's print the Y extent of all vertices with Z between 2.5 and 3.2
front_verts = [v.co for v in mesh.vertices if -3.5 <= v.co.y <= -2.0 and 2.5 <= v.co.z <= 3.5]
min_y = min(v.y for v in front_verts)
max_y = max(v.y for v in front_verts)
print(f"Front verts in Z [2.5, 3.5]: min_y={min_y:.4f}, max_y={max_y:.4f}")

# Find corbel vertices specifically
# Corbels have MAT_INDEX_TIMBER (3)
# Let's find timber faces around y_min
bm = bmesh.new()
bm.from_mesh(mesh)
timber_corbel_verts = []
for f in bm.faces:
    if f.material_index == 3: # TIMBER
        cz = sum(v.co.z for v in f.verts) / len(f.verts)
        cy = sum(v.co.y for v in f.verts) / len(f.verts)
        if 2.4 <= cz <= 3.0 and cy < -2.0:
            timber_corbel_verts.extend(f.verts)

if timber_corbel_verts:
    c_min_y = min(v.co.y for v in timber_corbel_verts)
    c_max_y = max(v.co.y for v in timber_corbel_verts)
    c_min_z = min(v.co.z for v in timber_corbel_verts)
    c_max_z = max(v.co.z for v in timber_corbel_verts)
    print(f"Corbel bounds: Y=[{c_min_y:.4f}, {c_max_y:.4f}], Z=[{c_min_z:.4f}, {c_max_z:.4f}]")

# Stone wall faces at z ~ 2.6
stone_verts = []
for f in bm.faces:
    if f.material_index == 0: # STONE
        cz = sum(v.co.z for v in f.verts) / len(f.verts)
        if 2.4 <= cz <= 3.0:
            stone_verts.extend(f.verts)
if stone_verts:
    s_min_y = min(v.co.y for v in stone_verts)
    s_max_y = max(v.co.y for v in stone_verts)
    print(f"Stone wall Y=[{s_min_y:.4f}, {s_max_y:.4f}] at Z=[2.4, 3.0]")

# Soffit / overhanging wall beam at z ~ 3.0
beam_verts = []
for f in bm.faces:
    cz = sum(v.co.z for v in f.verts) / len(f.verts)
    cy = sum(v.co.y for v in f.verts) / len(f.verts)
    if 2.8 <= cz <= 3.3 and cy < -2.5:
        beam_verts.extend(f.verts)
if beam_verts:
    b_min_z = min(v.co.z for v in beam_verts)
    b_max_z = max(v.co.z for v in beam_verts)
    print(f"Beam/Soffit Z=[{b_min_z:.4f}, {b_max_z:.4f}]")

bm.free()
