"""
Mini-wing outcrop builder.

A small annex / oriel projection attached to a facade. This module owns only
the outcrop's own body (foundation or corbels, floor and ceiling, post-and-panel
walls) and composes the shared builders for everything it has in common with the
main hall:

- :func:`~generator.openings.build_window_assembly` for the leaded window,
- :func:`~generator.roof.outcrop_roof.build_outcrop_roof` for the shingled roof,
- :mod:`generator.facade` / :mod:`generator.uv_utils` for placement and UVs.
"""

import math
from mathutils import Vector

from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER_FRAME,
    MAT_INDEX_WOOD,
)
from ..walls import create_curved_corbel
from ..facade import get_facade_frame
from ..uv_utils import map_local_wall_uv
from ..roof.outcrop_roof import build_outcrop_roof


def mini_wing_offsets(bounds, side, count, wing_w, randomize=False, seed=0, avoid=None):
    """Centres (relative to the facade centre, along the wall) for the outcrops.

    ``bounds`` is (x_min, x_max, y_min, y_max) of the facade box. Offsets run
    along X for FRONT/BACK facades and along Y for LEFT/RIGHT facades. The wall
    is reduced to the runs left over once ``avoid`` (a list of (lo, hi) spans
    such as doorways, turret corners or whatever the storey below carries) has
    been cut out, then the outcrops are laid into those runs one width + gap
    apart - evenly spaced, or scattered over the available slots when
    ``randomize`` is set. Nothing ever overlaps, and the count is reduced when
    there is not enough room.
    """
    x_min, x_max, y_min, y_max = bounds
    span = (x_max - x_min) if side in ('FRONT', 'BACK') else (y_max - y_min)
    count = max(1, min(12, int(count)))
    pitch = wing_w + 0.5
    half = span * 0.5 - wing_w * 0.5 - 0.05
    if half <= 0.0:
        return []
    clearance = wing_w * 0.5 + 0.30
    runs = _free_runs(-half, half,
                      [(lo - clearance, hi + clearance) for lo, hi in (avoid or ())])
    if not runs:
        return []

    slot_runs = []
    for a, b in runs:
        n = max(1, int((b - a) // pitch) + 1)
        total = (n - 1) * pitch
        start = (a + b) * 0.5 - total * 0.5
        slot_runs.append([start + i * pitch for i in range(n)])
    total_slots = sum(len(r) for r in slot_runs)
    if count >= total_slots:
        return [o for run in slot_runs for o in run]

    if not randomize:
        # Even spread: at least one per run, then the rest by spare capacity.
        share = [1] * len(slot_runs)
        for _ in range(count - len(slot_runs)):
            best, slack = None, 0
            for i, run in enumerate(slot_runs):
                if len(run) - share[i] > slack:
                    best, slack = i, len(run) - share[i]
            if best is None:
                break
            share[best] += 1
        out = []
        for run, k in zip(slot_runs, share):
            if k >= len(run):
                out.extend(run)
            elif k == 1:
                out.append(run[len(run) // 2])
            else:
                out.extend(run[round(j * (len(run) - 1) / (k - 1))] for j in range(k))
        return sorted(out)

    flat = [o for run in slot_runs for o in run]
    rng = _seed_rng(seed, bounds, len(flat))
    return sorted(rng.sample(flat, count))


def _free_runs(lo, hi, blocked):
    """``[lo, hi]`` minus the blocked spans, as a list of (a, b) runs."""
    out = [(lo, hi)]
    for blo, bhi in blocked:
        nxt = []
        for a, b in out:
            if bhi <= a or blo >= b:
                nxt.append((a, b))
                continue
            if blo > a:
                nxt.append((a, min(blo, b)))
            if bhi < b:
                nxt.append((max(bhi, a), b))
        out = nxt
    return [(a, b) for a, b in out if b - a > 1e-6]


def _seed_rng(seed, bounds, count):
    import random
    key = int(abs((bounds[0] + bounds[1] + bounds[2] + bounds[3]) * 100.0)) + int(seed) * 7 + count * 13
    return random.Random(key)


_MW_SIDES = ('FRONT', 'BACK', 'LEFT', 'RIGHT')


def _share(total, caps):
    """Split ``total`` over items with capacities ``caps`` (largest remainder)."""
    n = len(caps)
    out = [0] * n
    total_cap = sum(caps)
    if total <= 0 or n == 0 or total_cap <= 0:
        return out
    total = min(total, total_cap)
    exact = [total * c / float(total_cap) for c in caps]
    out = [min(int(e), c) for e, c in zip(exact, caps)]
    left = total - sum(out)
    order = sorted(range(n), key=lambda i: -(exact[i] - int(exact[i])))
    while left > 0:
        moved = False
        for i in order:
            if left <= 0:
                break
            if out[i] < caps[i]:
                out[i] += 1
                left -= 1
                moved = True
        if not moved:
            break
    return out


def mini_wing_spread(bounds, floors, count, wing_w, randomize=True, seed=0,
                     open_sides=None, avoid=None, wing_d=1.6,
                     width_var=0.0, depth_var=0.0):
    """Lay ``count`` outcrops out over ``floors`` — ``count`` is the total.

    ``open_sides`` maps a floor to the facades still free on it and ``avoid``
    maps a floor to ``{facade: [(lo, hi), ...]}`` spans the outcrops must keep
    clear of (doorways, a wing or annex, turret corners, ...). The amount is
    shared out over the storeys and then over the free facades in proportion to
    how much room each one still has, so a big clear wall gets more than a
    narrow strip. Outcrops also keep off the ones on the storey below so the
    bays stagger; when there is not enough staggered room left they stack
    instead of being dropped.

    ``width_var`` / ``depth_var`` let each outcrop vary around ``wing_w`` /
    ``wing_d`` by up to that amount (the random size option). Slots are laid
    out for the widest outcrop so they can never overlap, and the chosen size
    travels with the placement. Returns ``{floor: [(side, offset, width, depth), ...]}``.
    """
    import random
    floors = [f for f in dict.fromkeys(int(f) for f in floors)]
    open_sides = open_sides or {}
    usable = [f for f in floors if open_sides.get(f)]
    if not usable:
        return {}
    count = max(1, int(count))
    width_var = max(0.0, float(width_var))
    depth_var = max(0.0, float(depth_var))
    # Reserve the widest possible outcrop so random sizes never overlap.
    slot_w = wing_w + width_var

    def _static(f, side):
        return list((avoid or {}).get(f, {}).get(side, ()))

    # Capacity of every free facade: how many outcrops fit ignoring the storey
    # below (which only ever removes slots).
    caps = {}
    for f in usable:
        for side in open_sides[f]:
            caps[(f, side)] = len(mini_wing_offsets(bounds, side, 99, slot_w,
                                                     randomize=False, seed=0,
                                                     avoid=_static(f, side)))
    capacity = sum(caps.values())
    if capacity <= 0:
        return {}
    count = min(count, capacity)

    floor_caps = {f: sum(caps[(f, s)] for s in open_sides[f]) for f in usable}
    alloc = {}
    for f, share in zip(usable, _share(count, [floor_caps[f] for f in usable])):
        sides = open_sides[f]
        for s, k in zip(sides, _share(share, [caps[(f, s)] for s in sides])):
            if k:
                alloc[(f, s)] = k

    out, placed = {}, {}
    for f in sorted(usable):
        row = []
        for side in open_sides[f]:
            k = alloc.get((f, side), 0)
            if not k:
                continue
            static = _static(f, side)
            below = list(placed.get(f - 1, {}).get(side, ()))
            offsets = mini_wing_offsets(bounds, side, k, slot_w,
                                        randomize=randomize,
                                        seed=seed * 31 + f * 7 + _MW_SIDES.index(side),
                                        avoid=static + below)
            if len(offsets) < k:
                # Not enough room to stagger: stack them rather than drop them.
                offsets = mini_wing_offsets(bounds, side, k, slot_w,
                                            randomize=randomize,
                                            seed=seed * 31 + f * 7 + _MW_SIDES.index(side),
                                            avoid=static)
            for off in offsets:
                mw_w, mw_d = _placement_size(seed, f, side, off, wing_w, wing_d,
                                             width_var, depth_var)
                row.append((side, off, mw_w, mw_d))
                # Body only - the offset routine adds its own clearance, so the
                # storey above keeps clear of this roof without double-padding.
                placed.setdefault(f, {}).setdefault(side, []).append(
                    (off - mw_w * 0.5 - 0.05, off + mw_w * 0.5 + 0.05))
        if row:
            out[f] = row
    return out


def _placement_size(seed, floor, side, off, wing_w, wing_d, width_var, depth_var):
    """Deterministic random width/depth for one outcrop (stable per seed+slot)."""
    import random
    key = (int(seed) * 131 + int(floor) * 17 + _MW_SIDES.index(side) * 7
           + int(abs(off) * 1000.0) * 13)
    rng = random.Random(key)
    w = wing_w + rng.uniform(-width_var, width_var) if width_var > 0.0 else wing_w
    d = wing_d + rng.uniform(-depth_var, depth_var) if depth_var > 0.0 else wing_d
    return (max(1.2, w), max(0.9, d))


def build_mini_wing(bm, side, floor_mode, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                    z_base, width=2.2, depth=1.6, height=2.6, roof_style='LEAN_TO', tier='TIER_3',
                    floor_h=2.8, lower_bounds=None,
                    win_w=None, win_h=None, shingle_scale=0.32, shingle_rot=0,
                    off_along=0.0):
    """
    Builds a small outcrop bay room / annex projection:
    - GROUND: rests on grounded stone foundation plinth.
    - UPPER: cantilevered oriel bay with heavy diagonal timber corbel brackets.
    - Features timber corner posts, leaded glass window(s), and dedicated shingled roof.
    ``off_along`` shifts the outcrop along the facade from its centre.
    """
    # Shift the facade line along the wall so several outcrops can share a facade.
    if abs(off_along) > 1e-6:
        if side in ('LEFT', 'RIGHT'):
            wall_y_min += off_along
            wall_y_max += off_along
        else:
            wall_x_min += off_along
            wall_x_max += off_along
        if lower_bounds is not None:
            lb = list(lower_bounds)
            if side in ('LEFT', 'RIGHT'):
                lb[2] += off_along
                lb[3] += off_along
            else:
                lb[0] += off_along
                lb[1] += off_along
            lower_bounds = tuple(lb)
    height = max(2.20, min(height, floor_h * 0.82))
    frame = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = frame.rotation

    half_w = width * 0.5

    # 1. Foundation or Console Corbels
    if floor_mode == 'GROUND':
        found_depth = depth + 0.15
        found_width = width + 0.20
        # Foundation extends all the way down to ground level (z=0)
        found_h = max(0.30, z_base)
        create_beveled_box(
            bm,
            size=(found_depth, found_width, found_h),
            location=frame.to_world(Vector((depth * 0.5 + 0.05, 0.0, found_h * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )
    else:  # UPPER floor oriel bay
        # Heavy carved console corbels springing from the wall below the oriel
        # (accounting for any jetty / pillared offset), matching the balcony
        # brackets instead of plain diagonal beams.
        if lower_bounds is not None:
            lower = get_facade_frame(side, lower_bounds[0], lower_bounds[1], lower_bounds[2], lower_bounds[3])
            inset = max(0.0, (frame.wall_x - lower.wall_x) * frame.out_x + (frame.wall_y - lower.wall_y) * frame.out_y)
        else:
            inset = 0.0
        corbel_w = 0.16
        corbel_depth = depth + 0.20
        # Keep the console short so it never reaches down over the window on the
        # storey below.
        corbel_h = max(0.34, min(0.48, depth * 0.32 + 0.12))
        bracket_spacing = width * 0.34
        for b_sign in (-1.0, 0.0, 1.0):
            loc = frame.to_world(Vector((-inset - 0.02, b_sign * bracket_spacing, z_base - 0.07)))
            create_curved_corbel(
                bm, loc=loc, facing_dir=(frame.out_x, frame.out_y, 0.0),
                width=corbel_w, depth=corbel_depth, height=corbel_h,
                mat_index=MAT_INDEX_TIMBER_FRAME
            )

    # 2. Walk-in Interior Wooden Floor & Ceiling Planks
    # Continuous level walk-in floor
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=frame.to_world(Vector((depth * 0.50, 0.0, z_base + 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Walk-in threshold floor board bridging through the house wall cutout
    mw_portal_w = min(1.30, width - 0.45)
    create_beveled_box(
        bm,
        size=(0.28, mw_portal_w - 0.06, 0.058),
        location=frame.to_world(Vector((-0.12, 0.0, z_base + 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Interior ceiling planks
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=frame.to_world(Vector((depth * 0.50, 0.0, z_base + height - 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )

    # 3. Hollow Walls: Front Wall & Side Walls (Leaving Rear Open into Main Room)
    wall_mat = MAT_INDEX_WOOD if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
    col_w = 0.16
    wall_thick = 0.12

    # Collected wall faces so they can be unwrapped at the engine's wall scale
    # (U along the wall run, V vertical) instead of the generic box unwrap.
    wall_side_faces = []
    wall_front_faces = []

    # 3a. Two Side Walls (Left and Right) - framed between timber corner posts
    for s_sign in [-1, 1]:
        wall_side_faces.extend(create_beveled_box(
            bm,
            size=(depth + 0.02, wall_thick, height),
            location=frame.to_world(Vector((depth * 0.50 + 0.01, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=wall_mat,
            bevel_amount=0.010
        ))
        # Wall-anchor timber trim flat at house wall junction
        create_beveled_box(
            bm,
            size=(0.08, col_w, height + 0.04),
            location=frame.to_world(Vector((0.04, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Outer corner post - thickened + outset to break coplanar
        create_beveled_box(
            bm,
            size=(0.24, 0.24, height + 0.06),
            location=frame.to_world(Vector((depth - col_w * 0.5 + 0.022, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.014
        )
        # Heavy horizontal timber sill beam along side wall base (hides interior floor)
        create_beveled_box(
            bm,
            size=(depth + 0.06, col_w + 0.02, 0.18),
            location=frame.to_world(Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + 0.04))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        # Horizontal timber top plate beam along side wall top (under roof rafter / cheek)
        create_beveled_box(
            bm,
            size=(depth + 0.04, col_w, 0.12),
            location=frame.to_world(Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + height - 0.04))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    # 3b. Outer Front Wall with one or more window bays.
    # Cap the oriel glazing to the hall's own window size so the outcrop never
    # reads as having a bigger window than the rest of the building. Wider
    # outcrops split into multiple evenly-spaced windows instead of one huge pane.
    cap_w = win_w if win_w else 0.95
    cap_h = win_h if win_h else 1.15
    inner_half = max(0.3, half_w - col_w)
    avail_w = inner_half * 2.0
    # Pick the most windows that fit while keeping a sane minimum width and
    # enough centre-to-centre pitch that the open shutters never overlap.
    cap = min(cap_w, 0.98)
    min_win_w = 0.68
    n_win = 1
    win_w = min(cap, max(min_win_w, avail_w * 0.62))
    for _k in (3, 2):
        _step = avail_w / _k
        _w = min(cap, _step * 0.60)
        if _w >= min_win_w and _step >= 1.52 * _w + 0.12:
            n_win, win_w = _k, _w
            break
    win_w = min(win_w, max(min_win_w, avail_w - 0.40))
    bay_step = avail_w / n_win
    win_h = min(cap_h, height * 0.46)
    win_z = z_base + height * 0.52
    win_bot_z = win_z - win_h * 0.5
    win_top_z = win_z + win_h * 0.5
    win_centers = [(-avail_w * 0.5) + (i + 0.5) * bay_step for i in range(n_win)]

    # Outer front wall center
    f_wall_x = depth - wall_thick * 0.5
    # Front spandrel below the window band (full width)
    spand_h = win_bot_z - z_base
    if spand_h > 0.02:
        wall_front_faces.extend(create_beveled_box(
            bm,
            size=(wall_thick, width - col_w * 1.5, spand_h),
            location=frame.to_world(Vector((f_wall_x, 0.0, z_base + spand_h * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=wall_mat,
            bevel_amount=0.010
        ))
    # Front header above the window band (full width)
    head_h = (z_base + height) - win_top_z
    if head_h > 0.02:
        wall_front_faces.extend(create_beveled_box(
            bm,
            size=(wall_thick, width - col_w * 1.5, head_h),
            location=frame.to_world(Vector((f_wall_x, 0.0, win_top_z + head_h * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=wall_mat,
            bevel_amount=0.008
        ))
    # Vertical piers filing the band around and between the windows
    _piers = []
    _edge = -inner_half
    for _c in win_centers:
        _piers.append((_edge, _c - win_w * 0.5))
        _edge = _c + win_w * 0.5
    _piers.append((_edge, inner_half))
    for _p0, _p1 in _piers:
        _pw = _p1 - _p0
        if _pw > 0.04:
            wall_front_faces.extend(create_beveled_box(
                bm,
                size=(wall_thick, _pw, win_h + 0.04),
                location=frame.to_world(Vector((f_wall_x, (_p0 + _p1) * 0.5, win_z))),
                rotation=(0.0, 0.0, frame.rot_z),
                mat_index=wall_mat,
                bevel_amount=0.008
            ))
    # Engine-consistent wall UVs: side runs get U along the depth (local X),
    # front runs get U along the width (local Y); both use V vertical at 0.55/m.
    map_local_wall_uv(bm, wall_side_faces, frame.wall_x, frame.wall_y, facade_rot_mat,
                      u_comp=0, v_comp=2, scale=0.55)
    map_local_wall_uv(bm, wall_front_faces, frame.wall_x, frame.wall_y, facade_rot_mat,
                      u_comp=1, v_comp=2, scale=0.55)

    # Heavy horizontal timber sill plate across front wall base (hides interior floor)
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.18),
        location=frame.to_world(Vector((depth - col_w * 0.5 + 0.015, 0.0, z_base + 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    # Outer top horizontal header beam across front wall top
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.14),
        location=frame.to_world(Vector((depth - col_w * 0.5 + 0.01, 0.0, z_base + height - 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # 4. Window assemblies - reuse the main building's window construction
    # (reveal lining, exterior casing & stone sill, interior casing, glass panes)
    # so the outcrop matches every other window on the hall.
    from ..openings import build_window_assembly
    normal = (facade_rot_mat @ Vector((1.0, 0.0, 0.0)).to_4d()).to_3d()
    for _c in win_centers:
        window_center = frame.to_world(Vector((f_wall_x, _c, win_z)))
        build_window_assembly(
            bm,
            center=(window_center.x, window_center.y, window_center.z),
            size=(win_w, win_h),
            wall_thickness=wall_thick,
            normal_axis=(normal.x, normal.y),
            has_shutters=True,
        )

    # 5. Dedicated shingled roof (shared outcrop roof builder)
    build_outcrop_roof(
        bm, roof_style, frame,
        z_roof=z_base + height, depth=depth, width=width,
        avail_h=max(0.35, floor_h - height - 0.08), wall_mat=wall_mat,
        wall_thick=wall_thick, shingle_scale=shingle_scale, shingle_rot=shingle_rot,
    )
