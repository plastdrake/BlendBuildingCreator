"""
Primitive makeshift roof generator for low-tier industrial buildings.
Generates an authentic timber rafter truss structure, continuous draped canvas canopy
with custom fantasy textile shader (MAT_INDEX_TARP), and slope-aligned wooden weatherboards.
"""

import math
import random
from mathutils import Vector
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD,
    MAT_INDEX_TARP, MAT_INDEX_ROPE
)
from ..uv_utils import map_planar_faces


def build_makeshift_roof(bm, x_min, x_max, y_min, y_max, z_base, effective_archetype='NONE', seed=42):
    """
    Builds an authentic rustic industrial roof structure:
    1. Cross-rafter trusses resting solidly on the arcade posts with a low ridge.
    2. Longitudinal ridge and mid-slope purlins safely recessed underneath the roof covering.
    3. Smooth, continuous draped canvas canopy (MAT_INDEX_TARP) with eave overhang flaps.
    4. Weathered roof planks laid cleanly along the roof pitch across the purlins.
    5. Wooden hold-down battens and post tie-down ropes.
    """
    rng = random.Random(seed + 303)

    span_x = x_max - x_min
    span_y = y_max - y_min
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5

    is_x_long = span_x >= span_y
    long_len = span_x if is_x_long else span_y
    cross_span = span_y if is_x_long else span_x

    ridge_rise = min(0.70, max(0.42, cross_span * 0.08))
    z_ridge = z_base + ridge_rise
    eave_overhang = 0.35

    # -------------------------------------------------------------------------
    # 1. Rafter Trusses & Collar Ties across the building
    # -------------------------------------------------------------------------
    rafter_w = 0.12
    rafter_d = 0.10
    n_trusses = max(3, int(round(long_len / 3.4)) + 1)
    half_cross = cross_span * 0.5 + eave_overhang
    slope_len = math.sqrt(half_cross * half_cross + ridge_rise * ridge_rise)
    pitch_angle = math.atan2(ridge_rise, half_cross)

    # Rafters are shortened so their square ends never poke through the ridge peak
    # or protrude past the canvas eave flap.
    rafter_reach = cross_span * 0.5 + 0.18
    rafter_len = math.sqrt(rafter_reach * rafter_reach + (ridge_rise * (rafter_reach / max(0.1, half_cross))) ** 2) - 0.10
    rafter_cz = z_base + ridge_rise * 0.5 - 0.035

    for ti in range(n_trusses):
        t = ti / float(n_trusses - 1)
        long_pos = (t - 0.5) * (long_len - 0.10)

        if is_x_long:
            tx = cx + long_pos
            # Horizontal tie beam across the posts
            create_beveled_box(
                bm, size=(rafter_w, cross_span + 0.04, 0.14),
                location=(tx, cy, z_base - 0.02),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # Front slope rafter (slopes down toward front eave)
            r_front_cy = cy - rafter_reach * 0.5 - 0.04
            create_beveled_box(
                bm, size=(rafter_w, rafter_len, rafter_d),
                location=(tx, r_front_cy, rafter_cz),
                rotation=(pitch_angle, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # Back slope rafter (slopes down toward back eave)
            r_back_cy = cy + rafter_reach * 0.5 + 0.04
            create_beveled_box(
                bm, size=(rafter_w, rafter_len, rafter_d),
                location=(tx, r_back_cy, rafter_cz),
                rotation=(-pitch_angle, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # King post at center supporting ridge purlin from below
            kp_h = max(0.15, ridge_rise - 0.08)
            create_beveled_box(
                bm, size=(0.11, 0.11, kp_h),
                location=(tx, cy, z_base + kp_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )
        else:
            ty = cy + long_pos
            create_beveled_box(
                bm, size=(cross_span + 0.04, rafter_w, 0.14),
                location=(cx, ty, z_base - 0.02),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            r_left_cx = cx - rafter_reach * 0.5 - 0.04
            create_beveled_box(
                bm, size=(rafter_len, rafter_w, rafter_d),
                location=(r_left_cx, ty, rafter_cz),
                rotation=(0.0, -pitch_angle, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            r_right_cx = cx + rafter_reach * 0.5 + 0.04
            create_beveled_box(
                bm, size=(rafter_len, rafter_w, rafter_d),
                location=(r_right_cx, ty, rafter_cz),
                rotation=(0.0, pitch_angle, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            kp_h = max(0.15, ridge_rise - 0.08)
            create_beveled_box(
                bm, size=(0.11, 0.11, kp_h),
                location=(cx, ty, z_base + kp_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )

    # -------------------------------------------------------------------------
    # 2. Longitudinal Purlins (Ridge & Mid-Slopes) - Safely recessed under roof
    # -------------------------------------------------------------------------
    purlin_w = 0.10
    purlin_h = 0.08
    purlin_overhang = 0.15
    p_len = long_len + purlin_overhang * 2.0

    # Ridge purlin sits right below the roof peak (supporting it from beneath)
    if is_x_long:
        create_beveled_box(
            bm, size=(p_len, purlin_w, purlin_h),
            location=(cx, cy, z_ridge - 0.03),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
        )
        for sgn in (-1.0, 1.0):
            py = cy + sgn * (cross_span * 0.24)
            pz = z_base + ridge_rise * 0.5 - 0.035
            create_beveled_box(
                bm, size=(p_len, purlin_w, purlin_h),
                location=(cx, py, pz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
            )
    else:
        create_beveled_box(
            bm, size=(purlin_w, p_len, purlin_h),
            location=(cx, cy, z_ridge - 0.03),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
        )
        for sgn in (-1.0, 1.0):
            px = cx + sgn * (cross_span * 0.24)
            pz = z_base + ridge_rise * 0.5 - 0.035
            create_beveled_box(
                bm, size=(purlin_w, p_len, purlin_h),
                location=(px, cy, pz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
            )

    # -------------------------------------------------------------------------
    # 3. Continuous Draped Canvas Canopy (MAT_INDEX_TARP)
    # Covers one portion of the roof (e.g. 58% of length)
    # -------------------------------------------------------------------------
    tarp_ratio = 0.58
    tarp_long_len = long_len * tarp_ratio + 0.15
    cloth_t = 0.024
    roof_cz = z_base + ridge_rise * 0.5 + 0.03

    # Place canopy over the negative side (where saw/gear is)
    if is_x_long:
        tarp_cx = cx - (long_len * (1.0 - tarp_ratio) * 0.5)
        # Front slope canvas
        front_y_c = cy - half_cross * 0.5
        f_faces1 = create_beveled_box(
            bm, size=(tarp_long_len, slope_len + 0.04, cloth_t),
            location=(tarp_cx, front_y_c, roof_cz),
            rotation=(pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, f_faces1, scale=0.8, axis=1)

        # Front eave vertical hanging flap
        f_flap_y = cy - half_cross - 0.02
        f_flap_z = z_base - 0.04
        f_faces2 = create_beveled_box(
            bm, size=(tarp_long_len, cloth_t, 0.20),
            location=(tarp_cx, f_flap_y, f_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, f_faces2, scale=0.8, axis=1)

        # Back slope canvas
        back_y_c = cy + half_cross * 0.5
        b_faces1 = create_beveled_box(
            bm, size=(tarp_long_len, slope_len + 0.04, cloth_t),
            location=(tarp_cx, back_y_c, roof_cz),
            rotation=(-pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, b_faces1, scale=0.8, axis=1)

        # Back eave vertical hanging flap
        b_flap_y = cy + half_cross + 0.02
        b_flap_z = z_base - 0.04
        b_faces2 = create_beveled_box(
            bm, size=(tarp_long_len, cloth_t, 0.20),
            location=(tarp_cx, b_flap_y, b_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, b_faces2, scale=0.8, axis=1)

        # Clamping battens across the canvas (shortened at top so they don't poke over ridge)
        batten_len = slope_len - 0.08
        for b_frac in (-0.35, 0.0, 0.35):
            bx = tarp_cx + b_frac * (tarp_long_len - 0.20)
            for sgn in (-1.0, 1.0):
                by = cy + sgn * (half_cross * 0.5 + 0.02)
                bz = roof_cz + 0.02
                rot_x = pitch_angle if sgn < 0 else -pitch_angle
                create_beveled_box(
                    bm, size=(0.06, batten_len, 0.025),
                    location=(bx, by, bz),
                    rotation=(rot_x, 0.0, 0.0),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
                )

        # Tie ropes at canvas corners to timber posts
        for rx in (tarp_cx - tarp_long_len * 0.46, tarp_cx + tarp_long_len * 0.46):
            for sgn in (-1.0, 1.0):
                ry = cy + sgn * half_cross
                rope_h = 0.45
                create_cylinder(
                    bm, radius=0.016, height=rope_h, segments=6,
                    location=(rx, ry, z_base - rope_h * 0.5 + 0.02),
                    mat_index=MAT_INDEX_ROPE
                )
    else:
        tarp_cy = cy - (long_len * (1.0 - tarp_ratio) * 0.5)
        # Left slope canvas
        left_x_c = cx - half_cross * 0.5
        f_faces1 = create_beveled_box(
            bm, size=(slope_len + 0.04, tarp_long_len, cloth_t),
            location=(left_x_c, tarp_cy, roof_cz),
            rotation=(0.0, -pitch_angle, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, f_faces1, scale=0.8, axis=0)

        # Right slope canvas
        right_x_c = cx + half_cross * 0.5
        b_faces1 = create_beveled_box(
            bm, size=(slope_len + 0.04, tarp_long_len, cloth_t),
            location=(right_x_c, tarp_cy, roof_cz),
            rotation=(0.0, pitch_angle, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )
        map_planar_faces(bm, b_faces1, scale=0.8, axis=0)

    # -------------------------------------------------------------------------
    # 4. Roof Planks / Weatherboards along the pitch
    # Covers the remaining portion of the roof
    # -------------------------------------------------------------------------
    plank_section_start = long_len * (tarp_ratio - 0.5) - 0.10
    plank_section_end = long_len * 0.5 + 0.15
    plank_span = plank_section_end - plank_section_start
    n_plank_rows = max(3, int(plank_span / 0.28))

    plank_w = 0.22
    plank_t = 0.030

    for pi in range(n_plank_rows):
        p_frac = pi / float(n_plank_rows)
        p_offset = plank_section_start + p_frac * plank_span

        # Random slight length stagger (+/- 0.08m)
        p_len_var = (rng.random() - 0.5) * 0.16
        cur_plank_len = max(0.8, slope_len + p_len_var - 0.06)

        # Occasional missing plank for rustic open look
        if rng.random() < 0.18:
            continue

        jank_yaw = (rng.random() - 0.5) * 0.02
        jank_pitch = (rng.random() - 0.5) * 0.015

        if is_x_long:
            px = cx + p_offset
            for sgn in (-1.0, 1.0):
                if rng.random() < 0.12:
                    continue
                py = cy + sgn * (cur_plank_len * 0.5 + 0.02)
                pz = roof_cz + 0.015
                rot_x = (pitch_angle if sgn < 0 else -pitch_angle) + jank_pitch
                create_beveled_box(
                    bm, size=(plank_w, cur_plank_len, plank_t),
                    location=(px, py, pz),
                    rotation=(rot_x, 0.0, jank_yaw),
                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
                )
        else:
            py = cy + p_offset
            for sgn in (-1.0, 1.0):
                if rng.random() < 0.12:
                    continue
                px = cx + sgn * (cur_plank_len * 0.5 + 0.02)
                pz = roof_cz + 0.015
                rot_y = (-pitch_angle if sgn < 0 else pitch_angle) + jank_pitch
                create_beveled_box(
                    bm, size=(cur_plank_len, plank_w, plank_t),
                    location=(px, py, pz),
                    rotation=(0.0, rot_y, jank_yaw),
                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
                )
