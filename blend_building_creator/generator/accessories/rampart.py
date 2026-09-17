"""Reusable rampart accessories: elevated rampart walks, sloped ramps and the
grounded stone entrance terrace/ramp.

Previously the rampart walk lived in ``town_hall.py`` (only reachable through
the T-shaped composer) and the entrance ramp in ``civic.py``, with the sloped
plank ramp + paired railings duplicated in both.
"""

import math
from ..mesh_utils import create_beveled_box
from ..railing import build_railing
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_CUT_STONE,
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME,
)


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
                       ramp_outer=False, ramp_cx=None):
    """Elevated timber rampart walk: plank deck at upper-floor level on wooden
    posts, outer + end timber parapets, and a sloped plank ramp descending to
    grade. The ramp is placed at the front end when the walk starts at the
    clock tower.
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
    build_railing(bm, (rail_x, y0), (rail_x, y1), deck_top_z, height=1.05)
    for ey, is_ramp_end in ((y0 + 0.12, not ramp_at_back),
                            (y1 - 0.12, ramp_at_back)):
        if is_ramp_end:
            continue
        build_railing(bm, (wall_face_x + side_sgn * 0.12, ey),
                      (rail_x, ey), deck_top_z, height=1.05, braces=False)
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


def build_side_rampart_for_shape(bm, props, ctx):
    """Place an elevated rampart walk along a side facade for any footprint.

    Mirrors the town-hall placement (deck starts at the back wall, ramp descends
    at the front) but makes no assumptions about a clock tower or turret, so it
    also works on U/L/rectangular barracks. The walk stays on the main block so
    it never runs over the front wings.
    """
    side = getattr(props, 'rampart_side', 'RIGHT')
    sgn = 1.0 if side == 'RIGHT' else -1.0
    fl1 = ctx.floor_wall_bounds.get(1)
    if fl1 is not None:
        face = fl1[1] if sgn > 0 else fl1[0]
    else:
        face = sgn * ctx.base_w * 0.5
    base_hy = ctx.base_d * 0.5
    deck_y1 = base_hy + 0.45
    deck_y0 = max(-base_hy + 0.5, deck_y1 - 7.0)
    if deck_y1 - deck_y0 < 5.5:
        deck_y0 = deck_y1 - 5.5
    deck_top = ctx.found_h + ctx.floor_h + 0.11
    build_rampart_walk(bm, side_sgn=sgn, wall_face_x=face,
                       deck_cy=(deck_y0 + deck_y1) * 0.5,
                       deck_len=deck_y1 - deck_y0,
                       deck_top_z=deck_top,
                       width=2.6, tier=getattr(props, 'material_tier', 'TIER_3'),
                       ramp_at_back=False)


def build_entry_ramp(bm, door_x, front_y, z_floor=0.6, width=1.6, length=None,
                     side_offset=2.2):
    """Raised stone entrance rampart: terrace at door level with parapets + side ramp.

    The terrace wraps the front steps; the ramp descends from its right end to
    grade. Parapet rampart walls (with coping) replace thin rails on the terrace,
    timber handrails run along the sloped ramp only.
    """
    rise = max(0.2, z_floor)
    ramp_len = length if length else rise * 5.0 + 2.5
    deck_t = 0.22
    deck_top = z_floor

    # Terrace platform wrapping the entrance (steps land on it)
    terr_w = 5.6
    terr_d = 2.4
    terr_cx = door_x + 0.9
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

    # Sloped ramp descending from the terrace mouth to grade
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
