"""Brewery wine cellar: a sunken stone undercroft in the courtyard.

Fires for the BREWERY archetype. The cellar is a stone-lined, partially
sunken vault tucked into the L-footprint courtyard (never on the open plot
lanes), sized by material tier and never leaving the plot:

* Tier 1 — a small single vault (~4.0 x 3.2 m) with a corner stair, a few
  wine racks and barrels.
* Tier 2 — a wider vault with racks on two walls, a barrel cradle and a
  barrel platform.
* Tier 3 — a two-level undercroft: the upper vault plus a lower storey
  reached by an internal stone stair, both fully racked.

Everything is built from MAT_INDEX_* slots and the shared prop builders so
it matches the rest of the kit.
"""

import math

from ..mesh_utils import create_beveled_box, create_cylinder, transform_faces
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_IRON, MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_WAX, MAT_INDEX_LOG,
)
from ..uv_utils import map_planar_faces


def _courtyard_rect(ctx, margin=0.6):
    """(x0, x1, y0, y1) of the open courtyard inside an L/T/U footprint.

    Returns None when the building has no usable inner courtyard.
    """
    wings = getattr(ctx, 'wings', None) or []
    if not wings:
        return None
    hx, hy = ctx.hx, ctx.hy
    w = wings[0]
    base = w.get('base') or w.get('bounds')
    if not base:
        return None
    wx1, wx2, wy1, wy2 = (float(base[0]), float(base[1]),
                          float(base[2]), float(base[3]))
    wall = w.get('wall')
    align = w.get('align')
    if wall in ('FRONT', 'BACK'):
        cy0, cy1 = wy1, wy2
        if align == 'RIGHT':
            cx0, cx1 = -hx, wx1
        elif align == 'LEFT':
            cx0, cx1 = wx2, hx
        else:
            return None
    elif wall in ('LEFT', 'RIGHT'):
        cx0, cx1 = wx1, wx2
        if align == 'FRONT':
            cy0, cy1 = wy2, hy
        elif align == 'BACK':
            cy0, cy1 = -hy, wy1
        else:
            return None
    else:
        return None
    if cx1 - cx0 < 2.5 or cy1 - cy0 < 2.5:
        return None
    return (cx0 + margin, cx1 - margin, cy0 + margin, cy1 - margin)


def _wine_rack(bm, x, y, z_floor, ang, width=1.1):
    from .artisan_props import build_wine_rack
    faces = build_wine_rack(bm, 0.0, 0.0, 0.0, 0.0, width=width)
    transform_faces(faces, _place(x, y, z_floor, ang))
    return faces


def _place(x, y, z_ground, ang):
    from mathutils import Matrix
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _barrel(bm, x, y, z, radius=0.34, height=0.74, lying=False):
    from .furniture import build_barrel
    return build_barrel(bm, x, y, z, 0.0, radius=radius, height=height,
                        lying=lying)


def _crate(bm, x, y, z, size=0.58):
    from .furniture import build_crate
    return build_crate(bm, x, y, z, 0.0, size=size)


def build_brewery_cellar(bm, props, ctx, tier='TIER_1'):
    """Build the courtyard wine cellar for the given tier. Returns its
    world-space footprint (x0, x1, y0, y1) or None when it does not fit."""
    rect = _courtyard_rect(ctx)
    if rect is None:
        return None
    cx0, cx1, cy0, cy1 = rect
    cw, cd = cx1 - cx0, cy1 - cy0

    # Tier sizing: small -> large, all clamped to the courtyard.
    if tier == 'TIER_1':
        w = min(cw, 4.2)
        d = min(cd, 3.4)
        depth = 1.7
        two_level = False
    elif tier == 'TIER_2':
        w = min(cw, 5.6)
        d = min(cd, 4.4)
        depth = 2.1
        two_level = False
    else:
        w = min(cw, 6.6)
        d = min(cd, 5.2)
        depth = 2.3
        two_level = True

    # Centre the cellar in the courtyard.
    ccx = (cx0 + cx1) * 0.5
    ccy = (cy0 + cy1) * 0.5
    x0, x1 = ccx - w * 0.5, ccx + w * 0.5
    y0, y1 = ccy - d * 0.5, ccy + d * 0.5

    wall_t = 0.32
    parapet = 0.55
    z_floor = -depth
    z_top = parapet
    faces = []

    # 1. Stone floor slab (sunk).
    faces += create_beveled_box(
        bm, size=(w, d, 0.22),
        location=(ccx, ccy, z_floor - 0.11),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    # 2. Perimeter retaining walls from floor up to the parapet.
    for sx in (x0 + wall_t * 0.5, x1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t, d, z_top - z_floor),
            location=(sx, ccy, (z_floor + z_top) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
    for sy in (y0 + wall_t * 0.5, y1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(w, wall_t, z_top - z_floor),
            location=(ccx, sy, (z_floor + z_top) * 0.5),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
    # Capstones around the parapet lip.
    for sx in (x0 + wall_t * 0.5, x1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t + 0.12, d + 0.12, 0.09),
            location=(sx, ccy, z_top + 0.045),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012
        )
    for sy in (y0 + wall_t * 0.5, y1 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(w + 0.12, wall_t + 0.12, 0.09),
            location=(ccx, sy, z_top + 0.045),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012
        )

    # 3. Corner stair descending along the -X wall (front-left corner).
    steps = max(6, int(math.ceil(depth / 0.22)))
    step_d = 0.30
    stair_y0 = y0 + wall_t + 0.40
    for i in range(steps):
        sz = 0.0 - (i + 1) * (depth / steps)
        faces += create_beveled_box(
            bm, size=(1.10, step_d, depth / steps + 0.02),
            location=(x0 + wall_t + 0.55, stair_y0 + i * step_d,
                      sz + (depth / steps) * 0.5),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010
        )

    # 4. Wine racks along the +Y and +X walls (facing into the vault).
    rack_z = z_floor + 0.02
    _wine_rack(bm, ccx, y1 - wall_t - 0.24, rack_z, math.pi,
               width=min(w - wall_t * 2 - 0.4, 1.10))
    _wine_rack(bm, x1 - wall_t - 0.24, ccy, rack_z, -math.pi * 0.5,
               width=min(d - wall_t * 2 - 0.4, 1.10))
    if tier != 'TIER_1':
        _wine_rack(bm, ccx, y0 + wall_t + 0.24, rack_z, 0.0,
                   width=min(w - wall_t * 2 - 0.4, 1.10))

    # 5. Barrel cradle + loose barrels and crates on the vault floor.
    bx = x1 - wall_t - 0.55
    _barrel(bm, bx, ccy - 0.9, z_floor, radius=0.30, height=0.66, lying=True)
    _barrel(bm, bx, ccy + 0.9, z_floor, radius=0.30, height=0.66, lying=True)
    _barrel(bm, ccx + 0.4, ccy - d * 0.5 + 0.7, z_floor, radius=0.28, height=0.72)
    _crate(bm, ccx - 0.6, ccy + d * 0.5 - 0.7, z_floor, size=0.52)
    if tier == 'TIER_2':
        _barrel(bm, ccx + 1.2, ccy + d * 0.5 - 0.8, z_floor, radius=0.30, height=0.70)
    if tier == 'TIER_3':
        _crate(bm, ccx - 1.3, ccy - d * 0.5 + 0.8, z_floor, size=0.52)

    # 6. Tier-3 lower storey: a compact sub-cellar under the vault with its
    # own stone stair and a second rack row (deeper wine archive).
    if two_level:
        sub_depth = 2.0
        sub_w = w - 1.4
        sub_d = d - 1.4
        z_sub = z_floor - sub_depth
        faces += create_beveled_box(
            bm, size=(sub_w, sub_d, 0.20),
            location=(ccx, ccy, z_sub - 0.10),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        for sx in (ccx - sub_w * 0.5 + wall_t * 0.5,
                   ccx + sub_w * 0.5 - wall_t * 0.5):
            faces += create_beveled_box(
                bm, size=(wall_t, sub_d, z_floor - z_sub),
                location=(sx, ccy, (z_sub + z_floor) * 0.5),
                mat_index=MAT_INDEX_STONE, bevel_amount=0.02
            )
        for sy in (ccy - sub_d * 0.5 + wall_t * 0.5,
                   ccy + sub_d * 0.5 - wall_t * 0.5):
            faces += create_beveled_box(
                bm, size=(sub_w, wall_t, z_floor - z_sub),
                location=(ccx, sy, (z_sub + z_floor) * 0.5),
                mat_index=MAT_INDEX_STONE, bevel_amount=0.02
            )
        # Sub-cellar descending stair (opposite corner to the upper stair).
        sub_steps = max(6, int(math.ceil(sub_depth / 0.22)))
        for i in range(sub_steps):
            sz = z_floor - (i + 1) * (sub_depth / sub_steps)
            faces += create_beveled_box(
                bm, size=(0.95, step_d, sub_depth / sub_steps + 0.02),
                location=(ccx + sub_w * 0.5 - 0.55,
                          ccy + sub_d * 0.5 - 0.40 - i * step_d,
                          sz + (sub_depth / sub_steps) * 0.5),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010
            )
        _wine_rack(bm, ccx - sub_w * 0.5 + 0.30, ccy, z_sub + 0.02,
                   -math.pi * 0.5, width=min(sub_d - 0.5, 1.10))
        _barrel(bm, ccx + sub_w * 0.5 - 0.7, ccy - sub_d * 0.5 + 0.6, z_sub,
                radius=0.28, height=0.70)

    return (x0 - wall_t, x1 + wall_t, y0 - wall_t, y1 + wall_t)
