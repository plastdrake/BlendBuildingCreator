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

def build_bakery_oven(bm, x_min, x_max, y_min, y_max, z_ground):
    oven_x = x_max + 0.85
    oven_y = (y_min + y_max) * 0.5
    oven_w = 1.6
    oven_d = 1.5
    oven_h = 1.35
    create_beveled_box(
        bm, size=(oven_w, oven_d, 0.50),
        location=(oven_x, oven_y, z_ground + 0.25),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.02
    )
    create_cylinder(
        bm, radius=0.65, height=0.65, segments=16,
        location=(oven_x, oven_y, z_ground + 0.50 + 0.325),
        mat_index=MAT_INDEX_STONE
    )
    create_cone(
        bm, radius1=0.65, radius2=0.15, height=0.45, segments=16,
        location=(oven_x, oven_y, z_ground + 0.50 + 0.65 + 0.225),
        mat_index=MAT_INDEX_STONE
    )
    chim_h = 2.4
    create_beveled_box(
        bm, size=(0.42, 0.42, chim_h),
        location=(oven_x - 0.35, oven_y, z_ground + 1.10 + chim_h * 0.5),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.015
    )
    create_beveled_box(
        bm, size=(0.52, 0.52, 0.12),
        location=(oven_x - 0.35, oven_y, z_ground + 1.10 + chim_h + 0.06),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.01
    )
