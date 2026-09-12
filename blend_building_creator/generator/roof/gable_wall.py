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
    f_int.material_index = MAT_INDEX_PLASTER_INT

    uv_g = bm.loops.layers.uv.verify()
    for f in (f_ext, f_int):
        for loop in f.loops:
            co = loop.vert.co
            u = co.x * 0.55
            v = (co.z - z_base) * 0.55
            loop[uv_g].uv = Vector((u, v))

    # Top sloping boundary seals (under roof deck)
    for k in range(len(top_xs) - 1):
        if g_norm < 0:
            bm.faces.new([top_verts_ext[k], top_verts_ext[k+1], top_verts_int[k+1], top_verts_int[k]]).material_index = MAT_INDEX_TIMBER
        else:
            bm.faces.new([top_verts_int[k], top_verts_int[k+1], top_verts_ext[k+1], top_verts_ext[k]]).material_index = MAT_INDEX_TIMBER

    # Vertical side boundary seals (only if vertical jamb exists)
    if has_left_jamb:
        if g_norm < 0:
            bm.faces.new([v_ext_bl, top_verts_ext[0], top_verts_int[0], v_int_bl]).material_index = MAT_INDEX_TIMBER
        else:
            bm.faces.new([v_ext_bl, v_int_bl, top_verts_int[0], top_verts_ext[0]]).material_index = MAT_INDEX_TIMBER

    if has_right_jamb:
        if g_norm < 0:
            bm.faces.new([v_ext_br, v_int_br, top_verts_int[-1], top_verts_ext[-1]]).material_index = MAT_INDEX_TIMBER
        else:
            bm.faces.new([v_ext_br, top_verts_ext[-1], top_verts_int[-1], v_int_br]).material_index = MAT_INDEX_TIMBER

    # Bottom sealing face closing the bottom of the gable wall against attic floor
    if g_norm < 0:
        bm.faces.new([v_ext_bl, v_int_bl, v_int_br, v_ext_br]).material_index = MAT_INDEX_TIMBER
    else:
        bm.faces.new([v_int_bl, v_ext_bl, v_ext_br, v_int_br]).material_index = MAT_INDEX_TIMBER

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
