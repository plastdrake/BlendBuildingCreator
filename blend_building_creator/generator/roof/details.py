"""Roof detail phases: dormers, roof spire turret, roof clock spire and chimney.

Each function is a self-contained phase lifted out of ``attic.build_roof_and_attic``
so the orchestrating roof builder reads as a sequence of named steps.
"""

import math
from . import build_dormer, build_roof_turret, build_fantasy_chimney
from ..accessories.tower import build_roof_clock_spire


def build_roof_dormers(bm, props, effective_archetype, roof_style,
                       dormer_placements, wing_dormer_placements,
                       z_dormer_base, main_dormer_w, cur_dormer_h,
                       cur_dormer_roof_h, cur_dormer_reach, flare_val):
    """Place every main-roof and wing dormer window."""
    if not (props.has_dormers and roof_style in ('SWAY', 'GABLE')
            and effective_archetype != 'WATCHTOWER'):
        return
    tier_val = getattr(props, 'material_tier', 'TIER_3')
    for dp in dormer_placements:
        build_dormer(
            bm,
            center_pos=dp['pos'],
            z_base=z_dormer_base,
            facing_dir=dp['facing'],
            dormer_w=dp.get('dormer_w', main_dormer_w), dormer_d=1.35, dormer_h=cur_dormer_h,
            dormer_roof_h=cur_dormer_roof_h,
            roof_flare=flare_val,
            tier=tier_val,
            max_back_reach=cur_dormer_reach,
            roof_style=roof_style,
            sway_amount=props.roof_sway if roof_style == 'SWAY' else 0.0
        )
    for wdp in wing_dormer_placements:
        build_dormer(
            bm,
            center_pos=wdp['pos'],
            z_base=wdp['z_base'],
            facing_dir=wdp['facing'],
            dormer_w=wdp['dormer_w'],
            dormer_d=wdp['dormer_d'],
            dormer_h=wdp['dormer_h'],
            dormer_roof_h=wdp['dormer_roof_h'],
            roof_flare=flare_val,
            tier=tier_val,
            max_back_reach=wdp['max_back_reach'],
            roof_style=roof_style,
            sway_amount=wdp['sway_amount']
        )


def _roof_surface_point(props, is_rotated_roof, roof_style, flare_val,
                        top_hx, top_hy, top_cx, top_cy, top_z,
                        pos_x, pos_y, cross_min):
    """Resolve (cx, cy, z) where a roof fixture seats on the roof surface.

    Shared by the roof spire turret and the roof clock spire: both use the same
    slope-drop + sway-sag maths with the cross-axis coordinate swapped for a
    rotated roof (``cross_min`` is top_x_min when rotated, else top_y_min).
    """
    if is_rotated_roof:
        roof_half_w = top_hy + props.roof_overhang
        cx = top_cx + pos_x * top_hx * 0.75
        cy = top_cy + pos_y * roof_half_w * 0.65
        u = min(1.0, max(0.0, abs(cy - top_cy) / max(0.01, roof_half_w)))
        cross = cx
        cross_half = top_hx
    else:
        roof_half_w = top_hx + props.roof_overhang
        cx = top_cx + pos_x * roof_half_w * 0.65
        cy = top_cy + pos_y * top_hy * 0.75
        u = min(1.0, max(0.0, abs(cx - top_cx) / max(0.01, roof_half_w)))
        cross = cy
        cross_half = top_hy
    drop = (1.0 - flare_val) * u + flare_val * (1.0 - (1.0 - u) ** 2)
    if roof_style == 'SWAY':
        t = max(0.0, min(1.0, (cross - cross_min) / max(0.01, 2.0 * cross_half)))
        sag = math.sin(t * math.pi) * getattr(props, 'roof_sway', 0.25)
    else:
        sag = 0.0
    z = (top_z + props.roof_height - sag) - drop * (props.roof_height + 0.10)
    return cx, cy, z


def build_roof_spire_turret(bm, props, effective_archetype, roof_style,
                            is_rotated_roof, top_hx, top_hy, top_cx, top_cy,
                            top_x_min, top_y_min, top_z, flare_val):
    """Fairytale spire turret seated on the roof pitch (with attic penetration)."""
    if not (getattr(props, 'has_roof_turret', False)
            and effective_archetype != 'WATCHTOWER'):
        return
    cross_min = top_x_min if is_rotated_roof else top_y_min
    cx, cy, z = _roof_surface_point(
        props, is_rotated_roof, roof_style, flare_val,
        top_hx, top_hy, top_cx, top_cy, top_z,
        getattr(props, 'roof_turret_pos_x', 0.0),
        getattr(props, 'roof_turret_pos_y', -0.25),
        cross_min,
    )
    build_roof_turret(
        bm,
        center_pos=(cx, cy),
        z_base=z,
        turret_w=1.3,
        turret_h=1.9,
        spire_h=2.4,
        style=getattr(props, 'roof_turret_style', 'OCTAGONAL'),
        roof_flare=flare_val,
        scale=getattr(props, 'roof_turret_scale', 1.0),
    )


def build_roof_clock_spire_pass(bm, props, effective_archetype, roof_style,
                                is_rotated_roof, top_hx, top_hy, top_cx, top_cy,
                                top_x_min, top_y_min, top_z, flare_val):
    """Roof-mounted clock spire (Tier 1 small / Tier 2 bigger town hall clocks)."""
    if not (getattr(props, 'has_roof_clock_spire', False)
            and effective_archetype != 'WATCHTOWER'):
        return
    cross_min = top_x_min if is_rotated_roof else top_y_min
    cx, cy, z = _roof_surface_point(
        props, is_rotated_roof, roof_style, flare_val,
        top_hx, top_hy, top_cx, top_cy, top_z,
        getattr(props, 'roof_clock_pos_x', 0.0),
        getattr(props, 'roof_clock_pos_y', -0.20),
        cross_min,
    )
    build_roof_clock_spire(bm, cx=cx, cy=cy, z_base=z,
                           scale=getattr(props, 'roof_clock_scale', 0.85),
                           tier=getattr(props, 'material_tier', 'TIER_3'))


def build_roof_chimney(bm, props, effective_archetype,
                       dormer_placements, wing_dormer_placements,
                       top_cx, top_cy, top_hx, top_hy,
                       top_x_min, top_x_max, top_y_min, top_y_max, total_height,
                       annex_band=None):
    """Stylized crooked stone chimney that dodges pillared overhangs and dormers."""
    # Bakery builds its own dedicated bake-oven flue in the accessories phase, so
    # it must not also receive this generic (unrelated) chimney.
    if not (props.has_chimney and effective_archetype not in ('WATCHTOWER', 'BAKERY')):
        return
    cpx = getattr(props, 'chimney_pos_x', 0.55)
    cpy = getattr(props, 'chimney_pos_y', 0.55)
    # If pillared overhang active, force chimney to opposite side
    if getattr(props, 'has_pillared_overhang', False):
        p_side = getattr(props, 'pillared_overhang_side', 'FRONT')
        if p_side == 'FRONT' and cpy < 0.15:
            cpy = 0.65
        if p_side == 'BACK' and cpy > -0.15:
            cpy = -0.65
        if p_side == 'LEFT' and cpx < 0.15:
            cpx = 0.65
        if p_side == 'RIGHT' and cpx > -0.15:
            cpx = -0.65
    chim_x = top_cx + cpx * top_hx * 0.75
    chim_y = top_cy + cpy * top_hy * 0.75
    # Clamp inside roof
    chim_x = max(top_x_min + 0.9, min(top_x_max - 0.9, chim_x))
    chim_y = max(top_y_min + 0.9, min(top_y_max - 0.9, chim_y))
    # Nudge away from dormer placements - push along whichever axis is tightest so
    # collisions purely in X (dormers sit far left/right on the roof slope) actually
    # get resolved instead of only ever shifting Y.
    clearance = 1.0
    for _pass in range(4):
        moved = False
        for dp in (dormer_placements + wing_dormer_placements):
            dx = chim_x - dp['pos'][0]
            dy = chim_y - dp['pos'][1]
            if abs(dx) < clearance and abs(dy) < clearance:
                if abs(dx) <= abs(dy):
                    chim_x += (clearance - abs(dx) + 0.05) * (1.0 if dx >= 0 else -1.0)
                    chim_x = max(top_x_min + 0.9, min(top_x_max - 0.9, chim_x))
                else:
                    chim_y += (clearance - abs(dy) + 0.05) * (1.0 if dy >= 0 else -1.0)
                    chim_y = max(top_y_min + 0.9, min(top_y_max - 0.9, chim_y))
                moved = True
        if not moved:
            break
    # Keep the chimney out of a full-height annex's roof band (its valley
    # extension sweeps across that part of the main slope).
    if annex_band is not None:
        _as, _ay0, _ay1 = annex_band
        if (chim_x - top_cx) * _as > -0.2 and _ay0 <= chim_y <= _ay1:
            if chim_y - _ay0 < _ay1 - chim_y:
                chim_y = _ay0 - 0.60
            else:
                chim_y = _ay1 + 0.60
            chim_y = max(top_y_min + 0.9, min(top_y_max - 0.9, chim_y))
            if _ay0 <= chim_y <= _ay1:
                chim_x = top_cx - _as * abs(chim_x - top_cx)
                chim_x = max(top_x_min + 0.9, min(top_x_max - 0.9, chim_x))
    chim_total_h = total_height + 0.8
    build_fantasy_chimney(
        bm,
        pos_xy=(chim_x, chim_y),
        z_start=0.0,
        total_height=chim_total_h,
        width=0.75, depth=0.75,
        crooked_angle=0.03
    )
