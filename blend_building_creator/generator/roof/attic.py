"""Roof and attic construction phase.

Builds the exterior roof (sway / gable), wing roofs and valleys, attic floor
slab, dormers, roof turret, roof clock spire, chimney and the gable loft hatch
spec. Called once by the orchestrator with the shared
:class:`BuildingContext`.
"""

import bmesh
import math
from mathutils import Vector, Matrix
from ..materials import MAT_INDEX_FLOOR
from ..shapes import compute_fl_wing_bounds
from ..interior import build_floor_slab, build_ceiling_beams
from . import build_sway_roof, build_gable_roof, build_conical_turret_roof, build_shingle_layers, build_valley_rafters, deck_top_z
from .details import (
    build_roof_dormers, build_roof_spire_turret,
    build_roof_clock_spire_pass, build_roof_chimney,
)


def _wing_loft_candidates(props, ctx, wings, found_h, floor_h, num_floors, wall_t,
                          roof_height, wing_roof_scale, is_rotated_roof, tier_val,
                          mini_sides, balc_side):
    """Outer-gable loft-hatch candidates on FRONT/BACK wings.

    Returns a list of ``(penalty, wing_index, loft_arg, loft_spec)``. Only the
    outer gable of each wing is used (the natural place for a ground ladder).
    """
    cands = []
    wing_floors = ctx.wing_floors
    w_top_fl = min(wing_floors, num_floors)
    w_fl_idx = w_top_fl - 1
    w_top_z = found_h + w_top_fl * floor_h
    w_roof_h = roof_height if wing_floors == num_floors else roof_height * wing_roof_scale
    if w_roof_h < 2.2:
        return cands
    for idx, w_elem in enumerate(wings):
        wall = w_elem.get('wall')
        if wall not in ('FRONT', 'BACK'):
            continue
        if 'bounds_fl' in w_elem and w_fl_idx in w_elem['bounds_fl']:
            x0b, x1b, y0b, y1b = w_elem['bounds_fl'][w_fl_idx]
        else:
            tb = ctx.floor_wall_bounds.get(w_fl_idx, (-ctx.base_w * 0.5, ctx.base_w * 0.5,
                                                      -ctx.base_d * 0.5, ctx.base_d * 0.5))
            ov = w_fl_idx * ctx.cantilever if getattr(props, 'has_cantilever', False) else 0.0
            x0b, x1b, y0b, y1b = compute_fl_wing_bounds(
                w_elem, w_fl_idx, ov, tb[0], tb[1], tb[2], tb[3])
        if x1b - x0b < 1.6:
            continue
        cx = (x0b + x1b) * 0.5
        loff = 0.30 if tier_val == 'TIER_1' else (wall_t * 0.5 + 0.03)
        sill = w_top_z + min(w_roof_h * 0.22, max(0.30, w_roof_h - 1.90))
        if sill + 1.20 > w_top_z + w_roof_h - 0.50:
            continue
        side = 'FRONT' if wall == 'FRONT' else 'BACK'
        face = y0b - loff if side == 'FRONT' else y1b + loff
        pen = 1.0
        if side in mini_sides:
            pen += 10.0
        if balc_side == side:
            pen += 6.0
        if getattr(props, 'has_arched_porch', False) and side == 'FRONT' and abs(cx) < 2.0:
            pen += 4.0
        if getattr(props, 'has_front_door', False) and side == 'FRONT' and abs(cx) < 2.0:
            pen += 3.0
        if getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == side:
            pen += 3.0
        arg = {'side': side, 'x0': cx - 0.45, 'x1': cx + 0.45, 'z0': sill, 'z1': sill + 1.20}
        spec = {'axis': 'Y', 'side': side, 'face': face, 'center': cx, 'sill': sill}
        cands.append((pen, idx, arg, spec))
    return cands


def build_roof_and_attic(bm, props, ctx):
    """Attic deck, exterior roof, dormers, chimneys, turrets and the roof hoist."""
    base_d = ctx.base_d
    base_w = ctx.base_w
    cantilever = ctx.cantilever
    effective_archetype = ctx.effective_archetype
    floor_h = ctx.floor_h
    floor_stair_holes = ctx.floor_stair_holes
    floor_wall_bounds = ctx.floor_wall_bounds
    found_h = ctx.found_h
    has_wing = ctx.has_wing
    num_floors = ctx.num_floors
    seed = ctx.seed
    total_height = ctx.total_height
    wall_t = ctx.wall_t
    wing_floors = ctx.wing_floors
    wings = ctx.wings

    # 4. Roof & Attic Level
    top_fl_idx = num_floors - 1
    top_x_min, top_x_max, top_y_min, top_y_max = floor_wall_bounds[top_fl_idx]
    top_w = top_x_max - top_x_min
    top_d = top_y_max - top_y_min
    top_hx = top_w * 0.5
    top_hy = top_d * 0.5
    top_cx = (top_x_min + top_x_max) * 0.5
    top_cy = (top_y_min + top_y_max) * 0.5
    top_z = found_h + num_floors * floor_h
    roof_style = props.roof_style
    
    # Attic floor plate (embedded into wall core with zero gap)
    build_floor_slab(
        bm,
        floor_idx=num_floors,
        x_min=top_x_min + 0.03, x_max=top_x_max - 0.03,
        y_min=top_y_min + 0.03, y_max=top_y_max - 0.03,
        z_level=top_z + 0.05,
        thickness=0.12,
        stair_hole=floor_stair_holes.get(num_floors, None),
        mat_idx=MAT_INDEX_FLOOR
    )
    
    tier_val = getattr(props, 'material_tier', 'TIER_3')
    plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')

    # Loft hatch resolved below by the roof builder. Initialised here so builds
    # that raise no gable/sway roof (watchtower, turret, round tower) leave them
    # defined for the later frame/ladder pass.
    _loft_spec = None
    _loft_arg = None
    _wing_loft = None

    # Defined for every archetype: watchtowers skip the main roof but still build
    # their wing roofs, which use the flare for their slope/valley math.
    flare_val = getattr(props, 'roof_flare', 0.35)
    is_rotated_roof = ctx.is_rotated_roof
    # Always define the dormer lists so the roof-detail phase calls below can be
    # evaluated for every archetype (watchtowers raise no main roof/dormers).
    dormer_placements = []
    wing_dormer_placements = []
    if effective_archetype != 'WATCHTOWER':
        # Exterior Roof Construction
        roof_orient = getattr(props, 'roof_orientation', 'FRONT_BACK')
        if roof_orient == 'AUTO':
            roof_orient = 'LEFT_RIGHT' if top_w > top_d * 1.15 else 'FRONT_BACK'
        is_rotated_roof = (roof_orient == 'LEFT_RIGHT' and roof_style in ('SWAY', 'GABLE'))
        # Loft hatch spec (world frame) plus the builder-local arg for the
        # main roof. Decided BEFORE the roof is built so the gable wall can
        # leave a real opening; the frame/leaf/ladder are added later at 4.5b.
        if getattr(props, 'has_loft_hatch', False) and effective_archetype != 'WATCHTOWER' \
                and roof_style in ('GABLE', 'SWAY'):
            _rh = max(1.6, getattr(props, 'roof_height', 3.0))
            _sill = top_z + min(_rh * 0.22, max(0.30, _rh - 1.90))
            _loff = 0.30 if tier_val == 'TIER_1' else (wall_t * 0.5 + 0.03)
            _hh2 = 0.45
            _wing_walls = [w.get('wall') for w in wings]
            _balc_side = getattr(props, 'balcony_side', None) if getattr(props, 'has_balcony', False) else None
            _mini_sides = {s for s, _o, _w, _d in ctx.mini_wing_spread.get(num_floors - 1, [])}
            def _gable_penalty(side):
                p = 0.0
                if side in _wing_walls:
                    p += 10.0
                if side in _mini_sides:
                    p += 10.0
                if _balc_side == side:
                    p += 6.0
                if getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == side:
                    p += 3.0
                if getattr(props, 'has_side_rampart', False) and getattr(props, 'rampart_side', 'RIGHT') == side:
                    p += 12.0
                if getattr(props, 'has_clock_tower', False) and getattr(props, 'clock_tower_side', 'RIGHT') == side:
                    p += 8.0
                if getattr(props, 'has_corner_turrets', False) and side == 'BACK':
                    p += 8.0
                if getattr(props, 'has_arched_porch', False) and side == 'FRONT':
                    p += 4.0
                if getattr(props, 'has_front_door', False) and side == 'FRONT':
                    p += 3.0
                return p

            if not is_rotated_roof:
                _lside = 'BACK' if _gable_penalty('BACK') <= _gable_penalty('FRONT') else 'FRONT'
                _lspan = top_x_max - top_x_min
                _lc = top_cx
                if _balc_side == _lside or _lside in _mini_sides:
                    _lc = _lc + min(1.2, _lspan * 0.15)
                _lc = min(top_x_max - 1.05, max(top_x_min + 1.05, _lc))
                _ov = getattr(props, 'roof_overhang', 0.6)
                _fl = getattr(props, 'roof_flare', 0.35)
                _hw = _lspan * 0.5 + _ov
                _u = min(1.0, abs(_lc + 0.50 - top_cx) / max(0.01, _hw))
                _dd = (1.0 - _fl) * _u + _fl * (1.0 - (1.0 - _u) ** 2)
                _deck_edge = top_z + _rh - _dd * (_rh + 0.10)
                if _lspan >= 2.6 and _sill + 1.20 <= _deck_edge - 0.30:
                    _lface = top_y_max + _loff if _lside == 'BACK' else top_y_min - _loff
                    _loft_spec = {'axis': 'Y', 'side': _lside, 'face': _lface, 'center': _lc, 'sill': _sill}
                    _loft_arg = {'side': _lside, 'x0': _lc - _hh2, 'x1': _lc + _hh2,
                                 'z0': _sill, 'z1': _sill + 1.20}
            else:
                _lside = 'RIGHT' if _gable_penalty('RIGHT') <= _gable_penalty('LEFT') else 'LEFT'
                _lspan = top_y_max - top_y_min
                _lc = top_cy
                if _balc_side == _lside or _lside in _mini_sides:
                    _lc = _lc + min(1.2, _lspan * 0.15)
                _lc = min(top_y_max - 1.05, max(top_y_min + 1.05, _lc))
                _ov = getattr(props, 'roof_overhang', 0.6)
                _fl = getattr(props, 'roof_flare', 0.35)
                _hw = _lspan * 0.5 + _ov
                _u = min(1.0, abs(_lc + 0.50 - top_cy) / max(0.01, _hw))
                _dd = (1.0 - _fl) * _u + _fl * (1.0 - (1.0 - _u) ** 2)
                _deck_edge = top_z + _rh - _dd * (_rh + 0.10)
                if _lspan >= 2.6 and _sill + 1.20 <= _deck_edge - 0.30:
                    _lface = top_x_max + _loff if _lside == 'RIGHT' else top_x_min - _loff
                    _loft_spec = {'axis': 'X', 'side': _lside, 'face': _lface, 'center': _lc, 'sill': _sill}
                    _ls = 'BACK' if _lside == 'RIGHT' else 'FRONT'
                    _loft_arg = {'side': _ls, 'x0': top_cy - (_lc + _hh2), 'x1': top_cy - (_lc - _hh2),
                                 'z0': _sill - top_z, 'z1': _sill + 1.20 - top_z}

            # If every main gable is obstructed, try a free wing gable instead.
            if _loft_spec is not None and _gable_penalty(_lside) > 0:
                _wcands = _wing_loft_candidates(
                    props, ctx, wings, found_h, floor_h, num_floors, wall_t,
                    props.roof_height, getattr(props, 'wing_roof_scale', 0.88),
                    is_rotated_roof, tier_val, _mini_sides, _balc_side)
                if _wcands:
                    _wcands.sort(key=lambda c: c[0])
                    _wpen, _widx, _warg, _wspec = _wcands[0]
                    if _wpen < _gable_penalty(_lside):
                        _wing_loft = {'idx': _widx, 'arg': _warg}
                        _loft_spec = _wspec
                        _loft_arg = None

        # Pre-compute dormer apertures to open attic holes in the roof deck and shingles
        dormer_apertures = []
        dormer_placements = []
        if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
            z_main_ridge = top_z + props.roof_height
            dormer_u = 0.58
            dormer_drop = (1.0 - flare_val) * dormer_u + flare_val * (1.0 - (1.0 - dormer_u) ** 2)
            slope_deck_z = z_main_ridge - dormer_drop * (props.roof_height + 0.10)
            z_dormer_base = slope_deck_z - 0.20
            
            # Scale dormer height so its ridge is guaranteed at least 0.35m below the main roof ridge
            max_dormer_total_h = max(1.10, (z_main_ridge - 0.35) - z_dormer_base)
            cur_dormer_h = min(1.00, max_dormer_total_h * 0.62)
            cur_dormer_roof_h = min(0.55, max_dormer_total_h * 0.38)
            d_rz = z_dormer_base + cur_dormer_h + cur_dormer_roof_h
            u_intersect = max(0.12, (z_main_ridge - d_rz) / max(0.5, props.roof_height))
            
            d_count = max(1, getattr(props, 'dormer_count', 2))
            d_sides = getattr(props, 'dormer_sides', 'BOTH')
            # Adaptive dormer width: shrinks only when crowded on small roofs (1.2m otherwise, no regression)
            main_dormer_w = 1.2

            if is_rotated_roof:
                roof_half_w = top_hy + props.roof_overhang
                reach_to_slope = (dormer_u - u_intersect) * roof_half_w
                dist_to_ridge = dormer_u * roof_half_w
                cur_dormer_reach = min(dist_to_ridge - 0.20, max(0.90, reach_to_slope + 0.14))

                if d_sides == 'FRONT_LEFT':
                    n_front, n_back = d_count, 0
                elif d_sides == 'BACK_RIGHT':
                    n_front, n_back = 0, d_count
                else: # 'BOTH'
                    n_front = (d_count + 1) // 2
                    n_back = d_count // 2

                x_margin = min(1.0, max(0.65, (top_hx * 2.0) * 0.16))
                x_start = top_x_min + x_margin
                x_end = top_x_max - x_margin
                x_span = max(0.2, x_end - x_start)
                # Clamp dormers per side so cheeks never overlap on small buildings (1.2m + 0.4m gap).
                # Large roofs are unaffected since the fit count exceeds the request.
                max_per_side_x = max(1, int((x_span + 0.3) / 1.6))
                n_front = min(n_front, max_per_side_x)
                n_back = min(n_back, max_per_side_x)
                tight_n_x = max(n_front, n_back, 1)
                if tight_n_x > 1:
                    main_dormer_w = min(1.2, max(0.85, (x_span / tight_n_x) - 0.35))

                if n_front == 1 and n_back == 1 and x_span >= 1.6:
                    fx = top_cx - x_span * 0.22
                    dormer_placements.append({'pos': (fx, top_cy - roof_half_w * dormer_u), 'facing': (0, -1), 'side': 1, 'loc_y': fx - top_cx})
                    bx = top_cx + x_span * 0.22
                    dormer_placements.append({'pos': (bx, top_cy + roof_half_w * dormer_u), 'facing': (0, 1), 'side': -1, 'loc_y': bx - top_cx})
                else:
                    for i in range(n_front):
                        fx = top_cx if n_front == 1 else (x_start + ((i + 0.5) / n_front) * x_span)
                        dormer_placements.append({'pos': (fx, top_cy - roof_half_w * dormer_u), 'facing': (0, -1), 'side': 1, 'loc_y': fx - top_cx})
                    for i in range(n_back):
                        bx = top_cx if n_back == 1 else (x_start + ((i + 0.5) / n_back) * x_span)
                        dormer_placements.append({'pos': (bx, top_cy + roof_half_w * dormer_u), 'facing': (0, 1), 'side': -1, 'loc_y': bx - top_cx})

                # Roof deck is kept solid under dormers (no cell skipping) so small roofs
                # never open gap holes; cheeks penetrate the slope for a watertight seam.
                ap_half = max(0.24, main_dormer_w * 0.5 - 0.18)
                for dp in dormer_placements:
                    dormer_apertures.append({
                        'side': dp['side'],
                        'y_min': dp['loc_y'] - ap_half,
                        'y_max': dp['loc_y'] + ap_half,
                        'u_min': max(0.25, u_intersect + 0.04),
                        'u_max': min(0.70, dormer_u + 0.08)
                    })
            else:
                roof_half_w = top_hx + props.roof_overhang
                reach_to_slope = (dormer_u - u_intersect) * roof_half_w
                # Penetrate 14cm into slope for a watertight seam, but stop at least 20cm before the ridge
                dist_to_ridge = dormer_u * roof_half_w
                cur_dormer_reach = min(dist_to_ridge - 0.20, max(0.90, reach_to_slope + 0.14))

                if d_sides == 'FRONT_LEFT':
                    n_left, n_right = d_count, 0
                elif d_sides == 'BACK_RIGHT':
                    n_left, n_right = 0, d_count
                else: # 'BOTH'
                    n_left = (d_count + 1) // 2
                    n_right = d_count // 2

                y_margin = min(1.0, max(0.65, (top_hy * 2.0) * 0.16))
                y_start = top_y_min + y_margin
                y_end = top_y_max - y_margin
                y_span = max(0.2, y_end - y_start)
                # Same overlap guard for the standard orientation (see rotated branch above).
                max_per_side_y = max(1, int((y_span + 0.3) / 1.6))
                n_left = min(n_left, max_per_side_y)
                n_right = min(n_right, max_per_side_y)
                tight_n_y = max(n_left, n_right, 1)
                if tight_n_y > 1:
                    main_dormer_w = min(1.2, max(0.85, (y_span / tight_n_y) - 0.35))

                if n_left == 1 and n_right == 1 and y_span >= 1.6:
                    ly = top_cy + y_span * 0.22
                    dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, ly), 'facing': (-1, 0), 'side': -1})
                    ry = top_cy - (y_span * 0.25 if props.has_chimney else y_span * 0.22)
                    dormer_placements.append({'pos': (top_cx + roof_half_w * dormer_u, ry), 'facing': (1, 0), 'side': 1})
                else:
                    for i in range(n_left):
                        ly = top_cy if n_left == 1 else (y_start + ((i + 0.5) / n_left) * y_span)
                        dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, ly), 'facing': (-1, 0), 'side': -1})
                    for i in range(n_right):
                        ry = top_cy if n_right == 1 else (y_start + ((i + 0.5) / n_right) * y_span)
                        dormer_placements.append({'pos': (top_cx + roof_half_w * dormer_u, ry), 'facing': (1, 0), 'side': 1})

                ap_half = max(0.24, main_dormer_w * 0.5 - 0.18)
                for dp in dormer_placements:
                    d_cx, d_cy = dp['pos']
                    dormer_apertures.append({
                        'side': dp['side'],
                        'y_min': d_cy - ap_half,
                        'y_max': d_cy + ap_half,
                        'u_min': max(0.25, u_intersect + 0.04),
                        'u_max': min(0.70, dormer_u + 0.08)
                    })

        # Eave exclusions for equal-floor wings so eave fascia beams don't slice through wing roofs
        eave_ex = {'min': [], 'max': []}
        if has_wing and wing_floors == num_floors:
            for w_elem in wings:
                ww = w_elem['wall']
                w_idx = min(wing_floors, num_floors) - 1
                if 'bounds_fl' in w_elem and w_idx in w_elem['bounds_fl']:
                    wb = w_elem['bounds_fl'][w_idx]
                else:
                    wb = (w_elem.get('x_min', 0.0), w_elem.get('x_max', 0.0), w_elem.get('y_min', 0.0), w_elem.get('y_max', 0.0))
                wx1, wx2, wy1, wy2 = wb
                if is_rotated_roof:
                    # Rotated roof: local X is (-top_hy to top_hy), local Y is (-top_hx to top_hx)
                    # rx_max (+X local) rotates to -Y (FRONT facade in world space)
                    # rx_min (-X local) rotates to +Y (BACK facade in world space)
                    # local Y is (world_x - top_cx)
                    ly1 = (wx1 - props.roof_overhang * 0.4) - top_cx
                    ly2 = (wx2 + props.roof_overhang * 0.4) - top_cx
                    if ww == 'FRONT':
                        eave_ex['max'].append((ly1, ly2))
                    elif ww == 'BACK':
                        eave_ex['min'].append((ly1, ly2))
                    elif ww in ('LEFT', 'RIGHT'):
                        # Flush side wing: main eave overhang corner would cross the
                        # wing facade, so break the eave at the wing span.
                        if wy1 <= top_y_min + 0.35:
                            eave_ex['max'].append((ly1, ly2))
                        if wy2 >= top_y_max - 0.35:
                            eave_ex['min'].append((ly1, ly2))
                else:
                    # Non-rotated roof: rx_min is LEFT facade, rx_max is RIGHT facade
                    ly1 = (wy1 - props.roof_overhang * 0.4)
                    ly2 = (wy2 + props.roof_overhang * 0.4)
                    if ww == 'LEFT':
                        eave_ex['min'].append((ly1, ly2))
                    elif ww == 'RIGHT':
                        eave_ex['max'].append((ly1, ly2))
                    elif ww in ('FRONT', 'BACK'):
                        # Flush front/back wing: break the side eave at the wing span.
                        if wx2 >= top_x_max - 0.35:
                            eave_ex['max'].append((ly1, ly2))
                        if wx1 <= top_x_min + 0.35:
                            eave_ex['min'].append((ly1, ly2))

        if roof_style in ('SWAY', 'GABLE'):
            roof_bm = bmesh.new()
            if is_rotated_roof:
                if roof_style == 'SWAY':
                    build_sway_roof(
                        roof_bm,
                        x_min=-top_hy, x_max=top_hy,
                        loft_hatch=_loft_arg,
                        y_min=-top_hx, y_max=top_hx,
                        z_base=0.0,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway,
                        wall_thickness=wall_t,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                else: # 'GABLE'
                    build_gable_roof(
                        roof_bm,
                        x_min=-top_hy, x_max=top_hy,
                        loft_hatch=_loft_arg,
                        y_min=-top_hx, y_max=top_hx,
                        z_base=0.0,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        segments_y=6,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                rot_m = Matrix.Rotation(-math.pi * 0.5, 4, 'Z')
                trans_m = Matrix.Translation(Vector((top_cx, top_cy, top_z)))
                bmesh.ops.transform(roof_bm, matrix=trans_m @ rot_m, verts=roof_bm.verts)
            else:
                if roof_style == 'SWAY':
                    build_sway_roof(
                        roof_bm,
                        x_min=top_x_min, x_max=top_x_max,
                        loft_hatch=_loft_arg,
                        y_min=top_y_min, y_max=top_y_max,
                        z_base=top_z,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway,
                        wall_thickness=wall_t,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                else:
                    build_gable_roof(
                        roof_bm,
                        x_min=top_x_min, x_max=top_x_max,
                        loft_hatch=_loft_arg,
                        y_min=top_y_min, y_max=top_y_max,
                        z_base=top_z,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        segments_y=6,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )

            uv_src = roof_bm.loops.layers.uv.verify()
            uv_dst = bm.loops.layers.uv.verify()
            vert_map = {v: bm.verts.new(v.co) for v in roof_bm.verts}
            for f in roof_bm.faces:
                try:
                    new_f = bm.faces.new([vert_map[v] for v in f.verts])
                    new_f.material_index = f.material_index
                    new_f.smooth = f.smooth
                    for l_src, l_dst in zip(f.loops, new_f.loops):
                        l_dst[uv_dst].uv = l_src[uv_src].uv
                except ValueError:
                    pass
            roof_bm.free()
        elif roof_style == 'TURRET':
            radius = max(top_hx, top_hy) * 1.05
            build_conical_turret_roof(
                bm,
                center_pos=(top_cx, top_cy, top_z),
                radius=radius,
                height=props.roof_height * 1.3
            )
        if getattr(props, 'has_hoist_beam', False) and roof_style in ('SWAY', 'GABLE'):
            from .features import build_hoist_beam
            if is_rotated_roof:
                hoist_bm = bmesh.new()
                build_hoist_beam(
                    hoist_bm,
                    front_x=0.0,
                    front_y=0.0,
                    z_ridge=0.0,
                    length=1.4
                )
                rot_m = Matrix.Rotation(-math.pi * 0.5, 4, 'Z')
                trans_m = Matrix.Translation(Vector((top_x_min - props.roof_overhang, top_cy, top_z + props.roof_height)))
                bmesh.ops.transform(hoist_bm, matrix=trans_m @ rot_m, verts=hoist_bm.verts)
                uv_src = hoist_bm.loops.layers.uv.verify()
                uv_dst = bm.loops.layers.uv.verify()
                vmap = {v: bm.verts.new(v.co) for v in hoist_bm.verts}
                for f in hoist_bm.faces:
                    try:
                        nf = bm.faces.new([vmap[v] for v in f.verts])
                        nf.material_index = f.material_index
                        nf.smooth = f.smooth
                        for ls, ld in zip(f.loops, nf.loops):
                            ld[uv_dst].uv = ls[uv_src].uv
                    except ValueError:
                        pass
                hoist_bm.free()
            else:
                build_hoist_beam(
                    bm,
                    front_x=top_cx,
                    front_y=top_y_min - props.roof_overhang,
                    z_ridge=top_z + props.roof_height,
                    length=1.4
                )
            
        # Physical shingle layers disabled: textured roof deck provides stylized clay tiles cleanly without micro-geometry
        if False and props.has_roof_shingles and roof_style in ('SWAY', 'GABLE'):
            build_shingle_layers(
                bm,
                x_min=top_x_min, x_max=top_x_max,
                y_min=top_y_min, y_max=top_y_max,
                z_base=top_z,
                roof_height=props.roof_height,
                rows=props.shingle_rows,
                seed=seed,
                overhang=props.roof_overhang,
                sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0,
                roof_style=roof_style,
                roof_flare=flare_val,
                dormer_apertures=dormer_apertures
            )

    # Compound Shape Wing Roof (Cross-Gable intersecting main roof or upper facade)
    wing_dormer_placements = []
    if has_wing:
        w_top_fl = min(wing_floors, num_floors)
        is_lower_wing = (wing_floors < num_floors)
        w_fl_idx = w_top_fl - 1
        w_top_z = found_h + w_top_fl * floor_h
        _wr_scale = getattr(props, 'wing_roof_scale', 0.88)
        w_roof_h = props.roof_height if (wing_floors == num_floors) else (props.roof_height * _wr_scale)

        if is_lower_wing:
            if props.has_cantilever:
                if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                    up_fl_overhang = cantilever if w_top_fl >= 1 else 0.0
                else:
                    up_fl_overhang = w_top_fl * cantilever
            else:
                up_fl_overhang = 0.0
            up_main_hx = (base_w + up_fl_overhang * 2.0) * 0.5
            up_main_hy = (base_d + up_fl_overhang * 2.0) * 0.5
            up_front_y = -up_main_hy
            up_back_y = up_main_hy

        for _w_idx, w_elem in enumerate(wings):
            w_wall = w_elem['wall']
            w_loft_arg = _wing_loft['arg'] if (_wing_loft and _wing_loft['idx'] == _w_idx) else None
            if 'bounds_fl' in w_elem and w_fl_idx in w_elem['bounds_fl']:
                w_top_xmin, w_top_xmax, w_top_ymin, w_top_ymax = w_elem['bounds_fl'][w_fl_idx]
            else:
                top_b = floor_wall_bounds.get(w_fl_idx, (-base_w*0.5, base_w*0.5, -base_d*0.5, base_d*0.5))
                w_top_xmin, w_top_xmax, w_top_ymin, w_top_ymax = compute_fl_wing_bounds(
                    w_elem, w_fl_idx,
                    (w_fl_idx * cantilever if props.has_cantilever else 0.0),
                    top_b[0], top_b[1], top_b[2], top_b[3]
                )

            if is_lower_wing or (not is_lower_wing and has_wing):
                # Interior ceiling slab for the wing (enclosing the wing interior from above).
                # Equal-height wings get one too so rooms never see open roof/dark attic.
                # Level matches the main attic slab (top at +0.05) so eave decks hide
                # inside slab depth instead of banding across ceilings.
                ceil_z = (w_top_z - 0.02) if is_lower_wing else (w_top_z + 0.05)
                ceil_t = 0.10 if is_lower_wing else 0.12
                build_floor_slab(
                    bm,
                    floor_idx=w_top_fl,
                    x_min=w_top_xmin + 0.02,
                    x_max=w_top_xmax - 0.02,
                    y_min=w_top_ymin + 0.02,
                    y_max=w_top_ymax - 0.02,
                    z_level=ceil_z,
                    thickness=ceil_t,
                    stair_hole=None,
                    mat_idx=MAT_INDEX_FLOOR
                )
                if props.has_ceiling_beams:
                    build_ceiling_beams(
                        bm,
                        x_min=w_top_xmin + wall_t,
                        x_max=w_top_xmax - wall_t,
                        y_min=w_top_ymin + wall_t,
                        y_max=w_top_ymax - wall_t,
                        z_ceil=ceil_z,
                        spacing=1.2
                    )

            # Pre-compute wing roof dormer apertures and placements
            w_dormer_apertures = []
            do_wing_dormers = (
                props.has_dormers and
                getattr(props, 'has_wing_dormers', True) and
                roof_style in ('SWAY', 'GABLE') and
                effective_archetype != 'WATCHTOWER'
            )
            w_d_sides = getattr(props, 'wing_dormer_sides', 'BOTH')
            w_d_target_count = max(1, getattr(props, 'wing_dormer_count', 1))
            w_sway = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0

            z_w_ridge = w_top_z + w_roof_h
            w_dormer_u = 0.58
            w_dormer_drop = (1.0 - flare_val) * w_dormer_u + flare_val * (1.0 - (1.0 - w_dormer_u) ** 2)
            w_slope_deck_z = z_w_ridge - w_dormer_drop * (w_roof_h + 0.10)
            # Raised 0.16 above the main-roof formula so cheeks/floor stay above the
            # wing ceiling line and never hang into the rooms below.
            z_w_dormer_base = w_slope_deck_z - 0.04

            max_w_d_total_h = max(0.95, (z_w_ridge - 0.28) - z_w_dormer_base)
            w_cur_d_h = min(0.85, max_w_d_total_h * 0.60)
            w_cur_d_roof_h = min(0.48, max_w_d_total_h * 0.40)
            w_d_rz = z_w_dormer_base + w_cur_d_h + w_cur_d_roof_h
            w_u_intersect = max(0.12, (z_w_ridge - w_d_rz) / max(0.4, w_roof_h))

            if w_wall == 'FRONT':
                if is_lower_wing:
                    w_roof_ymax = up_front_y + 0.04
                    abut_back = True
                elif is_rotated_roof:
                    # Perpendicular junction (valley): extend into the main slope.
                    # Deck past the valley lines is notch-cut in the builder.
                    w_roof_ymax = top_cy
                    abut_back = True
                else:
                    # Parallel ridges (gable-to-gable): stop flush in the main gable
                    # wall core so no tiles cross plaster outside or bands indoors.
                    w_roof_ymax = top_y_min + 0.12
                    abut_back = True

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_roof_half_w = (w_top_xmax - w_top_xmin) * 0.5 + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, (w_top_xmax - w_top_xmin) * 0.28))

                if do_wing_dormers:
                    # Pulled back from outer eave corner (1.10) and main valley corner
                    # (1.40) so dormers never crowd corners.
                    y_start = w_top_ymin + 1.10
                    y_end = w_roof_ymax - 1.40
                    if not is_lower_wing and is_rotated_roof:
                        # Valley-notched deck: dormers must sit fully outside the main
                        # wall on intact deck, never over the cut triangle.
                        y_end = min(y_end, top_y_min - 0.25)
                    y_span = y_end - y_start
                    if y_span >= 0.60:
                        if w_cx < top_cx - 0.2:
                            outer_s, inner_s = -1, 1
                        elif w_cx > top_cx + 0.2:
                            outer_s, inner_s = 1, -1
                        else:
                            outer_s, inner_s = None, None

                        if w_d_sides == 'OUTER' and outer_s is not None:
                            slopes = [outer_s]
                        elif w_d_sides == 'INNER' and inner_s is not None:
                            slopes = [inner_s]
                        else:
                            slopes = [-1, 1]

                        for s in slopes:
                            # 1.6m pitch + width shrink so neighbouring cheeks never overlap.
                            k = min(w_d_target_count, max(1, int((y_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (y_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_y = (y_start + y_end) * 0.5 if k == 1 else (y_start + ((i + 0.5) / k) * y_span)
                                d_x = w_cx + s * w_roof_half_w * w_dormer_u
                                facing = (-1, 0) if s == -1 else (1, 0)
                                w_dormer_apertures.append({
                                    'side': s,
                                    'y_min': d_y - ap_half,
                                    'y_max': d_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                # Perpendicular: open valley (outer gable only, deck notch-cut past
                # valley lines). Parallel: finished gable abutting the main gable.
                w_gable_fb = ('FRONT',) if (is_lower_wing or is_rotated_roof) else ('FRONT', 'BACK')
                # Trim side eave fascia where it would enter main timber/walls.
                w_eave_fb = None
                if is_lower_wing:
                    w_eave_fb = None
                elif is_rotated_roof:
                    # Deep valley: no side fascia past the main wall face.
                    trim = [(top_y_min - 0.10, w_roof_ymax + 0.60)]
                    w_eave_fb = {'min': list(trim), 'max': list(trim)}

                w_notch_side = 'BOTH'

                # Parallel flush case: fascia ends die inside the gable core, no trim.
                w_notch_fb = None
                if not is_lower_wing and is_rotated_roof:
                    w_notch_fb = {
                        'apex_x': w_cx,
                        'apex_y': top_cy,
                        'half_width': w_roof_half_w,
                        'base_y': top_y_min - props.roof_overhang,
                        'keep': 'le',
                        'overlap': 0.02,
                        'side': w_notch_side
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_top_ymin, y_max=w_roof_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_fb,
                        loft_hatch=w_loft_arg,
                        abut_back=abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_fb,
                        valley_notch=w_notch_fb
                    )
                else:
                    build_gable_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_top_ymin, y_max=w_roof_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_fb,
                        loft_hatch=w_loft_arg,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_back=abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_fb,
                        valley_notch=w_notch_fb
                    )

                if not is_lower_wing and is_rotated_roof:
                    # Segmented valley flashing: samples both deck profiles along the
                    # plan line so every notch step is covered (no slits/holes).
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _tc=(top_cx, top_cy), _th=top_hy, _ov=_ov,
                                 _ez=_ezm, _sw=_swm):
                        _lx = _tc[1] - py
                        _ly = px - _tc[0]
                        return deck_top_z(_lx, _ly, 0.0, _th + _ov, 0.0,
                                          props.roof_height, flare_val, _sw,
                                          -top_hx - _ov, top_hx + _ov, _ez - top_z,
                                          top_off=0.05) + top_z
                    _ezw = (w_top_z - 0.12) if roof_style == 'SWAY' else (w_top_z - 0.10)
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    def _wing_fn(px, py, _wx=w_cx, _wh=w_roof_half_w, _wz=w_top_z,
                                 _wr=w_roof_h, _wy0=w_top_ymin - _ov, _wy1=w_roof_ymax,
                                 _ez=_ezw, _sw=_sww):
                        return deck_top_z(px, py, _wx, _wh, _wz, _wr,
                                          flare_val, _sw, _wy0, _wy1, _ez,
                                          top_off=0.05)
                    valley_feet = [w_top_xmin - _ov, w_top_xmax + _ov]
                    for vx in valley_feet:
                        build_valley_rafters(bm, (vx, top_y_min - _ov), (w_cx, top_cy),
                                             _main_fn, _wing_fn)

            elif w_wall == 'BACK':
                if is_lower_wing:
                    w_roof_ymin = up_back_y - 0.04
                    abut_front = True
                elif is_rotated_roof:
                    # Perpendicular junction (valley): see FRONT.
                    w_roof_ymin = top_cy
                    abut_front = True
                else:
                    # Parallel ridges (gable-to-gable): flush in the wall core.
                    w_roof_ymin = top_y_max - 0.12
                    abut_front = True

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_roof_half_w = (w_top_xmax - w_top_xmin) * 0.5 + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, (w_top_xmax - w_top_xmin) * 0.28))

                if do_wing_dormers:
                    # Main valley corner first (1.40), outer eave corner 1.10.
                    y_start = w_roof_ymin + 1.40
                    y_end = w_top_ymax - 1.10
                    if not is_lower_wing and is_rotated_roof:
                        # See FRONT: keep dormers outside the wall on intact deck.
                        y_start = max(y_start, top_y_max + 0.25)
                    y_span = y_end - y_start
                    if y_span >= 0.60:
                        if w_cx < top_cx - 0.2:
                            outer_s, inner_s = -1, 1
                        elif w_cx > top_cx + 0.2:
                            outer_s, inner_s = 1, -1
                        else:
                            outer_s, inner_s = None, None

                        if w_d_sides == 'OUTER' and outer_s is not None:
                            slopes = [outer_s]
                        elif w_d_sides == 'INNER' and inner_s is not None:
                            slopes = [inner_s]
                        else:
                            slopes = [-1, 1]

                        for s in slopes:
                            # Same 1.6m anti-overlap pitch as FRONT (see above).
                            k = min(w_d_target_count, max(1, int((y_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (y_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_y = (y_start + y_end) * 0.5 if k == 1 else (y_start + ((i + 0.5) / k) * y_span)
                                d_x = w_cx + s * w_roof_half_w * w_dormer_u
                                facing = (-1, 0) if s == -1 else (1, 0)
                                w_dormer_apertures.append({
                                    'side': s,
                                    'y_min': d_y - ap_half,
                                    'y_max': d_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                w_gable_bk = ('BACK',) if (is_lower_wing or is_rotated_roof) else ('FRONT', 'BACK')
                w_eave_bk = None
                if is_lower_wing:
                    w_eave_bk = None
                elif is_rotated_roof:
                    trim = [(w_roof_ymin - 0.60, top_y_max + 0.10)]
                    w_eave_bk = {'min': list(trim), 'max': list(trim)}

                w_notch_side = 'BOTH'

                w_notch_bk = None
                if not is_lower_wing and is_rotated_roof:
                    w_notch_bk = {
                        'apex_x': w_cx,
                        'apex_y': top_cy,
                        'half_width': w_roof_half_w,
                        'base_y': top_y_max + props.roof_overhang,
                        'keep': 'ge',
                        'overlap': 0.02,
                        'side': w_notch_side
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_roof_ymin, y_max=w_top_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_bk,
                        loft_hatch=w_loft_arg,
                        abut_front=abut_front,
                        abut_back=False,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_bk,
                        valley_notch=w_notch_bk
                    )
                else:
                    build_gable_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_roof_ymin, y_max=w_top_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_bk,
                        loft_hatch=w_loft_arg,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_front=abut_front,
                        abut_back=False,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_bk,
                        valley_notch=w_notch_bk
                    )

                if not is_lower_wing and is_rotated_roof:
                    # Segmented valley flashing (see FRONT).
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _tc=(top_cx, top_cy), _th=top_hy, _ov=_ov,
                                 _ez=_ezm, _sw=_swm):
                        _lx = _tc[1] - py
                        _ly = px - _tc[0]
                        return deck_top_z(_lx, _ly, 0.0, _th + _ov, 0.0,
                                          props.roof_height, flare_val, _sw,
                                          -top_hx - _ov, top_hx + _ov, _ez - top_z,
                                          top_off=0.05) + top_z
                    _ezw = (w_top_z - 0.12) if roof_style == 'SWAY' else (w_top_z - 0.10)
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    def _wing_fn(px, py, _wx=w_cx, _wh=w_roof_half_w, _wz=w_top_z,
                                 _wr=w_roof_h, _wy0=w_roof_ymin, _wy1=w_top_ymax + _ov,
                                 _ez=_ezw, _sw=_sww):
                        return deck_top_z(px, py, _wx, _wh, _wz, _wr,
                                          flare_val, _sw, _wy0, _wy1, _ez,
                                          top_off=0.05)
                    valley_feet = [w_top_xmin - _ov, w_top_xmax + _ov]

                    for vx in valley_feet:
                        build_valley_rafters(bm, (vx, top_y_max + _ov), (w_cx, top_cy),
                                             _main_fn, _wing_fn)

            elif w_wall in ('LEFT', 'RIGHT'):
                w_ridge_len = w_top_xmax - w_top_xmin
                w_span_y = w_top_ymax - w_top_ymin
                wing_roof_bm = bmesh.new()
                lx_half = w_span_y * 0.5
                ly_half = (w_ridge_len + 0.04) * 0.5 if is_rotated_roof else (w_ridge_len * 0.5)

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_cy = (w_top_ymin + w_top_ymax) * 0.5
                if is_lower_wing or is_rotated_roof:
                    # Lower wings abut the facade; rotated (parallel ridges) stop flush
                    # in the main gable wall core.
                    loc_abut_back = True
                    y_max_adj = 0.04
                else:
                    # Perpendicular equal junction: run the ridge to the main ridge so
                    # valleys die into the slope (cross-hipped U/L, cf. FRONT rotated).
                    # Flush open tip (no overhang past the ridge, no cap face).
                    loc_abut_back = True
                    serve_dist = abs(top_cx - w_cx)
                    y_max_adj = max(0.25, serve_dist - ly_half)
                w_roof_half_w = lx_half + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, w_span_y * 0.28))

                if do_wing_dormers:
                    # Outer corner 1.10, main valley corner 1.40 (main side is east
                    # for LEFT wings, west for RIGHT wings).
                    if w_wall == 'LEFT':
                        x_start = w_top_xmin + 1.10
                        x_end = w_top_xmax - 1.40
                        if not is_lower_wing and not is_rotated_roof:
                            # Notched deck: keep dormers outside the wall line.
                            x_end = min(x_end, top_x_min - 0.25)
                    else: # 'RIGHT'
                        x_start = w_top_xmin + 1.40
                        x_end = w_top_xmax - 1.10
                        if not is_lower_wing and not is_rotated_roof:
                            x_start = max(x_start, top_x_max + 0.25)
                    x_span = x_end - x_start

                    if x_span >= 0.60:
                        if w_cy < top_cy - 0.2:
                            outer_sw, inner_sw = -1, 1
                        elif w_cy > top_cy + 0.2:
                            outer_sw, inner_sw = 1, -1
                        else:
                            outer_sw, inner_sw = None, None

                        if w_d_sides == 'OUTER' and outer_sw is not None:
                            slopes_world = [outer_sw]
                        elif w_d_sides == 'INNER' and inner_sw is not None:
                            slopes_world = [inner_sw]
                        else:
                            slopes_world = [-1, 1]

                        for sw in slopes_world:
                            k = min(w_d_target_count, max(1, int((x_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (x_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_x = (x_start + x_end) * 0.5 if k == 1 else (x_start + ((i + 0.5) / k) * x_span)
                                d_y = w_cy + sw * w_roof_half_w * w_dormer_u
                                facing = (0, -1) if sw == -1 else (0, 1)

                                if w_wall == 'LEFT':
                                    local_side = -1 if sw == -1 else 1
                                    loc_y = d_x - w_cx
                                else: # 'RIGHT'
                                    local_side = 1 if sw == -1 else -1
                                    loc_y = w_cx - d_x

                                w_dormer_apertures.append({
                                    'side': local_side,
                                    'y_min': loc_y - ap_half,
                                    'y_max': loc_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                # Parallel (rotated): finished gable abuts main gable. Perpendicular
                # (non-rotated): open valley, deck notch-cut (local coords).
                w_gable_lr = ('FRONT',) if (is_lower_wing or not is_rotated_roof) else ('FRONT', 'BACK')
                # Local-coord fascia trim (see FRONT/BACK above).
                w_eave_lr = None
                if is_lower_wing:
                    w_eave_lr = None
                elif not is_rotated_roof:
                    y_top_local = ly_half + y_max_adj
                    if w_wall == 'LEFT':
                        wall_local = top_x_min - w_cx
                    else:
                        wall_local = w_cx - top_x_max
                    trim = [(wall_local - 0.10, y_top_local + 0.60)]
                    w_eave_lr = {'min': list(trim), 'max': list(trim)}

                w_notch_side_lr = 'BOTH'

                w_notch_lr = None
                if not is_lower_wing and not is_rotated_roof:
                    w_notch_lr = {
                        'apex_x': 0.0,
                        'apex_y': ly_half + y_max_adj,
                        'half_width': lx_half + props.roof_overhang,
                        'base_y': ((top_x_min - w_cx) if w_wall == 'LEFT' else (w_cx - top_x_max)) - props.roof_overhang,
                        'keep': 'le',
                        'overlap': 0.02,
                        'side': w_notch_side_lr
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        wing_roof_bm,
                        x_min=-lx_half, x_max=lx_half,
                        y_min=-ly_half, y_max=ly_half + y_max_adj,
                        z_base=0.0,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_lr,
                        abut_back=loc_abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_lr,
                        valley_notch=w_notch_lr
                    )
                else:
                    build_gable_roof(
                        wing_roof_bm,
                        x_min=-lx_half, x_max=lx_half,
                        y_min=-ly_half, y_max=ly_half + y_max_adj,
                        z_base=0.0,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_lr,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_back=loc_abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_lr,
                        valley_notch=w_notch_lr
                    )

                rot_ang = -math.pi * 0.5 if w_wall == 'LEFT' else math.pi * 0.5
                rot_m = Matrix.Rotation(rot_ang, 4, 'Z')
                trans_m = Matrix.Translation(Vector((w_cx, w_cy, w_top_z)))
                bmesh.ops.transform(wing_roof_bm, matrix=trans_m @ rot_m, verts=wing_roof_bm.verts)

                uv_src = wing_roof_bm.loops.layers.uv.verify()
                uv_dst = bm.loops.layers.uv.verify()
                vert_map = {v: bm.verts.new(v.co) for v in wing_roof_bm.verts}
                for f in wing_roof_bm.faces:
                    try:
                        new_f = bm.faces.new([vert_map[v] for v in f.verts])
                        new_f.material_index = f.material_index
                        new_f.smooth = f.smooth
                        for l_src, l_dst in zip(f.loops, new_f.loops):
                            l_dst[uv_dst].uv = l_src[uv_src].uv
                    except ValueError:
                        pass
                wing_roof_bm.free()

                # Segmented valley flashing for the perpendicular (non-rotated) equal
                # junction (see FRONT): samples both deck profiles, no slits/holes.
                if not is_lower_wing and not is_rotated_roof and roof_style in ('SWAY', 'GABLE'):
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _cx=top_cx, _hw=top_hx + _ov, _zb=top_z,
                                 _wr=props.roof_height, _ry0=top_y_min - _ov,
                                 _ry1=top_y_max + _ov, _ez=_ezm, _sw=_swm):
                        return deck_top_z(px, py, _cx, _hw, _zb, _wr,
                                          flare_val, _sw, _ry0, _ry1, _ez,
                                          top_off=0.05)
                    _ezw = -0.12 if roof_style == 'SWAY' else -0.10
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    _ly1 = ly_half + y_max_adj
                    if w_wall == 'LEFT':
                        def _wing_fn(px, py, _wc=(w_cx, w_cy), _hw=lx_half + _ov,
                                     _wz=w_top_z, _wr=w_roof_h, _ry0=-ly_half - _ov,
                                     _ry1=_ly1, _ez=_ezw, _sw=_sww):
                            return deck_top_z(-(py - _wc[1]), (px - _wc[0]), 0.0, _hw,
                                              0.0, _wr, flare_val, _sw, _ry0, _ry1,
                                              _ez, top_off=0.05) + _wz
                        die = (w_cx + _ly1, w_cy)
                    else:
                        def _wing_fn(px, py, _wc=(w_cx, w_cy), _hw=lx_half + _ov,
                                     _wz=w_top_z, _wr=w_roof_h, _ry0=-ly_half - _ov,
                                     _ry1=_ly1, _ez=_ezw, _sw=_sww):
                            return deck_top_z((py - _wc[1]), -(px - _wc[0]), 0.0, _hw,
                                              0.0, _wr, flare_val, _sw, _ry0, _ry1,
                                              _ez, top_off=0.05) + _wz
                        die = (w_cx - _ly1, w_cy)
                    if w_wall == 'LEFT':
                        corners = [(top_x_min - _ov, w_top_ymin - _ov), (top_x_min - _ov, w_top_ymax + _ov)]
                    else:
                        corners = [(top_x_max + _ov, w_top_ymin - _ov), (top_x_max + _ov, w_top_ymax + _ov)]
                    for cx0, cy0 in corners:
                        build_valley_rafters(bm, (cx0, cy0), die,
                                             _main_fn, _wing_fn)

    # Dormer Windows
    if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
        build_roof_dormers(bm, props, effective_archetype, roof_style,
                           dormer_placements, wing_dormer_placements,
                           z_dormer_base, main_dormer_w, cur_dormer_h,
                           cur_dormer_roof_h, cur_dormer_reach, flare_val)

    # Fairytale Roof Spire Turret (Positionable across roof pitch with attic penetration)
    build_roof_spire_turret(bm, props, effective_archetype, roof_style,
                            is_rotated_roof, top_hx, top_hy, top_cx, top_cy,
                            top_x_min, top_y_min, top_z, flare_val)

    # Roof-mounted clock spire (Tier 1 small / Tier 2 bigger town hall clocks).
    build_roof_clock_spire_pass(bm, props, effective_archetype, roof_style,
                                is_rotated_roof, top_hx, top_hy, top_cx, top_cy,
                                top_x_min, top_y_min, top_z, flare_val)

    # Stylized Crooked Chimney - user-controlled, avoids pillared outdoors & dormers
    build_roof_chimney(bm, props, effective_archetype,
                       dormer_placements, wing_dormer_placements,
                       top_cx, top_cy, top_hx, top_hy,
                       top_x_min, top_x_max, top_y_min, top_y_max, total_height)

    ctx.top_z = top_z
    ctx.top_hx = top_hx
    ctx.top_hy = top_hy
    return _loft_spec
