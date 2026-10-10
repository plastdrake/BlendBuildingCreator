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
    MAT_INDEX_CLAY, MAT_INDEX_WAX,
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
    """One crusty loaf resting on a surface at (lx, ly, lz)."""
    faces += create_beveled_box(
        bm, size=(length, length * 0.55, 0.105),
        location=(lx, ly, lz + 0.0525),
        rotation=(0.0, 0.0, yaw),
        mat_index=MAT_INDEX_BREAD, bevel_amount=0.032
    )
    return faces


def build_bread_loaf(bm, x, y, z_ground=0.0, ang=0.0, length=0.30):
    """Single crusty loaf for counters and tables."""
    faces = []
    _loaf(bm, faces, 0.0, 0.0, 0.0, yaw=0.0, length=length)
    transform_faces(faces, _place(x, y, z_ground, ang))
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
            _loaf(bm, faces, lx, 0.0, sz + 0.0225, yaw=(0.12 if si % 2 else -0.10) + i * 0.05)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_dough_bowl(bm, x, y, z_ground=0.0, ang=0.0):
    """Clay proving bowl with a risen dough dome, for kneading tables."""
    faces = []
    faces += create_hollow_dish(
        bm, radius_base=0.075, radius_rim=0.150, inner_radius_rim=0.132,
        inner_radius_base=0.062, height=0.105, inner_depth=0.075,
        segments=18, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_CLAY,
        smooth=True
    )
    faces += create_beveled_box(
        bm, size=(0.20, 0.20, 0.085),
        location=(0.0, 0.0, 0.075),
        rotation=(0.0, 0.0, 0.20),
        mat_index=MAT_INDEX_WAX, bevel_amount=0.030
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
    # Fresh rib cuts waiting on the block.
    for i, (ox, oy, yaw) in enumerate(((-0.10, 0.08, 0.25), (0.11, -0.06, -0.35))):
        faces += create_beveled_box(
            bm, size=(0.20, 0.13, 0.075 - i * 0.012),
            location=(ox, oy, top_z + 0.037),
            rotation=(0.0, 0.0, yaw),
            mat_index=MAT_INDEX_FABRIC_RED, bevel_amount=0.022
        )
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


def build_sausage_string(bm, x, y, z_ground=0.0, ang=0.0, width=1.30):
    """Butcher's hanging rail with strings of linked sausages."""
    faces = []
    post_s = 0.07
    for sx in (-width * 0.5 + post_s * 0.5, width * 0.5 - post_s * 0.5):
        faces += create_beveled_box(
            bm, size=(post_s, post_s, 1.55),
            location=(sx, 0.0, 0.775),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
        )
        for fz in (-0.16, 0.16):
            faces += create_beveled_box(
                bm, size=(0.30, post_s, 0.06),
                location=(sx, fz, 0.03),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
            )
    faces += create_cylinder(
        bm, radius=0.032, height=width - 0.05, segments=8,
        location=(0.0, 0.0, 1.50),
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_WOOD
    )
    n = max(3, int(width / 0.26))
    for i in range(n):
        hx = -width * 0.5 + 0.20 + i * ((width - 0.40) / max(1, n - 1))
        faces += create_cylinder(
            bm, radius=0.008, height=0.30, segments=6,
            location=(hx, 0.0, 1.50 - 0.15), mat_index=MAT_INDEX_ROPE
        )
        for li in range(3):
            faces += create_cylinder(
                bm, radius=0.034, height=0.095, segments=8,
                location=(hx, 0.0, 1.50 - 0.30 - 0.045 - li * 0.10),
                rotation=(0.0, math.pi * 0.5 if li % 2 else 0.0, 0.0),
                mat_index=MAT_INDEX_LEATHER
            )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_dress_form(bm, x, y, z_ground=0.0, ang=0.0):
    """Tailor's dress form: linen torso on a turned stand with waist sash."""
    faces = []
    faces += create_cylinder(
        bm, radius=0.20, height=0.055, segments=14,
        location=(0.0, 0.0, 0.0275), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cylinder(
        bm, radius=0.030, height=1.00, segments=10,
        location=(0.0, 0.0, 0.055 + 0.50), mat_index=MAT_INDEX_WOOD
    )
    # Torso: hip, waist, bust stacked in stitched linen.
    faces += create_cylinder(
        bm, radius=0.165, height=0.26, segments=14,
        location=(0.0, 0.0, 0.555 + 0.13), mat_index=MAT_INDEX_CLOTH_LINEN,
        smooth=True
    )
    faces += create_cylinder(
        bm, radius=0.125, height=0.20, segments=14,
        location=(0.0, 0.0, 0.815 + 0.10), mat_index=MAT_INDEX_CLOTH_LINEN,
        smooth=True
    )
    faces += create_cylinder(
        bm, radius=0.160, height=0.24, segments=14,
        location=(0.0, 0.0, 1.015 + 0.12), mat_index=MAT_INDEX_CLOTH_LINEN,
        smooth=True
    )
    faces += create_cylinder(
        bm, radius=0.055, height=0.09, segments=10,
        location=(0.0, 0.0, 1.255 + 0.045), mat_index=MAT_INDEX_WOOD
    )
    faces += create_cone(
        bm, radius1=0.055, radius2=0.008, height=0.07, segments=10,
        location=(0.0, 0.0, 1.345 + 0.035), mat_index=MAT_INDEX_WOOD
    )
    # Waist sash ring + measuring tape over the shoulder.
    faces += create_torus_ring(
        bm, location=(0.0, 0.0, 0.915), rotation=(0.0, 0.0, 0.0),
        major_radius=0.132, minor_radius=0.024,
        major_segments=18, minor_segments=8, mat_index=MAT_INDEX_FABRIC_RED
    )
    faces += create_beveled_box(
        bm, size=(0.025, 0.012, 0.55),
        location=(0.10, 0.06, 1.02),
        rotation=(0.12, 0.0, 0.10),
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


def _gem(bm, faces, lx, ly, lz, mat, size=0.024):
    """One faceted cut gem (octahedron from two cones)."""
    faces += create_cone(
        bm, radius1=size, radius2=size * 0.25, height=size * 0.9, segments=6,
        location=(lx, ly, lz + size * 0.45), mat_index=mat
    )
    faces += create_cone(
        bm, radius1=size * 0.25, radius2=size, height=size * 0.9, segments=6,
        location=(lx, ly, lz - size * 0.45),
        rotation=(math.pi, 0.0, 0.0), mat_index=mat
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
        (-0.10, 0.045, MAT_INDEX_BOTTLE_GLASS, 0.026),
        (-0.03, -0.035, MAT_INDEX_GLASS, 0.022),
        (0.045, 0.050, MAT_INDEX_BOTTLE_GLASS, 0.024),
        (0.115, -0.030, MAT_INDEX_GLASS, 0.027),
    )
    for gx, gy, mat, gs in gems:
        _gem(bm, faces, gx, gy, 0.042, mat, size=gs)
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
    """Smith's anvil on a stump: waist, face, stepped horn and heel."""
    faces = []
    faces += create_cylinder(
        bm, radius=0.26, height=0.44, segments=14,
        location=(0.0, 0.0, 0.22), mat_index=MAT_INDEX_LOG
    )
    faces += create_beveled_box(
        bm, size=(0.46, 0.24, 0.10),
        location=(0.0, 0.0, 0.44 + 0.05),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )
    faces += create_beveled_box(
        bm, size=(0.22, 0.19, 0.16),
        location=(-0.02, 0.0, 0.54 + 0.08),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )
    faces += create_beveled_box(
        bm, size=(0.60, 0.25, 0.13),
        location=(0.0, 0.0, 0.70 + 0.065),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )
    # Stepped horn tapering forward.
    horn_z = 0.70 + 0.065
    for i, (hl, hw, hh) in enumerate(((0.20, 0.20, 0.11), (0.16, 0.15, 0.085), (0.13, 0.10, 0.06))):
        faces += create_beveled_box(
            bm, size=(hl, hw, hh),
            location=(0.30 + 0.10 + i * 0.155, 0.0, horn_z),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.010
        )
    # Heel block at the back.
    faces += create_beveled_box(
        bm, size=(0.12, 0.25, 0.13),
        location=(-0.30 - 0.05, 0.0, horn_z),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
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
        rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_STONE,
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
    # Sledge hammer.
    faces += create_cylinder(
        bm, radius=0.018, height=0.62, segments=8,
        location=(-width * 0.5 + 0.24, 0.0, 1.38 - 0.33),
        mat_index=MAT_INDEX_WOOD
    )
    faces += create_beveled_box(
        bm, size=(0.10, 0.10, 0.22),
        location=(-width * 0.5 + 0.24, 0.0, 1.38 - 0.06),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010
    )
    # Hand hammer.
    faces += create_cylinder(
        bm, radius=0.014, height=0.40, segments=8,
        location=(-width * 0.5 + 0.48, 0.0, 1.38 - 0.22),
        mat_index=MAT_INDEX_WOOD
    )
    faces += create_beveled_box(
        bm, size=(0.07, 0.07, 0.13),
        location=(-width * 0.5 + 0.48, 0.0, 1.38 - 0.045),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.008
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
    """Single fish for stall tables and racks (smoked fish are brown)."""
    faces = []
    _fish_body(bm, faces, 0.0, 0.0, 0.0, yaw=0.0, length=length,
               mat=MAT_INDEX_LEATHER if smoked else MAT_INDEX_IRON)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


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
    n = max(4, int(width / 0.26))
    for row, (bar_y, bar_z) in enumerate(((0.23, 1.55), (0.03, 0.95))):
        for i in range(n):
            hx = -width * 0.5 + 0.24 + i * ((width - 0.48) / max(1, n - 1))
            faces += create_cylinder(
                bm, radius=0.006, height=0.10, segments=6,
                location=(hx, bar_y, bar_z - 0.05), mat_index=MAT_INDEX_ROPE
            )
            # Tail knot, hanging body, head (top to bottom).
            faces += create_beveled_box(
                bm, size=(0.075, 0.075, 0.020),
                location=(hx, bar_y, bar_z - 0.115),
                rotation=(0.0, 0.0, math.pi * 0.25 + i * 0.1),
                mat_index=MAT_INDEX_LEATHER, bevel_amount=0.005
            )
            faces += create_beveled_box(
                bm, size=(0.085, 0.062, 0.26),
                location=(hx, bar_y, bar_z - 0.125 - 0.13),
                rotation=(0.0, 0.0, (0.06 if (i + row) % 2 else -0.06)),
                mat_index=MAT_INDEX_LEATHER, bevel_amount=0.026
            )
            faces += create_beveled_box(
                bm, size=(0.095, 0.072, 0.07),
                location=(hx, bar_y, bar_z - 0.125 - 0.26 - 0.02),
                rotation=(0.0, 0.0, (0.06 if (i + row) % 2 else -0.06)),
                mat_index=MAT_INDEX_LEATHER, bevel_amount=0.022
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
        # Tail knot, hanging body, head (top to bottom).
        faces += create_beveled_box(
            bm, size=(0.070, 0.070, 0.020),
            location=(lx, 0.0, -0.20),
            rotation=(0.0, 0.0, math.pi * 0.25 + i * 0.12),
            mat_index=MAT_INDEX_LEATHER, bevel_amount=0.005
        )
        faces += create_beveled_box(
            bm, size=(0.085, 0.062, 0.26),
            location=(lx, 0.0, -0.21 - 0.13),
            rotation=(0.0, 0.0, (0.06 if i % 2 else -0.06)),
            mat_index=MAT_INDEX_LEATHER, bevel_amount=0.026
        )
        faces += create_beveled_box(
            bm, size=(0.095, 0.072, 0.07),
            location=(lx, 0.0, -0.21 - 0.26 - 0.02),
            rotation=(0.0, 0.0, (0.06 if i % 2 else -0.06)),
            mat_index=MAT_INDEX_LEATHER, bevel_amount=0.022
        )
    transform_faces(faces, _place(x, y, z_ceiling, ang))
    return faces
