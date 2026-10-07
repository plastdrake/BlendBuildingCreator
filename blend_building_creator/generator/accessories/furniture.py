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
    MAT_INDEX_CLAY, MAT_INDEX_HAY, MAT_INDEX_ROPE,
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

    # 3. Horizontal Perimeter Rails (Top and Bottom, embedded 10mm into posts)
    rail_x_len = max(0.06, sx - b * 2.0 + 0.02)
    rail_y_len = max(0.06, sy - b * 2.0 + 0.02)
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

    # 5. Chunky Corner Caps standing 4mm proud (never coplanar with posts)
    for cx_sign in (-1.0, 1.0):
        for cy_sign in (-1.0, 1.0):
            cx = cx_sign * (sx * 0.5 - b * 0.5)
            cy = cy_sign * (sy * 0.5 - b * 0.5)
            for cz_sign in (-1.0, 1.0):
                cz = sz * 0.5 + cz_sign * (sz * 0.5 - b * 0.16 + 0.004)
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

    # Lathe faces with normalized 0..1 UVs (no world-scale stretching); the
    # faces are tagged so the global box-UV pass preserves this unwrap.
    for s in range(len(rings) - 1):
        v0 = z_profile[s][0]
        v1 = z_profile[s + 1][0]
        for i in range(segments):
            j = (i + 1) % segments
            f = bm.faces.new([rings[s][i], rings[s][j], rings[s + 1][j], rings[s + 1][i]])
            f.material_index = MAT_INDEX_CLAY
            u0 = i / segments
            u1 = (i + 1) / segments
            f.loops[0][uv_layer].uv = (u0, v0)
            f.loops[1][uv_layer].uv = (u1, v0)
            f.loops[2][uv_layer].uv = (u1, v1)
            f.loops[3][uv_layer].uv = (u0, v1)
            f.tag = True
            faces.append(f)

    # Bottom cap with planar normalized UVs.
    bot = bm.faces.new(list(reversed(rings[0])))
    bot.material_index = MAT_INDEX_CLAY
    for loop in bot.loops:
        loop[uv_layer].uv = (loop.vert.co.x / (2 * r) + 0.5,
                             loop.vert.co.y / (2 * r) + 0.5)
    bot.tag = True
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
    # Flanged lid rim overlapping the mouth (embedded, never floating).
    faces += create_cylinder(
        bm, radius=rim_r * 1.05, height=0.035, segments=16,
        location=(0.0, 0.0, h + 0.015),
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
    """A plump tied burlap sack: lathe-turned body, cinched neck, rope tie.

    Modelled as a proper sack silhouette (wide belly, gathered neck, frilled
    mouth) with two stitched patches, matching the stylized bag reference.
    """
    from ..materials import MAT_INDEX_ROPE, MAT_INDEX_FABRIC_RED
    s = scale
    h = 0.55 * s
    # Squat slouchy silhouette: fat belly, gently gathered neck, wrinkled
    # mouth pulled nearly shut above the tie (never a flared vase collar).
    z_profile = [
        (0.00, 0.78), (0.10, 0.95), (0.30, 1.00), (0.52, 0.94),
        (0.68, 0.80), (0.80, 0.62), (0.86, 0.55), (0.93, 0.60),
        (0.97, 0.48), (1.00, 0.22),
    ]
    segments = 14
    base_r = 0.33 * s
    lean = 0.045 * s  # handmade slouch: the top drifts slightly sideways
    rings = []
    for zn, rn in z_profile:
        ring = []
        dx = lean * zn * zn
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            ring.append(bm.verts.new((dx + base_r * rn * math.cos(a),
                                      base_r * rn * math.sin(a), zn * h)))
        rings.append(ring)
    uv_layer = bm.loops.layers.uv.verify()
    faces = []
    for si in range(len(rings) - 1):
        v0 = z_profile[si][0]
        v1 = z_profile[si + 1][0]
        for i in range(segments):
            j = (i + 1) % segments
            f = bm.faces.new([rings[si][i], rings[si][j],
                              rings[si + 1][j], rings[si + 1][i]])
            f.material_index = MAT_INDEX_HAY
            f.loops[0][uv_layer].uv = (i / segments, v0)
            f.loops[1][uv_layer].uv = ((i + 1) / segments, v0)
            f.loops[2][uv_layer].uv = ((i + 1) / segments, v1)
            f.loops[3][uv_layer].uv = (i / segments, v1)
            f.tag = True
            faces.append(f)
    # Closed bottom + gathered mouth cap.
    bot = bm.faces.new(list(reversed(rings[0])))
    bot.material_index = MAT_INDEX_HAY
    for loop in bot.loops:
        loop[uv_layer].uv = (loop.vert.co.x / (2 * base_r) + 0.5,
                             loop.vert.co.y / (2 * base_r) + 0.5)
    bot.tag = True
    faces.append(bot)
    mouth = bm.faces.new(rings[-1])
    mouth.material_index = MAT_INDEX_HAY
    for loop in mouth.loops:
        loop[uv_layer].uv = (loop.vert.co.x / (2 * base_r) + 0.5,
                             loop.vert.co.y / (2 * base_r) + 0.5)
    mouth.tag = True
    faces.append(mouth)
    # Tied knot nub closing the gathered mouth.
    faces += create_cylinder(bm, radius=0.045 * s, height=0.05 * s, segments=10,
                             location=(lean, 0.0, h + 0.015 * s),
                             mat_index=MAT_INDEX_HAY)
    # Rope tie cord sunk into the gathered neck below the mouth.
    tie_z = 0.84 * h
    tie_r = base_r * 0.575 + 0.008
    faces += create_torus_ring(bm, location=(lean * 0.84 * 0.84, 0.0, tie_z),
                               major_radius=tie_r, minor_radius=0.020 * s,
                               major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_ROPE)
    # Two stitched patches tangent to the belly, centres sunk 5mm.
    for ang_off, ph, pr_frac in ((0.3, 0.28 * h, 1.00), (2.6, 0.40 * h, 0.967)):
        zn = ph / h
        pr = base_r * pr_frac - 0.005
        px = lean * zn * zn + math.cos(ang_off) * pr
        py = math.sin(ang_off) * pr
        faces += create_beveled_box(bm, size=(0.10 * s, 0.02, 0.08 * s),
                                    location=(px, py, ph),
                                    rotation=(0.0, 0.0, ang_off + math.pi / 2),
                                    mat_index=MAT_INDEX_FABRIC_RED,
                                    bevel_amount=0.004)
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

    # 3 Straight vertical timber legs (no splay: feet directly under the seat).
    for i in range(3):
        a = (2.0 * math.pi * i / 3.0) + 0.4
        lx, ly = math.cos(a) * radius * 0.62, math.sin(a) * radius * 0.62
        faces += create_beveled_box(
            bm, size=(0.07, 0.07, height),
            location=(lx, ly, height * 0.5),
            rotation=(0.0, 0.0, a),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Braced cross stretchers between the leg centres (embedded both ends).
    for i in range(3):
        a0 = (2.0 * math.pi * i / 3.0) + 0.4
        a1 = (2.0 * math.pi * ((i + 1) % 3) / 3.0) + 0.4
        p0 = (math.cos(a0) * radius * 0.62, math.sin(a0) * radius * 0.62)
        p1 = (math.cos(a1) * radius * 0.62, math.sin(a1) * radius * 0.62)
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

    # 4 Straight vertical legs (feet on the ground, tops embedded in the seat).
    leg_w = 0.10
    for sx in (-L * 0.5 + 0.20, L * 0.5 - 0.20):
        for sy in (-seat_d * 0.30, seat_d * 0.30):
            faces += create_beveled_box(
                bm, size=(leg_w, leg_w, seat_z),
                location=(sx, sy, seat_z * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

        # End cross stretchers tying the legs together (ends embedded in legs).
        faces += create_beveled_box(bm, size=(leg_w * 0.8, seat_d * 0.60 + 0.02, 0.07),
                                    location=(sx, 0.0, 0.16),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    if with_back:
        # Tilted backrest posts (all timber, no iron).
        post_h = 0.52
        tilt = 0.16
        for sx in (-L * 0.5 + 0.18, L * 0.5 - 0.18):
            faces += create_beveled_box(
                bm, size=(0.08, 0.08, post_h + 0.06),
                location=(sx, seat_d * 0.42 + 0.04, seat_z + post_h * 0.5 - 0.03),
                rotation=(-tilt, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

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
    """A sturdy tavern picnic table: plank top, bench slabs, A-frame trestles.

    Every joint overlaps (legs embed into the top and bearers, bearers into
    the benches) so nothing merely touches; no tie beams, pegs or braces.
    """
    L = length
    top_z = 0.78
    seat_z = 0.46
    faces = []

    # 1. Table top: 3 slabs with small gaps (12mm, never touching).
    plank_w = 0.28
    gap = 0.012
    top_thick = 0.085
    for dy in (-plank_w - gap, 0.0, plank_w + gap):
        faces += create_beveled_box(
            bm, size=(L, plank_w, top_thick),
            location=(0.0, dy, top_z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.016, bevel_segments=2)

    # 2. Bench slabs on both sides.
    bench_w = 0.25
    bench_thick = 0.075
    bench_y_dist = 0.65
    for side_y in (-bench_y_dist, bench_y_dist):
        faces += create_beveled_box(
            bm, size=(L, bench_w, bench_thick),
            location=(0.0, side_y, seat_z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)

    # 3. A-frame trestles: splayed legs running from under the top down to
    # the ground, plus one cross-bearer per trestle carrying the benches.
    leg_w = 0.13
    top_under = top_z - top_thick / 2
    for sx in (-L * 0.5 + 0.36, L * 0.5 - 0.36):
        for s in (-1.0, 1.0):
            # Top end hidden 30mm inside the tabletop, foot sunk 5mm.
            y_top, y_bot = s * 0.10, s * 0.58
            z_top, z_bot = top_under + 0.03, -0.005
            dy, dz = y_bot - y_top, z_bot - z_top
            leg_len = math.hypot(dy, dz)
            faces += create_beveled_box(
                bm, size=(leg_w, leg_w, leg_len),
                location=(sx, (y_top + y_bot) / 2, (z_top + z_bot) / 2),
                rotation=(s * math.atan2(abs(dy), abs(dz)), 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
        # Bearer overlaps 5mm into each bench slab and crosses the legs.
        faces += create_beveled_box(
            bm, size=(leg_w, bench_y_dist * 2.0 + bench_w * 0.6, 0.10),
            location=(sx, 0.0, seat_z - bench_thick / 2 + 0.005),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_hay_bale(bm, x=0.0, y=0.0, z_ground=0.0, ang=0.0,
                   width=0.88, depth=0.54, height=0.44):
    """A realistic tied golden straw / thatch hay bale with rope twine bands.

    Features volumetric straw geometry (main beveled bale + slight side expansion)
    and two taut twine cords wrapped around the bale with tied top knots.
    """
    faces = []
    # 1. Main straw bale body with generous bevel so it reads soft and bound
    faces += create_beveled_box(
        bm, size=(width, depth, height),
        location=(0.0, 0.0, height * 0.5),
        mat_index=MAT_INDEX_HAY, bevel_amount=0.045, bevel_segments=2)

    # 2. Slight central bulge (straw expanding between the tight binding twine)
    faces += create_beveled_box(
        bm, size=(width * 0.40, depth + 0.02, height + 0.02),
        location=(0.0, 0.0, height * 0.5),
        mat_index=MAT_INDEX_HAY, bevel_amount=0.035, bevel_segments=2)

    # 3. Two binding twine straps wrapped around the bale (YZ perimeter)
    strap_w = 0.028
    strap_thick = 0.014
    for sx in (-width * 0.24, width * 0.24):
        # Ring loop around depth and height
        faces += create_beveled_box(
            bm, size=(strap_w, depth + strap_thick * 2.0, height + strap_thick * 2.0),
            location=(sx, 0.0, height * 0.5),
            mat_index=MAT_INDEX_ROPE, bevel_amount=0.005)
        # Small tied twine knot on top
        faces += create_beveled_box(
            bm, size=(0.045, 0.05, 0.035),
            location=(sx, 0.0, height + strap_thick + 0.012),
            mat_index=MAT_INDEX_ROPE, bevel_amount=0.004)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_hay_pile(bm, x=0.0, y=0.0, z_ground=0.0, ang=0.0,
                   radius=0.58, height=0.20):
    """A natural, slightly ruffled loose pile of golden straw/hay for floors and stalls.

    Constructed with an irregular low-poly faceted mound so loose straw appears
    authentically scattered rather than a geometric cone.
    """
    import mathutils
    faces = []
    segments = 10
    # Deterministic wonkiness based on location
    rng = _rng(x, y, salt=77)

    uv_layer = bm.loops.layers.uv.verify()
    peak = bm.verts.new((0.0, 0.0, height))

    # Inner ring of raised straw tufts
    inner_verts = []
    r_in = radius * 0.55
    z_in = height * 0.62
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        r_var = r_in * (0.85 + 0.30 * rng.random())
        z_var = z_in * (0.85 + 0.25 * rng.random())
        inner_verts.append(bm.verts.new((r_var * math.cos(a), r_var * math.sin(a), z_var)))

    # Outer ruffled skirt on the floor
    outer_verts = []
    for i in range(segments):
        a = 2.0 * math.pi * (i + 0.5) / segments
        r_var = radius * (0.82 + 0.36 * rng.random())
        outer_verts.append(bm.verts.new((r_var * math.cos(a), r_var * math.sin(a), 0.005)))

    # Connect peak to inner ring
    for i in range(segments):
        nxt = (i + 1) % segments
        f = bm.faces.new([peak, inner_verts[i], inner_verts[nxt]])
        f.material_index = MAT_INDEX_HAY
        f.tag = True
        faces.append(f)

    # Connect inner ring to outer skirt
    for i in range(segments):
        nxt = (i + 1) % segments
        f1 = bm.faces.new([inner_verts[i], outer_verts[i], inner_verts[nxt]])
        f1.material_index = MAT_INDEX_HAY
        f1.tag = True
        faces.append(f1)
        f2 = bm.faces.new([inner_verts[nxt], outer_verts[i], outer_verts[nxt]])
        f2.material_index = MAT_INDEX_HAY
        f2.tag = True
        faces.append(f2)

    # Bottom cap
    f_bot = bm.faces.new(list(reversed(outer_verts)))
    f_bot.material_index = MAT_INDEX_HAY
    f_bot.tag = True
    faces.append(f_bot)

    # Apply planar UVs
    for f in faces:
        for loop in f.loops:
            loop[uv_layer].uv = mathutils.Vector((loop.vert.co.x / (radius * 2.0) + 0.5,
                                                  loop.vert.co.y / (radius * 2.0) + 0.5))

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_feed_trough(bm, x=0.0, y=0.0, z_ground=0.0, ang=0.0,
                      length=1.05, depth=0.44, height=0.42):
    """An open wooden feeding manger trough with a genuine hollow interior volume
    packed full of golden straw/hay.

    No lid: authentic 4-walled timber basin with heavy supporting runners, iron corner
    straps, and an interior hollow bed heaped with organic straw thatch.
    """
    faces = []
    t_wall = 0.045
    leg_h = 0.16
    trough_h = height - leg_h

    # 1. Supporting timber runners / skids underneath
    runner_w = 0.08
    for rx in (-length * 0.32, length * 0.32):
        faces += create_beveled_box(
            bm, size=(runner_w, depth - 0.04, leg_h),
            location=(rx, 0.0, leg_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # 2. Hollow wooden basin (bottom + 4 side walls)
    base_z = leg_h
    # Bottom board
    faces += create_beveled_box(
        bm, size=(length - 0.02, depth - 0.02, t_wall),
        location=(0.0, 0.0, base_z + t_wall * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)

    wall_h = trough_h - t_wall
    wall_cz = base_z + t_wall + wall_h * 0.5

    # Front and back walls
    for s_y in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(length, t_wall, wall_h),
            location=(0.0, s_y * (depth * 0.5 - t_wall * 0.5), wall_cz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Left and right end walls
    inner_d = depth - 2.0 * t_wall
    for s_x in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(t_wall, inner_d, wall_h),
            location=(s_x * (length * 0.5 - t_wall * 0.5), 0.0, wall_cz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # 3. Iron corner reinforcement brackets on the trough exterior
    bracket_h = wall_h * 0.70
    for s_x in (-1.0, 1.0):
        for s_y in (-1.0, 1.0):
            faces += create_beveled_box(
                bm, size=(0.045, 0.045, bracket_h),
                location=(s_x * (length * 0.5 - 0.02), s_y * (depth * 0.5 - 0.02), wall_cz),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

    # 4. Interior straw fill (heaped bedding of hay filling the hollow cavity)
    fill_l = length - 2.0 * t_wall - 0.02
    fill_d = inner_d - 0.02
    fill_h = wall_h * 0.82
    fill_cz = base_z + t_wall + fill_h * 0.5
    # Base hay volume inside the cavity
    faces += create_beveled_box(
        bm, size=(fill_l, fill_d, fill_h),
        location=(0.0, 0.0, fill_cz),
        mat_index=MAT_INDEX_HAY, bevel_amount=0.03, bevel_segments=2)

    # Mounded tufts of fresh straw protruding slightly near the rim
    faces += create_beveled_box(
        bm, size=(fill_l * 0.70, fill_d * 0.75, 0.08),
        location=(0.0, 0.0, base_z + t_wall + fill_h + 0.01),
        mat_index=MAT_INDEX_HAY, bevel_amount=0.025, bevel_segments=2)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


