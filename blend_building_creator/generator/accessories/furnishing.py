"""Whole-building interior furnishing composer (Controller).

``furnish_building_interior`` dresses every walkable storey in one pass:
the room *role* per floor is derived from the building archetype (tavern =
common room below + beds above, house = hearth + table + bed, ...), then
small deterministic layouts place registry props with wall insets and
clearance around the stair opening and the entrance path (GRASP Creator).

The composer only *arranges* — all geometry comes from ``prop_registry``
so a standalone prop and a furnished-room prop are literally the same mesh
code (DRY).

Hearths are placed with their backs near the rear wall and the firebox facing
into the room; when chimney-aware placement lands, the chimney should rise
over the recorded hearth anchor (same X, flue straight up).
"""

import math
import random

from .prop_registry import build_prop, get_spec


def _hole(ctx, fl):
    try:
        return ctx.floor_stair_holes.get(fl)
    except Exception:
        return None


def _blocked(x, y, r, holes, path=None):
    for h in holes:
        if h is None:
            continue
        hx0, hx1, hy0, hy1 = h
        if hx0 - r <= x <= hx1 + r and hy0 - r <= y <= hy1 + r:
            return True
    if path is not None:
        px, py, pr = path
        if abs(x - px) < pr + r and y > py - 0.5:
            return True
    return False


def _role_for(ctx, fl, props):
    arch = getattr(ctx, 'effective_archetype', 'NONE')
    if arch in ('TAVERN', 'INN'):
        return 'COMMON' if fl == 0 else 'GUEST'
    if arch in ('BLACKSMITH', 'WAREHOUSE', 'LUMBERMILL', 'BAKERY'):
        return 'WORKSHOP' if fl == 0 else 'LODGE'
    if arch == 'CHAPEL':
        return 'CHAPEL_HALL'
    return 'HOUSE' if fl == 0 else 'BEDROOM'


# Layout recipes: list of (prop_key, dx_frac, dy_frac, yaw, scale_kwargs).
# Fractions are in [-1, 1] of the usable half-extents.
_LAYOUTS = {
    'COMMON': [
        ('COUNTER', 0.0, 0.62, math.pi, {}),
        ('ROUND_TABLE', -0.45, -0.10, 0.3, {}),
        ('ROUND_TABLE', 0.45, -0.15, -0.2, {}),
        ('INDOOR_TABLE', 0.0, -0.55, 0.0, {}),
        ('STOOL', -0.45, 0.35, 1.2, {}),
        ('STOOL', 0.50, 0.30, -0.8, {}),
        ('CHAIR', -0.15, -0.55, math.pi, {}),
        ('HEARTH', 0.0, 0.90, 0.0, {}),
        ('BARREL', -0.85, 0.55, 0.0, {}),
        ('CHAIN_LANTERN', 0.0, 0.0, 0.0, {'_ceiling': True}),
    ],
    'GUEST': [
        ('BED', -0.45, 0.30, math.pi / 2, {}),
        ('BED', 0.45, 0.30, -math.pi / 2, {}),
        ('CHEST', 0.0, 0.80, 0.0, {}),
        ('STOOL', 0.0, -0.30, 0.5, {}),
        ('CHAIN_LANTERN', 0.0, 0.0, 0.0, {'_ceiling': True}),
    ],
    'HOUSE': [
        ('HEARTH', 0.0, 0.85, 0.0, {}),
        ('INDOOR_TABLE', 0.0, -0.10, 0.1, {}),
        ('CHAIR', -0.35, -0.10, math.pi / 2, {}),
        ('CHAIR', 0.35, -0.10, -math.pi / 2, {}),
        ('SHELF', -0.80, 0.80, 0.0, {}),
        ('CAULDRON', 0.55, 0.30, 0.0, {}),
        ('CHAIN_LANTERN', 0.0, 0.0, 0.0, {'_ceiling': True}),
    ],
    'BEDROOM': [
        ('BED', -0.40, 0.35, math.pi / 2, {}),
        ('WARDROBE', 0.70, 0.75, math.pi, {}),
        ('CHEST', 0.30, 0.80, 0.0, {}),
        ('STOOL', 0.10, -0.35, 0.0, {}),
        ('CHAIN_LANTERN', 0.0, 0.0, 0.0, {'_ceiling': True}),
    ],
    'WORKSHOP': [
        ('DESK', -0.50, 0.60, 0.0, {}),
        ('SHELF', 0.55, 0.75, math.pi, {}),
        ('CRATE', 0.75, -0.30, 0.2, {}),
        ('CRATE', -0.75, -0.45, -0.15, {}),
        ('BARREL', -0.80, 0.10, 0.0, {}),
        ('INDOOR_TABLE', 0.10, -0.20, 0.0, {}),
        ('STOOL', 0.10, -0.65, math.pi, {}),
    ],
    'LODGE': [
        ('BED', -0.45, 0.30, math.pi / 2, {}),
        ('CHEST', 0.45, 0.70, 0.0, {}),
        ('INDOOR_TABLE', 0.10, -0.40, 0.0, {}),
        ('STOOL', 0.10, -0.75, 0.0, {}),
    ],
    'CHAPEL_HALL': [
        ('BENCH', -0.35, 0.0, math.pi / 2, {'length': 2.2}),
        ('BENCH', 0.35, 0.0, math.pi / 2, {'length': 2.2}),
        ('COUNTER', 0.0, 0.80, 0.0, {'length': 1.8}),
        ('CHAIN_LANTERN', 0.0, 0.0, 0.0, {'_ceiling': True}),
    ],
}


def furnish_building_interior(bm, props, ctx):
    """Dress every floor per its room role. No-op unless enabled."""
    if not bool(getattr(props, 'has_interior_furnishing', False)):
        return
    if getattr(ctx, 'shape', 'RECTANGLE') == 'ROUND_TOWER':
        return  # round tower path owns its own interior; skip to avoid clipping
    density = float(getattr(props, 'furnishing_density', 1.0))
    if density <= 0.01:
        return
    seed = int(getattr(props, 'seed', 1)) + 917
    style = getattr(props, 'furnishing_style', 'AUTO')

    for fl in range(ctx.num_floors):
        bounds = ctx.bounds_for(fl)
        x0, x1, y0, y1 = bounds
        inset = ctx.wall_t * 0.5 + 0.45
        ux0, ux1, uy0, uy1 = x0 + inset, x1 - inset, y0 + inset, y1 - inset
        if ux1 - ux0 < 1.6 or uy1 - uy0 < 1.6:
            continue
        z_floor = ctx.found_h + fl * ctx.floor_h + 0.02
        z_ceil = z_floor + ctx.floor_h - 0.15
        role = _role_for(ctx, fl, props)
        recipe = list(_LAYOUTS.get(role, _LAYOUTS['HOUSE']))
        if style == 'SPARSE':
            recipe = [r for i, r in enumerate(recipe) if i % 2 == 0]
        elif style == 'COSY':
            pass  # full recipe
        # Density trims the tail (lantern always kept when possible).
        keep = [r for r in recipe if r[0] in ('CHAIN_LANTERN', 'CHANDELIER')]
        rest = [r for r in recipe if r[0] not in ('CHAIN_LANTERN', 'CHANDELIER')]
        n_keep = max(1, int(len(rest) * min(1.0, density)))
        recipe = rest[:n_keep] + keep

        rng = random.Random(seed + fl * 131)
        holes = [_hole(ctx, fl), _hole(ctx, fl + 1)]
        path = (ctx.main_door_cx, y0, 0.9) if fl == 0 else None
        cx, cy = (ux0 + ux1) / 2, (uy0 + uy1) / 2
        hx, hy = (ux1 - ux0) / 2, (uy1 - uy0) / 2

        for key, fx, fy, yaw, extra in recipe:
            spec = get_spec(key)
            r = spec.clearance * 0.75
            jx = (rng.random() - 0.5) * 0.25
            jy = (rng.random() - 0.5) * 0.25
            x = cx + fx * hx * 0.82 + jx
            y = cy + fy * hy * 0.82 + jy
            x = min(ux1 - r, max(ux0 + r, x))
            y = min(uy1 - r, max(uy0 + r, y))
            if key not in ('CHAIN_LANTERN', 'CHANDELIER') and _blocked(x, y, r, holes, path):
                continue
            kw = {k: v for k, v in (extra or {}).items() if not k.startswith('_')}
            z = z_ceil if key in ('CHAIN_LANTERN', 'CHANDELIER') else z_floor
            try:
                build_prop(bm, key, x, y, z, yaw + (rng.random() - 0.5) * 0.15, **kw)
            except Exception:
                continue
