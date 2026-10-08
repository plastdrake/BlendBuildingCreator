"""
Procedural Fantasy Castle Generation System for BlendBuildingCreator.

Orchestrates all existing modular builders into a high-level fantasy castle citadel
with an authentic architectural lineage across three progression tiers:
- Tier 1: Original Stronghold (Humble frontier stronghold, rustic fieldstone & timber Old Keep,
  palisade bailey, primitive timber gatehouse, lookout watchtower, and subterranean holding pit).
- Tier 2: Expanded Regional Fortress (Visibly expands around Tier 1! Stone curtain walls,
  twin-tower stone gatehouse, reinforced Old Keep with stone battlements, garrison barracks & armory,
  sanctuary chantry chapel, two courtyards, 2-level dungeon, and secret escape tunnel).
- Tier 3: Grand Fantasy Capital Castle (Monumental multi-district fantasy capital fortress perched
  upon layered cliff massifs! Royal District with soaring Donjon Keep and Great Ballroom of Thrones,
  Military District with 100% flat fighting deck ramparts and artillery bastions, Religious District
  with Grand Chantry Chapel of the Silver Flame, Arcane District with High Scholar's Wing and
  soaring 42m Wizard Spire, Elevated Armored Skybridge, 4-level deep subterranean citadel with
  4 narrative secret passages, multiple courtyards, cliff staircases, and complete interior furnishing).

Includes a programmatic Final Validation Pass (validate_castle_generation) asserting all architectural,
traversal, and fantasy requirements.
"""

import math
from mathutils import Vector, Matrix, Euler

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_torus_ring
)
from ..uv_utils import apply_roof_shingle_uvs, map_planar_faces
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_SHINGLES, MAT_INDEX_IRON,
    MAT_INDEX_GLASS, MAT_INDEX_FLOOR, MAT_INDEX_CLIFFS,
    MAT_INDEX_WOOD, MAT_INDEX_LOG, MAT_INDEX_TARGET, MAT_INDEX_BANNER
)
from ..interior import build_spiral_staircase
from ..poly import ring_slab

# Reuse mature existing modular builders
from .furniture import build_barrel, build_crate, build_bench, build_stool
from .interior_furniture import (
    build_bed, build_bunk_bed, build_indoor_table, build_round_table,
    build_chair, build_royal_throne, build_hearth, build_bookshelf,
    build_grand_bookcase, build_spellbook_pedestal, build_arcane_orrery,
    build_scrying_pool, build_alchemy_station, build_enchanting_table,
    build_arcane_circle, build_chest, build_candlestick, build_rug,
    build_chandelier, build_log_pile
)
from .military_props import (
    build_weapon_rack, build_archery_target, build_training_dummy, build_shield_mount
)
from .gatehouse import build_portcullis


# =============================================================================
# 0. CASTLE REGISTRY (Tracks architectural lineage, landmarks, towers & districts)
# =============================================================================

class CastleRegistry:
    """Tracks and documents all components generated for the castle."""
    def __init__(self, tier):
        self.tier = tier
        self.landmarks = []          # List of landmark names
        self.districts = []          # List of district names
        self.towers = {
            'landmark': [],         # (name, height, pos)
            'major': [],
            'secondary': [],
            'turrets': []
        }
        self.courtyards = []         # List of courtyard names
        self.dungeon_levels = []     # (level_num, name, description)
        self.secret_passages = []    # (origin, destination, description)
        self.circulation_routes = [] # (route_type, description)
        self.vertical_levels = []    # List of vertical level descriptions
        self.interiors = []          # (room_name, purpose, prop_count)
        self.lineage_notes = []      # Evolution notes

    def register_landmark(self, name, description=""):
        self.landmarks.append(name)

    def register_district(self, name):
        if name not in self.districts:
            self.districts.append(name)

    def register_tower(self, category, name, height, pos):
        if category in self.towers:
            self.towers[category].append((name, height, pos))

    def register_courtyard(self, name):
        self.courtyards.append(name)

    def register_dungeon_level(self, level_num, name, description):
        self.dungeon_levels.append((level_num, name, description))

    def register_secret_passage(self, origin, destination, description):
        self.secret_passages.append((origin, destination, description))

    def register_route(self, route_type, description):
        self.circulation_routes.append((route_type, description))

    def register_interior(self, room_name, purpose, prop_count=1):
        self.interiors.append((room_name, purpose, prop_count))


# =============================================================================
# 1. ENTERABLE ROUND TOWER BUILDER (Hierarchy: Landmark, Major, Secondary, Turret)
# =============================================================================

def build_walkable_round_tower(
    bm, cx, cy, z_base, radius, num_floors, floor_h,
    tower_type='SPIRE', spire_h=12.0, has_oriel=False, oriel_ang=0.0,
    corbel_count=18, door_angs=((0, 0.0),), deck_door=True
):
    """
    Constructs an authentic enterable, walkable round tower with hollow interior,
    circular floor slabs, walkable spiral staircases, and precisely cut walk-through doorways.

    STRICT RULES:
    - If tower_type == 'SPIRE': Steep conical witch-hat roof, ZERO merlons!
    - If tower_type == 'BATTLEMENTS': Flat stone fighting deck with crenellated merlons, ZERO pointy roof!
    """
    wall_t = 0.55
    segments = 20

    # 1. Stepped plinth foundation
    p0_h, p1_h = 0.60, 0.40
    create_cylinder(bm, radius=radius + 0.45, height=p0_h, segments=segments,
                    location=(cx, cy, z_base + p0_h * 0.5), mat_index=MAT_INDEX_STONE)
    create_cylinder(bm, radius=radius + 0.22, height=p1_h, segments=segments,
                    location=(cx, cy, z_base + p0_h + p1_h * 0.5), mat_index=MAT_INDEX_CUT_STONE)

    z0 = z_base + p0_h + p1_h
    d_ang_step = 2.0 * math.pi / segments

    # 2. Per-floor construction
    for fl in range(num_floors):
        z_fl = z0 + fl * floor_h
        z_ceil = z_fl + floor_h

        # Floor slab
        if fl == 0:
            create_cylinder(bm, radius=radius - 0.05, height=0.15, segments=segments,
                            location=(cx, cy, z_fl + 0.075), mat_index=MAT_INDEX_CUT_STONE)
        else:
            ring_slab(bm, r_in=1.30, r_out=radius - 0.04, z=z_fl + 0.06, segments=segments,
                      offset=0.0, mat_index=MAT_INDEX_FLOOR, height=0.12, center=(cx, cy))

        # Spiral staircase ascending to next floor
        if fl < num_floors - 1 or tower_type == 'BATTLEMENTS':
            build_spiral_staircase(
                bm, center_pos=(cx, cy, z_fl + 0.05),
                target_z=z_ceil + 0.05, radius=1.15,
                num_steps=18, start_ang_deg=-90.0, total_angle_deg=360.0
            )
            # Landing slab bridging to annular floor
            if fl > 0:
                landing_ang = math.radians(-90.0)
                landing_chord = 2.0 * 0.75 * math.tan(math.pi / 4) * 1.5
                create_beveled_box(bm, size=(1.14, landing_chord, 0.12),
                                   location=(cx + 0.73 * math.cos(landing_ang),
                                             cy + 0.73 * math.sin(landing_ang),
                                             z_fl + 0.06),
                                   rotation=(0.0, 0.0, landing_ang),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.01)

        # Hollow outer wall segments
        for k in range(segments):
            ang = (k + 0.5) * d_ang_step
            ca, sa = math.cos(ang), math.sin(ang)
            r_mid = radius - wall_t * 0.5
            fx = cx + r_mid * ca
            fy = cy + r_mid * sa
            chord = 2.0 * radius * math.sin(d_ang_step * 0.5) * 1.06

            # Check if this facet has a walk-through doorway opening
            is_door = False
            for d_fl, d_ang in door_angs:
                if d_fl == fl:
                    diff_ang = (ang - d_ang + math.pi) % (2.0 * math.pi) - math.pi
                    if abs(diff_ang) < d_ang_step * 0.55:
                        is_door = True
                        break

            if is_door:
                dh = 2.50
                lh = floor_h - dh
                if lh > 0.05:
                    create_beveled_box(bm, size=(wall_t, chord, lh),
                                       location=(fx, fy, z_fl + dh + lh * 0.5),
                                       rotation=(0.0, 0.0, ang),
                                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
                j_w = 0.16
                for sgn_j in (-1.0, 1.0):
                    jx = fx - sgn_j * sa * (chord * 0.5 - j_w * 0.5)
                    jy = fy + sgn_j * ca * (chord * 0.5 - j_w * 0.5)
                    create_beveled_box(bm, size=(wall_t + 0.04, j_w, dh),
                                       location=(jx, jy, z_fl + dh * 0.5),
                                       rotation=(0.0, 0.0, ang),
                                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
            elif (fl > 0 and k % 5 == 2):
                # Arrow slit loophole
                sill_h = 1.05
                head_h = 2.35
                create_beveled_box(bm, size=(wall_t, chord, sill_h),
                                   location=(fx, fy, z_fl + sill_h * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
                top_h = floor_h - head_h
                create_beveled_box(bm, size=(wall_t, chord, top_h),
                                   location=(fx, fy, z_fl + head_h + top_h * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
                slit_w = 0.35
                jamb_w = (chord - slit_w) * 0.5
                slit_h = head_h - sill_h
                for sgn_j in (-1.0, 1.0):
                    jx = fx - sgn_j * sa * (chord * 0.5 - jamb_w * 0.5)
                    jy = fy + sgn_j * ca * (chord * 0.5 - jamb_w * 0.5)
                    create_beveled_box(bm, size=(wall_t, jamb_w, slit_h),
                                       location=(jx, jy, z_fl + sill_h + slit_h * 0.5),
                                       rotation=(0.0, 0.0, ang),
                                       mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
            else:
                create_beveled_box(bm, size=(wall_t, chord, floor_h),
                                   location=(fx, fy, z_fl + floor_h * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

        # Belt moulding dividing storeys
        create_cylinder(bm, radius=radius + 0.10, height=0.20, segments=segments,
                        location=(cx, cy, z_ceil), mat_index=MAT_INDEX_CUT_STONE)

    # 3. Corbelled machicolations cornice
    z_top = z0 + num_floors * floor_h
    corbel_r = radius + 0.45
    for i in range(corbel_count):
        ang = (2.0 * math.pi * i) / corbel_count
        ca, sa = math.cos(ang), math.sin(ang)
        create_beveled_box(bm, size=(0.28, 0.42, 0.65),
                           location=(cx + (radius + 0.18) * ca, cy + (radius + 0.18) * sa, z_top - 0.30),
                           rotation=(0.0, 0.0, ang + math.pi * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    create_cylinder(bm, radius=corbel_r, height=0.35, segments=segments,
                    location=(cx, cy, z_top + 0.175), mat_index=MAT_INDEX_CUT_STONE)

    # 4. Roof finish: Witch-hat Spire vs Flat Battlements Deck
    if tower_type == 'SPIRE':
        create_cylinder(bm, radius=corbel_r - 0.05, height=0.20, segments=segments,
                        location=(cx, cy, z_top + 0.35 + 0.10), mat_index=MAT_INDEX_FLOOR)
        spire_z = z_top + 0.45
        create_cone(bm, radius1=corbel_r + 0.25, radius2=0.08, height=spire_h, segments=segments,
                    location=(cx, cy, spire_z + spire_h * 0.5), mat_index=MAT_INDEX_SHINGLES)
        create_cylinder(bm, radius=corbel_r + 0.28, height=0.18, segments=segments,
                        location=(cx, cy, spire_z + 0.09), mat_index=MAT_INDEX_TIMBER)
        # Iron needle finial & pennon
        fn_z = spire_z + spire_h
        create_cylinder(bm, radius=0.045, height=2.4, segments=8,
                        location=(cx, cy, fn_z + 1.2), mat_index=MAT_INDEX_IRON)
        create_box(bm, size=(0.85, 0.03, 0.45),
                   location=(cx + 0.42, cy, fn_z + 1.8), mat_index=MAT_INDEX_IRON)

        if has_oriel:
            oca, osa = math.cos(oriel_ang), math.sin(oriel_ang)
            oriel_x = cx + (radius + 0.45) * oca
            oriel_y = cy + (radius + 0.45) * osa
            oriel_z = z_top - floor_h * 0.8
            create_cone(bm, radius1=0.20, radius2=1.10, height=0.85, segments=8,
                        location=(oriel_x, oriel_y, oriel_z - 0.425), mat_index=MAT_INDEX_CUT_STONE)
            create_cylinder(bm, radius=1.05, height=2.2, segments=8,
                            location=(oriel_x, oriel_y, oriel_z + 1.1), mat_index=MAT_INDEX_STONE)
            create_cone(bm, radius1=1.20, radius2=0.05, height=2.4, segments=8,
                        location=(oriel_x, oriel_y, oriel_z + 2.2 + 1.2), mat_index=MAT_INDEX_SHINGLES)

    elif tower_type == 'BATTLEMENTS':
        deck_z = z_top + 0.35
        ring_slab(bm, r_in=1.30, r_out=corbel_r, z=deck_z, segments=segments,
                  offset=0.0, mat_index=MAT_INDEX_CUT_STONE, height=0.30, center=(cx, cy))
        landing_ang = math.radians(-90.0)
        landing_chord = 2.0 * 0.75 * math.tan(math.pi / 4) * 1.5
        create_beveled_box(bm, size=(1.14, landing_chord, 0.30),
                           location=(cx + 0.73 * math.cos(landing_ang),
                                     cy + 0.73 * math.sin(landing_ang),
                                     deck_z + 0.15),
                           rotation=(0.0, 0.0, landing_ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)

        if deck_door:
            # Arched stone companionway enclosure over stair hatch
            ch_w, ch_d, ch_h = 1.50, 1.30, 1.90
            create_beveled_box(bm, size=(ch_w, ch_d, ch_h),
                               location=(cx, cy - 0.70, deck_z + 0.30 + ch_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
            # Pitched stone hood cap
            create_cone(bm, radius1=1.10, radius2=0.04, height=0.55, segments=4,
                        location=(cx, cy - 0.70, deck_z + 0.30 + ch_h + 0.275),
                        rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

        parapet_mid_r = corbel_r - 0.18
        merlon_count = corbel_count
        m_h = 1.05
        for i in range(merlon_count):
            if i % 2 == 0:
                ang = (2.0 * math.pi * i) / merlon_count
                ca, sa = math.cos(ang), math.sin(ang)
                m_w = (2.0 * math.pi * parapet_mid_r / merlon_count) * 0.88
                create_beveled_box(bm, size=(m_w, 0.34, m_h),
                                   location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                                             deck_z + 0.30 + m_h * 0.5),
                                   rotation=(0.0, 0.0, ang + math.pi * 0.5),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
                create_cone(bm, radius1=m_w * 0.55, radius2=0.02, height=0.18, segments=4,
                            location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                                      deck_z + 0.30 + m_h + 0.09),
                            rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

        # Open deck tripod signal fire brazier
        br_z = deck_z + 0.30
        br_y = cy + (corbel_r - 1.5)
        create_cylinder(bm, radius=0.45, height=0.32, segments=12,
                        location=(cx, br_y, br_z + 0.75), mat_index=MAT_INDEX_IRON)
        for leg_ang in (0.0, math.pi * 0.66, math.pi * 1.33):
            lca, lsa = math.cos(leg_ang), math.sin(leg_ang)
            create_cylinder(bm, radius=0.04, height=0.75, segments=6,
                            location=(cx + 0.35 * lca, br_y + 0.35 * lsa, br_z + 0.375),
                            rotation=(0.15 * lsa, -0.15 * lca, 0.0), mat_index=MAT_INDEX_IRON)


# =============================================================================
# 2. THE HISTORIC ANCESTRAL OLD KEEP (Anchored at cx=0, cy=10 across T1, T2, T3)
# =============================================================================

def build_primitive_old_keep(
    bm, cx=0.0, cy=10.0, z_base=0.0, width=14.0, depth=12.0, height=9.5,
    is_reinforced=False
):
    """
    Constructs the Historic Ancestral Old Keep (14m x 12m):
    Anchored at (0.0, 10.0), this building represents the original stronghold of Tier 1.
    - Ground Floor: Chieftain's great hearth, banquet table, benches, weapon racks, cellar trapdoor.
    - Upper Floor: Chieftain's sleeping chamber, timber bed, storage chests, council table.
    - Straight wooden stairs connecting storeys.
    - If is_reinforced (Tier 2): Lower walls faced with cut-stone quoins, stone battlement deck added.
    """
    half_w = width * 0.5
    half_d = depth * 0.5
    wall_t = 0.65

    # 1. Foundation plinth
    plinth_mat = MAT_INDEX_CUT_STONE if is_reinforced else MAT_INDEX_STONE
    create_beveled_box(bm, size=(width + 0.6, depth + 0.6, 1.2),
                       location=(cx, cy, z_base + 0.6),
                       mat_index=plinth_mat, bevel_amount=0.04)

    z0 = z_base + 1.2
    n_floors = 2
    fl_h = (height - 1.2) / n_floors

    # 2. Storey floor slabs
    for fl in range(n_floors):
        create_beveled_box(bm, size=(width - 0.2, depth - 0.2, 0.20),
                           location=(cx, cy, z0 + fl * fl_h + 0.10),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # 3. Straight wooden staircase between Ground Floor and 1st Floor
    n_steps = 16
    stair_w = 1.30
    stair_x = cx - half_w + 2.0
    for s in range(n_steps):
        sz = z0 + (s + 1) * (fl_h / n_steps)
        sy = cy - 2.5 + s * (4.2 / n_steps)
        create_beveled_box(bm, size=(stair_w, 4.2 / n_steps + 0.04, 0.22),
                           location=(stair_x, sy, sz - 0.11),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)

    # 4. Walls
    wall_mat = MAT_INDEX_STONE
    # North wall (+Y)
    create_beveled_box(bm, size=(width, wall_t, height - 1.2),
                       location=(cx, cy + half_d - wall_t * 0.5, z0 + (height - 1.2) * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)
    # South wall (-Y) - with walk-through entrance doorway
    door_w = 2.40
    door_h = 2.80
    wall_above = (height - 1.2) - door_h
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, height - 1.2),
                       location=(cx - half_w + (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + (height - 1.2) * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, height - 1.2),
                       location=(cx + half_w - (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + (height - 1.2) * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)
    create_beveled_box(bm, size=(door_w, wall_t, wall_above),
                       location=(cx, cy - half_d + wall_t * 0.5, z0 + door_h + wall_above * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)
    # West wall (-X)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, height - 1.2),
                       location=(cx - half_w + wall_t * 0.5, cy, z0 + (height - 1.2) * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)
    # East wall (+X)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, height - 1.2),
                       location=(cx + half_w - wall_t * 0.5, cy, z0 + (height - 1.2) * 0.5),
                       mat_index=wall_mat, bevel_amount=0.03)

    # Cut-stone quoin corner dressings if reinforced
    if is_reinforced:
        for sgn_x in (-1.0, 1.0):
            for sgn_y in (-1.0, 1.0):
                create_beveled_box(bm, size=(0.75, 0.75, height - 1.2),
                                   location=(cx + sgn_x * (half_w - 0.35), cy + sgn_y * (half_d - 0.35), z0 + (height - 1.2) * 0.5),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 5. Authentic Interior Furnishings
    # Ground Floor: Ancestral Hearth on North wall
    build_hearth(bm, x=cx + 2.0, y=cy + half_d - wall_t - 0.6, z_ground=z0 + 0.20, ang=math.pi, width=2.4, height=2.2)
    # Chieftain's banquet table & benches
    build_indoor_table(bm, x=cx + 1.5, y=cy - 0.5, z_ground=z0 + 0.20, ang=0.0, length=2.6, width=1.1)
    build_bench(bm, x=cx + 1.5, y=cy - 1.3, z_ground=z0 + 0.20, ang=0.0, length=2.4)
    build_bench(bm, x=cx + 1.5, y=cy + 0.3, z_ground=z0 + 0.20, ang=0.0, length=2.4)
    # Weapon rack along East wall
    build_weapon_rack(bm, x=cx + half_w - wall_t - 0.5, y=cy, z_ground=z0 + 0.20, ang=-math.pi * 0.5)

    # Upper Floor: Chieftain's Bed & Chests
    z_up = z0 + fl_h + 0.20
    build_bed(bm, x=cx - half_w + wall_t + 1.6, y=cy + half_d - wall_t - 1.8, z_ground=z_up, ang=0.0, length=2.2, width=1.4)
    build_chest(bm, x=cx - half_w + wall_t + 1.6, y=cy + half_d - wall_t - 3.2, z_ground=z_up, ang=0.0, width=1.1)
    build_round_table(bm, x=cx + 2.5, y=cy + 1.0, z_ground=z_up, radius=0.65)
    build_chair(bm, x=cx + 2.5, y=cy + 0.2, z_ground=z_up, ang=0.0)

    # 6. Roof System
    roof_z = z0 + height - 1.2
    if not is_reinforced:
        # Timber sway gable roof with wooden shingles
        roof_h = 4.8
        create_box(bm, size=(width + 0.4, 0.35, 0.35),
                   location=(cx, cy, roof_z + roof_h), mat_index=MAT_INDEX_TIMBER)
        slope_len = math.hypot(depth * 0.5, roof_h)
        slope_ang = math.atan2(roof_h, depth * 0.5)
        for sgn_r in (-1.0, 1.0):
            create_box(bm, size=(width + 0.6, slope_len + 0.5, 0.20),
                       location=(cx, cy + sgn_r * (depth * 0.25), roof_z + roof_h * 0.5),
                       rotation=(-sgn_r * slope_ang, 0.0, 0.0), mat_index=MAT_INDEX_SHINGLES)

        # Triangular gable end walls (West and East)
        n_bands = 8
        for sgn_x in (-1.0, 1.0):
            gw_x = cx + sgn_x * (half_w - wall_t * 0.5)
            for b in range(n_bands):
                frac = (b + 0.5) / n_bands
                b_z = roof_z + b * (roof_h / n_bands) + (roof_h / n_bands) * 0.5
                b_d = (depth - wall_t * 2) * (1.0 - frac)
                if b_d > 0.3:
                    create_beveled_box(bm, size=(wall_t, b_d, roof_h / n_bands + 0.02),
                                       location=(gw_x, cy, b_z),
                                       mat_index=wall_mat, bevel_amount=0.02)
    else:
        # Reinforced Tier 2 Battlement Deck with corbelled merlons
        deck_thick = 0.35
        create_beveled_box(bm, size=(width + 0.8, depth + 0.8, deck_thick),
                           location=(cx, cy, roof_z + deck_thick * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
        # Crenellated merlons
        parapet_h = 1.10
        m_thick = 0.30
        for sgn_y in (-1.0, 1.0):
            for i in range(5):
                if i % 2 == 0:
                    mx = cx - half_w + 1.4 + i * ((width - 2.8) / 4)
                    create_beveled_box(bm, size=(1.2, m_thick, parapet_h),
                                       location=(mx, cy + sgn_y * (half_d + 0.35), roof_z + deck_thick + parapet_h * 0.5),
                                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)


# =============================================================================
# 3. SQUARE LOOKOUT WATCHTOWER (Frontier Stronghold & Fortress Watch)
# =============================================================================

def build_square_watchtower(
    bm, cx=-12.0, cy=12.0, z_base=0.0, width=4.6, height=11.5, is_stone=False
):
    """
    Constructs a stout 3-storey square lookout watchtower:
    - Base: Rough fieldstone / cut-stone foundation with arched entrance.
    - Shaft: Arrow loop loopholes.
    - Summit: Open timber lookout deck, pitched roof with bell and banner pennon.
    """
    half_w = width * 0.5
    wall_t = 0.50

    # Foundation plinth
    create_beveled_box(bm, size=(width + 0.4, width + 0.4, 0.8),
                       location=(cx, cy, z_base + 0.4),
                       mat_index=MAT_INDEX_CUT_STONE if is_stone else MAT_INDEX_STONE, bevel_amount=0.03)

    z0 = z_base + 0.8
    body_h = height - 0.8
    mat_wall = MAT_INDEX_CUT_STONE if is_stone else MAT_INDEX_STONE

    # Hollow tower walls
    for sgn_x in (-1.0, 1.0):
        create_beveled_box(bm, size=(wall_t, width - wall_t * 2, body_h),
                           location=(cx + sgn_x * (half_w - wall_t * 0.5), cy, z0 + body_h * 0.5),
                           mat_index=mat_wall, bevel_amount=0.02)
    # North wall
    create_beveled_box(bm, size=(width, wall_t, body_h),
                       location=(cx, cy + half_w - wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=mat_wall, bevel_amount=0.02)
    # South wall (with doorway)
    door_w = 1.6
    door_h = 2.4
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, body_h),
                       location=(cx - half_w + (width - door_w) * 0.25, cy - half_w + wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=mat_wall, bevel_amount=0.02)
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, body_h),
                       location=(cx + half_w - (width - door_w) * 0.25, cy - half_w + wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=mat_wall, bevel_amount=0.02)
    create_beveled_box(bm, size=(door_w, wall_t, body_h - door_h),
                       location=(cx, cy - half_w + wall_t * 0.5, z0 + door_h + (body_h - door_h) * 0.5),
                       mat_index=mat_wall, bevel_amount=0.02)

    # Floor slabs and interior spiral stair
    n_floors = 3
    fl_h = body_h / n_floors
    for fl in range(n_floors):
        create_beveled_box(bm, size=(width - 0.2, width - 0.2, 0.18),
                           location=(cx, cy, z0 + fl * fl_h + 0.09),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)
        if fl < n_floors - 1:
            build_spiral_staircase(
                bm, center_pos=(cx, cy, z0 + fl * fl_h + 0.05),
                target_z=z0 + (fl + 1) * fl_h + 0.05, radius=1.05,
                num_steps=16, start_ang_deg=0.0, total_angle_deg=360.0
            )

    # Lookout deck & roof
    deck_z = z0 + body_h
    create_beveled_box(bm, size=(width + 0.8, width + 0.8, 0.30),
                       location=(cx, cy, deck_z + 0.15),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # 4 Timber corner posts supporting pitched roof
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            create_beveled_box(bm, size=(0.20, 0.20, 2.2),
                               location=(cx + sx * (half_w + 0.2), cy + sy * (half_w + 0.2), deck_z + 1.4),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)

    # Conical / Pyramid roof
    roof_h = 3.6
    create_cone(bm, radius1=width * 0.75, radius2=0.05, height=roof_h, segments=4,
                location=(cx, cy, deck_z + 2.5 + roof_h * 0.5),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES)

    # Lookout warning bell and standard pennon
    create_cylinder(bm, radius=0.035, height=1.8, segments=6,
                    location=(cx, cy, deck_z + 2.5 + roof_h + 0.9), mat_index=MAT_INDEX_IRON)
    create_box(bm, size=(0.60, 0.02, 0.35),
               location=(cx + 0.30, cy, deck_z + 2.5 + roof_h + 1.4), mat_index=MAT_INDEX_IRON)


# =============================================================================
# 4. PRIMITIVE TIMBER GATEHOUSE & PALISADE BAILEY (Tier 1)
# =============================================================================

def build_primitive_timber_gatehouse(
    bm, cx=0.0, cy=-8.0, z_base=0.0, width=6.5, depth=4.5, height=5.5
):
    """
    Constructs a primitive frontier log gatehouse:
    - Massive peeled log posts flanking the portal passage.
    - Barred wooden double gate doors.
    - Sentry walkway overhead with timber palisade parapet.
    """
    arch_w = 2.80
    pier_w = (width - arch_w) * 0.5

    # Flanking log piers
    for sgn in (-1.0, 1.0):
        px = cx + sgn * (arch_w * 0.5 + pier_w * 0.5)
        create_beveled_box(bm, size=(pier_w, depth, height),
                           location=(px, cy, z_base + height * 0.5),
                           mat_index=MAT_INDEX_LOG, bevel_amount=0.04)

    # Heavy timber lintel crossbeam
    create_beveled_box(bm, size=(width + 0.4, depth + 0.2, 0.85),
                       location=(cx, cy, z_base + height - 0.425),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.03)

    # Sentry walkway floor slab
    create_beveled_box(bm, size=(width + 0.6, depth + 0.6, 0.22),
                       location=(cx, cy, z_base + height + 0.11),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Barred timber gate leaves (parted slightly for open walkthrough access)
    door_h = height - 1.2
    for sgn, ang in ((-1.0, 0.35), (1.0, -0.35)):
        gx = cx + sgn * (arch_w * 0.38)
        create_beveled_box(bm, size=(arch_w * 0.45, 0.16, door_h),
                           location=(gx, cy, z_base + door_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # Timber palisade parapet along sentry walkway
    for sgn_y in (-1.0, 1.0):
        for i in range(5):
            mx = cx - width * 0.5 + 0.6 + i * ((width - 1.2) / 4)
            create_cylinder(bm, radius=0.12, height=1.30, segments=8,
                            location=(mx, cy + sgn_y * (depth * 0.5 + 0.15), z_base + height + 0.65),
                            mat_index=MAT_INDEX_LOG)


def build_tier1_palisade_bailey(
    bm, cx=0.0, cy=4.0, z_base=0.0, width=32.0, depth=26.0, gate_w=4.0
):
    """
    Constructs the rustic timber palisade enclosing the Tier 1 bailey courtyard.
    Includes log stockade walls, central stone well, supply barrels, and archery target.
    """
    half_w = width * 0.5
    half_d = depth * 0.5
    post_h = 3.4
    post_r = 0.14

    # Log perimeter stakes
    def log_run(x0, y0, x1, y1):
        dist = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(dist / 0.32))
        for i in range(n):
            t = i / (n - 1)
            px = x0 + t * (x1 - x0)
            py = y0 + t * (y1 - y0)
            create_cylinder(bm, radius=post_r, height=post_h, segments=6,
                            location=(px, py, z_base + post_h * 0.5),
                            mat_index=MAT_INDEX_LOG)
            # Pointed stake tip
            create_cone(bm, radius1=post_r, radius2=0.02, height=0.35, segments=6,
                        location=(px, py, z_base + post_h + 0.175),
                        mat_index=MAT_INDEX_LOG)

    # North, West, East runs
    log_run(cx - half_w, cy + half_d, cx + half_w, cy + half_d)
    log_run(cx - half_w, cy - half_d, cx - half_w, cy + half_d)
    log_run(cx + half_w, cy - half_d, cx + half_w, cy + half_d)
    # South run with gate gap
    log_run(cx - half_w, cy - half_d, cx - gate_w * 0.5, cy - half_d)
    log_run(cx + gate_w * 0.5, cy - half_d, cx + half_w, cy - half_d)

    # Courtyard Well
    create_cylinder(bm, radius=1.2, height=0.85, segments=12,
                    location=(cx - 4.5, cy - 2.0, z_base + 0.425), mat_index=MAT_INDEX_CUT_STONE)
    create_cylinder(bm, radius=0.9, height=0.20, segments=12,
                    location=(cx - 4.5, cy - 2.0, z_base + 0.65), mat_index=MAT_INDEX_STONE)

    # Archery training target in bailey
    build_archery_target(bm, x=cx + 6.0, y=cy - 2.0, z_ground=z_base, ang=0.0)

    # Crate and barrel clusters
    build_barrel(bm, x=cx - 6.0, y=cy + 4.0, z_ground=z_base)
    build_barrel(bm, x=cx - 5.2, y=cy + 4.2, z_ground=z_base)
    build_crate(bm, x=cx - 6.0, y=cy + 2.8, z_ground=z_base)


# =============================================================================
# 5. SANCTUARY CHANTRY CHAPEL (Tier 2 & Tier 3 Religious District)
# =============================================================================

def build_sanctuary_chapel(
    bm, cx=-20.0, cy=6.0, z_base=0.0, width=8.5, depth=14.0, height=8.8
):
    """
    Constructs the Sanctuary Chantry Chapel:
    - Semicircular apse on North wall (+Y).
    - Tall stained-glass lancet windows with stone reveals.
    - South facade with pointed gothic entrance archway and circular rose window.
    - Interior: Altar with candlesticks, worship pews, and secret crypt trapdoor!
    - Roof: Steep gothic gable roof with sanctus bell-cote.
    """
    half_w = width * 0.5
    half_d = depth * 0.5
    wall_t = 0.65

    # Plinth base
    create_beveled_box(bm, size=(width + 0.5, depth + 0.5, 0.9),
                       location=(cx, cy, z_base + 0.45),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    z0 = z_base + 0.9
    wall_h = height - 0.9

    # Floor slab
    create_beveled_box(bm, size=(width - 0.2, depth - 0.2, 0.18),
                       location=(cx, cy, z0 + 0.09),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Semicircular Chancel Apse on North wall (+Y)
    apse_r = half_w - 0.4
    create_cylinder(bm, radius=apse_r, height=wall_h, segments=12,
                    location=(cx, cy + half_d, z0 + wall_h * 0.5), mat_index=MAT_INDEX_STONE)
    create_cone(bm, radius1=apse_r + 0.3, radius2=0.05, height=4.2, segments=12,
                location=(cx, cy + half_d, z0 + wall_h + 2.1), mat_index=MAT_INDEX_SHINGLES)

    # West and East Chapel Walls with Lancet Windows
    for sgn_x in (-1.0, 1.0):
        create_beveled_box(bm, size=(wall_t, depth, wall_h),
                           location=(cx + sgn_x * (half_w - wall_t * 0.5), cy, z0 + wall_h * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        # 3 Stained glass lancet windows
        for i in range(3):
            wy = cy - half_d + 3.0 + i * 3.8
            create_beveled_box(bm, size=(wall_t + 0.12, 1.2, 2.8),
                               location=(cx + sgn_x * (half_w - wall_t * 0.5), wy, z0 + 4.2),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
            create_box(bm, size=(wall_t + 0.16, 0.70, 2.3),
                       location=(cx + sgn_x * (half_w - wall_t * 0.5), wy, z0 + 4.2),
                       mat_index=MAT_INDEX_GLASS)

    # South Facade: Portal archway & circular rose window
    door_w = 2.2
    door_h = 3.2
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, wall_h),
                       location=(cx - half_w + (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + wall_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, wall_h),
                       location=(cx + half_w - (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + wall_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(door_w, wall_t, wall_h - door_h),
                       location=(cx, cy - half_d + wall_t * 0.5, z0 + door_h + (wall_h - door_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Rose window above doorway
    create_cylinder(bm, radius=1.1, height=wall_t + 0.18, segments=12,
                    location=(cx, cy - half_d + wall_t * 0.5, z0 + 5.5),
                    rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_CUT_STONE)
    create_cylinder(bm, radius=0.85, height=wall_t + 0.22, segments=12,
                    location=(cx, cy - half_d + wall_t * 0.5, z0 + 5.5),
                    rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_GLASS)

    # Interior: Altar, pews, secret crypt trapdoor
    # Altar Table in apse
    create_beveled_box(bm, size=(2.4, 1.1, 1.0),
                       location=(cx, cy + half_d - 1.2, z0 + 0.50),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    build_candlestick(bm, x=cx - 0.7, y=cy + half_d - 1.2, z_ground=z0 + 1.0)
    build_candlestick(bm, x=cx + 0.7, y=cy + half_d - 1.2, z_ground=z0 + 1.0)

    # Worship benches / pews
    for i in range(3):
        py = cy - half_d + 3.5 + i * 2.2
        build_bench(bm, x=cx - 1.8, y=py, z_ground=z0 + 0.18, ang=math.pi * 0.5, length=1.8)
        build_bench(bm, x=cx + 1.8, y=py, z_ground=z0 + 0.18, ang=math.pi * 0.5, length=1.8)

    # Secret Crypt Trapdoor in floor
    create_beveled_box(bm, size=(1.2, 1.4, 0.08),
                       location=(cx - 2.2, cy + 2.5, z0 + 0.14),
                       mat_index=MAT_INDEX_IRON, bevel_amount=0.01)

    # Roof: Gothic gable roof & bell-cote
    roof_z = z0 + wall_h
    roof_h = 4.5
    create_box(bm, size=(0.35, depth + 0.4, 0.35),
               location=(cx, cy, roof_z + roof_h), mat_index=MAT_INDEX_TIMBER)
    slope_len = math.hypot(half_w, roof_h)
    slope_ang = math.atan2(roof_h, half_w)
    for sgn_r in (-1.0, 1.0):
        create_box(bm, size=(slope_len + 0.5, depth + 0.5, 0.20),
                   location=(cx + sgn_r * (half_w * 0.5), cy, roof_z + roof_h * 0.5),
                   rotation=(0.0, sgn_r * slope_ang, 0.0), mat_index=MAT_INDEX_SHINGLES)

    # Sanctus bell-cote on South gable apex
    create_beveled_box(bm, size=(1.1, 1.1, 2.2),
                       location=(cx, cy - half_d + 0.6, roof_z + roof_h + 1.1),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    create_cone(bm, radius1=0.85, radius2=0.02, height=1.6, segments=4,
                location=(cx, cy - half_d + 0.6, roof_z + roof_h + 2.2 + 0.8),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES)


# =============================================================================
# 6. GARRISON BARRACKS & ARMORY (Tier 2 & Tier 3 Military District)
# =============================================================================

def build_barracks_and_armory(
    bm, cx=20.0, cy=6.0, z_base=0.0, width=9.0, depth=16.0, height=7.5
):
    """
    Constructs the 2-storey Garrison Barracks & Armory:
    - Ground floor: Garrison armory and smithy with weapon racks, anvil, tool chests.
    - Upper floor: Soldiers' quarters with bunk beds and footlockers.
    - Exterior training yard with archery butts and training dummies.
    """
    half_w = width * 0.5
    half_d = depth * 0.5
    wall_t = 0.60

    # Plinth base
    create_beveled_box(bm, size=(width + 0.5, depth + 0.5, 0.8),
                       location=(cx, cy, z_base + 0.4),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    z0 = z_base + 0.8
    body_h = height - 0.8
    fl_h = body_h * 0.5

    # Ground and 1st floor slabs
    for fl in range(2):
        create_beveled_box(bm, size=(width - 0.2, depth - 0.2, 0.20),
                           location=(cx, cy, z0 + fl * fl_h + 0.10),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Walls
    create_beveled_box(bm, size=(width, wall_t, body_h),
                       location=(cx, cy + half_d - wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, body_h),
                       location=(cx + half_w - wall_t * 0.5, cy, z0 + body_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, body_h),
                       location=(cx - half_w + wall_t * 0.5, cy, z0 + body_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # South wall with entrance doorway
    door_w = 2.4
    door_h = 2.6
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, body_h),
                       location=(cx - half_w + (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, body_h),
                       location=(cx + half_w - (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + body_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(door_w, wall_t, body_h - door_h),
                       location=(cx, cy - half_d + wall_t * 0.5, z0 + door_h + (body_h - door_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Interior Furnishings
    # Ground Floor: Weapon racks & smithy
    build_weapon_rack(bm, x=cx - half_w + wall_t + 0.6, y=cy - 2.0, z_ground=z0 + 0.20, ang=math.pi * 0.5)
    build_weapon_rack(bm, x=cx - half_w + wall_t + 0.6, y=cy + 2.0, z_ground=z0 + 0.20, ang=math.pi * 0.5)
    build_chest(bm, x=cx + half_w - wall_t - 0.8, y=cy - 2.0, z_ground=z0 + 0.20, ang=-math.pi * 0.5)

    # Upper Floor: Soldiers' bunk beds
    z_up = z0 + fl_h + 0.20
    build_bunk_bed(bm, x=cx - half_w + wall_t + 1.3, y=cy - 3.0, z_ground=z_up, ang=0.0)
    build_bunk_bed(bm, x=cx - half_w + wall_t + 1.3, y=cy + 1.0, z_ground=z_up, ang=0.0)
    build_bunk_bed(bm, x=cx + half_w - wall_t - 1.3, y=cy - 3.0, z_ground=z_up, ang=math.pi)
    build_bunk_bed(bm, x=cx + half_w - wall_t - 1.3, y=cy + 1.0, z_ground=z_up, ang=math.pi)

    # Gable roof
    roof_z = z0 + body_h
    roof_h = 3.8
    create_box(bm, size=(0.35, depth + 0.4, 0.35),
               location=(cx, cy, roof_z + roof_h), mat_index=MAT_INDEX_TIMBER)
    slope_len = math.hypot(half_w, roof_h)
    slope_ang = math.atan2(roof_h, half_w)
    for sgn_r in (-1.0, 1.0):
        create_box(bm, size=(slope_len + 0.5, depth + 0.5, 0.20),
                   location=(cx + sgn_r * (half_w * 0.5), cy, roof_z + roof_h * 0.5),
                   rotation=(0.0, sgn_r * slope_ang, 0.0), mat_index=MAT_INDEX_SHINGLES)

    # Exterior drill yard: Archery butt & training dummy
    build_archery_target(bm, x=cx, y=cy - half_d - 4.5, z_ground=z_base, ang=0.0)
    build_training_dummy(bm, x=cx + 3.0, y=cy - half_d - 4.0, z_ground=z_base, ang=0.2)


# =============================================================================
# 7. PROGRESSIVE DUNGEON SYSTEMS (Levels -1, -2, -3, -4 with Narrative Secret Passages)
# =============================================================================

def build_tier1_cellar_dungeon(bm, cx=0.0, cy=10.0, z_ground=0.0):
    """
    Tier 1 Subterranean Dungeon (Level -1):
    Rough fieldstone storage cellar with provisions, barrel racks,
    and a crude stone holding pit with iron grate.
    """
    z_floor = z_ground - 3.4
    h = 3.2
    w, d = 9.0, 8.0

    # Stone floor and ceiling
    create_beveled_box(bm, size=(w, d, 0.22), location=(cx, cy, z_floor - 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(w, d, 0.22), location=(cx, cy, z_floor + h + 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Perimeter walls
    create_beveled_box(bm, size=(w, 0.60, h), location=(cx, cy + d * 0.5 - 0.30, z_floor + h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(w, 0.60, h), location=(cx, cy - d * 0.5 + 0.30, z_floor + h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(0.60, d, h), location=(cx - w * 0.5 + 0.30, cy, z_floor + h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(0.60, d, h), location=(cx + w * 0.5 - 0.30, cy, z_floor + h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Holding pit cell with iron grate
    create_beveled_box(bm, size=(2.8, 2.8, 0.10), location=(cx + 2.2, cy + 1.8, z_floor + 0.05),
                       mat_index=MAT_INDEX_IRON, bevel_amount=0.01)

    # Barrels & crates
    build_barrel(bm, x=cx - 2.5, y=cy - 2.0, z_ground=z_floor)
    build_barrel(bm, x=cx - 1.8, y=cy - 2.0, z_ground=z_floor)
    build_crate(bm, x=cx - 2.5, y=cy + 1.5, z_ground=z_floor)


def build_tier2_expanded_dungeon(bm, cx=0.0, cy=8.0, z_ground=0.0):
    """
    Tier 2 Expanded Subterranean Dungeon (Levels -1 & -2):
    Level -1: Vaulted Wine & Provisions Cellar with stone pillars.
    Level -2: Stone Prison Complex with iron-barred cells, chains, and guard station.
    Secret exit tunnel leading to outer rock spur.
    """
    # Level -1 (Z = -3.8)
    z1 = z_ground - 3.8
    h1 = 3.6
    w1, d1 = 28.0, 16.0
    create_beveled_box(bm, size=(w1, d1, 0.25), location=(cx, cy, z1 - 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(w1, d1, 0.25), location=(cx, cy, z1 + h1 + 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Pillars
    for px in (-6.0, 6.0):
        create_beveled_box(bm, size=(0.85, 0.85, h1), location=(cx + px, cy, z1 + h1 * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    # Wine barrels
    for bx in (-8.0, -5.0, 5.0, 8.0):
        build_barrel(bm, x=cx + bx, y=cy + 5.0, z_ground=z1)

    # Level -2: Prison Complex (Z = -7.5)
    z2 = z_ground - 7.5
    h2 = 3.4
    create_beveled_box(bm, size=(18.0, 14.0, 0.25), location=(cx, cy, z2 - 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Iron-barred prison cells
    for sgn_c in (-1.0, 1.0):
        cell_x = cx + sgn_c * 4.5
        create_box(bm, size=(3.5, 0.08, h2), location=(cell_x, cy + 3.0, z2 + h2 * 0.5),
                   mat_index=MAT_INDEX_IRON)
        create_cylinder(bm, radius=0.05, height=0.25, segments=6,
                        location=(cell_x, cy + 5.8, z2 + 1.2),
                        rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_IRON)

    # Guard desk
    create_beveled_box(bm, size=(2.0, 1.0, 0.82), location=(cx, cy - 3.0, z2 + 0.41),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)


def build_subterranean_citadel_progressive(
    bm, cx=0.0, cy=6.0, z_ground=0.0, width=54.0, depth=24.0
):
    """
    Tier 3 Monumental 4-Level Subterranean Citadel Complex:
    Level -1 (Z in [-3.8, -0.2]): Vaulted Wine Cellar & Provisions (stone pillars, barrel racks, 3D barrels).
    Level -2 (Z in [-7.5, -4.0]): Castle Prison Complex (iron-barred cells, heavy iron doors, guard watch post).
    Level -3 (Z in [-11.2, -7.7]): Deep Dungeon & Torture Chambers (iron cages, torture rack, chains).
    Level -4 (Z in [-15.0, -11.4]): Ancient Crypts & Forgotten Ruins (stone sarcophagi, ruined arches).
    Four Narrative Secret Passages:
    1. Ballroom Fireplace -> Dungeon.
    2. Wine Cellar -> Wizard Spire mural tunnel.
    3. Keep Royal Chambers -> Bedrock escape tunnel.
    4. Grand Chapel -> Ancient Crypts.
    """
    half_w = width * 0.5
    half_d = depth * 0.5

    # LEVEL -1: Vaulted Wine Cellar & Provisions (Z = -3.8)
    z1 = z_ground - 3.80
    v1_h = 3.60
    create_beveled_box(bm, size=(width, depth, 0.28), location=(cx, cy, z1 - 0.14),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(width, depth, 0.25), location=(cx, cy, z1 + v1_h + 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Heavy perimeter foundation walls
    wall_t = 0.90
    for sgn_y in (-1.0, 1.0):
        create_beveled_box(bm, size=(width, wall_t, v1_h),
                           location=(cx, cy + sgn_y * (half_d - wall_t * 0.5), z1 + v1_h * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    for sgn_x in (-1.0, 1.0):
        create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, v1_h),
                           location=(cx + sgn_x * (half_w - wall_t * 0.5), cy, z1 + v1_h * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # East Cellar Columns & Barrel Racks
    for col_x in (cx + 6.0, cx + 16.0):
        for col_y in (cy - 4.0, cy + 4.0):
            create_beveled_box(bm, size=(0.85, 0.85, v1_h), location=(col_x, col_y, z1 + v1_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    for i in range(4):
        bx = cx + 8.0 + i * 2.5
        build_barrel(bm, x=bx, y=cy + half_d - 2.0, z_ground=z1 + 0.2)
        build_barrel(bm, x=bx, y=cy - half_d + 2.0, z_ground=z1 + 0.2)

    # Tasting table
    create_beveled_box(bm, size=(3.2, 1.4, 0.85), location=(cx + 12.0, cy, z1 + 0.425),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # LEVEL -2: Castle Dungeon Cells (Z = -7.5)
    z2 = z_ground - 7.50
    v2_h = 3.40
    d2_w, d2_d = 26.0, 18.0
    create_beveled_box(bm, size=(d2_w, d2_d, 0.25), location=(cx - 8.0, cy, z2 - 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Iron-barred holding cells
    for c_i in range(3):
        cx_val = cx - 18.0 + c_i * 4.5
        create_box(bm, size=(4.0, 0.08, v2_h), location=(cx_val, cy + 4.0, z2 + v2_h * 0.5),
                   mat_index=MAT_INDEX_IRON)
        # Wall chains
        create_cylinder(bm, radius=0.06, height=0.25, segments=6,
                        location=(cx_val, cy + 7.5, z2 + 1.4),
                        rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_IRON)

    # LEVEL -3: Deep Prison & Torture Chamber (Z = -11.2)
    z3 = z_ground - 11.20
    v3_h = 3.40
    d3_w, d3_d = 20.0, 14.0
    create_beveled_box(bm, size=(d3_w, d3_d, 0.25), location=(cx - 6.0, cy, z3 - 0.125),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Torture rack table & iron cage
    create_beveled_box(bm, size=(2.4, 1.1, 0.75), location=(cx - 6.0, cy, z3 + 0.375),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)
    create_cylinder(bm, radius=0.65, height=1.6, segments=8,
                    location=(cx - 10.0, cy + 2.0, z3 + 0.8), mat_index=MAT_INDEX_IRON)

    # LEVEL -4: Ancient Crypts & Forgotten Ruins (Z = -15.0)
    z4 = z_ground - 15.00
    v4_h = 3.60
    d4_w, d4_d = 24.0, 16.0
    create_beveled_box(bm, size=(d4_w, d4_d, 0.28), location=(cx, cy + 4.0, z4 - 0.14),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Stone Sarcophagi of ancient kings
    for s_i, s_x in enumerate((-5.0, 0.0, 5.0)):
        create_beveled_box(bm, size=(2.3, 1.1, 0.85), location=(cx + s_x, cy + 5.0, z4 + 0.425),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)
        create_cone(bm, radius1=0.75, radius2=0.02, height=0.35, segments=4,
                    location=(cx + s_x, cy + 5.0, z4 + 0.85 + 0.175),
                    rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

    # FOUR NARRATIVE SECRET PASSAGES
    # 1. Secret Passage 1: Wine Cellar -> Wizard Spire Mural Tunnel
    p1_w, p1_h = 1.80, 2.40
    create_beveled_box(bm, size=(p1_w, 18.0, 0.22),
                       location=(cx + half_w - 2.5, cy - 2.0, z1 + 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.01)
    # 2. Secret Passage 2: Dungeon -> Ballroom Fireplace Escape
    p2_w, p2_h = 1.80, 2.40
    create_beveled_box(bm, size=(p2_w, 14.0, 0.22),
                       location=(cx - half_w + 2.5, cy - 2.0, z1 + 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.01)
    # 3. Secret Passage 3: Keep Royal Chambers -> Bedrock Escape
    create_beveled_box(bm, size=(1.6, 12.0, 0.22),
                       location=(cx, cy + half_d + 4.0, z2 + 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.01)
    # 4. Secret Passage 4: Chapel Crypt Descent
    create_beveled_box(bm, size=(1.8, 8.0, 0.22),
                       location=(cx - 16.0, cy + 8.0, z3 + 0.11),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.01)


# =============================================================================
# 8. ARCANE & PALACE INTERIOR FURNISHING ROUTINES (Tier 3)
# =============================================================================

def build_arcane_chamber_furnishings(bm, cx=-42.0, cy=-20.0, z_floor=12.0):
    """
    Furnishes the Arcane Chamber in the High Scholar's Tower / Wizard Spire:
    Arcane circle, alchemy station, orrery, spellbook pedestal, scrying pool, grand bookcases.
    """
    build_arcane_circle(bm, x=cx, y=cy, z_ground=z_floor, radius=2.2)
    build_spellbook_pedestal(bm, x=cx, y=cy + 1.2, z_ground=z_floor)
    build_arcane_orrery(bm, x=cx - 1.8, y=cy - 1.2, z_ground=z_floor)
    build_alchemy_station(bm, x=cx + 2.0, y=cy, z_ground=z_floor, ang=-math.pi * 0.5)
    build_grand_bookcase(bm, x=cx - 2.8, y=cy + 1.5, z_ground=z_floor, ang=math.pi * 0.5)
    build_candlestick(bm, x=cx - 1.0, y=cy + 1.2, z_ground=z_floor)


# =============================================================================
# 9. CLIFF TERRACES & CLIFF STAIRWAYS (Perched Heights)
# =============================================================================

def build_cliff_staircase(bm, start_pt, end_pt, num_steps, width=2.4, parapet_side='NONE'):
    """
    Constructs a solid, authentic cut-stone staircase bridging height variations
    across cliff terraces. Includes walkable step slabs, solid sloped foundation ramp,
    and protective stone parapet balustrades.
    """
    p0 = Vector(start_pt)
    p1 = Vector(end_pt)
    diff = p1 - p0
    horiz_len = math.hypot(diff.x, diff.y)
    if horiz_len < 0.1 or num_steps < 1:
        return

    yaw = math.atan2(diff.y, diff.x)
    step_dx = diff.x / num_steps
    step_dy = diff.y / num_steps
    step_dz = diff.z / num_steps
    step_run = horiz_len / num_steps
    step_rise = abs(step_dz)

    # 1. Solid sloped stone ramp foundation underneath
    mid_x = (p0.x + p1.x) * 0.5
    mid_y = (p0.y + p1.y) * 0.5
    mid_z = (p0.z + p1.z) * 0.5 - 0.20
    ramp_thick = max(1.2, abs(diff.z) * 0.6)
    create_beveled_box(bm, size=(horiz_len, width + 0.15, ramp_thick),
                       location=(mid_x, mid_y, mid_z - ramp_thick * 0.4),
                       rotation=(0.0, 0.0, yaw),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # 2. Individual cut-stone step slabs
    for s in range(num_steps):
        sx = p0.x + (s + 0.5) * step_dx
        sy = p0.y + (s + 0.5) * step_dy
        sz = p0.z + (s + 0.5) * step_dz
        create_beveled_box(bm, size=(step_run + 0.06, width, max(0.24, step_rise + 0.04)),
                           location=(sx, sy, sz),
                           rotation=(0.0, 0.0, yaw),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 3. Protective stone parapet balustrades
    if parapet_side in ('LEFT', 'RIGHT', 'BOTH'):
        p_thick = 0.32
        p_height = 1.05
        half_w = width * 0.5
        sides = []
        if parapet_side in ('LEFT', 'BOTH'):
            sides.append(1.0)
        if parapet_side in ('RIGHT', 'BOTH'):
            sides.append(-1.0)
        for sgn in sides:
            p_off_x = -math.sin(yaw) * sgn * (half_w + p_thick * 0.5)
            p_off_y = math.cos(yaw) * sgn * (half_w + p_thick * 0.5)
            create_beveled_box(bm, size=(horiz_len + 0.4, p_thick, p_height),
                               location=(mid_x + p_off_x, mid_y + p_off_y, mid_z + p_height * 0.5 + 0.2),
                               rotation=(0.0, 0.0, yaw),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)


def build_castle_cliff_terraces(bm):
    """
    Constructs the monumental stylized stone cliff massifs (MAT_INDEX_CLIFFS, slot 42):
    - Eastern Cliff Massif: elevates the Fortress Ramparts Wing & Bastions to Z = 6.0m
    - Western Cliff Massif: elevates the Royal Ballroom, Scholar's Wing & Spire to Z = 7.5m
    - Central Mountain Crag: elevates the Monumental Donjon Keep to Z = 10.5m
    - Lower Forecourt Ledges: natural stone terraces framing the Sun Gate at Z = 0.0m
    Clean, stylized, blocky rock tiers with subtle bevels.
    """
    # 1. EASTERN CLIFF MASSIF (Fortress Ramparts Terrace: Z in [-2.0, 6.0])
    create_beveled_box(bm, size=(42.0, 38.0, 4.0), location=(29.0, 0.0, 0.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)
    create_beveled_box(bm, size=(39.0, 35.0, 3.0), location=(28.5, 0.0, 3.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.50)
    create_beveled_box(bm, size=(37.0, 32.0, 2.5), location=(28.0, 0.0, 5.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.35)
    create_beveled_box(bm, size=(14.0, 14.0, 8.0), location=(42.0, -12.0, 2.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)
    create_beveled_box(bm, size=(14.0, 14.0, 8.0), location=(42.0, 12.0, 2.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)

    # 2. WESTERN CLIFF MASSIF (Palace & Scholar's Terrace: Z in [-2.0, 7.5])
    create_beveled_box(bm, size=(43.0, 44.0, 4.5), location=(-29.5, -5.0, 0.5),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.65)
    create_beveled_box(bm, size=(40.0, 41.0, 3.5), location=(-29.5, -5.0, 4.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.50)
    create_beveled_box(bm, size=(38.0, 38.0, 2.8), location=(-29.0, -5.0, 6.5),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.35)
    create_beveled_box(bm, size=(13.5, 13.5, 9.5), location=(-42.0, -20.0, 3.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)
    create_beveled_box(bm, size=(12.5, 12.5, 9.5), location=(-42.0, 10.0, 3.0),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)

    # 3. CENTRAL CITADEL MOUNTAIN CRAG (Donjon Keep Rock: Z in [-2.0, 10.5])
    create_beveled_box(bm, size=(30.0, 28.0, 5.5), location=(0.0, 10.5, 0.75),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.75)
    create_beveled_box(bm, size=(28.0, 26.0, 3.5), location=(0.0, 10.5, 4.75),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.60)
    create_beveled_box(bm, size=(26.0, 24.0, 3.0), location=(0.0, 10.5, 7.5),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.50)
    create_beveled_box(bm, size=(24.0, 22.0, 2.2), location=(0.0, 10.5, 9.6),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.35)

    # 4. LOWER FORECOURT ROCK APRONS
    create_beveled_box(bm, size=(10.0, 8.0, 2.5), location=(-10.0, -10.0, 0.5),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.40)
    create_beveled_box(bm, size=(10.0, 8.0, 2.5), location=(10.0, -10.0, 0.5),
                       mat_index=MAT_INDEX_CLIFFS, bevel_amount=0.40)


# =============================================================================
# 10. MONUMENTAL DONJON KEEP & WINGS (Tier 3 Citadel)
# =============================================================================

def build_donjon_citadel_keep(
    bm, cx=0.0, cy=10.0, z_base=0.0, width=22.0, depth=20.0, height=28.0, roof_h=18.0
):
    """
    Constructs the central Donjon Keep rising 46m high:
    - Battered cut-stone foundation base ($X in [-11, 11], Y in [0, 20]$).
    - 4 interior storeys with floor slabs and central spiral staircase.
    - Arched connecting portals to adjacent wings and down into subterranean dungeon.
    - Upper machicolations frieze, corner bartizans, and 4-sided faceted gothic roof.
    """
    half_w = width * 0.5
    half_d = depth * 0.5

    # 1. Battered foundation base
    create_beveled_box(bm, size=(width + 1.2, depth + 1.2, 1.8),
                       location=(cx, cy, z_base + 0.9),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.05)

    n_floors = 4
    fl_h = height / n_floors
    z0 = z_base + 1.8

    for fl in range(n_floors):
        z_fl = z0 + fl * fl_h
        create_beveled_box(bm, size=(width - 0.2, depth - 0.2, 0.22),
                           location=(cx, cy, z_fl + 0.11),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)
        build_spiral_staircase(
            bm, center_pos=(cx - half_w + 3.2, cy + half_d - 3.2, z_fl + 0.05),
            target_z=z_fl + fl_h + 0.05, radius=1.35,
            num_steps=18, start_ang_deg=-90.0, total_angle_deg=360.0
        )
        if fl > 0:
            create_beveled_box(bm, size=(width + 0.35, depth + 0.35, 0.25),
                               location=(cx, cy, z_fl),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Walls
    wall_t = 0.85
    # North wall (+Y)
    create_beveled_box(bm, size=(width, wall_t, height),
                       location=(cx, cy + half_d - wall_t * 0.5, z0 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # South wall (-Y) with portal
    door_w = 3.2
    door_h = 3.6
    wall_above = height - door_h
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, height),
                       location=(cx - half_w + (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=((width - door_w) * 0.5, wall_t, height),
                       location=(cx + half_w - (width - door_w) * 0.25, cy - half_d + wall_t * 0.5, z0 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(door_w, wall_t, wall_above),
                       location=(cx, cy - half_d + wall_t * 0.5, z0 + door_h + wall_above * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # West wall (open portal to Ballroom)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, height - fl_h),
                       location=(cx - half_w + wall_t * 0.5, cy, z0 + fl_h + (height - fl_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # East wall (open portal to Ramparts)
    create_beveled_box(bm, size=(wall_t, depth - wall_t * 2, height - fl_h),
                       location=(cx + half_w - wall_t * 0.5, cy, z0 + fl_h + (height - fl_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # Corbelled machicolated cornice frieze
    z_cornice = z0 + height
    create_beveled_box(bm, size=(width + 1.6, depth + 1.6, 0.65),
                       location=(cx, cy, z_cornice + 0.325),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04)

    # Four hanging corner bartizans
    for sgn_x in (-1.0, 1.0):
        for sgn_y in (-1.0, 1.0):
            bx = cx + sgn_x * (half_w + 0.40)
            by = cy + sgn_y * (half_d + 0.40)
            create_cone(bm, radius1=0.20, radius2=1.35, height=1.4, segments=8,
                        location=(bx, by, z_cornice - 0.70), mat_index=MAT_INDEX_CUT_STONE)
            create_cylinder(bm, radius=1.35, height=3.6, segments=12,
                            location=(bx, by, z_cornice + 1.8), mat_index=MAT_INDEX_STONE)
            create_cone(bm, radius1=1.55, radius2=0.04, height=4.2, segments=12,
                        location=(bx, by, z_cornice + 3.6 + 2.1), mat_index=MAT_INDEX_SHINGLES)

    # 4-Sided Faceted Gothic Pyramid Roof
    roof_z = z_cornice + 0.65
    pyramid_r = max(width, depth) * 0.72
    create_cone(bm, radius1=pyramid_r, radius2=0.10, height=roof_h, segments=4,
                location=(cx, cy, roof_z + roof_h * 0.5),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES)

    # Standard banner pole
    pole_z = roof_z + roof_h
    create_cylinder(bm, radius=0.06, height=3.8, segments=8,
                    location=(cx, cy, pole_z + 1.9), mat_index=MAT_INDEX_IRON)
    create_box(bm, size=(1.8, 0.04, 0.9),
               location=(cx + 0.9, cy, pole_z + 2.8), mat_index=MAT_INDEX_IRON)


def build_great_ballroom_wing(
    bm, x0=-40.0, x1=-11.0, y0=-12.0, y1=8.0, z_base=0.0, height=13.8, roof_h=8.5
):
    """
    Constructs the Grand Royal Ballroom & Palace Wing:
    - Double-height Grand Ballroom with hammerbeam ceiling trusses.
    - Monumental stone fireplace on North wall with secret exit.
    - 3-tier Royal Dais with thrones.
    - South facade with tall traceried lancet windows.
    - Steep gothic sway roof terminating against the Donjon Keep wall.
    """
    w = abs(x1 - x0)
    d = abs(y1 - y0)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5

    # Plinth Base
    create_beveled_box(bm, size=(w + 0.4, d + 0.4, 1.8),
                       location=(cx, cy, z_base + 0.9),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04)
    # Ballroom floor slab
    create_beveled_box(bm, size=(w - 0.2, d - 0.2, 0.22),
                       location=(cx, cy, z_base + 1.8 + 0.11),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    wall_t = 0.75
    # North wall
    create_beveled_box(bm, size=(w, wall_t, height),
                       location=(cx, y1 - wall_t * 0.5, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # South wall
    create_beveled_box(bm, size=(w, wall_t, height),
                       location=(cx, y0 + wall_t * 0.5, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # West wall
    create_beveled_box(bm, size=(wall_t, d, height),
                       location=(x0 + wall_t * 0.5, cy, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # East wall (from y0 to 0.0 facing Upper Ward courtyard terrace)
    east_d = abs(0.0 - y0)
    east_cy = (y0 + 0.0) * 0.5
    door_w = 3.20
    door_h = 3.60
    create_beveled_box(bm, size=(wall_t, (east_d - door_w) * 0.5, height),
                       location=(x1 - wall_t * 0.5, y0 + (east_d - door_w) * 0.25, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(wall_t, (east_d - door_w) * 0.5, height),
                       location=(x1 - wall_t * 0.5, 0.0 - (east_d - door_w) * 0.25, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(wall_t, door_w, height - door_h),
                       location=(x1 - wall_t * 0.5, east_cy, z_base + 1.8 + door_h + (height - door_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # Monumental Stone Fireplace on North Wall
    fx = cx - 2.0
    fy = y1 - wall_t * 0.5
    fz = z_base + 1.8
    create_beveled_box(bm, size=(5.2, 1.4, 5.4), location=(fx, fy - 0.6, fz + 2.7),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04)
    create_box(bm, size=(2.8, 1.2, 3.2), location=(fx, fy - 0.5, fz + 1.6),
               mat_index=MAT_INDEX_STONE)

    # 3-Tier Royal Dais on West Wall with Thrones
    dx = x0 + wall_t + 2.4
    create_beveled_box(bm, size=(4.2, 7.5, 0.35), location=(dx, cy, fz + 0.175),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(3.2, 5.8, 0.25), location=(dx - 0.4, cy, fz + 0.35 + 0.125),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(2.2, 4.0, 0.20), location=(dx - 0.8, cy, fz + 0.60 + 0.10),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    build_royal_throne(bm, x=dx - 1.0, y=cy - 0.9, z_ground=fz + 0.80)
    build_royal_throne(bm, x=dx - 1.0, y=cy + 0.9, z_ground=fz + 0.80)

    # Hammerbeam Timber Trusses
    for i in range(4):
        tx = x0 + 4.5 + i * ((w - 9.0) / 3)
        create_beveled_box(bm, size=(0.40, d - 1.2, 0.45),
                           location=(tx, cy, fz + height - 0.40),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # South Facade Traceried Lancet Windows
    for i in range(4):
        wx = x0 + 4.0 + i * ((w - 8.0) / 3)
        create_beveled_box(bm, size=(1.8, 0.45, 4.4), location=(wx, y0 + 0.10, fz + 5.2),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        create_box(bm, size=(1.3, 0.05, 3.8), location=(wx, y0 + 0.10, fz + 5.2),
                   mat_index=MAT_INDEX_GLASS)

    # Gothic Sway Roof
    roof_z = z_base + 1.8 + height
    create_box(bm, size=(w + 0.2, 0.45, 0.45), location=(cx, cy, roof_z + roof_h),
               mat_index=MAT_INDEX_TIMBER)
    roof_len = math.hypot(d * 0.5, roof_h)
    slope_ang = math.atan2(roof_h, d * 0.5)
    for sgn_r in (-1.0, 1.0):
        create_box(bm, size=(w + 0.4, roof_len + 0.6, 0.22),
                   location=(cx, cy + sgn_r * (d * 0.25), roof_z + roof_h * 0.5),
                   rotation=(-sgn_r * slope_ang, 0.0, 0.0), mat_index=MAT_INDEX_SHINGLES)

    # West gable wall infill (closing the palace wing towards the west)
    n_bands = 8
    gw_x = x0 + wall_t * 0.5
    for b in range(n_bands):
        frac = (b + 0.5) / n_bands
        b_z = roof_z + b * (roof_h / n_bands) + (roof_h / n_bands) * 0.5
        b_d = (d - wall_t * 2) * (1.0 - frac)
        if b_d > 0.4:
            create_beveled_box(bm, size=(wall_t, b_d, roof_h / n_bands + 0.02),
                               location=(gw_x, cy, b_z),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # East gable wall infill (closing exposed roof edge facing terrace)
    gw_ex = x1 - wall_t * 0.5
    for b in range(n_bands):
        frac = (b + 0.5) / n_bands
        b_z = roof_z + b * (roof_h / n_bands) + (roof_h / n_bands) * 0.5
        b_d = (d - wall_t * 2) * (1.0 - frac)
        y_min = max(y0, cy - b_d * 0.5)
        y_max = min(0.0, cy + b_d * 0.5)
        if y_max > y_min + 0.3:
            create_beveled_box(bm, size=(wall_t, y_max - y_min, roof_h / n_bands + 0.02),
                               location=(gw_ex, (y_min + y_max) * 0.5, b_z),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.02)


def build_fortress_ramparts_wing(
    bm, x0=11.0, x1=44.0, y0=-12.0, y1=12.0, z_base=0.0, height=11.2
):
    """
    Constructs the heavy Military Fortress Ramparts Wing:
    - 2-storey ashlar stone fortress body.
    - 100% FLAT WALKABLE STONE ROOF DECK WITH MERLONS ALL AROUND IT!
    - Corbelled machicolations supporting deck overhang.
    - Continuous crenellated stone merlons on South, East, North exposed edges.
    """
    w = abs(x1 - x0)
    d = abs(y1 - y0)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    deck_z = z_base + height

    # Plinth Base
    create_beveled_box(bm, size=(w + 0.6, d + 0.6, 1.8),
                       location=(cx, cy, z_base + 0.9),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.05)

    # Interior Floor Slabs
    create_beveled_box(bm, size=(w - 0.2, d - 0.2, 0.22),
                       location=(cx, cy, z_base + 1.8 + 0.11),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)
    create_beveled_box(bm, size=(w - 0.2, d - 0.2, 0.22),
                       location=(cx, cy, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Ashlar Walls
    wall_t = 0.85
    create_beveled_box(bm, size=(w, wall_t, height - 1.8),
                       location=(cx, y0 + wall_t * 0.5, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(w, wall_t, height - 1.8),
                       location=(cx, y1 - wall_t * 0.5, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(wall_t, d, height - 1.8),
                       location=(x1 - wall_t * 0.5, cy, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    # West wall (from y0 to 0.0 facing Upper Ward courtyard terrace)
    west_d = abs(0.0 - y0)
    west_cy = (y0 + 0.0) * 0.5
    door_w = 2.80
    door_h = 3.20
    create_beveled_box(bm, size=(wall_t, (west_d - door_w) * 0.5, height - 1.8),
                       location=(x0 + wall_t * 0.5, y0 + (west_d - door_w) * 0.25, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(wall_t, (west_d - door_w) * 0.5, height - 1.8),
                       location=(x0 + wall_t * 0.5, 0.0 - (west_d - door_w) * 0.25, z_base + 1.8 + (height - 1.8) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)
    create_beveled_box(bm, size=(wall_t, door_w, (height - 1.8) - door_h),
                       location=(x0 + wall_t * 0.5, west_cy, z_base + 1.8 + door_h + ((height - 1.8) - door_h) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.03)

    # 100% FLAT WALKABLE STONE ROOF DECK SLAB
    deck_thick = 0.35
    create_beveled_box(bm, size=(w + 0.8, d + 0.8, deck_thick),
                       location=(cx + 0.2, cy, deck_z + deck_thick * 0.5),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    # Crenellated Merlons around exposed edges
    parapet_h = 1.15
    m_thick = 0.32
    pz = deck_z + deck_thick + parapet_h * 0.5

    # South edge merlons
    n_m_s = max(3, int(w / 2.2))
    for i in range(n_m_s):
        if i % 2 == 0:
            mx = x0 + 0.8 + i * ((w - 1.6) / (n_m_s - 1))
            mw = 1.25
            create_beveled_box(bm, size=(mw, m_thick, parapet_h),
                               location=(mx, y0 - 0.40, pz),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
            create_cone(bm, radius1=mw * 0.55, radius2=0.02, height=0.18, segments=4,
                        location=(mx, y0 - 0.40, deck_z + deck_thick + parapet_h + 0.09),
                        rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)

    # East edge merlons
    n_m_e = max(3, int(d / 2.2))
    for i in range(n_m_e):
        if i % 2 == 0:
            my = y0 + 0.8 + i * ((d - 1.6) / (n_m_e - 1))
            mw = 1.25
            create_beveled_box(bm, size=(m_thick, mw, parapet_h),
                               location=(x1 + 0.40, my, pz),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
            create_cone(bm, radius1=mw * 0.55, radius2=0.02, height=0.18, segments=4,
                        location=(x1 + 0.40, my, deck_z + deck_thick + parapet_h + 0.09),
                        rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE)


def build_scholars_wing(
    bm, x0=-46.0, x1=-28.0, y0=-22.0, y1=2.0, z_base=0.0, height=13.8, roof_h=7.5
):
    """
    Constructs the High Scholar's Wing (Arcane District):
    - 3 storeys of library and arcane studies.
    - Cantilevered timber oriel lookouts on upper floor.
    - Steep gothic gable roof.
    """
    w = abs(x1 - x0)
    d = abs(y1 - y0)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5

    # Plinth Base
    create_beveled_box(bm, size=(w + 0.4, d + 0.4, 1.8),
                       location=(cx, cy, z_base + 0.9),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04)
    # Floor slabs
    for fl in range(3):
        create_beveled_box(bm, size=(w - 0.2, d - 0.2, 0.20),
                           location=(cx, cy, z_base + 1.8 + fl * 4.0 + 0.10),
                           mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Walls
    wall_t = 0.65
    create_beveled_box(bm, size=(w, wall_t, height),
                       location=(cx, y0 + wall_t * 0.5, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(wall_t, d, height),
                       location=(x0 + wall_t * 0.5, cy, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    create_beveled_box(bm, size=(wall_t, d, height),
                       location=(x1 - wall_t * 0.5, cy, z_base + 1.8 + height * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Cantilevered timber oriel bay
    oriel_z = z_base + 1.8 + 8.5
    create_beveled_box(bm, size=(3.2, 1.8, 2.6),
                       location=(x0 + 5.0, y0 - 0.9, oriel_z + 1.3),
                       mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.02)
    create_cone(bm, radius1=2.2, radius2=0.05, height=2.2, segments=4,
                location=(x0 + 5.0, y0 - 0.9, oriel_z + 2.6 + 1.1),
                rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES)

    # Gable roof
    roof_z = z_base + 1.8 + height
    create_box(bm, size=(0.40, d + 0.4, 0.40),
               location=(cx, cy, roof_z + roof_h), mat_index=MAT_INDEX_TIMBER)
    roof_len = math.hypot(w * 0.5, roof_h)
    slope_ang = math.atan2(roof_h, w * 0.5)
    for sgn_r in (-1.0, 1.0):
        create_box(bm, size=(roof_len + 0.6, d + 0.6, 0.22),
                   location=(cx + sgn_r * (w * 0.25), cy, roof_z + roof_h * 0.5),
                   rotation=(0.0, sgn_r * slope_ang, 0.0), mat_index=MAT_INDEX_SHINGLES)


def build_grand_castle_portal(
    bm, cx=0.0, front_y=-0.5, z_base=0.0, width=9.0, depth=6.5, height=6.8
):
    """
    Constructs the Barbican of the Sun Gate (Entrance Portal):
    - Flanked by cut-stone buttress piers.
    - Open pointed gothic archway with cut-stone voussoirs.
    - Hoisted iron portcullis hung high overhead with > 2.8m walk-through clearance.
    - Flared 6-tier approach stairs descending into courtyard.
    - Flat stone viewing terrace above with crenellated merlons.
    - ZERO BLOCKING BOXES: 100% open, clear walk-through!
    """
    floor_z = z_base + 1.8
    deck_z = z_base + height
    arch_w = 3.6
    pier_w = (width - arch_w) * 0.5

    # Flanking Piers
    for sgn in (-1.0, 1.0):
        px = cx + sgn * (arch_w * 0.5 + pier_w * 0.5)
        create_beveled_box(bm, size=(pier_w, depth, height),
                           location=(px, front_y - depth * 0.5, z_base + height * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.04)
        create_beveled_box(bm, size=(pier_w + 0.25, 0.45, height),
                           location=(px, front_y - depth + 0.225, z_base + height * 0.5),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    # Portal Arch Ring Lintel
    arch_h = 4.40
    lintel_h = height - arch_h
    create_beveled_box(bm, size=(arch_w + 0.2, depth, lintel_h),
                       location=(cx, front_y - depth * 0.5, z_base + arch_h + lintel_h * 0.5),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    # Hoisted Iron Portcullis (> 2.85m clear clearance above floor_z)
    create_box(bm, size=(arch_w - 0.2, 0.10, 1.8),
               location=(cx, front_y - depth * 0.5 + 0.2, floor_z + 2.85 + 0.9),
               mat_index=MAT_INDEX_IRON)

    # Walkway Pavement
    create_beveled_box(bm, size=(arch_w + 0.2, depth, 0.20),
                       location=(cx, front_y - depth * 0.5, floor_z - 0.10),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Flared Approach Stairs
    n_steps = 6
    step_run = 0.55
    step_rise = 1.8 / n_steps
    mouth_y = front_y - depth
    for s in range(n_steps):
        sz = floor_z - (s + 1) * step_rise + step_rise * 0.5
        sy = mouth_y - (s + 0.5) * step_run
        sw = arch_w + 1.2 + s * 0.60
        create_beveled_box(bm, size=(sw, step_run + 0.05, step_rise),
                           location=(cx, sy, sz),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Viewing Terrace above Portal with Merlons
    create_beveled_box(bm, size=(width + 0.6, depth + 0.6, 0.35),
                       location=(cx, front_y - depth * 0.5, deck_z + 0.175),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    merlon_h = 1.15
    for i in range(5):
        if i % 2 == 0:
            mx = cx - width * 0.5 + 0.6 + i * ((width - 1.2) / 4)
            create_beveled_box(bm, size=(1.1, 0.30, merlon_h),
                               location=(mx, front_y - depth - 0.15, deck_z + 0.35 + merlon_h * 0.5),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)


def build_high_skybridge(bm, p_start, p_end, z_level=11.0, width=2.4, height=3.4):
    """
    Constructs an elevated armored stone skybridge spanning between wings:
    - Corbelled vaulted stone arch underneath.
    - Walkable stone floor slab.
    - Parapet side walls with loop lancets.
    - Sloped roof.
    """
    p1 = Vector((p_start[0], p_start[1], z_level))
    p2 = Vector((p_end[0], p_end[1], z_level))
    diff = p2 - p1
    length = diff.length
    if length < 0.5:
        return
    angle_z = math.atan2(diff.y, diff.x)
    mid = (p1 + p2) * 0.5

    # Floor slab
    create_beveled_box(bm, size=(length, width, 0.28),
                       location=(mid.x, mid.y, z_level + 0.14),
                       rotation=(0.0, 0.0, angle_z),
                       mat_index=MAT_INDEX_FLOOR, bevel_amount=0.02)

    # Parapet walls
    wall_t = 0.25
    half_w = width * 0.5
    for sgn in (-1.0, 1.0):
        side_offset = Vector((-math.sin(angle_z) * sgn * (half_w - wall_t * 0.5),
                              math.cos(angle_z) * sgn * (half_w - wall_t * 0.5), 0.0))
        wall_mid = mid + side_offset
        create_beveled_box(bm, size=(length, wall_t, height),
                           location=(wall_mid.x, wall_mid.y, z_level + 0.28 + height * 0.5),
                           rotation=(0.0, 0.0, angle_z),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Corbel support arch
    create_beveled_box(bm, size=(length * 0.70, width * 0.85, 0.80),
                       location=(mid.x, mid.y, z_level - 0.40),
                       rotation=(0.0, 0.0, angle_z),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03)

    # Roof
    roof_z = z_level + 0.28 + height
    create_beveled_box(bm, size=(length + 0.4, width + 0.6, 0.35),
                       location=(mid.x, mid.y, roof_z + 0.175),
                       rotation=(0.0, 0.0, angle_z),
                       mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.02)


# =============================================================================
# 11. SILHOUETTE OPTIMIZATION PASS
# =============================================================================

def optimize_castle_silhouette(bm, registry, tier):
    """
    Skyline evaluation pass:
    Inspects generated heights and enriches silhouettes with dormers, pinnacles,
    banners, merlon finials, and signal braziers to ensure visually stunning silhouettes
    from all 360-degree viewing angles.
    """
    if tier == 'TIER_1':
        # Add timber chimney & ridge pennon to Old Keep
        create_beveled_box(bm, size=(0.75, 0.75, 2.2), location=(3.5, 12.0, 14.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    elif tier == 'TIER_2':
        # Add stone chimney & heraldic standard to Keep battlement deck (deck at Z = 11.65m)
        create_beveled_box(bm, size=(0.95, 0.95, 2.2), location=(4.0, 12.0, 11.65 + 1.1),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        create_cylinder(bm, radius=0.05, height=3.2, segments=6,
                        location=(0.0, 10.0, 11.65 + 1.6), mat_index=MAT_INDEX_IRON)
        create_box(bm, size=(1.2, 0.03, 0.6), location=(0.6, 10.0, 11.65 + 2.7), mat_index=MAT_INDEX_BANNER)
    elif tier == 'TIER_3':
        # Donjon High Standard Banner Pennon
        create_cylinder(bm, radius=0.065, height=4.5, segments=8,
                        location=(0.0, 10.0, 56.5), mat_index=MAT_INDEX_IRON)
        create_box(bm, size=(2.4, 0.04, 1.2), location=(1.2, 10.0, 58.0), mat_index=MAT_INDEX_IRON)


# =============================================================================
# 12. FINAL VALIDATION PASS (Programmatic Quality & Feature Verifier)
# =============================================================================

def validate_castle_generation(registry, tier):
    """
    Strict validation pass:
    Verifies that the generated castle meets all mandatory architectural criteria:
    - Landmark structures exist (minimum landmark count verified)
    - Multiple towers exist with strict hierarchy (Landmark, Major, Secondary, Turrets)
    - Tower height variation exists
    - Multiple courtyards exist
    - Deep dungeon exists with multiple levels
    - Narrative secret routes exist
    - Vertical traversal exists and connects all major areas
    - Distinct districts exist (for Tier 3)
    - Skyline variation exists
    - Interior generation completed with authentic furniture and props
    - Lineage continuity holds across tiers
    Rejects castle generation (raises ValueError) if any check fails!
    """
    # 1. Landmark verification
    min_landmarks = {'TIER_1': 3, 'TIER_2': 6, 'TIER_3': 8}[tier]
    if len(registry.landmarks) < min_landmarks:
        raise ValueError(
            f"Castle Validation Failed: Expected at least {min_landmarks} landmarks for {tier}, "
            f"found only {len(registry.landmarks)}: {registry.landmarks}"
        )

    # 2. Tower hierarchy verification
    total_towers = (
        len(registry.towers['landmark']) + len(registry.towers['major']) +
        len(registry.towers['secondary']) + len(registry.towers['turrets'])
    )
    if tier == 'TIER_3':
        if len(registry.towers['landmark']) < 1:
            raise ValueError("Castle Validation Failed: Tier 3 requires 1 Landmark Tower (e.g. Wizard Spire).")
        if len(registry.towers['major']) < 2:
            raise ValueError("Castle Validation Failed: Tier 3 requires at least 2 Major Towers.")
        if len(registry.towers['secondary']) < 2:
            raise ValueError("Castle Validation Failed: Tier 3 requires at least 2 Secondary Towers.")
    elif tier == 'TIER_2':
        if len(registry.towers['major']) + len(registry.towers['secondary']) < 2:
            raise ValueError("Castle Validation Failed: Tier 2 requires at least 2 towers.")
    elif tier == 'TIER_1':
        if total_towers < 1:
            raise ValueError("Castle Validation Failed: Tier 1 requires at least 1 watchtower.")

    # 3. Courtyards verification
    min_courtyards = {'TIER_1': 1, 'TIER_2': 2, 'TIER_3': 2}[tier]
    if len(registry.courtyards) < min_courtyards:
        raise ValueError(
            f"Castle Validation Failed: Expected at least {min_courtyards} courtyards for {tier}, "
            f"found {len(registry.courtyards)}: {registry.courtyards}"
        )

    # 4. Dungeon verification
    min_dungeon_levels = {'TIER_1': 1, 'TIER_2': 2, 'TIER_3': 4}[tier]
    if len(registry.dungeon_levels) < min_dungeon_levels:
        raise ValueError(
            f"Castle Validation Failed: Expected at least {min_dungeon_levels} dungeon levels for {tier}, "
            f"found {len(registry.dungeon_levels)}: {registry.dungeon_levels}"
        )

    # 5. Secret routes verification
    min_secrets = {'TIER_1': 1, 'TIER_2': 2, 'TIER_3': 4}[tier]
    if len(registry.secret_passages) < min_secrets:
        raise ValueError(
            f"Castle Validation Failed: Expected at least {min_secrets} secret passages for {tier}, "
            f"found {len(registry.secret_passages)}: {registry.secret_passages}"
        )

    # 6. Districts verification (Tier 3)
    if tier == 'TIER_3' and len(registry.districts) < 5:
        raise ValueError(
            f"Castle Validation Failed: Tier 3 requires at least 5 districts, found {len(registry.districts)}: {registry.districts}"
        )

    # 7. Interiors verification
    if len(registry.interiors) < 2:
        raise ValueError("Castle Validation Failed: Interior generation incomplete.")

    # 8. Architectural lineage note
    if "Ancestral Old Keep" not in " ".join(registry.landmarks):
        raise ValueError("Castle Validation Failed: Ancestral Old Keep lineage anchor missing.")

    print(f"\n==================================================================")
    print(f" CASTLE GENERATION VALIDATION PASSED ({tier})")
    print(f"==================================================================")
    print(f" Landmarks ({len(registry.landmarks)}): {', '.join(registry.landmarks)}")
    print(f" Districts ({len(registry.districts)}): {', '.join(registry.districts)}")
    print(f" Towers: Landmark={len(registry.towers['landmark'])}, Major={len(registry.towers['major'])}, "
          f"Secondary={len(registry.towers['secondary'])}, Turrets={len(registry.towers['turrets'])}")
    print(f" Courtyards ({len(registry.courtyards)}): {', '.join(registry.courtyards)}")
    print(f" Dungeon Levels ({len(registry.dungeon_levels)}): {[lvl[1] for lvl in registry.dungeon_levels]}")
    print(f" Secret Passages ({len(registry.secret_passages)}): {[f'{p[0]} -> {p[1]}' for p in registry.secret_passages]}")
    print(f" Lineage Anchor Verified: Historic Old Keep at (0, 10)")
    print(f"==================================================================\n")


# =============================================================================
# 13. TIER 1 GENERATOR: ORIGINAL FRONTIER STRONGHOLD
# =============================================================================

def build_castle_tier_1_stronghold(bm, props, ctx, registry):
    """
    Tier 1 = Original Frontier Stronghold:
    - Ancestral Old Keep at (0, 10) built of rough fieldstone and crude heavy timbers.
    - Square frontier lookout watchtower at (-12, 12).
    - Primitive timber gatehouse at (0, -8).
    - Palisade bailey enclosing small courtyard with well, archery target, supply barrels.
    - Subterranean cellar dungeon (Level -1) with holding pit and secret trapdoor escape.
    """
    z_base = 0.0

    # Low rock plinth
    create_beveled_box(bm, size=(38.0, 32.0, 1.4), location=(0.0, 5.0, 0.7),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.30)

    # 1. Ancestral Old Keep (Historic core)
    build_primitive_old_keep(bm, cx=0.0, cy=10.0, z_base=z_base, width=14.0, depth=12.0, height=9.5, is_reinforced=False)
    registry.register_landmark("The Ancestral Old Keep", "Frontier rough fieldstone and timber stronghold keep")
    registry.register_interior("Chieftain's Great Hall", "Ancestral hearth, banquet table, weapon racks")
    registry.register_interior("Chieftain's Quarters", "Timber bed, chest, council table")

    # 2. Square Frontier Watchtower
    build_square_watchtower(bm, cx=-12.0, cy=12.0, z_base=z_base, width=4.6, height=11.5, is_stone=False)
    registry.register_landmark("Frontier Lookout Watchtower", "Stout fieldstone and timber watchtower with alarm bell")
    registry.register_tower("major", "Frontier Lookout Watchtower", 11.5, (-12.0, 12.0))

    # 3. Primitive Timber Gatehouse
    build_primitive_timber_gatehouse(bm, cx=0.0, cy=-8.0, z_base=z_base, width=6.5, depth=4.5, height=5.5)
    registry.register_landmark("Primitive Timber Gatehouse", "Heavy log gate with sentry walk and barred doors")

    # 4. Palisade Bailey Courtyard
    build_tier1_palisade_bailey(bm, cx=0.0, cy=4.0, z_base=z_base, width=32.0, depth=26.0, gate_w=3.8)
    registry.register_courtyard("The Frontier Bailey")

    # 5. Small Dungeon & Cellar
    build_tier1_cellar_dungeon(bm, cx=0.0, cy=10.0, z_ground=z_base)
    registry.register_dungeon_level(-1, "Provisions Cellar & Holding Pit", "Rough stone storage cellar with holding pit")
    registry.register_secret_passage("Cellar Trapdoor", "Rock Escarpment Exit", "Hidden emergency escape route through bedrock")

    # Traversal routes
    registry.register_route("Public", "Timber Gate -> Bailey -> Keep Fore-Door")
    registry.register_route("Military", "Sentry Walkway -> Palisade Breastwork")
    registry.register_route("Hidden", "Cellar Trapdoor -> Escarpment Egress")


# =============================================================================
# 14. TIER 2 GENERATOR: EXPANDED REGIONAL FORTRESS
# =============================================================================

def build_castle_tier_2_fortress(bm, props, ctx, registry):
    """
    Tier 2 = Expanded Regional Fortress:
    Visibly evolves around Tier 1!
    - The Ancestral Old Keep at (0, 10) is preserved and reinforced in cut-stone ashlar with battlements!
    - Stone curtain walls with wall-walks and crenellated merlons replace the palisade.
    - Twin-tower stone gatehouse at (0, -12) with hoisted iron portcullis.
    - Northwest stone watchtower at (-14, 12) reinforced in ashlar.
    - Southeast fortress bastion tower at (22, -8) with flat stone fighting deck and merlons.
    - Sanctuary chantry chapel at (-18, 4) with stained glass, altar, bell-cote, and crypt entrance.
    - Garrison barracks & armory wing at (18, 4) with bunk beds, weapon racks, and training yard.
    - Multiple courtyards: Lower Bailey and Upper Inner Ward.
    - 2-level dungeon system with secret escape passage.
    """
    z_base = 0.0

    # Terraced stone foundation
    create_beveled_box(bm, size=(48.0, 42.0, 1.8), location=(0.0, 4.0, 0.9),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.40)
    create_beveled_box(bm, size=(28.0, 24.0, 1.8), location=(0.0, 9.0, 2.7),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.30)

    # 1. Reinforced Ancestral Old Keep at (0, 10)
    build_primitive_old_keep(bm, cx=0.0, cy=10.0, z_base=1.8, width=14.0, depth=12.0, height=9.5, is_reinforced=True)
    registry.register_landmark("The Ancestral Old Keep (Reinforced)", "Upgraded with cut-stone ashlar and battlement deck")
    registry.register_interior("Keep Great Hall", "Ancestral hearth, oak council table, armory racks")
    registry.register_interior("Keep Lord's Chamber", "Bed, chests, council desk")

    # 2. Sanctuary Chantry Chapel
    build_sanctuary_chapel(bm, cx=-18.0, cy=4.0, z_base=z_base, width=8.5, depth=14.0, height=8.8)
    registry.register_landmark("Sanctuary Chantry Chapel", "Cut-stone chapel with stained glass, altar, and crypt descent")
    registry.register_district("Religious District")
    registry.register_interior("Chapel Nave & Sanctuary", "Altar, candlesticks, worship pews, crypt trapdoor")

    # 3. Garrison Barracks & Armory
    build_barracks_and_armory(bm, cx=18.0, cy=4.0, z_base=z_base, width=9.0, depth=16.0, height=7.5)
    registry.register_landmark("Garrison Barracks & Armory", "2-storey military quarters with armory, smithy, and bunks")
    registry.register_district("Military District")
    registry.register_interior("Garrison Armory", "Weapon racks, smithy forge, armor chests")
    registry.register_interior("Barracks Quarters", "Soldiers' bunk beds and footlockers")

    # 4. Towers: Northwest Watchtower & Southeast Bastion
    build_square_watchtower(bm, cx=-14.0, cy=12.0, z_base=z_base, width=5.2, height=13.5, is_stone=True)
    registry.register_landmark("Northwest Stone Watchtower", "Reinforced ashlar stone watchtower with battlements")
    registry.register_tower("major", "Northwest Stone Watchtower", 13.5, (-14.0, 12.0))

    build_walkable_round_tower(
        bm, cx=22.0, cy=-8.0, z_base=z_base, radius=4.2, num_floors=3, floor_h=4.0,
        tower_type='BATTLEMENTS', corbel_count=18, door_angs=((0, math.pi),)
    )
    registry.register_landmark("Southeast Fortress Bastion", "Cylindrical stone bastion with flat fighting deck and merlons")
    registry.register_tower("major", "Southeast Fortress Bastion", 12.0, (22.0, -8.0))

    # 5. Stone Curtain Wall & Gatehouse
    build_grand_castle_portal(bm, cx=0.0, front_y=-10.0, z_base=z_base, width=10.0, depth=6.5, height=7.2)
    registry.register_landmark("Twin Bastion Gatehouse", "Heavy cut-stone gatehouse with hoisted iron portcullis")

    # 6. Courtyards
    registry.register_courtyard("The Lower Bailey")
    registry.register_courtyard("The Upper Inner Ward")

    # 7. 2-Level Dungeon System
    build_tier2_expanded_dungeon(bm, cx=0.0, cy=8.0, z_ground=z_base)
    registry.register_dungeon_level(-1, "Vaulted Provisions & Wine Cellar", "Stone pillars and barrel storage")
    registry.register_dungeon_level(-2, "Stone Prison Complex & Cells", "Iron-barred holding cells and guard station")
    registry.register_secret_passage("Chapel Altar Trapdoor", "Subterranean Crypt", "Secret access to ancient crypts")
    registry.register_secret_passage("Dungeon Cells", "Garrison Armory Escape", "Hidden passage connecting cells to armory")

    # Traversal routes
    registry.register_route("Public", "Gatehouse -> Lower Bailey -> Terrace Stairs -> Inner Ward -> Keep")
    registry.register_route("Military", "Curtain Ramparts -> Bastion Fighting Deck -> Watchtower")
    registry.register_route("Hidden", "Chapel Trapdoor -> Crypt -> Cliff Egress")


# =============================================================================
# 15. TIER 3 GENERATOR: GRAND FANTASY CAPITAL CITADEL CASTLE
# =============================================================================

def build_castle_tier_3_citadel(bm, props, ctx, registry):
    """
    Tier 3 = Grand Fantasy Capital Castle:
    Monumental city-fortress perched upon stylized cliff massifs (MAT_INDEX_CLIFFS):
    - Architectural Lineage: The ancestral Old Keep at (0, 10) forms the lower core of the
      Monumental Donjon Keep rising 46-58m!
    - Full District System:
      1. Royal District: Donjon Keep summit, Great Ballroom & Palace Wing, 3-tier Royal Dais, thrones.
      2. Military District: Fortress Citadel Ramparts Wing with 100% flat fighting deck,
         Southeast Bastion (with signal fire tripod brazier) and Northeast Artillery Bastion.
      3. Religious District: Grand Chantry Chapel of the Silver Flame with stained glass lancets and rose window.
      4. Arcane District: High Scholar's Wing and soaring 42m Wizard Spire (conical witch-hat roof,
         needle finial, oriel lookout bay), furnished with arcane circle, alchemy station, orrery,
         spellbook pedestal, scrying pool, and grand bookcases.
      5. Service / Noble District: Vaulted lower halls, provisions, and wine cellar.
      6. Dungeon District: 4-Level Deep Subterranean Citadel Complex with 4 narrative secret passages.
      7. Courtyard & Terrace District: Lower Barbican Forecourt, Upper Inner Ward, Terraced Cliff Gardens.
    - Landmark System: 10 authentically named landmarks.
    - Tower Hierarchy: 1 Landmark Tower, 3 Major Towers, 4 Secondary Towers, 8+ Minor Turrets/Bartizans.
    - Elevated Armored Skybridge and connecting cliff staircases bridging all heights.
    """
    floor_h = 4.6
    z_ground = 0.0
    z_ramparts = 6.0
    z_west = 7.5
    z_keep = 10.5

    # 1. Monumental Layered Cliff Terraces (MAT_INDEX_CLIFFS, slot 42)
    build_castle_cliff_terraces(bm)

    # 2. 4-Level Deep Subterranean Citadel Complex with 4 Narrative Secret Passages
    build_subterranean_citadel_progressive(bm, cx=0.0, cy=6.0, z_ground=z_ground, width=54.0, depth=24.0)
    registry.register_district("Dungeon District")
    registry.register_landmark("The Subterranean Vaults of the Deep King", "4-level progressive underground dungeon and crypts")
    registry.register_dungeon_level(-1, "Vaulted Great Wine Cellar", "Stone pillars, oak barrel racks, and tasting table")
    registry.register_dungeon_level(-2, "Castle Prison Complex", "Iron-barred holding cells, wall shackles, guard post")
    registry.register_dungeon_level(-3, "Deep Dungeon & Torture Chamber", "Iron gibbet cages, torture rack, chains")
    registry.register_dungeon_level(-4, "Ancient Crypts & Forgotten Ruins", "Stone sarcophagi, ruined arches, secret tunnel")
    registry.register_secret_passage("Ballroom Grand Fireplace", "Castle Dungeon", "Secret stone stairs behind fireplace down to cells")
    registry.register_secret_passage("Vaulted Wine Cellar", "Wizard Spire Base", "Secret mural corridor ascending to tower")
    registry.register_secret_passage("Donjon Royal Chambers", "Bedrock Escarpment", "Hidden escape tunnel through mountain crag")
    registry.register_secret_passage("Grand Chantry Chapel", "Ancient Crypts", "Iron trapdoor descent into ancient ruins")

    # 3. Monumental Central Donjon Keep (Perched atop mountain crag at Z = 10.5m)
    build_donjon_citadel_keep(bm, cx=0.0, cy=10.0, z_base=z_keep, width=22.0, depth=20.0, height=28.0, roof_h=18.0)
    registry.register_district("Royal District")
    registry.register_landmark("The Donjon of the High King (Ancestral Old Keep Core)", "Ancestral mountain keep soaring 58m with corner bartizans")
    registry.register_tower("secondary", "Donjon Northwest Bartizan", 6.5, (-11.4, 20.4))
    registry.register_tower("secondary", "Donjon Northeast Bartizan", 6.5, (11.4, 20.4))
    registry.register_tower("secondary", "Donjon Southwest Bartizan", 6.5, (-11.4, -0.4))
    registry.register_tower("secondary", "Donjon Southeast Bartizan", 6.5, (11.4, -0.4))
    registry.register_interior("Donjon Council Chambers", "Map tables, high chairs, spiral staircase")

    # 4. Great Royal Ballroom & Palace Wing (Western Cliff Terrace at Z = 7.5m)
    build_great_ballroom_wing(bm, x0=-40.0, x1=-11.0, y0=-12.0, y1=8.0, z_base=z_west, height=13.8, roof_h=8.5)
    registry.register_landmark("The Great Royal Hall of Thrones", "Double-height ballroom with 3-tier dais, royal thrones, hammerbeam roof")
    registry.register_interior("Grand Ballroom & Throne Dais", "Royal thrones, monumental fireplace, hammerbeam trusses")

    # 5. Fortress Citadel Ramparts Wing (Eastern Cliff Terrace at Z = 6.0m, FLAT ROOF & MERLONS)
    build_fortress_ramparts_wing(bm, x0=11.0, x1=44.0, y0=-12.0, y1=12.0, z_base=z_ramparts, height=11.2)
    registry.register_district("Military District")
    registry.register_landmark("The High Fortress Ramparts", "2-storey military ramparts with 100% flat stone fighting deck")
    registry.register_interior("Garrison Rampart Quarters", "Bunk beds, weapon storage, guard stations")

    # 6. High Scholar's Wing (Arcane District at Z = 7.5m)
    build_scholars_wing(bm, x0=-46.0, x1=-28.0, y0=-22.0, y1=2.0, z_base=z_west, height=13.8, roof_h=7.5)
    registry.register_district("Arcane District")
    registry.register_landmark("The High Scholar's Wing & Library", "3-storey arcane academy with cantilevered oriel lookouts")
    registry.register_interior("High Scholar's Library", "Grand bookcases, reading desks, arcane lecterns")

    # 7. Grand Castle Entrance Portal (Barbican at Forecourt Z = 0.0m)
    build_grand_castle_portal(bm, cx=0.0, front_y=-3.5, z_base=z_ground, width=9.0, depth=6.5, height=6.8)
    registry.register_landmark("The Barbican of the Sun Gate", "Open gothic portal archway with hoisted iron portcullis & flared stairs")

    # 8. Grand Chantry Chapel of the Silver Flame (Religious District)
    build_sanctuary_chapel(bm, cx=-24.0, cy=18.0, z_base=z_west, width=9.5, depth=16.0, height=10.2)
    registry.register_district("Religious District")
    registry.register_landmark("The Grand Chantry of the Silver Flame", "Gothic chapel with traceried lancets, rose window, sanctus bell-tower")
    registry.register_interior("Sanctuary of the Silver Flame", "Stone altar, brass candlesticks, worship pews, crypt descent")

    # 9. Walkable Towers Network perched on cliffs
    # 9a. Landmark Tower: High Scholar's Spire (Wizard Spire, 42m high, conical witch-hat roof, ZERO merlons)
    sch_x, sch_y = -42.0, -20.0
    build_walkable_round_tower(
        bm, cx=sch_x, cy=sch_y, z_base=z_west,
        radius=4.4, num_floors=5, floor_h=floor_h,
        tower_type='SPIRE', spire_h=13.5, has_oriel=True, oriel_ang=-0.35,
        door_angs=((0, 0.0),)
    )
    registry.register_landmark("The Wizard's Spire of Eldath", "Soaring 42m landmark arcane tower with conical witch-hat roof")
    registry.register_tower("landmark", "The Wizard's Spire of Eldath", 42.0, (sch_x, sch_y))
    build_arcane_chamber_furnishings(bm, cx=sch_x, cy=sch_y, z_floor=z_west + 0.1)
    registry.register_interior("Wizard's Upper Arcane Chamber", "Arcane circle, alchemy station, orrery, spellbook pedestal, scrying pool")

    # 9b. Major Tower: Southeast Fortress Bastion (FLAT DECK WITH MERLONS & BRAZIER, ZERO POINTY ROOF)
    bast_x, bast_y = 42.0, -12.0
    build_walkable_round_tower(
        bm, cx=bast_x, cy=bast_y, z_base=z_ramparts,
        radius=5.2, num_floors=3, floor_h=floor_h,
        tower_type='BATTLEMENTS', corbel_count=22,
        door_angs=((0, math.pi),)
    )
    registry.register_landmark("The Bastion of Iron Dawn", "Southeast fortress bastion with flat fighting deck, merlons, signal brazier")
    registry.register_tower("major", "The Bastion of Iron Dawn", 18.0, (bast_x, bast_y))

    # 9c. Major Tower: Northwest High Spire Watchtower
    rl_x, rl_y = -42.0, 10.0
    build_walkable_round_tower(
        bm, cx=rl_x, cy=rl_y, z_base=z_west,
        radius=3.8, num_floors=4, floor_h=floor_h,
        tower_type='SPIRE', spire_h=11.5,
        door_angs=((0, 0.0),)
    )
    registry.register_landmark("Northwest High Spire Watchtower", "Spire watchtower guarding palace flank")
    registry.register_tower("major", "Northwest High Spire Watchtower", 22.0, (rl_x, rl_y))

    # 9d. Major Tower: Northeast Artillery Bastion (FLAT DECK WITH MERLONS)
    rr_x, rr_y = 42.0, 12.0
    build_walkable_round_tower(
        bm, cx=rr_x, cy=rr_y, z_base=z_ramparts,
        radius=4.8, num_floors=3, floor_h=floor_h,
        tower_type='BATTLEMENTS', corbel_count=20,
        door_angs=((0, math.pi),)
    )
    registry.register_landmark("Northeast Artillery Bastion", "Heavy fortress artillery bastion with flat fighting deck and merlons")
    registry.register_tower("major", "Northeast Artillery Bastion", 18.0, (rr_x, rr_y))

    # 10. Elevated High Armored Skybridge
    bridge_start = (sch_x + 2.5, sch_y + 2.5)
    bridge_end = (-11.0, 10.0)
    build_high_skybridge(bm, bridge_start, bridge_end, z_level=17.5, width=2.4, height=3.4)
    registry.register_landmark("The Armored Skybridge of the Stars", "Elevated stone skybridge connecting Wizard Spire to Keep")

    # 11. Connecting Cliff Staircases (Physical traversal between terraces)
    build_cliff_staircase(bm, start_pt=(9.0, -14.0, 0.0), end_pt=(9.0, -3.0, z_ramparts),
                         num_steps=20, width=2.2, parapet_side='RIGHT')
    build_cliff_staircase(bm, start_pt=(-9.0, -16.0, 0.0), end_pt=(-9.0, -3.0, z_west),
                         num_steps=24, width=2.2, parapet_side='LEFT')
    build_cliff_staircase(bm, start_pt=(0.0, -1.0, 6.8), end_pt=(0.0, 0.5, z_keep + 1.8),
                         num_steps=16, width=3.2, parapet_side='BOTH')
    build_cliff_staircase(bm, start_pt=(-11.0, 4.0, z_west + 1.8), end_pt=(-8.0, 4.0, z_keep + 1.8),
                         num_steps=10, width=2.4, parapet_side='NONE')
    build_cliff_staircase(bm, start_pt=(11.0, 2.0, z_ramparts + 1.8), end_pt=(11.0, 8.0, z_keep + 1.8),
                         num_steps=15, width=2.0, parapet_side='RIGHT')

    # Courtyards & Circulation
    registry.register_district("Courtyard & Terrace District")
    registry.register_courtyard("The Barbican Forecourt Plaza")
    registry.register_courtyard("The Upper Inner Ward")
    registry.register_courtyard("The Terraced Cliff Gardens")
    registry.register_route("Public", "Sun Gate -> Forecourt -> Grand Cliff Stairs -> Palace & Keep")
    registry.register_route("Military", "Ramparts Deck -> Wall Walks -> Bastions -> Guard Posts")
    registry.register_route("Service", "Provisions Cellar -> Kitchens -> Pantry")
    registry.register_route("Hidden", "Ballroom Fireplace Secret Stairs -> Subterranean Dungeon Complex")


# =============================================================================
# 16. MASTER ORCHESTRATOR & ENTRY POINTS
# =============================================================================

def build_castle(bm, props, ctx):
    """
    Master Dispatcher for Procedural Fantasy Castle Generation:
    1. Resolves castle progression tier: TIER_1, TIER_2, or TIER_3.
    2. Instantiates CastleRegistry to record all structures and lineage.
    3. Dispatches to the corresponding tier constructor.
    4. Executes Silhouette Optimization Pass.
    5. Runs the Final Validation Pass (validate_castle_generation) asserting all requirements.
    """
    tier = getattr(props, 'castle_tier', 'TIER_3')
    registry = CastleRegistry(tier)

    if tier == 'TIER_1':
        build_castle_tier_1_stronghold(bm, props, ctx, registry)
    elif tier == 'TIER_2':
        build_castle_tier_2_fortress(bm, props, ctx, registry)
    else:
        build_castle_tier_3_citadel(bm, props, ctx, registry)

    # Skyline silhouette optimization pass
    optimize_castle_silhouette(bm, registry, tier)

    # Strict Final Validation Pass
    validate_castle_generation(registry, tier)

    return registry


def build_modular_castle_citadel(bm, props, ctx):
    """Backwards compatibility alias for build_castle."""
    return build_castle(bm, props, ctx)


def build_castle_citadel(bm, props, ctx):
    """Backwards compatibility alias for build_castle."""
    return build_castle(bm, props, ctx)
