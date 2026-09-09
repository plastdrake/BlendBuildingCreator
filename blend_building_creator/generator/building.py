"""
Master Building Generator Orchestrator for Stylized Fantasy Buildings.
Coordinates foundation, double-walled floors, walk-in doorways, intermediate floor slabs,
staircases, ceiling beams, roofs, shingles, dormers, and chimneys into a unified mesh.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, apply_box_uvs, add_wonkiness
from .materials import (
    setup_building_material_slots,
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_TIMBER, MAT_INDEX_FLOOR, MAT_INDEX_SHINGLES,
    MAT_INDEX_GLASS, MAT_INDEX_DOOR, MAT_INDEX_IRON
)
from .walls import build_wall_with_opening, build_timber_framing, build_cantilever_corbels, build_cantilever_soffit
from .interior import (
    build_floor_slab, build_ceiling_beams, build_straight_staircase,
    build_spiral_staircase, build_attic_trusses, build_stair_guardrail
)
from .openings import build_door_assembly, build_front_steps, build_window_assembly, build_iron_lantern
from .roof import build_sway_roof, build_gable_roof, build_conical_turret_roof, build_shingle_layers, build_dormer, build_fantasy_chimney

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
        # On upper floors, extend slab to cover the outer wall perimeter below (eliminates Z-overlap)
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
            build_cantilever_corbels(bm, x_min, x_max, y_min, y_max, z_floor, overhang_dist=overhang_step)
            build_cantilever_soffit(
                bm,
                (prev_x_min, prev_x_max, prev_y_min, prev_y_max),
                (x_min, x_max, y_min, y_max),
                z_floor
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
        
        # Upper floor safety guardrail around stair opening (safely inset onto floor slab with L-shaped return)
        if fl_idx > 0 and props.has_stairs and cur_stair_hole is not None:
            sh_x1, sh_x2, sh_y1, sh_y2 = cur_stair_hole
            rail_x = min(slab_xmax - 0.10, sh_x2 + 0.07)
            if props.stair_style == 'SPIRAL':
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=sh_y1, x_start=sh_x1 + 0.20)
            else:
                ret_y = sh_y1 if (fl_idx % 2 == 1) else sh_y2
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=ret_y, x_start=sh_x1 + 0.20)
        
        # Determine next flight of stairs leading up to fl_idx + 1
        next_stair_hole = None
        if fl_idx < num_floors - 1 and props.has_stairs:
            if props.stair_style == 'SPIRAL':
                spiral_r = min(1.15, props.stair_width * 1.05)
                spiral_cx = fl0_ix_min + spiral_r + 0.15
                spiral_cy = fl0_iy_max - spiral_r - 0.15
                fl_start_ang = -90.0 + fl_idx * 30.0
                build_spiral_staircase(
                    bm,
                    center_pos=(spiral_cx, spiral_cy, z_floor + 0.05),
                    target_z=z_ceil + 0.05,
                    radius=spiral_r,
                    start_ang_deg=fl_start_ang,
                    total_angle_deg=360.0
                )
                # Headroom cutout leaves the landing sector (Y < spiral_cy - 0.10) solid
                next_stair_hole = (slab_xmin, spiral_cx + spiral_r + 0.08,
                                   spiral_cy - 0.10, slab_ymax)
            else:
                # Straight stairs: Floor 0 -> 1 runs front to back (+Y)
                # Floor 1 -> 2 runs back to front (-Y) on adjacent track (switchback)
                if fl_idx % 2 == 0:
                    # Flight going front to back (+Y)
                    stair_start = (stair_cx_0, stair_y_bot, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=1)
                    next_stair_hole = (slab_xmin, stair_cx_0 + stair_w * 0.5 + 0.22,
                                       stair_y_bot - 0.25, stair_y_top + 0.10)
                else:
                    # Flight going back to front (-Y) on adjacent bay
                    stair_start = (stair_cx_1, stair_y_top, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=-1)
                    next_stair_hole = (stair_cx_1 - stair_w * 0.5 - 0.12, stair_cx_1 + stair_w * 0.5 + 0.22,
                                       stair_y_bot - 0.10, stair_y_top + 0.25)
            
            # Store cutout for the floor above
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
        
        # Doorway on Floor 0
        if fl_idx == 0 and props.has_front_door:
            dw = props.door_width
            dh = props.door_height
            door_center_u = cur_w * 0.5
            door_u1 = door_center_u - dw * 0.5
            door_u2 = door_center_u + dw * 0.5
            front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh})
            
            # Door assembly (frame, casing, openable door leaf, hinges)
            build_door_assembly(
                bm,
                center_x=0.0,
                y_front=y_min,
                z_base=z_floor,
                wall_thickness=wall_t,
                door_w=dw,
                door_h=dh,
                door_angle_deg=props.door_angle
            )
            # Front stone entrance steps (solidly grounded to Z = 0)
            if props.has_front_steps and props.has_foundation:
                build_front_steps(bm, center_x=0.0, y_front=y_min, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)))
                
            # Front entrance lantern
            if props.has_lanterns:
                build_iron_lantern(bm, location=(dw * 0.5 + 0.45, y_min - 0.05, z_floor + dh * 0.8))

        # Windows on this floor
        win_w = props.window_width
        win_h = props.window_height
        win_cz = z_floor + floor_h * 0.48
        win_z1 = win_cz - win_h * 0.5
        win_z2 = win_cz + win_h * 0.5
        
        # Front windows (fl_idx > 0 or if door is off-center / multi-window)
        if fl_idx > 0 and props.has_windows:
            for side in [-1, 1]:
                wx = side * (cur_w * 0.26)
                wu = (wx - x_min)
                front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm,
                    center=(wx, y_min, win_cz),
                    size=(win_w, win_h),
                    wall_thickness=wall_t,
                    normal_axis='-Y',
                    has_shutters=props.has_shutters,
                    has_flower_box=props.has_flower_boxes
                )
        elif fl_idx == 0 and props.has_windows and cur_w > 4.5:
            # Flank door with small window to the right if building is wide enough
            wx = cur_w * 0.30
            wu = (wx - x_min)
            front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
            build_window_assembly(
                bm,
                center=(wx, y_min, win_cz),
                size=(win_w, win_h),
                wall_thickness=wall_t,
                normal_axis='-Y',
                has_shutters=props.has_shutters,
                has_flower_box=props.has_flower_boxes
            )

        # Back windows
        if props.has_windows:
            for side in [-0.25, 0.25]:
                wx = cur_w * side
                wu = (wx - x_min)
                back_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm,
                    center=(wx, y_max, win_cz),
                    size=(win_w, win_h),
                    wall_thickness=wall_t,
                    normal_axis='+Y',
                    has_shutters=props.has_shutters,
                    has_flower_box=False
                )

        # Side windows (Left and Right)
        if props.has_windows and cur_d > 3.0:
            wy = 0.0 # Center along Y
            wu = (wy - y_min)
            
            # Left window (omit on floor 0 if stairs are occupying the left wall)
            if not (fl_idx == 0 and props.has_stairs):
                left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                build_window_assembly(
                    bm,
                    center=(x_min, wy, win_cz),
                    size=(win_w, win_h),
                    wall_thickness=wall_t,
                    normal_axis='-X',
                    has_shutters=props.has_shutters,
                    has_flower_box=props.has_flower_boxes
                )
                
            # Right window (always unobstructed)
            right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
            build_window_assembly(
                bm,
                center=(x_max, wy, win_cz),
                size=(win_w, win_h),
                wall_thickness=wall_t,
                normal_axis='+X',
                has_shutters=props.has_shutters,
                has_flower_box=props.has_flower_boxes
            )

        # 4 Solid Walls with Openings
        # Front: (x_min, y_min) -> (x_max, y_min)
        build_wall_with_opening(bm, (x_min, y_min), (x_max, y_min), z_floor, z_ceil, wall_t, front_openings)
        # Back: (x_min, y_max) -> (x_max, y_max)
        build_wall_with_opening(bm, (x_min, y_max), (x_max, y_max), z_floor, z_ceil, wall_t, back_openings)
        # Left: (x_min, y_min) -> (x_min, y_max)
        build_wall_with_opening(bm, (x_min, y_min), (x_min, y_max), z_floor, z_ceil, wall_t, left_openings)
        # Right: (x_max, y_min) -> (x_max, y_max)
        build_wall_with_opening(bm, (x_max, y_min), (x_max, y_max), z_floor, z_ceil, wall_t, right_openings)
        
        # Tudor Timber Framing on Exterior (with all openings properly cut out)
        if props.has_timber_framing:
            build_timber_framing(
                bm, x_min, x_max, y_min, y_max, z_floor, z_ceil,
                wall_thickness=wall_t,
                front_ops=front_openings,
                back_ops=back_openings,
                left_ops=left_openings,
                right_ops=right_openings,
                has_diagonals=props.timber_diagonals
            )

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
    
    # Interior Roof Trusses & Collar Beams (visible inside attic)
    build_attic_trusses(
        bm,
        x_min=-top_hx + wall_t, x_max=top_hx - wall_t,
        y_min=-top_hy + wall_t, y_max=top_hy - wall_t,
        z_base=top_z,
        ridge_z=top_z + props.roof_height,
        spacing=1.4
    )
    
    # Exterior Roof Construction
    roof_style = props.roof_style
    if roof_style == 'SWAY':
        build_sway_roof(
            bm,
            x_min=-top_hx, x_max=top_hx,
            y_min=-top_hy, y_max=top_hy,
            z_base=top_z,
            roof_height=props.roof_height,
            overhang=props.roof_overhang,
            sway_amount=props.roof_sway,
            wall_thickness=wall_t
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
            wall_thickness=wall_t
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
