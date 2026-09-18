"""Reusable heraldic banner poles and cloth standards."""

import math
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME,
    MAT_INDEX_IRON, MAT_INDEX_BANNER,
)


def build_banner_pole(bm, x, y, z_ground=0.0, height=4.6,
                      flag_len=0.95, flag_h=0.62, flag_dir=(1.0, 0.0)):
    """A timber standard with an iron finial and a waving cloth banner."""
    create_cylinder(bm, radius=0.075, height=0.28, segments=8,
                    location=(x, y, z_ground + 0.14), mat_index=MAT_INDEX_TIMBER_FRAME)
    create_cylinder(bm, radius=0.048, height=height, segments=8,
                    location=(x, y, z_ground + 0.28 + height * 0.5), mat_index=MAT_INDEX_WOOD)
    top_z = z_ground + 0.28 + height
    create_cylinder(bm, radius=0.09, height=0.10, segments=8,
                    location=(x, y, top_z - 0.05), mat_index=MAT_INDEX_TIMBER_FRAME)
    create_cone(bm, radius1=0.07, radius2=0.0, height=0.22, segments=8,
                location=(x, y, top_z + 0.11), mat_index=MAT_INDEX_IRON)

    ang = math.atan2(flag_dir[1], flag_dir[0])
    # Crossbar the cloth hangs from.
    create_cylinder(bm, radius=0.028, height=flag_len + 0.10, segments=6,
                    location=(x + math.cos(ang) * flag_len * 0.5,
                              y + math.sin(ang) * flag_len * 0.5,
                              top_z - 0.10),
                    rotation=(0.0, 1.5708, ang), mat_index=MAT_INDEX_WOOD)
    # Two cloth panels at slight opposing angles so it reads as a waving flag.
    panel_w = flag_len * 0.5
    for off, rot_off in ((0.30, 0.10), (0.76, -0.10)):
        cx = x + math.cos(ang) * (flag_len * off)
        cy = y + math.sin(ang) * (flag_len * off)
        create_beveled_box(
            bm, size=(panel_w, 0.035, flag_h),
            location=(cx, cy, top_z - 0.12 - flag_h * 0.5),
            rotation=(0.0, 0.0, ang + rot_off),
            mat_index=MAT_INDEX_BANNER, bevel_amount=0.006,
        )
