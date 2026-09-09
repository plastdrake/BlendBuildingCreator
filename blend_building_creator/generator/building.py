"""
Master Building Generator Orchestrator for Stylized Fantasy Buildings.
Coordinates foundation, double-walled floors, walk-in doorways, intermediate floor slabs,
staircases, ceiling beams, roofs, shingles, dormers, and chimneys into a unified mesh.
Supports Rectangular, L-Shaped, T-Shaped, and Round Tower footprint architectures.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone, apply_box_uvs, add_wonkiness
from .materials import (
    setup_building_material_slots,
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_TIMBER, MAT_INDEX_FLOOR, MAT_INDEX_SHINGLES,
    MAT_INDEX_GLASS, MAT_INDEX_DOOR, MAT_INDEX_IRON
)
from .walls import (
    build_wall_with_opening, build_timber_framing, build_facade_timber,
    build_cantilever_corbels, build_cantilever_soffit
)
from .interior import (
    build_floor_slab, build_ceiling_beams, build_straight_staircase,
    build_spiral_staircase, build_attic_trusses, build_stair_guardrail
)
from .openings import build_door_assembly, build_front_steps, build_window_assembly, build_iron_lantern
from .roof import build_sway_roof, build_gable_roof, build_conical_turret_roof, build_shingle_layers, build_dormer, build_fantasy_chimney

def get_facade_window_positions(span_min, span_max, target_spacing=2.4, min_margin=0.85):
    """
    Computes dynamic window center positions along a facade segment.
    Automatically scales window count smoothly as width or depth increases.
    """
    length = span_max - span_min
    avail = length - min_margin * 2.0
    if avail < 0.4:
        return []
    
    count = max(1, int(round(avail / target_spacing)))
    if count == 1:
        return [(span_min + span_max) * 0.5]
    step = avail / max(1, count - 1)
    return [span_min + min_margin + i * step for i in range(count)]

def build_round_tower(bm, props, seed):
    """
    Generates an 8-sided faceted fantasy wizard tower with conical turret spire roof,
    centered spiral staircase, stone foundation, and glowing windows.
    """
    num_floors = max(1, props.num_floors)
    floor_h = props.floor_height
    radius = max(1.8, props.width * 0.45)
    wall_t = props.wall_thickness
    found_h = props.foundation_height if props.has_foundation else 0.4
    cantilever = props.cantilever_overhang if props.has_cantilever else 0.0
    total_height = found_h + num_floors * floor_h + props.roof_height
    
    num_facets = 8
    d_ang = 2.0 * math.pi / num_facets
    offset_ang = -math.pi / num_facets

    # Foundation
    if props.has_foundation:
        f_r = radius + 0.30
        create_cylinder(bm, radius=f_r, height=found_h, segments=8,
                        location=(0.0, 0.0, found_h * 0.5), mat_index=MAT_INDEX_STONE)
        create_cylinder(bm, radius=f_r + 0.10, height=0.12, segments=8,
                        location=(0.0, 0.0, found_h - 0.06), mat_index=MAT_INDEX_STONE)

    # Multi-floor loop
    prev_r = radius
    cur_r = radius
    
    for fl_idx in range(num_floors):
        z_floor = found_h + fl_idx * floor_h
        z_ceil = z_floor + floor_h
        fl_overhang = cantilever if (fl_idx >= 1 and props.has_cantilever) else 0.0
        cur_r = radius + fl_overhang

        # Floor slab
        mat_fl = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_FLOOR
        create_cylinder(bm, radius=cur_r - 0.02, height=0.12, segments=8,
                        location=(0.0, 0.0, z_floor + 0.06), mat_index=mat_fl)
        
        # Cantilever corbels under the 8 vertices
        if fl_idx > 0 and fl_overhang > 0.01:
            for k in range(num_facets):
                ang = k * d_ang + offset_ang
                cx = prev_r * math.cos(ang)
                cy = prev_r * math.sin(ang)
                create_beveled_box(bm, size=(0.16, 0.16, 0.35),
                                   location=(cx, cy, z_floor - 0.18),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)

        # Stairs
        if fl_idx < num_floors - 1 and props.has_stairs:
            stair_r = min(cur_r - wall_t - 0.25, 1.10)
            build_spiral_staircase(
                bm,
                center_pos=(0.0, 0.0, z_floor + 0.05),
                target_z=z_ceil + 0.05,
                radius=stair_r,
                start_ang_deg=-90.0,
                total_angle_deg=360.0
            )

        # Ceiling beams
        if props.has_ceiling_beams:
            beam_d = 0.16
            create_box(bm, size=(cur_r * 1.8, 0.14, beam_d), location=(0.0, 0.0, z_ceil - beam_d * 0.5), mat_index=MAT_INDEX_TIMBER)
            create_box(bm, size=(0.14, cur_r * 1.8, beam_d), location=(0.0, 0.0, z_ceil - beam_d * 0.5), mat_index=MAT_INDEX_TIMBER)

        # 8 Wall Facets
        win_w = min(1.0, props.window_width)
        win_h = props.window_height
        win_cz = z_floor + floor_h * 0.48
        
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        phys_siding = getattr(props, 'physical_siding', True)
        plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')
        plank_jank = getattr(props, 'plank_jankiness', 0.35)
        stone_scale = getattr(props, 'stone_block_scale', 1.0)
        stone_disorder = getattr(props, 'stone_disorder', 0.35)
        if tier_val == 'TIER_1':
            mat_w = MAT_INDEX_TIMBER
        elif tier_val == 'TIER_2':
            mat_w = MAT_INDEX_TIMBER
        else:
            mat_w = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_PLASTER_EXT
        
        for k in range(num_facets):
            a1 = k * d_ang + offset_ang
            a2 = (k + 1) * d_ang + offset_ang
            p1 = (cur_r * math.cos(a1), cur_r * math.sin(a1))
            p2 = (cur_r * math.cos(a2), cur_r * math.sin(a2))
            
            facet_len = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            openings = []
            
            # Corner post at p1
            create_beveled_box(bm, size=(0.14, 0.14, floor_h),
                               location=(p1[0], p1[1], z_floor + floor_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            
            # Outward normal for this facet
            mid_pt = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
            fn_vec = Vector((mid_pt[0], mid_pt[1], 0.0)).normalized()
            
            # Facet 6 is the front facet (facing -Y)
            if fl_idx == 0 and k == 6 and props.has_front_door:
                dw = min(facet_len - 0.4, props.door_width)
                dh = props.door_height
                u1 = (facet_len - dw) * 0.5
                u2 = u1 + dw
                openings.append({'u_start': u1, 'u_end': u2, 'z_start': z_floor, 'z_end': z_floor + dh})
                door_mid = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
                build_door_assembly(bm, center_x=door_mid[0], y_front=door_mid[1], z_base=z_floor,
                                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle)
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=door_mid[0], y_front=door_mid[1], z_base=z_floor,
                                      num_steps=max(2, int(found_h / 0.18)))
            elif props.has_windows and (k % 2 == 1 or (fl_idx > 0 and k == 6)):
                if facet_len > win_w + 0.4:
                    u1 = (facet_len - win_w) * 0.5
                    u2 = u1 + win_w
                    win_z1 = win_cz - win_h * 0.5
                    win_z2 = win_cz + win_h * 0.5
                    openings.append({'u_start': u1, 'u_end': u2, 'z_start': win_z1, 'z_end': win_z2})
                    facing_angle = math.atan2(fn_vec.x, -fn_vec.y)
                    build_window_assembly(bm, center=(mid_pt[0], mid_pt[1], win_cz), size=(win_w, win_h),
                                          wall_thickness=wall_t, normal_axis=facing_angle,
                                          has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes)

            build_wall_with_opening(
                bm, p1, p2, z_floor, z_ceil, wall_t, openings,
                mat_ext=mat_w, normal_vec=(fn_vec.x, fn_vec.y), tier=tier_val,
                physical_siding=phys_siding, plank_direction=plank_dir,
                plank_jankiness=plank_jank, stone_block_scale=stone_scale,
                stone_disorder=stone_disorder, seed=seed + k * 17
            )

        prev_r = cur_r

    # Conical Turret Roof
    top_z = found_h + num_floors * floor_h
    top_r = cur_r
    build_conical_turret_roof(bm, center_pos=(0.0, 0.0, top_z), radius=top_r * 1.15, height=props.roof_height * 1.25, segments=16)

    # Chimney
    if props.has_chimney:
        chim_h = total_height + 0.8
        build_fantasy_chimney(
            bm,
            pos_xy=(top_r * 0.65, top_r * 0.45),
            z_start=0.0,
            total_height=chim_h,
            width=0.75, depth=0.75,
            crooked_angle=0.05
        )

def generate_building(obj, props):
    """
    Main generator function called when properties change or generate button is clicked.
    Constructs the building inside obj.data.
    """
    bm = bmesh.new()
    
    # 1. Dimensions setup
    seed = props.seed
    num_floors = max(1, props.num_floors)
    floor_h = props.floor_height
    base_w = props.width
    base_d = props.depth
    wall_t = props.wall_thickness
    cantilever = props.cantilever_overhang if props.has_cantilever else 0.0
    found_h = props.foundation_height if props.has_foundation else 0.2
    
    # Compound building shape setup (L-Shape, T-Shape, Round Tower)
    shape = getattr(props, 'building_shape', 'RECTANGLE')
    if shape == 'ROUND_TOWER':
        build_round_tower(bm, props, seed)
        if props.wonkiness > 0.001:
            total_h = found_h + num_floors * floor_h + props.roof_height
            add_wonkiness(bm, z_min=0.0, z_max=total_h, amount=props.wonkiness, seed=seed)
        apply_box_uvs(bm, scale=1.0)
        setup_building_material_slots(obj, props)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        return

    has_wing = shape in ('L_SHAPE', 'T_SHAPE')
    wing_floors = min(num_floors, max(1, getattr(props, 'wing_floors', 1)))
    wing_w = min(base_w * 0.70, max(2.5, getattr(props, 'wing_width', 3.5)))
    wing_d = max(2.0, getattr(props, 'wing_depth', 3.0))
    wing_side = getattr(props, 'wing_side', 'RIGHT')
    
    if shape == 'L_SHAPE':
        if wing_side == 'LEFT':
            wx_base_min = -base_w * 0.5
            wx_base_max = -base_w * 0.5 + wing_w
        else: # 'RIGHT'
            wx_base_min = base_w * 0.5 - wing_w
            wx_base_max = base_w * 0.5
    else: # 'T_SHAPE'
        wx_base_min = -wing_w * 0.5
        wx_base_max = wing_w * 0.5
    wy_base_min = -base_d * 0.5 - wing_d
    wy_base_max = -base_d * 0.5
    
    # Track overall bounding box for wonkiness
    total_height = found_h + num_floors * floor_h + props.roof_height
    
    # 2. Foundation Base
    if props.has_foundation:
        fw = base_w + 0.35
        fd = base_d + 0.35
        create_beveled_box(
            bm,
            size=(fw, fd, found_h),
            location=(0.0, 0.0, found_h * 0.5),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.04
        )
        # Decorative stone plinth trim
        create_beveled_box(
            bm,
            size=(fw + 0.12, fd + 0.12, 0.12),
            location=(0.0, 0.0, found_h - 0.06),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )
        # Foundation for Wing
        if has_wing:
            w_fw = wing_w + 0.35
            w_fd = wing_d + 0.35
            w_fcx = (wx_base_min + wx_base_max) * 0.5
            w_fcy = (wy_base_min + wy_base_max) * 0.5
            create_beveled_box(
                bm,
                size=(w_fw, w_fd, found_h),
                location=(w_fcx, w_fcy, found_h * 0.5),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.04
            )
        
    # 3. Multi-Floor Loop
    prev_fl_overhang = 0.0
    prev_x_min, prev_x_max = -base_w * 0.5, base_w * 0.5
    prev_y_min, prev_y_max = -base_d * 0.5, base_d * 0.5

    # Ground floor master interior reference for staircase
    fl0_ix_min = -base_w * 0.5 + wall_t
    fl0_ix_max =  base_w * 0.5 - wall_t
    fl0_iy_min = -base_d * 0.5 + wall_t
    fl0_iy_max =  base_d * 0.5 - wall_t

    stair_w = props.stair_width
    landing_depth = 0.85
    stair_cx_0 = fl0_ix_min + 0.06 + stair_w * 0.5
    stair_cx_1 = stair_cx_0 + stair_w + 0.20
    
    stair_y_top = fl0_iy_max - landing_depth
    stair_len = min(2.4, max(1.8, (fl0_iy_max - fl0_iy_min) - landing_depth - 1.0))
    stair_y_bot = stair_y_top - stair_len

    # Track stair holes per floor
    floor_stair_holes = {}

    for fl_idx in range(num_floors):
        z_floor = found_h + fl_idx * floor_h
        z_ceil = z_floor + floor_h
        fl_has_wing = has_wing and (fl_idx < wing_floors)
        
        # Upper floor cantilever expansion
        if props.has_cantilever:
            if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                fl_overhang = cantilever if fl_idx >= 1 else 0.0
            else: # ALL_FLOORS
                fl_overhang = fl_idx * cantilever
        else:
            fl_overhang = 0.0

        cur_w = base_w + fl_overhang * 2.0
        cur_d = base_d + fl_overhang * 2.0
        
        hx = cur_w * 0.5
        hy = cur_d * 0.5
        
        x_min, x_max = -hx, hx
        y_min, y_max = -hy, hy
        
        # Solid floor slab bounds
        if fl_idx > 0:
            slab_xmin = x_min - wall_t * 0.45
            slab_xmax = x_max + wall_t * 0.45
            slab_ymin = y_min - wall_t * 0.45
            slab_ymax = y_max + wall_t * 0.45
        else:
            slab_xmin = x_min + 0.03
            slab_xmax = x_max - 0.03
            slab_ymin = y_min + 0.03
            slab_ymax = y_max - 0.03
        
        # Interior bounds for current floor room
        ix_min, ix_max = x_min + wall_t, x_max - wall_t
        iy_min, iy_max = y_min + wall_t, y_max - wall_t
        
        # Corbels and solid wooden soffit underneath upper floor overhang
        if fl_idx > 0 and fl_overhang > prev_fl_overhang:
            overhang_step = fl_overhang - prev_fl_overhang
            front_ex = (wx_base_min - 0.15, wx_base_max + 0.15) if (has_wing and fl_idx >= wing_floors) else None
            build_cantilever_corbels(bm, x_min, x_max, y_min, y_max, z_floor,
                                    overhang_dist=overhang_step, front_exclude_x=front_ex)
            build_cantilever_soffit(
                bm,
                (prev_x_min, prev_x_max, prev_y_min, prev_y_max),
                (x_min, x_max, y_min, y_max),
                z_floor,
                front_exclude_x=front_ex
            )

        # Determine staircase cutout for this floor (if coming from below)
        cur_stair_hole = floor_stair_holes.get(fl_idx, None)

        # Floor Slab (Ground floor is stone/timber; upper floors have stair cutout)
        floor_mat = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_FLOOR
        build_floor_slab(
            bm,
            floor_idx=fl_idx,
            x_min=slab_xmin, x_max=slab_xmax,
            y_min=slab_ymin, y_max=slab_ymax,
            z_level=z_floor + 0.05,
            thickness=0.12,
            stair_hole=cur_stair_hole if (fl_idx > 0 and props.has_stairs) else None,
            mat_idx=floor_mat
        )
        
        # Upper floor safety guardrail around stair opening
        if fl_idx > 0 and props.has_stairs and cur_stair_hole is not None:
            sh_x1, sh_x2, sh_y1, sh_y2 = cur_stair_hole
            # Solid timber trimmer sill plate only when there is an actual void gap between stairwell and wall
            if (sh_x1 - ix_min) > 0.18:
                create_beveled_box(
                    bm,
                    size=(0.14, (sh_y2 - sh_y1) + 0.08, 0.14),
                    location=(sh_x1 - 0.07, (sh_y1 + sh_y2) * 0.5, z_floor + 0.05),
                    mat_index=MAT_INDEX_TIMBER,
                    bevel_amount=0.015
                )
            rail_x = min(slab_xmax - 0.10, sh_x2 + 0.07)
            if props.stair_style == 'SPIRAL':
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=sh_y1, x_start=sh_x1 + 0.20)
            else:
                # Straight stairs: only guard open void on the top floor where no more stairs ascend
                # On intermediate floors, the ascending flight's own handrail protects the opening
                if fl_idx == num_floors - 1:
                    ret_y = sh_y1 if (fl_idx % 2 == 1) else sh_y2
                    build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                          return_y=ret_y, x_start=sh_x1 + 0.20)
        
        # Wing floor slab for compound shapes
        if fl_has_wing:
            if shape == 'L_SHAPE':
                if wing_side == 'LEFT':
                    wx_min = x_min
                    wx_max = x_min + (wing_w + fl_overhang * 2.0)
                else:
                    wx_min = x_max - (wing_w + fl_overhang * 2.0)
                    wx_max = x_max
            else: # T_SHAPE
                wx_min = -(wing_w + fl_overhang * 2.0) * 0.5
                wx_max =  (wing_w + fl_overhang * 2.0) * 0.5
            wy_min = y_min - (wing_d + fl_overhang)
            wy_max = y_min

            if fl_idx > 0:
                w_slab_xmin = wx_min - wall_t * 0.45
                w_slab_xmax = wx_max + wall_t * 0.45
                w_slab_ymin = wy_min - wall_t * 0.45
            else:
                w_slab_xmin = wx_min + 0.03
                w_slab_xmax = wx_max - 0.03
                w_slab_ymin = wy_min + 0.03
            w_slab_ymax = y_min + 0.05
            build_floor_slab(
                bm,
                floor_idx=fl_idx,
                x_min=w_slab_xmin, x_max=w_slab_xmax,
                y_min=w_slab_ymin, y_max=w_slab_ymax,
                z_level=z_floor + 0.05,
                thickness=0.12,
                stair_hole=None,
                mat_idx=floor_mat
            )
            if fl_idx > 0 and fl_overhang > prev_fl_overhang:
                overhang_step = fl_overhang - prev_fl_overhang
                # ONLY exterior front edge, NEVER interior ceiling junction
                build_cantilever_corbels(bm, wx_min, wx_max, wy_min, wy_max, z_floor,
                                        overhang_dist=overhang_step, include_back=False)

        # Determine next flight of stairs leading up to fl_idx + 1
        next_stair_hole = None
        if fl_idx < num_floors - 1 and props.has_stairs:
            if props.stair_style == 'SPIRAL':
                spiral_r = min(1.15, props.stair_width * 1.05)
                spiral_cx = fl0_ix_min + spiral_r + 0.15
                spiral_cy = fl0_iy_max - spiral_r - 0.15
                fl_start_ang = -90.0
                build_spiral_staircase(
                    bm,
                    center_pos=(spiral_cx, spiral_cy, z_floor + 0.05),
                    target_z=z_ceil + 0.05,
                    radius=spiral_r,
                    start_ang_deg=fl_start_ang,
                    total_angle_deg=360.0
                )
                # Headroom cutout envelopes the entire circular stair path
                next_stair_hole = (ix_min + 0.02, spiral_cx + spiral_r + 0.08,
                                   spiral_cy - spiral_r - 0.06, min(iy_max, spiral_cy + spiral_r + 0.06))
            else:
                # Straight stairs: Floor 0 -> 1 runs front to back (+Y)
                # Floor 1 -> 2 runs back to front (-Y) on adjacent track (switchback)
                if fl_idx % 2 == 0:
                    stair_start = (stair_cx_0, stair_y_bot, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=1)
                    next_stair_hole = (ix_min + 0.02, stair_cx_0 + stair_w * 0.5 + 0.22,
                                       stair_y_bot - 0.25, stair_y_top + 0.10)
                else:
                    stair_start = (stair_cx_1, stair_y_top, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=-1)
                    next_stair_hole = (stair_cx_1 - stair_w * 0.5 - 0.12, stair_cx_1 + stair_w * 0.5 + 0.22,
                                       stair_y_bot - 0.10, stair_y_top + 0.25)
            
            floor_stair_holes[fl_idx + 1] = next_stair_hole

        # Ceiling Beams (underneath next floor, trimmed around stairs)
        if props.has_ceiling_beams:
            build_ceiling_beams(
                bm, ix_min, ix_max, iy_min, iy_max, z_ceil - 0.02, spacing=1.2,
                stair_hole=next_stair_hole if (fl_idx < num_floors - 1 and props.has_stairs) else None
            )
                
        # Openings definitions for this floor
        front_openings = []
        back_openings = []
        left_openings = []
        right_openings = []
        
        w_front_openings = []
        w_left_openings = []
        w_right_openings = []

        win_w = props.window_width
        win_h = props.window_height
        win_cz = z_floor + floor_h * 0.48
        win_z1 = win_cz - win_h * 0.5
        win_z2 = win_cz + win_h * 0.5

        # Doorway placement
        if fl_idx == 0 and props.has_front_door:
            dw = props.door_width
            dh = props.door_height
            if shape == 'RECTANGLE':
                door_cx = 0.0
                door_yf = y_min
                door_u1 = (door_cx - dw * 0.5) - x_min
                door_u2 = (door_cx + dw * 0.5) - x_min
                front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh})
            elif shape == 'L_SHAPE':
                if wing_side == 'RIGHT':
                    door_cx = (x_min + wx_min) * 0.5
                else:
                    door_cx = (wx_max + x_max) * 0.5
                door_yf = y_min
                door_u1 = (door_cx - dw * 0.5) - x_min
                door_u2 = (door_cx + dw * 0.5) - x_min
                front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh})
            else: # T_SHAPE
                door_cx = (wx_min + wx_max) * 0.5
                door_yf = wy_min
                door_u1 = (door_cx - dw * 0.5) - wx_min
                door_u2 = (door_cx + dw * 0.5) - wx_min
                w_front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh})

            build_door_assembly(
                bm, center_x=door_cx, y_front=door_yf, z_base=z_floor,
                wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle
            )
            if props.has_front_steps and props.has_foundation:
                build_front_steps(bm, center_x=door_cx, y_front=door_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)))
            if props.has_lanterns:
                build_iron_lantern(bm, location=(door_cx + dw * 0.5 + 0.45, door_yf - 0.05, z_floor + dh * 0.8))

        # Interior walk-through portal between main building and wing
        if fl_has_wing:
            portal_w = max(2.2, (wx_max - wx_min) - 0.45)
            portal_h = floor_h * 0.82
            p_cx = (wx_min + wx_max) * 0.5
            p_u1 = (p_cx - portal_w * 0.5) - x_min
            p_u2 = (p_cx + portal_w * 0.5) - x_min
            front_openings.append({'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h})
            
            # Timber portal archway framing encasing full wall depth
            jamb_w = 0.18
            jamb_d = wall_t + 0.05
            create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                               location=(p_cx - portal_w * 0.5 - jamb_w * 0.5, y_min, z_floor + portal_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                               location=(p_cx + portal_w * 0.5 + jamb_w * 0.5, y_min, z_floor + portal_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            lintel_w = portal_w + jamb_w * 2.0 + 0.08
            lintel_d = wall_t + 0.06
            lintel_h = 0.20
            create_beveled_box(bm, size=(lintel_w, lintel_d, lintel_h),
                               location=(p_cx, y_min, z_floor + portal_h + lintel_h * 0.5),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)

        # Dynamic Windows - Front Wall
        if props.has_windows:
            front_win_xs = []
            w_top_roof_z = (found_h + wing_floors * floor_h + props.roof_height * 0.88) if has_wing else 0.0
            wing_roof_occludes = has_wing and (z_floor < w_top_roof_z + 0.3)
            
            # Door exclusion zone calculation on floor 0
            has_door_here = (fl_idx == 0 and props.has_front_door and shape in ('RECTANGLE', 'L_SHAPE'))
            if has_door_here:
                door_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                door_clr_left = door_clr
                door_clr_right = door_clr + (0.35 if props.has_lanterns else 0.0)
                d_ex1 = door_cx - door_clr_left
                d_ex2 = door_cx + door_clr_right
            else:
                d_ex1, d_ex2 = 999.0, -999.0

            def get_cleared_spans(s_min, s_max):
                """Subdivides a facade interval to strictly exclude the front door envelope."""
                if not has_door_here or s_max <= d_ex1 or s_min >= d_ex2:
                    return [(s_min, s_max)]
                spans = []
                if d_ex1 - s_min >= win_w + 0.35:
                    spans.append((s_min, d_ex1))
                if s_max - d_ex2 >= win_w + 0.35:
                    spans.append((d_ex2, s_max))
                return spans

            if not fl_has_wing and not wing_roof_occludes:
                if fl_idx > 0:
                    front_win_xs = get_facade_window_positions(x_min, x_max, target_spacing=2.4, min_margin=0.9)
                else:
                    for s1, s2 in get_cleared_spans(x_min, x_max):
                        if props.has_stairs and cur_w < 6.0 and s1 < 0.0:
                            continue
                        front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=2.2, min_margin=0.7))
            else:
                # Compound shapes or floors occluded by wing roof:
                # Place windows only along exposed spans with 1.2m corner clearance
                if shape == 'L_SHAPE':
                    if wing_side == 'RIGHT':
                        exp_x1, exp_x2 = x_min, wx_base_min - 1.20
                    else:
                        exp_x1, exp_x2 = wx_base_max + 1.20, x_max
                    if (exp_x2 - exp_x1) > 1.2:
                        for s1, s2 in get_cleared_spans(exp_x1, exp_x2):
                            front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=2.4, min_margin=0.75))
                else: # T_SHAPE
                    if (wx_base_min - 1.20 - x_min) > 1.2:
                        for s1, s2 in get_cleared_spans(x_min, wx_base_min - 1.20):
                            front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=2.4, min_margin=0.75))
                    if (x_max - (wx_base_max + 1.20)) > 1.2:
                        for s1, s2 in get_cleared_spans(wx_base_max + 1.20, x_max):
                            front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=2.4, min_margin=0.75))

            # Strict safety filter: ensure no window lies within door exclusion envelope
            if has_door_here:
                front_win_xs = [wx for wx in front_win_xs if (wx < d_ex1 or wx > d_ex2)]

            for wx in front_win_xs:
                wu = (wx - x_min)
                front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(wx, y_min, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-Y',
                    has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                )

        # Dynamic Windows - Back Wall
        if props.has_windows:
            back_win_xs = get_facade_window_positions(x_min, x_max, target_spacing=2.4, min_margin=0.9)
            for wx in back_win_xs:
                wu = (wx - x_min)
                back_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(wx, y_max, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+Y',
                    has_shutters=props.has_shutters, has_flower_box=False
                )

        # Dynamic Windows - Side Walls (Left and Right)
        if props.has_windows and cur_d > 2.8:
            side_win_ys = get_facade_window_positions(y_min, y_max, target_spacing=2.4, min_margin=0.9)
            # Left side
            for wy in side_win_ys:
                if fl_idx == 0 and props.has_stairs and (wy > stair_y_bot - 0.2 and wy < stair_y_top + 0.2):
                    continue
                wu = (wy - y_min)
                left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(x_min, wy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-X',
                    has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                )
            # Right side
            for wy in side_win_ys:
                wu = (wy - y_min)
                right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(x_max, wy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+X',
                    has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                )

        # Dynamic Windows - Wing Walls
        if fl_has_wing and props.has_windows:
            # Wing Front
            if not (fl_idx == 0 and shape == 'T_SHAPE'):
                w_win_xs = get_facade_window_positions(wx_min, wx_max, target_spacing=2.2, min_margin=0.85)
                for wwx in w_win_xs:
                    wu = (wwx - wx_min)
                    w_front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                    build_window_assembly(
                        bm, center=(wwx, wy_min, win_cz), size=(win_w, win_h),
                        wall_thickness=wall_t, normal_axis='-Y',
                        has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                    )
            # Wing Left & Right: Enforce 1.25m clearance from re-entrant corner at wy_max
            if (wy_max - 1.25) - (wy_min + 0.85) > 0.8:
                w_win_ys = get_facade_window_positions(wy_min + 0.85, wy_max - 1.25, target_spacing=2.4, min_margin=0.6)
            else:
                w_win_ys = [(wy_min + wy_max - 0.4) * 0.5] if (wy_max - wy_min > 2.2) else []
                
            for wwy in w_win_ys:
                wu = (wwy - wy_min)
                w_left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(wx_min, wwy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-X',
                    has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                )
                w_right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm, center=(wx_max, wwy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+X',
                    has_shutters=props.has_shutters, has_flower_box=props.has_flower_boxes
                )

        # 4 Main Solid Walls with Openings
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val == 'TIER_1':
            mat_w = MAT_INDEX_TIMBER
        elif tier_val == 'TIER_2':
            mat_w = MAT_INDEX_TIMBER
        else:
            mat_w = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_PLASTER_EXT

        phys_siding = getattr(props, 'physical_siding', True)
        plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')
        plank_jank = getattr(props, 'plank_jankiness', 0.35)
        stone_scale = getattr(props, 'stone_block_scale', 1.0)
        stone_disorder = getattr(props, 'stone_disorder', 0.35)

        wall_top_z = z_ceil

        build_wall_with_opening(
            bm, (x_min, y_min), (x_max, y_min), z_floor, wall_top_z, wall_t, front_openings,
            mat_ext=mat_w, normal_vec=(0.0, -1.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
        )
        build_wall_with_opening(
            bm, (x_min, y_max), (x_max, y_max), z_floor, wall_top_z, wall_t, back_openings,
            mat_ext=mat_w, normal_vec=(0.0, 1.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
        )
        build_wall_with_opening(
            bm, (x_min, y_min), (x_min, y_max), z_floor, wall_top_z, wall_t, left_openings,
            mat_ext=mat_w, normal_vec=(-1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
        )
        build_wall_with_opening(
            bm, (x_max, y_min), (x_max, y_max), z_floor, wall_top_z, wall_t, right_openings,
            mat_ext=mat_w, normal_vec=(1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
        )
        
        # Wing Solid Walls
        if fl_has_wing:
            build_wall_with_opening(
                bm, (wx_min, wy_min), (wx_max, wy_min), z_floor, wall_top_z, wall_t, w_front_openings,
                mat_ext=mat_w, normal_vec=(0.0, -1.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
            )
            build_wall_with_opening(
                bm, (wx_min, wy_min), (wx_min, wy_max), z_floor, wall_top_z, wall_t, w_left_openings,
                mat_ext=mat_w, normal_vec=(-1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
            )
            build_wall_with_opening(
                bm, (wx_max, wy_min), (wx_max, wy_max), z_floor, wall_top_z, wall_t, w_right_openings,
                mat_ext=mat_w, normal_vec=(1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
                plank_direction=plank_dir, plank_jankiness=plank_jank,
                stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed
            )

        # Tudor Timber Framing on Exterior
        if props.has_timber_framing:
            beam_w = 0.14
            # 1. Main building corner posts
            corners = [
                (x_min, y_max),
                (x_max, y_max),
            ]
            if not fl_has_wing:
                corners.extend([(x_min, y_min), (x_max, y_min)])
            else:
                if shape == 'L_SHAPE':
                    if wing_side == 'RIGHT':
                        corners.append((x_min, y_min))
                    else:
                        corners.append((x_max, y_min))
                else: # T_SHAPE
                    corners.extend([(x_min, y_min), (x_max, y_min)])
                    
            for cx, cy in corners:
                create_beveled_box(
                    bm, size=(beam_w, beam_w, floor_h),
                    location=(cx, cy, z_floor + floor_h * 0.5),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
                )

            # 2. Main building exterior facades
            build_facade_timber(bm, (x_min, y_max), (x_max, y_max), z_floor, z_ceil, wall_t,
                                (0.0, 1.0), back_openings, props.timber_diagonals)
            build_facade_timber(bm, (x_min, y_min), (x_min, y_max), z_floor, z_ceil, wall_t,
                                (-1.0, 0.0), left_openings, props.timber_diagonals)
            build_facade_timber(bm, (x_max, y_min), (x_max, y_max), z_floor, z_ceil, wall_t,
                                (1.0, 0.0), right_openings, props.timber_diagonals)

            # Front wall: only exposed exterior spans (no framing across interior junction)
            if not fl_has_wing:
                build_facade_timber(bm, (x_min, y_min), (x_max, y_min), z_floor, z_ceil, wall_t,
                                    (0.0, -1.0), front_openings, props.timber_diagonals)
            else:
                if shape == 'L_SHAPE':
                    if wing_side == 'RIGHT':
                        exp_ops = [op for op in front_openings if op.get('u_end', 0) <= (wx_min - x_min) + 0.01]
                        build_facade_timber(bm, (x_min, y_min), (wx_min, y_min), z_floor, z_ceil, wall_t,
                                            (0.0, -1.0), exp_ops, props.timber_diagonals)
                    else:
                        exp_ops = []
                        for op in front_openings:
                            u1 = op.get('u_start', 0) - (wx_max - x_min)
                            u2 = op.get('u_end', 0) - (wx_max - x_min)
                            if u1 >= -0.01:
                                exp_ops.append({'u_start': u1, 'u_end': u2, 'z_start': op['z_start'], 'z_end': op['z_end']})
                        build_facade_timber(bm, (wx_max, y_min), (x_max, y_min), z_floor, z_ceil, wall_t,
                                            (0.0, -1.0), exp_ops, props.timber_diagonals)
                else: # T_SHAPE
                    exp_ops_l = [op for op in front_openings if op.get('u_end', 0) <= (wx_min - x_min) + 0.01]
                    build_facade_timber(bm, (x_min, y_min), (wx_min, y_min), z_floor, z_ceil, wall_t,
                                        (0.0, -1.0), exp_ops_l, props.timber_diagonals)
                    exp_ops_r = []
                    for op in front_openings:
                        u1 = op.get('u_start', 0) - (wx_max - x_min)
                        u2 = op.get('u_end', 0) - (wx_max - x_min)
                        if u1 >= -0.01:
                            exp_ops_r.append({'u_start': u1, 'u_end': u2, 'z_start': op['z_start'], 'z_end': op['z_end']})
                    build_facade_timber(bm, (wx_max, y_min), (x_max, y_min), z_floor, z_ceil, wall_t,
                                        (0.0, -1.0), exp_ops_r, props.timber_diagonals)

            # 3. Wing exterior facades (ONLY exterior faces, NEVER interior junction at wy_max)
            if fl_has_wing:
                # Lower wing timber frame slightly beneath wall top/ceiling to eliminate coplanar Z conflict
                w_timber_z_top = z_ceil - 0.06
                w_post_h = floor_h - 0.06
                w_post_cz = z_floor + w_post_h * 0.5
                
                # Wing front corner posts
                create_beveled_box(bm, size=(beam_w, beam_w, w_post_h),
                                   location=(wx_min, wy_min, w_post_cz),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
                create_beveled_box(bm, size=(beam_w, beam_w, w_post_h),
                                   location=(wx_max, wy_min, w_post_cz),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
                # Wing front facade
                build_facade_timber(bm, (wx_min, wy_min), (wx_max, wy_min), z_floor, w_timber_z_top, wall_t,
                                    (0.0, -1.0), w_front_openings, props.timber_diagonals)
                # Wing left facade
                build_facade_timber(bm, (wx_min, wy_min), (wx_min, wy_max), z_floor, w_timber_z_top, wall_t,
                                    (-1.0, 0.0), w_left_openings, props.timber_diagonals)
                # Wing right facade
                build_facade_timber(bm, (wx_max, wy_min), (wx_max, wy_max), z_floor, w_timber_z_top, wall_t,
                                    (1.0, 0.0), w_right_openings, props.timber_diagonals)

        # Update previous floor tracking for overhang transitions
        prev_fl_overhang = fl_overhang
        prev_x_min, prev_x_max = x_min, x_max
        prev_y_min, prev_y_max = y_min, y_max

    # 4. Roof & Attic Level
    top_fl_idx = num_floors - 1
    if props.has_cantilever:
        if props.overhang_mode == 'SECOND_FLOOR_ONLY':
            top_overhang = cantilever if top_fl_idx >= 1 else 0.0
        else:
            top_overhang = top_fl_idx * cantilever
    else:
        top_overhang = 0.0

    top_w = base_w + top_overhang * 2.0
    top_d = base_d + top_overhang * 2.0
    top_hx = top_w * 0.5
    top_hy = top_d * 0.5
    top_z = found_h + num_floors * floor_h
    roof_style = props.roof_style
    
    # Attic floor plate (embedded into wall core with zero gap)
    build_floor_slab(
        bm,
        floor_idx=num_floors,
        x_min=-top_hx + 0.03, x_max=top_hx - 0.03,
        y_min=-top_hy + 0.03, y_max=top_hy - 0.03,
        z_level=top_z + 0.05,
        thickness=0.12,
        stair_hole=floor_stair_holes.get(num_floors, None),
        mat_idx=MAT_INDEX_FLOOR
    )
    
    # Interior Roof Trusses & Collar Beams (visible inside attic, safe clearance under sway)
    build_attic_trusses(
        bm,
        x_min=-top_hx + wall_t, x_max=top_hx - wall_t,
        y_min=-top_hy + wall_t, y_max=top_hy - wall_t,
        z_base=top_z,
        ridge_z=top_z + props.roof_height,
        spacing=1.4,
        sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0
    )
    
    # Exterior Roof Construction
    tier_val = getattr(props, 'material_tier', 'TIER_3')
    plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')

    if roof_style == 'SWAY':
        build_sway_roof(
            bm,
            x_min=-top_hx, x_max=top_hx,
            y_min=-top_hy, y_max=top_hy,
            z_base=top_z,
            roof_height=props.roof_height,
            overhang=props.roof_overhang,
            sway_amount=props.roof_sway,
            wall_thickness=wall_t,
            tier=tier_val,
            plank_direction=plank_dir
        )
    elif roof_style == 'TURRET':
        radius = max(top_hx, top_hy) * 1.05
        build_conical_turret_roof(
            bm,
            center_pos=(0.0, 0.0, top_z),
            radius=radius,
            height=props.roof_height * 1.3
        )
    else: # 'GABLE'
        build_gable_roof(
            bm,
            x_min=-top_hx, x_max=top_hx,
            y_min=-top_hy, y_max=top_hy,
            z_base=top_z,
            roof_height=props.roof_height,
            overhang=props.roof_overhang,
            wall_thickness=wall_t,
            segments_y=6,
            tier=tier_val,
            plank_direction=plank_dir
        )

    # Roof Hoist Beam with Cargo Hook (Warehouse / freight feature)
    if getattr(props, 'has_hoist_beam', False) and roof_style in ('SWAY', 'GABLE'):
        from .roof import build_hoist_beam
        build_hoist_beam(
            bm,
            front_x=0.0,
            front_y=-top_hy - props.roof_overhang,
            z_ridge=top_z + props.roof_height,
            length=1.4
        )
        
    # Roof Shingles
    if props.has_roof_shingles and roof_style in ('SWAY', 'GABLE'):
        build_shingle_layers(
            bm,
            x_min=-top_hx, x_max=top_hx,
            y_min=-top_hy, y_max=top_hy,
            z_base=top_z,
            roof_height=props.roof_height,
            rows=props.shingle_rows,
            seed=seed,
            overhang=props.roof_overhang,
            sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0,
            roof_style=roof_style
        )

    # Compound Shape Wing Roof (Cross-Gable intersecting main roof or upper facade)
    if has_wing:
        w_top_fl = min(wing_floors, num_floors)
        is_lower_wing = (wing_floors < num_floors)
        w_fl_idx = w_top_fl - 1
        
        if props.has_cantilever:
            if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                w_overhang = cantilever if w_fl_idx >= 1 else 0.0
            else:
                w_overhang = w_fl_idx * cantilever
        else:
            w_overhang = 0.0

        # Main building coordinates at the wing's top floor height
        w_main_hx = (base_w + w_overhang * 2.0) * 0.5
        w_main_hy = (base_d + w_overhang * 2.0) * 0.5
        w_main_front_y = -w_main_hy

        if shape == 'L_SHAPE':
            if wing_side == 'LEFT':
                w_top_xmin = -w_main_hx
                w_top_xmax = -w_main_hx + (wing_w + w_overhang * 2.0)
            else:
                w_top_xmin = w_main_hx - (wing_w + w_overhang * 2.0)
                w_top_xmax = w_main_hx
        else: # T_SHAPE
            w_top_xmin = -(wing_w + w_overhang * 2.0) * 0.5
            w_top_xmax =  (wing_w + w_overhang * 2.0) * 0.5
            
        w_top_ymin = w_main_front_y - (wing_d + w_overhang)
        w_top_z = found_h + w_top_fl * floor_h
        w_roof_h = props.roof_height * 0.88

        if is_lower_wing:
            # Upper facade front wall coordinate directly above the wing
            if props.has_cantilever:
                if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                    up_fl_overhang = cantilever if w_top_fl >= 1 else 0.0
                else:
                    up_fl_overhang = w_top_fl * cantilever
            else:
                up_fl_overhang = 0.0
            up_front_y = -(base_d + up_fl_overhang * 2.0) * 0.5
            w_top_ymax = up_front_y + 0.04 # Embedded 4cm into wall plaster, zero interior intrusion!
            abut_back = True

            # Interior ceiling slab for the wing (enclosing the wing interior from above)
            build_floor_slab(
                bm,
                floor_idx=w_top_fl,
                x_min=w_top_xmin + 0.02,
                x_max=w_top_xmax - 0.02,
                y_min=w_top_ymin + 0.02,
                y_max=w_main_front_y + 0.02,
                z_level=w_top_z - 0.02,
                thickness=0.10,
                stair_hole=None,
                mat_idx=MAT_INDEX_FLOOR
            )
            # Exposed wooden ceiling beams in wing interior
            if props.has_ceiling_beams:
                build_ceiling_beams(
                    bm,
                    x_min=w_top_xmin + wall_t,
                    x_max=w_top_xmax - wall_t,
                    y_min=w_top_ymin + wall_t,
                    y_max=w_main_front_y,
                    z_ceil=w_top_z - 0.02,
                    spacing=1.2
                )
        else:
            w_top_ymax = -top_hy + 0.25 # Intersects with main roof attic
            abut_back = False

        if props.roof_style == 'SWAY':
            build_sway_roof(
                bm,
                x_min=w_top_xmin, x_max=w_top_xmax,
                y_min=w_top_ymin, y_max=w_top_ymax,
                z_base=w_top_z,
                roof_height=w_roof_h,
                overhang=props.roof_overhang,
                sway_amount=props.roof_sway * 0.70,
                segments_y=6,
                wall_thickness=wall_t,
                gable_ends=('FRONT',),
                abut_back=abut_back,
                tier=tier_val,
                plank_direction=plank_dir
            )
            if props.has_roof_shingles:
                build_shingle_layers(
                    bm,
                    x_min=w_top_xmin, x_max=w_top_xmax,
                    y_min=w_top_ymin, y_max=w_top_ymax,
                    z_base=w_top_z,
                    roof_height=w_roof_h,
                    rows=max(4, int(props.shingle_rows * (wing_d / max(1.0, base_d)))),
                    seed=seed + 101,
                    overhang=props.roof_overhang,
                    sway_amount=props.roof_sway * 0.70,
                    roof_style='SWAY',
                    abut_back=abut_back
                )
        else:
            build_gable_roof(
                bm,
                x_min=w_top_xmin, x_max=w_top_xmax,
                y_min=w_top_ymin, y_max=w_top_ymax,
                z_base=w_top_z,
                roof_height=w_roof_h,
                overhang=props.roof_overhang,
                wall_thickness=wall_t,
                gable_ends=('FRONT',),
                segments_y=6,
                abut_back=abut_back,
                tier=tier_val,
                plank_direction=plank_dir
            )
            if props.has_roof_shingles:
                build_shingle_layers(
                    bm,
                    x_min=w_top_xmin, x_max=w_top_xmax,
                    y_min=w_top_ymin, y_max=w_top_ymax,
                    z_base=w_top_z,
                    roof_height=w_roof_h,
                    rows=max(4, int(props.shingle_rows * (wing_d / max(1.0, base_d)))),
                    seed=seed + 101,
                    overhang=props.roof_overhang,
                    sway_amount=0.0,
                    roof_style='GABLE',
                    abut_back=abut_back
                )
        
    # Dormer Windows
    if props.has_dormers and roof_style in ('SWAY', 'GABLE'):
        dormer_y = -top_hy * 0.5
        build_dormer(
            bm,
            center_x=0.0,
            center_y=dormer_y,
            z_base=top_z + props.roof_height * 0.25,
            dormer_w=1.2, dormer_d=1.5, dormer_h=1.3
        )
        
    # Stylized Crooked Chimney
    if props.has_chimney:
        chim_x = top_hx * 0.72
        chim_y = top_hy * 0.45
        chim_total_h = total_height + 0.8
        build_fantasy_chimney(
            bm,
            pos_xy=(chim_x, chim_y),
            z_start=0.0,
            total_height=chim_total_h,
            width=0.9, depth=0.9,
            crooked_angle=0.05
        )

    # 5. Whimsical Curvature / Wonkiness Deformation
    if props.wonkiness > 0.001:
        add_wonkiness(bm, z_min=0.0, z_max=total_height, amount=props.wonkiness, seed=seed)
        
    # 6. Apply UVs
    apply_box_uvs(bm, scale=1.0)
    
    # 7. Setup Material Slots and procedural node shaders BEFORE transferring bmesh
    setup_building_material_slots(obj, props)
    
    # 8. Commit bmesh to object mesh data (preserves material slot mapping)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
