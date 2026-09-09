"""
Stylized Fantasy Roof Generator: curved saddle/sway roofs, steep medieval gables,
conical turrets, layered shingles, dormer windows, and crooked stone chimneys.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cone, create_cylinder, create_horizontal_cylinder
from .materials import (
    MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER, MAT_INDEX_STONE,
    MAT_INDEX_GLASS, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_IRON
)

def build_gable_physical_siding(bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
                               z_base, ez, rz, deck_thick, slope, tier='TIER_3', plank_direction='HORIZONTAL'):
    """
    Populates the triangular gable wall under the roof pitch with physical 3D
    horizontal rounded logs (Tier 1) or overlapping/batten planks (Tier 2) sliced
    to match the sloping rafters with zero gap.
    """
    if tier not in ('TIER_1', 'TIER_2'):
        return

    z_deck_top = rz - deck_thick
    y_siding = gy + g_norm * (half_wt + 0.05)
    total_gable_h = z_deck_top - z_base
    if total_gable_h < 0.3:
        return

    def get_width_at_z(z_val):
        x_l = rx_min + (z_val + deck_thick - ez) / max(0.01, slope)
        x_r = rx_max - (z_val + deck_thick - ez) / max(0.01, slope)
        x_l = max(x_min, min(cx - 0.05, x_l))
        x_r = min(x_max, max(cx + 0.05, x_r))
        return x_l, x_r

    if tier == 'TIER_1':
        # Stacked physical rounded horizontal logs matching lower walls
        log_h = 0.28
        num_logs = int(math.ceil(total_gable_h / log_h))
        for k in range(num_logs):
            cur_z = z_base + (k + 0.5) * log_h
            if cur_z >= z_deck_top - 0.08:
                break
            x_l, x_r = get_width_at_z(cur_z)
            span = x_r - x_l
            if span < 0.25:
                break
            mid_x = (x_l + x_r) * 0.5
            create_horizontal_cylinder(
                bm,
                radius_y=0.11,
                radius_z=0.125,
                length=span + 0.06,
                segments=16,
                location=(mid_x, y_siding, cur_z),
                rotation=(0.0, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER,
                smooth=True
            )
    elif tier == 'TIER_2':
        if plank_direction == 'VERTICAL':
            # Vertical board siding trimmed to sloping rafters
            target_bw = 0.22
            full_w = x_max - x_min
            num_boards = max(1, int(round(full_w / target_bw)))
            actual_bw = full_w / num_boards
            for b in range(num_boards):
                bx = x_min + (b + 0.5) * actual_bw
                dist_from_cx = abs(bx - cx)
                z_rafter = z_deck_top - dist_from_cx * slope
                bh = max(0.15, z_rafter - z_base)
                bz = z_base + bh * 0.5
                create_beveled_box(
                    bm,
                    size=(actual_bw - 0.01, 0.024, bh),
                    location=(bx, y_siding, bz),
                    mat_index=MAT_INDEX_TIMBER,
                    bevel_amount=0.004
                )
        else:
            # Horizontal weatherboards sliced to triangle
            plank_h = 0.20
            reveal = 0.17
            num_planks = int(math.ceil(total_gable_h / reveal))
            for p in range(num_planks):
                cur_z = z_base + p * reveal + plank_h * 0.5
                if cur_z >= z_deck_top - 0.05:
                    break
                x_l, x_r = get_width_at_z(cur_z)
                span = x_r - x_l
                if span < 0.20:
                    break
                mid_x = (x_l + x_r) * 0.5
                row_step = (p % 2) * 0.006
                create_beveled_box(
                    bm,
                    size=(span + 0.04, 0.026, plank_h),
                    location=(mid_x, y_siding + g_norm * row_step, cur_z),
                    mat_index=MAT_INDEX_TIMBER,
                    bevel_amount=0.004
                )

def build_sway_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=2.8, overhang=0.45,
                    sway_amount=0.25, segments_y=6, wall_thickness=0.28, gable_ends=('FRONT', 'BACK'),
                    abut_back=False, tier='TIER_3', plank_direction='HORIZONTAL'):
    """
    Builds a whimsical fairytale curved/saddle roof with flared eaves, saggy ridge,
    solid 0.12m thick timber roof decking, thick volumetric gable walls, and full eave closures.
    abut_back: If True, roof deck, ridge, and shingles terminate flush at y_max with zero rear overhang.
    """
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max if abut_back else (y_max + overhang)
    
    total_w = rx_max - rx_min
    total_d = ry_max - ry_min
    
    cx = (rx_min + rx_max) * 0.5
    deck_thick = 0.12
    
    # 1. Solid Volumetric 3D Timber Roof Deck (Left and Right Slopes)
    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d
        
        sag0 = math.sin(t0 * math.pi) * sway_amount
        sag1 = math.sin(t1 * math.pi) * sway_amount
        
        rz0 = z_base + roof_height - sag0
        rz1 = z_base + roof_height - sag1
        ez = z_base - 0.12 # Eaves level
        
        # --- Left Slope Solid Slab ---
        s_left = Vector((cx - rx_min, 0.0, (rz0 + rz1) * 0.5 - ez))
        # Vector pointing inward/downward into attic
        inward_l = Vector((s_left.z, 0.0, -s_left.x)).normalized() * deck_thick
        
        vl0_t = bm.verts.new(Vector((rx_min, y0, ez)))
        vl1_t = bm.verts.new(Vector((rx_min, y1, ez)))
        vr1_t = bm.verts.new(Vector((cx, y1, rz1)))
        vr0_t = bm.verts.new(Vector((cx, y0, rz0)))
        
        vl0_b = bm.verts.new(Vector((rx_min, y0, ez)) + inward_l)
        vl1_b = bm.verts.new(Vector((rx_min, y1, ez)) + inward_l)
        vr1_b = bm.verts.new(Vector((cx, y1, rz1)) + inward_l)
        vr0_b = bm.verts.new(Vector((cx, y0, rz0)) + inward_l)
        
        # Deck faces: top, bottom, outer eave side
        f_top_l = bm.faces.new([vl0_t, vl1_t, vr1_t, vr0_t])
        f_top_l.material_index = MAT_INDEX_TIMBER
        f_bot_l = bm.faces.new([vr0_b, vr1_b, vl1_b, vl0_b])
        f_bot_l.material_index = MAT_INDEX_TIMBER
        f_eave_l = bm.faces.new([vl0_t, vl0_b, vl1_b, vl1_t])
        f_eave_l.material_index = MAT_INDEX_TIMBER
        
        if j == 0:
            f_fl = bm.faces.new([vr0_t, vr0_b, vl0_b, vl0_t])
            f_fl.material_index = MAT_INDEX_TIMBER
        if j == segments_y - 1:
            f_rl = bm.faces.new([vl1_t, vl1_b, vr1_b, vr1_t])
            f_rl.material_index = MAT_INDEX_TIMBER
            
        # --- Right Slope Solid Slab ---
        delta_xr = rx_max - cx
        delta_zr = (rz0 + rz1) * 0.5 - ez
        inward_r = Vector((-delta_zr, 0.0, -delta_xr)).normalized() * deck_thick
        
        vrr0_t = bm.verts.new(Vector((rx_max, y0, ez)))
        vrr1_t = bm.verts.new(Vector((rx_max, y1, ez)))
        
        vrr0_b = bm.verts.new(Vector((rx_max, y0, ez)) + inward_r)
        vrr1_b = bm.verts.new(Vector((rx_max, y1, ez)) + inward_r)
        vr1_rb = bm.verts.new(Vector((cx, y1, rz1)) + inward_r)
        vr0_rb = bm.verts.new(Vector((cx, y0, rz0)) + inward_r)
        
        f_top_r = bm.faces.new([vr0_t, vr1_t, vrr1_t, vrr0_t])
        f_top_r.material_index = MAT_INDEX_TIMBER
        f_bot_r = bm.faces.new([vrr0_b, vrr1_b, vr1_rb, vr0_rb])
        f_bot_r.material_index = MAT_INDEX_TIMBER
        f_eave_r = bm.faces.new([vrr1_t, vrr1_b, vrr0_b, vrr0_t])
        f_eave_r.material_index = MAT_INDEX_TIMBER
        
        if j == 0:
            f_fr = bm.faces.new([vrr0_t, vrr0_b, vr0_rb, vr0_t])
            f_fr.material_index = MAT_INDEX_TIMBER
        if j == segments_y - 1:
            f_rr = bm.faces.new([vr1_t, vr1_rb, vrr1_b, vrr1_t])
            f_rr.material_index = MAT_INDEX_TIMBER

    # 2. Volumetric Gable End Walls matching exact roof pitch with zero gaps
    half_wt = wall_thickness * 0.5
    deck_thick = 0.12
    gable_configs = []
    if 'FRONT' in gable_ends:
        gable_configs.append((y_min, -1))
    if 'BACK' in gable_ends:
        gable_configs.append((y_max, 1))
    for gy, g_norm in gable_configs:
        y_ext = gy + g_norm * (half_wt + 0.005)
        y_int = gy - g_norm * half_wt
        
        # Sag at this gable wall (t_y = 0 or 1, sag = 0)
        rz = z_base + roof_height
        
        # Underside of roof deck at wall boundaries and ridge
        delta_x = cx - rx_min
        delta_z = rz - ez
        slope = delta_z / max(0.01, delta_x)
        
        # Height of deck underside at x_min and x_max
        z_deck_left = ez + (x_min - rx_min) * slope - deck_thick
        z_deck_right = ez + (rx_max - x_max) * slope - deck_thick
        z_deck_top = rz - deck_thick
        
        # 5-vertex polygon on exterior face: Base-L, Base-R, Mid-R, Apex, Mid-L
        v_ext_bl = bm.verts.new(Vector((x_min, y_ext, z_base)))
        v_ext_br = bm.verts.new(Vector((x_max, y_ext, z_base)))
        v_ext_mr = bm.verts.new(Vector((x_max, y_ext, z_deck_right)))
        v_ext_t  = bm.verts.new(Vector((cx, y_ext, z_deck_top)))
        v_ext_ml = bm.verts.new(Vector((x_min, y_ext, z_deck_left)))
        
        # Matching interior vertices
        v_int_bl = bm.verts.new(Vector((x_min, y_int, z_base)))
        v_int_br = bm.verts.new(Vector((x_max, y_int, z_base)))
        v_int_mr = bm.verts.new(Vector((x_max, y_int, z_deck_right)))
        v_int_t  = bm.verts.new(Vector((cx, y_int, z_deck_top)))
        v_int_ml = bm.verts.new(Vector((x_min, y_int, z_deck_left)))
        
        gable_mat = MAT_INDEX_TIMBER if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
        if g_norm < 0:
            bm.faces.new([v_ext_bl, v_ext_br, v_ext_mr, v_ext_t, v_ext_ml]).material_index = gable_mat
            bm.faces.new([v_int_ml, v_int_t, v_int_mr, v_int_br, v_int_bl]).material_index = MAT_INDEX_PLASTER_INT
        else:
            bm.faces.new([v_ext_ml, v_ext_t, v_ext_mr, v_ext_br, v_ext_bl]).material_index = gable_mat
            bm.faces.new([v_int_bl, v_int_br, v_int_mr, v_int_t, v_int_ml]).material_index = MAT_INDEX_PLASTER_INT
            
        # Top sloping boundary seals (under roof deck)
        bm.faces.new([v_ext_ml, v_ext_t, v_int_t, v_int_ml]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_t, v_ext_mr, v_int_mr, v_int_t]).material_index = MAT_INDEX_TIMBER
        
        # Vertical side boundary seals at x_min and x_max
        bm.faces.new([v_ext_bl, v_ext_ml, v_int_ml, v_int_bl]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_mr, v_ext_br, v_int_br, v_int_mr]).material_index = MAT_INDEX_TIMBER
        
        # Eaves Soffit Box: completely closes the open wedge between rx_min/rx_max and x_min/x_max
        for side_sign, rx_eave, x_wall, z_deck_side in [(-1, rx_min, x_min, z_deck_left), (1, rx_max, x_max, z_deck_right)]:
            v_s_eave_ext = bm.verts.new(Vector((rx_eave, y_ext, ez)))
            v_s_wall_ext = bm.verts.new(Vector((x_wall, y_ext, z_base)))
            v_s_top_ext  = bm.verts.new(Vector((x_wall, y_ext, z_deck_side)))
            
            v_s_eave_int = bm.verts.new(Vector((rx_eave, y_int, ez)))
            v_s_wall_int = bm.verts.new(Vector((x_wall, y_int, z_base)))
            v_s_top_int  = bm.verts.new(Vector((x_wall, y_int, z_deck_side)))
            
            if (g_norm * side_sign) < 0:
                bm.faces.new([v_s_eave_ext, v_s_wall_ext, v_s_top_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_top_int, v_s_wall_int, v_s_eave_int]).material_index = MAT_INDEX_TIMBER
            else:
                bm.faces.new([v_s_top_ext, v_s_wall_ext, v_s_eave_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_eave_int, v_s_wall_int, v_s_top_int]).material_index = MAT_INDEX_TIMBER
            # Underside face of soffit
            bm.faces.new([v_s_eave_ext, v_s_eave_int, v_s_wall_int, v_s_wall_ext]).material_index = MAT_INDEX_TIMBER
            
        # Physical 3D siding for gable wall matching lower walls (Tier 1 logs or Tier 2 planks)
        build_gable_physical_siding(
            bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
            z_base, ez, rz, deck_thick, slope, tier=tier, plank_direction=plank_direction
        )
            
        # Decorative Horizontal Timber Belt at gable base
        create_beveled_box(
            bm,
            size=(x_max - x_min + 0.16, 0.12, 0.14),
            location=(cx, gy + g_norm * (half_wt + 0.04), z_base + 0.07),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012
        )
        # Vertical King Post Beam
        post_h = z_deck_top - z_base
        create_beveled_box(
            bm,
            size=(0.14, 0.10, post_h),
            location=(cx, gy + g_norm * (half_wt + 0.03), z_base + post_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.01
        )
        
        # Verge Bargeboards along gable rafter slopes (capping the verge overhang)
        b_len = math.sqrt(delta_x * delta_x + delta_z * delta_z) + 0.10
        b_ang = math.atan2(delta_z, delta_x)
        b_mid_z = (ez + rz) * 0.5
        y_verge = ry_min + 0.04 if g_norm < 0 else ry_max - 0.04
        
        b_mid_l = Vector(((rx_min + cx) * 0.5, y_verge, b_mid_z))
        create_box(bm, size=(b_len, 0.08, 0.14), location=b_mid_l, rotation=(0.0, -b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)
        b_mid_r = Vector(((rx_max + cx) * 0.5, y_verge, b_mid_z))
        create_box(bm, size=(b_len, 0.08, 0.14), location=b_mid_r, rotation=(0.0, b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)

    # 3. Eaves Fascia & Segmented Ridge Beams (curves with sway and wonkiness)
    fascia_d = total_d if abut_back else total_d + 0.15
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    # Segmented Ridge Beam along Y: each segment follows local (rz0, rz1)
    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d
        sag0 = math.sin(t0 * math.pi) * sway_amount
        sag1 = math.sin(t1 * math.pi) * sway_amount
        rz0 = z_base + roof_height - sag0
        rz1 = z_base + roof_height - sag1
        
        mid_y = (y0 + y1) * 0.5
        mid_z = (rz0 + rz1) * 0.5 + 0.05
        dy = y1 - y0
        dz = rz1 - rz0
        extra_len = 0.01 if (abut_back and j == segments_y - 1) else 0.04
        seg_len = math.sqrt(dy * dy + dz * dz) + extra_len
        seg_pitch = math.atan2(dz, dy)
        
        create_beveled_box(
            bm,
            size=(0.20, seg_len, 0.22),
            location=(cx, mid_y, mid_z),
            rotation=(seg_pitch, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.015
        )

def build_gable_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=3.0, overhang=0.45, wall_thickness=0.28, gable_ends=('FRONT', 'BACK'), segments_y=6, abut_back=False, tier='TIER_3', plank_direction='HORIZONTAL'):
    """
    Builds a classic steep medieval gable roof with solid 0.12m thick timber decking,
    thick volumetric gable walls, and complete eave closures.
    Segmented along Y to allow organic wonkiness and curvature deformation.
    abut_back: If True, roof deck, ridge, and shingles terminate flush at y_max with zero rear overhang.
    """
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max if abut_back else (y_max + overhang)
    total_d = ry_max - ry_min
    
    cx = (x_min + x_max) * 0.5
    rz = z_base + roof_height
    ez = z_base - 0.10
    deck_thick = 0.12
    
    # 1. Solid Volumetric 3D Timber Roof Deck (Left and Right Slopes, Segmented)
    s_left = Vector((cx - rx_min, 0.0, rz - ez))
    inward_l = Vector((s_left.z, 0.0, -s_left.x)).normalized() * deck_thick
    delta_xr = rx_max - cx
    delta_zr = rz - ez
    inward_r = Vector((-delta_zr, 0.0, -delta_xr)).normalized() * deck_thick

    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d

        # Left slope
        vl0_t = bm.verts.new(Vector((rx_min, y0, ez)))
        vl1_t = bm.verts.new(Vector((rx_min, y1, ez)))
        vr1_t = bm.verts.new(Vector((cx, y1, rz)))
        vr0_t = bm.verts.new(Vector((cx, y0, rz)))

        vl0_b = bm.verts.new(Vector((rx_min, y0, ez)) + inward_l)
        vl1_b = bm.verts.new(Vector((rx_min, y1, ez)) + inward_l)
        vr1_b = bm.verts.new(Vector((cx, y1, rz)) + inward_l)
        vr0_b = bm.verts.new(Vector((cx, y0, rz)) + inward_l)

        bm.faces.new([vl0_t, vl1_t, vr1_t, vr0_t]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([vr0_b, vr1_b, vl1_b, vl0_b]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([vl0_t, vl0_b, vl1_b, vl1_t]).material_index = MAT_INDEX_TIMBER
        if j == 0:
            bm.faces.new([vr0_t, vr0_b, vl0_b, vl0_t]).material_index = MAT_INDEX_TIMBER
        if j == segments_y - 1:
            bm.faces.new([vl1_t, vl1_b, vr1_b, vr1_t]).material_index = MAT_INDEX_TIMBER

        # Right slope
        vrr0_t = bm.verts.new(Vector((rx_max, y0, ez)))
        vrr1_t = bm.verts.new(Vector((rx_max, y1, ez)))

        vrr0_b = bm.verts.new(Vector((rx_max, y0, ez)) + inward_r)
        vrr1_b = bm.verts.new(Vector((rx_max, y1, ez)) + inward_r)
        vr1_rb = bm.verts.new(Vector((cx, y1, rz)) + inward_r)
        vr0_rb = bm.verts.new(Vector((cx, y0, rz)) + inward_r)

        bm.faces.new([vr0_t, vr1_t, vrr1_t, vrr0_t]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([vrr0_b, vrr1_b, vr1_rb, vr0_rb]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([vrr1_t, vrr1_b, vrr0_b, vrr0_t]).material_index = MAT_INDEX_TIMBER
        if j == 0:
            bm.faces.new([vrr0_t, vrr0_b, vr0_rb, vr0_t]).material_index = MAT_INDEX_TIMBER
        if j == segments_y - 1:
            bm.faces.new([vr1_t, vr1_rb, vrr1_b, vrr1_t]).material_index = MAT_INDEX_TIMBER
    
    # 2. Volumetric Gable End Walls matching exact roof pitch with zero gaps
    half_wt = wall_thickness * 0.5
    gable_configs = []
    if 'FRONT' in gable_ends:
        gable_configs.append((y_min, -1))
    if 'BACK' in gable_ends:
        gable_configs.append((y_max, 1))
    for gy, g_norm in gable_configs:
        y_ext = gy + g_norm * (half_wt + 0.005)
        y_int = gy - g_norm * half_wt
        
        # Underside of roof deck at wall boundaries and ridge
        delta_x = cx - rx_min
        delta_z = rz - ez
        slope = delta_z / max(0.01, delta_x)
        
        z_deck_left = ez + (x_min - rx_min) * slope - deck_thick
        z_deck_right = ez + (rx_max - x_max) * slope - deck_thick
        z_deck_top = rz - deck_thick
        
        # 5-vertex polygon on exterior face: Base-L, Base-R, Mid-R, Apex, Mid-L
        v_ext_bl = bm.verts.new(Vector((x_min, y_ext, z_base)))
        v_ext_br = bm.verts.new(Vector((x_max, y_ext, z_base)))
        v_ext_mr = bm.verts.new(Vector((x_max, y_ext, z_deck_right)))
        v_ext_t  = bm.verts.new(Vector((cx, y_ext, z_deck_top)))
        v_ext_ml = bm.verts.new(Vector((x_min, y_ext, z_deck_left)))
        
        # Matching interior vertices
        v_int_bl = bm.verts.new(Vector((x_min, y_int, z_base)))
        v_int_br = bm.verts.new(Vector((x_max, y_int, z_base)))
        v_int_mr = bm.verts.new(Vector((x_max, y_int, z_deck_right)))
        v_int_t  = bm.verts.new(Vector((cx, y_int, z_deck_top)))
        v_int_ml = bm.verts.new(Vector((x_min, y_int, z_deck_left)))
        
        gable_mat = MAT_INDEX_TIMBER if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
        if g_norm < 0:
            bm.faces.new([v_ext_bl, v_ext_br, v_ext_mr, v_ext_t, v_ext_ml]).material_index = gable_mat
            bm.faces.new([v_int_ml, v_int_t, v_int_mr, v_int_br, v_int_bl]).material_index = MAT_INDEX_PLASTER_INT
        else:
            bm.faces.new([v_ext_ml, v_ext_t, v_ext_mr, v_ext_br, v_ext_bl]).material_index = gable_mat
            bm.faces.new([v_int_bl, v_int_br, v_int_mr, v_int_t, v_int_ml]).material_index = MAT_INDEX_PLASTER_INT
            
        # Top sloping boundary seals (under roof deck)
        bm.faces.new([v_ext_ml, v_ext_t, v_int_t, v_int_ml]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_t, v_ext_mr, v_int_mr, v_int_t]).material_index = MAT_INDEX_TIMBER
        
        # Vertical side boundary seals at x_min and x_max
        bm.faces.new([v_ext_bl, v_ext_ml, v_int_ml, v_int_bl]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_mr, v_ext_br, v_int_br, v_int_mr]).material_index = MAT_INDEX_TIMBER
        
        # Eaves Soffit Box: completely closes the open wedge between rx_min/rx_max and x_min/x_max
        for side_sign, rx_eave, x_wall, z_deck_side in [(-1, rx_min, x_min, z_deck_left), (1, rx_max, x_max, z_deck_right)]:
            v_s_eave_ext = bm.verts.new(Vector((rx_eave, y_ext, ez)))
            v_s_wall_ext = bm.verts.new(Vector((x_wall, y_ext, z_base)))
            v_s_top_ext  = bm.verts.new(Vector((x_wall, y_ext, z_deck_side)))
            
            v_s_eave_int = bm.verts.new(Vector((rx_eave, y_int, ez)))
            v_s_wall_int = bm.verts.new(Vector((x_wall, y_int, z_base)))
            v_s_top_int  = bm.verts.new(Vector((x_wall, y_int, z_deck_side)))
            
            if (g_norm * side_sign) < 0:
                bm.faces.new([v_s_eave_ext, v_s_wall_ext, v_s_top_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_top_int, v_s_wall_int, v_s_eave_int]).material_index = MAT_INDEX_TIMBER
            else:
                bm.faces.new([v_s_top_ext, v_s_wall_ext, v_s_eave_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_eave_int, v_s_wall_int, v_s_top_int]).material_index = MAT_INDEX_TIMBER
            bm.faces.new([v_s_eave_ext, v_s_eave_int, v_s_wall_int, v_s_wall_ext]).material_index = MAT_INDEX_TIMBER
            
        # Physical 3D siding for gable wall matching lower walls (Tier 1 logs or Tier 2 planks)
        build_gable_physical_siding(
            bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
            z_base, ez, rz, deck_thick, slope, tier=tier, plank_direction=plank_direction
        )
            
        # Decorative Horizontal Timber Belt at gable base
        create_beveled_box(
            bm,
            size=(x_max - x_min + 0.16, 0.12, 0.14),
            location=(cx, gy + g_norm * (half_wt + 0.04), z_base + 0.07),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012
        )
        # Vertical King Post Beam
        post_h = z_deck_top - z_base
        create_beveled_box(
            bm,
            size=(0.14, 0.10, post_h),
            location=(cx, gy + g_norm * (half_wt + 0.03), z_base + post_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.01
        )
        
        # Verge Bargeboards along gable rafter slopes (capping the verge overhang)
        b_len = math.sqrt(delta_x * delta_x + delta_z * delta_z) + 0.10
        b_ang = math.atan2(delta_z, delta_x)
        b_mid_z = (ez + rz) * 0.5
        y_verge = ry_min + 0.04 if g_norm < 0 else ry_max - 0.04
        
        b_mid_l = Vector(((rx_min + cx) * 0.5, y_verge, b_mid_z))
        create_box(bm, size=(b_len, 0.08, 0.14), location=b_mid_l, rotation=(0.0, -b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)
        b_mid_r = Vector(((rx_max + cx) * 0.5, y_verge, b_mid_z))
        create_box(bm, size=(b_len, 0.08, 0.14), location=b_mid_r, rotation=(0.0, b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)

    # 3. Eaves Fascia & Ridge Beams
    fascia_d = total_d if abut_back else total_d + 0.15
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    # Segmented Ridge Beam along Y
    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d
        extra_len = 0.01 if (abut_back and j == segments_y - 1) else 0.04
        seg_len = (y1 - y0) + extra_len
        create_beveled_box(
            bm,
            size=(0.20, seg_len, 0.22),
            location=(cx, (y0 + y1) * 0.5, rz + 0.05),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.015
        )

def build_conical_turret_roof(bm, center_pos, radius=2.2, height=3.8, segments=12):
    """
    Builds a wizard turret / conical roof with flared eaves and a finial spire.
    """
    cx, cy, z_base = center_pos
    # Main cone
    create_cone(
        bm,
        radius1=radius,
        radius2=0.08,
        height=height,
        segments=segments,
        location=(cx, cy, z_base + height * 0.5),
        mat_index=MAT_INDEX_SHINGLES
    )
    # Eaves rim
    create_cylinder(
        bm,
        radius=radius + 0.12,
        height=0.20,
        segments=segments,
        location=(cx, cy, z_base + 0.10),
        mat_index=MAT_INDEX_TIMBER
    )
    # Spire / finial
    create_cone(
        bm,
        radius1=0.12,
        radius2=0.02,
        height=1.0,
        segments=8,
        location=(cx, cy, z_base + height + 0.5),
        mat_index=MAT_INDEX_STONE
    )

def build_shingle_layers(bm, x_min, x_max, y_min, y_max, z_base, roof_height=2.8,
                         rows=6, seed=42, overhang=0.45, sway_amount=0.25, roof_style='SWAY',
                         abut_back=False):
    """
    Generates chunky stylized overlapping shingle rows that match the exact roof slope
    and sway sag profile, offset safely above the timber deck to eliminate clipping and overlap.
    abut_back: If True, shingles stop flush at y_max with zero rear overhang.
    """
    rng = random.Random(seed)
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max if abut_back else (y_max + overhang)
    total_w = rx_max - rx_min
    total_d = ry_max - ry_min
    
    cx = (rx_min + rx_max) * 0.5
    half_w = total_w * 0.5
    ez = z_base - 0.12 # Matching exact eaves level
    
    # Shingle dimensions: width along Y, length along slope, thickness along normal
    shingle_w = 0.44
    usable_d = max(0.5, total_d - shingle_w)
    cols = max(3, int(usable_d / (shingle_w * 0.78)) + 1)
    step_y = usable_d / max(1, cols - 1)
    
    for side in [-1, 1]:
        tilt_sign = 1 if side < 0 else -1
        
        for r in range(rows):
            t = (r + 0.45) / max(1, rows)
            
            # Base column positions covering verge to verge
            y_positions = [ry_min + shingle_w * 0.5 + c * step_y for c in range(cols)]
            if r % 2 == 1:
                # Running-bond stagger: shift interior shingles and pin both edges
                shifted = [y + step_y * 0.5 for y in y_positions[:-1]]
                y_positions = [ry_min + shingle_w * 0.5] + shifted + [ry_max - shingle_w * 0.5]
            
            for cur_y in y_positions:
                t_y = max(0.0, min(1.0, (cur_y - ry_min) / max(0.01, total_d)))
                
                # Exact matching sag and ridge height at this Y coordinate
                sag = math.sin(t_y * math.pi) * sway_amount if (roof_style == 'SWAY') else 0.0
                rz = z_base + roof_height - sag
                
                delta_z = rz - ez
                delta_x = half_w
                slope_len = math.sqrt(delta_x * delta_x + delta_z * delta_z)
                shingle_l = (slope_len / rows) * 1.35
                shingle_t = 0.035
                
                pitch_ang = math.atan2(delta_z, delta_x)
                norm_x = math.sin(pitch_ang)
                norm_z = math.cos(pitch_ang)
                
                # Position along the slope from eaves to ridge
                cur_z = ez + t * delta_z
                cur_x = cx + side * ((1.0 - t) * half_w)
                
                # Outward offset along local surface normal so shingles sit cleanly atop timber deck
                cur_x += side * (norm_x * 0.095)
                cur_z += norm_z * 0.095
                
                # Small whimsical jitter
                jitter_y = (rng.random() - 0.5) * 0.03
                jitter_tilt = (rng.random() - 0.5) * 0.03
                jitter_rot = (rng.random() - 0.5) * 0.04
                
                slope_angle = -pitch_ang if side < 0 else pitch_ang
                overlap_tilt = 0.05 * tilt_sign
                final_angle = slope_angle + overlap_tilt + jitter_tilt
                
                create_beveled_box(
                    bm,
                    size=(shingle_l, shingle_w, shingle_t),
                    location=(cur_x, cur_y + jitter_y, cur_z),
                    rotation=(0.0, final_angle, jitter_rot),
                    mat_index=MAT_INDEX_SHINGLES,
                    bevel_amount=0.006
                )

def build_dormer(bm, center_x, center_y, z_base, dormer_w=1.1, dormer_d=1.4, dormer_h=1.3):
    """
    Builds a dormer window structure projecting from the roof slope.
    """
    # Dormer body box
    create_box(
        bm,
        size=(dormer_w, dormer_d, dormer_h),
        location=(center_x, center_y, z_base + dormer_h * 0.5),
        mat_index=MAT_INDEX_TIMBER
    )
    # Dormer gable roof
    d_rx_min = center_x - dormer_w * 0.5 - 0.15
    d_rx_max = center_x + dormer_w * 0.5 + 0.15
    d_ry_min = center_y - dormer_d * 0.5 - 0.15
    d_ry_max = center_y + dormer_d * 0.5
    d_rz = z_base + dormer_h + 0.65
    
    # Mini gable slopes
    v_l0 = bm.verts.new(Vector((d_rx_min, d_ry_min, z_base + dormer_h)))
    v_l1 = bm.verts.new(Vector((d_rx_min, d_ry_max, z_base + dormer_h)))
    v_r1 = bm.verts.new(Vector((center_x, d_ry_max, d_rz)))
    v_r0 = bm.verts.new(Vector((center_x, d_ry_min, d_rz)))
    f_l = bm.faces.new([v_l0, v_l1, v_r1, v_r0])
    f_l.material_index = MAT_INDEX_SHINGLES
    
    v_rr0 = bm.verts.new(Vector((d_rx_max, d_ry_min, z_base + dormer_h)))
    v_rr1 = bm.verts.new(Vector((d_rx_max, d_ry_max, z_base + dormer_h)))
    f_r = bm.faces.new([v_r0, v_r1, v_rr1, v_rr0])
    f_r.material_index = MAT_INDEX_SHINGLES
    
    # Dormer window
    create_box(
        bm,
        size=(dormer_w * 0.7, 0.04, dormer_h * 0.6),
        location=(center_x, center_y - dormer_d * 0.5 - 0.02, z_base + dormer_h * 0.5),
        mat_index=MAT_INDEX_GLASS
    )

def build_fantasy_chimney(bm, pos_xy, z_start, total_height, width=0.85, depth=0.85, crooked_angle=0.0):
    """
    Builds a stylized fantasy stone chimney with tapered profile, stone cap, and smoke pot.
    """
    cx, cy = pos_xy
    
    # 1. Main stone chimney trunk
    create_beveled_box(
        bm,
        size=(width, depth, total_height),
        location=(cx, cy, z_start + total_height * 0.5),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.03
    )
    # 2. Projecting stone collar trim
    collar_z = z_start + total_height - 0.16
    create_beveled_box(
        bm,
        size=(width + 0.10, depth + 0.10, 0.12),
        location=(cx, cy, collar_z),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.02
    )
    # 3. Overhanging stone cap with subtle 2-degree tilt for organic handmade feel
    cap_z = z_start + total_height + 0.05
    create_beveled_box(
        bm,
        size=(width + 0.18, depth + 0.18, 0.12),
        location=(cx, cy, cap_z),
        rotation=(0.0, 0.025, 0.0),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.025
    )
    # 4. Terracotta/clay smoke pot on top, perfectly centered
    create_cone(
        bm,
        radius1=0.20,
        radius2=0.25,
        height=0.42,
        segments=8,
        location=(cx, cy, cap_z + 0.06 + 0.21),
        mat_index=MAT_INDEX_SHINGLES
    )

def build_hoist_beam(bm, front_x, front_y, z_ridge, length=1.4):
    """
    Builds an authentic fantasy warehouse roof hoist beam extending forward from
    the front gable peak, with a 45-degree timber support strut, wooden pulley block,
    hanging iron chain/rope, and a curved iron cargo hook.
    """
    beam_w = 0.22
    beam_h = 0.24
    half_l = length * 0.5
    
    # 1. Main projecting horizontal timber hoist beam (extends along -Y from front_y)
    beam_mid_y = front_y - half_l
    beam_mid_z = z_ridge + 0.04
    create_beveled_box(
        bm,
        size=(beam_w, length + 0.35, beam_h),
        location=(front_x, beam_mid_y + 0.15, beam_mid_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    
    # 2. Diagonal 45-degree heavy timber support strut underneath
    strut_len = math.sqrt(2.0) * 0.70
    strut_mid_y = front_y - 0.35
    strut_mid_z = z_ridge - 0.35
    create_box(
        bm,
        size=(0.14, 0.14, strut_len),
        location=(front_x, strut_mid_y, strut_mid_z),
        rotation=(-math.pi * 0.25, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )
    
    # 3. Wooden Pulley Block near outer end of beam
    pulley_y = front_y - length + 0.22
    pulley_z = beam_mid_z - beam_h * 0.5 - 0.10
    create_beveled_box(
        bm,
        size=(0.16, 0.18, 0.20),
        location=(front_x, pulley_y, pulley_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    # Pulley wheel iron axle hub
    create_cylinder(
        bm, radius=0.04, height=0.20, segments=8,
        location=(front_x, pulley_y, pulley_z),
        rotation=(0.0, math.pi * 0.5, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    
    # 4. Suspended Iron Rope / Chain
    chain_h = 0.85
    chain_mid_z = pulley_z - 0.10 - chain_h * 0.5
    create_cylinder(
        bm, radius=0.018, height=chain_h, segments=6,
        location=(front_x, pulley_y, chain_mid_z),
        mat_index=MAT_INDEX_IRON
    )
    
    # 5. Stylized Heavy Curved Iron Cargo Hook
    hook_z = chain_mid_z - chain_h * 0.5 - 0.06
    # Upper hook eye ring
    create_cylinder(
        bm, radius=0.05, height=0.035, segments=8,
        location=(front_x, pulley_y, hook_z),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    # Hook shank
    create_cylinder(
        bm, radius=0.024, height=0.18, segments=8,
        location=(front_x, pulley_y, hook_z - 0.09),
        mat_index=MAT_INDEX_IRON
    )
    # Curved hook bottom (beveled curved box)
    create_beveled_box(
        bm, size=(0.04, 0.14, 0.05),
        location=(front_x, pulley_y + 0.04, hook_z - 0.19),
        rotation=(math.pi * 0.15, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON,
        bevel_amount=0.012
    )
    # Hook tip pointing up
    create_beveled_box(
        bm, size=(0.035, 0.04, 0.09),
        location=(front_x, pulley_y + 0.09, hook_z - 0.15),
        mat_index=MAT_INDEX_IRON,
        bevel_amount=0.010
    )

