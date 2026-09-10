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
from .mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone, apply_box_uvs, add_wonkiness, apply_organic_shading
from .materials import (
    setup_building_material_slots,
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_TIMBER, MAT_INDEX_FLOOR, MAT_INDEX_SHINGLES,
    MAT_INDEX_GLASS, MAT_INDEX_DOOR, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_LOG_END
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
from .roof import build_sway_roof, build_gable_roof, build_conical_turret_roof, build_shingle_layers, build_dormer, build_roof_turret, build_fantasy_chimney
from .accessories import (
    build_blacksmith_forge, build_windmill_sails, build_watchtower_lookout,
    build_tavern_porch_and_sign, build_fisherman_stilts, build_bakery_oven,
    build_warehouse_cargo, build_mini_wing, build_balcony, build_pillared_overhang
)

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
        if fl_idx == 0 or not props.has_stairs:
            create_cylinder(bm, radius=cur_r - 0.02, height=0.12, segments=8,
                            location=(0.0, 0.0, z_floor + 0.06), mat_index=mat_fl)
        else:
            # Build 8-faceted annular floor with central stairwell opening
            stair_r = min(cur_r - wall_t - 0.25, 1.10)
            well_r = stair_r + 0.08
            ring_dr = (cur_r - 0.02) - well_r
            if ring_dr > 0.15:
                mid_r = well_r + ring_dr * 0.5
                sec_w = 2.0 * mid_r * math.tan(math.pi / 8.0) * 1.05
                for k in range(num_facets):
                    ang = (k + 0.5) * d_ang + offset_ang
                    fcx = mid_r * math.cos(ang)
                    fcy = mid_r * math.sin(ang)
                    create_beveled_box(
                        bm,
                        size=(ring_dr, sec_w, 0.12),
                        location=(fcx, fcy, z_floor + 0.06),
                        rotation=(0.0, 0.0, ang),
                        mat_index=mat_fl,
                        bevel_amount=0.01
                    )
            else:
                create_cylinder(bm, radius=cur_r - 0.02, height=0.12, segments=8,
                                location=(0.0, 0.0, z_floor + 0.06), mat_index=mat_fl)
        
            # Walkable landing bridge connecting spiral staircase exit to the annular floor
            create_beveled_box(
                bm,
                size=(0.60, well_r * 0.95, 0.12),
                location=(0.0, -well_r * 0.52, z_floor + 0.06),
                mat_index=mat_fl,
                bevel_amount=0.01
            )
        
        # Cantilever corbels under the 8 vertices
        if fl_idx > 0 and fl_overhang > 0.01:
            for k in range(num_facets):
                ang = k * d_ang + offset_ang
                cx = prev_r * math.cos(ang)
                cy = prev_r * math.sin(ang)
                create_beveled_box(bm, size=(0.16, 0.16, 0.35),
                                   location=(cx, cy, z_floor - 0.18),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.015)

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

        # Ceiling beams (radial when stairs present to keep central void completely clear)
        if props.has_ceiling_beams:
            beam_d = 0.16
            if props.has_stairs:
                stair_r = min(cur_r - wall_t - 0.25, 1.10)
                well_r = stair_r + 0.08
                beam_span = max(0.25, (cur_r - 0.05) - well_r)
                beam_mid_r = well_r + beam_span * 0.5
                for k in range(num_facets):
                    b_ang = k * d_ang + offset_ang
                    bx = beam_mid_r * math.cos(b_ang)
                    by = beam_mid_r * math.sin(b_ang)
                    create_box(
                        bm,
                        size=(beam_span, 0.14, beam_d),
                        location=(bx, by, z_ceil - beam_d * 0.5),
                        rotation=(0.0, 0.0, b_ang),
                        mat_index=MAT_INDEX_WOOD
                    )
            else:
                create_box(bm, size=(cur_r * 1.8, 0.14, beam_d), location=(0.0, 0.0, z_ceil - beam_d * 0.5), mat_index=MAT_INDEX_WOOD)
                create_box(bm, size=(0.14, cur_r * 1.8, beam_d), location=(0.0, 0.0, z_ceil - beam_d * 0.5), mat_index=MAT_INDEX_WOOD)

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
                               mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
            
            # Outward normal for this facet
            mid_pt = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
            fn_vec = Vector((mid_pt[0], mid_pt[1], 0.0)).normalized()
            
            # Facet 6 is the front facet (facing -Y)
            if fl_idx == 0 and k == 6 and props.has_front_door:
                dw = min(facet_len - 0.4, props.door_width)
                dh = props.door_height
                frame_margin = 0.13
                u1 = (facet_len - dw) * 0.5 - frame_margin
                u2 = (facet_len + dw) * 0.5 + frame_margin
                openings.append({'u_start': max(0.02, u1), 'u_end': min(facet_len - 0.02, u2), 'z_start': z_floor, 'z_end': z_floor + dh + frame_margin})
                door_mid = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
                build_door_assembly(bm, center_x=door_mid[0], y_front=door_mid[1], z_base=z_floor,
                                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone)
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

    # Conical Turret Roof / Watchtower Lookout Deck
    top_z = found_h + num_floors * floor_h
    top_r = cur_r
    archetype = getattr(props, 'building_archetype', 'AUTO')
    if archetype != 'WATCHTOWER':
        build_conical_turret_roof(bm, center_pos=(0.0, 0.0, top_z), radius=top_r * 1.15, height=props.roof_height * 1.25, segments=16)

    # Chimney
    if props.has_chimney and archetype != 'WATCHTOWER':
        chim_h = total_height + 0.8
        build_fantasy_chimney(
            bm,
            pos_xy=(top_r * 0.65, top_r * 0.45),
            z_start=0.0,
            total_height=chim_h,
            width=0.75, depth=0.75,
            crooked_angle=0.05
        )

    # Architectural Archetype Accessories for Round Tower
    if archetype == 'WINDMILL':
        hub_z = top_z - 0.35
        build_windmill_sails(bm, cx=0.0, front_y=-top_r, hub_z=hub_z, radius=max(2.8, top_r * 1.8), wall_y=-top_r + 0.35)
    elif archetype == 'WATCHTOWER':
        build_watchtower_lookout(bm, -top_r, top_r, -top_r, top_r, z_platform=top_z)


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
    
    # Archetype resolution
    archetype = getattr(props, 'building_archetype', 'AUTO')
    if archetype == 'AUTO':
        if getattr(props, 'has_hoist_beam', False):
            archetype = 'WAREHOUSE'
        else:
            archetype = 'NONE'
    effective_archetype = archetype

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
        apply_organic_shading(obj)
        try:
            from ..operators import get_props_dict
            import json
            obj["building_settings"] = json.dumps(get_props_dict(props))
        except Exception:
            pass
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
    main_door_cx = 0.0
    main_door_yf = -base_d * 0.5
    
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

    # Track stair holes and wall bounds per floor
    floor_stair_holes = {}
    floor_wall_bounds = {}

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

        # Upper floor jettying over pillared overhang colonnade
        if getattr(props, 'has_pillared_overhang', False) and fl_idx >= 1:
            p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
            p_depth = getattr(props, 'pillared_overhang_depth', 1.6)
            if p_side == 'FRONT':
                y_min -= p_depth
            elif p_side == 'BACK':
                y_max += p_depth
            elif p_side == 'LEFT':
                x_min -= p_depth
            elif p_side == 'RIGHT':
                x_max += p_depth

        floor_wall_bounds[fl_idx] = (x_min, x_max, y_min, y_max)
        
        # Solid floor slab bounds (covers full expanded footprint — interior+overhang share floor, soffit hides underside)
        slab_xmin = x_min + 0.03
        slab_xmax = x_max - 0.03
        slab_ymin = y_min + 0.03
        slab_ymax = y_max - 0.03
        
        # Interior bounds for current floor room
        ix_min, ix_max = x_min + wall_t, x_max - wall_t
        iy_min, iy_max = y_min + wall_t, y_max - wall_t
        
        # Wing coordinates if this floor has an active wing
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

        # Corbels and solid wooden soffit underneath upper floor overhang
        if fl_idx > 0 and fl_overhang > prev_fl_overhang:
            overhang_step = fl_overhang - prev_fl_overhang
            # Exclude interior wing junction from exterior cantilever corbels/soffits
            front_ex = (wx_min - 0.05, wx_max + 0.05) if fl_has_wing else None
            has_po = getattr(props, 'has_pillared_overhang', False)
            po_s = getattr(props, 'pillared_overhang_side', 'FRONT')
            inc_f = not (has_po and po_s == 'FRONT')
            inc_b = not (has_po and po_s == 'BACK')
            build_cantilever_corbels(bm, x_min, x_max, y_min, y_max, z_floor,
                                    overhang_dist=overhang_step, front_exclude_x=front_ex,
                                    include_front=inc_f, include_back=inc_b)
            build_cantilever_soffit(
                bm,
                (prev_x_min, prev_x_max, prev_y_min, prev_y_max),
                (x_min, x_max, y_min, y_max),
                z_floor,
                front_exclude_x=front_ex,
                include_front=inc_f,
                include_back=inc_b
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
            # Solid wing floor slab bounds (strictly inside exterior wall perimeter)
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
                # Compute previous wing bounds for cantilever soffit
                if shape == 'L_SHAPE':
                    if wing_side == 'LEFT':
                        prev_w_xmin = prev_x_min
                        prev_w_xmax = prev_x_min + (wing_w + prev_fl_overhang * 2.0)
                        w_inc_l = False # flush with main left wall, covered by main soffit
                        w_inc_r = True
                    else:
                        prev_w_xmin = prev_x_max - (wing_w + prev_fl_overhang * 2.0)
                        prev_w_xmax = prev_x_max
                        w_inc_l = True
                        w_inc_r = False # flush with main right wall
                else: # T_SHAPE
                    prev_w_xmin = -(wing_w + prev_fl_overhang * 2.0) * 0.5
                    prev_w_xmax =  (wing_w + prev_fl_overhang * 2.0) * 0.5
                    w_inc_l = True
                    w_inc_r = True
                prev_w_ymin = prev_y_min - (wing_d + prev_fl_overhang)
                prev_w_ymax = prev_y_min

                build_cantilever_soffit(
                    bm,
                    (prev_w_xmin, prev_w_xmax, prev_w_ymin, prev_w_ymax),
                    (wx_min, wx_max, wy_min, wy_max),
                    z_floor,
                    include_front=True,
                    include_back=False,
                    include_left=w_inc_l,
                    include_right=w_inc_r
                )

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
            frame_margin = 0.13
            if shape == 'RECTANGLE':
                door_cx = 0.0
                door_yf = y_min
                door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh + frame_margin})
            elif shape == 'L_SHAPE':
                if wing_side == 'RIGHT':
                    door_cx = (x_min + wx_min) * 0.5
                else:
                    door_cx = (wx_max + x_max) * 0.5
                door_yf = y_min
                door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh + frame_margin})
            else: # T_SHAPE
                door_cx = (wx_min + wx_max) * 0.5
                door_yf = wy_min
                door_u1 = (door_cx - dw * 0.5 - frame_margin) - wx_min
                door_u2 = (door_cx + dw * 0.5 + frame_margin) - wx_min
                w_front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': z_floor + dh + frame_margin})

            main_door_cx = door_cx
            main_door_yf = door_yf

            build_door_assembly(
                bm, center_x=door_cx, y_front=door_yf, z_base=z_floor,
                wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone
            )
            if props.has_front_steps and props.has_foundation and effective_archetype != 'TAVERN':
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
            
            jamb_w = 0.22
            jamb_d = wall_t + 0.12
            inset = 0.035
            lower = 0.018
            create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                               location=(p_cx - portal_w * 0.5 - jamb_w * 0.5, y_min + inset, z_floor + portal_h * 0.5 - lower*0.5),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
            create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                               location=(p_cx + portal_w * 0.5 + jamb_w * 0.5, y_min + inset, z_floor + portal_h * 0.5 - lower*0.5),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
            lintel_w = portal_w + jamb_w * 2.0 + 0.12
            lintel_d = wall_t + 0.12
            lintel_h = 0.22
            create_beveled_box(bm, size=(lintel_w, lintel_d, lintel_h),
                               location=(p_cx, y_min + inset, z_floor + portal_h + lintel_h * 0.5 - lower),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)

        # Walk-in portal into mini-wing outcrop
        has_mw = getattr(props, 'has_mini_wing', False)
        mw_side = getattr(props, 'mini_wing_side', 'LEFT')
        mw_floor_mode = getattr(props, 'mini_wing_floor', 'GROUND')
        mw_fl = 0 if mw_floor_mode == 'GROUND' else min(num_floors - 1, 1)
        mw_w = getattr(props, 'mini_wing_width', 2.2)

        if has_mw and fl_idx == mw_fl:
            mw_portal_w = min(1.30, mw_w - 0.45)
            mw_portal_h = min(2.20, floor_h * 0.80)
            if mw_side in ('FRONT', 'BACK'):
                mw_u_mid = (x_max - x_min) * 0.5
            else:
                mw_u_mid = (y_max - y_min) * 0.5
            
            mw_op = {
                'u_start': mw_u_mid - mw_portal_w * 0.5,
                'u_end': mw_u_mid + mw_portal_w * 0.5,
                'z_start': z_floor,
                'z_end': z_floor + mw_portal_h
            }
            jamb_w = 0.16
            jamb_d = wall_t + 0.05
            if mw_side == 'FRONT':
                front_openings.append(mw_op)
                p_cx = (x_min + x_max) * 0.5
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5, y_min, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5, y_min, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                lintel_w = mw_portal_w + jamb_w * 2.0 + 0.06
                lintel_h = 0.18
                create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                   location=(p_cx, y_min, z_floor + mw_portal_h + lintel_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'BACK':
                back_openings.append(mw_op)
                p_cx = (x_min + x_max) * 0.5
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5, y_max, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5, y_max, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                lintel_w = mw_portal_w + jamb_w * 2.0 + 0.06
                lintel_h = 0.18
                create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                   location=(p_cx, y_max, z_floor + mw_portal_h + lintel_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'LEFT':
                left_openings.append(mw_op)
                p_cy = (y_min + y_max) * 0.5
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_min, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_min, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                lintel_w = mw_portal_w + jamb_w * 2.0 + 0.06
                lintel_h = 0.18
                create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                   location=(x_min, p_cy, z_floor + mw_portal_h + lintel_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'RIGHT':
                right_openings.append(mw_op)
                p_cy = (y_min + y_max) * 0.5
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_max, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_max, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                lintel_w = mw_portal_w + jamb_w * 2.0 + 0.06
                lintel_h = 0.18
                create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                   location=(x_max, p_cy, z_floor + mw_portal_h + lintel_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

        # Balcony Doorway Cutout
        has_balc = getattr(props, 'has_balcony', False) and num_floors >= 2
        b_side = getattr(props, 'balcony_side', 'FRONT')
        b_fl = min(num_floors, max(2, getattr(props, 'balcony_floor', 2)))
        balc_fl_idx = b_fl - 1
        b_width = getattr(props, 'balcony_width', 2.4)

        if has_balc and fl_idx == balc_fl_idx:
            balc_door_w = 0.95
            balc_door_h = min(2.15, floor_h * 0.76)
            if b_side in ('FRONT', 'BACK'):
                b_u_mid = (x_max - x_min) * 0.5
            else:
                b_u_mid = (y_max - y_min) * 0.5
            
            b_op = {
                'u_start': b_u_mid - balc_door_w * 0.5,
                'u_end': b_u_mid + balc_door_w * 0.5,
                'z_start': z_floor,
                'z_end': z_floor + balc_door_h
            }
            if b_side == 'FRONT':
                front_openings.append(b_op)
            elif b_side == 'BACK':
                back_openings.append(b_op)
            elif b_side == 'LEFT':
                left_openings.append(b_op)
            elif b_side == 'RIGHT':
                right_openings.append(b_op)

        # Dynamic Windows - Front Wall — balcony also suppresses windows on floor directly below it
        if props.has_windows:
            front_win_xs = []
            w_top_roof_z = (found_h + wing_floors * floor_h + props.roof_height * 0.88) if has_wing else 0.0
            wing_roof_occludes = has_wing and (z_floor < w_top_roof_z + 0.3)
            balcony_overhead = False
            has_balc_any = getattr(props, 'has_balcony', False) and num_floors >= 2
            if has_balc_any:
                b_side_any = getattr(props, 'balcony_side', 'FRONT')
                b_fl_any = min(num_floors, max(2, getattr(props, 'balcony_floor', 2)))
                balc_fl_idx_any = b_fl_any - 1
                if fl_idx == balc_fl_idx_any - 1 and b_side_any == 'FRONT':
                    balcony_overhead = True
            
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

            # Strict safety filter: ensure no window lies within door, mini-wing, or balcony envelopes
            if has_door_here:
                front_win_xs = [wx for wx in front_win_xs if (wx < d_ex1 or wx > d_ex2)]
            if has_mw and fl_idx == mw_fl and mw_side == 'FRONT':
                front_win_xs = [wx for wx in front_win_xs if abs(wx - (x_min + x_max) * 0.5) > (mw_w * 0.5 + 0.35)]
            if has_balc and fl_idx == balc_fl_idx and b_side == 'FRONT':
                front_win_xs = [wx for wx in front_win_xs if abs(wx - (x_min + x_max) * 0.5) > (b_width * 0.5 + 0.85)]

            # Ground floor under balcony: suppress windows that would be occluded by diagonal struts
            if balcony_overhead and b_side_any == 'FRONT':
                b_width_any = getattr(props, 'balcony_width', 2.4)
                front_win_xs = [wx for wx in front_win_xs if abs(wx - (x_min + x_max)*0.5) > (b_width_any*0.5 + 0.35) and abs(abs(wx - (x_min + x_max)*0.5) - b_width_any*0.42) > 0.35]
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
            if has_mw and fl_idx == mw_fl and mw_side == 'BACK':
                back_win_xs = [wx for wx in back_win_xs if abs(wx - (x_min + x_max) * 0.5) > (mw_w * 0.5 + 0.35)]
            if has_balc and fl_idx == balc_fl_idx and b_side == 'BACK':
                back_win_xs = [wx for wx in back_win_xs if abs(wx - (x_min + x_max) * 0.5) > (b_width * 0.5 + 0.85)]
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
                if has_mw and fl_idx == mw_fl and mw_side == 'LEFT' and abs(wy - (y_min + y_max) * 0.5) < (mw_w * 0.5 + 0.35):
                    continue
                if has_balc and fl_idx == balc_fl_idx and b_side == 'LEFT' and abs(wy - (y_min + y_max) * 0.5) < (b_width * 0.5 + 0.85):
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
                if has_mw and fl_idx == mw_fl and mw_side == 'RIGHT' and abs(wy - (y_min + y_max) * 0.5) < (mw_w * 0.5 + 0.35):
                    continue
                if has_balc and fl_idx == balc_fl_idx and b_side == 'RIGHT' and abs(wy - (y_min + y_max) * 0.5) < (b_width * 0.5 + 0.85):
                    continue
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
            # Mask out mini-wing footprint from timber framing so diagonal struts never slice through mini wing
            b_timber_ops = list(back_openings)
            l_timber_ops = list(left_openings)
            r_timber_ops = list(right_openings)
            f_timber_ops = list(front_openings)
            if has_mw and fl_idx == mw_fl:
                mw_mask = {
                    'u_start': mw_u_mid - mw_w * 0.5 - 0.05,
                    'u_end': mw_u_mid + mw_w * 0.5 + 0.05,
                    'z_start': z_floor,
                    'z_end': z_floor + floor_h
                }
                if mw_side == 'LEFT':
                    l_timber_ops.append(mw_mask)
                elif mw_side == 'RIGHT':
                    r_timber_ops.append(mw_mask)
                elif mw_side == 'BACK':
                    b_timber_ops.append(mw_mask)
                elif mw_side == 'FRONT':
                    f_timber_ops.append(mw_mask)

            build_facade_timber(bm, (x_min, y_max), (x_max, y_max), z_floor, z_ceil, wall_t,
                                (0.0, 1.0), b_timber_ops, props.timber_diagonals)
            build_facade_timber(bm, (x_min, y_min), (x_min, y_max), z_floor, z_ceil, wall_t,
                                (-1.0, 0.0), l_timber_ops, props.timber_diagonals)
            build_facade_timber(bm, (x_max, y_min), (x_max, y_max), z_floor, z_ceil, wall_t,
                                (1.0, 0.0), r_timber_ops, props.timber_diagonals)

            # Front wall: only exposed exterior spans (no framing across interior junction)
            if not fl_has_wing:
                build_facade_timber(bm, (x_min, y_min), (x_max, y_min), z_floor, z_ceil, wall_t,
                                    (0.0, -1.0), f_timber_ops, props.timber_diagonals)
            else:
                if shape == 'L_SHAPE':
                    if wing_side == 'RIGHT':
                        exp_ops = [op for op in f_timber_ops if op.get('u_end', 0) <= (wx_min - x_min) + 0.01]
                        build_facade_timber(bm, (x_min, y_min), (wx_min, y_min), z_floor, z_ceil, wall_t,
                                            (0.0, -1.0), exp_ops, props.timber_diagonals)
                    else:
                        exp_ops = []
                        for op in f_timber_ops:
                            u1 = op.get('u_start', 0) - (wx_max - x_min)
                            u2 = op.get('u_end', 0) - (wx_max - x_min)
                            if u1 >= -0.01:
                                exp_ops.append({'u_start': u1, 'u_end': u2, 'z_start': op['z_start'], 'z_end': op['z_end']})
                        build_facade_timber(bm, (wx_max, y_min), (x_max, y_min), z_floor, z_ceil, wall_t,
                                            (0.0, -1.0), exp_ops, props.timber_diagonals)
                else: # T_SHAPE
                    exp_ops_l = [op for op in f_timber_ops if op.get('u_end', 0) <= (wx_min - x_min) + 0.01]
                    build_facade_timber(bm, (x_min, y_min), (wx_min, y_min), z_floor, z_ceil, wall_t,
                                        (0.0, -1.0), exp_ops_l, props.timber_diagonals)
                    exp_ops_r = []
                    for op in f_timber_ops:
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
    top_x_min, top_x_max, top_y_min, top_y_max = floor_wall_bounds[top_fl_idx]
    top_w = top_x_max - top_x_min
    top_d = top_y_max - top_y_min
    top_hx = top_w * 0.5
    top_hy = top_d * 0.5
    top_cx = (top_x_min + top_x_max) * 0.5
    top_cy = (top_y_min + top_y_max) * 0.5
    top_z = found_h + num_floors * floor_h
    roof_style = props.roof_style
    
    # Attic floor plate (embedded into wall core with zero gap)
    build_floor_slab(
        bm,
        floor_idx=num_floors,
        x_min=top_x_min + 0.03, x_max=top_x_max - 0.03,
        y_min=top_y_min + 0.03, y_max=top_y_max - 0.03,
        z_level=top_z + 0.05,
        thickness=0.12,
        stair_hole=floor_stair_holes.get(num_floors, None),
        mat_idx=MAT_INDEX_FLOOR
    )
    
    tier_val = getattr(props, 'material_tier', 'TIER_3')
    plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')

    if effective_archetype != 'WATCHTOWER':
        # Interior Roof Trusses & Collar Beams (visible inside attic, safe clearance under sway)
        build_attic_trusses(
            bm,
            x_min=top_x_min + wall_t, x_max=top_x_max - wall_t,
            y_min=top_y_min + wall_t, y_max=top_y_max - wall_t,
            z_base=top_z,
            ridge_z=top_z + props.roof_height,
            spacing=1.4,
            sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0
        )
        
        # Exterior Roof Construction
        flare_val = getattr(props, 'roof_flare', 0.35)
        
        # Pre-compute dormer apertures to open attic holes in the roof deck and shingles
        dormer_apertures = []
        dormer_placements = []
        if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
            roof_half_w = top_hx + props.roof_overhang
            z_main_ridge = top_z + props.roof_height
            
            # Position dormer midway down the slope
            dormer_u = 0.58
            dormer_drop = (1.0 - flare_val) * dormer_u + flare_val * (1.0 - (1.0 - dormer_u) ** 2)
            slope_deck_z = z_main_ridge - dormer_drop * (props.roof_height + 0.10)
            z_dormer_base = slope_deck_z - 0.20
            
            # Scale dormer height so its ridge is guaranteed at least 0.35m below the main roof ridge
            max_dormer_total_h = max(1.10, (z_main_ridge - 0.35) - z_dormer_base)
            cur_dormer_h = min(1.00, max_dormer_total_h * 0.62)
            cur_dormer_roof_h = min(0.55, max_dormer_total_h * 0.38)
            d_rz = z_dormer_base + cur_dormer_h + cur_dormer_roof_h
            
            # Calculate intersection with main roof slope:
            u_intersect = max(0.12, (z_main_ridge - d_rz) / max(0.5, props.roof_height))
            reach_to_slope = (dormer_u - u_intersect) * roof_half_w
            # Penetrate 14cm into slope for a watertight seam, but stop at least 20cm before the ridge
            dist_to_ridge = dormer_u * roof_half_w
            cur_dormer_reach = min(dist_to_ridge - 0.20, max(0.90, reach_to_slope + 0.14))
            
            # Determine dormer Y positions avoiding chimney collision
            # Chimney is at +X (right slope) and +Y (top_hy * 0.45)
            if top_hy * 2.0 > 4.2:
                left_y = top_cy + top_hy * 0.35
                right_y = top_cy - top_hy * 0.40 if props.has_chimney else top_cy + top_hy * 0.35
                dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, left_y), 'facing': (-1, 0), 'side': -1})
                dormer_placements.append({'pos': (top_cx + roof_half_w * dormer_u, right_y), 'facing': (1, 0), 'side': 1})
            else:
                dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, top_cy), 'facing': (-1, 0), 'side': -1})
                
            for dp in dormer_placements:
                d_cx, d_cy = dp['pos']
                dormer_apertures.append({
                    'side': dp['side'],
                    'y_min': d_cy - 0.42,
                    'y_max': d_cy + 0.42,
                    'u_min': max(0.25, u_intersect + 0.04),
                    'u_max': min(0.70, dormer_u + 0.08)
                })

        if roof_style == 'SWAY':
            build_sway_roof(
                bm,
                x_min=top_x_min, x_max=top_x_max,
                y_min=top_y_min, y_max=top_y_max,
                z_base=top_z,
                roof_height=props.roof_height,
                overhang=props.roof_overhang,
                sway_amount=props.roof_sway,
                wall_thickness=wall_t,
                tier=tier_val,
                plank_direction=plank_dir,
                roof_flare=flare_val,
                dormer_apertures=dormer_apertures
            )
        elif roof_style == 'TURRET':
            radius = max(top_hx, top_hy) * 1.05
            build_conical_turret_roof(
                bm,
                center_pos=(top_cx, top_cy, top_z),
                radius=radius,
                height=props.roof_height * 1.3
            )
        else: # 'GABLE'
            build_gable_roof(
                bm,
                x_min=top_x_min, x_max=top_x_max,
                y_min=top_y_min, y_max=top_y_max,
                z_base=top_z,
                roof_height=props.roof_height,
                overhang=props.roof_overhang,
                wall_thickness=wall_t,
                segments_y=6,
                tier=tier_val,
                plank_direction=plank_dir,
                roof_flare=flare_val,
                dormer_apertures=dormer_apertures
            )

        # Roof Hoist Beam with Cargo Hook (Warehouse / freight feature)
        if getattr(props, 'has_hoist_beam', False) and roof_style in ('SWAY', 'GABLE'):
            from .roof import build_hoist_beam
            build_hoist_beam(
                bm,
                front_x=top_cx,
                front_y=top_y_min - props.roof_overhang,
                z_ridge=top_z + props.roof_height,
                length=1.4
            )
            
        # Roof Shingles
        if props.has_roof_shingles and roof_style in ('SWAY', 'GABLE'):
            build_shingle_layers(
                bm,
                x_min=top_x_min, x_max=top_x_max,
                y_min=top_y_min, y_max=top_y_max,
                z_base=top_z,
                roof_height=props.roof_height,
                rows=props.shingle_rows,
                seed=seed,
                overhang=props.roof_overhang,
                sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0,
                roof_style=roof_style,
                roof_flare=flare_val,
                dormer_apertures=dormer_apertures
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
                plank_direction=plank_dir,
                roof_flare=flare_val
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
                    abut_back=abut_back,
                    roof_flare=flare_val
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
                plank_direction=plank_dir,
                roof_flare=flare_val
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
                    abut_back=abut_back,
                    roof_flare=flare_val
                )
        
    # Dormer Windows
    if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        for dp in dormer_placements:
            build_dormer(
                bm,
                center_pos=dp['pos'],
                z_base=z_dormer_base,
                facing_dir=dp['facing'],
                dormer_w=1.2, dormer_d=1.35, dormer_h=cur_dormer_h,
                dormer_roof_h=cur_dormer_roof_h,
                roof_flare=flare_val,
                tier=tier_val,
                max_back_reach=cur_dormer_reach
            )
            
    # Fairytale Roof Spire Turret (Positionable across roof pitch with attic penetration)
    if getattr(props, 'has_roof_turret', False) and effective_archetype != 'WATCHTOWER':
        t_px = getattr(props, 'roof_turret_pos_x', 0.0)
        t_py = getattr(props, 'roof_turret_pos_y', -0.25)
        t_scale = getattr(props, 'roof_turret_scale', 1.0)
        
        roof_half_w = top_hx + props.roof_overhang
        turret_cx = top_cx + t_px * roof_half_w * 0.65
        turret_cy = top_cy + t_py * top_hy * 0.75
        
        # Calculate surface contact height at turret position considering sway sag and flare drop
        u_turret = min(1.0, max(0.0, abs(turret_cx - top_cx) / max(0.01, roof_half_w)))
        drop_turret = (1.0 - flare_val) * u_turret + flare_val * (1.0 - (1.0 - u_turret) ** 2)
        if roof_style == 'SWAY':
            t_y = max(0.0, min(1.0, (turret_cy - top_y_min) / max(0.01, 2.0 * top_hy)))
            sway_val = getattr(props, 'roof_sway', 0.25)
            sag_turret = math.sin(t_y * math.pi) * sway_val
        else:
            sag_turret = 0.0
        z_turret_surf = (top_z + props.roof_height - sag_turret) - drop_turret * (props.roof_height + 0.10)
        
        turret_style = getattr(props, 'roof_turret_style', 'OCTAGONAL')
        build_roof_turret(
            bm,
            center_pos=(turret_cx, turret_cy),
            z_base=z_turret_surf,
            turret_w=1.3,
            turret_h=1.9,
            spire_h=2.4,
            style=turret_style,
            roof_flare=flare_val,
            scale=t_scale
        )
        
    # Stylized Crooked Chimney — user-controlled, avoids pillared outdoors & dormers
    if props.has_chimney and effective_archetype != 'WATCHTOWER':
        cpx = getattr(props, 'chimney_pos_x', 0.55)
        cpy = getattr(props, 'chimney_pos_y', 0.55)
        # If pillared overhang active, force chimney to opposite side
        if getattr(props, 'has_pillared_overhang', False):
            p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
            if p_side == 'FRONT' and cpy < 0.15: cpy = 0.65
            if p_side == 'BACK' and cpy > -0.15: cpy = -0.65
            if p_side == 'LEFT' and cpx < 0.15: cpx = 0.65
            if p_side == 'RIGHT' and cpx > -0.15: cpx = -0.65
        chim_x = top_cx + cpx * top_hx * 0.75
        chim_y = top_cy + cpy * top_hy * 0.75
        # Clamp inside roof
        chim_x = max(top_x_min + 0.9, min(top_x_max - 0.9, chim_x))
        chim_y = max(top_y_min + 0.9, min(top_y_max - 0.9, chim_y))
        # Nudge away from dormer placements — push along whichever axis is tightest so
        # collisions purely in X (dormers sit far left/right on the roof slope) actually
        # get resolved instead of only ever shifting Y.
        clearance = 1.0
        for _pass in range(4):
            moved = False
            for dp in dormer_placements:
                dx = chim_x - dp['pos'][0]
                dy = chim_y - dp['pos'][1]
                if abs(dx) < clearance and abs(dy) < clearance:
                    if abs(dx) <= abs(dy):
                        chim_x += (clearance - abs(dx) + 0.05) * (1.0 if dx >= 0 else -1.0)
                        chim_x = max(top_x_min + 0.9, min(top_x_max - 0.9, chim_x))
                    else:
                        chim_y += (clearance - abs(dy) + 0.05) * (1.0 if dy >= 0 else -1.0)
                        chim_y = max(top_y_min + 0.9, min(top_y_max - 0.9, chim_y))
                    moved = True
            if not moved:
                break
        chim_total_h = total_height + 0.8
        build_fantasy_chimney(
            bm,
            pos_xy=(chim_x, chim_y),
            z_start=0.0,
            total_height=chim_total_h,
            width=0.75, depth=0.75,
            crooked_angle=0.03
        )

    # 4.5. Specialized Architectural Archetype Accessories
    if effective_archetype == 'BLACKSMITH':
        build_blacksmith_forge(bm, -hx, hx, -hy, hy, z_ground=0.04, wall_thickness=wall_t, seed=seed)
    elif effective_archetype == 'WINDMILL':
        hub_z = top_z - 0.35
        build_windmill_sails(bm, cx=0.0, front_y=-hy, hub_z=hub_z, radius=max(2.6, props.width * 0.48), wall_y=-hy + 0.35)
    elif effective_archetype == 'WATCHTOWER':
        build_watchtower_lookout(bm, -top_hx, top_hx, -top_hy, top_hy, z_platform=top_z)
    elif effective_archetype == 'TAVERN':
        build_tavern_porch_and_sign(bm, -hx, hx, front_y=main_door_yf, z_ground=0.0, door_x=main_door_cx, seed=seed)
    elif effective_archetype == 'FISHERMAN':
        build_fisherman_stilts(bm, -hx, hx, -hy, hy, z_ground=0.0, z_floor=found_h)
    elif effective_archetype == 'BAKERY':
        build_bakery_oven(bm, -hx, hx, -hy, hy, z_ground=0.0)
    elif effective_archetype == 'WAREHOUSE':
        build_warehouse_cargo(bm, front_x=0.0, front_y=-hy, z_ground=0.0)

    # 4.6. Architectural Outcrops, Balconies & Pillared Overhangs
    tier_val = getattr(props, 'material_tier', 'TIER_3')
    
    # Mini-Wing Outcrop
    if getattr(props, 'has_mini_wing', False):
        w_side = getattr(props, 'mini_wing_side', 'LEFT')
        w_floor = getattr(props, 'mini_wing_floor', 'GROUND')
        w_width = getattr(props, 'mini_wing_width', 2.2)
        w_depth = getattr(props, 'mini_wing_depth', 1.6)
        w_roof = getattr(props, 'mini_wing_roof', 'LEAN_TO')
        
        target_fl = 0 if w_floor == 'GROUND' else min(num_floors - 1, 1)
        z_wing_base = found_h + target_fl * floor_h
        mw_bounds = floor_wall_bounds.get(target_fl, (-hx, hx, -hy, hy))
            
        build_mini_wing(
            bm, side=w_side, floor_mode=w_floor,
            wall_x_min=mw_bounds[0], wall_x_max=mw_bounds[1], wall_y_min=mw_bounds[2], wall_y_max=mw_bounds[3],
            z_base=z_wing_base, width=w_width, depth=w_depth, height=floor_h * 0.92,
            roof_style=w_roof, tier=tier_val
        )
        
    # Timber Balcony
    if getattr(props, 'has_balcony', False) and num_floors >= 2:
        b_side = getattr(props, 'balcony_side', 'FRONT')
        b_floor = min(num_floors, max(2, getattr(props, 'balcony_floor', 2)))
        b_width = getattr(props, 'balcony_width', 2.4)
        b_depth = getattr(props, 'balcony_depth', 1.3)
        balc_fl_idx = b_floor - 1
        z_balc = found_h + balc_fl_idx * floor_h
        b_bounds = floor_wall_bounds.get(balc_fl_idx, (-hx, hx, -hy, hy))
        build_balcony(
            bm, side=b_side,
            wall_x_min=b_bounds[0], wall_x_max=b_bounds[1], wall_y_min=b_bounds[2], wall_y_max=b_bounds[3],
            z_floor=z_balc, width=b_width, depth=b_depth, tier=tier_val
        )
        
    # Pillared Overhang / Colonnade
    if getattr(props, 'has_pillared_overhang', False):
        p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
        p_depth = getattr(props, 'pillared_overhang_depth', 1.6)
        p_count = getattr(props, 'pillared_overhang_pillars', 3)
        p_style = getattr(props, 'pillared_overhang_style', 'TIMBER_STONE')
        z_overhang_ceil = found_h + floor_h
        po_bounds = floor_wall_bounds.get(0, (-hx, hx, -hy, hy))
        build_pillared_overhang(
            bm, side=p_side,
            wall_x_min=po_bounds[0], wall_x_max=po_bounds[1], wall_y_min=po_bounds[2], wall_y_max=po_bounds[3],
            z_ground=0.0, z_ceiling=z_overhang_ceil, depth=p_depth,
            pillar_count=p_count, pillar_style=p_style, tier=tier_val
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
    apply_organic_shading(obj)
    
    # Store settings dictionary on object for independent multi-building recall
    try:
        from ..operators import get_props_dict
        import json
        obj["building_settings"] = json.dumps(get_props_dict(props))
    except Exception:
        pass
