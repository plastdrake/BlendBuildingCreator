"""
Nasher's castle undercroft. A stair house on the citadel terrace leads down through the mount
into small walled rooms framed in timber - cellar, prison, torture chamber and crypt - each
four metres below the last. Tier 1 digs one level, tier 2 two, tier 3 all four.
"""

import math
import bmesh

from ..materials import (
    MAT_INDEX_CUT_STONE, MAT_INDEX_IRON, MAT_INDEX_STONE, MAT_INDEX_CLIFFS,
    MAT_INDEX_DUNGEON_WALL as WALL, MAT_INDEX_DUNGEON_FLOOR as FLOOR,
    MAT_INDEX_DUNGEON_BEAM as BEAM,
)
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from .furniture import build_barrel, build_crate

PAD_Z = 14.0
LEVEL_Z = (9.5, 5.5, 1.5, -2.5)
WALL_H = 3.7
T = 0.6
DOOR_H = 2.5
X0, X1, Y0, Y1 = -18.0, 18.0, 30.0, 46.0
CORR_S, CORR_N = 36.0, 40.0
SHAFT_X = (-8.6, -5.4)
SHAFT_Y = (21.4, 30.3)

# (x_top, x_bottom) of the flight leaving each level; all run along y 37.0..39.4.
STAIRS = ((8.0, 15.2), (-8.0, -15.2), (8.0, 15.2))
STAIR_Y = (37.0, 39.4)


def _box(bm, x0, x1, y0, y1, z0, z1, mat=WALL, long_axis=None):
    if x1 - x0 < 0.01 or y1 - y0 < 0.01 or z1 - z0 < 0.01:
        return
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    loc = ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5)
    if mat == BEAM:
        from ..uv_utils import timber_box
        timber_box(bm, size=(dx, dy, dz), location=loc, mat_index=mat, bevel_amount=0.01, long_axis=long_axis)
    else:
        create_beveled_box(bm, size=(dx, dy, dz),
                           location=loc,
                           mat_index=mat, bevel_amount=0.01)


def _slab(bm, ztop, hole=None, ceiling_only=False):
    """Level slab: flagstone top over a dark soffit, with an optional rectangular hole.
    When ceiling_only=True, generates a single solid stone ceiling slab (no duplicate floor layer).
    """
    x0, x1, y0, y1 = X0 - T * 0.5, X1 + T * 0.5, Y0 - T * 0.5, Y1 + T * 0.5

    def part(a0, a1, b0, b1):
        if ceiling_only:
            _box(bm, a0, a1, b0, b1, ztop - 0.3, ztop, WALL)
        else:
            _box(bm, a0, a1, b0, b1, ztop - 0.3, ztop - 0.12, WALL)
            _box(bm, a0, a1, b0, b1, ztop - 0.12, ztop, FLOOR)

    if hole is None:
        part(x0, x1, y0, y1)
        return
    hx0, hx1, hy0, hy1 = hole
    part(x0, hx0, y0, y1)
    part(hx1, x1, y0, y1)
    part(hx0, hx1, y0, hy0)
    part(hx0, hx1, hy1, y1)


def _wall(bm, horizontal, fixed, a, b, zf, doors=(), posts=True):
    """Masonry wall with framed doorways, timber posts and a top plate.

    Door frames, posts and plate are proud of both wall faces so nothing is coplanar.
    """
    top = zf + WALL_H
    frame_t = T + 0.24

    def put(u0, u1, z0, z1, mat, across, long_axis=None):
        if u1 - u0 < 0.01 or z1 - z0 < 0.01:
            return
        if horizontal:
            _box(bm, u0, u1, fixed - across * 0.5, fixed + across * 0.5, z0, z1, mat, long_axis=long_axis)
        else:
            _box(bm, fixed - across * 0.5, fixed + across * 0.5, u0, u1, z0, z1, mat, long_axis=long_axis)

    spans = [(a, b)]
    for c, w in doors:
        lo, hi = c - w * 0.5 - 0.24, c + w * 0.5 + 0.24
        nxt = []
        for s0, s1 in spans:
            if hi <= s0 or lo >= s1:
                nxt.append((s0, s1))
                continue
            if lo > s0:
                nxt.append((s0, lo))
            if hi < s1:
                nxt.append((hi, s1))
        spans = nxt
    for s0, s1 in spans:
        put(s0, s1, zf, top, WALL, T)
    for c, w in doors:
        for side in (-1.0, 1.0):
            pc = c + side * (w * 0.5 + 0.12)
            put(pc - 0.12, pc + 0.12, zf, zf + DOOR_H, BEAM, frame_t, long_axis=2)
        put(c - w * 0.5 - 0.24, c + w * 0.5 + 0.24, zf + DOOR_H, zf + DOOR_H + 0.3, BEAM, frame_t + 0.04,
            long_axis=0 if horizontal else 1)
        put(c - w * 0.5 - 0.24, c + w * 0.5 + 0.24, zf + DOOR_H + 0.3, top, WALL, T)

    if posts:
        u = a + 1.5
        while u < b - 0.5:
            if all(abs(u - c) > w * 0.5 + 0.9 for c, w in doors):
                put(u - 0.14, u + 0.14, zf, top - 0.25, BEAM, T + 0.28, long_axis=2)
            u += 3.0
        put(a, b, top - 0.25, top, BEAM, T + 0.16, long_axis=0 if horizontal else 1)


def _bars(bm, x0, x1, y, zf):
    n = max(2, int((x1 - x0) / 0.2))
    for i in range(n + 1):
        create_cylinder(bm, radius=0.025, height=DOOR_H, segments=6,
                        location=(x0 + (x1 - x0) * i / n, y, zf + DOOR_H * 0.5), mat_index=MAT_INDEX_IRON)
    for z in (zf + 0.4, zf + DOOR_H - 0.1):
        _box(bm, x0, x1, y - 0.03, y + 0.03, z - 0.03, z + 0.03, MAT_INDEX_IRON)


def _post(bm, x, y, zf):
    _box(bm, x - 0.2, x + 0.2, y - 0.2, y + 0.2, zf, zf + WALL_H - 0.3, BEAM, long_axis=2)
    _box(bm, x - 0.32, x + 0.32, y - 0.32, y + 0.32, zf + WALL_H - 0.3, zf + WALL_H, BEAM, long_axis=2)


def _stair(bm, x_top, x_bot, z_top, z_bot, y0=None, y1=None):
    n = max(6, int(math.ceil((z_top - z_bot) / 0.2)))
    sgn = 1.0 if x_bot > x_top else -1.0
    run = abs(x_bot - x_top) / n
    rise = (z_top - z_bot) / n
    sy0, sy1 = (STAIR_Y if y0 is None else (y0, y1))
    from mathutils import Vector
    uv_layer = bm.loops.layers.uv.verify()
    nosing = 0.025 * sgn

    # 1. Structural carriage ramp supporting the flight (kept clear of side rails)
    diag_len = math.hypot(abs(x_bot - x_top), abs(z_top - z_bot))
    pitch = math.atan2(z_bot - z_top, abs(x_bot - x_top)) * sgn
    cx_ramp = (x_top + x_bot) * 0.5
    cz_ramp = (z_top + z_bot) * 0.5 - 0.25
    create_box(
        bm, size=(diag_len, (sy1 - sy0) - 0.12, 0.30),
        location=(cx_ramp, (sy0 + sy1) * 0.5, cz_ramp),
        rotation=(0.0, -pitch, 0.0),
        mat_index=WALL
    )

    # 2. Individual step tread slabs and risers (zero coplanar face collisions)
    tread_t = 0.06
    for i in range(n):
        top = z_top - (i + 1) * rise
        if top <= z_bot + 0.03:
            break
        xa = x_top + sgn * i * run
        xc = xa + sgn * (run * 0.5 + 0.015)
        step_faces = create_beveled_box(
            bm, size=(run + 0.03, sy1 - sy0, tread_t),
            location=(xc, (sy0 + sy1) * 0.5, top - tread_t * 0.5),
            mat_index=FLOOR, bevel_amount=0.01
        )
        for f in step_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                v = (co.y - (sy0 + sy1) * 0.5) * 0.85
                u = (co.x - xc) * 1.5 + (co.z - top) * 1.5
                loop[uv_layer].uv = Vector((u, v))
            f.tag = True

        # Riser beneath tread (top embedded 6mm into tread slab to eliminate coplanar contact)
        if rise > tread_t + 0.01:
            riser_h = rise - tread_t + 0.006
            r_faces = create_box(
                bm, size=(0.04, sy1 - sy0 - 0.02, riser_h),
                location=(xa, (sy0 + sy1) * 0.5, top - rise + riser_h * 0.5),
                mat_index=WALL
            )

    # Proper timber handrails following the stair flight slope
    from ..railing import build_railing
    # If sy1 is against the north wall, only build on the open side sy0
    rail_sides = (sy0,) if (y0 is not None and abs(sy1 - 52.40) < 0.20) else (sy0, sy1)
    for sy in rail_sides:
        build_railing(bm, (x_top, sy), (x_bot, sy),
                      base_z=z_top, base_z_end=z_bot,
                      height=0.95, post_spacing=1.80, baluster_spacing=0.25,
                      braces=False, end_overhang=0.0)



def _hole(i):
    xt, xb = STAIRS[i]
    return (min(xt, xb) - 0.15, max(xt, xb) + 0.15, STAIR_Y[0] - 0.2, STAIR_Y[1] + 0.2)


def _dress_room(bm, kind, rx, ry, zf):
    back_y = 30.9 if ry < 36.0 else 45.1
    if kind == 'barrels':
        for i in range(3):
            build_barrel(bm, x=rx - 1.1 + i * 1.1, y=back_y, z_ground=zf)
    elif kind == 'crates':
        for i in range(3):
            build_crate(bm, x=rx - 1.1 + i * 1.1, y=back_y, z_ground=zf)
    elif kind == 'table':
        _box(bm, rx - 1.2, rx + 1.2, ry - 0.4, ry + 0.4, zf + 0.7, zf + 0.82, BEAM, long_axis=0)
        for sx in (-1.0, 1.0):
            _box(bm, rx + sx - 0.08, rx + sx + 0.08, ry - 0.3, ry + 0.3, zf, zf + 0.7, BEAM, long_axis=2)
    elif kind == 'cell':
        _box(bm, rx - 1.8, rx - 0.4, ry - 0.5, ry + 0.5, zf, zf + 0.5, BEAM, long_axis=0)
    elif kind == 'rack':
        _box(bm, rx - 1.4, rx + 1.4, ry - 0.6, ry + 0.6, zf + 0.75, zf + 0.87, BEAM, long_axis=0)
        for sx in (-1.2, 1.2):
            _box(bm, rx + sx - 0.08, rx + sx + 0.08, ry - 0.5, ry + 0.5, zf, zf + 0.75, BEAM, long_axis=2)
        create_cylinder(bm, radius=0.7, height=1.7, segments=10,
                        location=(rx + 2.0, ry + 1.2, zf + 0.85), mat_index=MAT_INDEX_IRON)
    elif kind == 'tombs':
        for sx in (-1.8, 1.8):
            _box(bm, rx + sx - 0.6, rx + sx + 0.6, ry - 1.2, ry + 1.2, zf, zf + 0.9, MAT_INDEX_CUT_STONE)
            _box(bm, rx + sx - 0.7, rx + sx + 0.7, ry - 1.3, ry + 1.3, zf + 0.9, zf + 1.05, MAT_INDEX_CUT_STONE)


def _dress_hall(bm, kind, hx, zf, south=True):
    sgn = -1.0 if hx < 0.0 else 1.0
    wall_x = (X0 + 0.9) if hx < 0.0 else (X1 - 0.9)
    corner_y = (Y0 + 1.2) if south else (Y1 - 1.2)
    dy = 1.3 if south else -1.3

    if kind == 'crates':
        build_crate(bm, x=wall_x, y=corner_y, z_ground=zf)
        build_crate(bm, x=wall_x, y=corner_y + dy, z_ground=zf)
        build_crate(bm, x=wall_x - 1.2 * sgn, y=corner_y, z_ground=zf)
    elif kind == 'barrels':
        build_barrel(bm, x=wall_x, y=corner_y, z_ground=zf)
        build_barrel(bm, x=wall_x, y=corner_y + dy, z_ground=zf)
        build_barrel(bm, x=wall_x - 1.0 * sgn, y=corner_y, z_ground=zf)
    elif kind == 'table':
        ty = corner_y + dy * 1.5
        _box(bm, wall_x - 0.4 * sgn, wall_x + 0.4 * sgn, ty - 1.2, ty + 1.2, zf + 0.7, zf + 0.82, BEAM, long_axis=1)
        for sy in (-1.0, 1.0):
            _box(bm, wall_x - 0.3 * sgn, wall_x + 0.3 * sgn, ty + sy - 0.08, ty + sy + 0.08, zf, zf + 0.7, BEAM, long_axis=2)
    elif kind == 'rack':
        ry = corner_y + dy * 1.5
        _box(bm, wall_x - 0.5 * sgn, wall_x + 0.5 * sgn, ry - 1.2, ry + 1.2, zf + 0.75, zf + 0.87, BEAM, long_axis=1)
        create_cylinder(bm, radius=0.6, height=1.7, segments=10,
                        location=(wall_x - 1.2 * sgn, ry, zf + 0.85), mat_index=MAT_INDEX_IRON)
    elif kind == 'tombs':
        ty = corner_y + dy * 1.5
        _box(bm, wall_x - 0.7 * sgn, wall_x + 0.7 * sgn, ty - 1.2, ty + 1.2, zf, zf + 0.9, MAT_INDEX_CUT_STONE)
        _box(bm, wall_x - 0.8 * sgn, wall_x + 0.8 * sgn, ty - 1.3, ty + 1.3, zf + 0.9, zf + 1.05, MAT_INDEX_CUT_STONE)



# Dressing for the four central rooms (S-left, S-right, N-left, N-right) and the two halls (W, E).
_KINDS = (
    (('barrels', 'crates', 'crates', 'table'), ('crates', 'barrels')),
    (('cell', 'cell', 'cell', 'cell'), ('table', 'crates')),
    (('rack', 'barrels', 'cell', 'rack'), ('rack', 'barrels')),
    (('tombs', 'tombs', 'tombs', 'tombs'), ('tombs', 'tombs')),
)


def _level(bm, i, zf, depart_hole):
    _slab(bm, zf, hole=depart_hole)
    if depart_hole is not None:
        from ..interior import build_stair_hole_trim
        open_side = 'W' if STAIRS[i][0] < STAIRS[i][1] else 'E'
        build_stair_hole_trim(bm, depart_hole, zf, thickness=0.30,
                              mat_index=BEAM, open_side=open_side, curb_w=0.10)
    _wall(bm, True, Y0, X0, X1, zf)
    _y1_doors = ((4.40, 2.6),) if i == 0 else ()
    _wall(bm, True, Y1, X0, X1, zf, doors=_y1_doors)
    _wall(bm, False, X0, Y0, Y1, zf)
    _wall(bm, False, X1, Y0, Y1, zf)

    # Two halls at the ends open onto the corridor; the central block holds four small rooms.
    for hx in (-6.0, 6.0):
        _wall(bm, False, hx, Y0, Y1, zf, doors=((38.0, 2.4),))
    centres = (-3.0, 3.0)
    _wall(bm, True, CORR_S, -6.0, 6.0, zf, doors=tuple((c, 1.6) for c in centres))
    _wall(bm, True, CORR_N, -6.0, 6.0, zf, doors=tuple((c, 1.6) for c in centres))
    _wall(bm, False, 0.0, Y0, CORR_S, zf, posts=False)
    _wall(bm, False, 0.0, CORR_N, Y1, zf, posts=False)

    hole_above = _hole(i - 1) if i > 0 else None
    for jx in (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0):
        if hole_above and (hole_above[0] - 0.15 <= jx <= hole_above[1] + 0.15):
            hy0, hy1 = hole_above[2], hole_above[3]
            # Beam south of stair opening:
            _box(bm, jx - 0.15, jx + 0.15, Y0 + 0.3, hy0 - 0.05, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=1)
            # Beam north of stair opening:
            _box(bm, jx - 0.15, jx + 0.15, hy1 + 0.05, Y1 - 0.3, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=1)
        else:
            _box(bm, jx - 0.15, jx + 0.15, Y0 + 0.3, Y1 - 0.3, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=1)

    if hole_above:
        hx0, hx1, hy0, hy1 = hole_above
        # Structural trimmer headers framing the north and south edges of the ceiling opening:
        _box(bm, hx0, hx1, hy0 - 0.22, hy0 - 0.02, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=0)
        _box(bm, hx0, hx1, hy1 + 0.02, hy1 + 0.22, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=0)

    rooms, halls = _KINDS[i]
    for (rx, ry), kind in zip(((-3.0, 33.0), (3.0, 33.0), (-3.0, 43.0), (3.0, 43.0)), rooms):
        # In Level 0, shift the North-East room table to rx=1.6 so the wide corridor entry at x=4.40 has a completely clear walking aisle
        actual_rx = 1.6 if (i == 0 and rx > 0 and ry > 40) else rx
        _dress_room(bm, kind, actual_rx, ry, zf)
        if kind == 'cell':
            _bars(bm, rx - 0.8, rx + 0.8, CORR_S if ry < 36 else CORR_N, zf)
    for hx in (-12.0, 12.0):
        _post(bm, hx, 33.0, zf)
        _post(bm, -13.0 if hx < 0.0 else 12.0, 43.0, zf)
        _dress_hall(bm, halls[0], hx, zf, south=True)
        _dress_hall(bm, halls[1], hx, zf, south=False)


def build_nasher_dungeon(bm, tier):
    """Four walled underground levels with logical indoor stairs from the Keep."""
    from .building_connector import carve_pass_through_portal
    from ..railing import build_railing
    levels = {1: 1, 2: 2}.get(tier, 4)

    # 1. Build underground dungeon levels
    for i in range(levels):
        _level(bm, i, LEVEL_Z[i], _hole(i) if i < levels - 1 else None)
        if i < levels - 1:
            _stair(bm, STAIRS[i][0], STAIRS[i][1], LEVEL_Z[i], LEVEL_Z[i + 1])

    # 2. Ceiling slab over Level 0
    # The Keep stair descends in the rear wing (y in [50.80, 52.40]), north of Level 0 (Y1 = 46.0),
    # so the Level 0 main ceiling slab stays solid with no holes.
    _slab(bm, 13.5, hole=None, ceiling_only=True)

    bs_x0, bs_x1 = -0.50, 4.10
    bs_y0, bs_y1 = 50.80, 52.40
    z_keep_floor = 14.95
    t_w = 0.22

    # Connecting corridor and wide stair bottom landing
    # Foot of stairs lands at x = bs_x1 - 0.20 = 3.90.
    # Widen corridor and bottom landing to span x in [corr_x0, corr_x1],
    # giving a spacious 2.5m x 2.9m clear landing in front of the stairs
    # and a 4.0m wide subterranean hallway (more than twice the previous 1.70m width).
    corr_x0 = 2.40
    corr_x1 = 6.40

    # 3. Clear shaft volume through rock / foundation / floor
    # Clear the stair flight volume in the Keep back wing:
    carve_pass_through_portal(bm, x_span=(bs_x0 - 0.30, bs_x1 + 0.30), y_span=(bs_y0 - 0.20, bs_y1 + 0.20), z_span=(9.40, 15.05))
    # Clear the wide stair bottom landing:
    carve_pass_through_portal(bm, x_span=(3.80, corr_x1 + 0.40), y_span=(bs_y0 - 0.20, bs_y1 + 0.20), z_span=(9.40, 13.60))
    # Clear the connecting passage between the stair landing (y = 50.80) and Level 0 north wall (y = 46.00):
    carve_pass_through_portal(bm, x_span=(corr_x0 - 0.20, corr_x1 + 0.40), y_span=(45.80, 50.90), z_span=(9.40, 13.60))
    # Clear the grand arched doorway through the north wall of Level 0 at y = 46.00:
    carve_pass_through_portal(bm, x_span=(2.90, 5.90), y_span=(45.70, 46.30), z_span=(9.50, 12.60))

    # Purge all residual cliff rock, foundation stone, floor slab slivers, and cut boundary faces inside/around the shaft casing
    # so NO duplicate or bisected sliver faces can ever coexist with the clean casing walls:
    stair_casing_purge = [
        f for f in bm.faces if f.is_valid
        and (
            # Inside the stair flight opening: purge everything
            (bs_x0 + 0.01 <= f.calc_center_median().x <= bs_x1 - 0.01
             and bs_y0 + 0.01 <= f.calc_center_median().y <= bs_y1 - 0.01
             and 9.40 <= f.calc_center_median().z <= z_keep_floor + 0.05)
            or
            # Inside the connecting passage and landing: purge everything
            (corr_x0 - 0.15 <= f.calc_center_median().x <= corr_x1 + 0.15
             and 45.75 <= f.calc_center_median().y <= bs_y1 + 0.05
             and 9.40 <= f.calc_center_median().z <= 13.20)
            or
            # Around perimeter: purge stone / cliffs / cut stone
            (bs_x0 - 0.45 <= f.calc_center_median().x <= corr_x1 + 0.50
             and 45.60 <= f.calc_center_median().y <= bs_y1 + 0.45
             and 9.40 <= f.calc_center_median().z <= z_keep_floor - 0.05
             and f.material_index in (MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_CLIFFS))
        )
    ]
    if stair_casing_purge:
        bmesh.ops.delete(bm, geom=stair_casing_purge, context='FACES')

    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context='EDGES')

    # 4. Subterranean floor slab for the stair bottom landing and connecting passage
    _box(bm, corr_x0 - 0.10, corr_x1 + 0.10, 45.80, bs_y1 + t_w, 9.50 - 0.30, 9.50 - 0.12, WALL)
    _box(bm, corr_x0 - 0.10, corr_x1 + 0.10, 45.80, bs_y1 + t_w, 9.50 - 0.12, 9.50, FLOOR)

    # 5. Clean masonry shaft casing walls and subterranean connecting corridor
    z_top_casing = z_keep_floor - 0.12
    # North wall along the full length of the stair flight and bottom landing:
    _box(bm, bs_x0 - t_w, corr_x1 + t_w, bs_y1, bs_y1 + t_w, 9.50, z_top_casing, WALL)
    # West wall behind the top of the stair (retains the earth under the upper floor):
    _box(bm, bs_x0 - t_w, bs_x0, bs_y0 - t_w, bs_y1 + t_w, 9.50, z_top_casing, WALL)
    # South wall along the descending flight, from top down to the connecting corridor opening:
    _box(bm, bs_x0 - t_w, corr_x0, bs_y0 - t_w, bs_y0, 9.50, z_top_casing, WALL)
    # South headwall above the wide corridor opening, sealing the stair hall up to the Keep floor:
    _box(bm, corr_x0, corr_x1 + t_w, bs_y0 - t_w, bs_y0, 13.00, z_top_casing, WALL)
    # West wall of the connecting corridor (full height up to upper floor slab):
    _box(bm, corr_x0 - t_w, corr_x0, 45.80, bs_y0, 9.50, z_top_casing, WALL)
    # East wall along the stair landing (full height up to Keep floor):
    _box(bm, corr_x1, corr_x1 + t_w, bs_y0, bs_y1 + t_w, 9.50, z_top_casing, WALL)
    # East wall of the connecting corridor (full height up to upper floor slab):
    _box(bm, corr_x1, corr_x1 + t_w, 45.80, bs_y0, 9.50, z_top_casing, WALL)
    # South end headwall over the dungeon doorway at the end of the corridor, closing the gap up to the upper floor slab:
    _box(bm, corr_x0 - t_w, corr_x1 + t_w, 45.75, 46.10, 12.50, z_top_casing, WALL)
    # Ceiling over the connecting corridor:
    _box(bm, corr_x0 - t_w, corr_x1 + t_w, 45.80, bs_y0, 12.80, 13.10, WALL)
    # Transverse heavy oak lintel beam across the entrance to the corridor at bs_y0:
    _box(bm, corr_x0 - 0.05, corr_x1 + 0.05, bs_y0 - 0.10, bs_y0 + 0.10, 12.60, 13.00, BEAM, long_axis=0)
    # Decorative heavy timber ceiling beams across the connecting corridor:
    _box(bm, corr_x0 - 0.05, corr_x1 + 0.05, 47.30, 47.50, 12.60, 12.80, BEAM, long_axis=0)
    _box(bm, corr_x0 - 0.05, corr_x1 + 0.05, 49.00, 49.20, 12.60, 12.80, BEAM, long_axis=0)
    # Decorative heavy timber beam across landing ceiling at underside of Keep floor:
    _box(bm, bs_x1 - 0.05, corr_x1 + 0.05, 51.50, 51.70, z_top_casing - 0.22, z_top_casing, BEAM, long_axis=0)

    # Timber well-hole curb trimmers capping the floor slab edges neatly around the shaft opening in the wing
    from ..interior import build_stair_hole_trim
    build_stair_hole_trim(bm, (bs_x0, bs_x1, bs_y0, bs_y1), z_keep_floor,
                          thickness=0.18, mat_index=BEAM, open_side='W', curb_w=0.08)

    # 6. Straight stair flight along X in the Keep Back Wing: top step starts at bs_x0,
    # descending eastward down to Level 0 floor at z = 9.50.
    _stair(bm, bs_x0, bs_x1 - 0.20, z_keep_floor, LEVEL_Z[0], y0=bs_y0 + 0.05, y1=bs_y1 - 0.05)

    # 7. Timber guard railing across the foot end of the Keep floor stairwell:
    # North side has solid masonry wall; south side is guarded by the stair flight's own sloped handrail.
    # The foot end (East) guards the open void from the south stair rail post to the north wall:
    build_railing(bm, (bs_x1 + 0.02, bs_y0 + 0.05), (bs_x1 + 0.02, bs_y1 - 0.05), z_keep_floor,
                  height=0.95, post_spacing=1.60, baluster_spacing=0.25, braces=False,
                  end_overhang=0.0)

