"""
Interior architecture generator for stylized fantasy buildings.
Generates floor plates with stairwell cutouts, rustic exposed ceiling beams,
staircases (straight/L or fantasy spiral), and roof rafters.
"""

import bpy
import bmesh
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder, recalc_face_normals_safe
from .railing import build_railing, build_railing_post
from .materials import (
    MAT_INDEX_FLOOR, MAT_INDEX_STONE, MAT_INDEX_WOOD, MAT_INDEX_TIMBER,
    MAT_INDEX_STAIRS, MAT_INDEX_RAILING, MAT_INDEX_PLASTER_EXT
)


def _add_floorboard_finish(bm, x_min, x_max, y_min, y_max, z_top, seed=0, thickness=0.10):
    """Build the floor itself from slightly irregular, segmented timber boards rotated 90 degrees (along Y)."""
    rng = __import__('random').Random(731 + seed * 97)
    board_h = thickness
    x = x_min
    col = 0
    while x < x_max - 0.05:
        board_w = min(x_max - x, 0.28 + rng.uniform(-0.035, 0.045))
        y = y_min
        # Stagger every other column along Y: no uninterrupted grid seams.
        if col % 2:
            y -= 0.62 + rng.uniform(-0.14, 0.14)
        while y < y_max - 0.04:
            length = 1.65 + rng.uniform(-0.38, 0.42)
            y2 = min(y_max, y + length)
            if y2 > y_min + 0.04:
                bot = max(y_min, y)
                top = y2
                if top - bot > 0.07:
                    create_beveled_box(
                        bm, size=(max(0.06, board_w - 0.010), top - bot - 0.012, board_h),
                        location=(x + board_w * 0.5, (bot + top) * 0.5,
                                  z_top - board_h * 0.5),
                        mat_index=MAT_INDEX_FLOOR, bevel_amount=0.008
                    )
            y += length
        x += board_w
        col += 1

def build_floor_slab(bm, floor_idx, x_min, x_max, y_min, y_max, z_level, thickness=0.15,
                     stair_hole=None, mat_idx=MAT_INDEX_FLOOR, floor_void=None):
    """
    Builds a solid floor slab. If stair_hole and/or floor_void are provided,
    decomposes the floor into clean non-overlapping rectangular slabs around the openings.
    """
    z_bottom = z_level - thickness
    z_top = z_level

    def add_floor_region(rx_min, rx_max, ry_min, ry_max, region_seed):
        if rx_max - rx_min < 0.04 or ry_max - ry_min < 0.04:
            return
        faces = create_box(
            bm, size=(rx_max - rx_min, ry_max - ry_min, thickness),
            location=((rx_min + rx_max) * 0.5, (ry_min + ry_max) * 0.5,
                      (z_bottom + z_top) * 0.5), mat_index=mat_idx
        )
        if (rx_max - rx_min) < (ry_max - ry_min):
            uv_layer = bm.loops.layers.uv.verify()
            for f in faces:
                zs = [loop.vert.co.z for loop in f.loops]
                if max(zs) - min(zs) > 1e-6:
                    continue
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = Vector((co.y, co.x))
                f.tag = True

    holes = []
    if stair_hole is not None:
        holes.append(stair_hole)
    if floor_void is not None:
        holes.append(floor_void)

    if not holes:
        add_floor_region(x_min, x_max, y_min, y_max, floor_idx)
        return

    # Subtract each hole sequentially from the remaining rectangular regions:
    rects = [(x_min, x_max, y_min, y_max)]
    for hole in holes:
        hx0, hx1, hy0, hy1 = hole
        new_rects = []
        for (rx0, rx1, ry0, ry1) in rects:
            ox0 = max(rx0, hx0)
            ox1 = min(rx1, hx1)
            oy0 = max(ry0, hy0)
            oy1 = min(ry1, hy1)
            if ox1 <= ox0 or oy1 <= oy0:
                new_rects.append((rx0, rx1, ry0, ry1))
                continue
            if rx0 < ox0:
                new_rects.append((rx0, ox0, ry0, ry1))
            if rx1 > ox1:
                new_rects.append((ox1, rx1, ry0, ry1))
            if ry0 < oy0:
                new_rects.append((ox0, ox1, ry0, oy0))
            if ry1 > oy1:
                new_rects.append((ox0, ox1, oy1, ry1))
        rects = new_rects

    for i, (rx0, rx1, ry0, ry1) in enumerate(rects):
        add_floor_region(rx0, rx1, ry0, ry1, floor_idx + i * 17)

def _wood_beam(bm, size, location, bevel_amount=0.015):
    """Creates a horizontal timber beam with UV unwrap aligned along the beam's length.
    Uses MAT_INDEX_TIMBER so ceiling beams match the rich dark timber framing,
    and map_beam_uvs so wood grain flows longitudinally along the beam length.
    """
    from .uv_utils import timber_box
    return timber_box(
        bm,
        size=size,
        location=location,
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=bevel_amount,
    )

def _subtract_interval(segments, cut_start, cut_end):
    """Subtracts [cut_start, cut_end] from a list of (start, end) intervals."""
    new_segs = []
    for a, b in segments:
        if cut_end <= a or cut_start >= b:
            new_segs.append((a, b))
        else:
            if a < cut_start:
                new_segs.append((a, cut_start))
            if b > cut_end:
                new_segs.append((cut_end, b))
    return new_segs


def build_ceiling_beams(bm, x_min, x_max, y_min, y_max, z_ceil, spacing=1.2, beam_w=0.14, beam_d=0.18, stair_hole=None, holes=None):
    """
    Builds rustic timber cross-beams under the ceiling for that classic fantasy tavern interior.
    Beams always span the SHORTEST room distance (floorboards run along the longest).
    Automatically clips and trims beams around stairwells and floor voids so beams never block stairs,
    head clearance, or double-height grand hall voids.
    """
    beam_cz = z_ceil - (beam_d * 0.5)

    all_holes = list(holes) if holes else []
    if stair_hole is not None and stair_hole not in all_holes:
        all_holes.append(stair_hole)

    if (x_max - x_min) <= (y_max - y_min):
        total_y = y_max - y_min
        num_beams = max(2, int(total_y / spacing))
        actual_step = total_y / (num_beams + 1)

        # 1. Framing trimmer beam along the stairwell opening edge
        if stair_hole is not None:
            sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
            trimmer_len = (sh_ymax - sh_ymin) + 0.3
            trimmer_cy = (sh_ymin + sh_ymax) * 0.5
            _wood_beam(
                bm,
                size=(beam_w, trimmer_len, beam_d),
                location=(sh_xmax, trimmer_cy, beam_cz),
                bevel_amount=0.015
            )

        # 2. Cross beams spanning X
        for i in range(1, num_beams + 1):
            by = y_min + i * actual_step

            # Calculate remaining spans after subtracting all holes
            # Beam ends are recessed 1 cm (0.01m) away from hole rims to eliminate coplanar conflicts with ceiling/floor slab
            segments = [(x_min - 0.02, x_max + 0.02)]
            for h in all_holes:
                hx_min, hx_max, hy_min, hy_max = h
                if (hy_min - 0.25) <= by <= (hy_max + 0.25):
                    segments = _subtract_interval(segments, hx_min - 0.01, hx_max + 0.01)

            for seg_a, seg_b in segments:
                w = seg_b - seg_a
                if w >= 0.40:
                    cx = (seg_a + seg_b) * 0.5
                    _wood_beam(
                        bm,
                        size=(w, beam_w, beam_d),
                        location=(cx, by, beam_cz),
                        bevel_amount=0.015
                    )
        return

    total_x = x_max - x_min
    num_beams = max(2, int(total_x / spacing))
    actual_step = total_x / (num_beams + 1)

    # 1. Framing trimmer beam along the stairwell opening edge (room side)
    if stair_hole is not None:
        sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
        trimmer_len = (sh_xmax - sh_xmin) + 0.3
        trimmer_cx = (sh_xmin + sh_xmax) * 0.5
        trim_edge = sh_ymax if (y_max - sh_ymax) >= (sh_ymin - y_min) else sh_ymin
        _wood_beam(
            bm,
            size=(trimmer_len, beam_w, beam_d),
            location=(trimmer_cx, trim_edge, beam_cz),
            bevel_amount=0.015
        )

    # 2. Cross beams spanning Y (the shorter distance)
    for i in range(1, num_beams + 1):
        bx = x_min + i * actual_step

        # Calculate remaining spans after subtracting all holes
        # Beam ends are recessed 1 cm (0.01m) away from hole rims to eliminate coplanar conflicts with ceiling/floor slab
        segments = [(y_min - 0.02, y_max + 0.02)]
        for h in all_holes:
            hx_min, hx_max, hy_min, hy_max = h
            if (hx_min - 0.25) <= bx <= (hx_max + 0.25):
                segments = _subtract_interval(segments, hy_min - 0.01, hy_max + 0.01)

        for seg_a, seg_b in segments:
            h = seg_b - seg_a
            if h >= 0.40:
                cy = (seg_a + seg_b) * 0.5
                _wood_beam(
                    bm,
                    size=(beam_w, h, beam_d),
                    location=(bx, cy, beam_cz),
                    bevel_amount=0.015
                )


def build_interior_trims(bm, x_min, x_max, y_min, y_max, z_floor, z_ceil,
                         wall_thickness=0.28, stair_hole=None, wall_openings=None,
                         skip_sides=None):
    """Build interior baseboards and crown moulding flush to the *inside* wall faces.

    ``wall_openings`` uses the same local-U opening dictionaries as the wall builder.
    Baseboards are split around ground-reaching openings (doors and portals), rather
    than running across the walk-through.  The small inward offset prevents trims
    from poking through the exterior side of a double wall.

    ``skip_sides`` names sides ('front' | 'right' | 'back' | 'left') that must carry
    NO trim at all — use them for walls that open into a wing or an annex, where
    the portal jambs already dress the junction and a baseboard/crown would either
    cross the walk-through or z-fight with the wing's own joinery.
    """
    import math

    trim_h_floor = 0.11
    trim_d = 0.028
    trim_h_ceil = 0.09
    reveal = 0.035
    wall_openings = wall_openings or {}
    skip = set(skip_sides or ())

    # Ordered clockwise so the supplied inward vectors always point into the room.
    sides = (
        ('front', x_min, y_min, x_max, y_min, (0.0, 1.0)),
        ('right', x_max, y_min, x_max, y_max, (-1.0, 0.0)),
        ('back',  x_max, y_max, x_min, y_max, (0.0, -1.0)),
        ('left',  x_min, y_max, x_min, y_min, (1.0, 0.0)),
    )

    def add_trim_segment(x1, y1, x2, y2, inward, z_center, depth, height, bevel):
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 0.08:
            return
        angle = math.atan2(y2 - y1, x2 - x1)
        cx = (x1 + x2) * 0.5 + inward[0] * (depth * 0.5 + 0.002)
        cy = (y1 + y2) * 0.5 + inward[1] * (depth * 0.5 + 0.002)
        create_beveled_box(
            bm, size=(length, depth, height), location=(cx, cy, z_center),
            rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_TIMBER,
            bevel_amount=bevel
        )

    for side, x1, y1, x2, y2, inward in sides:
        if side in skip:
            continue
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length

        # Door/portal openings are stored relative to the exterior wall start.
        # The trim line sits half a wall thickness inboard of that origin, so
        # shift the opening by wall_t/2 before converting to the trim segment
        # (otherwise every cut is half a wall thickness off and the baseboard
        # crosses the doorway).
        cuts = []
        ceil_cuts = []
        reversed_from_wall_builder = side in {'back', 'left'}
        shift = wall_thickness * 0.5
        for opening in wall_openings.get(side, []):
            clr = opening.get('trim_clearance', reveal)
            u0 = opening.get('u_start', 0.0)
            u1 = opening.get('u_end', 0.0)
            if reversed_from_wall_builder:
                a = length - (u1 - shift) - clr
                b = length - (u0 - shift) + clr
            else:
                a = (u0 - shift) - clr
                b = (u1 - shift) + clr
            a = max(0.0, a)
            b = min(length, b)
            if b <= a:
                continue
            z0 = opening.get('z_start', z_floor + 1.0)
            z1 = opening.get('z_end', z0 + 2.0)
            if z0 <= z_floor + trim_h_floor:
                cuts.append((a, b))
            # Only a genuinely full-height opening (reaching the ceiling) may
            # break the crown; a normal window or door lintel below leaves the
            # ceiling trim continuous, so the wall is dressed top AND bottom.
            if z1 >= z_ceil - trim_h_ceil - 0.10:
                ceil_cuts.append((a, b))
        cuts.sort()
        ceil_cuts.sort()

        cursor = 0.0
        for a, b in cuts:
            if a > cursor:
                add_trim_segment(x1 + ux * cursor, y1 + uy * cursor,
                                 x1 + ux * a, y1 + uy * a, inward,
                                 z_floor + trim_h_floor * 0.5, trim_d, trim_h_floor, 0.009)
            cursor = max(cursor, b)
        if cursor < length:
            add_trim_segment(x1 + ux * cursor, y1 + uy * cursor, x2, y2, inward,
                             z_floor + trim_h_floor * 0.5, trim_d, trim_h_floor, 0.009)

        # Crown moulding: continuous along the whole wall unless a full-height
        # opening (a walk-through portal reaching the ceiling) interrupts it.
        trim_h_ceil = 0.09
        z_crown = z_ceil - trim_h_ceil * 0.5 - 0.008
        if ceil_cuts:
            crown_cursor = 0.0
            for a, b in ceil_cuts:
                if a > crown_cursor:
                    add_trim_segment(x1 + ux * crown_cursor, y1 + uy * crown_cursor,
                                     x1 + ux * a, y1 + uy * a, inward,
                                     z_crown, 0.026, trim_h_ceil, 0.008)
                crown_cursor = max(crown_cursor, b)
            if crown_cursor < length:
                add_trim_segment(x1 + ux * crown_cursor, y1 + uy * crown_cursor, x2, y2, inward,
                                 z_crown, 0.026, trim_h_ceil, 0.008)
        else:
            add_trim_segment(x1, y1, x2, y2, inward,
                             z_crown, 0.026, trim_h_ceil, 0.008)

def build_stair_hole_trim(bm, hole, floor_z, thickness=0.12, mat_index=MAT_INDEX_TIMBER,
                          open_side=None, curb_w=0.06, bounds=None, wall_sides=None):
    """
    Builds a neat timber curb trim framing the cut edges of a floor slab around a stair opening.
    Capping timbers sit directly over the cut edges, preventing any raw board ends from showing.
    Any edge bordering a wall is skipped so it never overlaps or z-fights with the wall's bottom baseboard trim.
    Perpendicular curbs terminating into a wall stop cleanly at the baseboard line (trim_margin ~ 0.038m).
    Closed sides are raised 8mm proud of the floor (floor_z + 0.008) and extend 8mm below the soffit
    (floor_z - thickness - 0.008) to completely eliminate any coplanar z-fighting with floor planks or ceiling.
    The open/walk-off side sits at floor_z + 0.002 (2mm beveled threshold) for a smooth walking surface.
    """
    if hole is None:
        return
    hx0, hx1, hy0, hy1 = hole
    if hx1 - hx0 < 0.20 or hy1 - hy0 < 0.20:
        return

    hw = curb_w * 0.5
    z_bot = floor_z - thickness - 0.008

    # Detect wall proximity: any side within 0.45m of the bounding perimeter is considered along a wall
    wsides = set(wall_sides or ())
    if bounds is not None:
        b_xmin, b_xmax, b_ymin, b_ymax = bounds
        if hx0 - b_xmin < 0.45:
            wsides.add('W')
        if b_xmax - hx1 < 0.45:
            wsides.add('E')
        if hy0 - b_ymin < 0.45:
            wsides.add('S')
        if b_ymax - hy1 < 0.45:
            wsides.add('N')

    # Trim margin to cleanly butt into wall baseboard without penetration (baseboard depth is 0.028 + 0.008)
    trim_margin = 0.038

    # Calculate X extent for S and N curbs:
    # If W or E borders a wall, stop at the wall margin instead of extending past the hole edge
    x_start = (hx0 + trim_margin) if ('W' in wsides) else (hx0 - hw)
    x_end = (hx1 - trim_margin) if ('E' in wsides) else (hx1 + hw)

    # Calculate Y extent for W and E curbs:
    # If S or N borders a wall, stop at the wall margin instead of extending into the baseboard
    y_start = (hy0 + trim_margin) if ('S' in wsides) else (hy0 + hw + 0.001)
    y_end = (hy1 - trim_margin) if ('N' in wsides) else (hy1 - hw - 0.001)

    edges = []
    if 'S' not in wsides:
        edges.append(('S', x_start, x_end, hy0 - hw, hy0 + hw, 'X'))
    if 'N' not in wsides:
        edges.append(('N', x_start, x_end, hy1 - hw, hy1 + hw, 'X'))
    if 'W' not in wsides:
        edges.append(('W', hx0 - hw, hx0 + hw, y_start, y_end, 'Y'))
    if 'E' not in wsides:
        edges.append(('E', hx1 - hw, hx1 + hw, y_start, y_end, 'Y'))

    uv_layer = bm.loops.layers.uv.verify()

    for side, x0, x1, y0, y1, axis in edges:
        if x1 - x0 < 0.01 or y1 - y0 < 0.01:
            continue
        is_open = (side == open_side)
        z_top = floor_z + (0.002 if is_open else 0.008)
        cx = (x0 + x1) * 0.5
        cy = (y0 + y1) * 0.5
        cz = (z_bot + z_top) * 0.5
        sx = x1 - x0
        sy = y1 - y0
        sz = z_top - z_bot

        faces = create_beveled_box(
            bm, size=(sx, sy, sz), location=(cx, cy, cz),
            mat_index=mat_index, bevel_amount=0.006
        )
        for f in faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                if axis == 'X':
                    v = (co.x - cx) * 0.85
                    u = (co.y - cy) * 1.5 + (co.z - cz) * 1.5
                else:
                    v = (co.y - cy) * 0.85
                    u = (co.x - cx) * 1.5 + (co.z - cz) * 1.5
                loop[uv_layer].uv = Vector((u, v))
            f.tag = True


def build_stair_guardrail_3sided(bm, sh_x1, sh_x2, sh_y1, sh_y2, floor_z,
                                 climb_side='NORTH', offset=0.08, rail_h=0.95,
                                 bounds=None):
    """
    Builds a safety guardrail on the upper floor around the stairwell opening,
    offset outward from the hole so it sits neatly on the floor along the opening rim.
    The arrival side where you step onto the floor is kept open.
    Any side that is against an exterior or partition wall is skipped to prevent wall intersection.
    Corner posts are cleanly shared so there is zero overlap between adjacent railing segments.
    """
    slab_xmin, slab_xmax, slab_ymin, slab_ymax = bounds if bounds else (-999.0, 999.0, -999.0, 999.0)
    skip = set()
    if sh_x1 - slab_xmin < 0.45:
        skip.add('W')
    if slab_xmax - sh_x2 < 0.45:
        skip.add('E')
    if sh_y1 - slab_ymin < 0.45:
        skip.add('S')
    if slab_ymax - sh_y2 < 0.45:
        skip.add('N')

    open_s = 'N' if str(climb_side).upper().startswith('N') else 'S'
    build_stair_guardrail_one_open(
        bm, (sh_x1, sh_x2, sh_y1, sh_y2), floor_z, open_side=open_s,
        offset=offset, rail_h=rail_h, bounds=bounds, skip_sides=skip
    )


def build_stair_guardrail(bm, rail_x, y_start, y_end, floor_z, rail_h=0.95, return_y=None, x_start=None):
    """
    Builds a safety guardrail on the upper floor along the open edge of the stairwell
    (at X = rail_x, from y_start to y_end).
    If return_y and x_start are given, also adds the short return rail along the open end.
    Uses the shared detailed railing builder with end_overhang=0.0 to prevent wall penetrations.
    """
    if abs(y_end - y_start) >= 0.3:
        build_railing(bm, (rail_x, y_start), (rail_x, y_end), floor_z, height=rail_h, end_overhang=0.0)
    if return_y is not None and x_start is not None and abs(rail_x - x_start) >= 0.3:
        build_railing(bm, (x_start, return_y), (rail_x, return_y), floor_z + 0.0015,
                      height=rail_h - 0.003, braces=False, post_spacing=1.0,
                      post_at_start=False, post_at_end=False, end_overhang=0.0)


def compute_mezzanine_void(hall_bounds, stair_hole=None, min_rim=2.00, doorways=None):
    """Calculates the central double-height opening dimensions inside a grand hall,
    leaving a continuous, fully connected, walkable perimeter rim around upstairs.
    Returns (vx0, vx1, vy0, vy1) or None if space is too narrow.
    Guarantees at least 2.0m of clear walkable floor on every rim and in front of doorways."""
    hx0, hx1, hy0, hy1 = hall_bounds
    hw = hx1 - hx0
    hd = hy1 - hy0
    min_walk = max(2.00, min_rim)
    # Must have room for 2.0m rims on both sides plus at least 1.6m void
    if hw < (min_walk * 2.0 + 1.6) or hd < (min_walk * 2.0 + 1.6):
        return None

    rim_w_left = min_walk
    if stair_hole is not None:
        sx0, sx1, sy0, sy1 = stair_hole
        # If stairs are on the west side of this hall, ensure the west rim clears the stair landing by >= 2.0m
        if sx1 > hx0 and sx0 < hx1:
            rim_w_left = max(min_walk, (sx1 - hx0) + 2.00)

    rim_w_right = min_walk
    rim_w_south = min_walk
    rim_w_north = min_walk

    # Check doorways around the hall perimeter to maintain at least 2.0m solid landing
    if doorways:
        for dw in doorways:
            dx = dw.get('x', (hx0 + hx1) * 0.5)
            dy = dw.get('y', (hy0 + hy1) * 0.5)
            d_axis = dw.get('axis', 'X')
            if d_axis == 'Y':
                if abs(dx - hx0) <= 0.65 and (hy0 - 0.5 <= dy <= hy1 + 0.5):
                    rim_w_left = max(rim_w_left, (dx - hx0) + 2.00)
                elif abs(dx - hx1) <= 0.65 and (hy0 - 0.5 <= dy <= hy1 + 0.5):
                    rim_w_right = max(rim_w_right, (hx1 - dx) + 2.00)
            else:
                if abs(dy - hy0) <= 0.65 and (hx0 - 0.5 <= dx <= hx1 + 0.5):
                    rim_w_south = max(rim_w_south, (dy - hy0) + 2.00)
                elif abs(dy - hy1) <= 0.65 and (hx0 - 0.5 <= dx <= hx1 + 0.5):
                    rim_w_north = max(rim_w_north, (hy1 - dy) + 2.00)

    # Don't let rims swallow the void completely if hall is wide enough
    if (rim_w_left + rim_w_right) > hw - 1.6:
        excess = (rim_w_left + rim_w_right) - (hw - 1.6)
        rim_w_left = max(min_walk, rim_w_left - excess * 0.5)
        rim_w_right = max(min_walk, rim_w_right - excess * 0.5)

    if (rim_w_south + rim_w_north) > hd - 1.6:
        excess = (rim_w_south + rim_w_north) - (hd - 1.6)
        rim_w_south = max(min_walk, rim_w_south - excess * 0.5)
        rim_w_north = max(min_walk, rim_w_north - excess * 0.5)

    vx0 = hx0 + rim_w_left
    vx1 = hx1 - rim_w_right
    vy0 = hy0 + rim_w_south
    vy1 = hy1 - rim_w_north

    if (vx1 - vx0) < 1.6 or (vy1 - vy0) < 1.6:
        return None
    return (vx0, vx1, vy0, vy1)


def build_mezzanine_void_railing(bm, vx0, vx1, vy0, vy1, floor_z, height=0.98):
    """Builds a complete protective perimeter balustrade around a double-height floor void.
    Corner posts are shared cleanly at the 4 corners of the void."""
    from .railing import build_railing
    if (vx1 - vx0) < 0.5 or (vy1 - vy0) < 0.5:
        return
    # West run: from (vx0, vy0) to (vx0, vy1)
    build_railing(bm, (vx0, vy0), (vx0, vy1), floor_z, height=height,
                  post_at_start=True, post_at_end=True, post_spacing=1.4, baluster_spacing=0.22)
    # East run: from (vx1, vy0) to (vx1, vy1)
    build_railing(bm, (vx1, vy0), (vx1, vy1), floor_z, height=height,
                  post_at_start=True, post_at_end=True, post_spacing=1.4, baluster_spacing=0.22)
    # South run: from (vx0, vy0) to (vx1, vy0) (omit corner posts since side runs placed them)
    build_railing(bm, (vx0, vy0), (vx1, vy0), floor_z, height=height,
                  post_at_start=False, post_at_end=False, post_spacing=1.4, baluster_spacing=0.22)
    # North run: from (vx0, vy1) to (vx1, vy1) (omit corner posts)
    build_railing(bm, (vx0, vy1), (vx1, vy1), floor_z, height=height,
                  post_at_start=False, post_at_end=False, post_spacing=1.4, baluster_spacing=0.22)


def _build_stringer_prism(bm, p_start, p_end, z0, z_head, stringer_thick,
                          axis='Y', mat_index=MAT_INDEX_STAIRS,
                          trim_head_clearance=0.08, stringer_h=0.34):
    """
    Builds a structural wooden stringer prism that:
    - Continues all the way down to the floor at the bottom (rests flat on floor at z0).
    - Stops just below the frame/trim for the stair hole on the top (at z_head - trim_head_clearance).
    - Has strictly vertical end faces against newel posts and hole rims.
    - Zero protruding sharp corners, zero dangling ends in mid-air.
    """
    if axis == 'Y':
        s0 = p_start[0]
        r0 = p_start[1]
        r1 = p_end[1]
    else:
        s0 = p_start[1]
        r0 = p_start[0]
        r1 = p_end[0]

    L = abs(r1 - r0)
    if L < 0.10:
        return []
    dir_r = 1.0 if r1 >= r0 else -1.0
    dz = z_head - z0
    m = dz / L

    h_front = min(0.24, max(0.16, dz / 14 + 0.04))
    z_head_cut = z_head - trim_head_clearance

    # Top cutoff where slope hits underside of trim
    u_top_cut = max(0.0, min(L, (z_head_cut - (z0 + h_front)) / m))
    # Bottom cutoff where bottom slope hits floor
    u_bot_cut = max(0.0, min(L, (stringer_h - h_front) / m))
    z_bot_end = max(z0, z0 + h_front + m * L - stringer_h)

    # 2D profile polygon in (u, z) relative to (r0, z0)
    u_start = 0.162  # Disjoint hairline gap from newel post bottom (POST_W = 0.16 in railing.py)
    poly = [
        (u_start, z0),
        (u_start, z0 + h_front),
    ]
    if u_top_cut < L - 0.02:
        poly.append((u_top_cut, z_head_cut))
    poly.append((L, z_head_cut))
    poly.append((L, z_bot_end))
    if u_bot_cut > u_start + 0.02:
        poly.append((u_bot_cut, z0))

    s1 = s0 - stringer_thick * 0.5
    s2 = s0 + stringer_thick * 0.5

    v_in = []
    v_out = []
    for u, z in poly:
        r = r0 + u * dir_r
        if axis == 'Y':
            v_in.append(bm.verts.new((s1, r, z)))
            v_out.append(bm.verts.new((s2, r, z)))
        else:
            v_in.append(bm.verts.new((r, s1, z)))
            v_out.append(bm.verts.new((r, s2, z)))

    faces = []
    f_side1 = bm.faces.new(v_in)
    f_side2 = bm.faces.new(reversed(v_out))
    faces.extend([f_side1, f_side2])

    N = len(poly)
    for i in range(N):
        i_next = (i + 1) % N
        f_rim = bm.faces.new([v_in[i], v_in[i_next], v_out[i_next], v_out[i]])
        faces.append(f_rim)

    recalc_face_normals_safe(bm, faces)

    diag_len = math.sqrt(L * L + dz * dz)
    t_r = (L / diag_len) * dir_r
    t_z = dz / diag_len
    n_r = -(dz / diag_len) * dir_r
    n_z = L / diag_len

    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        if not f.is_valid:
            continue
        f.material_index = mat_index
        nx = abs(f.normal.x)
        ny = abs(f.normal.y)
        is_side = (axis == 'Y' and nx > 0.5) or (axis == 'X' and ny > 0.5)
        for loop in f.loops:
            co = loop.vert.co
            dist_run = (co.y - r0) if axis == 'Y' else (co.x - r0)
            delta_z = co.z - z0
            dist_along = dist_run * t_r + delta_z * t_z
            dist_perp = dist_run * n_r + delta_z * n_z
            dist_lat = (co.x - s0) if axis == 'Y' else (co.y - s0)

            v_coord = dist_along * 0.40
            u_coord = dist_perp * 1.2 if is_side else dist_lat * 1.2
            loop[uv_layer].uv = Vector((u_coord, v_coord))
        f.tag = True

    return faces


def build_straight_staircase(
    bm, start_pos, target_z,
    stair_width=1.40, stair_depth=2.6, num_steps=14,
    direction_y=1, base_anchor=False, top_anchor=False,
    bounds=None, axis='Y', direction_x=1,
    has_rail_left=None, has_rail_right=None
):
    """
    Generates a wooden straight/run staircase with:
    - Chunky treads with grain aligned strictly along the length of each board.
    - Grounded stringers that continue all the way to the floor at the bottom
      and stop cleanly just below the frame/trim of the stair hole at the top.
    - Clean newel posts and railings with zero intersecting sharp corners.
    - NO extra fake box steps at the bottom or top.
    Supports axis='Y' (default) and axis='X'.
    """
    x0, y0, z0 = start_pos
    dz = target_z - z0
    step_h = dz / num_steps

    if axis == 'Y':
        dir_run = direction_y
        run_depth = stair_depth * dir_run
        step_d = (stair_depth / num_steps) * dir_run
    else:
        dir_run = direction_x
        run_depth = stair_depth * dir_run
        step_d = (stair_depth / num_steps) * dir_run

    tread_d = (stair_depth / num_steps) + 0.04
    tread_thick = 0.045
    stringer_thick = 0.08
    stringer_h = 0.34

    uv_layer = bm.loops.layers.uv.verify()

    # Treads penetrate 12mm into stringers, risers penetrate 6mm so lateral end faces never touch
    tread_w = stair_width - 2 * stringer_thick + 0.024
    riser_w = stair_width - 2 * stringer_thick + 0.012

    for i in range(num_steps):
        # Embed riser top 2mm into underside of tread above to seal joint without protruding,
        # and embed riser bottom 2mm into tread below (or floor for i=0).
        # Tread sits cleanly ON TOP of the riser.
        r_bot = (z0 - 0.003) if i == 0 else (z0 + i * step_h - 0.002)
        r_top = z0 + (i + 1) * step_h - tread_thick + 0.002
        this_riser_h = max(0.04, r_top - r_bot)
        rz = (r_bot + r_top) * 0.5
        ru = (i * abs(step_d)) * dir_run

        if axis == 'Y':
            riser_loc = (x0, y0 + ru + 0.015 * dir_run, rz)
            riser_size = (riser_w, 0.035, this_riser_h)
        else:
            riser_loc = (x0 + ru + 0.015 * dir_run, y0, rz)
            riser_size = (0.035, riser_w, this_riser_h)

        riser_faces = create_box(bm, size=riser_size, location=riser_loc, mat_index=MAT_INDEX_STAIRS)
        for f in riser_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                if axis == 'Y':
                    v = (co.x - (x0 - riser_w * 0.5)) * 0.85 + (i * 0.37 + 0.15)
                    u = (co.z - r_bot) * 1.6 + (co.y - riser_loc[1]) * 1.2
                else:
                    v = (co.y - (y0 - riser_w * 0.5)) * 0.85 + (i * 0.37 + 0.15)
                    u = (co.z - r_bot) * 1.6 + (co.x - riser_loc[0]) * 1.2
                loop[uv_layer].uv = Vector((u, v))
            f.tag = True

        # Tread sits cleanly on top of riser for every step including the final top step
        tz = z0 + (i + 1) * step_h - tread_thick * 0.5
        tu = (i + 0.5) * step_d + 0.015 * dir_run
        if axis == 'Y':
            tread_loc = (x0, y0 + tu, tz)
            tread_size = (tread_w, tread_d, tread_thick)
        else:
            tread_loc = (x0 + tu, y0, tz)
            tread_size = (tread_d, tread_w, tread_thick)

        tread_faces = create_beveled_box(
            bm, size=tread_size, location=tread_loc,
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.01
        )
        for f in tread_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                if axis == 'Y':
                    v = (co.x - x0) * 0.85 + (i * 0.31)
                    u = (co.y - tread_loc[1]) * 1.5 + (co.z - tz) * 1.4
                else:
                    v = (co.y - y0) * 0.85 + (i * 0.31)
                    u = (co.x - tread_loc[0]) * 1.5 + (co.z - tz) * 1.4
                loop[uv_layer].uv = Vector((u, v))
            f.tag = True

    # 2. Structural Side Stringers (grounded at floor, capped below trim at head)
    # Kept inside stair_width so the flight clears the floor hole and trim frame cleanly.
    str_offset = stair_width * 0.5 - stringer_thick * 0.5
    for side in [-1, 1]:
        if axis == 'Y':
            str_x = x0 + side * str_offset
            p_s = (str_x, y0)
            p_e = (str_x, y0 + run_depth)
        else:
            str_y = y0 + side * str_offset
            p_s = (x0, str_y)
            p_e = (x0 + run_depth, str_y)

        _build_stringer_prism(
            bm, p_s, p_e, z0, target_z, stringer_thick,
            axis=axis, mat_index=MAT_INDEX_STAIRS,
            trim_head_clearance=0.08, stringer_h=stringer_h
        )

    # 3. Guard Railings with End Pillars (Newel Posts)
    POST_W = 0.16
    bot_post_h = 1.10
    top_post_h = 1.00
    rail_h = 0.85
    tan_pitch = dz / stair_depth
    u_start = 0.162
    z_head_cut = target_z - 0.08
    h_front = min(0.24, max(0.16, dz / 14 + 0.04))

    for side in [-1, 1]:
        if axis == 'Y':
            rail_s = x0 + side * str_offset
            if bounds is not None:
                slab_xmin, slab_xmax, slab_ymin, slab_ymax = bounds
                if side == -1 and (rail_s - slab_xmin < 0.35):
                    continue
                if side == 1 and (slab_xmax - rail_s < 0.35):
                    continue
            if side == -1 and has_rail_left is False:
                continue
            if side == 1 and has_rail_right is False:
                continue

            bot_post_r = y0 + (POST_W * 0.5) * dir_run
            top_post_r = y0 + (stair_depth - POST_W * 0.5) * dir_run

            build_railing_post(bm, rail_s, bot_post_r, z0, height=bot_post_h,
                               iron_pin=False, jankiness=0.0)
            build_railing_post(bm, rail_s, top_post_r, target_z, height=top_post_h,
                               iron_pin=False, jankiness=0.0)

            r_start = bot_post_r + (POST_W * 0.5) * dir_run
            r_end = top_post_r - (POST_W * 0.5) * dir_run
            dist_start = abs(r_start - y0)
            dist_end = abs(r_end - y0)
            z_start = min(z_head_cut, z0 + h_front + tan_pitch * max(0.0, dist_start - u_start))
            z_end = min(z_head_cut, z0 + h_front + tan_pitch * max(0.0, dist_end - u_start))

            build_railing(
                bm, (rail_s, r_start), (rail_s, r_end),
                z_start, height=rail_h, base_z_end=z_end,
                has_sill=False, posts=False, post_at_start=False, post_at_end=False,
                baluster_spacing=0.20, end_overhang=0.06, braces=False
            )
        else:
            rail_s = y0 + side * str_offset
            if bounds is not None:
                slab_xmin, slab_xmax, slab_ymin, slab_ymax = bounds
                if side == -1 and (rail_s - slab_ymin < 0.35):
                    continue
                if side == 1 and (slab_ymax - rail_s < 0.35):
                    continue
            if side == -1 and has_rail_left is False:
                continue
            if side == 1 and has_rail_right is False:
                continue

            bot_post_r = x0 + (POST_W * 0.5) * dir_run
            top_post_r = x0 + (stair_depth - POST_W * 0.5) * dir_run

            build_railing_post(bm, bot_post_r, rail_s, z0, height=bot_post_h,
                               iron_pin=False, jankiness=0.0)
            build_railing_post(bm, top_post_r, rail_s, target_z, height=top_post_h,
                               iron_pin=False, jankiness=0.0)

            r_start = bot_post_r + (POST_W * 0.5) * dir_run
            r_end = top_post_r - (POST_W * 0.5) * dir_run
            dist_start = abs(r_start - x0)
            dist_end = abs(r_end - x0)
            z_start = min(z_head_cut, z0 + h_front + tan_pitch * max(0.0, dist_start - u_start))
            z_end = min(z_head_cut, z0 + h_front + tan_pitch * max(0.0, dist_end - u_start))

            build_railing(
                bm, (r_start, rail_s), (r_end, rail_s),
                z_start, height=rail_h, base_z_end=z_end,
                has_sill=False, posts=False, post_at_start=False, post_at_end=False,
                baluster_spacing=0.20, end_overhang=0.06, braces=False
            )


def build_straight_stairs(bm, start_pos, target_z, width=1.40, length=2.6,
                          direction=None, has_railings=True):
    """Compatibility wrapper for callers using the older straight-stair API."""
    direction_y = 1
    direction_x = 1
    axis = 'Y'
    if direction is not None:
        if abs(direction.x) > abs(direction.y):
            axis = 'X'
            direction_x = 1 if direction.x >= 0 else -1
        else:
            direction_y = 1 if direction.y >= 0 else -1

    return build_straight_staircase(
        bm,
        start_pos=start_pos,
        target_z=target_z,
        stair_width=width,
        stair_depth=length,
        direction_y=direction_y,
        direction_x=direction_x,
        axis=axis,
        has_rail_left=has_railings,
        has_rail_right=has_railings,
    )


def _l_stair_run(bm, foot_xy, top_xy, z0, z1, width, along_axis):
    """One flight of an L-stair: risers + treads climbing from z0 to z1, with
    the wood grain unwrapped ALONG the length of each step (V along the tread
    length, U across) so it never runs crossways. ``along_axis`` is 'Y' or 'X'."""
    import math as _m
    uv_layer = bm.loops.layers.uv.verify()
    fx, fy = foot_xy
    tx, ty = top_xy
    horiz = _m.hypot(tx - fx, ty - fy)
    n = max(3, int(round(abs(z1 - z0) / 0.20)))
    step_h = (z1 - z0) / n
    step_d = (horiz / n)
    for i in range(n):
        frac = (i + 0.5) / n
        cx = fx + (tx - fx) * frac
        cy = fy + (ty - fy) * frac
        sz = z0 + (i + 0.5) * step_h
        if along_axis == 'Y':
            tread = create_beveled_box(bm, size=(width, step_d + 0.05, 0.05),
                                       location=(cx, cy, sz), mat_index=MAT_INDEX_WOOD,
                                       bevel_amount=0.010)
            riser = create_box(bm, size=(width - 0.02, 0.035, step_h),
                               location=(cx, cy - (ty - fy) / n * 0.5, sz - step_h * 0.5),
                               mat_index=MAT_INDEX_STAIRS)
        else:
            tread = create_beveled_box(bm, size=(step_d + 0.05, width, 0.05),
                                       location=(cx, cy, sz), mat_index=MAT_INDEX_WOOD,
                                       bevel_amount=0.010)
            riser = create_box(bm, size=(0.035, width - 0.02, step_h),
                               location=(cx - (tx - fx) / n * 0.5, cy, sz - step_h * 0.5),
                               mat_index=MAT_INDEX_STAIRS)
        # Treads: grain (V) along the step's length, U across the tread.
        for f in tread:
            if not f.is_valid:
                continue
            nx, ny, nz = abs(f.normal.x), abs(f.normal.y), abs(f.normal.z)
            for loop in f.loops:
                co = loop.vert.co
                if nz >= nx and nz >= ny:
                    if along_axis == 'Y':
                        u, v = (co.y - cy) * 1.1, (co.x - cx) * 1.5
                    else:
                        u, v = (co.x - cx) * 1.1, (co.y - cy) * 1.5
                elif ny >= nx:
                    u, v = (co.x - cx) * 1.5, (co.z - sz) * 1.1
                else:
                    u, v = (co.y - cy) * 1.5, (co.z - sz) * 1.1
                loop[uv_layer].uv = Vector((u, v))
        # Risers: grain along the step width, so the riser reads as a board.
        for f in riser:
            if not f.is_valid:
                continue
            nz2 = abs(f.normal.z)
            for loop in f.loops:
                co = loop.vert.co
                if nz2 > 0.5:
                    u, v = (co.x - cx) * 1.2, (co.y - cy) * 1.2
                else:
                    u, v = (co.x - cx) * 1.5, (co.z - (sz - step_h * 0.5)) * 1.0
                loop[uv_layer].uv = Vector((u, v))


def _l_stair_rail(bm, p0xy, p1xy, z0, z1, out_xy, h=0.92):
    """A sloped handrail with balusters along one edge of an L-stair flight."""
    import math as _m
    x0, y0 = p0xy
    x1, y1 = p1xy
    ox, oy = out_xy
    dx, dy = (x1 - x0), (y1 - y0)
    run = _m.hypot(dx, dy) or 1e-4
    ux, uy = dx / run, dy / run
    # Sloped rail beam.
    L = _m.hypot(run, z1 - z0)
    pitch = _m.atan2(z1 - z0, run)
    # create_box(): length along Y, so yaw the beam to the run then pitch it.
    yaw = _m.atan2(dx, dy)
    create_box(bm, size=(0.06, L, 0.07),
               location=((x0 + x1) * 0.5 + ox, (y0 + y1) * 0.5 + oy,
                         (z0 + z1) * 0.5 + h),
               rotation=(pitch, 0.0, yaw), mat_index=MAT_INDEX_STAIRS)
    # Balusters.
    nb = max(2, int(run / 0.22))
    for i in range(nb + 1):
        f = i / float(nb)
        bx = x0 + dx * f + ox
        by = y0 + dy * f + oy
        bz = z0 + (z1 - z0) * f
        create_box(bm, size=(0.035, 0.035, h),
                   location=(bx, by, bz + h * 0.5), mat_index=MAT_INDEX_STAIRS)


def _merge_bmesh(dst, src):
    """Copy every face of ``src`` into ``dst`` (positions, material and UVs)."""
    uv_s = src.loops.layers.uv.verify()
    uv_d = dst.loops.layers.uv.verify()
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(v.co)
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        nf.material_index = f.material_index
        nf.smooth = f.smooth
        for l_s, l_d in zip(f.loops, nf.loops):
            l_d[uv_d].uv = l_s[uv_s].uv
    dst.verts.index_update()
    dst.faces.index_update()


def build_turned_flight(bm, foot_xy, top_xy, z0, z1, width, along_axis='Y',
                        num_steps=14, base_anchor=True, top_anchor=True):
    """One full-storey flight built with the NORMAL straight-staircase geometry
    (chunky treads, closed stringers, end pillars and rails on both sides),
    oriented along 'Y' or 'X'. Used to make the turned-flight staircase: an X
    run is built as an ordinary +Y flight and then yawed 90 degrees about its
    foot, rotating ONLY the newly added verts so nothing else is disturbed."""
    fx, fy = foot_xy
    tx, ty = top_xy
    dz = abs(z1 - z0)
    run = abs(ty - fy) if along_axis == 'Y' else abs(tx - fx)
    # Balance riser (~0.185 m) and tread (~0.30 m) so no flight is stretched
    # (deep treads) or mushed (short treads): pick the step count that keeps
    # BOTH within comfortable bounds, clamped to a sane range.
    steps_rise = max(2, int(round(dz / 0.185)))
    steps_run = max(2, int(round(run / 0.30)))
    num_steps = max(4, min(24, min(steps_rise, steps_run)))
    if along_axis == 'Y':
        direction = 1 if ty >= fy else -1
        build_straight_staircase(bm, (fx, fy, z0), z1, stair_width=width,
                                 stair_depth=run, num_steps=num_steps,
                                 direction_y=direction,
                                 base_anchor=base_anchor, top_anchor=top_anchor)
        return
    dz = abs(z1 - z0)
    run = abs(tx - fx)
    steps_rise = max(2, int(round(dz / 0.185)))
    steps_run = max(2, int(round(run / 0.30)))
    num_steps = max(4, min(24, min(steps_rise, steps_run)))
    before = set(bm.verts)
    build_straight_staircase(bm, (fx, fy, z0), z1, stair_width=width,
                             stair_depth=run, num_steps=num_steps,
                             direction_y=1,
                             base_anchor=base_anchor, top_anchor=top_anchor)
    ang = -math.pi * 0.5 if tx >= fx else math.pi * 0.5
    moving = [v for v in bm.verts if v not in before]
    if moving:
        bmesh.ops.rotate(bm, cent=Vector((fx, fy, 0.0)),
                         matrix=Matrix.Rotation(ang, 3, 'Z'), verts=moving)
    bm.verts.index_update()


def build_stair_landing(bm, cx, cy, z_top, size=2.0):
    """A solid square landing platform at the top of a flight; wood grain runs
    along X. Returns the (x0, x1, y0, y1) rect it occupies."""
    _land = create_beveled_box(bm, size=(size, size, 0.12),
                               location=(cx, cy, z_top - 0.06),
                               mat_index=MAT_INDEX_STAIRS, bevel_amount=0.012)
    _uvl = bm.loops.layers.uv.verify()
    for _f in _land:
        if not _f.is_valid:
            continue
        _nz = abs(_f.normal.z)
        for _loop in _f.loops:
            _co = _loop.vert.co
            if _nz > 0.5:
                _u, _v = (_co.y - cy) * 1.2, (_co.x - cx) * 1.5
            else:
                _u, _v = (_co.x - cx) * 1.5, (_co.z - z_top) * 1.2
            _loop[_uvl].uv = Vector((_u, _v))
        _f.tag = True
    return (cx - size * 0.5, cx + size * 0.5, cy - size * 0.5, cy + size * 0.5)


def build_stair_guardrail_one_open(bm, hole, floor_z, open_side,
                                   offset=0.08, rail_h=0.95, bounds=None,
                                   skip_sides=None):
    """Guard a rectangular stair opening on all sides EXCEPT ``open_side``
    ('N', 'S', 'E' or 'W') where you step onto/off the flight, and any side in
    ``skip_sides`` (e.g. a side that sits against a wall).
    Corner posts are cleanly shared so there is zero duplicate post or coplanar overlap."""
    if hole is None:
        return
    x0, x1, y0, y1 = hole
    if bounds:
        sx0, sx1, sy0, sy1 = bounds
    else:
        sx0, sx1, sy0, sy1 = x0 - 99.0, x1 + 99.0, y0 - 99.0, y1 + 99.0
    xl = max(sx0 + 0.06, x0 - offset)
    xr = min(sx1 - 0.06, x1 + offset)
    yl = max(sy0 + 0.06, y0 - offset)
    yr = min(sy1 - 0.06, y1 + offset)

    skip = set(skip_sides or ())
    open_s = str(open_side or '').upper()[:1]

    # Side configurations with clean corner post sharing:
    # Closed cross-railings are lifted 1.5mm to eliminate coplanar intersection at corner posts.
    if open_s == 'N':
        # Open on North (arrival end)
        if 'W' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xl, yl), (xl, yr), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'E' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xr, yl), (xr, yr), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'S' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xl, yl), (xr, yl), floor_z + 0.0015, height=rail_h - 0.003,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=('W' in skip), post_at_end=('E' in skip), end_overhang=0.0)
    elif open_s == 'S':
        # Open on South (arrival end)
        if 'W' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xl, yr), (xl, yl), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'E' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xr, yr), (xr, yl), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'N' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xl, yr), (xr, yr), floor_z + 0.0015, height=rail_h - 0.003,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=('W' in skip), post_at_end=('E' in skip), end_overhang=0.0)
    elif open_s == 'E':
        # Open on East (arrival end)
        if 'S' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xl, yl), (xr, yl), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'N' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xl, yr), (xr, yr), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'W' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xl, yl), (xl, yr), floor_z + 0.0015, height=rail_h - 0.003,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=('S' in skip), post_at_end=('N' in skip), end_overhang=0.0)
    else:  # 'W'
        # Open on West (arrival end)
        if 'S' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xr, yl), (xl, yl), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'N' not in skip and (xr - xl) >= 0.30:
            build_railing(bm, (xr, yr), (xl, yr), floor_z, height=rail_h,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=True, post_at_end=True, end_overhang=0.0)
        if 'E' not in skip and (yr - yl) >= 0.30:
            build_railing(bm, (xr, yl), (xr, yr), floor_z + 0.0015, height=rail_h - 0.003,
                          post_spacing=1.25, baluster_spacing=0.20, braces=False,
                          post_at_start=('S' in skip), post_at_end=('N' in skip), end_overhang=0.0)


def build_spiral_staircase(bm, center_pos, target_z, radius=1.35, num_steps=18, start_ang_deg=-90.0, total_angle_deg=360.0):
    """
    Generates a continuous multi-floor fantasy spiral staircase.
    Rotates a full 360 degrees per storey so each floor arrives and departs
    at the exact same walkable orientation.
    """
    cx, cy, z0 = center_pos
    dz = target_z - z0
    step_h = dz / num_steps
    ang_rad = math.radians(total_angle_deg)
    step_ang = ang_rad / num_steps
    base_ang = math.radians(start_ang_deg)
    
    # 1. Central wooden column segment for this storey
    col_r = 0.16
    create_cylinder(
        bm,
        radius=col_r,
        height=dz + 0.05,
        segments=12,
        location=(cx, cy, z0 + dz * 0.5),
        mat_index=MAT_INDEX_WOOD
    )
    
    # 2. Wedge steps with wood fibers running along radial length (V axis)
    step_len = radius - col_r
    posts = []
    uv_layer = bm.loops.layers.uv.verify()
    
    for i in range(num_steps):
        cur_ang = base_ang + i * step_ang
        # Step rises from z0 to target_z
        cur_z = z0 + (i + 1) * step_h
        
        mid_ang = cur_ang + step_ang * 0.5
        mid_r = col_r + step_len * 0.5
        sx = cx + mid_r * math.cos(mid_ang)
        sy = cy + mid_r * math.sin(mid_ang)
        
        # Step wedge plank
        step_w = 2.0 * mid_r * math.tan(step_ang * 0.5) * 1.15
        tread_faces = create_beveled_box(
            bm,
            size=(step_len + 0.04, max(0.24, step_w), 0.065),
            location=(sx, sy, cur_z - 0.032),
            rotation=(0.0, 0.0, mid_ang),
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.01
        )
        cos_ang = math.cos(mid_ang)
        sin_ang = math.sin(mid_ang)
        for f in tread_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                dx = co.x - sx
                dy = co.y - sy
                # Local coordinates: lx along radial length of step board, ly across width
                lx = dx * cos_ang + dy * sin_ang
                ly = -dx * sin_ang + dy * cos_ang
                v = lx * 0.45 + (i * 0.31)
                u = ly * 1.6 + (co.z - cur_z) * 1.4 + (i * 0.17)
                loop[uv_layer].uv = Vector((u, v))
            f.tag = True
        
        # Outer banister point on every step (post added after the loop)
        px = cx + (radius - 0.04) * math.cos(mid_ang)
        py = cy + (radius - 0.04) * math.sin(mid_ang)
        posts.append(Vector((px, py, cur_z)))
        
    # 3. Dedicated Top Landing Platform (flushes perfectly with upper floor level at target_z)
    land_len = step_len + 0.35
    land_w = max(0.50, 2.0 * (col_r + land_len * 0.5) * math.tan(step_ang * 0.5) * 1.5)
    land_r = col_r + land_len * 0.5
    land_ang = base_ang + ang_rad
    land_x = cx + land_r * math.cos(land_ang)
    land_y = cy + land_r * math.sin(land_ang)
    land_faces = create_beveled_box(
        bm,
        size=(land_len, land_w, 0.065),
        location=(land_x, land_y, target_z - 0.032),
        rotation=(0.0, 0.0, land_ang),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.012
    )
    cos_lang = math.cos(land_ang)
    sin_lang = math.sin(land_ang)
    for f in land_faces:
        if not f.is_valid:
            continue
        for loop in f.loops:
            co = loop.vert.co
            dx = co.x - land_x
            dy = co.y - land_y
            lx = dx * cos_lang + dy * sin_lang
            ly = -dx * sin_lang + dy * cos_lang
            v = lx * 0.45
            u = ly * 1.6 + (co.z - target_z) * 1.4
            loop[uv_layer].uv = Vector((u, v))
        f.tag = True
    
    # Top landing banister point
    top_px = cx + (radius + 0.15) * math.cos(land_ang)
    top_py = cy + (radius + 0.15) * math.sin(land_ang)
    posts.append(Vector((top_px, top_py, target_z)))

    # 4. Detailed banister around the helix: a capped newel per step plus the
    # shared railing joinery (sill, rails, balusters) between them.
    rail_h = 0.92
    for _i, p in enumerate(posts):
        build_railing_post(bm, p.x, p.y, p.z, rail_h, index=_i, seed=3)
    for idx in range(len(posts) - 1):
        p1 = posts[idx]
        p2 = posts[idx + 1]
        build_railing(bm, (p1.x, p1.y), (p2.x, p2.y), p1.z, height=rail_h,
                      base_z_end=p2.z, posts=False, braces=False,
                      end_overhang=0.0, baluster_spacing=0.16, seed=idx + 5)

def build_attic_trusses(bm, x_min, x_max, y_min, y_max, z_base, ridge_z, spacing=1.5, sway_amount=0.0):
    """
    Builds visible A-frame roof trusses and collar beams strictly inside the top floor/attic cavity.
    Safe clearance ensures rafters never poke through roof decking under sway or wonkiness.
    """
    total_y = y_max - y_min
    num_trusses = max(2, int(total_y / spacing))
    actual_step = total_y / (num_trusses + 1)
    
    cx = (x_min + x_max) * 0.5
    half_w = (x_max - x_min) * 0.5
    
    beam_w = 0.12
    beam_d = 0.14
    
    for i in range(1, num_trusses + 1):
        ty = y_min + i * actual_step
        t_span = (ty - y_min) / max(0.01, total_y)
        local_sag = math.sin(t_span * math.pi) * sway_amount
        local_ridge_z = ridge_z - local_sag
        h_roof = max(0.5, local_ridge_z - z_base)
        
        # Left rafter (inside attic, from eaves up to ridge with safe margin)
        p_left_start = Vector((cx - half_w + 0.45, ty, z_base + 0.08))
        p_left_end = Vector((cx - 0.06, ty, local_ridge_z - 0.40))
        left_mid = (p_left_start + p_left_end) * 0.5
        left_len = (p_left_end - p_left_start).length
        local_pitch_l = math.atan2(p_left_end.z - p_left_start.z, p_left_end.x - p_left_start.x)
        
        create_box(
            bm,
            size=(left_len, beam_w, beam_d),
            location=left_mid,
            rotation=(0.0, -local_pitch_l, 0.0),
            mat_index=MAT_INDEX_WOOD
        )
        
        # Right rafter (inside attic, from ridge down to eaves with safe margin)
        p_right_start = Vector((cx + 0.06, ty, local_ridge_z - 0.40))
        p_right_end = Vector((cx + half_w - 0.45, ty, z_base + 0.08))
        right_mid = (p_right_start + p_right_end) * 0.5
        right_len = (p_right_end - p_right_start).length
        local_pitch_r = math.atan2(p_right_end.z - p_right_start.z, p_right_end.x - p_right_start.x)
        
        create_box(
            bm,
            size=(right_len, beam_w, beam_d),
            location=right_mid,
            rotation=(0.0, -local_pitch_r, 0.0),
            mat_index=MAT_INDEX_WOOD
        )
        
        # Collar tie beam (horizontal cross beam midway up)
        collar_z = z_base + h_roof * 0.40
        collar_w = half_w * 0.85
        create_box(
            bm,
            size=(collar_w, beam_w, beam_d),
            location=(cx, ty, collar_z),
            mat_index=MAT_INDEX_WOOD
        )


# ---------------------------------------------------------------------------
# Discrete Room Planning & Interior Partition Walls
# ---------------------------------------------------------------------------

@dataclass
class Room:
    """Represents a discrete functional room on a floor."""
    id: str
    floor_idx: int
    role: str
    bounds: Tuple[float, float, float, float]  # (ix_min, ix_max, iy_min, iy_max)
    is_wing: bool = False
    wing_id: int = 0
    doorways: List[Dict[str, Any]] = field(default_factory=list)
    stair_hole: Optional[Tuple[float, float, float, float]] = None
    exterior_facades: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    floor_void: Optional[Tuple[float, float, float, float]] = None
    # Functional layouts such as throne and banquet halls are intentionally large.
    allow_large: bool = False


def build_interior_wall(bm, p1, p2, z_floor, z_ceil, thickness=0.16,
                        doorway=None, mat_index=MAT_INDEX_WOOD,
                        casing_mat=MAT_INDEX_TIMBER, plank_direction='VERTICAL'):
    """
    Builds a double-sided stylized interior partition wall running from p1=(x1,y1) to p2=(x2,y2).
    Includes an open cased walkthrough doorway (with timber jambs and lintel, but NO door blade).
    Also generates interior baseboard and crown moulding trims on both sides of the wall.
    doorway: optional dict with keys 'cx', 'cy', 'w', 'h' or tuple (u_cx, door_w, door_h).
    plank_direction: 'VERTICAL' for floor-to-ceiling boards, 'HORIZONTAL' for left-to-right boards.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.20:
        return

    ux = dx / length
    uy = dy / length
    nx, ny = -uy, ux
    ang = math.atan2(dy, dx)
    H = z_ceil - z_floor

    trim_h_floor = 0.11
    trim_d = 0.028
    trim_h_ceil = 0.09
    trim_ceil_d = 0.026
    # Every piece of interior joinery is timber, whatever the wall finish is.
    trim_mat = MAT_INDEX_TIMBER

    _uvl = bm.loops.layers.uv.verify()

    def _plank_panel(size, location, rotation, u_off=0.0, v_off=0.0):
        """Wall panel whose plank grain direction matches surrounding interior walls.

        Using create_box with is_wall=True generates local wall UVs where U is along
        the wall length and V is up the wall height. Combined with M_Building_Wood's
        90-degree shader rotation, this produces vertical planks on the walls that
        align seamlessly across openings and corners.
        """
        fs = create_box(
            bm, size=size, location=location, rotation=rotation,
            mat_index=mat_index, is_wall=True,
            u_offset=u_off, v_offset=v_off
        )
        if plank_direction == 'HORIZONTAL':
            for f in fs:
                for lp in f.loops:
                    uv = lp[_uvl].uv
                    lp[_uvl].uv = Vector((uv.y, uv.x))
        return fs

    # Resolve doorway
    has_door = False
    u_door_cx = 0.0
    door_w = 1.75
    door_h = min(2.95, H - 0.25)

    if doorway is not None:
        if isinstance(doorway, dict):
            dw_x = doorway.get('x', (x1 + x2) * 0.5)
            dw_y = doorway.get('y', (y1 + y2) * 0.5)
            u_door_cx = (dw_x - x1) * ux + (dw_y - y1) * uy
            door_w = doorway.get('w', 1.75)
            door_h = min(doorway.get('h', 2.95), H - 0.25)
        elif isinstance(doorway, (tuple, list)) and len(doorway) >= 3:
            u_door_cx, door_w, door_h = doorway[0], doorway[1], min(doorway[2], H - 0.25)
        has_door = True

    jamb_w = 0.09
    jamb_margin = jamb_w + 0.09
    if has_door:
        if length < door_w + jamb_margin * 2.0:
            if length > 1.4:
                door_w = length - jamb_margin * 2.0
                u_door_cx = length * 0.5
            else:
                has_door = False
        else:
            u_door_cx = max(jamb_margin + door_w * 0.5, min(length - jamb_margin - door_w * 0.5, u_door_cx))

    if not has_door:
        cx = (x1 + x2) * 0.5
        cy = (y1 + y2) * 0.5
        cz = z_floor + H * 0.5
        _plank_panel(
            size=(length, thickness, H),
            location=(cx, cy, cz),
            rotation=(0.0, 0.0, ang),
            u_off=0.0,
            v_off=0.0,
        )
        for sgn in (-1.0, 1.0):
            off = sgn * (thickness * 0.5 + trim_d * 0.5)
            create_beveled_box(
                bm, size=(length, trim_d, trim_h_floor),
                location=(cx + nx * off, cy + ny * off, z_floor + trim_h_floor * 0.5),
                rotation=(0.0, 0.0, ang), mat_index=trim_mat, bevel_amount=0.008
            )
            off_c = sgn * (thickness * 0.5 + trim_ceil_d * 0.5)
            create_beveled_box(
                bm, size=(length, trim_ceil_d, trim_h_ceil),
                location=(cx + nx * off_c, cy + ny * off_c, z_ceil - trim_h_ceil * 0.5 - 0.008),
                rotation=(0.0, 0.0, ang), mat_index=trim_mat, bevel_amount=0.008
            )
        return

    # Wall with open doorway
    u_start = u_door_cx - door_w * 0.5
    u_end = u_door_cx + door_w * 0.5

    # Recess rough plaster opening slightly so the timber casing cleanly laps and caps it,
    # preventing any coplanar z-fighting or wonkiness tearing.
    jamb_w = 0.10
    overlap = 0.035
    rough_start = u_start - overlap
    rough_end = u_end + overlap
    casing_d = thickness + 0.065  # Proud of plaster by ~3.2cm on both sides

    def _crown(u0, u1):
        """Crown moulding strip on both faces, spanning u0..u1 along the wall."""
        seg = u1 - u0
        if seg < 0.05:
            return
        sc = (u0 + u1) * 0.5
        for sgn in (-1.0, 1.0):
            off_c = sgn * (thickness * 0.5 + trim_ceil_d * 0.5)
            create_beveled_box(
                bm, size=(seg, trim_ceil_d, trim_h_ceil),
                location=(x1 + ux * sc + nx * off_c, y1 + uy * sc + ny * off_c,
                          z_ceil - trim_h_ceil * 0.5 - 0.008),
                rotation=(0.0, 0.0, ang), mat_index=trim_mat, bevel_amount=0.008
            )

    # 1. Left segment
    len1 = rough_start
    if len1 > 0.02:
        c1 = len1 * 0.5
        _plank_panel(
            size=(len1, thickness, H),
            location=(x1 + ux * c1, y1 + uy * c1, z_floor + H * 0.5),
            rotation=(0.0, 0.0, ang),
            u_off=0.0,
            v_off=0.0,
        )
        for sgn in (-1.0, 1.0):
            off = sgn * (thickness * 0.5 + trim_d * 0.5)
            t_len = max(0.04, len1 - 0.04)
            t_c = t_len * 0.5
            create_beveled_box(
                bm, size=(t_len, trim_d, trim_h_floor),
                location=(x1 + ux * t_c + nx * off, y1 + uy * t_c + ny * off, z_floor + trim_h_floor * 0.5),
                rotation=(0.0, 0.0, ang), mat_index=trim_mat, bevel_amount=0.008
            )
    # 2. Header segment above doorway (raised slightly so lintel caps it from below)
    top_pad = 0.03
    top_h = H - (door_h + top_pad)
    if top_h > 0.02:
        c2 = (rough_start + rough_end) * 0.5
        header_len = rough_end - rough_start
        _plank_panel(
            size=(header_len, thickness, top_h),
            location=(x1 + ux * c2, y1 + uy * c2, z_floor + door_h + top_pad + top_h * 0.5),
            rotation=(0.0, 0.0, ang),
            u_off=rough_start,
            v_off=door_h + top_pad,
        )

    # 3. Right segment
    len3 = length - rough_end
    if len3 > 0.02:
        c3 = rough_end + len3 * 0.5
        _plank_panel(
            size=(len3, thickness, H),
            location=(x1 + ux * c3, y1 + uy * c3, z_floor + H * 0.5),
            rotation=(0.0, 0.0, ang),
            u_off=rough_end,
            v_off=0.0,
        )
        for sgn in (-1.0, 1.0):
            off = sgn * (thickness * 0.5 + trim_d * 0.5)
            t_len = max(0.04, len3 - 0.04)
            t_c = rough_end + 0.04 + t_len * 0.5
            create_beveled_box(
                bm, size=(t_len, trim_d, trim_h_floor),
                location=(x1 + ux * t_c + nx * off, y1 + uy * t_c + ny * off, z_floor + trim_h_floor * 0.5),
                rotation=(0.0, 0.0, ang), mat_index=trim_mat, bevel_amount=0.008
            )
    # 4. Continuous crown moulding at ceiling.  A doorway leaves a header wall
    # right below the ceiling, so the crown can run the full length of the wall
    # without ever crossing the opening.
    _crown(0.0, length)

    # 5. Cased Doorway Frame (walkthrough opening without door blade)
    # Jambs centered over the rough plaster boundary so they swallow the rough edge and form smooth reveals
    jamb_x = x1 + ux * (u_start - jamb_w * 0.5 + overlap * 0.4)
    jamb_y = y1 + uy * (u_start - jamb_w * 0.5 + overlap * 0.4)
    create_beveled_box(
        bm, size=(jamb_w, casing_d, door_h),
        location=(jamb_x, jamb_y, z_floor + door_h * 0.5),
        rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.010
    )
    jamb_rx = x1 + ux * (u_end + jamb_w * 0.5 - overlap * 0.4)
    jamb_ry = y1 + uy * (u_end + jamb_w * 0.5 - overlap * 0.4)
    create_beveled_box(
        bm, size=(jamb_w, casing_d, door_h),
        location=(jamb_rx, jamb_ry, z_floor + door_h * 0.5),
        rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.010
    )
    head_w = door_w + jamb_w * 2.0 + 0.06
    head_h = 0.15
    head_d = casing_d + 0.02
    head_x = x1 + ux * u_door_cx
    head_y = y1 + uy * u_door_cx
    create_beveled_box(
        bm, size=(head_w, head_d, head_h),
        location=(head_x, head_y, z_floor + door_h + head_h * 0.5),
        rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.012
    )

    # Beveled timber threshold board spanning the floor opening
    _th_h = 0.028
    create_beveled_box(
        bm, size=(door_w + jamb_w * 2.0 + 0.04, casing_d + 0.02, _th_h),
        location=(head_x, head_y, z_floor + 0.05 + _th_h * 0.5),
        rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.006
    )


# ---------------------------------------------------------------------------
# Interior programs: declarative room mixes per building type.
# AUTO follows the archetype logic below; choosing a program (from the UI)
# overrides it. Utility roles never get rugs in an industrial fit-out.
# ---------------------------------------------------------------------------
_INTERIOR_PROGRAMS = {
    'RESIDENTIAL': {
        'ground': ('HOUSE_HALL', 'KITCHEN', 'PANTRY', 'LIBRARY'),
        'upper': ('STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'STUDY', 'GUEST_ROOM'),
    },
    'HOSPITALITY': {
        'ground': ('TAVERN_TAPROOM', 'KITCHEN', 'PANTRY', 'CELLAR'),
        'upper': ('STAIR_LANDING', 'GUEST_ROOM', 'GUEST_ROOM', 'MASTER_BED', 'STUDY'),
    },
    'CIVIC': {
        'ground': ('GREAT_HALL', 'COUNCIL_CHAMBER', 'ARCHIVE', 'STUDY'),
        'upper': ('STAIR_LANDING', 'MAYOR_OFFICE', 'OFFICE', 'STUDY', 'ARCHIVE'),
    },
    'MILITARY': {
        'ground': ('KITCHEN', 'MESS_HALL', 'DRILL_HALL', 'ARMORY', 'STORAGE'),
        'upper': ('STAIR_LANDING', 'BARRACKS_DORM', 'BARRACKS_DORM', 'OFFICER_QUARTERS'),
    },
    'PALACE': {
        'ground': ('THRONE_ROOM', 'BANQUET_HALL', 'COUNCIL_CHAMBER', 'GUARD_ROOM'),
        'upper': ('STAIR_LANDING', 'MASTER_BED', 'TREASURY', 'STUDY', 'GUEST_ROOM'),
    },
    'SACRED': {
        'ground': ('CHAPEL_HALL', 'INFIRMARY', 'APOTHECARY', 'STUDY'),
        'upper': ('STAIR_LANDING', 'HEALER_QUARTERS', 'STUDY', 'BEDROOM'),
    },
    'COMMERCIAL': {
        'ground': ('STORE', 'WORKSHOP', 'STORAGE', 'PANTRY'),
        'upper': ('STAIR_LANDING', 'MASTER_BED', 'KITCHEN', 'HOUSE_HALL', 'BEDROOM'),
    },
    'INDUSTRIAL': {
        'ground': ('WORKSHOP', 'STORAGE', 'STORE', 'OFFICE'),
        'upper': ('STAIR_LANDING', 'STORAGE', 'WORKSHOP', 'OFFICE'),
        'no_utility_rugs': True,
    },
    'RANGER': {
        'ground': ('FLETCHER_WORKSHOP', 'RANGE', 'STORAGE', 'LODGE'),
        'upper': ('STAIR_LANDING', 'BARRACKS_DORM', 'LODGE', 'BEDROOM'),
    },
    'STABLE': {
        'ground': ('STABLE_HALL',),
        'upper': ('STABLE_HALL',),
    },
    'ARMORY': {
        'ground': ('ARMORY', 'STORAGE', 'ENTRANCE_HALL'),
        'upper': ('ARMORY', 'STORAGE', 'ENTRANCE_HALL'),
    },
    'GARRISON': {
        # Outlying garrison houses: a real kitchen, a dining hall, a store room
        # and a drill space downstairs, real bedrooms (dorms) upstairs.
        'ground': ('MESS_HALL', 'KITCHEN', 'STORAGE', 'ARMORY'),
        'upper': ('STAIR_LANDING', 'BARRACKS_DORM', 'BARRACKS_DORM', 'OFFICER_QUARTERS'),
    },
    'ROYAL_ARCHIVE': {
        # The royal archive wing: one great banquet hall on the ground floor,
        # proper chambers (library, study, royal apartments) on the floors
        # above.
        'ground': ('BANQUET_HALL',),
        'upper': ('STAIR_LANDING', 'LIBRARY', 'STUDY', 'MASTER_BED', 'GUEST_ROOM'),
    },
}

_ARCHETYPE_PROGRAM = {
    'HOUSE': 'RESIDENTIAL', 'MANOR': 'RESIDENTIAL', 'TENEMENT': 'RESIDENTIAL',
    'TAVERN': 'HOSPITALITY', 'INN': 'HOSPITALITY',
    'TOWN_HALL': 'CIVIC', 'CIVIC': 'CIVIC', 'GUILDHALL': 'CIVIC',
    'BARRACKS': 'MILITARY', 'INFANTRY_BARRACKS': 'MILITARY', 'KNIGHTS_MANOR': 'MILITARY',
    'ARMORY': 'ARMORY',
    'PALACE': 'PALACE', 'CASTLE': 'PALACE', 'NASHERS_MANOR': 'PALACE',
    'STABLE': 'STABLE',
    'ARCHERY': 'RANGER', 'ARCHERY_RANGE': 'RANGER',
    'CHAPEL': 'SACRED', 'HEALERS_CHAPEL': 'SACRED',
    'WAREHOUSE': 'INDUSTRIAL', 'LUMBERMILL': 'INDUSTRIAL', 'BUILDER': 'INDUSTRIAL',
    'BLACKSMITH': 'COMMERCIAL',
    'QUARRY': 'INDUSTRIAL',
    'BAKERY': 'COMMERCIAL', 'FISHERMAN': 'COMMERCIAL', 'BREWERY': 'COMMERCIAL',
    'BUTCHER': 'COMMERCIAL', 'TAILOR': 'COMMERCIAL', 'TOOLSMITH': 'COMMERCIAL',
    'JEWELER': 'COMMERCIAL', 'FURNITURE_MAKER': 'COMMERCIAL', 'HUNTER': 'COMMERCIAL',
}


def resolve_interior_program(archetype, program_override='AUTO'):
    """Resolve the active interior program: explicit UI choice, else archetype."""
    if program_override and program_override != 'AUTO':
        return program_override
    return _ARCHETYPE_PROGRAM.get(archetype, 'RESIDENTIAL')


def _program_roles(program, fl_idx, num_rooms, has_stairs_landing):
    """Role pool for a chosen interior program, or None when unknown."""
    prog = _INTERIOR_PROGRAMS.get(program)
    if not prog:
        return None
    if has_stairs_landing and prog.get('upper'):
        pool = list(prog['upper'])
    else:
        pool = list(prog['ground'])
    while len(pool) < num_rooms:
        pool.append(pool[-1] if pool else 'STORAGE')
    return pool[:num_rooms]


# Dedicated craft workshops per artisan trade: the street-facing shop plus
# the trade's own production rooms (never generic offices or studies).
_ARTISAN_GROUND = {
    'BAKERY': ['BAKEHOUSE', 'STORE', 'STORAGE'],
    'BREWERY': ['BREWHOUSE', 'STORE', 'STORAGE'],
    'BUTCHER': ['BUTCHERY', 'STORE', 'STORAGE'],
    'TAILOR': ['TAILOR_ATELIER', 'STORE', 'STORAGE'],
    'JEWELER': ['GOLDSMITH', 'STORE', 'STORAGE'],
    'BLACKSMITH': ['SMITHY', 'STORE', 'STORAGE'],
    'TOOLSMITH': ['SMITHY', 'STORE', 'STORAGE'],
    'FURNITURE_MAKER': ['JOINERY', 'STORE', 'STORAGE'],
    'FISHERMAN': ['FISHERY', 'STORE', 'STORAGE'],
    'HUNTER': ['FLETCHER_WORKSHOP', 'STORE', 'STORAGE'],
}

# Rooms that must simply be walked through. The smart planner carves these
# out as ribbons along whatever wall has room, so the rooms they serve keep
# compact, squarish proportions instead of becoming long strips themselves.
THROUGH_ROLES = ('CORRIDOR', 'STAIR_LANDING', 'ENTRANCE_HALL')
PRIVATE_ROOM_ROLES = {
    'BEDROOM', 'MASTER_BED', 'GUEST_ROOM', 'TENEMENT_BEDROOM',
    'OFFICER_QUARTERS', 'ROYAL_CHAMBER', 'HEALER_QUARTERS',
}

# Archetypes whose upper storeys are a hall/corridor serving many rooms.  They
# use the hallway planner so bedrooms/offices open off circulation instead of
# being walked through, and rooms stay functionally sized.
_HALL_ARCHETYPES = {
    'HOUSE', 'NONE', 'AUTO', 'CIVIC', 'TOWN_HALL', 'GUILDHALL',
    'BARRACKS', 'INFANTRY_BARRACKS', 'KNIGHTS_MANOR', 'ARMORY',
    'CHAPEL', 'HEALERS_CHAPEL', 'ARCHERY', 'ARCHERY_RANGE',
    'BLACKSMITH', 'BAKERY', 'BREWERY', 'BUTCHER', 'TAILOR', 'TOOLSMITH',
    'JEWELER', 'FURNITURE_MAKER', 'HUNTER', 'FISHERMAN', 'INN', 'TAVERN',
}


def stair_circulation_zone(stair_hole, stair_pos_info=None, bounds=None,
                           landing_depth=1.25, side_clearance=0.30):
    """Return the usable stair flight plus its step-on/off landing envelope."""
    if stair_hole is None:
        return None
    x0, x1, y0, y1 = map(float, stair_hole)
    if stair_pos_info:
        cx = float(stair_pos_info.get('cx', (x0 + x1) * 0.5))
        width = max(0.80, float(stair_pos_info.get('w', x1 - x0) or (x1 - x0)))
        x0 = min(x0, cx - width * 0.5)
        x1 = max(x1, cx + width * 0.5)
        y_bot = stair_pos_info.get('y_bot')
        y_top = stair_pos_info.get('y_top')
        if y_bot is not None and y_top is not None:
            y0 = min(y0, float(y_bot), float(y_top))
            y1 = max(y1, float(y_bot), float(y_top))
    x0 -= side_clearance
    x1 += side_clearance
    y0 -= landing_depth
    y1 += landing_depth
    if bounds is not None:
        bx0, bx1, by0, by1 = bounds
        x0, x1 = max(bx0, x0), min(bx1, x1)
        y0, y1 = max(by0, y0), min(by1, y1)
    return (x0, x1, y0, y1)


def _rect_overlap_area(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[2], b[2]))


def _normalize_stair_circulation_rooms(rooms, stair_hole, stair_pos_info, bounds):
    """Keep multi-room stair landings and through-routes out of private rooms.

    A large public room (taproom, great hall, workshop, ...) may legitimately
    contain the staircase - the furnishing pass still keeps the flight and its
    landings clear - so those rooms are never renamed into landings.
    """
    if not rooms or stair_hole is None or len(rooms) <= 1:
        return rooms
    circulation = stair_circulation_zone(stair_hole, stair_pos_info, bounds)
    if circulation is None:
        return rooms
    _STAIR_TOLERANT = {
        'TAVERN_TAPROOM', 'GREAT_HALL', 'BANQUET_HALL', 'HOUSE_HALL',
        'COUNCIL_CHAMBER', 'MESS_HALL', 'THRONE_ROOM', 'CHAPEL_HALL',
        'WORKSHOP', 'STONE_STORE', 'STABLE_HALL', 'LODGE', 'RANGE',
        'DINING', 'COMMON_ROOM', 'ENTRANCE_HALL',
        'BAKEHOUSE', 'JOINERY', 'TAILOR_ATELIER', 'BREWHOUSE', 'BUTCHERY',
        'GOLDSMITH', 'FISHERY', 'SMITHY', 'FLETCHER_WORKSHOP', 'STORE',
    }
    holders = [room for room in rooms if _rect_overlap_area(room.bounds, circulation) > 0.08]
    hole_holders = [room for room in rooms if _rect_overlap_area(room.bounds, stair_hole) > 0.08]
    for room in holders:
        # Public/common rooms keep their role; the stair is just part of the room.
        if room.role in _STAIR_TOLERANT:
            if room in hole_holders:
                room.stair_hole = stair_hole
            continue
        # A chamber touched by the flight, landing, or required egress apron is
        # part of the route. Never leave a private furnished room across that
        # route merely because the slab opening itself is in its neighbour.
        room.role = 'STAIR_LANDING' if room in hole_holders else 'CORRIDOR'
        room.stair_hole = stair_hole if room in hole_holders else None
    for room in rooms:
        if room.role not in PRIVATE_ROOM_ROLES:
            continue
        internal_doors = [door for door in (room.doorways or [])
                          if bounds[0] + 0.10 < door.get('x', 0.0) < bounds[1] - 0.10
                          and bounds[2] + 0.10 < door.get('y', 0.0) < bounds[3] - 0.10]
        if len(internal_doors) >= 2:
            room.role = 'CORRIDOR'
    return rooms


def _looks_like_corridor(b, min_side=2.2, max_aspect=2.25):
    """True when a room rectangle is a long thin strip rather than a room."""
    x0, x1, y0, y1 = b
    w, d = x1 - x0, y1 - y0
    if w <= 0.01 or d <= 0.01:
        return True
    return min(w, d) < min_side or max(w, d) / min(w, d) > max_aspect


def _resolve_room_roles(archetype, fl_idx, num_rooms, has_stairs_landing=False, total_floors=1,
                        program=None):

    """Assigns functional roles to rooms on a floor based on building archetype and stair presence."""
    if program and program != 'AUTO':
        _p = _program_roles(program, fl_idx, num_rooms, has_stairs_landing)
        if _p is not None:
            return _p
    if archetype == 'MANOR':
        # Grand residence: banquet hall, living salon, suites, and guest rooms.
        if has_stairs_landing:
            if num_rooms == 1:
                return ['MASTER_BED']
            pool = ['STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'GUEST_ROOM',
                    'LIBRARY', 'BEDROOM']
            return pool[:num_rooms]
        if total_floors == 1:
            if num_rooms == 1:
                return ['COTTAGE']
            elif num_rooms == 2:
                return ['BANQUET_HALL', 'MASTER_BED']
            pool = ['BANQUET_HALL', 'HOUSE_HALL', 'KITCHEN', 'MASTER_BED', 'BEDROOM']
            return pool[:num_rooms]
        pool = ['BANQUET_HALL', 'HOUSE_HALL', 'KITCHEN', 'PANTRY', 'DINING']
        return pool[:num_rooms]
    if has_stairs_landing:
        # On upper floors with stairs, Room 0 (around stair hole) is the protected landing/corridor.
        # Bedrooms and private suites are strictly placed in the separate partitioned chambers.
        if archetype in ('TAVERN', 'INN'):
            # Upper storeys of an inn are lodgings: a cheap shared common room
            # with bunk beds plus progressively nicer private rooms. The first
            # room is always the stair landing so guests never arrive directly
            # into a sleeping chamber or furnished common room.
            if num_rooms == 1:
                return ['GUEST_ROOM']
            if num_rooms == 2:
                return ['STAIR_LANDING', 'GUEST_ROOM']
            pool = ['STAIR_LANDING', 'COMMON_ROOM', 'GUEST_ROOM', 'MASTER_BED',
                    'GUEST_ROOM', 'GUEST_ROOM', 'STUDY', 'GUEST_ROOM']
            return pool[:num_rooms]
        elif archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY', 'BUILDER'):
            # Industrial upper floors are work/storage, never bedrooms or kitchens.
            pool = ['STAIR_LANDING', 'STONE_STORE' if archetype == 'QUARRY' else 'STORAGE', 'WORKSHOP', 'OFFICE']
            return pool[:num_rooms]
        elif archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                          'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER', 'HUNTER') or archetype.startswith('ARTISAN'):
            # Artisan live/work house: trade below, family home above. Upper
            # storeys are strictly residential (no offices, no studies).
            # Highest priority: 1 bedroom then 1 kitchen.
            if fl_idx == 1:
                if num_rooms == 1:
                    return ['COTTAGE']
                pool = ['STAIR_LANDING', 'MASTER_BED', 'KITCHEN', 'HOUSE_HALL', 'BEDROOM']
            else:
                if num_rooms == 1:
                    return ['COTTAGE']
                pool = ['STAIR_LANDING', 'BEDROOM', 'GUEST_ROOM', 'STORAGE', 'BEDROOM']
            return pool[:num_rooms]
        elif archetype == 'ARMORY':
            pool = ['STAIR_LANDING', 'ARMORY', 'STORAGE', 'DRILL_HALL']
            return pool[:num_rooms]
        elif archetype in ('BARRACKS', 'INFANTRY_BARRACKS'):
            pool = ['STAIR_LANDING', 'ARMORY', 'STORAGE', 'OFFICER_QUARTERS']
            return pool[:num_rooms]
        elif archetype in ('KNIGHTS_MANOR',):
            pool = ['STAIR_LANDING', 'BARRACKS_DORM', 'OFFICER_QUARTERS', 'ARMORY', 'BARRACKS_DORM']
            return pool[:num_rooms]
        elif archetype in ('ARCHERY', 'ARCHERY_RANGE'):
            pool = ['STAIR_LANDING', 'BARRACKS_DORM', 'LODGE', 'BEDROOM']
            return pool[:num_rooms]
        elif archetype in ('CHAPEL', 'HEALERS_CHAPEL'):
            pool = ['STAIR_LANDING', 'HEALER_QUARTERS', 'INFIRMARY',
                    'APOTHECARY', 'STUDY', 'VESTRY']
            return pool[:num_rooms]
        elif archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
            pool = ['STAIR_LANDING', 'MAYOR_OFFICE', 'OFFICE', 'STUDY', 'ARCHIVE']
            return pool[:num_rooms]
        elif archetype in ('TENEMENT',):
            if num_rooms == 1:
                return ['TENEMENT_BEDROOM']
            pool = ['STAIR_LANDING', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM']
            return pool[:num_rooms]
        elif archetype in ('STABLE',):
            pool = ['STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL']
            return pool[:num_rooms]
        else:  # HOUSE, default
            # A 1-room upper floor in a house is a combined living/sleeping cottage
            if num_rooms == 1:
                return ['COTTAGE']
            pool = ['STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'GUEST_ROOM', 'BEDROOM']
            return pool[:num_rooms]

    # Ground floor (or single floor without stair landing)
    if archetype in ('TAVERN', 'INN'):
        # The taproom only exists downstairs. Upper storeys are guest rooms,
        # never a second taproom / kitchen / cellar.
        if fl_idx > 0:
            if num_rooms == 1:
                return ['GUEST_ROOM']
            if num_rooms == 2:
                return ['COMMON_ROOM', 'MASTER_BED']
            return ['COMMON_ROOM', 'GUEST_ROOM', 'MASTER_BED', 'GUEST_ROOM',
                    'GUEST_ROOM', 'STUDY'][:num_rooms]
        if num_rooms == 1:
            return ['TAVERN_TAPROOM']
        pool = ['TAVERN_TAPROOM', 'KITCHEN', 'PANTRY', 'CELLAR']
        return pool[:num_rooms]

    if archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
        pool = ['GREAT_HALL', 'COUNCIL_CHAMBER', 'ARCHIVE', 'STUDY']
        return pool[:num_rooms]

    if archetype in ('TAVERN', 'INN'):
        pool = ['TAVERN_TAPROOM', 'KITCHEN', 'CELLAR', 'PANTRY']
        return pool[:num_rooms]

    if archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY', 'BUILDER'):
        if archetype == 'QUARRY':
            pool = ['STONE_STORE', 'STORAGE', 'WORKSHOP', 'OFFICE']
        else:
            pool = ['STORE', 'WORKSHOP', 'STORAGE', 'PANTRY']
        return pool[:num_rooms]

    if archetype in _ARTISAN_GROUND or archetype.startswith('ARTISAN'):
        if total_floors == 1:
            if num_rooms == 1:
                return ['COTTAGE']
            elif num_rooms == 2:
                shop_role = _ARTISAN_GROUND.get(archetype, ['STORE'])[0]
                return [shop_role, 'COTTAGE']
            elif num_rooms == 3:
                shop_role = _ARTISAN_GROUND.get(archetype, ['STORE'])[0]
                return [shop_role, 'MASTER_BED', 'KITCHEN']
            else:
                ground_roles = _ARTISAN_GROUND.get(archetype, ['STORE', 'WORKSHOP'])
                return [ground_roles[0], ground_roles[1] if len(ground_roles) > 1 else 'WORKSHOP', 'MASTER_BED', 'KITCHEN'] + ground_roles[2:]
        pool = _ARTISAN_GROUND.get(archetype, ['STORE', 'WORKSHOP', 'STORAGE', 'PANTRY'])
        return pool[:num_rooms]

    if archetype == 'ARMORY':
        if num_rooms == 1:
            return ['ARMORY']
        if num_rooms == 2:
            return ['ARMORY', 'STORAGE']
        pool = ['ENTRANCE_HALL', 'ARMORY', 'STORAGE', 'DRILL_HALL']
        return pool[:num_rooms]

    if archetype in ('BARRACKS', 'INFANTRY_BARRACKS'):
        # A garrison needs a working kitchen and a dining/mess hall first;
        # kitchen and mess hall first; pantry/stores support them.  Armoury
        # and drill spaces live upstairs so the ground floor never becomes a
        # row of huge empty military prop rooms.
        pool = ['KITCHEN', 'MESS_HALL', 'PANTRY', 'STORAGE', 'DRILL_HALL']
        return pool[:num_rooms]

    if archetype in ('KNIGHTS_MANOR',):
        pool = ['KITCHEN', 'MESS_HALL', 'GREAT_HALL', 'ARMORY', 'STORAGE']
        return pool[:num_rooms]

    if archetype in ('ARCHERY', 'ARCHERY_RANGE'):
        pool = ['FLETCHER_WORKSHOP', 'RANGE', 'STORAGE', 'LODGE']
        return pool[:num_rooms]

    if archetype in ('CHAPEL', 'HEALERS_CHAPEL'):
        if int(total_floors) <= 1:
            # Single-storey chapel: the healing beds have to share the ground.
            pool = ['CHAPEL_HALL', 'INFIRMARY', 'APOTHECARY', 'STUDY']
        else:
            # Multi-storey: the ground is the grand chapel; all beds and
            # healer lodgings live on the upper floors.
            pool = ['CHAPEL_HALL', 'VESTRY', 'STUDY', 'STORAGE']
        return pool[:num_rooms]

    if archetype in ('TENEMENT',):
        pool = ['TENEMENT_KITCHEN', 'TENEMENT_BEDROOM', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM']
        return pool[:num_rooms]

    if archetype in ('STABLE',):
        pool = ['STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL']
        return pool[:num_rooms]

    # Default HOUSE. Living hall, kitchen, dining and bedrooms.
    # Hard requirement: small houses MUST have a bed or bedroom.
    if total_floors == 1:
        if num_rooms == 1:
            return ['COTTAGE']
        elif num_rooms == 2:
            return ['KITCHEN', 'MASTER_BED']
        elif num_rooms == 3:
            return ['HOUSE_HALL', 'KITCHEN', 'MASTER_BED']
        else:
            return ['HOUSE_HALL', 'KITCHEN', 'MASTER_BED', 'BEDROOM'][:num_rooms]
    else:
        pool = ['HOUSE_HALL', 'KITCHEN', 'PANTRY', 'DINING']
        return pool[:num_rooms]


def _wing_portals(wb, doorways):
    """Doorways connecting a wing to the main block (exclusive entrance).

    Matches floor doorways sitting on the wing's junction edges; street doors
    elsewhere never match because they fall outside the wing spans.
    """
    wx1, wx2, wy1, wy2 = wb
    out = []
    for dw in (doorways or []):
        if dw.get('axis', 'X') == 'X':
            if wx1 - 0.4 <= dw.get('x', 0.0) <= wx2 + 0.4 and \
               (abs(dw.get('y', 0.0) - wy1) < 0.7 or abs(dw.get('y', 0.0) - wy2) < 0.7):
                out.append(dw)
        else:
            if wy1 - 0.4 <= dw.get('y', 0.0) <= wy2 + 0.4 and \
               (abs(dw.get('x', 0.0) - wx1) < 0.7 or abs(dw.get('x', 0.0) - wx2) < 0.7):
                out.append(dw)
    return out


def _plan_throne_palace_rooms(fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
                              has_stairs_landing, stair_pos_info=None,
                              extra_doorways=None, props=None):
    """Grand Castle / Palace floor plan with central Throne Room & Mezzanine Gallery.

    Structure:
    - West Bay: Dedicated Stair & Circulation Hall (holds stairs, connector wing portal, chapel portal).
    - Center Bay: Grand Throne Room (Floor 0) / Mezzanine Gallery (Floor 1).
      Centered exactly on X = 0.0, directly aligned with the front entrance and terrace stairs.
      Zero interior partition walls inside this bay - never cuts the void or walkways!
    - East Bay: Royal Chambers / Council Chamber / Banquet Hall (and Archive portal).
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 13.0 or D < 5.5:
        return None

    stair_on_right = bool(
        (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
        or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
    )

    if stair_pos_info:
        _sw = float(stair_pos_info.get('w', 1.5))
        _scx = float(stair_pos_info.get('cx', ix_min + 2.0))
        if stair_on_right:
            req_side_w = max(4.0, (ix_max - _scx) + _sw * 0.5 + 2.2)
        else:
            req_side_w = max(4.0, (_scx - ix_min) + _sw * 0.5 + 2.2)
    elif stair_hole:
        if stair_on_right:
            req_side_w = max(4.0, ix_max - stair_hole[0] + 2.2)
        else:
            req_side_w = max(4.0, stair_hole[1] - ix_min + 2.2)
    else:
        req_side_w = 4.5

    # If there is a basement stair hole or floor stair opening, ensure side bay has clearance to partition wall
    if stair_hole and stair_hole[2] <= iy_max and stair_hole[3] >= iy_min:
        if stair_hole[0] > (ix_min + ix_max) * 0.5:
            # Stair on east side (e.g. basement stair in East Bay)
            req_side_w = max(req_side_w, (ix_max - stair_hole[0]) + 0.3)
        else:
            # Stair on west side (main stairs in West Bay)
            req_side_w = max(req_side_w, (stair_hole[1] - ix_min) + 2.2)

    # For wide palace/keep (W >= 18.0), the center bay is [-6.0, 6.0].
    # Doorways inside the central bay (|ex| <= 6.5) enter the Throne Room / Mezzanine Gallery,
    # and MUST NOT push req_side_w! Only doorways outside [-6.5, 6.5] belong to side bays.
    for ed in (extra_doorways or []):
        if ed.get('floor_idx', fl_idx) == fl_idx:
            d_axis = ed.get('axis', 'X' if ed.get('facade') in ('FRONT', 'BACK') else 'Y')
            if d_axis == 'X':
                ex = ed.get('x', ed.get('pos', 0.0))
                ew = ed.get('w', 1.2)
                if ex < -6.5:
                    req_side_w = max(req_side_w, (ex + ew * 0.5 + 1.0) - ix_min)
                elif ex > 6.5:
                    req_side_w = max(req_side_w, ix_max - (ex - ew * 0.5 - 1.0))

    max_half = (W * 0.5) - req_side_w
    half_hall_w = min(6.0, max(3.5, max_half))
    if W >= 18.0:
        half_hall_w = 6.0
    b_west = -half_hall_w
    b_east = half_hall_w

    rooms = []
    walls = []

    def _vwall(px, y0, y1, dw_y):
        walls.append({
            'p1': (px, y0), 'p2': (px, y1),
            'axis': 'Y', 'pos': px, 'thickness': wall_t,
            'doorway': {'x': px, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
        })

    def _hwall(x0, x1, y, dw_x):
        walls.append({
            'p1': (x0, y), 'p2': (x1, y),
            'axis': 'X', 'pos': y, 'thickness': wall_t,
            'doorway': {'x': dw_x, 'y': y, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
        })

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.30
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

    y_mid = (iy_min + iy_max) * 0.5
    _y_split = None

    if fl_idx == 0:
        _vwall(b_west, iy_min, iy_max, y_mid)
        _vwall(b_east, iy_min, iy_max, y_mid)

        # Optional royal kitchen. It is placed in the SOUTH half of the east bay
        # (a proper 5 x 5 m service room) and NOT in the west bay: the west
        # bay is the stair hall and a partition there would stand right in
        # front of the flight and block the way up.
        _royal_kitchen = bool(getattr(props, 'has_royal_kitchen', False))
        _y_split = None

        rm_west = Room(
            id=f"fl{fl_idx}_stair_hall", floor_idx=fl_idx, role='CORRIDOR',
            bounds=(ix_min, b_west, iy_min, _y_split if _y_split is not None else iy_max),
            doorways=[{'x': b_west, 'y': y_mid, 'axis': 'Y', 'w': dw_w}],
            stair_hole=_holds_stair((ix_min, b_west, iy_min, iy_max)),
            exterior_facades={'FRONT': (ix_min, b_west), 'BACK': (ix_min, b_west),
                              'LEFT': (iy_min, _y_split if _y_split is not None else iy_max)}
        )
        rm_center = Room(
            id=f"fl{fl_idx}_throne_room", floor_idx=fl_idx, role='THRONE_ROOM',
            bounds=(b_west, b_east, iy_min, iy_max),
            doorways=[
                {'x': b_west, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
                {'x': b_east, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'FRONT': (b_west, b_east), 'BACK': (b_west, b_east)}
        )
        # Partition the East Bay into Council Chamber (south) and Banquet/Archive Hall (north).
        # Shift the cross-wall to y_mid - 2.8 so it never intersects the Archive portal at y_mid!
        split_y_east = y_mid - 2.8
        if _royal_kitchen and (iy_max - iy_min) >= 11.0:
            # The royal kitchen takes the southern half of the east bay and the
            # council chamber moves north of it.
            split_y_east = iy_min + (iy_max - iy_min) * 0.5
        # Only build the partition wall if we are NOT using the royal kitchen,
        # otherwise the wall would block the doorway into the addition building.
        if not _royal_kitchen:
            _hwall(b_east, ix_max, split_y_east, (b_east + ix_max) * 0.5)
        rm_east_s = Room(
            id=f"fl{fl_idx}_council_chamber", floor_idx=fl_idx,
            role='KITCHEN' if _royal_kitchen else 'COUNCIL_CHAMBER',
            bounds=(b_east, ix_max, iy_min, split_y_east),
            doorways=[{'x': (b_east + ix_max) * 0.5, 'y': split_y_east, 'axis': 'X', 'w': dw_w}],
            stair_hole=None,
            exterior_facades={'FRONT': (b_east, ix_max), 'RIGHT': (iy_min, split_y_east)}
        )
        rm_east_n = Room(
            id=f"fl{fl_idx}_banquet_hall", floor_idx=fl_idx, role='LIBRARY',
            bounds=(b_east, ix_max, split_y_east, iy_max),
            doorways=[
                {'x': b_east, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
                {'x': (b_east + ix_max) * 0.5, 'y': split_y_east, 'axis': 'X', 'w': dw_w},
                {'x': ix_max, 'y': y_mid, 'axis': 'Y', 'w': 2.40}
            ],
            stair_hole=_holds_stair((b_east, ix_max, split_y_east, iy_max)),
            exterior_facades={'BACK': (b_east, ix_max), 'RIGHT': (split_y_east, iy_max)}
        )
        rooms = [rm_west, rm_center, rm_east_s, rm_east_n]

    elif fl_idx == 1 and bool(getattr(props, 'has_throne_room', False) or getattr(props, 'has_double_height', False)):
        _vwall(b_west, iy_min, iy_max, y_mid)
        _vwall(b_east, iy_min, iy_max, y_mid)

        v_rim = 2.00
        vx0 = b_west + v_rim
        vx1 = b_east - v_rim
        vy0 = iy_min + v_rim
        vy1 = iy_max - v_rim
        void_rect = (vx0, vx1, vy0, vy1)

        rm_west = Room(
            id=f"fl{fl_idx}_stair_landing", floor_idx=fl_idx, role='STAIR_LANDING',
            bounds=(ix_min, b_west, iy_min, iy_max),
            doorways=[{'x': b_west, 'y': y_mid, 'axis': 'Y', 'w': dw_w}],
            stair_hole=_holds_stair((ix_min, b_west, iy_min, iy_max)),
            exterior_facades={'FRONT': (ix_min, b_west), 'BACK': (ix_min, b_west), 'LEFT': (iy_min, iy_max)}
        )
        rm_center = Room(
            id=f"fl{fl_idx}_mezzanine_gallery", floor_idx=fl_idx, role='MEZZANINE_GALLERY',
            bounds=(b_west, b_east, iy_min, iy_max),
            doorways=[
                {'x': b_west, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
                {'x': b_east, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'FRONT': (b_west, b_east), 'BACK': (b_west, b_east)}
        )
        rm_center.floor_void = void_rect

        split_y_east = y_mid - 2.8
        _hwall(b_east, ix_max, split_y_east, (b_east + ix_max) * 0.5)
        rm_east_s = Room(
            id=f"fl{fl_idx}_study", floor_idx=fl_idx, role='STUDY',
            bounds=(b_east, ix_max, iy_min, split_y_east),
            doorways=[{'x': (b_east + ix_max) * 0.5, 'y': split_y_east, 'axis': 'X', 'w': dw_w}],
            stair_hole=None,
            exterior_facades={'FRONT': (b_east, ix_max), 'RIGHT': (iy_min, split_y_east)}
        )
        rm_east_n = Room(
            id=f"fl{fl_idx}_master_bed", floor_idx=fl_idx, role='MASTER_BED',
            bounds=(b_east, ix_max, split_y_east, iy_max),
            doorways=[
                {'x': b_east, 'y': y_mid, 'axis': 'Y', 'w': dw_w},
                {'x': (b_east + ix_max) * 0.5, 'y': split_y_east, 'axis': 'X', 'w': dw_w}
            ],
            stair_hole=None,
            exterior_facades={'BACK': (b_east, ix_max), 'RIGHT': (split_y_east, iy_max)}
        )
        rooms = [rm_west, rm_center, rm_east_s, rm_east_n]

    else:
        dw_y_s = (iy_min + y_mid) * 0.5
        dw_y_n = (y_mid + iy_max) * 0.5
        dw_x_center = (b_west + b_east) * 0.5
        dw_x_east = (b_east + ix_max) * 0.5

        # West dividing walls between stair landing and central salons
        _vwall(b_west, iy_min, y_mid, dw_y_s)
        _vwall(b_west, y_mid, iy_max, dw_y_n)

        # East dividing walls between central salons and library/treasury
        _vwall(b_east, iy_min, y_mid, dw_y_s)
        _vwall(b_east, y_mid, iy_max, dw_y_n)

        # Horizontal partition dividing central salon into south and north rooms
        _hwall(b_west, b_east, y_mid, dw_x_center)

        # Horizontal partition dividing east wing into south and north rooms
        _hwall(b_east, ix_max, y_mid, dw_x_east)

        rm_west = Room(
            id=f"fl{fl_idx}_stair_landing", floor_idx=fl_idx, role='STAIR_LANDING',
            bounds=(ix_min, b_west, iy_min, iy_max),
            doorways=[
                {'x': b_west, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                {'x': b_west, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
            ],
            stair_hole=_holds_stair((ix_min, b_west, iy_min, iy_max)),
            exterior_facades={'FRONT': (ix_min, b_west), 'BACK': (ix_min, b_west), 'LEFT': (iy_min, iy_max)}
        )
        rm_center_s = Room(
            id=f"fl{fl_idx}_royal_salon", floor_idx=fl_idx,
            role='GREAT_HALL' if fl_idx == 2 else 'HOUSE_HALL',
            bounds=(b_west, b_east, iy_min, y_mid),
            doorways=[
                {'x': b_west, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_center, 'y': y_mid, 'axis': 'X', 'w': dw_w},
                {'x': b_east, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'FRONT': (b_west, b_east)}
        )
        rm_center_n = Room(
            id=f"fl{fl_idx}_royal_bed", floor_idx=fl_idx,
            role='MASTER_BED' if fl_idx == 2 else 'BEDROOM',
            bounds=(b_west, b_east, y_mid, iy_max),
            doorways=[
                {'x': b_west, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_center, 'y': y_mid, 'axis': 'X', 'w': dw_w},
                {'x': b_east, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'BACK': (b_west, b_east)}
        )
        rm_east_s = Room(
            id=f"fl{fl_idx}_bedchamber", floor_idx=fl_idx, role='BEDROOM',
            bounds=(b_east, ix_max, iy_min, y_mid),
            doorways=[
                {'x': b_east, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_east, 'y': y_mid, 'axis': 'X', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'FRONT': (b_east, ix_max), 'RIGHT': (iy_min, y_mid)}
        )
        rm_east_n = Room(
            id=f"fl{fl_idx}_guest_room", floor_idx=fl_idx, role='GUEST_ROOM',
            bounds=(b_east, ix_max, y_mid, iy_max),
            doorways=[
                {'x': b_east, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_east, 'y': y_mid, 'axis': 'X', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'BACK': (b_east, ix_max), 'RIGHT': (y_mid, iy_max)}
        )
        rooms = [rm_west, rm_center_s, rm_center_n, rm_east_s, rm_east_n]

    # Register external portals (connector doorways, skybridge entrances) in room boundaries
    for r in rooms:
        rx0, rx1, ry0, ry1 = r.bounds
        for ed in (extra_doorways or []):
            if ed.get('floor_idx', fl_idx) == fl_idx:
                sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
                if sax == 'X':
                    ed_x = ed.get('x', ed.get('pos', 0.0))
                    ed_y = iy_max if ed.get('facade') == 'BACK' else iy_min
                    if (rx0 - 0.45 <= ed_x <= rx1 + 0.45) and (abs(ed_y - ry0) < 0.45 or abs(ed_y - ry1) < 0.45):
                        ed_entry = {'x': ed_x, 'y': ed_y, 'axis': 'X', 'w': ed.get('w', 2.4), 'is_portal': True}
                        if not any(abs(d.get('x', 0) - ed_x) < 0.2 and abs(d.get('y', 0) - ed_y) < 0.2 for d in r.doorways):
                            r.doorways.append(ed_entry)
                else:
                    ed_y = ed.get('y', ed.get('pos', 0.0))
                    ed_x = ix_max if ed.get('facade') == 'RIGHT' else ix_min
                    if (ry0 - 0.45 <= ed_y <= ry1 + 0.45) and (abs(ed_x - rx0) < 0.45 or abs(ed_x - rx1) < 0.45):
                        ed_entry = {'x': ed_x, 'y': ed_y, 'axis': 'Y', 'w': ed.get('w', 2.4), 'is_portal': True}
                        if not any(abs(d.get('x', 0) - ed_x) < 0.2 and abs(d.get('y', 0) - ed_y) < 0.2 for d in r.doorways):
                            r.doorways.append(ed_entry)

    return rooms, walls


def _plan_manor_rooms(fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
                      has_stairs_landing, stair_pos_info=None,
                      extra_doorways=None, props=None, fl_wings_bounds=None):
    """Grand Manor / Palace multi-column floor plan for wide buildings (W >= 15m).

    Supports both left-hand and right-hand stairs.
    Divides the floor into a dedicated stair hall strip plus 2 to 3 well-proportioned
    living bays with central grand salons, libraries, suites, and skybridge reception galleries.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 15.0 or D < 6.0:
        return None

    # Collect all doorway spans along X (front & back doors, wing portals, connector portals)
    # that vertical partition walls must NEVER cross or bisect.
    x_dw_spans = []
    margin = 0.55
    for ed in (extra_doorways or []):
        sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
        if sax == 'X':
            dcx = ed.get('x', ed.get('pos', 0.0))
            d_w = ed.get('w', 1.4)
            x_dw_spans.append((dcx - d_w * 0.5 - margin, dcx + d_w * 0.5 + margin))

    if fl_wings_bounds:
        for wb in fl_wings_bounds:
            w_cx = (wb[0] + wb[1]) * 0.5
            w_span = wb[1] - wb[0]
            p_w = min(max(1.2, w_span - 1.2), 2.2)
            x_dw_spans.append((w_cx - p_w * 0.5 - margin, w_cx + p_w * 0.5 + margin))

    def _clear_cw(pos, lo, hi):
        if hi < lo:
            hi = lo
        pos = min(hi, max(lo, pos))
        for _ in range(5):
            hit = False
            for s0, s1 in x_dw_spans:
                if s0 <= pos <= s1:
                    cands = [p for p in (s0, s1) if lo <= p <= hi]
                    if not cands:
                        for tm in (0.35, 0.22, 0.15):
                            s_mid = (s0 + s1) * 0.5
                            half = (s1 - s0 - margin * 2.0) * 0.5 + tm
                            cands = [p for p in (s_mid - half, s_mid + half) if lo <= p <= hi]
                            if cands:
                                break
                    if not cands:
                        cands = [lo if abs(lo - pos) < abs(hi - pos) else hi]
                    pos = min(cands, key=lambda p: abs(p - pos))
                    hit = True
            if not hit:
                break
        return min(hi, max(lo, pos))

    stair_on_right = bool(
        (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
        or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
    )

    if stair_pos_info:
        _sw = float(stair_pos_info.get('w', 1.5))
        c_stair_w = max(4.2, _sw + 2.2)
    else:
        c_stair_w = 4.6
    c_stair_w = min(max(c_stair_w, 3.8), W * 0.28)

    rem_w = W - c_stair_w
    num_bays = 3 if rem_w >= 13.0 else 2

    if stair_on_right:
        b3 = _clear_cw(ix_max - c_stair_w, ix_min + 3.0, ix_max - 2.5)
        if num_bays == 3:
            avail_w = b3 - ix_min
            bay_w = avail_w / 3.0
            b1 = _clear_cw(ix_min + bay_w, ix_min + 2.0, b3 - 3.0)
            b2 = _clear_cw(b1 + (b3 - b1) * 0.5, b1 + 2.0, b3 - 2.0)
            cols = [
                (ix_min, b1, 'west'),
                (b1, b2, 'center_west'),
                (b2, b3, 'center_east'),
                (b3, ix_max, 'east_stair')
            ]
            col_b_walls = [b1, b2, b3]
        else:
            b1 = _clear_cw(ix_min + (b3 - ix_min) * 0.5, ix_min + 2.0, b3 - 2.0)
            cols = [
                (ix_min, b1, 'west'),
                (b1, b3, 'center'),
                (b3, ix_max, 'east_stair')
            ]
            col_b_walls = [b1, b3]
    else:
        b1 = _clear_cw(ix_min + c_stair_w, ix_min + 2.5, ix_max - 3.0)
        if num_bays == 3:
            avail_w = ix_max - b1
            bay_w = avail_w / 3.0
            b2 = _clear_cw(b1 + bay_w, b1 + 2.0, ix_max - 4.0)
            b3 = _clear_cw(b2 + (ix_max - b2) * 0.5, b2 + 2.0, ix_max - 2.0)
            cols = [
                (ix_min, b1, 'west_stair'),
                (b1, b2, 'center_west'),
                (b2, b3, 'center_east'),
                (b3, ix_max, 'east')
            ]
            col_b_walls = [b1, b2, b3]
        else:
            b2 = _clear_cw(b1 + (ix_max - b1) * 0.5, b1 + 2.0, ix_max - 2.0)
            cols = [
                (ix_min, b1, 'west_stair'),
                (b1, b2, 'center'),
                (b2, ix_max, 'east')
            ]
            col_b_walls = [b1, b2]

    # Check portals on this floor (e.g. skybridge portal on Floor 3)
    has_left_portal = False
    has_right_portal = False
    for ed in (extra_doorways or []):
        if ed.get('floor_idx', fl_idx) == fl_idx and ed.get('is_portal'):
            fac = ed.get('facade')
            ex = ed.get('x', 0.0)
            if fac == 'LEFT' or abs(ex - ix_min) < 0.35:
                has_left_portal = True
            elif fac == 'RIGHT' or abs(ex - ix_max) < 0.35:
                has_right_portal = True

    y_mid = (iy_min + iy_max) * 0.5
    walls = []

    def _vwall(px, y0, y1, dw_y):
        walls.append({
            'p1': (px, y0), 'p2': (px, y1),
            'axis': 'Y', 'pos': px, 'thickness': wall_t,
            'doorway': {'x': px, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
        })

    def _hwall(x0, x1, y, dw_x):
        walls.append({
            'p1': (x0, y), 'p2': (x1, y),
            'axis': 'X', 'pos': y, 'thickness': wall_t,
            'doorway': {'x': dw_x, 'y': y, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
        })

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.30
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

    def _dw(x, y, axis):
        return {'x': x, 'y': y, 'axis': axis, 'w': dw_w}

    # Vertical dividing walls with doorways between adjacent bays
    for cw in col_b_walls:
        _vwall(cw, iy_min, y_mid, (iy_min + y_mid) * 0.5)
        # Second doorway in north half for flowing circulation
        _vwall(cw, y_mid, iy_max, (y_mid + iy_max) * 0.5)

    rooms = []
    for ci, (cx0, cx1, ctag) in enumerate(cols):
        is_stair = 'stair' in ctag
        is_portal_col = (has_left_portal and ci == 0) or (has_right_portal and ci == len(cols) - 1)

        facades = {}
        if ci == 0:
            facades['LEFT'] = (iy_min, iy_max)
        if ci == len(cols) - 1:
            facades['RIGHT'] = (iy_min, iy_max)
        facades['FRONT'] = (cx0, cx1)
        facades['BACK'] = (cx0, cx1)

        if is_stair:
            _s_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'STAIR_LANDING'
            _rb = (cx0, cx1, iy_min, iy_max)
            _doors = []
            if ci > 0:
                _doors.append(_dw(cx0, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx0, (y_mid + iy_max) * 0.5, 'Y'))
            if ci < len(cols) - 1:
                _doors.append(_dw(cx1, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx1, (y_mid + iy_max) * 0.5, 'Y'))
            rooms.append(Room(
                id=f"fl{fl_idx}_{ctag}", floor_idx=fl_idx, role=_s_role,
                bounds=_rb, doorways=_doors, stair_hole=_holds_stair(_rb),
                exterior_facades=facades
            ))
        elif is_portal_col:
            # Full-depth skybridge reception gallery / galleria
            _p_role = 'ENTRANCE_HALL' if fl_idx == 3 else 'GREAT_HALL'
            _rb = (cx0, cx1, iy_min, iy_max)
            _doors = []
            if ci > 0:
                _doors.append(_dw(cx0, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx0, (y_mid + iy_max) * 0.5, 'Y'))
            if ci < len(cols) - 1:
                _doors.append(_dw(cx1, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx1, (y_mid + iy_max) * 0.5, 'Y'))
            rooms.append(Room(
                id=f"fl{fl_idx}_skybridge_gallery", floor_idx=fl_idx, role=_p_role,
                bounds=_rb, doorways=_doors, stair_hole=_holds_stair(_rb),
                exterior_facades=facades
            ))
        elif ctag == 'center_west' or (num_bays == 2 and ctag == 'center'):
            # Grand Salon / Dining / Reception Hall (full depth)
            if fl_idx == 0:
                _c_role = 'BANQUET_HALL'
            elif fl_idx == 1:
                _c_role = 'HOUSE_HALL'
            elif fl_idx == 2:
                _c_role = 'HOUSE_HALL'
            elif fl_idx == 3:
                _c_role = 'HOUSE_HALL'
            else:
                _c_role = 'MASTER_BED'
            _rb = (cx0, cx1, iy_min, iy_max)
            _doors = []
            if ci > 0:
                _doors.append(_dw(cx0, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx0, (y_mid + iy_max) * 0.5, 'Y'))
            if ci < len(cols) - 1:
                _doors.append(_dw(cx1, (iy_min + y_mid) * 0.5, 'Y'))
                _doors.append(_dw(cx1, (y_mid + iy_max) * 0.5, 'Y'))
            rooms.append(Room(
                id=f"fl{fl_idx}_salon", floor_idx=fl_idx, role=_c_role,
                bounds=_rb, doorways=_doors, stair_hole=_holds_stair(_rb),
                exterior_facades=facades
            ))
        else:
            # Split front/back into 2 comfortable domestic rooms!
            y_h = y_mid
            for ed in (extra_doorways or []):
                sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
                if sax == 'Y':
                    ey = ed.get('y', ed.get('pos', 0.0))
                    ew = ed.get('w', 1.2)
                    is_on_col_wall = (ci == 0 and (ed.get('facade') == 'LEFT' or abs(ed.get('x', 0) - ix_min) < 0.5)) or \
                                     (ci == len(cols) - 1 and (ed.get('facade') == 'RIGHT' or abs(ed.get('x', 0) - ix_max) < 0.5))
                    if is_on_col_wall:
                        d_margin = ew * 0.5 + 0.55
                        if abs(y_h - ey) < d_margin:
                            cands_y = [p for p in (ey - d_margin, ey + d_margin) if iy_min + 1.8 <= p <= iy_max - 1.8]
                            if cands_y:
                                y_h = min(cands_y, key=lambda p: abs(p - y_mid))
                            else:
                                y_h = None
                                break
            if y_h is not None:
                _hwall(cx0, cx1, y_h, (cx0 + cx1) * 0.5)
            if fl_idx == 0:
                if ci == 0:
                    r_south = 'KITCHEN'
                    r_north = 'PANTRY'
                elif ci == 1:
                    r_south = 'COUNCIL_CHAMBER'
                    r_north = 'BANQUET_HALL'
                else:
                    r_south = 'OFFICE'
                    r_north = 'BARRACKS_DORM'
            elif fl_idx == 1:
                if ci == 0:
                    r_south = 'MASTER_BED'
                    r_north = 'BEDROOM'
                else:
                    r_south = 'LIBRARY'
                    r_north = 'GUEST_ROOM'
            elif fl_idx == 2:
                r_south = 'BEDROOM'
                r_north = 'GUEST_ROOM'
            elif fl_idx == 3:
                r_south = 'PARLOR'
                r_north = 'BEDROOM'
            else:
                r_south = 'BEDROOM'
                r_north = 'GUEST_ROOM'

            _rb_s = (cx0, cx1, iy_min, y_mid)
            _rb_n = (cx0, cx1, y_mid, iy_max)

            _doors_s = [_dw((cx0 + cx1) * 0.5, y_mid, 'X')]
            _doors_n = [_dw((cx0 + cx1) * 0.5, y_mid, 'X')]
            if ci > 0:
                _doors_s.append(_dw(cx0, (iy_min + y_mid) * 0.5, 'Y'))
                _doors_n.append(_dw(cx0, (y_mid + iy_max) * 0.5, 'Y'))
            if ci < len(cols) - 1:
                _doors_s.append(_dw(cx1, (iy_min + y_mid) * 0.5, 'Y'))
                _doors_n.append(_dw(cx1, (y_mid + iy_max) * 0.5, 'Y'))

            rooms.append(Room(
                id=f"fl{fl_idx}_{ctag}_s", floor_idx=fl_idx, role=r_south,
                bounds=_rb_s, doorways=_doors_s, stair_hole=_holds_stair(_rb_s),
                exterior_facades={'FRONT': (cx0, cx1), **({'LEFT': (iy_min, y_mid)} if ci == 0 else {}), **({'RIGHT': (iy_min, y_mid)} if ci == len(cols) - 1 else {})}
            ))
            rooms.append(Room(
                id=f"fl{fl_idx}_{ctag}_n", floor_idx=fl_idx, role=r_north,
                bounds=_rb_n, doorways=_doors_n, stair_hole=_holds_stair(_rb_n),
                exterior_facades={'BACK': (cx0, cx1), **({'LEFT': (y_mid, iy_max)} if ci == 0 else {}), **({'RIGHT': (y_mid, iy_max)} if ci == len(cols) - 1 else {})}
            ))

    # Register external portals (connector doorways, skybridge entrances) in room boundaries
    for r in rooms:
        rx0, rx1, ry0, ry1 = r.bounds
        for ed in (extra_doorways or []):
            if ed.get('floor_idx', fl_idx) == fl_idx:
                sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
                if sax == 'X':
                    ed_x = ed.get('x', ed.get('pos', 0.0))
                    ed_y = iy_max if ed.get('facade') == 'BACK' else iy_min
                    if (rx0 - 0.45 <= ed_x <= rx1 + 0.45) and (abs(ed_y - ry0) < 0.45 or abs(ed_y - ry1) < 0.45):
                        ed_entry = {'x': ed_x, 'y': ed_y, 'axis': 'X', 'w': ed.get('w', 2.4), 'is_portal': True}
                        if not any(abs(d.get('x', 0) - ed_x) < 0.2 and abs(d.get('y', 0) - ed_y) < 0.2 for d in r.doorways):
                            r.doorways.append(ed_entry)
                else:
                    ed_y = ed.get('y', ed.get('pos', 0.0))
                    ed_x = ix_max if ed.get('facade') == 'RIGHT' else ix_min
                    if (ry0 - 0.45 <= ed_y <= ry1 + 0.45) and (abs(ed_x - rx0) < 0.45 or abs(ed_x - rx1) < 0.45):
                        ed_entry = {'x': ed_x, 'y': ed_y, 'axis': 'Y', 'w': ed.get('w', 2.4), 'is_portal': True}
                        if not any(abs(d.get('x', 0) - ed_x) < 0.2 and abs(d.get('y', 0) - ed_y) < 0.2 for d in r.doorways):
                            r.doorways.append(ed_entry)

    return rooms, walls


def _plan_noble_manor_rooms(fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
                            has_stairs_landing, stair_pos_info=None,
                            extra_doorways=None, props=None,
                            fl_wings_bounds=None, noble_void=None):
    """Corridor-based Noble Manor plan.

    The old throne-palace planner made a huge central hall, duplicated the
    banquet hall in a wing and left the upper floor as a chain of walk-through
    rooms.  This plan keeps the throne room but puts it on axis behind the
    entrance, then serves two rows of compact chambers from a front reception
    gallery and a rear service corridor.  The staircase sits in a dedicated
    open stair hall at one end, so it is never cut off by a partition.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 22.0 or D < 12.0:
        return None

    stair_on_right = bool(
        (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
        or (stair_hole is not None and (stair_hole[0] + stair_hole[1]) * 0.5 > (ix_min + ix_max) * 0.5)
        or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
    )

    stair_w = 4.8
    if stair_pos_info:
        stair_w = max(stair_w, float(stair_pos_info.get('w', 1.5)) + 2.4)
    stair_w = min(max(stair_w, 4.0), W * 0.24)
    if stair_on_right:
        stair_x0, stair_x1 = ix_max - stair_w, ix_max
        rooms_x0, rooms_x1 = ix_min, stair_x0
    else:
        stair_x0, stair_x1 = ix_min, ix_min + stair_w
        rooms_x0, rooms_x1 = stair_x1, ix_max
    rooms_w = rooms_x1 - rooms_x0

    front_d = 2.15
    back_d = 2.15
    front_y1 = iy_min + front_d
    back_y0 = iy_max - back_d
    mid_y = (front_y1 + back_y0) * 0.5
    if back_y0 - front_y1 < 5.2:
        return None

    # A narrow cross-passage at the far end from the stair links the reception
    # gallery to the rear service corridor, so servants never have to cross the
    # whole manor to reach the back rooms.  It also prevents the two corridors
    # from becoming dead ends.
    cross_w = 2.20
    if stair_on_right:
        cross_x0, cross_x1 = rooms_x0, rooms_x0 + cross_w
        bay_x0, bay_x1 = cross_x1, rooms_x1
    else:
        cross_x0, cross_x1 = rooms_x1 - cross_w, rooms_x1
        bay_x0, bay_x1 = rooms_x0, cross_x0
    rooms_w = bay_x1 - bay_x0

    n_bays = max(3, min(9, int(round(rooms_w / 6.2))))
    x_edges = [bay_x0 + rooms_w * i / n_bays for i in range(n_bays + 1)]

    # The throne room spans the middle pair of front bays.  It opens straight
    # off the entrance gallery, on the same axis as the front door.
    throne_a = max(0, n_bays // 2 - 1)
    throne_b = min(n_bays - 1, throne_a + 1)
    if throne_b == throne_a and throne_a > 0:
        throne_a -= 1

    def _is_throne_bay(i):
        return throne_a <= i <= throne_b

    def _bay_doors(i):
        return {'x': (x_edges[i] + x_edges[i + 1]) * 0.5,
                'y': front_y1, 'axis': 'X', 'w': dw_w}

    walls = []
    rooms = []

    def _room(b, role, doors, facades, allow_large=True):
        return Room(
            id=f"fl{fl_idx}_{role.lower()}_{len(rooms)}", floor_idx=fl_idx,
            role=role, bounds=b, doorways=list(doors), stair_hole=None,
            exterior_facades=facades, allow_large=allow_large)

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.25
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

    # Ground-floor programme: service rooms and the ceremonial axis.  There is
    # deliberately NO banquet hall here; the only one is in the right wing.
    ground_south = ['PANTRY', 'DINING', 'GUARD_ROOM', 'STUDY', 'LIBRARY',
                    'COUNCIL_CHAMBER', 'STORAGE', 'OFFICE', 'STUDY']
    ground_north = ['ARMORY', 'GUARD_ROOM', 'TREASURY', 'STUDY', 'LIBRARY',
                    'COUNCIL_CHAMBER', 'STORAGE', 'OFFICE', 'HOUSE_HALL']
    upper_south = ['BEDROOM', 'GUEST_ROOM', 'BEDROOM', 'GUEST_ROOM', 'STUDY',
                   'BEDROOM', 'GUEST_ROOM', 'BEDROOM', 'STUDY']
    upper_north = ['BEDROOM', 'GUEST_ROOM', 'STUDY', 'BEDROOM', 'GUEST_ROOM',
                   'LIBRARY', 'BEDROOM', 'GUEST_ROOM', 'STUDY']
    if fl_idx == 0:
        south_roles, north_roles = ground_south, ground_north
    else:
        south_roles, north_roles = list(upper_south), list(upper_north)
        if not fl_wings_bounds and fl_idx == 1:
            # T1 has no upper wing: the service barracks lives in the manor.
            north_roles[0] = 'BARRACKS_DORM'
            north_roles[1] = 'OFFICER_QUARTERS'

    # Front reception gallery: connects the main entrance, both wing portals
    # and the stair hall.
    gallery_doors = []
    for ed in (extra_doorways or []):
        if ed.get('floor_idx', fl_idx) != fl_idx:
            continue
        ax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
        if ax == 'X':
            ey = float(ed.get('y', ed.get('pos', iy_min)))
            if abs(ey - iy_min) < 0.6:
                gallery_doors.append({'x': float(ed.get('x', 0.0)),
                                      'y': iy_min, 'axis': 'X',
                                      'w': float(ed.get('w', 2.4)),
                                      'is_portal': bool(ed.get('is_portal'))})
    gallery = Room(
        id=f"fl{fl_idx}_reception_gallery", floor_idx=fl_idx, role='CORRIDOR',
        bounds=(rooms_x0, rooms_x1, iy_min, front_y1),
        doorways=gallery_doors, stair_hole=None,
        exterior_facades={'FRONT': (rooms_x0, rooms_x1)}, allow_large=True)
    rooms.append(gallery)

    # Rear service corridor.
    rear_doors = []
    for ed in (extra_doorways or []):
        if ed.get('floor_idx', fl_idx) != fl_idx:
            continue
        ax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
        if ax == 'X':
            ey = float(ed.get('y', ed.get('pos', iy_max)))
            if abs(ey - iy_max) < 0.6:
                rear_doors.append({'x': float(ed.get('x', 0.0)),
                                   'y': iy_max, 'axis': 'X',
                                   'w': float(ed.get('w', 2.4)),
                                   'is_portal': bool(ed.get('is_portal'))})
    rear = Room(
        id=f"fl{fl_idx}_rear_corridor", floor_idx=fl_idx, role='CORRIDOR',
        bounds=(rooms_x0, rooms_x1, back_y0, iy_max),
        doorways=rear_doors, stair_hole=None,
        exterior_facades={'BACK': (rooms_x0, rooms_x1)}, allow_large=True)
    rooms.append(rear)

    # Short cross-passage from the front gallery to the rear corridor at the
    # end opposite the stair.
    cross_facades = {}
    if stair_on_right:
        cross_facades['LEFT'] = (front_y1, back_y0)
    else:
        cross_facades['RIGHT'] = (front_y1, back_y0)
    cross = Room(
        id=f"fl{fl_idx}_cross_passage", floor_idx=fl_idx, role='CORRIDOR',
        bounds=(cross_x0, cross_x1, front_y1, back_y0),
        doorways=[], stair_hole=None,
        exterior_facades=cross_facades, allow_large=True)
    rooms.append(cross)

    # Stair hall: full depth and open to both corridors.  No partition ever
    # crosses the flight or the step-off landings.
    stair_facades = {}
    if stair_on_right:
        stair_facades['RIGHT'] = (iy_min, iy_max)
    else:
        stair_facades['LEFT'] = (iy_min, iy_max)
    stair_facades['FRONT'] = (stair_x0, stair_x1)
    stair_facades['BACK'] = (stair_x0, stair_x1)
    stair_room = Room(
        id=f"fl{fl_idx}_stair_hall", floor_idx=fl_idx,
        role='ENTRANCE_HALL' if fl_idx == 0 else 'STAIR_LANDING',
        bounds=(stair_x0, stair_x1, iy_min, iy_max),
        doorways=[], stair_hole=_holds_stair((stair_x0, stair_x1, iy_min, iy_max)),
        exterior_facades=stair_facades, allow_large=True)
    rooms.append(stair_room)

    # Front row (off the reception gallery).  The central span is the throne.
    throne_bounds = (x_edges[throne_a], x_edges[throne_b + 1], front_y1, mid_y)
    for i in range(n_bays):
        if _is_throne_bay(i):
            continue
        role = south_roles[min(i, len(south_roles) - 1)]
        door = _bay_doors(i)
        facades = {'FRONT': (x_edges[i], x_edges[i + 1])}
        if i == 0:
            facades['LEFT'] = (front_y1, mid_y)
        if i == n_bays - 1:
            facades['RIGHT'] = (front_y1, mid_y)
        rooms.append(_room((x_edges[i], x_edges[i + 1], front_y1, mid_y),
                           role, [door], facades))
        gallery.doorways.append(door)

    throne_door = {'x': (throne_bounds[0] + throne_bounds[1]) * 0.5,
                   'y': front_y1, 'axis': 'X',
                   'w': min(2.60, dw_w + 0.55) if fl_idx == 0 else dw_w}
    if fl_idx == 0:
        throne_role = 'THRONE_ROOM'
    elif fl_idx == int(getattr(props, 'num_floors', 1)) - 1:
        throne_role = 'MASTER_BED'
    else:
        throne_role = 'HOUSE_HALL'
    rooms.append(_room(throne_bounds, throne_role, [throne_door],
                       {'FRONT': (throne_bounds[0], throne_bounds[1])}))
    if fl_idx == 1 and bool(getattr(props, 'noble_manor_layout', False)):
        _central = rooms[-1]
        _central.role = 'MEZZANINE_GALLERY'
        if noble_void is not None:
            _central.floor_void = noble_void
        else:
            _rim = 1.45
            _v = (throne_bounds[0] + _rim, throne_bounds[1] - _rim,
                  throne_bounds[2] + _rim, throne_bounds[3] - _rim)
            if _v[1] - _v[0] >= 2.2 and _v[3] - _v[2] >= 2.2:
                _central.floor_void = _v
    gallery.doorways.append(throne_door)

    # Back row (off the rear service corridor): compact chambers, never
    # walk-through rooms.
    for i in range(n_bays):
        role = north_roles[min(i, len(north_roles) - 1)]
        door = {'x': (x_edges[i] + x_edges[i + 1]) * 0.5,
                'y': back_y0, 'axis': 'X', 'w': dw_w}
        facades = {'BACK': (x_edges[i], x_edges[i + 1])}
        if i == 0:
            facades['LEFT'] = (mid_y, back_y0)
        if i == n_bays - 1:
            facades['RIGHT'] = (mid_y, back_y0)
        rooms.append(_room((x_edges[i], x_edges[i + 1], mid_y, back_y0),
                           role, [door], facades))
        rear.doorways.append(door)

    # --- Partition walls -------------------------------------------------
    # Corridor walls: one segment per room, each with its own door.  The
    # throne bay uses one wide segment instead of two narrow ones.
    for i in range(n_bays):
        if _is_throne_bay(i):
            continue
        dw_x = (x_edges[i] + x_edges[i + 1]) * 0.5
        walls.append({'p1': (x_edges[i], front_y1),
                      'p2': (x_edges[i + 1], front_y1),
                      'axis': 'X', 'pos': front_y1, 'thickness': wall_t,
                      'doorway': {'x': dw_x, 'y': front_y1, 'w': dw_w,
                                  'h': dw_h, 'axis': 'X'}})
        dw_x = (x_edges[i] + x_edges[i + 1]) * 0.5
        walls.append({'p1': (x_edges[i], back_y0),
                      'p2': (x_edges[i + 1], back_y0),
                      'axis': 'X', 'pos': back_y0, 'thickness': wall_t,
                      'doorway': {'x': dw_x, 'y': back_y0, 'w': dw_w,
                                  'h': dw_h, 'axis': 'X'}})
    walls.append({'p1': (throne_bounds[0], front_y1),
                  'p2': (throne_bounds[1], front_y1),
                  'axis': 'X', 'pos': front_y1, 'thickness': wall_t,
                  'doorway': {'x': throne_door['x'], 'y': front_y1,
                              'w': throne_door['w'], 'h': dw_h, 'axis': 'X'}})
    # The central spine wall between the two chamber rows.
    walls.append({'p1': (bay_x0, mid_y), 'p2': (bay_x1, mid_y),
                  'axis': 'X', 'pos': mid_y, 'thickness': wall_t,
                  'doorway': None})
    # Wall between the cross-passage and the first real room bay.
    walls.append({'p1': (bay_x0, front_y1), 'p2': (bay_x0, mid_y),
                  'axis': 'Y', 'pos': bay_x0, 'thickness': wall_t,
                  'doorway': None})
    walls.append({'p1': (bay_x0, mid_y), 'p2': (bay_x0, back_y0),
                  'axis': 'Y', 'pos': bay_x0, 'thickness': wall_t,
                  'doorway': None})
    # Bay partitions: south half always, north half except inside the throne
    # span (where the two central front bays are one room).
    for i in range(1, n_bays):
        px = x_edges[i]
        if not (_is_throne_bay(i - 1) and _is_throne_bay(i)):
            walls.append({'p1': (px, front_y1), 'p2': (px, mid_y),
                          'axis': 'Y', 'pos': px, 'thickness': wall_t,
                          'doorway': None})
        walls.append({'p1': (px, mid_y), 'p2': (px, back_y0),
                      'axis': 'Y', 'pos': px, 'thickness': wall_t,
                      'doorway': None})

    # Register side doors on the outer walls with the room that owns them.
    for ed in (extra_doorways or []):
        if ed.get('floor_idx', fl_idx) != fl_idx:
            continue
        ax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
        if ax != 'Y':
            continue
        ex = ix_max if ed.get('facade') == 'RIGHT' else ix_min
        ey = float(ed.get('y', ed.get('pos', 0.0)))
        for room in rooms:
            rx0, rx1, ry0, ry1 = room.bounds
            if abs(ex - rx0) < 0.5 or abs(ex - rx1) < 0.5:
                if ry0 - 0.45 <= ey <= ry1 + 0.45:
                    entry = {'x': ex, 'y': ey, 'axis': 'Y',
                             'w': float(ed.get('w', 2.4)),
                             'is_portal': bool(ed.get('is_portal'))}
                    if not any(abs(d.get('x', 0) - ex) < 0.2
                               and abs(d.get('y', 0) - ey) < 0.2
                               for d in room.doorways):
                        room.doorways.append(entry)

    # --- Wings ------------------------------------------------------------
    for wi, wb in enumerate(fl_wings_bounds or []):
        wx1, wx2, wy1, wy2 = wb
        if fl_idx == 0:
            role = 'KITCHEN' if wi == 0 else 'BANQUET_HALL'
        else:
            role = 'BARRACKS_DORM' if wi == 0 else 'GUEST_ROOM'
        wing_doors = []
        wing_x = (wx1 + wx2) * 0.5
        if abs(wy1 - iy_min) < 0.5:
            wing_doors.append({'x': wing_x, 'y': wy1, 'axis': 'X', 'w': dw_w})
        elif abs(wy2 - iy_min) < 0.5:
            wing_doors.append({'x': wing_x, 'y': wy2, 'axis': 'X', 'w': dw_w})
        w_sh = None
        if stair_hole is not None:
            if not (stair_hole[1] < wx1 or stair_hole[0] > wx2
                    or stair_hole[3] < wy1 or stair_hole[2] > wy2):
                w_sh = stair_hole
        rooms.append(Room(
            id=f"fl{fl_idx}_noble_wing{wi}", floor_idx=fl_idx, role=role,
            bounds=wb, is_wing=True, wing_id=wi, doorways=wing_doors,
            stair_hole=w_sh, exterior_facades={}, allow_large=True))

    return rooms, walls


def _secondary_role(primary, index):
    """Sensible companion role for a room carved out of a long strip."""
    table = {
        'MASTER_BED': ['BEDROOM', 'STUDY'],
        'BEDROOM': ['GUEST_ROOM', 'STUDY'],
        'GUEST_ROOM': ['BEDROOM', 'STORAGE'],
        'KITCHEN': ['PANTRY', 'STORAGE'],
        'HOUSE_HALL': ['KITCHEN', 'STUDY'],
        'GREAT_HALL': ['STUDY', 'STORAGE'],
        'BANQUET_HALL': ['PANTRY', 'STUDY'],
        'LIBRARY': ['STUDY', 'STORAGE'],
    }
    opts = table.get(primary, ['STORAGE', 'STUDY'])
    return opts[min(max(index - 1, 0), len(opts) - 1)]


def _split_room_out_of_zones(rooms, interior_walls, zones, wall_t, dw_w, dw_h):
    """Carve any room that crosses a keep-out into rooms that leave it empty.

    A keep-out (stair well, annex doorway apron) must be physically clear, so a
    room whose rectangle overlaps one is split along the short axis just outside
    the keep-out edge: the larger piece stays the room, the leftover strip
    becomes a CORRIDOR (walkable space is allowed there), and the splitting wall
    gets a door so the corridor leads into it.
    """
    if not rooms or not zones:
        return rooms
    out = []
    for room in rooms:
        b = list(room.bounds)
        _split = False
        for (zx0, zx1, zy0, zy1) in zones:
            # Overlap with a little slack: a wall kissing the keep-out is fine.
            if (b[1] <= zx0 + 0.02 or b[0] >= zx1 - 0.02
                    or b[3] <= zy0 + 0.02 or b[2] >= zy1 - 0.02):
                continue
            # Split on the axis that leaves the bigger usable room.
            w = b[1] - b[0]
            d = b[3] - b[2]
            left = zx0 - b[0]
            right = b[1] - zx1
            front = zy0 - b[2]
            back = b[3] - zy1
            cands = []
            if left >= 1.2:
                cands.append((left, 'X', b[0], zx0))
            if right >= 1.2:
                cands.append((right, 'X', zx1, b[1]))
            if front >= 1.2:
                cands.append((front, 'Y', b[2], zy0))
            if back >= 1.2:
                cands.append((back, 'Y', zy1, b[3]))
            if not cands:
                continue
            _len, _axis, _a, _c = max(cands)
            if _axis == 'X':
                keep = (_a, _c, b[2], b[3])
                rest = (b[0], b[1], b[2], b[3])
                cut = _a if _a > b[0] + 0.01 else _c
                rest = ((cut, b[1], b[2], b[3]) if cut == _a
                        else (b[0], cut, b[2], b[3]))
                dy = (b[2] + b[3]) * 0.5
                interior_walls.append({
                    'p1': (cut, b[2]), 'p2': (cut, b[3]),
                    'axis': 'Y', 'pos': cut, 'thickness': wall_t,
                    'doorway': {'x': cut, 'y': dy, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
                })
                _door = {'x': cut, 'y': dy, 'axis': 'Y', 'w': dw_w}
            else:
                keep = (b[0], b[1], _a, _c)
                cut = _a if _a > b[2] + 0.01 else _c
                rest = ((b[0], b[1], cut, b[3]) if cut == _a
                        else (b[0], b[1], b[2], cut))
                dx = (b[0] + b[1]) * 0.5
                interior_walls.append({
                    'p1': (b[0], cut), 'p2': (b[1], cut),
                    'axis': 'X', 'pos': cut, 'thickness': wall_t,
                    'doorway': {'x': dx, 'y': cut, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
                })
                _door = {'x': dx, 'y': cut, 'axis': 'X', 'w': dw_w}
            room.bounds = keep
            room.stair_hole = None
            room.doorways = list(room.doorways) + [_door]
            out.append(room)
            _rw = rest[1] - rest[0]
            _rd = rest[3] - rest[2]
            if min(_rw, _rd) >= 0.9:
                out.append(Room(
                    id=f"{room.id}_corr", floor_idx=room.floor_idx, role='CORRIDOR',
                    bounds=rest, doorways=[_door], stair_hole=None,
                    is_wing=False, wing_id=room.wing_id,
                    exterior_facades=dict(room.exterior_facades)))
            _split = True
            break
        if not _split:
            out.append(room)
    return out


def _merge_sliver_rooms(rooms, interior_walls, min_side=1.30, max_passes=4):
    """Merge unusable thin rooms (e.g. a 0.7 m strip carved in front of a wing
    door) into their neighbour and remove the partition that separated them.

    Slivers read as a broken wall ending in the middle of a room and can also
    wall off a doorway, so they are folded back into a real room.
    """
    if not rooms:
        return rooms
    for _ in range(max_passes):
        changed = False
        for sliver in list(rooms):
            if sliver.stair_hole is not None:
                continue
            b = sliver.bounds
            w, d = b[1] - b[0], b[3] - b[2]
            if min(w, d) >= min_side or w <= 0.01 or d <= 0.01:
                continue
            best = None
            for other in rooms:
                if other is sliver:
                    continue
                ob = other.bounds
                # Shared vertical edge (left/right neighbours) -> merge along X.
                if abs(b[0] - ob[1]) < 0.35 or abs(b[1] - ob[0]) < 0.35:
                    ov = min(b[3], ob[3]) - max(b[2], ob[2])
                    if ov > 0.30 and (best is None or ov > best[0]):
                        best = (ov, other)
                # Shared horizontal edge (front/back neighbours) -> merge along Y.
                if abs(b[2] - ob[3]) < 0.35 or abs(b[3] - ob[2]) < 0.35:
                    ov = min(b[1], ob[1]) - max(b[0], ob[0])
                    if ov > 0.30 and (best is None or ov > best[0]):
                        best = (ov, other)
            if best is None:
                continue
            other = best[1]
            nb = (min(b[0], other.bounds[0]), max(b[1], other.bounds[1]),
                  min(b[2], other.bounds[2]), max(b[3], other.bounds[3]))
            other.bounds = nb
            other.doorways = list(other.doorways or [])
            for _dw in (sliver.doorways or []):
                if _dw not in other.doorways:
                    other.doorways.append(_dw)
            rooms.remove(sliver)
            # Drop partitions that now sit strictly inside the merged room.
            for _wl in list(interior_walls):
                p1, p2 = _wl.get('p1'), _wl.get('p2')
                if p1 is None or p2 is None:
                    continue
                if abs(p1[1] - p2[1]) < 1e-6:      # horizontal wall at y
                    _y = p1[1]
                    _x0, _x1 = min(p1[0], p2[0]), max(p1[0], p2[0])
                    if (nb[2] + 0.20 < _y < nb[3] - 0.20
                            and _x0 >= nb[0] - 0.20 and _x1 <= nb[1] + 0.20):
                        interior_walls.remove(_wl)
                elif abs(p1[0] - p2[0]) < 1e-6:    # vertical wall at x
                    _x = p1[0]
                    _y0, _y1 = min(p1[1], p2[1]), max(p1[1], p2[1])
                    if (nb[0] + 0.20 < _x < nb[1] - 0.20
                            and _y0 >= nb[2] - 0.20 and _y1 <= nb[3] + 0.20):
                        interior_walls.remove(_wl)
            changed = True
            break
        if not changed:
            break
    return rooms


def _wall_endpoint_connected(pt, walls, bounds, skip=None, tol=0.22):
    x, y = pt
    x0, x1, y0, y1 = bounds
    if min(abs(x - x0), abs(x - x1), abs(y - y0), abs(y - y1)) <= tol:
        return True
    for other in walls:
        if other is skip:
            continue
        p1, p2 = other.get('p1'), other.get('p2')
        if not p1 or not p2:
            continue
        ax = other.get('axis')
        if ax == 'Y':
            # Vertical wall: endpoint on its line and within its span.
            if abs(p1[0] - x) <= tol:
                lo, hi = min(p1[1], p2[1]), max(p1[1], p2[1])
                if lo - tol <= y <= hi + tol:
                    # Do not count a point sitting inside this wall's doorway.
                    dw = other.get('doorway')
                    if dw and abs(dw.get('y', 1e9) - y) < float(dw.get('w', 1.0)) * 0.5 + 0.05:
                        continue
                    return True
        elif ax == 'X':
            if abs(p1[1] - y) <= tol:
                lo, hi = min(p1[0], p2[0]), max(p1[0], p2[0])
                if lo - tol <= x <= hi + tol:
                    dw = other.get('doorway')
                    if dw and abs(dw.get('x', 1e9) - x) < float(dw.get('w', 1.0)) * 0.5 + 0.05:
                        continue
                    return True
    return False


def _repair_dangling_walls(interior_walls, bounds, tol=0.22, max_extension=4.0):
    """Never leave a partition ending in mid-air.

    A wall end must meet the exterior shell or another partition.  If a split
    was blocked by a door/annex keep-out, the old planner simply cut the wall
    short; extend it to the nearest legal perpendicular wall or shell instead.
    If no legal target exists, drop the stub so the rooms read as one planned
    space rather than a broken wall.
    """
    if not interior_walls:
        return interior_walls
    x0, x1, y0, y1 = bounds
    drop = set()
    for _ in range(3):
        changed = False
        live = [w for w in interior_walls if id(w) not in drop]
        for w in live:
            p1, p2 = w.get('p1'), w.get('p2')
            if not p1 or not p2:
                continue
            ax = w.get('axis')
            for which in (0, 1):
                pt = p1 if which == 0 else p2
                if _wall_endpoint_connected(pt, live, bounds, skip=w, tol=tol):
                    continue
                px, py = pt
                best = None
                if ax == 'Y':
                    direction = 1.0 if which == 0 else -1.0
                    # Midpoint of this wall tells us which way the free end
                    # points when p1/p2 order is ambiguous.
                    mid_y = (p1[1] + p2[1]) * 0.5
                    direction = 1.0 if py >= mid_y else -1.0
                    for other in live:
                        if other is w or other.get('axis') != 'X':
                            continue
                        op1, op2 = other.get('p1'), other.get('p2')
                        if not op1 or not op2:
                            continue
                        olo, ohi = min(op1[0], op2[0]), max(op1[0], op2[0])
                        if not (olo - tol <= px <= ohi + tol):
                            continue
                        oy = op1[1]
                        dy = oy - py
                        if (dy > tol or dy < -tol) and dy * direction > 0:
                            dw = other.get('doorway')
                            if dw and abs(dw.get('x', 1e9) - px) < float(dw.get('w', 1.0)) * 0.5 + 0.10:
                                continue
                            dist = abs(dy)
                            if dist <= max_extension and (best is None or dist < best[0]):
                                best = (dist, oy)
                    if best is None:
                        shell = y1 if direction > 0 else y0
                        if abs(shell - py) <= max_extension:
                            best = (abs(shell - py), shell)
                    if best is not None:
                        newpt = (px, best[1])
                    else:
                        drop.add(id(w))
                        changed = True
                        break
                elif ax == 'X':
                    mid_x = (p1[0] + p2[0]) * 0.5
                    direction = 1.0 if px >= mid_x else -1.0
                    for other in live:
                        if other is w or other.get('axis') != 'Y':
                            continue
                        op1, op2 = other.get('p1'), other.get('p2')
                        if not op1 or not op2:
                            continue
                        olo, ohi = min(op1[1], op2[1]), max(op1[1], op2[1])
                        if not (olo - tol <= py <= ohi + tol):
                            continue
                        ox = op1[0]
                        dx = ox - px
                        if (dx > tol or dx < -tol) and dx * direction > 0:
                            dw = other.get('doorway')
                            if dw and abs(dw.get('y', 1e9) - py) < float(dw.get('w', 1.0)) * 0.5 + 0.10:
                                continue
                            dist = abs(dx)
                            if dist <= max_extension and (best is None or dist < best[0]):
                                best = (dist, ox)
                    if best is None:
                        shell = x1 if direction > 0 else x0
                        if abs(shell - px) <= max_extension:
                            best = (abs(shell - px), shell)
                    if best is not None:
                        newpt = (best[1], py)
                    else:
                        drop.add(id(w))
                        changed = True
                        break
                else:
                    continue
                if which == 0:
                    w['p1'] = newpt
                else:
                    w['p2'] = newpt
                changed = True
        if not changed:
            break
    return [w for w in interior_walls if id(w) not in drop]


def _replan_knights_manor_ground(rooms, walls, bounds, stair_hole, props, doorways,
                                 wall_t=0.16, dw_w=1.75, dw_h=2.95):
    """Rebuild the Knights Manor ground floor around a real banquet/kitchen.

    The generic military split left a huge stair-landing strip and chopped the
    remaining wing into narrow north/south slivers (tiny mess/armoury strips).
    This plan keeps the stair hall, puts one generous banquet hall beside it,
    then a full-depth kitchen/pantry pair.  No tiny rooms are left over.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 14.0 or D < 8.0 or not rooms:
        return rooms, walls
    wings = [r for r in rooms if getattr(r, 'is_wing', False)]
    stair_rm = next((r for r in rooms
                     if not getattr(r, 'is_wing', False)
                     and (r.role == 'STAIR_LANDING' or
                          (stair_hole is not None and r.stair_hole is not None))), None)
    if stair_rm is None:
        stair_rm = next((r for r in rooms
                         if not getattr(r, 'is_wing', False)
                         and r.role in ('ENTRANCE_HALL', 'CORRIDOR')), None)
    if stair_rm is None:
        return rooms, walls
    sr_x0, sr_x1, _, _ = stair_rm.bounds
    stair_on_right = (sr_x0 + sr_x1) * 0.5 > (ix_min + ix_max) * 0.5

    stair_w = 5.25
    if stair_hole is not None:
        stair_w = max(stair_w, (stair_hole[1] - ix_min) + 0.75) if not stair_on_right \
            else max(stair_w, (ix_max - stair_hole[0]) + 0.75)
    stair_w = min(max(stair_w, 4.8), W * 0.34)
    if stair_on_right:
        stair_x0, stair_x1 = ix_max - stair_w, ix_max
        rest_x0, rest_x1 = ix_min, stair_x0
    else:
        stair_x0, stair_x1 = ix_min, ix_min + stair_w
        rest_x0, rest_x1 = stair_x1, ix_max
    rest_w = rest_x1 - rest_x0
    if rest_w < 7.0:
        return rooms, walls

    mid_y = (iy_min + iy_max) * 0.5
    mid_s = (iy_min + mid_y) * 0.5
    mid_n = (mid_y + iy_max) * 0.5
    banquet_w = rest_w * (0.56 if rest_w >= 9.0 else 0.62)
    if stair_on_right:
        banquet_x0, banquet_x1 = rest_x1 - banquet_w, rest_x1
        kitchen_x0, kitchen_x1 = rest_x0, banquet_x0
    else:
        banquet_x0, banquet_x1 = rest_x0, rest_x0 + banquet_w
        kitchen_x0, kitchen_x1 = banquet_x1, rest_x1
    inner_x = stair_x1 if not stair_on_right else stair_x0
    banquet_stair_x = inner_x
    kitchen_boundary = banquet_x0 if stair_on_right else banquet_x1

    new_rooms = []
    stair_old = stair_rm
    stair_doors = [{'x': inner_x, 'y': mid_y, 'axis': 'Y', 'w': dw_w}]
    stair_fac = {'FRONT': (stair_x0, stair_x1), 'BACK': (stair_x0, stair_x1)}
    stair_fac['RIGHT' if stair_on_right else 'LEFT'] = (iy_min, iy_max)
    new_rooms.append(Room(
        id=f"fl0_knights_stair", floor_idx=0,
        role='STAIR_LANDING',
        bounds=(stair_x0, stair_x1, iy_min, iy_max),
        doorways=stair_doors, stair_hole=getattr(stair_old, 'stair_hole', None),
        exterior_facades=stair_fac, allow_large=True))

    banquet_doors = [
        {'x': banquet_stair_x, 'y': mid_y, 'axis': 'Y', 'w': dw_w},
        {'x': kitchen_boundary, 'y': mid_s, 'axis': 'Y', 'w': dw_w},
        {'x': kitchen_boundary, 'y': mid_n, 'axis': 'Y', 'w': dw_w},
    ]
    new_rooms.append(Room(
        id="fl0_knights_banquet", floor_idx=0, role='BANQUET_HALL',
        bounds=(banquet_x0, banquet_x1, iy_min, iy_max),
        doorways=banquet_doors, stair_hole=None,
        exterior_facades={'FRONT': (banquet_x0, banquet_x1),
                          'BACK': (banquet_x0, banquet_x1)},
        allow_large=True))
    new_rooms.append(Room(
        id="fl0_knights_kitchen", floor_idx=0, role='KITCHEN',
        bounds=(kitchen_x0, kitchen_x1, iy_min, mid_y),
        doorways=[{'x': kitchen_boundary, 'y': mid_s, 'axis': 'Y', 'w': dw_w}],
        stair_hole=None,
        exterior_facades={'FRONT': (kitchen_x0, kitchen_x1),
                          ('RIGHT' if kitchen_x1 >= ix_max - 0.1 else 'LEFT'):
                              (iy_min, mid_y)},
        allow_large=True))
    new_rooms.append(Room(
        id="fl0_knights_pantry", floor_idx=0, role='PANTRY',
        bounds=(kitchen_x0, kitchen_x1, mid_y, iy_max),
        doorways=[{'x': kitchen_boundary, 'y': mid_n, 'axis': 'Y', 'w': dw_w}],
        stair_hole=None,
        exterior_facades={'BACK': (kitchen_x0, kitchen_x1),
                          ('RIGHT' if kitchen_x1 >= ix_max - 0.1 else 'LEFT'):
                              (mid_y, iy_max)},
        allow_large=True))

    # Register front/back/side portals with the room that owns the facade span.
    all_new = new_rooms + wings
    for r in all_new:
        rx0, rx1, ry0, ry1 = r.bounds
        for d in (doorways or []):
            ax = d.get('axis', 'X')
            dx = float(d.get('x', 0.0)); dy = float(d.get('y', 0.0))
            w = float(d.get('w', 2.4))
            hit = False
            if ax == 'X':
                if (rx0 - 0.45 <= dx <= rx1 + 0.45
                        and (abs(dy - ry0) < 0.45 or abs(dy - ry1) < 0.45)):
                    hit = True
            else:
                if (ry0 - 0.45 <= dy <= ry1 + 0.45
                        and (abs(dx - rx0) < 0.45 or abs(dx - rx1) < 0.45)):
                    hit = True
            if hit and not any(abs(e.get('x', 0) - dx) < 0.2
                               and abs(e.get('y', 0) - dy) < 0.2
                               for e in r.doorways):
                r.doorways.append({'x': dx, 'y': dy, 'axis': ax, 'w': w,
                                   'is_portal': bool(d.get('is_portal'))})

    new_walls = [
        {'p1': (inner_x, iy_min), 'p2': (inner_x, iy_max),
         'axis': 'Y', 'pos': inner_x, 'thickness': wall_t,
         'doorway': {'x': inner_x, 'y': mid_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}},
        {'p1': (kitchen_boundary, iy_min), 'p2': (kitchen_boundary, mid_y),
         'axis': 'Y', 'pos': kitchen_boundary, 'thickness': wall_t,
         'doorway': {'x': kitchen_boundary, 'y': mid_s, 'w': dw_w,
                     'h': dw_h, 'axis': 'Y'}},
        {'p1': (kitchen_boundary, mid_y), 'p2': (kitchen_boundary, iy_max),
         'axis': 'Y', 'pos': kitchen_boundary, 'thickness': wall_t,
         'doorway': {'x': kitchen_boundary, 'y': mid_n, 'w': dw_w,
                     'h': dw_h, 'axis': 'Y'}},
        {'p1': (kitchen_x0, mid_y), 'p2': (kitchen_x1, mid_y),
         'axis': 'X', 'pos': mid_y, 'thickness': wall_t, 'doorway': None},
    ]
    return new_rooms, new_walls


def _replan_archery_lodge_ground(rooms, walls, bounds, stair_hole, props, doorways,
                                 wall_t=0.16, dw_w=1.75, dw_h=2.95):
    """Ground floor of an archery lodge: mess hall, kitchen and pantry.

    The shooting butts are outdoors; the indoor hall should not be a second
    empty range.  Give the archers a proper refectory with a working kitchen
    and pantry instead.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 8.0 or D < 7.0 or not rooms:
        return rooms, walls
    wings = [r for r in rooms if getattr(r, 'is_wing', False)]
    mid_y = (iy_min + iy_max) * 0.5
    mid_s = (iy_min + mid_y) * 0.5
    mid_n = (mid_y + iy_max) * 0.5
    mess_w = W * (0.62 if W >= 11.0 else 0.58)
    mess_x1 = ix_min + mess_w
    if ix_max - mess_x1 < 3.6:
        mess_x1 = ix_max - 3.6

    new_rooms = []
    mess = Room(
        id="fl0_archery_mess", floor_idx=0, role='MESS_HALL',
        bounds=(ix_min, mess_x1, iy_min, iy_max),
        doorways=[{'x': mess_x1, 'y': mid_s, 'axis': 'Y', 'w': dw_w},
                  {'x': mess_x1, 'y': mid_n, 'axis': 'Y', 'w': dw_w}],
        stair_hole=stair_hole if stair_hole is not None else None,
        exterior_facades={'FRONT': (ix_min, mess_x1),
                          'BACK': (ix_min, mess_x1),
                          'LEFT': (iy_min, iy_max)},
        allow_large=True)
    new_rooms.append(mess)
    new_rooms.append(Room(
        id="fl0_archery_kitchen", floor_idx=0, role='KITCHEN',
        bounds=(mess_x1, ix_max, iy_min, mid_y),
        doorways=[{'x': mess_x1, 'y': mid_s, 'axis': 'Y', 'w': dw_w}],
        stair_hole=None,
        exterior_facades={'FRONT': (mess_x1, ix_max),
                          'RIGHT': (iy_min, mid_y)},
        allow_large=True))
    new_rooms.append(Room(
        id="fl0_archery_pantry", floor_idx=0, role='PANTRY',
        bounds=(mess_x1, ix_max, mid_y, iy_max),
        doorways=[{'x': mess_x1, 'y': mid_n, 'axis': 'Y', 'w': dw_w}],
        stair_hole=None,
        exterior_facades={'BACK': (mess_x1, ix_max),
                          'RIGHT': (mid_y, iy_max)},
        allow_large=True))
    new_rooms += wings

    for r in new_rooms:
        rx0, rx1, ry0, ry1 = r.bounds
        for d in (doorways or []):
            ax = d.get('axis', 'X')
            dx = float(d.get('x', 0.0)); dy = float(d.get('y', 0.0))
            w = float(d.get('w', 2.4))
            hit = False
            if ax == 'X':
                if (rx0 - 0.45 <= dx <= rx1 + 0.45
                        and (abs(dy - ry0) < 0.45 or abs(dy - ry1) < 0.45)):
                    hit = True
            else:
                if (ry0 - 0.45 <= dy <= ry1 + 0.45
                        and (abs(dx - rx0) < 0.45 or abs(dx - rx1) < 0.45)):
                    hit = True
            if hit and not any(abs(e.get('x', 0) - dx) < 0.2
                               and abs(e.get('y', 0) - dy) < 0.2
                               for e in r.doorways):
                r.doorways.append({'x': dx, 'y': dy, 'axis': ax, 'w': w,
                                   'is_portal': bool(d.get('is_portal'))})

    new_walls = [
        {'p1': (mess_x1, iy_min), 'p2': (mess_x1, mid_y),
         'axis': 'Y', 'pos': mess_x1, 'thickness': wall_t,
         'doorway': {'x': mess_x1, 'y': mid_s, 'w': dw_w,
                     'h': dw_h, 'axis': 'Y'}},
        {'p1': (mess_x1, mid_y), 'p2': (mess_x1, iy_max),
         'axis': 'Y', 'pos': mess_x1, 'thickness': wall_t,
         'doorway': {'x': mess_x1, 'y': mid_n, 'w': dw_w,
                     'h': dw_h, 'axis': 'Y'}},
        {'p1': (mess_x1, mid_y), 'p2': (ix_max, mid_y),
         'axis': 'X', 'pos': mid_y, 'thickness': wall_t, 'doorway': None},
    ]
    return new_rooms, new_walls


def _clamp_tenement_walls(interior_walls, rooms, tol=0.24):
    """Keep tenement partitions inside the flat/room bounds they divide.

    Apartment grids are planned per flat; a wall from one flat must never run
    on into the neighbouring apartment.  Clip each wall to the extents of the
    rooms that actually share its line.
    """
    if not interior_walls or not rooms:
        return interior_walls
    for w in interior_walls:
        p1, p2 = w.get('p1'), w.get('p2')
        if not p1 or not p2:
            continue
        ax = w.get('axis')
        if ax == 'Y':
            pos = p1[0]
            lo, hi = min(p1[1], p2[1]), max(p1[1], p2[1])
            spans = []
            for r in rooms:
                x0, x1, y0, y1 = r.bounds
                if abs(x0 - pos) <= tol or abs(x1 - pos) <= tol:
                    spans.append((min(y0, y1), max(y0, y1)))
            if spans:
                nlo = max(lo, min(s[0] for s in spans if s[1] >= lo - tol))
                nhi = min(hi, max(s[1] for s in spans if s[0] <= hi + tol))
                if nhi - nlo >= 0.6:
                    w['p1'] = (pos, nlo)
                    w['p2'] = (pos, nhi)
        elif ax == 'X':
            pos = p1[1]
            lo, hi = min(p1[0], p2[0]), max(p1[0], p2[0])
            spans = []
            for r in rooms:
                x0, x1, y0, y1 = r.bounds
                if abs(y0 - pos) <= tol or abs(y1 - pos) <= tol:
                    spans.append((min(x0, x1), max(x0, x1)))
            if spans:
                nlo = max(lo, min(s[0] for s in spans if s[1] >= lo - tol))
                nhi = min(hi, max(s[1] for s in spans if s[0] <= hi + tol))
                if nhi - nlo >= 0.6:
                    w['p1'] = (nlo, pos)
                    w['p2'] = (nhi, pos)
    return interior_walls


def _open_wing_entrance_walls(interior_walls, wings, bounds, tol=0.35):
    """Drop partitions that run into a wing entrance opening.

    Some T-wing outbuildings placed a perpendicular main-block partition right
    inside the wide wing doorway.  A cut-down wall end still reads as a wall
    in the opening, so remove the offending segment entirely and let the
    entrance read as one vestibule.
    """
    if not interior_walls or not wings:
        return interior_walls
    ix_min, ix_max, iy_min, iy_max = bounds
    drop = set()
    for w in interior_walls:
        if w.get('axis') != 'Y':
            continue
        p1, p2 = w.get('p1'), w.get('p2')
        if not p1 or not p2:
            continue
        px = p1[0]
        for wb in wings:
            try:
                wx0, wx1, wy0, wy1 = (float(wb[0]), float(wb[1]),
                                      float(wb[2]), float(wb[3]))
            except Exception:
                continue
            if not (wx0 + 0.25 <= px <= wx1 - 0.25):
                continue
            # A wing attached to the front/back facade: any vertical wall end
            # at that facade inside the wing width is in the doorway.
            if wy1 <= iy_min + 0.45 and (abs(p1[1] - iy_min) < tol
                                         or abs(p2[1] - iy_min) < tol):
                drop.add(id(w))
                break
            if wy0 >= iy_max - 0.45 and (abs(p1[1] - iy_max) < tol
                                         or abs(p2[1] - iy_max) < tol):
                drop.add(id(w))
                break
    return [w for w in interior_walls if id(w) not in drop]


def _merge_open_rooms(rooms, walls, min_overlap=1.0, max_passes=4):
    """Merge adjacent rooms that have no wall between them.

    When a partition is removed to open a wing doorway, leaving the old room
    rectangles split makes the furnisher place chests against an invisible
    wall.  If no wall actually exists on the shared boundary, make it one room.
    """
    if not rooms:
        return rooms
    for _ in range(max_passes):
        merged = False
        for i in range(len(rooms)):
            if merged:
                break
            a = rooms[i]
            ax0, ax1, ay0, ay1 = a.bounds
            for j in range(i + 1, len(rooms)):
                b = rooms[j]
                bx0, bx1, by0, by1 = b.bounds
                shared = False
                vertical = False
                if abs(ax1 - bx0) < 0.12 or abs(bx1 - ax0) < 0.12:
                    shared = min(ay1, by1) - max(ay0, by0) >= min_overlap
                    vertical = True
                elif abs(ay1 - by0) < 0.12 or abs(by1 - ay0) < 0.12:
                    shared = min(ax1, bx1) - max(ax0, bx0) >= min_overlap
                if not shared:
                    continue
                # Check for any surviving wall on this boundary.
                has_wall = False
                for w in walls:
                    p1, p2 = w.get('p1'), w.get('p2')
                    if not p1 or not p2:
                        continue
                    if vertical and w.get('axis') == 'Y':
                        if abs(p1[0] - ax1) < 0.15 or abs(p1[0] - bx0) < 0.15 \
                                or abs(p1[0] - ax0) < 0.15 or abs(p1[0] - bx1) < 0.15:
                            lo = min(p1[1], p2[1]); hi = max(p1[1], p2[1])
                            if hi > max(ay0, by0) + 0.2 and lo < min(ay1, by1) - 0.2:
                                has_wall = True
                                break
                    elif not vertical and w.get('axis') == 'X':
                        if abs(p1[1] - ay1) < 0.15 or abs(p1[1] - by0) < 0.15 \
                                or abs(p1[1] - ay0) < 0.15 or abs(p1[1] - by1) < 0.15:
                            lo = min(p1[0], p2[0]); hi = max(p1[0], p2[0])
                            if hi > max(ax0, bx0) + 0.2 and lo < min(ax1, bx1) - 0.2:
                                has_wall = True
                                break
                if has_wall:
                    continue
                nb = (min(ax0, bx0), max(ax1, bx1), min(ay0, by0), max(ay1, by1))
                a.bounds = nb
                a.doorways = list(a.doorways or [])
                for d in (b.doorways or []):
                    if d not in a.doorways:
                        a.doorways.append(d)
                if a.stair_hole is None:
                    a.stair_hole = b.stair_hole
                if getattr(a, 'floor_void', None) is None:
                    a.floor_void = getattr(b, 'floor_void', None)
                a.allow_large = True
                rooms.pop(j)
                merged = True
                break
        if not merged:
            break
    return rooms


def _rebalance_room_boundaries(rooms, walls, min_side=3.15, max_passes=3):
    """Give cramped rooms a usable width by shifting the shared wall.

    The Nasher halls sometimes end up with a 1.8 m sleeping strip beside an
    oversized landing.  Rather than merging the whole floor, slide the common
    partition a little so both sides remain real, furnishable rooms.
    """
    if not rooms or not walls:
        return rooms
    _protected = {'THRONE_ROOM', 'BANQUET_HALL', 'CHAPEL_HALL',
                  'MEZZANINE_GALLERY', 'GREAT_HALL'}
    for _ in range(max_passes):
        changed = False
        for i in range(len(rooms)):
            a = rooms[i]
            for j in range(i + 1, len(rooms)):
                b = rooms[j]
                if getattr(a, 'role', '') in _protected or getattr(b, 'role', '') in _protected:
                    continue
                ax0, ax1, ay0, ay1 = a.bounds
                bx0, bx1, by0, by1 = b.bounds
                # Vertical shared wall
                if abs(ax1 - bx0) < 0.12 or abs(bx1 - ax0) < 0.12:
                    if min(ay1, by1) - max(ay0, by0) < 1.5:
                        continue
                    if ax1 <= bx0:
                        l, r, old = a, b, ax1
                    else:
                        l, r, old = b, a, ax1
                    lw = l.bounds[1] - l.bounds[0]
                    rw = r.bounds[1] - r.bounds[0]
                    if lw < min_side and rw > min_side + 1.0:
                        new = old + (min_side - lw)
                    elif rw < min_side and lw > min_side + 1.0:
                        new = old - (min_side - rw)
                    else:
                        continue
                    l.bounds = (l.bounds[0], new, l.bounds[2], l.bounds[3])
                    r.bounds = (new, r.bounds[1], r.bounds[2], r.bounds[3])
                    for w in walls:
                        if w.get('axis') != 'Y':
                            continue
                        if abs(w.get('pos', w['p1'][0]) - old) > 0.16:
                            continue
                        lo = min(w['p1'][1], w['p2'][1]); hi = max(w['p1'][1], w['p2'][1])
                        if hi < max(ay0, by0) + 0.2 or lo > min(ay1, by1) - 0.2:
                            continue
                        w['p1'] = (new, w['p1'][1]); w['p2'] = (new, w['p2'][1])
                        w['pos'] = new
                        dw = w.get('doorway')
                        if dw and dw.get('axis') == 'Y':
                            dw['x'] = new
                    for rm in (l, r):
                        for d in (rm.doorways or []):
                            if d.get('axis') == 'Y' and abs(d.get('x', 0.0) - old) < 0.2:
                                d['x'] = new
                    changed = True
                # Horizontal shared wall
                elif abs(ay1 - by0) < 0.12 or abs(by1 - ay0) < 0.12:
                    if min(ax1, bx1) - max(ax0, bx0) < 1.5:
                        continue
                    if ay1 <= by0:
                        s, n, old = a, b, ay1
                    else:
                        s, n, old = b, a, ay1
                    sd = s.bounds[3] - s.bounds[2]
                    nd = n.bounds[3] - n.bounds[2]
                    if sd < min_side and nd > min_side + 1.0:
                        new = old + (min_side - sd)
                    elif nd < min_side and sd > min_side + 1.0:
                        new = old - (min_side - nd)
                    else:
                        continue
                    s.bounds = (s.bounds[0], s.bounds[1], s.bounds[2], new)
                    n.bounds = (n.bounds[0], n.bounds[1], new, n.bounds[3])
                    for w in walls:
                        if w.get('axis') != 'X':
                            continue
                        if abs(w.get('pos', w['p1'][1]) - old) > 0.16:
                            continue
                        lo = min(w['p1'][0], w['p2'][0]); hi = max(w['p1'][0], w['p2'][0])
                        if hi < max(ax0, bx0) + 0.2 or lo > min(ax1, bx1) - 0.2:
                            continue
                        w['p1'] = (w['p1'][0], new); w['p2'] = (w['p2'][0], new)
                        w['pos'] = new
                        dw = w.get('doorway')
                        if dw and dw.get('axis') == 'X':
                            dw['y'] = new
                    for rm in (s, n):
                        for d in (rm.doorways or []):
                            if d.get('axis') == 'X' and abs(d.get('y', 0.0) - old) < 0.2:
                                d['y'] = new
                    changed = True
                if changed:
                    break
            if changed:
                break
        if not changed:
            break
    return rooms


def _consolidate_outbuilding_rooms(rooms, walls, max_habitable=3):
    """Merge small adjacent outbuilding rooms into a few usable chambers."""
    if not rooms:
        return rooms
    _through = {'CORRIDOR', 'STAIR_LANDING', 'ENTRANCE_HALL'}
    _protected = {'THRONE_ROOM', 'BANQUET_HALL', 'CHAPEL_HALL',
                  'MEZZANINE_GALLERY', 'GREAT_HALL'}

    def _habitable():
        return [r for r in rooms if getattr(r, 'role', '') not in _through]

    for _ in range(8):
        hab = _habitable()
        if len(hab) <= max_habitable:
            break
        best = None
        for i in range(len(rooms)):
            a = rooms[i]
            if getattr(a, 'role', '') in _protected:
                continue
            ax0, ax1, ay0, ay1 = a.bounds
            for j in range(i + 1, len(rooms)):
                b = rooms[j]
                if getattr(b, 'role', '') in _protected:
                    continue
                bx0, bx1, by0, by1 = b.bounds
                shared = 0.0
                vertical = None
                if abs(ax1 - bx0) < 0.14 or abs(bx1 - ax0) < 0.14:
                    shared = min(ay1, by1) - max(ay0, by0)
                    vertical = True
                elif abs(ay1 - by0) < 0.14 or abs(by1 - ay0) < 0.14:
                    shared = min(ax1, bx1) - max(ax0, bx0)
                    vertical = False
                if shared < 1.0:
                    continue
                score = (a.bounds[1] - a.bounds[0]) * (a.bounds[3] - a.bounds[2]) + \
                        (b.bounds[1] - b.bounds[0]) * (b.bounds[3] - b.bounds[2])
                if best is None or score < best[0]:
                    best = (score, i, j, vertical)
        if best is None:
            break
        _, i, j, vertical = best
        a, b = rooms[i], rooms[j]
        ax0, ax1, ay0, ay1 = a.bounds
        bx0, bx1, by0, by1 = b.bounds
        # Remove the shared wall.
        if vertical:
            bx = ax1 if abs(ax1 - bx0) < 0.14 else ax0
            ylo, yhi = max(ay0, by0), min(ay1, by1)
            new_walls = []
            for w in walls:
                if w.get('axis') == 'Y' and abs(w.get('pos', w['p1'][0]) - bx) < 0.16:
                    lo = min(w['p1'][1], w['p2'][1]); hi = max(w['p1'][1], w['p2'][1])
                    if hi > ylo + 0.1 and lo < yhi - 0.1:
                        continue
                new_walls.append(w)
            walls[:] = new_walls
        else:
            by = ay1 if abs(ay1 - by0) < 0.14 else ay0
            xlo, xhi = max(ax0, bx0), min(ax1, bx1)
            new_walls = []
            for w in walls:
                if w.get('axis') == 'X' and abs(w.get('pos', w['p1'][1]) - by) < 0.16:
                    lo = min(w['p1'][0], w['p2'][0]); hi = max(w['p1'][0], w['p2'][0])
                    if hi > xlo + 0.1 and lo < xhi - 0.1:
                        continue
                new_walls.append(w)
            walls[:] = new_walls
        # Keep the larger room's role, union the footprints and doors.
        if (a.bounds[1] - a.bounds[0]) * (a.bounds[3] - a.bounds[2]) < \
                (b.bounds[1] - b.bounds[0]) * (b.bounds[3] - b.bounds[2]):
            a, b = b, a
        a.bounds = (min(ax0, bx0), max(ax1, bx1), min(ay0, by0), max(ay1, by1))
        a.doorways = list(a.doorways or [])
        for d in (b.doorways or []):
            if d not in a.doorways:
                a.doorways.append(d)
        if a.stair_hole is None:
            a.stair_hole = b.stair_hole
        a.allow_large = True
        rooms.remove(b)
    return rooms


def _extend_wall_ends_to_bounds(interior_walls, bounds, snap=1.10):
    """Snap near-bound partition ends onto the wall line.

    A partition that stops a few decimetres short of an exterior wall reads as
    a wall ending abruptly and leaves a gap; pull such ends flush.
    """
    x0, x1, y0, y1 = bounds
    for w in interior_walls:
        p1, p2 = list(w.get('p1', (0.0, 0.0))), list(w.get('p2', (0.0, 0.0)))
        if abs(p1[0] - p2[0]) < 1e-6:          # vertical wall at x
            if x0 + 0.05 < p1[0] < x1 - 0.05:
                for pt in (p1, p2):
                    if 0.05 < pt[1] - y0 <= snap:
                        pt[1] = y0
                    elif 0.05 < y1 - pt[1] <= snap:
                        pt[1] = y1
        elif abs(p1[1] - p2[1]) < 1e-6:        # horizontal wall at y
            if y0 + 0.05 < p1[1] < y1 - 0.05:
                for pt in (p1, p2):
                    if 0.05 < pt[0] - x0 <= snap:
                        pt[0] = x0
                    elif 0.05 < x1 - pt[0] <= snap:
                        pt[0] = x1
        w['p1'], w['p2'] = tuple(p1), tuple(p2)


def _recut_oversized_rooms(rooms, interior_walls, bounds, wall_t, dw_w, dw_h,
                           archetype, fl_idx, has_stairs_landing, total_floors, program,
                           clear_zone_rects=None):
    """Give every room room-like proportions.

    * Thin strips (aspect >= 2.0) become CORRIDOR when they already serve as
      circulation, otherwise they are split into squarish rooms.
    * Oversized private-purpose rooms are split across the short axis into
      proportioned chambers; named social/ceremonial rooms keep their intended scale.
    """
    if not rooms:
        return rooms
    ix_min, ix_max, iy_min, iy_max = bounds
    out = []
    for room in rooms:
        b = room.bounds
        w, d = b[1] - b[0], b[3] - b[2]
        if room.role in THROUGH_ROLES or w <= 0.01 or d <= 0.01:
            out.append(room)
            continue
        # A warehouse/lumber-yard wing is already one purpose-built storage bay.
        # Re-cutting its 4.2 x 8.5 m footprint produced two narrow rooms and a
        # partition right beside the cargo-port portal; keep it whole.
        if getattr(room, 'is_wing', False) and archetype in ('WAREHOUSE', 'LUMBERMILL', 'BUILDER'):
            out.append(room)
            continue
        # Rooms explicitly protected from re-cutting (hallway-planned rooms with
        # their own corridor doors) must never be split here: splitting would
        # drop their circulation doorway and make them unreachable.
        if bool(getattr(room, 'allow_large', False)):
            out.append(room)
            continue
        aspect = max(w, d) / min(w, d)
        long_side = max(w, d)

        # Named ceremonial/social spaces may be large; private-purpose rooms may not.
        # Artisan trade halls and their shop/store are single purposeful rooms:
        # keep them whole and keep their role (never re-cut into storerooms).
        _large_intended = (room.role in {
            'THRONE_ROOM', 'BANQUET_HALL', 'TAVERN_TAPROOM', 'GREAT_HALL',
            'MEZZANINE_GALLERY', 'MESS_HALL', 'COUNCIL_CHAMBER', 'CHAPEL_HALL',
            'STABLE_HALL', 'WORKSHOP', 'STONE_STORE', 'LODGE', 'RANGE',
            'BAKEHOUSE', 'JOINERY', 'TAILOR_ATELIER', 'BREWHOUSE', 'BUTCHERY',
            'GOLDSMITH', 'FISHERY', 'SMITHY', 'FLETCHER_WORKSHOP', 'STORE',
        }) or bool(getattr(room, 'allow_large', False))
        if _large_intended and aspect < 2.5:
            out.append(room)
            continue
        # A thin strip that is already a passage: name it one.
        if aspect >= 2.0 and room.role in ('ENTRANCE_HALL', 'STORAGE') and long_side >= 6.0:
            room.role = 'CORRIDOR'
            out.append(room)
            continue

        _big = (not _large_intended and w * d > 52.0 and min(w, d) > 4.2)
        _strip = aspect >= (2.0 if _large_intended else 1.65) and long_side >= 5.5 and min(w, d) <= 4.5
        if not (_big or _strip):
            out.append(room)
            continue

        n_axis = 'X' if w >= d else 'Y'
        span = w if n_axis == 'X' else d
        n = max(2, min(3, int(round(span / max(5.0, (span * span) / (w * d) / 1.4)))))
        step = span / n
        if step < 3.0:
            n = max(1, int(span // 3.6))
            step = span / max(n, 1)
        if n < 2 or step < 3.0:
            out.append(room)
            continue

        # Avoid adding full-height walls that cross stairs or annex doorway aprons.
        _split_coords = ([b[0] + i * step for i in range(1, n)] if n_axis == 'X'
                         else [b[2] + i * step for i in range(1, n)])
        _crosses_clear_zone = False
        for _p in _split_coords:
            for _z in (clear_zone_rects or []):
                if n_axis == 'X':
                    _hit = (_z[0] - 0.05 <= _p <= _z[1] + 0.05
                            and not (b[3] <= _z[2] or b[2] >= _z[3]))
                else:
                    _hit = (_z[2] - 0.05 <= _p <= _z[3] + 0.05
                            and not (b[1] <= _z[0] or b[0] >= _z[1]))
                if _hit:
                    _crosses_clear_zone = True
                    break
            if _crosses_clear_zone:
                break
        if _crosses_clear_zone:
            out.append(room)
            continue

        # Never let a new partition bisect an existing doorway or portal (wing
        # and annex portals included).  Shift the split off the opening while
        # keeping both neighbouring rooms at least 2.4 m wide, so the piece
        # walls still meet the corridor/exterior walls instead of stopping in
        # the middle of a doorway.
        _door_axis = 'X' if n_axis == 'X' else 'Y'
        _door_spans = []
        for _d in (room.doorways or []):
            if _d.get('axis') == _door_axis:
                _dc = float(_d.get('x', 0.0)) if _door_axis == 'X' else float(_d.get('y', 0.0))
                _dw = float(_d.get('w', 1.2) or 1.2)
                _door_spans.append((_dc - _dw * 0.5 - 0.35, _dc + _dw * 0.5 + 0.35))
        if _door_spans and _split_coords:
            _lo_b = b[0] if n_axis == 'X' else b[2]
            _hi_b = b[1] if n_axis == 'X' else b[3]
            _fixed_coords = []
            _prev = _lo_b
            for _p in _split_coords:
                for _s0, _s1 in _door_spans:
                    if _s0 - 1e-6 <= _p <= _s1 + 1e-6:
                        _cands = [c for c in (_s0, _s1)
                                  if c - _prev >= 2.4 and _hi_b - c >= 2.4]
                        if _cands:
                            _p = min(_cands, key=lambda c: abs(c - _p))
                        break
                _fixed_coords.append(_p)
                _prev = _p
            _split_coords = _fixed_coords

        _edges = ([b[0]] + list(_split_coords) + [b[1]] if n_axis == 'X'
                  else [b[2]] + list(_split_coords) + [b[3]])

        # Companion roles keep the floor legible (shop -> store, bed -> study).
        _extra = _resolve_room_roles(archetype, fl_idx, len(rooms) + n - 1,
                                     has_stairs_landing, total_floors, program=program)
        _internal = []
        for i in range(n - 1):
            if n_axis == 'X':
                px = _edges[i + 1]
                _dd = {'x': px, 'y': (b[2] + b[3]) * 0.5, 'axis': 'Y', 'w': dw_w}
                interior_walls.append({
                    'p1': (px, b[2]), 'p2': (px, b[3]),
                    'axis': 'Y', 'pos': px, 'thickness': wall_t,
                    'doorway': dict(_dd, h=dw_h),
                })
            else:
                py = _edges[i + 1]
                _dd = {'x': (b[0] + b[1]) * 0.5, 'y': py, 'axis': 'X', 'w': dw_w}
                interior_walls.append({
                    'p1': (b[0], py), 'p2': (b[1], py),
                    'axis': 'X', 'pos': py, 'thickness': wall_t,
                    'doorway': dict(_dd, h=dw_h),
                })
            _internal.append((i, i + 1, _dd))

        for i in range(n):
            if n_axis == 'X':
                nb = (_edges[i], _edges[i + 1], b[2], b[3])
            else:
                nb = (b[0], b[1], _edges[i], _edges[i + 1])
            _role = room.role if i == 0 else _secondary_role(room.role, i)
            if i > 0 and _extra and i < len(_extra) and _extra[i] != room.role:
                _role = _extra[i]
            # Keep every entrance/portal that lies on this piece's boundary.
            _piece_doors = []
            for _ii, _jj, _dd in _internal:
                if _ii == i or _jj == i:
                    _piece_doors.append(dict(_dd))
            for _d in (room.doorways or []):
                _dx = float(_d.get('x', 1e9))
                _dy = float(_d.get('y', 1e9))
                if not (nb[0] - 0.30 <= _dx <= nb[1] + 0.30
                        and nb[2] - 0.30 <= _dy <= nb[3] + 0.30):
                    continue
                _on_edge = (abs(_dx - nb[0]) < 0.35 or abs(_dx - nb[1]) < 0.35
                            or abs(_dy - nb[2]) < 0.35 or abs(_dy - nb[3]) < 0.35)
                if not _on_edge:
                    continue
                if any(abs(_pd.get('x', -1e9) - _dx) < 0.01
                       and abs(_pd.get('y', -1e9) - _dy) < 0.01
                       and _pd.get('axis') == _d.get('axis') for _pd in _piece_doors):
                    continue
                _piece_doors.append(dict(_d))
            out.append(Room(
                id=f"{room.id}_{i + 1}", floor_idx=room.floor_idx, role=_role,
                bounds=nb, doorways=_piece_doors, stair_hole=room.stair_hole,
                is_wing=bool(getattr(room, 'is_wing', False)),
                wing_id=room.wing_id,
                exterior_facades=dict(room.exterior_facades),
                allow_large=_large_intended))
    return out


def _carve_corridor_rooms(rooms, interior_walls, bounds, wall_t, dw_w, dw_h):
    """Re-cut any corridor-thin room into chunky rooms joined by a corridor.

    Called after a floor has been partitioned. A room whose rectangle is a long
    strip (very wide and shallow, or tall and thin) is split across its short
    axis into 2+ squarish rooms, each reachable through a real doorway. Rooms
    stay compact; corridors are what get to be long.

    Returns the new room list; ``interior_walls`` is extended in place.
    """
    if not rooms:
        return rooms
    out = []
    for room in rooms:
        b = room.bounds
        w, d = b[1] - b[0], b[3] - b[2]
        if room.role in THROUGH_ROLES or w <= 0.01 or d <= 0.01:
            out.append(room)
            continue

        aspect = max(w, d) / min(w, d)
        _large_intended = bool(getattr(room, 'allow_large', False)) or room.role in {
            'THRONE_ROOM', 'BANQUET_HALL', 'TAVERN_TAPROOM', 'GREAT_HALL',
            'MEZZANINE_GALLERY', 'MESS_HALL', 'COUNCIL_CHAMBER', 'CHAPEL_HALL',
            'STABLE_HALL', 'WORKSHOP', 'STONE_STORE', 'LODGE', 'RANGE',
        }
        # Rescue elongated rooms, while allowing genuinely large social spaces.
        if aspect < (1.75 if _large_intended else 1.55) or max(w, d) < 5.5:
            out.append(room)
            continue
        if w >= d:
            # Long along X: split into near-square pieces (n ~ aspect).
            n = max(2, min(4, int(round(aspect))))
            step = w / n
            if step < 2.6 or step > 4.6:
                n = max(2, min(4, int(round(w / 4.0))))
                step = w / n
            if step < 2.6:
                out.append(room)
                continue
            for i in range(1, n):
                px = b[0] + i * step
                dy = (b[2] + b[3]) * 0.5
                interior_walls.append({
                    'p1': (px, b[2]), 'p2': (px, b[3]),
                    'axis': 'Y', 'pos': px, 'thickness': wall_t,
                    'doorway': {'x': px, 'y': dy, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
                })
            for i in range(n):
                x0, x1 = b[0] + i * step, b[0] + (i + 1) * step
                door_px = b[0] + (i + 1) * step if i < n - 1 else b[0] + i * step
                out.append(Room(
                    id=f"{room.id}_{i + 1}", floor_idx=room.floor_idx,
                    role=(room.role if i == 0 else _secondary_role(room.role, i)),
                    bounds=(x0, x1, b[2], b[3]),
                    doorways=[{'x': door_px, 'y': (b[2] + b[3]) * 0.5,
                               'axis': 'Y', 'w': dw_w}],
                    stair_hole=room.stair_hole,
                    is_wing=room.is_wing, wing_id=room.wing_id,
                    exterior_facades=dict(room.exterior_facades),
                    allow_large=_large_intended))
        else:
            n = max(2, min(4, int(round(aspect))))
            step = d / n
            if step < 2.6 or step > 4.6:
                n = max(2, min(4, int(round(d / 4.0))))
                step = d / n
            if step < 2.6:
                out.append(room)
                continue
            for i in range(1, n):
                py = b[2] + i * step
                dx = (b[0] + b[1]) * 0.5
                interior_walls.append({
                    'p1': (b[0], py), 'p2': (b[1], py),
                    'axis': 'X', 'pos': py, 'thickness': wall_t,
                    'doorway': {'x': dx, 'y': py, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
                })
            for i in range(n):
                y0, y1 = b[2] + i * step, b[2] + (i + 1) * step
                door_py = b[2] + (i + 1) * step if i < n - 1 else b[2] + i * step
                out.append(Room(
                    id=f"{room.id}_{i + 1}", floor_idx=room.floor_idx,
                    role=(room.role if i == 0 else _secondary_role(room.role, i)),
                    bounds=(b[0], b[1], y0, y1),
                    doorways=[{'x': (b[0] + b[1]) * 0.5, 'y': door_py,
                               'axis': 'X', 'w': dw_w}],
                    stair_hole=room.stair_hole,
                    is_wing=room.is_wing, wing_id=room.wing_id,
                    exterior_facades=dict(room.exterior_facades),
                    allow_large=_large_intended))
    return out


def plan_floor_rooms(fl_idx, bounds, stair_hole=None, stair_pos_info=None,
                     front_door_info=None, fl_wings_bounds=None,
                     effective_archetype='NONE', props=None, seed=0,
                     doorways=None, clear_zone_rects=None, noble_void=None):
    """
    Intelligently partitions a floor storey into rooms with open cased doorways.
    Returns:
        rooms: List[Room]
        interior_walls: List[Dict[str, Any]]
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min

    has_interior_walls = bool(getattr(props, 'has_interior_walls', True))
    partition_style = getattr(props, 'interior_partition_style', 'AUTO')
    wall_t = float(getattr(props, 'interior_wall_thickness', 0.16))
    floor_h = float(getattr(props, 'floor_height', 3.6))
    total_floors = int(getattr(props, 'num_floors', 1))
    shape = getattr(props, 'building_shape', 'RECTANGLE')
    program = getattr(props, 'interior_program', 'AUTO')
    has_stairs_landing = (fl_idx > 0 and stair_hole is not None)
    stair_zone = stair_circulation_zone(stair_hole, stair_pos_info, bounds)
    if stair_zone is not None:
        clear_zone_rects = list(clear_zone_rects or [])
        if stair_zone not in clear_zone_rects:
            clear_zone_rects.append(stair_zone)

    dw_w = 1.75
    dw_h = min(2.95, floor_h - 0.25)

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.30
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

    if bool(getattr(props, 'noble_manor_layout', False)) and has_interior_walls \
            and W >= 22.0 and D >= 12.0:
        _noble = _plan_noble_manor_rooms(
            fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
            has_stairs_landing, stair_pos_info=stair_pos_info,
            extra_doorways=doorways, props=props,
            fl_wings_bounds=fl_wings_bounds, noble_void=noble_void)
        if _noble is not None:
            _n_rooms, _n_walls = _noble
            _n_rooms = _recut_oversized_rooms(
                _n_rooms, _n_walls, bounds, wall_t, dw_w, dw_h,
                effective_archetype, fl_idx, has_stairs_landing, total_floors,
                program, clear_zone_rects=clear_zone_rects)
            # The corridor plan already isolates the stair hall; the generic
            # "rename rooms touched by the stair keep-out" pass mis-reads the
            # wing cellar shaft as a floor-wide keep-out and turns every
            # service/chamber room into a corridor, so it is deliberately
            # skipped here.
            return _n_rooms, _n_walls

    if bool(getattr(props, 'has_throne_room', False)) and has_interior_walls and W >= 13.0 and D >= 5.5:
        _palace = _plan_throne_palace_rooms(
            fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
            has_stairs_landing, stair_pos_info=stair_pos_info,
            extra_doorways=doorways, props=props
        )
        if _palace is not None:
            _p_rooms, _p_walls = _palace
            if fl_wings_bounds:
                for wi, wb in enumerate(fl_wings_bounds):
                    if fl_idx == 0:
                        w_role = 'ENTRANCE_HALL' if wi == 0 else 'BANQUET_HALL'
                    elif fl_idx == 1:
                        w_role = 'ARMORY' if wi == 0 else 'LIBRARY'
                    elif fl_idx == 2:
                        w_role = 'BEDROOM' if wi == 0 else 'GUEST_ROOM'
                    else:
                        w_role = 'STUDY' if wi == 0 else 'GUEST_ROOM'
                    wing_dw = []
                    dw_wx = (wb[0] + wb[1]) * 0.5
                    dw_w_eff = dw_w
                    if bool(getattr(props, 'has_throne_room', False)) and wb[2] >= iy_max - 0.30:
                        dw_w_eff = min(dw_w, 1.30)
                        dw_wx = max(wb[0] + dw_w_eff * 0.5 + 0.35, min(-2.20 - dw_w_eff * 0.5, (wb[0] + wb[1]) * 0.5 - 3.00))
                    if wb[3] <= iy_min + 0.30:
                        wing_dw.append({'x': dw_wx, 'y': iy_min, 'axis': 'X', 'w': dw_w_eff})
                    elif wb[2] >= iy_max - 0.30:
                        wing_dw.append({'x': dw_wx, 'y': iy_max, 'axis': 'X', 'w': dw_w_eff})
                        for r in _p_rooms:
                            if getattr(r, 'role', '') == 'THRONE_ROOM':
                                if not any(abs(d.get('x', 0) - dw_wx) < 0.2 and abs(d.get('y', 0) - iy_max) < 0.2 for d in r.doorways):
                                    r.doorways.append({'x': dw_wx, 'y': iy_max, 'axis': 'X', 'w': dw_w_eff})
                    _w_sh = None
                    if stair_hole is not None:
                        if not (stair_hole[1] < wb[0] or stair_hole[0] > wb[1]
                                or stair_hole[3] < wb[2] or stair_hole[2] > wb[3]):
                            _w_sh = stair_hole
                    _p_rooms.append(Room(
                        id=f"fl{fl_idx}_wing{wi}", floor_idx=fl_idx,
                        role=w_role, bounds=wb, is_wing=True, wing_id=wi,
                        doorways=wing_dw, stair_hole=_w_sh, exterior_facades={}))
            _p_rooms = _recut_oversized_rooms(
                _p_rooms, _p_walls, bounds, wall_t, dw_w, dw_h,
                effective_archetype, fl_idx, has_stairs_landing, total_floors, program,
                clear_zone_rects=clear_zone_rects)
            _p_rooms = _normalize_stair_circulation_rooms(
                _p_rooms, stair_hole, stair_pos_info, bounds)
            return _p_rooms, _p_walls

    is_wide_mansion = (W >= 22.0 and D >= 7.0
                       and effective_archetype in ('NONE', 'HOUSE', 'AUTO', 'MANOR')
                       and not getattr(props, 'has_throne_room', False)
                       and not getattr(props, 'has_double_height', False))
    # A building with an "open ground floor" keeps its ground storey as one
    # grand hall (banquet hall, great hall) and only partitions the floors
    # above it into proper chambers.
    _open_ground = (fl_idx == 0 and bool(getattr(props, 'open_ground_floor', False)))
    if (effective_archetype == 'MANOR' or is_wide_mansion) and has_interior_walls \
            and partition_style in ('AUTO', 'HALL_CHAMBERS') and not _open_ground:
        _manor = _plan_manor_rooms(fl_idx, bounds, stair_hole, wall_t,
                                   dw_w, dw_h, has_stairs_landing,
                                   stair_pos_info=stair_pos_info,
                                   extra_doorways=doorways,
                                   props=props,
                                   fl_wings_bounds=fl_wings_bounds)
        if _manor is not None:
            _manor_rooms, _manor_walls = _manor
            if fl_wings_bounds:
                for wi, wb in enumerate(fl_wings_bounds):
                    if fl_idx == 0:
                        w_role = 'ENTRANCE_HALL' if wi == 0 else 'BANQUET_HALL'
                    elif fl_idx == 1:
                        w_role = 'ARMORY' if wi == 0 else 'LIBRARY'
                    elif fl_idx == 2:
                        w_role = 'STUDY' if wi == 0 else 'GUEST_ROOM'
                    else:
                        w_role = 'BEDROOM' if wi == 0 else 'GUEST_ROOM'
                    wing_dw = []
                    dw_wx = (wb[0] + wb[1]) * 0.5
                    if wb[3] <= iy_min + 0.30:
                        wing_dw.append({'x': dw_wx, 'y': iy_min, 'axis': 'X', 'w': dw_w})
                    elif wb[2] >= iy_max - 0.30:
                        wing_dw.append({'x': dw_wx, 'y': iy_max, 'axis': 'X', 'w': dw_w})
                    _manor_rooms.append(Room(
                        id=f"fl{fl_idx}_wing{wi}", floor_idx=fl_idx,
                        role=w_role, bounds=wb, is_wing=True, wing_id=wi,
                        doorways=wing_dw, stair_hole=None, exterior_facades={}))
            _manor_rooms = _recut_oversized_rooms(
                _manor_rooms, _manor_walls, bounds, wall_t, dw_w, dw_h,
                effective_archetype, fl_idx, has_stairs_landing, total_floors, program,
                clear_zone_rects=clear_zone_rects)
            _manor_rooms = _normalize_stair_circulation_rooms(
                _manor_rooms, stair_hole, stair_pos_info, bounds)
            return _manor_rooms, _manor_walls

    # Single open room fallback (only when explicitly requested, plot is tiny
    # < 4.2m, or the archetype is an open industrial hall such as a lumbermill
    # whose equipment fills the floor).
    _turn_layout = (getattr(props, 'stair_style', 'STRAIGHT') == 'TURN')
    loom_open = (effective_archetype in ('LUMBERMILL', 'QUARRY'))
    # Working stable barns stay one open hall (stall rows + hay storage),
    # never partitioned into bedrooms.
    stable_open = (effective_archetype == 'STABLE')

    # Detect floors too small to divide into separate rooms:
    # 1. Turned-stair floors with D < 13.0 or W < 8.0 (flights wrap around multiple walls)
    # 2. Upper floors with W < 7.5 and D < 7.5 (dividing leaves cramped rooms < 3.2m)
    # 3. Small artisan live/work buildings (Fisherman, Hunter, etc. with W < 9.0 and D < 9.0)
    # 4. Explicit partition_style in ('OPEN', 'ONE_ROOM') or not has_interior_walls
    _too_small_to_divide = False
    if fl_idx > 0:
        if _turn_layout and (D < 13.0 or W < 8.0):
            _too_small_to_divide = True
        elif W < 7.5 and D < 7.5:
            _too_small_to_divide = True
        elif effective_archetype in ('FISHERMAN', 'HUNTER') and (W < 9.0 and D < 9.0):
            _too_small_to_divide = True

    if not has_interior_walls or partition_style in ('OPEN', 'ONE_ROOM') or (W < 4.2 and D < 4.2) or loom_open or stable_open \
            or _too_small_to_divide \
            or (fl_idx == 0 and bool(getattr(props, 'open_ground_floor', False))):
        if effective_archetype == 'QUARRY':
            roles = ['STONE_STORE']
        elif effective_archetype == 'LUMBERMILL':
            roles = ['WORKSHOP' if fl_idx == 0 else 'STORAGE']
        elif effective_archetype == 'STABLE':
            roles = ['STABLE_HALL']
        elif fl_idx > 0 and _too_small_to_divide and effective_archetype not in ('WAREHOUSE', 'BUILDER'):
            # Combined living area on upper floors: bedroom and kitchen get highest priority!
            roles = ['COTTAGE']
        else:
            roles = _resolve_room_roles(effective_archetype, fl_idx, 1, has_stairs_landing, total_floors, program=program)
        main_room = Room(
            id=f"fl{fl_idx}_living" if (fl_idx > 0 and roles[0] == 'COTTAGE') else f"fl{fl_idx}_main",
            floor_idx=fl_idx,
            role=roles[0],
            bounds=(ix_min, ix_max, iy_min, iy_max),
            doorways=[],
            stair_hole=stair_hole,
            exterior_facades={
                'FRONT': (ix_min, ix_max),
                'BACK': (ix_min, ix_max),
                'LEFT': (iy_min, iy_max),
                'RIGHT': (iy_min, iy_max),
            }
        )
        rooms = [main_room]
        # Attach any wing rooms
        if fl_wings_bounds:
            for wi, wb in enumerate(fl_wings_bounds):
                if effective_archetype in ('TAVERN', 'INN'):
                    # The kitchen lives in the ground-floor wing, leaving the
                    # whole main block free for one big taproom.  Upstairs the
                    # wing becomes guest lodging instead of another dining room.
                    _inn_roles = _resolve_room_roles(
                        effective_archetype, fl_idx, 2, fl_idx > 0, total_floors,
                        program=program)
                    # _inn_roles[1] is KITCHEN on the ground floor (service wing)
                    # and GUEST_ROOM above; _inn_roles[0] is TAPROOM/stair-landing
                    # which belongs in the main block, not the wing.
                    w_role = _inn_roles[1] if len(_inn_roles) > 1 else (
                        'GUEST_ROOM' if fl_idx > 0 else 'KITCHEN')
                    w_doorways = _wing_portals(wb, doorways)
                elif effective_archetype == 'TENEMENT':
                    # In U-shape tenements, each wing is an independent apartment with its own entrance.
                    # In other shapes, it is an extra bedroom connected via portal.
                    w_role = 'TENEMENT_KITCHEN' if shape == 'U_SHAPE' else 'TENEMENT_BEDROOM'
                    if shape == 'U_SHAPE':
                        wx1, wx2, wy1, wy2 = wb
                        door_x = wx2 if wi == 0 else wx1
                        door_y = (wy1 + max(2.2, (wy2 - wy1) * 0.22)
                                  if fl_idx == 0 else wy2 - 0.96)
                        w_doorways = [{'x': door_x, 'y': door_y, 'axis': 'Y', 'w': 1.10}]
                    else:
                        w_doorways = _wing_portals(wb, doorways)
                elif effective_archetype == 'MANOR':
                    w_role = 'STUDY' if (fl_idx == 0 and wi == 0) else ('GUEST_ROOM' if fl_idx == 0 else ('BEDROOM' if wi == 0 else 'GUEST_ROOM'))
                    w_doorways = _wing_portals(wb, doorways)
                elif effective_archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
                    w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'MAYOR_OFFICE'
                    w_doorways = _wing_portals(wb, doorways)
                elif effective_archetype in ('KNIGHTS_MANOR',):
                    w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'BARRACKS_DORM'
                    w_doorways = _wing_portals(wb, doorways)
                elif effective_archetype in ('BARRACKS', 'INFANTRY_BARRACKS',
                                             'ARCHERY', 'ARCHERY_RANGE'):
                    w_role = 'ENTRANCE_HALL' if (fl_idx == 0 and wi == 0 and getattr(props, 'wing_placement', '') == 'FRONT') else 'BARRACKS_DORM'
                    w_doorways = _wing_portals(wb, doorways)
                else:
                    # Artisan courtyard wings are working trade space on the
                    # ground floor (forge wing, brew wing, ...), bedrooms above.
                    _craft_wing = {'BLACKSMITH': 'SMITHY', 'TOOLSMITH': 'SMITHY',
                                   'BREWERY': 'BREWHOUSE', 'BAKERY': 'BAKEHOUSE',
                                   'BUTCHER': 'BUTCHERY', 'FISHERMAN': 'FISHERY',
                                   'TAILOR': 'TAILOR_ATELIER', 'JEWELER': 'GOLDSMITH',
                                   'FURNITURE_MAKER': 'JOINERY'}.get(effective_archetype)
                    if fl_idx == 0 and _craft_wing:
                        w_role = _craft_wing
                    else:
                        w_role = 'STORAGE' if (fl_idx == 0 or effective_archetype in
                                           ('WAREHOUSE', 'LUMBERMILL', 'BLACKSMITH', 'BUILDER')) else 'GUEST_ROOM'
                    w_doorways = _wing_portals(wb, doorways)
                w_rm = Room(
                    id=f"fl{fl_idx}_wing{wi}",
                    floor_idx=fl_idx,
                    role=w_role,
                    bounds=wb,
                    is_wing=True,
                    wing_id=wi,
                    doorways=w_doorways,
                    stair_hole=_holds_stair(wb),
                    exterior_facades={}
                )
                rooms.append(w_rm)
        rooms = _normalize_stair_circulation_rooms(rooms, stair_hole, stair_pos_info, bounds)
        return rooms, []

    # Safe boundaries around stairs (left side)
    stair_switchback = bool((stair_pos_info or {}).get('switchback', False))
    walk_w = float((stair_pos_info or {}).get('walk_w', 1.85) or 1.85)
    if stair_pos_info:
        stair_safe_x = stair_pos_info.get('cx', ix_min + 1.4) + stair_pos_info.get('w', 1.2) * 0.5 + 0.20
        stair_safe_y_bot = min(iy_max - 3.4, stair_pos_info.get('y_bot', iy_max - 3.4))
        stair_safe_y_top = max(iy_min + 3.4, stair_pos_info.get('y_top', iy_min + 3.4))
        stair_guards_north = float(stair_pos_info.get('y_ascend', 1.0) or 1.0) > 0.0
    else:
        stair_safe_x = ix_min + 1.8
        stair_safe_y_bot = iy_max - 3.4
        stair_safe_y_top = iy_min + 3.4
        stair_guards_north = True

    door_cx = front_door_info[0] if (front_door_info and fl_idx == 0) else None

    # Bakery hearth oven: fixed slot at depth-centre against the +X wall
    # (glazing keeps clear of it in floors.py; geometry in accessories/bakery.py).
    # Cross-partitions must never slice through the masonry, and the flue
    # rises through the same slot on every storey, so each bakery floor keeps
    # this band free: the oven always stands whole inside one bakehouse chamber.
    oven_band = None
    if effective_archetype == 'BAKERY' and has_interior_walls \
            and partition_style in ('AUTO', 'HALL_CHAMBERS') and D >= 7.0:
        from .accessories.bakery import OVEN_WALL_CLEAR
        # The bake-oven lives in the rear bakehouse, not at the mid-depth stair
        # (where the flue/footprint used to collide with the flight).
        _oven_y = iy_min + D * 0.72
        oven_band = (_oven_y - OVEN_WALL_CLEAR, _oven_y + OVEN_WALL_CLEAR)

    def _dodge_oven_band(pos, lo, hi):
        if oven_band is None:
            return pos
        b0, b1 = oven_band
        if b0 <= pos <= b1:
            pos = b0 if (pos - b0) <= (b1 - pos) else b1
        return min(hi, max(lo, pos))

    def _force_bakehouse_chamber(room_list):
        """The chamber holding the oven masonry serves as the bakehouse."""
        if oven_band is None or len(room_list) <= 2:
            # Two-room floors keep street order (shop stays at the street);
            # the masonry keep-out still protects props either way.
            return
        oy = (oven_band[0] + oven_band[1]) * 0.5
        holder = None
        for ox0, ox1 in ((ix_max - 1.50, ix_max - 0.05),
                         (ix_min + 0.05, ix_min + 1.50)):
            for r in room_list:
                if getattr(r, 'is_wing', False):
                    continue
                x0, x1, y0, y1 = r.bounds
                if x0 <= ox0 and ox1 <= x1 and y0 <= oy <= y1:
                    holder = r
                    break
            if holder is not None:
                break
        if holder is None or holder.role == 'BAKEHOUSE':
            return
        for r in room_list:
            if r is not holder and r.role == 'BAKEHOUSE' \
                    and not getattr(r, 'is_wing', False):
                r.role, holder.role = holder.role, r.role
                return

    # Decide layout mode
    _turn_layout = (getattr(props, 'stair_style', 'STRAIGHT') == 'TURN')
    # A turned staircase takes a big corner column, so those floors use the
    # band (front-to-back) layout: the stair gets a full-width band and the
    # rooms wrap around it instead of being squeezed into a side strip.
    is_deep = ((D > W * 1.25 and D >= 6.5) or _turn_layout) \
        and effective_archetype != 'TENEMENT'
    can_3_rooms = (partition_style in ('AUTO', 'HALL_CHAMBERS')) and (W >= 10.5 and D >= 7.5)
    can_4_rooms = can_3_rooms and (W >= 13.5 and D >= 10.5)

    rooms = []
    interior_walls = []

    def _clear_doorway_span_base(pos, axis='X', margin=0.65, lo=None, hi=None):
        """Move partition coordinate `pos` off any doorway/wing-portal opening
        it would otherwise cross (a partition must never land in the middle of
        a doorway). The result stays within [lo, hi]; iterate to fixpoint so
        dodging one opening never lands inside another."""
        if axis == 'X':
            lo = ix_min + 1.8 if lo is None else lo
            hi = ix_max - 1.8 if hi is None else hi
            door_items = [(dw.get('x', 0.0), dw.get('w', 1.2),
                           0.30 if dw.get('is_balcony') else margin)
                          for dw in (doorways or []) if dw.get('axis', 'X') == 'X']
        else:
            lo = iy_min + 1.8 if lo is None else lo
            hi = iy_max - 1.8 if hi is None else hi
            door_items = [(dw.get('y', 0.0), dw.get('w', 1.2),
                           0.30 if dw.get('is_balcony') else margin)
                          for dw in (doorways or []) if dw.get('axis', 'X') == 'Y']
        spans = [(dc - dw * 0.5 - m, dc + dw * 0.5 + m, dc, dw)
                 for dc, dw, m in door_items]
        if hi < lo:
            hi = lo
        pos = min(hi, max(lo, pos))
        for _ in range(4):
            hit = False
            for s0, s1, dc, dw in spans:
                if s0 <= pos <= s1:
                    cands = [p for p in (s0, s1) if lo <= p <= hi]
                    if not cands:
                        # Fallback: if margin pushed past bounds, try tighter clearances
                        # (down to 0.18m from casing) so the wall never bisects the actual door opening
                        for tm in (0.35, 0.25, 0.18):
                            dh = dw * 0.5 + tm
                            tc = [p for p in (dc - dh, dc + dh) if lo <= p <= hi]
                            if tc:
                                cands = tc
                                break
                    if not cands:
                        cands = [lo if abs(lo - dc) > abs(hi - dc) else hi]
                    pos = min(cands, key=lambda p: abs(p - pos))
                    hit = True
            if not hit:
                break
        return min(hi, max(lo, pos))

    # Keep-outs that must stay physically empty: the stair well and the apron in
    # front of each annex walk-through.  Partitions are trimmed back to the edge
    # of any keep-out they would otherwise cross, so a staircase or a furniture
    # run never ends up standing in the way into a side annex.
    _clear_zones = [tuple(z) for z in (clear_zone_rects or []) if z is not None]
    # Zone-aware doorway dodging lives in `_clear_doorway_span` below.
    _ZONE_DEPTH = 0.35

    def _clear_doorway_span(pos, axis='X', margin=0.65, lo=None, hi=None):
        pos = _clear_doorway_span_base(pos, axis=axis, margin=margin, lo=lo, hi=hi)
        a0, a1 = (ix_min, ix_max) if axis == 'X' else (iy_min, iy_max)
        lo_ = lo if lo is not None else a0
        hi_ = hi if hi is not None else a1
        # Slide the coordinate out of any keep-out zone on this line.
        for zx0, zx1, zy0, zy1 in _clear_zones:
            z0, z1 = (zx0, zx1) if axis == 'X' else (zy0, zy1)
            if not (z0 - 1e-6 <= pos <= z1 + 1e-6):
                continue
            cands = [c for c in (z0 - margin - _ZONE_DEPTH, z1 + margin + _ZONE_DEPTH)
                     if lo_ <= c <= hi_]
            if cands:
                pos = min(cands, key=lambda c: abs(c - pos))
        return pos
        if (_n0, _n1) == (a0, a1):
            return pos
        # Coordinate sits inside a keep-out: slide to the nearer keep-out edge.
        for zx0, zx1, zy0, zy1 in _clear_zones:
            if axis == 'X' and not (zx0 - 1e-6 <= pos <= zx1 + 1e-6):
                continue
            if axis == 'Y' and not (zy0 - 1e-6 <= pos <= zy1 + 1e-6):
                continue
            z0, z1 = (zy0, zy1) if axis == 'X' else (zx0, zx1)
            lo_ = lo if lo is not None else a0
            hi_ = hi if hi is not None else a1
            cands = [c for c in (z0 - margin - 0.05, z1 + margin + 0.05) if lo_ <= c <= hi_]
            if cands:
                return min(cands, key=lambda c: abs(c - pos))
        return pos

    def _clip_to_zones(axis, pos, a0, a1, zones=None):
        """Trim a partition's span (a0..a1 along `axis`) back out of every zone.

        A zone only clips when it actually straddles the wall line (the wall
        passes through its interior). Zones that merely touch the wall line or
        its ends are ignored, so a partition is never shortened where it meets
        another wall or its own doorway - that used to leave dangling wall ends.
        """
        _zlist = _clear_zones if zones is None else zones
        for _ in range(3):
            changed = False
            for zx0, zx1, zy0, zy1 in _zlist:
                if axis == 'X':
                    # Horizontal wall at y = pos: the zone must straddle that y.
                    # Ignore walls that run along the zone edge (room/corridor
                    # boundaries): only a wall through the middle of the walkway
                    # actually blocks it.  The old 2 cm threshold clipped the
                    # corridor walls beside an annex door, leaving the room open
                    # at the corner.
                    if not (zy0 + 0.55 < pos < zy1 - 0.55):
                        continue
                    z0, z1 = zx0, zx1
                else:
                    # Vertical wall at x = pos: same rule along X.
                    if not (zx0 + 0.55 < pos < zx1 - 0.55):
                        continue
                    z0, z1 = zy0, zy1
                if a1 <= z0 + 1e-6 or a0 >= z1 - 1e-6:
                    continue
                # A keep-out that reaches either end of the wall must not trim
                # that junction. Only interior openings clip.
                if z0 <= a0 + 1e-6 or z1 >= a1 - 1e-6:
                    continue
                # Keep the longer of the two remaining pieces.
                if (a1 - a0) <= 0.0:
                    break
                if (z0 - a0) >= (a1 - z1):
                    a1 = z0
                else:
                    a0 = z1
                changed = True
            if not changed:
                break
        return a0, a1

    def _blocked_by_zone(x, y, zx0z=None, zx1z=None, zy0z=None, zy1z=None):
        """True when the point, or an optional rect, overlaps any keep-out."""
        for zx0, zx1, zy0, zy1 in _clear_zones:
            if zx0z is None:
                if zx0 - 0.05 <= x <= zx1 + 0.05 and zy0 - 0.05 <= y <= zy1 + 0.05:
                    return True
            else:
                if not (zx1z + 0.05 <= zx0 or zx0z - 0.05 >= zx1
                        or zy1z + 0.05 <= zy0 or zy0z - 0.05 >= zy1):
                    return True
        return False

    def _push_split_out(axis, pos, lo, hi, x_min_, x_max_, y_min_, y_max_):
        """Slide a partition coordinate so its whole wall line stays out of zones.

        Returns the moved coordinate (or `pos`) and the x-range / y-range the
        partition may actually occupy.  Only partitions whose line genuinely
        crosses a keep-out are trimmed; clear partitions keep full span.
        """
        a0, a1 = (x_min_, x_max_) if axis == 'X' else (y_min_, y_max_)
        b0, b1 = _clip_to_zones(axis, pos, a0, a1)
        if (b0, b1) == (a0, a1):
            return pos, a0, a1
        # The line crosses a keep-out: step it to whichever side leaves the
        # longer usable wall, staying inside the requested [lo, hi] window.
        cands = []
        for zx0, zx1, zy0, zy1 in _clear_zones:
            if axis == 'X' and zx0 - 1e-6 <= pos <= zx1 + 1e-6:
                cands.extend((zy0 - 0.02, zy1 + 0.02))
            elif axis == 'Y' and zy0 - 1e-6 <= pos <= zy1 + 1e-6:
                cands.extend((zx0 - 0.02, zx1 + 0.02))
        cands = [c for c in cands if lo <= c <= hi]
        if not cands:
            return b0 if (b0 - a0) >= (a1 - b1) else b1, a0, a1
        pos = min(cands, key=lambda c: abs(c - pos))
        return pos, a0, a1

    if fl_idx == 0 and (effective_archetype in _ARTISAN_GROUND
                        or effective_archetype.startswith('ARTISAN')):
        # Artisan shop-house: one BIG trade room on the ground floor (the
        # workshop, with the shop kept inside it) plus an optional side store.
        # Two big squarish rooms read as a proper workshop; a stack of strips
        # read as a corridor with doors.
        _ground = _ARTISAN_GROUND.get(effective_archetype, ['WORKSHOP', 'STORE', 'STORAGE'])
        _shop, _store = _ground[0], (_ground[1] if len(_ground) > 1 else 'STORE')
        _split_like = None
        # The bakery must read as a real shop-house: the STORE/sales room at
        # the street entrance, the BAKEHOUSE (oven + stair) behind it.
        if effective_archetype == 'BAKERY' and D >= 9.0:
            _sy = iy_min + D * 0.30
            _sy = _clear_doorway_span(_sy, axis='Y', lo=iy_min + 3.4, hi=iy_max - 3.4)
            _sy = _dodge_oven_band(_sy, iy_min + 3.4, iy_max - 3.4)
            if _sy > iy_min + 3.4 and iy_max - _sy > 3.4:
                _split_like = ('X', _sy)
        # Cut so each half stays chunky: the workshop keeps the long dimension
        # (and the larger share), the store takes the street end.
        if _split_like is None and W >= D and W >= 9.0:
            _sx = ix_min + W * 0.58
            _sx = _clear_doorway_span(_sx, axis='X', lo=ix_min + 3.6, hi=ix_max - 3.6)
            if _sx > ix_min + 3.4 and ix_max - _sx > 3.4:
                _split_like = ('Y', _sx)
        elif _split_like is None and D >= 9.0:
            _sy = iy_min + D * 0.58
            _sy = _clear_doorway_span(_sy, axis='Y', lo=iy_min + 3.6, hi=iy_max - 3.6)
            _sy = _dodge_oven_band(_sy, iy_min + 3.6, iy_max - 3.6)
            if _sy > iy_min + 3.4 and iy_max - _sy > 3.4:
                _split_like = ('X', _sy)
        # Keep the artisan split wall out of the wing portal band so it never
        # bisects the doorway into the wing (a wall through the door frame).
        if _split_like is not None and fl_wings_bounds:
            _axis, _pos = _split_like
            for wb in fl_wings_bounds:
                _wx1, _wx2, _wy1, _wy2 = wb
                if _axis == 'Y':
                    _pw = min(2.2, max(1.2, (_wx2 - _wx1) - 1.2))
                    _p_lo = (_wx1 + _wx2) * 0.5 - _pw * 0.5 - 0.6
                    _p_hi = (_wx1 + _wx2) * 0.5 + _pw * 0.5 + 0.6
                    if _p_lo <= _pos <= _p_hi:
                        if _wx1 - 1.0 > ix_min + 2.0:
                            _pos = _wx1 - 1.0
                        elif _wx2 + 1.0 < ix_max - 2.0:
                            _pos = _wx2 + 1.0
                else:
                    _pw = min(2.2, max(1.2, (_wy2 - _wy1) - 1.2))
                    _p_lo = (_wy1 + _wy2) * 0.5 - _pw * 0.5 - 0.6
                    _p_hi = (_wy1 + _wy2) * 0.5 + _pw * 0.5 + 0.6
                    if _p_lo <= _pos <= _p_hi:
                        if _wy1 - 1.0 > iy_min + 2.0:
                            _pos = _wy1 - 1.0
                        elif _wy2 + 1.0 < iy_max - 2.0:
                            _pos = _wy2 + 1.0
            _split_like = (_axis, _pos)
        if _split_like is not None:
            _axis, _pos = _split_like
            if _axis == 'X':
                _dw_c = (ix_min + ix_max) * 0.5
                _dw_c = _clear_doorway_span(_dw_c, axis='X', lo=ix_min + 1.8, hi=ix_max - 1.8)
                interior_walls.append({
                    'p1': (ix_min, _pos), 'p2': (ix_max, _pos),
                    'axis': 'X', 'pos': _pos, 'thickness': wall_t,
                    'doorway': {'x': _dw_c, 'y': _pos, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
                })
                _a = (ix_min, ix_max, iy_min, _pos)
                _b = (ix_min, ix_max, _pos, iy_max)
                _fa = {'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, _pos), 'RIGHT': (iy_min, _pos)}
                _fb = {'BACK': (ix_min, ix_max), 'LEFT': (_pos, iy_max), 'RIGHT': (_pos, iy_max)}
                _doors = [{'x': _dw_c, 'y': _pos, 'axis': 'X', 'w': dw_w}]
            else:
                _dw_c = (iy_min + iy_max) * 0.5
                _dw_c = _clear_doorway_span(_dw_c, axis='Y', lo=iy_min + 1.8, hi=iy_max - 1.8)
                interior_walls.append({
                    'p1': (_pos, iy_min), 'p2': (_pos, iy_max),
                    'axis': 'Y', 'pos': _pos, 'thickness': wall_t,
                    'doorway': {'x': _pos, 'y': _dw_c, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
                })
                _a = (ix_min, _pos, iy_min, iy_max)
                _b = (_pos, ix_max, iy_min, iy_max)
                _fa = {'LEFT': (iy_min, iy_max), 'FRONT': (ix_min, _pos), 'BACK': (ix_min, _pos)}
                _fb = {'RIGHT': (iy_min, iy_max), 'FRONT': (_pos, ix_max), 'BACK': (_pos, ix_max)}
                _doors = [{'x': _pos, 'y': _dw_c, 'axis': 'Y', 'w': dw_w}]
            _a_area = (_a[1] - _a[0]) * (_a[3] - _a[2])
            _b_area = (_b[1] - _b[0]) * (_b[3] - _b[2])
            if _axis == 'X':
                # Front/back split: the shop (STORE) always faces the street;
                # the workshop takes the rear room.
                _store_b, _store_fac, _shop_b, _shop_fac = _a, _fa, _b, _fb
            else:
                # Side-by-side split: the room that actually contains the
                # street entrance is the shop; the other half is the workshop.
                _entry_x = None
                for _d in (doorways or []):
                    if (_d.get('axis') == 'X'
                            and abs(float(_d.get('y', 0.0)) - iy_min) < 0.60):
                        _entry_x = float(_d.get('x', 0.0))
                        break
                if _entry_x is not None and _a[0] <= _entry_x <= _a[1]:
                    _store_b, _store_fac, _shop_b, _shop_fac = _a, _fa, _b, _fb
                elif _entry_x is not None and _b[0] <= _entry_x <= _b[1]:
                    _store_b, _store_fac, _shop_b, _shop_fac = _b, _fb, _a, _fa
                elif _a_area >= _b_area:
                    _shop_b, _shop_fac, _store_b, _store_fac = _a, _fa, _b, _fb
                else:
                    _shop_b, _shop_fac, _store_b, _store_fac = _b, _fb, _a, _fa
            rooms = [
                Room(id=f"fl{fl_idx}_workshop", floor_idx=fl_idx, role=_shop,
                     bounds=_shop_b, doorways=list(_doors),
                     stair_hole=_holds_stair(_shop_b), exterior_facades=_shop_fac,
                     allow_large=True),
                Room(id=f"fl{fl_idx}_store", floor_idx=fl_idx, role=_store,
                     bounds=_store_b, doorways=list(_doors),
                     stair_hole=_holds_stair(_store_b), exterior_facades=_store_fac,
                     allow_large=True),
            ]
        else:
            # Small/odd footprint: one generous trade hall, no slivers.
            rooms = [Room(id=f"fl{fl_idx}_workshop", floor_idx=fl_idx, role=_shop,
                          bounds=(ix_min, ix_max, iy_min, iy_max), doorways=[],
                          stair_hole=stair_hole,
                          exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                                            'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)})]

    elif fl_idx == 0 and effective_archetype in ('INN', 'TAVERN') and fl_wings_bounds:
        # Inn with a service wing: the whole main block is ONE grand taproom
        # (long bar down one side, tables everywhere else) and the kitchen
        # moves out into the wing.  Peak nights need the floor, not a corridor
        # to a second dining room.
        rm0 = Room(
            id=f"fl{fl_idx}_taproom", floor_idx=fl_idx, role='TAVERN_TAPROOM',
            bounds=(ix_min, ix_max, iy_min, iy_max),
            doorways=[], stair_hole=stair_hole,
            exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                              'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)}
        )
        rooms = [rm0]
        # NOTE: wing rooms are added by the single common wing pass below
        # (~line 4953) so no duplicate taproom/kitchen wing can ever be created.

    elif fl_idx == 0 and effective_archetype in ('INN', 'TAVERN'):
        # Ground floor of Inn/Tavern without a wing: either one grand open
        # taproom (small footprints / open ground floor) or two spacious
        # rooms, a great taproom plus a service kitchen.
        if (W < 9.0 and D < 9.0) or bool(getattr(props, 'open_ground_floor', False)):
            rm0 = Room(
                id=f"fl{fl_idx}_taproom", floor_idx=fl_idx, role='TAVERN_TAPROOM',
                bounds=(ix_min, ix_max, iy_min, iy_max),
                doorways=[], stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                                  'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)}
            )
            rooms = [rm0]
        elif D > W * 1.10:
            # Deep tavern: front grand taproom (~68% depth) + rear service kitchen (~32% depth)
            split_y = iy_min + D * 0.68
            min_split_y = iy_min + 3.5
            if stair_guards_north:
                min_split_y = max(min_split_y, stair_safe_y_top + 0.65)
            if stair_hole is not None:
                min_split_y = max(min_split_y, stair_hole[3] + 1.00)
            split_y = max(min_split_y, split_y)
            split_y = min(iy_max - 2.5, max(iy_min + 3.5, split_y))
            split_y = _clear_doorway_span(split_y, axis='Y', lo=iy_min + 3.0, hi=iy_max - 2.2)

            dw_x = (ix_min + ix_max) * 0.5
            if abs(dw_x - (door_cx or 0.0)) < 0.4:
                dw_x += 0.85
            dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.8, hi=ix_max - 1.8)

            interior_walls.append({
                'p1': (ix_min, split_y), 'p2': (ix_max, split_y),
                'axis': 'X', 'pos': split_y, 'thickness': wall_t,
                'doorway': {'x': dw_x, 'y': split_y, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
            })
            rm0 = Room(
                id=f"fl{fl_idx}_taproom", floor_idx=fl_idx, role='TAVERN_TAPROOM',
                bounds=(ix_min, ix_max, iy_min, split_y),
                doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                stair_hole=_holds_stair((ix_min, ix_max, iy_min, split_y)),
                exterior_facades={'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, split_y), 'RIGHT': (iy_min, split_y)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_kitchen", floor_idx=fl_idx, role='KITCHEN',
                bounds=(ix_min, ix_max, split_y, iy_max),
                doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                stair_hole=_holds_stair((ix_min, ix_max, split_y, iy_max)),
                exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (split_y, iy_max), 'RIGHT': (split_y, iy_max)}
            )
            rooms = [rm0, rm1]
        else:
            # Wide tavern: grand taproom (~70% width) + service kitchen (~30% width)
            stair_on_right = bool(
                (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
                or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
            )
            if stair_on_right:
                stair_w = float((stair_pos_info or {}).get('w', 1.2) or 1.2)
                stair_cx = float((stair_pos_info or {}).get('cx', ix_max - 1.4) or (ix_max - 1.4))
                stair_safe_x_left = stair_cx - stair_w * 0.5 - 0.20
                max_split_x = stair_safe_x_left - 1.00
                if stair_hole is not None:
                    max_split_x = min(max_split_x, stair_hole[0] - 0.50)
                if door_cx is not None:
                    max_split_x = min(max_split_x, door_cx - 0.95)
                # Taproom ~64%, but the kitchen never a corridor (min 3.9 m).
                split_x = min(max_split_x, ix_max - max(W * 0.64, 3.9))
                split_x = max(ix_min + 4.0, split_x)
                split_x = _clear_doorway_span(split_x, axis='X', lo=ix_min + 2.2, hi=min(ix_max - 3.0, max_split_x))
                dw_y = (iy_min + iy_max) * 0.5
                dw_y = _clear_doorway_span(dw_y, axis='Y', lo=iy_min + 1.8, hi=iy_max - 1.8)
                interior_walls.append({
                    'p1': (split_x, iy_min), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
                rm0 = Room(
                    id=f"fl{fl_idx}_kitchen", floor_idx=fl_idx, role='KITCHEN',
                    bounds=(ix_min, split_x, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, split_x, iy_min, iy_max)),
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_taproom", floor_idx=fl_idx, role='TAVERN_TAPROOM',
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, iy_max)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'BACK': (split_x, ix_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0, rm1]
            else:
                min_split_x = stair_safe_x + 1.00
                if stair_hole is not None:
                    min_split_x = max(min_split_x, stair_hole[1] + 1.00)
                if door_cx is not None:
                    min_split_x = max(min_split_x, door_cx + 0.95)
                # Taproom ~64%, but the kitchen never a corridor (min 3.9 m).
                split_x = max(min_split_x, ix_min + max(W * 0.64, 3.9))
                split_x = min(ix_max - 4.0, split_x)
                split_x = _clear_doorway_span(split_x, axis='X', lo=max(ix_min + 3.0, min_split_x), hi=ix_max - 2.2)
                dw_y = (iy_min + iy_max) * 0.5
                dw_y = _clear_doorway_span(dw_y, axis='Y', lo=iy_min + 1.8, hi=iy_max - 1.8)
                interior_walls.append({
                    'p1': (split_x, iy_min), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
                rm0 = Room(
                    id=f"fl{fl_idx}_taproom", floor_idx=fl_idx, role='TAVERN_TAPROOM',
                    bounds=(ix_min, split_x, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, split_x, iy_min, iy_max)),
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_kitchen", floor_idx=fl_idx, role='KITCHEN',
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, iy_max)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'BACK': (split_x, ix_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0, rm1]
                # A deep, narrow service wing would read as a corridor: split it
                # into a kitchen plus a pantry/scullery instead.
                _kw = ix_max - split_x
                _kd = iy_max - iy_min
                if _kd / max(_kw, 0.1) > 2.0 and _kw >= 3.4 and _kd >= 7.0:
                    _py = iy_min + _kd * 0.55
                    _py = _clear_doorway_span(_py, axis='Y', lo=iy_min + 3.0, hi=iy_max - 3.0)
                    interior_walls.append({
                        'p1': (split_x, _py), 'p2': (ix_max, _py),
                        'axis': 'X', 'pos': _py, 'thickness': wall_t,
                        'doorway': {'x': (split_x + ix_max) * 0.5, 'y': _py,
                                    'w': dw_w, 'h': dw_h, 'axis': 'X'},
                    })
                    _pdx = (split_x + ix_max) * 0.5
                    rm1.bounds = (split_x, ix_max, iy_min, _py)
                    rm1.stair_hole = _holds_stair(rm1.bounds)
                    rm1.doorways = list(rm1.doorways) + [
                        {'x': _pdx, 'y': _py, 'axis': 'X', 'w': dw_w}]
                    rm1.exterior_facades = {'RIGHT': (iy_min, _py),
                                            'FRONT': (split_x, ix_max)}
                    rooms = [rm0, rm1, Room(
                        id=f"fl{fl_idx}_pantry", floor_idx=fl_idx, role='PANTRY',
                        bounds=(split_x, ix_max, _py, iy_max),
                        doorways=[{'x': _pdx, 'y': _py, 'axis': 'X', 'w': dw_w}],
                        stair_hole=_holds_stair((split_x, ix_max, _py, iy_max)),
                        exterior_facades={'RIGHT': (_py, iy_max),
                                          'BACK': (split_x, ix_max)})]

    elif ((fl_idx > 0 and (effective_archetype in _HALL_ARCHETYPES
                           or effective_archetype.startswith('ARTISAN')))
          and has_interior_walls and partition_style in ('AUTO', 'HALL_CHAMBERS')
          and getattr(props, 'has_stairs', False)
          and W >= 10.0 and D >= 7.0):
        # Guest floor of an inn/tavern: a stair landing strip along the stair
        # wall, a central corridor, and sensibly sized guest rooms that all open
        # off that corridor. No huge empty landing and no route through a
        # bedroom to reach another room.
        _stair_right = bool(
            (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
            or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT')
        _sw = float((stair_pos_info or {}).get('w', 1.8) or 1.8)
        if stair_pos_info and stair_pos_info.get('cx') is not None:
            _scx = float(stair_pos_info.get('cx'))
        else:
            _scx = (ix_max - 0.08 - _sw * 0.5) if _stair_right else (ix_min + 0.08 + _sw * 0.5)
        _corr_half = 1.0   # corridor is always at least 2.0 m wide
        _mid_y = (iy_min + iy_max) * 0.5
        if _stair_right:
            _stair_edge = _scx - _sw * 0.5 - 1.70
            _land_edge = max(ix_min + 2.0, _stair_edge)
            _land_lo, _land_hi = _land_edge, ix_max
            _rest_lo, _rest_hi = ix_min, _land_edge
        else:
            _stair_edge = _scx + _sw * 0.5 + 1.70
            _land_edge = min(ix_max - 2.0, _stair_edge)
            _land_lo, _land_hi = ix_min, _land_edge
            _rest_lo, _rest_hi = _land_edge, ix_max

        # Never run the landing wall through a front/back doorway - notably the
        # wing portal.  Expand the stair hall to swallow any such opening on the
        # stair side so the wing opens into circulation instead of a wall.
        for _d in (doorways or []):
            if _d.get('axis') != 'X':
                continue
            _dx = float(_d.get('x', 0.0))
            _dwid = float(_d.get('w', 1.0) or 1.0)
            if _stair_right:
                if (_dx + _dwid * 0.5 >= _land_edge
                        and _dx - _dwid * 0.5 <= ix_max):
                    _cand = _dx - _dwid * 0.5 - 0.35
                    if _cand - ix_min >= 6.0:
                        _land_edge = min(_land_edge, _cand)
            else:
                if (_dx - _dwid * 0.5 <= _land_edge
                        and _dx + _dwid * 0.5 >= ix_min):
                    _cand = _dx + _dwid * 0.5 + 0.35
                    if ix_max - _cand >= 6.0:
                        _land_edge = max(_land_edge, _cand)
        if _stair_right:
            _land_lo, _land_hi = _land_edge, ix_max
            _rest_lo, _rest_hi = ix_min, _land_edge
        else:
            _land_lo, _land_hi = ix_min, _land_edge
            _rest_lo, _rest_hi = _land_edge, ix_max

        _land_fac = {'FRONT': (_land_lo, _land_hi), 'BACK': (_land_lo, _land_hi)}
        _land_fac['LEFT' if not _stair_right else 'RIGHT'] = (iy_min, iy_max)
        landing_rm = Room(
            id=f"fl{fl_idx}_stair_landing", floor_idx=fl_idx, role='STAIR_LANDING',
            bounds=(_land_lo, _land_hi, iy_min, iy_max),
            doorways=[{'x': _land_edge, 'y': _mid_y, 'axis': 'Y', 'w': dw_w}],
            stair_hole=stair_hole, exterior_facades=_land_fac)
        interior_walls.append({
            'p1': (_land_edge, iy_min), 'p2': (_land_edge, iy_max),
            'axis': 'Y', 'pos': _land_edge, 'thickness': wall_t,
            'doorway': {'x': _land_edge, 'y': _mid_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
        })
        corridor_rm = Room(
            id=f"fl{fl_idx}_corridor", floor_idx=fl_idx, role='CORRIDOR',
            bounds=(_rest_lo, _rest_hi, _mid_y - _corr_half, _mid_y + _corr_half),
            doorways=[{'x': _land_edge, 'y': _mid_y, 'axis': 'Y', 'w': dw_w}],
            stair_hole=None, exterior_facades={})
        rooms = [landing_rm, corridor_rm]

        _rest_w = _rest_hi - _rest_lo
        _n_cols = (4 if _rest_w >= 18.0 else 3 if _rest_w >= 12.0
                   else 2 if _rest_w >= 7.0 else 1)
        _col = _rest_w / _n_cols
        _wing_cy = None
        if fl_wings_bounds:
            _wing_cy = (fl_wings_bounds[0][0] + fl_wings_bounds[0][1]) * 0.5
        _gi = [0]
        _room_role_pool = [
            r for r in (_resolve_room_roles(
                effective_archetype, fl_idx, max(4, _n_cols * 2), True,
                total_floors, program=program) or [])
            if r not in ('STAIR_LANDING', 'CORRIDOR', 'ENTRANCE_HALL')
        ] or ['BEDROOM']

        def _add_guest_zone(zy0, zy1, north):
            for _ci in range(_n_cols):
                x0 = _rest_lo + _ci * _col
                x1 = _rest_hi if _ci == _n_cols - 1 else _rest_lo + (_ci + 1) * _col
                cxz = (x0 + x1) * 0.5
                is_common = ((not north) and _wing_cy is not None
                             and (x0 - 0.30 <= _wing_cy <= x1 + 0.30)
                             and effective_archetype in ('INN', 'TAVERN'))
                if is_common:
                    role = 'COMMON_ROOM'
                else:
                    role = _room_role_pool[_gi[0] % len(_room_role_pool)]
                    _gi[0] += 1
                door_y = zy0 if north else zy1
                _fac = {}
                if north and abs(zy1 - iy_max) < 0.01:
                    _fac['BACK'] = (x0, x1)
                if (not north) and abs(zy0 - iy_min) < 0.01:
                    _fac['FRONT'] = (x0, x1)
                if abs(x1 - _rest_hi) < 0.01:
                    _fac['RIGHT'] = (zy0, zy1)
                if abs(x0 - _rest_lo) < 0.01:
                    _fac['LEFT'] = (zy0, zy1)
                rooms.append(Room(
                    id=f"fl{fl_idx}_{'n' if north else 's'}{_ci}", floor_idx=fl_idx,
                    role=role, bounds=(x0, x1, zy0, zy1),
                    doorways=[{'x': cxz, 'y': door_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=None, exterior_facades=_fac, allow_large=True))
                interior_walls.append({
                    'p1': (x0, door_y), 'p2': (x1, door_y),
                    'axis': 'X', 'pos': door_y, 'thickness': wall_t,
                    'doorway': {'x': cxz, 'y': door_y, 'w': dw_w, 'h': dw_h, 'axis': 'X'},
                })
                if _ci > 0:
                    interior_walls.append({
                        'p1': (x0, zy0), 'p2': (x0, zy1),
                        'axis': 'Y', 'pos': x0, 'thickness': wall_t,
                        'doorway': None,
                    })

        _add_guest_zone(_mid_y + _corr_half, iy_max, True)
        _add_guest_zone(iy_min, _mid_y - _corr_half, False)

    elif not is_deep:
        # Partition along Y (vertical wall at X = split_x, running from iy_min to iy_max)
        stair_on_right = bool(
            (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
            or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
        )
        if stair_on_right:
            stair_w = float((stair_pos_info or {}).get('w', 1.2) or 1.2)
            stair_cx = float((stair_pos_info or {}).get('cx', ix_max - 1.4) or (ix_max - 1.4))
            stair_safe_x_left = stair_cx - stair_w * 0.5 - 0.20
            max_split_x = stair_safe_x_left - 1.00
            split_x = max(ix_min + 2.2, min(max_split_x, ix_max - W * 0.38))
            split_x = _clear_doorway_span(split_x, axis='X',
                                          lo=ix_min + 1.8,
                                          hi=min(ix_max - 1.8, max_split_x))
        else:
            min_split_x = stair_safe_x + 1.00
            if door_cx is not None:
                min_split_x = max(min_split_x, door_cx + 0.95)
            if bool(getattr(props, 'has_throne_room', False)):
                min_split_x = max(min_split_x, 0.95)

            split_x = min(ix_max - 2.2, max(min_split_x, ix_min + W * 0.50))
            split_x = _clear_doorway_span(split_x, axis='X',
                                          lo=max(ix_min + 1.8, min_split_x),
                                          hi=ix_max - 1.8)

        # Smarter room division: refuse long narrow corridor-rooms. Peek the
        # chamber roles so the single kitchen gets a bigger share, then
        # downgrade 4 -> 3 -> 2 rooms whenever the strip would slice into
        # proportions worse than ~2.4:1 (or any side under 3.6m for 3rd-person gameplay).
        def _strip_chunky(hw, cw, fracs):
            if min(hw, cw) < 3.6:
                return False
            if D / max(hw, 0.5) > 2.8:
                return False
            for f in fracs:
                d = D * f
                if min(cw, d) < 3.6:
                    return False
                if max(cw, d) / max(min(cw, d), 0.5) > 2.4:
                    return False
            return True

        _hw_now = split_x - ix_min
        _cw_now = ix_max - split_x
        _r4 = _resolve_room_roles(effective_archetype, fl_idx, 4, has_stairs_landing, total_floors, program=program)
        _r3 = _resolve_room_roles(effective_archetype, fl_idx, 3, has_stairs_landing, total_floors, program=program)
        _big_k4 = len(_r4) > 1 and _r4[1] == 'KITCHEN'
        _big_k3 = len(_r3) > 1 and _r3[1] == 'KITCHEN'
        _f4 = (0.42, 0.28, 0.30) if _big_k4 else (0.35, 0.33, 0.32)
        _f3 = (0.58, 0.42) if _big_k3 else (0.50, 0.50)
        has_bs = (fl_idx == 0 and stair_hole is not None and getattr(props, 'has_basement_stair', False)
                 and shape != 'L_SHAPE')
        if can_4_rooms and _cw_now >= 2.4 and not has_bs and not _strip_chunky(_hw_now, _cw_now, _f4):
            can_4_rooms = False
        if can_3_rooms and not has_bs and not _strip_chunky(_hw_now, _cw_now, _f3):
            can_3_rooms = False
            can_4_rooms = False

        if effective_archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL') and fl_idx == 0:
            # Ground floor of Town Hall: Grand Great Hall, optionally with side archive/clerk office
            if W >= 8.5 and not is_deep:
                dw_y = (iy_min + iy_max) * 0.5
                interior_walls.append({
                    'p1': (split_x, iy_min), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
                rm0 = Room(
                    id=f"fl{fl_idx}_great_hall", floor_idx=fl_idx, role='GREAT_HALL',
                    bounds=(ix_min, split_x, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, split_x, iy_min, iy_max)),
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_archive", floor_idx=fl_idx, role='ARCHIVE',
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, iy_max)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'BACK': (split_x, ix_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0, rm1]
            else:
                rm0 = Room(
                    id=f"fl{fl_idx}_great_hall", floor_idx=fl_idx, role='GREAT_HALL',
                    bounds=(ix_min, ix_max, iy_min, iy_max),
                    doorways=[],
                    stair_hole=stair_hole,
                    exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                                      'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0]

        elif effective_archetype == 'TENEMENT':
            # Dedicated Tenement Multi-Apartment System:
            # If interior stairs exist: dedicated enclosed common hallway / stairwell on left.
            # The staircase is strictly isolated inside the hallway - NEVER inside an apartment!
            # The remaining area is divided into self-contained apartments (South and North),
            # each entered via a private door from the hallway and partitioned into
            # an independent TENEMENT_KITCHEN and TENEMENT_BEDROOM with an internal doorway.
            has_internal_stairs = bool(has_stairs_landing or stair_hole is not None or getattr(props, 'has_stairs', False))
            ext_stairs_side = getattr(props, 'exterior_stairs_side', 'LEFT')
            has_courtyard_or_dual = (ext_stairs_side in ('COURTYARD', 'BOTH'))
            # Common hallway is only used when there are internal stairs.
            # When exterior stairs / walkways are present, circulation is via
            # the exterior gallery deck with direct apartment entrances.
            use_common_hall = has_internal_stairs
            # Exterior gallery entrance: South/North apartments split the depth
            # evenly so both suites stay the same size (the old 4.5m cap made
            # the south suite a shallow strip and the north suite huge).
            # Room proportions are kept chunky by the preset footprint
            # (each room about W/2 x D/2, both sides in the 3.2m..6.0m band).
            if not use_common_hall:
                split_y = _clear_doorway_span((iy_min + iy_max) * 0.5, axis='Y',
                                             lo=iy_min + 3.2, hi=iy_max - 3.2)
            else:
                split_y = _clear_doorway_span((iy_min + iy_max) * 0.5, axis='Y')
            dw_y_s = (iy_min + split_y) * 0.5
            dw_y_n = (split_y + iy_max) * 0.5

            if use_common_hall:
                # Dedicated common stairwell / hallway corridor along the left side.
                # Floor-to-floor the demising wall keeps the SAME X, so the
                # route up through the building is continuous.
                if stair_switchback:
                    # Two-lane (switchback) tenement well: the hall has to
                    # swallow BOTH flights plus the walkway beside them, so it is
                    # sized from the stair geometry first.  The percentage
                    # guardrails still apply wherever they can reach that far,
                    # but never squeeze the stairwell into the apartments.
                    min_hw = max(3.20, (stair_safe_x - ix_min) + walk_w)
                    if door_cx is not None:
                        min_hw = max(min_hw, (door_cx + dw_w * 0.5 + 0.30) - ix_min)
                    hall_w = min(max(min_hw, 3.20), max(W * 0.38, min_hw))
                else:
                    # Single-lane corridor: stair lane (~1.55m from wall) + clear walking aisle of at least 2.5m
                    # (2.5m is the smallest walkable area in game)
                    min_hw = max(4.10, (stair_safe_x - ix_min) + 2.50)
                    if door_cx is not None:
                        min_hw = max(min_hw, (door_cx + dw_w * 0.5 + 0.30) - ix_min)
                    hall_w = max(min_hw, min(W * 0.36, max(min_hw, 4.10)))
                hall_x = ix_min + hall_w
                # The hallway wall meets the front/back walls: keep it clear of
                # street doors and wing portals there (without squeezing the
                # stairs or an entrance door out of the hallway).
                hall_x = _clear_doorway_span(
                    hall_x, axis='X', lo=max(ix_min + 1.8, ix_min + min_hw),
                    hi=min(ix_max - 2.5, ix_min + max(W * 0.38, min_hw + 0.50)))

                # 1. Hallway demising wall at X = hall_x (spans full depth iy_min to iy_max)
                # Two cased entrance doors leading into Apartment 1 (South) and Apartment 2 (North)
                interior_walls.append({
                    'p1': (hall_x, iy_min), 'p2': (hall_x, split_y),
                    'axis': 'Y', 'pos': hall_x, 'thickness': wall_t,
                    'doorway': {'x': hall_x, 'y': dw_y_s, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
                interior_walls.append({
                    'p1': (hall_x, split_y), 'p2': (hall_x, iy_max),
                    'axis': 'Y', 'pos': hall_x, 'thickness': wall_t,
                    'doorway': {'x': hall_x, 'y': dw_y_n, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })

                # 2. Apartment Demising Wall at Y = split_y (hall_x to ix_max, NO doorway)
                interior_walls.append({
                    'p1': (hall_x, split_y), 'p2': (ix_max, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t, 'doorway': None
                })

                # 3. Dedicated Common Hallway / Stairwell Room (isolates stairs from suites)
                rm_hall = Room(
                    id=f"fl{fl_idx}_common_hall", floor_idx=fl_idx, role='STAIR_LANDING',
                    bounds=(ix_min, hall_x, iy_min, iy_max),
                    doorways=[
                        {'x': hall_x, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                        {'x': hall_x, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                    ],
                    stair_hole=stair_hole,
                    exterior_facades={'FRONT': (ix_min, hall_x), 'BACK': (ix_min, hall_x), 'LEFT': (iy_min, iy_max)}
                )
                rooms = [rm_hall]

                apt_w = ix_max - hall_x
                if apt_w >= 7.5:
                    # Plan each side flat as a cluster of cozy rooms around its
                    # hall door, instead of two 100 m² half-apartments.
                    from .tenement import cozy_apartment

                    def _apt_touches(b, d):
                        return (b[0] - 0.15 <= d.get('x', 0.0) <= b[1] + 0.15
                                and b[2] - 0.15 <= d.get('y', 0.0) <= b[3] + 0.15)

                    for _tag, _y0, _y1, _ey in (
                            ('south', iy_min, split_y, dw_y_s),
                            ('north', split_y, iy_max, dw_y_n)):
                        _rect = (hall_x, ix_max, _y0, _y1)
                        _aentry = {'x': hall_x, 'y': _ey, 'axis': 'Y', 'w': dw_w}
                        _arms, _arws = cozy_apartment(_rect, _aentry, max_rooms=8)
                        _adoors = ([w['doorway'] for w in _arws if w.get('doorway')]
                                   + [_aentry])
                        for _aw in _arws:
                            interior_walls.append({
                                'p1': _aw['p1'], 'p2': _aw['p2'],
                                'axis': _aw['axis'], 'pos': _aw['pos'],
                                'thickness': wall_t, 'doorway': _aw.get('doorway'),
                            })
                        for _ai, _ar in enumerate(_arms):
                            _ab = _ar['bounds']
                            _adws = [dict(d) for d in _adoors
                                     if d and _apt_touches(_ab, d)]
                            _afac = {}
                            if abs(_ab[2] - iy_min) < 0.02:
                                _afac['FRONT'] = (_ab[0], _ab[1])
                            if abs(_ab[3] - iy_max) < 0.02:
                                _afac['BACK'] = (_ab[0], _ab[1])
                            if abs(_ab[1] - ix_max) < 0.02:
                                _afac['RIGHT'] = (_ab[2], _ab[3])
                            rooms.append(Room(
                                id=f"fl{fl_idx}_apt_{_tag}_r{_ai}",
                                floor_idx=fl_idx, role=_ar['role'],
                                bounds=_ab, doorways=_adws, stair_hole=None,
                                exterior_facades=_afac))
                else:
                    # Narrow plot: single-room studio apartments
                    rm_s = Room(
                        id=f"fl{fl_idx}_apt_south", floor_idx=fl_idx, role='TENEMENT_KITCHEN',
                        bounds=(hall_x, ix_max, iy_min, split_y),
                        doorways=[{'x': hall_x, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'FRONT': (hall_x, ix_max), 'RIGHT': (iy_min, split_y)}
                    )
                    rm_n = Room(
                        id=f"fl{fl_idx}_apt_north", floor_idx=fl_idx, role='TENEMENT_BEDROOM',
                        bounds=(hall_x, ix_max, split_y, iy_max),
                        doorways=[{'x': hall_x, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'BACK': (hall_x, ix_max), 'RIGHT': (split_y, iy_max)}
                    )
                    rooms.extend([rm_s, rm_n])
            else:
                # Exterior-entrance tenement: split the floor into the small
                # apartments described by the shared layout (generator/tenement),
                # so the rooms, the single exterior door per flat and the outside
                # staircase always agree.  No common corridor is needed because
                # circulation happens on the exterior gallery.
                from .tenement import apartment_layout, demising_walls
                _tb = (ix_min, ix_max, iy_min, iy_max)
                _apts = apartment_layout(_tb, shape, fl_wings_bounds, props, fl_idx=fl_idx)
                for _dwr in demising_walls(_tb, shape, fl_wings_bounds, props):
                    interior_walls.append({
                        'p1': _dwr['p1'], 'p2': _dwr['p2'],
                        'axis': _dwr['axis'], 'pos': _dwr['pos'],
                        'thickness': wall_t, 'doorway': None,
                    })

                def _touches(b, d):
                    _x0, _x1, _y0, _y1 = b
                    return (_x0 - 0.15 <= d.get('x', 0.0) <= _x1 + 0.15
                            and _y0 - 0.15 <= d.get('y', 0.0) <= _y1 + 0.15)

                # Collect every doorway on the floor once: a door in a shared
                # wall belongs to both rooms, and a flat's rooms may be served
                # by a portal registered on a neighbouring apartment.
                _all_doors = []
                for _apt in _apts:
                    _all_doors.extend(w['doorway'] for w in _apt['walls'] if w.get('doorway'))
                    _all_doors.append(_apt['entry'])
                for _apt in _apts:
                    _is_w = _apt['id'].startswith('wing')
                    _w_id = (int(_apt['id'].replace('wing', '')) - 1) if _is_w else None
                    for _ri, _rd in enumerate(_apt['rooms']):
                        _b = _rd['bounds']
                        _rdws = [dict(d) for d in _all_doors if d and _touches(_b, d)]
                        rooms.append(Room(
                            id=f"fl{fl_idx}_{_apt['id']}_r{_ri}",
                            floor_idx=fl_idx, role=_rd['role'], bounds=_b,
                            is_wing=_is_w, wing_id=_w_id,
                            doorways=_rdws, stair_hole=None,
                            exterior_facades=dict(_rd['facades'])))
                    for _w in _apt['walls']:
                        interior_walls.append({
                            'p1': _w['p1'], 'p2': _w['p2'],
                            'axis': _w['axis'], 'pos': _w['pos'],
                            'thickness': wall_t, 'doorway': _w.get('doorway'),
                        })

        elif can_4_rooms and (ix_max - split_x >= 2.4):
            # 4 Rooms (Corridor/Landing Hall on Left + 3 separate chambers on Right)
            roles = _resolve_room_roles(effective_archetype, fl_idx, 4, has_stairs_landing, total_floors, program=program)
            # One bigger kitchen: when chamber 1 is the kitchen it takes a
            # larger share of the strip instead of two small rooms.
            _k1, _k2 = (0.42, 0.70) if (len(roles) > 1 and roles[1] == 'KITCHEN') else (0.35, 0.68)
            # Clear in order and keep the chambers stacked with room to spare.
            split_y1 = _clear_doorway_span(iy_min + D * _k1, axis='Y',
                                            hi=iy_min + D * _k2 - 3.2)
            split_y2 = _clear_doorway_span(iy_min + D * _k2, axis='Y',
                                            lo=split_y1 + 3.2)
            if oven_band is not None:
                # Keep both chamber lines out of the oven masonry, preserving
                # their order and a walkable 3.2m minimum chamber depth.
                split_y1 = _dodge_oven_band(split_y1, iy_min + 3.2, iy_max - 5.0)
                split_y2 = _dodge_oven_band(max(split_y2, split_y1 + 3.2),
                                            split_y1 + 3.2, iy_max - 3.2)
                if oven_band[0] <= split_y2 <= oven_band[1]:
                    split_y2 = min(iy_max - 3.2, oven_band[1])

            dw_y1 = (iy_min + split_y1) * 0.5
            dw_y2 = (split_y1 + split_y2) * 0.5
            has_bs = (fl_idx == 0 and stair_hole is not None and getattr(props, 'has_basement_stair', False)
                 and shape != 'L_SHAPE')
            if has_bs:
                dw_y3 = (stair_hole[2] + stair_hole[3]) * 0.5
                cellar_west_x = min(split_x, stair_hole[0] - 1.10)
                stair_sep_x = max(split_x + 2.4, min(ix_max - 2.4, stair_hole[1] + 0.70))
                dw_c3_x = (stair_sep_x + ix_max) * 0.5
            else:
                dw_y3 = (split_y2 + iy_max) * 0.5
                cellar_west_x = split_x
                stair_sep_x = None
                dw_c3_x = None

            interior_walls.append({
                'p1': (split_x, iy_min), 'p2': (split_x, split_y1),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y1, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            interior_walls.append({
                'p1': (split_x, split_y1), 'p2': (split_x, split_y2),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y2, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            if has_bs:
                # West wall of the cellar stair room: placed WEST of stair landing with doorway opening from hall
                interior_walls.append({
                    'p1': (cellar_west_x, split_y2), 'p2': (cellar_west_x, iy_max),
                    'axis': 'Y', 'pos': cellar_west_x, 'thickness': wall_t,
                    'doorway': {'x': cellar_west_x, 'y': dw_y3, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
            else:
                interior_walls.append({
                    'p1': (split_x, split_y2), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y3, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
            interior_walls.append({
                'p1': (split_x, split_y1), 'p2': (ix_max, split_y1),
                'axis': 'X', 'pos': split_y1, 'thickness': wall_t, 'doorway': None
            })
            if has_bs:
                # South wall of the cellar stair room: solid wall from cellar_west_x to stair_sep_x
                interior_walls.append({
                    'p1': (cellar_west_x, split_y2), 'p2': (stair_sep_x, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t, 'doorway': None
                })
                # South wall of Chamber 3: doorway connecting into Chamber 2
                interior_walls.append({
                    'p1': (stair_sep_x, split_y2), 'p2': (ix_max, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t,
                    'doorway': {'x': dw_c3_x, 'y': split_y2, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                })
                # Solid partition wall enclosing the cellar stair hall from Chamber 3 (NO doorway!)
                interior_walls.append({
                    'p1': (stair_sep_x, split_y2), 'p2': (stair_sep_x, iy_max),
                    'axis': 'Y', 'pos': stair_sep_x, 'thickness': wall_t,
                    'doorway': None
                })
            else:
                interior_walls.append({
                    'p1': (split_x, split_y2), 'p2': (ix_max, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t, 'doorway': None
                })

            _hall_dw_4 = [
                {'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w},
                {'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w},
                {'x': cellar_west_x if has_bs else split_x, 'y': dw_y3, 'axis': 'Y', 'w': dw_w},
            ]
            rm0 = Room(
                id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role=roles[0],
                bounds=(ix_min, split_x, iy_min, iy_max),
                doorways=_hall_dw_4,
                stair_hole=None if has_bs else _holds_stair((ix_min, split_x, iy_min, iy_max)),
                exterior_facades={'FRONT': (ix_min, split_x),
                                  'BACK': (ix_min, cellar_west_x if has_bs else split_x),
                                  'LEFT': (iy_min, iy_max)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_chamber_1", floor_idx=fl_idx, role=roles[1],
                bounds=(split_x, ix_max, iy_min, split_y1),
                doorways=[{'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w}],
                stair_hole=_holds_stair((split_x, ix_max, iy_min, split_y1)),
                exterior_facades={'FRONT': (split_x, ix_max), 'RIGHT': (iy_min, split_y1)}
            )
            if has_bs:
                rm2 = Room(
                    id=f"fl{fl_idx}_chamber_2", floor_idx=fl_idx, role=roles[2],
                    bounds=(split_x, ix_max, split_y1, split_y2),
                    doorways=[
                        {'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w},
                        {'x': dw_c3_x, 'y': split_y2, 'axis': 'X', 'w': dw_w},
                    ],
                    stair_hole=_holds_stair((split_x, ix_max, split_y1, split_y2)),
                    exterior_facades={'RIGHT': (split_y1, split_y2)}
                )
                rm_stair = Room(
                    id=f"fl{fl_idx}_cellar_stair", floor_idx=fl_idx, role='STAIR_LANDING',
                    bounds=(cellar_west_x, stair_sep_x, split_y2, iy_max),
                    doorways=[
                        {'x': cellar_west_x, 'y': dw_y3, 'axis': 'Y', 'w': dw_w},
                    ],
                    stair_hole=stair_hole,
                    exterior_facades={'BACK': (cellar_west_x, stair_sep_x)}
                )
                rm3 = Room(
                    id=f"fl{fl_idx}_chamber_3", floor_idx=fl_idx, role=roles[3],
                    bounds=(stair_sep_x, ix_max, split_y2, iy_max),
                    doorways=[{'x': dw_c3_x, 'y': split_y2, 'axis': 'X', 'w': dw_w}],
                    stair_hole=None,
                    exterior_facades={'BACK': (stair_sep_x, ix_max), 'RIGHT': (split_y2, iy_max)}
                )
                rooms = [rm0, rm1, rm2, rm_stair, rm3]
            else:
                rm2 = Room(
                    id=f"fl{fl_idx}_chamber_2", floor_idx=fl_idx, role=roles[2],
                    bounds=(split_x, ix_max, split_y1, split_y2),
                    doorways=[{'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, split_y1, split_y2)),
                    exterior_facades={'RIGHT': (split_y1, split_y2)}
                )
                rm3 = Room(
                    id=f"fl{fl_idx}_chamber_3", floor_idx=fl_idx, role=roles[3],
                    bounds=(split_x, ix_max, split_y2, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y3, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, split_y2, iy_max)),
                    exterior_facades={'BACK': (split_x, ix_max), 'RIGHT': (split_y2, iy_max)}
                )
                rooms = [rm0, rm1, rm2, rm3]
            _force_bakehouse_chamber(rooms)

        elif can_3_rooms and (D >= 5.4) and (ix_max - split_x >= 2.2):
            # 3 Rooms total (Landing/Corridor on Left + 2 Chambers on Right)
            roles = _resolve_room_roles(effective_archetype, fl_idx, 3, has_stairs_landing, total_floors, program=program)
            # One bigger kitchen: the kitchen chamber takes ~58% of the strip.
            _kf = 0.58 if (len(roles) > 1 and roles[1] == 'KITCHEN') else 0.50
            split_y = _clear_doorway_span(iy_min + D * _kf, axis='Y')
            split_y = _dodge_oven_band(split_y, iy_min + 1.8, iy_max - 1.8)

            has_bs = (fl_idx == 0 and stair_hole is not None and getattr(props, 'has_basement_stair', False)
                 and shape != 'L_SHAPE')
            dw_y1 = (iy_min + split_y) * 0.5
            if has_bs:
                dw_y2 = (stair_hole[2] + stair_hole[3]) * 0.5
                cellar_west_x = min(split_x, stair_hole[0] - 1.10)
                stair_sep_x = max(split_x + 2.4, min(ix_max - 2.4, stair_hole[1] + 0.70))
                dw_c2_x = (stair_sep_x + ix_max) * 0.5
            else:
                dw_y2 = (split_y + iy_max) * 0.5
                cellar_west_x = split_x
                stair_sep_x = None
                dw_c2_x = None

            interior_walls.append({
                'p1': (split_x, iy_min), 'p2': (split_x, split_y),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y1, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            if has_bs:
                interior_walls.append({
                    'p1': (cellar_west_x, split_y), 'p2': (cellar_west_x, iy_max),
                    'axis': 'Y', 'pos': cellar_west_x, 'thickness': wall_t,
                    'doorway': {'x': cellar_west_x, 'y': dw_y2, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
            else:
                interior_walls.append({
                    'p1': (split_x, split_y), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y2, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
            if has_bs:
                # South wall of the cellar stair room: solid wall (NO doorway)
                interior_walls.append({
                    'p1': (cellar_west_x, split_y), 'p2': (stair_sep_x, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t, 'doorway': None
                })
                # South wall of North-East Chamber: doorway connecting into South-East Chamber
                interior_walls.append({
                    'p1': (stair_sep_x, split_y), 'p2': (ix_max, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t,
                    'doorway': {'x': dw_c2_x, 'y': split_y, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                })
                # Solid partition wall enclosing the cellar stair hall from NE Chamber (NO doorway!)
                interior_walls.append({
                    'p1': (stair_sep_x, split_y), 'p2': (stair_sep_x, iy_max),
                    'axis': 'Y', 'pos': stair_sep_x, 'thickness': wall_t,
                    'doorway': None
                })
            else:
                interior_walls.append({
                    'p1': (split_x, split_y), 'p2': (ix_max, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t, 'doorway': None
                })

            _hall_dw_3 = [
                {'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w},
                {'x': cellar_west_x if has_bs else split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}
            ]
            rm0 = Room(
                id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role=roles[0],
                bounds=(ix_min, split_x, iy_min, iy_max),
                doorways=_hall_dw_3,
                stair_hole=None if has_bs else _holds_stair((ix_min, split_x, iy_min, iy_max)),
                exterior_facades={'FRONT': (ix_min, split_x),
                                  'BACK': (ix_min, cellar_west_x if has_bs else split_x),
                                  'LEFT': (iy_min, iy_max)}
            )
            if has_bs:
                rm1 = Room(
                    id=f"fl{fl_idx}_chamber_se", floor_idx=fl_idx, role=roles[1],
                    bounds=(split_x, ix_max, iy_min, split_y),
                    doorways=[
                        {'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w},
                        {'x': dw_c2_x, 'y': split_y, 'axis': 'X', 'w': dw_w},
                    ],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, split_y)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'RIGHT': (iy_min, split_y)}
                )
                rm_stair = Room(
                    id=f"fl{fl_idx}_cellar_stair", floor_idx=fl_idx, role='STAIR_LANDING',
                    bounds=(cellar_west_x, stair_sep_x, split_y, iy_max),
                    doorways=[
                        {'x': cellar_west_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w},
                    ],
                    stair_hole=stair_hole,
                    exterior_facades={'BACK': (cellar_west_x, stair_sep_x)}
                )
                rm2 = Room(
                    id=f"fl{fl_idx}_chamber_ne", floor_idx=fl_idx, role=roles[2],
                    bounds=(stair_sep_x, ix_max, split_y, iy_max),
                    doorways=[{'x': dw_c2_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=None,
                    exterior_facades={'BACK': (stair_sep_x, ix_max), 'RIGHT': (split_y, iy_max)}
                )
                rooms = [rm0, rm1, rm_stair, rm2]
            else:
                rm1 = Room(
                    id=f"fl{fl_idx}_chamber_se", floor_idx=fl_idx, role=roles[1],
                    bounds=(split_x, ix_max, iy_min, split_y),
                    doorways=[{'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, split_y)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'RIGHT': (iy_min, split_y)}
                )
                rm2 = Room(
                    id=f"fl{fl_idx}_chamber_ne", floor_idx=fl_idx, role=roles[2],
                    bounds=(split_x, ix_max, split_y, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, split_y, iy_max)),
                    exterior_facades={'BACK': (split_x, ix_max), 'RIGHT': (split_y, iy_max)}
                )
                rooms = [rm0, rm1, rm2]
            _force_bakehouse_chamber(rooms)

        else:
            # 2 Rooms: choose the cardinal direction (Y vertical or X horizontal) that
            # produces squareish rooms rather than long corridors.
            roles = _resolve_room_roles(effective_archetype, fl_idx, 2, has_stairs_landing, total_floors, program=program)
            w_left = split_x - ix_min
            w_right = ix_max - split_x
            ar_y = max(D / max(w_left, 0.5), D / max(w_right, 0.5), max(w_left, w_right) / max(D, 0.5))

            # Candidate horizontal split (axis='X')
            sy_b = (stair_pos_info or {}).get('y_bot', stair_hole[2] if stair_hole is not None else None)
            sy_t = (stair_pos_info or {}).get('y_top', stair_hole[3] if stair_hole is not None else None)
            if sy_b is not None and sy_t is not None:
                pad_2rm = 2.00
                _hh0 = min(sy_b, sy_t) - pad_2rm
                _hh1 = max(sy_b, sy_t) + pad_2rm
            elif stair_hole is not None:
                _hh0, _hh1 = stair_hole[2] - 1.80, stair_hole[3] + 1.80
            else:
                _hh0 = _hh1 = None

            if stair_guards_north:
                cand_split_y = min((_hh0 if _hh0 is not None else (stair_safe_y_bot - 0.65)), iy_min + D * 0.48)
                cand_split_y = max(iy_min + 2.3, cand_split_y)
            else:
                cand_split_y = max((_hh1 if _hh1 is not None else (stair_safe_y_top + 0.65)), iy_min + D * 0.48)
                cand_split_y = min(iy_max - 2.3, cand_split_y)
            cand_split_y = _clear_doorway_span(cand_split_y, axis='Y', lo=iy_min + 2.3, hi=iy_max - 1.8)
            cand_split_y = _dodge_oven_band(cand_split_y, iy_min + 2.3, iy_max - 1.8)
            if _hh0 is not None and _hh0 < cand_split_y < _hh1:
                cand_split_y = _hh0 if (cand_split_y - _hh0) <= (_hh1 - cand_split_y) else _hh1
                cand_split_y = min(max(cand_split_y, iy_min + 2.3), iy_max - 1.8)

            d_front = cand_split_y - iy_min
            d_back = iy_max - cand_split_y
            can_x_split = (d_front >= 2.2 and d_back >= 2.2)
            ar_x = max(W / max(d_front, 0.5), W / max(d_back, 0.5), max(d_front, d_back) / max(W, 0.5)) if can_x_split else 999.0

            if can_x_split and (ar_x < ar_y * 0.90 or (D >= W * 1.15 and ar_x <= 2.2)):
                # Split the other cardinal direction (X - horizontal wall) to avoid narrow vertical strips
                split_y = cand_split_y
                if stair_pos_info and (stair_hole is not None or getattr(props, 'has_stairs', False)):
                    if stair_safe_x < (ix_min + ix_max) * 0.5:
                        dw_x = (stair_safe_x + ix_max) * 0.5
                    else:
                        dw_x = (ix_min + stair_safe_x) * 0.5
                else:
                    dw_x = (ix_min + ix_max) * 0.5
                if door_cx is not None and abs(dw_x - door_cx) < 0.4:
                    dw_x += 0.85
                dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.2, hi=ix_max - 1.2)

                interior_walls.append({
                    'p1': (ix_min, split_y), 'p2': (ix_max, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t,
                    'doorway': {'x': dw_x, 'y': split_y, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                })
                front_role = ('STAIR_LANDING' if (has_stairs_landing and not stair_guards_north)
                              else (roles[1] if has_stairs_landing else roles[0]))
                back_role = ('STAIR_LANDING' if (has_stairs_landing and stair_guards_north)
                             else (roles[0] if has_stairs_landing else roles[1]))
                if back_role == 'STAIR_LANDING':
                    _pool2 = _resolve_room_roles(effective_archetype, fl_idx, 2, False, total_floors, program=program)
                    back_role = next((r for r in reversed(_pool2) if r != 'STAIR_LANDING'), None) or 'BEDROOM'
                rm0 = Room(
                    id=f"fl{fl_idx}_front", floor_idx=fl_idx, role=front_role,
                    bounds=(ix_min, ix_max, iy_min, split_y),
                    doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, ix_max, iy_min, split_y)),
                    exterior_facades={'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, split_y), 'RIGHT': (iy_min, split_y)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_back", floor_idx=fl_idx, role=back_role,
                    bounds=(ix_min, ix_max, split_y, iy_max),
                    doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, ix_max, split_y, iy_max)),
                    exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (split_y, iy_max), 'RIGHT': (split_y, iy_max)}
                )
                rooms = [rm0, rm1]
            else:
                # Vertical split (axis='Y')
                dw_y = (iy_min + iy_max) * 0.5
                dw_y = _clear_doorway_span(dw_y, axis='Y', lo=iy_min + 1.8, hi=iy_max - 1.8)
                dw_y = _dodge_oven_band(dw_y, iy_min + 1.8, iy_max - 1.8)
                interior_walls.append({
                    'p1': (split_x, iy_min), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })
                rm0 = Room(
                    id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role=roles[0],
                    bounds=(ix_min, split_x, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, split_x, iy_min, iy_max)),
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_chamber", floor_idx=fl_idx, role=roles[1],
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, iy_max)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'BACK': (split_x, ix_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0, rm1]

        # Dedicated stair bay: when the landing hall is roomy, split the stair
        # well (plus a 1m walkway) off into its own narrow full-depth stairwell
        # room, so the flight never shares furnishing space with a living room
        # and stays walkable end to end. Skipped for small footprints and for
        # archetypes with bespoke layouts (they manage their own stairs).
        if (rooms and rooms[0].stair_hole is not None and stair_hole is not None
                and fl_idx > 0
                and effective_archetype not in ('TOWN_HALL', 'CIVIC', 'GUILDHALL',
                                                'TAVERN', 'INN', 'TENEMENT', 'MANOR',
                                                'BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                                                'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER',
                                                'FURNITURE_MAKER', 'HUNTER')
                and not effective_archetype.startswith('ARTISAN')
                and D >= 7.0):
            _hall = rooms[0]
            _hx0, _hx1, _hy0, _hy1 = _hall.bounds
            if _hy0 <= iy_min + 0.05 and _hy1 >= iy_max - 0.05:
                if stair_pos_info:
                    try:
                        _scx = float(stair_pos_info.get('cx', 0.0))
                        _sw = float(stair_pos_info.get('w', 1.5))
                        _wx0, _wx1 = _scx - _sw * 0.5, _scx + _sw * 0.5
                    except Exception:
                        _wx0, _wx1 = stair_hole[0], stair_hole[1]
                else:
                    _wx0, _wx1 = stair_hole[0], stair_hole[1]
                _bay = _clear_doorway_span(_wx1 + 1.80, axis='X',
                                           lo=_wx1 + 1.20, hi=_hx1 - 2.8)
                if front_door_info is not None and fl_idx == 0:
                    _dcx, _ddw = front_door_info
                    if abs(_bay - _dcx) < _ddw * 0.5 + 0.65:
                        _bay = _dcx + _ddw * 0.5 + 0.65
                if _hx1 - _bay >= 3.2 and _bay - _hx0 >= 2.0 and D / (_hx1 - _bay) <= 2.6:
                    _ym = (iy_min + iy_max) * 0.5
                    _bd0 = (_bay, (iy_min + _ym) * 0.5)
                    _bd1 = (_bay, (_ym + iy_max) * 0.5)
                    for (_sy0, _sy1, _sbd) in ((iy_min, _ym, _bd0), (_ym, iy_max, _bd1)):
                        interior_walls.append({
                            'p1': (_bay, _sy0), 'p2': (_bay, _sy1),
                            'axis': 'Y', 'pos': _bay, 'thickness': wall_t,
                            'doorway': {'x': _sbd[0], 'y': _sbd[1],
                                        'w': dw_w, 'h': dw_h, 'axis': 'Y'},
                        })
                    _bay_dw = [{'x': _bd0[0], 'y': _bd0[1], 'axis': 'Y', 'w': dw_w},
                               {'x': _bd1[0], 'y': _bd1[1], 'axis': 'Y', 'w': dw_w}]
                    _bay_room = Room(
                        id=f"fl{fl_idx}_stair_bay", floor_idx=fl_idx,
                        role='CORRIDOR' if fl_idx == 0 else 'STAIR_LANDING',
                        bounds=(_hx0, _bay, iy_min, iy_max),
                        doorways=list(_bay_dw),
                        stair_hole=_holds_stair((_hx0, _bay, iy_min, iy_max)),
                        exterior_facades={'FRONT': (_hx0, _bay),
                                          'BACK': (_hx0, _bay),
                                          'LEFT': (iy_min, iy_max)})
                    _hall.bounds = (_bay, _hx1, iy_min, iy_max)
                    _hall.stair_hole = _holds_stair((_bay, _hx1, iy_min, iy_max))
                    _hall.doorways = list(_hall.doorways) + list(_bay_dw)
                    if fl_idx > 0:
                        _hw = _hx1 - _bay
                        _hd = iy_max - iy_min
                        if min(_hw, _hd) < 3.2 or len(_hall.doorways) >= 2:
                            _hall.role = 'CORRIDOR'
                        else:
                            _pool = _resolve_room_roles(
                                effective_archetype, fl_idx, len(rooms) + 1,
                                has_stairs_landing, total_floors, program=program)
                            while len(_pool) <= len(rooms):
                                _pool.append(_pool[-1] if _pool else 'STORAGE')
                            _hall.role = _pool[len(rooms)]
                    _fac = dict(_hall.exterior_facades)
                    _fac.pop('LEFT', None)
                    if 'FRONT' in _fac:
                        _fac['FRONT'] = (_bay, _hx1)
                    if 'BACK' in _fac:
                        _fac['BACK'] = (_bay, _hx1)
                    _hall.exterior_facades = _fac
                    rooms = [_bay_room, _hall] + list(rooms[1:])



    else:
        # Deep building: split the depth into bands so long houses get
        # proper apartments instead of one giant front/back pair. Artisan
        # ground floor is a single big workshop (planned above); upper floors
        # get at most 3 spacious multi-use bands.
        # Prefer bands whose rooms stay at or below ~2:1, so a deep floor never
        # becomes one wide hall with a sliver behind it.
        # Take the SMALLEST number of bands that already yields rooms no more
        # than ~2:1 (a deep hall should become 2 proper rooms, not 1 hall plus
        # leftovers). Only fall back to more bands when 2 would still be strips.
        _deep_target = 2
        for _cand_n in (2, 3, 4):
            if W / max(D / _cand_n, 0.1) <= 2.0 and (D / _cand_n) >= 2.4:
                _deep_target = _cand_n
                break
        if D >= 16.8 and W / max(D / 4.0, 0.1) <= 2.0:
            _deep_target = 4
        _deep_splits = None
        if not _turn_layout and _deep_target >= 3:
            for _try_n in range(_deep_target, 2, -1):
                _raw = [iy_min + D * i / _try_n for i in range(1, _try_n)]
                _ok = True
                _fixed = []
                _lo = iy_min + 2.3
                for _sp in _raw:
                    _sp = _clear_doorway_span(_sp, axis='Y', lo=_lo, hi=iy_max - 1.8)
                    _sp = _dodge_oven_band(_sp, _lo, iy_max - 1.8)
                    _sp = min(max(_sp, _lo), iy_max - 1.8)
                    _hs0 = _hs1 = None
                    sy_b = (stair_pos_info or {}).get('y_bot', stair_hole[2] if stair_hole is not None else None)
                    sy_t = (stair_pos_info or {}).get('y_top', stair_hole[3] if stair_hole is not None else None)
                    if sy_b is not None and sy_t is not None:
                        # Guarantee at least 2.20m walkable landing corridor at both
                        # foot and head landings so partition walls never block stair egress.
                        stair_land_pad = 2.20
                        _hs0 = min(sy_b, sy_t) - stair_land_pad
                        _hs1 = max(sy_b, sy_t) + stair_land_pad
                    if _hs0 is not None:
                        # A split exactly on the clearance edge is already
                        # safe; only the open interval is forbidden.
                        if _hs0 < _sp < _hs1:
                            can_lo = (_hs0 >= _lo)
                            can_hi = (_hs1 <= iy_max - 1.8)
                            if can_lo and can_hi:
                                _sp = _hs0 if (_sp - _hs0) <= (_hs1 - _sp) else _hs1
                            elif can_lo:
                                _sp = _hs0
                            elif can_hi:
                                _sp = _hs1
                            else:
                                _ok = False
                                break
                            _sp = min(max(_sp, _lo), iy_max - 1.8)
                        if _hs0 < _sp < _hs1:
                            _ok = False
                            break
                    _fixed.append(_sp)
                    _lo = _sp + 2.2
                if not (_ok and len(_fixed) == len(_raw) and iy_max - _fixed[-1] >= 2.2 - 1e-6):
                    continue
                _b_spans = [(iy_min, _fixed[0])] + [(_fixed[i], _fixed[i + 1]) for i in range(len(_fixed) - 1)] + [(_fixed[-1], iy_max)]
                _min_d = min(_b1 - _b0 for _b0, _b1 in _b_spans)
                _max_d = max(_b1 - _b0 for _b0, _b1 in _b_spans)
                if not (_min_d >= 2.75 and (W / _min_d) <= 2.85 and (W / _max_d) <= 2.6):
                    # Also reject plans whose deepest band would leave a room
                    # twice as long as it is wide (reads as a corridor).
                    continue
                # Equal bands: every room gets a comparable share instead of one
                # great hall and a sliver behind it.
                if _max_d - _min_d > max(1.2, 0.22 * _max_d):
                    continue
                _deep_splits = _fixed
                _deep_target = _try_n
                break

        if _turn_layout and has_stairs_landing:
            if D < 13.0 or W < 8.0 or partition_style == 'ONE_ROOM':
                # Too small to divide: single generous open combined living area
                rm_living = Room(
                    id=f"fl{fl_idx}_living", floor_idx=fl_idx, role='COTTAGE',
                    bounds=(ix_min, ix_max, iy_min, iy_max),
                    doorways=[],
                    stair_hole=stair_hole,
                    exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                                      'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)}
                )
                _living_rooms = _recut_oversized_rooms(
                    [rm_living], [], bounds, wall_t, dw_w, dw_h,
                    effective_archetype, fl_idx, has_stairs_landing, total_floors, program,
                    clear_zone_rects=clear_zone_rects)
                _living_rooms = _normalize_stair_circulation_rooms(
                    _living_rooms, stair_hole, stair_pos_info, bounds)
                return _living_rooms, []

            # Turned-stair floors: the stair column occupies the front zone (from iy_min to _col_top).
            # It is isolated into a dedicated STAIR_LANDING corridor room with real partition walls,
            # ensuring stair flights and landings are 100% walkable and clutter-free (strictly no beds or couches).
            # The generous floor area behind it (from _col_top to iy_max) is partitioned into
            # elegant, well-proportioned rooms with cased walkthrough doorways.
            _col_top = stair_safe_y_top + 0.35
            _col_top = max(iy_min + 2.8, min(iy_max - 2.8, _col_top))
            _col_top = _clear_doorway_span(_col_top, axis='Y', lo=iy_min + 2.4, hi=iy_max - 2.4)
            _col_top = _dodge_oven_band(_col_top, iy_min + 2.4, iy_max - 2.4)

            has_ascend = (fl_idx < total_floors - 1 and getattr(props, 'has_stairs', True))
            if has_ascend and (fl_idx % 4 == 1):
                # Ascending flight climbs along the North wall of the stair column from West to East.
                # Safe flat landing approach is at the NW arrival corner (corner 1).
                dw_x = ix_min + 1.25
                dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.0, hi=ix_min + 1.6)
                dw_w_eff = min(dw_w, 1.30)
            else:
                dw_x = (ix_min + ix_max) * 0.5
                if door_cx is not None and abs(dw_x - door_cx) < 0.4:
                    dw_x += 0.85
                dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.8, hi=ix_max - 1.8)
                dw_w_eff = dw_w

            interior_walls.append({
                'p1': (ix_min, _col_top), 'p2': (ix_max, _col_top),
                'axis': 'X', 'pos': _col_top, 'thickness': wall_t,
                'doorway': {'x': dw_x, 'y': _col_top, 'w': dw_w_eff, 'h': dw_h, 'axis': 'X'}
            })
            rm_landing = Room(
                id=f"fl{fl_idx}_stair_landing", floor_idx=fl_idx, role='STAIR_LANDING',
                bounds=(ix_min, ix_max, iy_min, _col_top),
                doorways=[{'x': dw_x, 'y': _col_top, 'axis': 'X', 'w': dw_w_eff}],
                stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, _col_top), 'RIGHT': (iy_min, _col_top)}
            )

            avail_d = iy_max - _col_top
            avail_w = ix_max - ix_min

            if avail_d < 4.2 or (partition_style == 'TWO_ROOMS' and avail_d < 6.8):
                if avail_w >= 6.4 and avail_w > avail_d * 1.35 and partition_style != 'ONE_ROOM':
                    # Wide rear zone behind turned stair landing: split into two squareish
                    # private bedrooms (West and East) instead of one giant wide corridor!
                    split_x2 = (ix_min + ix_max) * 0.5
                    split_x2 = _clear_doorway_span(split_x2, axis='X', lo=ix_min + 2.2, hi=ix_max - 2.2)
                    dw_x_l = (ix_min + split_x2) * 0.5
                    dw_x_l = _clear_doorway_span(dw_x_l, axis='X', lo=ix_min + 1.2, hi=split_x2 - 1.2)
                    dw_x_r = (split_x2 + ix_max) * 0.5
                    dw_x_r = _clear_doorway_span(dw_x_r, axis='X', lo=split_x2 + 1.2, hi=ix_max - 1.2)

                    interior_walls.pop()  # remove single-door col_top wall
                    interior_walls.append({
                        'p1': (ix_min, _col_top), 'p2': (split_x2, _col_top),
                        'axis': 'X', 'pos': _col_top, 'thickness': wall_t,
                        'doorway': {'x': dw_x_l, 'y': _col_top, 'w': min(dw_w, 1.35), 'h': dw_h, 'axis': 'X'}
                    })
                    interior_walls.append({
                        'p1': (split_x2, _col_top), 'p2': (ix_max, _col_top),
                        'axis': 'X', 'pos': _col_top, 'thickness': wall_t,
                        'doorway': {'x': dw_x_r, 'y': _col_top, 'w': min(dw_w, 1.35), 'h': dw_h, 'axis': 'X'}
                    })
                    interior_walls.append({
                        'p1': (split_x2, _col_top), 'p2': (split_x2, iy_max),
                        'axis': 'Y', 'pos': split_x2, 'thickness': wall_t,
                    })

                    rm_landing.doorways = [
                        {'x': dw_x_l, 'y': _col_top, 'axis': 'X', 'w': min(dw_w, 1.35)},
                        {'x': dw_x_r, 'y': _col_top, 'axis': 'X', 'w': min(dw_w, 1.35)},
                    ]
                    rm_bed_l = Room(
                        id=f"fl{fl_idx}_bed_w", floor_idx=fl_idx, role='MASTER_BED' if fl_idx <= 1 else 'BEDROOM',
                        bounds=(ix_min, split_x2, _col_top, iy_max),
                        doorways=[{'x': dw_x_l, 'y': _col_top, 'axis': 'X', 'w': min(dw_w, 1.35)}],
                        stair_hole=None,
                        exterior_facades={'LEFT': (_col_top, iy_max), 'BACK': (ix_min, split_x2)}
                    )
                    _is_art = (effective_archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                                                      'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER',
                                                      'FURNITURE_MAKER', 'HUNTER') or effective_archetype.startswith('ARTISAN'))
                    _r_role = ('KITCHEN' if _is_art and fl_idx <= 1 else ('BEDROOM' if fl_idx <= 1 else 'GUEST_ROOM'))
                    rm_bed_r = Room(
                        id=f"fl{fl_idx}_bed_e", floor_idx=fl_idx, role=_r_role,
                        bounds=(split_x2, ix_max, _col_top, iy_max),
                        doorways=[{'x': dw_x_r, 'y': _col_top, 'axis': 'X', 'w': min(dw_w, 1.35)}],
                        stair_hole=None,
                        exterior_facades={'RIGHT': (_col_top, iy_max), 'BACK': (split_x2, ix_max)}
                    )
                    rooms = [rm_landing, rm_bed_l, rm_bed_r]
                else:
                    # Single chamber behind landing
                    rm_role = 'MASTER_BED' if fl_idx <= 1 else 'BEDROOM'
                    rm_chamber = Room(
                        id=f"fl{fl_idx}_chamber", floor_idx=fl_idx, role=rm_role,
                        bounds=(ix_min, ix_max, _col_top, iy_max),
                        doorways=[{'x': dw_x, 'y': _col_top, 'axis': 'X', 'w': dw_w_eff}],
                        stair_hole=None,
                        exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (_col_top, iy_max), 'RIGHT': (_col_top, iy_max)}
                    )
                    rooms = [rm_landing, rm_chamber]
            elif avail_d < 6.8 or avail_w < 6.8 or partition_style == 'TWO_ROOMS':
                # Two chambers divided along Y (front-to-back): Middle Salon + Rear Bedroom
                split_y2 = (_col_top + iy_max) * 0.5
                split_y2 = _clear_doorway_span(split_y2, axis='Y', lo=_col_top + 2.0, hi=iy_max - 2.0)
                split_y2 = _dodge_oven_band(split_y2, _col_top + 2.0, iy_max - 2.0)
                dw_x2 = (ix_min + ix_max) * 0.5
                dw_x2 = _clear_doorway_span(dw_x2, axis='X', lo=ix_min + 1.8, hi=ix_max - 1.8)
                interior_walls.append({
                    'p1': (ix_min, split_y2), 'p2': (ix_max, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t,
                    'doorway': {'x': dw_x2, 'y': split_y2, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                })
                _is_art = (effective_archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                                                  'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER',
                                                  'FURNITURE_MAKER', 'HUNTER') or effective_archetype.startswith('ARTISAN'))
                if _is_art and fl_idx <= 1:
                    role_mid = 'KITCHEN'
                    role_rear = 'MASTER_BED'
                else:
                    role_mid = 'HOUSE_HALL' if fl_idx <= 1 else ('MASTER_BED' if total_floors > 2 else 'BEDROOM')
                    role_rear = 'MASTER_BED' if fl_idx <= 1 else 'BEDROOM'
                rm_mid = Room(
                    id=f"fl{fl_idx}_salon", floor_idx=fl_idx, role=role_mid,
                    bounds=(ix_min, ix_max, _col_top, split_y2),
                    doorways=[{'x': dw_x, 'y': _col_top, 'axis': 'X', 'w': dw_w_eff},
                              {'x': dw_x2, 'y': split_y2, 'axis': 'X', 'w': dw_w}],
                    stair_hole=None,
                    exterior_facades={'LEFT': (_col_top, split_y2), 'RIGHT': (_col_top, split_y2)}
                )
                rm_rear = Room(
                    id=f"fl{fl_idx}_bed", floor_idx=fl_idx, role=role_rear,
                    bounds=(ix_min, ix_max, split_y2, iy_max),
                    doorways=[{'x': dw_x2, 'y': split_y2, 'axis': 'X', 'w': dw_w}],
                    stair_hole=None,
                    exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (split_y2, iy_max), 'RIGHT': (split_y2, iy_max)}
                )
                rooms = [rm_landing, rm_mid, rm_rear]
            else:
                # Large deep floor (e.g. Tailor 8m x 16.5m):
                # Middle Living Salon / Fitting Parlor + Two Private Rear Chambers!
                split_y2 = _col_top + avail_d * 0.48
                split_y2 = _clear_doorway_span(split_y2, axis='Y', lo=_col_top + 2.8, hi=iy_max - 3.0)
                split_y2 = _dodge_oven_band(split_y2, _col_top + 2.8, iy_max - 3.0)

                split_x2 = (ix_min + ix_max) * 0.5
                split_x2 = _clear_doorway_span(split_x2, axis='X', lo=ix_min + 2.8, hi=ix_max - 2.8)

                dw_x_l = (ix_min + split_x2) * 0.5
                dw_x_l = _clear_doorway_span(dw_x_l, axis='X', lo=ix_min + 1.2, hi=split_x2 - 1.2)
                dw_x_r = (split_x2 + ix_max) * 0.5
                dw_x_r = _clear_doorway_span(dw_x_r, axis='X', lo=split_x2 + 1.2, hi=ix_max - 1.2)

                # Cross-partition wall at split_y2 with doorways into each rear chamber
                interior_walls.append({
                    'p1': (ix_min, split_y2), 'p2': (split_x2, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t,
                    'doorway': {'x': dw_x_l, 'y': split_y2, 'w': min(dw_w, 1.40), 'h': dw_h, 'axis': 'X'}
                })
                interior_walls.append({
                    'p1': (split_x2, split_y2), 'p2': (ix_max, split_y2),
                    'axis': 'X', 'pos': split_y2, 'thickness': wall_t,
                    'doorway': {'x': dw_x_r, 'y': split_y2, 'w': min(dw_w, 1.40), 'h': dw_h, 'axis': 'X'}
                })
                # Vertical dividing wall between the two rear chambers
                interior_walls.append({
                    'p1': (split_x2, split_y2), 'p2': (split_x2, iy_max),
                    'axis': 'Y', 'pos': split_x2, 'thickness': wall_t,
                })

                _is_art = (effective_archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                                                  'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER',
                                                  'FURNITURE_MAKER', 'HUNTER') or effective_archetype.startswith('ARTISAN'))
                if _is_art and fl_idx <= 1:
                    role_mid = 'HOUSE_HALL'
                    role_l = 'MASTER_BED'
                    role_r = 'KITCHEN'
                else:
                    role_mid = 'HOUSE_HALL' if fl_idx <= 1 else ('MASTER_BED' if total_floors > 2 else 'BEDROOM')
                    role_l = 'MASTER_BED' if fl_idx <= 1 else 'BEDROOM'
                    role_r = 'BEDROOM' if fl_idx <= 1 else 'GUEST_ROOM'

                rm_salon = Room(
                    id=f"fl{fl_idx}_salon", floor_idx=fl_idx, role=role_mid,
                    bounds=(ix_min, ix_max, _col_top, split_y2),
                    doorways=[
                        {'x': dw_x, 'y': _col_top, 'axis': 'X', 'w': dw_w_eff},
                        {'x': dw_x_l, 'y': split_y2, 'axis': 'X', 'w': min(dw_w, 1.40)},
                        {'x': dw_x_r, 'y': split_y2, 'axis': 'X', 'w': min(dw_w, 1.40)},
                    ],
                    stair_hole=None,
                    exterior_facades={'LEFT': (_col_top, split_y2), 'RIGHT': (_col_top, split_y2)}
                )
                rm_bed_l = Room(
                    id=f"fl{fl_idx}_bed_w", floor_idx=fl_idx, role=role_l,
                    bounds=(ix_min, split_x2, split_y2, iy_max),
                    doorways=[{'x': dw_x_l, 'y': split_y2, 'axis': 'X', 'w': min(dw_w, 1.40)}],
                    stair_hole=None,
                    exterior_facades={'LEFT': (split_y2, iy_max), 'BACK': (ix_min, split_x2)}
                )
                rm_bed_r = Room(
                    id=f"fl{fl_idx}_bed_e", floor_idx=fl_idx, role=role_r,
                    bounds=(split_x2, ix_max, split_y2, iy_max),
                    doorways=[{'x': dw_x_r, 'y': split_y2, 'axis': 'X', 'w': min(dw_w, 1.40)}],
                    stair_hole=None,
                    exterior_facades={'RIGHT': (split_y2, iy_max), 'BACK': (split_x2, ix_max)}
                )
                rooms = [rm_landing, rm_salon, rm_bed_l, rm_bed_r]
        elif _deep_splits is None:
            _deep_target = 2
            roles = _resolve_room_roles(effective_archetype, fl_idx, 2, has_stairs_landing, total_floors, program=program)
            sy_b = (stair_pos_info or {}).get('y_bot', stair_hole[2] if stair_hole is not None else None)
            sy_t = (stair_pos_info or {}).get('y_top', stair_hole[3] if stair_hole is not None else None)
            if sy_b is not None and sy_t is not None:
                pad_2rm = 2.00
                _hh0 = min(sy_b, sy_t) - pad_2rm
                _hh1 = max(sy_b, sy_t) + pad_2rm
            elif stair_hole is not None:
                _hh0, _hh1 = stair_hole[2] - 1.80, stair_hole[3] + 1.80
            else:
                _hh0 = _hh1 = None

            if stair_guards_north:
                split_y = min((_hh0 if _hh0 is not None else (stair_safe_y_bot - 0.65)), iy_min + D * 0.48)
                split_y = max(iy_min + 2.3, split_y)
            else:
                split_y = max((_hh1 if _hh1 is not None else (stair_safe_y_top + 0.65)), iy_min + D * 0.48)
                split_y = min(iy_max - 2.3, split_y)
            split_y = _clear_doorway_span(split_y, axis='Y',
                                          lo=iy_min + 2.3, hi=iy_max - 1.8)
            split_y = _dodge_oven_band(split_y, iy_min + 2.3, iy_max - 1.8)
            if _hh0 is not None:
                if _hh0 < split_y < _hh1:
                    split_y = _hh0 if (split_y - _hh0) <= (_hh1 - split_y) else _hh1
                    split_y = min(max(split_y, iy_min + 2.3), iy_max - 1.8)

            d_front = split_y - iy_min
            d_back = iy_max - split_y
            ar_x = max(W / max(d_front, 0.5), W / max(d_back, 0.5), max(d_front, d_back) / max(W, 0.5))

            # Evaluate whether splitting the other cardinal direction (Y - vertical wall)
            # gives squarer rooms, avoiding two wide shallow corridor strips across the building width.
            stair_on_right = bool(
                (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
                or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
            )
            if stair_on_right:
                stair_w = float((stair_pos_info or {}).get('w', 1.2) or 1.2)
                stair_cx = float((stair_pos_info or {}).get('cx', ix_max - 1.4) or (ix_max - 1.4))
                stair_safe_x_left = stair_cx - stair_w * 0.5 - 0.20
                max_split_x = stair_safe_x_left - 1.00
                cand_split_x = min(max_split_x, (ix_min + ix_max) * 0.50)
                cand_split_x = max(ix_min + 2.3, cand_split_x)
                can_split_y = (cand_split_x >= ix_min + 2.2 and ix_max - cand_split_x >= 2.2 and max_split_x >= ix_min + 2.2)
            else:
                min_split_x = stair_safe_x + 1.00
                cand_split_x = max(min_split_x, (ix_min + ix_max) * 0.50)
                cand_split_x = min(ix_max - 2.3, cand_split_x)
                can_split_y = (cand_split_x <= ix_max - 2.2 and cand_split_x - ix_min >= 2.2 and min_split_x <= ix_max - 2.2)

            if can_split_y:
                w_left = cand_split_x - ix_min
                w_right = ix_max - cand_split_x
                ar_y = max(D / max(w_left, 0.5), D / max(w_right, 0.5), max(w_left, w_right) / max(D, 0.5))
            else:
                ar_y = 999.0

            do_y_split = can_split_y and (ar_y < ar_x * 0.90 or (W >= D * 1.15 and ar_y <= 2.2))

            if do_y_split:
                split_x = _clear_doorway_span(cand_split_x, axis='X', lo=ix_min + 2.0, hi=ix_max - 2.0)
                if has_stairs_landing and stair_pos_info:
                    if stair_guards_north:
                        dw_y = min(iy_max - 1.8, max(iy_min + 1.8, (stair_safe_y_top + iy_max) * 0.5))
                    else:
                        dw_y = min(iy_max - 1.8, max(iy_min + 1.8, (iy_min + stair_safe_y_bot) * 0.5))
                else:
                    dw_y = (iy_min + iy_max) * 0.5
                dw_y = _clear_doorway_span(dw_y, axis='Y', lo=iy_min + 1.8, hi=iy_max - 1.8)
                dw_y = _dodge_oven_band(dw_y, iy_min + 1.8, iy_max - 1.8)

                interior_walls.append({
                    'p1': (split_x, iy_min), 'p2': (split_x, iy_max),
                    'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                    'doorway': {'x': split_x, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                })

                if stair_on_right:
                    west_role = roles[1] if has_stairs_landing else roles[0]
                    east_role = roles[0] if has_stairs_landing else roles[1]
                else:
                    west_role = roles[0] if has_stairs_landing else roles[0]
                    east_role = roles[1] if has_stairs_landing else roles[1]

                if east_role == 'STAIR_LANDING' and not stair_on_right:
                    _pool2 = _resolve_room_roles(effective_archetype, fl_idx, 2, False, total_floors, program=program)
                    east_role = next((r for r in reversed(_pool2) if r != 'STAIR_LANDING'), None) or 'BEDROOM'
                if west_role == 'STAIR_LANDING' and stair_on_right:
                    _pool2 = _resolve_room_roles(effective_archetype, fl_idx, 2, False, total_floors, program=program)
                    west_role = next((r for r in reversed(_pool2) if r != 'STAIR_LANDING'), None) or 'BEDROOM'

                rm0 = Room(
                    id=f"fl{fl_idx}_west", floor_idx=fl_idx, role=west_role,
                    bounds=(ix_min, split_x, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, split_x, iy_min, iy_max)),
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_east", floor_idx=fl_idx, role=east_role,
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=_holds_stair((split_x, ix_max, iy_min, iy_max)),
                    exterior_facades={'FRONT': (split_x, ix_max), 'BACK': (split_x, ix_max), 'RIGHT': (iy_min, iy_max)}
                )
                rooms = [rm0, rm1]
            else:
                if stair_pos_info and (stair_hole is not None or getattr(props, 'has_stairs', False)):
                    if stair_safe_x < (ix_min + ix_max) * 0.5:
                        dw_x = (stair_safe_x + ix_max) * 0.5
                    else:
                        dw_x = (ix_min + stair_safe_x) * 0.5
                else:
                    dw_x = (ix_min + ix_max) * 0.5
                if door_cx is not None and abs(dw_x - door_cx) < 0.4:
                    dw_x += 0.85
                dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.2, hi=ix_max - 1.2)

                interior_walls.append({
                    'p1': (ix_min, split_y), 'p2': (ix_max, split_y),
                    'axis': 'X', 'pos': split_y, 'thickness': wall_t,
                    'doorway': {'x': dw_x, 'y': split_y, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                })
                # The stairs sit in whichever room the partition left them in.
                front_role = ('STAIR_LANDING' if (has_stairs_landing and not stair_guards_north)
                              else (roles[1] if has_stairs_landing else roles[0]))
                back_role = ('STAIR_LANDING' if (has_stairs_landing and stair_guards_north)
                             else (roles[0] if has_stairs_landing else roles[1]))
                # Never leave the second band ALSO a bare landing — when the stair
                # takes the front band, the band behind it must become a real room.
                if back_role == 'STAIR_LANDING':
                    _pool2 = _resolve_room_roles(effective_archetype, fl_idx, 2, False,
                                                 total_floors, program=program)
                    _pick = next((r for r in reversed(_pool2) if r != 'STAIR_LANDING'), None)
                    back_role = _pick or 'BEDROOM'
                # A turned staircase leaves only one room behind it here: make it a
                # single combined living area (hearth, bed and kitchen corner).
                # Upper floors only — the ground floor keeps its trade workshop.
                if _turn_layout and fl_idx > 0 and _deep_target <= 2:
                    back_role = 'COTTAGE'

                rm0 = Room(
                    id=f"fl{fl_idx}_front", floor_idx=fl_idx, role=front_role,
                    bounds=(ix_min, ix_max, iy_min, split_y),
                    doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, ix_max, iy_min, split_y)),
                    exterior_facades={'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, split_y), 'RIGHT': (iy_min, split_y)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_back", floor_idx=fl_idx, role=back_role,
                    bounds=(ix_min, ix_max, split_y, iy_max),
                    doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
                    stair_hole=_holds_stair((ix_min, ix_max, split_y, iy_max)),
                    exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (split_y, iy_max), 'RIGHT': (split_y, iy_max)}
                )
                rooms = [rm0, rm1]
        else:
            _n = len(_deep_splits) + 1
            roles = _resolve_room_roles(effective_archetype, fl_idx, _n, has_stairs_landing, total_floors, program=program)
            _room_roles = list(roles[:_n])
            while len(_room_roles) < _n:
                _room_roles.append(_room_roles[-1] if _room_roles else 'STORAGE')
            _bounds = [(iy_min, _deep_splits[0])]
            _bounds += [(_deep_splits[i], _deep_splits[i + 1]) for i in range(len(_deep_splits) - 1)]
            _bounds += [(_deep_splits[-1], iy_max)]
            # The band holding the stairwell serves as the landing.
            if has_stairs_landing and stair_hole is not None and 'STAIR_LANDING' in _room_roles:
                _hb = None
                for _bi, (_b0, _b1) in enumerate(_bounds):
                    if _b0 - 0.3 <= stair_hole[2] and stair_hole[3] <= _b1 + 0.3:
                        _hb = _bi
                        break
                if _hb is None:
                    _hc = (stair_hole[2] + stair_hole[3]) * 0.5
                    for _bi, (_b0, _b1) in enumerate(_bounds):
                        if _b0 - 0.3 <= _hc <= _b1 + 0.3:
                            _hb = _bi
                            break
                if _hb is not None:
                    _li = _room_roles.index('STAIR_LANDING')
                    if _li != _hb:
                        _room_roles[_li], _room_roles[_hb] = _room_roles[_hb], _room_roles[_li]

            if stair_pos_info and (stair_hole is not None or getattr(props, 'has_stairs', False)):
                if stair_safe_x < (ix_min + ix_max) * 0.5:
                    dw_x = (stair_safe_x + ix_max) * 0.5
                else:
                    dw_x = (ix_min + stair_safe_x) * 0.5
            else:
                dw_x = (ix_min + ix_max) * 0.5
            if door_cx is not None and abs(dw_x - door_cx) < 0.4:
                dw_x += 0.85
            dw_x = _clear_doorway_span(dw_x, axis='X', lo=ix_min + 1.2, hi=ix_max - 1.2)

            rooms = []
            for _bi, (_b0, _b1) in enumerate(_bounds):
                if _bi > 0:
                    interior_walls.append({
                        'p1': (ix_min, _b0), 'p2': (ix_max, _b0),
                        'axis': 'X', 'pos': _b0, 'thickness': wall_t,
                        'doorway': {'x': dw_x, 'y': _b0, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                    })
                _doors = []
                if _bi > 0:
                    _doors.append({'x': dw_x, 'y': _b0, 'axis': 'X', 'w': dw_w})
                if _bi < _n - 1:
                    _doors.append({'x': dw_x, 'y': _b1, 'axis': 'X', 'w': dw_w})
                _fac = {'LEFT': (_b0, _b1), 'RIGHT': (_b0, _b1)}
                if _bi == 0:
                    _fac['FRONT'] = (ix_min, ix_max)
                if _bi == _n - 1:
                    _fac['BACK'] = (ix_min, ix_max)
                rooms.append(Room(
                    id=f"fl{fl_idx}_band{_bi}", floor_idx=fl_idx, role=_room_roles[_bi],
                    bounds=(ix_min, ix_max, _b0, _b1),
                    doorways=_doors,
                    stair_hole=_holds_stair((ix_min, ix_max, _b0, _b1)),
                    exterior_facades=_fac
                ))
        _force_bakehouse_chamber(rooms)

    # Add any wing rooms (the exterior-entrance tenement layout above already
    # created its own wing apartments, so never add duplicates).
    if fl_wings_bounds and not (effective_archetype == 'TENEMENT'
                                and getattr(props, 'has_exterior_stairs', False)):
        for wi, wb in enumerate(fl_wings_bounds):
            # Never duplicate a wing room that a specialised branch already made
            # (Inn/Tavern only; tenements keep their own wing apartments).
            if (effective_archetype in ('TAVERN', 'INN')
                    and any(getattr(r, 'is_wing', False) and getattr(r, 'wing_id', None) == wi
                            for r in rooms)):
                continue
            if effective_archetype in ('TAVERN', 'INN'):
                # Ground-floor wing = service KITCHEN; upstairs = guest lodging.
                # _inn_roles[1] is KITCHEN on the ground floor and GUEST_ROOM
                # above; [0] is the taproom/stair-landing that belongs in the
                # main block, never in the wing.
                _inn_roles = _resolve_room_roles(
                    effective_archetype, fl_idx, 2, fl_idx > 0, total_floors,
                    program=program)
                w_role = (_inn_roles[1] if len(_inn_roles) > 1
                          else ('GUEST_ROOM' if fl_idx > 0 else 'KITCHEN'))
                # A real doorway in the shared facade wall, recorded on both the
                # wing and the main room so the kitchen/lodging is reachable.
                wx1, wx2, wy1, wy2 = wb
                _px = (wx1 + wx2) * 0.5
                _py = (wy1 + wy2) * 0.5
                _axis = None
                _wall_y = _wall_x = None
                if wy2 <= iy_min + 0.35:
                    _axis, _wall_y = 'X', iy_min
                elif wy1 >= iy_max - 0.35:
                    _axis, _wall_y = 'X', iy_max
                elif wx2 <= ix_min + 0.35:
                    _axis, _wall_x = 'Y', ix_min
                elif wx1 >= ix_max - 0.35:
                    _axis, _wall_x = 'Y', ix_max
                # Pick the main room that actually fronts this wing portal, not
                # the largest room on the floor (the stair landing used to
                # swallow the wing door, leaving the wing cut off at a wall).
                _main_rm = None
                if _axis == 'X' and _wall_y is not None:
                    _cand = [r for r in rooms
                             if not getattr(r, 'is_wing', False)
                             and min(abs(r.bounds[2] - _wall_y),
                                     abs(r.bounds[3] - _wall_y)) <= 0.40]
                    _main_rm = next(
                        (r for r in _cand if r.bounds[0] - 0.05 <= _px <= r.bounds[1] + 0.05),
                        min(_cand, key=lambda r: abs((r.bounds[0] + r.bounds[1]) * 0.5 - _px),
                            default=None) if _cand else None)
                elif _axis == 'Y' and _wall_x is not None:
                    _cand = [r for r in rooms
                             if not getattr(r, 'is_wing', False)
                             and min(abs(r.bounds[0] - _wall_x),
                                     abs(r.bounds[1] - _wall_x)) <= 0.40]
                    _main_rm = next(
                        (r for r in _cand if r.bounds[2] - 0.05 <= _py <= r.bounds[3] + 0.05),
                        min(_cand, key=lambda r: abs((r.bounds[2] + r.bounds[3]) * 0.5 - _py),
                            default=None) if _cand else None)
                _dw = None
                if _main_rm is not None:
                    if _axis == 'X':
                        _dw = {'x': min(max(_px, _main_rm.bounds[0] + 0.85),
                                        _main_rm.bounds[1] - 0.85),
                               'y': _wall_y, 'axis': 'X',
                               'w': min(dw_w, max(1.2, wx2 - wx1 - 1.2))}
                    else:
                        _dw = {'x': _wall_x,
                               'y': min(max(_py, _main_rm.bounds[2] + 0.85),
                                        _main_rm.bounds[3] - 0.85),
                               'axis': 'Y',
                               'w': min(dw_w, max(1.2, wy2 - wy1 - 1.2))}
                    if _dw is not None:
                        if _dw not in _main_rm.doorways:
                            _main_rm.doorways.append(_dw)
                w_doorways = [_dw] if _dw is not None else []
            elif effective_archetype == 'TENEMENT' and shape == 'U_SHAPE':
                # Independent apartment suite in the wing with its own exterior entrance
                wx1, wx2, wy1, wy2 = wb
                w_depth = wy2 - wy1
                w_dws = [dw for dw in (doorways or []) if (wx1 - 0.4 <= dw.get('x', 0.0) <= wx2 + 0.4 and wy1 - 0.4 <= dw.get('y', 0.0) <= wy2 + 0.4)]
                if w_depth >= 5.5:
                    split_wy = (wy1 + wy2) * 0.5
                    dw_wx = (wx1 + wx2) * 0.5
                    interior_walls.append({
                        'p1': (wx1, split_wy), 'p2': (wx2, split_wy),
                        'axis': 'X', 'pos': split_wy, 'thickness': wall_t,
                        'doorway': {'x': dw_wx, 'y': split_wy, 'w': dw_w, 'h': dw_h, 'axis': 'X'}
                    })
                    rm_k = Room(
                        id=f"fl{fl_idx}_apt_wing{wi}_kitchen", floor_idx=fl_idx, role='TENEMENT_KITCHEN',
                        bounds=(wx1, wx2, wy1, split_wy),
                        doorways=w_dws + [{'x': dw_wx, 'y': split_wy, 'axis': 'X', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'FRONT': (wx1, wx2)}
                    )
                    rm_b = Room(
                        id=f"fl{fl_idx}_apt_wing{wi}_bed", floor_idx=fl_idx, role='TENEMENT_BEDROOM',
                        bounds=(wx1, wx2, split_wy, wy2),
                        doorways=[{'x': dw_wx, 'y': split_wy, 'axis': 'X', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'BACK': (wx1, wx2)}
                    )
                    rooms.extend([rm_k, rm_b])
                else:
                    rm_w = Room(
                        id=f"fl{fl_idx}_apt_wing{wi}", floor_idx=fl_idx, role='TENEMENT_KITCHEN',
                        bounds=wb, is_wing=True, wing_id=wi, doorways=w_dws, stair_hole=None, exterior_facades={}
                    )
                    rooms.append(rm_w)
                continue
            elif effective_archetype == 'TENEMENT':
                # Each wing is an extra bedroom of the adjacent apartment
                # (never an orphan kitchen); its portal is its doorway.
                w_role = 'TENEMENT_BEDROOM'
                w_doorways = _wing_portals(wb, doorways)
            elif effective_archetype == 'MANOR':
                if fl_idx == 0:
                    w_role = 'STUDY' if wi == 0 else 'GUEST_ROOM'
                else:
                    w_role = 'BEDROOM' if wi == 0 else 'GUEST_ROOM'
                w_doorways = _wing_portals(wb, doorways)
            elif effective_archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
                w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'MAYOR_OFFICE'
                w_doorways = _wing_portals(wb, doorways)
            elif effective_archetype in ('KNIGHTS_MANOR',):
                w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'BARRACKS_DORM'
                w_doorways = _wing_portals(wb, doorways)
            elif effective_archetype in ('BARRACKS', 'INFANTRY_BARRACKS',
                                         'ARCHERY', 'ARCHERY_RANGE'):
                w_role = 'ENTRANCE_HALL' if (fl_idx == 0 and wi == 0 and getattr(props, 'wing_placement', '') == 'FRONT') else 'BARRACKS_DORM'
                w_doorways = _wing_portals(wb, doorways)
            else:
                w_role = 'STORAGE' if (fl_idx == 0 or effective_archetype in
                                       ('WAREHOUSE', 'LUMBERMILL', 'BLACKSMITH')) else 'GUEST_ROOM'
                w_doorways = list(_wing_portals(wb, doorways))
                # The warehouse cargo port is cut into the wing's courtyard-side
                # wall on the ground floor.  Register it as a doorway for the
                # room so no shelf/pile can be pushed into the portal opening.
                if (fl_idx == 0 and effective_archetype == 'WAREHOUSE'
                        and not getattr(props, 'open_timber_frame', False)
                        and not (getattr(props, 'material_tier', '') == 'TIER_1'
                                 and getattr(props, 'roof_style', '') == 'NONE')
                        and (wb[3] <= iy_min + 0.35 or wb[2] >= iy_max - 0.35)):
                    wx1, wx2, wy1, wy2 = wb
                    inner_x = wx1 if ((wx1 + wx2) * 0.5) > 0.0 else wx2
                    cp_y = wy1 + (wy2 - wy1) * 0.38
                    w_doorways.append({
                        'x': inner_x, 'y': cp_y, 'axis': 'Y',
                        'w': 2.30, 'is_cargo_port': True,
                    })
            _w_sh = None
            if stair_hole is not None:
                _shx0, _shx1, _shy0, _shy1 = stair_hole
                if not (_shx1 < wb[0] or _shx0 > wb[1]
                        or _shy1 < wb[2] or _shy0 > wb[3]):
                    _w_sh = stair_hole
            w_rm = Room(
                id=f"fl{fl_idx}_wing{wi}",
                floor_idx=fl_idx,
                role=w_role,
                bounds=wb,
                is_wing=True,
                wing_id=wi,
                doorways=w_doorways,
                stair_hole=_w_sh,
                exterior_facades={}
            )
            rooms.append(w_rm)

    if doorways:
        for rm in rooms:
            if rm.doorways is None:
                rm.doorways = []
            rx0, rx1, ry0, ry1 = rm.bounds
            for d in doorways:
                dx, dy = d.get('x', 0.0), d.get('y', 0.0)
                dw = d.get('w', 0.95)
                axis = d.get('axis', 'X')
                touches = False
                if axis == 'X':
                    touches = ((dx + dw * 0.5 >= rx0 - 0.20 and dx - dw * 0.5 <= rx1 + 0.20)
                               and (ry0 - 0.55 <= dy <= ry1 + 0.55))
                else:
                    touches = ((dy + dw * 0.5 >= ry0 - 0.20 and dy - dw * 0.5 <= ry1 + 0.20)
                               and (rx0 - 0.55 <= dx <= rx1 + 0.55))
                if not touches:
                    continue
                if effective_archetype == 'TENEMENT':
                    # The apartment planner puts its entry on the room-side
                    # face of the wall, while floors.py cuts the real door on
                    # the exterior wall line.  Snapping the two copies onto
                    # the exterior door prevents a doubled frame and keeps the
                    # room's circulation door aligned with the cut.
                    _near = next((_e for _e in rm.doorways
                                  if _e.get('axis', 'X') == axis
                                  and abs(_e.get('x', 0.0) - dx) < 0.55
                                  and abs(_e.get('y', 0.0) - dy) < 0.55), None)
                    if _near is not None:
                        _near.update(d)
                        continue
                if d not in rm.doorways:
                    rm.doorways.append(d)

    # Check if this floor has a mezzanine gallery void (double-height grand hall)
    if fl_idx == 1 and bool(getattr(props, 'has_throne_room', False) or getattr(props, 'has_double_height', False)):
        # Target the room directly above the ground floor hall / throne room
        hall_rm = next((r for r in rooms if not getattr(r, 'is_wing', False) and (r.id.endswith('_hall') or r.id.endswith('_great_hall'))), None)
        if hall_rm is None:
            hall_rm = max([r for r in rooms if not getattr(r, 'is_wing', False) and not r.id.endswith('_stair_bay')],
                          key=lambda r: (r.bounds[1] - r.bounds[0]) * (r.bounds[3] - r.bounds[2]),
                          default=None)
        if hall_rm is not None:
            v_rect = compute_mezzanine_void(hall_rm.bounds, stair_hole=stair_hole, min_rim=2.00, doorways=doorways)
            if v_rect:
                hall_rm.floor_void = v_rect
                hall_rm.role = 'MEZZANINE_GALLERY'

    # Explicit open-ground-floor halls (a deliberate single trade hall) keep
    # one open room.  Ordinary artisan houses are NOT collapsed here: their
    # ground floor must keep the real lower-floor STORE + WORKSHOP split.
    _is_artisan = (effective_archetype in _ARTISAN_GROUND or effective_archetype.startswith('ARTISAN'))
    if fl_idx == 0 and bool(getattr(props, 'open_ground_floor', False)) and not _is_artisan:
        _wings = [r for r in rooms if getattr(r, 'is_wing', False)]
        _cand = []
        for _r in rooms:
            for _d in getattr(_r, 'doorways', []) or []:
                if _d not in _cand:
                    _cand.append(_d)
        for _d in (doorways or []):
            if _d not in _cand:
                _cand.append(_d)
        # Only keep doorways on the main block's EXTERIOR edges — the doorways
        # to the now-removed side chambers would otherwise carve phantom
        # corridors through the open shop.
        def _on_edge(_d):
            _dx, _dy = _d.get('x', 1e9), _d.get('y', 1e9)
            return (abs(_dx - ix_min) < 0.9 or abs(_dx - ix_max) < 0.9
                    or abs(_dy - iy_min) < 0.9 or abs(_dy - iy_max) < 0.9)
        _all_dw = [_d for _d in _cand if _on_edge(_d)]
        if front_door_info:
            _fdw = {'x': front_door_info[0], 'y': iy_min, 'axis': 'X',
                    'w': front_door_info[1]}
            if _fdw not in _all_dw:
                _all_dw.append(_fdw)
        _main_room = Room(
            id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role='STORE',
            bounds=(ix_min, ix_max, iy_min, iy_max),
            doorways=_all_dw, stair_hole=stair_hole,
            exterior_facades={'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                              'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)})
        rooms = [_main_room] + _wings
        interior_walls = []

    # Final safety pass: keep partitions and their door openings clear of
    # stair wells and annex portal aprons, even for specialized floor plans.
    if _clear_zones and interior_walls:
        _kept = []
        for _w in interior_walls:
            _p1, _p2 = _w['p1'], _w['p2']
            _ax = 'X' if abs(_p1[1] - _p2[1]) < 1e-6 else 'Y'
            _pos = _p1[1] if _ax == 'X' else _p1[0]
            _a0, _a1 = (_p1[0], _p2[0]) if _ax == 'X' else (_p1[1], _p2[1])
            _lo, _hi = min(_a0, _a1), max(_a0, _a1)
            _n0, _n1 = _clip_to_zones(_ax, _pos, _lo, _hi)
            if _n1 - _n0 < 1.0:
                continue
            if (_n0, _n1) != (_lo, _hi):
                _w = dict(_w)
                if _ax == 'X':
                    _w['p1'] = (_n0, _p1[1])
                    _w['p2'] = (_n1, _p2[1])
                else:
                    _w['p1'] = (_p1[0], _n0)
                    _w['p2'] = (_p2[0], _n1)
                _dw = _w.get('doorway')
                if _dw:
                    _du = _dw.get('x') if _ax == 'X' else _dw.get('y')
                    _dh = (_dw.get('w', 1.0) or 1.0) * 0.5
                    if _du is None or not (_n0 + _dh <= _du <= _n1 - _dh):
                        _nu = (_n0 + _n1) * 0.5
                        if _ax == 'X':
                            _dw['x'] = _nu
                        else:
                            _dw['y'] = _nu
            _kept.append(_w)
        interior_walls = _kept
    # Late proportion pass covers specialized layouts as well. Leave explicitly
    # ceremonial/social rooms expansive, while splitting oversized private rooms
    # and long narrow rooms into useful, reachable spaces.  Tenements are already
    # composed of self-contained apartments (own entrance + kitchen + bedroom),
    # so they must never be subdivided by this generic pass.
    if effective_archetype != 'TENEMENT':
        rooms = _recut_oversized_rooms(
            rooms, interior_walls, bounds, wall_t, dw_w, dw_h,
            effective_archetype, fl_idx, has_stairs_landing, total_floors, program,
            clear_zone_rects=clear_zone_rects)
    # Fold unusable thin strips back into a real room (and remove the partition
    # that made them) so walls never end abruptly or block a wing doorway.
    rooms = _merge_sliver_rooms(rooms, interior_walls)
    _extend_wall_ends_to_bounds(interior_walls, (ix_min, ix_max, iy_min, iy_max))
    # All layout branches converge here. A room holding the stair landing, or
    # serving as a two-door route between rooms, is circulation—not a bedroom.
    # One-room small floors remain the intentional combined-cottage exception.
    # Wing portals are wide openings in the main facade.  A perpendicular
    # partition that ends on that facade inside the wing's span splits the
    # entrance in half (Knights Manor T-wing).  Pull such wall ends 1.8 m into
    # the room so the opening reads as one clear vestibule.
    if fl_wings_bounds and effective_archetype == 'KNIGHTS_MANOR':
        _drop_walls = []
        for w in interior_walls:
            _p1, _p2 = w.get('p1'), w.get('p2')
            if not _p1 or not _p2:
                continue
            _ax = w.get('axis')
            _pos = w.get('pos', 0.0)
            for wb in fl_wings_bounds:
                try:
                    wx0, wx1, wy0, wy1 = (float(wb[0]), float(wb[1]),
                                          float(wb[2]), float(wb[3]))
                except Exception:
                    continue
                _trim = 0.12
                _changed = False
                if wy1 <= iy_min + 0.35 and _ax == 'Y' and wx0 + 0.20 < _pos < wx1 - 0.20:
                    for _k in (0, 1):
                        _pt = _p1 if _k == 0 else _p2
                        if abs(_pt[1] - iy_min) < 0.25:
                            _new = (_pt[0], iy_min + _trim)
                            if _k == 0:
                                _p1 = _new
                            else:
                                _p2 = _new
                            _changed = True
                elif wy0 >= iy_max - 0.35 and _ax == 'Y' and wx0 + 0.20 < _pos < wx1 - 0.20:
                    for _k in (0, 1):
                        _pt = _p1 if _k == 0 else _p2
                        if abs(_pt[1] - iy_max) < 0.25:
                            _new = (_pt[0], iy_max - _trim)
                            if _k == 0:
                                _p1 = _new
                            else:
                                _p2 = _new
                            _changed = True
                elif wx1 <= ix_min + 0.35 and _ax == 'X' and wy0 + 0.20 < _pos < wy1 - 0.20:
                    for _k in (0, 1):
                        _pt = _p1 if _k == 0 else _p2
                        if abs(_pt[0] - ix_min) < 0.25:
                            _new = (ix_min + _trim, _pt[1])
                            if _k == 0:
                                _p1 = _new
                            else:
                                _p2 = _new
                            _changed = True
                elif wx0 >= ix_max - 0.35 and _ax == 'X' and wy0 + 0.20 < _pos < wy1 - 0.20:
                    for _k in (0, 1):
                        _pt = _p1 if _k == 0 else _p2
                        if abs(_pt[0] - ix_max) < 0.25:
                            _new = (ix_max - _trim, _pt[1])
                            if _k == 0:
                                _p1 = _new
                            else:
                                _p2 = _new
                            _changed = True
                if _changed:
                    _len = math.hypot(_p2[0] - _p1[0], _p2[1] - _p1[1])
                    if _len < 0.8:
                        _drop_walls.append(w)
                    else:
                        w['p1'], w['p2'] = _p1, _p2
                        _dw = w.get('doorway')
                        if _dw:
                            _coord = _dw.get('y', 0.0) if _dw.get('axis') == 'Y' else _dw.get('x', 0.0)
                            _lo = min(_p1[1], _p2[1]) if _dw.get('axis') == 'Y' else min(_p1[0], _p2[0])
                            _hi = max(_p1[1], _p2[1]) if _dw.get('axis') == 'Y' else max(_p1[0], _p2[0])
                            if not (_lo - 0.05 <= _coord <= _hi + 0.05):
                                if _dw.get('axis') == 'Y':
                                    _dw['y'] = (_lo + _hi) * 0.5
                                else:
                                    _dw['x'] = (_lo + _hi) * 0.5
                    break
        if _drop_walls:
            interior_walls[:] = [w for w in interior_walls if w not in _drop_walls]

    # Same issue at ordinary exterior entrances: a partition that ends on the
    # facade inside the front/back/side door span visually splits the doorway.
    if doorways:
        _facade_spans = {'FRONT': [], 'BACK': [], 'LEFT': [], 'RIGHT': []}
        for _d in (doorways or []):
            _dax = _d.get('axis', 'X')
            _dc = _d.get('x', 0.0) if _dax == 'X' else _d.get('y', 0.0)
            _dw = float(_d.get('w', 1.5) or 1.5)
            if _dax == 'X':
                if abs(_d.get('y', 0.0) - iy_min) < 0.45:
                    _facade_spans['FRONT'].append((_dc - _dw * 0.5, _dc + _dw * 0.5))
                elif abs(_d.get('y', 0.0) - iy_max) < 0.45:
                    _facade_spans['BACK'].append((_dc - _dw * 0.5, _dc + _dw * 0.5))
            else:
                if abs(_d.get('x', 0.0) - ix_min) < 0.45:
                    _facade_spans['LEFT'].append((_dc - _dw * 0.5, _dc + _dw * 0.5))
                elif abs(_d.get('x', 0.0) - ix_max) < 0.45:
                    _facade_spans['RIGHT'].append((_dc - _dw * 0.5, _dc + _dw * 0.5))
        _drop_doors = []
        for w in interior_walls:
            _p1, _p2 = w.get('p1'), w.get('p2')
            if not _p1 or not _p2:
                continue
            _ax = w.get('axis')
            _pos = w.get('pos', 0.0)
            _trim = 0.12
            _changed = False
            if _ax == 'Y' and any(_s0 - 0.35 <= _pos <= _s1 + 0.35
                                  for _s0, _s1 in _facade_spans['FRONT']):
                if abs(_p1[1] - iy_min) < 0.25:
                    _p1 = (_p1[0], iy_min + _trim); _changed = True
                elif abs(_p2[1] - iy_min) < 0.25:
                    _p2 = (_p2[0], iy_min + _trim); _changed = True
            elif _ax == 'Y' and any(_s0 - 0.35 <= _pos <= _s1 + 0.35
                                    for _s0, _s1 in _facade_spans['BACK']):
                if abs(_p1[1] - iy_max) < 0.25:
                    _p1 = (_p1[0], iy_max - _trim); _changed = True
                elif abs(_p2[1] - iy_max) < 0.25:
                    _p2 = (_p2[0], iy_max - _trim); _changed = True
            elif _ax == 'X' and any(_s0 - 0.35 <= _pos <= _s1 + 0.35
                                    for _s0, _s1 in _facade_spans['LEFT']):
                if abs(_p1[0] - ix_min) < 0.25:
                    _p1 = (ix_min + _trim, _p1[1]); _changed = True
                elif abs(_p2[0] - ix_min) < 0.25:
                    _p2 = (ix_min + _trim, _p2[1]); _changed = True
            elif _ax == 'X' and any(_s0 - 0.35 <= _pos <= _s1 + 0.35
                                    for _s0, _s1 in _facade_spans['RIGHT']):
                if abs(_p1[0] - ix_max) < 0.25:
                    _p1 = (ix_max - _trim, _p1[1]); _changed = True
                elif abs(_p2[0] - ix_max) < 0.25:
                    _p2 = (ix_max - _trim, _p2[1]); _changed = True
            if _changed:
                _len = math.hypot(_p2[0] - _p1[0], _p2[1] - _p1[1])
                if _len < 0.8:
                    _drop_doors.append(w)
                else:
                    w['p1'], w['p2'] = _p1, _p2
        if _drop_doors:
            interior_walls[:] = [w for w in interior_walls if w not in _drop_doors]

    if fl_wings_bounds:
        interior_walls = _open_wing_entrance_walls(
            interior_walls, fl_wings_bounds, (ix_min, ix_max, iy_min, iy_max))
    _is_estate_out = False
    try:
        _is_estate_out = bool(props.get('is_estate_outbuilding', False))
    except Exception:
        _is_estate_out = bool(getattr(props, 'is_estate_outbuilding', False))
    if _is_estate_out:
        rooms = _consolidate_outbuilding_rooms(
            rooms, interior_walls, max_habitable=(4 if fl_idx == 0 else 3))
    rooms = _merge_open_rooms(rooms, interior_walls)
    rooms = _rebalance_room_boundaries(rooms, interior_walls)

    if (effective_archetype in ('ARCHERY', 'ARCHERY_RANGE') and fl_idx == 0
            and rooms):
        rooms, interior_walls = _replan_archery_lodge_ground(
            rooms, interior_walls, bounds, stair_hole, props, doorways,
            wall_t=wall_t, dw_w=dw_w, dw_h=dw_h)

    if (effective_archetype in ('CHAPEL', 'HEALERS_CHAPEL') and fl_idx == 0
            and rooms):
        # A chapel ground floor is one preaching nave, not a maze of vestries
        # and store rooms.  Keep any wings, remove every internal partition,
        # and let the apse/altar read as the single focal piece.
        _wings = [r for r in rooms if getattr(r, 'is_wing', False)]
        _hall_doors = []
        for _d in (doorways or []):
            _dx = float(_d.get('x', 0.0)); _dy = float(_d.get('y', 0.0))
            _dax = _d.get('axis', 'X')
            if _dax == 'X' and (abs(_dy - iy_min) < 0.5 or abs(_dy - iy_max) < 0.5):
                _hall_doors.append(dict(_d))
            elif _dax == 'Y' and (abs(_dx - ix_min) < 0.5 or abs(_dx - ix_max) < 0.5):
                _hall_doors.append(dict(_d))
        _hall = Room(
            id="fl0_chapel_nave", floor_idx=0, role='CHAPEL_HALL',
            bounds=(ix_min, ix_max, iy_min, iy_max),
            doorways=_hall_doors,
            stair_hole=stair_hole,
            exterior_facades={'FRONT': (ix_min, ix_max),
                              'BACK': (ix_min, ix_max),
                              'LEFT': (iy_min, iy_max),
                              'RIGHT': (iy_min, iy_max)},
            allow_large=True)
        rooms = [_hall] + _wings
        interior_walls = []

    if (effective_archetype == 'KNIGHTS_MANOR' and fl_idx == 0 and rooms):
        rooms, interior_walls = _replan_knights_manor_ground(
            rooms, interior_walls, bounds, stair_hole, props, doorways,
            wall_t=wall_t, dw_w=dw_w, dw_h=dw_h)

    if effective_archetype == 'TENEMENT':
        interior_walls = _clamp_tenement_walls(interior_walls, rooms)

    rooms = _normalize_stair_circulation_rooms(rooms, stair_hole, stair_pos_info, bounds)

    # Every military building needs a working kitchen and a dining/mess area.
    # Guarantee both after stair normalization (which may turn the old kitchen
    # room into the protected stair landing).
    _military_layout = (
        effective_archetype in ('BARRACKS', 'INFANTRY_BARRACKS',
                                'ARMORY', 'ARCHERY', 'ARCHERY_RANGE')
        or bool(getattr(props, 'kit_tournament', False))
        or bool(getattr(props, 'kit_archery', False))
        or any(getattr(r, 'role', '') in
               ('MESS_HALL', 'ARMORY', 'BARRACKS_DORM', 'DRILL_HALL',
                'OFFICER_QUARTERS') for r in rooms))
    if _military_layout and fl_idx == 0 and rooms:
        if not any(getattr(r, 'role', '') == 'KITCHEN' for r in rooms):
            _cand = next((r for r in rooms if getattr(r, 'role', '') in
                          ('STORAGE', 'OFFICE', 'ARMORY', 'PANTRY', 'GUEST_ROOM',
                           'BEDROOM', 'GREAT_HALL', 'LODGE')), None)
            if _cand is not None:
                _cand.role = 'KITCHEN'
        if not any(getattr(r, 'role', '') == 'MESS_HALL' for r in rooms):
            _cand = next((r for r in rooms if getattr(r, 'role', '') in
                          ('STORAGE', 'OFFICE', 'ARMORY', 'PANTRY', 'GUEST_ROOM',
                           'BEDROOM', 'GREAT_HALL', 'LODGE')), None)
            if _cand is not None:
                _cand.role = 'MESS_HALL'

    # A house is one household: never leave duplicate kitchens on a floor.
    # (Upper-storey kitchens likewise collapse into a living room when the
    # ground floor already feeds the home.)
    if effective_archetype in ('HOUSE', 'COTTAGE', 'MANOR', 'NONE', 'AUTO'):
        if fl_idx > 0:
            for _r in rooms:
                if getattr(_r, 'role', '') == 'KITCHEN':
                    _r.role = 'HOUSE_HALL'
        else:
            _kits = [r for r in rooms if getattr(r, 'role', '') == 'KITCHEN']
            for _extra in _kits[1:]:
                if not any(getattr(r, 'role', '') == 'DINING' for r in rooms):
                    _extra.role = 'DINING'
                elif not any(getattr(r, 'role', '') == 'PANTRY' for r in rooms):
                    _extra.role = 'PANTRY'
                else:
                    _extra.role = 'STORAGE'

    # Nasher keep: the basement stair hall is a working store, not a parlour.
    if (fl_idx == 0 and getattr(props, 'has_basement_stair', False)
            and stair_hole is not None):
        _sx = (stair_hole[0] + stair_hole[1]) * 0.5
        _sy = (stair_hole[2] + stair_hole[3]) * 0.5
        _holder = None
        for _r in rooms:
            x0, x1, y0, y1 = _r.bounds
            if x0 <= _sx <= x1 and y0 <= _sy <= y1:
                _holder = _r
                break
        if _holder is not None and getattr(_holder, 'role', '') in (
                'ENTRANCE_HALL', 'HOUSE_HALL', 'STUDY', 'CORRIDOR',
                'STAIR_LANDING'):
            _holder.role = 'STORAGE'

    # Upper storeys of living outbuildings must expose real beds, even when a
    # simplified T-wing plan would otherwise fill the floor with salons.
    if fl_idx > 0 and rooms:
        _bed_roles = {'BEDROOM', 'MASTER_BED', 'GUEST_ROOM',
                      'BARRACKS_DORM', 'OFFICER_QUARTERS', 'HEALER_QUARTERS'}
        if not any(getattr(r, 'role', '') in _bed_roles for r in rooms):
            _cand = None
            for _r in rooms:
                if getattr(_r, 'is_wing', False):
                    continue
                if getattr(_r, 'role', '') in (
                        'CORRIDOR', 'STAIR_LANDING', 'ENTRANCE_HALL',
                        'KITCHEN', 'PANTRY', 'BATH'):
                    continue
                if _cand is None:
                    _cand = _r
                    continue
                if (_r.bounds[1] - _r.bounds[0]) * (_r.bounds[3] - _r.bounds[2]) > \
                        (_cand.bounds[1] - _cand.bounds[0]) * (_cand.bounds[3] - _cand.bounds[2]):
                    _cand = _r
            if _cand is not None:
                _cand.role = ('BARRACKS_DORM'
                              if (program in ('GARRISON', 'MILITARY')
                                  or effective_archetype in
                                  ('BARRACKS', 'INFANTRY_BARRACKS', 'ARMORY',
                                   'KNIGHTS_MANOR'))
                              else 'BEDROOM')

    return rooms, interior_walls


def build_floor_interior_walls(bm, interior_walls, z_floor, z_ceil,
                               mat_index=MAT_INDEX_WOOD, casing_mat=MAT_INDEX_TIMBER,
                               plank_direction='VERTICAL'):
    """Constructs physical 3D geometry for all planned interior partition walls on a floor."""
    for w in interior_walls:
        p1 = w['p1']
        p2 = w['p2']
        thick = w.get('thickness', 0.16)
        doorway = w.get('doorway')
        build_interior_wall(
            bm, p1, p2, z_floor, z_ceil,
            thickness=thick, doorway=doorway,
            mat_index=mat_index, casing_mat=casing_mat,
            plank_direction=plank_direction
        )

