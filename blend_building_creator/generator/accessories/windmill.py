import math
from mathutils import Vector
from ..facade import get_facade_frame
from ..uv_utils import map_planar_faces
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
)

def build_windmill_sails(bm, cx, front_y, hub_z, radius=3.2, rotation_deg=22.5, wall_y=None):
    if wall_y is None:
        wall_y = front_y
        
    hub_y = front_y - 0.38
    box_len = max(0.40, abs(hub_y - wall_y) + 0.25)
    box_cy = (hub_y + wall_y) * 0.5
    create_beveled_box(
        bm, size=(1.10, box_len, 1.05),
        location=(cx, box_cy, hub_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02
    )
    create_beveled_box(
        bm, size=(1.24, box_len + 0.12, 0.18),
        location=(cx, box_cy, hub_z + 0.56),
        mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.012
    )
    for bx_off in [-0.38, 0.38]:
        create_beveled_box(
            bm, size=(0.10, 0.10, 0.55),
            location=(cx + bx_off, box_cy, hub_z - 0.55),
            rotation=(-0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        
    create_cylinder(
        bm, radius=0.35, height=0.45, segments=12,
        location=(cx, hub_y, hub_z),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )
    create_cone(
        bm, radius1=0.22, radius2=0.04, height=0.20, segments=8,
        location=(cx, hub_y - 0.28, hub_z),
        rotation=(-1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )

    blade_y = hub_y - 0.15
    rad_base = math.radians(rotation_deg)
    
    for i in range(4):
        blade_angle = rad_base + i * (math.pi * 0.5)
        dir_x = math.cos(blade_angle)
        dir_z = math.sin(blade_angle)
        norm_x = -dir_z
        norm_z = dir_x
        
        mid_span = radius * 0.5
        spar_cx = cx + dir_x * mid_span
        spar_cz = hub_z + dir_z * mid_span
        
        create_beveled_box(
            bm, size=(radius, 0.09, 0.11),
            location=(spar_cx, blade_y, spar_cz),
            rotation=(0.0, -blade_angle, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        
        num_ribs = 5
        rib_len = 0.85
        sail_w = 0.70
        
        for r in range(1, num_ribs + 1):
            t_r = 0.25 + (r / float(num_ribs)) * 0.72
            rib_dist = radius * t_r
            rib_x = cx + dir_x * rib_dist + norm_x * (rib_len * 0.5)
            rib_z = hub_z + dir_z * rib_dist + norm_z * (rib_len * 0.5)
            create_box(
                bm, size=(0.04, 0.04, rib_len),
                location=(rib_x, blade_y - 0.02, rib_z),
                rotation=(0.0, -blade_angle + 1.57, 0.0),
                mat_index=MAT_INDEX_TIMBER
            )
            
        sail_len = radius * 0.70
        sail_cx = cx + dir_x * (radius * 0.62) + norm_x * (sail_w * 0.5)
        sail_cz = hub_z + dir_z * (radius * 0.62) + norm_z * (sail_w * 0.5)
        create_beveled_box(
            bm, size=(sail_len, 0.015, sail_w),
            location=(sail_cx, blade_y - 0.04, sail_cz),
            rotation=(0.0, -blade_angle, 0.08),
            mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.002
        )
