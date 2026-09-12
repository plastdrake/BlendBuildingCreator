"""
Bell-Cast Flared Dormer Window Generator for Stylized Fantasy Roofs.
Follows Single Responsibility and GRASP principles.
"""

import math
from mathutils import Vector, Euler
from ..mesh_utils import create_box, create_beveled_box
from ..materials import (
    MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER, MAT_INDEX_GLASS,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD
)

def build_dormer(bm, center_pos=None, z_base=0.0, facing_dir=(-1, 0), dormer_w=1.2, dormer_d=1.4, dormer_h=1.05,
                 dormer_roof_h=0.65, roof_flare=0.35, tier='TIER_3', max_back_reach=None,
                 center_x=None, center_y=None, roof_style='SWAY', sway_amount=0.0, **kwargs):
    """
    Builds an authentic stylized fantasy flared dormer window:
    - Curved bell-cast flared roof deck with layered stylized shingles and timber soffit underside.
    - Curved verge bargeboards sweeping along the flared eaves.
    - Stylized vertical timber apex finial cap block.
    - Front timber framing: thick corner posts penetrating deep into attic, collar tie beam, king post.
    - Clean vertical wood plank apron below window flush with framing (no dividing sill bar).
    - Vertical wood plank cheek walls penetrating cleanly into main roof.
    """
    if center_x is not None and center_y is not None:
        center_pos = (center_x, center_y)
    elif center_pos is None:
        center_pos = (0.0, 0.0)

    fx, fy = facing_dir
    f_len = math.sqrt(fx * fx + fy * fy)
    if f_len > 1e-4:
        fx /= f_len
        fy /= f_len
    else:
        fx, fy = -1.0, 0.0
    sx, sy = -fy, fx
    
    cx, cy = center_pos
    half_dw = dormer_w * 0.5
    half_dd = dormer_d * 0.5
    rot_z = math.atan2(fy, fx)
    
    col_w = 0.18
    uv_layer = bm.loops.layers.uv.verify()
    dormer_wall_mat = MAT_INDEX_PLASTER_EXT if tier == 'TIER_3' else MAT_INDEX_WOOD

    # Local-to-world helper
    def to_w(x_f, y_s, z_val):
        return Vector((cx + fx * x_f + sx * y_s, cy + fy * x_f + sy * y_s, z_val))

    # Overhang and reach geometry (tight eaves: barges hug the cheeks,
    # roof front sits close over the corner posts instead of floating past them)
    d_overhang = 0.16
    front_reach = half_dd + 0.12
    back_reach = max_back_reach if max_back_reach is not None else (half_dd + 1.20)
    roof_len = front_reach + back_reach
    roof_mid_xf = (front_reach - back_reach) * 0.5

    # 1. Cheek Walls (Vertical Wood Planks) - extend deep into attic to eliminate gaps,
    # tops tucked below the roof deck underside so corners never poke through slopes
    cheek_len = half_dd + back_reach
    cheek_mid_xf = (half_dd - back_reach) * 0.5
    cheek_bot_z = z_base - 0.85
    cheek_top_z = z_base + dormer_h + 0.02
    cheek_h = cheek_top_z - cheek_bot_z
    cheek_mid_z = (cheek_top_z + cheek_bot_z) * 0.5
    for s_sign in [-1, 1]:
        ch_pos = to_w(cheek_mid_xf, s_sign * (half_dw - col_w * 0.5 - 0.02), cheek_mid_z)
        ch_faces = create_beveled_box(
            bm,
            size=(cheek_len, 0.07, cheek_h),
            location=ch_pos,
            rotation=(0.0, 0.0, rot_z),
            mat_index=dormer_wall_mat,
            bevel_amount=0.010
        )
        for f in ch_faces:
            if f.is_valid:
                for loop in f.loops:
                    co = loop.vert.co
                    u = (co.x * fx + co.y * fy) * 0.75
                    v = (co.z - z_base) * 0.75
                    loop[uv_layer].uv = Vector((u, v))

    # 1b. Rear Closing Wall (Attic Seal)
    rear_wall_w = dormer_w - col_w * 0.5
    rear_wall_h = max(0.40, dormer_h * 0.65)
    rear_pos = to_w(-back_reach + 0.04, 0.0, z_base + rear_wall_h * 0.5)
    rear_faces = create_beveled_box(
        bm,
        size=(col_w + 0.04, rear_wall_w, rear_wall_h),
        location=rear_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=dormer_wall_mat,
        bevel_amount=0.010
    )
    for f in rear_faces:
        if f.is_valid:
            for loop in f.loops:
                co = loop.vert.co
                u = (co.x * sx + co.y * sy) * 0.75
                v = (co.z - z_base) * 0.75
                loop[uv_layer].uv = Vector((u, v))

    # 2. Front Timber Framing (collar tucked under the deck; post tops die into
    # the collar instead of poking through the slopes)
    front_xf = half_dd - col_w * 0.5
    collar_z = z_base + dormer_h - 0.02
    post_bot_z = z_base - 0.85
    post_top_z = collar_z - 0.02
    post_h = post_top_z - post_bot_z
    
    # Corner posts: 0.18m thick, extend down into attic, project slightly outward to eliminate coplanar fights
    for s_sign in [-1, 1]:
        p_pos = to_w(front_xf + 0.015, s_sign * (half_dw - col_w * 0.5 + 0.01), (post_top_z + post_bot_z) * 0.5)
        create_beveled_box(
            bm,
            size=(col_w, col_w, post_h),
            location=p_pos,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.014
        )

    # Horizontal Collar Tie Beam across dormer front at eave level (ends die
    # into the corner posts instead of piercing the roof slopes)
    collar_pos = to_w(front_xf, 0.0, collar_z)
    create_beveled_box(
        bm,
        size=(col_w + 0.02, dormer_w - col_w, 0.12),
        location=collar_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.010
    )

    # 3. Front Window & Flush Vertical Siding (Apron)
    clear_w = dormer_w - col_w * 2.0
    win_w = max(0.48, clear_w - 0.04)
    win_h = max(0.38, dormer_h * 0.44)
    win_top_z = collar_z - 0.06
    win_bot_z = win_top_z - win_h
    win_cz = (win_top_z + win_bot_z) * 0.5

    # Window Perimeter Timber Casing (full rectangular frame: chunky jambs lapping
    # past the sill into the apron, with top and bottom rails between them)
    casing_w = 0.09
    casing_t = col_w + 0.02

    # Left and Right Casing Jambs: full height, lapping below the sill line
    j_bot = win_bot_z - casing_w
    j_top = win_top_z + casing_w
    j_h = j_top - j_bot
    j_cz = (j_top + j_bot) * 0.5
    for s_sign in [-1, 1]:
        j_pos = to_w(front_xf, s_sign * (win_w * 0.5 + casing_w * 0.5), j_cz)
        create_beveled_box(
            bm,
            size=(casing_t, casing_w, j_h),
            location=j_pos,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
    # Top Casing Rail
    r_pos = to_w(front_xf, 0.0, win_top_z + casing_w * 0.5)
    create_beveled_box(
        bm,
        size=(casing_t, win_w, casing_w),
        location=r_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    # Bottom Sill Rail (was missing: glass used to sit straight on the apron)
    b_pos = to_w(front_xf + 0.01, 0.0, win_bot_z - casing_w * 0.5)
    create_beveled_box(
        bm,
        size=(casing_t + 0.02, win_w + 0.04, casing_w),
        location=b_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )

    # Window Glass Pane
    create_box(
        bm,
        size=(0.04, win_w - 0.02, win_h - 0.02),
        location=to_w(front_xf, 0.0, win_cz),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_GLASS
    )
    # 4-Pane Muntins (2x2 Grid)
    create_box(
        bm,
        size=(0.055, 0.032, win_h - 0.02),
        location=to_w(front_xf, 0.0, win_cz),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )
    create_box(
        bm,
        size=(0.055, win_w - 0.02, 0.032),
        location=to_w(front_xf, 0.0, win_cz),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )

    # Solid Flush Vertical Board Apron below Window (extends into attic, uninterrupted by extra sills)
    apron_top_z = win_bot_z
    apron_bot_z = z_base - 0.85
    apron_h = apron_top_z - apron_bot_z
    apron_pos = to_w(front_xf - 0.02, 0.0, apron_bot_z + apron_h * 0.5)
    apron_faces = create_beveled_box(
        bm,
        size=(col_w - 0.04, clear_w + 0.02, apron_h),
        location=apron_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=dormer_wall_mat,
        bevel_amount=0.008
    )
    for f in apron_faces:
        if f.is_valid:
            for loop in f.loops:
                co = loop.vert.co
                u = (co.x * sx + co.y * sy) * 0.75
                v = (co.z - z_base) * 0.75
                loop[uv_layer].uv = Vector((u, v))

    # 4. Triangular Gable Wall & King Post above Collar Beam
    d_roof_h = max(0.52, dormer_roof_h)
    d_rz = z_base + dormer_h + d_roof_h
    d_ez = z_base + dormer_h - 0.04
    
    # Vertical King Post Beam in Gable Triangle (top stopped well below the deck
    # underside so it never pierces the roof surface at the ridge)
    king_top_z = d_rz - 0.14
    king_bot_z = collar_z + 0.06
    king_h = max(0.15, king_top_z - king_bot_z)
    king_pos = to_w(front_xf, 0.0, king_bot_z + king_h * 0.5)
    create_beveled_box(
        bm,
        size=(0.09, 0.11, king_h),
        location=king_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    
    # Vertical Plank Siding filling triangular gable (apex tucked below the deck
    # underside so the gable never pokes through the roof slopes)
    tri_thick = 0.08
    v_top_f = to_w(front_xf, 0.0, d_rz - 0.10)
    v_left_f = to_w(front_xf, -(half_dw - 0.02), collar_z + 0.06)
    v_right_f = to_w(front_xf, (half_dw - 0.02), collar_z + 0.06)
    v_top_b = to_w(front_xf - tri_thick, 0.0, d_rz - 0.10)
    v_left_b = to_w(front_xf - tri_thick, -(half_dw - 0.02), collar_z + 0.06)
    v_right_b = to_w(front_xf - tri_thick, (half_dw - 0.02), collar_z + 0.06)
    
    vt_f = bm.verts.new(v_top_f)
    vl_f = bm.verts.new(v_left_f)
    vr_f = bm.verts.new(v_right_f)
    vt_b = bm.verts.new(v_top_b)
    vl_b = bm.verts.new(v_left_b)
    vr_b = bm.verts.new(v_right_b)
    
    f_gf = bm.faces.new([vt_f, vl_f, vr_f])
    f_gf.material_index = dormer_wall_mat
    f_gb = bm.faces.new([vr_b, vl_b, vt_b])
    f_gb.material_index = MAT_INDEX_TIMBER
    f_top_edge = bm.faces.new([vt_f, vt_b, vl_b, vl_f])
    f_right_edge = bm.faces.new([vr_f, vr_b, vt_b, vt_f])
    f_bot_edge = bm.faces.new([vl_f, vl_b, vr_b, vr_f])
    for f_timber in [f_gb, f_top_edge, f_right_edge, f_bot_edge]:
        f_timber.material_index = MAT_INDEX_TIMBER
        for loop in f_timber.loops:
            co = loop.vert.co
            loop[uv_layer].uv = Vector(((co.x * sx + co.y * sy) * 0.75, (co.z - z_base) * 0.75))
    for loop in f_gf.loops:
        co = loop.vert.co
        u = (co.x * sx + co.y * sy) * 0.75
        v = (co.z - z_base) * 0.75
        loop[uv_layer].uv = Vector((u, v))

    # 5. Interior Floor Deck (Kept fully inside dormer interior behind front apron)
    floor_front_xf = front_xf - col_w * 0.5 - 0.04
    floor_back_xf = -back_reach + 0.10
    floor_deck_l = max(0.2, floor_front_xf - floor_back_xf)
    floor_mid_xf = (floor_front_xf + floor_back_xf) * 0.5
    floor_pos = to_w(floor_mid_xf, 0.0, z_base + 0.04)
    create_beveled_box(
        bm,
        size=(floor_deck_l, max(0.2, dormer_w - col_w * 2.0 - 0.04), 0.08),
        location=floor_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )

    # 6. Bell-Cast Curved Roof Deck
    n_slope = 4
    n_len = 4
    roof_half_w = half_dw + d_overhang
    deck_thick = 0.08
    uv_layer_d = bm.loops.layers.uv.verify()

    def get_flare_z(u_val):
        d_val = (1.0 - roof_flare) * u_val + roof_flare * (1.0 - (1.0 - u_val) ** 2)
        return d_rz - d_val * (d_rz - d_ez)

    dormer_slope_len = math.sqrt(roof_half_w ** 2 + (d_rz - d_ez) ** 2)

    for side_sign in [-1, 1]:
        grid_top = []
        grid_bot = []

        for k in range(n_slope + 1):
            u_k = k / n_slope
            y_s = side_sign * u_k * roof_half_w
            z_surf = get_flare_z(u_k)

            eps = 1e-4
            u_plus = min(1.0, u_k + eps)
            u_minus = max(0.0, u_k - eps)
            dy_du = side_sign * roof_half_w
            dz_du = (get_flare_z(u_plus) - get_flare_z(u_minus)) / (u_plus - u_minus)
            n_len_2d = math.sqrt(dy_du * dy_du + dz_du * dz_du)
            if n_len_2d > 1e-5:
                in_ys = (dz_du / n_len_2d) * side_sign * deck_thick
                in_z = (-abs(dy_du) / n_len_2d) * deck_thick
            else:
                in_ys = 0.0
                in_z = -deck_thick

            row_top = []
            row_bot = []
            for j in range(n_len + 1):
                t_j = j / n_len
                x_f = front_reach - t_j * roof_len
                v_top = bm.verts.new(to_w(x_f, y_s, z_surf))
                v_bot = bm.verts.new(to_w(x_f, y_s + in_ys, z_surf + in_z))
                row_top.append(v_top)
                row_bot.append(v_bot)
            grid_top.append(row_top)
            grid_bot.append(row_bot)

        # Quads for top (shingles) and bottom (timber soffit)
        for k in range(n_slope):
            for j in range(n_len):
                vt00 = grid_top[k][j]
                vt01 = grid_top[k][j+1]
                vt10 = grid_top[k+1][j]
                vt11 = grid_top[k+1][j+1]

                vb00 = grid_bot[k][j]
                vb01 = grid_bot[k][j+1]
                vb10 = grid_bot[k+1][j]
                vb11 = grid_bot[k+1][j+1]

                if side_sign > 0:
                    f_top = bm.faces.new([vt00, vt10, vt11, vt01])
                    f_bot = bm.faces.new([vb01, vb11, vb10, vb00])
                    loop_k_j = [(k, j), (k+1, j), (k+1, j+1), (k, j+1)]
                else:
                    f_top = bm.faces.new([vt00, vt01, vt11, vt10])
                    f_bot = bm.faces.new([vb10, vb11, vb01, vb00])
                    loop_k_j = [(k, j), (k, j+1), (k+1, j+1), (k+1, j)]

                f_top.material_index = MAT_INDEX_SHINGLES
                f_bot.material_index = MAT_INDEX_TIMBER

                # Clean Parametric Shingles UV:
                # U along ridge (front to back), V down slope (ridge to eave)
                # Exactly aligned with roof scallops pointing downwards, zero world-coordinate distortion!
                for l_idx, loop in enumerate(f_top.loops):
                    lk, lj = loop_k_j[l_idx]
                    u_uv = (lj / float(n_len)) * roof_len * 0.32
                    v_uv = -(lk / float(n_slope)) * dormer_slope_len * 0.32
                    loop[uv_layer_d].uv = Vector((u_uv, v_uv))
                for l_idx, loop in enumerate(f_bot.loops):
                    lk, lj = loop_k_j[l_idx]
                    u_uv = (lj / float(n_len)) * roof_len * 0.32
                    v_uv = -(lk / float(n_slope)) * dormer_slope_len * 0.32
                    loop[uv_layer_d].uv = Vector((u_uv, v_uv))

        # Front verge edge closure
        for k in range(n_slope):
            if side_sign > 0:
                f_cl = bm.faces.new([grid_top[k+1][0], grid_top[k][0], grid_bot[k][0], grid_bot[k+1][0]])
            else:
                f_cl = bm.faces.new([grid_top[k][0], grid_top[k+1][0], grid_bot[k+1][0], grid_bot[k][0]])
            f_cl.material_index = MAT_INDEX_TIMBER
            for loop in f_cl.loops:
                loop[uv_layer_d].uv = Vector(((loop.vert.co.x + loop.vert.co.y) * 0.5, loop.vert.co.z * 0.5))

        # Side eave outer edge closure
        for j in range(n_len):
            if side_sign > 0:
                f_cl = bm.faces.new([grid_top[-1][j], grid_bot[-1][j], grid_bot[-1][j+1], grid_top[-1][j+1]])
            else:
                f_cl = bm.faces.new([grid_top[-1][j], grid_top[-1][j+1], grid_bot[-1][j+1], grid_bot[-1][j]])
            f_cl.material_index = MAT_INDEX_TIMBER
            for loop in f_cl.loops:
                loop[uv_layer_d].uv = Vector(((loop.vert.co.x + loop.vert.co.y) * 0.5, loop.vert.co.z * 0.5))

    # 7. Curved Verge Bargeboards (seated on the verge edge, not floating ahead of it)
    barge_t = 0.10
    barge_h = 0.16
    barge_xf = front_reach + 0.01
    for side_sign in [-1, 1]:
        for k in range(n_slope):
            u0 = k / n_slope
            u1 = (k + 1) / n_slope
            ys0 = side_sign * u0 * roof_half_w
            ys1 = side_sign * u1 * roof_half_w
            z0 = get_flare_z(u0)
            z1 = get_flare_z(u1)

            p0 = to_w(barge_xf, ys0, z0)
            p1 = to_w(barge_xf, ys1, z1)
            mid = (p0 + p1) * 0.5

            dys = ys1 - ys0
            dz = z1 - z0
            seg_len = math.sqrt(dys * dys + dz * dz) + 0.02
            
            roll_ang = math.atan2(dz, dys)
            rot_mat = Euler((0.0, 0.0, rot_z), 'XYZ').to_matrix().to_4x4() @ Euler((roll_ang, 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
            eul_rot = rot_mat.to_euler('XYZ')
            
            create_beveled_box(
                bm,
                size=(barge_t, seg_len, barge_h),
                location=mid,
                rotation=eul_rot,
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.012
            )

    # 8. Apex Finial Peak Cap Block
    apex_pos = to_w(front_reach + 0.06, 0.0, d_rz + 0.09)
    create_beveled_box(
        bm,
        size=(0.16, 0.18, 0.28),
        location=apex_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )

    # 9. Ridge Cap Beam running back along peak
    ridge_len = roof_len + 0.04
    ridge_pos = to_w(roof_mid_xf, 0.0, d_rz + 0.02)
    create_beveled_box(
        bm,
        size=(ridge_len, 0.14, 0.14),
        location=ridge_pos,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )

    # 10. Eave Side Fascia Trims along outer slope edges, running full length
    # back into the main roof so no end grain shows mid-slope
    for side_sign in [-1, 1]:
        fascia_pos = to_w(roof_mid_xf, side_sign * (roof_half_w - 0.02), d_ez + 0.01)
        create_beveled_box(
            bm,
            size=(roof_len, 0.06, 0.12),
            location=fascia_pos,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
