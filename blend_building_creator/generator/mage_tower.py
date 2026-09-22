"""Whimsical fantasy Mage Tower.

A majestic round wizard tower inspired by classic high-fantasy arcane sanctuaries
(Warcraft Alliance Mage Tower, Kirin Tor Spire, Valheim Wizard Tower):
- Sturdy stone cylindrical shaft built as a seamless, continuous curved shell
  without embedded pillar end-caps or harsh segment creases.
- Dramatically cantilevered crown (Belvedere / Arcane Observatory) supported
  by a ring of chunky carved wooden console corbels resting under a seamless
  gap-free wooden soffit.
- Smooth plaster walls on the crown room with glowing arched leaded windows,
  without internal pillars slicing through the walls.
- Flared bell-cast witch-hat roof in royal blue / arcane purple shingles,
  crowned with an iron spire and glowing arcane crystal, accented by 4 high-poly
  smooth corner tourelle pinnacles with gold caps, and floating orbiting arcane crystals.
- Functional, walkable multi-storey interior: a curved castle staircase winds
  along the inner face of the outer wall, leaving open walk-off landing gaps at each
  level with zero blocking railings and a solid gap-free floor.
"""

import math
from mathutils import Vector, Euler, Matrix

from .mesh_utils import (
    create_beveled_box, create_cylinder, create_cone, create_box,
    create_torus_ring,
)
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR, MAT_INDEX_WOOD,
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_PLASTER_EXT,
    MAT_INDEX_PLASTER_INT, MAT_INDEX_GLASS, MAT_INDEX_IRON, MAT_INDEX_SHINGLES,
    MAT_INDEX_BANNER,
)
from .poly import segment_frame
from .railing import build_railing, _beam
from .openings import build_door_assembly, build_front_steps, build_window_assembly
from .walls import create_curved_corbel
from .uv_utils import apply_roof_shingle_uvs, map_planar_faces
from .accessories.lighting import _lantern_cage, _uv_faces


BAYS = 8
BAY_ANG = 2.0 * math.pi / BAYS
OFFSET = -math.pi * 0.5 - BAY_ANG * 0.5     # bay 0 faces -Y (the front entrance)
SEGMENTS = 24


# =============================================================================
# ARCANE & WHIMSICAL FLOURISHES (ROOF, TOURELLES, CRYSTALS, BANNERS, LANTERNS)
# =============================================================================

def _shift_uvs(bm, faces, du, dv):
    """Offset a set of faces' UVs so repeated pieces do not share an identical map."""
    uv = bm.loops.layers.uv.verify()
    for f in faces or ():
        for lp in f.loops:
            lp[uv].uv = (lp[uv].uv[0] + du, lp[uv].uv[1] + dv)


def _arcane_crystal(bm, cx, cy, z, scale=1.0, rx=0.0, ry=0.0, rz=0.0):
    """A faceted double-pyramid arcane crystal with glowing glass material."""
    s = max(0.3, scale)
    r = 0.24 * s
    rot = (rx, ry, rz + math.pi * 0.25)
    create_cone(bm, radius1=r, radius2=0.0, height=0.55 * s, segments=4,
                location=(cx, cy, z + 0.275 * s),
                rotation=rot, mat_index=MAT_INDEX_GLASS)
    create_cone(bm, radius1=0.0, radius2=r, height=0.38 * s, segments=4,
                location=(cx, cy, z - 0.19 * s),
                rotation=rot, mat_index=MAT_INDEX_GLASS)


def _floating_arcane_shards(bm, cx, cy, z_spire, bel_r):
    """Magical faceted crystal shards floating in the air orbiting the upper spire."""
    shard_configs = [
        (bel_r * 0.76, 0.45, z_spire + 1.8, 1.05, 0.22, -0.15),
        (bel_r * 0.88, 2.15, z_spire + 3.1, 0.95, -0.20, 0.28),
        (bel_r * 0.72, 3.65, z_spire + 4.3, 0.85, 0.32, 0.12),
        (bel_r * 0.82, 5.15, z_spire + 2.4, 1.00, -0.16, -0.22),
    ]
    for dist, ang, z, sc, rx, ry in shard_configs:
        sx = cx + dist * math.cos(ang)
        sy = cy + dist * math.sin(ang)
        _arcane_crystal(bm, sx, sy, z, scale=sc, rx=rx, ry=ry, rz=ang)
        create_torus_ring(bm, location=(sx, sy, z),
                          rotation=(rx + math.pi * 0.38, ry, ang),
                          major_radius=0.34 * sc, minor_radius=0.015 * sc,
                          major_segments=12, minor_segments=4,
                          mat_index=MAT_INDEX_IRON)


def _witch_hat_roof(bm, cx, cy, z_base, radius, height, segments=48, offset=OFFSET):
    """Flared bell-cast fantasy spire with shingle UVs, iron spire and crystal finial.

    Includes a continuous wooden eaves soffit ring bridging the wall top to the flared
    shingle skirt, downward overlapping the top of the wall to eliminate any gaps.
    """
    skirt_h = min(1.8, height * 0.32)
    skirt = create_cone(bm, radius1=radius * 1.18, radius2=radius * 0.70,
                        height=skirt_h, segments=segments,
                        location=(cx, cy, z_base + skirt_h * 0.5),
                        mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, skirt, scale=0.32)

    main_h = height - skirt_h
    main = create_cone(bm, radius1=radius * 0.70, radius2=0.05, height=main_h,
                       segments=segments,
                       location=(cx, cy, z_base + skirt_h + main_h * 0.5),
                       mat_index=MAT_INDEX_SHINGLES)
    apply_roof_shingle_uvs(bm, main, scale=0.32)

    # Timber eaves fascia disc (single, seals the overhang underside) & collar
    create_cylinder(bm, radius=radius * 1.20, height=0.18, segments=segments,
                    location=(cx, cy, z_base + 0.06), mat_index=MAT_INDEX_WOOD)
    create_cylinder(bm, radius=radius * 0.74, height=0.12, segments=segments,
                    location=(cx, cy, z_base + skirt_h + 0.04),
                    mat_index=MAT_INDEX_TIMBER)

    # Real carved timber corbels under the eaves overhang - the same joined
    # bracket used on the belvedere, aligned with the eight bays.
    overhang = radius * 0.20 + 0.12
    for k in range(BAYS):
        ang = k * (2.0 * math.pi / BAYS) + offset
        c_pos = Vector((cx + radius * math.cos(ang), cy + radius * math.sin(ang), z_base))
        f_dir = (math.cos(ang), math.sin(ang), 0.0)
        create_curved_corbel(bm, loc=c_pos, facing_dir=f_dir,
                             width=0.26, depth=overhang, height=0.74,
                             mat_index=MAT_INDEX_TIMBER)

    # Apex iron needle and glowing arcane crystal
    apex = z_base + height
    create_cylinder(bm, radius=0.055, height=0.85, segments=8,
                    location=(cx, cy, apex + 0.42), mat_index=MAT_INDEX_IRON)
    _arcane_crystal(bm, cx, cy, apex + 1.25, scale=1.35)


def _corner_tourelles(bm, cx, cy, z_base, bel_r, height=2.4):
    """High-poly smooth fantasy corner tourelles / pinnacles around the belvedere eaves."""
    angles = [math.pi * 0.25, math.pi * 0.75, math.pi * 1.25, math.pi * 1.75]
    tr_r = 0.55
    segs = 24  # High poly smooth roundness
    for ang in angles:
        tx = cx + (bel_r - 0.12) * math.cos(ang)
        ty = cy + (bel_r - 0.12) * math.sin(ang)
        # Plain turret shaft straight down onto the deck (the ornate flared base
        # lived in the attic and is not worth the geometry).
        c_wall = create_cylinder(bm, radius=tr_r, height=height, segments=segs,
                                 location=(tx, ty, z_base + height * 0.5),
                                 mat_index=MAT_INDEX_PLASTER_EXT)
        for f in c_wall:
            f.smooth = True
        # Single timber framing collar at the eaves.
        create_cylinder(bm, radius=tr_r + 0.04, height=0.08, segments=segs,
                        location=(tx, ty, z_base + height), mat_index=MAT_INDEX_TIMBER_FRAME)
        # Steep conical spire
        sp_h = height * 1.22
        cone_f = create_cone(bm, radius1=tr_r * 1.16, radius2=0.03, height=sp_h, segments=segs,
                             location=(tx, ty, z_base + height + sp_h * 0.5),
                             mat_index=MAT_INDEX_SHINGLES)
        for f in cone_f:
            f.smooth = True
        apply_roof_shingle_uvs(bm, cone_f, scale=0.32)
        # Golden pointed cap finial
        cone_cap = create_cone(bm, radius1=0.09, radius2=0.0, height=0.28, segments=12,
                               location=(tx, ty, z_base + height + sp_h + 0.14),
                               mat_index=MAT_INDEX_CUT_STONE)
        for f in cone_cap:
            f.smooth = True


def _hanging_corbel_banner(bm, x, y, z_top, facing_ang, banner_w=0.88, banner_h=1.45):
    """Hanging cloth banner suspended from an iron crossbar under the corbel overhang."""
    fx = math.cos(facing_ang)
    fy = math.sin(facing_ang)
    sx, sy = -fy, fx
    ang_side = math.atan2(sy, sx)

    bar_w = banner_w + 0.26
    bar_cx = x + fx * 0.08
    bar_cy = y + fy * 0.08
    bar_z = z_top - 0.12
    create_cylinder(bm, radius=0.024, height=bar_w, segments=8,
                    location=(bar_cx, bar_cy, bar_z),
                    rotation=(0.0, 1.5708, ang_side), mat_index=MAT_INDEX_IRON)
    for end_sign in (-1.0, 1.0):
        tip_x = bar_cx + sx * (bar_w * 0.5 * end_sign)
        tip_y = bar_cy + sy * (bar_w * 0.5 * end_sign)
        create_cone(bm, radius1=0.034, radius2=0.0, height=0.08, segments=6,
                    location=(tip_x, tip_y, bar_z),
                    rotation=(0.0, 1.5708 * end_sign, ang_side), mat_index=MAT_INDEX_IRON)

    hx = banner_w * 0.5
    cloth_t = 0.016
    cloth_cx = bar_cx + fx * 0.02
    cloth_cy = bar_cy + fy * 0.02
    cloth_top_z = bar_z - 0.04

    local_front = [
        Vector((-hx,  cloth_t * 0.5, 0.0)),
        Vector((-hx,  cloth_t * 0.5, -banner_h)),
        Vector(( hx,  cloth_t * 0.5, -banner_h)),
        Vector(( hx,  cloth_t * 0.5, 0.0)),
    ]
    local_back = [
        Vector(( hx, -cloth_t * 0.5, 0.0)),
        Vector(( hx, -cloth_t * 0.5, -banner_h)),
        Vector((-hx, -cloth_t * 0.5, -banner_h)),
        Vector((-hx, -cloth_t * 0.5, 0.0)),
    ]
    rot_mat = Matrix([
        [sx, fx, 0.0, 0.0],
        [sy, fy, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]
    ])
    loc_mat = Matrix.Translation(Vector((cloth_cx, cloth_cy, cloth_top_z)))
    tr = loc_mat @ rot_mat

    vf = [bm.verts.new(tr @ v) for v in local_front]
    vb = [bm.verts.new(tr @ v) for v in local_back]

    uv_layer = bm.loops.layers.uv.verify()
    ff = bm.faces.new(vf)
    ff.material_index = MAT_INDEX_BANNER
    ff.loops[0][uv_layer].uv = Vector((0.0, 1.0))
    ff.loops[1][uv_layer].uv = Vector((0.0, 0.0))
    ff.loops[2][uv_layer].uv = Vector((1.0, 0.0))
    ff.loops[3][uv_layer].uv = Vector((1.0, 1.0))

    fb = bm.faces.new(vb)
    fb.material_index = MAT_INDEX_BANNER
    fb.loops[0][uv_layer].uv = Vector((0.0, 1.0))
    fb.loops[1][uv_layer].uv = Vector((0.0, 0.0))
    fb.loops[2][uv_layer].uv = Vector((1.0, 0.0))
    fb.loops[3][uv_layer].uv = Vector((1.0, 1.0))


def _hanging_chain_lantern(bm, x, y, z_ceiling, chain_len=0.55, scale=0.90):
    """A forged iron lantern hanging straight down from a ceiling/soffit by an unbroken continuous chain."""
    s = scale
    w = 0.26 * s
    h = 0.36 * s
    hh = h * 0.5

    # 1. Ceiling mounting plate / boss
    create_cylinder(bm, radius=0.065 * s, height=0.024, segments=8,
                    location=(x, y, z_ceiling - 0.012), mat_index=MAT_INDEX_IRON)

    r_maj = 0.032 * s
    r_min = 0.0075 * s

    z_eyelet = z_ceiling - 0.036
    # Fixed ceiling eyelet ring (XZ plane)
    create_torus_ring(bm, location=(x, y, z_eyelet), rotation=(math.pi * 0.5, 0.0, 0.0),
                      major_radius=r_maj, minor_radius=r_min,
                      major_segments=12, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # 2. Lantern cage
    cz = z_ceiling - chain_len - 0.16 * s
    cage = _lantern_cage(bm, x, y, cz, size=w, height=h)
    _uv_faces(cage, bm)

    # The top suspension ring of _lantern_cage is at cz + hh + 0.27 (XZ plane)
    z_lantern_ring = cz + hh + 0.27

    # 3. Interlocking chain links bridging z_eyelet down to z_lantern_ring
    dist = z_eyelet - z_lantern_ring
    if dist > 0.04:
        target_step = 0.040 * s
        n_links = max(1, int(round(dist / target_step)) - 1)
        # Ensure odd number of links so last link (YZ plane) interlocks with lantern ring (XZ plane)
        if n_links % 2 == 0:
            n_links += 1
        step_z = dist / (n_links + 1)
        for li in range(1, n_links + 1):
            lz = z_eyelet - li * step_z
            rot = (0.0, math.pi * 0.5, 0.0) if (li % 2 == 1) else (math.pi * 0.5, 0.0, 0.0)
            create_torus_ring(bm, location=(x, y, lz), rotation=rot,
                              major_radius=r_maj, minor_radius=r_min,
                              major_segments=12, minor_segments=6,
                              mat_index=MAT_INDEX_IRON)


# =============================================================================
# CONTINUOUS GAP-FREE OVERHANG SOFFIT
# =============================================================================

# =============================================================================
# CONTINUOUS GAP-FREE OVERHANG SOFFIT & EXTERIOR STRING COURSES
# =============================================================================

def _build_seamless_soffit(bm, r_in, r_out, z_top, thickness=0.14, segments=48, offset=OFFSET):
    """Build a completely seamless, gap-free annular wooden soffit under the overhang."""
    z_bot = z_top - thickness
    d_ang = 2.0 * math.pi / segments

    verts_top_in = []
    verts_top_out = []
    verts_bot_in = []
    verts_bot_out = []

    for k in range(segments):
        ang = k * d_ang + offset
        ca, sa = math.cos(ang), math.sin(ang)
        verts_top_in.append(bm.verts.new((r_in * ca, r_in * sa, z_top)))
        verts_top_out.append(bm.verts.new((r_out * ca, r_out * sa, z_top)))
        verts_bot_in.append(bm.verts.new((r_in * ca, r_in * sa, z_bot)))
        verts_bot_out.append(bm.verts.new((r_out * ca, r_out * sa, z_bot)))

    uv_layer = bm.loops.layers.uv.verify()

    for k in range(segments):
        k_next = (k + 1) % segments
        # Underside face (the soffit visible from below) - clean quad with shared edge
        f_bot = bm.faces.new([verts_bot_in[k], verts_bot_out[k],
                              verts_bot_out[k_next], verts_bot_in[k_next]])
        f_bot.material_index = MAT_INDEX_WOOD
        f_bot.tag = True

        # Outer rim vertical face
        f_rim = bm.faces.new([verts_bot_out[k], verts_top_out[k],
                              verts_top_out[k_next], verts_bot_out[k_next]])
        f_rim.material_index = MAT_INDEX_TIMBER
        f_rim.tag = True

        # UV unwrap
        for lp in f_bot.loops:
            co = lp.vert.co
            lp[uv_layer].uv = Vector((co.x * 0.4, co.y * 0.4))
        for lp in f_rim.loops:
            co = lp.vert.co
            lp[uv_layer].uv = Vector((k * 0.25, co.z * 1.5))


def _build_exterior_annular_band(bm, r_in, r_out, z_bot, z_top, segments=48, offset=OFFSET, mat_index=MAT_INDEX_CUT_STONE):
    """Build an exterior-only annular trim ring without creating a solid disc through the interior."""
    d_ang = 2.0 * math.pi / segments
    verts_t_out = []
    verts_t_in = []
    verts_b_out = []
    verts_b_in = []
    for i in range(segments):
        a = i * d_ang + offset
        ca, sa = math.cos(a), math.sin(a)
        verts_t_out.append(bm.verts.new((r_out * ca, r_out * sa, z_top)))
        verts_t_in.append(bm.verts.new((r_in * ca, r_in * sa, z_top)))
        verts_b_out.append(bm.verts.new((r_out * ca, r_out * sa, z_bot)))
        verts_b_in.append(bm.verts.new((r_in * ca, r_in * sa, z_bot)))

    uv_layer = bm.loops.layers.uv.verify()
    faces = []
    for i in range(segments):
        ni = (i + 1) % segments
        # Top ring face
        f_top = bm.faces.new([verts_t_in[i], verts_t_out[i], verts_t_out[ni], verts_t_in[ni]])
        # Outer vertical face
        f_out = bm.faces.new([verts_b_out[i], verts_t_out[i], verts_t_out[ni], verts_b_out[ni]])
        # Bottom ring face
        f_bot = bm.faces.new([verts_b_in[i], verts_b_in[ni], verts_b_out[ni], verts_b_out[i]])
        for f in (f_top, f_out, f_bot):
            f.material_index = mat_index
            f.tag = True
            f.smooth = True
            for lp in f.loops:
                co = lp.vert.co
                lp[uv_layer].uv = Vector((co.x * 0.5, co.z * 0.5 if f == f_out else co.y * 0.5))
            faces.append(f)
    return faces


# =============================================================================
# WARCRAFT-STYLE EXTERIOR TIMBER SEAM PILLARS & FRAMING
# =============================================================================

def _build_exterior_seam_pillars(bm, r_shaft, z_base, z_top, bays=BAYS, offset=OFFSET,
                                 with_foot=True, with_collar=True):
    """Chunky beveled vertical timber pillars running up the exterior facet seams (Warcraft style).

    Frames the round stone cylinder into 8 intentional medieval bays and adds depth and majesty.
    Built per storey at that storey's radius so the pillar always follows the tower's
    taper (otherwise the lower, wider storeys swallow the pillar body entirely).
    """
    d_ang = 2.0 * math.pi / bays
    h = z_top - z_base
    w = 0.32
    d = 0.35
    foot_h = 0.44 if with_foot else 0.0
    collar_h = 0.28 if with_collar else 0.0

    for k in range(bays):
        ang = k * d_ang + offset
        ca, sa = math.cos(ang), math.sin(ang)
        post_r = r_shaft + 0.05
        px = post_r * ca
        py = post_r * sa

        # 1. Beveled Plinth Foot Block
        if with_foot:
            create_beveled_box(
                bm, size=(w * 1.30, d * 1.25, foot_h),
                location=(px, py, z_base + foot_h * 0.5),
                rotation=(0.0, 0.0, ang),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.014
            )

        # 2. Main Vertical Timber Pillar
        main_h = h - foot_h
        create_beveled_box(
            bm, size=(w, d, main_h),
            location=(px, py, z_base + foot_h + main_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.016
        )

        # 3. Capital / Collar right below the corbels
        if with_collar:
            create_beveled_box(
                bm, size=(w * 1.25, d * 1.20, collar_h),
                location=(px, py, z_top - collar_h * 0.5),
                rotation=(0.0, 0.0, ang),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
            )


def _build_belvedere_framing_posts(bm, bel_r, crown_z, roof_z, bays=BAYS, offset=OFFSET):
    """Vertical timber corner posts framing each white plaster bay on the crown observatory."""
    d_ang = 2.0 * math.pi / bays
    h = roof_z - crown_z
    w = 0.26
    d = 0.28

    for k in range(bays):
        ang = k * d_ang + offset
        ca, sa = math.cos(ang), math.sin(ang)
        post_r = bel_r + 0.02
        px = post_r * ca
        py = post_r * sa

        create_beveled_box(
            bm, size=(w, d, h),
            location=(px, py, crown_z + h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014
        )


# =============================================================================
# =============================================================================
# CONTINUOUS WALL RING WITH PRECISION WINDOW & DOOR OPENINGS (UNIFIED GRID)
# =============================================================================

def _build_seamless_wall_ring(bm, r_out, r_in, z0, z1, bays=BAYS, offset=OFFSET,
                              door_bay=None, door_w=1.40, door_h=2.60,
                              window_bays=set(), win_w=0.85, win_h=1.40,
                              mat_ext=MAT_INDEX_STONE, mat_int=MAT_INDEX_PLASTER_INT):
    """Build a smooth cylindrical wall ring with watertight door/window cutouts.

    Uses a unified vertex grid with shared height levels across ALL bays,
    eliminating T-junctions at opening boundaries so Blender auto-smooth
    produces 100% seamless curvature even around doors and windows.
    Each bay is subdivided into 6 angular slices for a 48-segment cylinder.
    """
    d_bay = 2.0 * math.pi / bays
    uv_layer = bm.loops.layers.uv.verify()

    # -- Compute unified Z levels shared by every bay boundary ----------------
    # Cut the wall openings a touch LARGER than the glazing/door aperture so the
    # frame casing (which laps a few cm over the opening) always covers the raw
    # masonry edge - otherwise the wall pokes through inside the window/door.
    cut_win_w = max(0.30, win_w + 0.02)
    cut_win_h = max(0.30, win_h + 0.02)
    cut_door_w = max(0.60, door_w + 0.10)
    cut_door_h = max(0.60, door_h + 0.10)

    levels = [z0, z1]
    z_dh = None
    if door_bay is not None:
        z_dh = z0 + cut_door_h
        if z0 < z_dh < z1:
            levels.append(z_dh)
    zw0 = zw1 = None
    if window_bays:
        w_cz = z0 + (z1 - z0) * 0.52
        zw0 = w_cz - cut_win_h * 0.5
        zw1 = w_cz + cut_win_h * 0.5
        if z0 < zw0 < z1:
            levels.append(zw0)
        if z0 < zw1 < z1:
            levels.append(zw1)
    levels = sorted(set(levels))
    n_levels = len(levels)

    # -- Pre-create boundary vertices at all bay junctions x all levels -------
    boundary = []
    for k in range(bays):
        ang = k * d_bay + offset
        ca, sa = math.cos(ang), math.sin(ang)
        col = [(bm.verts.new((r_out * ca, r_out * sa, lz)),
                bm.verts.new((r_in  * ca, r_in  * sa, lz)))
               for lz in levels]
        boundary.append(col)

    created_faces = []
    trim_faces = []

    for b in range(bays):
        bn = (b + 1) % bays
        a0 = b * d_bay + offset
        a1 = (b + 1) * d_bay + offset
        a_mid = (a0 + a1) * 0.5

        # -- Angular stations for this bay ------------------------------------
        if b == door_bay and z_dh is not None:
            da = 2.0 * math.asin(min(0.99, (cut_door_w * 0.5) / r_out))
            ad0 = a_mid - da * 0.5
            ad1 = a_mid + da * 0.5
            angles = [a0, (a0 + ad0) * 0.5, ad0, a_mid, ad1,
                      (ad1 + a1) * 0.5, a1]
        elif b in window_bays and zw0 is not None:
            da = 2.0 * math.asin(min(0.99, (cut_win_w * 0.5) / r_out))
            aw0a = a_mid - da * 0.5
            aw1a = a_mid + da * 0.5
            angles = [a0, (a0 + aw0a) * 0.5, aw0a, a_mid, aw1a,
                      (aw1a + a1) * 0.5, a1]
        else:
            angles = [a0 + i * (a1 - a0) / 6.0 for i in range(7)]

        n_st = len(angles)

        # -- Build vertex grid[station][level] = (v_out, v_in) ----------------
        grid = []
        for si in range(n_st):
            if si == 0:
                grid.append(boundary[b])
            elif si == n_st - 1:
                grid.append(boundary[bn])
            else:
                a = angles[si]
                ca, sa = math.cos(a), math.sin(a)
                col = [(bm.verts.new((r_out * ca, r_out * sa, lz)),
                        bm.verts.new((r_in  * ca, r_in  * sa, lz)))
                       for lz in levels]
                grid.append(col)

        # -- Determine which cells (slice, band) are openings -----------------
        opening = set()
        if b == door_bay and z_dh is not None and z_dh in levels:
            idx_dh = levels.index(z_dh)
            for s in (2, 3):
                for l in range(0, idx_dh):
                    opening.add((s, l))
        elif b in window_bays and zw0 is not None and zw1 is not None:
            if zw0 in levels and zw1 in levels:
                idx_w0 = levels.index(zw0)
                idx_w1 = levels.index(zw1)
                for s in (2, 3):
                    for l in range(idx_w0, idx_w1):
                        opening.add((s, l))

        # -- Create wall quads (outer + inner) for every non-opening cell -----
        for s in range(n_st - 1):
            for l in range(n_levels - 1):
                if (s, l) in opening:
                    continue
                fo = bm.faces.new([grid[s][l][0], grid[s+1][l][0],
                                   grid[s+1][l+1][0], grid[s][l+1][0]])
                fo.material_index = mat_ext
                fi = bm.faces.new([grid[s+1][l][1], grid[s][l][1],
                                   grid[s][l+1][1], grid[s+1][l+1][1]])
                fi.material_index = mat_int
                created_faces.extend([fo, fi])

        # -- Jamb, sill and lintel faces for openings -------------------------
        if b == door_bay and z_dh is not None and z_dh in levels:
            idx_dh = levels.index(z_dh)
            # Left jamb (station 2, facing right into opening)
            for l in range(0, idx_dh):
                f = bm.faces.new([grid[2][l][1], grid[2][l][0],
                                  grid[2][l+1][0], grid[2][l+1][1]])
                f.material_index = MAT_INDEX_CUT_STONE
                trim_faces.append(f)
            # Right jamb (station 4, facing left into opening)
            for l in range(0, idx_dh):
                f = bm.faces.new([grid[4][l][0], grid[4][l][1],
                                  grid[4][l+1][1], grid[4][l+1][0]])
                f.material_index = MAT_INDEX_CUT_STONE
                trim_faces.append(f)
            # Lintel underside (at z_dh, facing down)
            for s in (2, 3):
                f = bm.faces.new([grid[s][idx_dh][0], grid[s][idx_dh][1],
                                  grid[s+1][idx_dh][1], grid[s+1][idx_dh][0]])
                f.material_index = MAT_INDEX_CUT_STONE
                trim_faces.append(f)

        elif b in window_bays and zw0 is not None and zw1 is not None:
            if zw0 in levels and zw1 in levels:
                idx_w0 = levels.index(zw0)
                idx_w1 = levels.index(zw1)
                # Left jamb (station 2) - planar unwrap so the cut stone stays crisp
                for l in range(idx_w0, idx_w1):
                    f = bm.faces.new([grid[2][l][1], grid[2][l][0],
                                      grid[2][l+1][0], grid[2][l+1][1]])
                    f.material_index = MAT_INDEX_CUT_STONE
                    trim_faces.append(f)
                # Right jamb (station 4)
                for l in range(idx_w0, idx_w1):
                    f = bm.faces.new([grid[4][l][0], grid[4][l][1],
                                      grid[4][l+1][1], grid[4][l+1][0]])
                    f.material_index = MAT_INDEX_CUT_STONE
                    trim_faces.append(f)
                # Sill top face (at zw0, facing up)
                for s in (2, 3):
                    f = bm.faces.new([grid[s][idx_w0][0], grid[s+1][idx_w0][0],
                                      grid[s+1][idx_w0][1], grid[s][idx_w0][1]])
                    f.material_index = MAT_INDEX_CUT_STONE
                    trim_faces.append(f)
                # Header underside (at zw1, facing down)
                for s in (2, 3):
                    f = bm.faces.new([grid[s][idx_w1][0], grid[s][idx_w1][1],
                                      grid[s+1][idx_w1][1], grid[s+1][idx_w1][0]])
                    f.material_index = MAT_INDEX_CUT_STONE
                    trim_faces.append(f)

    # -- Smooth shading and continuous cylindrical UV mapping ------------------
    # UVs are unwrapped per face relative to its first loop, so a face that
    # straddles the 0/2pi seam can never stretch across the whole map (which
    # showed up as a bright smeared band on the front bay).
    u_scale = r_out * 0.45
    two_pi = 2.0 * math.pi
    for f in created_faces:
        f.smooth = True
        f.tag = True
        angs = []
        for lp in f.loops:
            co = lp.vert.co
            angs.append((math.atan2(co.y, co.x) - offset) % two_pi)
        a0 = angs[0]
        for lp, a in zip(f.loops, angs):
            while a - a0 > math.pi:
                a -= two_pi
            while a0 - a > math.pi:
                a += two_pi
            lp[uv_layer].uv = Vector((a * u_scale, lp.vert.co.z * 0.45))

    # Opening reveal faces (jambs, sills, lintels) stay hard-edged with a clean
    # planar unwrap so the stone reads crisp around every door and window.
    for f in trim_faces:
        f.smooth = False
        f.tag = True
    if trim_faces:
        map_planar_faces(bm, trim_faces, scale=0.5)

    return created_faces + trim_faces


# =============================================================================
# CONTINUOUS HELICAL SWEPT BEAM (ONE PIECE ALONG CURVE, 100% SEAMLESS)
# =============================================================================

def _sweep_helical_beam(bm, r_helix, theta_start, theta_end, z_start, z_end,
                        cross_w, cross_h, z_offset, mat_index,
                        segments=48):
    """Generate a continuous 3D helical swept beam along a circular arc.

    cross_w: Radial horizontal width of the beam.
    cross_h: Vertical height of the beam.
    z_offset: Vertical offset from the stair slope centerline to the beam center.
    mat_index: MAT_INDEX_TIMBER or MAT_INDEX_WOOD.

    Loop UVs are mapped so that wood grain flows strictly along the helical curve,
    accounting for the 90-degree shader rotation discrepancy between timber and wood.
    """
    uv_layer = bm.loops.layers.uv.verify()
    d_theta = theta_end - theta_start
    dz = z_end - z_start
    arc_len = abs(r_helix * d_theta)
    total_len = math.hypot(arc_len, dz)

    hw = cross_w * 0.5
    hh = cross_h * 0.5

    ring_verts = []
    station_s = []

    for k in range(segments + 1):
        t = k / segments
        ang = theta_start + t * d_theta
        z_c = z_start + t * dz + z_offset
        s_k = t * total_len
        station_s.append(s_k)

        ca, sa = math.cos(ang), math.sin(ang)
        r_out = r_helix + hw
        r_in  = r_helix - hw

        v0 = bm.verts.new((r_out * ca, r_out * sa, z_c + hh))
        v1 = bm.verts.new((r_in  * ca, r_in  * sa, z_c + hh))
        v2 = bm.verts.new((r_in  * ca, r_in  * sa, z_c - hh))
        v3 = bm.verts.new((r_out * ca, r_out * sa, z_c - hh))
        ring_verts.append((v0, v1, v2, v3))

    def _set_quad_uv(face, s0, s1, p0, p1):
        """Map length s->V and profile p->U so wood grain runs along the curve."""
        uvs = [
            Vector((p0 * 1.2, s0 * 0.45)),
            Vector((p1 * 1.2, s0 * 0.45)),
            Vector((p1 * 1.2, s1 * 0.45)),
            Vector((p0 * 1.2, s1 * 0.45)),
        ]
        for lp, uv in zip(face.loops, uvs):
            lp[uv_layer].uv = uv

    created_faces = []

    for k in range(segments):
        v_a = ring_verts[k]
        v_b = ring_verts[k + 1]
        s0 = station_s[k]
        s1 = station_s[k + 1]

        # Top face
        f_top = bm.faces.new([v_a[0], v_a[1], v_b[1], v_b[0]])
        _set_quad_uv(f_top, s0, s1, 0.0, cross_w)

        # Inner face
        f_in = bm.faces.new([v_a[1], v_a[2], v_b[2], v_b[1]])
        _set_quad_uv(f_in, s0, s1, 0.0, cross_h)

        # Bottom face
        f_bot = bm.faces.new([v_a[2], v_a[3], v_b[3], v_b[2]])
        _set_quad_uv(f_bot, s0, s1, 0.0, cross_w)

        # Outer face
        f_out = bm.faces.new([v_a[3], v_a[0], v_b[0], v_b[3]])
        _set_quad_uv(f_out, s0, s1, 0.0, cross_h)

        for f in (f_top, f_in, f_bot, f_out):
            f.material_index = mat_index
            f.smooth = True
            created_faces.append(f)

    # End caps
    f_start = bm.faces.new([ring_verts[0][3], ring_verts[0][2], ring_verts[0][1], ring_verts[0][0]])
    f_end   = bm.faces.new([ring_verts[-1][0], ring_verts[-1][1], ring_verts[-1][2], ring_verts[-1][3]])
    for f in (f_start, f_end):
        f.material_index = mat_index
        f.smooth = True
        for lp in f.loops:
            lp[uv_layer].uv = Vector((0.2, 0.2))
        created_faces.append(f)

    return created_faces


# =============================================================================
# CURVED WALL STAIRCASE (CONTINUOUS HELICAL RAILING, STEP 0 TO LANDING)
# =============================================================================

def _build_curved_wall_stairs(bm, cur_r, wall_t, z0, z1, start_ang_deg, arc_deg=135.0, stair_w=1.10):
    """Curved castle staircase running along the inside perimeter of the stone wall.

    - Treads hug the inner face of the wall.
    - Banister railing is shaped as one continuous 3D helical piece swept along the curve.
    - Railing runs completely from the ground step 0 all the way to the top floor landing.
    - Handrail cap (MAT_INDEX_WOOD) and timber beams (MAT_INDEX_TIMBER) both have longitudinal
      wood grain running along the curve with zero 90-deg rotation errors.
    - Sturdy vertical timber support pillars support the stairs from underneath.
    """
    dz = z1 - z0
    num_steps = max(14, int(dz / 0.19))
    step_h = dz / num_steps
    r_wall_in = cur_r - wall_t - 0.02
    r_stair_in = r_wall_in - stair_w
    r_mid = (r_wall_in + r_stair_in) * 0.5

    step_ang_rad = math.radians(arc_deg) / num_steps
    start_ang_rad = math.radians(start_ang_deg)
    tread_thick = 0.065

    # 1. Step treads hugging the outer wall. The floor slab itself is the top
    # landing, so we build one tread per riser *below* it (no flush top tread,
    # which would read as a missing step and coplanar-fight the floor).
    # The whole flight is shifted half a step toward the top (i + 1.5) so the
    # last tread lands exactly on the floor-opening edge - otherwise the top of
    # the flight stops short and leaves a hole where it passes through the floor.
    for i in range(num_steps - 1):
        mid_ang = start_ang_rad + (i + 1.5) * step_ang_rad
        cur_z = z0 + (i + 1) * step_h
        chord_mult = 1.08

        sx = r_mid * math.cos(mid_ang)
        sy = r_mid * math.sin(mid_ang)
        chord_w = 2.0 * r_mid * math.tan(step_ang_rad * 0.5) * chord_mult

        # Step wedge plank (UVs shifted per tread so the wood grain never repeats).
        tread_faces = create_beveled_box(
            bm, size=(stair_w, max(0.24, chord_w), tread_thick),
            location=(sx, sy, cur_z - tread_thick * 0.5),
            rotation=(0.0, 0.0, mid_ang),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
        )
        _shift_uvs(bm, tread_faces,
                   (i * 0.318 + start_ang_rad * 1.3) % 1.0,
                   (i * 0.211 + start_ang_rad * 0.7) % 1.0)

    # 2. Continuous 3D helical banister railing along the inner edge
    rail_h = 0.92
    theta_start = start_ang_rad + 0.5 * step_ang_rad
    theta_end = start_ang_rad + (num_steps - 0.5) * step_ang_rad
    z_start = z0 + step_h
    z_end = z1

    def _helix_z(theta):
        """Height of the (continuous) stair slope line at a given angle."""
        t = (theta - theta_start) / max(1e-6, (theta_end - theta_start))
        return z_start + t * (z_end - z_start)

    # Top of the dropped base stringer beam, so posts can sit down onto it.
    beam_top = -0.085 + 0.055

    # Continuous base stringer rail, dropped just below the tread line so it
    # reads as the beam carrying the treads rather than a rail on top of them.
    _sweep_helical_beam(bm, r_helix=r_stair_in,
                        theta_start=theta_start, theta_end=theta_end,
                        z_start=z_start, z_end=z_end,
                        cross_w=0.13, cross_h=0.11, z_offset=-0.085,
                        mat_index=MAT_INDEX_TIMBER, segments=48)

    # Continuous lower stringer rail
    _sweep_helical_beam(bm, r_helix=r_stair_in,
                        theta_start=theta_start, theta_end=theta_end,
                        z_start=z_start, z_end=z_end,
                        cross_w=0.07, cross_h=0.05, z_offset=0.28,
                        mat_index=MAT_INDEX_TIMBER, segments=48)

    # Continuous mid stringer rail
    _sweep_helical_beam(bm, r_helix=r_stair_in,
                        theta_start=theta_start, theta_end=theta_end,
                        z_start=z_start, z_end=z_end,
                        cross_w=0.07, cross_h=0.05, z_offset=0.52,
                        mat_index=MAT_INDEX_TIMBER, segments=48)

    # Continuous main handrail beam (under cap)
    _sweep_helical_beam(bm, r_helix=r_stair_in,
                        theta_start=theta_start, theta_end=theta_end,
                        z_start=z_start, z_end=z_end,
                        cross_w=0.13, cross_h=0.09, z_offset=rail_h - 0.06,
                        mat_index=MAT_INDEX_TIMBER, segments=48)

    # Continuous wide handrail cap board (light wood, with longitudinal wood grain along curve)
    _sweep_helical_beam(bm, r_helix=r_stair_in,
                        theta_start=theta_start, theta_end=theta_end,
                        z_start=z_start, z_end=z_end,
                        cross_w=0.19, cross_h=0.045, z_offset=rail_h + 0.015,
                        mat_index=MAT_INDEX_WOOD, segments=48)

    # 3. Sturdy Newel Posts at start (floor z0) and stop (floor z1)
    # A. Bottom Newel Post: firmly rooted on floor z0 at step 0
    p0_x = r_stair_in * math.cos(theta_start)
    p0_y = r_stair_in * math.sin(theta_start)
    bot_post_h = step_h + rail_h + 0.10
    create_beveled_box(bm, size=(0.16, 0.16, bot_post_h),
                       location=(p0_x, p0_y, z0 + bot_post_h * 0.5),
                       rotation=(0.0, 0.0, theta_start),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)
    create_beveled_box(bm, size=(0.22, 0.22, 0.05),
                       location=(p0_x, p0_y, z0 + bot_post_h + 0.005),
                       rotation=(0.0, 0.0, theta_start),
                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

    # B. Top Newel Post: firmly rooted on floor z1 at landing
    p1_x = r_stair_in * math.cos(theta_end)
    p1_y = r_stair_in * math.sin(theta_end)
    top_post_h = rail_h + 0.10
    create_beveled_box(bm, size=(0.16, 0.16, top_post_h),
                       location=(p1_x, p1_y, z1 + top_post_h * 0.5),
                       rotation=(0.0, 0.0, theta_end),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)
    create_beveled_box(bm, size=(0.22, 0.22, 0.05),
                       location=(p1_x, p1_y, z1 + top_post_h + 0.005),
                       rotation=(0.0, 0.0, theta_end),
                       mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

    # 4. Vertical balusters / pickets placed at every step
    for i in range(num_steps - 1):
        mid_ang = start_ang_rad + (i + 1.5) * step_ang_rad
        cur_z = z0 + (i + 1) * step_h
        px = r_stair_in * math.cos(mid_ang)
        py = r_stair_in * math.sin(mid_ang)
        # Balusters run from the handrail down onto the base stringer beam.
        top_z = cur_z + 0.09 + (rail_h - 0.18)
        bot_z = _helix_z(mid_ang) + beam_top
        if top_z - bot_z > 0.20:
            create_beveled_box(bm, size=(0.075, 0.075, top_z - bot_z),
                               location=(px, py, (top_z + bot_z) * 0.5),
                               rotation=(0.0, 0.0, mid_ang),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)

    # 5. Intermediate structural posts along the flight
    for frac in (0.33, 0.67):
        i_step = int((num_steps - 1) * frac)
        p_ang = start_ang_rad + (i_step + 1.5) * step_ang_rad
        pz = z0 + (i_step + 1) * step_h
        px = r_stair_in * math.cos(p_ang)
        py = r_stair_in * math.sin(p_ang)
        # Intermediate posts drop all the way down onto the base stringer beam.
        top_z = pz + rail_h
        bot_z = _helix_z(p_ang) + beam_top
        create_beveled_box(bm, size=(0.09, 0.09, top_z - bot_z),
                           location=(px, py, (top_z + bot_z) * 0.5),
                           rotation=(0.0, 0.0, p_ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # 6. Sturdy interior timber support pillars under the stairs
    support_fractions = [0.35, 0.72]
    for sf in support_fractions:
        step_idx = int((num_steps - 1) * sf)
        p_ang = start_ang_rad + (step_idx + 1.5) * step_ang_rad
        p_z = z0 + (step_idx + 1) * step_h
        post_r = r_stair_in + 0.08
        px = post_r * math.cos(p_ang)
        py = post_r * math.sin(p_ang)
        h_total = p_z - tread_thick - z0
        if h_total > 0.60:
            foot_h = min(0.35, h_total * 0.20)
            col_h = h_total - foot_h - 0.12
            # 1. Beveled timber base foot collar (no stone plinth indoors on wood floor!)
            create_beveled_box(bm, size=(0.26, 0.26, foot_h),
                               location=(px, py, z0 + foot_h * 0.5),
                               rotation=(0.0, 0.0, p_ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            # 2. Heavy vertical timber post
            create_beveled_box(bm, size=(0.18, 0.18, col_h),
                               location=(px, py, z0 + foot_h + col_h * 0.5),
                               rotation=(0.0, 0.0, p_ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            # 3. Capital collar bracket under the stair stringer
            create_beveled_box(bm, size=(0.28, 0.28, 0.12),
                               location=(px, py, p_z - tread_thick - 0.06),
                               rotation=(0.0, 0.0, p_ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
            # 4. Diagonal timber brace out to the step
            out_x = px + math.cos(p_ang) * 0.28
            out_y = py + math.sin(p_ang) * 0.28
            _beam(bm, (px, py), (out_x, out_y),
                  p_z - tread_thick - 0.45, p_z - tread_thick - 0.02,
                  0.10, 0.09, MAT_INDEX_TIMBER, bevel=0.008)


# =============================================================================
# UNIFIED TIMBER FLOOR SLAB WITH OPEN STAIRWELL CUTOUT
# =============================================================================

def _build_watertight_floor(bm, r_floor, z_floor, stair_arc=None, shaft_r_in=None,
                            thickness=0.14, segments=32, offset=0.0,
                            stair_inner_r=None, stair_outer_r=None):
    """Build a unified gap-free timber floor slab with an open stairwell cutout.

    - The entire floor and ceiling is built as a single unified radial disc:
      Zero concentric seams, 100% consistent material and plank texture.
    - If stair_arc is provided (s_deg, e_deg):
      The opening is cut out over the stair ascent arc [e_deg - 75 deg, e_deg].
      The cutout is strictly sized to shaft_r_in (not r_floor), so that on the
      top belvedere overhang floor, the stairs emerge cleanly into the room without
      being covered by the belvedere floor!
      The cutout ends precisely at e_deg, where the top step meets the solid floor
      landing with zero gaps!
    - Protective wooden guard railing is built along the inner curved opening edge.
    """
    if shaft_r_in is None:
        shaft_r_in = r_floor
    stair_w = 1.10
    if stair_inner_r is None:
        stair_inner_r = shaft_r_in - stair_w
    if stair_outer_r is None:
        stair_outer_r = shaft_r_in
    # The opening hugs the stair footprint exactly (no radial sliver showing the
    # storey below through the floor edge).
    r_cut_in = max(0.6, stair_inner_r - 0.02)
    r_cut_out = min(r_floor, stair_outer_r)
    has_outer_ring = (r_floor > r_cut_out + 0.08)

    z_top = z_floor
    z_bot = z_floor - thickness

    N = max(24, segments)
    d_ang = 2.0 * math.pi / N
    uv_layer = bm.loops.layers.uv.verify()

    cut_s_deg = 0.0
    cut_e_deg = 0.0
    if stair_arc is not None:
        s_deg = stair_arc[0] % 360.0
        e_deg = stair_arc[1] % 360.0
        cut_s_deg = (e_deg - 42.0) % 360.0
        cut_e_deg = e_deg % 360.0

    def in_cut(ang):
        if stair_arc is None:
            return False
        a = ang % 360.0
        s = cut_s_deg
        e = cut_e_deg
        if s <= e:
            return s <= a <= e
        else:
            return a >= s or a <= e

    v_c_top = bm.verts.new((0.0, 0.0, z_top))
    v_c_bot = bm.verts.new((0.0, 0.0, z_bot))

    sector_cut = []
    for j in range(N):
        ang_mid = math.degrees((j + 0.5) * d_ang + offset) % 360.0
        sector_cut.append(in_cut(ang_mid))

    created_faces = []

    for j in range(N):
        jn = (j + 1) % N
        a0 = j * d_ang + offset
        a1 = (j + 1) * d_ang + offset
        ca0, sa0 = math.cos(a0), math.sin(a0)
        ca1, sa1 = math.cos(a1), math.sin(a1)

        is_c = sector_cut[j]

        if not is_c:
            # Full solid sector from 0 to r_floor
            vt0 = bm.verts.new((r_floor * ca0, r_floor * sa0, z_top))
            vt1 = bm.verts.new((r_floor * ca1, r_floor * sa1, z_top))
            vb0 = bm.verts.new((r_floor * ca0, r_floor * sa0, z_bot))
            vb1 = bm.verts.new((r_floor * ca1, r_floor * sa1, z_bot))

            ft = bm.faces.new([v_c_top, vt0, vt1])
            fb = bm.faces.new([v_c_bot, vb1, vb0])
            fe = bm.faces.new([vb0, vb1, vt1, vt0])

            ft.material_index = MAT_INDEX_FLOOR
            fb.material_index = MAT_INDEX_WOOD
            fe.material_index = MAT_INDEX_TIMBER
            created_faces.extend([ft, fb, fe])
        else:
            # 1. Inner solid sector from 0 to r_cut_in
            vi_t0 = bm.verts.new((r_cut_in * ca0, r_cut_in * sa0, z_top))
            vi_t1 = bm.verts.new((r_cut_in * ca1, r_cut_in * sa1, z_top))
            vi_b0 = bm.verts.new((r_cut_in * ca0, r_cut_in * sa0, z_bot))
            vi_b1 = bm.verts.new((r_cut_in * ca1, r_cut_in * sa1, z_bot))

            fit = bm.faces.new([v_c_top, vi_t0, vi_t1])
            fib = bm.faces.new([v_c_bot, vi_b1, vi_b0])
            fie = bm.faces.new([vi_b1, vi_b0, vi_t0, vi_t1])

            fit.material_index = MAT_INDEX_FLOOR
            fib.material_index = MAT_INDEX_WOOD
            fie.material_index = MAT_INDEX_TIMBER
            created_faces.extend([fit, fib, fie])

            # 2. Outer solid ring (if belvedere overhang outside shaft)
            if has_outer_ring:
                vo_t0 = bm.verts.new((r_cut_out * ca0, r_cut_out * sa0, z_top))
                vo_t1 = bm.verts.new((r_cut_out * ca1, r_cut_out * sa1, z_top))
                vo_b0 = bm.verts.new((r_cut_out * ca0, r_cut_out * sa0, z_bot))
                vo_b1 = bm.verts.new((r_cut_out * ca1, r_cut_out * sa1, z_bot))

                vf_t0 = bm.verts.new((r_floor * ca0, r_floor * sa0, z_top))
                vf_t1 = bm.verts.new((r_floor * ca1, r_floor * sa1, z_top))
                vf_b0 = bm.verts.new((r_floor * ca0, r_floor * sa0, z_bot))
                vf_b1 = bm.verts.new((r_floor * ca1, r_floor * sa1, z_bot))

                fot = bm.faces.new([vo_t0, vf_t0, vf_t1, vo_t1])
                fob = bm.faces.new([vo_b1, vf_b1, vf_b0, vo_b0])
                fo_in = bm.faces.new([vo_b0, vo_b1, vo_t1, vo_t0])
                fo_out = bm.faces.new([vf_b0, vf_b1, vf_t1, vf_t0])

                fot.material_index = MAT_INDEX_FLOOR
                fob.material_index = MAT_INDEX_WOOD
                fo_in.material_index = MAT_INDEX_TIMBER
                fo_out.material_index = MAT_INDEX_TIMBER
                created_faces.extend([fot, fob, fo_in, fo_out])

        # Boundary radial face at cutout transitions
        jp = (j - 1) % N
        if sector_cut[jp] != sector_cut[j]:
            v_rad_i_t = bm.verts.new((r_cut_in * ca0, r_cut_in * sa0, z_top))
            v_rad_i_b = bm.verts.new((r_cut_in * ca0, r_cut_in * sa0, z_bot))
            v_rad_o_t = bm.verts.new((r_cut_out * ca0, r_cut_out * sa0, z_top))
            v_rad_o_b = bm.verts.new((r_cut_out * ca0, r_cut_out * sa0, z_bot))

            if sector_cut[j]:
                frad = bm.faces.new([v_rad_i_b, v_rad_o_b, v_rad_o_t, v_rad_i_t])
            else:
                frad = bm.faces.new([v_rad_o_b, v_rad_i_b, v_rad_i_t, v_rad_o_t])
            frad.material_index = MAT_INDEX_TIMBER
            created_faces.append(frad)

    # UV unwrap
    for f in created_faces:
        f.tag = True
        for lp in f.loops:
            co = lp.vert.co
            if f.material_index in (MAT_INDEX_FLOOR, MAT_INDEX_WOOD):
                lp[uv_layer].uv = Vector((co.x * 0.45, co.y * 0.45))
            else:
                lp[uv_layer].uv = Vector((co.x * 0.5, co.z * 1.5))

    # -------------------------------------------------------------------------
    # Protective guard railing around the stair opening, built with the very
    # same joinery as the staircase banister: a few continuous swept rails plus
    # chunky posts and balusters (bigger, singular parts - no fiddly add-ons).
    # It closes the whole lip: the inner arc AND the radial back edge, so the
    # opening is fully fenced.
    # -------------------------------------------------------------------------
    if stair_arc is not None:
        # Snap the railing to the *actual* cutout boundaries (the opening is
        # quantised to whole sectors), so no unfenced sliver is left open.
        cut_idx = [j for j in range(N) if sector_cut[j]]
        if cut_idx:
            cut_s_deg = math.degrees(min(cut_idx) * d_ang + offset) % 360.0
            cut_e_deg = math.degrees((max(cut_idx) + 1) * d_ang + offset) % 360.0
        r_rail = r_cut_in - 0.05
        th_s = math.radians(cut_s_deg)
        th_e = math.radians(cut_e_deg)
        if th_e <= th_s:
            th_e += 2.0 * math.pi
        h = 0.92
        n_seg = 14
        for (cw, ch_, zo, m) in ((0.12, 0.09, 0.05, MAT_INDEX_TIMBER),
                                 (0.07, 0.05, 0.52, MAT_INDEX_TIMBER),
                                 (0.13, 0.09, h - 0.06, MAT_INDEX_TIMBER),
                                 (0.19, 0.045, h + 0.015, MAT_INDEX_WOOD)):
            _sweep_helical_beam(bm, r_helix=r_rail, theta_start=th_s, theta_end=th_e,
                                z_start=z_floor, z_end=z_floor, cross_w=cw, cross_h=ch_,
                                z_offset=zo, mat_index=m, segments=n_seg)

        def _guard_post(px, py, ang):
            create_beveled_box(bm, size=(0.15, 0.15, h + 0.10),
                               location=(px, py, z_floor + (h + 0.10) * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.014)
            create_beveled_box(bm, size=(0.21, 0.21, 0.05),
                               location=(px, py, z_floor + h + 0.115),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)

        for ta in (th_s, th_e):
            _guard_post(r_rail * math.cos(ta), r_rail * math.sin(ta), ta)

        n_bal = 3
        for k in range(1, n_bal + 1):
            ta = th_s + (th_e - th_s) * (k / (n_bal + 1))
            create_beveled_box(bm, size=(0.09, 0.09, h - 0.16),
                               location=(r_rail * math.cos(ta), r_rail * math.sin(ta),
                                         z_floor + 0.05 + (h - 0.16) * 0.5),
                               rotation=(0.0, 0.0, ta),
                               mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)

        # Radial return fencing the free (back) edge of the opening.
        p_in = (r_rail * math.cos(th_s), r_rail * math.sin(th_s))
        r_outb = r_cut_out + 0.02
        p_out = (r_outb * math.cos(th_s), r_outb * math.sin(th_s))
        for (cw, ch_, zo, m) in ((0.12, 0.09, 0.05, MAT_INDEX_TIMBER),
                                 (0.07, 0.05, 0.52, MAT_INDEX_TIMBER),
                                 (0.13, 0.09, h - 0.06, MAT_INDEX_TIMBER),
                                 (0.19, 0.045, h + 0.015, MAT_INDEX_WOOD)):
            _beam(bm, p_in, p_out, z_floor + zo, z_floor + zo, cw, ch_, m, bevel=0.010)
        _guard_post((p_in[0] + p_out[0]) * 0.5, (p_in[1] + p_out[1]) * 0.5, th_s)


# =============================================================================
# MAIN MAGE TOWER GENERATOR
# =============================================================================

def build_mage_tower(bm, props, seed):
    """Build the authentic whimsical fantasy Mage Tower."""
    wall_t = props.wall_thickness
    found_h = props.foundation_height if props.has_foundation else 0.5
    R = max(3.8, props.width * 0.46)
    level_h = max(4.6, props.floor_height)
    levels = max(3, props.num_floors)

    # Grand entrance dimensions
    door_w = 1.45
    door_h = 2.60
    win_w = min(0.92, getattr(props, 'window_width', 0.85))
    win_h = min(1.65, getattr(props, 'window_height', 1.40))

    # -------------------------------------------------------------------------
    # 1. Stepped Stone Plinth (Solid masonry foundation - keep smooth round look)
    # -------------------------------------------------------------------------
    if props.has_foundation:
        create_cylinder(bm, radius=R + 0.75, height=found_h * 0.5, segments=48,
                        location=(0.0, 0.0, found_h * 0.25), mat_index=MAT_INDEX_CUT_STONE)
        create_cylinder(bm, radius=R + 0.42, height=found_h * 0.5, segments=48,
                        location=(0.0, 0.0, found_h * 0.75), mat_index=MAT_INDEX_STONE)

    # -------------------------------------------------------------------------
    # 2. Lower Tower Shaft Storeys (Sturdy stone masonry)
    # -------------------------------------------------------------------------
    shaft_storeys = levels - 1

    # Stair flight trajectory along the inner wall with comfortable landing gaps
    stair_configs = []
    for fl in range(shaft_storeys):
        s_ang = (-30.0 + fl * 200.0) % 360.0
        e_ang = (s_ang + 135.0) % 360.0
        stair_configs.append((s_ang, e_ang))

    for fl in range(shaft_storeys):
        z0 = found_h + fl * level_h
        z1 = z0 + level_h
        cur_r = R - fl * 0.08
        r_inner = cur_r - wall_t

        # --- Solid unified floor (zero concentric seams, with stairwell cutout) ---
        if fl == 0:
            create_cylinder(bm, radius=r_inner, height=0.14, segments=48,
                            location=(0.0, 0.0, z0 + 0.07), mat_index=MAT_INDEX_STONE)
        else:
            prev_stair_arc = stair_configs[fl - 1]
            prev_wall_in = (R - (fl - 1) * 0.08) - wall_t - 0.02
            _build_watertight_floor(bm, r_floor=r_inner, z_floor=z0 + 0.14,
                                    stair_arc=prev_stair_arc, shaft_r_in=r_inner,
                                    thickness=0.14, segments=48, offset=OFFSET,
                                    stair_inner_r=prev_wall_in - 1.10,
                                    stair_outer_r=prev_wall_in)

        # --- Curved castle staircase along the wall with interior support pillars ---
        s_ang_deg, _ = stair_configs[fl]
        _build_curved_wall_stairs(bm, cur_r=cur_r, wall_t=wall_t, z0=z0 + 0.14, z1=z1 + 0.14,
                                  start_ang_deg=s_ang_deg, arc_deg=135.0, stair_w=1.10)

        # --- Openings configuration ---
        door_k = 0 if (fl == 0 and props.has_front_door) else None
        win_facets = {k for k in ((2, 4, 6) if fl == 0 else (0, 2, 4, 6)) if (props.has_windows and k != door_k)}

        # Continuous smooth stone wall ring with precision cutouts (8 bays, 48 segments)
        _build_seamless_wall_ring(bm, r_out=cur_r, r_in=r_inner, z0=z0, z1=z1,
                                  bays=BAYS, offset=OFFSET,
                                  door_bay=door_k, door_w=door_w, door_h=door_h,
                                  window_bays=win_facets, win_w=win_w, win_h=win_h,
                                  mat_ext=MAT_INDEX_STONE, mat_int=MAT_INDEX_PLASTER_INT)

        # Front Door Assembly (projected slightly proud to eliminate any coplanar overlaps)
        if door_k is not None:
            a_door = (door_k + 0.5) * BAY_ANG + OFFSET
            # A full-depth portal casing: it spans the whole wall so its stone
            # architrave is proud on BOTH faces - covering the outer wall and the
            # inner wall - rather than floating on one side.
            door_proud = 0.05
            door_margin = 0.08
            door_r = cur_r - (wall_t + door_margin - door_proud) * 0.5
            dx = door_r * math.cos(a_door)
            dy = door_r * math.sin(a_door)
            build_door_assembly(bm, center_x=dx, y_front=dy, z_base=z0,
                                wall_thickness=wall_t + door_proud + door_margin - 0.06,
                                door_w=door_w, door_h=door_h,
                                door_angle_deg=getattr(props, 'door_angle', 0.0),
                                door_shape='ARCHED', ground_floor_stone=True)
            if props.has_front_steps and props.has_foundation:
                build_front_steps(bm, center_x=dx, y_front=cur_r * math.sin(a_door),
                                  z_base=z0, num_steps=max(2, int(found_h / 0.18)))

        # Windows with stone sills & frames
        for wk in win_facets:
            a_win = (wk + 0.5) * BAY_ANG + OFFSET
            # Seated 20 cm into the wall (recessed reveal).
            w_r = cur_r - 0.20
            wx = w_r * math.cos(a_win)
            wy = w_r * math.sin(a_win)
            build_window_assembly(bm, center=(wx, wy, z0 + level_h * 0.52),
                                  size=(win_w, win_h), wall_thickness=wall_t,
                                  normal_axis=(math.cos(a_win), math.sin(a_win)), has_shutters=False)

        # Exterior-only stone string course band between storeys (keep smooth round look)
        _build_exterior_annular_band(bm, r_in=cur_r - 0.02, r_out=cur_r + 0.08,
                                    z_bot=z1 - 0.12, z_top=z1,
                                    segments=48, offset=OFFSET, mat_index=MAT_INDEX_CUT_STONE)

        # Warcraft-style chunky timber seam pillars at THIS storey's radius so
        # they follow the taper and stay proud of the wall on every level.
        _build_exterior_seam_pillars(bm, r_shaft=cur_r, z_base=z0, z_top=z1,
                                    bays=BAYS, offset=OFFSET,
                                    with_foot=(fl == 0),
                                    with_collar=(fl == shaft_storeys - 1))

    # -------------------------------------------------------------------------
    # 3. Cantilevered Belvedere / Crown (Archmage Observatory)
    # -------------------------------------------------------------------------
    top_shaft_r = R - (shaft_storeys - 1) * 0.08
    crown_z = found_h + shaft_storeys * level_h
    # Dramatic overhang: ~1.32x shaft radius (matching Reference Image 2)
    bel_r = top_shaft_r + 1.28
    bel_h = max(3.4, level_h * 0.75)
    soffit_thickness = 0.14
    # The crown floor slab (below) is the single wooden ceiling/soffit; the
    # corbels sit directly underneath it, aligned with the 8 seam pillars.
    corbel_z = crown_z

    # --- Ring of Chunky Carved Timber Corbels (Directly Aligned with 8 Seam Pillars) ---
    corbel_depth = bel_r - top_shaft_r + 0.12
    for k in range(BAYS):
        ang = k * BAY_ANG + OFFSET  # Aligned directly with the 8 vertical seam pillars!
        c_pos = Vector((top_shaft_r * math.cos(ang), top_shaft_r * math.sin(ang), corbel_z))
        f_dir = (math.cos(ang), math.sin(ang), 0.0)
        create_curved_corbel(bm, loc=c_pos, facing_dir=f_dir,
                             width=0.28, depth=corbel_depth, height=0.96,
                             mat_index=MAT_INDEX_TIMBER)

    # --- Hanging Banners Centered Between Pillars Under Corbels ---
    banner_facets = (2, 6)
    for bf in banner_facets:
        b_ang = (bf + 0.5) * BAY_ANG + OFFSET
        bx = (bel_r - 0.18) * math.cos(b_ang)
        by = (bel_r - 0.18) * math.sin(b_ang)
        _hanging_corbel_banner(bm, bx, by, corbel_z, facing_ang=b_ang,
                               banner_w=0.85, banner_h=1.60)

    # --- Hanging Chain Lanterns Centered in Front and Rear Bays ---
    for lf in (0, 4):
        l_ang = (lf + 0.5) * BAY_ANG + OFFSET
        lx = (bel_r - 0.22) * math.cos(l_ang)
        ly = (bel_r - 0.22) * math.sin(l_ang)
        _hanging_chain_lantern(bm, lx, ly, z_ceiling=corbel_z, chain_len=0.55, scale=0.90)

    # --- Top Floor Crown Slab (single unified slab: interior floor AND the
    # overhang soffit, with the precise stairwell cutout and guard railing) ---
    inner_bel_r = bel_r - wall_t
    top_stair_arc = stair_configs[-1]
    shaft_r_in = top_shaft_r - wall_t
    top_wall_in = top_shaft_r - wall_t - 0.02
    _build_watertight_floor(bm, r_floor=bel_r + 0.04, z_floor=crown_z + 0.14,
                            stair_arc=top_stair_arc, shaft_r_in=shaft_r_in,
                            thickness=soffit_thickness, segments=48, offset=OFFSET,
                            stair_inner_r=top_wall_in - 1.10,
                            stair_outer_r=top_wall_in)

    # --- Crown Walls: Continuous Smooth Plaster with Precision Cutouts (8 bays, 48 segments) ---
    crown_win_facets = {0, 2, 4, 6}
    _build_seamless_wall_ring(bm, r_out=bel_r, r_in=inner_bel_r,
                              z0=crown_z, z1=crown_z + bel_h,
                              bays=BAYS, offset=OFFSET,
                              window_bays=crown_win_facets,
                              win_w=win_w, win_h=win_h,
                              mat_ext=MAT_INDEX_PLASTER_EXT, mat_int=MAT_INDEX_PLASTER_INT)

    # --- Belvedere Timber Corner Framing Posts (Covering Plaster Seams on 8 bays) ---
    _build_belvedere_framing_posts(bm, bel_r=bel_r, crown_z=crown_z, roof_z=crown_z + bel_h,
                                  bays=BAYS, offset=OFFSET)

    # Belvedere exterior timber string courses (horizontal only, never interior!)
    _build_exterior_annular_band(bm, r_in=bel_r - 0.02, r_out=bel_r + 0.08,
                                z_bot=crown_z - 0.02, z_top=crown_z + 0.13,
                                segments=48, offset=OFFSET, mat_index=MAT_INDEX_TIMBER)
    _build_exterior_annular_band(bm, r_in=bel_r - 0.02, r_out=bel_r + 0.08,
                                z_bot=crown_z + bel_h - 0.12, z_top=crown_z + bel_h,
                                segments=48, offset=OFFSET, mat_index=MAT_INDEX_TIMBER)

    # Arched leaded windows with warm glowing glass
    for wk in crown_win_facets:
        a_win = (wk + 0.5) * BAY_ANG + OFFSET
        # Seated 20 cm into the wall (recessed reveal).
        w_r = bel_r - 0.20
        wx = w_r * math.cos(a_win)
        wy = w_r * math.sin(a_win)
        build_window_assembly(bm, center=(wx, wy, crown_z + bel_h * 0.52),
                              size=(win_w, win_h), wall_thickness=wall_t,
                              normal_axis=(math.cos(a_win), math.sin(a_win)), has_shutters=False)

    # -------------------------------------------------------------------------
    # 4. Roof, Spires, Tourelles & Orbiting Arcane Crystals
    # -------------------------------------------------------------------------
    roof_z = crown_z + bel_h
    roof_h = max(5.8, level_h * 1.25)

    # Main flared witch-hat spire (round smooth look)
    _witch_hat_roof(bm, 0.0, 0.0, roof_z, radius=bel_r, height=roof_h, segments=48)

    # 4 high-poly smooth corner tourelles / pinnacles around the eaves (matching Image 2).
    # Seated just above the eaves fascia so they no longer punch through the soffit wood.
    _corner_tourelles(bm, 0.0, 0.0, roof_z + 0.16, bel_r, height=2.30)

    # Floating orbiting arcane crystal shards (matching Images 4 & 5)
    _floating_arcane_shards(bm, 0.0, 0.0, roof_z, bel_r)


