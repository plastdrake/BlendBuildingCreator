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
        build_wine_rack(bm, bx0 + wall_t + 0.24, bcy, rack_z, math.pi * 0.5,
                        width=min(bd - 2.2, 1.20))

    # 5. Upright bottle shelves on the FRONT wall, clear of the back rack.
    from .interior_furniture import build_bottle
    _shelf_w = min(bw * 0.55, 2.0)
    _shelf_y = by0 + wall_t + 0.18
    for _sz in (z_floor + 1.55, z_floor + 2.00):
        faces += create_beveled_box(
            bm, size=(_shelf_w, 0.30, 0.05),
            location=(bcx, _shelf_y, _sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)
        _n = 6
        for _i in range(_n):
            _bx = bcx - _shelf_w * 0.5 + 0.18 + _i * ((_shelf_w - 0.36) / max(1, _n - 1))
            faces += build_bottle(
                bm, _bx, _shelf_y + 0.02, _sz + 0.025, ang=0.0,
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

    # 9. Stone wash basin (Tier 3), tucked into the front-left clear corner.
    if tier == 'TIER_3':
        faces += create_beveled_box(
            bm, size=(1.0, 0.7, 0.5),
            location=(bx0 + wall_t + 0.75, by0 + wall_t + 3.20, z_floor + 0.25),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        faces += create_beveled_box(
            bm, size=(0.86, 0.56, 0.04),
            location=(bx0 + wall_t + 0.75, by0 + wall_t + 3.20, z_floor + 0.47),
            mat_index=MAT_INDEX_WATER, bevel_amount=0.005
        )

    return (bx0 - wall_t, bx1 + wall_t, by0 - wall_t, by1 + wall_t)
