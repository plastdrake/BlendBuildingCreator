"""
Generic street and yard furniture (cozy, hand-built, chunky stylized).

Every builder models its prop once at a local origin and then drops it into the
world with a single transform, so a barrel can just as easily stand in a tavern
beer garden, a warehouse yard or a market square. Nothing here knows what
building it belongs to - that composition lives in ``hospitality.py`` and the
other archetype composers.

The look targets robust hand-made game props: thick members, visible plank
seams, hand-forged iron banding and a touch of deterministic wonkiness so no
two pieces read as machine-perfect.
"""

import math
import random
from mathutils import Matrix

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_torus_ring, transform_faces,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_IRON, MAT_INDEX_WOOD,
)


def _place(x, y, z_ground=0.0, ang=0.0, extra=None):
    """Local-to-world matrix: grounding translation, yaw, then an optional tilt."""
    mat = Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')
    if extra is not None:
        mat = mat @ extra
    return mat


def _rng(x, y, salt=0):
    return random.Random((int(abs(x) * 73856093) ^ int(abs(y) * 19349663) ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _barrel_shell(bm, radius, height, segments, rng, mat_index=MAT_INDEX_TIMBER):
    """A lathe-turned staved shell: narrower at the ends, bulging at the waist."""
    z_profile = [(-0.50, 0.80), (-0.30, 0.94), (-0.08, 1.00),
                 (0.08, 1.00), (0.30, 0.94), (0.50, 0.80)]
    rings = []
    for t, rf in z_profile:
        ring = []
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            wob = 1.0 + (rng.random() - 0.5) * 0.035
            rr = radius * rf * wob
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), t * height)))
        rings.append(ring)

    uv_layer = bm.loops.layers.uv.verify()
    circumference = 2.0 * math.pi * radius
    faces = []
    for s in range(len(rings) - 1):
        z0 = z_profile[s][0] * height + height * 0.5
        z1 = z_profile[s + 1][0] * height + height * 0.5
        for i in range(segments):
            j = (i + 1) % segments
            f = bm.faces.new([rings[s][i], rings[s][j], rings[s + 1][j], rings[s + 1][i]])
            f.material_index = mat_index
            u0 = circumference * i / segments
            u1 = circumference * (i + 1) / segments
            f.loops[0][uv_layer].uv = (u0, z0)
            f.loops[1][uv_layer].uv = (u1, z0)
            f.loops[2][uv_layer].uv = (u1, z1)
            f.loops[3][uv_layer].uv = (u0, z1)
            faces.append(f)

    top = bm.faces.new(list(rings[-1]))
    bot = bm.faces.new(list(reversed(rings[0])))
    for cap, zc in ((top, height * 0.5), (bot, -height * 0.5)):
        cap.material_index = mat_index
        for loop in cap.loops:
            loop[uv_layer].uv = (loop.vert.co.x, loop.vert.co.y)
        faces.append(cap)
    return faces


def build_barrel(bm, x, y, z_ground=0.0, ang=0.0, radius=0.34, height=0.74, lying=False):
    """A chunky fantasy ale barrel with bulging staves, 4 forged iron hoops with rivets and a bung."""
    rng = _rng(x, y, 1)
    r, h = radius, height
    faces = []
    # Bulging barrel shell with stave UVs
    faces += _barrel_shell(bm, r, h, 14, rng, mat_index=MAT_INDEX_WOOD)

    # Recessed top and bottom wooden lids (chime rims)
    lid_r = r * 0.82
    for lid_z in (-(h * 0.5 - 0.04), h * 0.5 - 0.04):
        faces += create_cylinder(bm, radius=lid_r, height=0.03, segments=14,
                                 location=(0.0, 0.0, lid_z), mat_index=MAT_INDEX_TIMBER)
        # Plank lines across the lid
        for off in (-lid_r * 0.45, 0.0, lid_r * 0.45):
            faces += create_beveled_box(
                bm, size=(lid_r * 1.8, 0.02, 0.015),
                location=(0.0, off, lid_z + (0.015 if lid_z > 0 else -0.015)),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.002)

    # 4 Forged iron hoops: 2 chime hoops at ends, 2 quarter hoops around the bulge
    hoop_profiles = [
        (-h * 0.42, r * 0.85, 0.045),  # bottom chime
        (-h * 0.16, r * 0.98, 0.040),  # lower bilge
        ( h * 0.16, r * 0.98, 0.040),  # upper bilge
        ( h * 0.42, r * 0.85, 0.045),  # top chime
    ]
    for hz, hr, hw in hoop_profiles:
        faces += create_torus_ring(bm, location=(0.0, 0.0, hz),
                                   major_radius=hr + 0.010, minor_radius=0.018,
                                   major_segments=14, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)
        # Forged iron square rivets / lugs around each hoop
        for ai in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
            faces += create_beveled_box(
                bm, size=(0.022, 0.022, 0.022),
                location=((hr + 0.022) * math.cos(ai), (hr + 0.022) * math.sin(ai), hz),
                rotation=(0.0, 0.0, ai),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

    # Wooden bung / tap plug on the belly
    faces += create_cylinder(bm, radius=0.028, height=0.06, segments=8,
                             location=(r + 0.02, 0.0, 0.0),
                             rotation=(0.0, math.pi * 0.5, 0.0),
                             mat_index=MAT_INDEX_WOOD)

    if lying:
        # Timber cradle / chock blocks underneath so lying barrels don't roll or float
        cradle_mat = _place(x, y, z_ground, ang)
        chock_faces = []
        for cx in (-h * 0.28, h * 0.28):
            chock_faces += create_beveled_box(
                bm, size=(0.10, r * 1.6, r * 0.45),
                location=(cx, 0.0, r * 0.22),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
        transform_faces(chock_faces, cradle_mat)
        faces += chock_faces

        mat = _place(x, y, z_ground + r + 0.04, ang, extra=Matrix.Rotation(math.pi * 0.5, 4, 'Y'))
    else:
        mat = _place(x, y, z_ground + h * 0.5, ang)

    transform_faces(faces, mat)
    return faces


def build_crate(bm, x, y, z_ground=0.0, ang=0.0, size=0.58):
    """A chunky fantasy RPG shipping crate with heavy timber frame, X-bracing, and iron corner straps."""
    s = size
    rng = _rng(x, y, 2)
    faces = []

    # 1. Inner planked core box
    faces += create_beveled_box(bm, size=(s * 0.94, s * 0.94, s * 0.94),
                                location=(0.0, 0.0, s * 0.5),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

    # 2. Chunky square timber corner posts
    b = s * 0.14
    for cx in (-s * 0.5 + b * 0.5, s * 0.5 - b * 0.5):
        for cy in (-s * 0.5 + b * 0.5, s * 0.5 - b * 0.5):
            j = (rng.random() - 0.5) * 0.008
            faces += create_beveled_box(
                bm, size=(b, b, s + 0.01),
                location=(cx, cy, s * 0.5 + j),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # 3. Heavy top and bottom framing perimeter rails
    for rz in (b * 0.5, s - b * 0.5):
        for face_rot in (0.0, math.pi * 0.5):
            faces += create_beveled_box(
                bm, size=(s - b * 1.8, b, b * 0.85),
                location=(0.0, s * 0.5 - b * 0.5, rz),
                rotation=(0.0, 0.0, face_rot),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
            faces += create_beveled_box(
                bm, size=(s - b * 1.8, b, b * 0.85),
                location=(0.0, -(s * 0.5 - b * 0.5), rz),
                rotation=(0.0, 0.0, face_rot),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)

    # 4. Diagonal X-brace timber battens on all 4 vertical faces
    diag_len = math.hypot(s - b * 1.6, s - b * 1.6)
    diag_ang = math.atan2(s - b * 1.6, s - b * 1.6)
    for face_rot in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        for d_sign in (-1.0, 1.0):
            faces += create_beveled_box(
                bm, size=(diag_len, b * 0.72, 0.024),
                location=(0.0, s * 0.5 - b * 0.42, s * 0.5),
                rotation=(0.0, d_sign * diag_ang, face_rot),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)

    # 5. Forged iron corner L-plates on all 8 corners
    strap_len = b * 1.8
    strap_t = 0.025
    for cz in (strap_len * 0.45, s - strap_len * 0.45):
        for corner in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            faces += create_beveled_box(
                bm, size=(b * 1.2, b * 0.42, strap_t),
                location=(corner[0] * (s * 0.5 - b * 0.6), corner[1] * (s * 0.5 - b * 0.22), cz),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
            faces += create_beveled_box(
                bm, size=(b * 0.42, b * 1.2, strap_t),
                location=(corner[0] * (s * 0.5 - b * 0.22), corner[1] * (s * 0.5 - b * 0.6), cz),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_sack(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """A plump burlap sack of grain, tied at the neck."""
    s = scale
    rng = _rng(x, y, 3)
    faces = []
    faces += create_cylinder(bm, radius=0.28 * s, height=0.42 * s, segments=12,
                             location=(0.0, 0.0, 0.21 * s), mat_index=MAT_INDEX_TIMBER)
    faces += create_cylinder(bm, radius=0.32 * s, height=0.18 * s, segments=12,
                             location=(0.0, 0.0, 0.26 * s), mat_index=MAT_INDEX_TIMBER)
    faces += create_cylinder(bm, radius=0.22 * s, height=0.20 * s, segments=10,
                             location=(0.0, 0.0, 0.48 * s), mat_index=MAT_INDEX_TIMBER)
    # Tied neck with rope cord
    faces += create_torus_ring(bm, location=(0.0, 0.0, 0.58 * s), major_radius=0.10 * s,
                               minor_radius=0.022 * s, major_segments=10, minor_segments=6,
                               mat_index=MAT_INDEX_WOOD)
    # Frilled bag opening
    faces += create_cone(bm, radius1=0.09 * s, radius2=0.16 * s, height=0.12 * s, segments=8,
                         location=(0.0, 0.0, 0.65 * s), mat_index=MAT_INDEX_TIMBER)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_stool(bm, x, y, z_ground=0.0, ang=0.0, radius=0.22, height=0.48):
    """A chunky three-legged pine taproom stool with carved seat and stretchers."""
    rng = _rng(x, y, 4)
    # Thick carved round seat
    faces = []
    faces += create_cylinder(bm, radius=radius, height=0.075, segments=14,
                             location=(0.0, 0.0, height), mat_index=MAT_INDEX_WOOD)
    faces += create_cylinder(bm, radius=radius * 0.92, height=0.035, segments=14,
                             location=(0.0, 0.0, height - 0.04), mat_index=MAT_INDEX_TIMBER)

    # 3 Splayed chunky timber legs
    for i in range(3):
        a = (2.0 * math.pi * i / 3.0) + 0.4
        lx, ly = math.cos(a) * radius * 0.62, math.sin(a) * radius * 0.62
        tilt = 0.16
        faces += create_beveled_box(
            bm, size=(0.07, 0.07, height),
            location=(lx, ly, height * 0.5),
            rotation=(math.sin(a + math.pi * 0.5) * tilt, -math.cos(a + math.pi * 0.5) * tilt, a),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Braced cross stretchers with protruding wooden pins
    for i in range(3):
        a0 = (2.0 * math.pi * i / 3.0) + 0.4
        a1 = (2.0 * math.pi * ((i + 1) % 3) / 3.0) + 0.4
        p0 = (math.cos(a0) * radius * 0.52, math.sin(a0) * radius * 0.52)
        p1 = (math.cos(a1) * radius * 0.52, math.sin(a1) * radius * 0.52)
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        seg = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        faces += create_beveled_box(
            bm, size=(seg, 0.04, 0.04),
            location=(mx, my, height * 0.24),
            rotation=(0.0, 0.0, math.atan2(p1[1] - p0[1], p1[0] - p0[0])),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bench(bm, x, y, z_ground=0.0, ang=0.0, length=1.75, with_back=True):
    """A heavy hand-hewn fantasy timber bench with wedged legs and backrest."""
    L = length
    rng = _rng(x, y, 5)
    seat_z = 0.48
    seat_d = 0.40
    faces = []

    # Chunky slab seat (thick hand-hewn timber with heavy bevels)
    faces += create_beveled_box(bm, size=(L, seat_d, 0.08),
                                location=(0.0, 0.0, seat_z),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.016, bevel_segments=2)

    # 4 Heavy splayed timber legs (0.10m x 0.10m)
    leg_w = 0.10
    for sx in (-L * 0.5 + 0.20, L * 0.5 - 0.20):
        for sy, splay in ((-seat_d * 0.30, -0.12), (seat_d * 0.30, 0.12)):
            faces += create_beveled_box(
                bm, size=(leg_w, leg_w, seat_z),
                location=(sx, sy, seat_z * 0.5 - 0.02),
                rotation=(splay, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

        # End cross stretchers tying the legs together
        faces += create_beveled_box(bm, size=(leg_w * 0.8, seat_d * 0.88, 0.07),
                                    location=(sx, 0.0, 0.16),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        # Protruding wooden through-tenon wedge pegs
        faces += create_beveled_box(bm, size=(leg_w * 1.3, 0.04, 0.04),
                                    location=(sx, 0.0, 0.16),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)

    # Longitudinal center stretcher
    faces += create_beveled_box(bm, size=(L - 0.36, 0.07, 0.07),
                                location=(0.0, 0.0, 0.16),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)

    if with_back:
        # Tilted backrest posts with forged iron support braces
        post_h = 0.52
        tilt = 0.16
        for sx in (-L * 0.5 + 0.18, L * 0.5 - 0.18):
            faces += create_beveled_box(
                bm, size=(0.08, 0.08, post_h),
                location=(sx, seat_d * 0.42 + 0.04, seat_z + post_h * 0.5),
                rotation=(-tilt, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
            # Forged iron support bracket strap
            faces += create_beveled_box(
                bm, size=(0.035, 0.12, 0.22),
                location=(sx, seat_d * 0.42, seat_z + 0.08),
                rotation=(-tilt * 0.5, 0.0, 0.0),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

        # Two heavy horizontal backrest planks
        for bz_off, bh in ((0.22, 0.12), (0.40, 0.12)):
            faces += create_beveled_box(
                bm, size=(L, 0.065, bh),
                location=(0.0, seat_d * 0.44 + bz_off * math.sin(tilt) + 0.04, seat_z + bz_off),
                rotation=(-tilt, 0.0, 0.0),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_picnic_table(bm, x, y, z_ground=0.0, ang=0.0, length=2.05):
    """A massive hand-hewn fantasy tavern picnic table with heavy trestles, wedge pegs and benches."""
    L = length
    rng = _rng(x, y, 6)
    top_z = 0.78
    seat_z = 0.46
    faces = []

    # 1. Table top: 3 massive timber slabs with hand-carved chamfers and wonky plank seams
    plank_w = 0.28
    gap = 0.012
    top_thick = 0.085
    for k, dy in enumerate((-plank_w - gap, 0.0, plank_w + gap)):
        j = (rng.random() - 0.5) * 0.008
        faces += create_beveled_box(
            bm, size=(L, plank_w, top_thick),
            location=(0.0, dy, top_z + j),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.016, bevel_segments=2)

    # 2. Attached bench seats on both sides (each made of a chunky thick timber slab)
    bench_w = 0.25
    bench_thick = 0.075
    bench_y_dist = 0.65
    for side_y in (-bench_y_dist, bench_y_dist):
        faces += create_beveled_box(
            bm, size=(L, bench_w, bench_thick),
            location=(0.0, side_y, seat_z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)

    # 3. Massive timber A-frame trestle leg assemblies at each end
    leg_w = 0.13
    for sx in (-L * 0.5 + 0.36, L * 0.5 - 0.36):
        jx = (rng.random() - 0.5) * 0.010
        splay = 0.68
        # Splayed trestle legs supporting the table top
        for s in (-1.0, 1.0):
            faces += create_beveled_box(
                bm, size=(leg_w, leg_w, top_z),
                location=(sx + jx, s * 0.28, top_z * 0.5),
                rotation=(s * splay, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)

        # Massive horizontal cross-bearer beam supporting both the table top and side benches
        faces += create_beveled_box(
            bm, size=(leg_w, bench_y_dist * 2.0 + bench_w * 0.6, 0.10),
            location=(sx + jx, 0.0, seat_z - bench_thick * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

        # Protruding through-tenons with wooden wedge pegs on the trestles
        for s in (-1.0, 1.0):
            faces += create_beveled_box(
                bm, size=(leg_w * 1.35, 0.045, 0.045),
                location=(sx + jx, s * bench_y_dist, seat_z - bench_thick * 0.5),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005)

        # Diagonal knee-brace supports under the table top
        for s in (-1.0, 1.0):
            brace_diag = math.hypot(0.24, 0.22)
            faces += create_beveled_box(
                bm, size=(0.07, 0.07, brace_diag),
                location=(sx + jx, s * 0.16, top_z - 0.14),
                rotation=(-s * 0.85, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)

    # 4. Heavy longitudinal tie-beam stretcher running under the table
    faces += create_beveled_box(
        bm, size=(L - 0.40, 0.09, 0.10),
        location=(0.0, 0.0, 0.28),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # Wooden wedge keys pinning the center tie beam
    for sx in (-L * 0.5 + 0.22, L * 0.5 - 0.22):
        faces += create_beveled_box(
            bm, size=(0.04, 0.15, 0.08),
            location=(sx, 0.0, 0.28),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces

