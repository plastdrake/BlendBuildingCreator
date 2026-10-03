"""Reusable rampart accessories: elevated rampart walks, sloped ramps and the
grounded stone entrance terrace/ramp.

Previously the rampart walk lived in ``town_hall.py`` (only reachable through
the T-shaped composer) and the entrance ramp in ``civic.py``, with the sloped
plank ramp + paired railings duplicated in both.
"""

import math
from ..mesh_utils import create_beveled_box
from ..railing import build_railing
from .battlement import build_battlement_run
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_CUT_STONE,
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME,
)


def _rects_overlap(a, b, pad=0.0):
    """Rects as (x0, x1, y0, y1)."""
    return not (a[1] + pad < b[0] or a[0] - pad > b[1] or
                a[3] + pad < b[2] or a[2] - pad > b[3])


def _sloped_deck(bm, cx, width, diag, mid_y, mid_z, tilt, mat_index):
    """A single tilted plank/stone deck forming a ramp surface."""
    create_beveled_box(bm, size=(width, diag, 0.14),
                       location=(cx, mid_y, mid_z - 0.07),
                       rotation=(tilt, 0.0, 0.0), mat_index=mat_index,
                       bevel_amount=0.015)


def _sloped_railings(bm, cx, width, top_y, foot_y, deck_top_z):
    """Matching guard railings down both sides of a sloped ramp."""
    for s in (-1.0, 1.0):
        px = cx + s * (width * 0.5 + 0.02)
        build_railing(bm, (px, top_y), (px, foot_y),
                      deck_top_z, height=0.95, base_z_end=0.0,
                      baluster_spacing=0.24, braces=False)


def build_rampart_walk(bm, side_sgn, wall_face_x, deck_cy, deck_len=7.0,
                       deck_top_z=3.7, width=2.3, tier='TIER_3', ramp_at_back=False,
                       ramp_outer=False, ramp_cx=None, battlements=False,
                       battlement_style='STONE', skip_ramp=False):
    """Elevated timber rampart walk: plank deck at upper-floor level on wooden
    posts, outer + end timber parapets, and a sloped plank ramp descending to
    grade. The ramp is placed at the front end when the walk starts at the
    clock tower. With ``skip_ramp`` the deck is built with both ends railed
    and no ground ramp (used when neither descent fits the yard).
    """
    outer_x = wall_face_x + side_sgn * width
    cx = (wall_face_x + outer_x) * 0.5
    y0, y1 = deck_cy - deck_len * 0.5, deck_cy + deck_len * 0.5
    deck_t = 0.20
    # Plank deck slab + wooden support posts down to grade with wall corbels
    create_beveled_box(bm, size=(width, deck_len, deck_t),
                       location=(cx, deck_cy, deck_top_z - deck_t * 0.5),
                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.02)
    n_piers = max(2, int(deck_len / 2.2) + 1)
    for i in range(n_piers):
        py = y0 + 0.4 + (deck_len - 0.8) * (i / max(1, n_piers - 1))
        create_beveled_box(bm, size=(0.34, 0.34, deck_top_z - deck_t - 0.30),
                           location=(outer_x - side_sgn * 0.1, py, 0.30 + (deck_top_z - deck_t - 0.30) * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.018)
        create_beveled_box(bm, size=(0.50, 0.50, 0.30),
                           location=(outer_x - side_sgn * 0.1, py, 0.15),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        create_beveled_box(bm, size=(0.16, 0.5, 0.5),
                           location=(wall_face_x + side_sgn * 0.05, py, deck_top_z - deck_t - 0.25),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
    # Detailed timber guard railings (outer edge + both ends) instead of a
    # solid plank wall. The ramp end is left open so the ramp meets the deck.
    rail_x = outer_x - side_sgn * 0.12
    if battlements:
        build_battlement_run(bm, (rail_x, y0), (rail_x, y1), deck_top_z,
                             height=0.85, thickness=0.28, style=battlement_style)
    else:
        build_railing(bm, (rail_x, y0), (rail_x, y1), deck_top_z, height=1.05)
    for ey, is_ramp_end in ((y0 + 0.12, not ramp_at_back and not skip_ramp),
                            (y1 - 0.12, ramp_at_back and not skip_ramp)):
        if is_ramp_end:
            continue
        build_railing(bm, (wall_face_x + side_sgn * 0.12, ey),
                      (rail_x, ey), deck_top_z, height=1.05, braces=False)
    if skip_ramp:
        return
    # Sloped plank ramp from one deck end down to grade. It descends away from
    # the front toward the clock tower so you climb it onto the walk.
    rise = deck_top_z
    ramp_len = rise * 1.9 + 1.3
    ramp_w = 1.5
    if ramp_cx is not None:
        rcx = ramp_cx
    elif ramp_outer:
        rcx = outer_x - side_sgn * (ramp_w * 0.5 + 0.14)
    else:
        rcx = cx
    dir_sgn = 1.0 if ramp_at_back else -1.0
    start_y = (y1 - 0.3) if ramp_at_back else (y0 + 0.3)
    mid_y = start_y + dir_sgn * ramp_len * 0.5
    mid_z = deck_top_z - rise * 0.5
    tilt = math.atan2(rise, ramp_len) * (-dir_sgn)
    diag = math.sqrt(rise * rise + ramp_len * ramp_len)
    _sloped_deck(bm, rcx, ramp_w, diag, mid_y, mid_z, tilt, MAT_INDEX_WOOD)
    foot_y = start_y + dir_sgn * ramp_len
    _sloped_railings(bm, rcx, ramp_w, start_y, foot_y, deck_top_z)


def town_hall_deck_span(props, base_hx, base_d, found_h, floor_h, wing_front):
    """Y-span and deck-top Z of the town-hall composer side rampart walk.

    Single source of truth shared by the deck builder (town_hall.py) and the
    upper-door placement (floors.py) so the door always lands on the physical
    deck instead of the wall centre, which can sit past the deck end next to
    the descent ramp. The ramp always leaves from the FRONT end, so callers
    should bias the door toward the BACK end.
    """
    tower_side = getattr(props, 'clock_tower_side', 'RIGHT')
    t_size = getattr(props, 'clock_tower_size', 3.0)
    has_tower = getattr(props, 'has_clock_tower', False)
    base_hy = base_d * 0.5
    r_side = getattr(props, 'rampart_side', 'RIGHT')
    t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
    r_sgn = 1.0 if r_side == 'RIGHT' else -1.0
    has_turrets = bool(getattr(props, 'has_corner_turrets', False))
    deck_top = found_h + floor_h + 0.11
    ramp_len = deck_top * 1.9 + 1.3
    if has_tower and t_sgn == r_sgn:
        t_cy = wing_front + t_size * 0.5 - 0.25
        t_plinth = t_size * 0.5 + 0.45
        deck_y0 = (t_cy + t_plinth) + 0.10 + ramp_len
    else:
        deck_y0 = -3.0
        if deck_y0 > -base_hy * 0.5:
            deck_y0 = -base_hy * 0.5 - 1.0
    if has_turrets:
        deck_y1 = base_hy + 0.45
    else:
        deck_y1 = deck_y0 + 7.0
    if deck_y1 - deck_y0 < 5.5:
        deck_y1 = deck_y0 + 5.5
    return deck_y0, deck_y1, deck_top


def rampart_deck_span(props, ctx):
    """World-space Y span of the generic side rampart deck.

    Spans the whole main side wall (front to back) so an upper side door at the
    wall centre always lands safely on the deck, away from the descent ramp.
    Returns None when a wing projects from the same side (the walk would collide).
    """
    side = getattr(props, 'rampart_side', 'RIGHT')
    if any(w.get('wall') == side for w in ctx.wings):
        return None
    base_hy = ctx.base_d * 0.5
    return (-base_hy + 0.5, base_hy + 0.45)


def _rampart_obstacles(props, ctx):
    """Obstacle rects (x0, x1, y0, y1) the rampart walk and its descent must
    avoid: courtyard towers, projecting wings and the entry terrace. Also
    returns the enclosure Y bounds (or infinities when open)."""
    from .palisade import compound_bounds, fortification_offset, fortification_depth_extra
    from .bastion import courtyard_tower_footprints

    has_towers = bool(getattr(props, 'has_bastion_towers', False))
    obstacles = list(courtyard_tower_footprints(props, ctx)) if has_towers else []
    for w in (getattr(ctx, 'wings', []) or []):
        wb = w.get('base')
        if wb:
            obstacles.append((wb[0] - 0.3, wb[1] + 0.3, wb[2] - 0.3, wb[3] + 0.3))
    if bool(getattr(props, 'has_entry_ramp', False)):
        _rise = max(0.2, float(getattr(ctx, 'found_h', 0.6)))
        _rlen = _rise * 5.0 + 2.5
        _dx = float(getattr(ctx, 'main_door_cx', 0.0))
        _fy = float(getattr(ctx, 'main_door_yf', 0.0))
        obstacles.append((_dx - 2.8, _dx + 3.7, _fy - 2.1 - _rlen, _fy + 0.4))

    has_enclosure = bool(getattr(props, 'has_palisade', False) or
                         getattr(props, 'has_curtain_wall', False))
    if has_enclosure:
        off = fortification_offset(props)
        _cx0, _cx1, cy0, cy1 = compound_bounds(
            ctx, off, fortification_depth_extra(props))
    else:
        cy0, cy1 = -1e9, 1e9
    return obstacles, cy0, cy1, has_enclosure


def _descent_choice(props, ctx, sgn, face, deck_y0, deck_y1, deck_top):
    """Pick where the rampart descent ramp goes: 'FRONT', 'BACK' or None.

    The ~9m ramp must neither pierce the palisade/curtain line nor land on a
    tower, wing or entry terrace. First fitting option wins; None means the
    deck is built without a ground ramp (still reached via the upper door).
    """
    obstacles, cy0, cy1, has_enclosure = _rampart_obstacles(props, ctx)

    rise = deck_top
    ramp_len = rise * 1.9 + 1.3
    rcx = face + sgn * 1.30
    for option, start_y, direction in (('FRONT', deck_y0 + 0.3, -1.0),
                                       ('BACK', deck_y1 - 0.3, 1.0)):
        foot_y = start_y + direction * ramp_len
        lo, hi = (foot_y, start_y) if direction < 0 else (start_y, foot_y)
        ramp_rect = (rcx - 0.95, rcx + 0.95, lo - 0.3, hi + 0.3)
        if has_enclosure and (lo < cy0 + 0.8 or hi > cy1 - 0.8):
            continue
        if any(_rects_overlap(ramp_rect, ob, pad=0.25) for ob in obstacles):
            continue
        return option
    return None


def build_side_rampart_for_shape(bm, props, ctx):
    """Place an elevated rampart walk along a side facade for any footprint.

    Mirrors the town-hall placement (deck starts at the back wall, ramp descends
    at the front) but makes no assumptions about a clock tower or turret, so it
    also works on U/L/rectangular barracks. The walk spans the main side wall and
    is skipped when a wing projects from that same side. The descent ramp takes
    the first end (front, else back) that fits the yard without hitting towers,
    wings or the enclosure; otherwise the deck is built without a ground ramp.
    """
    span = rampart_deck_span(props, ctx)
    if span is None:
        return
    side = getattr(props, 'rampart_side', 'RIGHT')
    sgn = 1.0 if side == 'RIGHT' else -1.0
    fl1 = ctx.floor_wall_bounds.get(1)
    if fl1 is not None:
        face = fl1[1] if sgn > 0 else fl1[0]
    else:
        face = sgn * ctx.base_w * 0.5
    deck_y0, deck_y1 = span
    deck_top = ctx.found_h + ctx.floor_h + 0.11
    # The deck itself must clear towers and wings too (the old full-side span
    # could bury its front end in a wing roof or tower); otherwise skip it all.
    obstacles, _cy0, _cy1, _has_enc = _rampart_obstacles(props, ctx)
    _dx0, _dx1 = (face, face + sgn * 2.6) if sgn > 0 else (face + sgn * 2.6, face)
    if any(_rects_overlap((_dx0, _dx1, deck_y0, deck_y1), ob, pad=0.15) for ob in obstacles):
        return
    choice = _descent_choice(props, ctx, sgn, face, deck_y0, deck_y1, deck_top)
    build_rampart_walk(bm, side_sgn=sgn, wall_face_x=face,
                       deck_cy=(deck_y0 + deck_y1) * 0.5,
                       deck_len=deck_y1 - deck_y0,
                       deck_top_z=deck_top,
                       width=2.6, tier=getattr(props, 'material_tier', 'TIER_3'),
                       ramp_at_back=(choice == 'BACK'),
                       battlements=bool(getattr(props, 'has_battlements', False)),
                       battlement_style=getattr(props, 'battlement_style', 'STONE'),
                       skip_ramp=(choice is None))


def build_entry_ramp(bm, door_x, front_y, z_floor=0.6, width=1.6, length=None,
                     side_offset=2.2, towers=()):
    """Raised stone entrance rampart: terrace at door level with parapets + side ramp.

    The terrace wraps the front steps; the ramp descends from its right end to
    grade. Parapet rampart walls (with coping) replace thin rails on the terrace,
    timber handrails run along the sloped ramp only. ``towers`` are courtyard
    tower footprints (x0, x1, y0, y1): the whole assembly sidesteps clear of
    them (keeping the door covered); if it cannot clear, the sloped ramp is
    dropped and the terrace alone remains.
    """
    rise = max(0.2, z_floor)
    ramp_len = length if length else rise * 5.0 + 2.5
    deck_t = 0.22
    deck_top = z_floor

    # Terrace platform wrapping the entrance (steps land on it)
    terr_w = 5.6
    terr_d = 2.4
    terr_cx = door_x + 0.9
    build_ramp = True
    for (tx0, tx1, ty0, ty1) in (towers or ()):
        for _ in range(4):
            foot = (terr_cx - 2.8, terr_cx + 3.4,
                    front_y - 2.1 - ramp_len, front_y + 0.4)
            if not _rects_overlap(foot, (tx0, tx1, ty0, ty1), pad=0.2):
                break
            tcx = (tx0 + tx1) * 0.5
            step = 0.4 if terr_cx < tcx else -0.4
            if abs((terr_cx + step) - (door_x + 0.9)) > 1.2:
                break
            terr_cx += step
        foot = (terr_cx - 2.8, terr_cx + 3.4,
                front_y - 2.1 - ramp_len, front_y + 0.4)
        if _rects_overlap(foot, (tx0, tx1, ty0, ty1), pad=0.2):
            build_ramp = False
            break
    terr_cy = front_y - terr_d * 0.5 + 0.35
    create_beveled_box(bm, size=(terr_w, terr_d, deck_t + 0.35),
                       location=(terr_cx, terr_cy, deck_top - (deck_t + 0.35) * 0.5 + 0.06),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)

    # Rampart parapets with coping around the terrace (gap left for the ramp)
    parap_h = 0.62
    parap_t = 0.26
    pz = deck_top + parap_h * 0.5
    # Left cheek
    create_beveled_box(bm, size=(parap_t, terr_d, parap_h),
                       location=(terr_cx - terr_w * 0.5 + parap_t * 0.5, terr_cy, pz),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    # Front wall with opening where the ramp joins (ramp on right half)
    ramp_mouth_w = width + 0.3
    mouth_cx = terr_cx + terr_w * 0.5 - ramp_mouth_w * 0.5 - 0.3
    left_seg_w = (mouth_cx - ramp_mouth_w * 0.5) - (terr_cx - terr_w * 0.5)
    if left_seg_w > 0.3:
        create_beveled_box(bm, size=(left_seg_w, parap_t, parap_h),
                           location=(terr_cx - terr_w * 0.5 + left_seg_w * 0.5,
                                     terr_cy - terr_d * 0.5 + parap_t * 0.5, pz),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    # Coping stones on terrace parapets
    for (cw, cd, cpx, cpy) in (
        (parap_t + 0.12, terr_d + 0.06, terr_cx - terr_w * 0.5 + parap_t * 0.5, terr_cy),
    ):
        create_beveled_box(bm, size=(cw, cd, 0.10), location=(cpx, cpy, deck_top + parap_h + 0.05),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)
    if left_seg_w > 0.3:
        create_beveled_box(bm, size=(left_seg_w + 0.06, parap_t + 0.12, 0.10),
                           location=(terr_cx - terr_w * 0.5 + left_seg_w * 0.5,
                                     terr_cy - terr_d * 0.5 + parap_t * 0.5,
                                     deck_top + parap_h + 0.05),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)

    # Sloped ramp descending from the terrace mouth to grade (skipped when a
    # tower forced the terrace aside and the run still will not clear).
    if not build_ramp:
        return
    rcx = mouth_cx
    mid_y = (terr_cy - terr_d * 0.5) - ramp_len * 0.5
    mid_z = deck_top - rise * 0.5
    ang = math.atan2(rise, ramp_len)
    ramp_diag = math.sqrt(rise * rise + ramp_len * ramp_len)
    _sloped_deck(bm, rcx, width, ramp_diag, mid_y, mid_z, ang, MAT_INDEX_CUT_STONE)
    # Sloped stone cheeks + detailed timber guard railings on the ramp
    ramp_top_y = terr_cy - terr_d * 0.5
    ramp_bot_y = ramp_top_y - ramp_len
    for s in (-1.0, 1.0):
        px = rcx + s * (width * 0.5 + 0.02)
        create_beveled_box(bm, size=(0.16, ramp_diag, 0.34),
                           location=(px, mid_y, mid_z + 0.10),
                           rotation=(ang, 0.0, 0.0), mat_index=MAT_INDEX_STONE,
                           bevel_amount=0.01)
    _sloped_railings(bm, rcx, width, ramp_top_y, ramp_bot_y, deck_top)
