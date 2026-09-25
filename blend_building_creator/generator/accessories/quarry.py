"""Reusable stone-quarry worksite kit (DRY / SOLID / GRASP).

Single-responsibility module: everything quarry-specific lives here, and every
generic prop is delegated to its owner (``crane``, ``furniture``, ``archery``)
instead of being re-implemented.

Design contract (agreed with the user):
- The site produces **stone only**: no lumber/log/sack *product* piles here.
  Timber appears only as equipment (crane masts, skid sleepers, tool crates).
- The plot centre is a reserved keep-out for rocks the user places manually.
  Nothing in :func:`build_quarry_yard` may intrude into it on any tier.
- Showcase rocks keep the **same footprint on all tiers**; only the stepped
  cut notches deepen (``cut_level`` 0 -> 2), so manually placed big rocks
  fitting T1 also fit T2/T3.
- Tier progression is derived from the existing ``material_tier`` (no new
  properties): cut depth, crane count and block-stack count all step up
  T1 -> T2 -> T3.

Layout convention (plot space, 100m x 100m so |x|,|y| <= 46 must hold):
- The storage hut is the *main building* pushed north by ``plot_setback``.
- This yard owns everything south of it in plot space (after the setback
  translation), exactly like the archery range / tournament yard.
"""

import math
import random

from ..mesh_utils import create_beveled_box, create_box
from ..materials import (
    MAT_INDEX_CUT_STONE,
    MAT_INDEX_TIMBER,
)

# Centre keep-out reserved for the user's manually placed big rocks.
KEEPOUT_CX = 0.0
KEEPOUT_CY = -4.0
KEEPOUT_HALF = 13.0

# Showcase faces: fixed footprint on every tier, only the cut steps grow.
SHOWCASE_ROCKS = (
    # (cx, cy, width_x, depth_y, height)
    (-20.0, -6.0, 10.0, 6.0, 4.2),
    (18.0, -2.0, 8.0, 5.0, 3.2),
)

PLOT_LIMIT = 46.0


def _tier_cut_level(tier):
    """Map material tier to quarry cut depth (T1 intact -> T3 heavily benched)."""
    return {'TIER_1': 0, 'TIER_2': 1, 'TIER_3': 2}.get(tier, 0)


def _rng(seed, salt=0):
    return random.Random((int(seed) * 73856093 ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _scale_uv(bm, faces, factor):
    """Scale UVs on the given faces (factor < 1 = larger shader pattern)."""
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        for loop in f.loops:
            loop[uv_layer].uv *= factor


def _mass(bm, cx, cy, sx, sy, h, sink, rng, mat, bevel=0.28):
    """One solid grounded rock mass.

    The base is sunk ``sink`` metres below grade and the block carries a heavy
    single-segment chamfer plus slight yaw/tilt, so big faces read as craggy
    quarried rock rather than built masonry. The tilt is small enough that
    the sunk base never peeks above ground. UVs are scaled up 3x and tagged
    so the finalize pass keeps the large-block unwrap instead of retiling it.
    """
    faces = create_beveled_box(
        bm, size=(sx, sy, h + sink),
        location=(cx, cy, (h + sink) * 0.5 - sink),
        rotation=((rng.random() - 0.5) * 0.04,
                  (rng.random() - 0.5) * 0.04,
                  (rng.random() - 0.5) * 0.08),
        mat_index=mat, bevel_amount=bevel, bevel_segments=1,
    )
    for f in faces:
        f.tag = True
    _scale_uv(bm, faces, 0.3)
    return faces


def build_quarry_rock(bm, cx, cy, size_x=10.0, size_y=6.0, height=4.0,
                      cut_level=0, seed=42):
    """Build one quarry face with progressively deeper bench cuts.

    The face is a few large overlapping grounded masses, never a block grid,
    so nothing floats and nothing reads as a brick wall: ``cut_level`` only
    benches the southern working strip down (full height -> stepped benches
    -> low bench plus cut floor), while the footprint stays identical on all
    tiers. Loose won blocks gather at the foot of the face per tier.
    """
    rng = _rng(seed, salt=int(cx * 13 + cy * 7))
    cut = min(2, max(0, cut_level))
    sink = 0.5
    # Back mass: full height on every tier (the uncut face).
    back_d = size_y * 0.58
    back_cy = cy + size_y * 0.5 - back_d * 0.5
    _mass(bm, cx, back_cy, size_x, back_d, height, sink, rng, MAT_INDEX_CUT_STONE)
    # Flank shoulder overlapping the back mass (breaks the box silhouette).
    _mass(bm, cx - size_x * 0.28, back_cy - 0.4, size_x * 0.45, back_d * 0.9,
          height * 0.72, sink, rng, MAT_INDEX_CUT_STONE)
    # Southern working strip: benched down as the tiers progress.
    work_d = size_y - back_d + 0.4
    work_cy = cy - size_y * 0.5 + work_d * 0.5
    if cut == 0:
        _mass(bm, cx + size_x * 0.05, work_cy, size_x * 0.9, work_d,
              height * 0.92, sink, rng, MAT_INDEX_CUT_STONE)
    elif cut == 1:
        _mass(bm, cx - size_x * 0.22, work_cy, size_x * 0.5, work_d,
              height * 0.58, sink, rng, MAT_INDEX_CUT_STONE)
        _mass(bm, cx + size_x * 0.26, work_cy + 0.2, size_x * 0.42,
              work_d - 0.4, height * 0.30, sink, rng, MAT_INDEX_CUT_STONE)
    else:
        _mass(bm, cx - size_x * 0.25, work_cy, size_x * 0.44, work_d,
              height * 0.32, sink, rng, MAT_INDEX_CUT_STONE)
        # Grounded cut-floor slab where the rest of the lift was taken out.
        # Crisp unbeveled box: fresh-cut stone has sharp edges, and it keeps
        # the poly count down (6 faces instead of a beveled ~30).
        create_box(
            bm, size=(size_x * 0.44, work_d, 0.30),
            location=(cx + size_x * 0.25, work_cy, 0.05),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.03),
            mat_index=MAT_INDEX_CUT_STONE,
        )
    # Loose won blocks at the foot of the face (grounded, count grows/tier).
    # Crisp boxes again: sharp fresh-cut edges at 6 faces each.
    for k in range(2 + cut * 2):
        s = 0.8 + rng.random() * 0.5
        create_box(
            bm, size=(s, s * (0.75 + rng.random() * 0.4), s * 0.7),
            location=(cx - size_x * 0.4 + k * (size_x * 0.8 / max(1, 1 + cut * 2))
                      + (rng.random() - 0.5) * 0.5,
                      cy - size_y * 0.5 - 1.0 - rng.random() * 1.2,
                      s * 0.35 - 0.08),
            rotation=(0.0, 0.0, rng.random() * math.pi),
            mat_index=MAT_INDEX_CUT_STONE,
        )


def build_cut_block_stack(bm, x, y, z_ground=0.0, count=6, seed=1):
    """Stack of freshly cut ashlar blocks on transverse timber skids.

    Every bottom-layer block bears on its own pair of skids (one near each
    end), so no block ever balances on a single central support. Upper layers
    sit directly on the blocks below.
    """
    rng = _rng(seed, salt=int(x * 31 + y * 17))
    bw, bh, bd = 1.1, 0.55, 0.8
    for i in range(2):
        px = x + (i - 0.5) * (bw + 0.08)
        for ex in (-0.35, 0.35):
            create_beveled_box(
                bm, size=(0.14, bd + 0.5, 0.14),
                location=(px + ex, y, z_ground + 0.07),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
            )
    # Crisp unbeveled blocks: fresh ashlar has sharp edges, and plain boxes
    # cost 6 faces each instead of ~30 beveled ones.
    for i in range(max(1, count)):
        layer, slot = divmod(i, 2)
        px = x + (slot - 0.5) * (bw + 0.08)
        pz = z_ground + 0.14 + bh * 0.5 + layer * (bh + 0.03)
        create_box(
            bm, size=(bw, bd, bh),
            location=(px, y, pz),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.07),
            mat_index=MAT_INDEX_CUT_STONE,
        )


def build_rubble_pile(bm, x, y, z_ground=0.0, count=5, seed=7):
    """Small scatter of off-cut rubble (plain low-poly chunks)."""
    rng = _rng(seed, salt=int(x * 11 + y * 5))
    for _ in range(max(1, count)):
        s = 0.25 + rng.random() * 0.35
        create_box(
            bm, size=(s, s * (0.7 + rng.random() * 0.5), s * 0.7),
            location=(x + (rng.random() - 0.5) * 2.2,
                      y + (rng.random() - 0.5) * 2.2,
                      z_ground + s * 0.3),
            rotation=(0.0, 0.0, rng.random() * math.pi),
            mat_index=MAT_INDEX_CUT_STONE,
        )


def build_tool_crate_cluster(bm, x, y, z_ground=0.0):
    """Tool storage only (spare crates) - never stone product."""
    from .furniture import build_crate
    build_crate(bm, x=x - 0.5, y=y, z_ground=z_ground, ang=0.1,
                size=0.62, height=0.55, brace_style='DIAGONAL')
    build_crate(bm, x=x + 0.35, y=y + 0.15, z_ground=z_ground, ang=-0.15,
                size=0.48, height=0.45, brace_style='CROSS')


def build_quarry_yard(bm, props, ctx, tier):
    """Plot-space worksite composer: rocks, cranes, block stacks, fencing.

    Spreads the worksite across the 100m plot while keeping the centre
    keep-out (and the pushed-back storage hut) clear on every tier.
    """
    from .crane import build_courtyard_crane
    from .warehouse import build_tarp_awning, build_lean_to_awning

    cut = _tier_cut_level(tier)
    seed = getattr(ctx, 'seed', 42)

    # 1. Showcase faces (fixed footprints, deepening cuts per tier).
    for i, (rx, ry, rw, rd, rh) in enumerate(SHOWCASE_ROCKS):
        build_quarry_rock(bm, rx, ry, size_x=rw, size_y=rd, height=rh,
                          cut_level=cut, seed=seed + i * 17)

    # 2. Cranes: 1 / 2 / 3 by tier, each clear of rocks, hut and keep-out.
    crane_spots = [(10.0, -24.0, 0.5), (-10.0, 16.0, 2.4), (26.0, 14.0, -2.2)]
    n_cranes = (1, 2, 3)[min(2, cut)]
    for i in range(n_cranes):
        qx, qy, rot = crane_spots[i]
        mast = 4.0 if i < 2 else 5.0
        jib = 3.4 if i < 2 else 4.2
        build_courtyard_crane(bm, yard_x=qx, yard_y=qy, z_ground=0.0,
                              mast_height=mast, jib_length=jib, rot_angle=rot)

    # 3. Fresh-cut block stacks beside each active crane (the only product).
    stack_spots = [(14.0, -22.0), (-14.0, 12.0), (22.0, 11.0)]
    stack_counts = (4, 6, 8)
    for i in range(n_cranes):
        sx, sy = stack_spots[i]
        build_cut_block_stack(bm, sx, sy, z_ground=0.0,
                              count=stack_counts[cut], seed=seed + 100 + i)
        build_rubble_pile(bm, sx + 3.0, sy + 1.5, count=3 + cut * 2,
                          seed=seed + 200 + i)

    # 4. Small tool stores flanking the haul road (equipment, not product).
    build_tool_crate_cluster(bm, 4.0, -22.0)
    if cut >= 1:
        build_tool_crate_cluster(bm, -6.0, 13.0)

    # 5. Oversized yard awnings (the warehouse kit at 1.5x size) sheltering
    # dressed stone, each with its own small block stack underneath.
    build_tarp_awning(bm, cx=19.5, cy=-22.0, z_base=0.0,
                      width=2.9 * 1.5, depth=2.5 * 1.5)
    build_cut_block_stack(bm, 19.5, -22.0, z_ground=0.0, count=4,
                          seed=seed + 300)
    if cut >= 1:
        build_lean_to_awning(bm, cx=-19.5, cy=12.0, z_base=0.0,
                             width=2.5 * 1.5, depth=2.2 * 1.5)
        build_cut_block_stack(bm, -19.5, 12.0, z_ground=0.0, count=4,
                              seed=seed + 301)
