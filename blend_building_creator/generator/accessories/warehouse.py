import math
from mathutils import Vector
from ..facade import get_facade_frame
from ..uv_utils import map_planar_faces
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

def build_warehouse_cargo(bm, front_x, front_y, z_ground):
    create_beveled_box(
        bm, size=(0.85, 0.85, 0.85),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
    )
    create_box(
        bm, size=(0.87, 0.10, 0.87),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_IRON
    )
    create_beveled_box(
        bm, size=(0.60, 0.60, 0.60),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.85 + 0.30),
        rotation=(0.0, 0.0, -0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    for bx, by in [(front_x - 1.45, front_y - 0.60), (front_x - 1.05, front_y - 0.95)]:
        create_cylinder(
            bm, radius=0.32, height=0.75, segments=12,
            location=(bx, by, z_ground + 0.375),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=0.328, height=0.05, segments=12,
            location=(bx, by, z_ground + 0.18),
            mat_index=MAT_INDEX_IRON
        )
        create_cylinder(
            bm, radius=0.328, height=0.05, segments=12,
            location=(bx, by, z_ground + 0.57),
            mat_index=MAT_INDEX_IRON
        )
