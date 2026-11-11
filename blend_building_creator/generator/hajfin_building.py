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
    MAT_INDEX_CUT_STONE,
    MAT_INDEX_WATER,
)
from .mesh_utils import (
    create_box,
    create_beveled_box,
    create_cylinder,
    create_cone,
    create_torus_ring,
    create_hollow_cylinder,
    apply_box_uvs,
    transform_faces,
)
from .interior import build_straight_staircase
from .railing import build_railing
from .accessories.artisan_props import build_anvil, build_tool_rack
from .uv_utils import timber_box

_HAJFIN_ROOF_PROPS = None


def _build_hajfin_roof_variant(bm, x0, x1, y0, y1, eave_z, peak_h,
                               overhang_x=0.55, overhang_y=0.55):
    """Build a Hajfin roof using the selected human-style structural variant."""
    props = _HAJFIN_ROOF_PROPS
    style = getattr(props, 'roof_style', 'SHINGLES') if props is not None else 'SHINGLES'
    if style == 'SHINGLES':
        return False

    if style == 'SWAY':
        from .roof.sway_roof import build_sway_roof
        build_sway_roof(
            bm, x0, x1, y0, y1, eave_z, roof_height=peak_h,
            overhang=max(overhang_x, overhang_y),
            sway_amount=float(getattr(props, 'roof_sway', 0.28)),
            wall_thickness=0.26, tier='TIER_2', roof_mat='WOOD_SHINGLES',
            gable_ends=(), roof_flare=0.42,
        )
        return True

    if style == 'TARP':
        from .roof.makeshift_roof import build_makeshift_roof
        build_makeshift_roof(
            bm, x0, x1, y0, y1, z_base=eave_z,
            effective_archetype='HAJFIN', seed=int(getattr(props, 'seed', 42)),
        )
        return True

    if style == 'FLAT':
        ox = max(0.35, overhang_x)
        oy = max(0.35, overhang_y)
        z = eave_z + 0.08
        create_box(bm, (x1 - x0 + ox * 2.0, y1 - y0 + oy * 2.0, 0.18),
                   ((x0 + x1) * 0.5, (y0 + y1) * 0.5, z),
                   mat_index=MAT_INDEX_TIMBER)
        for size, loc in (
            ((x1 - x0 + ox * 2.0, 0.24, 0.28), ((x0 + x1) * 0.5, y0 - oy, z + 0.16)),
            ((x1 - x0 + ox * 2.0, 0.24, 0.28), ((x0 + x1) * 0.5, y1 + oy, z + 0.16)),
            ((0.24, y1 - y0 + oy * 2.0, 0.28), (x0 - ox, (y0 + y1) * 0.5, z + 0.16)),
            ((0.24, y1 - y0 + oy * 2.0, 0.28), (x1 + ox, (y0 + y1) * 0.5, z + 0.16)),
        ):
            create_box(bm, size, loc, mat_index=MAT_INDEX_TIMBER)
        return True

    if style == 'PLANKS':
        _build_hajfin_supported_plank_roof(
            bm, x0, x1, y0, y1, eave_z, peak_h,
            overhang_x, overhang_y,
        )
        return True

    return False


def _build_hajfin_supported_plank_roof(bm, x0, x1, y0, y1, eave_z, peak_h,
                                       overhang_x=0.55, overhang_y=0.55):
    """Build a shabby plank roof with visible gaps and timber support below."""
    ridge_x = (x0 + x1) * 0.5
    ridge_z = eave_z + peak_h
    roof_y0 = y0 - overhang_y
    roof_y1 = y1 + overhang_y
    span_y = roof_y1 - roof_y0
    left_eave = x0 - overhang_x
    right_eave = x1 + overhang_x
    slope_len = math.hypot(ridge_x - left_eave, peak_h)
    pitch = math.atan2(peak_h, (x1 - x0) * 0.5 + overhang_x)

    # Primary ridge and eave beams carry the boards instead of leaving them
    # suspended above the frame.
    for bx, bz in ((ridge_x, ridge_z), (left_eave, eave_z), (right_eave, eave_z)):
        timber_box(
            bm, size=(0.26, span_y, 0.30),
            location=(bx, (roof_y0 + roof_y1) * 0.5, bz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012, long_axis=1,
        )

    # Sloped rafters are evenly spaced along the ridge and visibly meet both
    # eave beams. Their UVs follow the beam length.
    rafter_count = max(4, int(span_y / 1.35) + 1)
    for i in range(rafter_count):
        ty = roof_y0 + (roof_y1 - roof_y0) * i / max(1, rafter_count - 1)
        _create_oriented_beam(
            bm, (ridge_x, ty, ridge_z - 0.02),
            (left_eave, ty, eave_z),
            width=0.16, depth=0.18, mat_index=MAT_INDEX_TIMBER,
        )
        _create_oriented_beam(
            bm, (ridge_x, ty, ridge_z - 0.02),
            (right_eave, ty, eave_z),
            width=0.16, depth=0.18, mat_index=MAT_INDEX_TIMBER,
        )

    # Wide boards lie directly on the rafters, with deliberate narrow gaps.
    board_width = 0.30
    board_gap = 0.055
    board_count = max(3, int(span_y / (board_width + board_gap)))
    for i in range(board_count):
        ty = roof_y0 + (i + 0.5) * span_y / board_count
        for side, eave_x in ((-1.0, left_eave), (1.0, right_eave)):
            timber_box(
                bm, size=(slope_len + 0.12, board_width, 0.10),
                location=((ridge_x + eave_x) * 0.5, ty,
                          (ridge_z + eave_z) * 0.5 + 0.085),
                rotation=(0.0, side * pitch, 0.0),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.008, long_axis=0,
            )


def _hajfin_roof_props(props):
    global _HAJFIN_ROOF_PROPS
    _HAJFIN_ROOF_PROPS = props


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

def _build_curved_bone_spine(bm, x, y, z, height=1.0, base_radius=0.14, rot_z=0.0, sweep_y=-0.25):
    """Builds a smooth, volumetric sculpted bone tusk / spine with graceful backward curve and oval cross section."""
    num_rings = 7
    num_segs = 8
    rings = []
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    for ri in range(num_rings):
        t = ri / (num_rings - 1)
        r = base_radius * (1.0 - t * 0.88)
        cz = z + t * height
        cy = y + (t ** 1.6) * sweep_y
        ring = []
        for si in range(num_segs):
            ang = si * (2.0 * math.pi / num_segs)
            p_local = Vector((math.cos(ang) * r, math.sin(ang) * (r * 0.75), 0.0))
            p_rot = rot_mat @ p_local
            ring.append(bm.verts.new(Vector((x + p_rot.x, cy + p_rot.y, cz))))
        rings.append(ring)

    for ri in range(num_rings - 1):
        r0 = rings[ri]
        r1 = rings[ri + 1]
        for si in range(num_segs):
            si_next = (si + 1) % num_segs
            f = bm.faces.new([r0[si], r0[si_next], r1[si_next], r1[si]])
            f.material_index = MAT_INDEX_BONE
            f.tag = True

    tip_z = z + height + 0.04
    tip_y = y + sweep_y
    v_tip = bm.verts.new(Vector((x, tip_y, tip_z)))
    r_top = rings[-1]
    for si in range(num_segs):
        si_next = (si + 1) % num_segs
        f = bm.faces.new([v_tip, r_top[si], r_top[si_next]])
        f.material_index = MAT_INDEX_BONE
        f.tag = True

def _build_railing_segment(bm, x0, x1, y0, y1, z_base, height=1.0):
    """Build a clean shared guard rail around a Hajfin stairwell."""
    build_railing(
        bm, (x0, y0), (x1, y1), z_base, height=height,
        rail_mat=MAT_INDEX_TIMBER, baluster_mat=MAT_INDEX_TIMBER,
        post_spacing=1.60, baluster_spacing=0.28,
        braces=False, jankiness=0.06, has_sill=True,
    )


def _build_hajfin_interior_staircase(bm, x0, y0, z0, x1, y1, z1, width=1.60, with_railing=True):
    """Build a Hajfin stair flight using the shared clean straight staircase."""
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    run_len = math.hypot(dx, dy)
    if run_len < 0.5 or dz <= 0.05:
        return
    if abs(dx) > abs(dy):
        build_straight_staircase(
            bm, (x0, y0, z0), z1,
            stair_width=width, stair_depth=run_len,
            num_steps=max(10, int(dz / 0.22)),
            axis='X', direction_x=1 if dx >= 0 else -1,
            has_rail_left=with_railing, has_rail_right=False,
        )
    else:
        build_straight_staircase(
            bm, (x0, y0, z0), z1,
            stair_width=width, stair_depth=run_len,
            num_steps=max(10, int(dz / 0.22)),
            axis='Y', direction_y=1 if dy >= 0 else -1,
            has_rail_left=with_railing, has_rail_right=False,
        )


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
                create_box(bm, (0.24, stair_y0 - y0, 0.28), (jx, jy, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_TIMBER)
            if stair_y1 < y1:
                jy = (stair_y1 + y1) * 0.5
                create_box(bm, (0.24, y1 - stair_y1, 0.28), (jx, jy, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_TIMBER)
        else:
            create_box(bm, (0.24, (y1 - y0), 0.28), (jx, (y0 + y1) * 0.5, z_floor - slab_th - 0.14), mat_index=MAT_INDEX_TIMBER)

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


def _build_chunky_corner_column(bm, x, y, z0, z1, size=0.42, extend_top=0.0, with_spikes=False):
    """Oversized square timber column supporting eaves cleanly with iron brackets and optional spikes."""
    col_h = (z1 - z0) + max(0.0, extend_top)
    cz = z0 + col_h * 0.5
    # Main column (uses heavy structural timber with vertical grain)
    create_box(bm, (size, size, col_h), (x, y, cz), mat_index=MAT_INDEX_TIMBER)

    # Beveled chisel pyramid cap only when extending above roof eave
    if extend_top > 0.05:
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

    # Protruding triangular iron spikes driven into the timber (optional)
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
    """Builds a solid timber wall with a massive, weather-tight door opening and 3D predatory shark jaw arch.
    Features:
    - Clear walkthrough width >= 2.40m and clear walkthrough height >= 3.60m (scaled for 3m tall characters).
    - Doorframe sits centered in the middle of the wall thickness (y_off = 0.0), wrapping both exterior and interior.
    - Pointed header wall panel matching the shark jaw arch apex: zero raw edges, zero gaps.
    - Left and right walls are solid, continuous vertical-grain panels meeting the door opening cleanly.
    - Nothing sticks out into the walkthrough opening (zero obstructing teeth/spikes).
    - Heavy timber threshold sill beam at floor level."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    door_w = max(2.40, float(door_w))
    avail_h = z1 - z0
    door_h = max(3.60, min(float(door_h), avail_h * 0.90))
    d_half_w = door_w * 0.5
    z_spring = min(door_h * 0.78, 3.40, avail_h * 0.75)

    def _add_local_box(sx, sy, sz, local_x, local_z, mat_idx, is_wall=False):
        local_pos = Vector((local_x, 0.0, local_z))
        w_pos = rot_mat @ local_pos + Vector((door_cx, y, 0.0))
        create_box(bm, (sx, sy, sz), (w_pos.x, w_pos.y, w_pos.z),
                   rotation=(0, 0, rot_z), mat_index=mat_idx, is_wall=is_wall)

    # 1. Left Wall Panel (Solid continuous vertical plank siding from x0 to left door jamb)
    local_x0 = x0 - door_cx
    left_w = -d_half_w - local_x0
    if left_w > 0.02:
        _add_local_box(left_w, wall_th, z1 - z0, local_x0 + left_w * 0.5, z0 + (z1 - z0) * 0.5,
                       MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 2. Right Wall Panel (Solid continuous vertical plank siding from right door jamb to x1)
    local_x1 = x1 - door_cx
    right_w = local_x1 - d_half_w
    if right_w > 0.02:
        _add_local_box(right_w, wall_th, z1 - z0, d_half_w + right_w * 0.5, z0 + (z1 - z0) * 0.5,
                       MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Header Wall Panel above arch with pointed bottom matching the shark jaw arch apex
    if z1 > z0 + door_h:
        uv_layer = bm.loops.layers.uv.verify()
        v_f, v_b = [], []
        for ly, v_list in ((-wall_th * 0.5, v_f), (wall_th * 0.5, v_b)):
            pts = [
                (-d_half_w, ly, z0 + z_spring),
                (0.0, ly, z0 + door_h),
                (d_half_w, ly, z0 + z_spring),
                (d_half_w, ly, z1),
                (-d_half_w, ly, z1),
            ]
            for p in pts:
                w_pt = rot_mat @ Vector(p) + Vector((door_cx, y, 0.0))
                v_list.append(bm.verts.new(w_pt))

        f_front = bm.faces.new([v_f[0], v_f[1], v_f[2], v_f[3], v_f[4]])
        f_front.material_index = MAT_INDEX_DRIFTWOOD
        f_front.tag = True

        f_back = bm.faces.new([v_b[4], v_b[3], v_b[2], v_b[1], v_b[0]])
        f_back.material_index = MAT_INDEX_DRIFTWOOD
        f_back.tag = True

        f_top = bm.faces.new([v_f[4], v_f[3], v_b[3], v_b[4]])
        f_top.material_index = MAT_INDEX_DRIFTWOOD
        f_top.tag = True

        f_sL = bm.faces.new([v_f[0], v_b[0], v_b[1], v_f[1]])
        f_sL.material_index = MAT_INDEX_TIMBER
        f_sL.tag = True

        f_sR = bm.faces.new([v_f[1], v_b[1], v_b[2], v_f[2]])
        f_sR.material_index = MAT_INDEX_TIMBER
        f_sR.tag = True

        for f in (f_front, f_back):
            for loop in f.loops:
                lx = loop.vert.co.x
                lz = loop.vert.co.z
                loop[uv_layer].uv = Vector((lx * 0.18, lz * 0.18))

    # 4. Heavy Structural Timber Threshold Sill Beam under Doorway
    sill_w = door_w + 0.60
    _add_local_box(sill_w, wall_th + 0.24, 0.16, 0.0, z0 + 0.08, MAT_INDEX_TIMBER)

    # 4b. Square structural jambs behind the jaw.  The bone arch is decorative;
    # these continuous posts define the actual opening and keep the frame
    # precise when the door dimensions change.
    jamb_h = max(0.20, z_spring - z0)
    jamb_w = min(0.34, max(0.22, door_w * 0.12))
    for jamb_x in (-d_half_w - jamb_w * 0.16, d_half_w + jamb_w * 0.16):
        _add_local_box(
            jamb_w, wall_th + 0.20, jamb_h,
            jamb_x, z0 + jamb_h * 0.5,
            MAT_INDEX_TIMBER,
        )
    create_beveled_box(
        bm,
        size=(door_w + jamb_w * 1.8, wall_th + 0.20, 0.22),
        location=(door_cx, y, z0 + z_spring + 0.08),
        rotation=(0.0, 0.0, rot_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.035,
    )

    # 5. Optional Recessed Door Leaf (ONLY if include_leaf is True)
    if include_leaf:
        _add_local_box(door_w * 0.94, 0.08, z_spring * 0.96,
                       0.0, z0 + z_spring * 0.48, MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 6. Unified 3D Shark Jaw Bone Frame centered in the middle of the wall (y_off = 0.0)
    _build_shark_jaw_arch(bm, door_cx, y, z0, rot_z=rot_z,
                          width=door_w, height=door_h, wall_th=wall_th)


def _build_shark_jaw_arch(bm, cx, cy, cz, rot_z=0.0, width=2.40, height=3.80, wall_th=0.26, rot_matrix=None):
    """Exaggerated, beefy 3D predatory shark jaw arch framing the door opening.
    Sits centered in the middle of the wall (y_off = 0.0), wrapping both exterior and interior
    with zero cut edges showing, zero obstructing spikes, and generous clearance for 3m tall characters."""
    if rot_matrix is not None:
        rot_mat = rot_matrix
    else:
        rot_mat = Matrix.Rotation(rot_z, 4, 'Z')

    d_half_w = width * 0.5
    # Keep the decorative jaw on top of the structural sill instead of
    # embedding its base cap through the sill and floor.
    base_lift = 0.18
    base_z = cz + base_lift
    z_spring = min(height * 0.78, 3.40)  # Upright jamb height (3.4m clear!)
    bone_rad = 0.32  # Sturdy, exaggerated, beefy bone cross-section
    y_off = 0.0

    num_segs = 8  # 8-sided octagonal cross section for the bone tube
    uv_layer = bm.loops.layers.uv.verify()

    # Build one continuous centreline from the left foot through the crown to
    # the right foot. A single ring sequence gives the apex one clean mitre
    # instead of two independent legs plus a loose bridge piece.
    num_side_steps = 7
    spine_pts = []
    for side_sgn in (-1.0, 1.0):
        side_pts = []
        for si in range(num_side_steps):
            t = si / (num_side_steps - 1)
            if t <= 0.45:
                st = t / 0.45
                cur_z = base_lift + st * (z_spring - base_lift)
                cur_x = side_sgn * (d_half_w + bone_rad * 0.55)
            else:
                st = (t - 0.45) / 0.55
                cur_z = z_spring + st * (height - z_spring)
                cur_x = side_sgn * ((d_half_w + bone_rad * 0.55) * (1.0 - st ** 1.30))
            side_pts.append(Vector((cur_x, y_off, cur_z)))
        spine_pts.extend(side_pts if side_sgn < 0 else reversed(side_pts[:-1]))

    rings = []
    for si, point in enumerate(spine_pts):
        if si == 0:
            tangent = spine_pts[1] - point
        elif si == len(spine_pts) - 1:
            tangent = point - spine_pts[si - 1]
        else:
            tangent = spine_pts[si + 1] - spine_pts[si - 1]
        tangent.normalize()
        norm_y = Vector((0.0, 1.0, 0.0))
        norm_x = tangent.cross(norm_y).normalized()
        norm_y = norm_x.cross(tangent).normalized()
        t = min(si, len(spine_pts) - 1 - si) / max(1, num_side_steps - 1)
        radius = bone_rad * (1.25 - 0.35 * min(1.0, t))
        ring = []
        for j in range(num_segs):
            ang = j * (2.0 * math.pi / num_segs)
            offset = norm_x * (math.cos(ang) * radius) + norm_y * (math.sin(ang) * radius * 1.18)
            world_pt = rot_mat @ (point + offset) + Vector((cx, cy, cz))
            if si in (0, len(spine_pts) - 1) and world_pt.z < base_z:
                world_pt.z = base_z
            ring.append(bm.verts.new(world_pt))
        rings.append(ring)

    for si in range(len(rings) - 1):
        for j in range(num_segs):
            j_next = (j + 1) % num_segs
            face = bm.faces.new((rings[si][j], rings[si][j_next],
                                 rings[si + 1][j_next], rings[si + 1][j]))
            face.material_index = MAT_INDEX_BONE
            face.tag = True
            u0 = si / max(1, len(rings) - 1)
            u1 = (si + 1) / max(1, len(rings) - 1)
            v0 = j / num_segs
            v1 = (j + 1) / num_segs
            for loop in face.loops:
                if loop.vert == rings[si][j]:
                    loop[uv_layer].uv = Vector((u0, v0))
                elif loop.vert == rings[si][j_next]:
                    loop[uv_layer].uv = Vector((u0, v1))
                elif loop.vert == rings[si + 1][j_next]:
                    loop[uv_layer].uv = Vector((u1, v1))
                else:
                    loop[uv_layer].uv = Vector((u1, v0))
    for ring in (rings[0], rings[-1]):
        face = bm.faces.new(list(reversed(ring)))
        face.material_index = MAT_INDEX_BONE
        face.tag = True
        for j, loop in enumerate(face.loops):
            loop[uv_layer].uv = Vector((0.0, j / num_segs))


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
    matching the lower wall siding orientation and continuous grain with zero stepped cuts."""
    roof_style = getattr(_HAJFIN_ROOF_PROPS, 'roof_style', 'SHINGLES') if _HAJFIN_ROOF_PROPS is not None else 'SHINGLES'
    allow_bone_shop_gables = (
        _HAJFIN_ROOF_PROPS is not None
        and getattr(_HAJFIN_ROOF_PROPS, 'hajfin_style', '') == 'BONE_SHOP'
    )
    if roof_style in ('SWAY', 'TARP', 'PLANKS', 'FLAT') and not allow_bone_shop_gables:
        return
    min_x = min(x0, x1)
    max_x = max(x0, x1)
    mx = (min_x + max_x) * 0.5
    half_th = wall_th * 0.5
    uv_layer = bm.loops.layers.uv.verify()

    v_fl = bm.verts.new(Vector((min_x, y - half_th, z_eave)))
    v_fr = bm.verts.new(Vector((max_x, y - half_th, z_eave)))
    v_fp = bm.verts.new(Vector((mx, y - half_th, z_peak)))

    v_bl = bm.verts.new(Vector((min_x, y + half_th, z_eave)))
    v_br = bm.verts.new(Vector((max_x, y + half_th, z_eave)))
    v_bp = bm.verts.new(Vector((mx, y + half_th, z_peak)))

    f_front = bm.faces.new([v_fl, v_fr, v_fp])
    f_front.material_index = MAT_INDEX_DRIFTWOOD
    f_front.tag = True

    f_back = bm.faces.new([v_bp, v_br, v_bl])
    f_back.material_index = MAT_INDEX_DRIFTWOOD
    f_back.tag = True

    f_bot = bm.faces.new([v_fl, v_bl, v_br, v_fr])
    f_bot.material_index = MAT_INDEX_DRIFTWOOD
    f_bot.tag = True

    f_sl = bm.faces.new([v_fl, v_fp, v_bp, v_bl])
    f_sl.material_index = MAT_INDEX_DRIFTWOOD
    f_sl.tag = True

    f_sr = bm.faces.new([v_fr, v_br, v_bp, v_fp])
    f_sr.material_index = MAT_INDEX_DRIFTWOOD
    f_sr.tag = True

    for f in (f_front, f_back):
        for loop in f.loops:
            co = loop.vert.co
            loop[uv_layer].uv = Vector((co.x * 0.18, co.z * 0.18))
    for f in (f_sl, f_sr, f_bot):
        for loop in f.loops:
            co = loop.vert.co
            loop[uv_layer].uv = Vector((co.y * 0.18, co.z * 0.18))

def _build_wall_with_window_x(bm, x0, x1, y, z0, z1, win_cx, win_cz, win_w=0.75, win_h=0.75,
                              wall_th=0.26, facing_north=False):
    """Builds a wall along the X axis (from x0 to x1 at constant y) with a window cutout and frame."""
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5

    # 1. Below Window Wall
    sill_h = (win_cz - w_half_h) - z0
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 2. Above Window Wall
    header_h = z1 - (win_cz + w_half_h)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Left Wall Segment
    left_w = (win_cx - w_half_w) - x0
    if left_w > 0.05:
        create_box(bm, (left_w, wall_th, z1 - z0), (x0 + left_w * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 4. Right Wall Segment
    right_w = x1 - (win_cx + w_half_w)
    if right_w > 0.05:
        create_box(bm, (right_w, wall_th, z1 - z0), (win_cx + w_half_w + right_w * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 5. Window Frame & Iron Bars inside opening
    frame_y = y + (wall_th * 0.5 if facing_north else -wall_th * 0.5)
    rot_z = math.pi if facing_north else 0.0
    _build_bone_window(bm, win_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h, wall_th=wall_th)


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
        create_box(bm, (w_left, wall_th, z1 - z0), (x0 + w_left * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 2. Window 1 sill & header
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win1_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win1_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Center segment between windows
    w_mid = (win2_cx - w_half_w) - (win1_cx + w_half_w)
    if w_mid > 0.05:
        create_box(bm, (w_mid, wall_th, z1 - z0), (win1_cx + w_half_w + w_mid * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 4. Window 2 sill & header
    if sill_h > 0.05:
        create_box(bm, (win_w, wall_th, sill_h), (win2_cx, y, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)
    if header_h > 0.05:
        create_box(bm, (win_w, wall_th, header_h), (win2_cx, y, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 5. Right of window 2
    w_right = x1 - (win2_cx + w_half_w)
    if w_right > 0.05:
        create_box(bm, (w_right, wall_th, z1 - z0), (win2_cx + w_half_w + w_right * 0.5, y, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 6. Bone windows
    frame_y = y + (wall_th * 0.5 if facing_north else -wall_th * 0.5)
    rot_z = math.pi if facing_north else 0.0
    _build_bone_window(bm, win1_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h, wall_th=wall_th)
    _build_bone_window(bm, win2_cx, frame_y, win_cz, rot_z=rot_z, w=win_w, h=win_h, wall_th=wall_th)


def _build_wall_with_window_y(bm, y0, y1, x, z0, z1, win_cy, win_cz, win_w=0.75, win_h=0.75,
                              wall_th=0.26, facing_east=False):
    """Builds a wall along the Y axis (from y0 to y1 at constant x) with a window cutout and frame."""
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5

    # 1. Below Window Wall
    sill_h = (win_cz - w_half_h) - z0
    if sill_h > 0.05:
        create_box(bm, (wall_th, win_w, sill_h), (x, win_cy, z0 + sill_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 2. Above Window Wall
    header_h = z1 - (win_cz + w_half_h)
    if header_h > 0.05:
        create_box(bm, (wall_th, win_w, header_h), (x, win_cy, win_cz + w_half_h + header_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3. Front Wall Segment (smaller y)
    front_w = (win_cy - w_half_w) - y0
    if front_w > 0.05:
        create_box(bm, (wall_th, front_w, z1 - z0), (x, y0 + front_w * 0.5, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 4. Back Wall Segment (larger y)
    back_w = y1 - (win_cy + w_half_w)
    if back_w > 0.05:
        create_box(bm, (wall_th, back_w, z1 - z0), (x, win_cy + w_half_w + back_w * 0.5, z0 + (z1 - z0) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 5. Window Frame & Iron Bars inside opening
    frame_x = x + (wall_th * 0.5 if facing_east else -wall_th * 0.5)
    rot_z = math.pi * 0.5 if facing_east else -math.pi * 0.5
    _build_bone_window(bm, frame_x, win_cy, win_cz, rot_z=rot_z, w=win_w, h=win_h, wall_th=wall_th)


def _build_bone_window(bm, x, y, z, rot_z=0.0, pitch=0.0, w=0.75, h=0.75, wall_th=0.26, rot_matrix=None):
    """Complete, weather-tight stylized window assembly for Hajfin buildings.
    Fully covers and seals the entire wall cutout hole on BOTH exterior and interior:
    - Full-depth timber jamb liners encasing the cutout through the entire wall thickness.
    - Prominent carved bone exterior casing frame overlapping the wall planks by >= 15cm on all sides.
    - Interior timber window casing trim framing the opening inside the room.
    - Vertical iron security bars and recessed glass pane.
    - Zero visible cut gaps, zero see-through cracks, zero unfinished wall guts."""
    if rot_matrix is not None:
        rot_mat = rot_matrix
    else:
        rot_mat = Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'X')
    hw = w * 0.5
    hh = h * 0.5

    tr_origin = Matrix.Translation(Vector((x, y, z))) @ rot_mat

    def _add_local_box(size, local_pos, mat_idx, is_wall=False):
        create_box(bm, size, local_pos,
                   transform_matrix=tr_origin,
                   mat_index=mat_idx, is_wall=is_wall)

    # 1. Full-Depth Cutout Liners (Encase the wall opening through the full wall thickness)
    liner_th = 0.05
    liner_depth = wall_th + 0.04
    liner_y = wall_th * 0.5

    # Bottom sill liner
    _add_local_box((w, liner_depth, liner_th), (0.0, liner_y, -hh + liner_th * 0.5), MAT_INDEX_TIMBER)
    # Top lintel liner
    _add_local_box((w, liner_depth, liner_th), (0.0, liner_y, hh - liner_th * 0.5), MAT_INDEX_TIMBER)
    # Left jamb liner
    _add_local_box((liner_th, liner_depth, h - liner_th * 2.0), (-hw + liner_th * 0.5, liner_y, 0.0), MAT_INDEX_TIMBER)
    # Right jamb liner
    _add_local_box((liner_th, liner_depth, h - liner_th * 2.0), (hw - liner_th * 0.5, liner_y, 0.0), MAT_INDEX_TIMBER)

    # 2. Exterior Carved Bone Casing Frame (Firmly overlaps the wood wall planks on all sides)
    casing_w = 0.16
    casing_th = 0.065
    ext_y = -casing_th * 0.5

    # Bottom sill casing (extends slightly past jambs with decorative fantasy horn ears)
    sill_w = w + casing_w * 2.0 + 0.12
    _add_local_box((sill_w, casing_th, casing_w), (0.0, ext_y, -hh - casing_w * 0.5 + 0.02), MAT_INDEX_BONE)

    # Top lintel casing
    lintel_w = w + casing_w * 2.0 + 0.12
    _add_local_box((lintel_w, casing_th, casing_w), (0.0, ext_y, hh + casing_w * 0.5 - 0.02), MAT_INDEX_BONE)

    # Left and Right side jamb casings
    jamb_h = h + casing_w * 0.6
    _add_local_box((casing_w, casing_th, jamb_h), (-hw - casing_w * 0.5 + 0.02, ext_y, 0.0), MAT_INDEX_BONE)
    _add_local_box((casing_w, casing_th, jamb_h), (hw + casing_w * 0.5 - 0.02, ext_y, 0.0), MAT_INDEX_BONE)

    # 4 Carved bone knuckle condyles at exterior frame corners
    for sgn_cx in (-1.0, 1.0):
        for sgn_cz in (-1.0, 1.0):
            corner_x = sgn_cx * (hw + casing_w * 0.5)
            corner_z = sgn_cz * (hh + casing_w * 0.5)
            _add_local_box((0.10, casing_th + 0.02, 0.10),
                           (corner_x, ext_y - 0.01, corner_z), MAT_INDEX_BONE)

    # 3. Interior Timber Window Trim (Covers the cutout on the INSIDE room face)
    in_casing_w = 0.14
    in_casing_th = 0.045
    in_y = wall_th + in_casing_th * 0.5

    # Interior bottom sill apron
    _add_local_box((w + in_casing_w * 2.0 + 0.08, in_casing_th, in_casing_w),
                   (0.0, in_y, -hh - in_casing_w * 0.5 + 0.02), MAT_INDEX_TIMBER)
    # Interior top lintel casing
    _add_local_box((w + in_casing_w * 2.0 + 0.08, in_casing_th, in_casing_w),
                   (0.0, in_y, hh + in_casing_w * 0.5 - 0.02), MAT_INDEX_TIMBER)
    # Interior left & right jamb casings
    _add_local_box((in_casing_w, in_casing_th, h + 0.04),
                   (-hw - in_casing_w * 0.5 + 0.02, in_y, 0.0), MAT_INDEX_TIMBER)
    _add_local_box((in_casing_w, in_casing_th, h + 0.04),
                   (hw + in_casing_w * 0.5 - 0.02, in_y, 0.0), MAT_INDEX_TIMBER)

    # 4. Iron Security Bars & Weather-Sealed Glass Pane
    num_bars = 3
    bar_clear_h = h - liner_th * 2.0
    for i in range(num_bars):
        bx = -w * 0.28 + i * (w * 0.56 / max(1, num_bars - 1))
        _add_local_box((0.035, 0.035, bar_clear_h), (bx, 0.02, 0.0), MAT_INDEX_IRON)

    # Recessed glass pane firmly seated inside the liner frame
    _add_local_box((w - liner_th * 0.8, 0.03, h - liner_th * 0.8), (0.0, 0.06, 0.0), MAT_INDEX_GLASS)


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


def _build_continuous_bone_arc(bm, points, base_radius=0.20, mat_index=MAT_INDEX_BONE):
    """Create one uninterrupted tapered bone tube along a curved centreline."""
    if len(points) < 2:
        return
    sides = 10
    rings = []
    for i, point in enumerate(points):
        tangent = (points[min(i + 1, len(points) - 1)] -
                   points[max(0, i - 1)]).normalized()
        radial = Vector((point.x, point.y, 0.0))
        if radial.length < 1e-5:
            radial = Vector((1.0, 0.0, 0.0))
        radial.normalize()
        across = tangent.cross(radial).normalized()
        radius = base_radius * (1.0 - 0.30 * i / max(1, len(points) - 1))
        rings.append([
            bm.verts.new(point + radial * (math.cos(a) * radius) +
                         across * (math.sin(a) * radius))
            for a in (2.0 * math.pi * j / sides for j in range(sides))
        ])
    for ri in range(len(rings) - 1):
        for si in range(sides):
            bm.faces.new((rings[ri][si], rings[ri][(si + 1) % sides],
                          rings[ri + 1][(si + 1) % sides], rings[ri + 1][si])).material_index = mat_index
    bm.faces.new(list(reversed(rings[0]))).material_index = mat_index
    bm.faces.new(rings[-1]).material_index = mat_index


def _build_whale_rib_tunnel_entrance(bm, entrance_x, entrance_y, z0, rot_z=0.0,
                                     length=3.8, height=4.4, width=3.6, num_pairs=5):
    """Projecting whale rib cage tunnel entrance extending OUTWARD from the main door.
    Features elevated solid reef-stone foundation plinth, wide ceremonial access steps,
    raised timber boardwalk platform, continuous curved bone ribs connecting cleanly,
    rope lashings, and flanking tribal totem posts."""
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
        # The curb sits on the deck top; its former center left 9 cm of
        # coplanar/intersecting timber inside the floor slab.
        timber_box(
            bm, (0.26, bw_len, 0.22), (cx_pos, bw_cy, z0 + 0.27),
            rotation=(0, 0, rot_z), mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012, long_axis=1,
        )

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
                                 fin_scale=1.5, num_ridge_teeth=8,
                                 overhang_x_left=None, overhang_x_right=None):
    """Builds an optimized, 100% weather-tight gable roof with textured bone scale shingles
    pointing downward toward the eaves, heavy timber verge bargeboards, ridge beam, and dorsal fin crest.
    Supports asymmetric left/right overhangs for multi-tier roofs meeting interior/tower walls."""
    if _build_hajfin_roof_variant(bm, x0, x1, y0, y1, eave_z, peak_h,
                                  overhang_x, overhang_y):
        return
    mx = (x0 + x1) * 0.5
    ov_xl = overhang_x if overhang_x_left is None else overhang_x_left
    ov_xr = overhang_x if overhang_x_right is None else overhang_x_right
    span_y = (y1 - y0) + overhang_y * 2
    my = (y0 + y1) * 0.5
    peak_z = eave_z + peak_h

    # 1. Solid Heavy Timber Ridge Beam
    ridge_len = span_y + 0.4
    create_box(bm, (0.36, ridge_len, 0.38), (mx, my, peak_z), mat_index=MAT_INDEX_TIMBER)

    # 2. Solid Roof Deck Slopes with Downward Bone Scale Texture Mapping
    # Left slope (x < mx) terminates at x0 - ov_xl
    _build_roof_slope_slab(bm, x_peak=mx, x_eave=x0 - ov_xl,
                           y0=y0 - overhang_y, y1=y1 + overhang_y,
                           z_peak=peak_z, z_eave=eave_z, slab_th=0.14, u_scale=0.12, v_scale=0.14)
    # Right slope (x > mx) terminates at x1 + ov_xr
    _build_roof_slope_slab(bm, x_peak=mx, x_eave=x1 + ov_xr,
                           y0=y0 - overhang_y, y1=y1 + overhang_y,
                           z_peak=peak_z, z_eave=eave_z, slab_th=0.14, u_scale=0.12, v_scale=0.14)

    # 3. Heavy Timber Verge Bargeboards on Front & Rear Gable Slopes
    for gy in (y0 - overhang_y, y1 + overhang_y):
        p_peak = (mx, gy, peak_z)
        if ov_xl > -0.05:
            p_eave_l = (x0 - ov_xl, gy, eave_z)
            _create_oriented_beam(bm, p_peak, p_eave_l, width=0.24, depth=0.24, mat_index=MAT_INDEX_TIMBER)
        if ov_xr > -0.05:
            p_eave_r = (x1 + ov_xr, gy, eave_z)
            _create_oriented_beam(bm, p_peak, p_eave_r, width=0.24, depth=0.24, mat_index=MAT_INDEX_TIMBER)

    # 4. Ridge Dorsal Fin Bone & Jagged Teeth Crest
    _build_ridge_crest_fin_and_spines(bm, mx, y0 - overhang_y, y1 + overhang_y,
                                      peak_z + 0.18, fin_scale=fin_scale, num_teeth=num_ridge_teeth)


def _build_shark_dorsal_fin(bm, cx, cy, cz, height=1.8, length=1.3, thickness=0.22, rot_z=0.0):
    """Volumetric sculpted bone shark dorsal fin standing upright on roof ridge/apex."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Smooth curved aerodynamic foil profile with natural curvature
    profile = [
        Vector((-length * 0.50, 0.0, 0.0)),
        Vector((-length * 0.42, 0.0, height * 0.22)),
        Vector((-length * 0.30, 0.0, height * 0.48)),
        Vector((-length * 0.12, 0.0, height * 0.76)),
        Vector((length * 0.10, 0.0, height * 0.98)),
        Vector((length * 0.18, 0.0, height)),
        Vector((length * 0.16, 0.0, height * 0.82)),
        Vector((length * 0.12, 0.0, height * 0.65)),
        Vector((length * 0.20, 0.0, height * 0.42)),
        Vector((length * 0.32, 0.0, height * 0.22)),
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
    f_l.tag = True
    f_r = bm.faces.new(list(reversed(v_right)))
    f_r.material_index = MAT_INDEX_BONE
    f_r.tag = True

    n = len(profile)
    for i in range(n):
        nxt = (i + 1) % n
        f_side = bm.faces.new([v_left[i], v_left[nxt], v_right[nxt], v_right[i]])
        f_side.material_index = MAT_INDEX_BONE
        f_side.tag = True


def _build_ridge_crest_fin_and_spines(bm, rx, y_start, y_end, rz, fin_scale=1.5, num_teeth=8):
    """Crown of giant curved shark dorsal fin and smooth sculpted curved bone spines along the roof peak."""
    fin_y = y_start + 0.65
    fin_h = 1.45 * fin_scale
    fin_base_w = 1.15 * fin_scale

    # Primary giant volumetric dorsal fin bone near front gable (facing along ridge Y)
    _build_shark_dorsal_fin(bm, rx, fin_y, rz, height=fin_h, length=fin_base_w, thickness=0.22, rot_z=math.pi * 0.5)

    # Row of smooth curved bone spines running down the ridge (zero 5-segment needle cones)
    spine_span = (y_end - (fin_y + fin_base_w * 0.6))
    if spine_span > 0.8 and num_teeth > 0:
        dy = spine_span / max(1, num_teeth)
        for i in range(num_teeth):
            ty = (fin_y + fin_base_w * 0.6) + (i + 0.5) * dy
            t_ratio = 1.0 - 0.45 * (i / max(1, num_teeth - 1))
            th = (0.65 + 0.40 * math.sin(i * 1.5)) * t_ratio * fin_scale
            # Smooth curved sculpted ivory tusk / whale rib spine
            _build_curved_bone_spine(bm, rx, ty, rz, height=th,
                                     base_radius=0.14 * t_ratio,
                                     sweep_y=-0.22 * th)


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
    v_tiles = max(0.85, slope_len * 0.14)
    u_repeat = max(2.5, (2.0 * math.pi * radius) * 0.14)

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

    # 2. Tiered Stylized Timber Apex Hub Cap & Iron Strapping
    # Lower octagon timber collar anchoring onto cone peak
    cap_r0 = 0.68
    cap_h0 = 0.26
    create_cylinder(bm, radius=cap_r0, height=cap_h0, segments=8,
                    location=(cx, cy, apex_z + cap_h0 * 0.5), mat_index=MAT_INDEX_TIMBER)

    if fin_scale > 0.05:
        # Upper tapering timber cap hub
        cap_h1 = 0.42
        create_cone(bm, radius1=cap_r0 * 0.88, radius2=0.30, height=cap_h1, segments=8,
                    location=(cx, cy, apex_z + cap_h0 + cap_h1 * 0.5), mat_index=MAT_INDEX_TIMBER)

        # Forged iron collar rings wrapping the apex hub
        create_cylinder(bm, radius=cap_r0 + 0.04, height=0.08, segments=8,
                        location=(cx, cy, apex_z + cap_h0 * 0.70), mat_index=MAT_INDEX_IRON)
        create_cylinder(bm, radius=0.34, height=0.07, segments=8,
                        location=(cx, cy, apex_z + cap_h0 + cap_h1 * 0.90), mat_index=MAT_INDEX_IRON)
    else:
        # Flat weathered timber cap disk with forged iron rim (zero pointy cone / finial)
        create_cylinder(bm, radius=cap_r0 * 0.92, height=0.10, segments=8,
                        location=(cx, cy, apex_z + cap_h0 + 0.05), mat_index=MAT_INDEX_TIMBER)
        create_torus_ring(bm, (cx, cy, apex_z + cap_h0 + 0.05), major_radius=cap_r0 * 0.94,
                          minor_radius=0.03, mat_index=MAT_INDEX_IRON)

    # 3. Apex Cap or Sculpted Predatory Curved Bone Spire Finial
    if fin_scale > 0.05:
        finial_z0 = apex_z + cap_h0 + cap_h1
        spire_h = 1.35 * fin_scale
        num_spire_rings = 7
        r_spire_base = 0.20
        spire_rings = []
        for si in range(num_spire_rings):
            t_sp = si / (num_spire_rings - 1)
            # Gentle tribal backward sweep
            curve_y = 0.24 * (t_sp ** 1.8)
            r_sp = r_spire_base * (1.0 - t_sp * 0.90)
            curr_sz = finial_z0 + t_sp * spire_h
            ring_v = []
            for ri in range(8):
                ang_r = ri * (2.0 * math.pi / 8)
                rx = cx + math.cos(ang_r) * r_sp
                ry = cy + curve_y + math.sin(ang_r) * r_sp
                ring_v.append(bm.verts.new(Vector((rx, ry, curr_sz))))
            spire_rings.append(ring_v)

        for si in range(num_spire_rings - 1):
            rA = spire_rings[si]
            rB = spire_rings[si + 1]
            for ri in range(8):
                ri_next = (ri + 1) % 8
                f_sp = bm.faces.new([rA[ri], rA[ri_next], rB[ri_next], rB[ri]])
                f_sp.material_index = MAT_INDEX_BONE

        # Spire apex tip cap
        tip_v = bm.verts.new(Vector((cx, cy + 0.24, finial_z0 + spire_h + 0.04)))
        top_r = spire_rings[-1]
        for ri in range(8):
            ri_next = (ri + 1) % 8
            f_tip = bm.faces.new([tip_v, top_r[ri], top_r[ri_next]])
            f_tip.material_index = MAT_INDEX_BONE

        # Forged iron strapping collar at bone spire base
        create_cylinder(bm, radius=r_spire_base + 0.035, height=0.10, segments=8,
                        location=(cx, cy, finial_z0 + 0.05), mat_index=MAT_INDEX_IRON)
    else:
        # When fin_scale <= 0.05: Clean capped timber hub with zero pointy cone / finial
        pass


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


def _build_hajfin_bone_shop_table(bm, x, y, z, width=3.8):
    """Simple rough timber display table for heavy scrimshaw and salvaged goods."""
    table_d = 0.78
    table_h = 1.02
    top_th = 0.16
    create_box(
        bm, (width, table_d, top_th),
        (x, y, z + table_h),
        mat_index=MAT_INDEX_TIMBER,
    )
    for lx in (x - width * 0.40, x + width * 0.40):
        create_box(
            bm, (0.18, 0.18, table_h),
            (lx, y - table_d * 0.28, z + table_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
        )
        create_box(
            bm, (0.18, 0.18, table_h),
            (lx, y + table_d * 0.28, z + table_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
        )


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
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.0)

    # 5. Dense Bone Scale Gable Roof
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=7)


def _build_tapered_facet_panel(bm, pb0, pb1, pt0, pt1, n_vec, wall_th,
                               u_start=0.0, v_start=0.0, u_scale=0.18, v_scale=0.18,
                               mat_index=MAT_INDEX_DRIFTWOOD,
                               build_left_cap=False, build_right_cap=False,
                               build_top_cap=True, build_bot_cap=True):
    """Constructs a true planar trapezoidal wall panel with thickness and vertical plank UV unwrapping.
    Guarantees zero twist, zero clipping, zero diagonal stretching, and continuous vertical wood grain."""
    uv_layer = bm.loops.layers.uv.verify()

    ipb0 = pb0 - n_vec * wall_th
    ipb1 = pb1 - n_vec * wall_th
    ipt0 = pt0 - n_vec * wall_th
    ipt1 = pt1 - n_vec * wall_th

    v_pb0 = bm.verts.new(pb0)
    v_pb1 = bm.verts.new(pb1)
    v_pt0 = bm.verts.new(pt0)
    v_pt1 = bm.verts.new(pt1)

    v_ipb0 = bm.verts.new(ipb0)
    v_ipb1 = bm.verts.new(ipb1)
    v_ipt0 = bm.verts.new(ipt0)
    v_ipt1 = bm.verts.new(ipt1)

    # 1. Outer Face
    f_out = bm.faces.new([v_pb0, v_pb1, v_pt1, v_pt0])
    f_out.material_index = mat_index
    f_out.tag = True

    # 2. Inner Face
    f_in = bm.faces.new([v_ipb1, v_ipb0, v_ipt0, v_ipt1])
    f_in.material_index = mat_index
    f_in.tag = True

    # 3. Top and Bottom Caps
    if build_top_cap:
        f_top = bm.faces.new([v_pt0, v_pt1, v_ipt1, v_ipt0])
        f_top.material_index = mat_index
        f_top.tag = True
    if build_bot_cap:
        f_bot = bm.faces.new([v_ipb0, v_ipb1, v_pb1, v_pb0])
        f_bot.material_index = mat_index
        f_bot.tag = True

    # 4. Side Jamb Caps
    if build_left_cap:
        f_left = bm.faces.new([v_ipt0, v_pt0, v_pb0, v_ipb0])
        f_left.material_index = mat_index
        f_left.tag = True
    if build_right_cap:
        f_right = bm.faces.new([v_pt1, v_ipt1, v_ipb1, v_pb1])
        f_right.material_index = mat_index
        f_right.tag = True

    # Calibrated UV Unwrapping: vertical boards running straight along local height
    w_bot = (pb1 - pb0).length
    h_slope = ((pt0 - pb0).length + (pt1 - pb1).length) * 0.5
    u0 = u_start
    u1 = u_start + w_bot * u_scale
    v0 = v_start
    v1 = v_start + h_slope * v_scale

    for loop in f_out.loops:
        if loop.vert == v_pb0: loop[uv_layer].uv = Vector((u0, v0))
        elif loop.vert == v_pb1: loop[uv_layer].uv = Vector((u1, v0))
        elif loop.vert == v_pt1: loop[uv_layer].uv = Vector((u1, v1))
        elif loop.vert == v_pt0: loop[uv_layer].uv = Vector((u0, v1))

    for loop in f_in.loops:
        if loop.vert == v_ipb1: loop[uv_layer].uv = Vector((u0, v0))
        elif loop.vert == v_ipb0: loop[uv_layer].uv = Vector((u1, v0))
        elif loop.vert == v_ipt0: loop[uv_layer].uv = Vector((u1, v1))
        elif loop.vert == v_ipt1: loop[uv_layer].uv = Vector((u0, v1))

    if build_top_cap:
        for loop in f_top.loops:
            loop[uv_layer].uv = Vector((loop.vert.co.x * u_scale, loop.vert.co.y * u_scale))
    if build_bot_cap:
        for loop in f_bot.loops:
            loop[uv_layer].uv = Vector((loop.vert.co.x * u_scale, loop.vert.co.y * u_scale))
    if build_left_cap:
        for loop in f_left.loops:
            loop[uv_layer].uv = Vector((u0, loop.vert.co.z * v_scale))
    if build_right_cap:
        for loop in f_right.loops:
            loop[uv_layer].uv = Vector((u1, loop.vert.co.z * v_scale))


def _build_hajfin_round_hut(bm, props, diameter=10.5, height=4.8, found_h=0.8):
    """The Tapered Round Bone-Scale Hut:
    Scaled for 2-3m tall Hajfin characters with accessible hollow interior.
    8-sided tapered conical timber hut with true planar trapezoidal wall panels, massive perimeter posts
    extending 10m downwards, conical bone-scale roof with solid underlay, tiered timber apex cap and
    sculpted curved bone spire finial, shark jaw door with open walkthrough, and accessible upper mezzanine loft."""
    r_base = diameter * 0.5
    r_top = r_base * 0.82
    z0 = found_h
    z1 = z0 + height
    num_facets = 8
    wall_th = 0.26
    num_fl = max(1, getattr(props, 'num_floors', 1))

    # Corner angles around the perimeter (8 corners)
    theta_corners = [(i - 0.5) * (2.0 * math.pi / num_facets) for i in range(num_facets + 1)]

    # 1. Stilt Pier Foundation & Floor Framing (Zero 10m stone cylinder)
    col_size = 0.44
    for i in range(num_facets):
        thA = theta_corners[i]
        thB = theta_corners[i + 1]
        p_sill0 = Vector((r_base * math.cos(thA), r_base * math.sin(thA), z0 + 0.10))
        p_sill1 = Vector((r_base * math.cos(thB), r_base * math.sin(thB), z0 + 0.10))
        _create_oriented_beam(bm, p_sill0, p_sill1, width=col_size * 0.75, depth=0.24, mat_index=MAT_INDEX_TIMBER)

    # Interior wooden floor slab across circular ground floor
    create_cylinder(bm, radius=r_base * 0.98, height=0.14, segments=num_facets,
                    location=(0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 2. Tapered 8-sided body shell (True planar trapezoidal facets, zero twist, zero clipping)
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), height * 0.82)

    for i in range(num_facets):
        th0 = theta_corners[i]
        th1 = theta_corners[i + 1]

        # Corner positions
        pb0 = Vector((r_base * math.cos(th0), r_base * math.sin(th0), z0))
        pb1 = Vector((r_base * math.cos(th1), r_base * math.sin(th1), z0))
        pt0 = Vector((r_top * math.cos(th0), r_top * math.sin(th0), z1))
        pt1 = Vector((r_top * math.cos(th1), r_top * math.sin(th1), z1))

        mb = (pb0 + pb1) * 0.5
        mt = (pt0 + pt1) * 0.5
        u_vec = (pb1 - pb0).normalized()
        w_vec = (mt - mb).normalized()
        n_vec = u_vec.cross(w_vec).normalized()

        w_base_f = (pb1 - pb0).length
        w_top_f = (pt1 - pt0).length

        if i == 6:
            # SOUTH DOOR FACET (facing South, centered at x=0)
            door_w = min(float(getattr(props, 'door_width', 2.00)), w_top_f * 0.65)
            door_h = min(float(getattr(props, 'door_height', 3.60)), height * 0.78)
            d_half_w = door_w * 0.5
            z_spring = door_h * 0.75

            # Parallel door jambs along facet slope (ZERO inward taper, matching arch legs perfectly)
            sin_pitch = max(0.1, w_vec.z)
            h_door_dist = door_h / sin_pitch
            h_spring_dist = z_spring / sin_pitch
            facet_len = (mt - mb).length

            pb_jL = mb - u_vec * d_half_w
            pb_jR = mb + u_vec * d_half_w
            p_springL = pb_jL + w_vec * h_spring_dist
            p_springR = pb_jR + w_vec * h_spring_dist
            p_apex = mb + w_vec * h_door_dist

            pt_jL = pb_jL + w_vec * facet_len
            pt_jR = pb_jR + w_vec * facet_len

            # 1. Left jamb wall panel
            _build_tapered_facet_panel(bm, pb0, pb_jL, pt0, pt_jL, n_vec, wall_th,
                                       u_start=0.0, build_right_cap=True)

            # 2. Right jamb wall panel
            _build_tapered_facet_panel(bm, pb_jR, pb1, pt_jR, pt1, n_vec, wall_th,
                                       u_start=2.5, build_left_cap=True)

            # 3. Header wall panel above arch with pointed bottom matching the shark jaw arch apex
            v_hf0 = bm.verts.new(p_springL)
            v_hf1 = bm.verts.new(p_apex)
            v_hf2 = bm.verts.new(p_springR)
            v_hf3 = bm.verts.new(pt_jR)
            v_hf4 = bm.verts.new(pt_jL)

            v_hb0 = bm.verts.new(p_springL - n_vec * wall_th)
            v_hb1 = bm.verts.new(p_apex - n_vec * wall_th)
            v_hb2 = bm.verts.new(p_springR - n_vec * wall_th)
            v_hb3 = bm.verts.new(pt_jR - n_vec * wall_th)
            v_hb4 = bm.verts.new(pt_jL - n_vec * wall_th)

            f_hf = bm.faces.new([v_hf0, v_hf1, v_hf2, v_hf3, v_hf4])
            f_hf.material_index = MAT_INDEX_DRIFTWOOD
            f_hf.tag = True

            f_hb = bm.faces.new([v_hb4, v_hb3, v_hb2, v_hb1, v_hb0])
            f_hb.material_index = MAT_INDEX_DRIFTWOOD
            f_hb.tag = True

            f_htop = bm.faces.new([v_hf4, v_hf3, v_hb3, v_hb4])
            f_htop.material_index = MAT_INDEX_DRIFTWOOD
            f_htop.tag = True

            f_hsL = bm.faces.new([v_hf0, v_hb0, v_hb1, v_hf1])
            f_hsL.material_index = MAT_INDEX_TIMBER
            f_hsL.tag = True

            f_hsR = bm.faces.new([v_hf1, v_hb1, v_hb2, v_hf2])
            f_hsR.material_index = MAT_INDEX_TIMBER
            f_hsR.tag = True

            uv_l = bm.loops.layers.uv.verify()
            for f in (f_hf, f_hb):
                for loop in f.loops:
                    v_rel = loop.vert.co - pb0
                    u = v_rel.dot(u_vec) * 0.18
                    v = v_rel.dot(w_vec) * 0.18
                    loop[uv_l].uv = Vector((u, v))

            # Heavy timber threshold sill beam centered at middle of wall thickness
            sill_p = mb - n_vec * (wall_th * 0.5)
            create_box(bm, (door_w + 0.60, wall_th + 0.24, 0.16), (sill_p.x, sill_p.y, z0 + 0.08),
                       mat_index=MAT_INDEX_TIMBER)

            # Continuous 3D Shark Jaw Bone Archway framing opening flush on tilted facet
            p_door_center = mb - n_vec * (wall_th * 0.5)
            r_door_mat = Matrix((
                (u_vec.x, -n_vec.x, w_vec.x, 0.0),
                (u_vec.y, -n_vec.y, w_vec.y, 0.0),
                (u_vec.z, -n_vec.z, w_vec.z, 0.0),
                (0.0,     0.0,      0.0,     1.0)
            ))
            _build_shark_jaw_arch(bm, p_door_center.x, p_door_center.y, z0,
                                  rot_matrix=r_door_mat, width=door_w, height=door_h, wall_th=wall_th)

        elif i in (5, 7):
            # SOUTH-WEST (i=5) and SOUTH-EAST (i=7) FLANK WINDOW FACETS
            win_w = 0.85
            win_h = 0.85
            win_cz = z0 + height * 0.48

            sin_pitch = max(0.1, w_vec.z)
            facet_len = (mt - mb).length
            w_mid = (win_cz - z0) / sin_pitch
            w_bot = max(0.2, w_mid - win_h * 0.5)
            w_top = min(facet_len - 0.2, w_mid + win_h * 0.5)
            t_bot = w_bot / facet_len
            t_top = w_top / facet_len

            # Edge vertices along left and right facet boundaries
            p_edgeL_bot = pb0 * (1.0 - t_bot) + pt0 * t_bot
            p_edgeR_bot = pb1 * (1.0 - t_bot) + pt1 * t_bot
            p_edgeL_top = pb0 * (1.0 - t_top) + pt0 * t_top
            p_edgeR_top = pb1 * (1.0 - t_top) + pt1 * t_top

            # Cutout opening vertices (pure rectangular window hole along u_vec and w_vec)
            u_hw = win_w * 0.5
            p_mid_bot = mb * (1.0 - t_bot) + mt * t_bot
            p_mid_top = mb * (1.0 - t_top) + mt * t_top
            p_win_bl = p_mid_bot - u_vec * u_hw
            p_win_br = p_mid_bot + u_vec * u_hw
            p_win_tl = p_mid_top - u_vec * u_hw
            p_win_tr = p_mid_top + u_vec * u_hw

            # 1. Bottom Sill Wall Panel (Full width below window, capped top sill)
            _build_tapered_facet_panel(bm, pb0, pb1, p_edgeL_bot, p_edgeR_bot, n_vec, wall_th,
                                       u_start=i * 2.8, v_start=0.0, build_top_cap=True)

            # 2. Top Header Wall Panel (Full width above window, capped bottom lintel)
            _build_tapered_facet_panel(bm, p_edgeL_top, p_edgeR_top, pt0, pt1, n_vec, wall_th,
                                       u_start=i * 0.72, v_start=w_top * 0.18, build_bot_cap=True)

            # 3. Left Flank Wall Panel (Left of window cutout, capped right jamb)
            _build_tapered_facet_panel(bm, p_edgeL_bot, p_win_bl, p_edgeL_top, p_win_tl, n_vec, wall_th,
                                       u_start=i * 0.72, v_start=w_bot * 0.18,
                                       build_right_cap=True, build_top_cap=False, build_bot_cap=False)

            # 4. Right Flank Wall Panel (Right of window cutout, capped left jamb)
            u_flank_r = i * 0.72 + (p_win_br - pb0).dot(u_vec) * 0.18
            _build_tapered_facet_panel(bm, p_win_br, p_edgeR_bot, p_win_tr, p_edgeR_top, n_vec, wall_th,
                                       u_start=u_flank_r, v_start=w_bot * 0.18,
                                       build_left_cap=True, build_top_cap=False, build_bot_cap=False)

            # 5. Carved bone window assembly flush in the cutout opening
            p_win_center = (p_win_bl + p_win_br + p_win_tl + p_win_tr) * 0.25
            r_win_mat = Matrix((
                (u_vec.x, -n_vec.x, w_vec.x, 0.0),
                (u_vec.y, -n_vec.y, w_vec.y, 0.0),
                (u_vec.z, -n_vec.z, w_vec.z, 0.0),
                (0.0,     0.0,      0.0,     1.0)
            ))
            _build_bone_window(bm, p_win_center.x, p_win_center.y, p_win_center.z,
                               rot_matrix=r_win_mat, w=win_w, h=win_h, wall_th=wall_th)

        else:
            # SOLID WALL FACETS (i = 0, 1, 2, 3, 4)
            _build_tapered_facet_panel(bm, pb0, pb1, pt0, pt1, n_vec, wall_th,
                                       u_start=i * 2.8)

    # 3. Perimeter Timber Corner Posts at All 8 Vertex Junctions
    col_size = 0.44
    for i in range(num_facets):
        v_ang = theta_corners[i]
        p_b = Vector((math.cos(v_ang) * r_base, math.sin(v_ang) * r_base, z0))
        p_t = Vector((math.cos(v_ang) * r_top, math.sin(v_ang) * r_top, z1))
        p_b_deep = Vector((math.cos(v_ang) * r_base, math.sin(v_ang) * r_base, -10.0))

        # Deep stilt pilings plunging 10m down into water/ground bed (all corners)
        _create_oriented_beam(bm, p_b_deep, p_b, width=col_size, depth=col_size, mat_index=MAT_INDEX_TIMBER)

        # Above ground corner posts on all 8 corners (framing wall facets)
        _create_oriented_beam(bm, p_b, p_t, width=col_size, depth=col_size, mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (col_size + 0.06, col_size + 0.06, 0.24), (p_b.x, p_b.y, z0 + 0.22),
                   mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.06, col_size + 0.06, 0.24), (p_t.x, p_t.y, z1 - 0.15),
                   mat_index=MAT_INDEX_IRON)

    # Horizontal top eave plate beams physically separating wall segments from roof
    for i in range(num_facets):
        thA = theta_corners[i]
        thB = theta_corners[i + 1]
        p_eave0 = Vector((r_top * math.cos(thA), r_top * math.sin(thA), z1 - 0.10))
        p_eave1 = Vector((r_top * math.cos(thB), r_top * math.sin(thB), z1 - 0.10))
        _create_oriented_beam(bm, p_eave0, p_eave1, width=col_size * 0.70, depth=0.22, mat_index=MAT_INDEX_TIMBER)

    # 4. Accessible Mezzanine Loft & Interior Staircase (if num_floors >= 2 or height >= 5.5)
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

    # 5. Conical Bone Scale Roof with Tiered Timber Hub Cap & Forged Iron Boss (No weird bone stuff)
    roof_h = max(3.5, diameter * 0.35)
    _build_bone_scale_roof_conical(bm, 0.0, 0.0, z1, radius=r_top * 1.25, height=roof_h,
                                   fin_scale=0.0, num_spears=0)

    # 8 Heavy Timber Hip Ribs / Rafters separating the roof sectors
    r_eave = r_top * 1.25
    p_peak = Vector((0.0, 0.0, z1 + roof_h + 0.05))
    for i in range(num_facets):
        th_hip = theta_corners[i]
        p_eave = Vector((math.cos(th_hip) * r_eave, math.sin(th_hip) * r_eave, z1))
        _create_oriented_beam(bm, p_eave, p_peak, width=0.22, depth=0.26, mat_index=MAT_INDEX_TIMBER)


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
    matching the wall siding orientation and continuous grain with zero stepped cuts."""
    roof_style = getattr(_HAJFIN_ROOF_PROPS, 'roof_style', 'SHINGLES') if _HAJFIN_ROOF_PROPS is not None else 'SHINGLES'
    allow_bone_shop_gables = (
        _HAJFIN_ROOF_PROPS is not None
        and getattr(_HAJFIN_ROOF_PROPS, 'hajfin_style', '') == 'BONE_SHOP'
    )
    if roof_style in ('SWAY', 'TARP', 'PLANKS', 'FLAT') and not allow_bone_shop_gables:
        return
    min_y = min(y0, y1)
    max_y = max(y0, y1)
    my = (min_y + max_y) * 0.5
    half_th = wall_th * 0.5
    uv_layer = bm.loops.layers.uv.verify()

    v_fl = bm.verts.new(Vector((x - half_th, min_y, z_eave)))
    v_fr = bm.verts.new(Vector((x - half_th, max_y, z_eave)))
    v_fp = bm.verts.new(Vector((x - half_th, my, z_peak)))

    v_bl = bm.verts.new(Vector((x + half_th, min_y, z_eave)))
    v_br = bm.verts.new(Vector((x + half_th, max_y, z_eave)))
    v_bp = bm.verts.new(Vector((x + half_th, my, z_peak)))

    f_front = bm.faces.new([v_fl, v_fr, v_fp])
    f_front.material_index = MAT_INDEX_DRIFTWOOD
    f_front.tag = True

    f_back = bm.faces.new([v_bp, v_br, v_bl])
    f_back.material_index = MAT_INDEX_DRIFTWOOD
    f_back.tag = True

    f_bot = bm.faces.new([v_fl, v_bl, v_br, v_fr])
    f_bot.material_index = MAT_INDEX_DRIFTWOOD
    f_bot.tag = True

    f_sl = bm.faces.new([v_fl, v_fp, v_bp, v_bl])
    f_sl.material_index = MAT_INDEX_DRIFTWOOD
    f_sl.tag = True

    f_sr = bm.faces.new([v_fr, v_br, v_bp, v_fp])
    f_sr.material_index = MAT_INDEX_DRIFTWOOD
    f_sr.tag = True

    for f in (f_front, f_back):
        for loop in f.loops:
            co = loop.vert.co
            loop[uv_layer].uv = Vector((co.y * 0.18, co.z * 0.18))
    for f in (f_sl, f_sr, f_bot):
        for loop in f.loops:
            co = loop.vert.co
            loop[uv_layer].uv = Vector((co.x * 0.18, co.z * 0.18))


def _build_bone_scale_roof_gable_ew(bm, x0, x1, y0, y1, eave_z, peak_h,
                                    overhang_x=0.45, overhang_y=0.45,
                                    fin_scale=1.5, num_ridge_teeth=6):
    """Gable roof whose ridge runs along the X axis (East-West), so the front and back
    faces are sloped roof decks with scalloped bone scales, matching the watchtower concept art."""
    if _build_hajfin_roof_variant(bm, x0, x1, y0, y1, eave_z, peak_h,
                                  overhang_x, overhang_y):
        return
    my = (y0 + y1) * 0.5
    half_span_y = (y1 - y0) * 0.5 + overhang_y
    span_x = (x1 - x0) + overhang_x * 2
    mx = (x0 + x1) * 0.5
    peak_z = eave_z + peak_h

    slope_len = math.hypot(half_span_y, peak_h)
    pitch_angle = math.atan2(peak_h, half_span_y)

    # 1. Heavy Timber Ridge Beam along X
    create_box(bm, (span_x + 0.4, 0.36, 0.38), (mx, my, peak_z), mat_index=MAT_INDEX_TIMBER)

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
            _create_oriented_beam(bm, p_peak, p_eave, width=0.24, depth=0.24, mat_index=MAT_INDEX_TIMBER)

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
        _create_oriented_beam(bm, p0, p1, width=0.42, depth=0.42, mat_index=MAT_INDEX_TIMBER)
        # Deep stilt pilings (extending 10m downwards) for placing tower in deep water / next to piers
        p_deep = (sgn_x * h_bw, sgn_y * h_bd, -10.0)
        _create_oriented_beam(bm, p_deep, p0, width=0.42, depth=0.42, mat_index=MAT_INDEX_TIMBER)

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

    # 5. Access Ladder (Centered on Front, climbing straight into the open platform hatchway)
    lad_w = 0.90
    lad_x = 0.0
    deck_w = tw + 0.80
    deck_d = td + 0.80
    h_dw = deck_w * 0.5
    h_dd = deck_d * 0.5

    hatch_hw = lad_w * 0.65
    hatch_back_y = -h_td + 0.55

    lad_y0 = -h_bd - 0.35
    y_hatch_center = -(h_td + 0.15)
    slope_dy = (y_hatch_center - lad_y0) / max(0.1, stilt_h)
    lad_y1 = y_hatch_center + slope_dy * 1.10

    # Two heavy timber ladder stringers extending above deck to form grab rails:
    for sgn_lad in (-1.0, 1.0):
        lx = lad_x + sgn_lad * (lad_w * 0.5)
        _create_oriented_beam(bm, (lx, lad_y0, 0.0), (lx, lad_y1, stilt_h + 1.10),
                              width=0.14, depth=0.16, mat_index=MAT_INDEX_TIMBER)

    # Ladder rungs spaced vertically up to floor level (none above floor to trip climbers)
    num_rungs = max(6, int(stilt_h / 0.35))
    for i in range(1, num_rungs):
        rz = i * (stilt_h / num_rungs)
        if rz > stilt_h - 0.10:
            continue
        t_lad = rz / (stilt_h + 1.10)
        ry = lad_y0 * (1.0 - t_lad) + lad_y1 * t_lad
        _create_oriented_beam(bm, (lad_x - lad_w * 0.46, ry, rz), (lad_x + lad_w * 0.46, ry, rz),
                              width=0.10, depth=0.12, mat_index=MAT_INDEX_DRIFTWOOD)

    # 6. Elevated Platform Deck with Real Hatchway Opening
    # Perimeter sill joists underneath deck (Front joist is split flanking the hatch opening!)
    w_front_bm = h_dw - hatch_hw
    # Left front sill beam
    create_box(bm, (w_front_bm, 0.30, 0.30),
               ((-h_dw - hatch_hw) * 0.5, -(h_td + 0.15), stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)
    # Right front sill beam
    create_box(bm, (w_front_bm, 0.30, 0.30),
               ((hatch_hw + h_dw) * 0.5, -(h_td + 0.15), stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)
    # Rear perimeter joist
    create_box(bm, (deck_w, 0.30, 0.30), (0.0, h_td + 0.15, stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)
    # Left and right side joists
    for sgn_x in (-1.0, 1.0):
        create_box(bm, (0.30, deck_d, 0.30), (sgn_x * (h_tw + 0.15), 0.0, stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)
    # Transverse header joist behind hatch
    create_box(bm, (hatch_hw * 2.0, 0.22, 0.28), (0.0, hatch_back_y, stilt_h - 0.15), mat_index=MAT_INDEX_TIMBER)

    # Walkable timber floor slabs around hatchway cutout [-hatch_hw, hatch_hw] x [-h_dd, hatch_back_y]
    w_left = (-hatch_hw) - (-h_dw)
    create_box(bm, (w_left, deck_d, 0.16), ((-h_dw - hatch_hw) * 0.5, 0.0, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)
    w_right = h_dw - hatch_hw
    create_box(bm, (w_right, deck_d, 0.16), ((hatch_hw + h_dw) * 0.5, 0.0, stilt_h + 0.08), mat_index=MAT_INDEX_FLOOR)
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
    # Match the gable footprint to the roof eaves so no daylight seam remains
    # between the triangular wall and the sloped roof deck.
    _build_gable_triangle_wall_ew(bm, -h_td - 0.25, h_td + 0.25, -h_tw - 0.25, eave_z, peak_z, wall_th=0.22)
    _build_gable_triangle_wall_ew(bm, -h_td - 0.25, h_td + 0.25, h_tw + 0.25, eave_z, peak_z, wall_th=0.22)

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
    wall_th = 0.26
    story_h = max(height * 0.5, 4.8)
    z1 = z0 + story_h * 2.0
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
    hollow upper room with bone windows and bone-window detailing,
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
    counter_top_z = z0 + counter_h
    open_top_z = counter_top_z + 2.05
    stall_cx = 0.0
    stall_y = -hd + wall_th * 0.5

    # Knee wall below counter
    create_box(bm, (counter_w, wall_th, counter_h),
               (stall_cx, stall_y, z0 + counter_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)
    # Heavy timber base sill beam under knee wall
    create_box(bm, (counter_w + 0.30, wall_th + 0.12, 0.18),
               (stall_cx, stall_y, z0 + 0.09), mat_index=MAT_INDEX_TIMBER)

    # Massive cantilevered trade counter slab protruding forward
    counter_depth = 0.92
    counter_slab_th = 0.18
    # Set the slab's rear edge flush with the exterior face of the wall.
    # The previous center placed 26 cm of timber inside the wall volume.
    counter_cy = -hd - wall_th * 0.5 - counter_depth * 0.5
    create_box(bm, (counter_w + 0.44, counter_depth, counter_slab_th),
               (stall_cx, counter_cy, counter_top_z - counter_slab_th * 0.5), mat_index=MAT_INDEX_TIMBER)

    # 3 heavy diagonal corbel brackets supporting the counter slab underneath
    for sgn_cb in (-1.35, 0.0, 1.35):
        p_corbel_bot = (sgn_cb, -hd + 0.04, z0 + 0.18)
        p_corbel_top = (sgn_cb, -hd - counter_depth * 0.65, counter_top_z - counter_slab_th)
        _create_oriented_beam(bm, p_corbel_bot, p_corbel_top, width=0.16, depth=0.18, mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (0.20, 0.12, 0.12), (sgn_cb, -hd + 0.02, z0 + 0.22), mat_index=MAT_INDEX_IRON)
        create_box(bm, (0.20, 0.12, 0.12), (sgn_cb, -hd - counter_depth * 0.65, counter_top_z - counter_slab_th - 0.04), mat_index=MAT_INDEX_IRON)

    # Thick timber jamb posts flanking the barter window opening
    jamb_w = 0.32
    jamb_d = wall_th + 0.10
    jamb_h = open_top_z - counter_top_z
    for sgn_jp in (-1.0, 1.0):
        jx = sgn_jp * (counter_w * 0.5)
        create_box(bm, (jamb_w, jamb_d, jamb_h + counter_slab_th),
                   (jx, stall_y, counter_top_z - counter_slab_th + (jamb_h + counter_slab_th) * 0.5),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (jamb_w + 0.04, jamb_d + 0.04, 0.16),
                   (jx, stall_y, counter_top_z + 0.15), mat_index=MAT_INDEX_IRON)

    # Heavy lintel header beam spanning across the barter opening
    lintel_h = 0.34
    lintel_w = counter_w + jamb_w * 2.0 + 0.20
    create_box(bm, (lintel_w, jamb_d, lintel_h),
               (stall_cx, stall_y, open_top_z + lintel_h * 0.5), mat_index=MAT_INDEX_TIMBER)

    # Solid wall above header up to z_mid
    h_above = z_mid - (open_top_z + lintel_h)
    if h_above > 0.05:
        create_box(bm, (counter_w, wall_th, h_above),
                   (stall_cx, stall_y, open_top_z + lintel_h + h_above * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD, is_wall=True)

    # 3C. Right wall segment with bone barred window
    r_cx = (counter_w * 0.5 + hw - wall_th) * 0.5
    _build_wall_with_window_x(bm, counter_w * 0.5, hw - wall_th, -hd + wall_th * 0.5, z0, z_mid,
                              win_cx=r_cx, win_cz=z0 + 2.1, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_north=False)

    # Massive Ground Floor Corner Columns
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z_mid - 0.30, size=col_size, extend_top=0.0)

    # 4. Solid Timber Awning Canopy (Framed with rafters, ledger, front fascia, and bargeboards)
    awning_ledger_z = open_top_z + lintel_h + 0.18
    create_box(bm, (lintel_w, 0.22, 0.20),
               (stall_cx, -hd + 0.02, awning_ledger_z), mat_index=MAT_INDEX_TIMBER)

    awning_span_w = counter_w + 1.10
    awning_reach_d = 1.95
    awning_drop_h = 0.65
    front_eave_y = -hd - awning_reach_d
    front_eave_z = awning_ledger_z - awning_drop_h

    # 3 Heavy Sloped Timber Rafter Beams
    raf_xs = (-counter_w * 0.5 - 0.15, 0.0, counter_w * 0.5 + 0.15)
    for rx in raf_xs:
        p_raf_top = (rx, -hd + 0.02, awning_ledger_z)
        p_raf_bot = (rx, front_eave_y, front_eave_z)
        _create_oriented_beam(bm, p_raf_top, p_raf_bot, width=0.18, depth=0.20, mat_index=MAT_INDEX_TIMBER)

    # Sturdy diagonal struts anchored ONLY to solid structural jamb posts flanking the window (zero window clutter)
    for sgn_strut in (-1.0, 1.0):
        strut_base_x = sgn_strut * (counter_w * 0.5 + jamb_w * 0.5)
        strut_raf_x = sgn_strut * (counter_w * 0.5 + 0.15)
        p_strut_wall = (strut_base_x, -hd + 0.02, counter_top_z + 0.35)
        p_strut_raf = (strut_raf_x, front_eave_y * 0.70 + (-hd) * 0.30,
                       front_eave_z * 0.70 + awning_ledger_z * 0.30 - 0.06)
        _create_oriented_beam(bm, p_strut_wall, p_strut_raf, width=0.14, depth=0.14, mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (0.18, 0.12, 0.12), (strut_base_x, -hd + 0.04, counter_top_z + 0.35), mat_index=MAT_INDEX_IRON)

    # Timber knee braces from header lintel beam down to outer rafters
    for sgn_kb in (-1.0, 1.0):
        kb_x = sgn_kb * (counter_w * 0.35)
        p_kb_lintel = (kb_x, -hd + 0.02, open_top_z + lintel_h * 0.5)
        p_kb_raf = (kb_x, front_eave_y * 0.35 + (-hd) * 0.65,
                    front_eave_z * 0.35 + awning_ledger_z * 0.65 - 0.06)
        _create_oriented_beam(bm, p_kb_lintel, p_kb_raf, width=0.12, depth=0.12, mat_index=MAT_INDEX_TIMBER)

    # Front Fascia Beam connecting all rafter tips
    create_box(bm, (awning_span_w + 0.20, 0.18, 0.22),
               (stall_cx, front_eave_y, front_eave_z), mat_index=MAT_INDEX_TIMBER)

    # Weathered Sloped Timber Plank Deck on top of rafters
    slope_len = math.hypot(awning_reach_d, awning_drop_h) + 0.20
    slope_ang = math.atan2(awning_drop_h, awning_reach_d)
    deck_mid_y = -hd - awning_reach_d * 0.5
    deck_mid_z = awning_ledger_z - awning_drop_h * 0.5 + 0.11
    create_box(bm, (awning_span_w, slope_len, 0.12),
               (stall_cx, deck_mid_y, deck_mid_z),
               rotation=(slope_ang, 0.0, 0.0), mat_index=MAT_INDEX_TIMBER)

    # Side Bargeboards capping awning ends
    for sgn_bg in (-1.0, 1.0):
        bg_x = sgn_bg * (awning_span_w * 0.5)
        create_box(bm, (0.08, slope_len, 0.22),
                   (bg_x, deck_mid_y, deck_mid_z),
                   rotation=(slope_ang, 0.0, 0.0), mat_index=MAT_INDEX_TIMBER)

    # Hanging Carved Wooden Trade Signboard: Suspended solidly below front fascia beam
    sign_w = 2.40
    sign_h = 0.60
    sign_th = 0.08
    sign_y = front_eave_y
    sign_top_z = front_eave_z - 0.32
    sign_cz = sign_top_z - sign_h * 0.5

    create_box(bm, (sign_w, sign_th, sign_h), (stall_cx, sign_y, sign_cz), mat_index=MAT_INDEX_TIMBER)
    for sgn_sb in (-sign_w * 0.5 + 0.08, sign_w * 0.5 - 0.08):
        create_box(bm, (0.10, sign_th + 0.02, sign_h), (sgn_sb, sign_y, sign_cz), mat_index=MAT_INDEX_IRON)
    create_box(bm, (1.60, sign_th + 0.03, 0.34), (stall_cx, sign_y, sign_cz), mat_index=MAT_INDEX_BONE)

    # Sturdy forged iron hanging chains connecting fascia beam down to sign
    for sgn_ch in (-sign_w * 0.35, sign_w * 0.35):
        create_cylinder(bm, radius=0.035, height=0.06, segments=6,
                        location=(sgn_ch, front_eave_y, front_eave_z - 0.12), mat_index=MAT_INDEX_IRON)
        chain_len = (front_eave_z - 0.12) - sign_top_z
        create_cylinder(bm, radius=0.022, height=chain_len, segments=6,
                        location=(sgn_ch, front_eave_y, sign_top_z + chain_len * 0.5), mat_index=MAT_INDEX_IRON)
        create_cylinder(bm, radius=0.035, height=0.06, segments=6,
                        location=(sgn_ch, front_eave_y, sign_top_z), mat_index=MAT_INDEX_IRON)

    # Rich Barter Counter Trade Goods (All 100% physically grounded at Z = counter_top_z)
    prop_y = -hd - 0.30

    # 1. Ornamental Scrimshaw Megalodon Tooth in Carved Timber Cradle Stand
    tooth_cx = -1.30
    cradle_h = 0.07
    create_box(bm, (0.34, 0.20, cradle_h), (tooth_cx, prop_y, counter_top_z + cradle_h * 0.5), mat_index=MAT_INDEX_TIMBER)
    for sgn_cr in (-0.14, 0.14):
        create_box(bm, (0.04, 0.21, cradle_h + 0.01), (tooth_cx + sgn_cr, prop_y, counter_top_z + cradle_h * 0.5), mat_index=MAT_INDEX_IRON)
    tooth_h = 0.42
    create_cone(bm, radius1=0.09, radius2=0.012, height=tooth_h, segments=7,
                location=(tooth_cx, prop_y, counter_top_z + cradle_h + tooth_h * 0.5),
                rotation=(-0.05, 0.0, 0.0), mat_index=MAT_INDEX_BONE)

    # 2. Polished Bone Currency Token Stacks
    tokens_cx = -0.75
    create_cylinder(bm, radius=0.08, height=0.15, segments=8,
                    location=(tokens_cx, prop_y + 0.05, counter_top_z + 0.075), mat_index=MAT_INDEX_BONE)
    create_cylinder(bm, radius=0.075, height=0.09, segments=8,
                    location=(tokens_cx + 0.14, prop_y - 0.04, counter_top_z + 0.045), mat_index=MAT_INDEX_BONE)
    create_cylinder(bm, radius=0.07, height=0.05, segments=8,
                    location=(tokens_cx - 0.12, prop_y - 0.04, counter_top_z + 0.025), mat_index=MAT_INDEX_BONE)

    # 3. Carved Bone Merchant Relic Chest with Iron Straps
    chest_cx = -0.15
    chest_w = 0.38
    chest_d = 0.25
    chest_h = 0.20
    create_box(bm, (chest_w, chest_d, chest_h),
               (chest_cx, prop_y, counter_top_z + chest_h * 0.5), mat_index=MAT_INDEX_BONE)
    create_box(bm, (chest_w + 0.015, 0.04, chest_h + 0.015),
               (chest_cx, prop_y, counter_top_z + chest_h * 0.5), mat_index=MAT_INDEX_IRON)
    create_box(bm, (0.04, chest_d + 0.015, chest_h + 0.015),
               (chest_cx, prop_y, counter_top_z + chest_h * 0.5), mat_index=MAT_INDEX_IRON)

    # 4. Merchant Weighing Balance Scale
    scale_cx = 0.48
    base_r = 0.12
    base_h = 0.035
    create_cylinder(bm, radius=base_r, height=base_h, segments=8,
                    location=(scale_cx, prop_y, counter_top_z + base_h * 0.5), mat_index=MAT_INDEX_IRON)
    post_h = 0.44
    create_cylinder(bm, radius=0.018, height=post_h, segments=6,
                    location=(scale_cx, prop_y, counter_top_z + base_h + post_h * 0.5), mat_index=MAT_INDEX_IRON)
    beam_w = 0.46
    create_box(bm, (beam_w, 0.025, 0.025),
               (scale_cx, prop_y, counter_top_z + base_h + post_h), mat_index=MAT_INDEX_IRON)
    for sgn_pan in (-1.0, 1.0):
        pan_x = scale_cx + sgn_pan * (beam_w * 0.46)
        rod_h = 0.22
        create_cylinder(bm, radius=0.008, height=rod_h, segments=5,
                        location=(pan_x, prop_y, counter_top_z + base_h + post_h - rod_h * 0.5), mat_index=MAT_INDEX_IRON)
        create_cylinder(bm, radius=0.065, height=0.018, segments=8,
                        location=(pan_x, prop_y, counter_top_z + base_h + post_h - rod_h), mat_index=MAT_INDEX_IRON)

    # 5. Carved Bone Barter Dagger on Rolled Leather Mat
    mat_cx = 1.0
    mat_w = 0.28
    mat_d = 0.22
    mat_th = 0.018
    create_box(bm, (mat_w, mat_d, mat_th),
               (mat_cx, prop_y, counter_top_z + mat_th * 0.5), mat_index=MAT_INDEX_LEATHER)
    create_box(bm, (0.045, 0.20, 0.02),
               (mat_cx, prop_y, counter_top_z + mat_th + 0.01), mat_index=MAT_INDEX_BONE)
    create_box(bm, (0.12, 0.035, 0.025),
               (mat_cx, prop_y + 0.06, counter_top_z + mat_th + 0.012), mat_index=MAT_INDEX_TIMBER)
    create_cylinder(bm, radius=0.018, height=0.09, segments=6,
                    location=(mat_cx, prop_y + 0.11, counter_top_z + mat_th + 0.012),
                    rotation=(math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_BONE)

    # 6. Coiled Hemp Rope
    rope_cx = 1.50
    create_torus_ring(bm, (rope_cx, prop_y, counter_top_z + 0.04),
                      major_radius=0.15, minor_radius=0.038, mat_index=MAT_INDEX_ROPE)

    # 5. Flanking Wooden Dock / Pier Platforms with Cargo Stacks
    for sgn_x in (-1.0, 1.0):
        plat_w = 2.4
        plat_d = depth * 0.85
        px = sgn_x * (hw + plat_w * 0.5)
        # Deck floor slab
        create_box(bm, (plat_w, plat_d, 0.16), (px, 0.0, z0 + 1.2), mat_index=MAT_INDEX_FLOOR)
        # Perimeter timber rim joists underneath deck
        create_box(bm, (plat_w, 0.20, 0.24), (px, -plat_d * 0.5 + 0.10, z0 + 1.04), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (plat_w, 0.20, 0.24), (px, plat_d * 0.5 - 0.10, z0 + 1.04), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (0.20, plat_d, 0.24), (px + sgn_x * (plat_w * 0.5 - 0.10), 0.0, z0 + 1.04), mat_index=MAT_INDEX_TIMBER)
        # 6 deep stilt pilings (outer and inner edge, plunging 10m deep)
        tot_h = (z0 + 1.2) + 10.0
        post_z = (z0 + 1.2 - 10.0) * 0.5
        for py in (-plat_d * 0.42, 0.0, plat_d * 0.42):
            create_cylinder(bm, radius=0.16, height=tot_h, segments=7,
                            location=(px + sgn_x * (plat_w * 0.5 - 0.18), py, post_z), mat_index=MAT_INDEX_TIMBER)
            create_cylinder(bm, radius=0.16, height=tot_h, segments=7,
                            location=(px - sgn_x * (plat_w * 0.5 - 0.35), py, post_z), mat_index=MAT_INDEX_TIMBER)
        # Cargo stacks placed toward rear of pier (clear of side window)
        _build_hajfin_cargo_stack(bm, px, plat_d * 0.28, z0 + 1.2)

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
            _build_chunky_corner_column(bm, cx, cy, z_mid, z_top - 0.08, size=0.40, extend_top=0.0)

    # 8. Interior Baseboard Skirting around upper room floor (seals wall-to-floor joints 100%)
    skirt_w = u_w - wall_th * 2.0
    skirt_d = u_d - wall_th * 2.0
    skirt_my = (u_y0 + wall_th + u_y1 - wall_th) * 0.5
    for sgn_sk in (-1.0, 1.0):
        create_box(bm, (0.10, skirt_d, 0.18),
                   (sgn_sk * (skirt_w * 0.5 - 0.05), skirt_my, z_mid + 0.09), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (skirt_w, 0.10, 0.18),
                   (0.0, skirt_my + sgn_sk * (skirt_d * 0.5 - 0.05), z_mid + 0.09), mat_index=MAT_INDEX_TIMBER)

    # 10. Interior Trade Room Furniture & Props
    _build_hajfin_bone_shop_table(bm, 0.0, -hd + 3.2, z0, width=3.8)
    _build_hajfin_weapon_rack(bm, -hw + 1.2, 0.0, z0, rot_z=math.pi * 0.5)

    # 11. Multi-Tier Bone Scale Roofs with Full Solid Gable Triangles
    # Lower flanking roofs (Eave sits 25cm below second floor level, sealed by exterior timber flashing ledgers)
    fl_eave_z = z_mid - 0.25
    for sgn_x in (-1.0, 1.0):
        if sgn_x < 0:
            fl_x0 = -hw
            fl_x1 = -u_hw - wall_th - 0.06
            ov_l = 0.40
            ov_r = 0.0
        else:
            fl_x0 = u_hw + wall_th + 0.06
            fl_x1 = hw
            ov_l = 0.0
            ov_r = 0.40
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, -hd, fl_eave_z, fl_eave_z + 2.25, wall_th=wall_th)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, hd, fl_eave_z, fl_eave_z + 2.25, wall_th=wall_th)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd, hd, fl_eave_z, 2.25,
                                     overhang_y=0.40, fin_scale=1.2, num_ridge_teeth=5,
                                     overhang_x_left=ov_l, overhang_x_right=ov_r)

        # Exterior timber flashing ledger beam sealing the roof-to-tower junction
        ledger_x = -u_hw - wall_th * 0.5 if sgn_x < 0 else u_hw + wall_th * 0.5
        create_box(bm, (0.16, depth + 0.40, 0.22), (ledger_x, 0.0, z_mid - 0.12), mat_index=MAT_INDEX_TIMBER)

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
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + nave_h, size=0.48, extend_top=0.0)
    for sgn_x in (-1.0, 1.0):
        for cy in (-hd * 0.85, hd * 0.85):
            _build_chunky_corner_column(bm, sgn_x * hw, cy, z0, z0 + side_h, size=0.40, extend_top=0.0)

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

    # 7B. Front Facade Structural Belt Beams & War Banners
    # Horizontal structural timber belt course flanking the grand entrance (leaving doorway 100% open)
    d_half_door = door_w * 0.5 + 0.35
    for sgn_bx in (-1.0, 1.0):
        b_x0 = sgn_bx * d_half_door
        b_x1 = sgn_bx * (nave_w * 0.5)
        bw = abs(b_x1 - b_x0)
        create_box(bm, (bw, 0.26, 0.34), ((b_x0 + b_x1) * 0.5, -hd - 0.08, z0 + nave_h * 0.58), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (0.36, 0.28, 0.36), ((b_x0 + b_x1) * 0.5, -hd - 0.08, z0 + nave_h * 0.58), mat_index=MAT_INDEX_IRON)

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
        if sgn_x < 0:
            fl_x0 = -hw
            fl_x1 = -nave_w * 0.5 - wall_th * 0.5
            ov_l = 0.40
            ov_r = 0.0  # Stops flush at nave exterior wall so ZERO shingles poke into interior
        else:
            fl_x0 = nave_w * 0.5 + wall_th * 0.5
            fl_x1 = hw
            ov_l = 0.0  # Stops flush at nave exterior wall so ZERO shingles poke into interior
            ov_r = 0.40
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd * 0.85, hd * 0.85, z0 + side_h, 2.2,
                                     overhang_y=0.40, fin_scale=1.2, num_ridge_teeth=5,
                                     overhang_x_left=ov_l, overhang_x_right=ov_r)

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

    # 1. Stilt Pier Foundation (aligned with front entrance)
    _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h, door_cx=-hw * 0.4)

    # 2. Full Interior Ground Floor Slab across main taproom and wing
    m_w = width
    m_d = depth - wing_d
    my = -hd + m_d * 0.5
    create_box(bm, (m_w - wall_th * 2, m_d - wall_th * 2, 0.14),
               (0.0, my, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)
    create_box(bm, (wing_w - wall_th * 2, wing_d - wall_th * 2, 0.14),
               (hw - wing_w * 0.5, hd - wing_d * 0.5, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)

    # 3. Ground Floor Walls (Hollow taproom rooms with real window cutouts)
    # Arched door opening leading from taproom out onto the stilt drinking deck
    tap_x0 = -hw + wall_th
    tap_x1 = hw - wing_w - wall_th
    door_w = float(getattr(props, 'door_width', 1.85))
    door_h = min(float(getattr(props, 'door_height', 3.50)), story_h * 0.85)
    _build_wall_with_door_opening(bm, tap_x0, tap_x1, -hd + m_d - wall_th * 0.5,
                                  z0, z_mid, door_cx=(tap_x0 + tap_x1) * 0.5, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=math.pi,
                                  include_leaf=getattr(props, 'include_door_leaves', False))

    # Flanking side walls with real window cutouts
    _build_wall_with_window_y(bm, -hd + wall_th, -hd + m_d - wall_th, -hw + wall_th * 0.5,
                              z0, z_mid, win_cy=my, win_cz=z0 + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -hd + wall_th, -hd + m_d - wall_th, hw - wall_th * 0.5,
                              z0, z_mid, win_cy=my, win_cz=z0 + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)

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

    # Flanking upper side walls with real window cutouts
    _build_wall_with_window_y(bm, -hd + wall_th, -hd + m_d - wall_th, -hw + wall_th * 0.5,
                              z_mid, z1, win_cy=my, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=False)
    _build_wall_with_window_y(bm, -hd + wall_th, -hd + m_d - wall_th, hw - wall_th * 0.5,
                              z_mid, z1, win_cy=my, win_cz=z_mid + story_h * 0.52,
                              win_w=0.85, win_h=0.85, wall_th=wall_th, facing_east=True)

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

    # 8. Corner Columns (supporting eaves cleanly without punching through shingles)
    col_size = 0.46
    for cx in (-hw, hw):
        for cy in (-hd, my + m_d * 0.5):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.0)

    # 9. Solid Gable Triangle Walls & Bone Scale Roofs (Zero sky gaps!)
    m_peak_z = z1 + 3.8
    w_peak_z = z1 + 3.0
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z1, m_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, -hd + m_d, z1, m_peak_z, wall_th=wall_th)

    # Gable walls sealing both ends of the wing roof (solves open hole)
    _build_gable_triangle_wall(bm, hw - wing_w, hw, hd - wing_d, z1, w_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, hw - wing_w, hw, hd, z1, w_peak_z, wall_th=wall_th)

    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, -hd + m_d, z1, 3.8,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.7, num_ridge_teeth=8)
    _build_bone_scale_roof_gable(bm, hw - wing_w, hw, hd - wing_d, hd, z1, 3.0,
                                 overhang_x=0.45, overhang_y=0.45, fin_scale=1.3, num_ridge_teeth=6)


def _build_hajfin_bone_gate(bm, props, width=12.0, depth=4.0, height=4.5, found_h=0.0):
    """The Fortified Shark-Bone Palisade Gate:
    - Dense, fortified palisade wall with tightly packed overlapping sharpened timber logs.
    - Rear horizontal cross-beams and diagonal timber buttress supports.
    - Elevated rear sentry bastion platforms with access ladders for Hajfin defenders.
    - Massive dual gate posts bound with nautical cordage.
    - Heavy double lintel beam structure with diagonal timber knee braces.
    - Monumental timber crest with carved bone horns at apex.
    - Symmetrical gate wings with central open gateway for 2-3m tall Hajfin warriors."""
    hw = width * 0.5
    gate_w = max(2.8, float(getattr(props, 'door_width', 3.20)))
    h_gw = gate_w * 0.5
    post_r = 0.20
    log_h = height

    wing_w = (width - gate_w) * 0.5
    dx = 0.38
    num_posts_per_wing = max(7, int(wing_w / dx))
    dx = wing_w / num_posts_per_wing

    # 1. Rear Horizontal Tie Beams
    for rail_z in (0.95, 2.25, 3.4):
        create_box(bm, (wing_w + 0.3, 0.22, 0.20), (-hw + wing_w * 0.5, 0.16, rail_z), mat_index=MAT_INDEX_TIMBER)
        create_box(bm, (wing_w + 0.3, 0.22, 0.20), (hw - wing_w * 0.5, 0.16, rail_z), mat_index=MAT_INDEX_TIMBER)

    # 2. Dense Sharpened Palisade Logs across each wing
    for side_sgn, (start_x, end_x) in ((-1, (-hw, -h_gw)), (1, (h_gw, hw))):
        for i in range(num_posts_per_wing + 1):
            px = start_x + i * dx
            if abs(px) > hw + 0.01:
                continue
            cur_post_h = log_h * (0.88 + 0.18 * math.sin(i * 1.6 + side_sgn * 0.7))
            # Sharpened timber post
            create_cylinder(bm, radius=post_r, height=cur_post_h, segments=8,
                            location=(px, 0.0, cur_post_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
            create_cone(bm, radius1=post_r, radius2=0.02, height=0.65, segments=8,
                        location=(px, 0.0, cur_post_h + 0.30), mat_index=MAT_INDEX_DRIFTWOOD)
            # Rope bindings around horizontal rails
            for rz in (0.95, 2.25):
                if rz < cur_post_h - 0.4:
                    create_torus_ring(bm, (px, 0.0, rz), major_radius=post_r + 0.03, minor_radius=0.022,
                                      mat_index=MAT_INDEX_ROPE)

            # Rear diagonal timber buttress brace every 3 logs
            if i % 3 == 1:
                p_butt_top = Vector((px, 0.12, cur_post_h * 0.65))
                p_butt_bot = Vector((px, 1.45, 0.08))
                _create_oriented_beam(bm, p_butt_bot, p_butt_top, width=0.18, depth=0.18, mat_index=MAT_INDEX_TIMBER)

            # Alternating curved whale rib pickets lashed to front
            if i % 2 == 1 and i < num_posts_per_wing:
                rib_x = px + dx * 0.5
                _build_curved_bone_spine(bm, rib_x, -0.10, 0.20, height=2.2,
                                         base_radius=0.08, sweep_y=-0.12)

    # 3. Elevated Rear Sentry Bastion Catwalks & Access Ladders
    cat_z = 2.40
    cat_d = 1.30
    for side_sgn in (-1, 1):
        cx = side_sgn * (h_gw + wing_w * 0.5)
        # Timber catwalk platform
        create_box(bm, (wing_w, cat_d, 0.14), (cx, cat_d * 0.5 + 0.14, cat_z), mat_index=MAT_INDEX_FLOOR)
        # Rear protective railing
        _build_railing_segment(bm, cx - wing_w * 0.5, cx + wing_w * 0.5, cat_d + 0.14, cat_d + 0.14, cat_z, height=1.0)
        # Access ladder
        lad_x = cx + side_sgn * (wing_w * 0.32)
        for sgn_ls in (-0.25, 0.25):
            _create_oriented_beam(bm, (lad_x + sgn_ls, cat_d + 0.10, 0.0),
                                  (lad_x + sgn_ls, cat_d + 0.10, cat_z + 0.8),
                                  width=0.10, depth=0.10, mat_index=MAT_INDEX_TIMBER)
        for r_i in range(7):
            rz = (r_i + 1) * (cat_z / 8.0)
            create_cylinder(bm, radius=0.03, height=0.50, segments=6,
                            location=(lad_x, cat_d + 0.10, rz),
                            rotation=(0, math.pi * 0.5, 0), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Monumental Gate Portal (Massive Posts and Timber Crest)
    gate_post_h = log_h * 1.45
    gate_post_r = 0.28
    for sgn_gx in (-1.0, 1.0):
        gpx = sgn_gx * h_gw
        create_cylinder(bm, radius=gate_post_r, height=gate_post_h, segments=10,
                        location=(gpx, 0.0, gate_post_h * 0.5), mat_index=MAT_INDEX_TIMBER)
        create_cone(bm, radius1=gate_post_r, radius2=0.03, height=0.85, segments=10,
                    location=(gpx, 0.0, gate_post_h + 0.40), mat_index=MAT_INDEX_TIMBER)
        for rz in (1.0, 2.3, 3.6, gate_post_h * 0.85):
            create_torus_ring(bm, (gpx, 0.0, rz), major_radius=gate_post_r + 0.04, minor_radius=0.03,
                              mat_index=MAT_INDEX_ROPE)

    # Heavy double lintel beam structure above gateway
    lintel_z = log_h * 1.05
    create_box(bm, (gate_w + 1.2, 0.38, 0.34), (0.0, 0.0, lintel_z), mat_index=MAT_INDEX_TIMBER)
    create_box(bm, (gate_w + 1.0, 0.32, 0.26), (0.0, 0.0, lintel_z + 0.35), mat_index=MAT_INDEX_TIMBER)

    # Diagonal knee braces supporting lintel
    for sgn_k in (-1.0, 1.0):
        p_kb_post = Vector((sgn_k * (h_gw - 0.15), 0.0, lintel_z - 1.2))
        p_kb_lintel = Vector((sgn_k * (h_gw * 0.45), 0.0, lintel_z - 0.10))
        _create_oriented_beam(bm, p_kb_post, p_kb_lintel, width=0.20, depth=0.20, mat_index=MAT_INDEX_TIMBER)

    # Central Tall Timber Totem above lintel
    totem_pole_h = 2.6
    create_cylinder(bm, radius=0.22, height=totem_pole_h, segments=8,
                    location=(0.0, 0.0, lintel_z + 0.35 + totem_pole_h * 0.5), mat_index=MAT_INDEX_TIMBER)
    create_cone(bm, radius1=0.22, radius2=0.03, height=0.75, segments=8,
                location=(0.0, 0.0, lintel_z + 0.35 + totem_pole_h + 0.35), mat_index=MAT_INDEX_TIMBER)

    totem_z = lintel_z + 0.35 + totem_pole_h * 0.68
    create_torus_ring(bm, (0.0, 0.0, totem_z), major_radius=0.38, minor_radius=0.04,
                      mat_index=MAT_INDEX_ROPE)

    # Flanking curved bone horns
    for sgn_h in (-1.0, 1.0):
        _build_curved_bone_spine(bm, sgn_h * 0.65, -0.15, totem_z - 0.20, height=1.35,
                                 base_radius=0.13, sweep_y=-0.15)

    # Hanging bone amulet beneath the totem
    create_cone(bm, radius1=0.10, radius2=0.01, height=0.42, segments=6,
                location=(0.0, -0.28, lintel_z + 0.35 + totem_pole_h * 0.30),
                rotation=(math.pi, 0, 0), mat_index=MAT_INDEX_BONE)

    # Side post shark fin wedge
    fin_px = h_gw + dx * 1.5
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
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + height, size=col_size, extend_top=0.0)

    # Open-air canopy beams; the forge remains exposed to wind and smoke.
    canopy_z = z0 + height - 0.16
    for size, loc in (
        ((width, 0.32, 0.32), (0.0, -hd, canopy_z)),
        ((0.32, depth, 0.32), (hw, 0.0, canopy_z)),
        ((width, 0.32, 0.32), (0.0, hd, canopy_z)),
        ((0.32, depth, 0.32), (-hw, 0.0, canopy_z)),
    ):
        timber_box(
            bm, size, loc, mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.018, long_axis=0 if size[0] > size[1] else 1,
        )

    # 3. Primitive open coal-bed forge: low stone rim, fuel chunks, and heat.
    f_w, f_d, f_h = 2.25, 1.65, 0.38
    furnace_x = -hw + f_w * 0.5 + 0.8
    furnace_y = hd - f_d * 0.5 - 1.0
    create_box(bm, (f_w, f_d, f_h), (furnace_x, furnace_y, z0 + f_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)
    rim_h = 0.22
    for rx, ry, rw, rd in (
        (furnace_x, furnace_y - f_d * 0.5, f_w, 0.16),
        (furnace_x, furnace_y + f_d * 0.5, f_w, 0.16),
        (furnace_x - f_w * 0.5, furnace_y, 0.16, f_d - 0.18),
        (furnace_x + f_w * 0.5, furnace_y, 0.16, f_d - 0.18),
    ):
        create_box(bm, (rw, rd, rim_h), (rx, ry, z0 + f_h + rim_h * 0.5),
                   mat_index=MAT_INDEX_ROUGH_STONE)
    for ci in range(9):
        cx = furnace_x + random.uniform(-f_w * 0.35, f_w * 0.35)
        cy = furnace_y + random.uniform(-f_d * 0.30, f_d * 0.30)
        chunk = random.uniform(0.10, 0.18)
        create_beveled_box(
            bm, (chunk * 1.5, chunk, chunk * 0.8),
            (cx, cy, z0 + f_h + 0.12),
            rotation=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                      random.uniform(0.0, math.pi)),
            mat_index=MAT_INDEX_IRON, bevel_amount=chunk * 0.18,
        )
    create_cylinder(
        bm, radius=0.42, height=0.10, segments=10,
        location=(furnace_x, furnace_y, z0 + f_h + 0.16),
        mat_index=MAT_INDEX_LANTERN,
    )

    # 4. Master Blacksmith Anvil from FBX (reusing artisan props builder)
    build_anvil(bm, x=furnace_x + 2.4, y=furnace_y - 0.9, z_ground=z0 + 0.14, ang=0.4, scale=1.2)

    # 5. Hollow Timber Quenching Water Tub
    quench_x = furnace_x + 2.5
    quench_y = furnace_y + 0.75
    q_r, q_h = 0.42, 0.85
    create_hollow_cylinder(bm, radius=q_r, inner_radius=q_r - 0.04, height=q_h,
                           inner_depth=q_h - 0.08, segments=12,
                           location=(quench_x, quench_y, z0 + q_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_torus_ring(bm, (quench_x, quench_y, z0 + q_h * 0.25), major_radius=q_r + 0.02, minor_radius=0.02, mat_index=MAT_INDEX_IRON)
    create_torus_ring(bm, (quench_x, quench_y, z0 + q_h * 0.75), major_radius=q_r + 0.02, minor_radius=0.02, mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=q_r - 0.05, height=0.04, segments=10,
                    location=(quench_x, quench_y, z0 + q_h - 0.10), mat_index=MAT_INDEX_WATER)

    # Firewood log pile beside furnace
    for li in range(3):
        create_cylinder(bm, radius=0.14, height=1.4, segments=8,
                        location=(furnace_x + 0.2, furnace_y - f_d * 0.5 - 0.35 - li * 0.25, z0 + 0.16),
                        rotation=(math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_LOG)

    # 6. Harpoon & Artisan Tool Rack (reusing artisan props builder)
    build_tool_rack(bm, x=hw - 0.45, y=-0.5, z_ground=z0 + 0.14, ang=-math.pi * 0.5, width=2.0)

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

    # 2. Main Floor Slabs & Complete Walkable Pier Platform (with full flank decks)
    flank_w = (width - cabin_w) * 0.5
    flank_d = cabin_d
    flank_left_cx = (-hw + (-c_hw)) * 0.5
    flank_right_cx = (c_hw + hw) * 0.5
    flank_cy = c_y

    # Interior cabin floor
    create_box(bm, (cabin_w - wall_th * 2, cabin_d - wall_th * 2, 0.14), (0.0, c_y, z0 + 0.07), mat_index=MAT_INDEX_FLOOR)
    # Rear extended dock deck
    create_box(bm, (width, depth - cabin_d, 0.16), (0.0, hd - (depth - cabin_d) * 0.5, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)
    # Left flank pier deck
    create_box(bm, (flank_w, flank_d, 0.16), (flank_left_cx, flank_cy, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)
    # Right flank pier deck
    create_box(bm, (flank_w, flank_d, 0.16), (flank_right_cx, flank_cy, z0 + 0.08), mat_index=MAT_INDEX_FLOOR)

    # Perimeter Timber Railings wrapping the entire exterior pier edge
    rail_h = 1.05
    _build_railing_segment(bm, -hw, -hw, -hd, hd, z0 + 0.08, height=rail_h)
    _build_railing_segment(bm, hw, hw, -hd, hd, z0 + 0.08, height=rail_h)
    _build_railing_segment(bm, -hw, hw, hd, hd, z0 + 0.08, height=rail_h)
    _build_railing_segment(bm, -hw, -c_hw, -hd, -hd, z0 + 0.08, height=rail_h)
    _build_railing_segment(bm, c_hw, hw, -hd, -hd, z0 + 0.08, height=rail_h)

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

    # 4. Upper Floor Hollow Cabin with Real Window Cutouts
    _build_wall_with_window_x(bm, -c_hw + wall_th, c_hw - wall_th, -hd + wall_th * 0.5, z_mid, z1,
                              win_cx=0.0, win_cz=z_mid + story_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_north=False)
    _build_wall_with_window_x(bm, -c_hw + wall_th, c_hw - wall_th, c_y + c_hd - wall_th * 0.5, z_mid, z1,
                              win_cx=0.0, win_cz=z_mid + story_h * 0.52, win_w=0.85, win_h=0.85,
                              wall_th=wall_th, facing_north=True)
    create_box(bm, (wall_th, cabin_d - wall_th * 2, story_h), (-c_hw + wall_th * 0.5, c_y, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, cabin_d - wall_th * 2, story_h), (c_hw - wall_th * 0.5, c_y, z_mid + story_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Cabin Corner Columns (supporting eaves cleanly without punching through shingles)
    col_size = 0.44
    for cx in (-c_hw, c_hw):
        for cy in (-hd, c_y + c_hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.0)

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
    - Tribal totems, glowing smoking brazier, and shark tooth fetish staves."""
    r_base = diameter * 0.5
    z0 = found_h

    # 1. Stepped Circular Reef Stone Dais
    create_cylinder(bm, radius=r_base, height=found_h * 0.6, segments=20,
                    location=(0.0, 0.0, found_h * 0.3), mat_index=MAT_INDEX_ROUGH_STONE)
    create_cylinder(bm, radius=r_base * 0.85, height=found_h * 0.4, segments=18,
                    location=(0.0, 0.0, found_h * 0.8), mat_index=MAT_INDEX_ROUGH_STONE)
    create_cylinder(bm, radius=r_base * 0.72, height=0.12, segments=16,
                    location=(0.0, 0.0, z0 + 0.06), mat_index=MAT_INDEX_FLOOR)

    # 2. Ring of 6 Towering Smooth Curved Whale Rib Arches (Cathedral Dome)
    num_ribs = 6
    arch_r = r_base * 0.70
    dome_h = height
    n_rib_segs = 18
    for i in range(num_ribs):
        ang = i * (2.0 * math.pi / num_ribs)
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)

        rib_pts = []
        for s_idx in range(n_rib_segs + 1):
            t = s_idx / n_rib_segs
            r_cur = arch_r * (1.0 - t ** 1.8)
            z_cur = z0 + (math.sin(t * math.pi * 0.5) ** 0.85) * dome_h
            rib_pts.append(Vector((cos_a * r_cur, sin_a * r_cur, z_cur)))

        _build_continuous_bone_arc(
            bm, rib_pts, base_radius=0.22, mat_index=MAT_INDEX_BONE
        )

    # 3. Apex Sculpted Bone Crown with 4 Curved Horn Finials
    create_cylinder(bm, radius=0.45, height=0.35, segments=8,
                    location=(0.0, 0.0, z0 + dome_h + 0.175), mat_index=MAT_INDEX_TIMBER)
    create_torus_ring(bm, (0.0, 0.0, z0 + dome_h + 0.30), major_radius=0.48, minor_radius=0.04, mat_index=MAT_INDEX_IRON)
    for c_i in range(4):
        c_ang = c_i * (math.pi * 0.5)
        _build_curved_bone_spine(bm, math.cos(c_ang) * 0.28, math.sin(c_ang) * 0.28,
                                 z0 + dome_h + 0.35, height=1.35, base_radius=0.12, sweep_y=-0.18)

    # 4. Monumental Megalodon Jaw Bone Altar on Whale Vertebrae Pillars
    altar_w = 2.4
    altar_d = 1.5
    altar_h = 1.10
    create_cylinder(bm, radius=altar_w * 0.65, height=0.25, segments=8,
                    location=(0.0, 0.0, z0 + 0.125), mat_index=MAT_INDEX_ROUGH_STONE)
    for sgn_x in (-1.0, 1.0):
        for sgn_y in (-1.0, 1.0):
            vx = sgn_x * (altar_w * 0.35)
            vy = sgn_y * (altar_d * 0.32)
            create_cylinder(bm, radius=0.18, height=altar_h - 0.25, segments=8,
                            location=(vx, vy, z0 + 0.25 + (altar_h - 0.25) * 0.5), mat_index=MAT_INDEX_BONE)
            create_torus_ring(bm, (vx, vy, z0 + 0.40), major_radius=0.20, minor_radius=0.025, mat_index=MAT_INDEX_BONE)
            create_torus_ring(bm, (vx, vy, z0 + altar_h - 0.10), major_radius=0.20, minor_radius=0.025, mat_index=MAT_INDEX_BONE)

    # Massive Scrimshaw Megalodon Altar Slab
    create_box(bm, (altar_w, altar_d, 0.26), (0.0, 0.0, z0 + altar_h), mat_index=MAT_INDEX_BONE)
    create_box(bm, (altar_w + 0.12, altar_d + 0.12, 0.08), (0.0, 0.0, z0 + altar_h + 0.13), mat_index=MAT_INDEX_TIMBER)

    # Ceremonial Forged Iron Brazier with Glowing Embers
    br_r = 0.45
    br_h = 0.35
    create_cylinder(bm, radius=br_r, height=br_h, segments=12,
                    location=(0.0, 0.0, z0 + altar_h + 0.18 + br_h * 0.5), mat_index=MAT_INDEX_IRON)
    create_torus_ring(bm, (0.0, 0.0, z0 + altar_h + 0.18 + br_h), major_radius=br_r + 0.02, minor_radius=0.03, mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=br_r - 0.06, height=0.10, segments=10,
                    location=(0.0, 0.0, z0 + altar_h + 0.18 + br_h - 0.04), mat_index=MAT_INDEX_LANTERN)

    # 5. Flanking Tribal Totems (Positioned in Open Bays between ribs to guarantee ZERO overlap)
    for sgn_ty in (-1.0, 1.0):
        ty = sgn_ty * (arch_r * 0.75)
        totem_h = 3.2
        create_cylinder(bm, radius=0.15, height=totem_h, segments=7,
                        location=(0.0, ty, z0 + totem_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.15, radius2=0.02, height=0.5, segments=6,
                    location=(0.0, ty, z0 + totem_h + 0.25), mat_index=MAT_INDEX_DRIFTWOOD)


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
    landing_beam_z = height - 0.27
    timber_box(
        bm, (landing_w, 0.22, 0.22),
        (door_cx, y0 - landing_d + 0.11, landing_beam_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012, long_axis=0,
    )
    for sgn_lp in (-1.0, 1.0):
        # Flanking joists
        timber_box(
            bm, (0.22, landing_d, 0.22),
            (door_cx + sgn_lp * (landing_w * 0.5 - 0.11), landing_cy, landing_beam_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012, long_axis=1,
        )
        # 2 sturdy stilt posts extending 10m downwards under landing outer corners (capped cleanly under joists)
        landing_post_top = height - 0.38
        landing_post_h = landing_post_top + post_depth
        landing_post_cz = landing_post_top - landing_post_h * 0.5
        create_cylinder(bm, radius=0.18, height=landing_post_h, segments=7,
                        location=(door_cx + sgn_lp * (landing_w * 0.42), y0 - landing_d + 0.20, landing_post_cz),
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

    # Steps between the stringers (UV aligned horizontally across step width)
    uv_l = bm.loops.layers.uv.verify()
    for i in range(num_steps):
        sz = (i + 0.5) * (height / num_steps)
        sy = y_stair_top - (num_steps - i - 0.5) * step_d
        step_faces = create_box(bm, (step_w, step_d * 1.05, 0.12), (door_cx, sy, sz), mat_index=MAT_INDEX_FLOOR)
        for sf in step_faces:
            if sf.normal.z > 0.5:
                for loop in sf.loops:
                    d_rel = loop.vert.co - Vector((door_cx, sy, sz))
                    loop[uv_l].uv = Vector((d_rel.y * 0.50, d_rel.x * 0.50))
            sf.tag = True


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


def _apply_hajfin_wall_uvs(bm, scale=0.18):
    """Normalize every Hajfin siding face after all archetypes and props build.

    Individual archetypes contain a mixture of boxes, gables, and tapered
    panels. A final material-scoped pass keeps their board density identical
    and prevents world elevation or a builder-specific offset from stretching
    the wall atlas.
    """
    uv_layer = bm.loops.layers.uv.verify()
    bm.normal_update()
    for face in bm.faces:
        if face.material_index != MAT_INDEX_DRIFTWOOD:
            continue
        normal = face.normal
        if abs(normal.z) >= 0.25:
            for loop in face.loops:
                co = loop.vert.co
                loop[uv_layer].uv = Vector((co.x * scale, co.y * scale))
        elif abs(normal.x) >= abs(normal.y):
            for loop in face.loops:
                co = loop.vert.co
                u = co.y * scale * (-1.0 if normal.x < 0.0 else 1.0)
                loop[uv_layer].uv = Vector((u, co.z * scale))
        else:
            for loop in face.loops:
                co = loop.vert.co
                u = co.x * scale * (-1.0 if normal.y < 0.0 else 1.0)
                loop[uv_layer].uv = Vector((u, co.z * scale))


def _fill_missing_hajfin_uvs(bm, scale=0.25):
    """Give any untouched procedural face a stable planar UV instead of a zero map."""
    uv_layer = bm.loops.layers.uv.verify()
    bm.normal_update()
    for face in bm.faces:
        if not face.loops:
            continue
        if not all(loop[uv_layer].uv.length_squared < 1e-12 for loop in face.loops):
            continue
        normal = face.normal
        if abs(normal.z) >= abs(normal.x) and abs(normal.z) >= abs(normal.y):
            projection = lambda co: (co.x * scale, co.y * scale)
        elif abs(normal.x) >= abs(normal.y):
            projection = lambda co: (co.y * scale, co.z * scale)
        else:
            projection = lambda co: (co.x * scale, co.z * scale)
        for loop in face.loops:
            u, v = projection(loop.vert.co)
            loop[uv_layer].uv = Vector((u, v))


# =============================================================================
# MAIN HAJFIN ENTRY POINT
# =============================================================================

def build_hajfin_building(obj, bm, props):
    """Primary entry point for generating authentic Hajfin pirate architecture.
    Completely replaces human half-timber/stone construction with 100% dedicated
    procedural geometry matching the Hajfin fantasy concept art."""
    _hajfin_roof_props(props)
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

    # Final material-scoped pass prevents any archetype-specific wall builder
    # from reintroducing a different siding density.
    _apply_hajfin_wall_uvs(bm)

    # Box UV mapping preserves the specialized UVs above.
    apply_box_uvs(bm, scale=0.18)
    _fill_missing_hajfin_uvs(bm)

    # Write bmesh to obj
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
