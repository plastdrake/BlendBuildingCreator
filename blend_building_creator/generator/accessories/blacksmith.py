import math
from mathutils import Vector
from ..uv_utils import apply_roof_shingle_uvs
from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_SHINGLES
)

def build_blacksmith_forge(bm, x_min, x_max, y_min, y_max, z_ground, wall_thickness, seed=42):
    wall_x = x_max
    canopy_w = 2.6
    canopy_d = (y_max - y_min) * 0.75
    canopy_h = 2.45
    canopy_cy = (y_min + y_max) * 0.5
    outer_x = wall_x + canopy_w
    
    deck_thick = 0.12
    create_beveled_box(
        bm, size=(canopy_w + 0.15, canopy_d + 0.20, deck_thick),
        location=(wall_x + canopy_w * 0.5, canopy_cy, z_ground + deck_thick * 0.5),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )
    
    col_w = 0.18
    p1_y = canopy_cy - canopy_d * 0.44
    p2_y = canopy_cy + canopy_d * 0.44
    post_x = outer_x - col_w * 0.5
    pillar_h = canopy_h - 0.20
    
    # Vertical posts and knee braces
    for py in (p1_y, p2_y):
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.20),
            location=(post_x, py, z_ground + 0.10),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(col_w, col_w, pillar_h),
            location=(post_x, py, z_ground + 0.20 + pillar_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        sgn = 1.0 if py < canopy_cy else -1.0
        # Longitudinal knee brace along Y to the front plate beam
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(post_x, py + sgn * 0.23, z_ground + canopy_h - 0.23),
            rotation=(-sgn * 0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        # Transverse knee brace along X to the horizontal tie beam
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(post_x - 0.23, py, z_ground + canopy_h - 0.23),
            rotation=(0.0, -0.785, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        
    # Front longitudinal plate beam along Y connecting the posts
    create_beveled_box(
        bm, size=(col_w, canopy_d + 0.30, 0.18),
        location=(post_x, canopy_cy, z_ground + canopy_h),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    
    # Transverse tie beams along X connecting the wall to the outer posts (embedded into the wall)
    embed_wall = 0.50
    tie_len = canopy_w + embed_wall
    for py in (p1_y, p2_y):
        create_beveled_box(
            bm, size=(tie_len, col_w, 0.18),
            location=(wall_x + canopy_w * 0.5 - embed_wall * 0.5, py, z_ground + canopy_h),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        
    roof_pitch = 0.35
    roof_z_wall = z_ground + canopy_h + canopy_w * roof_pitch
    roof_z_outer = z_ground + canopy_h
    roof_mid_x = (wall_x + outer_x) * 0.5
    roof_mid_z = (roof_z_wall + roof_z_outer) * 0.5 + 0.08
    rafter_l = math.sqrt(canopy_w * canopy_w + (roof_z_wall - roof_z_outer) ** 2) + 0.40
    roof_ang = math.atan2(roof_z_wall - roof_z_outer, canopy_w)
    cos_ang = math.cos(roof_ang)
    sin_ang = math.sin(roof_ang)
    
    # Wall ledger beam supporting rafters against the wall
    create_beveled_box(
        bm, size=(0.28, canopy_d + 0.30, 0.18),
        location=(wall_x, canopy_cy, roof_z_wall - 0.06),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
    )
    
    # Sloping rafters
    for ry in (p1_y, canopy_cy, p2_y):
        create_beveled_box(
            bm, size=(rafter_l, 0.10, 0.14),
            location=(roof_mid_x, ry, roof_mid_z - 0.08),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
    
    # Timber under-deck
    create_beveled_box(
        bm, size=(rafter_l, canopy_d + 0.40, 0.08),
        location=(roof_mid_x, canopy_cy, roof_mid_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.010
    )
    
    # Roof shingle layer with matching 0.32 scale and downhill facing UVs
    shingle_l = rafter_l + 0.05
    shingle_w = canopy_d + 0.46
    slab_z = roof_mid_z + 0.06
    shingle_faces = create_beveled_box(
        bm, size=(shingle_l, shingle_w, 0.05),
        location=(roof_mid_x, canopy_cy, slab_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_SHINGLES,
        bevel_amount=0.008
    )
    apply_roof_shingle_uvs(bm, shingle_faces, scale=0.32)
    
    # Timber framing around the roof (fascia board, side bargeboards, wall trim)
    half_l = shingle_l * 0.5
    
    # Front eave fascia board capping the low edge
    front_x = roof_mid_x + half_l * cos_ang + 0.02
    front_z = slab_z - half_l * sin_ang - 0.02
    create_beveled_box(
        bm, size=(0.08, shingle_w + 0.18, 0.18),
        location=(front_x, canopy_cy, front_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.008
    )
    
    # Side sloping bargeboards down both verges
    for s in (-1.0, 1.0):
        y_barge = canopy_cy + s * (shingle_w * 0.5 + 0.035)
        create_beveled_box(
            bm, size=(shingle_l + 0.10, 0.08, 0.16),
            location=(roof_mid_x, y_barge, slab_z - 0.01),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )
        
    # Top wall trim / flashing where the roof meets the building wall
    back_x = roof_mid_x - half_l * cos_ang - 0.01
    back_z = slab_z + half_l * sin_ang + 0.02
    create_beveled_box(
        bm, size=(0.10, shingle_w + 0.18, 0.14),
        location=(back_x, canopy_cy, back_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.008
    )
