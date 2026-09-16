import math
from mathutils import Vector, Matrix
from ..facade import get_facade_frame
from ..railing import build_railing
from ..uv_utils import map_planar_faces
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

def build_tavern_porch_and_sign(bm, x_min, x_max, front_y, z_ground, door_x=None, seed=42):
    if door_x is None:
        door_x = (x_min + x_max) * 0.5
        
    porch_w = 2.8
    porch_d = 1.5
    porch_h = 2.4
    px_min = door_x - porch_w * 0.5
    px_max = door_x + porch_w * 0.5
    py_front = front_y - porch_d
    
    deck_h = 0.20
    create_beveled_box(
        bm, size=(porch_w, porch_d, deck_h),
        location=(door_x, (front_y + py_front) * 0.5, z_ground + deck_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    create_beveled_box(
        bm, size=(porch_w * 0.65, 0.35, deck_h * 0.5),
        location=(door_x, py_front - 0.18, z_ground + deck_h * 0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )

    col_r = 0.09
    col_h = porch_h - deck_h
    col_z = z_ground + deck_h + col_h * 0.5
    for cx in (px_min + col_r, px_max - col_r):
        create_cylinder(
            bm, radius=col_r, height=col_h, segments=12,
            location=(cx, py_front + col_r, col_z),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + deck_h + 0.04),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + porch_h - 0.04),
            mat_index=MAT_INDEX_TIMBER
        )

    create_beveled_box(
        bm, size=(porch_w + 0.20, 0.14, 0.16),
        location=(door_x, py_front + col_r, z_ground + porch_h),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )
    awning_pitch = 0.35
    awning_l = math.sqrt(porch_d * porch_d + (porch_d * awning_pitch) ** 2) + 0.25
    awning_mid_y = (front_y + py_front) * 0.5
    awning_mid_z = z_ground + porch_h + (porch_d * awning_pitch) * 0.5 + 0.08
    awning_ang = math.atan2(porch_d * awning_pitch, porch_d)
    
    create_beveled_box(
        bm, size=(porch_w + 0.30, awning_l, 0.08),
        location=(door_x, awning_mid_y, awning_mid_z),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    create_beveled_box(
        bm, size=(porch_w + 0.35, awning_l + 0.04, 0.05),
        location=(door_x, awning_mid_y, awning_mid_z + 0.065),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.006
    )

    post_cx = px_max - col_r
    post_cy = py_front + col_r
    sign_z = z_ground + porch_h - 0.15
    bracket_l = 0.85
    arm_x = post_cx + bracket_l * 0.5
    create_cylinder(
        bm, radius=0.024, height=bracket_l, segments=8,
        location=(arm_x, post_cy, sign_z),
        rotation=(0.0, 1.57, 0.0),
        mat_index=MAT_INDEX_IRON
    )
    create_beveled_box(
        bm, size=(0.020, 0.020, 0.45),
        location=(post_cx + 0.18, post_cy, sign_z - 0.18),
        rotation=(0.0, 0.78, 0.0),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.003
    )
    create_cylinder(
        bm, radius=0.035, height=0.022, segments=8,
        location=(post_cx + bracket_l - 0.02, post_cy, sign_z + 0.04),
        rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    board_x = post_cx + bracket_l * 0.68
    board_d = 0.55
    board_h = 0.42
    board_cz = sign_z - 0.35
    for cd_off in [-board_d * 0.30, board_d * 0.30]:
        create_cylinder(
            bm, radius=0.012, height=0.15, segments=6,
            location=(board_x, post_cy + cd_off, sign_z - 0.075),
            mat_index=MAT_INDEX_IRON
        )
    create_beveled_box(
        bm, size=(0.05, board_d, board_h),
        location=(board_x, post_cy, board_cz),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    create_beveled_box(
        bm, size=(0.056, board_d - 0.08, board_h - 0.08),
        location=(board_x, post_cy, board_cz),
        mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.004
    )
    create_cylinder(
        bm, radius=0.018, height=0.04, segments=6,
        location=(board_x, post_cy, board_cz - board_h * 0.5 - 0.02),
        mat_index=MAT_INDEX_IRON
    )

def build_balcony(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                  z_floor, width=2.4, depth=1.3, tier='TIER_3',
                  lower_wall_x_min=None, lower_wall_x_max=None,
                  lower_wall_y_min=None, lower_wall_y_max=None):
    wx, wy, ox, oy, tx, ty, rot_z = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    
    if lower_wall_x_min is not None and lower_wall_x_max is not None and lower_wall_y_min is not None and lower_wall_y_max is not None:
        lwx, lwy, lox, loy, ltx, lty, lrot_z = get_facade_frame(side, lower_wall_x_min, lower_wall_x_max, lower_wall_y_min, lower_wall_y_max)
        overhang_dist = max(0.0, (wx - lwx) * ox + (wy - lwy) * oy)
    else:
        overhang_dist = 0.0

    half_w = width * 0.5
    half_d = depth * 0.5
    cx = wx + ox * half_d
    cy = wy + oy * half_d
    
    joist_count = 2
    spacing = width * 0.42
    for j_sign in [-1, 1]:
        joist_len = depth + overhang_dist + 0.35
        j_local_x = (depth + 0.08 - overhang_dist - 0.25) * 0.5
        loc_j = Vector((j_local_x, j_sign * spacing, z_floor - 0.08))
        world_j = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_j.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(joist_len, 0.12, 0.16),
            location=world_j,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        embed = 0.04
        corbel_depth = overhang_dist + embed + depth * 0.60
        corbel_h = max(0.48, 0.42 + overhang_dist * 0.40)
        p_corbel_wall = Vector((wx - ox * (overhang_dist + embed), wy - oy * (overhang_dist + embed), z_floor - 0.08)) + Vector((tx, ty, 0.0)) * (j_sign * spacing)
        create_curved_corbel(
            bm, loc=p_corbel_wall, facing_dir=(ox, oy, 0.0),
            width=0.16, depth=corbel_depth, height=corbel_h,
            mat_index=MAT_INDEX_TIMBER_FRAME
        )
        
    loc_deck = Vector((depth * 0.50, 0.0, z_floor + 0.03))
    world_deck = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_deck.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(depth + 0.08, width + 0.10, 0.06),
        location=world_deck,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    
    rail_h = 0.95
    outer_d = depth + 0.02
    wall_clearance = 0.48

    def _w(lx, ly):
        p = Vector((wx, wy, 0.0)) + (facade_rot_mat @ Vector((lx, ly, 0.0)).to_4d()).to_3d()
        return (p.x, p.y)

    # Detailed guard railings around the deck (front run + both returns),
    # built with the shared railing generator so all rails match the rest of
    # the building's joinery.
    build_railing(bm, _w(outer_d, -half_w), _w(outer_d, half_w),
                  z_floor + 0.06, height=rail_h)
    for s_sign in [-1, 1]:
        build_railing(bm, _w(wall_clearance, half_w * s_sign),
                      _w(outer_d, half_w * s_sign),
                      z_floor + 0.06, height=rail_h, braces=False,
                      post_spacing=1.0)

        
    door_w = 0.92
    door_h = 2.02
    door_thick = 0.05
    loc_dl = Vector((0.02, 0.0, z_floor + door_h + 0.06))
    world_dl = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dl.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(0.14, door_w + 0.20, 0.12),
        location=world_dl,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )
    for d_sign in [-1, 1]:
        loc_dj = Vector((0.02, (door_w * 0.5 + 0.06) * d_sign, z_floor + door_h * 0.5))
        world_dj = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dj.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(0.14, 0.12, door_h),
            location=world_dj,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        
    door_leaf_w = door_w - 0.06
    door_leaf_h = door_h - 0.06
    num_planks = 4
    plank_gap = 0.004
    pw = (door_leaf_w - (num_planks - 1) * plank_gap) / num_planks
    ajar_ang = -0.30
    hinge_facade_pos = Vector((0.03, -door_w * 0.5 + 0.03, z_floor + 0.03))
    door_leaf_mat = (
        Matrix.Translation(Vector((wx, wy, 0.0))) @
        facade_rot_mat @
        Matrix.Translation(hinge_facade_pos) @
        Matrix.Rotation(ajar_ang, 4, 'Z')
    )
    door_leaf_euler = door_leaf_mat.to_euler()
    rot_cyl_x = (door_leaf_mat.to_3x3() @ Matrix.Rotation(1.5707963, 3, 'Y')).to_euler()
    
    for h_rel in [0.20, 0.52, 0.82]:
        hz = z_floor + 0.03 + door_leaf_h * h_rel
        loc_plate = Vector((0.088, -door_w * 0.5 - 0.035, hz))
        world_plate = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_plate.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(0.014, 0.07, 0.065),
            location=world_plate,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.003,
            bevel_segments=2
        )
        for by in [-0.018, 0.018]:
            loc_bolt = loc_plate + Vector((0.008, by, 0.0))
            world_bolt = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_bolt.to_4d()).to_3d()
            create_cylinder(
                bm, radius=0.007, height=0.016, segments=6,
                location=world_bolt,
                rotation=(0.0, 1.5707963, rot_z),
                mat_index=MAT_INDEX_IRON
            )
        loc_arm = Vector((0.055, -door_w * 0.5 + 0.005, hz))
        world_arm = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_arm.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(0.07, 0.024, 0.038),
            location=world_arm,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.003,
            bevel_segments=2
        )
        loc_pin = Vector((0.03, -door_w * 0.5 + 0.03, hz))
        world_pin = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_pin.to_4d()).to_3d()
        create_cylinder(
            bm, radius=0.018, height=0.14, segments=10,
            location=world_pin,
            rotation=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
        loc_pincap = loc_pin + Vector((0.0, 0.0, 0.075))
        world_pincap = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_pincap.to_4d()).to_3d()
        create_cylinder(
            bm, radius=0.011, height=0.025, segments=8,
            location=world_pincap,
            rotation=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
    for k in range(num_planks):
        py = (k + 0.5) * pw + k * plank_gap
        jank = 0.002 * math.sin(k * 2.8 + 1.2)
        local_plank = Vector((jank, py, door_leaf_h * 0.5))
        world_plank = (door_leaf_mat @ local_plank.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(door_thick, pw - 0.002, door_leaf_h),
            location=world_plank,
            rotation=door_leaf_euler,
            mat_index=MAT_INDEX_DOOR,
            bevel_amount=0.008,
            bevel_segments=2
        )
    for bf in [0.20, 0.82]:
        local_bat = Vector((-door_thick * 0.5 - 0.010, door_leaf_w * 0.5, door_leaf_h * bf))
        world_bat = (door_leaf_mat @ local_bat.to_4d()).to_3d()
        create_door_batten(
            bm, size=(0.022, door_leaf_w * 0.92, 0.10),
            location=world_bat,
            rotation=door_leaf_euler,
            mat_index=MAT_INDEX_DOOR,
            bevel_amount=0.004,
            bevel_segments=2
        )
    for h_rel in [0.20, 0.52, 0.82]:
        hz = door_leaf_h * h_rel
        local_socket = Vector((0.0, 0.0, hz))
        world_socket = (door_leaf_mat @ local_socket.to_4d()).to_3d()
        create_cylinder(
            bm, radius=0.022, height=0.09, segments=10,
            location=world_socket,
            rotation=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_IRON
        )
        strap_len = door_leaf_w * 0.80
        strap_x = door_thick * 0.5 + 0.010
        local_strap = Vector((strap_x, strap_len * 0.45, hz))
        world_strap = (door_leaf_mat @ local_strap.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(0.018, strap_len, 0.055),
            location=world_strap,
            rotation=door_leaf_euler,
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.004,
            bevel_segments=2
        )
        for r_frac in [0.22, 0.52, 0.80]:
            local_rv = Vector((strap_x + 0.008, strap_len * r_frac, hz))
            world_rv = (door_leaf_mat @ local_rv.to_4d()).to_3d()
            create_cylinder(
                bm, radius=0.009, height=0.018, segments=6,
                location=world_rv,
                rotation=rot_cyl_x,
                mat_index=MAT_INDEX_IRON
            )
    handle_z = door_leaf_h * 0.48
    handle_y = door_leaf_w * 0.82
    out_x = door_thick * 0.5 + 0.008
    local_esc = Vector((out_x, handle_y, handle_z))
    world_esc = (door_leaf_mat @ local_esc.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(0.014, 0.09, 0.15),
        location=world_esc,
        rotation=door_leaf_euler,
        mat_index=MAT_INDEX_IRON,
        bevel_amount=0.004,
        bevel_segments=2
    )
    for dy, dz in [(-0.028, -0.050), (0.028, -0.050), (-0.028, 0.050), (0.028, 0.050)]:
        local_crv = local_esc + Vector((0.007, dy, dz))
        world_crv = (door_leaf_mat @ local_crv.to_4d()).to_3d()
        create_cylinder(
            bm, radius=0.006, height=0.014, segments=5,
            location=world_crv,
            rotation=rot_cyl_x,
            mat_index=MAT_INDEX_IRON
        )
    local_boss_box = local_esc + Vector((0.012, 0.0, -0.025))
    world_boss_box = (door_leaf_mat @ local_boss_box.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(0.018, 0.045, 0.04),
        location=world_boss_box,
        rotation=door_leaf_euler,
        mat_index=MAT_INDEX_IRON,
        bevel_amount=0.003,
        bevel_segments=2
    )
    local_boss_cyl = local_boss_box + Vector((0.010, 0.0, -0.008))
    world_boss_cyl = (door_leaf_mat @ local_boss_cyl.to_4d()).to_3d()
    create_cylinder(
        bm, radius=0.011, height=0.025, segments=8,
        location=world_boss_cyl,
        rotation=rot_cyl_x,
        mat_index=MAT_INDEX_IRON
    )
    local_ring = local_boss_cyl + Vector((0.009, 0.0, -0.042))
    world_ring = (door_leaf_mat @ local_ring.to_4d()).to_3d()
    create_torus_ring(
        bm, location=world_ring, rotation=rot_cyl_x,
        major_radius=0.048, minor_radius=0.010, major_segments=16, minor_segments=10,
        mat_index=MAT_INDEX_IRON
    )
    in_x = -door_thick * 0.5 - 0.008
    local_in_esc = Vector((in_x, handle_y, handle_z))
    world_in_esc = (door_leaf_mat @ local_in_esc.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(0.014, 0.09, 0.15),
        location=world_in_esc,
        rotation=door_leaf_euler,
        mat_index=MAT_INDEX_IRON,
        bevel_amount=0.004,
        bevel_segments=2
    )
    local_in_boss_cyl = local_in_esc + Vector((-0.014, 0.0, -0.033))
    world_in_boss_cyl = (door_leaf_mat @ local_in_boss_cyl.to_4d()).to_3d()
    create_cylinder(
        bm, radius=0.011, height=0.025, segments=8,
        location=world_in_boss_cyl,
        rotation=rot_cyl_x,
        mat_index=MAT_INDEX_IRON
    )
    local_in_ring = local_in_boss_cyl + Vector((-0.009, 0.0, -0.042))
    world_in_ring = (door_leaf_mat @ local_in_ring.to_4d()).to_3d()
    create_torus_ring(
        bm, location=world_in_ring, rotation=rot_cyl_x,
        major_radius=0.048, minor_radius=0.010, major_segments=16, minor_segments=10,
        mat_index=MAT_INDEX_IRON
    )
