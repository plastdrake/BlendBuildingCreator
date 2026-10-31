"""
Nasher's castle composer: half-timbered halls, a chapel and round towers terraced up a craggy
mount and built hard against one another so they read as one castle. It grows from a frontier
hold (T1) through a fortress (T2) to a fantasy capital (T3); positions never change between tiers.
"""

import math

from .nasher_site import (
    FORECOURT, TERRACE, build_citadel_mount, build_ramp_stairs, build_rim_walls,
    build_cliff_paved_roads, ground_z, ring_towers,
)
from .castle import build_walkable_round_tower
from .battlement import build_battlement_run
from .nasher_dungeon import build_nasher_dungeon
from .estate import _merge_generated_building, build_estate_chapel
from ..materials import MAT_INDEX_STONE, MAT_INDEX_CUT_STONE
from ..mesh_utils import create_beveled_box

_FLOOR_H = 3.7

# id, first_tier, x, y, pad_z, width, depth, floors, rot_deg, shape, wing_facade, wing_w, wing_d, roof_h
_HALLS = (
    ("keep", 1, 0.0, 40.0, 14.0, 24.0, 16.0, 4, 0.0, 'T_SHAPE', 'BACK', 14.0, 5.5, 10.5),
    ("great_hall", 1, -15.0, 0.0, 8.0, 22.0, 10.0, 5, 0.0, 'T_SHAPE', 'FRONT', 8.0, 5.0, 7.5),
    ("east_hall", 2, 15.0, 0.0, 8.0, 22.0, 10.0, 5, 0.0, 'T_SHAPE', 'FRONT', 8.0, 5.0, 7.0),
    ("barracks", 2, -20.0, -28.5, 3.0, 14.0, 9.0, 2, 5.0, 'RECTANGLE', 'FRONT', 0.0, 0.0, 5.5),
    ("armory", 2, 20.0, -28.5, 3.0, 14.0, 9.0, 2, -5.0, 'RECTANGLE', 'FRONT', 0.0, 0.0, 5.5),
    ("archive_hall", 3, 20.5, 40.0, 14.0, 17.0, 10.0, 3, 0.0, 'RECTANGLE', 'FRONT', 0.0, 0.0, 7.0),
)

# x, y, radius, floors, spire_h, first_tier, rank, spire_roof. Every tower is walkable inside
# (2 m wide wall stair), so none is thinner than 4.4 m. Flank towers are free-standing with open courtyard access.
_TOWERS = (
    (-33.5, -8.0, 4.2, 4, 10.0, 2, 'major', False),
    (33.5, -8.0, 4.2, 4, 10.0, 2, 'major', False),
    (-27.6, 40.0, 4.2, 5, 14.0, 2, 'landmark', True),
    (48.0, 26.0, 4.4, 4, 10.0, 3, 'major', False),
)

# Room mix per hall. The outlying garrison houses get a real kitchen, mess
# hall and store room downstairs with dormitory bedrooms above; the great
# halls are residential; the keep is a palace with a royal kitchen.
_HALL_PROGRAM = {
    'keep': 'PALACE',
    'great_hall': 'RESIDENTIAL',
    'east_hall': 'RESIDENTIAL',
    'barracks': 'GARRISON',
    'armory': 'GARRISON',
    'archive_hall': 'CIVIC',
}


def _hall_overrides(tier, w, d, floors, shape, facade, ww, wd, roof_h, hid=""):
    o = {
        'building_shape': shape,
        'num_floors': floors,
        'floor_height': _FLOOR_H,
        'width': w,
        'depth': d,
        'wall_thickness': 0.38,
        'has_cantilever': tier > 1,
        'overhang_mode': 'SECOND_FLOOR_ONLY',
        'cantilever_overhang': 0.40,
        'wonkiness': 0.0,
        'has_foundation': True,
        'foundation_height': 1.2,
        'ground_floor_stone': tier > 1,
        'has_ceiling_beams': True,
        'has_stairs': floors > 1,
        'stair_style': 'STRAIGHT',
        'has_front_door': False if hid == "archive_hall" else True,
        'door_width': 1.9,
        'door_height': 2.8,
        'door_shape': 'ARCHED',
        'has_windows': True,
        'window_spacing': 2.6,
        'has_shutters': True,
        'shutter_state': 'OPEN',
        'has_timber_framing': tier > 1,
        'timber_diagonals': tier > 1,
        'roof_style': 'GABLE',
        'roof_orientation': 'LEFT_RIGHT',
        'roof_height': roof_h,
        'roof_overhang': 0.8,
        'has_roof_shingles': True,
        'has_dormers': True,
        'dormer_count': 3,
        'dormer_sides': 'BOTH',
        'has_chimney': True,
        'chimney_pos_x': 0.65,
        'tier1_wall_style': 'LOGS',
        'tier1_roof_style': 'WOOD_SHINGLES',
        'material_tier': 'TIER_3' if tier == 3 else ('TIER_2' if tier == 2 else 'TIER_1'),
        'wall_material_override': 'STUCCO' if tier == 3 else ('WOOD_PLANKS' if tier == 2 else 'LOGS'),
        'physical_siding': tier == 1,
        'has_exposed_brick': False,
        # Every hall of the castle gets a real room mix instead of the generic
        # fallback, so the interiors read as proper living quarters.
        'interior_program': _HALL_PROGRAM.get(hid, 'RESIDENTIAL'),
        'interior_partition_style': 'AUTO',
        'has_interior_walls': True,
    }
    if shape != 'RECTANGLE':
        o.update({'wing_placement': facade, 'wing_width': ww, 'wing_depth': wd,
                  'wing_floors': max(1, floors - 1),
                  # East hall's wing sits on the free (west) side so it never
                  # overlaps the east connecting wing.
                  'wing_side': 'LEFT' if hid == 'east_hall' else 'RIGHT'})
    return o


def _hall_floors(tier, floors, hid):
    if hid == "keep" and tier == 1:
        return 2
    if hid in ("great_hall", "east_hall"):
        return 5 if tier == 3 else (4 if tier == 2 else 3)
    return floors if tier == 3 else max(1, floors - (2 if tier == 1 else 1))


def _build_halls(bm, props, tier):
    for hid, first, x, y, pz, w, d, floors, rot, shape, facade, ww, wd, rh in _HALLS:
        if first > tier:
            continue
        fl = _hall_floors(tier, floors, hid)
        ov = _hall_overrides(tier, w, d, fl, shape, facade, ww, wd, rh * 1.3, hid)
        extra_doors = []
        extra_win_excl = []
        if hid == "great_hall":
            # Floor 3 skybridge doorway on East facade (-X in world = RIGHT (+X) in local space)
            if tier >= 2:
                extra_doors.append({'floor_idx': 3, 'facade': 'RIGHT', 'pos': 0.0, 'w': 2.2, 'h': 3.2, 'is_portal': True})
                extra_win_excl.append({'facade': 'RIGHT', 'min': -2.0, 'max': 2.0, 'floor_min': 3, 'floor_max': 4})
            # Connecting wing doorway on North facade (+Y in world = BACK in local space)
            # West Connecting Wing is at cx = -8.5. Great hall center is -15.0, so local pos = -8.5 - (-15.0) = 6.5
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'BACK', 'pos': 6.5, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'BACK', 'min': 1.4, 'max': 11.5, 'floor_min': 0, 'floor_max': 4})
        elif hid == "east_hall":
            ov['stair_placement'] = 'RIGHT'
            # Floor 3 skybridge doorway on West facade (+X in world = LEFT (-X) in local space)
            if tier >= 2:
                extra_doors.append({'floor_idx': 3, 'facade': 'LEFT', 'pos': 0.0, 'w': 2.2, 'h': 3.2, 'is_portal': True})
                extra_win_excl.append({'facade': 'LEFT', 'min': -2.0, 'max': 2.0, 'floor_min': 3, 'floor_max': 4})
            # Connecting wing doorway on North facade (+Y in world = BACK in local space)
            # East Connecting Wing is at cx = 16.5. East hall center is 15.0, so local pos = 16.5 - 15.0 = 1.5
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'BACK', 'pos': 1.5, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'BACK', 'min': -3.6, 'max': 6.6, 'floor_min': 0, 'floor_max': 4})
        elif hid == "keep":
            ov['has_basement_stair'] = True
            # The stair outcrop must be wide enough to roof the whole
            # basement opening; the old 2.4m mini-wing left the shaft edge
            # and the floor behind the stair exposed.
            ov['mini_wing_width'] = max(6.8, float(getattr(props, 'mini_wing_width', 0.0)))
            ov['mini_wing_depth'] = max(3.2, float(getattr(props, 'mini_wing_depth', 0.0)))
            ov['mini_wing_random_size'] = False
            ov['window_left'] = False
            ov['has_throne_room'] = True
            ov['has_double_height'] = True
            ov['has_cantilever'] = False
            ov['cantilever_overhang'] = 0.0
            # A castle keep must have a working kitchen.
            ov['has_royal_kitchen'] = True
            ov['interior_program'] = 'PALACE'
            if tier == 3:
                ov['wall_splits'] = {'RIGHT': [3.0, 13.0]}
                ov['timber_exclusions'] = {'RIGHT': [(3.0, 13.0)]}
                ov['window_right'] = False
            # Floor 0 chapel-link doorway on West facade (-X in world = LEFT in local space)
            # Positioned at pos=3.8 (+Y in local space, world Y = 43.8) well clear of the
            # Keep interior stairs at y in [-1.8, +1.8] (world Y in [38.2, 41.8]).
            if tier >= 2:
                extra_doors.append({'floor_idx': 0, 'facade': 'LEFT', 'pos': 3.8, 'w': 2.2, 'h': 2.85, 'is_portal': True})
            # Floor 0 west connecting wing doorway on South facade (-Y in world = FRONT in local space)
            # West Connecting Wing is at cx = -8.5. Keep center is 0.0, so local pos = -8.5
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'FRONT', 'pos': -8.5, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'FRONT', 'min': -12.5, 'max': -3.4, 'floor_min': 0, 'floor_max': 4})
                # Floor 0 portal to Archive Hall on East facade (+X in world = RIGHT in local space)
                extra_doors.append({'floor_idx': 0, 'facade': 'RIGHT', 'pos': 0.0, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'RIGHT', 'min': -5.5, 'max': 5.5, 'floor_min': 0, 'floor_max': 4})
        elif hid == "archive_hall":
            ov['has_front_door'] = False
            ov['window_left'] = False
            ov['has_cantilever'] = False
            ov['roof_abut_left'] = True
            ov['gable_left'] = False
            ov['stair_placement'] = 'RIGHT'
            ov['timber_left'] = False
            ov['corner_posts_left'] = False
            ov['building_archetype'] = 'CIVIC'
            # The royal archive wing: the great banquet hall lives on its open
            # ground floor, the upper storeys are proper chambers.
            ov['interior_program'] = 'ROYAL_ARCHIVE'
            ov['interior_partition_style'] = 'AUTO'
            ov['open_ground_floor'] = True
            # Floor 0 east connecting wing doorway on South facade (-Y in world = FRONT in local space)
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'FRONT', 'pos': -4.0, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'FRONT', 'min': -9.0, 'max': 1.1, 'floor_min': 0, 'floor_max': 4})
                # Floor 0 portal to Keep on West facade (-X in world = LEFT in local space)
                extra_doors.append({'floor_idx': 0, 'facade': 'LEFT', 'pos': 0.0, 'w': 2.4, 'h': 2.85, 'is_portal': True})
                extra_win_excl.append({'facade': 'LEFT', 'min': -5.5, 'max': 5.5, 'floor_min': 0, 'floor_max': 4})
        if extra_doors:
            ov['extra_doorways'] = extra_doors
        if extra_win_excl:
            ov['extra_window_exclusions'] = extra_win_excl
        _merge_generated_building(bm, props, ov, pos=(x, y, pz - 0.3), rot_z=math.radians(rot))
    if tier >= 2:
        # Left addition house: Armory, Storage & Gallery Hallway connecting Keep (x=-12.0) to Wizard Tower (x=-27.6)
        build_estate_chapel(
            bm, props, pos=(-18.2, 40.0, 14.11), rot_z=0.0,
            tier=f"TIER_{tier}", width=7.6, depth=12.0, floors=1,
            extra_overrides={
                'building_archetype': 'ARMORY',
                'interior_program': 'GARRISON',
                'interior_partition_style': 'AUTO',
                'has_interior_walls': True,
                'has_stairs': False,
                'has_chapel_kit': False,
                'has_bell_cote': False,
                'roof_overhang': 0.50,
                'extra_doorways': [
                    {'floor_idx': 0, 'facade': 'RIGHT', 'pos': 3.8, 'w': 2.2, 'h': 2.85, 'is_portal': True},
                    {'floor_idx': 0, 'facade': 'LEFT', 'pos': 0.0, 'w': 2.0, 'h': 2.85, 'is_portal': True},
                ],
                'extra_window_exclusions': [
                    {'facade': 'RIGHT', 'min': 2.0, 'max': 5.6, 'floor_min': 0, 'floor_max': 0},
                    {'facade': 'LEFT', 'min': -1.8, 'max': 1.8, 'floor_min': 0, 'floor_max': 0},
                ],
            }
        )
        # Dedicated ground corridor link joining Chapel east wall to Keep west wall
        # with clean walls, floor, ceiling, and timber portal casings encasing cut wall edges.
        from .building_connector import build_chapel_connector
        build_chapel_connector(bm, p_chapel=(-14.4, 43.8), p_keep=(-12.0, 43.8), floor_z=14.86, chapel_floor_z=14.86, tier=tier)


def _gate_link(bm, tier):
    """Enclosed skybridge link joining the two raised terrace halls high above the grand stair passage.

    Spans centrally between Great Hall and East Hall at y=0.0, connecting
    cleanly into their vertical gable end walls well clear of the front wing roofs;
    the deck sits exactly on the halls' 3rd-storey floor level (20.0) so both portals
    open flush with no step.
    """
    from .building_connector import build_skybridge_link
    fz = 20.00
    build_skybridge_link(
        bm,
        p1=(-4.0, 0.0),
        p2=(4.0, 0.0),
        width=3.4,
        floor_z=fz,
        ceiling_h=3.7,
        wall_thickness=0.55,
        roof_style='BATTLEMENTS',
        has_windows=True,
        num_windows=2,
        has_portals=True,
        has_underpass_arch=False,
        underpass_spring_z=14.5,
    )


def _tower_base(x, y, r, door_ang=None):
    if door_ang is not None:
        dx = x + (r - 0.2) * math.cos(door_ang)
        dy = y + (r - 0.2) * math.sin(door_ang)
        walk_z = max(ground_z(x, y), ground_z(dx, dy))
    else:
        walk_z = ground_z(x, y)
    return walk_z - 1.0


def _build_towers(bm, registry, tier):
    from .building_connector import build_tower_building_connector
    for x, y, r, floors, spire_h, first, rank, spire in _TOWERS:
        if first > tier:
            continue
        z = None
        roofed = spire and tier == 3
        # Direct door orientations connecting into adjacent buildings or bridge.
        # Flank towers aim their doors at the vestibule corridor (y=-4.2),
        # which lands inside both tower and hall footprints.
        stair_base = None
        if abs(x - 48.0) < 1.0:
            door_angs = ((1, math.pi),)  # West-facing doorway on Floor 1 to receive the wooden bridge
            # Calibrate base so Floor 1 sits precisely at z=14.86, matching the wooden bridge deck
            z = 14.86 - 4.2 - 1.0
            # Shift stair flight so Flight 0 lands at 170 deg and Flight 1 starts at 235 deg,
            # leaving the 180 deg doorway completely clear of stairs on an open floor landing.
            stair_base = 35.0
        elif abs(x - (-33.5)) < 1.0:
            door_angs = ((0, 0.0),)  # East-facing doorway on Floor 0 opening toward Great Hall courtyard
            z = _tower_base(x, y, r, door_ang=0.0)
        elif abs(x - 33.5) < 1.0:
            door_angs = ((0, math.pi),)  # West-facing doorway on Floor 0 opening toward East Hall courtyard
            z = _tower_base(x, y, r, door_ang=math.pi)
        elif abs(x - (-27.6)) < 1.0:
            door_angs = ((1, 0.0),)  # East-facing doorway on Floor 1 connecting into Armory (z=14.86)
            z = 14.86 - 4.2 - 1.0  # Floor 1 at 14.86 matching Armory and Keep floor level
            # Ensure stairs never cross the 0 deg East doorway:
            # Flight 0 starts at 180 deg (West) and lands at 315 deg (North-West).
            # Flight 1 starts at 60 deg (North-East) and climbs to 195 deg (South-West).
            # The entire Eastern arc (315 -> 0 -> 60) on Floor 1 is an open landing with zero stairs.
            stair_base = {0: 180.0, 1: 60.0, 'default': 60.0}
        else:
            d_ang = math.atan2(-y, -x)
            door_angs = ((0, d_ang),)
            z = _tower_base(x, y, r, door_ang=d_ang)

        build_walkable_round_tower(
            bm, cx=x, cy=y, z_base=z, radius=r,
            num_floors=floors + 1 if tier == 3 else floors,
            floor_h=4.2 if tier == 3 else 4.0,
            tower_type='SPIRE' if roofed else 'BATTLEMENTS', spire_h=spire_h,
            door_angs=door_angs,
            stair_base_deg=stair_base)

        # Architectural connector vestibule for the Wizard's Spire tying into the Armory Hall
        if abs(x - (-27.6)) < 1.0:
            build_tower_building_connector(
                bm, tower_cx=x, tower_cy=y, tower_r=r, tower_z_base=z,
                bld_wall_x=-22.0, bld_y_span=(34.0, 46.0),
                floor_zs=(14.86,),
                bld_floor_z=14.86,
                max_vest_z=17.6, hall_step=0.0
            )

        height = z + floors * 4.1 + (spire_h if roofed else 0.0)
        if abs(x - 48.0) < 1.0:
            registry.register_tower('major', "The East Bluff Bastion Tower", height, (x, y))
        elif rank == 'landmark':
            registry.register_tower('landmark', "The Wizard's Spire of Eldath", height, (x, y))
        else:
            registry.register_tower(rank, f"Castle Tower ({x:+.0f},{y:+.0f})", height, (x, y))
    for i, (x, y, r, floors) in enumerate(ring_towers(tier)):
        registry.register_tower('secondary', f"Wall Tower {i + 1}", floors * 4.1, (x, y))


def _register(registry, tier):
    r = registry
    if tier == 1:
        r.register_landmark("The Ancestral Old Keep", "Rough log keep crowning the rock")
        r.register_landmark("Chieftain's Longhouse", "Timber great hall on the middle terrace")
        r.register_landmark("The Timber Palisade Gate", "Stockade gate at the foot of the mount")
        r.register_tower('major', "Frontier Watchtower", 9.5, (0.0, -88.0))
        r.register_courtyard("The Frontier Bailey")
        r.register_dungeon_level(-1, "Provisions Cellar & Holding Pit", "Rough stone cellar")
        r.register_secret_passage("Cellar Trapdoor", "Rock Escarpment Exit", "Hidden escape route")
        r.register_interior("Chieftain's Great Hall", "Hearth, table, weapon racks")
        r.register_interior("Chieftain's Quarters", "Bed, chest, council table")
        r.register_route("Public", "Palisade Gate -> Rock Stair -> Longhouse -> Keep")
        r.register_route("Hidden", "Cellar Trapdoor -> Escarpment Egress")
        return
    r.register_landmark("The Ancestral Old Keep (Reinforced)", "Keep crowning the upper terrace")
    r.register_landmark("The Great Hall of Nasher", "Half-timbered hall on the middle terrace")
    r.register_landmark("The East Hall", "Gabled wing beside the grand stair")
    r.register_landmark("Garrison Barracks", "Soldiers' hall on the forecourt")
    r.register_landmark("The Armory", "Weapon hall on the forecourt")
    r.register_landmark("Sanctuary Chantry Chapel", "Gothic chapel built against the keep")
    r.register_landmark("The Wizard's Spire Rock", "Spire crowning the upper citadel")
    r.register_landmark("The Stone Gate and Curtain Wall", "Wall ringing the bailey")
    r.register_district("Religious District")
    r.register_district("Military District")
    r.register_courtyard("The Lower Bailey")
    r.register_courtyard("The Forecourt Terrace")
    r.register_courtyard("The Upper Inner Ward")
    r.register_dungeon_level(-1, "Vaulted Provisions & Wine Cellar", "Timber-braced stores")
    r.register_dungeon_level(-2, "Stone Prison Complex & Cells", "Barred cells, guard post")
    r.register_secret_passage("Chapel Altar Trapdoor", "Subterranean Crypt", "Secret crypt access")
    r.register_secret_passage("Dungeon Cells", "Armory Escape", "Hidden passage to the armory")
    r.register_interior("Keep Great Hall", "Hearth, council table")
    r.register_interior("Barracks Quarters", "Bunks and footlockers")
    r.register_route("Public", "Gate -> Forecourt -> Grand Stair -> Terrace -> Keep")
    r.register_route("Military", "Rim Walls -> Towers -> Curtain Wall")
    r.register_route("Hidden", "Chapel Trapdoor -> Crypt -> Cliff Egress")
    if tier == 2:
        return
    r.register_landmark("The Royal Archive Hall", "Library hall built against the keep")
    r.register_landmark("The Gate Block of the Terrace", "Stone block joining the terrace halls")
    r.register_landmark("The Barbican of the Sun Gate", "Gate towers and drawbridge")
    r.register_landmark("The Donjon of the High King", "Tallest keep in the realm")
    r.register_landmark("The West Connecting Gallery", "Stair-stepped gallery wing linking the Great Hall to the Keep")
    r.register_landmark("The East Connecting Wing", "Covered hall connecting East Hall to Archive Hall and the Bluff Bridge")
    r.register_landmark("The Covered Wooden Bluff Bridge", "Cozy timber trestle bridge spanning to the East Bluff")
    r.register_landmark("The East Bluff Bastion Tower", "Fortified tower guarding the eastern escarpment")
    r.register_landmark("The Grand Throne Room of the High King", "Soaring double-height hall with stepped dais, Royal Throne, heraldic banners and mezzanine gallery")
    r.register_landmark("Archive Hall Portal", "Monumental cased archway connecting Keep to the Royal Archive Hall")
    r.register_district("Royal District")
    r.register_district("Arcane District")
    r.register_district("Service District")
    r.register_district("Courtyard & Terrace District")
    r.register_dungeon_level(-3, "Deep Dungeon & Torture Chamber", "Gibbet cages, rack")
    r.register_dungeon_level(-4, "Ancient Crypts & Forgotten Ruins", "Sarcophagi, ruined arches")
    r.register_secret_passage("Ballroom Grand Fireplace", "Castle Dungeon", "Secret stairs to the cells")
    r.register_secret_passage("Donjon Royal Chambers", "Bedrock Escarpment", "Hidden escape tunnel")
    r.register_interior("Grand Hall & Throne Dais", "Thrones, fireplace")
    r.register_interior("Wizard's Arcane Chamber", "Arcane circle, orrery, scrying pool")


def build_nasher_castle(bm, props, ctx, registry, tier):
    """Compose the whole castle for tier 1..3 on the shared rock mount."""
    build_citadel_mount(bm, tier=tier)
    build_ramp_stairs(bm)
    build_cliff_paved_roads(bm, tier)

    if tier == 2:
        from .nasher_site import build_upper_citadel_perimeter_wall
        bld_forecourt = ((-27.5, -12.5, -34.0, -23.0), (12.5, 27.5, -34.0, -23.0))
        bld_terrace = ((-26.0, -4.0, -5.0, 5.0), (4.0, 26.0, -5.0, 5.0))
        build_rim_walls(bm, FORECOURT, 185.0, 355.0, height=3.0, thick=0.85, inset=0.98,
                        gate=True, bld_boxes=bld_forecourt)
        build_upper_citadel_perimeter_wall(bm, height=3.4, thick=0.90, bld_boxes=bld_terrace, tier=2)
    elif tier == 3:
        from .nasher_site import build_upper_citadel_perimeter_wall
        bld_forecourt = ((-27.5, -12.5, -34.0, -23.0), (12.5, 27.5, -34.0, -23.0))
        bld_upper = (
            (-26.0, -4.0, -5.0, 5.0), (4.0, 26.0, -5.0, 5.0),    # Great & East Halls
            (-18.5, -10.5, 4.5, 34.5), (12.5, 20.5, 4.5, 34.5),   # West & East Connecting Wings
            (-12.5, 12.5, 31.5, 48.5),                              # Keep
            (12.0, 29.0, 34.5, 45.5),                               # Archive Hall
            (-33.0, -22.5, 35.0, 45.0),                             # Wizard's Spire
            (43.0, 53.0, 21.0, 31.0),                             # East Bluff Tower
        )
        build_rim_walls(bm, FORECOURT, 185.0, 355.0, height=3.0, thick=0.85, inset=0.98,
                        gate=True, bld_boxes=bld_forecourt)
        build_upper_citadel_perimeter_wall(bm, height=3.4, thick=0.90, bld_boxes=bld_upper, tier=3)

    _build_halls(bm, props, tier)
    if tier >= 2:
        _gate_link(bm, tier)

    if tier == 3:
        from .building_connector import build_connecting_wing, build_wooden_bridge
        # West Connecting Wing linking Great Hall (y=5.0) to Keep (south wall y=32.0).
        # Decks sit flush with the connected ground floors (8.86 / 14.86).
        build_connecting_wing(
            bm, cx=-8.5, y_start=5.0, y_end=32.0, width=6.6,
            z_low=8.86, z_high=14.86, stair_y_start=15.0, stair_y_end=24.0,
            wall_y_north=32.0, roof_y_end_north=32.0
        )
        # East Connecting Wing linking East Hall (y=5.0) to Archive Hall (south wall y=35.0)
        build_connecting_wing(
            bm, cx=16.5, y_start=5.0, y_end=35.0, width=6.6,
            z_low=8.86, z_high=14.86, stair_y_start=15.0, stair_y_end=24.0,
            has_bridge_door=True, bridge_door_y=26.0,
            wall_y_north=35.0, roof_y_end_north=35.0,
            include_door_leaves=getattr(props, 'include_door_leaves', False)
        )
        # Open-timbered trestle bridge spanning across the chasm to East Bluff Tower
        build_wooden_bridge(
            bm, p_start=(19.8, 26.0), p_end=(43.6, 26.0),
            floor_z=14.86, width=2.6
        )

        from .building_connector import build_archive_hall_portal
        # Seamless integrated portal connecting Keep to Archive Hall across the x=12.0 double-wall joint
        build_archive_hall_portal(bm, x_wall=12.0, cy=40.0, z_floor=14.86, portal_w=2.40, portal_h=2.85)

    _build_towers(bm, registry, tier)
    build_nasher_dungeon(bm, tier)

    # Clean any detached or orphaned floating prop clutter across the castle grounds
    from .building_connector import clean_orphan_floating_props
    clean_orphan_floating_props(bm)

    _register(registry, tier)

