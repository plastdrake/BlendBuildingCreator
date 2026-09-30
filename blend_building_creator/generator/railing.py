"""
Reusable railing / balustrade generator.

One sturdy, detailed railing builder shared by every place the building needs a
guard: balconies, stairwell openings, staircase flights, rampart walks and
ramps. It supports level runs and sloped runs (a straight grade from
``base_z`` to ``base_z_end``) so the same call dresses a walkway and its ramp.
"""

import math

from mathutils import Matrix, Vector

from .mesh_utils import create_box, create_beveled_box, create_cylinder
from .materials import (
    MAT_INDEX_TIMBER,
    MAT_INDEX_WOOD,
    MAT_INDEX_IRON,
    MAT_INDEX_RAILING,
)

# Cross sections (metres) - deliberately chunky so rails read as real joinery.
SILL_W, SILL_T = 0.13, 0.11
RAIL_W, RAIL_T = 0.14, 0.11
CAP_W, CAP_T = 0.19, 0.045
MID_W, MID_T = 0.10, 0.065
LOW_W, LOW_T = 0.09, 0.055
POST_W = 0.16
POST_CAP_W, POST_CAP_T = 0.22, 0.05


def _hash01(i, salt, seed=0):
    """Deterministic pseudo random in [0, 1) - keeps jankiness stable per build."""
    v = math.sin(i * 12.9898 + salt * 78.233 + seed * 3.7) * 43758.5453
    return v - math.floor(v)


def _jitter(jankiness, i, salt, seed, amount):
    """Signed jitter in [-amount, amount] scaled by jankiness."""
    return (_hash01(i, salt, seed) - 0.5) * 2.0 * amount * jankiness


def _beam(bm, p0, p1, z0, z1, cross_w, cross_t, mat, bevel=0.012):
    """Beam spanning (p0,z0) -> (p1,z1) in 3D, so it also works around curves.

    cross_w is the width seen from the side of the run, cross_t the beam's own
    thickness (perpendicular to its length).
    """
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    dz = z1 - z0
    run = math.hypot(dx, dy)
    if run < 1e-5:
        return
    length = math.hypot(run, dz)
    yaw = math.atan2(dy, dx)
    pitch = math.atan2(dz, run)
    rot = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y')
    faces = create_beveled_box(bm, size=(length, cross_w, cross_t),
                               location=((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5),
                               rotation=tuple(rot.to_euler()), mat_index=mat,
                               bevel_amount=bevel)
    pass


def build_railing_post(bm, x, y, base_z, height=1.05,
                       rail_mat=MAT_INDEX_TIMBER, cap_mat=MAT_INDEX_WOOD,
                       iron_pin=False, jankiness=0.0, index=0, seed=0):
    """A single capped newel post matching build_railing's joinery."""
    tilt_x = _jitter(jankiness, index, 1.7, seed, 0.035)
    tilt_y = _jitter(jankiness, index, 4.1, seed, 0.035)
    ox = _jitter(jankiness, index, 7.3, seed, 0.020)
    oy = _jitter(jankiness, index, 9.9, seed, 0.020)
    px, py = x + ox, y + oy
    create_beveled_box(bm, size=(POST_W, POST_W, height),
                       location=(px, py, base_z + height * 0.5),
                       rotation=(tilt_x, tilt_y, 0.0),
                       mat_index=rail_mat, bevel_amount=0.012)
    create_beveled_box(bm, size=(POST_CAP_W, POST_CAP_W, POST_CAP_T),
                       location=(px + tilt_x * height * 0.35,
                                 py + tilt_y * height * 0.35,
                                 base_z + height + POST_CAP_T * 0.40),
                       rotation=(tilt_x, tilt_y, 0.0),
                       mat_index=cap_mat, bevel_amount=0.010)
    if iron_pin:
        create_cylinder(bm, radius=0.020, height=0.04, segments=6,
                        location=(px + tilt_x * height * 0.35,
                                  py + tilt_y * height * 0.35,
                                  base_z + height + POST_CAP_T * 0.75),
                        mat_index=MAT_INDEX_IRON)


def _rail_beam(bm, x0, y0, x1, y1, z0, z1, cross_w, cross_t, mat, bevel=0.010):
    """A clean single continuous beam spanning (x0, y0, z0) to (x1, y1, z1)."""
    _beam(bm, (x0, y0), (x1, y1), z0, z1, cross_w, cross_t, mat, bevel=bevel)


def build_railing(bm, p_start, p_end, base_z, height=1.05, base_z_end=None,
                  rail_mat=MAT_INDEX_TIMBER, baluster_mat=MAT_INDEX_WOOD,
                  end_overhang=0.08, post_spacing=1.60, baluster_spacing=0.25,
                  braces=False, iron_pins=False, posts=True, jankiness=0.15,
                  seed=0):
    """Build a clean, optimized guard railing from p_start to p_end at floor level base_z.

    height is measured vertically from the underside of the sill to the top of the handrail.
    Pass base_z_end to make the railing follow a straight slope (ramps).
    Uses clean single-span beams and evenly spaced vertical balusters without
    unnecessary polygon bloat, nested collars, or redundant intersecting rails.
    """
    x0, y0 = p_start
    x1, y1 = p_end
    z0 = float(base_z)
    z1 = float(base_z if base_z_end is None else base_z_end)
    dx, dy = x1 - x0, y1 - y0
    run = math.hypot(dx, dy)
    if run < 0.16 or height < 0.30:
        return
    ux, uy = dx / run, dy / run

    def at(t):
        return (x0 + dx * t, y0 + dy * t, z0 + (z1 - z0) * t)

    # 1. Grounded base sill rail, following slope
    _rail_beam(bm, x0, y0, x1, y1,
               z0 + SILL_T * 0.5, z1 + SILL_T * 0.5,
               SILL_W, SILL_T, rail_mat, bevel=0.010)

    # 2. Handrail and cap board
    rx0 = x0 - ux * end_overhang
    ry0 = y0 - uy * end_overhang
    rx1 = x1 + ux * end_overhang
    ry1 = y1 + uy * end_overhang

    _rail_beam(bm, rx0, ry0, rx1, ry1,
               z0 + height - RAIL_T * 0.5, z1 + height - RAIL_T * 0.5,
               RAIL_W, RAIL_T, rail_mat, bevel=0.010)
    _rail_beam(bm, rx0, ry0, rx1, ry1,
               z0 + height + CAP_T * 0.5, z1 + height + CAP_T * 0.5,
               CAP_W, CAP_T, baluster_mat, bevel=0.008)

    # 3. Newel posts: both ends plus evenly spaced in between
    n_post = max(1, int(round(run / max(0.6, post_spacing))))
    posts_t = [i / n_post for i in range(n_post + 1)]
    if posts:
        for i, t in enumerate(posts_t):
            px, py, pz = at(t)
            build_railing_post(bm, px, py, pz, height, rail_mat, baluster_mat,
                               iron_pins, jankiness, i, seed)
    elif len(posts_t) < 2:
        posts_t = [0.0, 1.0]

    # 4. Clean vertical balusters inside every bay
    for bi in range(len(posts_t) - 1):
        ta, tb = posts_t[bi], posts_t[bi + 1]
        bay = (tb - ta) * run
        if bay < 0.28:
            continue
        n_bal = max(1, int(round(bay / max(0.16, baluster_spacing))) - 1)
        for k in range(1, n_bal + 1):
            t = ta + (tb - ta) * (k / (n_bal + 1))
            px, py, pz = at(t)
            bal_h = height - SILL_T - RAIL_T
            if bal_h < 0.12:
                continue
            idx = bi * 100 + k
            t_x = _jitter(jankiness, idx, 27.0, seed, 0.02)
            t_y = _jitter(jankiness, idx, 30.0, seed, 0.02)
            create_beveled_box(bm, size=(0.055, 0.055, bal_h),
                               location=(px, py, pz + SILL_T + bal_h * 0.5),
                               rotation=(t_x, t_y, 0.0),
                               mat_index=baluster_mat, bevel_amount=0.006)

