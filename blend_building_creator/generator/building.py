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


def _ensure_door_floor_clearance(props):
    """Raise ``floor_height`` just enough that tall entrance portals fit.

    The arched stone portal stacks ~0.41m of trim above the opening and the
    square timber header ~0.16m; both run full wall depth, so when the floor
    is too short they poke through the slab into the storey above (visible
    as trim bands on the upstairs interior walls). Per preference the floor
    grows slightly instead of shrinking the door. The update callback is
    muted while adjusting so generation does not recurse.
    """
    has_door = (getattr(props, 'has_front_door', False)
                or getattr(props, 'has_back_door', False)
                or getattr(props, 'has_side_door', False)
                or getattr(props, 'has_back_portal', False))
    if not has_door:
        return
    door_h = float(getattr(props, 'door_height', 2.8))
    shape = getattr(props, 'door_shape', 'AUTO')
    tier = getattr(props, 'material_tier', 'TIER_3')
    door_w = float(getattr(props, 'door_width', 1.45))
    ground_stone = bool(getattr(props, 'ground_floor_stone', False))
    is_arched = (shape == 'ARCHED') or (shape == 'AUTO' and ground_stone and door_w < 1.6)
    crown = 0.41 if is_arched else 0.16
    # Crown trim + floor slab (0.15) + ceiling beams (0.18) + small air gap.
    needed = door_h + crown + 0.40
    needed = min(8.0, max(2.4, needed))
    try:
        cur = float(getattr(props, 'floor_height', 3.6))
    except Exception:
        return
    if cur + 1e-6 < needed:
        old_auto = getattr(props, 'auto_update', True)
        try:
            props.auto_update = False
            props.floor_height = needed
        except Exception:
            pass
        finally:
            try:
                props.auto_update = old_auto
            except Exception:
                pass


def generate_building(obj, props, extra_doorways=None, extra_window_exclusions=None):
    """
    Main generator function called when properties change or generate button is clicked.
    Constructs the building inside obj.data.

    The work is split into phases that share a single mutable :class:`BuildingContext`:
    setup, foundation, per-floor construction, roof/attic, archetype accessories,
    optional outcrops/balconies, then finalization.

    Empty construction sites (scaffold-only, no building yet) take a separate
    early-out path: scaffold + piles + cranes, no walls, roof or footing.
    """
    # Tall doors must fit inside the ground storey: grow short floors
    # slightly rather than clipping the portal through the slab above.
    _ensure_door_floor_clearance(props)
    _original_stair_side = getattr(props, 'stair_placement', None)
    from . import mesh_utils
    mesh_utils.ENABLE_BEVELS = bool(getattr(props, 'enable_bevels', False))
    bm = bmesh.new()

    if (getattr(props, 'has_construction', False)
            and getattr(props, 'construction_mode', 'WRAP_BUILDING') == 'EMPTY_SITE'):
        _build_empty_construction_site(obj, bm, props)
        if _original_stair_side is not None:
            props.stair_placement = _original_stair_side
        return

    if getattr(props, 'building_shape', 'RECTANGLE') == 'ROUND_TOWER':
        _build_round_tower_building(obj, bm, props)
        if _original_stair_side is not None:
            props.stair_placement = _original_stair_side
        return

    if getattr(props, 'has_castle_citadel', False):
        _build_castle_citadel_building(obj, bm, props)
        return

    ctx = _create_building_context(props, extra_doorways=extra_doorways, extra_window_exclusions=extra_window_exclusions)
    ctx.props = props
    ctx.host_obj = obj
    _build_foundation(bm, props, ctx)
    build_floors(bm, props, ctx)
    loft_spec = build_roof_and_attic(bm, props, ctx)
    build_archetype_accessories(bm, props, ctx, loft_spec)
    build_architectural_accessories(bm, props, ctx)
    _finalize_building(obj, bm, props, ctx)


def _build_castle_citadel_building(obj, bm, props):
    """
    Dedicated generator for the monumental modular fantasy castle citadel.
    Constructs an asymmetrical, multi-winged fortress with enterable towers,
    walkable spiral staircases, great ballroom, flat stone ramparts with merlons,
    and complete subterranean dungeons and wine cellar.
    """
    from .accessories.estate import cleanup_outbuilding_objects
    cleanup_outbuilding_objects(obj)

    ctx = _create_building_context(props)
    ctx.host_obj = obj
    from .accessories.castle import build_modular_castle_citadel
    build_modular_castle_citadel(bm, props, ctx)
    from .accessories.estate import build_estate_outbuildings
    build_estate_outbuildings(bm, props, ctx, host_obj=obj)
    from .accessories.dispatch import _build_plot_fortifications
    _build_plot_fortifications(bm, props, ctx)
    _finalize_building(obj, bm, props, ctx)


def _build_empty_construction_site(obj, bm, props):
    """Scaffold-only site: no walls, floors, roof or footing, just scaffold + yard.

    Reuses the normal context (intended width/depth/floors define the future
    building's size and scaffold height) and the scaffold composer, then
    commits without wonkiness so poles stay straight.
    """
    from .accessories.scaffold import build_empty_construction_site
    ctx = _create_building_context(props)
    build_empty_construction_site(bm, props, ctx)
    # Commit without wonkiness: a bent scaffold reads as broken, not busy.
    # NOTE: auto_update is muted while we park wonkiness, otherwise the
    # property update callback would re-enter generate_building recursively.
    old_auto = getattr(props, 'auto_update', True)
    old_wonk = getattr(props, 'wonkiness', 0.0)
    try:
        props.auto_update = False
        props.wonkiness = 0.0
        _finalize_building(obj, bm, props, ctx)
    finally:
        try:
            props.wonkiness = old_wonk
        except Exception:
            pass
        try:
            props.auto_update = old_auto
        except Exception:
            pass


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
    from .materials import prune_material_slots_for_bmesh
    prune_material_slots_for_bmesh(obj, bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    apply_organic_shading(obj)
    _store_building_settings(obj, props)


def _create_building_context(props, extra_doorways=None, extra_window_exclusions=None):
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
    is_u_tenement = (shape == 'U_SHAPE' and (
        effective_archetype == 'TENEMENT' or
        getattr(props, 'exterior_stairs_side', '') == 'COURTYARD' or
        'TENEMENT' in getattr(props, 'building_family', '')
    ))
    is_estate_or_manor = (
        effective_archetype in ('MANOR', 'PALACE', 'CASTLE') or
        'MANOR' in getattr(props, 'building_family', '') or
        (base_w >= 36.0 and num_floors >= 3)
    )
    if has_balc:
        b_mode = getattr(props, 'balcony_mode', 'SINGLE')
        if is_u_tenement and b_mode == 'SINGLE':
            # Tenement complexes have multiple flats per storey; balconies grace all upper floors.
            active_balc_floors = list(range(1, num_floors))
        elif is_estate_or_manor and b_mode == 'SINGLE' and num_floors >= 3:
            # Grand manors & ducal palaces: balconies on piano nobile (fl 2) and ducal solar (fl 3)
            active_balc_floors = [1, 2] if num_floors >= 4 else [1]
        elif b_mode == 'SINGLE':
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
    if is_u_tenement and balc_side_eff == 'FRONT':
        balc_side_eff = 'BACK'

    floor_balc_side = {}
    floor_balconies = {}
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
        if is_u_tenement:
            # Courtyard is on FRONT; balconies belong on BACK or exterior flanks
            for _s in (balc_side_eff, 'BACK', 'LEFT', 'RIGHT'):
                if _s not in _order:
                    _order.append(_s)
        else:
            for _s in (*_eave_f, balc_side_eff, *_gable_f):
                if _s not in _order:
                    _order.append(_s)
        _order = tuple(_order)
        for _bf in active_balc_floors:
            _blocked_f = set()
            if _bf <= wing_floors:
                _blocked_f |= _wing_walls
            if _annex_on and _bf <= _annex_floors:
                if _annex_side == 'BOTH':
                    _blocked_f.add('LEFT')
                    _blocked_f.add('RIGHT')
                else:
                    _blocked_f.add(_annex_side)
            if _rampart_side is not None and _bf <= 1:
                _blocked_f.add(_rampart_side)
            if _has_veranda:
                _blocked_f.add('FRONT')
            chosen_side = next((_s for _s in _order if _s not in _blocked_f), None)
            floor_balc_side[_bf] = chosen_side

            # For U-shaped tenements (or wide tenements), place multiple balconies spaced across apartments
            if is_u_tenement and chosen_side == 'BACK' and len(wings) >= 2 and base_w >= 14.0:
                from .tenement import courtyard_cut_x
                ix_min = -base_w * 0.5 + wall_t * 0.5
                ix_max = base_w * 0.5 - wall_t * 0.5
                cuts = courtyard_cut_x(ix_min, ix_max, wings)
                b_entries = []
                for k in range(len(cuts) - 1):
                    cx_mid = (cuts[k] + cuts[k + 1]) * 0.5
                    b_entries.append({'side': 'BACK', 'offset': cx_mid})
                floor_balconies[_bf] = b_entries
            elif is_estate_or_manor and base_w >= 36.0 and _bf == 1:
                # Main palace piano nobile: ceremonial lord's balcony at center + flank balconies
                flank_off = base_w * 0.28
                floor_balconies[_bf] = [
                    {'side': chosen_side, 'offset': 0.0},
                    {'side': chosen_side, 'offset': -flank_off},
                    {'side': chosen_side, 'offset': flank_off},
                ]
            elif chosen_side is not None:
                floor_balconies[_bf] = [{'side': chosen_side, 'offset': 0.0}]

    if extra_doorways is None:
        extra_dw = getattr(props, 'extra_doorways', None) or (props.get('extra_doorways', None) if hasattr(props, 'get') else None) or []
    else:
        extra_dw = extra_doorways

    if extra_window_exclusions is None:
        extra_we = getattr(props, 'extra_window_exclusions', None) or (props.get('extra_window_exclusions', None) if hasattr(props, 'get') else None) or []
    else:
        extra_we = extra_window_exclusions

    # The blacksmith's open forge canopy stands against the +X (RIGHT) wall on
    # the ground floor. Suppress the ground-floor windows beneath it so they
    # are not buried behind the work canopy (upper-storey windows stay).
    _bs_kit = bool(getattr(props, 'kit_blacksmith', False)) or effective_archetype == 'BLACKSMITH'
    if _bs_kit:
        _hy = base_d * 0.5
        extra_we = list(extra_we)
        extra_we.append({'facade': 'RIGHT', 'min': -0.82 * _hy, 'max': 0.82 * _hy,
                         'floor_min': 0, 'floor_max': 0})

    # The fishmonger's shop display case moves into the front-left corner: drop
    # the shopfront window there (the adjacent west window stays).
    if effective_archetype == 'FISHERMAN':
        extra_we = list(extra_we)
        extra_we.append({'facade': 'FRONT',
                         'min': -base_w * 0.5 + 0.18,
                         'max': -base_w * 0.5 + 2.00,
                         'floor_min': 0, 'floor_max': 0})

    planned_chimneys = []
    if getattr(props, 'has_chimney', False) and effective_archetype not in ('WATCHTOWER', 'BAKERY'):
        from .roof.details import get_planned_chimney_positions
        chim_specs = get_planned_chimney_positions(props, effective_archetype, top_w=_top_w, top_d=_top_d)
        if chim_specs:
            extra_we = list(extra_we)
            chim_win_clr = 1.35  # clearance so windows are never placed behind or adjacent to fireplace/chimney
            for cs in chim_specs:
                planned_chimneys.append(cs['pos'])
                if cs['axis'] == 'X':
                    extra_we.append({
                        'facade': cs['facade'],
                        'min': cs['x'] - chim_win_clr,
                        'max': cs['x'] + chim_win_clr,
                        'floor_min': 0,
                        'floor_max': 99
                    })
                else:
                    extra_we.append({
                        'facade': cs['facade'],
                        'min': cs['y'] - chim_win_clr,
                        'max': cs['y'] + chim_win_clr,
                        'floor_min': 0,
                        'floor_max': 99
                    })

    # Resolve the annex layout once, up front, so the floors phase (portal cut
    # + window suppression), the accessory dispatch (annex volume / roof band)
    # and the attic phase (loft-hatch avoidance) all read the SAME side, width
    # and portal position instead of re-deriving them.
    from .annex_layout import resolve_annex_layout
    annex = resolve_annex_layout(props, base_w, base_d, wall_t, num_floors,
                                 wings=wings, shape=shape)

    # Annex doorways must also steer the ROOM PLAN: the grand-manor planner
    # otherwise drops a full-height partition straight across the walk-through,
    # giving the annex a wall instead of a door. Registering them as side
    # portals makes the planner reserve that exact span.
    if annex.get('by_side'):
        extra_dw = list(extra_dw)
        for _side, _lay in sorted(annex['by_side'].items()):
            _pc = _lay.get('portal_cy', 0.0)
            _face_x = (base_w * 0.5 - wall_t * 0.5) * (1.0 if _side == 'RIGHT' else -1.0)
            for _fl in range(int(annex.get('floors', 0) or 0)):
                extra_dw.append({
                    'x': _face_x,
                    'y': _pc, 'axis': 'Y', 'w': 1.65,
                    'floor_idx': _fl, 'is_portal': True, 'facade': _side,
                })

    return BuildingContext(
        num_floors=num_floors, floor_h=floor_h, found_h=found_h,
        floor_wall_bounds={}, hx=0.0, hy=0.0,
        base_w=base_w, base_d=base_d, raw_wing_d=raw_wing_d,
        main_door_cx=main_door_cx, main_door_yf=main_door_yf,
        shape=shape, seed=seed, plank_dir=getattr(props, 'plank_direction', 'VERTICAL'),
        floor_balc_side=floor_balc_side, floor_balconies=floor_balconies,
        active_balc_floors=active_balc_floors,
        wall_t=wall_t, cantilever=cantilever, open_timber=open_timber,
        effective_archetype=effective_archetype,         wings=wings, has_wing=has_wing,
        wing_floors=wing_floors, raw_wing_w=raw_wing_w,
        wing_placement=wing_placement, wing_side=wing_side,
        total_height=total_height, floor_stair_holes={},
        wx_base_min=wx_base_min, wx_base_max=wx_base_max,
        wy_base_min=wy_base_min, wy_base_max=wy_base_max,
        extra_doorways=list(extra_dw),
        extra_window_exclusions=list(extra_we),
        is_rotated_roof=is_rotated_roof,
        chimney_pos=planned_chimneys[0] if planned_chimneys else None,
        chimney_positions=list(planned_chimneys),
        planned_chimneys=list(planned_chimneys),
        annex_kind=annex['kind'],
        annex_side=annex['side'],
        annex_width=annex['width'],
        annex_floors=annex['floors'],
        annex_cy=annex.get('cy', 0.0),
        annex_portal_cy=annex.get('portal_cy', 0.0),
        annex_by_side=annex['by_side'],
        annex_stair_side=annex.get('stair_side'),
        annex_clear_rects=list(annex.get('clear_rects') or []),
    )


def _build_foundation_block(bm, fw, fd, fcx, fcy, found_h, found_type, stair_hole=None):
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
        fx0, fx1 = fcx - fw * 0.5, fcx + fw * 0.5
        fy0, fy1 = fcy - fd * 0.5, fcy + fd * 0.5
        if stair_hole is not None:
            sh_x0, sh_x1, sh_y0, sh_y1 = stair_hole
            if not (sh_x1 <= fx0 or sh_x0 >= fx1 or sh_y1 <= fy0 or sh_y0 >= fy1):
                sx0 = max(fx0, min(fx1, sh_x0))
                sx1 = max(fx0, min(fx1, sh_x1))
                sy0 = max(fy0, min(fy1, sh_y0))
                sy1 = max(fy0, min(fy1, sh_y1))

                def _found_sub(x_a, x_b, y_a, y_b):
                    if x_b - x_a < 0.04 or y_b - y_a < 0.04:
                        return
                    create_beveled_box(
                        bm,
                        size=(x_b - x_a, y_b - y_a, found_h),
                        location=((x_a + x_b) * 0.5, (y_a + y_b) * 0.5, found_h * 0.5),
                        mat_index=MAT_INDEX_STONE,
                        bevel_amount=0.04
                    )

                if sx0 > fx0 + 0.02:
                    _found_sub(fx0, sx0, fy0, fy1)
                if sx1 < fx1 - 0.02:
                    _found_sub(sx1, fx1, fy0, fy1)
                if sy0 > fy0 + 0.02:
                    _found_sub(sx0, sx1, fy0, sy0)
                if sy1 < fy1 - 0.02:
                    _found_sub(sx0, sx1, sy1, fy1)
                return

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
    tier = getattr(props, 'material_tier', 'TIER_3')
    if tier == 'TIER_1':
        found_type = 'WOOD'
    fw = ctx.base_w + 0.35
    fd = ctx.base_d + 0.35
    fcx = 0.0
    fcy = 0.0
    if ctx.effective_archetype == 'CHAPEL' or getattr(props, 'has_back_portal', False):
        # Stop foundation plinth at rear wall line (y_max = base_hy) so it does not poke into apse room
        fd = ctx.base_d + 0.175
        fcy = -0.0875

    bs_hole = None
    if getattr(props, 'has_basement_stair', False):
        if ctx.shape == 'L_SHAPE' and ctx.wings:
            wb = ctx.wings[0]['base']
            _shx = float(wb[0]) + 1.50
            _shy = (float(wb[2]) + float(wb[3])) * 0.5
            bs_hole = (_shx - 0.80, _shx + 0.80, _shy - 1.80, _shy + 1.80)
        else:
            if getattr(props, 'has_throne_room', False):
                bs_hole = (-0.50, 4.10, 10.80, 12.40)
            else:
                bs_hole = (1.10, 5.70, 4.00, 5.40)

    _build_foundation_block(bm, fw, fd, fcx, fcy, found_h, found_type, stair_hole=bs_hole)
    for w_elem in ctx.wings:
        wb = w_elem['base']
        w_fw = (wb[1] - wb[0]) + 0.35
        w_fd = (wb[3] - wb[2]) + 0.35
        w_fcx = (wb[0] + wb[1]) * 0.5
        w_fcy = (wb[2] + wb[3]) * 0.5
        _build_foundation_block(bm, w_fw, w_fd, w_fcx, w_fcy, found_h, found_type, stair_hole=bs_hole)
        
    if getattr(props, 'has_dungeon', False):
        from .accessories.castle import build_subterranean_dungeon_level
        build_subterranean_dungeon_level(bm, cx=fcx, cy=fcy, z_floor=-7.5, width=fw, depth=fd)

    if getattr(props, 'has_cliffs', False):
        from .materials import MAT_INDEX_CLIFFS
        from .mesh_utils import create_beveled_box
        # Clean, tiered, blocky stylized rock terraces establishing solid cliff foundation
        # Tier 1: Direct pedestal cradling the foundation
        create_beveled_box(bm, size=(fw + 2.5, fd + 2.5, 2.5),
                           location=(fcx, fcy, -1.25),
                           mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.35)
        # Tier 2: Mid-level stepped rock shelf
        create_beveled_box(bm, size=(fw + 6.0, fd + 6.0, 3.5),
                           location=(fcx, fcy, -3.75),
                           mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.50)
        # Tier 3: Broad bedrock base shelf
        create_beveled_box(bm, size=(fw + 10.0, fd + 10.0, 4.5),
                           location=(fcx, fcy, -7.0),
                           mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.65)

        # Stepped rock corner buttresses supporting the outer angles
        for sgn_x in (-1.0, 1.0):
            for sgn_y in (-1.0, 1.0):
                bx = fcx + sgn_x * (fw * 0.5 + 2.2)
                by = fcy + sgn_y * (fd * 0.5 + 2.2)
                create_beveled_box(bm, size=(5.0, 5.0, 7.0),
                                   location=(bx, by, -3.5),
                                   mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.55)

        # If tower annex is active, build an elevated cliff promontory under it
        if getattr(props, 'has_tower_annex', False):
            a_side = getattr(props, 'annex_side', 'LEFT')
            t_sgns = [-1.0, 1.0] if a_side == 'BOTH' else ([1.0] if a_side == 'RIGHT' else [-1.0])
            for sgn in t_sgns:
                tx = fcx + sgn * (fw * 0.5 + 4.5)
                create_beveled_box(bm, size=(10.0, 14.0, 8.5),
                                   location=(tx, fcy, -2.5),
                                   mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)


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
    from .materials import prune_material_slots_for_bmesh
    prune_material_slots_for_bmesh(obj, bm)
    
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
