"""
Exterior wooden staircase system for multi-apartment tenements.

Builds an external timber stair that climbs the outside of the building with a
railed landing at EVERY upper storey (so each floor's apartment entrance is
reachable from outside), wrapping around the corners when a storey's flight no
longer fits the current wall. The plan is computed once and shared by the
geometry builder, the per-floor door placement and the window exclusions, so
the stair, the doors and the windows can never overlap each other.
"""

import math
from mathutils import Vector, Matrix
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..railing import build_railing
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_STAIRS, MAT_INDEX_TIMBER_FRAME,
)


# Proportions shared by the plan, the geometry and the exclusion helper.
_STAIR_W = 1.30          # stair tread width (step planks)
_LAND_LEN = 1.30          # along the wall (corner landing length)
_LAND_DEPTH = 1.35        # outward from the wall (small landing)
_WALK_DEPTH = 2.50        # walkway width (perpendicular to wall) — min 2.5m for comfortable passage
_STEP_D = 0.26            # tread depth
_STEP_H_MAX = 0.215       # riser height cap
_RAIL_H = 0.95
_EDGE = 0.85              # wall run kept clear at each corner


def _stair_clearance(props):
    """Distance from the wall CENTRELINE the stair structure stands off.

    Tier 1 walls are stacks of bulging round logs, so the stair clears well
    past the log crest; planked and masonry walls need only a hair.
    """
    wall_t = float(getattr(props, 'wall_thickness', 0.28))
    tier = getattr(props, 'material_tier', 'TIER_3')
    bulge = 0.26 if tier == 'TIER_1' else 0.06
    return wall_t * 0.5 + bulge


def _wall_ring(props, ctx):
    """The four walls as an ordered walk around the building.

    Uses the BASE footprint (plus any cantilever) rather than the per-floor
    wall bounds: the stair plan is built during the wall phase, before the
    context's floor bounds exist, and a stable footprint keeps the doors, the
    stairs and the window exclusions all agreeing.

    Each wall: dict(name, axis, fixed, outward, dir, lo, hi) where 'fixed' is
    the wall line coordinate, 'outward' the sign away from the building, 'dir'
    the walk direction along the axis and lo/hi the usable span.
    """
    hw = float(getattr(ctx, 'base_w', 8.0)) * 0.5
    hd = float(getattr(ctx, 'base_d', 8.0)) * 0.5
    if getattr(props, 'has_cantilever', False):
        _c = float(getattr(props, 'cantilever_overhang', 0.35))
        hw += _c
        hd += _c
    x_min, x_max = -hw, hw
    y_min, y_max = -hd, hd

    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    m = _EDGE

    left = dict(name='LEFT', axis='Y', fixed=x_min, outward=-1.0, dir=1.0,
                lo=y_min + m, hi=y_max - m)
    front = dict(name='FRONT', axis='X', fixed=y_min, outward=-1.0, dir=-1.0,
                 lo=x_min + m, hi=x_max - m)
    right = dict(name='RIGHT', axis='X', fixed=x_max, outward=1.0, dir=-1.0,
                 lo=y_min + m, hi=y_max - m)
    back = dict(name='BACK', axis='Y', fixed=y_max, outward=1.0, dir=1.0,
                lo=x_min + m, hi=x_max - m)

    # NOTE: wings project OUTWARD from the base footprint, while every stair
    # run and landing sits alongside the base edges (|along| within the base
    # span), so projecting wings can never overlap the stair - no clamping.

    if side == 'LEFT':
        return [left, back, right, front]
    return [right, back, left, front]


def _courtyard_stair_plan(props, ctx):
    """Symmetrical courtyard dual-stair system and elevated gallery for U-shape buildings."""
    wings = getattr(ctx, 'wings', [])
    if len(wings) < 2:
        return None
    w0, w1 = wings[0], wings[1]
    wx1_l, wx2_l, wy1_l, wy2_l = w0['base']
    wx1_r, wx2_r, wy1_r, wy2_r = w1['base']

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))

    base_w = float(getattr(ctx, 'base_w', getattr(props, 'width', 32.0)))
    hx = base_w * 0.5
    gap0 = max(wx2_l, -hx)
    gap1 = min(wx1_r, hx)
    gap_w = max(2.0, gap1 - gap0)
    y_min = wy2_l  # main building front wall

    stair_w = max(2.50, float(getattr(props, 'stair_width', 2.50)))
    gal_depth = max(2.60, stair_w + 0.10)
    wall_clearance = 0.20

    # Ground flight climbs from courtyard grade z=0.0 up to second-floor gallery
    climb_h = found_h + floor_h
    steps = max(3, int(math.ceil(climb_h / _STEP_H_MAX)))
    flight_len = steps * _STEP_D

    y_gal_edge = y_min - gal_depth
    y_bot = y_gal_edge - flight_len

    if gap_w >= 9.0:
        apt_doors = [
            gap0 + gap_w * 0.125,
            gap0 + gap_w * 0.375,
            gap0 + gap_w * 0.625,
            gap0 + gap_w * 0.875,
        ]
    else:
        apt_doors = [
            gap0 + gap_w * 0.25,
            gap0 + gap_w * 0.75,
        ]

    lane_w = min(stair_w, max(1.80, (gap_w - 1.6) * 0.25))
    cx_in_l = gap0 + wall_clearance + lane_w * 0.5
    cx_out_l = gap0 + wall_clearance + lane_w + 0.12 + lane_w * 0.5
    cx_in_r = gap1 - wall_clearance - lane_w * 0.5
    cx_out_r = gap1 - wall_clearance - lane_w - 0.12 - lane_w * 0.5

    flights = []
    landings = []
    rects = []

    for i in range(1, n_floors):
        z_target = found_h + i * floor_h
        z_prev = 0.0 if i == 1 else (found_h + (i - 1) * floor_h)

        # Alternating stepped lanes (all climbing +Y with full open headroom):
        # i == 1 (Gr -> Fl 2): Inner lane climbs +Y (y_bot -> y_gal_edge)
        # i == 2 (Fl 2 -> Fl 3): Outer lane climbs +Y (y_bot -> y_gal_edge)
        # i == 3 (Fl 3 -> Fl 4): Inner lane climbs +Y (y_bot -> y_gal_edge)
        if i % 2 == 1:
            a0, a1 = y_bot, y_gal_edge
            x_l, x_r = cx_in_l, cx_in_r
            lane_name = 'INNER'
        else:
            a0, a1 = y_gal_edge, y_bot
            x_l, x_r = cx_out_l, cx_out_r
            lane_name = 'OUTER'

        flights.append({
            'wall': 'COURTYARD_LEFT',
            'a0': a0, 'a1': a1,
            'z0': z_prev, 'z1': z_target,
            'x': x_l, 'stair_w': lane_w, 'side': 'LEFT',
            'lane': lane_name, 'floor': i
        })
        flights.append({
            'wall': 'COURTYARD_RIGHT',
            'a0': a0, 'a1': a1,
            'z0': z_prev, 'z1': z_target,
            'x': x_r, 'stair_w': lane_w, 'side': 'RIGHT',
            'lane': lane_name, 'floor': i
        })

        for dx in apt_doors:
            landings.append({
                'floor': i, 'wall': 'FRONT',
                'along': dx,
                'door_along': dx,
                'z': z_target, 'axis': 'X', 'fixed': y_min,
                'outward': -1.0, 'corner': False
            })
            rects.append(('FRONT', i, (dx - 1.10, dx + 1.10)))

        rects.append(('LEFT', i, (y_bot - 0.3, y_min + 0.2)))
        rects.append(('RIGHT', i, (y_bot - 0.3, y_min + 0.2)))

    return {
        'is_courtyard': True,
        'gap0': gap0, 'gap1': gap1, 'gap_w': gap_w,
        'y_min': y_min, 'wy1': wy1_l,
        'gal_depth': gal_depth, 'stair_w': stair_w, 'lane_w': lane_w,
        'cx_in_l': cx_in_l, 'cx_out_l': cx_out_l,
        'cx_in_r': cx_in_r, 'cx_out_r': cx_out_r,
        'wall_clearance': wall_clearance,
        'flight_len': flight_len,
        'flights': flights, 'landings': landings, 'rects': rects,
        'ring': [
            {'name': 'FRONT', 'axis': 'X', 'fixed': y_min, 'outward': -1.0, 'dir': -1.0, 'lo': gap0, 'hi': gap1}
        ]
    }


def _dual_side_stair_plan(props, ctx):
    """Dual exterior staircases on Left and Right sides for rectangular buildings."""
    hw = float(getattr(ctx, 'base_w', 8.0)) * 0.5
    hd = float(getattr(ctx, 'base_d', 8.0)) * 0.5
    if getattr(props, 'has_cantilever', False):
        _c = float(getattr(props, 'cantilever_overhang', 0.35))
        hw += _c
        hd += _c
    x_min, x_max = -hw, hw
    y_min, y_max = -hd, hd
    m = _EDGE

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))

    steps = max(3, int(math.ceil(floor_h / _STEP_H_MAX)))
    flight_len = steps * _STEP_D

    flights, landings, rects = [], [], []
    ring = [
        dict(name='LEFT', axis='Y', fixed=x_min, outward=-1.0, dir=1.0, lo=y_min + m, hi=y_max - m),
        dict(name='RIGHT', axis='Y', fixed=x_max, outward=1.0, dir=1.0, lo=y_min + m, hi=y_max - m),
    ]

    for i in range(1, n_floors):
        z_target = found_h + i * floor_h
        z_prev = 0.0 if i == 1 else (found_h + (i - 1) * floor_h)
        climb = z_target - z_prev
        steps_i = max(3, int(math.ceil(climb / _STEP_H_MAX)))
        flight_len_i = steps_i * _STEP_D

        # Left side
        pos_l = y_min + m + (i - 1) * (flight_len_i + _LAND_LEN)
        pos_l = min(pos_l, y_max - m - flight_len_i - _LAND_LEN)
        a0_l = pos_l
        a1_l = pos_l + flight_len_i
        flights.append({'wall': 'LEFT', 'a0': a0_l, 'a1': a1_l, 'z0': z_prev, 'z1': z_target})
        landings.append({
            'floor': i, 'wall': 'LEFT', 'along': a1_l,
            'door_along': a1_l + _LAND_LEN * 0.5,
            'z': z_target, 'axis': 'Y', 'fixed': x_min,
            'outward': -1.0, 'corner': False
        })
        rects.append(('LEFT', i, (a0_l - 0.35, a1_l + _LAND_LEN + 0.2)))

        # Right side
        pos_r = y_min + m + (i - 1) * (flight_len_i + _LAND_LEN)
        pos_r = min(pos_r, y_max - m - flight_len_i - _LAND_LEN)
        a0_r = pos_r
        a1_r = pos_r + flight_len_i
        flights.append({'wall': 'RIGHT', 'a0': a0_r, 'a1': a1_r, 'z0': z_prev, 'z1': z_target})
        landings.append({
            'floor': i, 'wall': 'RIGHT', 'along': a1_r,
            'door_along': a1_r + _LAND_LEN * 0.5,
            'z': z_target, 'axis': 'Y', 'fixed': x_max,
            'outward': 1.0, 'corner': False
        })
        rects.append(('RIGHT', i, (a0_r - 0.35, a1_r + _LAND_LEN + 0.2)))

    return {'flights': flights, 'landings': landings, 'rects': rects, 'ring': ring}


def exterior_stair_plan(props, ctx):
    """Compute the whole stair: flights, per-storey landings and footprints.

    For single-side (LEFT/RIGHT) tenements this generates:
      - A full-length walkway along the building side wall at every upper floor
      - One stair flight at the front end of the walkway climbing between floors
      - Landing spots at the stair top at each floor (where a door may open)
    Returns a dict with:
      flights  : [{wall, a0, a1, z0, z1}]
      landings : [{floor, wall, along, z, axis, fixed, outward, corner, door_along}]
      rects    : [(facade, floor_idx, (a0, a1))] for window exclusion
    or None when there is no exterior stair.
    """
    if not getattr(props, 'has_exterior_stairs', False):
        return None
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    if n_floors < 2:
        return None

    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    shape = getattr(ctx, 'shape', getattr(props, 'building_shape', 'RECTANGLE'))

    if shape == 'U_SHAPE' or side == 'COURTYARD':
        cp = _courtyard_stair_plan(props, ctx)
        if cp:
            return cp
    if side == 'BOTH':
        return _dual_side_stair_plan(props, ctx)

    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))
    ring = _wall_ring(props, ctx)
    wall = ring[0]  # primary wall (LEFT or RIGHT)

    n_up = n_floors - 1
    steps = max(3, int(math.ceil(floor_h / _STEP_H_MAX)))
    flight_len = steps * _STEP_D

    # The walkway runs along the full wall span (lo..hi).
    # The stair flight occupies a strip at the lo-end (front of building).
    # Each floor's walkway is a full-depth (_WALK_DEPTH) platform along the wall.
    walk_depth = _WALK_DEPTH
    walk_lo = wall['lo']  # start of walkway along-wall
    walk_hi = wall['hi']  # end of walkway along-wall

    # Stair is placed at the FRONT (lo end) of the walkway, occupying
    # flight_len along-wall space, with the stair itself outboard of the walkway.
    stair_lo = walk_lo
    stair_hi = walk_lo + flight_len

    flights, landings, rects = [], [], []
    z_prev = 0.0

    for i in range(1, n_floors):
        z_target = found_h + i * floor_h

        # One stair flight per floor transition, at the front (lo) end
        flights.append({
            'wall': wall['name'],
            'a0': stair_lo, 'a1': stair_hi,
            'z0': z_prev, 'z1': z_target,
            'walk_depth': walk_depth,
            'is_walkway_stair': True,
        })

        # One landing at the stair top (beginning of the walkway at that floor)
        # The door is mid-walkway, near the front
        door_a = stair_hi + (walk_hi - stair_hi) * 0.25
        landings.append({
            'floor': i, 'wall': wall['name'],
            'along': stair_hi,
            'door_along': door_a,
            'z': z_target,
            'axis': wall['axis'], 'fixed': wall['fixed'],
            'outward': wall['outward'],
            'corner': False,
            'is_walkway': True,
            'walk_lo': walk_lo, 'walk_hi': walk_hi,
            'walk_depth': walk_depth,
            'stair_lo': stair_lo, 'stair_hi': stair_hi,
        })
        z_prev = z_target

    # Exclusion footprints
    # Stair strip: covers stair_lo..stair_hi + extra outboard
    rects.append((wall['name'], None, (stair_lo - 0.30, stair_hi + 0.20)))
    # Walkway strip: covers full wall span at each upper floor
    for i in range(1, n_floors):
        rects.append((wall['name'], i, (walk_lo - 0.20, walk_hi + 0.20)))

    return {
        'flights': flights, 'landings': landings, 'rects': rects,
        'ring': ring,
        'is_walkway': True,
        'wall': wall,
        'walk_lo': walk_lo, 'walk_hi': walk_hi,
        'walk_depth': walk_depth,
        'stair_lo': stair_lo, 'stair_hi': stair_hi,
        'flight_len': flight_len,
    }


def _wall_point(wall, along, u):
    """World XY for a point 'along' the wall and 'u' outward from its centreline."""
    if wall['axis'] == 'Y':
        return (wall['fixed'] + wall['outward'] * u, along)
    return (along, wall['fixed'] + wall['outward'] * u)


def exterior_stairs_y_span(props, ctx):
    """Back-compat helper: (a0, a1) span on the selected side wall, or None."""
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return None
    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    lo, hi = None, None
    for wall_name, _fl, (a0, a1) in plan['rects']:
        if wall_name != side:
            continue
        lo = a0 if lo is None else min(lo, a0)
        hi = a1 if hi is None else max(hi, a1)
    return None if lo is None else (lo, hi)


def exterior_stair_door_spots(props, ctx):
    """Landing-door positions per floor, in world coordinates.

    Pure geometry (no bm): floors.py registers these into the planning
    doorways BEFORE rooms are planned, so partitions never land where a
    landing door must go. The builder re-derives the same spots afterwards.
    Returns {floor_idx: [{'x','y','axis','w'}]}.
    """
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return {}
    ring = {w['name']: w for w in plan['ring']}
    edw = min(1.20, float(getattr(props, 'door_width', 1.20)))
    out = {}

    if plan.get('is_walkway'):
        # For walkway plans: apartments are split at mid-depth of the walkway span.
        # Place two entrance doors per floor: one in each half of the wall span.
        wall = plan['wall']
        walk_lo = plan['walk_lo']
        walk_hi = plan['walk_hi']
        mid = (walk_lo + walk_hi) * 0.5
        door_s = (walk_lo + mid) * 0.5   # south/front apartment door
        door_n = (mid + walk_hi) * 0.5   # north/back apartment door
        for ld in plan['landings']:
            if ld.get('corner'):
                continue
            fl = ld['floor']
            if wall['axis'] == 'Y':
                x = wall['fixed']
                out.setdefault(fl, []).append({'x': x, 'y': door_s, 'axis': 'Y', 'w': edw})
                out.setdefault(fl, []).append({'x': x, 'y': door_n, 'axis': 'Y', 'w': edw})
            else:
                y = wall['fixed']
                out.setdefault(fl, []).append({'x': door_s, 'y': y, 'axis': 'X', 'w': edw})
                out.setdefault(fl, []).append({'x': door_n, 'y': y, 'axis': 'X', 'w': edw})
        return out

    for ld in plan['landings']:
        if ld.get('corner'):
            continue
        wall = ring[ld['wall']]
        a = ld.get('door_along', ld['along'])
        if wall['axis'] == 'Y':
            x = wall['fixed']
            out.setdefault(ld['floor'], []).append(
                {'x': x, 'y': a, 'axis': 'Y', 'w': edw})
        else:
            y = wall['fixed']
            out.setdefault(ld['floor'], []).append(
                {'x': a, 'y': y, 'axis': 'X', 'w': edw})
    return out


def _build_courtyard_flight(bm, cx, y_start, y_end, z_start, z_end, stair_w,
                            railing_courtyard_side=+1.0):
    """Builds a single straight timber flight with treads, risers, stringers, center beam and railing."""
    run_len = y_end - y_start
    total_h = z_end - z_start
    steps = max(3, int(math.ceil(abs(total_h) / _STEP_H_MAX)))
    step_h = total_h / steps
    step_d = run_len / steps
    sgn_d = 1.0 if run_len > 0 else -1.0
    diag = math.hypot(abs(run_len), abs(total_h))
    pitch = math.atan2(abs(total_h), abs(run_len))

    # Treads and risers
    for s in range(steps):
        sy = y_start + (s + 0.5) * step_d
        sz = z_start + (s + 0.5) * step_h
        create_beveled_box(
            bm, size=(stair_w, abs(step_d) + 0.04, 0.06),
            location=(cx, sy, sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
        )
        create_box(
            bm, size=(stair_w - 0.02, 0.04, abs(step_h)),
            location=(cx, sy - step_d * 0.5 + 0.02 * sgn_d, sz - step_h * 0.5),
            mat_index=MAT_INDEX_STAIRS
        )

    # Stringers and carriage beam rotation
    # If run_len > 0 (climbing +Y): pitch around X
    # If run_len < 0 (climbing -Y): pitch around X and pi around Z so beam slants along -Y and +Z
    rot = (pitch, 0.0, 0.0) if sgn_d > 0 else (pitch, 0.0, math.pi)

    # Center carriage beam
    create_box(
        bm, size=(0.10, diag, 0.20),
        location=(cx, (y_start + y_end) * 0.5, (z_start + z_end) * 0.5 - 0.03),
        rotation=rot,
        mat_index=MAT_INDEX_TIMBER
    )

    # Outer and inner stringers
    u_l = cx - stair_w * 0.5 - 0.04
    u_r = cx + stair_w * 0.5 + 0.04
    for u_str in (u_l, u_r):
        create_box(
            bm, size=(0.08, diag, 0.22),
            location=(u_str, (y_start + y_end) * 0.5, (z_start + z_end) * 0.5),
            rotation=rot,
            mat_index=MAT_INDEX_TIMBER
        )

    # Railing on exposed courtyard side
    u_rail = cx + railing_courtyard_side * (stair_w * 0.5 + 0.04)
    p0 = (u_rail, y_start + 0.08 * sgn_d)
    p1 = (u_rail, y_end - 0.08 * sgn_d)
    build_railing(
        bm, p0, p1,
        z_start + 0.06, height=_RAIL_H, base_z_end=z_end + 0.06,
        post_spacing=1.1, baluster_spacing=0.22, braces=False
    )


def _build_courtyard_stairs(bm, props, ctx, plan, tier='TIER_1'):
    """Constructs the physical 3D geometry of the U-shaped tenement courtyard switchback stair-system and galleries."""
    gap0 = plan['gap0']
    gap1 = plan['gap1']
    gap_w = plan['gap_w']
    y_min = plan['y_min']
    gal_depth = plan['gal_depth']
    stair_w = plan['stair_w']
    lane_w = plan.get('lane_w', min(stair_w, max(1.80, (gap_w - 1.6) * 0.25)))
    cx_in_l = plan.get('cx_in_l', gap0 + 0.20 + lane_w * 0.5)
    cx_out_l = plan.get('cx_out_l', cx_in_l + lane_w + 0.12)
    cx_in_r = plan.get('cx_in_r', gap1 - 0.20 - lane_w * 0.5)
    cx_out_r = plan.get('cx_out_r', cx_in_r - lane_w - 0.12)

    wall_clearance = plan.get('wall_clearance', 0.20)
    flight_len = plan['flight_len']

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))

    y_top = y_min - gal_depth + 0.08
    y_bot = y_top - flight_len

    z_walkways = {}
    for fl_idx in range(1, n_floors):
        z_walkways[fl_idx] = found_h + fl_idx * floor_h - 0.02

    top_walkway_z = z_walkways[n_floors - 1]

    cantilever = float(getattr(props, 'cantilever_overhang', 0.35)) if getattr(props, 'has_cantilever', False) else 0.0
    overhang_mode = getattr(props, 'overhang_mode', 'ALL_FLOORS')

    # 1. Main Front Gallery Decks for every upper floor (flush to exterior facade)
    deck_cx = (gap0 + gap1) * 0.5
    for fl_idx in range(1, n_floors):
        zw = z_walkways[fl_idx]
        fov = cantilever if overhang_mode == 'SECOND_FLOOR_ONLY' else (fl_idx * cantilever) if cantilever > 0.0 else 0.0
        y_facade = y_min - fov
        gal_cy = y_facade - gal_depth * 0.5

        create_beveled_box(
            bm, size=(gap_w + 0.04, gal_depth, 0.07),
            location=(deck_cx, gal_cy, zw + 0.035),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
        )
        # Heavy Timber Ledger, Center, and Front Support Beams
        create_box(bm, size=(gap_w + 0.04, 0.16, 0.24),
                   location=(deck_cx, y_facade - 0.08, zw - 0.12),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(gap_w + 0.04, 0.16, 0.24),
                   location=(deck_cx, y_facade - gal_depth * 0.5, zw - 0.12),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(gap_w + 0.04, 0.16, 0.24),
                   location=(deck_cx, y_facade - gal_depth + 0.08, zw - 0.12),
                   mat_index=MAT_INDEX_TIMBER)

    # 2. Continuous Vertical Heavy Timber Columns for the Front Gallery
    post_l = cx_out_l + lane_w * 0.5 + 0.04 if n_floors > 2 else cx_in_l + lane_w * 0.5 + 0.04
    post_r = cx_out_r - lane_w * 0.5 - 0.04 if n_floors > 2 else cx_in_r - lane_w * 0.5 - 0.04
    post_xs = [post_l, gap0 + gap_w * 0.38, gap0 + gap_w * 0.62, post_r]
    post_y = y_min - gal_depth + 0.08
    for px in post_xs:
        create_beveled_box(
            bm, size=(0.20, 0.20, top_walkway_z),
            location=(px, post_y, top_walkway_z * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
        )
        for sgn in (-1.0, 1.0):
            if px <= post_l + 0.05 and sgn < 0:
                continue
            if px >= post_r - 0.05 and sgn > 0:
                continue
            if gap0 + 0.3 < px + sgn * 0.4 < gap1 - 0.3:
                for fl_idx in range(1, n_floors):
                    zw = z_walkways[fl_idx]
                    create_box(
                        bm, size=(0.60, 0.12, 0.12),
                        location=(px + sgn * 0.24, post_y, zw - 0.26),
                        rotation=(0.0, -sgn * 0.785, 0.0),
                        mat_index=MAT_INDEX_TIMBER
                    )

    # 3. Front Edge Guard Railings along the exposed gallery span
    for fl_idx in range(1, n_floors):
        zw = z_walkways[fl_idx]
        fov = cantilever if overhang_mode == 'SECOND_FLOOR_ONLY' else (fl_idx * cantilever) if cantilever > 0.0 else 0.0
        y_facade = y_min - fov
        rail_y = y_facade - gal_depth + 0.05
        rx0 = post_l + 0.08
        rx1 = post_r - 0.08
        if rx1 > rx0 + 0.6:
            build_railing(
                bm, (rx0, rail_y), (rx1, rail_y),
                zw + 0.07, height=_RAIL_H,
                post_spacing=1.2, baluster_spacing=0.22, braces=False
            )

        # On upper floors where no stair flight ascends from y_top, the outer lane above
        # the stair below must also have front guard railings so there is no drop-off gap:
        has_flight_at_top = (n_floors >= fl_idx + 2)
        if not has_flight_at_top and fl_idx >= 2:
            lx0 = cx_in_l + lane_w * 0.5 + 0.04
            lx1 = post_l + 0.08
            if lx1 > lx0 + 0.4:
                build_railing(
                    bm, (lx0, rail_y), (lx1, rail_y),
                    zw + 0.07, height=_RAIL_H,
                    post_spacing=1.1, baluster_spacing=0.22, braces=False
                )
            rx0_out = post_r - 0.08
            rx1_out = cx_in_r - lane_w * 0.5 - 0.04
            if rx1_out > rx0_out + 0.4:
                build_railing(
                    bm, (rx0_out, rail_y), (rx1_out, rail_y),
                    zw + 0.07, height=_RAIL_H,
                    post_spacing=1.1, baluster_spacing=0.22, braces=False
                )

    # 4. Multi-Floor Switchback Landings and Connecting Walkways
    if n_floors > 2:
        tot_w = (cx_out_l + lane_w * 0.5 + 0.08) - (gap0 + wall_clearance - 0.05)
        cx_land_l = ((gap0 + wall_clearance - 0.05) + (cx_out_l + lane_w * 0.5 + 0.08)) * 0.5
        cx_land_r = ((gap1 - wall_clearance + 0.05) + (cx_out_r - lane_w * 0.5 - 0.08)) * 0.5

        land_len = max(1.60, lane_w)
        land_bot_cy = y_bot - land_len * 0.5 + 0.04
        y_land_front = y_bot - land_len + 0.04
        ww_len = flight_len + 0.10
        ww_cy = (y_bot + y_top) * 0.5

        top_zw = z_walkways[n_floors - 1]

        # Structural support columns under the outer landing at y_bot down to grade (built once up to highest walkway)
        for px in (cx_out_l + lane_w * 0.5 + 0.04, cx_out_l - lane_w * 0.5 - 0.04):
            create_beveled_box(bm, size=(0.20, 0.20, top_zw),
                               location=(px, land_bot_cy, top_zw * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
        for px in (cx_out_r - lane_w * 0.5 - 0.04, cx_out_r + lane_w * 0.5 + 0.04):
            create_beveled_box(bm, size=(0.20, 0.20, top_zw),
                               location=(px, land_bot_cy, top_zw * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)

        for fl_idx in range(2, n_floors):
            zw = z_walkways[fl_idx]

            # Switchback Landing at y_bot bridging outer arrival to inner walkway
            create_beveled_box(
                bm, size=(tot_w, land_len, 0.07),
                location=(cx_land_l, land_bot_cy, zw + 0.035),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
            )
            build_railing(bm, (cx_out_l + lane_w * 0.5 + 0.04, y_bot),
                          (cx_out_l + lane_w * 0.5 + 0.04, y_land_front),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.0, baluster_spacing=0.22)
            build_railing(bm, (cx_out_l + lane_w * 0.5 + 0.04, y_land_front),
                          (gap0 + wall_clearance, y_land_front),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.0, baluster_spacing=0.22)

            create_beveled_box(
                bm, size=(tot_w, land_len, 0.07),
                location=(cx_land_r, land_bot_cy, zw + 0.035),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
            )
            build_railing(bm, (cx_out_r - lane_w * 0.5 - 0.04, y_bot),
                          (cx_out_r - lane_w * 0.5 - 0.04, y_land_front),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.0, baluster_spacing=0.22)
            build_railing(bm, (cx_out_r - lane_w * 0.5 - 0.04, y_land_front),
                          (gap1 - wall_clearance, y_land_front),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.0, baluster_spacing=0.22)

            # Connecting Wing Walkway along the INNER lane (next to wing wall)
            fov_i = cantilever if overhang_mode == 'SECOND_FLOOR_ONLY' else (fl_idx * cantilever) if cantilever > 0.0 else 0.0
            rail_y_i = (y_min - fov_i) - gal_depth + 0.05
            y_top_inner = min(y_top, rail_y_i)

            # Left inner wing walkway
            create_beveled_box(
                bm, size=(lane_w + 0.08, ww_len, 0.07),
                location=(cx_in_l, ww_cy, zw + 0.035),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
            )
            build_railing(bm, (cx_in_l + lane_w * 0.5 + 0.04, y_bot),
                          (cx_in_l + lane_w * 0.5 + 0.04, y_top_inner),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.2, baluster_spacing=0.22)

            # Right inner wing walkway
            create_beveled_box(
                bm, size=(lane_w + 0.08, ww_len, 0.07),
                location=(cx_in_r, ww_cy, zw + 0.035),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
            )
            build_railing(bm, (cx_in_r - lane_w * 0.5 - 0.04, y_bot),
                          (cx_in_r - lane_w * 0.5 - 0.04, y_top_inner),
                          zw + 0.07, height=_RAIL_H, post_spacing=1.2, baluster_spacing=0.22)

    # 5. Stair Flights (All open to the sky with complete headroom!)
    # Flight 1: Ground (z = 0.0) -> Floor 2 (zw2), Inner Lane, climbing +Y
    zw2 = z_walkways[1]
    _build_courtyard_flight(bm, cx_in_l, y_bot, y_top, 0.0, zw2, lane_w, railing_courtyard_side=+1.0)
    _build_courtyard_flight(bm, cx_in_r, y_bot, y_top, 0.0, zw2, lane_w, railing_courtyard_side=-1.0)

    # Upper Flights: Floor 2 -> Floor 3, Floor 3 -> Floor 4, etc. Outer Lane, switchback climbing -Y (open sky!)
    for fl_idx in range(2, n_floors):
        z_start = z_walkways[fl_idx - 1]
        z_end = z_walkways[fl_idx]
        _build_courtyard_flight(bm, cx_out_l, y_top, y_bot, z_start, z_end, lane_w, railing_courtyard_side=+1.0)
        _build_courtyard_flight(bm, cx_out_r, y_top, y_bot, z_start, z_end, lane_w, railing_courtyard_side=-1.0)


def _build_walkway_stair(bm, wall, a0, a1, z0, z1, clear, walk_depth):
    """Build a stair flight climbing from z0 to z1, running along-wall from a0 to a1.

    The stair is placed OUTBOARD of the walkway at distance (clear + walk_depth) from
    the wall centreline, so it doesn't overlap the walkway deck. The stair runs parallel
    to the wall (along the 'along' axis).
    """
    span = a1 - a0
    rise = z1 - z0
    n = max(3, int(math.ceil(abs(rise) / _STEP_H_MAX)))
    step_h = rise / n
    step_d = span / n
    sgn_d = 1.0 if span > 0 else -1.0

    stair_w = _STAIR_W
    # Stair centre: just outboard of the walkway deck outer edge
    u_stair = clear + walk_depth + stair_w * 0.5 + 0.08

    for i in range(n):
        a = a0 + step_d * (i + 0.5)
        sz = z0 + (i + 0.5) * step_h
        cx, cy = _wall_point(wall, a, u_stair)
        if wall['axis'] == 'Y':
            sz_tread = sz
            create_beveled_box(bm, size=(stair_w, abs(step_d) + 0.04, 0.06),
                               location=(cx, cy, sz_tread),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
            rx, ry = _wall_point(wall, a - step_d * 0.5 + 0.02 * sgn_d, u_stair)
            create_box(bm, size=(stair_w - 0.02, 0.04, abs(step_h)),
                       location=(rx, ry, sz_tread - step_h * 0.5),
                       mat_index=MAT_INDEX_STAIRS)
        else:
            create_beveled_box(bm, size=(abs(step_d) + 0.04, stair_w, 0.06),
                               location=(cx, cy, sz),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
            rx, ry = _wall_point(wall, a - step_d * 0.5 + 0.02 * sgn_d, u_stair)
            create_box(bm, size=(0.04, stair_w - 0.02, abs(step_h)),
                       location=(rx, ry, sz - step_h * 0.5),
                       mat_index=MAT_INDEX_STAIRS)

    # Outer stringer (angled along the pitch)
    run_len = abs(span)
    diag = math.hypot(run_len, abs(rise))
    pitch = math.atan2(abs(rise), run_len)
    u_str = u_stair + stair_w * 0.5 + 0.06
    sx, sy = _wall_point(wall, (a0 + a1) * 0.5, u_str)
    if wall['axis'] == 'Y':
        rot = (pitch * sgn_d, 0.0, 0.0)
        ssize = (0.10, diag, 0.22)
    else:
        rot = (0.0, -pitch * sgn_d, 0.0)
        ssize = (diag, 0.10, 0.22)
    create_box(bm, size=ssize, location=(sx, sy, (z0 + z1) * 0.5),
               rotation=rot, mat_index=MAT_INDEX_TIMBER)

    # Inner stringer (wall side)
    u_str_in = u_stair - stair_w * 0.5 - 0.06
    sx_in, sy_in = _wall_point(wall, (a0 + a1) * 0.5, u_str_in)
    create_box(bm, size=ssize, location=(sx_in, sy_in, (z0 + z1) * 0.5),
               rotation=rot, mat_index=MAT_INDEX_TIMBER)

    # Railing on outer side of stair only
    p_start = _wall_point(wall, a0 + 0.08 * sgn_d, u_str)
    p_end = _wall_point(wall, a1, u_str)
    build_railing(bm, p_start, p_end, z0 + 0.06, height=_RAIL_H,
                  base_z_end=z1 + 0.06, post_spacing=1.1,
                  baluster_spacing=0.22, braces=False)

    # Bottom end cap railing (perpendicular, across the stair width at bottom)
    pb0 = _wall_point(wall, a0, u_stair - stair_w * 0.5 - 0.04)
    pb1 = _wall_point(wall, a0, u_str)
    build_railing(bm, pb0, pb1, z0 + 0.06, height=_RAIL_H,
                  braces=False, post_spacing=2.0)

    # Vertical support posts for the stair at bottom and top
    for pa, pz in ((a0, z0), (a1, z1)):
        ppx, ppy = _wall_point(wall, pa, u_stair)
        create_beveled_box(bm, size=(0.16, 0.16, pz),
                           location=(ppx, ppy, pz * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)


def _build_single_side_walkway_stairs(bm, props, ctx, plan):
    """Build a continuous elevated walkway along one building side, with stair flights at the front.

    Design:
    - At each upper floor: a full-length deck (walk_lo..walk_hi, walk_depth wide) along the wall
    - A single stair flight at the lo-end, outboard of the deck, climbing from prev floor to this floor
    - Railing only on outer edge of deck; no railing between deck and wall
    - Heavy vertical timber posts at intervals supporting the deck from grade
    - At the stair top: a short landing platform bridging stair to walkway deck
    """
    wall = plan['wall']
    walk_lo = plan['walk_lo']
    walk_hi = plan['walk_hi']
    walk_depth = plan['walk_depth']
    stair_lo = plan['stair_lo']
    stair_hi = plan['stair_hi']
    flight_len = plan['flight_len']

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))
    clear = _stair_clearance(props)

    walk_len = walk_hi - walk_lo  # building depth (along-wall)

    # u-coordinates relative to wall centreline:
    u_wall_face = float(getattr(props, 'wall_thickness', 0.28)) * 0.5
    u_deck_in = clear           # inner edge of walkway deck (near wall face)
    u_deck_out = clear + walk_depth  # outer edge of walkway deck
    u_deck_cx = (u_deck_in + u_deck_out) * 0.5

    # Stair is further outboard
    stair_w = _STAIR_W
    u_stair_cx = u_deck_out + stair_w * 0.5 + 0.08

    top_z = found_h + (n_floors - 1) * floor_h

    # Support post positions along the walkway (every ~2.5m)
    post_spacing = 2.40
    n_posts = max(2, int(math.ceil(walk_len / post_spacing)))
    post_positions = [walk_lo + walk_len * k / (n_posts - 1) for k in range(n_posts)]

    for fl_idx in range(1, n_floors):
        z_floor = found_h + fl_idx * floor_h
        z_prev = 0.0 if fl_idx == 1 else (found_h + (fl_idx - 1) * floor_h)

        # ---- 1. Full walkway deck ----
        deck_cx_along = (walk_lo + walk_hi) * 0.5
        deck_cx, deck_cy = _wall_point(wall, deck_cx_along, u_deck_cx)
        if wall['axis'] == 'Y':
            deck_size = (walk_depth, walk_len, 0.07)
        else:
            deck_size = (walk_len, walk_depth, 0.07)
        create_beveled_box(bm, size=deck_size,
                           location=(deck_cx, deck_cy, z_floor + 0.035),
                           mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

        # Ledger beam along the wall (supports inner deck edge)
        lx, ly = _wall_point(wall, deck_cx_along, u_deck_in - 0.04)
        if wall['axis'] == 'Y':
            create_box(bm, size=(0.20, walk_len, 0.22),
                       location=(lx, ly, z_floor - 0.11),
                       mat_index=MAT_INDEX_TIMBER)
        else:
            create_box(bm, size=(walk_len, 0.20, 0.22),
                       location=(lx, ly, z_floor - 0.11),
                       mat_index=MAT_INDEX_TIMBER)

        # Outer fascia beam
        fx, fy = _wall_point(wall, deck_cx_along, u_deck_out + 0.04)
        if wall['axis'] == 'Y':
            create_box(bm, size=(0.20, walk_len + 0.10, 0.22),
                       location=(fx, fy, z_floor - 0.11),
                       mat_index=MAT_INDEX_TIMBER)
        else:
            create_box(bm, size=(walk_len + 0.10, 0.20, 0.22),
                       location=(fx, fy, z_floor - 0.11),
                       mat_index=MAT_INDEX_TIMBER)

        # ---- 2. Outer railing along the full walkway length ----
        rail_lo = walk_lo + 0.10
        rail_hi = walk_hi - 0.10
        rp0 = _wall_point(wall, rail_lo, u_deck_out - 0.06)
        rp1 = _wall_point(wall, rail_hi, u_deck_out - 0.06)
        build_railing(bm, rp0, rp1, z_floor + 0.07, height=_RAIL_H,
                      post_spacing=1.20, baluster_spacing=0.22, braces=False)

        # ---- 3. End railings (perpendicular caps at lo and hi ends of walkway) ----
        # lo-end (front): open gap where stair arrives — no railing here
        # hi-end (back): closed cap
        ep_in = _wall_point(wall, walk_hi - 0.05, u_deck_in)
        ep_out = _wall_point(wall, walk_hi - 0.05, u_deck_out - 0.06)
        build_railing(bm, ep_in, ep_out, z_floor + 0.07, height=_RAIL_H,
                      braces=False, post_spacing=2.0)

        # ---- 4. Vertical support posts ----
        for pa in post_positions:
            px, py = _wall_point(wall, pa, u_deck_out - 0.10)
            create_beveled_box(bm, size=(0.18, 0.18, z_floor),
                               location=(px, py, z_floor * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

        # ---- 5. Short landing platform bridging stair top to walkway ----
        # The stair arrives at z_floor at the outboard side; this landing
        # connects u_stair_cx to u_deck_out at a_lo end
        land_along = stair_lo
        land_len = stair_hi - stair_lo
        landing_cx_along = stair_lo + land_len * 0.5
        u_land_cx = (u_stair_cx + u_deck_out * 0.5)
        lnd_cx, lnd_cy = _wall_point(wall, landing_cx_along, u_land_cx)
        land_depth = u_stair_cx - u_deck_out + stair_w + 0.16
        if wall['axis'] == 'Y':
            lnd_size = (land_depth, land_len, 0.07)
        else:
            lnd_size = (land_len, land_depth, 0.07)
        create_beveled_box(bm, size=lnd_size,
                           location=(lnd_cx, lnd_cy, z_floor + 0.035),
                           mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

        # Stair-side railing on the landing (far side, away from stair)
        lp0 = _wall_point(wall, stair_lo, u_stair_cx + stair_w * 0.5 + 0.06)
        lp1 = _wall_point(wall, stair_hi, u_stair_cx + stair_w * 0.5 + 0.06)
        build_railing(bm, lp0, lp1, z_floor + 0.07, height=_RAIL_H,
                      post_spacing=1.1, baluster_spacing=0.22, braces=False)

        # ---- 6. Stair flight from z_prev to z_floor ----
        _build_walkway_stair(bm, wall, stair_lo, stair_hi, z_prev, z_floor, clear, walk_depth)


def build_exterior_stairs(bm, props, ctx, tier='TIER_1'):
    """Build the planned external stair (flights + a landing per storey)."""
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return
    if plan.get('is_courtyard'):
        _build_courtyard_stairs(bm, props, ctx, plan, tier)
        return
    if plan.get('is_walkway'):
        _build_single_side_walkway_stairs(bm, props, ctx, plan)
        return

    # Fallback: legacy small-landing single-flight build (BOTH/dual side)
    ring = {w['name']: w for w in plan['ring']}
    clear = _stair_clearance(props)
    wall_t = float(getattr(props, 'wall_thickness', 0.28))

    def wp(wall, along, u):
        return _wall_point(wall, along, u)

    # ---- Flights -----------------------------------------------------------
    for f in plan['flights']:
        wall = ring[f['wall']]
        a0, a1 = f['a0'], f['a1']
        z0, z1 = f['z0'], f['z1']
        span = a1 - a0
        n = max(3, int(round((z1 - z0) / _STEP_H_MAX)))
        step_h = (z1 - z0) / n
        step_d = span / n
        sgn_d = 1.0 if span > 0 else -1.0
        u_c = clear + _STAIR_W * 0.5
        for i in range(n):
            a = a0 + step_d * (i + 0.5)
            sz = z0 + (i + 0.5) * step_h
            cx, cy = wp(wall, a, u_c)
            if wall['axis'] == 'Y':
                size = (_STAIR_W, abs(step_d) + 0.04)
            else:
                size = (abs(step_d) + 0.04, _STAIR_W)
            create_beveled_box(
                bm, size=(size[0], size[1], 0.06),
                location=(cx, cy, sz),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
            rx, ry = wp(wall, a - step_d * 0.5 + 0.02 * sgn_d, u_c)
            if wall['axis'] == 'Y':
                rsize = (_STAIR_W - 0.02, 0.04)
            else:
                rsize = (0.04, _STAIR_W - 0.02)
            create_box(bm, size=(rsize[0], rsize[1], step_h),
                       location=(rx, ry, sz - step_h * 0.5),
                       mat_index=MAT_INDEX_STAIRS)

        # Outer stringer + handrail
        u_str = clear + _STAIR_W + 0.06
        sx, sy = wp(wall, (a0 + a1) * 0.5, u_str)
        run_len = abs(span)
        rise = z1 - z0
        diag = math.hypot(run_len, rise)
        pitch = math.atan2(rise, run_len)
        if wall['axis'] == 'Y':
            rot = (pitch * sgn_d, 0.0, 0.0)
            size = (0.10, diag, 0.22)
        else:
            rot = (0.0, -pitch * sgn_d, 0.0)
            size = (diag, 0.10, 0.22)
        create_box(bm, size=size, location=(sx, sy, (z0 + z1) * 0.5),
                   rotation=rot, mat_index=MAT_INDEX_TIMBER)
        p_start = wp(wall, a0 + 0.08 * sgn_d, u_str)
        p_end = wp(wall, a1, u_str)
        build_railing(bm, p_start, p_end, z0 + 0.06, height=_RAIL_H,
                      base_z_end=z1 + 0.06, post_spacing=1.1,
                      baluster_spacing=0.22, braces=False)

    # ---- Landings -----------------------------------------------------------
    for ld in plan['landings']:
        wall = ring[ld['wall']]
        a = ld['along']
        z = ld['z']
        u_in = clear - 0.10
        u_out = clear + _LAND_DEPTH
        length_along = _LAND_LEN + (0.20 if ld.get('corner') else 0.0)
        cx, cy = wp(wall, a + length_along * 0.5 * (1.0 if wall['dir'] > 0 else -1.0),
                    (u_in + u_out) * 0.5)
        if wall['axis'] == 'Y':
            deck = (abs(u_out - u_in), length_along)
        else:
            deck = (length_along, abs(u_out - u_in))
        create_beveled_box(bm, size=(deck[0], deck[1], 0.06),
                           location=(cx, cy, z + 0.03),
                           mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
        p0 = wp(wall, a, u_out - 0.06)
        _dir = 1.0 if wall['dir'] > 0 else -1.0
        p1 = wp(wall, a + length_along * _dir, u_out - 0.06)
        build_railing(bm, p0, p1, z + 0.06, height=_RAIL_H,
                      post_spacing=1.0, braces=False)
        _end = a + length_along * _dir
        _departs = any(f['wall'] == ld['wall'] and abs(f['a0'] - _end) < 0.06
                       for f in plan['flights'])
        if not _departs:
            _r0 = wp(wall, _end, u_in)
            _r1 = wp(wall, _end, u_out - 0.06)
            build_railing(bm, _r0, _r1, z + 0.06, height=_RAIL_H,
                          braces=False, post_spacing=1.0)
        u_face = wall_t * 0.5
        if clear > u_face + 0.02:
            la, lb = wp(wall, a, u_face), wp(wall, a, u_in)
            mx, my = (la[0] + lb[0]) * 0.5, (la[1] + lb[1]) * 0.5
            if wall['axis'] == 'Y':
                lsize = (abs(u_in - u_face) + 0.06, 1.30)
            else:
                lsize = (1.30, abs(u_in - u_face) + 0.06)
            create_beveled_box(bm, size=(lsize[0], lsize[1], 0.10),
                               location=(mx, my, z + 0.02),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        if not ld.get('corner'):
            px, py = wp(wall, a + 0.10 * (1.0 if wall['dir'] > 0 else -1.0), u_out - 0.12)
            create_beveled_box(bm, size=(0.16, 0.16, z),
                               location=(px, py, z * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

