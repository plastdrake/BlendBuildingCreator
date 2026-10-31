"""
Generic attached side annex.

A 1-2 storey half-timbered volume embedded into a main building's side wall, with
its own perpendicular cross-gable roof, cut-out windows, corner boards and an
upper oriel bay. Originally written for the Town Hall; now reusable by any
preset (town hall, taverns, inns, ...) via ``has_side_annex``.
"""

import math
import bmesh
from mathutils import Vector, Matrix

from ..mesh_utils import create_beveled_box
from ..walls import build_facade_timber, build_wall_with_opening
from ..openings import build_window_assembly
from ..roof.gable_roof import build_gable_roof
from ..roof.valley import build_valley_rafters, deck_top_z
from ..interior import build_interior_trims
from ..style import tier_wall_mat, get_effective_wall_material, get_effective_roof_material
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_FLOOR,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER,
)
from .mini_wing import build_mini_wing


GABLE_WINDOW_INSET = 0.15


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build_side_annex(bm, side_sgn, main_hx, main_cy0, main_cy1, z_ground=0.0,
                     found_h=0.6, floors=2, floor_h=3.0, tier='TIER_3',
                     width=5.2, depth=4.0, roof_h=3.0, plank_direction='VERTICAL',
                     main_bounds_by_floor=None, timber_framing=True, diagonals=True,
                      main_roof=None, props=None, portal_cy=None, is_wattle=None,
                      shared_walls_by_floor=None):
    """Half-timbered side volume embedded into the main side wall.

    side_sgn: +1 attaches on +X, -1 on -X. width runs along Y, depth along X.
    main_bounds_by_floor: {floor_idx: (x_min, x_max, y_min, y_max)} of the main
    hall so the annex tracks the jettied wall face on upper floors instead of
    poking into the main hall interior.
    Returns the outer face X for forecourt layout.
    """
    overlap = 0.6
    wmat_upper = tier_wall_mat(tier, props=props)
    eff_wall = get_effective_wall_material(props) if props is not None else ''
    _wall_tier = 'TIER_1' if tier == 'TIER_1' else tier
    from ..style import is_tier1_wattle_daub
    if props is not None:
        # The host's resolved construction is authoritative (also for manually
        # chosen tier styles); a side annex must never infer a different finish.
        _host_wall = get_effective_wall_material(props)
        if _host_wall == 'WATTLE_DAUB':
            is_wattle = True
            _wall_tier = 'TIER_1'
        elif _host_wall == 'LOGS':
            is_wattle = False
            _wall_tier = 'TIER_1'
        else:
            is_wattle = False
    elif is_wattle is None:
        is_wattle = tier == 'TIER_1' and is_tier1_wattle_daub(props)
    else:
        is_wattle = bool(is_wattle)
    if is_wattle and _wall_tier != 'TIER_1':
        # Round log courses are gated on TIER_1; never let a wattle annex
        # reach the log-wall branch through a tier mismatch.
        _wall_tier = 'TIER_1'
    physical_siding = False if is_wattle else eff_wall in ('LOGS', 'WOOD_PLANKS')
    timber_framing = bool(timber_framing and is_wattle)
    _plaster_cells = is_wattle
    wall_h = floors * floor_h
    top_z = found_h + wall_h
    wall_t = 0.28
    # The outer wall is the cross-gable face. Recess its fixture far enough that
    # the exterior casing straddles the cut wall edges instead of floating proud
    # of the opening (matching the inset finish of the other annex windows).

    outer_x = side_sgn * (main_hx + depth - overlap)
    cy = (main_cy0 + main_cy1) * 0.5
    portal_cy = cy if portal_cy is None else float(portal_cy)
    y0, y1 = cy - width * 0.5, cy + width * 0.5

    def _floor_inner(f):
        if main_bounds_by_floor:
            keys = sorted(main_bounds_by_floor.keys())
            k = f if f in main_bounds_by_floor else keys[-1]
            b = main_bounds_by_floor[k]
            return b[0] if side_sgn < 0 else b[1]
        return side_sgn * main_hx

    floor_inner = {f: _floor_inner(f) for f in range(floors)}
    jetted_inner = max(floor_inner.values(), key=abs)

    # Foundation plinth: top flush with the main floor (no step up) and flared
    # outward only, so it never pushes up through the main hall interior.
    g_inner = floor_inner[0]
    g_span = abs(outer_x - g_inner)
    g_cx = (g_inner + outer_x) * 0.5
    create_beveled_box(bm, size=(g_span + 0.16, width + 0.3, found_h),
                       location=(g_cx + side_sgn * 0.08, cy, z_ground + found_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.025)

    # Exterior wall cladding/construction is resolved from the host building's
    # effective wall style, including the Tier-1 logs vs. framed wattle-daub choice.
    out_normal = (1.0, 0.0) if side_sgn > 0 else (-1.0, 0.0)
    for f in range(floors):
        fz0 = found_h + f * floor_h
        fz1 = fz0 + floor_h
        f_mat = MAT_INDEX_PLASTER_EXT if _plaster_cells else wmat_upper
        inner_x = floor_inner[f]
        cxf = (inner_x + outer_x) * 0.5
        outer_wall_x = outer_x - side_sgn * wall_t * 0.5
        front_wall_y = y0 + wall_t * 0.5
        back_wall_y = y1 - wall_t * 0.5
        win_w = 1.0
        win_h = min(1.25, floor_h * 0.46)
        sill = fz0 + floor_h * 0.30
        # Interior plank floor. Stops cleanly at the wall plane inner_x;
        # the raised threshold board covers the door reveal transition cleanly.
        _fx_inner = inner_x
        _fx_outer = outer_x - side_sgn * wall_t * 0.5
        _fx_min, _fx_max = min(_fx_inner, _fx_outer), max(_fx_inner, _fx_outer)
        create_beveled_box(
            bm, size=(max(0.1, _fx_max - _fx_min), max(0.1, (y1 - wall_t) - (y0 + wall_t)), 0.12),
            location=((_fx_min + _fx_max) * 0.5, cy, fz0 + 0.05 - 0.06),
            mat_index=MAT_INDEX_FLOOR, bevel_amount=0.008)
        # Outer wall (runs along Y). On the top lift the oriel bay sits here, so
        # cut a full-height portal instead of a window: the bay becomes usable
        # interior space connected to the annex room (like every other outcrop).
        if not (floors >= 2 and f == floors - 1):
            uc = width * 0.5
            outer_ops = [{'u_start': uc - win_w * 0.5 - 0.12, 'u_end': uc + win_w * 0.5 + 0.12,
                          'z_start': sill, 'z_end': sill + win_h}]
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                list(outer_ops),
                mat_ext=f_mat, normal_vec=out_normal, tier=_wall_tier, physical_siding=physical_siding,
                plank_direction=plank_direction, seed=42)
            build_window_assembly(
                bm, center=(outer_x - side_sgn * GABLE_WINDOW_INSET, cy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=out_normal, has_shutters=True)
        else:
            # Upper floor walk-through portal into the oriel bay.
            # Sized to match the annex entrance doorway in dimension (1.65m x 2.35m), profile, and material.
            oriel_portal_w = 1.65
            oriel_portal_h = min(2.35, floor_h * 0.78)
            _lh = 0.16
            _jw = 0.16
            _jd = wall_t + 0.10
            cy = portal_cy
            uc = width * 0.5
            _oz0 = fz0
            _oz1 = fz0 + oriel_portal_h + _lh
            outer_ops = [{'u_start': uc - oriel_portal_w * 0.5 - _jw * 0.5,
                          'u_end': uc + oriel_portal_w * 0.5 + _jw * 0.5,
                          'z_start': _oz0, 'z_end': _oz1}]
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                list(outer_ops),
                mat_ext=f_mat, normal_vec=out_normal, tier=_wall_tier, physical_siding=physical_siding,
                plank_direction=plank_direction, seed=42)
            # Timber jambs + lintel matching the annex doorway in dimensions & material
            _wc = outer_wall_x
            for _s in (-1.0, 1.0):
                create_beveled_box(
                    bm, size=(_jd, _jw, oriel_portal_h),
                    location=(_wc, cy + _s * (oriel_portal_w * 0.5 + _jw * 0.5),
                              fz0 + oriel_portal_h * 0.5),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
            create_beveled_box(
                bm, size=(_jd + 0.02, oriel_portal_w + _jw * 2.0 + 0.04, _lh),
                location=(_wc, cy, fz0 + oriel_portal_h + _lh * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)

            # Matching raised timber threshold board into the oriel bay
            _th_h = 0.034
            create_beveled_box(
                bm, size=(_jd + 0.02, oriel_portal_w + _jw * 2.0 + 0.02, _th_h),
                location=(_wc, cy, fz0 + 0.05 + _th_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008)
        if timber_framing and not physical_siding:
            build_facade_timber(bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                                out_normal, list(outer_ops), diagonals,
                                is_top_floor=(f == floors - 1))
        # Front + back walls (run along X)
        ucx = abs(outer_x - inner_x) * 0.5
        for wy, nvec, shutters in ((front_wall_y, (0.0, -1.0), True),
                                   (back_wall_y, (0.0, 1.0), False)):
            _fb_ops = [{'u_start': ucx - win_w * 0.5 - 0.12, 'u_end': ucx + win_w * 0.5 + 0.12,
                        'z_start': sill, 'z_end': sill + win_h}]
            _is_log_wall = (not is_wattle and eff_wall == 'LOGS')
            build_wall_with_opening(
                bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                list(_fb_ops),
                mat_ext=f_mat, normal_vec=nvec, tier=_wall_tier, physical_siding=physical_siding,
                plank_direction=plank_direction, seed=42,
                # Keep the annex logs on their own side of the main wall.  The
                # old inner saddle overrun pushed round log ends through the
                # hall's interior wall.  A vertical closure post covers the
                # butt joint instead, so there is no gap and no intrusion.
                is_corner_start=False, is_corner_end=True,
                omit_top_log_row=False,
                force_omit_top_log_row=False)
            if _is_log_wall:
                create_beveled_box(
                    bm, size=(0.24, 0.24, fz1 - fz0),
                    location=(inner_x + side_sgn * 0.05, wy, (fz0 + fz1) * 0.5),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
            build_window_assembly(
                bm, center=(cxf, wy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=nvec, has_shutters=shutters)
            if timber_framing and not physical_siding:
                build_facade_timber(bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                                    nvec, list(_fb_ops), diagonals,
                                    is_top_floor=(f == floors - 1))

        # Interior joinery: timber baseboards and crown mouldings around the
        # annex room on every wall and every tier. The runs are cut around the
        # walk-through and the oriel doorway, so no trim crosses an opening.
        _shared_face = 'left' if side_sgn > 0 else 'right'
        _outer_face = 'right' if side_sgn > 0 else 'left'
        _annex_door_u = max(1.65 * 0.5, min(width - 1.65 * 0.5, portal_cy - cy + width * 0.5))
        _annex_ops = {
            _shared_face: [{
                'u_start': _annex_door_u - 1.65 * 0.5,
                'u_end': _annex_door_u + 1.65 * 0.5,
                'z_start': fz0, 'z_end': fz0 + 2.35
            }],
        }
        if floors >= 2 and f == floors - 1:
            _annex_ops[_outer_face] = [{
                'u_start': width * 0.5 - 1.65 * 0.5,
                'u_end': width * 0.5 + 1.65 * 0.5,
                'z_start': fz0, 'z_end': fz0 + 2.35
            }]
        build_interior_trims(
            bm, _fx_min, _fx_max, y0 + wall_t, y1 - wall_t, fz0 + 0.05, fz0 + floor_h - 0.08,
            wall_thickness=wall_t,
            wall_openings=_annex_ops,
            skip_sides=(_shared_face,),
        )
        # The main facade wall already supplies the annex portal cut and its
        # casing. Building another full-length wall on this shared face creates
        # coincident double/triple partitions (and can wall the doorway back up).
        # Only add a divider when this annex builder is used without the host wall
        # portal pass recording a junction for the floor.
        _shared_walls_by_floor = shared_walls_by_floor or {}
        _shared_sides = _shared_walls_by_floor.get(f, set()) if _shared_walls_by_floor else set()
        if ('LEFT' if side_sgn < 0 else 'RIGHT') not in _shared_sides:
            from ..interior import build_interior_wall
            _shared_is_left = _shared_face == 'left'
            _sx = inner_x
            _sy0, _sy1 = (y0 + wall_t * 0.5, y1 - wall_t * 0.5) if _shared_is_left \
                else (y1 - wall_t * 0.5, y0 + wall_t * 0.5)
            _door_h = min(2.35, floor_h - 0.35)
            build_interior_wall(
                bm, (_sx, _sy0), (_sx, _sy1), fz0, fz0 + floor_h, thickness=wall_t,
                doorway={'cx': _sx, 'cy': portal_cy, 'w': 1.65, 'h': _door_h},
                mat_index=MAT_INDEX_WOOD, casing_mat=MAT_INDEX_TIMBER,
                plank_direction=plank_direction,
            )

        # Furnish the annex as a small separate sitting room: the seating reads
        # from the doorway, so its back never faces the person walking in.
        try:
            from .prop_registry import build_prop
            from ..materials import MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_FABRIC_STITCHED
            import random as _rnd
            _leather_opts = [MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_FABRIC_STITCHED]
            _rng = _rnd.Random(int(abs(outer_x * 97 + cy * 131)) + f)
            _annex_leather = _rng.choice(_leather_opts)
            # Usable room rectangle between the *finished* wall faces.  _fx_max
            # is the outer edge of the outer wall, so the inner face is half a
            # wall thickness further in; ignoring that buried the sofa.
            # The slab starts/ends at the inside wall plane and the front/back
            # wall centerlines are offset by half a wall. Use the actual finished
            # faces, not a full extra wall thickness, when furnishing footprints.
            _room_x_lo = min(_fx_min, _fx_max) + wall_t * 0.5 + 0.10
            _room_x_hi = max(_fx_min, _fx_max) - wall_t * 0.5 - 0.10
            _room_y_lo = y0 + wall_t * 0.5 + 0.10
            _room_y_hi = y1 - wall_t * 0.5 - 0.10
            _room_w = max(0.2, _room_y_hi - _room_y_lo)
            _room_d = max(0.2, _room_x_hi - _room_x_lo)
            _annex_cx = (_room_x_lo + _room_x_hi) * 0.5
            _annex_cy = cy
            _z_fl = fz0 + 0.05
            _z_cl = fz0 + floor_h - 0.08
            # Everything in a bay must stay this clear of the doorway opening.
            _door_clear = 1.65 * 0.5 + 0.34

            def _clamp_x(v, half):
                lo, hi = _room_x_lo + half, _room_x_hi - half
                return _clamp(v, lo, hi) if lo <= hi else _annex_cx

            def _free_bay(lo, hi, width_needed):
                """Absolute Y centre for a `width_needed` wide piece.

                Try in front of the door first, then behind it, then the amplest
                edge - but always with its footprint out of the doorway band.
                """
                half = width_needed * 0.5 + _door_clear
                cands = [_clamp(portal_cy + half, lo, hi),
                         _clamp(portal_cy - half, lo, hi),
                         hi if abs(hi - portal_cy) >= abs(lo - portal_cy) else lo]
                for c in cands:
                    if abs(c - portal_cy) >= half - 1e-6:
                        return c
                # Room too short to clear the doorway band at all: report it
                # so callers can drop the piece instead of blocking the walkway.
                return None

            # Sofa against the OUTER wall, back to it, facing the doorway wall.
            # Yaw of -pi/2 turns local +Y into -X, so on the +X side the sofa
            # faces the main hall; mirrored on the -X side.
            _sofa_len = min(1.70, max(0.95, _room_w * 0.42))
            _sofa_depth = 0.86 + 0.06
            _sofa_yaw = -math.pi / 2 if side_sgn > 0 else math.pi / 2
            _sofa_y = _free_bay(_room_y_lo + _sofa_len * 0.5,
                                _room_y_hi - _sofa_len * 0.5, _sofa_len)
            _sofa_x = _room_x_hi - _sofa_depth * 0.5 - 0.04
            _seating_y = _sofa_y
            _sofa_half_x = _sofa_depth * 0.5
            _sofa_half_y = _sofa_len * 0.5
            if (_sofa_y is not None and _room_x_lo <= _sofa_x - _sofa_half_x
                    and _sofa_x + _sofa_half_x <= _room_x_hi
                    and _room_y_lo <= _sofa_y - _sofa_half_y
                    and _sofa_y + _sofa_half_y <= _room_y_hi):
                build_prop(bm, 'SOFA', _sofa_x, _sofa_y, _z_fl, _sofa_yaw,
                           length=_sofa_len, fabric_mat=_annex_leather)
            else:
                # Do not force furniture into the doorway or through a finished wall.
                _sofa_y = None
                _seating_y = None

            # Potted plant tucked into the corner diagonally opposite the sofa.
            _anchor_y = _sofa_y if _sofa_y is not None else _annex_cy
            _pl_y = _room_y_lo + 0.42 if abs(_anchor_y - _room_y_hi) < abs(_anchor_y - _room_y_lo) \
                else _room_y_hi - 0.42
            if (_room_x_hi - _room_x_lo >= 0.90 and _room_y_hi - _room_y_lo >= 0.90
                    and abs(_pl_y - portal_cy) >= 0.80):
                build_prop(bm, 'POTTED_PLANT_LARGE', _room_x_lo + 0.42, _pl_y, _z_fl, 0.0)

            if _sofa_y is not None:
                # Table and rug fit within the room and stay away from portal axis.
                _table_x = _clamp_x(_sofa_x - side_sgn * (_sofa_depth * 0.5 + 0.52), 0.30)
                _table_y = _sofa_y
                _table_r = 0.26
                if (_room_x_lo + _table_r <= _table_x <= _room_x_hi - _table_r
                        and _room_y_lo + _table_r <= _table_y <= _room_y_hi - _table_r
                        and abs(_table_y - portal_cy) >= _table_r + 0.25):
                    build_prop(bm, 'ROUND_TABLE', _table_x, _table_y, _z_fl, 0.0, radius=_table_r)
                    _rug_w = min(1.30, max(0.0, _room_d * 0.56))
                    _rug_l = min(1.80, max(0.0, _room_w * 0.52))
                    if (_rug_w >= 0.60 and _rug_l >= 0.80
                            and abs(_table_y - portal_cy) >= _rug_l * 0.5 + 0.20):
                        build_prop(bm, 'RUG_CRIMSON', (_sofa_x + _table_x) * 0.5, _table_y, _z_fl, 0.0,
                                   width=_rug_w, length=_rug_l)

            # Bookshelf flat against the FRONT/back side wall, back to the plaster.
            # Shelf faces -Y locally; yaw=pi flips it against the +Y wall, yaw=0
            # against the -Y wall, standing back-panel-to-plaster, spines outward.
            _bk_w = min(1.10, max(0.50, _room_d * 0.52))
            _bk_d = 0.32
            _bk_half = _bk_w * 0.5 + 0.10
            _bk_room_top = (floor_h - 0.20) if (floors >= 2 and f == floors - 1) else floor_h
            _bk_h = max(0.95, min(1.75, _bk_room_top - 0.45))
            _bk_y_front = _room_y_lo + _bk_d * 0.5 + 0.01
            _bk_y_back = _room_y_hi - _bk_d * 0.5 - 0.01
            _d_front_ok = (abs(_bk_y_front - portal_cy) >= _bk_half
                           and _room_y_lo <= _bk_y_front - _bk_d * 0.5
                           and _bk_y_front + _bk_d * 0.5 <= _room_y_hi)
            _d_back_ok = (abs(_bk_y_back - portal_cy) >= _bk_half
                          and _room_y_lo <= _bk_y_back - _bk_d * 0.5
                          and _bk_y_back + _bk_d * 0.5 <= _room_y_hi)
            _bk_y = None
            if _room_w >= _bk_w + 0.20:
                if _d_front_ok and (not _d_back_ok or _room_w >= 2.2):
                    _bk_y, _bk_yaw = _bk_y_front, math.pi
                elif _d_back_ok:
                    _bk_y, _bk_yaw = _bk_y_back, 0.0
            if _bk_y is not None:
                build_prop(bm, 'BOOKSHELF', _annex_cx, _bk_y, _z_fl, _bk_yaw,
                           width=_bk_w, height=_bk_h)

            # Chair only when the sofa exists and a real floor footprint fits.
            _chair_x = _clamp_x(_sofa_x - side_sgn * 1.55, 0.60)
            _chair_half_x, _chair_half_y = 0.42, 0.42
            if (_sofa_y is not None and _room_x_lo <= _chair_x - _chair_half_x
                    and _chair_x + _chair_half_x <= _room_x_hi
                    and _room_y_lo <= _sofa_y - _chair_half_y
                    and _sofa_y + _chair_half_y <= _room_y_hi
                    and abs(_sofa_y - portal_cy) >= _chair_half_y + 0.25):
                build_prop(bm, 'ARMCHAIR', _chair_x, _sofa_y, _z_fl, _sofa_yaw + math.pi)

            # Collar tie / ceiling timber beam across the annex room, hung below
            # the ceiling plane so it never penetrates the floor of the room above.
            _beam_w = 0.16
            _beam_h = 0.18
            _beam_y_span = (y1 - wall_t) - (y0 + wall_t)
            create_beveled_box(
                bm, size=(_beam_w, _beam_y_span, _beam_h),
                location=(_annex_cx, _annex_cy, _z_cl - _beam_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)

            build_prop(bm, 'CHAIN_LANTERN', _annex_cx, _annex_cy, _z_cl - _beam_h, 0.0)
        except Exception:
            pass
    top_inner = floor_inner[floors - 1]
    # Timber belt course between ground and upper lifts, built as a ring of
    # boards rather than one solid slab: it dresses the outside without filling
    # the annex room (the storey above already gives it a floor/ceiling).
    if floors >= 2 and not physical_siding:
        b_span = abs(outer_x - jetted_inner)
        b_cx = (jetted_inner + outer_x) * 0.5
        _bz = found_h + floor_h - 0.20
        _bh, _bt = 0.18, 0.14
        create_beveled_box(bm, size=(b_span + 0.14, _bt, _bh),
                           location=(b_cx, y0 - _bt * 0.5 + 0.06, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
        create_beveled_box(bm, size=(b_span + 0.14, _bt, _bh),
                           location=(b_cx, y1 + _bt * 0.5 - 0.06, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
        create_beveled_box(bm, size=(_bt, width + 0.14, _bh),
                           location=(outer_x + side_sgn * (_bt * 0.5 - 0.06), cy, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Corner boards on the outer corners (plain log annexes keep their log ends).
    if not physical_siding:
        for sy in (y0 + 0.08, y1 - 0.08):
            create_beveled_box(bm, size=(0.28, 0.28, wall_h),
                               location=(outer_x, sy, found_h + wall_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)

    # Upper oriel on the outer face: reuse the shared mini-wing outcrop builder
    # so the annex bay matches every other outcrop on the hall (same casing,
    # window size, corbels and shingled cap) instead of a bespoke box.
    if floors >= 2:
        _ow_side = 'LEFT' if side_sgn < 0 else 'RIGHT'
        _ow_anchor_lo = outer_x if side_sgn < 0 else top_inner
        _ow_anchor_hi = top_inner if side_sgn < 0 else outer_x
        # The walk-through portal is cut on the annex's TOP storey.  A
        # three/four-storey annex used to put the oriel on floor 1 only,
        # leaving the top-floor portal opening straight into the sky.
        _ow_z = found_h + max(1, floors - 1) * floor_h
        build_mini_wing(
            bm, side=_ow_side, floor_mode='UPPER',
            wall_x_min=_ow_anchor_lo, wall_x_max=_ow_anchor_hi,
            wall_y_min=cy - 1.6, wall_y_max=cy + 1.6,
            z_base=_ow_z, width=max(2.40, min(2.80, width * 0.58)), depth=0.9,
            height=max(2.80, min(3.20, floor_h - 0.55)), roof_style='LEAN_TO',
            tier=tier, floor_h=floor_h, wall_mat=f_mat, is_wattle=is_wattle,
            lower_bounds=(_ow_anchor_lo, _ow_anchor_hi, cy - 1.6, cy + 1.6),
        )

    # Cross-gable roof: the ridge points OUTWARD (along the depth / X axis) so the
    # annex reads as a real wing with a street-side gable, instead of a long low
    # shed with a ridge running parallel to the main wall. build_gable_roof is
    # axis-aligned (ridge along its Y input), so we build the roof in a local
    # frame with the ridge along the annex depth and rotate it 90 deg into place.
    # The outer depth end carries the gable; the inner end (the jettied main wall
    # face) abuts flush with zero overhang so no deck buries into the hall.
    _annex_depth = abs(outer_x - top_inner)
    _roof_cx = (top_inner + outer_x) * 0.5
    if side_sgn < 0:
        _gable_ends, _abut_front, _abut_back = ('BACK',), True, False
    else:
        _gable_ends, _abut_front, _abut_back = ('FRONT',), False, True
    annex_roof_bm = bmesh.new()
    # For a full-height annex under a front/back main ridge, extend the deck
    # inward along the valley: it must reach where the main slope climbs to the
    # annex ridge (the valley apex). The deck is notch-cut back along the two
    # valley lines so the annex roof meets the main roof instead of stopping bare
    # at the wall (and the apex never runs past the main slope into the attic).
    _use_valley = (bool(main_roof) and not main_roof.get('rotated', False)
                   and floors >= main_roof.get('num_floors', floors))
    _ov = 0.20
    _r_y_min, _r_y_max = -_annex_depth * 0.5, _annex_depth * 0.5
    _vnotch = None
    _seg_y = 3
    _valley = None
    if _use_valley:
        mr = main_roof
        _swm = mr['sway'] if mr['style'] == 'SWAY' else 0.0
        _ezm = (mr['top_z'] - 0.12) if mr['style'] == 'SWAY' else (mr['top_z'] - 0.10)

        def _main_fn(px, py):
            return deck_top_z(px, py, mr['top_cx'], mr['top_hx'] + mr['ov'],
                              mr['top_z'], mr['roof_h'], mr['flare'], _swm,
                              mr['y_min'] - mr['ov'], mr['y_max'] + mr['ov'],
                              _ezm, top_off=0.05)

        _eave_x = side_sgn * (mr['top_hx'] + mr['ov'])
        _ridge_z = top_z + roof_h
        # Walk from the main eave inward until the main slope reaches the annex
        # ridge height; that crossing is the valley apex.
        _apex_x = 0.0
        for _i in range(81):
            _x = _eave_x * (1.0 - _i / 80.0)
            if _main_fn(_x, cy) >= _ridge_z:
                _apex_x = _x
                break
        _apex_ly = _roof_cx - _apex_x
        _base_ly = _roof_cx - _eave_x
        if side_sgn > 0:
            _r_y_max = _apex_ly
            _keep = 'le'
        else:
            _r_y_min = _apex_ly
            _keep = 'ge'
        _vnotch = {'apex_x': -cy, 'apex_y': _apex_ly, 'base_y': _base_ly,
                   'half_width': width * 0.5 + _ov, 'keep': _keep,
                   'overlap': 0.02, 'side': 'BOTH'}
        _seg_y = 10
        _valley = {'main_fn': _main_fn, 'eave_x': _eave_x, 'apex_x': _apex_x}
    _main_style = main_roof.get('style', 'SWAY') if main_roof else 'SWAY'
    _r_flare = main_roof.get('flare', 0.35) if main_roof else 0.35
    _r_sway = main_roof.get('sway', 0.25) if main_roof else 0.25
    _r_mat = main_roof.get('roof_mat', None) if main_roof else None
    if not _r_mat and props is not None:
        _r_mat = get_effective_roof_material(props)
    if _main_style == 'MAKESHIFT' and _r_mat in ('THATCH', 'WOOD_SHINGLES'):
        _main_style = 'SWAY'

    if _main_style == 'NONE':
        # Flat roof deck on top of the annex: solid timber floor slab + perimeter parapet curb
        _deck_t = 0.14
        create_beveled_box(
            bm, size=(_annex_depth + 0.30, width + 0.30, _deck_t),
            location=(_roof_cx, cy, top_z + _deck_t * 0.5),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
        )
        _curb_h = 0.22
        _curb_w = 0.16
        create_beveled_box(
            bm, size=(_curb_w, width + 0.30, _curb_h),
            location=(outer_x + side_sgn * 0.08, cy, top_z + _deck_t + _curb_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        for _py in (y0 - 0.08, y1 + 0.08):
            create_beveled_box(
                bm, size=(_annex_depth + 0.30, _curb_w, _curb_h),
                location=(_roof_cx, _py, top_z + _deck_t + _curb_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
            )
        annex_roof_bm.free()
        return outer_x
    elif _main_style == 'MAKESHIFT':
        # Low-tier annex under a makeshift main roof: the same draped-canvas
        # rafters over the annex volume, in the annex's own footprint.
        from ..roof.makeshift_roof import build_makeshift_roof
        build_makeshift_roof(
            bm,
            min(top_inner, outer_x), max(top_inner, outer_x),
            y0, y1,
            z_base=top_z,
            effective_archetype='NONE',
            seed=42,
        )
        annex_roof_bm.free()
        return outer_x
    elif _main_style == 'TURRET':
        # A conical turret cap over the annex, echoing the main roof style.
        from ..roof.turret_roof import build_conical_turret_roof
        _t_rad = max(width * 0.62, 1.4)
        build_conical_turret_roof(
            bm,
            center_pos=(_roof_cx, cy, top_z),
            radius=_t_rad,
            height=max(1.8, roof_h * 1.15),
        )
        annex_roof_bm.free()
        return outer_x
    elif _main_style == 'SWAY':
        from ..roof.sway_roof import build_sway_roof
        build_sway_roof(
            annex_roof_bm,
            x_min=-width * 0.5,
            x_max=width * 0.5,
            y_min=_r_y_min,
            y_max=_r_y_max,
            z_base=top_z,
            roof_height=roof_h,
            overhang=0.20,
            sway_amount=_r_sway,
            segments_y=max(6, _seg_y),
            wall_thickness=0.18,
            gable_ends=_gable_ends,
            abut_front=_abut_front,
            abut_back=_abut_back,
            tier=tier,
            plank_direction='VERTICAL',
            roof_flare=_r_flare,
            valley_notch=_vnotch,
            roof_mat=_r_mat,
            is_wattle=is_wattle,
        )
    else:
        build_gable_roof(
            annex_roof_bm,
            x_min=-width * 0.5,
            x_max=width * 0.5,
            y_min=_r_y_min,
            y_max=_r_y_max,
            z_base=top_z,
            roof_height=roof_h,
            overhang=0.20,
            wall_thickness=0.18,
            gable_ends=_gable_ends,
            abut_front=_abut_front,
            abut_back=_abut_back,
            segments_y=_seg_y,
            tier=tier,
            plank_direction='VERTICAL',
            roof_flare=_r_flare,
            valley_notch=_vnotch,
            roof_mat=_r_mat,
            is_wattle=is_wattle,
        )
    bmesh.ops.transform(
        annex_roof_bm,
        matrix=Matrix.Rotation(math.radians(90.0), 4, 'Z'),
        verts=annex_roof_bm.verts,
    )
    for v in annex_roof_bm.verts:
        v.co += Vector((_roof_cx, cy, 0.0))
    # The gable wall UVs came out of the roof builder in its LOCAL frame, so the
    # 90 deg rotation left the facade texture rotated/misaligned against the rest
    # of the building. Remap the gable faces (wood / plaster) to world-space UVs.
    _uvg = annex_roof_bm.loops.layers.uv.verify()
    for _gf in annex_roof_bm.faces:
        if _gf.material_index in (MAT_INDEX_WOOD, MAT_INDEX_PLASTER_EXT):
            for _gl in _gf.loops:
                _gc = _gl.vert.co
                _gl[_uvg].uv = (_gc.y * 0.55, (_gc.z - top_z) * 0.55)
    uv_src = annex_roof_bm.loops.layers.uv.verify()
    uv_dst = bm.loops.layers.uv.verify()
    vert_map = {v: bm.verts.new(v.co) for v in annex_roof_bm.verts}
    for f in annex_roof_bm.faces:
        try:
            nf = bm.faces.new([vert_map[v] for v in f.verts])
            nf.material_index = f.material_index
            nf.smooth = f.smooth
            for l_src, l_dst in zip(f.loops, nf.loops):
                l_dst[uv_dst].uv = l_src[uv_src].uv
        except ValueError:
            pass
    annex_roof_bm.free()

    # Connect the annex cross-gable roof into the main roof with the same valley
    # rafters the wings get. The rafters run from the main eave corners to the
    # valley apex (where the annex ridge meets the main slope), i.e. exactly on
    # the deck's notch edge, so the frame actually touches the roof.
    if _valley is not None:
        _main_fn = _valley['main_fn']
        _lx_half = width * 0.5
        _ly_half = _annex_depth * 0.5
        _hw = _lx_half + _ov

        def _annex_fn(px, py):
            return deck_top_z(py - cy, _roof_cx - px, 0.0, _hw, 0.0, roof_h, 0.35, 0.0,
                              -_ly_half - _ov, _apex_ly, -0.10, top_off=0.05) + top_z

        _ex = _valley['eave_x']
        _ax = _valley['apex_x']
        corners = [(_ex, cy - _lx_half - _ov), (_ex, cy + _lx_half + _ov)]
        die = (_ax, cy)
        for _cx0, _cy0 in corners:
            build_valley_rafters(bm, (_cx0, _cy0), die, _main_fn, _annex_fn)

    return outer_x


def build_tower_annex(bm, side_sgn, main_hx, main_cy0, main_cy1, z_ground=0.0,
                      found_h=0.6, floors=3, floor_h=4.0, tier='TIER_3',
                      width=10.0, depth=8.0, main_bounds_by_floor=None,
                      props=None, main_roof_mat=None):
    """Tower annex; the finish follows the host building's effective materials."""
    overlap = 1.0
    eff_wall = get_effective_wall_material(props) if props is not None else 'STONE'
    wall_mat = tier_wall_mat(tier, props=props) if props is not None else MAT_INDEX_STONE
    wall_tier = 'TIER_1' if tier == 'TIER_1' else tier
    physical_siding = eff_wall in ('LOGS', 'WOOD_PLANKS')
    wall_h = floors * floor_h
    top_z = found_h + wall_h
    wall_t = 0.65

    outer_x = side_sgn * (main_hx + depth - overlap)
    cy = (main_cy0 + main_cy1) * 0.5
    y0, y1 = cy - width * 0.5, cy + width * 0.5

    def _floor_inner(f):
        if main_bounds_by_floor:
            keys = sorted(main_bounds_by_floor.keys())
            k = f if f in main_bounds_by_floor else keys[-1]
            b = main_bounds_by_floor[k]
            return b[0] if side_sgn < 0 else b[1]
        return side_sgn * main_hx

    # Foundation
    g_inner = _floor_inner(0)
    g_span = abs(outer_x - g_inner)
    g_cx = (g_inner + outer_x) * 0.5
    create_beveled_box(bm, size=(g_span + 0.16, width + 0.16, found_h),
                       location=(g_cx + side_sgn * 0.08, cy, z_ground + found_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.025)

    out_normal = (1.0, 0.0) if side_sgn > 0 else (-1.0, 0.0)
    for f in range(floors):
        fz0 = found_h + f * floor_h
        fz1 = fz0 + floor_h
        inner_x = _floor_inner(f)
        outer_wall_x = outer_x - side_sgn * wall_t * 0.5
        front_wall_y = y0 + wall_t * 0.5
        back_wall_y = y1 - wall_t * 0.5
        win_w = 1.2
        win_h = min(1.8, floor_h * 0.5)
        sill = fz0 + floor_h * 0.35

        # Floor slab
        _fx_inner = inner_x - side_sgn * (wall_t * 0.5 + 0.02)
        _fx_outer = outer_x - side_sgn * wall_t * 0.5
        _fx_min, _fx_max = min(_fx_inner, _fx_outer), max(_fx_inner, _fx_outer)
        create_beveled_box(
            bm, size=(max(0.1, _fx_max - _fx_min), max(0.1, (y1 - wall_t) - (y0 + wall_t)), 0.12),
            location=((_fx_min + _fx_max) * 0.5, cy, fz0 + 0.05 - 0.06),
            mat_index=MAT_INDEX_FLOOR, bevel_amount=0.008)

        # Windows
        uc = width * 0.5
        outer_ops = [{'u_start': uc - win_w * 0.5 - 0.12, 'u_end': uc + win_w * 0.5 + 0.12,
                      'z_start': sill, 'z_end': sill + win_h}] if f > 0 else []
        
        build_wall_with_opening(
            bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
            list(outer_ops), mat_ext=wall_mat, normal_vec=out_normal, tier=wall_tier, physical_siding=physical_siding,
            plank_direction='HORIZONTAL', seed=42)
        
        if f > 0:
            build_window_assembly(bm, (outer_wall_x, cy), sill, win_w, win_h, wall_t,
                                  normal_axis=out_normal, shape='ARCHED', has_shutters=False,
                                  tier=wall_tier, depth_offset=0.06)

        ucx = abs(outer_x - inner_x) * 0.5
        for wy, nvec in ((front_wall_y, (0.0, -1.0)), (back_wall_y, (0.0, 1.0))):
            _fb_ops = [{'u_start': ucx - win_w * 0.5 - 0.12, 'u_end': ucx + win_w * 0.5 + 0.12,
                        'z_start': sill, 'z_end': sill + win_h}] if f > 0 else []
            build_wall_with_opening(
                bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                list(_fb_ops), mat_ext=wall_mat, normal_vec=nvec, tier=wall_tier, physical_siding=physical_siding,
                is_corner_start=False, is_corner_end=True, plank_direction='HORIZONTAL', seed=42)
            if f > 0:
                wx = (inner_x + outer_x) * 0.5
                build_window_assembly(bm, (wx, wy), sill, win_w, win_h, wall_t,
                                      normal_axis=nvec, shape='ARCHED', has_shutters=False,
                                      tier=wall_tier, depth_offset=0.06)
                                      
        # Internal staircase (straight)
        if f < floors - 1:
            from ..interior import build_straight_stairs
            stair_x = (_fx_min + _fx_max) * 0.5 + (1.0 if side_sgn > 0 else -1.0)
            build_straight_stairs(bm, start_pos=(stair_x, front_wall_y + 1.0, fz0 + 0.05),
                                  target_z=fz1 + 0.05, width=1.4, length=4.5,
                                  direction=Vector((0, 1, 0)), has_railings=True)
        else:
            # Final stair up to roof deck
            from ..interior import build_straight_stairs
            stair_x = (_fx_min + _fx_max) * 0.5 + (1.0 if side_sgn > 0 else -1.0)
            build_straight_stairs(bm, start_pos=(stair_x, front_wall_y + 1.0, fz0 + 0.05),
                                  target_z=top_z + 0.35, width=1.4, length=4.5,
                                  direction=Vector((0, 1, 0)), has_railings=True)
                                  
    # Roof deck and battlements preserve the main building's roof finish language.
    roof_material = main_roof_mat or (get_effective_roof_material(props) if props is not None else 'SLATE')
    roof_z = top_z
    _ix = _floor_inner(floors - 1)
    _ox = outer_x
    _deck_cx = (_ix + _ox) * 0.5
    _deck_w = abs(_ox - _ix)
    
    # Roof slab
    _roof_deck_mat = MAT_INDEX_WOOD if roof_material in ('THATCH', 'WOOD_SHINGLES') else MAT_INDEX_CUT_STONE
    create_beveled_box(bm, size=(_deck_w, width, 0.3),
                       location=(_deck_cx, cy, roof_z + 0.15),
                       mat_index=_roof_deck_mat, bevel_amount=0.015)
                       
    # Stair bulkhead on roof
    create_beveled_box(bm, size=(2.0, 5.0, 2.8),
                       location=(stair_x, front_wall_y + 3.25, roof_z + 0.30 + 1.4),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
                       
    # Merlons around 3 exposed sides
    merlon_h = 1.2
    merlon_w = 1.0
    gap = 0.8
    n_front = int(_deck_w / (merlon_w + gap))
    for i in range(n_front):
        mx = min(_ix, _ox) + 0.5 + i * (merlon_w + gap)
        create_beveled_box(bm, size=(merlon_w, 0.4, merlon_h),
                           location=(mx, y0 + 0.2, roof_z + 0.30 + merlon_h * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        create_beveled_box(bm, size=(merlon_w, 0.4, merlon_h),
                           location=(mx, y1 - 0.2, roof_z + 0.30 + merlon_h * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    n_outer = int(width / (merlon_w + gap))
    for i in range(n_outer):
        my = y0 + 0.5 + i * (merlon_w + gap)
        create_beveled_box(bm, size=(0.4, merlon_w, merlon_h),
                           location=(outer_x - side_sgn * 0.2, my, roof_z + 0.30 + merlon_h * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    return outer_x
