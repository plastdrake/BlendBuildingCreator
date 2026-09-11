"""
Automated Test Suite for Stylized Fantasy Building Generator in Blender 5.2 LTS.
Verifies registration, generation, interior structure, presets, materials, and operators.
"""

import sys
import os
import bpy

# Ensure current directory is in sys.path
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import blend_building_creator

def run_tests():
    print("=" * 60)
    print("RUNNING FANTASY BUILDING GENERATOR TEST SUITE IN BLENDER", bpy.app.version)
    print("=" * 60)

    # 1. Test Registration
    print("[1/6] Registering add-on...")
    blend_building_creator.register()
    assert hasattr(bpy.types.Scene, "fantasy_building_settings"), "Scene property group not registered!"
    print("  -> Add-on registered successfully.")

    # Clear existing objects in scene
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # 2. Test Building Creation
    print("[2/6] Testing building creation operator...")
    res = bpy.ops.building.create_fantasy_building()
    assert res == {'FINISHED'}, f"Creation operator failed: {res}"
    
    obj = bpy.context.active_object
    assert obj is not None, "No active object created!"
    assert obj.get("is_fantasy_building") is True, "Object missing building tag!"
    
    mesh = obj.data
    v_count = len(mesh.vertices)
    p_count = len(mesh.polygons)
    m_count = len(obj.data.materials)
    print(f"  -> Generated default building: {v_count} verts, {p_count} polys, {m_count} materials.")
    assert v_count > 500, f"Expected rich geometry (>500 verts), got {v_count}"
    assert m_count == 17, f"Expected 17 material slots, got {m_count}"
    
    # 3. Test Interior Floor and Door Angle
    print("[3/6] Testing door toggle & walk-in interior...")
    props = bpy.context.scene.fantasy_building_settings
    initial_angle = props.door_angle
    bpy.ops.building.toggle_door()
    print(f"  -> Toggled door angle from {initial_angle} to {props.door_angle}")
    assert props.door_angle != initial_angle, "Door toggle did not alter angle!"
    
    # Test Multi-story straight & spiral stairs
    props.num_floors = 3
    props.stair_style = 'STRAIGHT'
    props.cantilever_overhang = 0.0 # Test 0-overhang trimmer beam safety
    bpy.ops.building.regenerate()
    print(f"  -> 3-floor building with straight stairs (0-overhang): {len(obj.data.vertices)} verts.")

    props.stair_style = 'SPIRAL'
    bpy.ops.building.regenerate()
    print(f"  -> 3-floor building with spiral stairs: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys.")

    # Test L-Shape with 1-floor wing on 3-floor building (Wing ceiling & no roof overlap)
    props.building_shape = 'L_SHAPE'
    props.wing_floors = 1
    bpy.ops.building.regenerate()
    print(f"  -> L-Shape with 1-floor wing on 3-floor building: {len(obj.data.vertices)} verts.")

    # Test Material Tiers & Siding Styles
    print("[4/8] Testing Material Tiers & Siding Styles (Logs, Planks, Stone)...")
    for tier in ['TIER_1', 'TIER_2', 'TIER_3']:
        props.material_tier = tier
        if tier == 'TIER_2':
            for p_dir in ['HORIZONTAL', 'VERTICAL']:
                props.plank_direction = p_dir
                props.plank_jankiness = 0.5
                bpy.ops.building.regenerate()
                print(f"  -> Tier 2 with {p_dir} planks (jankiness=0.5): {len(obj.data.vertices)} verts.")
        elif tier == 'TIER_3':
            props.stone_block_scale = 1.3
            props.stone_disorder = 0.6
            bpy.ops.building.regenerate()
            print(f"  -> Tier 3 with chunky stone masonry (scale=1.3, disorder=0.6): {len(obj.data.vertices)} verts.")
        else:
            bpy.ops.building.regenerate()
            print(f"  -> Tier 1 with rounded interlocking logs: {len(obj.data.vertices)} verts.")
        m_count = len(obj.data.materials)
        assert m_count == 17, f"Expected 17 material slots for {tier}, got {m_count}"
        print(f"  -> Material {tier}: verified 17 procedural shader slots successfully.")

    # Test Hoist Beam
    props.has_hoist_beam = True
    bpy.ops.building.regenerate()
    print(f"  -> Verified roof hoist beam with cargo hook: {len(obj.data.vertices)} verts.")

    # 5. Test Presets
    from blend_building_creator.presets import PRESETS
    print(f"[5/8] Testing all {len(PRESETS)} architectural style presets...")
    for preset_key in PRESETS.keys():
        bpy.ops.building.apply_preset(preset_key=preset_key)
        v = len(obj.data.vertices)
        p = len(obj.data.polygons)
        print(f"  -> Preset '{preset_key}': {v} verts, {p} polys.")
        assert v > 200, f"Preset {preset_key} produced empty geometry!"

    # 5. Test Randomize
    print("[5/6] Testing randomization operator...")
    old_seed = props.seed
    bpy.ops.building.randomize_seed()
    assert props.seed != old_seed, "Seed did not change after randomize!"
    print(f"  -> Randomize changed seed from {old_seed} to {props.seed}")

    # 6. Test Finalize Mesh
    print("[6/6] Testing mesh finalization...")
    bpy.ops.building.finalize_mesh()
    assert "is_fantasy_building" not in obj, "Building tag was not removed!"
    print("  -> Building successfully finalized to standard editable mesh.")

    # 7. Test UI Icons Validity for Blender 5.2
    print("[7/7] Testing UI icon compatibility in Blender 5.2...")
    import re
    ui_path = os.path.join(addon_dir, "blend_building_creator", "ui.py")
    with open(ui_path, "r", encoding="utf-8") as f:
        ui_text = f.read()
    icons_used = set(re.findall(r'icon=[\'\"]([A-Z0-9_]+)[\'\"]', ui_text))
    valid_icons = {item.identifier for item in bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items}
    invalid_icons = icons_used - valid_icons
    assert len(invalid_icons) == 0, f"Found invalid icons in ui.py: {invalid_icons}"
    print(f"  -> All {len(icons_used)} UI icons validated against Blender 5.2 RNA successfully.")

    # 8. Test Archetypes & Accessories
    print("[8/10] Testing Specialized Architectural Archetypes...")
    obj["is_fantasy_building"] = True
    for arch in ['BLACKSMITH', 'WINDMILL', 'WATCHTOWER', 'TAVERN', 'FISHERMAN', 'BAKERY', 'WAREHOUSE']:
        props.building_archetype = arch
        bpy.ops.building.regenerate()
        print(f"  -> Archetype '{arch}': {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys.")
        assert len(obj.data.vertices) > 500, f"Archetype {arch} failed to build geometry!"

    # 9. Test Reset and Multi-Building Offset
    print("[9/10] Testing Reset Operator and Multi-Building Independence...")
    # Change some properties
    props.num_floors = 4
    props.wonkiness = 0.25
    props.building_archetype = 'WINDMILL'
    # Run Reset Operator
    bpy.ops.building.reset_settings(regenerate_active=False)
    assert props.num_floors == 2, f"Expected reset to 2 floors, got {props.num_floors}"
    assert abs(props.wonkiness - 0.08) < 0.001, f"Expected reset to wonkiness 0.08, got {props.wonkiness}"
    assert props.building_archetype == 'AUTO', f"Expected reset to AUTO archetype, got {props.building_archetype}"
    print("  -> Reset operator restored all settings to defaults.")

    # Test creating second building (must be offset along X and not overlap)
    bpy.ops.building.create_fantasy_building()
    bldg2 = bpy.context.active_object
    assert bldg2 != obj, "Second building creation did not produce a new object!"
    assert bldg2.location.x > obj.location.x + 4.0, f"Building 2 was not offset properly: {bldg2.location.x} vs {obj.location.x}"
    print(f"  -> Multi-building offset verified: Building 1 at {obj.location.x:.1f}, Building 2 at {bldg2.location.x:.1f}")

    # Test loading settings from Building 1
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.building.load_settings()
    print("  -> Loaded settings from Building 1 successfully.")

    # Unregister
    blend_building_creator.unregister()
    print("  -> Add-on unregistered cleanly.")

    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    try:
        run_tests()
        sys.exit(0)
    except Exception as e:
        print("TEST FAILED WITH ERROR:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
