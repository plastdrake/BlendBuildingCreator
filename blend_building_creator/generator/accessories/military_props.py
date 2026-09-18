"""Reusable military yard props: archery targets, weapon racks, quintains, wall shields.

Authentic medieval garrison props based on reference concept art:
- Archery targets with painted concentric rings, wooden tripod stands, and embedded arrows.
- A-frame weapon racks with spears, halberds, and a hanging battleaxe.
- Training quintains with spinning shield arm and sandbag counterweight.
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_PLASTER, MAT_INDEX_CUT_STONE,
)
from .shield import build_round_shield


def build_shield_mount(bm, x, y, z, normal=(0.0, -1.0, 0.0), r=0.34):
    """A round shield with an iron boss and heraldic pattern mounted flat on a wall or post."""
    build_round_shield(bm, (x, y, z), normal=normal, radius=r, pattern='QUARTERED')


def build_archery_target(bm, x, y, z_ground=0.0, ang=0.0):
    """A traditional round straw archery target on a timber tripod with embedded arrows.

    Near-vertical orientation facing the shooting lane with an authentic ~7° backward rake.
    Tripod legs are situated 100% behind and underneath the disc.
    Concentric painted scoring rings use clean procedural shaders (no dragon banner texture).
    """
    ca, sa = math.cos(ang), math.sin(ang)
    tilt = math.radians(7.0)  # slight backward rake so disc rests firmly on tripod
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)

    # Orthonormal orientation:
    # fn points outward from the target face toward the courtyard / archer
    fn = Vector((-sa * cos_t, -ca * cos_t, sin_t)).normalized()
    right = Vector((ca, -sa, 0.0)).normalized()
    up = fn.cross(right).normalized()

    target_z = z_ground + 1.25
    target_r = 0.44
    target_t = 0.12

    rot_mat = Matrix([
        [right.x, up.x, fn.x, 0.0],
        [right.y, up.y, fn.y, 0.0],
        [right.z, up.z, fn.z, 0.0],
        [0.0,     0.0,  0.0,  1.0]
    ])
    loc_mat = Matrix.Translation(Vector((x, y, target_z)))
    tr = loc_mat @ rot_mat

    uv_layer = bm.loops.layers.uv.verify()
    segments = 16

    # 1. Straw cylinder body
    half_t = target_t * 0.5
    v_front = []
    v_back = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca_i, sa_i = math.cos(a), math.sin(a)
        vf = tr @ Vector((target_r * ca_i, target_r * sa_i, half_t))
        vb = tr @ Vector((target_r * ca_i, target_r * sa_i, -half_t))
        v_front.append(bm.verts.new(vf))
        v_back.append(bm.verts.new(vb))

    # Rim side quads
    for i in range(segments):
        nxt = (i + 1) % segments
        side_f = bm.faces.new([v_front[i], v_back[i], v_back[nxt], v_front[nxt]])
        side_f.material_index = MAT_INDEX_WOOD
        side_f.tag = True

    # Back face cap
    c_back = bm.verts.new(tr @ Vector((0.0, 0.0, -half_t)))
    for i in range(segments):
        nxt = (i + 1) % segments
        bf = bm.faces.new([c_back, v_back[nxt], v_back[i]])
        bf.material_index = MAT_INDEX_TIMBER
        bf.tag = True

    # 2. Concentric scoring rings on the front face (clean rings, no banner texture)
    ring_radii = [
        (target_r * 1.00, 0.000, MAT_INDEX_WOOD),         # Outer straw braid rim
        (target_r * 0.88, 0.003, MAT_INDEX_PLASTER),      # Outer white scoring ring
        (target_r * 0.65, 0.006, MAT_INDEX_IRON),         # Black scoring ring
        (target_r * 0.42, 0.009, MAT_INDEX_TIMBER),       # Red/dark scoring ring
        (target_r * 0.20, 0.012, MAT_INDEX_WOOD),         # Center gold bullseye
    ]

    for r_outer, z_off, mat_idx in ring_radii:
        ring_verts = []
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            vf = tr @ Vector((r_outer * math.cos(a), r_outer * math.sin(a), half_t + z_off))
            ring_verts.append(bm.verts.new(vf))
        c_v = bm.verts.new(tr @ Vector((0.0, 0.0, half_t + z_off)))
        for i in range(segments):
            nxt = (i + 1) % segments
            rf = bm.faces.new([c_v, ring_verts[i], ring_verts[nxt]])
            rf.material_index = mat_idx
            rf.tag = True
            a0 = 2.0 * math.pi * i / segments
            a1 = 2.0 * math.pi * (i + 1) / segments
            rf.loops[0][uv_layer].uv = Vector((0.5, 0.5))
            rf.loops[1][uv_layer].uv = Vector((0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0)))
            rf.loops[2][uv_layer].uv = Vector((0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1)))

    # 3. Timber tripod stand (two front splayed legs + rear kickstand prop leg)
    # Both situated 100% behind the disc face (local Z <= -half_t)
    leg_w = 0.075
    # Two front legs splayed left and right
    for s_x in (-1.0, 1.0):
        # Mount on back of target
        top_pt = tr @ Vector((s_x * 0.22, 0.20, -half_t - 0.02))
        bot_pt = Vector((x + right.x * (s_x * 0.38) + up.x * -0.45,
                         y + right.y * (s_x * 0.38) + up.y * -0.45,
                         z_ground + leg_w * 0.5))
        mid_pt = (top_pt + bot_pt) * 0.5
        leg_vec = top_pt - bot_pt
        leg_len = leg_vec.length
        leg_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(leg_vec.normalized()).to_euler()
        leg_f = create_beveled_box(bm, size=(leg_w, leg_w, leg_len),
                                   location=mid_pt, rotation=leg_rot,
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        for f in leg_f:
            f.tag = True

    # Rear kickstand prop leg extending back away from face
    rear_top = tr @ Vector((0.0, 0.26, -half_t - 0.025))
    rear_bot = Vector((x - fn.x * 0.62, y - fn.y * 0.62, z_ground + leg_w * 0.5))
    rear_mid = (rear_top + rear_bot) * 0.5
    rear_vec = rear_top - rear_bot
    rear_len = rear_vec.length
    rear_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(rear_vec.normalized()).to_euler()
    rear_f = create_beveled_box(bm, size=(leg_w, leg_w, rear_len),
                                location=rear_mid, rotation=rear_rot,
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    for f in rear_f:
        f.tag = True

    # Stretcher tie crossbar between the two front legs
    cbar_z = z_ground + 0.45
    cbar_loc = Vector((x - fn.x * 0.08, y - fn.y * 0.08, cbar_z))
    cbar = create_beveled_box(bm, size=(0.74, 0.06, 0.07),
                             location=cbar_loc, rotation=(0.0, 0.0, ang),
                             mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for f in cbar:
        f.tag = True

    # 4. Embedded 3D arrows sticking into the face at dynamic angles
    arrow_hits = [
        (0.06,  0.03, math.radians(3.0),  math.radians(2.0)),
        (-0.09, -0.06, math.radians(-5.0), math.radians(-4.0)),
        (0.02,  0.10, math.radians(2.0),  math.radians(-5.0)),
    ]
    shaft_len = 0.65
    for hx, hy, p_pitch, p_yaw in arrow_hits:
        hit_pos = tr @ Vector((hx, hy, half_t + 0.008))
        # Arrow direction: points OUTWARD toward the shooting line along fn
        arr_rot = Matrix.Rotation(p_pitch, 3, right) @ Matrix.Rotation(p_yaw, 3, up)
        arr_dir = (arr_rot @ fn).normalized()

        shaft_center = hit_pos + arr_dir * (shaft_len * 0.5)
        arr_euler = Vector((0.0, 0.0, 1.0)).rotation_difference(arr_dir).to_euler()
        shaft_f = create_cylinder(bm, radius=0.0075, height=shaft_len, segments=6,
                                  location=shaft_center, rotation=arr_euler,
                                  mat_index=MAT_INDEX_WOOD)
        for f in shaft_f:
            f.tag = True

        # Fletching feathers at tail end
        tail_pos = hit_pos + arr_dir * (shaft_len - 0.06)
        fletch_f = create_cone(bm, radius1=0.025, radius2=0.006, height=0.10, segments=5,
                               location=tail_pos, rotation=arr_euler,
                               mat_index=MAT_INDEX_PLASTER)
        for f in fletch_f:
            f.tag = True


def build_weapon_rack(bm, x, y, z_ground=0.0, ang=0.0):
    """Sturdy A-frame rack holding spears, halberds, and a hanging battleaxe.

    Features:
    - Heavy timber A-frame end posts with wide stability runners.
    - Bottom base trough with individual carved socket cups where weapon butts sit.
    - Top notched rest rail positioned so spears lean back naturally at ~11° (no mashing).
    - Diverse weaponry: 3 spears with iron collars/leaf blades, 1 halberd/poleaxe, and a side battleaxe.
    """
    ca, sa = math.cos(ang), math.sin(ang)
    def to_world(lx, ly, lz):
        # lx = along rack span, ly = across rack depth, lz = height
        wx = x + ca * lx - sa * ly
        wy = y + sa * lx + ca * ly
        return Vector((wx, wy, z_ground + lz))

    rack_len = 1.55
    half_len = rack_len * 0.5

    # 1. Sturdy timber end uprights with wide foot runners
    for s_x in (-half_len, half_len):
        # Stability foot runner resting on ground
        foot_pos = to_world(s_x, 0.0, 0.06)
        foot_f = create_beveled_box(bm, size=(0.14, 0.54, 0.12),
                                   location=foot_pos, rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
        for f in foot_f:
            f.tag = True

        # Vertical end post
        post_pos = to_world(s_x, -0.02, 0.72)
        post_f = create_beveled_box(bm, size=(0.12, 0.12, 1.44),
                                    location=post_pos, rotation=(0.0, 0.0, ang),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
        for f in post_f:
            f.tag = True

        # Diagonal timber knee braces
        for s_brace, b_ang in ((-1, math.radians(35.0)), (1, math.radians(-35.0))):
            brace_pos = to_world(s_x, s_brace * 0.14, 0.36)
            br_f = create_beveled_box(bm, size=(0.08, 0.08, 0.48),
                                     location=brace_pos, rotation=(b_ang, 0.0, ang),
                                     mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
            for f in br_f:
                f.tag = True

    # 2. Bottom Weapon Rest Runner with Socket Cups
    bot_y = 0.18  # forward offset for spear butts
    bot_z = 0.06
    bot_rail_pos = to_world(0.0, bot_y, bot_z)
    bot_rail = create_beveled_box(bm, size=(rack_len, 0.22, 0.12),
                                  location=bot_rail_pos, rotation=(0.0, 0.0, ang),
                                  mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    for f in bot_rail:
        f.tag = True

    # 3. Top Rest Board - front face is precisely at ly = 0.0
    top_y = -0.03
    top_z = 1.22
    top_rail_pos = to_world(0.0, top_y, top_z)
    top_rail = create_beveled_box(bm, size=(rack_len, 0.06, 0.14),
                                  location=top_rail_pos, rotation=(0.0, 0.0, ang),
                                  mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    for f in top_rail:
        f.tag = True

    # 4. Weapons resting in individual slots (all spears, leaning flush against the board)
    slots = [-0.45, -0.15, 0.15, 0.45]
    shaft_len = 2.42
    r_shaft = 0.021

    rot_mat = Matrix.Rotation(ang, 4, 'Z')
    trans_mat = Matrix.Translation(Vector((x, y, z_ground)))
    tr = trans_mat @ rot_mat

    for slot_x in slots:
        # Carved iron socket cup at bottom rest
        cup_pos = to_world(slot_x, bot_y, 0.12)
        cup_f = create_cylinder(bm, radius=0.038, height=0.045, segments=8,
                                location=cup_pos, rotation=(0.0, 0.0, ang),
                                mat_index=MAT_INDEX_IRON)
        for f in cup_f:
            f.tag = True

        # Twin wooden retaining pegs on top rest board flanking the spear shaft
        for s_peg in (-0.045, 0.045):
            peg_pos = to_world(slot_x + s_peg, 0.035, top_z)
            peg_f = create_cylinder(bm, radius=0.010, height=0.07, segments=6,
                                    location=peg_pos, rotation=(math.radians(90.0), 0.0, ang),
                                    mat_index=MAT_INDEX_TIMBER)
            for f in peg_f:
                f.tag = True

        # Spear shaft geometry:
        # Butt rests in bottom cup at (slot_x, 0.18, 0.12)
        # At top board z = 1.22, front face of board is at y = 0.0.
        # Shaft center at y = r_shaft (0.021) places back surface of shaft at y = 0.0 (flush physical contact).
        p_butt = Vector((slot_x, bot_y, 0.12))
        p_rest = Vector((slot_x, r_shaft, top_z))
        local_dir = (p_rest - p_butt).normalized()

        butt_pos = tr @ p_butt
        shaft_dir = (rot_mat.to_3x3() @ local_dir).normalized()
        shaft_center = butt_pos + shaft_dir * (shaft_len * 0.5)
        shaft_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(shaft_dir).to_euler()

        shaft_f = create_cylinder(bm, radius=r_shaft, height=shaft_len, segments=8,
                                  location=shaft_center, rotation=shaft_rot,
                                  mat_index=MAT_INDEX_WOOD)
        for f in shaft_f:
            f.tag = True

        # Iron butt ferrule resting in bottom socket cup
        ferrule_pos = butt_pos + shaft_dir * 0.05
        fer_f = create_cylinder(bm, radius=0.026, height=0.09, segments=8,
                                location=ferrule_pos, rotation=shaft_rot,
                                mat_index=MAT_INDEX_IRON)
        for f in fer_f:
            f.tag = True

        # Spearhead at the tip
        tip_pos = butt_pos + shaft_dir * (shaft_len - 0.04)

        # Socket collar
        col_pos = tip_pos - shaft_dir * 0.06
        col_f = create_cylinder(bm, radius=0.032, height=0.08, segments=8,
                                location=col_pos, rotation=shaft_rot,
                                mat_index=MAT_INDEX_IRON)
        for f in col_f:
            f.tag = True

        # Leaf-shaped spearhead
        blade_pos = tip_pos + shaft_dir * 0.16
        blade_f = create_cone(bm, radius1=0.055, radius2=0.0, height=0.34, segments=6,
                              location=blade_pos, rotation=shaft_rot,
                              mat_index=MAT_INDEX_IRON)
        for f in blade_f:
            f.tag = True


def build_training_dummy(bm, x, y, z_ground=0.0, ang=0.0):
    """A medieval training quintain: pivoting crossbeam with a shield target and hanging sandbag."""
    # 1. Chunky timber center post with iron reinforcing bands
    post_h = 2.10
    post_r = 0.11
    p_faces = create_cylinder(bm, radius=post_r, height=post_h, segments=8,
                              location=(x, y, z_ground + post_h * 0.5), mat_index=MAT_INDEX_TIMBER)
    for f in p_faces:
        f.tag = True

    # Iron base & top bands
    for b_z in (z_ground + 0.35, z_ground + 1.85):
        bf = create_cylinder(bm, radius=post_r + 0.015, height=0.08, segments=8,
                             location=(x, y, b_z), mat_index=MAT_INDEX_IRON)
        for f in bf:
            f.tag = True

    # 2. Horizontal pivoting crossarm
    bar_z = z_ground + 1.75
    bar_len = 1.30
    ca, sa = math.cos(ang), math.sin(ang)
    arm_f = create_beveled_box(bm, size=(bar_len, 0.12, 0.12),
                               location=(x, y, bar_z),
                               rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    for f in arm_f:
        f.tag = True

    # Iron pivot cap on top
    cap_f = create_cylinder(bm, radius=0.075, height=0.20, segments=8,
                            location=(x, y, bar_z + 0.12), mat_index=MAT_INDEX_IRON)
    for f in cap_f:
        f.tag = True

    # 3. Arm 1: Wooden round shield target
    sh_x = x + ca * (bar_len * 0.5)
    sh_y = y + sa * (bar_len * 0.5)
    build_round_shield(bm, (sh_x, sh_y, bar_z), normal=(-sa, ca, 0.0), radius=0.28, pattern='QUARTERED')

    # 4. Arm 2: Hanging counterweighted wooden sandbag / flail
    fl_x = x - ca * (bar_len * 0.48)
    fl_y = y - sa * (bar_len * 0.48)
    # Suspension link
    link_f = create_cylinder(bm, radius=0.015, height=0.45, segments=6,
                             location=(fl_x, fl_y, bar_z - 0.22), mat_index=MAT_INDEX_IRON)
    for f in link_f:
        f.tag = True
    # Chunky barrel / sandbag counterweight
    sb_f = create_cylinder(bm, radius=0.16, height=0.42, segments=10,
                           location=(fl_x, fl_y, bar_z - 0.58), mat_index=MAT_INDEX_TIMBER_FRAME)
    for f in sb_f:
        f.tag = True
    # Iron band around sandbag
    sbb_f = create_cylinder(bm, radius=0.17, height=0.06, segments=10,
                            location=(fl_x, fl_y, bar_z - 0.58), mat_index=MAT_INDEX_IRON)
    for f in sbb_f:
        f.tag = True


def build_military_props(bm, props, ctx):
    """Scatter an authentic military drill yard layout: archery lane, weapon rack, quintain.

    Shape-aware collision avoidance guarantees props never clip inside wings, rooms, or walls.
    """
    count = max(1, int(getattr(props, 'military_props_count', 3)))
    wall_t = ctx.wall_t
    found_h = getattr(props, 'foundation_height', 0.5)

    # 1. Determine safe courtyard and drill yard boundaries factoring in wings
    has_u_wings = (ctx.shape == 'U_SHAPE' and ctx.wings and any(w.get('wall') == 'FRONT' for w in ctx.wings))

    if has_u_wings:
        front_wings = [w for w in ctx.wings if w.get('wall') == 'FRONT']
        w_left = min(front_wings, key=lambda w: w['base'][0])
        w_right = max(front_wings, key=lambda w: w['base'][1])
        # Inner walls of wings forming the courtyard
        court_x0 = w_left['base'][1]
        court_x1 = w_right['base'][0]
        wing_front_y = min(w['base'][2] for w in front_wings)
        main_front_y = -ctx.base_d * 0.5 - wall_t * 0.5
    else:
        court_x0 = -ctx.base_w * 0.5 + 1.2
        court_x1 = ctx.base_w * 0.5 - 1.2
        wing_front_y = -ctx.base_d * 0.5 - wall_t * 0.5
        main_front_y = wing_front_y

    court_w = max(2.0, court_x1 - court_x0)
    court_cx = (court_x0 + court_x1) * 0.5

    # Palisade boundary
    has_pal = getattr(props, 'has_palisade', False)
    pal_off = getattr(props, 'palisade_offset', 3.0) if has_pal else 2.0
    pal_front_y = wing_front_y - pal_off

    door_cx = ctx.main_door_cx
    door_clear = getattr(props, 'door_width', 1.2) * 0.5 + 1.1

    # 1. Weapon rack placed on the right flank of the drill yard
    if has_u_wings:
        rack_x = court_cx + court_w * 0.22
        rack_y = (main_front_y + wing_front_y) * 0.50
        build_weapon_rack(bm, rack_x, rack_y, 0.0, ang=math.radians(-25.0))
    else:
        rack_x = door_cx - door_clear - 0.9
        rack_x = max(court_x0 + 0.95, min(rack_x, court_x1 - 0.95))
        build_weapon_rack(bm, rack_x, main_front_y - 0.45, 0.0, ang=0.0)

    # 2. Training quintain / dummy on the left flank of the drill yard
    if has_u_wings:
        dummy_x = court_cx - court_w * 0.22
        dummy_y = (main_front_y + wing_front_y) * 0.50
        build_training_dummy(bm, dummy_x, dummy_y, 0.0, ang=math.radians(20.0))
    else:
        dummy_x = court_x0 + 1.3
        dummy_y = main_front_y - pal_off * 0.48
        build_training_dummy(bm, dummy_x, dummy_y, 0.0, ang=math.radians(20.0))

    # 3. Archery target(s):
    # Placed at the end of the courtyard shooting lane facing +Y toward archers
    if has_u_wings:
        target_x = court_cx + court_w * 0.32
        target_y = wing_front_y + 1.6
        build_archery_target(bm, target_x, target_y, 0.0, ang=math.radians(170.0))
        if count >= 3:
            build_archery_target(bm, target_x - 1.25, target_y + 0.35, 0.0, ang=math.radians(165.0))
    else:
        target_x = court_x1 - 0.85
        target_y = main_front_y - pal_off * 0.65
        build_archery_target(bm, target_x, target_y, 0.0, ang=math.radians(165.0))
        if count >= 3:
            build_archery_target(bm, target_x - 1.25, target_y - 0.30, 0.0, ang=math.radians(170.0))

    # 4. Mounted wall shield:
    # Mounted directly above the main entrance door lintel (garrison heraldry)
    # Guaranteed never to collide with window openings
    door_h = getattr(props, 'door_height', 2.1)
    shield_z = found_h + door_h + 0.36
    build_round_shield(bm, (door_cx, main_front_y - 0.02, shield_z),
                       normal=(0.0, -1.0, 0.0), radius=0.34, pattern='QUARTERED')
