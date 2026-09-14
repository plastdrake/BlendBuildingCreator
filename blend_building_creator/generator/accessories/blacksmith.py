import math
from mathutils import Vector
from .common import (
    _get_facade_frame, _planar_uv_faces
)
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from ..walls import create_curved_corbel
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
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
    
    for py in (p1_y, p2_y):
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.20),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.10),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
        pillar_h = canopy_h - 0.20
        create_beveled_box(
            bm, size=(col_w, col_w, pillar_h),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.20 + pillar_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        sgn = 1.0 if py < canopy_cy else -1.0
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(outer_x - col_w * 0.5, py + sgn * 0.23, z_ground + canopy_h - 0.23),
            rotation=(sgn * 0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(outer_x - col_w * 0.5 - 0.23, py, z_ground + canopy_h - 0.23),
            rotation=(0.0, -0.785, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        
    create_beveled_box(
        bm, size=(col_w, canopy_d + 0.30, 0.18),
        location=(outer_x - col_w * 0.5, canopy_cy, z_ground + canopy_h),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    
    roof_pitch = 0.35
    roof_z_wall = z_ground + canopy_h + canopy_w * roof_pitch
    roof_z_outer = z_ground + canopy_h
    roof_mid_x = (wall_x + outer_x) * 0.5
    roof_mid_z = (roof_z_wall + roof_z_outer) * 0.5 + 0.08
    rafter_l = math.sqrt(canopy_w * canopy_w + (roof_z_wall - roof_z_outer) ** 2) + 0.40
    roof_ang = math.atan2(roof_z_wall - roof_z_outer, canopy_w)
    
    for ry in (p1_y, canopy_cy, p2_y):
        create_beveled_box(
            bm, size=(rafter_l, 0.10, 0.14),
            location=(roof_mid_x, ry, roof_mid_z - 0.08),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
    
    create_beveled_box(
        bm, size=(rafter_l, canopy_d + 0.40, 0.08),
        location=(roof_mid_x, canopy_cy, roof_mid_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.010
    )
    create_beveled_box(
        bm, size=(rafter_l + 0.05, canopy_d + 0.46, 0.05),
        location=(roof_mid_x, canopy_cy, roof_mid_z + 0.06),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_SHINGLES,
        bevel_amount=0.008
    )
    
    forge_w, forge_d, forge_h = 0.95, 0.95, 0.85
    forge_x = wall_x + forge_w * 0.5 + 0.15
    forge_y = canopy_cy
    create_beveled_box(
        bm, size=(forge_w, forge_d, forge_h),
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h * 0.5),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.02
    )
    create_box(
        bm, size=(0.60, 0.60, 0.06),
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h + 0.02),
        mat_index=MAT_INDEX_IRON
    )
    chim_pipe_h = (roof_z_wall + 0.80) - (z_ground + deck_thick + forge_h)
    create_cylinder(
        bm, radius=0.14, height=chim_pipe_h, segments=10,
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h + chim_pipe_h * 0.5),
        mat_index=MAT_INDEX_IRON
    )
    
    stump_r = 0.24
    stump_h = 0.46
    stump_x = wall_x + 1.65
    stump_y = canopy_cy - 0.40
    create_cylinder(
        bm, radius=stump_r, height=stump_h, segments=10,
        location=(stump_x, stump_y, z_ground + deck_thick + stump_h * 0.5),
        mat_index=MAT_INDEX_WOOD
    )
    anvil_z = z_ground + deck_thick + stump_h
    create_beveled_box(
        bm, size=(0.28, 0.54, 0.22),
        location=(stump_x, stump_y, anvil_z + 0.11),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.015
    )
    create_cone(
        bm, radius1=0.09, radius2=0.02, height=0.22, segments=8,
        location=(stump_x, stump_y - 0.38, anvil_z + 0.12),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    
    trough_w, trough_d, trough_h = 0.45, 0.70, 0.46
    trough_x = wall_x + 0.60
    trough_y = canopy_cy + canopy_d * 0.34
    create_beveled_box(
        bm, size=(trough_w, trough_d, trough_h),
        location=(trough_x, trough_y, z_ground + deck_thick + trough_h * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
    )
    for bz in [-0.14, 0.14]:
        create_box(
            bm, size=(trough_w + 0.02, trough_d + 0.02, 0.035),
            location=(trough_x, trough_y, z_ground + deck_thick + trough_h * 0.5 + bz),
            mat_index=MAT_INDEX_IRON
        )
