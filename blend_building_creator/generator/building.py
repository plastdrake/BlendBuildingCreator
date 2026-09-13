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
from .mesh_utils import create_box, create_beveled_box, create_flared_post, create_cylinder, create_cone, apply_box_uvs, add_wonkiness, apply_organic_shading
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
    build_floor_slab, build_ceiling_beams, build_interior_trims, build_straight_staircase,
    build_spiral_staircase, build_attic_trusses, build_stair_guardrail
)
from .openings import build_door_assembly, build_front_steps, build_window_assembly, build_iron_lantern
from .roof import build_sway_roof, build_gable_roof, build_conical_turret_roof, build_shingle_layers, build_dormer, build_roof_turret, build_fantasy_chimney, build_valley_rafters, deck_top_z
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
            mat_w = MAT_INDEX_WOOD
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
                stone_disorder=stone_disorder, seed=seed + k * 17,
                has_exposed_brick=getattr(props, 'has_exposed_brick', True),
                exposed_brick_freq=getattr(props, 'exposed_brick_frequency', 0.25)
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


def get_wings_setup(shape, wing_placement, wing_side, base_w, base_d, raw_wing_w, raw_wing_d, courtyard_w):
    """
    Computes base boundary coordinates and alignment descriptors for compound building shapes:
    L-Shape, T-Shape, and U-Shape (dual wings forming a courtyard).
    Supports FRONT, BACK, LEFT, RIGHT facade attachments.
    """
    wings = []
    if shape == 'L_SHAPE':
        if wing_placement == 'FRONT':
            w_w = min(base_w * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wx1, wx2 = -base_w * 0.5, -base_w * 0.5 + w_w
                align = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5 - w_w, base_w * 0.5
                align = 'RIGHT'
            wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
            wings.append({'id': 0, 'wall': 'FRONT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'BACK':
            w_w = min(base_w * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wx1, wx2 = -base_w * 0.5, -base_w * 0.5 + w_w
                align = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5 - w_w, base_w * 0.5
                align = 'RIGHT'
            wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
            wings.append({'id': 0, 'wall': 'BACK', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'LEFT':
            w_w = min(base_d * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wy1, wy2 = -base_d * 0.5, -base_d * 0.5 + w_w
                align = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5 - w_w, base_d * 0.5
                align = 'BACK'
            wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
            wings.append({'id': 0, 'wall': 'LEFT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        elif wing_placement == 'RIGHT':
            w_w = min(base_d * 0.70, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            if wing_side == 'LEFT':
                wy1, wy2 = -base_d * 0.5, -base_d * 0.5 + w_w
                align = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5 - w_w, base_d * 0.5
                align = 'BACK'
            wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
            wings.append({'id': 0, 'wall': 'RIGHT', 'align': align, 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
    elif shape == 'T_SHAPE':
        if wing_placement in ('FRONT', 'BACK'):
            w_w = min(base_w * 0.85, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            hw = w_w * 0.5
            wx1, wx2 = -hw, hw
            if wing_placement == 'FRONT':
                wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
                wall = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
                wall = 'BACK'
            wings.append({'id': 0, 'wall': wall, 'align': 'CENTER', 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
        else: # LEFT or RIGHT
            w_w = min(base_d * 0.85, max(2.0, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            hd = w_w * 0.5
            wy1, wy2 = -hd, hd
            if wing_placement == 'LEFT':
                wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
                wall = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
                wall = 'RIGHT'
            wings.append({'id': 0, 'wall': wall, 'align': 'CENTER', 'base': (wx1, wx2, wy1, wy2), 'w': w_w, 'd': w_d})
    elif shape == 'U_SHAPE':
        # Dual wings forming a central courtyard
        if wing_placement in ('FRONT', 'BACK'):
            max_w = max(1.8, (base_w - courtyard_w) * 0.5)
            w_w = min(max_w, max(1.8, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            wx1_l, wx2_l = -base_w * 0.5, -base_w * 0.5 + w_w
            wx1_r, wx2_r = base_w * 0.5 - w_w, base_w * 0.5
            if wing_placement == 'FRONT':
                wy1, wy2 = -base_d * 0.5 - w_d, -base_d * 0.5
                wall = 'FRONT'
            else:
                wy1, wy2 = base_d * 0.5, base_d * 0.5 + w_d
                wall = 'BACK'
            wings.append({'id': 0, 'wall': wall, 'align': 'LEFT', 'base': (wx1_l, wx2_l, wy1, wy2), 'w': w_w, 'd': w_d})
            wings.append({'id': 1, 'wall': wall, 'align': 'RIGHT', 'base': (wx1_r, wx2_r, wy1, wy2), 'w': w_w, 'd': w_d})
        else: # LEFT or RIGHT
            max_w = max(1.8, (base_d - courtyard_w) * 0.5)
            w_w = min(max_w, max(1.8, raw_wing_w))
            w_d = max(2.0, raw_wing_d)
            wy1_f, wy2_f = -base_d * 0.5, -base_d * 0.5 + w_w
            wy1_b, wy2_b = base_d * 0.5 - w_w, base_d * 0.5
            if wing_placement == 'LEFT':
                wx1, wx2 = -base_w * 0.5 - w_d, -base_w * 0.5
                wall = 'LEFT'
            else:
                wx1, wx2 = base_w * 0.5, base_w * 0.5 + w_d
                wall = 'RIGHT'
            wings.append({'id': 0, 'wall': wall, 'align': 'FRONT', 'base': (wx1, wx2, wy1_f, wy2_f), 'w': w_w, 'd': w_d})
            wings.append({'id': 1, 'wall': wall, 'align': 'BACK', 'base': (wx1, wx2, wy1_b, wy2_b), 'w': w_w, 'd': w_d})
    return wings

def compute_fl_wing_bounds(wing, fl_idx, fl_overhang, x_min, x_max, y_min, y_max):
    """Calculates per-floor coordinates of a wing factoring in cantilever overhang."""
    wall = wing['wall']
    w_w = wing['w']
    w_d = wing['d']
    align = wing['align']
    if wall == 'FRONT':
        if align == 'LEFT':
            wx1, wx2 = x_min, x_min + (w_w + fl_overhang * 2.0)
        elif align == 'RIGHT':
            wx1, wx2 = x_max - (w_w + fl_overhang * 2.0), x_max
        else: # CENTER
            hw = (w_w + fl_overhang * 2.0) * 0.5
            wx1, wx2 = -hw, hw
        wy1 = y_min - w_d
        wy2 = y_min
        return (wx1, wx2, wy1, wy2)
    elif wall == 'BACK':
        if align == 'LEFT':
            wx1, wx2 = x_min, x_min + (w_w + fl_overhang * 2.0)
        elif align == 'RIGHT':
            wx1, wx2 = x_max - (w_w + fl_overhang * 2.0), x_max
        else:
            hw = (w_w + fl_overhang * 2.0) * 0.5
            wx1, wx2 = -hw, hw
        wy1 = y_max
        wy2 = y_max + w_d
        return (wx1, wx2, wy1, wy2)
    elif wall == 'LEFT':
        if align == 'FRONT':
            wy1, wy2 = y_min, y_min + (w_w + fl_overhang * 2.0)
        elif align == 'BACK':
            wy1, wy2 = y_max - (w_w + fl_overhang * 2.0), y_max
        else:
            hd = (w_w + fl_overhang * 2.0) * 0.5
            wy1, wy2 = -hd, hd
        wx1 = x_min - w_d
        wx2 = x_min
        return (wx1, wx2, wy1, wy2)
    elif wall == 'RIGHT':
        if align == 'FRONT':
            wy1, wy2 = y_min, y_min + (w_w + fl_overhang * 2.0)
        elif align == 'BACK':
            wy1, wy2 = y_max - (w_w + fl_overhang * 2.0), y_max
        else:
            hd = (w_w + fl_overhang * 2.0) * 0.5
            wy1, wy2 = -hd, hd
        wx1 = x_max
        wx2 = x_max + w_d
        return (wx1, wx2, wy1, wy2)
    return (0.0, 0.0, 0.0, 0.0)


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

    raw_wing_w = getattr(props, 'wing_width', 3.5)
    raw_wing_d = getattr(props, 'wing_depth', 3.0)
    wing_placement = getattr(props, 'wing_placement', 'FRONT')
    wing_side = getattr(props, 'wing_side', 'RIGHT')
    courtyard_w = getattr(props, 'courtyard_width', 3.5)
    wing_floors = min(num_floors, max(1, getattr(props, 'wing_floors', 1)))

    wings = get_wings_setup(shape, wing_placement, wing_side, base_w, base_d, raw_wing_w, raw_wing_d, courtyard_w)
    has_wing = len(wings) > 0

    # Backwards compatibility bounds for single wing references
    if has_wing:
        wx_base_min, wx_base_max = wings[0]['base'][0], wings[0]['base'][1]
        wy_base_min, wy_base_max = wings[0]['base'][2], wings[0]['base'][3]
    else:
        wx_base_min, wx_base_max = 0.0, 0.0
        wy_base_min, wy_base_max = 0.0, 0.0
    
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
        # Foundation for Wings
        for w_elem in wings:
            wb = w_elem['base']
            w_fw = (wb[1] - wb[0]) + 0.35
            w_fd = (wb[3] - wb[2]) + 0.35
            w_fcx = (wb[0] + wb[1]) * 0.5
            w_fcy = (wb[2] + wb[3]) * 0.5
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

    # Active balcony floor levels
    active_balc_floors = []
    has_balc = getattr(props, 'has_balcony', False) and num_floors >= 2
    if has_balc:
        b_mode = getattr(props, 'balcony_mode', 'SINGLE')
        if b_mode == 'SINGLE':
            fl = min(num_floors, max(2, getattr(props, 'balcony_floor', 2)))
            active_balc_floors = [fl - 1]
        elif b_mode == 'ALL_UPPER':
            active_balc_floors = list(range(1, num_floors))
        elif b_mode == 'CUSTOM':
            for fl_i, toggle_p in [(1, 'balcony_fl2'), (2, 'balcony_fl3'), (3, 'balcony_fl4'), (4, 'balcony_fl5')]:
                if fl_i < num_floors and getattr(props, toggle_p, False):
                    active_balc_floors.append(fl_i)

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
        
        # Interior bounds for current floor room (inner wall face at wall_t * 0.50)
        ix_min, ix_max = x_min + wall_t * 0.50, x_max - wall_t * 0.50
        iy_min, iy_max = y_min + wall_t * 0.50, y_max - wall_t * 0.50
        # Floor slab strictly interior so no double floor line visible outside
        slab_xmin = ix_min + 0.02
        slab_xmax = ix_max - 0.02
        slab_ymin = iy_min + 0.02
        slab_ymax = iy_max - 0.02
        
        # Wing coordinates if this floor has an active wing
        fl_wings_bounds = []
        if fl_has_wing:
            for w_elem in wings:
                wb = compute_fl_wing_bounds(w_elem, fl_idx, fl_overhang, x_min, x_max, y_min, y_max)
                fl_wings_bounds.append(wb)
                w_elem.setdefault('bounds_fl', {})[fl_idx] = wb
            wx_min, wx_max, wy_min, wy_max = fl_wings_bounds[0]
        else:
            wx_min, wx_max, wy_min, wy_max = 0.0, 0.0, 0.0, 0.0

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
            rail_x = min(slab_xmax - 0.10, sh_x2 + 0.05)
            if props.stair_style == 'SPIRAL':
                build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                      return_y=sh_y1, x_start=sh_x1 + 0.20)
            else:
                # Straight stairs: only guard open void on the top floor where no more stairs ascend
                # On intermediate floors, the ascending flight's own handrail protects the opening
                if fl_idx == num_floors - 1:
                    ret_y = sh_y1 if (fl_idx % 2 == 1) else sh_y2
                    # Guardrail along the right side and across the void edge
                    build_stair_guardrail(bm, rail_x, sh_y1, sh_y2, z_floor + 0.05,
                                          return_y=ret_y, x_start=sh_x1)
                    # If there is walkable floor to the left of the stair opening (e.g. over lower flight),
                    # protect that open edge with a matching left guardrail
                    if sh_x1 > ix_min + 0.35:
                        build_stair_guardrail(bm, sh_x1, sh_y1, sh_y2, z_floor + 0.05)
        
        # Wing floor slabs for compound shapes
        if fl_has_wing:
            for w_elem, (w_xmin, w_xmax, w_ymin, w_ymax) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                if w_wall == 'FRONT':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = slab_ymin + 0.01
                elif w_wall == 'BACK':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = slab_ymax - 0.01
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02
                elif w_wall == 'LEFT':
                    w_slab_xmin = w_xmin + wall_t * 0.50 + 0.02
                    w_slab_xmax = slab_xmin + 0.01
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02
                else: # RIGHT
                    w_slab_xmin = slab_xmax - 0.01
                    w_slab_xmax = w_xmax - wall_t * 0.50 - 0.02
                    w_slab_ymin = w_ymin + wall_t * 0.50 + 0.02
                    w_slab_ymax = w_ymax - wall_t * 0.50 - 0.02

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
                    prev_wb = w_elem.get('bounds_fl', {}).get(fl_idx - 1, None)
                    if prev_wb:
                        build_cantilever_soffit(
                            bm,
                            prev_wb,
                            (w_xmin, w_xmax, w_ymin, w_ymax),
                            z_floor,
                            include_back=(w_wall != 'FRONT'),
                            include_front=(w_wall != 'BACK'),
                            include_left=(w_wall != 'RIGHT'),
                            include_right=(w_wall != 'LEFT')
                        )
                    build_cantilever_corbels(bm, w_xmin, w_xmax, w_ymin, w_ymax, z_floor,
                                            overhang_dist=overhang_step,
                                            include_back=(w_wall != 'FRONT'),
                                            include_front=(w_wall != 'BACK'),
                                            include_left=(w_wall != 'RIGHT'),
                                            include_right=(w_wall != 'LEFT'))

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
                spiral_hole_xmin = spiral_cx - spiral_r - 0.08
                spiral_hole_xmax = spiral_cx + spiral_r + 0.08
                next_stair_hole = (spiral_hole_xmin, spiral_hole_xmax,
                                   spiral_cy - spiral_r - 0.06, min(iy_max, spiral_cy + spiral_r + 0.06))
            else:
                # Straight stairs: Floor 0 -> 1 runs front to back (+Y) on track 0
                # Floor 1 -> 2 runs back to front (-Y) on adjacent track 1 (switchback)
                if fl_idx % 2 == 0:
                    stair_start = (stair_cx_0, stair_y_bot, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=1)
                    # Opening on upper floor only spans this active track, leaving any overhang and adjacent track as solid floor
                    next_stair_hole = (stair_cx_0 - stair_w * 0.5 - 0.08, stair_cx_0 + stair_w * 0.5 + 0.12,
                                       stair_y_bot - 0.15, stair_y_top + 0.05)
                else:
                    stair_start = (stair_cx_1, stair_y_top, z_floor + 0.05)
                    build_straight_staircase(bm, stair_start, z_ceil + 0.05,
                                             stair_width=stair_w, stair_depth=stair_len, direction_y=-1)
                    # Opening on upper floor only spans this active track, leaving adjacent track as solid floor
                    next_stair_hole = (stair_cx_1 - stair_w * 0.5 - 0.08, stair_cx_1 + stair_w * 0.5 + 0.12,
                                       stair_y_bot - 0.05, stair_y_top + 0.15)
            
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
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val == 'TIER_1':
            # For authentic log cabins: window fits cleanly across 3 sawed-off logs
            # Row 1 (sill log) top is at 2.0 * log_diam (0.72)
            # Row 5 (lintel log) bottom is at 5.0 * log_diam (1.80)
            # Opening cutout height = 1.08m
            log_diam = 0.36
            win_cz = z_floor + 3.5 * log_diam
            win_z1 = z_floor + 2.0 * log_diam
            win_z2 = z_floor + 5.0 * log_diam
            win_h = win_z2 - win_z1
            win_w = props.window_width
        else:
            win_cz = z_floor + floor_h * 0.48
            win_z1 = win_cz - win_h * 0.5
            win_z2 = win_cz + win_h * 0.5

        # Doorway placement on Ground Floor (Front, Rear/Back, and Side Entrances)
        if fl_idx == 0:
            tier_val = getattr(props, 'material_tier', 'TIER_3')
            dw = props.door_width
            dh = props.door_height
            if tier_val == 'TIER_1':
                log_diam = 0.36
                dh = 2.02
                door_top_z = z_floor + 6.0 * log_diam
                frame_margin = 0.08
            else:
                frame_margin = 0.12
                door_top_z = z_floor + dh + frame_margin

            # 1. Front Entrance
            if props.has_front_door:
                if shape == 'RECTANGLE':
                    door_cx = 0.0
                    door_yf = y_min
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                elif shape == 'L_SHAPE':
                    if wing_placement == 'FRONT':
                        door_cx = (x_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + x_max) * 0.5
                    else:
                        door_cx = 0.0
                    door_yf = y_min
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                elif shape == 'U_SHAPE':
                    door_cx = 0.0 # Center of front courtyard
                    door_yf = y_min
                    door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                    door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                    front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                else: # T_SHAPE
                    if wing_placement == 'FRONT':
                        door_cx = (wings[0]['base'][0] + wings[0]['base'][1]) * 0.5
                        door_yf = wings[0]['base'][2]
                        door_u1 = (door_cx - dw * 0.5 - frame_margin) - wings[0]['base'][0]
                        door_u2 = (door_cx + dw * 0.5 + frame_margin) - wings[0]['base'][0]
                        w_front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    else:
                        door_cx = 0.0
                        door_yf = y_min
                        door_u1 = (door_cx - dw * 0.5 - frame_margin) - x_min
                        door_u2 = (door_cx + dw * 0.5 + frame_margin) - x_min
                        front_openings.append({'u_start': door_u1, 'u_end': door_u2, 'z_start': z_floor, 'z_end': door_top_z})

                main_door_cx = door_cx
                main_door_yf = door_yf

                build_door_assembly(
                    bm, center_x=door_cx, y_front=door_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                    normal_axis='-Y'
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=door_cx, y_front=door_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-Y')
                if props.has_lanterns:
                    build_iron_lantern(bm, location=(door_cx + dw * 0.5 + 0.45, door_yf - 0.05, z_floor + dh * 0.8))

            # 2. Rear / Back Door
            if getattr(props, 'has_back_door', False):
                b_cx = 0.0
                if shape == 'L_SHAPE' and wing_placement == 'BACK':
                    b_cx = (x_min + wings[0]['base'][0]) * 0.5 if wing_side == 'RIGHT' else (wings[0]['base'][1] + x_max) * 0.5
                b_yf = y_max
                b_u1 = (b_cx - dw * 0.5 - frame_margin) - x_min
                b_u2 = (b_cx + dw * 0.5 + frame_margin) - x_min
                back_openings.append({'u_start': b_u1, 'u_end': b_u2, 'z_start': z_floor, 'z_end': door_top_z})

                build_door_assembly(
                    bm, center_x=b_cx, y_front=b_yf, z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                    normal_axis='+Y'
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=b_cx, y_front=b_yf, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+Y')
                if props.has_lanterns:
                    build_iron_lantern(bm, location=(b_cx + dw * 0.5 + 0.45, b_yf + 0.05, z_floor + dh * 0.8))

            # 3. Side Door
            if getattr(props, 'has_side_door', False):
                s_facade = getattr(props, 'side_door_facade', 'LEFT')
                if s_facade == 'LEFT':
                    s_cy = (y_min + stair_y_bot) * 0.5 if (props.has_stairs and (stair_y_bot - y_min) > 2.0) else (y_min + y_max) * 0.5
                    s_xf = x_min
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    left_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                        normal_axis='-X'
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='-X')
                    if props.has_lanterns:
                        build_iron_lantern(bm, location=(s_xf - 0.05, s_cy + dw * 0.5 + 0.45, z_floor + dh * 0.8))
                else: # RIGHT
                    s_cy = (y_min + y_max) * 0.5
                    s_xf = x_max
                    s_u1 = (s_cy - dw * 0.5 - frame_margin) - y_min
                    s_u2 = (s_cy + dw * 0.5 + frame_margin) - y_min
                    right_openings.append({'u_start': s_u1, 'u_end': s_u2, 'z_start': z_floor, 'z_end': door_top_z})
                    build_door_assembly(
                        bm, center_x=s_xf, y_front=s_cy, z_base=z_floor,
                        wall_thickness=wall_t, door_w=dw, door_h=dh, door_angle_deg=props.door_angle,
                        door_shape=getattr(props, 'door_shape', 'AUTO'), ground_floor_stone=props.ground_floor_stone,
                        normal_axis='+X'
                    )
                    if props.has_front_steps and props.has_foundation:
                        build_front_steps(bm, center_x=s_xf, y_front=s_cy, z_base=z_floor, num_steps=max(2, int(found_h / 0.18)), normal_axis='+X')
                    if props.has_lanterns:
                        build_iron_lantern(bm, location=(s_xf + 0.05, s_cy + dw * 0.5 + 0.45, z_floor + dh * 0.8))

        # Interior walk-through portals between main building and wings
        if fl_has_wing:
            for w_elem, (w_xmin, w_xmax, w_ymin, w_ymax) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                jamb_w = 0.18
                jamb_d = wall_t + 0.10  # Proud of wall into both rooms by 0.05m
                lower = 0.018
                portal_h = floor_h * 0.82
                lintel_h = 0.20

                if w_wall in ('FRONT', 'BACK'):
                    wing_span = w_xmax - w_xmin
                    clear_margin = wall_t + jamb_w + 0.22
                    max_pw = max(1.2, wing_span - clear_margin * 2.0)
                    p_w = min(max_pw, 2.2)
                    p_cx = (w_xmin + w_xmax) * 0.5
                    p_yf = y_min if w_wall == 'FRONT' else y_max
                    # Nudge frame a hair into the main room so wood faces never sit coplanar with plaster
                    nudge = 0.015 if w_wall == 'FRONT' else -0.015
                    f_yf = p_yf + nudge
                    # Cutout in the wall encompasses the whole frame opening + jambs so plaster never z-fights with wood
                    p_u1 = (p_cx - p_w * 0.5 - jamb_w - 0.02) - x_min
                    p_u2 = (p_cx + p_w * 0.5 + jamb_w + 0.02) - x_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h + 0.02}
                    if w_wall == 'FRONT':
                        front_openings.append(op_dict)
                    else:
                        back_openings.append(op_dict)

                    create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                                       location=(p_cx - p_w * 0.5 - jamb_w * 0.5, f_yf, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    create_beveled_box(bm, size=(jamb_w, jamb_d, portal_h),
                                       location=(p_cx + p_w * 0.5 + jamb_w * 0.5, f_yf, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    lintel_w = p_w + jamb_w * 2.0 + 0.06
                    create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                       location=(p_cx, f_yf, z_floor + portal_h + lintel_h * 0.5 - lower),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    # Beveled Wooden Floor Threshold Board bridging the floor opening
                    create_beveled_box(bm, size=(p_w + jamb_w * 2.0 + 0.06, wall_t + 0.16, 0.038),
                                       location=(p_cx, f_yf, z_floor + 0.05 + 0.019),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.008, bevel_segments=2)
                else: # LEFT or RIGHT
                    wing_span = w_ymax - w_ymin
                    clear_margin = wall_t + jamb_w + 0.22
                    max_pw = max(1.2, wing_span - clear_margin * 2.0)
                    p_w = min(max_pw, 2.2)
                    p_cy = (w_ymin + w_ymax) * 0.5
                    p_xf = x_min if w_wall == 'LEFT' else x_max
                    # Same room-ward nudge as FRONT/BACK above
                    nudge = 0.015 if w_wall == 'LEFT' else -0.015
                    f_xf = p_xf + nudge
                    # Cutout in the wall encompasses the whole frame opening + jambs so plaster never z-fights with wood
                    p_u1 = (p_cy - p_w * 0.5 - jamb_w - 0.02) - y_min
                    p_u2 = (p_cy + p_w * 0.5 + jamb_w + 0.02) - y_min
                    op_dict = {'u_start': p_u1, 'u_end': p_u2, 'z_start': z_floor, 'z_end': z_floor + portal_h + lintel_h + 0.02}
                    if w_wall == 'LEFT':
                        left_openings.append(op_dict)
                    else:
                        right_openings.append(op_dict)

                    create_beveled_box(bm, size=(jamb_d, jamb_w, portal_h),
                                       location=(f_xf, p_cy - p_w * 0.5 - jamb_w * 0.5, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    create_beveled_box(bm, size=(jamb_d, jamb_w, portal_h),
                                       location=(f_xf, p_cy + p_w * 0.5 + jamb_w * 0.5, z_floor + portal_h * 0.5 - lower * 0.5),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    lintel_w = p_w + jamb_w * 2.0 + 0.06
                    create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                       location=(f_xf, p_cy, z_floor + portal_h + lintel_h * 0.5 - lower),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.014, bevel_segments=2)
                    # Beveled Wooden Floor Threshold Board bridging the floor opening
                    create_beveled_box(bm, size=(wall_t + 0.16, p_w + jamb_w * 2.0 + 0.06, 0.038),
                                       location=(f_xf, p_cy, z_floor + 0.05 + 0.019),
                                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.008, bevel_segments=2)

        # Walk-in portal into mini-wing outcrop
        has_mw = getattr(props, 'has_mini_wing', False)
        mw_side = getattr(props, 'mini_wing_side', 'LEFT')
        mw_floor_mode = getattr(props, 'mini_wing_floor', 'GROUND')
        mw_fl = 0 if mw_floor_mode == 'GROUND' else min(num_floors - 1, 1)
        mw_w = getattr(props, 'mini_wing_width', 2.2)

        if has_mw and fl_idx == mw_fl:
            mw_portal_w = min(1.30, mw_w - 0.45)
            mw_portal_h = min(2.15, floor_h * 0.78)
            if mw_side in ('FRONT', 'BACK'):
                mw_u_mid = (x_max - x_min) * 0.5
            else:
                mw_u_mid = (y_max - y_min) * 0.5
            
            shift_in = 0.05
            shift_down = 0.0
            jamb_w = 0.16
            jamb_d = wall_t + 0.06
            lintel_h = 0.18
            lintel_w = mw_portal_w + jamb_w * 2.0 - shift_in * 2.0 + 0.08
            trim_clr = jamb_w - shift_in + 0.015

            mw_op = {
                'u_start': mw_u_mid - mw_portal_w * 0.5,
                'u_end': mw_u_mid + mw_portal_w * 0.5,
                'z_start': z_floor,
                'z_end': z_floor + mw_portal_h,
                'trim_clearance': trim_clr
            }

            if mw_side == 'FRONT':
                front_openings.append(mw_op)
                p_cx = (x_min + x_max) * 0.5
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, y_min, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, y_min, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                   location=(p_cx, y_min, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'BACK':
                back_openings.append(mw_op)
                p_cx = (x_min + x_max) * 0.5
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, y_max, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_w, jamb_d, mw_portal_h),
                                   location=(p_cx + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, y_max, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(lintel_w, jamb_d, lintel_h),
                                   location=(p_cx, y_max, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'LEFT':
                left_openings.append(mw_op)
                p_cy = (y_min + y_max) * 0.5
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_min, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_min, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                   location=(x_min, p_cy, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            elif mw_side == 'RIGHT':
                right_openings.append(mw_op)
                p_cy = (y_min + y_max) * 0.5
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_max, p_cy - mw_portal_w * 0.5 - jamb_w * 0.5 + shift_in, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, jamb_w, mw_portal_h),
                                   location=(x_max, p_cy + mw_portal_w * 0.5 + jamb_w * 0.5 - shift_in, z_floor + mw_portal_h * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
                create_beveled_box(bm, size=(jamb_d, lintel_w, lintel_h),
                                   location=(x_max, p_cy, z_floor + mw_portal_h + lintel_h * 0.5 - shift_down),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

        # Balcony Doorway Cutout
        b_side = getattr(props, 'balcony_side', 'FRONT')
        b_width = getattr(props, 'balcony_width', 2.4)

        if fl_idx in active_balc_floors:
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

        # Dynamic Windows - Facade Openings & Shutters
        # Dynamic Windows - Facade Openings & Shutters
        eff_spacing = max(1.0, props.window_spacing / max(0.2, getattr(props, 'window_density', 1.0)))
        win_w_clr = (win_w * 0.5 + 0.65) if props.has_shutters else (win_w * 0.5 + 0.45)
        w_top_roof_z = (found_h + wing_floors * floor_h + props.roof_height * 0.88) if has_wing else 0.0

        def carve_intervals(spans, excludes, min_len):
            cur_spans = list(spans)
            for ex1, ex2 in excludes:
                next_spans = []
                for s1, s2 in cur_spans:
                    if ex2 <= s1 or ex1 >= s2:
                        next_spans.append((s1, s2))
                    else:
                        if ex1 - s1 >= min_len:
                            next_spans.append((s1, ex1))
                        if s2 - ex2 >= min_len:
                            next_spans.append((ex2, s2))
                cur_spans = next_spans
            return cur_spans

        def get_shutter_info(wx_val, wy_val, wz_val):
            if not props.has_shutters:
                return False, False
            st = getattr(props, 'shutter_state', 'OPEN')
            if st == 'CLOSED':
                return True, True
            elif st == 'PARTIAL':
                pct = getattr(props, 'shutter_closed_amount', 0.5)
                h = int(abs(math.sin(wx_val * 12.9898 + wy_val * 78.233 + wz_val * 37.719 + seed * 19.113)) * 10000) % 100
                return True, (h < int(pct * 100))
            return True, False

        def get_facade_wing_exclusions(facade_name):
            excludes = []
            if not has_wing:
                return excludes
            for w_e in wings:
                # Active if floor is part of wing OR wing roof reaches this floor
                if not (fl_has_wing or (z_floor < w_top_roof_z + 0.35)):
                    continue
                w_wall = w_e['wall']
                wb = w_e.get('bounds_fl', {}).get(fl_idx, None)
                if wb is None:
                    wb = w_e.get('bounds_fl', {}).get(wing_floors - 1, w_e['base'])
                
                # 1. Direct attachment to this facade
                if w_wall == facade_name:
                    if facade_name in ('FRONT', 'BACK'):
                        excludes.append((wb[0] - win_w_clr, wb[1] + win_w_clr))
                    else: # LEFT or RIGHT
                        excludes.append((wb[2] - win_w_clr, wb[3] + win_w_clr))
                
                # 2. Adjacent corner attachment flush with this facade
                if facade_name == 'LEFT':
                    if w_wall in ('FRONT', 'BACK') and (wb[0] <= x_min + 0.35):
                        if w_wall == 'FRONT':
                            excludes.append((y_min - 0.50, y_min + win_w_clr + 0.40))
                        else: # BACK
                            excludes.append((y_max - (win_w_clr + 0.40), y_max + 0.50))
                elif facade_name == 'RIGHT':
                    if w_wall in ('FRONT', 'BACK') and (wb[1] >= x_max - 0.35):
                        if w_wall == 'FRONT':
                            excludes.append((y_min - 0.50, y_min + win_w_clr + 0.40))
                        else: # BACK
                            excludes.append((y_max - (win_w_clr + 0.40), y_max + 0.50))
                elif facade_name == 'FRONT':
                    if w_wall in ('LEFT', 'RIGHT') and (wb[2] <= y_min + 0.35):
                        if w_wall == 'LEFT':
                            excludes.append((x_min - 0.50, x_min + win_w_clr + 0.40))
                        else: # RIGHT
                            excludes.append((x_max - (win_w_clr + 0.40), x_max + 0.50))
                elif facade_name == 'BACK':
                    if w_wall in ('LEFT', 'RIGHT') and (wb[3] >= y_max - 0.35):
                        if w_wall == 'LEFT':
                            excludes.append((x_min - 0.50, x_min + win_w_clr + 0.40))
                        else: # RIGHT
                            excludes.append((x_max - (win_w_clr + 0.40), x_max + 0.50))
            return excludes

        # Dynamic Windows - Front Wall
        if props.has_windows:
            front_excludes = list(get_facade_wing_exclusions('FRONT'))
            balcony_overhead = (fl_idx + 1 in active_balc_floors and b_side == 'FRONT')
            
            # Door exclusion zone calculation on floor 0
            if fl_idx == 0 and props.has_front_door:
                door_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                d_ex1 = door_cx - door_clr
                d_ex2 = door_cx + door_clr + (0.35 if props.has_lanterns else 0.0)
                front_excludes.append((d_ex1, d_ex2))
                
            if has_mw and mw_side == 'FRONT' and fl_idx in (mw_fl, mw_fl + 1):
                mw_cx = (x_min + x_max) * 0.5
                front_excludes.append((mw_cx - (mw_w * 0.5 + win_w_clr), mw_cx + (mw_w * 0.5 + win_w_clr)))
                
            if fl_idx in active_balc_floors and b_side == 'FRONT':
                b_cx = (x_min + x_max) * 0.5
                front_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))
            elif balcony_overhead and b_side == 'FRONT':
                b_cx = (x_min + x_max) * 0.5
                front_excludes.append((b_cx - (b_width * 0.5 + 0.45), b_cx + (b_width * 0.5 + 0.45)))

            front_spans = carve_intervals([(x_min, x_max)], front_excludes, min_len=win_w + 0.35)
            front_win_xs = []
            for s1, s2 in front_spans:
                if fl_idx == 0 and props.has_stairs and cur_w < 6.0 and s2 <= 0.0:
                    continue
                front_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.75))

            # Strict safety filter
            front_win_xs = [wx for wx in front_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in front_excludes)]

            for wx in front_win_xs:
                wu = (wx - x_min)
                front_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(wx, y_min, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_min, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-Y',
                    has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes
                )

        # Dynamic Windows - Back Wall
        if props.has_windows:
            back_excludes = list(get_facade_wing_exclusions('BACK'))
            if fl_idx == 0 and getattr(props, 'has_back_door', False):
                bd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                bd_ex1 = b_cx - bd_clr
                bd_ex2 = b_cx + bd_clr + (0.35 if props.has_lanterns else 0.0)
                back_excludes.append((bd_ex1, bd_ex2))
                
            if has_mw and mw_side == 'BACK' and fl_idx in (mw_fl, mw_fl + 1):
                mw_cx = (x_min + x_max) * 0.5
                back_excludes.append((mw_cx - (mw_w * 0.5 + win_w_clr), mw_cx + (mw_w * 0.5 + win_w_clr)))
                
            if fl_idx in active_balc_floors and b_side == 'BACK':
                b_cx = (x_min + x_max) * 0.5
                back_excludes.append((b_cx - (b_width * 0.5 + 0.85), b_cx + (b_width * 0.5 + 0.85)))

            back_spans = carve_intervals([(x_min, x_max)], back_excludes, min_len=win_w + 0.35)
            back_win_xs = []
            for s1, s2 in back_spans:
                back_win_xs.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.75))
            back_win_xs = [wx for wx in back_win_xs if not any(ex1 <= wx <= ex2 for ex1, ex2 in back_excludes)]

            for wx in back_win_xs:
                wu = (wx - x_min)
                back_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(wx, y_max, win_cz)
                build_window_assembly(
                    bm, center=(wx, y_max, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+Y',
                    has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=False
                )

        # Dynamic Windows - Side Walls (Left and Right)
        if props.has_windows and cur_d > 2.8:
            # Left side
            left_excludes = list(get_facade_wing_exclusions('LEFT'))
            if fl_idx == 0 and props.has_stairs:
                left_excludes.append((stair_y_bot - 0.25, stair_y_top + 0.25))
            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'LEFT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                left_excludes.append((s_cy - sd_clr, s_cy + sd_clr + (0.35 if props.has_lanterns else 0.0)))
            if has_mw and mw_side == 'LEFT' and fl_idx in (mw_fl, mw_fl + 1):
                mw_cy = (y_min + y_max) * 0.5
                left_excludes.append((mw_cy - (mw_w * 0.5 + win_w_clr), mw_cy + (mw_w * 0.5 + win_w_clr)))
            if fl_idx in active_balc_floors and b_side == 'LEFT':
                b_cy = (y_min + y_max) * 0.5
                left_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            left_spans = carve_intervals([(y_min, y_max)], left_excludes, min_len=win_w + 0.35)
            left_win_ys = []
            for s1, s2 in left_spans:
                left_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.75))
            left_win_ys = [wy for wy in left_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in left_excludes)]

            for wy in left_win_ys:
                wu = (wy - y_min)
                left_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(x_min, wy, win_cz)
                build_window_assembly(
                    bm, center=(x_min, wy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='-X',
                    has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes
                )

            # Right side
            right_excludes = list(get_facade_wing_exclusions('RIGHT'))
            if fl_idx == 0 and getattr(props, 'has_side_door', False) and getattr(props, 'side_door_facade', 'LEFT') == 'RIGHT':
                sd_clr = (props.door_width + win_w) * 0.5 + (0.50 if props.has_shutters else 0.28)
                right_excludes.append((s_cy - sd_clr, s_cy + sd_clr + (0.35 if props.has_lanterns else 0.0)))
            if has_mw and mw_side == 'RIGHT' and fl_idx in (mw_fl, mw_fl + 1):
                mw_cy = (y_min + y_max) * 0.5
                right_excludes.append((mw_cy - (mw_w * 0.5 + win_w_clr), mw_cy + (mw_w * 0.5 + win_w_clr)))
            if fl_idx in active_balc_floors and b_side == 'RIGHT':
                b_cy = (y_min + y_max) * 0.5
                right_excludes.append((b_cy - (b_width * 0.5 + 0.85), b_cy + (b_width * 0.5 + 0.85)))

            right_spans = carve_intervals([(y_min, y_max)], right_excludes, min_len=win_w + 0.35)
            right_win_ys = []
            for s1, s2 in right_spans:
                right_win_ys.extend(get_facade_window_positions(s1, s2, target_spacing=eff_spacing, min_margin=0.75))
            right_win_ys = [wy for wy in right_win_ys if not any(ex1 <= wy <= ex2 for ex1, ex2 in right_excludes)]

            for wy in right_win_ys:
                wu = (wy - y_min)
                right_openings.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                sh_act, sh_cl = get_shutter_info(x_max, wy, win_cz)
                build_window_assembly(
                    bm, center=(x_max, wy, win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis='+X',
                    has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes
                )

        # Dynamic Windows - Wing Walls
        wing_wall_openings = [] # List of tuples: (w_elem, wall_face, openings, start_pt, end_pt, norm_vec)
        if fl_has_wing:
            for w_elem, (wx1, wx2, wy1, wy2) in zip(wings, fl_wings_bounds):
                w_wall = w_elem['wall']
                # Create opening lists for each of the 3 exposed faces
                w_ops_1, w_ops_2, w_ops_3 = [], [], []
                
                if w_wall == 'FRONT':
                    # Face 1: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    if props.has_windows and not (fl_idx == 0 and shape == 'T_SHAPE' and wing_placement == 'FRONT'):
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=0.75)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    if props.has_windows and ((wy2 - 1.25) - (wy1 + 0.85) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 0.85, wy2 - 1.25, target_spacing=eff_spacing, min_margin=0.6)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy2 (main building junction) by 1.25m
                    if props.has_windows and ((wy2 - 1.25) - (wy1 + 0.85) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 0.85, wy2 - 1.25, target_spacing=eff_spacing, min_margin=0.6)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)

                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_1, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_2, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_3, (1.0, 0.0)))

                elif w_wall == 'BACK':
                    # Face 1: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    if props.has_windows:
                        w_win_xs = get_facade_window_positions(wx1, wx2, target_spacing=eff_spacing, min_margin=0.75)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=False)
                    # Face 2: Left (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    if props.has_windows and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.6)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 3: Right (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    # Buffered inside corner at wy1 (main building junction) by 1.25m
                    if props.has_windows and ((wy2 - 0.85) - (wy1 + 1.25) >= win_w * 0.7):
                        w_win_ys = get_facade_window_positions(wy1 + 1.25, wy2 - 0.85, target_spacing=eff_spacing, min_margin=0.6)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)

                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_1, (0.0, 1.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_2, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_3, (1.0, 0.0)))

                elif w_wall == 'LEFT':
                    # Face 1: Left End (wx1, wy1) -> (wx1, wy2) normal (-1, 0)
                    if props.has_windows:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=0.75)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx1, wwy, win_cz)
                            build_window_assembly(bm, center=(wx1, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if props.has_windows and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.6)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx2 (main building junction) by 1.25m
                    if props.has_windows and ((wx2 - 1.25) - (wx1 + 0.85) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 0.85, wx2 - 1.25, target_spacing=eff_spacing, min_margin=0.6)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=False)

                    wing_wall_openings.append(((wx1, wy1), (wx1, wy2), w_ops_1, (-1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

                elif w_wall == 'RIGHT':
                    # Face 1: Right End (wx2, wy1) -> (wx2, wy2) normal (1, 0)
                    if props.has_windows:
                        w_win_ys = get_facade_window_positions(wy1, wy2, target_spacing=eff_spacing, min_margin=0.75)
                        for wwy in w_win_ys:
                            wu = (wwy - wy1)
                            w_ops_1.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wx2, wwy, win_cz)
                            build_window_assembly(bm, center=(wx2, wwy, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+X',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 2: Front (wx1, wy1) -> (wx2, wy1) normal (0, -1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if props.has_windows and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.6)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_2.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy1, win_cz)
                            build_window_assembly(bm, center=(wwx, wy1, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='-Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=props.has_flower_boxes)
                    # Face 3: Back (wx1, wy2) -> (wx2, wy2) normal (0, 1)
                    # Buffered inside corner at wx1 (main building junction) by 1.25m
                    if props.has_windows and ((wx2 - 0.85) - (wx1 + 1.25) >= win_w * 0.7):
                        w_win_xs = get_facade_window_positions(wx1 + 1.25, wx2 - 0.85, target_spacing=eff_spacing, min_margin=0.6)
                        for wwx in w_win_xs:
                            wu = (wwx - wx1)
                            w_ops_3.append({'u_start': wu - win_w * 0.5, 'u_end': wu + win_w * 0.5, 'z_start': win_z1, 'z_end': win_z2})
                            sh_act, sh_cl = get_shutter_info(wwx, wy2, win_cz)
                            build_window_assembly(bm, center=(wwx, wy2, win_cz), size=(win_w, win_h),
                                                  wall_thickness=wall_t, normal_axis='+Y',
                                                  has_shutters=sh_act, shutters_closed=sh_cl, has_flower_box=False)

                    wing_wall_openings.append(((wx2, wy1), (wx2, wy2), w_ops_1, (1.0, 0.0)))
                    wing_wall_openings.append(((wx1, wy1), (wx2, wy1), w_ops_2, (0.0, -1.0)))
                    wing_wall_openings.append(((wx1, wy2), (wx2, wy2), w_ops_3, (0.0, 1.0)))

        # 4 Main Solid Walls with Openings
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        if tier_val in ('TIER_1', 'TIER_2'):
            mat_w = MAT_INDEX_WOOD
        else:
            mat_w = MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone) else MAT_INDEX_PLASTER_EXT

        phys_siding = getattr(props, 'physical_siding', True)
        plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')
        plank_jank = getattr(props, 'plank_jankiness', 0.35)
        stone_scale = getattr(props, 'stone_block_scale', 1.0)
        stone_disorder = getattr(props, 'stone_disorder', 0.35)
        has_brick = getattr(props, 'has_exposed_brick', True)
        brick_freq = getattr(props, 'exposed_brick_frequency', 0.25)

        # Interior joinery
        build_interior_trims(
            bm, ix_min, ix_max, iy_min, iy_max, z_floor, z_ceil,
            wall_thickness=wall_t, stair_hole=cur_stair_hole,
            wall_openings={
                'front': front_openings,
                'back': back_openings,
                'left': left_openings,
                'right': right_openings,
            },
        )

        wall_top_z = z_ceil

        omit_crown = (tier_val == 'TIER_1' and phys_siding and num_floors > 1
                      and fl_idx == num_floors - 1)

        build_wall_with_opening(
            bm, (x_min, y_min), (x_max, y_min), z_floor, wall_top_z, wall_t, front_openings,
            mat_ext=mat_w, normal_vec=(0.0, -1.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
            has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
        )
        build_wall_with_opening(
            bm, (x_min, y_max), (x_max, y_max), z_floor, wall_top_z, wall_t, back_openings,
            mat_ext=mat_w, normal_vec=(0.0, 1.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
            has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
        )
        build_wall_with_opening(
            bm, (x_min, y_min), (x_min, y_max), z_floor, wall_top_z, wall_t, left_openings,
            mat_ext=mat_w, normal_vec=(-1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
            omit_top_log_row=omit_crown,
            has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
        )
        build_wall_with_opening(
            bm, (x_max, y_min), (x_max, y_max), z_floor, wall_top_z, wall_t, right_openings,
            mat_ext=mat_w, normal_vec=(1.0, 0.0), tier=tier_val, physical_siding=phys_siding,
            plank_direction=plank_dir, plank_jankiness=plank_jank,
            stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
            omit_top_log_row=omit_crown,
            has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
        )
        
        # Wing Solid Walls
        if fl_has_wing:
            for p1, p2, w_ops, norm_v in wing_wall_openings:
                build_wall_with_opening(
                    bm, p1, p2, z_floor, wall_top_z, wall_t, w_ops,
                    mat_ext=mat_w, normal_vec=norm_v, tier=tier_val, physical_siding=phys_siding,
                    plank_direction=plank_dir, plank_jankiness=plank_jank,
                    stone_block_scale=stone_scale, stone_disorder=stone_disorder, seed=seed,
                    has_exposed_brick=has_brick, exposed_brick_freq=brick_freq
                )

        # Timber Framing (Tudor Half-Timbering)
        # In Tier 1 (Log Cabin), authentic interlocking logs already provide all structural aesthetics
        if props.has_timber_framing and effective_archetype != 'WATCHTOWER' and tier_val != 'TIER_1':
            post_w = 0.22
            timber_jank = props.wonkiness * 0.5
            is_top_fl = (fl_idx == num_floors - 1)

            # 1. Main building corner posts (chunky, flared at ends, subtly wonky)
            corners = [
                (x_min, y_min), (x_max, y_min),
                (x_min, y_max), (x_max, y_max)
            ]
            for cx, cy in corners:
                is_ground = (fl_idx == 0 and props.has_foundation)
                if is_ground:
                    ph = floor_h + found_h
                    pz = ph * 0.5
                else:
                    if is_top_fl:
                        ph = floor_h - 0.08
                        pz = z_floor + ph * 0.5 - 0.012
                    else:
                        ph = floor_h + 0.012
                        pz = z_floor + ph * 0.5 - 0.012
                b_cx = (x_min + x_max) * 0.5
                b_cy = (y_min + y_max) * 0.5
                dx = cx - b_cx
                dy = cy - b_cy
                dlen = math.sqrt(dx * dx + dy * dy)
                if dlen > 1e-4:
                    nx = dx / dlen
                    ny = dy / dlen
                else:
                    nx, ny = 0.0, 0.0
                off = wall_t * 0.42
                ocx = cx + nx * off
                ocy = cy + ny * off
                create_flared_post(
                    bm, size=(post_w, post_w, ph),
                    location=(ocx, ocy, pz),
                    mat_index=MAT_INDEX_TIMBER, flare=0.35, jankiness=timber_jank,
                    chamfer_top=is_top_fl
                )

            # 2. Main building exterior facades
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

            def build_exposed_wall_timber(p1, p2, norm_v, ops, occlusions):
                total_len = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                if total_len < 0.1:
                    return
                occ_sorted = sorted([(max(0.0, o[0]), min(total_len, o[1])) for o in occlusions if o[1] > 0 and o[0] < total_len])
                exp_intervals = []
                cur_u = 0.0
                for occ_s, occ_e in occ_sorted:
                    if occ_s > cur_u + 0.35:
                        exp_intervals.append((cur_u, occ_s))
                    cur_u = max(cur_u, occ_e)
                if total_len > cur_u + 0.35:
                    exp_intervals.append((cur_u, total_len))

                if not occlusions:
                    build_facade_timber(bm, p1, p2, z_floor, z_ceil, wall_t, norm_v, ops, props.timber_diagonals, is_top_floor=is_top_fl)
                    return

                ux = (p2[0] - p1[0]) / total_len
                uy = (p2[1] - p1[1]) / total_len
                for iu1, iu2 in exp_intervals:
                    sub_p1 = (p1[0] + ux * iu1, p1[1] + uy * iu1)
                    sub_p2 = (p1[0] + ux * iu2, p1[1] + uy * iu2)
                    sub_ops = []
                    for op in ops:
                        op_u1 = op.get('u_start', 0.0) - iu1
                        op_u2 = op.get('u_end', 0.0) - iu1
                        if op_u2 > 0 and op_u1 < (iu2 - iu1):
                            sub_ops.append({
                                'u_start': max(0.0, op_u1),
                                'u_end': min(iu2 - iu1, op_u2),
                                'z_start': op['z_start'],
                                'z_end': op['z_end']
                            })
                    build_facade_timber(bm, sub_p1, sub_p2, z_floor, z_ceil, wall_t, norm_v, sub_ops, props.timber_diagonals, is_top_floor=is_top_fl)

            # Compute attached wing occlusions for each wall
            f_occs, b_occs, l_occs, r_occs = [], [], [], []
            if fl_has_wing:
                for w_elem, (wx_min, wx_max, wy_min, wy_max) in zip(wings, fl_wings_bounds):
                    ww = w_elem['wall']
                    if ww == 'FRONT':
                        f_occs.append((wx_min - x_min, wx_max - x_min))
                    elif ww == 'BACK':
                        b_occs.append((wx_min - x_min, wx_max - x_min))
                    elif ww == 'LEFT':
                        l_occs.append((wy_min - y_min, wy_max - y_min))
                    elif ww == 'RIGHT':
                        r_occs.append((wy_min - y_min, wy_max - y_min))

            build_exposed_wall_timber((x_min, y_min), (x_max, y_min), (0.0, -1.0), f_timber_ops, f_occs)
            build_exposed_wall_timber((x_min, y_max), (x_max, y_max), (0.0, 1.0), b_timber_ops, b_occs)
            build_exposed_wall_timber((x_min, y_min), (x_min, y_max), (-1.0, 0.0), l_timber_ops, l_occs)
            build_exposed_wall_timber((x_max, y_min), (x_max, y_max), (1.0, 0.0), r_timber_ops, r_occs)

            # 3. Wing exterior facades and corner posts
            if fl_has_wing:
                for w_elem, (wx_min, wx_max, wy_min, wy_max) in zip(wings, fl_wings_bounds):
                    ww = w_elem['wall']
                    is_w_ground = (fl_idx == 0 and props.has_foundation)
                    if is_w_ground:
                        w_post_h = floor_h + found_h
                        w_post_cz = w_post_h * 0.5
                    else:
                        if is_top_fl:
                            w_post_h = floor_h - 0.08
                            w_post_cz = z_floor + w_post_h * 0.5 - 0.012
                        else:
                            w_post_h = floor_h + 0.012
                            w_post_cz = z_floor + w_post_h * 0.5 - 0.012

                    w_cx = (wx_min + wx_max) * 0.5
                    w_cy = (wy_min + wy_max) * 0.5

                    if ww == 'FRONT':
                        w_corners = [(wx_min, wy_min), (wx_max, wy_min)]
                    elif ww == 'BACK':
                        w_corners = [(wx_min, wy_max), (wx_max, wy_max)]
                    elif ww == 'LEFT':
                        w_corners = [(wx_min, wy_min), (wx_min, wy_max)]
                    else:
                        w_corners = [(wx_max, wy_min), (wx_max, wy_max)]

                    for wpx, wpy in w_corners:
                        dx_w = wpx - w_cx
                        dy_w = wpy - w_cy
                        dlen_w = math.sqrt(dx_w * dx_w + dy_w * dy_w)
                        if dlen_w > 1e-4:
                            nx_w = dx_w / dlen_w
                            ny_w = dy_w / dlen_w
                        else:
                            nx_w, ny_w = 0.0, -1.0
                        off_w = wall_t * 0.42
                        ocx_w = wpx + nx_w * off_w
                        ocy_w = wpy + ny_w * off_w
                        create_flared_post(bm, size=(post_w, post_w, w_post_h),
                                           location=(ocx_w, ocy_w, w_post_cz),
                                           mat_index=MAT_INDEX_TIMBER, flare=0.35, jankiness=timber_jank,
                                           chamfer_top=is_top_fl)

                for p1, p2, w_ops, norm_v in wing_wall_openings:
                    build_facade_timber(bm, p1, p2, z_floor, z_ceil, wall_t,
                                        norm_v, w_ops, props.timber_diagonals, is_top_floor=is_top_fl)

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
        # Exterior Roof Construction
        flare_val = getattr(props, 'roof_flare', 0.35)
        roof_orient = getattr(props, 'roof_orientation', 'FRONT_BACK')
        if roof_orient == 'AUTO':
            roof_orient = 'LEFT_RIGHT' if top_w > top_d * 1.15 else 'FRONT_BACK'
        is_rotated_roof = (roof_orient == 'LEFT_RIGHT' and roof_style in ('SWAY', 'GABLE'))
        
        # Pre-compute dormer apertures to open attic holes in the roof deck and shingles
        dormer_apertures = []
        dormer_placements = []
        if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
            z_main_ridge = top_z + props.roof_height
            dormer_u = 0.58
            dormer_drop = (1.0 - flare_val) * dormer_u + flare_val * (1.0 - (1.0 - dormer_u) ** 2)
            slope_deck_z = z_main_ridge - dormer_drop * (props.roof_height + 0.10)
            z_dormer_base = slope_deck_z - 0.20
            
            # Scale dormer height so its ridge is guaranteed at least 0.35m below the main roof ridge
            max_dormer_total_h = max(1.10, (z_main_ridge - 0.35) - z_dormer_base)
            cur_dormer_h = min(1.00, max_dormer_total_h * 0.62)
            cur_dormer_roof_h = min(0.55, max_dormer_total_h * 0.38)
            d_rz = z_dormer_base + cur_dormer_h + cur_dormer_roof_h
            u_intersect = max(0.12, (z_main_ridge - d_rz) / max(0.5, props.roof_height))
            
            d_count = max(1, getattr(props, 'dormer_count', 2))
            d_sides = getattr(props, 'dormer_sides', 'BOTH')
            # Adaptive dormer width: shrinks only when crowded on small roofs (1.2m otherwise, no regression)
            main_dormer_w = 1.2

            if is_rotated_roof:
                roof_half_w = top_hy + props.roof_overhang
                reach_to_slope = (dormer_u - u_intersect) * roof_half_w
                dist_to_ridge = dormer_u * roof_half_w
                cur_dormer_reach = min(dist_to_ridge - 0.20, max(0.90, reach_to_slope + 0.14))

                if d_sides == 'FRONT_LEFT':
                    n_front, n_back = d_count, 0
                elif d_sides == 'BACK_RIGHT':
                    n_front, n_back = 0, d_count
                else: # 'BOTH'
                    n_front = (d_count + 1) // 2
                    n_back = d_count // 2

                x_margin = min(1.0, max(0.65, (top_hx * 2.0) * 0.16))
                x_start = top_x_min + x_margin
                x_end = top_x_max - x_margin
                x_span = max(0.2, x_end - x_start)
                # Clamp dormers per side so cheeks never overlap on small buildings (1.2m + 0.4m gap).
                # Large roofs are unaffected since the fit count exceeds the request.
                max_per_side_x = max(1, int((x_span + 0.3) / 1.6))
                n_front = min(n_front, max_per_side_x)
                n_back = min(n_back, max_per_side_x)
                tight_n_x = max(n_front, n_back, 1)
                if tight_n_x > 1:
                    main_dormer_w = min(1.2, max(0.85, (x_span / tight_n_x) - 0.35))

                if n_front == 1 and n_back == 1 and x_span >= 1.6:
                    fx = top_cx - x_span * 0.22
                    dormer_placements.append({'pos': (fx, top_cy - roof_half_w * dormer_u), 'facing': (0, -1), 'side': 1, 'loc_y': fx - top_cx})
                    bx = top_cx + x_span * 0.22
                    dormer_placements.append({'pos': (bx, top_cy + roof_half_w * dormer_u), 'facing': (0, 1), 'side': -1, 'loc_y': bx - top_cx})
                else:
                    for i in range(n_front):
                        fx = top_cx if n_front == 1 else (x_start + ((i + 0.5) / n_front) * x_span)
                        dormer_placements.append({'pos': (fx, top_cy - roof_half_w * dormer_u), 'facing': (0, -1), 'side': 1, 'loc_y': fx - top_cx})
                    for i in range(n_back):
                        bx = top_cx if n_back == 1 else (x_start + ((i + 0.5) / n_back) * x_span)
                        dormer_placements.append({'pos': (bx, top_cy + roof_half_w * dormer_u), 'facing': (0, 1), 'side': -1, 'loc_y': bx - top_cx})

                # Roof deck is kept solid under dormers (no cell skipping) so small roofs
                # never open gap holes; cheeks penetrate the slope for a watertight seam.
                ap_half = max(0.24, main_dormer_w * 0.5 - 0.18)
                for dp in dormer_placements:
                    dormer_apertures.append({
                        'side': dp['side'],
                        'y_min': dp['loc_y'] - ap_half,
                        'y_max': dp['loc_y'] + ap_half,
                        'u_min': max(0.25, u_intersect + 0.04),
                        'u_max': min(0.70, dormer_u + 0.08)
                    })
            else:
                roof_half_w = top_hx + props.roof_overhang
                reach_to_slope = (dormer_u - u_intersect) * roof_half_w
                # Penetrate 14cm into slope for a watertight seam, but stop at least 20cm before the ridge
                dist_to_ridge = dormer_u * roof_half_w
                cur_dormer_reach = min(dist_to_ridge - 0.20, max(0.90, reach_to_slope + 0.14))

                if d_sides == 'FRONT_LEFT':
                    n_left, n_right = d_count, 0
                elif d_sides == 'BACK_RIGHT':
                    n_left, n_right = 0, d_count
                else: # 'BOTH'
                    n_left = (d_count + 1) // 2
                    n_right = d_count // 2

                y_margin = min(1.0, max(0.65, (top_hy * 2.0) * 0.16))
                y_start = top_y_min + y_margin
                y_end = top_y_max - y_margin
                y_span = max(0.2, y_end - y_start)
                # Same overlap guard for the standard orientation (see rotated branch above).
                max_per_side_y = max(1, int((y_span + 0.3) / 1.6))
                n_left = min(n_left, max_per_side_y)
                n_right = min(n_right, max_per_side_y)
                tight_n_y = max(n_left, n_right, 1)
                if tight_n_y > 1:
                    main_dormer_w = min(1.2, max(0.85, (y_span / tight_n_y) - 0.35))

                if n_left == 1 and n_right == 1 and y_span >= 1.6:
                    ly = top_cy + y_span * 0.22
                    dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, ly), 'facing': (-1, 0), 'side': -1})
                    ry = top_cy - (y_span * 0.25 if props.has_chimney else y_span * 0.22)
                    dormer_placements.append({'pos': (top_cx + roof_half_w * dormer_u, ry), 'facing': (1, 0), 'side': 1})
                else:
                    for i in range(n_left):
                        ly = top_cy if n_left == 1 else (y_start + ((i + 0.5) / n_left) * y_span)
                        dormer_placements.append({'pos': (top_cx - roof_half_w * dormer_u, ly), 'facing': (-1, 0), 'side': -1})
                    for i in range(n_right):
                        ry = top_cy if n_right == 1 else (y_start + ((i + 0.5) / n_right) * y_span)
                        dormer_placements.append({'pos': (top_cx + roof_half_w * dormer_u, ry), 'facing': (1, 0), 'side': 1})

                ap_half = max(0.24, main_dormer_w * 0.5 - 0.18)
                for dp in dormer_placements:
                    d_cx, d_cy = dp['pos']
                    dormer_apertures.append({
                        'side': dp['side'],
                        'y_min': d_cy - ap_half,
                        'y_max': d_cy + ap_half,
                        'u_min': max(0.25, u_intersect + 0.04),
                        'u_max': min(0.70, dormer_u + 0.08)
                    })

        # Eave exclusions for equal-floor wings so eave fascia beams don't slice through wing roofs
        eave_ex = {'min': [], 'max': []}
        if has_wing and wing_floors == num_floors:
            for w_elem in wings:
                ww = w_elem['wall']
                w_idx = min(wing_floors, num_floors) - 1
                if 'bounds_fl' in w_elem and w_idx in w_elem['bounds_fl']:
                    wb = w_elem['bounds_fl'][w_idx]
                else:
                    wb = (w_elem.get('x_min', 0.0), w_elem.get('x_max', 0.0), w_elem.get('y_min', 0.0), w_elem.get('y_max', 0.0))
                wx1, wx2, wy1, wy2 = wb
                if is_rotated_roof:
                    # Rotated roof: local X is (-top_hy to top_hy), local Y is (-top_hx to top_hx)
                    # rx_max (+X local) rotates to -Y (FRONT facade in world space)
                    # rx_min (-X local) rotates to +Y (BACK facade in world space)
                    # local Y is (world_x - top_cx)
                    ly1 = (wx1 - props.roof_overhang * 0.4) - top_cx
                    ly2 = (wx2 + props.roof_overhang * 0.4) - top_cx
                    if ww == 'FRONT':
                        eave_ex['max'].append((ly1, ly2))
                    elif ww == 'BACK':
                        eave_ex['min'].append((ly1, ly2))
                    elif ww in ('LEFT', 'RIGHT'):
                        # Flush side wing: main eave overhang corner would cross the
                        # wing facade, so break the eave at the wing span.
                        if wy1 <= top_y_min + 0.35:
                            eave_ex['max'].append((ly1, ly2))
                        if wy2 >= top_y_max - 0.35:
                            eave_ex['min'].append((ly1, ly2))
                else:
                    # Non-rotated roof: rx_min is LEFT facade, rx_max is RIGHT facade
                    ly1 = (wy1 - props.roof_overhang * 0.4)
                    ly2 = (wy2 + props.roof_overhang * 0.4)
                    if ww == 'LEFT':
                        eave_ex['min'].append((ly1, ly2))
                    elif ww == 'RIGHT':
                        eave_ex['max'].append((ly1, ly2))
                    elif ww in ('FRONT', 'BACK'):
                        # Flush front/back wing: break the side eave at the wing span.
                        if wx2 >= top_x_max - 0.35:
                            eave_ex['max'].append((ly1, ly2))
                        if wx1 <= top_x_min + 0.35:
                            eave_ex['min'].append((ly1, ly2))

        if roof_style in ('SWAY', 'GABLE'):
            roof_bm = bmesh.new()
            if is_rotated_roof:
                if roof_style == 'SWAY':
                    build_sway_roof(
                        roof_bm,
                        x_min=-top_hy, x_max=top_hy,
                        y_min=-top_hx, y_max=top_hx,
                        z_base=0.0,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway,
                        wall_thickness=wall_t,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                else: # 'GABLE'
                    build_gable_roof(
                        roof_bm,
                        x_min=-top_hy, x_max=top_hy,
                        y_min=-top_hx, y_max=top_hx,
                        z_base=0.0,
                        roof_height=props.roof_height,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        segments_y=6,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                rot_m = Matrix.Rotation(-math.pi * 0.5, 4, 'Z')
                trans_m = Matrix.Translation(Vector((top_cx, top_cy, top_z)))
                bmesh.ops.transform(roof_bm, matrix=trans_m @ rot_m, verts=roof_bm.verts)
            else:
                if roof_style == 'SWAY':
                    build_sway_roof(
                        roof_bm,
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
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )
                else:
                    build_gable_roof(
                        roof_bm,
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
                        dormer_apertures=dormer_apertures,
                        eave_exclusions=eave_ex
                    )

            # Eliminate main roof protrusion through wing slopes at outside corners
            if has_wing and wing_floors == num_floors:
                del_main_faces = []
                for w_elem in wings:
                    ww = w_elem['wall']
                    w_idx = min(wing_floors, num_floors) - 1
                    wb = w_elem['bounds_fl'][w_idx] if ('bounds_fl' in w_elem and w_idx in w_elem['bounds_fl']) else (w_elem.get('x_min', 0.0), w_elem.get('x_max', 0.0), w_elem.get('y_min', 0.0), w_elem.get('y_max', 0.0))
                    wx1, wx2, wy1, wy2 = wb
                    w_cx = (wx1 + wx2) * 0.5
                    w_cy = (wy1 + wy2) * 0.5
                    if is_rotated_roof:
                        if ww == 'FRONT':
                            if wx2 >= top_x_max - 0.35: # Outside corner on right
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.x >= w_cx - 0.05 and fc.y < top_cy - 0.05:
                                        del_main_faces.append(f)
                            if wx1 <= top_x_min + 0.35: # Outside corner on left
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.x <= w_cx + 0.05 and fc.y < top_cy - 0.05:
                                        del_main_faces.append(f)
                        elif ww == 'BACK':
                            if wx2 >= top_x_max - 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.x >= w_cx - 0.05 and fc.y > top_cy + 0.05:
                                        del_main_faces.append(f)
                            if wx1 <= top_x_min + 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.x <= w_cx + 0.05 and fc.y > top_cy + 0.05:
                                        del_main_faces.append(f)
                    else:
                        if ww == 'LEFT':
                            if wy1 <= top_y_min + 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.y <= w_cy + 0.05 and fc.x < top_cx - 0.05:
                                        del_main_faces.append(f)
                            if wy2 >= top_y_max - 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.y >= w_cy - 0.05 and fc.x < top_cx - 0.05:
                                        del_main_faces.append(f)
                        elif ww == 'RIGHT':
                            if wy1 <= top_y_min + 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.y <= w_cy + 0.05 and fc.x > top_cx + 0.05:
                                        del_main_faces.append(f)
                            if wy2 >= top_y_max - 0.35:
                                for f in roof_bm.faces:
                                    fc = f.calc_center_median()
                                    if fc.y >= w_cy - 0.05 and fc.x > top_cx + 0.05:
                                        del_main_faces.append(f)
                if del_main_faces:
                    bmesh.ops.delete(roof_bm, geom=list(set(del_main_faces)), context='FACES')

            uv_src = roof_bm.loops.layers.uv.verify()
            uv_dst = bm.loops.layers.uv.verify()
            vert_map = {v: bm.verts.new(v.co) for v in roof_bm.verts}
            for f in roof_bm.faces:
                try:
                    new_f = bm.faces.new([vert_map[v] for v in f.verts])
                    new_f.material_index = f.material_index
                    new_f.smooth = f.smooth
                    for l_src, l_dst in zip(f.loops, new_f.loops):
                        l_dst[uv_dst].uv = l_src[uv_src].uv
                except ValueError:
                    pass
            roof_bm.free()
        elif roof_style == 'TURRET':
            radius = max(top_hx, top_hy) * 1.05
            build_conical_turret_roof(
                bm,
                center_pos=(top_cx, top_cy, top_z),
                radius=radius,
                height=props.roof_height * 1.3
            )
        if getattr(props, 'has_hoist_beam', False) and roof_style in ('SWAY', 'GABLE'):
            from .roof import build_hoist_beam
            if is_rotated_roof:
                hoist_bm = bmesh.new()
                build_hoist_beam(
                    hoist_bm,
                    front_x=0.0,
                    front_y=0.0,
                    z_ridge=0.0,
                    length=1.4
                )
                rot_m = Matrix.Rotation(-math.pi * 0.5, 4, 'Z')
                trans_m = Matrix.Translation(Vector((top_x_min - props.roof_overhang, top_cy, top_z + props.roof_height)))
                bmesh.ops.transform(hoist_bm, matrix=trans_m @ rot_m, verts=hoist_bm.verts)
                uv_src = hoist_bm.loops.layers.uv.verify()
                uv_dst = bm.loops.layers.uv.verify()
                vmap = {v: bm.verts.new(v.co) for v in hoist_bm.verts}
                for f in hoist_bm.faces:
                    try:
                        nf = bm.faces.new([vmap[v] for v in f.verts])
                        nf.material_index = f.material_index
                        nf.smooth = f.smooth
                        for ls, ld in zip(f.loops, nf.loops):
                            ld[uv_dst].uv = ls[uv_src].uv
                    except ValueError:
                        pass
                hoist_bm.free()
            else:
                build_hoist_beam(
                    bm,
                    front_x=top_cx,
                    front_y=top_y_min - props.roof_overhang,
                    z_ridge=top_z + props.roof_height,
                    length=1.4
                )
            
        # Physical shingle layers disabled: textured roof deck provides stylized clay tiles cleanly without micro-geometry
        if False and props.has_roof_shingles and roof_style in ('SWAY', 'GABLE'):
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
    wing_dormer_placements = []
    if has_wing:
        w_top_fl = min(wing_floors, num_floors)
        is_lower_wing = (wing_floors < num_floors)
        w_fl_idx = w_top_fl - 1
        w_top_z = found_h + w_top_fl * floor_h
        w_roof_h = props.roof_height if (wing_floors == num_floors) else (props.roof_height * 0.88)

        if is_lower_wing:
            if props.has_cantilever:
                if props.overhang_mode == 'SECOND_FLOOR_ONLY':
                    up_fl_overhang = cantilever if w_top_fl >= 1 else 0.0
                else:
                    up_fl_overhang = w_top_fl * cantilever
            else:
                up_fl_overhang = 0.0
            up_main_hx = (base_w + up_fl_overhang * 2.0) * 0.5
            up_main_hy = (base_d + up_fl_overhang * 2.0) * 0.5
            up_front_y = -up_main_hy
            up_back_y = up_main_hy

        for w_elem in wings:
            w_wall = w_elem['wall']
            if 'bounds_fl' in w_elem and w_fl_idx in w_elem['bounds_fl']:
                w_top_xmin, w_top_xmax, w_top_ymin, w_top_ymax = w_elem['bounds_fl'][w_fl_idx]
            else:
                top_b = floor_wall_bounds.get(w_fl_idx, (-base_w*0.5, base_w*0.5, -base_d*0.5, base_d*0.5))
                w_top_xmin, w_top_xmax, w_top_ymin, w_top_ymax = compute_fl_wing_bounds(
                    w_elem, w_fl_idx,
                    (w_fl_idx * cantilever if props.has_cantilever else 0.0),
                    top_b[0], top_b[1], top_b[2], top_b[3]
                )

            if is_lower_wing or (not is_lower_wing and has_wing):
                # Interior ceiling slab for the wing (enclosing the wing interior from above).
                # Equal-height wings get one too so rooms never see open roof/dark attic.
                # Level matches the main attic slab (top at +0.05) so eave decks hide
                # inside slab depth instead of banding across ceilings.
                ceil_z = (w_top_z - 0.02) if is_lower_wing else (w_top_z + 0.05)
                ceil_t = 0.10 if is_lower_wing else 0.12
                build_floor_slab(
                    bm,
                    floor_idx=w_top_fl,
                    x_min=w_top_xmin + 0.02,
                    x_max=w_top_xmax - 0.02,
                    y_min=w_top_ymin + 0.02,
                    y_max=w_top_ymax - 0.02,
                    z_level=ceil_z,
                    thickness=ceil_t,
                    stair_hole=None,
                    mat_idx=MAT_INDEX_FLOOR
                )
                if props.has_ceiling_beams:
                    build_ceiling_beams(
                        bm,
                        x_min=w_top_xmin + wall_t,
                        x_max=w_top_xmax - wall_t,
                        y_min=w_top_ymin + wall_t,
                        y_max=w_top_ymax - wall_t,
                        z_ceil=ceil_z,
                        spacing=1.2
                    )

            # Pre-compute wing roof dormer apertures and placements
            w_dormer_apertures = []
            do_wing_dormers = (
                props.has_dormers and
                getattr(props, 'has_wing_dormers', True) and
                roof_style in ('SWAY', 'GABLE') and
                effective_archetype != 'WATCHTOWER'
            )
            w_d_sides = getattr(props, 'wing_dormer_sides', 'BOTH')
            w_d_target_count = max(1, getattr(props, 'wing_dormer_count', 1))
            w_sway = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0

            z_w_ridge = w_top_z + w_roof_h
            w_dormer_u = 0.58
            w_dormer_drop = (1.0 - flare_val) * w_dormer_u + flare_val * (1.0 - (1.0 - w_dormer_u) ** 2)
            w_slope_deck_z = z_w_ridge - w_dormer_drop * (w_roof_h + 0.10)
            # Raised 0.16 above the main-roof formula so cheeks/floor stay above the
            # wing ceiling line and never hang into the rooms below.
            z_w_dormer_base = w_slope_deck_z - 0.04

            max_w_d_total_h = max(0.95, (z_w_ridge - 0.28) - z_w_dormer_base)
            w_cur_d_h = min(0.85, max_w_d_total_h * 0.60)
            w_cur_d_roof_h = min(0.48, max_w_d_total_h * 0.40)
            w_d_rz = z_w_dormer_base + w_cur_d_h + w_cur_d_roof_h
            w_u_intersect = max(0.12, (z_w_ridge - w_d_rz) / max(0.4, w_roof_h))

            if w_wall == 'FRONT':
                if is_lower_wing:
                    w_roof_ymax = up_front_y + 0.04
                    abut_back = True
                elif is_rotated_roof:
                    # Perpendicular junction (valley): extend into the main slope.
                    # Deck past the valley lines is notch-cut in the builder.
                    w_roof_ymax = top_cy
                    abut_back = True
                else:
                    # Parallel ridges (gable-to-gable): stop flush in the main gable
                    # wall core so no tiles cross plaster outside or bands indoors.
                    w_roof_ymax = top_y_min + 0.12
                    abut_back = True

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_roof_half_w = (w_top_xmax - w_top_xmin) * 0.5 + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, (w_top_xmax - w_top_xmin) * 0.28))

                if do_wing_dormers:
                    # Pulled back from outer eave corner (1.10) and main valley corner
                    # (1.40) so dormers never crowd corners.
                    y_start = w_top_ymin + 1.10
                    y_end = w_roof_ymax - 1.40
                    if not is_lower_wing and is_rotated_roof:
                        # Valley-notched deck: dormers must sit fully outside the main
                        # wall on intact deck, never over the cut triangle.
                        y_end = min(y_end, top_y_min - 0.25)
                    y_span = y_end - y_start
                    if y_span >= 0.60:
                        if w_cx < top_cx - 0.2:
                            outer_s, inner_s = -1, 1
                        elif w_cx > top_cx + 0.2:
                            outer_s, inner_s = 1, -1
                        else:
                            outer_s, inner_s = None, None

                        if w_d_sides == 'OUTER' and outer_s is not None:
                            slopes = [outer_s]
                        elif w_d_sides == 'INNER' and inner_s is not None:
                            slopes = [inner_s]
                        else:
                            slopes = [-1, 1]

                        for s in slopes:
                            # 1.6m pitch + width shrink so neighbouring cheeks never overlap.
                            k = min(w_d_target_count, max(1, int((y_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (y_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_y = (y_start + y_end) * 0.5 if k == 1 else (y_start + ((i + 0.5) / k) * y_span)
                                d_x = w_cx + s * w_roof_half_w * w_dormer_u
                                facing = (-1, 0) if s == -1 else (1, 0)
                                w_dormer_apertures.append({
                                    'side': s,
                                    'y_min': d_y - ap_half,
                                    'y_max': d_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                # Perpendicular: open valley (outer gable only, deck notch-cut past
                # valley lines). Parallel: finished gable abutting the main gable.
                w_gable_fb = ('FRONT',) if (is_lower_wing or is_rotated_roof) else ('FRONT', 'BACK')
                # Trim side eave fascia where it would enter main timber/walls.
                w_eave_fb = None
                if is_lower_wing:
                    w_eave_fb = None
                elif is_rotated_roof:
                    # Deep valley: no side fascia past the main wall face.
                    trim = [(top_y_min - 0.10, w_roof_ymax + 0.60)]
                    w_eave_fb = {'min': list(trim), 'max': list(trim)}

                has_left = (w_top_xmin > top_x_min + 0.35)
                has_right = (w_top_xmax < top_x_max - 0.35)
                w_notch_side = 'BOTH' if (has_left and has_right) else ('LEFT' if has_left else 'RIGHT')

                # Parallel flush case: fascia ends die inside the gable core, no trim.
                w_notch_fb = None
                if not is_lower_wing and is_rotated_roof:
                    w_notch_fb = {
                        'apex_x': w_cx,
                        'apex_y': top_cy,
                        'half_width': w_roof_half_w,
                        'base_y': top_y_min - props.roof_overhang,
                        'keep': 'le',
                        'overlap': 0.02,
                        'side': w_notch_side
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_top_ymin, y_max=w_roof_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_fb,
                        abut_back=abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_fb,
                        valley_notch=w_notch_fb
                    )
                else:
                    build_gable_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_top_ymin, y_max=w_roof_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_fb,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_back=abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_fb,
                        valley_notch=w_notch_fb
                    )

                if not is_lower_wing and is_rotated_roof:
                    # Segmented valley flashing: samples both deck profiles along the
                    # plan line so every notch step is covered (no slits/holes).
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _tc=(top_cx, top_cy), _th=top_hy, _ov=_ov,
                                 _ez=_ezm, _sw=_swm):
                        _lx = _tc[1] - py
                        _ly = px - _tc[0]
                        return deck_top_z(_lx, _ly, 0.0, _th + _ov, 0.0,
                                          props.roof_height, flare_val, _sw,
                                          -top_hx - _ov, top_hx + _ov, _ez - top_z,
                                          top_off=0.05) + top_z
                    _ezw = (w_top_z - 0.12) if roof_style == 'SWAY' else (w_top_z - 0.10)
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    def _wing_fn(px, py, _wx=w_cx, _wh=w_roof_half_w, _wz=w_top_z,
                                 _wr=w_roof_h, _wy0=w_top_ymin - _ov, _wy1=w_roof_ymax,
                                 _ez=_ezw, _sw=_sww):
                        return deck_top_z(px, py, _wx, _wh, _wz, _wr,
                                          flare_val, _sw, _wy0, _wy1, _ez,
                                          top_off=0.05)
                    # Only true inside corner valleys (not outside walls) form valleys
                    valley_feet = []
                    if has_left:
                        valley_feet.append(w_top_xmin - _ov)
                    if has_right:
                        valley_feet.append(w_top_xmax + _ov)
                    for vx in valley_feet:
                        build_valley_rafters(bm, (vx, top_y_min - _ov), (w_cx, top_cy),
                                             _main_fn, _wing_fn)

            elif w_wall == 'BACK':
                if is_lower_wing:
                    w_roof_ymin = up_back_y - 0.04
                    abut_front = True
                elif is_rotated_roof:
                    # Perpendicular junction (valley): see FRONT.
                    w_roof_ymin = top_cy
                    abut_front = True
                else:
                    # Parallel ridges (gable-to-gable): flush in the wall core.
                    w_roof_ymin = top_y_max - 0.12
                    abut_front = True

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_roof_half_w = (w_top_xmax - w_top_xmin) * 0.5 + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, (w_top_xmax - w_top_xmin) * 0.28))

                if do_wing_dormers:
                    # Main valley corner first (1.40), outer eave corner 1.10.
                    y_start = w_roof_ymin + 1.40
                    y_end = w_top_ymax - 1.10
                    if not is_lower_wing and is_rotated_roof:
                        # See FRONT: keep dormers outside the wall on intact deck.
                        y_start = max(y_start, top_y_max + 0.25)
                    y_span = y_end - y_start
                    if y_span >= 0.60:
                        if w_cx < top_cx - 0.2:
                            outer_s, inner_s = -1, 1
                        elif w_cx > top_cx + 0.2:
                            outer_s, inner_s = 1, -1
                        else:
                            outer_s, inner_s = None, None

                        if w_d_sides == 'OUTER' and outer_s is not None:
                            slopes = [outer_s]
                        elif w_d_sides == 'INNER' and inner_s is not None:
                            slopes = [inner_s]
                        else:
                            slopes = [-1, 1]

                        for s in slopes:
                            # Same 1.6m anti-overlap pitch as FRONT (see above).
                            k = min(w_d_target_count, max(1, int((y_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (y_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_y = (y_start + y_end) * 0.5 if k == 1 else (y_start + ((i + 0.5) / k) * y_span)
                                d_x = w_cx + s * w_roof_half_w * w_dormer_u
                                facing = (-1, 0) if s == -1 else (1, 0)
                                w_dormer_apertures.append({
                                    'side': s,
                                    'y_min': d_y - ap_half,
                                    'y_max': d_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                w_gable_bk = ('BACK',) if (is_lower_wing or is_rotated_roof) else ('FRONT', 'BACK')
                w_eave_bk = None
                if is_lower_wing:
                    w_eave_bk = None
                elif is_rotated_roof:
                    trim = [(w_roof_ymin - 0.60, top_y_max + 0.10)]
                    w_eave_bk = {'min': list(trim), 'max': list(trim)}

                has_left = (w_top_xmin > top_x_min + 0.35)
                has_right = (w_top_xmax < top_x_max - 0.35)
                w_notch_side = 'BOTH' if (has_left and has_right) else ('LEFT' if has_left else 'RIGHT')

                w_notch_bk = None
                if not is_lower_wing and is_rotated_roof:
                    w_notch_bk = {
                        'apex_x': w_cx,
                        'apex_y': top_cy,
                        'half_width': w_roof_half_w,
                        'base_y': top_y_max + props.roof_overhang,
                        'keep': 'ge',
                        'overlap': 0.02,
                        'side': w_notch_side
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_roof_ymin, y_max=w_top_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_bk,
                        abut_front=abut_front,
                        abut_back=False,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_bk,
                        valley_notch=w_notch_bk
                    )
                else:
                    build_gable_roof(
                        bm,
                        x_min=w_top_xmin, x_max=w_top_xmax,
                        y_min=w_roof_ymin, y_max=w_top_ymax,
                        z_base=w_top_z,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_bk,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_front=abut_front,
                        abut_back=False,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_bk,
                        valley_notch=w_notch_bk
                    )

                if not is_lower_wing and is_rotated_roof:
                    # Segmented valley flashing (see FRONT).
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _tc=(top_cx, top_cy), _th=top_hy, _ov=_ov,
                                 _ez=_ezm, _sw=_swm):
                        _lx = _tc[1] - py
                        _ly = px - _tc[0]
                        return deck_top_z(_lx, _ly, 0.0, _th + _ov, 0.0,
                                          props.roof_height, flare_val, _sw,
                                          -top_hx - _ov, top_hx + _ov, _ez - top_z,
                                          top_off=0.05) + top_z
                    _ezw = (w_top_z - 0.12) if roof_style == 'SWAY' else (w_top_z - 0.10)
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    def _wing_fn(px, py, _wx=w_cx, _wh=w_roof_half_w, _wz=w_top_z,
                                 _wr=w_roof_h, _wy0=w_roof_ymin, _wy1=w_top_ymax + _ov,
                                 _ez=_ezw, _sw=_sww):
                        return deck_top_z(px, py, _wx, _wh, _wz, _wr,
                                          flare_val, _sw, _wy0, _wy1, _ez,
                                          top_off=0.05)
                    valley_feet = []
                    if has_left:
                        valley_feet.append(w_top_xmin - _ov)
                    if has_right:
                        valley_feet.append(w_top_xmax + _ov)

                    for vx in valley_feet:
                        build_valley_rafters(bm, (vx, top_y_max + _ov), (w_cx, top_cy),
                                             _main_fn, _wing_fn)

            elif w_wall in ('LEFT', 'RIGHT'):
                w_ridge_len = w_top_xmax - w_top_xmin
                w_span_y = w_top_ymax - w_top_ymin
                wing_roof_bm = bmesh.new()
                lx_half = w_span_y * 0.5
                ly_half = (w_ridge_len + 0.04) * 0.5 if is_rotated_roof else (w_ridge_len * 0.5)

                w_cx = (w_top_xmin + w_top_xmax) * 0.5
                w_cy = (w_top_ymin + w_top_ymax) * 0.5
                if is_lower_wing or is_rotated_roof:
                    # Lower wings abut the facade; rotated (parallel ridges) stop flush
                    # in the main gable wall core.
                    loc_abut_back = True
                    y_max_adj = 0.04
                else:
                    # Perpendicular equal junction: run the ridge to the main ridge so
                    # valleys die into the slope (cross-hipped U/L, cf. FRONT rotated).
                    # Flush open tip (no overhang past the ridge, no cap face).
                    loc_abut_back = True
                    serve_dist = abs(top_cx - w_cx)
                    y_max_adj = max(0.25, serve_dist - ly_half)
                w_roof_half_w = lx_half + props.roof_overhang
                w_reach = (w_dormer_u - w_u_intersect) * w_roof_half_w
                dist_to_ridge = w_dormer_u * w_roof_half_w
                w_cur_d_reach = min(dist_to_ridge - 0.16, max(0.75, w_reach + 0.12))
                w_cur_d_w = min(1.10, max(0.90, w_span_y * 0.28))

                if do_wing_dormers:
                    # Outer corner 1.10, main valley corner 1.40 (main side is east
                    # for LEFT wings, west for RIGHT wings).
                    if w_wall == 'LEFT':
                        x_start = w_top_xmin + 1.10
                        x_end = w_top_xmax - 1.40
                        if not is_lower_wing and not is_rotated_roof:
                            # Notched deck: keep dormers outside the wall line.
                            x_end = min(x_end, top_x_min - 0.25)
                    else: # 'RIGHT'
                        x_start = w_top_xmin + 1.40
                        x_end = w_top_xmax - 1.10
                        if not is_lower_wing and not is_rotated_roof:
                            x_start = max(x_start, top_x_max + 0.25)
                    x_span = x_end - x_start

                    if x_span >= 0.60:
                        if w_cy < top_cy - 0.2:
                            outer_sw, inner_sw = -1, 1
                        elif w_cy > top_cy + 0.2:
                            outer_sw, inner_sw = 1, -1
                        else:
                            outer_sw, inner_sw = None, None

                        if w_d_sides == 'OUTER' and outer_sw is not None:
                            slopes_world = [outer_sw]
                        elif w_d_sides == 'INNER' and inner_sw is not None:
                            slopes_world = [inner_sw]
                        else:
                            slopes_world = [-1, 1]

                        for sw in slopes_world:
                            k = min(w_d_target_count, max(1, int((x_span + 0.3) / 1.6)))
                            eff_w = w_cur_d_w
                            if k > 1:
                                eff_w = min(w_cur_d_w, max(0.85, (x_span / k) - 0.40))
                            ap_half = max(0.24, eff_w * 0.5 - 0.18)
                            for i in range(k):
                                d_x = (x_start + x_end) * 0.5 if k == 1 else (x_start + ((i + 0.5) / k) * x_span)
                                d_y = w_cy + sw * w_roof_half_w * w_dormer_u
                                facing = (0, -1) if sw == -1 else (0, 1)

                                if w_wall == 'LEFT':
                                    local_side = -1 if sw == -1 else 1
                                    loc_y = d_x - w_cx
                                else: # 'RIGHT'
                                    local_side = 1 if sw == -1 else -1
                                    loc_y = w_cx - d_x

                                w_dormer_apertures.append({
                                    'side': local_side,
                                    'y_min': loc_y - ap_half,
                                    'y_max': loc_y + ap_half,
                                    'u_min': max(0.25, w_u_intersect + 0.04),
                                    'u_max': min(0.70, w_dormer_u + 0.08)
                                })
                                wing_dormer_placements.append({
                                    'pos': (d_x, d_y),
                                    'facing': facing,
                                    'z_base': z_w_dormer_base,
                                    'dormer_w': eff_w,
                                    'dormer_d': w_cur_d_reach,
                                    'dormer_h': w_cur_d_h,
                                    'dormer_roof_h': w_cur_d_roof_h,
                                    'max_back_reach': w_cur_d_reach,
                                    'sway_amount': w_sway
                                })

                # Parallel (rotated): finished gable abuts main gable. Perpendicular
                # (non-rotated): open valley, deck notch-cut (local coords).
                w_gable_lr = ('FRONT',) if (is_lower_wing or not is_rotated_roof) else ('FRONT', 'BACK')
                # Local-coord fascia trim (see FRONT/BACK above).
                w_eave_lr = None
                if is_lower_wing:
                    w_eave_lr = None
                elif not is_rotated_roof:
                    y_top_local = ly_half + y_max_adj
                    if w_wall == 'LEFT':
                        wall_local = top_x_min - w_cx
                    else:
                        wall_local = w_cx - top_x_max
                    trim = [(wall_local - 0.10, y_top_local + 0.60)]
                    w_eave_lr = {'min': list(trim), 'max': list(trim)}

                has_front = (w_top_ymin > top_y_min + 0.35)
                has_back = (w_top_ymax < top_y_max - 0.35)
                if w_wall == 'LEFT':
                    w_notch_side_lr = 'BOTH' if (has_front and has_back) else ('RIGHT' if has_front else 'LEFT')
                else:
                    w_notch_side_lr = 'BOTH' if (has_front and has_back) else ('LEFT' if has_front else 'RIGHT')

                w_notch_lr = None
                if not is_lower_wing and not is_rotated_roof:
                    w_notch_lr = {
                        'apex_x': 0.0,
                        'apex_y': ly_half + y_max_adj,
                        'half_width': lx_half + props.roof_overhang,
                        'base_y': ((top_x_min - w_cx) if w_wall == 'LEFT' else (w_cx - top_x_max)) - props.roof_overhang,
                        'keep': 'le',
                        'overlap': 0.02,
                        'side': w_notch_side_lr
                    }
                if props.roof_style == 'SWAY':
                    build_sway_roof(
                        wing_roof_bm,
                        x_min=-lx_half, x_max=lx_half,
                        y_min=-ly_half, y_max=ly_half + y_max_adj,
                        z_base=0.0,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        sway_amount=props.roof_sway * 0.70,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_lr,
                        abut_back=loc_abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_lr,
                        valley_notch=w_notch_lr
                    )
                else:
                    build_gable_roof(
                        wing_roof_bm,
                        x_min=-lx_half, x_max=lx_half,
                        y_min=-ly_half, y_max=ly_half + y_max_adj,
                        z_base=0.0,
                        roof_height=w_roof_h,
                        overhang=props.roof_overhang,
                        wall_thickness=wall_t,
                        gable_ends=w_gable_lr,
                        # Denser ridge steps so valley-notch edges run smooth.
                        segments_y=10,
                        abut_back=loc_abut_back,
                        tier=tier_val,
                        plank_direction=plank_dir,
                        roof_flare=flare_val,
                        dormer_apertures=w_dormer_apertures,
                        eave_exclusions=w_eave_lr,
                        valley_notch=w_notch_lr
                    )

                rot_ang = -math.pi * 0.5 if w_wall == 'LEFT' else math.pi * 0.5
                rot_m = Matrix.Rotation(rot_ang, 4, 'Z')
                trans_m = Matrix.Translation(Vector((w_cx, w_cy, w_top_z)))
                bmesh.ops.transform(wing_roof_bm, matrix=trans_m @ rot_m, verts=wing_roof_bm.verts)

                uv_src = wing_roof_bm.loops.layers.uv.verify()
                uv_dst = bm.loops.layers.uv.verify()
                vert_map = {v: bm.verts.new(v.co) for v in wing_roof_bm.verts}
                for f in wing_roof_bm.faces:
                    try:
                        new_f = bm.faces.new([vert_map[v] for v in f.verts])
                        new_f.material_index = f.material_index
                        new_f.smooth = f.smooth
                        for l_src, l_dst in zip(f.loops, new_f.loops):
                            l_dst[uv_dst].uv = l_src[uv_src].uv
                    except ValueError:
                        pass
                wing_roof_bm.free()

                # Segmented valley flashing for the perpendicular (non-rotated) equal
                # junction (see FRONT): samples both deck profiles, no slits/holes.
                if not is_lower_wing and not is_rotated_roof and roof_style in ('SWAY', 'GABLE'):
                    _ov = props.roof_overhang
                    _ezm = (top_z - 0.12) if roof_style == 'SWAY' else (top_z - 0.10)
                    _swm = props.roof_sway if roof_style == 'SWAY' else 0.0
                    def _main_fn(px, py, _cx=top_cx, _hw=top_hx + _ov, _zb=top_z,
                                 _wr=props.roof_height, _ry0=top_y_min - _ov,
                                 _ry1=top_y_max + _ov, _ez=_ezm, _sw=_swm):
                        return deck_top_z(px, py, _cx, _hw, _zb, _wr,
                                          flare_val, _sw, _ry0, _ry1, _ez,
                                          top_off=0.05)
                    _ezw = -0.12 if roof_style == 'SWAY' else -0.10
                    _sww = props.roof_sway * 0.70 if roof_style == 'SWAY' else 0.0
                    _ly1 = ly_half + y_max_adj
                    if w_wall == 'LEFT':
                        def _wing_fn(px, py, _wc=(w_cx, w_cy), _hw=lx_half + _ov,
                                     _wz=w_top_z, _wr=w_roof_h, _ry0=-ly_half - _ov,
                                     _ry1=_ly1, _ez=_ezw, _sw=_sww):
                            return deck_top_z(-(py - _wc[1]), (px - _wc[0]), 0.0, _hw,
                                              0.0, _wr, flare_val, _sw, _ry0, _ry1,
                                              _ez, top_off=0.05) + _wz
                        die = (w_cx + _ly1, w_cy)
                    else:
                        def _wing_fn(px, py, _wc=(w_cx, w_cy), _hw=lx_half + _ov,
                                     _wz=w_top_z, _wr=w_roof_h, _ry0=-ly_half - _ov,
                                     _ry1=_ly1, _ez=_ezw, _sw=_sww):
                            return deck_top_z((py - _wc[1]), -(px - _wc[0]), 0.0, _hw,
                                              0.0, _wr, flare_val, _sw, _ry0, _ry1,
                                              _ez, top_off=0.05) + _wz
                        die = (w_cx - _ly1, w_cy)
                    corners = []
                    if w_wall == 'LEFT':
                        if has_front:
                            corners.append((top_x_min - _ov, w_top_ymin - _ov))
                        if has_back:
                            corners.append((top_x_min - _ov, w_top_ymax + _ov))
                    else:
                        if has_front:
                            corners.append((top_x_max + _ov, w_top_ymin - _ov))
                        if has_back:
                            corners.append((top_x_max + _ov, w_top_ymax + _ov))
                    for cx0, cy0 in corners:
                        build_valley_rafters(bm, (cx0, cy0), die,
                                             _main_fn, _wing_fn)

    # Dormer Windows
    if props.has_dormers and roof_style in ('SWAY', 'GABLE') and effective_archetype != 'WATCHTOWER':
        tier_val = getattr(props, 'material_tier', 'TIER_3')
        for dp in dormer_placements:
            build_dormer(
                bm,
                center_pos=dp['pos'],
                z_base=z_dormer_base,
                facing_dir=dp['facing'],
                dormer_w=dp.get('dormer_w', main_dormer_w), dormer_d=1.35, dormer_h=cur_dormer_h,
                dormer_roof_h=cur_dormer_roof_h,
                roof_flare=flare_val,
                tier=tier_val,
                max_back_reach=cur_dormer_reach,
                roof_style=roof_style,
                sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0
            )
        for wdp in wing_dormer_placements:
            build_dormer(
                bm,
                center_pos=wdp['pos'],
                z_base=wdp['z_base'],
                facing_dir=wdp['facing'],
                dormer_w=wdp['dormer_w'],
                dormer_d=wdp['dormer_d'],
                dormer_h=wdp['dormer_h'],
                dormer_roof_h=wdp['dormer_roof_h'],
                roof_flare=flare_val,
                tier=tier_val,
                max_back_reach=wdp['max_back_reach'],
                roof_style=roof_style,
                sway_amount=wdp['sway_amount']
            )
            
    # Fairytale Roof Spire Turret (Positionable across roof pitch with attic penetration)
    if getattr(props, 'has_roof_turret', False) and effective_archetype != 'WATCHTOWER':
        t_px = getattr(props, 'roof_turret_pos_x', 0.0)
        t_py = getattr(props, 'roof_turret_pos_y', -0.25)
        t_scale = getattr(props, 'roof_turret_scale', 1.0)
        
        if is_rotated_roof:
            roof_half_w = top_hy + props.roof_overhang
            turret_cx = top_cx + t_px * top_hx * 0.75
            turret_cy = top_cy + t_py * roof_half_w * 0.65
            u_turret = min(1.0, max(0.0, abs(turret_cy - top_cy) / max(0.01, roof_half_w)))
            drop_turret = (1.0 - flare_val) * u_turret + flare_val * (1.0 - (1.0 - u_turret) ** 2)
            if roof_style == 'SWAY':
                t_x = max(0.0, min(1.0, (turret_cx - top_x_min) / max(0.01, 2.0 * top_hx)))
                sway_val = getattr(props, 'roof_sway', 0.25)
                sag_turret = math.sin(t_x * math.pi) * sway_val
            else:
                sag_turret = 0.0
            z_turret_surf = (top_z + props.roof_height - sag_turret) - drop_turret * (props.roof_height + 0.10)
        else:
            roof_half_w = top_hx + props.roof_overhang
            turret_cx = top_cx + t_px * roof_half_w * 0.65
            turret_cy = top_cy + t_py * top_hy * 0.75
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
            for dp in (dormer_placements + wing_dormer_placements):
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
            z_base=z_wing_base, width=w_width, depth=w_depth, height=min(2.05, floor_h * 0.72),
            roof_style=w_roof, tier=tier_val, floor_h=floor_h
        )
        
    # Timber Balcony
    if getattr(props, 'has_balcony', False) and num_floors >= 2 and active_balc_floors:
        b_side = getattr(props, 'balcony_side', 'FRONT')
        b_width = getattr(props, 'balcony_width', 2.4)
        b_depth = getattr(props, 'balcony_depth', 1.3)
        for balc_fl_idx in active_balc_floors:
            z_balc = found_h + balc_fl_idx * floor_h
            b_bounds = floor_wall_bounds.get(balc_fl_idx, (-hx, hx, -hy, hy))
            lower_bounds = floor_wall_bounds.get(max(0, balc_fl_idx - 1), b_bounds)
            build_balcony(
                bm, side=b_side,
                wall_x_min=b_bounds[0], wall_x_max=b_bounds[1], wall_y_min=b_bounds[2], wall_y_max=b_bounds[3],
                lower_wall_x_min=lower_bounds[0], lower_wall_x_max=lower_bounds[1],
                lower_wall_y_min=lower_bounds[2], lower_wall_y_max=lower_bounds[3],
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
    # 8b. Optional split by material — each piece (log, beam, board) becomes separate object with conformal islands
    if getattr(props, 'split_by_material', False):
        try:
            import bpy as _bpy
            _bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            _bpy.ops.object.mode_set(mode='EDIT')
            _bpy.ops.mesh.separate(type='MATERIAL')
            _bpy.ops.object.mode_set(mode='OBJECT')
            # After separate, ensure every new piece has consistent fiber direction via smart UV for handpaint if needed
            for o in [o for o in _bpy.context.scene.objects if o.get("is_fantasy_building", False) or o == obj]:
                if len(o.data.polygons) == 0: continue
                # Keep existing manual UVs (already along length) — no auto re-unwrap to preserve fiber direction
                pass
        except Exception as e:
            print(f"split_by_material failed: {e}")
            try: _bpy.ops.object.mode_set(mode='OBJECT')
            except: pass
    
    # Store settings dictionary on object for independent multi-building recall
    try:
        from ..operators import get_props_dict
        import json
        obj["building_settings"] = json.dumps(get_props_dict(props))
    except Exception:
        pass
