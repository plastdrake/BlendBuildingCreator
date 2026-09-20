"""
Solid double-walled room generator, cantilever corbels, and Tudor timber-framing.
Builds manifold thick walls with cleanly framed door and window cutouts.
"""

import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_horizontal_cylinder
from .materials import (
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER, MAT_INDEX_STONE,
    MAT_INDEX_LOG, MAT_INDEX_LOG_END, MAT_INDEX_WOOD, MAT_INDEX_PLASTER_BRICK,
    MAT_INDEX_TIMBER_FRAME,
)

def build_log_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                           openings=[], normal_vec=None, is_corner_start=False, is_corner_end=False,
                           is_y_wall=None, seed=42, omit_top_row=False, force_omit_top_row=False):
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
    
    # Consistent global log height grid (0.36m) matching roof gable logs
    log_h = 0.36

    # 1. Solid Interior Core (sealed flat interior surface). Only a hair below
    # the floor line - enough to meet the floor slab, but not so low that the
    # skirt hangs out under a jettied storey and buries the cantilever corbels.
    # Interior planks (wood), matching the core the opening path builds, so a
    # wall that happens to get no windows/doors still reads as a log-cabin room
    # instead of exposing the shared plaster material on the inside.
    if not openings:
        core_thick = thickness * 0.40
        core_cx = (x1 + x2) * 0.5 - nx * (thickness * 0.28)
        core_cy = (y1 + y2) * 0.5 - ny * (thickness * 0.28)
        core_z_bottom = max(0.0, z_bottom - 0.06)
        core_cz = (core_z_bottom + z_top) * 0.5
        create_box(
            bm,
            size=(seg_len, core_thick, z_top - core_z_bottom),
            location=(core_cx, core_cy, core_cz),
            rotation=(0.0, 0.0, angle),
            mat_index=MAT_INDEX_WOOD,
            is_wall=True
        )
    
    # 2. Stacked Physical 3D Rounded Cylindrical Logs on Exterior
    ext_offset = thickness * 0.32
    ux = dx / seg_len
    uy = dy / seg_len
    
    # Consistent global vertical grid on ALL walls (no half-height stagger, matching Reference Image 4)
    z_shift = 0.0
    
    k_start = int(math.floor((z_bottom - z_shift) / log_h))
    k_end = int(math.ceil((z_top - z_shift) / log_h))

    # Optional crown removal (multi-floor Tier-1 eave sides): drop the topmost
    # row only when it rides on/above the wall top line (redundant cap crowding
    # the eave). Recessed crowns are kept so no slit opens under the eave.
    skip_k = None
    if omit_top_row:
        valid_ks = [kk for kk in range(k_start, k_end + 1)
                    if z_bottom - 0.05 <= (kk + 0.5) * log_h + z_shift <= z_top + 0.05]
        if len(valid_ks) >= 2:
            top_z = (valid_ks[-1] + 0.5) * log_h + z_shift
            if force_omit_top_row or top_z > z_top - 0.02:
                skip_k = valid_ks[-1]

    for k in range(k_start, k_end + 1):
        if k == skip_k:
            continue
        log_z = (k + 0.5) * log_h + z_shift
        # Ensure log center falls within current wall vertical slice
        if log_z < z_bottom - 0.05 or log_z > z_top + 0.05:
            continue
            
        # Handcrafted organic jitter per log
        h_val = ((seed * 37 + k * 193 + int(abs(x1) * 17) + int(abs(y1) * 31)) % 1000) / 1000.0
        r_jitter = (h_val - 0.5) * 0.030
        d_jitter = ((h_val * 7.1) % 1.0 - 0.5) * 0.024
        tilt_j = ((h_val * 11.3) % 1.0 - 0.5) * 0.020
        
        log_ry = min(thickness * 0.65, log_h * 0.56) + d_jitter
        log_rz = (log_h * 0.49) + r_jitter
        
        # Check openings that intersect this log row's vertical span
        cut_intervals = []
        for op in openings:
            op_z1 = op.get('z_start', z_bottom)
            op_z2 = op.get('z_end', z_top)
            if op_z1 - 0.04 <= log_z <= op_z2 + 0.04:
                u1 = max(0.0, min(seg_len, op.get('u_start', 0.0)))
                u2 = max(0.0, min(seg_len, op.get('u_end', seg_len)))
                if u2 > u1 + 0.01:
                    cut_intervals.append((u1, u2))
        
        if cut_intervals:
            cut_intervals.sort(key=lambda x: x[0])
            merged = []
            for cu1, cu2 in cut_intervals:
                if not merged:
                    merged.append([cu1, cu2])
                else:
                    if cu1 <= merged[-1][1] + 0.01:
                        merged[-1][1] = max(merged[-1][1], cu2)
                    else:
                        merged.append([cu1, cu2])
            spans = []
            cur_u = 0.0
            for cu1, cu2 in merged:
                if cu1 > cur_u + 0.04:
                    spans.append((cur_u, cu1))
                cur_u = max(cur_u, cu2)
            if cur_u < seg_len - 0.04:
                spans.append((cur_u, seg_len))
        else:
            spans = [(0.0, seg_len)]
            
        ext_len = 0.38
        if is_y_wall:
            row_extends = (k % 2 == 0)
        else:
            row_extends = (k % 2 == 1)
            
        for u_a, u_b in spans:
            span_len = u_b - u_a
            if span_len < 0.04:
                continue
                
            ext_start = ext_len if (is_corner_start and row_extends and u_a <= 0.01) else 0.0
            ext_end = ext_len if (is_corner_end and row_extends and u_b >= seg_len - 0.01) else 0.0
            
            cur_len = span_len + ext_start + ext_end
            u_mid = (u_a + u_b) * 0.5 + (ext_end - ext_start) * 0.5
            
            cur_cx = (x1 + ux * u_mid) + nx * ext_offset
            cur_cy = (y1 + uy * u_mid) + ny * ext_offset
            
            shared_uv = (k - k_start) * (cur_len * 0.12)
            create_horizontal_cylinder(
                bm,
                radius_y=log_ry,
                radius_z=log_rz,
                length=cur_len,
                segments=16,
                location=(cur_cx, cur_cy, log_z),
                rotation=(tilt_j, 0.0, angle),
                mat_index=MAT_INDEX_LOG,
                mat_index_cap=MAT_INDEX_LOG_END,
                smooth=True,
                uv_offset=shared_uv
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

def _choose_plaster_mat(p1, p2, z_b, z_t, base_mat, has_brick, brick_freq, seed_val):
    if (not has_brick) or (base_mat != MAT_INDEX_PLASTER_EXT) or (brick_freq <= 0.001):
        return base_mat
    cx = (p1[0] + p2[0]) * 0.5
    cy = (p1[1] + p2[1]) * 0.5
    cz = (z_b + z_t) * 0.5
    # Concentrated corner/here-and-there gating: low-frequency field picks 1-2 wall
    # zones per building so bricks cluster instead of spacing evenly on every wall.
    # High frequency values still open more zones (no regression for max settings).
    import math as _math
    cluster = _math.sin(cx * 0.55 + seed_val * 1.7) * _math.cos(cy * 0.55 - cz * 0.25 + seed_val * 0.9)
    gate = 0.55 - min(0.95, max(0.01, brick_freq)) * 0.8
    if cluster < gate and brick_freq < 0.85:
        return MAT_INDEX_PLASTER_EXT
    h = int(abs(math.sin(cx * 17.13 + cy * 53.71 + cz * 31.19 + seed_val * 97.43)) * 10000) % 100
    if h < int(brick_freq * 100):
        return MAT_INDEX_PLASTER_BRICK
    return MAT_INDEX_PLASTER_EXT

def build_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness,
                       mat_ext=MAT_INDEX_PLASTER_EXT, normal_vec=None,
                       tier='TIER_3', physical_siding=True,
                       plank_direction='HORIZONTAL', plank_jankiness=0.35,
                       stone_block_scale=1.0, stone_disorder=0.35,
                       is_corner_start=True, is_corner_end=True, seed=42, u_offset=0.0, v_offset=0.0,
                       has_exposed_brick=False, exposed_brick_freq=0.25):
    """
    Constructs a single wall section between p_start and p_end:
    rounded logs (Tier 1), overlapping/batten planks (Tier 2), chunky stone blocks (Tier 3),
    or smooth plaster/stone core boxes with optional exposed terracotta brick accents.
    """
    if physical_siding and tier == 'TIER_1':
        build_log_wall_segment(
            bm, p_start, p_end, z_bottom, z_top, thickness,
            normal_vec=normal_vec, is_corner_start=is_corner_start, is_corner_end=is_corner_end,
            seed=seed
        )
        return

    if tier == 'TIER_1' and mat_ext in (MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER):
        mat_ext = MAT_INDEX_WOOD

    if mat_ext == MAT_INDEX_PLASTER_EXT and has_exposed_brick:
        mat_ext = _choose_plaster_mat(p_start, p_end, z_bottom, z_top, mat_ext, has_exposed_brick, exposed_brick_freq, seed)

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
        mat_index=mat_ext,
        is_wall=True,
        u_offset=u_offset,
        v_offset=v_offset
    )

def build_wall_with_opening(bm, p_start, p_end, z_bottom, z_top, thickness,
                            openings=[], mat_ext=MAT_INDEX_PLASTER_EXT,
                            normal_vec=None, tier='TIER_3', physical_siding=True,
                            plank_direction='HORIZONTAL', plank_jankiness=0.35,
                            stone_block_scale=1.0, stone_disorder=0.35,
                            is_corner_start=True, is_corner_end=True, seed=42, u_offset=0.0,
                            omit_top_log_row=False,
                            force_omit_top_log_row=False,
                            has_exposed_brick=False, exposed_brick_freq=0.25):
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
            is_corner_start=is_corner_start, is_corner_end=is_corner_end, seed=seed,
            u_offset=u_offset,
            has_exposed_brick=has_exposed_brick, exposed_brick_freq=exposed_brick_freq
        )
        return

    if tier == 'TIER_1' and physical_siding:
        # Build authentic cylindrical log wall with openings handled per-log
        build_log_wall_segment(
            bm, p_start, p_end, z_bottom, z_top, thickness,
            openings=openings, normal_vec=normal_vec,
            is_corner_start=is_corner_start, is_corner_end=is_corner_end,
            seed=seed, omit_top_row=omit_top_log_row,
            force_omit_top_row=force_omit_top_log_row
        )
        # Build sealed interior core around openings in matching warm wood planks.
        # Kept just below the floor line so it meets the floor slab without
        # hanging out under the jetty and covering the corbels.
        build_wall_with_opening(
            bm, p_start, p_end, max(0.0, z_bottom - 0.06), z_top, thickness,
            openings=openings, mat_ext=MAT_INDEX_WOOD, normal_vec=normal_vec,
            tier='TIER_3', physical_siding=False,
            is_corner_start=is_corner_start, is_corner_end=is_corner_end,
            seed=seed, u_offset=u_offset
        )
        return

    # Cut the openings column by column instead of one opening at a time.
    # Towers and shafts stack several windows at the SAME u, and a one-at-a-time
    # pass would let the "above opening" filler of a lower window seal the
    # window above it. Splitting the wall at every opening edge and building the
    # complementary z spans per column keeps every window open.
    u_edges = {0.0, seg_len}
    for op in openings:
        ou1 = max(0.0, min(seg_len, op['u_start']))
        ou2 = max(0.0, min(seg_len, op['u_end']))
        if ou2 - ou1 > 0.01:
            u_edges.add(ou1)
            u_edges.add(ou2)
    edges = sorted(u_edges)

    def _emit(ua, ub, za, zb, seg_is_start, seg_is_end):
        build_wall_segment(
            bm, pt_at(ua), pt_at(ub), za, zb, thickness, mat_ext=mat_ext,
            normal_vec=normal_vec, tier=tier, physical_siding=physical_siding,
            plank_direction=plank_direction, plank_jankiness=plank_jankiness,
            stone_block_scale=stone_block_scale, stone_disorder=stone_disorder,
            is_corner_start=seg_is_start, is_corner_end=seg_is_end, seed=seed,
            u_offset=u_offset + ua, v_offset=za - z_bottom,
            has_exposed_brick=has_exposed_brick, exposed_brick_freq=exposed_brick_freq
        )

    for i in range(len(edges) - 1):
        ua, ub = edges[i], edges[i + 1]
        if ub - ua <= 0.001:
            continue
        spans = []
        for op in openings:
            ou1 = max(0.0, min(seg_len, op['u_start']))
            ou2 = max(0.0, min(seg_len, op['u_end']))
            if ou1 <= ua + 0.005 and ou2 >= ub - 0.005:
                oz1 = max(z_bottom, min(z_top, op['z_start']))
                oz2 = max(z_bottom, min(z_top, op['z_end']))
                if oz2 - oz1 > 0.01:
                    spans.append((oz1, oz2))
        pieces = []
        if spans:
            spans.sort()
            cur = z_bottom
            for (za, zb) in spans:
                if za > cur + 0.005:
                    pieces.append((cur, za))
                cur = max(cur, zb)
            if cur < z_top - 0.005:
                pieces.append((cur, z_top))
        else:
            pieces.append((z_bottom, z_top))
        last_col = (i == len(edges) - 2)
        for pi, (za, zb) in enumerate(pieces):
            _emit(ua, ub, za, zb,
                  seg_is_start=(i == 0 and pi == 0 and is_corner_start),
                  seg_is_end=(last_col and pi == len(pieces) - 1 and is_corner_end))

def build_facade_timber(bm, p_start, p_end, z_bottom, z_top, wall_thickness,
                         normal_vec, openings=[], has_diagonals=True, is_top_floor=False):
    """
    Builds authentic Tudor half-timbering along one exterior facade,
    cleanly cutting around doorways and windows so beams never block openings.
    When is_top_floor is True, the top plate beam is chamfered/inset at the ends to stay under roof eaves.
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
    # Top floor eave plates sit directly under the sloping roof deck: drop them
    # 12cm so the beam top stays below the deck underside instead of poking through.
    if is_top_floor:
        top_z -= 0.12
    top_span = max(0.2, span - 0.32) if is_top_floor else span
    cx, cy, cz = to_world_pt(span * 0.5, top_z)
    create_beveled_box(bm, size=(top_span, beam_d, beam_w), location=(cx, cy, cz), rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)

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
    for i in range(num_pts - 1, -1, -1):
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
    corbel_faces = [f_l, f_r]
    for k in range(M):
        kn = (k + 1) % M
        f_p = bm.faces.new([vl[k], vr[k], vr[kn], vl[kn]])
        f_p.material_index = mat_index
        corbel_faces.append(f_p)
    bmesh.ops.recalc_face_normals(bm, faces=corbel_faces)

    uv_layer = bm.loops.layers.uv.verify()
    inv_rot = rot_m.to_3x3().transposed()
    for f in corbel_faces:
        is_side = (f in (f_l, f_r))
        for loop in f.loops:
            lv = inv_rot @ (loop.vert.co - loc)
            if is_side:
                loop[uv_layer].uv = Vector((lv.y * 0.85, lv.z * 0.85))
            else:
                loop[uv_layer].uv = Vector((lv.x * 0.85, (lv.y + lv.z) * 0.85))

def build_cantilever_corbels(bm, x_min_upper, x_max_upper, y_min_upper, y_max_upper, z_level, overhang_dist=0.35, spacing=1.2, include_front=True, include_back=True, include_left=False, include_right=False, front_exclude_x=None, drop=0.10):
    """
    Builds chunky carved wooden support brackets (corbels) underneath
    the overhanging upper floors for that iconic European fantasy silhouette.
    """
    if overhang_dist < 0.05:
        return
        
    corbel_w = 0.20
    corbel_h = 0.52
    corbel_d = overhang_dist + 0.16
    # Drop the corbel's mounting point below the upper floor's timber top-plate beam
    # so the bracket sits under it instead of poking up through it.
    z_mount = z_level - drop
    # Embed the corbel's inner (wall-side) tip slightly into the wall face so it always
    # makes solid contact instead of just grazing it.
    embed = 0.08
    
    total_x = x_max_upper - x_min_upper
    num_x = max(2, int(total_x / spacing))
    step_x = total_x / (num_x + 1)
    
    # 1. Front and Back Facade corbels
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

    # 1b. Left and Right Facade corbels
    total_y = y_max_upper - y_min_upper
    num_y = max(2, int(total_y / spacing))
    step_y = total_y / (num_y + 1)
    for j in range(1, num_y + 1):
        cy = y_min_upper + j * step_y
        if include_left:
            loc_left = Vector((x_min_upper + overhang_dist + embed, cy, z_mount))
            create_curved_corbel(
                bm, loc=loc_left, facing_dir=(-1.0, 0.0, 0.0),
                width=corbel_w, depth=corbel_d + embed, height=corbel_h,
                mat_index=MAT_INDEX_TIMBER
            )
        if include_right:
            loc_right = Vector((x_max_upper - overhang_dist - embed, cy, z_mount))
            create_curved_corbel(
                bm, loc=loc_right, facing_dir=(1.0, 0.0, 0.0),
                width=corbel_w, depth=corbel_d + embed, height=corbel_h,
                mat_index=MAT_INDEX_TIMBER
            )
            
    # 2. 45-degree diagonal corner corbels for structural fantasy silhouette.
    # Each corner respects BOTH facades it touches, so suppressing one facade
    # (e.g. a pillared overhang) also removes the corner brackets on that side.
    corner_d = corbel_d * 1.15
    if include_front and include_left:
        # Front-Left corner
        if not (front_exclude_x and front_exclude_x[0] <= x_min_upper <= front_exclude_x[1]):
            loc_fl = Vector((x_min_upper + overhang_dist + embed * 0.707, y_min_upper + overhang_dist + embed * 0.707, z_mount))
            create_curved_corbel(bm, loc=loc_fl, facing_dir=(-0.707, -0.707, 0.0),
                                width=corbel_w, depth=corner_d + embed, height=corbel_h)
    if include_front and include_right:
        # Front-Right corner
        if not (front_exclude_x and front_exclude_x[0] <= x_max_upper <= front_exclude_x[1]):
            loc_fr = Vector((x_max_upper - overhang_dist - embed * 0.707, y_min_upper + overhang_dist + embed * 0.707, z_mount))
            create_curved_corbel(bm, loc=loc_fr, facing_dir=(0.707, -0.707, 0.0),
                                width=corbel_w, depth=corner_d + embed, height=corbel_h)
    if include_back and include_left:
        # Back-Left corner
        loc_bl = Vector((x_min_upper + overhang_dist + embed * 0.707, y_max_upper - overhang_dist - embed * 0.707, z_mount))
        create_curved_corbel(bm, loc=loc_bl, facing_dir=(-0.707, 0.707, 0.0),
                            width=corbel_w, depth=corner_d + embed, height=corbel_h)
    if include_back and include_right:
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


def build_open_timber_arcade(bm, p_start, p_end, z_floor, z_top, wall_t=0.28,
                             has_foundation=True, found_h=0.45, bay_spacing=3.2,
                             post_w=0.24, mat_post=MAT_INDEX_TIMBER_FRAME, mat_brace=MAT_INDEX_TIMBER):
    """
    Builds an authentic open timber post-and-beam arcade along a perimeter wall line:
    - Ground stone plinth pedestals under each post (if at ground level with foundation).
    - Chunky vertical timber posts spaced evenly across the span.
    - Continuous horizontal header beam across the top.
    - 45-degree knee braces bracing posts to the header beam.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len = math.sqrt(dx * dx + dy * dy)
    if seg_len < 0.5:
        return

    ux = dx / seg_len
    uy = dy / seg_len
    ang_z = math.atan2(dy, dx)

    # 1. Continuous Top Header Beam
    beam_h = 0.22
    beam_w = post_w
    beam_mid_z = z_top - beam_h * 0.5
    mid_x = (x1 + x2) * 0.5
    mid_y = (y1 + y2) * 0.5

    create_beveled_box(
        bm,
        size=(seg_len + post_w * 0.5, beam_w, beam_h),
        location=(mid_x, mid_y, beam_mid_z),
        rotation=(0.0, 0.0, ang_z),
        mat_index=mat_post,
        bevel_amount=0.012
    )

    # 2. Evenly spaced posts along segment
    n_bays = max(1, int(round(seg_len / bay_spacing)))
    post_h = z_top - z_floor
    post_mid_z = z_floor + post_h * 0.5

    for b_i in range(n_bays + 1):
        t = b_i / float(n_bays)
        px = x1 + dx * t
        py = y1 + dy * t


        # Vertical Timber Post
        create_beveled_box(
            bm,
            size=(post_w, post_w, post_h),
            location=(px, py, post_mid_z),
            rotation=(0.0, 0.0, ang_z),
            mat_index=mat_post,
            bevel_amount=0.014
        )

        # 45-degree Knee Braces to header beam
        brace_len = 0.65
        brace_off = 0.26
        # Forward brace (+ direction along segment)
        if b_i < n_bays and (seg_len / n_bays) >= 1.4:
            bx = px + ux * brace_off
            by = py + uy * brace_off
            bz = z_top - beam_h - brace_off * 0.5
            create_beveled_box(
                bm,
                size=(brace_len, 0.12, 0.12),
                location=(bx, by, bz),
                rotation=(0.0, -0.785, ang_z),
                mat_index=mat_brace,
                bevel_amount=0.008
            )
        # Backward brace (- direction along segment)
        if b_i > 0 and (seg_len / n_bays) >= 1.4:
            bx = px - ux * brace_off
            by = py - uy * brace_off
            bz = z_top - beam_h - brace_off * 0.5
            create_beveled_box(
                bm,
                size=(brace_len, 0.12, 0.12),
                location=(bx, by, bz),
                rotation=(0.0, 0.785, ang_z),
                mat_index=mat_brace,
                bevel_amount=0.008
            )

