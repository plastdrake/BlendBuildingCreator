"""Reusable military yard props: archery targets, weapon racks, training pells, wall shields.

Authentic medieval garrison props based on reference concept art:
- Archery targets with painted concentric rings, wooden tripod stands, and embedded arrows.
- A-frame weapon racks with spears, halberds, and a hanging battleaxe.
- Padded training pells (burlap torso with painted bullseye, stuffed head, cross arms).
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_torus_ring,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_PLASTER, MAT_INDEX_CUT_STONE, MAT_INDEX_TARGET,
    MAT_INDEX_HAY,
)
from .shield import build_round_shield
from .palisade import compound_bounds, fortification_offset


def build_shield_mount(bm, x, y, z, normal=(0.0, -1.0, 0.0), r=0.34):
    """A round shield with an iron boss and heraldic pattern mounted flat on a wall or post."""
    build_round_shield(bm, (x, y, z), normal=normal, radius=r, pattern='QUARTERED')


def _painted_disc(bm, center, normal, radius, segments=18, dome=0.004,
                  surface_radius=None, n_rings=None, uv_radius=None):
    """A painted scoring-ring disc facing ``normal``, with radial UVs for the
    dedicated target material.

    When ``surface_radius`` is given the disc is built as a tessellated cap of
    ``n_rings`` concentric rings that each conform to a cylinder of that radius
    (+``dome``). A single flat fan would cut *inside* the curved surface between
    the raised centre and rim and appear half-embedded, so multiple rings keep
    the whole bullseye proud of the barrel.

    ``uv_radius`` clamps every loop to a single ring of the target shader, so the
    whole disc samples one flat colour (used to paint a plain red circle).
    """
    fn = Vector(normal).normalized()
    up_ref = Vector((0.0, 0.0, 1.0)) if abs(fn.z) <= 0.95 else Vector((0.0, 1.0, 0.0))
    right = up_ref.cross(fn).normalized()
    up = fn.cross(right).normalized()
    c = Vector(center)
    uv_layer = bm.loops.layers.uv.verify()

    if surface_radius is None:
        n_rings = 1
    elif n_rings is None:
        n_rings = 4
    n_rings = max(1, int(n_rings))

    def off(rho, a):
        if surface_radius is None:
            return 0.0
        # Conform to a vertical cylinder: depth depends on the *horizontal*
        # offset (rho*cos a) alone. Using the full radius here would build a
        # sphere cap instead, burying the top and bottom of the disc in the
        # barrel so only a thin horizontal band stayed visible.
        u = rho * math.cos(a)
        return math.sqrt(max(0.0, surface_radius * surface_radius - u * u)) + dome

    def uv_at(rho, a):
        if uv_radius is not None:
            # Pin every loop to one ring of the shader so the disc is a single
            # flat colour (a painted circle) instead of concentric rings.
            return Vector((0.5 + uv_radius, 0.5))
        f = rho / radius
        return Vector((0.5 + 0.5 * f * math.cos(a), 0.5 + 0.5 * f * math.sin(a)))

    center_v = bm.verts.new(c + fn * ((surface_radius if surface_radius else 0.0) + dome))
    rings = [center_v]
    for ri in range(1, n_rings + 1):
        rho = radius * ri / n_rings
        row = []
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            p = c + fn * off(rho, a) + right * (rho * math.cos(a)) + up * (rho * math.sin(a))
            row.append(bm.verts.new(p))
        rings.append(row)

    # Centre fan to the first ring.
    r1 = radius / n_rings
    for i in range(segments):
        nxt = (i + 1) % segments
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        f = bm.faces.new([center_v, rings[1][i], rings[1][nxt]])
        f.material_index = MAT_INDEX_TARGET
        f.tag = True
        f.loops[0][uv_layer].uv = uv_at(0.0, 0.0)
        f.loops[1][uv_layer].uv = uv_at(r1, a0)
        f.loops[2][uv_layer].uv = uv_at(r1, a1)

    # Quad bands between successive rings.
    for ri in range(1, n_rings):
        rho0 = radius * ri / n_rings
        rho1 = radius * (ri + 1) / n_rings
        for i in range(segments):
            nxt = (i + 1) % segments
            a0 = 2.0 * math.pi * i / segments
            a1 = 2.0 * math.pi * (i + 1) / segments
            f = bm.faces.new([rings[ri][i], rings[ri][nxt],
                              rings[ri + 1][nxt], rings[ri + 1][i]])
            f.material_index = MAT_INDEX_TARGET
            f.tag = True
            f.loops[0][uv_layer].uv = uv_at(rho0, a0)
            f.loops[1][uv_layer].uv = uv_at(rho0, a1)
            f.loops[2][uv_layer].uv = uv_at(rho1, a1)
            f.loops[3][uv_layer].uv = uv_at(rho1, a0)


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

    # 2. Painted target face: one disc with radial UVs sampled by the dedicated
    #    target material (concentric scoring rings + gold bullseye).
    _painted_disc(bm, tr @ Vector((0.0, 0.0, half_t)), fn, target_r,
                  segments=segments, dome=0.004)

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

        # Fletching feathers at the tail end. The cone's wide end must sit at the
        # tail (+arr_dir, away from the target), not at the head, so the flare
        # points back toward the archer.
        tail_pos = hit_pos + arr_dir * (shaft_len - 0.06)
        fletch_f = create_cone(bm, radius1=0.006, radius2=0.028, height=0.12, segments=5,
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
    """A padded training pell on a timber stake (reference-accurate).

    Stuffed burlap torso with a painted bullseye, rounded head, cross arms with
    rope-wrapped ends and rope bindings, standing on a bracketed round timber
    base. Replaces the old shield-quintain whose shield clipped through the arm.
    """
    ca, sa = math.cos(ang), math.sin(ang)
    fwd = Vector((-sa, ca, 0.0))     # torso faces the archer
    right = Vector((ca, sa, 0.0))

    # 1. Round timber base (plain stacked discs, no metal brackets).
    create_cylinder(bm, radius=0.34, height=0.10, segments=16,
                    location=(x, y, z_ground + 0.05), mat_index=MAT_INDEX_TIMBER)
    create_cylinder(bm, radius=0.26, height=0.07, segments=16,
                    location=(x, y, z_ground + 0.12), mat_index=MAT_INDEX_TIMBER)

    # 2. Central stake up through the pell.
    create_cylinder(bm, radius=0.05, height=1.72, segments=10,
                    location=(x, y, z_ground + 0.86), mat_index=MAT_INDEX_TIMBER)

    # 3. Stuffed hay torso (main barrel + lower skirt) and shoulders. High
    #    segment count keeps the barrel round so the painted bullseye conforms
    #    flush to the surface instead of sinking into a flat facet.
    z0 = z_ground + 1.18
    create_cylinder(bm, radius=0.30, height=0.55, segments=28,
                    location=(x, y, z0), mat_index=MAT_INDEX_HAY)
    create_cylinder(bm, radius=0.25, height=0.30, segments=28,
                    location=(x, y, z0 - 0.32), mat_index=MAT_INDEX_HAY)
    create_cylinder(bm, radius=0.16, height=0.14, segments=20,
                    location=(x, y, z0 + 0.30), mat_index=MAT_INDEX_HAY)

    # 4. Stuffed head with a rounded crown.
    head_z = z0 + 0.56
    create_cylinder(bm, radius=0.18, height=0.26, segments=20,
                    location=(x, y, head_z), mat_index=MAT_INDEX_HAY)
    create_cone(bm, radius1=0.18, radius2=0.05, height=0.16, segments=20,
                location=(x, y, head_z + 0.21), mat_index=MAT_INDEX_HAY)

    # 5. Rope bindings (neck, waist, lower hem).
    for rz, rr in ((head_z - 0.17, 0.15), (z0 - 0.26, 0.27), (z0 + 0.20, 0.30)):
        rf = create_torus_ring(bm, location=(x, y, rz), rotation=(0.0, 0.0, 0.0),
                               major_radius=rr, minor_radius=0.022,
                               major_segments=14, minor_segments=6,
                               mat_index=MAT_INDEX_TIMBER)
        for f in rf:
            f.tag = True

    # 6. Cross arms with rope-wrapped padded ends.
    arm_z = z0 + 0.14
    arm_f = create_beveled_box(bm, size=(0.98, 0.085, 0.085),
                               location=(x, y, arm_z), rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    for f in arm_f:
        f.tag = True
    for s in (-1.0, 1.0):
        ap = Vector((x, y, arm_z)) + right * (s * 0.44)
        pf = create_cylinder(bm, radius=0.065, height=0.18, segments=8,
                             location=(ap.x, ap.y, ap.z),
                             rotation=(0.0, math.pi * 0.5, ang),
                             mat_index=MAT_INDEX_HAY)
        for f in pf:
            f.tag = True
        brf = create_torus_ring(bm, location=(ap.x, ap.y, ap.z),
                                rotation=(0.0, math.pi * 0.5, ang),
                                major_radius=0.07, minor_radius=0.016,
                                major_segments=8, minor_segments=5,
                                mat_index=MAT_INDEX_TIMBER)
        for f in brf:
            f.tag = True

    # 7. Painted red target circle on the belly, conforming to the barrel so it
    #    reads as painted-on straw rather than a separate lashed-on paper plate.
    #    Sits below the cross arms and above the hem rope so it stays unoccluded.
    _R = 0.30
    _painted_disc(bm, Vector((x, y, z0 - 0.06)), fwd, 0.15, segments=24, dome=0.004,
                  surface_radius=_R, n_rings=3, uv_radius=0.12)

    # 8. Spent arrows sticking out of the torso at dynamic angles. The butt is
    #    seated inside the barrel surface at that lateral offset (sqrt profile),
    #    so every shaft emerges through the straw instead of floating in front.
    arrow_specs = [(-0.15, 0.14, -1.0), (0.09, -0.06, 1.0), (0.20, 0.12, 1.0)]
    for hx, hz, side in arrow_specs:
        surf = math.sqrt(max(0.0, _R * _R - hx * hx))
        base = Vector((x, y, z0 + hz)) + right * hx + fwd * (surf - 0.06)
        adir = (fwd * 0.55 + Vector((0.0, 0.0, 1.0)) * 0.5
                + right * (0.35 * side)).normalized()
        alen = 0.34
        mid = base + adir * (alen * 0.5)
        arot = Vector((0.0, 0.0, 1.0)).rotation_difference(adir).to_euler()
        sf = create_cylinder(bm, radius=0.008, height=alen, segments=6,
                             location=(mid.x, mid.y, mid.z), rotation=arot,
                             mat_index=MAT_INDEX_WOOD)
        for f in sf:
            f.tag = True
        tail = base + adir * (alen - 0.05)
        flf = create_cone(bm, radius1=0.006, radius2=0.026, height=0.10, segments=5,
                          location=(tail.x, tail.y, tail.z), rotation=arot,
                          mat_index=MAT_INDEX_PLASTER)
        for f in flf:
            f.tag = True


def _spread_positions(n, lo, hi):
    """Return ``n`` evenly spaced positions between ``lo`` and ``hi`` (inclusive)."""
    n = max(1, int(n))
    if n == 1 or hi <= lo:
        return [(lo + hi) * 0.5]
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def build_military_props(bm, props, ctx):
    """Lay out the military drill yard along the courtyard walls.

    On U-shaped buildings the archery targets line one wing's inner wall and the
    training pells line the opposite wing, both facing into the courtyard so they
    face each other across the drill lane. Weapon racks stand at the inner ends
    of the wing walls. Shape-aware so props never clip wings, rooms or walls.
    """
    wall_t = ctx.wall_t
    found_h = getattr(props, 'foundation_height', 0.5)

    n_racks = max(0, int(getattr(props, 'military_rack_count', 2)))
    n_dummies = max(0, int(getattr(props, 'military_dummy_count', 3)))
    n_targets = max(0, int(getattr(props, 'military_target_count', 3)))

    main_front_y = -ctx.base_d * 0.5 - wall_t * 0.5
    has_u_wings = (ctx.shape == 'U_SHAPE' and ctx.wings
                   and any(w.get('wall') == 'FRONT' for w in ctx.wings))

    if has_u_wings:
        front_wings = [w for w in ctx.wings if w.get('wall') == 'FRONT']
        w_left = min(front_wings, key=lambda w: w['base'][0])
        w_right = max(front_wings, key=lambda w: w['base'][1])
        left_wall = w_left['base'][1]     # left wing inner face (faces +X)
        right_wall = w_right['base'][0]   # right wing inner face (faces -X)
        wing_front_y = min(w['base'][2] for w in front_wings)

        stand = 0.82
        y_front = wing_front_y + 1.8
        y_back = max(y_front, main_front_y - 3.1)
        ys = _spread_positions(max(n_targets, n_dummies, 1), y_front, y_back)

        # Archery targets on the left wall, facing right into the courtyard.
        for i in range(n_targets):
            build_archery_target(bm, left_wall + stand, ys[min(i, len(ys) - 1)], 0.0,
                                 ang=math.radians(-90.0))
        # Training pells on the right wall, facing left into the courtyard.
        for i in range(n_dummies):
            build_training_dummy(bm, right_wall - stand, ys[min(i, len(ys) - 1)], 0.0,
                                 ang=math.radians(90.0))
        # Weapon racks flank the gate against the front enclosure wall (which has
        # no windows) and face into the courtyard, so they cannot intersect the
        # wing windows the way wall-mounted racks did.
        _x0, _x1, enclosure_y, _y1 = compound_bounds(ctx, fortification_offset(props))
        rack_y = enclosure_y + 0.85
        for rx in _spread_positions(n_racks, ctx.main_door_cx - 3.3,
                                    ctx.main_door_cx + 3.3):
            build_weapon_rack(bm, rx, rack_y, 0.0, ang=0.0)
    else:
        court_x0 = -ctx.base_w * 0.5 + 1.2
        court_x1 = ctx.base_w * 0.5 - 1.2
        pal_off = (getattr(props, 'palisade_offset', 3.0)
                   if getattr(props, 'has_palisade', False) else 2.0)

        for tx in _spread_positions(n_targets, court_x0 + 0.9, court_x1 - 0.9):
            build_archery_target(bm, tx, main_front_y + 1.3, 0.0, ang=0.0)
        for dx in _spread_positions(n_dummies, court_x0 + 1.1, court_x1 - 1.1):
            build_training_dummy(bm, dx, main_front_y - pal_off * 0.48, 0.0,
                                 ang=math.radians(180.0))
        rack_y = main_front_y - pal_off + 0.85
        for rx in _spread_positions(n_racks, ctx.main_door_cx - 3.0,
                                    ctx.main_door_cx + 3.0):
            build_weapon_rack(bm, rx, rack_y, 0.0, ang=0.0)

    # Mounted heraldic wall shield above the main entrance (never over a window).
    # Shrink it to the headroom between the door head and the storey above, and
    # skip it entirely when even a small plaque would clip the ceiling/floor.
    door_cx = ctx.main_door_cx
    door_h = getattr(props, 'door_height', 2.1)
    door_head = found_h + door_h
    radius = 0.34
    shield_z = door_head + 0.36
    if ctx.num_floors >= 2:
        floor_above = found_h + getattr(props, 'floor_height', 2.8)
        head_room = floor_above - door_head
        if shield_z + radius + 0.06 > floor_above:
            radius = (head_room - 0.12) * 0.5
            if radius < 0.18:
                return
            shield_z = door_head + head_room * 0.5
    build_round_shield(bm, (door_cx, main_front_y - 0.02, shield_z),
                       normal=(0.0, -1.0, 0.0), radius=radius, pattern='QUARTERED')
