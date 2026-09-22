"""Reusable tournament / knights' yard props.

- :func:`build_jousting_quintain` - a pivoting practice target (shield + sandbag)
- :func:`build_tournament_yard`    - lays out quintains, racks and standards

The yard reuses the shared weapon rack (DRY) and the generic range fence from
:mod:`archery`, so a tiltyard and an archery line are built from one fence.
"""

import math

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_torus_ring,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD,
    MAT_INDEX_IRON, MAT_INDEX_HAY,
)
from .shield import build_round_shield
from .military_props import build_weapon_rack
from .archery import build_range_fence
from .banner import build_banner_pole
from .palisade import (
    compound_bounds, fortification_offset, fortification_depth_extra,
)


def build_jousting_quintain(bm, x, y, z_ground=0.0, ang=0.0):
    """A rotary quintain: post, spinning cross-arm, shield and counter-weight bag."""
    ca, sa = math.cos(ang), math.sin(ang)

    def to_world(lx, ly, lz):
        return (x + ca * lx - sa * ly, y + sa * lx + ca * ly, z_ground + lz)

    # Stepped round timber base.
    create_cylinder(bm, radius=0.42, height=0.12, segments=16,
                    location=to_world(0.0, 0.0, 0.06), mat_index=MAT_INDEX_TIMBER)
    create_cylinder(bm, radius=0.32, height=0.10, segments=16,
                    location=to_world(0.0, 0.0, 0.17), mat_index=MAT_INDEX_TIMBER)

    # Central pivot post with an iron hub collar.
    create_cylinder(bm, radius=0.10, height=2.30, segments=10,
                    location=to_world(0.0, 0.0, 1.15), mat_index=MAT_INDEX_TIMBER_FRAME)
    create_torus_ring(bm, location=to_world(0.0, 0.0, 1.80),
                      major_radius=0.14, minor_radius=0.035,
                      major_segments=14, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # Spinning cross-arm through the hub.
    arm_len = 1.9
    create_beveled_box(bm, size=(arm_len, 0.12, 0.12),
                       location=to_world(0.0, 0.0, 1.80),
                       rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_WOOD,
                       bevel_amount=0.010)

    # Shield on one end (facing the rider).
    sx, sy, _ = to_world(-arm_len * 0.5 + 0.10, 0.0, 1.80)
    build_round_shield(bm, (sx, sy, z_ground + 1.80),
                       normal=(0.0, -1.0, 0.0), radius=0.34, pattern='QUARTERED')
    # Counter-weight sandbag on the other end.
    bx, by, _ = to_world(arm_len * 0.5 - 0.08, 0.0, 1.62)
    create_cylinder(bm, radius=0.16, height=0.42, segments=12,
                    location=(bx, by, z_ground + 1.55), mat_index=MAT_INDEX_HAY)
    create_cone(bm, radius1=0.16, radius2=0.05, height=0.14, segments=12,
                location=(bx, by, z_ground + 1.33),
                rotation=(math.pi, 0.0, 0.0), mat_index=MAT_INDEX_HAY)
    create_torus_ring(bm, location=(bx, by, z_ground + 1.75),
                      major_radius=0.09, minor_radius=0.02,
                      major_segments=10, minor_segments=5, mat_index=MAT_INDEX_TIMBER)


def build_tournament_yard(bm, props, ctx, tier):
    """Lay out the knights' training yard on the LEFT of the forecourt.

    Built in plot space (after the plot setback), so it tracks the hall's real
    position. The right of the court is reserved for the stable, so every prop
    here lives on the -X side and nothing collides.
    """
    base_hx = ctx.base_w * 0.5
    setback = getattr(props, 'plot_setback', 0.0)

    # The front-most extent of any projecting wing (in real, set-back plot space).
    wing_tip_y = ctx.main_door_yf + setback
    wing_half_w = 0.0
    for w in ctx.wings or ():
        if w.get('wall') == 'FRONT':
            wing_tip_y = min(wing_tip_y, w['base'][2] + setback)
            _wc = (w['base'][0] + w['base'][1]) * 0.5
            wing_half_w = max(wing_half_w, abs(w['base'][1] - _wc))

    try:
        x_min, _x_max, y_min, _y_max = compound_bounds(
            ctx, fortification_offset(props),
            fortification_depth_extra(props) if (
                getattr(props, 'has_curtain_wall', False)
                or getattr(props, 'has_palisade', False)) else 0.0)
    except Exception:
        x_min, y_min = -18.0, -18.0

    court_y = max(wing_tip_y - 2.8, y_min + 2.6)

    # Keep the yard on the opposite flank to the stable, clear of the central wing.
    lane_side = -1.0
    if (getattr(props, 'has_stable', False)
            and getattr(props, 'stable_side', 'RIGHT') == 'LEFT'):
        lane_side = 1.0
    x_lane = max(wing_half_w + 2.0, base_hx * 0.75)
    x_lane = min(x_lane, abs(x_min) - 2.5, 14.0) * lane_side

    for qx in (x_lane, x_lane * 0.5):
        build_jousting_quintain(bm, qx, court_y, z_ground=0.0, ang=0.0)

    build_range_fence(bm, (x_lane + lane_side * 1.6, court_y - 1.5),
                      (x_lane * 0.15, court_y - 1.5),
                      z_ground=0.0, post_spacing=2.2, height=0.95)

    build_weapon_rack(bm, x_lane + lane_side * 1.4, court_y + 0.6, 0.0,
                      ang=-lane_side * math.pi * 0.5)
    build_banner_pole(bm, x_lane + lane_side * 2.0, court_y - 1.0,
                      z_ground=0.0, height=4.6, flag_dir=(0.0, -1.0))
