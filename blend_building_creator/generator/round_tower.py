"""Round (8-sided faceted) tower footprint builder.

Extracted from ``building.py``; the orchestrator simply dispatches to it when
the footprint shape is ``ROUND_TOWER``.
"""

import math
from mathutils import Vector
from .mesh_utils import create_box, create_beveled_box, create_cylinder
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_FLOOR, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_PLASTER_EXT,
)
from .interior import build_spiral_staircase
from .openings import build_door_assembly, build_front_steps, build_window_assembly
from .walls import build_wall_with_opening
from .roof import build_conical_turret_roof, build_fantasy_chimney
from .accessories.windmill import build_windmill_sails
from .accessories.watchtower import build_watchtower_lookout


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
                                          has_shutters=props.has_shutters)

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
