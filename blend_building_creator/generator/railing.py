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
                       iron_pin=True):
    """A single capped newel post matching build_railing's joinery."""
    create_beveled_box(bm, size=(POST_W, POST_W, height),
                       location=(x, y, base_z + height * 0.5),
                       mat_index=rail_mat, bevel_amount=0.014)
    create_beveled_box(bm, size=(POST_CAP_W, POST_CAP_W, POST_CAP_T),
                       location=(x, y, base_z + height + POST_CAP_T * 0.35),
                       mat_index=cap_mat, bevel_amount=0.012)
    if iron_pin:
        create_cylinder(bm, radius=0.022, height=0.05, segments=6,
                        location=(x, y, base_z + height + POST_CAP_T * 0.72),
                        mat_index=MAT_INDEX_IRON)


def build_railing_post(bm, x, y, base_z, height=1.05,
                       rail_mat=MAT_INDEX_TIMBER, cap_mat=MAT_INDEX_WOOD,
                       iron_pin=True, jankiness=0.0, index=0, seed=0):
    """A single capped newel post matching build_railing's joinery.

    jankiness tilts and nudges the post for a hand-built fantasy look.
    """
    tilt_x = _jitter(jankiness, index, 1.7, seed, 0.055)
    tilt_y = _jitter(jankiness, index, 4.1, seed, 0.055)
    ox = _jitter(jankiness, index, 7.3, seed, 0.035)
    oy = _jitter(jankiness, index, 9.9, seed, 0.035)
    px, py = x + ox, y + oy
    create_beveled_box(bm, size=(POST_W, POST_W, height),
                       location=(px, py, base_z + height * 0.5),
                       rotation=(tilt_x, tilt_y, 0.0),
                       mat_index=rail_mat, bevel_amount=0.014)
    create_beveled_box(bm, size=(POST_CAP_W, POST_CAP_W, POST_CAP_T),
                       location=(px + tilt_x * height * 0.35,
                                 py + tilt_y * height * 0.35,
                                 base_z + height + POST_CAP_T * 0.35),
                       rotation=(tilt_x, tilt_y, 0.0),
                       mat_index=cap_mat, bevel_amount=0.012)
    if iron_pin:
        create_cylinder(bm, radius=0.022, height=0.05, segments=6,
                        location=(px + tilt_x * height * 0.35,
                                  py + tilt_y * height * 0.35,
                                  base_z + height + POST_CAP_T * 0.72),
                        mat_index=MAT_INDEX_IRON)


def _wonky_rail(bm, x0, y0, x1, y1, za0, za1, cross_w, cross_t, mat,
                jankiness, salt, seed, bevel=0.012):
    """A rail built as a few slightly mis-aligned boards so it reads hand-hewn."""
    n = 4 if jankiness > 0.02 else 1
    dx, dy = x1 - x0, y1 - y0
    run = math.hypot(dx, dy)
    nx, ny = (-dy / run, dx / run) if run > 1e-5 else (0.0, 0.0)
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + dx * t
        y = y0 + dy * t
        z = za0 + (za1 - za0) * t
        if 0 < i < n:
            k = _hash01(i, salt, seed)
            z += (k - 0.5) * 0.05 * jankiness
            lat = _jitter(jankiness, i, salt + 11.0, seed, 0.030)
            x += nx * lat
            y += ny * lat
        pts.append((x, y, z))
    for a, b in zip(pts[:-1], pts[1:]):
        _beam(bm, (a[0], a[1]), (b[0], b[1]), a[2], b[2],
              cross_w, cross_t, mat, bevel=bevel)


def build_railing(bm, p_start, p_end, base_z, height=1.05, base_z_end=None,
                  rail_mat=MAT_INDEX_TIMBER, baluster_mat=MAT_INDEX_WOOD,
                  end_overhang=0.10, post_spacing=1.45, baluster_spacing=0.20,
                  braces=True, iron_pins=True, posts=True, jankiness=0.45,
                  seed=0):
    """Build a detailed guard railing from p_start to p_end at floor level base_z.

    height is measured vertically from the underside of the sill to the top of the
    handrail. Pass base_z_end to make the railing follow a straight slope (ramps);
    the rail and sill tilt with it while posts and balusters stay vertical.
    Set posts=False to lay only the rails/balusters between externally placed
    newels (used by the spiral stair, which already has a post per step).
    jankiness (0 = machined, ~0.45 = hand-built fantasy) adds the crooked,
    slightly askew character the rest of the building's joinery has.
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

    # 1. Grounded sill (base rail), following the slope.
    _wonky_rail(bm, x0, y0, x1, y1,
                z0 + SILL_T * 0.5, z1 + SILL_T * 0.5,
                SILL_W, SILL_T, rail_mat, jankiness, 2.0, seed)

    # 2. Handrail + its wide cap board, with a little overhang past the ends.
    _wonky_rail(bm,
                x0 - ux * end_overhang, y0 - uy * end_overhang,
                x1 + ux * end_overhang, y1 + uy * end_overhang,
                z0 + height - RAIL_T * 0.5, z1 + height - RAIL_T * 0.5,
                RAIL_W, RAIL_T, rail_mat, jankiness, 5.0, seed)
    _wonky_rail(bm,
                x0 - ux * end_overhang, y0 - uy * end_overhang,
                x1 + ux * end_overhang, y1 + uy * end_overhang,
                z0 + height + CAP_T * 0.5, z1 + height + CAP_T * 0.5,
                CAP_W, CAP_T, baluster_mat, jankiness * 0.6, 8.0, seed)

    # 3. Mid + lower string rails between the bays (only on taller rails).
    if height > 0.7:
        _wonky_rail(bm, x0, y0, x1, y1,
                    z0 + height * 0.56, z1 + height * 0.56,
                    MID_W, MID_T, rail_mat, jankiness, 12.0, seed)
    if height > 0.85:
        _wonky_rail(bm, x0, y0, x1, y1,
                    z0 + height * 0.26, z1 + height * 0.26,
                    LOW_W, LOW_T, rail_mat, jankiness, 15.0, seed)

    # 4. Posts: both ends plus evenly spaced in between, each with a capped head.
    n_post = max(1, int(round(run / max(0.4, post_spacing))))
    posts_t = [i / n_post for i in range(n_post + 1)]
    if posts:
        for i, t in enumerate(posts_t):
            px, py, pz = at(t)
            build_railing_post(bm, px, py, pz, height, rail_mat, baluster_mat,
                               iron_pins, jankiness, i, seed)
    elif len(posts_t) < 2:
        posts_t = [0.0, 1.0]

    # 5. Balusters inside every bay, plus an optional turned collar.
    for bi in range(len(posts_t) - 1):
        ta, tb = posts_t[bi], posts_t[bi + 1]
        bay = (tb - ta) * run
        if bay < 0.24:
            continue
        n_bal = max(1, int(round(bay / max(0.12, baluster_spacing))) - 1)
        for k in range(1, n_bal + 1):
            t = ta + (tb - ta) * (k / (n_bal + 1))
            px, py, pz = at(t)
            bal_h = height - SILL_T - RAIL_T
            if bal_h < 0.12:
                continue
            idx = bi * 100 + k
            px += _jitter(jankiness, idx, 21.0, seed, 0.028)
            py += _jitter(jankiness, idx, 24.0, seed, 0.028)
            t_x = _jitter(jankiness, idx, 27.0, seed, 0.05)
            t_y = _jitter(jankiness, idx, 30.0, seed, 0.05)
            create_beveled_box(bm, size=(0.058, 0.058, bal_h),
                               location=(px, py, pz + SILL_T + bal_h * 0.5),
                               rotation=(t_x, t_y, 0.0),
                               mat_index=baluster_mat, bevel_amount=0.010)
            if braces:
                # Small turned collar on each baluster for a hand-carved feel.
                create_beveled_box(bm, size=(0.088, 0.088, 0.045),
                                   location=(px, py, pz + SILL_T + bal_h * 0.5),
                                   rotation=(t_x, t_y, 0.0),
                                   mat_index=rail_mat, bevel_amount=0.008)
        if braces and bay > 0.55:
            # Diagonal brace across the bay, sill corner up to the mid rail.
            t0, t1 = ta + (tb - ta) * 0.08, ta + (tb - ta) * 0.92
            ax, ay, az = at(t0)
            bx, by, bz = at(t1)
            _beam(bm, (ax, ay), (bx, by),
                  az + SILL_T + 0.06, bz + height * 0.50,
                  0.055, 0.05, rail_mat, bevel=0.008)
