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
_STAIR_W = 1.10
_LAND_LEN = 1.30          # along the wall
_LAND_DEPTH = 1.35        # outward from the wall
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


def exterior_stair_plan(props, ctx):
    """Compute the whole stair: flights, per-storey landings and footprints.

    Returns a dict with:
      flights  : [{wall, a0, a1, z0, z1}]  (a* = along-coordinate on wall)
      landings : [{floor, wall, along, z, name, axis, fixed, outward}]
      rects    : [(facade, floor_idx, (a0, a1))] for window exclusion
    or None when there is no exterior stair.
    """
    if not getattr(props, 'has_exterior_stairs', False):
        return None
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    if n_floors < 2:
        return None
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    found_h = float(getattr(ctx, 'found_h', 0.4))
    ring = _wall_ring(props, ctx)

    n_up = n_floors - 1
    steps = max(3, int(math.ceil(floor_h / _STEP_H_MAX)))
    flight_len = steps * _STEP_D

    flights, landings, rects = [], [], []
    wall_i = 0
    wall = ring[wall_i]
    # Start from the low end when walking forward, high end when walking back.
    pos = wall['lo'] if wall['dir'] > 0 else wall['hi']
    z_prev = 0.0
    first = True

    def _end_pos(w):
        return w['hi'] if w['dir'] > 0 else w['lo']

    for i in range(1, n_floors):
        z_target = found_h + i * floor_h
        # Move to the next wall if this flight (plus its landing) will not fit.
        need = flight_len + _LAND_LEN
        if not first:
            pos = pos  # already advanced past the previous landing
        fits = ((wall['dir'] > 0 and pos + need <= wall['hi'] + 1e-6) or
                (wall['dir'] < 0 and pos - need >= wall['lo'] - 1e-6))
        if not fits:
            # Corner landing at the wall end, then turn onto the next wall.
            cpos = _end_pos(wall)
            landings.append({
                'floor': i - 1, 'wall': wall['name'], 'along': cpos,
                'z': z_prev, 'axis': wall['axis'], 'fixed': wall['fixed'],
                'outward': wall['outward'], 'corner': True})
            wall_i = (wall_i + 1) % len(ring)
            wall = ring[wall_i]
            pos = wall['lo'] if wall['dir'] > 0 else wall['hi']

        a0 = pos
        a1 = pos + wall['dir'] * flight_len
        flights.append({'wall': wall['name'], 'a0': a0, 'a1': a1,
                        'z0': z_prev, 'z1': z_target})
        pos = a1
        landings.append({
            'floor': i, 'wall': wall['name'], 'along': pos,
            'door_along': pos + wall['dir'] * _LAND_LEN * 0.5,
            'z': z_target, 'axis': wall['axis'], 'fixed': wall['fixed'],
            'outward': wall['outward'], 'corner': False})
        pos = pos + wall['dir'] * _LAND_LEN
        z_prev = z_target
        first = False

    # Footprints for exclusion: each flight and landing covers a strip on its
    # wall from a0..a1 (+ landing) at the storey's z.
    for f in flights:
        lo, hi = sorted((f['a0'], f['a1']))
        rects.append((f['wall'], None, (lo - 0.35, hi + 0.35)))
    for ld in landings:
        a = ld['along']
        rects.append((ld['wall'], ld['floor'], (a - 0.20, a + _LAND_LEN + 0.20)))
    return {'flights': flights, 'landings': landings, 'rects': rects,
            'ring': ring}


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


def build_exterior_stairs(bm, props, ctx, tier='TIER_1'):
    """Build the planned external stair (flights + a landing per storey)."""
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return
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

        # Outer stringer + handrail following the flight pitch.
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

        # Ground starter block on the first flight.
        if f is plan['flights'][0]:
            bx, by = wp(wall, a0 + 0.10 * sgn_d, u_c)
            if wall['axis'] == 'Y':
                bsize = (_STAIR_W + 0.20, 0.30)
            else:
                bsize = (0.30, _STAIR_W + 0.20)
            create_beveled_box(bm, size=(bsize[0], bsize[1], 0.12),
                               location=(bx, by, 0.06),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)

    # ---- Landings (one per storey, plus corner turns) -----------------------
    for ld in plan['landings']:
        wall = ring[ld['wall']]
        a = ld['along']
        z = ld['z']
        u_in = clear - 0.10
        u_out = clear + _LAND_DEPTH
        if wall['axis'] == 'Y':
            length_along = _LAND_LEN + (0.20 if ld.get('corner') else 0.0)
            cx, cy = wp(wall, a + length_along * 0.5 * (1.0 if wall['dir'] > 0 else -1.0),
                        (u_in + u_out) * 0.5)
            deck = (abs(u_out - u_in), length_along)
        else:
            length_along = _LAND_LEN + (0.20 if ld.get('corner') else 0.0)
            cx, cy = wp(wall, a + length_along * 0.5 * (1.0 if wall['dir'] > 0 else -1.0),
                        (u_in + u_out) * 0.5)
            deck = (length_along, abs(u_out - u_in))
        create_beveled_box(bm, size=(deck[0], deck[1], 0.06),
                           location=(cx, cy, z + 0.03),
                           mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
        # Outer support post + rail on the landing's outer edge.
        p0 = wp(wall, a, u_out - 0.06)
        _dir = 1.0 if wall['dir'] > 0 else -1.0
        p1 = wp(wall, a + length_along * _dir, u_out - 0.06)
        build_railing(bm, p0, p1, z + 0.06, height=_RAIL_H,
                      post_spacing=1.0, braces=False)
        # End railing across the far end of the platform, unless a flight
        # departs from exactly there (the walk continues upward). Terminal
        # landings and corner turns always get it: with a single flight the
        # end is closed here, and with continuing flights it moves up to the
        # top landing instead.
        _end = a + length_along * _dir
        _departs = any(f['wall'] == ld['wall'] and abs(f['a0'] - _end) < 0.06
                       for f in plan['flights'])
        if not _departs:
            _r0 = wp(wall, _end, u_in)
            _r1 = wp(wall, _end, u_out - 0.06)
            build_railing(bm, _r0, _r1, z + 0.06, height=_RAIL_H,
                          braces=False, post_spacing=1.0)
        # Deck lip bridging the stand-off gap to the wall face.
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
        # Vertical support post down to grade on the outer corner.
        if not ld.get('corner'):
            px, py = wp(wall, a + 0.10 * (1.0 if wall['dir'] > 0 else -1.0), u_out - 0.12)
            create_beveled_box(bm, size=(0.16, 0.16, z),
                               location=(px, py, z * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)
