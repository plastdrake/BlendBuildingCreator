"""Dedicated artisan trade props: workstations and shop display goods.

Each of the eight artisan trades gets purpose-built furniture modelled once at
a local origin (footprint centred on X/Y, base at Z=0) and dropped with a
single yaw+translation transform, mirroring ``interior_furniture.py``
conventions exactly. Only MAT_INDEX_* slots are used.

Workstations (floor pieces for the craft rooms):
    BREAD_RACK, DOUGH_BOWL, MASH_TUN, KEG_RACK, BOTTLE_CRATE, BUTCHER_BLOCK,
    SAUSAGE_STRING, DRESS_FORM, CLOTH_BOLT_BIN, STRONGBOX, GEM_TRAY,
    BALANCE_SCALE, ANVIL, GRINDSTONE, TOOL_RACK, JOINER_BENCH, SAWBUCK,
    FISH, FISH_DRYING_RACK, ROPE_COIL, BREAD_LOAF
"""

import math
from mathutils import Matrix

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
    create_torus_ring, create_hollow_cylinder, create_hollow_dish,
    transform_faces,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON,
    MAT_INDEX_CLAY, MAT_INDEX_WAX, MAT_INDEX_FABRIC_WHITE,
    MAT_INDEX_FABRIC_RED, MAT_INDEX_FABRIC_STITCHED,
    MAT_INDEX_CLOTH_LINEN, MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_GLASS,
    MAT_INDEX_LEATHER, MAT_INDEX_BREAD, MAT_INDEX_WATER,
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_LOG,
    MAT_INDEX_ROPE,
)
from .furniture import build_barrel


def _place(x, y, z_ground=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _loaf(bm, faces, lx, ly, lz, yaw=0.0, length=0.30):
    """One crusty loaf: low base with a domed crown and pale slash cuts.

    Built axis-aligned in a sublist, then yawed rigidly (avoids composed
    Euler ambiguity between the barrel-laid crown and the loaf direction).
    """
    w = length * 0.58
    crown_r = length * 0.25
    crown_cz = 0.055 + crown_r - 0.030
    local = []
    # Base slab.
    local += create_beveled_box(
        bm, size=(length, w, 0.055),
        location=(0.0, 0.0, 0.0275),
        mat_index=MAT_INDEX_BREAD, bevel_amount=0.018
    )
    # Domed crown (barrel laid along the loaf).
    local += create_cylinder(
        bm, radius=crown_r, height=length * 0.92, segments=12,
        location=(0.0, 0.0, crown_cz),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_BREAD,
        smooth=True
    )
    # Pale slash cuts along the crown ridge.
    for i, sx in enumerate((-0.062, 0.0, 0.062)):
        local += create_beveled_box(
            bm, size=(0.080, 0.018, 0.012),
            location=(sx, 0.0, crown_cz + crown_r - 0.007),
            rotation=(0.0, 0.0, (0.35 if i % 2 else -0.35)),
            mat_index=MAT_INDEX_WAX, bevel_amount=0.002
        )
    # Flour-dusted pad the loaf sits on.
    local += create_beveled_box(
        bm, size=(length + 0.06, w + 0.05, 0.006),
        location=(0.0, 0.0, 0.003),
        mat_index=MAT_INDEX_WAX, bevel_amount=0.002
    )
    transform_faces(local,
                    Matrix.Translation((lx, ly, lz)) @ Matrix.Rotation(yaw, 4, 'Z'))
    faces += local
    return faces
    return faces


def build_bread_loaf(bm, x, y, z_ground=0.0, ang=0.0, length=0.30):
    """Single crusty loaf for counters and tables.

    Uses the artist's bread FBX (props/bread.fbx, textured by bread.png);
    falls back to the stylized domed loaf whenever the FBX cannot load.
    """
    try:
        if _build_fbx_prop(bm, 'bread.fbx', None, x, y, z_ground, ang,
                           length, _bread_fbx_mat(), long_axis='AUTO'):
            return True
    except Exception:
        pass
    faces = []
    _loaf(bm, faces, 0.0, 0.0, 0.0, yaw=0.0, length=length)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _bread_fbx_mat():
    from ..materials import MAT_INDEX_BREAD_FBX
    return MAT_INDEX_BREAD_FBX


def _stamp_baked_local(bm, faces, fbx_file, lx, ly, lz, yaw, length,
                       mat_index, long_axis='AUTO', pre_rot=(0.0, 0.0, 0.0),
                       pre_mat=None):
    """Stamp a baked mesh in a caller's LOCAL frame, appending the new faces
    to ``faces`` so they ride along with the caller's own final transform."""
    _n0 = len(bm.faces)
    try:
        if _build_fbx_prop(bm, fbx_file, None, lx, ly, lz, yaw, length,
                           mat_index, long_axis=long_axis, pre_rot=pre_rot,
                           pre_mat=pre_mat):
            faces += [f for f in list(bm.faces)[_n0:] if f.is_valid]
            return True
    except Exception:
        pass
    return False


def _stamp_bread(bm, faces, lx, ly, lz, yaw=0.0, length=0.30):
    """One loaf in a LOCAL frame: the baked artist bread when available,
    else the stylized domed loaf. Faces are appended to ``faces`` (local)."""
    if _stamp_baked_local(bm, faces, 'bread.fbx', lx, ly, lz, yaw, length,
                          _bread_fbx_mat(), long_axis='AUTO'):
        return faces
    local = []
    _loaf(bm, local, lx, ly, lz, yaw=yaw, length=length)
    faces += local
    return faces


def build_bread_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.50):
    """Baker's cooling rack: post frame with three loaf-laden shelves."""
    faces = []
    post_s = 0.07
    for sx in (-width * 0.5 + post_s * 0.5, width * 0.5 - post_s * 0.5):
        for sy in (-0.20, 0.20):
            faces += create_beveled_box(
                bm, size=(post_s, post_s, 1.15),
                location=(sx, sy, 0.575),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
            )
    # End X-braces (tilted in the vertical YZ plane).
    for sx in (-width * 0.5 + post_s * 0.5, width * 0.5 - post_s * 0.5):
        faces += create_beveled_box(
            bm, size=(0.05, 0.52, 0.05),
            location=(sx, 0.0, 0.575),
            rotation=(0.65, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    for si, sz in enumerate((0.32, 0.66, 1.00)):
        faces += create_beveled_box(
            bm, size=(width - 0.06, 0.46, 0.045),
            location=(0.0, 0.0, sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
        )
        n = max(2, int(width / 0.42))
        for i in range(n):
            lx = -width * 0.5 + 0.28 + i * ((width - 0.56) / max(1, n - 1))
            _stamp_bread(bm, faces, lx, 0.0, sz + 0.0225,
                         yaw=(0.12 if si % 2 else -0.10) + i * 0.05)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_dough_bowl(bm, x, y, z_ground=0.0, ang=0.0):
    """Clay proving bowl with a risen dough dome mounding over the rim."""
    faces = []
    faces += create_hollow_dish(
        bm, radius_base=0.075, radius_rim=0.150, inner_radius_rim=0.132,
        inner_radius_base=0.062, height=0.105, inner_depth=0.075,
        segments=18, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_CLAY,
        smooth=True
    )
    # Risen dough: soft stepped dome spilling over the rim (pale, smooth).
    for dr, dh, dz in ((0.105, 0.055, 0.055), (0.088, 0.045, 0.105),
                       (0.058, 0.040, 0.145)):
        faces += create_cylinder(
            bm, radius=dr, height=dh, segments=14,
            location=(0.0, 0.0, dz), mat_index=MAT_INDEX_WAX, smooth=True
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_mash_tun(bm, x, y, z_ground=0.0, ang=0.0, radius=0.55, height=1.00):
    """Brewer's open mash vat: staved tun with iron bands, celebrated wort
    surface and a leaning mash paddle."""
    faces = []
    faces += create_hollow_cylinder(
        bm, radius=radius, inner_radius=radius - 0.055, height=height,
        inner_depth=height - 0.10, segments=20,
        location=(0.0, 0.0, height * 0.5), mat_index=MAT_INDEX_WOOD,
        liquid_height=height - 0.32, liquid_mat_index=MAT_INDEX_WATER,
        smooth=True
    )
    # Iron hoops around the staves.
    for hz in (height * 0.22, height * 0.78):
        faces += create_torus_ring(
            bm, location=(0.0, 0.0, hz), rotation=(0.0, 0.0, 0.0),
            major_radius=radius + 0.008, minor_radius=0.020,
            major_segments=24, minor_segments=8, mat_index=MAT_INDEX_IRON
        )
    # Mash paddle leaning out of the tun.
    faces += create_cylinder(
        bm, radius=0.022, height=1.15, segments=8,
        location=(radius * 0.45, 0.0, height * 0.5 + 0.28),
        rotation=(0.0, 0.32, 0.0), mat_index=MAT_INDEX_WOOD
    )
    faces += create_beveled_box(
        bm, size=(0.16, 0.025, 0.30),
        location=(radius * 0.45 - 0.17, 0.0, height * 0.5 - 0.22),
        rotation=(0.0, 0.32, 0.0),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_keg_rack(bm, x, y, z_ground=0.0, ang=0.0, length=1.30):
    """Low rack with two tapped-ready lying kegs."""
    faces = []
    # Stand rails.
    for ry in (-0.24, 0.24):
        faces += create_beveled_box(
            bm, size=(length, 0.09, 0.12),
            location=(0.0, ry, 0.10),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )
    for rx in (-length * 0.5 + 0.10, length * 0.5 - 0.10):
        faces += create_beveled_box(
            bm, size=(0.10, 0.57, 0.08),
            location=(rx, 0.0, 0.04),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
    # Two lying kegs side by side on the rails.
    for kx in (-length * 0.25, length * 0.25):
        faces += build_barrel(bm, kx, 0.0, 0.16, 0.0,
                              radius=0.27, height=0.58, lying=True)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _bottle(bm, faces, lx, ly, lz):
    """One bottled brew with cork."""
    faces += create_cylinder(
        bm, radius=0.046, height=0.190, segments=10,
        location=(lx, ly, lz + 0.095), mat_index=MAT_INDEX_BOTTLE_GLASS,
        smooth=True
    )
    faces += create_cylinder(
        bm, radius=0.016, height=0.085, segments=8,
        location=(lx, ly, lz + 0.190 + 0.0425), mat_index=MAT_INDEX_BOTTLE_GLASS,
        smooth=True
    )
    faces += create_cylinder(
        bm, radius=0.014, height=0.030, segments=8,
        location=(lx, ly, lz + 0.275 + 0.015), mat_index=MAT_INDEX_WAX
    )
    return faces


def build_bottle_crate(bm, x, y, z_ground=0.0, ang=0.0):
    """Open slatted crate with six bottled brews, for shop counters."""
    faces = []
    w, d, wall_h, wall_t = 0.52, 0.36, 0.22, 0.035
    faces += create_beveled_box(
        bm, size=(w, d, 0.04),
        location=(0.0, 0.0, 0.02),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
    )
    for sy in (-d * 0.5 + wall_t * 0.5, d * 0.5 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(w, wall_t, wall_h),
            location=(0.0, sy, wall_h * 0.5 + 0.04),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
    for sx in (-w * 0.5 + wall_t * 0.5, w * 0.5 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t, d, wall_h),
            location=(sx, 0.0, wall_h * 0.5 + 0.04),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
    for ix, bx in enumerate((-0.13, 0.0, 0.13)):
        for by in (-0.085, 0.085):
            _bottle(bm, faces, bx + (0.01 if ix % 2 else -0.01), by, 0.04)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_butcher_block(bm, x, y, z_ground=0.0, ang=0.0):
    """Butcher's stump block with cleaver and fresh cuts."""
    faces = []
    faces += create_cylinder(
        bm, radius=0.30, height=0.52, segments=14,
        location=(0.0, 0.0, 0.26), mat_index=MAT_INDEX_LOG
    )
    faces += create_cylinder(
        bm, radius=0.325, height=0.07, segments=14,
        location=(0.0, 0.0, 0.52 + 0.035), mat_index=MAT_INDEX_WOOD
    )
    top_z = 0.52 + 0.07
    # Artist's butcher cuts laid on the block (fall back to red cuts if the
    # FBX cannot load: newly added bmesh faces are tracked for the transform).
    from mathutils import Matrix as _M2
    _n0 = len(bm.faces)
    try:
        _build_fbx_prop(bm, 'meat.fbx', None, -0.08, 0.05, top_z, 0.30,
                        0.22, _meat_mat(), final=_M2.Identity(4), long_axis='Y')
        _build_fbx_prop(bm, 'meat1.fbx', None, 0.10, -0.07, top_z, -0.40,
                        0.16, _meat_mat(), final=_M2.Identity(4), long_axis='Y')
    except Exception:
        for ox, oy, yaw in ((-0.10, 0.08, 0.25), (0.11, -0.06, -0.35)):
            faces += create_beveled_box(
                bm, size=(0.20, 0.13, 0.063),
                location=(ox, oy, top_z + 0.031),
                rotation=(0.0, 0.0, yaw),
                mat_index=MAT_INDEX_FABRIC_RED, bevel_amount=0.022
            )
    faces += [f for f in list(bm.faces)[_n0:] if f.is_valid]
    # Heavy cleaver buried in the block.
    faces += create_beveled_box(
        bm, size=(0.175, 0.018, 0.10),
        location=(0.02, 0.10, top_z + 0.10),
        rotation=(0.30, 0.0, -0.15),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )
    faces += create_cylinder(
        bm, radius=0.016, height=0.11, segments=8,
        location=(0.02, 0.10, top_z + 0.20),
        rotation=(0.30, 0.0, 0.0), mat_index=MAT_INDEX_WOOD
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _hanging_rail_frame(bm, width):
    """Shared butcher/fish hanging-rail frame: full-width foot skid, twin
    posts, knee braces and a top rail. Returns (faces, rail_z)."""
    faces = []
    post_s = 0.09
    h = 1.62
    faces += create_beveled_box(
        bm, size=(width + 0.18, 0.20, 0.09),
        location=(0.0, 0.0, 0.045),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )
    for sx in (-width * 0.5 + post_s * 0.5, width * 0.5 - post_s * 0.5):
        faces += create_beveled_box(
            bm, size=(post_s, post_s, h),
            location=(sx, 0.0, 0.09 + h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
        faces += create_beveled_box(
            bm, size=(0.06, 0.06, 0.40),
            location=(sx, 0.11, 0.30),
            rotation=(0.70, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )
    rail_z = 0.09 + h - 0.07
    faces += create_cylinder(
        bm, radius=0.034, height=width - 0.02, segments=8,
        location=(0.0, 0.0, rail_z),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_WOOD
    )
    return faces, rail_z


def build_sausage_string(bm, x, y, z_ground=0.0, ang=0.0, width=1.30):
    """Butcher's hanging meat rail: the artist's meat cuts hang on ropes
    (local -Y faces the room)."""
    faces, rail_z = _hanging_rail_frame(bm, width)
    n = max(3, int(width / 0.24))
    for i in range(n):
        hx = -width * 0.5 + 0.22 + i * ((width - 0.44) / max(1, n - 1))
        rope_len = 0.24 + (0.07 if i % 2 else 0.0)
        faces += create_cylinder(
            bm, radius=0.007, height=rope_len, segments=6,
            location=(hx, 0.0, rail_z - rope_len * 0.5),
            mat_index=MAT_INDEX_ROPE
        )
        _stamp_baked_local(
            bm, faces, 'meat.fbx' if i % 2 else 'meat1.fbx',
            hx, 0.0, rail_z - rope_len - 0.02, 0.0,
            0.30 if i % 2 else 0.24, _meat_mat(), long_axis='Y',
            pre_rot=(math.pi * 0.5, 0.0, 0.0)
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_fish_rail(bm, x, y, z_ground=0.0, ang=0.0, width=1.30):
    """Fishmonger's hanging rail: the artist's fish hang nose-down on ropes,
    like the butcher's cuts (local -Y faces the room)."""
    faces, rail_z = _hanging_rail_frame(bm, width)
    n = max(3, int(width / 0.26))
    for i in range(n):
        hx = -width * 0.5 + 0.22 + i * ((width - 0.44) / max(1, n - 1))
        rope_len = 0.20 + (0.08 if i % 2 else 0.0)
        faces += create_cylinder(
            bm, radius=0.006, height=rope_len, segments=6,
            location=(hx, 0.0, rail_z - rope_len * 0.5),
            mat_index=MAT_INDEX_ROPE
        )
        _stamp_baked_local(
            bm, faces, 'fish.fbx',
            hx, -0.005, rail_z - rope_len - 0.02, 0.0,
            0.30, _fish_mat(), long_axis='X', pre_mat=_hang_mat()
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_dress_form(bm, x, y, z_ground=0.0, ang=0.0):
    """Tailor's dress form: smoothly tapered linen torso on a turned stand.

    Hip/waist/bust flow into each other (cones, no stacked-roll seams), a
    red sash covers the waist joint, a pinned red overskirt hides the hip
    joint, and the wooden neck knob grows out of the shoulder cap.
    """
    faces = []
    faces += create_cylinder(
        bm, radius=0.20, height=0.055, segments=14,
        location=(0.0, 0.0, 0.0275), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.028, height=1.00, segments=10,
        location=(0.0, 0.0, 0.055 + 0.50), mat_index=MAT_INDEX_WOOD
    )
    # Hips taper in toward the waist.
    faces += create_cone(
        bm, radius1=0.165, radius2=0.125, height=0.24, segments=14,
        location=(0.0, 0.0, 0.95 + 0.12), mat_index=MAT_INDEX_FABRIC_WHITE,
    )
    # Waist column.
    faces += create_cylinder(
        bm, radius=0.122, height=0.16, segments=14,
        location=(0.0, 0.0, 1.19 + 0.08), mat_index=MAT_INDEX_FABRIC_WHITE,
    )
    # Bust flares back out.
    faces += create_cone(
        bm, radius1=0.120, radius2=0.158, height=0.24, segments=14,
        location=(0.0, 0.0, 1.35 + 0.12), mat_index=MAT_INDEX_FABRIC_WHITE,
    )
    # Shoulder cap closing the torso.
    faces += create_cone(
        bm, radius1=0.158, radius2=0.060, height=0.09, segments=14,
        location=(0.0, 0.0, 1.59 + 0.045), mat_index=MAT_INDEX_FABRIC_WHITE,
    )
    # Wooden neck knob rooted in the cap.
    faces += create_cylinder(
        bm, radius=0.045, height=0.07, segments=10,
        location=(0.0, 0.0, 1.66), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.026, height=0.045, segments=10,
        location=(0.0, 0.0, 1.695 + 0.0225), mat_index=MAT_INDEX_WOOD
    )
    # Pinned red overskirt over the hips.
    faces += create_cone(
        bm, radius1=0.190, radius2=0.150, height=0.30, segments=14,
        location=(0.0, 0.0, 0.88 + 0.15), mat_index=MAT_INDEX_FABRIC_RED,
    )
    # Waist sash ring.
    faces += create_torus_ring(
        bm, location=(0.0, 0.0, 1.27), rotation=(0.0, 0.0, 0.0),
        major_radius=0.130, minor_radius=0.022,
        major_segments=18, minor_segments=8, mat_index=MAT_INDEX_FABRIC_RED
    )
    # Measuring tape over one shoulder.
    faces += create_beveled_box(
        bm, size=(0.022, 0.012, 0.50),
        location=(0.095, 0.045, 1.32),
        rotation=(0.10, 0.0, 0.08),
        mat_index=MAT_INDEX_WAX, bevel_amount=0.003
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_cloth_bolt_bin(bm, x, y, z_ground=0.0, ang=0.0):
    """Open bin with three upright cloth bolts (linen, red, stitched)."""
    faces = []
    bw, bd, wall_h, wall_t = 0.55, 0.42, 0.42, 0.04
    faces += create_beveled_box(
        bm, size=(bw, bd, 0.05),
        location=(0.0, 0.0, 0.025),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
    )
    for sy in (-bd * 0.5 + wall_t * 0.5, bd * 0.5 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(bw, wall_t, wall_h),
            location=(0.0, sy, wall_h * 0.5 + 0.05),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
    for sx in (-bw * 0.5 + wall_t * 0.5, bw * 0.5 - wall_t * 0.5):
        faces += create_beveled_box(
            bm, size=(wall_t, bd, wall_h),
            location=(sx, 0.0, wall_h * 0.5 + 0.05),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
    bolts = (
        (-0.14, 0.02, 1.02, MAT_INDEX_CLOTH_LINEN),
        (0.02, -0.06, 0.94, MAT_INDEX_FABRIC_RED),
        (0.15, 0.07, 1.08, MAT_INDEX_FABRIC_STITCHED),
    )
    for bx, by, bh, mat in bolts:
        faces += create_cylinder(
            bm, radius=0.085, height=bh, segments=12,
            location=(bx, by, 0.05 + bh * 0.5), mat_index=mat, smooth=True
        )
        faces += create_cylinder(
            bm, radius=0.030, height=0.03, segments=8,
            location=(bx, by, 0.05 + bh + 0.008), mat_index=MAT_INDEX_WOOD
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_strongbox(bm, x, y, z_ground=0.0, ang=0.0):
    """Jeweler's iron-banded strongbox with lock plate and studs."""
    faces = []
    bw, bd, bh = 0.62, 0.38, 0.30
    faces += create_beveled_box(
        bm, size=(bw, bd, bh),
        location=(0.0, 0.0, bh * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
    )
    faces += create_beveled_box(
        bm, size=(bw + 0.02, bd + 0.02, 0.10),
        location=(0.0, 0.0, bh + 0.05),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
    )
    # Iron bands wrapping body and lid.
    for bx in (-bw * 0.28, bw * 0.28):
        faces += create_beveled_box(
            bm, size=(0.055, bd + 0.025, bh + 0.10),
            location=(bx, 0.0, (bh + 0.10) * 0.5),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.004
        )
    # Lock plate + studs on the front face.
    faces += create_beveled_box(
        bm, size=(0.13, 0.025, 0.17),
        location=(0.0, -bd * 0.5 - 0.006, bh * 0.55),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )
    for sx in (-bw * 0.28, bw * 0.28):
        faces += create_cylinder(
            bm, radius=0.018, height=0.02, segments=8,
            location=(sx, -bd * 0.5 - 0.008, bh * 0.72),
            rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_IRON
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _gem(bm, faces, lx, ly, lz, mat, size=0.024, yaw=0.0, tilt=0.0):
    """One faceted cut gem (octahedron from two cones), varied yaw/tilt."""
    faces += create_cone(
        bm, radius1=size, radius2=size * 0.25, height=size * 0.9, segments=8,
        location=(lx, ly, lz + size * 0.45),
        rotation=(tilt, 0.0, yaw), mat_index=mat
    )
    faces += create_cone(
        bm, radius1=size * 0.25, radius2=size, height=size * 0.9, segments=8,
        location=(lx, ly, lz - size * 0.45),
        rotation=(math.pi + tilt, 0.0, yaw), mat_index=mat
    )
    return faces


def build_gem_tray(bm, x, y, z_ground=0.0, ang=0.0):
    """Velvet gem tray with cut stones and gold coins, for counters."""
    faces = []
    tw, td = 0.36, 0.26
    faces += create_beveled_box(
        bm, size=(tw, td, 0.030),
        location=(0.0, 0.0, 0.015),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
    )
    rim_h, rim_t = 0.045, 0.020
    for sy in (-td * 0.5 + rim_t * 0.5, td * 0.5 - rim_t * 0.5):
        faces += create_beveled_box(
            bm, size=(tw, rim_t, rim_h),
            location=(0.0, sy, rim_h * 0.5 + 0.030),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
        )
    for sx in (-tw * 0.5 + rim_t * 0.5, tw * 0.5 - rim_t * 0.5):
        faces += create_beveled_box(
            bm, size=(rim_t, td, rim_h),
            location=(sx, 0.0, rim_h * 0.5 + 0.030),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
        )
    faces += create_beveled_box(
        bm, size=(tw - 0.05, td - 0.05, 0.012),
        location=(0.0, 0.0, 0.036),
        mat_index=MAT_INDEX_FABRIC_RED, bevel_amount=0.003
    )
    gems = (
        (-0.10, 0.045, MAT_INDEX_BOTTLE_GLASS, 0.026, 0.3, 0.06),
        (-0.03, -0.035, MAT_INDEX_GLASS, 0.022, 1.1, -0.05),
        (0.045, 0.050, MAT_INDEX_BOTTLE_GLASS, 0.024, 2.2, 0.08),
        (0.115, -0.030, MAT_INDEX_GLASS, 0.027, 2.9, -0.07),
    )
    for gx, gy, mat, gs, gyaw, gtilt in gems:
        _gem(bm, faces, gx, gy, 0.042, mat, size=gs, yaw=gyaw, tilt=gtilt)
    # Gold rings: two flat, one standing against the rim.
    for rx, ry in ((-0.062, -0.068), (0.015, 0.062)):
        faces += create_torus_ring(
            bm, location=(rx, ry, 0.048 + 0.008),
            rotation=(0.0, 0.0, rx * 10.0),
            major_radius=0.023, minor_radius=0.008,
            major_segments=14, minor_segments=6, mat_index=MAT_INDEX_WAX
        )
    faces += create_torus_ring(
        bm, location=(0.125, 0.045, 0.048 + 0.024),
        rotation=(math.pi * 0.5, 0.0, 0.2),
        major_radius=0.023, minor_radius=0.008,
        major_segments=14, minor_segments=6, mat_index=MAT_INDEX_WAX
    )
    for cx, cy in ((0.10, 0.055), (0.135, 0.030), (-0.065, -0.055)):
        faces += create_cylinder(
            bm, radius=0.020, height=0.008, segments=10,
            location=(cx, cy, 0.046), mat_index=MAT_INDEX_WAX
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_balance_scale(bm, x, y, z_ground=0.0, ang=0.0):
    """Goldsmith's standing balance scale with twin pans and weights."""
    faces = []
    faces += create_cylinder(
        bm, radius=0.16, height=0.05, segments=14,
        location=(0.0, 0.0, 0.025), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.024, height=1.05, segments=10,
        location=(0.0, 0.0, 0.05 + 0.525), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cone(
        bm, radius1=0.030, radius2=0.008, height=0.07, segments=8,
        location=(0.0, 0.0, 1.10 + 0.035), mat_index=MAT_INDEX_IRON
    )
    faces += create_beveled_box(
        bm, size=(0.56, 0.030, 0.030),
        location=(0.0, 0.0, 1.02),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.005
    )
    for sx in (-0.25, 0.25):
        for chain_dx in (-0.035, 0.035):
            faces += create_cylinder(
                bm, radius=0.005, height=0.20, segments=6,
                location=(sx + chain_dx, 0.0, 1.02 - 0.10),
                mat_index=MAT_INDEX_IRON
            )
        faces += create_hollow_dish(
            bm, radius_base=0.020, radius_rim=0.075, inner_radius_rim=0.066,
            inner_radius_base=0.016, height=0.045, inner_depth=0.030,
            segments=14, location=(sx, 0.0, 1.02 - 0.20 - 0.022),
            mat_index=MAT_INDEX_WAX, smooth=True
        )
    # Brass weights stacked at the foot.
    for wi, wr in enumerate((0.045, 0.036, 0.028)):
        faces += create_cylinder(
            bm, radius=wr, height=0.035, segments=10,
            location=(0.10, 0.06 + wi * 0.075, 0.0175), mat_index=MAT_INDEX_WAX
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_anvil(bm, x, y, z_ground=0.0, ang=0.0):
    """Smith's anvil on a stump: tapered waist, full face, conical horn."""
    faces = []
    faces += create_cylinder(
        bm, radius=0.26, height=0.44, segments=14,
        location=(0.0, 0.0, 0.22), mat_index=MAT_INDEX_LOG
    )
    # Foot spreading onto the stump.
    faces += create_beveled_box(
        bm, size=(0.48, 0.26, 0.10),
        location=(0.0, 0.0, 0.44 + 0.05),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )
    # Waist tapering up in two steps.
    faces += create_beveled_box(
        bm, size=(0.26, 0.20, 0.13),
        location=(-0.01, 0.0, 0.54 + 0.065),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.014
    )
    faces += create_beveled_box(
        bm, size=(0.32, 0.23, 0.11),
        location=(0.0, 0.0, 0.67 + 0.055),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.014
    )
    # Face plate with a slight overhang.
    faces += create_beveled_box(
        bm, size=(0.46, 0.26, 0.10),
        location=(0.0, 0.0, 0.78 + 0.05),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010
    )
    # Conical horn reaching forward (+X).
    faces += create_cone(
        bm, radius1=0.105, radius2=0.014, height=0.36, segments=12,
        location=(0.23 + 0.18, 0.0, 0.78 + 0.05),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_IRON
    )
    # Heel block at the back.
    faces += create_beveled_box(
        bm, size=(0.12, 0.26, 0.10),
        location=(-0.23 - 0.05, 0.0, 0.78 + 0.05),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_grindstone(bm, x, y, z_ground=0.0, ang=0.0):
    """Treadle grindstone: stone wheel in a timber frame over a water trough."""
    faces = []
    for sx in (-0.30, 0.30):
        faces += create_beveled_box(
            bm, size=(0.09, 0.09, 0.78),
            location=(sx, 0.0, 0.39),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
        faces += create_beveled_box(
            bm, size=(0.09, 0.55, 0.07),
            location=(sx, 0.0, 0.035),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    faces += create_cylinder(
        bm, radius=0.028, height=0.72, segments=10,
        location=(0.0, 0.0, 0.66),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.32, height=0.085, segments=20,
        location=(0.0, 0.0, 0.66),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_CUT_STONE,
        smooth=True
    )
    # Water trough the wheel dips into.
    faces += create_beveled_box(
        bm, size=(0.50, 0.30, 0.16),
        location=(0.0, 0.0, 0.08),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
    )
    faces += create_beveled_box(
        bm, size=(0.44, 0.24, 0.02),
        location=(0.0, 0.0, 0.145),
        mat_index=MAT_INDEX_WATER, bevel_amount=0.002
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_tool_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.20):
    """Wall tool rack with hanging smith's hand tools."""
    faces = []
    post_s = 0.07
    for sx in (-width * 0.5 + post_s * 0.5, width * 0.5 - post_s * 0.5):
        faces += create_beveled_box(
            bm, size=(post_s, post_s, 1.50),
            location=(sx, 0.0, 0.75),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
    for bz in (1.38, 0.55):
        faces += create_beveled_box(
            bm, size=(width, 0.06, 0.06),
            location=(0.0, 0.0, bz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Sledge hammer: handle down from the bar, head at its foot.
    faces += create_cylinder(
        bm, radius=0.020, height=0.52, segments=8,
        location=(-width * 0.5 + 0.24, 0.0, 1.38 - 0.28),
        mat_index=MAT_INDEX_WOOD
    )
    faces += create_beveled_box(
        bm, size=(0.16, 0.09, 0.10),
        location=(-width * 0.5 + 0.24, 0.0, 1.38 - 0.60),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )
    # Hand hammer.
    faces += create_cylinder(
        bm, radius=0.016, height=0.38, segments=8,
        location=(-width * 0.5 + 0.50, 0.0, 1.38 - 0.21),
        mat_index=MAT_INDEX_WOOD
    )
    faces += create_beveled_box(
        bm, size=(0.13, 0.075, 0.085),
        location=(-width * 0.5 + 0.50, 0.0, 1.38 - 0.445),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010
    )
    # Tongs: two long jaws with hinge ring.
    for jx in (-0.025, 0.025):
        faces += create_beveled_box(
            bm, size=(0.022, 0.022, 0.55),
            location=(width * 0.5 - 0.48 + jx, 0.0, 1.38 - 0.30),
            rotation=(0.0, jx * 2.0, 0.0),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.003
        )
    faces += create_torus_ring(
        bm, location=(width * 0.5 - 0.48, 0.0, 1.38 - 0.03),
        rotation=(0.0, 0.0, 0.0),
        major_radius=0.030, minor_radius=0.009,
        major_segments=12, minor_segments=6, mat_index=MAT_INDEX_IRON
    )
    # Fire poker.
    faces += create_cylinder(
        bm, radius=0.011, height=0.72, segments=8,
        location=(width * 0.5 - 0.24, 0.0, 1.38 - 0.38),
        mat_index=MAT_INDEX_IRON
    )
    faces += create_beveled_box(
        bm, size=(0.05, 0.05, 0.12),
        location=(width * 0.5 - 0.24, 0.0, 1.38 - 0.05),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_joiner_bench(bm, x, y, z_ground=0.0, ang=0.0, length=1.70):
    """Joiner's workbench with front vice, mallet and a board in progress."""
    faces = []
    top_z = 0.80
    faces += create_beveled_box(
        bm, size=(length, 0.62, 0.12),
        location=(0.0, 0.0, top_z - 0.06),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.012
    )
    for lx in (-length * 0.5 + 0.12, length * 0.5 - 0.12):
        for ly in (-0.22, 0.22):
            faces += create_beveled_box(
                bm, size=(0.11, 0.11, top_z - 0.12),
                location=(lx, ly, (top_z - 0.12) * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
            )
    faces += create_beveled_box(
        bm, size=(length - 0.24, 0.44, 0.06),
        location=(0.0, 0.0, 0.22),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )
    # Front vice: outer jaw, screw and handle bar.
    faces += create_beveled_box(
        bm, size=(0.34, 0.09, 0.22),
        location=(0.25, -0.31 - 0.075, top_z - 0.17),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
    )
    faces += create_cylinder(
        bm, radius=0.025, height=0.30, segments=10,
        location=(0.25, -0.31, top_z - 0.17),
        rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.014, height=0.30, segments=8,
        location=(0.25, -0.31 - 0.16, top_z - 0.17),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_WOOD
    )
    # Joiner's mallet resting on the bench.
    faces += create_cylinder(
        bm, radius=0.055, height=0.13, segments=10,
        location=(-0.45, 0.10, top_z + 0.065),
        rotation=(0.0, math.pi * 0.5, 0.30), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.016, height=0.30, segments=8,
        location=(-0.28, 0.02, top_z + 0.016),
        rotation=(0.0, math.pi * 0.5, -0.15), mat_index=MAT_INDEX_WOOD
    )
    # Board in progress clamped on the bench.
    faces += create_beveled_box(
        bm, size=(1.10, 0.26, 0.045),
        location=(0.10, 0.05, top_z + 0.0225),
        rotation=(0.0, 0.0, 0.04),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_sawbuck(bm, x, y, z_ground=0.0, ang=0.0):
    """Sawbuck with a log ready for bucking and a leaning hand saw."""
    faces = []
    # Legs cross in the vertical YZ plane (splay along Y); the log lies
    # along X resting in the V above the crossing.
    for lx in (-0.45, 0.45):
        faces += create_beveled_box(
            bm, size=(0.08, 0.08, 0.85),
            location=(lx, 0.0, 0.425),
            rotation=(0.42, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        faces += create_beveled_box(
            bm, size=(0.08, 0.08, 0.85),
            location=(lx, 0.0, 0.425),
            rotation=(-0.42, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    faces += create_beveled_box(
        bm, size=(1.10, 0.07, 0.07),
        location=(0.0, 0.0, 0.425),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    faces += create_cylinder(
        bm, radius=0.13, height=1.25, segments=12,
        location=(0.0, 0.0, 0.57),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_LOG
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _fish_body(bm, faces, lx, ly, lz, yaw=0.0, length=0.34, mat=MAT_INDEX_IRON):
    """One stylized fish: lofted body, tail diamond and dorsal fin."""
    faces += create_beveled_box(
        bm, size=(length, 0.085, 0.065),
        location=(lx, ly, lz + 0.0325),
        rotation=(0.0, 0.0, yaw),
        mat_index=mat, bevel_amount=0.028
    )
    tx = lx + math.cos(yaw) * (length * 0.5 + 0.035)
    ty = ly + math.sin(yaw) * (length * 0.5 + 0.035)
    faces += create_beveled_box(
        bm, size=(0.10, 0.10, 0.018),
        location=(tx, ty, lz + 0.030),
        rotation=(0.0, 0.0, yaw + math.pi * 0.25),
        mat_index=mat, bevel_amount=0.006
    )
    faces += create_beveled_box(
        bm, size=(0.09, 0.016, 0.055),
        location=(lx - math.cos(yaw) * length * 0.08, ly - math.sin(yaw) * length * 0.08,
                  lz + 0.065 + 0.0275),
        rotation=(0.0, 0.0, yaw),
        mat_index=mat, bevel_amount=0.005
    )
    return faces


def build_fish(bm, x, y, z_ground=0.0, ang=0.0, length=0.34, smoked=False):
    """Single fish for stall tables and racks: the artist's FBX mesh
    (props/fish.fbx, textured by fish.png). ``smoked`` only nudges the size
    now — the stylized box body is a last-resort fallback."""
    try:
        if _build_fbx_prop(bm, 'fish.fbx', None, x, y, z_ground, ang,
                           length, _fish_mat(), long_axis='AUTO'):
            return True
    except Exception:
        pass
    faces = []
    _fish_body(bm, faces, 0.0, 0.0, 0.0, yaw=0.0, length=length,
               mat=MAT_INDEX_LEATHER if smoked else MAT_INDEX_IRON)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# Hanging orientation for the flat fish mesh: length (local X) points down
# (-Z), the flat face (local Z) faces the room (-Y), width (local Y) runs
# across (X).
def _hang_mat():
    from mathutils import Matrix as _M
    return _M(((0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0)))


def build_meat(bm, x, y, z_ground=0.0, ang=0.0, length=0.30, variant=0):
    """Artist's butcher cuts (props/meat.fbx, meat1.fbx textured by
    meat.jpg); variant 0/1 selects the file. Falls back to a stylized box
    cut whenever the FBX cannot be loaded."""
    try:
        if _build_fbx_prop(bm, 'meat.fbx' if variant == 0 else 'meat1.fbx',
                           None, x, y, z_ground, ang, length, _meat_mat(),
                           long_axis='Y'):
            return True
    except Exception:
        pass
    faces = []
    _fish_body(bm, faces, 0.0, 0.0, 0.0, yaw=0.0, length=length,
               mat=MAT_INDEX_FABRIC_RED)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _fish_mat():
    from ..materials import MAT_INDEX_FISH
    return MAT_INDEX_FISH


def _meat_mat():
    from ..materials import MAT_INDEX_MEAT
    return MAT_INDEX_MEAT


def _build_fbx_prop(bm, fbx_file, _unused, x, y, z_ground, ang, length,
                    mat_index, final=None, long_axis='Y',
                    pre_rot=(0.0, 0.0, 0.0), pre_mat=None):
    """Stamp a baked artist prop mesh normalized to ``length`` with ``mat_index``.

    ``fbx_file`` names the source art (e.g. ``bread.fbx``); the geometry comes
    from the baked table in :mod:`artisan_meshdata` so no FBX operator runs at
    generation time (``bpy.ops.import_scene.fbx`` fails inside property-update
    and depsgraph contexts). ``long_axis`` is the local axis that must end up
    pointing along the prop's +X length. ``pre_rot`` (Euler) or ``pre_mat``
    (Matrix) is applied AFTER that axis fix — used to hang cuts/fish.
    Returns True, raises on any problem.
    """
    from mathutils import Matrix as _M, Vector as _V, Euler as _E
    from .artisan_meshdata import PROP_MESHES
    key = fbx_file[:-4] if fbx_file.lower().endswith('.fbx') else fbx_file
    it = PROP_MESHES.get(key)
    if not it:
        raise RuntimeError(f'{fbx_file} not baked')
    # Fit the mesh's chosen horizontal axis: X-native needs nothing, a
    # Y-native prop is yawed -90 so its length points along +X.
    verts = it['verts']
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if long_axis == 'AUTO':
        yaw_fix = 0.0 if dx >= dy else -math.pi * 0.5
    else:
        yaw_fix = 0.0 if long_axis == 'X' else -math.pi * 0.5
    span = (dx if long_axis == 'X' else dy) if long_axis in ('X', 'Y') \
        else max(dx, dy)
    span = span or 1.0
    s = length / span
    cx, cy, z0 = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5,
                  min(zs))
    fix = _M.Rotation(yaw_fix, 4, 'Z')
    pre = (pre_mat.to_4x4() if hasattr(pre_mat, 'to_4x4') else pre_mat) \
        if pre_mat is not None else _E(pre_rot).to_matrix().to_4x4()
    local = (_M.Translation((x, y, z_ground)) @ _M.Rotation(ang, 4, 'Z'))
    place = (local if final is None else (final @ local))
    place = place @ pre @ fix @ _M.Diagonal((s, s, s, 1.0))
    base = _M.Translation((-cx, -cy, -z0))
    uv_layer = bm.loops.layers.uv.verify()
    seen = set()
    remap = {}
    used = set(vi for poly in it['polys'] for vi, _ in poly)
    for i in used:
        v = verts[i]
        remap[i] = bm.verts.new(place @ (fix @ (base @ _V(v))))
    for poly in it['polys']:
        idx = [vi for vi, _ in poly]
        if len(set(idx)) < 3:
            continue  # degenerate loop
        key_f = tuple(sorted(idx))
        if key_f in seen:
            continue  # duplicate face
        seen.add(key_f)
        f = bm.faces.new([remap[i] for i in idx])
        f.material_index = mat_index
        f.smooth = True
        f.tag = True  # protect the atlas UVs from the final cubic UV pass
        for loop, (_, uv) in zip(f.loops, poly):
            loop[uv_layer].uv = uv
    return True


def build_fish_drying_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.60):
    """Tall A-frame drying rack with two rows of hanging smoked fish.

    Fish hang vertically (tail up) from bars lashed across the front legs;
    rows are spaced so the upper fish clear the lower bar.
    """
    faces = []
    for sx in (-width * 0.5 + 0.05, width * 0.5 - 0.05):
        faces += create_beveled_box(
            bm, size=(0.07, 0.07, 1.90),
            location=(sx, 0.0, 0.95),
            rotation=(0.35, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        faces += create_beveled_box(
            bm, size=(0.07, 0.07, 1.90),
            location=(sx, 0.0, 0.95),
            rotation=(-0.35, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    for bar_y, bar_z in ((0.23, 1.55), (0.03, 0.95)):
        faces += create_cylinder(
            bm, radius=0.028, height=width - 0.05, segments=8,
            location=(0.0, bar_y, bar_z),
            rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_WOOD
        )
    n = max(4, int(width / 0.30))
    for row, (bar_y, bar_z) in enumerate(((0.23, 1.55), (0.03, 0.95))):
        for i in range(n):
            hx = -width * 0.5 + 0.24 + i * ((width - 0.48) / max(1, n - 1))
            # Rope hanger.
            faces += create_cylinder(
                bm, radius=0.006, height=0.10, segments=6,
                location=(hx, bar_y, bar_z - 0.05), mat_index=MAT_INDEX_ROPE
            )
            # The artist's fish hanging nose-down, face to the room.
            _stamp_baked_local(
                bm, faces, 'fish.fbx', hx, bar_y - 0.005, bar_z - 0.11,
                0.0, 0.30, _fish_mat(), long_axis='X',
                pre_mat=_hang_mat()
            )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_rope_coil(bm, x, y, z_ground=0.0, ang=0.0):
    """Coiled mooring rope: three stacked rings."""
    faces = []
    for i, (major, z) in enumerate(((0.165, 0.035), (0.135, 0.100), (0.105, 0.160))):
        faces += create_torus_ring(
            bm, location=(0.0, 0.0, z), rotation=(0.0, 0.0, i * 0.35),
            major_radius=major, minor_radius=0.034,
            major_segments=20, minor_segments=8, mat_index=MAT_INDEX_ROPE
        )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_market_display(bm, x, y, z_ground=0.0, ang=0.0, width=1.50):
    """Stepped market display: three solid ascending tiers against a tall
    backboard, front (+Y local) facing the customer.

    Each tier is a SOLID box resting on the floor (no floating shelves, no
    coplanar seams: adjacent boxes overlap in Y by 2cm). Tier tops (local):
    front (y=+0.18, z=0.50), mid (y=-0.18, z=0.85), back (y=-0.54, z=1.20).
    Furnishing mirrors these numbers for the goods slots.
    """
    faces = []
    d = 0.38
    tiers = ((0.18, 0.50), (-0.18, 0.85), (-0.54, 1.20))
    for (ty, tz) in tiers:
        faces += create_beveled_box(
            bm, size=(width - 0.04, d + 0.02, tz),
            location=(0.0, ty, tz * 0.5),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.010
        )
    # Timber corner posts framing the steps (proud of the boxes, so no
    # coplanar face ever coincides with a tier box).
    for sx in (-width * 0.5 + 0.05, width * 0.5 - 0.05):
        faces += create_beveled_box(
            bm, size=(0.10, d * 3.0 + 0.10, 1.26),
            location=(sx, -0.18, 0.63),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
    # Top shelf lip on each tier (slightly proud, insets the goods).
    for (ty, tz) in tiers:
        faces += create_beveled_box(
            bm, size=(width + 0.03, d + 0.06, 0.05),
            location=(0.0, ty, tz - 0.02),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Tall backboard rising behind the top tier.
    faces += create_beveled_box(
        bm, size=(width - 0.02, 0.06, 0.62),
        location=(0.0, -0.74, 1.20 + 0.30),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_horseshoe(bm, x, y, z_ground=0.0, ang=0.0):
    """Lucky iron horseshoe lying flat (U opening toward +Y local)."""
    faces = []
    for sx in (-0.045, 0.045):
        faces += create_beveled_box(
            bm, size=(0.035, 0.11, 0.030),
            location=(sx, 0.02, 0.015),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.005
        )
    faces += create_beveled_box(
        bm, size=(0.125, 0.035, 0.030),
        location=(0.0, -0.035, 0.015),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.005
    )
    for sx in (-0.045, 0.045):
        for sy in (-0.01, 0.055):
            faces += create_cylinder(
                bm, radius=0.007, height=0.014, segments=6,
                location=(sx, sy, 0.030 + 0.007), mat_index=MAT_INDEX_IRON
            )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_wine_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.10):
    """Cellar wine rack: a timber frame with three solid shelves, each
    holding a row of the detailed mage-tower wine bottles LYING flat.

    Shelves sit *between* the posts (inset 2cm) so no face is coplanar with
    a post, and each bottle rests on a shelf top (never floating).
    """
    faces = []
    h = 1.34
    depth = 0.44
    post_w = 0.10
    shelf_t = 0.06
    shelf_zs = (0.22, 0.66, 1.10)
    half = width * 0.5 - post_w * 0.5
    # Posts.
    for sx in (-half, half):
        faces += create_beveled_box(
            bm, size=(post_w, depth, h),
            location=(sx, 0.0, h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Solid shelves inset between the posts.
    for sz in shelf_zs:
        faces += create_beveled_box(
            bm, size=(width - post_w - 0.04, depth, shelf_t),
            location=(0.0, 0.0, sz),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
        )
    # Back rail tying the frame together.
    faces += create_beveled_box(
        bm, size=(width - post_w - 0.04, 0.05, 0.06),
        location=(0.0, depth * 0.5 - 0.05, h - 0.06),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
    )
    # Lying bottles resting on each shelf, axis along the shelf (X),
    # necks toward the room (-Y side).
    from .interior_furniture import build_bottle
    per_shelf = max(2, int((width - 0.30) / 0.22))
    for sz in shelf_zs:
        top = sz + shelf_t * 0.5
        for i in range(per_shelf):
            bx = -width * 0.5 + 0.26 + i * ((width - 0.52) / max(1, per_shelf - 1))
            bf = build_bottle(bm, 0.0, 0.0, 0.0, 0.0, bottle_type='WINE')
            m = (Matrix.Translation((bx, 0.04, top + 0.05))
                 @ Matrix.Rotation(math.pi * 0.5, 4, 'Y'))
            transform_faces(bf, m)
            faces += bf
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_wooden_bowl(bm, x, y, z_ground=0.0, ang=0.0):
    """Turned wooden bowl with a spoon resting across the rim."""
    faces = []
    faces += create_hollow_dish(
        bm, radius_base=0.045, radius_rim=0.105, inner_radius_rim=0.092,
        inner_radius_base=0.038, height=0.075, inner_depth=0.055,
        segments=16, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_WOOD,
        smooth=True
    )
    faces += create_beveled_box(
        bm, size=(0.020, 0.20, 0.010),
        location=(0.03, 0.02, 0.078),
        rotation=(0.0, 0.0, 0.35),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.002
    )
    faces += create_beveled_box(
        bm, size=(0.045, 0.055, 0.012),
        location=(0.085, 0.075, 0.078),
        rotation=(0.0, 0.0, 0.35),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.003
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_fish_stringer(bm, x, y, z_ceiling=3.0, ang=0.0, drops=3):
    """Ceiling-hung curing stringer for low fishery rooms: rope drops with
    tail-tied smoked fish lashed to a crossbar. Hangs from z_ceiling, so it
    needs no floor footprint (placed via the CEILING_MOUNTED path)."""
    faces = []
    span = drops * 0.28 + 0.15
    faces += create_beveled_box(
        bm, size=(span, 0.05, 0.06),
        location=(0.0, 0.0, -0.03),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    for i in range(drops):
        lx = (i - (drops - 1) * 0.5) * 0.28
        faces += create_cylinder(
            bm, radius=0.006, height=0.14, segments=6,
            location=(lx, 0.0, -0.06 - 0.07), mat_index=MAT_INDEX_ROPE
        )
        # The artist's fish hanging nose-down off the bar.
        _stamp_baked_local(
            bm, faces, 'fish.fbx', lx, -0.005, -0.13, 0.0, 0.30,
            _fish_mat(), long_axis='X', pre_mat=_hang_mat()
        )
    transform_faces(faces, _place(x, y, z_ceiling, ang))
    return faces
