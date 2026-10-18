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
from .mesh_utils import create_box, create_beveled_box, create_cylinder
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
                         wall_thickness=0.28, stair_hole=None, wall_openings=None):
    """Build interior baseboards and crown moulding flush to the *inside* wall faces.

    ``wall_openings`` uses the same local-U opening dictionaries as the wall builder.
    Baseboards are split around ground-reaching openings (doors and portals), rather
    than running across the walk-through.  The small inward offset prevents trims
    from poking through the exterior side of a double wall.
    """
    import math

    trim_h_floor = 0.11
    trim_d = 0.028
    reveal = 0.035
    wall_openings = wall_openings or {}

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
            rotation=(0.0, 0.0, angle), mat_index=MAT_INDEX_WOOD,
            bevel_amount=bevel
        )

    for side, x1, y1, x2, y2, inward in sides:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length

        # Door/portal openings are stored relative to the exterior wall start.
        # The trim line sits half a wall thickness inboard of that origin, so
        # shift the opening by wall_t/2 before converting to the trim segment
        # (otherwise every cut is half a wall thickness off and the baseboard
        # crosses the doorway).
        cuts = []
        reversed_from_wall_builder = side in {'back', 'left'}
        shift = wall_thickness * 0.5
        for opening in wall_openings.get(side, []):
            if opening.get('z_start', z_floor + 1.0) <= z_floor + trim_h_floor:
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
                if b > a:
                    cuts.append((a, b))
        cuts.sort()

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

        # Crown trims sit clear of ordinary doors and remain continuous by design.
        trim_h_ceil = 0.09
        add_trim_segment(x1, y1, x2, y2, inward,
                         z_ceil - trim_h_ceil * 0.5 - 0.008, 0.026, trim_h_ceil, 0.008)

def build_stair_guardrail_3sided(bm, sh_x1, sh_x2, sh_y1, sh_y2, floor_z,
                                 climb_side='NORTH', offset=0.18, rail_h=0.95,
                                 bounds=None):
    """
    Builds a 3-sided safety guardrail on the upper floor around the stairwell opening,
    offset 18 cm (0.18m) outward from the hole so it never overlaps the stair structure or posts.
    The side we climb up from the stairs is kept open.
    Corner posts are cleanly shared so there is zero overlap between adjacent railing segments.
    """
    slab_xmin, slab_xmax, slab_ymin, slab_ymax = bounds if bounds else (-999.0, 999.0, -999.0, 999.0)
    x_left = max(slab_xmin + 0.08, sh_x1 - offset)
    x_right = min(slab_xmax - 0.08, sh_x2 + offset)
    
    if climb_side == 'NORTH':
        y_foot = max(slab_ymin + 0.08, sh_y1 - offset)
        y_climb = min(slab_ymax - 0.08, sh_y2)
        # Left long railing (corner post at y_foot, end post at y_climb)
        build_railing(bm, (x_left, y_foot), (x_left, y_climb), floor_z, height=rail_h,
                      post_spacing=1.3, baluster_spacing=0.20, braces=False,
                      post_at_start=True, post_at_end=True)
        # Right long railing (corner post at y_foot, end post at y_climb)
        build_railing(bm, (x_right, y_foot), (x_right, y_climb), floor_z, height=rail_h,
                      post_spacing=1.3, baluster_spacing=0.20, braces=False,
                      post_at_start=True, post_at_end=True)
        # Return short railing across closed foot end (skips corner posts as side rails placed them)
        if x_right - x_left > 0.3:
            build_railing(bm, (x_left, y_foot), (x_right, y_foot), floor_z, height=rail_h,
                          post_spacing=1.3, baluster_spacing=0.20, braces=False,
                          post_at_start=False, post_at_end=False)
    else:  # climb_side == 'SOUTH'
        y_foot = min(slab_ymax - 0.08, sh_y2 + offset)
        y_climb = max(slab_ymin + 0.08, sh_y1)
        # Left long railing
        build_railing(bm, (x_left, y_climb), (x_left, y_foot), floor_z, height=rail_h,
                      post_spacing=1.3, baluster_spacing=0.20, braces=False,
                      post_at_start=True, post_at_end=True)
        # Right long railing
        build_railing(bm, (x_right, y_climb), (x_right, y_foot), floor_z, height=rail_h,
                      post_spacing=1.3, baluster_spacing=0.20, braces=False,
                      post_at_start=True, post_at_end=True)
        # Return short railing across closed foot end
        if x_right - x_left > 0.3:
            build_railing(bm, (x_left, y_foot), (x_right, y_foot), floor_z, height=rail_h,
                          post_spacing=1.3, baluster_spacing=0.20, braces=False,
                          post_at_start=False, post_at_end=False)

def build_stair_guardrail(bm, rail_x, y_start, y_end, floor_z, rail_h=0.95, return_y=None, x_start=None):
    """
    Builds a safety guardrail on the upper floor along the open edge of the stairwell
    (at X = rail_x, from y_start to y_end).
    If return_y and x_start are given, also adds the short return rail along the open end.
    Uses the shared detailed railing builder.
    """
    if y_end - y_start < 0.3:
        return
    build_railing(bm, (rail_x, y_start), (rail_x, y_end), floor_z, height=rail_h)
    if return_y is not None and x_start is not None and abs(rail_x - x_start) > 0.3:
        build_railing(bm, (x_start, return_y), (rail_x, return_y), floor_z,
                      height=rail_h, braces=False, post_spacing=1.0,
                      post_at_start=False, post_at_end=False)


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


def build_straight_staircase(bm, start_pos, target_z, stair_width=1.40, stair_depth=2.6, num_steps=14, direction_y=1, base_anchor=True, top_anchor=True):
    """
    Generates a wooden straight/run staircase with chunky treads, grounded stringers,
    solid base and top anchor plates, and stylized handrails on BOTH SIDES.
    direction_y: 1 for +Y (front to back), -1 for -Y (back to front).
    """
    x0, y0, z0 = start_pos
    dz = target_z - z0
    step_h = dz / num_steps
    step_d = (stair_depth / num_steps) * direction_y
    tread_d = (stair_depth / num_steps) + 0.04
    tread_thick = 0.05
    
    uv_layer = bm.loops.layers.uv.verify()
    
    # 1. Grounded Starter Base Timber (anchored to floor)
    if base_anchor:
        base_faces = create_beveled_box(
            bm,
            size=(stair_width + 0.18, 0.22, 0.08),
            location=(x0, y0 + 0.05 * direction_y, z0 + 0.04),
            mat_index=MAT_INDEX_STAIRS,
            bevel_amount=0.012
        )
        for f in base_faces:
            if f.is_valid:
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = Vector(((co.y - y0) * 1.5 + (co.z - z0) * 1.5, (co.x - x0) * 0.65))
    
    # 2. Wooden Treads and Risers
    for i in range(num_steps):
        sz = z0 + i * step_h + step_h * 0.5
        sy = y0 + i * step_d + step_d * 0.5
        sx = x0
        tread_faces = create_beveled_box(
            bm,
            size=(stair_width, tread_d, tread_thick),
            location=(sx, sy, sz),
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.01
        )
        # Wood grain oriented strictly ALONG LENGTH (V axis) of each stair step board
        # The length direction is along the stair flight diagonal
        for f in tread_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                # Calculate position along the stair length (diagonal from start to target)
                # Length direction: (stair_depth * direction_y, 0, dz)
                # Normalize and map to V axis (0 at bottom, 1 at top of tread)
                len_dir_x = stair_depth * direction_y
                len_dir_z = dz
                length = math.sqrt(len_dir_x * len_dir_x + len_dir_z * len_dir_z)
                if length > 0:
                    along = (co.x * len_dir_x + co.z * len_dir_z) / length * 0.5 + 0.5  # 0-1 along length
                else:
                    along = 0.5
                # V runs along length, U runs across width
                u = (co.y - (sy - tread_d * 0.5)) * 1.6 + (co.z - sz) * 1.4 + (i * 0.19)
                v = along * 2.0  # Scale to fill UV space
                loop[uv_layer].uv = Vector((u, v))

        # Riser plank beneath tread (down to step below or floor)
        riser_faces = create_box(
            bm,
            size=(stair_width - 0.02, 0.035, step_h),
            location=(sx, sy - step_d * 0.5 + 0.015 * direction_y, sz - step_h * 0.5),
            mat_index=MAT_INDEX_STAIRS
        )
        for f in riser_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                v = (co.x - (sx - stair_width * 0.5)) * 0.45 + (i * 0.37 + 0.15)
                u = (co.z - (sz - step_h * 0.5)) * 1.6 + (co.y - sy) * 1.2 + (i * 0.19)
                loop[uv_layer].uv = Vector((u, v))
        
    # 3. Side Stringer Boards (anchored from starter base to upper landing)
    # Closed stringer beam (stringer_h=0.44, stringer_thick=0.10) to cover the sides of all
    # step treads and risers, and directly carry all vertical balusters without an extra sill rail.
    stringer_thick = 0.10
    stringer_h = 0.44
    diag_length = math.sqrt(dz * dz + stair_depth * stair_depth)
    pitch_angle = math.atan2(dz, stair_depth) * direction_y
    cos_pitch = math.cos(abs(pitch_angle))
    sin_pitch = math.sin(abs(pitch_angle))
    top_offset = (stringer_h * 0.5) / cos_pitch

    # Shift along slope so bottom front corner meets the back of the bottom post flush
    shift_along = (stringer_h * 0.5) * sin_pitch
    shift_y = shift_along * cos_pitch * direction_y
    shift_z = shift_along * sin_pitch
    
    for side in [-1, 1]:
        str_x = x0 + side * (stair_width * 0.5 + stringer_thick * 0.5)
        str_y = y0 + (stair_depth * 0.5) * direction_y + shift_y
        str_z = z0 + dz * 0.5 + shift_z
        # create_box automatically unwraps V strictly along the diagonal beam length (dy)
        create_box(
            bm,
            size=(stringer_thick, diag_length, stringer_h),
            location=(str_x, str_y, str_z),
            rotation=(pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_STAIRS
        )
        
    # 4. Top Landing Anchor Timber (anchors stringers solidly to the upper floor).
    # Dropped a touch below the floor so its top face never z-fights the slab.
    if top_anchor:
        top_faces = create_beveled_box(
            bm,
            size=(stair_width + 0.18, 0.22, 0.10),
            location=(x0, y0 + stair_depth * direction_y, target_z - 0.09),
            mat_index=MAT_INDEX_STAIRS,
            bevel_amount=0.012
        )
        for f in top_faces:
            if f.is_valid:
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = Vector(((co.x - x0) * 1.5, (co.y - (y0 + stair_depth * direction_y)) * 0.65 + (co.z - target_z) * 1.2))

    # 5. Guard railings on BOTH sides with prominent, taller end pillars (newel posts).
    # End pillars are placed forward at the landing/step edges and grounded on floor/landing slabs.
    # The handrail terminates cleanly into the sides of the pillars, and balusters enter
    # directly into the top of the enlarged diagonal stringer beam without redundant sill beams.
    POST_W = 0.10
    bot_post_h = 1.15
    top_post_h = 1.05
    rail_h = 0.68
    tan_pitch = dz / stair_depth

    for side in [-1, 1]:
        rail_x = x0 + side * (stair_width * 0.5 + stringer_thick * 0.5)

        # Bottom end pillar: at the foot of the stairs, standing firmly on the lower floor (z0)
        bot_post_y = y0 + (POST_W * 0.5) * direction_y
        build_railing_post(bm, rail_x, bot_post_y, z0, height=bot_post_h,
                           iron_pin=False, jankiness=0.0)

        # Top end pillar: at the landing edge, standing firmly on the upper floor (target_z)
        top_post_y = y0 + (stair_depth - POST_W * 0.5) * direction_y
        build_railing_post(bm, rail_x, top_post_y, target_z, height=top_post_h,
                           iron_pin=False, jankiness=0.0)

        # Sloped rail spans between the inner faces of bottom and top end pillars
        y_rail_start = bot_post_y + (POST_W * 0.5) * direction_y
        y_rail_end = top_post_y - (POST_W * 0.5) * direction_y

        dist_start = abs(y_rail_start - y0)
        dist_end = abs(y_rail_end - y0)
        z_start = z0 + dist_start * tan_pitch + top_offset
        z_end = z0 + dist_end * tan_pitch + top_offset

        build_railing(
            bm,
            (rail_x, y_rail_start),
            (rail_x, y_rail_end),
            z_start,
            height=rail_h,
            base_z_end=z_end,
            has_sill=False,
            posts=False,
            post_at_start=False,
            post_at_end=False,
            baluster_spacing=0.20,
            end_overhang=0.0,
            braces=False,
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
    return (cx - size * 0.5, cx + size * 0.5, cy - size * 0.5, cy + size * 0.5)


def build_stair_guardrail_one_open(bm, hole, floor_z, open_side,
                                   offset=0.14, rail_h=0.95, bounds=None,
                                   skip_sides=None):
    """Guard a rectangular stair opening on all sides EXCEPT ``open_side``
    ('N', 'S', 'E' or 'W') where you step onto/off the flight, and any side in
    ``skip_sides`` (e.g. a side that sits against a wall)."""
    x0, x1, y0, y1 = hole
    if bounds:
        sx0, sx1, sy0, sy1 = bounds
    else:
        sx0, sx1, sy0, sy1 = x0 - 99.0, x1 + 99.0, y0 - 99.0, y1 + 99.0
    xl = max(sx0 + 0.06, x0 - offset)
    xr = min(sx1 - 0.06, x1 + offset)
    yl = max(sy0 + 0.06, y0 - offset)
    yr = min(sy1 - 0.06, y1 + offset)
    _sides = {'W': (xl, yl, xl, yr), 'E': (xr, yl, xr, yr),
              'S': (xl, yl, xr, yl), 'N': (xl, yr, xr, yr)}
    for _s, (_ax, _ay, _bx, _by) in _sides.items():
        if _s == open_side:
            continue
        if skip_sides and _s in skip_sides:
            continue
        if abs(_bx - _ax) < 0.3 and abs(_by - _ay) < 0.3:
            continue
        build_railing(bm, (_ax, _ay), (_bx, _by), floor_z, height=rail_h,
                      post_spacing=1.25, baluster_spacing=0.20, braces=False)


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
    door_w = 1.30
    door_h = min(2.65, H - 0.30)

    if doorway is not None:
        if isinstance(doorway, dict):
            dw_x = doorway.get('x', (x1 + x2) * 0.5)
            dw_y = doorway.get('y', (y1 + y2) * 0.5)
            u_door_cx = (dw_x - x1) * ux + (dw_y - y1) * uy
            door_w = doorway.get('w', 1.30)
            door_h = min(doorway.get('h', 2.65), H - 0.30)
        elif isinstance(doorway, (tuple, list)) and len(doorway) >= 3:
            u_door_cx, door_w, door_h = doorway[0], doorway[1], min(doorway[2], H - 0.30)
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
                rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.008
            )
            off_c = sgn * (thickness * 0.5 + trim_ceil_d * 0.5)
            create_beveled_box(
                bm, size=(length, trim_ceil_d, trim_h_ceil),
                location=(cx + nx * off_c, cy + ny * off_c, z_ceil - trim_h_ceil * 0.5 - 0.008),
                rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.008
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
                rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.008
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
                rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.008
            )

    # 4. Continuous crown moulding at ceiling
    for sgn in (-1.0, 1.0):
        off_c = sgn * (thickness * 0.5 + trim_ceil_d * 0.5)
        create_beveled_box(
            bm, size=(length, trim_ceil_d, trim_h_ceil),
            location=((x1 + x2) * 0.5 + nx * off_c, (y1 + y2) * 0.5 + ny * off_c, z_ceil - trim_h_ceil * 0.5 - 0.008),
            rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.008
        )

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
        location=(head_x, head_y, z_floor + door_h + head_h * 0.5 - 0.015),
        rotation=(0.0, 0.0, ang), mat_index=casing_mat, bevel_amount=0.012
    )

    # Beveled timber threshold board spanning the floor opening
    create_beveled_box(
        bm, size=(door_w + jamb_w * 2.0 + 0.04, casing_d + 0.02, 0.028),
        location=(head_x, head_y, z_floor + 0.014),
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
        'ground': ('DRILL_HALL', 'MESS_HALL', 'ARMORY', 'STORAGE'),
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
        'upper': ('STAIR_LANDING', 'HOUSE_HALL', 'BEDROOM', 'KITCHEN'),
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
    'WAREHOUSE': 'INDUSTRIAL', 'LUMBERMILL': 'INDUSTRIAL',
    'BLACKSMITH': 'COMMERCIAL',
    'QUARRY': 'INDUSTRIAL',
    'BAKERY': 'COMMERCIAL', 'FISHERMAN': 'COMMERCIAL', 'BREWERY': 'COMMERCIAL',
    'BUTCHER': 'COMMERCIAL', 'TAILOR': 'COMMERCIAL', 'TOOLSMITH': 'COMMERCIAL',
    'JEWELER': 'COMMERCIAL', 'FURNITURE_MAKER': 'COMMERCIAL',
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


def _resolve_room_roles(archetype, fl_idx, num_rooms, has_stairs_landing=False, total_floors=1,
                        program=None):

    """Assigns functional roles to rooms on a floor based on building archetype and stair presence."""
    if program and program != 'AUTO':
        _p = _program_roles(program, fl_idx, num_rooms, has_stairs_landing)
        if _p is not None:
            return _p
    if archetype == 'MANOR':
        # Grand residence: banquet hall + compact service rooms + library.
        if has_stairs_landing:
            pool = ['STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'LIBRARY',
                    'STUDY', 'GUEST_ROOM']
            return pool[:num_rooms]
        if total_floors == 1:
            pool = ['BANQUET_HALL', 'KITCHEN', 'BEDROOM', 'LIBRARY', 'STUDY']
            return pool[:num_rooms]
        pool = ['BANQUET_HALL', 'KITCHEN', 'PANTRY', 'LIBRARY', 'STUDY']
        return pool[:num_rooms]
    if has_stairs_landing:
        # On upper floors with stairs, Room 0 (around stair hole) is the protected landing/corridor.
        # Bedrooms and private suites are strictly placed in the separate partitioned chambers.
        if archetype in ('TAVERN', 'INN'):
            pool = ['STAIR_LANDING', 'GUEST_ROOM', 'GUEST_ROOM', 'GUEST_ROOM', 'MASTER_BED', 'STUDY']
            return pool[:num_rooms]
        elif archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY'):
            # Industrial upper floors are work/storage, never bedrooms or kitchens.
            pool = ['STAIR_LANDING', 'STONE_STORE' if archetype == 'QUARRY' else 'STORAGE', 'WORKSHOP', 'OFFICE']
            return pool[:num_rooms]
        elif archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                          'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER') or archetype.startswith('ARTISAN'):
            # Artisan live/work house: trade below, family home above. Upper
            # storeys are strictly residential (no offices, no studies).
            # Floor 2 pairs the bedroom with an eat-in kitchen (no separate
            # hall on these narrow floors, so the kitchen lays its full
            # dining set) instead of a third narrow chamber.
            if fl_idx == 1:
                pool = ['STAIR_LANDING', 'BEDROOM', 'KITCHEN', 'HOUSE_HALL']
            else:
                pool = ['STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'GUEST_ROOM']
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
            pool = ['STAIR_LANDING', 'HEALER_QUARTERS', 'STUDY', 'BEDROOM']
            return pool[:num_rooms]
        elif archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
            pool = ['STAIR_LANDING', 'MAYOR_OFFICE', 'OFFICE', 'STUDY', 'ARCHIVE']
            return pool[:num_rooms]
        elif archetype in ('TENEMENT',):
            pool = ['STAIR_LANDING', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM']
            return pool[:num_rooms]
        elif archetype in ('STABLE',):
            pool = ['STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL']
            return pool[:num_rooms]
        else:  # HOUSE, MANOR, default
            pool = ['STAIR_LANDING', 'MASTER_BED', 'BEDROOM', 'STUDY', 'GUEST_ROOM']
            return pool[:num_rooms]

    # Ground floor (or single floor without stair landing)
    if archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
        pool = ['GREAT_HALL', 'COUNCIL_CHAMBER', 'ARCHIVE', 'STUDY']
        return pool[:num_rooms]

    if archetype in ('TAVERN', 'INN'):
        pool = ['TAVERN_TAPROOM', 'KITCHEN', 'CELLAR', 'PANTRY']
        return pool[:num_rooms]

    # Dedicated craft workshops per artisan trade: the street-facing shop plus
    # the trade's own production rooms (never generic offices or studies).
    _ARTISAN_GROUND = {
        'BAKERY': ['STORE', 'BAKEHOUSE', 'BAKEHOUSE', 'STORAGE'],
        'BREWERY': ['STORE', 'BREWHOUSE', 'BREWHOUSE', 'STORAGE'],
        'BUTCHER': ['STORE', 'BUTCHERY', 'BUTCHERY', 'STORAGE'],
        'TAILOR': ['STORE', 'TAILOR_ATELIER', 'TAILOR_ATELIER', 'STORAGE'],
        'JEWELER': ['STORE', 'GOLDSMITH', 'GOLDSMITH', 'STORAGE'],
        'BLACKSMITH': ['STORE', 'SMITHY', 'SMITHY', 'STORAGE'],
        'TOOLSMITH': ['STORE', 'SMITHY', 'SMITHY', 'STORAGE'],
        'FURNITURE_MAKER': ['STORE', 'JOINERY', 'JOINERY', 'STORAGE'],
        'FISHERMAN': ['STORE', 'FISHERY', 'FISHERY', 'STORAGE'],
    }
    if archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY'):
        if archetype == 'QUARRY':
            pool = ['STONE_STORE', 'STORAGE', 'WORKSHOP', 'OFFICE']
        else:
            pool = ['STORE', 'WORKSHOP', 'STORAGE', 'PANTRY']
        return pool[:num_rooms]

    if archetype in _ARTISAN_GROUND or archetype.startswith('ARTISAN'):
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
        pool = ['ARMORY', 'STORAGE', 'DRILL_HALL', 'MESS_HALL']
        return pool[:num_rooms]

    if archetype in ('KNIGHTS_MANOR',):
        pool = ['GREAT_HALL', 'MESS_HALL', 'ARMORY', 'STORAGE']
        return pool[:num_rooms]

    if archetype in ('ARCHERY', 'ARCHERY_RANGE'):
        pool = ['FLETCHER_WORKSHOP', 'RANGE', 'STORAGE', 'LODGE']
        return pool[:num_rooms]

    if archetype in ('CHAPEL', 'HEALERS_CHAPEL'):
        pool = ['CHAPEL_HALL', 'INFIRMARY', 'APOTHECARY', 'STUDY']
        return pool[:num_rooms]

    if archetype in ('TENEMENT',):
        pool = ['TENEMENT_KITCHEN', 'TENEMENT_BEDROOM', 'TENEMENT_KITCHEN', 'TENEMENT_BEDROOM']
        return pool[:num_rooms]

    if archetype in ('STABLE',):
        pool = ['STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL', 'STABLE_HALL']
        return pool[:num_rooms]

    # Default HOUSE / MANOR. A house only needs ONE pantry; the largest plots
    # get a library/reading room instead of a second storage room.
    if total_floors == 1:
        pool = ['HOUSE_HALL', 'KITCHEN', 'BEDROOM', 'LIBRARY']
        return pool[:num_rooms]
    else:
        pool = ['HOUSE_HALL', 'KITCHEN', 'PANTRY', 'LIBRARY']
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

    if fl_idx == 0:
        _vwall(b_west, iy_min, iy_max, y_mid)
        _vwall(b_east, iy_min, iy_max, y_mid)

        rm_west = Room(
            id=f"fl{fl_idx}_stair_hall", floor_idx=fl_idx, role='CORRIDOR',
            bounds=(ix_min, b_west, iy_min, iy_max),
            doorways=[{'x': b_west, 'y': y_mid, 'axis': 'Y', 'w': dw_w}],
            stair_hole=_holds_stair((ix_min, b_west, iy_min, iy_max)),
            exterior_facades={'FRONT': (ix_min, b_west), 'BACK': (ix_min, b_west), 'LEFT': (iy_min, iy_max)}
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
        _hwall(b_east, ix_max, split_y_east, (b_east + ix_max) * 0.5)
        rm_east_s = Room(
            id=f"fl{fl_idx}_council_chamber", floor_idx=fl_idx, role='COUNCIL_CHAMBER',
            bounds=(b_east, ix_max, iy_min, split_y_east),
            doorways=[{'x': (b_east + ix_max) * 0.5, 'y': split_y_east, 'axis': 'X', 'w': dw_w}],
            stair_hole=None,
            exterior_facades={'FRONT': (b_east, ix_max), 'RIGHT': (iy_min, split_y_east)}
        )
        rm_east_n = Room(
            id=f"fl{fl_idx}_banquet_hall", floor_idx=fl_idx, role='BANQUET_HALL',
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
            id=f"fl{fl_idx}_royal_salon", floor_idx=fl_idx, role='GREAT_HALL',
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
            id=f"fl{fl_idx}_royal_bed", floor_idx=fl_idx, role='MASTER_BED',
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
            id=f"fl{fl_idx}_library", floor_idx=fl_idx, role='LIBRARY',
            bounds=(b_east, ix_max, iy_min, y_mid),
            doorways=[
                {'x': b_east, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_east, 'y': y_mid, 'axis': 'X', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'FRONT': (b_east, ix_max), 'RIGHT': (iy_min, y_mid)}
        )
        rm_east_n = Room(
            id=f"fl{fl_idx}_treasury", floor_idx=fl_idx, role='OFFICE',
            bounds=(b_east, ix_max, y_mid, iy_max),
            doorways=[
                {'x': b_east, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                {'x': dw_x_east, 'y': y_mid, 'axis': 'X', 'w': dw_w},
            ],
            stair_hole=None,
            exterior_facades={'BACK': (b_east, ix_max), 'RIGHT': (y_mid, iy_max)}
        )
        rooms = [rm_west, rm_center_s, rm_center_n, rm_east_s, rm_east_n]

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
        c_stair_w = max(3.6, _sw + 1.8)
    else:
        c_stair_w = 4.0
    c_stair_w = min(max(c_stair_w, 3.5), W * 0.28)

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
                r_south = 'KITCHEN' if ci == 0 else 'PANTRY'
                r_north = 'PANTRY' if ci == 0 else 'STORAGE'
            elif fl_idx == 1:
                r_south = 'LIBRARY'
                r_north = 'STUDY'
            elif fl_idx == 2:
                r_south = 'MASTER_BED'
                r_north = 'BEDROOM'
            elif fl_idx == 3:
                r_south = 'PARLOR'
                r_north = 'STUDY'
            else:
                r_south = 'BEDROOM'
                r_north = 'STORAGE'

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

    return rooms, walls


def plan_floor_rooms(fl_idx, bounds, stair_hole=None, stair_pos_info=None,
                     front_door_info=None, fl_wings_bounds=None,
                     effective_archetype='NONE', props=None, seed=0,
                     doorways=None):
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

    dw_w = 1.30
    dw_h = min(2.65, floor_h - 0.35)

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.30
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

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
                    w_role = 'LIBRARY' if fl_idx == 0 else ('MASTER_BED' if fl_idx == 1 else 'GUEST_ROOM')
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
            return _p_rooms, _p_walls

    is_wide_mansion = (W >= 15.0 and D >= 6.0
                       and not getattr(props, 'has_throne_room', False)
                       and not getattr(props, 'has_double_height', False))
    if (effective_archetype == 'MANOR' or is_wide_mansion) and has_interior_walls \
            and partition_style in ('AUTO', 'HALL_CHAMBERS'):
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
                        w_role = 'STORAGE' if wi == 0 else 'GUEST_ROOM'
                    elif fl_idx == 3:
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
            return _manor_rooms, _manor_walls

    # Single open room fallback (only when explicitly requested, plot is tiny
    # < 4.2m, or the archetype is an open industrial hall such as a lumbermill
    # whose equipment fills the floor).
    loom_open = (effective_archetype in ('LUMBERMILL', 'QUARRY'))
    # Working stable barns stay one open hall (stall rows + hay storage),
    # never partitioned into bedrooms.
    stable_open = (effective_archetype == 'STABLE')
    if not has_interior_walls or partition_style == 'OPEN' or (W < 4.2 and D < 4.2) or loom_open or stable_open:
        if effective_archetype == 'QUARRY':
            roles = ['STONE_STORE']
        elif effective_archetype == 'LUMBERMILL':
            roles = ['WORKSHOP' if fl_idx == 0 else 'STORAGE']
        elif effective_archetype == 'STABLE':
            roles = ['STABLE_HALL']
        else:
            roles = _resolve_room_roles(effective_archetype, fl_idx, 1, has_stairs_landing, total_floors, program=program)
        main_room = Room(
            id=f"fl{fl_idx}_main",
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
                    w_role = 'DINING'
                    w_doorways = []
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
                    w_doorways = []
                elif effective_archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
                    w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'MAYOR_OFFICE'
                    w_doorways = []
                elif effective_archetype in ('BARRACKS', 'INFANTRY_BARRACKS', 'KNIGHTS_MANOR',
                                             'ARCHERY', 'ARCHERY_RANGE'):
                    w_role = 'BARRACKS_DORM'
                    w_doorways = []
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
                                           ('WAREHOUSE', 'LUMBERMILL', 'BLACKSMITH')) else 'GUEST_ROOM'
                    w_doorways = []
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
        return rooms, []

    # Safe boundaries around stairs (left side)
    stair_switchback = bool((stair_pos_info or {}).get('switchback', False))
    walk_w = float((stair_pos_info or {}).get('walk_w', 1.05) or 1.05)
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
        _ocy = (iy_min + iy_max) * 0.5
        oven_band = (_ocy - OVEN_WALL_CLEAR, _ocy + OVEN_WALL_CLEAR)

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
        ox0, ox1 = ix_max - 1.50, ix_max - 0.05
        holder = None
        for r in room_list:
            if getattr(r, 'is_wing', False):
                continue
            x0, x1, y0, y1 = r.bounds
            if x0 <= ox0 and ox1 <= x1 and y0 <= oy <= y1:
                holder = r
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
    can_3_rooms = (partition_style in ('AUTO', 'HALL_CHAMBERS')) and (W >= 7.2 and D >= 5.4)
    can_4_rooms = can_3_rooms and (D >= 8.0 or effective_archetype in ('INN', 'TENEMENT'))

    rooms = []
    interior_walls = []

    def _clear_doorway_span(pos, axis='X', margin=0.65, lo=None, hi=None):
        """Move partition coordinate `pos` off any doorway/wing-portal opening
        it would otherwise cross (a partition must never land in the middle of
        a doorway). The result stays within [lo, hi]; iterate to fixpoint so
        dodging one opening never lands inside another."""
        if axis == 'X':
            lo = ix_min + 1.8 if lo is None else lo
            hi = ix_max - 1.8 if hi is None else hi
            door_items = [(dw.get('x', 0.0), dw.get('w', 1.2))
                          for dw in (doorways or []) if dw.get('axis', 'X') == 'X']
        else:
            lo = iy_min + 1.8 if lo is None else lo
            hi = iy_max - 1.8 if hi is None else hi
            door_items = [(dw.get('y', 0.0), dw.get('w', 1.2))
                          for dw in (doorways or []) if dw.get('axis', 'X') == 'Y']
        spans = [(dc - dw * 0.5 - margin, dc + dw * 0.5 + margin, dc, dw)
                 for dc, dw in door_items]
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

    if not is_deep:
        # Partition along Y (vertical wall at X = split_x, running from iy_min to iy_max)
        stair_on_right = bool(
            (stair_pos_info and float(stair_pos_info.get('cx', ix_min)) > (ix_min + ix_max) * 0.5)
            or getattr(props, 'stair_placement', 'LEFT') == 'RIGHT'
        )
        if stair_on_right:
            stair_w = float((stair_pos_info or {}).get('w', 1.2) or 1.2)
            stair_cx = float((stair_pos_info or {}).get('cx', ix_max - 1.4) or (ix_max - 1.4))
            stair_safe_x_left = stair_cx - stair_w * 0.5 - 0.20
            max_split_x = stair_safe_x_left - 0.60
            split_x = max(ix_min + 2.2, min(max_split_x, ix_max - W * 0.38))
            split_x = _clear_doorway_span(split_x, axis='X',
                                          lo=ix_min + 1.8,
                                          hi=min(ix_max - 1.8, max_split_x))
        else:
            min_split_x = stair_safe_x + 0.60
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
        # proportions worse than ~2.6:1 (or any side under 2m).
        def _strip_chunky(hw, cw, fracs):
            if min(hw, cw) < 2.0:
                return False
            if D / max(hw, 0.5) > 3.2:
                return False
            for f in fracs:
                d = D * f
                if min(cw, d) < 2.0:
                    return False
                if max(cw, d) / max(min(cw, d), 0.5) > 2.6:
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

        elif effective_archetype in ('INN', 'TAVERN') and fl_idx == 0:
            # Ground floor of Inn/Tavern: Great Taproom on Left + ONE big spacious Kitchen on Right
            dw_y = (iy_min + iy_max) * 0.5
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
                    min_hw = max(2.40, (stair_safe_x - ix_min) + walk_w)
                    if door_cx is not None:
                        min_hw = max(min_hw, (door_cx + dw_w * 0.5 + 0.30) - ix_min)
                    hall_w = min(max(min_hw, 2.50), max(W * 0.36, min_hw))
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
                if apt_w >= 4.0:
                    apt_split_x = _clear_doorway_span(
                        hall_x + apt_w * 0.48, axis='X',
                        lo=hall_x + 1.8, hi=ix_max - 1.8)
                    # Internal doors inside apartments connecting kitchen/living to bedroom
                    interior_walls.append({
                        'p1': (apt_split_x, iy_min), 'p2': (apt_split_x, split_y),
                        'axis': 'Y', 'pos': apt_split_x, 'thickness': wall_t,
                        'doorway': {'x': apt_split_x, 'y': dw_y_s, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                    })
                    interior_walls.append({
                        'p1': (apt_split_x, split_y), 'p2': (apt_split_x, iy_max),
                        'axis': 'Y', 'pos': apt_split_x, 'thickness': wall_t,
                        'doorway': {'x': apt_split_x, 'y': dw_y_n, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
                    })

                    rm_s_k = Room(
                        id=f"fl{fl_idx}_apt_south_kitchen", floor_idx=fl_idx, role='TENEMENT_KITCHEN',
                        bounds=(hall_x, apt_split_x, iy_min, split_y),
                        doorways=[
                            {'x': hall_x, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                            {'x': apt_split_x, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w},
                        ],
                        stair_hole=None,
                        exterior_facades={'FRONT': (hall_x, apt_split_x)}
                    )
                    rm_s_b = Room(
                        id=f"fl{fl_idx}_apt_south_bed", floor_idx=fl_idx, role='TENEMENT_BEDROOM',
                        bounds=(apt_split_x, ix_max, iy_min, split_y),
                        doorways=[{'x': apt_split_x, 'y': dw_y_s, 'axis': 'Y', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'FRONT': (apt_split_x, ix_max), 'RIGHT': (iy_min, split_y)}
                    )
                    rm_n_k = Room(
                        id=f"fl{fl_idx}_apt_north_kitchen", floor_idx=fl_idx, role='TENEMENT_KITCHEN',
                        bounds=(hall_x, apt_split_x, split_y, iy_max),
                        doorways=[
                            {'x': hall_x, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                            {'x': apt_split_x, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w},
                        ],
                        stair_hole=None,
                        exterior_facades={'BACK': (hall_x, apt_split_x)}
                    )
                    rm_n_b = Room(
                        id=f"fl{fl_idx}_apt_north_bed", floor_idx=fl_idx, role='TENEMENT_BEDROOM',
                        bounds=(apt_split_x, ix_max, split_y, iy_max),
                        doorways=[{'x': apt_split_x, 'y': dw_y_n, 'axis': 'Y', 'w': dw_w}],
                        stair_hole=None,
                        exterior_facades={'BACK': (apt_split_x, ix_max), 'RIGHT': (split_y, iy_max)}
                    )
                    rooms.extend([rm_s_k, rm_s_b, rm_n_k, rm_n_b])
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

                for _apt in _apts:
                    _doors = [w['doorway'] for w in _apt['walls'] if w.get('doorway')]
                    _doors.append(_apt['entry'])
                    _is_w = _apt['id'].startswith('wing')
                    _w_id = (int(_apt['id'].replace('wing', '')) - 1) if _is_w else None
                    for _ri, _rd in enumerate(_apt['rooms']):
                        _b = _rd['bounds']
                        _rdws = [dict(d) for d in _doors if d and _touches(_b, d)]
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
                                            hi=iy_min + D * _k2 - 1.6)
            split_y2 = _clear_doorway_span(iy_min + D * _k2, axis='Y',
                                            lo=split_y1 + 1.6)
            if oven_band is not None:
                # Keep both chamber lines out of the oven masonry, preserving
                # their order and a walkable 1.6m minimum chamber depth.
                split_y1 = _dodge_oven_band(split_y1, iy_min + 1.6, iy_max - 3.2)
                split_y2 = _dodge_oven_band(max(split_y2, split_y1 + 1.6),
                                            split_y1 + 1.6, iy_max - 1.6)
                if oven_band[0] <= split_y2 <= oven_band[1]:
                    split_y2 = min(iy_max - 1.6, oven_band[1])

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
            # 2 Rooms along Y (Left Room + Right Room)
            roles = _resolve_room_roles(effective_archetype, fl_idx, 2, has_stairs_landing, total_floors, program=program)
            dw_y = (iy_min + iy_max) * 0.5
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
                and effective_archetype not in ('TOWN_HALL', 'CIVIC', 'GUILDHALL',
                                                'TAVERN', 'INN', 'TENEMENT', 'MANOR')
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
                _bay = _clear_doorway_span(_wx1 + 1.0, axis='X',
                                           lo=_wx1 + 0.6, hi=_hx1 - 2.2)
                if front_door_info is not None and fl_idx == 0:
                    _dcx, _ddw = front_door_info
                    if abs(_bay - _dcx) < _ddw * 0.5 + 0.65:
                        _bay = _dcx + _ddw * 0.5 + 0.65
                if _hx1 - _bay >= 2.2 and _bay - _hx0 >= 2.0:
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
                        # The bay is the landing now, so the leftover hall
                        # strip becomes the next unused chamber role instead
                        # of a second landing.
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
        # ground floors stay at 2 big rooms (shop + workshop); upper floors
        # get at most 3 spacious multi-use bands. Falls back to the legacy
        # 2-room split when the stairwell leaves no room for more bands.
        if fl_idx == 0 and (effective_archetype in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY',
                                                 'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER',
                                                 'FURNITURE_MAKER') or effective_archetype.startswith('ARTISAN')):
            _deep_target = 2
        else:
            _deep_target = 4 if D >= 16.8 else (3 if D >= 10.5 else 2)
        _deep_splits = None
        if _turn_layout and has_stairs_landing:
            # Turned-stair floors: the front band is the stair column; whatever
            # depth is left behind it is divided into evenly-sized (square-ish)
            # rooms. No corridor slivers, and if only one decent room fits it is
            # simply one room.
            _col_top = stair_safe_y_top + 0.35
            _avail = iy_max - _col_top
            _nrooms = int(_avail / 3.6)
            while _nrooms >= 1 and _avail / _nrooms < 2.8:
                _nrooms -= 1
            if _nrooms >= 1 and (_col_top - iy_min) >= 1.6:
                _splits = [_col_top]
                for _ri in range(1, _nrooms):
                    _splits.append(_col_top + _avail * _ri / _nrooms)
                _deep_splits = _splits
                _deep_target = _nrooms + 1
        elif _deep_target >= 3:
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
                    if _turn_layout:
                        # Keep the partition clear of the WHOLE turned-stair
                        # column (flights, landings and all), not just the slab
                        # opening, so no wall ever runs through the stairs.
                        _hs0, _hs1 = stair_safe_y_bot - 0.35, stair_safe_y_top + 0.35
                    elif stair_hole is not None:
                        _hs0, _hs1 = stair_hole[2] - 0.80, stair_hole[3] + 0.80
                    if _hs0 is not None:
                        # A split exactly on the clearance edge is already
                        # safe; only the open interval is forbidden.
                        if _hs0 < _sp < _hs1:
                            _sp = _hs0 if (_sp - _hs0) <= (_hs1 - _sp) else _hs1
                            _sp = min(max(_sp, _lo), iy_max - 1.8)
                        if _hs0 < _sp < _hs1:
                            _ok = False
                            break
                    _fixed.append(_sp)
                    _lo = _sp + 2.2
                if not (_ok and _fixed and iy_max - _fixed[-1] >= 2.2 - 1e-6):
                    continue
                if _turn_layout:
                    # Prefer squarer rooms: reject a band set that contains a
                    # corridor-thin slice and retry with one band fewer.
                    _ed = [iy_min] + list(_fixed) + [iy_max]
                    if min(_ed[_i + 1] - _ed[_i] for _i in range(len(_ed) - 1)) < 2.8:
                        continue
                _deep_splits = _fixed
                _deep_target = _try_n
                break
        # Reject corridor-thin bands on turned-stair floors: a floor sliced into
        # shallow strips reads as hallways. Prefer a single room instead.
        if _deep_splits is not None and _turn_layout:
            _bd = [iy_min] + list(_deep_splits) + [iy_max]
            if min(_bd[_i + 1] - _bd[_i] for _i in range(len(_bd) - 1)) < 2.8:
                _deep_splits = None
        if _turn_layout and has_stairs_landing:
            # The corner-loop stair hugs the walls, so the CENTRE of the floor
            # stays free: put square-ish rooms there (one combined living room
            # on a small floor; a short row of them on a deep one).
            # Inset the room only off the walls that actually carry a flight on
            # THIS floor (the one coming up and the one going up); the free
            # walls stay as the room boundary so furniture hugs the real walls
            # instead of lining a virtual box in the middle of the floor.
            _sides = set()
            for _hrect in (stair_hole, (stair_pos_info or {}).get('ascend_hole')):
                if not _hrect:
                    continue
                _hx0, _hx1, _hy0, _hy1 = _hrect
                if _hx0 - ix_min < 0.95:
                    _sides.add('W')
                if ix_max - _hx1 < 0.95:
                    _sides.add('E')
                if _hy0 - iy_min < 0.95:
                    _sides.add('S')
                if iy_max - _hy1 < 0.95:
                    _sides.add('N')
            _ins = 1.75
            _rx0 = ix_min + (_ins if 'W' in _sides else 0.0)
            _rx1 = ix_max - (_ins if 'E' in _sides else 0.0)
            _ry0 = iy_min + (_ins if 'S' in _sides else 0.0)
            _ry1 = iy_max - (_ins if 'N' in _sides else 0.0)
            _rw, _rd = _rx1 - _rx0, _ry1 - _ry0
            _fac = {'FRONT': (ix_min, ix_max), 'BACK': (ix_min, ix_max),
                    'LEFT': (iy_min, iy_max), 'RIGHT': (iy_min, iy_max)}
            # Roles per floor: a small home (2 storeys) gets one combined
            # kitchen/bed/living room upstairs; taller homes keep them on
            # SEPARATE floors so a stove is never in a bedroom.
            _tf = max(1, int(total_floors or 1))
            if _tf <= 2:
                _first_role = 'COTTAGE'
            elif fl_idx <= 1:
                _first_role = 'KITCHEN'
            else:
                _first_role = 'MASTER_BED' if fl_idx >= _tf - 1 else 'BEDROOM'
            if _rw > 1.8 and _rd > 1.8:
                _n = 1
                while _n < 4 and _rd / _n > _rw * 1.85:
                    _n += 1
                _roles = [_first_role] + ['BEDROOM'] * (_n - 1)
                rooms = []
                for _i in range(_n):
                    _b0 = _ry0 + _rd * _i / _n
                    _b1 = _ry0 + _rd * (_i + 1) / _n
                    rooms.append(Room(
                        id=f"fl{fl_idx}_room{_i}", floor_idx=fl_idx,
                        role=_roles[_i], bounds=(_rx0, _rx1, _b0, _b1),
                        doorways=list(doorways or []),
                        stair_hole=(stair_hole if _i == 0 else None),
                        exterior_facades=dict(_fac)))
            else:
                rooms = [Room(
                    id=f"fl{fl_idx}_cottage", floor_idx=fl_idx, role=_first_role,
                    bounds=(ix_min, ix_max, iy_min, iy_max),
                    doorways=list(doorways or []),
                    stair_hole=stair_hole, exterior_facades=dict(_fac))]
        elif _deep_splits is None:
            _deep_target = 2
            roles = _resolve_room_roles(effective_archetype, fl_idx, 2, has_stairs_landing, total_floors, program=program)
            # Keep the cross partition clear of the stair band on whichever side
            # the switchback actually occupies, so it never bisects the flights.
            if stair_guards_north:
                split_y = min(stair_safe_y_bot - 0.65, iy_min + D * 0.48)
                split_y = max(iy_min + 2.3, split_y)
            else:
                split_y = max(stair_safe_y_top + 0.65, iy_min + D * 0.48)
                split_y = min(iy_max - 2.3, split_y)
            split_y = _clear_doorway_span(split_y, axis='Y',
                                          lo=iy_min + 2.3, hi=iy_max - 1.8)
            split_y = _dodge_oven_band(split_y, iy_min + 2.3, iy_max - 1.8)
            if stair_hole is not None:
                # Never bisect the stair flight itself: nudge to the nearest
                # clear edge when the depth clamps forced the split inside it.
                _hh0, _hh1 = stair_hole[2] - 0.50, stair_hole[3] + 0.50
                if _hh0 < split_y < _hh1:
                    split_y = _hh0 if (split_y - _hh0) <= (_hh1 - split_y) else _hh1
                    split_y = min(max(split_y, iy_min + 2.3), iy_max - 1.8)

            dw_x = (ix_min + ix_max) * 0.5
            if abs(dw_x - (door_cx or 0.0)) < 0.4:
                dw_x += 0.85

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

            dw_x = (ix_min + ix_max) * 0.5
            if abs(dw_x - (door_cx or 0.0)) < 0.4:
                dw_x += 0.85

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
        if has_stairs_landing and stair_hole is not None:
            # Whoever holds the stairwell serves as the landing, so arrivals
            # never step off into a bedroom (also repairs the legacy heuristic
            # when the flight geometry disagrees with it).
            _holders = [r for r in rooms
                        if r.bounds[0] - 0.3 <= stair_hole[0] and stair_hole[1] <= r.bounds[1] + 0.3
                        and r.bounds[2] - 0.3 <= stair_hole[2] and stair_hole[3] <= r.bounds[3] + 0.3]
            if len(_holders) == 1 and _holders[0].role != 'STAIR_LANDING':
                for r in rooms:
                    if r is not _holders[0] and r.role == 'STAIR_LANDING':
                        r.role, _holders[0].role = _holders[0].role, r.role
                        break
        _force_bakehouse_chamber(rooms)

    # Add any wing rooms (the exterior-entrance tenement layout above already
    # created its own wing apartments, so never add duplicates).
    if fl_wings_bounds and not (effective_archetype == 'TENEMENT'
                                and getattr(props, 'has_exterior_stairs', False)):
        for wi, wb in enumerate(fl_wings_bounds):
            if effective_archetype in ('TAVERN', 'INN'):
                w_role = 'DINING'
                w_doorways = []
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
                w_doorways = []
            elif effective_archetype in ('TOWN_HALL', 'CIVIC', 'GUILDHALL'):
                w_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'MAYOR_OFFICE'
                w_doorways = []
            elif effective_archetype in ('BARRACKS', 'INFANTRY_BARRACKS', 'KNIGHTS_MANOR',
                                         'ARCHERY', 'ARCHERY_RANGE'):
                w_role = 'BARRACKS_DORM'
                w_doorways = []
            else:
                w_role = 'STORAGE' if (fl_idx == 0 or effective_archetype in
                                       ('WAREHOUSE', 'LUMBERMILL', 'BLACKSMITH')) else 'GUEST_ROOM'
                w_doorways = []
            w_rm = Room(
                id=f"fl{fl_idx}_wing{wi}",
                floor_idx=fl_idx,
                role=w_role,
                bounds=wb,
                is_wing=True,
                wing_id=wi,
                doorways=w_doorways,
                stair_hole=None,
                exterior_facades={}
            )
            rooms.append(w_rm)

    if doorways:
        for rm in rooms:
            rx0, rx1, ry0, ry1 = rm.bounds
            for d in doorways:
                dx, dy = d.get('x', 0.0), d.get('y', 0.0)
                dw = d.get('w', 0.95)
                axis = d.get('axis', 'X')
                if axis == 'X':
                    if (dx + dw * 0.5 >= rx0 - 0.20 and dx - dw * 0.5 <= rx1 + 0.20) and (ry0 - 0.55 <= dy <= ry1 + 0.55):
                        if d not in rm.doorways:
                            rm.doorways.append(d)
                else:
                    if (dy + dw * 0.5 >= ry0 - 0.20 and dy - dw * 0.5 <= ry1 + 0.20) and (rx0 - 0.55 <= dx <= rx1 + 0.55):
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

    # Fishmonger ground floor: ONE big open shop room (no side chambers) so the
    # trade has room to work; the catch is stored in barrels.
    if fl_idx == 0 and effective_archetype == 'FISHERMAN':
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


