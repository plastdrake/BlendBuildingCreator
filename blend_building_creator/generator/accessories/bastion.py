"""Reusable fortified corner bastion towers with hollow interiors and crenellated merlons.

Based on fortress/citadel architecture:
- Straight masonry base with the same cut-stone plinth band as the curtain wall
  (the old flared talus did not line up with the wall and left a seam at the
  inside corner).
- Real walk-in hollow interior chamber with plank upper floor/ceiling and a
  timber-framed hatch the access ladder climbs through, plus a wall torch.
- Open arched courtyard entrance doorway with an inward-swung heavy timber door leaf (no palisade conflict).
- Chamfered quoin corners and horizontal string courses to eliminate blockiness.
- Real window slits (arrow loops): genuine through-holes cut into the shaft and
  dressed with cut-stone reveals, so the dark chamber is visible through them.
- Stepped stone corbels and machicolation brackets.
- Open rooftop stone platform (fighting deck) surrounded by crenellated merlons with coping caps (no roof).
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..walls import build_wall_with_opening
from ..openings import build_arrow_slit
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_IRON, MAT_INDEX_WOOD, MAT_INDEX_FLOOR,
)
from .palisade import (
    compound_bounds, fortification_offset, fortification_depth_extra,
)


def build_bastion_tower(bm, x, y, z_ground=0.0, base_size=3.2, height=8.2,
                        roof_style='MERLONS',
                        mat_index=MAT_INDEX_STONE, door_dir=(0.0, 1.0),
                        trim_mat=None, door_shift=0.0, door_push=0.03,
                        is_grand=False):
    """A heavy fortified bastion tower with walk-in hollow interior, courtyard entrance,
    open rooftop platform with crenellated merlons, and chamfered quoin corners.
    Supports wooden towers (Tier 2) and stone towers (Tier 3).
    """
    if trim_mat is None:
        trim_mat = MAT_INDEX_TIMBER if mat_index == MAT_INDEX_WOOD else MAT_INDEX_CUT_STONE
    deck_mat = MAT_INDEX_WOOD if mat_index == MAT_INDEX_WOOD else MAT_INDEX_CUT_STONE
    half_s = base_size * 0.5
    wall_t = 0.38
    int_half = max(0.6, half_s - wall_t)

    # Normalize door direction (points towards courtyard entrance)
    ddx, ddy = door_dir
    d_len = math.hypot(ddx, ddy)
    if d_len < 1e-4:
        ddx, ddy = 0.0, 1.0
    else:
        ddx, ddy = ddx / d_len, ddy / d_len

    # Local coordinate basis relative to tower orientation:
    # d_fwd: points toward courtyard / doorway (+ly)
    # d_right: horizontal tangent across doorway (+lx)
    # d_up: vertical height (Z)
    d_fwd = Vector((ddx, ddy, 0.0))
    d_right = Vector((-ddy, ddx, 0.0))
    d_up = Vector((0.0, 0.0, 1.0))
    door_yaw = math.atan2(ddy, ddx) - math.pi * 0.5

    def to_world(lx, ly, lz):
        return Vector((x, y, z_ground)) + d_right * lx + d_fwd * ly + d_up * lz

    deck_lz = height - 1.20
    deck_z = z_ground + deck_lz

    # -----------------------------------------------------------------------
    # 1. Straight Masonry Base matching the Curtain Wall
    # -----------------------------------------------------------------------
    # The old flared talus (battered base) never lined up with the curtain
    # wall's straight plinth and left an open seam at the inside corner, so the
    # shaft now rises straight from grade wearing the same cut-stone plinth.
    corner_signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    plinth_h = 0.45
    uv_layer = bm.loops.layers.uv.verify()

    base_v = [bm.verts.new(to_world(s_x * half_s, s_y * half_s, 0.0))
              for s_x, s_y in corner_signs]
    f_bot = bm.faces.new(base_v)
    f_bot.material_index = mat_index
    for lp in f_bot.loops:
        lp[uv_layer].uv = Vector((lp.vert.co.x * 0.5, lp.vert.co.y * 0.5))

    # Cut-stone plinth band (0.17 proud) wrapping all four faces, broken across
    # the doorway on the courtyard face exactly like the wall plinth is broken
    # across the gate. Every strip is run *past* the corner by pl_t so the four
    # strips overlap in solid 0.34 x 0.34 corner blocks: separate strips that
    # only just met at the corners left a notch of bare masonry showing.
    pl_t = 0.34
    pl_reach = half_s + pl_t
    for lx, ly, sx, sy in ((0.0, -half_s, base_size + pl_t * 2.0, pl_t),
                           (-half_s, 0.0, pl_t, base_size + pl_t * 2.0),
                           (half_s, 0.0, pl_t, base_size + pl_t * 2.0)):
        pf = create_beveled_box(bm, size=(sx, sy, plinth_h),
                                location=to_world(lx, ly, plinth_h * 0.5),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.02)
        for f in pf:
            f.tag = False
    door_w_pl = 1.05
    door_x0_pl = max(-pl_reach, door_shift - door_w_pl * 0.5)
    door_x1_pl = min(pl_reach, door_shift + door_w_pl * 0.5)
    # Left plinth span from -pl_reach to door_x0_pl
    w_pl_left = door_x0_pl - (-pl_reach)
    if w_pl_left > 0.05:
        c_pl_left = (-pl_reach + door_x0_pl) * 0.5
        pf = create_beveled_box(bm, size=(w_pl_left, pl_t, plinth_h),
                                location=to_world(c_pl_left, half_s, plinth_h * 0.5),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.02)
        for f in pf: f.tag = False
    # Right plinth span from door_x1_pl to +pl_reach
    w_pl_right = pl_reach - door_x1_pl
    if w_pl_right > 0.05:
        c_pl_right = (door_x1_pl + pl_reach) * 0.5
        pf = create_beveled_box(bm, size=(w_pl_right, pl_t, plinth_h),
                                location=to_world(c_pl_right, half_s, plinth_h * 0.5),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.02)
        for f in pf: f.tag = False

    # -----------------------------------------------------------------------
    # 2. Real Hollow Walk-In Interior Chamber & 4 Walls
    # -----------------------------------------------------------------------
    # Heavy ceiling timber joists overhead inside the chamber
    joist_lz = 2.85
    for j_off in (-0.70, 0.0, 0.70):
        jf = create_beveled_box(bm, size=(int_half * 2.0, 0.16, 0.14),
                                location=to_world(0.0, j_off, joist_lz),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        for f in jf:
            f.tag = True

    # Plank upper floor/ceiling over the joists with a hatch the ladder climbs
    # through, so the ladder reads as rising into a hole rather than a solid slab.
    floor_lz = joist_lz + 0.14
    floor_t = 0.07
    hole_c_lx = int_half * 0.50
    hole_c_ly = -int_half * 0.55
    hole_half = 0.38
    ih = int_half
    floor_segs = [
        (-ih, hole_c_lx - hole_half, -ih, ih),
        (hole_c_lx + hole_half, ih, -ih, ih),
        (hole_c_lx - hole_half, hole_c_lx + hole_half, hole_c_ly + hole_half, ih),
        (hole_c_lx - hole_half, hole_c_lx + hole_half, -ih, hole_c_ly - hole_half),
    ]
    for lx0, lx1, ly0, ly1 in floor_segs:
        if lx1 - lx0 < 0.02 or ly1 - ly0 < 0.02:
            continue
        ff = create_beveled_box(bm, size=(lx1 - lx0, ly1 - ly0, floor_t),
                                location=to_world((lx0 + lx1) * 0.5,
                                                  (ly0 + ly1) * 0.5, floor_lz),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_FLOOR, bevel_amount=0.006)
        for f in ff:
            f.tag = True

    # Timber frame ringing the hatch opening.
    fr_t = 0.11
    fr_h = 0.10
    fr_z = floor_lz + floor_t * 0.5 + fr_h * 0.5
    for flx, fly, fsx, fsy in (
            (hole_c_lx, hole_c_ly - hole_half - fr_t * 0.5, hole_half * 2.0 + fr_t * 2.0, fr_t),
            (hole_c_lx, hole_c_ly + hole_half + fr_t * 0.5, hole_half * 2.0 + fr_t * 2.0, fr_t),
            (hole_c_lx - hole_half - fr_t * 0.5, hole_c_ly, fr_t, hole_half * 2.0),
            (hole_c_lx + hole_half + fr_t * 0.5, hole_c_ly, fr_t, hole_half * 2.0)):
        ffr = create_beveled_box(bm, size=(fsx, fsy, fr_h),
                                 location=to_world(flx, fly, fr_z),
                                 rotation=(0.0, 0.0, door_yaw),
                                 mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
        for f in ffr:
            f.tag = True


    shaft_bot_lz = 0.0
    shaft_wall_h = deck_lz - shaft_bot_lz

    # Window-slit schedule: two real through-slits per exterior face, placed
    # above the interior joists and clear of the string courses. The wall builder
    # cuts the apertures; ``slit_specs`` remembers where to dress each one into a
    # cut-stone arrow loop afterwards.
    slit_w, slit_h = 0.18, 0.92
    slit_zs = [shaft_bot_lz + shaft_wall_h * 0.32,
               shaft_bot_lz + shaft_wall_h * 0.66]
    slit_specs = []  # (local_lx, local_ly, z, outward_normal)

    def _slit_ops(u_center):
        return [{'u_start': u_center - slit_w * 0.5, 'u_end': u_center + slit_w * 0.5,
                 'z_start': z - slit_h * 0.5, 'z_end': z + slit_h * 0.5}
                for z in slit_zs]

    def _wall_line(lx_a, ly_a, lx_b, ly_b):
        pa = to_world(lx_a, ly_a, 0.0)
        pb = to_world(lx_b, ly_b, 0.0)
        return (pa.x, pa.y), (pb.x, pb.y)

    # Rear Exterior Wall (-ly)
    _rear_y = -half_s + wall_t * 0.5
    p0, p1 = _wall_line(-half_s, _rear_y, half_s, _rear_y)
    build_wall_with_opening(bm, p0, p1, shaft_bot_lz, deck_lz, wall_t,
                            _slit_ops(base_size * 0.5), mat_ext=mat_index,
                            normal_vec=(-d_fwd.x, -d_fwd.y), tier='TIER_3',
                            physical_siding=False)
    for z in slit_zs:
        slit_specs.append((0.0, _rear_y, z, (-d_fwd.x, -d_fwd.y)))

    # Left Exterior Wall (-lx)
    lw_len = base_size - 2.0 * wall_t
    _lx = -half_s + wall_t * 0.5
    p0, p1 = _wall_line(_lx, -lw_len * 0.5, _lx, lw_len * 0.5)
    build_wall_with_opening(bm, p0, p1, shaft_bot_lz, deck_lz, wall_t,
                            _slit_ops(lw_len * 0.5), mat_ext=mat_index,
                            normal_vec=(-d_right.x, -d_right.y), tier='TIER_3',
                            physical_siding=False)
    for z in slit_zs:
        slit_specs.append((_lx, 0.0, z, (-d_right.x, -d_right.y)))

    # Right Exterior Wall (+lx)
    _rx = half_s - wall_t * 0.5
    p0, p1 = _wall_line(_rx, -lw_len * 0.5, _rx, lw_len * 0.5)
    build_wall_with_opening(bm, p0, p1, shaft_bot_lz, deck_lz, wall_t,
                            _slit_ops(lw_len * 0.5), mat_ext=mat_index,
                            normal_vec=(d_right.x, d_right.y), tier='TIER_3',
                            physical_siding=False)
    for z in slit_zs:
        slit_specs.append((_rx, 0.0, z, (d_right.x, d_right.y)))

    # Courtyard Wall (+ly) with real walk-in entrance opening:
    door_w = 1.05
    door_h = 2.15
    door_cz = door_h * 0.5
    door_x0 = max(-half_s, door_shift - door_w * 0.5)
    door_x1 = min(half_s, door_shift + door_w * 0.5)

    # Left door jamb wall segment (from local x = -half_s to door_x0)
    w_jamb_left = door_x0 - (-half_s)
    if w_jamb_left > 0.02:
        c_jamb_left = (-half_s + door_x0) * 0.5
        left_jamb_pos = to_world(c_jamb_left, half_s - wall_t * 0.5, door_cz)
        lj_f = create_beveled_box(bm, size=(w_jamb_left, wall_t, door_h),
                                  location=left_jamb_pos, rotation=(0.0, 0.0, door_yaw),
                                  mat_index=mat_index, bevel_amount=0.02)
        for f in lj_f:
            f.tag = False

    # Right door jamb wall segment (from local x = door_x1 to +half_s)
    w_jamb_right = half_s - door_x1
    if w_jamb_right > 0.02:
        c_jamb_right = (door_x1 + half_s) * 0.5
        right_jamb_pos = to_world(c_jamb_right, half_s - wall_t * 0.5, door_cz)
        rj_f = create_beveled_box(bm, size=(w_jamb_right, wall_t, door_h),
                                  location=right_jamb_pos, rotation=(0.0, 0.0, door_yaw),
                                  mat_index=mat_index, bevel_amount=0.02)
        for f in rj_f:
            f.tag = False

    # Upper wall above the door lintel, carrying one courtyard-facing slit.
    upper_wall_h = deck_lz - door_h
    _cw_y = half_s - wall_t * 0.5
    _cw_lz = (door_h + deck_lz) * 0.5
    _cw_ops = [{'u_start': base_size * 0.5 - slit_w * 0.5,
                'u_end': base_size * 0.5 + slit_w * 0.5,
                'z_start': _cw_lz - slit_h * 0.5, 'z_end': _cw_lz + slit_h * 0.5}]
    p0, p1 = _wall_line(-half_s, _cw_y, half_s, _cw_y)
    build_wall_with_opening(bm, p0, p1, door_h, deck_lz, wall_t, _cw_ops,
                            mat_ext=mat_index, normal_vec=(d_fwd.x, d_fwd.y),
                            tier='TIER_3', physical_siding=False)
    slit_specs.append((0.0, _cw_y, _cw_lz, (d_fwd.x, d_fwd.y)))

    # -----------------------------------------------------------------------
    # 3. Arched Doorway Trimmings & Open Inward Timber Door Leaf
    # -----------------------------------------------------------------------
    door_front_y = half_s
    # The stone casing frames the wall opening. It is seated into the wall
    # so it stands only slightly proud (+0.03m to +0.05m) of the masonry instead
    # of jutting far out into the courtyard.
    casing_y = half_s - wall_t * 0.5 + door_push

    # Threshold step at ground level
    th_f = create_beveled_box(bm, size=(door_w + 0.24, wall_t + 0.12, 0.14),
                             location=to_world(door_shift, casing_y + 0.04, 0.07),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=trim_mat, bevel_amount=0.015)
    for f in th_f:
        f.tag = False

    # Heavy jamb pilasters framing the opening (flush with masonry)
    for s_j in (-1.0, 1.0):
        jx = door_shift + s_j * (door_w * 0.5 + 0.09)
        jamb_f = create_beveled_box(bm, size=(0.18, wall_t + 0.06, door_h),
                                   location=to_world(jx, casing_y, door_cz),
                                   rotation=(0.0, 0.0, door_yaw),
                                   mat_index=trim_mat, bevel_amount=0.015)
        for f in jamb_f:
            f.tag = False

    # Heavy arched lintel header above door
    lintel_f = create_beveled_box(bm, size=(door_w + 0.36, wall_t + 0.08, 0.28),
                                 location=to_world(door_shift, casing_y + 0.01, door_h + 0.14),
                                 rotation=(0.0, 0.0, door_yaw),
                                 mat_index=trim_mat, bevel_amount=0.02)
    for f in lintel_f:
        f.tag = False

    # Timber reveal casing lining the doorway aperture (hollow frame, not a solid plug)
    cas_t = 0.035
    # Left casing lining
    l_cas = create_beveled_box(bm, size=(cas_t, wall_t, door_h),
                              location=to_world(door_shift - door_w * 0.5 + cas_t * 0.5, half_s - wall_t * 0.5, door_cz),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in l_cas: f.tag = True
    # Right casing lining
    r_cas = create_beveled_box(bm, size=(cas_t, wall_t, door_h),
                              location=to_world(door_shift + door_w * 0.5 - cas_t * 0.5, half_s - wall_t * 0.5, door_cz),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in r_cas: f.tag = True
    # Head casing lining
    h_cas = create_beveled_box(bm, size=(door_w, wall_t, cas_t),
                              location=to_world(door_shift, half_s - wall_t * 0.5, door_h - cas_t * 0.5),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in h_cas: f.tag = True

    # Heavy timber door leaf swung OPEN into the chamber (revealing the hollow interior)
    door_leaf_w = door_w - 0.08
    door_leaf_h = door_h - 0.08
    door_leaf_t = 0.055
    open_angle = math.radians(72.0)  # swung inward towards the left inner wall

    # Hinge location at left inner casing corner (follows the shifted opening)
    hinge_lx = door_shift - door_w * 0.5 + 0.06
    hinge_ly = half_s - wall_t + 0.05
    # Center of swung door leaf
    dl_cx = hinge_lx + math.cos(open_angle) * (door_leaf_w * 0.5)
    dl_cy = hinge_ly - math.sin(open_angle) * (door_leaf_w * 0.5)
    dl_rot = (0.0, 0.0, door_yaw + open_angle)

    d_leaf = create_beveled_box(bm, size=(door_leaf_w, door_leaf_t, door_leaf_h),
                               location=to_world(dl_cx, dl_cy, 0.06 + door_leaf_h * 0.5),
                               rotation=dl_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    for f in d_leaf: f.tag = True

    # Iron strap hinges on the open door leaf
    for h_z in (0.45, door_leaf_h - 0.35):
        sh_f = create_beveled_box(bm, size=(door_leaf_w * 0.75, door_leaf_t + 0.02, 0.065),
                                 location=to_world(dl_cx - math.cos(open_angle) * 0.08,
                                                   dl_cy + math.sin(open_angle) * 0.08,
                                                   0.06 + h_z),
                                 rotation=dl_rot, mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
        for f in sh_f: f.tag = True

    # -----------------------------------------------------------------------
    # 4. Interior Furnishings (Access Ladder & Wall Torch)
    # -----------------------------------------------------------------------
    lad_bottom = to_world(hole_c_lx + 0.24, hole_c_ly + int_half * 0.72, 0.02)
    lad_top = to_world(hole_c_lx, hole_c_ly, floor_lz + 0.50)
    lad_vec = lad_top - lad_bottom
    lad_len = lad_vec.length
    lad_mid = (lad_bottom + lad_top) * 0.5
    lad_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(lad_vec.normalized()).to_euler()

    for s_rail in (-0.20, 0.20):
        rail_offset = d_right * s_rail
        r_f = create_beveled_box(bm, size=(0.05, 0.08, lad_len),
                                location=lad_mid + rail_offset, rotation=lad_rot,
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
        for f in r_f: f.tag = True

    # Ladder rungs
    n_rungs = 7
    for ir in range(1, n_rungs):
        t_r = ir / n_rungs
        rung_loc = lad_bottom + lad_vec * t_r
        rung_f = create_cylinder(bm, radius=0.016, height=0.40, segments=6,
                                 location=rung_loc, rotation=(0.0, 1.5708, door_yaw),
                                 mat_index=MAT_INDEX_WOOD)
        for f in rung_f: f.tag = True

    # Iron wall torch bracket on interior left wall
    torch_loc = to_world(-int_half + 0.08, 0.0, 1.65)
    t_brk = create_beveled_box(bm, size=(0.14, 0.05, 0.16), location=torch_loc,
                               rotation=(0.0, 0.0, door_yaw), mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    for f in t_brk: f.tag = True
    torch_shaft = create_cylinder(bm, radius=0.022, height=0.36, segments=6,
                                  location=torch_loc + d_right * 0.06 + d_up * 0.10,
                                  rotation=(0.0, 0.0, door_yaw), mat_index=MAT_INDEX_TIMBER)
    for f in torch_shaft: f.tag = True

    # -----------------------------------------------------------------------
    # 5. Softening Blockiness: Chamfered Quoin Corners & String Courses
    # -----------------------------------------------------------------------
    # Stacked alternating quoin blocks along the 4 vertical corners
    quoin_step = 0.65
    n_quoins = max(3, int(shaft_wall_h / quoin_step))
    for i_q in range(n_quoins):
        q_z = shaft_bot_lz + 0.30 + i_q * quoin_step
        if q_z > deck_lz - 0.40:
            break
        for s_x, s_y in corner_signs:
            qw = 0.42 if (i_q % 2 == 0) else 0.30
            qd = 0.30 if (i_q % 2 == 0) else 0.42
            q_loc = to_world(s_x * (half_s - qw * 0.45), s_y * (half_s - qd * 0.45), q_z)
            q_faces = create_beveled_box(bm, size=(qw, qd, 0.30), location=q_loc,
                                         rotation=(0.0, 0.0, door_yaw),
                                         mat_index=trim_mat, bevel_amount=0.018)
            for f in q_faces:
                f.tag = False

    # Mid-height drip stringer course (water table)
    mid_lz = shaft_bot_lz + shaft_wall_h * 0.46
    mid_belt = create_beveled_box(bm, size=(base_size + 0.12, base_size + 0.12, 0.12),
                                  location=to_world(0.0, 0.0, mid_lz),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.015)
    for f in mid_belt:
        f.tag = False

    # -----------------------------------------------------------------------
    # 6. Real Window Slits: reveals dressing the through-holes
    # -----------------------------------------------------------------------
    for lx, ly, lz, out_n in slit_specs:
        c = to_world(lx, ly, lz)
        build_arrow_slit(bm, center=(c.x, c.y, c.z), normal_axis=out_n,
                         wall_thickness=wall_t, slit_w=slit_w, slit_h=slit_h,
                         mat_index=trim_mat, has_transom=True)

    # -----------------------------------------------------------------------
    # 7. Stepped Corbels & Open Rooftop Platform (Fighting Deck)
    # -----------------------------------------------------------------------
    # Tier 1 stepped corbel course
    c1_lz = deck_lz - 0.22
    c1_f = create_beveled_box(bm, size=(base_size + 0.24, base_size + 0.24, 0.18),
                             location=to_world(0.0, 0.0, c1_lz),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=trim_mat, bevel_amount=0.025)
    for f in c1_f:
        f.tag = False

    # Tier 2 projecting corbel course
    c2_lz = deck_lz - 0.06
    c2_f = create_beveled_box(bm, size=(base_size + 0.44, base_size + 0.44, 0.18),
                             location=to_world(0.0, 0.0, c2_lz),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=trim_mat, bevel_amount=0.025)
    for f in c2_f:
        f.tag = False

    # Individual cantilevered machicolation brackets under the overhang
    b_offsets = [-0.95, 0.0, 0.95]
    for b_off in b_offsets:
        bk_f1 = create_beveled_box(bm, size=(0.22, 0.32, 0.38),
                                  location=to_world(b_off, -half_s - 0.06, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.015)
        for f in bk_f1: f.tag = False
        bk_f2 = create_beveled_box(bm, size=(0.22, 0.32, 0.38),
                                  location=to_world(b_off, half_s + 0.06, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.015)
        for f in bk_f2: f.tag = False
        bk_f3 = create_beveled_box(bm, size=(0.32, 0.22, 0.38),
                                  location=to_world(-half_s - 0.06, b_off, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.015)
        for f in bk_f3: f.tag = False
        bk_f4 = create_beveled_box(bm, size=(0.32, 0.22, 0.38),
                                  location=to_world(half_s + 0.06, b_off, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.015)
        for f in bk_f4: f.tag = False

    if is_grand:
        # Sculpted stone arches spanning between adjacent machicolation brackets
        for i_b in range(len(b_offsets) - 1):
            b0, b1 = b_offsets[i_b], b_offsets[i_b + 1]
            b_mid = (b0 + b1) * 0.5
            b_span = abs(b1 - b0)
            for s_face in (-1.0, 1.0):
                af1 = create_beveled_box(bm, size=(b_span - 0.16, 0.22, 0.14),
                                         location=to_world(b_mid, s_face * (half_s + 0.05), c1_lz - 0.03),
                                         rotation=(0.0, 0.0, door_yaw),
                                         mat_index=trim_mat, bevel_amount=0.015)
                for f in af1: f.tag = False
                af2 = create_beveled_box(bm, size=(0.22, b_span - 0.16, 0.14),
                                         location=to_world(s_face * (half_s + 0.05), b_mid, c1_lz - 0.03),
                                         rotation=(0.0, 0.0, door_yaw),
                                         mat_index=trim_mat, bevel_amount=0.015)
                for f in af2: f.tag = False

    # Open rooftop fighting deck platform (open to sky - NO ROOF)
    deck_slab_pos = to_world(0.0, 0.0, deck_lz + 0.07)
    plat_w = base_size + 0.44
    d_f = create_beveled_box(bm, size=(plat_w, plat_w, 0.14),
                            location=deck_slab_pos,
                            rotation=(0.0, 0.0, door_yaw),
                            mat_index=deck_mat, bevel_amount=0.02)
    for f in d_f:
        f.tag = False

    # Rooftop timber hatch / trapdoor to interior stairwell
    hatch_f = create_beveled_box(bm, size=(0.88, 0.88, 0.08),
                                location=to_world(0.0, 0.0, deck_lz + 0.16),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    for f in hatch_f:
        f.tag = True
    for h_off in (-0.28, 0.28):
        hf = create_beveled_box(bm, size=(0.10, 0.65, 0.025),
                               location=to_world(h_off, 0.0, deck_lz + 0.21),
                               rotation=(0.0, 0.0, door_yaw),
                               mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
        for f in hf:
            f.tag = True

    # -----------------------------------------------------------------------
    # 8. Fortified Crenellated Merlons with Coping Caps
    # -----------------------------------------------------------------------
    half_p = plat_w * 0.5
    merlon_h = 0.72
    merlon_t = 0.26
    merlon_cz = deck_lz + 0.14 + merlon_h * 0.5

    # 4 massive corner merlon piers
    corner_inset = half_p - merlon_t * 0.85
    for s_x, s_y in corner_signs:
        cp_pos = to_world(s_x * corner_inset, s_y * corner_inset, merlon_cz)
        cpf = create_beveled_box(bm, size=(merlon_t * 1.7, merlon_t * 1.7, merlon_h),
                                location=cp_pos, rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.015)
        for f in cpf:
            f.tag = False
        cap_f = create_beveled_box(bm, size=(merlon_t * 1.9, merlon_t * 1.9, 0.09),
                                  location=cp_pos + d_up * (merlon_h * 0.5 + 0.045),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=trim_mat, bevel_amount=0.018)
        for f in cap_f:
            f.tag = False

        if is_grand:
            # Tapered cut-stone pyramidal spire pinnacle crowning each corner merlon
            pin_h = 0.85
            pin_r = merlon_t * 1.15
            pin_loc = cp_pos + d_up * (merlon_h * 0.5 + 0.09 + pin_h * 0.5)
            pin_f = create_cone(bm, radius1=pin_r, radius2=0.02, height=pin_h, segments=4,
                                location=pin_loc,
                                rotation=(0.0, 0.0, door_yaw + math.pi * 0.25),
                                mat_index=trim_mat)
            for f in pin_f: f.tag = False
            # Iron collar & decorative spearhead spire finial atop pinnacle
            fin_loc = cp_pos + d_up * (merlon_h * 0.5 + 0.09 + pin_h + 0.16)
            fin_f = create_cylinder(bm, radius=0.022, height=0.34, segments=8,
                                    location=fin_loc, mat_index=MAT_INDEX_IRON)
            for f in fin_f: f.tag = True
            fin_cone = create_cone(bm, radius1=0.05, radius2=0.0, height=0.18, segments=8,
                                   location=fin_loc + d_up * 0.17, mat_index=MAT_INDEX_IRON)
            for f in fin_cone: f.tag = True

    # Intermediate merlons with embrasure firing gaps along the 4 edges
    m_edge_inset = half_p - merlon_t * 0.5
    im_w = 0.50
    im_offsets = [-0.55, 0.55]

    for im_x in im_offsets:
        # Rear edge merlons (-ly)
        m1_pos = to_world(im_x, -m_edge_inset, merlon_cz)
        mf1 = create_beveled_box(bm, size=(im_w, merlon_t, merlon_h), location=m1_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.012)
        for f in mf1: f.tag = False
        c1 = create_beveled_box(bm, size=(im_w + 0.08, merlon_t + 0.08, 0.08),
                                location=m1_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.015)
        for f in c1: f.tag = False

        # Front edge merlons (+ly)
        m2_pos = to_world(im_x, m_edge_inset, merlon_cz)
        mf2 = create_beveled_box(bm, size=(im_w, merlon_t, merlon_h), location=m2_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.012)
        for f in mf2: f.tag = False
        c2 = create_beveled_box(bm, size=(im_w + 0.08, merlon_t + 0.08, 0.08),
                                location=m2_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.015)
        for f in c2: f.tag = False

        # Left edge merlons (-lx)
        m3_pos = to_world(-m_edge_inset, im_x, merlon_cz)
        mf3 = create_beveled_box(bm, size=(merlon_t, im_w, merlon_h), location=m3_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.012)
        for f in mf3: f.tag = False
        c3 = create_beveled_box(bm, size=(merlon_t + 0.08, im_w + 0.08, 0.08),
                                location=m3_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.015)
        for f in c3: f.tag = False

        # Right edge merlons (+lx)
        m4_pos = to_world(m_edge_inset, im_x, merlon_cz)
        mf4 = create_beveled_box(bm, size=(merlon_t, im_w, merlon_h), location=m4_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.012)
        for f in mf4: f.tag = False
        c4 = create_beveled_box(bm, size=(merlon_t + 0.08, im_w + 0.08, 0.08),
                                location=m4_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=trim_mat, bevel_amount=0.015)
        for f in c4: f.tag = False

    if is_grand:
        try:
            from .banner import build_banner_pole
            banner_loc = to_world(0.0, -m_edge_inset, merlon_cz + merlon_h * 0.5)
            build_banner_pole(bm, banner_loc.x, banner_loc.y, banner_loc.z,
                              height=2.8, flag_len=1.1, flag_h=0.7, flag_dir=(-d_fwd.x, -d_fwd.y))
        except Exception:
            pass

        try:
            from .shield import build_round_shield
            sh_z = shaft_bot_lz + shaft_wall_h * 0.78
            # Rear outward face
            sh_rear = to_world(0.0, -half_s - 0.04, sh_z)
            build_round_shield(bm, (sh_rear.x, sh_rear.y, sh_rear.z),
                               normal=(-d_fwd.x, -d_fwd.y, 0.0), radius=0.44)
            # Flank outward faces
            sh_left = to_world(-half_s - 0.04, 0.0, sh_z)
            build_round_shield(bm, (sh_left.x, sh_left.y, sh_left.z),
                               normal=(-d_right.x, -d_right.y, 0.0), radius=0.44)
            sh_right = to_world(half_s + 0.04, 0.0, sh_z)
            build_round_shield(bm, (sh_right.x, sh_right.y, sh_right.z),
                               normal=(d_right.x, d_right.y, 0.0), radius=0.44)
        except Exception:
            pass


def build_rickety_frame_tower(bm, x, y, z_ground=0.0, base_size=3.2, height=8.2,
                              door_dir=(0.0, 1.0)):
    """A rickety open-timber watchtower for palisade (wood-tier) forts.

    Freestanding battered frame in the spirit of a classic timber lookout:
    splayed corner posts on stone footings, girt levels with X-cross braces
    on every face, an overhanging railed deck, a plank watch-hut with a
    pitched roof, round shields, and a full-height exterior ladder with
    horizontal rungs. No masonry shaft, no merlons, no arrow slits.

    Tilted members use exact ``rotation_difference`` orientation (Euler order
    cannot express yaw-then-pitch), so braces and rungs are correct on every
    facing.
    """
    import random
    from .shield import build_round_shield
    half_b = base_size * 0.5
    half_t = half_b - 0.55
    deck_lz = height - 2.40
    rng = random.Random((int(round(x * 13.7)) * 73856093) ^ (int(round(y * 13.7)) * 19349663))

    ddx, ddy = door_dir
    d_len = math.hypot(ddx, ddy) or 1.0
    ddx, ddy = ddx / d_len, ddy / d_len
    d_fwd = Vector((ddx, ddy, 0.0))
    d_right = Vector((-ddy, ddx, 0.0))
    d_up = Vector((0.0, 0.0, 1.0))
    door_yaw = math.atan2(ddy, ddx) - math.pi * 0.5
    zup = Vector((0.0, 0.0, 1.0))

    def to_world(lx, ly, lz):
        return Vector((x, y, z_ground)) + d_right * lx + d_fwd * ly + d_up * lz

    def _beam(p0, p1, thick, mat, bevel=0.008, tag=True):
        """One timber between two local points, exactly oriented."""
        v0, v1 = to_world(*p0), to_world(*p1)
        dv = v1 - v0
        ln = max(dv.length, 0.05)
        e = zup.rotation_difference(dv.normalized()).to_euler()
        bf = create_beveled_box(bm, size=(thick, thick, ln),
                                location=(v0 + v1) * 0.5,
                                rotation=(e.x, e.y, e.z),
                                mat_index=mat, bevel_amount=bevel)
        for f in bf:
            f.tag = tag
        return bf

    def _hbox(sx, sy, sz, loc, mat, bevel=0.010, tag=True):
        hf = create_beveled_box(bm, size=(sx, sy, sz),
                                location=to_world(*loc),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=mat, bevel_amount=bevel)
        for f in hf:
            f.tag = tag
        return hf

    def _half(z):
        return half_b + (half_t - half_b) * (z / deck_lz)

    # -- Stone footings + 4 battered corner posts --------------------------------
    for s_x in (-1.0, 1.0):
        for s_y in (-1.0, 1.0):
            _hbox(0.55, 0.55, 0.35, (s_x * half_b, s_y * half_b, 0.17),
                  MAT_INDEX_STONE, bevel=0.02, tag=False)
            _beam((s_x * half_b, s_y * half_b, 0.25),
                  (s_x * (half_t + rng.uniform(-0.03, 0.03)),
                   s_y * (half_t + rng.uniform(-0.03, 0.03)), deck_lz),
                  0.17, MAT_INDEX_TIMBER, bevel=0.012)

    # -- Girt levels ---------------------------------------------------------------
    levels = [deck_lz * 0.36 + rng.uniform(-0.06, 0.06),
              deck_lz * 0.62 + rng.uniform(-0.06, 0.06),
              deck_lz * 0.87]
    for lz in levels:
        h = _half(lz)
        _hbox(h * 2.0 + 0.13, 0.13, 0.13, (0.0, h, lz), MAT_INDEX_TIMBER)
        _hbox(h * 2.0 + 0.13, 0.13, 0.13, (0.0, -h, lz), MAT_INDEX_TIMBER)
        _hbox(0.13, h * 2.0 + 0.13, 0.13, (h, 0.0, lz), MAT_INDEX_TIMBER)
        _hbox(0.13, h * 2.0 + 0.13, 0.13, (-h, 0.0, lz), MAT_INDEX_TIMBER)

    # -- X-cross braces on every face, every span ------------------------------------
    spans = [(deck_lz * 0.10, levels[0]), (levels[0], levels[1]),
             (levels[1], levels[2]), (levels[2], deck_lz - 0.05)]
    for z0, z1 in spans:
        if z1 - z0 < 0.4:
            continue
        h0, h1 = _half(z0), _half(z1)
        for axis, sgn in (('y', 1.0), ('y', -1.0), ('x', 1.0), ('x', -1.0)):
            if axis == 'y':
                def _pt(u, h, z):
                    return (u * h, sgn * h, z)
            else:
                def _pt(u, h, z):
                    return (sgn * h, u * h, z)
            _beam(_pt(-1.0, h0, z0), _pt(1.0, h1, z1), 0.09, MAT_INDEX_TIMBER, bevel=0.006)
            _beam(_pt(1.0, h0, z0), _pt(-1.0, h1, z1), 0.09, MAT_INDEX_TIMBER, bevel=0.006)

    # -- Overhanging deck on cross-beams, railed parapet --------------------------------
    _hbox(half_t * 2.0 + 0.30, 0.18, 0.18, (0.0, 0.0, deck_lz - 0.09), MAT_INDEX_TIMBER)
    _hbox(0.18, half_t * 2.0 + 0.30, 0.18, (0.0, 0.0, deck_lz - 0.09), MAT_INDEX_TIMBER)
    plat = half_t * 2.0 + 1.00
    _deck_p = plat * 0.5
    # Deck floor with a ladder hatch: open band at the hatch x-range from
    # mid-deck to the edge so the ladder arrives through the floor.
    _hatch_x0, _hatch_x1 = 0.55 - 0.30, 0.55 + 0.30
    _hatch_y0 = 0.85
    _hbox(plat, (_deck_p + _hatch_y0), 0.12,
          (0.0, (_hatch_y0 - _deck_p) * 0.5, deck_lz + 0.06),
          MAT_INDEX_WOOD, bevel=0.012, tag=False)
    if _deck_p - _hatch_y0 > 0.05:
        _hbox((_hatch_x0 + _deck_p), (_deck_p - _hatch_y0), 0.12,
              ((_hatch_x0 - _deck_p) * 0.5, (_hatch_y0 + _deck_p) * 0.5, deck_lz + 0.06),
              MAT_INDEX_WOOD, bevel=0.012, tag=False)
        _hbox((_deck_p - _hatch_x1), (_deck_p - _hatch_y0), 0.12,
              ((_hatch_x1 + _deck_p) * 0.5, (_hatch_y0 + _deck_p) * 0.5, deck_lz + 0.06),
              MAT_INDEX_WOOD, bevel=0.012, tag=False)
    rail_h = 1.00
    half_p = plat * 0.5 - 0.07
    for s_x in (-1.0, 1.0):
        for s_y in (-1.0, 1.0):
            _hbox(0.11, 0.11, rail_h,
                  (s_x * half_p, s_y * half_p, deck_lz + 0.12 + rail_h * 0.5),
                  MAT_INDEX_TIMBER)
    for rz in (deck_lz + 0.12 + rail_h - 0.06, deck_lz + 0.12 + rail_h * 0.45):
        _hbox(plat - 0.06, 0.09, 0.09, (0.0, half_p, rz), MAT_INDEX_TIMBER)
        _hbox(plat - 0.06, 0.09, 0.09, (0.0, -half_p, rz), MAT_INDEX_TIMBER)
        _hbox(0.09, plat - 0.06, 0.09, (half_p, 0.0, rz), MAT_INDEX_TIMBER)
        _hbox(0.09, plat - 0.06, 0.09, (-half_p, 0.0, rz), MAT_INDEX_TIMBER)

    # -- Watch-hut: plank walls with window bands, open courtyard front ---------------
    fz = deck_lz + 0.12
    huh = half_t - 0.12
    wall_top = fz + 1.60
    _hbox(0.13, 0.13, 1.60, (huh, huh, fz + 0.80), MAT_INDEX_TIMBER)
    _hbox(0.13, 0.13, 1.60, (-huh, huh, fz + 0.80), MAT_INDEX_TIMBER)
    _hbox(0.13, 0.13, 1.60, (huh, -huh, fz + 0.80), MAT_INDEX_TIMBER)
    _hbox(0.13, 0.13, 1.60, (-huh, -huh, fz + 0.80), MAT_INDEX_TIMBER)
    # Front header over the open doorway (sits on the front posts, clear of
    # the roof slabs above).
    _hbox(huh * 2.0 + 0.13, 0.14, 0.16, (0.0, huh, fz + 1.55), MAT_INDEX_TIMBER)

    # Back wall: solid low band, slatted window band, header plate.
    _plank_lo = huh * 2.0
    nz = max(1, int(round(0.80 / 0.24)))
    for i in range(nz):
        za = fz + 0.80 * i / nz
        zb = fz + 0.80 * (i + 1) / nz
        _hbox(_plank_lo, 0.07, (zb - za) * 0.94, (0.0, -huh, (za + zb) * 0.5),
              MAT_INDEX_WOOD, bevel=0.006)
    _hbox(_plank_lo, 0.07, 0.18, (0.0, -huh, wall_top - 0.09), MAT_INDEX_WOOD, bevel=0.006)
    for _u in (-huh * 0.66, -huh * 0.22, huh * 0.22, huh * 0.66):
        _hbox(0.12, 0.07, wall_top - 0.18 - (fz + 0.80),
              (_u, -huh, (fz + 0.80 + wall_top - 0.18) * 0.5),
              MAT_INDEX_WOOD, bevel=0.006)
    # Side walls: same pattern turned 90 degrees.
    for _sx in (-huh, huh):
        for i in range(nz):
            za = fz + 0.80 * i / nz
            zb = fz + 0.80 * (i + 1) / nz
            _hbox(0.07, huh * 2.0, (zb - za) * 0.94, (_sx, 0.0, (za + zb) * 0.5),
                  MAT_INDEX_WOOD, bevel=0.006)
        _hbox(0.07, huh * 2.0, 0.18, (_sx, 0.0, wall_top - 0.09), MAT_INDEX_WOOD, bevel=0.006)
        for _u in (-huh * 0.55, 0.0, huh * 0.55):
            _hbox(0.07, 0.12, wall_top - 0.18 - (fz + 0.80),
                  (_sx, _u, (fz + 0.80 + wall_top - 0.18) * 0.5),
                  MAT_INDEX_WOOD, bevel=0.006)

    # -- Pitched plank roof, ridge along local X -----------------------------------------
    ridge_z = fz + 2.30
    eave_y = huh + 0.42
    eave_z = fz + 1.50
    hut_w = huh * 2.0
    for sgn in (-1.0, 1.0):
        p_top = to_world(0.0, 0.0, ridge_z)
        p_eave = to_world(0.0, sgn * eave_y, eave_z)
        dv = p_eave - p_top
        # Slabs meet exactly at the ridge (no overshoot crossing); overhang
        # at the eave only.
        _dir = dv.normalized()
        p_eave_ext = p_eave + _dir * 0.18
        ln = (p_eave_ext - p_top).length
        mid = (p_top + p_eave_ext) * 0.5
        x_axis = d_right.normalized()
        z_axis = _dir
        y_axis = z_axis.cross(x_axis).normalized()
        R = Matrix((x_axis, y_axis, z_axis)).transposed()
        e = R.to_euler('XYZ')
        rf = create_beveled_box(bm, size=(hut_w + 0.60, 0.07, ln),
                                location=mid, rotation=(e.x, e.y, e.z),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
        for f in rf:
            f.tag = False
    _hbox(hut_w + 0.62, 0.20, 0.12, (0.0, 0.0, ridge_z + 0.03), MAT_INDEX_TIMBER)
    # Stepped gable infills under both ridge ends. Each board is sized to the
    # slope width at its TOP edge (the narrowest point of that band) so it can
    # never poke out through the roof plane, and stops short of the ridge.
    _gable_top = ridge_z - 0.18
    for gx in (-huh - 0.02, huh + 0.02):
        for gi in range(3):
            gz0 = wall_top + (_gable_top - wall_top) * gi / 3
            gz1 = wall_top + (_gable_top - wall_top) * (gi + 1) / 3
            _span_at_top = 2.0 * eave_y * (ridge_z - gz1) / max(ridge_z - wall_top, 0.01)
            _span_at_top = max(0.15, _span_at_top - 0.06)
            _hbox(0.07, _span_at_top, (gz1 - gz0) * 0.90, (gx, 0.0, (gz0 + gz1) * 0.5),
                  MAT_INDEX_WOOD, bevel=0.006)

    # -- Round shields on the hut front -----------------------------------------------------
    for _sx, _pat in ((-huh + 0.02, 'QUARTERED'), (huh - 0.02, 'SOLID')):
        _sp = to_world(_sx, huh + 0.12, fz + 1.10)
        build_round_shield(bm, (_sp.x, _sp.y, _sp.z),
                           normal=(d_fwd.x, d_fwd.y, 0.0), radius=0.30, pattern=_pat)

    # -- Exterior ladder hugging the battered courtyard face: the rails run
    # parallel to the taper (feet just off the base, top tucked against the
    # deck edge) so it reads as resting on the tower, not floating.
    lad_lx = 0.55
    _lad_bot_out = half_b + 0.16
    _lad_top_out = min(half_t + 0.12, _deck_p - 0.05)
    lad_bot = to_world(lad_lx, _lad_bot_out, 0.0)
    lad_top = to_world(lad_lx, _lad_top_out, deck_lz + 1.00)
    for s_r in (-0.26, 0.26):
        _beam((lad_lx + s_r, _lad_bot_out, 0.0),
              (lad_lx + s_r, _lad_top_out, deck_lz + 1.00),
              0.07, MAT_INDEX_WOOD, bevel=0.006)
    n_rungs = max(5, int((deck_lz + 1.0) / 0.40))
    e_rung = zup.rotation_difference(d_right).to_euler()
    for ir in range(n_rungs):
        t_r = (ir + 0.75) / n_rungs
        rp = lad_bot + (lad_top - lad_bot) * t_r
        rf = create_cylinder(bm, radius=0.020, height=0.52, segments=6,
                             location=rp, rotation=(e_rung.x, e_rung.y, e_rung.z),
                             mat_index=MAT_INDEX_WOOD)
        for f in rf:
            f.tag = True


def _tower_geom(props, ctx):
    """Enclosure line, tower size, wall thickness and outward projection."""
    from .palisade import compound_bounds, fortification_offset, fortification_depth_extra
    off = fortification_offset(props)
    x_min, x_max, y_min, y_max = compound_bounds(ctx, off, fortification_depth_extra(props))
    t = float(getattr(props, 'bastion_tower_size', 3.2))
    if getattr(props, 'has_curtain_wall', False):
        T = float(getattr(props, 'curtain_wall_thickness', 0.55))
    elif getattr(props, 'has_palisade', False):
        T = 0.30
    else:
        T = 0.55
    proj = 0.06          # small proud step so tower and wall never z-fight
    return x_min, x_max, y_min, y_max, t, T, proj


def is_wood_tower(props):
    """True when courtyard towers are open timber watchtowers (palisade fort
    without curtain wall) rather than stone bastions."""
    style = getattr(props, 'bastion_tower_style', 'AUTO')
    if style == 'WOOD':
        return True
    if style in ('STONE', 'GRAND'):
        return False
    # AUTO:
    if getattr(props, 'has_curtain_wall', False):
        return False
    t_tier = getattr(props, 'material_tier', 'TIER_3')
    return t_tier != 'TIER_3'


def courtyard_tower_rects(props, ctx):
    """Corner tower footprints (x0, x1, y0, y1, door_dir), corner-anchored.

    Stone bastions (Tier 3) ARE the corners of the defensive wall: their outer
    two faces lie flush with the enclosure line and the runs stop at their
    edges. Open timber watchtowers (Tier 1/2) instead stand fully INSIDE the
    palisade with clearance all round, and the palisade runs past them
    uninterrupted so the compound stays completely enclosed.
    """
    x_min, x_max, y_min, y_max, t, T, proj = _tower_geom(props, ctx)
    if is_wood_tower(props):
        m = 0.55  # clearance between the fence line and the tower footprint
        rects = []
        # Front-left
        rects.append((x_min + m, x_min + m + t, y_min + m, y_min + m + t, (0.0, 1.0)))
        # Front-right
        rects.append((x_max - m - t, x_max - m, y_min + m, y_min + m + t, (0.0, 1.0)))
        if int(getattr(props, 'bastion_tower_count', 2)) >= 4:
            rects.append((x_max - m - t, x_max - m, y_max - m - t, y_max - m, (0.0, -1.0)))
            rects.append((x_min + m, x_min + m + t, y_max - m - t, y_max - m, (0.0, -1.0)))
        return rects
    h = T * 0.5 + proj
    rects = []
    # Front-left
    rects.append((x_min - h, x_min - h + t, y_min - h, y_min - h + t, (0.0, 1.0)))
    # Front-right
    rects.append((x_max + h - t, x_max + h, y_min - h, y_min - h + t, (0.0, 1.0)))
    if int(getattr(props, 'bastion_tower_count', 2)) >= 4:
        rects.append((x_max + h - t, x_max + h, y_max + h - t, y_max + h, (0.0, -1.0)))
        rects.append((x_min - h, x_min - h + t, y_max + h - t, y_max + h, (0.0, -1.0)))
    return rects


def courtyard_tower_centers(props, ctx):
    """Corner centers for courtyard towers (derived from the footprints)."""
    return [((r[0] + r[1]) * 0.5, (r[2] + r[3]) * 0.5, r[4])
            for r in courtyard_tower_rects(props, ctx)]


def courtyard_tower_footprints(props, ctx):
    """Tower ground footprints (with margin) for collision checks elsewhere."""
    h = 0.20
    return [(r[0] - h, r[1] + h, r[2] - h, r[3] + h)
            for r in courtyard_tower_rects(props, ctx)]


def build_bastion_courtyard_towers(bm, props, ctx):
    """Place corner towers fully inside the enclosure line.

    Palisade tiers get open rickety frame watchtowers (tapered X-braced
    frame, deck hut, exterior ladder); curtain-wall tiers get heavy stone
    bastions with walk-in interiors and crenellated decks.
    """
    t_size = getattr(props, 'bastion_tower_size', 3.2)
    t_height = getattr(props, 'bastion_tower_height', 8.2)

    is_wood = is_wood_tower(props)
    t_mat = MAT_INDEX_WOOD if is_wood else MAT_INDEX_STONE
    t_trim = MAT_INDEX_TIMBER if is_wood else MAT_INDEX_CUT_STONE
    style = getattr(props, 'bastion_tower_style', 'AUTO')
    t_tier = getattr(props, 'material_tier', 'TIER_3')
    is_grand = (style == 'GRAND') or (style == 'AUTO' and t_tier == 'TIER_3')

    for cx, cy, d_dir in courtyard_tower_centers(props, ctx):
        if is_wood:
            # Palisade tiers get an open rickety frame watchtower, never a
            # wooden clone of the stone bastion.
            build_rickety_frame_tower(bm, cx, cy, z_ground=0.0, base_size=t_size,
                                      height=t_height, door_dir=d_dir)
        else:
            if style == 'ROUND_STONE':
                from .castle import build_walkable_round_tower
                build_walkable_round_tower(
                    bm, cx, cy, z_base=0.0,
                    radius=t_size * 0.5,
                    num_floors=int(t_height // 4.5),
                    floor_h=4.5,
                    tower_type='BATTLEMENTS'
                )
            else:
                # Shift the courtyard doorway sideways off the adjoining side
                # wall (which otherwise laps the door jamb) and push the frame
                # slightly proud into the courtyard so all four stay walkable.
                # Left towers step east, right towers step west.
                _ddx, _ddy = d_dir
                _side = -1.0 if cx < 0.0 else 1.0
                _world_shift_x = -_side * 0.55
                # Convert the world X shift into the tower's local lateral axis.
                _rlx, _rly = -_ddy, _ddx
                _shift = _world_shift_x * _rlx
                # Clamp so the shifted opening never leaves the tower face.
                _half_s = max(0.5, t_size * 0.5)
                _max_shift = max(0.0, _half_s - 0.85)
                _shift = max(-_max_shift, min(_max_shift, _shift))
                build_bastion_tower(bm, cx, cy, z_ground=0.0, base_size=t_size,
                                    height=t_height, mat_index=t_mat,
                                    door_dir=d_dir, trim_mat=t_trim,
                                    door_shift=_shift, door_push=0.03,
                                    is_grand=is_grand)

