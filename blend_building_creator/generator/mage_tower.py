"""Whimsical fantasy Mage Tower.

A tall, exaggerated round tower with a *half-open* interior: annular platforms
hug the wall, leaving a wide central shaft where two short switchback flights
(joined by landings/walkways) wind up - no spiral, nothing floating, and no two
flights ever overlap. Square annexes break the silhouette (a big entrance hall
at the base, hanging outcrops at height); each annex is cut through into the
tower and the shell skips any window that would sit inside one.

Big jettied overhangs, chunky pillars between wall bays and string courses keep
the shape toy-like rather than realistic, matching the reference art.

Shell/opening maths come from :mod:`generator.poly` (DRY); stairs from
:mod:`generator.interior`; annex roofs from :mod:`generator.roof.outcrop_roof`.
"""

import math

from .mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_box,
)
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR, MAT_INDEX_WOOD,
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_PLASTER_EXT,
    MAT_INDEX_GLASS, MAT_INDEX_IRON, MAT_INDEX_SHINGLES,
)
from .poly import segment_frame, ring_slab, corbel_ring, wall_ring
from .interior import build_straight_staircase
from .openings import build_door_assembly, build_front_steps, build_window_assembly
from .walls import build_wall_with_opening
from .style import tier_wall_mat
from .uv_utils import apply_roof_shingle_uvs
from .facade import get_facade_frame
from .roof.outcrop_roof import build_outcrop_gable_roof


SEGMENTS = 16
D_ANG = 2.0 * math.pi / SEGMENTS
OFFSET = -math.pi * 0.5 - D_ANG * 0.5     # facet 0 faces -Y (the door)


def _nearest_facet(dx, dy):
    """Facet index whose outward normal is closest to (dx, dy)."""
    target = math.atan2(dy, dx)
    best, best_d = 0, 1e9
    for k in range(SEGMENTS):
        ma = (k + 0.5) * D_ANG + OFFSET
        d = abs(math.atan2(math.sin(ma - target), math.cos(ma - target)))
        if d < best_d:
            best, best_d = k, d
    return best


def _platform_railing(bm, radius, z, gap_deg=None, height=1.0):
    """Posts + top rail around a platform's void edge, with a stair gap."""
    for k in range(SEGMENTS):
        ang = k * D_ANG + OFFSET
        if gap_deg is not None:
            d = math.degrees(math.atan2(math.sin(ang - gap_deg),
                                        math.cos(ang - gap_deg)))
            if abs(d) < 24.0:
                continue
        create_beveled_box(bm, size=(0.07, 0.07, height),
                           location=(radius * math.cos(ang), radius * math.sin(ang),
                                     z + height * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.007)
    # Rail ring drawn as a thin ring slab, skipping the stair gap.
    d_ang = D_ANG
    for k in range(SEGMENTS):
        if gap_deg is not None:
            ang_c = (k + 0.5) * D_ANG + OFFSET
            d = math.degrees(math.atan2(math.sin(ang_c - gap_deg),
                                        math.cos(ang_c - gap_deg)))
            if abs(d) < 26.0:
                continue
        ang = (k + 0.5) * D_ANG + OFFSET
        create_beveled_box(bm, size=(0.10, 2.0 * radius * math.tan(d_ang * 0.5) * 1.05, 0.07),
                           location=(radius * math.cos(ang), radius * math.sin(ang),
                                     z + height),
                           rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER,
                           bevel_amount=0.005)


def _witch_hat_roof(bm, cx, cy, z_base, radius, height, segments=SEGMENTS):
    """A flared bell-cast spire with correct shingle UVs and a crystal finial."""
    skirt_h = min(1.6, height * 0.34)
    skirt = create_cone(bm, radius1=radius * 1.16, radius2=radius * 0.70,
                        height=skirt_h, segments=segments,
                        location=(cx, cy, z_base + skirt_h * 0.5),
                        mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, skirt, scale=0.32)
    main_h = height - skirt_h
    main = create_cone(bm, radius1=radius * 0.70, radius2=0.05, height=main_h,
                       segments=segments,
                       location=(cx, cy, z_base + skirt_h + main_h * 0.5),
                       mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, main, scale=0.32)
    create_cylinder(bm, radius=radius * 1.18, height=0.16, segments=segments,
                    location=(cx, cy, z_base + 0.05), mat_index=MAT_INDEX_WOOD)
    create_cylinder(bm, radius=radius * 0.74, height=0.12, segments=segments,
                    location=(cx, cy, z_base + skirt_h + 0.04),
                    mat_index=MAT_INDEX_TIMBER)
    apex = z_base + height
    create_cylinder(bm, radius=0.05, height=0.7, segments=6,
                    location=(cx, cy, apex + 0.35), mat_index=MAT_INDEX_IRON)
    _arcane_crystal(bm, cx, cy, apex + 1.0, scale=1.15)


def _arcane_crystal(bm, cx, cy, z, scale=1.0):
    s = max(0.4, scale)
    r = 0.22 * s
    create_cone(bm, radius1=r, radius2=0.0, height=0.5 * s, segments=4,
                location=(cx, cy, z + 0.25 * s),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_GLASS)
    create_cone(bm, radius1=0.0, radius2=r, height=0.32 * s, segments=4,
                location=(cx, cy, z - 0.16 * s),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_GLASS)


def _build_switchback(bm, z0, z1, void_r, index):
    """Two short flights joined by a landing, side by side in the void.

    Flight A climbs from the lower platform into the shaft, a landing turns the
    corner, and flight B climbs back out to the upper platform. Both flights sit
    on the deck/landing (never floating), and the two flights of a storey never
    occupy the same lane, so consecutive storeys never collide.
    """
    half_h = (z1 - z0) * 0.5
    stair_w = min(1.5, void_r * 0.62)
    lane = stair_w * 0.5 + 0.22
    run = min(2.0 * void_r - 1.4, max(2.6, half_h * 1.1))
    steps = max(6, int(round(half_h / 0.19)))
    s = 1.0 if index % 2 == 0 else -1.0
    y_lo = void_r - 0.35
    y_hi = y_lo - run
    z_mid = z0 + half_h

    # Flight A: lower platform -> mid landing.
    build_straight_staircase(bm, start_pos=(-s * lane, y_lo, z0 + 0.12),
                             target_z=z_mid + 0.12, stair_width=stair_w,
                             stair_depth=run, num_steps=steps, direction_y=-1)
    # Mid landing walkway.
    create_beveled_box(bm, size=(void_r * 1.5, 1.5, 0.14),
                       location=(0.0, y_hi + 0.75, z_mid + 0.05),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.01)
    # Flight B: mid landing -> upper platform.
    build_straight_staircase(bm, start_pos=(s * lane, y_hi + 0.75, z_mid + 0.12),
                             target_z=z1 + 0.12, stair_width=stair_w,
                             stair_depth=run, num_steps=steps, direction_y=1)


def _build_annex(bm, attach, cx, cy, w, d, z0, z1, t, tier, seed,
                 door=False, win_w=0.8, win_h=1.3):
    """A square annex attached to the tower's ``attach`` side, open to it."""
    half_w = w * 0.5
    wall_mat = tier_wall_mat(tier)
    stone_top = min(z0 + 0.9, z1 - 0.4)

    if attach == 'FRONT':
        y_in = cy + d * 0.5
        y_out = y_in - d
        x0, x1 = cx - half_w, cx + half_w
        outer = ((x0, y_out), (x1, y_out), (0.0, -1.0), '-Y', w)
        sides = [((x0, y_out), (x0, y_in), (-1.0, 0.0), '-X', d),
                 ((x1, y_out), (x1, y_in), (1.0, 0.0), '+X', d)]
        frame = get_facade_frame('FRONT', x0, x1, y_in, y_in + 1.0)
    elif attach == 'BACK':
        y_in = cy - d * 0.5
        y_out = y_in + d
        x0, x1 = cx - half_w, cx + half_w
        outer = ((x0, y_out), (x1, y_out), (0.0, 1.0), '+Y', w)
        sides = [((x0, y_in), (x0, y_out), (-1.0, 0.0), '-X', d),
                 ((x1, y_in), (x1, y_out), (1.0, 0.0), '+X', d)]
        frame = get_facade_frame('BACK', x0, x1, y_in - 1.0, y_in)
    elif attach == 'LEFT':
        x_in = cx + d * 0.5
        x_out = x_in - d
        y0, y1 = cy - half_w, cy + half_w
        outer = ((x_out, y0), (x_out, y1), (-1.0, 0.0), '-X', w)
        sides = [((x_out, y0), (x_in, y0), (0.0, -1.0), '-Y', d),
                 ((x_out, y1), (x_in, y1), (0.0, 1.0), '+Y', d)]
        frame = get_facade_frame('LEFT', x_in, x_in + 1.0, y0, y1)
    else:  # RIGHT
        x_in = cx - d * 0.5
        x_out = x_in + d
        y0, y1 = cy - half_w, cy + half_w
        outer = ((x_out, y0), (x_out, y1), (1.0, 0.0), '+X', w)
        sides = [((x_in, y0), (x_out, y0), (0.0, -1.0), '-Y', d),
                 ((x_in, y1), (x_out, y1), (0.0, 1.0), '+Y', d)]
        frame = get_facade_frame('RIGHT', x_in - 1.0, x_in, y0, y1)

    p0, p1, nv, na, length = outer
    if door:
        dw, dh = min(1.4, length - 0.9), 2.4
        u0 = length * 0.5 - dw * 0.5
        ops = [{'u_start': u0, 'u_end': u0 + dw, 'z_start': z0, 'z_end': z0 + dh + 0.12}]
        build_door_assembly(bm, center_x=(p0[0] + p1[0]) * 0.5,
                            y_front=(p0[1] + p1[1]) * 0.5, z_base=z0,
                            wall_thickness=t, door_w=dw, door_h=dh,
                            door_angle_deg=0.0, door_shape='ARCHED',
                            ground_floor_stone=False, normal_axis=na)
    else:
        u0 = length * 0.5 - win_w * 0.5
        wz = z0 + (z1 - z0) * 0.55
        ops = [{'u_start': u0, 'u_end': u0 + win_w,
                'z_start': wz - win_h * 0.5, 'z_end': wz + win_h * 0.5}]
        build_window_assembly(bm, center=((p0[0] + p1[0]) * 0.5,
                                          (p0[1] + p1[1]) * 0.5, wz),
                              size=(win_w, win_h), wall_thickness=t,
                              normal_axis=nv, has_shutters=False)
    for (z0b, z1b, mat) in ((z0, stone_top, MAT_INDEX_STONE), (stone_top, z1, wall_mat)):
        if z1b - z0b < 0.06:
            continue
        band = [o for o in ops if o['z_start'] < z1b - 0.01 and o['z_end'] > z0b + 0.01]
        build_wall_with_opening(bm, p0, p1, z0b, z1b, t, band, mat_ext=mat,
                                normal_vec=nv, tier=tier, physical_siding=False,
                                seed=seed)

    for (sp0, sp1, snv, sna, slen) in sides:
        su0 = slen * 0.5 - win_w * 0.5
        wz = z0 + (z1 - z0) * 0.55
        sop = [{'u_start': su0, 'u_end': su0 + win_w,
                'z_start': wz - win_h * 0.5, 'z_end': wz + win_h * 0.5}]
        for (z0b, z1b, mat) in ((z0, stone_top, MAT_INDEX_STONE), (stone_top, z1, wall_mat)):
            if z1b - z0b < 0.06:
                continue
            band = [o for o in sop if o['z_start'] < z1b - 0.01 and o['z_end'] > z0b + 0.01]
            build_wall_with_opening(bm, sp0, sp1, z0b, z1b, t, band, mat_ext=mat,
                                    normal_vec=snv, tier=tier,
                                    physical_siding=False, seed=seed + 5)
        build_window_assembly(bm, center=((sp0[0] + sp1[0]) * 0.5,
                                          (sp0[1] + sp1[1]) * 0.5, wz),
                              size=(win_w, win_h), wall_thickness=t,
                              normal_axis=snv, has_shutters=False)

    side_attach = attach in ('LEFT', 'RIGHT')
    slab = (d - 0.1, w - 0.1, 0.12) if side_attach else (w - 0.1, d - 0.1, 0.12)
    for cz in (z0 + 0.06, z1 - 0.06):
        create_beveled_box(bm, size=slab, location=(cx, cy, cz),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.01)
    build_outcrop_gable_roof(bm, frame, z1, d, w,
                             avail_h=max(1.2, d * 0.5), wall_mat=wall_mat)


def build_mage_tower(bm, props, seed):
    """Build the tall, exaggerated, half-open fantasy mage tower."""
    wall_t = props.wall_thickness
    found_h = props.foundation_height if props.has_foundation else 0.4
    R = max(4.0, props.width * 0.5)
    level_h = max(4.8, props.floor_height)
    levels = max(2, props.num_floors)
    tier = getattr(props, 'material_tier', 'TIER_3')
    phys = getattr(props, 'physical_siding', True)
    mat_w = (MAT_INDEX_TIMBER if tier == 'TIER_1'
             else MAT_INDEX_WOOD if tier == 'TIER_2' else MAT_INDEX_PLASTER_EXT)

    flare = 0.55                         # exaggerated jetty per storey
    platform_w = min(2.6, R * 0.5)
    void_r = R - platform_w

    # ---- Annex schedule (built after the shell, but drives its openings) ----
    annexes = []
    entrance = {'side': 'FRONT', 'dir': (0.0, -1.0), 'level': 0, 'w': 5.0, 'd': 3.6,
                'z0': 0.0, 'z1': found_h + level_h * 0.5, 'door': True}
    annexes.append(entrance)
    if levels >= 2:
        annexes.append({'side': 'RIGHT', 'dir': (1.0, 0.0), 'level': 1, 'w': 3.2,
                        'd': 2.6, 'z0': found_h + level_h + level_h * 0.40,
                        'z1': found_h + level_h + level_h * 0.40 + level_h * 0.5,
                        'door': False})
    if levels >= 3:
        annexes.append({'side': 'LEFT', 'dir': (-1.0, 0.0), 'level': 2, 'w': 3.2,
                        'd': 2.6, 'z0': found_h + 2 * level_h + level_h * 0.50,
                        'z1': found_h + 2 * level_h + level_h * 0.50 + level_h * 0.45,
                        'door': False})

    level_skip, level_open = {}, {}
    for spec in annexes:
        k = _nearest_facet(*spec['dir'])
        for kk in (k - 1, k, k + 1):
            level_skip.setdefault(spec['level'], set()).add(kk % SEGMENTS)
        level_open.setdefault(spec['level'], {})[k] = spec
    # Entrance also blocks windows beside the front door on the ground floor.
    for kk in (SEGMENTS - 1, 0, 1):
        level_skip.setdefault(0, set()).add(kk)

    # ---- Stepped stone plinth ----
    if props.has_foundation:
        create_cylinder(bm, radius=R + 0.8, height=found_h * 0.5, segments=SEGMENTS,
                        location=(0.0, 0.0, found_h * 0.25), mat_index=MAT_INDEX_CUT_STONE)
        create_cylinder(bm, radius=R + 0.45, height=found_h * 0.5, segments=SEGMENTS,
                        location=(0.0, 0.0, found_h * 0.75), mat_index=MAT_INDEX_STONE)

    win_w = min(0.95, getattr(props, 'window_width', 0.9))
    win_h = min(1.7, getattr(props, 'window_height', 1.3))

    # ---- Ground-floor arcade of chunky stone columns, supporting the jetty ----
    if levels >= 2:
        n_col = 8
        col_r = R + 0.42
        for c in range(n_col):
            ang = c * (2.0 * math.pi / n_col) + math.pi / n_col
            create_cylinder(bm, radius=0.23, height=level_h, segments=8,
                            location=(col_r * math.cos(ang), col_r * math.sin(ang),
                                      found_h + level_h * 0.5),
                            mat_index=MAT_INDEX_STONE)

    prev_r = R
    for i in range(levels):
        z0 = found_h + i * level_h
        z1 = z0 + level_h
        cur_r = R + i * flare
        if props.has_cantilever and i == 0:
            cur_r = R + flare          # first upper floor already jetties out

        # Floors: ground disc, then annular platforms (open centre + stairs).
        if i == 0:
            create_cylinder(bm, radius=cur_r - 0.05, height=0.14, segments=SEGMENTS,
                            location=(0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)
        else:
            ring_slab(bm, void_r, cur_r - 0.05, z0 + 0.07, SEGMENTS, OFFSET,
                      MAT_INDEX_FLOOR, height=0.14)
            gap = math.radians(90.0) if i % 2 == 0 else math.radians(-90.0)
            _platform_railing(bm, void_r, z0 + 0.14, gap_deg=gap)
            corbel_ring(bm, prev_r + (cur_r - prev_r) * 0.4, z0 - 0.22,
                        SEGMENTS, OFFSET, size=0.22, drop=0.45)

        # Shell openings: door (ground), annex passages, windows elsewhere.
        openings = {}
        win_specs = []
        rows = (z0 + level_h * 0.34, z0 + level_h * 0.70)
        for k in range(SEGMENTS):
            p1, p2, nrm, mid = segment_frame(cur_r, k, SEGMENTS, OFFSET)
            facet_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            ops = []
            if i == 0 and k == 0 and props.has_front_door:
                dw = min(facet_len - 0.34, getattr(props, 'door_width', 1.4))
                dh = getattr(props, 'door_height', 2.6)
                m = 0.13
                ops.append({'u_start': max(0.02, (facet_len - dw) * 0.5 - m),
                            'u_end': min(facet_len - 0.02, (facet_len + dw) * 0.5 + m),
                            'z_start': z0, 'z_end': z0 + dh + m})
                build_door_assembly(bm, center_x=mid[0], y_front=mid[1], z_base=z0,
                                    wall_thickness=wall_t, door_w=dw, door_h=dh,
                                    door_angle_deg=getattr(props, 'door_angle', 0.0),
                                    door_shape='ARCHED', ground_floor_stone=False)
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=mid[0], y_front=mid[1],
                                      z_base=z0, num_steps=max(2, int(found_h / 0.18)))
            elif k in level_open.get(i, {}):
                spec = level_open[i][k]
                pw = 1.4
                u0 = facet_len * 0.5 - pw * 0.5
                ops.append({'u_start': u0, 'u_end': u0 + pw,
                            'z_start': spec['z0'] + 0.25,
                            'z_end': spec['z1'] - 0.25})
            elif (props.has_windows and k % 2 == 1
                  and k not in level_skip.get(i, set())
                  and facet_len > win_w + 0.3):
                for wz in rows:
                    u0 = (facet_len - win_w) * 0.5
                    ops.append({'u_start': u0, 'u_end': u0 + win_w,
                                'z_start': wz - win_h * 0.5,
                                'z_end': wz + win_h * 0.5})
                    win_specs.append(((mid[0], mid[1], wz), (nrm.x, nrm.y)))
            openings[k] = ops

        wall_ring(bm, cur_r, z0, z1, wall_t, SEGMENTS, OFFSET, openings, mat_w,
                  tier=tier, seed=seed + i * 13, physical_siding=phys)
        # Chunky pillars between bays (covers the facet seams), plus a string course.
        for k in range(SEGMENTS):
            ang = (k + 0.5) * D_ANG + OFFSET
            create_beveled_box(bm, size=(0.30, 0.30, level_h),
                               location=(cur_r * math.cos(ang), cur_r * math.sin(ang),
                                         z0 + level_h * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
        ring_slab(bm, cur_r - 0.10, cur_r + 0.10, z1 - 0.10, SEGMENTS, OFFSET,
                  MAT_INDEX_WOOD, height=0.16, overlap=1.12, bevel=0.01)
        for center, nv in win_specs:
            build_window_assembly(bm, center=center, size=(win_w, win_h),
                                  wall_thickness=wall_t, normal_axis=nv,
                                  has_shutters=getattr(props, 'has_shutters', True))

        # Winding switchback stairs (two flights + landing) in the shaft.
        if i < levels - 1:
            _build_switchback(bm, z0, z1, void_r, i)

        prev_r = cur_r

    top_z = found_h + levels * level_h
    top_r = prev_r

    # ---- Belvedere: a wider windowed drum under the spire ----
    bel_h = max(2.8, level_h * 0.6)
    bel_r = top_r + 0.45
    corbel_ring(bm, top_r + 0.15, top_z - 0.24, SEGMENTS, OFFSET, size=0.24, drop=0.5)
    bel_open, bel_wins = {}, []
    for k in range(SEGMENTS):
        p1, p2, nrm, mid = segment_frame(bel_r, k, SEGMENTS, OFFSET)
        fl = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if fl > win_w + 0.3:
            u0 = (fl - win_w) * 0.5
            bel_open[k] = [{'u_start': u0, 'u_end': u0 + win_w,
                            'z_start': top_z + bel_h * 0.30 - win_h * 0.5,
                            'z_end': top_z + bel_h * 0.30 + win_h * 0.5}]
            bel_wins.append(((mid[0], mid[1], top_z + bel_h * 0.30), (nrm.x, nrm.y)))
        else:
            bel_open[k] = []
    wall_ring(bm, bel_r, top_z, top_z + bel_h, wall_t, SEGMENTS, OFFSET, bel_open,
              mat_w, tier=tier, seed=seed + 99, physical_siding=phys)
    for center, nv in bel_wins:
        build_window_assembly(bm, center=center, size=(win_w, win_h),
                              wall_thickness=wall_t, normal_axis=nv,
                              has_shutters=False)

    _witch_hat_roof(bm, 0.0, 0.0, top_z + bel_h, radius=bel_r,
                    height=max(5.5, level_h * 1.15))

    # ---- Annexes: entrance hall + hanging outcrops (open into the tower) ----
    for spec in annexes:
        lvl = spec['level']
        cur_r = R + lvl * flare
        d = spec['d']
        if spec['side'] == 'FRONT':
            cx, cy = 0.0, -(cur_r - 0.6) - d * 0.5
        elif spec['side'] == 'BACK':
            cx, cy = 0.0, (cur_r - 0.6) + d * 0.5
        elif spec['side'] == 'LEFT':
            cx, cy = -(cur_r - 0.3) - d * 0.5, 0.0
        else:
            cx, cy = (cur_r - 0.3) + d * 0.5, 0.0
        _build_annex(bm, spec['side'], cx, cy, spec['w'], d,
                     spec['z0'], spec['z1'], wall_t, tier, seed + 31 + lvl,
                     door=spec['door'], win_w=0.7, win_h=1.1)

    # ---- Whimsical little dormer roofs on the belvedere ----
    for c, ang in ((0, math.radians(45.0)), (1, math.radians(-135.0))):
        bx = bel_r * 0.75 * math.cos(ang)
        by = bel_r * 0.75 * math.sin(ang)
        create_beveled_box(bm, size=(1.5, 1.5, 1.1),
                           location=(bx, by, top_z + bel_h - 0.2),
                           rotation=(0.0, 0.0, ang + math.pi * 0.25),
                           mat_index=mat_w, bevel_amount=0.02)
        create_cone(bm, radius1=1.15, radius2=0.05, height=1.3, segments=4,
                    location=(bx, by, top_z + bel_h + 0.65),
                    rotation=(0.0, 0.0, ang + math.pi * 0.25),
                    mat_index=MAT_INDEX_SHINGLES)
