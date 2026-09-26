"""Construction scaffold kit (SOLID / DRY).

Builds a timber pole scaffold around the current building so any footprint
reads as "under construction", plus optional staged material piles and a
yard crane. Reuses only generic builders (mesh_utils, crane, furniture,
warehouse) - no duplicated prop code.

Plot contract (from the user):
- SMALL 12x12, MEDIUM 20x20, LARGE 40x40, HUGE 100x100.
- The scaffold never fills the whole plot: ``padding`` metres of walkway are
  left clear around it (default 1.5 m, clamp 0.5-3.0 m).
- AUTO sizes the scaffold to the building itself plus a work margin.
"""

import math
import random

from ..mesh_utils import create_beveled_box, create_box, create_cylinder
from ..materials import (
    MAT_INDEX_TIMBER,
    MAT_INDEX_WOOD,
    MAT_INDEX_ROPE,
    MAT_INDEX_TARP,
    MAT_INDEX_CUT_STONE,
    MAT_INDEX_IRON,
)

PLOT_SIZES = {
    'SMALL': 12.0,
    'MEDIUM': 20.0,
    'LARGE': 40.0,
    'HUGE': 100.0,
}

# Dressing scale per plot (DRY): bigger sites read busier with no extra
# properties to learn. Small sites stay quiet; huge sites get full yards.
LADDER_COUNT = {'AUTO': 1, 'SMALL': 1, 'MEDIUM': 2, 'LARGE': 3, 'HUGE': 4}
CRANES_INSIDE = {'AUTO': 0, 'SMALL': 0, 'MEDIUM': 0, 'LARGE': 1, 'HUGE': 2}
PILE_TIER = {'AUTO': 0, 'SMALL': 0, 'MEDIUM': 1, 'LARGE': 2, 'HUGE': 3}


def scaffold_extents(plot_key, padding, bldg_w, bldg_d):
    """Return (sx, sy) scaffold footprint for the plot, honouring padding.

    Target is ``plot - 2 * padding``. The scaffold always encloses the
    building plus a 1.2 m work margin, but never exceeds ``plot - 0.5`` so
    at least a half-metre walkway survives even on oversized buildings.
    """
    pad = min(3.0, max(0.5, float(padding)))
    if plot_key in PLOT_SIZES:
        plot = PLOT_SIZES[plot_key]
        target = plot - 2.0 * pad
        need_w = float(bldg_w) + 1.2
        need_d = float(bldg_d) + 1.2
        sx = max(target, need_w)
        sy = max(target, need_d)
        cap = plot - 0.5
        return min(sx, cap), min(sy, cap)
    # AUTO: just wrap the building with a work margin.
    return float(bldg_w) + 2.4, float(bldg_d) + 2.4


def _rng(seed, salt=0):
    return random.Random((int(seed) * 73856093 ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _pole(bm, x, y, h, r=0.06):
    create_cylinder(
        bm, radius=r, height=h, segments=8,
        location=(x, y, h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
    )


def _ledger(bm, x1, y1, x2, y2, z, thick=0.09):
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    ang = math.atan2(dy, dx)
    create_beveled_box(
        bm, size=(length, thick, thick),
        location=((x1 + x2) * 0.5, (y1 + y2) * 0.5, z),
        rotation=(0.0, 0.0, ang),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
    )


def _platform(bm, x0, x1, y0, y1, z, plank_w=0.28):
    w = abs(x1 - x0)
    d = abs(y1 - y0)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    if w >= d:
        n = max(2, int(round(d / plank_w)))
        for i in range(n):
            py = y0 + (i + 0.5) * d / n
            create_beveled_box(
                bm, size=(w, d / n - 0.02, 0.05),
                location=(cx, py, z),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
            )
    else:
        n = max(2, int(round(w / plank_w)))
        for i in range(n):
            px = x0 + (i + 0.5) * w / n
            create_beveled_box(
                bm, size=(w / n - 0.02, d, 0.05),
                location=(px, cy, z),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
            )


def _diagonal(bm, x1, y1, x2, y2, z0, z1, thick=0.07):
    dx, dy, dz = x2 - x1, y2 - y1, z1 - z0
    horiz = math.hypot(dx, dy)
    length = math.hypot(horiz, dz)
    if length < 1e-6:
        return
    ang_z = math.atan2(dy, dx)
    ang_y = math.atan2(dz, horiz)
    create_beveled_box(
        bm, size=(length, thick, thick),
        location=((x1 + x2) * 0.5, (y1 + y2) * 0.5, (z0 + z1) * 0.5),
        rotation=(0.0, -ang_y, ang_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006,
    )


def _rope_lashing(bm, x, y, z):
    create_cylinder(
        bm, radius=0.035, height=0.10, segments=8,
        location=(x, y, z),
        mat_index=MAT_INDEX_ROPE,
    )


def _leaning_ladder(bm, x, y_edge, z_landing, width=0.5):
    """Access ladder leaning against the walkway platform edge.

    Feet stand on the ground out from the face, rail tops rest against the
    platform's outer edge with ~1 m running past as a handhold (like a real
    site ladder). Rungs stay level while the rails lean at ~70 degrees, so
    it never reads as a free-standing tower.
    """
    z_top = z_landing + 1.0
    run = z_top / 2.75  # ~70-degree lean
    y_top = y_edge + 0.05
    y_base = y_edge - run
    for s in (-1.0, 1.0):
        _diagonal(bm, x + s * width * 0.5, y_base,
                  x + s * width * 0.5, y_top, 0.0, z_top, thick=0.06)
    z = 0.3
    while z < z_top - 0.15:
        ry = y_base + (y_top - y_base) * (z / z_top)
        create_beveled_box(
            bm, size=(width, 0.05, 0.05),
            location=(x, ry, z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
        )
        z += 0.32


def _tarp_roof(bm, cx, cy, sx, sy, pole_h, lifts, seed=42):
    """Segmented canvas weather roof carried on a real timber support grid.

    Bearer beams sit directly on the pole tops (perimeter rows plus the
    interior pole rows on large sites), rafters cross them every ~2 m, and
    the canvas is laid in ~9 m segments stepping down 0.05 m per bay like
    overlapping sheets, each clamped by its own batten and tied with ropes
    to the top lift. Nothing floats: every sheet sits on rafters that sit
    on bearers that sit on poles.
    """
    rng = _rng(seed, salt=208)
    # Support grid first: bearers on the pole rows, rafters across them.
    for by in _pole_rows(cy, sy, sx):
        create_beveled_box(
            bm, size=(sx, 0.12, 0.14),
            location=(cx, by, pole_h + 0.07),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
        )
    for px in _line_coords(cx - sx * 0.5 - 0.3, cx + sx * 0.5 + 0.3, step=2.0):
        create_beveled_box(
            bm, size=(0.09, sy + 0.6, 0.12),
            location=(px, cy, pole_h + 0.20),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006,
        )
    # Canvas in overlapping segments stepping down along +X.
    n_seg = max(1, int(round(sx / 9.0)))
    seg_w = sx / n_seg
    top = lifts[-1]
    for i in range(n_seg):
        seg_cx = cx - sx * 0.5 + (i + 0.5) * seg_w
        z = pole_h + 0.28 - i * 0.05
        create_box(
            bm, size=(seg_w + 0.35, sy + 0.6, 0.05),
            location=(seg_cx, cy, z),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.01),
            mat_index=MAT_INDEX_TARP,
        )
        # Batten clamping this segment's windward edge.
        create_beveled_box(
            bm, size=(0.09, sy + 0.6, 0.06),
            location=(seg_cx - seg_w * 0.5, cy, z + 0.05),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005,
        )
        # Rope ties from the segment corners down to the top lift.
        drop = max(0.15, z - top)
        for qx in (seg_cx - seg_w * 0.5 + 0.15, seg_cx + seg_w * 0.5 - 0.15):
            for qy in (cy - sy * 0.5, cy + sy * 0.5):
                create_cylinder(
                    bm, radius=0.025, height=drop, segments=6,
                    location=(qx, qy, z - drop * 0.5),
                    mat_index=MAT_INDEX_ROPE,
                )


def _line_coords(a0, a1, step=2.0):
    """Evenly spaced coordinates from ``a0`` to ``a1`` (~``step`` apart)."""
    span = a1 - a0
    n = max(2, int(round(span / step)) + 1)
    return [a0 + i * span / (n - 1) for i in range(n)]


def _grid_bays(span):
    """Number of ~6 m bays across ``span`` (capped so huge sites stay bounded)."""
    return min(6, max(1, int(round(span / 6.0))))


def _pole_rows(c, s, other):
    """Coordinates of every pole row along one axis: perimeter pair plus interior rows.

    Sites under 12 m across get perimeter poles only; larger sites grow
    interior pole rows on ~6 m bays so the roof grid and long ledgers are
    visibly carried instead of spanning impossible distances.
    """
    if min(s, other) <= 12.0:
        return [c - s * 0.5, c + s * 0.5]
    n = _grid_bays(s)
    return [c - s * 0.5 + i * s / n for i in range(n + 1)]


def build_scaffold_frame(bm, cx, cy, sx, sy, height, levels=2, seed=42,
                         ladders=1):
    """Timber pole scaffold rectangle centred on (cx, cy).

    Poles every ~2 m around the perimeter (plus interior rows on sites over
    12 m across), ledgers at each lift, working platforms on the front/back
    faces per lift, diagonal braces on alternating bays and leaning access
    ladders climbing the front face onto the first walkway platform.
    Returns ``(pole_height, lifts)`` so callers can seat the tarp roof.
    """
    rng = _rng(seed, salt=913)
    height = max(2.5, float(height))
    levels = min(6, max(1, int(levels)))
    x0, x1 = cx - sx * 0.5, cx + sx * 0.5
    y0, y1 = cy - sy * 0.5, cy + sy * 0.5

    xs = _line_coords(x0, x1)
    ys = _line_coords(y0, y1)
    x_rows = _pole_rows(cx, sx, sy)
    y_rows = _pole_rows(cy, sy, sx)

    # Perimeter poles, then interior rows on large sites (thinner).
    for px in xs:
        for py in (y0, y1):
            _pole(bm, px, py, height, r=0.055 + rng.random() * 0.015)
    for py in ys[1:-1]:
        for px in (x0, x1):
            _pole(bm, px, py, height, r=0.055 + rng.random() * 0.015)
    for px in x_rows[1:-1]:
        for py in y_rows[1:-1]:
            _pole(bm, px, py, height, r=0.05 + rng.random() * 0.01)

    # Lifts spread from a reachable first lift (~2 m) up to just under the
    # pole tops, so no tall bare cage sticks out above the working level.
    top = height - 0.5
    if levels == 1:
        lifts = [round(min(max(top, 1.9), height - 0.4), 2)]
    else:
        first = 2.0
        lifts = [round(min(max(first + i * (top - first) / (levels - 1), 1.9),
                           height - 0.4), 2)
                 for i in range(levels)]

    for lv in lifts:
        # Ledgers along all four faces.
        for px_a, px_b in zip(xs[:-1], xs[1:]):
            _ledger(bm, px_a, y0, px_b, y0, lv)
            _ledger(bm, px_a, y1, px_b, y1, lv)
        for py_a, py_b in zip(ys[:-1], ys[1:]):
            _ledger(bm, x0, py_a, x0, py_b, lv)
            _ledger(bm, x1, py_a, x1, py_b, lv)
        # Platforms on front/back faces (alternate per lift to save polys).
        _platform(bm, x0, x1, y0 - 0.55, y0 + 0.05, lv + 0.06)
        if lifts.index(lv) % 2 == 1:
            _platform(bm, x0, x1, y1 - 0.05, y1 + 0.55, lv + 0.06)
        # Lashings at corners.
        for qx, qy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            _rope_lashing(bm, qx, qy, lv)

    # Diagonal braces on alternating bays (front/back + sides).
    for i, (px_a, px_b) in enumerate(zip(xs[:-1], xs[1:])):
        if i % 2 == 0:
            _diagonal(bm, px_a, y0, px_b, y0, 0.2, lifts[0])
            if len(lifts) > 1:
                _diagonal(bm, px_b, y1, px_a, y1, lifts[0], lifts[-1])
    for i, (py_a, py_b) in enumerate(zip(ys[:-1], ys[1:])):
        if i % 2 == 1:
            _diagonal(bm, x0, py_a, x0, py_b, 0.2, lifts[0])

    # Leaning access ladders on the front face, rails resting against the
    # walkway platform edge so workers climb straight up onto the first
    # lift. Spread across the face on larger sites.
    n_lad = min(4, max(1, int(ladders)))
    lad_step = min(6.0, sx * 0.18)
    for i in range(n_lad):
        lx = cx + (i - (n_lad - 1) * 0.5) * lad_step
        _leaning_ladder(bm, lx, y0 - 0.55, lifts[0] + 0.09, width=0.5)
    return height, lifts


def build_construction_piles(bm, cx, cy, sx, sy, seed=42, plot_key='AUTO'):
    """Stage stone / timber / prop piles around the scaffold interior (DRY).

    The base set suits a small site; ``PILE_TIER`` adds clusters for larger
    plots (extra stone courses, timber piles, barrel stores, crates) so big
    yards read busy instead of empty. Everything hugs the scaffold edges,
    clear of the centre where the building (or its future walls) stands.
    """
    from .furniture import build_crate, build_barrel
    from .quarry import build_cut_block_stack, build_rubble_pile

    tier = PILE_TIER.get(plot_key, 0)
    rng = _rng(seed, salt=551)
    hx, hy = sx * 0.5 - 1.0, sy * 0.5 - 1.0
    # Cut-stone stacks: the unfinished walls' next courses.
    build_cut_block_stack(bm, cx - hx, cy + hy, z_ground=0.0,
                          count=6, seed=seed + 11)
    build_cut_block_stack(bm, cx + hx, cy + hy - 1.0, z_ground=0.0,
                          count=4, seed=seed + 12)
    build_rubble_pile(bm, cx - hx + 2.2, cy + hy - 0.5, count=4,
                      seed=seed + 13)
    _timber_pile(bm, cx - hx + 0.4, cy - hy + 1.0, rng)
    # Barrels + crates: site stores (front-right corner).
    build_barrel(bm, cx + hx - 0.4, cy - hy, z_ground=0.0, ang=0.2)
    build_barrel(bm, cx + hx + 0.3, cy - hy + 0.4, z_ground=0.0, ang=-0.1)
    build_crate(bm, cx + hx - 0.2, cy - hy + 1.2, z_ground=0.0, ang=0.15,
                size=0.62, height=0.55, brace_style='DIAGONAL')
    # Hoop iron banding stack beside the timber.
    create_cylinder(
        bm, radius=0.30, height=0.5, segments=10,
        location=(cx - hx + 1.2, cy - hy + 0.6, 0.25),
        mat_index=MAT_INDEX_IRON,
    )
    if tier >= 1:
        # Medium+: second stone course mid-back and timber along the flank.
        build_cut_block_stack(bm, cx, cy + hy, z_ground=0.0,
                              count=6, seed=seed + 21)
        _timber_pile(bm, cx + hx - 0.4, cy, rng)
        build_crate(bm, cx - hx + 0.6, cy - hy + 0.4, z_ground=0.0, ang=-0.2,
                    size=0.55, height=0.5, brace_style='CROSS')
    if tier >= 2:
        # Large+: barrel store on the left flank and rubble up front.
        build_barrel(bm, cx - hx, cy + 0.5, z_ground=0.0, ang=0.5)
        build_barrel(bm, cx - hx + 0.7, cy - 0.2, z_ground=0.0, ang=-0.3)
        build_rubble_pile(bm, cx + hx - 2.0, cy - hy + 0.5, count=5,
                          seed=seed + 23)
        build_crate(bm, cx + hx - 1.4, cy + hy - 0.6, z_ground=0.0, ang=0.3,
                    size=0.62, height=0.55, brace_style='DIAGONAL')
    if tier >= 3:
        # Huge: full working yard - courses on every side, twin timber.
        build_cut_block_stack(bm, cx - hx, cy - hy + 2.2, z_ground=0.0,
                              count=6, seed=seed + 31)
        build_cut_block_stack(bm, cx + hx, cy - 1.0, z_ground=0.0,
                              count=5, seed=seed + 32)
        _timber_pile(bm, cx - hx * 0.3, cy + hy - 1.5, rng)
        for k, (ox, oy) in enumerate(((0.4, -0.6), (-0.5, 0.2), (1.2, 0.8))):
            build_crate(bm, cx + hx * 0.2 + ox, cy - hy + 2.0 + oy,
                        z_ground=0.0, ang=0.1 * k,
                        size=0.58, height=0.5, brace_style='DIAGONAL')
        build_rubble_pile(bm, cx + 1.5, cy + hy - 2.0, count=5,
                          seed=seed + 33)


def _timber_pile(bm, x, y, rng):
    """One stacked plank pile on the ground (shared by all pile tiers).

    Laid along Y so a corner pile never pokes past the scaffold poles.
    """
    for k in range(5):
        create_beveled_box(
            bm, size=(0.24, 1.8 - k * 0.06, 0.12),
            location=(x, y, 0.12 + k * 0.13),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.06),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006,
        )


def _build_site_cranes(bm, ccx, ccy, sx, sy, plot_key):
    """Yard crane outside plus interior cranes on large/huge plots.

    The outside crane serves the plot from the front-right; interior cranes
    stand at the back inside the scaffold where the long spans leave room,
    so big sites get the multi-crane bustle the user asked for.
    """
    from .crane import build_courtyard_crane
    build_courtyard_crane(bm, yard_x=ccx + sx * 0.5 + 1.5,
                          yard_y=ccy - sy * 0.5 - 1.0,
                          z_ground=0.0, rot_angle=0.6)
    n_inside = CRANES_INSIDE.get(plot_key, 0)
    if n_inside <= 0:
        return
    back_y = ccy + sy * 0.5 - 3.0
    if n_inside == 1:
        spots = ((ccx, back_y, 2.6),)
    else:
        spots = ((ccx - sx * 0.25, back_y, 2.6),
                 (ccx + sx * 0.25, back_y, -2.6))
    for qx, qy, rot in spots[:n_inside]:
        build_courtyard_crane(bm, yard_x=qx, yard_y=qy, z_ground=0.0,
                              mast_height=5.0, jib_length=4.2, rot_angle=rot)


def build_construction_site(bm, props, ctx, tier):
    """Plot-space scaffold composer called from the accessory dispatch.

    Scaffold footprint follows ``construction_plot`` + ``scaffold_padding``
    (walk-around guarantee); height follows the actual building so every
    lift serves a real storey. Tarps, piles and crane are independent
    toggles. Only used in WRAP_BUILDING mode (empty sites go through
    :func:`build_empty_construction_site` instead).
    """
    plot_key = getattr(props, 'construction_plot', 'AUTO')
    padding = getattr(props, 'scaffold_padding', 1.5)
    levels = getattr(props, 'scaffold_levels', 2)
    seed = getattr(ctx, 'seed', 42)

    bldg_w = float(getattr(ctx, 'base_w', 8.0))
    bldg_d = float(getattr(ctx, 'base_d', 8.0))
    # Wings extend the footprint: enclose main + wings so poles clear them.
    try:
        _x0, _x1 = -bldg_w * 0.5, bldg_w * 0.5
        _y0, _y1 = -bldg_d * 0.5, bldg_d * 0.5
        for w in getattr(ctx, 'wings', []) or []:
            b = w.get('base', None)
            if b and len(b) == 4:
                _x0, _x1 = min(_x0, b[0]), max(_x1, b[1])
                _y0, _y1 = min(_y0, b[2]), max(_y1, b[3])
        bldg_w, bldg_d = _x1 - _x0, _y1 - _y0
    except Exception:
        pass
    # Building centre in plot space (after setback translation).
    # ctx does not track the translation, so rebuild it from props.
    setback = float(getattr(props, 'plot_setback', 0.0) or 0.0)
    off_x = float(getattr(props, 'plot_offset_x', 0.0) or 0.0)
    ccx, ccy = off_x, setback

    sx, sy = scaffold_extents(plot_key, padding, bldg_w, bldg_d)

    total_h = float(getattr(ctx, 'total_height', 6.0) or 6.0)
    scaf_h = total_h + 1.0

    _h, lifts = build_scaffold_frame(bm, ccx, ccy, sx, sy, scaf_h,
                                     levels=levels, seed=seed,
                                     ladders=LADDER_COUNT.get(plot_key, 1))

    if getattr(props, 'scaffold_tarp', True):
        _tarp_roof(bm, ccx, ccy, sx, sy, _h, lifts, seed=seed)

    if getattr(props, 'construction_piles', True):
        build_construction_piles(bm, ccx, ccy, sx, sy, seed=seed,
                                 plot_key=plot_key)

    if getattr(props, 'construction_crane', False):
        _build_site_cranes(bm, ccx, ccy, sx, sy, plot_key)


def build_empty_construction_site(bm, props, ctx):
    """Scaffold-only site composer: scaffold + piles + crane, nothing else.

    No walls, floors, roof or footing are built. The scaffold footprint
    follows ``construction_plot`` + ``scaffold_padding`` exactly (no need to
    enclose a real building, so no work-margin growth); height follows the
    intended storeys (``num_floors`` x ``floor_height``, roof excluded since
    nothing is roofed yet) so lifts serve the future floors.
    """
    plot_key = getattr(props, 'construction_plot', 'AUTO')
    padding = getattr(props, 'scaffold_padding', 1.5)
    levels = getattr(props, 'scaffold_levels', 2)
    seed = getattr(ctx, 'seed', 42)
    pad = min(3.0, max(0.5, float(padding)))

    setback = float(getattr(props, 'plot_setback', 0.0) or 0.0)
    off_x = float(getattr(props, 'plot_offset_x', 0.0) or 0.0)
    ccx, ccy = off_x, setback

    if plot_key in PLOT_SIZES:
        plot = PLOT_SIZES[plot_key]
        sx = sy = plot - 2.0 * pad
    else:
        # AUTO with no building: scaffold the intended footprint + margin.
        fw = max(3.0, float(getattr(ctx, 'base_w', 6.0)))
        fd = max(3.0, float(getattr(ctx, 'base_d', 6.0)))
        sx, sy = fw + 2.4, fd + 2.4

    # Intended scaffold height = future wall height + 1 m working top
    # (roof excluded: nothing is roofed yet, so don't build air).
    scaf_h = max(2.5, float(getattr(ctx, 'found_h', 0.0) or 0.0)
                 + max(1, int(getattr(ctx, 'num_floors', 1))) * float(getattr(ctx, 'floor_h', 2.8)) + 1.0)

    _h, lifts = build_scaffold_frame(bm, ccx, ccy, sx, sy, scaf_h,
                                     levels=levels, seed=seed,
                                     ladders=LADDER_COUNT.get(plot_key, 1))

    if getattr(props, 'scaffold_tarp', True):
        _tarp_roof(bm, ccx, ccy, sx, sy, _h, lifts, seed=seed)

    if getattr(props, 'construction_piles', True):
        build_construction_piles(bm, ccx, ccy, sx, sy, seed=seed,
                                 plot_key=plot_key)

    if getattr(props, 'construction_crane', False):
        _build_site_cranes(bm, ccx, ccy, sx, sy, plot_key)
