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
from .railing import build_railing, build_railing_post
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
        # Convert them to this interior segment and expand a little for the jamb.
        cuts = []
        reversed_from_wall_builder = side in {'back', 'left'}
        outer_length = length + wall_thickness * 2.0
        for opening in wall_openings.get(side, []):
            if opening.get('z_start', z_floor + 1.0) <= z_floor + trim_h_floor:
                clr = opening.get('trim_clearance', reveal)
                if reversed_from_wall_builder:
                    a = outer_length - opening.get('u_end', 0.0) - wall_thickness - clr
                    b = outer_length - opening.get('u_start', 0.0) - wall_thickness + clr
                else:
                    a = opening.get('u_start', 0.0) - wall_thickness - clr
                    b = opening.get('u_end', 0.0) - wall_thickness + clr
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
    Uses the shared detailed railing builder.
    """
    if y_end - y_start < 0.3:
        return
    build_railing(bm, (rail_x, y_start), (rail_x, y_end), floor_z, height=rail_h)
    if return_y is not None and x_start is not None and abs(rail_x - x_start) > 0.3:
        build_railing(bm, (x_start, return_y), (rail_x, return_y), floor_z,
                      height=rail_h, braces=False, post_spacing=1.0)

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

    # 5. Detailed guard railings on BOTH sides, following the flight's pitch
    for side in [-1, 1]:
        rail_x = x0 + side * (stair_width * 0.5 + stringer_thick * 0.5)
        build_railing(
            bm,
            (rail_x, y0 + 0.06 * direction_y),
            (rail_x, y0 + (stair_depth - 0.06) * direction_y),
            z0 + 0.06, height=0.92, base_z_end=target_z + 0.06,
            post_spacing=1.1, baluster_spacing=0.20, braces=False,
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
        
        # Outer banister point on every step (post added after the loop)
        px = cx + (radius - 0.04) * math.cos(mid_ang)
        py = cy + (radius - 0.04) * math.sin(mid_ang)
        posts.append(Vector((px, py, cur_z)))
        
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

