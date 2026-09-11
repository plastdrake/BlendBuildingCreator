"""
Classic Medieval Gable Roof Generator with flared eaves and segmented ridge.
Follows Single Responsibility, Open/Closed, and DRY principles.
"""

import math
from mathutils import Vector
from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER
from .gable_wall import build_gable_end_wall
from .features import build_curved_bargeboards

def build_gable_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=3.0, overhang=0.45,
                     wall_thickness=0.28, gable_ends=('FRONT', 'BACK'), segments_y=6, abut_back=False,
                     tier='TIER_3', plank_direction='HORIZONTAL', roof_flare=0.35, dormer_apertures=None):
    """
    Builds a classic steep medieval gable roof with solid 0.16m thick timber decking,
    thick volumetric gable walls, and complete eave closures.
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
    deck_thick = 0.16
    uv_layer = bm.loops.layers.uv.verify()
    
    segments_x = 4
    half_w = total_w * 0.5
    
    # 1. Solid Volumetric 3D Timber Roof Deck (Segmented along Y)
    for side in [-1, 1]:
        grid_top = []
        grid_bot = []
        
        for k in range(segments_x + 1):
            u = k / segments_x
            drop = (1.0 - roof_flare) * u + roof_flare * (1.0 - (1.0 - u) ** 2)
            x_val = cx + side * u * half_w
            
            row_top = []
            row_bot = []
            for j in range(segments_y + 1):
                t_y = j / segments_y
                y_val = ry_min + t_y * total_d
                z_val = rz - drop * (rz - ez)
                
                d_drop = (1.0 - roof_flare) + 2.0 * roof_flare * (1.0 - u)
                dz_du = -d_drop * (rz - ez)
                dx_du = side * half_w
                inward = Vector((dz_du * side, 0.0, -abs(dx_du))).normalized() * deck_thick if (dx_du**2 + dz_du**2) > 1e-6 else Vector((0, 0, -deck_thick))
                
                row_top.append(bm.verts.new(Vector((x_val, y_val, z_val))))
                row_bot.append(bm.verts.new(Vector((x_val, y_val, z_val)) + inward))
            grid_top.append(row_top)
            grid_bot.append(row_bot)
            
        for k in range(segments_x):
            for j in range(segments_y):
                u0 = k / segments_x
                u1 = (k + 1) / segments_x
                t0 = j / segments_y
                t1 = (j + 1) / segments_y
                y0 = ry_min + t0 * total_d
                y1 = ry_min + t1 * total_d
                
                if dormer_apertures:
                    mid_y = (y0 + y1) * 0.5
                    mid_u = (u0 + u1) * 0.5
                    skip_cell = False
                    for ap in dormer_apertures:
                        if ap.get('side') == side:
                            if ap['y_min'] <= mid_y <= ap['y_max'] and ap['u_min'] <= mid_u <= ap['u_max']:
                                skip_cell = True
                                break
                    if skip_cell:
                        continue
                
                v_in0_t = grid_top[k][j]
                v_in1_t = grid_top[k][j+1]
                v_out1_t = grid_top[k+1][j+1]
                v_out0_t = grid_top[k+1][j]
                
                v_in0_b = grid_bot[k][j]
                v_in1_b = grid_bot[k][j+1]
                v_out1_b = grid_bot[k+1][j+1]
                v_out0_b = grid_bot[k+1][j]
                
                if side < 0:
                    f_top = bm.faces.new([v_out0_t, v_out1_t, v_in1_t, v_in0_t])
                    f_bot = bm.faces.new([v_in0_b, v_in1_b, v_out1_b, v_out0_b])
                    if k == segments_x - 1:
                        bm.faces.new([v_out0_t, v_out0_b, v_out1_b, v_out1_t]).material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        bm.faces.new([v_in0_t, v_in0_b, v_out0_b, v_out0_t]).material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        bm.faces.new([v_out1_t, v_out1_b, v_in1_b, v_in1_t]).material_index = MAT_INDEX_TIMBER
                else:
                    f_top = bm.faces.new([v_in0_t, v_in1_t, v_out1_t, v_out0_t])
                    f_bot = bm.faces.new([v_out0_b, v_out1_b, v_in1_b, v_in0_b])
                    if k == segments_x - 1:
                        bm.faces.new([v_out1_t, v_out1_b, v_out0_b, v_out0_t]).material_index = MAT_INDEX_TIMBER
                    if j == 0:
                        bm.faces.new([v_out0_t, v_out0_b, v_in0_b, v_in0_t]).material_index = MAT_INDEX_TIMBER
                    if j == segments_y - 1:
                        bm.faces.new([v_in1_t, v_in1_b, v_out1_b, v_out1_t]).material_index = MAT_INDEX_TIMBER
                        
                f_top.material_index = MAT_INDEX_SHINGLES
                f_bot.material_index = MAT_INDEX_TIMBER
                for loop in f_top.loops:
                    co = loop.vert.co
                    u_uv = (co.y - ry_min) * 0.32
                    s_dist = math.sqrt((co.x - cx) ** 2 + (rz - co.z) ** 2)
                    v_uv = -s_dist * 0.32
                    loop[uv_layer].uv = Vector((u_uv, v_uv))
    
    # 2. Volumetric Gable End Walls
    half_wt = wall_thickness * 0.5
    
    def get_gable_deck_z(px):
        u = min(1.0, max(0.0, abs(px - cx) / max(0.001, half_w)))
        d = (1.0 - roof_flare) * u + roof_flare * (1.0 - (1.0 - u) ** 2)
        return (rz - d * (rz - ez)) - deck_thick - 0.02

    gable_configs = []
    if 'FRONT' in gable_ends:
        gable_configs.append((y_min, -1))
    if 'BACK' in gable_ends:
        gable_configs.append((y_max, 1))

    for gy, g_norm in gable_configs:
        build_gable_end_wall(
            bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
            deck_thick, z_base, roof_height, roof_flare, tier, plank_direction,
            get_gable_deck_z, ez, rz
        )
        # Verge Bargeboards along gable rafter slopes
        y_verge = ry_min + 0.04 if g_norm < 0 else ry_max - 0.04
        build_curved_bargeboards(bm, cx, rx_min, rx_max, y_verge, ez, rz, roof_flare=roof_flare)

    # 3. Eaves Fascia & Ridge Beams
    y_f_start = ry_min + 0.06
    y_f_end = (ry_max - 0.06) if not abut_back else ry_max
    fascia_d = max(0.2, y_f_end - y_f_start)
    fascia_mid_y = (y_f_start + y_f_end) * 0.5
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_min, fascia_mid_y, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, fascia_d, 0.18),
        location=(rx_max, fascia_mid_y, ez),
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
