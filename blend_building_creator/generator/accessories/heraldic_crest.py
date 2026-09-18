"""Reusable heraldic crest with crossed broadswords and shield plaque.

Mounted on roof gables, dormers, or above gate arches (Concept 1 military barracks).
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_IRON, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_BANNER, MAT_INDEX_CUT_STONE,
)


def _basis_from_normal(normal):
    """Build an orthonormal basis (right, up, forward) from a forward normal vector."""
    fn = Vector(normal).normalized()
    if fn.length < 1e-4:
        fn = Vector((0.0, -1.0, 0.0))
    if abs(fn.z) > 0.95:
        up_ref = Vector((0.0, 1.0, 0.0))
    else:
        up_ref = Vector((0.0, 0.0, 1.0))
    right = up_ref.cross(fn).normalized()
    up = fn.cross(right).normalized()
    return right, up, fn


def _build_sword(bm, tr, angle=45.0, scale=1.0):
    """Build a medieval broadsword lying in the crest plane (blade up, thickness
    across the wall). The sword is rotated about the wall normal by ``angle`` so
    the pair crosses behind the shield instead of poking out of the facade."""
    rad = math.radians(angle)
    # In-plane rotation about the outward normal (local Z = forward).
    str_mat = tr @ Matrix.Rotation(rad, 4, 'Z')
    str_eul = str_mat.to_euler('XYZ')
    str_rot3 = str_mat.to_3x3()

    def loc(x, y, z):
        return str_mat @ Vector((x, y, z))

    y_axis = (str_rot3 @ Vector((0.0, 1.0, 0.0))).normalized()
    z_axis = (str_rot3 @ Vector((0.0, 0.0, 1.0))).normalized()
    y_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(y_axis).to_euler()
    z_rot = Vector((0.0, 0.0, 1.0)).rotation_difference(z_axis).to_euler()

    # 1. Double-edged blade, length along local Y, thickness along local Z.
    blade_len = 1.35 * scale
    blade_w = 0.09 * scale
    blade_t = 0.022 * scale
    y0 = 0.10 * scale
    tip_y = y0 + blade_len
    blade_mid = (y0 + tip_y) * 0.5
    b_verts = [
        loc(-blade_w * 0.5, y0, 0.0),
        loc(-blade_w * 0.45, y0 + blade_len * 0.82, 0.0),
        loc(0.0, tip_y, 0.0),
        loc(blade_w * 0.45, y0 + blade_len * 0.82, 0.0),
        loc(blade_w * 0.5, y0, 0.0),
    ]
    vf_c = bm.verts.new(loc(0.0, blade_mid, blade_t * 0.5))
    vb_c = bm.verts.new(loc(0.0, blade_mid, -blade_t * 0.5))
    bm_v = [bm.verts.new(v) for v in b_verts]
    for i in range(4):
        f = bm.faces.new([vf_c, bm_v[i], bm_v[i + 1]])
        f.material_index = MAT_INDEX_IRON
        f.tag = True
        fb = bm.faces.new([vb_c, bm_v[i + 1], bm_v[i]])
        fb.material_index = MAT_INDEX_IRON
        fb.tag = True

    # 2. Forged iron crossguard (across the blade, local X).
    guard_w = 0.38 * scale
    guard_t = 0.038 * scale
    g_faces = create_beveled_box(bm, size=(guard_w, guard_t, guard_t),
                                 location=loc(0.0, 0.09 * scale, 0.0),
                                 rotation=str_eul,
                                 mat_index=MAT_INDEX_IRON, bevel_amount=0.006 * scale)
    for f in g_faces:
        f.tag = True
    for sgn in (-1.0, 1.0):
        q_pos = loc(sgn * guard_w * 0.5, 0.09 * scale, 0.0)
        q_faces = create_cylinder(bm, radius=0.024 * scale, height=0.04 * scale, segments=6,
                                  location=(q_pos.x, q_pos.y, q_pos.z),
                                  rotation=z_rot, mat_index=MAT_INDEX_IRON)
        for f in q_faces:
            f.tag = True

    # 3. Grip / hilt below the guard (along the blade axis).
    grip_len = 0.22 * scale
    grip_pos = loc(0.0, 0.09 * scale - grip_len * 0.5, 0.0)
    h_faces = create_cylinder(bm, radius=0.022 * scale, height=grip_len, segments=8,
                              location=(grip_pos.x, grip_pos.y, grip_pos.z),
                              rotation=y_rot, mat_index=MAT_INDEX_WOOD)
    for f in h_faces:
        f.tag = True

    # 4. Faceted iron pommel at the hilt base.
    pommel_pos = loc(0.0, 0.09 * scale - grip_len, 0.0)
    pm_faces = create_cylinder(bm, radius=0.038 * scale, height=0.045 * scale, segments=8,
                               location=(pommel_pos.x, pommel_pos.y, pommel_pos.z),
                               rotation=y_rot, mat_index=MAT_INDEX_IRON)
    for f in pm_faces:
        f.tag = True


def build_gable_heraldic_crest(bm, location, normal=(0.0, -1.0, 0.0), scale=1.0,
                               style='CROSSED_SWORDS'):
    """An ornamental heraldic cartouche plaque with crossed broadswords mounted on a gable."""
    rx, ry, rz = location
    right, up, fn = _basis_from_normal(normal)

    # 4x4 coordinate frame: X = right, Y = up, Z = outward forward
    rot_mat = Matrix([
        [right.x, up.x, fn.x, 0.0],
        [right.y, up.y, fn.y, 0.0],
        [right.z, up.z, fn.z, 0.0],
        [0.0,     0.0,  0.0,  1.0]
    ])
    loc_mat = Matrix.Translation(Vector((rx, ry, rz)))
    tr = loc_mat @ rot_mat

    # 1. Two crossed broadswords behind the shield (at +45° and -45°)
    if style == 'CROSSED_SWORDS':
        _build_sword(bm, tr, angle=45.0, scale=scale)
        _build_sword(bm, tr, angle=-45.0, scale=scale)

    # 2. Mounted Heraldic Heater Shield Plaque in front
    sw = 0.54 * scale
    sh = 0.68 * scale
    st = 0.05 * scale
    # Shield front position offset slightly outward along normal (Z)
    s_verts_local = [
        Vector((-sw * 0.5,  sh * 0.5,  st * 0.5 + 0.02)), # Top-left
        Vector((-sw * 0.5,  0.0,       st * 0.5 + 0.02)), # Mid-left
        Vector((0.0,       -sh * 0.5,  st * 0.5 + 0.02)), # Bottom V-apex
        Vector(( sw * 0.5,  0.0,       st * 0.5 + 0.02)), # Mid-right
        Vector(( sw * 0.5,  sh * 0.5,  st * 0.5 + 0.02)), # Top-right
        Vector((0.0,        sh * 0.54, st * 0.5 + 0.02)), # Top-center crest point
    ]
    # Back vertices against wall
    s_verts_back = [
        Vector((v.x, v.y, -st * 0.5)) for v in s_verts_local
    ]

    front_v = [bm.verts.new(tr @ v) for v in s_verts_local]
    back_v  = [bm.verts.new(tr @ v) for v in s_verts_back]

    uv_layer = bm.loops.layers.uv.verify()

    # Front face (CCW: 0, 1, 2, 3, 4, 5)
    f_front = bm.faces.new([front_v[0], front_v[1], front_v[2], front_v[3], front_v[4], front_v[5]])
    f_front.material_index = MAT_INDEX_BANNER
    f_front.tag = True
    f_front.loops[0][uv_layer].uv = Vector((0.15, 0.95))
    f_front.loops[1][uv_layer].uv = Vector((0.15, 0.45))
    f_front.loops[2][uv_layer].uv = Vector((0.50, 0.05))
    f_front.loops[3][uv_layer].uv = Vector((0.85, 0.45))
    f_front.loops[4][uv_layer].uv = Vector((0.85, 0.95))
    f_front.loops[5][uv_layer].uv = Vector((0.50, 1.00))

    # Back face
    f_back = bm.faces.new([back_v[5], back_v[4], back_v[3], back_v[2], back_v[1], back_v[0]])
    f_back.material_index = MAT_INDEX_WOOD
    f_back.tag = True

    # Rim border quads
    for i in range(6):
        nxt = (i + 1) % 6
        rim_f = bm.faces.new([front_v[i], back_v[i], back_v[nxt], front_v[nxt]])
        rim_f.material_index = MAT_INDEX_IRON
        rim_f.tag = True

    # 3. Decorative central iron boss & mounting studs
    boss_c = tr @ Vector((0.0, 0.0, st * 0.5 + 0.04))
    b_cone = create_cone(bm, radius1=0.065 * scale, radius2=0.0, height=0.055 * scale, segments=8,
                         location=(boss_c.x, boss_c.y, boss_c.z),
                         rotation=(fn.x, fn.y, fn.z), mat_index=MAT_INDEX_IRON)
    for f in b_cone:
        f.tag = True
