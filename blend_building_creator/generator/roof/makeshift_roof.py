"""
Primitive makeshift roof generator for low-tier industrial buildings.
Generates rough timber rafters, scattered loose planks/boards, and draped weather cloth (tarpaulins).
"""

import math
import random
from mathutils import Vector
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD,
    MAT_INDEX_BANNER, MAT_INDEX_ROPE, MAT_INDEX_IRON
)


def build_makeshift_roof(bm, x_min, x_max, y_min, y_max, z_base, effective_archetype='NONE', seed=42):
    """
    Builds a primitive, makeshift overhead shelter:
    1. Perimeter header and cross tie-beams across posts.
    2. Slightly pitched rough timber rafters / purlins.
    3. Staggered, loose weathered wooden planks with slight jankiness and gaps.
    4. Draped sagging weather canvas / tarpaulin patches pinned with wood battens and tie ropes.
    """
    rng = random.Random(seed + 109)

    span_x = x_max - x_min
    span_y = y_max - y_min
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5

    # 1. Main cross tie-beams across the short axis
    # Decide short axis
    is_x_short = span_x <= span_y
    short_span = span_x if is_x_short else span_y
    long_span = span_y if is_x_short else span_x

    beam_w = 0.22
    beam_h = 0.22
    z_tie = z_base + beam_h * 0.5

    n_ties = max(2, int(round(long_span / 2.6)) + 1)
    tie_locs = []
    for ti in range(n_ties):
        t = ti / float(n_ties - 1)
        if is_x_short:
            # Short axis is X (-span_x/2 to span_x/2)
            by = y_min + t * span_y
            tie_locs.append((cx, by))
            create_beveled_box(
                bm, size=(span_x + 0.35, beam_w, beam_h),
                location=(cx, by, z_tie),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
            )
            # 45-deg diagonal knee braces at the ends
            for s in (-1.0, 1.0):
                px = cx + s * (span_x * 0.5 - 0.45)
                create_beveled_box(
                    bm, size=(0.14, 0.14, 0.70),
                    location=(px, by, z_base - 0.22),
                    rotation=(0.0, s * 0.785, 0.0),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
                )
        else:
            bx = x_min + t * span_x
            tie_locs.append((bx, cy))
            create_beveled_box(
                bm, size=(beam_w, span_y + 0.35, beam_h),
                location=(bx, cy, z_tie),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
            )
            for s in (-1.0, 1.0):
                py = cy + s * (span_y * 0.5 - 0.45)
                create_beveled_box(
                    bm, size=(0.14, 0.14, 0.70),
                    location=(bx, py, z_base - 0.22),
                    rotation=(-s * 0.785, 0.0, 0.0),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
                )

    # 2. Longitudinal Purlin Poles / Rafters resting on the tie-beams
    # Low pitch in the center: ~0.45m rise
    ridge_h = 0.50
    purlin_w = 0.14
    purlin_h = 0.14
    n_purlins = max(3, int(round(short_span / 1.4)) + 1)
    
    for pi in range(n_purlins):
        t = pi / float(n_purlins - 1) # 0.0 to 1.0 across short axis
        u = (t - 0.5) * 2.0 # -1.0 to 1.0
        # Parabolic rise towards center
        rz = z_base + beam_h + purlin_h * 0.5 + (1.0 - u * u) * ridge_h
        
        if is_x_short:
            px = x_min + t * span_x
            p_len = span_y + 0.50
            create_beveled_box(
                bm, size=(purlin_w, p_len, purlin_h),
                location=(px, cy, rz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
            )
        else:
            py = y_min + t * span_y
            p_len = span_x + 0.50
            create_beveled_box(
                bm, size=(p_len, purlin_w, purlin_h),
                location=(cx, py, rz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01
            )

    # 3. Scattered Loose Weatherboards / Planks
    # Planks span across purlins with irregular spacing, pitch, and random gaps
    plank_w = 0.24
    plank_t = 0.038
    plank_l = (short_span * 0.48) + 0.35
    n_bays = max(2, int(long_span / 0.55))
    
    for bi in range(n_bays):
        frac = bi / float(n_bays)
        # Skip ~25% of planks to give the weathered open feel
        if rng.random() < 0.28:
            continue

        along_pos = (frac - 0.5) * long_span * 0.94
        for side in (-1.0, 1.0):
            # Also occasionally skip one side
            if rng.random() < 0.20:
                continue

            jank_rot_z = (rng.random() - 0.5) * 0.06
            jank_tilt = (rng.random() - 0.5) * 0.04
            overhang_var = (rng.random() - 0.5) * 0.22

            u = 0.55
            z_surf = z_base + beam_h + purlin_h + (1.0 - u * u) * ridge_h + 0.02

            if is_x_short:
                px = cx + side * (short_span * 0.25 + overhang_var)
                py = cy + along_pos + (rng.random() - 0.5) * 0.08
                # Plank runs along X
                create_beveled_box(
                    bm, size=(plank_l, plank_w, plank_t),
                    location=(px, py, z_surf),
                    rotation=(jank_tilt, -side * (ridge_h / max(1.0, short_span * 0.5)) * 0.8, jank_rot_z),
                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
                )
            else:
                px = cx + along_pos + (rng.random() - 0.5) * 0.08
                py = cy + side * (short_span * 0.25 + overhang_var)
                # Plank runs along Y
                create_beveled_box(
                    bm, size=(plank_w, plank_l, plank_t),
                    location=(px, py, z_surf),
                    rotation=(side * (ridge_h / max(1.0, short_span * 0.5)) * 0.8, jank_tilt, jank_rot_z),
                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
                )

    # 4. Draped Weather Cloth / Canvas (Tarpaulin)
    # A heavy canvas tarp draped over a central/sheltered bay
    tarp_len = min(long_span * 0.65, 5.5)
    tarp_w = short_span + 0.70
    tarp_center_long = (rng.random() - 0.5) * (long_span * 0.25)
    
    # Mesh geometry for the draped tarp: 6-segment curve along short span
    n_segs = 6
    cloth_t = 0.02
    for si in range(n_segs):
        t1 = si / float(n_segs)
        t2 = (si + 1) / float(n_segs)
        u1 = (t1 - 0.5) * 2.0
        u2 = (t2 - 0.5) * 2.0
        
        # Sagging catenary
        sag1 = (1.0 - u1 * u1) * (ridge_h + 0.08) - 0.03 * math.sin(t1 * math.pi)
        sag2 = (1.0 - u2 * u2) * (ridge_h + 0.08) - 0.03 * math.sin(t2 * math.pi)
        z1 = z_base + beam_h + purlin_h + 0.06 + sag1
        z2 = z_base + beam_h + purlin_h + 0.06 + sag2
        
        cz = (z1 + z2) * 0.5
        seg_h = z2 - z1
        
        if is_x_short:
            x1 = cx + (t1 - 0.5) * tarp_w
            x2 = cx + (t2 - 0.5) * tarp_w
            seg_w = abs(x2 - x1)
            cx_seg = (x1 + x2) * 0.5
            cy_seg = cy + tarp_center_long
            slope = math.atan2(seg_h, max(0.001, x2 - x1))
            create_beveled_box(
                bm, size=(seg_w, tarp_len, cloth_t),
                location=(cx_seg, cy_seg, cz),
                rotation=(0.0, -slope, 0.0),
                mat_index=MAT_INDEX_BANNER, bevel_amount=0.004
            )
        else:
            y1 = cy + (t1 - 0.5) * tarp_w
            y2 = cy + (t2 - 0.5) * tarp_w
            seg_d = abs(y2 - y1)
            cx_seg = cx + tarp_center_long
            cy_seg = (y1 + y2) * 0.5
            slope = math.atan2(seg_h, max(0.001, y2 - y1))
            create_beveled_box(
                bm, size=(tarp_len, seg_d, cloth_t),
                location=(cx_seg, cy_seg, cz),
                rotation=(slope, 0.0, 0.0),
                mat_index=MAT_INDEX_BANNER, bevel_amount=0.004
            )

    # 5. Wood Battens pinning the cloth + Tie Ropes
    for b_off in [-tarp_len * 0.38, 0.0, tarp_len * 0.38]:
        batten_cz = z_base + beam_h + purlin_h + ridge_h * 0.65 + 0.10
        if is_x_short:
            create_beveled_box(
                bm, size=(tarp_w * 0.95, 0.08, 0.045),
                location=(cx, cy + tarp_center_long + b_off, batten_cz),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )
            # Tie ropes at ends hanging down to tie onto the posts
            for s in (-1.0, 1.0):
                rx = cx + s * (tarp_w * 0.48)
                ry = cy + tarp_center_long + b_off
                rope_h = max(0.4, batten_cz - z_base + 0.30)
                create_cylinder(
                    bm, radius=0.016, height=rope_h, segments=6,
                    location=(rx, ry, batten_cz - rope_h * 0.5),
                    mat_index=MAT_INDEX_ROPE
                )
        else:
            create_beveled_box(
                bm, size=(0.08, tarp_w * 0.95, 0.045),
                location=(cx + tarp_center_long + b_off, cy, batten_cz),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )
            for s in (-1.0, 1.0):
                rx = cx + tarp_center_long + b_off
                ry = cy + s * (tarp_w * 0.48)
                rope_h = max(0.4, batten_cz - z_base + 0.30)
                create_cylinder(
                    bm, radius=0.016, height=rope_h, segments=6,
                    location=(rx, ry, batten_cz - rope_h * 0.5),
                    mat_index=MAT_INDEX_ROPE
                )
