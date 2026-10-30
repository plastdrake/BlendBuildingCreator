"""Brewery wine cellar: a stone basement directly UNDER the L-wing.

Fires for the BREWERY archetype. The cellar is a real below-grade room the
same footprint as the wing, entered from inside the house by a railed
timber staircase that descends through a hole cut in the ground-floor slab
(the ``has_basement_stair`` shaft, positioned in the wing by ``floors.py``).

Sizing grows with the material tier; the room never leaves the wing plot and
the stair shaft is reserved by the floor planner so no furniture lands in it.
"""

import math

from ..mesh_utils import create_beveled_box, create_cylinder, transform_faces
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_WAX, MAT_INDEX_LOG, MAT_INDEX_WATER,
)
from .artisan_props import build_wine_rack, build_mash_tun, build_keg_rack
from .furniture import build_barrel, build_crate


def _place(x, y, z_ground, ang):
    from mathutils import Matrix
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _wing_rect(ctx):
    wings = getattr(ctx, 'wings', None) or []
    if not wings:
        return None
    base = wings[0].get('base') or wings[0].get('bounds')
    if not base:
        return None
    return tuple(float(v) for v in base[:4])


def build_inn_cellar(bm, props, ctx, tier='TIER_2'):
    """A generous, two-chamber inn undercroft under the guest wing + main block.

    Bigger than the brewery cellar but still a single readable space: a cask
    hall under the wing (barrels, tasting table, wine bins) and a provisions
    store under the main block (wine racks, bottle shelves, well, strongbox),
    joined by a wide stone arch.  The cellar stair descends through the same
    ``has_basement_stair`` shaft the wing already reserves.
    """
    wing = _wing_rect(ctx)
    if wing is None:
        return None
    wx1, wx2, wy1, wy2 = wing
    wall_t = 0.34
    z_ground = float(getattr(ctx, 'found_h', 0.6))
    depth = {'TIER_1': 2.70, 'TIER_2': 3.10, 'TIER_3': 3.50}.get(tier, 3.10)
    z_floor = -depth
    z_ceil = z_ground + 0.03

    base_w = float(getattr(ctx, 'base_w', getattr(props, 'width', 18.0)))
    base_d = float(getattr(ctx, 'base_d', getattr(props, 'depth', 11.0)))
    main_wt = float(getattr(ctx, 'wall_t', getattr(props, 'wall_thickness', 0.30)))
    hx = base_w * 0.5 - main_wt * 0.5
    hy = base_d * 0.5 - main_wt * 0.5

    bx0 = wx1 + 0.25
    bx1 = min(wx2 - 0.25, hx - 0.30)
    by0 = wy1 + 0.25
    by1 = min(wy2 + 6.20, hy - 0.30)
    if bx1 - bx0 < 4.0 or by1 - by0 < 6.0:
        return None
    bcx, bcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
    bw, bd = bx1 - bx0, by1 - by0
    h = z_ceil - z_floor

    faces = []
    # Stone shell.
    faces += create_beveled_box(
        bm, size=(bw, bd, 0.22), location=(bcx, bcy, z_floor - 0.11),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    for sx in (bx0 + wall_t * 0.5, bx1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t, bd, h),
            location=(sx, bcy, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    for sy in (by0 + wall_t * 0.5, by1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(bw, wall_t, h),
            location=(bcx, sy, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Two chambers joined by a wide arch in the middle.
    arch_y = by0 + bd * 0.56
    open_half = 1.35
    for _x0, _x1 in ((bx0, bcx - open_half), (bcx + open_half, bx1)):
        if _x1 - _x0 < 0.35:
            continue
        faces += create_beveled_box(
            bm, size=(_x1 - _x0, 0.32, h),
            location=((_x0 + _x1) * 0.5, arch_y, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    # Timber lintel + stone pilasters frame the arch.
    faces += create_beveled_box(
        bm, size=(open_half * 2.0 + 0.70, 0.24, 0.30),
        location=(bcx, arch_y, z_ceil - 0.24),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    for _px in (bcx - open_half - 0.18, bcx + open_half + 0.18):
        faces += create_beveled_box(
            bm, size=(0.34, 0.50, h),
            location=(_px, arch_y, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Chunky timber ceiling beams give the vaulted cellar some rhythm.
    for _i in range(1, 5):
        _by = by0 + bd * _i / 5.0
        faces += create_beveled_box(
            bm, size=(bw - wall_t * 2.0, 0.16, 0.20),
            location=(bcx, _by, z_ceil - 0.30),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Descending stair (same shaft as floors.py reserves in the wing).
    shx = wx1 + 1.50
    shy = (wy1 + wy2) * 0.5
    stair_depth = 3.60
    steps = max(8, int(round((z_ground - z_floor) / 0.185)))
    from ..interior import build_straight_staircase
    build_straight_staircase(
        bm, (shx, shy + stair_depth * 0.5, z_floor), z_ground,
        stair_width=1.35, stair_depth=stair_depth, num_steps=steps,
        direction_y=-1)

    def _stair_clear(x, y, m=0.55):
        return not (shx - 0.95 - m <= x <= shx + 0.95 + m
                    and shy - 1.95 - m <= y <= shy + 1.95 + m)

    # --- Cask hall (under the wing) ---------------------------------------
    # Wine bins on the front wall and the left wall, kept clear of the stair.
    build_wine_rack(bm, bcx, by0 + wall_t + 0.24, z_floor + 0.02, 0.0,
                    width=min(bw - 2.2, 1.50))
    build_wine_rack(bm, bx0 + wall_t + 0.24, by0 + 1.85, z_floor + 0.02,
                    math.pi * 0.5, width=1.20)
    # Big casks along the right wall, lids facing into the room.
    for _i, _yy in enumerate((by0 + 2.5, by0 + 5.3, by0 + 8.1)):
        if _yy > arch_y - 1.1:
            break
        _rad, _hlen = ((0.46, 1.10), (0.52, 1.25), (0.42, 0.98))[_i % 3]
        build_barrel(bm, bx1 - wall_t - _hlen * 0.5 - 0.10, _yy, z_floor, 0.0,
                     radius=_rad, height=_hlen, lying=True)
    # Tasting table in the open middle of the hall.
    _tx, _ty = bcx + 1.55, by0 + 5.5
    if _stair_clear(_tx, _ty):
        from .prop_registry import build_prop
        build_prop(bm, 'INDOOR_TABLE', _tx, _ty, z_floor, 0.0,
                   length=1.90, width=0.90)
        build_prop(bm, 'SCATTER_TABLEWARE', _tx, _ty, z_floor + 0.99, 0.0)
        for _ox, _oy, _ang in ((-1.25, 0.0, math.pi / 2), (1.25, 0.0, -math.pi / 2),
                               (0.0, -0.95, 0.0), (0.0, 0.95, math.pi)):
            build_prop(bm, 'STOOL', _tx + _ox, _ty + _oy, z_floor,
                       _ang + math.pi * 0.5, height=0.62)
    # Barrels in the front-left corner, away from the stair.
    for _ox in (0.0, 0.9):
        build_barrel(bm, bx0 + wall_t + 1.15 + _ox, by0 + wall_t + 0.95,
                     z_floor, 0.0, radius=0.32, height=0.76)

    # --- Provisions store (under the main block) --------------------------
    _store_y = (arch_y + by1) * 0.5
    build_wine_rack(bm, bx0 + wall_t + 0.24, _store_y, z_floor + 0.02,
                    math.pi * 0.5, width=min(bd * 0.22, 1.70))
    build_wine_rack(bm, bx1 - wall_t - 0.24, _store_y - 1.8, z_floor + 0.02,
                    -math.pi * 0.5, width=min(bd * 0.22, 1.70))
    # Upright bottle shelves on the right wall, above the rack.
    from .interior_furniture import build_bottle
    _shelf_l = min(bd * 0.30, 1.70)
    _shelf_x = bx1 - wall_t - 0.18
    for _sz in (z_floor + 1.62, z_floor + 2.08):
        faces += create_beveled_box(
            bm, size=(0.30, _shelf_l, 0.05),
            location=(_shelf_x, _store_y, _sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)
        for _i in range(5):
            _by = _store_y - _shelf_l * 0.5 + 0.20 + _i * ((_shelf_l - 0.40) / 4.0)
            faces += build_bottle(
                bm, _shelf_x + 0.02, _by, _sz + 0.025, 0.0,
                bottle_type=('POTION' if _i % 3 == 1 else 'WINE'))
    # Strongbox + provisioning crates in the back corners.
    from .prop_registry import build_prop
    build_prop(bm, 'CHEST', bcx + 2.35, by1 - 0.85, z_floor, math.pi * 0.5)
    build_crate(bm, bx0 + wall_t + 0.65, by1 - 0.80, z_floor, size=0.62)
    build_crate(bm, bx0 + wall_t + 1.35, by1 - 0.80, z_floor, size=0.52)
    for _yy in (by1 - 1.65, by1 - 2.55):
        build_barrel(bm, bx1 - wall_t - 0.75, _yy, z_floor,
                     radius=0.30, height=0.72)

    # Hanging lights in each chamber.
    build_prop(bm, 'CHANDELIER', bcx, (by0 + arch_y) * 0.5, z_ceil, 0.0,
               radius=0.48, chain_drop=0.55)
    build_prop(bm, 'CHANDELIER', bcx, (arch_y + by1) * 0.5, z_ceil, 0.0,
               radius=0.44, chain_drop=0.55)

    return (bx0 - wall_t, bx1 + wall_t, by0 - wall_t, by1 + wall_t)


def build_brewery_cellar(bm, props, ctx, tier='TIER_1'):
    """Build the under-wing basement + descending staircase. Returns its
    world-space footprint or None when there is no wing to sit under."""
    wing = _wing_rect(ctx)
    if wing is None:
        return None
    wx1, wx2, wy1, wy2 = wing
    wall_t = 0.32
    z_ground = float(getattr(ctx, 'found_h', 0.45))

    # Tier-scaled room height.
    if tier == 'TIER_1':
        depth = 2.40
    elif tier == 'TIER_2':
        depth = 2.80
    else:
        depth = 3.20
    z_floor = -depth
    z_ceil = z_ground + 0.03  # meet the ground-floor slab, no gap at the top

    # Basement room = wing footprint inset a little.
    bx0, bx1 = wx1 + 0.25, wx2 - 0.25
    by0 = wy1 + 0.25
    # Extend the cellar past the wing's +Y wall (under the main block) so the
    # stair, which descends toward +Y, has clear landing room at its foot.
    by1 = wy2 + 1.40
    bcx, bcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
    bw, bd = bx1 - bx0, by1 - by0

    faces = []
    # 1. Floor slab.
    faces += create_beveled_box(
        bm, size=(bw, bd, 0.22),
        location=(bcx, bcy, z_floor - 0.11),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    # 2. Perimeter walls floor -> ceiling.
    h = z_ceil - z_floor
    for sx in (bx0 + wall_t * 0.5, bx1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t, bd, h),
            location=(sx, bcy, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
    for sy in (by0 + wall_t * 0.5, by1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(bw, wall_t, h),
            location=(bcx, sy, (z_floor + z_ceil) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )

    # 3. Stair shaft in the wing (matches floors.py): a railed timber stair
    #    from the ground floor down to the cellar.
    shx = wx1 + 1.50
    shy = (wy1 + wy2) * 0.5
    riser = 0.185
    steps = max(8, int(round((z_ground - z_floor) / riser)))
    stair_w = 1.30
    stair_depth = 3.60
    from ..interior import build_straight_staircase
    build_straight_staircase(
        bm, (shx, shy + stair_depth * 0.5, z_floor), z_ground,
        stair_width=stair_w, stair_depth=stair_depth, num_steps=steps,
        direction_y=-1
    )

    # 4. Wine racks: back wall (centred) and the left wall on larger cellars.
    #    The right wall stays free for the big casks.
    rack_z = z_floor + 0.02
    build_wine_rack(bm, bcx, by1 - wall_t - 0.24, rack_z, 0.0,
                    width=min(bw - 1.8, 1.20))
    if tier != 'TIER_1':
        # Tuck the left-wall rack under the higher half of the flight, one
        # metre back from the stair's low end, so its top shelf clears the
        # stair underside instead of poking through the steps.
        build_wine_rack(bm, bx0 + wall_t + 0.24, bcy - 1.05, rack_z, math.pi * 0.5,
                        width=min(bd - 2.2, 1.20))

    # 5. Upright bottle shelves on the RIGHT wall, above the casks and well
    #    clear of the stair flight (which hugs the left side of the wing).
    from .interior_furniture import build_bottle
    _shelf_l = min(bd * 0.55, 2.0)
    _shelf_x = bx1 - wall_t - 0.18
    for _sz in (z_floor + 1.55, z_floor + 2.00):
        faces += create_beveled_box(
            bm, size=(0.30, _shelf_l, 0.05),
            location=(_shelf_x, bcy, _sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)
        _n = 6
        for _i in range(_n):
            _by = bcy - _shelf_l * 0.5 + 0.18 + _i * ((_shelf_l - 0.36) / max(1, _n - 1))
            faces += build_bottle(
                bm, _shelf_x + 0.02, _by, _sz + 0.025, ang=0.0,
                bottle_type=('POTION' if _i % 3 == 1 else 'WINE'))

    # 6. Big lying casks along the right wall, circular lids facing INTO the
    #    room (barrel axis perpendicular to the wall). Sizes vary.
    _cask_ys = (bcy - min(bd * 0.28, 2.2),
                bcy,
                bcy + min(bd * 0.28, 2.2))
    _cask_specs = ((0.46, 1.10), (0.52, 1.25), (0.40, 0.95))
    for _i, _yy in enumerate(_cask_ys):
        _rad, _hlen = _cask_specs[_i % len(_cask_specs)]
        build_barrel(bm, bx1 - wall_t - _hlen * 0.5 - 0.08, _yy, z_floor, 0.0,
                     radius=_rad, height=_hlen, lying=True)

    # 7. Standing barrels and a crate in the front-left corner.
    build_barrel(bm, bx0 + wall_t + 1.10, by0 + wall_t + 2.10, z_floor,
                 radius=0.32, height=0.76)
    build_barrel(bm, bx0 + wall_t + 2.10, by0 + wall_t + 2.10, z_floor,
                 radius=0.32, height=0.76)
    build_crate(bm, bx0 + wall_t + 0.85, by0 + wall_t + 0.85, z_floor, size=0.52)

    # 8. Stirring vat / mash tun with paddle, clear of casks and the stair.
    build_mash_tun(bm, bcx + bw * 0.10, by0 + bd * 0.52, z_floor,
                   radius=min(0.55, max(0.38, bw * 0.09)), height=0.95)

    return (bx0 - wall_t, bx1 + wall_t, by0 - wall_t, by1 + wall_t)
