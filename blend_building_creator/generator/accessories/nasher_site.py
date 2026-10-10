"""
Nasher's castle site: the craggy citadel mount the castle is built on, boulders,
terrace rim walls, terrain-following stairs and the irregular outer curtain wall.

Every rock mass is a polar height-field. The same height function builds the mesh and
answers ground_z(), so buildings can sit exactly on the rock. The rock never changes
between tiers; only what stands on it does.
"""

import math

from ..materials import MAT_INDEX_CLIFFS, MAT_INDEX_CUT_STONE, MAT_INDEX_STONE
from ..mesh_utils import create_beveled_box

# (name, cx, cy, rx, ry, height, seed, slope_band, outline_amp, rough_amp)
# slope_band = fraction of the radius taken by the slope; the rest is the flat pad.
FORECOURT = ("forecourt_rock", 0.0, -34.0, 46.0, 22.0, 3.0, 5, 0.30, 0.08, 0.14)
TERRACE = ("terrace_rock", 0.0, -2.0, 56.0, 30.0, 8.0, 9, 0.40, 0.08, 0.20)
CITADEL = ("citadel_rock", 0.0, 36.0, 44.0, 30.0, 14.0, 13, 0.40, 0.08, 0.22)
EAST_BLUFF = ("east_bluff", 48.0, 26.0, 18.0, 15.0, 9.0, 21, 0.45, 0.12, 0.22)
MOUNT = (FORECOURT, TERRACE, CITADEL, EAST_BLUFF)

def _stair_run(y0, z0, y1, z1, flights, land=2.5):
    """Split a climb into equal flights separated by flat landings: (y0, z0, y1, z1) segments."""
    segs = []
    flight_len = ((y1 - y0) - (flights - 1) * land) / flights
    y = y0
    for i in range(flights):
        za = z0 + (z1 - z0) * i / flights
        zb = z0 + (z1 - z0) * (i + 1) / flights
        segs.append((y, za, y + flight_len, zb))
        y += flight_len
        if i < flights - 1:
            segs.append((y, zb, y + land, zb))
            y += land
    return segs


# Grand stair corridor along x=0: (y_from, z_from, y_to, z_to); flat segments are landings.
RAMPS = tuple(_stair_run(-66.0, 0.0, -50.0, 3.0, 2) + _stair_run(-40.0, 3.0, -20.0, 8.0, 3)
              + _stair_run(-2.0, 8.0, 18.0, 14.0, 2))

# Exact shaft opening for undercroft stair house: (x0, x1, y0, y1).
SHAFT_CUT = (-8.6, -5.4, 21.4, 30.0)

_BOTTOM_Z = -6.0
_ANGULAR = 112
_RADIAL_STEPS = 14
_STRATA = 1.7


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _fbm(x, y, seed):
    s = seed * 1.713
    v = 0.0
    for freq, amp in ((0.23, 0.55), (0.61, 0.3), (1.37, 0.15)):
        v += amp * (math.sin(x * freq + s) * math.cos(y * freq * 0.83 + s * 1.3)
                    + 0.6 * math.sin((x + y) * freq * 0.71 + s * 2.1))
    return v / 1.6


def _outline(spec, a):
    seed, amp = spec[6], spec[8]
    p = (seed * 0.37, seed * 0.91, seed * 1.43, seed * 2.17, seed * 3.1)
    wob = (0.45 * math.sin(2 * a + p[0]) + 0.35 * math.sin(3 * a + p[1])
           + 0.25 * math.sin(5 * a + p[2]) + 0.18 * math.sin(9 * a + p[3])
           + 0.10 * math.sin(17 * a + p[4]))
    return 1.0 + amp * wob


def _height(spec, x, y):
    _, cx, cy, rx, ry, h, seed, band, _amp, rough = spec
    ex, ey = (x - cx) / rx, (y - cy) / ry
    t = math.hypot(ex, ey) / _outline(spec, math.atan2(ey, ex))
    if t >= 1.0:
        return 0.0
    m = _smooth((1.0 - t) / band)
    ridge = 4.0 * m * (1.0 - m)
    z = h * m + rough * h * ridge * _fbm(x, y, seed)
    s = z / _STRATA
    f = s - math.floor(s)
    stepped = _STRATA * (math.floor(s) + _smooth(f * 1.7))
    z += (stepped - z) * min(1.0, ridge * 3.0)
    z = max(0.0, z)
    if spec[0] == "terrace_rock":
        ax = abs(x)
        if 5.0 <= ax <= 35.0 and y <= -18.5:
            if ax < 9.0:
                wx = _smooth((ax - 5.0) / 4.0)
            elif ax > 30.0:
                wx = 1.0 - _smooth((ax - 30.0) / 4.0)
            else:
                wx = 1.0
            if y <= -22.5:
                wy = 1.0
            else:
                wy = 1.0 - _smooth((y - (-22.5)) / 3.5)
            z *= (1.0 - wx * wy)
    return z


def _ramp(x, y):
    """(weight, z) of the grand-stair corridor along x=0, or (0, 0) outside it."""
    w = 1.0 - _smooth((abs(x) - 2.8) / 0.7)
    if w <= 0.0:
        return 0.0, 0.0
    for y0, z0, y1, z1 in RAMPS:
        if y0 <= y <= y1:
            return w, z0 + (z1 - z0) * (y - y0) / (y1 - y0)
    return 0.0, 0.0


def _mesh_z(spec, x, y):
    z = _height(spec, x, y)
    w, zr = _ramp(x, y)
    return z + (zr - z) * w if w > 0.0 else z


def ground_z(x, y):
    """Rock surface height at (x, y); 0.0 on the open plateau."""
    best = 0.0
    for spec in MOUNT:
        if abs(x - spec[1]) > spec[3] * 1.3 or abs(y - spec[2]) > spec[4] * 1.3:
            continue
        best = max(best, _height(spec, x, y))
    w, zr = _ramp(x, y)
    return best + (zr - best) * w if w > 0.0 else best


def pad_point(spec, angle, inset=0.97):
    """Point on the rim of a flat pad (just inside the slope) at the given angle."""
    a = math.radians(angle)
    r = (1.0 - spec[7]) * _outline(spec, a) * inset
    return spec[1] + spec[3] * r * math.cos(a), spec[2] + spec[4] * r * math.sin(a)


def _ring_fractions(band, rx, ry):
    start = 1.0 - band
    n_inner = max(2, int(math.ceil(start * min(rx, ry) / 2.5)))
    inner = [start * i / n_inner for i in range(n_inner)]
    return inner + [start + band * i / _RADIAL_STEPS for i in range(_RADIAL_STEPS + 1)]


def _in_hole(spec, x, y):
    for hx0, hx1, hy0, hy1 in HOLES.get(spec[0], ()):
        if hx0 <= x <= hx1 and hy0 <= y <= hy1:
            return True
    return False


def _build_rock(bm, spec):
    _, cx, cy, rx, ry, _h, _seed, band, _amp, _rough = spec
    fracs = _ring_fractions(band, rx, ry)
    rings = []
    for f in fracs:
        ring = []
        for k in range(_ANGULAR):
            a = 2.0 * math.pi * k / _ANGULAR
            r = f * _outline(spec, a)
            x, y = cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)
            ring.append(bm.verts.new((x, y, 0.0 if f >= 1.0 else _mesh_z(spec, x, y))))
        rings.append(ring)

    rock_faces = []

    def _face(vs):
        f = bm.faces.new(vs)
        f.material_index = MAT_INDEX_CLIFFS
        rock_faces.append(f)

    if fracs[0] == 0.0:
        centre = bm.verts.new((cx, cy, _mesh_z(spec, cx, cy)))
        for k in range(_ANGULAR):
            _face((centre, rings[1][k], rings[1][(k + 1) % _ANGULAR]))
        rings = rings[1:]
    for j in range(len(rings) - 1):
        for k in range(_ANGULAR):
            k2 = (k + 1) % _ANGULAR
            quad = (rings[j][k], rings[j + 1][k], rings[j + 1][k2], rings[j][k2])
            _face(quad)
    edge = rings[-1]
    low = [bm.verts.new((v.co.x, v.co.y, _BOTTOM_Z)) for v in edge]
    for k in range(_ANGULAR):
        k2 = (k + 1) % _ANGULAR
        _face((low[k], low[k2], edge[k2], edge[k]))
    return rock_faces


def _boulder(bm, x, y, radius, seed):
    import bmesh
    res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    verts = res['verts']
    for i, v in enumerate(verts):
        j = 0.62 + 0.55 * (0.5 + 0.5 * math.sin(i * 12.9898 + seed * 78.233))
        v.co.x *= j * 1.15
        v.co.y *= j
        v.co.z *= j * 0.8
        v.co.x += x
        v.co.y += y
        v.co.z += ground_z(x, y) + radius * 0.15
    faces = {f for v in verts for f in v.link_faces}
    for f in faces:
        f.material_index = MAT_INDEX_CLIFFS
    return list(faces)


def _cut_citadel_shaft(bm, cut_box=(-8.6, -5.4, 21.4, 30.0)):
    """Cleanly cuts the stair house shaft out of the rock mount via bisect planes."""
    import bmesh
    from mathutils import Vector
    cand_faces = [f for f in bm.faces if cut_box[0] - 2.0 <= f.calc_center_median().x <= cut_box[1] + 2.0
                  and cut_box[2] - 2.0 <= f.calc_center_median().y <= cut_box[3] + 2.0]
    if not cand_faces:
        cand_faces = bm.faces[:]
    cand_edges = list({e for f in cand_faces for e in f.edges})
    cand_verts = list({v for f in cand_faces for v in f.verts})
    geom = cand_faces + cand_edges + cand_verts
    planes = [
        (Vector((cut_box[0], 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
        (Vector((cut_box[1], 0.0, 0.0)), Vector((1.0, 0.0, 0.0))),
        (Vector((0.0, cut_box[2], 0.0)), Vector((0.0, 1.0, 0.0))),
        (Vector((0.0, cut_box[3], 0.0)), Vector((0.0, 1.0, 0.0))),
    ]
    for pt, norm in planes:
        res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=pt, plane_no=norm)
        geom = res.get('geom', geom)
    to_del = [f for f in bm.faces if (cut_box[0] - 0.001 <= f.calc_center_median().x <= cut_box[1] + 0.001
                                       and cut_box[2] - 0.001 <= f.calc_center_median().y <= cut_box[3] + 0.001)]
    if to_del:
        bmesh.ops.delete(bm, geom=to_del, context='FACES')


def build_citadel_mount(bm):
    """The rocky mount (identical in every tier) plus boulders strewn round its feet."""
    from ..uv_utils import map_planar_faces
    faces = []
    for spec in MOUNT:
        faces += _build_rock(bm, spec)
    n = 0
    for spec in (FORECOURT, TERRACE, CITADEL, EAST_BLUFF):
        count = int(spec[3] * 0.25)
        for i in range(count):
            a = 2.0 * math.pi * (i + 0.37 * (spec[6] % 5)) / count
            n += 1
            rr = _outline(spec, a) * (0.97 + 0.07 * math.sin(n * 7.1))
            x = spec[1] + spec[3] * rr * math.cos(a)
            y = spec[2] + spec[4] * rr * math.sin(a)
            if abs(x) < 10.0 or (-14.0 < x < 0.0 and 17.0 < y < 35.0):
                continue
            faces += _boulder(bm, x, y, 0.9 + 1.6 * (0.5 + 0.5 * math.sin(n * 3.3)), n)
    cliff_faces = [f for f in bm.faces if f.is_valid and f.material_index == MAT_INDEX_CLIFFS]
    map_planar_faces(bm, cliff_faces, scale=1.5)


def _stair_flight(bm, y0, z0, y1, z1, width):
    n = max(3, int(math.ceil((z1 - z0) / 0.17)))
    run = (y1 - y0) / n
    rise = (z1 - z0) / n
    cheek_w = 0.5
    for i in range(n):
        top = z0 + (i + 1) * rise
        ya = y0 + i * run
        yc = ya + run * 0.5
        create_beveled_box(bm, size=(width, run, 1.6), location=(0.0, yc, top - 0.12 - 0.8),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.005)
        create_beveled_box(bm, size=(width, run + 0.07, 0.12), location=(0.0, yc - 0.015, top - 0.06),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for side in (-1.0, 1.0):
            sx = side * (width * 0.5 + cheek_w * 0.5)
            create_beveled_box(bm, size=(cheek_w, run, 1.1 + 0.9), location=(sx, yc, top - 0.12 - 0.2 + 0.05),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.005)

    # Diagonal running railing capping the cheek walls continuously from bottom to top
    dy = y1 - y0
    dz = z1 - z0
    ln = math.hypot(dy, dz)
    pitch = math.atan2(dz, dy)
    yc = (y0 + y1) * 0.5
    zc = (z0 + z1) * 0.5 + 0.88
    rail_w = cheek_w + 0.18
    rail_thick = 0.16
    for side in (-1.0, 1.0):
        sx = side * (width * 0.5 + cheek_w * 0.5)
        create_beveled_box(bm, size=(rail_w, ln + 0.06, rail_thick),
                           location=(sx, yc, zc),
                           rotation=(pitch, 0.0, 0.0),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        if abs(y0 - RAMPS[0][0]) < 0.1:
            create_beveled_box(bm, size=(0.6, 0.6, 1.5), location=(sx, y0, z0 + 0.75),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        if abs(y1 - RAMPS[-1][2]) < 0.1:
            create_beveled_box(bm, size=(0.6, 0.6, 1.5), location=(sx, y1, z1 + 0.75),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)


def _stair_landing(bm, y0, y1, z, width):
    ln = y1 - y0
    yc = (y0 + y1) * 0.5
    create_beveled_box(bm, size=(width, ln, 1.6), location=(0.0, yc, z - 0.12 - 0.8),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.005)
    create_beveled_box(bm, size=(width, ln, 0.12), location=(0.0, yc, z - 0.06),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
    for side in (-1.0, 1.0):
        sx = side * (width * 0.5 + 0.25)
        create_beveled_box(bm, size=(0.5, ln, 0.9 + 0.2), location=(sx, yc, z + 0.45 - 0.1),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.005)
        create_beveled_box(bm, size=(0.7, ln + 0.05, 0.12), location=(sx, yc, z + 0.9 + 0.06),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for end in (y0, y1):
            create_beveled_box(bm, size=(0.6, 0.6, 1.5), location=(side * (width * 0.5 + 0.25), end, z + 0.75),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)


def build_ramp_stairs(bm, width=4.4):
    """Flights of cheeked stone steps with landings laid over every RAMPS corridor."""
    for y0, z0, y1, z1 in RAMPS:
        if abs(z1 - z0) < 1e-6:
            _stair_landing(bm, y0, y1, z0, width)
        else:
            _stair_flight(bm, y0, z0, y1, z1, width)


def _in_boxes(x, y, boxes, margin):
    for bx0, bx1, by0, by1 in boxes:
        if (bx0 - margin <= x <= bx1 + margin) and (by0 - margin <= y <= by1 + margin):
            return True
    return False


def _build_clipped_wall_run(bm, build_run, s, e, outward, boxes, top_z, thick, seed):
    """Build a wall run clipped around building boxes with no pinhole gaps.

    The run is split into quarters; pieces inside a box (0.3 margin) are dropped
    while kept pieces extend 0.35 past their ends so consecutive runs overlap.
    Every piece shares the loop-wide top elevation and reaches 1.5 m into the rock.
    """
    segs = []
    for q in range(4):
        t0, t1 = q / 4.0, (q + 1) / 4.0
        mx = s[0] + (e[0] - s[0]) * (t0 + t1) * 0.5
        my = s[1] + (e[1] - s[1]) * (t0 + t1) * 0.5
        if not _in_boxes(mx, my, boxes, 0.30):
            segs.append((t0, t1))
    if not segs:
        return
    # Merge adjacent kept quarters, then extend each merged piece 0.35 past
    # its ends so runs overlap instead of gapping.
    merged = [segs[0]]
    for t0, t1 in segs[1:]:
        if abs(t0 - merged[-1][1]) < 1e-6:
            merged[-1] = (merged[-1][0], t1)
        else:
            merged.append((t0, t1))
    ln = math.hypot(e[0] - s[0], e[1] - s[1])
    if ln < 0.8:
        return
    ux, uy = (e[0] - s[0]) / ln, (e[1] - s[1]) / ln
    for t0, t1 in merged:
        p0 = (s[0] + (e[0] - s[0]) * t0 - ux * 0.35, s[1] + (e[1] - s[1]) * t0 - uy * 0.35)
        p1 = (s[0] + (e[0] - s[0]) * t1 + ux * 0.35, s[1] + (e[1] - s[1]) * t1 + uy * 0.35)
        zs = ground_z(p0[0], p0[1])
        ze = ground_z(p1[0], p1[1])
        base_z = min(zs, ze) - 1.50
        build_run(bm, p0, p1, outward, base_z, top_z - base_z, thick,
                  slits=False, seed=seed)
    return


def build_flank_connecting_walls(bm, height=3.2, thick=0.85, bld_boxes=()):
    """Build connecting curtain wall runs on the east and west flanks linking
    the lower forecourt rim wall to the upper citadel perimeter wall, closing
    the defensive perimeter gap.
    """
    from .curtain_wall import build_curtain_wall_run

    # West flank: from upper wall at (-29.0, -13.5) down to forecourt rim at (-33.33, -35.39)
    # Goes south so outward vector naturally faces west (exterior).
    chain_west = [(-29.0, -13.5), (-29.5, -18.5), (-30.5, -24.0), (-32.0, -30.0), (-33.33, -35.39)]

    # East flank: from forecourt rim at (32.00, -35.34) up to upper wall at (29.0, -13.5)
    # Goes north so outward vector naturally faces east (exterior).
    chain_east = [(32.00, -35.34), (31.5, -30.0), (30.0, -24.0), (29.5, -18.5), (29.0, -13.5)]

    for chain, seed_base in ((chain_west, 201), (chain_east, 251)):
        sub_pts = []
        for i in range(len(chain) - 1):
            p0, p1 = chain[i], chain[i + 1]
            dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            sub_n = max(1, int(math.ceil(dist / 3.0)))
            for s in range(sub_n):
                t = s / sub_n
                sub_pts.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
        sub_pts.append(chain[-1])

        for i in range(len(sub_pts) - 1):
            s, e = sub_pts[i], sub_pts[i + 1]
            ln = math.hypot(e[0] - s[0], e[1] - s[1])
            if ln < 0.6:
                continue
            outward = ((e[1] - s[1]) / ln, -(e[0] - s[0]) / ln)
            zs = ground_z(s[0], s[1])
            ze = ground_z(e[0], e[1])
            base_z = min(zs, ze) - 1.50
            top_z = max(zs, ze) + height
            wall_h = top_z - base_z
            ux, uy = (e[0] - s[0]) / ln, (e[1] - s[1]) / ln
            p0 = (s[0] - ux * 0.35, s[1] - uy * 0.35)
            p1 = (e[0] + ux * 0.35, e[1] + uy * 0.35)
            _build_clipped_wall_run(bm, build_curtain_wall_run, p0, p1, outward,
                                    bld_boxes, top_z, thick, seed=seed_base + i)


def build_rim_walls(bm, spec, a0, a1, height=3.2, thick=0.8, gap_x=3.2, inset=0.98,
                    gate=True, gate_y=None, bld_boxes=(), connect_upper=True):
    """Crenellated retaining curtain wall along a plateau pad's rim, conforming to cliff terrain with fortified gate and portcullis."""
    from .curtain_wall import build_curtain_wall_run
    from .building_connector import build_curtain_wall_gate_portal
    z = spec[5]
    steps = max(2, int(abs(a1 - a0) / 4.5))
    pts = [pad_point(spec, a0 + (a1 - a0) * i / steps, inset) for i in range(steps + 1)]

    # 1. Curtain wall top elevation matches terrain plus wall height
    top_z = max([ground_z(px, py) for px, py in pts]) + height
    eff_gate_wall_h = top_z - z

    # 2. Gatehouse with portcullis at the central grand stair passage (towers matching wall height)
    eff_gate_y = gate_y
    if eff_gate_y is None:
        if spec[0] == "forecourt_rock":
            eff_gate_y = -48.0
        elif spec[0] == "terrace_rock":
            eff_gate_y = -19.5
        elif spec[0] == "citadel_rock":
            eff_gate_y = 18.0

    if gate and eff_gate_y is not None:
        build_curtain_wall_gate_portal(
            bm, cx=0.0, cy=eff_gate_y, z_ground=z,
            outward=(0.0, -1.0), gate_w=4.8, gate_h=min(eff_gate_wall_h - 0.6, height + 0.4),
            wall_h=eff_gate_wall_h, tower_h=eff_gate_wall_h, thickness=thick + 0.35,
            raised_portcullis=True
        )

    # 3. Curtain wall runs along the plateau rim: one level top everywhere,
    # bases driven 1.5 m through the cliffs, clipped (never gapped) at buildings.
    # The gate opening stays clear including the flanking gate towers.
    for i in range(steps):
        s, e = pts[i], pts[i + 1]
        mid_x = (s[0] + e[0]) * 0.5
        mid_y = (s[1] + e[1]) * 0.5
        if abs(mid_x) < gap_x:
            continue
        if gate and eff_gate_y is not None and abs(mid_x) < 7.2 and abs(mid_y - eff_gate_y) < 6.0:
            continue

        ln = math.hypot(e[0] - s[0], e[1] - s[1])
        if ln < 0.8:
            continue
        outward = ((e[1] - s[1]) / ln, -(e[0] - s[0]) / ln)
        _build_clipped_wall_run(bm, build_curtain_wall_run, s, e, outward,
                                bld_boxes, top_z, thick, seed=i + 7)

    # 4. Connecting walls linking the forecourt rim ends up to the upper citadel perimeter wall
    if connect_upper and spec[0] == "forecourt_rock":
        build_flank_connecting_walls(bm, height=height, thick=thick, bld_boxes=bld_boxes)


def build_upper_citadel_perimeter_wall(bm, height=3.4, thick=0.90, bld_boxes=(), tier=3):
    """
    Constructs the complete perimeter curtain wall loop encircling the entire upper
    castle complex and the East Bluff plateau, conforming continuously to the
    undulating cliff terrain and extending down 1.2m into the cliffs.
    """
    from .curtain_wall import build_curtain_wall_run
    from .building_connector import build_curtain_wall_gate_portal

    # 1. Control waypoints tracing the perimeter along the cliff rims, shifted outwards to clear all buildings.
    # The loop starts/ends clear of the gatehouse towers (outer faces at +-6.9).
    waypoints = [
        # Gate right flank (East arm of Terrace rim)
        (7.2, -19.5),
        (10.0, -19.0),
        (18.0, -18.2),
        (25.0, -16.8),
        (29.0, -13.5),
        # East terrace flank passing cleanly outside the free-standing East Flank Tower
        (39.0, -11.0),
        (39.5, -8.0),
        (39.5, -3.0),
        (37.5, 6.0),
        (36.0, 13.0),
    ]

    if tier >= 3:
        # Promontory around East Bluff (encircling the East Bluff Bastion Tower)
        waypoints += [
            (40.0, 14.0),
            (52.0, 14.0),
            (62.0, 19.0),
            (66.0, 26.0),
            (62.0, 33.0),
            (52.0, 38.0),
            (40.0, 39.0),
            (34.0, 41.0),
        ]
    else:
        # Tier 2 direct east flank up to upper citadel rim
        waypoints += [
            (34.0, 20.0),
            (33.0, 28.0),
            (32.0, 36.0),
            (31.0, 42.0),
        ]

    waypoints += [
        # Citadel north rim behind Archive Hall and Keep
        (28.0, 48.0),
        (20.0, 52.0),
        (10.0, 54.5),
        (0.0, 55.5),
        (-10.0, 54.5),
        (-20.0, 52.0),
        (-28.0, 48.0),
        # West flank around the Wizard's Spire (shifted outwards to clear spire)
        (-34.5, 45.0),
        (-35.5, 40.0),
        (-34.5, 33.0),
        # West flank outside West Connecting Wing and Great Hall
        (-36.0, 24.0),
        (-36.0, 14.0),
        (-37.0, 5.0),
        # Passing cleanly outside the free-standing West Flank Tower
        (-39.5, -3.0),
        (-39.5, -8.0),
        (-39.0, -11.0),
        # Return to gate left flank (clear of the gatehouse towers)
        (-29.0, -13.5),
        (-25.0, -16.8),
        (-18.0, -18.2),
        (-10.0, -19.0),
        (-7.2, -19.5),
    ]

    pts = []
    for i in range(len(waypoints) - 1):
        p0 = waypoints[i]
        p1 = waypoints[i + 1]
        dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        sub_n = max(1, int(math.ceil(dist / 3.2)))
        for s in range(sub_n):
            t = s / sub_n
            pts.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
    pts.append(waypoints[-1])

    # 2. Wall top elevation across loop: max terrain + height
    top_z = max([ground_z(px, py) for px, py in pts]) + height

    # 3. Fortified Gatehouse with twin flanking gate towers matching the wall height exactly
    gate_cx = 0.0
    gate_cy = -19.5
    gate_z = ground_z(gate_cx, gate_cy)
    gate_wall_h = top_z - gate_z
    build_curtain_wall_gate_portal(
        bm, cx=gate_cx, cy=gate_cy, z_ground=gate_z,
        outward=(0.0, -1.0), gate_w=4.8, gate_h=min(gate_wall_h - 1.0, 4.5),
        wall_h=gate_wall_h, tower_h=gate_wall_h, thickness=thick + 0.35,
        raised_portcullis=True
    )

    # 4. Curtain wall runs clipped around buildings with overlapping ends (no gaps).
    for i in range(len(pts) - 1):
        s, e = pts[i], pts[i + 1]

        ln = math.hypot(e[0] - s[0], e[1] - s[1])
        if ln < 0.6:
            continue

        outward = ((e[1] - s[1]) / ln, -(e[0] - s[0]) / ln)
        _build_clipped_wall_run(bm, build_curtain_wall_run, s, e, outward,
                                bld_boxes, top_z, thick, seed=i + 101)


# ---------------------------------------------------------------------------
# Smooth outer curtain wall + tower ring
# ---------------------------------------------------------------------------

# Control points of the wall curve, counter-clockwise from the gate:
# (x, y, first_tier_with_tower, tower_radius, floors). first_tier 0 = no tower here.
_RING = (
    (-24.0, -88.0, 1, 4.8, 3),
    (24.0, -88.0, 1, 4.8, 3),
    (50.0, -94.0, 0, 0.0, 0),
    (84.0, -84.0, 1, 5.6, 4),
    (96.0, -48.0, 0, 0.0, 0),
    (100.0, -6.0, 3, 4.6, 4),
    (95.0, 34.0, 0, 0.0, 0),
    (88.0, 66.0, 1, 5.6, 4),
    (62.0, 90.0, 0, 0.0, 0),
    (28.0, 102.0, 2, 4.6, 4),
    (-8.0, 98.0, 0, 0.0, 0),
    (-40.0, 100.0, 3, 4.6, 4),
    (-72.0, 88.0, 1, 5.6, 4),
    (-94.0, 56.0, 0, 0.0, 0),
    (-100.0, 16.0, 2, 4.6, 4),
    (-96.0, -26.0, 0, 0.0, 0),
    (-93.0, -58.0, 3, 4.6, 3),
    (-84.0, -84.0, 1, 5.6, 4),
    (-50.0, -94.0, 0, 0.0, 0),
)
_GATE_Y = -88.0
_GATE_HALF = 1.8
_GATE_SPAN = 10.0
_WALL = {1: (3.4, 0.5), 2: (4.2, 0.9), 3: (5.4, 1.1)}
_SAMPLE = 3.5


def tier_number(props):
    return {"TIER_1": 1, "TIER_2": 2}.get(getattr(props, 'castle_tier', 'TIER_3'), 3)


def ring_towers(tier):
    """(x, y, radius, floors) of every wall tower present in the tier."""
    return [(v[0], v[1], v[3], v[4]) for v in _RING if v[2] and v[2] <= tier]


def _curve():
    """Closed Catmull-Rom curve through _RING (gate leg kept straight): [(x, y, index_or_None)]."""
    n = len(_RING)
    pts = []
    for i in range(n):
        p1 = _RING[i][:2]
        p2 = _RING[(i + 1) % n][:2]
        pts.append((p1[0], p1[1], i))
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        steps = max(1, int(math.ceil(length / _SAMPLE)))
        if i == 0:
            steps = 1
        p0 = _RING[(i - 1) % n][:2]
        p3 = _RING[(i + 2) % n][:2]
        for s in range(1, steps):
            t = s / steps
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t * t
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t ** 3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t * t
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t ** 3)
            pts.append((x, y, None))
    return pts


def _legs(tier):
    """Curve split into runs between consecutive towers present in the tier."""
    pts = _curve()
    n = len(_RING)
    towers = [i for i in range(n) if _RING[i][2] and _RING[i][2] <= tier]
    start = pts.index(next(p for p in pts if p[2] == towers[0]))
    seq = pts[start:] + pts[:start] + [pts[start]]
    legs, cur = [], [seq[0]]
    for p in seq[1:]:
        cur.append(p)
        if p[2] is not None and p[2] in towers:
            legs.append(cur)
            cur = [p]
    return legs


def _trim_leg(leg, c0, r0, c1, r1):
    pts = [(p[0], p[1]) for p in leg]

    def cut(points, c, r):
        while len(points) > 2 and math.hypot(points[0][0] - c[0], points[0][1] - c[1]) < r:
            if math.hypot(points[1][0] - c[0], points[1][1] - c[1]) >= r:
                ax, ay = points[0]
                bx, by = points[1]
                dx, dy = bx - ax, by - ay
                fx, fy = ax - c[0], ay - c[1]
                a = dx * dx + dy * dy
                b = 2 * (fx * dx + fy * dy)
                cc = fx * fx + fy * fy - r * r
                disc = max(0.0, b * b - 4 * a * cc)
                t = (-b + math.sqrt(disc)) / (2 * a)
                points[0] = (ax + dx * t, ay + dy * t)
                return points
            points.pop(0)
        return points

    if r0:
        pts = cut(pts, c0, r0)
    if r1:
        pts = cut(pts[::-1], c1, r1)[::-1]
    return pts


def _build_ring_towers(bm, tier):
    from .castle import build_walkable_round_tower
    from .bastion import build_rickety_frame_tower
    from .building_connector import carve_pass_through_portal
    for x, y, r, floors in ring_towers(tier):
        face_in = math.atan2(-y, -x)
        if tier == 1:
            inset = r * 0.375 + 1.4
            build_rickety_frame_tower(
                bm, x + math.cos(face_in) * inset, y + math.sin(face_in) * inset, z_ground=0.0,
                base_size=r * 0.75, height=9.5, door_dir=(math.cos(face_in), math.sin(face_in)))
        else:
            # Guarantee the circular interior of the tower is completely open and walkable
            wall_t = 0.75 if r >= 3.4 else 0.6
            inner_r = r - wall_t
            to_del = [f for f in bm.faces if f.is_valid and
                      math.hypot(f.calc_center_median().x - x, f.calc_center_median().y - y) < inner_r - 0.05 and
                      0.0 <= f.calc_center_median().z <= (floors + 2) * 4.2]
            if to_del:
                import bmesh
                bmesh.ops.delete(bm, geom=to_del, context='FACES')
            z_base = min(0.0, ground_z(x, y) - 0.5)
            build_walkable_round_tower(
                bm, cx=x, cy=y, z_base=z_base, radius=r,
                num_floors=floors if tier == 2 else floors + 1,
                floor_h=4.0 if tier == 2 else 4.2, tower_type='BATTLEMENTS',
                door_angs=((0, face_in),))


def _pieces(p0, p1, max_len=_SAMPLE):
    n = max(1, int(math.ceil(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / max_len)))
    pts = [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n)
           for i in range(n + 1)]
    return list(zip(pts[:-1], pts[1:]))


def build_nasher_enclosure(bm, props, ctx):
    """Smooth curtain wall (palisade in T1) with a south gate; runs stop at tower surfaces."""
    from .curtain_wall import build_curtain_wall_run, build_gate_house, gate_stair_top_offset
    from .palisade import build_palisade_run, _gate_post

    tier = tier_number(props)
    height, thick = _WALL[tier]
    centres = {i: (v[0], v[1], v[3]) for i, v in enumerate(_RING) if v[2] and v[2] <= tier}

    for li, leg in enumerate(_legs(tier)):
        ia, ib = leg[0][2], leg[-1][2]
        ca, cb = centres[ia], centres[ib]
        gate_leg = (ia == 0 and ib == 1)
        if tier == 1:
            pts = [(p[0], p[1]) for p in leg]
        else:
            # Embed the full wall width into the tower masonry (trim inside the
            # tower wall, never short of its face) so no gap opens at the joint
            # and no wall face survives inside the tower room (the tower wall
            # is 0.6-0.75 thick solid stone, hiding the embed completely).
            pts = _trim_leg(leg, ca[:2], max(0.5, ca[2] - 0.45), cb[:2], max(0.5, cb[2] - 0.45))

        if gate_leg:
            parts = (_pieces(pts[0], (-_GATE_SPAN, _GATE_Y))
                     + [((-_GATE_SPAN, _GATE_Y), (_GATE_SPAN, _GATE_Y))]
                     + _pieces((_GATE_SPAN, _GATE_Y), pts[-1]))
        else:
            parts = list(zip(pts[:-1], pts[1:]))

        for j, (s, e) in enumerate(parts):
            ln = math.hypot(e[0] - s[0], e[1] - s[1])
            if ln < 0.3:
                continue
            outward = ((e[1] - s[1]) / ln, -(e[0] - s[0]) / ln)
            gate_piece = gate_leg and s == (-_GATE_SPAN, _GATE_Y)
            seed = ctx.seed + li * 11 + j
            if tier == 1:
                gaps = [(-_GATE_HALF, _GATE_HALF)] if gate_piece else None
                build_palisade_run(bm, s, e, 0.0, height, 'STAKES', gaps=gaps, seed=seed)
            elif gate_piece:
                build_curtain_wall_run(
                    bm, s, e, outward, 0.0, height, thick, seed=seed,
                    gate={'u0': _GATE_SPAN - _GATE_HALF, 'u1': _GATE_SPAN + _GATE_HALF,
                          'h': 3.0, 'breach': gate_stair_top_offset(True) + 1.5})
            else:
                build_curtain_wall_run(bm, s, e, outward, 0.0, height, thick, seed=seed)

    _build_ring_towers(bm, tier)

    if tier == 1:
        _gate_post(bm, -_GATE_HALF, _GATE_Y, 0.0, height)
        _gate_post(bm, _GATE_HALF, _GATE_Y, 0.0, height)
    else:
        build_gate_house(bm, 0.0, _GATE_Y, (0.0, -1.0), _GATE_HALF * 2.0, 0.0, thick,
                         gate_h=3.0, portcullis=getattr(props, 'has_portcullis', False),
                         drawbridge=getattr(props, 'has_drawbridge', False),
                         drawbridge_angle=getattr(props, 'drawbridge_angle', 0.0),
                         gate_towers=getattr(props, 'has_gate_towers', False), wall_h=height)
