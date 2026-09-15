import math
from mathutils import Vector
from ..mesh_utils import (
    create_beveled_box, create_cylinder,
    create_torus_ring, create_door_batten
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_DOOR,
)


def _beam(bm, p1, p2, w, mat):
    v1 = Vector(p1)
    v2 = Vector(p2)
    d = v2 - v1
    length = max(0.05, d.length)
    mid = (v1 + v2) * 0.5
    rot = d.to_track_quat('Z', 'Y').to_euler()
    create_beveled_box(
        bm, size=(w, w, length),
        location=(mid.x, mid.y, mid.z),
        rotation=rot, mat_index=mat, bevel_amount=0.008
    )


def build_gable_loft_hatch(bm, wall_axis, wall_face, center, sill_z,
                           z_ground=0.0, outward=1.0):
    hatch_w = 0.90
    hatch_h = 1.20
    cz = sill_z + hatch_h * 0.5

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
        for hz in (sill_z + hatch_h * 0.25, sill_z + hatch_h * 0.75):
            _box((0.05, 0.16, 0.05), (center - hatch_w * 0.5 - 0.05, wall_face + outward * 0.06, hz),
                 MAT_INDEX_IRON, bevel=0.004)
            create_cylinder(
                bm, radius=0.018, height=0.12, segments=8,
                location=(center - hatch_w * 0.5 - 0.05, wall_face + outward * 0.06, hz),
                mat_index=MAT_INDEX_IRON
            )
        open_ang = outward * 1.8326
        ca = math.cos(open_ang)
        sa = math.sin(open_ang)
        hinge_x = center - hatch_w * 0.5
        hinge_y = wall_face - outward * 0.03
        leaf_x = hinge_x + 0.45 * ca
        leaf_y = hinge_y + outward * 0.45 * abs(sa)
        leaf_rot = (0.0, 0.0, open_ang)
        create_beveled_box(
            bm, size=(hatch_w, 0.05, hatch_h), location=(leaf_x, leaf_y, cz),
            rotation=leaf_rot, mat_index=MAT_INDEX_DOOR,
            bevel_amount=0.008, bevel_segments=2
        )
        for bf in (0.18, 0.82):
            create_door_batten(
                bm, size=(hatch_w * 0.92, 0.022, 0.10),
                location=(leaf_x, leaf_y - outward * 0.035, sill_z + hatch_h * bf),
                rotation=leaf_rot, mat_index=MAT_INDEX_DOOR,
                bevel_amount=0.004, bevel_segments=2
            )
        _box((0.30, 0.016, 0.05),
             (hinge_x + 0.17 * ca, hinge_y + outward * (0.17 * abs(sa) + 0.035), sill_z + hatch_h * 0.72),
             MAT_INDEX_IRON, bevel=0.003, rot=leaf_rot)
        create_torus_ring(
            bm, location=(hinge_x + 0.78 * ca, hinge_y + outward * (0.78 * abs(sa) + 0.05), sill_z + hatch_h * 0.5),
            rotation=(0.0, 0.0, 0.0),
            major_radius=0.055, minor_radius=0.011,
            major_segments=12, minor_segments=8, mat_index=MAT_INDEX_IRON
        )
        rail_top_z = sill_z + 0.95
        base_off = min(1.2, 0.30 + rail_top_z * 0.06)
        for sx in (-0.26, 0.26):
            _beam(bm, (center + sx, wall_face + outward * base_off, z_ground),
                  (center + sx, wall_face + outward * 0.06, rail_top_z),
                  0.07, MAT_INDEX_TIMBER)
        _rung_n = max(3, int((sill_z - 0.30) / 0.30))
        for r in range(_rung_n):
            rz = 0.32 + r * ((sill_z - 0.10 - 0.32) / max(1, _rung_n - 1))
            t = (rz - z_ground) / max(0.01, rail_top_z - z_ground)
            ry = (wall_face + outward * base_off) * (1.0 - t) + (wall_face + outward * 0.06) * t
            create_cylinder(
                bm, radius=0.025, height=0.52, segments=8,
                location=(center, ry, rz),
                rotation=(0.0, 1.5708, 0.0), mat_index=MAT_INDEX_TIMBER
            )
    else:
        _box((0.14, 0.10, hatch_h + 0.1), (wall_face, center - hatch_w * 0.5 - 0.05, cz), MAT_INDEX_TIMBER_FRAME)
        _box((0.14, 0.10, hatch_h + 0.1), (wall_face, center + hatch_w * 0.5 + 0.05, cz), MAT_INDEX_TIMBER_FRAME)
        _box((0.14, hatch_w + 0.30, 0.12), (wall_face, center, sill_z + hatch_h + 0.06), MAT_INDEX_TIMBER_FRAME)
        _box((0.18, hatch_w + 0.24, 0.10), (wall_face, center, sill_z - 0.05), MAT_INDEX_TIMBER)
        for hz in (sill_z + hatch_h * 0.25, sill_z + hatch_h * 0.75):
            _box((0.16, 0.05, 0.05), (wall_face + outward * 0.06, center - hatch_w * 0.5 - 0.05, hz),
                 MAT_INDEX_IRON, bevel=0.004)
            create_cylinder(
                bm, radius=0.018, height=0.12, segments=8,
                location=(wall_face + outward * 0.06, center - hatch_w * 0.5 - 0.05, hz),
                mat_index=MAT_INDEX_IRON
            )
        open_ang = 4.4506 if outward > 0 else 1.8326
        hinge_x = wall_face - outward * 0.03
        hinge_y = center - hatch_w * 0.5
        leaf_x = hinge_x + outward * (0.45 * 0.9659)
        leaf_y = hinge_y - 0.45 * 0.2588
        leaf_rot = (0.0, 0.0, open_ang)
        create_beveled_box(
            bm, size=(0.05, hatch_w, hatch_h), location=(leaf_x, leaf_y, cz),
            rotation=leaf_rot, mat_index=MAT_INDEX_DOOR,
            bevel_amount=0.008, bevel_segments=2
        )
        for bf in (0.18, 0.82):
            create_door_batten(
                bm, size=(0.022, hatch_w * 0.92, 0.10),
                location=(leaf_x - outward * 0.035, leaf_y, sill_z + hatch_h * bf),
                rotation=leaf_rot, mat_index=MAT_INDEX_DOOR,
                bevel_amount=0.004, bevel_segments=2
            )
        _box((0.016, 0.30, 0.05),
             (hinge_x + outward * (0.17 * 0.9659 + 0.035), hinge_y - 0.17 * 0.2588, sill_z + hatch_h * 0.72),
             MAT_INDEX_IRON, bevel=0.003, rot=leaf_rot)
        create_torus_ring(
            bm, location=(hinge_x + outward * (0.78 * 0.9659 + 0.05), hinge_y - 0.78 * 0.2588, sill_z + hatch_h * 0.5),
            rotation=(0.0, 1.5708, 0.0),
            major_radius=0.055, minor_radius=0.011,
            major_segments=12, minor_segments=8, mat_index=MAT_INDEX_IRON
        )
        rail_top_z = sill_z + 0.95
        base_off = min(1.2, 0.30 + rail_top_z * 0.06)
        for sz in (-0.26, 0.26):
            _beam(bm, (wall_face + outward * base_off, center + sz, z_ground),
                  (wall_face + outward * 0.06, center + sz, rail_top_z),
                  0.07, MAT_INDEX_TIMBER)
        _rung_n = max(3, int((sill_z - 0.30) / 0.30))
        for r in range(_rung_n):
            rz = 0.32 + r * ((sill_z - 0.10 - 0.32) / max(1, _rung_n - 1))
            t = (rz - z_ground) / max(0.01, rail_top_z - z_ground)
            rx = (wall_face + outward * base_off) * (1.0 - t) + (wall_face + outward * 0.06) * t
            create_cylinder(
                bm, radius=0.025, height=0.52, segments=8,
                location=(rx, center, rz),
                rotation=(1.5708, 0.0, 0.0), mat_index=MAT_INDEX_TIMBER
            )
