import math
from mathutils import Vector
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder,
    create_torus_ring, create_door_batten
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_DOOR,
)


def build_gable_loft_hatch(bm, wall_axis, wall_face, center, sill_z,
                           z_ground=0.0):
    hatch_w = 0.90
    hatch_h = 1.20
    cz = sill_z + hatch_h * 0.5
    if wall_axis == 'Y':
        nx, nz = wall_face, center
    else:
        nx, nz = center, wall_face

    def _box(size, loc, mat, bevel=0.008, rot=(0.0, 0.0, 0.0)):
        create_beveled_box(
            bm, size=size, location=loc, rotation=rot,
            mat_index=mat, bevel_amount=bevel
        )

    if wall_axis == 'Y':
        _box((0.10, 0.14, hatch_h + 0.1), (center - hatch_w * 0.5 - 0.05, wall_face, cz), MAT_INDEX_TIMBER_FRAME)
        _box((0.10, 0.14, hatch_h + 0.1), (center + hatch_w * 0.5 + 0.05, wall_face, cz), MAT_INDEX_TIMBER_FRAME)
        _box((hatch_w + 0.30, 0.14, 0.12), (center, wall_face, sill_z + hatch_h + 0.06), MAT_INDEX_TIMBER_FRAME)
        _box((hatch_w + 0.24, 0.18, 0.10), (center, wall_face, sill_z - 0.05), MAT_INDEX_TIMBER)
        leaf_c = (center, wall_face - 0.045, cz)
        create_beveled_box(
            bm, size=(hatch_w, 0.06, hatch_h), location=leaf_c,
            mat_index=MAT_INDEX_DOOR, bevel_amount=0.008, bevel_segments=2
        )
        for bf in (0.18, 0.82):
            create_door_batten(
                bm, size=(hatch_w * 0.92, 0.022, 0.10),
                location=(center, wall_face - 0.085, sill_z + hatch_h * bf),
                mat_index=MAT_INDEX_DOOR, bevel_amount=0.004, bevel_segments=2
            )
        for hz in (sill_z + hatch_h * 0.25, sill_z + hatch_h * 0.75):
            _box((0.30, 0.018, 0.05), (center - hatch_w * 0.5 + 0.17, wall_face - 0.02, hz), MAT_INDEX_IRON, bevel=0.003)
        create_torus_ring(
            bm, location=(center + hatch_w * 0.28, wall_face - 0.10, sill_z + hatch_h * 0.5),
            rotation=(0.0, 0.0, 0.0),
            major_radius=0.055, minor_radius=0.011,
            major_segments=12, minor_segments=8, mat_index=MAT_INDEX_IRON
        )
    else:
        _box((0.14, 0.10, hatch_h + 0.1), (wall_face, center - hatch_w * 0.5 - 0.05, cz), MAT_INDEX_TIMBER_FRAME)
        _box((0.14, 0.10, hatch_h + 0.1), (wall_face, center + hatch_w * 0.5 + 0.05, cz), MAT_INDEX_TIMBER_FRAME)
        _box((0.14, hatch_w + 0.30, 0.12), (wall_face, center, sill_z + hatch_h + 0.06), MAT_INDEX_TIMBER_FRAME)
        _box((0.18, hatch_w + 0.24, 0.10), (wall_face, center, sill_z - 0.05), MAT_INDEX_TIMBER)
        create_beveled_box(
            bm, size=(0.06, hatch_w, hatch_h), location=(wall_face - 0.045, center, cz),
            mat_index=MAT_INDEX_DOOR, bevel_amount=0.008, bevel_segments=2
        )
        for bf in (0.18, 0.82):
            create_door_batten(
                bm, size=(0.022, hatch_w * 0.92, 0.10),
                location=(wall_face - 0.085, center, sill_z + hatch_h * bf),
                mat_index=MAT_INDEX_DOOR, bevel_amount=0.004, bevel_segments=2
            )
        for hz in (sill_z + hatch_h * 0.25, sill_z + hatch_h * 0.75):
            _box((0.018, 0.30, 0.05), (wall_face - 0.02, center - hatch_w * 0.5 + 0.17, hz), MAT_INDEX_IRON, bevel=0.003)
        create_torus_ring(
            bm, location=(wall_face - 0.10, center + hatch_w * 0.28, sill_z + hatch_h * 0.5),
            rotation=(0.0, 1.5708, 0.0),
            major_radius=0.055, minor_radius=0.011,
            major_segments=12, minor_segments=8, mat_index=MAT_INDEX_IRON
        )

    rail_off = 0.30
    rail_w = 0.07
    top_z = sill_z + 0.15
    rail_h = top_z - z_ground
    rail_cz = z_ground + rail_h * 0.5
    if wall_axis == 'Y':
        lad_y = wall_face + rail_off
        for sx in (-0.26, 0.26):
            _box((rail_w, rail_w, rail_h), (center + sx, lad_y, rail_cz), MAT_INDEX_TIMBER)
        n_rungs = max(3, int(rail_h / 0.30))
        for r in range(n_rungs):
            rz = z_ground + 0.30 + r * ((rail_h - 0.45) / max(1, n_rungs - 1))
            if rz > top_z - 0.10:
                break
            create_cylinder(
                bm, radius=0.025, height=0.52, segments=8,
                location=(center, lad_y, rz),
                rotation=(0.0, 1.5708, 0.0), mat_index=MAT_INDEX_TIMBER
            )
        for bz in (z_ground + rail_h * 0.33, z_ground + rail_h * 0.66):
            _box((0.06, rail_off, 0.06), (center, wall_face + rail_off * 0.5, bz), MAT_INDEX_IRON, bevel=0.004)
    else:
        lad_x = wall_face + rail_off
        for sz in (-0.26, 0.26):
            _box((rail_w, rail_w, rail_h), (lad_x, center + sz, rail_cz), MAT_INDEX_TIMBER)
        n_rungs = max(3, int(rail_h / 0.30))
        for r in range(n_rungs):
            rz = z_ground + 0.30 + r * ((rail_h - 0.45) / max(1, n_rungs - 1))
            if rz > top_z - 0.10:
                break
            create_cylinder(
                bm, radius=0.025, height=0.52, segments=8,
                location=(lad_x, center, rz),
                rotation=(1.5708, 0.0, 0.0), mat_index=MAT_INDEX_TIMBER
            )
        for bz in (z_ground + rail_h * 0.33, z_ground + rail_h * 0.66):
            _box((rail_off, 0.06, 0.06), (wall_face + rail_off * 0.5, center, bz), MAT_INDEX_IRON, bevel=0.004)
