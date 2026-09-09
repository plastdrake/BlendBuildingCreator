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
    assert m_count == 9, f"Expected 9 material slots, got {m_count}"
    
    # 3. Test Interior Floor and Door Angle
    print("[3/6] Testing door toggle & walk-in interior...")
    props = bpy.context.scene.fantasy_building_settings
    initial_angle = props.door_angle
    bpy.ops.building.toggle_door()
    print(f"  -> Toggled door angle from {initial_angle} to {props.door_angle}")
    assert props.door_angle != initial_angle, "Door toggle did not alter angle!"
    
    # Test Spiral staircase on 3 floors
    props.num_floors = 3
    props.stair_style = 'SPIRAL'
    bpy.ops.building.regenerate()
    print(f"  -> 3-floor building with spiral stairs: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys.")

    # 4. Test Presets
    print("[4/6] Testing style presets...")
    for preset_key in ['TAVERN', 'WIZARD_TOWER', 'COTTAGE', 'TOWNHOUSE']:
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

    # Save verification blend file
    output_blend = os.path.join(addon_dir, "test_output.blend")
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"  -> Saved test scene to: {output_blend}")

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
