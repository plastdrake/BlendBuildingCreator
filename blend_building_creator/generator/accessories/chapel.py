"""Reusable Healers' Chapel kit.

Small, single-purpose builders (GRASP) that reuse the shared curved-shell maths
in :mod:`generator.poly`, the square spire in ``accessories.tower`` and the wall
lantern in ``accessories.lighting``:

- :func:`build_chapel_apse`  - half-round chancel open to the nave
- :func:`build_bell_tower`   - free-standing campanile with a spire + cross
- :func:`build_rose_window`  - decorative wheel window for the gable
- :func:`build_chapel_kit`   - layout orchestrator for the whole chapel

The apse is a genuine *half* drum attached to the back wall (never a full circle
buried inside the nave), roofed with a half-cone whose shingle UVs match the main
roof.
"""

import math

from mathutils import Matrix, Vector

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_box,
    create_torus_ring,
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON, MAT_INDEX_GLASS,
    MAT_INDEX_FLOOR, MAT_INDEX_SHINGLES,
)
from ..poly import segment_frame, wall_ring
from ..openings import build_door_assembly, build_window_assembly
from ..style import tier_wall_mat
from ..walls import build_wall_with_opening
from ..uv_utils import apply_roof_shingle_uvs
from .tower import build_square_spire_roof
from .lighting import build_hanging_lantern


def build_chapel_apse(bm, cx, cy, z_ground, z_top, radius, wall_t, tier, seed,
                      door_w=1.3, door_h=2.5):
    """A fully-walled octagonal chancel pavilion behind the nave.

    ``cy`` is the nave's rear wall line; the pavilion is placed just outside it
    so it never appears inside the nave. Facet 0 faces the nave and carries a
    doorway that lines up with the nave's rear door (``has_back_door``), so the
    two interiors connect. A full shingle cone caps it.
    """
    segments = 8
    d_ang = 2.0 * math.pi / segments
    offset = -math.radians(112.5)          # facet 0 faces -Y (toward the nave)
    wall_mat = tier_wall_mat(tier)
    ccx = cx
    ccy = cy + wall_t * 0.5 + 0.02 + radius   # sit just outside the nave wall

    # Full floor disc, level with the nave floor.
    create_cylinder(bm, radius=radius - wall_t * 0.5, height=0.14,
                    segments=segments, location=(ccx, ccy, z_ground + 0.07),
                    mat_index=MAT_INDEX_FLOOR)

    facet_len = 2.0 * radius * math.sin(d_ang * 0.5)
    win_w = min(0.9, facet_len - 0.55)
    win_h = min(1.7, (z_top - z_ground) * 0.62)
    win_cz = z_ground + (z_top - z_ground) * 0.55
    stone_top = min(z_ground + 1.0, z_top - 0.4)

    openings = {}
    win_specs = []
    for k in range(segments):
        _p1, _p2, nrm, mid = segment_frame(radius, k, segments, offset)
        u_mid = facet_len * 0.5
        if k == 0:
            openings[k] = [{'u_start': u_mid - door_w * 0.5, 'u_end': u_mid + door_w * 0.5,
                            'z_start': z_ground, 'z_end': z_ground + door_h + 0.12}]
        elif k in (2, 3, 4, 5, 6):
            openings[k] = [{'u_start': u_mid - win_w * 0.5, 'u_end': u_mid + win_w * 0.5,
                            'z_start': win_cz - win_h * 0.5, 'z_end': win_cz + win_h * 0.5}]
            win_specs.append(((ccx + mid[0], ccy + mid[1], win_cz), (nrm.x, nrm.y)))
        else:
            openings[k] = []

    wall_ring(bm, radius, z_ground, stone_top, wall_t, segments, offset,
              openings, MAT_INDEX_STONE, tier=tier, seed=seed)
    wall_ring(bm, radius, stone_top, z_top, wall_t, segments, offset,
              openings, wall_mat, tier=tier, seed=seed + 7)

    _p1, _p2, _n, mid0 = segment_frame(radius, 0, segments, offset)
    build_door_assembly(bm, center_x=ccx + mid0[0], y_front=ccy + mid0[1],
                        z_base=z_ground, wall_thickness=wall_t, door_w=door_w,
                        door_h=door_h, door_angle_deg=0.0, door_shape='ARCHED',
                        ground_floor_stone=False, normal_axis='-Y')
    for center, nv in win_specs:
        build_window_assembly(bm, center=center, size=(win_w, win_h),
                              wall_thickness=wall_t, normal_axis=nv,
                              has_shutters=False)

    # Full shingle cone roof over the pavilion.
    roof_r = radius + 0.24
    roof_h = max(1.9, radius * 0.95)
    uv = bm.loops.layers.uv.verify()
    cone = create_cone(bm, radius1=roof_r, radius2=0.06, height=roof_h,
                       segments=segments, location=(ccx, ccy, z_top + roof_h * 0.5),
                       mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, cone)
    create_cylinder(bm, radius=roof_r + 0.04, height=0.14, segments=segments,
                    location=(ccx, ccy, z_top + 0.06), mat_index=MAT_INDEX_TIMBER)
    create_cylinder(bm, radius=0.035, height=0.6, segments=6,
                    location=(ccx, ccy, z_top + roof_h + 0.26),
                    mat_index=MAT_INDEX_IRON)


def _square_shaft(bm, cx, cy, size, wall_t, z0, z1, tier, seed,
                  openings_per_face):
    """A square tower shaft from four wall facets with per-face openings."""
    half = size * 0.5
    inset = wall_t * 0.5
    faces = {
        'front': ((cx - half, cy - half + inset), (cx + half, cy - half + inset), (0.0, -1.0)),
        'back': ((cx - half, cy + half - inset), (cx + half, cy + half - inset), (0.0, 1.0)),
        'left': ((cx - half + inset, cy - half), (cx - half + inset, cy + half), (-1.0, 0.0)),
        'right': ((cx + half - inset, cy - half), (cx + half - inset, cy + half), (1.0, 0.0)),
    }
    wall_mat = tier_wall_mat(tier)
    stone_top = min(z0 + size * 0.55, z1 - 0.4)
    for face, (p0, p1, nv) in faces.items():
        ops = openings_per_face.get(face, [])
        if stone_top > z0 + 0.1:
            band_ops = [o for o in ops if o['z_end'] > z0 + 0.01 and o['z_start'] < stone_top - 0.01]
            build_wall_with_opening(bm, p0, p1, z0, stone_top, wall_t, band_ops,
                                    mat_ext=MAT_INDEX_STONE, normal_vec=nv,
                                    tier=tier, physical_siding=False, seed=seed)
        if z1 > stone_top + 0.06:
            band_ops = [o for o in ops if o['z_end'] > stone_top + 0.01 and o['z_start'] < z1 - 0.01]
            build_wall_with_opening(bm, p0, p1, stone_top, z1, wall_t, band_ops,
                                    mat_ext=wall_mat, normal_vec=nv,
                                    tier=tier, physical_siding=False, seed=seed + 3)


def build_bell_tower(bm, cx, cy, z_ground, size, z_top, tier, seed):
    """A slender free-standing campanile: louvred belfry, hung bell, spire, cross."""
    wall_t = 0.34
    half = size * 0.5

    create_beveled_box(bm, size=(size + 0.9, size + 0.9, 0.32),
                       location=(cx, cy, z_ground + 0.16),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(size + 0.55, size + 0.55, 0.42),
                       location=(cx, cy, z_ground + 0.50),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)
    base_z = z_ground + 0.70

    belfry_h = 1.7
    shaft_top = z_top - belfry_h - 0.8
    win_w, win_h = 0.42, 1.0

    # Opening centre is half the *face* length (the shaft spans the full size).
    openings = {}
    for face in ('front', 'back', 'left', 'right'):
        c = size * 0.5
        openings[face] = [
            {'u_start': c - win_w * 0.5, 'u_end': c + win_w * 0.5,
             'z_start': base_z + (shaft_top - base_z) * 0.35 - win_h * 0.5,
             'z_end': base_z + (shaft_top - base_z) * 0.35 + win_h * 0.5},
            {'u_start': c - win_w * 0.5, 'u_end': c + win_w * 0.5,
             'z_start': shaft_top - 1.3 - win_h * 0.5,
             'z_end': shaft_top - 1.3 + win_h * 0.5},
        ]
    _square_shaft(bm, cx, cy, size, wall_t, base_z, shaft_top, tier, seed, openings)
    for face, (px, py, nv) in {
        'front': (cx, cy - half + wall_t * 0.5, (0.0, -1.0)),
        'back': (cx, cy + half - wall_t * 0.5, (0.0, 1.0)),
        'left': (cx - half + wall_t * 0.5, cy, (-1.0, 0.0)),
        'right': (cx + half - wall_t * 0.5, cy, (1.0, 0.0)),
    }.items():
        for wz in (base_z + (shaft_top - base_z) * 0.35, shaft_top - 1.3):
            build_window_assembly(bm, center=(px, py, wz), size=(win_w, win_h),
                                  wall_thickness=wall_t, normal_axis=nv,
                                  has_shutters=False)

    create_beveled_box(bm, size=(size + 0.4, size + 0.4, 0.18),
                       location=(cx, cy, shaft_top + 0.09),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Open belfry: four posts, sill rails, top plate.
    belf_z = shaft_top + 0.18
    post_h = belfry_h
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.20, 0.20, post_h),
                               location=(cx + sx * half, cy + sy * half,
                                         belf_z + post_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    for sy in (-1.0, 1.0):
        create_beveled_box(bm, size=(size + 0.2, 0.14, 0.16),
                           location=(cx, cy + sy * half, belf_z + 0.30),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_beveled_box(bm, size=(size + 0.2, 0.14, 0.16),
                           location=(cx, cy + sy * half, belf_z + post_h - 0.16),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    for sx in (-1.0, 1.0):
        create_beveled_box(bm, size=(0.14, size + 0.2, 0.16),
                           location=(cx + sx * half, cy, belf_z + 0.30),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_beveled_box(bm, size=(0.14, size + 0.2, 0.16),
                           location=(cx + sx * half, cy, belf_z + post_h - 0.16),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

    # Hung bell + yoke.
    bell_top = belf_z + post_h - 0.20
    create_cylinder(bm, radius=0.03, height=0.40, segments=6,
                    location=(cx, cy, bell_top - 0.20), mat_index=MAT_INDEX_IRON)
    create_cone(bm, radius1=0.26, radius2=0.11, height=0.46, segments=12,
                location=(cx, cy, bell_top - 0.62), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.055, height=0.09, segments=8,
                    location=(cx, cy, bell_top - 0.90), mat_index=MAT_INDEX_IRON)

    plate_z = belf_z + post_h
    create_beveled_box(bm, size=(size + 0.5, size + 0.5, 0.18),
                       location=(cx, cy, plate_z + 0.09),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    spire_base = plate_z + 0.18
    spire_h = max(2.6, size * 1.7 + 1.4)
    build_square_spire_roof(bm, cx, cy, spire_base, half + 0.42, spire_h)
    cross_z = spire_base + spire_h + 0.65
    create_cylinder(bm, radius=0.035, height=0.55, segments=6,
                    location=(cx, cy, cross_z - 0.28), mat_index=MAT_INDEX_IRON)
    create_beveled_box(bm, size=(0.46, 0.05, 0.06),
                       location=(cx, cy, cross_z + 0.02),
                       mat_index=MAT_INDEX_IRON, bevel_amount=0.004)


def build_rose_window(bm, center, normal_axis, radius=0.72):
    """A decorative wheel window: stone ring, glowing glass and iron mullions.

    Built in a local frame whose wall normal is -Y, then yawed into place, so
    one definition serves every facade.
    """
    cx, cy, cz = center
    rot = ((math.pi * 0.5, 0.0, 0.0) if normal_axis in ('-Y', '+Y')
           else (0.0, math.pi * 0.5, 0.0))
    yaw = {'-Y': 0.0, '+Y': math.pi, '-X': math.pi * 0.5, '+X': -math.pi * 0.5}.get(
        normal_axis, 0.0)
    tr = Matrix.Translation((cx, cy, cz)) @ Matrix.Rotation(yaw, 4, 'Z')

    create_cylinder(bm, radius=radius, height=0.05, segments=24,
                    location=(0.0, 0.0, 0.0), rotation=(math.pi * 0.5, 0.0, 0.0),
                    mat_index=MAT_INDEX_GLASS, transform_matrix=tr)
    create_torus_ring(bm, location=(cx, cy, cz), rotation=rot,
                      major_radius=radius + 0.06, minor_radius=0.10,
                      major_segments=24, minor_segments=7,
                      mat_index=MAT_INDEX_CUT_STONE)
    bar = (radius * 1.7, 0.06, 0.05)
    for angle in (0.0, math.pi * 0.5, math.pi * 0.25, -math.pi * 0.25):
        create_box(bm, size=bar, location=(0.0, 0.0, 0.0),
                   rotation=(0.0, angle, 0.0), mat_index=MAT_INDEX_IRON,
                   transform_matrix=tr)
    create_cylinder(bm, radius=0.09, height=0.11, segments=10,
                    location=(0.0, 0.0, 0.0), rotation=(math.pi * 0.5, 0.0, 0.0),
                    mat_index=MAT_INDEX_IRON, transform_matrix=tr)


def build_chapel_kit(bm, props, ctx, tier):
    """Attach the chancel apse, campanile, rose window and wall lanterns."""
    base_hx = ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    wall_t = ctx.wall_t
    eave_z = ctx.found_h + ctx.num_floors * ctx.floor_h
    roof_h = getattr(props, 'roof_height', 3.2)
    overhang = getattr(props, 'roof_overhang', 0.8)

    # 1. Half-round chancel on the back wall (open to the nave, never inside it).
    apse_r = max(1.8, min(3.2, ctx.base_w * 0.32))
    build_chapel_apse(bm, 0.0, base_hy, 0.0, eave_z, apse_r, wall_t, tier,
                      ctx.seed)

    # 2. Free-standing campanile in front of the corner, clear of the roof eave.
    t_size = 2.4
    t_cx = base_hx - t_size * 0.5 - 0.2
    t_cy = -base_hy - overhang - t_size * 0.5 - 0.1
    t_top = eave_z + roof_h + 2.4
    build_bell_tower(bm, t_cx, t_cy, 0.0, t_size, t_top, tier, ctx.seed + 11)

    # 3. Rose window high in the front gable (clear of every wall window).
    rose_y = ctx.main_door_yf - 0.03
    rose_z = eave_z + roof_h * 0.30
    build_rose_window(bm, (ctx.main_door_cx, rose_y, rose_z), '-Y',
                      radius=min(0.78, ctx.base_w * 0.15))

    # 4. Forged wall lanterns flanking the entrance (reuses the hospitality fitment).
    door_half = getattr(props, 'door_width', 1.2) * 0.5
    lan_z = ctx.found_h + 2.35
    lan_y = ctx.main_door_yf - wall_t * 0.5 - 0.07
    for s in (-1.0, 1.0):
        build_hanging_lantern(bm, ctx.main_door_cx + s * (door_half + 0.75),
                              lan_y, z_top=lan_z, arm_ang=-math.pi * 0.5,
                              arm_len=0.62, scale=0.95)
