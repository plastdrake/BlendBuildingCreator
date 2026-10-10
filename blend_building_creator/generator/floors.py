"""Per-floor construction phase.

Builds the foundation-to-eave shell for every storey: interior floor slabs,
staircases, ceiling beams, doors, windows, wing walls, timber framing, plus the
side-annex and corner-turret connections. Called once by the orchestrator with
the shared :class:`BuildingContext`.
"""

import math
from .mesh_utils import create_beveled_box, create_flared_post
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER,
    MAT_INDEX_FLOOR, MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_DIRT,
    MAT_INDEX_CUT_STONE
)
from .walls import (
    build_wall_with_opening, build_facade_timber,
    build_cantilever_corbels, build_cantilever_soffit, build_open_timber_arcade
)
from .shapes import get_facade_window_positions, compute_fl_wing_bounds
from .style import is_tier1_wattle_daub, get_effective_wall_material
from .interior import (
    build_floor_slab, build_ceiling_beams, build_interior_trims, build_straight_staircase,
    build_spiral_staircase, build_stair_guardrail, build_stair_guardrail_3sided, plan_floor_rooms, build_floor_interior_walls
)
from .openings import build_door_assembly, build_front_steps, build_window_assembly
from .accessories.cargo_port import build_cargo_port_frame
from .accessories.mini_wing import plan_outcrop_spread
from .accessories.rampart import rampart_deck_span, town_hall_deck_span
from .accessories.exterior_stairs import (
    exterior_stairs_y_span as _ext_stairs_y_span,
    exterior_stair_plan as _ext_stair_plan,
    exterior_stair_door_spots as _ext_stair_door_spots,
)


def build_floors(bm, props, ctx):
    """Per-floor construction: slabs, stairs, beams, walls, openings, doors, windows."""
    num_floors = ctx.num_floors
    floor_h = ctx.floor_h
    base_w = ctx.base_w
    base_d = ctx.base_d
    wall_t = ctx.wall_t
    cantilever = ctx.cantilever
    found_h = ctx.found_h
    open_timber = ctx.open_timber
    effective_archetype = ctx.effective_archetype
    shape = ctx.shape
    wing_floors = ctx.wing_floors
    wing_placement = ctx.wing_placement
    wing_side = ctx.wing_side
    wings = ctx.wings
    has_wing = ctx.has_wing
    seed = ctx.seed
    plank_dir = ctx.plank_dir
    floor_balc_side = ctx.floor_balc_side
    main_door_cx = ctx.main_door_cx
    main_door_yf = ctx.main_door_yf
    is_rotated_roof = ctx.is_rotated_roof

    def _floor_xy_bounds(fi):
        """Wall bounds a given floor will have (overhang + pillared expansion)."""
        if props.has_cantilever:
            if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                fov = cantilever if fi >= 1 else 0.0
            else:
                fov = fi * cantilever
        else:
            fov = 0.0
        hxx = (base_w + fov * 2.0) * 0.5
        hyy = (base_d + fov * 2.0) * 0.5
        bx0, bx1, by0, by1 = -hxx, hxx, -hyy, hyy
        if getattr(props, 'has_pillared_overhang', False) and fi >= 1:
            p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
            p_depth = getattr(props, 'pillared_overhang_depth', 1.6)
            if p_side == 'FRONT':
                by0 -= p_depth
            elif p_side == 'BACK':
                by1 += p_depth
            elif p_side == 'LEFT':
                bx0 -= p_depth
            elif p_side == 'RIGHT':
                bx1 += p_depth
        return bx0, bx1, by0, by1

    def _get_floor_door_corbel_exclusions(f_idx, bounds):
        """Returns (front_ex, back_ex, left_ex, right_ex) exclusion ranges along each facade

        for doorways/portals on storey `f_idx`, ensuring overhang support corbels are never
        placed inside door frames, portals, or entrance arches.
        """
        lx_min, lx_max, ly_min, ly_max = bounds
        dw = getattr(props, 'door_width', 1.0)
        door_margin = dw * 0.5 + 0.50
        front_ex = []
        back_ex = []
        left_ex = []
        right_ex = []

        if f_idx == 0:
            # 1. Front entrance
            if getattr(props, 'has_front_door', True) and not open_timber:
                # Default to the building's resolved main-door centre; the
                # RECTANGLE/L/U branches below refine it. (T-shaped town halls
                # previously left this unset and crashed.)
                door_cx = main_door_cx
                if shape == 'RECTANGLE':
                    door_offset = getattr(props, 'front_door_offset_x', 0.0)
                    door_cx = 0.0 + door_offset
                elif shape == 'L_SHAPE':
                    if wing_placement == 'FRONT' and len(wings) > 0:
                        door_cx = (lx_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + lx_max) * 0.5
                    else:
                        door_cx = 0.0
                elif shape == 'U_SHAPE':
                    door_cx = 0.0
                front_ex.append((door_cx - door_margin, door_cx + door_margin))

        elif f_idx == 1:
            # Upper side door onto rampart deck
            if getattr(props, 'has_side_rampart', False) and not open_timber:
                r_side = getattr(props, 'rampart_side', 'RIGHT')
                _composer = (getattr(props, 'town_hall_composer', False) and shape == 'T_SHAPE')
                _rspan = (ly_min, ly_max) if _composer else rampart_deck_span(props, ctx)
                if _rspan is not None:
                    rdw = getattr(props, 'rampart_door_width', dw)
                    r_cy = (_rspan[0] + _rspan[1]) * 0.5
                    r_margin = rdw * 0.5 + 0.50
                    if r_side == 'LEFT':
                        left_ex.append((r_cy - r_margin, r_cy + r_margin))
                    else:
                        right_ex.append((r_cy - r_margin, r_cy + r_margin))

        return front_ex, back_ex, left_ex, right_ex

    # Ground floor master interior reference for staircase. Walls are centred
    # on the footprint line, so the interior face is half a wall thickness in
    # (matching the per-floor bounds used everywhere else).
    fl0_ix_min = -base_w * 0.5 + wall_t * 0.5
    fl0_ix_max = base_w * 0.5 - wall_t * 0.5
    fl0_iy_min = -base_d * 0.5 + wall_t * 0.5
    fl0_iy_max = base_d * 0.5 - wall_t * 0.5

    stair_w = props.stair_width
    landing_depth = max(1.10, stair_w * 0.75)

    is_tenement_stairs = (
        effective_archetype == 'TENEMENT'
        and getattr(props, 'has_stairs', False)
        and getattr(props, 'stair_style', 'STRAIGHT') != 'SPIRAL'
    )

    # Non-tenement straight stairs use a side-by-side switchback: each storey
    # climbs the lane the storey below did NOT use, so an upper flight sits
    # BESIDE the lower one and never stacks on top of it (which made the run
    # below unwalkable).  Tenements keep their own single-wall tandem scheme.
    lane_gap = 0.20
    stair_side_opt = getattr(props, 'stair_placement', 'LEFT')
    stair_switchback = (
        not is_tenement_stairs
        and getattr(props, 'stair_style', 'STRAIGHT') != 'SPIRAL'
    )
    if stair_side_opt == 'RIGHT':
        lane_cx_0 = fl0_ix_max - 0.08 - stair_w * 0.5
        lane_cx_1 = lane_cx_0 - stair_w - lane_gap
    else:
        lane_cx_0 = fl0_ix_min + 0.08 + stair_w * 0.5
        lane_cx_1 = lane_cx_0 + stair_w + lane_gap
    # Room planning needs the whole switchback well centre; the single-lane
    # tenement/tandem stair just uses its one lane.
    stair_cx = (lane_cx_0 + lane_cx_1) * 0.5 if stair_switchback else lane_cx_0

    D_interior = fl0_iy_max - fl0_iy_min
    end_landing = max(1.10, stair_w * 0.75)
    mid_landing = max(1.20, stair_w * 0.85)

    if is_tenement_stairs and D_interior >= 7.4:
        if D_interior >= 12.0:
            end_landing = 2.50
            mid_landing = 2.50
        else:
            end_landing = max(1.50, min(2.50, (D_interior - 2.0 * 2.6) / 3.0))
            mid_landing = end_landing
        run_avail = D_interior - 2.0 * end_landing - mid_landing
        stair_len = min(3.8, max(2.6, run_avail * 0.5))

        # South flight (half 0)
        stair_y_s0 = fl0_iy_min + end_landing
        stair_y_s1 = stair_y_s0 + stair_len

        # North flight (half 1)
        stair_y_n1 = fl0_iy_max - end_landing
        stair_y_n0 = stair_y_n1 - stair_len

        stair_y_bot = min(stair_y_s0, stair_y_n0)
        stair_y_top = max(stair_y_s1, stair_y_n1)
        stair_y_head = stair_y_s1
        stair_y_foot = stair_y_s0
        stair_ascend_sign = 1.0
    else:
        stair_len = min(3.8, max(2.6, D_interior - landing_depth - 1.2))
        if effective_archetype == 'MANOR':
            # Grand stair hall: center the flight depth-wise so both the foot
            # approach and the head landing open onto generous clear floor
            # instead of crowding one end wall.
            stair_y_head = (fl0_iy_min + fl0_iy_max) * 0.5 - stair_len * 0.5
        else:
            stair_y_head = fl0_iy_min + landing_depth
        stair_ascend_sign = -1.0
        stair_y_foot = stair_y_head - stair_ascend_sign * stair_len
        stair_y_bot = min(stair_y_head, stair_y_foot)
        stair_y_top = max(stair_y_head, stair_y_foot)

    prev_fl_overhang = 0.0
    prev_x_min, prev_x_max = -base_w * 0.5, base_w * 0.5
    prev_y_min, prev_y_max = -base_d * 0.5, base_d * 0.5

    # Track stair holes, rooms, interior walls and wall bounds per floor
    floor_stair_holes = {}
    if getattr(props, 'has_basement_stair', False):
        if shape == 'L_SHAPE' and wings:
            # Cellar stairwell: a shaft in the L-wing so the cellar can sit
            # directly UNDER the wing. Hugs the outer (-X) side of the wing.
            wx1, wx2, wy1, wy2 = (float(wings[0]['base'][0]),
                                  float(wings[0]['base'][1]),
                                  float(wings[0]['base'][2]),
                                  float(wings[0]['base'][3]))
            _shx = wx1 + 1.05
            _shy = (wy1 + wy2) * 0.5
            floor_stair_holes[0] = (_shx - 0.80, _shx + 0.80,
                                    _shy - 1.80, _shy + 1.80)
        else:
            # Legacy rear stair hall (north strip), flight runs east-west.
            # Top step starts at x=1.10 to leave a solid flat entrance landing
            # between the central partition doorway at x=0.0 and the first tread.
            bs_y0 = 4.00
            bs_y1 = 5.40
            bs_x0 = 1.10
            bs_x1 = 5.70
            floor_stair_holes[0] = (bs_x0, bs_x1, bs_y0, bs_y1)
    floor_wall_bounds = {}
    floor_rooms = {}
    floor_interior_walls = {}
    # World-space window sill centres per floor/facade, so accessories (flower
    # boxes, awnings, hanging baskets, lanterns) can align to the real windows.
    window_centers = {}

    # Town-Hall side annex: it hugs the main side wall (opposite the clock tower)
    # for its whole height. Windows on the main wall behind it are interior and
    # must be suppressed, and its portal opens on every floor it spans so the
    # upper storey is reachable from inside the hall.
    _is_hall_annex = (getattr(props, 'town_hall_composer', False) and shape == 'T_SHAPE')
    _is_generic_annex = (not getattr(props, 'town_hall_composer', False))
    _has_tower_annex = bool(getattr(props, 'has_tower_annex', False))
    _annex_on = (bool(getattr(props, 'has_side_annex', False)) and (_is_hall_annex or _is_generic_annex)) or _has_tower_annex
    _annex_floors = 0
    _annex_side = None
    _annex_y_span = None
    if _annex_on:
        if _has_tower_annex:
            _annex_floors = num_floors
            _raw_side = getattr(props, 'annex_side', 'LEFT')
            _annex_side = _raw_side if _raw_side in ('LEFT', 'RIGHT', 'BOTH') else 'LEFT'
            _a_w = 12.0
            _annex_y_span = (-_a_w * 0.5 - 0.1, _a_w * 0.5 + 0.1)
        else:
            _annex_floors = max(1, min(2, getattr(props, 'annex_floors', 2)))
            if _is_hall_annex:
                _annex_side = 'LEFT' if getattr(props, 'clock_tower_side', 'RIGHT') == 'RIGHT' else 'RIGHT'
                _a_w = 5.2 if getattr(props, 'material_tier', 'TIER_3') != 'TIER_1' else 4.4
                _annex_y_span = (-_a_w * 0.5 - 0.5, _a_w * 0.5 + 0.5)
            else:
                _raw_side = getattr(props, 'annex_side', 'LEFT')
                _annex_side = _raw_side if _raw_side in ('LEFT', 'RIGHT', 'BOTH') else 'LEFT'
                _a_w = min(6.0, max(3.6, base_d * 0.72))
                _annex_y_span = (-_a_w * 0.5 - 0.1, _a_w * 0.5 + 0.1)

    # Square corner turrets bolt onto the outside of the BACK wall, so each one
    # connects through a doorway cut in the back wall (clear of the stairs).
    _turrets = []
    if getattr(props, 'has_corner_turrets', False) and not open_timber:
        _thalf = max(1.0, min(3.5, getattr(props, 'corner_turret_size', 1.35)))
        # The turret centres on the OUTERMOST (top-storey) wall face, so the
        # doorway must use that same reference or it lands off the tower and a
        # wall blocks the way in.
        _t_ovh = 0.0
        if getattr(props, 'has_cantilever', False):
            if getattr(props, 'overhang_mode', 'SECOND_FLOOR_ONLY') == 'SECOND_FLOOR_ONLY':
                _t_ovh = cantilever if num_floors >= 2 else 0.0
            else:
                _t_ovh = (num_floors - 1) * cantilever
        _t_cx = base_w * 0.5 + _t_ovh - _thalf
        _turrets = [{'cx': -_t_cx, 'half': _thalf}, {'cx': _t_cx, 'half': _thalf}]

    # ---- Mini-wing outcrop layout ------------------------------------------
    # Outcrops scatter over open slots only: never on a facade that already
    # carries a wing, annex, clock tower, rampart or balcony, and never over a
    # doorway, a turret corner, the outdoor archetype gear or the outcrop on
    # the storey below (whose roof rises into this one).
    _mw_spread = plan_outcrop_spread(
        props, base_w, base_d, num_floors, wings, has_wing, effective_archetype,
        floor_balc_side, main_door_cx, _annex_on, _annex_side, _annex_floors,
        seed, open_timber)
    ctx.mini_wing_spread = _mw_spread

    for fl_idx in range(num_floors):
        z_floor = found_h + fl_idx * floor_h
        z_ceil = z_floor + floor_h
        fl_has_wing = has_wing and (fl_idx < wing_floors)
        
        # Upper floor cantilever expansion
        if props.has_cantilever:
            if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                fl_overhang = cantilever if fl_idx >= 1 else 0.0
            else: # ALL_FLOORS
                fl_overhang = fl_idx * cantilever
        else:
            fl_overhang = 0.0

        cur_w = base_w + fl_overhang * 2.0
        cur_d = base_d + fl_overhang * 2.0
        
        hx = cur_w * 0.5
        hy = cur_d * 0.5
        
        x_min, x_max = -hx, hx
        y_min, y_max = -hy, hy

        # Upper floor jettying over pillared overhang colonnade
        if getattr(props, 'has_pillared_overhang', False) and fl_idx >= 1:
            p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
            p_depth = getattr(props, 'pillared_overhang_depth', 1.6)
            if p_side == 'FRONT':
                y_min -= p_depth
            elif p_side == 'BACK':
                y_max += p_depth
            elif p_side == 'LEFT':
                x_min -= p_depth
            elif p_side == 'RIGHT':
                x_max += p_depth

        floor_wall_bounds[fl_idx] = (x_min, x_max, y_min, y_max)
        
        # Interior bounds for current floor room (inner wall face at wall_t * 0.50)
        ix_min, ix_max = x_min + wall_t * 0.50, x_max - wall_t * 0.50
        iy_min, iy_max = y_min + wall_t * 0.50, y_max - wall_t * 0.50
        # Floor slab bounds:
        if open_timber:
            # Open timber frames (Lumbermill / Warehouse T1) have arcade posts rather than solid walls.
            # Inset slightly inside the outer timber sleeper sills so it does NOT fight with the sill edges.
            slab_xmin = x_min + 0.01
            slab_xmax = x_max - 0.01
            slab_ymin = y_min + 0.01
            slab_ymax = y_max - 0.01
        else:
            # Floor slab strictly interior so no double floor line visible outside
            slab_xmin = ix_min + 0.02
            slab_xmax = ix_max - 0.02
            slab_ymin = iy_min + 0.02
            slab_ymax = iy_max - 0.02
        
        # Wing coordinates if this floor has an active wing
        fl_wings_bounds = []
        if fl_has_wing:
            for w_elem in wings:
                wb = compute_fl_wing_bounds(w_elem, fl_idx, fl_overhang, x_min, x_max, y_min, y_max)
                fl_wings_bounds.append(wb)
                w_elem.setdefault('bounds_fl', {})[fl_idx] = wb
            wx_min, wx_max, wy_min, wy_max = fl_wings_bounds[0]
        else:
            wx_min, wx_max, wy_min, wy_max = 0.0, 0.0, 0.0, 0.0

        # Corbels and solid wooden soffit underneath upper floor overhang
        if fl_idx > 0 and fl_overhang > prev_fl_overhang:
            overhang_step = fl_overhang - prev_fl_overhang
            # Exclude interior wing junction from exterior cantilever corbels/soffits
            front_ex = (wx_min - 0.05, wx_max + 0.05) if fl_has_wing else None
            has_po = getattr(props, 'has_pillared_overhang', False)
            po_s = getattr(props, 'pillared_overhang_side', 'FRONT')
            # The pillared overhang supplies its own pillars/soffit on its facade,
            # so suppress the soffit there. The decorative jetty corbels are dropped
            # entirely whenever a pillared overhang exists, otherwise brackets are
            # left hanging inside the colonnade.
            inc_f = not (has_po and po_s == 'FRONT')
            inc_b = not (has_po and po_s == 'BACK')
            inc_l = not (has_po and po_s == 'LEFT')
            inc_r = not (has_po and po_s == 'RIGHT')
            # The side annex swallows the jetty pocket on its side, so the
            # decorative brackets would hang inside the annex room - drop them
            # there. The soffit board is kept: it closes the jetty underside and
            # becomes the annex ceiling edge.
            cor_l, cor_r = inc_l, inc_r
            if _annex_side in ('LEFT', 'BOTH') and _annex_floors > 0:
                cor_l = False
            if _annex_side in ('RIGHT', 'BOTH') and _annex_floors > 0:
                cor_r = False
            door_ex_f, door_ex_b, door_ex_l, door_ex_r = _get_floor_door_corbel_exclusions(
                fl_idx - 1, (prev_x_min, prev_x_max, prev_y_min, prev_y_max)
            )
            corbel_ex_f = []
            if front_ex:
                corbel_ex_f.append(front_ex)
            corbel_ex_f.extend(door_ex_f)
            build_cantilever_corbels(bm, x_min, x_max, y_min, y_max, z_floor,
                                    overhang_dist=overhang_step,
                                    front_exclude_x=corbel_ex_f if corbel_ex_f else None,
                                    back_exclude_x=door_ex_b if door_ex_b else None,
                                    left_exclude_y=door_ex_l if door_ex_l else None,
                                    right_exclude_y=door_ex_r if door_ex_r else None,
                                    include_front=inc_f, include_back=inc_b,
                                    include_left=cor_l, include_right=cor_r)
            build_cantilever_soffit(
                bm,
                (prev_x_min, prev_x_max, prev_y_min, prev_y_max),
                (x_min, x_max, y_min, y_max),
                z_floor,
                front_exclude_x=front_ex,
                include_front=inc_f,
                include_back=inc_b,
                include_left=inc_l,
                include_right=inc_r
            )

        # Determine staircase cutout for this floor (if coming from below)
        cur_stair_hole = floor_stair_holes.get(fl_idx, None)

        is_temporary_stockpile = (
            effective_archetype == 'WAREHOUSE'
            and getattr(props, 'material_tier', 'TIER_1') == 'TIER_1'
            and props.roof_style == 'NONE'
        )

        # Floor Slab (Ground floor is stone/timber/dirt; upper floors have stair cutout)
        if is_temporary_stockpile:
            pass
        else:
            tier_val = getattr(props, 'material_tier', 'TIER_3')
            is_stable_floor = (effective_archetype == 'STABLE' or getattr(props, 'building_archetype', '') == 'STABLE')
            floor_mat = MAT_INDEX_STONE if (fl_idx == 0 and (is_stable_floor or (props.ground_floor_stone and tier_val != 'TIER_1'))) else MAT_INDEX_FLOOR
            # Quarry / lumbermill Tier 1: the open timber frame stands on a wood
            # sill ring whose top sits exactly at z_floor + 0.05, so a
            # full-height slab would sit coplanar with the frame and z-fight
            # along the seam. Drop the ground-floor slab 3 cm to sit cleanly
            # below the sills.
            is_low_slab_t1 = (effective_archetype in ('LUMBERMILL', 'QUARRY') and fl_idx == 0
                              and getattr(props, 'material_tier', 'TIER_1') == 'TIER_1')
            slab_z = z_floor + 0.02 if is_low_slab_t1 else z_floor + 0.05
            # Main-block slab takes the stair hole only when the hole is
            # actually inside it (a wing-held cellar shaft belongs to the
            # wing slab instead, so the main slab stays solid).
            _main_hole = None
            if fl_idx > 0 and props.has_stairs:
                _main_hole = cur_stair_hole
            elif (fl_idx == 0 and getattr(props, 'has_basement_stair', False)
                  and cur_stair_hole is not None):
                _h = cur_stair_hole
                if not (_h[1] < slab_xmin or _h[0] > slab_xmax
                        or _h[3] < slab_ymin or _h[2] > slab_ymax):
                    _main_hole = _h
            build_floor_slab(
                bm,
                floor_idx=fl_idx,
                x_min=slab_xmin, x_max=slab_xmax,
                y_min=slab_ymin, y_max=slab_ymax,
                z_level=slab_z,
                thickness=0.12,
                stair_hole=_main_hole,
                mat_idx=floor_mat
            )
        
        # Upper floor safety guardrail around stair opening
        if fl_idx > 0 and props.has_stairs and cur_stair_hole is not None:
            sh_x1, sh_x2, sh_y1, sh_y2 = cur_stair_hole
            rail_x = min(slab_xmax - 0.10, sh_x2 + 0.05)
            if props.stair_style == 'SPIRAL':
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=sh_y1, x_start=sh_x1 + 0.20)
            elif is_tenement_stairs and D_interior >= 7.4:
                # Single-wall tandem stairwell: guard the walking aisle edge (+X)
                # and close off the foot end of the hole, keeping arrival end open
                arr_cycle = (fl_idx - 1) % 4
                ret_y = sh_y1 if arr_cycle in (0, 1) else sh_y2
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=ret_y, x_start=sh_x1)
            elif stair_switchback:
                # Switchback floor: this storey's opening is the lane the flight
                # below climbed, and the sibling lane is solid floor carrying the
                # next flight. On top floor, no next flight ascends so all 3 sides are guarded.
                if fl_idx == num_floors - 1:
                    dir_y = int(stair_ascend_sign) if ((fl_idx - 1) % 2 == 0) else int(-stair_ascend_sign)
                    climb_side = 'NORTH' if dir_y == 1 else 'SOUTH'
                    build_stair_guardrail_3sided(
                        bm, sh_x1, sh_x2, sh_y1, sh_y2, z_floor + 0.05,
                        climb_side=climb_side, offset=0.18, rail_h=0.95,
                        bounds=(slab_xmin, slab_xmax, slab_ymin, slab_ymax),
                    )
                elif (fl_idx - 1) % 2 == 0:
                    # Void over the WEST lane: walkable floor lies to its east
                    build_stair_guardrail(bm, sh_x2 + 0.18, sh_y1 - 0.18, sh_y2, z_floor + 0.05,
                                          return_y=sh_y2 + 0.18, x_start=sh_x1 - 0.18)
                else:
                    # Void over the EAST lane: walkable floor on BOTH sides
                    build_stair_guardrail(bm, sh_x1 - 0.18, sh_y1, sh_y2 + 0.18, z_floor + 0.05,
                                          return_y=sh_y1 - 0.18, x_start=sh_x2 + 0.18)
                    build_stair_guardrail(bm, min(slab_xmax - 0.08, sh_x2 + 0.18),
                                          sh_y1, sh_y2 + 0.18, z_floor + 0.05)
            else:
                # Straight stairs: guard the open stairwell on all 3 sides except the climb-up side,
                # offset 18 cm outward from the hole so it sits cleanly on the floor without overlapping
                # any stair stringers or pillars.
                if fl_idx == num_floors - 1:
                    dir_y = int(stair_ascend_sign) if ((fl_idx - 1) % 2 == 0) else int(-stair_ascend_sign)
                    climb_side = 'NORTH' if dir_y == 1 else 'SOUTH'
                    build_stair_guardrail_3sided(
                        bm, sh_x1, sh_x2, sh_y1, sh_y2, z_floor + 0.05,
                        climb_side=climb_side, offset=0.18, rail_h=0.95,
                        bounds=(slab_xmin, slab_xmax, slab_ymin, slab_ymax),
                    )
        
        # Wing floor slabs for compound shapes (never on open-air temporary
        # stockpiles: the yard stays bare dirt with pallets and awnings).
        if fl_has_wing and not is_temporary_stockpile:
            for w_elem, (w_xmin, w_xmax, w_ymin, w_ymax) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                if w_wall == 'FRONT':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = slab_ymin + 0.01
                elif w_wall == 'BACK':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = slab_ymax - 0.01
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02
                elif w_wall == 'LEFT':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = slab_xmin + 0.01
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02
                else: # RIGHT
                    w_slab_xmin = slab_xmax - 0.01
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02

                _w_hole = None
                if (fl_idx == 0 and getattr(props, 'has_basement_stair', False)
                        and cur_stair_hole is not None):
                    _h = cur_stair_hole
                    if not (_h[1] < w_slab_xmin or _h[0] > w_slab_xmax
                            or _h[3] < w_slab_ymin or _h[2] > w_slab_ymax):
                        _w_hole = _h
                # Slab (ground floor of wings is stone/timber/dirt; upper floors have stair cutout)
                build_floor_slab(
                    bm,
                    floor_idx=fl_idx,
                    x_min=w_slab_xmin, x_max=w_slab_xmax,
                    y_min=w_slab_ymin, y_max=w_slab_ymax,
                    z_level=z_floor + 0.05,
                    thickness=0.12,
                    stair_hole=_w_hole,
                    mat_idx=floor_mat
                )
                if fl_idx > 0 and fl_overhang > prev_fl_overhang:
                    overhang_step = fl_overhang - prev_fl_overhang
                    prev_wb = w_elem.get('bounds_fl', {}).get(fl_idx - 1, None)
                    if prev_wb:
                        build_cantilever_soffit(
                            bm,
                            prev_wb,
                            (w_xmin, w_xmax, w_ymin, w_ymax),
                            z_floor,
                            include_back=(w_wall != 'FRONT') and inc_b,
                            include_front=(w_wall != 'BACK') and inc_f,
                            include_left=(w_wall != 'RIGHT') and inc_l,
                            include_right=(w_wall != 'LEFT') and inc_r
                        )
                    w_corbel_ex_f = []
                    if fl_idx - 1 == 0 and w_wall == 'FRONT' and getattr(props, 'has_wing_door', False) and not open_timber:
                        w_cx = (w_xmin + w_xmax) * 0.5
                        w_dw = getattr(props, 'door_width', 1.0)
                        w_margin = w_dw * 0.5 + 0.50
                        w_corbel_ex_f.append((w_cx - w_margin, w_cx + w_margin))

                    build_cantilever_corbels(bm, w_xmin, w_xmax, w_ymin, w_ymax, z_floor,
                                            overhang_dist=overhang_step,
                                            front_exclude_x=w_corbel_ex_f if w_corbel_ex_f else None,
                                            include_back=(w_wall != 'FRONT') and inc_b,
                                            include_front=(w_wall != 'BACK') and inc_f,
                                            include_left=(w_wall != 'RIGHT') and inc_l,
                                            include_right=(w_wall != 'LEFT') and inc_r)

        # Determine next flight of stairs leading up to fl_idx + 1
        next_stair_hole = None
        if fl_idx < num_floors - 1 and props.has_stairs:
            if props.stair_style == 'SPIRAL':
                spiral_r = min(max(1.35, props.stair_width * 1.05), (fl0_ix_max - fl0_ix_min) * 0.42)
                spiral_cx = fl0_ix_min + spiral_r + 0.15
                spiral_cy = fl0_iy_max - spiral_r - 0.15
                fl_start_ang = -90.0
                build_spiral_staircase(
                    bm,
                    center_pos=(spiral_cx, spiral_cy, z_floor + 0.05),
                    target_z=z_ceil + 0.05,
                    radius=spiral_r,
                    start_ang_deg=fl_start_ang,
                    total_angle_deg=360.0
                )
                # Headroom cutout envelopes the entire circular stair path
                spiral_hole_xmin = spiral_cx - spiral_r - 0.08
                spiral_hole_xmax = spiral_cx + spiral_r + 0.08
                next_stair_hole = (spiral_hole_xmin, spiral_hole_xmax,
                                   spiral_cy - spiral_r - 0.06, min(iy_max, spiral_cy + spiral_r + 0.06))
            else:
                if is_tenement_stairs and D_interior >= 7.4:
                    # Single-wall tandem stair for tenements: all flights hug the same wall
                    cycle = fl_idx % 4
                    if cycle == 0:
                        # Floor 0: South flight climbs North (+Y)
                        y_foot, y_head = stair_y_s0, stair_y_s1
                        dir_y = 1
                    elif cycle == 1:
                        # Floor 1: North flight climbs North (+Y) (in-line continuation along SAME wall!)
                        y_foot, y_head = stair_y_n0, stair_y_n1
                        dir_y = 1
                    elif cycle == 2:
                        # Floor 2: South flight climbs South (-Y) (turned 180° and moved to South solid floor!)
                        y_foot, y_head = stair_y_s1, stair_y_s0
                        dir_y = -1
                    else: # cycle == 3
                        # Floor 3: North flight climbs South (-Y)
                        y_foot, y_head = stair_y_n1, stair_y_n0
                        dir_y = -1

                    stair_start = (stair_cx, y_foot, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len,
                                             direction_y=dir_y)
                    sh_y0 = min(y_foot, y_head) - 0.10
                    sh_y1 = max(y_foot, y_head) + 0.10
                    next_stair_hole = (stair_cx - stair_w * 0.5 - 0.08,
                                       stair_cx + stair_w * 0.5 + 0.12,
                                       sh_y0, sh_y1)
                else:
                    if fl_idx % 2 == 0:
                        lane_cx = lane_cx_0
                        stair_start = (lane_cx, stair_y_foot, z_floor + 0.05)
                        direction_y = int(stair_ascend_sign)
                    else:
                        lane_cx = lane_cx_1 if stair_switchback else lane_cx_0
                        stair_start = (lane_cx, stair_y_head, z_floor + 0.05)
                        direction_y = int(-stair_ascend_sign)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len,
                                             direction_y=direction_y)
                    next_stair_hole = (lane_cx - stair_w * 0.5 - 0.08, lane_cx + stair_w * 0.5 + 0.12,
                                       stair_y_bot - 0.10, stair_y_top + 0.10)
            
            floor_stair_holes[fl_idx + 1] = next_stair_hole

        # Ceiling Beams (underneath next floor, trimmed around stairs).
        # Never on open-air temporary stockpiles: with no walls or roof the
        # beams would float in mid-air over the yard.
        if props.has_ceiling_beams and not is_temporary_stockpile:
            build_ceiling_beams(
                bm, ix_min, ix_max, iy_min, iy_max, z_ceil - 0.02, spacing=1.2,
                stair_hole=next_stair_hole if (fl_idx < num_floors - 1 and props.has_stairs) else None
            )
        # Openings definitions for this floor
        front_openings = []
        back_openings = []
        left_openings = []
        right_openings = []
        
        w_front_openings = []
        w_left_openings = []
        w_right_openings = []

        # Corner turret doorways: a walk-through portal in the back wall so each
        # tower room opens straight into the hall (annex-style connection).
        # With a curtain wall the turret foot is buried in masonry, so the
        # ground-storey portal is skipped (it would open into the wall).
        _skip_ground_turret = bool(getattr(props, 'has_curtain_wall', False))
        for _tr in _turrets:
            if _skip_ground_turret and fl_idx == 0:
                continue
            _tcx = _tr['cx']
            _pw = 1.25  # Clear walkthrough width
            _ph = min(2.15, floor_h * 0.72)  # Clear walkthrough height
            _jw = 0.18  # Heavy timber jamb post width
            _jd = wall_t + 0.14  # Full casing depth: sits proud by 0.07m on both hall & turret sides
            _lh = 0.20  # Header lintel beam height
            _pz1 = z_floor + _ph

            # Wall opening cutout:
            # - In X: cutout edges align with the jamb centerlines (_tcx +/- (_pw * 0.5 + _jw * 0.5)),
            #   so each jamb overlaps 0.09m over the solid wall and 0.09m into the opening as a reveal liner.
            #   The rough cut edge is completely buried at the center of the jamb timber!
            # - In Z: cutout extends to _pz1 + _lh * 0.5 (halfway into the lintel beam),
            #   so the lintel caps the wall head by 0.10m and the underside of the lintel at _pz1 has
            #   zero coplanar conflict with the wall!
            _u_start = (_tcx - _pw * 0.5 - _jw * 0.5) - x_min
            _u_end = (_tcx + _pw * 0.5 + _jw * 0.5) - x_min
            back_openings.append({
                'u_start': _u_start,
                'u_end': _u_end,
                'z_start': z_floor,
                'z_end': _pz1 + _lh * 0.5
            })
            ctx.floor_doorways.setdefault(fl_idx, []).append({'x': _tcx, 'y': y_max, 'axis': 'X', 'w': _pw})

            # Left and Right Heavy Timber Casing Jambs:
            for _s in (-1.0, 1.0):
                create_beveled_box(
                    bm, size=(_jw, _jd, _ph),
                    location=(_tcx + _s * (_pw * 0.5 + _jw * 0.5), y_max, z_floor + _ph * 0.5),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
                )

            # Heavy Timber Header Lintel Beam resting on top of jambs:
            create_beveled_box(
                bm, size=(_pw + _jw * 2.0 + 0.06, _jd + 0.02, _lh),
                location=(_tcx, y_max, _pz1 + _lh * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014
            )

            # Beveled Wooden Floor Threshold Board bridging the floor opening:
            _th_h = 0.038
            create_beveled_box(
                bm, size=(_pw + _jw * 2.0 + 0.04, _jd + 0.04, _th_h),
                location=(_tcx, y_max, z_floor + _th_h * 0.5),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
            )

        win_w = props.window_width
        win_h = props.window_height
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val == 'TIER_1':
            # For authentic log cabins: window fits cleanly across 3 sawed-off logs
            # Row 1 (sill log) top is at 2.0 * log_diam (0.72)
            # Row 5 (lintel log) bottom is at 5.0 * log_diam (1.80)
            # Opening cutout height = 1.08m
            log_diam = 0.44
            win_cz = z_floor + 3.5 * log_diam
            win_z1 = z_floor + 2.0 * log_diam
            win_z2 = z_floor + 5.0 * log_diam
            win_h = win_z2 - win_z1
            win_w = props.window_width
        else:
            win_cz = z_floor + floor_h * 0.48
            win_z1 = win_cz - win_h * 0.5
            win_z2 = win_cz + win_h * 0.5

        # Doorway placement on Ground Floor (Front, Rear/Back, and Side Entrances)
        if fl_idx == 0:
            tier_val = getattr(props, 'material_tier', 'TIER_3')
            dw = getattr(props, 'door_width', 1.45)
            dh = getattr(props, 'door_height', 2.80)
            frame_margin = 0.08 if tier_val == 'TIER_1' else 0.12
            door_top_z = z_floor + dh + frame_margin
            door_cx = 0.0
            extra_front_doors = []

            # 1. Front Entrance
            side_entry_tenement = (
                effective_archetype == 'TENEMENT' and shape == 'RECTANGLE'
                and getattr(props, 'has_exterior_stairs', False)
                and getattr(props, 'exterior_stairs_side', 'LEFT') in ('LEFT', 'RIGHT')
            )
            if props.has_front_door and not open_timber and not side_entry_tenement:
                if shape == 'RECTANGLE':
                    door_offset = getattr(props, 'front_door_offset_x', 0.0)
                    if effective_archetype == 'TENEMENT' and getattr(props, 'has_stairs', False):
                        # Tenement with a real interior staircase: the entrance
                        # belongs in the common stair corridor on the left.
                        if stair_switchback:
                            # ...but NOT face-first into the bottom flight.  The
                            # switchback well is two lanes deep, so the door
                            # opens into the walkway strip beside it: you step in
                            # with a clear walking area ahead and the climb
                            # starts off to one side.
                            well_x1 = lane_cx_1 + stair_w * 0.5
                            # Centre the entrance in the walkway beside the well,
                            # leaving a clear margin of wall between the casing
                            # and the stairwell's east edge.
                            default_door_cx = min(well_x1 + dw * 0.5 + 0.15,
                                                  x_max - wall_t - dw * 0.5 - 0.25)
                        else:
                            # Align the door inside the hallway's 2.5m walking corridor,
                            # clear of the staircase and exterior corner.
                            default_door_cx = x_min + wall_t + 1.50 + dw * 0.5
                        door_cx = default_door_cx + door_offset
                    elif effective_archetype == 'TENEMENT':
                        _w = x_max - x_min
                        if _w >= 14.0:
                            door_cx = x_min + _w * 0.125 + door_offset
                            extra_front_doors = [
                                x_min + _w * 0.375,
                                x_min + _w * 0.625,
                                x_min + _w * 0.875,
                            ]
                        else:
                            _split = (x_min + x_max) * 0.5
                            door_cx = (x_min + _split) * 0.5 + door_offset
                            extra_front_doors = [(_split + x_max) * 0.5]
                    else:
                        door_cx = 0.0 + door_offset
                    door_yf = y_min
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                elif shape == 'L_SHAPE':
                    if wing_placement == 'FRONT':
                        door_cx = (x_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + x_max) * 0.5
                    else:
                        door_cx = 0.0
                    door_yf = y_min
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                elif shape == 'U_SHAPE':
                    door_yf = y_min
                    if effective_archetype == 'TENEMENT' and len(wings) >= 2:
                        # One street/courtyard door per back-block flat, at the
                        # same positions the upper floors use.
                        from .tenement import apartment_layout
                        _apts = apartment_layout((ix_min, ix_max, iy_min, iy_max),
                                                 'U_SHAPE', fl_wings_bounds, props)
                        _main_e = sorted(a['entry']['x'] for a in _apts
                                         if a['id'].startswith('main'))
                        if _main_e:
                            door_cx = _main_e[0]
                            extra_front_doors = list(_main_e[1:])
                        else:
                            door_cx = 0.0
                    else:
                        door_cx = 0.0  # Center of front courtyard
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                else: # T_SHAPE
                    if wing_placement == 'FRONT':
                        door_cx = (wings[0]['base'][0] + wings[0]['base'][1]) * 0.5
                        door_yf = wings[0]['base'][2]
                        door_u1 = (door_cx - dw * 0.5 - frame_margin) - wings[0]['base'][0]
                        door_u2 = (door_cx + dw * 0.5 + frame_margin) - wings[0]['base'][0]
                        w_front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    else:
                        door_cx = 0.0
                        door_yf = y_min
                        door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                        door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                        front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})

                main_door_cx = door_cx
                main_door_yf = door_yf
                ctx.floor_doorways.setdefault(0, []).append({'x': door_cx, 'y': door_yf, 'axis': 'X', 'w': dw})

                door_gf_stone = props.ground_floor_stone and tier_val != 'TIER_1'
                steps_mat = MAT_INDEX_TIMBER if (tier_val == 'TIER_1' or getattr(props, 'foundation_type', 'STONE') == 'WOOD') else MAT_INDEX_CUT_STONE

                build_door_assembly(
                    bm, center_x=door_cx, y_front=door_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                    normal_axis='-Y', include_leaf=getattr(props, 'include_door_leaves', True)
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=door_cx, y_front=door_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y', mat_index=steps_mat)

                # Additional front doors (exterior-entrance tenement: one per
                # ground-floor apartment). Each needs its own opening cut in
                # the wall, not just a door assembly.
                for _edx in extra_front_doors:
                    _eu1 = (_edx - dw * 0.5 - frame_margin) - x_min
                    _eu2 = (_edx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': _eu1, 'u_end': _eu2,
                                           'z_start': z_floor, 'z_end': door_top_z})
                    ctx.floor_doorways.setdefault(0, []).append({'x': _edx, 'y': y_min, 'axis': 'X', 'w': dw})
                    build_door_assembly(
                        bm, center_x=_edx, y_front=y_min, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                        normal_axis='-Y', include_leaf=getattr(props, 'include_door_leaves', True)
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=_edx, y_front=y_min, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y', mat_index=steps_mat)

            # 2. Rear / Back Door
            if getattr(props, 'has_back_door', False) and not open_timber:
                b_cx = 0.0
                if shape == 'L_SHAPE' and wing_placement == 'BACK':
                    b_cx = (x_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + x_max) * 0.5
                b_yf = y_max
                b_u1 = (b_cx - dw * 0.5 - frame_margin) - x_min
                b_u2 = (b_cx + dw * 0.5 + frame_margin) - x_min
                back_openings.append({'u_start': b_u1, 'u_end': b_u2, 'z_start': z_floor, 'z_end': door_top_z})
                ctx.floor_doorways.setdefault(0, []).append({'x': b_cx, 'y': b_yf, 'axis': 'X', 'w': dw})

                build_door_assembly(
                    bm, center_x=b_cx, y_front=b_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                    normal_axis='+Y', include_leaf=getattr(props, 'include_door_leaves', True)
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=b_cx, y_front=b_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+Y', mat_index=steps_mat)

            # 2b. Open rear portal (framed opening, no door leaf). Used to join
            # the nave to an attached chancel apse.
            if (getattr(props, 'has_back_portal', False) and not open_timber
                    and not getattr(props, 'has_back_door', False)):
                p_cx = 0.0
                p_yf = y_max
                p_w = max(dw, 1.7)
                p_top = z_floor + dh + frame_margin
                p_u1 = (p_cx - p_w * 0.5 - frame_margin) - x_min
                p_u2 = (p_cx + p_w * 0.5 + frame_margin) - x_min
                back_openings.append({'u_start': p_u1, 'u_end': p_u2,
                                      'z_start': z_floor, 'z_end': p_top})
                ctx.floor_doorways.setdefault(0, []).append({'x': p_cx, 'y': p_yf, 'axis': 'X', 'w': p_w})
                jamb = 0.16
                fy = p_yf  # Exactly centered on the rear wall line
                for jx in (-1.0, 1.0):
                    create_beveled_box(
                        bm, size=(jamb, wall_t + 0.04, p_top - z_floor),
                        location=(p_cx + jx * (p_w * 0.5 + jamb * 0.5), fy,
                                  (z_floor + p_top) * 0.5),
                        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
                create_beveled_box(
                    bm, size=(p_w + jamb * 2.0 + 0.04, wall_t + 0.04, jamb),
                    location=(p_cx, fy, p_top + jamb * 0.5),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
                # Level floor threshold bridging nave floor to apse with no height gap
                create_beveled_box(
                    bm, size=(p_w + 0.02, wall_t + 0.04, 0.03),
                    location=(p_cx, fy, z_floor + 0.035),
                    mat_index=MAT_INDEX_FLOOR, bevel_amount=0.005)

            # 3. Side Door
            if getattr(props, 'has_side_door', False) and not open_timber:
                s_facade = getattr(props, 'side_door_facade', 'LEFT')
                if s_facade == 'LEFT':
                    s_cy = (y_min + stair_y_bot) * 0.5 if (props.has_stairs and (stair_y_bot - y_min) > 2.0) else (y_min + y_max) * 0.5
                    s_xf = x_min
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    left_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    ctx.floor_doorways.setdefault(0, []).append({'x': s_xf, 'y': s_cy, 'axis': 'Y', 'w': dw})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                        normal_axis='-X', include_leaf=getattr(props, 'include_door_leaves', True)
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-X', mat_index=steps_mat)
                else: # RIGHT
                    s_cy = (y_min + y_max) * 0.5
                    s_xf = x_max
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    right_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    ctx.floor_doorways.setdefault(0, []).append({'x': s_xf, 'y': s_cy, 'axis': 'Y', 'w': dw})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                        normal_axis='+X', include_leaf=getattr(props, 'include_door_leaves', True)
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+X', mat_index=steps_mat)

        # Upper side door onto the side rampart deck (Tier 3 town halls)
        if fl_idx == 1 and getattr(props, 'has_side_rampart', False) and not open_timber:
            r_side = getattr(props, 'rampart_side', 'RIGHT')
            _composer = (getattr(props, 'town_hall_composer', False) and shape == 'T_SHAPE')
            if _composer:
                # The composer deck spans less than the wall (it starts behind
                # the clock tower and the ramp leaves from its front end), so
                # a wall-centre door can land past the deck next to the ramp.
                # Use the real deck span (same helper the deck builder uses).
                _dy0, _dy1, _dtop = town_hall_deck_span(
                    props, ctx.base_w * 0.5, ctx.base_d, ctx.found_h,
                    ctx.floor_h, -(ctx.base_d * 0.5) - ctx.raw_wing_d)
                _rspan = (_dy0, _dy1)
                _bias_back = True
            else:
                _rspan = rampart_deck_span(props, ctx)
                _bias_back = False
            if _rspan is not None:
                rdw = getattr(props, 'rampart_door_width', getattr(props, 'door_width', 1.20))
                rdh = min(props.door_height, 2.40)
                r_margin = 0.12
                r_top_z = z_floor + rdh + r_margin
                # Centre the door on the deck (not the wall) so it always lands
                # on the walk, clear of the descent ramp at the front end.
                # Composer decks start behind the tower with the ramp at the
                # front, so push the door toward the back end instead.
                r_cy = (_rspan[0] + _rspan[1]) * 0.5
                if _bias_back:
                    r_cy = _rspan[0] + (_rspan[1] - _rspan[0]) * 0.68
                    _clr = rdw * 0.5 + 0.9
                    r_cy = max(_rspan[0] + _clr, min(_rspan[1] - _clr, r_cy))
                if r_side == 'LEFT':
                    left_openings.append({'u_start': (r_cy - rdw * 0.5 - r_margin) - y_min,
                                          'u_end': (r_cy + rdw * 0.5 + r_margin) - y_min,
                                          'z_start': z_floor, 'z_end': r_top_z})
                    ctx.floor_doorways.setdefault(1, []).append({'x': x_min, 'y': r_cy, 'axis': 'Y', 'w': rdw})
                    # Recess the whole assembly into the wall so the arch
                    # surround and threshold sit nearly flush with the wall face
                    # instead of jutting onto the narrow deck walkway, which
                    # made the door unreachable from the ramp. The wall opening
                    # itself stays on the wall line; the jambs still lap it.
                    build_door_assembly(
                        bm, center_x=x_min + 0.10, y_front=r_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=rdw, door_h=rdh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                        normal_axis='-X', include_leaf=getattr(props, 'include_door_leaves', True)
                    )
                else:
                    right_openings.append({'u_start': (r_cy - rdw * 0.5 - r_margin) - y_min,
                                           'u_end': (r_cy + rdw * 0.5 + r_margin) - y_min,
                                           'z_start': z_floor, 'z_end': r_top_z})
                    ctx.floor_doorways.setdefault(1, []).append({'x': x_max, 'y': r_cy, 'axis': 'Y', 'w': rdw})
                    # Recessed like the LEFT branch so the deck stays walkable.
                    build_door_assembly(
                        bm, center_x=x_max - 0.10, y_front=r_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=rdw, door_h=rdh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                        normal_axis='+X', include_leaf=getattr(props, 'include_door_leaves', True)
                    )

        # Town-Hall annex portal: a plain walk-through opening into the side annex
        # (opposite the clock tower) on every floor the annex spans, so its upper
        # storey is reachable from inside the hall and no door leaf blocks it.
        if (fl_idx < _annex_floors and _annex_side is not None and not open_timber):
            _ap_w = 1.30
            _ap_h = min(2.30, floor_h * 0.78)
            _ap_m = 0.12
            _ap_top = z_floor + _ap_h + _ap_m
            _ap_cy = (y_min + y_max) * 0.5
            _jamb_w = 0.16
            _jamb_d = wall_t + 0.10
            _cut_sides = ['LEFT', 'RIGHT'] if _annex_side == 'BOTH' else [_annex_side]
            for _cs in _cut_sides:
                if _cs == 'LEFT':
                    left_openings.append({'u_start': (_ap_cy - _ap_w * 0.5 - _ap_m) - y_min,
                                          'u_end': (_ap_cy + _ap_w * 0.5 + _ap_m) - y_min,
                                          'z_start': z_floor, 'z_end': _ap_top})
                    _ap_fx = x_min
                else:
                    right_openings.append({'u_start': (_ap_cy - _ap_w * 0.5 - _ap_m) - y_min,
                                           'u_end': (_ap_cy + _ap_w * 0.5 + _ap_m) - y_min,
                                           'z_start': z_floor, 'z_end': _ap_top})
                    _ap_fx = x_max
                ctx.floor_doorways.setdefault(fl_idx, []).append({'x': _ap_fx, 'y': _ap_cy, 'axis': 'Y', 'w': _ap_w})
                # Timber jamb + lintel frame around the opening (no door leaf).
                for _s in (-1.0, 1.0):
                    create_beveled_box(
                        bm, size=(_jamb_d, _jamb_w, _ap_h + _ap_m),
                        location=(_ap_fx, _ap_cy + _s * (_ap_w * 0.5 + _jamb_w * 0.5),
                                  z_floor + (_ap_h + _ap_m) * 0.5),
                        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
                create_beveled_box(
                    bm, size=(_jamb_d, _ap_w + _jamb_w * 2.0, _ap_m),
                    location=(_ap_fx, _ap_cy, _ap_top - _ap_m * 0.5),
                    mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)

        # Interior walk-through portals between main building and wings
        # Open-timber pavilions (Warehouse/Lumbermill T1) have no walls, so the
        # arcade posts already leave the junction fully open - skip the floating
        # jamb/lintel/threshold frame that otherwise hovers mid-room.
        # Open-air temporary stockpiles have no walls at all, so the portal
        # frame and its full-height liner panels would stand alone in the
        # yard - skip them there too.
        # Tenement U-shaped wings are independent apartment suites with their own
        # exterior entrances, so they have solid demising walls rather than walk-in portals.
        if fl_has_wing and not open_timber and not is_temporary_stockpile and not (effective_archetype == 'TENEMENT' and shape == 'U_SHAPE'):
            for w_elem, (w_xmin, w_xmax, w_ymin, w_ymax) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                jamb_w = 0.18
                jamb_d = wall_t + 0.10  # Proud of wall into both rooms by 0.05m
                lower = 0.018
                portal_h = min(2.15, floor_h * 0.72)
                lintel_h = 0.20

                if w_wall in ('FRONT', 'BACK'):
                    wing_span = w_xmax - w_xmin
                    clear_margin = wall_t + jamb_w + 0.22
                    max_pw = max(1.2, wing_span - clear_margin * 2.0)
                    p_w = min(max_pw, 2.2)
                    p_cx = (w_xmin + w_xmax) * 0.5
                    p_yf = y_min if w_wall == 'FRONT' else y_max
                    # Nudge frame a hair into the main room so wood faces never sit coplanar with plaster
                    nudge = 0.015 if w_wall == 'FRONT' else -0.015
                    f_yf = p_yf + nudge
                    # Cutout in the wall matches the jamb center line so jambs cleanly lap the opening
                    p_u1 = (p_cx - p_w * 0.5 - jamb_w * 0.5) - x_min
                    p_u2 = (p_cx + p_w * 0.5 + jamb_w * 0.5) - x_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h * 0.5}
                    if w_wall == 'FRONT':
                        front_openings.append(op_dict)
                    else:
                        back_openings.append(op_dict)
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': p_cx, 'y': f_yf, 'axis': 'X', 'w': p_w})

                    create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                                       location=(p_cx - p_w * 0.5 - jamb_w * 0.5, f_yf, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                                       location=(p_cx + p_w * 0.5 + jamb_w * 0.5, f_yf, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    lintel_w = p_w + jamb_w * 2.0 + 0.06
                    create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                       location=(p_cx, f_yf, z_floor + portal_h + lintel_h * 0.5 - lower),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    # Beveled Wooden Floor Threshold Board bridging the floor opening
                    create_beveled_box(bm, size=(p_w + jamb_w * 2.0 + 0.06, wall_t + 0.16, 0.038),
                                       location=(p_cx, f_yf, z_floor + 0.05 + 0.019),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.008, bevel_segments=2)
                    # Interior liner: the main wall's outer (exterior) face would
                    # otherwise show inside the wing room. Cover the wing span
                    # with wood planks (portal cut out), tucking every liner
                    # edge under the portal jambs/lintel and the wing side walls
                    # so no raw edge ever shows.
                    _lt = 0.06
                    _ly = p_yf + (-1.0 if w_wall == 'FRONT' else 1.0) * (wall_t * 0.5)
                    _lx0 = w_xmin - 0.05
                    _lx1 = w_xmax + 0.05
                    _jx0 = p_cx - p_w * 0.5 - jamb_w + 0.03
                    _jx1 = p_cx + p_w * 0.5 + jamb_w - 0.03
                    _HH = z_ceil - z_floor
                    if _jx0 - _lx0 > 0.05:
                        create_beveled_box(
                            bm, size=((_jx0 - _lx0), _lt, _HH),
                            location=((_lx0 + _jx0) * 0.5, _ly, z_floor + _HH * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
                    if _lx1 - _jx1 > 0.05:
                        create_beveled_box(
                            bm, size=((_lx1 - _jx1), _lt, _HH),
                            location=((_jx1 + _lx1) * 0.5, _ly, z_floor + _HH * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
                    _ztop = z_floor + portal_h + lintel_h - 0.05
                    if z_ceil - _ztop > 0.05 and _jx1 - _jx0 > 0.05:
                        create_beveled_box(
                            bm, size=((_jx1 - _jx0), _lt, z_ceil - _ztop),
                            location=(p_cx, _ly, _ztop + (z_ceil - _ztop) * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
                else: # LEFT or RIGHT
                    wing_span = w_ymax - w_ymin
                    clear_margin = wall_t + jamb_w + 0.22
                    max_pw = max(1.2, wing_span - clear_margin * 2.0)
                    p_w = min(max_pw, 2.2)
                    p_cy = (w_ymin + w_ymax) * 0.5
                    p_xf = x_min if w_wall == 'LEFT' else x_max
                    # Same room-ward nudge as FRONT/BACK above
                    nudge = 0.015 if w_wall == 'LEFT' else -0.015
                    f_xf = p_xf + nudge
                    # Cutout in the wall matches the jamb center line so jambs cleanly lap the opening
                    p_u1 = (p_cy - p_w * 0.5 - jamb_w * 0.5) - y_min
                    p_u2 = (p_cy + p_w * 0.5 + jamb_w * 0.5) - y_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h * 0.5}
                    if w_wall == 'LEFT':
                        left_openings.append(op_dict)
                    else:
                        right_openings.append(op_dict)
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': f_xf, 'y': p_cy, 'axis': 'Y', 'w': p_w})

                    create_beveled_box(bm, size=(jamb_d, jamb_w, portal_h),
                                       location=(f_xf, p_cy - p_w * 0.5 - jamb_w * 0.5, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    create_beveled_box(bm, size=(jamb_d, jamb_w, portal_h),
                                       location=(f_xf, p_cy + p_w * 0.5 + jamb_w * 0.5, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    lintel_w = p_w + jamb_w * 2.0 + 0.06
                    create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                       location=(f_xf, p_cy, z_floor + portal_h + lintel_h * 0.5 - lower),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    # Beveled Wooden Floor Threshold Board bridging the floor opening
                    create_beveled_box(bm, size=(wall_t + 0.16, p_w + jamb_w * 2.0 + 0.06, 0.038),
                                       location=(f_xf, p_cy, z_floor + 0.05 + 0.019),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.008, bevel_segments=2)
                    # Interior liner (mirrors the FRONT/BACK case): cover the wing
                    # span of the main wall with wood planks on the wing side,
                    # portal cut out, all edges tucked under jambs/lintel/walls.
                    _lt = 0.06
                    _lx = p_xf + (-1.0 if w_wall == 'LEFT' else 1.0) * (wall_t * 0.5)
                    _ly0 = w_ymin - 0.05
                    _ly1 = w_ymax + 0.05
                    _jy0 = p_cy - p_w * 0.5 - jamb_w + 0.03
                    _jy1 = p_cy + p_w * 0.5 + jamb_w - 0.03
                    _HH = z_ceil - z_floor
                    if _jy0 - _ly0 > 0.05:
                        create_beveled_box(
                            bm, size=(_lt, (_jy0 - _ly0), _HH),
                            location=(_lx, (_ly0 + _jy0) * 0.5, z_floor + _HH * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
                    if _ly1 - _jy1 > 0.05:
                        create_beveled_box(
                            bm, size=(_lt, (_ly1 - _jy1), _HH),
                            location=(_lx, (_jy1 + _ly1) * 0.5, z_floor + _HH * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
                    _ztop = z_floor + portal_h + lintel_h - 0.05
                    if z_ceil - _ztop > 0.05 and _jy1 - _jy0 > 0.05:
                        create_beveled_box(
                            bm, size=(_lt, (_jy1 - _jy0), z_ceil - _ztop),
                            location=(_lx, p_cy, _ztop + (z_ceil - _ztop) * 0.5),
                            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)

        # Walk-in portal into mini-wing outcrop (layout decided up front)
        has_mw = getattr(props, 'has_mini_wing', False)

        def _mw_offs_for(facade):
            """(offset, width) of every outcrop occupying `facade` on this floor.

            An outcrop is capped below the ceiling, so it never reaches into the
            storey above; windows and framing up there only avoid this storey's
            outcrops.
            """
            return [(off, w) for _s, off, w, _d in _mw_spread.get(fl_idx, [])
                    if _s == facade]

        if has_mw and _mw_spread.get(fl_idx):
            mw_portal_h = min(2.15, floor_h * 0.78)
            shift_in = 0.05
            shift_down = 0.0
            jamb_w = 0.16
            # Reveal liner: centred on the wall and just a hair deeper, so it
            # lines the whole reveal instead of poking out of the outer face.
            jamb_d = wall_t + 0.02
            lintel_h = 0.18
            trim_clr = jamb_w - shift_in + 0.015
            _wall_c = {
                'FRONT': (None, y_min + wall_t * 0.5),
                'BACK': (None, y_max - wall_t * 0.5),
                'LEFT': (x_min + wall_t * 0.5, None),
                'RIGHT': (x_max - wall_t * 0.5, None),
            }

            for mw_side_i, _off, _mw_pw, _mw_pd in _mw_spread.get(fl_idx, []):
                mw_portal_w = min(1.30, max(0.0, _mw_pw) - 0.45)
                lintel_w = mw_portal_w + jamb_w * 2.0 - shift_in * 2.0 + 0.08
                _wc_x, _wc_y = _wall_c.get(mw_side_i, (None, None))
                if mw_side_i in ('FRONT', 'BACK'):
                    mw_u_mid = (x_max - x_min) * 0.5 + _off
                else:
                    mw_u_mid = (y_max - y_min) * 0.5 + _off

                mw_op = {
                    'u_start': mw_u_mid - mw_portal_w * 0.5,
                    'u_end': mw_u_mid + mw_portal_w * 0.5,
                    'z_start': z_floor,
                    'z_end': z_floor + mw_portal_h,
                    'trim_clearance': trim_clr
                }

                if mw_side_i == 'FRONT':
                    front_openings.append(mw_op)
                    p_cx = (x_min + x_max) * 0.5 + _off
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': p_cx, 'y': y_min, 'axis': 'X', 'w': mw_portal_w})
                    create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                       location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, _wc_y, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                       location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, _wc_y, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                       location=(p_cx, _wc_y, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                elif mw_side_i == 'BACK':
                    back_openings.append(mw_op)
                    p_cx = (x_min + x_max) * 0.5 + _off
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': p_cx, 'y': y_max, 'axis': 'X', 'w': mw_portal_w})
                    create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                       location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, _wc_y, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                       location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, _wc_y, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                       location=(p_cx, _wc_y, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                elif mw_side_i == 'LEFT':
                    left_openings.append(mw_op)
                    p_cy = (y_min + y_max) * 0.5 + _off
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': x_min, 'y': p_cy, 'axis': 'Y', 'w': mw_portal_w})
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                       location=(_wc_x, p_cy, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                elif mw_side_i == 'RIGHT':
                    right_openings.append(mw_op)
                    p_cy = (y_min + y_max) * 0.5 + _off
                    ctx.floor_doorways.setdefault(fl_idx, []).append({'x': x_max, 'y': p_cy, 'axis': 'Y', 'w': mw_portal_w})
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                       location=(_wc_x, p_cy, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

        # Balcony Doorway Cutouts
        balconies_on_fl = getattr(ctx, 'floor_balconies', {}).get(fl_idx, [])
        if not balconies_on_fl and floor_balc_side.get(fl_idx) is not None:
            balconies_on_fl = [{'side': floor_balc_side[fl_idx], 'offset': getattr(ctx, 'floor_balc_offset', {}).get(fl_idx, 0.0)}]
        b_side = floor_balc_side.get(fl_idx)
        b_side_next = floor_balc_side.get(fl_idx + 1)
        b_width = getattr(props, 'balcony_width', 2.4)

        balc_door_w = 0.95
        balc_door_h = min(2.15, floor_h * 0.76)
        for b_entry in balconies_on_fl:
            bs = b_entry.get('side')
            if bs is None:
                continue
            b_off = b_entry.get('offset', 0.0)
            if bs in ('FRONT', 'BACK'):
                b_cx = (x_min + x_max) * 0.5 + b_off
                b_cy = y_min if bs == 'FRONT' else y_max
                b_u_mid = b_cx - x_min
                b_axis = 'X'
            else:
                b_cx = x_min if bs == 'LEFT' else x_max
                b_cy = (y_min + y_max) * 0.5 + b_off
                b_u_mid = b_cy - y_min
                b_axis = 'Y'

            b_op = {
                'u_start': b_u_mid - balc_door_w * 0.5,
                'u_end': b_u_mid + balc_door_w * 0.5,
                'z_start': z_floor,
                'z_end': z_floor + balc_door_h
            }
            if bs == 'FRONT':
                front_openings.append(b_op)
            elif bs == 'BACK':
                back_openings.append(b_op)
            elif bs == 'LEFT':
                left_openings.append(b_op)
            elif bs == 'RIGHT':
                right_openings.append(b_op)

            # Register balcony doorway in ctx so room planning partitions & furnishings avoid it
            ctx.floor_doorways.setdefault(fl_idx, []).append({
                'x': b_cx, 'y': b_cy, 'axis': b_axis, 'w': balc_door_w, 'is_balcony': True
            })

        # Dynamic Windows - Facade Openings & Shutters
        # Dynamic Windows - Facade Openings & Shutters
        eff_spacing = max(1.6, (props.window_spacing / max(0.2, getattr(props, 'window_density', 1.0))) * 1.5)
        win_w_clr = (win_w * 0.5 + 0.65) if props.has_shutters else (win_w * 0.5 + 0.45)
        w_top_roof_z = (found_h + wing_floors * floor_h + props.roof_height * 0.88) if has_wing else 0.0

        def carve_intervals(spans, excludes, min_len):
            cur_spans = list(spans)
            for ex1, ex2 in excludes:
                next_spans = []
                for s1, s2 in cur_spans:
                    if ex2 <= s1 or ex1 >= s2:
                        next_spans.append((s1, s2))
                    else:
                        if ex1 - s1 >= min_len:
                            next_spans.append((s1, ex1))
                        if s2 - ex2 >= min_len:
                            next_spans.append((ex2, s2))
                cur_spans = next_spans
            return cur_spans

        def get_shutter_info(wx_val, wy_val, wz_val):
            if not props.has_shutters:
                return False, False
            if effective_archetype == 'TENEMENT' and getattr(props, 'has_exterior_stairs', False):
                stair_side = getattr(props, 'exterior_stairs_side', 'LEFT')
                if stair_side == 'LEFT' and abs(wx_val - x_min) < 0.08:
                    return False, False
                if stair_side == 'RIGHT' and abs(wx_val - x_max) < 0.08:
                    return False, False
                if stair_side == 'COURTYARD' and shape == 'U_SHAPE':
                    if abs(wy_val - y_min) < 0.08:
                        gap_lo = max(wings[0]['base'][1], x_min)
                        gap_hi = min(wings[1]['base'][0], x_max)
                        if gap_lo <= wx_val <= gap_hi:
                            return False, False
                    for wing, wing_bounds in zip(wings, fl_wings_bounds):
                        wx1, wx2, wy1, wy2 = wing_bounds
                        inner_x = wx2 if wing.get('id', 0) == 0 else wx1
                        if abs(wx_val - inner_x) < 0.08 and wy1 <= wy_val <= wy2:
                            return False, False
            st = getattr(props, 'shutter_state', 'OPEN')
            if st == 'CLOSED':
                return True, True
            elif st == 'PARTIAL':
                pct = getattr(props, 'shutter_closed_amount', 0.5)
                h = int(abs(math.sin(wx_val * 12.9898 + wy_val * 78.233 + wz_val * 37.719 + seed * 19.113)) * 10000) % 100
                return True, (h < int(pct * 100))
            return True, False

        def get_facade_wing_exclusions(facade_name):
            excludes = []
            if not has_wing:
                return excludes
            for w_e in wings:
                # Active if floor is part of wing OR wing roof reaches this floor
                if not (fl_has_wing or (z_floor < w_top_roof_z + 0.35)):
                    continue
                w_wall = w_e['wall']
                wb = w_e.get('bounds_fl', {}).get(fl_idx, None)
                if wb is None:
                    wb = w_e.get('bounds_fl', {}).get(wing_floors - 1, w_e['base'])
                
                # 1. Direct attachment to this facade
                if w_wall == facade_name:
                    if facade_name in ('FRONT', 'BACK'):
                        excludes.append((wb[0] - win_w_clr, wb[1] + win_w_clr))
                    else: # LEFT or RIGHT
                        excludes.append((wb[2] - win_w_clr, wb[3] + win_w_clr))
                
                # 2. Adjacent corner attachment flush with this facade
                if facade_name == 'LEFT':
                    if w_wall in ('FRONT', 'BACK') and (wb[0] <= x_min + 0.35):
                        if w_wall == 'FRONT':
                            excludes.append((y_min - 0.50, y_min + win_w_clr + 0.40))
                        else: # BACK
                            excludes.append((y_max - (win_w_clr + 0.40), y_max + 0.50))
                elif facade_name == 'RIGHT':
                    if w_wall in ('FRONT', 'BACK') and (wb[1] >= x_max - 0.35):
                        if w_wall == 'FRONT':
                            excludes.append((y_min - 0.50, y_min + win_w_clr + 0.40))
                        else: # BACK
                            excludes.append((y_max - (win_w_clr + 0.40), y_max + 0.50))
                elif facade_name == 'FRONT':
                    if w_wall in ('LEFT', 'RIGHT') and (wb[2] <= y_min + 0.35):
                        if w_wall == 'LEFT':
                            excludes.append((x_min - 0.50, x_min + win_w_clr + 0.40))
                        else: # RIGHT
                            excludes.append((x_max - (win_w_clr + 0.40), x_max + 0.50))
                elif facade_name == 'BACK':
                    if w_wall in ('LEFT', 'RIGHT') and (wb[3] >= y_max - 0.35):
                        if w_wall == 'LEFT':
                            excludes.append((x_min - 0.50, x_min + win_w_clr + 0.40))
                        else: # RIGHT
                            excludes.append((x_max - (win_w_clr + 0.40), x_max + 0.50))
            return excludes

        def get_turret_exclusions(facade_name):
            """Keep facade windows clear of the square corner turrets."""
            ex = []
            for _tr in _turrets:
                _tcx, _th = _tr['cx'], _tr['half']
                if facade_name == 'BACK':
                    ex.append((_tcx - _th - win_w_clr, _tcx + _th + win_w_clr))
                if facade_name == ('RIGHT' if _tcx > 0 else 'LEFT'):
                    ex.append((y_max - 0.9, y_max + 1.2))
            return ex

        # Exterior staircase footprints, keyed by facade, so windows never land
        # behind the flights or landings.
        ext_stair_excl = {}
        if getattr(props, 'has_exterior_stairs', False) and not open_timber:
            _sp = _ext_stair_plan(props, ctx)
            if _sp:
                for _w, _fl, (_a0, _a1) in _sp['rects']:
                    ext_stair_excl.setdefault(_w, []).append((_a0, _a1))

        # Determine industrial cargo dock facade placement
        rec_cargo_side = getattr(props, 'cargo_dock_facade', 'AUTO')
        if rec_cargo_side == 'AUTO':
            rec_cargo_side = 'FRONT' if effective_archetype == 'LUMBERMILL' else 'LEFT'

        # Rectangular main building cargo dock / freight opening (Front facade)
        front_cargo_port_cx = None
        if not open_timber and not fl_has_wing and rec_cargo_side == 'FRONT':
            _is_t3 = (effective_archetype == 'LUMBERMILL' and getattr(props, 'material_tier', 'TIER_3') == 'TIER_3')
            _is_mill = (effective_archetype == 'LUMBERMILL')
            if _is_mill:
                # Lumber mill: wide open portal taking up almost the entire side/front section so you can see inside!
                _door_x = getattr(props, 'front_door_offset_x', 0.0) if getattr(props, 'has_front_door', True) else None
                if _door_x is not None and _door_x < 0:
                    _dock_x1 = max(x_min + 0.6, _door_x + getattr(props, 'door_width', 1.2) * 0.5 + 0.6)
                else:
                    _dock_x1 = x_min + 0.6
                _dock_x2 = x_max - 0.6
                _cp_w = max(3.5, _dock_x2 - _dock_x1)
                _cp_cx = (_dock_x1 + _dock_x2) * 0.5
                _cp_h = min(floor_h - 0.35, 3.2 if _is_t3 else 3.0)
                _dock_depth = 3.2 if _is_t3 else 2.5
            else:
                _cp_w = 2.6
                _cp_h = min(2.8, floor_h - 0.35)
                _cp_cx = 3.5 if cur_w > 13.5 else 3.2
                _dock_depth = 3.2 if _is_t3 else 2.2
                _dock_x1 = 0.8
                _dock_x2 = _dock_x1 + (6.0 if _is_t3 else 5.0)
            front_cargo_port_cx = _cp_cx

            if fl_idx == 0 and effective_archetype in ('LUMBERMILL', 'WAREHOUSE', 'QUARRY') and not is_temporary_stockpile:
                front_openings.append({
                    'u_start': _cp_cx - _cp_w * 0.5 - x_min,
                    'u_end': _cp_cx + _cp_w * 0.5 - x_min,
                    'z_start': z_floor,
                    'z_end': z_floor + _cp_h
                })
                build_cargo_port_frame(
                    bm, face_coord=y_min, outward_sgn=-1.0, portal_center=_cp_cx,
                    portal_w=_cp_w, portal_h=_cp_h, z_floor=z_floor, wall_t=wall_t,
                    dock_span1=_dock_x1, dock_span2=_dock_x2,
                    axis='Y', deck_depth=_dock_depth
                )
            elif fl_idx == 1 and getattr(props, 'has_upper_cargo_crane', False):
                front_openings.append({
                    'u_start': _cp_cx - _cp_w * 0.5 - x_min,
                    'u_end': _cp_cx + _cp_w * 0.5 - x_min,
                    'z_start': z_floor,
                    'z_end': z_floor + _cp_h
                })
                build_cargo_port_frame(
                    bm, face_coord=y_min, outward_sgn=-1.0, portal_center=_cp_cx,
                    portal_w=_cp_w, portal_h=_cp_h, z_floor=z_floor, wall_t=wall_t,
                    dock_span1=_dock_x1, dock_span2=_dock_x2,
                    axis='Y', deck_depth=_dock_depth,
                    is_upper_tier=True, lower_z_floor=found_h,
                    has_upper_crane=True
                )

        # Plan discrete rooms and interior walls for this floor
        # Landing-door spots are known before planning (pure stair geometry),
        # so partitions can avoid them by construction; the builder below
        # re-derives the same spots and nudges only as a backup.
        _stair_door_spots = {}
        if getattr(props, 'has_exterior_stairs', False) and not open_timber:
            try:
                _stair_door_spots = _ext_stair_door_spots(props, ctx) or {}
            except Exception:
                _stair_door_spots = {}
        _plan_doorways = list(ctx.floor_doorways.get(fl_idx, []))
        _plan_doorways.extend(_stair_door_spots.get(fl_idx, []))
        for ed in getattr(props, 'extra_doorways', []):
            if ed.get('floor_idx', 0) == fl_idx:
                sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
                if sax == 'Y':
                    xf = ix_min if ed.get('facade') == 'LEFT' else ix_max
                    _plan_doorways.append({'x': xf, 'y': ed.get('pos', 0.0), 'axis': 'Y', 'w': ed.get('w', 1.8)})
                else:
                    yf = iy_max if ed.get('facade') == 'BACK' else iy_min
                    _plan_doorways.append({'x': ed.get('pos', 0.0), 'y': yf, 'axis': 'X', 'w': ed.get('w', 1.8)})
        fl_rooms, fl_interior_walls = plan_floor_rooms(
            fl_idx, (ix_min, ix_max, iy_min, iy_max),
            stair_hole=cur_stair_hole or next_stair_hole,
            stair_pos_info={
                # For a tenement switchback `cx`/`w` describe the WHOLE well (both
                # lanes), so the hall clears both flights and still keeps a
                # walkway beside them; otherwise they describe the single lane.
                'cx': stair_cx,
                'w': (stair_w * 2.0 + lane_gap) if stair_switchback else stair_w,
                'y_bot': stair_y_bot, 'y_top': stair_y_top,
                'y_ascend': stair_ascend_sign,
                'has_stairs': props.has_stairs, 'style': props.stair_style,
                'switchback': stair_switchback, 'walk_w': 1.05
            },
            front_door_info=(door_cx, getattr(props, 'door_width', 1.0)) if (
                fl_idx == 0 and props.has_front_door and not open_timber
                and not (effective_archetype == 'TENEMENT' and shape == 'RECTANGLE'
                         and getattr(props, 'has_exterior_stairs', False)
                         and getattr(props, 'exterior_stairs_side', 'LEFT') in ('LEFT', 'RIGHT'))
            ) else None,
            fl_wings_bounds=fl_wings_bounds if fl_has_wing else None,
            effective_archetype=effective_archetype,
            props=props,
            seed=seed + fl_idx * 17,
            doorways=_plan_doorways
        )
        floor_rooms[fl_idx] = fl_rooms
        floor_interior_walls[fl_idx] = fl_interior_walls

        # Exterior apartment-stair doors are placed AFTER room planning so
        # they can dodge the interior partition walls (a partition running
        # into the facade must never bisect a doorway).
        _place_exterior_stair_doors(
            bm, props, ctx, fl_idx, z_floor,
            x_min, x_max, y_min, y_max, wall_t,
            ix_min, ix_max, iy_min, iy_max, fl_interior_walls,
            left_openings, right_openings, front_openings, back_openings)

        # Dynamic Windows - Front Wall
        if props.has_windows and getattr(props, 'window_front', True) and not open_timber:
            front_excludes = list(get_facade_wing_exclusions('FRONT')) + get_turret_exclusions('FRONT')
            front_excludes += ext_stair_excl.get('FRONT', [])
            balcony_overhead = (b_side_next == 'FRONT')

            # Interior wall exclusions on Front facade
            for iw in fl_interior_walls:
                if iw['axis'] == 'Y':
                    wx_p = iw['pos']
                    front_excludes.append((wx_p - 0.50, wx_p + 0.50))
            
            # Doorway exclusions on Front facade (ALL floors): entrance doors, exterior stair doors, balcony doors
            for d in ctx.floor_doorways.get(fl_idx, []):
                if d.get('axis') == 'X' and abs(d.get('y', y_min) - y_min) < 0.8:
                    _dw = d.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    front_excludes.append((d['x'] - _dclr, d['x'] + _dclr))
            for spot in _stair_door_spots.get(fl_idx, []):
                if spot.get('axis', 'X') == 'X' and abs(spot.get('y', y_min) - y_min) < 0.8:
                    _dw = spot.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    front_excludes.append((spot['x'] - _dclr, spot['x'] + _dclr))

            # Door exclusion zone calculation on floor 0
            if fl_idx == 0 and props.has_front_door and not side_entry_tenement:
                door_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                d_ex1 = door_cx - door_clr
                d_ex2 = door_cx + door_clr
                front_excludes.append((d_ex1, d_ex2))
                # Additional tenement front doors need the same window clearance.
                for _edx in extra_front_doors:
                    front_excludes.append((_edx - door_clr, _edx + door_clr))

            if front_cargo_port_cx is not None and (fl_idx == 0 or (fl_idx == 1 and getattr(props, 'has_upper_cargo_crane', False))):
                front_excludes.append((front_cargo_port_cx - _cp_w * 0.5 - 0.5, front_cargo_port_cx + _cp_w * 0.5 + 0.5))
                
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('FRONT'):
                    mw_cx = (x_min + x_max) * 0.5 + _off
                    front_excludes.append((mw_cx - (_mw_pw * 0.5 + win_w_clr), mw_cx + (_mw_pw * 0.5 + win_w_clr)))
                
            for b_ent in balconies_on_fl:
                if b_ent.get('side') == 'FRONT':
                    b_cx = (x_min + x_max) * 0.5 + b_ent.get('offset', 0.0)
                    front_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))
            if b_side_next == 'FRONT':
                b_cx = (x_min + x_max) * 0.5 + getattr(ctx, 'floor_balc_offset', {}).get(fl_idx + 1, 0.0)
                front_excludes.append((b_cx - (b_width * 0.5 + 0.45), b_cx + (b_width * 0.5 + 0.45)))

            front_win_xs = []
            front_rooms = [rm for rm in fl_rooms if 'FRONT' in rm.exterior_facades
                           and not getattr(rm, 'is_wing', False)
                           and (x_min - 0.05 <= rm.exterior_facades['FRONT'][0] and rm.exterior_facades['FRONT'][1] <= x_max + 0.05)]
            if front_rooms:
                for rm in front_rooms:
                    rx0, rx1 = rm.exterior_facades['FRONT']
                    rm_spans = carve_intervals([(rx0, rx1)], front_excludes, min_len=win_w + 0.35)
                    for s1, s2 in rm_spans:
                        span_l = s2 - s1
                        if span_l < 1.35:
                            continue
                        if fl_idx == 0 and props.has_stairs and cur_w < 6.0 and s2 <= 0.0:
                            continue
                        if span_l < 3.4:
                            front_win_xs.append((s1 + s2) * 0.5)
                        else:
                            front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.9))
            else:
                front_spans = carve_intervals([(x_min, x_max)], front_excludes, min_len=win_w + 0.35)
                for s1, s2 in front_spans:
                    if fl_idx == 0 and props.has_stairs and cur_w < 6.0 and s2 <= 0.0:
                        continue
                    front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))

            # Strict safety filter
            front_win_xs = [wx for wx in front_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in front_excludes)]

            for wx in front_win_xs:
                wu = (wx - x_min)
                front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                window_centers.setdefault(fl_idx, {}).setdefault('FRONT', []).append((wx, y_min, win_z1))
                sh_act, sh_cl = get_shutter_info(wx, y_min, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_min, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-Y',
                    has_shutters=sh_act, shutters_closed=sh_cl
                )

        # Dynamic Windows - Back Wall
        if props.has_windows and getattr(props, 'window_back', True) and not open_timber:
            back_excludes = list(get_facade_wing_exclusions('BACK')) + get_turret_exclusions('BACK')
            back_excludes += ext_stair_excl.get('BACK', [])
            for iw in fl_interior_walls:
                if iw['axis'] == 'Y':
                    wx_p = iw['pos']
                    back_excludes.append((wx_p - 0.50, wx_p + 0.50))

            # Doorway exclusions on Back facade (ALL floors)
            for d in ctx.floor_doorways.get(fl_idx, []):
                if d.get('axis') == 'X' and abs(d.get('y', y_max) - y_max) < 0.8:
                    _dw = d.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    back_excludes.append((d['x'] - _dclr, d['x'] + _dclr))
            for spot in _stair_door_spots.get(fl_idx, []):
                if spot.get('axis', 'X') == 'X' and abs(spot.get('y', y_max) - y_max) < 0.8:
                    _dw = spot.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    back_excludes.append((spot['x'] - _dclr, spot['x'] + _dclr))

            if effective_archetype == 'CHAPEL' or getattr(props, 'has_back_portal', False):
                apse_r = max(1.8, min(3.2, cur_w * 0.32))
                back_excludes.append((-apse_r - 0.6, apse_r + 0.6))
            if fl_idx == 0 and getattr(props, 'has_back_door', False):
                bd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                bd_ex1 = b_cx - bd_clr
                bd_ex2 = b_cx + bd_clr
                back_excludes.append((bd_ex1, bd_ex2))
                
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('BACK'):
                    mw_cx = (x_min + x_max) * 0.5 + _off
                    back_excludes.append((mw_cx - (_mw_pw * 0.5 + win_w_clr), mw_cx + (_mw_pw * 0.5 + win_w_clr)))
                
            for b_ent in balconies_on_fl:
                if b_ent.get('side') == 'BACK':
                    b_cx = (x_min + x_max) * 0.5 + b_ent.get('offset', 0.0)
                    back_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))

            back_win_xs = []
            back_rooms = [rm for rm in fl_rooms if 'BACK' in rm.exterior_facades
                          and not getattr(rm, 'is_wing', False)
                          and (x_min - 0.05 <= rm.exterior_facades['BACK'][0] and rm.exterior_facades['BACK'][1] <= x_max + 0.05)]
            if back_rooms:
                for rm in back_rooms:
                    rx0, rx1 = rm.exterior_facades['BACK']
                    rm_spans = carve_intervals([(rx0, rx1)], back_excludes, min_len=win_w + 0.35)
                    for s1, s2 in rm_spans:
                        span_l = s2 - s1
                        if span_l < 1.35:
                            continue
                        if span_l < 3.4:
                            back_win_xs.append((s1 + s2) * 0.5)
                        else:
                            back_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.9))
            else:
                back_spans = carve_intervals([(x_min, x_max)], back_excludes, min_len=win_w + 0.35)
                for s1, s2 in back_spans:
                    back_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))

            back_win_xs = [wx for wx in back_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in back_excludes)]

            for wx in back_win_xs:
                wu = (wx - x_min)
                back_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                window_centers.setdefault(fl_idx, {}).setdefault('BACK', []).append((wx, y_max, win_z1))
                sh_act, sh_cl = get_shutter_info(wx, y_max, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_max, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+Y',
                    has_shutters=sh_act, shutters_closed=sh_cl
                )

        # Dynamic Windows - Side Walls (Left and Right)
        if not open_timber and cur_d > 2.8:
            # Left side
            left_excludes = list(get_facade_wing_exclusions('LEFT')) + get_turret_exclusions('LEFT')
            left_excludes += ext_stair_excl.get('LEFT', [])
            for iw in fl_interior_walls:
                if iw['axis'] == 'X':
                    wy_p = iw['pos']
                    left_excludes.append((wy_p - 0.50, wy_p + 0.50))

            if fl_idx == 0 and props.has_stairs:
                left_excludes.append((stair_y_bot - 0.25, stair_y_top + 0.25))
            # Exterior apartment staircase runs along this wall: keep windows
            # (and their shutters) clear of the flight and landing.
            if (getattr(props, 'has_exterior_stairs', False)
                    and getattr(props, 'exterior_stairs_side', 'LEFT') == 'LEFT'
                    and fl_idx in (0, 1)):
                _es_span = _ext_stairs_y_span(props, ctx)
                if _es_span is not None:
                    left_excludes.append(_es_span)
            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'LEFT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                left_excludes.append((s_cy - sd_clr, s_cy + sd_clr))
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('LEFT'):
                    mw_cy = (y_min + y_max) * 0.5 + _off
                    left_excludes.append((mw_cy - (_mw_pw * 0.5 + win_w_clr), mw_cy + (_mw_pw * 0.5 + win_w_clr)))
            if _annex_side in ('LEFT', 'BOTH') and fl_idx <= _annex_floors:
                left_excludes.append(_annex_y_span)
            # Doorway exclusions on Left facade (ALL floors)
            for d in ctx.floor_doorways.get(fl_idx, []):
                if d.get('axis') == 'Y' and abs(d.get('x', x_min) - x_min) < 0.8:
                    _dw = d.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    left_excludes.append((d['y'] - _dclr, d['y'] + _dclr))

            if (fl_idx == 1 and getattr(props, 'has_side_rampart', False)
                    and getattr(props, 'rampart_side', 'RIGHT') == 'LEFT'):
                _rc = (y_min + y_max) * 0.5
                _rclr = min(props.door_width, 1.30) * 0.5 + win_w * 0.5 + 0.35
                left_excludes.append((_rc - _rclr, _rc + _rclr))
            for b_ent in balconies_on_fl:
                if b_ent.get('side') == 'LEFT':
                    b_cy = (y_min + y_max) * 0.5 + b_ent.get('offset', 0.0)
                    left_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            # Rectangular main building cargo dock / freight opening (Left)
            if fl_idx == 0 and effective_archetype in ('LUMBERMILL', 'WAREHOUSE') and not is_temporary_stockpile and not fl_has_wing and rec_cargo_side == 'LEFT':
                _is_mill = (effective_archetype == 'LUMBERMILL')
                if _is_mill:
                    _cp_w = max(2.6, (y_max - y_min) - 1.2)
                    _cp_h = min(floor_h - 0.35, 3.0)
                    _dock_y1 = y_min + 0.5
                    _dock_y2 = y_max - 0.5
                else:
                    _cp_w = 2.6
                    _cp_h = min(2.8, floor_h - 0.35)
                    _dock_y1 = y_min + 0.4
                    _dock_y2 = y_max - 0.4
                _cp_cy = (y_min + y_max) * 0.5
                left_excludes.append((_cp_cy - _cp_w * 0.5 - 0.5, _cp_cy + _cp_w * 0.5 + 0.5))
                left_openings.append({'u_start': _cp_cy - _cp_w * 0.5 - y_min, 'u_end': _cp_cy + _cp_w * 0.5 - y_min, 'z_start': z_floor, 'z_end': z_floor + _cp_h})
                build_cargo_port_frame(bm, x_min, -1.0, _cp_cy, _cp_w, _cp_h, z_floor, wall_t, dock_y1=_dock_y1, dock_y2=_dock_y2)
            elif fl_idx == 1 and getattr(props, 'has_upper_cargo_crane', False) and rec_cargo_side == 'LEFT':
                _cp_w = 2.0
                _cp_h = min(2.5, floor_h - 0.35)
                _cp_cy = (y_min + y_max) * 0.5
                left_excludes.append((_cp_cy - _cp_w * 0.5 - 0.5, _cp_cy + _cp_w * 0.5 + 0.5))
                left_openings.append({'u_start': _cp_cy - _cp_w * 0.5 - y_min, 'u_end': _cp_cy + _cp_w * 0.5 - y_min, 'z_start': z_floor, 'z_end': z_floor + _cp_h})
                from .accessories.crane import build_wall_jib_crane
                build_wall_jib_crane(bm, wall_x=x_min, wall_y=_cp_cy, z_mount=z_floor, outward_dir=(-1.0, 0.0), jib_len=2.8)

            if props.has_windows and getattr(props, 'window_left', True):
                left_win_ys = []
                left_rooms = [rm for rm in fl_rooms if 'LEFT' in rm.exterior_facades
                              and not getattr(rm, 'is_wing', False)
                              and (y_min - 0.05 <= rm.exterior_facades['LEFT'][0] and rm.exterior_facades['LEFT'][1] <= y_max + 0.05)]
                if left_rooms:
                    for rm in left_rooms:
                        ry0, ry1 = rm.exterior_facades['LEFT']
                        rm_spans = carve_intervals([(ry0, ry1)], left_excludes, min_len=win_w + 0.35)
                        for s1, s2 in rm_spans:
                            span_l = s2 - s1
                            if span_l < 1.35:
                                continue
                            if span_l < 3.4:
                                left_win_ys.append((s1 + s2) * 0.5)
                            else:
                                left_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.9))
                else:
                    left_spans = carve_intervals([(y_min, y_max)], left_excludes, min_len=win_w + 0.35)
                    for s1, s2 in left_spans:
                        left_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))

                left_win_ys = [wy for wy in left_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in left_excludes)]

                for wy in left_win_ys:
                    wu = (wy - y_min)
                    left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                    window_centers.setdefault(fl_idx, {}).setdefault('LEFT', []).append((x_min, wy, win_z1))
                    sh_act, sh_cl = get_shutter_info(x_min, wy, win_cz)
                    build_window_assembly(
                        bm, center=(x_min, wy, win_cz), size=(win_w, win_h),
                        wall_thickness=wall_t, normal_axis='-X',
                        has_shutters=sh_act, shutters_closed=sh_cl
                    )

            # Right side
            right_excludes = list(get_facade_wing_exclusions('RIGHT')) + get_turret_exclusions('RIGHT')
            right_excludes += ext_stair_excl.get('RIGHT', [])
            for iw in fl_interior_walls:
                if iw['axis'] == 'X':
                    wy_p = iw['pos']
                    right_excludes.append((wy_p - 0.50, wy_p + 0.50))

            # Bakery hearth oven: fixed depth-centre slot against the +X wall.
            # Keep glazing clear of it so the room planner can reserve one
            # uncut bakehouse chamber (oven body + work apron) around it.
            if fl_idx == 0 and effective_archetype == 'BAKERY':
                from .accessories.bakery import OVEN_WIN_CLEAR
                _ocy = (y_min + y_max) * 0.5
                right_excludes.append((_ocy - OVEN_WIN_CLEAR, _ocy + OVEN_WIN_CLEAR))

            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'RIGHT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                right_excludes.append((s_cy - sd_clr, s_cy + sd_clr))
            if (getattr(props, 'has_exterior_stairs', False)
                    and getattr(props, 'exterior_stairs_side', 'LEFT') == 'RIGHT'
                    and fl_idx in (0, 1)):
                _es_span = _ext_stairs_y_span(props, ctx)
                if _es_span is not None:
                    right_excludes.append(_es_span)
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('RIGHT'):
                    mw_cy = (y_min + y_max) * 0.5 + _off
                    right_excludes.append((mw_cy - (_mw_pw * 0.5 + win_w_clr), mw_cy + (_mw_pw * 0.5 + win_w_clr)))
            if _annex_side in ('RIGHT', 'BOTH') and fl_idx <= _annex_floors:
                right_excludes.append(_annex_y_span)
            # Doorway exclusions on Right facade (ALL floors)
            for d in ctx.floor_doorways.get(fl_idx, []):
                if d.get('axis') == 'Y' and abs(d.get('x', x_max) - x_max) < 0.8:
                    _dw = d.get('w', getattr(props, 'door_width', 1.0))
                    _dclr = (_dw + win_w) * 0.5 + (0.50 if props.has_shutters else 0.30)
                    right_excludes.append((d['y'] - _dclr, d['y'] + _dclr))

            if (fl_idx == 1 and getattr(props, 'has_side_rampart', False)
                    and getattr(props, 'rampart_side', 'RIGHT') == 'RIGHT'):
                _rc = (y_min + y_max) * 0.5
                _rclr = min(props.door_width, 1.30) * 0.5 + win_w * 0.5 + 0.35
                right_excludes.append((_rc - _rclr, _rc + _rclr))
            for b_ent in balconies_on_fl:
                if b_ent.get('side') == 'RIGHT':
                    b_cy = (y_min + y_max) * 0.5 + b_ent.get('offset', 0.0)
                    right_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            # Rectangular main building cargo dock / freight opening (Right)
            if fl_idx == 0 and effective_archetype in ('LUMBERMILL', 'WAREHOUSE') and not is_temporary_stockpile and not fl_has_wing and rec_cargo_side == 'RIGHT':
                _is_mill = (effective_archetype == 'LUMBERMILL')
                if _is_mill:
                    _cp_w = max(2.6, (y_max - y_min) - 1.2)
                    _cp_h = min(floor_h - 0.35, 3.0)
                    _dock_y1 = y_min + 0.5
                    _dock_y2 = y_max - 0.5
                else:
                    _cp_w = 2.6
                    _cp_h = min(2.8, floor_h - 0.35)
                    _dock_y1 = y_min + 0.4
                    _dock_y2 = y_max - 0.4
                _cp_cy = (y_min + y_max) * 0.5
                right_excludes.append((_cp_cy - _cp_w * 0.5 - 0.5, _cp_cy + _cp_w * 0.5 + 0.5))
                right_openings.append({'u_start': _cp_cy - _cp_w * 0.5 - y_min, 'u_end': _cp_cy + _cp_w * 0.5 - y_min, 'z_start': z_floor, 'z_end': z_floor + _cp_h})
                build_cargo_port_frame(bm, x_max, 1.0, _cp_cy, _cp_w, _cp_h, z_floor, wall_t, dock_y1=_dock_y1, dock_y2=_dock_y2)
            elif fl_idx == 1 and getattr(props, 'has_upper_cargo_crane', False) and rec_cargo_side == 'RIGHT':
                _cp_w = 2.0
                _cp_h = min(2.5, floor_h - 0.35)
                _cp_cy = (y_min + y_max) * 0.5
                right_excludes.append((_cp_cy - _cp_w * 0.5 - 0.5, _cp_cy + _cp_w * 0.5 + 0.5))
                right_openings.append({'u_start': _cp_cy - _cp_w * 0.5 - y_min, 'u_end': _cp_cy + _cp_w * 0.5 - y_min, 'z_start': z_floor, 'z_end': z_floor + _cp_h})
                from .accessories.crane import build_wall_jib_crane
                build_wall_jib_crane(bm, wall_x=x_max, wall_y=_cp_cy, z_mount=z_floor, outward_dir=(1.0, 0.0), jib_len=2.8)

            if props.has_windows and getattr(props, 'window_right', True):
                right_win_ys = []
                right_rooms = [rm for rm in fl_rooms if 'RIGHT' in rm.exterior_facades
                               and not getattr(rm, 'is_wing', False)
                               and (y_min - 0.05 <= rm.exterior_facades['RIGHT'][0] and rm.exterior_facades['RIGHT'][1] <= y_max + 0.05)]
                if right_rooms:
                    for rm in right_rooms:
                        ry0, ry1 = rm.exterior_facades['RIGHT']
                        rm_spans = carve_intervals([(ry0, ry1)], right_excludes, min_len=win_w + 0.35)
                        for s1, s2 in rm_spans:
                            span_l = s2 - s1
                            if span_l < 1.35:
                                continue
                            if span_l < 3.4:
                                right_win_ys.append((s1 + s2) * 0.5)
                            else:
                                right_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.9))
                else:
                    right_spans = carve_intervals([(y_min, y_max)], right_excludes, min_len=win_w + 0.35)
                    for s1, s2 in right_spans:
                        right_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))

                right_win_ys = [wy for wy in right_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in right_excludes)]

                for wy in right_win_ys:
                    wu = (wy - y_min)
                    right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                    window_centers.setdefault(fl_idx, {}).setdefault('RIGHT', []).append((x_max, wy, win_z1))
                    sh_act, sh_cl = get_shutter_info(x_max, wy, win_cz)
                    build_window_assembly(
                        bm, center=(x_max, wy, win_cz), size=(win_w, win_h),
                        wall_thickness=wall_t, normal_axis='+X',
                        has_shutters=sh_act, shutters_closed=sh_cl
                    )

        # Dynamic Windows - Wing Walls
        wing_wall_openings = [] # List of tuples: (w_elem, wall_face, openings, start_pt, end_pt, norm_vec)
        if fl_has_wing:
            for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                # Create opening lists for each of the 3 exposed faces
                w_ops_1, w_ops_2, w_ops_3 = [], [], []
                # Warehouse cargo port (enclosed ground floor only): open freight portal
                # on the courtyard side face (Face 2 = left, Face 3 = right) for crane
                # loading. Timber framing auto-avoids it via the openings list.
                # Never on open-air temporary stockpiles: there are no walls to
                # cut a portal into and no dock to build.
                cargo_port = None
                if (effective_archetype == 'WAREHOUSE' and not open_timber and fl_idx == 0
                        and w_wall in ('FRONT', 'BACK') and not is_temporary_stockpile):
                    _face = 2 if w_elem.get('align', 'RIGHT') == 'RIGHT' else 3
                    _pw = 2.3
                    _ph = min(getattr(props, 'door_height', 2.5), floor_h - 0.35)
                    _pc = wy1 + (wy2 - wy1) * 0.38
                    cargo_port = {'face': _face, 'cy': _pc, 'w': _pw, 'h': _ph}
                    (w_ops_2 if _face == 2 else w_ops_3).append({
                        'u_start': _pc - _pw * 0.5 - wy1,
                        'u_end': _pc + _pw * 0.5 - wy1,
                        'z_start': z_floor, 'z_end': z_floor + _ph})
                
                _is_u_tenement = (shape == 'U_SHAPE' and (
                    effective_archetype == 'TENEMENT' or
                    getattr(props, 'exterior_stairs_side', '') == 'COURTYARD' or
                    'TENEMENT' in getattr(props, 'building_family', '')
                ))
                _w_id = w_elem.get('id', 0)

                if w_wall == 'FRONT':
                    _w_margin_x = max(1.10, win_w * 0.5 + 0.65) if props.has_shutters else 1.0
                    _w_margin_y = max(1.10, win_w * 0.5 + 0.65) if props.has_shutters else 0.85
                    _part_clr = win_w * 0.5 + (0.50 if props.has_shutters else 0.30)
                    _w_part_ys = [iw['pos'] for iw in fl_interior_walls if iw.get('axis') == 'X' and (wy1 + 0.3 <= iw.get('pos', 0.0) <= wy2 - 0.3)]

                    # Face 1: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    if (props.has_windows and getattr(props, 'window_front', True) and not open_timber
                            and not (fl_idx == 0 and shape == 'T_SHAPE' and wing_placement == 'FRONT')):
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=_w_margin_x)
                        if _is_u_tenement and _w_id == 0 and fl_idx == 0:
                            # Ground floor left wing entrance is moved to this gable; exclude doorway area from windows
                            w_win_xs = [wwx for wwx in w_win_xs if abs(wwx - (wx1 + wx2) * 0.5) >= dw * 0.5 + 0.70]
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('FRONT', []).append((wwx, wy1, win_z1))

                    # Ground entrance for Left Wing of U-shaped tenement moved to the front gable (wy1)
                    if _is_u_tenement and _w_id == 0 and fl_idx == 0:
                        _cx_gable = (wx1 + wx2) * 0.5
                        _u_cg = _cx_gable - wx1
                        door_gf_stone = props.ground_floor_stone and tier_val != 'TIER_1'
                        steps_mat = MAT_INDEX_TIMBER if (tier_val == 'TIER_1' or getattr(props, 'foundation_type', 'STONE') == 'WOOD') else MAT_INDEX_CUT_STONE
                        w_ops_1.append({'u_start': _u_cg - dw * 0.5 - frame_margin, 'u_end': _u_cg + dw * 0.5 + frame_margin,
                                        'z_start': z_floor, 'z_end': door_top_z})
                        build_door_assembly(bm, center_x=_cx_gable, y_front=wy1, z_base=z_floor,
                                            wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                                            door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                                            normal_axis='-Y', include_leaf=getattr(props, 'include_door_leaves', True))
                        if props.has_front_steps and props.has_foundation:
                            build_front_steps(bm, center_x=_cx_gable, y_front=wy1, z_base=z_floor,
                                              num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y', mat_index=steps_mat)
                        ctx.floor_doorways.setdefault(0, []).append({'x': _cx_gable, 'y': wy1, 'axis': 'X', 'w': dw})

                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_2 = cargo_port is not None and cargo_port['face'] == 2
                    if (props.has_windows and getattr(props, 'window_left', True) and not open_timber
                            and not _port_here_2 and ((wy2 - 1.25) - (wy1 + _w_margin_y) >= win_w * 0.7)):
                        w_win_ys = get_facade_window_positions(wy1, wy2 - 1.25, target_spacing=eff_spacing, min_margin=_w_margin_y)
                        if _is_u_tenement and _w_id == 1:
                            _d_ex = [wy1 + max(1.3, (wy2 - wy1) * 0.26)]
                            w_win_ys = [wy for wy in w_win_ys if not any(abs(wy - dy) < dw * 0.5 + 0.70 for dy in _d_ex)]
                        if _w_part_ys:
                            w_win_ys = [wy for wy in w_win_ys if not any(abs(wy - py) < _part_clr for py in _w_part_ys)]
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('LEFT', []).append((wx1, wwy, win_z1))

                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_3 = cargo_port is not None and cargo_port['face'] == 3
                    if (props.has_windows and getattr(props, 'window_right', True) and not open_timber
                            and not _port_here_3 and ((wy2 - 1.25) - (wy1 + _w_margin_y) >= win_w * 0.7)):
                        w_win_ys = get_facade_window_positions(wy1, wy2 - 1.25, target_spacing=eff_spacing, min_margin=_w_margin_y)
                        if _is_u_tenement and _w_id == 0:
                            _d_ex = [wy1 + max(1.3, (wy2 - wy1) * 0.26)]
                            w_win_ys = [wy for wy in w_win_ys if not any(abs(wy - dy) < dw * 0.5 + 0.70 for dy in _d_ex)]
                        if _w_part_ys:
                            w_win_ys = [wy for wy in w_win_ys if not any(abs(wy - py) < _part_clr for py in _w_part_ys)]
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('RIGHT', []).append((wx2, wwy, win_z1))

                    # Courtyard apartment entrance doors for U-shaped tenements:
                    # Left wing ground door is on Face 1 (front gable). Right wing ground door is on Face 2 (-X).
                    if _is_u_tenement:
                        door_gf_stone = props.ground_floor_stone and tier_val != 'TIER_1'
                        steps_mat = MAT_INDEX_TIMBER if (tier_val == 'TIER_1' or getattr(props, 'foundation_type', 'STONE') == 'WOOD') else MAT_INDEX_CUT_STONE
                        if fl_idx == 0:
                            _dy = wy1 + max(1.3, (wy2 - wy1) * 0.26)
                            _u_c = _dy - wy1
                            # Note: Left Wing (_w_id == 0) ground door is on Face 1 (front gable) above!
                            if _w_id == 1:  # Right Wing courtyard door (Face 2)
                                w_ops_2.append({'u_start': _u_c - dw * 0.5 - frame_margin, 'u_end': _u_c + dw * 0.5 + frame_margin,
                                                'z_start': z_floor, 'z_end': door_top_z})
                                build_door_assembly(bm, center_x=wx1, y_front=_dy, z_base=z_floor,
                                                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                                                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=door_gf_stone,
                                                    normal_axis='-X', include_leaf=getattr(props, 'include_door_leaves', True))
                                if props.has_front_steps and props.has_foundation:
                                    build_front_steps(bm, center_x=wx1, y_front=_dy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-X', mat_index=steps_mat)
                                ctx.floor_doorways.setdefault(0, []).append({'x': wx1, 'y': _dy, 'axis': 'Y', 'w': dw})
                        elif fl_idx >= 1 and props.has_exterior_stairs:
                            dw_apt = min(1.10, float(getattr(props, 'door_width', 1.10)))
                            dh_apt = min(2.20, float(getattr(props, 'door_height', 2.20)))
                            _dy_up = wy1 + max(1.3, (wy2 - wy1) * 0.26)
                            _u_cup = _dy_up - wy1
                            if _w_id == 0:  # Left Wing upper gallery door (Face 3)
                                w_ops_3.append({'u_start': _u_cup - dw_apt * 0.5 - frame_margin, 'u_end': _u_cup + dw_apt * 0.5 + frame_margin,
                                                'z_start': z_floor, 'z_end': z_floor + dh_apt + frame_margin})
                                build_door_assembly(bm, center_x=wx2, y_front=_dy_up, z_base=z_floor,
                                                    wall_thickness=wall_t, door_w=dw_apt, door_h=dh_apt, door_angle_deg=props.door_angle,
                                                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                                                    normal_axis='+X', include_leaf=getattr(props, 'include_door_leaves', True))
                                ctx.floor_doorways.setdefault(fl_idx, []).append({'x': wx2, 'y': _dy_up, 'axis': 'Y', 'w': dw_apt})
                            elif _w_id == 1:  # Right Wing upper gallery door (Face 2)
                                w_ops_2.append({'u_start': _u_cup - dw_apt * 0.5 - frame_margin, 'u_end': _u_cup + dw_apt * 0.5 + frame_margin,
                                                'z_start': z_floor, 'z_end': z_floor + dh_apt + frame_margin})
                                build_door_assembly(bm, center_x=wx1, y_front=_dy_up, z_base=z_floor,
                                                    wall_thickness=wall_t, door_w=dw_apt, door_h=dh_apt, door_angle_deg=props.door_angle,
                                                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                                                    normal_axis='-X', include_leaf=getattr(props, 'include_door_leaves', True))
                                ctx.floor_doorways.setdefault(fl_idx, []).append({'x': wx1, 'y': _dy_up, 'axis': 'Y', 'w': dw_apt})

                    if w_elem.get('id', 0) == 0 and w_front_openings:
                        w_ops_1.extend(w_front_openings)

                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_1, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_2, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_3, (1.0, 0.0)))

                    if cargo_port is not None:
                        _fx = wx1 if cargo_port['face'] == 2 else wx2
                        _sgn = -1.0 if cargo_port['face'] == 2 else 1.0
                        build_cargo_port_frame(bm, _fx, _sgn, cargo_port['cy'],
                                               cargo_port['w'], cargo_port['h'],
                                               z_floor, wall_t,
                                               dock_y1=wy1 + 0.30, dock_y2=wy2 - 0.30)

                elif w_wall == 'BACK':
                    # Face 1: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    if props.has_windows and getattr(props, 'window_back', True) and not open_timber:
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('BACK', []).append((wwx, wy2, win_z1))
                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_2 = cargo_port is not None and cargo_port['face'] == 2
                    if (props.has_windows and getattr(props, 'window_left', True) and not open_timber
                            and not _port_here_2 and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7)):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('LEFT', []).append((wx1, wwy, win_z1))
                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_3 = cargo_port is not None and cargo_port['face'] == 3
                    if (props.has_windows and getattr(props, 'window_right', True) and not open_timber
                            and not _port_here_3 and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7)):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('RIGHT', []).append((wx2, wwy, win_z1))

                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_1, (0.0, 1.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_2, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_3, (1.0, 0.0)))

                    if cargo_port is not None:
                        _fx = wx1 if cargo_port['face'] == 2 else wx2
                        _sgn = -1.0 if cargo_port['face'] == 2 else 1.0
                        build_cargo_port_frame(bm, _fx, _sgn, cargo_port['cy'],
                                               cargo_port['w'], cargo_port['h'],
                                               z_floor, wall_t,
                                               dock_y1=wy1 + 0.30, dock_y2=wy2 - 0.30)

                elif w_wall == 'LEFT':
                    # Face 1: Left End (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    if props.has_windows and getattr(props, 'window_left', True) and not open_timber:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('LEFT', []).append((wx1, wwy, win_z1))
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if (props.has_windows and getattr(props, 'window_front', True) and not open_timber
                            and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7)):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('FRONT', []).append((wwx, wy1, win_z1))
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if (props.has_windows and getattr(props, 'window_back', True) and not open_timber
                            and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7)):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('BACK', []).append((wwx, wy2, win_z1))

                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_1, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

                elif w_wall == 'RIGHT':
                    # Face 1: Right End (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    if props.has_windows and getattr(props, 'window_right', True) and not open_timber:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('RIGHT', []).append((wx2, wwy, win_z1))
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if (props.has_windows and getattr(props, 'window_front', True) and not open_timber
                            and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7)):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('FRONT', []).append((wwx, wy1, win_z1))
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if (props.has_windows and getattr(props, 'window_back', True) and not open_timber
                            and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7)):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                            window_centers.setdefault(fl_idx, {}).setdefault('BACK', []).append((wwx, wy2, win_z1))

                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_1, (1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

        # 4 Main Solid Walls with Openings
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        eff_wall_mat = get_effective_wall_material(props)
        tier1_wattle = (eff_wall_mat == 'WATTLE_DAUB') or (tier_val == 'TIER_1' and is_tier1_wattle_daub(props))
        if eff_wall_mat == 'WATTLE_DAUB':
            mat_w = MAT_INDEX_PLASTER_EXT
            phys_siding = False
        elif eff_wall_mat == 'LOGS':
            mat_w = MAT_INDEX_WOOD
            phys_siding = True
        elif eff_wall_mat == 'WOOD_PLANKS':
            mat_w = MAT_INDEX_WOOD
            phys_siding = getattr(props, 'physical_siding', True)
        elif eff_wall_mat == 'STUCCO':
            mat_w = MAT_INDEX_PLASTER_EXT
            phys_siding = False
        elif eff_wall_mat == 'STONE':
            mat_w = MAT_INDEX_STONE
            phys_siding = False
        else: # AUTO
            tier1_wattle = (tier_val == 'TIER_1' and is_tier1_wattle_daub(props))
            if fl_idx == 0 and props.ground_floor_stone and tier_val != 'TIER_1':
                mat_w = MAT_INDEX_STONE
            elif tier1_wattle:
                mat_w = MAT_INDEX_PLASTER_EXT
            elif tier_val in ('TIER_1', 'TIER_2'):
                mat_w = MAT_INDEX_WOOD
            else:
                mat_w = MAT_INDEX_PLASTER_EXT

            phys_siding = getattr(props, 'physical_siding', True)
            if tier1_wattle:
                phys_siding = False
            elif fl_idx == 0 and props.ground_floor_stone and tier_val == 'TIER_2':
                phys_siding = False
        plank_dir = getattr(props, 'plank_direction', 'VERTICAL')
        plank_jank = getattr(props, 'plank_jankiness', 0.35)
        stone_scale = getattr(props, 'stone_block_scale', 1.0)
        stone_disorder = getattr(props, 'stone_disorder', 0.0)
        # Exposed brick patches only make sense on smooth stucco (Tier 3).
        # On wattle-and-daub or log walls the brick material reads as plain
        # white stucco strips (most visible on the narrow wall columns above
        # and below windows), so suppress it there.
        has_brick = getattr(props, 'has_exposed_brick', False) and not tier1_wattle
        brick_freq = getattr(props, 'exposed_brick_frequency', 0.25)

        # Interior joinery
        if not open_timber and not is_temporary_stockpile:
            build_interior_trims(
                bm, ix_min, ix_max, iy_min, iy_max, z_floor, z_ceil,
                wall_thickness=wall_t, stair_hole=cur_stair_hole,
                wall_openings={
                    'front': front_openings,
                    'back': back_openings,
                    'left': left_openings,
                    'right': right_openings,
                },
            )
            if fl_interior_walls:
                build_floor_interior_walls(
                    bm, fl_interior_walls, z_floor, z_ceil,
                    mat_index=MAT_INDEX_WOOD, casing_mat=MAT_INDEX_TIMBER,
                    plank_direction='VERTICAL'
                )

        wall_top_z = z_ceil

        if is_temporary_stockpile:
            pass  # Open-air temporary stockpile: no perimeter walls or arcade columns
        elif open_timber:
            arcade_segs = []
            if fl_has_wing:
                for p1, p2, w_ops, norm_v in wing_wall_openings:
                    arcade_segs.append((p1, p2))
                w_elem = wings[0]
                wx1, wx2, wy1, wy2 = fl_wings_bounds[0]
                if w_elem['wall'] == 'FRONT':
                    if wx1 > x_min + 0.4:
                        arcade_segs.append(((x_min, y_min), (wx1, y_min)))
                    if wx2 < x_max - 0.4:
                        arcade_segs.append(((wx2, y_min), (x_max, y_min)))
                    arcade_segs.append(((x_min, y_max), (x_max, y_max)))
                    arcade_segs.append(((x_min, y_min), (x_min, y_max)))
                    arcade_segs.append(((x_max, y_min), (x_max, y_max)))
                elif w_elem['wall'] == 'BACK':
                    arcade_segs.append(((x_min, y_min), (x_max, y_min)))
                    if wx1 > x_min + 0.4:
                        arcade_segs.append(((x_min, y_max), (wx1, y_max)))
                    if wx2 < x_max - 0.4:
                        arcade_segs.append(((wx2, y_max), (x_max, y_max)))
                    arcade_segs.append(((x_min, y_min), (x_min, y_max)))
                    arcade_segs.append(((x_max, y_min), (x_max, y_max)))
                elif w_elem['wall'] == 'LEFT':
                    arcade_segs.append(((x_min, y_min), (x_max, y_min)))
                    arcade_segs.append(((x_min, y_max), (x_max, y_max)))
                    if wy1 > y_min + 0.4:
                        arcade_segs.append(((x_min, y_min), (x_min, wy1)))
                    if wy2 < y_max - 0.4:
                        arcade_segs.append(((x_min, wy2), (x_min, y_max)))
                    arcade_segs.append(((x_max, y_min), (x_max, y_max)))
                elif w_elem['wall'] == 'RIGHT':
                    arcade_segs.append(((x_min, y_min), (x_max, y_min)))
                    arcade_segs.append(((x_min, y_max), (x_max, y_max)))
                    arcade_segs.append(((x_min, y_min), (x_min, y_max)))
                    if wy1 > y_min + 0.4:
                        arcade_segs.append(((x_max, y_min), (x_max, wy1)))
                    if wy2 < y_max - 0.4:
                        arcade_segs.append(((x_max, wy2), (x_max, y_max)))
            else:
                arcade_segs = [
                    ((x_min, y_min), (x_max, y_min)),
                    ((x_min, y_max), (x_max, y_max)),
                    ((x_min, y_min), (x_min, y_max)),
                    ((x_max, y_min), (x_max, y_max)),
                ]
            arcade_spacing = 5.2 if effective_archetype in ('LUMBERMILL', 'WAREHOUSE', 'QUARRY') else 3.8
            placed_posts = set()
            for p_start, p_end in arcade_segs:
                build_open_timber_arcade(
                    bm, p_start, p_end, z_floor, wall_top_z, wall_t,
                    has_foundation=props.has_foundation, found_h=found_h,
                    bay_spacing=arcade_spacing, placed_posts=placed_posts
                )
        else:
            # A Tier-1 log crown may only be dropped on the walls that sit under
            # an eave (which is where the roof deck overlaps). Gable-end walls
            # must keep their top log so the gable siding meets it with no gap.
            omit_crown = (tier_val == 'TIER_1' and phys_siding and num_floors > 1
                          and fl_idx == num_floors - 1)
            omit_front = omit_crown and is_rotated_roof
            omit_back = omit_crown and is_rotated_roof
            omit_left = omit_crown and not is_rotated_roof
            omit_right = omit_crown and not is_rotated_roof

            # When the floor above jetties outward, this wall's top partial log
            # would poke up through the upper floor and stand inside the room.
            # Drop it just like a crown; the soffit/core above closes the seam.
            jetty_next = False
            if fl_idx < num_floors - 1:
                _nb = _floor_xy_bounds(fl_idx + 1)
                jetty_next = (_nb[0] < x_min - 0.01 or _nb[1] > x_max + 0.01 or
                              _nb[2] < y_min - 0.01 or _nb[3] > y_max + 0.01)

            fr_front = [(wx1 - x_min, wx2 - x_min) for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds) if w_elem['wall'] == 'FRONT'] if fl_has_wing else None
            fr_back = [(wx1 - x_min, wx2 - x_min) for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds) if w_elem['wall'] == 'BACK'] if fl_has_wing else None
            fr_left = [(wy1 - y_min, wy2 - y_min) for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds) if w_elem['wall'] == 'LEFT'] if fl_has_wing else None
            fr_right = [(wy1 - y_min, wy2 - y_min) for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds) if w_elem['wall'] == 'RIGHT'] if fl_has_wing else None

            build_wall_with_opening(
                bm, (x_min, y_min), (x_max, y_min), z_floor, wall_top_z, wall_t, front_openings,
                mat_ext=mat_w, normal_vec=(0.0, -1.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_front or jetty_next,
                force_omit_top_log_row=jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq,
                flat_ranges=fr_front
            )
            build_wall_with_opening(
                bm, (x_min, y_max), (x_max, y_max), z_floor, wall_top_z, wall_t, back_openings,
                mat_ext=mat_w, normal_vec=(0.0, 1.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_back or jetty_next,
                force_omit_top_log_row=jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq,
                flat_ranges=fr_back
            )
            build_wall_with_opening(
                bm, (x_min, y_min), (x_min, y_max), z_floor, wall_top_z, wall_t, left_openings,
                mat_ext=mat_w, normal_vec=(-1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_left or jetty_next,
                force_omit_top_log_row=jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq,
                flat_ranges=fr_left
            )
            build_wall_with_opening(
                bm, (x_max, y_min), (x_max, y_max), z_floor, wall_top_z, wall_t, right_openings,
                mat_ext=mat_w, normal_vec=(1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_right or jetty_next,
                force_omit_top_log_row=jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq,
                flat_ranges=fr_right
            )
            
            # Wing Solid Walls.
            # Logs must NOT over-run at an end that dies into a main-hall wall,
            # otherwise their cut log ends poke through into the interior rooms.
            # NOTE: test against the main footprint, not mere plane alignment:
            # U-shaped side wings sit flush with the main facades, and a pure
            # plane test wrongly classified their outer corners as junctions,
            # killing the interleaved log ends there.
            if fl_has_wing:
                def _inside_main(pt):
                    return (x_min - 0.05 <= pt[0] <= x_max + 0.05 and
                            y_min - 0.05 <= pt[1] <= y_max + 0.05)
                for p1, p2, w_ops, norm_v in wing_wall_openings:
                    build_wall_with_opening(
                        bm, p1, p2, z_floor, wall_top_z, wall_t, w_ops,
                        mat_ext=mat_w, normal_vec=norm_v, tier=tier_val, physical_siding=phys_siding,
                        plank_direction=plank_dir, plank_jankiness=plank_jank,
                        stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                        is_corner_start=not _inside_main(p1),
                        is_corner_end=not _inside_main(p2),
                        has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
                    )

        # Timber Framing (Tudor Half-Timbering)
        # In Tier 1 (Log Cabin), authentic interlocking logs already provide all structural aesthetics.
        # Corner posts stay even on a stone ground storey so the frame reads as continuous;
        # only the infill/brace timbering is dropped there to keep the base solid masonry.
        _stone_ground_fl = (fl_idx == 0 and props.ground_floor_stone)
        _frame_here = (tier_val != 'TIER_1') or _stone_ground_fl or tier1_wattle
        if not open_timber and props.has_timber_framing and effective_archetype != 'WATCHTOWER' and _frame_here:
            post_w = 0.30
            timber_jank = props.wonkiness * 0.5
            is_top_fl = (fl_idx == num_floors - 1)

            # 1. Main building corner posts (chunky, flared at ends, subtly wonky)
            corners = [
                (x_min, y_min), (x_max, y_min),
                (x_min, y_max), (x_max, y_max)
            ]
            for cx, cy in corners:
                is_ground = (fl_idx == 0 and props.has_foundation)
                if is_ground:
                    ph = floor_h + found_h
                    pz = ph * 0.5
                else:
                    if is_top_fl:
                        ph = floor_h - 0.08
                        pz = z_floor + ph * 0.5 - 0.012
                    else:
                        ph = floor_h + 0.012
                        pz = z_floor + ph * 0.5 - 0.012
                b_cx = (x_min + x_max) * 0.5
                b_cy = (y_min + y_max) * 0.5
                dx = cx - b_cx
                dy = cy - b_cy
                dlen = math.sqrt(dx * dx + dy * dy)
                if dlen > 1e-4:
                    nx = dx / dlen
                    ny = dy / dlen
                else:
                    nx, ny = 0.0, 0.0
                off = wall_t * 0.46
                ocx = cx + nx * off
                ocy = cy + ny * off
                create_flared_post(
                    bm, size=(post_w, post_w, ph),
                    location=(ocx, ocy, pz),
                    mat_index=MAT_INDEX_TIMBER, flare=0.42, jankiness=timber_jank,
                    chamfer_top=is_top_fl
                )

            # 2. Main building exterior facades
            b_timber_ops = list(back_openings)
            l_timber_ops = list(left_openings)
            r_timber_ops = list(right_openings)
            f_timber_ops = list(front_openings)
            def _mw_mask_ops(ops_list, facade, span):
                for _off, _mw_pw in _mw_offs_for(facade):
                    _u_mid = span * 0.5 + _off
                    ops_list.append({
                        'u_start': _u_mid - _mw_pw * 0.5 - 0.05,
                        'u_end': _u_mid + _mw_pw * 0.5 + 0.05,
                        'z_start': z_floor,
                        'z_end': z_floor + floor_h
                    })

            if has_mw and _mw_spread.get(fl_idx):
                _mw_mask_ops(l_timber_ops, 'LEFT', (y_max - y_min))
                _mw_mask_ops(r_timber_ops, 'RIGHT', (y_max - y_min))
                _mw_mask_ops(b_timber_ops, 'BACK', (x_max - x_min))
                _mw_mask_ops(f_timber_ops, 'FRONT', (x_max - x_min))

            def build_exposed_wall_timber(p1, p2, norm_v, ops, occlusions):
                total_len = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                if total_len < 0.1:
                    return
                occ_sorted = sorted([(max(0.0, o[0]), min(total_len, o[1])) for o in occlusions if o[1] > 0 and o[0] < total_len])
                exp_intervals = []
                cur_u = 0.0
                for occ_s, occ_e in occ_sorted:
                    if occ_s > cur_u + 0.35:
                        exp_intervals.append((cur_u, occ_s))
                    cur_u = max(cur_u, occ_e)
                if total_len > cur_u + 0.35:
                    exp_intervals.append((cur_u, total_len))

                if not occlusions:
                    build_facade_timber(bm, p1, p2, z_floor, z_ceil, wall_t, norm_v, ops, props.timber_diagonals, is_top_floor=is_top_fl)
                    return

                ux = (p2[0] - p1[0]) / total_len
                uy = (p2[1] - p1[1]) / total_len
                for iu1, iu2 in exp_intervals:
                    sub_p1 = (p1[0] + ux * iu1, p1[1] + uy * iu1)
                    sub_p2 = (p1[0] + ux * iu2, p1[1] + uy * iu2)
                    sub_ops = []
                    for op in ops:
                        op_u1 = op.get('u_start', 0.0) - iu1
                        op_u2 = op.get('u_end', 0.0) - iu1
                        if op_u2 > 0 and op_u1 < (iu2 - iu1):
                            sub_ops.append({
                                'u_start': max(0.0, op_u1),
                                'u_end': min(iu2 - iu1, op_u2),
                                'z_start': op['z_start'],
                                'z_end': op['z_end']
                            })
                    build_facade_timber(bm, sub_p1, sub_p2, z_floor, z_ceil, wall_t, norm_v, sub_ops, props.timber_diagonals, is_top_floor=is_top_fl)

            # Compute attached wing occlusions for each wall
            f_occs, b_occs, l_occs, r_occs = [], [], [], []
            if fl_has_wing:
                for w_elem, (wx_min, wx_max, wy_min, wy_max) in zip(wings, fl_wings_bounds):
                    ww = w_elem['wall']
                    if ww == 'FRONT':
                        f_occs.append((wx_min - x_min, wx_max - x_min))
                    elif ww == 'BACK':
                        b_occs.append((wx_min - x_min, wx_max - x_min))
                    elif ww == 'LEFT':
                        l_occs.append((wy_min - y_min, wy_max - y_min))
                    elif ww == 'RIGHT':
                        r_occs.append((wy_min - y_min, wy_max - y_min))

            if not _stone_ground_fl:
                build_exposed_wall_timber((x_min, y_min), (x_max, y_min), (0.0, -1.0), f_timber_ops, f_occs)
                build_exposed_wall_timber((x_min, y_max), (x_max, y_max), (0.0, 1.0), b_timber_ops, b_occs)
                build_exposed_wall_timber((x_min, y_min), (x_min, y_max), (-1.0, 0.0), l_timber_ops, l_occs)
                build_exposed_wall_timber((x_max, y_min), (x_max, y_max), (1.0, 0.0), r_timber_ops, r_occs)

            # 3. Wing exterior facades and corner posts
            if fl_has_wing:
                for w_elem, (wx_min, wx_max, wy_min, wy_max) in zip(wings, fl_wings_bounds):
                    ww = w_elem['wall']
                    is_w_ground = (fl_idx == 0 and props.has_foundation)
                    if is_w_ground:
                        w_post_h = floor_h + found_h
                        w_post_cz = w_post_h * 0.5
                    else:
                        if is_top_fl:
                            w_post_h = floor_h - 0.08
                            w_post_cz = z_floor + w_post_h * 0.5 - 0.012
                        else:
                            w_post_h = floor_h + 0.012
                            w_post_cz = z_floor + w_post_h * 0.5 - 0.012

                    w_cx = (wx_min + wx_max) * 0.5
                    w_cy = (wy_min + wy_max) * 0.5

                    if ww == 'FRONT':
                        w_corners = [(wx_min, wy_min), (wx_max, wy_min)]
                    elif ww == 'BACK':
                        w_corners = [(wx_min, wy_max), (wx_max, wy_max)]
                    elif ww == 'LEFT':
                        w_corners = [(wx_min, wy_min), (wx_min, wy_max)]
                    else:
                        w_corners = [(wx_max, wy_min), (wx_max, wy_max)]

                    for wpx, wpy in w_corners:
                        dx_w = wpx - w_cx
                        dy_w = wpy - w_cy
                        dlen_w = math.sqrt(dx_w * dx_w + dy_w * dy_w)
                        if dlen_w > 1e-4:
                            nx_w = dx_w / dlen_w
                            ny_w = dy_w / dlen_w
                        else:
                            nx_w, ny_w = 0.0, -1.0
                        off_w = wall_t * 0.46
                        ocx_w = wpx + nx_w * off_w
                        ocy_w = wpy + ny_w * off_w
                        create_flared_post(bm, size=(post_w, post_w, w_post_h),
                                           location=(ocx_w, ocy_w, w_post_cz),
                                           mat_index=MAT_INDEX_TIMBER, flare=0.42, jankiness=timber_jank,
                                           chamfer_top=is_top_fl)

                if not _stone_ground_fl:
                    for p1, p2, w_ops, norm_v in wing_wall_openings:
                        build_facade_timber(bm, p1, p2, z_floor, z_ceil, wall_t,
                                            norm_v, w_ops, props.timber_diagonals, is_top_floor=is_top_fl)

        # Update previous floor tracking for overhang transitions
        prev_fl_overhang = fl_overhang
        prev_x_min, prev_x_max = x_min, x_max
        prev_y_min, prev_y_max = y_min, y_max

    ctx.floor_wall_bounds = floor_wall_bounds
    ctx.floor_stair_holes = floor_stair_holes
    ctx.floor_rooms = floor_rooms
    ctx.floor_interior_walls = floor_interior_walls
    ctx.window_centers = window_centers
    ctx.hx = hx
    ctx.hy = hy
    ctx.main_door_cx = main_door_cx
    ctx.main_door_yf = main_door_yf


def _segment_cross(p1, p2, axis, line):
    """Along-coordinate where segment p1->p2 crosses the line x=line (axis 'X')
    or y=line (axis 'Y'), or None when it does not reach it."""
    if axis == 'X':
        a, b = p1[0] - line, p2[0] - line
        if abs(a) < 1e-6 and abs(b) < 1e-6:
            return None
        if (a <= 0 <= b) or (b <= 0 <= a):
            t = 0.0 if abs(a - b) < 1e-9 else (0.0 - a) / (b - a)
            return p1[1] + (p2[1] - p1[1]) * t
        return None
    a, b = p1[1] - line, p2[1] - line
    if abs(a) < 1e-6 and abs(b) < 1e-6:
        return None
    if (a <= 0 <= b) or (b <= 0 <= a):
        t = 0.0 if abs(a - b) < 1e-9 else (0.0 - a) / (b - a)
        return p1[0] + (p2[0] - p1[0]) * t
    return None


def _nudge_along(a, blockers, lo, hi, clear=0.95, step=0.45, tries=14):
    """Slide a door position along the facade until it clears every blocker.

    Blockers are positions, or (position, clearance) pairs when an entry
    needs more room than ``clear`` (e.g. a wide wing portal next to a door).
    """
    items = [(b, clear) if not isinstance(b, tuple) else b for b in blockers]
    for _ in range(tries):
        hits = [(p, need) for p, need in items if abs(a - p) < need]
        if not hits:
            return a
        b, need = min(hits, key=lambda t: abs(a - t[0]))
        a += step if a >= b else -step
        a = min(max(a, lo + 0.75), hi - 0.75)
    return a


def _place_exterior_stair_doors(bm, props, ctx, fl_idx, z_floor,
                                x_min, x_max, y_min, y_max, wall_t,
                                ix_min, ix_max, iy_min, iy_max, interior_walls,
                                left_openings, right_openings,
                                front_openings, back_openings):
    """One exterior door per storey landing, nudged clear of interior walls."""
    if fl_idx < 0 or not getattr(props, 'has_exterior_stairs', False):
        return
    if getattr(props, 'open_timber_frame', False):
        return
    plan = _ext_stair_plan(props, ctx)
    if not plan:
        return

    if fl_idx == 0:
        if not plan.get('is_walkway'):
            return
        side = plan['wall']['name']
        xf = x_min if side == 'LEFT' else x_max
        ops = left_openings if side == 'LEFT' else right_openings
        edw = min(1.20, float(getattr(props, 'door_width', 1.20)))
        edh = min(2.40, float(getattr(props, 'door_height', 2.40)))
        margin = 0.12
        for spot in (_ext_stair_door_spots(props, ctx) or {}).get(0, []):
            along = spot['y'] if side in ('LEFT', 'RIGHT') else spot['x']
            ops.append({'u_start': (along - edw * 0.5 - margin) - y_min,
                        'u_end': (along + edw * 0.5 + margin) - y_min,
                        'z_start': z_floor, 'z_end': z_floor + edh + margin})
            ctx.floor_doorways.setdefault(0, []).append(
                {'x': xf, 'y': along, 'axis': 'Y', 'w': edw})
            build_door_assembly(
                bm, center_x=xf, y_front=along, z_base=z_floor,
                wall_thickness=wall_t, door_w=edw, door_h=edh,
                door_angle_deg=props.door_angle,
                door_shape=getattr(props, 'door_shape', 'AUTO'),
                ground_floor_stone=False,
                normal_axis=('-X' if side == 'LEFT' else '+X'),
                include_leaf=getattr(props, 'include_door_leaves', True))
            if getattr(props, 'has_front_steps', False) and getattr(props, 'has_foundation', False):
                steps_mat = MAT_INDEX_TIMBER if (
                    getattr(props, 'material_tier', 'TIER_3') == 'TIER_1'
                    or getattr(props, 'foundation_type', 'STONE') == 'WOOD'
                ) else MAT_INDEX_CUT_STONE
                build_front_steps(
                    bm, center_x=xf, y_front=along, z_base=z_floor,
                    num_steps=max(2, int(float(getattr(ctx, 'found_h', 0.4)) / 0.18)),
                    normal_axis=('-X' if side == 'LEFT' else '+X'), mat_index=steps_mat)
        return

    # Where interior partitions meet each facade, plus doors already on it
    # (street doors, wing portals, earlier landings): two doors must never
    # share one spot.
    def _blockers(facade):
        if facade in ('LEFT', 'RIGHT'):
            axis, line = 'X', (ix_min if facade == 'LEFT' else ix_max)
        else:
            axis, line = 'Y', (iy_min if facade == 'FRONT' else iy_max)
        out = []
        for w in interior_walls:
            p1, p2 = w.get('p1'), w.get('p2')
            if not p1 or not p2:
                continue
            c = _segment_cross(p1, p2, axis, line)
            if c is not None:
                out.append(c)
        for d in ctx.floor_doorways.get(fl_idx, []):
            dax = d.get('axis', 'X')
            if (facade in ('LEFT', 'RIGHT')) != (dax == 'Y'):
                continue
            if facade == 'LEFT' and abs(d.get('x', 0.0) - x_min) > 0.7:
                continue
            if facade == 'RIGHT' and abs(d.get('x', 0.0) - x_max) > 0.7:
                continue
            if facade == 'FRONT' and abs(d.get('y', 0.0) - y_min) > 0.7:
                continue
            if facade == 'BACK' and abs(d.get('y', 0.0) - y_max) > 0.7:
                continue
            c = d.get('y', 0.0) if facade in ('LEFT', 'RIGHT') else d.get('x', 0.0)
            out.append((c, edw * 0.5 + d.get('w', 1.2) * 0.5 + 0.30))
        return out

    edw = min(1.20, getattr(props, 'door_width', 1.20))
    edh = min(2.40, getattr(props, 'door_height', 2.40))
    e_margin = 0.12
    e_top_z = z_floor + edh + e_margin

    for spot in (_ext_stair_door_spots(props, ctx) or {}).get(fl_idx, []):
        sax = spot.get('axis', 'X')
        if sax == 'Y':
            facade = 'LEFT' if spot.get('x', 0.0) < 0.0 else 'RIGHT'
            xf = x_min if facade == 'LEFT' else x_max
            a = _nudge_along(spot['y'], _blockers(facade), y_min, y_max)
            ops = left_openings if facade == 'LEFT' else right_openings
            ops.append({'u_start': (a - edw * 0.5 - e_margin) - y_min,
                        'u_end': (a + edw * 0.5 + e_margin) - y_min,
                        'z_start': z_floor, 'z_end': e_top_z})
            ctx.floor_doorways.setdefault(fl_idx, []).append(
                {'x': xf, 'y': a, 'axis': 'Y', 'w': edw})
            build_door_assembly(
                bm, center_x=xf, y_front=a, z_base=z_floor,
                wall_thickness=wall_t, door_w=edw, door_h=edh,
                door_angle_deg=props.door_angle,
                door_shape=getattr(props, 'door_shape', 'AUTO'),
                ground_floor_stone=False,
                normal_axis=('-X' if facade == 'LEFT' else '+X'),
                include_leaf=getattr(props, 'include_door_leaves', True))
        else:
            facade = 'FRONT' if spot.get('y', 0.0) < 0.0 else 'BACK'
            a = _nudge_along(spot['x'], _blockers(facade), x_min, x_max)
            yf = y_max if facade == 'BACK' else y_min
            ops = back_openings if facade == 'BACK' else front_openings
            ops.append({'u_start': (a - edw * 0.5 - e_margin) - x_min,
                        'u_end': (a + edw * 0.5 + e_margin) - x_min,
                        'z_start': z_floor, 'z_end': e_top_z})
            ctx.floor_doorways.setdefault(fl_idx, []).append(
                {'x': a, 'y': yf, 'axis': 'X', 'w': edw})
            build_door_assembly(
                bm, center_x=a, y_front=yf, z_base=z_floor,
                wall_thickness=wall_t, door_w=edw, door_h=edh,
                door_angle_deg=props.door_angle,
                door_shape=getattr(props, 'door_shape', 'AUTO'),
                ground_floor_stone=False,
                normal_axis=('+Y' if facade == 'BACK' else '-Y'),
                include_leaf=getattr(props, 'include_door_leaves', True))

    for ed in getattr(props, 'extra_doorways', []):
        if ed.get('floor_idx', 0) != fl_idx:
            continue
        facade = ed.get('facade', 'RIGHT')
        dw_w = ed.get('w', 1.80)
        dw_h = ed.get('h', 2.60)
        pos = ed.get('pos', 0.0)
        top_z = z_floor + dw_h + e_margin
        is_portal = ed.get('is_portal', True)
        if facade in ('LEFT', 'RIGHT'):
            xf = x_min if facade == 'LEFT' else x_max
            ops = left_openings if facade == 'LEFT' else right_openings
            ops.append({'u_start': (pos - dw_w * 0.5 - e_margin) - y_min,
                        'u_end': (pos + dw_w * 0.5 + e_margin) - y_min,
                        'z_start': z_floor, 'z_end': top_z})
            ctx.floor_doorways.setdefault(fl_idx, []).append({'x': xf, 'y': pos, 'axis': 'Y', 'w': dw_w})
            build_door_assembly(
                bm, center_x=xf, y_front=pos, z_base=z_floor,
                wall_thickness=wall_t, door_w=dw_w, door_h=dw_h,
                door_angle_deg=props.door_angle,
                door_shape='ARCHED',
                ground_floor_stone=False,
                normal_axis=('-X' if facade == 'LEFT' else '+X'),
                include_leaf=not is_portal)
        else:
            yf = y_max if facade == 'BACK' else y_min
            ops = back_openings if facade == 'BACK' else front_openings
            ops.append({'u_start': (pos - dw_w * 0.5 - e_margin) - x_min,
                        'u_end': (pos + dw_w * 0.5 + e_margin) - x_min,
                        'z_start': z_floor, 'z_end': top_z})
            ctx.floor_doorways.setdefault(fl_idx, []).append({'x': pos, 'y': yf, 'axis': 'X', 'w': dw_w})
            build_door_assembly(
                bm, center_x=pos, y_front=yf, z_base=z_floor,
                wall_thickness=wall_t, door_w=dw_w, door_h=dw_h,
                door_angle_deg=props.door_angle,
                door_shape='ARCHED',
                ground_floor_stone=False,
                normal_axis=('+Y' if facade == 'BACK' else '-Y'),
                include_leaf=not is_portal)
