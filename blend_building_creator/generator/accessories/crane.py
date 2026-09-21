import math
from mathutils import Vector
from ..facade import get_facade_frame
from ..uv_utils import map_planar_faces
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
)

def build_courtyard_crane(bm, yard_x, yard_y, z_ground=0.0, mast_height=4.0, jib_length=3.4, rot_angle=0.45,
                          pad_mat=None, include_stone_pad=True, pad_radius=None):
    cos_r = math.cos(rot_angle)
    sin_r = math.sin(rot_angle)
    boom_dir = Vector((cos_r, sin_r, 0.0))
    side_dir = Vector((-sin_r, cos_r, 0.0))

    def _beam(p1, p2, width, mat, bevel=0.012):
        v1 = Vector(p1)
        v2 = Vector(p2)
        d = v2 - v1
        length = max(0.05, d.length)
        mid = (v1 + v2) * 0.5
        rot = d.to_track_quat('Z', 'Y').to_euler()
        create_beveled_box(
            bm, size=(width, width, length),
            location=(mid.x, mid.y, mid.z),
            rotation=rot, mat_index=mat, bevel_amount=bevel
        )
        return mid

    def _cyl_axis(p, radius, height, axis_vec, mat, segments=10):
        axis = Vector(axis_vec).normalized()
        rot = axis.to_track_quat('Z', 'Y').to_euler()
        create_cylinder(
            bm, radius=radius, height=height, segments=segments,
            location=(p[0], p[1], p[2]), rotation=rot, mat_index=mat
        )

    if include_stone_pad:
        pad_h = 0.16
        pad_r = pad_radius if pad_radius is not None else 1.30
        _pad_mat = pad_mat if pad_mat is not None else MAT_INDEX_CUT_STONE
        create_cylinder(
            bm, radius=pad_r, height=pad_h, segments=24,
            location=(yard_x, yard_y, z_ground + pad_h * 0.5),
            mat_index=_pad_mat
        )
        ring_r = pad_r * 0.78
    else:
        pad_h = 0.0
        pad_r = pad_radius if pad_radius is not None else 0.72
        ring_r = pad_r

    ring_h = 0.07
    ring_z = z_ground + pad_h + ring_h * 0.5
    create_cylinder(
        bm, radius=ring_r, height=ring_h, segments=24,
        location=(yard_x, yard_y, ring_z),
        mat_index=MAT_INDEX_IRON
    )
    disc_h = 0.15
    disc_r = ring_r * 0.92
    disc_z = z_ground + pad_h + ring_h + disc_h * 0.5
    create_cylinder(
        bm, radius=disc_r, height=disc_h, segments=16,
        location=(yard_x, yard_y, disc_z),
        mat_index=MAT_INDEX_TIMBER
    )
    create_cylinder(
        bm, radius=disc_r + 0.015, height=0.07, segments=16,
        location=(yard_x, yard_y, z_ground + pad_h + ring_h + 0.035),
        mat_index=MAT_INDEX_IRON
    )
    create_cylinder(
        bm, radius=0.07, height=0.30, segments=8,
        location=(yard_x, yard_y, z_ground + pad_h + ring_h + 0.10),
        mat_index=MAT_INDEX_IRON
    )

    mast_z0 = z_ground + pad_h + ring_h + disc_h
    mast_w = 0.38
    mast_mid_z = mast_z0 + mast_height * 0.5
    create_beveled_box(
        bm, size=(mast_w, mast_w, mast_height),
        location=(yard_x, yard_y, mast_mid_z),
        rotation=(0.0, 0.0, rot_angle),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.02
    )
    for fz in [0.55, 1.55, mast_height - 0.35]:
        create_beveled_box(
            bm, size=(mast_w + 0.06, mast_w + 0.06, 0.10),
            location=(yard_x, yard_y, mast_z0 + fz),
            rotation=(0.0, 0.0, rot_angle),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.008
        )
    create_beveled_box(
        bm, size=(mast_w + 0.12, mast_w + 0.12, 0.14),
        location=(yard_x, yard_y, mast_z0 + mast_height + 0.07),
        rotation=(0.0, 0.0, rot_angle),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    create_cylinder(
        bm, radius=0.05, height=0.22, segments=8,
        location=(yard_x, yard_y, mast_z0 + mast_height + 0.24),
        mat_index=MAT_INDEX_IRON
    )

    brace_h = 1.15
    brace_dist = min(0.68, disc_r * 0.78)
    for i in range(4):
        ang = rot_angle + math.pi * 0.25 + i * (math.pi * 0.5)
        ca = math.cos(ang)
        sa = math.sin(ang)
        foot = (yard_x + ca * brace_dist, yard_y + sa * brace_dist, mast_z0 + 0.02)
        head = (yard_x + ca * (mast_w * 0.32), yard_y + sa * (mast_w * 0.32), mast_z0 + brace_h)
        _beam(foot, head, 0.17, MAT_INDEX_TIMBER, bevel=0.01)

    jib_elev = math.radians(16.0)
    attach_z = mast_z0 + mast_height - 0.75
    root = Vector((yard_x, yard_y, attach_z))
    boom_d = Vector((cos_r * math.cos(jib_elev), sin_r * math.cos(jib_elev), math.sin(jib_elev)))
    tip = root + boom_d * jib_length
    _beam(root - boom_d * 0.25, tip, 0.30, MAT_INDEX_TIMBER_FRAME, bevel=0.015)
    tail_end = root - Vector((cos_r, sin_r, -0.06)).normalized() * 1.0
    _beam(root - boom_d * 0.2, tail_end, 0.26, MAT_INDEX_TIMBER_FRAME, bevel=0.015)
    cw_c = (tail_end.x, tail_end.y, tail_end.z - 0.12)
    create_beveled_box(
        bm, size=(0.50, 0.42, 0.58),
        location=cw_c,
        rotation=(0.0, 0.0, rot_angle),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    for dz in (-0.16, 0.14):
        create_beveled_box(
            bm, size=(0.53, 0.45, 0.09),
            location=(cw_c[0], cw_c[1], cw_c[2] + dz),
            rotation=(0.0, 0.0, rot_angle),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.006
        )
    create_beveled_box(
        bm, size=(0.10, 0.45, 0.61),
        location=cw_c,
        rotation=(0.0, 0.0, rot_angle),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006
    )
    for t in (0.35, 0.62, 0.88):
        pos = root + boom_d * (jib_length * t)
        rot_q = boom_d.to_track_quat('Z', 'Y').to_euler()
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.10),
            location=(pos.x, pos.y, pos.z),
            rotation=rot_q, mat_index=MAT_INDEX_IRON, bevel_amount=0.006
        )
    for s in (-1.0, 1.0):
        out_axis = side_dir * s
        out_rot = out_axis.to_track_quat('Z', 'Y').to_euler()
        hub = root + side_dir * (s * (mast_w * 0.5 + 0.045))
        _cyl_axis((hub.x, hub.y, hub.z), 0.23, 0.07, side_dir, MAT_INDEX_IRON, segments=16)
        rim_c = hub + out_axis * 0.035
        create_torus_ring(
            bm, location=(rim_c.x, rim_c.y, rim_c.z), rotation=out_rot,
            major_radius=0.185, minor_radius=0.024, major_segments=16, minor_segments=8,
            mat_index=MAT_INDEX_IRON
        )
        _cyl_axis((hub.x, hub.y, hub.z), 0.085, 0.13, side_dir, MAT_INDEX_IRON, segments=12)
        dome_c = hub + out_axis * (0.065 + 0.03)
        create_cone(
            bm, radius1=0.055, radius2=0.012, height=0.06, segments=10,
            location=(dome_c.x, dome_c.y, dome_c.z), rotation=out_rot,
            mat_index=MAT_INDEX_IRON
        )
    low_pt = Vector((yard_x + cos_r * (mast_w * 0.4), yard_y + sin_r * (mast_w * 0.4), attach_z - 1.55))
    high_pt = root + boom_d * (jib_length * 0.58) - Vector((0.0, 0.0, 0.16))
    _beam(low_pt, high_pt, 0.18, MAT_INDEX_TIMBER, bevel=0.01)
    jib_tip_x, jib_tip_y, jib_tip_z = tip.x, tip.y, tip.z
    tip_q = boom_d.to_track_quat('Z', 'Y').to_euler()
    create_beveled_box(
        bm, size=(0.30, 0.10, 0.34),
        location=(jib_tip_x, jib_tip_y, jib_tip_z - 0.10),
        rotation=tip_q, mat_index=MAT_INDEX_IRON, bevel_amount=0.005
    )
    _cyl_axis((jib_tip_x, jib_tip_y, jib_tip_z - 0.10), 0.16, 0.07, side_dir, MAT_INDEX_WOOD, segments=12)
    _cyl_axis((jib_tip_x, jib_tip_y, jib_tip_z - 0.10), 0.035, 0.24, side_dir, MAT_INDEX_IRON, segments=8)
    winch_z = mast_z0 + 1.05
    wheel_off = 0.58
    _cyl_axis((yard_x, yard_y, winch_z), 0.16, 0.62, side_dir, MAT_INDEX_TIMBER, segments=12)
    _cyl_axis((yard_x, yard_y, winch_z), 0.185, 0.40, side_dir, MAT_INDEX_TIMBER, segments=12)
    _cyl_axis((yard_x, yard_y, winch_z), 0.045, wheel_off * 2.0 + 0.16, side_dir, MAT_INDEX_IRON, segments=8)
    wheel_c = Vector((yard_x, yard_y, winch_z)) + side_dir * wheel_off
    wheel_rot = side_dir.to_track_quat('Z', 'Y').to_euler()
    create_torus_ring(
        bm, location=(wheel_c.x, wheel_c.y, wheel_c.z), rotation=wheel_rot,
        major_radius=0.46, minor_radius=0.05, major_segments=18, minor_segments=8,
        mat_index=MAT_INDEX_IRON
    )
    for k in range(4):
        a = k * math.pi * 0.5 + math.pi * 0.25
        off = boom_dir * math.cos(a) * 0.42 + Vector((0.0, 0.0, 1.0)) * math.sin(a) * 0.42
        _beam(wheel_c - off, wheel_c + off, 0.055, MAT_INDEX_IRON, bevel=0.004)
    _cyl_axis((wheel_c.x, wheel_c.y, wheel_c.z), 0.085, 0.14, side_dir, MAT_INDEX_IRON, segments=10)
    cable_h = 2.0
    cable_mid_z = jib_tip_z - 0.25 - cable_h * 0.5
    create_cylinder(
        bm, radius=0.018, height=cable_h, segments=6,
        location=(jib_tip_x, jib_tip_y, cable_mid_z),
        mat_index=MAT_INDEX_WOOD
    )
    hook_top_z = cable_mid_z - cable_h * 0.5
    create_cylinder(
        bm, radius=0.055, height=0.03, segments=10,
        location=(jib_tip_x, jib_tip_y, hook_top_z),
        rotation=(math.pi * 0.5, 0.0, rot_angle),
        mat_index=MAT_INDEX_IRON
    )
    shank_h = 0.18
    create_cylinder(
        bm, radius=0.030, height=shank_h, segments=8,
        location=(jib_tip_x, jib_tip_y, hook_top_z - shank_h * 0.5),
        mat_index=MAT_INDEX_IRON
    )
    throat_r = 0.11
    center_y = jib_tip_y + cos_r * throat_r
    center_x = jib_tip_x - sin_r * throat_r
    center_z = hook_top_z - shank_h
    arc_segs = 8
    for step in range(arc_segs):
        t1 = step / float(arc_segs)
        t2 = (step + 1) / float(arc_segs)
        phi1 = -math.pi + t1 * math.pi
        phi2 = -math.pi + t2 * math.pi
        c1x = center_x - sin_r * throat_r * math.cos(phi1)
        c1y = center_y + cos_r * throat_r * math.cos(phi1)
        c1z = center_z + throat_r * math.sin(phi1)
        c2x = center_x - sin_r * throat_r * math.cos(phi2)
        c2y = center_y + cos_r * throat_r * math.cos(phi2)
        c2z = center_z + throat_r * math.sin(phi2)
        seg_len = math.sqrt((c2x-c1x)**2 + (c2y-c1y)**2 + (c2z-c1z)**2)
        _cyl_axis(((c1x+c2x)*0.5, (c1y+c2y)*0.5, (c1z+c1z)*0.5),
                      0.028 * (1.0 - t1 * 0.3), seg_len + 0.01,
                      (c2x-c1x, c2y-c1y, c2z-c1z), MAT_INDEX_IRON, segments=6)


def build_wall_jib_crane(bm, wall_x, wall_y, z_mount, outward_dir=(1.0, 0.0), jib_len=2.8):
    """
    Builds a cantilevered timber jib crane mounted on an upper-floor wall/portal:
    - Vertical wall bracket post attached to the wall with iron strapping plates.
    - Horizontal heavy timber boom extending outward_dir over the loading dock.
    - 45-degree diagonal under-brace strut supporting the boom.
    - Iron pulley wheel at the jib tip with hanging rope and forged iron cargo hook.
    - Hand winch wheel and crank mechanism on the wall bracket.
    """
    ox, oy = outward_dir
    d_len = math.sqrt(ox * ox + oy * oy)
    if d_len > 0.001:
        ox /= d_len
        oy /= d_len
    else:
        ox, oy = 1.0, 0.0

    rot_z = math.atan2(oy, ox)
    side_x, side_y = -oy, ox

    # 1. Vertical wall bracket post
    bracket_h = 2.4
    bracket_w = 0.22
    create_beveled_box(
        bm, size=(bracket_w, bracket_w, bracket_h),
        location=(wall_x + ox * 0.08, wall_y + oy * 0.08, z_mount - 0.2),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    # Iron mounting wall straps
    for sz in (-0.9, 0.1, 0.8):
        create_beveled_box(
            bm, size=(bracket_w + 0.05, bracket_w + 0.05, 0.09),
            location=(wall_x + ox * 0.08, wall_y + oy * 0.08, z_mount - 0.2 + sz),
            rotation=(0.0, 0.0, rot_z),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.005
        )

    # 2. Horizontal cantilever boom
    boom_w = 0.20
    boom_h = 0.22
    boom_cx = wall_x + ox * (jib_len * 0.5 + 0.08)
    boom_cy = wall_y + oy * (jib_len * 0.5 + 0.08)
    boom_cz = z_mount + 0.85
    create_beveled_box(
        bm, size=(jib_len, boom_w, boom_h),
        location=(boom_cx, boom_cy, boom_cz),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )

    # 3. 45-degree diagonal under-brace strut
    strut_run = min(1.6, jib_len * 0.65)
    strut_len = math.sqrt(strut_run * strut_run * 2.0)
    strut_cx = wall_x + ox * (strut_run * 0.5 + 0.08)
    strut_cy = wall_y + oy * (strut_run * 0.5 + 0.08)
    strut_cz = boom_cz - strut_run * 0.5
    # Rotation: pitch 45 deg, yaw rot_z
    pitch = 0.785398
    create_beveled_box(
        bm, size=(strut_len, 0.16, 0.16),
        location=(strut_cx, strut_cy, strut_cz),
        rotation=(0.0, -pitch, rot_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )

    # 4. Iron Pulley Wheel at jib tip
    tip_x = wall_x + ox * (jib_len + 0.02)
    tip_y = wall_y + oy * (jib_len + 0.02)
    tip_z = boom_cz
    create_torus_ring(
        bm, location=(tip_x, tip_y, tip_z),
        rotation=(1.5708, 0.0, rot_z),
        major_radius=0.18, minor_radius=0.03,
        major_segments=12, minor_segments=6,
        mat_index=MAT_INDEX_IRON
    )

    # 5. Hanging Rope and Hook
    rope_h = 2.4
    rope_cz = tip_z - 0.20 - rope_h * 0.5
    create_cylinder(
        bm, radius=0.016, height=rope_h, segments=6,
        location=(tip_x, tip_y, rope_cz),
        mat_index=MAT_INDEX_WOOD
    )
    hook_z = rope_cz - rope_h * 0.5 - 0.12
    create_cylinder(
        bm, radius=0.045, height=0.18, segments=8,
        location=(tip_x, tip_y, hook_z),
        mat_index=MAT_INDEX_IRON
    )
    # Curved hook loop
    create_torus_ring(
        bm, location=(tip_x, tip_y, hook_z - 0.10),
        rotation=(0.0, 1.5708, rot_z),
        major_radius=0.09, minor_radius=0.022,
        major_segments=10, minor_segments=6,
        mat_index=MAT_INDEX_IRON
    )

    # 6. Hand winch wheel on the bracket post
    winch_z = z_mount - 0.35
    winch_x = wall_x + ox * 0.08 + side_x * 0.18
    winch_y = wall_y + oy * 0.08 + side_y * 0.18
    create_torus_ring(
        bm, location=(winch_x, winch_y, winch_z),
        rotation=(0.0, 1.5708, rot_z),
        major_radius=0.28, minor_radius=0.03,
        major_segments=12, minor_segments=6,
        mat_index=MAT_INDEX_IRON
    )
    # Winch axle & crank
    create_cylinder(
        bm, radius=0.04, height=0.35, segments=8,
        location=(wall_x + ox * 0.08, wall_y + oy * 0.08, winch_z),
        rotation=(1.5708, 0.0, rot_z),
        mat_index=MAT_INDEX_IRON
    )
