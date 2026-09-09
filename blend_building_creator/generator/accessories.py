"""
Purpose-built architectural accessories and specialized fixtures for Stylized Fantasy Buildings.
Empowers buildings to visibly express their function according to their archetype:
- Blacksmith: Outdoor forge lean-to canopy, stone furnace, iron chimney, quenching tub, and anvil.
- Windmill: Front rotating 4-blade lattice timber windmill rotor with canvas sails.
- Watchtower: Machicolated defensive timber hoarding, cantilever corbels, and lookout parapet.
- Tavern: Covered entrance veranda porch and hanging wrought-iron tavern trade sign.
- Fisherman: Stilted pier timber pilings foundation and outdoor fish drying net frame.
- Bakery: Protruding outdoor curved brick bread oven with chimney.
- Warehouse: Stacked wooden cargo crates and iron-banded storage barrels under hoist beam.
"""

import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD
)

def build_blacksmith_forge(bm, x_min, x_max, y_min, y_max, z_ground, wall_thickness, seed=42):
    """
    Builds a grounded, architecturally authentic blacksmith workshop lean-to shed
    on the right facade (+X):
    - Grounded stone footing pedestals and heavy timber support columns.
    - Solid timber workshop deck floor.
    - Sloping rafters and shingle awning roof cleanly anchored to the main building wall.
    - Open-air sheltered craft workshop without floating props.
    """
    wall_x = x_max
    canopy_w = 2.6
    canopy_d = (y_max - y_min) * 0.75
    canopy_h = 2.45
    canopy_cy = (y_min + y_max) * 0.5
    outer_x = wall_x + canopy_w
    
    deck_thick = 0.18
    # 1. Solid Grounded Workshop Deck Floor
    create_beveled_box(
        bm, size=(canopy_w + 0.15, canopy_d + 0.20, deck_thick),
        location=(wall_x + canopy_w * 0.5, canopy_cy, z_ground + deck_thick * 0.5),
        mat_index=MAT_INDEX_WOOD if 'MAT_INDEX_WOOD' in globals() else MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    
    # 2. Heavy Timber Pillars on Grounded Stone Footing Plinths
    col_w = 0.18
    p1_y = canopy_cy - canopy_d * 0.44
    p2_y = canopy_cy + canopy_d * 0.44
    
    for py in (p1_y, p2_y):
        # Grounded stone plinth
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.24),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.12),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
        # Vertical timber pillar
        pillar_h = canopy_h - 0.24
        create_beveled_box(
            bm, size=(col_w, col_w, pillar_h),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.24 + pillar_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        # Angled timber knee brace up to header beam
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.70),
            location=(outer_x - col_w * 0.5, py + (0.22 if py < canopy_cy else -0.22), z_ground + canopy_h - 0.25),
            rotation=(0.78 if py < canopy_cy else -0.78, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        # Wall-tie knee brace back to wall
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.70),
            location=(outer_x - col_w * 0.5 - 0.28, py, z_ground + canopy_h - 0.25),
            rotation=(0.0, -0.78, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        
    # 3. Outer Horizontal Header Beam connecting pillars
    create_beveled_box(
        bm, size=(col_w, canopy_d + 0.30, 0.18),
        location=(outer_x - col_w * 0.5, canopy_cy, z_ground + canopy_h),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    
    # 4. Sloping Rafters & Roof Deck
    roof_pitch = 0.32
    roof_z_wall = z_ground + canopy_h + canopy_w * roof_pitch
    roof_z_outer = z_ground + canopy_h
    roof_mid_x = (wall_x + outer_x) * 0.5
    roof_mid_z = (roof_z_wall + roof_z_outer) * 0.5 + 0.08
    rafter_l = math.sqrt(canopy_w * canopy_w + (roof_z_wall - roof_z_outer) ** 2) + 0.35
    roof_ang = math.atan2(roof_z_wall - roof_z_outer, canopy_w)
    
    # Sloping timber decking slab
    create_beveled_box(
        bm, size=(rafter_l, canopy_d + 0.40, 0.09),
        location=(roof_mid_x, canopy_cy, roof_mid_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_WOOD if 'MAT_INDEX_WOOD' in globals() else MAT_INDEX_TIMBER,
        bevel_amount=0.010
    )
    # Shingle layer
    create_beveled_box(
        bm, size=(rafter_l + 0.05, canopy_d + 0.46, 0.05),
        location=(roof_mid_x, canopy_cy, roof_mid_z + 0.06),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_SHINGLES,
        bevel_amount=0.008
    )


def build_windmill_sails(bm, cx, front_y, hub_z, radius=3.2, rotation_deg=22.5):
    """
    Builds a large 4-blade rotating lattice timber windmill rotor:
    - Central protruding heavy timber axle hub.
    - 4 lattice timber spars with cross-ribs.
    - Stretched canvas cloth sails.
    """
    # Central axle hub box protruding from front facade (-Y)
    hub_y = front_y - 0.35
    create_cylinder(
        bm, radius=0.35, height=0.55, segments=12,
        location=(cx, hub_y, hub_z),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )
    # Center iron cap
    create_cone(
        bm, radius1=0.22, radius2=0.04, height=0.20, segments=8,
        location=(cx, hub_y - 0.32, hub_z),
        rotation=(-1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )

    # 4 Blades arranged perpendicularly
    blade_y = hub_y - 0.15
    rad_base = math.radians(rotation_deg)
    
    for i in range(4):
        blade_angle = rad_base + i * (math.pi * 0.5)
        dir_x = math.cos(blade_angle)
        dir_z = math.sin(blade_angle)
        norm_x = -dir_z
        norm_z = dir_x
        
        mid_span = radius * 0.5
        spar_cx = cx + dir_x * mid_span
        spar_cz = hub_z + dir_z * mid_span
        
        # Heavy main timber spar
        create_beveled_box(
            bm, size=(radius, 0.09, 0.11),
            location=(spar_cx, blade_y, spar_cz),
            rotation=(0.0, -blade_angle, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        
        # Cross ribs (5 per blade)
        num_ribs = 5
        rib_len = 0.85
        sail_w = 0.70
        
        for r in range(1, num_ribs + 1):
            t_r = 0.25 + (r / float(num_ribs)) * 0.72
            rib_dist = radius * t_r
            rib_x = cx + dir_x * rib_dist + norm_x * (rib_len * 0.5)
            rib_z = hub_z + dir_z * rib_dist + norm_z * (rib_len * 0.5)
            create_box(
                bm, size=(0.04, 0.04, rib_len),
                location=(rib_x, blade_y - 0.02, rib_z),
                rotation=(0.0, -blade_angle + 1.57, 0.0),
                mat_index=MAT_INDEX_TIMBER
            )
            
        # Stretched Canvas Sail Cloth
        sail_len = radius * 0.70
        sail_cx = cx + dir_x * (radius * 0.62) + norm_x * (sail_w * 0.5)
        sail_cz = hub_z + dir_z * (radius * 0.62) + norm_z * (sail_w * 0.5)
        create_beveled_box(
            bm, size=(sail_len, 0.015, sail_w),
            location=(sail_cx, blade_y - 0.04, sail_cz),
            rotation=(0.0, -blade_angle, 0.08),
            mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.002
        )


def build_watchtower_lookout(bm, x_min, x_max, y_min, y_max, z_platform):
    """
    Builds an overhanging machicolated timber hoarding / defensive lookout gallery:
    - Cantilevered heavy timber corbels projecting outward on all 4 sides.
    - Perimeter timber walkway gallery with crenellated timber battlements and arrow slits.
    """
    overhang = 0.45
    ox_min = x_min - overhang
    ox_max = x_max + overhang
    oy_min = y_min - overhang
    oy_max = y_max + overhang
    
    total_w = ox_max - ox_min
    total_d = oy_max - oy_min
    cx = (ox_min + ox_max) * 0.5
    cy = (oy_min + oy_max) * 0.5
    
    # 1. Heavy Angled Timber Corbel Brackets supporting the overhang
    num_corbels_x = max(2, int(round((x_max - x_min) / 1.5)))
    step_x = (x_max - x_min) / float(num_corbels_x)
    for i in range(num_corbels_x + 1):
        bx = x_min + i * step_x
        # Front corbels (-Y)
        create_beveled_box(
            bm, size=(0.14, 0.45, 0.14),
            location=(bx, y_min - overhang * 0.5, z_platform - 0.10),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )
        # Angled brace under corbel
        create_beveled_box(
            bm, size=(0.10, 0.55, 0.10),
            location=(bx, y_min - overhang * 0.30, z_platform - 0.38),
            rotation=(0.78, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        # Back corbels (+Y)
        create_beveled_box(
            bm, size=(0.14, 0.45, 0.14),
            location=(bx, y_max + overhang * 0.5, z_platform - 0.10),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )
        create_beveled_box(
            bm, size=(0.10, 0.55, 0.10),
            location=(bx, y_max + overhang * 0.30, z_platform - 0.38),
            rotation=(-0.78, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    # 2. Overhanging Platform Deck
    create_beveled_box(
        bm, size=(total_w, total_d, 0.14),
        location=(cx, cy, z_platform),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
    )
    
    # 3. Defensive Hoarding Walls with Arrow-Slit Embrasures
    parapet_h = 1.35
    pz = z_platform + parapet_h * 0.5
    
    def build_parapet_wall_with_slits(length, is_x_axis, center_pos):
        # Build base wall (0.45m high)
        base_h = 0.45
        size_base = (length, 0.12, base_h) if is_x_axis else (0.12, length, base_h)
        create_beveled_box(
            bm, size=size_base,
            location=(center_pos[0], center_pos[1], z_platform + base_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
        # Add pillars with arrow slits (openings) between them
        num_posts = max(3, int(length / 1.1))
        post_step = length / float(num_posts)
        post_w = 0.45
        upper_h = parapet_h - base_h
        for p in range(num_posts + 1):
            pos_offset = -length * 0.5 + p * post_step
            if is_x_axis:
                px = center_pos[0] + pos_offset
                py = center_pos[1]
                size_post = (min(post_w, post_step * 0.65), 0.12, upper_h)
            else:
                px = center_pos[0]
                py = center_pos[1] + pos_offset
                size_post = (0.12, min(post_w, post_step * 0.65), upper_h)
            create_beveled_box(
                bm, size=size_post,
                location=(px, py, z_platform + base_h + upper_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
            )
        # Heavy timber cap rail along top
        cap_h = 0.08
        size_cap = (length + 0.06, 0.16, cap_h) if is_x_axis else (0.16, length + 0.06, cap_h)
        create_beveled_box(
            bm, size=size_cap,
            location=(center_pos[0], center_pos[1], z_platform + parapet_h + cap_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    # Front & Back parapets
    build_parapet_wall_with_slits(total_w, True, (cx, oy_min + 0.06))
    build_parapet_wall_with_slits(total_w, True, (cx, oy_max - 0.06))
    # Left & Right parapets
    build_parapet_wall_with_slits(total_d - 0.24, False, (ox_min + 0.06, cy))
    build_parapet_wall_with_slits(total_d - 0.24, False, (ox_max - 0.06, cy))



def build_tavern_porch_and_sign(bm, x_min, x_max, front_y, z_ground, door_x=None, seed=42):
    """
    Builds a covered entrance veranda porch and hanging wrought-iron tavern sign:
    - Raised wooden deck with stairs.
    - Timber turned posts supporting a shingled awning roof.
    - Swinging wooden signboard on an ornate scrollwork iron wall bracket.
    """
    if door_x is None:
        door_x = (x_min + x_max) * 0.5
        
    porch_w = 2.8
    porch_d = 1.5
    porch_h = 2.4
    px_min = door_x - porch_w * 0.5
    px_max = door_x + porch_w * 0.5
    py_front = front_y - porch_d
    
    # 1. Raised Timber Deck
    deck_h = 0.20
    create_beveled_box(
        bm, size=(porch_w, porch_d, deck_h),
        location=(door_x, (front_y + py_front) * 0.5, z_ground + deck_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    # Wooden front step
    create_beveled_box(
        bm, size=(porch_w * 0.65, 0.35, deck_h * 0.5),
        location=(door_x, py_front - 0.18, z_ground + deck_h * 0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )

    # 2. Turned Timber Support Columns
    col_r = 0.09
    col_h = porch_h - deck_h
    col_z = z_ground + deck_h + col_h * 0.5
    for cx in (px_min + col_r, px_max - col_r):
        create_cylinder(
            bm, radius=col_r, height=col_h, segments=12,
            location=(cx, py_front + col_r, col_z),
            mat_index=MAT_INDEX_TIMBER
        )
        # Pillar capital and base trim rings
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + deck_h + 0.04),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + porch_h - 0.04),
            mat_index=MAT_INDEX_TIMBER
        )

    # 3. Timber Header Beam & Shingled Porch Awning
    create_beveled_box(
        bm, size=(porch_w + 0.20, 0.14, 0.16),
        location=(door_x, py_front + col_r, z_ground + porch_h),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )
    # Sloping porch roof awning
    awning_pitch = 0.35
    awning_l = math.sqrt(porch_d * porch_d + (porch_d * awning_pitch) ** 2) + 0.25
    awning_mid_y = (front_y + py_front) * 0.5
    awning_mid_z = z_ground + porch_h + (porch_d * awning_pitch) * 0.5 + 0.08
    awning_ang = math.atan2(porch_d * awning_pitch, porch_d)
    
    create_beveled_box(
        bm, size=(porch_w + 0.30, awning_l, 0.08),
        location=(door_x, awning_mid_y, awning_mid_z),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    create_beveled_box(
        bm, size=(porch_w + 0.35, awning_l + 0.04, 0.04),
        location=(door_x, awning_mid_y, awning_mid_z + 0.05),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.006
    )

    # 4. Ornate Wrought-Iron Tavern Sign (Mounted to outer front-right veranda post in open air)
    post_cx = px_max - col_r
    post_cy = py_front + col_r
    sign_z = z_ground + porch_h - 0.15
    
    # Iron horizontal bracket pole projecting out to the right (+X)
    bracket_l = 0.85
    arm_x = post_cx + bracket_l * 0.5
    create_cylinder(
        bm, radius=0.024, height=bracket_l, segments=8,
        location=(arm_x, post_cy, sign_z),
        rotation=(0.0, 1.57, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    # Scrollwork knee brace underneath
    create_beveled_box(
        bm, size=(0.020, 0.020, 0.45),
        location=(post_cx + 0.18, post_cy, sign_z - 0.18),
        rotation=(0.0, 0.78, 0.0),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.003
    )
    # Outer decorative scroll curl
    create_cylinder(
        bm, radius=0.035, height=0.022, segments=8,
        location=(post_cx + bracket_l - 0.02, post_cy, sign_z + 0.04),
        rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    # Hanging wooden sign board in YZ plane
    board_x = post_cx + bracket_l * 0.68
    board_d = 0.55
    board_h = 0.42
    board_cz = sign_z - 0.35
    
    # Iron suspension chains
    for cd_off in [-board_d * 0.30, board_d * 0.30]:
        create_cylinder(
            bm, radius=0.012, height=0.15, segments=6,
            location=(board_x, post_cy + cd_off, sign_z - 0.075),
            mat_index=MAT_INDEX_IRON
        )
    # Outer carved wooden sign frame
    create_beveled_box(
        bm, size=(0.05, board_d, board_h),
        location=(board_x, post_cy, board_cz),
        mat_index=MAT_INDEX_WOOD if 'MAT_INDEX_WOOD' in globals() else MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    # Inner painted pub sign board inset
    create_beveled_box(
        bm, size=(0.056, board_d - 0.08, board_h - 0.08),
        location=(board_x, post_cy, board_cz),
        mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.004
    )
    # Top and bottom decorative iron crest finials
    create_cylinder(
        bm, radius=0.018, height=0.04, segments=6,
        location=(board_x, post_cy, board_cz - board_h * 0.5 - 0.02),
        mat_index=MAT_INDEX_IRON
    )


def build_fisherman_stilts(bm, x_min, x_max, y_min, y_max, z_ground, z_floor):
    """
    Builds heavy stilted timber pier pilings and outdoor fish net drying racks:
    - Driven round wooden piles with cross-bracing and iron bolts.
    - Mooring bollards.
    - A-frame fish net drying rack on the side.
    """
    stilt_h = z_floor - z_ground + 0.60
    stilt_z = z_ground - 0.30 + stilt_h * 0.5
    pile_r = 0.13
    
    # 4 corner pilings + mid pilings
    coords = [
        (x_min + pile_r, y_min + pile_r),
        (x_max - pile_r, y_min + pile_r),
        (x_min + pile_r, y_max - pile_r),
        (x_max - pile_r, y_max - pile_r),
        ((x_min + x_max) * 0.5, y_min + pile_r),
        ((x_min + x_max) * 0.5, y_max - pile_r),
    ]
    for px, py in coords:
        create_cylinder(
            bm, radius=pile_r, height=stilt_h, segments=12,
            location=(px, py, stilt_z),
            mat_index=MAT_INDEX_TIMBER
        )
        # Iron collar ring
        create_cylinder(
            bm, radius=pile_r * 1.15, height=0.06, segments=12,
            location=(px, py, z_floor - 0.15),
            mat_index=MAT_INDEX_IRON
        )

    # Mooring bollard at front
    bollard_x = x_min - 0.65
    bollard_y = y_min - 0.55
    create_cylinder(
        bm, radius=0.16, height=0.85, segments=12,
        location=(bollard_x, bollard_y, z_ground + 0.425),
        mat_index=MAT_INDEX_TIMBER
    )
    # Rope ring
    create_cylinder(
        bm, radius=0.19, height=0.10, segments=12,
        location=(bollard_x, bollard_y, z_ground + 0.65),
        mat_index=MAT_INDEX_PLASTER_EXT
    )

    # Outdoor Fish Net Drying Rack (A-frame) on left side (-X)
    rack_x = x_min - 1.20
    rack_cy = (y_min + y_max) * 0.5
    rack_h = 1.8
    rack_l = 2.4
    # Top horizontal pole
    create_horizontal_cylinder(
        bm, radius_y=0.06, radius_z=0.06, length=rack_l, segments=12,
        location=(rack_x, rack_cy, z_ground + rack_h),
        rotation=(0.0, 0.0, 1.57),
        mat_index=MAT_INDEX_TIMBER, smooth=True
    )
    # Angled A-frame legs
    for ly in (rack_cy - rack_l * 0.45, rack_cy + rack_l * 0.45):
        leg_len = math.sqrt(rack_h * rack_h + 0.5 * 0.5)
        create_box(
            bm, size=(0.08, 0.08, leg_len),
            location=(rack_x - 0.25, ly, z_ground + rack_h * 0.5),
            rotation=(0.0, 0.28, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )
        create_box(
            bm, size=(0.08, 0.08, leg_len),
            location=(rack_x + 0.25, ly, z_ground + rack_h * 0.5),
            rotation=(0.0, -0.28, 0.0),
            mat_index=MAT_INDEX_TIMBER
        )


def build_bakery_oven(bm, x_min, x_max, y_min, y_max, z_ground):
    """
    Builds a protruding curved stone/brick bread oven on the right side (+X):
    - Rounded brick dome furnace.
    - Iron oven door.
    - Dedicated brick chimney stack.
    """
    oven_x = x_max + 0.85
    oven_y = (y_min + y_max) * 0.5
    oven_w = 1.6
    oven_d = 1.5
    oven_h = 1.35
    
    # Brick base plinth
    create_beveled_box(
        bm, size=(oven_w, oven_d, 0.50),
        location=(oven_x, oven_y, z_ground + 0.25),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.02
    )
    # Domed upper oven body
    create_cylinder(
        bm, radius=0.65, height=0.65, segments=16,
        location=(oven_x, oven_y, z_ground + 0.50 + 0.325),
        mat_index=MAT_INDEX_STONE
    )
    create_cone(
        bm, radius1=0.65, radius2=0.15, height=0.45, segments=16,
        location=(oven_x, oven_y, z_ground + 0.50 + 0.65 + 0.225),
        mat_index=MAT_INDEX_STONE
    )
    # Dedicated brick chimney on oven
    chim_h = 2.4
    create_beveled_box(
        bm, size=(0.42, 0.42, chim_h),
        location=(oven_x - 0.35, oven_y, z_ground + 1.10 + chim_h * 0.5),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.015
    )
    create_beveled_box(
        bm, size=(0.52, 0.52, 0.12),
        location=(oven_x - 0.35, oven_y, z_ground + 1.10 + chim_h + 0.06),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.01
    )


def build_warehouse_cargo(bm, front_x, front_y, z_ground):
    """
    Builds stacked wooden cargo crates and banded storage barrels near the entrance:
    - Sits beneath the projecting roof hoist beam.
    """
    # Large wooden crate
    create_beveled_box(
        bm, size=(0.85, 0.85, 0.85),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
    )
    # Cross strapping on crate
    create_box(
        bm, size=(0.87, 0.10, 0.87),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.425),
        rotation=(0.0, 0.0, 0.12),
        mat_index=MAT_INDEX_IRON
    )
    # Medium stacked crate on top
    create_beveled_box(
        bm, size=(0.60, 0.60, 0.60),
        location=(front_x + 1.35, front_y - 0.65, z_ground + 0.85 + 0.30),
        rotation=(0.0, 0.0, -0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    # Barrels
    for bx, by in [(front_x - 1.45, front_y - 0.60), (front_x - 1.05, front_y - 0.95)]:
        create_cylinder(
            bm, radius=0.32, height=0.75, segments=12,
            location=(bx, by, z_ground + 0.375),
            mat_index=MAT_INDEX_TIMBER
        )
        # Iron bands on barrel
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
