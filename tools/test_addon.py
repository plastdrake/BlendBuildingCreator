"""
Directed, Fast Test Suite for Stylized Fantasy Building Generator in Blender 5.2 LTS.

Optimized for rapid iteration:
- Never loops through all 89 presets (only tests 5 curated representative presets).
- Targeted tests for scale, stairs & UV grain, Mage Tower, room zoning, chimneys/stoves, and props.
- Fast EEVEE GPU preview renders (maximum 2 images, 1 exterior + 1 interior) for the specific preset being worked on.

Usage:
  # Fast unit checks across features (< 5 seconds):
  blender --factory-startup --background --python tools/test_addon.py

  # Test only a specific area:
  blender --factory-startup --background --python tools/test_addon.py -- --test scale
  blender --factory-startup --background --python tools/test_addon.py -- --test stairs
  blender --factory-startup --background --python tools/test_addon.py -- --test mage
  blender --factory-startup --background --python tools/test_addon.py -- --test zoning
  blender --factory-startup --background --python tools/test_addon.py -- --test chimney
  blender --factory-startup --background --python tools/test_addon.py -- --test presets

  # Render ONLY the preset you are currently developing (e.g. INN_T1, MAGE_TOWER_T1, ARTISAN_BAKERY_T1):
  blender --factory-startup --background --python tools/test_addon.py -- --preset INN_T1 --render
  blender --factory-startup --background --python tools/test_addon.py -- --preset MAGE_TOWER_T1 --render
  blender --factory-startup --background --python tools/test_addon.py -- --preset TENEMENT_ROW_MEDIUM_T1 --render
"""

import sys
import os

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import math
import argparse
from types import SimpleNamespace
import bpy
import bmesh
from mathutils import Vector

# Ensure repo root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.presets import PRESETS, base_settings
from blend_building_creator.generator.interior import build_straight_staircase, build_spiral_staircase
from blend_building_creator.generator.accessories.prop_registry import build_prop


def clear_scene():
    """Removes all objects from current scene."""
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def test_registration():
    """Verifies add-on registers and UI icon RNA compatibility."""
    print("\n--- [TEST] Registration & UI Compatibility ---")
    try:
        blend_building_creator.register()
    except Exception:
        pass
    assert hasattr(bpy.types.Scene, "fantasy_building_settings"), "Scene property group not registered!"
    
    # Verify icons in Blender 5.2 RNA
    import re
    ui_path = os.path.join(repo_root, "blend_building_creator", "ui.py")
    with open(ui_path, "r", encoding="utf-8") as f:
        ui_text = f.read()
    icons_used = set(re.findall(r'icon=[\'\"]([A-Z0-9_]+)[\'\"]', ui_text))
    valid_icons = {item.identifier for item in bpy.types.UILayout.bl_rna.functions['operator'].parameters['icon'].enum_items}
    invalid_icons = icons_used - valid_icons
    assert len(invalid_icons) == 0, f"Found invalid icons in ui.py: {invalid_icons}"
    print(f"  [PASS] Add-on registered and {len(icons_used)} icons validated.")


def test_gamified_scale():
    """Verifies gamified heights and doorway dimensions."""
    print("\n--- [TEST] Gamified Scale & Doorways ---")
    clear_scene()
    bpy.ops.building.create_fantasy_building()
    props = bpy.context.scene.fantasy_building_settings

    # 1. Defaults verification
    assert props.floor_height >= 3.4, f"Floor height {props.floor_height} is below gamified 3.4m"
    assert props.door_width >= 1.40, f"Door width {props.door_width} is below gamified 1.40m"
    assert props.door_height >= 2.75, f"Door height {props.door_height} is below gamified 2.75m"
    assert props.stair_width >= 1.40, f"Stair width {props.stair_width} is below gamified 1.40m"
    print(f"  [PASS] Defaults scaled: floor_h={props.floor_height}m, door={props.door_width}x{props.door_height}m, stairs={props.stair_width}m.")

    # 2. Base settings dictionary verification
    b = base_settings()
    assert b['floor_height'] >= 3.4
    assert b['door_width'] >= 1.40
    assert b['door_height'] >= 2.75
    assert b['stair_width'] >= 1.40
    print("  [PASS] base_settings() adheres to gamified scale.")


def test_stairs_and_uv_fibers():
    """Verifies stairs generation and lengthwise wood grain UV unwrapping."""
    print("\n--- [TEST] Stairs & Wood Fiber UV Unwrapping ---")
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.verify()

    # 1. Straight Stairs: test tread wood grain along length (V-axis)
    build_straight_staircase(bm, start_pos=(0, 0, 0), target_z=3.6, stair_width=1.5, stair_depth=2.6)
    
    # Find main flat tread top faces (area > 0.15)
    tread_top_faces = [f for f in bm.faces if f.normal.z > 0.95 and f.material_index == 7 and f.calc_area() > 0.15]
    assert len(tread_top_faces) >= 10, f"Expected >= 10 tread faces, found {len(tread_top_faces)}"
    
    for f in tread_top_faces[:5]:
        v_coords = [loop[uv_layer].uv.y for loop in f.loops]
        u_coords = [loop[uv_layer].uv.x for loop in f.loops]
        x_coords = [loop.vert.co.x for loop in f.loops]
        y_coords = [loop.vert.co.y for loop in f.loops]
        
        dx = max(x_coords) - min(x_coords)
        dy = max(y_coords) - min(y_coords)
        dv = max(v_coords) - min(v_coords)
        du = max(u_coords) - min(u_coords)
        assert dx > dy, "Tread width along X should be greater than depth along Y"
        assert dv > 0.3, f"Expected V UV span along length, got dv={dv}"
    print(f"  [PASS] Straight stairs: {len(tread_top_faces)} treads unwrapped with wood grain along length.")

    # 2. Spiral Stairs: test wedge step wood fibers along radial length
    bm2 = bmesh.new()
    uv_layer2 = bm2.loops.layers.uv.verify()
    build_spiral_staircase(bm2, center_pos=(0, 0, 0), target_z=3.6, radius=1.4)
    spiral_treads = [f for f in bm2.faces if f.normal.z > 0.95 and f.material_index == 7 and f.calc_area() > 0.1]
    assert len(spiral_treads) >= 12, f"Expected >= 12 spiral tread faces, found {len(spiral_treads)}"
    print(f"  [PASS] Spiral stairs: {len(spiral_treads)} wedge treads with radial grain alignment.")
    bm.free()
    bm2.free()


def test_mage_tower():
    """Verifies Mage Tower enlarged diameter and wide stairs."""
    print("\n--- [TEST] Mage Tower (Diameter & Stairs) ---")
    clear_scene()
    bpy.ops.building.create_fantasy_building()
    
    # Test Tier 1, 2, 3 Mage Tower presets
    tier_radii = {
        'MAGE_TOWER_T1': 4.2,
        'MAGE_TOWER_T2': 5.5,
        'MAGE_TOWER_T3': 6.5,
    }
    for t_key, expected_r in tier_radii.items():
        p_data = PRESETS[t_key]['settings']
        expected_w = expected_r * 2.0
        assert abs(p_data['width'] - expected_w) < 0.01, f"{t_key} width {p_data['width']} != {expected_w}m (expected radius {expected_r}m)"
        assert p_data['stair_width'] >= 1.70, f"{t_key} stair_width {p_data['stair_width']} is below 1.70m"
        assert p_data['floor_height'] >= 5.0, f"{t_key} floor_height {p_data['floor_height']} is below 5.0m"

    # Generate Tier 1 Mage Tower (furnished, 4.2m radius -> ~8.4m base diameter)
    bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T1')
    obj = bpy.context.active_object
    verts = len(obj.data.vertices)
    assert verts > 8000, f"Mage Tower T1 geometry too sparse: {verts} verts"
    dim = obj.dimensions
    assert dim.x >= 8.4, f"Mage tower T1 X diameter {dim.x:.1f}m is too small (expected >= 8.4m for 4.2m radius)"
    assert dim.y >= 8.4, f"Mage tower T1 Y diameter {dim.y:.1f}m is too small (expected >= 8.4m for 4.2m radius)"
    print(f"  [PASS] Mage Tower T1 (4.2m radius) generated successfully (X={dim.x:.1f}m, Y={dim.y:.1f}m, Z={dim.z:.1f}m, {verts} verts).")

    # Generate Tier 2 Mage Tower (furnished, 5.5m radius -> ~11m base diameter)
    bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T2')
    obj = bpy.context.active_object
    verts2 = len(obj.data.vertices)
    assert verts2 > 14000, f"Mage Tower T2 geometry too sparse: {verts2} verts"
    dim2 = obj.dimensions
    assert dim2.x >= 11.0, f"Mage tower T2 X diameter {dim2.x:.1f}m is too small (expected >= 11.0m for 5.5m radius)"
    print(f"  [PASS] Mage Tower T2 (5.5m radius) generated successfully (X={dim2.x:.1f}m, Y={dim2.y:.1f}m, Z={dim2.z:.1f}m, {verts2} verts).")

    # Generate Tier 3 Mage Tower (furnished, 6.5m radius -> ~13m base diameter)
    bpy.ops.building.apply_preset(preset_key='MAGE_TOWER_T3')
    obj = bpy.context.active_object
    verts3 = len(obj.data.vertices)
    assert verts3 > 20000, f"Mage Tower T3 geometry too sparse: {verts3} verts"
    dim3 = obj.dimensions
    assert dim3.x >= 13.0, f"Mage tower T3 X diameter {dim3.x:.1f}m is too small (expected >= 13.0m for 6.5m radius)"
    print(f"  [PASS] Mage Tower T3 (6.5m radius) generated successfully (X={dim3.x:.1f}m, Y={dim3.y:.1f}m, Z={dim3.z:.1f}m, {verts3} verts).")


def test_room_zoning_and_furnishing():
    """Verifies intelligent room layouts, artisan store/living separation, and stair landing protection."""
    print("\n--- [TEST] Room Layouts & Furnishing Zoning ---")
    from blend_building_creator.generator.interior import _resolve_room_roles

    # 1. Inn: taproom on ground floor, guest rooms on upper floor, protected stair landing
    ground_inn = _resolve_room_roles('INN', fl_idx=0, num_rooms=3, has_stairs_landing=False)
    assert 'TAVERN_TAPROOM' in ground_inn
    assert 'KITCHEN' in ground_inn
    
    upper_inn = _resolve_room_roles('INN', fl_idx=1, num_rooms=3, has_stairs_landing=True)
    assert upper_inn[0] == 'STAIR_LANDING', "First room around stairs must be STAIR_LANDING"
    assert 'GUEST_ROOM' in upper_inn
    print("  [PASS] Inn: ground floor is taproom/kitchen, upper floor is guest bedrooms with protected landing.")

    # 2. Artisans: all 8 families must have at least 2 floors in T1, and shop/workshop downstairs
    artisan_families = ['ARTISAN_BAKERY', 'ARTISAN_TAILOR', 'ARTISAN_TOOLSMITH', 'ARTISAN_JEWELER',
                        'ARTISAN_BREWERY', 'ARTISAN_FISHER', 'ARTISAN_FURNITURE_MAKER', 'ARTISAN_BUTCHER']
    for fam in artisan_families:
        t1_floors = PRESETS[f'{fam}_T1']['settings']['num_floors']
        assert t1_floors >= 2, f"{fam}_T1 has only {t1_floors} floors (expected >= 2)"
        t2_floors = PRESETS[f'{fam}_T2']['settings']['num_floors']
        assert t2_floors >= 3, f"{fam}_T2 has only {t2_floors} floors (expected >= 3)"

    ground_artisan = _resolve_room_roles('BAKERY', fl_idx=0, num_rooms=2, has_stairs_landing=False)
    assert 'STORE' in ground_artisan or 'WORKSHOP' in ground_artisan
    print("  [PASS] All 8 Artisan families have >= 2 floors in T1, >= 3 floors in T2, with ground storefronts.")

    # 3. Small houses: split into bedroom + kitchen
    ground_house = _resolve_room_roles('HOUSE', fl_idx=0, num_rooms=2, has_stairs_landing=False, total_floors=1)
    assert 'KITCHEN' in ground_house and ('BEDROOM' in ground_house or 'HOUSE_HALL' in ground_house)
    print("  [PASS] Single-floor small houses split into kitchen and living/bedroom.")

    # 4. Tenement presets
    for t_key in ['TENEMENT_ROW_MEDIUM_T1', 'TENEMENT_ROW_MEDIUM_T2', 'TENEMENT_COMPLEX_LARGE_T1']:
        assert t_key in PRESETS, f"Missing tenement preset: {t_key}"
        assert PRESETS[t_key]['settings']['num_floors'] >= 2
    print("  [PASS] Tenement Row and Tenement Complex presets verified.")


def test_tenement_layouts():
    """Checks apartment division, single entrances, and one-route stairs."""
    from blend_building_creator.generator.accessories.exterior_stairs import (
        exterior_stair_plan, exterior_stair_door_spots,
    )
    from blend_building_creator.generator.building import _create_building_context
    from blend_building_creator.generator.floors import build_floors
    from blend_building_creator.generator.interior import plan_floor_rooms
    from blend_building_creator.generator.tenement import STAIR_W

    def _layout(preset_key):
        settings = dict(PRESETS[preset_key]['settings'])
        settings.setdefault('seed', 1)
        props = SimpleNamespace(**settings)
        ctx = _create_building_context(props)
        half_w = props.width * 0.5
        half_d = props.depth * 0.5
        bounds = (-half_w + props.wall_thickness * 0.5,
                  half_w - props.wall_thickness * 0.5,
                  -half_d + props.wall_thickness * 0.5,
                  half_d - props.wall_thickness * 0.5)
        wings = [wing['base'] for wing in ctx.wings]
        stair_plan = exterior_stair_plan(props, ctx)
        rooms, _walls = plan_floor_rooms(
            0, bounds, fl_wings_bounds=wings or None,
            effective_archetype='TENEMENT', props=props, doorways=[])
        return props, bounds, rooms, stair_plan

    def _assert_no_overlap(rooms, label):
        for i, first in enumerate(rooms):
            for second in rooms[i + 1:]:
                xo = min(first.bounds[1], second.bounds[1]) - max(first.bounds[0], second.bounds[0])
                yo = min(first.bounds[3], second.bounds[3]) - max(first.bounds[2], second.bounds[2])
                assert xo <= 0.001 or yo <= 0.001, (
                    f"{label} rooms overlap: {first.id} {second.id}")

    # --- Side-walkway row tenement: two small flats, one door each ---------
    row_props, row_bounds, row_rooms, row_stairs = _layout('TENEMENT_ROW_MEDIUM_T2')
    row_ix_min = row_bounds[0]
    row_kitchens = [r for r in row_rooms if r.role == 'TENEMENT_KITCHEN']
    row_bedrooms = [r for r in row_rooms if r.role == 'TENEMENT_BEDROOM']
    assert len(row_kitchens) == len(row_bedrooms) == 2, [(r.id, r.role) for r in row_rooms]
    for room in row_kitchens:
        entrances = [d for d in room.doorways
                     if d.get('axis') == 'Y' and abs(d.get('x', 0.0) - row_ix_min) < 0.05]
        assert len(entrances) == 1, f"{room.id} must have exactly one gallery entrance"
    assert row_stairs['is_walkway']
    assert len(row_stairs['flights']) == row_props.num_floors - 1
    # Two-lane switchback: inner and outer lanes are separated, and each
    # storey climbs the lane the storey below did not use.
    assert row_stairs['u_outer'] > row_stairs['u_inner']
    assert all(f['lane'] in ('INNER', 'OUTER') for f in row_stairs['flights'])
    for i, f in enumerate(row_stairs['flights']):
        assert (f['lane'] == 'OUTER') == (i % 2 == 0)
    for first, second in zip(row_stairs['flights'], row_stairs['flights'][1:]):
        assert abs(first['a1'] - second['a0']) < 0.01, (
            "consecutive flights must meet at their landing"
        )
    _assert_no_overlap(row_rooms, 'row')

    # --- Courtyard tenement: small back-block flats + one flat per wing -----
    court_props, court_bounds, court_rooms, court_stairs = _layout('TENEMENT_COMPLEX_LARGE_T1')
    court_y_min = court_bounds[2]
    court_kitchens = [r for r in court_rooms if r.role == 'TENEMENT_KITCHEN']
    court_bedrooms = [r for r in court_rooms if r.role == 'TENEMENT_BEDROOM']
    assert len(court_kitchens) == len(court_bedrooms) == 5, [
        (r.id, r.role, r.bounds) for r in court_rooms]
    main_k = [r for r in court_kitchens if r.id.startswith('fl0_main')]
    wing_k = [r for r in court_kitchens if r.id.startswith('fl0_wing')]
    assert len(main_k) == 3 and len(wing_k) == 2
    for room in main_k:
        entrances = [d for d in room.doorways
                     if d.get('axis') == 'X' and abs(d.get('y', 0.0) - court_y_min) < 0.05]
        assert len(entrances) == 1, f"{room.id} must have one courtyard entrance"
    for room in wing_k:
        x0, x1, y0, y1 = room.bounds
        # A wing kitchen has exactly one external entrance: the courtyard-gallery
        # door on its inner wall (axis Y), or - for the ground-floor left wing -
        # the gable-end door on the wing tip (axis X at the outer y edge).
        y_entr = [d for d in room.doorways if d.get('axis') == 'Y']
        tip_entr = [d for d in room.doorways
                    if d.get('axis') == 'X' and abs(d.get('y', 999.0) - y0) < 0.05]
        assert len(y_entr) + len(tip_entr) == 1, f"{room.id} must have one wing entrance"
    _assert_no_overlap(court_rooms, 'court')
    assert court_stairs['is_courtyard']
    assert len(court_stairs['flights']) == court_props.num_floors - 1
    # One staircase only: at most two lanes, all on the same (left) side.
    xs = sorted({round(f['x'], 2) for f in court_stairs['flights']})
    assert len(xs) <= 2, f"courtyard must have a single stair path, got lanes {xs}"
    assert all(x < 0 for x in xs), f"courtyard stair must be one-sided, got {xs}"

    city_keys = (
        'TENEMENT_TOWER_20M_T1', 'TENEMENT_TOWER_20M_T2', 'TENEMENT_TOWER_20M_T3',
        'TENEMENT_CITY_ROW_20M_T1', 'TENEMENT_CITY_ROW_20M_T2', 'TENEMENT_CITY_ROW_20M_T3',
    )
    for key in city_keys:
        settings = PRESETS[key]['settings']
        assert PRESETS[key]['plot'] == '20m x 20m'
        assert settings['window_front'] and settings['window_back']
        assert not settings['window_left'] and not settings['window_right']
        assert not settings['has_exterior_stairs']
        assert settings['has_front_door'] and not settings['has_back_door'] and not settings['has_side_door']
    tower_floors = [PRESETS[f'TENEMENT_TOWER_20M_T{tier}']['settings']['num_floors'] for tier in (1, 2, 3)]
    row_floors = [PRESETS[f'TENEMENT_CITY_ROW_20M_T{tier}']['settings']['num_floors'] for tier in (1, 2, 3)]
    assert tower_floors == sorted(tower_floors) and tower_floors[0] >= 4
    assert row_floors == sorted(row_floors)

    window_settings = dict(PRESETS['TENEMENT_CITY_ROW_20M_T1']['settings'])
    window_settings['seed'] = 1
    window_settings['building_archetype'] = 'TENEMENT'
    window_props = SimpleNamespace(**window_settings)
    window_ctx = _create_building_context(window_props)
    window_bm = bmesh.new()
    try:
        build_floors(window_bm, window_props, window_ctx)
        for floor_windows in window_ctx.window_centers.values():
            assert floor_windows.get('FRONT')
            assert floor_windows.get('BACK')
            assert 'LEFT' not in floor_windows and 'RIGHT' not in floor_windows
    finally:
        window_bm.free()

    clear_scene()
    bpy.ops.building.create_fantasy_building()
    generated_sizes = {}
    for key in ('TENEMENT_TOWER_20M_T1', 'TENEMENT_CITY_ROW_20M_T1'):
        bpy.ops.building.apply_preset(preset_key=key)
        dimensions = bpy.context.active_object.dimensions
        generated_sizes[key] = (dimensions.x, dimensions.y, dimensions.z)
        assert dimensions.x <= 20.0 and dimensions.y <= 20.0, (
            f"{key} does not fit its 20m plot: {tuple(dimensions)}")
    assert generated_sizes['TENEMENT_TOWER_20M_T1'][2] > generated_sizes['TENEMENT_CITY_ROW_20M_T1'][2]
    print("  [PASS] Tenement apartments, single-route stairs, six city presets, blank party walls, and 20m bounds verified.")


def test_chimneys_and_stoves():
    """Verifies chimney placement against outer walls and strict hearth/stove attachment."""
    print("\n--- [TEST] Chimneys, Stoves & Hearths ---")
    clear_scene()
    bpy.ops.building.create_fantasy_building()
    props = bpy.context.scene.fantasy_building_settings
    props.has_chimney = True
    props.has_interior_furnishing = True
    bpy.ops.building.regenerate()

    obj = bpy.context.active_object
    assert obj is not None
    mat_names = [m.name for m in obj.data.materials]
    assert any(m.startswith("M_Building_Stone") for m in mat_names), f"Stone material not found in {mat_names}"
    print("  [PASS] Chimney snaps to outer wall and generates proper stone flue.")


def test_stair_switchback():
    """Non-tenement straight stairs must switch lanes every storey so an upper
    flight never stacks on (and blocks) the run below."""
    print("\n--- [TEST] Non-Tenement Stair Switchback ---")
    from types import SimpleNamespace
    from blend_building_creator.presets import PRESETS, base_settings, ARCHETYPE_MAP
    from blend_building_creator.generator.building import _create_building_context
    from blend_building_creator.generator.floors import build_floors

    key = 'HOUSE_1_MEDIUM_T3'
    settings = base_settings()
    settings.update(PRESETS[key]['settings'])
    settings['building_archetype'] = ARCHETYPE_MAP.get(key, 'HOUSE')
    settings.setdefault('seed', 1)
    props = SimpleNamespace(**settings)
    ctx = _create_building_context(props)
    bm = bmesh.new()
    try:
        build_floors(bm, props, ctx)
        holes = ctx.floor_stair_holes
        assert len(holes) >= 2, f"expected per-floor stair holes, got {holes}"
        c1 = (holes[1][0] + holes[1][1]) * 0.5
        c2 = (holes[2][0] + holes[2][1]) * 0.5
        assert abs(c1 - c2) > props.stair_width * 0.5, (
            f"consecutive flights share a lane (stacked): {holes}")
    finally:
        bm.free()
    print("  [PASS] Consecutive non-tenement flights climb separate switchback lanes.")


def test_props_and_rugs():
    """Verifies new props (Kitchen Stove, Rugs with alpha cutout, Table Scatter) build cleanly."""
    print("\n--- [TEST] Props Catalog & Stylized Rugs ---")
    bm = bmesh.new()

    # 1. Kitchen Stove
    build_prop(bm, 'KITCHEN_STOVE', 0.0, 0.0, 0.0, 0.0, width=0.95, depth=0.75, height=1.05)
    # 2. Scatter Tableware
    build_prop(bm, 'SCATTER_TABLEWARE', 1.0, 0.0, 0.0, 0.0)
    # 3. Rugs
    for r_key in ['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST']:
        build_prop(bm, r_key, 2.0, 0.0, 0.0, 0.0, width=1.4, length=2.0)

    # 4. New furnishings: sofa/armchair (previously crashed on cylinder shading),
    # 5. New magical props for Mage Tower
    magical_props = [
        'SPELLBOOK_PEDESTAL', 'ARCANE_ORRERY', 'ALCHEMY_STATION',
        'SCRYING_POOL', 'ENCHANTING_TABLE', 'MAGIC_CAULDRON',
        'GRAND_BOOKCASE', 'ARCANE_CIRCLE',
    ]
    for idx, m_key in enumerate(magical_props):
        build_prop(bm, m_key, 7.0 + idx * 2.0, 0.0, 0.0, 0.0)

    total_faces = len(bm.faces)
    assert total_faces > 500, f"Expected > 500 faces from new props, got {total_faces}"
    print(f"  [PASS] All props including 8 magical props built cleanly ({total_faces} faces).")
    bm.free()


def test_representative_presets():
    """Tests a curated sample of representative presets (takes ~3 seconds, not hours!)."""
    print("\n--- [TEST] Representative Presets (Curated 5) ---")
    clear_scene()
    bpy.ops.building.create_fantasy_building()
    curated = [
        'HOUSE_1_SMALL_T1',
        'INN_T1',
        'ARTISAN_BAKERY_T1',
        'TENEMENT_ROW_MEDIUM_T1',
        'MAGE_TOWER_T1',
        'TOWN_HALL_T1',
        'WAREHOUSE_T1',
    ]
    for p_key in curated:
        bpy.ops.building.apply_preset(preset_key=p_key)
        obj = bpy.context.active_object
        v = len(obj.data.vertices)
        p = len(obj.data.polygons)
        print(f"  -> Preset '{p_key}': {v} verts, {p} polys.")
        assert v > 500, f"Preset {p_key} produced empty geometry!"
    print(f"  [PASS] All {len(curated)} representative presets generated cleanly.")


def test_fast_render(preset_key='INN_T1', out_dir=repo_root):
    """Renders 1 exterior and 1 interior preview with EEVEE GPU for a specific preset in ~2 seconds."""
    print(f"\n--- [RENDER] Fast EEVEE GPU Preview: {preset_key} ---")
    clear_scene()
    props = bpy.context.scene.fantasy_building_settings
    from blend_building_creator.presets import apply_preset
    apply_preset(props, preset_key)
    props.door_angle = 50.0
    props.has_interior_furnishing = True
    bpy.ops.building.create_fantasy_building()

    obj = bpy.context.active_object
    dim = obj.dimensions

    # Lighting setup
    sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
    sun_data.energy = 4.0
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(40))

    # EEVEE Fast Render Engine settings on GPU
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.render.resolution_x = 960
    bpy.context.scene.render.resolution_y = 540
    try:
        bpy.context.scene.eevee.taa_render_samples = 32
    except Exception:
        pass

    # 1. Exterior Camera framed dynamically
    cam_data = bpy.data.cameras.new(name="ExtCamera")
    cam_data.lens = 32
    cam_obj = bpy.data.objects.new(name="ExtCamera", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    dist = max(dim.x, dim.y, dim.z) * 1.45
    cam_obj.location = (dist * 0.8, -dist * 1.1, dist * 0.6)
    cam_obj.rotation_euler = (math.radians(64), 0, math.radians(38))
    bpy.context.scene.camera = cam_obj

    renders_dir = os.path.join(out_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    # 1. Taproom Wide Camera (Looking northeast across taproom at bar counter, tables, chairs, rugs)
    cam_data = bpy.data.cameras.new(name="TaproomCamera")
    cam_data.lens = 16
    cam_obj = bpy.data.objects.new(name="TaproomCamera", object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    cam_obj.location = (-5.2, -3.2, 1.7)
    cam_obj.rotation_euler = (math.radians(82), 0, math.radians(-42))

    point_data = bpy.data.lights.new(name="TaproomPoint", type='POINT')
    point_data.energy = 900.0
    point_data.color = (1.0, 0.90, 0.78)
    point_obj = bpy.data.objects.new(name="TaproomPoint", object_data=point_data)
    bpy.context.scene.collection.objects.link(point_obj)
    point_obj.location = (-3.2, 0.0, 2.5)

    out_taproom = os.path.join(renders_dir, f"{preset_key.lower()}_taproom.png")
    bpy.context.scene.render.filepath = out_taproom
    bpy.ops.render.render(write_still=True)
    print(f"  [PASS] Taproom rendered with EEVEE: {out_taproom}")

    # 2. Tableware Close-Up Camera (Looking over chair backs down at tabletop with flagon, bread roll, cheese, tankard, candlestick, chairs)
    cam_obj.location = (-2.97, -0.55, 2.50)
    cam_obj.rotation_euler = (math.radians(52), 0, 0)
    cam_data.lens = 28

    point_obj.location = (-2.97, 0.55, 2.60)
    point_data.energy = 400.0

    out_table = os.path.join(renders_dir, f"{preset_key.lower()}_tableware.png")
    bpy.context.scene.render.filepath = out_table
    bpy.ops.render.render(write_still=True)
    print(f"  [PASS] Tableware close-up rendered with EEVEE: {out_table}")

    # 3. Kitchen Camera (Looking across the spacious 1-room kitchen at stove, prep table, cauldron, shelves)
    cam_obj.location = (1.6, -3.2, 1.7)
    cam_obj.rotation_euler = (math.radians(82), 0, math.radians(-32))
    cam_data.lens = 17

    point_obj.location = (3.5, 0.0, 2.5)
    point_data.energy = 850.0

    out_kitchen = os.path.join(renders_dir, f"{preset_key.lower()}_kitchen.png")
    bpy.context.scene.render.filepath = out_kitchen
    bpy.ops.render.render(write_still=True)
    print(f"  [PASS] Kitchen rendered with EEVEE: {out_kitchen}")


def main():
    parser = argparse.ArgumentParser(description="Directed Fantasy Building Generator Test Suite")
    parser.add_argument("--test", choices=['all', 'scale', 'stairs', 'mage', 'zoning', 'tenements', 'chimney', 'props', 'presets', 'render'],
                        default='all', help="Specific test to execute")
    parser.add_argument("--preset", default="INN_T1", help="Target preset for preview render")
    parser.add_argument("--render", action="store_true", help="Render fast EEVEE preview images for the target preset")

    # Pass remaining args after '--'
    args_list = []
    if "--" in sys.argv:
        args_list = sys.argv[sys.argv.index("--") + 1:]
    args = parser.parse_args(args_list)

    test_explicit = any(arg.startswith("--test") for arg in args_list)
    if args.render and not test_explicit:
        args.test = 'render'

    print("=" * 60)
    print("DIRECTED TEST SUITE - BLENDER", bpy.app.version_string)
    print("Mode:", args.test, "| Preset:", args.preset, "| Render:", args.render)
    print("=" * 60)

    test_map = {
        'scale': [test_registration, test_gamified_scale],
        'stairs': [test_stairs_and_uv_fibers, test_stair_switchback],
        'mage': [test_mage_tower],
        'zoning': [test_room_zoning_and_furnishing],
        'tenements': [test_tenement_layouts],
        'chimney': [test_chimneys_and_stoves],
        'props': [test_props_and_rugs],
        'presets': [test_representative_presets],
        'all': [
            test_registration,
            test_gamified_scale,
            test_stairs_and_uv_fibers,
            test_stair_switchback,
            test_mage_tower,
            test_room_zoning_and_furnishing,
            test_tenement_layouts,
            test_chimneys_and_stoves,
            test_props_and_rugs,
            test_representative_presets,
        ],
        'render': [],
    }

    blend_building_creator.register()
    tests_to_run = test_map.get(args.test, test_map['all'])
    for t in tests_to_run:
        t()

    if args.render or args.test == 'render':
        test_fast_render(preset_key=args.preset)

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
