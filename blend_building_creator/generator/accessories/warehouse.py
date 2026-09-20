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


def build_supply_depot_yard(bm, min_x, max_x, min_y, max_y, z_floor, seed=42):
    """
    Builds a high-density, organized medieval supply depot:
    - Multiple clusters of shipping crates (large banded crates, small crates, stacks).
    - Rows and pyramids of standing and lying wooden casks/barrels.
    - Sawn lumber piles with cross-batten spacers (stickers).
    - Burlap sacks grouped in sheltered corners.
    - Wooden cargo pallets / skids.
    """
    from .furniture import build_barrel, build_crate, build_sack
    import random
    rng = random.Random(seed + 808)

    span_x = max_x - min_x
    span_y = max_y - min_y
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5

    # 1. Pallet Skids (heavy wooden cargo bases)
    pallet_locs = [
        (min_x + span_x * 0.28, min_y + span_y * 0.32),
        (min_x + span_x * 0.72, min_y + span_y * 0.35),
        (min_x + span_x * 0.30, min_y + span_y * 0.70),
        (min_x + span_x * 0.70, min_y + span_y * 0.68),
    ]
    for px, py in pallet_locs:
        # 3 bearer skids
        for off in (-0.55, 0.0, 0.55):
            create_beveled_box(
                bm, size=(1.40, 0.12, 0.12),
                location=(px, py + off, z_floor + 0.06),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
        # 5 deck slats
        for si in range(5):
            sx = (si - 2) * 0.28
            create_beveled_box(
                bm, size=(0.18, 1.35, 0.04),
                location=(px + sx, py, z_floor + 0.14),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
            )

    # 2. Crate Clusters on Pallet 0 & Pallet 1
    # Cluster 1 (Left front)
    p0x, p0y = pallet_locs[0]
    build_crate(bm, x=p0x - 0.28, y=p0y - 0.25, z_ground=z_floor + 0.16, ang=0.08, size=0.68)
    build_crate(bm, x=p0x + 0.32, y=p0y - 0.22, z_ground=z_floor + 0.16, ang=-0.05, size=0.62)
    build_crate(bm, x=p0x - 0.15, y=p0y + 0.30, z_ground=z_floor + 0.16, ang=0.15, size=0.55)
    # 2nd tier crate
    build_crate(bm, x=p0x + 0.02, y=p0y - 0.24, z_ground=z_floor + 0.16 + 0.65, ang=0.12, size=0.52)

    # Cluster 2 (Right front)
    p1x, p1y = pallet_locs[1]
    build_crate(bm, x=p1x - 0.30, y=p1y + 0.20, z_ground=z_floor + 0.16, ang=0.0, size=0.65)
    build_crate(bm, x=p1x + 0.28, y=p1y + 0.15, z_ground=z_floor + 0.16, ang=0.22, size=0.60)
    build_crate(bm, x=p1x - 0.05, y=p1y - 0.32, z_ground=z_floor + 0.16, ang=-0.10, size=0.58)
    build_crate(bm, x=p1x + 0.28, y=p1y + 0.15, z_ground=z_floor + 0.16 + 0.60, ang=-0.08, size=0.50)

    # 3. Barrel Racks on Pallet 2 (Left rear)
    p2x, p2y = pallet_locs[2]
    # Standing barrels
    build_barrel(bm, x=p2x - 0.38, y=p2y - 0.32, z_ground=z_floor + 0.16, ang=0.0, radius=0.32, height=0.72)
    build_barrel(bm, x=p2x + 0.28, y=p2y - 0.35, z_ground=z_floor + 0.16, ang=0.5, radius=0.30, height=0.68)
    build_barrel(bm, x=p2x - 0.35, y=p2y + 0.28, z_ground=z_floor + 0.16, ang=1.2, radius=0.31, height=0.70)
    # Lying barrels with chocks
    build_barrel(bm, x=p2x + 0.30, y=p2y + 0.28, z_ground=z_floor + 0.16, ang=1.57, radius=0.28, height=0.74, lying=True)

    # 4. Sawn Lumber Piles on Pallet 3 (Right rear)
    p3x, p3y = pallet_locs[3]
    plank_l = 1.9
    plank_w = 0.95
    for layer in range(5):
        lz = z_floor + 0.16 + layer * 0.11
        create_beveled_box(
            bm, size=(plank_l, plank_w, 0.08),
            location=(p3x, p3y, lz + 0.04),
            rotation=(0.0, 0.0, 0.04),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
        if layer < 4:
            for s_off in (-0.65, 0.0, 0.65):
                create_box(
                    bm, size=(0.05, plank_w + 0.04, 0.03),
                    location=(p3x + s_off, p3y, lz + 0.095),
                    mat_index=MAT_INDEX_TIMBER
                )

    # 5. Burlap Sacks in Corners and Clusters
    sack_pts = [
        (min_x + 0.85, cy - 0.4, 0.2),
        (min_x + 1.15, cy - 0.3, -0.4),
        (min_x + 0.95, cy + 0.2, 0.8),
        (max_x - 0.85, cy - 0.2, 0.0),
        (max_x - 1.10, cy + 0.1, 0.5),
        (cx - 0.3, max_y - 0.75, 0.3),
        (cx + 0.3, max_y - 0.70, -0.2),
    ]
    for sx, sy, sang in sack_pts:
        build_sack(bm, x=sx, y=sy, z_ground=z_floor, ang=sang, scale=1.0)

