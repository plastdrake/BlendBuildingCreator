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
                    sway_amount=0.25, segments_y=6):
    """
    Builds a whimsical fairytale curved/saddle roof with flared eaves and saggy ridge.
    """
    total_w = (x_max - x_min) + overhang * 2.0
    total_d = (y_max - y_min) + overhang * 2.0
    
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max + overhang
    
    cx = (rx_min + rx_max) * 0.5
    half_w = total_w * 0.5
    
    # Generate profile along Y with parabolic sag
    # Ridge beam at cx
    for j in range(segments_y):
        t0 = j / segments_y
        t1 = (j + 1) / segments_y
        
        y0 = ry_min + t0 * total_d
        y1 = ry_min + t1 * total_d
        
        # Parabolic sag: highest at ends, dipped in center
        sag0 = math.sin(t0 * math.pi) * sway_amount
        sag1 = math.sin(t1 * math.pi) * sway_amount
        
        rz0 = z_base + roof_height - sag0
        rz1 = z_base + roof_height - sag1
        
        ez = z_base - 0.15 # Eaves level
        
        # Left slope panel (exterior surface)
        v_l0 = bm.verts.new(Vector((rx_min, y0, ez)))
        v_l1 = bm.verts.new(Vector((rx_min, y1, ez)))
        v_r0 = bm.verts.new(Vector((cx, y0, rz0)))
        v_r1 = bm.verts.new(Vector((cx, y1, rz1)))
        
        f_left = bm.faces.new([v_l0, v_l1, v_r1, v_r0])
        f_left.material_index = MAT_INDEX_SHINGLES
        
        # Left slope inner ceiling (solid wood deck seen from inside attic)
        v_il0 = bm.verts.new(Vector((rx_min, y0, ez - 0.07)))
        v_il1 = bm.verts.new(Vector((rx_min, y1, ez - 0.07)))
        v_ir0 = bm.verts.new(Vector((cx, y0, rz0 - 0.07)))
        v_ir1 = bm.verts.new(Vector((cx, y1, rz1 - 0.07)))
        f_ileft = bm.faces.new([v_ir0, v_ir1, v_il1, v_il0])
        f_ileft.material_index = MAT_INDEX_TIMBER

        # Right slope panel (exterior surface)
        v_rr0 = bm.verts.new(Vector((rx_max, y0, ez)))
        v_rr1 = bm.verts.new(Vector((rx_max, y1, ez)))
        
        f_right = bm.faces.new([v_r0, v_r1, v_rr1, v_rr0])
        f_right.material_index = MAT_INDEX_SHINGLES

        # Right slope inner ceiling (solid wood deck seen from inside attic)
        v_irr0 = bm.verts.new(Vector((rx_max, y0, ez - 0.07)))
        v_irr1 = bm.verts.new(Vector((rx_max, y1, ez - 0.07)))
        f_iright = bm.faces.new([v_irr0, v_irr1, v_ir1, v_ir0])
        f_iright.material_index = MAT_INDEX_TIMBER
        
    # Front and back gable triangular end walls (double-sided / thick timber)
    # Front gable
    v_fl = bm.verts.new(Vector((x_min, y_min, z_base)))
    v_fr = bm.verts.new(Vector((x_max, y_min, z_base)))
    v_ft = bm.verts.new(Vector((cx, y_min, z_base + roof_height)))
    f_front = bm.faces.new([v_fl, v_fr, v_ft])
    f_front.material_index = MAT_INDEX_TIMBER
    
    # Back gable
    v_bl = bm.verts.new(Vector((x_min, y_max, z_base)))
    v_br = bm.verts.new(Vector((x_max, y_max, z_base)))
    v_bt = bm.verts.new(Vector((cx, y_max, z_base + roof_height)))
    f_back = bm.faces.new([v_br, v_bl, v_bt])
    f_back.material_index = MAT_INDEX_TIMBER
    
    # Eaves fascia beams (left and right lower edges)
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.16),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.16),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )

    # Heavy stylized ridge beam
    create_beveled_box(
        bm,
        size=(0.20, total_d + 0.25, 0.22),
        location=(cx, (ry_min + ry_max) * 0.5, z_base + roof_height - sway_amount * 0.5 + 0.05),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )

def build_gable_roof(bm, x_min, x_max, y_min, y_max, z_base, roof_height=3.0, overhang=0.45):
    """
    Builds a classic steep medieval gable roof with timber trims.
    """
    total_d = (y_max - y_min) + overhang * 2.0
    rx_min = x_min - overhang
    rx_max = x_max + overhang
    ry_min = y_min - overhang
    ry_max = y_max + overhang
    
    cx = (x_min + x_max) * 0.5
    rz = z_base + roof_height
    ez = z_base - 0.10
    
    # Left slope (exterior)
    v_l0 = bm.verts.new(Vector((rx_min, ry_min, ez)))
    v_l1 = bm.verts.new(Vector((rx_min, ry_max, ez)))
    v_r1 = bm.verts.new(Vector((cx, ry_max, rz)))
    v_r0 = bm.verts.new(Vector((cx, ry_min, rz)))
    f_left = bm.faces.new([v_l0, v_l1, v_r1, v_r0])
    f_left.material_index = MAT_INDEX_SHINGLES

    # Left inner ceiling (solid wood deck)
    v_il0 = bm.verts.new(Vector((rx_min, ry_min, ez - 0.07)))
    v_il1 = bm.verts.new(Vector((rx_min, ry_max, ez - 0.07)))
    v_ir1 = bm.verts.new(Vector((cx, ry_max, rz - 0.07)))
    v_ir0 = bm.verts.new(Vector((cx, ry_min, rz - 0.07)))
    f_ileft = bm.faces.new([v_ir0, v_ir1, v_il1, v_il0])
    f_ileft.material_index = MAT_INDEX_TIMBER
    
    # Right slope (exterior)
    v_rr0 = bm.verts.new(Vector((rx_max, ry_min, ez)))
    v_rr1 = bm.verts.new(Vector((rx_max, ry_max, ez)))
    f_right = bm.faces.new([v_r0, v_r1, v_rr1, v_rr0])
    f_right.material_index = MAT_INDEX_SHINGLES

    # Right inner ceiling (solid wood deck)
    v_irr0 = bm.verts.new(Vector((rx_max, ry_min, ez - 0.07)))
    v_irr1 = bm.verts.new(Vector((rx_max, ry_max, ez - 0.07)))
    f_iright = bm.faces.new([v_irr0, v_irr1, v_ir1, v_ir0])
    f_iright.material_index = MAT_INDEX_TIMBER
    
    # Front gable
    v_fl = bm.verts.new(Vector((x_min, y_min, z_base)))
    v_fr = bm.verts.new(Vector((x_max, y_min, z_base)))
    v_ft = bm.verts.new(Vector((cx, y_min, rz)))
    f_front = bm.faces.new([v_fl, v_fr, v_ft])
    f_front.material_index = MAT_INDEX_TIMBER
    
    # Back gable
    v_bl = bm.verts.new(Vector((x_min, y_max, z_base)))
    v_br = bm.verts.new(Vector((x_max, y_max, z_base)))
    v_bt = bm.verts.new(Vector((cx, y_max, rz)))
    f_back = bm.faces.new([v_br, v_bl, v_bt])
    f_back.material_index = MAT_INDEX_TIMBER

    # Eaves fascia beams
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.16),
        location=(rx_min, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    create_beveled_box(
        bm,
        size=(0.14, total_d + 0.15, 0.16),
        location=(rx_max, (ry_min + ry_max) * 0.5, ez),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )
    
    # Ridge beam
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
