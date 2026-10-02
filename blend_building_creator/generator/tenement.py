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
GAL_D = 2.50      # clear walkway / courtyard-gallery depth (2.5m wide walkways)
STAIR_W = 1.50    # single stair lane clear width (comfortably walkable)
LANE_GAP = 0.20   # air gap between the two switchback lanes
STEP_D = 0.28     # tread depth
STEP_H = 0.19     # riser height cap

DW = 1.20         # apartment entrance door width
DWI = 1.15        # internal room doorway width


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

def rectangle_layout(bounds, side):
    """Two small flats stacked along the depth of a side-walkway tenement.

    ``side`` is the exterior walkway wall (``LEFT``/``RIGHT``); every flat's one
    entrance sits on that wall.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    apts = []
    for k in range(2):
        ay0 = iy_min + D * k / 2.0
        ay1 = iy_min + D * (k + 1) / 2.0
        if W >= 6.8:
            # Wide enough to split across the width: kitchen on the walkway
            # side, private bedroom away from the street.
            ax = _clear((ix_min + ix_max) * 0.5, ix_min, ix_max, 2.6)
            if side == 'RIGHT':
                k_b = (ax, ix_max, ay0, ay1)
                b_b = (ix_min, ax, ay0, ay1)
            else:
                k_b = (ix_min, ax, ay0, ay1)
                b_b = (ax, ix_max, ay0, ay1)
            entry_y = (ay0 + ay1) * 0.5
            walls = [{'p1': (ax, ay0), 'p2': (ax, ay1), 'axis': 'Y', 'pos': ax,
                      'doorway': {'x': ax, 'y': entry_y, 'axis': 'Y', 'w': DWI}}]
        else:
            # Narrow deep plot: split along the depth so neither room becomes a
            # corridor sliver.  Kitchen/living at the front, bedroom behind.
            my = ay0 + (ay1 - ay0) * 0.56
            k_b = (ix_min, ix_max, ay0, my)
            b_b = (ix_min, ix_max, my, ay1)
            entry_y = ay0 + (ay1 - ay0) * 0.30
            walls = [{'p1': (ix_min, my), 'p2': (ix_max, my), 'axis': 'X', 'pos': my,
                      'doorway': {'x': (ix_min + ix_max) * 0.5, 'y': my,
                                  'axis': 'X', 'w': DWI}}]
        ex = ix_max if side == 'RIGHT' else ix_min
        rooms = [
            {'role': 'TENEMENT_KITCHEN', 'bounds': k_b,
             'facades': _facades(*k_b, bounds)},
            {'role': 'TENEMENT_BEDROOM', 'bounds': b_b,
             'facades': _facades(*b_b, bounds)},
        ]
        apts.append({
            'id': f'flat{k + 1}',
            'rooms': rooms,
            'entry': {'x': ex, 'y': entry_y, 'axis': 'Y', 'w': DW},
            'walls': walls,
        })
    return apts


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
    k_main = int(_clamp(round(gap_w / 4.6), 2, 4))
    cut = [gap0 + gap_w * i / k_main for i in range(k_main + 1)]
    cut[0] = ix_min
    cut[-1] = ix_max
    return cut


def courtyard_layout(bounds, wings, wall_t=0.30, fl_idx=None):
    """Small courtyard flats plus one two-room flat per projecting wing."""
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
        my = iy_min + D * 0.54
        k_b = (cx0, cx1, iy_min, my)
        b_b = (cx0, cx1, my, iy_max)
        k_facades = _facades(*k_b, bounds)
        if e_hi > e_lo + 0.3:
            k_facades['FRONT'] = (e_lo, e_hi)
        else:
            k_facades.pop('FRONT', None)
        b_facades = _facades(*b_b, bounds)
        apts.append({
            'id': f'main{k + 1}',
            'rooms': [
                {'role': 'TENEMENT_KITCHEN', 'bounds': k_b,
                 'facades': k_facades},
                {'role': 'TENEMENT_BEDROOM', 'bounds': b_b,
                 'facades': b_facades},
            ],
            'entry': {'x': ex, 'y': iy_min, 'axis': 'X', 'w': DW},
            'walls': [{'p1': (cx0, my), 'p2': (cx1, my), 'axis': 'X', 'pos': my,
                       'doorway': {'x': (cx0 + cx1) * 0.5, 'y': my,
                                   'axis': 'X', 'w': DWI}}],
        })

    for wi, w in enumerate(wings):
        wx0, wx1, wy0, wy1 = _wing_coords(w)
        wx = (wx0 + wx1) * 0.5
        inner_x = wx1 if wi == 0 else wx0
        wdepth = wy1 - wy0
        my = wy0 + wdepth * 0.54
        entry_y = (wy0 + my) * 0.5
        k_b = (wx0, wx1, wy0, my)
        b_b = (wx0, wx1, my, wy1)
        if wi == 0 and fl_idx == 0:
            # On the ground floor of the left wing, the entrance is placed on
            # the wing front gable end (wy0) to avoid being blocked by the courtyard stairs.
            w_entry = {'x': wx, 'y': wy0, 'axis': 'X', 'w': DW}
        else:
            w_entry = {'x': inner_x, 'y': entry_y, 'axis': 'Y', 'w': DW}
        apts.append({
            'id': f'wing{wi + 1}',
            'rooms': [
                {'role': 'TENEMENT_KITCHEN', 'bounds': k_b,
                 'facades': {}},
                {'role': 'TENEMENT_BEDROOM', 'bounds': b_b,
                 'facades': {}},
            ],
            'entry': w_entry,
            'walls': [{'p1': (wx0, my), 'p2': (wx1, my), 'axis': 'X', 'pos': my,
                       'doorway': {'x': wx, 'y': my, 'axis': 'X', 'w': DWI}}],
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
