"""
Generic signage and awnings.

Hanging trade signs, freestanding notice boards and cloth awnings. Any shop,
forge, inn or tavern can mount these; the geometry only needs a mounting point
and a yaw, never knowledge of the host building.

The hanging sign is a chunky light-plank board carrying a handpainted icon
decal (``M_Building_Sign``) on both faces, so it reads from the street and from
the door. Local +X is the bracket/outward direction: the board faces out along
+X, so callers yaw the sign to point away from the wall.
"""

import math
import random
from mathutils import Matrix, Vector

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_torus_ring, transform_faces,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_IRON, MAT_INDEX_WOOD,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_BANNER, MAT_INDEX_SIGN,
    MAT_INDEX_CLOCK_FACE,
)


def _place(x, y, z_base=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_base)) @ Matrix.Rotation(ang, 4, 'Z')


def _rng(x, y, salt=0):
    return random.Random((int(abs(x) * 73856093) ^ int(abs(y) * 19349663) ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _create_sign_decal_quad(bm, cx, dy, cz, w, h, is_back=False):
    """Creates a planar decal quad for the trade sign emblem.
    
    The sign faces along +/- Y in local coordinates.
    When viewed from the outside:
      - Front face (+Y normal): viewer looking toward -Y has viewer's Left at +X and Right at -X.
        Therefore, U=0 (left) is at +X and U=1 (right) is at -X.
      - Back face (-Y normal): viewer looking toward +Y has viewer's Left at -X and Right at +X.
        Therefore, U=0 (left) is at -X and U=1 (right) is at +X.
    This guarantees that text and emblems read completely un-mirrored and left-to-right from BOTH directions along the street!
    """
    hw = w * 0.5
    hh = h * 0.5
    uv = bm.loops.layers.uv.verify()
    
    if not is_back:
        # Front face (+Y): normal points along +Y (0, 1, 0)
        # CCW loop from outside: Bottom-Left (+X), Bottom-Right (-X), Top-Right (-X), Top-Left (+X)
        p0 = Vector((cx + hw, dy, cz - hh))
        p1 = Vector((cx - hw, dy, cz - hh))
        p2 = Vector((cx - hw, dy, cz + hh))
        p3 = Vector((cx + hw, dy, cz + hh))
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    else:
        # Back face (-Y): normal points along -Y (0, -1, 0)
        # CCW loop from outside: Bottom-Left (-X), Bottom-Right (+X), Top-Right (+X), Top-Left (-X)
        p0 = Vector((cx - hw, dy, cz - hh))
        p1 = Vector((cx + hw, dy, cz - hh))
        p2 = Vector((cx + hw, dy, cz + hh))
        p3 = Vector((cx - hw, dy, cz + hh))
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        
    v_objs = [bm.verts.new(p) for p in (p0, p1, p2, p3)]
    face = bm.faces.new(v_objs)
    face.material_index = MAT_INDEX_SIGN
    face.normal_update()
    
    for loop, uv_coord in zip(face.loops, uvs):
        loop[uv].uv = uv_coord
        
    return [face]


def build_hanging_sign(bm, x, y, z_top, run_ang=0.0, bracket_len=0.60,
                       board_w=0.88, board_h=0.74, light_board=True):
    """A compact blacksmith-forged hanging trade sign with a painted icon decal.

    ``run_ang`` yaws the bracket in the XY plane (0 = +X). Local +X is the
    bracket projection away from the wall; the board hangs in the local XZ plane
    under the arm (faces local +/-Y) so it reads along the street, and sits close
    to the wall on a short bracket.
    """
    rng = _rng(x, y, 31)
    faces = []

    # Wall mounting plate.
    faces += create_beveled_box(bm, size=(0.06, 0.16, 0.34),
                                location=(0.02, 0.0, -0.14), mat_index=MAT_INDEX_IRON,
                                bevel_amount=0.008)
    # Main horizontal forged iron beam.
    faces += create_beveled_box(bm, size=(bracket_len, 0.042, 0.042),
                                location=(bracket_len * 0.5 + 0.02, 0.0, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
    # Support brace running from the wall foot UP to the arm near its tip.
    brace_l = math.hypot(bracket_len * 0.8, 0.30)
    brace_a = math.atan2(0.30, bracket_len * 0.8)
    faces += create_beveled_box(bm, size=(brace_l, 0.028, 0.028),
                                location=(bracket_len * 0.40, 0.0, -0.15),
                                rotation=(0.0, -brace_a, 0.0),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    # Two short straps hanging the board directly from the arm. The board hangs
    # low enough that the diagonal brace ends above it instead of crossing it.
    board_cx = bracket_len * 0.55
    board_top_z = -0.34
    board_cz = board_top_z - board_h * 0.5
    for hx in (board_cx - board_w * 0.30, board_cx + board_w * 0.30):
        faces += create_beveled_box(bm, size=(0.03, 0.03, -board_top_z + 0.03),
                                    location=(hx, 0.0, board_top_z * 0.5),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

    # Chunky wooden sign board (3 vertical planks lying in the local XZ plane).
    board_thick = 0.075
    board_mat = MAT_INDEX_WOOD if light_board else MAT_INDEX_TIMBER
    gap = 0.010
    plank_w = (board_w - gap * 2.0) / 3.0
    for k in range(3):
        px = board_cx - board_w * 0.5 + plank_w * 0.5 + k * (plank_w + gap)
        j = (rng.random() - 0.5) * 0.012
        faces += create_beveled_box(
            bm, size=(plank_w, board_thick, board_h),
            location=(px, 0.0, board_cz + j),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.02),
            mat_index=board_mat, bevel_amount=0.010, bevel_segments=2)

    # Timber top and bottom cross battens.
    for bz in (board_cz + board_h * 0.44, board_cz - board_h * 0.44):
        faces += create_beveled_box(bm, size=(board_w + 0.03, board_thick + 0.022, 0.07),
                                    location=(board_cx, 0.0, bz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Icon decal panels proud of both faces (local +/- Y).
    decal_w = board_w * 0.82
    decal_h = board_h * 0.76
    for side in (-1.0, 1.0):
        dy = side * (board_thick * 0.5 + 0.005)
        faces += _create_sign_decal_quad(
            bm, board_cx, dy, board_cz, decal_w, decal_h, is_back=(side < 0.0)
        )

    transform_faces(faces, _place(x, y, z_top, run_ang))
    return faces


def build_notice_board(bm, x, y, z_ground=0.0, ang=0.0, width=1.10,
                       height=0.82, post_h=1.70):
    """A chunky roofed timber notice board with pinned bounty/notice parchment."""
    rng = _rng(x, y, 32)
    faces = []
    # Chunky chamfered posts
    post_w = 0.12
    for sx in (-width * 0.5, width * 0.5):
        faces += create_beveled_box(bm, size=(post_w, post_w, post_h),
                                    location=(sx, 0.0, post_h * 0.5),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    board_cz = post_h - height * 0.5 - 0.12
    # Thick rustic backing board, kept a touch shorter than the rail centres so
    # the top/bottom rails fully cover its edges (no panel poking through).
    faces += create_beveled_box(bm, size=(width - 0.04, 0.09, height - 0.10),
                                location=(0.0, -0.02, board_cz),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.014)
    # Heavy frame rails
    for bz in (-height * 0.5 + 0.05, height * 0.5 - 0.05):
        faces += create_beveled_box(bm, size=(width + 0.04, 0.05, 0.10),
                                    location=(0.0, -0.07, board_cz + bz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # Chunky gabled / pitched timber hood
    faces += create_beveled_box(bm, size=(width + 0.28, 0.28, 0.06),
                                location=(0.0, -0.06, post_h + 0.04),
                                rotation=(0.24 + (rng.random() - 0.5) * 0.03, 0.0, 0.0),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # 2 Pinned paper notice sheets with forged iron pins
    for nx, ny_off in ((-width * 0.22, 0.04), (width * 0.20, -0.03)):
        faces += create_beveled_box(bm, size=(0.26, 0.010, 0.32),
                                    location=(nx, -0.07, board_cz + ny_off),
                                    rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.08),
                                    mat_index=MAT_INDEX_CLOCK_FACE, bevel_amount=0.0)
        faces += create_cylinder(bm, radius=0.012, height=0.025, segments=6,
                                 location=(nx, -0.08, board_cz + ny_off + 0.13),
                                 rotation=(math.pi * 0.5, 0.0, 0.0),
                                 mat_index=MAT_INDEX_IRON)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_awning(bm, x, y, z_top, ang=0.0, width=1.45, depth=1.10, drop=0.50):
    """A cloth awning projecting from a wall over a door or window.

    Local frame: the wall plane is XZ at y=0 and the awning reaches toward -Y.
    """
    slope_len = math.hypot(depth, drop)
    tilt = math.atan2(drop, depth)
    faces = []
    faces += create_beveled_box(bm, size=(width, slope_len, 0.03),
                                location=(0.0, -depth * 0.5, -drop * 0.5),
                                rotation=(tilt, 0.0, 0.0),
                                mat_index=MAT_INDEX_BANNER, bevel_amount=0.0)
    # Scalloped valance.
    n = max(3, int(width / 0.36))
    for i in range(n):
        vx = -width * 0.5 + width * (i + 0.5) / n
        faces += create_beveled_box(bm, size=(width / n - 0.01, 0.10, 0.13),
                                    location=(vx, -depth, -drop - 0.04),
                                    mat_index=MAT_INDEX_BANNER, bevel_amount=0.01)
    for sx in (-width * 0.5, width * 0.5):
        faces += create_beveled_box(bm, size=(0.05, depth, 0.05),
                                    location=(sx, -depth * 0.5, -drop * 0.5 - 0.02),
                                    rotation=(tilt, 0.0, 0.0),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
        faces += create_beveled_box(bm, size=(0.05, 0.05, 0.16),
                                    location=(sx, -0.02, -0.06),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    transform_faces(faces, _place(x, y, z_top, ang))
    return faces
