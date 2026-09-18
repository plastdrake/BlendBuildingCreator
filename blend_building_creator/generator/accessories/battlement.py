"""Reusable crenellated battlements (merlons and crenels)."""

import math
from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_TIMBER,
)


def build_battlement_run(bm, p_start, p_end, z_base, height=0.78,
                         thickness=0.30, merlon_w=0.55, crenel_w=0.50,
                         style='STONE'):
    """Build a merlon/crenel parapet along a straight wall between two points."""
    x1, y1 = p_start
    x2, y2 = p_end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.5:
        return
    ux, uy = dx / length, dy / length
    ang = math.atan2(dy, dx)
    mid_x, mid_y = (x1 + x2) * 0.5, (y1 + y2) * 0.5

    base_h = height * 0.45
    merlon_h = height - base_h
    if style == 'TIMBER':
        base_mat, merlon_mat, cap_mat = MAT_INDEX_TIMBER_FRAME, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_TIMBER
    else:
        base_mat, merlon_mat, cap_mat = MAT_INDEX_STONE, MAT_INDEX_STONE, MAT_INDEX_CUT_STONE

    # Continuous low parapet under the crenels.
    create_beveled_box(
        bm, size=(length, thickness, base_h),
        location=(mid_x, mid_y, z_base + base_h * 0.5),
        rotation=(0.0, 0.0, ang), mat_index=base_mat, bevel_amount=0.015,
    )
    # Merlons spaced along the run.
    pitch = merlon_w + crenel_w
    n = max(2, int(round(length / pitch)))
    step = length / n
    for i in range(n + 1):
        t = i * step
        if t < 0.05 or t > length - 0.05:
            continue
        mx, my = x1 + ux * t, y1 + uy * t
        create_beveled_box(
            bm, size=(merlon_w * 0.62, thickness * 1.06, merlon_h),
            location=(mx, my, z_base + base_h + merlon_h * 0.5),
            rotation=(0.0, 0.0, ang), mat_index=merlon_mat, bevel_amount=0.012,
        )
        create_beveled_box(
            bm, size=(merlon_w * 0.72, thickness * 1.16, 0.10),
            location=(mx, my, z_base + base_h + merlon_h + 0.05),
            rotation=(0.0, 0.0, ang), mat_index=cap_mat, bevel_amount=0.008,
        )
