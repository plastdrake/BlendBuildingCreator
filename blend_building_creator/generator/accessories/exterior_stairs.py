"""Exterior timber staircase system for multi-apartment tenements.

Two clean, fully walkable routes are built here:

* **Side walkway** (rectangular row tenements): a 1.6 m gallery runs the full
  length of the chosen side wall at every upper storey.  A single switchback
  staircase sits outboard of the gallery at the front of the building - odd
  storeys climb on the inner lane, even storeys on the outer lane - so no two
  flights ever share a footprint.  Every apartment door opens straight onto the
  gallery.

* **Courtyard** (U-shaped tenements): one switchback staircase only, standing
  in the courtyard against the left wing, serving a gallery that wraps the
  courtyard facade and runs along each wing wall.  There is deliberately no
  mirrored second staircase.

The plan is computed once and shared by the geometry builder, the per-floor
door placement and the window exclusions, so stair, doors and windows can never
overlap.
"""

import math
from mathutils import Vector, Matrix
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..railing import build_railing
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_STAIRS, MAT_INDEX_TIMBER_FRAME,
)
from ..tenement import (
    GAL_D, STAIR_W, LANE_GAP, STEP_D, STEP_H,
    stair_geometry, flight_steps, courtyard_gap,
)

_RAIL_H = 0.95
_EDGE = 0.70              # wall run kept clear at each corner
_LAND_LEN = 2.50          # landing depth along the wall (2.5m wide turn-around room)
DW_HALF = 0.60            # rough entrance half-width used for railing gaps


def _stair_clearance(props):
    """Distance from the wall centreline the stair structure stands off."""
    return stair_geometry(props, type('C', (), {'found_h': 0.4, 'floor_h': 3.6}))['clearance']


def _wall_ring(props, ctx):
    """The four walls as an ordered walk around the building (base footprint)."""
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
    back = dict(name='BACK', axis='X', fixed=y_max, outward=1.0, dir=1.0,
                lo=x_min + m, hi=x_max - m)
    if side == 'RIGHT':
        return [right, back, left, front]
    return [left, back, right, front]


def _wall_point(wall, along, u):
    """World XY for a point 'along' a wall and 'u' outward from its centreline."""
    if wall['axis'] == 'Y':
        return (wall['fixed'] + wall['outward'] * u, along)
    return (along, wall['fixed'] + wall['outward'] * u)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

def _side_plan(props, ctx):
    """Side-walkway switchback plan for rectangular tenements."""
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    geom = stair_geometry(props, ctx)
    found_h, floor_h = geom['found_h'], geom['floor_h']
    clearance = geom['clearance']
    ring = _wall_ring(props, ctx)
    wall = ring[0]

    walk_lo, walk_hi = wall['lo'], wall['hi']
    min_land = max(2.20, STAIR_W + 0.10)
    flen, _ = flight_steps(found_h + floor_h)
    flen = min(flen, max(3.0, walk_span - min_land * 2.0))

    # Landings extend all the way to walk_lo and walk_hi so they align with walkway ends
    land_len = max(min_land, (walk_span - flen) * 0.5)
    stair_lo = walk_lo + land_len
    stair_hi = walk_hi - land_len

    u_deck_in = clearance
    u_deck_out = clearance + GAL_D
    u_inner = u_deck_out + LANE_GAP + STAIR_W * 0.5
    u_outer = u_inner + STAIR_W + LANE_GAP
    u_out_edge = u_outer + STAIR_W * 0.5 + 0.10

    flights = []
    for i in range(1, n_floors):
        z0 = 0.0 if i == 1 else found_h + (i - 1) * floor_h
        z1 = found_h + i * floor_h
        odd = (i % 2 == 1)
        lane_u = u_outer if odd else u_inner
        flights.append({
            'floor': i, 'lane': 'OUTER' if odd else 'INNER',
            'u': lane_u,
            'a0': stair_lo if odd else stair_hi,
            'a1': stair_hi if odd else stair_lo,
            'z0': z0, 'z1': z1,
        })

    return {
        'is_walkway': True,
        'wall': wall, 'ring': ring,
        'walk_lo': walk_lo, 'walk_hi': walk_hi, 'walk_span': walk_span,
        'stair_lo': stair_lo, 'stair_hi': stair_hi, 'flight_len': flen,
        'land_len': land_len,
        'u_deck_in': u_deck_in, 'u_deck_out': u_deck_out,
        'u_inner': u_inner, 'u_outer': u_outer, 'u_out_edge': u_out_edge,
        'flights': flights,
        'rects': [(wall['name'], None, (walk_lo - 0.20, walk_hi + 0.20))],
    }


def _courtyard_plan(props, ctx):
    """Single courtyard switchback against the left wing, with a wrap gallery."""
    wings = getattr(ctx, 'wings', [])
    if len(wings) < 2:
        return None
    wb0, wb1 = wings[0]['base'], wings[1]['base']
    # Use the wing bounds the floor planner will use (interior frame).
    gap0 = float(wb0[1])
    gap1 = float(wb1[0])
    y_attach = float(wb0[3])          # main courtyard facade (wing attach line)
    y_tip = min(float(wb0[2]), float(wb1[2]))

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    geom = stair_geometry(props, ctx)
    found_h, floor_h = geom['found_h'], geom['floor_h']

    flen, _ = flight_steps(found_h + floor_h)
    y_gal_edge = y_attach - GAL_D
    y_bot = y_gal_edge - flen
    if y_bot < y_tip + 0.40:
        y_bot = y_tip + 0.40
        flen = max(1.9, y_gal_edge - y_bot)

    u_wing_gal = GAL_D                          # spur depth off the wing wall
    x_inner = gap0 + u_wing_gal + LANE_GAP + STAIR_W * 0.5
    x_outer = x_inner + STAIR_W + LANE_GAP
    u_out_edge = x_outer + STAIR_W * 0.5 + 0.10

    flights = []
    for i in range(1, n_floors):
        z0 = 0.0 if i == 1 else found_h + (i - 1) * floor_h
        z1 = found_h + i * floor_h
        odd = (i % 2 == 1)
        flights.append({
            'floor': i, 'lane': 'INNER' if odd else 'OUTER',
            'x': x_inner if odd else x_outer,
            'a0': y_bot if odd else y_gal_edge,
            'a1': y_gal_edge if odd else y_bot,
            'z0': z0, 'z1': z1,
        })

    return {
        'is_courtyard': True,
        'gap0': gap0, 'gap1': gap1, 'gap_w': max(2.0, gap1 - gap0),
        'y_attach': y_attach, 'y_tip': y_tip,
        'y_gal_edge': y_gal_edge, 'y_bot': y_bot,
        'x_inner': x_inner, 'x_outer': x_outer,
        'u_wing_gal': u_wing_gal, 'u_out_edge': u_out_edge,
        'flight_len': flen, 'flights': flights,
        'rects': [('FRONT', None, (gap0, min(gap1, x_inner + STAIR_W * 0.5 + 0.2)))],
    }


def exterior_stair_plan(props, ctx):
    """Compute the whole exterior stair plan, or ``None`` when there is none."""
    if not getattr(props, 'has_exterior_stairs', False):
        return None
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    if n_floors < 2:
        return None
    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    shape = getattr(ctx, 'shape', getattr(props, 'building_shape', 'RECTANGLE'))
    if shape == 'U_SHAPE' or side == 'COURTYARD':
        return _courtyard_plan(props, ctx)
    return _side_plan(props, ctx)


def exterior_stairs_y_span(props, ctx):
    """Back-compat helper: (a0, a1) span on the selected side wall, or None."""
    plan = exterior_stair_plan(props, ctx)
    if not plan or not plan.get('is_walkway'):
        return None
    alen = plan.get('along_len', 2.40)
    return (plan['stair_lo'] - alen - 0.30, plan['stair_hi'] + alen + 0.30)


def exterior_stair_door_spots(props, ctx):
    """Apartment entrance positions per floor, in world coordinates.

    Pure geometry (no bm): the floor planner registers these before rooms are
    planned so a partition can never land across an apartment's single door.
    The builder re-derives the same positions afterwards.
    """
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return {}
    from ..tenement import apartment_layout, DW
    from ..shapes import compute_fl_wing_bounds

    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    wall_t = float(getattr(props, 'wall_thickness', 0.28))
    hw = float(getattr(ctx, 'base_w', 8.0)) * 0.5
    hd = float(getattr(ctx, 'base_d', 8.0)) * 0.5
    if getattr(props, 'has_cantilever', False):
        _c = float(getattr(props, 'cantilever_overhang', 0.35))
        hw += _c
        hd += _c
    bounds = (-hw + wall_t * 0.5, hw - wall_t * 0.5,
              -hd + wall_t * 0.5, hd - wall_t * 0.5)
    shape = getattr(ctx, 'shape', 'RECTANGLE')

    out = {}

    def _add(fl, x, y, axis):
        bucket = out.setdefault(fl, [])
        for prev in bucket:
            if abs(prev['x'] - x) < 0.30 and abs(prev['y'] - y) < 0.30:
                return
        bucket.append({'x': x, 'y': y, 'axis': axis, 'w': DW})

    if plan.get('is_walkway'):
        # Side-walkway flats: one door on the walkway wall per flat, every floor
        # including ground (the street door is suppressed for these presets).
        wall = plan['wall']
        for fl in range(n_floors):
            apts = apartment_layout(bounds, shape, [], props)
            for apt in apts:
                e = apt['entry']
                if wall['axis'] == 'Y':
                    _add(fl, wall['fixed'], e['y'], 'Y')
                else:
                    _add(fl, e['x'], wall['fixed'], 'X')
        return out

    # Courtyard: the wing flats own their own wall doors (built in floors.py),
    # so only the back-block flats' courtyard doors are reported here.
    fl_wings = []
    for fl in range(n_floors):
        fl_overhang = 0.0
        if getattr(props, 'has_cantilever', False) and fl >= 1:
            fl_overhang = float(getattr(props, 'cantilever_overhang', 0.0))
        fl_wings = [compute_fl_wing_bounds(w, fl, fl_overhang,
                                           -hw, hw, -hd, hd)
                    for w in getattr(ctx, 'wings', [])]
        if len(fl_wings) < 2:
            continue
        apts = apartment_layout(bounds, shape, fl_wings, props)
        for apt in apts:
            if apt['id'].startswith('main'):
                e = apt['entry']
                if fl == 0:
                    continue  # ground doors are built by floors.py
                _add(fl, e['x'], bounds[2], 'X')
    return out


# ---------------------------------------------------------------------------
# Geometry builders
# ---------------------------------------------------------------------------

def _build_side_flight(bm, wall, a0, a1, z0, z1, u_cx, stair_w):
    """Straight flight along a wall at ``u_cx``, climbing ``z0`` -> ``z1``."""
    sgn = 1.0 if (a1 - a0) > 0 else -1.0
    span = a1 - a0
    rise = z1 - z0
    n = max(3, int(math.ceil(abs(rise) / STEP_H)))
    step_h = rise / n
    step_d = span / n
    for i in range(n):
        a = a0 + step_d * (i + 0.5)
        sz = z0 + (i + 0.5) * step_h
        cx, cy = _wall_point(wall, a, u_cx)
        if wall['axis'] == 'Y':
            create_beveled_box(bm, size=(stair_w, abs(step_d) + 0.03, 0.06),
                               location=(cx, cy, sz), mat_index=MAT_INDEX_WOOD,
                               bevel_amount=0.010)
            rx, ry = _wall_point(wall, a - step_d * 0.5 + 0.02 * sgn, u_cx)
            create_box(bm, size=(stair_w - 0.02, 0.04, abs(step_h)),
                       location=(rx, ry, sz - step_h * 0.5),
                       mat_index=MAT_INDEX_STAIRS)
        else:
            create_beveled_box(bm, size=(abs(step_d) + 0.03, stair_w, 0.06),
                               location=(cx, cy, sz), mat_index=MAT_INDEX_WOOD,
                               bevel_amount=0.010)
            rx, ry = _wall_point(wall, a - step_d * 0.5 + 0.02 * sgn, u_cx)
            create_box(bm, size=(0.04, stair_w - 0.02, abs(step_h)),
                       location=(rx, ry, sz - step_h * 0.5),
                       mat_index=MAT_INDEX_STAIRS)

    # Stringers under both edges
    run = abs(span)
    diag = math.hypot(run, abs(rise))
    pitch = math.atan2(abs(rise), run)
    for side in (-1, 1):
        u_str = u_cx + side * (stair_w * 0.5 + 0.05)
        sx, sy = _wall_point(wall, (a0 + a1) * 0.5, u_str)
        if wall['axis'] == 'Y':
            rot = (pitch * sgn, 0.0, 0.0)
            size = (0.09, diag, 0.20)
        else:
            rot = (0.0, -pitch * sgn, 0.0)
            size = (diag, 0.09, 0.20)
        create_box(bm, size=size, location=(sx, sy, (z0 + z1) * 0.5),
                   rotation=rot, mat_index=MAT_INDEX_TIMBER)

    # Handrails along both sides of the flight
    for side in (-1, 1):
        u_rail = u_cx + side * (stair_w * 0.5 - 0.04)
        p0 = _wall_point(wall, a0 + 0.12 * sgn, u_rail)
        p1 = _wall_point(wall, a1 - 0.12 * sgn, u_rail)
        build_railing(bm, p0, p1, z0 + 0.06, height=_RAIL_H,
                      base_z_end=z1 + 0.06, post_spacing=1.1,
                      baluster_spacing=0.24, braces=False)


def _build_side_landing(bm, wall, a_lo, a_hi, z, u_deck_out, u_out_edge,
                        facing_side, is_top=False, active_lane='OUTER',
                        u_inner=None, u_outer=None, stair_w=STAIR_W):
    """A turn landing platform bridging between the gallery walkway and stair flights.

    The landing sits OUTBOARD of the gallery walkway deck (from u_deck_out to u_out_edge)
    so there is ZERO coplanar overlap with the gallery deck slab.
    """
    if z <= 0.01:
        return
    along_span = abs(a_hi - a_lo)
    a_center = (a_lo + a_hi) * 0.5
    u_cx = (u_deck_out + u_out_edge) * 0.5
    depth = u_out_edge - u_deck_out

    # Deck slab
    lx, ly = _wall_point(wall, a_center, u_cx)
    if wall['axis'] == 'Y':
        size = (depth, along_span, 0.07)
    else:
        size = (along_span, depth, 0.07)
    create_beveled_box(bm, size=size, location=(lx, ly, z + 0.035),
                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

    # Rim fascia under outer edge (centered at u_out_edge - 0.08 so outer face is flush with u_out_edge)
    fx, fy = _wall_point(wall, a_center, u_out_edge - 0.08)
    if wall['axis'] == 'Y':
        create_box(bm, size=(0.16, along_span, 0.20), location=(fx, fy, z - 0.10),
                   mat_index=MAT_INDEX_TIMBER)
    else:
        create_box(bm, size=(along_span, 0.16, 0.20), location=(fx, fy, z - 0.10),
                   mat_index=MAT_INDEX_TIMBER)

    # Rim beam under far end (away from stairs)
    far_beam_a = (a_hi - 0.08) if facing_side == -1 else (a_lo + 0.08)
    ex, ey = _wall_point(wall, far_beam_a, u_cx)
    if wall['axis'] == 'Y':
        create_box(bm, size=(depth, 0.16, 0.20), location=(ex, ey, z - 0.10),
                   mat_index=MAT_INDEX_TIMBER)
    else:
        create_box(bm, size=(0.16, depth, 0.20), location=(ex, ey, z - 0.10),
                   mat_index=MAT_INDEX_TIMBER)

    base_z = z + 0.07

    # 1. Outer railing overlooking yard
    r0 = _wall_point(wall, a_lo + 0.06, u_out_edge - 0.06)
    r1 = _wall_point(wall, a_hi - 0.06, u_out_edge - 0.06)
    build_railing(bm, r0, r1, base_z, height=_RAIL_H,
                  post_spacing=1.2, baluster_spacing=0.24, braces=False)

    # 2. Far end-cap railing (away from stairs)
    # Aligns perfectly with the walkway end cap at the exact same along coordinate
    far_a = (a_hi - 0.06) if facing_side == -1 else (a_lo + 0.06)
    c0 = _wall_point(wall, far_a, u_deck_out - 0.04)
    c1 = _wall_point(wall, far_a, u_out_edge - 0.06)
    build_railing(bm, c0, c1, base_z, height=_RAIL_H,
                  post_spacing=1.4, baluster_spacing=0.24, braces=False)

    # 3. Near end facing stairs:
    # If this is the top floor, guard the inactive lane void so nobody falls off
    if is_top and u_inner is not None and u_outer is not None:
        near_a = (a_lo + 0.06) if facing_side == -1 else (a_hi - 0.06)
        if active_lane == 'OUTER':
            # Arrived via outer lane; guard inner lane edge
            ic0 = _wall_point(wall, near_a, u_deck_out + 0.04)
            ic1 = _wall_point(wall, near_a, u_inner + stair_w * 0.5 - 0.05)
            build_railing(bm, ic0, ic1, base_z, height=_RAIL_H,
                          post_spacing=1.2, baluster_spacing=0.24, braces=False)
        else:
            # Arrived via inner lane; guard outer lane edge
            ic0 = _wall_point(wall, near_a, u_outer - stair_w * 0.5 + 0.05)
            ic1 = _wall_point(wall, near_a, u_out_edge - 0.06)
            build_railing(bm, ic0, ic1, base_z, height=_RAIL_H,
                          post_spacing=1.2, baluster_spacing=0.24, braces=False)


def _build_side_stairs(bm, props, ctx, plan):
    wall = plan['wall']
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    geom = stair_geometry(props, ctx)
    found_h, floor_h = geom['found_h'], geom['floor_h']
    walk_lo, walk_hi = plan['walk_lo'], plan['walk_hi']
    u_deck_in, u_deck_out = plan['u_deck_in'], plan['u_deck_out']
    u_inner, u_outer = plan['u_inner'], plan['u_outer']
    u_out_edge = plan['u_out_edge']
    stair_lo, stair_hi = plan['stair_lo'], plan['stair_hi']

    walk_len = walk_hi - walk_lo
    deck_cx_along = (walk_lo + walk_hi) * 0.5
    top_z = found_h + (n_floors - 1) * floor_h

    # Support posts under outer corners of landings, sized up to the actual highest landing level
    high_floors = [fl for fl in range(1, n_floors) if fl % 2 == 1]
    low_floors = [fl for fl in range(1, n_floors) if fl % 2 == 0]
    max_z_high = (found_h + max(high_floors) * floor_h) if high_floors else 0.0
    max_z_low = (found_h + max(low_floors) * floor_h) if low_floors else 0.0

    if max_z_low > 0.1:
        for pa in (walk_lo + 0.08, stair_lo - 0.12):
            px, py = _wall_point(wall, pa, u_out_edge - 0.08)
            create_beveled_box(bm, size=(0.16, 0.16, max_z_low),
                               location=(px, py, max_z_low * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

    if max_z_high > 0.1:
        for pa in (stair_hi + 0.12, walk_hi - 0.08):
            px, py = _wall_point(wall, pa, u_out_edge - 0.08)
            create_beveled_box(bm, size=(0.16, 0.16, max_z_high),
                               location=(px, py, max_z_high * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

    # Support posts under the gallery deck (at u_deck_out - 0.08)
    n_posts = max(2, int(math.ceil(walk_len / 2.4)))
    for k in range(n_posts):
        pa = walk_lo + walk_len * k / (n_posts - 1)
        # Avoid blocking doorways to landings
        if (stair_hi - 0.20 <= pa <= walk_hi - 0.30) or \
           (walk_lo + 0.30 <= pa <= stair_lo + 0.20):
            continue
        px, py = _wall_point(wall, pa, u_deck_out - 0.08)
        create_beveled_box(bm, size=(0.16, 0.16, top_z),
                           location=(px, py, top_z * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

    # Upper storeys: gallery decks, rim beams, railings, and turn landings
    for fl_idx in range(1, n_floors):
        zw = found_h + fl_idx * floor_h
        odd = (fl_idx % 2 == 1)
        is_top = (fl_idx == n_floors - 1)

        # 1. Gallery deck (runs full walk_len, from u_deck_in to u_deck_out)
        dcx, dcy = _wall_point(wall, deck_cx_along, (u_deck_in + u_deck_out) * 0.5)
        gal_depth = u_deck_out - u_deck_in
        if wall['axis'] == 'Y':
            dsize = (gal_depth, walk_len, 0.07)
        else:
            dsize = (walk_len, gal_depth, 0.07)
        create_beveled_box(bm, size=dsize, location=(dcx, dcy, zw + 0.035),
                           mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

        # Ledger + fascia beams under the gallery deck:
        # Ledger beam against the wall (outer face flush with wall at u_deck_in):
        lx, ly = _wall_point(wall, deck_cx_along, u_deck_in + 0.08)
        # Fascia beam under outer gallery edge (outer face flush with u_deck_out):
        fx, fy = _wall_point(wall, deck_cx_along, u_deck_out - 0.08)
        if wall['axis'] == 'Y':
            create_box(bm, size=(0.16, walk_len, 0.20), location=(lx, ly, zw - 0.10),
                       mat_index=MAT_INDEX_TIMBER)
            create_box(bm, size=(0.16, walk_len, 0.20), location=(fx, fy, zw - 0.10),
                       mat_index=MAT_INDEX_TIMBER)
        else:
            create_box(bm, size=(walk_len, 0.16, 0.20), location=(lx, ly, zw - 0.10),
                       mat_index=MAT_INDEX_TIMBER)
            create_box(bm, size=(walk_len, 0.16, 0.20), location=(fx, fy, zw - 0.10),
                       mat_index=MAT_INDEX_TIMBER)

        # End rim beams under the walkway deck at walk_lo and walk_hi ("the ends are missing beams"):
        for end_a, sgn_end in [(walk_lo, 1.0), (walk_hi, -1.0)]:
            bx, by = _wall_point(wall, end_a + 0.08 * sgn_end, (u_deck_in + u_deck_out) * 0.5)
            if wall['axis'] == 'Y':
                create_box(bm, size=(gal_depth, 0.16, 0.20), location=(bx, by, zw - 0.10),
                           mat_index=MAT_INDEX_TIMBER)
            else:
                create_box(bm, size=(0.16, gal_depth, 0.20), location=(bx, by, zw - 0.10),
                           mat_index=MAT_INDEX_TIMBER)

        # Determine active landing for this floor:
        # High landing at [stair_hi, walk_hi] on odd floors
        # Low landing at [walk_lo, stair_lo] on even floors
        if odd:
            land_lo = stair_hi
            land_hi = walk_hi
            facing_side = -1  # flights connect at land_lo
            active_lane = 'OUTER'
        else:
            land_lo = walk_lo
            land_hi = stair_lo
            facing_side = +1  # flights connect at land_hi
            active_lane = 'INNER'

        # End caps for the gallery deck at walk_lo and walk_hi:
        # Both end caps sit at walk_lo + 0.06 and walk_hi - 0.06.
        # At the active landing end, this segment perfectly connects to the landing end cap!
        for end_a, sgn_end in [(walk_lo, 1.0), (walk_hi, -1.0)]:
            cap0 = _wall_point(wall, end_a + 0.06 * sgn_end, u_deck_in + 0.04)
            cap1 = _wall_point(wall, end_a + 0.06 * sgn_end, u_deck_out - 0.04)
            build_railing(bm, cap0, cap1, zw + 0.07, height=_RAIL_H,
                          post_spacing=1.4, baluster_spacing=0.24, braces=False)

        # Outer gallery railing along u_deck_out - 0.06, with a gap for the landing opening
        if wall['axis'] == 'Y':
            fixed_gal_rail = wall['fixed'] + wall['outward'] * (u_deck_out - 0.06)
            _rail_gapped(bm, 'Y', fixed_gal_rail, walk_lo + 0.10, walk_hi - 0.10,
                         [(land_lo, land_hi)], zw + 0.07, spacing=1.2)
        else:
            fixed_gal_rail = wall['fixed'] + wall['outward'] * (u_deck_out - 0.06)
            _rail_gapped(bm, 'X', fixed_gal_rail, walk_lo + 0.10, walk_hi - 0.10,
                         [(land_lo, land_hi)], zw + 0.07, spacing=1.2)

        # Turn landing platform outboard of the gallery (zero overlap with gallery deck)
        _build_side_landing(bm, wall, land_lo, land_hi, zw, u_deck_out, u_out_edge,
                            facing_side=facing_side, is_top=is_top,
                            active_lane=active_lane, u_inner=u_inner,
                            u_outer=u_outer, stair_w=STAIR_W)

    # 3. Flights (straight flights on separate outer and inner lanes)
    for f in plan['flights']:
        zw0 = 0.0 if f['floor'] == 1 else found_h + (f['floor'] - 1) * floor_h
        zw1 = found_h + f['floor'] * floor_h
        _build_side_flight(bm, wall, f['a0'], f['a1'], zw0, zw1, f['u'], STAIR_W)


def _build_courtyard_flight(bm, x_cx, y0, y1, z0, z1, stair_w):
    """Straight flight running along Y at a fixed X (courtyard lanes)."""
    sgn = 1.0 if (y1 - y0) > 0 else -1.0
    y0e = y0 - 0.18 * sgn
    y1e = y1 + 0.18 * sgn
    span = y1e - y0e
    rise = z1 - z0
    n = max(3, int(math.ceil(abs(rise) / STEP_H)))
    step_h = rise / n
    step_d = span / n
    for i in range(n):
        y = y0e + step_d * (i + 0.5)
        sz = z0 + (i + 0.5) * step_h
        create_beveled_box(bm, size=(stair_w, abs(step_d) + 0.03, 0.06),
                           location=(x_cx, y, sz), mat_index=MAT_INDEX_WOOD,
                           bevel_amount=0.010)
        create_box(bm, size=(stair_w - 0.02, 0.04, abs(step_h)),
                   location=(x_cx, y - step_d * 0.5 + 0.02 * sgn, sz - step_h * 0.5),
                   mat_index=MAT_INDEX_STAIRS)
    if z0 <= 0.45:
        create_beveled_box(
            bm, size=(stair_w + 0.16, 0.28, 0.08),
            location=(x_cx, y0e + 0.05 * sgn, z0 + 0.04),
            mat_index=MAT_INDEX_STAIRS, bevel_amount=0.012
        )
    run = abs(span)
    diag = math.hypot(run, abs(rise))
    pitch = math.atan2(abs(rise), run)
    rot = (pitch, 0.0, 0.0) if sgn > 0 else (pitch, 0.0, math.pi)
    for side in (-1, 1):
        create_box(bm, size=(0.09, diag, 0.20),
                   location=(x_cx + side * (stair_w * 0.5 + 0.05),
                             (y0e + y1e) * 0.5, (z0 + z1) * 0.5),
                   rotation=rot, mat_index=MAT_INDEX_TIMBER)
    for side in (-1, 1):
        u_rail = x_cx + side * (stair_w * 0.5 + 0.05)
        build_railing(bm, (u_rail, y0e + 0.10 * sgn), (u_rail, y1e - 0.30 * sgn),
                      z0 + 0.06, height=_RAIL_H, base_z_end=z1 + 0.06,
                      post_spacing=1.1, baluster_spacing=0.24, braces=False)


def _build_courtyard_deck(bm, x0, x1, y0, y1, z, mat=MAT_INDEX_WOOD, thick=0.07):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    if dx < 0.05 or dy < 0.05:
        return
    create_beveled_box(bm, size=(dx, dy, thick),
                       location=((x0 + x1) * 0.5, (y0 + y1) * 0.5, z + thick * 0.5),
                       mat_index=mat, bevel_amount=0.010)
    # Ledger/fascia under the long edges - exact size without overlap to prevent coplanar z-fighting
    if dx >= dy:
        create_box(bm, size=(dx, 0.16, 0.22),
                   location=((x0 + x1) * 0.5, min(y0, y1) + 0.08, z - 0.11),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(dx, 0.16, 0.22),
                   location=((x0 + x1) * 0.5, max(y0, y1) - 0.08, z - 0.11),
                   mat_index=MAT_INDEX_TIMBER)
    else:
        create_box(bm, size=(0.16, dy, 0.22),
                   location=(min(x0, x1) + 0.08, (y0 + y1) * 0.5, z - 0.11),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(0.16, dy, 0.22),
                   location=(max(x0, x1) - 0.08, (y0 + y1) * 0.5, z - 0.11),
                   mat_index=MAT_INDEX_TIMBER)


def _rail_gapped(bm, axis, fixed, lo, hi, gaps, z, spacing=1.2):
    """A railing along an axis-aligned line, skipping the listed gaps."""
    segs = [(min(lo, hi), max(lo, hi))]
    for g0, g1 in gaps:
        g0, g1 = min(g0, g1), max(g0, g1)
        nxt = []
        for s0, s1 in segs:
            if g1 <= s0 or g0 >= s1:
                nxt.append((s0, s1))
                continue
            if g0 - s0 > 0.25:
                nxt.append((s0, g0))
            if s1 - g1 > 0.25:
                nxt.append((g1, s1))
        segs = nxt
    for s0, s1 in segs:
        if s1 - s0 < 0.25:
            continue
        p0 = (s0, fixed) if axis == 'X' else (fixed, s0)
        p1 = (s1, fixed) if axis == 'X' else (fixed, s1)
        build_railing(bm, p0, p1, z, height=_RAIL_H, post_spacing=spacing,
                      baluster_spacing=0.24, braces=False)


def _build_courtyard_landing(bm, plan, gap0, u_out_edge, y_bot, z, abut_hi=False,
                             ground=False):
    """Turn platform at y_bot bridging the courtyard lanes and the left-wing gallery."""
    if ground or z <= 0.01:
        return
    along_len = _LAND_LEN
    x0 = gap0 + plan['u_wing_gal']
    x1 = u_out_edge
    y_lo = y_bot - along_len
    y_hi = y_bot

    # Build turn platform deck cleanly in front of the stair run (from y_lo to y_bot)
    _build_courtyard_deck(bm, x0, x1, y_lo, y_hi, z)
    base_z = z + 0.07

    # Outer perimeter railings only:
    # 1. Outer right edge (X = x1 - 0.06)
    build_railing(bm, (x1 - 0.06, y_lo + 0.06), (x1 - 0.06, y_hi - 0.06), base_z,
                  height=_RAIL_H, post_spacing=1.2, baluster_spacing=0.24, braces=False)

    # 2. Front outer edge (Y = y_lo + 0.06) from left wing edge x0 to outer edge x1
    build_railing(bm, (x0, y_lo + 0.06), (x1 - 0.06, y_lo + 0.06), base_z,
                  height=_RAIL_H, post_spacing=1.4, baluster_spacing=0.24, braces=False)

    # 3. Back edge (Y = y_hi - 0.06 = y_bot - 0.06):
    # The stairs attach between (x_inner - STAIR_W * 0.5) and x1.
    # That region MUST stay 100% open so stairs are completely walkable!
    # If there is a small gap between x0 and the inner stair edge, close it with safety rail:
    stair_x_start = plan['x_inner'] - STAIR_W * 0.5
    if stair_x_start - x0 > 0.35:
        build_railing(bm, (x0, y_hi - 0.06), (stair_x_start, y_hi - 0.06), base_z,
                      height=_RAIL_H, post_spacing=1.2, baluster_spacing=0.24, braces=False)

    # Note: Left edge (X = x0) is 100% OPEN so people walk freely between the
    # Left Wing walkway and the landing!

    # Support posts under landing:
    if z > 0.01:
        for px in (x0 + 0.14, x1 - 0.14):
            for py in (y_lo + 0.14, y_hi - 0.14):
                create_beveled_box(bm, size=(0.18, 0.18, z),
                                   location=(px, py, z * 0.5),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)


def _build_courtyard_stairs(bm, props, ctx, plan, tier='TIER_1'):
    wings = getattr(ctx, 'wings', [])
    if len(wings) < 2:
        return
    n_floors = max(1, int(getattr(props, 'num_floors', 2)))
    geom = stair_geometry(props, ctx)
    found_h, floor_h = geom['found_h'], geom['floor_h']
    gap0, gap1 = plan['gap0'], plan['gap1']
    y_attach, y_gal_edge, y_bot = plan['y_attach'], plan['y_gal_edge'], plan['y_bot']
    x_inner, x_outer, u_out_edge = plan['x_inner'], plan['x_outer'], plan['u_out_edge']
    sg = plan['u_wing_gal']

    # Wing inner-wall geometry: the spurs run the wing's full depth so every
    # turn landing is reachable, and the wing doors sit in the front kitchen.
    wing_info = []
    for wi, w in enumerate(wings):
        wx0, wx1, wy0, wy1 = (float(w['base'][0]), float(w['base'][1]),
                              float(w['base'][2]), float(w['base'][3]))
        inner_x = wx1 if wi == 0 else wx0
        e_y = wy0 + max(1.3, (wy1 - wy0) * 0.26)
        sx0, sx1 = (inner_x, inner_x + sg) if wi == 0 else (inner_x - sg, inner_x)
        wing_info.append({'inner_x': inner_x, 'tip': wy0, 'attach': wy1,
                          'e_y': e_y, 'sx0': sx0, 'sx1': sx1})

    left, right = wing_info[0], wing_info[1]
    top_z = found_h + (n_floors - 1) * floor_h

    # Support posts around the wrap gallery / landings (placed on outside corners, never blocking paths).
    # Note: intermediate turn landings create their own support posts sized up to landing level z.
    # We do NOT create full-height posts for the landing here to prevent them from shooting through upper stairs.
    landing_lo = gap0 + sg
    post_spots = [
        (left['sx0'] + 0.16, y_attach - 0.20),
        (right['sx1'] - 0.16, y_attach - 0.20),
        (gap0 + sg + 0.16, y_gal_edge - 0.18),
        (gap1 - sg - 0.16, y_gal_edge - 0.18),
        (left['sx0'] + 0.16, left['tip'] + 0.20),
        (right['sx1'] - 0.16, right['tip'] + 0.20),
    ]
    for px, py in post_spots:
        create_beveled_box(bm, size=(0.18, 0.18, top_z),
                           location=(px, py, top_z * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

    for fl_idx in range(1, n_floors):
        zw = found_h + fl_idx * floor_h
        odd = (fl_idx % 2 == 1)

        # Decks: main facade strip between the spurs, plus full-depth spurs.
        # Cleanly abutted at gap0 + sg and gap1 - sg with zero coplanar overlap!
        _build_courtyard_deck(bm, gap0 + sg, gap1 - sg, y_gal_edge, y_attach, zw)
        _build_courtyard_deck(bm, left['sx0'], left['sx1'], left['tip'], y_attach, zw)
        _build_courtyard_deck(bm, right['sx0'], right['sx1'], right['tip'], y_attach, zw)

        # 1. Left spur outer railing:
        # Runs along X = left['sx1'] - 0.06.
        # CRITICAL: stops at y_gal_edge - 0.06 so the 2.5m walkway into the Main Gallery is 100% UNBLOCKED!
        # On even floors (e.g. Floor 2), open the passage where the turn landing connects at y_bot:
        left_gaps = []
        if not odd:
            left_gaps.append((y_bot - _LAND_LEN - 0.10, y_bot + 0.10))
        _rail_gapped(bm, 'Y', left['sx1'] - 0.06, left['tip'] + 0.06, y_gal_edge - 0.06,
                     left_gaps, zw + 0.07)

        # 2. Right spur outer railing:
        # Runs along X = right['sx0'] + 0.06 from tip up to y_gal_edge - 0.06.
        # CRITICAL: stops at y_gal_edge - 0.06 so the 2.5m corner into the Main Gallery is 100% UNBLOCKED!
        _rail_gapped(bm, 'Y', right['sx0'] + 0.06, right['tip'] + 0.06,
                     y_gal_edge - 0.06, [], zw + 0.07)

        # 3. Wing-tip end caps:
        for wf in wing_info:
            _rail_gapped(bm, 'X', wf['tip'] + 0.06, wf['sx0'] + 0.04, wf['sx1'] - 0.04, [], zw + 0.07)

        # 4. Main facade outer railing along Y = y_gal_edge - 0.06:
        # On odd floors, leave clear openings for the stairs arriving at x_inner and departing at x_outer:
        main_gaps = []
        if odd:
            half_open = STAIR_W * 0.5 + 0.15
            main_gaps.append((x_inner - half_open, x_inner + half_open))
            if fl_idx < n_floors - 1:
                main_gaps.append((x_outer - half_open, x_outer + half_open))
        _rail_gapped(bm, 'X', y_gal_edge - 0.06, gap0 + sg, gap1 - sg,
                     main_gaps, zw + 0.07)

        # 5. Turn landing at y_bot for even storeys (e.g. Floor 2):
        if not odd:
            _build_courtyard_landing(bm, plan, gap0, u_out_edge, y_bot, zw,
                                     abut_hi=False, ground=False)

    # NO ground pad/platform at floor level (z=0)! (per user request)

    for f in plan['flights']:
        _build_courtyard_flight(bm, f['x'], f['a0'], f['a1'], f['z0'], f['z1'], STAIR_W)


def build_exterior_stairs(bm, props, ctx, tier='TIER_1'):
    """Build the planned external stair (flights + a landing per storey)."""
    plan = exterior_stair_plan(props, ctx)
    if not plan:
        return
    if plan.get('is_courtyard'):
        _build_courtyard_stairs(bm, props, ctx, plan, tier)
        return
    _build_side_stairs(bm, props, ctx, plan)
