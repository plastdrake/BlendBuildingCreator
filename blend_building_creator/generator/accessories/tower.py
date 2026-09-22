"""Reusable tower accessories: clock/belfry tower, square corner turret,
roof-mounted clock spire, plus the shared square-spire and clock-face fittings.

These were previously bundled as "civic landmarks for town halls", but nothing
here is town-hall specific - the dispatcher mounts them on any footprint.
"""

import math
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
)
from ..uv_utils import apply_roof_shingle_uvs
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER_FRAME,
    MAT_INDEX_DOOR, MAT_INDEX_CUT_STONE, MAT_INDEX_CLOCK_FACE,
    MAT_INDEX_FLOOR,
)
from ..openings import build_window_assembly
from ..walls import build_wall_with_opening
from ..style import tier_wall_mat


def build_square_spire_roof(bm, cx, cy, z_base, half, height, eave=0.20):
    """Axis-aligned 4-facet square spire roof (a regular pyramid, no cylinder),
    with per-face shingle UVs, a square timber eave board and an iron finial.

    Shared by the civic clock tower, the corner turret and the chapel bell
    tower (DRY): every square spire in the add-on comes from this one builder.
    """
    # Lift the roof 10cm off the plate below so no faces end up coplanar.
    z_roof = z_base + 0.10
    apex_z = z_roof + height
    R = max(0.12, half) * math.sqrt(2.0)
    faces = create_cone(
        bm, radius1=R, radius2=0.06, height=height, segments=4,
        location=(cx, cy, z_roof + height * 0.5),
        rotation=(0.0, 0.0, math.pi * 0.25),
        mat_index=MAT_INDEX_SHINGLES,
    )
    # World-aligned shingle UVs (axis-aligned + correctly oriented + engine size).
    apply_roof_shingle_uvs(bm, faces)
    # Square eave board under the spire
    create_beveled_box(bm, size=(half * 2.0 + eave, half * 2.0 + eave, 0.14),
                       location=(cx, cy, z_base + 0.05),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    # Iron finial needle + ball
    create_cylinder(bm, radius=0.035, height=0.9, segments=6,
                    location=(cx, cy, apex_z + 0.45), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.085, height=0.12, segments=8,
                    location=(cx, cy, apex_z + 0.62), mat_index=MAT_INDEX_IRON)


def _clock_face(bm, center, facing, radius=0.85, frame=True):
    """Recessed dial with optional timber surround, tick ring, hands and boss.

    Facing: 'front' (-Y), 'back' (+Y), 'left' (-X), 'right' (+X).

    Every layer is stacked PROUD of the wall along the face normal so the iron
    rim, dial disc, ticks and hands all sit in front of the wooden backer
    instead of intersecting it.
    """
    cx, cy, cz = center
    # Cylinder axis must point along the face normal:
    # front/back -> axis Y (rotate 90 deg about X), sides -> axis X (rotate about Y).
    rot = (1.5707963, 0.0, 0.0) if facing in ('front', 'back') else (0.0, 1.5707963, 0.0)

    if facing == 'front':
        off = (0.0, -1.0)
    elif facing == 'back':
        off = (0.0, 1.0)
    elif facing == 'left':
        off = (-1.0, 0.0)
    else:
        off = (1.0, 0.0)
    ox, oy = off
    front_dial = facing in ('front', 'back')

    def at(d):
        return (cx + ox * d, cy + oy * d, cz)

    # Surround backboard (square, slightly larger than dial) - sunk slightly into the wall
    fw = radius * 2.0 + 0.30
    if frame:
        if front_dial:
            create_beveled_box(bm, size=(fw, 0.10, fw), location=at(-0.02),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.015)
        else:
            create_beveled_box(bm, size=(0.10, fw, fw), location=at(-0.02),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.015)
    # Iron rim sits proud of the backer
    create_cylinder(bm, radius=radius + 0.12, height=0.08, segments=24,
                    location=at(0.09), rotation=rot, mat_index=MAT_INDEX_IRON)
    # White dial disc sits in front of the iron rim
    create_cylinder(bm, radius=radius, height=0.07, segments=24,
                    location=at(0.14), rotation=rot, mat_index=MAT_INDEX_CLOCK_FACE)

    dial_d = 0.180
    dx, dy, dz = at(dial_d)

    # 12 tick marks around the dial face.
    # Front/back dials lie in the XZ plane and must rotate about Y;
    # side dials lie in the YZ plane and must rotate about X.
    k = radius / 0.85
    for h in range(12):
        ang = h * math.pi / 6.0
        radial = radius * 0.80
        big = (h % 3 == 0)
        tw, th = (0.075 * k, 0.21 * k) if big else (0.045 * k, 0.12 * k)
        if front_dial:
            create_box(bm, size=(tw, 0.035 * k, th),
                       location=(dx + math.sin(ang) * radial, dy, dz + math.cos(ang) * radial),
                       rotation=(0.0, ang, 0.0),
                       mat_index=MAT_INDEX_IRON)
        else:
            create_box(bm, size=(0.035 * k, tw, th),
                       location=(dx, dy + math.sin(ang) * radial, dz + math.cos(ang) * radial),
                       rotation=(-ang, 0.0, 0.0),
                       mat_index=MAT_INDEX_IRON)
    # Hands (10:09 read): hour + minute offset radially + center boss
    hour_ang = math.radians(60.0)
    min_ang = math.radians(305.0)
    if front_dial:
        for (ha, hl, hw) in ((hour_ang, 0.46, 0.10), (min_ang, 0.66, 0.075)):
            orad = hl * 0.5
            create_beveled_box(bm, size=(hw * k, 0.04 * k, hl * k),
                               location=(dx + math.sin(ha) * orad * k, dy + oy * 0.012,
                                         dz + math.cos(ha) * orad * k),
                               rotation=(0.0, ha, 0.0),
                               mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
        create_cylinder(bm, radius=0.085 * k, height=0.07 * k, segments=10,
                        location=at(dial_d + 0.025), rotation=rot,
                        mat_index=MAT_INDEX_IRON)
    else:
        for (ha, hl, hw) in ((hour_ang, 0.46, 0.10), (min_ang, 0.66, 0.075)):
            orad = hl * 0.5
            create_beveled_box(bm, size=(0.04 * k, hw * k, hl * k),
                               location=(dx + ox * 0.012, dy + math.sin(ha) * orad * k,
                                         dz + math.cos(ha) * orad * k),
                               rotation=(-ha, 0.0, 0.0),
                               mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
        create_cylinder(bm, radius=0.085 * k, height=0.07 * k, segments=10,
                        location=at(dial_d + 0.025), rotation=rot,
                        mat_index=MAT_INDEX_IRON)


def build_clock_tower(bm, cx, cy, z_ground=0.0, size=3.0, shaft_top_z=10.0,
                      tier='TIER_3', roof_flare=0.38, floor_levels=None,
                      front_y=None, arch_passage=False, deck_portal_z=None):
    """Attached civic clock/belfry tower integrated into the front corner.

    floor_levels: list of deck heights so string courses line up with the
    main building storeys. front_y: wing front plane to flush the tower to.
    arch_passage: open a walk-through gate tunnel (front-back) through the base.
    deck_portal_z: (z0, z1) opening cut into the back wall so an entrance ramp
    can climb from the gate up onto the adjacent rampart walk.
    """
    s = max(2.4, min(4.2, size))
    half = s * 0.5
    # Match the hall's material language instead of one monotone stone block:
    # a lower ashlar stone stage carries a tier-material (stucco / plank) upper
    # shaft, tied together with cut-stone quoins, bands and string courses.
    wall_mat = tier_wall_mat(tier)
    # Stone stage (index 0) receives the engine's clean world-space masonry UVs,
    # instead of the streaky default box UVs wood/plaster would get.
    stage_mat = MAT_INDEX_STONE

    if arch_passage:
        # Gate base: corner piers + open tunnel along Y, arch trims front/back
        tunnel_w = min(2.2, s - 1.0)
        arch_top = z_ground + 3.1
        strip_w = (s + 0.9 - tunnel_w) * 0.5
        for px in (-1.0, 1.0):
            create_beveled_box(bm, size=(strip_w, s + 0.9, 0.30),
                               location=(cx + px * (tunnel_w * 0.5 + strip_w * 0.5), cy, z_ground + 0.15),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
        for px in (-1.0, 1.0):
            for py in (-1.0, 1.0):
                create_beveled_box(bm, size=(0.62, 0.62, arch_top - z_ground),
                                   location=(cx + px * (half - 0.25), cy + py * (half - 0.25),
                                             z_ground + (arch_top - z_ground) * 0.5),
                                   mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        # Side walls between piers (tunnel stays open front-back)
        for px in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.24, s - 0.9, arch_top - z_ground - 0.3),
                               location=(cx + px * (half - 0.12), cy, z_ground + (arch_top - z_ground) * 0.5),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
        # Timber gate frame: jamb posts set into the piers, a lintel beam across
        # the opening and 45-degree knee braces tying each jamb to the lintel so
        # nothing floats in the middle of the tunnel.
        jamb_h = arch_top - z_ground
        frame_d = 0.18
        embed = 0.06
        br_len = min(0.95, tunnel_w * 0.55)
        br_ang = math.radians(48.0)
        for py in (-1.0, 1.0):
            fy = cy + py * (half + 0.015)
            for ax in (-1.0, 1.0):
                px = cx + ax * (tunnel_w * 0.5 + frame_d * 0.5 - embed)
                create_beveled_box(bm, size=(frame_d, 0.26, jamb_h),
                                   location=(px, fy, z_ground + jamb_h * 0.5),
                                   mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
                bx = px - ax * (frame_d * 0.5 + br_len * 0.5 * math.cos(br_ang) - embed)
                bz = arch_top - 0.30 - br_len * 0.5 * math.sin(br_ang)
                create_beveled_box(bm, size=(br_len, 0.16, 0.16),
                                   location=(bx, fy, bz),
                                   rotation=(0.0, ax * br_ang, 0.0),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
            create_beveled_box(bm, size=(tunnel_w + frame_d * 2.0 - embed * 2.0, 0.28, 0.30),
                               location=(cx, fy, arch_top - 0.15),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014)
            create_beveled_box(bm, size=(s, 0.2, shaft_top_z - arch_top if (shaft_top_z - arch_top) < 1.2 else 1.0),
                               location=(cx, fy, arch_top + 0.45),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
        base_z = arch_top
    else:
        # Two-step stepped plinth grounding the tower
        create_beveled_box(bm, size=(s + 0.9, s + 0.9, 0.30), location=(cx, cy, z_ground + 0.15),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
        create_beveled_box(bm, size=(s + 0.5, s + 0.5, 0.45), location=(cx, cy, z_ground + 0.45),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.025)
        base_z = z_ground + 0.60

    # Shaft: hollow shell so every window is a real cut-out instead of a casing
    # sunk into a solid block. Lower ashlar stone stage + tier-material upper
    # stage, tied together with cut-stone quoins, bands and string courses.
    shaft_h = max(2.0, shaft_top_z - base_z)
    stone_h = min(shaft_h * 0.55, max(2.4, shaft_h * 0.42))
    shaft_t = 0.44
    levels = list(floor_levels) if floor_levels else [
        base_z + shaft_h * 0.4, base_z + shaft_h * 0.68]

    # Window schedule: alternate the faces down the shaft so no side is blank.
    wins = []
    for i, fz in enumerate(levels):
        wz = fz + 0.90
        if wz > shaft_top_z - 0.80:
            continue
        # Keep the gate tunnel mouth clear when an arch passage runs front-back.
        if arch_passage and wz < base_z + 1.0:
            continue
        wins.append(('front' if i % 2 == 0 else 'right', wz))
    _wz0 = base_z + stone_h + 0.95
    if _wz0 < shaft_top_z - 0.85:
        wins.append(('left', _wz0))
        wins.append(('back', _wz0))

    _ww, _wh = 0.70, 1.10

    def _shaft_face(face):
        """(p_start, p_end, outward normal) for a shaft side centre-line."""
        if face == 'front':
            return ((cx - half, cy - half + shaft_t * 0.5),
                    (cx + half, cy - half + shaft_t * 0.5), (0.0, -1.0))
        if face == 'back':
            return ((cx - half, cy + half - shaft_t * 0.5),
                    (cx + half, cy + half - shaft_t * 0.5), (0.0, 1.0))
        if face == 'left':
            return ((cx - half + shaft_t * 0.5, cy - half),
                    (cx - half + shaft_t * 0.5, cy + half), (-1.0, 0.0))
        return ((cx + half - shaft_t * 0.5, cy - half),
                (cx + half - shaft_t * 0.5, cy + half), (1.0, 0.0))

    def _win_center(face, wz):
        if face == 'front':
            return (cx, cy - half + shaft_t * 0.5, wz), '-Y'
        if face == 'back':
            return (cx, cy + half - shaft_t * 0.5, wz), '+Y'
        if face == 'left':
            return (cx - half + shaft_t * 0.5, cy, wz), '-X'
        return (cx + half - shaft_t * 0.5, cy, wz), '+X'

    for face in ('front', 'back', 'left', 'right'):
        p0, p1, nv = _shaft_face(face)
        f_len = abs(p1[0] - p0[0]) + abs(p1[1] - p0[1])
        f_ops = [{'u_start': f_len * 0.5 - _ww * 0.5, 'u_end': f_len * 0.5 + _ww * 0.5,
                  'z_start': wz - _wh * 0.5, 'z_end': wz + _wh * 0.5}
                 for (f, wz) in wins if f == face]
        if face == 'back' and deck_portal_z is not None:
            _pz0 = max(base_z - 0.5, deck_portal_z[0])
            f_ops.append({'u_start': f_len * 0.5 - 0.85, 'u_end': f_len * 0.5 + 0.85,
                          'z_start': _pz0, 'z_end': deck_portal_z[1]})
        for (z0, z1, mat) in ((base_z, base_z + stone_h, MAT_INDEX_STONE),
                              (base_z + stone_h, shaft_top_z, wall_mat)):
            if z1 - z0 < 0.06:
                continue
            band_ops = [op for op in f_ops
                        if op['z_start'] < z1 - 0.01 and op['z_end'] > z0 + 0.01]
            build_wall_with_opening(bm, p0, p1, z0, z1, shaft_t, band_ops,
                                    mat_ext=mat, normal_vec=nv, tier=tier,
                                    physical_siding=False, seed=42)
        for (f, wz) in wins:
            if f != face:
                continue
            c, na = _win_center(face, wz)
            build_window_assembly(bm, center=c, size=(_ww, _wh),
                                  wall_thickness=shaft_t, normal_axis=na,
                                  has_shutters=False)
        if face == 'back' and deck_portal_z is not None:
            _fb = max(base_z - 0.5, deck_portal_z[0])
            _ft = deck_portal_z[1]
            _fy = cy + half - shaft_t * 0.5
            for _ax in (-1.0, 1.0):
                create_beveled_box(bm, size=(0.16, 0.30, _ft - _fb),
                                   location=(cx + _ax * 0.93, _fy, (_fb + _ft) * 0.5),
                                   mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
            create_beveled_box(bm, size=(2.02, 0.30, 0.20),
                               location=(cx, _fy, _ft + 0.10),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Interior floor decks so the shaft is not a bottomless well. (The old
    # cut-stone string-course boxes read as stone interior floors, so they are
    # gone; only the vertical quoins remain as exterior dressing.)
    for fz in levels:
        if base_z + 0.4 < fz < shaft_top_z - 0.2:
            create_box(bm, size=(s - shaft_t * 2.0, s - shaft_t * 2.0, 0.12),
                       location=(cx, cy, fz + 0.07), mat_index=MAT_INDEX_FLOOR)

    # Cut-stone corner quoins full height
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.26, 0.26, shaft_h),
                               location=(cx + sx * (half - 0.05), cy + sy * (half - 0.05),
                                         base_z + shaft_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)

    # Base doorway facing front (skipped when the arch tunnel passes through)
    if not arch_passage:
        door_fy = cy - half
        create_box(bm, size=(1.0, 0.14, 2.1), location=(cx, door_fy - 0.02, base_z + 1.05),
                   mat_index=MAT_INDEX_DOOR)
        create_beveled_box(bm, size=(1.24, 0.12, 0.16), location=(cx, door_fy - 0.02, base_z + 2.18),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        for dsx in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.14, 0.12, 2.2), location=(cx + dsx * 0.60, door_fy - 0.02, base_z + 1.10),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)

    # Clock stage: same footprint as shaft (no floating slab) + corner pilasters.
    # Tall enough that the dial + its surround never overlap the cornice above.
    stage_h = max(2.0, s * 0.68)
    stage_z = shaft_top_z + stage_h * 0.5
    create_beveled_box(bm, size=(s + 0.15, s + 0.15, stage_h), location=(cx, cy, stage_z),
                       mat_index=stage_mat, bevel_amount=0.02)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.26, 0.26, stage_h),
                               location=(cx + sx * (half - 0.02), cy + sy * (half - 0.02), stage_z),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    half_stage = (s + 0.15) * 0.5
    r = min(0.80 * (s / 3.0), half_stage - 0.30, (stage_h - 0.62) * 0.5)
    _clock_face(bm, (cx, cy - half_stage, stage_z), 'front', radius=r)
    _clock_face(bm, (cx, cy + half_stage, stage_z), 'back', radius=r)
    _clock_face(bm, (cx - half_stage, cy, stage_z), 'left', radius=r)
    _clock_face(bm, (cx + half_stage, cy, stage_z), 'right', radius=r)

    # Dentil cornice above dials
    corn_z = shaft_top_z + stage_h
    create_beveled_box(bm, size=(s + 0.55, s + 0.55, 0.20), location=(cx, cy, corn_z + 0.10),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    dent_n = 5
    for i in range(dent_n):
        t = -half + (i + 0.5) * (s / dent_n)
        for sy in (-1.0, 1.0):
            create_box(bm, size=(0.14, 0.14, 0.16),
                       location=(cx + t, cy + sy * (half + 0.22), corn_z - 0.05),
                       mat_index=MAT_INDEX_TIMBER_FRAME)
        for sx in (-1.0, 1.0):
            create_box(bm, size=(0.14, 0.14, 0.16),
                       location=(cx + sx * (half + 0.22), cy + t, corn_z - 0.05),
                       mat_index=MAT_INDEX_TIMBER_FRAME)

    # Open belfry: corner posts, sill rails, top plate, bell, cross braces
    post_h = 1.6
    belf_z = corn_z + 0.20
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.20, 0.20, post_h),
                               location=(cx + sx * half, cy + sy * half, belf_z + post_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    for sy in (-1.0, 1.0):
        create_beveled_box(bm, size=(s + 0.15, 0.14, 0.16),
                           location=(cx, cy + sy * half, belf_z + 0.35),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
    for sx in (-1.0, 1.0):
        create_beveled_box(bm, size=(0.14, s + 0.15, 0.16),
                           location=(cx + sx * half, cy, belf_z + 0.35),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
    create_beveled_box(bm, size=(0.12, 0.12, 1.1),
                       location=(cx, cy, belf_z + post_h - 0.35),
                       rotation=(0.0, 0.0, 0.785),
                       mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008)
    # Hung bell reaching up to the belfry plate (not a floating lump)
    create_cone(bm, radius1=0.34, radius2=0.13, height=0.60, segments=10,
                location=(cx, cy, belf_z + 1.0), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.05, height=0.42, segments=8,
                    location=(cx, cy, belf_z + 1.48), mat_index=MAT_INDEX_TIMBER)
    create_beveled_box(bm, size=(s + 0.55, s + 0.55, 0.18),
                       location=(cx, cy, belf_z + post_h + 0.09),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)

    # Square 4-facet spire roof (regular pyramid, no cylinder)
    spire_base = belf_z + post_h + 0.18
    build_square_spire_roof(bm, cx, cy, spire_base, half + 0.50, 3.1)


def build_roof_clock_spire(bm, cx, cy, z_base, scale=0.85, tier='TIER_3'):
    """Small roof-mounted spire turret with a clock stage (Tier 1/2 halls).

    Timber curb rooted deep into the roof, 4 small dials, open mini-belfry
    with bell, tall bell-cast spire and needle.
    """
    sc = max(0.6, min(1.6, scale))
    w = 1.05 * sc
    half = w * 0.5
    # Stone stage (index 0) gets the engine's clean world-space UVs.
    stage_mat = MAT_INDEX_STONE
    # Raise the clock stage clear of the roof surface so no dial is half-buried.
    lift = 0.85 * sc + 0.10
    z_stage0 = z_base + lift
    # Timber curb/skirt rooted down into the roof slope up to the clock stage
    curb_bot = z_base - 1.2 * sc
    curb_h = z_stage0 - curb_bot
    create_beveled_box(bm, size=(w + 0.30 * sc, w + 0.30 * sc, curb_h),
                       location=(cx, cy, (curb_bot + z_stage0) * 0.5),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02 * sc)
    # Clock stage with corner boards
    stage_h = 0.95 * sc
    stage_z = z_stage0 + stage_h * 0.5
    create_beveled_box(bm, size=(w, w, stage_h), location=(cx, cy, stage_z),
                       mat_index=stage_mat, bevel_amount=0.015 * sc)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.13 * sc, 0.13 * sc, stage_h),
                               location=(cx + sx * (half - 0.03 * sc), cy + sy * (half - 0.03 * sc), stage_z),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008 * sc)
    r = 0.30 * sc
    _clock_face(bm, (cx, cy - half, stage_z), 'front', radius=r, frame=False)
    _clock_face(bm, (cx, cy + half, stage_z), 'back', radius=r, frame=False)
    _clock_face(bm, (cx - half, cy, stage_z), 'left', radius=r, frame=False)
    _clock_face(bm, (cx + half, cy, stage_z), 'right', radius=r, frame=False)
    # Cornice + mini belfry with bell
    corn_z = z_stage0 + stage_h
    create_beveled_box(bm, size=(w + 0.30 * sc, w + 0.30 * sc, 0.12 * sc),
                       location=(cx, cy, corn_z + 0.06 * sc),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010 * sc)
    post_h = 1.05 * sc
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.10 * sc, 0.10 * sc, post_h),
                               location=(cx + sx * half * 0.85, cy + sy * half * 0.85,
                                         corn_z + 0.12 * sc + post_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008 * sc)
    plate_z = corn_z + 0.12 * sc + post_h
    create_beveled_box(bm, size=(w + 0.24 * sc, w + 0.24 * sc, 0.10 * sc),
                       location=(cx, cy, plate_z + 0.05 * sc),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010 * sc)
    # Hung bell: a long iron yoke drops from the top plate so the bell and clapper
    # swing clear of the belfry floor instead of standing on it.
    bell_top = plate_z - 0.06 * sc
    hanger_h = 0.48 * sc
    create_cylinder(bm, radius=0.03 * sc, height=hanger_h, segments=6,
                    location=(cx, cy, bell_top - hanger_h * 0.5), mat_index=MAT_INDEX_IRON)
    create_beveled_box(bm, size=(0.36 * sc, 0.11 * sc, 0.11 * sc),
                       location=(cx, cy, bell_top - hanger_h * 0.5),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008 * sc)
    bell_h = 0.34 * sc
    bell_shoulder = bell_top - hanger_h
    create_cone(bm, radius1=0.20 * sc, radius2=0.09 * sc, height=bell_h, segments=10,
                location=(cx, cy, bell_shoulder - bell_h * 0.5), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.045 * sc, height=0.10 * sc, segments=8,
                    location=(cx, cy, bell_shoulder - bell_h - 0.02 * sc), mat_index=MAT_INDEX_IRON)
    # Square 4-facet spire roof (regular pyramid, no cylinder)
    build_square_spire_roof(bm, cx, cy, plate_z + 0.10 * sc, half + 0.28 * sc, 2.5 * sc)


def build_corner_turret(bm, cx, cy, z_ground=0.0, half=1.35, wall_top_z=6.0,
                        tier='TIER_3', out_dir=(1.0, 0.0),
                        floor_levels=None, floor_h=3.0, main_wall_top=None,
                        attach_tuck=0.32, plank_direction='HORIZONTAL', seed=42):
    """Square corner tower bolted onto the outside of the hall, annex-style.

    out_dir is the axis the tower projects along; the opposite side (toward the
    hall wall) is left open and gets a doorway per storey cut into that wall.
    The tower is hollow with real window cut-outs on its three exposed faces and
    a floor slab per main level, capped with a square shingled spire. Works for
    both side-wall and back-wall mounts.
    """
    wall_mat = tier_wall_mat(tier)
    t = 0.34
    levels = list(floor_levels) if floor_levels else [z_ground + floor_h, z_ground + 2.0 * floor_h]
    ox, oy = out_dir
    px, py = -oy, ox                       # width (perpendicular) direction

    def pt(d_out, d_perp):
        return (cx + ox * d_out + px * d_perp, cy + oy * d_out + py * d_perp)

    # Stepped stone root flush with the ground floor.
    plinth_top = max(z_ground + 0.55, min(z_ground + 1.30, (levels[0] if levels else z_ground + 0.9)))
    step0 = min(0.30, (plinth_top - z_ground) * 0.55)
    create_beveled_box(bm, size=(half * 2.0 + 0.72, half * 2.0 + 0.72, step0),
                       location=(cx, cy, z_ground + step0 * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    if plinth_top - step0 - z_ground > 0.06:
        h1 = plinth_top - step0 - z_ground
        create_beveled_box(bm, size=(half * 2.0 + 0.40, half * 2.0 + 0.40, h1),
                           location=(cx, cy, z_ground + step0 + h1 * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.025)
    # No cut-stone cap slab here: it sat coplanar with the ground storey floor
    # and read as an extra stone floor inside the tower.
    shaft_base = plinth_top
    shaft_h = max(1.5, wall_top_z - shaft_base)

    o_line = half - t * 0.5
    i_line = -(half - t * 0.5)
    reach = -half - attach_tuck

    # (p_start, p_end, normal, z_from). The open (inner) side only gets a wall
    # above the eave, where the hall wall/gable no longer backs the tower.
    face_defs = [
        (pt(o_line, -half), pt(o_line, half), (ox, oy), shaft_base),
        (pt(reach, o_line), pt(half, o_line), (px, py), shaft_base),
        (pt(reach, -o_line), pt(half, -o_line), (-px, -py), shaft_base),
    ]
    if main_wall_top is not None:
        face_defs.append((pt(i_line, -half), pt(i_line, half), (-ox, -oy), main_wall_top))

    ww = 0.72
    wh = min(1.15, floor_h * 0.46)
    stone_top = min(wall_top_z - 0.50, (levels[1] if len(levels) > 1 else shaft_base + floor_h) + 0.90)
    # Extra high windows above the eave - the tall shaft would otherwise be
    # blank up top. They need no interior decks, just openings and glazing.
    win_levels = list(levels)
    _wz = (levels[-1] if levels else shaft_base) + floor_h
    while _wz + wh * 0.5 < wall_top_z - 0.35:
        win_levels.append(_wz)
        _wz += floor_h

    for (p0, p1, nv, z_from) in face_defs:
        f_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if f_len < 0.30:
            continue
        z_lo = max(shaft_base, z_from)
        ux = (p1[0] - p0[0]) / f_len
        uy = (p1[1] - p0[1]) / f_len
        # Centre windows over the tower axis (not the tucked-in wall end).
        u_win = (cx - p0[0]) * ux + (cy - p0[1]) * uy
        ops, wins = [], []
        if z_from <= shaft_base + 0.01 and f_len >= ww + 0.60:
            for fz in win_levels:
                wz = fz + floor_h * 0.50
                if wz + wh * 0.5 > wall_top_z - 0.10 or wz - wh * 0.5 < shaft_base - 0.05:
                    continue
                ops.append({'u_start': u_win - ww * 0.5, 'u_end': u_win + ww * 0.5,
                            'z_start': wz - wh * 0.5, 'z_end': wz + wh * 0.5})
                wins.append((p0[0] + ux * u_win, p0[1] + uy * u_win, wz))
        bands = []
        if stone_top > z_lo + 0.06:
            bands.append((z_lo, min(stone_top, wall_top_z), MAT_INDEX_STONE))
        if wall_top_z > max(stone_top, z_lo) + 0.06:
            bands.append((max(stone_top, z_lo), wall_top_z, wall_mat))
        for (z0, z1, mat) in bands:
            band_ops = [op for op in ops
                        if op['z_start'] < z1 - 0.01 and op['z_end'] > z0 + 0.01]
            build_wall_with_opening(bm, p0, p1, z0, z1, t, band_ops, mat_ext=mat,
                                    normal_vec=nv, tier=tier, physical_siding=False,
                                    plank_direction=plank_direction, seed=seed)
        for (wx, wy, wz) in wins:
            build_window_assembly(bm, center=(wx, wy, wz), size=(ww, wh),
                                  wall_thickness=t, normal_axis=nv, has_shutters=True)

    # Floor decks on every storey (ground included), sized to sit inside the
    # shell so they never poke out through the tower walls.
    span = half * 2.0 - t + 0.04
    _sz = pt(-t * 0.5, 0.0)
    for fz in levels:
        if shaft_base - 0.01 <= fz < wall_top_z - 0.10:
            create_box(bm, size=(span, span, 0.12), location=(_sz[0], _sz[1], fz + 0.07),
                       mat_index=MAT_INDEX_FLOOR)

    # No timber collar at the eave: the tall shaft now runs straight through the
    # main roof, and the old skirt ring read as a stray slab mid-tower.
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.24, 0.24, shaft_h),
                               location=(cx + sx * (half - 0.05), cy + sy * (half - 0.05),
                                         shaft_base + shaft_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
    # Square shingled spire (uses the shared roof material + UVs). Seated just
    # above the shaft head so the roof never floats.
    _spire_base = wall_top_z + 0.02
    _spire_h = max(2.6, half * 1.9)
    build_square_spire_roof(bm, cx, cy, _spire_base, half + 0.40, _spire_h)
    # Iron finial needle above the spire
    create_cylinder(bm, radius=0.035, height=0.9, segments=6,
                    location=(cx, cy, _spire_base + _spire_h + 1.30),
                    mat_index=MAT_INDEX_IRON)
