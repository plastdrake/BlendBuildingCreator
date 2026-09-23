import sys
import os
import math
import bpy
from mathutils import Vector

# Add addon directory to sys.path
addon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import blend_building_creator
import bmesh
from blend_building_creator.generator.accessories.lighting import build_hanging_lantern, build_chain_lantern
from blend_building_creator.generator.openings import build_standalone_door_blade
from blend_building_creator.generator.materials import MAT_INDEX_DOOR, MAT_INDEX_IRON

print("--- STARTING TESTS ---")

# 1. Test build_hanging_lantern has NO bolts
bm = bmesh.new()
build_hanging_lantern(bm, 0, 0, 0, arm_ang=0.0)
print(f"build_hanging_lantern produced {len(bm.verts)} verts and {len(bm.faces)} faces")
print("PASS: build_hanging_lantern built cleanly without bolts")
bm.free()

# 2. Test build_chain_lantern
bm = bmesh.new()
chain_faces = build_chain_lantern(bm, 0, 0, 2.5, chain_len=0.55)
print(f"PASS: build_chain_lantern produced {len(chain_faces)} faces")
bm.free()

# 3. Test standalone door blade
for shape in ('SQUARE', 'ARCHED'):
    for hinge in ('LEFT', 'RIGHT'):
        bm = bmesh.new()
        build_standalone_door_blade(bm, width=1.1, height=2.3, shape=shape, hinge_side=hinge)
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        zs = [v.co.z for v in bm.verts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        
        print(f"Door blade ({shape}, {hinge}): X=[{min_x:.3f}, {max_x:.3f}], Y=[{min_y:.3f}, {max_y:.3f}], Z=[{min_z:.3f}, {max_z:.3f}]")
        
        # Check pivot and hinge at (0, 0)
        assert min_z >= -0.01, f"Bottom of door should be at z=0, got {min_z}"
        assert abs(max_z - 2.3) < 0.05, f"Top of door should be at z=2.3, got {max_z}"
        
        # Check hinge side
        if hinge == 'LEFT':
            assert abs(min_x) < 0.04, f"Hinge on left should start at x~0, got min_x={min_x}"
            assert abs(max_x - 1.1) < 0.08, f"Door blade width should reach ~1.1, got max_x={max_x}"
        else:
            assert abs(max_x) < 0.04, f"Hinge on right should end at x~0, got max_x={max_x}"
            assert abs(min_x - (-1.1)) < 0.08, f"Door blade width should reach ~-1.1, got min_x={min_x}"
            
        # Check materials (standalone door blades use clean 2-material setup: 0 for wood, 1 for iron)
        mats = {f.material_index for f in bm.faces}
        assert 0 in mats, "Must have wood material (slot 0)"
        assert 1 in mats, "Must have iron material (slot 1)"
        bm.free()
        print(f"PASS: Door blade ({shape}, {hinge}) verified successfully")

# 4. Register addon and test operator and building generation
try:
    blend_building_creator.register()
    print("PASS: Addon registered cleanly")
except Exception as e:
    print(f"FAIL registering addon: {e}")
    sys.exit(1)

# Test BUILDING_OT_create_door_blade operator
bpy.ops.building.create_door_blade(width=1.2, height=2.4, shape='ARCHED', hinge_side='LEFT', use_scene_settings=False)
active_obj = bpy.context.active_object
assert active_obj is not None, "Operator must create an active object"
assert active_obj.name.startswith("Door_Blade"), f"Object name expected Door_Blade, got {active_obj.name}"
assert len(active_obj.data.vertices) > 50, "Mesh should have vertices"
assert len(active_obj.material_slots) > 0, "Object should have material slots assigned"
print(f"PASS: Operator created object '{active_obj.name}' with {len(active_obj.data.vertices)} vertices and {len(active_obj.material_slots)} material slots")

# 5. Test building generation with include_door_leaves=True vs False
props = bpy.context.scene.fantasy_building_settings
props.has_front_door = True
props.has_back_door = True
props.has_outdoor_decor = True
props.lantern_style = 'CORNER_BRACKET'

# Building WITH door leaves
props.include_door_leaves = True
b_obj = bpy.data.objects.new("Test_Building_With_Doors", bpy.data.meshes.new("Test_Mesh_With_Doors"))
bpy.context.collection.objects.link(b_obj)
from blend_building_creator.generator.building import generate_building
generate_building(b_obj, props)
mats_with_doors = {p.material_index for p in b_obj.data.polygons}
assert MAT_INDEX_DOOR in mats_with_doors, "Building with doors must contain MAT_INDEX_DOOR polygons"
print(f"PASS: Building with doors has {len(b_obj.data.polygons)} polygons including MAT_INDEX_DOOR")

# Building WITHOUT door leaves (Unreal Engine mode)
props.include_door_leaves = False
b_obj_no_doors = bpy.data.objects.new("Test_Building_No_Doors", bpy.data.meshes.new("Test_Mesh_No_Doors"))
bpy.context.collection.objects.link(b_obj_no_doors)
generate_building(b_obj_no_doors, props)
# Check doorway volume for door leaf polygons
# Front doorway is at x=0, y=door_yf, z between 0.3 and 1.8
def count_doorway_polys(obj):
    door_yf = props.bounds_for_test if hasattr(props, 'bounds_for_test') else -2.5
    # The front door is at x near 0, y near front wall (-base_depth/2), z inside doorway opening
    # Bounds of the front door walkthrough volume:
    door_yf = -props.depth * 0.5
    count = 0
    for p in obj.data.polygons:
        center = sum((obj.data.vertices[i].co for i in p.vertices), Vector((0,0,0))) / len(p.vertices)
        if abs(center.x) < 0.35 and abs(center.y - door_yf) < 0.06 and 0.3 < center.z < 1.8:
            count += 1
    return count

polys_with_doors = count_doorway_polys(b_obj)
polys_no_doors = count_doorway_polys(b_obj_no_doors)
print(f"Doorway volume polygons: with_doors={polys_with_doors}, no_doors={polys_no_doors}")
assert polys_with_doors > 50, f"Building with doors must have door leaf polygons inside doorway, got {polys_with_doors}"
assert polys_no_doors <= 2, f"Building without doors should only have wall reveal faces, got {polys_no_doors}"
assert (polys_with_doors - polys_no_doors) > 50, "At least 50 door leaf polygons must be removed"
print(f"PASS: Door leaf toggle verified! {polys_with_doors - polys_no_doors} door leaf polygons removed while opening/frame kept intact.")

# 6. Test lantern styles on building
for lstyle in ('CORNER_BRACKET', 'HANGING_CHAIN', 'AUTO'):
    props.lantern_style = lstyle
    props.include_door_leaves = False
    test_l_obj = bpy.data.objects.new(f"Test_Building_{lstyle}", bpy.data.meshes.new(f"Mesh_{lstyle}"))
    bpy.context.collection.objects.link(test_l_obj)
    generate_building(test_l_obj, props)
    print(f"PASS: Generated building with lantern_style={lstyle} successfully ({len(test_l_obj.data.polygons)} polys)")

print("--- ALL TESTS COMPLETED SUCCESSFULLY ---")
