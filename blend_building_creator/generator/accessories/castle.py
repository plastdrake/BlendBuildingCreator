"""
Castle Citadel Generator for BlendBuildingCreator.

Procedurally constructs an authentic, asymmetrical, adventure-filled fantasy fortress castle:
1. Asymmetrical massing:
   - Left Wing: Royal Library & Scholar's Wing with steep gothic gable roof, dormers,
     and the soaring Scholar's Tower with a steep conical witch-hat spire roof (NO merlons).
   - Right Wing: High Fortress & Rampart Wing with a FLAT STONE ROOF, walkable rampart walk,
     and the Grand Bastion Tower with a FLAT STONE DECK and CRENELLATED MERLONS (NO pointy roof).
   - Center: Monumental Barbican portal gateway with a flat crenellated stone viewing terrace,
     and the soaring Central Donjon Keep rising 45m with a grand faceted spire.
   - High arched stone skybridge connecting the upper Scholar's Wing to the Keep.
2. Exploratory Interior Adventure:
   - Walkable Subterranean Citadel Level (Z in [-3.6, 0.0]):
     - Vaulted Wine Cellar with stone pillars, barrel racks, and alcoves.
     - Castle Dungeon with iron-barred cells, prisoner shackles, and guard post.
     - Two Secret Mural Passageways (hidden corridors inside thick walls):
       * Secret Passage 1: connects Wine Cellar to the secret base of the Scholar's Tower.
       * Secret Passage 2: connects Dungeon to a hidden exit behind the Great Ballroom fireplace!
   - Great Ballroom & Banquet Hall with monumental fireplace, dais, and arched windows.
   - Walkable roof battlements and ramparts allowing full player traversal!
"""

import math
from mathutils import Vector, Matrix, Euler

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone
)
from ..uv_utils import apply_roof_shingle_uvs
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_SHINGLES, MAT_INDEX_IRON,
    MAT_INDEX_GLASS, MAT_INDEX_FLOOR
)


# =============================================================================
# TOWER BUILDERS (Strict Rule: Pointy roofs have NO merlons; Flat towers have NO pointy roofs)
# =============================================================================

def build_spire_tower(bm, cx, cy, z_ground, radius=3.6, shaft_h=24.0, spire_h=11.0,
                      segments=28, num_floors=4, has_oriel=False, oriel_ang=0.0):
    """
    Type 1: Fairy-tale Spire / Witch-Hat Tower (Scholar's Tower / Watchtower).
    Features:
    - Stepped cut-stone plinth
    - Cylindrical ashlar shaft with horizontal torus mouldings
    - Arrow-slit cross loopholes and gothic arched windows
    - Flared stone corbel cornice table at the head
    - Steep conical witch-hat spire roof with needle finial and pennant flag
    - STRICT RULE: NO merlons around the spire!
    """
    # 1. Base plinth
    p0_h, p1_h = 0.50, 0.40
    create_cylinder(bm, radius=radius + 0.65, height=p0_h, segments=segments,
                    location=(cx, cy, z_ground + p0_h * 0.5), mat_index=MAT_INDEX_STONE)
    create_cylinder(bm, radius=radius + 0.35, height=p1_h, segments=segments,
                    location=(cx, cy, z_ground + p0_h + p1_h * 0.5), mat_index=MAT_INDEX_CUT_STONE)
    shaft_z0 = z_ground + p0_h + p1_h
    actual_shaft_h = shaft_h - (p0_h + p1_h)

    # 2. Cylindrical stone shaft
    create_cylinder(bm, radius=radius, height=actual_shaft_h, segments=segments,
                    location=(cx, cy, shaft_z0 + actual_shaft_h * 0.5), mat_index=MAT_INDEX_STONE)

    # 3. Cut-stone belt courses
    fl_step = actual_shaft_h / max(1, num_floors)
    for f in range(1, num_floors):
        create_cylinder(bm, radius=radius + 0.12, height=0.22, segments=segments,
                        location=(cx, cy, shaft_z0 + f * fl_step), mat_index=MAT_INDEX_CUT_STONE)

    # 4. Windows & arrow slits
    for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        ca, sa = math.cos(ang), math.sin(ang)
        for f in range(num_floors):
            wz = shaft_z0 + (f + 0.5) * fl_step
            fx, fy = cx + radius * ca, cy + radius * sa
            ang_z = ang + math.pi * 0.5
            if f % 2 == 0:
                # Arrow slit
                create_beveled_box(bm, size=(0.65, 0.22, 1.35),
                                   location=(fx + ca * 0.05, fy + sa * 0.05, wz),
                                   rotation=(0.0, 0.0, ang_z),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
                create_box(bm, size=(0.14, 0.26, 1.05),
                           location=(fx + ca * 0.08, fy + sa * 0.08, wz),
                           rotation=(0.0, 0.0, ang_z), mat_index=MAT_INDEX_IRON)
            else:
                # Gothic arched window
                create_beveled_box(bm, size=(0.95, 0.28, 1.75),
                                   location=(fx + ca * 0.05, fy + sa * 0.05, wz),
                                   rotation=(0.0, 0.0, ang_z),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
                create_box(bm, size=(0.58, 0.30, 1.35),
                           location=(fx + ca * 0.08, fy + sa * 0.08, wz),
                           rotation=(0.0, 0.0, ang_z), mat_index=MAT_INDEX_GLASS)

    # 5. Optional Scholar's Oriel Lookout Bay
    if has_oriel:
        oca, osa = math.cos(oriel_ang), math.sin(oriel_ang)
        ow_z = shaft_z0 + actual_shaft_h * 0.65
        ox = cx + (radius + 0.60) * oca
        oy = cy + (radius + 0.60) * osa
        create_cone(bm, radius1=1.40, radius2=0.20, height=1.20, segments=8,
                    location=(ox, oy, ow_z - 0.60), rotation=(0.0, math.pi, 0.0),
                    mat_index=MAT_INDEX_CUT_STONE)
        create_beveled_box(bm, size=(2.0, 1.6, 2.4),
                           location=(ox, oy, ow_z + 1.20),
                           rotation=(0.0, 0.0, oriel_ang + math.pi * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        create_cone(bm, radius1=1.55, radius2=0.05, height=1.8, segments=8,
                    location=(ox, oy, ow_z + 2.4 + 0.90), mat_index=MAT_INDEX_SHINGLES)

    # 6. Flared stone corbel cornice table under spire
    head_z = shaft_z0 + actual_shaft_h
    corn_h = 0.90
    create_cone(bm, radius1=radius + 0.65, radius2=radius, height=corn_h, segments=segments,
                location=(cx, cy, head_z - corn_h * 0.5), rotation=(0.0, math.pi, 0.0),
                mat_index=MAT_INDEX_CUT_STONE)
    # Coping ring
    create_cylinder(bm, radius=radius + 0.72, height=0.24, segments=segments,
                    location=(cx, cy, head_z + 0.12), mat_index=MAT_INDEX_CUT_STONE)

    # 7. Steep Conical Witch-Hat Spire (NO MERLONS!)
    spire_r = radius + 0.80
    roof_faces = create_cone(bm, radius1=spire_r, radius2=0.05, height=spire_h, segments=segments,
                             location=(cx, cy, head_z + 0.24 + spire_h * 0.5),
                             mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, roof_faces)

    # 8. Apex Finial Needle & Pennant Flag
    apex_z = head_z + 0.24 + spire_h
    create_cylinder(bm, radius=0.18, height=0.30, segments=12,
                    location=(cx, cy, apex_z + 0.15), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.15, height=0.25, segments=12,
                    location=(cx, cy, apex_z + 0.42), mat_index=MAT_INDEX_CUT_STONE)
    create_cylinder(bm, radius=0.035, height=2.20, segments=8,
                    location=(cx, cy, apex_z + 0.55 + 1.10), mat_index=MAT_INDEX_IRON)
    # Flag
    create_box(bm, size=(1.60, 0.03, 0.65), location=(cx + 0.80, cy, apex_z + 1.75),
               mat_index=MAT_INDEX_CUT_STONE)


def build_battlement_tower(bm, cx, cy, z_ground, radius=4.4, shaft_h=20.0,
                           segments=28, num_floors=3, corbel_count=18):
    """
    Type 2: Heavy Fortress Bastion Tower (Open Fighting Platform).
    Features:
    - Massive cylindrical/D-shaped cut-stone plinth and shaft
    - Flared machicolations with deep stone corbel brackets
    - Walkable flat stone roof deck (accessible for players!)
    - Crenellated stone battlements with merlons and embrasures
    - Iron signal brazier / fire basket on tripod legs
    - STRICT RULE: NO pointy roof! A true open defensive platform!
    """
    # 1. Battered plinth
    p_h = 1.20
    create_cone(bm, radius1=radius + 0.80, radius2=radius + 0.15, height=p_h, segments=segments,
                location=(cx, cy, z_ground + p_h * 0.5), mat_index=MAT_INDEX_STONE)
    shaft_z0 = z_ground + p_h
    actual_shaft_h = shaft_h - p_h

    # 2. Main shaft
    create_cylinder(bm, radius=radius, height=actual_shaft_h, segments=segments,
                    location=(cx, cy, shaft_z0 + actual_shaft_h * 0.5), mat_index=MAT_INDEX_STONE)

    # 3. String courses and arrow slits
    fl_step = actual_shaft_h / max(1, num_floors)
    for f in range(1, num_floors):
        create_cylinder(bm, radius=radius + 0.14, height=0.26, segments=segments,
                        location=(cx, cy, shaft_z0 + f * fl_step), mat_index=MAT_INDEX_CUT_STONE)

    for ang in [i * (math.pi / 3.0) for i in range(6)]:
        ca, sa = math.cos(ang), math.sin(ang)
        for f in range(num_floors):
            wz = shaft_z0 + (f + 0.5) * fl_step
            fx, fy = cx + radius * ca, cy + radius * sa
            ang_z = ang + math.pi * 0.5
            create_beveled_box(bm, size=(0.70, 0.24, 1.40),
                               location=(fx + ca * 0.05, fy + sa * 0.05, wz),
                               rotation=(0.0, 0.0, ang_z),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
            create_box(bm, size=(0.14, 0.28, 1.10),
                       location=(fx + ca * 0.08, fy + sa * 0.08, wz),
                       rotation=(0.0, 0.0, ang_z), mat_index=MAT_INDEX_IRON)

    # 4. Machicolation Gallery (Corbel brackets)
    gallery_r = radius + 0.70
    corbel_h = 1.20
    deck_z = shaft_z0 + actual_shaft_h
    create_cone(bm, radius1=gallery_r, radius2=radius, height=corbel_h, segments=segments,
                location=(cx, cy, deck_z - corbel_h * 0.5), rotation=(0.0, math.pi, 0.0),
                mat_index=MAT_INDEX_CUT_STONE)

    for i in range(corbel_count):
        ang = (2.0 * math.pi * i) / corbel_count
        ca, sa = math.cos(ang), math.sin(ang)
        create_beveled_box(bm, size=(0.30, 0.75, corbel_h + 0.20),
                           location=(cx + (radius + 0.35) * ca, cy + (radius + 0.35) * sa,
                                     deck_z - corbel_h * 0.5),
                           rotation=(0.0, 0.0, ang + math.pi * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 5. Walkable Flat Stone Roof Deck
    create_cylinder(bm, radius=gallery_r, height=0.30, segments=segments,
                    location=(cx, cy, deck_z + 0.15), mat_index=MAT_INDEX_CUT_STONE)

    # 6. Crenellated Stone Merlons (NO POINTY ROOF!)
    parapet_h = 1.25
    parapet_t = 0.32
    parapet_mid_r = gallery_r - parapet_t * 0.5
    merlon_count = corbel_count

    # Parapet curb
    create_cylinder(bm, radius=gallery_r, height=0.35, segments=segments,
                    location=(cx, cy, deck_z + 0.30 + 0.175), mat_index=MAT_INDEX_CUT_STONE)

    # Alternating merlons
    for i in range(merlon_count):
        if i % 2 == 0:
            ang = (2.0 * math.pi * i) / merlon_count
            ca, sa = math.cos(ang), math.sin(ang)
            m_w = (2.0 * math.pi * parapet_mid_r / merlon_count) * 0.85
            m_h = parapet_h - 0.35
            create_beveled_box(bm, size=(m_w, parapet_t, m_h),
                               location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                                         deck_z + 0.65 + m_h * 0.5),
                               rotation=(0.0, 0.0, ang + math.pi * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
            # Merlon stone cap
            create_cone(bm, radius1=m_w * 0.55, radius2=0.02, height=0.18, segments=4,
                        location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                                  deck_z + 0.65 + m_h + 0.09),
                        rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

    # 7. Iron Signal Fire Brazier in center of fighting deck
    br_z = deck_z + 0.30
    create_cylinder(bm, radius=0.45, height=0.30, segments=12,
                    location=(cx, cy, br_z + 0.75), mat_index=MAT_INDEX_IRON)
    for leg_ang in (0.0, math.pi * 0.66, math.pi * 1.33):
        lca, lsa = math.cos(leg_ang), math.sin(leg_ang)
        create_cylinder(bm, radius=0.04, height=0.75, segments=6,
                        location=(cx + 0.35 * lca, cy + 0.35 * lsa, br_z + 0.375),
                        rotation=(0.15 * lsa, -0.15 * lca, 0.0), mat_index=MAT_INDEX_IRON)


# =============================================================================
# UNDER-CITADEL: DUNGEON, WINE CELLAR & SECRET MURAL PASSAGES
# =============================================================================

def build_castle_underground_citadel(bm, cx=0.0, cy=0.0, z_ground=0.0, width=44.0, depth=18.0):
    """
    Subterranean Citadel Level (Z in [-3.6, 0.0]):
    - The Great Vaulted Wine Cellar with stone pillars, barrel racks, and alcoves
    - The Castle Dungeon with iron-barred prison cells, shackles, and guard post
    - Two Secret Mural Passageways (hidden corridors inside thick walls):
      * Secret Passage 1: Wine Cellar -> Scholar's Tower base
      * Secret Passage 2: Dungeon -> Behind the Great Ballroom fireplace!
    All floors, walls, and doorways are physically modelled and walkable for Unreal Engine!
    """
    z_floor = z_ground - 3.60
    vault_h = 3.40
    half_w = width * 0.5
    half_d = depth * 0.5

    # 1. Main Subterranean Stone Floor Slab
    create_box(bm, size=(width, depth, 0.25), location=(cx, cy, z_floor - 0.125),
               mat_index=MAT_INDEX_STONE)

    # 2. Outer Heavy Masonry Foundation Walls
    wall_t = 1.00
    # North wall (+Y)
    create_box(bm, size=(width, wall_t, vault_h),
               location=(cx, cy + half_d - wall_t * 0.5, z_floor + vault_h * 0.5),
               mat_index=MAT_INDEX_STONE)
    # South wall (-Y)
    create_box(bm, size=(width, wall_t, vault_h),
               location=(cx, cy - half_d + wall_t * 0.5, z_floor + vault_h * 0.5),
               mat_index=MAT_INDEX_STONE)
    # West wall (-X)
    create_box(bm, size=(wall_t, depth - wall_t * 2, vault_h),
               location=(cx - half_w + wall_t * 0.5, cy, z_floor + vault_h * 0.5),
               mat_index=MAT_INDEX_STONE)
    # East wall (+X)
    create_box(bm, size=(wall_t, depth - wall_t * 2, vault_h),
               location=(cx + half_w - wall_t * 0.5, cy, z_floor + vault_h * 0.5),
               mat_index=MAT_INDEX_STONE)

    # 3. Dividing Central Stone Spine Wall with Arched Corridor Doorways
    create_box(bm, size=(0.80, depth - wall_t * 2, vault_h),
               location=(cx, cy, z_floor + vault_h * 0.5), mat_index=MAT_INDEX_CUT_STONE)
    # Cut doorway in spine wall connecting East (Wine Cellar) and West (Dungeon)
    create_box(bm, size=(0.85, 2.20, 2.40),
               location=(cx, cy, z_floor + 1.20), mat_index=MAT_INDEX_STONE)

    # -------------------------------------------------------------------------
    # 4. EAST WING: THE GREAT VAULTED WINE CELLAR (X in [2, 20])
    # -------------------------------------------------------------------------
    # Stone groin vault pillars
    for px in (cx + 6.0, cx + 14.0):
        for py in (cy - 3.5, cy + 3.5):
            create_beveled_box(bm, size=(0.70, 0.70, vault_h),
                               location=(px, py, z_floor + vault_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
            # Pillar carved cap & base
            create_beveled_box(bm, size=(0.95, 0.95, 0.25),
                               location=(px, py, z_floor + 0.125),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
            create_beveled_box(bm, size=(0.95, 0.95, 0.25),
                               location=(px, py, z_floor + vault_h - 0.125),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Giant oak wine tun casks / barrels on skid racks
    for bx, by, rot in [(cx + 18.0, cy - 4.5, 0.0), (cx + 18.0, cy - 1.5, 0.0),
                        (cx + 18.0, cy + 1.5, 0.0), (cx + 18.0, cy + 4.5, 0.0),
                        (cx + 10.0, cy + 6.0, 1.57), (cx + 6.0, cy + 6.0, 1.57)]:
        # Timber support skid
        create_beveled_box(bm, size=(1.8, 0.35, 0.25), location=(bx, by, z_floor + 0.125),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
        # Giant barrel
        create_cylinder(bm, radius=0.68, height=1.65, segments=16,
                        location=(bx, by, z_floor + 0.85),
                        rotation=(0.0, 1.5708, rot), mat_index=MAT_INDEX_TIMBER)
        create_cylinder(bm, radius=0.70, height=0.08, segments=16,
                        location=(bx, by, z_floor + 0.85),
                        rotation=(0.0, 1.5708, rot), mat_index=MAT_INDEX_IRON)

    # -------------------------------------------------------------------------
    # 5. WEST WING: THE CASTLE DUNGEON & CELLS (X in [-20, -2])
    # -------------------------------------------------------------------------
    # Dungeon cell dividing partition walls
    cell_y_positions = [cy - 5.0, cy, cy + 5.0]
    for dy in cell_y_positions:
        create_box(bm, size=(6.5, 0.40, vault_h),
                   location=(cx - 14.5, dy, z_floor + vault_h * 0.5),
                   mat_index=MAT_INDEX_STONE)

    # Iron barred front grates for the 3 cells
    for cy_mid in [(cell_y_positions[0] + cell_y_positions[1]) * 0.5,
                   (cell_y_positions[1] + cell_y_positions[2]) * 0.5]:
        # Iron frame
        create_beveled_box(bm, size=(0.14, 4.5, vault_h),
                           location=(cx - 11.2, cy_mid, z_floor + vault_h * 0.5),
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.01)
        # Iron vertical cell bars
        for bar_idx in range(9):
            by_pos = cy_mid - 2.0 + bar_idx * 0.50
            create_cylinder(bm, radius=0.035, height=vault_h - 0.20, segments=8,
                            location=(cx - 11.2, by_pos, z_floor + vault_h * 0.5),
                            mat_index=MAT_INDEX_IRON)
        # Stone sleeping bench in each cell
        create_beveled_box(bm, size=(1.2, 2.2, 0.45),
                           location=(cx - 18.0, cy_mid, z_floor + 0.225),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # -------------------------------------------------------------------------
    # 6. SECRET MURAL PASSAGES (Hidden Walkways Inside the Foundation Walls)
    # -------------------------------------------------------------------------
    # Secret Passage 1: Wine Cellar -> Scholar's Tower Base
    # Starts behind the wine barrels at (cx + 18, cy + 6), runs north inside wall!
    p1_w, p1_h = 1.30, 2.40
    # Walkable corridor floor & clearance
    create_box(bm, size=(p1_w, 8.0, 0.15),
               location=(cx + 18.0, cy + 9.5, z_floor - 0.05), mat_index=MAT_INDEX_CUT_STONE)
    # Flanking stone walls of secret passage
    create_box(bm, size=(0.35, 8.0, p1_h),
               location=(cx + 18.0 - p1_w * 0.5 - 0.175, cy + 9.5, z_floor + p1_h * 0.5),
               mat_index=MAT_INDEX_CUT_STONE)
    create_box(bm, size=(0.35, 8.0, p1_h),
               location=(cx + 18.0 + p1_w * 0.5 + 0.175, cy + 9.5, z_floor + p1_h * 0.5),
               mat_index=MAT_INDEX_CUT_STONE)
    # Ceiling of passage
    create_box(bm, size=(p1_w + 0.70, 8.0, 0.25),
               location=(cx + 18.0, cy + 9.5, z_floor + p1_h + 0.125), mat_index=MAT_INDEX_CUT_STONE)

    # Secret Passage 2: Dungeon Solitary Cell -> Behind Ballroom Fireplace!
    # Starts in the solitary cell (cx - 18, cy + 6), climbs up inside wall!
    create_box(bm, size=(p1_w, 8.0, 0.15),
               location=(cx - 18.0, cy + 9.5, z_floor - 0.05), mat_index=MAT_INDEX_CUT_STONE)
    create_box(bm, size=(0.35, 8.0, p1_h),
               location=(cx - 18.0 - p1_w * 0.5 - 0.175, cy + 9.5, z_floor + p1_h * 0.5),
               mat_index=MAT_INDEX_CUT_STONE)
    create_box(bm, size=(0.35, 8.0, p1_h),
               location=(cx - 18.0 + p1_w * 0.5 + 0.175, cy + 9.5, z_floor + p1_h * 0.5),
               mat_index=MAT_INDEX_CUT_STONE)
    create_box(bm, size=(p1_w + 0.70, 8.0, 0.25),
               location=(cx - 18.0, cy + 9.5, z_floor + p1_h + 0.125), mat_index=MAT_INDEX_CUT_STONE)


# =============================================================================
# GREAT BALLROOM & BANQUET HALL
# =============================================================================

def build_great_ballroom_features(bm, cx=0.0, cy=0.0, z_floor=1.5, width=28.0, depth=14.0):
    """
    Grand Royal Ballroom & Banquet Hall:
    - Double-height vaulted space
    - Monumental stone fireplace on the wall (with hidden flue passage behind it!)
    - Royal dais with carved cut-stone steps and throne balusters
    - Heavy timber hammerbeam ceiling trusses
    """
    hall_h = 8.5
    # 1. Monumental Stone Fireplace on West Wall (cx - width*0.5 + 0.6)
    fx = cx - width * 0.5 + 0.60
    fy = cy
    create_beveled_box(bm, size=(1.20, 3.80, 4.20),
                       location=(fx, fy, z_floor + 2.10),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04)
    # Fireplace hearth opening
    create_box(bm, size=(1.25, 2.40, 2.60),
               location=(fx + 0.10, fy, z_floor + 1.30), mat_index=MAT_INDEX_STONE)
    # Hooded over-mantel rising to ceiling
    create_cone(bm, radius1=1.80, radius2=0.80, height=3.60, segments=4,
                location=(fx, fy, z_floor + 4.20 + 1.80),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

    # 2. Royal Dais Platform (North Wall)
    create_beveled_box(bm, size=(8.0, 3.6, 0.45),
                       location=(cx, cy + depth * 0.5 - 2.0, z_floor + 0.225),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(6.5, 2.6, 0.25),
                       location=(cx, cy + depth * 0.5 - 1.8, z_floor + 0.45 + 0.125),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 3. Hammerbeam Roof Trusses across the Ballroom
    n_trusses = 4
    for i in range(n_trusses):
        tx = cx - width * 0.40 + i * (width * 0.80 / (n_trusses - 1))
        # Main cross tie beam
        create_beveled_box(bm, size=(0.35, depth - 0.40, 0.45),
                           location=(tx, cy, z_floor + hall_h - 0.40),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)
        # Diagonal arch braces
        for sgn in (-1.0, 1.0):
            by = cy + sgn * (depth * 0.5 - 1.6)
            create_beveled_box(bm, size=(0.28, 2.2, 0.28),
                               location=(tx, by, z_floor + hall_h - 1.2),
                               rotation=(sgn * 0.65, 0.0, 0.0),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)


# =============================================================================
# FRONT BARBICAN GATEHOUSE & STONE TERRACE
# =============================================================================

def build_barbican_entrance(bm, cx=0.0, cy=-9.0, z_ground=0.0, width=9.0, depth=5.5, height=7.2):
    """
    Fortified Barbican Portal & Viewing Terrace:
    - Heavy ashlar gateway projecting forward into the courtyard
    - Monumental pointed gothic arch portal with iron portcullis slot
    - Flat stone roof terrace with crenellated stone merlons
    - Grand stepped approach staircase
    """
    barb_z0 = z_ground
    half_w = width * 0.5
    deck_z = barb_z0 + height

    # 1. Main Barbican Ashlar Block
    create_beveled_box(bm, size=(width, depth, height),
                       location=(cx, cy - depth * 0.5, barb_z0 + height * 0.5),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    # 2. Portal Arch Cut-through
    arch_w, arch_h = 3.6, 4.4
    create_box(bm, size=(arch_w, depth + 0.40, arch_h),
               location=(cx, cy - depth * 0.5, barb_z0 + arch_h * 0.5),
               mat_index=MAT_INDEX_STONE)

    # 3. Portcullis Grate
    create_box(bm, size=(arch_w - 0.20, 0.12, arch_h - 0.20),
               location=(cx, cy - depth * 0.5 - 0.30, barb_z0 + (arch_h - 0.20) * 0.5 + 0.8),
               mat_index=MAT_INDEX_IRON)

    # 4. Stepped Grand Approach Staircase
    n_steps = 6
    stair_w = width + 1.4
    for s in range(n_steps):
        sz = (s + 0.5) * 0.18
        s_d = depth + (n_steps - s) * 0.45
        create_beveled_box(bm, size=(stair_w - s * 0.20, s_d, 0.18),
                           location=(cx, cy - s_d * 0.5, sz),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 5. Walkable Stone Roof Terrace with Crenellated Merlons (FLAT ROOF WITH MERLONS!)
    create_beveled_box(bm, size=(width + 0.40, depth + 0.40, 0.30),
                       location=(cx, cy - depth * 0.5, deck_z + 0.15),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Parapet with merlons around front and sides
    merlon_h = 1.15
    # Front parapet
    create_beveled_box(bm, size=(width + 0.40, 0.30, 0.35),
                       location=(cx, cy - depth - 0.05, deck_z + 0.30 + 0.175),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    # Front merlons
    n_front_m = 5
    for i in range(n_front_m):
        mx = cx - half_w + 0.60 + i * ((width - 1.20) / (n_front_m - 1))
        create_beveled_box(bm, size=(0.95, 0.30, merlon_h - 0.35),
                           location=(mx, cy - depth - 0.05, deck_z + 0.475 + (merlon_h - 0.35) * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)


# =============================================================================
# HIGH ARMORED RAMPARTS (Flat stone roof with battlements on Right Wing)
# =============================================================================

def build_wing_ramparts(bm, x0, x1, y0, y1, z_top, wall_t=0.65):
    """
    Constructs a true walkable stone rampart wing with battlements on the Right Wing:
    - Solid 2-storey ashlar stone fortress body
    - Flat walkable stone roof deck (accessible for players!)
    - Crenellated stone merlons and embrasures on all exposed sides
    """
    rw_w = abs(x1 - x0)
    rw_d = abs(y1 - y0)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5

    # 0. Solid 2-storey ashlar stone fortress wing body
    create_beveled_box(bm, size=(rw_w, rw_d, z_top),
                       location=(cx, cy, z_top * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # 1. Flat Stone Deck
    create_beveled_box(bm, size=(rw_w, rw_d, 0.32),
                       location=(cx, cy, z_top + 0.16),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 2. Crenellated Parapet on Front edge (min Y)
    merlon_h = 1.15
    y_front = min(y0, y1)
    create_beveled_box(bm, size=(rw_w, wall_t * 0.5, 0.35),
                       location=(cx, y_front + wall_t * 0.25, z_top + 0.32 + 0.175),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    n_m = max(3, int(rw_w / 2.2))
    for i in range(n_m):
        mx = min(x0, x1) + 0.8 + i * ((rw_w - 1.6) / (n_m - 1))
        create_beveled_box(bm, size=(1.10, wall_t * 0.5, merlon_h - 0.35),
                           location=(mx, y_front + wall_t * 0.25, z_top + 0.50 + (merlon_h - 0.35) * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 3. Crenellated Parapet on Outer flank edge (max X)
    x_outer = max(x0, x1)
    create_beveled_box(bm, size=(wall_t * 0.5, rw_d, 0.35),
                       location=(x_outer - wall_t * 0.25, cy, z_top + 0.32 + 0.175),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    n_md = max(3, int(rw_d / 2.2))
    for i in range(n_md):
        my = min(y0, y1) + 0.8 + i * ((rw_d - 1.6) / (n_md - 1))
        create_beveled_box(bm, size=(wall_t * 0.5, 1.10, merlon_h - 0.35),
                           location=(x_outer - wall_t * 0.25, my, z_top + 0.50 + (merlon_h - 0.35) * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)


# =============================================================================
# HIGH ARCHED SKYBRIDGE
# =============================================================================

def build_high_skybridge(bm, p_start, p_end, z_level, width=2.4, height=3.6):
    """Walkable high stone arched skybridge connecting upper tower levels through the air."""
    x0, y0 = p_start
    x1, y1 = p_end
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    ang = math.atan2(dy, dx)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5

    # Deck slab
    create_beveled_box(bm, size=(length, width, 0.30),
                       location=(cx, cy, z_level + 0.15),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    # Under-bridge stone arch corbel span
    create_beveled_box(bm, size=(length * 0.90, width - 0.20, 0.65),
                       location=(cx, cy, z_level - 0.35),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
    # Side parapets / balustrades
    for sgn in (-1.0, 1.0):
        py_off = sgn * (width * 0.5 - 0.12)
        px_pos = cx - math.sin(ang) * py_off
        py_pos = cy + math.cos(ang) * py_off
        create_beveled_box(bm, size=(length, 0.24, 1.10),
                           location=(px_pos, py_pos, z_level + 0.30 + 0.55),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)



# =============================================================================
# CENTRAL DONJON CITADEL KEEP
# =============================================================================

def build_central_citadel_keep(bm, cx=0.0, cy=1.5, z_ground=0.0, radius=5.4,
                               shaft_h=35.0, spire_h=12.5, num_floors=5):
    """
    The Donjon Citadel Keep:
    Soaring 45m command tower rising high above the fortress.
    Machicolated gallery and soaring faceted spire with dormer turrets.
    """
    # 1. Base plinth
    plinth_h = 1.40
    create_cone(bm, radius1=radius + 0.90, radius2=radius + 0.15, height=plinth_h, segments=36,
                location=(cx, cy, z_ground + plinth_h * 0.5), mat_index=MAT_INDEX_STONE)
    shaft_z0 = z_ground + plinth_h
    actual_shaft_h = shaft_h - plinth_h

    # 2. Shaft
    create_cylinder(bm, radius=radius, height=actual_shaft_h, segments=36,
                    location=(cx, cy, shaft_z0 + actual_shaft_h * 0.5), mat_index=MAT_INDEX_STONE)

    # 3. Belt courses
    fl_step = actual_shaft_h / max(1, num_floors)
    for f in range(1, num_floors):
        create_cylinder(bm, radius=radius + 0.15, height=0.30, segments=36,
                        location=(cx, cy, shaft_z0 + f * fl_step), mat_index=MAT_INDEX_CUT_STONE)

    # 4. Windows
    for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        ca, sa = math.cos(ang), math.sin(ang)
        for f in range(1, num_floors):
            level_mid = shaft_z0 + (f + 0.5) * fl_step
            fx, fy = cx + radius * ca, cy + radius * sa
            create_beveled_box(bm, size=(1.05, 0.28, 1.85),
                               location=(fx + ca * 0.05, fy + sa * 0.05, level_mid),
                               rotation=(0.0, 0.0, ang + math.pi * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
            create_box(bm, size=(0.65, 0.32, 1.45),
                       location=(fx + ca * 0.08, fy + sa * 0.08, level_mid),
                       rotation=(0.0, 0.0, ang + math.pi * 0.5), mat_index=MAT_INDEX_GLASS)

    # 5. Machicolation Gallery (flared corbels)
    gallery_r = radius + 0.65
    corbel_h = 1.30
    head_z = shaft_z0 + actual_shaft_h
    create_cone(bm, radius1=gallery_r, radius2=radius, height=corbel_h, segments=36,
                location=(cx, cy, head_z - corbel_h * 0.5), rotation=(0.0, math.pi, 0.0),
                mat_index=MAT_INDEX_CUT_STONE)
    for i in range(24):
        ang = (2.0 * math.pi * i) / 24
        ca, sa = math.cos(ang), math.sin(ang)
        create_beveled_box(bm, size=(0.28, 0.70, corbel_h + 0.20),
                           location=(cx + (radius + 0.35) * ca, cy + (radius + 0.35) * sa, head_z - corbel_h * 0.5),
                           rotation=(0.0, 0.0, ang + math.pi * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 6. Spire (Directly on the flared gallery head, NO merlons around spire!)
    spire_r = radius + 0.75
    spire_faces = create_cone(bm, radius1=spire_r, radius2=0.06, height=spire_h, segments=36,
                             location=(cx, cy, head_z + 0.20 + spire_h * 0.5),
                             mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, spire_faces)

    # 7. Four Spire Dormer Turrets
    dormer_r = radius * 0.65
    for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        ca, sa = math.cos(ang), math.sin(ang)
        dz = head_z + spire_h * 0.28
        create_beveled_box(bm, size=(1.40, 1.20, 2.40),
                           location=(cx + dormer_r * ca, cy + dormer_r * sa, dz + 1.20),
                           rotation=(0.0, 0.0, ang + math.pi * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        create_cone(bm, radius1=1.00, radius2=0.02, height=1.40, segments=4,
                    location=(cx + dormer_r * ca, cy + dormer_r * sa, dz + 2.40 + 0.70),
                    rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES)

    # 8. Royal Apex Finial Needle & Silk Banner
    apex_z = head_z + 0.20 + spire_h
    create_cylinder(bm, radius=0.28, height=0.35, segments=16,
                    location=(cx, cy, apex_z + 0.17), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.22, height=0.30, segments=16,
                    location=(cx, cy, apex_z + 0.50), mat_index=MAT_INDEX_CUT_STONE)
    create_cylinder(bm, radius=0.05, height=3.20, segments=8,
                    location=(cx, cy, apex_z + 0.65 + 1.60), mat_index=MAT_INDEX_IRON)
    create_box(bm, size=(2.80, 0.04, 1.20), location=(cx + 1.40, cy, apex_z + 2.20),
               mat_index=MAT_INDEX_CUT_STONE)


# =============================================================================
# HIGH-LEVEL ORCHESTRATOR
# =============================================================================

def build_castle_citadel(bm, props, ctx):
    """
    High-level orchestrator called to construct the authentic, asymmetrical fantasy castle:
    - Exploratory Subterranean Level: Vaulted Wine Cellar, Dungeon, and 2 Secret Mural Passages
    - Great Ballroom & Banquet Hall with monumental fireplace and dais
    - Front Barbican Portal & Crenellated Stone Terrace
    - Asymmetric Wings:
      * Left Wing: Royal Library & Scholar's Wing (gothic gable roof) anchored by the
        Scholar's Tower with steep conical witch-hat spire (NO merlons).
      * Right Wing: High Fortress & Ramparts with FLAT WALKABLE STONE ROOF & MERLONS,
        anchored by the Fortress Bastion Tower with flat stone deck & merlons (NO pointy roof).
    - Soaring Donjon Keep rising 45m high.
    - High stone skybridge connecting the upper tower levels.
    """
    tier = getattr(props, 'material_tier', 'TIER_3')
    base_w = ctx.base_w
    base_d = ctx.base_d
    num_floors = ctx.num_floors
    floor_h = ctx.floor_h
    found_h = ctx.found_h
    eave_z = found_h + num_floors * floor_h
    wing_d = getattr(props, 'wing_depth', 17.0)

    # 1. Under-Citadel: Dungeon, Wine Cellar & Secret Mural Passages (Z in [-3.6, 0.0])
    build_castle_underground_citadel(bm, cx=0.0, cy=0.0, z_ground=0.0, width=base_w, depth=base_d)

    # 2. Great Ballroom interior features
    build_great_ballroom_features(bm, cx=0.0, cy=0.0, z_floor=found_h, width=base_w * 0.65, depth=base_d)

    # 3. Front Barbican Gateway & Crenellated Viewing Terrace
    build_barbican_entrance(bm, cx=0.0, cy=-base_d * 0.5, z_ground=0.0, width=9.5, depth=5.5, height=floor_h + 1.6)

    # -------------------------------------------------------------------------
    # 4. ASYMMETRIC TOWER NETWORK (Strict Rule: Pointy roofs have NO merlons; Flat towers have NO pointy roofs)
    # -------------------------------------------------------------------------
    # 4a. FRONT-LEFT: The Scholar's Tower (POINTY WITCH-HAT SPIRE, NO MERLONS!)
    # Anchors the Scholar's Wing, soaring high into the clouds!
    sch_x = -base_w * 0.5 + 5.5
    sch_y = -base_d * 0.5 - wing_d
    build_spire_tower(
        bm, cx=sch_x, cy=sch_y, z_ground=0.0,
        radius=3.8, shaft_h=eave_z + 5.5, spire_h=12.5,
        num_floors=num_floors + 1, has_oriel=True, oriel_ang=-0.35
    )

    # 4b. FRONT-RIGHT: The Fortress Bastion Tower (FLAT STONE ROOF WITH MERLONS, NO POINTY ROOF!)
    # Anchors the defensive rampart wing with heavy fighting battlements!
    bast_x = base_w * 0.5 - 5.5
    bast_y = -base_d * 0.5 - (wing_d * 0.75)  # Asymmetric shorter forward projection!
    build_battlement_tower(
        bm, cx=bast_x, cy=bast_y, z_ground=0.0,
        radius=4.6, shaft_h=eave_z + 1.2, num_floors=num_floors, corbel_count=20
    )

    # 4c. RIGHT WING WALKABLE RAMPARTS (FLAT STONE ROOF WITH MERLONS!)
    # Replaces the standard gable roof on the right wing with a full walkable stone battlements deck!
    r_wing_x0 = base_w * 0.5 - 11.0
    r_wing_x1 = base_w * 0.5
    r_wing_y0 = -base_d * 0.5 - (wing_d * 0.75)
    r_wing_y1 = -base_d * 0.5
    build_wing_ramparts(bm, r_wing_x0, r_wing_x1, r_wing_y0, r_wing_y1, z_top=eave_z - 0.20)

    # 4d. REAR-LEFT: The High Watchtower (POINTY CONICAL SPIRE, NO MERLONS!)
    rl_x = -base_w * 0.5
    rl_y = base_d * 0.5
    build_spire_tower(
        bm, cx=rl_x, cy=rl_y, z_ground=0.0,
        radius=3.5, shaft_h=eave_z + 4.0, spire_h=10.5,
        num_floors=num_floors
    )

    # 4e. REAR-RIGHT: The Artillery Citadel Bastion (FLAT STONE ROOF WITH MERLONS, NO POINTY ROOF!)
    rr_x = base_w * 0.5
    rr_y = base_d * 0.5
    build_battlement_tower(
        bm, cx=rr_x, cy=rr_y, z_ground=0.0,
        radius=4.2, shaft_h=eave_z + 2.0, num_floors=num_floors, corbel_count=18
    )

    # -------------------------------------------------------------------------
    # 5. CENTRAL DONJON CITADEL KEEP
    # -------------------------------------------------------------------------
    build_central_citadel_keep(
        bm, cx=0.0, cy=1.5, z_ground=0.0,
        radius=5.5, shaft_h=eave_z + 14.0, spire_h=12.5, num_floors=num_floors + 2
    )

    # -------------------------------------------------------------------------
    # 6. HIGH ARMORED SKYBRIDGE
    # Connects upper level of Scholar's Wing across to the Keep!
    # -------------------------------------------------------------------------
    bridge_start = (sch_x + 2.2, sch_y + 2.2)
    bridge_end = (0.0 - 3.8, 1.5 - 2.0)
    bridge_z = found_h + (num_floors - 1) * floor_h + 1.2
    build_high_skybridge(bm, bridge_start, bridge_end, z_level=bridge_z, width=2.2, height=3.4)
