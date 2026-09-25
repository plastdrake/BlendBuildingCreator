import math
from mathutils import Vector, Matrix, Euler
from ..facade import get_facade_frame
from ..uv_utils import map_planar_faces
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten, transform_faces
)
from ..walls import create_curved_corbel
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG, MAT_INDEX_LOG_END,
    MAT_INDEX_ROPE, MAT_INDEX_LANTERN, MAT_INDEX_TARP, MAT_INDEX_DIRT,
    MAT_INDEX_CLAY
)


def build_warehouse_cargo(bm, front_x, front_y, z_ground):
    create_beveled_box(
        bm, size=(0.85, 0.85, 0.85),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
    )
    create_box(
        bm, size=(0.87, 0.10, 0.87),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_IRON
    )
    create_beveled_box(
        bm, size=(0.60, 0.60, 0.60),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.85 + 0.30),
        rotation=(0.0, 0.0, -0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    for bx, by in [(front_x - 1.45, front_y - 0.60), (front_x - 1.05, front_y - 0.95)]:
        create_cylinder(
            bm, radius=0.32, height=0.75, segments=12,
            location=(bx, by, z_ground + 0.375),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=0.328, height=0.05, segments=12,
            location=(bx, by, z_ground + 0.18),
            mat_index=MAT_INDEX_IRON
        )
        create_cylinder(
            bm, radius=0.328, height=0.05, segments=12,
            location=(bx, by, z_ground + 0.57),
            mat_index=MAT_INDEX_IRON
        )


def build_tarp_awning(bm, cx, cy, z_base, width=2.9, depth=2.5, front_h=2.15, back_h=2.65):
    """
    Builds a rugged rustic 4-post canvas awning shelter:
    - 4 heavy square timber uprights
    - Slope rake beams and header crossbeams
    - Diagonal knee braces
    - Draped canvas tarpaulin (MAT_INDEX_TARP) with eave overhang flaps
    - Wooden hold-down battens
    - 4 diagonal guy ropes (MAT_INDEX_ROPE) anchored to wooden ground pegs
    - Hanging iron lantern under the center beam
    """
    hx = width * 0.5
    hy = depth * 0.5
    post_thick = 0.14

    # 1. 4 Corner Timber Uprights
    # Front-left, Front-right, Back-left, Back-right
    corners = [
        (-hx + post_thick * 0.5, -hy + post_thick * 0.5, front_h),
        ( hx - post_thick * 0.5, -hy + post_thick * 0.5, front_h),
        (-hx + post_thick * 0.5,  hy - post_thick * 0.5, back_h),
        ( hx - post_thick * 0.5,  hy - post_thick * 0.5, back_h),
    ]
    for px, py, ph in corners:
        create_beveled_box(
            bm, size=(post_thick, post_thick, ph),
            location=(cx + px, cy + py, z_base + ph * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    # 2. Header Beams connecting posts
    # Front header beam
    create_beveled_box(
        bm, size=(width + 0.15, 0.12, 0.12),
        location=(cx, cy - hy + post_thick * 0.5, z_base + front_h - 0.06),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
    )
    # Back ridge beam
    create_beveled_box(
        bm, size=(width + 0.15, 0.12, 0.12),
        location=(cx, cy + hy - post_thick * 0.5, z_base + back_h - 0.06),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
    )

    # Side rake beams (along slope from back to front)
    slope_drop = back_h - front_h
    rake_len = math.hypot(depth - post_thick, slope_drop)
    pitch_ang = math.atan2(slope_drop, depth - post_thick)
    mid_z = z_base + (front_h + back_h) * 0.5 - 0.06
    for s_sign in (-1.0, 1.0):
        rx = cx + s_sign * (hx - post_thick * 0.5)
        create_beveled_box(
            bm, size=(0.12, rake_len + 0.10, 0.12),
            location=(rx, cy, mid_z),
            rotation=(pitch_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )

    # 3 intermediate rafters bridging from front to back across the slope
    for rx_off in (-hx * 0.45, 0.0, hx * 0.45):
        create_beveled_box(
            bm, size=(0.09, rake_len + 0.12, 0.09),
            location=(cx + rx_off, cy, mid_z + 0.06),
            rotation=(pitch_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    # 3. Knee Braces stiffening the posts
    brace_len = 0.48
    brace_z = z_base + front_h - 0.28
    for s_sign in (-1.0, 1.0):
        bx = cx + s_sign * (hx - post_thick * 0.5 - 0.16)
        by = cy - hy + post_thick * 0.5
        create_beveled_box(
            bm, size=(brace_len, 0.08, 0.08),
            location=(bx, by, brace_z),
            rotation=(0.0, s_sign * 0.785, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )

    # 4. Draped Canvas Canopy (MAT_INDEX_TARP)
    canopy_w = width + 0.35
    canopy_l = rake_len + 0.35
    tarp_z = mid_z + 0.13
    create_beveled_box(
        bm, size=(canopy_w, canopy_l, 0.025),
        location=(cx, cy, tarp_z),
        rotation=(pitch_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.004
    )
    # Calculate exact front and back edge coordinates of the rotated canopy plane
    half_l_proj_y = (canopy_l * 0.5) * math.cos(pitch_ang)
    half_l_proj_z = (canopy_l * 0.5) * math.sin(pitch_ang)

    front_eave_y = cy - half_l_proj_y
    front_eave_z = tarp_z - half_l_proj_z

    back_eave_y = cy + half_l_proj_y
    back_eave_z = tarp_z + half_l_proj_z

    flap_h = 0.16
    # Drooping front eave flap (tucked flush into canopy bottom)
    create_beveled_box(
        bm, size=(canopy_w, 0.02, flap_h),
        location=(cx, front_eave_y, front_eave_z - flap_h * 0.5 + 0.01),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.003
    )
    # Drooping back eave flap (tucked flush into canopy bottom)
    create_beveled_box(
        bm, size=(canopy_w, 0.02, flap_h),
        location=(cx, back_eave_y, back_eave_z - flap_h * 0.5 + 0.01),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.003
    )
    # Drooping side eave flaps
    for s_sign in (-1.0, 1.0):
        side_edge_x = cx + s_sign * (canopy_w * 0.5 - 0.01)
        create_beveled_box(
            bm, size=(0.02, canopy_l, 0.12),
            location=(side_edge_x, cy, tarp_z - 0.05),
            rotation=(pitch_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )

    # 5. Wooden Hold-down Battens on top of tarp along rafters
    for rx_off in (-hx * 0.55, 0.0, hx * 0.55):
        create_beveled_box(
            bm, size=(0.07, canopy_l, 0.035),
            location=(cx + rx_off, cy, tarp_z + 0.025),
            rotation=(pitch_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
        )





def build_lean_to_awning(bm, cx, cy, z_base, width=2.5, depth=2.2, front_h=1.85, back_h=2.40):
    """
    Builds a simple wooden board lean-to shed/awning over sawn lumber:
    - 4 rustic timber posts (tall back, short front)
    - Timber slope rafters
    - Staggered overlapping rustic weatherboards (MAT_INDEX_WOOD)
    - Completely open on all sides
    """
    hx = width * 0.5
    hy = depth * 0.5
    post_thick = 0.12

    # 4 Posts
    for s_sign in (-1.0, 1.0):
        # Front post (short)
        create_beveled_box(
            bm, size=(post_thick, post_thick, front_h),
            location=(cx + s_sign * (hx - post_thick * 0.5), cy - hy + post_thick * 0.5, z_base + front_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
        # Back post (tall)
        create_beveled_box(
            bm, size=(post_thick, post_thick, back_h),
            location=(cx + s_sign * (hx - post_thick * 0.5), cy + hy - post_thick * 0.5, z_base + back_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )

    slope_drop = back_h - front_h
    rake_len = math.hypot(depth - post_thick, slope_drop)
    pitch_ang = math.atan2(slope_drop, depth - post_thick)
    mid_z = z_base + (front_h + back_h) * 0.5 - 0.05

    # 3 Timber Rake Rafters
    for s_off in (-hx + post_thick * 0.5, 0.0, hx - post_thick * 0.5):
        create_beveled_box(
            bm, size=(0.10, rake_len + 0.18, 0.10),
            location=(cx + s_off, cy, mid_z),
            rotation=(pitch_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    # Overlapping Rustic Weatherboards across the pitch
    num_planks = 6
    plank_w = (rake_len + 0.28) / num_planks
    for pi in range(num_planks):
        # Distribute along slope from front to back
        t = (pi + 0.5) / num_planks - 0.5
        py_off = t * depth
        pz_off = mid_z + 0.08 + t * slope_drop
        create_beveled_box(
            bm, size=(width + 0.32, plank_w + 0.05, 0.032),
            location=(cx, cy + py_off, pz_off),
            rotation=(pitch_ang + 0.04, 0.0, 0.0),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
        )


def _build_handcart(bm, cx, cy, z_base, rot_ang=0.45):
    """A rugged 2-wheeled wooden cargo handcart carrying burlap sacks."""
    from .furniture import build_clay_pot
    mat = Matrix.Translation((cx, cy, z_base)) @ Matrix.Rotation(rot_ang, 4, 'Z')

    # Bed dimensions
    bed_l = 1.30
    bed_w = 0.72
    bed_z = 0.32

    faces = []
    # 2 Big Spoked/Solid Wooden Wheels
    wheel_r = 0.34
    for s_sign in (-1.0, 1.0):
        faces += create_cylinder(
            bm, radius=wheel_r, height=0.06, segments=14,
            location=(0.0, s_sign * (bed_w * 0.5 + 0.05), wheel_r),
            rotation=(1.57, 0.0, 0.0),
            mat_index=MAT_INDEX_WOOD
        )
        faces += create_cylinder(
            bm, radius=0.07, height=0.09, segments=8,
            location=(0.0, s_sign * (bed_w * 0.5 + 0.05), wheel_r),
            rotation=(1.57, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
    # Iron Axle
    faces += create_cylinder(
        bm, radius=0.025, height=bed_w + 0.22, segments=8,
        location=(0.0, 0.0, wheel_r),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    # Wooden Chassis Spars & Handles (slanted down to ground)
    handle_len = 1.95
    tilt = 0.12
    for s_sign in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(handle_len, 0.06, 0.06),
            location=(0.20, s_sign * (bed_w * 0.5 - 0.05), bed_z),
            rotation=(0.0, tilt, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )
    # Plank Bed
    for si in range(4):
        bx = (si - 1.5) * 0.22 - 0.10
        faces += create_beveled_box(
            bm, size=(0.20, bed_w, 0.035),
            location=(bx, 0.0, bed_z + 0.05),
            rotation=(0.0, tilt, 0.0),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
        )
    # Side Rails
    for s_sign in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(bed_l * 0.8, 0.04, 0.18),
            location=(-0.10, s_sign * (bed_w * 0.5 - 0.02), bed_z + 0.14),
            rotation=(0.0, tilt, 0.0),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
        )
    transform_faces(faces, mat)

    # Glazed pots riding in the cart bed
    build_clay_pot(bm, x=cx - 0.12, y=cy, z_ground=z_base + bed_z + 0.06,
                   ang=rot_ang + 0.2, radius=0.20, height=0.46, pot_type='JAR')
    build_clay_pot(bm, x=cx + 0.15, y=cy - 0.08, z_ground=z_base + bed_z + 0.06,
                   ang=rot_ang - 0.3, radius=0.17, height=0.40, pot_type='URN')


def build_supply_depot_yard(bm, min_x, max_x, min_y, max_y, z_floor, seed=42):
    """
    Builds an authentic medieval/fantasy temporary supply stockpile:
    - Perimeter ground sleeper timber boundary demarcating the depot plot.
    - Multiple pallet skids bearing organized cargo.
    - Crate clusters (banded freight crates, small crates, stacked).
    - Barrel racks (upright casks, chocked horizontal barrels).
    - Sawn lumber piles with cross-batten spacers.
    - Groups of burlap sacks.
    - Awnings covering parts of it:
      * Canvas Tarp Awning (MAT_INDEX_TARP) with guy ropes and lantern over Pallet 0.
      * Rustic Board Lean-To Awning (MAT_INDEX_WOOD) over Pallet 3.
    - Open-air areas: Pallet 1 (crates), Pallet 2 (barrels), timber log stack, handcart.
    """
    from .furniture import build_barrel, build_crate, build_clay_pot
    import random
    rng = random.Random(seed + 808)

    span_x = max_x - min_x
    span_y = max_y - min_y
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5

    # 1. Pallet Skids (heavy wooden cargo bases)
    pallet_locs = [
        (min_x + span_x * 0.28, min_y + span_y * 0.32),  # Pallet 0: Sheltered by Canvas Tarp Awning
        (min_x + span_x * 0.74, min_y + span_y * 0.32),  # Pallet 1: Open-air Crates
        (min_x + span_x * 0.28, min_y + span_y * 0.72),  # Pallet 2: Open-air Barrels
        (min_x + span_x * 0.72, min_y + span_y * 0.70),  # Pallet 3: Sheltered by Lean-to Awning
    ]
    for px, py in pallet_locs:
        # 3 bearer skids
        for off in (-0.55, 0.0, 0.55):
            create_beveled_box(
                bm, size=(1.40, 0.12, 0.12),
                location=(px, py + off, z_floor + 0.06),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
        # 5 deck slats
        for si in range(5):
            sx = (si - 2) * 0.28
            create_beveled_box(
                bm, size=(0.18, 1.35, 0.04),
                location=(px + sx, py, z_floor + 0.14),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
            )

    # 3. Crate & Clay Pot Clusters on Pallet 0 (Sheltered under Tarp) & Pallet 1 (Open Air)
    # Cluster 1 (Left front - Under Canvas Awning)
    p0x, p0y = pallet_locs[0]
    z_p0 = z_floor + 0.16
    # Base layer crates
    build_crate(bm, x=p0x - 0.32, y=p0y - 0.26, z_ground=z_p0, ang=0.0, size=0.68, depth=0.50, height=0.52, brace_style='DIAGONAL')
    build_crate(bm, x=p0x + 0.34, y=p0y - 0.26, z_ground=z_p0, ang=0.0, size=0.50, height=0.52, brace_style='CROSS')
    build_crate(bm, x=p0x - 0.28, y=p0y + 0.28, z_ground=z_p0, ang=0.0, size=0.52, height=0.52, brace_style='NONE')
    # 2nd tier crate: stacked squarely on top of the left base crate (height 0.52) with zero overlap
    build_crate(bm, x=p0x - 0.32, y=p0y - 0.26, z_ground=z_p0 + 0.52, ang=0.0, size=0.48, depth=0.44, height=0.46, brace_style='DIAGONAL')
    # Clay pot on pallet 0 (tucked on back-right corner of deck with clean crate clearance)
    build_clay_pot(bm, x=p0x + 0.30, y=p0y + 0.26, z_ground=z_p0, ang=0.3, radius=0.18, height=0.46, pot_type='JAR')

    # Cluster 2 (Right front - Open to sky)
    p1x, p1y = pallet_locs[1]
    z_p1 = z_floor + 0.16
    # Base layer crates
    build_crate(bm, x=p1x - 0.32, y=p1y - 0.24, z_ground=z_p1, ang=0.0, size=0.54, height=0.52, brace_style='CROSS')
    build_crate(bm, x=p1x + 0.32, y=p1y - 0.24, z_ground=z_p1, ang=0.0, size=0.66, depth=0.48, height=0.52, brace_style='DIAGONAL')
    build_crate(bm, x=p1x - 0.28, y=p1y + 0.30, z_ground=z_p1, ang=0.0, size=0.50, height=0.52, brace_style='NONE')
    # 2nd tier crate: stacked squarely on top of the right base crate (height 0.52)
    build_crate(bm, x=p1x + 0.32, y=p1y - 0.24, z_ground=z_p1 + 0.52, ang=0.0, size=0.46, depth=0.44, height=0.46, brace_style='CROSS')
    # Clay pot on pallet 1
    build_clay_pot(bm, x=p1x + 0.28, y=p1y + 0.26, z_ground=z_p1, ang=-0.4, radius=0.19, height=0.48, pot_type='URN')

    # 4. Barrel Racks on Pallet 2 (Left rear - Open Air)
    p2x, p2y = pallet_locs[2]
    # Standing barrels
    build_barrel(bm, x=p2x - 0.38, y=p2y - 0.32, z_ground=z_floor + 0.16, ang=0.0, radius=0.32, height=0.72)
    build_barrel(bm, x=p2x + 0.28, y=p2y - 0.35, z_ground=z_floor + 0.16, ang=0.5, radius=0.30, height=0.68)
    build_barrel(bm, x=p2x - 0.35, y=p2y + 0.28, z_ground=z_floor + 0.16, ang=1.2, radius=0.31, height=0.70)
    # Lying barrels with chocks
    build_barrel(bm, x=p2x + 0.30, y=p2y + 0.28, z_ground=z_floor + 0.16, ang=1.57, radius=0.28, height=0.74, lying=True)

    # 5. Sawn Lumber Piles on Pallet 3 (Right rear - Under Lean-To)
    p3x, p3y = pallet_locs[3]
    plank_l = 1.95
    plank_w = 0.95
    for layer in range(5):
        lz = z_floor + 0.16 + layer * 0.11
        create_beveled_box(
            bm, size=(plank_l, plank_w, 0.08),
            location=(p3x, p3y, lz + 0.04),
            rotation=(0.0, 0.0, 0.04),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
        if layer < 4:
            for s_off in (-0.65, 0.0, 0.65):
                create_box(
                    bm, size=(0.05, plank_w + 0.04, 0.03),
                    location=(p3x + s_off, p3y, lz + 0.095),
                    mat_index=MAT_INDEX_TIMBER
                )

    # 6. AWNINGS COVERING PARTS OF THE STOCKPILE
    # Awning 1: Rustic Canvas Tarp Canopy covering Pallet 0 (Crates & Sacks)
    build_tarp_awning(
        bm, cx=p0x, cy=p0y, z_base=z_floor,
        width=3.0, depth=2.5, front_h=2.15, back_h=2.65
    )

    # Awning 2: Rustic Board Lean-To covering Pallet 3 (Sawn Lumber)
    build_lean_to_awning(
        bm, cx=p3x, cy=p3y, z_base=z_floor,
        width=2.5, depth=2.3, front_h=1.85, back_h=2.40
    )

    # 7. Stack of Round Timber Logs in Open Yard (between Pallet 2 and 3)
    log_cx = cx
    log_cy = cy + span_y * 0.24
    log_len = 2.4
    log_r = 0.13
    # Layer 1: 3 logs
    for li, l_off in enumerate((-0.28, 0.0, 0.28)):
        create_horizontal_cylinder(
            bm, radius_y=log_r, radius_z=log_r, length=log_len, segments=12,
            location=(log_cx + l_off, log_cy, z_floor + log_r),
            rotation=(0.0, 0.0, 1.5708),
            mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
        )
    # End timber chocks
    for cs in (-0.42, 0.42):
        create_beveled_box(
            bm, size=(0.10, 0.12, 0.10),
            location=(log_cx + cs, log_cy, z_floor + 0.05),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Layer 2: 2 logs
    for li, l_off in enumerate((-0.14, 0.14)):
        create_horizontal_cylinder(
            bm, radius_y=log_r * 0.95, radius_z=log_r * 0.95, length=log_len - 0.10, segments=12,
            location=(log_cx + l_off, log_cy, z_floor + log_r * 2.5),
            rotation=(0.0, 0.0, 1.5708),
            mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
        )
    # Layer 3: 1 apex log
    create_horizontal_cylinder(
        bm, radius_y=log_r * 0.90, radius_z=log_r * 0.90, length=log_len - 0.20, segments=12,
        location=(log_cx, log_cy, z_floor + log_r * 3.9),
        rotation=(0.0, 0.0, 1.5708),
        mat_index=MAT_INDEX_LOG, mat_index_cap=MAT_INDEX_LOG_END
    )


    # 9. Terracotta Clay Pots Grouped in Clusters (collision-checked, clear of all posts/crates)
    pot_clusters = [
        # Cluster A: Open ground to the left (between Pallet 0 and Pallet 2)
        (-4.60, 0.40, 0.4, 0.22, 0.50, 'JAR'),
        (-4.60, 0.90, -0.8, 0.19, 0.56, 'JUG'),
        # Cluster B: Open ground to the right (between Pallet 1 and Pallet 3)
        ( 4.40, 0.10, 0.6, 0.22, 0.48, 'URN'),
        ( 4.40, 0.60, -0.2, 0.19, 0.54, 'JAR'),
        # Cluster C: Open yard entrance walkway (clear of posts and pallets)
        ( 0.60, -2.80, 0.5, 0.22, 0.50, 'JAR'),
        ( 0.95, -2.55, -0.7, 0.18, 0.56, 'JUG'),
    ]
    for px, py, pang, pr, ph, ptype in pot_clusters:
        build_clay_pot(bm, x=px, y=py, z_ground=z_floor, ang=pang, radius=pr, height=ph, pot_type=ptype)

