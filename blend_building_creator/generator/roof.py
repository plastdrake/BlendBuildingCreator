"""
Stylized Fantasy Roof Generator: curved saddle/sway roofs, steep medieval gables,
conical turrets, layered shingles, dormer windows, and crooked stone chimneys.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cone, create_cylinder
from .materials import MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER, MAT_INDEX_STONE, MAT_INDEX_GLASS

def build_sway_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=2.8, overhang=0.45,
                    sway_amount=0.25, segments_y=6, wall_thickness=0.28):
    """
    Builds a whimsical fairytale curved/saddle roof with flared eaves, saggy ridge,
    solid 0.12m thick timber roof decking, thick volumetric gable walls, and full eave closures.
    """
    total_w = (x_max - x_min) + overhang * 2.0
    total_d = (y_max - y_min) + overhang * 2.0
    
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max + overhang
    
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
        vr0_t = bm.verts.new(Vector((cx, y0, rz0)))
        vr1_t = bm.verts.new(Vector((cx, y1, rz1)))
        
        vl0_b = bm.verts.new(Vector((rx_min, y0, ez)) + inward_l)
        vl1_b = bm.verts.new(Vector((rx_min, y1, ez)) + inward_l)
        vr0_b = bm.verts.new(Vector((cx, y0, rz0)) + inward_l)
        vr1_b = bm.verts.new(Vector((cx, y1, rz1)) + inward_l)
        
        # Top face (timber decking)
        f_lt = bm.faces.new([vl0_t, vl1_t, vr1_t, vr0_t])
        f_lt.material_index = MAT_INDEX_TIMBER
        # Bottom face (interior ceiling)
        f_lb = bm.faces.new([vr0_b, vr1_b, vl1_b, vl0_b])
        f_lb.material_index = MAT_INDEX_TIMBER
        # Outer eave face
        f_le = bm.faces.new([vl0_t, vl0_b, vl1_b, vl1_t])
        f_le.material_index = MAT_INDEX_TIMBER
        # Front rake edge
        if j == 0:
            f_lf = bm.faces.new([vr0_t, vr0_b, vl0_b, vl0_t])
            f_lf.material_index = MAT_INDEX_TIMBER
        # Back rake edge
        if j == segments_y - 1:
            f_lr = bm.faces.new([vl1_t, vl1_b, vr1_b, vr1_t])
            f_lr.material_index = MAT_INDEX_TIMBER

        # --- Right Slope Solid Slab ---
        s_right = Vector((rx_max - cx, 0.0, ez - (rz0 + rz1) * 0.5))
        inward_r = Vector((-s_right.z, 0.0, s_right.x)).normalized() * deck_thick
        
        vrr0_t = bm.verts.new(Vector((rx_max, y0, ez)))
        vrr1_t = bm.verts.new(Vector((rx_max, y1, ez)))
        
        vrr0_b = bm.verts.new(Vector((rx_max, y0, ez)) + inward_r)
        vrr1_b = bm.verts.new(Vector((rx_max, y1, ez)) + inward_r)
        vr0_rb = bm.verts.new(Vector((cx, y0, rz0)) + inward_r)
        vr1_rb = bm.verts.new(Vector((cx, y1, rz1)) + inward_r)
        
        # Top face
        f_rt = bm.faces.new([vr0_t, vr1_t, vrr1_t, vrr0_t])
        f_rt.material_index = MAT_INDEX_TIMBER
        # Bottom face
        f_rb = bm.faces.new([vrr0_b, vrr1_b, vr1_rb, vr0_rb])
        f_rb.material_index = MAT_INDEX_TIMBER
        # Outer eave face
        f_re = bm.faces.new([vrr1_t, vrr1_b, vrr0_b, vrr0_t])
        f_re.material_index = MAT_INDEX_TIMBER
        # Front rake edge
        if j == 0:
            f_rf = bm.faces.new([vrr0_t, vrr0_b, vr0_rb, vr0_t])
            f_rf.material_index = MAT_INDEX_TIMBER
        # Back rake edge
        if j == segments_y - 1:
            f_rr = bm.faces.new([vr1_t, vr1_rb, vrr1_b, vrr1_t])
            f_rr.material_index = MAT_INDEX_TIMBER

    # 2. Thick Volumetric Gable End Walls (sealing front and back triangular gaps)
    half_wt = wall_thickness * 0.5
    for gy, g_norm in [(y_min, -1), (y_max, 1)]:
        y_ext = gy + g_norm * half_wt
        y_int = gy - g_norm * half_wt
        
        # Front & Back triangular prism vertices
        v_ext_l = bm.verts.new(Vector((x_min - 0.04, y_ext, z_base)))
        v_ext_r = bm.verts.new(Vector((x_max + 0.04, y_ext, z_base)))
        v_ext_t = bm.verts.new(Vector((cx, y_ext, z_base + roof_height)))
        
        v_int_l = bm.verts.new(Vector((x_min - 0.04, y_int, z_base)))
        v_int_r = bm.verts.new(Vector((x_max + 0.04, y_int, z_base)))
        v_int_t = bm.verts.new(Vector((cx, y_int, z_base + roof_height)))
        
        if g_norm < 0:
            f_ext = bm.faces.new([v_ext_l, v_ext_r, v_ext_t])
            f_int = bm.faces.new([v_int_r, v_int_l, v_int_t])
        else:
            f_ext = bm.faces.new([v_ext_r, v_ext_l, v_ext_t])
            f_int = bm.faces.new([v_int_l, v_int_r, v_int_t])
            
        f_ext.material_index = MAT_INDEX_TIMBER
        f_int.material_index = MAT_INDEX_TIMBER
        
        # Sloping roof-wall seals
        f_g_left = bm.faces.new([v_ext_l, v_ext_t, v_int_t, v_int_l])
        f_g_left.material_index = MAT_INDEX_TIMBER
        f_g_right = bm.faces.new([v_ext_t, v_ext_r, v_int_r, v_int_t])
        f_g_right.material_index = MAT_INDEX_TIMBER
        
        # Chunky Verge Bargeboards along gable rafter slopes
        barge_w = 0.12
        barge_d = 0.16
        b_len = math.sqrt((cx - rx_min)**2 + roof_height**2)
        b_ang = math.atan2(roof_height, cx - rx_min)
        
        # Left rafter beam
        b_mid_l = Vector(((rx_min + cx) * 0.5, gy + g_norm * (half_wt + 0.06), z_base + roof_height * 0.5))
        create_box(bm, size=(b_len, barge_d, barge_w), location=b_mid_l, rotation=(0.0, -b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)
        # Right rafter beam
        b_mid_r = Vector(((rx_max + cx) * 0.5, gy + g_norm * (half_wt + 0.06), z_base + roof_height * 0.5))
        create_box(bm, size=(b_len, barge_d, barge_w), location=b_mid_r, rotation=(0.0, b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)

    # 3. Eaves Wall Plate & Frieze Closures (sealing gap between side walls and roof deck)
    side_span_y = (y_max - y_min) + 0.10
    create_box(
        bm,
        size=(wall_thickness + 0.06, side_span_y, 0.32),
        location=(x_min, (y_min + y_max) * 0.5, z_base + 0.12),
        mat_index=MAT_INDEX_TIMBER
    )
    create_box(
        bm,
        size=(wall_thickness + 0.06, side_span_y, 0.32),
        location=(x_max, (y_min + y_max) * 0.5, z_base + 0.12),
        mat_index=MAT_INDEX_TIMBER
    )

    # 4. Heavy Eaves Fascia & Ridge Beams
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.18),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.18),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.20, total_d + 0.25, 0.22),
        location=(cx, (ry_min + ry_max) * 0.5, z_base + roof_height - sway_amount * 0.5 + 0.05),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )

def build_gable_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=3.0, overhang=0.45, wall_thickness=0.28):
    """
    Builds a classic steep medieval gable roof with solid 0.12m thick timber decking,
    thick volumetric gable walls, and complete eave closures.
    """
    total_d = (y_max - y_min) + overhang * 2.0
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max + overhang
    
    cx = (x_min + x_max) * 0.5
    rz = z_base + roof_height
    ez = z_base - 0.10
    deck_thick = 0.12
    
    # 1. Solid Volumetric 3D Timber Roof Deck (Left and Right Slopes)
    s_left = Vector((cx - rx_min, 0.0, rz - ez))
    inward_l = Vector((s_left.z, 0.0, -s_left.x)).normalized() * deck_thick
    
    vl0_t = bm.verts.new(Vector((rx_min, ry_min, ez)))
    vl1_t = bm.verts.new(Vector((rx_min, ry_max, ez)))
    vr1_t = bm.verts.new(Vector((cx, ry_max, rz)))
    vr0_t = bm.verts.new(Vector((cx, ry_min, rz)))
    
    vl0_b = bm.verts.new(Vector((rx_min, ry_min, ez)) + inward_l)
    vl1_b = bm.verts.new(Vector((rx_min, ry_max, ez)) + inward_l)
    vr1_b = bm.verts.new(Vector((cx, ry_max, rz)) + inward_l)
    vr0_b = bm.verts.new(Vector((cx, ry_min, rz)) + inward_l)
    
    # Top, bottom, and side faces of left deck
    bm.faces.new([vl0_t, vl1_t, vr1_t, vr0_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vr0_b, vr1_b, vl1_b, vl0_b]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vl0_t, vl0_b, vl1_b, vl1_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vr0_t, vr0_b, vl0_b, vl0_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vl1_t, vl1_b, vr1_b, vr1_t]).material_index = MAT_INDEX_TIMBER
    
    # Right Slope
    s_right = Vector((rx_max - cx, 0.0, ez - rz))
    inward_r = Vector((-s_right.z, 0.0, s_right.x)).normalized() * deck_thick
    
    vrr0_t = bm.verts.new(Vector((rx_max, ry_min, ez)))
    vrr1_t = bm.verts.new(Vector((rx_max, ry_max, ez)))
    
    vrr0_b = bm.verts.new(Vector((rx_max, ry_min, ez)) + inward_r)
    vrr1_b = bm.verts.new(Vector((rx_max, ry_max, ez)) + inward_r)
    vr1_rb = bm.verts.new(Vector((cx, ry_max, rz)) + inward_r)
    vr0_rb = bm.verts.new(Vector((cx, ry_min, rz)) + inward_r)
    
    bm.faces.new([vr0_t, vr1_t, vrr1_t, vrr0_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vrr0_b, vrr1_b, vr1_rb, vr0_rb]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vrr1_t, vrr1_b, vrr0_b, vrr0_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vrr0_t, vrr0_b, vr0_rb, vr0_t]).material_index = MAT_INDEX_TIMBER
    bm.faces.new([vr1_t, vr1_rb, vrr1_b, vrr1_t]).material_index = MAT_INDEX_TIMBER
    
    # 2. Thick Volumetric Gable End Walls
    half_wt = wall_thickness * 0.5
    for gy, g_norm in [(y_min, -1), (y_max, 1)]:
        y_ext = gy + g_norm * half_wt
        y_int = gy - g_norm * half_wt
        
        v_ext_l = bm.verts.new(Vector((x_min - 0.04, y_ext, z_base)))
        v_ext_r = bm.verts.new(Vector((x_max + 0.04, y_ext, z_base)))
        v_ext_t = bm.verts.new(Vector((cx, y_ext, rz)))
        
        v_int_l = bm.verts.new(Vector((x_min - 0.04, y_int, z_base)))
        v_int_r = bm.verts.new(Vector((x_max + 0.04, y_int, z_base)))
        v_int_t = bm.verts.new(Vector((cx, y_int, rz)))
        
        if g_norm < 0:
            bm.faces.new([v_ext_l, v_ext_r, v_ext_t]).material_index = MAT_INDEX_TIMBER
            bm.faces.new([v_int_r, v_int_l, v_int_t]).material_index = MAT_INDEX_TIMBER
        else:
            bm.faces.new([v_ext_r, v_ext_l, v_ext_t]).material_index = MAT_INDEX_TIMBER
            bm.faces.new([v_int_l, v_int_r, v_int_t]).material_index = MAT_INDEX_TIMBER
            
        bm.faces.new([v_ext_l, v_ext_t, v_int_t, v_int_l]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_t, v_ext_r, v_int_r, v_int_t]).material_index = MAT_INDEX_TIMBER
        
        # Verge Bargeboards along gable rafter slopes
        b_len = math.sqrt((cx - rx_min)**2 + roof_height**2)
        b_ang = math.atan2(roof_height, cx - rx_min)
        
        b_mid_l = Vector(((rx_min + cx) * 0.5, gy + g_norm * (half_wt + 0.06), z_base + roof_height * 0.5))
        create_box(bm, size=(b_len, 0.16, 0.12), location=b_mid_l, rotation=(0.0, -b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)
        b_mid_r = Vector(((rx_max + cx) * 0.5, gy + g_norm * (half_wt + 0.06), z_base + roof_height * 0.5))
        create_box(bm, size=(b_len, 0.16, 0.12), location=b_mid_r, rotation=(0.0, b_ang, 0.0), mat_index=MAT_INDEX_TIMBER)

    # 3. Eaves Wall Plate & Frieze Closures
    side_span_y = (y_max - y_min) + 0.10
    create_box(
        bm,
        size=(wall_thickness + 0.06, side_span_y, 0.32),
        location=(x_min, (y_min + y_max) * 0.5, z_base + 0.12),
        mat_index=MAT_INDEX_TIMBER
    )
    create_box(
        bm,
        size=(wall_thickness + 0.06, side_span_y, 0.32),
        location=(x_max, (y_min + y_max) * 0.5, z_base + 0.12),
        mat_index=MAT_INDEX_TIMBER
    )

    # 4. Eaves Fascia & Ridge Beams
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.18),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.18),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.22, total_d + 0.20, 0.22),
        location=(cx, (ry_min + ry_max) * 0.5, rz + 0.05),
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
                         rows=6, seed=42):
    """
    Generates chunky stylized overlapping shingle rows with whimsical rotation jitter.
    Correctly aligns shingles flat against roof slope with proper outward normal.
    """
    rng = random.Random(seed)
    cx = (x_min + x_max) * 0.5
    half_w = (x_max - x_min) * 0.5 + 0.35
    total_d = (y_max - y_min) + 0.7
    
    slope_len = math.sqrt(half_w * half_w + roof_height * roof_height)
    pitch_ang = math.atan2(roof_height, half_w)
    
    # Shingle dimensions: width along Y, length along slope, thickness along normal
    shingle_w = 0.44
    shingle_l = (slope_len / rows) * 1.35  # Overlap between rows
    shingle_t = 0.035
    
    cols = max(3, int(total_d / (shingle_w * 0.82)))
    step_y = total_d / cols
    
    # Outward normal components
    norm_x = math.sin(pitch_ang)
    norm_z = math.cos(pitch_ang)
    
    for side in [-1, 1]:
        # Left slope (side == -1): normal points -X and +Z; rotation around Y is -pitch_ang
        # Right slope (side == 1): normal points +X and +Z; rotation around Y is +pitch_ang
        slope_angle = -pitch_ang if side < 0 else pitch_ang
        tilt_sign = 1 if side < 0 else -1
        
        for r in range(rows):
            # Fraction up the slope (from eaves to ridge)
            t = (r + 0.3) / rows
            
            # Position along the slope
            cur_z = z_base + t * roof_height
            cur_x = cx + side * ((1.0 - t) * half_w)
            
            # Slight outward offset along slope normal so shingles rest on roof
            cur_x += side * (norm_x * 0.035)
            cur_z += norm_z * 0.035
            
            # Staggered alternating brick pattern
            offset_y = (step_y * 0.5) if (r % 2 == 1) else 0.0
            
            for c in range(cols):
                cur_y = (y_min - 0.35) + (c + 0.5) * step_y + offset_y
                
                # Small stylized whimsical jitter
                jitter_y = (rng.random() - 0.5) * 0.04
                jitter_tilt = (rng.random() - 0.5) * 0.04
                jitter_rot = (rng.random() - 0.5) * 0.05
                
                # Slight overlap pitch (shingle tilts downward slightly over row below)
                overlap_tilt = 0.06 * tilt_sign
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
