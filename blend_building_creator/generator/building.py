"""
Master Building Generator Orchestrator for Stylized Fantasy Buildings.
Coordinates foundation, double-walled floors, walk-in doorways, intermediate floor slabs,
staircases, ceiling beams, roofs, shingles, dormers, and chimneys into a unified mesh.
Supports Rectangular, L-Shaped, T-Shaped, and Round Tower footprint architectures.
"""

import bmesh
from .mesh_utils import create_beveled_box, apply_box_uvs, add_wonkiness, apply_organic_shading
from .materials import (
    setup_building_material_slots, MAT_INDEX_STONE,
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON
)
from .shapes import get_wings_setup
from .round_tower import build_round_tower
from .floors import build_floors
from .roof.attic import build_roof_and_attic
from .accessories.dispatch import build_architectural_accessories, build_archetype_accessories
from .config import BuildingContext


def generate_building(obj, props):
    """
    Main generator function called when properties change or generate button is clicked.
    Constructs the building inside obj.data.

    The work is split into phases that share a single mutable :class:`BuildingContext`:
    setup, foundation, per-floor construction, roof/attic, archetype accessories,
    optional outcrops/balconies, then finalization.
    """
    bm = bmesh.new()

    if getattr(props, 'building_shape', 'RECTANGLE') == 'ROUND_TOWER':
        _build_round_tower_building(obj, bm, props)
        return

    ctx = _create_building_context(props)
    _build_foundation(bm, props, ctx)
    build_floors(bm, props, ctx)
    loft_spec = build_roof_and_attic(bm, props, ctx)
    build_archetype_accessories(bm, props, ctx, loft_spec)
    build_architectural_accessories(bm, props, ctx)
    _finalize_building(obj, bm, props, ctx)


def _store_building_settings(obj, props):
    """Persist the settings dict on the object for independent multi-building recall."""
    try:
        from ..operators import get_props_dict
        import json
        obj["building_settings"] = json.dumps(get_props_dict(props))
    except Exception:
        pass


def _build_round_tower_building(obj, bm, props):
    """Complete build path for the faceted cylindrical round-tower footprint."""
    seed = props.seed
    num_floors = max(1, props.num_floors)
    floor_h = props.floor_height
    found_h = props.foundation_height if props.has_foundation else 0.2
    build_round_tower(bm, props, seed)
    if props.wonkiness > 0.001:
        total_h = found_h + num_floors * floor_h + props.roof_height
        add_wonkiness(bm, z_min=0.0, z_max=total_h, amount=props.wonkiness, seed=seed)
    apply_box_uvs(bm, scale=1.0)
    setup_building_material_slots(obj, props)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    apply_organic_shading(obj)
    _store_building_settings(obj, props)


def _create_building_context(props):
    """Resolve every top-level dimension, wing and balcony decision into a context."""
    seed = props.seed
    num_floors = max(1, props.num_floors)
    floor_h = props.floor_height
    base_w = props.width
    base_d = props.depth
    wall_t = props.wall_thickness
    cantilever = props.cantilever_overhang if props.has_cantilever else 0.0
    found_h = props.foundation_height if props.has_foundation else 0.0
    open_timber = getattr(props, 'open_timber_frame', False)

    # Archetype resolution
    archetype = getattr(props, 'building_archetype', 'AUTO')
    if archetype == 'AUTO':
        archetype = 'NONE'
    effective_archetype = archetype

    shape = getattr(props, 'building_shape', 'RECTANGLE')

    raw_wing_w = getattr(props, 'wing_width', 3.5)
    raw_wing_d = getattr(props, 'wing_depth', 3.0)
    wing_placement = getattr(props, 'wing_placement', 'FRONT')
    wing_side = getattr(props, 'wing_side', 'RIGHT')
    courtyard_w = getattr(props, 'courtyard_width', 3.5)
    wing_floors = min(num_floors, max(1, getattr(props, 'wing_floors', 1)))

    wings = get_wings_setup(shape, wing_placement, wing_side, base_w, base_d, raw_wing_w, raw_wing_d, courtyard_w)
    has_wing = len(wings) > 0

    # Backwards compatibility bounds for single wing references
    if has_wing:
        wx_base_min, wx_base_max = wings[0]['base'][0], wings[0]['base'][1]
        wy_base_min, wy_base_max = wings[0]['base'][2], wings[0]['base'][3]
    else:
        wx_base_min, wx_base_max = 0.0, 0.0
        wy_base_min, wy_base_max = 0.0, 0.0

    # Resolve the roof orientation here (same rule the roof builder uses) so the
    # wall phase knows which facades are eaves and which are gables.
    roof_style = getattr(props, 'roof_style', 'SWAY')
    top_cant = 0.0
    if getattr(props, 'has_cantilever', False):
        if getattr(props, 'overhang_mode', 'SECOND_FLOOR_ONLY') == 'SECOND_FLOOR_ONLY':
            top_cant = props.cantilever_overhang if num_floors >= 2 else 0.0
        else:
            top_cant = (num_floors - 1) * props.cantilever_overhang
    _top_w = base_w + top_cant * 2.0
    _top_d = base_d + top_cant * 2.0
    _roof_orient = getattr(props, 'roof_orientation', 'FRONT_BACK')
    if _roof_orient == 'AUTO':
        _roof_orient = 'LEFT_RIGHT' if _top_w > _top_d * 1.15 else 'FRONT_BACK'
    is_rotated_roof = (_roof_orient == 'LEFT_RIGHT' and roof_style in ('SWAY', 'GABLE'))

    # Track overall bounding box for wonkiness
    total_height = found_h + num_floors * floor_h + props.roof_height
    main_door_cx = 0.0
    main_door_yf = -base_d * 0.5

    # Active balcony floor levels
    active_balc_floors = []
    has_balc = getattr(props, 'has_balcony', False) and num_floors >= 2
    if has_balc:
        b_mode = getattr(props, 'balcony_mode', 'SINGLE')
        if b_mode == 'SINGLE':
            fl = min(num_floors, max(2, getattr(props, 'balcony_floor', 2)))
            active_balc_floors = [fl - 1]
        elif b_mode == 'ALL_UPPER':
            active_balc_floors = list(range(1, num_floors))
        elif b_mode == 'CUSTOM':
            for fl_i, toggle_p in [(1, 'balcony_fl2'), (2, 'balcony_fl3'), (3, 'balcony_fl4'), (4, 'balcony_fl5')]:
                if fl_i < num_floors and getattr(props, toggle_p, False):
                    active_balc_floors.append(fl_i)

    # Effective balcony facade per floor: never mount a balcony on a facade
    # occupied at that height by a projecting volume (the wing and its roof, the
    # side annex, the mini-wing outcrop). Resolve every active floor
    # independently so a free upper facade can still take a balcony, and skip a
    # floor entirely when nothing is free.
    balc_side_eff = getattr(props, 'balcony_side', 'FRONT')
    floor_balc_side = {}
    if has_balc:
        _annex_on = (getattr(props, 'has_side_annex', False)
                     and (not getattr(props, 'town_hall_composer', False)
                          or shape == 'T_SHAPE'))
        _annex_side = None
        _annex_floors = 0
        if _annex_on:
            if getattr(props, 'town_hall_composer', False):
                _annex_side = ('LEFT' if getattr(props, 'clock_tower_side', 'RIGHT') == 'RIGHT'
                               else 'RIGHT')
            else:
                _annex_side = getattr(props, 'annex_side', 'LEFT')
            _annex_floors = max(1, min(2, getattr(props, 'annex_floors', 2)))
        _wing_walls = {w.get('wall') for w in wings} if has_wing else set()
        _rampart_side = (getattr(props, 'rampart_side', 'RIGHT')
                         if getattr(props, 'has_side_rampart', False) else None)
        # A covered veranda occupies the front facade up past the first floor, so
        # a front balcony would intersect its roof. Force balconies elsewhere.
        _has_veranda = (getattr(props, 'has_veranda', False)
                        or effective_archetype in ('TAVERN', 'INN'))
        # The loft/gable ladder climbs a gable end, so a balcony on the same
        # facade would collide with it. Prefer the eave facades (where the ladder
        # never goes), then the requested side, then the gables as a last resort.
        _gable_f = ['LEFT', 'RIGHT'] if is_rotated_roof else ['FRONT', 'BACK']
        _eave_f = ['FRONT', 'BACK'] if is_rotated_roof else ['LEFT', 'RIGHT']
        _order = []
        for _s in (*_eave_f, balc_side_eff, *_gable_f):
            if _s not in _order:
                _order.append(_s)
        _order = tuple(_order)
        for _bf in active_balc_floors:
            _blocked_f = set()
            if _bf <= wing_floors:
                _blocked_f |= _wing_walls
            if _annex_on and _bf <= _annex_floors:
                _blocked_f.add(_annex_side)
            if _rampart_side is not None and _bf <= 1:
                _blocked_f.add(_rampart_side)
            if _has_veranda:
                _blocked_f.add('FRONT')
            # Mini-wing outcrops pick their slots after this and keep clear of
            # whatever facade the balcony ends up on.
            floor_balc_side[_bf] = next((_s for _s in _order if _s not in _blocked_f), None)

    return BuildingContext(
        num_floors=num_floors, floor_h=floor_h, found_h=found_h,
        floor_wall_bounds={}, hx=0.0, hy=0.0,
        base_w=base_w, base_d=base_d, raw_wing_d=raw_wing_d,
        main_door_cx=main_door_cx, main_door_yf=main_door_yf,
        shape=shape, seed=seed, plank_dir=getattr(props, 'plank_direction', 'HORIZONTAL'),
        floor_balc_side=floor_balc_side, active_balc_floors=active_balc_floors,
        wall_t=wall_t, cantilever=cantilever, open_timber=open_timber,
        effective_archetype=effective_archetype,         wings=wings, has_wing=has_wing,
        wing_floors=wing_floors, raw_wing_w=raw_wing_w,
        wing_placement=wing_placement, wing_side=wing_side,
        total_height=total_height, floor_stair_holes={},
        wx_base_min=wx_base_min, wx_base_max=wx_base_max,
        wy_base_min=wy_base_min, wy_base_max=wy_base_max,
        is_rotated_roof=is_rotated_roof,
    )


def _build_foundation_block(bm, fw, fd, fcx, fcy, found_h, found_type):
    if found_type == 'WOOD':
        # Clean perimeter timber sill frame: no duplicate inner box (floor slab provides
        # the single clean floor deck), no metal corners, and cleanly butted side beams.
        sill_w = 0.24
        sill_h = found_h + 0.05
        # Front & Back sills
        for sgn in (-1.0, 1.0):
            py = fcy + sgn * (fd * 0.5 - sill_w * 0.5)
            create_beveled_box(
                bm,
                size=(fw, sill_w, sill_h),
                location=(fcx, py, sill_h * 0.5),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.012
            )
        # Left & Right sills (cleanly butted between front & back to avoid coplanar overlap)
        side_l = max(0.2, fd - sill_w * 2.0)
        for sgn in (-1.0, 1.0):
            px = fcx + sgn * (fw * 0.5 - sill_w * 0.5)
            create_beveled_box(
                bm,
                size=(sill_w, side_l, sill_h),
                location=(px, fcy, sill_h * 0.5),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.012
            )
    else:
        create_beveled_box(
            bm,
            size=(fw, fd, found_h),
            location=(fcx, fcy, found_h * 0.5),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.04
        )


def _build_foundation(bm, props, ctx):
    """Foundation plinth (stone or timber sleeper deck) under the main footprint and every wing."""
    if not props.has_foundation:
        return
    found_h = ctx.found_h
    found_type = getattr(props, 'foundation_type', 'STONE')
    fw = ctx.base_w + 0.35
    fd = ctx.base_d + 0.35
    _build_foundation_block(bm, fw, fd, 0.0, 0.0, found_h, found_type)
    for w_elem in ctx.wings:
        wb = w_elem['base']
        w_fw = (wb[1] - wb[0]) + 0.35
        w_fd = (wb[3] - wb[2]) + 0.35
        w_fcx = (wb[0] + wb[1]) * 0.5
        w_fcy = (wb[2] + wb[3]) * 0.5
        _build_foundation_block(bm, w_fw, w_fd, w_fcx, w_fcy, found_h, found_type)


def _finalize_building(obj, bm, props, ctx):
    """Wonkiness, UVs, material slots, mesh commit and optional per-material split."""
    total_height = ctx.total_height
    seed = ctx.seed

    # 5. Whimsical Curvature / Wonkiness Deformation
    if props.wonkiness > 0.001:
        add_wonkiness(bm, z_min=0.0, z_max=total_height, amount=props.wonkiness, seed=seed)
        
    # 6. Apply UVs
    apply_box_uvs(bm, scale=1.0)

    # 7. Setup Material Slots and procedural node shaders BEFORE transferring bmesh
    setup_building_material_slots(obj, props)
    
    # 8. Commit bmesh to object mesh data (preserves material slot mapping)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    apply_organic_shading(obj)
    # 8b. Optional split by material — each piece (log, beam, board) becomes separate object with conformal islands
    if getattr(props, 'split_by_material', False):
        try:
            import bpy as _bpy
            _bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            _bpy.ops.object.mode_set(mode='EDIT')
            _bpy.ops.mesh.separate(type='MATERIAL')
            _bpy.ops.object.mode_set(mode='OBJECT')
            # After separate, ensure every new piece has consistent fiber direction via smart UV for handpaint if needed
            for o in [o for o in _bpy.context.scene.objects if o.get("is_fantasy_building", False) or o == obj]:
                if len(o.data.polygons) == 0: continue
                # Keep existing manual UVs (already along length) — no auto re-unwrap to preserve fiber direction
                pass
        except Exception as e:
            print(f"split_by_material failed: {e}")
            try: _bpy.ops.object.mode_set(mode='OBJECT')
            except: pass
    
    # Store settings dictionary on object for independent multi-building recall
    try:
        from ..operators import get_props_dict
        import json
        obj["building_settings"] = json.dumps(get_props_dict(props))
    except Exception:
        pass
