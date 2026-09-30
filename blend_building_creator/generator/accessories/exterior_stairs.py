"""
Exterior wooden staircase and landing for multi-apartment tenements.

Provides direct exterior access to upper-floor apartments via a heavy timber
staircase rising alongside the outer wall to a railed landing platform outside
the upper apartment entrance door.
"""

import math
from mathutils import Vector, Matrix
from ..mesh_utils import create_box, create_beveled_box, create_cylinder
from ..railing import build_railing
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_STAIRS, MAT_INDEX_TIMBER_FRAME,
)


def build_exterior_stairs(bm, props, ctx, tier='TIER_1'):
    """
    Builds a robust fantasy exterior staircase alongside the building facade,
    leading up to a railed landing platform at the second floor.
    """
    if not getattr(props, 'has_exterior_stairs', False):
        return

    side = getattr(props, 'exterior_stairs_side', 'LEFT')
    fl0_bounds = ctx.bounds_for(0)
    fl1_bounds = ctx.bounds_for(1)
    
    x_min, x_max, y_min, y_max = fl1_bounds
    z_ground = 0.0
    z_land = ctx.found_h + ctx.floor_h
    dz = z_land - z_ground

    stair_w = 1.15
    land_len = 1.60
    land_depth = 1.35
    num_steps = max(12, int(round(dz / 0.20)))
    step_h = dz / num_steps
    step_d = 0.28
    flight_len = num_steps * step_d

    uv_layer = bm.loops.layers.uv.verify()

    if side == 'LEFT':
        wall_x = x_min
        # Landing centered at middle of wall
        land_cy = (y_min + y_max) * 0.5
        land_y1 = land_cy - land_len * 0.5
        land_y2 = land_cy + land_len * 0.5
        land_x_out = wall_x - land_depth

        # 1. Timber Landing Platform at z_land
        # Heavy perimeter beams
        beam_t = 0.14
        beam_h = 0.18
        # Outer beam along Y
        create_beveled_box(
            bm, size=(beam_t, land_len, beam_h),
            location=(land_x_out + beam_t * 0.5, land_cy, z_land - beam_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        # Transverse support beams (wall to outer beam)
        for ly in (land_y1, land_y2):
            create_beveled_box(
                bm, size=(land_depth, beam_t, beam_h),
                location=(wall_x - land_depth * 0.5, ly, z_land - beam_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
            )
        # Heavy wood deck planks
        create_beveled_box(
            bm, size=(land_depth + 0.04, land_len + 0.04, 0.06),
            location=(wall_x - land_depth * 0.5, land_cy, z_land + 0.03),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
        )

        # 2. Vertical Support Posts down to ground
        post_size = 0.18
        for ly in (land_y1 + 0.10, land_y2 - 0.10):
            px = land_x_out + post_size * 0.5 + 0.02
            pz = (z_ground + z_land) * 0.5
            create_beveled_box(
                bm, size=(post_size, post_size, z_land),
                location=(px, ly, pz),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
            )
            # Diagonal knee braces from post up to landing beam
            brace_len = 0.85
            create_beveled_box(
                bm, size=(0.10, 0.10, brace_len),
                location=(px + 0.22, ly, z_land - 0.35),
                rotation=(0.0, 0.785, 0.0),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
            )

        # 3. Guard Rails around landing (outer side and rear end)
        rail_h = 0.95
        build_railing(bm, (land_x_out, land_y1), (land_x_out, land_y2),
                      z_land + 0.06, height=rail_h, post_spacing=1.0)
        build_railing(bm, (land_x_out, land_y2), (wall_x - 0.10, land_y2),
                      z_land + 0.06, height=rail_h, braces=False, post_spacing=1.0)

        # 4. Straight Flight of Stairs ascending from South (-Y) up to landing at land_y1
        stair_start_y = land_y1 - flight_len
        stair_cx = wall_x - stair_w * 0.5 - 0.05
        tread_thick = 0.06
        tread_d = step_d + 0.04

        for i in range(num_steps):
            sz = z_ground + (i + 0.5) * step_h
            sy = stair_start_y + (i + 0.5) * step_d
            create_beveled_box(
                bm, size=(stair_w, tread_d, tread_thick),
                location=(stair_cx, sy, sz),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
            )
            # Riser plank
            create_box(
                bm, size=(stair_w - 0.02, 0.04, step_h),
                location=(stair_cx, sy - step_d * 0.5 + 0.02, sz - step_h * 0.5),
                mat_index=MAT_INDEX_STAIRS
            )

        # Outer Diagonal Timber Stringer
        stringer_x = wall_x - stair_w - 0.06
        diag_len = math.hypot(dz, flight_len)
        pitch = math.atan2(dz, flight_len)
        mid_sy = (stair_start_y + land_y1) * 0.5
        mid_sz = (z_ground + z_land) * 0.5
        create_box(
            bm, size=(0.10, diag_len, 0.22),
            location=(stringer_x, mid_sy, mid_sz),
            rotation=(pitch, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )
        # Outer handrail along the stair flight
        build_railing(
            bm,
            (stringer_x, stair_start_y + 0.08),
            (stringer_x, land_y1),
            z_ground + 0.06, height=rail_h, base_z_end=z_land + 0.06,
            post_spacing=1.1, baluster_spacing=0.22, braces=False
        )

        # Ground Starter Timber Block
        create_beveled_box(
            bm, size=(stair_w + 0.20, 0.30, 0.12),
            location=(stair_cx, stair_start_y + 0.10, z_ground + 0.06),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
        )
