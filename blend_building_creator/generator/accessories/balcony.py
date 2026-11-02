"""
Generic timber balcony.

A jettied deck with curved corbel brackets and a shared-slope railing, plus a
swing-following door leaf. Fully facade-agnostic (driven by ``get_facade_frame``)
so it can decorate any wall of any building.
"""

import math
from mathutils import Vector, Matrix

from ..facade import get_facade_frame
from ..railing import build_railing
from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_torus_ring, create_door_batten,
)
from ..walls import create_curved_corbel
from ..materials import (
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR, MAT_INDEX_IRON,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LANTERN, MAT_INDEX_BANNER,
)
from .banner import build_hanging_banner


def _build_noble_balcony(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                         z_floor, width=6.8, depth=2.2, tier='TIER_3',
                         lower_wall_x_min=None, lower_wall_x_max=None,
                         lower_wall_y_min=None, lower_wall_y_max=None,
                         door_angle_deg=0.0, include_leaf=True,
                         along_wall_offset=0.0, wall_thickness=0.38,
                         has_banners=True):
    """Constructs a grand noble Lord's balcony: wide stepped cut-stone corbel brackets,
    carved oak diagonal brace struts, spacious promenade deck, robust balustrade with
    corner lanterns, double arched French portals, and heraldic dragon banners."""
    wx, wy, ox, oy, tx, ty, rot_z = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    if along_wall_offset != 0.0:
        wx += tx * along_wall_offset
        wy += ty * along_wall_offset
    facade_rot_mat = Matrix.Rotation(rot_z, 4, 'Z')

    def _w(lx, ly, lz=0.0):
        return Vector((wx, wy, z_floor)) + (facade_rot_mat @ Vector((lx, ly, lz, 0.0))).to_3d()

    half_w = width * 0.5
    half_d = depth * 0.5
    wall_half = float(wall_thickness) * 0.5

    # 1. Stepped Cut-Stone Corbels and Heavy Oak Diagonal Braces (5 corbels across the width)
    corbel_ys = [-half_w * 0.82, -half_w * 0.41, 0.0, half_w * 0.41, half_w * 0.82]
    for cy_ in corbel_ys:
        create_beveled_box(
            bm, size=(0.55, 0.34, 0.36),
            location=_w(wall_half + 0.25, cy_, -0.20),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(0.95, 0.34, 0.30),
            location=_w(wall_half + 0.45, cy_, -0.15),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(1.45, 0.34, 0.26),
            location=_w(wall_half + 0.68, cy_, -0.10),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(depth + 0.12, 0.20, 0.22),
            location=_w((depth + wall_half) * 0.5, cy_, -0.09),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.015
        )
        b_x0, b_z0 = wall_half + 0.06, -1.35
        b_x1, b_z1 = depth * 0.72, -0.14
        brace_dx = b_x1 - b_x0
        brace_dz = b_z1 - b_z0
        brace_len = math.hypot(brace_dx, brace_dz)
        brace_pitch = math.atan2(brace_dz, brace_dx)
        brace_mid = _w((b_x0 + b_x1) * 0.5, cy_, (b_z0 + b_z1) * 0.5)
        brace_rot = (facade_rot_mat @ Matrix.Rotation(-brace_pitch, 4, 'Y')).to_euler()
        create_beveled_box(
            bm, size=(brace_len, 0.16, 0.16),
            location=brace_mid,
            rotation=brace_rot,
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )

    # Transverse heavy timber front bearer beam
    create_beveled_box(
        bm, size=(0.20, width + 0.18, 0.24),
        location=_w(depth - 0.06, 0.0, -0.09),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.015
    )

    # 2. Deck & Bullnose Rim Frame
    create_beveled_box(
        bm, size=(depth + 0.08, width + 0.12, 0.08),
        location=_w(depth * 0.5, 0.0, 0.04),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
    )
    create_beveled_box(
        bm, size=(depth + 0.18, width + 0.22, 0.12),
        location=_w(depth * 0.5, 0.0, 0.01),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.016
    )

    # 3. Grand Balustrade
    outer_x = depth + 0.02
    post_h = 1.15
    # Two Front Corner Posts
    for sgn in (-1.0, 1.0):
        py = half_w * sgn
        create_beveled_box(
            bm, size=(0.24, 0.24, post_h),
            location=_w(outer_x, py, post_h * 0.5),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.015
        )
        create_beveled_box(
            bm, size=(0.30, 0.30, 0.10),
            location=_w(outer_x, py, post_h + 0.05),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        lz = post_h + 0.10
        create_cylinder(
            bm, radius=0.045, height=0.08, segments=8,
            location=_w(outer_x, py, lz + 0.04),
            rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_IRON
        )
        create_beveled_box(
            bm, size=(0.22, 0.22, 0.32),
            location=_w(outer_x, py, lz + 0.24),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(0.16, 0.16, 0.24),
            location=_w(outer_x, py, lz + 0.24),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_LANTERN, bevel_amount=0.008
        )
        create_cone(
            bm, radius1=0.18, radius2=0.0, height=0.14, segments=8,
            location=_w(outer_x, py, lz + 0.47),
            rotation=(0.0, 0.0, rot_z), mat_index=MAT_INDEX_IRON
        )

    # Two Wall Anchor Posts
    for sgn in (-1.0, 1.0):
        py = half_w * sgn
        create_beveled_box(
            bm, size=(0.20, 0.20, post_h),
            location=_w(wall_half + 0.12, py, post_h * 0.5),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )

    # Two Intermediate Front Posts
    mid_post_ys = [-half_w * 0.33, half_w * 0.33]
    for mpy in mid_post_ys:
        create_beveled_box(
            bm, size=(0.20, 0.20, 1.10),
            location=_w(outer_x, mpy, 0.55),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        create_beveled_box(
            bm, size=(0.26, 0.26, 0.08),
            location=_w(outer_x, mpy, 1.14),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )

    # Front Railing Runs (3 bays between 4 posts)
    front_stops = [-half_w, mid_post_ys[0], mid_post_ys[1], half_w]
    for bi in range(3):
        y0 = front_stops[bi] + 0.12
        y1 = front_stops[bi + 1] - 0.12
        bay_len = y1 - y0
        bay_cy = (y0 + y1) * 0.5
        create_beveled_box(
            bm, size=(0.12, bay_len, 0.10),
            location=_w(outer_x, bay_cy, 1.00),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.014
        )
        create_beveled_box(
            bm, size=(0.10, bay_len, 0.08),
            location=_w(outer_x, bay_cy, 0.14),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
        n_bal = max(2, int(bay_len / 0.24))
        b_step = bay_len / (n_bal + 1)
        for b_idx in range(1, n_bal + 1):
            by = y0 + b_idx * b_step
            create_beveled_box(
                bm, size=(0.06, 0.06, 0.78),
                location=_w(outer_x, by, 0.57),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
            )

    # Side Return Railings (Left and Right)
    for sgn in (-1.0, 1.0):
        sy = half_w * sgn
        sx0 = wall_half + 0.22
        sx1 = outer_x - 0.12
        side_len = sx1 - sx0
        side_cx = (sx0 + sx1) * 0.5
        create_beveled_box(
            bm, size=(side_len, 0.12, 0.10),
            location=_w(side_cx, sy, 1.00),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.014
        )
        create_beveled_box(
            bm, size=(side_len, 0.10, 0.08),
            location=_w(side_cx, sy, 0.14),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
        n_sbal = max(2, int(side_len / 0.24))
        s_step = side_len / (n_sbal + 1)
        for s_idx in range(1, n_sbal + 1):
            bx = sx0 + s_idx * s_step
            create_beveled_box(
                bm, size=(0.06, 0.06, 0.78),
                location=_w(bx, sy, 0.57),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
            )

    # 4. Heraldic Draped Banners Hanging from Front Railing
    if has_banners:
        for ban_sign in (-1.0, 1.0):
            ban_y = half_w * 0.50 * ban_sign
            ban_wpos = _w(outer_x + 0.08, ban_y, 1.04)
            build_hanging_banner(
                bm, cx=ban_wpos.x, cy=ban_wpos.y, z_top=z_floor + 1.04,
                outward=(ox, oy), width=1.15, height=1.90, wall_offset=0.02
            )

    # 5. Grand Double Arched Portal (1.80m wide x 2.45m high)
    door_w = 1.80
    door_h = 2.45
    frame_d = max(0.36, float(wall_thickness) + 0.06)
    create_beveled_box(
        bm, size=(frame_d, door_w + 0.36, 0.18),
        location=_w(0.0, 0.0, door_h + 0.09),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014
    )
    for dsgn in (-1.0, 1.0):
        dj_y = (door_w * 0.5 + 0.09) * dsgn
        create_beveled_box(
            bm, size=(frame_d, 0.18, door_h),
            location=_w(0.0, dj_y, door_h * 0.5),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014
        )

    if not include_leaf:
        return

    # Paired Door Leaves (Left & Right)
    leaf_w = (door_w - 0.08) * 0.5
    leaf_h = door_h - 0.06
    leaf_th = 0.05
    for dsgn in (-1.0, 1.0):
        hinge_y = (door_w * 0.5 - 0.02) * dsgn
        leaf_cy = hinge_y - dsgn * (leaf_w * 0.5)
        create_beveled_box(
            bm, size=(leaf_th, leaf_w - 0.01, leaf_h),
            location=_w(wall_half + 0.035, leaf_cy, leaf_h * 0.5 + 0.03),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_DOOR, bevel_amount=0.008
        )
        for h_rel in (0.22, 0.52, 0.82):
            strap_z = leaf_h * h_rel + 0.03
            create_beveled_box(
                bm, size=(0.018, leaf_w * 0.82, 0.055),
                location=_w(wall_half + 0.065, leaf_cy + dsgn * (leaf_w * 0.06), strap_z),
                rotation=(0.0, 0.0, rot_z),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.004
            )
        handle_y = hinge_y - dsgn * (leaf_w * 0.80)
        handle_z = leaf_h * 0.48 + 0.03
        create_cylinder(
            bm, radius=0.012, height=0.025, segments=8,
            location=_w(wall_half + 0.075, handle_y, handle_z),
            rotation=(1.5707963, 0.0, rot_z), mat_index=MAT_INDEX_IRON
        )
        create_torus_ring(
            bm, location=_w(wall_half + 0.085, handle_y, handle_z - 0.035),
            rotation=(0.0, 1.5707963, rot_z),
            major_radius=0.045, minor_radius=0.009, major_segments=12, minor_segments=8,
            mat_index=MAT_INDEX_IRON
        )


def build_balcony(bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                  z_floor, width=2.4, depth=1.3, tier='TIER_3',
                  lower_wall_x_min=None, lower_wall_x_max=None,
                  lower_wall_y_min=None, lower_wall_y_max=None,
                  door_angle_deg=0.0, include_leaf=True,
                  along_wall_offset=0.0, wall_thickness=0.30,
                  is_noble=False, has_banners=True):
    if is_noble:
        _build_noble_balcony(
            bm, side, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
            z_floor, width=width, depth=depth, tier=tier,
            lower_wall_x_min=lower_wall_x_min, lower_wall_x_max=lower_wall_x_max,
            lower_wall_y_min=lower_wall_y_min, lower_wall_y_max=lower_wall_y_max,
            door_angle_deg=door_angle_deg, include_leaf=include_leaf,
            along_wall_offset=along_wall_offset, wall_thickness=wall_thickness,
            has_banners=has_banners
        )
        return
    wx, wy, ox, oy, tx, ty, rot_z = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    if along_wall_offset != 0.0:
        wx += tx * along_wall_offset
        wy += ty * along_wall_offset
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
    # The facade frame's local x = 0 is the WALL CENTRELINE.  The old frame was
    # shifted inward and then made very deep, so it stood ~17 cm into the room.
    # Centre it again: wall thickness + 5 cm gives 2.5 cm proud on both the room
    # and balcony sides, with no coplanar wall/frame faces.
    wall_half = float(wall_thickness) * 0.5
    frame_depth = max(0.32, float(wall_thickness) + 0.05)
    fx_center = 0.0
    leaf_x = wall_half + 0.035
    plate_x = wall_half + 0.093
    arm_x = wall_half + 0.060
    pin_x = wall_half + 0.035
    loc_dl = Vector((fx_center, 0.0, z_floor + door_h + 0.06))
    world_dl = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dl.to_4d()).to_3d()
    create_beveled_box(
        bm, size=(frame_depth, door_w + 0.20, 0.12),
        location=world_dl,
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )
    for d_sign in [-1, 1]:
        loc_dj = Vector((fx_center, (door_w * 0.5 + 0.06) * d_sign, z_floor + door_h * 0.5))
        world_dj = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_dj.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(frame_depth, 0.12, door_h),
            location=world_dj,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    if not include_leaf:
        return

    door_leaf_w = door_w - 0.06
    door_leaf_h = door_h - 0.06
    num_planks = 4
    plank_gap = 0.004
    pw = (door_leaf_w - (num_planks - 1) * plank_gap) / num_planks
    # Balcony door leaf swing follows the main Door Open Angle (0 = shut).
    ajar_ang = -math.radians(max(0.0, min(110.0, door_angle_deg)))
    hinge_facade_pos = Vector((leaf_x, -door_w * 0.5 + 0.03, z_floor + 0.03))
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
        loc_plate = Vector((plate_x, -door_w * 0.5 - 0.035, hz))
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
        loc_arm = Vector((arm_x, -door_w * 0.5 + 0.005, hz))
        world_arm = Vector((wx, wy, 0.0)) + (facade_rot_mat @ loc_arm.to_4d()).to_3d()
        create_beveled_box(
            bm, size=(0.07, 0.024, 0.038),
            location=world_arm,
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.003,
            bevel_segments=2
        )
        loc_pin = Vector((pin_x, -door_w * 0.5 + 0.03, hz))
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
