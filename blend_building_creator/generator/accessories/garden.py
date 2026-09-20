"""
Generic garden and yard greenery.

Window planters (with tilable soil) and a round well with a windlass, rope and
bucket. Reusable by houses, inns, taverns and farms alike.
"""

import math
import random
from mathutils import Matrix

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
                   rotation=(0.0, 0.0, 0.0)):
    """A cylinder carrying rope UVs: U normalised 0..1 around, V along the length.

    The ``rope_diffuse`` texture is a row of vertical strands, so with the
    material's U scale at 1/16 the whole circumference shows a single strand and
    the strands run along the rope's length instead of smearing around it.
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
            loop[uv].uv = (co.x / circ, co.y)
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

    def _face(verts, mat=MAT_INDEX_WOOD):
        try:
            f = bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = mat
        for loop in f.loops:
            co = loop.vert.co
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

    # Solid bottom disc closing the bucket floor (the ring above is only the
    # underside lip; without this the bucket is an open-ended tube).
    fb = _face(list(v_ib), mat=MAT_INDEX_WOOD)
    if fb is not None:
        faces.append(fb)

    for frac, frac_r in ((0.28, 0.93), (0.82, 0.99)):
        bz = zb + h * frac
        rr = rb + (rt - rb) * frac
        faces += create_torus_ring(bm, location=(cx, cy, bz),
                                   major_radius=rr / frac_r + 0.008, minor_radius=0.010,
                                   major_segments=18, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)
    # Forged bail handle arcing over the top (the rope runs down through it and
    # is tied off at the apex, exactly like a real well bucket).
    faces += create_torus_ring(bm, location=(cx, cy, zt),
                               rotation=(math.pi * 0.5, 0.0, 0.0),
                               major_radius=rt * 0.95, minor_radius=0.013,
                               major_segments=18, minor_segments=6,
                               mat_index=MAT_INDEX_IRON)
    # Small grip/knob at the bail apex so the rope reads as lashed to it.
    faces += create_beveled_box(bm, size=(0.045, 0.045, 0.055),
                                location=(cx, cy, zt + rt * 0.95),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    return faces


def build_well(bm, x, y, z_ground=0.0, ang=0.0, radius=0.66, wall_h=0.62):
    """A smooth round stone well with a covered opening, windlass, rope and bucket."""
    ra = radius
    seg = 32
    faces = []
    # Smooth round masonry shaft + cut-stone coping lip. A single solid shaft is
    # enough because the fitted lid closes the top (no fake water table needed).
    faces += create_cylinder(bm, radius=ra, height=wall_h, segments=seg,
                             location=(0.0, 0.0, wall_h * 0.5), mat_index=MAT_INDEX_STONE)
    faces += create_torus_ring(bm, location=(0.0, 0.0, wall_h),
                               major_radius=ra * 0.97, minor_radius=0.07,
                               major_segments=seg, minor_segments=12,
                               mat_index=MAT_INDEX_CUT_STONE)
    # A fitted plank lid that actually covers the opening.
    faces += create_cylinder(bm, radius=ra * 0.96, height=0.05, segments=seg,
                             location=(0.0, 0.0, wall_h + 0.055), mat_index=MAT_INDEX_WOOD)
    for off in (-ra * 0.42, 0.0, ra * 0.42):
        faces += create_beveled_box(bm, size=(ra * 1.9, 0.02, 0.012),
                                    location=(0.0, off, wall_h + 0.085),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.002)
    faces += create_torus_ring(bm, location=(0.0, 0.0, wall_h + 0.08),
                               major_radius=ra * 0.96, minor_radius=0.022,
                               major_segments=seg, minor_segments=8,
                               mat_index=MAT_INDEX_TIMBER)

    # Windlass frame: two posts straddling the shaft along X.
    post_base = wall_h + 0.08
    post_h = 1.30
    post_top = post_base + post_h
    for sx in (-ra * 0.86, ra * 0.86):
        faces += create_beveled_box(bm, size=(0.12, 0.12, post_h),
                                    location=(sx, 0.0, post_base + post_h * 0.5),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    axle_z = post_base + post_h * 0.60
    axle_len = ra * 1.72
    faces += create_cylinder(bm, radius=0.05, height=axle_len, segments=14,
                             location=(0.0, 0.0, axle_z), rotation=(0.0, math.pi * 0.5, 0.0),
                             mat_index=MAT_INDEX_WOOD)
    # Rope drum on the axle + a hanging rope running down to the bucket's loop.
    faces += _rope_cylinder(bm, 0.075, 0.30, segments=16, location=(0.0, 0.0, axle_z),
                            rotation=(0.0, math.pi * 0.5, 0.0))
    bucket_cz = axle_z - 0.50
    _bucket_h = 0.24
    bucket_rim = bucket_cz + _bucket_h * 0.5 + 0.15 * 0.95
    rope_len = max(0.08, (axle_z - 0.05) - bucket_rim)
    faces += _rope_cylinder(bm, 0.015, rope_len, segments=10,
                            location=(0.0, 0.0, axle_z - 0.05 - rope_len * 0.5))
    # Forged crank on the +X end of the axle (arm + grip).
    crank_x = axle_len * 0.5 + 0.06
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

    # Gabled shingle hood resting directly on the post tops (no floating beams).
    # Kept compact so it can't reach into an adjacent building's roof/framing.
    ridge_z = post_top + 0.06
    faces += create_beveled_box(bm, size=(ra * 1.8, 0.10, 0.10),
                                location=(0.0, 0.0, ridge_z),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    run = ra * 0.95
    rise = ra * 0.42
    slope = math.atan2(rise, run)
    slope_len = math.hypot(run, rise) + 0.08
    for s in (-1.0, 1.0):
        zc = ridge_z - rise * 0.5
        yc = s * run * 0.5
        slab = create_beveled_box(
            bm, size=(ra * 1.95, slope_len, 0.05),
            location=(0.0, yc, zc),
            rotation=(-s * slope, 0.0, 0.0), mat_index=MAT_INDEX_SHINGLES,
            bevel_amount=0.006)
        map_lean_to_shingle_uvs(bm, slab, (0.0, yc, zc), (-s * slope, 0.0, 0.0))
        faces += slab
        # Fascia along the low eave.
        faces += create_beveled_box(bm, size=(ra * 1.95, 0.09, 0.12),
                                    location=(0.0, s * run, ridge_z - rise - 0.03),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
        # Raked barge boards down both gable ends.
        for sx in (-1.0, 1.0):
            faces += create_beveled_box(bm, size=(0.055, slope_len, 0.12),
                                        location=(sx * run, yc, zc - 0.02),
                                        rotation=(-s * slope, 0.0, 0.0),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces
