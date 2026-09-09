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
    MAT_INDEX_IRON, MAT_INDEX_WOOD
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

def build_curved_bargeboards(bm, cx, rx_min, rx_max, y_verge, ez, rz, roof_flare=0.35, segments=4):
    """
    Builds segmented curved bargeboards matching the bell-cast flare of the roof,
    complete with stylized upturned carved finial horns at the eave corners and an apex cap.
    """
    for side in [-1, 1]:
        rx_target = rx_min if side < 0 else rx_max
        for k in range(segments):
            u0 = k / segments
            u1 = (k + 1) / segments
            x0 = cx + side * u0 * abs(rx_target - cx)
            x1 = cx + side * u1 * abs(rx_target - cx)
            drop0 = (1.0 - roof_flare) * u0 + roof_flare * (1.0 - (1.0 - u0) ** 2)
            drop1 = (1.0 - roof_flare) * u1 + roof_flare * (1.0 - (1.0 - u1) ** 2)
            z0 = rz - drop0 * (rz - ez)
            z1 = rz - drop1 * (rz - ez)
            
            mid_x = (x0 + x1) * 0.5
            mid_z = (z0 + z1) * 0.5
            dx = x1 - x0
            dz = z1 - z0
            seg_len = math.sqrt(dx * dx + dz * dz) + 0.03
            seg_ang = math.atan2(dz, dx)
            create_beveled_box(
                bm,
                size=(seg_len, 0.10, 0.16),
                location=(mid_x, y_verge, mid_z),
                rotation=(0.0, -seg_ang, 0.0),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.012
            )
            
        # Upturned horn at eave tip
        horn_x = rx_target + side * 0.06
        horn_z = ez + 0.12
        horn_ang = -side * 0.65
        create_beveled_box(
            bm,
            size=(0.14, 0.11, 0.32),
            location=(horn_x, y_verge, horn_z),
            rotation=(0.0, horn_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.015
        )
        
    # Apex finial cap
    create_beveled_box(
        bm,
        size=(0.20, 0.12, 0.28),
        location=(cx, y_verge, rz + 0.10),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )

def build_sway_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=2.8, overhang=0.45,
                    sway_amount=0.25, segments_y=6, wall_thickness=0.28, gable_ends=('FRONT', 'BACK'),
                    abut_back=False, tier='TIER_3', plank_direction='HORIZONTAL', roof_flare=0.35):
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
    
    # 1. Solid Volumetric 3D Timber Roof Deck (Left and Right Slopes) with Bell-Cast Curvature
    segments_x = 4
    half_w = total_w * 0.5
    
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
        
        for side in [-1, 1]:
            for k in range(segments_x):
                u0 = k / segments_x
                u1 = (k + 1) / segments_x
                
                drop0 = (1.0 - roof_flare) * u0 + roof_flare * (1.0 - (1.0 - u0) ** 2)
                drop1 = (1.0 - roof_flare) * u1 + roof_flare * (1.0 - (1.0 - u1) ** 2)
                
                xa = cx + side * u0 * half_w
                xb = cx + side * u1 * half_w
                
                za0 = rz0 - drop0 * (rz0 - ez)
                za1 = rz1 - drop0 * (rz1 - ez)
                zb0 = rz0 - drop1 * (rz0 - ez)
                zb1 = rz1 - drop1 * (rz1 - ez)
                
                dx = xb - xa
                dz = ((zb0 + zb1) - (za0 + za1)) * 0.5
                inward = Vector((dz * side, 0.0, -abs(dx))).normalized() * deck_thick if (dx * dx + dz * dz) > 1e-6 else Vector((0, 0, -deck_thick))
                
                v_in0_t = bm.verts.new(Vector((xa, y0, za0)))
                v_in1_t = bm.verts.new(Vector((xa, y1, za1)))
                v_out1_t = bm.verts.new(Vector((xb, y1, zb1)))
                v_out0_t = bm.verts.new(Vector((xb, y0, zb0)))
                
                v_in0_b = bm.verts.new(Vector((xa, y0, za0)) + inward)
                v_in1_b = bm.verts.new(Vector((xa, y1, za1)) + inward)
                v_out1_b = bm.verts.new(Vector((xb, y1, zb1)) + inward)
                v_out0_b = bm.verts.new(Vector((xb, y0, zb0)) + inward)
                
                if side < 0:
                    f_top = bm.faces.new([v_out0_t, v_out1_t, v_in1_t, v_in0_t])
                    f_top.material_index = MAT_INDEX_SHINGLES
                    f_bot = bm.faces.new([v_in0_b, v_in1_b, v_out1_b, v_out0_b])
                    f_bot.material_index = MAT_INDEX_TIMBER
                    
                    if k == segments_x - 1:
                        f_eave = bm.faces.new([v_out0_t, v_out0_b, v_out1_b, v_out1_t])
                        f_eave.material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        f_f = bm.faces.new([v_in0_t, v_in0_b, v_out0_b, v_out0_t])
                        f_f.material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        f_r = bm.faces.new([v_out1_t, v_out1_b, v_in1_b, v_in1_t])
                        f_r.material_index = MAT_INDEX_TIMBER
                else:
                    f_top = bm.faces.new([v_in0_t, v_in1_t, v_out1_t, v_out0_t])
                    f_top.material_index = MAT_INDEX_SHINGLES
                    f_bot = bm.faces.new([v_out0_b, v_out1_b, v_in1_b, v_in0_b])
                    f_bot.material_index = MAT_INDEX_TIMBER
                    
                    if k == segments_x - 1:
                        f_eave = bm.faces.new([v_out1_t, v_out1_b, v_out0_b, v_out0_t])
                        f_eave.material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        f_f = bm.faces.new([v_out0_t, v_out0_b, v_in0_b, v_in0_t])
                        f_f.material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        f_r = bm.faces.new([v_in1_t, v_in1_b, v_out1_b, v_out1_t])
                        f_r.material_index = MAT_INDEX_TIMBER

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
        y_verge = ry_min + 0.04 if g_norm < 0 else ry_max - 0.04
        build_curved_bargeboards(bm, cx, rx_min, rx_max, y_verge, ez, rz, roof_flare=roof_flare)

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

def build_gable_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=3.0, overhang=0.45, wall_thickness=0.28, gable_ends=('FRONT', 'BACK'), segments_y=6, abut_back=False, tier='TIER_3', plank_direction='HORIZONTAL', roof_flare=0.35):
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
    total_w = rx_max - rx_min
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

    segments_x = 4
    half_w = total_w * 0.5
    
    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d

        for side in [-1, 1]:
            for k in range(segments_x):
                u0 = k / segments_x
                u1 = (k + 1) / segments_x
                
                drop0 = (1.0 - roof_flare) * u0 + roof_flare * (1.0 - (1.0 - u0) ** 2)
                drop1 = (1.0 - roof_flare) * u1 + roof_flare * (1.0 - (1.0 - u1) ** 2)
                
                xa = cx + side * u0 * half_w
                xb = cx + side * u1 * half_w
                
                za = rz - drop0 * (rz - ez)
                zb = rz - drop1 * (rz - ez)
                
                dx = xb - xa
                dz = zb - za
                inward = Vector((dz * side, 0.0, -abs(dx))).normalized() * deck_thick if (dx * dx + dz * dz) > 1e-6 else Vector((0, 0, -deck_thick))
                
                v_in0_t = bm.verts.new(Vector((xa, y0, za)))
                v_in1_t = bm.verts.new(Vector((xa, y1, za)))
                v_out1_t = bm.verts.new(Vector((xb, y1, zb)))
                v_out0_t = bm.verts.new(Vector((xb, y0, zb)))
                
                v_in0_b = bm.verts.new(Vector((xa, y0, za)) + inward)
                v_in1_b = bm.verts.new(Vector((xa, y1, za)) + inward)
                v_out1_b = bm.verts.new(Vector((xb, y1, zb)) + inward)
                v_out0_b = bm.verts.new(Vector((xb, y0, zb)) + inward)
                
                if side < 0:
                    f_top = bm.faces.new([v_out0_t, v_out1_t, v_in1_t, v_in0_t])
                    f_top.material_index = MAT_INDEX_SHINGLES
                    f_bot = bm.faces.new([v_in0_b, v_in1_b, v_out1_b, v_out0_b])
                    f_bot.material_index = MAT_INDEX_TIMBER
                    
                    if k == segments_x - 1:
                        f_eave = bm.faces.new([v_out0_t, v_out0_b, v_out1_b, v_out1_t])
                        f_eave.material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        f_f = bm.faces.new([v_in0_t, v_in0_b, v_out0_b, v_out0_t])
                        f_f.material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        f_r = bm.faces.new([v_out1_t, v_out1_b, v_in1_b, v_in1_t])
                        f_r.material_index = MAT_INDEX_TIMBER
                else:
                    f_top = bm.faces.new([v_in0_t, v_in1_t, v_out1_t, v_out0_t])
                    f_top.material_index = MAT_INDEX_SHINGLES
                    f_bot = bm.faces.new([v_out0_b, v_out1_b, v_in1_b, v_in0_b])
                    f_bot.material_index = MAT_INDEX_TIMBER
                    
                    if k == segments_x - 1:
                        f_eave = bm.faces.new([v_out1_t, v_out1_b, v_out0_b, v_out0_t])
                        f_eave.material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        f_f = bm.faces.new([v_out0_t, v_out0_b, v_in0_b, v_in0_t])
                        f_f.material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        f_r = bm.faces.new([v_in1_t, v_in1_b, v_out1_b, v_out1_t])
                        f_r.material_index = MAT_INDEX_TIMBER
    
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
        y_verge = ry_min + 0.04 if g_norm < 0 else ry_max - 0.04
        build_curved_bargeboards(bm, cx, rx_min, rx_max, y_verge, ez, rz, roof_flare=roof_flare)

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
                         abut_back=False, roof_flare=0.35):
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
                u = 1.0 - t
                drop_frac = (1.0 - roof_flare) * u + roof_flare * (1.0 - (1.0 - u) ** 2)
                cur_z = rz - drop_frac * delta_z
                cur_x = cx + side * (u * half_w)
                
                slope_mult = (1.0 - roof_flare) + roof_flare * 2.0 * (1.0 - u)
                pitch_ang = math.atan2(delta_z * slope_mult, delta_x)
                slope_len = math.sqrt(delta_x * delta_x + delta_z * delta_z)
                shingle_l = (slope_len / rows) * 1.35
                shingle_t = 0.035
                
                norm_x = math.sin(pitch_ang)
                norm_z = math.cos(pitch_ang)
                
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
    # Anchored against gable wall at front_y and angling up to support the beam outward
    strut_len = math.sqrt(2.0) * 0.65
    strut_mid_y = front_y - 0.32
    strut_mid_z = z_ridge - 0.32
    # Wall anchor corbel block
    create_beveled_box(
        bm,
        size=(0.20, 0.12, 0.22),
        location=(front_x, front_y + 0.02, z_ridge - 0.64),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    # 45-degree angled knee brace (sloping outward from wall up to hoist beam)
    create_box(
        bm,
        size=(0.14, 0.14, strut_len),
        location=(front_x, strut_mid_y, strut_mid_z),
        rotation=(math.pi * 0.25, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )
    
    # 3. Detailed Dual-Sheave Wooden Pulley Block near outer end of beam
    pulley_y = front_y - length + 0.22
    pulley_z = beam_mid_z - beam_h * 0.5 - 0.12
    # Wooden pulley casing shell
    create_beveled_box(
        bm,
        size=(0.18, 0.22, 0.24),
        location=(front_x, pulley_y, pulley_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.018
    )
    # Iron side reinforcing straps
    for sx_off in [-0.092, 0.092]:
        create_beveled_box(
            bm, size=(0.012, 0.08, 0.26),
            location=(front_x + sx_off, pulley_y, pulley_z),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.003
        )
    # Pulley axle hub pin
    create_cylinder(
        bm, radius=0.035, height=0.22, segments=8,
        location=(front_x, pulley_y, pulley_z),
        rotation=(0.0, math.pi * 0.5, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    # Top iron mounting shackle connecting to beam
    create_beveled_box(
        bm, size=(0.08, 0.04, 0.12),
        location=(front_x, pulley_y, pulley_z + 0.14),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )
    
    # 4. Suspended Heavy Cable / Chain
    chain_h = 0.85
    chain_mid_z = pulley_z - 0.12 - chain_h * 0.5
    create_cylinder(
        bm, radius=0.020, height=chain_h, segments=8,
        location=(front_x, pulley_y, chain_mid_z),
        mat_index=MAT_INDEX_IRON
    )
    
    # 5. Authentically Forged Curved J-Hook (functional heavy cargo lifting hook)
    hook_top_z = chain_mid_z - chain_h * 0.5 - 0.04
    
    # Swivel eyelet ring
    create_cylinder(
        bm, radius=0.048, height=0.026, segments=12,
        location=(front_x, pulley_y, hook_top_z),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    # Thick vertical shank
    shank_h = 0.16
    create_cylinder(
        bm, radius=0.032, height=shank_h, segments=8,
        location=(front_x, pulley_y, hook_top_z - shank_h * 0.5),
        mat_index=MAT_INDEX_IRON
    )
    
    # Continuous curved hook throat/belly (smooth 180-degree circular arc)
    throat_radius = 0.105
    center_y = pulley_y + throat_radius
    center_z = hook_top_z - shank_h
    
    arc_segs = 12
    prev_ring = None
    for step in range(arc_segs + 1):
        t = step / float(arc_segs)
        phi = -math.pi + t * math.pi # runs from -180 deg (straight down) to 0 deg (pointing up)
        
        # Cross section center along the throat arc
        cy = center_y + throat_radius * math.cos(phi)
        cz = center_z + throat_radius * math.sin(phi)
        
        # Taper radius: thick at belly (t=0.3 to 0.6), tapered towards the tip (t=1.0)
        ring_r = 0.034 * (1.0 - t * 0.40)
        
        # Local tangent along arc in YZ plane
        normal_y = -math.cos(phi)
        normal_z = -math.sin(phi)
        
        # Construct 6-sided cross section ring
        cur_ring = []
        for v_i in range(6):
            v_ang = (2.0 * math.pi * v_i) / 6.0
            vx = front_x + ring_r * math.cos(v_ang)
            vy = cy + (ring_r * math.sin(v_ang)) * normal_y
            vz = cz + (ring_r * math.sin(v_ang)) * normal_z
            cur_ring.append(bm.verts.new((vx, vy, vz)))
            
        if prev_ring is not None:
            for v_i in range(6):
                nxt = (v_i + 1) % 6
                f_hook = bm.faces.new([prev_ring[v_i], prev_ring[nxt], cur_ring[nxt], cur_ring[v_i]])
                f_hook.material_index = MAT_INDEX_IRON
                f_hook.smooth = True
        prev_ring = cur_ring
        
    # Tapered pointed hook barb / tip
    barb_tip_y = center_y + throat_radius + 0.018
    barb_tip_z = center_z + 0.12
    v_tip = bm.verts.new((front_x, barb_tip_y, barb_tip_z))
    for v_i in range(6):
        nxt = (v_i + 1) % 6
        f_tip = bm.faces.new([prev_ring[v_i], prev_ring[nxt], v_tip])
        f_tip.material_index = MAT_INDEX_IRON
        f_tip.smooth = True

