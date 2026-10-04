"""Arcane interior furnishing composer for the whimsical Mage Tower.

Furnishes the spacious, undivided circular storeys of the Mage Tower with:
- Grand multi-tier library bookcases packed with grimoires, scrolls, and ladders
- Dedicated wizard workstations: Alchemy Station with alembics, flasks, and mortar
- Arcane focal pieces: Celestial Armillary Orrery, Enchanting Altar with floating crystal,
  Scrying Divination Pool with glowing liquid, and large Bubbling Ritual Cauldron
- Illuminated Spellbook Pedestals with open tomes and platter-rooted candles
- Reading alcoves with study desks, comfy armchairs, luxury carpets, and chandeliers
- Open, undivided floor plan on every level with intelligent collision clearance around
  the winding stairs, door portals, and panoramic windows.
"""

import math
import random
from mathutils import Vector, Matrix

from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR, MAT_INDEX_WOOD,
    MAT_INDEX_TIMBER, MAT_INDEX_GLASS, MAT_INDEX_IRON, MAT_INDEX_WAX,
    MAT_INDEX_LANTERN, MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_LEATHER_3,
    MAT_INDEX_BOOK_PAPER, MAT_INDEX_RUG_1, MAT_INDEX_RUG_2, MAT_INDEX_RUG_3,
)

from .interior_furniture import (
    build_chair, build_indoor_table, build_round_table, build_shelf,
    build_wardrobe, build_chest, build_desk, build_bookshelf, build_bookshelf_neat,
    build_book_pile_small, build_book_pile_large, build_chandelier,
    build_rug, build_sofa, build_armchair, build_bed, build_bottle_cluster,
    build_spellbook_pedestal, build_arcane_orrery, build_alchemy_station,
    build_scrying_pool, build_enchanting_table, build_magic_cauldron,
    build_grand_bookcase, build_arcane_circle,
)
from .lighting import build_chain_lantern


BAYS = 8
BAY_ANG = 2.0 * math.pi / BAYS
OFFSET = -math.pi * 0.5 - BAY_ANG * 0.5
STAIR_W = 1.85
STAIR_ARC = 135.0
STAIR_OPEN = 75.0
TABLE_SURF = 0.775
DESK_SURF = 0.79


def _local_to_world(pos, ang, lx, ly):
    """Transform local coordinates (lx, ly) in an object frame at pos with rotation ang to world coords."""
    c, s = math.cos(ang), math.sin(ang)
    return Vector((pos.x + lx * c - ly * s, pos.y + lx * s + ly * c, getattr(pos, 'z', 0.0)))


def _chair_ang_facing(target_x, target_y, chair_x, chair_y):
    """Rotation angle for chair/armchair/sofa so its front (-Y in local frame) faces directly toward (target_x, target_y)."""
    dx = target_x - chair_x
    dy = target_y - chair_y
    facing_dir = math.atan2(dy, dx)
    return facing_dir + math.pi * 0.5


def _norm_ang_deg(a):
    return a % 360.0


def _bay_candidates():
    """Angular centers (degrees) of the 8 tower wall bays."""
    return [math.degrees((b + 0.5) * BAY_ANG + OFFSET) % 360.0 for b in range(BAYS)]


def _ang_in_range(ang_deg, start_deg, end_deg):
    """True if ang_deg falls in [start_deg, end_deg] with circular wrap-around."""
    a = ang_deg % 360.0
    s = start_deg % 360.0
    e = end_deg % 360.0
    if s <= e:
        return s <= a <= e
    return a >= s or a <= e


def _overlaps_any(x, y, clearance_radius, occupied):
    """True if a disc at (x, y) collides with any already-placed furniture."""
    for ox, oy, orad in occupied:
        if math.hypot(x - ox, y - oy) < orad + clearance_radius + 0.05:
            return True
    return False


def _claim(occupied, x, y, clearance_radius):
    """Register a placed piece so later placements route around it."""
    occupied.append((x, y, clearance_radius))


def _outcrop_bay_clear(cand_deg, outcrops):
    """True when no outcrop doorway opens in this bay sector."""
    for ob in outcrops:
        o_ang = math.degrees((ob + 0.5) * BAY_ANG + OFFSET) % 360.0
        if _ang_in_range(cand_deg, o_ang - 16.0, o_ang + 16.0):
            return False
    return True


def _under_stair_headroom(ang_deg, fl, stair_configs, level_h, shaft_storeys):
    """Headroom beneath the climbing flight at ang_deg, or None if not under it."""
    if fl >= shaft_storeys or fl >= len(stair_configs):
        return None
    s_ang, _ = stair_configs[fl]
    if _ang_in_range(ang_deg, s_ang, s_ang + STAIR_ARC):
        frac = ((ang_deg - s_ang) % 360.0) / STAIR_ARC
        return level_h * max(0.0, min(1.0, frac))
    return None


def _wall_spots(r_in, depth, fl, shaft_storeys, stair_configs, outcrops, occ,
                level_h, min_height=0.0, foot=None, has_front_door=False):
    """Yield (x, y, yaw) placements with backs to the wall.

    Clear bays first, then slots tucked under the high flight with enough
    headroom. Stair entries, landings, doorways and claimed furniture are all
    refused, so room middles and walking paths stay empty. Local +Y faces the
    wall (backs), local -Y faces the room.
    """
    if foot is None:
        foot = depth * 0.5
    rr = r_in - depth * 0.5 - 0.12
    if rr < 0.6:
        return
    for cand_deg in _bay_candidates():
        cand_rad = math.radians(cand_deg)
        x, y = rr * math.cos(cand_rad), rr * math.sin(cand_rad)
        if _overlaps_any(x, y, foot, occ):
            continue
        yaw = cand_rad - math.pi * 0.5
        if _is_wall_zone_clear(cand_deg, fl, shaft_storeys, stair_configs, outcrops,
                               has_front_door):
            yield x, y, yaw
            continue
        h = _under_stair_headroom(cand_deg, fl, stair_configs, level_h, shaft_storeys)
        if (h is not None and h >= min_height + 0.5
                and _outcrop_bay_clear(cand_deg, outcrops)):
            if fl < len(stair_configs):
                s_ang, _ = stair_configs[fl]
                if ((cand_deg - s_ang) % 360.0) < 0.35 * STAIR_ARC:
                    continue  # low entry apron: walking line, not a nook
            yield x, y, yaw


def _take_wall_spot(r_in, depth, fl, shaft_storeys, stair_configs, outcrops, occ,
                    level_h, min_height=0.0, foot=None, has_front_door=False):
    """First free wall placement, or (None, None, None) when walls are full."""
    for x, y, yaw in _wall_spots(r_in, depth, fl, shaft_storeys, stair_configs,
                                 outcrops, occ, level_h, min_height, foot,
                                 has_front_door):
        return x, y, yaw
    return None, None, None


def _is_wall_zone_clear(ang_deg, fl, shaft_storeys, stair_configs, outcrop_bays, has_front_door=True):
    """Check if an angular sector along the perimeter wall is free from stairs, doorways, and landings."""
    # 1. Front door on floor 0 (Bay 0: centered at -90 deg / 270 deg)
    if fl == 0 and has_front_door:
        if _ang_in_range(ang_deg, 245.0, 295.0):
            return False

    # 2. Climbing staircase for this floor (if below top shaft storey)
    if fl < shaft_storeys and fl < len(stair_configs):
        s_ang, _ = stair_configs[fl]
        if _ang_in_range(ang_deg, s_ang - 8.0, s_ang + STAIR_ARC + 12.0):
            return False
        # 2b. Stair entry walkway: tall furniture never crowds the flight's foot.
        if _ang_in_range(ang_deg, s_ang - 38.0, s_ang + 30.0):
            return False

    # 3. Landing & exit from stair flight below (floors >= 1)
    if fl > 0 and (fl - 1) < len(stair_configs):
        prev_s_ang, _ = stair_configs[fl - 1]
        prev_top_landing = prev_s_ang + STAIR_ARC
        if _ang_in_range(ang_deg, prev_top_landing - STAIR_OPEN - 10.0, prev_top_landing + 34.0):
            return False

    # 4. Outcrop doorways on this storey
    for ob in outcrop_bays:
        o_ang = math.degrees((ob + 0.5) * BAY_ANG + OFFSET) % 360.0
        if _ang_in_range(ang_deg, o_ang - 15.0, o_ang + 15.0):
            return False

    return True


def _is_floor_pos_safe(x, y, clearance_radius, fl, shaft_storeys, stair_configs, r_in,
                        has_front_door=False, outcrop_bays=(), occupied=()):
    """Check if placing an item of clearance_radius at (x, y) is completely clear
    of stairs, support pillars, curved landing railings, floor openings, doorways,
    and already-placed furniture (occupied discs)."""
    d = math.hypot(x, y)
    if d + clearance_radius > r_in - 0.15:
        return False

    r_stair_inner = max(0.8, r_in - STAIR_W)
    # If the object's outer boundary is safely inside the central area away from the stairs
    if d + clearance_radius < r_stair_inner - 0.20:
        if fl == 0 and has_front_door:
            ang_deg = math.degrees(math.atan2(y, x)) % 360.0
            if _ang_in_range(ang_deg, 245.0, 295.0) and d > 0.8:
                return False
        return not _overlaps_any(x, y, clearance_radius, occupied)

    # The object extends into the outer zone where stairs, pillars, and landings live!
    ang_deg = math.degrees(math.atan2(y, x)) % 360.0
    half_ang_deg = math.degrees(math.atan2(clearance_radius, max(0.5, d))) + 8.0

    # 1. Front door
    if fl == 0 and has_front_door:
        for test_a in (ang_deg - half_ang_deg, ang_deg, ang_deg + half_ang_deg):
            if _ang_in_range(test_a, 240.0, 300.0):
                return False

    # 2. Climbing staircase for this floor (treads, stringers, support pillars under steps)
    if fl < shaft_storeys and fl < len(stair_configs):
        s_ang, _ = stair_configs[fl]
        for test_a in (ang_deg - half_ang_deg, ang_deg, ang_deg + half_ang_deg):
            if _ang_in_range(test_a, s_ang - 15.0, s_ang + STAIR_ARC + 15.0):
                return False

    # 3. Landing & floor opening from flight below
    if fl > 0 and (fl - 1) < len(stair_configs):
        prev_s_ang, _ = stair_configs[fl - 1]
        prev_top = prev_s_ang + STAIR_ARC
        for test_a in (ang_deg - half_ang_deg, ang_deg, ang_deg + half_ang_deg):
            if _ang_in_range(test_a, prev_top - STAIR_OPEN - 16.0, prev_top + 30.0):
                return False

    # 4. Outcrop doorways
    for ob in outcrop_bays:
        o_ang = math.degrees((ob + 0.5) * BAY_ANG + OFFSET) % 360.0
        for test_a in (ang_deg - half_ang_deg, ang_deg, ang_deg + half_ang_deg):
            if _ang_in_range(test_a, o_ang - 16.0, o_ang + 16.0):
                return False

    # 5. Already-placed furniture on this storey
    return not _overlaps_any(x, y, clearance_radius, occupied)


def _find_safe_pos(candidate_angles_deg, target_r, clearance_radius, fl, shaft_storeys,
                   stair_configs, r_in, has_front_door=False, outcrop_bays=(), occupied=()):
    """Finds the best safe position among candidate angles, nudging inwards if needed."""
    for cur_r in (target_r, target_r * 0.85, target_r * 0.70, target_r * 0.55):
        for ang_deg in candidate_angles_deg:
            rad = math.radians(ang_deg)
            tx = cur_r * math.cos(rad)
            ty = cur_r * math.sin(rad)
            if _is_floor_pos_safe(tx, ty, clearance_radius, fl, shaft_storeys, stair_configs,
                                  r_in, has_front_door, outcrop_bays, occupied):
                return Vector((tx, ty, 0.0)), ang_deg
    return None, None


def furnish_mage_tower(bm, props, shaft_storeys, level_h, found_h,
                       R, wall_t, stair_configs, outcrop_by_floor,
                       crown_z, bel_r, bel_h, seed, door_bays_by_floor=None):
    """Furnish all storeys of the Mage Tower with thematic, open-plan arcane layouts."""
    if not bool(getattr(props, 'has_interior_furnishing', True)):
        return

    density = float(getattr(props, 'furnishing_density', 1.0))
    if density <= 0.05:
        return

    rng = random.Random(seed + 404)
    r_in = R - wall_t
    has_front_door = bool(getattr(props, 'has_front_door', True))

    # =========================================================================
    # 1. SHAFT STOREYS (Ground Floor -> Upper Shaft Floors)
    # =========================================================================
    for fl in range(shaft_storeys):
        z_floor = found_h + fl * level_h + 0.14
        door_map = door_bays_by_floor or {}
        outcrops = set(outcrop_by_floor.get(fl, ())) | set(door_map.get(fl, ()))
        fl_seed = seed + fl * 313

        if fl == 0:
            _furnish_ground_floor(bm, z_floor, r_in, level_h, stair_configs, outcrops,
                                  density, has_front_door, fl_seed)
        elif fl == 1:
            _furnish_library_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                                   stair_configs, outcrops, density, fl_seed)
        elif fl == 2 and shaft_storeys >= 4:
            _furnish_enchanter_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                                     stair_configs, outcrops, density, fl_seed)
        elif fl == shaft_storeys - 1 and shaft_storeys >= 3:
            _furnish_quarters_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                                    stair_configs, outcrops, density, fl_seed)
        else:
            _furnish_archive_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                                   stair_configs, outcrops, density, fl_seed)

    # =========================================================================
    # 2. CANTILEVERED BELVEDERE / CELESTIAL OBSERVATORY (THE CROWN)
    # =========================================================================
    inner_bel_r = bel_r - wall_t
    _furnish_crown_observatory(bm, crown_z + 0.14, inner_bel_r, bel_h,
                               shaft_storeys, stair_configs, density, seed + 808)


# -----------------------------------------------------------------------------
# Floor Furnishing Handlers
# -----------------------------------------------------------------------------

def _furnish_ground_floor(bm, z_floor, r_in, level_h, stair_configs, outcrops,
                          density, has_front_door, seed):
    """Ground Storey: Grand Arcane Entrance Hall & Alchemy Laboratory.

    Everything stands against the walls; the middle and the stair paths stay
    empty. Local +Y is the wall side, local -Y faces the room.
    """
    rng = random.Random(seed)
    is_compact = (r_in < 4.2)  # Tier 1 small tower check
    occ = []
    FL, SH = 0, 99

    # 1. Grand ornate runner carpet leading from the front entrance inward
    rug_w = min(1.8, r_in * 0.48) if is_compact else 2.2
    build_rug(bm, x=0.0, y=-r_in * 0.45, z_ground=z_floor, ang=0.0,
              width=rug_w, length=r_in * 0.75, rug_style=1)

    # 2. Grand bookcases line every free wall bay (stair feet refused, the
    #    void under the high flight allowed when headroom fits).
    case_h = min(3.4, level_h - 0.8)
    bc_w = min(2.1, r_in * 0.65) if is_compact else 2.3
    for bx, by, bang in _wall_spots(r_in, 0.55, FL, SH, stair_configs, outcrops,
                                    occ, level_h, case_h, bc_w * 0.5,
                                    has_front_door):
        build_grand_bookcase(bm, x=bx, y=by, z_ground=z_floor, ang=bang,
                             width=bc_w, height=case_h)
        _claim(occ, bx, by, bc_w * 0.5)

    # 3. Alchemy bench, shelf-side to the wall, work side facing the room.
    alch_len = 1.75 if is_compact else 2.2
    alch_w = 0.76 if is_compact else 0.90
    ax, ay, aang = _take_wall_spot(r_in, alch_w + 0.3, FL, SH, stair_configs,
                                   outcrops, occ, level_h, 1.4, alch_len * 0.52,
                                   has_front_door)
    if ax is not None:
        build_alchemy_station(bm, x=ax, y=ay, z_ground=z_floor, ang=aang,
                              length=alch_len, width=alch_w)
        _claim(occ, ax, ay, alch_len * 0.52)

    # 4. Bubbling ritual cauldron breathing against the wall.
    cauld_r = 0.44 if is_compact else 0.52
    cx, cy, _cang = _take_wall_spot(r_in, cauld_r * 2.7, FL, SH, stair_configs,
                                    outcrops, occ, level_h, 0.9, cauld_r * 1.35,
                                    has_front_door)
    if cx is not None:
        build_magic_cauldron(bm, x=cx, y=cy, z_ground=z_floor,
                             ang=0.0, radius=cauld_r, height=0.64 if is_compact else 0.68)
        _claim(occ, cx, cy, cauld_r * 1.35)

    # 5. Scholar study table (spacious towers): long side along the wall,
    #    both chairs on the room side facing it.
    if not is_compact:
        tx, ty, tang = _take_wall_spot(r_in, 1.7, FL, SH, stair_configs, outcrops,
                                       occ, level_h, 0.9, 1.25, has_front_door)
        if tx is not None:
            table_w = 0.95
            tpos = Vector((tx, ty, 0.0))
            build_indoor_table(bm, x=tx, y=ty, z_ground=z_floor,
                               ang=tang, length=1.8, width=table_w)
            _claim(occ, tx, ty, 1.25)
            for side in (-0.45, 0.45):
                c_pos = _local_to_world(tpos, tang, side, -(table_w * 0.5 + 0.34))
                if _is_floor_pos_safe(c_pos.x, c_pos.y, 0.35, FL, SH, stair_configs,
                                      r_in, has_front_door, outcrops, occ):
                    c_ang = _chair_ang_facing(tx, ty, c_pos.x, c_pos.y)
                    build_chair(bm, x=c_pos.x, y=c_pos.y, z_ground=z_floor, ang=c_ang)
                    _claim(occ, c_pos.x, c_pos.y, 0.35)
            pile_pos = _local_to_world(tpos, tang, 0.50, 0.05)
            build_book_pile_small(bm, x=pile_pos.x, y=pile_pos.y,
                                  z_ground=z_floor + TABLE_SURF, ang=0.2)
            bot_pos = _local_to_world(tpos, tang, -0.50, -0.05)
            build_bottle_cluster(bm, x=bot_pos.x, y=bot_pos.y,
                                 z_ground=z_floor + TABLE_SURF, ang=0.8)

    # 6. Wizard lectern greeting visitors from the wall.
    px, py, pang = _take_wall_spot(r_in, 0.9, FL, SH, stair_configs, outcrops,
                                   occ, level_h, 1.5, 0.55, has_front_door)
    if px is not None:
        build_spellbook_pedestal(bm, x=px, y=py, z_ground=z_floor, ang=pang)
        _claim(occ, px, py, 0.55)

    # 7. Component chest and (spacious towers) potion shelf, both walled.
    hx, hy, hang = _take_wall_spot(r_in, 0.6, FL, SH, stair_configs, outcrops,
                                   occ, level_h, 0.7, 0.65, has_front_door)
    if hx is not None:
        build_chest(bm, x=hx, y=hy, z_ground=z_floor, ang=hang, width=1.1)
        _claim(occ, hx, hy, 0.65)

    if density >= 0.8 and not is_compact:
        sx, sy, sang = _take_wall_spot(r_in, 0.5, FL, SH, stair_configs, outcrops,
                                       occ, level_h, 1.7, 0.80, has_front_door)
        if sx is not None:
            build_shelf(bm, x=sx, y=sy, z_ground=z_floor, ang=sang, width=1.4)
            _claim(occ, sx, sy, 0.80)

    # 8. Grand hanging candle chandelier from the ceiling (not furniture).
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + level_h - 0.15, radius=0.65 if is_compact else 0.75)


def _furnish_library_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                           stair_configs, outcrops, density, seed):
    """The Great Arcane Library & Scriptorium: the scrying pool holds the
    middle; every desk, chair and lectern stands against the walls."""
    rng = random.Random(seed)
    is_compact = (r_in < 4.2)
    occ = []

    # 1. Tall Grand Bookcases lining every free wall bay.
    case_h = min(3.6, level_h - 0.7)
    bc_w = 2.1 if is_compact else 2.35
    for bx, by, bang in _wall_spots(r_in, 0.55, fl, shaft_storeys, stair_configs,
                                    outcrops, occ, level_h, case_h, bc_w * 0.5):
        build_grand_bookcase(bm, x=bx, y=by, z_ground=z_floor, ang=bang,
                             width=bc_w, height=case_h)
        _claim(occ, bx, by, bc_w * 0.5)

    # 2. Centerpiece: Divination Scrying Pool on a Sapphire Royal Carpet,
    #    claimed before anything else so the walls route around the middle.
    scrying_r = min(0.72 if is_compact else 1.05, r_in * 0.22)
    rug_size = min(2.4 if is_compact else 3.2, r_in * 0.65)
    build_rug(bm, x=0.0, y=0.0, z_ground=z_floor, width=rug_size, length=rug_size, rug_style=2)
    build_scrying_pool(bm, x=0.0, y=0.0, z_ground=z_floor, radius=scrying_r)
    _claim(occ, 0.0, 0.0, scrying_r + 0.15)

    # 3. Study desk backed to the wall, chair on the room side facing it.
    dx, dy, dang = _take_wall_spot(r_in, 1.0, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 0.9, 0.90)
    if dx is not None:
        dpos = Vector((dx, dy, 0.0))
        build_desk(bm, x=dx, y=dy, z_ground=z_floor, ang=dang, width=1.3)
        _claim(occ, dx, dy, 0.90)
        c_pos = _local_to_world(dpos, dang, 0.0, -0.60)
        if _is_floor_pos_safe(c_pos.x, c_pos.y, 0.35, fl, shaft_storeys, stair_configs,
                              r_in, False, outcrops, occ):
            c_ang = _chair_ang_facing(dx, dy, c_pos.x, c_pos.y)
            build_chair(bm, x=c_pos.x, y=c_pos.y, z_ground=z_floor, ang=c_ang)
            _claim(occ, c_pos.x, c_pos.y, 0.35)
        pile_pos = _local_to_world(dpos, dang, 0.30, 0.05)
        build_book_pile_small(bm, x=pile_pos.x, y=pile_pos.y,
                              z_ground=z_floor + DESK_SURF, ang=0.1)

    # 4. Reading armchair backed to the wall, side table tucked alongside it
    #    (never circled in the middle of the room).
    ex, ey, eang = _take_wall_spot(r_in, 1.1, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 1.1, 0.75)
    if ex is not None:
        epos = Vector((ex, ey, 0.0))
        a1_ang = _chair_ang_facing(0.0, 0.0, ex, ey)
        build_armchair(bm, x=ex, y=ey, z_ground=z_floor, ang=a1_ang)
        _claim(occ, ex, ey, 0.75)
        tab_pos = _local_to_world(epos, eang, 0.62, 0.05)
        if _is_floor_pos_safe(tab_pos.x, tab_pos.y, 0.35, fl, shaft_storeys,
                              stair_configs, r_in, False, outcrops, occ):
            build_round_table(bm, x=tab_pos.x, y=tab_pos.y, z_ground=z_floor, radius=0.32)
            _claim(occ, tab_pos.x, tab_pos.y, 0.35)
            build_bottle_cluster(bm, x=tab_pos.x, y=tab_pos.y,
                                 z_ground=z_floor + TABLE_SURF, ang=0.3)
        pile2 = _local_to_world(epos, eang, -0.60, 0.15)
        if not _overlaps_any(pile2.x, pile2.y, 0.30, occ):
            build_book_pile_large(bm, x=pile2.x, y=pile2.y, z_ground=z_floor, ang=0.4)

    # 5. Spellbook Pedestal for rare grimoires, walled.
    px, py, pang = _take_wall_spot(r_in, 0.9, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 1.5, 0.55)
    if px is not None:
        build_spellbook_pedestal(bm, x=px, y=py, z_ground=z_floor, ang=pang)
        _claim(occ, px, py, 0.55)

    # 6. Hanging illumination
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + level_h - 0.15, radius=0.68 if is_compact else 0.85)


def _furnish_enchanter_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                             stair_configs, outcrops, density, seed):
    """Enchanter's Sanctorum: ONE centerpiece (the enchanting altar in its
    summoning circle). The lectern and seating stand walled; the orrery
    keeps to the crown observatory."""
    rng = random.Random(seed)
    is_compact = (r_in < 4.2)
    occ = []

    # 1. Floor Inlaid Arcane Summoning Circle in the center
    circle_r = min(1.9 if is_compact else 2.5, r_in * 0.60)
    build_arcane_circle(bm, x=0.0, y=0.0, z_ground=z_floor, radius=circle_r)

    # 2. Enchanting Table alone in the heart of the circle, claimed first.
    table_r = 0.75 if is_compact else 0.85
    build_enchanting_table(bm, x=0.0, y=0.0, z_ground=z_floor, radius=table_r)
    _claim(occ, 0.0, 0.0, table_r + 0.15)

    # 3. Perimeter wall grand bookcases & artifact display cases.
    case_h = min(3.4, level_h - 0.8)
    bc_w = 2.1 if is_compact else 2.3
    for bx, by, bang in _wall_spots(r_in, 0.55, fl, shaft_storeys, stair_configs,
                                    outcrops, occ, level_h, case_h, bc_w * 0.5):
        build_grand_bookcase(bm, x=bx, y=by, z_ground=z_floor, ang=bang,
                             width=bc_w, height=case_h)
        _claim(occ, bx, by, bc_w * 0.5)

    # 4. Spellbook Pedestal holding ritual enchantments, walled.
    px, py, pang = _take_wall_spot(r_in, 0.9, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 1.5, 0.55)
    if px is not None:
        build_spellbook_pedestal(bm, x=px, y=py, z_ground=z_floor, ang=pang)
        _claim(occ, px, py, 0.55)

    # 5. Seating backed to the wall: a chair with its side table alongside,
    #    or (spacious) a sofa with one flanking armchair and a coffee table
    #    grouped in front of them — never a circle in the middle.
    if is_compact:
        ax, ay, aang = _take_wall_spot(r_in, 1.1, fl, shaft_storeys, stair_configs,
                                       outcrops, occ, level_h, 1.1, 0.80)
        if ax is not None:
            apos = Vector((ax, ay, 0.0))
            arm_ang = _chair_ang_facing(0.0, 0.0, ax, ay)
            build_armchair(bm, x=ax, y=ay, z_ground=z_floor, ang=arm_ang)
            _claim(occ, ax, ay, 0.80)
            build_rug(bm, x=ax, y=ay, z_ground=z_floor, width=1.6, length=1.6, rug_style=1)
            tab_pos = _local_to_world(apos, aang, 0.62, 0.05)
            if _is_floor_pos_safe(tab_pos.x, tab_pos.y, 0.35, fl, shaft_storeys,
                                  stair_configs, r_in, False, outcrops, occ):
                build_round_table(bm, x=tab_pos.x, y=tab_pos.y, z_ground=z_floor, radius=0.32)
                _claim(occ, tab_pos.x, tab_pos.y, 0.35)
                build_bottle_cluster(bm, x=tab_pos.x, y=tab_pos.y,
                                     z_ground=z_floor + TABLE_SURF, ang=0.3)
    else:
        gx, gy, gang = _take_wall_spot(r_in, 1.1, fl, shaft_storeys, stair_configs,
                                       outcrops, occ, level_h, 1.1, 1.05)
        if gx is not None:
            gpos = Vector((gx, gy, 0.0))
            sofa_ang = gang
            build_sofa(bm, x=gx, y=gy, z_ground=z_floor, ang=sofa_ang, length=1.9)
            _claim(occ, gx, gy, 1.05)
            rug_pos = _local_to_world(gpos, gang, 0.0, -0.9)
            build_rug(bm, x=rug_pos.x, y=rug_pos.y, z_ground=z_floor,
                      width=2.4, length=2.8, rug_style=1)
            arm1_pos = _local_to_world(gpos, gang, 1.55, 0.10)
            if _is_floor_pos_safe(arm1_pos.x, arm1_pos.y, 0.60, fl, shaft_storeys,
                                  stair_configs, r_in, False, outcrops, occ):
                arm1_ang = _chair_ang_facing(gx, gy, arm1_pos.x, arm1_pos.y)
                build_armchair(bm, x=arm1_pos.x, y=arm1_pos.y, z_ground=z_floor, ang=arm1_ang)
                _claim(occ, arm1_pos.x, arm1_pos.y, 0.60)
            tab_pos = _local_to_world(gpos, gang, 0.0, -1.05)
            if _is_floor_pos_safe(tab_pos.x, tab_pos.y, 0.50, fl, shaft_storeys,
                                  stair_configs, r_in, False, outcrops, occ):
                build_round_table(bm, x=tab_pos.x, y=tab_pos.y, z_ground=z_floor, radius=0.45)
                _claim(occ, tab_pos.x, tab_pos.y, 0.50)
                build_bottle_cluster(bm, x=tab_pos.x, y=tab_pos.y,
                                     z_ground=z_floor + TABLE_SURF, ang=0.3)

    # 6. Hanging illumination
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + level_h - 0.15, radius=0.68 if is_compact else 0.85)


def _furnish_quarters_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                            stair_configs, outcrops, density, seed):
    """Archmage's Private Sanctum & Grand Study. The altar cluster, desk and
    lounge all back onto walls; wardrobes only where a wall bay is free."""
    rng = random.Random(seed)
    is_compact = (r_in < 4.2)
    occ = []

    # 1. Grand Archmage lectern altar backed to the wall, rug beneath it.
    gx, gy, gang = _take_wall_spot(r_in, 1.4, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 1.5, 1.25)
    if gx is not None:
        gpos = Vector((gx, gy, 0.0))
        rug_pos = _local_to_world(gpos, gang, 0.0, -0.4)
        build_rug(bm, x=rug_pos.x, y=rug_pos.y, z_ground=z_floor,
                  width=2.2 if is_compact else 2.6, length=2.2 if is_compact else 2.8, rug_style=2)
        build_spellbook_pedestal(bm, x=gx, y=gy, z_ground=z_floor, ang=gang)
        _claim(occ, gx, gy, 1.25)
        pile_pos = _local_to_world(gpos, gang, 0.60, -0.30)
        if not _overlaps_any(pile_pos.x, pile_pos.y, 0.30, occ):
            build_book_pile_large(bm, x=pile_pos.x, y=pile_pos.y, z_ground=z_floor, ang=0.3)

    # 2. Antique Wardrobe: wall bays only, skipped when the walls are full.
    ward_w = 1.3 if is_compact else 1.5
    wx, wy, wang = _take_wall_spot(r_in, 0.75, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 2.1, 0.85)
    if wx is not None:
        build_wardrobe(bm, x=wx, y=wy, z_ground=z_floor, ang=wang,
                       width=ward_w, height=2.1)
        _claim(occ, wx, wy, 0.85)

    # 3. Writing desk backed to the wall, chair on the room side facing it.
    dx, dy, dang = _take_wall_spot(r_in, 1.0, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 0.9, 0.95)
    if dx is not None:
        dpos = Vector((dx, dy, 0.0))
        build_desk(bm, x=dx, y=dy, z_ground=z_floor, ang=dang, width=1.3)
        _claim(occ, dx, dy, 0.95)
        chair_pos = _local_to_world(dpos, dang, 0.0, -0.60)
        if _is_floor_pos_safe(chair_pos.x, chair_pos.y, 0.35, fl, shaft_storeys,
                              stair_configs, r_in, False, outcrops, occ):
            chair_ang = _chair_ang_facing(dx, dy, chair_pos.x, chair_pos.y)
            build_chair(bm, x=chair_pos.x, y=chair_pos.y, z_ground=z_floor, ang=chair_ang)
            _claim(occ, chair_pos.x, chair_pos.y, 0.35)
        pile_pos = _local_to_world(dpos, dang, 0.30, 0.05)
        build_book_pile_small(bm, x=pile_pos.x, y=pile_pos.y,
                              z_ground=z_floor + DESK_SURF, ang=0.2)

    # 4. Personal library bookcases lining every free wall bay.
    case_h = min(3.2, level_h - 0.8)
    bc_w = 2.1 if is_compact else 2.2
    for bx, by, bang in _wall_spots(r_in, 0.55, fl, shaft_storeys, stair_configs,
                                    outcrops, occ, level_h, case_h, bc_w * 0.5):
        build_grand_bookcase(bm, x=bx, y=by, z_ground=z_floor, ang=bang,
                             width=bc_w, height=case_h)
        _claim(occ, bx, by, bc_w * 0.5)

    # 5. Fireside armchair backed to the wall, side table tucked alongside it;
    #    a second chair mirrors it on the other side on spacious floors.
    lx, ly, lang = _take_wall_spot(r_in, 1.1, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 1.1, 1.10)
    if lx is not None:
        lpos = Vector((lx, ly, 0.0))
        build_rug(bm, x=lx, y=ly, z_ground=z_floor, width=1.8, length=1.8, rug_style=3)
        a1_ang = _chair_ang_facing(0.0, 0.0, lx, ly)
        build_armchair(bm, x=lx, y=ly, z_ground=z_floor, ang=a1_ang)
        _claim(occ, lx, ly, 1.10)
        tab_pos = _local_to_world(lpos, lang, 0.62, 0.05)
        if _is_floor_pos_safe(tab_pos.x, tab_pos.y, 0.35, fl, shaft_storeys,
                              stair_configs, r_in, False, outcrops, occ):
            build_round_table(bm, x=tab_pos.x, y=tab_pos.y, z_ground=z_floor, radius=0.38)
            _claim(occ, tab_pos.x, tab_pos.y, 0.35)
            build_bottle_cluster(bm, x=tab_pos.x, y=tab_pos.y,
                                 z_ground=z_floor + TABLE_SURF, ang=0.2)
        if not is_compact:
            a2_pos = _local_to_world(lpos, lang, -0.62, 0.05)
            if _is_floor_pos_safe(a2_pos.x, a2_pos.y, 0.55, fl, shaft_storeys,
                                  stair_configs, r_in, False, outcrops, occ):
                a2_ang = _chair_ang_facing(0.0, 0.0, a2_pos.x, a2_pos.y)
                build_armchair(bm, x=a2_pos.x, y=a2_pos.y, z_ground=z_floor, ang=a2_ang)
                _claim(occ, a2_pos.x, a2_pos.y, 0.55)

    # 6. Hanging illumination
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + level_h - 0.15, radius=0.65 if is_compact else 0.75)


def _furnish_archive_floor(bm, z_floor, r_in, level_h, fl, shaft_storeys,
                           stair_configs, outcrops, density, seed):
    """General Arcane Archive & Study floor. The study table stands against
    the wall with its chairs; the middle stays walkable."""
    rng = random.Random(seed)
    occ = []

    # Perimeter grand bookcases on every free wall bay.
    case_h = min(3.4, level_h - 0.8)
    for bx, by, bang in _wall_spots(r_in, 0.55, fl, shaft_storeys, stair_configs,
                                    outcrops, occ, level_h, case_h, 1.15):
        build_grand_bookcase(bm, x=bx, y=by, z_ground=z_floor, ang=bang,
                             width=2.3, height=case_h)
        _claim(occ, bx, by, 1.15)

    # Study table backed to the wall, two chairs on the room side facing it.
    tx, ty, tang = _take_wall_spot(r_in, 2.2, fl, shaft_storeys, stair_configs,
                                   outcrops, occ, level_h, 0.8, 0.90)
    if tx is not None:
        tpos = Vector((tx, ty, 0.0))
        rug_pos = _local_to_world(tpos, tang, 0.0, -0.4)
        build_rug(bm, x=rug_pos.x, y=rug_pos.y, z_ground=z_floor,
                  width=2.4, length=2.4, rug_style=2)
        build_round_table(bm, x=tx, y=ty, z_ground=z_floor, radius=0.75)
        _claim(occ, tx, ty, 0.90)
        for side in (-0.55, 0.55):
            c_pos = _local_to_world(tpos, tang, side, -0.95)
            if not _is_floor_pos_safe(c_pos.x, c_pos.y, 0.35, fl, shaft_storeys,
                                      stair_configs, r_in, False, outcrops, occ):
                continue
            c_ang = _chair_ang_facing(tx, ty, c_pos.x, c_pos.y)
            build_chair(bm, x=c_pos.x, y=c_pos.y, z_ground=z_floor, ang=c_ang)
            _claim(occ, c_pos.x, c_pos.y, 0.35)

    ped_pos = _take_wall_spot(r_in, 0.9, fl, shaft_storeys, stair_configs,
                              outcrops, occ, level_h, 1.5, 0.55)
    if ped_pos[0] is not None:
        build_spellbook_pedestal(bm, x=ped_pos[0], y=ped_pos[1], z_ground=z_floor,
                                 ang=ped_pos[2])
        _claim(occ, ped_pos[0], ped_pos[1], 0.55)
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + level_h - 0.15, radius=0.75)


def _furnish_crown_observatory(bm, z_floor, bel_r_in, bel_h, shaft_storeys,
                               stair_configs, density, seed):
    """Crown Belvedere / Archmage Celestial Observatory. ONE centerpiece (the
    grand orrery under the apex); pool, chart desk and chairs hug the walls."""
    rng = random.Random(seed)
    occ = []
    SH = shaft_storeys + 1

    # 1. Centerpiece: The Grand Arcane Celestial Orrery right under the apex spire.
    build_rug(bm, x=0.0, y=0.0, z_ground=z_floor, width=3.2, length=3.2, rug_style=2)
    build_arcane_orrery(bm, x=0.0, y=0.0, z_ground=z_floor, ang=0.0)
    _claim(occ, 0.0, 0.0, 0.70)

    # 2. Celestial Grimoire lectern backed to the arched windows.
    px, py, pang = _take_wall_spot(bel_r_in, 0.9, shaft_storeys, SH,
                                   stair_configs, (6,), occ, bel_h, 1.5, 0.55)
    if px is not None:
        build_spellbook_pedestal(bm, x=px, y=py, z_ground=z_floor, ang=pang)
        _claim(occ, px, py, 0.55)

    # 3. Star chart desk backed to the wall, chair on the room side.
    hx, hy, hang = _take_wall_spot(bel_r_in, 1.0, shaft_storeys, SH,
                                   stair_configs, (6,), occ, bel_h, 0.9, 1.10)
    if hx is not None:
        hpos = Vector((hx, hy, 0.0))
        build_desk(bm, x=hx, y=hy, z_ground=z_floor, ang=hang, width=1.4)
        _claim(occ, hx, hy, 1.10)
        c_pos = _local_to_world(hpos, hang, 0.0, -0.60)
        if _is_floor_pos_safe(c_pos.x, c_pos.y, 0.35, shaft_storeys, SH,
                              stair_configs, bel_r_in, False, (6,), occ):
            c_ang = _chair_ang_facing(hx, hy, c_pos.x, c_pos.y)
            build_chair(bm, x=c_pos.x, y=c_pos.y, z_ground=z_floor, ang=c_ang)
            _claim(occ, c_pos.x, c_pos.y, 0.35)
        pile_pos = _local_to_world(hpos, hang, 0.35, 0.05)
        build_book_pile_small(bm, x=pile_pos.x, y=pile_pos.y,
                              z_ground=z_floor + DESK_SURF, ang=0.3)

    # 4. Panoramic armchair backed to the belvedere glass, side table alongside.
    ex, ey, eang = _take_wall_spot(bel_r_in, 1.1, shaft_storeys, SH,
                                   stair_configs, (6,), occ, bel_h, 1.1, 0.75)
    if ex is not None:
        epos = Vector((ex, ey, 0.0))
        build_armchair(bm, x=ex, y=ey, z_ground=z_floor,
                       ang=_chair_ang_facing(0.0, 0.0, ex, ey))
        _claim(occ, ex, ey, 0.75)
        tab_pos = _local_to_world(epos, eang, 0.62, 0.05)
        if _is_floor_pos_safe(tab_pos.x, tab_pos.y, 0.35, shaft_storeys, SH,
                              stair_configs, bel_r_in, False, (6,), occ):
            build_round_table(bm, x=tab_pos.x, y=tab_pos.y, z_ground=z_floor, radius=0.32)
            _claim(occ, tab_pos.x, tab_pos.y, 0.35)
            build_bottle_cluster(bm, x=tab_pos.x, y=tab_pos.y,
                                 z_ground=z_floor + TABLE_SURF, ang=0.2)

    # 5. Library bookcases nestled between the belvedere wall posts
    # Crown bay 6 has the doorway leading to the hanging bridge; keep it clear!
    for b in (1, 2, 3, 4, 5, 7):
        b_ang_rad = (b + 0.5) * BAY_ANG + OFFSET
        bx = (bel_r_in - 0.40) * math.cos(b_ang_rad)
        by = (bel_r_in - 0.40) * math.sin(b_ang_rad)
        if _overlaps_any(bx, by, 0.75, occ):
            continue
        facing_ang = b_ang_rad - math.pi * 0.5
        build_bookshelf_neat(bm, x=bx, y=by, z_ground=z_floor, ang=facing_ang,
                             width=1.35, height=min(2.4, bel_h - 1.2))
        _claim(occ, bx, by, 0.75)

    # 6. Hanging illumination from the high rafters
    build_chandelier(bm, x=0.0, y=0.0, z_top=z_floor + bel_h - 0.20, radius=0.85)
    for lf in (1, 3, 5, 7):
        l_ang = (lf + 0.5) * BAY_ANG + OFFSET
        lx = (bel_r_in * 0.70) * math.cos(l_ang)
        ly = (bel_r_in * 0.70) * math.sin(l_ang)
        build_chain_lantern(bm, lx, ly, z_ceiling=z_floor + bel_h - 0.15, chain_len=0.75, scale=0.85)


