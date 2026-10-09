"""Reusable gate fixtures.

The gatehouse framing itself lives in :mod:`curtain_wall`; this module owns the
moving parts that dress a gate opening:

- :func:`build_portcullis` - an iron grille gate (bars + rails + side channels)

It is deliberately independent of any footprint so the Knights Manor curtains,
the palisade gate and any future gatehouse can all reuse it.
"""

import math

from ..mesh_utils import create_cylinder, create_cone, create_beveled_box
from ..materials import MAT_INDEX_IRON, MAT_INDEX_TIMBER


def build_portcullis(bm, cx, cy, z_ground=0.0, width=2.6, height=2.9,
                     outward=(0.0, -1.0), raised=None):
    """An iron portcullis seated in a gate opening.

    ``outward`` is the horizontal normal of the wall the gate sits in; the
    grille is built in the gate plane. By default, ``raised`` hoists the gate
    high overhead into the vault so the gateway is open for the player to enter.
    """
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = 0.0, -1.0
    else:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox                      # wall tangent
    ang = math.atan2(ty, tx)

    eff_raised = max(2.15, height * 0.75) if raised is None else float(raised)
    z0 = z_ground + eff_raised
    z1 = z_ground + height + 0.70

    # Side guide channels biting into the jambs.
    chan_h = height + 0.90
    for s in (-1.0, 1.0):
        px = cx + tx * (s * (width * 0.5 + 0.09))
        py = cy + ty * (s * (width * 0.5 + 0.09))
        create_beveled_box(bm, size=(0.14, 0.22, chan_h),
                           location=(px, py, z_ground + chan_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Vertical bars with spiked feet.
    n_bars = max(3, int(round(width / 0.34)))
    step = width / (n_bars + 1)
    for i in range(1, n_bars + 1):
        u = -width * 0.5 + i * step
        bx = cx + tx * u
        by = cy + ty * u
        # Vertical iron bars: cylinder is along Z by default, rotation=(0.0, 0.0, ang) keeps it strictly vertical
        create_cylinder(bm, radius=0.045, height=z1 - z0, segments=6,
                        location=(bx, by, (z0 + z1) * 0.5),
                        rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_IRON)
        # Pointed cone spike at the bottom of each bar: rotation=(math.pi, 0.0, ang) flips tip downward
        create_cone(bm, radius1=0.05, radius2=0.0, height=0.16, segments=6,
                    location=(bx, by, z0 - 0.08),
                    rotation=(math.pi, 0.0, ang), mat_index=MAT_INDEX_IRON)

    # Horizontal rails across the grille.
    for rz in (z0 + 0.12, (z0 + z1) * 0.5, z1 - 0.12):
        create_beveled_box(bm, size=(width + 0.10, 0.10, 0.10),
                           location=(cx, cy, rz), rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.006)


def build_chain_run(bm, p_start, p_end, major_r=0.060, minor_r=0.013, pitch=0.082, mat_index=MAT_INDEX_IRON):
    """Interlocking 3D torus chain links along a 3D line segment with alternating 90-deg rotations."""
    from mathutils import Vector, Matrix
    from ..mesh_utils import create_torus_ring
    p0 = Vector(p_start)
    p1 = Vector(p_end)
    disp = p1 - p0
    dist = disp.length
    if dist < 0.1:
        return
    T = disp / dist
    up = Vector((0.0, 0.0, 1.0)) if abs(T.z) < 0.9 else Vector((0.0, 1.0, 0.0))
    N1 = T.cross(up).normalized()
    N2 = T.cross(N1).normalized()

    n_links = max(2, int(dist / pitch))
    step = dist / n_links
    for i in range(n_links + 1):
        pos = p0 + T * (i * step)
        if i % 2 == 0:
            mat_3x3 = Matrix([T, N1, N2]).transposed()
        else:
            mat_3x3 = Matrix([T, N2, -N1]).transposed()
        rot_euler = mat_3x3.to_euler('XYZ')
        create_torus_ring(bm, location=pos, rotation=rot_euler, major_radius=major_r, minor_radius=minor_r,
                          major_segments=10, minor_segments=6, mat_index=mat_index)


def build_drawbridge(bm, cx, cy, z_ground=0.0, width=2.6, length=4.4,
                     outward=(0.0, -1.0), angle_deg=0.0, has_chains=True, pier_h=3.2):
    """Fortified castle drawbridge with heavy oak plank deck, perimeter iron strapping,
    ditch pit curb, iron pivot hinges, and taut forged iron suspension chains.

    When ``angle_deg == 0.0``, the bridge is lowered flat across the ditch from the gate
    threshold to the outer stone abutment landing, allowing players to walk straight in.
    """
    from mathutils import Vector, Matrix
    from ..materials import MAT_INDEX_WOOD, MAT_INDEX_CUT_STONE
    from ..mesh_utils import create_torus_ring

    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = 0.0, -1.0
    else:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox
    ang_wall = math.atan2(ty, tx)
    # ang_gate faces forward along outward
    ang_gate = math.atan2(oy, ox) - math.pi * 0.5

    pitch_rad = math.radians(max(0.0, min(80.0, float(angle_deg))))
    rot_mat = Matrix.Rotation(ang_gate, 4, 'Z') @ Matrix.Rotation(pitch_rad, 4, 'X')
    rot_euler = rot_mat.to_euler('XYZ')

    p_hinge = Vector((cx, cy, z_ground - 0.04))
    deck_thick = 0.14
    plank_thick = 0.06

    # 1. Causeway, Gateway Platform, and Approach Ramps
    # a. Solid cut-stone Gateway Threshold Platform under the portal arch
    plat_w = width + 1.20
    plat_len = 2.40
    plat_cx = cx - ox * 0.40
    plat_cy = cy - oy * 0.40
    create_beveled_box(bm, size=(plat_w, plat_len, 0.28),
                       location=(plat_cx, plat_cy, z_ground + 0.02),
                       rotation=(0.0, 0.0, ang_gate),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)

    # b. Courtyard Approach Ramp (Inside): gentle cut-stone incline extending into the bailey
    ramp_in_len = 2.80
    ramp_in_w = width + 0.80
    ramp_in_cx = cx - ox * (plat_len * 0.5 + ramp_in_len * 0.5 + 0.30)
    ramp_in_cy = cy - oy * (plat_len * 0.5 + ramp_in_len * 0.5 + 0.30)
    n_in_tiers = 4
    for ri in range(n_in_tiers):
        t_frac = ri / n_in_tiers
        step_len = ramp_in_len / n_in_tiers
        tier_cx = cx - ox * (plat_len * 0.5 + 0.40 + (ri + 0.5) * step_len)
        tier_cy = cy - oy * (plat_len * 0.5 + 0.40 + (ri + 0.5) * step_len)
        tier_z = z_ground + (1.0 - t_frac) * 0.14
        create_beveled_box(bm, size=(ramp_in_w, step_len + 0.04, tier_z + 0.02),
                           location=(tier_cx, tier_cy, tier_z * 0.5),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    # Retaining curb beams framing courtyard ramp
    for sgn in (-1.0, 1.0):
        crb_x = ramp_in_cx + tx * (sgn * (ramp_in_w * 0.5 + 0.14))
        crb_y = ramp_in_cy + ty * (sgn * (ramp_in_w * 0.5 + 0.14))
        create_beveled_box(bm, size=(0.28, ramp_in_len + 0.40, 0.28),
                           location=(crb_x, crb_y, z_ground + 0.14),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # c. Moat / Dry Ditch stone pit curb under the bridge
    ditch_depth = 0.50
    pit_len = length * 1.05
    pit_cx = cx + ox * (pit_len * 0.5)
    pit_cy = cy + oy * (pit_len * 0.5)
    for sgn in (-1.0, 1.0):
        kx = pit_cx + tx * (sgn * (width * 0.5 + 0.35))
        ky = pit_cy + ty * (sgn * (width * 0.5 + 0.35))
        create_beveled_box(bm, size=(0.40, pit_len, ditch_depth + 0.25),
                           location=(kx, ky, z_ground - ditch_depth * 0.5),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # d. Outer stone abutment landing across the ditch
    ab_len = 2.40
    ab_w = width + 1.80
    ab_pos = p_hinge + Vector((ox, oy, 0.0)) * (length + ab_len * 0.5 + 0.05)
    create_beveled_box(bm, size=(ab_w, ab_len, ditch_depth + 0.26),
                       location=(ab_pos.x, ab_pos.y, z_ground - ditch_depth * 0.5 + 0.03),
                       rotation=(0.0, 0.0, ang_gate),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)
    # Low protective stone curbs framing the outer abutment landing
    for sgn in (-1.0, 1.0):
        ab_crb_x = ab_pos.x + tx * (sgn * (ab_w * 0.5 - 0.15))
        ab_crb_y = ab_pos.y + ty * (sgn * (ab_w * 0.5 - 0.15))
        create_beveled_box(bm, size=(0.32, ab_len + 0.10, 0.42),
                           location=(ab_crb_x, ab_crb_y, z_ground + 0.26 + 0.21),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # e. Outer Stone Approach Ramp (Outside): gentle stone incline sloping down to ground level
    ramp_out_len = 3.60
    ramp_out_w = width + 1.40
    ramp_out_cx = ab_pos.x + ox * (ab_len * 0.5 + ramp_out_len * 0.5)
    ramp_out_cy = ab_pos.y + oy * (ab_len * 0.5 + ramp_out_len * 0.5)
    n_out_tiers = 5
    for ro in range(n_out_tiers):
        t_frac = ro / n_out_tiers
        step_len = ramp_out_len / n_out_tiers
        tier_cx = ab_pos.x + ox * (ab_len * 0.5 + (ro + 0.5) * step_len)
        tier_cy = ab_pos.y + oy * (ab_len * 0.5 + (ro + 0.5) * step_len)
        tier_z = z_ground + (1.0 - t_frac) * 0.16
        create_beveled_box(bm, size=(ramp_out_w, step_len + 0.05, tier_z + 0.02),
                           location=(tier_cx, tier_cy, tier_z * 0.5),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    # Retaining side curbs on outer ramp
    for sgn in (-1.0, 1.0):
        o_crb_x = ramp_out_cx + tx * (sgn * (ramp_out_w * 0.5 + 0.14))
        o_crb_y = ramp_out_cy + ty * (sgn * (ramp_out_w * 0.5 + 0.14))
        create_beveled_box(bm, size=(0.28, ramp_out_len + 0.30, 0.30),
                           location=(o_crb_x, o_crb_y, z_ground + 0.15),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 2. Drawbridge Deck
    # Base longitudinal timber beams
    n_beams = max(3, int(width / 0.70))
    b_step = (width - 0.24) / max(1, n_beams - 1)
    for bi in range(n_beams):
        lx = -width * 0.5 + 0.12 + bi * b_step
        b_mid = p_hinge + (rot_mat @ Vector((lx, length * 0.5, deck_thick * 0.5))).to_3d()
        create_beveled_box(bm, size=(0.14, length, deck_thick),
                           location=(b_mid.x, b_mid.y, b_mid.z),
                           rotation=rot_euler,
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Cross transverse oak planks
    deck_mid = p_hinge + (rot_mat @ Vector((0.0, length * 0.5, deck_thick + plank_thick * 0.5))).to_3d()
    create_beveled_box(bm, size=(width, length, plank_thick),
                       location=(deck_mid.x, deck_mid.y, deck_mid.z),
                       rotation=rot_euler,
                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)

    # Perimeter iron strapping along bridge edges
    for sgn in (-1.0, 1.0):
        strap_lx = sgn * (width * 0.5 - 0.05)
        strap_mid = p_hinge + (rot_mat @ Vector((strap_lx, length * 0.5, deck_thick + plank_thick + 0.02))).to_3d()
        create_beveled_box(bm, size=(0.08, length, 0.05),
                           location=(strap_mid.x, strap_mid.y, strap_mid.z),
                           rotation=rot_euler,
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.005)

    # Heavy iron threshold hinges
    for sgn in (-1.0, 1.0):
        hx = cx + tx * (sgn * (width * 0.5 - 0.20))
        hy = cy + ty * (sgn * (width * 0.5 - 0.20))
        create_beveled_box(bm, size=(0.14, 0.45, 0.12),
                           location=(hx, hy, z_ground + 0.02),
                           rotation=(0.0, 0.0, ang_wall),
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.008)

    # 3. Forged Iron Suspension Chains (Strictly Parallel Runs, Zero Criss-Crossing!)
    if has_chains:
        reach = length - 0.25
        deck_fwd = Vector((ox, oy, 0.0)) * math.cos(pitch_rad) + Vector((0.0, 0.0, 1.0)) * math.sin(pitch_rad)
        deck_z_lift = (deck_thick + plank_thick + 0.04) * math.cos(pitch_rad)

        # Left deck eyelet: in negative tangent direction (-tx, -ty)
        p_corner_L = p_hinge + deck_fwd * reach - Vector((tx, ty, 0.0)) * (width * 0.5 - 0.15) + Vector((0.0, 0.0, deck_z_lift))
        # Right deck eyelet: in positive tangent direction (+tx, +ty)
        p_corner_R = p_hinge + deck_fwd * reach + Vector((tx, ty, 0.0)) * (width * 0.5 - 0.15) + Vector((0.0, 0.0, deck_z_lift))

        for cp in (p_corner_L, p_corner_R):
            create_torus_ring(bm, location=cp, rotation=rot_euler,
                              major_radius=0.075, minor_radius=0.016, mat_index=MAT_INDEX_IRON)

        # High chain portals in gate piers
        chain_h = max(2.6, pier_h + 0.35)
        # Left wall hawse: in negative tangent direction (-tx, -ty)
        p_wall_L = Vector((cx, cy, z_ground + chain_h)) - Vector((tx, ty, 0.0)) * (width * 0.5 + 0.42) + Vector((ox, oy, 0.0)) * 0.25
        # Right wall hawse: in positive tangent direction (+tx, +ty)
        p_wall_R = Vector((cx, cy, z_ground + chain_h)) + Vector((tx, ty, 0.0)) * (width * 0.5 + 0.42) + Vector((ox, oy, 0.0)) * 0.25

        for wp in (p_wall_L, p_wall_R):
            create_beveled_box(bm, size=(0.28, 0.28, 0.28),
                               location=(wp.x, wp.y, wp.z),
                               rotation=(0.0, 0.0, ang_wall),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
            create_torus_ring(bm, location=wp + Vector((ox * 0.15, oy * 0.15, 0.0)),
                              rotation=(1.5708, 0.0, ang_wall),
                              major_radius=0.080, minor_radius=0.018, mat_index=MAT_INDEX_IRON)

        # Interlocking 3D chains: strictly parallel Left-to-Left and Right-to-Right!
        build_chain_run(bm, p_corner_L, p_wall_L, major_r=0.062, minor_r=0.014, pitch=0.084)
        build_chain_run(bm, p_corner_R, p_wall_R, major_r=0.062, minor_r=0.014, pitch=0.084)


def build_flanking_gate_towers(bm, cx, cy, z_ground=0.0, gap_w=2.8, wall_h=3.2,
                               wall_t=0.55, outward=(0.0, -1.0), tower_r=1.90, tower_h=None):
    """Twin semicircular / D-shaped flanking bastion gate towers projecting forward
    from the curtain wall with arrow slits, cut-stone corbels, crenellated battlements,
    and direct stone access steps connecting the curtain wall-walk to the tower roof terrace."""
    from mathutils import Vector
    from ..materials import MAT_INDEX_STONE, MAT_INDEX_CUT_STONE
    from .battlement import build_battlement_run

    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = 0.0, -1.0
    else:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox
    ang = math.atan2(ty, tx)

    H = tower_h if tower_h is not None else wall_h + 1.85
    talus_h = 0.85
    pier_w = tower_r * 2.0

    tc_dist = gap_w * 0.5 + tower_r + 0.15

    for sgn in (-1.0, 1.0):
        # Tower centered to frame gate opening cleanly without pinching the passage
        tc_x = cx + tx * (sgn * tc_dist) + ox * (tower_r * 0.42)
        tc_y = cy + ty * (sgn * tc_dist) + oy * (tower_r * 0.42)

        # 1. Battered talus base
        create_beveled_box(bm, size=(pier_w + 0.40, pier_w + 0.40, talus_h),
                           location=(tc_x, tc_y, z_ground + talus_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.035)

        # 2. Main tower masonry shaft
        shaft_h = H - talus_h
        create_beveled_box(bm, size=(pier_w, pier_w, shaft_h),
                           location=(tc_x, tc_y, z_ground + talus_h + shaft_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.025)

        # 3. Arrow slits on forward and lateral faces
        slit_z = z_ground + talus_h + shaft_h * 0.48
        # Front arrow slit
        fs_x = tc_x + ox * (tower_r * 0.51)
        fs_y = tc_y + oy * (tower_r * 0.51)
        create_beveled_box(bm, size=(0.14, 0.22, 0.90),
                           location=(fs_x, fs_y, slit_z),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
        # Flank arrow slit
        ls_x = tc_x + tx * (sgn * tower_r * 0.51)
        ls_y = tc_y + ty * (sgn * tower_r * 0.51)
        create_beveled_box(bm, size=(0.22, 0.14, 0.90),
                           location=(ls_x, ls_y, slit_z),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)

        # 4. Machicolation corbel brackets beneath the parapet
        corbel_z = z_ground + H - 0.22
        for ci in range(4):
            c_u = -tower_r * 0.70 + ci * (tower_r * 1.40 / 3.0)
            cx_c = tc_x + tx * c_u + ox * (tower_r * 0.52)
            cy_c = tc_y + ty * c_u + oy * (tower_r * 0.52)
            create_beveled_box(bm, size=(0.18, 0.35, 0.42),
                               location=(cx_c, cy_c, corbel_z),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

        # 5. Overhanging crenellated battlements atop the tower
        top_z = z_ground + H
        deck_w = pier_w + 0.30
        create_beveled_box(bm, size=(deck_w, deck_w, 0.18),
                           location=(tc_x, tc_y, top_z),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

        # Parapet merlon runs around the 3 exposed sides (rear kept open for walk-up stair access!)
        # Front face battlements
        p_front_s = (tc_x + tx * (deck_w * 0.5) + ox * (deck_w * 0.5),
                     tc_y + ty * (deck_w * 0.5) + oy * (deck_w * 0.5))
        p_front_e = (tc_x - tx * (deck_w * 0.5) + ox * (deck_w * 0.5),
                     tc_y - ty * (deck_w * 0.5) + oy * (deck_w * 0.5))
        build_battlement_run(bm, p_front_s, p_front_e, top_z + 0.09, height=0.82,
                             thickness=0.30, style='STONE')

        # Outer flank battlements
        p_out_s = (tc_x + tx * (sgn * deck_w * 0.5) + ox * (deck_w * 0.5),
                   tc_y + ty * (sgn * deck_w * 0.5) + oy * (deck_w * 0.5))
        p_out_e = (tc_x + tx * (sgn * deck_w * 0.5) - ox * (deck_w * 0.5),
                   tc_y + ty * (sgn * deck_w * 0.5) - oy * (deck_w * 0.5))
        build_battlement_run(bm, p_out_s, p_out_e, top_z + 0.09, height=0.82,
                             thickness=0.30, style='STONE')

        # Inner flank battlements (facing gatehouse)
        p_in_s = (tc_x - tx * (sgn * deck_w * 0.5) + ox * (deck_w * 0.5),
                  tc_y - ty * (sgn * deck_w * 0.5) + oy * (deck_w * 0.5))
        p_in_e = (tc_x - tx * (sgn * deck_w * 0.5) - ox * (deck_w * 0.20),
                  tc_y - ty * (sgn * deck_w * 0.5) - oy * (deck_w * 0.20))
        build_battlement_run(bm, p_in_s, p_in_e, top_z + 0.09, height=0.82,
                             thickness=0.30, style='STONE')

        # 6. Solid cut-stone access steps from curtain wall-walk up to gate tower roof deck
        diff_h = H - (wall_h + 0.16)
        if diff_h > 0.4:
            n_tsteps = 6
            tstep_h = diff_h / n_tsteps
            tstep_w = 0.72
            tstep_d = (tower_r * 1.40) / n_tsteps
            rear_lat = tower_r * 0.42 - tower_r - tstep_w * 0.5
            for ti in range(n_tsteps):
                step_u = sgn * (tc_dist - tower_r * 0.70 + (ti + 0.5) * tstep_d)
                st_x = cx + tx * step_u + ox * rear_lat
                st_y = cy + ty * step_u + oy * rear_lat
                st_h_solid = (ti + 1) * tstep_h
                st_z = z_ground + wall_h + 0.16 + st_h_solid * 0.5
                create_beveled_box(bm, size=(tstep_d, tstep_w, st_h_solid),
                                   location=(st_x, st_y, st_z),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
                # Outer stepped stone balustrade along courtyard edge of the steps
                bal_x = st_x - ox * (tstep_w * 0.5 + 0.08)
                bal_y = st_y - oy * (tstep_w * 0.5 + 0.08)
                bal_h = 0.65
                bal_z = z_ground + wall_h + 0.16 + (ti + 1) * tstep_h + bal_h * 0.5
                create_beveled_box(bm, size=(tstep_d, 0.16, bal_h),
                                   location=(bal_x, bal_y, bal_z),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
