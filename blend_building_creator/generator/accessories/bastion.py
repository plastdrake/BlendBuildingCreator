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
                        mat_index=MAT_INDEX_STONE, door_dir=(0.0, 1.0)):
    """A heavy fortified bastion tower with walk-in hollow interior, courtyard entrance,
    open rooftop stone platform with crenellated merlons, and chamfered quoin corners.
    """
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
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        for f in pf:
            f.tag = False
    door_w_pl = 1.05
    pl_jamb = pl_reach - door_w_pl * 0.5
    for s_p in (-1.0, 1.0):
        pf = create_beveled_box(bm, size=(pl_jamb, pl_t, plinth_h),
                                location=to_world(s_p * (door_w_pl * 0.5 + pl_jamb * 0.5),
                                                  half_s, plinth_h * 0.5),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        for f in pf:
            f.tag = False

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
    jamb_w = half_s - door_w * 0.5

    # Left door jamb wall segment (from ground z=0 to door_h)
    left_jamb_pos = to_world(-half_s + jamb_w * 0.5, half_s - wall_t * 0.5, door_cz)
    lj_f = create_beveled_box(bm, size=(jamb_w, wall_t, door_h),
                             location=left_jamb_pos, rotation=(0.0, 0.0, door_yaw),
                             mat_index=mat_index, bevel_amount=0.02)
    for f in lj_f:
        f.tag = False

    # Right door jamb wall segment (from ground z=0 to door_h)
    right_jamb_pos = to_world(half_s - jamb_w * 0.5, half_s - wall_t * 0.5, door_cz)
    rj_f = create_beveled_box(bm, size=(jamb_w, wall_t, door_h),
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
    # 3. Arched Cut-Stone Doorway Trimmings & Open Inward Timber Door Leaf
    # -----------------------------------------------------------------------
    door_front_y = half_s

    # Cut-stone threshold step
    th_f = create_beveled_box(bm, size=(door_w + 0.28, wall_t + 0.22, 0.14),
                             location=to_world(0.0, door_front_y, 0.07),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    for f in th_f:
        f.tag = False

    # Heavy cut-stone jamb pilasters framing the opening
    for s_j in (-1.0, 1.0):
        jx = s_j * (door_w * 0.5 + 0.11)
        jamb_f = create_beveled_box(bm, size=(0.22, wall_t + 0.12, door_h),
                                   location=to_world(jx, door_front_y, door_cz),
                                   rotation=(0.0, 0.0, door_yaw),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in jamb_f:
            f.tag = False

    # Heavy arched cut-stone lintel header above door
    lintel_f = create_beveled_box(bm, size=(door_w + 0.44, wall_t + 0.16, 0.32),
                                 location=to_world(0.0, door_front_y, door_h + 0.16),
                                 rotation=(0.0, 0.0, door_yaw),
                                 mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    for f in lintel_f:
        f.tag = False

    # Timber reveal casing lining the doorway aperture (hollow frame, not a solid plug)
    cas_t = 0.035
    # Left casing lining
    l_cas = create_beveled_box(bm, size=(cas_t, wall_t, door_h),
                              location=to_world(-door_w * 0.5 + cas_t * 0.5, half_s - wall_t * 0.5, door_cz),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in l_cas: f.tag = True
    # Right casing lining
    r_cas = create_beveled_box(bm, size=(cas_t, wall_t, door_h),
                              location=to_world(door_w * 0.5 - cas_t * 0.5, half_s - wall_t * 0.5, door_cz),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in r_cas: f.tag = True
    # Head casing lining
    h_cas = create_beveled_box(bm, size=(door_w, wall_t, cas_t),
                              location=to_world(0.0, half_s - wall_t * 0.5, door_h - cas_t * 0.5),
                              rotation=(0.0, 0.0, door_yaw),
                              mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in h_cas: f.tag = True

    # Heavy timber door leaf swung OPEN into the chamber (revealing the hollow interior)
    door_leaf_w = door_w - 0.08
    door_leaf_h = door_h - 0.08
    door_leaf_t = 0.055
    open_angle = math.radians(72.0)  # swung inward towards the left inner wall

    # Hinge location at left inner casing corner
    hinge_lx = -door_w * 0.5 + 0.06
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
    # Sturdy timber access ladder climbing through the hatch in the upper floor.
    lad_bottom = to_world(hole_c_lx + 0.24, hole_c_ly + int_half * 0.72, 0.02)
    lad_top = to_world(hole_c_lx, hole_c_ly, floor_lz + 0.50)
    lad_vec = lad_top - lad_bottom
    lad_len = lad_vec.length
    lad_mid = (lad_bottom + lad_top) * 0.5
    lad_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(lad_vec.normalized()).to_euler()

    for s_rail in (-0.20, 0.20):
        # Tangent vector across ladder width
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
    # Stacked alternating cut-stone quoin blocks along the 4 vertical corners
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
                                         mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.018)
            for f in q_faces:
                f.tag = False

    # Mid-height cut-stone drip stringer course (water table)
    mid_lz = shaft_bot_lz + shaft_wall_h * 0.46
    mid_belt = create_beveled_box(bm, size=(base_size + 0.12, base_size + 0.12, 0.12),
                                  location=to_world(0.0, 0.0, mid_lz),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    for f in mid_belt:
        f.tag = False

    # -----------------------------------------------------------------------
    # 6. Real Window Slits: cut-stone reveals dressing the through-holes
    # -----------------------------------------------------------------------
    for lx, ly, lz, out_n in slit_specs:
        c = to_world(lx, ly, lz)
        build_arrow_slit(bm, center=(c.x, c.y, c.z), normal_axis=out_n,
                         wall_thickness=wall_t, slit_w=slit_w, slit_h=slit_h,
                         has_transom=True)

    # -----------------------------------------------------------------------
    # 7. Stepped Corbels & Open Rooftop Stone Platform (Fighting Deck)
    # -----------------------------------------------------------------------
    # Tier 1 stepped corbel course
    c1_lz = deck_lz - 0.22
    c1_f = create_beveled_box(bm, size=(base_size + 0.24, base_size + 0.24, 0.18),
                             location=to_world(0.0, 0.0, c1_lz),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)
    for f in c1_f:
        f.tag = False

    # Tier 2 projecting corbel course
    c2_lz = deck_lz - 0.06
    c2_f = create_beveled_box(bm, size=(base_size + 0.44, base_size + 0.44, 0.18),
                             location=to_world(0.0, 0.0, c2_lz),
                             rotation=(0.0, 0.0, door_yaw),
                             mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)
    for f in c2_f:
        f.tag = False

    # Individual cantilevered stone machicolation brackets under the overhang
    b_offsets = [-0.95, 0.0, 0.95]
    for b_off in b_offsets:
        bk_f1 = create_beveled_box(bm, size=(0.22, 0.32, 0.38),
                                  location=to_world(b_off, -half_s - 0.06, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in bk_f1: f.tag = False
        bk_f2 = create_beveled_box(bm, size=(0.22, 0.32, 0.38),
                                  location=to_world(b_off, half_s + 0.06, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in bk_f2: f.tag = False
        bk_f3 = create_beveled_box(bm, size=(0.32, 0.22, 0.38),
                                  location=to_world(-half_s - 0.06, b_off, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in bk_f3: f.tag = False
        bk_f4 = create_beveled_box(bm, size=(0.32, 0.22, 0.38),
                                  location=to_world(half_s + 0.06, b_off, c1_lz - 0.10),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in bk_f4: f.tag = False

    # Open rooftop fighting deck flagstone platform (open to sky - NO ROOF)
    deck_slab_pos = to_world(0.0, 0.0, deck_lz + 0.07)
    plat_w = base_size + 0.44
    d_f = create_beveled_box(bm, size=(plat_w, plat_w, 0.14),
                            location=deck_slab_pos,
                            rotation=(0.0, 0.0, door_yaw),
                            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
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
    # 8. Fortified Crenellated Merlons with Sloped Coping Caps
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
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in cpf:
            f.tag = False
        cap_f = create_beveled_box(bm, size=(merlon_t * 1.9, merlon_t * 1.9, 0.09),
                                  location=cp_pos + d_up * (merlon_h * 0.5 + 0.045),
                                  rotation=(0.0, 0.0, door_yaw),
                                  mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.018)
        for f in cap_f:
            f.tag = False

    # Intermediate merlons with embrasure firing gaps along the 4 edges
    m_edge_inset = half_p - merlon_t * 0.5
    im_w = 0.50
    im_offsets = [-0.55, 0.55]

    for im_x in im_offsets:
        # Rear edge merlons (-ly)
        m1_pos = to_world(im_x, -m_edge_inset, merlon_cz)
        mf1 = create_beveled_box(bm, size=(im_w, merlon_t, merlon_h), location=m1_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for f in mf1: f.tag = False
        c1 = create_beveled_box(bm, size=(im_w + 0.08, merlon_t + 0.08, 0.08),
                                location=m1_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in c1: f.tag = False

        # Front edge merlons (+ly)
        m2_pos = to_world(im_x, m_edge_inset, merlon_cz)
        mf2 = create_beveled_box(bm, size=(im_w, merlon_t, merlon_h), location=m2_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for f in mf2: f.tag = False
        c2 = create_beveled_box(bm, size=(im_w + 0.08, merlon_t + 0.08, 0.08),
                                location=m2_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in c2: f.tag = False

        # Left edge merlons (-lx)
        m3_pos = to_world(-m_edge_inset, im_x, merlon_cz)
        mf3 = create_beveled_box(bm, size=(merlon_t, im_w, merlon_h), location=m3_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for f in mf3: f.tag = False
        c3 = create_beveled_box(bm, size=(merlon_t + 0.08, im_w + 0.08, 0.08),
                                location=m3_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in c3: f.tag = False

        # Right edge merlons (+lx)
        m4_pos = to_world(m_edge_inset, im_x, merlon_cz)
        mf4 = create_beveled_box(bm, size=(merlon_t, im_w, merlon_h), location=m4_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
        for f in mf4: f.tag = False
        c4 = create_beveled_box(bm, size=(merlon_t + 0.08, im_w + 0.08, 0.08),
                                location=m4_pos + d_up * (merlon_h * 0.5 + 0.04),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in c4: f.tag = False


def build_bastion_courtyard_towers(bm, props, ctx):
    """Place heavy corner bastion towers with walk-in hollow interiors, courtyard arched entrances,
    and open fighting decks with crenellated merlons (no roof).

    Tower outer walls align flush with the compound X boundary (tower center shifted inward by half_s)
    so the courtyard-facing door is never blocked by the side palisades.
    """
    off = fortification_offset(props)
    x_min, x_max, y_min, y_max = compound_bounds(ctx, off, fortification_depth_extra(props))
    t_size = getattr(props, 'bastion_tower_size', 3.2)
    t_height = getattr(props, 'bastion_tower_height', 8.2)
    t_half = t_size * 0.5

    # Shift tower centers inward by t_half so the outer wall aligns with x_min/x_max.
    # Door faces North (0.0, 1.0) into courtyard — side palisades start at py_min = y_min+t_half+0.45
    # which is comfortably above the door face at y_min+t_half.
    corners = [
        (x_min + t_half, y_min, (0.0, 1.0)),  # front-left: outer wall on x_min
        (x_max - t_half, y_min, (0.0, 1.0)),  # front-right: outer wall on x_max
    ]
    # If 4 towers configured, add back corners (entrance doors face South into courtyard)
    if getattr(props, 'bastion_tower_count', 2) >= 4:
        corners.extend([
            (x_max - t_half, y_max, (0.0, -1.0)),
            (x_min + t_half, y_max, (0.0, -1.0)),
        ])

    for cx, cy, d_dir in corners:
        build_bastion_tower(bm, cx, cy, z_ground=0.0, base_size=t_size,
                            height=t_height, mat_index=MAT_INDEX_STONE,
                            door_dir=d_dir)

