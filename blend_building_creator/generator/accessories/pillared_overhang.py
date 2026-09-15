"""
Pillared overhang / colonnade builder.

A projecting upper-floor portico carried on heavy vertical pillars that run all
the way down to the ground, with a framed timber soffit and rim beams.
"""

from mathutils import Vector, Matrix

from ..mesh_utils import create_beveled_box, create_cylinder
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD,
)
from ..facade import get_facade_frame


def build_pillared_overhang(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                            z_ground, z_ceiling, depth=1.6, pillar_count=3,
                            pillar_style='TIMBER_STONE', tier='TIER_3'):
    """
    Builds a colonnaded portico / upper overhang supported by heavy vertical pillars
    extending from the overhang header beam down to ground level.
    """
    wx, wy, ox, oy, tx, ty, rot_z = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)

    total_w = abs((wall_y_max - wall_y_min) if abs(ox) > 0.5 else (wall_x_max - wall_x_min)) * 0.88
    half_w = total_w * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d

    total_col_h = z_ceiling - z_ground
    outer_d = depth

    # 1. Outer Horizontal Header Beam
    header_w = 0.18
    header_h = 0.20
    create_beveled_box(
        bm,
        size=(header_w, total_w + 0.30, header_h),
        location=(wx + ox * (outer_d - header_w * 0.5), wy + oy * (outer_d - header_w * 0.5), z_ceiling - header_h * 0.5),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # 2. Vertical Pillars reaching all the way down to ground
    pillar_col_w = 0.18
    plinth_h = 0.25
    plinth_w = 0.36

    step_t = total_w / max(1, pillar_count - 1)
    for p_i in range(pillar_count):
        t_offset = -half_w + p_i * step_t
        px = wx + ox * (outer_d - header_w * 0.5) + tx * t_offset
        py = wy + oy * (outer_d - header_w * 0.5) + ty * t_offset

        if pillar_style == 'TIMBER_STONE':
            # Grounded stone plinth
            create_beveled_box(
                bm,
                size=(plinth_w, plinth_w, plinth_h),
                location=(px, py, z_ground + plinth_h * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )
            # Timber pillar post (embedded 1cm into plinth: no coplanar bottom face)
            shaft_h = total_col_h - plinth_h - header_h
            create_beveled_box(
                bm,
                size=(pillar_col_w, pillar_col_w, shaft_h + 0.01),
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5 - 0.01),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )
            brace_len = 1.05
            for sgn in ([-1] if p_i == pillar_count - 1 else ([1] if p_i == 0 else [-1, 1])):
                brace_dir = (Vector((tx, ty, 0.0)) * sgn + Vector((0.0, 0.0, 1.0))).normalized()
                brace_norm = Vector((ox, oy, 0.0)).normalized()
                brace_side = brace_dir.cross(brace_norm).normalized()
                brace_rot_mat = Matrix((brace_norm, brace_side, brace_dir)).transposed().to_4x4()

                loc_b = Vector((px, py, z_ceiling - header_h + 0.02)) + (Vector((tx, ty, 0.0)) * sgn * 0.32 - Vector((0.0, 0.0, 0.32)))
                create_beveled_box(
                    bm,
                    size=(0.12, 0.12, brace_len),
                    location=loc_b,
                    rotation=brace_rot_mat.to_euler(),
                    mat_index=MAT_INDEX_TIMBER_FRAME,
                    bevel_amount=0.008
                )
        elif pillar_style == 'ROUND_POST':
            # Round log post
            create_cylinder(
                bm,
                radius=0.18, height=plinth_h, segments=12,
                location=(px, py, z_ground + plinth_h * 0.5),
                mat_index=MAT_INDEX_STONE
            )
            shaft_h = total_col_h - plinth_h - header_h
            create_cylinder(
                bm,
                radius=0.11, height=shaft_h, segments=12,
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME
            )
        else:  # STONE_COLUMN
            # Full chunky masonry pier
            create_beveled_box(
                bm,
                size=(0.32, 0.32, total_col_h - header_h),
                location=(px, py, z_ground + (total_col_h - header_h) * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )

    # 3. Timber Framing Beams Covering the Exterior Wall Box:
    box_w = (total_w + 0.12) * 1.2
    box_d = (depth + 0.12) * 1.2
    box_half_w = box_w * 0.5
    soffit_cx = wx + ox * (half_d + 0.06)
    soffit_cy = wy + oy * (half_d + 0.06)

    rim_t = 0.16
    rim_h = 0.22
    rim_z = z_ceiling - 0.075

    # Left Rim Beam (covering left side face of the box)
    w_left_rim = Vector((soffit_cx, soffit_cy, rim_z)) + Vector((tx, ty, 0.0)) * (-box_half_w + rim_t * 0.5)
    create_beveled_box(
        bm,
        size=(box_d + 0.04, rim_t, rim_h),
        location=w_left_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Right Rim Beam (covering right side face of the box)
    w_right_rim = Vector((soffit_cx, soffit_cy, rim_z)) + Vector((tx, ty, 0.0)) * (box_half_w - rim_t * 0.5)
    create_beveled_box(
        bm,
        size=(box_d + 0.04, rim_t, rim_h),
        location=w_right_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Front Rim Beam (fit between side rims so corner tops are not coplanar-overlapped)
    front_dist = half_d + 0.06 + box_d * 0.5 - rim_t * 0.5
    w_front_rim = Vector((wx + ox * front_dist, wy + oy * front_dist, rim_z + 0.008))
    create_beveled_box(
        bm,
        size=(rim_t, box_w - rim_t * 2.0 + 0.02, rim_h),
        location=w_front_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Rear Ledger Beam along building wall
    rear_dist = half_d + 0.06 - box_d * 0.5 + rim_t * 0.5
    w_rear_rim = Vector((wx + ox * rear_dist, wy + oy * rear_dist, rim_z + 0.008))
    create_beveled_box(
        bm,
        size=(rim_t, box_w - rim_t * 2.0 + 0.02, rim_h),
        location=w_rear_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Ceiling joist beams underneath the overhang - spanning full width between left and right rim beams
    beam_spacing = 0.60
    usable_w = box_w - rim_t * 2.0
    num_beams = max(pillar_count + 1, int(usable_w / beam_spacing) + 1)
    actual_spacing = usable_w / max(1, num_beams - 1) if num_beams > 1 else usable_w
    for b_i in range(num_beams):
        t_off = -usable_w * 0.5 + b_i * actual_spacing
        bx = soffit_cx + tx * t_off
        by = soffit_cy + ty * t_off
        create_beveled_box(
            bm,
            size=(box_d - rim_t * 1.5, 0.12, 0.14),
            location=(bx, by, z_ceiling - 0.09),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    # Wood soffit inside ceiling (inset 2cm from rim outer faces: no coplanar edges)
    create_beveled_box(
        bm,
        size=(box_d - 0.04, box_w - 0.04, 0.06),
        location=(soffit_cx, soffit_cy, z_ceiling - 0.02),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Soffit paneling - framed cleanly between the timber beams.
    # Tier-correct: stucco only for Tier 3, otherwise warm wood/planks.
    ext_mat = MAT_INDEX_PLASTER_EXT if tier == 'TIER_3' else MAT_INDEX_WOOD
    create_beveled_box(
        bm,
        size=(box_d - 0.06, box_w - 0.06, 0.07),
        location=(soffit_cx, soffit_cy, z_ceiling - 0.075),
        rotation=(0.0, 0.0, rot_z),
        mat_index=ext_mat,
        bevel_amount=0.006
    )
    # Fascia closure at wall line to hide slab side
    fascia_x = wx + ox * 0.06
    fascia_y = wy + oy * 0.06
    create_beveled_box(bm, size=(0.14, total_w + 0.18, 0.16), location=(fascia_x, fascia_y, z_ceiling - 0.08), rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
    # Ground flagstone platform
    create_beveled_box(
        bm,
        size=(depth + 0.20, total_w + 0.35, 0.12),
        location=(cx, cy, z_ground + 0.06),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )
