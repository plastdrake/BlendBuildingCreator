"""
Builder's Yard & Guild accessory generator.
Specialized for the city construction builder archetype on a square 16m x 16m plot:
- Tier 1: Clean open-air construction yard (no perimeter wooden frame),
  dual outward-facing swivel cranes, canvas tarp & lean-to awnings,
  workbenches, cut stone, logs, and ladders laid flat on the ground with zero overlap.
- Tier 2: Guildhouse with front yard swivel crane angled away from building,
  window-safe flank lean-to shelter, cut stone stacks clear of steps, and flat ground ladder.
- Tier 3: Master Builder headquarters with courtyard heavy swivel crane angled away from walls,
  flank staging, and dressed ashlar stacks (no side wall crane, no hole in wall, flat ground ladder).
"""

import math
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder,
    create_horizontal_cylinder
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG, MAT_INDEX_LOG_END,
    MAT_INDEX_ROPE
)
from .crane import build_courtyard_crane
from .warehouse import build_tarp_awning, build_lean_to_awning
from .quarry import build_cut_block_stack
from .furniture import build_crate, build_barrel


def build_ground_ladder(bm, x, y, length=2.4, width=0.46, rot_z=0.0, z_ground=0.0):
    """
    Constructs a timber work ladder laid completely flat on the ground.
    Zero tilt, zero floating, zero roof/wall penetration.
    """
    cos_r = math.cos(rot_z)
    sin_r = math.sin(rot_z)
    rail_w = 0.055
    rail_h = 0.065
    half_w = (width - rail_w) * 0.5
    rz = z_ground + rail_h * 0.5 + 0.005

    def _rot(lx, ly):
        return (x + lx * cos_r - ly * sin_r,
                y + lx * sin_r + ly * cos_r)

    # 1. Two parallel rails lying flat along local Y
    for s in (-1.0, 1.0):
        rx, ry = _rot(s * half_w, 0.0)
        create_beveled_box(
            bm, size=(rail_w, length, rail_h),
            location=(rx, ry, rz),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )

    # 2. Rungs lying flat between rails
    num_rungs = max(3, int(length / 0.28))
    actual_step = (length - 0.20) / max(1, num_rungs - 1)
    rung_len = width - rail_w * 0.8
    for ri in range(num_rungs):
        local_y = -length * 0.5 + 0.10 + ri * actual_step
        rx, ry = _rot(0.0, local_y)
        create_cylinder(
            bm, radius=0.018, height=rung_len, segments=8,
            location=(rx, ry, rz),
            rotation=(0.0, math.pi * 0.5, rot_z),
            mat_index=MAT_INDEX_WOOD
        )


def build_builder_log_stack(bm, cx, cy, z_floor=0.0, log_len=1.8, log_r=0.12):
    """Stack of round timber logs on heavy wooden ground chocks."""
    # Base chocks
    for cs in (-0.40, 0.40):
        create_beveled_box(
            bm, size=(0.12, 0.14, 0.09),
            location=(cx + cs, cy, z_floor + 0.045),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )
    # Layer 1: 3 logs
    for l_off in (-0.24, 0.0, 0.24):
        create_horizontal_cylinder(
            bm, radius_y=log_r, radius_z=log_r, length=log_len, segments=12,
            location=(cx + l_off, cy, z_floor + log_r),
            rotation=(0.0, 0.0, 1.5708),
            mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
        )
    # Layer 2: 2 logs
    for l_off in (-0.12, 0.12):
        create_horizontal_cylinder(
            bm, radius_y=log_r * 0.95, radius_z=log_r * 0.95, length=log_len - 0.10, segments=12,
            location=(cx + l_off, cy, z_floor + log_r * 2.45),
            rotation=(0.0, 0.0, 1.5708),
            mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
        )
    # Layer 3: 1 apex log
    create_horizontal_cylinder(
        bm, radius_y=log_r * 0.90, radius_z=log_r * 0.90, length=log_len - 0.20, segments=12,
        location=(cx, cy, z_floor + log_r * 3.85),
        rotation=(0.0, 0.0, 1.5708),
        mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
    )


def build_sawn_lumber_stack(bm, px, py, z_floor=0.0, layers=4, plank_l=1.5, plank_w=0.75):
    """Stacked sawn lumber planks with cross-batten spacers."""
    for so in (-0.45, 0.0, 0.45):
        create_beveled_box(
            bm, size=(0.09, plank_w + 0.12, 0.07),
            location=(px + so, py, z_floor + 0.035),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )
    for layer in range(layers):
        lz = z_floor + 0.07 + layer * 0.10
        create_beveled_box(
            bm, size=(plank_l, plank_w, 0.075),
            location=(px, py, lz + 0.0375),
            rotation=(0.0, 0.0, 0.015),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
        )
        if layer < layers - 1:
            for s_off in (-0.50, 0.0, 0.50):
                create_box(
                    bm, size=(0.04, plank_w + 0.02, 0.025),
                    location=(px + s_off, py, lz + 0.0875),
                    mat_index=MAT_INDEX_TIMBER
                )


def build_builder_tier1_yard(bm, min_x, max_x, min_y, max_y, z_floor=0.0, seed=42):
    """
    Tier 1: Open-air city construction builder yard on a 16m x 16m plot.
    - No wooden frame around the plot (clean open dirt yard)
    - Dual outward-facing swivel cranes in front corners
    - Canvas tarp awning (North-West) with joiner's bench
    - Timber lean-to awning (North-East) with sawn lumber
    - Ashlar cut stone stack on mid-West, round log stack on mid-East (>1.8m clearance from cranes)
    - Ladders laid flat on the ground (no floating, no roof penetration)
    """
    from .artisan_props import build_joiner_bench

    # 1. DUAL CRANES (Positioned at front corners, pointing outward to front-center loading area)
    # Crane 1 (South-West): Mast at (-4.0, -3.5). Stone pad radius 1.0m (X: [-5.0, -3.0], Y: [-4.5, -2.5]).
    # Boom points South-East (away from stone stack and back awning).
    crane1_x = -4.0
    crane1_y = -3.5
    build_courtyard_crane(
        bm, yard_x=crane1_x, yard_y=crane1_y, z_ground=z_floor,
        mast_height=4.2, jib_length=3.0, rot_angle=-0.50,
        include_stone_pad=True, pad_radius=1.00
    )

    # Crane 2 (South-East): Mast at (4.0, -3.5). Stone pad radius 1.0m (X: [3.0, 5.0], Y: [-4.5, -2.5]).
    # Boom points South-West (away from lumber stack and back awning).
    crane2_x = 4.0
    crane2_y = -3.5
    build_courtyard_crane(
        bm, yard_x=crane2_x, yard_y=crane2_y, z_ground=z_floor,
        mast_height=3.6, jib_length=2.8, rot_angle=-2.60,
        include_stone_pad=True, pad_radius=1.00
    )

    # 2. AWNINGS (In the North-West and North-East quadrants, Y: 3.5)
    # Awning 1: Canvas Tarp Awning (North-West: X: [-4.9, -2.1], Y: [2.3, 4.7])
    tarp_cx = -3.5
    tarp_cy = 3.5
    tarp_w = 2.8
    tarp_d = 2.4
    build_tarp_awning(
        bm, cx=tarp_cx, cy=tarp_cy, z_base=z_floor,
        width=tarp_w, depth=tarp_d, front_h=2.25, back_h=2.75,
        yaw=0.0
    )
    # Joiner's workbench centered under the canvas awning
    build_joiner_bench(bm, x=tarp_cx, y=tarp_cy, z_ground=z_floor, ang=0.0, length=1.30)
    build_crate(bm, x=-4.3, y=4.1, z_ground=z_floor, ang=0.15, size=0.45, height=0.42, brace_style='DIAGONAL')

    # Awning 2: Rustic Board Lean-To Awning (North-East: X: [2.1, 4.9], Y: [2.3, 4.7])
    leanto_cx = 3.5
    leanto_cy = 3.5
    leanto_w = 2.8
    leanto_d = 2.4
    build_lean_to_awning(
        bm, cx=leanto_cx, cy=leanto_cy, z_base=z_floor,
        width=leanto_w, depth=leanto_d, front_h=2.05, back_h=2.60
    )
    # Sawn lumber stack centered under the lean-to awning
    build_sawn_lumber_stack(bm, px=leanto_cx, py=leanto_cy, z_floor=z_floor, layers=4, plank_l=1.5, plank_w=0.75)
    build_barrel(bm, x=4.3, y=4.1, z_ground=z_floor, ang=0.0, radius=0.26, height=0.65)

    # 3. MID-YARD MATERIALS (Y: 0.0, completely isolated from both cranes and awnings)
    # Cut Ashlar Stone Block Stack (West mid-yard: X = -3.5, Y = 0.0)
    # Spans X: [-4.6, -2.4], Y: [-0.5, 0.5].
    # Clearance to Crane 1 pad: 2.0m! Clearance to Tarp Awning: 1.8m!
    build_cut_block_stack(bm, x=-3.5, y=0.0, z_ground=z_floor, count=6, seed=seed + 10)

    # Round Timber Log Stack (East mid-yard: X = 3.5, Y = 0.0)
    # Spans X: [2.6, 4.4], Y: [-0.4, 0.4].
    # Clearance to Crane 2 pad: 2.1m! Clearance to Lean-To Awning: 1.9m!
    build_builder_log_stack(bm, cx=3.5, cy=0.0, z_floor=z_floor, log_len=1.8)

    # 4. FRONT-CENTER LOADING STAGING (X: -0.4 to 0.4, Y: -3.8)
    # Flanked by both cranes with >2.5m clearance to pads on either side
    build_crate(bm, x=-0.4, y=-3.8, z_ground=z_floor, ang=0.1, size=0.48, height=0.45, brace_style='CROSS')
    build_barrel(bm, x=0.4, y=-3.8, z_ground=z_floor, ang=0.0, radius=0.26, height=0.65)

    # 5. WORK LADDERS LAID FLAT ON GROUND (No floating, no roof penetration)
    # Ladder 1: Staged flat on ground on West flank near workbench
    build_ground_ladder(bm, x=-5.2, y=3.0, length=2.4, width=0.46, rot_z=0.0, z_ground=z_floor)

    # Ladder 2: Staged flat on ground on East flank near lumber
    build_ground_ladder(bm, x=5.2, y=3.0, length=2.4, width=0.46, rot_z=0.0, z_ground=z_floor)


def build_builder_tier2_yard(bm, props, ctx, hx, hy, seed=42):
    """
    Tier 2: Builder's Guildhouse & Workshop on square plot.
    Guaranteed zero overlaps:
    - Crane boom points South-West away from building
    - Lean-to shelter rests against solid right wall (no windows/shutters on right)
    - Front steps and door completely clear of stone blocks and props
    - Work ladder laid flat on the ground
    """
    from .artisan_props import build_joiner_bench

    z_floor = 0.0

    # 1. Courtyard Crane in front-left yard
    # Mast at (-hx - 0.4, -hy - 2.0). Pad edge is 0.95m clear of front wall at Y = -hy.
    # Boom points South-West (rot_angle = -2.3), pointing completely AWAY from the building!
    crane_x = -hx - 0.4
    crane_y = -hy - 2.0
    build_courtyard_crane(
        bm, yard_x=crane_x, yard_y=crane_y, z_ground=z_floor,
        mast_height=4.0, jib_length=2.8, rot_angle=-2.30,
        include_stone_pad=True, pad_radius=1.00
    )

    # 2. Rustic Lean-To Awning on Right Flank (against solid right wall, window_right is False)
    leanto_x = hx + 1.35
    leanto_y = -0.4
    build_lean_to_awning(
        bm, cx=leanto_x, cy=leanto_y, z_base=z_floor,
        width=2.5, depth=2.2, front_h=2.00, back_h=2.55
    )
    build_sawn_lumber_stack(bm, px=leanto_x, py=leanto_y, z_floor=z_floor, layers=4, plank_l=1.5, plank_w=0.75)

    # 3. Cut Stone Stack in Front-Right Yard
    # Front steps are in X: [-1.4, 1.4]. Stack is placed at X = hx + 0.3 (>3.5m clear of steps!)
    stone_x = hx + 0.3
    stone_y = -hy - 1.8
    build_cut_block_stack(bm, stone_x, stone_y, z_ground=z_floor, count=6, seed=seed + 15)

    # 4. Work Ladder Laid Flat on Ground along the right flank
    build_ground_ladder(bm, x=hx + 1.35, y=-2.5, length=2.2, width=0.46, rot_z=0.0, z_ground=z_floor)

    # 5. Joiner's Bench placed neatly along the right flank behind the lean-to
    build_joiner_bench(bm, x=hx + 1.35, y=1.5, z_ground=z_floor, ang=1.5708, length=1.35)
    build_crate(bm, x=stone_x - 1.3, y=stone_y - 0.2, z_ground=z_floor, ang=0.15, size=0.48, height=0.45, brace_style='DIAGONAL')


def build_builder_tier3_yard(bm, props, ctx, hx, hy, seed=42):
    """
    Tier 3: Master Builder Headquarters & Guildhall on square plot.
    Guaranteed zero overlaps:
    - No side wall jib crane and no hole in wall
    - Courtyard heavy crane angled South-West away from building
    - Front steps and entrance completely clear
    - Dressed ashlar stone stacks and sawn lumber along flanks
    - Work ladder laid flat on the ground
    """
    z_floor = 0.0

    # 1. Courtyard Heavy Swivel Crane in front-left yard
    # Boom points South-West (rot_angle = -2.35), completely AWAY from building!
    crane_x = -hx - 0.5
    crane_y = -hy - 2.2
    build_courtyard_crane(
        bm, yard_x=crane_x, yard_y=crane_y, z_ground=z_floor,
        mast_height=4.6, jib_length=3.2, rot_angle=-2.35,
        include_stone_pad=True, pad_radius=1.10
    )

    # 2. Cut Stone Ashlar Block Stacks (Clear of front steps in X: [-1.5, 1.5])
    stone1_x = hx + 0.3
    stone1_y = -hy - 1.8
    build_cut_block_stack(bm, stone1_x, stone1_y, z_ground=z_floor, count=8, seed=seed + 10)

    # Second stone stack along right flank
    stone2_x = hx + 1.35
    stone2_y = 1.0
    build_cut_block_stack(bm, stone2_x, stone2_y, z_ground=z_floor, count=6, seed=seed + 25)

    # Sawn lumber stack on right flank (Y: -1.2, clear of stone2 at Y: 1.0)
    build_sawn_lumber_stack(bm, px=hx + 1.35, py=-1.2, z_floor=z_floor, layers=5, plank_l=1.6, plank_w=0.80)

    # 3. Work Ladder Laid Flat on Ground along the right flank
    build_ground_ladder(bm, x=hx + 1.35, y=-2.8, length=2.4, width=0.46, rot_z=0.0, z_ground=z_floor)

    # 4. Tool Crates & Barrels near stone staging
    build_crate(bm, x=stone1_x - 1.3, y=stone1_y - 0.2, z_ground=z_floor, ang=0.15, size=0.48, height=0.45, brace_style='DIAGONAL')
    build_barrel(bm, x=crane_x - 0.2, y=crane_y + 1.5, z_ground=z_floor, ang=0.0, radius=0.28, height=0.68)
