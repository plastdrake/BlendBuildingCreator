"""
Generic attached side annex.

A 1-2 storey half-timbered volume embedded into a main building's side wall, with
its own perpendicular cross-gable roof, cut-out windows, corner boards and an
upper oriel bay. Originally written for the Town Hall; now reusable by any
preset (town hall, taverns, inns, ...) via ``has_side_annex``.
"""

import math
import bmesh
from mathutils import Vector, Matrix

from ..mesh_utils import create_beveled_box
from ..walls import build_facade_timber, build_wall_with_opening
from ..openings import build_window_assembly
from ..roof.gable_roof import build_gable_roof
from ..style import tier_wall_mat
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_FLOOR,
)
from .mini_wing import build_mini_wing


def build_side_annex(bm, side_sgn, main_hx, main_cy0, main_cy1, z_ground=0.0,
                     found_h=0.6, floors=2, floor_h=3.0, tier='TIER_3',
                     width=5.2, depth=4.0, roof_h=3.0, plank_direction='HORIZONTAL',
                     main_bounds_by_floor=None, timber_framing=True, diagonals=True):
    """Half-timbered side volume embedded into the main side wall.

    side_sgn: +1 attaches on +X, -1 on -X. width runs along Y, depth along X.
    main_bounds_by_floor: {floor_idx: (x_min, x_max, y_min, y_max)} of the main
    hall so the annex tracks the jettied wall face on upper floors instead of
    poking into the main hall interior.
    Returns the outer face X for forecourt layout.
    """
    overlap = 0.6
    wmat_upper = tier_wall_mat(tier)
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
            outer_ops = [{'u_start': uc - win_w * 0.5 - 0.12, 'u_end': uc + win_w * 0.5 + 0.12,
                          'z_start': sill, 'z_end': sill + win_h}]
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                list(outer_ops),
                mat_ext=f_mat, normal_vec=out_normal, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
            build_window_assembly(
                bm, center=(outer_x, cy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=out_normal, has_shutters=True)
        else:
            oriel_w = min(2.2, width * 0.55)
            oriel_h = min(2.0, floor_h * 0.72)
            uc = width * 0.5
            _oz0 = fz0 + 0.10
            _oz1 = fz0 + oriel_h - 0.05
            outer_ops = [{'u_start': uc - oriel_w * 0.5 + 0.10, 'u_end': uc + oriel_w * 0.5 - 0.10,
                          'z_start': _oz0, 'z_end': _oz1}]
            build_wall_with_opening(
                bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                list(outer_ops),
                mat_ext=f_mat, normal_vec=out_normal, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42)
            # Timber jambs + lintel so the bay portal gets the same framed look
            # as the outcrop portals cut into the main hall walls. The liner is
            # centred on the wall and just a hair deeper than it, so it lines the
            # reveal top to bottom instead of poking out of the outer face.
            _jw, _lh = 0.16, 0.18
            _jd = wall_t + 0.02
            _wc = outer_wall_x
            _p_lo = y0 + uc - oriel_w * 0.5 + 0.10
            _p_hi = y0 + uc + oriel_w * 0.5 - 0.10
            for _py in (_p_lo - _jw * 0.5 + 0.05, _p_hi + _jw * 0.5 - 0.05):
                create_beveled_box(bm, size=(_jd, _jw, _oz1 - _oz0),
                                   location=(_wc, _py, (_oz0 + _oz1) * 0.5),
                                   mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
            create_beveled_box(bm,
                               size=(_jd, (_p_hi - _p_lo) + _jw * 2.0 - 0.10, _lh),
                               location=(_wc, (_p_lo + _p_hi) * 0.5, _oz1 + _lh * 0.5 - 0.02),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
        if timber_framing:
            build_facade_timber(bm, (outer_wall_x, y0), (outer_wall_x, y1), fz0, fz1, wall_t,
                                out_normal, list(outer_ops), diagonals,
                                is_top_floor=(f == floors - 1))
        # Front + back walls (run along X)
        ucx = abs(outer_x - inner_x) * 0.5
        for wy, nvec, shutters in ((front_wall_y, (0.0, -1.0), True),
                                   (back_wall_y, (0.0, 1.0), False)):
            _fb_ops = [{'u_start': ucx - win_w * 0.5 - 0.12, 'u_end': ucx + win_w * 0.5 + 0.12,
                        'z_start': sill, 'z_end': sill + win_h}]
            build_wall_with_opening(
                bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                list(_fb_ops),
                mat_ext=f_mat, normal_vec=nvec, tier=tier, physical_siding=True,
                plank_direction=plank_direction, seed=42,
                omit_top_log_row=(tier == 'TIER_1'))
            build_window_assembly(
                bm, center=(cxf, wy, sill + win_h * 0.5), size=(win_w, win_h),
                wall_thickness=wall_t, normal_axis=nvec, has_shutters=shutters)
            if timber_framing:
                build_facade_timber(bm, (inner_x, wy), (outer_x, wy), fz0, fz1, wall_t,
                                    nvec, list(_fb_ops), diagonals,
                                    is_top_floor=(f == floors - 1))
    top_inner = floor_inner[floors - 1]
    # Timber belt course between ground and upper lifts, built as a ring of
    # boards rather than one solid slab: it dresses the outside without filling
    # the annex room (the storey above already gives it a floor/ceiling).
    if floors >= 2 and tier != 'TIER_1':
        b_span = abs(outer_x - jetted_inner)
        b_cx = (jetted_inner + outer_x) * 0.5
        _bz = found_h + floor_h - 0.20
        _bh, _bt = 0.18, 0.14
        create_beveled_box(bm, size=(b_span + 0.14, _bt, _bh),
                           location=(b_cx, y0 - _bt * 0.5 + 0.06, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
        create_beveled_box(bm, size=(b_span + 0.14, _bt, _bh),
                           location=(b_cx, y1 + _bt * 0.5 - 0.06, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
        create_beveled_box(bm, size=(_bt, width + 0.14, _bh),
                           location=(outer_x + side_sgn * (_bt * 0.5 - 0.06), cy, _bz),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Corner boards on the outer corners (plain log annexes keep their log ends).
    if tier != 'TIER_1':
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
