"""
Hajfin Pirate Civilization Dedicated Procedural Architecture Generator.

Completely distinct procedural geometry pipeline for the Hajfin shark-humanoid pirate faction:
- Chunky tapered round huts, multi-tier staggered longhouses, barter trading posts, and crate shanties.
- 3D overlapping curved shark-scale / bone plate roofs with moss.
- Shark jaw bone doorways with inward-pointing sharp teeth.
- Roof ridge dorsal fins and jagged bone spike crests.
- Bone-framed barred windows.
- Oversized corner timber columns with iron bracket cuffs and wall spikes.
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
    add_wonkiness,
)


# =============================================================================
# SIGNATURE ARCHITECTURAL COMPONENTS
# =============================================================================

def _build_chunky_corner_column(bm, x, y, z0, z1, size=0.38, extend_top=0.35, with_spikes=True):
    """Oversized square timber column extending proudly above eaves with iron brackets and spikes."""
    col_h = (z1 - z0) + extend_top
    cz = z0 + col_h * 0.5
    # Main column
    create_box(bm, (size, size, col_h), (x, y, cz), mat_index=MAT_INDEX_DRIFTWOOD)

    # Beveled chisel pyramid cap on top
    cap_h = size * 0.4
    cap_z = z0 + col_h + cap_h * 0.5
    create_cone(bm, radius1=size * 0.707, radius2=0.02, height=cap_h, segments=4,
                location=(x, y, cap_z), rotation=(0, 0, math.pi * 0.25), mat_index=MAT_INDEX_DRIFTWOOD)

    # Bolted steel bracket cuffs at bottom and top
    cuff_th = 0.025
    cuff_h = 0.22
    for bz in (z0 + 0.15, z1 - 0.20):
        create_box(bm, (size + cuff_th * 2, size + cuff_th * 2, cuff_h), (x, y, bz),
                   mat_index=MAT_INDEX_IRON)

    # Protruding triangular iron spikes driven into the timber
    if with_spikes:
        num_spikes = max(2, int((z1 - z0) / 1.1))
        dz = (z1 - z0 - 1.0) / max(1, num_spikes - 1)
        for i in range(num_spikes):
            sz = z0 + 0.6 + i * dz
            # Random outward direction
            angle = ((i * 1.618) % 4) * (math.pi * 0.5) + math.pi * 0.25
            sx = x + math.cos(angle) * (size * 0.5 + 0.15)
            sy = y + math.sin(angle) * (size * 0.5 + 0.15)
            create_cone(bm, radius1=0.04, radius2=0.005, height=0.28, segments=5,
                        location=(sx, sy, sz), rotation=(math.pi * 0.5, 0, angle + math.pi * 0.5),
                        mat_index=MAT_INDEX_IRON)


def _build_shark_jaw_doorway(bm, cx, cy, cz, rot_z=0.0, width=1.35, height=2.30):
    """The iconic Hajfin Shark Jaw Doorway: Arched bone jaw with inward-pointing sharp teeth,
    carved bone dorsal fin emblem above the apex, and recessed wooden door with iron ring."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')

    # 1. Recessed solid timber plank door
    door_w = width * 0.85
    door_h = height * 0.88
    door_th = 0.10
    door_loc = rot_mat @ Vector((0.0, -0.06, door_h * 0.5)) + Vector((cx, cy, cz))
    create_box(bm, (door_w, door_th, door_h), (door_loc.x, door_loc.y, door_loc.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Iron door hinges/bands across planks
    for hz in (cz + door_h * 0.25, cz + door_h * 0.72):
        h_loc = rot_mat @ Vector((0.0, -0.115, hz - cz)) + Vector((cx, cy, cz))
        create_box(bm, (door_w * 0.92, 0.02, 0.08), (h_loc.x, h_loc.y, h_loc.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_IRON)

    # Iron pull ring handle
    ring_loc = rot_mat @ Vector((door_w * 0.28, -0.13, door_h * 0.45)) + Vector((cx, cy, cz))
    create_torus_ring(bm, (ring_loc.x, ring_loc.y, ring_loc.z),
                      rotation=(math.pi * 0.5, 0, rot_z), major_radius=0.07, minor_radius=0.014,
                      major_segments=12, minor_segments=6, mat_index=MAT_INDEX_IRON)

    # 2. Arched Shark Jaw Bone Frame
    # Built from two curving bone arches meeting at top apex
    jaw_segs = 8
    arch_pts = []
    # Semi-elliptical arched profile with sharp peak
    for i in range(jaw_segs + 1):
        t = i / jaw_segs  # 0 to 1
        ang = math.pi * t
        lx = -math.cos(ang) * (width * 0.5)
        # Curve height with pointed top peak
        lz = math.sin(ang) * height
        if lz < height * 0.5:
            # Vertical root section
            lz = (lz / (height * 0.5)) * (height * 0.45)
        else:
            # Arched upper section with slight gothic/shark tip
            norm_t = (lz - height * 0.5) / (height * 0.5)
            lz = height * 0.45 + (norm_t ** 0.85) * (height * 0.55)
        arch_pts.append((lx, lz))

    # Extrude jaw bone segments along arch
    bone_rad = 0.12
    for i in range(len(arch_pts) - 1):
        x0, z0_pt = arch_pts[i]
        x1, z1_pt = arch_pts[i + 1]
        mid_x = (x0 + x1) * 0.5
        mid_z = (z0_pt + z1_pt) * 0.5
        seg_len = math.hypot(x1 - x0, z1_pt - z0_pt)
        tilt_ang = math.atan2(z1_pt - z0_pt, x1 - x0) - math.pi * 0.5

        seg_pos = rot_mat @ Vector((mid_x, 0.02, mid_z)) + Vector((cx, cy, cz))
        # Jaw thickness tapers slightly toward apex
        taper_r = bone_rad * (1.1 - 0.25 * (mid_z / height))
        create_cylinder(bm, radius=taper_r, height=seg_len * 1.05, segments=8,
                        location=(seg_pos.x, seg_pos.y, seg_pos.z),
                        rotation=(0, -tilt_ang, rot_z), mat_index=MAT_INDEX_BONE)

        # Inward-pointing shark teeth on upper arch segments!
        if mid_z > height * 0.38 and i % 1 == 0:
            tooth_len = 0.16 + 0.05 * math.sin(i * 1.8)
            # Normal perpendicular to segment, pointing inward towards center
            in_dx = -(z1_pt - z0_pt) / max(seg_len, 1e-4)
            in_dz = (x1 - x0) / max(seg_len, 1e-4)
            if in_dz > 0:
                in_dx, in_dz = -in_dx, -in_dz
            # Position tooth at inner rim
            tx = mid_x + in_dx * (taper_r * 0.7)
            tz = mid_z + in_dz * (taper_r * 0.7)
            t_loc = rot_mat @ Vector((tx, 0.04, tz)) + Vector((cx, cy, cz))
            tooth_pitch = math.atan2(in_dz, in_dx) - math.pi * 0.5
            create_cone(bm, radius1=0.035, radius2=0.005, height=tooth_len, segments=5,
                        location=(t_loc.x, t_loc.y, t_loc.z),
                        rotation=(0, -tooth_pitch, rot_z), mat_index=MAT_INDEX_BONE)

    # 3. Carved Bone Dorsal Fin Emblem above door peak
    emblem_loc = rot_mat @ Vector((0.0, 0.05, height + 0.38)) + Vector((cx, cy, cz))
    _build_bone_fin_emblem(bm, emblem_loc.x, emblem_loc.y, emblem_loc.z, rot_z, scale=0.55)


def _build_bone_fin_emblem(bm, x, y, z, rot_z=0.0, scale=0.6):
    """Carved dorsal fin plaque mounted flat against the timber wall."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    # Fin base pedestal
    b_loc = rot_mat @ Vector((0.0, 0.0, -scale * 0.25)) + Vector((x, y, z))
    create_box(bm, (scale * 0.9, 0.06, scale * 0.15), (b_loc.x, b_loc.y, b_loc.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Curved predatory dorsal fin shape using tapered beveled segments
    fin_h = scale * 0.85
    fin_w = scale * 0.65
    f_loc = rot_mat @ Vector((scale * 0.05, 0.02, fin_h * 0.35)) + Vector((x, y, z))
    create_cone(bm, radius1=fin_w * 0.45, radius2=0.02, height=fin_h, segments=5,
                location=(f_loc.x, f_loc.y, f_loc.z),
                rotation=(0, 0.32, rot_z), mat_index=MAT_INDEX_BONE)


def _build_bone_window(bm, x, y, z, rot_z=0.0, w=0.75, h=0.75):
    """Square/rectangular window framed with 4 carved bone segments and iron security bars."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    bone_r = 0.055

    # 4 Bone frame pieces
    # Top & Bottom horizontal bones
    for sgn_y in (-1.0, 1.0):
        fz = h * 0.5 * sgn_y
        b_loc = rot_mat @ Vector((0.0, 0.02, fz)) + Vector((x, y, z))
        create_cylinder(bm, radius=bone_r, height=w + bone_r * 1.6, segments=6,
                        location=(b_loc.x, b_loc.y, b_loc.z),
                        rotation=(0, math.pi * 0.5, rot_z), mat_index=MAT_INDEX_BONE)
    # Left & Right vertical bones
    for sgn_x in (-1.0, 1.0):
        fx = w * 0.5 * sgn_x
        b_loc = rot_mat @ Vector((fx, 0.02, 0.0)) + Vector((x, y, z))
        create_cylinder(bm, radius=bone_r, height=h, segments=6,
                        location=(b_loc.x, b_loc.y, b_loc.z),
                        rotation=(0, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # 2-3 Vertical iron bars inside opening
    num_bars = 3
    for i in range(num_bars):
        bx = -w * 0.3 + i * (w * 0.6 / max(1, num_bars - 1))
        bar_loc = rot_mat @ Vector((bx, -0.02, 0.0)) + Vector((x, y, z))
        create_cylinder(bm, radius=0.016, height=h * 0.85, segments=5,
                        location=(bar_loc.x, bar_loc.y, bar_loc.z),
                        rotation=(0, 0, rot_z), mat_index=MAT_INDEX_IRON)

    # Dark recessed backing
    back_loc = rot_mat @ Vector((0.0, -0.06, 0.0)) + Vector((x, y, z))
    create_box(bm, (w * 0.85, 0.05, h * 0.85), (back_loc.x, back_loc.y, back_loc.z),
               rotation=(0, 0, rot_z), mat_index=MAT_INDEX_GLASS)


def _build_whale_spine_buttress(bm, x, y, z0, rot_z=0.0, num_vertebrae=6, max_h=2.8):
    """Massive segmented whale spine / vertebrae column curving up the back/corner of the building."""
    rot_mat = Matrix.Rotation(rot_z, 4, 'Z')
    seg_dz = max_h / num_vertebrae
    curr_z = z0

    for i in range(num_vertebrae):
        # Progressively smaller discs rising and curving outward
        t = i / max(1, num_vertebrae - 1)
        r = 0.32 * (1.1 - 0.35 * t)
        th = seg_dz * 0.75
        out_dist = 0.35 + 0.45 * (1.0 - math.cos(t * math.pi * 0.5))

        v_loc = rot_mat @ Vector((0.0, out_dist, curr_z + th * 0.5)) + Vector((x, y, 0.0))
        # Central vertebral disc
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

    # Eye socket cavities (dark boxes)
    for sgn in (-1.0, 1.0):
        eye_loc = rot_mat @ Vector((sgn * 0.28 * scale, 0.28 * scale, 0.30 * scale)) + Vector((x, y, z))
        create_box(bm, (0.16 * scale, 0.12 * scale, 0.16 * scale),
                   (eye_loc.x, eye_loc.y, eye_loc.z),
                   rotation=(0, 0, rot_z), mat_index=MAT_INDEX_GLASS)

    # Upper snout with sharp teeth rim
    snout_loc = rot_mat @ Vector((0.0, 0.48 * scale, 0.05 * scale)) + Vector((x, y, z))
    create_box(bm, (0.44 * scale, 0.22 * scale, 0.20 * scale),
               (snout_loc.x, snout_loc.y, snout_loc.z),
               rotation=(0.2, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Lower jaw hinged open downward
    jaw_loc = rot_mat @ Vector((0.0, 0.40 * scale, -0.28 * scale)) + Vector((x, y, z))
    create_box(bm, (0.42 * scale, 0.28 * scale, 0.16 * scale),
               (jaw_loc.x, jaw_loc.y, jaw_loc.z),
               rotation=(-0.4, 0, rot_z), mat_index=MAT_INDEX_BONE)

    # Jagged teeth inside maw
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
        # Each pair of ribs arches from ground on left and right, meeting at top center
        pair_h = height * (1.0 - 0.08 * i)  # slightly tapers outward
        pair_w = width * (1.0 + 0.05 * i)

        for sgn in (-1.0, 1.0):
            rib_base = rot_mat @ Vector((sgn * pair_w * 0.5, fwd, 0.0)) + Vector((entrance_x, entrance_y, z0))
            rib_mid = rot_mat @ Vector((sgn * pair_w * 0.65, fwd, pair_h * 0.55)) + Vector((entrance_x, entrance_y, z0))
            rib_top = rot_mat @ Vector((sgn * 0.08, fwd, pair_h)) + Vector((entrance_x, entrance_y, z0))

            # Bottom curved bone segment
            create_cylinder(bm, radius=0.10, height=pair_h * 0.65, segments=7,
                            location=(rib_base.x * 0.4 + rib_mid.x * 0.6,
                                      rib_base.y * 0.4 + rib_mid.y * 0.6,
                                      z0 + pair_h * 0.3),
                            rotation=(0, sgn * 0.35, rot_z), mat_index=MAT_INDEX_BONE)
            # Upper arched bone segment
            create_cylinder(bm, radius=0.08, height=pair_h * 0.55, segments=6,
                            location=(rib_mid.x * 0.4 + rib_top.x * 0.6,
                                      rib_mid.y * 0.4 + rib_top.y * 0.6,
                                      z0 + pair_h * 0.8),
                            rotation=(0, -sgn * 0.55, rot_z), mat_index=MAT_INDEX_BONE)

        # Rope winding at top apex tying the pair together
        apex_loc = rot_mat @ Vector((0.0, fwd, pair_h - 0.04)) + Vector((entrance_x, entrance_y, z0))
        create_cylinder(bm, radius=0.12, height=0.18, segments=8,
                        location=(apex_loc.x, apex_loc.y, apex_loc.z),
                        rotation=(math.pi * 0.5, 0, rot_z), mat_index=MAT_INDEX_ROPE)

    # Flanking carved wooden totem posts at the tunnel entrance
    for sgn in (-1.0, 1.0):
        post_loc = rot_mat @ Vector((sgn * (width * 0.55 + 0.4), length + 0.35, 0.0)) + Vector((entrance_x, entrance_y, z0))
        _build_tribal_totem_post(bm, post_loc.x, post_loc.y, z0, height=2.4)


def _build_tribal_totem_post(bm, x, y, z0, height=2.4):
    """Carved timber totem pole with rope coils and cross arms (Image 1, Image 4)."""
    post_r = 0.16
    cz = z0 + height * 0.5
    # Main post
    create_cylinder(bm, radius=post_r, height=height, segments=8,
                    location=(x, y, cz), mat_index=MAT_INDEX_DRIFTWOOD)

    # Pointed sharpened pencil tip top
    create_cone(bm, radius1=post_r, radius2=0.02, height=0.45, segments=8,
                location=(x, y, z0 + height + 0.22), mat_index=MAT_INDEX_DRIFTWOOD)

    # Rope coils wrapping the post
    for rz in (z0 + 0.6, z0 + 1.3, z0 + height - 0.2):
        create_cylinder(bm, radius=post_r + 0.035, height=0.16, segments=10,
                        location=(x, y, rz), mat_index=MAT_INDEX_ROPE)

    # Cross timber fin/arms
    create_box(bm, (0.75, 0.12, 0.14), (x, y, z0 + height * 0.65), mat_index=MAT_INDEX_DRIFTWOOD)


# =============================================================================
# BONE SCALE ROOF GENERATORS
# =============================================================================

def _build_bone_scale_roof_gable(bm, x0, x1, y0, y1, eave_z, peak_h,
                                 overhang_x=0.45, overhang_y=0.45,
                                 fin_scale=1.5, num_ridge_teeth=8):
    """Generates thick, 3D overlapping curved bone/shark scale shingles over a gable roof (Images 3, 4, 6).
    Ridge line runs along Y axis."""
    mx = (x0 + x1) * 0.5
    half_span = (x1 - x0) * 0.5 + overhang_x
    span_y = (y1 - y0) + overhang_y * 2
    peak_z = eave_z + peak_h

    # 1. Structural timber rafters & ridge beam
    ridge_len = span_y + 0.4
    create_box(bm, (0.35, ridge_len, 0.38), (mx, (y0 + y1) * 0.5, peak_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Heavy gable timber verge beams along the front and back slopes
    for gy in (y0 - overhang_y, y1 + overhang_y):
        for sgn_x in (-1.0, 1.0):
            bx = mx + sgn_x * half_span * 0.5
            bz = eave_z + peak_h * 0.5
            beam_len = math.hypot(half_span, peak_h)
            pitch = math.atan2(peak_h, half_span)
            create_box(bm, (0.32, 0.32, beam_len * 1.05), (bx, gy, bz),
                       rotation=(0, -sgn_x * (math.pi * 0.5 - pitch), 0),
                       mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Overlapping 3D Bone Scale Shingles
    # Rows stepping up from eave to ridge
    num_rows = max(4, int(peak_h * 3.2))
    scale_w = 0.52
    scale_l = 0.65
    scale_th = 0.08
    num_cols = max(3, int(span_y / (scale_w * 0.72)))

    for side in (-1.0, 1.0):  # Left slope (-1) and Right slope (+1)
        slope_angle = math.atan2(peak_h, half_span)
        for row in range(num_rows):
            t = (row + 0.5) / num_rows
            row_x = mx + side * (half_span * (1.0 - t))
            row_z = eave_z + peak_h * t

            # Stagger alternate rows (fish scale brick pattern)
            stagger = (row % 2) * (scale_w * 0.36)
            for col in range(num_cols + 1):
                col_y = (y0 - overhang_y + 0.25) + col * (scale_w * 0.72) + stagger
                if col_y > y1 + overhang_y - 0.15:
                    continue

                # Add tiny organic wobble so tiles look hand-laid
                rand_jitter = math.sin(row * 7.1 + col * 3.3) * 0.03
                tilt_pitch = slope_angle * side + rand_jitter + (0.12 * side)

                # Each scale is a beveled rounded tile (create_cone or tapered box)
                s_pos = (row_x, col_y, row_z)
                create_cone(bm, radius1=scale_w * 0.5, radius2=scale_w * 0.28, height=scale_l, segments=6,
                            location=s_pos,
                            rotation=(math.pi * 0.5, tilt_pitch, 0),
                            mat_index=MAT_INDEX_BONE)

    # 3. Ridge Dorsal Fin Bone & Jagged Teeth Crest
    _build_ridge_crest_fin_and_spines(bm, mx, y0 - overhang_y, y1 + overhang_y,
                                      peak_z + 0.18, fin_scale=fin_scale, num_teeth=num_ridge_teeth)


def _build_ridge_crest_fin_and_spines(bm, rx, y_start, y_end, rz, fin_scale=1.5, num_teeth=8):
    """Crown of giant curved shark dorsal fin and jagged bone spikes along the roof peak (Images 2, 4, 6)."""
    # 1. Primary giant dorsal fin bone near the front gable
    fin_y = y_start + 0.65
    fin_h = 1.35 * fin_scale
    fin_base_w = 0.95 * fin_scale
    # Curved predatory fin profile
    create_cone(bm, radius1=fin_base_w * 0.45, radius2=0.03, height=fin_h, segments=5,
                location=(rx, fin_y, rz + fin_h * 0.45),
                rotation=(0.28, 0, 0), mat_index=MAT_INDEX_BONE)

    # 2. Row of jagged curved bone teeth / horns running down the rest of the ridge
    spine_span = (y_end - (fin_y + fin_base_w * 0.6))
    if spine_span > 0.8 and num_teeth > 0:
        dy = spine_span / max(1, num_teeth)
        for i in range(num_teeth):
            ty = (fin_y + fin_base_w * 0.6) + (i + 0.5) * dy
            # Tooth height decreases slightly toward the rear
            t_ratio = 1.0 - 0.45 * (i / max(1, num_teeth - 1))
            th = (0.55 + 0.35 * math.sin(i * 1.5)) * t_ratio * fin_scale
            # Slight backward curve
            create_cone(bm, radius1=0.14 * t_ratio, radius2=0.015, height=th, segments=5,
                        location=(rx, ty, rz + th * 0.42),
                        rotation=(-0.25, 0, 0), mat_index=MAT_INDEX_BONE)


def _build_bone_scale_roof_conical(bm, cx, cy, eave_z, radius, height,
                                   fin_scale=1.4, num_spears=4):
    """Conical roof with concentric rings of thick overlapping rounded bone scale plates (Image 2)."""
    peak_z = eave_z + height
    num_rings = max(4, int(height * 2.8))

    for ring in range(num_rings):
        t = ring / num_rings
        ring_r = radius * (1.0 - t * 0.92)
        ring_z = eave_z + height * t
        circumference = 2.0 * math.pi * ring_r
        num_scales = max(6, int(circumference / 0.52))

        slope_pitch = math.atan2(height, radius)
        stagger = (ring % 2) * (math.pi / max(1, num_scales))

        for s in range(num_scales):
            ang = s * (2.0 * math.pi / num_scales) + stagger
            sx = cx + math.cos(ang) * ring_r
            sy = cy + math.sin(ang) * ring_r

            tile_w = 0.48 * (1.0 - t * 0.4)
            tile_l = 0.58
            create_cone(bm, radius1=tile_w * 0.5, radius2=tile_w * 0.25, height=tile_l, segments=6,
                        location=(sx, sy, ring_z),
                        rotation=(slope_pitch, 0, ang - math.pi * 0.5),
                        mat_index=MAT_INDEX_BONE)

    # Apex cap: Massive sharp dorsal fin bone with surrounding bone spears (Image 2)
    apex_z = peak_z + 0.1
    create_cylinder(bm, radius=0.55, height=0.22, segments=10,
                    location=(cx, cy, apex_z), mat_index=MAT_INDEX_DRIFTWOOD)

    # Central giant shark fin
    fin_h = 1.4 * fin_scale
    create_cone(bm, radius1=0.48, radius2=0.03, height=fin_h, segments=5,
                location=(cx, cy, apex_z + fin_h * 0.45),
                rotation=(0.25, 0, 0), mat_index=MAT_INDEX_BONE)

    # Miniature bone spears/arrows planted around fin
    for i in range(num_spears):
        ang = i * (2.0 * math.pi / num_spears) + math.pi * 0.25
        sp_x = cx + math.cos(ang) * 0.35
        sp_y = cy + math.sin(ang) * 0.35
        sp_h = 0.75 + 0.15 * math.sin(i * 2.0)
        # Shaft
        create_cylinder(bm, radius=0.02, height=sp_h, segments=5,
                        location=(sp_x, sp_y, apex_z + sp_h * 0.45),
                        rotation=(0.18 * math.sin(ang), 0.18 * math.cos(ang), 0),
                        mat_index=MAT_INDEX_DRIFTWOOD)
        # Bone arrowhead tip
        create_cone(bm, radius1=0.065, radius2=0.005, height=0.22, segments=4,
                    location=(sp_x, sp_y, apex_z + sp_h + 0.1),
                    rotation=(0, 0, 0), mat_index=MAT_INDEX_BONE)


# =============================================================================
# DEDICATED HAJFIN PRESET ARCHETYPE ASSEMBLERS
# =============================================================================

def _build_hajfin_shanty(bm, props, width=6.5, depth=7.5, height=3.6, found_h=1.2):
    """The Quintessential Hajfin Pirate Shanty (Image 6):
    Horizontal rough timber plank walls with iron spikes, 4 massive corner columns extending
    above eaves, shark jaw doorway with teeth, bone fin emblem, and bone-scale gable roof with ridge fin."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height

    # 1. Elevated Pier Stilts if foundation height > 0
    if found_h > 0.2:
        _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Main Building Shell: Chunky horizontal timber walls
    create_box(bm, (width, depth, height), (0.0, 0.0, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Horizontal wall battens & iron cleats/spikes driven into planks
    for bz in (z0 + height * 0.32, z0 + height * 0.68):
        create_box(bm, (width + 0.08, depth + 0.08, 0.18), (0.0, 0.0, bz), mat_index=MAT_INDEX_DRIFTWOOD)
        # Protruding iron cleats along walls
        for sgn_side in (-1.0, 1.0):
            for step_i in (-1, 0, 1):
                ix = step_i * (width * 0.32)
                create_cone(bm, radius1=0.035, radius2=0.005, height=0.24, segments=4,
                            location=(ix, sgn_side * (hd + 0.12), bz),
                            rotation=(sgn_side * math.pi * 0.5, 0, 0), mat_index=MAT_INDEX_IRON)

    # 3. 4 Oversized Timber Corner Columns
    col_size = 0.42
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z1, size=col_size, extend_top=0.45)

    # 4. Front Shark Jaw Doorway (on South / Front facade, Y = -hd)
    door_w = 1.40
    door_h = min(2.5, height * 0.72)
    _build_shark_jaw_doorway(bm, 0.0, -hd, z0, rot_z=0.0, width=door_w, height=door_h)

    # 5. Side Bone-Framed Barred Windows
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * hw, 0.0, z0 + height * 0.52,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.75, h=0.75)

    # 6. Thick Bone Scale Gable Roof
    roof_h = 3.2
    _build_bone_scale_roof_gable(bm, -hw, hw, -hd, hd, z1, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=1.5, num_ridge_teeth=7)


def _build_hajfin_round_hut(bm, props, diameter=7.5, height=3.8, found_h=0.8):
    """The Tapered Round Bone-Scale Hut (Image 2):
    8-sided tapered conical timber hut (wider at bottom, tapering up), massive perimeter posts,
    conical bone-scale roof, central shark fin crown with bone spears, shark jaw door,
    and massive whale vertebrae buttress curving up the rear wall!"""
    r_base = diameter * 0.5
    r_top = r_base * 0.82  # Tapered inward silhouette!
    z0 = found_h
    z1 = z0 + height
    num_facets = 8

    # 1. Stilt or reef stone foundation ring
    create_cylinder(bm, radius=r_base * 1.05, height=found_h + 0.1, segments=num_facets,
                    location=(0.0, 0.0, found_h * 0.5), mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Tapered 8-sided body shell with vertical driftwood planks
    body_h = height
    create_cone(bm, radius1=r_base, radius2=r_top, height=body_h, segments=num_facets,
                location=(0.0, 0.0, z0 + body_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Perimeter Timber Corner Posts at the 8 facet vertices
    col_size = 0.34
    for i in range(num_facets):
        ang = i * (2.0 * math.pi / num_facets)
        bx = math.cos(ang) * r_base
        by = math.sin(ang) * r_base
        tx = math.cos(ang) * r_top
        ty = math.sin(ang) * r_top
        # Lean angle
        lean_pitch = math.atan2(r_base - r_top, height)
        post_rot = (lean_pitch * math.sin(ang), -lean_pitch * math.cos(ang), ang)

        mid_x = (bx + tx) * 0.5
        mid_y = (by + ty) * 0.5
        create_box(bm, (col_size, col_size, height + 0.35), (mid_x, mid_y, z0 + height * 0.5),
                   rotation=post_rot, mat_index=MAT_INDEX_DRIFTWOOD)

        # Steel corner cuffs
        create_box(bm, (col_size + 0.04, col_size + 0.04, 0.22), (bx, by, z0 + 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)
        create_box(bm, (col_size + 0.04, col_size + 0.04, 0.22), (tx, ty, z1 - 0.2),
                   rotation=post_rot, mat_index=MAT_INDEX_IRON)

    # Horizontal reinforcement hoops
    for hz in (z0 + height * 0.35, z0 + height * 0.70):
        t = (hz - z0) / height
        hr = r_base * (1.0 - t) + r_top * t
        create_torus_ring(bm, (0.0, 0.0, hz), major_radius=hr + 0.02, minor_radius=0.035,
                          major_segments=num_facets, minor_segments=4, mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Front Shark Jaw Doorway (Facet at ang = -pi/2, South)
    door_w = 1.35
    door_h = 2.40
    _build_shark_jaw_doorway(bm, 0.0, -r_base, z0, rot_z=0.0, width=door_w, height=door_h)

    # 5. Rear Whale Spine / Vertebrae Buttress (Facet at ang = +pi/2, North)
    _build_whale_spine_buttress(bm, 0.0, r_base * 0.95, z0, rot_z=0.0, num_vertebrae=7, max_h=height * 0.9)

    # 6. Diagonal Bone-Framed Windows
    for ang in (-math.pi * 0.75, -math.pi * 0.25):
        wx = math.cos(ang) * (r_base * 0.6 + r_top * 0.4)
        wy = math.sin(ang) * (r_base * 0.6 + r_top * 0.4)
        _build_bone_window(bm, wx, wy, z0 + height * 0.55, rot_z=ang + math.pi * 0.5, w=0.68, h=0.68)

    # 7. Conical Bone Scale Roof
    roof_h = 3.2
    _build_bone_scale_roof_conical(bm, 0.0, 0.0, z1, radius=r_top * 1.25, height=roof_h,
                                   fin_scale=1.5, num_spears=4)


def _build_hajfin_crate_blockhouse(bm, props, width=7.0, depth=7.0, height=5.5, found_h=0.8):
    """The Heavy Timber Crate Blockhouse (Image 5):
    Solid cubic timber fortress shack with heavy square framing, bolted iron corner plates,
    flat planked deck roof with heavy beam rims, shark jaw doorway, bone-framed windows, and wall spikes."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height

    # 1. Foundation base
    create_box(bm, (width + 0.3, depth + 0.3, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
               mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Main Timber Shell
    create_box(bm, (width, depth, height), (0.0, 0.0, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Heavy Timber Braces & Grid Frames (Crate Construction)
    # Mid-height horizontal belt
    mid_z = z0 + height * 0.5
    create_box(bm, (width + 0.12, depth + 0.12, 0.28), (0.0, 0.0, mid_z), mat_index=MAT_INDEX_DRIFTWOOD)
    # Eave rim beam
    create_box(bm, (width + 0.16, depth + 0.16, 0.32), (0.0, 0.0, z1), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Massive Square Corner Columns
    col_size = 0.48
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            # Full height column with flat steel cap
            create_box(bm, (col_size, col_size, height + 0.25), (cx, cy, z0 + height * 0.5 + 0.125),
                       mat_index=MAT_INDEX_DRIFTWOOD)
            # Heavy metal L-brackets on all corners
            for bz in (z0 + 0.25, mid_z, z1):
                create_box(bm, (col_size + 0.05, col_size + 0.05, 0.32), (cx, cy, bz),
                           mat_index=MAT_INDEX_IRON)

    # 5. Flat Timber Deck Roof with heavy perimeter beam rim and metal corner caps
    deck_loc_z = z1 + 0.08
    create_box(bm, (width - 0.2, depth - 0.2, 0.15), (0.0, 0.0, deck_loc_z), mat_index=MAT_INDEX_FLOOR)
    # Roof rim parapet beams
    rim_th = 0.35
    for sgn_x in (-1.0, 1.0):
        create_box(bm, (rim_th, depth + 0.2, 0.32), (sgn_x * (hw - rim_th * 0.5), 0.0, z1 + 0.22),
                   mat_index=MAT_INDEX_DRIFTWOOD)
    for sgn_y in (-1.0, 1.0):
        create_box(bm, (width + 0.2, rim_th, 0.32), (0.0, sgn_y * (hd - rim_th * 0.5), z1 + 0.22),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # 6. Front Shark Jaw Doorway (South facade)
    _build_shark_jaw_doorway(bm, 0.0, -hd, z0, rot_z=0.0, width=1.45, height=2.45)

    # 7. Bone-Framed Barred Windows (2 on ground floor, 4 on upper level)
    # Upper front windows flanking emblem
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * (hw * 0.5), -hd, z0 + height * 0.74, rot_z=0.0, w=0.72, h=0.72)
    # Side windows
    for sgn_x in (-1.0, 1.0):
        for fl_z in (z0 + height * 0.28, z0 + height * 0.74):
            _build_bone_window(bm, sgn_x * hw, 0.0, fl_z,
                               rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.72, h=0.72)


def _build_hajfin_bone_shop(bm, props, width=9.5, depth=8.5, height=6.8, found_h=0.9):
    """The Bone & Drift Trading Post (Image 3):
    Two-storey trading depot with open barter stall counter, flip-up plank awning,
    flanking wooden dock platforms, second-level lookout room, giant mounted shark skull,
    bone-scale roofs, ladder, and trade sign."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    g_h = 3.4  # Ground floor height
    u_h = 3.0  # Upper tower height
    z_mid = z0 + g_h
    z_top = z_mid + u_h

    # 1. Ground Floor Shell
    create_box(bm, (width, depth, g_h), (0.0, 0.0, z0 + g_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 2. Massive Ground Floor Corner Columns
    col_size = 0.42
    for cx in (-hw, hw):
        for cy in (-hd, hd):
            _build_chunky_corner_column(bm, cx, cy, z0, z_mid, size=col_size, extend_top=0.2)

    # 3. Open Barter Trade Counter with Flip-Up Awning (Front Facade)
    counter_w = 3.6
    counter_d = 1.1
    counter_h = 1.0
    # Sunk counter shelf
    create_box(bm, (counter_w, counter_d, counter_h), (0.0, -hd - counter_d * 0.3, z0 + counter_h * 0.5),
               mat_index=MAT_INDEX_DRIFTWOOD)
    # Open serving hatch opening in wall
    create_box(bm, (counter_w * 0.95, 0.2, 1.4), (0.0, -hd, z0 + counter_h + 0.7), mat_index=MAT_INDEX_GLASS)

    # Flip-up plank awning overhead supported by diagonal struts
    awning_w = counter_w * 1.15
    awning_d = 1.4
    create_box(bm, (awning_w, awning_d, 0.08), (0.0, -hd - awning_d * 0.45, z0 + counter_h + 1.55),
               rotation=(0.32, 0, 0), mat_index=MAT_INDEX_DRIFTWOOD)

    # Plank Sign "BONE & DRIFT TRADING" mounted above awning
    create_box(bm, (3.2, 0.08, 0.55), (0.0, -hd - 0.15, z0 + counter_h + 1.95), mat_index=MAT_INDEX_DRIFTWOOD)

    # 4. Flanking Wooden Dock / Pier Platforms on left and right sides
    for sgn_x in (-1.0, 1.0):
        plat_w = 1.5
        plat_d = depth * 0.8
        px = sgn_x * (hw + plat_w * 0.5)
        # Platform deck
        create_box(bm, (plat_w, plat_d, 0.12), (px, 0.0, z0 + 1.2), mat_index=MAT_INDEX_FLOOR)
        # Support stilts underneath
        for py in (-plat_d * 0.4, 0.0, plat_d * 0.4):
            create_cylinder(bm, radius=0.12, height=z0 + 1.2, segments=6,
                            location=(px, py, (z0 + 1.2) * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 5. Second-Level Central Lookout Tower / Room
    u_w = width * 0.58
    u_d = depth * 0.72
    create_box(bm, (u_w, u_d, u_h), (0.0, 0.0, z_mid + u_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Corner posts for upper tower
    for cx in (-u_w * 0.5, u_w * 0.5):
        for cy in (-u_d * 0.5, u_d * 0.5):
            _build_chunky_corner_column(bm, cx, cy, z_mid, z_top, size=0.36, extend_top=0.3)

    # 6. Giant Open Shark Skull mounted on upper front facade (Image 3)
    _build_shark_skull_mount(bm, u_w * 0.28, -u_d * 0.5, z_mid + u_h * 0.62, rot_z=0.0, scale=1.1)

    # 7. Exterior Wooden Ladder leading to upper level
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

    # 9. Multi-Tier Bone Scale Roofs
    # Lower flanking roofs on ground floor
    for sgn_x in (-1.0, 1.0):
        lx0 = sgn_x * hw
        lx1 = sgn_x * (u_w * 0.5)
        fl_x0 = min(lx0, lx1)
        fl_x1 = max(lx0, lx1)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd, hd, z_mid, 1.8,
                                     overhang_x=0.35, overhang_y=0.35, fin_scale=1.1, num_ridge_teeth=4)

    # Upper Tower Main Roof with soaring shark dorsal fin
    _build_bone_scale_roof_gable(bm, -u_w * 0.5, u_w * 0.5, -u_d * 0.5, u_d * 0.5, z_top, 2.8,
                                 overhang_x=0.45, overhang_y=0.45, fin_scale=1.6, num_ridge_teeth=6)


def _build_hajfin_chieftain_hall(bm, props, width=12.0, depth=16.0, height=5.2, found_h=1.4):
    """The Chieftain Great Fin Hall (Image 4):
    Grand multi-tier staggered longhouse with central high nave and lower side wings,
    continuous ridge spine of giant curved bone horns leading to a soaring forward-curving horn/tusk,
    projecting whale rib cage tunnel entrance, and flanking tribal totem posts."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    z1 = z0 + height

    # 1. Elevated Reef Stone & Stilt Foundation
    create_box(bm, (width + 0.4, depth + 0.4, found_h + 0.1), (0.0, 0.0, found_h * 0.5),
               mat_index=MAT_INDEX_ROUGH_STONE)

    # 2. Main Central Longhouse Nave (higher)
    nave_w = width * 0.60
    nave_h = height
    create_box(bm, (nave_w, depth, nave_h), (0.0, 0.0, z0 + nave_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Flanking Lower Side Aisles/Wings
    side_w = (width - nave_w) * 0.5
    side_h = height * 0.65
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

    # 5. Projecting Whale Rib Cage Tunnel Entrance (South Facade)
    _build_whale_rib_tunnel_entrance(bm, 0.0, -hd, z0, rot_z=0.0, length=2.8, height=3.0, width=2.4, num_pairs=4)

    # Main Doorway inside tunnel
    _build_shark_jaw_doorway(bm, 0.0, -hd, z0, rot_z=0.0, width=1.65, height=2.80)

    # 6. Multi-Tier Dense Bone Scale Roofs
    # Lower Side Aisle Roofs
    for sgn_x in (-1.0, 1.0):
        ax0 = sgn_x * (nave_w * 0.5)
        ax1 = sgn_x * hw
        fl_x0 = min(ax0, ax1)
        fl_x1 = max(ax0, ax1)
        _build_bone_scale_roof_gable(bm, fl_x0, fl_x1, -hd * 0.85, hd * 0.85, z0 + side_h, 2.0,
                                     overhang_x=0.35, overhang_y=0.35, fin_scale=1.1, num_ridge_teeth=5)

    # High Nave Central Roof with giant horn/tusk & continuous spine
    roof_h = 4.4
    _build_bone_scale_roof_gable(bm, -nave_w * 0.5, nave_w * 0.5, -hd, hd, z0 + nave_h, roof_h,
                                 overhang_x=0.55, overhang_y=0.55, fin_scale=2.2, num_ridge_teeth=10)


def _build_hajfin_pirate_tavern(bm, props, width=11.0, depth=11.0, height=6.2, found_h=1.2):
    """The Barnacle Bilge Pirate Tavern:
    Multi-deck L-shaped pirate tavern with open-air stilt drinking veranda, grog barrels,
    staggered bone scale roofs, shark jaw doorway, and dorsal fin ridge ornaments."""
    hw = width * 0.5
    hd = depth * 0.5
    z0 = found_h
    wing_w = width * 0.52
    wing_d = depth * 0.48

    # 1. Stilt Pier Foundation
    _build_stilt_substructure(bm, -hw, hw, -hd, hd, found_h)

    # 2. Main L-Shaped Building Blocks
    # Main block
    m_w = width
    m_d = depth - wing_d
    my = -hd + m_d * 0.5
    create_box(bm, (m_w, m_d, height), (0.0, my, z0 + height * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)

    # Rear wing block
    create_box(bm, (wing_w, wing_d, height * 0.85), (hw - wing_w * 0.5, hd - wing_d * 0.5, z0 + height * 0.425),
               mat_index=MAT_INDEX_DRIFTWOOD)

    # 3. Open-Air Stilt Drinking Deck in the L-cutout (Front-Left)
    deck_w = width - wing_w
    deck_d = wing_d
    deck_x = -hw + deck_w * 0.5
    deck_y = hd - wing_d * 0.5
    create_box(bm, (deck_w, deck_d, 0.15), (deck_x, deck_y, z0 + 0.1), mat_index=MAT_INDEX_FLOOR)
    # Timber railing around drinking deck
    _build_timber_deck_railing(bm, deck_x, deck_y, z0 + 0.1, deck_w, deck_d)

    # Clustered grog barrels on the drinking deck
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

    # 5. Shark Jaw Entrance Doorways (Main South entrance + deck access door)
    _build_shark_jaw_doorway(bm, -0.6, -hd, z0, rot_z=0.0, width=1.55, height=2.55)
    _build_shark_jaw_doorway(bm, deck_x, my + m_d * 0.5, z0, rot_z=math.pi, width=1.35, height=2.30)

    # 6. Bone-Framed Windows
    for sgn_x in (-1.0, 1.0):
        _build_bone_window(bm, sgn_x * hw, my, z0 + height * 0.45,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.75, h=0.75)
        _build_bone_window(bm, sgn_x * hw, my, z0 + height * 0.80,
                           rot_z=(math.pi * 0.5 if sgn_x > 0 else -math.pi * 0.5), w=0.75, h=0.75)

    # 7. Bone Scale Roofs with Dorsal Fin Crests
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

    # Pier pilings
    for ix in range(nx):
        x = x0 + ix * ((x1 - x0) / (nx - 1))
        for iy in range(ny):
            y = y0 + iy * ((y1 - y0) / (ny - 1))
            # Pier log with slight crooked angle
            lean_x = (math.sin(ix * 3.3 + iy * 2.1) * 0.06)
            lean_y = (math.cos(ix * 2.7 + iy * 3.7) * 0.06)
            create_cylinder(bm, radius=0.18, height=height + 0.1, segments=7,
                            location=(x, y, height * 0.5),
                            rotation=(lean_y, lean_x, 0), mat_index=MAT_INDEX_DRIFTWOOD)

    # Heavy timber perimeter sill beams
    for sgn_y in (-1.0, 1.0):
        sy = y0 if sgn_y < 0 else y1
        create_box(bm, ((x1 - x0) + 0.3, 0.28, 0.28), ( (x0 + x1) * 0.5, sy, height - 0.14),
                   mat_index=MAT_INDEX_DRIFTWOOD)
    for sgn_x in (-1.0, 1.0):
        sx = x0 if sgn_x < 0 else x1
        create_box(bm, (0.28, (y1 - y0) + 0.3, 0.28), (sx, (y0 + y1) * 0.5, height - 0.14),
                   mat_index=MAT_INDEX_DRIFTWOOD)

    # Wooden access steps leading to front door
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
    # Corner posts
    for px in (cx - w * 0.5, cx + w * 0.5):
        for py in (cy - d * 0.5, cy + d * 0.5):
            create_cylinder(bm, radius=post_r, height=rail_h, segments=6,
                            location=(px, py, cz + rail_h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    # Top handrail
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

    # Apply organic wonkiness if requested
    wonkiness = getattr(props, 'wonkiness', 0.2)
    if wonkiness > 0.001:
        total_h = found_h + height + 4.0
        add_wonkiness(bm, z_min=0.0, z_max=total_h, amount=wonkiness, seed=seed)

    # Box UV mapping
    apply_box_uvs(bm, scale=1.0)

    # Write bmesh to obj
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

