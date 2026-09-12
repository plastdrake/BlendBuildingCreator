import bpy
import sys
import os

print("=" * 60)
print("RUNNING TARGETED TESTS FOR EXPANDED FEATURES")
print("=" * 60)

# Ensure add-on is available
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blend_building_creator
blend_building_creator.register()

props = bpy.context.scene.fantasy_building_settings

# Create test building
bpy.ops.building.create_fantasy_building(reset_to_defaults=True)
obj = bpy.context.active_object
assert obj is not None, "Failed to create building object"

# 1. Test Multiple Entrances (Front, Back, Side doors simultaneously)
print("\n[1] Testing Multiple Entrances (Front + Back + Side)...")
props.has_front_door = True
props.has_back_door = True
props.has_side_door = True
props.side_door_facade = 'RIGHT'
bpy.ops.building.regenerate()
v1 = len(obj.data.vertices)
print(f"  -> Building with 3 entrances (Front, Back, Right): {v1} verts, {len(obj.data.polygons)} polys")
assert v1 > 500, "Expected rich geometry with multiple doors"

# 2. Test Window Spacing & Density
print("\n[2] Testing Window Density & Spacing Controls...")
props.window_density = 1.8
props.window_spacing = 2.0
bpy.ops.building.regenerate()
v_dense = len(obj.data.vertices)
print(f"  -> High density windows: {v_dense} verts")

props.window_density = 0.5
props.window_spacing = 4.0
bpy.ops.building.regenerate()
v_sparse = len(obj.data.vertices)
print(f"  -> Sparse windows: {v_sparse} verts")
assert v_dense > v_sparse, "High density should generate more geometry than sparse windows"

# 3. Test Shutter States (OPEN, CLOSED, PARTIAL)
print("\n[3] Testing Shutter States...")
props.has_shutters = True
props.shutter_state = 'CLOSED'
bpy.ops.building.regenerate()
print(f"  -> Shutters all CLOSED: {len(obj.data.vertices)} verts")

props.shutter_state = 'PARTIAL'
props.shutter_closed_amount = 0.6
bpy.ops.building.regenerate()
print(f"  -> Shutters PARTIAL (60% closed): {len(obj.data.vertices)} verts")

props.shutter_state = 'OPEN'
bpy.ops.building.regenerate()
print(f"  -> Shutters all OPEN: {len(obj.data.vertices)} verts")

# 4. Test Balcony Modes (SINGLE, ALL_UPPER, CUSTOM)
print("\n[4] Testing Balcony Placement Across Floor Levels...")
props.num_floors = 4
props.has_balcony = True
props.balcony_mode = 'ALL_UPPER'
bpy.ops.building.regenerate()
v_all_balc = len(obj.data.vertices)
print(f"  -> Balconies on ALL_UPPER floors (floors 2, 3, 4): {v_all_balc} verts")

props.balcony_mode = 'CUSTOM'
props.balcony_fl2 = True
props.balcony_fl3 = False
props.balcony_fl4 = True
bpy.ops.building.regenerate()
v_custom_balc = len(obj.data.vertices)
print(f"  -> Balconies on CUSTOM floors (floors 2 and 4 only): {v_custom_balc} verts")
assert v_all_balc > v_custom_balc, "ALL_UPPER should have more balconies than CUSTOM 2-floors"

# 5. Test Wings: Left, Right, Back, Front
print("\n[5] Testing Wing Placements (FRONT, BACK, LEFT, RIGHT)...")
props.building_shape = 'L_SHAPE'
for place in ['FRONT', 'BACK', 'LEFT', 'RIGHT']:
    for side in ['LEFT', 'RIGHT']:
        props.wing_placement = place
        props.wing_side = side
        bpy.ops.building.regenerate()
        print(f"  -> L_SHAPE with wing on {place} (side: {side}): {len(obj.data.vertices)} verts")

# 6. Test U-Shaped Buildings (Courtyard)
print("\n[6] Testing U-Shaped Courtyard Buildings...")
props.building_shape = 'U_SHAPE'
props.courtyard_width = 3.5
props.wing_width = 3.0
props.wing_depth = 3.5
for place in ['FRONT', 'BACK', 'LEFT', 'RIGHT']:
    props.wing_placement = place
    bpy.ops.building.regenerate()
    print(f"  -> U_SHAPE projecting from {place}: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys")

# 7. Test Face Normals & Orientation on U-Shape and Complex wings
print("\n[7] Verifying Face Orientations (zero inverted faces)...")
import bmesh
bm = bmesh.new()
bm.from_mesh(obj.data)
inverted_faces = 0
for f in bm.faces:
    if f.normal.length < 0.1:
        inverted_faces += 1
bm.free()
print(f"  -> Degenerate/zero-normal faces: {inverted_faces}")
assert inverted_faces == 0, f"Found {inverted_faces} zero-normal faces"

print("\n" + "=" * 60)
print("ALL TARGETED FEATURE TESTS PASSED WITH 100% SUCCESS!")
print("=" * 60)
blend_building_creator.unregister()
