"""
Solid double-walled room generator, cantilever corbels, and Tudor timber-framing.
Builds manifold thick walls with cleanly framed door and window cutouts.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box
from .materials import MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER, MAT_INDEX_STONE

def build_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness, mat_ext=MAT_INDEX_PLASTER_EXT, mat_int=MAT_INDEX_PLASTER_INT):
    """
    Builds a solid wall segment between two 2D points with double-walled faces.
    """
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
    
    # We create the wall box
    # Outer faces have plaster exterior, inner faces have plaster interior
    create_box(
        bm,
        size=(seg_len, thickness, height),
        location=(cx, cy, cz),
        rotation=(0.0, 0.0, angle),
        mat_index=mat_ext
    )

def build_wall_with_opening(bm, p_start, p_end, z_bottom, z_top, thickness,
                            openings=[], mat_ext=MAT_INDEX_PLASTER_EXT):
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
        build_wall_segment(bm, p_start, p_end, z_bottom, z_top, thickness, mat_ext)
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
            build_wall_segment(bm, pt_at(last_u), pt_at(ou1), z_bottom, z_top, thickness, mat_ext)
            
        # Below the opening (sill portion)
        if oz1 > z_bottom + 0.01:
            build_wall_segment(bm, pt_at(ou1), pt_at(ou2), z_bottom, oz1, thickness, mat_ext)
            
        # Above the opening (lintel/header portion)
        if oz2 < z_top - 0.01:
            build_wall_segment(bm, pt_at(ou1), pt_at(ou2), oz2, z_top, thickness, mat_ext)
            
        last_u = ou2
        
    # Final wall segment after last opening
    if last_u < seg_len - 0.01:
        build_wall_segment(bm, pt_at(last_u), pt_at(seg_len), z_bottom, z_top, thickness, mat_ext)

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
    
    beam_w = 0.14
    beam_d = 0.06
    h = z_top - z_bottom
    
    # Exterior surface offset from wall centerline
    ext_dist = wall_thickness * 0.5 + beam_d * 0.4
    
    def to_world_pt(u, z):
        wx = x1 + ux * u + nx * ext_dist
        wy = y1 + uy * u + ny * ext_dist
        return (wx, wy, z)

    angle = math.atan2(dy, dx)

    # 1. Top Plate Beam (under the ceiling / floor above)
    top_z = z_top - beam_w * 0.5
    cx, cy, cz = to_world_pt(span * 0.5, top_z)
    create_beveled_box(bm, size=(span, beam_d, beam_w), location=(cx, cy, cz), rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

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
                    create_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx1, cy1, cz1), rotation=rot_euler1, mat_index=MAT_INDEX_TIMBER)
                    
                    # Right brace: rises from (u_b, z_bot_top) to (u_b - diag_w, z_mid_bot)
                    T2 = Vector((-math.cos(alpha) * ux, -math.cos(alpha) * uy, math.sin(alpha)))
                    B2 = N_vec.cross(T2).normalized()
                    rot_mat2 = Matrix([T2, N_vec, B2]).transposed()
                    rot_euler2 = rot_mat2.to_euler('XYZ')
                    
                    u_c2 = u_b - diag_w * 0.5 - 0.02
                    cx2, cy2, cz2 = to_world_pt(u_c2, z_c1)
                    create_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx2, cy2, cz2), rotation=rot_euler2, mat_index=MAT_INDEX_TIMBER)
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
                    create_box(bm, size=(diag_len, beam_d * 0.85, beam_w * 0.8), location=(cx1, cy1, cz1), rotation=rot_euler1, mat_index=MAT_INDEX_TIMBER)

def build_timber_framing(bm, x_min, x_max, y_min, y_max, z_bottom, z_top,
                         wall_thickness=0.28,
                         front_ops=[], back_ops=[], left_ops=[], right_ops=[],
                         has_diagonals=True):
    """
    Builds classic stylized Tudor half-timbering with corner posts, top/bottom plates,
    mid-rails, and diagonal braces, cleanly cutting around all openings.
    """
    beam_w = 0.14
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
            size=(beam_w, beam_w, h),
            location=(cx, cy, z_bottom + h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012
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

def build_cantilever_corbels(bm, x_min_upper, x_max_upper, y_min_upper, y_max_upper, z_level, overhang_dist=0.35, spacing=1.2, include_front=True, include_back=True, front_exclude_x=None):
    """
    Builds chunky carved wooden support brackets (corbels) underneath
    the overhanging upper floors for that iconic European fantasy silhouette.
    """
    if overhang_dist < 0.05:
        return
        
    corbel_w = 0.16
    corbel_h = 0.35
    corbel_d = overhang_dist + 0.12
    
    total_x = x_max_upper - x_min_upper
    num_x = max(2, int(total_x / spacing))
    step_x = total_x / (num_x + 1)
    
    for i in range(1, num_x + 1):
        cx = x_min_upper + i * step_x
        # Front corbel
        if include_front:
            if not (front_exclude_x and front_exclude_x[0] <= cx <= front_exclude_x[1]):
                create_beveled_box(
                    bm,
                    size=(corbel_w, corbel_d, corbel_h),
                    location=(cx, y_min_upper + corbel_d * 0.4, z_level - corbel_h * 0.5),
                    mat_index=MAT_INDEX_TIMBER,
                    bevel_amount=0.015
                )
        # Back corbel
        if include_back:
            create_beveled_box(
                bm,
                size=(corbel_w, corbel_d, corbel_h),
                location=(cx, y_max_upper - corbel_d * 0.4, z_level - corbel_h * 0.5),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.015
            )

def build_cantilever_soffit(bm, lower_bounds, upper_bounds, z_level, soffit_thick=0.10, front_exclude_x=None):
    """
    Builds solid wooden soffit plates sealing the underside of the overhanging upper floor.
    lower_bounds: (lx_min, lx_max, ly_min, ly_max)
    upper_bounds: (ux_min, ux_max, uy_min, uy_max)
    """
    lx_min, lx_max, ly_min, ly_max = lower_bounds
    ux_min, ux_max, uy_min, uy_max = upper_bounds
    cz = z_level - soffit_thick * 0.5
    
    # Front soffit (from uy_min to ly_min)
    if uy_min < ly_min:
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
    if uy_max > ly_max:
        d = uy_max - ly_max + 0.05
        w = ux_max - ux_min + 0.05
        cy = (uy_max + ly_max) * 0.5
        cx = (ux_min + ux_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Left soffit (from ux_min to lx_min)
    if ux_min < lx_min:
        w = lx_min - ux_min + 0.05
        d = ly_max - ly_min + 0.05
        cx = (ux_min + lx_min) * 0.5
        cy = (ly_min + ly_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Right soffit (from lx_max to ux_max)
    if ux_max > lx_max:
        w = ux_max - lx_max + 0.05
        d = ly_max - ly_min + 0.05
        cx = (lx_max + ux_max) * 0.5
        cy = (ly_min + ly_max) * 0.5
        create_beveled_box(bm, size=(w, d, soffit_thick), location=(cx, cy, cz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
