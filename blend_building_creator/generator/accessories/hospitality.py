"""
Hospitality front-of-house composer.

Arranges the generic props (veranda, signage, furniture, lighting, garden) into
a tavern or inn scene. This module holds only the *composition* knowledge - how
much decor a tier gets and where it goes - while all geometry lives in the
reusable prop modules it imports.
"""

import math

from .tavern import build_tavern_porch
from .signage import build_hanging_sign, build_notice_board, build_awning
from .furniture import (
    build_barrel, build_crate, build_sack, build_stool, build_bench,
    build_picnic_table,
)
from .lighting import build_post_lantern, build_hanging_lantern
from .garden import build_flower_box, build_well


def _prop(props, name, default):
    return getattr(props, name, default)


def _is_log_floor(props, ctx, tier, floor):
    """True when this storey is built from bulging logs (vs flush stone/planks).

    A stone ground storey stays thin even on a Tier-1 building, so wall props on
    the ground floor must not be pushed out to the log crest.
    """
    if floor <= 0 and bool(getattr(props, 'ground_floor_stone', False)):
        return False
    return (getattr(props, 'building_material', 'LOG') == 'LOG' or
            getattr(props, 'material_tier', 'TIER_1') == 'TIER_1' or
            (ctx.effective_archetype in ('TAVERN', 'INN') and tier == 'TIER_1'))


def _wall_out(props, ctx, tier, floor=0):
    """Distance from the wall CENTRELINE to its visible outer skin on a storey.

    Log walls bulge well past the wall line, so wall-mounted props must be pushed
    out to roughly the log crest or their back plates float off the wall. Smooth
    stone/plank/plaster walls only need the half wall thickness plus a hair.
    """
    return ctx.wall_t * 0.5 + (0.12 if _is_log_floor(props, ctx, tier, floor) else 0.02)


def build_hospitality_scene(bm, props, ctx, tier):
    """Compose the tavern/inn front: veranda, sign, decor, window boxes, well."""
    is_hospitality = ctx.effective_archetype in ('TAVERN', 'INN')
    is_inn = ctx.effective_archetype == 'INN'

    porch_info = None
    if _prop(props, 'has_veranda', False) or is_hospitality:
        # Anchor the veranda to the OUTERMOST front face (the jettied upper wall)
        # and clear the log bulge, so the awning roof never pokes into the
        # interior or under the upper storey.
        _fronts = [ctx.bounds_for(f)[2] for f in range(ctx.num_floors)]
        outer_front = min(_fronts) - _wall_out(props, ctx, tier)
        porch_info = build_tavern_porch(
            bm, -ctx.hx, ctx.hx, front_y=outer_front,
            z_ground=0.0, door_x=ctx.main_door_cx,
            door_h=_prop(props, 'door_height', 2.4), found_h=ctx.found_h,
        )

    if _prop(props, 'has_trade_sign', False) or is_hospitality:
        # Prefer a big sign hung on each roof gable end; only fall back to the
        # beside-the-door wall sign when the roof raises no gables at all.
        if _build_gable_signs(bm, props, ctx, tier) == 0:
            _build_trade_sign(bm, props, ctx, porch_info)

    if _prop(props, 'has_flower_boxes', False):
        _build_window_flower_boxes(bm, props, ctx, tier)

    if _prop(props, 'has_outdoor_decor', False) or is_hospitality:
        _build_yard_decor(bm, props, ctx, tier, is_inn, porch_info)

    if _prop(props, 'has_well', False):
        _build_well(bm, props, ctx)


def _build_trade_sign(bm, props, ctx, porch_info=None):
    """A large sign hung on the facade beside the door, clear of overhangs.

    Mounted on the outer face of the storey at the sign's height (so jetties and
    log bulges never bury it), on whichever side of the door is free of a wing.
    """
    door_x = ctx.main_door_cx
    outer = _wall_out(props, ctx, _prop(props, 'material_tier', 'TIER_2'))
    door_half = _prop(props, 'door_width', 1.2) * 0.5

    # Keep the sign on the ground storey's wall (a fixed +3.x mount floated above
    # the wall top on single-storey buildings).
    mount_z = ctx.found_h + ctx.floor_h * 0.60
    face_y = ctx.bounds_for(0)[2] - outer

    # Pick the side of the door that is clear of the front-wing footprint.
    side = -1.0
    for cand in (-1.0, 1.0):
        cx = door_x + cand * (door_half + 1.30)
        if is_point_outside_building(cx, face_y - 0.35, 0.30, ctx, margin=0.05):
            side = cand
            break

    mount_x = door_x + side * (door_half + 1.25)
    build_hanging_sign(
        bm, mount_x, face_y - 0.03, mount_z,
        run_ang=-math.pi * 0.5,
        bracket_len=1.05, board_w=1.15, board_h=0.96, light_board=True,
    )


def _build_gable_signs(bm, props, ctx, tier):
    """Hang one large trade sign on every roof gable end (main, wings, annex).

    The main gable/sway roof raises two gable-end walls: FRONT/BACK for a
    front-back ridge, LEFT/RIGHT for a rotated ridge. A main gable end already
    taken by a wing or the side annex is skipped. Returns how many were placed.
    """
    roof_style = _prop(props, 'roof_style', 'SWAY')
    roof_h = _prop(props, 'roof_height', 3.0)
    outer = _wall_out(props, ctx, tier, ctx.num_floors - 1)
    has_hatch = bool(_prop(props, 'has_loft_hatch', False))
    anchors = []

    if roof_style in ('GABLE', 'SWAY'):
        b = ctx.bounds_for(ctx.num_floors - 1)
        cx, cy = (b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5
        # A loft hatch sits low in one gable; hang the board high enough that it
        # clears the hatch instead of sitting in the middle of it.
        gz = ctx.top_z + roof_h * (0.80 if has_hatch else 0.5)
        annex_side = (_prop(props, 'annex_side', 'LEFT')
                      if _prop(props, 'has_side_annex', False) else None)
        ends = ('LEFT', 'RIGHT') if ctx.is_rotated_roof else ('FRONT', 'BACK')
        for end in ends:
            if end == 'FRONT':
                sx, sy, ang = cx, b[2] - outer, -math.pi * 0.5
            elif end == 'BACK':
                sx, sy, ang = cx, b[3] + outer, math.pi * 0.5
            elif end == 'LEFT':
                if annex_side == 'LEFT':
                    continue
                sx, sy, ang = b[0] - outer, cy, math.pi
            else:
                if annex_side == 'RIGHT':
                    continue
                sx, sy, ang = b[1] + outer, cy, 0.0
            anchors.append((sx, sy, gz, ang))

    # Wing gables: each wing reads as a cross-gable facing away from the wall.
    wtop = ctx.found_h + max(1, ctx.wing_floors) * ctx.floor_h
    wrh = roof_h * _prop(props, 'wing_roof_scale', 0.88)
    w_out = _wall_out(props, ctx, tier, max(0, ctx.wing_floors - 1))
    for w in getattr(ctx, 'wings', []):
        base, wall = w.get('base'), w.get('wall')
        if not base:
            continue
        if wall == 'FRONT':
            ax, ay, ang = (base[0] + base[1]) * 0.5, base[2] - w_out, -math.pi * 0.5
        elif wall == 'BACK':
            ax, ay, ang = (base[0] + base[1]) * 0.5, base[3] + w_out, math.pi * 0.5
        elif wall == 'LEFT':
            ax, ay, ang = base[0] - w_out, (base[2] + base[3]) * 0.5, math.pi
        else:
            ax, ay, ang = base[1] + w_out, (base[2] + base[3]) * 0.5, 0.0
        anchors.append((ax, ay, wtop + max(0.8, wrh * 0.5), ang))

    # Annex gable: its cross-gable faces straight out from the main side wall.
    if _prop(props, 'has_side_annex', False):
        side_sgn = 1.0 if _prop(props, 'annex_side', 'LEFT') == 'RIGHT' else -1.0
        a_floors = max(1, min(2, _prop(props, 'annex_floors', 2)))
        a_d = 3.6 if tier == 'TIER_1' else 4.0
        a_roof = 3.0 if tier == 'TIER_3' else 2.6
        a_out = _wall_out(props, ctx, tier, a_floors - 1)
        ax = side_sgn * (ctx.hx + a_d - 0.6 + a_out)
        atop = ctx.found_h + a_floors * ctx.floor_h
        ang = 0.0 if side_sgn > 0 else math.pi
        anchors.append((ax, 0.0, atop + max(0.8, a_roof * 0.5), ang))

    for ax, ay, az, ang in anchors:
        build_hanging_sign(bm, ax, ay, az, run_ang=ang,
                           bracket_len=1.55, board_w=1.00, board_h=0.90,
                           light_board=True)
    return len(anchors)


def _build_window_flower_boxes(bm, props, ctx, tier):
    """Mount plain soil-filled planters right up under the lower-storey sills."""
    depth = 0.22
    height = 0.22

    for fl_idx, facades in ctx.window_centers.items():
        if fl_idx > 1:
            continue
        # Planters clear the whole log bulge (a touch more than the sign/lantern
        # skin offset) so their top edge meets the sill; stone ground storeys are
        # flush, so they only need the thin offset.
        wall_out = ctx.wall_t * 0.5 + (0.22 if _is_log_floor(props, ctx, tier, fl_idx) else 0.06)
        for facade, windows in facades.items():
            for wx, wy, sill_z in windows:
                # Seat the top edge flush against the underside of the sill.
                z_box = sill_z - height + 0.03
                if facade == 'FRONT':
                    by = wy - (wall_out + depth * 0.5)
                    bx, ang = wx, 0.0
                elif facade == 'BACK':
                    by = wy + (wall_out + depth * 0.5)
                    bx, ang = wx, math.pi
                elif facade == 'LEFT':
                    bx = wx - (wall_out + depth * 0.5)
                    by, ang = wy, -math.pi * 0.5
                else: # RIGHT
                    bx = wx + (wall_out + depth * 0.5)
                    by, ang = wy, math.pi * 0.5

                build_flower_box(bm, bx, by, z_base=z_box, ang=ang,
                                 length=0.95, depth=depth, height=height)


def get_building_footprint_boxes(ctx):
    """Returns list of (x_min, x_max, y_min, y_max) for main building and all wings."""
    boxes = [(-ctx.hx, ctx.hx, -ctx.hy, ctx.hy)]
    for w in getattr(ctx, 'wings', []):
        b = w.get('base')
        if b:
            boxes.append((b[0], b[1], b[2], b[3]))
    return boxes


def is_point_outside_building(x, y, radius, ctx, margin=0.30):
    """Returns True if a circle of (x, y, radius + margin) does NOT intersect the building or any wing."""
    r = radius + margin
    for x1, x2, y1, y2 in get_building_footprint_boxes(ctx):
        if (x1 - r <= x <= x2 + r) and (y1 - r <= y <= y2 + r):
            return False
    return True


def _build_yard_decor(bm, props, ctx, tier, is_inn, porch_info=None):
    """A natural, cozy tavern beer garden and supply nook flanking a clear entrance path."""
    door_x = ctx.main_door_cx
    door_yf = ctx.main_door_yf
    face_y = door_yf
    rich = tier in ('TIER_2', 'TIER_3')
    best = tier == 'TIER_3'

    porch_w = 2.8
    porch_d = 1.5 if (_prop(props, 'has_veranda', False) or ctx.effective_archetype in ('TAVERN', 'INN')) else 0.0

    # 1. Wall lanterns hung at both front corners of the facade (no poles).
    outer = _wall_out(props, ctx, tier)
    lan_z = ctx.found_h + ctx.floor_h * 0.62
    lan_y = ctx.bounds_for(0)[2] - outer
    front_win_x = [w[0] for w in ctx.window_centers.get(0, {}).get('FRONT', [])]
    door_half_l = _prop(props, 'door_width', 1.2) * 0.5
    for s in (-1, 1):
        X0 = max(1.5, ctx.hx - 0.55)
        # If a front wing crowds this corner, start further in.
        if not is_point_outside_building(s * X0, lan_y - 0.30, 0.25, ctx, margin=0.05):
            X0 = max(1.2, ctx.hx - 1.7)
        # Slide along the wall until clear of every window and the door.
        best_lx, best_score = s * X0, -1e9
        for dX in (0.0, -0.45, 0.45, -0.9, 0.9, -1.35, 1.35, -1.8, 1.8):
            X = X0 + dX
            if X < 0.9 or X > ctx.hx - 0.35:
                continue
            cand = s * X
            win_clear = min((abs(cand - wx) for wx in front_win_x), default=99.0)
            door_clear = abs(cand - ctx.main_door_cx) - door_half_l
            score = min(win_clear, door_clear + 0.02)
            if score > best_score:
                best_score, best_lx = score, cand
        build_hanging_lantern(bm, best_lx, lan_y - 0.02, z_top=lan_z,
                              arm_ang=-math.pi * 0.5, arm_len=0.65,
                              scale=1.0 if rich else 0.92)

    # 2. Tavern Supply Nook: Barrels, Crates & Grain Sacks tucked against the exterior foundation
    side_sign = 1.0
    bx_base = door_x + porch_w * 0.5 + 0.55
    if not is_point_outside_building(bx_base + 0.40, face_y - 0.70, 0.40, ctx, margin=0.10):
        # Right side blocked by a wing; mirror to left side
        side_sign = -1.0
        bx_base = door_x - porch_w * 0.5 - 1.25

    if is_point_outside_building(bx_base, face_y - 0.65, 0.35, ctx, margin=0.05):
        build_barrel(bm, bx_base + side_sign * 0.10, face_y - 0.65, radius=0.34, height=0.74)
        build_barrel(bm, bx_base + side_sign * 0.70, face_y - 0.60, radius=0.27, height=0.60)
        build_barrel(bm, bx_base + side_sign * 0.40, face_y - 1.25, radius=0.30, height=0.68, lying=True, ang=0.15 * side_sign)
        build_stool(bm, bx_base + side_sign * 0.85, face_y - 1.10)

        cx_base = bx_base + side_sign * 1.45
        if is_point_outside_building(cx_base, face_y - 0.75, 0.35, ctx, margin=0.05):
            build_crate(bm, cx_base, face_y - 0.75, ang=0.14 * side_sign, size=0.60)
            if rich and is_point_outside_building(cx_base + side_sign * 0.60, face_y - 1.05, 0.30, ctx, margin=0.05):
                build_crate(bm, cx_base + side_sign * 0.60, face_y - 1.05, ang=-0.18 * side_sign, size=0.48)
                build_sack(bm, cx_base + side_sign * 0.15, face_y - 1.40, scale=1.05)

    # 3. Tavern Beer Garden: a tidy picnic table cluster, clear of the door path.
    tx_base = door_x - side_sign * (porch_w * 0.5 + 1.85)
    table_y = face_y - (porch_d + 1.45)
    if is_point_outside_building(tx_base, table_y, 0.95, ctx, margin=0.15):
        build_picnic_table(bm, tx_base, table_y, ang=0.08 * -side_sign, length=2.05)
        if rich and is_point_outside_building(tx_base - side_sign * 1.10, table_y - 1.70, 0.95, ctx, margin=0.15):
            build_picnic_table(bm, tx_base - side_sign * 1.10, table_y - 1.70,
                               ang=-0.12 * -side_sign, length=1.95)

    # 4. A bench set against the wall beside the entrance (left if free, else right).
    door_half = _prop(props, 'door_width', 1.2) * 0.5
    for s in (-1.0, 1.0):
        bench_x = door_x + s * (door_half + 1.75)
        bench_y = face_y - (outer + 0.30)
        if is_point_outside_building(bench_x, bench_y, 0.40, ctx, margin=0.05):
            build_bench(bm, bench_x, bench_y, ang=0.0, length=1.60, with_back=True)
            break

    # 5. Notice board. On an L-shaped building it leans on the wing wall; on a
    #    plain rectangle/square it sits against the facade wall beside the door,
    #    facing the street (rotated 90 deg relative to the wing-wall case).
    #    Placed just clear of the front-most footprint (the jettied top floor
    #    sticks out past the ground wall, so "against the wall" has to clear it).
    min_y = min(b[2] for b in get_building_footprint_boxes(ctx))
    nb_y = min_y - 0.85
    if ctx.shape == 'L_SHAPE':
        nb_ang = -math.radians(45.0)
    else:
        nb_ang = 0.0
    nb_x = door_x + (door_half + 1.95)
    for s in (1.0, -1.0):
        cand_x = door_x + s * (door_half + 1.95)
        if is_point_outside_building(cand_x, nb_y, 0.45, ctx, margin=0.10):
            nb_x = cand_x
            break
    if is_point_outside_building(nb_x, nb_y, 0.45, ctx, margin=0.10):
        build_notice_board(bm, nb_x, nb_y, ang=nb_ang, width=1.10, post_h=1.70)


def _build_well(bm, props, ctx):
    """A well tucked off to the LEFT of the entrance so it never blocks the door."""
    door_yf = ctx.main_door_yf
    candidates = [
        (-ctx.hx - 2.8, door_yf - 2.1),
        (-ctx.hx - 3.3, door_yf - 3.5),
        (-ctx.hx - 2.5, door_yf + 1.9),
        (-ctx.hx * 0.6, door_yf - 5.2),
        (ctx.hx + 2.8, door_yf - 2.1),
        (ctx.hx + 3.3, door_yf - 3.5),
    ]
    for wx, wy in candidates:
        # Margin clears the roof overhang too, so the hood can't meet the framing.
        if is_point_outside_building(wx, wy, 1.15, ctx, margin=0.90):
            build_well(bm, wx, wy, z_ground=0.0, radius=0.66, wall_h=0.62)
            return
    min_y = min(b[2] for b in get_building_footprint_boxes(ctx))
    build_well(bm, -ctx.hx - 3.2, min_y - 2.6, z_ground=0.0, radius=0.66, wall_h=0.62)

