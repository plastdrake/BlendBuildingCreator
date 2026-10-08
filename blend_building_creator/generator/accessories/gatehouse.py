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
        create_cylinder(bm, radius=0.045, height=z1 - z0, segments=6,
                        location=(bx, by, (z0 + z1) * 0.5),
                        rotation=(1.5707963, 0.0, ang), mat_index=MAT_INDEX_IRON)
        create_cone(bm, radius1=0.05, radius2=0.0, height=0.16, segments=6,
                    location=(bx, by, z0 - 0.08),
                    rotation=(0.0, math.pi, ang), mat_index=MAT_INDEX_IRON)

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

    p_hinge = Vector((cx, cy, z_ground + 0.08))

    # 1. Moat / Dry Ditch stone pit curb under the bridge
    ditch_depth = 0.45
    pit_len = length * 1.05
    pit_cx = cx + ox * (pit_len * 0.5)
    pit_cy = cy + oy * (pit_len * 0.5)
    # Side curb walls of the ditch
    for sgn in (-1.0, 1.0):
        kx = pit_cx + tx * (sgn * (width * 0.5 + 0.35))
        ky = pit_cy + ty * (sgn * (width * 0.5 + 0.35))
        create_beveled_box(bm, size=(0.40, pit_len, ditch_depth + 0.20),
                           location=(kx, ky, z_ground - ditch_depth * 0.5),
                           rotation=(0.0, 0.0, ang_gate),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    # Outer stone abutment landing across the ditch
    ab_pos = p_hinge + Vector((ox, oy, 0.0)) * (length + 0.45)
    create_beveled_box(bm, size=(width + 1.30, 0.90, ditch_depth + 0.25),
                       location=(ab_pos.x, ab_pos.y, z_ground - ditch_depth * 0.5),
                       rotation=(0.0, 0.0, ang_wall),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 2. Drawbridge Deck
    # Base longitudinal timber beams
    n_beams = max(3, int(width / 0.70))
    b_step = (width - 0.24) / max(1, n_beams - 1)
    deck_thick = 0.14
    for bi in range(n_beams):
        lx = -width * 0.5 + 0.12 + bi * b_step
        b_mid = p_hinge + (rot_mat @ Vector((lx, length * 0.5, deck_thick * 0.5))).to_3d()
        create_beveled_box(bm, size=(0.14, length, deck_thick),
                           location=(b_mid.x, b_mid.y, b_mid.z),
                           rotation=rot_euler,
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Cross transverse oak planks
    plank_thick = 0.06
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
                           location=(hx, hy, z_ground + 0.06),
                           rotation=(0.0, 0.0, ang_wall),
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.008)

    # 3. Forged Iron Suspension Chains
    if has_chains:
        p_corner_L = p_hinge + (rot_mat @ Vector((-width * 0.5 + 0.15, length - 0.20, deck_thick + plank_thick + 0.04))).to_3d()
        p_corner_R = p_hinge + (rot_mat @ Vector((width * 0.5 - 0.15, length - 0.20, deck_thick + plank_thick + 0.04))).to_3d()

        # Eyelets on bridge corners
        for cp in (p_corner_L, p_corner_R):
            create_torus_ring(bm, location=cp, rotation=rot_euler,
                              major_radius=0.075, minor_radius=0.016, mat_index=MAT_INDEX_IRON)

        # High chain portals in gate piers
        chain_h = max(2.6, pier_h + 0.35)
        p_wall_L = Vector((cx, cy, z_ground + chain_h)) + Vector((tx, ty, 0.0)) * (-width * 0.5 - 0.45) + Vector((ox, oy, 0.0)) * 0.20
        p_wall_R = Vector((cx, cy, z_ground + chain_h)) + Vector((tx, ty, 0.0)) * (width * 0.5 + 0.45) + Vector((ox, oy, 0.0)) * 0.20

        # Wall hawse brackets
        for wp in (p_wall_L, p_wall_R):
            create_beveled_box(bm, size=(0.28, 0.28, 0.28),
                               location=(wp.x, wp.y, wp.z),
                               rotation=(0.0, 0.0, ang_wall),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
            create_torus_ring(bm, location=wp + Vector((ox * 0.15, oy * 0.15, 0.0)),
                              rotation=(1.5708, 0.0, ang_wall),
                              major_radius=0.080, minor_radius=0.018, mat_index=MAT_INDEX_IRON)

        # Run interlocking 3D chains
        build_chain_run(bm, p_corner_L, p_wall_L, major_r=0.062, minor_r=0.014, pitch=0.084)
        build_chain_run(bm, p_corner_R, p_wall_R, major_r=0.062, minor_r=0.014, pitch=0.084)


def build_flanking_gate_towers(bm, cx, cy, z_ground=0.0, gap_w=2.8, wall_h=3.2,
                               wall_t=0.55, outward=(0.0, -1.0), tower_r=1.90, tower_h=None):
    """Twin semicircular / D-shaped flanking bastion gate towers projecting forward
    from the curtain wall with arrow slits, cut-stone corbels and crenellated tops."""
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

        # Parapet merlon runs around the 3 exposed sides
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
