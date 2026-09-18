"""Reusable palisade / stockade walls.

A pointed-stake (or neat picket) defensive fence that can run along any line or
enclose a whole compound with a gate gap. Used by the military presets but
available to any building via the Palisade toggle.
"""

import math
from ..mesh_utils import create_beveled_box, create_cone
from ..materials import MAT_INDEX_LOG, MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_CUT_STONE


def compound_bounds(ctx, offset):
    """Axis-aligned bounds enclosing the whole building (main + wings) + offset."""
    x_min, x_max = -ctx.base_w * 0.5, ctx.base_w * 0.5
    y_min, y_max = -ctx.base_d * 0.5, ctx.base_d * 0.5
    for w in ctx.wings:
        b = w['base']
        x_min, x_max = min(x_min, b[0]), max(x_max, b[1])
        y_min, y_max = min(y_min, b[2]), max(y_max, b[3])
    return x_min - offset, x_max + offset, y_min - offset, y_max + offset


def _stake(bm, x, y, z, height, w, mat, tip_mat, lean=0.0, jitter=0.0):
    """One vertical stake with a pointed top."""
    create_beveled_box(
        bm, size=(w, w, height),
        location=(x, y, z + height * 0.5),
        rotation=(lean, 0.0, 0.0),
        mat_index=mat, bevel_amount=0.012,
    )
    tip_h = max(0.14, w * 1.35)
    create_cone(
        bm, radius1=w * 0.74, radius2=0.0, height=tip_h, segments=4,
        location=(x, y, z + height + tip_h * 0.5),
        mat_index=tip_mat,
    )


def build_palisade_run(bm, p_start, p_end, ground_z=0.0, height=2.3,
                       style='STAKES', gaps=None, seed=7):
    """Build one straight palisade run between two (x, y) points.

    gaps: optional list of world-coordinate intervals along the run axis that
    are left open (e.g. a gate). Only applies to axis-aligned runs.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.3:
        return
    ux, uy = dx / length, dy / length

    # World-coordinate check for gate gaps (axis-aligned runs only).
    vertical = abs(dx) < 1e-6
    def _in_gap(px, py):
        if not gaps:
            return False
        c = py if vertical else px
        for g0, g1 in gaps:
            if g0 - 0.20 <= c <= g1 + 0.20:
                return True
        return False

    if style == 'PICKET':
        spacing = 0.24
        stake_w = 0.15
        rail = True
    else:
        spacing = 0.31
        stake_w = 0.21
        rail = True

    n = max(2, int(round(length / spacing)) + 1)
    step = length / (n - 1)
    for i in range(n):
        t = i * step
        px, py = x1 + ux * t, y1 + uy * t
        if _in_gap(px, py):
            continue
        # Deterministic pseudo-random variation from the seed.
        rnd = math.sin((i + 1) * 12.9898 + seed * 4.1414) * 43758.5453
        f = rnd - math.floor(rnd)
        if style == 'PICKET':
            h = height
            w = stake_w
            lean = 0.0
        else:
            h = height * (0.88 + 0.22 * f)
            w = stake_w * (0.85 + 0.30 * f)
            lean = (f - 0.5) * 0.10
        _stake(bm, px, py, ground_z, h, w, MAT_INDEX_LOG, MAT_INDEX_LOG, lean=lean)

    if rail:
        # Horizontal binding rails, broken around the gate gaps.
        rail_h = height * 0.72
        segs = [(0.0, length)]
        for g0, g1 in (gaps or []):
            c0 = (g0 - y1) / uy if vertical and abs(uy) > 1e-6 else (g0 - x1) / ux if abs(ux) > 1e-6 else None
            c1 = (g1 - y1) / uy if vertical and abs(uy) > 1e-6 else (g1 - x1) / ux if abs(ux) > 1e-6 else None
            if c0 is None or c1 is None:
                continue
            c0, c1 = min(c0, c1), max(c0, c1)
            new_segs = []
            for s0, s1 in segs:
                if c1 <= s0 or c0 >= s1:
                    new_segs.append((s0, s1))
                    continue
                if c0 > s0 + 0.2:
                    new_segs.append((s0, c0))
                if c1 < s1 - 0.2:
                    new_segs.append((c1, s1))
            segs = new_segs
        ang = math.atan2(dy, dx)
        for s0, s1 in segs:
            if s1 - s0 < 0.4:
                continue
            mid = (s0 + s1) * 0.5
            mx, my = x1 + ux * mid, y1 + uy * mid
            create_beveled_box(
                bm, size=(s1 - s0, 0.10, 0.16),
                location=(mx, my, ground_z + rail_h),
                rotation=(0.0, 0.0, ang),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01,
            )


def _gate_post(bm, x, y, ground_z, height):
    post_h = height * 0.82
    create_beveled_box(
        bm, size=(0.34, 0.34, post_h),
        location=(x, y, ground_z + post_h * 0.5),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.02,
    )
    create_beveled_box(
        bm, size=(0.48, 0.48, 0.14),
        location=(x, y, ground_z + post_h + 0.07),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012,
    )


def build_palisade_enclosure(bm, props, ctx, height=2.3, style='STAKES', offset=3.0):
    """Enclose the whole compound with a palisade and a front gate gap."""
    x_min, x_max, y_min, y_max = compound_bounds(ctx, offset)
    gate_cx = ctx.main_door_cx
    gate_half = max(1.1, (getattr(props, 'door_width', 1.2) + 1.0) * 0.5)
    g0, g1 = gate_cx - gate_half, gate_cx + gate_half

    build_palisade_run(bm, (x_min, y_min), (x_max, y_min), 0.0, height, style, gaps=[(g0, g1)], seed=ctx.seed)
    build_palisade_run(bm, (x_min, y_max), (x_max, y_max), 0.0, height, style, seed=ctx.seed + 1)
    build_palisade_run(bm, (x_min, y_min), (x_min, y_max), 0.0, height, style, seed=ctx.seed + 2)
    build_palisade_run(bm, (x_max, y_min), (x_max, y_max), 0.0, height, style, seed=ctx.seed + 3)

    # Corner posts + gate posts.
    for cx in (x_min, x_max):
        for cy in (y_min, y_max):
            _gate_post(bm, cx, cy, 0.0, height)
    _gate_post(bm, g0, y_min, 0.0, height)
    _gate_post(bm, g1, y_min, 0.0, height)
    return (x_min, x_max, y_min, y_max, g0, g1)
