"""
Nasher's castle undercroft. A stair house on the citadel terrace leads down through the mount
into small walled rooms framed in timber - cellar, prison, torture chamber and crypt - each
four metres below the last. Tier 1 digs one level, tier 2 two, tier 3 all four.
"""

import math

from ..materials import (
    MAT_INDEX_CUT_STONE, MAT_INDEX_IRON, MAT_INDEX_STONE,
    MAT_INDEX_DUNGEON_WALL as WALL, MAT_INDEX_DUNGEON_FLOOR as FLOOR,
    MAT_INDEX_DUNGEON_BEAM as BEAM,
)
from ..mesh_utils import create_beveled_box, create_cylinder
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
        timber_box(bm, size=(dx, dy, dz), location=loc, mat_index=mat, bevel_amount=0.01)
    else:
        create_beveled_box(bm, size=(dx, dy, dz),
                           location=loc,
                           mat_index=mat, bevel_amount=0.01)


def _slab(bm, ztop, hole=None):
    """Level slab: flagstone top over a dark soffit, with an optional rectangular hole."""
    x0, x1, y0, y1 = X0 - T * 0.5, X1 + T * 0.5, Y0 - T * 0.5, Y1 + T * 0.5

    def part(a0, a1, b0, b1):
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


def _stair(bm, x_top, x_bot, z_top, z_bot):
    n = max(6, int(math.ceil((z_top - z_bot) / 0.2)))
    sgn = 1.0 if x_bot > x_top else -1.0
    run = abs(x_bot - x_top) / n
    rise = (z_top - z_bot) / n
    for i in range(n):
        top = z_top - (i + 1) * rise
        if top <= z_bot + 0.03:
            break
        xa = x_top + sgn * i * run
        xb = xa + sgn * run
        _box(bm, min(xa, xb), max(xa, xb), STAIR_Y[0], STAIR_Y[1], z_bot, top, FLOOR)
        for y0 in (STAIR_Y[0] - 0.2, STAIR_Y[1]):
            _box(bm, min(xa, xb), max(xa, xb), y0, y0 + 0.2, z_bot, top + 0.9, BEAM, long_axis=2)


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
    _wall(bm, True, Y0, X0, X1, zf)
    _wall(bm, True, Y1, X0, X1, zf)
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

    for jx in (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0):
        _box(bm, jx - 0.15, jx + 0.15, Y0 + 0.3, Y1 - 0.3, zf + WALL_H - 0.3, zf + WALL_H - 0.02, BEAM, long_axis=1)

    rooms, halls = _KINDS[i]
    for (rx, ry), kind in zip(((-3.0, 33.0), (3.0, 33.0), (-3.0, 43.0), (3.0, 43.0)), rooms):
        _dress_room(bm, kind, rx, ry, zf)
        if kind == 'cell':
            _bars(bm, rx - 0.8, rx + 0.8, CORR_S if ry < 36 else CORR_N, zf)
    for hx in (-12.0, 12.0):
        _post(bm, hx, 33.0, zf)
        _post(bm, -13.0 if hx < 0.0 else 12.0, 43.0, zf)
        _dress_hall(bm, halls[0], hx, zf, south=True)
        _dress_hall(bm, halls[1], hx, zf, south=False)


def build_nasher_dungeon(bm, tier):
    """Four walled underground levels with logical indoor stairs from the Keep."""
    from ..interior import build_straight_staircase, build_stair_guardrail
    from .building_connector import carve_pass_through_portal
    levels = {1: 1, 2: 2}.get(tier, 4)

    # 1. Build underground dungeon levels
    for i in range(levels):
        _level(bm, i, LEVEL_Z[i], _hole(i) if i < levels - 1 else None)
        if i < levels - 1:
            _stair(bm, STAIRS[i][0], STAIRS[i][1], LEVEL_Z[i], LEVEL_Z[i + 1])

    # 2. Ceiling slab over Level 0 with an open stairwell cutout under the Keep
    # Sits flush at Z=13.2 (bottom at 13.2, top at 13.5), perfectly matching Level 0 walls (height 3.7 above 9.5)
    # with 0 gap, and sits 0.5m safely below Citadel rock pad at 14.0 (no coplanar z-fighting).
    stair_hole_keep = (-11.85, -10.15, 38.8, 46.6)
    _slab(bm, 13.5, hole=stair_hole_keep)

    z_keep_floor = 14.95

    # 3. Clear shaft volume through rock / foundation
    carve_pass_through_portal(bm, x_span=(-11.85, -10.15), y_span=(38.8, 46.6), z_span=(12.8, 15.3))

    # Clean masonry shaft casing walls lining the opening
    _box(bm, -12.15, -9.85, 46.6, 46.9, 13.2, z_keep_floor, WALL)
    _box(bm, -10.15, -9.85, 38.8, 46.9, 13.2, z_keep_floor, WALL)
    _box(bm, -12.15, -11.85, 38.8, 46.9, 13.2, z_keep_floor, WALL)
    _box(bm, -12.15, -9.85, 38.5, 38.8, 13.2, z_keep_floor, WALL)

    # 4. Logical indoor stairs descending from Keep Ground Floor (Z=14.95) into Level 0 (Z=9.5)
    # Stair descends from Keep floor at Y=39.0 to West Hall floor at Y=45.8, far north of
    # the corridor doorway at X=-6.0, Y=38.0 so the corridor passage is 100% unobstructed.
    stair_w = 1.40
    stair_cx = -10.90
    build_straight_staircase(
        bm,
        start_pos=(stair_cx, 45.8, LEVEL_Z[0]),
        target_z=z_keep_floor,
        stair_width=stair_w,
        stair_depth=6.8,
        num_steps=26,
        direction_y=-1
    )

    # 5. Upper safety guard railings around the stairwell opening on the Keep floor (Z=14.95)
    build_stair_guardrail(
        bm,
        rail_x=-10.05,
        y_start=39.8,
        y_end=46.8,
        floor_z=z_keep_floor,
        rail_h=0.95,
        return_y=46.8,
        x_start=-11.85
    )
