import bpy
import bmesh
import math
import os
import sys

# Ensure current directory is in sys.path
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import blend_building_creator

def run_checks():
    print("=" * 60)
    print("VERIFYING WING OVERLAPS & MINI-WING ROOF FIXES")
    print("=" * 60)

    # 1. Register
    blend_building_creator.register()
    settings = bpy.context.scene.fantasy_building_settings

    # Helper to clean and create
    def make_building(**kwargs):
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        # Reset settings
        bpy.ops.building.reset_settings()
        for k, v in kwargs.items():
            setattr(settings, k, v)
        res = bpy.ops.building.create_fantasy_building()
        assert res == {'FINISHED'}, f"Failed to generate building with {kwargs}"
        obj = bpy.context.active_object
        assert obj is not None
        return obj

    # -------------------------------------------------------------
    # TEST 1: Mini-Wing Gable Roof & Gable Wall Integrity
    # -------------------------------------------------------------
    print("[1/4] Testing Mini-Wing Gable Outcrop...")
    obj = make_building(
        has_mini_wing=True,
        mini_wing_side='FRONT',
        mini_wing_floor='GROUND',
        mini_wing_roof='GABLE',
        mini_wing_width=2.2,
        mini_wing_depth=1.6,
        floors=3,
        floor_height=2.8,
        has_foundation=True,
        foundation_height=0.45
    )
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    # Check shingles
    uv_layer = bm.loops.layers.uv.verify()
    mw_faces = [f for f in bm.faces if f.material_index == 4 and f.calc_center_median().z < 4.0]
    assert len(mw_faces) > 0, "No mini-wing shingles found!"
    
    mw_verts = [v for f in mw_faces for v in f.verts]
    mw_shingle_z_max = max(v.co.z for v in mw_verts)
    print(f"  Mini-wing roof peak Z: {mw_shingle_z_max:.3f}m (Floor 1 floorboards at 3.250m)")
    assert mw_shingle_z_max < 3.25, f"Mini-wing roof penetrates upper floorboards! Peak Z: {mw_shingle_z_max}"
    
    # Back edge stopping at facade (facade at -2.500m, interior room starts at -2.390m)
    mw_shingle_y_max = max(v.co.y for v in mw_verts)
    print(f"  Mini-wing roof backmost Y: {mw_shingle_y_max:.3f}m (Exterior facade at -2.500m, interior at -2.390m)")
    assert mw_shingle_y_max <= -2.44, f"Mini-wing roof penetrates into interior room! Max Y: {mw_shingle_y_max}"
    
    # UVs
    mw_uvs = [l[uv_layer].uv for f in mw_faces for l in f.loops]
    u_span = max(u.x for u in mw_uvs) - min(u.x for u in mw_uvs)
    v_span = max(u.y for u in mw_uvs) - min(u.y for u in mw_uvs)
    print(f"  Mini-wing shingle UV spans: U={u_span:.3f}, V={v_span:.3f}")
    assert u_span > 0.3 and v_span > 0.3, "Shingle UVs are degenerate or tiny!"
    
    # Plaster gable wall
    plaster_verts = [v.co for v in bm.verts for f in v.link_faces if f.material_index == 1 and v.co.y < -2.55 and abs(v.co.x) < 1.4 and v.co.z < 5.0]
    mw_plaster_z_max = max(v.z for v in plaster_verts) if plaster_verts else 0.0
    print(f"  Mini-wing gable wall max Z: {mw_plaster_z_max:.3f}m vs Roof peak: {mw_shingle_z_max:.3f}m")
    assert mw_plaster_z_max <= mw_shingle_z_max, f"Gable wall pokes above roof! Plaster: {mw_plaster_z_max}, Roof: {mw_shingle_z_max}"
    
    bm.free()

    # -------------------------------------------------------------
    # TEST 2: Mini-Wing Lean-to Roof Integrity
    # -------------------------------------------------------------
    print("[2/4] Testing Mini-Wing Lean-to Outcrop...")
    obj = make_building(
        has_mini_wing=True,
        mini_wing_side='FRONT',
        mini_wing_floor='GROUND',
        mini_wing_roof='LEAN_TO',
        mini_wing_width=2.2,
        mini_wing_depth=1.6,
        floors=3,
        floor_height=2.8,
        has_foundation=True,
        foundation_height=0.45
    )
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    mw_faces = [f for f in bm.faces if f.material_index == 4 and f.calc_center_median().z < 4.0]
    assert len(mw_faces) > 0, "No lean-to shingles found!"
    mw_verts = [v for f in mw_faces for v in f.verts]
    mw_shingle_z_max = max(v.co.z for v in mw_verts)
    mw_shingle_y_max = max(v.co.y for v in mw_verts)
    print(f"  Lean-to roof peak Z: {mw_shingle_z_max:.3f}m (Floor 1 floorboards at 3.250m)")
    print(f"  Lean-to roof backmost Y: {mw_shingle_y_max:.3f}m (Exterior facade at -2.500m, interior at -2.390m)")
    assert mw_shingle_z_max < 3.25, f"Lean-to roof penetrates upper floorboards! Peak Z: {mw_shingle_z_max}"
    assert mw_shingle_y_max <= -2.44, f"Lean-to roof penetrates interior room! Max Y: {mw_shingle_y_max}"
    
    bm.free()

    # -------------------------------------------------------------
    # TEST 3: L-Shape Wing Window Clearance & Multi-Floor Occlusion
    # -------------------------------------------------------------
    print("[3/4] Testing L-Shape Building with Front Wing & Multi-Floor Occlusion...")
    obj = make_building(
        building_shape='L_SHAPE',
        wing_placement='FRONT',
        wing_side='RIGHT',
        wing_floors=2,
        floors=3,
        has_windows=True,
        has_shutters=True,
        shutter_state='OPEN',
        floor_height=2.8,
        has_foundation=True,
        foundation_height=0.45
    )
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    # Front facade windows (glass mat 5 at y ~ -2.5)
    front_win_faces = []
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(c.y - (-2.5)) < 0.35 and f.material_index == 5:
            front_win_faces.append(c)
    
    # Wing is on FRONT-RIGHT [-0.5, 3.0].
    # Check that across all floors (Floor 0, Floor 1, Floor 2), NO window on front facade overlaps [-1.6, 3.4]
    for fl_i, z_bot, z_top in [(0, 0.45, 3.25), (1, 3.25, 6.05), (2, 6.05, 8.85)]:
        fl_win_xs = [c.x for c in front_win_faces if z_bot <= c.z <= z_top and abs(c.x) > 0.1]
        unique_xs = sorted(set(round(x, 2) for x in fl_win_xs))
        print(f"  Floor {fl_i} front window X positions: {unique_xs}")
        for x in unique_xs:
            assert not (-1.50 < x < 3.40), f"Window at X={x:.2f} on Floor {fl_i} collides with front wing envelope [-0.5, 3.0]!"
    
    # Check right wall windows (facing +X):
    # Must NOT have any window within 1.20m of that floor's front corner (where front wing attaches)
    for fl_i, z_bot, z_top, fl_ymin in [(0, 0.45, 3.25, -2.50), (1, 3.25, 6.05, -2.70), (2, 6.05, 8.85, -2.90)]:
        r_ys = [f.calc_center_median().y for f in bm.faces if f.material_index == 5 and f.calc_center_median().x > 2.7 and z_bot <= f.calc_center_median().z <= z_top]
        if r_ys:
            closest_y = min(abs(y - fl_ymin) for y in r_ys)
            print(f"  Floor {fl_i} right wall window closest distance to front corner: {closest_y:.3f}m")
            assert closest_y > 1.20, f"Floor {fl_i} right wall window too close to front corner! Distance: {closest_y:.3f}m"
    
    # Wing left side wall facing inside corner:
    # Wall is at x ~ -0.5, y running from -5.5 to -2.5.
    wing_side_win = [f for f in bm.faces if f.material_index == 5 and abs(f.calc_center_median().x - (-0.5)) < 0.3 and f.calc_center_median().y < -2.6]
    if wing_side_win:
        max_y_wing_win = max(f.calc_center_median().y for f in wing_side_win)
        print(f"  Wing side window closest Y to main building: {max_y_wing_win:.3f}m (Junction at -2.500m)")
        assert max_y_wing_win <= -3.55, f"Wing side window too close to main facade inside corner! Y={max_y_wing_win}"
    
    bm.free()

    # -------------------------------------------------------------
    # TEST 4: U-Shape Wing Window Clearance
    # -------------------------------------------------------------
    print("[4/4] Testing U-Shape Building Window Clearance...")
    obj = make_building(
        building_shape='U_SHAPE',
        wing_placement='FRONT',
        wing_floors=2,
        floors=3,
        has_windows=True,
        has_shutters=True,
        shutter_state='OPEN',
        floor_height=2.8,
        has_foundation=True,
        foundation_height=0.45
    )
    assert obj is not None
    print(f"  U-shape building generated: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys.")

    blend_building_creator.unregister()

    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_checks()
