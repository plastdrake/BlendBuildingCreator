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

def build_fisherman_stilts(bm, x_min, x_max, y_min, y_max, z_ground, z_floor):
    stilt_h = z_floor - z_ground + 0.60
    stilt_z = z_ground - 0.30 + stilt_h * 0.5
    pile_r = 0.13
    coords = [
        (x_min + pile_r, y_min + pile_r),
        (x_max - pile_r, y_min + pile_r),
        (x_min + pile_r, y_max - pile_r),
        (x_max - pile_r, y_max - pile_r),
        ((x_min + x_max) * 0.5, y_min + pile_r),
        ((x_min + x_max) * 0.5, y_max - pile_r),
    ]
    for px, py in coords:
        create_cylinder(
            bm, radius=pile_r, height=stilt_h, segments=12,
            location=(px, py, stilt_z),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=pile_r * 1.15, height=0.06, segments=12,
            location=(px, py, z_floor - 0.15),
            mat_index=MAT_INDEX_IRON
        )
    bollard_x = x_min - 0.65
    bollard_y = y_min - 0.55
    create_cylinder(
        bm, radius=0.16, height=0.85, segments=12,
        location=(bollard_x, bollard_y, z_ground + 0.425),
        mat_index=MAT_INDEX_TIMBER
    )
    create_cylinder(
        bm, radius=0.19, height=0.10, segments=12,
        location=(bollard_x, bollard_y, z_ground + 0.65),
        mat_index=MAT_INDEX_PLASTER_EXT
    )
    rack_x = x_min - 1.20
    rack_cy = (y_min + y_max) * 0.5
    rack_h = 1.8
    rack_l = 2.4
    create_horizontal_cylinder(
        bm, radius_y=0.06, radius_z=0.06, length=rack_l, segments=12,
        location=(rack_x, rack_cy, z_ground + rack_h),
        rotation=(0.0, 0.0, 1.57),
        mat_index=MAT_INDEX_TIMBER, smooth=True
    )
    for ly in (rack_cy - rack_l * 0.45, rack_cy + rack_l * 0.45):
        leg_len = math.sqrt(rack_h * rack_h + 0.5 * 0.5)
        create_box(
            bm, size=(0.08, 0.08, leg_len),
            location=(rack_x - 0.25, ly, z_ground + rack_h * 0.5),
            rotation=(0.0, 0.28, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )
        create_box(
            bm, size=(0.08, 0.08, leg_len),
            location=(rack_x + 0.25, ly, z_ground + rack_h * 0.5),
            rotation=(0.0, -0.28, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )
