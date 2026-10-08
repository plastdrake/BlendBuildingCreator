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

def build_floor_slab(bm, floor_idx, x_min, x_max, y_min, y_max, z_level, thickness=0.15, stair_hole=None, mat_idx=MAT_INDEX_FLOOR):
    """
    Builds a solid floor slab. If stair_hole (xmin, xmax, ymin, ymax) is provided,
    splits the floor slab into cleanly joined pieces leaving the stairwell opening open.
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
        # Planks run along the LONGEST span (beams cross the shortest).
        # Swap top/bottom UVs when Y is longest and tag faces so the final
        # cubic UV pass preserves this orientation.
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
    
    if stair_hole is None or floor_idx == 0:
        # Timber floors are the planks themselves—no duplicate hidden slab below.
        add_floor_region(x_min, x_max, y_min, y_max, floor_idx)
        return

    # Decompose floor into 4 rectangular slabs around the stairwell cutout:
    sx_min, sx_max, sy_min, sy_max = stair_hole
    # Clamp to bounds
    sx_min = max(x_min, min(x_max, sx_min))
    sx_max = max(x_min, min(x_max, sx_max))
    sy_min = max(y_min, min(y_max, sy_min))
    sy_max = max(y_min, min(y_max, sy_max))

    # 1. Left slab alongside stairwell from x_min up to sx_min (covers overhang & unused flight tracks)
    if sx_min > x_min + 0.02:
        add_floor_region(x_min, sx_min, y_min, y_max, floor_idx + 37)

    # 2. Right slab alongside stairwell from sx_max up to x_max
    if sx_max < x_max - 0.02:
        add_floor_region(sx_max, x_max, y_min, y_max, floor_idx)

    # 3. Front portion in front of stairwell (from y_min up to sy_min across stair width)
    if sy_min > y_min + 0.02:
        add_floor_region(sx_min, sx_max, y_min, sy_min, floor_idx + 11)

    # 4. Back portion behind stairwell (from sy_max up to y_max across stair width)
    if sy_max < y_max - 0.02:
        add_floor_region(sx_min, sx_max, sy_max, y_max, floor_idx + 23)

def build_ceiling_beams(bm, x_min, x_max, y_min, y_max, z_ceil, spacing=1.2, beam_w=0.14, beam_d=0.18, stair_hole=None):
    """
    Builds rustic timber cross-beams under the ceiling for that classic fantasy tavern interior.
    Beams always span the SHORTEST room distance (floorboards run along the longest).
    Automatically clips and trims beams around stairwells so beams never block stairs or head clearance.
    """
    beam_cz = z_ceil - (beam_d * 0.5)

    if (x_max - x_min) <= (y_max - y_min):
        total_y = y_max - y_min
        num_beams = max(2, int(total_y / spacing))
        actual_step = total_y / (num_beams + 1)

        # 1. Framing trimmer beam along the stairwell opening edge
        if stair_hole is not None:
            sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
            trimmer_len = (sh_ymax - sh_ymin) + 0.3
            trimmer_cy = (sh_ymin + sh_ymax) * 0.5
            create_beveled_box(
                bm,
                size=(beam_w, trimmer_len, beam_d),
                location=(sh_xmax, trimmer_cy, beam_cz),
                mat_index=MAT_INDEX_WOOD,
                bevel_amount=0.015
            )

        # 2. Cross beams spanning X
        for i in range(1, num_beams + 1):
            by = y_min + i * actual_step

            # Check if this beam crosses the stairwell cutout
            if stair_hole is not None:
                sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
                if (sh_ymin - 0.25) <= by <= (sh_ymax + 0.25):
                    # Trim the beam so it only spans from sh_xmax to x_max
                    if sh_xmax < x_max - 0.3:
                        w = (x_max + 0.02) - sh_xmax
                        cx = sh_xmax + w * 0.5
                        create_beveled_box(
                            bm,
                            size=(w, beam_w, beam_d),
                            location=(cx, by, beam_cz),
                            mat_index=MAT_INDEX_WOOD,
                            bevel_amount=0.015
                        )
                    # Also span beam on the left if there is floor on the left
                    if sh_xmin > x_min + 0.4:
                        w_left = sh_xmin - (x_min - 0.02)
                        cx_left = (x_min - 0.02) + w_left * 0.5
                        create_beveled_box(
                            bm,
                            size=(w_left, beam_w, beam_d),
                            location=(cx_left, by, beam_cz),
                            mat_index=MAT_INDEX_WOOD,
                            bevel_amount=0.015
                        )
                    continue

            # Full width beam � embedded 0.02 into interior plaster wall to prevent gaps without poking through roof
            beam_length = (x_max - x_min) + 0.04
            beam_cx = (x_min + x_max) * 0.5
            create_beveled_box(
                bm,
                size=(beam_length, beam_w, beam_d),
                location=(beam_cx, by, beam_cz),
                mat_index=MAT_INDEX_WOOD,
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
        create_beveled_box(
            bm,
            size=(trimmer_len, beam_w, beam_d),
            location=(trimmer_cx, trim_edge, beam_cz),
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.015
        )

    # 2. Cross beams spanning Y (the shorter distance)
    for i in range(1, num_beams + 1):
        bx = x_min + i * actual_step

        # Check if this beam crosses the stairwell cutout
        if stair_hole is not None:
            sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
            if (sh_xmin - 0.25) <= bx <= (sh_xmax + 0.25):
                # Trim the beam so it only spans from sh_ymax to y_max
                if sh_ymax < y_max - 0.3:
                    h = (y_max + 0.02) - sh_ymax
                    cy = sh_ymax + h * 0.5
                    create_beveled_box(
                        bm,
                        size=(beam_w, h, beam_d),
                        location=(bx, cy, beam_cz),
                        mat_index=MAT_INDEX_WOOD,
                        bevel_amount=0.015
                    )
                # Also span beam on the near side if there is floor there
                if sh_ymin > y_min + 0.4:
                    h_far = sh_ymin - (y_min - 0.02)
                    cy_far = (y_min - 0.02) + h_far * 0.5
                    create_beveled_box(
                        bm,
                        size=(beam_w, h_far, beam_d),
                        location=(bx, cy_far, beam_cz),
                        mat_index=MAT_INDEX_WOOD,
                        bevel_amount=0.015
                    )
                continue

        # Full depth beam � embedded 0.02 into interior plaster wall to prevent gaps without poking through roof
        beam_length = (y_max - y_min) + 0.04
        beam_cy = (y_min + y_max) * 0.5
        create_beveled_box(
            bm,
            size=(beam_w, beam_length, beam_d),
            location=(bx, beam_cy, beam_cz),
            mat_index=MAT_INDEX_WOOD,
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

def build_straight_staircase(bm, start_pos, target_z, stair_width=1.40, stair_depth=2.6, num_steps=14, direction_y=1):
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
}

_ARCHETYPE_PROGRAM = {
    'HOUSE': 'RESIDENTIAL', 'MANOR': 'RESIDENTIAL', 'TENEMENT': 'RESIDENTIAL',
    'TAVERN': 'HOSPITALITY', 'INN': 'HOSPITALITY',
    'TOWN_HALL': 'CIVIC', 'CIVIC': 'CIVIC', 'GUILDHALL': 'CIVIC',
    'BARRACKS': 'MILITARY', 'INFANTRY_BARRACKS': 'MILITARY', 'KNIGHTS_MANOR': 'MILITARY',
    'PALACE': 'PALACE', 'CASTLE': 'PALACE', 'NASHERS_MANOR': 'PALACE',
    'STABLE': 'STABLE',
    'ARCHERY': 'RANGER', 'ARCHERY_RANGE': 'RANGER',
    'CHAPEL': 'SACRED', 'HEALERS_CHAPEL': 'SACRED',
    'WAREHOUSE': 'INDUSTRIAL', 'LUMBERMILL': 'INDUSTRIAL', 'BLACKSMITH': 'INDUSTRIAL',
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
        elif archetype in ('WAREHOUSE', 'LUMBERMILL', 'BLACKSMITH', 'QUARRY'):
            # Industrial upper floors are work/storage, never bedrooms or kitchens.
            pool = ['STAIR_LANDING', 'STONE_STORE' if archetype == 'QUARRY' else 'STORAGE', 'WORKSHOP', 'OFFICE']
            return pool[:num_rooms]
        elif archetype in ('BAKERY', 'FISHERMAN', 'BREWERY',
                          'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER') or archetype.startswith('ARTISAN'):
            if fl_idx == 1:
                pool = ['STAIR_LANDING', 'HOUSE_HALL', 'BEDROOM', 'KITCHEN']
            else:
                pool = ['STAIR_LANDING', 'MASTER_BED', 'STUDY', 'BEDROOM']
            return pool[:num_rooms]
        elif archetype in ('BARRACKS', 'INFANTRY_BARRACKS'):
            pool = ['STAIR_LANDING', 'BARRACKS_DORM', 'BARRACKS_DORM', 'OFFICER_QUARTERS']
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
        pool = ['TAVERN_TAPROOM', 'KITCHEN', 'PANTRY', 'CELLAR']
        return pool[:num_rooms]

    if archetype in ('BLACKSMITH', 'WAREHOUSE', 'LUMBERMILL', 'QUARRY', 'BAKERY', 'FISHERMAN', 'BREWERY',
                     'BUTCHER', 'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER') or archetype.startswith('ARTISAN'):
        if archetype == 'QUARRY':
            pool = ['STONE_STORE', 'STORAGE', 'WORKSHOP', 'OFFICE']
        else:
            pool = ['STORE', 'WORKSHOP', 'STORAGE', 'PANTRY']
        return pool[:num_rooms]

    if archetype in ('BARRACKS', 'INFANTRY_BARRACKS'):
        pool = ['DRILL_HALL', 'MESS_HALL', 'ARMORY', 'STORAGE']
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
    return out


def _plan_manor_rooms(fl_idx, bounds, stair_hole, wall_t, dw_w, dw_h,
                      has_stairs_landing, stair_pos_info=None):
    """Manor-specific floor plan: dedicated stair hall + grand banquet hall.

    Large manor footprints (W >= 16m) get a 4-column grid instead of the generic
    2-column split, so rooms stay at sensible domestic sizes:
      - west strip: full-depth stair hall (the flight stands here, clear of
        every partition, with a 1.2m walk-off at its foot);
      - inner columns: kitchen/pantry split, full-depth banquet hall,
        library/study split.
    The stairs never sit inside the kitchen or a bedroom anymore.
    Returns (rooms, interior_walls) or None when the footprint is too small.
    """
    ix_min, ix_max, iy_min, iy_max = bounds
    W = ix_max - ix_min
    D = iy_max - iy_min
    if W < 16.0 or D < 7.0:
        return None

    # West strip holds the whole stair well plus a walkway beside it.
    if stair_pos_info:
        try:
            _cx = float(stair_pos_info.get('cx', 0.0))
            _w = float(stair_pos_info.get('w', 1.5))
            c0w = (_cx + _w * 0.5 + 1.0) - ix_min
        except Exception:
            c0w = W * 0.22
    else:
        c0w = W * 0.22
    c0w = min(max(c0w, 3.5), W * 0.30)
    rest = W - c0w
    b1 = ix_min + c0w
    b2 = b1 + rest / 3.0
    b3 = b1 + rest * 2.0 / 3.0
    yA = (iy_min + iy_max) * 0.5
    yB = (iy_min + iy_max) * 0.5

    walls = []

    def _vwall(px, y0, y1):
        dw_y = (y0 + y1) * 0.5
        walls.append({
            'p1': (px, y0), 'p2': (px, y1),
            'axis': 'Y', 'pos': px, 'thickness': wall_t,
            'doorway': {'x': px, 'y': dw_y, 'w': dw_w, 'h': dw_h, 'axis': 'Y'},
        })

    # West strip has no cross-divider: the flight runs full-depth clear.
    _vwall(b1, iy_min, yA)
    _vwall(b1, yA, iy_max)
    _vwall(b2, iy_min, yA)
    _vwall(b2, yA, iy_max)
    walls.append({
        'p1': (b1, yA), 'p2': (b2, yA),
        'axis': 'X', 'pos': yA, 'thickness': wall_t, 'doorway': None,
    })
    _vwall(b3, iy_min, yB)
    _vwall(b3, yB, iy_max)
    walls.append({
        'p1': (b3, yB), 'p2': (ix_max, yB),
        'axis': 'X', 'pos': yB, 'thickness': wall_t, 'doorway': None,
    })

    def _dw(x, y, axis):
        return {'x': x, 'y': y, 'axis': axis, 'w': dw_w}

    def _holds_stair(rb):
        if stair_hole is None:
            return None
        pad = 0.30
        if rb[1] < stair_hole[0] - pad or rb[0] > stair_hole[1] + pad \
                or rb[3] < stair_hole[2] - pad or rb[2] > stair_hole[3] + pad:
            return None
        return stair_hole

    rooms = []
    # Dedicated full-depth stair hall (west strip).
    _bs = (ix_min, b1, iy_min, iy_max)
    _stair_role = 'ENTRANCE_HALL' if fl_idx == 0 else 'STAIR_LANDING'
    rooms.append(Room(
        id=f"fl{fl_idx}_stair_hall", floor_idx=fl_idx, role=_stair_role,
        bounds=_bs,
        doorways=[_dw(b1, (iy_min + yA) * 0.5, 'Y'),
                  _dw(b1, (yA + iy_max) * 0.5, 'Y')],
        stair_hole=_holds_stair(_bs),
        exterior_facades={'FRONT': (ix_min, b1), 'BACK': (ix_min, b1),
                          'LEFT': (iy_min, iy_max)}))

    # Inner-west column split front/back (kitchen + pantry / bedrooms).
    if fl_idx == 0:
        _r0, _r1 = 'KITCHEN', 'PANTRY'
    elif has_stairs_landing:
        _r0, _r1 = 'BEDROOM', 'BEDROOM'
    else:
        _r0, _r1 = 'MASTER_BED', 'BEDROOM'
    _b0 = (b1, b2, iy_min, yA)
    _b1 = (b1, b2, yA, iy_max)
    rooms.append(Room(
        id=f"fl{fl_idx}_kitchen", floor_idx=fl_idx, role=_r0,
        bounds=_b0, doorways=[_dw(b1, (iy_min + yA) * 0.5, 'Y'),
                              _dw(b2, (iy_min + yA) * 0.5, 'Y')],
        stair_hole=_holds_stair(_b0),
        exterior_facades={'FRONT': (b1, b2)}))
    rooms.append(Room(
        id=f"fl{fl_idx}_pantry", floor_idx=fl_idx, role=_r1,
        bounds=_b1, doorways=[_dw(b1, (yA + iy_max) * 0.5, 'Y'),
                              _dw(b2, (yA + iy_max) * 0.5, 'Y')],
        stair_hole=_holds_stair(_b1),
        exterior_facades={'BACK': (b1, b2)}))

    # Full-depth banquet hall / grand suite (center-east column).
    _bc = (b2, b3, iy_min, iy_max)
    _crole = 'BANQUET_HALL' if fl_idx == 0 else (
        'MASTER_BED' if has_stairs_landing else 'GUEST_ROOM')
    rooms.append(Room(
        id=f"fl{fl_idx}_banquet", floor_idx=fl_idx, role=_crole,
        bounds=_bc,
        doorways=[_dw(b2, (iy_min + yA) * 0.5, 'Y'),
                  _dw(b2, (yA + iy_max) * 0.5, 'Y'),
                  _dw(b3, (iy_min + yB) * 0.5, 'Y'),
                  _dw(b3, (yB + iy_max) * 0.5, 'Y')],
        stair_hole=_holds_stair(_bc),
        exterior_facades={'FRONT': (b2, b3), 'BACK': (b2, b3)}))

    # East column split front/back (library + study).
    _b2 = (b3, ix_max, iy_min, yB)
    _b3 = (b3, ix_max, yB, iy_max)
    rooms.append(Room(
        id=f"fl{fl_idx}_library", floor_idx=fl_idx, role='LIBRARY',
        bounds=_b2, doorways=[_dw(b3, (iy_min + yB) * 0.5, 'Y')],
        stair_hole=_holds_stair(_b2),
        exterior_facades={'FRONT': (b3, ix_max), 'RIGHT': (iy_min, yB)}))
    rooms.append(Room(
        id=f"fl{fl_idx}_study", floor_idx=fl_idx, role='STUDY',
        bounds=_b3, doorways=[_dw(b3, (yB + iy_max) * 0.5, 'Y')],
        stair_hole=_holds_stair(_b3),
        exterior_facades={'BACK': (b3, ix_max), 'RIGHT': (yB, iy_max)}))
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

    # Grand manor plan: wide noble footprints use a dedicated 4-column grid
    # (full-depth stair hall + kitchen/pantry + banquet hall + library/study)
    # so rooms stay at sensible domestic sizes and the stairs never sit
    # inside the kitchen or a bedroom.
    if effective_archetype == 'MANOR' and has_interior_walls \
            and partition_style in ('AUTO', 'HALL_CHAMBERS'):
        _manor = _plan_manor_rooms(fl_idx, bounds, stair_hole, wall_t,
                                   dw_w, dw_h, has_stairs_landing,
                                   stair_pos_info=stair_pos_info)
        if _manor is not None:
            _manor_rooms, _manor_walls = _manor
            if fl_wings_bounds:
                for wi, wb in enumerate(fl_wings_bounds):
                    if fl_idx == 0:
                        w_role = 'STUDY' if wi == 0 else 'GUEST_ROOM'
                    else:
                        w_role = 'BEDROOM' if wi == 0 else 'GUEST_ROOM'
                    _manor_rooms.append(Room(
                        id=f"fl{fl_idx}_wing{wi}", floor_idx=fl_idx,
                        role=w_role, bounds=wb, is_wing=True, wing_id=wi,
                        doorways=[], stair_hole=None, exterior_facades={}))
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

    # Decide layout mode
    is_deep = (D > W * 1.25 and D >= 6.5
               and effective_archetype != 'TENEMENT')
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
        min_split_x = stair_safe_x + 0.60
        if door_cx is not None:
            min_split_x = max(min_split_x, door_cx + 0.95)

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
        if can_4_rooms and _cw_now >= 2.4 and not _strip_chunky(_hw_now, _cw_now, _f4):
            can_4_rooms = False
        if can_3_rooms and not _strip_chunky(_hw_now, _cw_now, _f3):
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
                    stair_hole=stair_hole,
                    exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
                )
                rm1 = Room(
                    id=f"fl{fl_idx}_archive", floor_idx=fl_idx, role='ARCHIVE',
                    bounds=(split_x, ix_max, iy_min, iy_max),
                    doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                    stair_hole=None,
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
                stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_kitchen", floor_idx=fl_idx, role='KITCHEN',
                bounds=(split_x, ix_max, iy_min, iy_max),
                doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
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

            dw_y1 = (iy_min + split_y1) * 0.5
            dw_y2 = (split_y1 + split_y2) * 0.5
            dw_y3 = (split_y2 + iy_max) * 0.5

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
            interior_walls.append({
                'p1': (split_x, split_y2), 'p2': (split_x, iy_max),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y3, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            interior_walls.append({
                'p1': (split_x, split_y1), 'p2': (ix_max, split_y1),
                'axis': 'X', 'pos': split_y1, 'thickness': wall_t, 'doorway': None
            })
            interior_walls.append({
                'p1': (split_x, split_y2), 'p2': (ix_max, split_y2),
                'axis': 'X', 'pos': split_y2, 'thickness': wall_t, 'doorway': None
            })

            rm0 = Room(
                id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role=roles[0],
                bounds=(ix_min, split_x, iy_min, iy_max),
                doorways=[
                    {'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w},
                    {'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w},
                    {'x': split_x, 'y': dw_y3, 'axis': 'Y', 'w': dw_w},
                ],
                stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_chamber_1", floor_idx=fl_idx, role=roles[1],
                bounds=(split_x, ix_max, iy_min, split_y1),
                doorways=[{'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
                exterior_facades={'FRONT': (split_x, ix_max), 'RIGHT': (iy_min, split_y1)}
            )
            rm2 = Room(
                id=f"fl{fl_idx}_chamber_2", floor_idx=fl_idx, role=roles[2],
                bounds=(split_x, ix_max, split_y1, split_y2),
                doorways=[{'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
                exterior_facades={'RIGHT': (split_y1, split_y2)}
            )
            rm3 = Room(
                id=f"fl{fl_idx}_chamber_3", floor_idx=fl_idx, role=roles[3],
                bounds=(split_x, ix_max, split_y2, iy_max),
                doorways=[{'x': split_x, 'y': dw_y3, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
                exterior_facades={'BACK': (split_x, ix_max), 'RIGHT': (split_y2, iy_max)}
            )
            rooms = [rm0, rm1, rm2, rm3]

        elif can_3_rooms and (D >= 5.4) and (ix_max - split_x >= 2.2):
            # 3 Rooms total (Landing/Corridor on Left + 2 Chambers on Right)
            roles = _resolve_room_roles(effective_archetype, fl_idx, 3, has_stairs_landing, total_floors, program=program)
            # One bigger kitchen: the kitchen chamber takes ~58% of the strip.
            _kf = 0.58 if (len(roles) > 1 and roles[1] == 'KITCHEN') else 0.50
            split_y = _clear_doorway_span(iy_min + D * _kf, axis='Y')

            dw_y1 = (iy_min + split_y) * 0.5
            dw_y2 = (split_y + iy_max) * 0.5

            interior_walls.append({
                'p1': (split_x, iy_min), 'p2': (split_x, split_y),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y1, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            interior_walls.append({
                'p1': (split_x, split_y), 'p2': (split_x, iy_max),
                'axis': 'Y', 'pos': split_x, 'thickness': wall_t,
                'doorway': {'x': split_x, 'y': dw_y2, 'w': dw_w, 'h': dw_h, 'axis': 'Y'}
            })
            interior_walls.append({
                'p1': (split_x, split_y), 'p2': (ix_max, split_y),
                'axis': 'X', 'pos': split_y, 'thickness': wall_t, 'doorway': None
            })

            rm0 = Room(
                id=f"fl{fl_idx}_hall", floor_idx=fl_idx, role=roles[0],
                bounds=(ix_min, split_x, iy_min, iy_max),
                doorways=[
                    {'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w},
                    {'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}
                ],
                stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_chamber_se", floor_idx=fl_idx, role=roles[1],
                bounds=(split_x, ix_max, iy_min, split_y),
                doorways=[{'x': split_x, 'y': dw_y1, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
                exterior_facades={'FRONT': (split_x, ix_max), 'RIGHT': (iy_min, split_y)}
            )
            rm2 = Room(
                id=f"fl{fl_idx}_chamber_ne", floor_idx=fl_idx, role=roles[2],
                bounds=(split_x, ix_max, split_y, iy_max),
                doorways=[{'x': split_x, 'y': dw_y2, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
                exterior_facades={'BACK': (split_x, ix_max), 'RIGHT': (split_y, iy_max)}
            )
            rooms = [rm0, rm1, rm2]

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
                stair_hole=stair_hole,
                exterior_facades={'FRONT': (ix_min, split_x), 'BACK': (ix_min, split_x), 'LEFT': (iy_min, iy_max)}
            )
            rm1 = Room(
                id=f"fl{fl_idx}_chamber", floor_idx=fl_idx, role=roles[1],
                bounds=(split_x, ix_max, iy_min, iy_max),
                doorways=[{'x': split_x, 'y': dw_y, 'axis': 'Y', 'w': dw_w}],
                stair_hole=None,
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
                        stair_hole=stair_hole,
                        exterior_facades={'FRONT': (_hx0, _bay),
                                          'BACK': (_hx0, _bay),
                                          'LEFT': (iy_min, iy_max)})
                    _hall.bounds = (_bay, _hx1, iy_min, iy_max)
                    _hall.stair_hole = None
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
        # Deep building: Partition along X (horizontal wall at Y = split_y, running from ix_min to ix_max)
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

        rm0 = Room(
            id=f"fl{fl_idx}_front", floor_idx=fl_idx, role=front_role,
            bounds=(ix_min, ix_max, iy_min, split_y),
            doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
            stair_hole=stair_hole if (has_stairs_landing and not stair_guards_north) else None,
            exterior_facades={'FRONT': (ix_min, ix_max), 'LEFT': (iy_min, split_y), 'RIGHT': (iy_min, split_y)}
        )
        rm1 = Room(
            id=f"fl{fl_idx}_back", floor_idx=fl_idx, role=back_role,
            bounds=(ix_min, ix_max, split_y, iy_max),
            doorways=[{'x': dw_x, 'y': split_y, 'axis': 'X', 'w': dw_w}],
            stair_hole=stair_hole if (has_stairs_landing and stair_guards_north) else None,
            exterior_facades={'BACK': (ix_min, ix_max), 'LEFT': (split_y, iy_max), 'RIGHT': (split_y, iy_max)}
        )
        rooms = [rm0, rm1]

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


