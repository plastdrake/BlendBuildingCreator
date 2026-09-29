"""
Generic garden and yard greenery.

Window planters (with tilable soil) and a round well with a windlass, rope and
bucket. Reusable by houses, inns, taverns and farms alike.
"""

import math
import random
from mathutils import Matrix, Vector, Euler

from ..mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_torus_ring, transform_faces,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_STONE, MAT_INDEX_CUT_STONE,
    MAT_INDEX_IRON, MAT_INDEX_DIRT, MAT_INDEX_SHINGLES, MAT_INDEX_ROPE,
)
from ..roof.shingles import map_lean_to_shingle_uvs


def _place(x, y, z_ground=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _rng(x, y, salt=0):
    return random.Random((int(abs(x) * 73856093) ^ int(abs(y) * 19349663) ^ int(salt * 83492791)) & 0x7FFFFFFF)


def build_flower_box(bm, x, y, z_base=0.0, ang=0.0, length=0.95,
                     depth=0.22, height=0.22):
    """A plain window planter: a timber trough filled with soil.

    No lid, brackets or fake plants - just the box and its dirt fill. The caller
    seats the top edge right under the window sill; flowers get added in-engine.
    Local frame: the box runs along X, +Y against the wall.
    """
    L, D, H = length, depth, height
    faces = []
    faces += create_beveled_box(bm, size=(L, D, H), location=(0.0, 0.0, H * 0.5),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.016, bevel_segments=2)
    faces += create_beveled_box(bm, size=(L - 0.10, D - 0.10, 0.06),
                                location=(0.0, 0.0, H - 0.02), mat_index=MAT_INDEX_DIRT,
                                bevel_amount=0.0)
    transform_faces(faces, _place(x, y, z_base, ang))
    return faces


def _rope_cylinder(bm, radius, height, segments=10, location=(0.0, 0.0, 0.0),
                   rotation=(0.0, 0.0, 0.0), coil=False):
    """A cylinder carrying rope UVs: U normalised 0..1 around, V along the length.

    The ``rope_diffuse`` texture is a diagonal twisted fibre, so a hanging
    rope reads correctly with strands running down its length. A wound drum
    (``coil=True``) gets the same map rotated 90 degrees and repeated x6 so
    it reads as coiled wraps instead of lengthwise fibres.
    """
    faces = create_cylinder(bm, radius=radius, height=height, segments=segments,
                            location=location, rotation=rotation, mat_index=MAT_INDEX_ROPE)
    uv = bm.loops.layers.uv.verify()
    circ = max(1e-6, 2.0 * math.pi * radius)
    for f in faces:
        if not f.is_valid:
            continue
        for loop in f.loops:
            co = loop[uv].uv
            u, v = co.x / circ, co.y
            if coil:
                loop[uv].uv = (v * 6.0, u * 0.1)
            else:
                loop[uv].uv = (u, v * 15.0)
    return faces


def _well_bucket(bm, cx, cy, cz, r=0.15, h=0.24):
    """A hollow tapered wooden bucket with iron bands and a rope-tie loop."""
    seg = 18
    thick = 0.02
    zb = cz - h * 0.5
    zt = cz + h * 0.5
    rb = r * 0.82
    rt = r
    uv = bm.loops.layers.uv.verify()

    v_ob, v_ot, v_ib, v_it = [], [], [], []
    for i in range(seg):
        a = 2.0 * math.pi * i / seg
        ca, sa = math.cos(a), math.sin(a)
        v_ob.append(bm.verts.new((cx + rb * ca, cy + rb * sa, zb)))
        v_ot.append(bm.verts.new((cx + rt * ca, cy + rt * sa, zt)))
        v_ib.append(bm.verts.new((cx + (rb - thick) * ca, cy + (rb - thick) * sa, zb + thick)))
        v_it.append(bm.verts.new((cx + (rt - thick) * ca, cy + (rt - thick) * sa, zt)))

    def _face(verts, mat=MAT_INDEX_WOOD, planar=False):
        try:
            f = bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = mat
        for loop in f.loops:
            co = loop.vert.co
            if planar:
                loop[uv].uv = (co.x / (2 * r) + 0.5, co.y / (2 * r) + 0.5)
            else:
                u = (math.atan2(co.y - cy, co.x - cx) / (2.0 * math.pi)) % 1.0
                loop[uv].uv = (u, (co.z - zb) / max(1e-6, h))
        return f

    faces = []
    for i in range(seg):
        j = (i + 1) % seg
        for f in (_face([v_ob[i], v_ob[j], v_ot[j], v_ot[i]]),   # outer wall
                  _face([v_ib[j], v_ib[i], v_it[i], v_it[j]]),   # inner wall
                  _face([v_ob[i], v_ib[i], v_ib[j], v_ob[j]]),   # bottom ring
                  _face([v_ot[j], v_it[j], v_it[i], v_ot[i]])):  # rim ring
            if f is not None:
                faces.append(f)

    # Solid bottom disc closing the bucket floor (planar UVs: the angular wrap
    # above would smear toward the centre).
    fb = _face(list(v_ib), mat=MAT_INDEX_WOOD, planar=True)
    if fb is not None:
        faces.append(fb)

    for frac in (0.28, 0.82):
        bz = zb + h * frac
        rr = rb + (rt - rb) * frac
        faces += create_torus_ring(bm, location=(cx, cy, bz),
                                   major_radius=rr + 0.006, minor_radius=0.010,
                                   major_segments=18, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)
    # Forged bail handle: a half-torus arcing over the top, both ends sunk
    # into the rim walls with rivet mounts (a real handle, not a full ring).
    faces += _half_handle(bm, cx, cy, zt, half_span=rt * 0.92,
                          rise=rt * 0.95, tube=0.013)
    for mx in (cx - rt * 0.92, cx + rt * 0.92):
        faces += create_beveled_box(bm, size=(0.05, 0.05, 0.07),
                                    location=(mx, cy, zt - 0.01),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
    return faces


def _half_handle(bm, cx, cy, z_base, half_span=0.14, rise=0.14, tube=0.013,
                 arc_segments=12, tube_segments=8):
    """Half of a torus standing in the XZ plane: an arch handle.

    Ends terminate exactly at ``z_base`` so callers can sink them into the
    supporting walls; the arch rises ``rise`` above it.
    """
    import math as _m
    verts_ring = []
    for i in range(arc_segments + 1):
        t = _m.pi * i / arc_segments  # 0..pi: from +X end over the top to -X
        ax = _m.cos(t) * half_span
        az = z_base + _m.sin(t) * rise
        ring = []
        for j in range(tube_segments):
            p = 2.0 * _m.pi * j / tube_segments
            # Tube frame: radial in the arch plane + Y thickness.
            nx = _m.cos(t) * _m.cos(p)
            nz = _m.sin(t) * _m.cos(p)
            ny = _m.sin(p)
            ring.append(bm.verts.new((cx + ax + nx * tube, cy + ny * tube,
                                      az + nz * tube)))
        verts_ring.append(ring)
    uv = bm.loops.layers.uv.verify()
    faces = []
    for i in range(arc_segments):
        for j in range(tube_segments):
            j2 = (j + 1) % tube_segments
            try:
                f = bm.faces.new([verts_ring[i][j], verts_ring[i][j2],
                                  verts_ring[i + 1][j2], verts_ring[i + 1][j]])
            except ValueError:
                continue
            f.material_index = MAT_INDEX_IRON
            f.loops[0][uv].uv = (i / arc_segments, j / tube_segments)
            f.loops[1][uv].uv = (i / arc_segments, j2 / tube_segments)
            f.loops[2][uv].uv = ((i + 1) / arc_segments, j2 / tube_segments)
            f.loops[3][uv].uv = ((i + 1) / arc_segments, j / tube_segments)
            faces.append(f)
    return faces


def build_well(bm, x, y, z_ground=0.0, ang=0.0, radius=0.66, wall_h=0.62):
    """A smooth round stone well with a covered opening, windlass, rope and bucket."""
    ra = radius
    seg = 32
    faces = []
    # Smooth round masonry shaft + cut-stone coping lip.
    # u_repeats=4.0 wraps exactly 3 full texture tiles with scale=0.75 in the stone shader,
    # giving completely seamless circumferential wrapping with zero seam.
    faces += create_cylinder(bm, radius=ra, height=wall_h, segments=seg,
                             location=(0.0, 0.0, wall_h * 0.5), mat_index=MAT_INDEX_STONE,
                             u_repeats=4.0)
    faces += create_torus_ring(bm, location=(0.0, 0.0, wall_h),
                               major_radius=ra * 0.97, minor_radius=0.07,
                               major_segments=seg, minor_segments=12,
                               mat_index=MAT_INDEX_CUT_STONE)
    # A fitted plank lid that actually covers the opening.
    faces += create_cylinder(bm, radius=ra * 0.96, height=0.05, segments=seg,
                             location=(0.0, 0.0, wall_h + 0.055), mat_index=MAT_INDEX_WOOD)
    ring_r = ra * 0.96
    ring_minor = 0.022
    inner_r = ring_r - ring_minor * 1.6
    for off in (-ra * 0.42, 0.0, ra * 0.42):
        chord_half = math.sqrt(max(0.01, inner_r**2 - off**2))
        batten_len = max(0.05, chord_half * 2.0 - 0.02)
        faces += create_beveled_box(bm, size=(batten_len, 0.028, 0.014),
                                    location=(0.0, off, wall_h + 0.085),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.002)
    faces += create_torus_ring(bm, location=(0.0, 0.0, wall_h + 0.08),
                               major_radius=ring_r, minor_radius=ring_minor,
                               major_segments=36, minor_segments=12,
                               mat_index=MAT_INDEX_TIMBER)

    # Windlass frame & roof supports: two sturdy timber posts running from ground (Z=0)
    # up to the roof rafters, straddling the masonry cylinder along X.
    # The +X post is placed directly over the cylinder's 0-radian seam (x=ra, y=0),
    # physically enclosing and covering the seam beneath the timber pillar from ground to rim.
    post_top = wall_h + 0.08 + 1.30
    total_post_h = post_top
    post_w = 0.14
    post_d = 0.14
    post_x = ra * 0.92  # center at ~0.607m: inner face at 0.537m, outer face at 0.677m, encasing x=0.66
    for sx in (-post_x, post_x):
        faces += create_beveled_box(bm, size=(post_w, post_d, total_post_h),
                                    location=(sx, 0.0, total_post_h * 0.5),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        # Decorative forged iron collar brackets bracing the timber pillar against the stone shaft
        faces += create_beveled_box(bm, size=(post_w + 0.014, post_d + 0.014, 0.04),
                                    location=(sx, 0.0, wall_h * 0.48),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
        faces += create_beveled_box(bm, size=(post_w + 0.014, post_d + 0.014, 0.04),
                                    location=(sx, 0.0, wall_h * 0.90),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)

    axle_z = (wall_h + 0.08) + 1.30 * 0.60
    axle_len = post_x * 2.0 + 0.06
    faces += create_cylinder(bm, radius=0.05, height=axle_len, segments=14,
                             location=(0.0, 0.0, axle_z), rotation=(0.0, math.pi * 0.5, 0.0),
                             mat_index=MAT_INDEX_WOOD)
    # Rope drum on the axle (coiled wraps) + a hanging rope down to the bucket.
    faces += _rope_cylinder(bm, 0.075, 0.30, segments=16, location=(0.0, 0.0, axle_z),
                            rotation=(0.0, math.pi * 0.5, 0.0), coil=True)
    bucket_cz = axle_z - 0.50
    _bucket_h = 0.24
    bucket_rim = bucket_cz + _bucket_h * 0.5 + 0.15 * 0.95
    rope_len = max(0.08, (axle_z - 0.05) - bucket_rim)
    faces += _rope_cylinder(bm, 0.015, rope_len, segments=10,
                            location=(0.0, 0.0, axle_z - 0.05 - rope_len * 0.5))
    # Forged crank on the +X end of the axle (arm + grip).
    crank_x = post_x + post_w * 0.5 + 0.05
    faces += create_cylinder(bm, radius=0.03, height=0.16, segments=8,
                             location=(crank_x - 0.03, 0.0, axle_z),
                             rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_IRON)
    faces += create_beveled_box(bm, size=(0.05, 0.028, 0.34),
                                location=(crank_x, 0.0, axle_z - 0.12),
                                mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    faces += create_cylinder(bm, radius=0.022, height=0.16, segments=8,
                             location=(crank_x + 0.06, 0.0, axle_z - 0.26),
                             rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_IRON)
    # Empty (hollow) bucket hanging from the rope; the rope ties through its loop.
    faces += _well_bucket(bm, 0.0, 0.0, bucket_cz)

    # Clean timber-framed gabled roof:
    # - Ridge beam & protective cap at the apex (prevents coplanar corner clashes)
    # - Eave fascias along bottom
    # - Bargeboards down gable ends
    # - Single lean-to deck per slope with shingles on top and wood planks underneath
    ridge_z = post_top + 0.06
    roof_len = post_x * 2.0 + post_w + 0.26
    run = ra * 0.92
    rise = ra * 0.40
    slope = math.atan2(rise, run)
    hyp = math.hypot(run, rise)

    # Ridge beam along X
    faces += create_beveled_box(bm, size=(roof_len + 0.02, 0.10, 0.10),
                                location=(0.0, 0.0, ridge_z),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    # Protective ridge cap plank covering the apex
    faces += create_beveled_box(bm, size=(roof_len + 0.04, 0.13, 0.03),
                                location=(0.0, 0.0, ridge_z + 0.052),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)

    barge_thick = 0.055
    barge_h = 0.10
    deck_w = roof_len - barge_thick * 2.0
    uv_layer = bm.loops.layers.uv.verify()

    for s in (-1.0, 1.0):
        zc = ridge_z - rise * 0.5
        yc = s * run * 0.5

        # Raked bargeboards down both gable ends
        for sx in (-1.0, 1.0):
            bx = sx * (roof_len * 0.5 - barge_thick * 0.5)
            faces += create_beveled_box(bm, size=(barge_thick, hyp, barge_h),
                                        location=(bx, yc, zc - 0.005),
                                        rotation=(-s * slope, 0.0, 0.0),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)

        # Fascia along the low eave
        faces += create_beveled_box(bm, size=(roof_len, 0.06, 0.08),
                                    location=(0.0, s * (run + 0.01), ridge_z - rise - 0.01),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)

        # Combined Roof Slab: Shingles on top, Wood Planks on underside (no duplicate boxes)
        slab_thick = 0.030
        slab = create_beveled_box(
            bm, size=(deck_w, hyp, slab_thick),
            location=(0.0, yc, zc + 0.015),
            rotation=(-s * slope, 0.0, 0.0), mat_index=MAT_INDEX_SHINGLES,
            bevel_amount=0.003)
        map_lean_to_shingle_uvs(bm, slab, (0.0, yc, zc + 0.015), (-s * slope, 0.0, 0.0))

        # Re-assign the underside of the slab to MAT_INDEX_WOOD with subroof plank UVs
        rot_mat = Euler((-s * slope, 0.0, 0.0), 'XYZ').to_matrix()
        inv_tr = (Matrix.Translation(Vector((0.0, yc, zc + 0.015))) @ rot_mat.to_4x4()).inverted()
        for f in slab:
            if not f.is_valid:
                continue
            local_n = (rot_mat.inverted() @ f.normal).normalized()
            if local_n.z < -0.6:
                f.material_index = MAT_INDEX_WOOD
                f.tag = True
                for loop in f.loops:
                    p = inv_tr @ loop.vert.co
                    # Wood plank grain running horizontally along X
                    loop[uv_layer].uv = Vector((p.x * 0.90, p.y * 0.90))
            elif local_n.z > 0.6:
                f.material_index = MAT_INDEX_SHINGLES
                f.tag = True
            else:
                f.material_index = MAT_INDEX_TIMBER
                f.tag = True
        faces += slab
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces
