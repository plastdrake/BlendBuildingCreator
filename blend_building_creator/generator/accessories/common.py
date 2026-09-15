import math
from mathutils import Vector, Euler, Matrix
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from ..walls import create_curved_corbel
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
)

def _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max):
    """
    Returns (wall_anchor_x, wall_anchor_y, out_dx, out_dy, tan_dx, tan_dy, rot_z)
    for a given facade side.
    """
    if side == 'LEFT': # -X
        return (wall_x_min, (wall_y_min + wall_y_max) * 0.5, -1.0, 0.0, 0.0, 1.0, math.pi)
    elif side == 'RIGHT': # +X
        return (wall_x_max, (wall_y_min + wall_y_max) * 0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
    elif side == 'BACK': # +Y
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_max, 0.0, 1.0, 1.0, 0.0, math.pi * 0.5)
    else: # FRONT (-Y)
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_min, 0.0, -1.0, 1.0, 0.0, -math.pi * 0.5)

def _planar_uv_faces(bm, faces, scale=0.5, axis=None):
    """Force planar world-space UVs on faces by dominant normal axis."""
    _uv = bm.loops.layers.uv.verify()
    if axis is None:
        bm.normal_update()
    for _f in faces:
        if axis is None:
            _n = _f.normal
            _ax = 0 if abs(_n.x) >= abs(_n.y) and abs(_n.x) >= abs(_n.z) else (1 if abs(_n.y) >= abs(_n.z) else 2)
        else:
            _ax = axis
        for _lp in _f.loops:
            _c = _lp.vert.co
            _co = (_c.x, _c.y, _c.z)
            _lp[_uv].uv = (_co[(_ax + 1) % 3] * scale, _co[(_ax + 2) % 3] * scale)


def build_mini_wing(bm, side, floor_mode, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                    z_base, width=2.2, depth=1.6, height=2.6, roof_style='LEAN_TO', tier='TIER_3', floor_h=2.8):
    """
    Builds a small outcrop bay room / annex projection:
    - GROUND: rests on grounded stone foundation plinth.
    - UPPER: cantilevered oriel bay with heavy diagonal timber corbel brackets.
    - Features timber corner posts, leaded glass window, and dedicated shingled roof.
    """
    height = max(2.20, min(height, floor_h * 0.82))
    wx, wy, ox, oy, tx, ty, rot_z = _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    
    half_w = width * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    # 1. Foundation or Console Corbels
    if floor_mode == 'GROUND':
        found_depth = depth + 0.15
        found_width = width + 0.20
        # Foundation extends all the way down to ground level (z=0)
        found_h = max(0.30, z_base)
        loc_found = Vector((half_d + 0.05, 0.0, found_h * 0.5))
        world_found = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_found.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(found_depth, found_width, found_h),
            location=world_found,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )
    else: # UPPER floor oriel bay
        # Heavy diagonal timber console corbels underneath
        bracket_spacing = width * 0.38
        diag_len = math.sqrt((depth * 0.80) ** 2 + 0.75 ** 2)
        diag_ang = math.atan2(0.75, depth * 0.80)
        bx_vec = Vector((math.cos(diag_ang), 0.0, math.sin(diag_ang)))
        by_vec = Vector((0.0, 1.0, 0.0))
        bz_vec = Vector((-math.sin(diag_ang), 0.0, math.cos(diag_ang)))
        corbel_euler = (facade_rot_mat @ Matrix((bx_vec, by_vec, bz_vec)).transposed().to_4x4()).to_euler()
        
        for b_sign in [-1, 0, 1]:
            loc_c = Vector((depth * 0.40, b_sign * bracket_spacing, z_base - 0.42))
            world_c = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_c.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(diag_len, 0.12, 0.14),
                location=world_c,
                rotation=corbel_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )
            
    # 2. Walk-in Interior Wooden Floor & Ceiling Planks
    # Continuous level walk-in floor
    loc_fl = Vector((depth * 0.50, 0.0, z_base + 0.03))
    world_fl = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fl.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=world_fl,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Walk-in threshold floor board bridging through the house wall cutout
    mw_portal_w = min(1.30, width - 0.45)
    loc_thresh = Vector((-0.12, 0.0, z_base + 0.03))
    world_thresh = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_thresh.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.28, mw_portal_w - 0.06, 0.058),
        location=world_thresh,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Interior ceiling planks
    loc_ceil = Vector((depth * 0.50, 0.0, z_base + height - 0.03))
    world_ceil = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_ceil.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=world_ceil,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    
    # 3. Hollow Walls: Front Wall & Side Walls (Leaving Rear Open into Main Room)
    wall_mat = MAT_INDEX_TIMBER if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
    col_w = 0.16
    wall_thick = 0.12
    
    # 3a. Two Side Walls (Left and Right) ??? framed between timber corner posts
    for s_sign in [-1, 1]:
        loc_sw = Vector((depth * 0.50 + 0.01, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))
        world_sw = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sw.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth + 0.02, wall_thick, height),
            location=world_sw,
            rotation=(0.0, 0.0, rot_z),
            mat_index=wall_mat,
            bevel_amount=0.010
        )
        # Wall-anchor timber trim flat at house wall junction
        loc_post = Vector((0.04, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))
        world_post = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_post.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.08, col_w, height + 0.04),
            location=world_post,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Outer corner post ??? thickened + outset 1.8cm to break coplanar
        loc_cpost = Vector((depth - col_w * 0.5 + 0.018, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))
        world_cpost = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_cpost.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.18, 0.18, height + 0.06),
            location=world_cpost,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.014
        )
        # Heavy horizontal timber sill beam along side wall base (solid skirt hiding interior floor)
        loc_side_sill = Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + 0.04))
        world_side_sill = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_side_sill.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth + 0.06, col_w + 0.02, 0.18),
            location=world_side_sill,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        # Horizontal timber top plate beam along side wall top (under roof rafter / cheek)
        loc_side_top = Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + height - 0.04))
        world_side_top = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_side_top.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(depth + 0.04, col_w, 0.12),
            location=world_side_top,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        
    # 3b. Outer Front Wall with Window Cutout
    win_w = width * 0.52
    win_h = height * 0.46
    win_z = z_base + height * 0.52
    win_bot_z = win_z - win_h * 0.5
    win_top_z = win_z + win_h * 0.5
    
    # Outer front wall center
    f_wall_x = depth - wall_thick * 0.5
    # Front spandrel below window
    spand_h = win_bot_z - z_base
    loc_spand = Vector((f_wall_x, 0.0, z_base + spand_h * 0.5))
    world_spand = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_spand.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, spand_h),
        location=world_spand,
        rotation=(0.0, 0.0, rot_z),
        mat_index=wall_mat,
        bevel_amount=0.010
    )
    # Front side jambs flanking window
    jamb_w = (width - col_w * 2.0 - win_w) * 0.5 + 0.02
    for s_sign in [-1, 1]:
        jamb_off = (win_w * 0.5 + jamb_w * 0.5 - 0.01) * s_sign
        loc_j = Vector((f_wall_x, jamb_off, win_z))
        world_j = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_j.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(wall_thick, jamb_w, win_h + 0.04),
            location=world_j,
            rotation=(0.0, 0.0, rot_z),
            mat_index=wall_mat,
            bevel_amount=0.008
        )
    # Front header above window
    head_h = (z_base + height) - win_top_z
    loc_head = Vector((f_wall_x, 0.0, win_top_z + head_h * 0.5))
    world_head = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_head.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, head_h),
        location=world_head,
        rotation=(0.0, 0.0, rot_z),
        mat_index=wall_mat,
        bevel_amount=0.008
    )
    
    # Heavy horizontal timber sill plate across front wall base (solid skirt hiding interior floor)
    loc_front_sill = Vector((depth - col_w * 0.5 + 0.015, 0.0, z_base + 0.04))
    world_front_sill = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_front_sill.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.18),
        location=world_front_sill,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    # Outer top horizontal header beam across front wall top
    loc_fhead = Vector((depth - col_w * 0.5 + 0.01, 0.0, z_base + height - 0.04))
    world_fhead = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_fhead.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.14),
        location=world_fhead,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    # 4. Outcrop Window Assembly with proper timber casing frame
    # Timber window sill
    loc_sill = Vector((depth + 0.04, 0.0, win_bot_z - 0.04))
    world_sill = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_sill.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.12, win_w + 0.20, 0.10),
        location=world_sill,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )
    # Glass & mullions
    loc_win = Vector((depth, 0.0, win_z))
    world_win = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_win.to_4d()).to_3d()
    create_box(
        bm,
        size=(0.05, win_w, win_h),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_GLASS
    )
    create_box(
        bm,
        size=(0.07, 0.04, win_h),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )
    create_box(
        bm,
        size=(0.07, win_w, 0.04),
        location=world_win,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER
    )
    # Proper timber window casing frame (left jamb, right jamb, top header)
    casing_t = 0.09
    casing_w = 0.10
    for s_sign in [-1, 1]:
        loc_wj = Vector((depth + 0.02, (win_w * 0.5 + casing_w * 0.5) * s_sign, win_z))
        world_wj = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_wj.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(casing_t, casing_w, win_h + casing_w),
            location=world_wj,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
    # Top header
    loc_wh = Vector((depth + 0.02, 0.0, win_top_z + casing_w * 0.5))
    world_wh = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_wh.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(casing_t + 0.02, win_w + casing_w * 2.0 + 0.06, casing_w),
        location=world_wh,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.010
    )

    # 4b. Interior Window Assembly matching main house windows (reveal lining, stool, apron, jambs, header)
    in_wall_x = depth - wall_thick
    in_casing_w = 0.09
    in_casing_t = 0.045
    
    # Interior reveal lining sleeve
    loc_rl_j1 = Vector((f_wall_x, -win_w * 0.5 + 0.01, win_z))
    world_rl_j1 = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_rl_j1.to_4d()).to_3d()
    create_beveled_box(bm, size=(wall_thick + 0.01, 0.02, win_h), location=world_rl_j1, rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    loc_rl_j2 = Vector((f_wall_x, win_w * 0.5 - 0.01, win_z))
    world_rl_j2 = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_rl_j2.to_4d()).to_3d()
    create_beveled_box(bm, size=(wall_thick + 0.01, 0.02, win_h), location=world_rl_j2, rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    loc_rl_top = Vector((f_wall_x, 0.0, win_top_z - 0.01))
    world_rl_top = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_rl_top.to_4d()).to_3d()
    create_beveled_box(bm, size=(wall_thick + 0.01, win_w, 0.02), location=world_rl_top, rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    loc_rl_bot = Vector((f_wall_x, 0.0, win_bot_z + 0.01))
    world_rl_bot = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_rl_bot.to_4d()).to_3d()
    create_beveled_box(bm, size=(wall_thick + 0.01, win_w, 0.02), location=world_rl_bot, rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)

    # Interior Sill Stool shelf extending into the room
    loc_istool = Vector((in_wall_x - 0.035, 0.0, win_bot_z + 0.02))
    world_istool = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_istool.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.09, win_w + in_casing_w * 2.0 + 0.08, 0.048),
        location=world_istool,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.008
    )

    # Interior Apron trim directly underneath stool shelf
    in_apron_h = 0.12
    loc_iapron = Vector((in_wall_x - 0.012, 0.0, win_bot_z - in_apron_h * 0.5 - 0.004))
    world_iapron = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_iapron.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(0.030, win_w + in_casing_w * 2.0 + 0.02, in_apron_h),
        location=world_iapron,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.006
    )

    # Interior Side Jambs running from stool shelf up to header
    in_jamb_h = win_h + 0.02
    for s_sign in [-1, 1]:
        loc_inj = Vector((in_wall_x - 0.012, (win_w * 0.5 + in_casing_w * 0.5 - 0.01) * s_sign, win_z))
        world_inj = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_inj.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(in_casing_t, in_casing_w, in_jamb_h),
            location=world_inj,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )

    # Interior Lintel / Header Beam across top of window
    in_th_h = in_casing_w + 0.04
    loc_inth = Vector((in_wall_x - 0.016, 0.0, win_top_z + in_th_h * 0.5 - 0.015))
    world_inth = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_inth.to_4d()).to_3d()
    create_beveled_box(
        bm,
        size=(in_casing_t + 0.020, win_w + in_casing_w * 2.0 + 0.06, in_th_h),
        location=world_inth,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.010
    )
    
    # 5. Dedicated Roof with Sealed Side Cheek Walls (Zero Gaps)
    roof_z_start = z_base + height
    avail_roof_h = max(0.35, floor_h - height - 0.08)
    
    if roof_style == 'LEAN_TO':
        roof_pitch = 0.32
        r_rise = min(avail_roof_h, depth * roof_pitch)
        x_back = -0.01
        x_front = depth + 0.16
        roof_len = x_front - x_back
        r_len = math.sqrt(roof_len * roof_len + r_rise * r_rise)
        r_ang = math.atan2(r_rise, roof_len)
        rx_vec = Vector((math.cos(-r_ang), 0.0, math.sin(-r_ang)))
        ry_vec = Vector((0.0, 1.0, 0.0))
        rz_vec = Vector((-math.sin(-r_ang), 0.0, math.cos(-r_ang)))
        local_rot_mat = Matrix((rx_vec, ry_vec, rz_vec)).transposed().to_4x4()
        total_roof_mat = facade_rot_mat @ local_rot_mat
        roof_euler = total_roof_mat.to_euler()

        # Single shingle roof slab only; starts at x_back (-0.03) stopping cleanly before interior room
        mid_x = (x_front + x_back) * 0.5
        mid_z = roof_z_start + r_rise * 0.5 + 0.06
        loc_shingle = Vector((mid_x, 0.0, mid_z))
        world_shingle = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_shingle.to_4d()).to_3d()
        _slab_sx = r_len * 0.5
        _slab_sy = (width + 0.34) * 0.5
        _slab_sz = 0.04
        create_beveled_box(
            bm,
            size=(r_len, width + 0.34, 0.08),
            location=world_shingle,
            rotation=roof_euler,
            mat_index=MAT_INDEX_SHINGLES,
            bevel_amount=0.008
        )
        # Main-roof shingle UVs: U along the eave (width), V down the slope from ridge to eave
        try:
            from mathutils import Matrix as _Mat, Vector as _Vec
            _uv = bm.loops.layers.uv.verify()
            _slab_mat = _Mat.Translation(_Vec(world_shingle)) @ roof_euler.to_matrix().to_4x4()
            _inv = _slab_mat.inverted()
            for _f in bm.faces:
                if _f.material_index != MAT_INDEX_SHINGLES:
                    continue
                _c = _f.calc_center_median()
                _lco = _inv @ _c
                if abs(_lco.x) > _slab_sx + 0.05 or abs(_lco.y) > _slab_sy + 0.05 or abs(_lco.z) > _slab_sz + 0.05:
                    continue
                _f.tag = True
                for _lp in _f.loops:
                    _vco = _inv @ _lp.vert.co
                    _lp[_uv].uv = _Vec(((_vco.y + _slab_sy) * 0.32, -(_vco.x + _slab_sx) * 0.32))
        except Exception:
            pass

        # Front eave purlin beam capping the slab's front edge
        loc_eave = Vector((x_front - 0.04, 0.0, roof_z_start + 0.04))
        world_eave = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_eave.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.10, width + 0.38, 0.14),
            location=world_eave,
            rotation=roof_euler,
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        
        # Side triangular cheek closure walls & sloping timber bargeboards
        barge_w = 0.08
        for s_sign in [-1, 1]:
            loc_barge = Vector((mid_x, (half_w + 0.16) * s_sign, mid_z))
            world_barge = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_barge.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(r_len + 0.04, barge_w, 0.12),
                location=world_barge,
                rotation=roof_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.008
            )
            # Sloping timber rafter plate atop the side wall
            loc_side_rafter = Vector((mid_x, (half_w - wall_thick * 0.5) * s_sign, mid_z - 0.06))
            world_side_rafter = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_side_rafter.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(r_len, wall_thick + 0.02, 0.10),
                location=world_side_rafter,
                rotation=roof_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.008
            )
            # Solid triangular cheek prism filling wedge between flat side wall top and sloping rafter
            tri_y_center = (half_w - wall_thick * 0.5) * s_sign
            half_t = wall_thick * 0.5
            v_t_b1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center - half_t, roof_z_start + r_rise)).to_4d()).to_3d())
            v_b_f1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((depth, tri_y_center - half_t, roof_z_start)).to_4d()).to_3d())
            v_b_b1 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center - half_t, roof_z_start)).to_4d()).to_3d())
            
            v_t_b2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center + half_t, roof_z_start + r_rise)).to_4d()).to_3d())
            v_b_f2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((depth, tri_y_center + half_t, roof_z_start)).to_4d()).to_3d())
            v_b_b2 = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((0.0, tri_y_center + half_t, roof_z_start)).to_4d()).to_3d())
            
            f1 = bm.faces.new([v_t_b1, v_b_f1, v_b_b1])
            f1.material_index = wall_mat
            f2 = bm.faces.new([v_t_b2, v_b_b2, v_b_f2])
            f2.material_index = wall_mat
            f_slope = bm.faces.new([v_t_b1, v_t_b2, v_b_f2, v_b_f1])
            f_slope.material_index = wall_mat
            f_back = bm.faces.new([v_t_b1, v_b_b1, v_b_b2, v_t_b2])
            f_back.material_index = wall_mat
    else: # GABLE roof
        g_roof_h = min(avail_roof_h, 0.58)
        x_back = -0.03
        x_front = depth + 0.16
        roof_len = x_front - x_back
        mid_x = (x_front + x_back) * 0.5
        roof_half_w = half_w + 0.16
        r_pitch_len = math.sqrt(roof_half_w ** 2 + g_roof_h ** 2)
        r_pitch_ang = math.atan2(g_roof_h, roof_half_w)

        # 1. Front Triangular Gable Wall (apex tucked cleanly under roof deck; no rectangular box poking through)
        tri_x = depth - 0.04
        tri_half_w = half_w - 0.02
        tri_apex_z = roof_z_start + g_roof_h - 0.06
        tri_t = 0.08

        v_apex_f = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x, 0.0, tri_apex_z)).to_4d()).to_3d())
        v_left_f = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x, -tri_half_w, roof_z_start + 0.02)).to_4d()).to_3d())
        v_right_f = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x, tri_half_w, roof_z_start + 0.02)).to_4d()).to_3d())

        v_apex_b = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x - tri_t, 0.0, tri_apex_z)).to_4d()).to_3d())
        v_left_b = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x - tri_t, -tri_half_w, roof_z_start + 0.02)).to_4d()).to_3d())
        v_right_b = bm.verts.new(Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((tri_x - tri_t, tri_half_w, roof_z_start + 0.02)).to_4d()).to_3d())

        f_tri_f = bm.faces.new([v_apex_f, v_right_f, v_left_f])
        f_tri_f.material_index = wall_mat
        f_tri_b = bm.faces.new([v_apex_b, v_left_b, v_right_b])
        f_tri_b.material_index = wall_mat
        f_tri_l = bm.faces.new([v_apex_f, v_left_f, v_left_b, v_apex_b])
        f_tri_l.material_index = wall_mat
        f_tri_r = bm.faces.new([v_apex_f, v_apex_b, v_right_b, v_right_f])
        f_tri_r.material_index = wall_mat
        f_tri_bot = bm.faces.new([v_left_f, v_right_f, v_right_b, v_left_b])
        f_tri_bot.material_index = wall_mat

        # 2. Horizontal Collar Tie Beam across base of front gable
        loc_collar = Vector((tri_x + 0.02, 0.0, roof_z_start + 0.04))
        world_collar = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_collar.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.12, width + 0.08, 0.12),
            location=world_collar,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

        # 3. Vertical King Post Beam in gable center
        king_h = max(0.18, g_roof_h - 0.16)
        loc_king = Vector((tri_x + 0.02, 0.0, roof_z_start + 0.10 + king_h * 0.5))
        world_king = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_king.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.10, 0.12, king_h),
            location=world_king,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )

        # 4. Pitched Roof Slopes (Left & Right) with Parametric Shingle UV Mapping
        _uv = bm.loops.layers.uv.verify()
        slope_thickness = 0.08
        for s_sign in [-1, 1]:
            # Local slope rotation: tilts around local X axis
            sx_vec = Vector((1.0, 0.0, 0.0))
            sy_vec = Vector((0.0, math.cos(s_sign * r_pitch_ang), -math.sin(s_sign * r_pitch_ang)))
            sz_vec = Vector((0.0, math.sin(s_sign * r_pitch_ang), math.cos(s_sign * r_pitch_ang)))
            g_rot = (facade_rot_mat @ Matrix((sx_vec, sy_vec, sz_vec)).transposed().to_4x4()).to_euler()
            
            # Position slope centered along slope span
            loc_slope = Vector((mid_x, (roof_half_w * 0.5) * s_sign, roof_z_start + g_roof_h * 0.5 + 0.02))
            world_slope = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_slope.to_4d()).to_3d()
            
            create_beveled_box(
                bm,
                size=(roof_len, r_pitch_len, slope_thickness),
                location=world_slope,
                rotation=g_rot,
                mat_index=MAT_INDEX_SHINGLES,
                bevel_amount=0.008
            )
            
            # Map shingle UVs on this slope: U along ridge (front to back), V down slope (ridge to eave)
            try:
                from mathutils import Matrix as _Mat, Vector as _Vec
                _slope_mat = _Mat.Translation(_Vec(world_slope)) @ g_rot.to_matrix().to_4x4()
                _inv = _slope_mat.inverted()
                _sx = roof_len * 0.5
                _sy = r_pitch_len * 0.5
                _sz = slope_thickness * 0.5
                for _f in bm.faces:
                    if _f.material_index != MAT_INDEX_SHINGLES:
                        continue
                    _c = _f.calc_center_median()
                    _lco = _inv @ _c
                    if abs(_lco.x) > _sx + 0.05 or abs(_lco.y) > _sy + 0.05 or abs(_lco.z) > _sz + 0.05:
                        continue
                    _f.tag = True
                    for _lp in _f.loops:
                        _vco = _inv @ _lp.vert.co
                        u_val = (_vco.x + _sx) * 0.32
                        if s_sign > 0:
                            v_val = -(_vco.y + _sy) * 0.32
                        else:
                            v_val = -(_sy - _vco.y) * 0.32
                        _lp[_uv].uv = _Vec((u_val, v_val))
            except Exception:
                pass

            # 5. Sloping timber bargeboard along front edge of this slope
            barge_len = r_pitch_len + 0.04
            loc_barge = Vector((x_front - 0.02, (roof_half_w * 0.5) * s_sign, roof_z_start + g_roof_h * 0.5 + 0.03))
            world_barge = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_barge.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(0.08, barge_len, 0.14),
                location=world_barge,
                rotation=g_rot,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.008
            )

            # 5b. Horizontal timber eave fascia beam capping the low edge of this slope
            loc_low_eave = Vector((mid_x, s_sign * (roof_half_w - 0.02), roof_z_start + 0.04))
            world_low_eave = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_low_eave.to_4d()).to_3d()
            create_beveled_box(
                bm,
                size=(roof_len + 0.04, 0.10, 0.14),
                location=world_low_eave,
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.010
            )

        # 6. Horizontal Timber Ridge Cap Beam along ridge line
        loc_ridge = Vector((mid_x, 0.0, roof_z_start + g_roof_h + 0.04))
        world_ridge = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_ridge.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(roof_len + 0.02, 0.14, 0.12),
            location=world_ridge,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

        # 7. Apex Finial Cap Block at front ridge peak
        loc_finial = Vector((x_front + 0.01, 0.0, roof_z_start + g_roof_h + 0.05))
        world_finial = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_finial.to_4d()).to_3d()
        create_beveled_box(
            bm,
            size=(0.12, 0.16, 0.18),
            location=world_finial,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )



def build_pillared_overhang(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                            z_ground, z_ceiling, depth=1.6, pillar_count=3,
                            pillar_style='TIMBER_STONE', tier='TIER_3'):
    """
    Builds a colonnaded portico / upper overhang supported by heavy vertical pillars
    extending from the overhang header beam down to ground level.
    """
    wx, wy, ox, oy, tx, ty, rot_z = _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    
    total_w = abs((wall_y_max - wall_y_min) if abs(ox) > 0.5 else (wall_x_max - wall_x_min)) * 0.88
    half_w = total_w * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    total_col_h = z_ceiling - z_ground
    outer_d = depth
    
    # 1. Outer Horizontal Header Beam
    header_w = 0.18
    header_h = 0.20
    create_beveled_box(
        bm,
        size=(header_w, total_w + 0.30, header_h),
        location=(wx + ox * (outer_d - header_w * 0.5), wy + oy * (outer_d - header_w * 0.5), z_ceiling - header_h * 0.5),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    
    # 2. Vertical Pillars reaching all the way down to ground
    pillar_col_w = 0.18
    plinth_h = 0.25
    plinth_w = 0.36
    
    step_t = total_w / max(1, pillar_count - 1)
    for p_i in range(pillar_count):
        t_offset = -half_w + p_i * step_t
        px = wx + ox * (outer_d - header_w * 0.5) + tx * t_offset
        py = wy + oy * (outer_d - header_w * 0.5) + ty * t_offset
        
        if pillar_style == 'TIMBER_STONE':
            # Grounded stone plinth
            create_beveled_box(
                bm,
                size=(plinth_w, plinth_w, plinth_h),
                location=(px, py, z_ground + plinth_h * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )
            # Timber pillar post (embedded 1cm into plinth: no coplanar bottom face)
            shaft_h = total_col_h - plinth_h - header_h
            create_beveled_box(
                bm,
                size=(pillar_col_w, pillar_col_w, shaft_h + 0.01),
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5 - 0.01),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )
            brace_len = 1.05
            for sgn in ([-1] if p_i == pillar_count - 1 else ([1] if p_i == 0 else [-1, 1])):
                brace_dir = (Vector((tx, ty, 0.0)) * sgn + Vector((0.0, 0.0, 1.0))).normalized()
                brace_norm = Vector((ox, oy, 0.0)).normalized()
                brace_side = brace_dir.cross(brace_norm).normalized()
                brace_rot_mat = Matrix((brace_norm, brace_side, brace_dir)).transposed().to_4x4()
                
                loc_b = Vector((px, py, z_ceiling - header_h + 0.02)) + (Vector((tx, ty, 0.0)) * sgn * 0.32 - Vector((0.0, 0.0, 0.32)))
                create_beveled_box(
                    bm,
                    size=(0.12, 0.12, brace_len),
                    location=loc_b,
                    rotation=brace_rot_mat.to_euler(),
                    mat_index=MAT_INDEX_TIMBER_FRAME,
                    bevel_amount=0.008
                )
        elif pillar_style == 'ROUND_POST':
            # Round log post
            create_cylinder(
                bm,
                radius=0.18, height=plinth_h, segments=12,
                location=(px, py, z_ground + plinth_h * 0.5),
                mat_index=MAT_INDEX_STONE
            )
            shaft_h = total_col_h - plinth_h - header_h
            create_cylinder(
                bm,
                radius=0.11, height=shaft_h, segments=12,
                location=(px, py, z_ground + plinth_h + shaft_h * 0.5),
                mat_index=MAT_INDEX_TIMBER_FRAME
            )
        else: # STONE_COLUMN
            # Full chunky masonry pier
            create_beveled_box(
                bm,
                size=(0.32, 0.32, total_col_h - header_h),
                location=(px, py, z_ground + (total_col_h - header_h) * 0.5),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_STONE,
                bevel_amount=0.02
            )
            
    # 3. Timber Framing Beams Covering the Exterior Wall Box:
    box_w = (total_w + 0.12) * 1.2
    box_d = (depth + 0.12) * 1.2
    box_half_w = box_w * 0.5
    soffit_cx = wx + ox * (half_d + 0.06)
    soffit_cy = wy + oy * (half_d + 0.06)

    rim_t = 0.16
    rim_h = 0.22
    rim_z = z_ceiling - 0.075

    # Left Rim Beam (covering left side face of the box)
    w_left_rim = Vector((soffit_cx, soffit_cy, rim_z)) + Vector((tx, ty, 0.0)) * (-box_half_w + rim_t * 0.5)
    create_beveled_box(
        bm,
        size=(box_d + 0.04, rim_t, rim_h),
        location=w_left_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Right Rim Beam (covering right side face of the box)
    w_right_rim = Vector((soffit_cx, soffit_cy, rim_z)) + Vector((tx, ty, 0.0)) * (box_half_w - rim_t * 0.5)
    create_beveled_box(
        bm,
        size=(box_d + 0.04, rim_t, rim_h),
        location=w_right_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Front Rim Beam (fit between side rims so corner tops are not coplanar-overlapped)
    front_dist = half_d + 0.06 + box_d * 0.5 - rim_t * 0.5
    w_front_rim = Vector((wx + ox * front_dist, wy + oy * front_dist, rim_z + 0.008))
    create_beveled_box(
        bm,
        size=(rim_t, box_w - rim_t * 2.0 + 0.02, rim_h),
        location=w_front_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Rear Ledger Beam along building wall
    rear_dist = half_d + 0.06 - box_d * 0.5 + rim_t * 0.5
    w_rear_rim = Vector((wx + ox * rear_dist, wy + oy * rear_dist, rim_z + 0.008))
    create_beveled_box(
        bm,
        size=(rim_t, box_w - rim_t * 2.0 + 0.02, rim_h),
        location=w_rear_rim,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # Ceiling joist beams underneath the overhang ??? spanning full width between left and right rim beams
    beam_spacing = 0.60
    usable_w = box_w - rim_t * 2.0
    num_beams = max(pillar_count + 1, int(usable_w / beam_spacing) + 1)
    actual_spacing = usable_w / max(1, num_beams - 1) if num_beams > 1 else usable_w
    for b_i in range(num_beams):
        t_off = -usable_w * 0.5 + b_i * actual_spacing
        bx = soffit_cx + tx * t_off
        by = soffit_cy + ty * t_off
        create_beveled_box(
            bm,
            size=(box_d - rim_t * 1.5, 0.12, 0.14),
            location=(bx, by, z_ceiling - 0.09),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    # Wood soffit inside ceiling (inset 2cm from rim outer faces: no coplanar edges)
    create_beveled_box(
        bm,
        size=(box_d - 0.04, box_w - 0.04, 0.06),
        location=(soffit_cx, soffit_cy, z_ceiling - 0.02),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Plaster box soffit paneling - framed cleanly between the timber beams
    ext_mat = MAT_INDEX_PLASTER_EXT
    create_beveled_box(
        bm,
        size=(box_d - 0.06, box_w - 0.06, 0.07),
        location=(soffit_cx, soffit_cy, z_ceiling - 0.075),
        rotation=(0.0, 0.0, rot_z),
        mat_index=ext_mat,
        bevel_amount=0.006
    )
    # Fascia closure at wall line to hide slab side
    fascia_x = wx + ox * 0.06
    fascia_y = wy + oy * 0.06
    create_beveled_box(bm, size=(0.14, total_w + 0.18, 0.16), location=(fascia_x, fascia_y, z_ceiling - 0.08), rotation=(0.0,0.0,rot_z), mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010)
    # Ground flagstone platform
    create_beveled_box(
        bm,
        size=(depth + 0.20, total_w + 0.35, 0.12),
        location=(cx, cy, z_ground + 0.06),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )

def build_cargo_port_frame(bm, face_x, outward_sgn, cy, portal_w, portal_h, z_floor, wall_t,
                           dock_y1=None, dock_y2=None):
    """
    Builds an open freight portal frame (no door leaf) in a wing side wall so the
    courtyard crane can lift cargo straight in:
    - Chunky timber jamb posts proud of the facade with iron binding straps.
    - Heavy timber lintel beam spanning the opening.
    - Wooden threshold strip flush with the interior floor (no step, roll cargo in).
    - Full-length loading dock outside: plank deck flush with the floor, carried on
      longitudinal bearer beams, chunky posts on stone footings, with a dark timber
      fascia skirt so it reads as a dock rather than a table.
    Callers must also cut a matching wall opening (u-span portal_w at cy,
    z_floor to z_floor + portal_h) and keep windows/timber clear of it.
    dock_y1/dock_y2 optionally bound the dock ends along the wall (defaults: a
    short pad around the portal).
    """
    jamb_w = 0.24
    jamb_d = wall_t + 0.26
    jx = face_x + outward_sgn * 0.06
    for s in (-1.0, 1.0):
        jy = cy + s * (portal_w * 0.5 + jamb_w * 0.5)
        create_beveled_box(
            bm, size=(jamb_d, jamb_w, portal_h),
            location=(jx, jy, z_floor + portal_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014, bevel_segments=2
        )
        for sz in (0.55, portal_h - 0.55):
            create_beveled_box(
                bm, size=(jamb_d + 0.03, jamb_w + 0.03, 0.09),
                location=(jx, jy, z_floor + sz),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.005
            )
    create_beveled_box(
        bm, size=(jamb_d, portal_w + jamb_w * 2.0 + 0.12, 0.30),
        location=(jx, cy, z_floor + portal_h + 0.15),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014, bevel_segments=2
    )
    # Wooden threshold bridging the wall gap, flush with the interior floor
    floor_top = z_floor + 0.05
    create_beveled_box(
        bm, size=(wall_t + 0.24, portal_w + 0.12, 0.10),
        location=(face_x, cy, floor_top - 0.05),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )
    # Full-length loading dock outside, deck top flush with the floor
    deck_t = 0.14
    deck_top = floor_top
    deck_d = 1.6
    if dock_y1 is None:
        dock_y1 = cy - (portal_w * 0.5 + 0.5)
    if dock_y2 is None:
        dock_y2 = cy + (portal_w * 0.5 + 0.5)
    deck_y1, deck_y2 = min(dock_y1, dock_y2), max(dock_y1, dock_y2)
    deck_len = max(1.0, deck_y2 - deck_y1)
    deck_yc = (deck_y1 + deck_y2) * 0.5
    deck_inner = face_x + outward_sgn * (wall_t * 0.5)
    deck_cx = deck_inner + outward_sgn * (deck_d * 0.5)
    create_beveled_box(
        bm, size=(deck_d, deck_len, deck_t),
        location=(deck_cx, deck_yc, deck_top - deck_t * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.01
    )
    # Longitudinal bearer beams under the deck (inner + outer post lines)
    bearer_h = 0.16
    bearer_z = deck_top - deck_t - bearer_h * 0.5
    post_rows = [deck_inner + outward_sgn * 0.20, deck_inner + outward_sgn * (deck_d - 0.20)]
    for brow in post_rows:
        create_beveled_box(
            bm, size=(0.16, deck_len - 0.10, bearer_h),
            location=(brow, deck_yc, bearer_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Dark fascia skirt around the deck edges (hides the bearer layer)
    fascia_h = 0.30
    fascia_z = deck_top - fascia_h * 0.5 + 0.02
    create_beveled_box(
        bm, size=(0.06, deck_len, fascia_h),
        location=(deck_inner + outward_sgn * (deck_d - 0.03), deck_yc, fascia_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    for es in (-1.0, 1.0):
        create_beveled_box(
            bm, size=(deck_d, 0.06, fascia_h),
            location=(deck_cx, deck_yc + es * (deck_len * 0.5 - 0.03), fascia_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Chunky posts on stone footings, spaced along both bearer lines
    n_posts = max(3, int(deck_len / 1.3) + 1)
    footing_top = 0.18
    post_top = bearer_z - bearer_h * 0.5
    post_h = post_top - footing_top
    if post_h > 0.12:
        for brow in post_rows:
            for k in range(n_posts):
                py = deck_y1 + 0.28 + (deck_len - 0.56) * (k / max(1, n_posts - 1))
                create_beveled_box(
                    bm, size=(0.34, 0.34, footing_top),
                    location=(brow, py, footing_top * 0.5),
                    mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
                )
                create_beveled_box(
                    bm, size=(0.16, 0.16, post_h),
                    location=(brow, py, footing_top + post_h * 0.5),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
                )
