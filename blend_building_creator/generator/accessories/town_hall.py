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
import bmesh
from mathutils import Vector, Matrix
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
)
from ..railing import build_railing
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR,
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
                     width=5.2, depth=4.0, roof_h=3.0, plank_direction='HORIZONTAL',
                     main_bounds_by_floor=None):
    """Half-timbered side volume embedded into the main side wall.

    side_sgn: +1 attaches on +X, -1 on -X. width runs along Y, depth along X.
    main_bounds_by_floor: {floor_idx: (x_min, x_max, y_min, y_max)} of the main
    hall so the annex tracks the jettied wall face on upper floors instead of
    poking into the main hall interior.
    Returns the outer face X for forecourt layout.
    """
    overlap = 0.6
    wmat_upper = _tier_wall_mat(tier)
    wall_h = floors * floor_h
    top_z = found_h + wall_h
    wall_t = 0.28

    outer_x = side_sgn * (main_hx + depth - overlap)
    cy = (main_cy0 + main_cy1) * 0.5
    y0, y1 = cy - width * 0.5, cy + width * 0.5

    def _floor_inner(f):
        if main_bounds_by_floor:
            keys = sorted(main_bounds_by_floor.keys())
            k = f if f in main_bounds_by_floor else keys[-1]
            b = main_bounds_by_floor[k]
            return b[0] if side_sgn < 0 else b[1]
        return side_sgn * main_hx

    floor_inner = {f: _floor_inner(f) for f in range(floors)}
    jetted_inner = max(floor_inner.values(), key=abs)

    # Foundation plinth: top flush with the main floor (no step up) and flared
    # outward only, so it never pushes up through the main hall interior.
    g_inner = floor_inner[0]
    g_span = abs(outer_x - g_inner)
    g_cx = (g_inner + outer_x) * 0.5
    create_beveled_box(bm, size=(g_span + 0.16, width + 0.3, found_h),
                       location=(g_cx + side_sgn * 0.08, cy, z_ground + found_h * 0.5),
                       mat_index=MAT_INDEX_STONE, bevel_amount=0.025)

    # Walls built by the engine wall builder so the siding (logs / planks / stone)
    # and the window cut-outs + casings match every other wall on the hall.
    out_normal = (1.0, 0.0) if side_sgn > 0 else (-1.0, 0.0)
    for f in range(floors):
        fz0 = found_h + f * floor_h
        fz1 = fz0 + floor_h
        f_mat = MAT_INDEX_STONE if f == 0 else wmat_upper
        inner_x = floor_inner[f]
        cxf = (inner_x + outer_x) * 0.5
        outer_wall_x = outer_x - side_sgn * wall_t * 0.5
        front_wall_y = y0 + wall_t * 0.5
        back_wall_y = y1 - wall_t * 0.5
        win_w = 1.0
        win_h = min(1.25, floor_h * 0.46)
        sill = fz0 + floor_h * 0.30
        # Interior plank floor. Its top sits flush with the main hall floor slab
        # (z_floor + 0.05) so it stays clear of the foundation top (no coplanar
        # z-fighting) and reads as the interior floor boards, not stone.
        _fx_inner = inner_x - side_sgn * (wall_t * 0.5 + 0.02)
        _fx_outer = outer_x - side_sgn * wall_t * 0.5
        _fx_min, _fx_max = min(_fx_inner, _fx_outer), max(_fx_inner, _fx_outer)
        create_beveled_box(
            bm, size=(max(0.1, _fx_max - _fx_min), max(0.1, (y1 - wall_t) - (y0 + wall_t)), 0.12),
            location=((_fx_min + _fx_max) * 0.5, cy, fz0 + 0.05 - 0.06),
            mat_index=MAT_INDEX_FLOOR, bevel_amount=0.008)
        # Outer wall (runs along Y). On the top lift the oriel bay sits here, so
        # cut a full-height portal instead of a window: the bay becomes usable
        # interior space connected to the annex room (like every other outcrop).
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
            oriel_w = min(2.2, width * 0.55)
            oriel_h = min(2.0, floor_h * 0.72)
            uc = width * 0.5
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                [{'u_start': uc - oriel_w * 0.5 + 0.10, 'u_end': uc + oriel_w * 0.5 - 0.10,
                  'z_start': fz0 + 0.10, 'z_end': fz0 + oriel_h - 0.05}],
                mat_ext=f_mat, normal_vec=out_normal, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
        # Front + back walls (run along X)
        ucx = abs(outer_x - inner_x) * 0.5
        for wy, nvec, shutters in ((front_wall_y, (0.0, -1.0), True),
                                   (back_wall_y, (0.0, 1.0), False)):
            build_wall_with_opening(
                bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                [{'u_start': ucx - win_w * 0.5 - 0.12, 'u_end': ucx + win_w * 0.5 + 0.12,
                  'z_start': sill, 'z_end': sill + win_h}],
                mat_ext=f_mat, normal_vec=nvec, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
            build_window_assembly(
                bm, center=(cxf, wy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=nvec, has_shutters=shutters)
    top_inner = floor_inner[floors - 1]
    # Timber belt course between ground and upper lifts. Kept below the upper
    # floor boards so it never covers the interior floor, and measured from the
    # jettied wall face so it cannot poke into the main hall.
    if floors >= 2:
        b_span = abs(outer_x - jetted_inner)
        b_cx = (jetted_inner + outer_x) * 0.5
        create_beveled_box(bm, size=(b_span + 0.14, width + 0.14, 0.18),
                           location=(b_cx, cy, found_h + floor_h - 0.20),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Corner boards on the outer corners
    for sy in (y0 + 0.08, y1 - 0.08):
        create_beveled_box(bm, size=(0.28, 0.28, wall_h),
                           location=(outer_x, sy, found_h + wall_h * 0.5),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)

    # Upper oriel on the outer face: reuse the shared mini-wing outcrop builder
    # so the annex bay matches every other outcrop on the hall (same casing,
    # window size, corbels and shingled cap) instead of a bespoke box.
    if floors >= 2:
        _ow_side = 'LEFT' if side_sgn < 0 else 'RIGHT'
        _ow_anchor_lo = outer_x if side_sgn < 0 else top_inner
        _ow_anchor_hi = top_inner if side_sgn < 0 else outer_x
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
    # shed with a ridge running parallel to the main wall. build_gable_roof is
    # axis-aligned (ridge along its Y input), so we build the roof in a local
    # frame with the ridge along the annex depth and rotate it 90 deg into place.
    # The outer depth end carries the gable; the inner end (the jettied main wall
    # face) abuts flush with zero overhang so no deck buries into the hall.
    _annex_depth = abs(outer_x - top_inner)
    _roof_cx = (top_inner + outer_x) * 0.5
    if side_sgn < 0:
        _gable_ends, _abut_front, _abut_back = ('BACK',), True, False
    else:
        _gable_ends, _abut_front, _abut_back = ('FRONT',), False, True
    annex_roof_bm = bmesh.new()
    build_gable_roof(
        annex_roof_bm,
        x_min=-width * 0.5,
        x_max=width * 0.5,
        y_min=-_annex_depth * 0.5,
        y_max=_annex_depth * 0.5,
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
    bmesh.ops.transform(
        annex_roof_bm,
        matrix=Matrix.Rotation(math.radians(90.0), 4, 'Z'),
        verts=annex_roof_bm.verts,
    )
    for v in annex_roof_bm.verts:
        v.co += Vector((_roof_cx, cy, 0.0))
    uv_src = annex_roof_bm.loops.layers.uv.verify()
    uv_dst = bm.loops.layers.uv.verify()
    vert_map = {v: bm.verts.new(v.co) for v in annex_roof_bm.verts}
    for f in annex_roof_bm.faces:
        try:
            nf = bm.faces.new([vert_map[v] for v in f.verts])
            nf.material_index = f.material_index
            nf.smooth = f.smooth
            for l_src, l_dst in zip(f.loops, nf.loops):
                l_dst[uv_dst].uv = l_src[uv_src].uv
        except ValueError:
            pass
    annex_roof_bm.free()
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
    create_beveled_box(bm, size=(ramp_w, diag, 0.14),
                       location=(rcx, mid_y, mid_z - 0.07),
                       rotation=(tilt, 0.0, 0.0), mat_index=MAT_INDEX_WOOD,
                       bevel_amount=0.015)
    # Matching detailed guard railings down both sides of the sloped ramp.
    foot_y = start_y + dir_sgn * ramp_len
    for s in (-1.0, 1.0):
        px = rcx + s * (ramp_w * 0.5 + 0.02)
        build_railing(bm, (px, start_y), (px, foot_y),
                      deck_top_z, height=0.95, base_z_end=0.0,
                      baluster_spacing=0.24, braces=False)


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
            main_bounds_by_floor=ctx.get('floor_wall_bounds', None),
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

    # Side rampart walk (Tier 3): elevated deck + parapets + descent ramp.
    # The deck starts inside the clock tower and runs back along the side so the
    # tower walk and the rampart read as one continuous elevated walk; the ramp
    # then descends beyond the corner turret along the deck's outer edge.
    if getattr(props, 'has_side_rampart', False):
        r_side = getattr(props, 'rampart_side', 'RIGHT')
        r_sgn = 1.0 if r_side == 'RIGHT' else -1.0
        fl1 = ctx.get('fl1_bounds', None)
        if fl1 is not None:
            r_face = fl1[1] if r_sgn > 0 else fl1[0]
        else:
            r_face = r_sgn * ctx['base_hx']
        base_hy = ctx['base_d'] * 0.5
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        has_turrets = bool(getattr(props, 'has_corner_turrets', False))
        tr_half = max(1.0, min(2.0, getattr(props, 'corner_turret_size', 1.35)))
        deck_top = found_h + ctx.get('floor_h', 3.0) + 0.11
        ramp_len = deck_top * 1.9 + 1.3
        if has_tower and t_sgn == r_sgn:
            t_cy = wing_front + t_size * 0.5 - 0.25
            # The ramp's foot sits just behind the tower's stepped plinth so it
            # never pokes through the tower wall: you run through the tower gate
            # and straight up the ramp onto the walk.
            t_plinth = t_size * 0.5 + 0.45
            deck_y0 = (t_cy + t_plinth) + 0.10 + ramp_len
        else:
            deck_y0 = -3.0
        if has_turrets:
            # The corner towers sit on the back wall now, so the walk can run
            # all the way to the back corner.
            deck_y1 = base_hy + 0.45
        else:
            deck_y1 = deck_y0 + 7.0
        if deck_y1 - deck_y0 < 5.5:
            deck_y1 = deck_y0 + 5.5
        build_side_rampart(bm, side_sgn=r_sgn, wall_face_x=r_face,
                           deck_cy=(deck_y0 + deck_y1) * 0.5,
                           deck_len=deck_y1 - deck_y0,
                           deck_top_z=deck_top,
                           width=2.6, tier=tier, ramp_at_back=False)
    return annex_outer
