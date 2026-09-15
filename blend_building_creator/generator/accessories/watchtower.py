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

def build_watchtower_lookout(bm, x_min, x_max, y_min, y_max, z_platform):
    overhang = 0.45
    ox_min = x_min - overhang
    ox_max = x_max + overhang
    oy_min = y_min - overhang
    oy_max = y_max + overhang
    
    total_w = ox_max - ox_min
    total_d = oy_max - oy_min
    cx = (ox_min + ox_max) * 0.5
    cy = (oy_min + oy_max) * 0.5
    
    num_corbels_x = max(2, int(round((x_max - x_min) / 1.5)))
    step_x = (x_max - x_min) / float(num_corbels_x)
    for i in range(num_corbels_x + 1):
        bx = x_min + i * step_x
        create_beveled_box(
            bm, size=(0.14, 0.45, 0.14),
            location=(bx, y_min - overhang * 0.5, z_platform - 0.10),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )
        create_beveled_box(
            bm, size=(0.10, 0.55, 0.10),
            location=(bx, y_min - overhang * 0.30, z_platform - 0.38),
            rotation=(0.78, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        create_beveled_box(
            bm, size=(0.14, 0.45, 0.14),
            location=(bx, y_max + overhang * 0.5, z_platform - 0.10),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )
        create_beveled_box(
            bm, size=(0.10, 0.55, 0.10),
            location=(bx, y_max + overhang * 0.30, z_platform - 0.38),
            rotation=(-0.78, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    create_beveled_box(
        bm, size=(total_w, total_d, 0.14),
        location=(cx, cy, z_platform),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
    )
    
    parapet_h = 1.35
    pz = z_platform + parapet_h * 0.5
    
    def build_parapet_wall_with_slits(length, is_x_axis, center_pos):
        base_h = 0.45
        size_base = (length, 0.12, base_h) if is_x_axis else (0.12, length, base_h)
        create_beveled_box(
            bm, size=size_base,
            location=(center_pos[0], center_pos[1], z_platform + base_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
        num_posts = max(3, int(length / 1.1))
        post_step = length / float(num_posts)
        post_w = 0.45
        upper_h = parapet_h - base_h
        for p in range(num_posts + 1):
            pos_offset = -length * 0.5 + p * post_step
            if is_x_axis:
                px = center_pos[0] + pos_offset
                py = center_pos[1]
                size_post = (min(post_w, post_step * 0.65), 0.12, upper_h)
            else:
                px = center_pos[0]
                py = center_pos[1] + pos_offset
                size_post = (0.12, min(post_w, post_step * 0.65), upper_h)
            create_beveled_box(
                bm, size=size_post,
                location=(px, py, z_platform + base_h + upper_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
            )
        cap_h = 0.08
        size_cap = (length + 0.06, 0.16, cap_h) if is_x_axis else (0.16, length + 0.06, cap_h)
        create_beveled_box(
            bm, size=size_cap,
            location=(center_pos[0], center_pos[1], z_platform + parapet_h + cap_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    build_parapet_wall_with_slits(total_w, True, (cx, oy_min + 0.06))
    build_parapet_wall_with_slits(total_w, True, (cx, oy_max - 0.06))
    build_parapet_wall_with_slits(total_d - 0.24, False, (ox_min + 0.06, cy))
    build_parapet_wall_with_slits(total_d - 0.24, False, (ox_max - 0.06, cy))
