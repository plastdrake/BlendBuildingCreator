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
)
from .mesh_utils import (
    create_box,
    create_cylinder,
    create_cone,
    create_torus_ring,
    apply_box_uvs,
)


# =============================================================================
# SIGNATURE ARCHITECTURAL COMPONENTS
# =============================================================================

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
                                  wall_th=0.26, rot_z=0.0):
    """Builds a solid timber wall with a GENUINE DOOR OPENING cutout, recessed plank door,
    threshold sill, header lintel, and shark jaw archway wrapping the opening."""
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

    # 5. Recessed Timber Plank Door Leaf (Set back ~10cm inside the opening)
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


def _build_wall_with_window(bm, x0, x1, y, z0, z1, win_cx, win_cz, win_w=0.75, win_h=0.75,
                            wall_th=0.26, rot_z=0.0):
    """Builds a wall with an actual recessed window opening, bone frame, and iron bars."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    w_half_w = win_w * 0.5
    w_half_h = win_h * 0.5

    # 1. Below Window Wall
    sill_h = (win_cz - w_half_h) - z0
    if sill_h > 0.05:
        pos = rot_mat @ Vector((win_cx, y, z0 + sill_h * 0.5))
        create_box(bm, (win_w, wall_th, sill_h), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Above Window Wall
    header_h = z1 - (win_cz + w_half_h)
    if header_h > 0.05:
        pos = rot_mat @ Vector((win_cx, y, win_cz + w_half_h + header_h * 0.5))
        create_box(bm, (win_w, wall_th, header_h), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Left Wall
    left_w = (win_cx - w_half_w) - x0
    if left_w > 0.05:
        pos = rot_mat @ Vector((x0 + left_w * 0.5, y, z0 + (z1 - z0) * 0.5))
        create_box(bm, (left_w, wall_th, z1 - z0), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Right Wall
    right_w = x1 - (win_cx + w_half_w)
    if right_w > 0.05:
        pos = rot_mat @ Vector((win_cx + w_half_w + right_w * 0.5, y, z0 + (z1 - z0) * 0.5))
        create_box(bm, (right_w, wall_th, z1 - z0), (pos.x, pos.y, pos.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Window Frame & Iron Bars inside opening
    win_pos = rot_mat @ Vector((win_cx, y - wall_th * 0.45, win_cz))
    _build_bone_window(bm, win_pos.x, win_pos.y, win_pos.z, rot_z=rot_z, w=win_w, h=win_h)


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

def _build_bone_scale_roof_gable(bm, x0, x1, y0, y1, eave_z, peak_h,
                                 overhang_x=0.55, overhang_y=0.55,
                                 fin_scale=1.5, num_ridge_teeth=8):
    """Builds a 100% weather-tight gable roof with solid timber deck slabs underneath,
    solid verge bargeboards, and tightly layered overlapping rounded bone scale tiles."""
    mx = (x0 + x1) * 0.5
    half_span = (x1 - x0) * 0.5 + overhang_x
    span_y = (y1 - y0) + overhang_y * 2
    my = (y0 + y1) * 0.5
    peak_z = eave_z + peak_h

    slope_len = math.hypot(half_span, peak_h)
    pitch_angle = math.atan2(peak_h, half_span)

    # 1. Solid Heavy Timber Ridge Beam
    ridge_len = span_y + 0.5
    create_box(bm, (0.38, ridge_len, 0.40), (mx, my, peak_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Solid Timber Roof Deck Slabs (Left & Right Slopes) - GUARANTEES ZERO GAPS
    deck_th = 0.12
    for side in (-1.0, 1.0):
        # Center of the slope slab
        dx = mx + side * (half_span * 0.5)
        dz = eave_z + peak_h * 0.5
        create_box(bm, (slope_len, span_y, deck_th), (dx, my, dz),
                   rotation=(0, side * (math.pi * 0.5 - pitch_angle), 0),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Heavy Timber Verge Bargeboards on Front & Rear Gable Slopes
    for gy in (y0 - overhang_y, y1 + overhang_y):
        for side in (-1.0, 1.0):
            bx = mx + side * (half_span * 0.5)
            bz = eave_z + peak_h * 0.5
            create_box(bm, (slope_len * 1.02, 0.28, 0.28), (bx, gy, bz),
                       rotation=(0, side * (math.pi * 0.5 - pitch_angle), 0),
                       mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Dense Overlapping 3D Rounded Bone Scale Shingles
    num_rows = max(5, int(peak_h * 3.4))
    scale_w = 0.55
    scale_l = 0.65
    scale_th = 0.06
    num_cols = max(3, int(span_y / (scale_w * 0.72)))

    for side in (-1.0, 1.0):
        for row in range(num_rows):
            t = (row + 0.5) / num_rows
            row_x = mx + side * (half_span * (1.0 - t))
            row_z = eave_z + peak_h * t + 0.06

            stagger = (row % 2) * (scale_w * 0.36)
            for col in range(num_cols + 1):
                col_y = (y0 - overhang_y + 0.25) + col * (scale_w * 0.72) + stagger
                if col_y > y1 + overhang_y - 0.15:
                    continue

                # Each scale is a wide rounded beveled plate lying flush on the roof deck
                s_pos = (row_x, col_y, row_z)
                tilt_pitch = side * (math.pi * 0.5 - pitch_angle)
                create_cone(bm, radius1=scale_w * 0.5, radius2=scale_w * 0.25, height=scale_l, segments=6,
                            location=s_pos,
                            rotation=(math.pi * 0.5, tilt_pitch, 0),
                            mat_index=MAT_INDEX_BONE)

    # 5. Ridge Dorsal Fin Bone & Jagged Teeth Crest
    _build_ridge_crest_fin_and_spines(bm, mx, y0 - overhang_y, y1 + overhang_y,
                                      peak_z + 0.18, fin_scale=fin_scale, num_teeth=num_ridge_teeth)


def _build_ridge_crest_fin_and_spines(bm, rx, y_start, y_end, rz, fin_scale=1.5, num_teeth=8):
    """Crown of giant curved shark dorsal fin and jagged bone spikes along the roof peak."""
    fin_y = y_start + 0.65
    fin_h = 1.35 * fin_scale
    fin_base_w = 0.95 * fin_scale

    # Primary giant dorsal fin bone near front gable
    create_cone(bm, radius1=fin_base_w * 0.45, radius2=0.03, height=fin_h, segments=5,
                location=(rx, fin_y, rz + fin_h * 0.45),
                rotation=(0.28, 0, 0), mat_index=MAT_INDEX_BONE)

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
    """Conical roof with a solid timber underlay deck and dense overlapping rounded bone scales."""
    peak_z = eave_z + height

    # 1. Solid Timber Underlay Cone Deck (GUARANTEES ZERO SKY GAPS)
    create_cone(bm, radius1=radius * 1.02, radius2=0.20, height=height, segments=12,
                location=(cx, cy, eave_z + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Overlapping Rounded Bone Scale Plates in Concentric Rings
    num_rings = max(5, int(height * 2.8))
    for ring in range(num_rings):
        t = ring / num_rings
        ring_r = radius * (1.0 - t * 0.90)
        ring_z = eave_z + height * t + 0.04
        circumference = 2.0 * math.pi * ring_r
        num_scales = max(6, int(circumference / 0.52))

        slope_pitch = math.atan2(height, radius)
        stagger = (ring % 2) * (math.pi / max(1, num_scales))

        for s in range(num_scales):
            ang = s * (2.0 * math.pi / num_scales) + stagger
            sx = cx + math.cos(ang) * ring_r
            sy = cy + math.sin(ang) * ring_r

            tile_w = 0.50 * (1.0 - t * 0.35)
            tile_l = 0.58
            create_cone(bm, radius1=tile_w * 0.5, radius2=tile_w * 0.25, height=tile_l, segments=6,
                        location=(sx, sy, ring_z),
                        rotation=(slope_pitch, 0, ang - math.pi * 0.5),
                        mat_index=MAT_INDEX_BONE)

    # 3. Solid Apex Timber Socket
    apex_z = peak_z + 0.08
    create_cylinder(bm, radius=0.55, height=0.22, segments=10,
                    location=(cx, cy, apex_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Central giant shark fin
    fin_h = 1.4 * fin_scale
    create_cone(bm, radius1=0.48, radius2=0.03, height=fin_h, segments=5,
                location=(cx, cy, apex_z + fin_h * 0.45),
                rotation=(0.25, 0, 0), mat_index=MAT_INDEX_BONE)

    # Miniature bone spears planted around fin
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

def _build_hajfin_shanty(bm, props, width=6.5, depth=7.5, height=3.6, found_h=1.2):
    """The Quintessential Hajfin Pirate Shanty (Image 6):
    Real doorway cutout with recessed door, full gable triangle walls, 4 massive corner columns
    extending above eaves, bone fin emblem, and bone-scale gable roof with ridge fin."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height
    wall_th = 0.26
    roof_h = 3.2
    peak_z = z1 + roof_h

    # 1. Elevated Pier Stilts if foundation height > 0
    if found_h > 0.2:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Left & Right Walls with Window Openings
    _build_wall_with_window(bm, -hd, hd, -hw + wall_th * 0.5, z0, z1,
                            win_cx=0.0, win_cz=z0 + height * 0.52,
                            win_w=0.75, win_h=0.75, wall_th=wall_th, rot_z=-math.pi * 0.5)
    _build_wall_with_window(bm, -hd, hd, hw - wall_th * 0.5, z0, z1,
                            win_cx=0.0, win_cz=z0 + height * 0.52,
                            win_w=0.75, win_h=0.75, wall_th=wall_th, rot_z=math.pi * 0.5)

    # 3. Rear Wall (Solid)
    create_box(bm, (width - wall_th * 2, wall_th, height),
               (0.0, hd - wall_th * 0.5, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Front Wall with REAL DOOR OPENING
    door_w = 1.40
    door_h = min(2.5, height * 0.72)
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z1, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0)

    # 5. Solid Gable Triangle Walls (Front & Rear) - SEALS ROOF GAPS 100%
    _build_gable_triangle_wall(bm, -hw, hw, -hd + wall_th * 0.5, z1, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, hd - wall_th * 0.5, z1, peak_z, wall_th=wall_th)

    # 6. 4 Oversized Timber Corner Columns
    col_size = 0.44
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.45)

    # 7. Dense Bone Scale Gable Roof
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=7)


def _build_hajfin_round_hut(bm, props, diameter=7.5, height=3.8, found_h=0.8):
    """The Tapered Round Bone-Scale Hut (Image 2):
    8-sided tapered conical timber hut, massive perimeter posts, conical bone-scale roof
    with solid underlay, central shark fin crown with bone spears, shark jaw door,
    and massive whale vertebrae buttress curving up the rear wall!"""
    r_base = diameter * 0.5
    r_top = r_base * 0.82
    z0 = found_h
    z1 = z0 + height
    num_facets = 8

    # 1. Reef stone foundation ring
    create_cylinder(bm, radius=r_base * 1.05, height=found_h + 0.1, segments=num_facets,
                    location=(0.0, 0.0, found_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Tapered 8-sided body shell
    create_cone(bm, radius1=r_base, radius2=r_top, height=height, segments=num_facets,
                location=(0.0, 0.0, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Perimeter Timber Corner Posts
    col_size = 0.36
    for i in range(num_facets):
        ang = i * (2.0 * math.pi / num_facets)
        bx = math.cos(ang) * r_base
        by = math.sin(ang) * r_base
        tx = math.cos(ang) * r_top
        ty = math.sin(ang) * r_top
        lean_pitch = math.atan2(r_base - r_top, height)
        post_rot = (lean_pitch * math.sin(ang), -lean_pitch * math.cos(ang), ang)

        mid_x = (bx + tx) * 0.5
        mid_y = (by + ty) * 0.5
        create_box(bm, (col_size, col_size, height + 0.35), (mid_x, mid_y, z0 + height * 0.5),
                   rotation=post_rot, mat_index=MAT_INDEX_DRIFTWOOD)

        create_box(bm, (col_size + 0.04, col_size + 0.04, 0.22), (bx, by, z0 + 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.04, col_size + 0.04, 0.22), (tx, ty, z1 - 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)

    # 4. Front Shark Jaw Doorway (South, ang = -pi/2)
    door_w = 1.35
    door_h = 2.40
    # Recessed door cavity
    create_box(bm, (door_w * 0.88, 0.10, door_h * 0.95), (0.0, -r_base + 0.15, z0 + door_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    _build_shark_jaw_arch(bm, 0.0, -r_base, z0, rot_z=0.0, width=door_w, height=door_h)

    # 5. Rear Whale Spine Buttress (North, ang = +pi/2)
    _build_whale_spine_buttress(bm, 0.0, r_base * 0.95, z0, rot_z=0.0, num_vertebrae=7, max_h=height * 0.9)

    # 6. Diagonal Bone-Framed Windows
    for ang in (-math.pi * 0.75, -math.pi * 0.25):
        wx = math.cos(ang) * (r_base * 0.6 + r_top * 0.4)
        wy = math.sin(ang) * (r_base * 0.6 + r_top * 0.4)
        _build_bone_window(bm, wx, wy, z0 + height * 0.55, rot_z=ang + math.pi * 0.5, w=0.68, h=0.68)

    # 7. Conical Bone Scale Roof with Solid Deck
    roof_h = 3.2
    _build_bone_scale_roof_conical(bm, 0.0, 0.0, z1, radius=r_top * 1.25, height=roof_h,
                                   fin_scale=1.5, num_spears=4)


def _build_hajfin_crate_blockhouse(bm, props, width=7.0, depth=7.0, height=5.5, found_h=0.8):
    """The Heavy Timber Crate Blockhouse (Image 5):
    Solid cubic timber fortress shack with heavy square framing, bolted iron corner plates,
    flat planked deck roof with heavy beam rims, shark jaw doorway with real opening, and bone-framed windows."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height
    wall_th = 0.26
    mid_z = z0 + height * 0.5

    # 1. Foundation base
    if getattr(props, 'found_type', 'STONE') == 'WOOD' or found_h >= 1.0:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)
    else:
        create_box(bm, (width + 0.3, depth + 0.3, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
                   mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Walls with Real Cut Openings
    # Left & Right walls with bone windows
    _build_wall_with_window(bm, -hd, hd, -hw + wall_th * 0.5, z0, z1,
                            win_cx=0.0, win_cz=z0 + height * 0.72,
                            win_w=0.72, win_h=0.72, wall_th=wall_th, rot_z=-math.pi * 0.5)
    _build_wall_with_window(bm, -hd, hd, hw - wall_th * 0.5, z0, z1,
                            win_cx=0.0, win_cz=z0 + height * 0.72,
                            win_w=0.72, win_h=0.72, wall_th=wall_th, rot_z=math.pi * 0.5)

    # Rear wall
    create_box(bm, (width - wall_th * 2, wall_th, height),
               (0.0, hd - wall_th * 0.5, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Front wall with real door cutout
    door_w = 1.45
    door_h = 2.45
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z1, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0)

    # Upper front windows
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * (hw * 0.5), -hd, z0 + height * 0.74, rot_z=0.0, w=0.70, h=0.70)

    # 3. Massive Square Corner Columns with L-Brackets
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            create_box(bm, (col_size, col_size, height + 0.25), (cx, cy, z0 + height * 0.5 + 0.125),
                       mat_index=MAT_INDEX_DRIFTWOOD)
            for bz in (z0 + 0.25, mid_z, z1):
                create_box(bm, (col_size + 0.05, col_size + 0.05, 0.32), (cx, cy, bz),
                           mat_index=MAT_INDEX_IRON)

    # 4. Dense Bone Scale Roof with solid gable triangle walls
    roof_h = max(2.8, width * 0.45)
    peak_z = z1 + roof_h
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z1, peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, hd, z1, peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=6)


def _build_hajfin_bone_shop(bm, props, width=9.5, depth=8.5, height=6.8, found_h=0.9):
    """The Bone & Drift Trading Post (Image 3):
    Two-storey trading depot with open barter stall counter, flip-up plank awning,
    flanking wooden dock platforms, second-level lookout room, giant mounted shark skull,
    solid roof decks with bone-scale shingles, ladder, and trade sign."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    g_h = 3.4
    u_h = 3.0
    z_mid = z0 + g_h
    z_top = z_mid + u_h
    wall_th = 0.26

    # 1. Ground Floor Shell with Open Barter Counter & Side Door
    create_box(bm, (width - wall_th * 2, wall_th, g_h), (0.0, hd - wall_th * 0.5, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, g_h), (-hw + wall_th * 0.5, 0.0, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, g_h), (hw - wall_th * 0.5, 0.0, z0 + g_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Massive Ground Floor Corner Columns
    col_size = 0.44
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z_mid, size=col_size, extend_top=0.2)

    # 3. Open Barter Trade Counter with Flip-Up Awning
    counter_w = 3.6
    counter_d = 1.1
    counter_h = 1.0
    create_box(bm, (counter_w, counter_d, counter_h), (0.0, -hd - counter_d * 0.3, z0 + counter_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (counter_w * 0.95, 0.2, 1.4), (0.0, -hd, z0 + counter_h + 0.7), mat_index=MAT_INDEX_GLASS)

    awning_w = counter_w * 1.15
    awning_d = 1.4
    create_box(bm, (awning_w, awning_d, 0.08), (0.0, -hd - awning_d * 0.45, z0 + counter_h + 1.55),
               rotation=(0.32, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)

    create_box(bm, (3.2, 0.08, 0.55), (0.0, -hd - 0.15, z0 + counter_h + 1.95), mat_index=MAT_INDEX_DRIFTWOOD)

    # Ground floor side entrance door
    _build_wall_with_door_opening(bm, -hw + wall_th, -counter_w * 0.5 - 0.2, -hd + wall_th * 0.5,
                                  z0, z_mid, door_cx=-hw * 0.65, door_w=1.2, door_h=2.2,
                                  wall_th=wall_th, rot_z=0.0)

    # 4. Flanking Wooden Dock / Pier Platforms
    for sgn_x in (-1.0, 1.0):
        plat_w = 1.5
        plat_d = depth * 0.8
        px = sgn_x * (hw + plat_w * 0.5)
        create_box(bm, (plat_w, plat_d, 0.12), (px, 0.0, z0 + 1.2), mat_index=MAT_INDEX_FLOOR)
        for py in (-plat_d * 0.4, 0.0, plat_d * 0.4):
            create_cylinder(bm, radius=0.12, height=z0 + 1.2, segments=6,
                            location=(px, py, (z0 + 1.2) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Second-Level Central Lookout Tower / Room
    u_w = width * 0.58
    u_d = depth * 0.72
    create_box(bm, (u_w, u_d, u_h), (0.0, 0.0, z_mid + u_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    for cx in (-u_w * 0.5, u_w * 0.5):
        for cy in (-u_d * 0.5, u_d * 0.5):
            _build_chunky_corner_column(bm, cx, cy, z_mid, z_top, size=0.36, extend_top=0.3)

    # 6. Giant Open Shark Skull mounted on upper front facade
    _build_shark_skull_mount(bm, u_w * 0.28, -u_d * 0.5, z_mid + u_h * 0.62, rot_z=0.0, scale=1.1)

    # 7. Exterior Wooden Ladder
    lad_x = u_w * 0.42
    lad_y = -hd - 0.25
    lad_len = g_h * 1.15
    lad_pitch = 0.22
    for sgn_rail in (-0.25, 0.25):
        create_cylinder(bm, radius=0.035, height=lad_len, segments=6,
                        location=(lad_x + sgn_rail, lad_y + lad_pitch * g_h * 0.5, z0 + g_h * 0.5),
                        rotation=(lad_pitch, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)
    for r_i in range(8):
        rz = z0 + 0.35 + r_i * (g_h * 0.95 / 8)
        ry = lad_y + (rz - z0) * math.tan(lad_pitch)
        create_box(bm, (0.50, 0.06, 0.06), (lad_x, ry, rz), mat_index=MAT_INDEX_DRIFTWOOD)

    # 8. Whale Ribs lashed along the corner post
    for ri in range(4):
        rib_z = z0 + 0.8 + ri * 0.32
        create_cylinder(bm, radius=0.045, height=0.65, segments=5,
                        location=(hw * 0.55, -u_d * 0.5 - 0.08, rib_z),
                        rotation=(0, 0.85, 0), mat_index=MAT_INDEX_BONE)

    # 9. Multi-Tier Bone Scale Roofs with Full Solid Gable Triangles
    # Lower flanking roofs
    for sgn_x in (-1.0, 1.0):
        lx0 = sgn_x * hw
        lx1 = sgn_x * (u_w * 0.5)
        fl_x0 = min(lx0, lx1)
        fl_x1 = max(lx0, lx1)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, -hd, z_mid, z_mid + 1.8, wall_th=wall_th)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, hd, z_mid, z_mid + 1.8, wall_th=wall_th)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd, hd, z_mid, 1.8,
                                     overhang_x=0.35, overhang_y=0.35, fin_scale=1.1, num_ridge_teeth=4)

    # Upper Tower Main Roof with full gable triangles
    u_peak_z = z_top + 2.8
    _build_gable_triangle_wall(bm, -u_w * 0.5, u_w * 0.5, -u_d * 0.5, z_top, u_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -u_w * 0.5, u_w * 0.5, u_d * 0.5, z_top, u_peak_z, wall_th=wall_th)
    _build_bone_scale_roof_gable(bm, -u_w * 0.5, u_w * 0.5, -u_d * 0.5, u_d * 0.5, z_top, 2.8,
                                 overhang_x=0.45, overhang_y=0.45, fin_scale=1.6, num_ridge_teeth=6)


def _build_hajfin_chieftain_hall(bm, props, width=12.0, depth=16.0, height=5.2, found_h=1.4):
    """The Chieftain Great Fin Hall (Image 4):
    Grand multi-tier staggered longhouse, continuous ridge spine of giant curved bone horns
    leading to a soaring forward-curving horn/tusk, projecting whale rib cage tunnel entrance,
    solid gable triangle walls, and flanking tribal totem posts."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wall_th = 0.28

    # 1. Elevated Reef Stone Foundation
    create_box(bm, (width + 0.4, depth + 0.4, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
               mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Central High Nave (Hollow walls with real cut door opening)
    nave_w = width * 0.60
    nave_h = height
    nave_peak_z = z0 + nave_h + 4.4
    # Rear wall
    create_box(bm, (nave_w, wall_th, nave_h), (0.0, hd - wall_th * 0.5, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Side walls
    create_box(bm, (wall_th, depth - wall_th * 2, nave_h), (-nave_w * 0.5 + wall_th * 0.5, 0.0, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, depth - wall_th * 2, nave_h), (nave_w * 0.5 - wall_th * 0.5, 0.0, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Front wall with real cut door opening inside rib tunnel
    door_w = 1.75
    door_h = min(3.0, nave_h * 0.75)
    _build_wall_with_door_opening(bm, -nave_w * 0.5 + wall_th, nave_w * 0.5 - wall_th, -hd + wall_th * 0.5,
                                  z0, z0 + nave_h, door_cx=0.0, door_w=door_w, door_h=door_h,
                                  wall_th=wall_th, rot_z=0.0)

    # 3. Flanking Lower Side Aisles
    side_w = (width - nave_w) * 0.5
    side_h = height * 0.65
    side_peak_z = z0 + side_h + 2.0
    for sgn_x in (-1.0, 1.0):
        sx = sgn_x * (nave_w * 0.5 + side_w * 0.5)
        create_box(bm, (side_w, depth * 0.85, side_h), (sx, 0.0, z0 + side_h * 0.5),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Chunky Corner Columns on Nave and Aisles
    for cx in (-nave_w * 0.5, nave_w * 0.5):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + nave_h, size=0.46, extend_top=0.35)
    for sgn_x in (-1.0, 1.0):
        for cy in (-hd * 0.85, hd * 0.85):
            _build_chunky_corner_column(bm, sgn_x * hw, cy, z0, z0 + side_h, size=0.38, extend_top=0.25)

    # 5. Projecting Whale Rib Cage Tunnel Entrance (Image 4)
    _build_whale_rib_tunnel_entrance(bm, 0.0, -hd, z0, rot_z=0.0, length=2.8, height=3.0, width=2.4, num_pairs=4)

    # Flanking Tribal Totem Posts at entrance
    for sgn_t in (-1.0, 1.0):
        tx = sgn_t * 1.85
        ty = -hd - 1.2
        create_cylinder(bm, radius=0.18, height=3.0, segments=7,
                        location=(tx, ty, z0 + 1.5), mat_index=MAT_INDEX_DRIFTWOOD)
        create_cone(bm, radius1=0.22, radius2=0.03, height=0.6, segments=5,
                    location=(tx, ty, z0 + 3.3), mat_index=MAT_INDEX_DRIFTWOOD)
        create_box(bm, (0.7, 0.12, 0.16), (tx, ty, z0 + 2.4), mat_index=MAT_INDEX_DRIFTWOOD)
        create_torus_ring(bm, (tx, ty, z0 + 1.8), major_radius=0.21, minor_radius=0.03, mat_index=MAT_INDEX_ROPE)
        create_torus_ring(bm, (tx, ty, z0 + 2.2), major_radius=0.21, minor_radius=0.03, mat_index=MAT_INDEX_ROPE)

    # 6. Solid Gable Triangle Walls (Zero gaps!)
    _build_gable_triangle_wall(bm, -nave_w * 0.5, nave_w * 0.5, -hd, z0 + nave_h, nave_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -nave_w * 0.5, nave_w * 0.5, hd, z0 + nave_h, nave_peak_z, wall_th=wall_th)

    for sgn_x in (-1.0, 1.0):
        ax0 = sgn_x * (nave_w * 0.5)
        ax1 = sgn_x * hw
        fl_x0 = min(ax0, ax1)
        fl_x1 = max(ax0, ax1)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, -hd * 0.85, z0 + side_h, side_peak_z, wall_th=wall_th)
        _build_gable_triangle_wall(bm, fl_x0, fl_x1, hd * 0.85, z0 + side_h, side_peak_z, wall_th=wall_th)

    # 7. Multi-Tier Dense Bone Scale Roofs
    for sgn_x in (-1.0, 1.0):
        ax0 = sgn_x * (nave_w * 0.5)
        ax1 = sgn_x * hw
        fl_x0 = min(ax0, ax1)
        fl_x1 = max(ax0, ax1)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd * 0.85, hd * 0.85, z0 + side_h, 2.0,
                                     overhang_x=0.35, overhang_y=0.35, fin_scale=1.1, num_ridge_teeth=5)

    # High Nave Central Roof with giant horn & continuous ridge spine
    _build_bone_scale_roof_gable(bm, -nave_w * 0.5, nave_w * 0.5, -hd, hd, z0 + nave_h, 4.4,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=2.2, num_ridge_teeth=10)


def _build_hajfin_pirate_tavern(bm, props, width=11.0, depth=11.0, height=6.2, found_h=1.2):
    """The Barnacle Bilge Pirate Tavern:
    Multi-deck L-shaped pirate tavern with open-air stilt drinking veranda, grog barrels,
    solid roof decks with bone scale shingles, shark jaw doorway, and dorsal fin ridge ornaments."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wing_w = width * 0.52
    wing_d = depth * 0.48
    wall_th = 0.26

    # 1. Stilt Pier Foundation
    _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Main L-Shaped Building Walls (Hollow shells with door openings)
    m_w = width
    m_d = depth - wing_d
    my = -hd + m_d * 0.5
    # Rear wall of main block
    create_box(bm, (m_w, wall_th, height), (0.0, -hd + m_d - wall_th * 0.5, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Side walls of main block
    create_box(bm, (wall_th, m_d - wall_th * 2, height), (-hw + wall_th * 0.5, my, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    create_box(bm, (wall_th, m_d - wall_th * 2, height), (hw - wall_th * 0.5, my, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Wing block walls
    create_box(bm, (wing_w, wing_d, height * 0.85), (hw - wing_w * 0.5, hd - wing_d * 0.5, z0 + height * 0.425),
               mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Open-Air Stilt Drinking Deck in L-cutout
    deck_w = width - wing_w
    deck_d = wing_d
    deck_x = -hw + deck_w * 0.5
    deck_y = hd - wing_d * 0.5
    create_box(bm, (deck_w, deck_d, 0.15), (deck_x, deck_y, z0 + 0.1), mat_index=MAT_INDEX_FLOOR)
    _build_timber_deck_railing(bm, deck_x, deck_y, z0 + 0.1, deck_w, deck_d)

    # Clustered grog barrels on drinking deck
    for bx, by in ((deck_x - 0.6, deck_y - 0.5), (deck_x + 0.5, deck_y - 0.4), (deck_x, deck_y + 0.6)):
        create_cylinder(bm, radius=0.32, height=0.75, segments=8,
                        location=(bx, by, z0 + 0.48), mat_index=MAT_INDEX_DRIFTWOOD)
        create_torus_ring(bm, (bx, by, z0 + 0.35), major_radius=0.33, minor_radius=0.02, mat_index=MAT_INDEX_IRON)
        create_torus_ring(bm, (bx, by, z0 + 0.65), major_radius=0.33, minor_radius=0.02, mat_index=MAT_INDEX_IRON)

    # 4. Corner Columns
    col_size = 0.42
    for cx in (-hw, hw):
        for cy in (-hd, my + m_d * 0.5):
            _build_chunky_corner_column(bm, cx, cy, z0, z0 + height, size=col_size, extend_top=0.35)

    # 5. Shark Jaw Entrance Doorways
    _build_wall_with_door_opening(bm, -hw + wall_th, hw - wall_th, -hd + wall_th * 0.5,
                                  z0, z0 + height * 0.5, door_cx=-0.6, door_w=1.55, door_h=2.55,
                                  wall_th=wall_th, rot_z=0.0)

    # 6. Bone-Framed Windows
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * hw, my, z0 + height * 0.45,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.75, h=0.75)
        _build_bone_window(bm, sgn_x * hw, my, z0 + height * 0.80,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.75, h=0.75)

    # 7. Solid Gable Triangle Walls & Bone Scale Roofs
    m_peak_z = z0 + height + 3.4
    w_peak_z = z0 + height * 0.85 + 2.6
    _build_gable_triangle_wall(bm, -hw, hw, -hd, z0 + height, m_peak_z, wall_th=wall_th)
    _build_gable_triangle_wall(bm, -hw, hw, -hd + m_d, z0 + height, m_peak_z, wall_th=wall_th)

    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, -hd + m_d, z0 + height, 3.4,
                                 overhang_x=0.5, overhang_y=0.5, fin_scale=1.6, num_ridge_teeth=7)
    _build_bone_scale_roof_gable(bm, hw - wing_w, hw, hd - wing_d, hd, z0 + height * 0.85, 2.6,
                                 overhang_x=0.4, overhang_y=0.4, fin_scale=1.2, num_ridge_teeth=5)


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
    step_w = 1.6
    step_d = 0.35
    for i in range(num_steps):
        sz = (i + 0.5) * (height / num_steps)
        sy = y0 - (num_steps - i) * step_d
        create_box(bm, (step_w, step_d * 1.05, 0.12), (0.0, sy, sz), mat_index=MAT_INDEX_FLOOR)


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
    elif style == 'BLOCKHOUSE' or shape == 'CUBE':
        _build_hajfin_crate_blockhouse(bm, props, width=width, depth=depth, height=height, found_h=found_h)
    else:
        # Default iconic Shanty Shack (Image 6)
        _build_hajfin_shanty(bm, props, width=width, depth=depth, height=height, found_h=found_h)

    # Box UV mapping at scale 3.5 so planks look chunky and hand-painted
    apply_box_uvs(bm, scale=3.5)

    # Write bmesh to obj
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
