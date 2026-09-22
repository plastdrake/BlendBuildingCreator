"""Round (smooth, many-sided) tower footprint builder.

The original tower was an 8-faceted prism, which read as a low-poly octagon
rather than the genuinely round, whimsical wizard towers in the reference art.
This rebuild drives the whole shell from a single ``segments`` count (default
16) so the silhouette is properly round while every opening is still a real
cut-out produced by the shared :func:`walls.build_wall_with_opening` system.

Curved-shell maths (segment frames, annular slabs, corner posts, corbels, the
wall ring) live in :mod:`generator.poly` so the chapel apse can reuse them. The
Mage Tower archetype layers the whimsy on top (jettied belvedere, ring balcony,
side tourelle, arcane crystal finial) without touching the core shell logic.
"""

import math
from mathutils import Vector
from .mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_FLOOR, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_PLASTER_EXT, MAT_INDEX_CUT_STONE,
    MAT_INDEX_GLASS, MAT_INDEX_IRON, MAT_INDEX_SHINGLES,
)
from .poly import (
    segment_frame, ring_slab, corner_posts, corbel_ring, wall_ring,
)
from .interior import build_spiral_staircase
from .openings import build_door_assembly, build_front_steps, build_window_assembly


def _ring_railing(bm, radius, z_floor, height=1.0, segments=16, offset=0.0):
    """Posts + top rail so a circular balcony reads as walkable."""
    d_ang = 2.0 * math.pi / segments
    for k in range(segments):
        ang = k * d_ang + offset
        create_beveled_box(
            bm, size=(0.075, 0.075, height),
            location=(radius * math.cos(ang), radius * math.sin(ang),
                      z_floor + height * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
        )
    ring_slab(bm, radius - 0.06, radius + 0.06, z_floor + height,
              segments, offset, MAT_INDEX_TIMBER, height=0.08,
              overlap=1.05, bevel=0.006)


def _conical_spire(bm, cx, cy, z_base, radius, height, segments=16):
    """Flared, shingle-UV'd conical spire with a timber eave ring."""
    uv_layer = bm.loops.layers.uv.verify()
    cone_faces = create_cone(
        bm, radius1=radius, radius2=0.06, height=height, segments=segments,
        location=(cx, cy, z_base + height * 0.5), mat_index=MAT_INDEX_SHINGLES,
    )
    for f in cone_faces:
        if f.material_index == MAT_INDEX_SHINGLES:
            for loop in f.loops:
                co = loop.vert.co
                ang = math.atan2(co.y - cy, co.x - cx)
                loop[uv_layer].uv = Vector(((ang + math.pi) / (2.0 * math.pi),
                                            co.z * 0.32))
    create_cylinder(bm, radius=radius * 0.86, height=0.16, segments=segments,
                    location=(cx, cy, z_base + 0.20), mat_index=MAT_INDEX_SHINGLES)
    create_cylinder(bm, radius=radius + 0.14, height=0.14, segments=segments,
                    location=(cx, cy, z_base + 0.07), mat_index=MAT_INDEX_TIMBER)


def _arcane_crystal(bm, cx, cy, z, scale=1.0):
    """A small glowing octahedral crystal — the whimsical spire finial."""
    s = max(0.4, scale)
    r = 0.20 * s
    create_cone(bm, radius1=r, radius2=0.0, height=0.46 * s, segments=4,
                location=(cx, cy, z + 0.23 * s),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_GLASS)
    create_cone(bm, radius1=0.0, radius2=r, height=0.30 * s, segments=4,
                location=(cx, cy, z - 0.15 * s),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_GLASS)
    create_cylinder(bm, radius=0.035 * s, height=0.22 * s, segments=6,
                    location=(cx, cy, z + 0.50 * s), mat_index=MAT_INDEX_IRON)


def _entrance_hood(bm, cx, cy, z_base, radius, width, height, fn):
    """A little projecting arched hood over the tower door."""
    fy = cy + fn.y * (radius + 0.18)
    create_beveled_box(bm, size=(width + 0.30, 0.55, 0.16),
                       location=(cx, fy, z_base + height + 0.10),
                       mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    for s in (-1.0, 1.0):
        create_beveled_box(bm, size=(0.10, 0.42, 0.10),
                           location=(cx + s * (width * 0.5 - 0.02),
                                     cy + fn.y * (radius + 0.02),
                                     z_base + height - 0.05),
                           rotation=(fn.y * -0.5, 0.0, 0.0),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008)


def _build_side_turret(bm, attach_ang, tower_r, z_start, wall_t,
                       win_w, win_h):
    """A corbelled round tourelle clinging to the tower flank, with a spire."""
    cx = math.cos(attach_ang) * (tower_r - 0.10)
    cy = math.sin(attach_ang) * (tower_r - 0.10)
    t_r = 0.85
    t_h = 3.1
    for i in range(3):
        rr = tower_r * 0.55 + i * 0.16
        create_cylinder(bm, radius=rr, height=0.16, segments=8,
                        location=(cx * (0.7 + i * 0.1), cy * (0.7 + i * 0.1),
                                  z_start + 0.16 * i),
                        mat_index=MAT_INDEX_STONE)
    base_z = z_start + 0.48
    create_cylinder(bm, radius=t_r + wall_t * 0.5, height=t_h, segments=10,
                    location=(cx, cy, base_z + t_h * 0.5), mat_index=MAT_INDEX_STONE)
    for dz in (0.9, 2.1):
        if dz > t_h - 0.6:
            continue
        build_window_assembly(
            bm,
            center=(cx + math.cos(attach_ang) * (t_r + wall_t * 0.5 - 0.02),
                    cy + math.sin(attach_ang) * (t_r + wall_t * 0.5 - 0.02),
                    base_z + dz),
            size=(win_w * 0.8, win_h * 0.8), wall_thickness=wall_t * 1.2,
            normal_axis=(math.cos(attach_ang), math.sin(attach_ang)),
            has_shutters=False,
        )
    roof_z = base_z + t_h
    _conical_spire(bm, cx, cy, roof_z, radius=t_r + 0.24, height=2.1)
    top = roof_z + 2.1
    create_cylinder(bm, radius=0.045, height=0.7, segments=6,
                    location=(cx, cy, top + 0.35), mat_index=MAT_INDEX_IRON)


def build_round_tower(bm, props, seed):
    """Build a genuinely round fantasy tower.

    Driven entirely by the preset properties so one code path serves every
    tier: floor count, wall material and overhang come from the props, while
    the Mage Tower archetype layers on the belvedere balcony, side tourelle
    and arcane crystal finial.
    """
    num_floors = max(1, props.num_floors)
    floor_h = props.floor_height
    radius = max(1.7, props.width * 0.45)
    wall_t = props.wall_thickness
    found_h = props.foundation_height if props.has_foundation else 0.4
    cantilever = props.cantilever_overhang if props.has_cantilever else 0.0
    total_height = found_h + num_floors * floor_h + props.roof_height

    archetype = getattr(props, 'building_archetype', 'AUTO')
    # The whimsical, half-open Mage Tower is its own (large, tall) builder;
    # every other round footprint keeps the compact shell below.
    if archetype in ('MAGE_TOWER', 'AUTO', 'WIZARD'):
        from .mage_tower import build_mage_tower
        build_mage_tower(bm, props, seed)
        return
    is_mage = False

    segments = 16
    d_ang = 2.0 * math.pi / segments
    # Offset so the centre of segment 0 faces -Y (the front door).
    offset_ang = -math.pi * 0.5 - d_ang * 0.5

    tier_val = getattr(props, 'material_tier', 'TIER_3')
    phys_siding = getattr(props, 'physical_siding', True)
    plank_dir = getattr(props, 'plank_direction', 'HORIZONTAL')
    plank_jank = getattr(props, 'plank_jankiness', 0.35)
    stone_scale = getattr(props, 'stone_block_scale', 1.0)
    stone_disorder = getattr(props, 'stone_disorder', 0.35)

    # ---- Foundation: broad battered stone plinth ----
    if props.has_foundation:
        create_cylinder(bm, radius=radius + 0.55, height=found_h * 0.55, segments=segments,
                        location=(0.0, 0.0, found_h * 0.275), mat_index=MAT_INDEX_CUT_STONE)
        create_cylinder(bm, radius=radius + 0.30, height=found_h * 0.55, segments=segments,
                        location=(0.0, 0.0, found_h * 0.72), mat_index=MAT_INDEX_STONE)

    prev_r = radius
    cur_r = radius
    belvedere_floor = None

    for fl_idx in range(num_floors):
        z_floor = found_h + fl_idx * floor_h
        z_ceil = z_floor + floor_h
        fl_overhang = cantilever if (fl_idx >= 1 and props.has_cantilever) else 0.0
        cur_r = radius + fl_overhang
        is_top = (fl_idx == num_floors - 1)

        # ---- Floor slab (annular, with a central spiral-stair well) ----
        mat_fl = (MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone)
                  else MAT_INDEX_FLOOR)
        stair_r = min(cur_r - wall_t - 0.25, 1.10)
        well_r = stair_r + 0.10
        if fl_idx == 0 or not props.has_stairs:
            create_cylinder(bm, radius=cur_r - 0.02, height=0.12, segments=segments,
                            location=(0.0, 0.0, z_floor + 0.06), mat_index=mat_fl)
        else:
            ring_slab(bm, well_r, cur_r - 0.02, z_floor + 0.06, segments,
                      offset_ang, mat_fl)
            create_beveled_box(bm, size=(0.60, well_r * 0.95, 0.12),
                               location=(0.0, -well_r * 0.52, z_floor + 0.06),
                               mat_index=mat_fl, bevel_amount=0.01)

        # ---- Cantilever corbels + soffit under the jetty ----
        if fl_idx > 0 and fl_overhang > 0.01:
            corbel_ring(bm, prev_r + fl_overhang * 0.5, z_floor - 0.18,
                        segments, offset_ang)
            ring_slab(bm, prev_r - 0.02, cur_r + 0.02, z_floor - 0.02, segments,
                      offset_ang, MAT_INDEX_WOOD, height=0.10)

        # ---- Spiral staircase ----
        if fl_idx < num_floors - 1 and props.has_stairs:
            build_spiral_staircase(
                bm, center_pos=(0.0, 0.0, z_floor + 0.05),
                target_z=z_ceil + 0.05, radius=stair_r,
                start_ang_deg=-90.0, total_angle_deg=360.0,
            )

        # ---- Ceiling beams (radial to keep the stair well clear) ----
        if props.has_ceiling_beams:
            beam_d = 0.16
            beam_span = max(0.25, (cur_r - 0.05) - well_r)
            beam_mid_r = well_r + beam_span * 0.5
            for k in range(segments):
                b_ang = k * d_ang + offset_ang
                create_box(bm, size=(beam_span, 0.14, beam_d),
                           location=(beam_mid_r * math.cos(b_ang),
                                     beam_mid_r * math.sin(b_ang),
                                     z_ceil - beam_d * 0.5),
                           rotation=(0.0, 0.0, b_ang), mat_index=MAT_INDEX_WOOD)

        # ---- Shell: wall material per tier (ground stone base) ----
        if tier_val == 'TIER_1':
            mat_w = MAT_INDEX_TIMBER
        elif tier_val == 'TIER_2':
            mat_w = MAT_INDEX_WOOD
        else:
            mat_w = (MAT_INDEX_STONE if (fl_idx == 0 and props.ground_floor_stone)
                     else MAT_INDEX_PLASTER_EXT)

        win_w = min(0.95, props.window_width)
        win_h = props.window_height
        win_cz = z_floor + floor_h * 0.50
        opening_segments = [k for k in range(segments) if k % 2 == 1]
        turret_seg = None
        if getattr(props, 'has_roof_turret', False) and fl_idx >= 1:
            turret_seg = int(round((math.pi * 0.5 - offset_ang) / d_ang)) % segments

        openings_by_seg = {}
        for k in range(segments):
            p1, p2, fn_vec, mid = segment_frame(cur_r, k, segments, offset_ang)
            facet_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            ops = []
            is_door = (fl_idx == 0 and k == 0 and props.has_front_door)
            has_window = (props.has_windows and k in opening_segments
                          and k != turret_seg and not is_door)

            if is_door:
                dw = min(facet_len - 0.34, props.door_width)
                dh = props.door_height
                margin = 0.13
                u1 = (facet_len - dw) * 0.5 - margin
                u2 = (facet_len + dw) * 0.5 + margin
                ops.append({'u_start': max(0.02, u1),
                            'u_end': min(facet_len - 0.02, u2),
                            'z_start': z_floor,
                            'z_end': z_floor + dh + margin})
                build_door_assembly(
                    bm, center_x=mid[0], y_front=mid[1], z_base=z_floor,
                    wall_thickness=wall_t, door_w=dw, door_h=dh,
                    door_angle_deg=props.door_angle,
                    door_shape=getattr(props, 'door_shape', 'AUTO'),
                    ground_floor_stone=props.ground_floor_stone,
                )
                if props.has_front_steps and props.has_foundation:
                    build_front_steps(bm, center_x=mid[0], y_front=mid[1],
                                      z_base=z_floor,
                                      num_steps=max(2, int(found_h / 0.18)))
                if getattr(props, 'has_arched_porch', False):
                    _entrance_hood(bm, mid[0], mid[1], z_floor, cur_r, dw, dh, fn_vec)
            elif has_window and facet_len > win_w + 0.30:
                u1 = (facet_len - win_w) * 0.5
                ops.append({'u_start': u1, 'u_end': u1 + win_w,
                            'z_start': win_cz - win_h * 0.5,
                            'z_end': win_cz + win_h * 0.5})
                build_window_assembly(
                    bm, center=(mid[0], mid[1], win_cz), size=(win_w, win_h),
                    wall_thickness=wall_t, normal_axis=(fn_vec.x, fn_vec.y),
                    has_shutters=props.has_shutters,
                )
            openings_by_seg[k] = ops

        wall_ring(
            bm, cur_r, z_floor, z_ceil, wall_t, segments, offset_ang,
            openings_by_seg, mat_w, tier=tier_val, seed=seed,
            physical_siding=phys_siding, plank_direction=plank_dir,
            plank_jankiness=plank_jank, stone_block_scale=stone_scale,
            stone_disorder=stone_disorder,
            has_exposed_brick=getattr(props, 'has_exposed_brick', True),
            exposed_brick_freq=getattr(props, 'exposed_brick_frequency', 0.25),
        )
        corner_posts(bm, cur_r, z_floor, floor_h, segments, offset_ang)

        if is_top:
            belvedere_floor = (fl_idx, cur_r)
        prev_r = cur_r

    # ---- Ring balcony on the jettied belvedere ----
    if getattr(props, 'has_balcony', False) and belvedere_floor is not None:
        fl_i, r_top = belvedere_floor
        zb = found_h + fl_i * floor_h
        _ring_slab_out = r_top + 0.72
        ring_slab(bm, r_top + 0.02, _ring_slab_out, zb - 0.06, segments,
                  offset_ang, MAT_INDEX_FLOOR, height=0.12)
        corbel_ring(bm, r_top + 0.30, zb - 0.26, segments, offset_ang)
        _ring_railing(bm, _ring_slab_out - 0.05, zb, height=1.0,
                      segments=segments, offset=offset_ang)

    # ---- Side tourelle ----
    if getattr(props, 'has_roof_turret', False):
        attach_ang = math.pi * 0.5
        z_start = found_h + max(1, num_floors - 2) * floor_h
        _build_side_turret(bm, attach_ang, radius, z_start, wall_t,
                           min(0.85, props.window_width), props.window_height)

    # ---- Roof ----
    top_z = found_h + num_floors * floor_h
    top_r = cur_r
    if archetype != 'WATCHTOWER':
        spire_h = props.roof_height * (1.45 if is_mage else 1.25)
        _conical_spire(bm, 0.0, 0.0, top_z, radius=top_r * 1.16,
                       height=spire_h, segments=segments)
        apex = top_z + spire_h
        if is_mage:
            create_cylinder(bm, radius=0.05, height=0.65, segments=6,
                            location=(0.0, 0.0, apex + 0.32), mat_index=MAT_INDEX_IRON)
            _arcane_crystal(bm, 0.0, 0.0, apex + 0.95, scale=1.0)
        else:
            create_cylinder(bm, radius=0.045, height=1.0, segments=6,
                            location=(0.0, 0.0, apex + 0.5), mat_index=MAT_INDEX_IRON)

    # ---- Chimney ----
    if props.has_chimney and archetype != 'WATCHTOWER':
        from .roof import build_fantasy_chimney
        build_fantasy_chimney(
            bm, pos_xy=(top_r * 0.62, top_r * 0.42), z_start=0.0,
            total_height=top_z + 0.8, width=0.72, depth=0.72,
            crooked_angle=0.05,
        )

    # ---- Non-tower archetypes that reuse the round shell ----
    if archetype == 'WINDMILL':
        from .accessories.windmill import build_windmill_sails
        hub_z = top_z - 0.35
        build_windmill_sails(bm, cx=0.0, front_y=-top_r, hub_z=hub_z,
                             radius=max(2.8, top_r * 1.8), wall_y=-top_r + 0.35)
    elif archetype == 'WATCHTOWER':
        from .accessories.watchtower import build_watchtower_lookout
        build_watchtower_lookout(bm, -top_r, top_r, -top_r, top_r, z_platform=top_z)
