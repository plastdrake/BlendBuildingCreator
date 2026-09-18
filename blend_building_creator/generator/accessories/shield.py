"""Reusable fantasy round shields with iron boss and heraldic paint patterns.

Can be mounted on palisades, rampart walks, or exterior walls (e.g. Norse longhouse
and military barracks aesthetic).
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import create_cylinder, create_cone, create_beveled_box
from ..materials import (
    MAT_INDEX_IRON, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_BANNER,
)


def _basis_from_normal(normal):
    """Build an orthonormal basis (right, up, forward) from a forward normal vector."""
    fn = Vector(normal).normalized()
    if fn.length < 1e-4:
        fn = Vector((0.0, -1.0, 0.0))
    # Reference up vector
    if abs(fn.z) > 0.95:
        up_ref = Vector((0.0, 1.0, 0.0))
    else:
        up_ref = Vector((0.0, 0.0, 1.0))
    right = up_ref.cross(fn).normalized()
    up = fn.cross(right).normalized()
    return right, up, fn


def build_round_shield(bm, location, normal=(0.0, -1.0, 0.0), radius=0.36,
                       pattern='QUARTERED', rim_mat=MAT_INDEX_IRON, wood_mat=MAT_INDEX_WOOD,
                       paint_mat=MAT_INDEX_BANNER):
    """A detailed fantasy round shield with an outer iron rim, wooden body planks,
    rivets, and a central domed iron boss (umbo).
    """
    rx, ry, rz = location
    right, up, fn = _basis_from_normal(normal)

    # 4x4 matrix mapping local: X = right, Y = up, Z = forward (along normal)
    rot_mat = Matrix([
        [right.x, up.x, fn.x, 0.0],
        [right.y, up.y, fn.y, 0.0],
        [right.z, up.z, fn.z, 0.0],
        [0.0,     0.0,  0.0,  1.0]
    ])
    loc_mat = Matrix.Translation(Vector((rx, ry, rz)))
    tr = loc_mat @ rot_mat

    # 1. Wooden backing disc (radius slightly inside rim)
    body_r = radius * 0.96
    body_t = 0.032
    segments = 16
    uv_layer = bm.loops.layers.uv.verify()

    # Create front and back vertices for the wooden shield face
    front_verts = []
    back_verts = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        # Slight dome convex curve toward the center
        dome_z = (1.0 - (math.hypot(ca, sa) * 0.5)) * 0.015
        vf = tr @ Vector((body_r * ca, body_r * sa, body_t * 0.5 + dome_z))
        vb = tr @ Vector((body_r * ca, body_r * sa, -body_t * 0.5))
        front_verts.append(bm.verts.new(vf))
        back_verts.append(bm.verts.new(vb))

    # Center vertex for pie-slice plank construction
    c_front = bm.verts.new(tr @ Vector((0.0, 0.0, body_t * 0.5 + 0.018)))
    c_back = bm.verts.new(tr @ Vector((0.0, 0.0, -body_t * 0.5)))

    # Build front pie faces with alternating quartered / wood materials
    for i in range(segments):
        nxt = (i + 1) % segments
        f_quadrant = int((i + 1) / (segments / 4)) % 2
        mat = paint_mat if (pattern == 'QUARTERED' and f_quadrant == 1) else wood_mat
        f = bm.faces.new([c_front, front_verts[i], front_verts[nxt]])
        f.material_index = mat
        f.tag = True
        # Radial UV
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        f.loops[0][uv_layer].uv = Vector((0.5, 0.5))
        f.loops[1][uv_layer].uv = Vector((0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0)))
        f.loops[2][uv_layer].uv = Vector((0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1)))

        # Back face (facing back)
        fb = bm.faces.new([c_back, back_verts[nxt], back_verts[i]])
        fb.material_index = MAT_INDEX_TIMBER
        fb.tag = True

        # Edge quad
        fe = bm.faces.new([front_verts[i], back_verts[i], back_verts[nxt], front_verts[nxt]])
        fe.material_index = rim_mat
        fe.tag = True

    # 2. Outer forged iron rim with bevel
    rim_w = 0.038
    rim_t = 0.042
    for i in range(segments):
        nxt = (i + 1) % segments
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        ca0, sa0 = math.cos(a0), math.sin(a0)
        ca1, sa1 = math.cos(a1), math.sin(a1)

        r_inner = body_r - 0.012
        r_outer = radius + 0.012

        p_v0 = tr @ Vector((r_inner * ca0, r_inner * sa0, body_t * 0.5 + 0.008))
        p_v1 = tr @ Vector((r_outer * ca0, r_outer * sa0, body_t * 0.5 + 0.004))
        p_v2 = tr @ Vector((r_outer * ca1, r_outer * sa1, body_t * 0.5 + 0.004))
        p_v3 = tr @ Vector((r_inner * ca1, r_inner * sa1, body_t * 0.5 + 0.008))

        rf = bm.faces.new([bm.verts.new(v) for v in (p_v0, p_v1, p_v2, p_v3)])
        rf.material_index = rim_mat
        rf.tag = True

    # 3. Central Domed Iron Boss (Umbo)
    boss_r = radius * 0.28
    boss_h = 0.068
    boss_c = tr @ Vector((0.0, 0.0, body_t * 0.5 + 0.018))
    # Flange ring
    flange_r = boss_r * 1.35
    flange_t = 0.015
    for i in range(12):
        nxt = (i + 1) % 12
        a0 = 2.0 * math.pi * i / 12
        a1 = 2.0 * math.pi * (i + 1) / 12
        ca0, sa0 = math.cos(a0), math.sin(a0)
        ca1, sa1 = math.cos(a1), math.sin(a1)
        p0 = tr @ Vector((boss_r * 0.6 * ca0, boss_r * 0.6 * sa0, body_t * 0.5 + 0.02))
        p1 = tr @ Vector((flange_r * ca0, flange_r * sa0, body_t * 0.5 + 0.016))
        p2 = tr @ Vector((flange_r * ca1, flange_r * sa1, body_t * 0.5 + 0.016))
        p3 = tr @ Vector((boss_r * 0.6 * ca1, boss_r * 0.6 * sa1, body_t * 0.5 + 0.02))
        fl_f = bm.faces.new([bm.verts.new(v) for v in (p0, p1, p2, p3)])
        fl_f.material_index = rim_mat
        fl_f.tag = True

    # Domed hemisphere cap
    dome_apex = tr @ Vector((0.0, 0.0, body_t * 0.5 + 0.018 + boss_h))
    v_apex = bm.verts.new(dome_apex)
    dome_rim_verts = []
    for i in range(12):
        a = 2.0 * math.pi * i / 12
        v = tr @ Vector((boss_r * math.cos(a), boss_r * math.sin(a), body_t * 0.5 + 0.024))
        dome_rim_verts.append(bm.verts.new(v))
    for i in range(12):
        nxt = (i + 1) % 12
        df = bm.faces.new([v_apex, dome_rim_verts[i], dome_rim_verts[nxt]])
        df.material_index = rim_mat
        df.tag = True

    # 4. Perimeter Rivet Studs around the iron boss flange
    for r_idx in range(6):
        ra = 2.0 * math.pi * r_idx / 6
        rcx = (boss_r + flange_r) * 0.5 * math.cos(ra)
        rcy = (boss_r + flange_r) * 0.5 * math.sin(ra)
        rv_pos = tr @ Vector((rcx, rcy, body_t * 0.5 + 0.022))
        # Small 4-sided pyramid / cone rivet
        rv_cone = create_cone(bm, radius1=0.014, radius2=0.004, height=0.014, segments=6,
                              location=(rv_pos.x, rv_pos.y, rv_pos.z),
                              rotation=(fn.x, fn.y, fn.z), mat_index=rim_mat)
        for f in rv_cone:
            f.tag = True


def build_shield_row(bm, p0, p1, z, normal=(0.0, -1.0, 0.0), spacing=1.25,
                     radius=0.34, skip_gap=None):
    """Distribute round shields evenly along a horizontal segment (p0 to p1).
    Used to line palisade walls, rampart railings, or stone barriers (Concept 2).
    """
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    total_len = math.hypot(dx, dy)
    if total_len < 1.0:
        return

    n_shields = max(1, int(round(total_len / spacing)))
    step = total_len / n_shields
    ux, uy = dx / total_len, dy / total_len

    for i in range(n_shields):
        dist = (i + 0.5) * step
        sx = x0 + ux * dist
        sy = y0 + uy * dist

        # Skip gate gap if specified
        if skip_gap is not None:
            g0, g1 = skip_gap
            if g0 <= sx <= g1:
                continue

        # Mount shield offset along outward normal so it sits flush on the outer face of pickets
        nx, ny = normal[0], normal[1]
        mx = sx + nx * 0.16
        my = sy + ny * 0.16
        build_round_shield(bm, (mx, my, z), normal=normal, radius=radius,
                           pattern='QUARTERED' if (i % 2 == 0) else 'SOLID')
