"""
Interior architecture generator for stylized fantasy buildings.
Generates floor plates with stairwell cutouts, rustic exposed ceiling beams,
staircases (straight/L or fantasy spiral), and roof rafters.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder
from .materials import MAT_INDEX_FLOOR, MAT_INDEX_STONE, MAT_INDEX_WOOD, MAT_INDEX_TIMBER, MAT_INDEX_STAIRS, MAT_INDEX_RAILING


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
        create_box(
            bm, size=(rx_max - rx_min, ry_max - ry_min, thickness),
            location=((rx_min + rx_max) * 0.5, (ry_min + ry_max) * 0.5,
                      (z_bottom + z_top) * 0.5), mat_index=mat_idx
        )
    
    if stair_hole is None or floor_idx == 0:
        # Timber floors are the planks themselves—no duplicate hidden slab below.
        add_floor_region(x_min, x_max, y_min, y_max, floor_idx)
        return

    # Decompose floor into 2 or 3 rectangular slabs around the stairwell cutout
    sx_min, sx_max, sy_min, sy_max = stair_hole
    # Clamp to bounds
    sx_min = max(x_min, min(x_max, sx_min))
    sx_max = max(x_min, min(x_max, sx_max))
    sy_min = max(y_min, min(y_max, sy_min))
    sy_max = max(y_min, min(y_max, sy_max))

    # Main room slab alongside stairwell (from x_max down to sx_max)
    if sx_max < x_max:
        w = x_max - sx_max
        cx = (x_max + sx_max) * 0.5
        add_floor_region(sx_max, x_max, y_min, y_max, floor_idx)

    # Front portion in front of stairwell (from y_min up to sy_min)
    if sy_min > y_min:
        w = sx_max - x_min
        cx = (sx_max + x_min) * 0.5
        h = sy_min - y_min
        cy = (sy_min + y_min) * 0.5
        add_floor_region(x_min, sx_max, y_min, sy_min, floor_idx + 11)

    # Back portion behind stairwell (if any space)
    if sy_max < y_max:
        w = sx_max - x_min
        cx = (sx_max + x_min) * 0.5
        h = y_max - sy_max
        cy = (y_max + sy_max) * 0.5
        add_floor_region(x_min, sx_max, sy_max, y_max, floor_idx + 23)

def build_ceiling_beams(bm, x_min, x_max, y_min, y_max, z_ceil, spacing=1.2, beam_w=0.14, beam_d=0.18, stair_hole=None):
    """
    Builds rustic timber cross-beams under the ceiling for that classic fantasy tavern interior.
    Automatically clips and trims beams around stairwells so beams never block stairs or head clearance.
    """
    total_y = y_max - y_min
    num_beams = max(2, int(total_y / spacing))
    actual_step = total_y / (num_beams + 1)
    
    beam_cz = z_ceil - (beam_d * 0.5)
    
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

    # 2. Cross beams
    for i in range(1, num_beams + 1):
        by = y_min + i * actual_step
        
        # Check if this beam crosses the stairwell cutout
        if stair_hole is not None:
            sh_xmin, sh_xmax, sh_ymin, sh_ymax = stair_hole
            if (sh_ymin - 0.25) <= by <= (sh_ymax + 0.25):
                # Trim the beam so it only spans from sh_xmax to x_max
                if sh_xmax < x_max - 0.3:
                    w = x_max - sh_xmax
                    cx = sh_xmax + w * 0.5
                    create_beveled_box(
                        bm,
                        size=(w, beam_w, beam_d),
                        location=(cx, by, beam_cz),
                        mat_index=MAT_INDEX_WOOD,
                        bevel_amount=0.015
                    )
                continue
                
        # Full width beam — extended 0.28 into walls to prevent short gap
        beam_length = x_max - x_min + 0.28
        beam_cx = (x_min + x_max) * 0.5
        create_beveled_box(
            bm,
            size=(beam_length, beam_w, beam_d),
            location=(beam_cx, by, beam_cz),
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
        # Convert them to this interior segment and expand a little for the jamb.
        cuts = []
        reversed_from_wall_builder = side in {'back', 'left'}
        outer_length = length + wall_thickness * 2.0
        for opening in wall_openings.get(side, []):
            if opening.get('z_start', z_floor + 1.0) <= z_floor + trim_h_floor:
                if reversed_from_wall_builder:
                    a = outer_length - opening.get('u_end', 0.0) - wall_thickness - reveal
                    b = outer_length - opening.get('u_start', 0.0) - wall_thickness + reveal
                else:
                    a = opening.get('u_start', 0.0) - wall_thickness - reveal
                    b = opening.get('u_end', 0.0) - wall_thickness + reveal
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

def build_stair_guardrail(bm, rail_x, y_start, y_end, floor_z, rail_h=0.95, return_y=None, x_start=None):
    """
    Builds a safety guardrail on the upper floor along the open edge of the stairwell
    (at X = rail_x, from y_start to y_end).
    If return_y and x_start are given, also adds the short return rail along the open end.
    """
    span_y = y_end - y_start
    if span_y < 0.3:
        return
        
    post_w = 0.09
    rail_w = 0.08
    sill_h = 0.05
    
    # 0. Solid Grounded Base Sill (long side)
    create_box(
        bm,
        size=(rail_w, span_y + post_w * 0.5, sill_h),
        location=(rail_x, (y_start + y_end) * 0.5, floor_z + sill_h * 0.5),
        mat_index=MAT_INDEX_WOOD
    )
    
    # 1. Corner Posts at start and end of open edge
    create_beveled_box(bm, size=(post_w, post_w, rail_h), location=(rail_x, y_start, floor_z + rail_h * 0.5), mat_index=MAT_INDEX_WOOD, bevel_amount=0.01)
    create_beveled_box(bm, size=(post_w, post_w, rail_h), location=(rail_x, y_end, floor_z + rail_h * 0.5), mat_index=MAT_INDEX_WOOD, bevel_amount=0.01)
    
    # 2. Top Handrail
    create_box(bm, size=(rail_w, span_y + post_w * 0.5, 0.06), location=(rail_x, (y_start + y_end) * 0.5, floor_z + rail_h - 0.03), mat_index=MAT_INDEX_WOOD)
    
    # 3. Mid Rail
    create_box(bm, size=(rail_w * 0.75, span_y, 0.04), location=(rail_x, (y_start + y_end) * 0.5, floor_z + rail_h * 0.5), mat_index=MAT_INDEX_WOOD)
    
    # 4. Spindles/Balusters (long side)
    num_spindles = max(1, int(span_y / 0.28))
    step = span_y / (num_spindles + 1)
    spindle_h = rail_h - sill_h - 0.06
    for i in range(1, num_spindles + 1):
        sy = y_start + i * step
        create_cylinder(
            bm,
            radius=0.022,
            height=spindle_h,
            segments=6,
            location=(rail_x, sy, floor_z + sill_h + spindle_h * 0.5),
            mat_index=MAT_INDEX_WOOD
        )
        
    # 5. Short Return Guardrail (protecting the open end of the floor hole)
    if return_y is not None and x_start is not None and abs(rail_x - x_start) > 0.3:
        span_x = abs(rail_x - x_start)
        cx = (x_start + rail_x) * 0.5
        # Return base sill
        create_box(bm, size=(span_x, rail_w, sill_h), location=(cx, return_y, floor_z + sill_h * 0.5), mat_index=MAT_INDEX_WOOD)
        # End post at x_start
        create_beveled_box(bm, size=(post_w, post_w, rail_h), location=(x_start, return_y, floor_z + rail_h * 0.5), mat_index=MAT_INDEX_WOOD, bevel_amount=0.01)
        # Return top rail
        create_box(bm, size=(span_x, rail_w, 0.06), location=(cx, return_y, floor_z + rail_h - 0.03), mat_index=MAT_INDEX_WOOD)
        # Return mid rail
        create_box(bm, size=(span_x, rail_w * 0.75, 0.04), location=(cx, return_y, floor_z + rail_h * 0.5), mat_index=MAT_INDEX_WOOD)
        # Return spindles
        num_sp_x = max(1, int(span_x / 0.28))
        step_x = span_x / (num_sp_x + 1)
        min_x = min(x_start, rail_x)
        for i in range(1, num_sp_x + 1):
            sx = min_x + i * step_x
            create_cylinder(bm, radius=0.022, height=spindle_h, segments=6, location=(sx, return_y, floor_z + sill_h + spindle_h * 0.5), mat_index=MAT_INDEX_WOOD)

def build_straight_staircase(bm, start_pos, target_z, stair_width=0.9, stair_depth=2.2, num_steps=14, direction_y=1):
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
        # Wood grain oriented along length (X) of each stair step
        for f in tread_faces:
            if not f.is_valid:
                continue
            for loop in f.loops:
                co = loop.vert.co
                u = (co.x - (sx - stair_width * 0.5)) * 0.65 + (i * 0.37)
                v = (co.y - (sy - tread_d * 0.5)) * 1.5 + (co.z - sz) * 1.2 + (i * 0.19)
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
                u = (co.x - (sx - stair_width * 0.5)) * 1.5 + (i * 0.37 + 0.15)
                v = (co.z - (sz - step_h * 0.5)) * 0.65 + (i * 0.19)
                loop[uv_layer].uv = Vector((u, v))
        
    # 3. Side Stringer Boards (anchored from starter base to upper landing)
    stringer_thick = 0.08
    stringer_h = 0.20
    diag_length = math.sqrt(dz * dz + stair_depth * stair_depth)
    pitch_angle = math.atan2(dz, stair_depth) * direction_y
    cos_pitch = math.cos(abs(pitch_angle))
    
    for side in [-1, 1]:
        str_x = x0 + side * (stair_width * 0.5 + stringer_thick * 0.5)
        str_y = y0 + (stair_depth * 0.5) * direction_y
        str_z = z0 + dz * 0.5
        # create_box automatically unwraps V strictly along the diagonal beam length (dy)
        create_box(
            bm,
            size=(stringer_thick, diag_length, stringer_h),
            location=(str_x, str_y, str_z),
            rotation=(pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_STAIRS
        )
        
    # 4. Top Landing Anchor Timber (anchors stringers solidly to the upper floor)
    top_faces = create_beveled_box(
        bm,
        size=(stair_width + 0.18, 0.22, 0.10),
        location=(x0, y0 + stair_depth * direction_y, target_z - 0.05),
        mat_index=MAT_INDEX_STAIRS,
        bevel_amount=0.012
    )
    for f in top_faces:
        if f.is_valid:
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_layer].uv = Vector(((co.x - x0) * 1.5, (co.y - (y0 + stair_depth * direction_y)) * 0.65 + (co.z - target_z) * 1.2))

    # 5. Stylized Newel Posts & Handrails on BOTH SIDES
    post_h = 0.95
    post_w = 0.09
    rail_thick = 0.07
    
    # Handrail spans precisely between the inner faces of bottom and top newel posts
    post_span_y = stair_depth - 0.10
    rail_span_y = max(0.2, post_span_y - post_w + 0.02)
    rail_diag_len = rail_span_y / cos_pitch
    rail_cy = y0 + (stair_depth * 0.5) * direction_y
    rail_cz = z0 + dz * 0.5 + post_h * 0.88
    
    for side in [-1, 1]:
        rail_x = x0 + side * (stair_width * 0.5 + stringer_thick * 0.5)
        # Bottom post with chamfered cap
        create_beveled_box(bm, size=(post_w, post_w, post_h),
                           location=(rail_x, y0 + 0.05 * direction_y, z0 + post_h * 0.5),
                           mat_index=MAT_INDEX_RAILING, bevel_amount=0.012)
        # Top post with chamfered cap
        create_beveled_box(bm, size=(post_w, post_w, post_h),
                           location=(rail_x, y0 + (stair_depth - 0.05) * direction_y, target_z + post_h * 0.5),
                           mat_index=MAT_INDEX_RAILING, bevel_amount=0.012)
        # Handrail bar (terminated flush inside posts, zero external poke; V unwrapped along length)
        create_box(
            bm,
            size=(rail_thick, rail_diag_len, rail_thick),
            location=(rail_x, rail_cy, rail_cz),
            rotation=(pitch_angle, 0.0, 0.0),
            mat_index=MAT_INDEX_RAILING
        )
        # Vertical spindles along run (seated flush on top of stringer, inserting into handrail underside)
        for i in range(1, num_steps):
            by = y0 + (i + 0.5) * step_d
            t_y = ((by - y0) * direction_y) / stair_depth
            
            # Exact top surface of the diagonal stringer beam at this Y position
            z_str_center = z0 + t_y * dz
            z_str_top = z_str_center + (stringer_h * 0.5) / cos_pitch
            
            # Exact underside of the handrail beam at this Y position
            z_rail_center = z0 + t_y * dz + post_h * 0.88
            z_rail_bot = z_rail_center - (rail_thick * 0.5) / cos_pitch
            
            spindle_len = z_rail_bot - z_str_top
            if spindle_len > 0.05:
                spindle_cz = (z_str_top + z_rail_bot) * 0.5
                create_box(
                    bm,
                    size=(0.034, 0.034, spindle_len),
                    location=(rail_x, by, spindle_cz),
                    mat_index=MAT_INDEX_RAILING
                )

def build_spiral_staircase(bm, center_pos, target_z, radius=1.0, num_steps=16, start_ang_deg=-90.0, total_angle_deg=360.0):
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
    col_r = 0.14
    create_cylinder(
        bm,
        radius=col_r,
        height=dz + 0.05,
        segments=12,
        location=(cx, cy, z0 + dz * 0.5),
        mat_index=MAT_INDEX_WOOD
    )
    
    # 2. Wedge steps
    step_len = radius - col_r
    posts = []
    
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
        create_beveled_box(
            bm,
            size=(step_len + 0.04, max(0.20, step_w), 0.065),
            location=(sx, sy, cur_z - 0.032),
            rotation=(0.0, 0.0, mid_ang),
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.01
        )
        
        # Outer banister post on every step
        px = cx + (radius - 0.04) * math.cos(mid_ang)
        py = cy + (radius - 0.04) * math.sin(mid_ang)
        pz = cur_z + 0.42
        posts.append(Vector((px, py, cur_z + 0.85)))
        create_cylinder(
            bm,
            radius=0.026,
            height=0.88,
            segments=6,
            location=(px, py, pz),
            mat_index=MAT_INDEX_WOOD
        )
        
    # 3. Dedicated Top Landing Platform (flushes perfectly with upper floor level at target_z)
    land_len = step_len + 0.35
    land_w = max(0.42, 2.0 * (col_r + land_len * 0.5) * math.tan(step_ang * 0.5) * 1.5)
    land_r = col_r + land_len * 0.5
    land_ang = base_ang + ang_rad
    land_x = cx + land_r * math.cos(land_ang)
    land_y = cy + land_r * math.sin(land_ang)
    create_beveled_box(
        bm,
        size=(land_len, land_w, 0.065),
        location=(land_x, land_y, target_z - 0.032),
        rotation=(0.0, 0.0, land_ang),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.012
    )
    
    # Top landing post
    top_px = cx + (radius + 0.15) * math.cos(land_ang)
    top_py = cy + (radius + 0.15) * math.sin(land_ang)
    posts.append(Vector((top_px, top_py, target_z + 0.85)))
    create_cylinder(
        bm,
        radius=0.035,
        height=0.90,
        segments=8,
        location=(top_px, top_py, target_z + 0.42),
        mat_index=MAT_INDEX_WOOD
    )
    
    # 4. Continuous outer handrail segments connecting posts
    for idx in range(len(posts) - 1):
        p1 = posts[idx]
        p2 = posts[idx + 1]
        seg_vec = p2 - p1
        seg_len = seg_vec.length
        if seg_len > 0.01:
            seg_mid = (p1 + p2) * 0.5
            rot_z = math.atan2(seg_vec.y, seg_vec.x)
            rot_pitch = -math.atan2(seg_vec.z, math.sqrt(seg_vec.x**2 + seg_vec.y**2))
            # Handrail bar
            rot_mat = Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(rot_pitch, 4, 'Y')
            create_box(
                bm,
                size=(seg_len, 0.05, 0.06),
                location=seg_mid,
                rotation=rot_mat.to_euler(),
                mat_index=MAT_INDEX_WOOD
            )

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

