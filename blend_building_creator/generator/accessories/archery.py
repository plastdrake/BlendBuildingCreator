"""Reusable archery range kit (side-by-side range layout).

The field is laid out *beside* the archers' lodge rather than in front of it:

- the log lodge sits on the +X half of the plot (shifted there by
  ``plot_offset_x``),
- the range field (targets) occupies the -X half,
- a rail fence marks the shooting line between them.

Everything here is plot-borne (built after the building offset), so the range
never inherits the lodge's translation and the two can never overlap.

Pieces:
- :func:`build_range_fence`   - generic low post-and-rail line
- :func:`build_archery_range` - layout orchestrator

Painted target faces come straight from ``military_props`` (DRY).
"""

import math

from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_TIMBER, MAT_INDEX_WOOD
from .military_props import build_archery_target


def build_range_fence(bm, p0, p1, z_ground=0.0, post_spacing=1.8, height=1.05):
    """A low post-and-rail fence marking the shooting line."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 0.5:
        return
    ux, uy = dx / length, dy / length
    ang = math.atan2(dy, dx)
    n_posts = max(2, int(round(length / post_spacing)) + 1)
    for i in range(n_posts):
        u = i * (length / (n_posts - 1))
        px, py = x0 + ux * u, y0 + uy * u
        create_beveled_box(bm, size=(0.12, 0.12, height),
                           location=(px, py, z_ground + height * 0.5),
                           rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER,
                           bevel_amount=0.010)
    for rz in (height - 0.18, height * 0.52):
        create_beveled_box(bm, size=(length, 0.10, 0.09),
                           location=((x0 + x1) * 0.5, (y0 + y1) * 0.5, z_ground + rz),
                           rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_WOOD,
                           bevel_amount=0.008)


def build_archery_range(bm, props, ctx, tier):
    """Lay out the range on the -X half of the plot, facing the +X lodge.

    All coordinates are in plot space and kept inside a +/-19 m plot. Targets
    face +X (toward the shooting line and the lodge) so the arrows fly leftward
    across the field.
    """
    # Shooting-line fence running front-to-back, well clear of the lodge.
    build_range_fence(bm, (0.0, -13.0), (0.0, 13.0), z_ground=0.0,
                      post_spacing=2.0, height=1.05)

    # Target butts: a far column of three, plus two inner markers. No hay or
    # dirt piles - just the painted targets on their stands.
    target_ang = math.radians(-90.0)   # painted face points +X
    for ty in (-9.0, 0.0, 9.0):
        build_archery_target(bm, -15.5, ty, z_ground=0.0, ang=target_ang)
    for ty in (-4.5, 4.5):
        build_archery_target(bm, -10.5, ty, z_ground=0.0, ang=target_ang)

    # A pair of slim range posts at the far corners to frame the field.
    for py in (-12.5, 12.5):
        create_beveled_box(bm, size=(0.12, 0.12, 2.2),
                           location=(-16.5, py, 1.1),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
