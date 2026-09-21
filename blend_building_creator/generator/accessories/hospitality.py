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
    build_barrel, build_crate, build_clay_pot, build_bench,
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
    return (tier or getattr(props, 'material_tier', 'TIER_1')) == 'TIER_1'


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

    # An arched entry porch and a covered veranda are mutually exclusive; when the
    # arched porch is present it owns the entrance, so skip the veranda entirely.
    has_arched = _prop(props, 'has_arched_porch', False)
    porch_info = None
    if (_prop(props, 'has_veranda', False) or is_hospitality) and not has_arched:
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
        # With an arched entry porch the gable anchors sit behind the porch roof,
        # so hang the sign off the porch's own beam instead.
        if has_arched:
            _build_porch_sign(bm, props, ctx, tier)
        elif _build_gable_signs(bm, props, ctx, tier) == 0:
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


def _build_porch_sign(bm, props, ctx, tier):
    """Hang the trade sign off the arched entry porch's outer beam.

    The gable anchors sit behind the porch hood, which buries the sign, so when an
    arched porch owns the entrance the sign is carried on the porch itself.
    """
    door_x = ctx.main_door_cx
    front_y = ctx.main_door_yf
    top_bounds = ctx.floor_wall_bounds.get(ctx.num_floors - 1)
    if top_bounds is not None and top_bounds[2] < front_y:
        front_y = top_bounds[2]
    # Mirror build_arched_porch(): outer beam sits on piers set 1.75m out.
    pier_y = (front_y - 2.05) + 0.30
    eave_z = 2.9 + 0.22
    mount_x = door_x - (1.5 - 0.15)
    build_hanging_sign(
        bm, mount_x, pier_y - 0.02, eave_z + 0.06,
        run_ang=-math.pi * 0.5,
        bracket_len=0.95, board_w=1.05, board_h=0.90, light_board=True,
    )


def _build_gable_signs(bm, props, ctx, tier):
    """Hang trade sign on the roof gable end facing the street."""
    roof_style = _prop(props, 'roof_style', 'SWAY')
    roof_h = _prop(props, 'roof_height', 3.0)
    outer = _wall_out(props, ctx, tier, ctx.num_floors - 1)
    has_hatch = bool(_prop(props, 'has_loft_hatch', False))
    anchors = []

    # Priority 1: Front wing cross-gable (projects furthest forward toward the street)
    for w in getattr(ctx, 'wings', []):
        wall = w.get('wall')
        if wall == 'FRONT':
            wfl = max(1, ctx.wing_floors)
            wtop = ctx.found_h + wfl * ctx.floor_h
            wrh = roof_h * _prop(props, 'wing_roof_scale', 0.88)
            w_out = _wall_out(props, ctx, tier, wfl - 1)
            base = (w.get('bounds_fl') or {}).get(wfl - 1) or w.get('base')
            if base:
                ax = (base[0] + base[1]) * 0.5
                ay = base[2] - w_out
                az = wtop + max(0.9, wrh * 0.52)
                anchors.append((ax, ay, az, -math.pi * 0.5))
                break

    # Priority 2: Main roof front gable
    if not anchors and roof_style in ('GABLE', 'SWAY'):
        b = ctx.bounds_for(ctx.num_floors - 1)
        cx, cy = (b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5
        gz = ctx.top_z + roof_h * (0.75 if has_hatch else 0.55)
        if not ctx.is_rotated_roof:
            sx, sy, ang = cx, b[2] - outer, -math.pi * 0.5
            anchors.append((sx, sy, gz, ang))
        else:
            # Rotated roof: ridge runs left-right, gable ends face left/right
            annex_side = (_prop(props, 'annex_side', 'LEFT')
                          if _prop(props, 'has_side_annex', False) else None)
            if annex_side != 'LEFT':
                anchors.append((b[0] - outer, cy, gz, math.pi))
            elif annex_side != 'RIGHT':
                anchors.append((b[1] + outer, cy, gz, 0.0))

    # Priority 3: Side annex cross-gable if no other gable was found
    if not anchors and _prop(props, 'has_side_annex', False):
        side_sgn = 1.0 if _prop(props, 'annex_side', 'LEFT') == 'RIGHT' else -1.0
        a_floors = max(1, min(2, _prop(props, 'annex_floors', 2)))
        a_d = 3.6 if tier == 'TIER_1' else 4.0
        a_roof = 3.0 if tier == 'TIER_3' else 2.6
        a_face = ctx.base_w * 0.5 + a_d - 0.6
        a_out = 0.12 if tier == 'TIER_1' else 0.03
        ax = side_sgn * (a_face + a_out)
        atop = ctx.found_h + a_floors * ctx.floor_h
        ang = 0.0 if side_sgn > 0 else math.pi
        anchors.append((ax, 0.0, atop + max(0.8, a_roof * 0.5), ang))

    for ax, ay, az, ang in anchors:
        build_hanging_sign(bm, ax, ay, az, run_ang=ang,
                           bracket_len=1.55, board_w=1.05, board_h=0.92,
                           light_board=True)
    return len(anchors)


def _build_window_flower_boxes(bm, props, ctx, tier):
    """Mount plain soil-filled planters right up under the lower-storey sills."""
    depth = 0.22
    height = 0.22

    for fl_idx, facades in ctx.window_centers.items():
        if fl_idx > 1:
            continue
        # The exterior timber sill projects ~0.20m past the wall face, so the
        # planter has to clear that or it buries itself inside the sill. This is
        # true on flush stone/plank/stucco walls too, not just log bulges.
        wall_out = ctx.wall_t * 0.5 + 0.22
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
    #    If a wing occupies that corner, hang the lantern on the wing's own outer
    #    wall instead of burying it inside the wing block.
    outer = _wall_out(props, ctx, tier)
    lan_z = ctx.found_h + ctx.floor_h * 0.62
    lan_y = ctx.bounds_for(0)[2] - outer
    front_win_x = [w[0] for w in ctx.window_centers.get(0, {}).get('FRONT', [])]
    door_half_l = _prop(props, 'door_width', 1.2) * 0.5

    def _blocking_wing(s):
        """Wing whose footprint covers the front corner on side s, if any."""
        for w in getattr(ctx, 'wings', []):
            b = (w.get('bounds_fl') or {}).get(max(1, ctx.wing_floors) - 1) or w.get('base')
            if not b:
                continue
            wall = w.get('wall')
            if wall == 'FRONT' and b[2] < lan_y - 0.2 and (b[0] - 0.6) <= s * (ctx.hx - 0.55) <= (b[1] + 0.6):
                return w, b, wall
            if wall == 'LEFT' and s < 0:
                return w, b, wall
            if wall == 'RIGHT' and s > 0:
                return w, b, wall
        return None

    for s in (-1, 1):
        wing = _blocking_wing(s)
        if wing is not None:
            _w, _b, wall = wing
            # The lantern hangs at ground-storey height, so mount it on the wing's
            # GROUND footprint (a jettied wing wall sits proud of the ground wall).
            b = _w.get('base') or _b
            w_out = _wall_out(props, ctx, tier, 0)
            # Keep the original wall, but sit right on the wing's corner post
            # instead of 0.6m inboard (which landed it in a window).
            inset = 0.14
            lx = (b[1] - inset) if s > 0 else (b[0] + inset)
            if wall == 'FRONT':
                build_hanging_lantern(bm, lx, b[2] - w_out - 0.065, z_top=lan_z,
                                      arm_ang=-math.pi * 0.5, arm_len=0.65,
                                      scale=1.0 if rich else 0.92)
            elif wall == 'BACK':
                build_hanging_lantern(bm, lx, b[3] + w_out + 0.065, z_top=lan_z,
                                      arm_ang=math.pi * 0.5, arm_len=0.65,
                                      scale=1.0 if rich else 0.92)
            elif wall == 'LEFT':
                build_hanging_lantern(bm, b[0] - w_out - 0.065, b[2] + inset, z_top=lan_z,
                                      arm_ang=math.pi, arm_len=0.65,
                                      scale=1.0 if rich else 0.92)
            else:
                build_hanging_lantern(bm, b[1] + w_out + 0.065, b[2] + inset, z_top=lan_z,
                                      arm_ang=0.0, arm_len=0.65,
                                      scale=1.0 if rich else 0.92)
            continue

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

        cx_base = bx_base + side_sign * 1.45
        if is_point_outside_building(cx_base, face_y - 0.75, 0.35, ctx, margin=0.05):
            build_crate(bm, cx_base, face_y - 0.75, ang=0.14 * side_sign, size=0.60)
            if rich and is_point_outside_building(cx_base + side_sign * 0.60, face_y - 1.05, 0.30, ctx, margin=0.05):
                build_crate(bm, cx_base + side_sign * 0.60, face_y - 1.05, ang=-0.18 * side_sign, size=0.48)
                build_clay_pot(bm, cx_base + side_sign * 0.15, face_y - 1.40, radius=0.21,
                               height=0.52, ang=0.3, pot_type='JAR')

    # 3. Tavern Beer Garden: a single picnic table, clear of the door path (Tavern/Inn only).
    if is_inn or ctx.effective_archetype in ('TAVERN', 'INN'):
        tx_base = door_x - side_sign * (porch_w * 0.5 + 1.85)
        table_y = face_y - (porch_d + 1.45)
        if is_point_outside_building(tx_base, table_y, 0.95, ctx, margin=0.15):
            build_picnic_table(bm, tx_base, table_y, ang=0.08 * -side_sign, length=2.05)

    # 4. A bench set against the wall beside the entrance on the free side.
    door_half = _prop(props, 'door_width', 1.2) * 0.5
    bench_side = -side_sign
    bench_x = door_x + bench_side * (door_half + 1.55)
    bench_y = face_y - (outer + 0.30)
    if is_point_outside_building(bench_x, bench_y, 0.40, ctx, margin=0.05):
        build_bench(bm, bench_x, bench_y, ang=0.0, length=1.50, with_back=True)

    # 5. Notice board: strictly for Inns / Taverns. Never on artisan workshops.
    if is_inn or ctx.effective_archetype in ('TAVERN', 'INN'):
        # Place with generous clearance away from entrance and barrels
        nb_side = -side_sign
        nb_x = door_x + nb_side * (porch_w * 0.5 + 2.50)
        min_y = min(b[2] for b in get_building_footprint_boxes(ctx))
        nb_y = min_y - 0.90
        nb_ang = -math.radians(45.0) if ctx.shape == 'L_SHAPE' else 0.0
        if is_point_outside_building(nb_x, nb_y, 0.50, ctx, margin=0.15):
            build_notice_board(bm, nb_x, nb_y, ang=nb_ang, width=1.10, post_h=1.70)


def _build_well(bm, props, ctx):
    """A well tucked off to the LEFT of the entrance so it never blocks the door."""
    door_yf = ctx.main_door_yf
    is_tavern = ctx.effective_archetype == 'TAVERN'
    max_xy = 9.1 if is_tavern else 19.0

    # Side clearance from main wall: sits in the side garden lane
    side_x = ctx.hx + 1.45
    if is_tavern:
        side_x = min(side_x, max_xy - 0.9)

    candidates = [
        (-side_x, door_yf + 1.2),
        (-side_x, door_yf - 1.6),
        (-side_x, 0.0),
        (-ctx.hx - 2.8, door_yf - 2.1),
        (-ctx.hx - 3.3, door_yf - 3.5),
        (-ctx.hx - 2.5, door_yf + 1.9),
        (-ctx.hx * 0.6, door_yf - 3.5),
        (side_x, door_yf + 1.2),
        (ctx.hx + 2.8, door_yf - 2.1),
        (ctx.hx + 3.3, door_yf - 3.5),
    ]

    # Beyond the manor's own footprint the side lanes belong to the estate
    # outbuildings and their fenced pens, so keep the well in the honor court.
    if _prop(props, 'has_stable', False) or _prop(props, 'has_servant_quarters', False):
        candidates = [
            (ctx.hx * 0.42, door_yf - 3.0),
            (-ctx.hx * 0.42, door_yf - 3.0),
            (ctx.hx * 0.60, door_yf - 5.2),
            (-ctx.hx * 0.60, door_yf - 5.2),
        ]

    for wx, wy in candidates:
        if is_tavern and (abs(wx) > max_xy or abs(wy) > max_xy):
            continue
        # Margin clears the roof overhang too, so the hood can't meet the framing.
        if is_point_outside_building(wx, wy, 1.15, ctx, margin=0.90):
            build_well(bm, wx, wy, z_ground=0.0, radius=0.66, wall_h=0.62)
            return
    min_y = min(b[2] for b in get_building_footprint_boxes(ctx))
    fallback_x = -min(side_x, max_xy - 0.9) if is_tavern else (-ctx.hx - 3.2)
    fallback_y = max(min_y - 2.2, -max_xy) if is_tavern else (min_y - 2.6)
    build_well(bm, fallback_x, fallback_y, z_ground=0.0, radius=0.66, wall_h=0.62)

