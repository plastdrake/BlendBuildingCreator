"""Reusable fortified corner bastion towers with hollow interiors and crenellated merlons.

Based on fortress/citadel architecture:
- Massive flared stone plinth (battered talus) at the exterior base.
- Real walk-in hollow interior chamber with flagstone floor, ceiling timber joists, ladder, and wall torch.
- Open arched courtyard entrance doorway with an inward-swung heavy timber door leaf (no palisade conflict).
- Chamfered quoin corners and horizontal string courses to eliminate blockiness.
- Authentic 3D recessed arrow slits (embrasures) with cut-stone reveals and iron cross-loops.
- Stepped stone corbels and machicolation brackets.
- Open rooftop stone platform (fighting deck) surrounded by crenellated merlons with coping caps (no roof).
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_IRON, MAT_INDEX_WOOD,
)
from .palisade import compound_bounds


def build_bastion_tower(bm, x, y, z_ground=0.0, base_size=3.2, height=8.2,
                        talus_height=2.2, talus_flare=0.55, roof_style='MERLONS',
                        mat_index=MAT_INDEX_STONE, door_dir=(0.0, 1.0)):
    """A heavy fortified bastion tower with walk-in hollow interior, courtyard entrance,
    open rooftop stone platform with crenellated merlons, and chamfered quoin corners.
    """
    half_s = base_size * 0.5
    flare_w = half_s + talus_flare
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
    # 1. Flared Stone Talus (Battered Base on 3 Exterior Faces)
    # -----------------------------------------------------------------------
    # Courtyard face (+ly) is vertical for clean doorway; Rear (-ly), Left (-lx), Right (+lx) flare
    corner_signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    b_verts = []
    for s_x, s_y in corner_signs:
        fx = flare_w
        fy = half_s if s_y > 0 else flare_w
        b_verts.append(bm.verts.new(to_world(s_x * fx, s_y * fy, 0.0)))

    t_verts = [
        bm.verts.new(to_world(-half_s, -half_s, talus_height)),
        bm.verts.new(to_world( half_s, -half_s, talus_height)),
        bm.verts.new(to_world( half_s,  half_s, talus_height)),
        bm.verts.new(to_world(-half_s,  half_s, talus_height)),
    ]

    uv_layer = bm.loops.layers.uv.verify()

    # Build the 3 exterior battered faces only:
    # i = 0: Rear (-ly) from (-1,-1) to (1,-1)
    # i = 1: Right (+lx) from (1,-1) to (1,1)
    # i = 3: Left (-lx) from (-1,1) to (-1,-1)
    # (Face i = 2 is the Courtyard face (+ly), which is built as vertical walls around the doorway)
    for i in (0, 1, 3):
        nxt = (i + 1) % 4
        f = bm.faces.new([b_verts[i], b_verts[nxt], t_verts[nxt], t_verts[i]])
        f.material_index = mat_index
        f.tag = False
        # Calculate UV coordinates for seamless stone brick texture
        for lp in f.loops:
            v_local = lp.vert.co - Vector((x, y, z_ground))
            if i == 0:
                u = (d_right.dot(v_local)) * 0.70
            elif i == 1:
                u = (d_fwd.dot(v_local)) * 0.70
            else:
                u = (-d_fwd.dot(v_local)) * 0.70
            v = v_local.z * 0.70
            lp[uv_layer].uv = Vector((u, v))

    # Bottom foundation floor plate under the talus
    f_bot = bm.faces.new([b_verts[3], b_verts[2], b_verts[1], b_verts[0]])
    f_bot.material_index = mat_index
    for lp in f_bot.loops:
        lp[uv_layer].uv = Vector((lp.vert.co.x * 0.5, lp.vert.co.y * 0.5))

    # Chunky cut-stone quoins along exterior base corners of the talus
    for s_x, s_y in ((-1, -1), (1, -1)):
        q_pos = to_world(s_x * (flare_w - 0.15), s_y * (flare_w - 0.15), 0.18)
        qf = create_beveled_box(bm, size=(0.48, 0.48, 0.36), location=q_pos,
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
        for f in qf:
            f.tag = False

    # Cut-stone torus stringer belt course atop the talus
    belt_lz = talus_height + 0.08
    belt_f = create_beveled_box(bm, size=(base_size + 0.18, base_size + 0.18, 0.16),
                                location=to_world(0.0, 0.0, belt_lz),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    for f in belt_f:
        f.tag = False

    # -----------------------------------------------------------------------
    # 2. Real Hollow Walk-In Interior Chamber & 4 Walls
    # -----------------------------------------------------------------------
    # Ground floor cut-stone flagstone slab inside the chamber
    fl_slab = create_beveled_box(bm, size=(int_half * 2.0 - 0.04, int_half * 2.0 - 0.04, 0.14),
                                location=to_world(0.0, 0.0, 0.07),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.01)
    for f in fl_slab:
        f.tag = False

    # Heavy ceiling timber joists overhead inside the chamber
    joist_lz = 2.85
    for j_off in (-0.70, 0.0, 0.70):
        jf = create_beveled_box(bm, size=(int_half * 2.0, 0.16, 0.14),
                                location=to_world(0.0, j_off, joist_lz),
                                rotation=(0.0, 0.0, door_yaw),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        for f in jf:
            f.tag = True

    shaft_bot_lz = belt_lz + 0.08
    shaft_wall_h = deck_lz - shaft_bot_lz

    # Rear Exterior Wall (-ly) - full height solid stone wall
    rear_wall_pos = to_world(0.0, -half_s + wall_t * 0.5, shaft_bot_lz + shaft_wall_h * 0.5)
    rw_f = create_beveled_box(bm, size=(base_size, wall_t, shaft_wall_h),
                              location=rear_wall_pos, rotation=(0.0, 0.0, door_yaw),
                              mat_index=mat_index, bevel_amount=0.02)
    for f in rw_f:
        f.tag = False

    # Left Exterior Wall (-lx)
    lw_len = base_size - 2.0 * wall_t
    left_wall_pos = to_world(-half_s + wall_t * 0.5, 0.0, shaft_bot_lz + shaft_wall_h * 0.5)
    lw_f = create_beveled_box(bm, size=(wall_t, lw_len, shaft_wall_h),
                              location=left_wall_pos, rotation=(0.0, 0.0, door_yaw),
                              mat_index=mat_index, bevel_amount=0.02)
    for f in lw_f:
        f.tag = False

    # Right Exterior Wall (+lx)
    right_wall_pos = to_world(half_s - wall_t * 0.5, 0.0, shaft_bot_lz + shaft_wall_h * 0.5)
    r_wall_f = create_beveled_box(bm, size=(wall_t, lw_len, shaft_wall_h),
                                  location=right_wall_pos, rotation=(0.0, 0.0, door_yaw),
                                  mat_index=mat_index, bevel_amount=0.02)
    for f in r_wall_f:
        f.tag = False

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

    # Upper wall above door lintel up to the rooftop platform
    upper_wall_h = deck_lz - door_h
    upper_wall_pos = to_world(0.0, half_s - wall_t * 0.5, door_h + upper_wall_h * 0.5)
    uw_f = create_beveled_box(bm, size=(base_size, wall_t, upper_wall_h),
                             location=upper_wall_pos, rotation=(0.0, 0.0, door_yaw),
                             mat_index=mat_index, bevel_amount=0.02)
    for f in uw_f:
        f.tag = False

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
    # Sturdy timber access ladder leaning against back-right corner towards ceiling joists
    lad_bottom = to_world(int_half * 0.55, -int_half * 0.50, 0.07)
    lad_top = to_world(int_half * 0.55, -int_half * 0.82, joist_lz + 0.10)
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
    # 6. 3D Recessed Arrow Slits (Embrasures) on 3 Exterior Faces
    # -----------------------------------------------------------------------
    exterior_faces = [
        (0.0, -1.0, 0.0),             # Rear wall (-ly)
        (-1.0, 0.0, math.pi * 0.5),   # Left wall (-lx)
        (1.0, 0.0, -math.pi * 0.5),   # Right wall (+lx)
    ]

    slit_lz = mid_lz + 0.55
    for fx_sign, fy_sign, slit_ang in exterior_faces:
        slit_cx = fx_sign * (half_s + 0.01)
        slit_cy = fy_sign * (half_s + 0.01)
        slit_world = to_world(slit_cx, slit_cy, slit_lz)
        tot_yaw = door_yaw + slit_ang

        # Sloped cut-stone wash sill
        sill_f = create_beveled_box(bm, size=(0.42, 0.24, 0.12),
                                   location=slit_world - d_up * 0.42,
                                   rotation=(math.radians(-10.0), 0.0, tot_yaw),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in sill_f:
            f.tag = False

        # Cut-stone lintel cap
        top_lint = create_beveled_box(bm, size=(0.42, 0.24, 0.14),
                                     location=slit_world + d_up * 0.44,
                                     rotation=(0.0, 0.0, tot_yaw),
                                     mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
        for f in top_lint:
            f.tag = False

        # Left and right cut-stone reveals
        for s_r in (-1.0, 1.0):
            r_vec = Vector((-math.sin(tot_yaw), math.cos(tot_yaw), 0.0)) * (s_r * 0.18)
            j_f = create_beveled_box(bm, size=(0.14, 0.22, 0.78),
                                    location=slit_world + r_vec,
                                    rotation=(0.0, 0.0, tot_yaw),
                                    mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
            for f in j_f:
                f.tag = False

        # Deep recessed dark embrasure cavity
        fwd_vec = Vector((math.cos(tot_yaw), math.sin(tot_yaw), 0.0))
        recess_f = create_beveled_box(bm, size=(0.20, 0.16, 0.74),
                                      location=slit_world - fwd_vec * 0.08,
                                      rotation=(0.0, 0.0, tot_yaw),
                                      mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
        for f in recess_f:
            f.tag = True

        # Narrow vertical aperture slit piercing inward
        vert_slit = create_beveled_box(bm, size=(0.075, 0.26, 0.70),
                                      location=slit_world,
                                      rotation=(0.0, 0.0, tot_yaw),
                                      mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
        for f in vert_slit:
            f.tag = True

        # Authentic medieval horizontal cross-loop bar
        cross_bar = create_beveled_box(bm, size=(0.28, 0.20, 0.065),
                                       location=slit_world + d_up * 0.08,
                                       rotation=(0.0, 0.0, tot_yaw),
                                       mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
        for f in cross_bar:
            f.tag = True

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
    off = getattr(props, 'palisade_offset', 3.0)
    x_min, x_max, y_min, y_max = compound_bounds(ctx, off)
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
                            height=t_height, talus_height=2.2, talus_flare=0.55,
                            mat_index=MAT_INDEX_STONE, door_dir=d_dir)

