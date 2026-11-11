"""
Hajfin Pirate Civilization Dedicated Procedural Architecture Generator.

Completely distinct procedural geometry pipeline for the Hajfin shark-humanoid pirate faction:
- Chunky tapered round huts, multi-tier staggered longhouses, barter trading posts, and crate shanties.
- Real cut doorways with recessed timber plank doors, deep jambs, and shark jaw arches with teeth.
- Solid gable triangle walls extending all the way into the roof peaks (zero open gaps).
- Solid weather-tight roof decks with 3D overlapping rounded bone / shark-scale plates and moss.
- Roof ridge dorsal fins and jagged bone spike crests firmly anchored into the ridge beams.
- Bone-framed barred windows with deep dark alcoves.
- Oversized corner timber columns with iron bracket cuffs, beveled caps, and wall spikes.
- Projecting whale rib tunnel entrances and whale vertebrae spinal buttresses.
- Open barter counters with flip-up plank awnings, ladders, and dock decks.
"""

import math
import random
import bmesh
from mathutils import Vector, Matrix
from .materials import (
    setup_building_material_slots,
    MAT_INDEX_DRIFTWOOD,
    MAT_INDEX_ROUGH_STONE,
    MAT_INDEX_BONE,
    MAT_INDEX_IRON,
    MAT_INDEX_ROPE,
    MAT_INDEX_FLOOR,
    MAT_INDEX_LOG,
    MAT_INDEX_WOOD,
    MAT_INDEX_GLASS,
    MAT_INDEX_SHINGLES,
    MAT_INDEX_TIMBER,
    MAT_INDEX_SIGN,
    MAT_INDEX_LANTERN,
    MAT_INDEX_BANNER,
    MAT_INDEX_LEATHER,
)
from .mesh_utils import (
    create_box,
    create_cylinder,
    create_cone,
    create_torus_ring,
    apply_box_uvs,
    transform_faces,
)


# =============================================================================
# SIGNATURE ARCHITECTURAL COMPONENTS & INTERIOR CIRCULATION
# =============================================================================

def _create_oriented_beam(bm, p0, p1, width=0.30, depth=0.30, mat_index=MAT_INDEX_TIMBER):
    """Creates a rectangular timber beam connecting any two 3D points p0 and p1
    with longitudinal wood grain unwrapped along its length."""
    v0 = Vector(p0)
    v1 = Vector(p1)
    v_dir = v1 - v0
    length = v_dir.length
    if length < 1e-4:
        return []
    mid = (v0 + v1) * 0.5
    up = Vector((0.0, 0.0, 1.0))
    d_norm = v_dir.normalized()
    axis = up.cross(d_norm)
    if axis.length < 1e-4:
        rot_mat = Matrix.Identity(4) if d_norm.z > 0 else Matrix.Rotation(math.pi, 4, 'X')
    else:
        angle = up.angle(d_norm)
        rot_mat = Matrix.Rotation(angle, 4, axis.normalized())
    faces = create_box(bm, (width, depth, length), (0.0, 0.0, 0.0), mat_index=mat_index)
    for f in faces:
        f.tag = True
    tr = Matrix.Translation(mid) @ rot_mat
    transform_faces(faces, tr)
    return faces

def _build_railing_segment(bm, x0, x1, y0, y1, z_base, height=1.0):
    """Builds a sturdy timber railing line with end posts and top/mid rails."""
    seg_len = math.hypot(x1 - x0, y1 - y0)
    if seg_len < 0.2:
        return
    yaw = math.atan2(y1 - y0, x1 - x0)
    mx = (x0 + x1) * 0.5
    my = (y0 + y1) * 0.5

    # Corner posts at each end
    for px, py in ((x0, y0), (x1, y1)):
        create_cylinder(bm, radius=0.08, height=height, segments=6,
                        location=(px, py, z_base + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Top rail
    create_box(bm, (seg_len, 0.12, 0.08), (mx, my, z_base + height),
               rotation=(0, 0, yaw), mat_index=MAT_INDEX_DRIFTWOOD)
    # Mid rail
    create_box(bm, (seg_len, 0.08, 0.06), (mx, my, z_base + height * 0.5),
               rotation=(0, 0, yaw), mat_index=MAT_INDEX_DRIFTWOOD)


def _build_hajfin_interior_staircase(bm, x0, y0, z0, x1, y1, z1, width=1.60, with_railing=True):
    """Builds a wide, chunky pirate timber staircase calibrated for 2-3m tall Hajfin characters.
    Runs from (x0, y0, z0) at the bottom floor to (x1, y1, z1) at the upper floor landing.
    Features heavy drift timber stringers, thick floor-plank treads, and a rough rope/timber handrail."""
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    run_len = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    cos_yaw = dx / max(0.001, run_len)
    sin_yaw = dy / max(0.001, run_len)

    # Perpendicular unit vector (across stair width)
    px = -sin_yaw
    py = cos_yaw

    num_steps = max(6, int(dz / 0.26))
    step_dz = dz / num_steps
    step_drun = run_len / num_steps

    # 1. Thick Drift Plank Treads
    for i in range(num_steps):
        s_mid_run = (i + 0.5) * step_drun
        sx = x0 + cos_yaw * s_mid_run
        sy = y0 + sin_yaw * s_mid_run
        sz = z0 + (i + 0.5) * step_dz
        create_box(bm, (step_drun * 1.08, width, 0.12), (sx, sy, sz),
                   rotation=(0, 0, yaw), mat_index=MAT_INDEX_FLOOR)

    # 2. Heavy Timber Stringer Beams (Left & Right)
    slope_len = math.hypot(run_len, dz)
    pitch = math.atan2(dz, run_len)
    for sgn_p in (-0.5, 0.5):
        str_x = (x0 + x1) * 0.5 + px * (width * sgn_p)
        str_y = (y0 + y1) * 0.5 + py * (width * sgn_p)
        str_z = (z0 + z1) * 0.5 - 0.08
        create_box(bm, (slope_len * 1.02, 0.18, 0.28), (str_x, str_y, str_z),
                   rotation=(0, -pitch, yaw), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Rough Timber & Rope Handrail on the inner room side
    if with_railing:
        rail_side = -0.5
        num_posts = max(3, int(run_len / 1.5) + 1)
        for pi in range(num_posts):
            t_post = pi / max(1, num_posts - 1)
            pos_x = x0 + dx * t_post + px * (width * rail_side)
            pos_y = y0 + dy * t_post + py * (width * rail_side)
            pos_z = z0 + dz * t_post + 0.50
            create_cylinder(bm, radius=0.07, height=1.0, segments=6,
                            location=(pos_x, pos_y, pos_z), mat_index=MAT_INDEX_DRIFTWOOD)
            # Rope tie ring
            create_torus_ring(bm, (pos_x, pos_y, pos_z + 0.42), major_radius=0.09, minor_radius=0.02,
                              mat_index=MAT_INDEX_ROPE)

        # Top handrail beam running along the slope
        top_rail_x = (x0 + x1) * 0.5 + px * (width * rail_side)
        top_rail_y = (y0 + y1) * 0.5 + py * (width * rail_side)
        top_rail_z = (z0 + z1) * 0.5 + 0.95
        create_box(bm, (slope_len * 1.02, 0.10, 0.08), (top_rail_x, top_rail_y, top_rail_z),
                   rotation=(0, -pitch, yaw), mat_index=MAT_INDEX_DRIFTWOOD)


def _build_hajfin_floor_slab_with_stairwell(bm, x0, x1, y0, y1, z_floor,
                                            stair_x0=None, stair_x1=None,
                                            stair_y0=None, stair_y1=None,
                                            slab_th=0.18, with_railing=True,
                                            open_exit_side='NORTH'):
    """Builds a complete, accessible timber floor deck spanning [x0, x1] x [y0, y1] at z_floor.
    Leaves an open stairwell cutout [stair_x0, stair_x1] x [stair_y0, stair_y1] with protective
    timber balustrades on the non-exit sides, and heavy supporting ceiling joists underneath."""
    # 1. Structural Timber Ceiling Joists running under floor
    joist_spacing = 2.2
    num_joists = max(2, int((x1 - x0) / joist_spacing) + 1)
    for ji in range(num_joists):
        jx = x0 + ji * ((x1 - x0) / max(1, num_joists - 1))
        if stair_x0 is not None and stair_x0 < jx < stair_x1:
            if stair_y0 > y0:
                jy = (y0 + stair_y0) * 0.5
                create_box(bm, (0.24, stair_y0 - y0, 0.28), (jx, jy, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_DRIFTWOOD)
            if stair_y1 < y1:
                jy = (stair_y1 + y1) * 0.5
                create_box(bm, (0.24, y1 - stair_y1, 0.28), (jx, jy, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_DRIFTWOOD)
        else:
            create_box(bm, (0.24, (y1 - y0), 0.28), (jx, (y0 + y1) * 0.5, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Floor Slabs around Stairwell
    if stair_x0 is None or stair_x1 is None or stair_y0 is None or stair_y1 is None:
        create_box(bm, (x1 - x0, y1 - y0, slab_th), ((x0 + x1) * 0.5, (y0 + y1) * 0.5, z_floor - slab_th * 0.5),
                   mat_index=MAT_INDEX_FLOOR)
        return

    sx0 = max(x0, min(x1, stair_x0))
    sx1 = max(x0, min(x1, stair_x1))
    sy0 = max(y0, min(y1, stair_y0))
    sy1 = max(y0, min(y1, stair_y1))

    # A. Slab left of stairwell (x0 to sx0)
    if sx0 - x0 > 0.05:
        w_a = sx0 - x0
        create_box(bm, (w_a, y1 - y0, slab_th), (x0 + w_a * 0.5, (y0 + y1) * 0.5, z_floor - slab_th * 0.5),
                   mat_index=MAT_INDEX_FLOOR)

    # B. Slab right of stairwell (sx1 to x1)
    if x1 - sx1 > 0.05:
        w_b = x1 - sx1
        create_box(bm, (w_b, y1 - y0, slab_th), (sx1 + w_b * 0.5, (y0 + y1) * 0.5, z_floor - slab_th * 0.5),
                   mat_index=MAT_INDEX_FLOOR)

    # C. Slab below stairwell (y0 to sy0) across [sx0, sx1]
    if sy0 - y0 > 0.05:
        d_c = sy0 - y0
        create_box(bm, (sx1 - sx0, d_c, slab_th), ((sx0 + sx1) * 0.5, y0 + d_c * 0.5, z_floor - slab_th * 0.5),
                   mat_index=MAT_INDEX_FLOOR)

    # D. Slab above stairwell (sy1 to y1) across [sx0, sx1]
    if y1 - sy1 > 0.05:
        d_d = y1 - sy1
        create_box(bm, (sx1 - sx0, d_d, slab_th), ((sx0 + sx1) * 0.5, sy1 + d_d * 0.5, z_floor - slab_th * 0.5),
                   mat_index=MAT_INDEX_FLOOR)

    # 3. Protective Railings around the stairwell opening on the upper floor
    if with_railing:
        rail_h = 1.0
        if open_exit_side != 'NORTH' and sy1 < y1 - 0.2:
            _build_railing_segment(bm, sx0, sx1, sy1, sy1, z_floor, rail_h)
        if open_exit_side != 'SOUTH' and sy0 > y0 + 0.2:
            _build_railing_segment(bm, sx0, sx1, sy0, sy0, z_floor, rail_h)
        if open_exit_side != 'WEST' and sx0 > x0 + 0.2:
            _build_railing_segment(bm, sx0, sx0, sy0, sy1, z_floor, rail_h)
        if open_exit_side != 'EAST' and sx1 < x1 - 0.2:
            _build_railing_segment(bm, sx1, sx1, sy0, sy1, z_floor, rail_h)


def _build_chunky_corner_column(bm, x, y, z0, z1, size=0.42, extend_top=0.38, with_spikes=True):
    """Oversized square timber column extending proudly above eaves with beveled cap, iron brackets, and spikes."""
    col_h = (z1 - z0) + extend_top
    cz = z0 + col_h * 0.5
    # Main column (uses heavy structural timber with vertical grain)
    create_box(bm, (size, size, col_h), (x, y, cz), mat_index=MAT_INDEX_TIMBER)

    # Beveled chisel pyramid cap on top
    cap_h = size * 0.45
    cap_z = z0 + col_h + cap_h * 0.5
    create_cone(bm, radius1=size * 0.707, radius2=0.03, height=cap_h, segments=4,
                location=(x, y, cap_z), rotation=(0, 0, math.pi * 0.25), mat_index=MAT_INDEX_TIMBER)

    # Bolted steel bracket cuffs at bottom, middle, and top
    cuff_th = 0.025
    cuff_h = 0.22
    for bz in (z0 + 0.15, z1 - 0.15):
        create_box(bm, (size + cuff_th * 2, size + cuff_th * 2, cuff_h), (x, y, bz),
                   mat_index=MAT_INDEX_IRON)

    # Protruding triangular iron spikes driven into the timber
    if with_spikes:
        num_spikes = max(2, int((z1 - z0) / 1.1))
        dz = (z1 - z0 - 0.8) / max(1, num_spikes - 1)
        for i in range(num_spikes):
            sz = z0 + 0.5 + i * dz
            angle = ((i * 1.618) % 4) * (math.pi * 0.5) + math.pi * 0.25
            sx = x + math.cos(angle) * (size * 0.5 + 0.14)
            sy = y + math.sin(angle) * (size * 0.5 + 0.14)
            create_cone(bm, radius1=0.04, radius2=0.005, height=0.26, segments=5,
                        location=(sx, sy, sz), rotation=(math.pi * 0.5, 0, angle + math.pi * 0.5),
                        mat_index=MAT_INDEX_IRON)


def _build_wall_with_door_opening(bm, x0, x1, y, z0, z1, door_cx, door_w, door_h,
                                  wall_th=0.26, rot_z=0.0, include_leaf=False):
    """Builds a solid timber wall with a GENUINE DOOR OPENING cutout,
    threshold sill, arched vertical plank infill, and a unified, continuous predatory shark jaw
    doorframe completely hugging and sealing the opening with ZERO gaps.
    Door leaf is omitted by default so openings remain clear for Unreal Engine interactive doors."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    d_half_w = door_w * 0.5

    # 1. Full-Height Side Walls outside the doorway span (Continuous vertical plank siding)
    left_w = (door_cx - d_half_w) - x0
    if left_w > 0.05:
        left_cx = x0 + left_w * 0.5
        create_box(bm, (left_w, wall_th, z1 - z0), (left_cx, y, z0 + (z1 - z0) * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    right_w = x1 - (door_cx + d_half_w)
    if right_w > 0.05:
        right_cx = (door_cx + d_half_w) + right_w * 0.5
        create_box(bm, (right_w, wall_th, z1 - z0), (right_cx, y, z0 + (z1 - z0) * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 2. Continuous Vertical Plank Infill above the pointed arch opening
    # Planks run vertically from the top of the bone arch curve up to z1 (no open corner gaps, no horizontal blocks)
    # The inner arch spring is at door_h * 0.52; planks only exist above the arch and dip slightly into the bone tube.
    z_spring = door_h * 0.52
    num_door_planks = 8
    plank_w = door_w / num_door_planks
    for ki in range(num_door_planks):
        pk_cx = (door_cx - d_half_w) + (ki + 0.5) * plank_w
        # Normalized distance from center [0, 1]
        u_pk = min(1.0, abs(pk_cx - door_cx) / max(0.001, d_half_w))
        # Pointed arch inner opening curve
        st = max(0.0, 1.0 - u_pk) ** 0.80
        z_arch = z_spring + st * (door_h - z_spring)
        pk_z_bot = z0 + z_arch - 0.08
        pk_h = z1 - pk_z_bot
        if pk_h > 0.05:
            create_box(bm, (plank_w * 1.02, wall_th, pk_h),
                       (pk_cx, y, pk_z_bot + pk_h * 0.5),
                       rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Heavy Structural Timber Threshold Sill Beam under Doorway
    sill_w = door_w + 0.60
    create_box(bm, (sill_w, wall_th + 0.16, 0.16), (door_cx, y, z0 - 0.08), mat_index=MAT_INDEX_TIMBER)

    # 4. Optional Recessed Door Leaf (ONLY if include_leaf is True, False by default for UE export)
    if include_leaf:
        recess = (wall_th * 0.25) if rot_z == 0.0 else -(wall_th * 0.25)
        create_box(bm, (door_w * 0.90, 0.08, door_h * 0.96), (door_cx, y + recess, z0 + door_h * 0.48),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)
        for hz in (z0 + door_h * 0.22, z0 + door_h * 0.72):
            create_box(bm, (door_w * 0.88, 0.02, 0.07), (door_cx, y + recess - 0.045, hz),
                       rotation=(0, 0, rot_z), mat_index=MAT_INDEX_IRON)
        create_torus_ring(bm, (door_cx + door_w * 0.28, y + recess - 0.06, z0 + door_h * 0.45),
                          rotation=(math.pi * 0.5, 0, rot_z), major_radius=0.065, minor_radius=0.013,
                          major_segments=10, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # 5. Unified 3D Shark Jaw Bone Frame with joined vertices and continuous geometry
    _build_shark_jaw_arch(bm, door_cx, y, z0, rot_z=rot_z,
                          width=door_w, height=door_h, wall_th=wall_th)


def _build_shark_jaw_arch(bm, cx, cy, cz, rot_z=0.0, width=1.85, height=3.40, wall_th=0.26):
    """Exaggerated, beefy 3D predatory shark jaw arch framing the door opening.
    Constructed as a unified, continuous lofted bone tube mesh with joined vertices,
    zero intersecting box vertices, heavy base knuckle condyles, inward sharp teeth,
    and apex dorsal fin emblem."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    d_half_w = width * 0.5
    z_spring = height * 0.55
    bone_rad = 0.28  # Sturdy, exaggerated, beefy bone cross-section

    # Y offset of the jaw frame to straddle the wall exterior
    y_off = -(wall_th * 0.5 + bone_rad * 0.45) if rot_z == 0.0 else (wall_th * 0.5 + bone_rad * 0.45)

    num_segs = 8  # 8-sided octagonal cross section for the bone tube
    uv_layer = bm.loops.layers.uv.verify()

    top_rings = {}
    for side_sgn in (-1.0, 1.0):
        # 1. Generate smooth spine path from ground to apex
        num_steps = 7
        spine_pts = []
        radii = []
        for si in range(num_steps):
            t = si / (num_steps - 1)
            if t <= 0.45:
                st = t / 0.45
                cur_z = st * z_spring
                cur_x = side_sgn * (d_half_w + bone_rad * (0.45 - 0.15 * st))
            else:
                st = (t - 0.45) / 0.55
                cur_z = z_spring + st * (height - z_spring)
                cur_x = side_sgn * ((d_half_w + bone_rad * 0.30) * (1.0 - st ** 1.3))
            spine_pts.append(Vector((cur_x, y_off, cur_z)))
            r = bone_rad * (1.30 - 0.38 * t)
            radii.append(r)

        # 2. Build cross-section vertex rings along the spine
        rings = []
        for si in range(num_steps):
            p = spine_pts[si]
            if si == 0:
                tang = (spine_pts[1] - spine_pts[0]).normalized()
            elif si == num_steps - 1:
                tang = (spine_pts[si] - spine_pts[si - 1]).normalized()
            else:
                tang = (spine_pts[si + 1] - spine_pts[si - 1]).normalized()

            norm_y = Vector((0.0, 1.0, 0.0))
            norm_x = tang.cross(norm_y).normalized()
            norm_y = norm_x.cross(tang).normalized()

            r = radii[si]
            v_ring = []
            for j in range(num_segs):
                ang = j * (2.0 * math.pi / num_segs)
                offset = norm_x * (math.cos(ang) * r) + norm_y * (math.sin(ang) * r * 1.15)
                local_pt = p + offset
                w_pt = rot_mat @ local_pt + Vector((cx, cy, cz))
                v = bm.verts.new(w_pt)
                v_ring.append(v)
            rings.append(v_ring)

        top_rings[side_sgn] = rings[-1]

        # 3. Create continuous quad faces connecting adjacent rings
        for si in range(num_steps - 1):
            r0 = rings[si]
            r1 = rings[si + 1]
            u0 = si / (num_steps - 1)
            u1 = (si + 1) / (num_steps - 1)
            for j in range(num_segs):
                j_next = (j + 1) % num_segs
                f = bm.faces.new([r0[j], r0[j_next], r1[j_next], r1[j]])
                f.material_index = MAT_INDEX_BONE
                f.tag = True
                v0 = j / num_segs
                v1 = (j + 1) / num_segs
                for loop in f.loops:
                    if loop.vert == r0[j]:
                        loop[uv_layer].uv = Vector((u0, v0))
                    elif loop.vert == r0[j_next]:
                        loop[uv_layer].uv = Vector((u0, v1))
                    elif loop.vert == r1[j_next]:
                        loop[uv_layer].uv = Vector((u1, v1))
                    else:
                        loop[uv_layer].uv = Vector((u1, v0))

        # Base cap (knuckle condyle foot resting cleanly on ground/threshold)
        f_base = bm.faces.new(list(reversed(rings[0])))
        f_base.material_index = MAT_INDEX_BONE
        f_base.tag = True

        # Inward-pointing sharp shark teeth along the inner rim
        for si in range(2, num_steps - 1):
            p = spine_pts[si]
            in_dir = Vector((-side_sgn, 0.0, 0.0))
            t_loc = rot_mat @ (p + in_dir * (radii[si] * 0.85) + Vector((0.0, -0.04, 0.0))) + Vector((cx, cy, cz))
            tooth_len = 0.22 + 0.04 * math.sin(si * 2.0)
            tooth_rot = (0.0, math.pi * 0.5 * side_sgn, rot_z)
            create_cone(bm, radius1=0.065, radius2=0.008, height=tooth_len, segments=5,
                        location=(t_loc.x, t_loc.y, t_loc.z),
                        rotation=tooth_rot, mat_index=MAT_INDEX_BONE)

    # 4. Seamless Apex Cap joining the left and right mandibles together cleanly
    r_left = top_rings[-1.0]
    r_right = top_rings[1.0]
    # Bridge the two top rings with continuous quad faces across the apex
    for j in range(num_segs):
        j_next = (j + 1) % num_segs
        # Invert ring order for right side so face normals point consistently outward
        j_opp = (num_segs - 1 - j) % num_segs
        j_opp_next = (num_segs - 1 - j_next) % num_segs
        try:
            f_bridge = bm.faces.new([r_left[j], r_left[j_next], r_right[j_opp_next], r_right[j_opp]])
            f_bridge.material_index = MAT_INDEX_BONE
            f_bridge.tag = True
        except ValueError:
            pass

    # 5. Carved Bone Dorsal Fin Emblem firmly mounted directly atop the arch apex (no air gap)
    emblem_loc = rot_mat @ Vector((0.0, y_off - 0.02, height + 0.02)) + Vector((cx, cy, cz))
    _build_bone_fin_emblem(bm, emblem_loc.x, emblem_loc.y, emblem_loc.z, rot_z, scale=0.85)


def _build_bone_fin_emblem(bm, x, y, z, rot_z=0.0, scale=0.6):
    """Carved dorsal fin plaque mounted flat against the timber wall."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Pedestal plate
    b_loc = rot_mat @ Vector((0.0, 0.0, -scale * 0.22)) + Vector((x, y, z))
    create_box(bm, (scale * 0.9, 0.06, scale * 0.14), (b_loc.x, b_loc.y, b_loc.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Curved predatory dorsal fin shape
    fin_h = scale * 0.88
    fin_w = scale * 0.65
    f_loc = rot_mat @ Vector((scale * 0.04, 0.02, fin_h * 0.35)) + Vector((x, y, z))
    create_cone(bm, radius1=fin_w * 0.45, radius2=0.02, height=fin_h, segments=5,
                location=(f_loc.x, f_loc.y, f_loc.z),
                rotation=(0, 0.32, rot_z), mat_index=MAT_INDEX_BONE)


def _build_gable_triangle_wall(bm, x0, x1, y, z_eave, z_peak, wall_th=0.26):
    """Builds a solid triangular timber gable wall with vertical wood planks
    matching the lower wall siding orientation and continuous grain."""
    mx = (x0 + x1) * 0.5
    w = x1 - x0
    h = z_peak - z_eave
    plank_w = 0.40
    num_planks = max(4, int(w / plank_w))
    dx = w / num_planks

    for i in range(num_planks):
        px = x0 + (i + 0.5) * dx
        t = abs(px - mx) / max(0.01, (w * 0.5))
        plank_h = max(0.12, h * (1.0 - t))
        create_box(bm, (dx * 1.02, wall_th, plank_h), (px, y, z_eave + plank_h * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

def _build_wall_with_window_x(bm, x0, x1, y, z0, z1, win_cx, win_cz, win_w=0.75, win_h=0.75,
                              wall_th=0.26, facing_north=False):
    """Builds a wall along the X axis (from x0 to x1 at constant y) with a window cutout and frame."""
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5

    # 1. Below Window Wall
    sill_h = (win_cz - w_half_h) - z0
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Above Window Wall
    header_h = z1 - (win_cz + w_half_h)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Left Wall Segment
    left_w = (win_cx - w_half_w) - x0
    if left_w > 0.05:
        create_box(bm, (left_w, wall_th, z1 - z0), (x0 + left_w * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Right Wall Segment
    right_w = x1 - (win_cx + w_half_w)
    if right_w > 0.05:
        create_box(bm, (right_w, wall_th, z1 - z0), (win_cx + w_half_w + right_w * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Window Frame & Iron Bars inside opening
    frame_y = y + (wall_th * 0.45 if facing_north else -wall_th * 0.45)
    rot_z = math.pi if facing_north else 0.0
    _build_bone_window(bm, win_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h)


def _build_wall_with_2_windows_x(bm, x0, x1, y, z0, z1, win1_cx, win2_cx, win_cz,
                                win_w=0.85, win_h=0.85, wall_th=0.26, facing_north=False):
    """Builds a wall along the X axis with two window openings and bone frames."""
    if win1_cx > win2_cx:
        win1_cx, win2_cx = win2_cx, win1_cx
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5
    sill_h = (win_cz - w_half_h) - z0
    header_h = z1 - (win_cz + w_half_h)

    # 1. Left of window 1
    w_left = (win1_cx - w_half_w) - x0
    if w_left > 0.05:
        create_box(bm, (w_left, wall_th, z1 - z0), (x0 + w_left * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Window 1 sill & header
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win1_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win1_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Center segment between windows
    w_mid = (win2_cx - w_half_w) - (win1_cx + w_half_w)
    if w_mid > 0.05:
        create_box(bm, (w_mid, wall_th, z1 - z0), (win1_cx + w_half_w + w_mid * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Window 2 sill & header
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win2_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win2_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Right of window 2
    w_right = x1 - (win2_cx + w_half_w)
    if w_right > 0.05:
        create_box(bm, (w_right, wall_th, z1 - z0), (win2_cx + w_half_w + w_right * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 6. Bone windows
    frame_y = y + (wall_th * 0.45 if facing_north else -wall_th * 0.45)
    rot_z = math.pi if facing_north else 0.0
    _build_bone_window(bm, win1_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h)
    _build_bone_window(bm, win2_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h)


def _build_wall_with_window_y(bm, y0, y1, x, z0, z1, win_cy, win_cz, win_w=0.75, win_h=0.75,
                              wall_th=0.26, facing_east=False):
    """Builds a wall along the Y axis (from y0 to y1 at constant x) with a window cutout and frame."""
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5

    # 1. Below Window Wall
    sill_h = (win_cz - w_half_h) - z0
    if sill_h > 0.05:
        create_box(bm, (wall_th, win_w, sill_h), (x, win_cy, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Above Window Wall
    header_h = z1 - (win_cz + w_half_h)
    if header_h > 0.05:
        create_box(bm, (wall_th, win_w, header_h), (x, win_cy, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Front Wall Segment (smaller y)
    front_w = (win_cy - w_half_w) - y0
    if front_w > 0.05:
        create_box(bm, (wall_th, front_w, z1 - z0), (x, y0 + front_w * 0.5, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Back Wall Segment (larger y)
    back_w = y1 - (win_cy + w_half_w)
    if back_w > 0.05:
        create_box(bm, (wall_th, back_w, z1 - z0), (x, win_cy + w_half_w + back_w * 0.5, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Window Frame & Iron Bars inside opening
    frame_x = x + (wall_th * 0.45 if facing_east else -wall_th * 0.45)
    rot_z = math.pi * 0.5 if facing_east else -math.pi * 0.5
    _build_bone_window(bm, frame_x, win_cy, win_cz, rot_z=rot_z, w=win_w, h=win_h)


def _build_bone_window(bm, x, y, z, rot_z=0.0, pitch=0.0, w=0.75, h=0.75):
    """Window framed with 4 carved bone segments and vertical iron security bars.
    Fully supports 3D wall pitch/lean angles for tapered and slanted walls."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'X')
    bone_r = 0.065
    hw = w * 0.5
    hh = h * 0.5

    # 4 Bone frame segments along the 4 edges
    p_bl = rot_mat @ Vector((-hw, 0.0, -hh)) + Vector((x, y, z))
    p_br = rot_mat @ Vector((hw, 0.0, -hh)) + Vector((x, y, z))
    p_tl = rot_mat @ Vector((-hw, 0.0, hh)) + Vector((x, y, z))
    p_tr = rot_mat @ Vector((hw, 0.0, hh)) + Vector((x, y, z))

    # Bottom sill bone
    _create_oriented_beam(bm, p_bl, p_br, width=bone_r * 2.0, depth=bone_r * 2.0, mat_index=MAT_INDEX_BONE)
    # Top lintel bone
    _create_oriented_beam(bm, p_tl, p_tr, width=bone_r * 2.0, depth=bone_r * 2.0, mat_index=MAT_INDEX_BONE)
    # Left jamb bone
    _create_oriented_beam(bm, p_bl, p_tl, width=bone_r * 2.0, depth=bone_r * 2.0, mat_index=MAT_INDEX_BONE)
    # Right jamb bone
    _create_oriented_beam(bm, p_br, p_tr, width=bone_r * 2.0, depth=bone_r * 2.0, mat_index=MAT_INDEX_BONE)

    # 4 Corner joint condyle spheres/cylinders
    for p_corner in (p_bl, p_br, p_tl, p_tr):
        create_cylinder(bm, radius=bone_r * 1.3, height=bone_r * 1.4, segments=6,
                        location=(p_corner.x, p_corner.y, p_corner.z), mat_index=MAT_INDEX_BONE)

    # 3 Vertical iron security bars
    num_bars = 3
    for i in range(num_bars):
        bx = -w * 0.30 + i * (w * 0.60 / max(1, num_bars - 1))
        b_bot = rot_mat @ Vector((bx, 0.04, -hh * 0.88)) + Vector((x, y, z))
        b_top = rot_mat @ Vector((bx, 0.04, hh * 0.88)) + Vector((x, y, z))
        _create_oriented_beam(bm, b_bot, b_top, width=0.035, depth=0.035, mat_index=MAT_INDEX_IRON)

    # Dark recessed backing
    back_loc = rot_mat @ Vector((0.0, 0.10, 0.0)) + Vector((x, y, z))
    rot_euler = rot_mat.to_euler()
    create_box(bm, (w * 0.88, 0.04, h * 0.88), (back_loc.x, back_loc.y, back_loc.z),
               rotation=(rot_euler.x, rot_euler.y, rot_euler.z), mat_index=MAT_INDEX_GLASS)


def _build_whale_spine_buttress(bm, x, y, z0, rot_z=0.0, num_vertebrae=6, max_h=2.8):
    """Massive segmented whale spine / vertebrae column curving up the back/corner of the building."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    seg_dz = max_h / num_vertebrae
    curr_z = z0

    for i in range(num_vertebrae):
        t = i / max(1, num_vertebrae - 1)
        r = 0.32 * (1.1 - 0.35 * t)
        th = seg_dz * 0.78
        out_dist = 0.35 + 0.45 * (1.0 - math.cos(t * math.pi * 0.5))

        v_loc = rot_mat @ Vector((0.0, out_dist, curr_z + th * 0.5)) + Vector((x, y, 0.0))
        create_cylinder(bm, radius=r, height=th, segments=8,
                        location=(v_loc.x, v_loc.y, v_loc.z),
                        rotation=(0.25 * t, 0, rot_z), mat_index=MAT_INDEX_BONE)

        # Radiating lateral wing processes
        for sgn in (-1.0, 1.0):
            w_loc = rot_mat @ Vector((sgn * (r + 0.14), out_dist, curr_z + th * 0.5)) + Vector((x, y, 0.0))
            create_box(bm, (0.24, 0.14, th * 0.55), (w_loc.x, w_loc.y, w_loc.z),
                       rotation=(0, sgn * 0.3, rot_z), mat_index=MAT_INDEX_BONE)

        curr_z += seg_dz


def _build_shark_skull_mount(bm, x, y, z, rot_z=0.0, scale=1.0):
    """Large predatory shark skull trophy mounted with open jagged maw on facade."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Cranium (upper head)
    c_loc = rot_mat @ Vector((0.0, 0.25 * scale, 0.20 * scale)) + Vector((x, y, z))
    create_cone(bm, radius1=0.45 * scale, radius2=0.18 * scale, height=0.75 * scale, segments=7,
                location=(c_loc.x, c_loc.y, c_loc.z),
                rotation=(math.pi * 0.5, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Eye socket cavities
    for sgn in (-1.0, 1.0):
        eye_loc = rot_mat @ Vector((sgn * 0.28 * scale, 0.28 * scale, 0.30 * scale)) + Vector((x, y, z))
        create_box(bm, (0.16 * scale, 0.12 * scale, 0.16 * scale),
                   (eye_loc.x, eye_loc.y, eye_loc.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_GLASS)

    # Snout
    snout_loc = rot_mat @ Vector((0.0, 0.48 * scale, 0.05 * scale)) + Vector((x, y, z))
    create_box(bm, (0.44 * scale, 0.22 * scale, 0.20 * scale),
               (snout_loc.x, snout_loc.y, snout_loc.z),
               rotation=(0.2, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Lower jaw
    jaw_loc = rot_mat @ Vector((0.0, 0.40 * scale, -0.28 * scale)) + Vector((x, y, z))
    create_box(bm, (0.42 * scale, 0.28 * scale, 0.16 * scale),
               (jaw_loc.x, jaw_loc.y, jaw_loc.z),
               rotation=(-0.4, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Teeth
    for i in range(5):
        tx = (-0.16 + i * 0.08) * scale
        t_loc = rot_mat @ Vector((tx, 0.46 * scale, -0.06 * scale)) + Vector((x, y, z))
        create_cone(bm, radius1=0.035 * scale, radius2=0.005, height=0.14 * scale, segments=4,
                    location=(t_loc.x, t_loc.y, t_loc.z),
                    rotation=(math.pi, 0, rot_z), mat_index=MAT_INDEX_BONE)


def _build_whale_rib_tunnel_entrance(bm, entrance_x, entrance_y, z0, rot_z=0.0,
                                     length=3.8, height=4.4, width=3.6, num_pairs=5):
    """Projecting whale rib cage tunnel entrance extending OUTWARD from the main door.
    Features elevated solid reef-stone foundation plinth, wide ceremonial access steps,
    raised timber boardwalk platform, continuous curved bone ribs connecting cleanly,
    rope lashings, and flanking tribal totem posts with mounted shark skull trophies."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    step_d = length / max(1, num_pairs)

    bw_len = length + 0.6
    bw_w = width + 0.6
    bw_cy = entrance_y - bw_len * 0.5

    # 1. Solid Reef Stone Foundation Plinth under the entrance boardwalk (extends down to z=0)
    if z0 > 0.05:
        create_box(bm, (bw_w + 0.30, bw_len + 0.10, z0), (entrance_x, bw_cy, z0 * 0.5),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_ROUGH_STONE)
        # Wide Ceremonial Stone Steps in front of boardwalk connecting ground to entrance deck
        num_steps = max(2, int(z0 / 0.22))
        step_run = 0.44
        st_front_y = entrance_y - bw_len
        for si in range(num_steps):
            sz = (si + 0.5) * (z0 / num_steps)
            sy = st_front_y - (num_steps - si - 0.5) * step_run
            create_box(bm, (bw_w + 0.20, step_run * 1.05, 0.18), (entrance_x, sy, sz),
                       rotation=(0, 0, rot_z), mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Raised Timber Boardwalk Platform extending outward from the threshold
    create_box(bm, (bw_w, bw_len, 0.16), (entrance_x, bw_cy, z0 + 0.08),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_FLOOR)
    # Timber curb sill beams on left & right edges
    for sgn_c in (-1.0, 1.0):
        cx_pos = entrance_x + sgn_c * (width * 0.5 + 0.14)
        create_box(bm, (0.26, bw_len, 0.22), (cx_pos, bw_cy, z0 + 0.18),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER)

    # 3. Outward Whale Rib Arches (Arched high and wide overhead, completely clear of the doorway)
    for i in range(num_pairs):
        fwd = -(i + 0.85) * step_d  # Negative Y projects OUTWARD in front of entrance!
        pair_h = height * (1.0 - 0.025 * i)
        pair_w = width * (1.0 - 0.020 * i)

        rib_pts_left = [
            rot_mat @ Vector((-pair_w * 0.50, fwd, 0.12)) + Vector((entrance_x, entrance_y, z0)),
            rot_mat @ Vector((-pair_w * 0.56, fwd, pair_h * 0.58)) + Vector((entrance_x, entrance_y, z0)),
            rot_mat @ Vector((-0.08, fwd, pair_h)) + Vector((entrance_x, entrance_y, z0)),
        ]
        rib_pts_right = [
            rot_mat @ Vector((pair_w * 0.50, fwd, 0.12)) + Vector((entrance_x, entrance_y, z0)),
            rot_mat @ Vector((pair_w * 0.56, fwd, pair_h * 0.58)) + Vector((entrance_x, entrance_y, z0)),
            rot_mat @ Vector((0.08, fwd, pair_h)) + Vector((entrance_x, entrance_y, z0)),
        ]

        for pts in (rib_pts_left, rib_pts_right):
            # Base to Mid
            _create_oriented_beam(bm, pts[0], pts[1], width=0.22, depth=0.24, mat_index=MAT_INDEX_BONE)
            # Mid to Apex
            _create_oriented_beam(bm, pts[1], pts[2], width=0.18, depth=0.20, mat_index=MAT_INDEX_BONE)
            # Bone knuckle joint
            create_cylinder(bm, radius=0.15, height=0.20, segments=7,
                            location=(pts[1].x, pts[1].y, pts[1].z), mat_index=MAT_INDEX_BONE)

        # Rope winding at top apex connecting the rib tips
        apex_mid = (rib_pts_left[2] + rib_pts_right[2]) * 0.5
        create_cylinder(bm, radius=0.16, height=0.28, segments=8,
                        location=(apex_mid.x, apex_mid.y, apex_mid.z),
                        rotation=(math.pi * 0.5, 0, rot_z), mat_index=MAT_INDEX_ROPE)

    # 4. Flanking carved wooden totem posts at the tunnel entrance
    post_y = -(length + 0.50)
    for sgn in (-1.0, 1.0):
        p_x = entrance_x + sgn * (width * 0.5 + 0.55)
        p_y = entrance_y + post_y
        _build_tribal_totem_post(bm, p_x, p_y, z0, height=3.4)
        # Shark skull faces outward (-Y) towards approaching visitors
        _build_shark_skull_mount(bm, p_x, p_y - 0.24, z0 + 2.4, rot_z=math.pi, scale=0.75)

def _build_tribal_totem_post(bm, x, y, z0, height=2.4):
    """Carved timber totem pole with rope coils and cross arms."""
    post_r = 0.16
    cz = z0 + height * 0.5
    create_cylinder(bm, radius=post_r, height=height, segments=8,
                    location=(x, y, cz), mat_index=MAT_INDEX_DRIFTWOOD)

    # Sharpened tip
    create_cone(bm, radius1=post_r, radius2=0.02, height=0.45, segments=8,
                location=(x, y, z0 + height + 0.22), mat_index=MAT_INDEX_DRIFTWOOD)

    # Rope coils
    for rz in (z0 + 0.6, z0 + 1.3, z0 + height - 0.2):
        create_cylinder(bm, radius=post_r + 0.035, height=0.16, segments=10,
                        location=(x, y, rz), mat_index=MAT_INDEX_ROPE)

    # Cross arms
    create_box(bm, (0.75, 0.12, 0.14), (x, y, z0 + height * 0.65), mat_index=MAT_INDEX_DRIFTWOOD)


# =============================================================================
# BONE SCALE ROOF GENERATORS (SOLID UNDERLAY + TIGHT TILES)
# =============================================================================

def _build_roof_slope_slab(bm, x_peak, x_eave, y0, y1, z_peak, z_eave, slab_th=0.14,
                           u_scale=1.4, v_scale=1.4):
    """Builds a solid roof slope deck with authentic UV-unwrapped bone scale shingles pointing downward."""
    uv_layer = bm.loops.layers.uv.verify()
    span_y = y1 - y0
    half_span = abs(x_peak - x_eave)
    peak_h = z_peak - z_eave
    slope_len = math.hypot(half_span, peak_h)

    dx = x_eave - x_peak
    dz = z_eave - z_peak
    s_len = math.hypot(dx, dz)
    nx = -dz / s_len
    nz = dx / s_len
    if nz < 0:
        nx, nz = -nx, -nz

    v_top_rf = bm.verts.new(Vector((x_peak, y0, z_peak)))
    v_top_rb = bm.verts.new(Vector((x_peak, y1, z_peak)))
    v_top_eb = bm.verts.new(Vector((x_eave, y1, z_eave)))
    v_top_ef = bm.verts.new(Vector((x_eave, y0, z_eave)))

    off_x = -nx * slab_th
    off_z = -nz * slab_th
    v_bot_rf = bm.verts.new(Vector((x_peak + off_x, y0, z_peak + off_z)))
    v_bot_rb = bm.verts.new(Vector((x_peak + off_x, y1, z_peak + off_z)))
    v_bot_eb = bm.verts.new(Vector((x_eave + off_x, y1, z_eave + off_z)))
    v_bot_ef = bm.verts.new(Vector((x_eave + off_x, y0, z_eave + off_z)))

    if dx > 0:
        f_top = bm.faces.new([v_top_rf, v_top_ef, v_top_eb, v_top_rb])
    else:
        f_top = bm.faces.new([v_top_rf, v_top_rb, v_top_eb, v_top_ef])
    f_top.material_index = MAT_INDEX_SHINGLES

    v_tiles = max(0.85, slope_len * v_scale)
    u_tiles = max(1.0, span_y * u_scale)

    for loop in f_top.loops:
        v_co = loop.vert.co
        u = (v_co.y - y0) * u_scale
        v = ((v_co.z - z_eave) / max(0.1, peak_h)) * v_tiles
        loop[uv_layer].uv = Vector((u, v))

    if dx > 0:
        f_bot = bm.faces.new([v_bot_rf, v_bot_rb, v_bot_eb, v_bot_ef])
        f_eave = bm.faces.new([v_top_ef, v_bot_ef, v_bot_eb, v_top_eb])
        f_ridge = bm.faces.new([v_top_rb, v_bot_rb, v_bot_rf, v_top_rf])
        f_front = bm.faces.new([v_top_rf, v_bot_rf, v_bot_ef, v_top_ef])
        f_back = bm.faces.new([v_top_eb, v_bot_eb, v_bot_rb, v_top_rb])
    else:
        f_bot = bm.faces.new([v_bot_rf, v_bot_ef, v_bot_eb, v_bot_rb])
        f_eave = bm.faces.new([v_top_eb, v_bot_eb, v_bot_ef, v_top_ef])
        f_ridge = bm.faces.new([v_top_rf, v_bot_rf, v_bot_rb, v_top_rb])
        f_front = bm.faces.new([v_top_ef, v_bot_ef, v_bot_rf, v_top_rf])
        f_back = bm.faces.new([v_top_rb, v_bot_rb, v_bot_eb, v_top_eb])

    for f in (f_bot, f_eave, f_ridge, f_front, f_back):
        f.material_index = MAT_INDEX_DRIFTWOOD


def _build_bone_scale_roof_gable(bm, x0, x1, y0, y1, eave_z, peak_h,
                                 overhang_x=0.55, overhang_y=0.55,
                                 fin_scale=1.5, num_ridge_teeth=8):
    """Builds an optimized, 100% weather-tight gable roof with textured bone scale shingles
    pointing downward toward the eaves, heavy timber verge bargeboards, ridge beam, and dorsal fin crest."""
    mx = (x0 + x1) * 0.5
    half_span = (x1 - x0) * 0.5 + overhang_x
    span_y = (y1 - y0) + overhang_y * 2
    my = (y0 + y1) * 0.5
    peak_z = eave_z + peak_h

    slope_len = math.hypot(half_span, peak_h)
    pitch_angle = math.atan2(peak_h, half_span)

    # 1. Solid Heavy Timber Ridge Beam
    ridge_len = span_y + 0.4
    create_box(bm, (0.36, ridge_len, 0.38), (mx, my, peak_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Solid Roof Deck Slopes with Downward Bone Scale Texture Mapping
    # Left slope (x < mx)
    _build_roof_slope_slab(bm, x_peak=mx, x_eave=mx - half_span,
                           y0=y0 - overhang_y, y1=y1 + overhang_y,
                           z_peak=peak_z, z_eave=eave_z, slab_th=0.14, u_scale=0.25, v_scale=0.28)
    # Right slope (x > mx)
    _build_roof_slope_slab(bm, x_peak=mx, x_eave=mx + half_span,
                           y0=y0 - overhang_y, y1=y1 + overhang_y,
                           z_peak=peak_z, z_eave=eave_z, slab_th=0.14, u_scale=0.25, v_scale=0.28)

    # 3. Heavy Timber Verge Bargeboards on Front & Rear Gable Slopes
    for gy in (y0 - overhang_y, y1 + overhang_y):
        for side in (-1.0, 1.0):
            p_peak = (mx, gy, peak_z)
            p_eave = (mx + side * half_span, gy, eave_z)
            _create_oriented_beam(bm, p_peak, p_eave, width=0.24, depth=0.24, mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Ridge Dorsal Fin Bone & Jagged Teeth Crest
    _build_ridge_crest_fin_and_spines(bm, mx, y0 - overhang_y, y1 + overhang_y,
                                      peak_z + 0.18, fin_scale=fin_scale, num_teeth=num_ridge_teeth)


def _build_shark_dorsal_fin(bm, cx, cy, cz, height=1.8, length=1.3, thickness=0.22, rot_z=0.0):
    """Volumetric sculpted bone shark dorsal fin standing upright on roof ridge/apex."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Profile points in local X-Z (Z is up, X is along fin length, Y is fin thickness)
    # Swept leading edge, arched tip, recurved trailing edge with notch
    profile = [
        Vector((-length * 0.50, 0.0, 0.0)),
        Vector((-length * 0.28, 0.0, height * 0.52)),
        Vector((length * 0.15, 0.0, height)),
        Vector((length * 0.08, 0.0, height * 0.68)),
        Vector((length * 0.22, 0.0, height * 0.40)),
        Vector((length * 0.45, 0.0, 0.0)),
    ]
    half_th = thickness * 0.5
    v_left = []
    v_right = []
    for p in profile:
        pt_l = rot_mat @ Vector((p.x, -half_th, p.z)) + Vector((cx, cy, cz))
        pt_r = rot_mat @ Vector((p.x, half_th, p.z)) + Vector((cx, cy, cz))
        v_left.append(bm.verts.new(pt_l))
        v_right.append(bm.verts.new(pt_r))

    f_l = bm.faces.new(v_left)
    f_l.material_index = MAT_INDEX_BONE
    f_r = bm.faces.new(list(reversed(v_right)))
    f_r.material_index = MAT_INDEX_BONE

    n = len(profile)
    for i in range(n):
        nxt = (i + 1) % n
        f_side = bm.faces.new([v_left[i], v_left[nxt], v_right[nxt], v_right[i]])
        f_side.material_index = MAT_INDEX_BONE


def _build_ridge_crest_fin_and_spines(bm, rx, y_start, y_end, rz, fin_scale=1.5, num_teeth=8):
    """Crown of giant curved shark dorsal fin and jagged bone spikes along the roof peak."""
    fin_y = y_start + 0.65
    fin_h = 1.45 * fin_scale
    fin_base_w = 1.15 * fin_scale

    # Primary giant volumetric dorsal fin bone near front gable (facing along ridge Y)
    _build_shark_dorsal_fin(bm, rx, fin_y, rz, height=fin_h, length=fin_base_w, thickness=0.22, rot_z=math.pi * 0.5)

    # Row of jagged bone teeth running down the ridge
    spine_span = (y_end - (fin_y + fin_base_w * 0.6))
    if spine_span > 0.8 and num_teeth > 0:
        dy = spine_span / max(1, num_teeth)
        for i in range(num_teeth):
            ty = (fin_y + fin_base_w * 0.6) + (i + 0.5) * dy
            t_ratio = 1.0 - 0.45 * (i / max(1, num_teeth - 1))
            th = (0.55 + 0.35 * math.sin(i * 1.5)) * t_ratio * fin_scale
            create_cone(bm, radius1=0.14 * t_ratio, radius2=0.015, height=th, segments=5,
                        location=(rx, ty, rz + th * 0.42),
                        rotation=(-0.25, 0, 0), mat_index=MAT_INDEX_BONE)


def _build_bone_scale_roof_conical(bm, cx, cy, eave_z, radius, height,
                                   fin_scale=1.4, num_spears=4):
    """Optimized conical roof with downward-pointing bone scale shingles, apex timber socket,
    central giant shark fin, and miniature bone spears."""
    peak_z = eave_z + height
    apex_z = peak_z + 0.08
    uv_layer = bm.loops.layers.uv.verify()

    # 1. Solid Conical Roof Slope with UV-unwrapped bone scales pointing downward
    num_segs = 16
    v_top = bm.verts.new(Vector((cx, cy, peak_z)))
    v_bot_ring = []
    for i in range(num_segs):
        ang = i * (2.0 * math.pi / num_segs)
        bx = cx + math.cos(ang) * radius
        by = cy + math.sin(ang) * radius
        v_bot_ring.append(bm.verts.new(Vector((bx, by, eave_z))))

    # Sloped triangular faces
    slope_len = math.hypot(radius, height)
    v_tiles = max(0.85, slope_len * 0.28)
    u_repeat = max(2.5, (2.0 * math.pi * radius) * 0.25)

    for i in range(num_segs):
        i_next = (i + 1) % num_segs
        f = bm.faces.new([v_top, v_bot_ring[i], v_bot_ring[i_next]])
        f.material_index = MAT_INDEX_SHINGLES

        # UVs: apex is at top of texture (v=v_tiles), eave is at bottom (v=0, scalloped tips point down!)
        u0 = (i / num_segs) * u_repeat
        u1 = ((i + 1) / num_segs) * u_repeat
        u_mid = (u0 + u1) * 0.5
        for loop in f.loops:
            if loop.vert == v_top:
                loop[uv_layer].uv = Vector((u_mid, v_tiles))
            elif loop.vert == v_bot_ring[i]:
                loop[uv_layer].uv = Vector((u0, 0.0))
            else:
                loop[uv_layer].uv = Vector((u1, 0.0))

    # Timber ceiling disk underneath
    v_center_bot = bm.verts.new(Vector((cx, cy, eave_z)))
    for i in range(num_segs):
        i_next = (i + 1) % num_segs
        f_under = bm.faces.new([v_center_bot, v_bot_ring[i_next], v_bot_ring[i]])
        f_under.material_index = MAT_INDEX_DRIFTWOOD

    # 2. Solid Apex Timber Socket
    create_cylinder(bm, radius=0.55, height=0.22, segments=10,
                    location=(cx, cy, apex_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Central giant shark fin
    fin_h = 1.55 * fin_scale
    fin_len = 1.25 * fin_scale
    _build_shark_dorsal_fin(bm, cx, cy, apex_z + 0.11, height=fin_h, length=fin_len, thickness=0.22, rot_z=0.0)

    # 4. Miniature bone spears planted around fin
    for i in range(num_spears):
        ang = i * (2.0 * math.pi / num_spears) + math.pi * 0.25
        sp_x = cx + math.cos(ang) * 0.35
        sp_y = cy + math.sin(ang) * 0.35
        sp_h = 0.75 + 0.15 * math.sin(i * 2.0)
        create_cylinder(bm, radius=0.02, height=sp_h, segments=5,
                        location=(sp_x, sp_y, apex_z + sp_h * 0.45),
                        rotation=(0.18 * math.sin(ang), 0.18 * math.cos(ang), 0),
                        mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.065, radius2=0.005, height=0.22, segments=4,
                    location=(sp_x, sp_y, apex_z + sp_h + 0.1),
                    rotation=(0, 0, 0), mat_index=MAT_INDEX_BONE)


# =============================================================================
# HAJFIN FURNITURE AND PROPS
# =============================================================================

def _build_hajfin_throne(bm, x, y, z, rot_z=0.0):
    """Megalodon jaw chieftain throne mounted on a raised bone platform."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Platform dais
    create_box(bm, (2.6, 2.2, 0.40), (x, y, z + 0.20), rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER)
    # Throne seat
    s_loc = rot_mat @ Vector((0.0, -0.15, 0.65)) + Vector((x, y, z))
    create_box(bm, (1.3, 1.1, 0.20), (s_loc.x, s_loc.y, s_loc.z), rotation=(0, 0, rot_z), mat_index=MAT_INDEX_LEATHER)

    # Megalodon jaw arch backrest
    num_pts = 7
    arch_pts = []
    for i in range(num_pts):
        t = i / (num_pts - 1)
        ang = math.pi * 0.15 + t * (math.pi * 0.70)
        lx = math.cos(ang) * 0.85
        lz = math.sin(ang) * 1.55 + 0.60
        ly = 0.35 + 0.12 * math.sin(t * math.pi)
        pt = rot_mat @ Vector((lx, ly, lz)) + Vector((x, y, z))
        arch_pts.append(pt)

    for i in range(len(arch_pts) - 1):
        _create_oriented_beam(bm, arch_pts[i], arch_pts[i + 1], width=0.20, depth=0.20, mat_index=MAT_INDEX_BONE)

    # Teeth on the inside of the jaw backrest
    for i in range(1, num_pts - 1):
        p = arch_pts[i]
        t_loc = p + rot_mat @ Vector((0.0, 0.05, -0.15))
        create_cone(bm, radius1=0.05, radius2=0.008, height=0.22, segments=5,
                    location=(t_loc.x, t_loc.y, t_loc.z), mat_index=MAT_INDEX_BONE)

    # Flanking Narwhal/Walrus tusks pointing upward
    for sgn_t in (-1.0, 1.0):
        tusk_loc = rot_mat @ Vector((sgn_t * 0.95, -0.30, 1.2)) + Vector((x, y, z))
        create_cone(bm, radius1=0.10, radius2=0.015, height=1.6, segments=6,
                    location=(tusk_loc.x, tusk_loc.y, tusk_loc.z),
                    rotation=(-0.2, sgn_t * 0.25, rot_z), mat_index=MAT_INDEX_BONE)

    # Carved bone armrests
    for sgn_a in (-1.0, 1.0):
        arm_loc = rot_mat @ Vector((sgn_a * 0.72, 0.05, 0.95)) + Vector((x, y, z))
        create_box(bm, (0.16, 1.0, 0.16), (arm_loc.x, arm_loc.y, arm_loc.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_BONE)


def _build_hajfin_brazier(bm, x, y, z):
    """Tribal iron fire brazier with glowing coals and burning embers."""
    # 3 Curved Iron Legs
    for i in range(3):
        ang = i * (2.0 * math.pi / 3.0)
        lx = math.cos(ang) * 0.55
        ly = math.sin(ang) * 0.55
        p0 = (x + lx * 1.3, y + ly * 1.3, z)
        p1 = (x + lx * 0.7, y + ly * 0.7, z + 0.9)
        _create_oriented_beam(bm, p0, p1, width=0.10, depth=0.10, mat_index=MAT_INDEX_IRON)

    # Iron Basin Bowl
    b_z = z + 0.95
    create_cylinder(bm, radius=0.75, height=0.42, segments=10,
                    location=(x, y, b_z), mat_index=MAT_INDEX_IRON)
    # Glowing Fire Embers
    create_cylinder(bm, radius=0.68, height=0.18, segments=8,
                    location=(x, y, b_z + 0.15), mat_index=MAT_INDEX_LANTERN)


def _build_hajfin_feast_table(bm, x, y, z, length=4.2, width=1.4):
    """Heavy timber feast table with flank benches."""
    th_h = 1.0
    # Table top
    create_box(bm, (width, length, 0.14), (x, y, z + th_h), mat_index=MAT_INDEX_TIMBER)

    # Trestle A-frame timber legs
    for sgn_y in (-1.0, 1.0):
        ly = y + sgn_y * (length * 0.38)
        # 2 Angled legs
        for sgn_x in (-1.0, 1.0):
            p0 = (x + sgn_x * (width * 0.42), ly, z)
            p1 = (x + sgn_x * (width * 0.15), ly, z + th_h - 0.08)
            _create_oriented_beam(bm, p0, p1, width=0.16, depth=0.18, mat_index=MAT_INDEX_TIMBER)
        # Leg cross tie
        create_box(bm, (width * 0.85, 0.14, 0.14), (x, ly, z + th_h * 0.45), mat_index=MAT_INDEX_TIMBER)

    # Center stretcher beam
    create_box(bm, (0.14, length * 0.76, 0.14), (x, y, z + th_h * 0.45), mat_index=MAT_INDEX_TIMBER)

    # Flanking Benches
    for sgn_bx in (-1.0, 1.0):
        bx = x + sgn_bx * (width * 0.5 + 0.48)
        # Bench top
        create_box(bm, (0.42, length * 0.92, 0.09), (bx, y, z + 0.55), mat_index=MAT_INDEX_TIMBER)
        for sgn_by in (-1.0, 1.0):
            bly = y + sgn_by * (length * 0.36)
            create_box(bm, (0.12, 0.34, 0.50), (bx, bly, z + 0.25), mat_index=MAT_INDEX_TIMBER)


def _build_hajfin_weapon_rack(bm, x, y, z, rot_z=0.0):
    """Timber weapon rack loaded with bone-barbed spears and harpoons."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    rack_w = 1.8
    rack_h = 1.8
    # Base feet
    for sgn_x in (-1.0, 1.0):
        f_loc = rot_mat @ Vector((sgn_x * (rack_w * 0.42), 0.0, 0.10)) + Vector((x, y, z))
        create_box(bm, (0.14, 0.70, 0.16), (f_loc.x, f_loc.y, f_loc.z), rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER)
        # Uprights
        u_loc = rot_mat @ Vector((sgn_x * (rack_w * 0.42), 0.0, rack_h * 0.5)) + Vector((x, y, z))
        create_box(bm, (0.12, 0.12, rack_h), (u_loc.x, u_loc.y, u_loc.z), rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER)

    # Cross rails
    for rz in (0.35, rack_h - 0.25):
        c_loc = rot_mat @ Vector((0.0, 0.0, rz)) + Vector((x, y, z))
        create_box(bm, (rack_w, 0.10, 0.12), (c_loc.x, c_loc.y, c_loc.z), rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER)

    # 3 Harpoons / Bone Spears
    for i in range(3):
        sx = -0.45 + i * 0.45
        shaft_loc = rot_mat @ Vector((sx, 0.08, 1.2)) + Vector((x, y, z))
        create_cylinder(bm, radius=0.035, height=2.4, segments=6,
                        location=(shaft_loc.x, shaft_loc.y, shaft_loc.z),
                        rotation=(0.10, 0, rot_z), mat_index=MAT_INDEX_TIMBER)
        # Bone spearhead
        head_loc = rot_mat @ Vector((sx, 0.08 + 0.12, 2.45)) + Vector((x, y, z))
        create_cone(bm, radius1=0.07, radius2=0.008, height=0.45, segments=5,
                    location=(head_loc.x, head_loc.y, head_loc.z),
                    rotation=(0.10, 0, rot_z), mat_index=MAT_INDEX_BONE)


def _build_hajfin_cargo_stack(bm, x, y, z):
    """Stacked trade crates, rum/oil barrels, and rope coils."""
    # Bottom crates
    create_box(bm, (0.95, 0.95, 0.75), (x - 0.45, y, z + 0.38), mat_index=MAT_INDEX_TIMBER)
    create_box(bm, (0.85, 0.85, 0.70), (x + 0.48, y - 0.20, z + 0.35), mat_index=MAT_INDEX_TIMBER)
    # Iron corner straps on crates
    create_box(bm, (0.97, 0.97, 0.10), (x - 0.45, y, z + 0.38), mat_index=MAT_INDEX_IRON)

    # Barrel standing
    b_loc = (x + 0.48, y + 0.45, z + 0.50)
    create_cylinder(bm, radius=0.38, height=1.0, segments=9,
                    location=b_loc, mat_index=MAT_INDEX_TIMBER)
    for bz in (z + 0.20, z + 0.80):
        create_torus_ring(bm, (x + 0.48, y + 0.45, bz), major_radius=0.39, minor_radius=0.025, mat_index=MAT_INDEX_IRON)

    # Barrel on side on top of crate
    create_cylinder(bm, radius=0.32, height=0.85, segments=8,
                    location=(x - 0.40, y, z + 0.75 + 0.34),
                    rotation=(0, math.pi * 0.5, 0.3), mat_index=MAT_INDEX_TIMBER)

    # Rope coil
    create_torus_ring(bm, (x + 0.48, y - 0.20, z + 0.70 + 0.08), major_radius=0.28, minor_radius=0.06, mat_index=MAT_INDEX_ROPE)


def _build_hajfin_counter_shelf(bm, x, y, z, width=3.2, height=2.2):
    """Back wall shelving rack loaded with scrimshaw, jars, and trinkets."""
    shelf_d = 0.55
    create_box(bm, (width, shelf_d, height), (x, y, z + height * 0.5), mat_index=MAT_INDEX_TIMBER)
    # Shelves
    num_shelves = 3
    for si in range(num_shelves):
        sz = z + 0.35 + si * ((height - 0.5) / (num_shelves - 1))
        create_box(bm, (width + 0.1, shelf_d + 0.1, 0.08), (x, y, sz), mat_index=MAT_INDEX_TIMBER)
        # Jars and bone trinkets on shelves
        for item_i in range(3):
            ix = x - width * 0.35 + item_i * (width * 0.35)
            create_cylinder(bm, radius=0.12, height=0.28, segments=7,
                            location=(ix, y + 0.08, sz + 0.16), mat_index=MAT_INDEX_BONE)


# =============================================================================
# DEDICATED HAJFIN PRESET ARCHETYPE ASSEMBLERS
# =============================================================================

def _build_hajfin_shanty(bm, props, width=8.5, depth=9.5, height=4.2, found_h=1.2):
    """The Quintessential Hajfin Pirate Shanty (Image 6):
    Scaled for 2-3m tall Hajfin characters with accessible hollow interior.
    Supports single-story vaulted interiors or two full stories with internal timber staircase,
    upper floor deck with stairwell cutout, real doorway cutout, full gable triangle walls,
    4 massive corner columns extending above eaves, bone fin emblem, and bone-scale gable roof with ridge fin."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height
    wall_th = 0.26
    num_fl = max(1, getattr(props, 'num_floors', 1))
    roof_h = max(3.4, width * 0.42)
    peak_z = z1 + roof_h

    # 1. Elevated Pier Stilts if foundation height > 0
    if found_h > 0.2:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h, door_cx=0.0)

    # 2. Ground Floor Slab (Accessible Walkable Interior)
    create_box(bm, (width - wall_th * 2, depth - wall_th * 2, 0.14),
               (0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    door_w = float(getattr(props, 'door_width', 1.80))
    door_h = float(getattr(props, 'door_height', 3.50))
    # Ensure door fits within ground story height
    door_h = min(door_h, (height / num_fl) * 0.85)

    if num_fl >= 2:
        story_h = height / num_fl
        z_mid = z0 + story_h

        # GROUND FLOOR WALLS
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z0, z_mid,
                                  win_cy=0.0, win_cz=z0 + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z0, z_mid,
                                  win_cy=hd * 0.35, win_cz=z0 + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)
        create_box(bm, (width - wall_th * 2, wall_th, story_h),
                   (0.0, hd - wall_th * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                      z0, z_mid, door_cx=0.0, door_w=door_w, door_h=door_h,
                                      wall_th=wall_th, rot_z=0.0,
                                      include_leaf=getattr(props, 'include_door_leaves', False))

        # INTERIOR STAIRCASE & UPPER FLOOR DECK WITH STAIRWELL CUTOUT
        stair_w = 1.60
        stair_x0 = hw - wall_th - stair_w - 0.2
        stair_x1 = hw - wall_th - 0.2
        stair_y0 = -hd + 1.8
        stair_y1 = -hd + 5.8
        _build_hajfin_floor_slab_with_stairwell(bm, -hw + wall_th, hw - wall_th, -hd + wall_th, hd - wall_th,
                                                z_mid, stair_x0, stair_x1, stair_y0, stair_y1,
                                                open_exit_side='NORTH')
        _build_hajfin_interior_staircase(bm, x0=(stair_x0 + stair_x1) * 0.5, y0=stair_y0 + 0.2, z0=z0,
                                         x1=(stair_x0 + stair_x1) * 0.5, y1=stair_y1 - 0.4, z1=z_mid,
                                         width=stair_w)

        # UPPER FLOOR WALLS
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z_mid, z1,
                                  win_cy=0.0, win_cz=z_mid + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z_mid, z1,
                                  win_cy=-hd * 0.35, win_cz=z_mid + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)
        _build_wall_with_window_x(bm, -hw + wall_th, hw - wall_th, hd - wall_th * 0.5, z_mid, z1,
                                  win_cx=0.0, win_cz=z_mid + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=True)
        _build_wall_with_window_x(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5, z_mid, z1,
                                  win_cx=0.0, win_cz=z_mid + story_h * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=False)
    else:
        # SINGLE STORY VAULTED INTERIOR
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z0, z1,
                                  win_cy=0.0, win_cz=z0 + height * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
        _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z0, z1,
                                  win_cy=0.0, win_cz=z0 + height * 0.52,
                                  win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)
        create_box(bm, (width - wall_th * 2, wall_th, height),
                   (0.0, hd - wall_th * 0.5, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                      z0, z1, door_cx=0.0, door_w=door_w, door_h=door_h,
                                      wall_th=wall_th, rot_z=0.0,
                                      include_leaf=getattr(props, 'include_door_leaves', False))

        # Exposed heavy timber collar tie beams spanning across ceiling
        for ty in (-hd * 0.5, 0.0, hd * 0.5):
            create_box(bm, (width - wall_th * 2, 0.22, 0.26), (0.0, ty, z1 - 0.15), mat_index=MAT_INDEX_TIMBER)

    # 3. Solid Gable Triangle Walls (Front & Rear) - SEALS ROOF GAPS 100%
    _build_gable_triangle_wall(bm, -hw, hw, -hd + wall_th * 0.5, z1, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, hd - wall_th * 0.5, z1, peak_z, wall_th=wall_th)

    # 4. 4 Oversized Timber Corner Columns
    col_size = 0.46
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.45)

    # 5. Dense Bone Scale Gable Roof
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=7)


def _build_hajfin_round_hut(bm, props, diameter=10.5, height=4.8, found_h=0.8):
    """The Tapered Round Bone-Scale Hut (Image 2):
    Scaled for 2-3m tall Hajfin characters with accessible hollow interior.
    8-sided tapered conical timber hut, massive perimeter posts flanking doorways, conical bone-scale roof
    with solid underlay, central shark fin crown with bone spears, shark jaw door with open walkthrough
    (no door leaf by default for UE export), accessible upper mezzanine loft with interior timber stairs,
    and massive whale vertebrae buttress curving up the rear wall!"""
    r_base = diameter * 0.5
    r_top = r_base * 0.82
    z0 = found_h
    z1 = z0 + height
    num_facets = 8
    wall_th = 0.26
    num_fl = max(1, getattr(props, 'num_floors', 1))
    include_leaves = getattr(props, 'include_door_leaves', False)

    # 1. Reef stone foundation ring
    create_cylinder(bm, radius=r_base * 1.05, height=found_h + 0.1, segments=num_facets,
                    location=(0.0, 0.0, found_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)

    # Interior wooden floor slab across entire circular ground floor
    create_cylinder(bm, radius=r_base * 0.98, height=0.14, segments=num_facets,
                    location=(0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 2. Tapered 8-sided body shell (ZERO twist, perfectly aligned planar facets)
    lean_pitch = math.atan2(r_base - r_top, height)
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), height * 0.82)
    facet_dist_bot = r_base * math.cos(math.pi / num_facets)
    facet_dist_top = r_top * math.cos(math.pi / num_facets)

    # Corner angles around the perimeter (8 corners)
    theta_corners = [(i - 0.5) * (2.0 * math.pi / num_facets) for i in range(num_facets + 1)]

    for i in range(num_facets):
        th0 = theta_corners[i]
        th1 = theta_corners[i + 1]
        mid_ang = (th0 + th1) * 0.5

        # Corner positions
        pb0 = Vector((r_base * math.cos(th0), r_base * math.sin(th0), z0))
        pb1 = Vector((r_base * math.cos(th1), r_base * math.sin(th1), z0))
        pt0 = Vector((r_top * math.cos(th0), r_top * math.sin(th0), z1))
        pt1 = Vector((r_top * math.cos(th1), r_top * math.sin(th1), z1))

        # Orthonormal orientation matrix for the facet (X horizontal, Z up-leaning, Y normal outward)
        # Guarantees ZERO roll, ZERO shear, 100% planar facet!
        x_loc = Vector((-math.sin(mid_ang), math.cos(mid_ang), 0.0))
        z_loc = Vector((-math.cos(mid_ang) * math.sin(lean_pitch), -math.sin(mid_ang) * math.sin(lean_pitch), math.cos(lean_pitch)))
        y_loc = z_loc.cross(x_loc).normalized()

        rot_mat_facet = Matrix((
            (x_loc.x, y_loc.x, z_loc.x, 0.0),
            (x_loc.y, y_loc.y, z_loc.y, 0.0),
            (x_loc.z, y_loc.z, z_loc.z, 0.0),
            (0.0, 0.0, 0.0, 1.0)
        ))
        p_rot = rot_mat_facet.to_euler()

        mid_r_bot = r_base * math.cos(math.pi / num_facets)
        mid_r_top = r_top * math.cos(math.pi / num_facets)
        f_cx = math.cos(mid_ang) * (mid_r_bot + mid_r_top) * 0.5
        f_cy = math.sin(mid_ang) * (mid_r_bot + mid_r_top) * 0.5
        f_w = (pb1 - pb0).length

        if i == 6:
            # SOUTH DOOR FACET (facing South, centered at x=0)
            door_hw = door_w * 0.5
            y_bot = -facet_dist_bot
            y_top = -facet_dist_top

            # Left jamb wall panel (x < -door_hw)
            lw_w = abs(-door_hw - pb0.x)
            create_box(bm, (lw_w, wall_th, height),
                       ((-door_hw + pb0.x) * 0.5, (y_bot + y_top) * 0.5, z0 + height * 0.5),
                       rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

            # Right jamb wall panel (x > door_hw)
            rw_w = abs(pb1.x - door_hw)
            create_box(bm, (rw_w, wall_th, height),
                       ((door_hw + pb1.x) * 0.5, (y_bot + y_top) * 0.5, z0 + height * 0.5),
                       rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

            # Continuous vertical plank infill above pointed bone jaw (no rectangular gap)
            z_spring = door_h * 0.52
            num_door_planks = 8
            plank_w = door_w / num_door_planks
            for ki in range(num_door_planks):
                pk_cx = -door_hw + (ki + 0.5) * plank_w
                u_pk = min(1.0, abs(pk_cx) / max(0.001, door_hw))
                st = max(0.0, 1.0 - u_pk) ** 0.80
                z_arch = z_spring + st * (door_h - z_spring)
                pk_z_bot = z0 + z_arch - 0.08
                pk_h = (z0 + height) - pk_z_bot
                if pk_h > 0.05:
                    p_mid_z = pk_z_bot + pk_h * 0.5
                    p_mid_y = y_bot + (y_top - y_bot) * ((p_mid_z - z0) / height)
                    create_box(bm, (plank_w * 1.02, wall_th, pk_h),
                               (pk_cx, p_mid_y, p_mid_z),
                               rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

            # Heavy timber threshold sill beam
            create_box(bm, (door_w + 0.40, wall_th + 0.14, 0.16), (0.0, y_bot, z0 - 0.05),
                       mat_index=MAT_INDEX_TIMBER)

            if include_leaves:
                create_box(bm, (door_w * 0.90, 0.08, door_h * 0.96),
                           (0.0, y_bot + wall_th * 0.35, z0 + door_h * 0.48),
                           rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

            # Continuous 3D Shark Jaw Bone Archway perfectly framing the opening
            _build_shark_jaw_arch(bm, 0.0, y_bot, z0, rot_z=0.0, width=door_w, height=door_h, wall_th=wall_th)

        elif i in (5, 7):
            # SOUTH-WEST (i=5) and SOUTH-EAST (i=7) FLANK WINDOW FACETS
            # Solid facet wall panel
            create_box(bm, (f_w * 0.98, wall_th, height), (f_cx, f_cy, z0 + height * 0.5),
                       rotation=(p_rot.x, p_rot.y, p_rot.z), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

            # Window placed flush on this facet surface with matching lean pitch
            win_z = z0 + height * 0.48
            t_win = (win_z - z0) / height
            r_at_win = mid_r_bot * (1.0 - t_win) + mid_r_top * t_win
            w_cx = math.cos(mid_ang) * (r_at_win + wall_th * 0.48)
            w_cy = math.sin(mid_ang) * (r_at_win + wall_th * 0.48)

            # Build carved bone window tilted flush with the tapered wall (-lean_pitch)
            _build_bone_window(bm, w_cx, w_cy, win_z,
                               rot_z=mid_ang + math.pi * 0.5, pitch=-lean_pitch,
                               w=0.85, h=0.85)

        else:
            # SOLID WALL FACETS (i = 0, 1, 2, 3, 4)
            create_box(bm, (f_w * 0.98, wall_th, height), (f_cx, f_cy, z0 + height * 0.5),
                       rotation=(p_rot.x, p_rot.y, p_rot.z), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Perimeter Timber Corner Posts at Vertex Junctions
    col_size = 0.44
    for i in range(num_facets):
        v_ang = theta_corners[i]
        p_b = Vector((math.cos(v_ang) * r_base, math.sin(v_ang) * r_base, z0))
        p_t = Vector((math.cos(v_ang) * r_top, math.sin(v_ang) * r_top, z1 + 0.35))

        # Heavy corner post running straight along the corner crease with longitudinal wood grain
        _create_oriented_beam(bm, p_b, p_t, width=col_size, depth=col_size, mat_index=MAT_INDEX_TIMBER)

        # Forged iron cuff brackets at base and top
        create_box(bm, (col_size + 0.06, col_size + 0.06, 0.24), (p_b.x, p_b.y, z0 + 0.22),
                   mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.06, col_size + 0.06, 0.24), (p_t.x, p_t.y, z1 - 0.15),
                   mat_index=MAT_INDEX_IRON)

    # 4. Rear Whale Spine Buttress (North, ang = +pi/2)
    _build_whale_spine_buttress(bm, 0.0, r_base * 0.95, z0, rot_z=0.0, num_vertebrae=7, max_h=height * 0.9)

    # 6. Accessible Mezzanine Loft & Interior Staircase (if num_floors >= 2 or height >= 5.5)
    if num_fl >= 2 or height >= 5.5:
        z_mez = z0 + 3.8
        mez_w = r_top * 1.85
        mez_d = r_top * 0.92
        # Mezzanine floor deck spanning rear half (y > 0)
        create_box(bm, (mez_w, mez_d, 0.16), (0.0, r_top * 0.46, z_mez - 0.08), mat_index=MAT_INDEX_FLOOR)
        # Heavy supporting cross-beam underneath mezzanine front edge
        create_box(bm, (mez_w * 1.02, 0.26, 0.30), (0.0, 0.0, z_mez - 0.23), mat_index=MAT_INDEX_DRIFTWOOD)

        # Protective timber balustrade along mezzanine front edge overlooking ground floor
        _build_railing_segment(bm, -mez_w * 0.5 + 1.8, mez_w * 0.5, 0.0, 0.0, z_mez, height=1.0)

        # Wide timber staircase along west wall up to mezzanine
        stair_x = -r_base * 0.42
        _build_hajfin_interior_staircase(bm, x0=stair_x, y0=-1.8, z0=z0,
                                         x1=stair_x, y1=1.4, z1=z_mez, width=1.60)

        # Upper bone windows on northwest and northeast upper walls
        for u_ang in (math.pi * 0.25, math.pi * 0.75):
            uwx = math.cos(u_ang) * (r_top * 0.92)
            uwy = math.sin(u_ang) * (r_top * 0.92)
            _build_bone_window(bm, uwx, uwy, z_mez + 1.2, rot_z=u_ang + math.pi * 0.5, w=0.75, h=0.75)

    # 7. Conical Bone Scale Roof with Solid Deck
    roof_h = max(3.5, diameter * 0.35)
    _build_bone_scale_roof_conical(bm, 0.0, 0.0, z1, radius=r_top * 1.25, height=roof_h,
                                   fin_scale=1.6, num_spears=4)


def _build_carved_bone_lookout_frame(bm, cx, cy, cz, width=1.80, height=1.35):
    """Carved bone window frame matching the Hajfin concept art:
    Four thick bone beams meet at the corners, with bulbous double joint knobs at each corner."""
    bone_r = 0.13
    hw = width * 0.5
    hh = height * 0.5

    # Horizontal bones (top and bottom)
    for sgn_z in (-1.0, 1.0):
        bz = cz + sgn_z * hh
        create_cylinder(bm, radius=bone_r, height=width * 0.95, segments=8,
                        location=(cx, cy, bz),
                        rotation=(0, math.pi * 0.5, 0), mat_index=MAT_INDEX_BONE)

    # Vertical bones (left and right)
    for sgn_x in (-1.0, 1.0):
        bx = cx + sgn_x * hw
        create_cylinder(bm, radius=bone_r, height=height * 0.95, segments=8,
                        location=(bx, cy, cz),
                        rotation=(0, 0, 0), mat_index=MAT_INDEX_BONE)

    # Bulbous bone joint knobs at the 4 corners (double condyle joint knobs)
    for sgn_x, sgn_z in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        kx = cx + sgn_x * hw
        kz = cz + sgn_z * hh
        create_cylinder(bm, radius=0.17, height=0.22, segments=7,
                        location=(kx + sgn_x * 0.05, cy - 0.02, kz),
                        rotation=(math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_BONE)
        create_cylinder(bm, radius=0.17, height=0.22, segments=7,
                        location=(kx, cy - 0.02, kz + sgn_z * 0.05),
                        rotation=(math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_BONE)


def _build_gable_triangle_wall_ew(bm, y0, y1, x, z_eave, z_peak, wall_th=0.26):
    """Builds a gable triangle wall on the West or East side with VERTICAL wood planks
    matching the wall siding orientation and continuous grain."""
    my = (y0 + y1) * 0.5
    h = z_peak - z_eave
    d = abs(y1 - y0)
    plank_d = 0.40
    num_planks = max(4, int(d / plank_d))
    dy = d / num_planks
    min_y = min(y0, y1)

    for i in range(num_planks):
        py = min_y + (i + 0.5) * dy
        t = abs(py - my) / max(0.01, (d * 0.5))
        plank_h = max(0.12, h * (1.0 - t))
        create_box(bm, (wall_th, dy * 1.02, plank_h), (x, py, z_eave + plank_h * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)


def _build_bone_scale_roof_gable_ew(bm, x0, x1, y0, y1, eave_z, peak_h,
                                    overhang_x=0.45, overhang_y=0.45,
                                    fin_scale=1.5, num_ridge_teeth=6):
    """Gable roof whose ridge runs along the X axis (East-West), so the front and back
    faces are sloped roof decks with scalloped bone scales, matching the watchtower concept art."""
    my = (y0 + y1) * 0.5
    half_span_y = (y1 - y0) * 0.5 + overhang_y
    span_x = (x1 - x0) + overhang_x * 2
    mx = (x0 + x1) * 0.5
    peak_z = eave_z + peak_h

    slope_len = math.hypot(half_span_y, peak_h)
    pitch_angle = math.atan2(peak_h, half_span_y)

    # 1. Heavy Timber Ridge Beam along X
    create_box(bm, (span_x + 0.4, 0.36, 0.38), (mx, my, peak_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Solid Roof Deck Slopes with Downward Bone Scale Texture Mapping
    uv_layer = bm.loops.layers.uv.verify()
    slab_th = 0.14
    
    # Front slope (y < my, eaves at my - half_span_y, z=eave_z)
    v_rf = bm.verts.new(Vector((x0 - overhang_x, my, peak_z)))
    v_rb = bm.verts.new(Vector((x1 + overhang_x, my, peak_z)))
    v_ef = bm.verts.new(Vector((x0 - overhang_x, my - half_span_y, eave_z)))
    v_eb = bm.verts.new(Vector((x1 + overhang_x, my - half_span_y, eave_z)))

    f_front = bm.faces.new([v_rf, v_rb, v_eb, v_ef])
    f_front.material_index = MAT_INDEX_SHINGLES
    
    u_repeat = max(1.0, span_x * 0.35)
    v_repeat = max(0.85, slope_len * 0.35)
    for loop in f_front.loops:
        v_co = loop.vert.co
        u = ((v_co.x - (x0 - overhang_x)) / span_x) * u_repeat
        v = ((v_co.z - eave_z) / max(0.1, peak_h)) * v_repeat
        loop[uv_layer].uv = Vector((u, v))

    # Back slope (y > my, eaves at my + half_span_y, z=eave_z)
    v_brf = bm.verts.new(Vector((x0 - overhang_x, my, peak_z)))
    v_brb = bm.verts.new(Vector((x1 + overhang_x, my, peak_z)))
    v_bef = bm.verts.new(Vector((x0 - overhang_x, my + half_span_y, eave_z)))
    v_beb = bm.verts.new(Vector((x1 + overhang_x, my + half_span_y, eave_z)))

    f_back = bm.faces.new([v_brf, v_bef, v_beb, v_brb])
    f_back.material_index = MAT_INDEX_SHINGLES
    for loop in f_back.loops:
        v_co = loop.vert.co
        u = ((v_co.x - (x0 - overhang_x)) / span_x) * u_repeat
        v = ((v_co.z - eave_z) / max(0.1, peak_h)) * v_repeat
        loop[uv_layer].uv = Vector((u, v))

    # Ceiling underlay boards
    create_box(bm, (span_x, (half_span_y - 0.15) * 2, 0.12), (mx, my, eave_z + 0.06), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Verge Bargeboards on Left (x0) and Right (x1) Gable Slopes
    for gx in (x0 - overhang_x, x1 + overhang_x):
        for side in (-1.0, 1.0):
            p_peak = (gx, my, peak_z)
            p_eave = (gx, my + side * half_span_y, eave_z)
            _create_oriented_beam(bm, p_peak, p_eave, width=0.24, depth=0.24, mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Central Giant Curved Shark Dorsal Fin on Ridge
    fin_h = 1.65 * fin_scale
    fin_len = 1.25 * fin_scale
    _build_shark_dorsal_fin(bm, mx, my, peak_z + 0.12, height=fin_h, length=fin_len, thickness=0.22, rot_z=0.0)

    # Flanking ridge teeth spikes along the ridge beam
    for sgn_rx in (-1.0, 1.0):
        for i in range(1, 4):
            tx = mx + sgn_rx * (fin_len * 0.42 + i * 0.42)
            if abs(tx - mx) < span_x * 0.48:
                th = 0.55 * (1.0 - i * 0.16) * fin_scale
                create_cone(bm, radius1=0.09, radius2=0.015, height=th, segments=5,
                            location=(tx, my, peak_z + th * 0.45),
                            rotation=(0, -sgn_rx * 0.18, 0), mat_index=MAT_INDEX_BONE)


def _build_hajfin_watchtower(bm, props, width=5.5, depth=5.5, height=10.5, found_h=0.0):
    """The Rickety Simple Hajfin Watchtower (matching concept art media_1794407220362_da16a290.jpg):
    - Tapering 4-legged heavy timber stilt tower with intermediate ring tie-beams and iron corner plates.
    - Diagonal X-bracing timbers across multiple vertical bays on all 4 sides.
    - Front-right angled timber ladder with chunky rungs climbing from ground to platform.
    - Elevated observation platform with floor deck, floor joists, and protective railing.
    - Sentry lookout booth with 4 corner posts, low half-walls, and an iconic giant carved bone window frame.
    - Scalloped bone-scale gable roof with timber bargeboards, shark dorsal fin crest, and ridge spikes.
    - Fully accessible and hollow inside for 2-3m tall Hajfin sentries."""
    # 1. Proportions & Levels
    stilt_h = max(6.2, height * 0.62)
    cabin_h = max(3.8, height - stilt_h)
    eave_z = stilt_h + cabin_h
    peak_z = eave_z + 2.5

    # Footprint: base leg spacing at ground
    bw = max(4.8, width)
    bd = max(4.8, depth)
    h_bw = bw * 0.5
    h_bd = bd * 0.5

    # Tapered platform leg spacing at stilt_h
    taper = 0.72
    tw = bw * taper
    td = bd * taper
    h_tw = tw * 0.5
    h_td = td * 0.5

    # 2. Four Main Corner Legs (Pyramidal stance)
    corner_signs = ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0))
    for sgn_x, sgn_y in corner_signs:
        p0 = (sgn_x * h_bw, sgn_y * h_bd, 0.0)
        p1 = (sgn_x * h_tw, sgn_y * h_td, stilt_h)
        _create_oriented_beam(bm, p0, p1, width=0.42, depth=0.42, mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Intermediate Ring Tie-Beams & Iron Plates (Two bays)
    num_bays = 2
    z_bays = [0.0, stilt_h * 0.48, stilt_h]

    for b_idx in range(1, len(z_bays)):
        bz = z_bays[b_idx]
        t = bz / stilt_h
        cur_w = bw * (1.0 - t) + tw * t
        cur_d = bd * (1.0 - t) + td * t
        c_hw = cur_w * 0.5
        c_hd = cur_d * 0.5

        # Horizontal ring tie-beams (Front, Back, Left, Right)
        _create_oriented_beam(bm, (-c_hw, -c_hd, bz), (c_hw, -c_hd, bz), width=0.28, depth=0.28, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (-c_hw, c_hd, bz), (c_hw, c_hd, bz), width=0.28, depth=0.28, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (-c_hw, -c_hd, bz), (-c_hw, c_hd, bz), width=0.28, depth=0.28, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (c_hw, -c_hd, bz), (c_hw, c_hd, bz), width=0.28, depth=0.28, mat_index=MAT_INDEX_DRIFTWOOD)

        # Iron corner reinforcement plates at each joint
        for sgn_x, sgn_y in corner_signs:
            create_box(bm, (0.46, 0.46, 0.34), (sgn_x * c_hw, sgn_y * c_hd, bz), mat_index=MAT_INDEX_IRON)

    # 4. Diagonal X-Bracing Timbers in each bay (Front, Back, Left, Right)
    for b_idx in range(num_bays):
        z_bot = z_bays[b_idx]
        z_top = z_bays[b_idx + 1]
        t_bot = z_bot / stilt_h
        t_top = z_top / stilt_h

        wb = bw * (1.0 - t_bot) + tw * t_bot
        db = bd * (1.0 - t_bot) + td * t_bot
        wt = bw * (1.0 - t_top) + tw * t_top
        dt = bd * (1.0 - t_top) + td * t_top

        h_wb, h_db = wb * 0.5, db * 0.5
        h_wt, h_dt = wt * 0.5, dt * 0.5

        # Front (Y = -d): X-brace
        _create_oriented_beam(bm, (-h_wb, -h_db, z_bot + 0.15), (h_wt, -h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (h_wb, -h_db, z_bot + 0.15), (-h_wt, -h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)

        # Back (Y = +d): X-brace
        _create_oriented_beam(bm, (-h_wb, h_db, z_bot + 0.15), (h_wt, h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (h_wb, h_db, z_bot + 0.15), (-h_wt, h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)

        # Left (X = -w): X-brace
        _create_oriented_beam(bm, (-h_wb, -h_db, z_bot + 0.15), (-h_wt, h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (-h_wb, h_db, z_bot + 0.15), (-h_wt, -h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)

        # Right (X = +w): X-brace
        _create_oriented_beam(bm, (h_wb, -h_db, z_bot + 0.15), (h_wt, h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)
        _create_oriented_beam(bm, (h_wb, h_db, z_bot + 0.15), (h_wt, -h_dt, z_top - 0.15), width=0.20, depth=0.18, mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Access Ladder (Centered on Front, climbing straight into the platform hatchway)
    lad_w = 0.90
    lad_x = 0.0
    lad_y0 = -h_bd * 1.15
    lad_y1 = -h_td + 0.15

    # Deck dimensions
    deck_w = tw + 0.80
    deck_d = td + 0.80
    h_dw = deck_w * 0.5
    h_dd = deck_d * 0.5

    # Two heavy timber ladder stringers extending above deck to form grab rails:
    for sgn_lad in (-1.0, 1.0):
        lx = lad_x + sgn_lad * (lad_w * 0.5)
        _create_oriented_beam(bm, (lx, lad_y0, 0.0), (lx, lad_y1, stilt_h + 1.10),
                              width=0.14, depth=0.16, mat_index=MAT_INDEX_TIMBER)

    # Ladder rungs spaced vertically
    num_rungs = max(6, int(stilt_h / 0.35))
    for i in range(1, num_rungs + 1):
        rz = i * (stilt_h / (num_rungs + 1))
        t_lad = rz / stilt_h
        ry = lad_y0 * (1.0 - t_lad) + lad_y1 * t_lad
        _create_oriented_beam(bm, (lad_x - lad_w * 0.46, ry, rz), (lad_x + lad_w * 0.46, ry, rz),
                              width=0.10, depth=0.12, mat_index=MAT_INDEX_DRIFTWOOD)

    # 6. Elevated Platform Deck with Real Hatchway Opening
    # Perimeter sill joists underneath deck
    for sgn_y in (-1.0, 1.0):
        create_box(bm, (deck_w, 0.30, 0.30), (0.0, sgn_y * (h_td + 0.15), stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)
    for sgn_x in (-1.0, 1.0):
        create_box(bm, (0.30, deck_d, 0.30), (sgn_x * (h_tw + 0.15), 0.0, stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)

    # Walkable timber floor slabs around hatchway cutout [-hatch_hw, hatch_hw] x [-h_dd, -h_td + 0.85]
    hatch_hw = lad_w * 0.60
    hatch_back_y = -h_td + 0.85

    # Left slab
    w_left = (-hatch_hw) - (-h_dw)
    create_box(bm, (w_left, deck_d, 0.16), ((-h_dw - hatch_hw) * 0.5, 0.0, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)
    # Right slab
    w_right = h_dw - hatch_hw
    create_box(bm, (w_right, deck_d, 0.16), ((hatch_hw + h_dw) * 0.5, 0.0, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)
    # Rear slab behind hatchway
    d_rear = h_dd - hatch_back_y
    create_box(bm, (hatch_hw * 2.0, d_rear, 0.16), (0.0, hatch_back_y + d_rear * 0.5, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)

    # Hatchway trim kerb timber
    create_box(bm, (hatch_hw * 2.0 + 0.16, 0.14, 0.12), (0.0, hatch_back_y + 0.07, stilt_h + 0.14), mat_index=MAT_INDEX_TIMBER)

    # 7. Sentry Lookout Cabin (4 Corner Posts)
    col_size = 0.42
    for sgn_x, sgn_y in corner_signs:
        cx = sgn_x * h_tw
        cy = sgn_y * h_td
        create_box(bm, (col_size, col_size, cabin_h + 0.20), (cx, cy, stilt_h + cabin_h * 0.5), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.26), (cx, cy, stilt_h + 0.18), mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.26), (cx, cy, eave_z - 0.18), mat_index=MAT_INDEX_IRON)

    # Perimeter Balustrades around the lookout platform
    bal_h = 1.05
    # Left (West) balustrade:
    create_box(bm, (0.16, td, bal_h), (-h_tw, 0.0, stilt_h + bal_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.24, td + 0.1, 0.12), (-h_tw, 0.0, stilt_h + bal_h), mat_index=MAT_INDEX_TIMBER)

    # Rear (North) balustrade:
    create_box(bm, (tw, 0.16, bal_h), (0.0, h_td, stilt_h + bal_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (tw + 0.1, 0.24, 0.12), (0.0, h_td, stilt_h + bal_h), mat_index=MAT_INDEX_TIMBER)

    # Right (East) balustrade:
    create_box(bm, (0.16, td, bal_h), (h_tw, 0.0, stilt_h + bal_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.24, td + 0.1, 0.12), (h_tw, 0.0, stilt_h + bal_h), mat_index=MAT_INDEX_TIMBER)

    # Front balustrades flanking the ladder hatchway:
    front_flank_w = (h_tw - col_size * 0.5) - hatch_hw
    if front_flank_w > 0.1:
        for sgn_fb in (-1.0, 1.0):
            fb_cx = sgn_fb * (hatch_hw + front_flank_w * 0.5)
            create_box(bm, (front_flank_w, 0.16, bal_h), (fb_cx, -h_td, stilt_h + bal_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
            create_box(bm, (front_flank_w, 0.24, 0.12), (fb_cx, -h_td, stilt_h + bal_h), mat_index=MAT_INDEX_TIMBER)

    # 8. Top Eave Perimeter Header Beams supporting roof
    for sgn_y in (-1.0, 1.0):
        create_box(bm, (tw + 0.30, 0.26, 0.26), (0.0, sgn_y * h_td, eave_z - 0.13), mat_index=MAT_INDEX_TIMBER)
    for sgn_x in (-1.0, 1.0):
        create_box(bm, (0.26, td + 0.30, 0.26), (sgn_x * h_tw, 0.0, eave_z - 0.13), mat_index=MAT_INDEX_TIMBER)

    # Diagonal knee braces from cabin corner posts to eave beams
    for sgn_x, sgn_y in corner_signs:
        cx = sgn_x * h_tw
        cy = sgn_y * h_td
        _create_oriented_beam(bm, (cx, cy, stilt_h + cabin_h * 0.65),
                              (cx - sgn_x * 0.85, cy, eave_z - 0.13), width=0.14, depth=0.14, mat_index=MAT_INDEX_TIMBER)
        _create_oriented_beam(bm, (cx, cy, stilt_h + cabin_h * 0.65),
                              (cx, cy - sgn_y * 0.85, eave_z - 0.13), width=0.14, depth=0.14, mat_index=MAT_INDEX_TIMBER)

    # 9. Scalloped Bone Scale Gable Roof (East-West Ridge, Front slope over bone window)
    _build_gable_triangle_wall_ew(bm, -h_td - 0.15, h_td + 0.15, -h_tw - 0.15, eave_z, peak_z, wall_th=0.22)
    _build_gable_triangle_wall_ew(bm, -h_td - 0.15, h_td + 0.15, h_tw + 0.15, eave_z, peak_z, wall_th=0.22)

    _build_bone_scale_roof_gable_ew(bm, -h_tw - 0.2, h_tw + 0.2, -h_td - 0.25, h_td + 0.25,
                                    eave_z, peak_z - eave_z,
                                    overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=6)


def _build_hajfin_crate_blockhouse(bm, props, width=9.5, depth=9.5, height=8.4, found_h=1.0):
    """The Heavy Timber Crate Blockhouse (Image 5):
    Two full accessible stories scaled for 2-3m tall Hajfin characters.
    Solid cubic timber fortress with interior timber staircase, upper floor deck with stairwell cutout,
    heavy square framing, bolted iron plates, open shark jaw doorway, and bone-framed windows."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height
    wall_th = 0.26
    story_h = height * 0.5
    z_mid = z0 + story_h

    # 1. Foundation base
    if getattr(props, 'found_type', 'STONE') == 'WOOD' or found_h >= 1.0:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)
    else:
        create_box(bm, (width + 0.3, depth + 0.3, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
                   mat_index=MAT_INDEX_ROUGH_STONE)

    # Ground floor slab
    create_box(bm, (width - wall_th * 2, depth - wall_th * 2, 0.14),
               (0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 2. Ground Floor Walls with Real Cut Openings
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), story_h * 0.85)

    # Left & Right walls with bone windows
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z0, z_mid,
                              win_cy=hd * 0.25, win_cz=z0 + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z0, z_mid,
                              win_cy=0.0, win_cz=z0 + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)

    # Rear wall
    create_box(bm, (width - wall_th * 2, wall_th, story_h),
               (0.0, hd - wall_th * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Front wall with real door cutout
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # 3. Interior Staircase & Upper Floor Deck with Stairwell Cutout
    stair_w = 1.60
    stair_x0 = -hw + wall_th + 0.2
    stair_x1 = -hw + wall_th + stair_w + 0.2
    stair_y0 = -hd + 1.8
    stair_y1 = -hd + 5.8
    _build_hajfin_floor_slab_with_stairwell(bm, -hw + wall_th, hw - wall_th, -hd + wall_th, hd - wall_th,
                                            z_mid, stair_x0, stair_x1, stair_y0, stair_y1,
                                            open_exit_side='NORTH')
    _build_hajfin_interior_staircase(bm, x0=(stair_x0 + stair_x1) * 0.5, y0=stair_y0 + 0.2, z0=z0,
                                     x1=(stair_x0 + stair_x1) * 0.5, y1=stair_y1 - 0.4, z1=z_mid,
                                     width=stair_w)

    # 4. Upper Floor Hollow Walls with Bone Windows
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z_mid, z1,
                              win_cy=hd * 0.25, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z_mid, z1,
                              win_cy=0.0, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)
    create_box(bm, (width - wall_th * 2, wall_th, story_h),
               (0.0, hd - wall_th * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Upper front wall with 2 bone windows
    _build_wall_with_2_windows_x(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                 z_mid, z1, -hw * 0.45, hw * 0.45, z_mid + story_h * 0.52,
                                 win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=False)

    # 5. Massive Square Corner Columns with L-Brackets
    col_size = 0.50
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            create_box(bm, (col_size, col_size, height + 0.35), (cx, cy, z0 + height * 0.5 + 0.175),
                       mat_index=MAT_INDEX_DRIFTWOOD)
            for bz in (z0 + 0.25, z_mid, z1):
                create_box(bm, (col_size + 0.05, col_size + 0.05, 0.32), (cx, cy, bz),
                           mat_index=MAT_INDEX_IRON)

    # 6. Dense Bone Scale Roof with solid gable triangle walls
    roof_h = max(3.4, width * 0.42)
    peak_z = z1 + roof_h
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z1, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, hd, z1, peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=6)
def _build_hajfin_bone_shop(bm, props, width=12.0, depth=11.0, height=8.8, found_h=1.0):
    """The Bone & Drift Trading Post (Image 3):
    Scaled for 2-3m tall Hajfin characters with accessible two-storey interior.
    Open barter stall counter, flip-up timber awning with diagonal struts, hanging carved bone trade sign,
    flanking pier dock platforms with stacked cargo crates and barrels,
    internal timber staircase connecting ground floor trade room to the upper lookout room,
    hollow upper room with bone windows, giant mounted Megalodon shark skull trophy,
    exterior dock access ladder with longitudinal timber grain, diagonal X-braces,
    and multi-tier bone scale roofs with ridge crests."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    g_h = 4.6
    u_h = 4.2
    z_mid = z0 + g_h
    z_top = z_mid + u_h
    wall_th = 0.26

    # 1. Foundation stilts/piers
    door_w = float(getattr(props, 'door_width', 1.80))
    door_h = min(float(getattr(props, 'door_height', 3.50)), g_h * 0.85)
    counter_w = 4.4
    counter_h = 1.2
    door_cx = (-hw + wall_th + (-counter_w * 0.5)) * 0.5

    if found_h > 0.2:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h, door_cx=door_cx)

    # 2. Ground Floor Slab (Walkable trade room interior)
    create_box(bm, (width - wall_th * 2, depth - wall_th * 2, 0.14),
               (0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 3. Ground Floor Walls
    # Rear wall
    create_box(bm, (width - wall_th * 2, wall_th, g_h), (0.0, hd - wall_th * 0.5, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    # Left wall with window
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, -hw + wall_th * 0.5, z0, z_mid,
                              win_cy=0.0, win_cz=z0 + 2.1, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=False)
    # Right wall with window
    _build_wall_with_window_y(bm, -hd + wall_th, hd - wall_th, hw - wall_th * 0.5, z0, z_mid,
                              win_cy=0.0, win_cz=z0 + 2.1, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=True)

    # FRONT FACADE (y = -hd + wall_th * 0.5)
    # 3A. Left segment with door opening
    _build_wall_with_door_opening(bm, -hw + wall_th, -counter_w * 0.5, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=door_cx, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # 3B. Center barter stall opening (open cutout with counter ledge, corbels, side posts, lintel)
    # Knee wall below counter
    create_box(bm, (counter_w, wall_th, counter_h), (0.0, -hd + wall_th * 0.5, z0 + counter_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    # Cantilevered trade counter shelf sill protruding forward
    create_box(bm, (counter_w + 0.40, 0.90, 0.16), (0.0, -hd - 0.28, z0 + counter_h - 0.08),
               mat_index=MAT_INDEX_TIMBER)
    # 3 diagonal corbel brackets supporting the counter from underneath
    for sgn_cb in (-1.2, 0.0, 1.2):
        _create_oriented_beam(bm, (sgn_cb, -hd + 0.05, z0 + 0.25),
                              (sgn_cb, -hd - 0.65, z0 + counter_h - 0.12),
                              width=0.14, depth=0.16, mat_index=MAT_INDEX_TIMBER)

    # Thick timber jamb posts flanking the barter window opening
    open_top_z = z0 + counter_h + 2.0
    for sgn_jp in (-1.0, 1.0):
        j_x = sgn_jp * (counter_w * 0.5 - 0.12)
        create_box(bm, (0.24, wall_th + 0.08, 2.0), (j_x, -hd + wall_th * 0.5, z0 + counter_h + 1.0),
                   mat_index=MAT_INDEX_TIMBER)

    # Heavy lintel header beam spanning across the barter opening
    create_box(bm, (counter_w + 0.40, wall_th + 0.10, 0.32),
               (0.0, -hd + wall_th * 0.5, open_top_z + 0.16), mat_index=MAT_INDEX_TIMBER)

    # Solid wall above header up to z_mid
    h_above = z_mid - (open_top_z + 0.32)
    if h_above > 0.05:
        create_box(bm, (counter_w, wall_th, h_above),
                   (0.0, -hd + wall_th * 0.5, open_top_z + 0.32 + h_above * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # 3C. Right wall segment with bone barred window
    r_cx = (counter_w * 0.5 + hw - wall_th) * 0.5
    _build_wall_with_window_x(bm, counter_w * 0.5, hw - wall_th, -hd + wall_th * 0.5, z0, z_mid,
                              win_cx=r_cx, win_cz=z0 + 2.1, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_north=False)

    # Massive Ground Floor Corner Columns
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z_mid, size=col_size, extend_top=0.25)

    # 4. Flip-Up Timber Awning & Hanging Trade Sign
    awning_w = counter_w + 0.80
    awning_d = 2.0
    awning_z = open_top_z + 0.45
    # Angled plank deck
    create_box(bm, (awning_w, awning_d, 0.10), (0.0, -hd - awning_d * 0.45, awning_z - 0.25),
               rotation=(0.28, 0, 0), mat_index=MAT_INDEX_TIMBER)
    # 3 Diagonal timber strut braces supporting the awning
    for sgn_st in (-1.5, 0.0, 1.5):
        _create_oriented_beam(bm, (sgn_st, -hd + 0.05, z0 + counter_h + 0.8),
                              (sgn_st, -hd - 1.55, awning_z - 0.65),
                              width=0.14, depth=0.14, mat_index=MAT_INDEX_TIMBER)

    # Hanging Carved Wooden Trade Signboard: "BONE & DRIFT TRADING"
    sign_z = awning_z - 0.70
    # Heavy timber sign backing board
    create_box(bm, (2.6, 0.08, 0.65), (0.0, -hd - 1.05, sign_z), mat_index=MAT_INDEX_TIMBER)
    # Iron reinforcement corner brackets
    for sgn_sb in (-1.25, 1.25):
        create_box(bm, (0.10, 0.10, 0.62), (sgn_sb, -hd - 1.05, sign_z), mat_index=MAT_INDEX_IRON)
    # Carved bone fish-spine symbol relief plate mounted on signboard
    create_box(bm, (1.8, 0.11, 0.35), (0.0, -hd - 1.05, sign_z), mat_index=MAT_INDEX_BONE)
    for sgn_chain in (-0.95, 0.95):
        create_cylinder(bm, radius=0.03, height=0.55, segments=5,
                        location=(sgn_chain, -hd - 1.05, sign_z + 0.50), mat_index=MAT_INDEX_IRON)
    # Giant carved bone hook dangling below the trade sign
    create_cone(bm, radius1=0.09, radius2=0.015, height=0.55, segments=6,
                location=(0.0, -hd - 1.05, sign_z - 0.48), rotation=(0.4, 0, 0), mat_index=MAT_INDEX_BONE)

    # Rich Barter Counter Trade Goods
    # Carved Megalodon scrimshaw tooth on counter
    create_cone(bm, radius1=0.12, radius2=0.02, height=0.38, segments=6,
                location=(-0.95, -hd - 0.28, z0 + counter_h + 0.18),
                rotation=(0.3, 0.2, 0.4), mat_index=MAT_INDEX_BONE)
    # Stack of bone currency discs
    create_cylinder(bm, radius=0.10, height=0.14, segments=8,
                    location=(-0.55, -hd - 0.26, z0 + counter_h + 0.07), mat_index=MAT_INDEX_BONE)
    # Trade balance scale
    create_cylinder(bm, radius=0.02, height=0.45, segments=6,
                    location=(0.45, -hd - 0.28, z0 + counter_h + 0.22), mat_index=MAT_INDEX_IRON)
    create_box(bm, (0.55, 0.03, 0.03), (0.45, -hd - 0.28, z0 + counter_h + 0.42), mat_index=MAT_INDEX_IRON)
    # Coiled hemp rope on the barter sill
    create_torus_ring(bm, (1.15, -hd - 0.28, z0 + counter_h + 0.06), major_radius=0.16, minor_radius=0.04, mat_index=MAT_INDEX_ROPE)

    # 5. Flanking Wooden Dock / Pier Platforms with Cargo Stacks
    for sgn_x in (-1.0, 1.0):
        plat_w = 2.2
        plat_d = depth * 0.85
        px = sgn_x * (hw + plat_w * 0.5)
        create_box(bm, (plat_w, plat_d, 0.16), (px, 0.0, z0 + 1.2), mat_index=MAT_INDEX_FLOOR)
        for py in (-plat_d * 0.4, 0.0, plat_d * 0.4):
            tot_h = (z0 + 1.2) + 10.0
            create_cylinder(bm, radius=0.18, height=tot_h, segments=7,
                            location=(px, py, (z0 + 1.2 - 10.0) * 0.5), mat_index=MAT_INDEX_TIMBER)
        # Cargo stacks on each dock pier platform
        _build_hajfin_cargo_stack(bm, px, -plat_d * 0.20, z0 + 1.2)

    # 6. Accessible Internal Timber Staircase & Upper Floor Deck
    u_w = width * 0.60
    u_hw = u_w * 0.5
    u_y0 = -hd
    u_y1 = hd - 2.2
    u_d = u_y1 - u_y0
    u_my = (u_y0 + u_y1) * 0.5

    stair_w = 1.60
    stair_x0 = u_hw - stair_w - 0.2
    stair_x1 = u_hw - 0.2
    stair_y0 = u_y0 + 2.0
    stair_y1 = u_y0 + 6.0
    _build_hajfin_floor_slab_with_stairwell(bm, -hw + wall_th, hw - wall_th, -hd + wall_th, hd - wall_th,
                                            z_mid, stair_x0, stair_x1, stair_y0, stair_y1,
                                            open_exit_side='NORTH')
    _build_hajfin_interior_staircase(bm, x0=(stair_x0 + stair_x1) * 0.5, y0=stair_y0 + 0.2, z0=z0,
                                     x1=(stair_x0 + stair_x1) * 0.5, y1=stair_y1 - 0.4, z1=z_mid,
                                     width=stair_w)

    # 7. Accessible Second-Level Central Lookout Room (HOLLOW & FRONT-ALIGNED!)
    # Rear wall of upper room
    create_box(bm, (u_w, wall_th, u_h), (0.0, u_y1 - wall_th * 0.5, z_mid + u_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Left & Right walls with bone windows
    _build_wall_with_window_y(bm, u_y0 + wall_th, u_y1 - wall_th, -u_hw + wall_th * 0.5, z_mid, z_top,
                              win_cy=u_my, win_cz=z_mid + u_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, u_y0 + wall_th, u_y1 - wall_th, u_hw - wall_th * 0.5, z_mid, z_top,
                              win_cy=u_my, win_cz=z_mid + u_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=True)
    # Front wall of upper room with two symmetrical bone windows
    _build_wall_with_2_windows_x(bm, -u_hw + wall_th, u_hw - wall_th, u_y0 + wall_th * 0.5, z_mid, z_top,
                                 win1_cx=-u_hw * 0.45, win2_cx=u_hw * 0.45, win_cz=z_mid + u_h * 0.52,
                                 win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=False)

    # Upper corner columns
    for cx in (-u_hw, u_hw):
        for cy in (u_y0, u_y1):
            _build_chunky_corner_column(bm, cx, cy, z_mid, z_top, size=0.40, extend_top=0.35)

    # 8. Giant Open Megalodon Shark Skull mounted proudly centered on the upper front gable peak
    _build_shark_skull_mount(bm, 0.0, u_y0 - 0.28, z_top + 1.20, rot_z=math.pi, scale=1.65)

    # 10. Interior Trade Room Furniture & Props
    _build_hajfin_counter_shelf(bm, 0.0, -hd + 3.2, z0, width=3.8, height=2.4)
    _build_hajfin_weapon_rack(bm, -hw + 1.2, 0.0, z0, rot_z=math.pi * 0.5)

    # 11. Multi-Tier Bone Scale Roofs with Full Solid Gable Triangles
    # Lower flanking roofs
    for sgn_x in (-1.0, 1.0):
        lx0 = sgn_x * hw
        lx1 = sgn_x * u_hw
        fl_x0 = min(lx0, lx1)
        fl_x1 = max(lx0, lx1)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, -hd, z_mid, z_mid + 2.2, wall_th=wall_th)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, hd, z_mid, z_mid + 2.2, wall_th=wall_th)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd, hd, z_mid, 2.2,
                                     overhang_x=0.40, overhang_y=0.40, fin_scale=1.2, num_ridge_teeth=5)

    # Upper Tower Main Roof with full gable triangles
    u_peak_z = z_top + 3.2
    _build_gable_triangle_wall(bm, -u_hw, u_hw, u_y0, z_top, u_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -u_hw, u_hw, u_y1, z_top, u_peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -u_hw, u_hw, u_y0, u_y1, z_top, 3.2,
                                 overhang_x=0.50, overhang_y=0.50, fin_scale=1.7, num_ridge_teeth=7)

def _build_hajfin_chieftain_hall(bm, props, width=15.0, depth=20.0, height=8.8, found_h=1.5):
    """The Chieftain Great Fin Hall (Image 4):
    Grand multi-tier staggered longhouse scaled for 2-3m tall Hajfin characters with accessible interior.
    Soaring vaulted central nave, projecting whale rib cage tunnel entrance, full ground floor deck,
    raised Chieftain throne dais with steps, accessible 2nd-level mezzanine galleries along side walls
    with twin internal timber stairs, continuous ridge spine of giant curved bone horns leading to
    a soaring forward-curving horn/tusk, solid gable triangle walls, and flanking tribal totem posts."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wall_th = 0.28
    nave_w = width * 0.60
    nave_h = height
    nave_peak_z = z0 + nave_h + 4.8

    # 1. Elevated Reef Stone Foundation
    create_box(bm, (width + 0.5, depth + 0.5, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
               mat_index=MAT_INDEX_ROUGH_STONE)

    # Full Interior Ground Floor Slab
    create_box(bm, (width - wall_th * 2, depth - wall_th * 2, 0.16),
               (0.0, 0.0, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)

    # 2. Central High Nave Walls
    create_box(bm, (nave_w, wall_th, nave_h), (0.0, hd - wall_th * 0.5, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, nave_h), (-nave_w * 0.5 + wall_th * 0.5, 0.0, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, nave_h), (nave_w * 0.5 - wall_th * 0.5, 0.0, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Front wall with real cut door opening inside rib tunnel
    door_w = float(getattr(props, 'door_width', 2.20))
    door_h = min(float(getattr(props, 'door_height', 3.60)), nave_h * 0.65)
    _build_wall_with_door_opening(bm, -nave_w * 0.5 + wall_th, nave_w * 0.5 - wall_th, -hd + wall_th * 0.5,
                                  z0, z0 + nave_h, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # 3. Raised Chieftain Dais / Throne Platform at Rear with Megalodon Throne
    dais_w = 5.2
    dais_d = 4.0
    dais_h = 1.2
    dais_y = hd - dais_d * 0.6
    create_box(bm, (dais_w, dais_d, dais_h), (0.0, dais_y, z0 + dais_h * 0.5), mat_index=MAT_INDEX_FLOOR)
    num_dais_steps = 4
    for dsi in range(num_dais_steps):
        ds_z = z0 + (dsi + 0.5) * (dais_h / num_dais_steps)
        ds_y = (dais_y - dais_d * 0.5) - (num_dais_steps - dsi) * 0.40
        create_box(bm, (dais_w * 0.85, 0.42, 0.12), (0.0, ds_y, ds_z), mat_index=MAT_INDEX_FLOOR)

    # Chieftain Megalodon Throne mounted on dais facing entrance
    _build_hajfin_throne(bm, 0.0, dais_y + 0.2, z0 + dais_h, rot_z=math.pi)

    # Sacred Fire Brazier burning before the dais
    _build_hajfin_brazier(bm, 0.0, dais_y - dais_d * 0.75, z0)

    # Long timber feast tables with benches along the central hall
    _build_hajfin_feast_table(bm, -nave_w * 0.26, 0.5, z0, length=5.5, width=1.3)
    _build_hajfin_feast_table(bm, nave_w * 0.26, 0.5, z0, length=5.5, width=1.3)

    # Flanking weapon racks loaded with harpoons & bone spears
    _build_hajfin_weapon_rack(bm, -nave_w * 0.40, -hd * 0.35, z0, rot_z=math.pi * 0.5)
    _build_hajfin_weapon_rack(bm, nave_w * 0.40, -hd * 0.35, z0, rot_z=-math.pi * 0.5)

    # 4. Flanking Lower Side Aisles
    side_w = (width - nave_w) * 0.5
    side_h = height * 0.62
    side_peak_z = z0 + side_h + 2.2
    for sgn_x in (-1.0, 1.0):
        sx = sgn_x * (nave_w * 0.5 + side_w * 0.5)
        create_box(bm, (side_w, depth * 0.85, side_h), (sx, 0.0, z0 + side_h * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Accessible 2nd-Level Mezzanine Galleries inside Nave
    z_gal = z0 + 4.2
    gal_w = 2.20
    gal_y0 = -hd + 3.0
    gal_y1 = hd - 2.5

    # Left Mezzanine Gallery & Staircase
    _build_hajfin_floor_slab_with_stairwell(bm, -nave_w * 0.5 + wall_th, -nave_w * 0.5 + wall_th + gal_w,
                                            gal_y0, gal_y1, z_gal)
    _build_railing_segment(bm, -nave_w * 0.5 + wall_th + gal_w, -nave_w * 0.5 + wall_th + gal_w,
                           gal_y0 + 3.5, gal_y1, z_gal, height=1.0)
    _build_hajfin_interior_staircase(bm, x0=-nave_w * 0.5 + wall_th + gal_w * 0.5, y0=gal_y0 + 0.2, z0=z0,
                                     x1=-nave_w * 0.5 + wall_th + gal_w * 0.5, y1=gal_y0 + 3.4, z1=z_gal,
                                     width=gal_w * 0.90)

    # Right Mezzanine Gallery & Staircase
    _build_hajfin_floor_slab_with_stairwell(bm, nave_w * 0.5 - wall_th - gal_w, nave_w * 0.5 - wall_th,
                                            gal_y0, gal_y1, z_gal)
    _build_railing_segment(bm, nave_w * 0.5 - wall_th - gal_w, nave_w * 0.5 - wall_th - gal_w,
                           gal_y0 + 3.5, gal_y1, z_gal, height=1.0)
    _build_hajfin_interior_staircase(bm, x0=nave_w * 0.5 - wall_th - gal_w * 0.5, y0=gal_y0 + 0.2, z0=z0,
                                     x1=nave_w * 0.5 - wall_th - gal_w * 0.5, y1=gal_y0 + 3.4, z1=z_gal,
                                     width=gal_w * 0.90)

    # 6. Chunky Corner Columns on Nave and Aisles
    for cx in (-nave_w * 0.5, nave_w * 0.5):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + nave_h, size=0.48, extend_top=0.38)
    for sgn_x in (-1.0, 1.0):
        for cy in (-hd * 0.85, hd * 0.85):
            _build_chunky_corner_column(bm, sgn_x * hw, cy, z0, z0 + side_h, size=0.40, extend_top=0.28)

    # 7. Grand Ceremonial Entrance Plinth & Stairs
    terrace_w = door_w + 2.40
    terrace_d = 2.40
    terrace_cy = -hd - terrace_d * 0.5
    # Solid reef stone terrace plinth
    if z0 > 0.05:
        create_box(bm, (terrace_w, terrace_d, z0), (0.0, terrace_cy, z0 * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)
        # Wide ceremonial stone steps leading from ground to terrace
        num_steps = max(2, int(z0 / 0.22))
        step_run = 0.44
        st_front_y = -hd - terrace_d
        for si in range(num_steps):
            sz = (si + 0.5) * (z0 / num_steps)
            sy = st_front_y - (num_steps - si - 0.5) * step_run
            create_box(bm, (terrace_w + 0.40, step_run * 1.05, 0.18), (0.0, sy, sz), mat_index=MAT_INDEX_ROUGH_STONE)

    # Walkable timber arrival deck on terrace
    create_box(bm, (terrace_w - 0.10, terrace_d - 0.10, 0.16), (0.0, terrace_cy, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)

    # Monumental Carved Whale Bone Totem Pillars flanking the arrival terrace
    for sgn_tp in (-1.0, 1.0):
        t_x = sgn_tp * (terrace_w * 0.48)
        t_y = -hd - terrace_d * 0.70
        _build_tribal_totem_post(bm, t_x, t_y, z0, height=4.2)
        _build_shark_skull_mount(bm, t_x, t_y - 0.26, z0 + 3.0, rot_z=math.pi, scale=0.90)

    # 7B. Front Facade Structural Belt Beams, War Banners & Upper Skull Trophy
    # Horizontal structural timber belt course across front wall
    create_box(bm, (nave_w + 0.2, 0.26, 0.34), (0.0, -hd - 0.08, z0 + nave_h * 0.58), mat_index=MAT_INDEX_TIMBER)
    for sgn_bx in (-nave_w * 0.42, 0.0, nave_w * 0.42):
        create_box(bm, (0.36, 0.28, 0.36), (sgn_bx, -hd - 0.08, z0 + nave_h * 0.58), mat_index=MAT_INDEX_IRON)

    # Flanking Tribal War Banners on front facade
    for sgn_ban in (-1.0, 1.0):
        ban_x = sgn_ban * (nave_w * 0.32)
        ban_z = z0 + nave_h * 0.56
        # Horizontal bone hanging peg
        _create_oriented_beam(bm, (ban_x - 0.65, -hd - 0.12, ban_z),
                              (ban_x + 0.65, -hd - 0.12, ban_z),
                              width=0.10, depth=0.10, mat_index=MAT_INDEX_BONE)
        # Hanging banner cloth
        create_box(bm, (1.1, 0.04, 2.5), (ban_x, -hd - 0.14, ban_z - 1.25), mat_index=MAT_INDEX_BANNER)

    # Upper Chieftain Lookout Window with bone frame
    win_z = z0 + nave_h * 0.78
    _create_oriented_beam(bm, (-0.85, -hd - 0.06, win_z - 0.65), (0.85, -hd - 0.06, win_z - 0.65),
                          width=0.14, depth=0.18, mat_index=MAT_INDEX_BONE)
    _create_oriented_beam(bm, (-0.85, -hd - 0.06, win_z + 0.65), (0.85, -hd - 0.06, win_z + 0.65),
                          width=0.14, depth=0.18, mat_index=MAT_INDEX_BONE)
    _create_oriented_beam(bm, (-0.85, -hd - 0.06, win_z - 0.65), (-0.85, -hd - 0.06, win_z + 0.65),
                          width=0.14, depth=0.18, mat_index=MAT_INDEX_BONE)
    _create_oriented_beam(bm, (0.85, -hd - 0.06, win_z - 0.65), (0.85, -hd - 0.06, win_z + 0.65),
                          width=0.14, depth=0.18, mat_index=MAT_INDEX_BONE)
    # Iron bars in window
    for ibx in (-0.40, 0.0, 0.40):
        create_cylinder(bm, radius=0.025, height=1.2, segments=5,
                        location=(ibx, -hd - 0.06, win_z), mat_index=MAT_INDEX_IRON)

    # Giant Megalodon Shark Skull Trophy mounted on front gable peak
    _build_shark_skull_mount(bm, 0.0, -hd - 0.28, z0 + nave_h + 1.8, rot_z=math.pi, scale=2.0)

    # 8. Solid Gable Triangle Walls (Zero gaps!)
    _build_gable_triangle_wall(bm, -nave_w * 0.5, nave_w * 0.5, -hd, z0 + nave_h, nave_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -nave_w * 0.5, nave_w * 0.5, hd, z0 + nave_h, nave_peak_z, wall_th=wall_th)

    for sgn_x in (-1.0, 1.0):
        ax0 = sgn_x * (nave_w * 0.5)
        ax1 = sgn_x * hw
        fl_x0 = min(ax0, ax1)
        fl_x1 = max(ax0, ax1)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, -hd * 0.85, z0 + side_h, side_peak_z, wall_th=wall_th)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, hd * 0.85, z0 + side_h, side_peak_z, wall_th=wall_th)

    # 9. Multi-Tier Dense Bone Scale Roofs
    for sgn_x in (-1.0, 1.0):
        ax0 = sgn_x * (nave_w * 0.5)
        ax1 = sgn_x * hw
        fl_x0 = min(ax0, ax1)
        fl_x1 = max(ax0, ax1)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd * 0.85, hd * 0.85, z0 + side_h, 2.2,
                                     overhang_x=0.40, overhang_y=0.40, fin_scale=1.2, num_ridge_teeth=5)

    # High Nave Central Roof with giant horn & continuous ridge spine
    _build_bone_scale_roof_gable(bm, -nave_w * 0.5, nave_w * 0.5, -hd, hd, z0 + nave_h, 4.8,
                                 overhang_x=0.60, overhang_y=0.60, fin_scale=2.4, num_ridge_teeth=12)


def _build_hajfin_pirate_tavern(bm, props, width=14.0, depth=14.0, height=8.4, found_h=1.2):
    """The Barnacle Bilge Pirate Tavern:
    Two full accessible stories scaled for 2-3m tall Hajfin characters.
    Multi-deck L-shaped pirate tavern with open-air stilt drinking veranda, clustered grog barrels,
    accessible ground floor taproom, internal timber staircase leading to upper pirate quarters,
    second-level balcony overlooking the drinking deck, solid roof decks with bone scale shingles,
    shark jaw doorway, and dorsal fin ridge ornaments."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    story_h = height * 0.5
    z_mid = z0 + story_h
    z1 = z0 + height
    wing_w = width * 0.52
    wing_d = depth * 0.48
    wall_th = 0.26

    # 1. Stilt Pier Foundation
    _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Full Interior Ground Floor Slab across main taproom and wing
    m_w = width
    m_d = depth - wing_d
    my = -hd + m_d * 0.5
    create_box(bm, (m_w - wall_th * 2, m_d - wall_th * 2, 0.14),
               (0.0, my, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)
    create_box(bm, (wing_w - wall_th * 2, wing_d - wall_th * 2, 0.14),
               (hw - wing_w * 0.5, hd - wing_d * 0.5, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 3. Ground Floor Walls (Hollow taproom rooms)
    # Arched door opening leading from taproom out onto the stilt drinking deck
    tap_x0 = -hw + wall_th
    tap_x1 = hw - wing_w - wall_th
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), story_h * 0.85)
    _build_wall_with_door_opening(bm, tap_x0, tap_x1, -hd + m_d - wall_th * 0.5,
                                  z0, z_mid, door_cx=(tap_x0 + tap_x1) * 0.5, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=math.pi,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (-hw + wall_th * 0.5, my, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (hw - wall_th * 0.5, my, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Wing block walls (Hollow!) with window overlooking drinking deck
    create_box(bm, (wing_w - wall_th * 2, wall_th, story_h),
               (hw - wing_w * 0.5, hd - wall_th * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, wing_d - wall_th * 2, story_h),
               (hw - wall_th * 0.5, hd - wing_d * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    _build_wall_with_window_y(bm, hd - wing_d + wall_th, hd - wall_th, hw - wing_w + wall_th * 0.5,
                              z0, z_mid, win_cy=hd - wing_d * 0.5, win_cz=z0 + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)

    # 4. Open-Air Stilt Drinking Deck in L-cutout with perimeter balustrade
    deck_w = width - wing_w
    deck_d = wing_d
    deck_x0 = -hw
    deck_x1 = hw - wing_w
    deck_y0 = hd - wing_d
    deck_y1 = hd
    deck_cx = (deck_x0 + deck_x1) * 0.5
    deck_cy = (deck_y0 + deck_y1) * 0.5
    create_box(bm, (deck_w, deck_d, 0.16), (deck_cx, deck_cy, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)
    _build_timber_deck_railing(bm, deck_x0, deck_x1, deck_y0, deck_y1, z0 + 0.08)

    # Clustered grog barrels on drinking deck
    deck_x = deck_cx
    deck_y = deck_cy
    for bx, by in ((deck_x - 0.8, deck_y - 0.6), (deck_x + 0.7, deck_y - 0.5), (deck_x, deck_y + 0.8)):
        create_cylinder(bm, radius=0.38, height=0.90, segments=8,
                        location=(bx, by, z0 + 0.55), mat_index=MAT_INDEX_DRIFTWOOD)
        create_torus_ring(bm, (bx, by, z0 + 0.40), major_radius=0.40, minor_radius=0.025, mat_index=MAT_INDEX_IRON)
        create_torus_ring(bm, (bx, by, z0 + 0.78), major_radius=0.40, minor_radius=0.025, mat_index=MAT_INDEX_IRON)

    # 5. Internal Timber Staircase & Upper Floor Deck
    stair_w = 1.60
    stair_x0 = -hw + wall_th + 0.2
    stair_x1 = -hw + wall_th + stair_w + 0.2
    stair_y0 = -hd + 1.8
    stair_y1 = -hd + 5.8
    _build_hajfin_floor_slab_with_stairwell(bm, -hw + wall_th, hw - wall_th, -hd + wall_th, -hd + m_d - wall_th,
                                            z_mid, stair_x0, stair_x1, stair_y0, stair_y1,
                                            open_exit_side='NORTH')
    create_box(bm, (wing_w - wall_th * 2, wing_d - wall_th * 2, 0.16),
               (hw - wing_w * 0.5, hd - wing_d * 0.5, z_mid - 0.08), mat_index=MAT_INDEX_FLOOR)

    _build_hajfin_interior_staircase(bm, x0=(stair_x0 + stair_x1) * 0.5, y0=stair_y0 + 0.2, z0=z0,
                                     x1=(stair_x0 + stair_x1) * 0.5, y1=stair_y1 - 0.4, z1=z_mid,
                                     width=stair_w)

    # 6. Upper Floor Hollow Rooms (Crew Quarters & Lookout)
    # Upper front wall with window
    _build_wall_with_window_x(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                              z_mid, z1, win_cx=-hw * 0.4, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=False)

    # Upper rear wall overlooking drinking deck with bone window
    _build_wall_with_window_x(bm, -hw + wall_th, hw - wing_w - wall_th, -hd + m_d - wall_th * 0.5,
                              z_mid, z1, win_cx=-hw + deck_w * 0.5, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_north=True)

    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (-hw + wall_th * 0.5, my, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (hw - wall_th * 0.5, my, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    create_box(bm, (wing_w - wall_th * 2, wall_th, story_h),
               (hw - wing_w * 0.5, hd - wall_th * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, wing_d - wall_th * 2, story_h),
               (hw - wall_th * 0.5, hd - wing_d * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, wing_d - wall_th * 2, story_h),
               (hw - wing_w + wall_th * 0.5, hd - wing_d * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 7. Front Entrance Shark Jaw Doorway
    door_w = float(getattr(props, 'door_width', 1.90))
    door_h = min(float(getattr(props, 'door_height', 3.60)), story_h * 0.85)
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=-hw * 0.4, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # 8. Corner Columns
    col_size = 0.46
    for cx in (-hw, hw):
        for cy in (-hd, my + m_d * 0.5):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.35)

    # 9. Bone-Framed Windows (Ground & Upper stories)
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * hw, my, z0 + story_h * 0.50,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.85, h=0.85)
        _build_bone_window(bm, sgn_x * hw, my, z_mid + story_h * 0.50,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.85, h=0.85)

    # 10. Solid Gable Triangle Walls & Bone Scale Roofs
    m_peak_z = z1 + 3.8
    w_peak_z = z1 + 3.0
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z1, m_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, -hd + m_d, z1, m_peak_z, wall_th=wall_th)

    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, -hd + m_d, z1, 3.8,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.7, num_ridge_teeth=8)
    _build_bone_scale_roof_gable(bm, hw - wing_w, hw, hd - wing_d, hd, z1, 3.0,
                                 overhang_x=0.45, overhang_y=0.45, fin_scale=1.3, num_ridge_teeth=6)


def _build_hajfin_bone_gate(bm, props, width=12.0, depth=4.0, height=4.5, found_h=0.0):
    """The Shark-Bone Palisade Gate (matching concept art media_1794401069315_68b6ac99.jpg):
    - Fortified sharpened timber palisade fence with conical carved wood tips.
    - Curved whale rib pickets alternating between timber posts.
    - Dual horizontal cross-rails wrapped with nautical rope bindings.
    - Hanging festoons of carved shark teeth garlands.
    - Central towering gate posts flanked with rope lashings and crowned with a giant predatory shark skull totem.
    - Carved stone/bone shark fin wedge lashed to flanking post.
    - Symmetrical gate wings with central open gateway for 2-3m tall Hajfin warriors."""
    hw = width * 0.5
    gate_w = max(2.8, float(getattr(props, 'door_width', 3.20)))
    h_gw = gate_w * 0.5
    post_r = 0.16
    log_h = height

    wing_w = (width - gate_w) * 0.5

    # Horizontal tie rails (lower at z=0.95, upper at z=2.25)
    for rail_z in (0.95, 2.25):
        create_box(bm, (wing_w + 0.3, 0.22, 0.20), (-hw + wing_w * 0.5, 0.0, rail_z), mat_index=MAT_INDEX_DRIFTWOOD)
        create_box(bm, (wing_w + 0.3, 0.22, 0.20), (hw - wing_w * 0.5, 0.0, rail_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Vertical sharpened posts & whale ribs across each wing
    num_posts_per_wing = max(3, int(wing_w / 1.15))
    dx = wing_w / num_posts_per_wing

    for side_sgn, (start_x, end_x) in ((-1, (-hw, -h_gw)), (1, (h_gw, hw))):
        for i in range(num_posts_per_wing + 1):
            px = start_x + i * dx
            if abs(px) > hw + 0.01:
                continue
            cur_post_h = log_h * (0.85 + 0.22 * math.sin(i * 1.8 + side_sgn))
            # Sharpened timber post
            create_cylinder(bm, radius=post_r, height=cur_post_h, segments=7,
                            location=(px, 0.0, cur_post_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
            create_cone(bm, radius1=post_r, radius2=0.02, height=0.65, segments=7,
                        location=(px, 0.0, cur_post_h + 0.30), mat_index=MAT_INDEX_DRIFTWOOD)
            # Rope bindings around horizontal rails
            for rz in (0.95, 2.25):
                create_torus_ring(bm, (px, 0.0, rz), major_radius=post_r + 0.03, minor_radius=0.022,
                                  mat_index=MAT_INDEX_ROPE)

            # Curved whale rib pickets between timber posts
            if i < num_posts_per_wing:
                rib_x = px + dx * 0.5
                rib_h = 2.10
                create_cylinder(bm, radius=0.075, height=rib_h, segments=6,
                                location=(rib_x, 0.10, 1.35),
                                rotation=(0.14, 0.0, 0.0), mat_index=MAT_INDEX_BONE)
                # Hanging shark teeth necklace strung under upper rail
                for ti in range(3):
                    tx = rib_x - 0.12 + ti * 0.12
                    create_cone(bm, radius1=0.045, radius2=0.005, height=0.18, segments=4,
                                location=(tx, 0.06, 2.15),
                                rotation=(math.pi, 0, 0), mat_index=MAT_INDEX_BONE)

    # 2. Main Gate Portal (Towering Posts & Shark Skull Totem)
    gate_post_h = log_h * 1.35
    for sgn_gx in (-1.0, 1.0):
        gpx = sgn_gx * h_gw
        create_cylinder(bm, radius=post_r * 1.35, height=gate_post_h, segments=8,
                        location=(gpx, 0.0, gate_post_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=post_r * 1.35, radius2=0.03, height=0.85, segments=8,
                    location=(gpx, 0.0, gate_post_h + 0.40), mat_index=MAT_INDEX_DRIFTWOOD)
        for rz in (1.0, 2.3, gate_post_h * 0.75):
            create_torus_ring(bm, (gpx, 0.0, rz), major_radius=post_r * 1.35 + 0.04, minor_radius=0.03,
                              mat_index=MAT_INDEX_ROPE)

    # Lintel cross-beam above gateway
    lintel_z = log_h * 1.05
    create_box(bm, (gate_w + 0.8, 0.32, 0.32), (0.0, 0.0, lintel_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Central Tall Totem Pole above lintel crowned with Giant Predatory Shark Skull
    skull_pole_h = 2.4
    create_cylinder(bm, radius=0.20, height=skull_pole_h, segments=7,
                    location=(0.0, 0.0, lintel_z + skull_pole_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_cone(bm, radius1=0.20, radius2=0.03, height=0.65, segments=7,
                location=(0.0, 0.0, lintel_z + skull_pole_h + 0.30), mat_index=MAT_INDEX_DRIFTWOOD)

    # Mount Giant Open-Maw Shark Skull Totem at apex of center pole
    _build_shark_skull_mount(bm, 0.0, -0.22, lintel_z + skull_pole_h * 0.72, rot_z=0.0, scale=1.45)
    create_torus_ring(bm, (0.0, 0.0, lintel_z + skull_pole_h * 0.72), major_radius=0.35, minor_radius=0.04,
                      mat_index=MAT_INDEX_ROPE)

    # Hanging bone amulet dangling beneath skull
    create_cone(bm, radius1=0.08, radius2=0.01, height=0.32, segments=5,
                location=(0.0, -0.28, lintel_z + skull_pole_h * 0.40),
                rotation=(math.pi, 0, 0), mat_index=MAT_INDEX_BONE)

    # Side post shark fin wedge (Matching Image 1 right post)
    fin_px = h_gw + dx * 1.2
    _build_shark_dorsal_fin(bm, fin_px, 0.12, 1.40, height=1.35, length=0.95, thickness=0.18, rot_z=-0.35)
    create_torus_ring(bm, (fin_px, 0.0, 1.40), major_radius=post_r + 0.05, minor_radius=0.025,
                      mat_index=MAT_INDEX_ROPE)


def _build_hajfin_forge(bm, props, width=10.0, depth=9.0, height=7.2, found_h=0.8):
    """The Harpoon Smithy & Bone Forge:
    - Rough stone masonry forge foundation and open-air timber workshop.
    - Heavy post-and-beam driftwood frame with massive square corner posts.
    - Stone smelting hearth furnace with towering coral-stone chimney.
    - Heavy iron scrap blacksmith anvil resting on a driftwood tree stump block.
    - Water quenching tub, tool workbench, and weapon racks with shark-tooth spears.
    - Scalloped bone scale gable roof with heavy bargeboards and shark dorsal fin crest."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wall_th = 0.28
    roof_h = max(3.2, width * 0.40)
    peak_z = z0 + height + roof_h

    # 1. Rough Stone Footing & Working Floor Slab
    create_box(bm, (width + 0.4, depth + 0.4, found_h + 0.1), (0.0, 0.0, found_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)
    create_box(bm, (width - 0.2, depth - 0.2, 0.14), (0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 2. Heavy Timber Posts (Open-Sided Workshop)
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + height, size=col_size, extend_top=0.3)

    # Back wall & Left wall (Semi-enclosed to shield forge wind)
    create_box(bm, (width - col_size, wall_th, height), (0.0, hd - wall_th * 0.5, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - col_size, height), (-hw + wall_th * 0.5, 0.0, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Front eave beam & Right eave beam
    create_box(bm, (width, 0.32, 0.32), (0.0, -hd, z0 + height - 0.16), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.32, depth, 0.32), (hw, 0.0, z0 + height - 0.16), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Stone Smelting Furnace & Chimney Flue
    f_w = 2.4
    f_d = 2.2
    f_h = 2.2
    furnace_x = -hw + f_w * 0.5 + 0.8
    furnace_y = hd - f_d * 0.5 - 0.8
    create_box(bm, (f_w, f_d, f_h), (furnace_x, furnace_y, z0 + f_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)
    create_box(bm, (f_w * 0.65, f_d * 0.5, f_h * 0.45), (furnace_x, furnace_y - f_d * 0.3, z0 + f_h * 0.35), mat_index=MAT_INDEX_IRON)
    chim_h = height + roof_h + 1.2
    create_box(bm, (1.1, 1.1, chim_h), (furnace_x, furnace_y, z0 + chim_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)

    # 4. Iron Scrap Blacksmith Anvil on Tree Stump
    stump_x = 0.5
    stump_y = -0.3
    create_cylinder(bm, radius=0.45, height=0.75, segments=8,
                    location=(stump_x, stump_y, z0 + 0.375), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.42, 0.95, 0.42), (stump_x, stump_y, z0 + 0.75 + 0.21), mat_index=MAT_INDEX_IRON)
    create_cone(bm, radius1=0.18, radius2=0.03, height=0.55, segments=6,
                location=(stump_x, stump_y + 0.65, z0 + 0.75 + 0.25),
                rotation=(math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_IRON)

    # 5. Quenching Water Trough
    trough_x = 1.8
    trough_y = 1.6
    create_box(bm, (1.8, 0.9, 0.75), (trough_x, trough_y, z0 + 0.375), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (1.6, 0.7, 0.65), (trough_x, trough_y, z0 + 0.45), mat_index=MAT_INDEX_GLASS)

    # 6. Harpoon & Weapon Display Rack
    rack_x = hw - 0.4
    rack_y = -0.5
    create_box(bm, (0.22, 2.6, 1.8), (rack_x, rack_y, z0 + 0.9), mat_index=MAT_INDEX_DRIFTWOOD)
    for sp_i in range(4):
        spy = rack_y - 0.9 + sp_i * 0.6
        create_cylinder(bm, radius=0.03, height=2.4, segments=6,
                        location=(rack_x - 0.12, spy, z0 + 1.2), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.09, radius2=0.01, height=0.45, segments=4,
                    location=(rack_x - 0.12, spy, z0 + 2.4 + 0.2), mat_index=MAT_INDEX_BONE)

    # 7. Bone Scale Gable Roof with Dorsal Fin
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z0 + height, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, hd, z0 + height, peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z0 + height, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=6)


def _build_hajfin_fish_depot(bm, props, width=12.0, depth=14.0, height=7.8, found_h=1.6):
    """The Fisher's Stilt Pier & Depot:
    - High crooked stilt pilings extending over tidal waterline.
    - Two-story central fish salting shack with shark jaw doorway.
    - Extended frontal fishing pier and side drying dock with barrels.
    - Hanging rope net drying racks with fish silhouettes.
    - Cantilevered heavy timber cargo boom crane with hoisted iron hook.
    - Scalloped bone-scale gable roof with ridge crest fin."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wall_th = 0.26
    cabin_w = width * 0.65
    cabin_d = depth * 0.60
    c_hw = cabin_w * 0.5
    c_hd = cabin_d * 0.5
    c_y = -hd + c_hd
    story_h = height * 0.5
    z_mid = z0 + story_h
    z1 = z0 + height
    roof_h = max(3.2, cabin_w * 0.42)
    peak_z = z1 + roof_h

    # 1. Full Stilt Substructure across building and dock
    _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Main Floor Slabs (Cabin and Pier Dock)
    create_box(bm, (cabin_w - wall_th * 2, cabin_d - wall_th * 2, 0.14), (0.0, c_y, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)
    create_box(bm, (width, depth - cabin_d, 0.16), (0.0, hd - (depth - cabin_d) * 0.5, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)
    _build_timber_deck_railing(bm, -hw, hw, c_y + c_hd, hd, z0 + 0.08)

    # 3. Cabin Walls with Doorway out to Pier
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), story_h * 0.85)
    _build_wall_with_door_opening(bm, -c_hw + wall_th, c_hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0, include_leaf=False)
    _build_wall_with_door_opening(bm, -c_hw + wall_th, c_hw - wall_th, c_y + c_hd - wall_th * 0.5,
                                  z0, z_mid, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=math.pi, include_leaf=False)
    _build_wall_with_window_y(bm, -hd + wall_th, c_y + c_hd - wall_th, -c_hw + wall_th * 0.5,
                              z0, z_mid, win_cy=c_y, win_cz=z0 + story_h * 0.52, win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -hd + wall_th, c_y + c_hd - wall_th, c_hw - wall_th * 0.5,
                              z0, z_mid, win_cy=c_y, win_cz=z0 + story_h * 0.52, win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)

    # 4. Upper Floor Hollow Cabin with Bone Windows
    create_box(bm, (cabin_w - wall_th * 2, wall_th, story_h), (0.0, -hd + wall_th * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (cabin_w - wall_th * 2, wall_th, story_h), (0.0, c_y + c_hd - wall_th * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, cabin_d - wall_th * 2, story_h), (-c_hw + wall_th * 0.5, c_y, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, cabin_d - wall_th * 2, story_h), (c_hw - wall_th * 0.5, c_y, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    _build_bone_window(bm, 0.0, -hd, z_mid + story_h * 0.52, rot_z=0.0, w=0.85, h=0.85)

    # 5. Cantilevered Cargo Hoist Crane Boom
    crane_x = c_hw + 0.3
    crane_y = c_y + c_hd * 0.5
    crane_h = height * 1.2
    create_cylinder(bm, radius=0.18, height=crane_h, segments=7,
                    location=(crane_x, crane_y, z0 + crane_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    boom_len = 3.6
    create_cylinder(bm, radius=0.14, height=boom_len, segments=6,
                    location=(crane_x + 1.2, crane_y, z0 + crane_h * 0.85),
                    rotation=(0, 0.65, 0), mat_index=MAT_INDEX_DRIFTWOOD)
    create_cylinder(bm, radius=0.02, height=2.4, segments=5,
                    location=(crane_x + 2.2, crane_y, z0 + crane_h * 0.85 - 1.2), mat_index=MAT_INDEX_ROPE)
    create_torus_ring(bm, (crane_x + 2.2, crane_y, z0 + crane_h * 0.85 - 2.4),
                      major_radius=0.12, minor_radius=0.025, mat_index=MAT_INDEX_IRON)

    # 6. Fish Drying Racks & Barrels on Pier
    for bx, by in ((c_hw + 1.2, c_y - 0.5), (c_hw + 1.8, c_y + 0.6), (-hw + 1.4, hd - 1.2)):
        create_cylinder(bm, radius=0.36, height=0.85, segments=8,
                        location=(bx, by, z0 + 0.50), mat_index=MAT_INDEX_DRIFTWOOD)
        create_torus_ring(bm, (bx, by, z0 + 0.35), major_radius=0.38, minor_radius=0.022, mat_index=MAT_INDEX_IRON)

    fr_x = -hw + 2.5
    fr_y = hd - 1.2
    create_box(bm, (2.4, 0.12, 1.8), (fr_x, fr_y, z0 + 1.0), mat_index=MAT_INDEX_DRIFTWOOD)
    for fi in range(4):
        create_cone(bm, radius1=0.12, radius2=0.02, height=0.55, segments=5,
                    location=(fr_x - 0.75 + fi * 0.5, fr_y + 0.1, z0 + 0.85),
                    rotation=(math.pi, 0, 0), mat_index=MAT_INDEX_BONE)

    # 7. Bone Scale Gable Roof on Cabin
    _build_gable_triangle_wall(bm, -c_hw, c_hw, -hd, z1, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -c_hw, c_hw, c_y + c_hd, z1, peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -c_hw, c_hw, -hd, c_y + c_hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=6)


def _build_hajfin_shaman_shrine(bm, props, diameter=11.0, height=7.5, found_h=0.6):
    """The Leviathan Bone Shrine:
    - Sacred tribal megalodon ceremonial sanctuary.
    - Two-tier stepped circular reef-stone dais.
    - Ring of 6 towering curved whale rib arches soaring inward to form a ribcage dome sanctuary.
    - Central carved megalodon jaw bone altar table with sacred offering bowl.
    - Tribal skull totems, glowing smoking brazier, and shark tooth fetish staves."""
    r_base = diameter * 0.5
    z0 = found_h

    # 1. Stepped Circular Reef Stone Dais
    create_cylinder(bm, radius=r_base, height=found_h * 0.6, segments=20,
                    location=(0.0, 0.0, found_h * 0.3), mat_index=MAT_INDEX_ROUGH_STONE)
    create_cylinder(bm, radius=r_base * 0.85, height=found_h * 0.4, segments=18,
                    location=(0.0, 0.0, found_h * 0.8), mat_index=MAT_INDEX_ROUGH_STONE)
    create_cylinder(bm, radius=r_base * 0.72, height=0.12, segments=16,
                    location=(0.0, 0.0, z0 + 0.06), mat_index=MAT_INDEX_FLOOR)

    # 2. Ring of 6 Towering Whale Rib Arches soaring inward into cathedral dome
    num_ribs = 6
    arch_r = r_base * 0.70
    dome_h = height
    for i in range(num_ribs):
        ang = i * (2.0 * math.pi / num_ribs)
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)

        p0 = (cos_a * arch_r, sin_a * arch_r, z0)
        p1 = (cos_a * (arch_r * 0.90), sin_a * (arch_r * 0.90), z0 + dome_h * 0.40)
        p2 = (cos_a * (arch_r * 0.48), sin_a * (arch_r * 0.48), z0 + dome_h * 0.78)
        p3 = (0.0, 0.0, z0 + dome_h)

        _create_oriented_beam(bm, p0, p1, width=0.38, depth=0.30, mat_index=MAT_INDEX_BONE)
        _create_oriented_beam(bm, p1, p2, width=0.30, depth=0.24, mat_index=MAT_INDEX_BONE)
        _create_oriented_beam(bm, p2, p3, width=0.24, depth=0.18, mat_index=MAT_INDEX_BONE)

        create_torus_ring(bm, (p0[0], p0[1], z0 + 0.45), major_radius=0.26, minor_radius=0.03, mat_index=MAT_INDEX_ROPE)

    # Apex megalodon dorsal fin crest atop the vault dome
    _build_shark_dorsal_fin(bm, 0.0, 0.0, z0 + dome_h, height=1.65, length=1.25, thickness=0.24, rot_z=0.0)

    # 3. Central Megalodon Jaw Bone Altar Table
    altar_w = 2.2
    altar_d = 1.4
    altar_h = 1.15
    create_box(bm, (altar_w, altar_d, 0.28), (0.0, 0.0, z0 + altar_h), mat_index=MAT_INDEX_BONE)
    for sgn_x in (-1.0, 1.0):
        for sgn_y in (-1.0, 1.0):
            create_cylinder(bm, radius=0.14, height=altar_h, segments=6,
                            location=(sgn_x * (altar_w * 0.4), sgn_y * (altar_d * 0.35), z0 + altar_h * 0.5),
                            mat_index=MAT_INDEX_BONE)

    # Sacred offering bowl / brazier atop altar
    create_cylinder(bm, radius=0.45, height=0.28, segments=10,
                    location=(0.0, 0.0, z0 + altar_h + 0.28), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.38, height=0.15, segments=8,
                    location=(0.0, 0.0, z0 + altar_h + 0.38), mat_index=MAT_INDEX_IRON)

    # 4. Flanking Tribal Shark Skull Totems on East and West
    for sgn_tx in (-1.0, 1.0):
        tx = sgn_tx * (arch_r * 0.88)
        totem_h = 3.2
        create_cylinder(bm, radius=0.15, height=totem_h, segments=7,
                        location=(tx, 0.0, z0 + totem_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.15, radius2=0.02, height=0.5, segments=6,
                    location=(tx, 0.0, z0 + totem_h + 0.25), mat_index=MAT_INDEX_DRIFTWOOD)
        _build_shark_skull_mount(bm, tx, -0.15, z0 + totem_h * 0.75,
                                 rot_z=0.0, scale=0.95)
        create_torus_ring(bm, (tx, 0.0, z0 + totem_h * 0.75), major_radius=0.22, minor_radius=0.025, mat_index=MAT_INDEX_ROPE)


# =============================================================================
# HELPER SUBSTRUCTURES
# =============================================================================

def _build_stilt_substructure(bm, x0, x1, y0, y1, height, door_cx=0.0, post_depth=10.0):
    """Crooked pier pilings underneath building with sill beams and wooden access steps.
    Posts extend 10 meters downwards so buildings can be placed over water, piers, cliffs."""
    post_spacing = 2.4
    nx = max(2, int((x1 - x0) / post_spacing) + 1)
    ny = max(2, int((y1 - y0) / post_spacing) + 1)

    total_post_h = height + post_depth
    cz = height - total_post_h * 0.5  # Extends from z = -post_depth down to z = height

    for ix in range(nx):
        x = x0 + ix * ((x1 - x0) / (nx - 1))
        for iy in range(ny):
            y = y0 + iy * ((y1 - y0) / (ny - 1))
            create_cylinder(bm, radius=0.20, height=total_post_h, segments=7,
                            location=(x, y, cz), mat_index=MAT_INDEX_TIMBER)

    # Heavy timber perimeter sill beams
    for sgn_y in (-1.0, 1.0):
        sy = y0 if sgn_y < 0 else y1
        create_box(bm, ((x1 - x0) + 0.3, 0.28, 0.28), ((x0 + x1) * 0.5, sy, height - 0.14),
                   mat_index=MAT_INDEX_TIMBER)
    for sgn_x in (-1.0, 1.0):
        sx = x0 if sgn_x < 0 else x1
        create_box(bm, (0.28, (y1 - y0) + 0.3, 0.28), (sx, (y0 + y1) * 0.5, height - 0.14),
                   mat_index=MAT_INDEX_TIMBER)

    # Walkable timber porch landing in front of door threshold
    landing_w = 2.40
    landing_d = 1.20
    landing_cy = y0 - landing_d * 0.5
    # Landing deck floor slab
    create_box(bm, (landing_w, landing_d, 0.16), (door_cx, landing_cy, height - 0.08), mat_index=MAT_INDEX_FLOOR)
    # Landing perimeter support joists
    create_box(bm, (landing_w, 0.22, 0.22), (door_cx, y0 - landing_d + 0.11, height - 0.20), mat_index=MAT_INDEX_TIMBER)
    for sgn_lp in (-1.0, 1.0):
        # Flanking joists
        create_box(bm, (0.22, landing_d, 0.22), (door_cx + sgn_lp * (landing_w * 0.5 - 0.11), landing_cy, height - 0.20),
                   mat_index=MAT_INDEX_TIMBER)
        # 2 sturdy stilt posts extending 10m downwards under landing outer corners
        create_cylinder(bm, radius=0.18, height=total_post_h, segments=7,
                        location=(door_cx + sgn_lp * (landing_w * 0.42), y0 - landing_d + 0.20, cz),
                        mat_index=MAT_INDEX_TIMBER)

    # Wooden access steps descending from landing deck down to ground
    num_steps = max(2, int(height / 0.22))
    step_w = 2.00
    step_d = 0.36
    run_len = num_steps * step_d
    y_stair_top = y0 - landing_d

    # Correctly aligned outside timber stringers flanking steps
    str_w = 0.16
    str_th = 0.24
    str_left_x = door_cx - step_w * 0.5 - str_w * 0.5
    str_right_x = door_cx + step_w * 0.5 + str_w * 0.5

    p_top_l = Vector((str_left_x, y_stair_top, height - 0.08))
    p_bot_l = Vector((str_left_x, y_stair_top - run_len, 0.08))
    _create_oriented_beam(bm, p_bot_l, p_top_l, width=str_w, depth=str_th, mat_index=MAT_INDEX_TIMBER)

    p_top_r = Vector((str_right_x, y_stair_top, height - 0.08))
    p_bot_r = Vector((str_right_x, y_stair_top - run_len, 0.08))
    _create_oriented_beam(bm, p_bot_r, p_top_r, width=str_w, depth=str_th, mat_index=MAT_INDEX_TIMBER)

    # Steps between the stringers
    for i in range(num_steps):
        sz = (i + 0.5) * (height / num_steps)
        sy = y_stair_top - (num_steps - i - 0.5) * step_d
        create_box(bm, (step_w, step_d * 1.05, 0.12), (door_cx, sy, sz), mat_index=MAT_INDEX_DRIFTWOOD)


def _build_timber_deck_railing(bm, x0, x1, y0, y1, z):
    """Heavy pirate timber balustrade with sturdy posts, top cap rail, and vertical pickets
    along the outer exposed edges (West x0 and North y1)."""
    rail_h = 1.05
    # West edge posts, pickets & top rail (at x=x0, y from y0 to y1)
    d = y1 - y0
    num_pickets = max(3, int(d / 0.65))
    create_box(bm, (0.22, d + 0.15, 0.12), (x0, (y0 + y1) * 0.5, z + rail_h), mat_index=MAT_INDEX_DRIFTWOOD)
    for i in range(num_pickets + 1):
        py = y0 + i * (d / num_pickets)
        create_cylinder(bm, radius=0.07, height=rail_h, segments=6,
                        location=(x0, py, z + rail_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # North edge posts, pickets & top rail (at y=y1, x from x0 to x1)
    w = x1 - x0
    num_pickets_w = max(3, int(w / 0.65))
    create_box(bm, (w + 0.15, 0.22, 0.12), ((x0 + x1) * 0.5, y1, z + rail_h), mat_index=MAT_INDEX_DRIFTWOOD)
    for i in range(num_pickets_w + 1):
        px = x0 + i * (w / num_pickets_w)
        create_cylinder(bm, radius=0.07, height=rail_h, segments=6,
                        location=(px, y1, z + rail_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)


# =============================================================================
# MAIN HAJFIN ENTRY POINT
# =============================================================================

def build_hajfin_building(obj, bm, props):
    """Primary entry point for generating authentic Hajfin pirate architecture.
    Completely replaces human half-timber/stone construction with 100% dedicated
    procedural geometry matching the Hajfin fantasy concept art."""
    seed = getattr(props, 'seed', 42)
    random.seed(seed)

    # Ensure material slots 0..55 are populated on obj
    setup_building_material_slots(obj, props)

    width = float(getattr(props, 'width', 7.0))
    depth = float(getattr(props, 'depth', 7.5))
    height = float(getattr(props, 'floor_height', 3.6)) * max(1, getattr(props, 'num_floors', 1))
    found_h = float(getattr(props, 'foundation_height', 1.0))

    # Primary archetype selection based on hajfin_style
    style = getattr(props, 'hajfin_style', 'SHANTY')
    arch = getattr(props, 'building_archetype', 'NONE')
    shape = getattr(props, 'building_shape', 'RECTANGLE')

    if style == 'ROUND_HUT' or shape in ('ROUND_TOWER', 'CIRCLE'):
        _build_hajfin_round_hut(bm, props, diameter=max(width, depth), height=height, found_h=found_h)
    elif style == 'CHIEFTAIN_HALL' or arch in ('CIVIC', 'TOWN_HALL', 'PALACE'):
        _build_hajfin_chieftain_hall(bm, props, width=max(10.0, width), depth=max(12.0, depth), height=height, found_h=found_h)
    elif style == 'TAVERN' or arch == 'TAVERN' or shape == 'L_SHAPE':
        _build_hajfin_pirate_tavern(bm, props, width=max(9.0, width), depth=max(9.0, depth), height=height, found_h=found_h)
    elif style == 'BONE_SHOP' or arch in ('STORE', 'COMMERCE'):
        _build_hajfin_bone_shop(bm, props, width=max(8.0, width), depth=max(7.5, depth), height=height, found_h=found_h)
    elif style in ('WATCHTOWER', 'LOOKOUT') or arch in ('WATCHTOWER', 'BARRACKS'):
        _build_hajfin_watchtower(bm, props, width=max(5.0, width), depth=max(5.0, depth), height=max(9.0, height), found_h=found_h)
    elif style in ('PALISADE_GATE', 'GATE') or arch in ('GATE', 'GATEHOUSE'):
        _build_hajfin_bone_gate(bm, props, width=max(12.0, width), depth=max(4.0, depth), height=max(5.5, height), found_h=0.0)
    elif style in ('FORGE', 'SMITHY') or arch in ('SMITHY', 'FORGE', 'BLACKSMITH'):
        _build_hajfin_forge(bm, props, width=max(9.0, width), depth=max(8.0, depth), height=height, found_h=found_h)
    elif style in ('FISH_DEPOT', 'DEPOT', 'PIER') or arch in ('WAREHOUSE', 'DEPOT', 'HARBOR'):
        _build_hajfin_fish_depot(bm, props, width=max(10.0, width), depth=max(12.0, depth), height=height, found_h=max(1.6, found_h))
    elif style in ('SHRINE', 'TEMPLE') or arch in ('TEMPLE', 'CHURCH', 'SHRINE'):
        _build_hajfin_shaman_shrine(bm, props, diameter=max(width, depth, 9.5), height=max(7.0, height), found_h=found_h)
    elif style == 'BLOCKHOUSE' or shape == 'CUBE':
        _build_hajfin_crate_blockhouse(bm, props, width=width, depth=depth, height=height, found_h=found_h)
    else:
        # Default iconic Shanty Shack (Image 6)
        _build_hajfin_shanty(bm, props, width=width, depth=depth, height=height, found_h=found_h)

    # Box UV mapping at scale 0.18 so timber boards span large expanses without tight repetitive tiling
    apply_box_uvs(bm, scale=0.18)

    # Write bmesh to obj
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
