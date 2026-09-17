"""Per-floor construction phase.

Builds the foundation-to-eave shell for every storey: interior floor slabs,
staircases, ceiling beams, doors, windows, wing walls, timber framing, plus the
side-annex and corner-turret connections. Called once by the orchestrator with
the shared :class:`BuildingContext`.
"""

import math
from .mesh_utils import create_beveled_box, create_flared_post
from .materials import MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER, MAT_INDEX_FLOOR, MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME
from .walls import (
    build_wall_with_opening, build_facade_timber,
    build_cantilever_corbels, build_cantilever_soffit, build_open_timber_arcade
)
from .shapes import get_facade_window_positions, compute_fl_wing_bounds
from .interior import (
    build_floor_slab, build_ceiling_beams, build_interior_trims, build_straight_staircase,
    build_spiral_staircase, build_stair_guardrail
)
from .openings import build_door_assembly, build_front_steps, build_window_assembly
from .accessories.cargo_port import build_cargo_port_frame
from .accessories.mini_wing import plan_outcrop_spread


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

    # Ground floor master interior reference for staircase
    fl0_ix_min = -base_w * 0.5 + wall_t
    fl0_ix_max = base_w * 0.5 - wall_t
    fl0_iy_min = -base_d * 0.5 + wall_t
    fl0_iy_max = base_d * 0.5 - wall_t

    stair_w = props.stair_width
    landing_depth = 0.85
    stair_cx_0 = fl0_ix_min + 0.06 + stair_w * 0.5
    stair_cx_1 = stair_cx_0 + stair_w + 0.20

    stair_y_top = fl0_iy_max - landing_depth
    stair_len = min(2.4, max(1.8, (fl0_iy_max - fl0_iy_min) - landing_depth - 1.0))
    stair_y_bot = stair_y_top - stair_len

    prev_fl_overhang = 0.0
    prev_x_min, prev_x_max = -base_w * 0.5, base_w * 0.5
    prev_y_min, prev_y_max = -base_d * 0.5, base_d * 0.5

    # Track stair holes and wall bounds per floor
    floor_stair_holes = {}
    floor_wall_bounds = {}

    # Town-Hall side annex: it hugs the main side wall (opposite the clock tower)
    # for its whole height. Windows on the main wall behind it are interior and
    # must be suppressed, and its portal opens on every floor it spans so the
    # upper storey is reachable from inside the hall.
    _annex_on = (getattr(props, 'town_hall_composer', False)
                 and getattr(props, 'has_side_annex', False) and shape == 'T_SHAPE')
    _annex_floors = 0
    _annex_side = None
    _annex_y_span = None
    if _annex_on:
        _annex_side = 'LEFT' if getattr(props, 'clock_tower_side', 'RIGHT') == 'RIGHT' else 'RIGHT'
        _annex_floors = max(1, min(2, getattr(props, 'annex_floors', 2)))
        _a_w = 5.2 if getattr(props, 'material_tier', 'TIER_3') != 'TIER_1' else 4.4
        _annex_y_span = (-_a_w * 0.5 - 0.5, _a_w * 0.5 + 0.5)

    # Square corner turrets bolt onto the outside of the BACK wall, so each one
    # connects through a doorway cut in the back wall (clear of the stairs).
    _turrets = []
    if getattr(props, 'has_corner_turrets', False) and not open_timber:
        _thalf = max(1.0, min(2.0, getattr(props, 'corner_turret_size', 1.35)))
        _t_cx = base_w * 0.5 - _thalf
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
            if _annex_side == 'LEFT' and _annex_floors > 0:
                cor_l = False
            elif _annex_side == 'RIGHT' and _annex_floors > 0:
                cor_r = False
            build_cantilever_corbels(bm, x_min, x_max, y_min, y_max, z_floor,
                                    overhang_dist=overhang_step, front_exclude_x=front_ex,
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

        # Floor Slab (Ground floor is stone/timber; upper floors have stair cutout)
        floor_mat = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_FLOOR
        build_floor_slab(
            bm,
            floor_idx=fl_idx,
            x_min=slab_xmin, x_max=slab_xmax,
            y_min=slab_ymin, y_max=slab_ymax,
            z_level=z_floor + 0.05,
            thickness=0.12,
            stair_hole=cur_stair_hole if (fl_idx > 0 and props.has_stairs) else None,
            mat_idx=floor_mat
        )
        
        # Upper floor safety guardrail around stair opening
        if fl_idx > 0 and props.has_stairs and cur_stair_hole is not None:
            sh_x1, sh_x2, sh_y1, sh_y2 = cur_stair_hole
            rail_x = min(slab_xmax - 0.10, sh_x2 + 0.05)
            if props.stair_style == 'SPIRAL':
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=sh_y1, x_start=sh_x1 + 0.20)
            else:
                # Straight stairs: only guard open void on the top floor where no more stairs ascend
                # On intermediate floors, the ascending flight's own handrail protects the opening
                if fl_idx == num_floors - 1:
                    ret_y = sh_y1 if (fl_idx % 2 == 1) else sh_y2
                    # Guardrail along the right side and across the void edge
                    build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                          return_y=ret_y, x_start=sh_x1)
                    # If there is walkable floor to the left of the stair opening (e.g. over lower flight),
                    # protect that open edge with a matching left guardrail
                    if sh_x1 > ix_min + 0.35:
                        build_stair_guardrail(bm, sh_x1, sh_y1, sh_y2, z_floor + 0.05)
        
        # Wing floor slabs for compound shapes
        if fl_has_wing:
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

                build_floor_slab(
                    bm,
                    floor_idx=fl_idx,
                    x_min=w_slab_xmin, x_max=w_slab_xmax,
                    y_min=w_slab_ymin, y_max=w_slab_ymax,
                    z_level=z_floor + 0.05,
                    thickness=0.12,
                    stair_hole=None,
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
                    build_cantilever_corbels(bm, w_xmin, w_xmax, w_ymin, w_ymax, z_floor,
                                            overhang_dist=overhang_step,
                                            include_back=(w_wall != 'FRONT') and inc_b,
                                            include_front=(w_wall != 'BACK') and inc_f,
                                            include_left=(w_wall != 'RIGHT') and inc_l,
                                            include_right=(w_wall != 'LEFT') and inc_r)

        # Determine next flight of stairs leading up to fl_idx + 1
        next_stair_hole = None
        if fl_idx < num_floors - 1 and props.has_stairs:
            if props.stair_style == 'SPIRAL':
                spiral_r = min(1.15, props.stair_width * 1.05)
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
                # Straight stairs: Floor 0 -> 1 runs front to back (+Y) on track 0
                # Floor 1 -> 2 runs back to front (-Y) on adjacent track 1 (switchback)
                if fl_idx % 2 == 0:
                    stair_start = (stair_cx_0, stair_y_bot, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=1)
                    # Opening on upper floor only spans this active track, leaving any overhang and adjacent track as solid floor
                    next_stair_hole = (stair_cx_0 - stair_w * 0.5 - 0.08, stair_cx_0 + stair_w * 0.5 + 0.12,
                                       stair_y_bot - 0.15, stair_y_top + 0.05)
                else:
                    stair_start = (stair_cx_1, stair_y_top, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=-1)
                    # Opening on upper floor only spans this active track, leaving adjacent track as solid floor
                    next_stair_hole = (stair_cx_1 - stair_w * 0.5 - 0.08, stair_cx_1 + stair_w * 0.5 + 0.12,
                                       stair_y_bot - 0.05, stair_y_top + 0.15)
            
            floor_stair_holes[fl_idx + 1] = next_stair_hole

        # Ceiling Beams (underneath next floor, trimmed around stairs)
        if props.has_ceiling_beams:
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
        for _tr in _turrets:
            _tcx = _tr['cx']
            _pw = 1.30
            _ph = min(2.15, floor_h * 0.78)
            _pm = 0.12
            _pz1 = z_floor + _ph
            back_openings.append({'u_start': (_tcx - _pw * 0.5 - _pm) - x_min,
                                  'u_end': (_tcx + _pw * 0.5 + _pm) - x_min,
                                  'z_start': z_floor, 'z_end': _pz1})
            _jw, _jd = 0.16, wall_t + 0.10
            for _s in (-1.0, 1.0):
                create_beveled_box(bm, size=(_jw, _jd, _ph + _pm),
                                   location=(_tcx + _s * (_pw * 0.5 + _jw * 0.5), y_max,
                                             z_floor + (_ph + _pm) * 0.5),
                                   mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
            create_beveled_box(bm, size=(_pw + _jw * 2.0, _jd, _pm),
                               location=(_tcx, y_max, _pz1 + _pm * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)

        win_w = props.window_width
        win_h = props.window_height
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val == 'TIER_1':
            # For authentic log cabins: window fits cleanly across 3 sawed-off logs
            # Row 1 (sill log) top is at 2.0 * log_diam (0.72)
            # Row 5 (lintel log) bottom is at 5.0 * log_diam (1.80)
            # Opening cutout height = 1.08m
            log_diam = 0.36
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
            dw = props.door_width
            dh = props.door_height
            if tier_val == 'TIER_1':
                log_diam = 0.36
                dh = 2.02
                door_top_z = z_floor + 6.0 * log_diam
                frame_margin = 0.08
            else:
                frame_margin = 0.12
                door_top_z = z_floor + dh + frame_margin

            # 1. Front Entrance
            if props.has_front_door and not open_timber:
                if shape == 'RECTANGLE':
                    door_cx = 0.0
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
                    door_cx = 0.0 # Center of front courtyard
                    door_yf = y_min
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

                build_door_assembly(
                    bm, center_x=door_cx, y_front=door_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                    normal_axis='-Y'
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=door_cx, y_front=door_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y')

            # 2. Rear / Back Door
            if getattr(props, 'has_back_door', False) and not open_timber:
                b_cx = 0.0
                if shape == 'L_SHAPE' and wing_placement == 'BACK':
                    b_cx = (x_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + x_max) * 0.5
                b_yf = y_max
                b_u1 = (b_cx - dw * 0.5 - frame_margin) - x_min
                b_u2 = (b_cx + dw * 0.5 + frame_margin) - x_min
                back_openings.append({'u_start': b_u1, 'u_end': b_u2, 'z_start': z_floor, 'z_end': door_top_z})

                build_door_assembly(
                    bm, center_x=b_cx, y_front=b_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                    normal_axis='+Y'
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=b_cx, y_front=b_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+Y')

            # 3. Side Door
            if getattr(props, 'has_side_door', False) and not open_timber:
                s_facade = getattr(props, 'side_door_facade', 'LEFT')
                if s_facade == 'LEFT':
                    s_cy = (y_min + stair_y_bot) * 0.5 if (props.has_stairs and (stair_y_bot - y_min) > 2.0) else (y_min + y_max) * 0.5
                    s_xf = x_min
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    left_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                        normal_axis='-X'
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-X')
                else: # RIGHT
                    s_cy = (y_min + y_max) * 0.5
                    s_xf = x_max
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    right_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                        normal_axis='+X'
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+X')

        # Upper side door onto the side rampart deck (Tier 3 town halls)
        if fl_idx == 1 and getattr(props, 'has_side_rampart', False) and not open_timber:
            r_side = getattr(props, 'rampart_side', 'RIGHT')
            rdw = min(props.door_width, 1.30)
            rdh = min(props.door_height, 2.30)
            r_margin = 0.12
            r_top_z = z_floor + rdh + r_margin
            if r_side == 'LEFT':
                r_cy = (y_min + y_max) * 0.5
                left_openings.append({'u_start': (r_cy - rdw * 0.5 - r_margin) - y_min,
                                      'u_end': (r_cy + rdw * 0.5 + r_margin) - y_min,
                                      'z_start': z_floor, 'z_end': r_top_z})
                build_door_assembly(
                    bm, center_x=x_min, y_front=r_cy, z_base=z_floor,
                    wall_thickness=wall_t, door_w=rdw, door_h=rdh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                    normal_axis='-X'
                )
            else:
                r_cy = (y_min + y_max) * 0.5
                right_openings.append({'u_start': (r_cy - rdw * 0.5 - r_margin) - y_min,
                                       'u_end': (r_cy + rdw * 0.5 + r_margin) - y_min,
                                       'z_start': z_floor, 'z_end': r_top_z})
                build_door_assembly(
                    bm, center_x=x_max, y_front=r_cy, z_base=z_floor,
                    wall_thickness=wall_t, door_w=rdw, door_h=rdh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=False,
                    normal_axis='+X'
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
            if _annex_side == 'LEFT':
                left_openings.append({'u_start': (_ap_cy - _ap_w * 0.5 - _ap_m) - y_min,
                                      'u_end': (_ap_cy + _ap_w * 0.5 + _ap_m) - y_min,
                                      'z_start': z_floor, 'z_end': _ap_top})
                _ap_fx = x_min
            else:
                right_openings.append({'u_start': (_ap_cy - _ap_w * 0.5 - _ap_m) - y_min,
                                       'u_end': (_ap_cy + _ap_w * 0.5 + _ap_m) - y_min,
                                       'z_start': z_floor, 'z_end': _ap_top})
                _ap_fx = x_max
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
        if fl_has_wing and not open_timber:
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
                    # Cutout in the wall encompasses the whole frame opening + jambs so plaster never z-fights with wood
                    p_u1 = (p_cx - p_w * 0.5 - jamb_w - 0.02) - x_min
                    p_u2 = (p_cx + p_w * 0.5 + jamb_w + 0.02) - x_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h + 0.02}
                    if w_wall == 'FRONT':
                        front_openings.append(op_dict)
                    else:
                        back_openings.append(op_dict)

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
                    # Cutout in the wall encompasses the whole frame opening + jambs so plaster never z-fights with wood
                    p_u1 = (p_cy - p_w * 0.5 - jamb_w - 0.02) - y_min
                    p_u2 = (p_cy + p_w * 0.5 + jamb_w + 0.02) - y_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h + 0.02}
                    if w_wall == 'LEFT':
                        left_openings.append(op_dict)
                    else:
                        right_openings.append(op_dict)

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
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                       location=(_wc_x, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, z_floor + mw_portal_h * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                    create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                       location=(_wc_x, p_cy, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

        # Balcony Doorway Cutout (per-floor facade resolved above)
        b_side = floor_balc_side.get(fl_idx)
        b_side_next = floor_balc_side.get(fl_idx + 1)
        b_width = getattr(props, 'balcony_width', 2.4)

        if b_side is not None:
            balc_door_w = 0.95
            balc_door_h = min(2.15, floor_h * 0.76)
            if b_side in ('FRONT', 'BACK'):
                b_u_mid = (x_max - x_min) * 0.5
            else:
                b_u_mid = (y_max - y_min) * 0.5
            
            b_op = {
                'u_start': b_u_mid - balc_door_w * 0.5,
                'u_end': b_u_mid + balc_door_w * 0.5,
                'z_start': z_floor,
                'z_end': z_floor + balc_door_h
            }
            if b_side == 'FRONT':
                front_openings.append(b_op)
            elif b_side == 'BACK':
                back_openings.append(b_op)
            elif b_side == 'LEFT':
                left_openings.append(b_op)
            elif b_side == 'RIGHT':
                right_openings.append(b_op)

        # Dynamic Windows - Facade Openings & Shutters
        # Dynamic Windows - Facade Openings & Shutters
        eff_spacing = max(1.0, props.window_spacing / max(0.2, getattr(props, 'window_density', 1.0)))
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

        # Dynamic Windows - Front Wall
        if props.has_windows and not open_timber:
            front_excludes = list(get_facade_wing_exclusions('FRONT')) + get_turret_exclusions('FRONT')
            balcony_overhead = (b_side_next == 'FRONT')
            
            # Door exclusion zone calculation on floor 0
            if fl_idx == 0 and props.has_front_door:
                door_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                d_ex1 = door_cx - door_clr
                d_ex2 = door_cx + door_clr
                front_excludes.append((d_ex1, d_ex2))
                
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('FRONT'):
                    mw_cx = (x_min + x_max) * 0.5 + _off
                    front_excludes.append((mw_cx - (_mw_pw * 0.5 + win_w_clr), mw_cx + (_mw_pw * 0.5 + win_w_clr)))
                
            if b_side == 'FRONT':
                b_cx = (x_min + x_max) * 0.5
                front_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))
            elif b_side_next == 'FRONT':
                b_cx = (x_min + x_max) * 0.5
                front_excludes.append((b_cx - (b_width * 0.5 + 0.45), b_cx + (b_width * 0.5 + 0.45)))

            front_spans = carve_intervals([(x_min, x_max)], front_excludes, min_len=win_w + 0.35)
            front_win_xs = []
            for s1, s2 in front_spans:
                if fl_idx == 0 and props.has_stairs and cur_w < 6.0 and s2 <= 0.0:
                    continue
                front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))

            # Strict safety filter
            front_win_xs = [wx for wx in front_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in front_excludes)]

            for wx in front_win_xs:
                wu = (wx - x_min)
                front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(wx, y_min, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_min, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-Y',
                    has_shutters=sh_act, shutters_closed=sh_cl
                )

        # Dynamic Windows - Back Wall
        if props.has_windows and not open_timber:
            back_excludes = list(get_facade_wing_exclusions('BACK')) + get_turret_exclusions('BACK')
            if fl_idx == 0 and getattr(props, 'has_back_door', False):
                bd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                bd_ex1 = b_cx - bd_clr
                bd_ex2 = b_cx + bd_clr
                back_excludes.append((bd_ex1, bd_ex2))
                
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('BACK'):
                    mw_cx = (x_min + x_max) * 0.5 + _off
                    back_excludes.append((mw_cx - (_mw_pw * 0.5 + win_w_clr), mw_cx + (_mw_pw * 0.5 + win_w_clr)))
                
            if b_side == 'BACK':
                b_cx = (x_min + x_max) * 0.5
                back_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))

            back_spans = carve_intervals([(x_min, x_max)], back_excludes, min_len=win_w + 0.35)
            back_win_xs = []
            for s1, s2 in back_spans:
                back_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))
            back_win_xs = [wx for wx in back_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in back_excludes)]

            for wx in back_win_xs:
                wu = (wx - x_min)
                back_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(wx, y_max, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_max, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+Y',
                    has_shutters=sh_act, shutters_closed=sh_cl
                )

        # Dynamic Windows - Side Walls (Left and Right)
        if props.has_windows and not open_timber and cur_d > 2.8:
            # Left side
            left_excludes = list(get_facade_wing_exclusions('LEFT')) + get_turret_exclusions('LEFT')
            if fl_idx == 0 and props.has_stairs:
                left_excludes.append((stair_y_bot - 0.25, stair_y_top + 0.25))
            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'LEFT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                left_excludes.append((s_cy - sd_clr, s_cy + sd_clr))
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('LEFT'):
                    mw_cy = (y_min + y_max) * 0.5 + _off
                    left_excludes.append((mw_cy - (_mw_pw * 0.5 + win_w_clr), mw_cy + (_mw_pw * 0.5 + win_w_clr)))
            if _annex_side == 'LEFT' and fl_idx <= _annex_floors:
                left_excludes.append(_annex_y_span)
            if (fl_idx == 1 and getattr(props, 'has_side_rampart', False)
                    and getattr(props, 'rampart_side', 'RIGHT') == 'LEFT'):
                _rc = (y_min + y_max) * 0.5
                _rclr = min(props.door_width, 1.30) * 0.5 + win_w * 0.5 + 0.35
                left_excludes.append((_rc - _rclr, _rc + _rclr))
            if b_side == 'LEFT':
                b_cy = (y_min + y_max) * 0.5
                left_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            left_spans = carve_intervals([(y_min, y_max)], left_excludes, min_len=win_w + 0.35)
            left_win_ys = []
            for s1, s2 in left_spans:
                left_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))
            left_win_ys = [wy for wy in left_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in left_excludes)]

            for wy in left_win_ys:
                wu = (wy - y_min)
                left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(x_min, wy, win_cz)
                build_window_assembly(
                    bm, center=(x_min, wy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-X',
                    has_shutters=sh_act, shutters_closed=sh_cl
                )

            # Right side
            right_excludes = list(get_facade_wing_exclusions('RIGHT')) + get_turret_exclusions('RIGHT')
            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'RIGHT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                right_excludes.append((s_cy - sd_clr, s_cy + sd_clr))
            if has_mw:
                for _off, _mw_pw in _mw_offs_for('RIGHT'):
                    mw_cy = (y_min + y_max) * 0.5 + _off
                    right_excludes.append((mw_cy - (_mw_pw * 0.5 + win_w_clr), mw_cy + (_mw_pw * 0.5 + win_w_clr)))
            if _annex_side == 'RIGHT' and fl_idx <= _annex_floors:
                right_excludes.append(_annex_y_span)
            if (fl_idx == 1 and getattr(props, 'has_side_rampart', False)
                    and getattr(props, 'rampart_side', 'RIGHT') == 'RIGHT'):
                _rc = (y_min + y_max) * 0.5
                _rclr = min(props.door_width, 1.30) * 0.5 + win_w * 0.5 + 0.35
                right_excludes.append((_rc - _rclr, _rc + _rclr))
            if b_side == 'RIGHT':
                b_cy = (y_min + y_max) * 0.5
                right_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            right_spans = carve_intervals([(y_min, y_max)], right_excludes, min_len=win_w + 0.35)
            right_win_ys = []
            for s1, s2 in right_spans:
                right_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=1.0))
            right_win_ys = [wy for wy in right_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in right_excludes)]

            for wy in right_win_ys:
                wu = (wy - y_min)
                right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
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
                cargo_port = None
                if (effective_archetype == 'WAREHOUSE' and not open_timber and fl_idx == 0
                        and w_wall in ('FRONT', 'BACK')):
                    _face = 2 if w_elem.get('align', 'RIGHT') == 'RIGHT' else 3
                    _pw = 2.3
                    _ph = min(getattr(props, 'door_height', 2.5), floor_h - 0.35)
                    _pc = wy1 + (wy2 - wy1) * 0.38
                    cargo_port = {'face': _face, 'cy': _pc, 'w': _pw, 'h': _ph}
                    (w_ops_2 if _face == 2 else w_ops_3).append({
                        'u_start': _pc - _pw * 0.5 - wy1,
                        'u_end': _pc + _pw * 0.5 - wy1,
                        'z_start': z_floor, 'z_end': z_floor + _ph})
                
                if w_wall == 'FRONT':
                    # Face 1: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    if props.has_windows and not open_timber and not (fl_idx == 0 and shape == 'T_SHAPE' and wing_placement == 'FRONT'):
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_2 = cargo_port is not None and cargo_port['face'] == 2
                    if props.has_windows and not open_timber and not _port_here_2 and ((wy2 - 1.25) - (wy1 + 0.85) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 0.85, wy2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_3 = cargo_port is not None and cargo_port['face'] == 3
                    if props.has_windows and not open_timber and not _port_here_3 and ((wy2 - 1.25) - (wy1 + 0.85) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 0.85, wy2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)

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
                    if props.has_windows and not open_timber:
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_2 = cargo_port is not None and cargo_port['face'] == 2
                    if props.has_windows and not open_timber and not _port_here_2 and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    # (skipped when the cargo port occupies this face)
                    _port_here_3 = cargo_port is not None and cargo_port['face'] == 3
                    if props.has_windows and not open_timber and not _port_here_3 and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)

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
                    if props.has_windows and not open_timber:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if props.has_windows and not open_timber and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if props.has_windows and not open_timber and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)

                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_1, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

                elif w_wall == 'RIGHT':
                    # Face 1: Right End (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    if props.has_windows and not open_timber:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=1.0)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if props.has_windows and not open_timber and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if props.has_windows and not open_timber and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.85)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl)

                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_1, (1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

        # 4 Main Solid Walls with Openings
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val in ('TIER_1', 'TIER_2'):
            mat_w = MAT_INDEX_WOOD
        else:
            mat_w = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_PLASTER_EXT

        phys_siding = getattr(props, 'physical_siding', True)
        plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')
        plank_jank = getattr(props, 'plank_jankiness', 0.35)
        stone_scale = getattr(props, 'stone_block_scale', 1.0)
        stone_disorder = getattr(props, 'stone_disorder', 0.35)
        has_brick = getattr(props, 'has_exposed_brick', True)
        brick_freq = getattr(props, 'exposed_brick_frequency', 0.25)

        # Interior joinery
        if not open_timber:
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

        wall_top_z = z_ceil

        if open_timber:
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
            for p_start, p_end in arcade_segs:
                build_open_timber_arcade(
                    bm, p_start, p_end, z_floor, wall_top_z, wall_t,
                    has_foundation=props.has_foundation, found_h=found_h
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

            build_wall_with_opening(
                bm, (x_min, y_min), (x_max, y_min), z_floor, wall_top_z, wall_t, front_openings,
                mat_ext=mat_w, normal_vec=(0.0, -1.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_front or jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
            )
            build_wall_with_opening(
                bm, (x_min, y_max), (x_max, y_max), z_floor, wall_top_z, wall_t, back_openings,
                mat_ext=mat_w, normal_vec=(0.0, 1.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_back or jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
            )
            build_wall_with_opening(
                bm, (x_min, y_min), (x_min, y_max), z_floor, wall_top_z, wall_t, left_openings,
                mat_ext=mat_w, normal_vec=(-1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_left or jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
            )
            build_wall_with_opening(
                bm, (x_max, y_min), (x_max, y_max), z_floor, wall_top_z, wall_t, right_openings,
                mat_ext=mat_w, normal_vec=(1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                omit_top_log_row=omit_right or jetty_next,
                has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
            )
            
            # Wing Solid Walls.
            # Logs must NOT over-run at an end that dies into a main-hall wall,
            # otherwise their cut log ends poke through into the interior rooms.
            if fl_has_wing:
                def _on_main_plane(pt):
                    return (abs(pt[0] - x_min) < 0.03 or abs(pt[0] - x_max) < 0.03 or
                            abs(pt[1] - y_min) < 0.03 or abs(pt[1] - y_max) < 0.03)
                for p1, p2, w_ops, norm_v in wing_wall_openings:
                    build_wall_with_opening(
                        bm, p1, p2, z_floor, wall_top_z, wall_t, w_ops,
                        mat_ext=mat_w, normal_vec=norm_v, tier=tier_val, physical_siding=phys_siding,
                        plank_direction=plank_dir, plank_jankiness=plank_jank,
                        stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                        is_corner_start=not _on_main_plane(p1),
                        is_corner_end=not _on_main_plane(p2),
                        has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
                    )

        # Timber Framing (Tudor Half-Timbering)
        # In Tier 1 (Log Cabin), authentic interlocking logs already provide all structural aesthetics
        if not open_timber and props.has_timber_framing and effective_archetype != 'WATCHTOWER' and tier_val != 'TIER_1':
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

                for p1, p2, w_ops, norm_v in wing_wall_openings:
                    build_facade_timber(bm, p1, p2, z_floor, z_ceil, wall_t,
                                        norm_v, w_ops, props.timber_diagonals, is_top_floor=is_top_fl)

        # Update previous floor tracking for overhang transitions
        prev_fl_overhang = fl_overhang
        prev_x_min, prev_x_max = x_min, x_max
        prev_y_min, prev_y_max = y_min, y_max

    ctx.floor_wall_bounds = floor_wall_bounds
    ctx.floor_stair_holes = floor_stair_holes
    ctx.hx = hx
    ctx.hy = hy
    ctx.main_door_cx = main_door_cx
    ctx.main_door_yf = main_door_yf
