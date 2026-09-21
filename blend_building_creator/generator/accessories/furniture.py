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
    create_beveled_box, create_cylinder, create_cone, create_torus_ring, transform_faces,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_IRON, MAT_INDEX_WOOD,
    MAT_INDEX_CLAY, MAT_INDEX_HAY,
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

    return faces


def build_barrel(bm, x, y, z_ground=0.0, ang=0.0, radius=0.34, height=0.74, lying=False):
    """A clean fantasy timber ale barrel with bulging staves and smooth forged iron hoops."""
    rng = _rng(x, y, 1)
    r, h = radius, height
    faces = []
    # Bulging barrel shell with stave UVs
    faces += _barrel_shell(bm, r, h, 14, rng, mat_index=MAT_INDEX_WOOD)

    # Clearly visible top and bottom wooden lids
    lid_r = r * 0.86
    for lid_z in (-(h * 0.5 - 0.012), h * 0.5 - 0.012):
        faces += create_cylinder(bm, radius=lid_r, height=0.024, segments=14,
                                 location=(0.0, 0.0, lid_z), mat_index=MAT_INDEX_TIMBER)
        # Plank lines across the lid
        for off in (-lid_r * 0.45, 0.0, lid_r * 0.45):
            faces += create_beveled_box(
                bm, size=(lid_r * 1.8, 0.02, 0.012),
                location=(0.0, off, lid_z + (0.012 if lid_z > 0 else -0.012)),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.002)

    # 4 Clean forged iron hoops (no rivets/nails, smooth bands)
    hoop_profiles = [
        (-h * 0.42, r * 0.85, 0.045),  # bottom chime
        (-h * 0.16, r * 0.98, 0.040),  # lower bilge
        ( h * 0.16, r * 0.98, 0.040),  # upper bilge
        ( h * 0.42, r * 0.85, 0.045),  # top chime
    ]
    for hz, hr, hw in hoop_profiles:
        faces += create_torus_ring(bm, location=(0.0, 0.0, hz),
                                   major_radius=hr + 0.008, minor_radius=0.016,
                                   major_segments=14, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)

    if lying:
        mat = _place(x, y, z_ground + r + 0.04, ang, extra=Matrix.Rotation(math.pi * 0.5, 4, 'Y'))
        transform_faces(faces, mat)

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
    else:
        mat = _place(x, y, z_ground + h * 0.5, ang)
        transform_faces(faces, mat)

    return faces


def build_crate(bm, x, y, z_ground=0.0, ang=0.0, size=0.58, height=None, depth=None, brace_style='DIAGONAL'):
    """
    A chunky fantasy RPG shipping crate with clean framing, corner caps with iron pins,
    and diagonal braces matching reference art:
    - Inner recessed plank core box (MAT_INDEX_WOOD)
    - 4 vertical timber corner posts (MAT_INDEX_TIMBER)
    - 4 top and 4 bottom perimeter framing rails (MAT_INDEX_TIMBER)
    - Diagonal timber braces flush inside the recessed panel faces
    - Chunky beveled corner caps with iron stud pins on all 8 corners
    - Flush plank lid detailing on top
    - Strictly bounded: NOTHING sticks out past the crate perimeter!
    """
    sx = size
    sy = depth if depth is not None else size
    sz = height if height is not None else size
    b = min(sx, sy, sz) * 0.14  # beam member thickness
    faces = []

    # 1. Inner recessed planked core box
    recess = b * 0.35
    core_sx = sx - recess * 2.0
    core_sy = sy - recess * 2.0
    core_sz = sz - recess * 2.0
    faces += create_beveled_box(
        bm, size=(core_sx, core_sy, core_sz),
        location=(0.0, 0.0, sz * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )

    # 2. 4 Vertical Timber Corner Posts
    for cx in (-sx * 0.5 + b * 0.5, sx * 0.5 - b * 0.5):
        for cy in (-sy * 0.5 + b * 0.5, sy * 0.5 - b * 0.5):
            faces += create_beveled_box(
                bm, size=(b, b, sz),
                location=(cx, cy, sz * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )

    # 3. Horizontal Perimeter Rails (Top and Bottom)
    rail_x_len = max(0.06, sx - b * 2.0)
    rail_y_len = max(0.06, sy - b * 2.0)
    for rz in (b * 0.5, sz - b * 0.5):
        # Front & Back rails (along X)
        for cy in (-sy * 0.5 + b * 0.5, sy * 0.5 - b * 0.5):
            faces += create_beveled_box(
                bm, size=(rail_x_len, b, b),
                location=(0.0, cy, rz),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )
        # Left & Right rails (along Y)
        for cx in (-sx * 0.5 + b * 0.5, sx * 0.5 - b * 0.5):
            faces += create_beveled_box(
                bm, size=(b, rail_y_len, b),
                location=(cx, 0.0, rz),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )

    # 4. Diagonal Bracing inside recessed panel walls
    span_h = max(0.06, sz - b * 2.0)
    diag_t = b * 0.35
    diag_w = b * 0.68

    # Front & Back faces (span along X)
    diag_lx = math.hypot(rail_x_len, span_h)
    diag_ang_x = math.atan2(span_h, rail_x_len)
    for cy_sign in (-1.0, 1.0):
        fy = cy_sign * (sy * 0.5 - b * 0.5)
        if brace_style in ('DIAGONAL', 'CROSS'):
            faces += create_beveled_box(
                bm, size=(diag_lx, diag_t, diag_w),
                location=(0.0, fy, sz * 0.5),
                rotation=(0.0, -diag_ang_x, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
            )
        if brace_style == 'CROSS':
            faces += create_beveled_box(
                bm, size=(diag_lx, diag_t, diag_w),
                location=(0.0, fy, sz * 0.5),
                rotation=(0.0, diag_ang_x, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
            )

    # Left & Right faces (span along Y)
    diag_ly = math.hypot(rail_y_len, span_h)
    diag_ang_y = math.atan2(span_h, rail_y_len)
    for cx_sign in (-1.0, 1.0):
        fx = cx_sign * (sx * 0.5 - b * 0.5)
        if brace_style in ('DIAGONAL', 'CROSS'):
            faces += create_beveled_box(
                bm, size=(diag_t, diag_ly, diag_w),
                location=(fx, 0.0, sz * 0.5),
                rotation=(diag_ang_y, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
            )
        if brace_style == 'CROSS':
            faces += create_beveled_box(
                bm, size=(diag_t, diag_ly, diag_w),
                location=(fx, 0.0, sz * 0.5),
                rotation=(-diag_ang_y, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
            )

    # 5. Chunky Corner Caps with Iron Stud Pins on all 8 corners
    for cx_sign in (-1.0, 1.0):
        for cy_sign in (-1.0, 1.0):
            cx = cx_sign * (sx * 0.5 - b * 0.5)
            cy = cy_sign * (sy * 0.5 - b * 0.5)
            for cz_sign in (-1.0, 1.0):
                cz = sz * 0.5 + cz_sign * (sz * 0.5 - b * 0.16)
                # Corner bracket cap block
                faces += create_beveled_box(
                    bm, size=(b * 1.15, b * 1.15, b * 0.32),
                    location=(cx, cy, cz),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
                )
                # Forged iron nail studs
                faces += create_cylinder(
                    bm, radius=0.009, height=0.012, segments=6,
                    location=(cx + cx_sign * (b * 0.58), cy, cz),
                    rotation=(0.0, 1.57, 0.0),
                    mat_index=MAT_INDEX_IRON
                )
                faces += create_cylinder(
                    bm, radius=0.009, height=0.012, segments=6,
                    location=(cx, cy + cy_sign * (b * 0.58), cz),
                    rotation=(1.57, 0.0, 0.0),
                    mat_index=MAT_INDEX_IRON
                )

    # 6. Plank Detailing on Top Lid
    for off in (-rail_y_len * 0.30, 0.0, rail_y_len * 0.30):
        faces += create_beveled_box(
            bm, size=(rail_x_len, 0.018, 0.006),
            location=(0.0, off, sz - 0.003),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.002
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_clay_pot(bm, x, y, z_ground=0.0, ang=0.0, radius=0.22, height=0.48, pot_type='JAR'):
    """
    A smooth, stylized terracotta/earthenware pottery jar, urn or jug with a carved wooden lid/bung.
    - Smooth 16-segment lathe-turned profile (smooth round silhouette)
    - UV unwrap mapped for MAT_INDEX_CLAY
    - Carved wooden stopper/lid with handle knob (MAT_INDEX_WOOD / MAT_INDEX_TIMBER)
    - Optional clay ear handles
    """
    r, h = radius, height
    faces = []

    # 1. Profile selection
    if pot_type == 'URN':
        # Bulbous round storage pot
        z_profile = [
            (0.00, 0.60),  # base foot
            (0.06, 0.66),  # foot flare
            (0.20, 0.94),  # lower swell
            (0.42, 1.00),  # wide belly
            (0.65, 0.88),  # tapering shoulder
            (0.82, 0.56),  # neck constriction
            (0.92, 0.64),  # rolled rim lip
            (1.00, 0.60),  # rim top
        ]
    elif pot_type == 'JUG':
        # Taller jug / pitcher profile
        z_profile = [
            (0.00, 0.55),
            (0.06, 0.60),
            (0.26, 0.96),
            (0.48, 0.94),
            (0.68, 0.74),
            (0.84, 0.46),
            (0.93, 0.54),
            (1.00, 0.50),
        ]
    else:  # 'JAR'
        # Standard wide-mouth storage jar
        z_profile = [
            (0.00, 0.62),
            (0.06, 0.68),
            (0.22, 0.95),
            (0.45, 1.00),
            (0.70, 0.84),
            (0.85, 0.58),
            (0.93, 0.66),
            (1.00, 0.62),
        ]

    segments = 16  # Smooth curved geometry
    rings = []
    for zn, rn in z_profile:
        ring = []
        cur_z = zn * h
        cur_r = rn * r
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            ring.append(bm.verts.new((cur_r * math.cos(a), cur_r * math.sin(a), cur_z)))
        rings.append(ring)

    uv_layer = bm.loops.layers.uv.verify()
    circumference = 2.0 * math.pi * r

    # Lathe faces
    for s in range(len(rings) - 1):
        z0 = z_profile[s][0] * h
        z1 = z_profile[s + 1][0] * h
        for i in range(segments):
            j = (i + 1) % segments
            f = bm.faces.new([rings[s][i], rings[s][j], rings[s + 1][j], rings[s + 1][i]])
            f.material_index = MAT_INDEX_CLAY
            u0 = circumference * i / segments
            u1 = circumference * (i + 1) / segments
            f.loops[0][uv_layer].uv = (u0, z0)
            f.loops[1][uv_layer].uv = (u1, z0)
            f.loops[2][uv_layer].uv = (u1, z1)
            f.loops[3][uv_layer].uv = (u0, z1)
            faces.append(f)

    # Bottom cap
    bot = bm.faces.new(list(reversed(rings[0])))
    bot.material_index = MAT_INDEX_CLAY
    for loop in bot.loops:
        loop[uv_layer].uv = (loop.vert.co.x + r, loop.vert.co.y + r)
    faces.append(bot)

    # 2. Carved Wooden Lid / Bung Stopper (MAT_INDEX_WOOD)
    neck_r = z_profile[-3][1] * r
    rim_r = z_profile[-1][1] * r

    # Plug into rim
    faces += create_cylinder(
        bm, radius=neck_r * 0.94, height=0.035, segments=16,
        location=(0.0, 0.0, h - 0.005),
        mat_index=MAT_INDEX_WOOD
    )
    # Flanged lid rim over pot mouth
    faces += create_cylinder(
        bm, radius=rim_r * 1.05, height=0.035, segments=16,
        location=(0.0, 0.0, h + 0.02),
        mat_index=MAT_INDEX_WOOD
    )
    # Turned wooden knob / grip
    faces += create_cylinder(
        bm, radius=0.032, height=0.032, segments=10,
        location=(0.0, 0.0, h + 0.046),
        mat_index=MAT_INDEX_TIMBER
    )

    # 3. Optional Clay Ear Handles (for JUG / URN)
    if pot_type in ('JUG', 'URN'):
        for h_sign in (-1.0, 1.0) if pot_type == 'URN' else (1.0,):
            hx = h_sign * (r * 0.88)
            hz = h * 0.72
            faces += create_torus_ring(
                bm, location=(hx, 0.0, hz),
                major_radius=0.065, minor_radius=0.016,
                major_segments=10, minor_segments=6,
                mat_index=MAT_INDEX_CLAY
            )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_sack(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """A plump burlap sack of grain, tied at the neck with rope cord."""
    s = scale
    faces = []
    # Smooth curved burlap body (MAT_INDEX_HAY)
    faces += create_cylinder(bm, radius=0.28 * s, height=0.42 * s, segments=14,
                             location=(0.0, 0.0, 0.21 * s), mat_index=MAT_INDEX_HAY)
    faces += create_cylinder(bm, radius=0.32 * s, height=0.18 * s, segments=14,
                             location=(0.0, 0.0, 0.26 * s), mat_index=MAT_INDEX_HAY)
    faces += create_cylinder(bm, radius=0.22 * s, height=0.20 * s, segments=12,
                             location=(0.0, 0.0, 0.48 * s), mat_index=MAT_INDEX_HAY)
    # Tied neck with rope cord
    faces += create_torus_ring(bm, location=(0.0, 0.0, 0.58 * s), major_radius=0.10 * s,
                               minor_radius=0.022 * s, major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_WOOD)
    # Frilled bag opening
    faces += create_cone(bm, radius1=0.09 * s, radius2=0.16 * s, height=0.12 * s, segments=10,
                         location=(0.0, 0.0, 0.65 * s), mat_index=MAT_INDEX_HAY)
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

