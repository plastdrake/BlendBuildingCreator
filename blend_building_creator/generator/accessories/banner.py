"""Reusable heraldic banner poles and hanging cloth standards."""

import math
from mathutils import Vector, Matrix
from ..mesh_utils import create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME,
    MAT_INDEX_IRON, MAT_INDEX_BANNER,
)


def build_banner_pole(bm, x, y, z_ground=0.0, height=4.6,
                      flag_len=0.95, flag_h=0.62, flag_dir=(0.0, -1.0)):
    """A stately timber standard with an iron spearhead finial and hanging heraldic cloth banner."""
    # Normalize facing direction (default (0.0, -1.0) is plot forward / front street)
    fx, fy = flag_dir
    flen = math.hypot(fx, fy)
    if flen < 1e-4:
        fx, fy = 0.0, -1.0
    else:
        fx, fy = fx / flen, fy / flen

    # Perpendicular horizontal direction for the crossbar (right-handed: right = forward x up)
    sx, sy = fy, -fx
    ang_side = math.atan2(sy, sx)

    # 1. Base plinth collar
    b_faces = create_cylinder(bm, radius=0.08, height=0.30, segments=8,
                              location=(x, y, z_ground + 0.15), mat_index=MAT_INDEX_TIMBER_FRAME)
    for f in b_faces:
        f.tag = True

    # 2. Main timber pole
    p_faces = create_cylinder(bm, radius=0.048, height=height, segments=8,
                              location=(x, y, z_ground + 0.30 + height * 0.5), mat_index=MAT_INDEX_WOOD)
    for f in p_faces:
        f.tag = True

    top_z = z_ground + 0.30 + height

    # 3. Decorative top iron collar & spearhead finial
    top_col = create_cylinder(bm, radius=0.075, height=0.10, segments=8,
                              location=(x, y, top_z - 0.05), mat_index=MAT_INDEX_IRON)
    for f in top_col:
        f.tag = True
    top_cone = create_cone(bm, radius1=0.065, radius2=0.0, height=0.25, segments=8,
                           location=(x, y, top_z + 0.125), mat_index=MAT_INDEX_IRON)
    for f in top_cone:
        f.tag = True

    # 4. Horizontal crossbar (yardarm) perpendicular to facing direction
    bar_z = top_z - 0.30
    bar_w = 1.08
    bar_cx = x + fx * 0.07
    bar_cy = y + fy * 0.07
    bar_faces = create_cylinder(bm, radius=0.026, height=bar_w, segments=8,
                                location=(bar_cx, bar_cy, bar_z),
                                rotation=(0.0, 1.5708, ang_side), mat_index=MAT_INDEX_WOOD)
    for f in bar_faces:
        f.tag = True

    # Ornate crossbar finials on the ends
    for end_sign in (-1.0, 1.0):
        cap_x = bar_cx + sx * (bar_w * 0.5 * end_sign)
        cap_y = bar_cy + sy * (bar_w * 0.5 * end_sign)
        cap_faces = create_cylinder(bm, radius=0.038, height=0.04, segments=8,
                                    location=(cap_x, cap_y, bar_z),
                                    rotation=(0.0, 1.5708, ang_side), mat_index=MAT_INDEX_IRON)
        for f in cap_faces:
            f.tag = True
        tip_x = cap_x + sx * (0.05 * end_sign)
        tip_y = cap_y + sy * (0.05 * end_sign)
        tip_faces = create_cone(bm, radius1=0.032, radius2=0.0, height=0.08, segments=8,
                                location=(tip_x, tip_y, bar_z),
                                rotation=(0.0, 1.5708 * end_sign, ang_side),
                                mat_index=MAT_INDEX_IRON)
        for f in tip_faces:
            f.tag = True

    # 5. Hanging Rectangular Banner Mesh (Alpha cutout defines chevron & golden border)
    banner_w = 0.88
    banner_h = 1.30
    cloth_t = 0.016
    cloth_cx = bar_cx + fx * 0.020
    cloth_cy = bar_cy + fy * 0.020
    cloth_top_z = bar_z - 0.04

    hx = banner_w * 0.5
    hy = cloth_t * 0.5

    # 4 front vertices and 4 back vertices forming a clean rectangular cloth sheet
    # Local: X = crossbar/side (-hx..+hx), Y = forward (-hy..+hy), Z = height (-banner_h..0)
    local_front = [
        Vector((-hx,  hy, 0.0)),         # 0: top-left
        Vector((-hx,  hy, -banner_h)),   # 1: bottom-left
        Vector(( hx,  hy, -banner_h)),   # 2: bottom-right
        Vector(( hx,  hy, 0.0)),         # 3: top-right
    ]
    local_back = [
        Vector(( hx, -hy, 0.0)),         # 4: back top-right
        Vector(( hx, -hy, -banner_h)),   # 5: back bottom-right
        Vector((-hx, -hy, -banner_h)),   # 6: back bottom-left
        Vector((-hx, -hy, 0.0)),         # 7: back top-left
    ]

    rot_mat = Matrix([
        [sx, fx, 0.0, 0.0],
        [sy, fy, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]
    ])
    loc_mat = Matrix.Translation(Vector((cloth_cx, cloth_cy, cloth_top_z)))
    tr = loc_mat @ rot_mat

    verts_front = [bm.verts.new(tr @ v) for v in local_front]
    verts_back  = [bm.verts.new(tr @ v) for v in local_back]

    uv_layer = bm.loops.layers.uv.verify()

    # Front face (outward toward fx, fy): CCW (0, 1, 2, 3)
    f_front = bm.faces.new([verts_front[0], verts_front[1], verts_front[2], verts_front[3]])
    f_front.material_index = MAT_INDEX_BANNER
    f_front.tag = True
    f_front.loops[0][uv_layer].uv = Vector((0.0, 1.0))
    f_front.loops[1][uv_layer].uv = Vector((0.0, 0.0))
    f_front.loops[2][uv_layer].uv = Vector((1.0, 0.0))
    f_front.loops[3][uv_layer].uv = Vector((1.0, 1.0))

    # Back face (facing backward): CCW (4, 5, 6, 7)
    f_back = bm.faces.new([verts_back[0], verts_back[1], verts_back[2], verts_back[3]])
    f_back.material_index = MAT_INDEX_BANNER
    f_back.tag = True
    f_back.loops[0][uv_layer].uv = Vector((0.0, 1.0))
    f_back.loops[1][uv_layer].uv = Vector((0.0, 0.0))
    f_back.loops[2][uv_layer].uv = Vector((1.0, 0.0))
    f_back.loops[3][uv_layer].uv = Vector((1.0, 1.0))

    # Top edge rim quad attaching to yardarm
    f_top = bm.faces.new([verts_front[0], verts_back[3], verts_back[0], verts_front[3]])
    f_top.material_index = MAT_INDEX_BANNER
    f_top.tag = True
    for lp in f_top.loops:
        lp[uv_layer].uv = Vector((0.5, 0.98))

    # 6. Suspension cloth straps looping over the crossbar (reference banners #1 & #3)
    strap_w = 0.09
    for sx_off in (-hx * 0.65, hx * 0.65):
        strap_cx = cloth_cx + sx * sx_off
        strap_cy = cloth_cy + sy * sx_off
        # Collar loop wrapped around the crossbar
        st_faces = create_cylinder(bm, radius=0.035, height=strap_w, segments=8,
                                   location=(strap_cx, strap_cy, bar_z),
                                   rotation=(0.0, 1.5708, ang_side), mat_index=MAT_INDEX_BANNER)
        for f in st_faces:
            f.tag = True

