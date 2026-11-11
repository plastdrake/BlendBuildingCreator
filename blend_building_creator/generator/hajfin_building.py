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

def _create_oriented_beam(bm, p0, p1, width=0.30, depth=0.30, mat_index=MAT_INDEX_DRIFTWOOD):
    """Creates a rectangular timber beam connecting any two 3D points p0 and p1."""
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
    # Main column
    create_box(bm, (size, size, col_h), (x, y, cz), mat_index=MAT_INDEX_DRIFTWOOD)

    # Beveled chisel pyramid cap on top
    cap_h = size * 0.45
    cap_z = z0 + col_h + cap_h * 0.5
    create_cone(bm, radius1=size * 0.707, radius2=0.03, height=cap_h, segments=4,
                location=(x, y, cap_z), rotation=(0, 0, math.pi * 0.25), mat_index=MAT_INDEX_DRIFTWOOD)

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
    threshold sill, header lintel, and shark jaw archway wrapping the opening.
    Door leaf is omitted by default so openings remain clear for Unreal Engine interactive doors."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    d_half_w = door_w * 0.5

    # 1. Left Wall Segment
    left_w = (door_cx - d_half_w) - x0
    if left_w > 0.05:
        left_cx = x0 + left_w * 0.5
        pos = rot_mat @ Vector((left_cx, y, z0 + (z1 - z0) * 0.5))
        create_box(bm, (left_w, wall_th, z1 - z0), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Right Wall Segment
    right_w = x1 - (door_cx + d_half_w)
    if right_w > 0.05:
        right_cx = (door_cx + d_half_w) + right_w * 0.5
        pos = rot_mat @ Vector((right_cx, y, z0 + (z1 - z0) * 0.5))
        create_box(bm, (right_w, wall_th, z1 - z0), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Lintel Wall Segment Above Door
    lintel_h = (z1 - (z0 + door_h))
    if lintel_h > 0.05:
        pos = rot_mat @ Vector((door_cx, y, z0 + door_h + lintel_h * 0.5))
        create_box(bm, (door_w, wall_th, lintel_h), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Threshold Sill Beam under Door
    pos = rot_mat @ Vector((door_cx, y, z0 - 0.06))
    create_box(bm, (door_w + 0.15, wall_th + 0.08, 0.14), (pos.x, pos.y, pos.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_FLOOR)

    # 5. Optional Recessed Door Leaf (ONLY if include_leaf is True, False by default for UE export)
    if include_leaf:
        recess = wall_th * 0.25
        door_pos = rot_mat @ Vector((door_cx, y + recess, z0 + door_h * 0.48))
        create_box(bm, (door_w * 0.90, 0.08, door_h * 0.96), (door_pos.x, door_pos.y, door_pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

        # Iron hinges/bands across the recessed door
        for hz in (z0 + door_h * 0.22, z0 + door_h * 0.72):
            h_pos = rot_mat @ Vector((door_cx, y + recess - 0.045, hz))
            create_box(bm, (door_w * 0.88, 0.02, 0.07), (h_pos.x, h_pos.y, h_pos.z),
                       rotation=(0, 0, rot_z), mat_index=MAT_INDEX_IRON)

        # Iron pull ring handle
        ring_pos = rot_mat @ Vector((door_cx + door_w * 0.28, y + recess - 0.06, z0 + door_h * 0.45))
        create_torus_ring(bm, (ring_pos.x, ring_pos.y, ring_pos.z),
                          rotation=(math.pi * 0.5, 0, rot_z), major_radius=0.065, minor_radius=0.013,
                          major_segments=10, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # 6. Shark Jaw Bone Arch wrapped around the opening
    _build_shark_jaw_arch(bm, door_cx, y - wall_th * 0.45, z0, rot_z=rot_z,
                          width=door_w * 1.15, height=door_h * 1.05)


def _build_shark_jaw_arch(bm, cx, cy, cz, rot_z=0.0, width=1.45, height=2.45):
    """Curved 3D predatory shark jaw arch framing the door opening with inward-pointing sharp teeth."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    jaw_segs = 8
    arch_pts = []

    for i in range(jaw_segs + 1):
        t = i / jaw_segs
        ang = math.pi * t
        lx = -math.cos(ang) * (width * 0.5)
        lz = math.sin(ang) * height
        if lz < height * 0.45:
            lz = (lz / (height * 0.45)) * (height * 0.42)
        else:
            norm_t = (lz - height * 0.45) / (height * 0.55)
            lz = height * 0.42 + (norm_t ** 0.82) * (height * 0.58)
        arch_pts.append((lx, lz))

    bone_rad = 0.12
    for i in range(len(arch_pts) - 1):
        x0, z0_pt = arch_pts[i]
        x1, z1_pt = arch_pts[i + 1]
        mid_x = (x0 + x1) * 0.5
        mid_z = (z0_pt + z1_pt) * 0.5
        seg_len = math.hypot(x1 - x0, z1_pt - z0_pt)
        tilt_ang = math.atan2(z1_pt - z0_pt, x1 - x0) - math.pi * 0.5

        seg_pos = rot_mat @ Vector((mid_x, 0.0, mid_z)) + Vector((cx, cy, cz))
        taper_r = bone_rad * (1.1 - 0.28 * (mid_z / height))
        create_cylinder(bm, radius=taper_r, height=seg_len * 1.05, segments=8,
                        location=(seg_pos.x, seg_pos.y, seg_pos.z),
                        rotation=(0, -tilt_ang, rot_z), mat_index=MAT_INDEX_BONE)

        # Inward-pointing shark teeth on upper arch segments
        if mid_z > height * 0.35:
            tooth_len = 0.16 + 0.04 * math.sin(i * 1.9)
            in_dx = -(z1_pt - z0_pt) / max(seg_len, 1e-4)
            in_dz = (x1 - x0) / max(seg_len, 1e-4)
            if in_dz > 0:
                in_dx, in_dz = -in_dx, -in_dz
            tx = mid_x + in_dx * (taper_r * 0.65)
            tz = mid_z + in_dz * (taper_r * 0.65)
            t_loc = rot_mat @ Vector((tx, 0.02, tz)) + Vector((cx, cy, cz))
            tooth_pitch = math.atan2(in_dz, in_dx) - math.pi * 0.5
            create_cone(bm, radius1=0.038, radius2=0.005, height=tooth_len, segments=5,
                        location=(t_loc.x, t_loc.y, t_loc.z),
                        rotation=(0, -tooth_pitch, rot_z), mat_index=MAT_INDEX_BONE)

    # Carved Bone Fin Emblem above arch apex
    emblem_loc = rot_mat @ Vector((0.0, 0.03, height + 0.35)) + Vector((cx, cy, cz))
    _build_bone_fin_emblem(bm, emblem_loc.x, emblem_loc.y, emblem_loc.z, rot_z, scale=0.55)


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
    """Builds a solid triangular timber gable wall filling the space from eave up to the roof ridge."""
    mx = (x0 + x1) * 0.5
    w = x1 - x0
    h = z_peak - z_eave
    num_planks = max(3, int(h / 0.45))
    dz = h / num_planks

    for i in range(num_planks):
        pz0 = z_eave + i * dz
        pz1 = pz0 + dz
        # Taper width towards peak
        t_mid = (i + 0.5) / num_planks
        plank_w = w * (1.0 - t_mid)
        if plank_w > 0.08:
            create_box(bm, (plank_w, wall_th, dz * 1.02), (mx, y, pz0 + dz * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)


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


def _build_bone_window(bm, x, y, z, rot_z=0.0, w=0.75, h=0.75):
    """Window framed with 4 carved bone segments and vertical iron security bars."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    bone_r = 0.055

    # 4 Bone frame segments
    for sgn_y in (-1.0, 1.0):
        fz = h * 0.5 * sgn_y
        b_loc = rot_mat @ Vector((0.0, 0.0, fz)) + Vector((x, y, z))
        create_cylinder(bm, radius=bone_r, height=w + bone_r * 1.6, segments=6,
                        location=(b_loc.x, b_loc.y, b_loc.z),
                        rotation=(0, math.pi * 0.5, rot_z), mat_index=MAT_INDEX_BONE)
    for sgn_x in (-1.0, 1.0):
        fx = w * 0.5 * sgn_x
        b_loc = rot_mat @ Vector((fx, 0.0, 0.0)) + Vector((x, y, z))
        create_cylinder(bm, radius=bone_r, height=h, segments=6,
                        location=(b_loc.x, b_loc.y, b_loc.z),
                        rotation=(0, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # 3 Vertical iron bars
    num_bars = 3
    for i in range(num_bars):
        bx = -w * 0.3 + i * (w * 0.6 / max(1, num_bars - 1))
        bar_loc = rot_mat @ Vector((bx, 0.06, 0.0)) + Vector((x, y, z))
        create_cylinder(bm, radius=0.016, height=h * 0.85, segments=5,
                        location=(bar_loc.x, bar_loc.y, bar_loc.z),
                        rotation=(0, 0, rot_z), mat_index=MAT_INDEX_IRON)

    # Dark recessed backing
    back_loc = rot_mat @ Vector((0.0, 0.12, 0.0)) + Vector((x, y, z))
    create_box(bm, (w * 0.88, 0.04, h * 0.88), (back_loc.x, back_loc.y, back_loc.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_GLASS)


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
                                     length=2.4, height=2.6, width=1.9, num_pairs=4):
    """Projecting whale rib cage tunnel entrance extending outward from the main door."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    step_d = length / max(1, num_pairs)

    for i in range(num_pairs):
        fwd = (i + 1) * step_d
        pair_h = height * (1.0 - 0.06 * i)
        pair_w = width * (1.0 + 0.04 * i)

        for sgn in (-1.0, 1.0):
            rib_base = rot_mat @ Vector((sgn * pair_w * 0.5, fwd, 0.0)) + Vector((entrance_x, entrance_y, z0))
            rib_mid = rot_mat @ Vector((sgn * pair_w * 0.65, fwd, pair_h * 0.55)) + Vector((entrance_x, entrance_y, z0))
            rib_top = rot_mat @ Vector((sgn * 0.08, fwd, pair_h)) + Vector((entrance_x, entrance_y, z0))

            create_cylinder(bm, radius=0.10, height=pair_h * 0.65, segments=7,
                            location=(rib_base.x * 0.4 + rib_mid.x * 0.6,
                                      rib_base.y * 0.4 + rib_mid.y * 0.6,
                                      z0 + pair_h * 0.3),
                            rotation=(0, sgn * 0.35, rot_z), mat_index=MAT_INDEX_BONE)
            create_cylinder(bm, radius=0.08, height=pair_h * 0.55, segments=6,
                            location=(rib_mid.x * 0.4 + rib_top.x * 0.6,
                                      rib_mid.y * 0.4 + rib_top.y * 0.6,
                                      z0 + pair_h * 0.8),
                            rotation=(0, -sgn * 0.55, rot_z), mat_index=MAT_INDEX_BONE)

        # Rope winding at top apex
        apex_loc = rot_mat @ Vector((0.0, fwd, pair_h - 0.04)) + Vector((entrance_x, entrance_y, z0))
        create_cylinder(bm, radius=0.12, height=0.18, segments=8,
                        location=(apex_loc.x, apex_loc.y, apex_loc.z),
                        rotation=(math.pi * 0.5, 0, rot_z), mat_index=MAT_INDEX_ROPE)

    # Flanking carved wooden totem posts at the tunnel entrance
    for sgn in (-1.0, 1.0):
        post_loc = rot_mat @ Vector((sgn * (width * 0.55 + 0.4), length + 0.35, 0.0)) + Vector((entrance_x, entrance_y, z0))
        _build_tribal_totem_post(bm, post_loc.x, post_loc.y, z0, height=2.4)


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
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

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
                                      z0, z_mid, door_cx=-0.4, door_w=door_w, door_h=door_h,
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
                                      z0, z1, door_cx=-0.4, door_w=door_w, door_h=door_h,
                                      wall_th=wall_th, rot_z=0.0,
                                      include_leaf=getattr(props, 'include_door_leaves', False))

        # Exposed heavy timber collar tie beams spanning across ceiling
        for ty in (-hd * 0.5, 0.0, hd * 0.5):
            create_box(bm, (width - wall_th * 2, 0.22, 0.26), (0.0, ty, z1 - 0.15), mat_index=MAT_INDEX_DRIFTWOOD)

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

    # 2. Tapered 8-sided body shell (7 solid facets, Facet 6 is South Doorway)
    lean_pitch = math.atan2(r_base - r_top, height)
    facet_w_bot = 2.0 * r_base * math.sin(math.pi / num_facets)
    facet_w_top = 2.0 * r_top * math.sin(math.pi / num_facets)
    facet_dist_bot = r_base * math.cos(math.pi / num_facets)
    facet_dist_top = r_top * math.cos(math.pi / num_facets)
    mid_dist = (facet_dist_bot + facet_dist_top) * 0.5

    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = float(getattr(props, 'door_height', 3.50))
    door_h = min(door_h, height * 0.82)

    for i in range(num_facets):
        ac = i * (2.0 * math.pi / num_facets)  # 0=E, 2=N, 4=W, 6=S
        if i == 6:
            # SOUTH DOOR FACET: Real cut doorway opening!
            jamb_w = (facet_w_bot - door_w) * 0.5
            if jamb_w > 0.05:
                lx = -door_w * 0.5 - jamb_w * 0.5
                create_box(bm, (jamb_w, wall_th, height), (lx, -mid_dist, z0 + height * 0.5),
                           rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)
                rx = door_w * 0.5 + jamb_w * 0.5
                create_box(bm, (jamb_w, wall_th, height), (rx, -mid_dist, z0 + height * 0.5),
                           rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)

            lintel_h = height - door_h
            if lintel_h > 0.05:
                create_box(bm, (door_w, wall_th, lintel_h),
                           (0.0, -mid_dist - (door_h + lintel_h * 0.5 - height * 0.5) * math.tan(lean_pitch),
                            z0 + door_h + lintel_h * 0.5),
                           rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)

            # Threshold sill beam at bottom
            create_box(bm, (door_w + 0.30, wall_th + 0.10, 0.14), (0.0, -facet_dist_bot, z0 - 0.05),
                       mat_index=MAT_INDEX_FLOOR)

            # Carved bone shark fin emblem plaque above door header
            emblem_z = z0 + door_h + 0.45
            create_box(bm, (0.75, 0.06, 0.50),
                       (0.0, -mid_dist - (emblem_z - z0 - height * 0.5) * math.tan(lean_pitch) - 0.05, emblem_z),
                       rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_BONE)
            create_cone(bm, radius1=0.25, radius2=0.03, height=0.45, segments=4,
                        location=(0.0, -mid_dist - (emblem_z - z0 - height * 0.5) * math.tan(lean_pitch) - 0.12, emblem_z + 0.05),
                        rotation=(math.pi * 0.5 - lean_pitch, 0.2, 0), mat_index=MAT_INDEX_BONE)

            if include_leaves:
                create_box(bm, (door_w * 0.90, 0.08, door_h * 0.96),
                           (0.0, -mid_dist + 0.10, z0 + door_h * 0.48),
                           rotation=(-lean_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)

            # Giant Shark jaw bone archway framing the opening
            _build_shark_jaw_arch(bm, 0.0, -facet_dist_bot, z0, rot_z=0.0, width=door_w * 1.15, height=door_h * 1.05)
        else:
            fc_x = math.cos(ac) * mid_dist
            fc_y = math.sin(ac) * mid_dist
            p_rot = (lean_pitch * math.sin(ac), -lean_pitch * math.cos(ac), ac - math.pi * 0.5)
            avg_w = (facet_w_bot + facet_w_top) * 0.5
            create_box(bm, (avg_w * 1.02, wall_th, height), (fc_x, fc_y, z0 + height * 0.5),
                       rotation=p_rot, mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Perimeter Timber Corner Posts at Vertex Junctions
    col_size = 0.44
    for i in range(num_facets):
        v_ang = (i - 0.5) * (2.0 * math.pi / num_facets)
        bx = math.cos(v_ang) * r_base
        by = math.sin(v_ang) * r_base
        tx = math.cos(v_ang) * r_top
        ty = math.sin(v_ang) * r_top
        post_rot = (lean_pitch * math.sin(v_ang), -lean_pitch * math.cos(v_ang), v_ang)

        mid_x = (bx + tx) * 0.5
        mid_y = (by + ty) * 0.5
        create_box(bm, (col_size, col_size, height + 0.40), (mid_x, mid_y, z0 + height * 0.5),
                   rotation=post_rot, mat_index=MAT_INDEX_DRIFTWOOD)

        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.24), (bx, by, z0 + 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.24), (tx, ty, z1 - 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)

    # 4. Rear Whale Spine Buttress (North, ang = +pi/2)
    _build_whale_spine_buttress(bm, 0.0, r_base * 0.95, z0, rot_z=0.0, num_vertebrae=7, max_h=height * 0.9)

    # 5. Diagonal Bone-Framed Windows (East and West flanks)
    for ang in (-math.pi * 0.75, -math.pi * 0.25):
        wx = math.cos(ang) * (r_base * 0.6 + r_top * 0.4)
        wy = math.sin(ang) * (r_base * 0.6 + r_top * 0.4)
        _build_bone_window(bm, wx, wy, z0 + height * 0.45, rot_z=ang + math.pi * 0.5, w=0.85, h=0.85)

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
    """Builds a gable triangle wall on the West or East side when ridge runs along X."""
    my = (y0 + y1) * 0.5
    h = z_peak - z_eave
    d = abs(y1 - y0)
    num_planks = max(3, int(h / 0.45))
    dz = h / num_planks
    for i in range(num_planks):
        pz0 = z_eave + i * dz
        t_mid = (i + 0.5) / num_planks
        plank_d = d * (1.0 - t_mid)
        if plank_d > 0.08:
            create_box(bm, (wall_th, plank_d, dz * 1.02), (x, my, pz0 + dz * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)


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

    # 5. Access Ladder (Mounted on Front-Right, leading from ground to platform)
    lad_w = 0.85
    lad_x = h_tw * 0.65
    lad_y0 = -h_bd * 1.15
    lad_y1 = -h_td * 0.96

    # Two heavy timber ladder stringers
    for sgn_lad in (-1.0, 1.0):
        lx = lad_x + sgn_lad * (lad_w * 0.5)
        _create_oriented_beam(bm, (lx, lad_y0, 0.0), (lx, lad_y1, stilt_h + 0.65),
                              width=0.14, depth=0.16, mat_index=MAT_INDEX_DRIFTWOOD)

    # Ladder rungs spaced vertically
    num_rungs = max(5, int(stilt_h / 0.35))
    for i in range(1, num_rungs + 1):
        rz = i * (stilt_h / (num_rungs + 1))
        t_lad = rz / stilt_h
        ry = lad_y0 * (1.0 - t_lad) + lad_y1 * t_lad
        _create_oriented_beam(bm, (lad_x - lad_w * 0.46, ry, rz), (lad_x + lad_w * 0.46, ry, rz),
                              width=0.10, depth=0.12, mat_index=MAT_INDEX_DRIFTWOOD)

    # 6. Elevated Platform Deck with Cantilevered Sill Joists
    deck_w = tw + 0.80
    deck_d = td + 0.80
    h_dw = deck_w * 0.5
    h_dd = deck_d * 0.5

    # Heavy perimeter sill joists underneath deck
    for sgn_y in (-1.0, 1.0):
        create_box(bm, (deck_w, 0.30, 0.30), (0.0, sgn_y * (h_td + 0.15), stilt_h - 0.15), mat_index=MAT_INDEX_DRIFTWOOD)
    for sgn_x in (-1.0, 1.0):
        create_box(bm, (0.30, deck_d, 0.30), (sgn_x * (h_tw + 0.15), 0.0, stilt_h - 0.15), mat_index=MAT_INDEX_DRIFTWOOD)

    # Walkable timber floor slab
    create_box(bm, (deck_w, deck_d, 0.16), (0.0, 0.0, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)

    # 7. Sentry Lookout Cabin (4 Corner Posts & Balustrade)
    col_size = 0.42
    for sgn_x, sgn_y in corner_signs:
        cx = sgn_x * h_tw
        cy = sgn_y * h_td
        create_box(bm, (col_size, col_size, cabin_h + 0.20), (cx, cy, stilt_h + cabin_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        # Iron corner brackets at base and top
        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.26), (cx, cy, stilt_h + 0.18), mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.05, col_size + 0.05, 0.26), (cx, cy, eave_z - 0.18), mat_index=MAT_INDEX_IRON)

    # Balustrades / Half-walls around the observation platform
    # Left (West) balustrade:
    create_box(bm, (0.16, td, 1.10), (-h_tw, 0.0, stilt_h + 0.55), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.24, td + 0.1, 0.12), (-h_tw, 0.0, stilt_h + 1.10), mat_index=MAT_INDEX_DRIFTWOOD)

    # Rear (North) balustrade / half-wall:
    create_box(bm, (tw, 0.16, 1.10), (0.0, h_td, stilt_h + 0.55), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (tw + 0.1, 0.24, 0.12), (0.0, h_td, stilt_h + 1.10), mat_index=MAT_INDEX_DRIFTWOOD)

    # Right (East) balustrade (leaves front portion open for ladder entrance):
    create_box(bm, (0.16, td * 0.55, 1.10), (h_tw, h_td * 0.45, stilt_h + 0.55), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.24, td * 0.55, 0.12), (h_tw, h_td * 0.45, stilt_h + 1.10), mat_index=MAT_INDEX_DRIFTWOOD)

    # 8. Front Facade: Low Timber Apron & Giant Carved Bone Window Frame
    apron_h = 1.25
    apron_w = tw - col_size
    create_box(bm, (apron_w, 0.22, apron_h), (0.0, -h_td, stilt_h + apron_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Header beam above window opening
    create_box(bm, (tw, 0.26, 0.26), (0.0, -h_td, eave_z - 0.13), mat_index=MAT_INDEX_DRIFTWOOD)

    # GIANT CARVED BONE WINDOW FRAME (Matching Concept Art):
    win_w = apron_w * 0.92
    win_h = 1.35
    win_cx = 0.0
    win_cy = -h_td - 0.12
    win_cz = stilt_h + apron_h + win_h * 0.52

    _build_carved_bone_lookout_frame(bm, win_cx, win_cy, win_cz, width=win_w, height=win_h)

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

    # Upper front wall with windows
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * (hw * 0.45), -hd, z_mid + story_h * 0.52, rot_z=0.0, w=0.85, h=0.85)

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
    Open barter stall counter, flip-up timber awning, flanking pier dock platforms,
    internal timber staircase connecting ground floor trade room to the upper lookout room,
    hollow upper room with bone windows, giant mounted shark skull, dual dock access ladder,
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
    if found_h > 0.2:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Ground Floor Slab (Walkable trade room interior)
    create_box(bm, (width - wall_th * 2, depth - wall_th * 2, 0.14),
               (0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 3. Ground Floor Walls with Open Barter Counter & Side Door
    create_box(bm, (width - wall_th * 2, wall_th, g_h), (0.0, hd - wall_th * 0.5, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, g_h), (-hw + wall_th * 0.5, 0.0, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, g_h), (hw - wall_th * 0.5, 0.0, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)

    # Massive Ground Floor Corner Columns
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z_mid, size=col_size, extend_top=0.25)

    # Open Barter Trade Counter with Flip-Up Awning (scaled for 2-3m tall Hajfin)
    counter_w = 4.4
    counter_d = 1.3
    counter_h = 1.2
    create_box(bm, (counter_w, counter_d, counter_h), (0.0, -hd - counter_d * 0.3, z0 + counter_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (counter_w * 0.95, 0.25, 1.8), (0.0, -hd, z0 + counter_h + 0.9), mat_index=MAT_INDEX_GLASS)

    awning_w = counter_w * 1.15
    awning_d = 1.6
    create_box(bm, (awning_w, awning_d, 0.09), (0.0, -hd - awning_d * 0.45, z0 + counter_h + 1.95),
               rotation=(0.32, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (3.8, 0.08, 0.65), (0.0, -hd - 0.15, z0 + counter_h + 2.35), mat_index=MAT_INDEX_DRIFTWOOD)

    # Ground floor side entrance door
    door_w = float(getattr(props, 'door_width', 1.80))
    door_h = min(float(getattr(props, 'door_height', 3.50)), g_h * 0.85)
    _build_wall_with_door_opening(bm, -hw + wall_th, -counter_w * 0.5 - 0.2, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=-hw * 0.65, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # 4. Flanking Wooden Dock / Pier Platforms
    for sgn_x in (-1.0, 1.0):
        plat_w = 1.8
        plat_d = depth * 0.85
        px = sgn_x * (hw + plat_w * 0.5)
        create_box(bm, (plat_w, plat_d, 0.14), (px, 0.0, z0 + 1.2), mat_index=MAT_INDEX_FLOOR)
        for py in (-plat_d * 0.4, 0.0, plat_d * 0.4):
            create_cylinder(bm, radius=0.15, height=z0 + 1.2, segments=7,
                            location=(px, py, (z0 + 1.2) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Accessible Internal Timber Staircase & Upper Floor Deck
    u_w = width * 0.60
    u_d = depth * 0.72
    u_hw = u_w * 0.5
    u_hd = u_d * 0.5

    stair_w = 1.60
    stair_x0 = u_hw - stair_w - 0.2
    stair_x1 = u_hw - 0.2
    stair_y0 = -u_hd + 1.8
    stair_y1 = -u_hd + 5.8
    _build_hajfin_floor_slab_with_stairwell(bm, -hw + wall_th, hw - wall_th, -hd + wall_th, hd - wall_th,
                                            z_mid, stair_x0, stair_x1, stair_y0, stair_y1,
                                            open_exit_side='NORTH')
    _build_hajfin_interior_staircase(bm, x0=(stair_x0 + stair_x1) * 0.5, y0=stair_y0 + 0.2, z0=z0,
                                     x1=(stair_x0 + stair_x1) * 0.5, y1=stair_y1 - 0.4, z1=z_mid,
                                     width=stair_w)

    # 6. Accessible Second-Level Central Lookout Room (HOLLOW!)
    # Rear wall of upper room
    create_box(bm, (u_w, wall_th, u_h), (0.0, u_hd - wall_th * 0.5, z_mid + u_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Left & Right walls with bone windows
    _build_wall_with_window_y(bm, -u_hd + wall_th, u_hd - wall_th, -u_hw + wall_th * 0.5, z_mid, z_top,
                              win_cy=0.0, win_cz=z_mid + u_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -u_hd + wall_th, u_hd - wall_th, u_hw - wall_th * 0.5, z_mid, z_top,
                              win_cy=0.0, win_cz=z_mid + u_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_east=True)
    # Front wall of upper room with window and hatch/door
    _build_wall_with_window_x(bm, -u_hw + wall_th, u_hw - wall_th, -u_hd + wall_th * 0.5, z_mid, z_top,
                              win_cx=-u_hw * 0.45, win_cz=z_mid + u_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_north=False)

    # Upper corner columns
    for cx in (-u_hw, u_hw):
        for cy in (-u_hd, u_hd):
            _build_chunky_corner_column(bm, cx, cy, z_mid, z_top, size=0.40, extend_top=0.35)

    # 7. Giant Open Shark Skull mounted on upper front facade
    _build_shark_skull_mount(bm, u_w * 0.28, -u_hd, z_mid + u_h * 0.62, rot_z=0.0, scale=1.2)

    # 8. Exterior Wooden Ladder
    lad_x = u_w * 0.42
    lad_y = -hd - 0.25
    lad_len = g_h * 1.15
    lad_pitch = 0.22
    for sgn_rail in (-0.28, 0.28):
        create_cylinder(bm, radius=0.045, height=lad_len, segments=6,
                        location=(lad_x + sgn_rail, lad_y + lad_pitch * g_h * 0.5, z0 + g_h * 0.5),
                        rotation=(lad_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)
    for r_i in range(10):
        rz = z0 + 0.35 + r_i * (g_h * 0.95 / 10)
        ry = lad_y + (rz - z0) * math.tan(lad_pitch)
        create_box(bm, (0.56, 0.07, 0.07), (lad_x, ry, rz), mat_index=MAT_INDEX_DRIFTWOOD)

    # 9. Whale Ribs lashed along corner post
    for ri in range(5):
        rib_z = z0 + 0.8 + ri * 0.40
        create_cylinder(bm, radius=0.05, height=0.80, segments=6,
                        location=(hw * 0.55, -u_hd - 0.10, rib_z),
                        rotation=(0, 0.85, 0), mat_index=MAT_INDEX_BONE)

    # 10. Multi-Tier Bone Scale Roofs with Full Solid Gable Triangles
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
    _build_gable_triangle_wall(bm, -u_hw, u_hw, -u_hd, z_top, u_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -u_hw, u_hw, u_hd, z_top, u_peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -u_hw, u_hw, -u_hd, u_hd, z_top, 3.2,
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

    # 3. Raised Chieftain Dais / Throne Platform at Rear
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

    # 7. Projecting Whale Rib Cage Tunnel Entrance (Image 4)
    _build_whale_rib_tunnel_entrance(bm, 0.0, -hd, z0, rot_z=0.0, length=3.5, height=3.8, width=2.8, num_pairs=5)

    # Flanking Tribal Totem Posts at entrance
    for sgn_t in (-1.0, 1.0):
        tx = sgn_t * 2.20
        ty = -hd - 1.4
        create_cylinder(bm, radius=0.22, height=3.6, segments=7,
                        location=(tx, ty, z0 + 1.8), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.26, radius2=0.03, height=0.75, segments=5,
                    location=(tx, ty, z0 + 3.9), mat_index=MAT_INDEX_DRIFTWOOD)
        create_box(bm, (0.85, 0.14, 0.20), (tx, ty, z0 + 2.8), mat_index=MAT_INDEX_DRIFTWOOD)
        create_torus_ring(bm, (tx, ty, z0 + 2.1), major_radius=0.24, minor_radius=0.035, mat_index=MAT_INDEX_ROPE)
        create_torus_ring(bm, (tx, ty, z0 + 2.6), major_radius=0.24, minor_radius=0.035, mat_index=MAT_INDEX_ROPE)

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
    create_box(bm, (m_w - wing_w, wall_th, story_h),
               (-hw + (m_w - wing_w) * 0.5, -hd + m_d - wall_th * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (-hw + wall_th * 0.5, my, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, m_d - wall_th * 2, story_h), (hw - wall_th * 0.5, my, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Wing block walls (Hollow!)
    create_box(bm, (wing_w - wall_th * 2, wall_th, story_h),
               (hw - wing_w * 0.5, hd - wall_th * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, wing_d - wall_th * 2, story_h),
               (hw - wall_th * 0.5, hd - wing_d * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, wing_d - wall_th * 2, story_h),
               (hw - wing_w + wall_th * 0.5, hd - wing_d * 0.5, z0 + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Open-Air Stilt Drinking Deck in L-cutout
    deck_w = width - wing_w
    deck_d = wing_d
    deck_x = -hw + deck_w * 0.5
    deck_y = hd - wing_d * 0.5
    create_box(bm, (deck_w, deck_d, 0.16), (deck_x, deck_y, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)
    _build_timber_deck_railing(bm, deck_x, deck_y, z0 + 0.08, deck_w, deck_d)

    # Clustered grog barrels on drinking deck
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
    create_box(bm, (m_w - wing_w, wall_th, story_h),
               (-hw + (m_w - wing_w) * 0.5, -hd + m_d - wall_th * 0.5, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
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

    # Upper Balcony Walkout Door in L-junction overlooking drinking deck
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wing_w, -hd + m_d - wall_th * 0.5,
                                  z_mid, z1, door_cx=-hw + deck_w * 0.5, door_w=1.60, door_h=3.20,
                                  wall_th=wall_th, rot_z=0.0,
                                  include_leaf=False)

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


# =============================================================================
# HELPER SUBSTRUCTURES
# =============================================================================

def _build_stilt_substructure(bm, x0, x1, y0, y1, height):
    """Crooked pier pilings underneath building with sill beams and wooden access steps."""
    post_spacing = 2.4
    nx = max(2, int((x1 - x0) / post_spacing) + 1)
    ny = max(2, int((y1 - y0) / post_spacing) + 1)

    for ix in range(nx):
        x = x0 + ix * ((x1 - x0) / (nx - 1))
        for iy in range(ny):
            y = y0 + iy * ((y1 - y0) / (ny - 1))
            create_cylinder(bm, radius=0.18, height=height + 0.1, segments=7,
                            location=(x, y, height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Heavy timber perimeter sill beams
    for sgn_y in (-1.0, 1.0):
        sy = y0 if sgn_y < 0 else y1
        create_box(bm, ((x1 - x0) + 0.3, 0.28, 0.28), ((x0 + x1) * 0.5, sy, height - 0.14),
                   mat_index=MAT_INDEX_DRIFTWOOD)
    for sgn_x in (-1.0, 1.0):
        sx = x0 if sgn_x < 0 else x1
        create_box(bm, (0.28, (y1 - y0) + 0.3, 0.28), (sx, (y0 + y1) * 0.5, height - 0.14),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # Wooden access steps leading directly to front door threshold
    num_steps = max(2, int(height / 0.22))
    step_w = 2.20
    step_d = 0.38

    # Angled heavy timber side stringers supporting the steps
    for sgn_x in (-1.0, 1.0):
        sx = sgn_x * (step_w * 0.5 - 0.08)
        run_len = num_steps * step_d
        str_len = math.hypot(run_len, height)
        ang = math.atan2(height, run_len)
        create_box(bm, (0.16, 0.22, str_len), (sx, y0 - run_len * 0.5, height * 0.5),
                   rotation=(ang, 0.0, 0.0), mat_index=MAT_INDEX_DRIFTWOOD)

    for i in range(num_steps):
        sz = (i + 0.5) * (height / num_steps)
        sy = y0 - (num_steps - i) * step_d
        create_box(bm, (step_w, step_d * 1.05, 0.12), (0.0, sy, sz), mat_index=MAT_INDEX_DRIFTWOOD)


def _build_timber_deck_railing(bm, cx, cy, cz, w, d):
    """Rough timber balustrade around open drinking deck."""
    rail_h = 0.95
    post_r = 0.08
    for px in (cx - w * 0.5, cx + w * 0.5):
        for py in (cy - d * 0.5, cy + d * 0.5):
            create_cylinder(bm, radius=post_r, height=rail_h, segments=6,
                            location=(px, py, cz + rail_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (w, 0.12, 0.08), (cx, cy - d * 0.5, cz + rail_h), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (0.12, d, 0.08), (cx - w * 0.5, cy, cz + rail_h), mat_index=MAT_INDEX_DRIFTWOOD)


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
    elif style == 'BLOCKHOUSE' or shape == 'CUBE':
        _build_hajfin_crate_blockhouse(bm, props, width=width, depth=depth, height=height, found_h=found_h)
    else:
        # Default iconic Shanty Shack (Image 6)
        _build_hajfin_shanty(bm, props, width=width, depth=depth, height=height, found_h=found_h)

    # Box UV mapping at scale 0.28 so planks span full story heights with wide chunky timber boards
    apply_box_uvs(bm, scale=0.28)

    # Write bmesh to obj
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
