"""
Solid double-walled room generator, cantilever corbels, and Tudor timber-framing.
Builds manifold thick walls with cleanly framed door and window cutouts.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_horizontal_cylinder
from .materials import MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER, MAT_INDEX_STONE

def build_log_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                           normal_vec=None, is_corner_start=False, is_corner_end=False,
                           is_y_wall=None, seed=42):
    """
    Builds authentic rustic 3D rounded logs with staggered interlocking saddle-notched
    projecting ends and organic handcrafted variation for Tier 1 architecture.
    Perpendicular walls are vertically staggered by half a log height so log ends
    interleave cleanly in an authentic saddle-notch joint without colliding.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.001:
        return
        
    angle = math.atan2(dy, dx)
    height = z_top - z_bottom
    if height < 0.05:
        return
        
    # Outward normal vector
    if normal_vec is not None:
        nx, ny = normal_vec[0], normal_vec[1]
    else:
        nx = -dy / seg_len
        ny = dx / seg_len
        
    if is_y_wall is None:
        is_y_wall = abs(dy) > abs(dx)
    
    # 1. Solid Interior Core (sealed flat interior surface)
    core_thick = thickness * 0.40
    core_cx = (x1 + x2) * 0.5 - nx * (thickness * 0.28)
    core_cy = (y1 + y2) * 0.5 - ny * (thickness * 0.28)
    core_cz = (z_bottom + z_top) * 0.5
    create_box(
        bm,
        size=(seg_len, core_thick, height),
        location=(core_cx, core_cy, core_cz),
        rotation=(0.0, 0.0, angle),
        mat_index=MAT_INDEX_PLASTER_INT
    )
    
    # 2. Stacked Physical 3D Rounded Cylindrical Logs on Exterior
    # Use consistent global log height grid (0.28m) so windows/cutouts align with corners
    target_diam = 0.28
    log_h = target_diam
    
    ext_offset = thickness * 0.20
    ext_cx = (x1 + x2) * 0.5 + nx * ext_offset
    ext_cy = (y1 + y2) * 0.5 + ny * ext_offset
    ux = dx / seg_len
    uy = dy / seg_len
    
    # Saddle-notch vertical offset: Y-walls are shifted by +0.5 * log_h relative to X-walls
    z_shift = 0.5 * log_h if is_y_wall else 0.0
    
    # Global grid indexing ensures logs across window openings align with solid walls
    k_start = int(math.floor((z_bottom - z_shift) / log_h))
    k_end = int(math.ceil((z_top - z_shift) / log_h))
    
    # If Y-wall at the very bottom sill level, add base foundation sill log
    if is_y_wall and z_bottom < 0.15:
        sill_z = z_bottom + 0.15 * log_h
        sill_r = log_h * 0.42
        create_horizontal_cylinder(
            bm, radius_y=sill_r * 0.85, radius_z=sill_r * 0.65, length=seg_len,
            segments=16, location=(ext_cx, ext_cy, sill_z),
            rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, smooth=True
        )
    
    for k in range(k_start, k_end + 1):
        log_z = (k + 0.5) * log_h + z_shift
        # Ensure log center falls within current wall vertical slice
        if log_z < z_bottom - 0.05 or log_z > z_top + 0.05:
            continue
            
        # Handcrafted organic jitter per log
        h_val = ((seed * 37 + k * 193 + int(abs(x1) * 17) + int(abs(y1) * 31)) % 1000) / 1000.0
        r_jitter = (h_val - 0.5) * 0.030
        d_jitter = ((h_val * 7.1) % 1.0 - 0.5) * 0.024
        tilt_j = ((h_val * 11.3) % 1.0 - 0.5) * 0.020
        
        log_ry = min(thickness * 0.46, log_h * 0.54) + d_jitter
        # Radius 0.49 * log_h prevents vertical intersection at perpendicular corner joints
        log_rz = (log_h * 0.49) + r_jitter
        
        # Interlocking saddle-notched extensions at outer corners
        # Matches authentic log cabin reference: logs extend 0.40m past the perpendicular wall
        ext_len = 0.40
        ext_start = ext_len if is_corner_start else 0.0
        ext_end = ext_len if is_corner_end else 0.0
            
        cur_len = seg_len + ext_start + ext_end
        u_shift = (ext_end - ext_start) * 0.5
        
        cur_cx = ext_cx + ux * u_shift
        cur_cy = ext_cy + uy * u_shift
        
        create_horizontal_cylinder(
            bm,
            radius_y=log_ry,
            radius_z=log_rz,
            length=cur_len,
            segments=16,
            location=(cur_cx, cur_cy, log_z),
            rotation=(tilt_j, 0.0, angle),
            mat_index=MAT_INDEX_TIMBER,
            mat_index_cap=10, # MAT_INDEX_LOG_END
            smooth=True
        )

def build_plank_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                             normal_vec=None, direction='HORIZONTAL', jankiness=0.35, seed=42):
    """
    Builds physical 3D wooden plank walls with organic jankiness for Tier 2 architecture.
    Supports:
    - 'HORIZONTAL': Classic overlapping weatherboard lap planks with stepped depth and bevels.
    - 'VERTICAL': Stylized board-and-batten vertical plank siding with raised battens over seams.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.001:
        return
        
    angle = math.atan2(dy, dx)
    height = z_top - z_bottom
    if height < 0.05:
        return
        
    # Outward normal vector
    if normal_vec is not None:
        nx, ny = normal_vec[0], normal_vec[1]
    else:
        nx = -dy / seg_len
        ny = dx / seg_len
        
    ux = dx / seg_len
    uy = dy / seg_len
    
    # 1. Solid Interior Core (sealed flat interior surface, flush with planks)
    core_thick = thickness * 0.84
    core_cx = (x1 + x2) * 0.5 - nx * (thickness * 0.06)
    core_cy = (y1 + y2) * 0.5 - ny * (thickness * 0.06)
    core_cz = (z_bottom + z_top) * 0.5
    create_box(
        bm,
        size=(seg_len, core_thick, height),
        location=(core_cx, core_cy, core_cz),
        rotation=(0.0, 0.0, angle),
        mat_index=MAT_INDEX_PLASTER_INT
    )
    
    ext_offset = thickness * 0.40
    
    if direction == 'VERTICAL':
        # --- VERTICAL BOARD AND BATTEN SIDING ---
        target_bw = 0.24
        num_boards = max(1, int(round(seg_len / target_bw)))
        actual_bw = seg_len / num_boards
        batten_w = 0.065
        
        for k in range(num_boards):
            mid_u = (k + 0.5) * actual_bw
            
            # Jankiness perturbations per board
            h_val = ((seed * 47 + k * 181 + int(abs(x1) * 23) + int(abs(y1) * 37)) % 1000) / 1000.0
            depth_j = (h_val - 0.5) * (0.035 * jankiness)
            tilt_v = ((h_val * 5.3) % 1.0 - 0.5) * (0.055 * jankiness)
            tilt_h = ((h_val * 9.7) % 1.0 - 0.5) * (0.035 * jankiness)
            w_jitter = (h_val - 0.5) * (0.035 * jankiness)
            
            bx = x1 + ux * mid_u + nx * (ext_offset + depth_j)
            by = y1 + uy * mid_u + ny * (ext_offset + depth_j)
            bz = (z_bottom + z_top) * 0.5
            
            # Base wide board
            create_beveled_box(
                bm,
                size=(max(0.08, actual_bw - 0.008 + w_jitter), 0.032, height),
                location=(bx, by, bz),
                rotation=(tilt_h, tilt_v, angle),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.005
            )
            
            # Raised batten strip over vertical seam
            seam_u = k * actual_bw
            if 0.02 < seam_u < seg_len - 0.02:
                batten_x = x1 + ux * seam_u + nx * (ext_offset + 0.016 + depth_j * 0.5)
                batten_y = y1 + uy * seam_u + ny * (ext_offset + 0.016 + depth_j * 0.5)
                create_beveled_box(
                    bm,
                    size=(batten_w, 0.035, height),
                    location=(batten_x, batten_y, bz),
                    rotation=(tilt_h * 0.5, tilt_v * 0.5, angle),
                    mat_index=MAT_INDEX_TIMBER,
                    bevel_amount=0.005
                )
    else:
        # --- HORIZONTAL OVERLAPPING LAP WEATHERBOARDS ---
        plank_h = 0.20
        reveal = 0.17
        num_planks = max(1, int(math.ceil(height / reveal)))
        
        for j in range(num_planks):
            pz = z_bottom + min(height - plank_h * 0.5, j * reveal + plank_h * 0.5)
            
            h_val = ((seed * 53 + j * 239 + int(abs(x1) * 19) + int(abs(y1) * 41)) % 1000) / 1000.0
            depth_j = (h_val - 0.5) * (0.045 * jankiness)
            tilt_j = ((h_val * 7.9) % 1.0 - 0.5) * (0.090 * jankiness)
            z_tilt = ((h_val * 13.1) % 1.0 - 0.5) * (0.035 * jankiness)
            
            row_step = (j % 2) * 0.005
            pcx = (x1 + x2) * 0.5 + nx * (ext_offset + row_step + depth_j)
            pcy = (y1 + y2) * 0.5 + ny * (ext_offset + row_step + depth_j)
            
            create_beveled_box(
                bm,
                size=(seg_len, 0.035, plank_h),
                location=(pcx, pcy, pz),
                rotation=(tilt_j, z_tilt, angle),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.006
            )

def build_stone_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                             normal_vec=None, block_scale=1.0, disorder=0.35,
                             is_corner_start=False, is_corner_end=False, seed=42):
    """
    Builds chunky 3D modern stylized fantasy stone blocks / masonry for Tier 3 architecture.
    Features staggered running-bond courses, soft bevels, and randomized depth protrusion
    and tilt controlled by block_scale and disorder parameters.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.001:
        return
        
    angle = math.atan2(dy, dx)
    height = z_top - z_bottom
    if height < 0.05:
        return
        
    if normal_vec is not None:
        nx, ny = normal_vec[0], normal_vec[1]
    else:
        nx = -dy / seg_len
        ny = dx / seg_len
        
    ux = dx / seg_len
    uy = dy / seg_len
    
    # 1. Solid Interior Core (sealed flat interior surface)
    core_thick = thickness * 0.38
    core_cx = (x1 + x2) * 0.5 - nx * (thickness * 0.29)
    core_cy = (y1 + y2) * 0.5 - ny * (thickness * 0.29)
    core_cz = (z_bottom + z_top) * 0.5
    create_box(
        bm,
        size=(seg_len, core_thick, height),
        location=(core_cx, core_cy, core_cz),
        rotation=(0.0, 0.0, angle),
        mat_index=MAT_INDEX_PLASTER_INT
    )
    
    # 2. Chunky 3D Stylized Ashlar / Fieldstone Blocks
    course_h_nominal = max(0.20, min(0.65, 0.36 * block_scale))
    num_courses = max(1, int(round(height / course_h_nominal)))
    actual_ch = height / num_courses
    
    nominal_bl = max(0.35, min(1.30, 0.70 * block_scale))
    stone_depth = thickness * 0.58
    ext_center_dist = thickness * 0.22
    bevel_r = max(0.015, min(0.045, 0.026 * block_scale))
    mortar_gap = 0.012
    
    for c in range(num_courses):
        cz_base = z_bottom + c * actual_ch
        mid_z = cz_base + actual_ch * 0.5
        
        # Running-bond horizontal stagger
        is_odd_course = (c % 2 == 1)
        cur_u = 0.0
        b_idx = 0
        
        while cur_u < seg_len - 0.02:
            # Deterministic hash for this specific block
            h_val = ((seed * 41 + c * 137 + b_idx * 277 + int(abs(x1)*19) + int(abs(y1)*31)) % 1000) / 1000.0
            
            # Base length with running-bond offset on first block
            if b_idx == 0 and is_odd_course and seg_len > nominal_bl * 0.9:
                target_l = nominal_bl * 0.5
            else:
                target_l = nominal_bl
                
            len_jitter = (h_val - 0.5) * (0.42 * nominal_bl * disorder)
            this_bl = target_l + len_jitter
            
            # Clamp to remaining wall length
            rem_len = seg_len - cur_u
            if rem_len < this_bl * 1.35 or this_bl >= rem_len:
                this_bl = rem_len
                
            if this_bl < 0.08:
                break
                
            mid_u = cur_u + this_bl * 0.5
            block_l = max(0.06, this_bl - mortar_gap)
            block_h = max(0.06, actual_ch - mortar_gap)
            
            # Disorder perturbations: depth pop and subtle 3D tilt
            h_pop = (((seed * 73 + c * 191 + b_idx * 311) % 1000) / 1000.0 - 0.5)
            pop_dist = h_pop * (0.080 * disorder)
            
            h_tilt_v = (((seed * 31 + c * 97 + b_idx * 503) % 1000) / 1000.0 - 0.5)
            tilt_x = h_tilt_v * (0.095 * disorder)
            
            h_tilt_h = (((seed * 67 + c * 43 + b_idx * 617) % 1000) / 1000.0 - 0.5)
            tilt_y = h_tilt_h * (0.055 * disorder)
            
            bx = x1 + ux * mid_u + nx * (ext_center_dist + pop_dist)
            by = y1 + uy * mid_u + ny * (ext_center_dist + pop_dist)
            
            create_beveled_box(
                bm,
                size=(block_l, stone_depth, block_h),
                location=(bx, by, mid_z),
                rotation=(tilt_x, tilt_y, angle),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=bevel_r
            )
            
            cur_u += this_bl
            b_idx += 1

def build_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                       mat_ext=MAT_INDEX_PLASTER_EXT, mat_int=MAT_INDEX_PLASTER_INT,
                       normal_vec=None, tier='TIER_3', physical_siding=True,
                       plank_direction='HORIZONTAL', plank_jankiness=0.35,
                       stone_block_scale=1.0, stone_disorder=0.35,
                       is_corner_start=False, is_corner_end=False, seed=42):
    """
    Builds a solid wall segment between two 2D points, dispatching to physical 3D
    rounded logs (Tier 1), overlapping/batten planks (Tier 2), chunky stone blocks (Tier 3),
    or smooth plaster/stone core boxes.
    """
    if physical_siding:
        if mat_ext == MAT_INDEX_STONE:
            build_stone_wall_segment(
                bm, p_start, p_end, z_bottom, z_top, thickness,
                normal_vec=normal_vec, block_scale=stone_block_scale, disorder=stone_disorder,
                is_corner_start=is_corner_start, is_corner_end=is_corner_end, seed=seed
            )
            return
        elif tier == 'TIER_1':
            build_log_wall_segment(
                bm, p_start, p_end, z_bottom, z_top, thickness,
                normal_vec=normal_vec, is_corner_start=is_corner_start, is_corner_end=is_corner_end,
                seed=seed
            )
            return
        elif tier == 'TIER_2':
            build_plank_wall_segment(
                bm, p_start, p_end, z_bottom, z_top, thickness,
                normal_vec=normal_vec, direction=plank_direction, jankiness=plank_jankiness,
                seed=seed
            )
            return

    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.001:
        return
        
    angle = math.atan2(dy, dx)
    cx = (x1 + x2) * 0.5
    cy = (y1 + y2) * 0.5
    cz = (z_bottom + z_top) * 0.5
    height = z_top - z_bottom
    
    create_box(
        bm,
        size=(seg_len, thickness, height),
        location=(cx, cy, cz),
        rotation=(0.0, 0.0, angle),
        mat_index=mat_ext
    )

def build_wall_with_opening(bm, p_start, p_end, z_bottom, z_top, thickness,
                            openings=[], mat_ext=MAT_INDEX_PLASTER_EXT,
                            normal_vec=None, tier='TIER_3', physical_siding=True,
                            plank_direction='HORIZONTAL', plank_jankiness=0.35,
                            stone_block_scale=1.0, stone_disorder=0.35,
                            is_corner_start=True, is_corner_end=True, seed=42):
    """
    Builds a wall along the line p_start -> p_end, cleanly cutting around
    one or more openings (e.g. door or windows) without destructive booleans.
    Each opening is a dict: {'u_start': float, 'u_end': float, 'z_start': float, 'z_end': float}
    where u is distance from p_start.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.001:
        return
        
    ux = dx / seg_len
    uy = dy / seg_len
    
    def pt_at(u):
        return (x1 + ux * u, y1 + uy * u)

    if not openings:
        build_wall_segment(
            bm, p_start, p_end, z_bottom, z_top, thickness, mat_ext=mat_ext,
            normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
            plank_direction=plank_direction, plank_jankiness=plank_jankiness,
            stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
            is_corner_start=is_corner_start, is_corner_end=is_corner_end, seed=seed
        )
        return

    # Sort openings by u_start
    sorted_ops = sorted(openings, key=lambda op: op['u_start'])
    
    last_u = 0.0
    for op in sorted_ops:
        ou1 = max(0.0, min(seg_len, op['u_start']))
        ou2 = max(0.0, min(seg_len, op['u_end']))
        oz1 = max(z_bottom, min(z_top, op['z_start']))
        oz2 = max(z_bottom, min(z_top, op['z_end']))
        
        # Wall segment before this opening
        if ou1 > last_u + 0.01:
            seg_is_start = (last_u <= 0.01) and is_corner_start
            build_wall_segment(
                bm, pt_at(last_u), pt_at(ou1), z_bottom, z_top, thickness, mat_ext=mat_ext,
                normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
                plank_direction=plank_direction, plank_jankiness=plank_jankiness,
                stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
                is_corner_start=seg_is_start, is_corner_end=False, seed=seed
            )
            
        # Below the opening (sill portion)
        if oz1 > z_bottom + 0.01:
            build_wall_segment(
                bm, pt_at(ou1), pt_at(ou2), z_bottom, oz1, thickness, mat_ext=mat_ext,
                normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
                plank_direction=plank_direction, plank_jankiness=plank_jankiness,
                stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
                is_corner_start=False, is_corner_end=False, seed=seed
            )
            
        # Above the opening (lintel/header portion)
        if oz2 < z_top - 0.01:
            build_wall_segment(
                bm, pt_at(ou1), pt_at(ou2), oz2, z_top, thickness, mat_ext=mat_ext,
                normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
                plank_direction=plank_direction, plank_jankiness=plank_jankiness,
                stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
                is_corner_start=False, is_corner_end=False, seed=seed
            )
            
        last_u = ou2
        
    # Final wall segment after last opening
    if last_u < seg_len - 0.01:
        build_wall_segment(
            bm, pt_at(last_u), pt_at(seg_len), z_bottom, z_top, thickness, mat_ext=mat_ext,
            normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
            plank_direction=plank_direction, plank_jankiness=plank_jankiness,
            stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
            is_corner_start=False, is_corner_end=is_corner_end, seed=seed
        )

def build_facade_timber(bm, p_start, p_end, z_bottom, z_top, wall_thickness,
                         normal_vec, openings=[], has_diagonals=True):
    """
    Builds authentic Tudor half-timbering along one exterior facade,
    cleanly cutting around doorways and windows so beams never block openings.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    span = math.sqrt(dx * dx + dy * dy)
    if span < 0.1:
        return
        
    ux = dx / span
    uy = dy / span
    nx, ny = normal_vec
    
    beam_w = 0.19
    beam_d = 0.09
    h = z_top - z_bottom
    
    # Exterior surface offset from wall centerline
    ext_dist = wall_thickness * 0.5 + beam_d * 0.35
    
    def to_world_pt(u, z):
        wx = x1 + ux * u + nx * ext_dist
        wy = y1 + uy * u + ny * ext_dist
        return (wx, wy, z)

    angle = math.atan2(dy, dx)

    # 1. Top Plate Beam (under the ceiling / floor above)
    top_z = z_top - beam_w * 0.5
    cx, cy, cz = to_world_pt(span * 0.5, top_z)
    create_beveled_box(bm, size=(span, beam_d, beam_w), location=(cx, cy, cz), rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

    # 2. Bottom Sill Beam (skips doors)
    bot_z = z_bottom + beam_w * 0.5
    ground_cutouts = [op for op in openings if op.get('z_start', 0.0) <= z_bottom + 0.15]
    
    bot_intervals = []
    last_u = 0.0
    for op in sorted(ground_cutouts, key=lambda o: o['u_start']):
        ou1 = max(0.0, min(span, op['u_start'] - 0.08))
        ou2 = max(0.0, min(span, op['u_end'] + 0.08))
        if ou1 > last_u + 0.15:
            bot_intervals.append((last_u, ou1))
        last_u = max(last_u, ou2)
    if last_u < span - 0.15:
        bot_intervals.append((last_u, span))
        
    for u_a, u_b in bot_intervals:
        seg_w = u_b - u_a
        if seg_w > 0.15:
            cx, cy, cz = to_world_pt((u_a + u_b) * 0.5, bot_z)
            create_beveled_box(bm, size=(seg_w, beam_d, beam_w), location=(cx, cy, cz), rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

    # 3. Horizontal Mid-Rail (skips any opening overlapping mid-height: doors & windows)
    mid_z = z_bottom + h * 0.48
    mid_cutouts = [op for op in openings if (op.get('z_start', 0.0) - 0.05) <= mid_z <= (op.get('z_end', 0.0) + 0.05)]
    
    mid_intervals = []
    last_u = 0.0
    for op in sorted(mid_cutouts, key=lambda o: o['u_start']):
        ou1 = max(0.0, min(span, op['u_start'] - 0.08))
        ou2 = max(0.0, min(span, op['u_end'] + 0.08))
        if ou1 > last_u + 0.2:
            mid_intervals.append((last_u, ou1))
        last_u = max(last_u, ou2)
    if last_u < span - 0.2:
        mid_intervals.append((last_u, span))
        
    for u_a, u_b in mid_intervals:
        seg_w = u_b - u_a
        if seg_w > 0.25:
            cx, cy, cz = to_world_pt((u_a + u_b) * 0.5, mid_z)
            create_beveled_box(bm, size=(seg_w, beam_d, beam_w), location=(cx, cy, cz), rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

    # 4. Diagonal Braces (only in solid wall panels with no openings)
    if has_diagonals:
        solid_intervals = []
        last_u = 0.0
        for op in sorted(openings, key=lambda o: o['u_start']):
            ou1 = max(0.0, min(span, op['u_start'] - 0.12))
            ou2 = max(0.0, min(span, op['u_end'] + 0.12))
            if ou1 > last_u + 1.3:
                solid_intervals.append((last_u, ou1))
            last_u = max(last_u, ou2)
        if last_u < span - 1.3:
            solid_intervals.append((last_u, span))
            
        # Exact vertical clear span between bottom beam top and mid-rail bottom
        z_bot_top = z_bottom + beam_w
        z_mid_bot = mid_z - beam_w * 0.5
        diag_h = z_mid_bot - z_bot_top
        z_c1 = (z_bot_top + z_mid_bot) * 0.5
        
        if diag_h > 0.4:
            for u_a, u_b in solid_intervals:
                p_w = u_b - u_a
                if p_w < 1.0:
                    continue
                    
                # If panel is wide (> 2.1m), use pair of mirrored braces meeting near center
                if p_w > 2.1:
                    diag_w = min(p_w * 0.46, diag_h * 1.15)
                    diag_len = math.sqrt(diag_w * diag_w + diag_h * diag_h) + 0.05
                    alpha = math.atan2(diag_h, diag_w)
                    
                    # Left brace: rises from (u_a, z_bot_top) to (u_a + diag_w, z_mid_bot)
                    T1 = Vector((math.cos(alpha) * ux, math.cos(alpha) * uy, math.sin(alpha)))
                    N_vec = Vector((nx, ny, 0.0))
                    B1 = N_vec.cross(T1).normalized()
                    rot_mat1 = Matrix([T1, N_vec, B1]).transposed()
                    rot_euler1 = rot_mat1.to_euler('XYZ')
                    
                    u_c1 = u_a + diag_w * 0.5 + 0.02
                    cx1, cy1, cz1 = to_world_pt(u_c1, z_c1)
                    create_beveled_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx1, cy1, cz1), rotation=rot_euler1, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
                    
                    # Right brace: rises from (u_b, z_bot_top) to (u_b - diag_w, z_mid_bot)
                    T2 = Vector((-math.cos(alpha) * ux, -math.cos(alpha) * uy, math.sin(alpha)))
                    B2 = N_vec.cross(T2).normalized()
                    rot_mat2 = Matrix([T2, N_vec, B2]).transposed()
                    rot_euler2 = rot_mat2.to_euler('XYZ')
                    
                    u_c2 = u_b - diag_w * 0.5 - 0.02
                    cx2, cy2, cz2 = to_world_pt(u_c2, z_c1)
                    create_beveled_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx2, cy2, cz2), rotation=rot_euler2, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
                else:
                    # Single diagonal brace spanning the panel
                    diag_w = min(p_w * 0.88, diag_h * 1.15)
                    diag_len = math.sqrt(diag_w * diag_w + diag_h * diag_h) + 0.05
                    alpha = math.atan2(diag_h, diag_w)
                    
                    T1 = Vector((math.cos(alpha) * ux, math.cos(alpha) * uy, math.sin(alpha)))
                    N_vec = Vector((nx, ny, 0.0))
                    B1 = N_vec.cross(T1).normalized()
                    rot_mat1 = Matrix([T1, N_vec, B1]).transposed()
                    rot_euler1 = rot_mat1.to_euler('XYZ')
                    
                    u_c1 = u_a + diag_w * 0.5 + 0.02
                    cx1, cy1, cz1 = to_world_pt(u_c1, z_c1)
                    create_beveled_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx1, cy1, cz1), rotation=rot_euler1, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)

def build_timber_framing(bm, x_min, x_max, y_min, y_max, z_bottom, z_top,
                         wall_thickness=0.28,
                         front_ops=[], back_ops=[], left_ops=[], right_ops=[],
                         has_diagonals=True):
    """
    Builds classic stylized Tudor half-timbering with corner posts, top/bottom plates,
    mid-rails, and diagonal braces, cleanly cutting around all openings.
    """
    beam_w = 0.22
    # Corner posts read visually thin at typical wall thicknesses — bulk them up so they
    # look like load-bearing timbers rather than the same thin rails used for mid-framing.
    corner_w = max(0.34, wall_thickness * 1.05)
    h = z_top - z_bottom
    
    # 4 Vertical Corner Posts
    corners = [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max)
    ]
    for cx, cy in corners:
        create_beveled_box(
            bm,
            size=(corner_w, corner_w, h),
            location=(cx, cy, z_bottom + h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.022
        )
        
    # Build each facade with its respective opening cutouts and explicit exterior normal
    # Front: (x_min, y_min) -> (x_max, y_min), normal (0, -1)
    build_facade_timber(bm, (x_min, y_min), (x_max, y_min), z_bottom, z_top, wall_thickness,
                         (0.0, -1.0), front_ops, has_diagonals)
    # Right: (x_max, y_min) -> (x_max, y_max), normal (1, 0)
    build_facade_timber(bm, (x_max, y_min), (x_max, y_max), z_bottom, z_top, wall_thickness,
                         (1.0, 0.0), right_ops, has_diagonals)
    # Back: (x_min, y_max) -> (x_max, y_max), normal (0, 1)
    build_facade_timber(bm, (x_min, y_max), (x_max, y_max), z_bottom, z_top, wall_thickness,
                         (0.0, 1.0), back_ops, has_diagonals)
    # Left: (x_min, y_min) -> (x_min, y_max), normal (-1, 0)
    build_facade_timber(bm, (x_min, y_min), (x_min, y_max), z_bottom, z_top, wall_thickness,
                         (-1.0, 0.0), left_ops, has_diagonals)

def create_curved_corbel(bm, loc, facing_dir=(0.0, -1.0, 0.0), width=0.18, depth=0.62, height=0.68, mat_index=MAT_INDEX_TIMBER):
    """
    Builds a stylized carved wooden console corbel bracket with:
    - Top horizontal beveled bolster block
    - Carved concave/S-curve knee console
    - Clean bevels and manifold geometry
    """
    fx, fy = facing_dir[0], facing_dir[1]
    norm = math.sqrt(fx * fx + fy * fy)
    if norm < 0.001:
        fx, fy = 0.0, -1.0
    else:
        fx, fy = fx / norm, fy / norm
        
    yaw = math.atan2(fy, fx) - math.pi * 0.5
    rot_m = Euler((0.0, 0.0, yaw), 'XYZ').to_matrix().to_4x4()
    
    # 1. Top bolster block (sits flat under the overhang)
    bolster_w = width + 0.04
    bolster_d = depth + 0.04
    bolster_h = 0.08
    bolster_center = Vector((0.0, bolster_d * 0.45, -bolster_h * 0.5))
    world_bolster = loc + rot_m @ bolster_center
    create_beveled_box(
        bm,
        size=(bolster_w, bolster_d, bolster_h),
        location=world_bolster,
        rotation=(0.0, 0.0, yaw),
        mat_index=mat_index,
        bevel_amount=0.012
    )
    
    # 2. Carved console bracket profile (segmented concave arc)
    h_console = height - bolster_h
    d_console = depth * 0.88
    num_pts = 5
    h_nose = 0.08
    
    prof_pts = [(0.0, -bolster_h), (d_console, -bolster_h), (d_console, -bolster_h - h_nose)]
    for i in range(num_pts, -1, -1):
        t = i / num_pts
        d_val = d_console * (t ** 1.6)
        h_val = -bolster_h - h_nose - (h_console - h_nose) * ((1.0 - t) ** 1.6)
        prof_pts.append((d_val, h_val))
        
    hw = width * 0.5
    vl = []
    vr = []
    for (py, pz) in prof_pts:
        vl.append(bm.verts.new(loc + rot_m @ Vector((-hw, py, pz))))
        vr.append(bm.verts.new(loc + rot_m @ Vector((hw, py, pz))))
        
    f_l = bm.faces.new(vl)
    f_l.material_index = mat_index
    f_r = bm.faces.new(list(reversed(vr)))
    f_r.material_index = mat_index
    
    M = len(prof_pts)
    for k in range(M):
        kn = (k + 1) % M
        f_p = bm.faces.new([vl[k], vl[kn], vr[kn], vr[k]])
        f_p.material_index = mat_index

def build_cantilever_corbels(bm, x_min_upper, x_max_upper, y_min_upper, y_max_upper, z_level, overhang_dist=0.35, spacing=1.2, include_front=True, include_back=True, front_exclude_x=None, drop=0.16):
    """
    Builds chunky carved wooden support brackets (corbels) underneath
    the overhanging upper floors for that iconic European fantasy silhouette.
    """
    if overhang_dist < 0.05:
        return
        
    corbel_w = 0.18
    corbel_h = 0.44
    corbel_d = overhang_dist + 0.10
    # Drop the corbel's mounting point below the upper floor's timber top-plate beam
    # so the bracket sits under it instead of poking up through it.
    z_mount = z_level - drop
    # Embed the corbel's inner (wall-side) tip slightly into the wall face so it always
    # makes solid contact instead of just grazing it.
    embed = 0.08
    
    total_x = x_max_upper - x_min_upper
    num_x = max(2, int(total_x / spacing))
    step_x = total_x / (num_x + 1)
    
    # 1. Facade corbels
    for i in range(1, num_x + 1):
        cx = x_min_upper + i * step_x
        # Front corbel
        if include_front:
            if not (front_exclude_x and front_exclude_x[0] <= cx <= front_exclude_x[1]):
                loc_front = Vector((cx, y_min_upper + overhang_dist + embed, z_mount))
                create_curved_corbel(
                    bm, loc=loc_front, facing_dir=(0.0, -1.0, 0.0),
                    width=corbel_w, depth=corbel_d + embed, height=corbel_h,
                    mat_index=MAT_INDEX_TIMBER
                )
        # Back corbel
        if include_back:
            loc_back = Vector((cx, y_max_upper - overhang_dist - embed, z_mount))
            create_curved_corbel(
                bm, loc=loc_back, facing_dir=(0.0, 1.0, 0.0),
                width=corbel_w, depth=corbel_d + embed, height=corbel_h,
                mat_index=MAT_INDEX_TIMBER
            )
            
    # 2. 45-degree diagonal corner corbels for structural fantasy silhouette
    corner_d = corbel_d * 1.15
    if include_front:
        # Front-Left corner
        if not (front_exclude_x and front_exclude_x[0] <= x_min_upper <= front_exclude_x[1]):
            loc_fl = Vector((x_min_upper + overhang_dist + embed * 0.707, y_min_upper + overhang_dist + embed * 0.707, z_mount))
            create_curved_corbel(bm, loc=loc_fl, facing_dir=(-0.707, -0.707, 0.0),
                                width=corbel_w, depth=corner_d + embed, height=corbel_h)
        # Front-Right corner
        if not (front_exclude_x and front_exclude_x[0] <= x_max_upper <= front_exclude_x[1]):
            loc_fr = Vector((x_max_upper - overhang_dist - embed * 0.707, y_min_upper + overhang_dist + embed * 0.707, z_mount))
            create_curved_corbel(bm, loc=loc_fr, facing_dir=(0.707, -0.707, 0.0),
                                width=corbel_w, depth=corner_d + embed, height=corbel_h)
    if include_back:
        # Back-Left corner
        loc_bl = Vector((x_min_upper + overhang_dist + embed * 0.707, y_max_upper - overhang_dist - embed * 0.707, z_mount))
        create_curved_corbel(bm, loc=loc_bl, facing_dir=(-0.707, 0.707, 0.0),
                            width=corbel_w, depth=corner_d + embed, height=corbel_h)
        # Back-Right corner
        loc_br = Vector((x_max_upper - overhang_dist - embed * 0.707, y_max_upper - overhang_dist - embed * 0.707, z_mount))
        create_curved_corbel(bm, loc=loc_br, facing_dir=(0.707, 0.707, 0.0),
                            width=corbel_w, depth=corner_d + embed, height=corbel_h)

def build_cantilever_soffit(bm, lower_bounds, upper_bounds, z_level, soffit_thick=0.10, front_exclude_x=None,
                            include_front=True, include_back=True, include_left=True, include_right=True):
    """
    Builds solid wooden soffit plates sealing the underside of the overhanging upper floor.
    lower_bounds: (lx_min, lx_max, ly_min, ly_max)
    upper_bounds: (ux_min, ux_max, uy_min, uy_max)
    """
    lx_min, lx_max, ly_min, ly_max = lower_bounds
    ux_min, ux_max, uy_min, uy_max = upper_bounds
    cz = z_level - soffit_thick * 0.5
    
    # Front soffit (from uy_min to ly_min)
    if include_front and uy_min < ly_min:
        d = ly_min - uy_min + 0.05
        cy = (uy_min + ly_min) * 0.5
        if front_exclude_x:
            ex1, ex2 = front_exclude_x
            if ex1 > ux_min:
                w1 = ex1 - ux_min + 0.05
                cx1 = (ux_min + ex1) * 0.5
                create_beveled_box(bm, size=(w1, d, soffit_thick), location=(cx1, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
            if ex2 < ux_max:
                w2 = ux_max - ex2 + 0.05
                cx2 = (ex2 + ux_max) * 0.5
                create_beveled_box(bm, size=(w2, d, soffit_thick), location=(cx2, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        else:
            w = ux_max - ux_min + 0.05
            cx = (ux_min + ux_max) * 0.5
            create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Back soffit (from ly_max to uy_max)
    if include_back and uy_max > ly_max:
        d = uy_max - ly_max + 0.05
        w = ux_max - ux_min + 0.05
        cy = (uy_max + ly_max) * 0.5
        cx = (ux_min + ux_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Left soffit (from ux_min to lx_min)
    if include_left and ux_min < lx_min:
        w = lx_min - ux_min + 0.05
        d = ly_max - ly_min + 0.05
        cx = (ux_min + lx_min) * 0.5
        cy = (ly_min + ly_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Right soffit (from lx_max to ux_max)
    if include_right and ux_max > lx_max:
        w = ux_max - lx_max + 0.05
        d = ly_max - ly_min + 0.05
        cx = (lx_max + ux_max) * 0.5
        cy = (ly_min + ly_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
