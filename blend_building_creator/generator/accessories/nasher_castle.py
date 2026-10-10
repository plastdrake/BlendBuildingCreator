"""
Nasher's castle composer: half-timbered halls, a chapel and round towers terraced up a craggy
mount and built hard against one another so they read as one castle. It grows from a frontier
hold (T1) through a fortress (T2) to a fantasy capital (T3); positions never change between tiers.
"""

import math

from .nasher_site import (
    FORECOURT, TERRACE, build_citadel_mount, build_ramp_stairs, build_rim_walls,
    ground_z, ring_towers,
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
    ("keep", 1, 0.0, 40.0, 14.0, 24.0, 16.0, 4, 0.0, 'T_SHAPE', 'BACK', 9.0, 5.0, 10.5),
    ("great_hall", 1, -15.0, 0.0, 8.0, 22.0, 10.0, 5, 0.0, 'T_SHAPE', 'FRONT', 8.0, 5.0, 7.5),
    ("east_hall", 2, 15.0, 0.0, 8.0, 22.0, 10.0, 5, 0.0, 'L_SHAPE', 'BACK', 7.0, 5.0, 7.0),
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
        'has_front_door': True,
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
        'material_tier': 'TIER_2' if tier > 1 else 'TIER_1',
        'wall_material_override': 'STUCCO' if tier > 1 else 'LOGS',
        'physical_siding': tier == 1,
        'has_exposed_brick': False,
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
        if hid == "great_hall":
            # Floor 3 skybridge doorway on East facade (-X in world = RIGHT (+X) in local space)
            if tier >= 2:
                extra_doors.append({'floor_idx': 3, 'facade': 'RIGHT', 'pos': -3.6, 'w': 2.0, 'h': 2.6, 'is_portal': True})
            # Floor 0 connecting wing doorway on North facade (+Y in world = BACK in local space)
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'BACK', 'pos': 0.5, 'w': 2.0, 'h': 2.6, 'is_portal': True})
        elif hid == "east_hall":
            ov['stair_placement'] = 'RIGHT'
            # Floor 3 skybridge doorway on West facade (+X in world = LEFT (-X) in local space)
            if tier >= 2:
                extra_doors.append({'floor_idx': 3, 'facade': 'LEFT', 'pos': -3.6, 'w': 2.0, 'h': 2.6, 'is_portal': True})
            # Floor 0 connecting wing doorway on North facade (+Y in world = BACK in local space)
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'BACK', 'pos': 1.5, 'w': 2.0, 'h': 2.6, 'is_portal': True})
        elif hid == "keep":
            ov['has_basement_stair'] = True
            ov['window_left'] = False
            # Floor 0 west connecting wing doorway on South facade (-Y in world = FRONT in local space)
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'FRONT', 'pos': -14.5, 'w': 2.0, 'h': 2.6, 'is_portal': True})
            # Floor 0 chapel-link doorway on West facade (-X in world = LEFT in local space)
            if tier >= 2:
                extra_doors.append({'floor_idx': 0, 'facade': 'LEFT', 'pos': 0.0, 'w': 2.0, 'h': 2.6, 'is_portal': True})
        elif hid == "archive_hall":
            # Floor 0 east connecting wing doorway on South facade (-Y in world = FRONT in local space)
            if tier == 3:
                extra_doors.append({'floor_idx': 0, 'facade': 'FRONT', 'pos': -4.0, 'w': 2.0, 'h': 2.6, 'is_portal': True})
        if extra_doors:
            ov['extra_doorways'] = extra_doors
        _merge_generated_building(bm, props, ov, pos=(x, y, pz - 0.3), rot_z=math.radians(rot))
    if tier >= 2:
        # Chapel positioned cleanly between Keep (x=-12.0) and Wizard Tower (x=-27.6, r=4.2)
        # with no side windows embedded into adjacent walls
        build_estate_chapel(
            bm, props, pos=(-18.2, 40.0, 13.7), rot_z=0.0,
            tier=f"TIER_{tier}", width=7.6, depth=12.0, floors=1,
            extra_overrides={'window_left': False, 'window_right': False, 'roof_overhang': 0.50}
        )
        # Architectural connecting link joining Chapel east wall to Keep west wall
        # (deck flush with the Keep ground floor; a two-tread stoop steps down
        # to the lower chapel floor at the east end)
        from .building_connector import build_skybridge_link
        build_skybridge_link(
            bm,
            p1=(-14.4, 40.0),
            p2=(-12.0, 40.0),
            width=3.8,
            floor_z=14.86,
            ceiling_h=3.2,
            has_underpass_arch=False,
            roof_style='GABLE',
            has_windows=False,
            has_portals=True
        )
        from ..mesh_utils import create_beveled_box as _cbb
        from ..materials import MAT_INDEX_CUT_STONE as _MCS
        # Entrance steps down from the link deck (14.90) to the chapel floor
        # (14.40): the deck-slab tongue forms the first tread, two solid stone
        # boxes grounded on the chapel floor slab complete the stair.
        for _sx0, _sx1, _stop in ((-15.00, -14.70, 14.72), (-15.32, -15.00, 14.56)):
            _sh = _stop - 14.38
            _cbb(bm, size=(_sx1 - _sx0, 1.90, _sh),
                 location=((_sx0 + _sx1) * 0.5, 40.0, 14.38 + _sh * 0.5),
                 mat_index=_MCS, bevel_amount=0.01)


def _gate_link(bm, tier):
    """Enclosed skybridge link joining the two raised terrace halls high above the grand stair passage.

    Narrow walkway shifted south of the hall midline (toward the gates); the
    deck sits exactly on the halls' 3rd-storey floor level (19.9) so both portals
    open flush with no step.
    """
    from .building_connector import build_skybridge_link
    fz = 19.9
    build_skybridge_link(
        bm,
        p1=(-4.0, -3.6),
        p2=(4.0, -3.6),
        width=3.4,
        floor_z=fz,
        ceiling_h=3.7,
        wall_thickness=0.55,
        roof_style='BATTLEMENTS',
        has_windows=True,
        num_windows=2,
        has_portals=True,
        has_underpass_arch=True,
        underpass_spring_z=14.5,
    )


def _tower_base(x, y, r):
    pts = [(x, y)] + [(x + (r + 0.5) * math.cos(a), y + (r + 0.5) * math.sin(a)) for a in
                      (i * math.pi / 8.0 for i in range(16))]
    return min(ground_z(px, py) for px, py in pts) - 1.2


def _build_towers(bm, registry, tier):
    from .building_connector import build_tower_building_connector
    for x, y, r, floors, spire_h, first, rank, spire in _TOWERS:
        if first > tier:
            continue
        z = _tower_base(x, y, r)
        roofed = spire and tier == 3
        # Direct door orientations connecting into adjacent buildings or bridge.
        # Flank towers aim their doors at the vestibule corridor (y=-4.2),
        # which lands inside both tower and hall footprints.
        if abs(x - (-33.5)) < 1.0:
            door_angs = ((0, 0.0),)  # East-facing doorway on Floor 0 opening toward Great Hall courtyard
        elif abs(x - 33.5) < 1.0:
            door_angs = ((0, math.pi),)  # West-facing doorway on Floor 0 opening toward East Hall courtyard
        elif abs(x - (-27.6)) < 1.0:
            door_angs = ((0, 0.0), (1, 0.0))  # East-facing doorways connecting into Chapel
        elif abs(x - 48.0) < 1.0:
            door_angs = ((1, math.pi),)  # West-facing doorway on Floor 1 to receive the wooden bridge
        else:
            door_angs = ((0, math.atan2(-y, -x)),)

        build_walkable_round_tower(
            bm, cx=x, cy=y, z_base=z, radius=r,
            num_floors=floors + 1 if tier == 3 else floors,
            floor_h=4.2 if tier == 3 else 4.0,
            tower_type='SPIRE' if roofed else 'BATTLEMENTS', spire_h=spire_h,
            door_angs=door_angs)

        # Architectural connector vestibule for the Wizard's Spire tying into the Chapel
        if abs(x - (-27.6)) < 1.0:
            build_tower_building_connector(
                bm, tower_cx=x, tower_cy=y, tower_r=r, tower_z_base=z,
                bld_wall_x=-22.0, bld_y_span=(34.0, 46.0),
                floor_zs=(14.0,),
                max_vest_z=17.2, hall_step=0.40
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
    build_citadel_mount(bm)
    build_ramp_stairs(bm)

    if tier == 2:
        from .nasher_site import build_upper_citadel_perimeter_wall
        bld_forecourt = ((-27.5, -12.5, -34.0, -23.0), (12.5, 27.5, -34.0, -23.0))
        bld_terrace = ((-26.0, -4.0, -5.0, 5.0), (4.0, 26.0, -5.0, 5.0),
                       (-38.2, -28.8, -12.7, -3.3), (28.8, 38.2, -12.7, -3.3))
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
            (-38.2, -28.8, -12.7, -3.3), (28.8, 38.2, -12.7, -3.3),  # Flank Towers
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
            bm, cx=-14.5, y_start=5.0, y_end=34.0, width=6.6,
            z_low=8.86, z_high=14.86, stair_y_start=15.0, stair_y_end=24.0,
            wall_y_north=32.0, roof_y_end_north=32.0
        )
        # East Connecting Wing linking East Hall (y=5.0) to Archive Hall (south wall y=35.0)
        build_connecting_wing(
            bm, cx=16.5, y_start=5.0, y_end=36.5, width=6.6,
            z_low=8.86, z_high=14.86, stair_y_start=15.0, stair_y_end=24.0,
            has_bridge_door=True, bridge_door_y=26.0,
            wall_y_north=35.0, roof_y_end_north=35.0
        )
        # Cozy covered wooden bridge spanning across the chasm to East Bluff Tower
        build_wooden_bridge(
            bm, p_start=(19.8, 26.0), p_end=(43.6, 26.0),
            floor_z=14.0, width=2.6
        )

    _build_towers(bm, registry, tier)
    build_nasher_dungeon(bm, tier)

    _register(registry, tier)

