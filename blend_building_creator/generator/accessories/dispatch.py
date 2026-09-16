"""
Accessory dispatch.

Builds the optional architectural accessories that layer onto the finished main
mass: the mini-wing outcrop, timber balconies, the pillared overhang and the
civic landmarks. Splitting this out of ``building.generate_building`` keeps the
orchestrator focused on the building itself and gives each accessory a single
named entry point.
"""

from .mini_wing import build_mini_wing, mini_wing_offsets
from .pillared_overhang import build_pillared_overhang
from .tavern import build_balcony
from .civic import (
    build_clock_tower, build_corner_turret, build_entry_ramp, build_arched_porch,
)
from .town_hall import build_town_hall_composer


def _prop(props, name, default):
    return getattr(props, name, default)


def _build_mini_wing(bm, props, ctx, tier):
    if not _prop(props, 'has_mini_wing', False):
        return
    floor_mode = _prop(props, 'mini_wing_floor', 'GROUND')
    target_fl = 0 if floor_mode == 'GROUND' else min(ctx.num_floors - 1, 1)
    bounds = ctx.bounds_for(target_fl)
    lower = ctx.bounds_for(max(0, target_fl - 1))
    side = _prop(props, 'mini_wing_side', 'LEFT')
    width = _prop(props, 'mini_wing_width', 2.2)
    count = int(_prop(props, 'mini_wing_count', 1))
    for off in mini_wing_offsets(bounds, side, count, width):
        build_mini_wing(
            bm,
            side=side,
            floor_mode=floor_mode,
            wall_x_min=bounds[0], wall_x_max=bounds[1],
            wall_y_min=bounds[2], wall_y_max=bounds[3],
            z_base=ctx.found_h + target_fl * ctx.floor_h,
            width=width,
            depth=_prop(props, 'mini_wing_depth', 1.6),
            height=min(2.05, ctx.floor_h * 0.72),
            roof_style=_prop(props, 'mini_wing_roof', 'LEAN_TO'),
            tier=tier, floor_h=ctx.floor_h, lower_bounds=lower,
            win_w=_prop(props, 'window_width', 0.85),
            win_h=_prop(props, 'window_height', 1.2),
            shingle_scale=_prop(props, 'mini_wing_shingle_scale', 0.32),
            shingle_rot=int(_prop(props, 'mini_wing_shingle_rot', '0')),
            off_along=off,
        )


def _build_balconies(bm, props, ctx, tier):
    if not _prop(props, 'has_balcony', False) or ctx.num_floors < 2 or not ctx.floor_balc_side:
        return
    width = _prop(props, 'balcony_width', 2.4)
    depth = _prop(props, 'balcony_depth', 1.3)
    for fl_idx in ctx.active_balc_floors:
        side = ctx.floor_balc_side.get(fl_idx)
        if side is None:
            continue
        bounds = ctx.bounds_for(fl_idx)
        lower = ctx.bounds_for(max(0, fl_idx - 1))
        build_balcony(
            bm, side=side,
            wall_x_min=bounds[0], wall_x_max=bounds[1],
            wall_y_min=bounds[2], wall_y_max=bounds[3],
            lower_wall_x_min=lower[0], lower_wall_x_max=lower[1],
            lower_wall_y_min=lower[2], lower_wall_y_max=lower[3],
            z_floor=ctx.found_h + fl_idx * ctx.floor_h,
            width=width, depth=depth, tier=tier,
        )


def _build_pillared_overhang(bm, props, ctx, tier):
    if not _prop(props, 'has_pillared_overhang', False):
        return
    bounds = ctx.bounds_for(0)
    build_pillared_overhang(
        bm,
        side=_prop(props, 'pillared_overhang_side', 'FRONT'),
        wall_x_min=bounds[0], wall_x_max=bounds[1],
        wall_y_min=bounds[2], wall_y_max=bounds[3],
        z_ground=0.0, z_ceiling=ctx.found_h + ctx.floor_h,
        depth=_prop(props, 'pillared_overhang_depth', 1.6),
        pillar_count=_prop(props, 'pillared_overhang_pillars', 3),
        pillar_style=_prop(props, 'pillared_overhang_style', 'TIMBER_STONE'),
        tier=tier,
    )


def _build_civic_landmarks(bm, props, ctx, tier):
    base_hx = ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    floor_decks = [ctx.found_h + i * ctx.floor_h for i in range(1, ctx.num_floors)]
    wing_front = -base_hy - ctx.raw_wing_d

    if _prop(props, 'has_clock_tower', False):
        t_size = _prop(props, 'clock_tower_size', 3.0)
        t_sgn = 1.0 if _prop(props, 'clock_tower_side', 'RIGHT') == 'RIGHT' else -1.0
        build_clock_tower(
            bm,
            cx=t_sgn * (base_hx + t_size * 0.5 - 0.7),
            cy=wing_front + t_size * 0.5 - 0.25,
            z_ground=0.0, size=t_size,
            shaft_top_z=ctx.found_h + ctx.num_floors * ctx.floor_h + props.roof_height * 1.15,
            tier=tier,
            roof_flare=_prop(props, 'roof_flare', 0.38),
            floor_levels=floor_decks, front_y=wing_front,
            arch_passage=bool(_prop(props, 'town_hall_composer', False)),
        )
    if _prop(props, 'has_corner_turrets', False):
        # Square corner towers, one full storey taller than the eaves. They sit
        # fully outside the wall planes (annex-style) so they never clash with
        # the interior, floor slabs or stairs, and connect via a doorway per
        # storey cut into the hall side wall.
        _eave = ctx.found_h + ctx.num_floors * ctx.floor_h
        tur_top = _eave + ctx.floor_h * 0.95
        tur_half = max(1.0, min(2.0, _prop(props, 'corner_turret_size', 1.35)))
        _levels = [ctx.found_h + i * ctx.floor_h for i in range(ctx.num_floors)]
        _wt = ctx.wall_t
        _t_cy = base_hy + _wt * 0.5 - tur_half
        for _sx in (-1.0, 1.0):
            build_corner_turret(
                bm,
                cx=_sx * (base_hx + _wt * 0.5 + tur_half), cy=_t_cy,
                z_ground=0.0, half=tur_half, wall_top_z=tur_top, tier=tier,
                out_sx=_sx, out_sy=1.0, floor_levels=_levels,
                floor_h=ctx.floor_h, main_wall_top=_eave,
                attach_tuck=max(0.30, _wt),
                plank_direction=ctx.plank_dir, seed=ctx.seed)
    if _prop(props, 'has_arched_porch', False):
        build_arched_porch(bm, door_x=ctx.main_door_cx, front_y=ctx.main_door_yf,
                           z_ground=0.0, z_floor=ctx.found_h,
                           tier=tier, plank_direction=ctx.plank_dir)
    if _prop(props, 'has_entry_ramp', False):
        build_entry_ramp(bm, door_x=ctx.main_door_cx, front_y=ctx.main_door_yf,
                         z_floor=ctx.found_h, width=1.6, side_offset=2.2)
    # Town Hall composer: annex volume + forecourt ramparts (tower arch above)
    if _prop(props, 'town_hall_composer', False) and ctx.shape == 'T_SHAPE':
        build_town_hall_composer(bm, props, {
            'tier': tier, 'base_hx': base_hx, 'base_d': ctx.base_d,
            'found_h': ctx.found_h, 'floor_h': ctx.floor_h, 'num_floors': ctx.num_floors,
            'wing_front': wing_front, 'door_x': ctx.main_door_cx,
            'seed': ctx.seed, 'fl1_bounds': ctx.floor_wall_bounds.get(1, None),
            'floor_wall_bounds': ctx.floor_wall_bounds, 'wall_t': ctx.wall_t,
        })


def build_architectural_accessories(bm, props, ctx):
    """Build every enabled outcrop, balcony, overhang and civic landmark."""
    tier = _prop(props, 'material_tier', 'TIER_3')
    _build_mini_wing(bm, props, ctx, tier)
    _build_balconies(bm, props, ctx, tier)
    _build_pillared_overhang(bm, props, ctx, tier)
    _build_civic_landmarks(bm, props, ctx, tier)
