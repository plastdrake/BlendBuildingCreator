"""
Gable Wall and Infill Generator for Stylized Fantasy Roofs.
Handles both solid double-walled volumetric gable ends with accurate pitch contours,
and physical horizontal log siding (Tier 1).
Follows Single Responsibility and DRY principles.
"""

import math
from mathutils import Vector
from ..mesh_utils import create_beveled_box, create_horizontal_cylinder
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_WOOD, MAT_INDEX_LOG
)

def build_gable_physical_siding(bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
                               z_base, ez, rz, deck_thick, slope, tier='TIER_3', plank_direction='HORIZONTAL',
                               roof_flare=0.35, hatch=None):
    """
    Populates the triangular gable wall under the roof pitch with physical 3D
    horizontal rounded logs (Tier 1) sliced to match the sloping bell-cast rafters.
    Tier 2 and 3 use solid walls with rich tileable PBR shaders.
    """
    if tier != 'TIER_1':
        return

    half_w = max(0.01, (rx_max - rx_min) * 0.5)
    z_deck_top = rz - deck_thick - 0.02
    total_gable_h = z_deck_top - z_base
    if total_gable_h < 0.3:
        return

    def get_width_at_z(z_val):
        u_target = max(0.0, min(1.0, (rz - deck_thick - 0.02 - z_val) / max(0.01, rz - ez)))
        lo, hi = 0.0, 1.0
        for _ in range(6):
            mid = (lo + hi) * 0.5
            d_mid = (1.0 - roof_flare) * mid + roof_flare * (1.0 - (1.0 - mid) ** 2)
            if d_mid < u_target:
                lo = mid
            else:
                hi = mid
        u_exact = (lo + hi) * 0.5
        half_span = u_exact * half_w
        x_l = max(x_min, cx - half_span)
        x_r = min(x_max, cx + half_span)
        return x_l, x_r

    # Stacked physical rounded horizontal logs matching lower walls identically
    target_diam = 0.36
    log_h = target_diam
    wall_t = half_wt * 2.0
    log_ry = min(wall_t * 0.65, log_h * 0.56)
    log_rz = log_h * 0.49
    y_log_siding = gy + g_norm * (wall_t * 0.32)
    
    k_start = int(math.floor(z_base / log_h))
    k_end = int(math.ceil(z_deck_top / log_h))
    for k in range(k_start, k_end + 1):
        cur_z = (k + 0.5) * log_h
        if cur_z < z_base - 0.05:
            continue
        if cur_z >= z_deck_top - 0.05:
            break
        x_l, x_r = get_width_at_z(cur_z)
        _spans = [(x_l, x_r)]
        if hatch is not None:
            try:
                _shx0, _shx1 = float(hatch['x0']), float(hatch['x1'])
                _shz0, _shz1 = float(hatch['z0']), float(hatch['z1'])
            except Exception:
                _shx0 = None
            if _shx0 is not None and _shz0 <= cur_z <= _shz1:
                _spans = [(x_l, min(x_r, _shx0 - 0.03)), (max(x_l, _shx1 + 0.03), x_r)]
        for (_sx0, _sx1) in _spans:
            _sspan = _sx1 - _sx0
            if _sspan < 0.28:
                continue
            _smid = (_sx0 + _sx1) * 0.5
            uv_off = (k - k_start) * (_sspan * 0.12)
            create_horizontal_cylinder(
                bm,
                radius_y=log_ry,
                radius_z=log_rz,
                length=_sspan + 0.06,
                segments=16,
                location=(_smid, y_log_siding, cur_z),
                rotation=(0.0, 0.0, 0.0),
                mat_index=MAT_INDEX_LOG,
                smooth=True,
                uv_offset=uv_off
            )
        if x_r - x_l < 0.28:
            break


def build_gable_end_wall(bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
                         deck_thick, z_base, roof_height, roof_flare, tier, plank_direction,
                         get_gable_deck_z_func, ez, rz, slope=None, hatch=None):
    """
    Constructs a solid double-walled volumetric gable end wall matching the roof deck contour,
    with timber boundary trims and bargeboard fascia.
    Shared across both sway roofs and straight gable roofs (DRY).
    """
    y_ext = gy + g_norm * (half_wt + 0.005)
    y_int = gy - g_norm * half_wt

    # Find the exact span at z_base where the roof underside meets z_base
    half_w = max(0.01, (rx_max - rx_min) * 0.5)
    z_deck_top = rz - deck_thick - 0.02
    u_target = max(0.0, min(1.0, (z_deck_top - z_base) / max(0.01, rz - ez)))
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) * 0.5
        d_mid = (1.0 - roof_flare) * mid + roof_flare * (1.0 - (1.0 - mid) ** 2)
        if d_mid < u_target:
            lo = mid
        else:
            hi = mid
    u_exact = (lo + hi) * 0.5
    half_span = u_exact * half_w

    # Clamp base bounds so the gable wall never extends past the building walls
    # and never extends into the region where the roof deck is below z_base
    base_x_left = max(x_min, cx - half_span)
    base_x_right = min(x_max, cx + half_span)

    z_left = max(z_base, get_gable_deck_z_func(base_x_left))
    z_right = max(z_base, get_gable_deck_z_func(base_x_right))

    # Segmented top contour matching pitch
    n_segs = 6
    xs_left = [base_x_left + (cx - base_x_left) * (i / n_segs) for i in range(n_segs + 1)]
    xs_right = [cx + (base_x_right - cx) * (i / n_segs) for i in range(1, n_segs + 1)]
    top_xs = xs_left + xs_right

    top_verts_ext = [bm.verts.new(Vector((tx, y_ext, max(z_base, get_gable_deck_z_func(tx))))) for tx in top_xs]
    top_verts_int = [bm.verts.new(Vector((tx, y_int, max(z_base, get_gable_deck_z_func(tx))))) for tx in top_xs]

    has_left_jamb = (z_left > z_base + 0.005)
    has_right_jamb = (z_right > z_base + 0.005)

    if has_left_jamb:
        v_ext_bl = bm.verts.new(Vector((base_x_left, y_ext, z_base)))
        v_int_bl = bm.verts.new(Vector((base_x_left, y_int, z_base)))
    else:
        v_ext_bl = top_verts_ext[0]
        v_int_bl = top_verts_int[0]

    if has_right_jamb:
        v_ext_br = bm.verts.new(Vector((base_x_right, y_ext, z_base)))
        v_int_br = bm.verts.new(Vector((base_x_right, y_int, z_base)))
    else:
        v_ext_br = top_verts_ext[-1]
        v_int_br = top_verts_int[-1]

    if tier in ('TIER_1', 'TIER_2'):
        gable_mat = MAT_INDEX_WOOD
    else:
        gable_mat = MAT_INDEX_PLASTER_EXT

    uv_g = bm.loops.layers.uv.verify()

    def _uv_wall(f):
        for loop in f.loops:
            co = loop.vert.co
            loop[uv_g].uv = Vector((co.x * 0.55, (co.z - z_base) * 0.55))

    # Optional loft hatch opening (validated against the real wall bounds,
    # edges snapped to the seal contour samples so no duplicate verts exist).
    _hx0 = None
    if hatch:
        try:
            _hx0 = max(float(hatch['x0']), base_x_left + 0.12)
            _hx1 = min(float(hatch['x1']), base_x_right - 0.12)
            _hz0 = max(float(hatch['z0']), z_base + 0.12)
            _hz1 = float(hatch['z1'])
            _hcx = (_hx0 + _hx1) * 0.5
            _hz1 = min(_hz1, get_gable_deck_z_func(_hcx) - 0.22)
            for _sx in top_xs:
                if abs(_sx - _hx0) < 0.02:
                    _hx0 = _sx
                if abs(_sx - _hx1) < 0.02:
                    _hx1 = _sx
            _hcx = (_hx0 + _hx1) * 0.5
        except Exception:
            _hx0 = None
        if _hx0 is None or _hx1 - _hx0 < 0.50 or _hz1 - _hz0 < 0.60:
            _hx0 = None

    def _mkface(pts_ext, pts_int):
        if g_norm < 0:
            fe = bm.faces.new(pts_ext)
            fi = bm.faces.new(pts_int)
        else:
            fe = bm.faces.new(list(reversed(pts_ext)))
            fi = bm.faces.new(list(reversed(pts_int)))
        fe.material_index = gable_mat
        # Interior gable face follows the same tier as the exterior (planks for
        # Tier 1-2, plaster for Tier 3) so log/plank halls do not show stucco inside.
        fi.material_index = gable_mat
        _uv_wall(fe)
        _uv_wall(fi)

    if _hx0 is None:
        # Construct clean, non-self-intersecting exterior & interior faces
        ext_loop = [v_ext_bl, v_ext_br]
        if has_right_jamb:
            ext_loop.append(top_verts_ext[-1])
        ext_loop.extend(reversed(top_verts_ext[1:-1]))
        if has_left_jamb:
            ext_loop.append(top_verts_ext[0])

        int_loop = [v_int_bl]
        if has_left_jamb:
            int_loop.append(top_verts_int[0])
        int_loop.extend(top_verts_int[1:-1])
        if has_right_jamb:
            int_loop.append(top_verts_int[-1])
        int_loop.append(v_int_br)

        if g_norm < 0:
            f_ext = bm.faces.new(ext_loop)
            f_int = bm.faces.new(int_loop)
        else:
            f_ext = bm.faces.new(list(reversed(ext_loop)))
            f_int = bm.faces.new(list(reversed(int_loop)))

        f_ext.material_index = gable_mat
        f_int.material_index = gable_mat
        _uv_wall(f_ext)
        _uv_wall(f_int)
    else:
        def _deck(x):
            return max(z_base, get_gable_deck_z_func(x))

        if _hx0 > base_x_left + 0.03:
            _le_xv = [(x, v) for x, v in zip(top_xs, top_verts_ext) if x <= _hx0 + 1e-6]
            _li_xv = [(x, v) for x, v in zip(top_xs, top_verts_int) if x <= _hx0 + 1e-6]
            if not _le_xv or abs(_le_xv[-1][0] - _hx0) > 1e-6:
                _le_xv.append((_hx0, bm.verts.new(Vector((_hx0, y_ext, _deck(_hx0))))))
                _li_xv.append((_hx0, bm.verts.new(Vector((_hx0, y_int, _deck(_hx0))))))
            _le = [v for _, v in _le_xv]
            _li = [v for _, v in _li_xv]
            _bl_e = bm.verts.new(Vector((base_x_left, y_ext, z_base)))
            _bl_i = bm.verts.new(Vector((base_x_left, y_int, z_base)))
            _br_e = bm.verts.new(Vector((_hx0, y_ext, z_base)))
            _br_i = bm.verts.new(Vector((_hx0, y_int, z_base)))
            _mkface([_bl_e, _br_e] + list(reversed(_le)),
                    [_bl_i] + _li + [_br_i])
        if _hx1 < base_x_right - 0.03:
            _re_xv = [(x, v) for x, v in zip(top_xs, top_verts_ext) if x >= _hx1 - 1e-6]
            _ri_xv = [(x, v) for x, v in zip(top_xs, top_verts_int) if x >= _hx1 - 1e-6]
            if not _re_xv or abs(_re_xv[0][0] - _hx1) > 1e-6:
                _re_xv.insert(0, (_hx1, bm.verts.new(Vector((_hx1, y_ext, _deck(_hx1))))))
                _ri_xv.insert(0, (_hx1, bm.verts.new(Vector((_hx1, y_int, _deck(_hx1))))))
            _re = [v for _, v in _re_xv]
            _ri = [v for _, v in _ri_xv]
            _bl_e = bm.verts.new(Vector((_hx1, y_ext, z_base)))
            _bl_i = bm.verts.new(Vector((_hx1, y_int, z_base)))
            _br_e = bm.verts.new(Vector((base_x_right, y_ext, z_base)))
            _br_i = bm.verts.new(Vector((base_x_right, y_int, z_base)))
            _mkface([_bl_e, _br_e] + list(reversed(_re)),
                    [_bl_i] + _ri + [_br_i])
        if _hz0 > z_base + 0.03:
            _e0 = bm.verts.new(Vector((_hx0, y_ext, z_base)))
            _e1 = bm.verts.new(Vector((_hx1, y_ext, z_base)))
            _e2 = bm.verts.new(Vector((_hx1, y_ext, _hz0)))
            _e3 = bm.verts.new(Vector((_hx0, y_ext, _hz0)))
            _i0 = bm.verts.new(Vector((_hx0, y_int, z_base)))
            _i1 = bm.verts.new(Vector((_hx1, y_int, z_base)))
            _i2 = bm.verts.new(Vector((_hx1, y_int, _hz0)))
            _i3 = bm.verts.new(Vector((_hx0, y_int, _hz0)))
            _mkface([_e0, _e1, _e2, _e3], [_i0, _i3, _i2, _i1])
        _te_xv = [(x, v) for x, v in zip(top_xs, top_verts_ext) if _hx0 - 1e-6 <= x <= _hx1 + 1e-6]
        _ti_xv = [(x, v) for x, v in zip(top_xs, top_verts_int) if _hx0 - 1e-6 <= x <= _hx1 + 1e-6]
        if not _te_xv or abs(_te_xv[0][0] - _hx0) > 1e-6:
            _te_xv.insert(0, (_hx0, bm.verts.new(Vector((_hx0, y_ext, _deck(_hx0))))))
            _ti_xv.insert(0, (_hx0, bm.verts.new(Vector((_hx0, y_int, _deck(_hx0))))))
        if abs(_te_xv[-1][0] - _hx1) > 1e-6:
            _te_xv.append((_hx1, bm.verts.new(Vector((_hx1, y_ext, _deck(_hx1))))))
            _ti_xv.append((_hx1, bm.verts.new(Vector((_hx1, y_int, _deck(_hx1))))))
        _te = [v for _, v in _te_xv]
        _ti = [v for _, v in _ti_xv]
        _b0e = bm.verts.new(Vector((_hx0, y_ext, _hz1)))
        _b1e = bm.verts.new(Vector((_hx1, y_ext, _hz1)))
        _b0i = bm.verts.new(Vector((_hx0, y_int, _hz1)))
        _b1i = bm.verts.new(Vector((_hx1, y_int, _hz1)))
        _mkface([_b0e, _b1e] + list(reversed(_te)),
                [_b0i] + _ti + [_b1i])
        _core = abs(y_ext - y_int) + 0.06
        _yc = (y_ext + y_int) * 0.5
        _midz = (_hz0 + _hz1) * 0.5
        _hh = _hz1 - _hz0
        create_beveled_box(bm, size=(0.10, _core, _hh), location=(_hx0, _yc, _midz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        create_beveled_box(bm, size=(0.10, _core, _hh), location=(_hx1, _yc, _midz), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        create_beveled_box(bm, size=(_hx1 - _hx0 + 0.10, _core, 0.10), location=(_hcx, _yc, _hz1), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        create_beveled_box(bm, size=(_hx1 - _hx0 + 0.10, _core, 0.10), location=(_hcx, _yc, _hz0), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Top sloping boundary seals (under roof deck)
    seal_faces = []
    for k in range(len(top_xs) - 1):
        if g_norm < 0:
            f = bm.faces.new([top_verts_ext[k], top_verts_ext[k+1], top_verts_int[k+1], top_verts_int[k]])
        else:
            f = bm.faces.new([top_verts_int[k], top_verts_int[k+1], top_verts_ext[k+1], top_verts_ext[k]])
        f.material_index = MAT_INDEX_TIMBER
        seal_faces.append(f)

    # Vertical side boundary seals (only if vertical jamb exists)
    if has_left_jamb:
        if g_norm < 0:
            f = bm.faces.new([v_ext_bl, top_verts_ext[0], top_verts_int[0], v_int_bl])
        else:
            f = bm.faces.new([v_ext_bl, v_int_bl, top_verts_int[0], top_verts_ext[0]])
        f.material_index = MAT_INDEX_TIMBER
        seal_faces.append(f)

    if has_right_jamb:
        if g_norm < 0:
            f = bm.faces.new([v_ext_br, v_int_br, top_verts_int[-1], top_verts_ext[-1]])
        else:
            f = bm.faces.new([v_ext_br, top_verts_ext[-1], top_verts_int[-1], v_int_br])
        f.material_index = MAT_INDEX_TIMBER
        seal_faces.append(f)

    # Bottom sealing face closing the bottom of the gable wall against attic floor
    if g_norm < 0:
        f = bm.faces.new([v_ext_bl, v_int_bl, v_int_br, v_ext_br])
    else:
        f = bm.faces.new([v_int_bl, v_ext_bl, v_ext_br, v_int_br])
    f.material_index = MAT_INDEX_TIMBER
    seal_faces.append(f)

    for sf in seal_faces:
        for loop in sf.loops:
            co = loop.vert.co
            s_dist = math.sqrt((co.x - cx) ** 2 + (rz - co.z) ** 2)
            loop[uv_g].uv = Vector(((co.y - gy) * 0.45, s_dist * 0.40))

    # Half-timber tie beam and king post for non-log tiers
    if tier != 'TIER_1':
        # Horizontal tie beam across gable base
        tie_t = half_wt * 2.0 + 0.08
        tie_h = 0.18
        tie_y = gy + g_norm * (half_wt * 0.10)
        tie_span = max(0.2, min((x_max - x_min) - 0.08, (base_x_right - base_x_left) - 0.04))
        create_beveled_box(
            bm,
            size=(tie_span, tie_t, tie_h),
            location=(cx, tie_y, z_base + tie_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012
        )

        # Vertical king post from tie beam up to apex (shifted clear of loft hatch)
        king_w = 0.16
        king_t = tie_t
        king_x = cx
        if _hx0 is not None and abs(cx - _hcx) < 0.80:
            _kx = _hx1 + 0.30
            if _kx + 0.15 > base_x_right:
                _kx = _hx0 - 0.30
            king_x = max(base_x_left + 0.15, min(base_x_right - 0.15, _kx))
        king_top = get_gable_deck_z_func(king_x)
        king_bot = z_base + tie_h
        king_h = max(0.2, king_top - king_bot)
        create_beveled_box(
            bm,
            size=(king_w, king_t, king_h),
            location=(king_x, tie_y, king_bot + king_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.010
        )

    # Physical logs siding for Tier 1 (split around a validated hatch opening)
    _siding_hatch = None
    if _hx0 is not None:
        _siding_hatch = {'x0': _hx0, 'x1': _hx1, 'z0': _hz0, 'z1': _hz1}
    build_gable_physical_siding(
        bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
        z_base, ez, rz, deck_thick, slope, tier=tier,
        plank_direction=plank_direction, roof_flare=roof_flare, hatch=_siding_hatch
    )
