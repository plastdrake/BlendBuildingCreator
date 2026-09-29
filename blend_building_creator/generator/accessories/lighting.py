"""
Generic lanterns (cozy hand-forged iron and timber).

Iron post lamps and wall/eave-hung lanterns shared by taverns, inns, shopfronts
and any street scene. The cage geometry is built once and reused by both the
post and the hanging variant (DRY), while placement is handled by a single
local-to-world transform. Local +X is always the direction the bracket arm
reaches, so callers simply yaw the whole prop.
"""

import math
import random
from mathutils import Matrix, Vector

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_torus_ring, transform_faces,
)
from ..materials import MAT_INDEX_IRON, MAT_INDEX_LANTERN, MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_CUT_STONE


def _place(x, y, z_ground=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _rng(x, y, salt=0):
    return random.Random((int(abs(x) * 73856093) ^ int(abs(y) * 19349663) ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _uv_faces(faces, bm, scale=1.0):
    """Cube-project UVs for prop faces.

    The global box-UV pass skips forged iron, so lantern cages (struts, plates
    and especially the pyramid roof cone) would otherwise carry no usable UVs.
    A local triplanar/cube projection gives them clean unwraps.
    """
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        if not f.is_valid:
            continue
        n = f.normal
        nx, ny, nz = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if nz >= nx and nz >= ny:
                u, v = co.x * scale, co.y * scale
            elif nx >= ny:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = Vector((u, v))


def _lantern_cage(bm, cx, cy, cz, size=0.22, height=0.32, rng=None):
    """A compact hand-forged four-pane lantern cage with a candle and top ring.

    The suspension ring lies in the local XZ plane (hole axis Y) so it can
    interlock with a perpendicular hook on a bracket arm.
    """
    w = size
    hh = height * 0.5
    faces = []

    # Bottom tray with drip lip.
    faces += create_beveled_box(bm, size=(w * 1.06, w * 1.06, 0.045),
                                location=(cx, cy, cz - hh), mat_index=MAT_INDEX_IRON,
                                bevel_amount=0.007)
    # Glowing glass body. This is the whole light source - no candle or other
    # geometry sits inside the panes (they would show through the emissive glass).
    faces += create_beveled_box(bm, size=(w * 0.74, w * 0.74, height * 0.86),
                                location=(cx, cy, cz), mat_index=MAT_INDEX_LANTERN,
                                bevel_amount=0.0)
    # Four vertical corner struts.
    for sx in (-w * 0.5, w * 0.5):
        for sy in (-w * 0.5, w * 0.5):
            faces += create_beveled_box(bm, size=(0.026, 0.026, height),
                                        location=(cx + sx, cy + sy, cz),
                                        mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    # Top plate + flared pyramid roof (faces aligned over the body faces).
    faces += create_beveled_box(bm, size=(w * 1.02, w * 1.02, 0.04),
                                location=(cx, cy, cz + hh), mat_index=MAT_INDEX_IRON,
                                bevel_amount=0.006)
    faces += create_cone(bm, radius1=w * 0.92, radius2=w * 0.10, height=0.15, segments=4,
                         location=(cx, cy, cz + hh + 0.09),
                         rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_IRON)
    # Finial + suspension ring (XZ plane).
    faces += create_cylinder(bm, radius=0.013, height=0.08, segments=6,
                             location=(cx, cy, cz + hh + 0.20), mat_index=MAT_INDEX_IRON)
    faces += create_torus_ring(bm, location=(cx, cy, cz + hh + 0.27),
                               rotation=(math.pi * 0.5, 0.0, 0.0),
                               major_radius=0.038, minor_radius=0.009,
                               major_segments=16, minor_segments=8,
                               mat_index=MAT_INDEX_IRON)
    return faces


def build_post_lantern(bm, x, y, z_ground=0.0, ang=0.0, height=2.55,
                       arm_len=0.55, scale=1.0):
    """A stout chamfered timber post with cut-stone plinth and a hanging cage.

    The cage hangs from the arm tip on a short link chain exactly like the
    wall-hung lantern (shared ``_lantern_cage`` geometry, DRY): two
    interlocking vertical links with the cage ring overlapping the last one.
    """
    s = scale
    rng = _rng(x, y, 11)
    faces = []

    # 1. Stepped cut-stone foundation plinth (upper step overlaps 20mm).
    faces += create_beveled_box(bm, size=(0.44 * s, 0.44 * s, 0.16),
                                location=(0.0, 0.0, 0.08), mat_index=MAT_INDEX_CUT_STONE,
                                bevel_amount=0.020, bevel_segments=2)
    faces += create_beveled_box(bm, size=(0.32 * s, 0.32 * s, 0.14),
                                location=(0.0, 0.0, 0.16 - 0.02 + 0.07), mat_index=MAT_INDEX_CUT_STONE,
                                bevel_amount=0.015, bevel_segments=2)

    # 2. Chunky hand-carved chamfered timber post, foot embedded 30mm.
    post_w = 0.18 * s
    post_h = height - 0.26
    post_base = 0.23
    faces += create_beveled_box(bm, size=(post_w, post_w, post_h),
                                location=(0.0, 0.0, post_base + post_h * 0.5),
                                rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.02),
                                mat_index=MAT_INDEX_TIMBER,
                                bevel_amount=0.016, bevel_segments=2)

    # Decorative carved timber capital / collar below the iron arm
    arm_base_z = post_base + post_h - 0.02
    faces += create_beveled_box(bm, size=(post_w + 0.06, post_w + 0.06, 0.09),
                                location=(0.0, 0.0, arm_base_z),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    faces += create_beveled_box(bm, size=(post_w + 0.02, post_w + 0.02, 0.05),
                                location=(0.0, 0.0, arm_base_z + 0.06),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)

    # 3. Straight forged iron arm reaching out along local +X.
    arm_z = arm_base_z + 0.04
    faces += create_beveled_box(bm, size=(arm_len, 0.045, 0.045),
                                location=(arm_len * 0.5 + 0.04, 0.0, arm_z),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)

    # Knee brace rising from the post up to the arm underside (embedded ends).
    bx0, bz0 = 0.05, arm_z - 0.36
    bx1, bz1 = arm_len * 0.62, arm_z - 0.025
    brace_l = math.hypot(bx1 - bx0, bz1 - bz0) + 0.04
    brace_a = math.atan2(bz1 - bz0, bx1 - bx0)
    faces += create_beveled_box(bm, size=(brace_l, 0.030, 0.030),
                                location=((bx0 + bx1) * 0.5, 0.0, (bz0 + bz1) * 0.5),
                                rotation=(0.0, -brace_a, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)

    # 4. Two interlocking vertical links hung straight off the arm tip:
    # link 1 overlaps the arm underside, link 2 overlaps link 1, and the
    # cage ring below overlaps link 2. Nothing floats.
    tip_x = arm_len - 0.02
    for i in range(2):
        lz = arm_z - 0.035 - i * 0.05
        rot = (math.pi * 0.5, 0.0, 0.0) if i % 2 == 0 else (0.0, math.pi * 0.5, 0.0)
        faces += create_torus_ring(bm, location=(tip_x, 0.0, lz), rotation=rot,
                                   major_radius=0.030, minor_radius=0.008,
                                   major_segments=12, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)

    # 5. Lantern cage hung so its suspension ring overlaps the last link.
    cage_h = 0.36 * s
    ring_off = cage_h * 0.5 + 0.27
    cage_z = arm_z - 0.12 - ring_off
    cage = _lantern_cage(bm, tip_x, 0.0, cage_z, size=0.26 * s,
                         height=cage_h, rng=rng)
    faces += cage

    transform_faces(faces, _place(x, y, z_ground, ang))
    _uv_faces(cage, bm)
    return faces


def build_hanging_lantern(bm, x, y, z_top, arm_ang=0.0, arm_len=0.42,
                          drop=0.0, scale=1.0, ang=None):
    """A wall bracket whose lantern hangs from an interlocking hook and ring.

    ``arm_ang`` yaws the bracket arm (0 = +X, pointing away from the wall). The
    lantern cage's top ring is seated just below the arm's hook ring so the two
    actually link, and the arm sits high enough for the cage to clear the floor.
    ``ang`` is an alias for ``arm_ang`` so the generic prop registry can drive
    this builder with one yaw convention.
    """
    if ang is not None:
        arm_ang = ang
    s = scale
    faces = []
    # Wall plate (flush against host timber post / wall, no bolts).
    faces += create_beveled_box(bm, size=(0.06, 0.16, 0.30),
                                location=(0.02, 0.0, -0.12), mat_index=MAT_INDEX_IRON,
                                bevel_amount=0.008)
    # Forged arm along +X.
    faces += create_beveled_box(bm, size=(arm_len, 0.038, 0.038),
                                location=(arm_len * 0.5 + 0.02, 0.0, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
    # Smaller, compact forged diagonal knee brace (meets plate cleanly at Z=-0.18, meets arm at ~45% span).
    x1, z1_brace = 0.05, -0.18
    x2, z2_brace = min(0.24, arm_len * 0.48), -0.019
    dx_brace = x2 - x1
    dz_brace = z2_brace - z1_brace
    brace_l = math.hypot(dx_brace, dz_brace)
    brace_a = math.atan2(dz_brace, dx_brace)
    faces += create_beveled_box(bm, size=(brace_l, 0.024, 0.024),
                                location=((x1 + x2) * 0.5, 0.0, (z1_brace + z2_brace) * 0.5),
                                rotation=(0.0, -brace_a, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    # Hook ring at the arm tip (hole axis X, so the arm passes through it).
    faces += create_torus_ring(bm, location=(arm_len, 0.0, -0.03),
                               rotation=(0.0, math.pi * 0.5, 0.0),
                               major_radius=0.038, minor_radius=0.009,
                               major_segments=16, minor_segments=8,
                               mat_index=MAT_INDEX_IRON)
    # Lantern cage with its suspension ring interlocking through the hook ring (Z_ring = -0.084 vs Z_hook = -0.03).
    hh = 0.17 * s
    cage_cz = -0.084 - hh - 0.27
    cage = _lantern_cage(bm, arm_len, 0.0, cage_cz, size=0.22 * s, height=0.34 * s)
    faces += cage
    transform_faces(faces, _place(x, y, z_top, arm_ang))
    _uv_faces(cage, bm)
    return faces


def build_chain_lantern(bm, x, y, z_ceiling, chain_len=0.55, scale=0.90, ang=None):
    """A forged iron lantern hanging straight down from a ceiling/soffit/beam by an unbroken continuous chain.

    ``ang`` is accepted and ignored (a hanging chain is radially symmetric)
    so the generic prop registry can pass one yaw convention to every builder.
    """
    s = scale
    w = 0.26 * s
    h = 0.36 * s
    hh = h * 0.5
    faces = []

    # 1. Ceiling mounting plate / boss
    faces += create_cylinder(bm, radius=0.065 * s, height=0.024, segments=8,
                             location=(x, y, z_ceiling - 0.012), mat_index=MAT_INDEX_IRON)

    r_maj = 0.032 * s
    r_min = 0.0075 * s

    z_eyelet = z_ceiling - 0.036
    # Fixed ceiling eyelet ring (XZ plane)
    faces += create_torus_ring(bm, location=(x, y, z_eyelet), rotation=(math.pi * 0.5, 0.0, 0.0),
                               major_radius=r_maj, minor_radius=r_min,
                               major_segments=12, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # 2. Lantern cage
    cz = z_ceiling - chain_len - 0.16 * s
    cage = _lantern_cage(bm, x, y, cz, size=w, height=h)
    faces += cage
    _uv_faces(cage, bm)

    # The top suspension ring of _lantern_cage is at cz + hh + 0.27 (XZ plane)
    z_lantern_ring = cz + hh + 0.27

    # 3. Interlocking chain links bridging z_eyelet down to z_lantern_ring
    dist = z_eyelet - z_lantern_ring
    if dist > 0.04:
        target_step = 0.040 * s
        n_links = max(1, int(round(dist / target_step)) - 1)
        # Ensure odd number of links so last link (YZ plane) interlocks with lantern ring (XZ plane)
        if n_links % 2 == 0:
            n_links += 1
        step_z = dist / (n_links + 1)
        for li in range(1, n_links + 1):
            lz = z_eyelet - li * step_z
            rot = (0.0, math.pi * 0.5, 0.0) if (li % 2 == 1) else (math.pi * 0.5, 0.0, 0.0)
            faces += create_torus_ring(bm, location=(x, y, lz), rotation=rot,
                                       major_radius=r_maj, minor_radius=r_min,
                                       major_segments=12, minor_segments=6,
                                       mat_index=MAT_INDEX_IRON)
    return faces


