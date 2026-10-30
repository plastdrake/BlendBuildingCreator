"""Shared tenement apartment + exterior-stair layout.

This module is the single source of truth for how a tenement is divided into
apartments and where each apartment's one exterior entrance is.  The floor
planner (:mod:`interior`), the ground/upper floor door placement
(:mod:`floors`) and the exterior staircase (:mod:`accessories.exterior_stairs`)
all derive their numbers from here, so rooms, doors and stairs can never
disagree.

Two families are supported:

* ``RECTANGLE`` row tenements with a single exterior side walkway.  Two small
  flats are stacked along the building depth; each is entered straight off the
  walkway wall.
* ``U_SHAPE`` courtyard tenements.  The courtyard-facing middle of the back
  block is split into small flats whose outer two absorb the strips hidden
  behind the wings; each projecting wing is a two-room corner flat entered from
  the courtyard gallery running along its inner wall.

All coordinates are interior (inside the wall face) except where noted.
"""

import math

# Exterior circulation proportions, shared by plan, geometry and exclusions.
# These are bounded by the tightest preset plot (the 12 m-wide tenement rows):
# a two-lane switchback plus gallery must stay inside the plot.
GAL_D = 1.80      # clear walkway / courtyard-gallery depth (1.8m wide walkways)
STAIR_W = 1.45    # single stair lane clear width
LANE_GAP = 0.15   # air gap between the switchback lanes / walkway
STEP_D = 0.28     # tread depth
STEP_H = 0.19     # riser height cap

DW = 1.65         # apartment entrance door width
DWI = 1.55        # internal room doorway width


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _clear(v, lo, hi, m=0.10):
    """Clamp ``v`` into ``[lo+m, hi-m]`` (centre when the span collapses)."""
    lo, hi = lo + m, hi - m
    if hi <= lo:
        return (lo + hi) * 0.5
    return _clamp(v, lo, hi)


def _facades(x0, x1, y0, y1, bounds):
    ix_min, ix_max, iy_min, iy_max = bounds
    out = {}
    if y0 <= iy_min + 0.03:
        out['FRONT'] = (x0, x1)
    if y1 >= iy_max - 0.03:
        out['BACK'] = (x0, x1)
    if x0 <= ix_min + 0.03:
        out['LEFT'] = (y0, y1)
    if x1 >= ix_max - 0.03:
        out['RIGHT'] = (y0, y1)
    return out


def cozy_apartment(bounds, entry, *, role_kitchen='TENEMENT_KITCHEN',
                   role_living='TENEMENT_LIVING',
                   role_parlour='TENEMENT_PARLOUR',
                   role_bed='TENEMENT_BEDROOM', max_rooms=9):
    """Divide one tenement flat into a small grid of realistically sized rooms.

    The entry cell is the kitchen.  Rooms are joined by a shortest-path tree
    from that cell, so every room opens directly off another room exactly once;
    bedrooms are placed on the leaves so no bedroom is ever a route into
    another part of the flat.  Split lines are nudged off the entry door so a
    partition can never bisect a doorway.

    Returns ``(rooms, walls)`` in the same shape used by the apartment layouts.
    """
    x0, x1, y0, y1 = map(float, bounds)
    W, D = x1 - x0, y1 - y0
    area = W * D
    if W <= 0.5 or D <= 0.5:
        return [], []
    n_target = max(4, min(max_rooms, int(round(area / 28.0))))

    # Pick the grid whose room proportions are the most natural.
    best = None
    for nx in range(1, 5):
        for ny in range(1, 6):
            if nx * ny < n_target or nx * ny > max_rooms + 2:
                continue
            if W / nx < 2.20 or D / ny < 2.10:
                continue
            rw, rd = W / nx, D / ny
            score = (abs(nx * ny - n_target)
                     + abs(max(rw, rd) / max(min(rw, rd), 0.5) - 1.0) * 1.2
                     + max(0.0, 2.7 - min(rw, rd)) * 1.5)
            if best is None or score < best[0]:
                best = (score, nx, ny)
    if best is None:
        nx = max(1, min(4, int(round(math.sqrt(n_target * W / max(D, 1e-6))))))
        ny = max(1, min(5, int(math.ceil(n_target / nx))))
    else:
        _, nx, ny = best

    xs = [x0 + W * i / nx for i in range(nx + 1)]
    ys = [y0 + D * i / ny for i in range(ny + 1)]
    ex, ey = float(entry.get('x', (x0 + x1) * 0.5)), float(entry.get('y', (y0 + y1) * 0.5))
    # A grid line exactly on the doorway leaves the door straddling two rooms.
    if entry.get('axis') == 'X':
        for i in range(1, nx):
            if abs(xs[i] - ex) < 0.85:
                xs[i] = min(x1 - 2.20, max(x0 + 2.20, ex + (0.90 if ex <= (x0 + x1) * 0.5 else -0.90)))
    else:
        for i in range(1, ny):
            if abs(ys[i] - ey) < 0.85:
                ys[i] = min(y1 - 2.10, max(y0 + 2.10, ey + (0.90 if ey <= (y0 + y1) * 0.5 else -0.90)))

    def _cell(v, coords):
        for i in range(len(coords) - 1):
            if coords[i] - 1e-6 <= v <= coords[i + 1] + 1e-6:
                return i
        return 0 if v < coords[0] else len(coords) - 2

    root = (_cell(ex, xs), _cell(ey, ys))
    from collections import deque
    parent = {root: None}
    order = [root]
    q = deque([root])
    while q:
        ci, cj = q.popleft()
        for ni, nj in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
            if 0 <= ni < nx and 0 <= nj < ny and (ni, nj) not in parent:
                parent[(ni, nj)] = (ci, cj)
                order.append((ni, nj))
                q.append((ni, nj))

    children = {c: 0 for c in parent}
    for c, par in parent.items():
        if par is not None:
            children[par] = children.get(par, 0) + 1

    walls = []
    _tree_edges = {frozenset((c, par)) for c, par in parent.items() if par is not None}
    # A room grid needs a wall on EVERY shared cell boundary.  The previous
    # pass only built the tree edges, so adjacent rooms that were not directly
    # connected became one huge open room (bed + parlour + living all merged).
    # Tree edges get a doorway; every other shared boundary stays solid.
    for i in range(nx):
        for j in range(ny - 1):
            _shared = frozenset(((i, j), (i, j + 1))) in _tree_edges
            wy = ys[j + 1]
            walls.append({
                'p1': (xs[i], wy), 'p2': (xs[i + 1], wy),
                'axis': 'X', 'pos': wy,
                'doorway': ({'x': (xs[i] + xs[i + 1]) * 0.5, 'y': wy,
                             'axis': 'X', 'w': DWI} if _shared else None),
            })
    for i in range(nx - 1):
        for j in range(ny):
            _shared = frozenset(((i, j), (i + 1, j))) in _tree_edges
            wx = xs[i + 1]
            walls.append({
                'p1': (wx, ys[j]), 'p2': (wx, ys[j + 1]),
                'axis': 'Y', 'pos': wx,
                'doorway': ({'x': wx, 'y': (ys[j] + ys[j + 1]) * 0.5,
                             'axis': 'Y', 'w': DWI} if _shared else None),
            })

    # Depth-first order from the kitchen so bedrooms are leaves only.
    depth = {}
    q = deque([root])
    depth[root] = 0
    while q:
        c = q.popleft()
        for nc in parent:
            if parent.get(nc) == c and nc not in depth:
                depth[nc] = depth[c] + 1
                q.append(nc)

    rooms = []
    _living_cell = next((c for c in order
                         if c != root and children.get(c, 0) > 0), None)
    for c in order:
        ci, cj = c
        rb = (xs[ci], xs[ci + 1], ys[cj], ys[cj + 1])
        if c == root:
            role = role_kitchen
        elif children.get(c, 0) > 0:
            role = role_living if c == _living_cell else role_parlour
        else:
            role = role_bed
        rooms.append({'role': role, 'bounds': rb, 'facades': {}})

    # Guarantee at least one bedroom: the deepest leaf becomes one.
    leaves = [c for c in parent if children.get(c, 0) == 0 and c != root]
    if not any(r['role'] == role_bed for r in rooms) and leaves and len(rooms) > 1:
        c = max(leaves, key=lambda cc: depth.get(cc, 0))
        ci, cj = c
        for r in rooms:
            if r['bounds'] == (xs[ci], xs[ci + 1], ys[cj], ys[cj + 1]):
                r['role'] = role_bed
                break
    return rooms, walls


def rectangle_layout(bounds, side):
    """A row of small gallery flats stacked along the building depth.

    Each flat now gets a several-room plan instead of two giant halves, and the
    row yields multiple flats per storey (one per ~6 m depth band).
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    n_flats = int(max(2, min(4, round(D / 6.0))))
    apts = []
    for k in range(n_flats):
        ay0 = iy_min + D * k / n_flats
        ay1 = iy_min + D * (k + 1) / n_flats
        ex = ix_max if side == 'RIGHT' else ix_min
        # Keep the gallery door off the mid-line of the grid (see below).
        ey = ay0 + (ay1 - ay0) * 0.38
        entry = {'x': ex, 'y': ey, 'axis': 'Y', 'w': DW}
        _rooms, _walls = cozy_apartment((ix_min, ix_max, ay0, ay1), entry)
        for _r in _rooms:
            _r['facades'] = _facades(*_r['bounds'], bounds)
        apts.append({
            'id': f'flat{k + 1}',
            'rooms': _rooms,
            'entry': entry,
            'walls': _walls,
        })
    return apts


def stair_geometry(props, ctx):
    """Shared external-stair metrics (clearance, wall span, per-floor climb)."""
    wall_t = float(getattr(props, 'wall_thickness', 0.28))
    tier = getattr(props, 'material_tier', 'TIER_3')
    bulge = 0.26 if tier == 'TIER_1' else 0.06
    clearance = wall_t * 0.5 + bulge
    found_h = float(getattr(ctx, 'found_h', 0.4))
    floor_h = float(getattr(ctx, 'floor_h', 3.6))
    return {'clearance': clearance, 'found_h': found_h, 'floor_h': floor_h}


def flight_steps(climb):
    steps = max(3, int(math.ceil(max(0.2, climb) / STEP_H)))
    return steps * STEP_D, steps


# ---------------------------------------------------------------------------
# Apartment layouts
# ---------------------------------------------------------------------------

def _wing_coords(w):
    if isinstance(w, dict):
        base = w.get('base') or w.get('bounds')
        if base:
            return float(base[0]), float(base[1]), float(base[2]), float(base[3])
    return float(w[0]), float(w[1]), float(w[2]), float(w[3])


def courtyard_gap(wings):
    w0 = _wing_coords(wings[0])
    w1 = _wing_coords(wings[1])
    gap0 = w0[1]
    gap1 = w1[0]
    return gap0, gap1, max(2.0, gap1 - gap0)


def courtyard_cut_x(ix_min, ix_max, wings):
    """X boundaries of the back-block flats (outer flats absorb the wings)."""
    gap0, gap1, gap_w = courtyard_gap(wings)
    k_main = int(_clamp(round(gap_w / 6.0), 1, 3))
    cut = [gap0 + gap_w * i / k_main for i in range(k_main + 1)]
    cut[0] = ix_min
    cut[-1] = ix_max
    return cut


def courtyard_layout(bounds, wings, wall_t=0.30, fl_idx=None):
    """Small courtyard flats plus one multi-room flat per projecting wing.

    Every flat is now planned as a cluster of realistically sized rooms
    (kitchen + living + bedrooms) instead of a kitchen/bedroom pair that could
    each swallow an entire 18x24 m corner of the block.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    D = iy_max - iy_min
    gap0, gap1, gap_w = courtyard_gap(wings)
    cut_x = courtyard_cut_x(ix_min, ix_max, wings)

    apts = []
    for k in range(len(cut_x) - 1):
        cx0, cx1 = cut_x[k], cut_x[k + 1]
        # Entrance must sit in the open (non-wing-covered) part of the facade.
        e_lo = max(cx0, gap0)
        e_hi = min(cx1, gap1)
        ex = _clear((e_lo + e_hi) * 0.5, cx0, cx1, 0.9)
        entry = {'x': ex, 'y': iy_min, 'axis': 'X', 'w': DW}
        _rooms, _walls = cozy_apartment((cx0, cx1, iy_min, iy_max), entry,
                                        max_rooms=6)
        # Only the courtyard-facing stretch of the front wall may take windows;
        # the rest of the frontage hides behind a projecting wing.
        _vis_lo, _vis_hi = e_lo, e_hi
        for _r in _rooms:
            _r['facades'] = _facades(*_r['bounds'], bounds)
            if 'FRONT' in _r['facades']:
                _fx0, _fx1 = _r['facades']['FRONT']
                _fx0, _fx1 = max(_fx0, _vis_lo), min(_fx1, _vis_hi)
                if _fx1 - _fx0 >= 0.60:
                    _r['facades']['FRONT'] = (_fx0, _fx1)
                else:
                    _r['facades'].pop('FRONT', None)
        apts.append({
            'id': f'main{k + 1}',
            'rooms': _rooms,
            'entry': entry,
            'walls': _walls,
        })

    for wi, w in enumerate(wings):
        wx0, wx1, wy0, wy1 = _wing_coords(w)
        wx = (wx0 + wx1) * 0.5
        inner_x = wx1 if wi == 0 else wx0
        entry_y = (wy0 + wy1) * 0.5
        if wi == 0 and fl_idx == 0:
            # On the ground floor of the left wing, the entrance is placed on
            # the wing front gable end (wy0) to avoid being blocked by the courtyard stairs.
            w_entry = {'x': wx, 'y': wy0, 'axis': 'X', 'w': DW}
        else:
            w_entry = {'x': inner_x, 'y': entry_y, 'axis': 'Y', 'w': DW}
        _wrooms, _wwalls = cozy_apartment((wx0, wx1, wy0, wy1), w_entry, max_rooms=4)
        for _r in _wrooms:
            _r['facades'] = {}
        apts.append({
            'id': f'wing{wi + 1}',
            'rooms': _wrooms,
            'entry': w_entry,
            'walls': _wwalls,
        })
    return apts


def apartment_layout(bounds, shape, wings, props, fl_idx=None):
    """Return the apartment list for one floor of a tenement."""
    if shape == 'U_SHAPE' and wings and len(wings) >= 2:
        return courtyard_layout(bounds, wings,
                                float(getattr(props, 'wall_thickness', 0.30)),
                                fl_idx=fl_idx)
    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    return rectangle_layout(bounds, side)


def demising_walls(bounds, shape, wings, props):
    """Solid partition segments that separate distinct apartments."""
    ix_min, ix_max, iy_min, iy_max = bounds
    walls = []
    if shape == 'U_SHAPE' and wings and len(wings) >= 2:
        cut_x = courtyard_cut_x(ix_min, ix_max, wings)
        for x in cut_x[1:-1]:
            walls.append({'p1': (x, iy_min), 'p2': (x, iy_max), 'axis': 'Y', 'pos': x})
    else:
        mid = (iy_min + iy_max) * 0.5
        walls.append({'p1': (ix_min, mid), 'p2': (ix_max, mid), 'axis': 'X', 'pos': mid})
    return walls


def wing_gallery_bounds(wings):
    """Per-wing (inner_x, y_lo, y_hi) courtyard-gallery spur strips."""
    out = []
    for wi, w in enumerate(wings):
        wx0, wx1, wy0, wy1 = _wing_coords(w)
        inner_x = wx1 if wi == 0 else wx0
        out.append((inner_x, wy0, wy1))
    return out
