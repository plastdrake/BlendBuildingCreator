"""
Primitive makeshift roof generator for low-tier industrial buildings and pirate shanties.
Generates an authentic timber rafter truss structure, continuous draped canvas canopy
with custom fantasy textile shader (MAT_INDEX_TARP), and slope-aligned wooden weatherboards.
"""

import math
import random
from mathutils import Vector, Euler, Matrix
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD,
    MAT_INDEX_TARP, MAT_INDEX_ROPE
)

# Clean single-plank UV bands sampled from pirate_timber_diffuse.jpg (15 vertical planks)
HAJFIN_PLANK_BANDS = [
    (0.015, 0.060),
    (0.068, 0.110),
    (0.118, 0.193),
    (0.201, 0.244),
    (0.252, 0.295),
    (0.303, 0.372),
    (0.380, 0.440),
    (0.448, 0.496),
    (0.504, 0.550),
    (0.558, 0.621),
    (0.629, 0.674),
    (0.682, 0.743),
    (0.751, 0.810),
    (0.817, 0.872),
    (0.880, 0.940),
]

# Clean single-plank UV bands sampled from facade_wood_planks_diffuse.jpg (17 horizontal planks)
HUMAN_PLANK_BANDS = [
    (0.007, 0.051),
    (0.059, 0.097),
    (0.105, 0.150),
    (0.158, 0.196),
    (0.204, 0.297),
    (0.305, 0.355),
    (0.363, 0.396),
    (0.404, 0.442),
    (0.450, 0.496),
    (0.504, 0.596),
    (0.604, 0.642),
    (0.649, 0.698),
    (0.706, 0.761),
    (0.769, 0.801),
    (0.809, 0.854),
    (0.862, 0.904),
    (0.912, 0.983),
]


def _map_makeshift_roof_plank_uvs(bm, faces, size, location, rotation,
                                  plank_idx=0, rng=None, is_hajfin=True, is_x_long=True):
    """
    Unwraps each individual roof plank so it maps to exactly ONE single board from the texture atlas.
    Guarantees no plank consists of multiple smaller painted planks, and adjacent planks
    are never identically unwrapped (staggered bands, inverted grain, and varied offsets).
    """
    uv_layer = bm.loops.layers.uv.verify()
    eul = Euler(rotation, 'XYZ')
    inv_tr = (Matrix.Translation(Vector(location)) @ eul.to_matrix().to_4x4()).inverted()
    inv_rot = eul.to_matrix().inverted()

    dx, dy, dz = size
    if is_x_long:
        width = dx
        length = dy
        thick = dz
    else:
        width = dy
        length = dx
        thick = dz

    bm.normal_update()

    if is_hajfin:
        v_offset = (plank_idx * 0.382 + (rng.random() * 0.25 if rng else 0.0)) % 1.0
        u_shift = (plank_idx * 0.236 + (rng.random() * 0.15 if rng else 0.0)) % 0.55
        v_scale = 0.28
        u_scale = 0.45

        for face in faces:
            ln = inv_rot @ face.normal
            lnx, lny, lnz = abs(ln.x), abs(ln.y), abs(ln.z)
            face.tag = True
            for loop in face.loops:
                lc = inv_tr @ loop.vert.co
                w_val = lc.x if is_x_long else lc.y
                l_val = lc.y if is_x_long else lc.x

                # Across plank width is U, along plank length is V:
                if (is_x_long and lnx >= lny and lnx >= lnz) or ((not is_x_long) and lny >= lnx and lny >= lnz):
                    u = (lc.z + thick * 0.5) * u_scale + u_shift
                else:
                    u = (w_val + width * 0.5) * u_scale + u_shift

                if (is_x_long and lny >= lnx and lny >= lnz) or ((not is_x_long) and lnx >= lny and lnx >= lnz):
                    v = (lc.z + thick * 0.5) * 0.08 + v_offset
                else:
                    v = (l_val + length * 0.5) * v_scale + v_offset

                loop[uv_layer].uv = Vector((u, v))
    else:
        # Human building: horizontal plank bands in facade_wood_planks_diffuse.jpg
        bands = HUMAN_PLANK_BANDS
        band_idx = (plank_idx * 5 + 3) % len(bands)
        v0, v1 = bands[band_idx]
        if plank_idx % 2 == 1:
            v0, v1 = v1, v0
        u_offset = (plank_idx * 0.382 + (rng.random() * 0.25 if rng else 0.0)) % 1.0
        u_scale = 0.28

        for face in faces:
            ln = inv_rot @ face.normal
            lnx, lny, lnz = abs(ln.x), abs(ln.y), abs(ln.z)
            face.tag = True
            for loop in face.loops:
                lc = inv_tr @ loop.vert.co
                w_val = lc.x if is_x_long else lc.y
                l_val = lc.y if is_x_long else lc.x
                t_v = max(0.0, min(1.0, (w_val + width * 0.5) / max(0.0001, width)))

                if is_x_long and (lnx >= lny and lnx >= lnz):
                    v = v1 if ln.x > 0 else v0
                elif (not is_x_long) and (lny >= lnx and lny >= lnz):
                    v = v1 if ln.y > 0 else v0
                else:
                    v = v0 + t_v * (v1 - v0)

                if (is_x_long and lny >= lnx and lny >= lnz) or ((not is_x_long) and lnx >= lny and lnx >= lnz):
                    u = (lc.z + thick * 0.5) / max(0.0001, thick) * 0.04 + u_offset
                else:
                    u = (l_val + length * 0.5) * u_scale + u_offset

                loop[uv_layer].uv = Vector((u, v))


def _map_canvas_slope_uvs(bm, faces, size, location, rotation, scale=0.9):
    """Maps continuous, undistorted UVs across sloped draped canvas in local space."""
    uv = bm.loops.layers.uv.verify()
    eul = Euler(rotation, 'XYZ')
    inv_m = (Matrix.Translation(Vector(location)) @ eul.to_matrix().to_4x4()).inverted()
    for face in faces:
        face.tag = True
        for loop in face.loops:
            lc = inv_m @ loop.vert.co
            loop[uv].uv = Vector(((lc.x + size[0] * 0.5) * scale, (lc.y + size[1] * 0.5) * scale))


def _map_canvas_flap_uvs(bm, faces, size, location, rotation, scale=0.9):
    """Maps hanging eave flaps so canvas weave flows down seamlessly."""
    uv = bm.loops.layers.uv.verify()
    eul = Euler(rotation, 'XYZ')
    inv_m = (Matrix.Translation(Vector(location)) @ eul.to_matrix().to_4x4()).inverted()
    for face in faces:
        face.tag = True
        for loop in face.loops:
            lc = inv_m @ loop.vert.co
            loop[uv].uv = Vector(((lc.x + size[0] * 0.5) * scale, (lc.z + size[2] * 0.5) * scale))


def build_makeshift_roof(bm, x_min, x_max, y_min, y_max, z_base,
                         effective_archetype='NONE', seed=42, roof_height=None):
    """
    Builds an authentic rustic industrial / shack roof structure:
    1. Cross-rafter trusses resting solidly on the arcade posts with an authentic pitch.
    2. Longitudinal ridge and mid-slope purlins safely recessed underneath the roof covering.
    3. Smooth, continuous draped canvas canopy (MAT_INDEX_TARP) with eave overhang flaps.
    4. Weathered roof planks laid cleanly along the roof pitch across the purlins.
    5. Wooden hold-down battens and post tie-down ropes.
    """
    rng = random.Random(seed + 303)

    span_x = x_max - x_min
    span_y = y_max - y_min
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5

    is_x_long = span_x >= span_y
    long_len = span_x if is_x_long else span_y
    cross_span = span_y if is_x_long else span_x

    is_hajfin = (effective_archetype == 'HAJFIN')

    # Calculate steepness/rise: give a distinctive, water-shedding pitch (~20-25 deg)
    # rather than an almost flat plane.
    if is_hajfin:
        if roof_height is not None and roof_height > 0.1:
            ridge_rise = max(1.40, min(roof_height * 0.55, cross_span * 0.28))
        else:
            ridge_rise = max(1.40, min(2.40, cross_span * 0.24))
    else:
        if roof_height is not None and roof_height > 0.1:
            ridge_rise = max(0.85, min(roof_height * 0.45, cross_span * 0.20))
        else:
            ridge_rise = min(1.40, max(0.75, cross_span * 0.15))

    z_ridge = z_base + ridge_rise
    eave_overhang = 0.35

    # -------------------------------------------------------------------------
    # 1. Rafter Trusses & Collar Ties across the building
    # -------------------------------------------------------------------------
    rafter_w = 0.14 if is_hajfin else 0.12
    rafter_d = 0.12 if is_hajfin else 0.10
    n_trusses = max(3, int(round(long_len / 3.4)) + 1)
    half_cross = cross_span * 0.5 + eave_overhang
    slope_len = math.sqrt(half_cross * half_cross + ridge_rise * ridge_rise)
    pitch_angle = math.atan2(ridge_rise, half_cross)

    # Rafters are shortened so their square ends never poke through the ridge peak
    # or protrude past the canvas eave flap.
    rafter_reach = cross_span * 0.5 + 0.18
    rafter_len = math.sqrt(rafter_reach * rafter_reach + (ridge_rise * (rafter_reach / max(0.1, half_cross))) ** 2) - 0.10
    rafter_cz = z_base + ridge_rise * 0.5 - 0.035

    for ti in range(n_trusses):
        t = ti / float(n_trusses - 1)
        long_pos = (t - 0.5) * (long_len - 0.10)

        if is_x_long:
            tx = cx + long_pos
            # Horizontal tie beam across the posts
            create_beveled_box(
                bm, size=(rafter_w, cross_span + 0.04, 0.14),
                location=(tx, cy, z_base - 0.02),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # Front slope rafter (slopes down toward front eave)
            r_front_cy = cy - rafter_reach * 0.5
            create_beveled_box(
                bm, size=(rafter_w, rafter_len, rafter_d),
                location=(tx, r_front_cy, rafter_cz),
                rotation=(pitch_angle, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # Back slope rafter (slopes down toward back eave)
            r_back_cy = cy + rafter_reach * 0.5
            create_beveled_box(
                bm, size=(rafter_w, rafter_len, rafter_d),
                location=(tx, r_back_cy, rafter_cz),
                rotation=(-pitch_angle, 0.0, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            # King post at center supporting ridge purlin from below
            kp_h = max(0.15, ridge_rise - 0.08)
            create_beveled_box(
                bm, size=(0.12, 0.12, kp_h),
                location=(tx, cy, z_base + kp_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )
        else:
            ty = cy + long_pos
            create_beveled_box(
                bm, size=(cross_span + 0.04, rafter_w, 0.14),
                location=(cx, ty, z_base - 0.02),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            r_left_cx = cx - rafter_reach * 0.5
            create_beveled_box(
                bm, size=(rafter_len, rafter_w, rafter_d),
                location=(r_left_cx, ty, rafter_cz),
                rotation=(0.0, -pitch_angle, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            r_right_cx = cx + rafter_reach * 0.5
            create_beveled_box(
                bm, size=(rafter_len, rafter_w, rafter_d),
                location=(r_right_cx, ty, rafter_cz),
                rotation=(0.0, pitch_angle, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
            kp_h = max(0.15, ridge_rise - 0.08)
            create_beveled_box(
                bm, size=(0.12, 0.12, kp_h),
                location=(cx, ty, z_base + kp_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
            )

    # -------------------------------------------------------------------------
    # 2. Longitudinal Purlins (Ridge & Mid-Slopes) - Safely recessed under roof
    # -------------------------------------------------------------------------
    purlin_w = 0.11 if is_hajfin else 0.10
    purlin_h = 0.09 if is_hajfin else 0.08
    purlin_overhang = 0.15
    p_len = long_len + purlin_overhang * 2.0

    # Ridge purlin sits right below the roof peak (supporting it from beneath)
    if is_x_long:
        create_beveled_box(
            bm, size=(p_len, purlin_w, purlin_h),
            location=(cx, cy, z_ridge - 0.03),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
        )
        for sgn in (-1.0, 1.0):
            py = cy + sgn * (cross_span * 0.24)
            pz = z_base + ridge_rise * 0.5 - 0.035
            create_beveled_box(
                bm, size=(p_len, purlin_w, purlin_h),
                location=(cx, py, pz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
            )
    else:
        create_beveled_box(
            bm, size=(purlin_w, p_len, purlin_h),
            location=(cx, cy, z_ridge - 0.03),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
        )
        for sgn in (-1.0, 1.0):
            px = cx + sgn * (cross_span * 0.24)
            pz = z_base + ridge_rise * 0.5 - 0.035
            create_beveled_box(
                bm, size=(purlin_w, p_len, purlin_h),
                location=(px, cy, pz),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.006
            )

    # -------------------------------------------------------------------------
    # 3. Continuous Draped Canvas Canopy (MAT_INDEX_TARP)
    # Covers one portion of the roof (e.g. 58% of length)
    # -------------------------------------------------------------------------
    tarp_ratio = 0.58
    tarp_long_len = long_len * tarp_ratio + 0.15
    # Hajfin sailcloth is layered, salt-stiffened canvas rather than the thin
    # human tarpaulin.
    cloth_t = 0.045 if is_hajfin else 0.024
    cloth_bevel = 0.005 if is_hajfin else 0.003
    roof_cz = z_base + ridge_rise * 0.5 + 0.03
    d_slope_mid = half_cross * 0.5

    # Place canopy over the negative side
    if is_x_long:
        tarp_cx = cx - (long_len * (1.0 - tarp_ratio) * 0.5)
        # Front slope canvas
        front_y_c = cy - d_slope_mid
        f_sz = (tarp_long_len, slope_len + 0.04, cloth_t)
        f_faces1 = create_beveled_box(
            bm, size=f_sz,
            location=(tarp_cx, front_y_c, roof_cz),
            rotation=(pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_slope_uvs(bm, f_faces1, f_sz, (tarp_cx, front_y_c, roof_cz), (pitch_angle, 0.0, 0.0))

        # Front eave vertical hanging flap
        f_flap_y = cy - half_cross - 0.01
        f_flap_z = z_base - 0.08
        flap_sz = (tarp_long_len, cloth_t, 0.20)
        f_faces2 = create_beveled_box(
            bm, size=flap_sz,
            location=(tarp_cx, f_flap_y, f_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_flap_uvs(bm, f_faces2, flap_sz, (tarp_cx, f_flap_y, f_flap_z), (0.0, 0.0, 0.0))

        # Back slope canvas
        back_y_c = cy + d_slope_mid
        b_sz = (tarp_long_len, slope_len + 0.04, cloth_t)
        b_faces1 = create_beveled_box(
            bm, size=b_sz,
            location=(tarp_cx, back_y_c, roof_cz),
            rotation=(-pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_slope_uvs(bm, b_faces1, b_sz, (tarp_cx, back_y_c, roof_cz), (-pitch_angle, 0.0, 0.0))

        # Back eave vertical hanging flap
        b_flap_y = cy + half_cross + 0.01
        b_flap_z = z_base - 0.08
        b_faces2 = create_beveled_box(
            bm, size=flap_sz,
            location=(tarp_cx, b_flap_y, b_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_flap_uvs(bm, b_faces2, flap_sz, (tarp_cx, b_flap_y, b_flap_z), (0.0, 0.0, 0.0))

        # Clamping battens across the canvas (shortened at top so they don't poke over ridge)
        batten_len = slope_len - 0.08
        for b_frac in (-0.35, 0.0, 0.35):
            bx = tarp_cx + b_frac * (tarp_long_len - 0.20)
            for sgn in (-1.0, 1.0):
                by = cy + sgn * d_slope_mid
                bz = roof_cz + cloth_t * 0.5 + 0.015
                rot_x = pitch_angle if sgn < 0 else -pitch_angle
                create_beveled_box(
                    bm, size=(0.07, batten_len, 0.025),
                    location=(bx, by, bz),
                    rotation=(rot_x, 0.0, 0.0),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004
                )

        # Tie ropes at canvas corners to timber posts
        for rx in (tarp_cx - tarp_long_len * 0.46, tarp_cx + tarp_long_len * 0.46):
            for sgn in (-1.0, 1.0):
                ry = cy + sgn * half_cross
                rope_h = 0.55
                create_cylinder(
                    bm, radius=0.016, height=rope_h, segments=6,
                    location=(rx, ry, z_base - rope_h * 0.5 + 0.02),
                    mat_index=MAT_INDEX_ROPE
                )
    else:
        tarp_cy = cy - (long_len * (1.0 - tarp_ratio) * 0.5)
        # Left slope canvas
        left_x_c = cx - d_slope_mid
        l_sz = (slope_len + 0.04, tarp_long_len, cloth_t)
        f_faces1 = create_beveled_box(
            bm, size=l_sz,
            location=(left_x_c, tarp_cy, roof_cz),
            rotation=(0.0, -pitch_angle, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_slope_uvs(bm, f_faces1, l_sz, (left_x_c, tarp_cy, roof_cz), (0.0, -pitch_angle, 0.0))

        # Left eave vertical hanging flap
        f_flap_x = cx - half_cross - 0.01
        f_flap_z = z_base - 0.08
        flap_sz = (cloth_t, tarp_long_len, 0.20)
        f_faces2 = create_beveled_box(
            bm, size=flap_sz,
            location=(f_flap_x, tarp_cy, f_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_flap_uvs(bm, f_faces2, flap_sz, (f_flap_x, tarp_cy, f_flap_z), (0.0, 0.0, 0.0))

        # Right slope canvas
        right_x_c = cx + d_slope_mid
        r_sz = (slope_len + 0.04, tarp_long_len, cloth_t)
        b_faces1 = create_beveled_box(
            bm, size=r_sz,
            location=(right_x_c, tarp_cy, roof_cz),
            rotation=(0.0, pitch_angle, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_slope_uvs(bm, b_faces1, r_sz, (right_x_c, tarp_cy, roof_cz), (0.0, pitch_angle, 0.0))

        # Right eave vertical hanging flap
        b_flap_x = cx + half_cross + 0.01
        b_flap_z = z_base - 0.08
        b_faces2 = create_beveled_box(
            bm, size=flap_sz,
            location=(b_flap_x, tarp_cy, b_flap_z),
            mat_index=MAT_INDEX_TARP, bevel_amount=cloth_bevel
        )
        _map_canvas_flap_uvs(bm, b_faces2, flap_sz, (b_flap_x, tarp_cy, b_flap_z), (0.0, 0.0, 0.0))

    # -------------------------------------------------------------------------
    # 4. Roof Planks / Weatherboards along the pitch
    # Covers the remaining portion of the roof with wide, hefty timber boards
    # -------------------------------------------------------------------------
    plank_section_start = long_len * (tarp_ratio - 0.5) - 0.05
    plank_section_end = long_len * 0.5 + 0.15
    plank_span = plank_section_end - plank_section_start

    # Make planks bigger and fewer:
    # Hajfin uses wide, thick driftwood planks matching the wall boards.
    if is_hajfin:
        plank_w = 0.52
        plank_t = 0.055
        plank_step = 0.58
    else:
        plank_w = 0.38
        plank_t = 0.038
        plank_step = 0.44

    n_plank_rows = max(2, int(round(plank_span / plank_step)))
    actual_step = plank_span / n_plank_rows

    for pi in range(n_plank_rows):
        p_offset = plank_section_start + (pi + 0.5) * actual_step

        # Random slight length stagger (+/- 0.08m)
        p_len_var = (rng.random() - 0.5) * 0.16
        cur_plank_len = max(0.8, slope_len + p_len_var - 0.06)

        # Occasional missing plank for rustic open look
        if rng.random() < (0.10 if is_hajfin else 0.15):
            continue

        jank_yaw = (rng.random() - 0.5) * 0.02
        jank_pitch = (rng.random() - 0.5) * 0.015

        if is_x_long:
            px = cx + p_offset
            for sgn in (-1.0, 1.0):
                if rng.random() < 0.08:
                    continue
                py = cy + sgn * d_slope_mid
                pz = z_base + ridge_rise * 0.5 + plank_t * 0.5 + 0.015
                rot_x = (pitch_angle if sgn < 0 else -pitch_angle) + jank_pitch
                p_size = (plank_w, cur_plank_len, plank_t)
                p_loc = (px, py, pz)
                p_rot = (rot_x, 0.0, jank_yaw)
                p_faces = create_beveled_box(
                    bm, size=p_size,
                    location=p_loc,
                    rotation=p_rot,
                    mat_index=MAT_INDEX_TIMBER if is_hajfin else MAT_INDEX_WOOD, bevel_amount=0.005
                )
                _map_makeshift_roof_plank_uvs(
                    bm, p_faces, p_size, p_loc, p_rot,
                    plank_idx=pi * 2 + (0 if sgn < 0 else 1),
                    rng=rng, is_hajfin=is_hajfin, is_x_long=True
                )
        else:
            py = cy + p_offset
            for sgn in (-1.0, 1.0):
                if rng.random() < 0.08:
                    continue
                px = cx + sgn * d_slope_mid
                pz = z_base + ridge_rise * 0.5 + plank_t * 0.5 + 0.015
                rot_y = (-pitch_angle if sgn < 0 else pitch_angle) + jank_pitch
                p_size = (cur_plank_len, plank_w, plank_t)
                p_loc = (px, py, pz)
                p_rot = (0.0, rot_y, jank_yaw)
                p_faces = create_beveled_box(
                    bm, size=p_size,
                    location=p_loc,
                    rotation=p_rot,
                    mat_index=MAT_INDEX_TIMBER if is_hajfin else MAT_INDEX_WOOD, bevel_amount=0.005
                )
                _map_makeshift_roof_plank_uvs(
                    bm, p_faces, p_size, p_loc, p_rot,
                    plank_idx=pi * 2 + (0 if sgn < 0 else 1),
                    rng=rng, is_hajfin=is_hajfin, is_x_long=False
                )
