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
    """Lay out the range on the -X half of the plot, running PARALLEL to the housing along Y.

    All coordinates are in plot space. The lodge sits on the +X half of the plot.
    The shooting lane runs from the front shooting line (Y = -14.0) to the far back (Y = +15.5),
    providing a long ~30-meter target practice field parallel to the building.
    Targets face -Y (toward the archers at the front shooting line).
    """
    # 1. Long boundary fence running along Y separating the archery field from the lodge walkway
    build_range_fence(bm, (-1.8, -15.0), (-1.8, 16.5), z_ground=0.0,
                      post_spacing=2.2, height=1.10)

    # 2. Outer boundary fence along the far -X plot edge
    build_range_fence(bm, (-16.5, -15.0), (-16.5, 16.5), z_ground=0.0,
                      post_spacing=2.2, height=1.10)

    # 3. Rear safety barrier fence behind the far targets
    build_range_fence(bm, (-16.5, 16.5), (-1.8, 16.5), z_ground=0.0,
                      post_spacing=2.0, height=1.20)

    # 4. Front shooting line rail where archers stand
    build_range_fence(bm, (-16.5, -14.0), (-1.8, -14.0), z_ground=0.0,
                      post_spacing=2.2, height=0.95)

    # 5. Far target butts (Y = 15.2): 3 championship targets across the lane, facing -Y (ang=0.0)
    for tx in (-13.5, -9.2, -4.8):
        build_archery_target(bm, tx, 15.2, z_ground=0.0, ang=0.0)

    # 6. Mid-distance practice targets (Y = 5.5) for short-range training
    for tx in (-11.5, -6.8):
        build_archery_target(bm, tx, 5.5, z_ground=0.0, ang=0.0)

    # 7. Corner marker posts framing the field
    for px, py in ((-16.5, -15.0), (-1.8, -15.0), (-16.5, 16.5), (-1.8, 16.5)):
        create_beveled_box(bm, size=(0.18, 0.18, 2.4),
                           location=(px, py, 1.2),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
