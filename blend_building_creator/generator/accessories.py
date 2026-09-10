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
    
    deck_thick = 0.12
    # 1. Solid Grounded Cobblestone / Flagstone Workshop Floor (grounded at z_ground)
    create_beveled_box(
        bm, size=(canopy_w + 0.15, canopy_d + 0.20, deck_thick),
        location=(wall_x + canopy_w * 0.5, canopy_cy, z_ground + deck_thick * 0.5),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )
    
    # 2. Heavy Timber Pillars on Grounded Stone Footing Plinths
    col_w = 0.18
    p1_y = canopy_cy - canopy_d * 0.44
    p2_y = canopy_cy + canopy_d * 0.44
    
    for py in (p1_y, p2_y):
        # Grounded stone plinth
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.20),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.10),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
        # Vertical timber pillar
        pillar_h = canopy_h - 0.20
        create_beveled_box(
            bm, size=(col_w, col_w, pillar_h),
            location=(outer_x - col_w * 0.5, py, z_ground + 0.20 + pillar_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        # Angled 45-degree timber knee brace up to header beam (along Y)
        sgn = 1.0 if py < canopy_cy else -1.0
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(outer_x - col_w * 0.5, py + sgn * 0.23, z_ground + canopy_h - 0.23),
            rotation=(sgn * 0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        # Wall-tie 45-degree knee brace back towards wall (along X)
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(outer_x - col_w * 0.5 - 0.23, py, z_ground + canopy_h - 0.23),
            rotation=(0.0, -0.785, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        
    # 3. Outer Horizontal Header Beam connecting pillars
    create_beveled_box(
        bm, size=(col_w, canopy_d + 0.30, 0.18),
        location=(outer_x - col_w * 0.5, canopy_cy, z_ground + canopy_h),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    
    # 4. Sloping Rafters & Roof Deck
    roof_pitch = 0.35
    roof_z_wall = z_ground + canopy_h + canopy_w * roof_pitch
    roof_z_outer = z_ground + canopy_h
    roof_mid_x = (wall_x + outer_x) * 0.5
    roof_mid_z = (roof_z_wall + roof_z_outer) * 0.5 + 0.08
    rafter_l = math.sqrt(canopy_w * canopy_w + (roof_z_wall - roof_z_outer) ** 2) + 0.40
    roof_ang = math.atan2(roof_z_wall - roof_z_outer, canopy_w)
    
    # Supporting rafter beams underneath roof
    for ry in (p1_y, canopy_cy, p2_y):
        create_beveled_box(
            bm, size=(rafter_l, 0.10, 0.14),
            location=(roof_mid_x, ry, roof_mid_z - 0.08),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
    
    # Sloping timber decking slab
    create_beveled_box(
        bm, size=(rafter_l, canopy_d + 0.40, 0.08),
        location=(roof_mid_x, canopy_cy, roof_mid_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_WOOD,
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
    
    # 5. Blacksmith Workshop Fixtures (Grounded on Stone Floor)
    # Masonry Forge Hearth & Hood
    forge_w, forge_d, forge_h = 0.95, 0.95, 0.85
    forge_x = wall_x + forge_w * 0.5 + 0.15
    forge_y = canopy_cy
    create_beveled_box(
        bm, size=(forge_w, forge_d, forge_h),
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h * 0.5),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.02
    )
    # Forge coals depression
    create_box(
        bm, size=(0.60, 0.60, 0.06),
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h + 0.02),
        mat_index=MAT_INDEX_IRON
    )
    # Iron exhaust chimney flue pipe through canopy roof
    chim_pipe_h = (roof_z_wall + 0.80) - (z_ground + deck_thick + forge_h)
    create_cylinder(
        bm, radius=0.14, height=chim_pipe_h, segments=10,
        location=(forge_x, forge_y, z_ground + deck_thick + forge_h + chim_pipe_h * 0.5),
        mat_index=MAT_INDEX_IRON
    )
    
    # Anvil on heavy wooden tree stump
    stump_r = 0.24
    stump_h = 0.46
    stump_x = wall_x + 1.65
    stump_y = canopy_cy - 0.40
    create_cylinder(
        bm, radius=stump_r, height=stump_h, segments=10,
        location=(stump_x, stump_y, z_ground + deck_thick + stump_h * 0.5),
        mat_index=MAT_INDEX_WOOD
    )
    # Forged iron anvil (waist, horn, and heel)
    anvil_z = z_ground + deck_thick + stump_h
    create_beveled_box(
        bm, size=(0.28, 0.54, 0.22),
        location=(stump_x, stump_y, anvil_z + 0.11),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.015
    )
    # Anvil horn cone
    create_cone(
        bm, radius1=0.09, radius2=0.02, height=0.22, segments=8,
        location=(stump_x, stump_y - 0.38, anvil_z + 0.12),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    
    # Water Quenching Trough
    trough_w, trough_d, trough_h = 0.45, 0.70, 0.46
    trough_x = wall_x + 0.60
    trough_y = canopy_cy + canopy_d * 0.34
    create_beveled_box(
        bm, size=(trough_w, trough_d, trough_h),
        location=(trough_x, trough_y, z_ground + deck_thick + trough_h * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
    )
    # Iron barrel bands
    for bz in [-0.14, 0.14]:
        create_box(
            bm, size=(trough_w + 0.02, trough_d + 0.02, 0.035),
            location=(trough_x, trough_y, z_ground + deck_thick + trough_h * 0.5 + bz),
            mat_index=MAT_INDEX_IRON
        )


def build_windmill_sails(bm, cx, front_y, hub_z, radius=3.2, rotation_deg=22.5, wall_y=None):
    """
    Builds a large 4-blade rotating lattice timber windmill rotor:
    - Solid timber axle machinery dormer housing connecting flush to the building wall.
    - 45-degree diagonal timber corbel braces supporting the housing underneath.
    - Central protruding heavy timber axle hub.
    - 4 lattice timber spars with cross-ribs.
    - Stretched canvas cloth sails.
    """
    if wall_y is None:
        wall_y = front_y
        
    hub_y = front_y - 0.38
    
    # 1. Solid Timber Axle Housing / Dormer connecting hub to tower wall
    box_len = max(0.40, abs(hub_y - wall_y) + 0.25)
    box_cy = (hub_y + wall_y) * 0.5
    create_beveled_box(
        bm, size=(1.10, box_len, 1.05),
        location=(cx, box_cy, hub_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02
    )
    # Housing shingled ridge cap
    create_beveled_box(
        bm, size=(1.24, box_len + 0.12, 0.18),
        location=(cx, box_cy, hub_z + 0.56),
        mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.012
    )
    # 45-degree timber supporting knee braces underneath against wall
    for bx_off in [-0.38, 0.38]:
        create_beveled_box(
            bm, size=(0.10, 0.10, 0.55),
            location=(cx + bx_off, box_cy, hub_z - 0.55),
            rotation=(-0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        
    # 2. Central Axle Hub Box protruding from housing
    create_cylinder(
        bm, radius=0.35, height=0.45, segments=12,
        location=(cx, hub_y, hub_z),
        rotation=(1.57, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER
    )
    # Center iron cap
    create_cone(
        bm, radius1=0.22, radius2=0.04, height=0.20, segments=8,
        location=(cx, hub_y - 0.28, hub_z),
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


def _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max):
    """
    Returns (wall_anchor_x, wall_anchor_y, out_dx, out_dy, tan_dx, tan_dy, rot_z)
    for a given facade side.
    """
    if side == 'LEFT': # -X
        return (wall_x_min, (wall_y_min + wall_y_max) * 0.5, -1.0, 0.0, 0.0, 1.0, math.pi)
    elif side == 'RIGHT': # +X
        return (wall_x_max, (wall_y_min + wall_y_max) * 0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
    elif side == 'BACK': # +Y
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_max, 0.0, 1.0, 1.0, 0.0, math.pi * 0.5)
    else: # FRONT (-Y)
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_min, 0.0, -1.0, 1.0, 0.0, -math.pi * 0.5)


def build_mini_wing(bm, side, floor_mode, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                    z_base, width=2.2, depth=1.6, height=2.6, roof_style='LEAN_TO', tier='TIER_3'):
    """
    Builds a small outcrop bay room / annex projection:
    - GROUND: rests on grounded stone foundation plinth.
    - UPPER: cantilevered oriel bay with heavy diagonal timber corbel brackets.
    - Features timber corner posts, leaded glass window, and dedicated shingled roof.
    """
    wx, wy, ox, oy, tx, ty, rot_z = _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    
    half_w = width * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    # 1. Foundation or Console Corbels
    # 1. Foundation or Console Corbels
    if floor_mode == 'GROUND':
        found_depth = depth + 0.15
        found_width = width + 0.20
        create_beveled_box(
            bm,
            size=(found_depth, found_width, 0.30),
            location=(wx + ox * (half_d + 0.05), wy + oy * (half_d + 0.05), z_base - 0.15),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )
    else: # UPPER floor oriel bay
        # Heavy diagonal timber console corbels underneath
        bracket_spacing = width * 0.38
        diag_len = math.sqrt((depth * 0.80) ** 2 + 0.75 ** 2)
        diag_ang = math.atan2(0.75, depth * 0.80)
        bx_vec = Vector((math.cos(diag_ang), 0.0, math.sin(diag_ang)))
        by_vec = Vector((0.0, 1.0, 0.0))
        bz_vec = Vector((-math.sin(diag_ang), 0.0, math.cos(diag_ang)))
        corbel_euler = (facade_rot_mat @ Matrix((bx_vec, by_vec, bz_vec)).transposed().to_4x4()).to_euler()
        
        for b_sign in [-1, 0, 1]:
            loc_c = Vector((depth * 0.40, b_sign * bracket_spacing, z_base - 0.42))
            world_c = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_c.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(diag_len, 0.12, 0.14),
                location=world_c,
                rotation=corbel_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )
            
    # 2. Walk-in Interior Wooden Floor & Ceiling Planks
    # Continuous level walk-in floor
    loc_fl = Vector((depth * 0.50, 0.0, z_base + 0.03))
    world_fl = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fl.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=world_fl,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Interior ceiling planks
    loc_ceil = Vector((depth * 0.50, 0.0, z_base + height - 0.03))
    world_ceil = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_ceil.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=world_ceil,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    
    # 3. Hollow Walls: Front Wall & Side Walls (Leaving Rear Open into Main Room)
    wall_mat = MAT_INDEX_TIMBER if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
    col_w = 0.16
    wall_thick = 0.18
    
    # 3a. Two Side Walls (Left and Right)
    for s_sign in [-1, 1]:
        loc_sw = Vector((depth * 0.50, (half_w - wall_thick * 0.5) * s_sign, z_base + height * 0.5))
        world_sw = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sw.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth, wall_thick, height),
            location=world_sw,
            rotation=(0.0, 0.0, rot_z),
            mat_index=wall_mat,
            bevel_amount=0.012
        )
        # Wall-anchor post at house wall
        loc_post = Vector((col_w * 0.5, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))
        world_post = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_post.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(col_w, col_w, height),
            location=world_post,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Outer corner post
        loc_cpost = Vector((depth - col_w * 0.5, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))
        world_cpost = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_cpost.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(col_w, col_w, height + 0.06),
            location=world_cpost,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        
    # 3b. Outer Front Wall with Window Cutout
    win_w = width * 0.52
    win_h = height * 0.46
    win_z = z_base + height * 0.52
    win_bot_z = win_z - win_h * 0.5
    win_top_z = win_z + win_h * 0.5
    
    # Outer front wall center
    f_wall_x = depth - wall_thick * 0.5
    # Front spandrel below window
    spand_h = win_bot_z - z_base
    loc_spand = Vector((f_wall_x, 0.0, z_base + spand_h * 0.5))
    world_spand = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_spand.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, spand_h),
        location=world_spand,
        rotation=(0.0, 0.0, rot_z),
        mat_index=wall_mat,
        bevel_amount=0.010
    )
    # Front side jambs flanking window
    jamb_w = (width - col_w * 2.0 - win_w) * 0.5 + 0.02
    for s_sign in [-1, 1]:
        jamb_off = (win_w * 0.5 + jamb_w * 0.5 - 0.01) * s_sign
        loc_j = Vector((f_wall_x, jamb_off, win_z))
        world_j = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_j.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(wall_thick, jamb_w, win_h + 0.04),
            location=world_j,
            rotation=(0.0, 0.0, rot_z),
            mat_index=wall_mat,
            bevel_amount=0.008
        )
    # Front header above window
    head_h = (z_base + height) - win_top_z
    loc_head = Vector((f_wall_x, 0.0, win_top_z + head_h * 0.5))
    world_head = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_head.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, head_h),
        location=world_head,
        rotation=(0.0, 0.0, rot_z),
        mat_index=wall_mat,
        bevel_amount=0.008
    )
    
    # Outer top horizontal header beam across front
    loc_fhead = Vector((depth - col_w * 0.5, 0.0, z_base + height))
    world_fhead = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fhead.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(col_w, width + 0.06, 0.16),
        location=world_fhead,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    
    # 4. Outcrop Window Assembly
    loc_sill = Vector((depth + 0.04, 0.0, win_bot_z - 0.04))
    world_sill = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sill.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.10, win_w + 0.16, 0.08),
        location=world_sill,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    # Glass & mullions
    loc_win = Vector((depth, 0.0, win_z))
    world_win = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_win.to_4d()).to_3d()
    create_box(
        bm,
        size=(0.05, win_w, win_h),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_GLASS
    )
    create_box(
        bm,
        size=(0.07, 0.04, win_h),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )
    create_box(
        bm,
        size=(0.07, win_w, 0.04),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )
    
    # 5. Dedicated Roof with Sealed Side Cheek Walls (Zero Gaps)
    roof_z_start = z_base + height
    
    if roof_style == 'LEAN_TO':
        roof_pitch = 0.38
        r_rise = depth * roof_pitch
        r_len = math.sqrt(depth * depth + r_rise * r_rise) + 0.38
        r_ang = math.atan2(r_rise, depth)
        
        # Local roof orientation: slopes DOWNWARDS away from wall (+X local tilts down)
        rx_vec = Vector((math.cos(-r_ang), 0.0, math.sin(-r_ang)))
        ry_vec = Vector((0.0, 1.0, 0.0))
        rz_vec = Vector((-math.sin(-r_ang), 0.0, math.cos(-r_ang)))
        local_rot_mat = Matrix((rx_vec, ry_vec, rz_vec)).transposed().to_4x4()
        total_roof_mat = facade_rot_mat @ local_rot_mat
        roof_euler = total_roof_mat.to_euler()
        
        # Center of roof in local space: halfway along depth and rise
        loc_center = Vector((depth * 0.48, 0.0, roof_z_start + r_rise * 0.52))
        world_center = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_center.to_4d()).to_3d()
        
        # Timber rafter decking
        create_beveled_box(
            bm,
            size=(r_len, width + 0.32, 0.08),
            location=world_center,
            rotation=roof_euler,
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.010
        )
        # Shingle layer
        loc_shingle = Vector((depth * 0.48, 0.0, roof_z_start + r_rise * 0.52 + 0.055))
        world_shingle = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_shingle.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(r_len + 0.04, width + 0.36, 0.05),
            location=world_shingle,
            rotation=roof_euler,
            mat_index=MAT_INDEX_SHINGLES,
            bevel_amount=0.008
        )
        
        # Side triangular cheek closure walls & sloping timber bargeboards
        barge_w = 0.08
        for s_sign in [-1, 1]:
            # Sloping bargeboard on side overhang edge
            loc_barge = Vector((depth * 0.48, (half_w + 0.16) * s_sign, roof_z_start + r_rise * 0.52 + 0.02))
            world_barge = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_barge.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(r_len + 0.06, barge_w, 0.12),
                location=world_barge,
                rotation=roof_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.008
            )
            # Sloping timber rafter plate directly atop the side wall
            loc_side_rafter = Vector((depth * 0.48, (half_w - wall_thick * 0.5) * s_sign, roof_z_start + r_rise * 0.52 - 0.04))
            world_side_rafter = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_side_rafter.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(r_len, wall_thick + 0.02, 0.10),
                location=world_side_rafter,
                rotation=roof_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.008
            )
            # Solid triangular cheek prism filling the wedge between flat side wall top and sloping rafter
            tri_y_center = (half_w - wall_thick * 0.5) * s_sign
            half_t = wall_thick * 0.5
            # Vertices in local space
            p_top_back = Vector((0.0, 0.0, roof_z_start + r_rise))
            p_bot_front = Vector((depth, 0.0, roof_z_start))
            p_bot_back = Vector((0.0, 0.0, roof_z_start))
            
            # Create triangular cheek prism faces
            v_t_b1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center - half_t, roof_z_start + r_rise)).to_4d()).to_3d())
            v_b_f1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((depth, tri_y_center - half_t, roof_z_start)).to_4d()).to_3d())
            v_b_b1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center - half_t, roof_z_start)).to_4d()).to_3d())
            
            v_t_b2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center + half_t, roof_z_start + r_rise)).to_4d()).to_3d())
            v_b_f2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((depth, tri_y_center + half_t, roof_z_start)).to_4d()).to_3d())
            v_b_b2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center + half_t, roof_z_start)).to_4d()).to_3d())
            
            f1 = bm.faces.new([v_t_b1, v_b_f1, v_b_b1])
            f1.material_index = wall_mat
            f2 = bm.faces.new([v_t_b2, v_b_b2, v_b_f2])
            f2.material_index = wall_mat
            f_slope = bm.faces.new([v_t_b1, v_t_b2, v_b_f2, v_b_f1])
            f_slope.material_index = wall_mat
            f_back = bm.faces.new([v_t_b1, v_b_b1, v_b_b2, v_t_b2])
            f_back.material_index = wall_mat
    else: # GABLE roof
        g_roof_h = 0.85
        # Front triangular gable wall on outer face
        create_beveled_box(
            bm,
            size=(0.12, width - 0.08, g_roof_h * 0.5),
            location=(wx + ox * (depth - 0.06), wy + oy * (depth - 0.06), roof_z_start + g_roof_h * 0.25),
            rotation=(0.0, 0.0, rot_z),
            mat_index=wall_mat,
            bevel_amount=0.01
        )
        # Pitched roof slopes (left & right of projection)
        r_pitch_len = math.sqrt((width * 0.5 + 0.18) ** 2 + g_roof_h ** 2)
        r_pitch_ang = math.atan2(g_roof_h, width * 0.5 + 0.18)
        for s_sign in [-1, 1]:
            # Local slope rotation: tilts around local X axis
            sx_vec = Vector((1.0, 0.0, 0.0))
            sy_vec = Vector((0.0, math.cos(s_sign * r_pitch_ang), -math.sin(s_sign * r_pitch_ang)))
            sz_vec = Vector((0.0, math.sin(s_sign * r_pitch_ang), math.cos(s_sign * r_pitch_ang)))
            g_rot = (facade_rot_mat @ Matrix((sx_vec, sy_vec, sz_vec)).transposed().to_4x4()).to_euler()
            
            loc_slope = Vector((depth * 0.5, (half_w * 0.5 + 0.06) * s_sign, roof_z_start + g_roof_h * 0.5))
            world_slope = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_slope.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(depth + 0.35, r_pitch_len, 0.08),
                location=world_slope,
                rotation=g_rot,
                mat_index=MAT_INDEX_SHINGLES,
                bevel_amount=0.008
            )


def build_balcony(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                  z_floor, width=2.4, depth=1.3, tier='TIER_3'):
    """
    Builds an authentic cantilevered wooden balcony platform on an upper floor:
    - Cantilevered floor joists projecting from the wall.
    - Matrix-aligned 45-degree diagonal timber corbel struts underneath.
    - Thick rustic wooden plank deck.
    - Timber balustrade railing with newel posts and handrails.
    - Authentic plank door with iron hinges inside the wall doorway.
    """
    wx, wy, ox, oy, tx, ty, rot_z = _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    
    half_w = width * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    # 1. Cantilevered Timber Floor Joist Beams & Matrix-Aligned Diagonal Struts
    joist_count = 3
    spacing = width * 0.38
    
    for j_sign in [-1, 0, 1]:
        # Horizontal joist beam
        loc_j = Vector((depth * 0.50, j_sign * spacing, z_floor - 0.08))
        world_j = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_j.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth + 0.35, 0.12, 0.16),
            location=world_j,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        # Diagonal timber corbel strut underneath reaching from wall up to joist
        p_wall = Vector((wx, wy, z_floor - 0.65)) + Vector((tx, ty, 0.0)) * (j_sign * spacing)
        p_joist = Vector((wx, wy, z_floor - 0.12)) + Vector((ox, oy, 0.0)) * (depth * 0.72) + Vector((tx, ty, 0.0)) * (j_sign * spacing)
        v_strut = p_joist - p_wall
        strut_len = v_strut.length
        strut_dir = v_strut.normalized()
        strut_norm = Vector((tx, ty, 0.0)).normalized()
        strut_side = strut_dir.cross(strut_norm).normalized()
        strut_mat = Matrix((strut_norm, strut_side, strut_dir)).transposed().to_4x4()
        
        loc_strut = (p_wall + p_joist) * 0.5
        create_beveled_box(
            bm,
            size=(0.11, 0.13, strut_len),
            location=loc_strut,
            rotation=strut_mat.to_euler(),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        
    # 2. Rustic Wood Deck Planks
    loc_deck = Vector((depth * 0.50, 0.0, z_floor + 0.03))
    world_deck = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_deck.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(depth + 0.08, width + 0.10, 0.06),
        location=world_deck,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    
    # 3. Perimeter Balustrade / Railing
    rail_h = 0.95
    post_w = 0.10
    outer_d = depth + 0.02
    for s_sign in [-1, 1]:
        # Outer corner posts
        loc_cp = Vector((outer_d, half_w * s_sign, z_floor + 0.06 + rail_h * 0.5))
        world_cp = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_cp.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(post_w, post_w, rail_h),
            location=world_cp,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Wall-anchor posts
        loc_wp = Vector((0.08, half_w * s_sign, z_floor + 0.06 + rail_h * 0.5))
        world_wp = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_wp.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(post_w, post_w, rail_h),
            location=world_wp,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Side return top handrail
        loc_sr = Vector((depth * 0.50, half_w * s_sign, z_floor + 0.06 + rail_h))
        world_sr = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sr.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth - 0.08, 0.08, 0.08),
            location=world_sr,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
        # Side mid-rail
        loc_sm = Vector((depth * 0.50, half_w * s_sign, z_floor + 0.06 + rail_h * 0.45))
        world_sm = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sm.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth - 0.08, 0.06, 0.06),
            location=world_sm,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.006
        )
        
    # Front outer top handrail
    loc_fr = Vector((outer_d, 0.0, z_floor + 0.06 + rail_h))
    world_fr = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fr.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.08, width + 0.04, 0.08),
        location=world_fr,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    # Front mid-rail
    loc_fm = Vector((outer_d, 0.0, z_floor + 0.06 + rail_h * 0.45))
    world_fm = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fm.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.06, width - 0.04, 0.06),
        location=world_fm,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.006
    )
    # Vertical balusters along front
    baluster_count = 5
    for b_idx in range(baluster_count):
        t_pos = -half_w * 0.8 + (b_idx / (baluster_count - 1)) * (width * 0.8)
        loc_b = Vector((outer_d, t_pos, z_floor + 0.06 + rail_h * 0.48))
        world_b = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_b.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.04, 0.04, rail_h * 0.85),
            location=world_b,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.004
        )
        
    # 4. Authentic Plank Door Leading Out to Balcony
    door_w = 0.92
    door_h = 2.02
    door_thick = 0.05
    # Heavy timber door frame
    loc_dl = Vector((0.02, 0.0, z_floor + door_h + 0.06))
    world_dl = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dl.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.14, door_w + 0.20, 0.12),
        location=world_dl,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )
    for d_sign in [-1, 1]:
        loc_dj = Vector((0.02, (door_w * 0.5 + 0.06) * d_sign, z_floor + door_h * 0.5))
        world_dj = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dj.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.14, 0.12, door_h),
            location=world_dj,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        
    # Vertical plank wooden door leaf (slightly ajar 15 degrees outwards onto balcony)
    ajar_ang = 0.26 # ~15 degrees
    door_leaf_rot = (facade_rot_mat @ Matrix.Rotation(ajar_ang, 4, 'Z')).to_euler()
    # Hinge is at -Y jamb
    hinge_y = -door_w * 0.5 + 0.04
    loc_door = Vector((0.06 + math.sin(ajar_ang) * door_w * 0.45, hinge_y + math.cos(ajar_ang) * door_w * 0.45, z_floor + door_h * 0.5))
    world_door = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_door.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(door_thick, door_w - 0.04, door_h - 0.04),
        location=world_door,
        rotation=door_leaf_rot,
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Decorative iron strap hinges
    for h_rel in [0.25, 0.75]:
        loc_h = Vector((0.08 + math.sin(ajar_ang) * 0.22, hinge_y + math.cos(ajar_ang) * 0.22, z_floor + door_h * h_rel))
        world_h = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_h.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.02, 0.42, 0.05),
            location=world_h,
            rotation=door_leaf_rot,
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.003
        )
    # Iron latch handle
    loc_latch = Vector((0.08 + math.sin(ajar_ang) * (door_w * 0.78), hinge_y + math.cos(ajar_ang) * (door_w * 0.78), z_floor + door_h * 0.48))
    world_latch = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_latch.to_4d()).to_3d()
    create_cylinder(
        bm,
        radius=0.025,
        height=0.14,
        segments=8,
        location=world_latch,
        mat_index=MAT_INDEX_IRON
    )


def build_pillared_overhang(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                            z_ground, z_ceiling, depth=1.6, pillar_count=3,
                            pillar_style='TIMBER_STONE', tier='TIER_3'):
    """
    Builds a colonnaded portico / upper overhang supported by heavy vertical pillars
    extending from the overhang header beam down to ground level.
    """
    wx, wy, ox, oy, tx, ty, rot_z = _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    
    total_w = abs((wall_y_max - wall_y_min) if abs(ox) > 0.5 else (wall_x_max - wall_x_min)) * 0.88
    half_w = total_w * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    total_col_h = z_ceiling - z_ground
    outer_d = depth
    
    # 1. Outer Horizontal Header Beam
    header_w = 0.18
    header_h = 0.20
    create_beveled_box(
        bm,
        size=(header_w, total_w + 0.30, header_h),
        location=(wx + ox * (outer_d - header_w * 0.5), wy + oy * (outer_d - header_w * 0.5), z_ceiling - header_h * 0.5),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    
    # 2. Vertical Pillars reaching all the way down to ground
    pillar_col_w = 0.18
    plinth_h = 0.25
    plinth_w = 0.36
    
    step_t = total_w / max(1, pillar_count - 1)
    for p_i in range(pillar_count):
        t_offset = -half_w + p_i * step_t
        px = wx + ox * (outer_d - header_w * 0.5) + tx * t_offset
        py = wy + oy * (outer_d - header_w * 0.5) + ty * t_offset
        
        if pillar_style == 'TIMBER_STONE':
            # Grounded stone plinth
            create_beveled_box(
                bm,
                size=(plinth_w, plinth_w, plinth_h),
                location=(px, py, z_ground + plinth_h * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )
            # Timber pillar post
            shaft_h = total_col_h - plinth_h - header_h
            create_beveled_box(
                bm,
                size=(pillar_col_w, pillar_col_w, shaft_h),
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )
            # 45-deg angled knee braces up to header beam in the colonnade plane
            brace_len = 0.55
            for sgn in ([-1] if p_i == pillar_count - 1 else ([1] if p_i == 0 else [-1, 1])):
                brace_dir = (Vector((tx, ty, 0.0)) * sgn + Vector((0.0, 0.0, 1.0))).normalized()
                brace_norm = Vector((ox, oy, 0.0)).normalized()
                brace_side = brace_dir.cross(brace_norm).normalized()
                brace_rot_mat = Matrix((brace_norm, brace_side, brace_dir)).transposed().to_4x4()
                
                loc_b = Vector((px, py, z_ceiling - header_h)) + (Vector((tx, ty, 0.0)) * sgn * 0.19 - Vector((0.0, 0.0, 0.19)))
                create_beveled_box(
                    bm,
                    size=(0.10, 0.10, brace_len),
                    location=loc_b,
                    rotation=brace_rot_mat.to_euler(),
                    mat_index=MAT_INDEX_TIMBER_FRAME,
                    bevel_amount=0.008
                )
        elif pillar_style == 'ROUND_POST':
            # Round log post
            create_cylinder(
                bm,
                radius=0.18, height=plinth_h, segments=12,
                location=(px, py, z_ground + plinth_h * 0.5),
                mat_index=MAT_INDEX_STONE
            )
            shaft_h = total_col_h - plinth_h - header_h
            create_cylinder(
                bm,
                radius=0.11, height=shaft_h, segments=12,
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME
            )
        else: # STONE_COLUMN
            # Full chunky masonry pier
            create_beveled_box(
                bm,
                size=(0.32, 0.32, total_col_h - header_h),
                location=(px, py, z_ground + (total_col_h - header_h) * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )
            
    # 3. Timber Ceiling Beams underneath the overhang
    beam_spacing = total_w / max(1, pillar_count - 1)
    for b_i in range(pillar_count):
        t_off = -half_w + b_i * beam_spacing
        bx = wx + ox * half_d + tx * t_off
        by = wy + oy * half_d + ty * t_off
        create_beveled_box(
            bm,
            size=(depth, 0.12, 0.14),
            location=(bx, by, z_ceiling - 0.07),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.01
        )
    # Solid wooden soffit ceiling plate
    create_beveled_box(
        bm,
        size=(depth, total_w + 0.10, 0.05),
        location=(cx, cy, z_ceiling - 0.025),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.006
    )
    # Ground flagstone platform
    create_beveled_box(
        bm,
        size=(depth + 0.20, total_w + 0.35, 0.12),
        location=(cx, cy, z_ground + 0.06),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )

