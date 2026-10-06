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


def build_tarp_awning(bm, cx, cy, z_base, width=2.9, depth=2.5, front_h=2.15, back_h=2.65,
                      yaw=0.0):
    """
    Builds a rugged rustic 4-post canvas awning shelter:
    - 4 heavy square timber uprights
    - Slope rake beams and header crossbeams
    - Diagonal knee braces
    - Draped canvas tarpaulin (MAT_INDEX_TARP) with eave overhang flaps
    - Wooden hold-down battens
    - 4 diagonal guy ropes (MAT_INDEX_ROPE) anchored to wooden ground pegs
    - Hanging iron lantern under the center beam

    The roof slopes down towards local -Y (the open front). ``yaw`` rotates
    the whole shelter around Z so the open front can face any direction
    (e.g. a courtyard); it defaults to 0 (front faces -Y, unchanged output).
    """
    hx = width * 0.5
    hy = depth * 0.5
    post_thick = 0.14
    _cyaw, _syaw = math.cos(yaw), math.sin(yaw)

    def _P(ox, oy, z):
        return (cx + ox * _cyaw - oy * _syaw,
                cy + ox * _syaw + oy * _cyaw, z)

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
            location=_P(px, py, z_base + ph * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    # 2. Header Beams connecting posts
    # Front header beam
    create_beveled_box(
        bm, size=(width + 0.15, 0.12, 0.12),
        location=_P(0.0, -hy + post_thick * 0.5, z_base + front_h - 0.06),
        rotation=(0.0, 0.0, yaw),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
    )
    # Back ridge beam
    create_beveled_box(
        bm, size=(width + 0.15, 0.12, 0.12),
        location=_P(0.0, hy - post_thick * 0.5, z_base + back_h - 0.06),
        rotation=(0.0, 0.0, yaw),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
    )

    # Side rake beams (along slope from back to front)
    slope_drop = back_h - front_h
    rake_len = math.hypot(depth - post_thick, slope_drop)
    pitch_ang = math.atan2(slope_drop, depth - post_thick)
    mid_z = z_base + (front_h + back_h) * 0.5 - 0.06
    for s_sign in (-1.0, 1.0):
        rx = s_sign * (hx - post_thick * 0.5)
        create_beveled_box(
            bm, size=(0.12, rake_len + 0.10, 0.12),
            location=_P(rx, 0.0, mid_z),
            rotation=(pitch_ang, 0.0, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )

    # 3 intermediate rafters bridging from front to back across the slope
    for rx_off in (-hx * 0.45, 0.0, hx * 0.45):
        create_beveled_box(
            bm, size=(0.09, rake_len + 0.12, 0.09),
            location=_P(rx_off, 0.0, mid_z + 0.06),
            rotation=(pitch_ang, 0.0, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    # 3. Knee Braces stiffening the posts
    brace_len = 0.48
    brace_z = z_base + front_h - 0.28
    for s_sign in (-1.0, 1.0):
        bx = s_sign * (hx - post_thick * 0.5 - 0.16)
        by = -hy + post_thick * 0.5
        create_beveled_box(
            bm, size=(brace_len, 0.08, 0.08),
            location=_P(bx, by, brace_z),
            rotation=(0.0, s_sign * 0.785, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )

    # 4. Draped Canvas Canopy (MAT_INDEX_TARP)
    canopy_w = width + 0.35
    canopy_l = rake_len + 0.35
    tarp_z = mid_z + 0.13
    create_beveled_box(
        bm, size=(canopy_w, canopy_l, 0.025),
        location=_P(0.0, 0.0, tarp_z),
        rotation=(pitch_ang, 0.0, yaw),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.004
    )
    # Calculate exact front and back edge coordinates of the rotated canopy plane
    half_l_proj_y = (canopy_l * 0.5) * math.cos(pitch_ang)
    half_l_proj_z = (canopy_l * 0.5) * math.sin(pitch_ang)

    front_eave_y = -half_l_proj_y
    front_eave_z = tarp_z - half_l_proj_z

    back_eave_y = half_l_proj_y
    back_eave_z = tarp_z + half_l_proj_z

    flap_h = 0.16
    # Drooping front eave flap (tucked flush into canopy bottom)
    create_beveled_box(
        bm, size=(canopy_w, 0.02, flap_h),
        location=_P(0.0, front_eave_y, front_eave_z - flap_h * 0.5 + 0.01),
        rotation=(0.0, 0.0, yaw),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.003
    )
    # Drooping back eave flap (tucked flush into canopy bottom)
    create_beveled_box(
        bm, size=(canopy_w, 0.02, flap_h),
        location=_P(0.0, back_eave_y, back_eave_z - flap_h * 0.5 + 0.01),
        rotation=(0.0, 0.0, yaw),
        mat_index=MAT_INDEX_TARP, bevel_amount=0.003
    )
    # Drooping side eave flaps
    for s_sign in (-1.0, 1.0):
        side_edge_x = s_sign * (canopy_w * 0.5 - 0.01)
        create_beveled_box(
            bm, size=(0.02, canopy_l, 0.12),
            location=_P(side_edge_x, 0.0, tarp_z - 0.05),
            rotation=(pitch_ang, 0.0, yaw),
            mat_index=MAT_INDEX_TARP, bevel_amount=0.003
        )

    # 5. Wooden Hold-down Battens on top of tarp along rafters
    for rx_off in (-hx * 0.55, 0.0, hx * 0.55):
        create_beveled_box(
            bm, size=(0.07, canopy_l, 0.035),
            location=_P(rx_off, 0.0, tarp_z + 0.025),
            rotation=(pitch_ang, 0.0, yaw),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
        )





def build_lean_to_awning(bm, cx, cy, z_base, width=2.5, depth=2.2, front_h=1.85, back_h=2.40,
                         yaw=0.0):
    """
    Builds a simple wooden board lean-to shed/awning over sawn lumber:
    - 4 rustic timber posts (tall back, short front)
    - Timber slope rafters
    - Staggered overlapping rustic weatherboards (MAT_INDEX_WOOD)
    - Completely open on all sides

    The roof slopes down towards local -Y (the open front). ``yaw``
    rotates the whole shelter around Z so the open front can face any
    direction; it defaults to 0 (front faces -Y, unchanged output).
    """
    hx = width * 0.5
    hy = depth * 0.5
    post_thick = 0.12
    _cyaw, _syaw = math.cos(yaw), math.sin(yaw)

    def _P(ox, oy, z):
        return (cx + ox * _cyaw - oy * _syaw,
                cy + ox * _syaw + oy * _cyaw, z)

    # 4 Posts
    for s_sign in (-1.0, 1.0):
        # Front post (short)
        create_beveled_box(
            bm, size=(post_thick, post_thick, front_h),
            location=_P(s_sign * (hx - post_thick * 0.5), -hy + post_thick * 0.5, z_base + front_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
        # Back post (tall)
        create_beveled_box(
            bm, size=(post_thick, post_thick, back_h),
            location=_P(s_sign * (hx - post_thick * 0.5), hy - post_thick * 0.5, z_base + back_h * 0.5),
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
            location=_P(s_off, 0.0, mid_z),
            rotation=(pitch_ang, 0.0, yaw),
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
            location=_P(0.0, py_off, pz_off),
            rotation=(pitch_ang + 0.04, 0.0, yaw),
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


def build_supply_depot_yard(bm, min_x, max_x, min_y, max_y, z_floor, seed=42,
                             awning_scale=1.0, with_logs=True, with_pots=True,
                             with_awnings=True, keepouts=None):
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

    ``awning_scale`` multiplies the two awning footprints (posts, beams,
    canvas) so the main yard can shelter under larger roofs while tight
    side yards keep fitting ones. Heights are unchanged. ``with_logs`` /
    ``with_pots`` drop the log rank / clay-pot garnish for cramped side
    yards where they would collide with the awning posts (the main yard
    always keeps them). ``with_awnings`` drops both roofs entirely so a
    dedicated shelter composer can raise exactly the roofs it wants.
    ``keepouts`` optionally collects ground footprints (pallets, log rank,
    pots) for the interior furnishing tracker so indoor piles never land
    on yard stock.
    Returns the ((pallet0_x, pallet0_y), (pallet3_x, pallet3_y)) anchor
    spots for shelter placement.
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
    if keepouts is not None:
        for px, py in pallet_locs:
            keepouts.append((px - 0.75, px + 0.75, py - 0.75, py + 0.75))
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

    # 6. AWNINGS COVERING PARTS OF THE STOCKPILE (skipped when a dedicated
    # shelter composer raises the roofs instead: exactly the roofs it wants).
    if with_awnings:
        # Awning 1: Rustic Canvas Tarp Canopy covering Pallet 0 (Crates & Sacks)
        build_tarp_awning(
            bm, cx=p0x, cy=p0y, z_base=z_floor,
            width=3.0 * awning_scale, depth=2.5 * awning_scale, front_h=2.15, back_h=2.65
        )

        # Awning 2: Rustic Board Lean-To covering Pallet 3 (Sawn Lumber)
        build_lean_to_awning(
            bm, cx=p3x, cy=p3y, z_base=z_floor,
            width=2.5 * awning_scale, depth=2.3 * awning_scale, front_h=1.85, back_h=2.40
        )

    # 7. Stack of Round Timber Logs in Open Yard (between Pallet 2 and 3).
    # Skipped in cramped side yards: the rank would collide with the awning
    # posts there (the main yard always keeps it).
    log_cx = cx
    log_cy = cy + span_y * 0.24
    log_len = 2.4
    log_r = 0.13
    if keepouts is not None and with_logs:
        keepouts.append((log_cx - 0.60, log_cx + 0.60,
                         log_cy - log_len * 0.5 - 0.10, log_cy + log_len * 0.5 + 0.10))
    if with_logs:
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


    # 9. Terracotta Clay Pots Grouped in Clusters (collision-checked, clear of all posts/crates).
    # Positions are span-relative so main and wing yards each land their own
    # pots in open ground; skipped entirely in cramped side yards.
    if with_pots:
        pot_clusters = [
            # Cluster A: open ground to the left (between Pallet 0 and Pallet 2)
            (min_x + span_x * 0.06, cy + span_y * 0.10, 0.4, 0.22, 0.50, 'JAR'),
            (min_x + span_x * 0.06, cy + span_y * 0.16, -0.8, 0.19, 0.56, 'JUG'),
            # Cluster B: open ground to the right (between Pallet 1 and Pallet 3)
            (max_x - span_x * 0.06, cy + span_y * 0.01, 0.6, 0.22, 0.48, 'URN'),
            (max_x - span_x * 0.06, cy + span_y * 0.09, -0.2, 0.19, 0.54, 'JAR'),
            # Cluster C: open yard entrance walkway (clear of posts and pallets)
            (cx + span_x * 0.05, min_y + span_y * 0.10, 0.5, 0.22, 0.50, 'JAR'),
            (cx + span_x * 0.09, min_y + span_y * 0.16, -0.7, 0.18, 0.56, 'JUG'),
        ]
        for px, py, pang, pr, ph, ptype in pot_clusters:
            if keepouts is not None:
                keepouts.append((px - 0.30, px + 0.30, py - 0.30, py + 0.30))
            build_clay_pot(bm, x=px, y=py, z_ground=z_floor, ang=pang, radius=pr, height=ph, pot_type=ptype)

    return ((p0x, p0y), (p3x, p3y))


def _courtyard_corner(main_rect, wing_rect):
    """Courtyard corner of an L footprint: the union-bbox corner farthest
    from both arm centres (the empty elbow of the L)."""
    (ax0, ax1, ay0, ay1) = main_rect
    (bx0, bx1, by0, by1) = wing_rect
    ux0, ux1 = min(ax0, bx0), max(ax1, bx1)
    uy0, uy1 = min(ay0, by0), max(ay1, by1)
    mcx, mcy = (ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5
    wcx, wcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
    best, bd = (ux0, uy0), -1.0
    for c in ((ux0, uy0), (ux0, uy1), (ux1, uy0), (ux1, uy1)):
        d = min(math.hypot(c[0] - mcx, c[1] - mcy),
                math.hypot(c[0] - wcx, c[1] - wcy))
        if d > bd:
            best, bd = c, d
    return best


def _face_yaw(sx, sy, tx, ty):
    """Yaw turning an awning's open front (local -Y) towards (tx, ty).

    Snapped to quarter turns so shelters stay axis-aligned with the yard
    (a free angle would twist long roofs diagonally like a butterfly).
    """
    dx, dy = tx - sx, ty - sy
    if abs(dy) >= abs(dx):
        return 0.0 if dy < 0.0 else math.pi
    return -math.pi * 0.5 if dx < 0.0 else math.pi * 0.5


def build_stockpile_shelters(bm, main_rect, wing_rect, main_anchors, wing_anchors,
                             z_base, seed=42, keepouts=None):
    """Raise exactly two courtyard-facing shelter roofs over a stockpile.

    The two shelters TOGETHER trace an L-shaped footprint matching the
    building's outline: one canvas tarp over the main yard (opens north),
    one board lean-to over the wing (opens west). Together they "simulate"
    the L-shaped building footprint with just awnings.

    ``wing_rect`` / ``wing_anchors`` may be None (rectangle yards get
    just the main shelter). Shelter sizes are real parametric dimensions
    (proper posts/beams), never stretched. ``keepouts`` optionally collects
    the shelter post footprints for the interior furnishing tracker.
    """
    def _record_posts(cx, cy, yaw, hx, hy, inset):
        if keepouts is None:
            return
        cyaw, syaw = math.cos(yaw), math.sin(yaw)
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                ox, oy = sx * (hx - inset), sy * (hy - inset)
                px = cx + ox * cyaw - oy * syaw
                py = cy + ox * syaw + oy * cyaw
                keepouts.append((px - 0.15, px + 0.15, py - 0.15, py + 0.15))

    ccx, ccy = None, None
    if wing_rect is not None:
        ccx, ccy = _courtyard_corner(main_rect, wing_rect)

    # 1. Main yard: canvas tarp covering the main yard footprint, rotated 180° (opens north)
    # Span the full main yard width/depth
    _m_span_x = main_rect[1] - main_rect[0]
    _m_span_y = main_rect[3] - main_rect[2]
    _tarp_cx = (main_rect[0] + main_rect[1]) * 0.5
    _tarp_cy = (main_rect[2] + main_rect[3]) * 0.5
    yaw_tarp = math.pi  # 180° = opens north
    build_tarp_awning(
        bm, cx=_tarp_cx, cy=_tarp_cy, z_base=z_base,
        width=_m_span_x * 0.9, depth=_m_span_y * 0.85, front_h=2.15, back_h=2.65,
        yaw=yaw_tarp,
    )
    _record_posts(_tarp_cx, _tarp_cy, yaw_tarp, _m_span_x * 0.45, _m_span_y * 0.425, 0.07)

    # 2. Wing: lean-to covering the wing footprint, rotated 90° CCW (opens west)
    if wing_rect is not None:
        _w_span_x = wing_rect[1] - wing_rect[0]
        _w_span_y = wing_rect[3] - wing_rect[2]
        _lean_cx = (wing_rect[0] + wing_rect[1]) * 0.5
        _lean_cy = (wing_rect[2] + wing_rect[3]) * 0.5
        yaw_lean = math.pi * 0.5  # +90° = opens east (180° from west)
        build_lean_to_awning(
            bm, cx=_lean_cx, cy=_lean_cy, z_base=z_base,
            width=_w_span_x * 0.9, depth=_w_span_y * 0.85, front_h=1.85, back_h=2.40,
            yaw=yaw_lean,
        )
        _record_posts(_lean_cx, _lean_cy, yaw_lean, _w_span_x * 0.45, _w_span_y * 0.425, 0.06)

