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
from ..walls import build_wall_with_opening, create_curved_corbel
from ..uv_utils import apply_roof_shingle_uvs, map_planar_faces
from .tower import build_square_spire_roof
from .lighting import build_hanging_lantern


def build_chapel_apse(bm, cx, cy, z_ground, z_top, radius, wall_t, tier, seed, found_h=0.0):
    """A half-round chancel apse attached to the nave's rear wall.

    The drum's base diameter lies on the wall line ``cy`` and only the outward
    half is built, so nothing ever appears inside the nave. It is open to the
    nave at the chord (the nave cuts its own rear portal), and a half-cone of
    correctly-UV'd shingles caps it. Vertical timber seam pillars with cut-stone
    plinths, capitals, and carved corbel brackets frame each facet.
    """
    segments = 8
    d_ang = 2.0 * math.pi / segments
    offset = 0.0                     # facets 0-3 span 0..180 deg (the +Y half)
    indices = [0, 1, 2, 3]
    wall_mat = tier_wall_mat(tier)
    ccx, ccy = cx, cy

    # Half-disc floor level with the nave floor (found_h + 0.05) - zero height difference!
    z_floor = (found_h + 0.05) if found_h > 0.05 else (z_ground + 0.06)
    center_v = bm.verts.new((ccx, ccy, z_floor))
    floor_faces = []
    for k in indices:
        p1, p2, _n, _m = segment_frame(radius, k, segments, offset)
        a = bm.verts.new((ccx + p1[0], ccy + p1[1], z_floor))
        b = bm.verts.new((ccx + p2[0], ccy + p2[1], z_floor))
        f = bm.faces.new([center_v, a, b])
        f.material_index = MAT_INDEX_FLOOR
        floor_faces.append(f)
    map_planar_faces(bm, floor_faces, scale=0.5, axis=2)

    facet_len = 2.0 * radius * math.sin(d_ang * 0.5)

    # 1. Stone foundation drum underneath apse floor (0.0 to found_h)
    if found_h > 0.05:
        found_r = radius + 0.06
        wall_ring(bm, found_r, z_ground, found_h, wall_t + 0.06, segments, offset,
                  {}, MAT_INDEX_STONE, tier=tier, seed=seed, indices=indices,
                  center=(ccx, ccy))
        for k in indices:
            _p1, _p2, nrm, mid = segment_frame(found_r + 0.03, k, segments, offset)
            c_len = 2.0 * (found_r + 0.03) * math.sin(d_ang * 0.5)
            create_beveled_box(
                bm, size=(c_len + 0.08, 0.12, 0.08),
                location=(ccx + mid[0], ccy + mid[1], found_h + 0.01),
                rotation=(0.0, 0.0, math.atan2(nrm.y, nrm.x) + math.pi * 0.5),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010
            )

    # 2. Apse drum walls above foundation
    wall_base_z = found_h if found_h > 0.05 else z_ground
    wall_h = z_top - wall_base_z
    win_w = min(0.9, facet_len - 0.55)
    win_h = min(1.7, wall_h * 0.55)
    win_cz = wall_base_z + wall_h * 0.52
    stone_top = min(wall_base_z + 0.90, z_top - 0.40)

    openings = {}
    win_specs = []
    for k in indices:
        _p1, _p2, nrm, mid = segment_frame(radius, k, segments, offset)
        u_mid = facet_len * 0.5
        openings[k] = [{'u_start': u_mid - win_w * 0.5, 'u_end': u_mid + win_w * 0.5,
                        'z_start': win_cz - win_h * 0.5, 'z_end': win_cz + win_h * 0.5}]
        win_specs.append(((ccx + mid[0], ccy + mid[1], win_cz), (nrm.x, nrm.y)))

    wall_ring(bm, radius, wall_base_z, stone_top, wall_t, segments, offset,
              openings, MAT_INDEX_STONE, tier=tier, seed=seed, indices=indices,
              center=(ccx, ccy))
    wall_ring(bm, radius, stone_top, z_top, wall_t, segments, offset,
              openings, wall_mat, tier=tier, seed=seed + 7, indices=indices,
              center=(ccx, ccy))
    for center, nv in win_specs:
        build_window_assembly(bm, center=center, size=(win_w, win_h),
                              wall_thickness=wall_t, normal_axis=nv,
                              has_shutters=False)

    # 3. Vertical timber seam pillars between wall segments (Warcraft style)
    h_apse = z_top - z_ground
    p_w = 0.24
    p_d = 0.26
    foot_h = min(0.44, h_apse * 0.15)
    collar_h = min(0.24, h_apse * 0.10)
    main_h = h_apse - foot_h
    post_r = radius + wall_t * 0.42

    for k in range(5):  # 5 seams for the 4 facets: 0..4 (0 to 180 deg)
        ang = k * d_ang + offset
        ca, sa = math.cos(ang), math.sin(ang)
        px = ccx + post_r * ca
        py = ccy + post_r * sa

        # 1. Beveled Plinth Foot Block (Cut Stone)
        create_beveled_box(
            bm, size=(p_w * 1.25, p_d * 1.20, foot_h),
            location=(px, py, z_ground + foot_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.014
        )

        # 2. Main Vertical Timber Pillar
        create_beveled_box(
            bm, size=(p_w, p_d, main_h),
            location=(px, py, z_ground + foot_h + main_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014
        )

        # 3. Capital / Collar at top under eave
        create_beveled_box(
            bm, size=(p_w * 1.20, p_d * 1.15, collar_h),
            location=(px, py, z_top - collar_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )

        # 4. Timber corbel bracket supporting the eave
        create_curved_corbel(
            bm, loc=Vector((ccx + (radius + 0.02) * ca, ccy + (radius + 0.02) * sa, z_top)),
            facing_dir=(ca, sa, 0.0),
            width=p_w * 0.85, depth=0.30, height=0.42,
            mat_index=MAT_INDEX_TIMBER
        )

    # Half-cone shingle roof, apex above the wall-line centre.
    roof_r = radius + 0.24
    roof_h = max(1.9, radius * 0.9)
    apex = bm.verts.new((ccx, ccy, z_top + roof_h))
    roof_faces = []
    for k in indices:
        a1 = k * d_ang + offset
        a2 = (k + 1) * d_ang + offset
        q1 = bm.verts.new((ccx + roof_r * math.cos(a1),
                           ccy + roof_r * math.sin(a1), z_top))
        q2 = bm.verts.new((ccx + roof_r * math.cos(a2),
                           ccy + roof_r * math.sin(a2), z_top))
        f = bm.faces.new([q1, q2, apex])
        f.material_index = MAT_INDEX_SHINGLES
        f.tag = True
        roof_faces.append(f)
        create_beveled_box(
            bm, size=(facet_len + 0.2, 0.10, 0.10),
            location=((q1.co.x + q2.co.x) * 0.5, (q1.co.y + q2.co.y) * 0.5,
                      z_top + 0.03),
            rotation=(0.0, 0.0, (a1 + a2) * 0.5 + math.pi * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    apply_roof_shingle_uvs(bm, roof_faces)
    create_cylinder(bm, radius=0.035, height=0.55, segments=6,
                    location=(ccx, ccy, z_top + roof_h + 0.24),
                    mat_index=MAT_INDEX_IRON)


def _square_shaft(bm, cx, cy, size, wall_t, z0, z1, tier, seed,
                  openings_per_face, z_split=None):
    """A square tower shaft from four wall facets with per-face openings."""
    half = size * 0.5
    inset = wall_t * 0.5
    lo = half - inset                 # trim the faces so corners never overlap
    faces = {
        'front': ((cx - lo, cy - half + inset), (cx + lo, cy - half + inset), (0.0, -1.0)),
        'back': ((cx - lo, cy + half - inset), (cx + lo, cy + half - inset), (0.0, 1.0)),
        'left': ((cx - half + inset, cy - lo), (cx - half + inset, cy + lo), (-1.0, 0.0)),
        'right': ((cx + half - inset, cy - lo), (cx + half - inset, cy + lo), (1.0, 0.0)),
    }
    # Corner posts close the trimmed corner notches cleanly.
    corner_mat = MAT_INDEX_TIMBER if tier == 'TIER_1' else MAT_INDEX_CUT_STONE
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(wall_t + 0.08, wall_t + 0.08, z1 - z0),
                               location=(cx + sx * lo, cy + sy * lo, (z0 + z1) * 0.5),
                               mat_index=corner_mat, bevel_amount=0.012)
    wall_mat = tier_wall_mat(tier)
    split_z = z_split if z_split is not None else min(z0 + size * 0.55, z1 - 0.4)
    for face, (p0, p1, nv) in faces.items():
        ops = openings_per_face.get(face, [])
        if split_z > z0 + 0.05:
            band_ops = [o for o in ops if o['z_end'] > z0 + 0.01 and o['z_start'] < split_z - 0.01]
            build_wall_with_opening(bm, p0, p1, z0, split_z, wall_t, band_ops,
                                    mat_ext=MAT_INDEX_STONE, normal_vec=nv,
                                    tier=tier, physical_siding=False, seed=seed)
        if z1 > split_z + 0.05:
            band_ops = [o for o in ops if o['z_end'] > split_z + 0.01 and o['z_start'] < z1 - 0.01]
            build_wall_with_opening(bm, p0, p1, split_z, z1, wall_t, band_ops,
                                    mat_ext=wall_mat, normal_vec=nv,
                                    tier=tier, physical_siding=False, seed=seed + 3)


def build_bell_tower(bm, cx, cy, z_base, size, shaft_top, tier, seed, ridge_z=None):
    """A chapel rooftop belfry / steeple sitting astride the roof ridge.

    Simplified without base plate / foundation boxes since it is mounted
    in the attic/roof deck. Features a single clean front lancet window
    above the roof ridge, cut-stone cornice, open timber belfry with hung
    iron bell, square spire roof and iron cross.
    """
    wall_t = 0.32
    half = size * 0.5

    if ridge_z is None:
        ridge_z = z_base + (shaft_top - z_base) * 0.75

    # Single front lancet window opening above the roof ridge
    win_w = min(0.48, size * 0.26)
    win_h = min(1.05, max(0.60, (shaft_top - ridge_z) * 0.62))
    w_cz = ridge_z + (shaft_top - ridge_z) * 0.52

    c = (size - wall_t) * 0.5
    openings = {
        'front': [{
            'u_start': c - win_w * 0.5,
            'u_end': c + win_w * 0.5,
            'z_start': w_cz - win_h * 0.5,
            'z_end': w_cz + win_h * 0.5,
        }],
        'back': [],
        'left': [],
        'right': [],
    }

    # Tower shaft running from attic level z_base to shaft_top
    _square_shaft(bm, cx, cy, size, wall_t, z_base, shaft_top, tier, seed,
                  openings, z_split=ridge_z)

    # Front window assembly
    build_window_assembly(
        bm,
        center=(cx, cy - half + wall_t * 0.5, w_cz),
        size=(win_w, win_h),
        wall_thickness=wall_t,
        normal_axis=(0.0, -1.0),
        has_shutters=False,
    )

    # Cut-stone cornice molding atop the shaft
    create_beveled_box(bm, size=(size + 0.36, size + 0.36, 0.16),
                       location=(cx, cy, shaft_top + 0.08),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.016)

    # Open belfry: four corner timber posts, sill & head rails
    belf_z = shaft_top + 0.16
    belfry_h = 1.70
    post_w = 0.18
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(post_w, post_w, belfry_h),
                               location=(cx + sx * half, cy + sy * half,
                                         belf_z + belfry_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    for sy in (-1.0, 1.0):
        create_beveled_box(bm, size=(size + 0.16, 0.12, 0.14),
                            location=(cx, cy + sy * half, belf_z + 0.20),
                            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_beveled_box(bm, size=(size + 0.16, 0.12, 0.14),
                            location=(cx, cy + sy * half, belf_z + belfry_h - 0.14),
                            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    for sx in (-1.0, 1.0):
        create_beveled_box(bm, size=(0.12, size + 0.16, 0.14),
                            location=(cx + sx * half, cy, belf_z + 0.20),
                            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_beveled_box(bm, size=(0.12, size + 0.16, 0.14),
                            location=(cx + sx * half, cy, belf_z + belfry_h - 0.14),
                            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

    # Hung bell + yoke inside belfry
    bell_top = belf_z + belfry_h - 0.18
    create_cylinder(bm, radius=0.03, height=0.36, segments=6,
                    location=(cx, cy, bell_top - 0.16), mat_index=MAT_INDEX_IRON)
    create_cone(bm, radius1=0.24, radius2=0.10, height=0.42, segments=12,
                location=(cx, cy, bell_top - 0.54), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.05, height=0.08, segments=8,
                    location=(cx, cy, bell_top - 0.79), mat_index=MAT_INDEX_IRON)

    # Top plate / belfry cornice
    plate_z = belf_z + belfry_h
    create_beveled_box(bm, size=(size + 0.44, size + 0.44, 0.16),
                       location=(cx, cy, plate_z + 0.08),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)

    # Square spire roof
    spire_base = plate_z + 0.16
    spire_h = max(2.8, size * 1.6 + 0.8)
    build_square_spire_roof(bm, cx, cy, spire_base, half + 0.34, spire_h)

    # Iron cross atop spire
    cross_z = spire_base + spire_h + 0.55
    create_cylinder(bm, radius=0.03, height=0.50, segments=6,
                    location=(cx, cy, cross_z - 0.25), mat_index=MAT_INDEX_IRON)
    create_beveled_box(bm, size=(0.42, 0.05, 0.05),
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
    """Attach the chancel apse, rooftop bell tower, rose window and wall lanterns."""
    base_hx = ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    wall_t = ctx.wall_t
    eave_z = ctx.found_h + ctx.num_floors * ctx.floor_h
    roof_h = getattr(props, 'roof_height', 3.2)
    ridge_z = eave_z + roof_h

    # 1. Half-round chancel on the back wall (open to the nave, never inside it).
    apse_r = max(1.8, min(3.2, ctx.base_w * 0.32))
    build_chapel_apse(bm, 0.0, base_hy, 0.0, eave_z, apse_r, wall_t, tier,
                      ctx.seed, found_h=ctx.found_h)

    # 2. Rooftop bell tower perched astride the main building roof ridge towards the back.
    t_size = max(1.8, min(2.2, ctx.base_w * 0.18))
    t_cx = 0.0
    t_cy = base_hy - t_size * 0.5 - 1.2
    shaft_top = ridge_z + 1.85
    build_bell_tower(bm, t_cx, t_cy, eave_z, t_size, shaft_top, tier, ctx.seed + 11,
                     ridge_z=ridge_z)

    # 3. Rose window high in the front gable (clear of every wall window).
    rose_y = ctx.main_door_yf - 0.03
    rose_z = eave_z + roof_h * 0.30
    build_rose_window(bm, (ctx.main_door_cx, rose_y, rose_z), '-Y',
                      radius=min(0.78, ctx.base_w * 0.15))

    # 4. Forged wall lanterns flanking the entrance (reuses the hospitality fitment).
    door_half = getattr(props, 'door_width', 1.2) * 0.5
    lan_z = ctx.found_h + 2.35
    lan_y = ctx.main_door_yf - wall_t * 0.5
    for s in (-1.0, 1.0):
        build_hanging_lantern(bm, ctx.main_door_cx + s * (door_half + 0.75),
                              lan_y, z_top=lan_z, arm_ang=-math.pi * 0.5,
                              arm_len=0.62, scale=0.95)
