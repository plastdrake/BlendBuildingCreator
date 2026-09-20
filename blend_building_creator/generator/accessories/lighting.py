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
                               major_radius=0.036, minor_radius=0.009,
                               major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_IRON)
    return faces


def build_post_lantern(bm, x, y, z_ground=0.0, ang=0.0, height=2.55,
                       arm_len=0.55, scale=1.0):
    """A stout chamfered timber post with cut-stone plinth, forged scroll arm and lantern."""
    s = scale
    rng = _rng(x, y, 11)
    faces = []

    # 1. Stepped cut-stone foundation plinth
    faces += create_beveled_box(bm, size=(0.44 * s, 0.44 * s, 0.16),
                                location=(0.0, 0.0, 0.08), mat_index=MAT_INDEX_CUT_STONE,
                                bevel_amount=0.020, bevel_segments=2)
    faces += create_beveled_box(bm, size=(0.32 * s, 0.32 * s, 0.12),
                                location=(0.0, 0.0, 0.20), mat_index=MAT_INDEX_CUT_STONE,
                                bevel_amount=0.015, bevel_segments=2)

    # 4 Iron corner bracket shoes clamping the timber post into the stone
    for sx in (-0.11 * s, 0.11 * s):
        for sy in (-0.11 * s, 0.11 * s):
            faces += create_beveled_box(bm, size=(0.04, 0.04, 0.18),
                                        location=(sx, sy, 0.26),
                                        mat_index=MAT_INDEX_IRON, bevel_amount=0.004)

    # 2. Chunky hand-carved chamfered timber post
    post_w = 0.18 * s
    post_h = height - 0.26
    faces += create_beveled_box(bm, size=(post_w, post_w, post_h),
                                location=(0.0, 0.0, 0.26 + post_h * 0.5),
                                rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.02),
                                mat_index=MAT_INDEX_TIMBER,
                                bevel_amount=0.016, bevel_segments=2)

    # Decorative carved timber capital / collar below the iron arm
    arm_base_z = 0.26 + post_h - 0.02
    faces += create_beveled_box(bm, size=(post_w + 0.06, post_w + 0.06, 0.09),
                                location=(0.0, 0.0, arm_base_z),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    faces += create_beveled_box(bm, size=(post_w + 0.02, post_w + 0.02, 0.05),
                                location=(0.0, 0.0, arm_base_z + 0.06),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)

    # 3. Forged iron crossarm reaching out along local +X
    faces += create_beveled_box(bm, size=(arm_len, 0.042, 0.042),
                                location=(arm_len * 0.5 + 0.04, 0.0, arm_base_z + 0.04),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)

    # Ornate forged terminal curl at the end of the crossarm
    faces += create_torus_ring(bm, location=(arm_len + 0.08, 0.0, arm_base_z + 0.09),
                               major_radius=0.065, minor_radius=0.012,
                               major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_IRON)

    # Curved forged scroll brace underneath
    brace_l = math.hypot(arm_len * 0.70, 0.38)
    brace_a = math.atan2(0.38, arm_len * 0.70)
    faces += create_beveled_box(bm, size=(brace_l, 0.030, 0.030),
                                location=(arm_len * 0.36, 0.0, arm_base_z - 0.16),
                                rotation=(0.0, brace_a, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    # Scroll ring in the crook of the brace
    faces += create_torus_ring(bm, location=(arm_len * 0.28, 0.0, arm_base_z - 0.12),
                               major_radius=0.065, minor_radius=0.012,
                               major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_IRON)

    # 4. Suspension chains: 2 interlocking links hanging down
    tip_x = arm_len * 0.92
    faces += create_torus_ring(bm, location=(tip_x, 0.0, arm_base_z + 0.01),
                               major_radius=0.030, minor_radius=0.008,
                               mat_index=MAT_INDEX_IRON)
    faces += create_torus_ring(bm, location=(tip_x, 0.0, arm_base_z - 0.05),
                               rotation=(0.0, math.pi * 0.5, 0.0),
                               major_radius=0.032, minor_radius=0.008,
                               mat_index=MAT_INDEX_IRON)
    faces += create_torus_ring(bm, location=(tip_x, 0.0, arm_base_z - 0.10),
                               rotation=(math.pi * 0.5, 0.0, 0.0),
                               major_radius=0.032, minor_radius=0.008,
                               mat_index=MAT_INDEX_IRON)

    # 5. Lantern cage hanging cleanly beneath the chain
    cage_z = arm_base_z - 0.38 * s
    cage = _lantern_cage(bm, tip_x, 0.0, cage_z, size=0.28 * s,
                         height=0.38 * s, rng=rng)
    faces += cage

    transform_faces(faces, _place(x, y, z_ground, ang))
    _uv_faces(cage, bm)
    return faces


def build_hanging_lantern(bm, x, y, z_top, arm_ang=0.0, arm_len=0.42,
                          drop=0.0, scale=1.0):
    """A wall bracket whose lantern hangs from an interlocking hook and ring.

    ``arm_ang`` yaws the bracket arm (0 = +X, pointing away from the wall). The
    lantern cage's top ring is seated just below the arm's hook ring so the two
    actually link, and the arm sits high enough for the cage to clear the floor.
    """
    s = scale
    faces = []
    # Wall plate with two forged bolts.
    faces += create_beveled_box(bm, size=(0.06, 0.16, 0.30),
                                location=(0.02, 0.0, -0.12), mat_index=MAT_INDEX_IRON,
                                bevel_amount=0.008)
    for bz in (0.0, -0.24):
        faces += create_cylinder(bm, radius=0.016, height=0.03, segments=6,
                                 location=(0.05, 0.0, bz), rotation=(0.0, math.pi * 0.5, 0.0),
                                 mat_index=MAT_INDEX_IRON)
    # Forged arm along +X.
    faces += create_beveled_box(bm, size=(arm_len, 0.038, 0.038),
                                location=(arm_len * 0.5 + 0.02, 0.0, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
    # Diagonal brace from the wall foot up to the arm (outer end higher).
    brace_l = math.hypot(arm_len * 0.75, 0.32)
    brace_a = math.atan2(0.32, arm_len * 0.75)
    faces += create_beveled_box(bm, size=(brace_l, 0.026, 0.026),
                                location=(arm_len * 0.38, 0.0, -0.16),
                                rotation=(0.0, -brace_a, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    # Hook ring at the arm tip (hole axis X, so the arm passes through it).
    faces += create_torus_ring(bm, location=(arm_len, 0.0, -0.03),
                               rotation=(0.0, math.pi * 0.5, 0.0),
                               major_radius=0.038, minor_radius=0.009,
                               major_segments=12, minor_segments=6,
                               mat_index=MAT_INDEX_IRON)
    # Lantern cage with its suspension ring directly under the hook.
    hh = 0.17 * s
    cage_cz = -0.11 - hh - 0.27
    cage = _lantern_cage(bm, arm_len, 0.0, cage_cz, size=0.22 * s, height=0.34 * s)
    faces += cage
    transform_faces(faces, _place(x, y, z_top, arm_ang))
    _uv_faces(cage, bm)
    return faces

