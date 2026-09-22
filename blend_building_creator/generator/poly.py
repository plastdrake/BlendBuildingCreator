"""Reusable polygonal / round shell helpers.

A smooth round tower and a chapel apse are both "a ring of flat wall segments
that approximates a curve". Keeping that maths in one place (DRY) lets every
curved volume share the same segment frames, annular slabs, corner posts,
corbels and wall-ring emission, instead of each builder hand-rolling its own.

The public surface is deliberately tiny and pure (GRASP: information expert -
the geometry knows how to describe itself):

- :func:`segment_frame`   - (p1, p2, outward normal, mid) for one facet
- :func:`ring_slab`       - annular deck of trapezoid slabs between two radii
- :func:`corner_posts`    - posts sealing every facet join
- :func:`corbel_ring`     - a ring of short corbels under a jetty
- :func:`wall_ring`       - emit the whole wall ring with per-facet openings
"""

import math

from mathutils import Vector

from .mesh_utils import create_beveled_box
from .materials import MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD
from .walls import build_wall_with_opening


def segment_frame(radius, k, segments, offset):
    """Return (p1, p2, outward_normal, midpoint) for facet ``k``."""
    d_ang = 2.0 * math.pi / segments
    a1 = k * d_ang + offset
    a2 = (k + 1) * d_ang + offset
    p1 = (radius * math.cos(a1), radius * math.sin(a1))
    p2 = (radius * math.cos(a2), radius * math.sin(a2))
    mid = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
    nrm = Vector((mid[0], mid[1], 0.0)).normalized()
    return p1, p2, nrm, mid


def ring_slab(bm, r_in, r_out, z, segments, offset, mat_index,
              height=0.12, overlap=1.06, bevel=0.01, skip=()):
    """Lay a ring of trapezoid boxes between two radii (an annular deck)."""
    d_ang = 2.0 * math.pi / segments
    width = r_out - r_in
    if width <= 0.02:
        return []
    mid_r = (r_in + r_out) * 0.5
    faces = []
    for k in range(segments):
        if k in skip:
            continue
        ang = (k + 0.5) * d_ang + offset
        chord = 2.0 * mid_r * math.tan(d_ang * 0.5) * overlap
        f = create_beveled_box(
            bm, size=(width, chord, height),
            location=(mid_r * math.cos(ang), mid_r * math.sin(ang), z),
            rotation=(0.0, 0.0, ang), mat_index=mat_index, bevel_amount=bevel,
        )
        faces.extend(f)
    return faces


def corner_posts(bm, radius, z_floor, height, segments, offset, size=0.14):
    """Timber posts at every facet vertex, sealing the joins."""
    d_ang = 2.0 * math.pi / segments
    for k in range(segments):
        ang = k * d_ang + offset
        create_beveled_box(
            bm, size=(size, size, height),
            location=(radius * math.cos(ang), radius * math.sin(ang),
                      z_floor + height * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012,
        )


def corbel_ring(bm, radius, z_level, segments, offset, size=0.16, drop=0.36):
    """Short timber corbels under a jettied floor / belvedere."""
    d_ang = 2.0 * math.pi / segments
    for k in range(segments):
        ang = k * d_ang + offset
        create_beveled_box(
            bm, size=(size, size, drop),
            location=(radius * math.cos(ang), radius * math.sin(ang), z_level),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.015,
        )


def wall_ring(bm, radius, z0, z1, wall_t, segments, offset, openings_by_seg,
              mat_ext, normal_face=True, seed=42, tier='TIER_3',
              physical_siding=True, plank_direction='HORIZONTAL',
              plank_jankiness=0.35, stone_block_scale=1.0, stone_disorder=0.35,
              has_exposed_brick=True, exposed_brick_freq=0.25, indices=None):
    """Emit a circular (or arc) wall as flat facets with per-facet openings.

    ``openings_by_seg`` maps a facet index to its list of opening dictionaries
    (same schema as :func:`walls.build_wall_with_opening`). ``indices`` restricts
    emission to a subset of facets, so a half-round apse reuses the same maths as
    a full round tower.
    """
    for k in (range(segments) if indices is None else indices):
        p1, p2, nrm, _mid = segment_frame(radius, k, segments, offset)
        build_wall_with_opening(
            bm, p1, p2, z0, z1, wall_t, openings_by_seg.get(k, ()),
            mat_ext=mat_ext, normal_vec=(nrm.x, nrm.y), tier=tier,
            physical_siding=physical_siding, plank_direction=plank_direction,
            plank_jankiness=plank_jankiness, stone_block_scale=stone_block_scale,
            stone_disorder=stone_disorder, seed=seed + k * 17,
            has_exposed_brick=has_exposed_brick,
            exposed_brick_freq=exposed_brick_freq,
        )
