"""Town Hall composer: multi-volume sprawling civic composition.

Layers satellite volumes around the engine-built main hall so Tier 2/3 read
like the storybook references instead of a single box:
- side annex: 1-2 storey half-timbered volume with its own perpendicular gable
  roof, surface windows, corner boards and an upper oriel.
- forecourt walls: low stone rampart walls with gate posts stitching tower and
  annex into one courtyard front; the entry ramp leaves through the gate.
- clock-tower arch passage lives in civic.build_clock_tower (arch_passage).
"""

import math
from mathutils import Vector
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE,
)
from ..roof.gable_roof import build_gable_roof
from ..walls import build_wall_with_opening
from ..openings import build_window_assembly
from .mini_wing import build_mini_wing

def _tier_wall_mat(tier):
    """Match the engine's wall logic: planks/wood for Tier 1-2, stucco for Tier 3."""
    return MAT_INDEX_PLASTER_EXT if tier == 'TIER_3' else MAT_INDEX_WOOD


def _surface_window(bm, x, y, z, w=0.9, h=1.2, facing='front', shutters=True):
    """Window mounted proud of a solid annex wall (no cutout needed)."""
    if facing == 'front':  # -Y
        create_beveled_box(bm, size=(w + 0.24, 0.12, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_box(bm, size=(w, 0.10, h), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.08, 0.12, h), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(w, 0.12, 0.08), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(w + 0.34, 0.16, 0.09), location=(x, y - 0.03, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        if shutters:
            for s in (-1.0, 1.0):
                create_box(bm, size=(0.32, 0.05, h + 0.05),
                           location=(x + s * (w * 0.5 + 0.30), y - 0.01, z),
                           mat_index=MAT_INDEX_WOOD)
    elif facing == 'back':  # +Y
        create_beveled_box(bm, size=(w + 0.24, 0.12, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_box(bm, size=(w, 0.10, h), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.08, 0.12, h), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(w, 0.12, 0.08), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(w + 0.34, 0.16, 0.09), location=(x, y + 0.03, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    elif facing == 'outer':  # away from main hall: +/-X given by out_sgn
        raise ValueError("use facing='left' or 'right'")
    elif facing in ('left', 'right'):  # -X / +X
        create_beveled_box(bm, size=(0.12, w + 0.24, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        sgn = -1.0 if facing == 'left' else 1.0
        create_box(bm, size=(0.10, w, h), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.12, 0.08, h), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(0.12, w, 0.08), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(0.16, w + 0.34, 0.09),
                           location=(x + sgn * 0.03, y, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        if shutters:
            for s in (-1.0, 1.0):
                create_box(bm, size=(0.05, 0.32, h + 0.05),
                           location=(x + sgn * 0.01, y + s * (w * 0.5 + 0.30), z),
                           mat_index=MAT_INDEX_WOOD)


def build_side_annex(bm, side_sgn, main_hx, main_cy0, main_cy1, z_ground=0.0,
                     found_h=0.6, floors=2, floor_h=3.0, tier='TIER_3',
                     width=5.2, depth=4.0, roof_h=3.0, plank_direction='HORIZONTAL'):
    """Half-timbered side volume embedded into the main side wall.

    side_sgn: +1 attaches on +X, -1 on -X. width runs along Y, depth along X.
    Returns the outer face X for forecourt layout.
    """
    overlap = 0.6
    wmat_upper = _tier_wall_mat(tier)
    wall_h = floors * floor_h
    top_z = found_h + wall_h

    inner_x = side_sgn * main_hx
    outer_x = side_sgn * (main_hx + depth - overlap)
    cx = (inner_x + outer_x) * 0.5
    cy = (main_cy0 + main_cy1) * 0.5
    y0, y1 = cy - width * 0.5, cy + width * 0.5

    # Foundation plinth
    create_beveled_box(bm, size=(abs(outer_x - inner_x) + 0.4, width + 0.3, found_h + 0.25),
                       location=(cx, cy, z_ground + (found_h + 0.25) * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.025)

    # Walls built by the engine wall builder so the siding (logs / planks / stone)
    # and the window cut-outs + casings match every other wall on the hall.
    wall_t = 0.28
    outer_wall_x = outer_x - side_sgn * wall_t * 0.5
    front_wall_y = y0 + wall_t * 0.5
    back_wall_y = y1 - wall_t * 0.5
    out_normal = (1.0, 0.0) if side_sgn > 0 else (-1.0, 0.0)
    depth_span = abs(outer_x - inner_x)
    for f in range(floors):
        fz0 = found_h + f * floor_h
        fz1 = fz0 + floor_h
        f_mat = MAT_INDEX_STONE if f == 0 else wmat_upper
        win_w = 1.0
        win_h = min(1.25, floor_h * 0.46)
        sill = fz0 + floor_h * 0.30
        # Outer wall (runs along Y); skip its window where the oriel bay sits above
        if not (floors >= 2 and f == floors - 1):
            uc = width * 0.5
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                [{'u_start': uc - win_w * 0.5 - 0.12, 'u_end': uc + win_w * 0.5 + 0.12,
                  'z_start': sill, 'z_end': sill + win_h}],
                mat_ext=f_mat, normal_vec=out_normal, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
            build_window_assembly(
                bm, center=(outer_x, cy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=out_normal, has_shutters=True)
        else:
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t, [],
                mat_ext=f_mat, normal_vec=out_normal, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
        # Front + back walls (run along X)
        ucx = depth_span * 0.5
        for wy, nvec, shutters in ((front_wall_y, (0.0, -1.0), True),
                                   (back_wall_y, (0.0, 1.0), False)):
            build_wall_with_opening(
                bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                [{'u_start': ucx - win_w * 0.5 - 0.12, 'u_end': ucx + win_w * 0.5 + 0.12,
                  'z_start': sill, 'z_end': sill + win_h}],
                mat_ext=f_mat, normal_vec=nvec, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
            build_window_assembly(
                bm, center=(cx, wy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=nvec, has_shutters=shutters)
    # Timber belt course between ground and upper lifts
    if floors >= 2:
        create_beveled_box(bm, size=(abs(outer_x - inner_x) + 0.14, width + 0.14, 0.18),
                           location=(cx, cy, found_h + floor_h),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Corner boards on the outer corners
    for sy in (y0 + 0.08, y1 - 0.08):
        create_beveled_box(bm, size=(0.20, 0.20, wall_h),
                           location=(outer_x, sy, found_h + wall_h * 0.5),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)

    # Upper oriel on the outer face: reuse the shared mini-wing outcrop builder
    # so the annex bay matches every other outcrop on the hall (same casing,
    # window size, corbels and shingled cap) instead of a bespoke box.
    if floors >= 2:
        _ow_side = 'LEFT' if side_sgn < 0 else 'RIGHT'
        _ow_anchor_lo = outer_x if side_sgn < 0 else inner_x
        _ow_anchor_hi = inner_x if side_sgn < 0 else outer_x
        build_mini_wing(
            bm, side=_ow_side, floor_mode='UPPER',
            wall_x_min=_ow_anchor_lo, wall_x_max=_ow_anchor_hi,
            wall_y_min=cy - 1.6, wall_y_max=cy + 1.6,
            z_base=found_h + floor_h, width=min(2.2, width * 0.55), depth=0.9,
            height=min(2.0, floor_h * 0.72), roof_style='LEAN_TO',
            tier=tier, floor_h=floor_h,
            lower_bounds=(_ow_anchor_lo, _ow_anchor_hi, cy - 1.6, cy + 1.6),
        )

    # Cross-gable roof: the ridge points OUTWARD (along the depth / X axis) so the
    # annex reads as a real wing with a street-side gable, instead of a long low
    # shed with a ridge running parallel to the main wall.
    # build_gable_roof's ridge runs along its Y input, so we feed the depth on Y
    # and the width on X. Only the outer gable is built (the inner side dies into
    # the main wall cleanly).
    _ix_lo = min(inner_x, outer_x)
    _ix_hi = max(inner_x, outer_x)
    # The gable must face the street (the outer depth end) and the inner end must
    # terminate flush against the main wall so no roof deck buries into it.
    if side_sgn < 0:
        _gable_ends, _abut_front, _abut_back = ('FRONT',), False, True
    else:
        _gable_ends, _abut_front, _abut_back = ('BACK',), True, False
    build_gable_roof(
        bm,
        x_min=y0,
        x_max=y1,
        y_min=_ix_lo,
        y_max=_ix_hi,
        z_base=top_z,
        roof_height=roof_h,
        overhang=0.20,
        wall_thickness=0.18,
        gable_ends=_gable_ends,
        abut_front=_abut_front,
        abut_back=_abut_back,
        segments_y=3,
        tier=tier,
        plank_direction='HORIZONTAL',
        roof_flare=0.35,
    )
    return outer_x


def build_forecourt_walls(bm, x_left, x_right, y_wall, z_ground=0.0,
                          gate_x=None, gate_w=2.4, wall_h=1.15):
    """Low stone forecourt ramparts with coping, gate posts and ball caps."""
    gate_x = gate_x if gate_x is not None else (x_left + x_right) * 0.5
    g0, g1 = gate_x - gate_w * 0.5, gate_x + gate_w * 0.5
    t = 0.30
    # Wall runs either side of the gate
    for (sx0, sx1) in ((x_left, g0), (g1, x_right)):
        if sx1 - sx0 < 0.4:
            continue
        seg_cx = (sx0 + sx1) * 0.5
        seg_w = sx1 - sx0
        create_beveled_box(bm, size=(seg_w, t, wall_h),
                           location=(seg_cx, y_wall, z_ground + wall_h * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        create_beveled_box(bm, size=(seg_w + 0.04, t + 0.14, 0.12),
                           location=(seg_cx, y_wall, z_ground + wall_h + 0.06),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)
    # Gate posts with caps + iron lantern balls
    for gx in (g0 - 0.15, g1 + 0.15):
        create_beveled_box(bm, size=(0.45, 0.45, wall_h + 0.7),
                           location=(gx, y_wall, z_ground + (wall_h + 0.7) * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        create_beveled_box(bm, size=(0.60, 0.60, 0.14),
                           location=(gx, y_wall, z_ground + wall_h + 0.77),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        create_cylinder(bm, radius=0.11, height=0.22, segments=8,
                        location=(gx, y_wall, z_ground + wall_h + 0.95),
                        mat_index=MAT_INDEX_IRON)


def build_side_rampart(bm, side_sgn, wall_face_x, deck_cy, deck_len=7.0,
                       deck_top_z=3.7, width=2.3, tier='TIER_3'):
    """Elevated side rampart walk: stone deck at upper-floor level on pillars,
    outer + end parapets with coping, and a sloped ramp descending forward to grade.
    """
    outer_x = wall_face_x + side_sgn * width
    cx = (wall_face_x + outer_x) * 0.5
    y0, y1 = deck_cy - deck_len * 0.5, deck_cy + deck_len * 0.5
    deck_t = 0.20
    # Deck slab + support pillars down to grade with wall corbels
    create_beveled_box(bm, size=(width, deck_len, deck_t),
                       location=(cx, deck_cy, deck_top_z - deck_t * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
    n_piers = max(2, int(deck_len / 2.2) + 1)
    for i in range(n_piers):
        py = y0 + 0.4 + (deck_len - 0.8) * (i / max(1, n_piers - 1))
        create_beveled_box(bm, size=(0.42, 0.42, deck_top_z - deck_t),
                           location=(outer_x - side_sgn * 0.1, py, (deck_top_z - deck_t) * 0.5),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.02)
        create_beveled_box(bm, size=(0.16, 0.5, 0.5),
                           location=(wall_face_x + side_sgn * 0.05, py, deck_top_z - deck_t - 0.25),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
    # Parapets (outer + both ends) with coping
    parap_h, parap_t = 1.0, 0.26
    pz = deck_top_z + parap_h * 0.5
    create_beveled_box(bm, size=(parap_t, deck_len, parap_h),
                       location=(outer_x - side_sgn * parap_t * 0.5 + side_sgn * 0.05, deck_cy, pz),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    create_beveled_box(bm, size=(parap_t + 0.12, deck_len + 0.06, 0.10),
                       location=(outer_x - side_sgn * parap_t * 0.5 + side_sgn * 0.05, deck_cy,
                                 deck_top_z + parap_h + 0.05),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)
    for ey in (y0 + parap_t * 0.5, y1 - parap_t * 0.5):
        if ey > y0 + deck_len - 2.6:  # leave the front end open where the ramp joins
            continue
        create_beveled_box(bm, size=(width, parap_t, parap_h),
                           location=(cx, ey, pz),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    # Sloped ramp from the deck's front end down to grade
    rise = deck_top_z
    ramp_len = rise * 2.2 + 1.5
    ramp_w = 1.7
    rcx = cx
    start_y = y0 + 0.3
    mid_y = start_y - ramp_len * 0.5
    mid_z = deck_top_z - rise * 0.5
    ang = math.atan2(rise, ramp_len)
    diag = math.sqrt(rise * rise + ramp_len * ramp_len)
    create_beveled_box(bm, size=(ramp_w, diag, 0.14),
                       location=(rcx, mid_y, mid_z - 0.07),
                       rotation=(ang, 0.0, 0.0), mat_index=MAT_INDEX_CUT_STONE,
                       bevel_amount=0.015)
    for s in (-1.0, 1.0):
        px = rcx + s * (ramp_w * 0.5 + 0.03)
        create_beveled_box(bm, size=(0.15, diag, 0.5),
                           location=(px, mid_y, mid_z + 0.15),
                           rotation=(ang, 0.0, 0.0), mat_index=MAT_INDEX_STONE,
                           bevel_amount=0.01)
        for t in (0.15, 0.55, 0.9):
            py = start_y - ramp_len * t
            pz2 = deck_top_z - rise * t
            create_beveled_box(bm, size=(0.09, 0.09, 0.85),
                               location=(px, py, pz2 + 0.55),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        create_beveled_box(bm, size=(0.08, diag, 0.08),
                           location=(px, mid_y, mid_z + 1.02),
                           rotation=(ang, 0.0, 0.0), mat_index=MAT_INDEX_TIMBER,
                           bevel_amount=0.008)


def build_town_hall_composer(bm, props, ctx):
    """Compose annex + forecourt around the main hall. Returns annex outer X."""
    tier = ctx.get('tier', 'TIER_3')
    base_hx = ctx['base_hx']
    base_d = ctx['base_d']
    found_h = ctx['found_h']
    floor_h = ctx['floor_h']
    num_floors = ctx['num_floors']
    wing_front = ctx['wing_front']
    door_x = ctx.get('door_x', 0.0)
    seed = ctx.get('seed', 42)

    tower_side = getattr(props, 'clock_tower_side', 'RIGHT')
    t_size = getattr(props, 'clock_tower_size', 3.0)
    has_tower = getattr(props, 'has_clock_tower', False)

    annex_outer = None
    if getattr(props, 'has_side_annex', False):
        a_side = -1.0 if tower_side == 'RIGHT' else 1.0
        a_floors = max(1, min(2, getattr(props, 'annex_floors', 2)))
        a_w = 5.2 if tier != 'TIER_1' else 4.4
        a_d = 4.0 if tier != 'TIER_1' else 3.4
        a_roof = 3.0 if tier == 'TIER_3' else 2.6
        # Annex centered on the side wall so its walk-in portal lines up with
        # the doorway cut into the main hall wall (y = 0).
        cy0 = -a_w * 0.5
        cy1 = a_w * 0.5
        annex_outer = build_side_annex(
            bm, side_sgn=a_side, main_hx=base_hx, main_cy0=cy0, main_cy1=cy1,
            z_ground=0.0, found_h=found_h, floors=a_floors, floor_h=floor_h,
            tier=tier, width=a_w, depth=a_d, roof_h=a_roof,
            plank_direction=getattr(props, 'plank_direction', 'HORIZONTAL'),
        )

    # Forecourt wall stitched between tower and annex (or main corners as fallback)
    if has_tower:
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        t_cx = t_sgn * (base_hx + t_size * 0.5 - 0.7)
        tower_inner = t_cx - t_sgn * t_size * 0.5
    else:
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        tower_inner = t_sgn * base_hx
    if annex_outer is not None:
        x_left = min(tower_inner, annex_outer) + 0.4
        x_right = max(tower_inner, annex_outer) - 0.4
    else:
        x_left, x_right = -base_hx + 0.4, base_hx - 0.4
    # NOTE: the front stone forecourt wall was removed by request - it read as a
    # wall stuck onto the front of the hall. The side rampart below replaces it.

    # Side rampart walk (Tier 3): elevated deck + parapets + descent ramp
    if getattr(props, 'has_side_rampart', False):
        r_side = getattr(props, 'rampart_side', 'RIGHT')
        r_sgn = 1.0 if r_side == 'RIGHT' else -1.0
        fl1 = ctx.get('fl1_bounds', None)
        if fl1 is not None:
            r_face = fl1[1] if r_sgn > 0 else fl1[0]
            r_cy = (fl1[2] + fl1[3]) * 0.5
        else:
            base_hx = ctx['base_hx']
            base_d = ctx['base_d']
            r_face = r_sgn * base_hx
            r_cy = 0.0
        build_side_rampart(bm, side_sgn=r_sgn, wall_face_x=r_face, deck_cy=r_cy,
                           deck_len=7.0, deck_top_z=found_h + ctx.get('floor_h', 3.0) + 0.11,
                           width=2.3, tier=tier)
    return annex_outer
