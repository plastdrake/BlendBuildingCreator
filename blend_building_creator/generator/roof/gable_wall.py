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
                               roof_flare=0.35):
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
        span = x_r - x_l
        if span < 0.28:
            break
        mid_x = (x_l + x_r) * 0.5
        uv_off = (k - k_start) * (span * 0.12)
        create_horizontal_cylinder(
            bm,
            radius_y=log_ry,
            radius_z=log_rz,
            length=span + 0.06,
            segments=16,
            location=(mid_x, y_log_siding, cur_z),
            rotation=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_LOG,
            smooth=True,
            uv_offset=uv_off
        )


def build_gable_end_wall(bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
                         deck_thick, z_base, roof_height, roof_flare, tier, plank_direction,
                         get_gable_deck_z_func, ez, rz, slope=None):
    """
    Constructs a solid double-walled volumetric gable end wall matching the roof deck contour,
    with timber boundary trims and bargeboard fascia.
    Shared across both sway roofs and straight gable roofs (DRY).
    """
    y_ext = gy + g_norm * (half_wt + 0.005)
    y_int = gy - g_norm * half_wt

    # Segmented top contour matching pitch
    n_segs = 6
    xs_left = [x_min + (cx - x_min) * (i / n_segs) for i in range(n_segs + 1)]
    xs_right = [cx + (x_max - cx) * (i / n_segs) for i in range(1, n_segs + 1)]
    top_xs = xs_left + xs_right

    top_verts_ext = [bm.verts.new(Vector((tx, y_ext, get_gable_deck_z_func(tx)))) for tx in top_xs]
    v_ext_bl = bm.verts.new(Vector((x_min, y_ext, z_base)))
    v_ext_br = bm.verts.new(Vector((x_max, y_ext, z_base)))

    top_verts_int = [bm.verts.new(Vector((tx, y_int, get_gable_deck_z_func(tx)))) for tx in top_xs]
    v_int_bl = bm.verts.new(Vector((x_min, y_int, z_base)))
    v_int_br = bm.verts.new(Vector((x_max, y_int, z_base)))

    if tier == 'TIER_2':
        gable_mat = MAT_INDEX_WOOD
    elif tier == 'TIER_1':
        gable_mat = MAT_INDEX_TIMBER
    else:
        gable_mat = MAT_INDEX_PLASTER_EXT

    if g_norm < 0:
        f_ext = bm.faces.new([v_ext_bl, v_ext_br] + list(reversed(top_verts_ext)))
        f_ext.material_index = gable_mat
        f_int = bm.faces.new(list(top_verts_int) + [v_int_br, v_int_bl])
        f_int.material_index = MAT_INDEX_PLASTER_INT
    else:
        f_ext = bm.faces.new(list(top_verts_ext) + [v_ext_br, v_ext_bl])
        f_ext.material_index = gable_mat
        f_int = bm.faces.new([v_int_bl, v_int_br] + list(reversed(top_verts_int)))
        f_int.material_index = MAT_INDEX_PLASTER_INT

    uv_g = bm.loops.layers.uv.verify()
    for f in (f_ext, f_int):
        for loop in f.loops:
            co = loop.vert.co
            if plank_direction == 'VERTICAL':
                u = co.z * 0.65
                v = co.x * 0.65
            else:
                u = co.x * 0.65
                v = co.z * 0.65
            loop[uv_g].uv = Vector((u, v))

    # Top sloping boundary seals (under roof deck)
    for k in range(len(top_xs) - 1):
        if g_norm < 0:
            bm.faces.new([top_verts_ext[k], top_verts_ext[k+1], top_verts_int[k+1], top_verts_int[k]]).material_index = MAT_INDEX_TIMBER
        else:
            bm.faces.new([top_verts_ext[k+1], top_verts_ext[k], top_verts_int[k], top_verts_int[k+1]]).material_index = MAT_INDEX_TIMBER

    # Vertical side boundary seals at x_min and x_max
    if g_norm < 0:
        bm.faces.new([v_ext_bl, top_verts_ext[0], top_verts_int[0], v_int_bl]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_br, v_int_br, top_verts_int[-1], top_verts_ext[-1]]).material_index = MAT_INDEX_TIMBER
    else:
        bm.faces.new([v_ext_bl, v_int_bl, top_verts_int[0], top_verts_ext[0]]).material_index = MAT_INDEX_TIMBER
        bm.faces.new([v_ext_br, top_verts_ext[-1], top_verts_int[-1], v_int_br]).material_index = MAT_INDEX_TIMBER

    # Side eave triangular filling wedges
    for is_right, side_x, sign_side in [(False, x_min, -1.0), (True, x_max, 1.0)]:
        z_eave = get_gable_deck_z_func(side_x)
        if z_eave > z_base + 0.05:
            eave_overhang_x = (rx_max - x_max) if is_right else (x_min - rx_min)
            sx_eave = side_x + sign_side * eave_overhang_x
            v_s_wall_ext = bm.verts.new(Vector((side_x, y_ext, z_base)))
            v_s_wall_int = bm.verts.new(Vector((side_x, y_int, z_base)))
            v_s_top_ext = bm.verts.new(Vector((side_x, y_ext, z_eave)))
            v_s_top_int = bm.verts.new(Vector((side_x, y_int, z_eave)))
            v_s_eave_ext = bm.verts.new(Vector((sx_eave, y_ext, z_base)))
            v_s_eave_int = bm.verts.new(Vector((sx_eave, y_int, z_base)))
            if g_norm < 0:
                bm.faces.new([v_s_eave_ext, v_s_wall_ext, v_s_top_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_top_int, v_s_wall_int, v_s_eave_int]).material_index = MAT_INDEX_TIMBER
            else:
                bm.faces.new([v_s_top_ext, v_s_wall_ext, v_s_eave_ext]).material_index = MAT_INDEX_TIMBER
                bm.faces.new([v_s_eave_int, v_s_wall_int, v_s_top_int]).material_index = MAT_INDEX_TIMBER
            bm.faces.new([v_s_eave_ext, v_s_eave_int, v_s_wall_int, v_s_wall_ext]).material_index = MAT_INDEX_TIMBER

    # Horizontal tie beam across gable base
    tie_t = half_wt * 2.0 + 0.08
    tie_h = 0.18
    tie_y = gy + g_norm * (half_wt * 0.10)
    create_beveled_box(
        bm,
        size=(x_max - x_min + 0.12, tie_t, tie_h),
        location=(cx, tie_y, z_base + tie_h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )

    # Vertical king post from tie beam up to apex
    king_w = 0.16
    king_t = tie_t
    king_top = get_gable_deck_z_func(cx)
    king_bot = z_base + tie_h
    king_h = max(0.2, king_top - king_bot)
    create_beveled_box(
        bm,
        size=(king_w, king_t, king_h),
        location=(cx, tie_y, king_bot + king_h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.010
    )

    # Physical logs siding for Tier 1
    build_gable_physical_siding(
        bm, cx, x_min, x_max, rx_min, rx_max, gy, g_norm, half_wt,
        z_base, ez, rz, deck_thick, slope, tier=tier,
        plank_direction=plank_direction, roof_flare=roof_flare
    )
