"""Indoor furniture catalogue (beds, tables, storage, hearths).

Every builder models its piece once at a local origin (footprint centred on
X/Y, base at Z=0) and drops it with a single yaw+translation transform. This
mirrors ``furniture.py`` conventions exactly so the prop registry and the
interior composer can treat indoor and outdoor props identically (DRY).

Only MAT_INDEX_* slots are used, so standalone props and in-building
furnishing share materials with no extra setup.
"""

import math
import random
import bmesh
from mathutils import Matrix, Vector

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_torus_ring,
    create_hollow_cylinder, create_hollow_dish, create_organic_pumpkin,
    transform_faces, recalc_face_normals_safe,
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON,
    MAT_INDEX_CLAY, MAT_INDEX_WAX, MAT_INDEX_LANTERN,
    MAT_INDEX_FABRIC_WHITE, MAT_INDEX_FABRIC_RED, MAT_INDEX_FABRIC_STITCHED,
    MAT_INDEX_PLANT, MAT_INDEX_PUMPKIN, MAT_INDEX_PUMPKIN_STEM,
    MAT_INDEX_UPHOLSTERY, MAT_INDEX_CLOTH_LINEN, MAT_INDEX_BOTTLE_GLASS,
    MAT_INDEX_DIRT, MAT_INDEX_CUT_STONE,
    MAT_INDEX_LOG, MAT_INDEX_LOG_END, MAT_INDEX_STONE,
    MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2,
)


def _place(x, y, z_ground=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _create_pillow(bm, cx, cy, cz, length=0.38, width=0.48, height=0.13, tilt_deg=22.0, seed=0.0):
    """Plump pillow with lofted perimeter, central head depression, and realistic wrinkles."""
    Nx, Ny = 14, 14
    tilt_rad = math.radians(tilt_deg)
    cos_t, sin_t = math.cos(tilt_rad), math.sin(tilt_rad)

    verts_top = []
    verts_bot = []

    uv_scale = 1.25

    for i in range(Nx + 1):
        u = i / Nx
        lx = (u - 0.5) * 2.0  # -1 (back/headboard) to +1 (front/foot)
        sx = math.sin(math.pi * u)
        row_top = []
        row_bot = []
        for j in range(Ny + 1):
            v = j / Ny
            ly = (v - 0.5) * 2.0  # -1 (left) to +1 (right)
            sy = math.sin(math.pi * v)

            # Dome envelope with rounded squircle profile
            edge_dist = min(u, 1.0 - u, v, 1.0 - v)
            rim_profile = math.sin(min(1.0, edge_dist * 4.0) * math.pi * 0.5)
            D = (sx * sy) ** 0.45

            # Head impression at center
            r2 = lx * lx + ly * ly
            indent = -0.32 * math.exp(-3.5 * r2)

            # Organic pillow wrinkles
            w1 = 0.12 * math.sin(4.0 * lx + 3.0 * ly + seed) * D
            w2 = 0.08 * math.cos(5.0 * lx - 4.0 * ly + seed * 1.5) * D
            w3 = 0.05 * math.sin(8.0 * (lx + ly) + seed * 2.2) * D

            rim_thick = 0.035 * rim_profile
            z_top = rim_thick + height * max(0.0, 1.0 + indent + w1 + w2 + w3) * D
            z_bot = -rim_thick - height * 0.25 * D

            x_loc = (u - 0.5) * length
            y_loc = (v - 0.5) * width

            xt_t = x_loc * cos_t + z_top * sin_t
            zt_t = -x_loc * sin_t + z_top * cos_t

            xb_t = x_loc * cos_t + z_bot * sin_t
            zb_t = -x_loc * sin_t + z_bot * cos_t

            vt = bm.verts.new((cx + xt_t, cy + y_loc, cz + zt_t))
            vb = bm.verts.new((cx + xb_t, cy + y_loc, cz + zb_t))
            row_top.append(vt)
            row_bot.append(vb)
        verts_top.append(row_top)
        verts_bot.append(row_bot)

    uv_layer = bm.loops.layers.uv.verify()
    faces = []
    mat_index = MAT_INDEX_FABRIC_WHITE

    # Top faces with isometric surface unwrapping
    for i in range(Nx):
        for j in range(Ny):
            f = bm.faces.new([verts_top[i][j], verts_top[i+1][j], verts_top[i+1][j+1], verts_top[i][j+1]])
            f.material_index = mat_index
            f.smooth = True
            for loop in f.loops:
                lu = (i if loop.vert in (verts_top[i][j], verts_top[i][j+1]) else i + 1) / Nx
                lv = (j if loop.vert in (verts_top[i][j], verts_top[i+1][j]) else j + 1) / Ny
                loop[uv_layer].uv = Vector((lu * length * uv_scale, lv * width * uv_scale))
            f.tag = True
            faces.append(f)

    # Bottom faces
    for i in range(Nx):
        for j in range(Ny):
            f = bm.faces.new([verts_bot[i][j], verts_bot[i][j+1], verts_bot[i+1][j+1], verts_bot[i+1][j]])
            f.material_index = mat_index
            f.smooth = True
            for loop in f.loops:
                lu = (i if loop.vert in (verts_bot[i][j], verts_bot[i][j+1]) else i + 1) / Nx
                lv = (j if loop.vert in (verts_bot[i][j], verts_bot[i+1][j]) else j + 1) / Ny
                loop[uv_layer].uv = Vector((lu * length * uv_scale, lv * width * uv_scale))
            f.tag = True
            faces.append(f)

    # Perimeter closure with smooth normal shading
    for i in range(Nx):
        f = bm.faces.new([verts_top[i][0], verts_top[i+1][0], verts_bot[i+1][0], verts_bot[i][0]])
        f.material_index = mat_index
        f.smooth = True
        f.tag = True
        faces.append(f)
    for i in range(Nx):
        f = bm.faces.new([verts_top[i+1][Ny], verts_top[i][Ny], verts_bot[i][Ny], verts_bot[i+1][Ny]])
        f.material_index = mat_index
        f.smooth = True
        f.tag = True
        faces.append(f)
    for j in range(Ny):
        f = bm.faces.new([verts_top[0][j+1], verts_top[0][j], verts_bot[0][j], verts_bot[0][j+1]])
        f.material_index = mat_index
        f.smooth = True
        f.tag = True
        faces.append(f)
    for j in range(Ny):
        f = bm.faces.new([verts_top[Nx][j], verts_top[Nx][j+1], verts_bot[Nx][j+1], verts_bot[Nx][j]])
        f.material_index = mat_index
        f.smooth = True
        f.tag = True
        faces.append(f)

    return faces


def _create_quilt_and_cuff(bm, x_start=-0.38, x_end=0.92, w_mat=0.49, w_rail=0.615,
                           z_mat_top=0.39, z_skirt=0.13, thick=0.024, cuff_length=0.16):
    """Create a thick, cozy down quilt with smooth rounded shoulders and drape,
    plus true isometric arc-length UV unwrap and soft rolled cuffs.
    """
    Nx = 30
    Ny = 38

    L = x_end - x_start
    w_drape = w_rail + 0.035
    cuff_u_split = cuff_length / L
    z_rail_top = z_mat_top + 0.028

    # Pre-calculate base cross-section profile y_prof and z_prof to measure arc-length
    y_base = []
    z_base = []
    for j in range(Ny + 1):
        s = j / Ny
        if s <= 0.24:
            # Left skirt
            t = s / 0.24
            y0 = -w_drape + ((-w_rail) - (-w_drape)) * (t ** 1.35)
            z0 = z_skirt + (z_rail_top - z_skirt) * math.sin(t * math.pi * 0.5)
        elif s <= 0.34:
            # Left shoulder over rail (smooth C1 cosine curve)
            t = (s - 0.24) / 0.10
            blend = 0.5 - 0.5 * math.cos(t * math.pi)
            y0 = -w_rail + ((-w_mat) - (-w_rail)) * blend
            z0 = z_rail_top + 0.018 * math.sin(t * math.pi)
        elif s <= 0.66:
            # Mattress top
            t = (s - 0.34) / 0.32
            y0 = -w_mat + 2.0 * w_mat * t
            z0 = z_mat_top + 0.035 + 0.025 * math.sin(t * math.pi)
        elif s <= 0.76:
            # Right shoulder over rail
            t = (s - 0.66) / 0.10
            blend = 0.5 - 0.5 * math.cos(t * math.pi)
            y0 = w_mat + (w_rail - w_mat) * blend
            z0 = z_rail_top + 0.018 * math.sin(t * math.pi)
        else:
            # Right skirt
            t = (s - 0.76) / 0.24
            y0 = w_rail + (w_drape - w_rail) * (1.0 - (1.0 - t) ** 1.35)
            z0 = z_rail_top - (z_rail_top - z_skirt) * math.sin(t * math.pi * 0.5)
        y_base.append(y0)
        z_base.append(z0)

    # Compute physical arc-length along Y cross section
    arc_y = [0.0] * (Ny + 1)
    for j in range(1, Ny + 1):
        dy = y_base[j] - y_base[j - 1]
        dz = z_base[j] - z_base[j - 1]
        arc_y[j] = arc_y[j - 1] + math.sqrt(dy * dy + dz * dz)

    verts_top = []
    verts_bot = []

    for i in range(Nx + 1):
        u = i / Nx
        x = x_start + u * L

        row_top = []
        row_bot = []

        # Soft hanging drapery wave along length
        skirt_wave = 0.015 * math.sin(2.5 * math.pi * u + 0.3) + 0.006 * math.sin(5.0 * math.pi * u)

        # Rolled rounded curl at the head edge of the turned-down cuff (u=0)
        head_curl_x = 0.0
        head_curl_z = 0.0
        if u < 0.06:
            ct = 1.0 - (u / 0.06)
            head_curl_x = 0.010 * ct
            head_curl_z = -0.016 * (ct ** 1.5)

        # Soft tuck at the foot edge (u=1)
        foot_curl_z = 0.0
        if u > 0.94:
            ft = (u - 0.94) / 0.06
            foot_curl_z = -0.014 * (ft ** 1.5)

        for j in range(Ny + 1):
            s = j / Ny
            y = y_base[j]
            z = z_base[j]

            # Apply skirt wave to hanging skirts
            if s <= 0.24:
                t = s / 0.24
                y -= skirt_wave * (1.0 - t)
            elif s >= 0.76:
                t = (s - 0.76) / 0.24
                y += skirt_wave * t

            # Organic rumples & bedding creases across top
            w1 = 0.012 * math.sin(6.0 * x + 4.0 * y)
            w2 = 0.009 * math.cos(9.0 * x - 6.5 * y)
            w3 = 0.006 * math.sin(14.0 * (x - y))
            sag = -0.008 * math.exp(-((y / 0.35) ** 2)) * math.sin(math.pi * u)

            top_mask = 1.0 if (0.28 <= s <= 0.72) else max(0.0, 1.0 - abs(s - 0.5) * 2.3)

            # Puffy fold ridge for the turned-down sheet cuff
            cuff_ridge = 0.0
            if u < cuff_u_split:
                cuff_t = u / cuff_u_split
                cuff_ridge = 0.016 * math.sin(cuff_t * math.pi)

            z_top = z + (w1 + w2 + w3 + sag) * top_mask + cuff_ridge * top_mask + head_curl_z + foot_curl_z
            if 0.28 <= s <= 0.72:
                z_top = max(z_mat_top + 0.008, z_top)

            # Rounded tuck at bottom vertices so edges are soft and thick
            z_bot = z_top - thick
            x_top = x + head_curl_x
            x_bot = x_top

            vt = bm.verts.new((x_top, y, z_top))
            vb = bm.verts.new((x_bot, y, z_bot))
            row_top.append(vt)
            row_bot.append(vb)

        verts_top.append(row_top)
        verts_bot.append(row_bot)

    uv_layer = bm.loops.layers.uv.verify()
    faces = []
    # Real-world UV scale: ~1.0 gives a natural life-sized fabric scale (no tiny micro-repeats)
    uv_scale = 1.05

    # Top faces: true isometric arc-length UV unwrap!
    for i in range(Nx):
        u_mid = (i + 0.5) / Nx
        cell_mat = MAT_INDEX_FABRIC_WHITE if (u_mid < cuff_u_split) else MAT_INDEX_FABRIC_RED

        for j in range(Ny):
            ft = bm.faces.new([verts_top[i][j], verts_top[i+1][j], verts_top[i+1][j+1], verts_top[i][j+1]])
            ft.material_index = cell_mat
            ft.smooth = True
            for loop in ft.loops:
                i_idx = i if loop.vert in (verts_top[i][j], verts_top[i][j+1]) else i + 1
                j_idx = j if loop.vert in (verts_top[i][j], verts_top[i+1][j]) else j + 1
                u_coord = (i_idx / Nx) * L * uv_scale
                v_coord = arc_y[j_idx] * uv_scale
                loop[uv_layer].uv = Vector((u_coord, v_coord))
            ft.tag = True
            faces.append(ft)

            fb = bm.faces.new([verts_bot[i][j], verts_bot[i][j+1], verts_bot[i+1][j+1], verts_bot[i+1][j]])
            fb.material_index = cell_mat
            fb.smooth = True
            for loop in fb.loops:
                i_idx = i if loop.vert in (verts_bot[i][j], verts_bot[i][j+1]) else i + 1
                j_idx = j if loop.vert in (verts_bot[i][j], verts_bot[i+1][j]) else j + 1
                u_coord = (i_idx / Nx) * L * uv_scale
                v_coord = arc_y[j_idx] * uv_scale
                loop[uv_layer].uv = Vector((u_coord, v_coord))
            fb.tag = True
            faces.append(fb)

    # Perimeter closure with smooth normals
    for j in range(Ny):
        f = bm.faces.new([verts_top[0][j+1], verts_top[0][j], verts_bot[0][j], verts_bot[0][j+1]])
        f.material_index = MAT_INDEX_FABRIC_WHITE
        f.smooth = True
        f.tag = True
        faces.append(f)
    for j in range(Ny):
        f = bm.faces.new([verts_top[Nx][j], verts_top[Nx][j+1], verts_bot[Nx][j+1], verts_bot[Nx][j]])
        f.material_index = MAT_INDEX_FABRIC_RED
        f.smooth = True
        f.tag = True
        faces.append(f)
    for i in range(Nx):
        u_mid = (i + 0.5) / Nx
        mat = MAT_INDEX_FABRIC_WHITE if (u_mid < cuff_u_split) else MAT_INDEX_FABRIC_RED
        f = bm.faces.new([verts_top[i][0], verts_top[i+1][0], verts_bot[i+1][0], verts_bot[i][0]])
        f.material_index = mat
        f.smooth = True
        f.tag = True
        faces.append(f)
    for i in range(Nx):
        u_mid = (i + 0.5) / Nx
        mat = MAT_INDEX_FABRIC_WHITE if (u_mid < cuff_u_split) else MAT_INDEX_FABRIC_RED
        f = bm.faces.new([verts_top[i+1][Ny], verts_top[i][Ny], verts_bot[i][Ny], verts_bot[i+1][Ny]])
        f.material_index = mat
        f.smooth = True
        f.tag = True
        faces.append(f)

    return faces


def build_bed(bm, x, y, z_ground=0.0, ang=0.0, length=2.0, width=1.2):
    """Realistic wooden bedstead with headboard, footboard, and cozy bedding.

    Features 4 sturdy corner timber posts, wood headboard & footboard panels,
    a nested stitched mattress, propped fluffy wrinkled pillows with central
    head indentations, a continuous organic draped quilt with realistic folds
    and side skirts, and an integrated turned-down white sheet cuff.
    """
    faces = []
    frame_h = 0.32
    post_w = 0.09
    head_x = -length / 2 + post_w * 0.5
    foot_x = length / 2 - post_w * 0.5

    # 4 Corner timber posts
    head_post_h = 1.08
    foot_post_h = 0.68
    for sy in (-width / 2 + post_w / 2, width / 2 - post_w / 2):
        faces += create_beveled_box(bm, size=(post_w, post_w, head_post_h),
                                    location=(head_x, sy, head_post_h / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
        faces += create_beveled_box(bm, size=(post_w, post_w, foot_post_h),
                                    location=(foot_x, sy, foot_post_h / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Headboard panel & top rail
    panel_w = width - post_w * 2 + 0.02
    faces += create_beveled_box(bm, size=(0.045, panel_w, 0.70),
                                location=(head_x, 0.0, 0.60),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
    faces += create_beveled_box(bm, size=(0.075, panel_w + 0.04, 0.06),
                                location=(head_x, 0.0, 0.95),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Footboard panel & top rail
    faces += create_beveled_box(bm, size=(0.045, panel_w, 0.38),
                                location=(foot_x, 0.0, 0.42),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
    faces += create_beveled_box(bm, size=(0.075, panel_w + 0.04, 0.05),
                                location=(foot_x, 0.0, 0.61),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Side Rails
    rail_len = (foot_x - post_w * 0.5) - (head_x + post_w * 0.5)
    rail_cx = (head_x + foot_x) * 0.5
    for sy in (-width / 2 + post_w / 2, width / 2 - post_w / 2):
        faces += create_beveled_box(bm, size=(rail_len, 0.06, 0.22),
                                    location=(rail_cx, sy, 0.29),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Wooden mattress support slats (5 planks spanning across the bed frame)
    num_slats = 5
    slat_thick = 0.022
    slat_width = 0.10
    slat_len = width - post_w - 0.02  # mortised / resting inside side rail ledges
    slat_cz = 0.205
    for k in range(num_slats):
        u = (k + 0.5) / num_slats
        sx = (rail_cx - rail_len * 0.40) + u * (rail_len * 0.80)
        faces += create_beveled_box(bm, size=(slat_width, slat_len, slat_thick),
                                    location=(sx, 0.0, slat_cz),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)

    # Mattress
    mat_h = 0.18
    mat_len = rail_len - 0.02
    mat_w = width - post_w * 2 - 0.02
    mat_cz = 0.30
    faces += create_beveled_box(bm, size=(mat_len, mat_w, mat_h),
                                location=(rail_cx, 0.0, mat_cz),
                                mat_index=MAT_INDEX_FABRIC_STITCHED,
                                bevel_amount=0.035, bevel_segments=3)
    mat_top = mat_cz + mat_h * 0.5

    # Pillows propped against the headboard
    pil_x = head_x + post_w * 0.5 + 0.22
    if mat_w < 0.65:
        faces += _create_pillow(bm, pil_x, 0.0, mat_top + 0.02,
                                length=0.38, width=max(0.30, mat_w - 0.08), height=0.12,
                                tilt_deg=22.0, seed=3.0)
    else:
        pil_w = (mat_w - 0.05) * 0.5
        for sy, seed in ((-pil_w * 0.51, 2.0), (pil_w * 0.51, 7.0)):
            faces += _create_pillow(bm, pil_x, sy, mat_top + 0.02,
                                    length=0.38, width=pil_w, height=0.12,
                                    tilt_deg=22.0, seed=seed)

    # Continuous draped, wrinkled quilt with integrated white sheet cuff
    cov_start = pil_x + 0.16
    cov_end = foot_x - post_w * 0.5
    faces += _create_quilt_and_cuff(bm, x_start=cov_start, x_end=cov_end,
                                   w_mat=mat_w * 0.5 + 0.01, w_rail=width * 0.5 + 0.015,
                                   z_mat_top=mat_top, z_skirt=0.13, thick=0.024,
                                   cuff_length=0.16)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bunk_bed(bm, x, y, z_ground=0.0, ang=0.0, length=2.0, width=1.1):
    """Sturdy military bunk bed: four tall posts, two dressed sleeping berths
    (mattress + pillow + draped quilt each), an upper safety rail and a
    climbing ladder on the +Y side. Local frame matches build_bed
    (length along X, headboard end at -X)."""
    faces = []
    post_w = 0.10
    post_h = 1.85
    hx = -length / 2 + post_w * 0.5
    fx = length / 2 - post_w * 0.5
    hy = width / 2 - post_w / 2
    rail_len = (fx - post_w * 0.5) - (hx + post_w * 0.5)
    rail_cx = (hx + fx) * 0.5
    mat_w = width - post_w * 2 - 0.02

    # 4 tall corner posts
    for sx in (hx, fx):
        for sy in (-hy, hy):
            faces += create_beveled_box(bm, size=(post_w, post_w, post_h),
                                        location=(sx, sy, post_h * 0.5),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    # Full-height head & foot panels
    panel_w = width - post_w * 2 + 0.02
    for px in (hx, fx):
        faces += create_beveled_box(bm, size=(0.05, panel_w, post_h - 0.15),
                                    location=(px, 0.0, (post_h - 0.15) * 0.5 + 0.05),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)

    # Two dressed berths (lower + upper)
    for lvl_z, skirt_z, seed in ((0.32, 0.13, 3.0), (1.22, 0.95, 11.0)):
        for sy in (-hy, hy):
            faces += create_beveled_box(bm, size=(rail_len, 0.07, 0.20),
                                        location=(rail_cx, sy, lvl_z),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        for k in range(5):
            u = (k + 0.5) / 5
            sx = rail_cx - rail_len * 0.40 + u * rail_len * 0.80
            faces += create_beveled_box(bm, size=(0.10, mat_w, 0.022),
                                        location=(sx, 0.0, lvl_z - 0.085),
                                        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
        mat_top = lvl_z + 0.10
        faces += create_beveled_box(bm, size=(rail_len - 0.02, mat_w, 0.16),
                                    location=(rail_cx, 0.0, lvl_z + 0.02),
                                    mat_index=MAT_INDEX_FABRIC_STITCHED,
                                    bevel_amount=0.035, bevel_segments=3)
        pil_x = hx + post_w * 0.5 + 0.22
        faces += _create_pillow(bm, pil_x, 0.0, mat_top + 0.02,
                                length=0.36, width=max(0.30, mat_w - 0.08), height=0.11,
                                tilt_deg=22.0, seed=seed)
        # Quilt stops shy of the end posts so no cover clips the frame.
        faces += _create_quilt_and_cuff(bm, x_start=pil_x + 0.16, x_end=fx - post_w - 0.03,
                                        w_mat=mat_w * 0.5 + 0.01, w_rail=width * 0.5 + 0.015,
                                        z_mat_top=mat_top, z_skirt=skirt_z, thick=0.024,
                                        cuff_length=0.16)

    # Upper safety rail on the open (+Y) side, carried by the tall corner
    # posts alone (no mid balusters for the quilt to swallow).
    faces += create_beveled_box(bm, size=(length - 0.10, 0.06, 0.07),
                                location=(0.0, hy + 0.02, 1.68),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Climbing ladder: leans from the floor onto the upper side rail so it
    # reads as hooked over the frame instead of balancing beside it.
    lad_y_bot, lad_y_top, lad_h = hy + 0.30, hy + 0.06, 1.75
    lad_tilt = math.atan2(lad_y_bot - lad_y_top, lad_h)
    lad_y_mid = (lad_y_bot + lad_y_top) * 0.5
    for lx in (fx - 0.42, fx - 0.10):
        faces += create_beveled_box(bm, size=(0.06, 0.06, lad_h),
                                    location=(lx, lad_y_mid, lad_h * 0.5),
                                    rotation=(lad_tilt, 0.0, 0.0),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)
    for r in range(4):
        rz = 0.35 + r * 0.38
        ry = lad_y_bot + (lad_y_top - lad_y_bot) * (rz / lad_h)
        faces += create_cylinder(bm, radius=0.020, height=0.32, segments=6,
                                 location=((fx - 0.42 + fx - 0.10) * 0.5, ry, rz),
                                 rotation=(0.0, 1.5708, 0.0),
                                 mat_index=MAT_INDEX_WOOD)
    # Hook blocks tying the ladder top into the upper side rail.
    for lx in (fx - 0.42, fx - 0.10):
        faces += create_beveled_box(bm, size=(0.06, 0.16, 0.06),
                                    location=(lx, hy + 0.02, 1.30),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces
    """Simple high-back tavern chair."""
    faces = []
    seat_z, seat_s = seat_h, 0.44
    faces += create_beveled_box(bm, size=(seat_s, seat_s, 0.06),
                                location=(0.0, 0.0, seat_z),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
    for sx in (-seat_s / 2 + 0.04, seat_s / 2 - 0.04):
        for sy in (-seat_s / 2 + 0.04, seat_s / 2 - 0.04):
            faces += create_beveled_box(bm, size=(0.055, 0.055, seat_z),
                                        location=(sx, sy, seat_z / 2),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    # Back posts + slats
    for sx in (-seat_s / 2 + 0.04, seat_s / 2 - 0.04):
        faces += create_beveled_box(bm, size=(0.055, 0.055, 0.62),
                                    location=(sx, seat_s / 2 - 0.04, seat_z + 0.31),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    for bz in (seat_z + 0.30, seat_z + 0.52):
        faces += create_beveled_box(bm, size=(seat_s - 0.04, 0.045, 0.11),
                                    location=(0.0, seat_s / 2 - 0.04, bz),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
    # Side stretchers
    for sy in (-seat_s / 2 + 0.04, seat_s / 2 - 0.04):
        faces += create_beveled_box(bm, size=(seat_s - 0.08, 0.035, 0.035),
                                    location=(0.0, sy, 0.16),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_indoor_table(bm, x, y, z_ground=0.0, ang=0.0, length=1.6, width=0.9):
    """Rectangular indoor dining/work table with an H-stretcher between the legs."""
    faces = []
    top_z, top_t = 0.74, 0.07
    faces += create_beveled_box(bm, size=(length, width, top_t),
                                location=(0.0, 0.0, top_z),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
    leg_xs = (-length / 2 + 0.12, length / 2 - 0.12)
    leg_ys = (-width / 2 + 0.10, width / 2 - 0.10)
    for sx in leg_xs:
        for sy in leg_ys:
            faces += create_beveled_box(bm, size=(0.09, 0.09, top_z),
                                        location=(sx, sy, top_z / 2),
                                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # H-stretcher: side rails embedded 10mm into each leg + a cross rail.
    # Rails sit at the same height but never share a face plane (0.01 offsets).
    span_x = (leg_xs[1] - leg_xs[0]) + 0.02
    for i, sy in enumerate(leg_ys):
        faces += create_beveled_box(bm, size=(span_x, 0.06, 0.08),
                                    location=(0.0, sy, 0.22 + i * 0.01),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    span_y = (leg_ys[1] - leg_ys[0]) + 0.02
    faces += create_beveled_box(bm, size=(0.06, span_y, 0.06),
                                location=(0.0, 0.0, 0.225),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_round_table(bm, x, y, z_ground=0.0, ang=0.0, radius=0.55):
    """Round tavern table on a pedestal foot."""
    faces = []
    faces += create_cylinder(bm, radius=radius, height=0.07, segments=16,
                             location=(0.0, 0.0, 0.74), mat_index=MAT_INDEX_WOOD)
    faces += create_cylinder(bm, radius=0.09, height=0.70, segments=10,
                             location=(0.0, 0.0, 0.37), mat_index=MAT_INDEX_TIMBER)
    faces += create_cylinder(bm, radius=0.30, height=0.07, segments=12,
                             location=(0.0, 0.0, 0.035), mat_index=MAT_INDEX_TIMBER)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_shelf(bm, x, y, z_ground=0.0, ang=0.0, width=1.4, height=1.7):
    """Open wall shelf with evenly spaced boards and varied stored goods.

    Boards are embedded into the sides, gaps are equal, and goods (jars,
    pots, folded cloth, small crates) are spread deterministically across
    the bays instead of clustering at one side.
    """
    from .furniture import build_clay_pot
    faces = []
    depth, side_t = 0.34, 0.06
    for sx in (-width / 2 + side_t / 2, width / 2 - side_t / 2):
        faces += create_beveled_box(bm, size=(side_t, depth, height),
                                    location=(sx, 0.0, height / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    board_w = (width - side_t * 2) + 0.02
    n = 4
    # Even distribution across the FULL interior: the bottom board sits at
    # kick height and the top board leaves headroom for the tallest goods
    # (lidded clay jar ~0.27m) under the cap, with equal gaps in between.
    board_t = 0.05
    cap_bottom = height - 0.02
    goods_clear = 0.29
    first_top = 0.10 + board_t / 2
    last_top = cap_bottom - goods_clear
    step = (last_top - first_top) / (n - 1)
    rng = random.Random(4242)
    for i in range(n):
        sz = first_top + i * step - board_t / 2
        faces += create_beveled_box(bm, size=(board_w, depth - 0.02, board_t),
                                    location=(0.0, 0.0, sz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
        board_top = sz + board_t / 2
        # Two bays per shelf, alternating goods type by shelf index so the
        # whole unit reads varied rather than repeating one pattern.
        for b in range(2):
            bx = (-width / 4, width / 4)[b] + (rng.random() - 0.5) * 0.10
            kind = (i + b) % 3
            if kind == 0:
                faces += build_clay_pot(bm, bx, 0.0, z_ground=board_top - 0.004,
                                        radius=0.085, height=0.20, pot_type='JAR')
            elif kind == 1:
                faces += create_cylinder(bm, radius=0.075, height=0.17, segments=10,
                                         location=(bx, 0.0, board_top - 0.004 + 0.085),
                                         mat_index=MAT_INDEX_CLAY)
            else:
                faces += create_beveled_box(bm, size=(0.26, 0.20, 0.09),
                                            location=(bx, 0.0, board_top - 0.004 + 0.045),
                                            mat_index=MAT_INDEX_FABRIC_WHITE,
                                            bevel_amount=0.012)
    # Oversized cap overlapping the side tops (no touching faces).
    faces += create_beveled_box(bm, size=(width + 0.06, depth + 0.04, 0.06),
                                location=(0.0, 0.0, height - 0.02 + 0.03),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_wardrobe(bm, x, y, z_ground=0.0, ang=0.0, width=1.2, height=1.9):
    """Closed cupboard/wardrobe with proud double doors, full-height dark stile.

    The centre stile runs the full carcass height in dark timber, the door
    leaves sit proud of the carcass, and the cornice/plinth overlap the body
    instead of just touching it.
    """
    faces = []
    depth = 0.55
    front = -depth / 2
    faces += create_beveled_box(bm, size=(width, depth, height),
                                location=(0.0, 0.0, height / 2),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
    # Two proud door leaves (embedded 15mm, standing 15mm proud).
    leaf_w = width / 2 - 0.025
    for sx in (-width / 4, width / 4):
        faces += create_beveled_box(bm, size=(leaf_w, 0.03, height - 0.24),
                                    location=(sx, front, height / 2),
                                    mat_index=MAT_INDEX_WOOD, bevel_amount=0.006)
    # Full-height dark timber centre stile + top/bottom rails over the leaves.
    stile_h = height - 0.10
    faces += create_beveled_box(bm, size=(0.05, 0.035, stile_h),
                                location=(0.0, front - 0.012, 0.095 + stile_h / 2),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    for rz in (0.10 + 0.035, height - 0.035):
        faces += create_beveled_box(bm, size=(width - 0.04, 0.035, 0.07),
                                    location=(0.0, front - 0.012, rz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    for sx in (-width / 4, width / 4):
        faces += create_cylinder(bm, radius=0.025, height=0.03, segments=8,
                                 location=(sx * 0.4, front - 0.035, height / 2),
                                 rotation=(math.pi / 2, 0.0, 0.0),
                                 mat_index=MAT_INDEX_IRON)
    # Cornice overlaps the carcass top; plinth swallows the carcass bottom.
    faces += create_beveled_box(bm, size=(width + 0.08, depth + 0.08, 0.09),
                                location=(0.0, 0.0, height - 0.02 + 0.045),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    faces += create_beveled_box(bm, size=(width + 0.04, depth + 0.04, 0.12),
                                location=(0.0, 0.0, 0.04),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_chest(bm, x, y, z_ground=0.0, ang=0.0, width=0.9):
    """Low storage chest with overlapping lid and wrap-over iron bands.

    The lid overlaps 15mm into the body and the straps stand 3mm proud of
    the faces they cross, so nothing is coplanar.
    """
    faces = []
    h, d = 0.48, 0.50
    faces += create_beveled_box(bm, size=(width, d, h),
                                location=(0.0, 0.0, h / 2),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.012)
    lid_h = 0.10
    faces += create_beveled_box(bm, size=(width + 0.03, d + 0.03, lid_h),
                                location=(0.0, 0.0, h - 0.015 + lid_h / 2),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    lid_top = h - 0.015 + lid_h
    for sx in (-width * 0.28, width * 0.28):
        # Upright band on the body, standing 3mm proud, running 5mm into the lid.
        faces += create_beveled_box(bm, size=(0.07, d + 0.006, h),
                                    location=(sx, 0.0, h / 2 + 0.005),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
        # Strap across the lid top, embedded 5mm, standing proud.
        faces += create_beveled_box(bm, size=(0.07, d + 0.006, 0.02),
                                    location=(sx, 0.0, lid_top - 0.005 + 0.01),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_desk(bm, x, y, z_ground=0.0, ang=0.0, width=1.4):
    """Writing desk: top slab on two full panel legs (no floating drawers)."""
    faces = []
    top_z, depth = 0.76, 0.65
    faces += create_beveled_box(bm, size=(width, depth, 0.06),
                                location=(0.0, 0.0, top_z),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
    for sx in (-width / 2 + 0.06, width / 2 - 0.06):
        faces += create_beveled_box(bm, size=(0.10, depth - 0.06, top_z),
                                    location=(sx, 0.0, top_z / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_counter(bm, x, y, z_ground=0.0, ang=0.0, length=2.4):
    """Tavern bar counter with plank front and top slab."""
    faces = []
    h, d = 1.02, 0.60
    faces += create_beveled_box(bm, size=(length, d, h),
                                location=(0.0, 0.0, h / 2),
                                mat_index=MAT_INDEX_WOOD, bevel_amount=0.010)
    faces += create_beveled_box(bm, size=(length + 0.12, d + 0.14, 0.07),
                                location=(0.0, 0.0, h - 0.015 + 0.035),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    # Vertical plank seams on the front face
    n = max(3, int(length / 0.4))
    for i in range(n):
        px = -length / 2 + length * (i + 0.5) / n
        faces += create_beveled_box(bm, size=(0.025, 0.02, h - 0.14),
                                    location=(px, -d / 2 - 0.005, h / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.002)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_hearth(bm, x, y, z_ground=0.0, ang=0.0, width=1.6, height=1.5):
    """Stone fireplace with back panel, overlapping mantel and grounded andirons.

    Local frame: the firebox opens toward -Y (into the room); place the prop
    with its +Y back against the wall, under the chimney line, so the flue
    can rise straight into the chimney breast.
    """
    from ..materials import MAT_INDEX_STONE, MAT_INDEX_CUT_STONE
    faces = []
    depth = 0.55
    cheek_w = 0.40
    opening_w = width - cheek_w * 2
    # Firebox back panel (recessed 30mm behind the cheek fronts).
    faces += create_beveled_box(bm, size=(width - 0.10, 0.12, height - 0.30),
                                location=(0.0, depth / 2 - 0.06 - 0.03, (height - 0.30) / 2),
                                mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    # Side cheeks.
    for sx in (-width / 2 + cheek_w / 2, width / 2 - cheek_w / 2):
        faces += create_beveled_box(bm, size=(cheek_w, depth, height),
                                    location=(sx, 0.0, height / 2),
                                    mat_index=MAT_INDEX_STONE, bevel_amount=0.020)
    # Lintel spans BETWEEN the cheeks, embedded 10mm per side.
    faces += create_beveled_box(bm, size=(opening_w + 0.02, depth - 0.04, 0.30),
                                location=(0.0, -0.01, height - 0.15),
                                mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    # Mantel overlaps 20mm into the masonry below.
    faces += create_beveled_box(bm, size=(width + 0.16, depth + 0.10, 0.12),
                                location=(0.0, 0.0, height - 0.02 + 0.06),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    # Hearthstone slab + andiron dogs resting ON the slab (embedded 10mm).
    slab_top = 0.08
    faces += create_beveled_box(bm, size=(width + 0.20, depth + 0.45, 0.08),
                                location=(0.0, -0.10, 0.04),
                                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.008)
    for sx in (-0.25, 0.25):
        faces += create_beveled_box(bm, size=(0.06, 0.40, 0.07),
                                    location=(sx, -0.05, slab_top - 0.01 + 0.035),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _planar_uv(bm, faces, scale=2.6):
    """Size-preserving planar UVs for a slab (uniform density, no stretch).

    Each face is projected on its two in-plane world axes (times ``scale``),
    so texel density is identical on every face rather than being stretched
    across thin edges.
    """
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        if not f.is_valid:
            continue
        f.normal_update()
        n = f.normal
        nx, ny, nz = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if nz >= nx and nz >= ny:
                a, b = co.x, co.y
            elif nx >= ny:
                a, b = co.y, co.z
            else:
                a, b = co.x, co.z
            loop[uv_layer].uv = (a * scale, b * scale)
        f.tag = True


def _smart_page_uv(bm, faces, scale=2.6):
    """Orientation-proof page unwrap: V always follows the face's long axis.

    Per face, the two in-plane world axes are measured and the LONGER one
    becomes V (the page-line direction). Standing, leaning or lying, the
    lines therefore always run along the book. Tagged against later passes.
    """
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        if not f.is_valid:
            continue
        f.normal_update()
        n = f.normal
        nx, ny, nz = abs(n.x), abs(n.y), abs(n.z)
        if nz >= nx and nz >= ny:
            axes = ('x', 'y')
        elif nx >= ny:
            axes = ('y', 'z')
        else:
            axes = ('x', 'z')
        coords = [[loop.vert.co.x, loop.vert.co.y, loop.vert.co.z]
                  for loop in f.loops]
        idx = {'x': 0, 'y': 1, 'z': 2}
        a_vals = [c[idx[axes[0]]] for c in coords]
        b_vals = [c[idx[axes[1]]] for c in coords]
        ra = max(a_vals) - min(a_vals)
        rb = max(b_vals) - min(b_vals)
        for loop, a, b in zip(f.loops, a_vals, b_vals):
            u, v = (a, b) if ra <= rb else (b, a)
            loop[uv_layer].uv = (u * scale, v * scale)
        f.tag = True


def _book_base(bm, bw, bh, bd, leather_mat=None):
    """One canonical book: thick-walled cover wrap + nested page block.

    The leather cover is ONE continuous wrap with real outward thickness
    (outer wall, inner wall, top/bottom rim strips, front edge rims),
    flowing from straight sides into an elliptical spine arc. The page
    block nests inside with a recessed fore-edge. Verts/faces are created
    explicitly - no boolean-style ops anywhere. Centred at origin, spine
    toward +Y.
    """
    from ..materials import MAT_INDEX_LEATHER, MAT_INDEX_BOOK_PAPER
    mat_cov = MAT_INDEX_LEATHER if leather_mat is None else leather_mat
    t = 0.006
    ry = min(0.018, bw * 0.32)
    y_j = bd / 2 - ry
    N = 8
    outer = [(bw / 2, -bd / 2), (bw / 2, y_j)]
    for k in range(1, N):
        a = math.pi * k / N
        outer.append((bw / 2 * math.cos(a), y_j + ry * math.sin(a)))
    outer += [(-bw / 2, y_j), (-bw / 2, -bd / 2)]
    inner = [(bw / 2 - t, -bd / 2), (bw / 2 - t, y_j)]
    for k in range(1, N):
        a = math.pi * k / N
        inner.append(((bw / 2 - t) * math.cos(a),
                      y_j + (ry - t) * math.sin(a)))
    inner += [(-(bw / 2 - t), y_j), (-(bw / 2 - t), -bd / 2)]

    def _ring(pts, z):
        return [bm.verts.new((px, py, z)) for (px, py) in pts]

    def _quad(a, b, c, d, mat):
        try:
            f = bm.faces.new([a, b, c, d])
        except ValueError:
            return None
        f.material_index = mat
        return f

    ob, ot = _ring(outer, -bh / 2), _ring(outer, bh / 2)
    ib, it = _ring(inner, -bh / 2), _ring(inner, bh / 2)
    leather = []
    n = len(outer)
    for i in range(n - 1):
        j = i + 1
        f = _quad(ob[i], ob[j], ot[j], ot[i], mat_cov)      # outer wall
        if f is not None:
            leather.append(f)
        f = _quad(ib[j], ib[i], it[i], it[j], mat_cov)      # inner wall
        if f is not None:
            leather.append(f)
        f = _quad(ot[i], ot[j], it[j], it[i], mat_cov)      # top rim
        if f is not None:
            leather.append(f)
        f = _quad(ob[j], ob[i], ib[i], ib[j], mat_cov)      # bottom rim
        if f is not None:
            leather.append(f)
    # Front edge rims (visible cover thickness at the fore-edge).
    f = _quad(ob[0], ot[0], it[0], ib[0], mat_cov)
    if f is not None:
        leather.append(f)
    f = _quad(ob[-1], ib[-1], it[-1], ot[-1], mat_cov)
    if f is not None:
        leather.append(f)

    # Pages nested inside: contours directly into the inner spine curve with
    # a tight 2.5mm clearance, eliminating the hollow gap at the spine.
    pg_clear = 0.002
    pg_w = bw - 2 * t - 2 * pg_clear
    pg_h = bh - 0.016
    pg_front = -bd / 2 + 0.008
    ry_pg = max(0.005, ry - t - 0.0025)

    pg_pts = [(pg_w / 2, pg_front), (pg_w / 2, y_j)]
    for k in range(1, N):
        a = math.pi * k / N
        pg_pts.append(((pg_w / 2) * math.cos(a), y_j + ry_pg * math.sin(a)))
    pg_pts += [(-pg_w / 2, y_j), (-pg_w / 2, pg_front)]

    pb = [bm.verts.new((px, py, -pg_h / 2)) for (px, py) in pg_pts]
    pt = [bm.verts.new((px, py,  pg_h / 2)) for (px, py) in pg_pts]

    pages = []
    M = len(pg_pts)
    for i in range(M - 1):
        f = _quad(pb[i], pb[i+1], pt[i+1], pt[i], MAT_INDEX_BOOK_PAPER)
        if f is not None:
            pages.append(f)
    # Fore-edge face connecting front-left to front-right
    f = _quad(pb[-1], pb[0], pt[0], pt[-1], MAT_INDEX_BOOK_PAPER)
    if f is not None:
        pages.append(f)
    # Top and bottom page caps (head and tail)
    try:
        f_top = bm.faces.new(pt)
        f_top.material_index = MAT_INDEX_BOOK_PAPER
        pages.append(f_top)
    except ValueError:
        pass
    try:
        f_bot = bm.faces.new(pb[::-1])
        f_bot.material_index = MAT_INDEX_BOOK_PAPER
        pages.append(f_bot)
    except ValueError:
        pass

    _smart_page_uv(bm, pages, scale=2.6)
    _planar_uv(bm, leather, scale=3.2)
    return pages + leather






def _seat(part, cx, cy, cz, yaw=0.0, tip=0.0, lay_first=False):
    """Rigid placement for a canonical book part.

    Upright: yaw about Z then tip about Y (``lay_first=False``). Lying:
    lay flat first, then yaw (``lay_first=True``). UVs ride along untouched.
    """
    from mathutils import Matrix as _M
    if lay_first:
        mat = (_M.Translation((cx, cy, cz))
               @ _M.Rotation(yaw, 4, 'Z')
               @ _M.Rotation(math.pi / 2, 4, 'Y'))
    else:
        mat = (_M.Translation((cx, cy, cz))
               @ _M.Rotation(tip, 4, 'Y')
               @ _M.Rotation(yaw, 4, 'Z'))
    transform_faces(part, mat)


def _upright_book(bm, faces, cx, base, bw, bh, lean=0.0, leather_mat=None,
                  bd=0.20):
    """One upright book from the canonical builder (spine out, same every copy)."""
    part = _book_base(bm, bw, bh, bd, leather_mat)
    _seat(part, cx, 0.0, base + bh / 2, yaw=math.pi, tip=lean)
    faces += part
    return bw


def _lay_book(bm, faces, x, y, z0, bw, bh, bd, yaw=0.0, leather_mat=None):
    """The same canonical book laid flat (rigid transform: identical UVs)."""
    part = _book_base(bm, bw, bh, bd, leather_mat)
    _seat(part, x, y, z0 + bw / 2, yaw=yaw, lay_first=True)
    faces += part
    return bw


def _leather_cycle():
    """The three bookbinding leathers, cycled for variety."""
    from ..materials import (MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2,
                             MAT_INDEX_LEATHER_3)
    return (MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_LEATHER_3)


def _dress_row(bm, faces, top, x0, x1, seed, mode, mat_a, mat_b):
    """Fill one shelf row between ``x0`` and ``x1``.

    ``mode`` is 'messy' (stacks, gaps, leaner, mixed heights — every row
    seeded differently so no two shelves duplicate) or 'neat' (one even
    run of identical books).
    """
    rng = random.Random(seed)
    bx = x0
    k = 0
    limit = x1
    leathers = _leather_cycle()
    if mode == 'neat':
        while bx < limit:
            bw = 0.058
            if bx + bw > limit + 0.01:
                break
            _upright_book(bm, faces, bx + bw / 2, top, bw, 0.24,
                          leather_mat=leathers[k % 3])
            bx += bw + 0.008
            k += 1
            if k > 16:
                break
        return
    gap_at = rng.randint(2, 5)
    stack_at = {rng.randint(1, 3), rng.randint(4, 6)}
    while bx < limit:
        if k == gap_at:
            bx += 0.10 + rng.random() * 0.12
            k += 1
            continue
        if k in stack_at and bx + 0.30 < limit:
            # Literally the same pile builder the pile props use.
            _pile_books(bm, faces, bx + 0.14, 0.0, top, 2 + (k % 2),
                        seed + k * 31, w_base=0.24)
            bx += 0.28
            k += 1
            continue
        bw = 0.055 + (0.02 if k % 3 == 0 else 0.0)
        if bx + bw > limit + 0.02:
            break
        cx = bx + bw / 2
        bh = 0.24 if k % 4 != 3 else 0.20
        _upright_book(bm, faces, cx, top, bw, bh,
                      leather_mat=leathers[k % 3])
        bx += bw + 0.010
        k += 1
        if k > 14:
            break
    if limit - bx > 0.10 and k > 3 and rng.random() < 0.8:
        _upright_book(bm, faces, bx + 0.045, top - 0.012, 0.06, 0.22,
                      lean=-0.18, leather_mat=mat_a)


def _bookshelf_frame(bm, width, height, depth=0.32):
    """Shared carcass: sides plus overlapping cap/plinth. Returns faces, side_t."""
    from ..materials import MAT_INDEX_TIMBER
    side_t = 0.06
    faces = []
    for sx in (-width / 2 + side_t / 2, width / 2 - side_t / 2):
        faces += create_beveled_box(bm, size=(side_t, depth, height),
                                    location=(sx, 0.0, height / 2),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    faces += create_beveled_box(bm, size=(width + 0.06, depth + 0.04, 0.07),
                                location=(0.0, 0.0, height - 0.02 + 0.035),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    faces += create_beveled_box(bm, size=(width + 0.04, depth + 0.02, 0.10),
                                location=(0.0, 0.0, 0.05),
                                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    return faces, side_t


def _pile_books(bm, faces, cx, cy, z0, count, seed, w_base=0.30):
    """A casual stack of flat books with jittered size, offset and yaw.

    Single source for every lying stack: the pile props AND the bookcase
    dress their stacks through this exact function. Alternates spines
    forward and backward with pronounced rotation for disorganized piles.
    """
    rng = random.Random(seed)
    z = z0
    for i in range(count):
        bw = 0.058
        bh = w_base - i * 0.012 + (rng.random() - 0.5) * 0.02
        bd = 0.20 - i * 0.005
        # Varied spine direction: mix spines forward (pi) and backward (0.0)
        spine_forward = (i % 2 == 1) if (rng.random() < 0.85) else (rng.random() < 0.5)
        base_yaw = math.pi if spine_forward else 0.0
        yaw_jitter = (rng.random() - 0.5) * 0.85  # ~ +/- 24 deg casual rotation
        yaw = base_yaw + yaw_jitter
        _lay_book(bm, faces, cx + (rng.random() - 0.5) * 0.04,
                  cy + (rng.random() - 0.5) * 0.03, z, bw, bh, bd,
                  yaw=yaw,
                  leather_mat=_leather_cycle()[i % 3])
        z += bw


def build_book_pile_small(bm, x, y, z_ground=0.0, ang=0.0):
    """A small pile of four flat books (table/desk clutter)."""
    faces = []
    _pile_books(bm, faces, 0.0, 0.0, 0.0, 4, seed=21, w_base=0.28)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_book_pile_large(bm, x, y, z_ground=0.0, ang=0.0):
    """A large pile of seven flat books (floor/library clutter)."""
    faces = []
    _pile_books(bm, faces, 0.0, 0.0, 0.0, 7, seed=77, w_base=0.32)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_book_single(bm, x, y, z_ground=0.0, ang=0.0):
    """One canonical book standing spine-out, for close inspection.

    Iterate on this prop to perfect the book: every shelf, pile and row
    reuses this exact geometry through rigid transforms.
    """
    from ..materials import MAT_INDEX_LEATHER
    faces = []
    _upright_book(bm, faces, 0.0, 0.0, 0.06, 0.24,
                  leather_mat=MAT_INDEX_LEATHER)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bookshelf(bm, x, y, z_ground=0.0, ang=0.0, width=1.2, height=1.8):
    """Lived-in bookshelf: every shelf dressed differently (stacks/gaps/leaner)."""
    from ..materials import MAT_INDEX_LEATHER as MAT_LEATHER
    from ..materials import MAT_INDEX_LEATHER_2 as MAT_LEATHER_2
    from ..materials import MAT_INDEX_TIMBER
    faces, side_t = _bookshelf_frame(bm, width, height)
    # Four evenly divided shelves; build all boards first so bevels don't clear face tags.
    board_w = (width - side_t * 2) + 0.02
    for i in range(4):
        sz = 0.10 + i * (height - 0.41) / 3.0
        faces += create_beveled_box(bm, size=(board_w, 0.30, 0.045),
                                    location=(0.0, 0.0, sz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)
    for i in range(4):
        sz = 0.10 + i * (height - 0.41) / 3.0
        _dress_row(bm, faces, sz + 0.0225,
                   -width / 2 + side_t + 0.03, width / 2 - side_t - 0.05,
                   1000 + i * 977 + int(width * 13), 'messy',
                   MAT_LEATHER, MAT_LEATHER_2)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bookshelf_neat(bm, x, y, z_ground=0.0, ang=0.0, width=1.2, height=1.8):
    """Ordered bookcase: four identical even runs, no stacks or leaners."""
    from ..materials import MAT_INDEX_LEATHER as MAT_LEATHER
    from ..materials import MAT_INDEX_LEATHER_2 as MAT_LEATHER_2
    from ..materials import MAT_INDEX_TIMBER
    faces, side_t = _bookshelf_frame(bm, width, height)
    board_w = (width - side_t * 2) + 0.02
    for i in range(4):
        sz = 0.10 + i * (height - 0.41) / 3.0
        faces += create_beveled_box(bm, size=(board_w, 0.30, 0.045),
                                    location=(0.0, 0.0, sz),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)
    for i in range(4):
        sz = 0.10 + i * (height - 0.41) / 3.0
        _dress_row(bm, faces, sz + 0.0225,
                   -width / 2 + side_t + 0.03, width / 2 - side_t - 0.05,
                   500 + i, 'neat', MAT_LEATHER, MAT_LEATHER_2)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_cauldron(bm, x, y, z_ground=0.0, ang=0.0):
    """Small stove pot with a fitted lid and top handle (sits on stoves).

    Registry key ``CAULDRON`` is kept so furnishing recipes and saved
    settings keep working; the geometry is now a tidy lidded pot.
    """
    faces = []
    r, h = 0.20, 0.24
    seg = 24
    # Body stands straight on the ground; rolled torus edges read as rounded.
    faces += create_cylinder(bm, radius=r, height=h, segments=seg,
                             location=(0.0, 0.0, h / 2), mat_index=MAT_INDEX_IRON)
    # Rounded foot roll + top rim band with its own rounded lip.
    faces += create_torus_ring(bm, location=(0.0, 0.0, 0.018),
                               major_radius=r - 0.005, minor_radius=0.018,
                               major_segments=seg, minor_segments=8,
                               mat_index=MAT_INDEX_IRON)
    faces += create_cylinder(bm, radius=r + 0.015, height=0.03, segments=seg,
                             location=(0.0, 0.0, h - 0.01 + 0.015),
                             mat_index=MAT_INDEX_IRON)
    faces += create_torus_ring(bm, location=(0.0, 0.0, h + 0.005),
                               major_radius=r + 0.015 - 0.006, minor_radius=0.010,
                               major_segments=seg, minor_segments=8,
                               mat_index=MAT_INDEX_IRON)
    # Lid overlapping into the body, with a rounded lid edge.
    lid_r = r * 0.92
    lid_cz = h + 0.005 + 0.02
    faces += create_cylinder(bm, radius=lid_r, height=0.04, segments=seg,
                             location=(0.0, 0.0, lid_cz), mat_index=MAT_INDEX_IRON)
    faces += create_torus_ring(bm, location=(0.0, 0.0, lid_cz + 0.02),
                               major_radius=lid_r - 0.008, minor_radius=0.012,
                               major_segments=seg, minor_segments=8,
                               mat_index=MAT_INDEX_IRON)
    # Turned wooden knob handle standing on the lid (embedded, never floating).
    faces += create_cylinder(bm, radius=0.035, height=0.05, segments=12,
                             location=(0.0, 0.0, lid_cz + 0.02 + 0.025 - 0.005),
                             mat_index=MAT_INDEX_TIMBER)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


build_pot = build_cauldron


def _normalize_candle_uv(bm, faces, cx, cy, z0, z1, r):
    """Normalized 0..1 UVs for a candle: wrap once around the sides."""
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        if not f.is_valid:
            continue
        n = f.normal
        if abs(n.z) > 0.7 and len(f.loops) > 4:
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_layer].uv = ((co.x - cx) / (2 * r) + 0.5,
                                     (co.y - cy) / (2 * r) + 0.5)
        elif len(f.loops) == 4:
            for loop in f.loops:
                co = loop.vert.co
                u = (math.atan2(co.y - cy, co.x - cx) / (2.0 * math.pi)) % 1.0
                v = (co.z - z0) / max(1e-6, z1 - z0)
                loop[uv_layer].uv = (u, v)
        f.tag = True


def build_chandelier(bm, x, y, z_top=2.4, ang=0.0, radius=0.45):
    """Wagon-wheel chandelier: open timber ring, wax candles, link chain.

    An open ring (torus + spokes) lets the candlelight fall through instead
    of pooling on a solid disc. ``z_top`` anchors the ceiling mount, and all
    parts hang downward into the room.
    """
    from ..materials import MAT_INDEX_LANTERN, MAT_INDEX_WAX
    faces = []
    # Ceiling mount + three interlocking vertical links down to the stem.
    faces += create_cylinder(bm, radius=0.06, height=0.03, segments=10,
                             location=(0.0, 0.0, -0.015), mat_index=MAT_INDEX_IRON)
    for i in range(3):
        lz = -0.05 - i * 0.055
        rot = (math.pi * 0.5, 0.0, 0.0) if i % 2 == 0 else (0.0, math.pi * 0.5, 0.0)
        faces += create_torus_ring(bm, location=(0.0, 0.0, lz), rotation=rot,
                                   major_radius=0.032, minor_radius=0.008,
                                   major_segments=10, minor_segments=6,
                                   mat_index=MAT_INDEX_IRON)
    # Iron stem from the last link down to the hub.
    faces += create_cylinder(bm, radius=0.022, height=0.42, segments=8,
                             location=(0.0, 0.0, -0.41), mat_index=MAT_INDEX_IRON)
    wheel_cz = -0.63
    # Open timber wheel ring + hub + spokes (light falls through the middle).
    faces += create_torus_ring(bm, location=(0.0, 0.0, wheel_cz),
                               major_radius=radius, minor_radius=0.055,
                               major_segments=36, minor_segments=14,
                               mat_index=MAT_INDEX_TIMBER)
    # Hub + spokes embedded into the wheel.
    faces += create_cylinder(bm, radius=0.07, height=0.10, segments=10,
                             location=(0.0, 0.0, wheel_cz), mat_index=MAT_INDEX_IRON)
    for i in range(3):
        a = math.pi * i / 3
        faces += create_beveled_box(bm, size=(radius * 2 - 0.06, 0.045, 0.045),
                                    location=(0.0, 0.0, wheel_cz),
                                    rotation=(0.0, 0.0, a),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005)
    # Hanger rods from the stem to the ring (embedded both ends).
    rod_top_z = -0.30
    for i in range(3):
        a = 2.0 * math.pi * i / 3 + 0.5
        px, py = math.cos(a) * radius * 0.94, math.sin(a) * radius * 0.94
        mx, my, mz = px / 2, py / 2, (rod_top_z + wheel_cz) / 2
        run = math.hypot(px, py)
        rise = rod_top_z - wheel_cz
        rod_len = math.hypot(run, rise) + 0.06
        yaw = math.atan2(py, px)
        pitch = math.atan2(rise, run)
        faces += create_beveled_box(bm, size=(rod_len, 0.025, 0.025),
                                    location=(mx, my, mz),
                                    rotation=(0.0, pitch, yaw),
                                    mat_index=MAT_INDEX_IRON, bevel_amount=0.003)
    # Six candles riding on the ring: iron cup + wax + emissive wick.
    for i in range(6):
        a = 2.0 * math.pi * i / 6
        cx, cy = math.cos(a) * radius, math.sin(a) * radius
        ring_top = wheel_cz + 0.055
        faces += create_cylinder(bm, radius=0.045, height=0.03, segments=10,
                                 location=(cx, cy, ring_top - 0.005 + 0.015),
                                 mat_index=MAT_INDEX_IRON)
        candle_z0 = ring_top + 0.01
        candle = create_cylinder(bm, radius=0.032, height=0.15, segments=12,
                                 location=(cx, cy, candle_z0 + 0.075),
                                 mat_index=MAT_INDEX_WAX)
        faces += candle
        _normalize_candle_uv(bm, candle, cx, cy, candle_z0, candle_z0 + 0.15, 0.032)
        faces += create_cylinder(bm, radius=0.006, height=0.025, segments=6,
                                 location=(cx, cy, candle_z0 + 0.15 + 0.008),
                                 mat_index=MAT_INDEX_LANTERN)
    transform_faces(faces, _place(x, y, z_top, ang))
    return faces


def build_kitchen_stove(bm, x, y, z_ground=0.0, ang=0.0, width=0.95, depth=0.75, height=1.05):
    """Cast-iron kitchen cookstove with heavy firebox, oven doors, cooking rings, and rear flue pipe."""
    faces = []
    leg_h = 0.22
    leg_w = 0.07
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            lx = sx * (width * 0.5 - 0.08)
            ly = sy * (depth * 0.5 - 0.08)
            faces += create_beveled_box(
                bm, size=(leg_w, leg_w, leg_h),
                location=(lx, ly, leg_h * 0.5),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.01
            )
            faces += create_beveled_box(
                bm, size=(leg_w + 0.04, leg_w + 0.04, 0.03),
                location=(lx, ly, 0.015),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.005
            )

    body_h = 0.65
    body_cz = leg_h + body_h * 0.5
    faces += create_beveled_box(
        bm, size=(width, depth, body_h),
        location=(0.0, 0.0, body_cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.02
    )

    top_t = 0.05
    top_w = width + 0.08
    top_d = depth + 0.08
    top_cz = leg_h + body_h + top_t * 0.5
    faces += create_beveled_box(
        bm, size=(top_w, top_d, top_t),
        location=(0.0, 0.0, top_cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.01
    )

    ring_r = 0.16
    for rx in (-width * 0.24, width * 0.24):
        faces += create_cylinder(
            bm, radius=ring_r, height=0.015, segments=16,
            location=(rx, 0.0, leg_h + body_h + top_t + 0.005),
            mat_index=MAT_INDEX_IRON
        )
        faces += create_torus_ring(
            bm, location=(rx, 0.0, leg_h + body_h + top_t + 0.02),
            rotation=(math.pi * 0.5, 0.0, 0.0),
            major_radius=0.025, minor_radius=0.006,
            major_segments=10, minor_segments=6,
            mat_index=MAT_INDEX_IRON
        )

    door_w = width * 0.75
    door_h = body_h * 0.45
    faces += create_beveled_box(
        bm, size=(door_w, 0.04, door_h),
        location=(0.0, -depth * 0.5 - 0.015, leg_h + body_h * 0.65),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.008
    )
    faces += create_beveled_box(
        bm, size=(0.14, 0.03, 0.03),
        location=(door_w * 0.35, -depth * 0.5 - 0.04, leg_h + body_h * 0.65),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
    )

    ash_h = body_h * 0.22
    faces += create_beveled_box(
        bm, size=(door_w, 0.03, ash_h),
        location=(0.0, -depth * 0.5 - 0.012, leg_h + ash_h * 0.5 + 0.04),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006
    )

    pipe_r = 0.09
    pipe_h = height - (leg_h + body_h + top_t) + 0.60
    pipe_cz = leg_h + body_h + top_t + pipe_h * 0.5
    pipe_y = depth * 0.5 - pipe_r - 0.04
    faces += create_cylinder(
        bm, radius=pipe_r, height=pipe_h, segments=16,
        location=(0.0, pipe_y, pipe_cz),
        mat_index=MAT_INDEX_IRON
    )
    faces += create_torus_ring(
        bm, location=(0.0, pipe_y, leg_h + body_h + top_t + 0.04),
        major_radius=pipe_r + 0.01, minor_radius=0.012,
        major_segments=16, minor_segments=8,
        mat_index=MAT_INDEX_IRON
    )

    # Simmering pot on left burner
    pot_faces = create_cylinder(
        bm, radius=0.13, height=0.16, segments=14,
        location=(-width * 0.24, 0.0, leg_h + body_h + top_t + 0.08),
        mat_index=MAT_INDEX_IRON
    )
    pot_faces += create_cylinder(
        bm, radius=0.135, height=0.02, segments=14,
        location=(-width * 0.24, 0.0, leg_h + body_h + top_t + 0.17),
        mat_index=MAT_INDEX_IRON
    )
    pot_faces += create_cylinder(
        bm, radius=0.02, height=0.03, segments=8,
        location=(-width * 0.24, 0.0, leg_h + body_h + top_t + 0.19),
        mat_index=MAT_INDEX_TIMBER
    )
    faces += pot_faces

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_rug(bm, x, y, z_ground=0.0, ang=0.0, width=2.4, length=3.6, rug_style=1, z_floor=None):
    """Woven carpet with transparent alpha tassels cutout.
    rug_style: 1 = Crimson Ornate, 2 = Sapphire Royal, 3 = Forest Woven.

    The rug art is painted landscape (1024 x 640) with the pattern's long axis
    along texture-U, so the UVs are chosen per-rug: texture-U always follows
    the rug's longer local axis and texture-V the shorter one.
    """
    if z_floor is not None:
        z_ground = z_floor
    from ..materials import MAT_INDEX_RUG_1, MAT_INDEX_RUG_2, MAT_INDEX_RUG_3
    mat_map = {1: MAT_INDEX_RUG_1, 2: MAT_INDEX_RUG_2, 3: MAT_INDEX_RUG_3}
    mat_idx = mat_map.get(rug_style, MAT_INDEX_RUG_1)

    hw = width * 0.5
    hl = length * 0.5
    z = z_ground + 0.008

    uv_layer = bm.loops.layers.uv.verify()
    v1 = bm.verts.new((-hw, -hl, z))
    v2 = bm.verts.new((hw, -hl, z))
    v3 = bm.verts.new((hw, hl, z))
    v4 = bm.verts.new((-hw, hl, z))
    f = bm.faces.new((v1, v2, v3, v4))
    f.material_index = mat_idx

    for loop in f.loops:
        # The rug art is painted portrait (aspect 2:3) with the pattern's long
        # axis and fringe tassels along texture-V (top & bottom short ends) and
        # width along texture-U.
        # Align texture-U to the narrower dimension and texture-V to the longer dimension
        # so tassels always sit on the shorter ends and patterns stay upright.
        if length >= width:
            u = 0.0 if loop.vert.co.x < 0 else 1.0
            v = 0.0 if loop.vert.co.y < 0 else 1.0
        else:
            u = 0.0 if loop.vert.co.y < 0 else 1.0
            v = 0.0 if loop.vert.co.x < 0 else 1.0
        loop[uv_layer].uv = Vector((u, v))
    f.tag = True

    transform_faces([f], Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(ang, 4, 'Z'))
    return [f]


def build_pewter_tankard(bm, x, y, z_ground=0.0, ang=0.0):
    """Authentic pewter tavern mug/tankard with flared base, banded body, hollow interior cavity, and ear handle."""
    faces = []
    r_out, r_in, h, depth = 0.052, 0.044, 0.13, 0.115
    # Hollow main cylinder with physical interior volume and sunken ale liquid level
    # Top rim is completely open (NO solid top cap cylinders!)
    faces += create_hollow_cylinder(
        bm, radius=r_out, inner_radius=r_in, height=h, inner_depth=depth,
        segments=18, location=(0.0, 0.0, h * 0.5),
        mat_index=MAT_INDEX_IRON, inner_mat_index=MAT_INDEX_IRON,
        liquid_height=0.070, liquid_mat_index=MAT_INDEX_TIMBER, smooth=True
    )
    # Flared bottom base foot ring
    faces += create_cone(
        bm, radius1=r_out + 0.008, radius2=r_out, height=0.018, segments=18,
        location=(0.0, 0.0, 0.009), mat_index=MAT_INDEX_IRON
    )
    # Mid-body decorative lathe band (low on the body, never covering the rim)
    faces += create_cylinder(
        bm, radius=r_out + 0.0025, height=0.007, segments=18,
        location=(0.0, 0.0, h * 0.46), mat_index=MAT_INDEX_IRON
    )
    # Cast pewter ear handle on side
    faces += create_torus_ring(
        bm, location=(r_out + 0.024, 0.0, h * 0.52),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        major_radius=0.034, minor_radius=0.0075,
        major_segments=14, minor_segments=8,
        mat_index=MAT_INDEX_IRON
    )
    # Ergonomic thumb-rest tab on top of handle
    faces += create_beveled_box(
        bm, size=(0.016, 0.012, 0.006),
        location=(r_out + 0.016, 0.0, h * 0.52 + 0.036),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.001
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


build_mug = build_pewter_tankard


def build_trencher_plate(bm, x, y, z_ground=0.0, ang=0.0):
    """Turned wooden dining trencher with true recessed concave well, artisan bread roll & creamy cheese wedge."""
    faces = []
    # 1. Real hollow wooden dish with concave interior cavity and resting foot ring (100% turned wood)
    h_plate = 0.024
    depth_well = 0.017
    faces += create_hollow_dish(
        bm, radius_base=0.088, radius_rim=0.130, inner_radius_rim=0.122,
        inner_radius_base=0.076, height=h_plate, inner_depth=depth_well,
        segments=20, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_WOOD, smooth=True
    )
    z_well = h_plate - depth_well
    # 2. Pale creamy cheese wedge sitting in the well
    faces += create_cone(
        bm, radius1=0.036, radius2=0.006, height=0.022, segments=5,
        location=(0.042, -0.020, z_well + 0.011),
        mat_index=MAT_INDEX_WAX
    )
    # 3. A second smaller cheese cube opposite it
    faces += create_beveled_box(
        bm, size=(0.034, 0.028, 0.024),
        location=(-0.030, 0.014, z_well + 0.012),
        rotation=(0.0, 0.0, 0.5),
        mat_index=MAT_INDEX_WAX, bevel_amount=0.003
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces



def build_candlestick(bm, x, y, z_ground=0.0, ang=0.0):
    """Chamber candlestick with saucer drip pan, finger ring, wax candle pillar, wick, and warm flame."""
    faces = []
    # Saucer base plate resting firmly at z=0.0
    faces += create_cylinder(
        bm, radius=0.055, height=0.006, segments=14,
        location=(0.0, 0.0, 0.003), mat_index=MAT_INDEX_IRON
    )
    # Saucer flared rim
    faces += create_cone(
        bm, radius1=0.055, radius2=0.070, height=0.014, segments=14,
        location=(0.0, 0.0, 0.010), mat_index=MAT_INDEX_IRON
    )
    # Central socket cup
    faces += create_cylinder(
        bm, radius=0.022, height=0.026, segments=12,
        location=(0.0, 0.0, 0.020), mat_index=MAT_INDEX_IRON
    )
    # Finger loop handle on saucer edge (fully elevated above table)
    faces += create_torus_ring(
        bm, location=(0.065, 0.0, 0.025),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        major_radius=0.018, minor_radius=0.004,
        major_segments=10, minor_segments=6,
        mat_index=MAT_INDEX_IRON
    )
    # Wax candle column
    faces += create_cylinder(
        bm, radius=0.014, height=0.076, segments=10,
        location=(0.0, 0.0, 0.030 + 0.038),
        mat_index=MAT_INDEX_WAX
    )
    # Dark wick
    faces += create_cylinder(
        bm, radius=0.002, height=0.010, segments=6,
        location=(0.0, 0.0, 0.030 + 0.076 + 0.005),
        mat_index=MAT_INDEX_IRON
    )
    # Glowing teardrop flame
    faces += create_cone(
        bm, radius1=0.007, radius2=0.001, height=0.022, segments=8,
        location=(0.0, 0.0, 0.030 + 0.076 + 0.016),
        mat_index=MAT_INDEX_LANTERN
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_wine_flagon(bm, x, y, z_ground=0.0, ang=0.0):
    """Stoneware tavern flagon with glazed ceramic body, neck, cork stopper & handle."""
    faces = []
    # Base ring at z=0.0
    faces += create_cylinder(
        bm, radius=0.048, height=0.015, segments=14,
        location=(0.0, 0.0, 0.0075), mat_index=MAT_INDEX_TIMBER
    )
    # Bulbous body
    faces += create_cylinder(
        bm, radius=0.052, height=0.12, segments=14,
        location=(0.0, 0.0, 0.015 + 0.06), mat_index=MAT_INDEX_CLAY
    )
    # Shoulder taper
    faces += create_cone(
        bm, radius1=0.052, radius2=0.024, height=0.045, segments=12,
        location=(0.0, 0.0, 0.135 + 0.0225), mat_index=MAT_INDEX_CLAY
    )
    # Slender neck with lip collar
    faces += create_cylinder(
        bm, radius=0.022, height=0.045, segments=10,
        location=(0.0, 0.0, 0.180 + 0.0225), mat_index=MAT_INDEX_CLAY
    )
    faces += create_cylinder(
        bm, radius=0.026, height=0.010, segments=10,
        location=(0.0, 0.0, 0.220), mat_index=MAT_INDEX_CLAY
    )
    # Cork stopper
    faces += create_cylinder(
        bm, radius=0.016, height=0.024, segments=10,
        location=(0.0, 0.0, 0.235), mat_index=MAT_INDEX_WOOD
    )
    # Loop handle
    faces += create_torus_ring(
        bm, location=(-0.038, 0.0, 0.165),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        major_radius=0.022, minor_radius=0.006,
        major_segments=10, minor_segments=6,
        mat_index=MAT_INDEX_CLAY
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_table_scatter(bm, x, y, z_ground=0.0, ang=0.0, clutter_type='AUTO', rng=None, z_table=None):
    """Authentic medieval tavern tabletop clutter: hollow pewter tankard, stoneware jug, wood trencher with bread, chamber candlestick."""
    if z_table is not None:
        z_ground = z_table
    if rng is None:
        rng = random.Random(42)

    faces = []
    # 1. Pewter tankard (hollow interior with ale!)
    faces += build_pewter_tankard(bm, 0.08, 0.05, 0.0, 0.15)
    # 2. Wooden trencher plate with bread & cheese
    faces += build_trencher_plate(bm, -0.10, -0.05, 0.0, -0.20)
    # 3. Stoneware flagon / jug
    faces += build_wine_flagon(bm, -0.06, 0.12, 0.0, 0.40)
    # 4. Chamber candlestick
    faces += build_candlestick(bm, 0.13, -0.09, 0.0, 0.0)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bottle(bm, x, y, z_ground=0.0, ang=0.0, bottle_type='WINE'):
    """Detailed glass wine bottle or apothecary potion flask with cork stopper."""
    faces = []
    is_potion = (bottle_type == 'POTION')
    r_body = 0.046 if is_potion else 0.038
    h_body = 0.11 if is_potion else 0.16

    # Bottom push-up punt
    faces += create_cylinder(bm, radius=r_body, height=0.014, segments=12,
                            location=(0.0, 0.0, 0.007), mat_index=MAT_INDEX_BOTTLE_GLASS)
    # Main bottle body
    faces += create_cylinder(bm, radius=r_body, height=h_body, segments=14,
                            location=(0.0, 0.0, 0.014 + h_body * 0.5), mat_index=MAT_INDEX_BOTTLE_GLASS)
    # Tapered shoulder
    sh_z = 0.014 + h_body
    faces += create_cone(bm, radius1=r_body, radius2=0.015, height=0.045, segments=12,
                         location=(0.0, 0.0, sh_z + 0.0225), mat_index=MAT_INDEX_BOTTLE_GLASS)
    # Slender neck
    neck_z = sh_z + 0.045
    faces += create_cylinder(bm, radius=0.015, height=0.065, segments=10,
                            location=(0.0, 0.0, neck_z + 0.0325), mat_index=MAT_INDEX_BOTTLE_GLASS)
    # Rolled lip collar
    faces += create_cylinder(bm, radius=0.018, height=0.010, segments=10,
                            location=(0.0, 0.0, neck_z + 0.060), mat_index=MAT_INDEX_BOTTLE_GLASS)
    # Cork stopper
    faces += create_cylinder(bm, radius=0.013, height=0.022, segments=10,
                            location=(0.0, 0.0, neck_z + 0.071), mat_index=MAT_INDEX_WOOD)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_bottle_cluster(bm, x, y, z_ground=0.0, ang=0.0):
    """Cluster of 3 varied bottles: wine bottle, round spirits flask, and small apothecary bottle."""
    faces = []
    # 1. Tall green wine bottle
    faces += build_bottle(bm, 0.04, 0.02, 0.0, 0.2, bottle_type='WINE')
    # 2. Squat rounded spirits flask
    faces += build_bottle(bm, -0.05, 0.03, 0.0, -0.5, bottle_type='POTION')
    # 3. Flagon / smaller bottle
    faces += build_bottle(bm, 0.00, -0.05, 0.0, 1.1, bottle_type='WINE')
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_pumpkin(bm, x, y, z_ground=0.0, ang=0.0, radius=0.20):
    """Stylized organic segmented pumpkin with spherical lobes, stem hollow, and twisted stalk."""
    faces = []
    faces += create_organic_pumpkin(
        bm, radius=radius, height=radius * 1.15, num_ribs=8,
        segments_per_rib=6, rings=16,
        location=(0.0, 0.0, 0.0),
        mat_index=MAT_INDEX_PUMPKIN, stem_mat_index=MAT_INDEX_PUMPKIN_STEM
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def _build_leaf(bm, faces, origin, yaw, pitch, length, width,
                roll=0.0, curl=0.35, mat_index=MAT_INDEX_PLANT,
                collect=None):
    """One real 3D leaf blade: a closed, pointed, gently cupped shell with a
    raised centre vein. Built in a local frame (length along +X, width ±Y),
    then yawed/pitched/rolled so it grows outward from ``origin``.

    Pass a ``collect`` list to gather this leaf's faces so the caller can fix
    winding once for the whole plant: ``bmesh.ops.recalc_face_normals`` tags
    EVERY face in the bmesh (not just the ones passed in), which would exempt
    all previously built geometry from the final world-space UV pass. Use
    :func:`mesh_utils.recalc_face_normals_safe` on the collected faces.
    """
    tr = (Matrix.Translation(Vector(origin))
          @ Matrix.Rotation(yaw, 4, 'Z')
          @ Matrix.Rotation(-pitch, 4, 'Y')
          @ Matrix.Rotation(roll, 4, 'X'))
    uv_layer = bm.loops.layers.uv.verify()
    local = {}
    leaf_faces = []

    def V(x, y, z):
        v = bm.verts.new(tr @ Vector((x, y, z)))
        local[v] = (x, y, z)
        return v

    def face(verts):
        f = bm.faces.new(verts)
        f.material_index = mat_index
        f.tag = True
        f.smooth = True
        for lp in f.loops:
            lx, ly, _lz = local[lp.vert]
            lp[uv_layer].uv = Vector((lx * 3.2, ly * 3.2))
        leaf_faces.append(f)

    n = 4
    th = max(0.0016, width * 0.05)
    base = V(0.0, 0.0, 0.0)
    tip = V(length, 0.0, length * 0.12)
    secs = []
    for i in range(1, n):
        t = i / n
        hw = width * (math.sin(math.pi * t) ** 0.7)
        lift = length * 0.18 * math.sin(math.pi * t)
        cup = curl * hw
        secs.append([
            V(t * length, hw, lift - cup),
            V(t * length, 0.0, lift + th),
            V(t * length, -hw, lift - cup),
            V(t * length, 0.0, lift - th),
        ])
    for k in range(4):
        face([base, secs[0][k], secs[0][(k + 1) % 4]])
    for i in range(len(secs) - 1):
        a, b = secs[i], secs[i + 1]
        for k in range(4):
            face([a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]])
    last = secs[-1]
    for k in range(4):
        face([last[k], last[(k + 1) % 4], tip])
    try:
        recalc_face_normals_safe(bm, leaf_faces)
    except Exception:
        pass
    for f in leaf_faces:
        f.tag = True
    faces.extend(leaf_faces)


def _leaf_fan(bm, faces, z, base_r, count, length, width, pitch_lo, pitch_hi,
              phase=0.0, curl=0.30, seed=0.0, mat_index=MAT_INDEX_PLANT):
    """A slightly irregular ring of real leaves growing up and outward.

    Each blade gets its own yaw jitter, pitch, size and curl so the plant reads
    organic instead of a perfect radial star.
    """
    for i in range(count):
        h1 = math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453
        r1 = h1 - math.floor(h1)
        h2 = math.sin((i + 1) * 39.3467 + seed * 11.135) * 24634.6345
        r2 = h2 - math.floor(h2)
        a = phase + i * (2.0 * math.pi / count) + (r1 - 0.5) * 0.40
        ca, sa = math.cos(a), math.sin(a)
        pitch = pitch_lo + (pitch_hi - pitch_lo) * ((i * 0.6180339 + r1 * 0.3) % 1.0)
        br = base_r * (0.75 + 0.55 * r2)
        lscale = 0.80 + 0.45 * r1
        wscale = 0.85 + 0.30 * r2
        _build_leaf(bm, faces,
                    (ca * br, sa * br, z + (r2 - 0.5) * 0.014), a, pitch,
                    length * lscale, width * wscale,
                    roll=0.28 * math.sin(a * 3.0) + (r1 - 0.5) * 0.25,
                    curl=curl * (0.8 + 0.4 * r2), mat_index=mat_index)


def build_potted_plant_small(bm, x, y, z_ground=0.0, ang=0.0):
    """Tabletop terracotta planter: a real hollow pot with soil inside and a
    bushy cluster of true 3D leaves (no flat leaf cards)."""
    faces = []
    h_pot = 0.13
    inner_depth = 0.075
    # Hollow planter (outer wall, rim lip, inner wall, inner floor).
    faces += create_hollow_dish(
        bm, radius_base=0.045, radius_rim=0.086, inner_radius_rim=0.072,
        inner_radius_base=0.036, height=h_pot, inner_depth=inner_depth,
        segments=16, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_CLAY, smooth=True
    )
    floor_z = h_pot - inner_depth
    # Soil fill inside the hollow cavity.
    faces += create_cylinder(
        bm, radius=0.037, height=0.014, segments=14,
        location=(0.0, 0.0, floor_z + 0.005), mat_index=MAT_INDEX_DIRT
    )
    soil_z = floor_z + 0.012

    # Short central stem, then rings of leaves starting at the rim height so
    # the blades never clip through the pot wall.
    stem_top = h_pot + 0.03
    faces += create_cylinder(bm, radius=0.007, height=max(0.02, stem_top - soil_z),
                             segments=6, location=(0.0, 0.0, (soil_z + stem_top) * 0.5),
                             mat_index=MAT_INDEX_TIMBER)
    _leaf_fan(bm, faces, h_pot - 0.010, 0.020, 6, 0.090, 0.030, 0.28, 0.58,
              phase=0.20, curl=0.26, seed=1.0)
    _leaf_fan(bm, faces, h_pot + 0.012, 0.013, 5, 0.072, 0.026, 0.60, 0.95,
              phase=0.80, curl=0.26, seed=2.0)
    _leaf_fan(bm, faces, h_pot + 0.030, 0.008, 4, 0.055, 0.020, 0.95, 1.25,
              phase=1.40, curl=0.24, seed=3.0)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces



def build_potted_plant_large(bm, x, y, z_ground=0.0, ang=0.0):
    """Large ornamental floor planter: a hollow stone-footed urn filled with
    soil, growing a small indoor tree with real 3D leaves."""
    faces = []
    # Stone foot plinth.
    faces += create_cylinder(bm, radius=0.19, height=0.05, segments=16,
                             location=(0.0, 0.0, 0.025), mat_index=MAT_INDEX_CUT_STONE)
    # Hollow clay urn (outer wall + rim lip + inner wall + inner floor).
    urn_h = 0.46
    inner_depth = 0.10
    faces += create_hollow_dish(
        bm, radius_base=0.16, radius_rim=0.235, inner_radius_rim=0.20,
        inner_radius_base=0.135, height=urn_h, inner_depth=inner_depth,
        segments=18, location=(0.0, 0.0, 0.05), mat_index=MAT_INDEX_CLAY, smooth=True
    )
    floor_z = 0.05 + urn_h - inner_depth          # cavity floor (world z)
    # Soil fill inside the cavity, mounded a touch above the cavity floor.
    faces += create_cylinder(bm, radius=0.137, height=0.02, segments=16,
                             location=(0.0, 0.0, floor_z + 0.008), mat_index=MAT_INDEX_DIRT)
    soil_z = floor_z + 0.016

    # Central woody trunk.
    trunk_h = 0.62
    faces += create_cylinder(bm, radius=0.034, height=trunk_h, segments=10,
                             location=(0.0, 0.0, soil_z + trunk_h * 0.5),
                             mat_index=MAT_INDEX_TIMBER)

    # Three tiers of real leaves fanning out from the trunk, plus a crown.
    _leaf_fan(bm, faces, soil_z + 0.18, 0.028, 6, 0.30, 0.075, 0.42, 0.72, phase=0.1, curl=0.22, seed=4.0)
    _leaf_fan(bm, faces, soil_z + 0.36, 0.024, 6, 0.25, 0.062, 0.55, 0.85, phase=0.6, curl=0.22, seed=5.0)
    _leaf_fan(bm, faces, soil_z + 0.52, 0.020, 5, 0.19, 0.050, 0.70, 1.00, phase=1.1, curl=0.22, seed=6.0)
    _leaf_fan(bm, faces, soil_z + 0.60, 0.012, 4, 0.13, 0.038, 1.00, 1.30, phase=1.7, curl=0.22, seed=7.0)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_potted_herb(bm, x, y, z_ground=0.0, ang=0.0):
    """Kitchen herb/salad bowl: a shallow terracotta dish mounded full of fresh
    greens. No loose chopped-leaf cards — the fill itself uses the plant
    material so the bowl simply reads as a bowl of herbs."""
    faces = []
    # Shallow terracotta herb bowl with a true hollow interior (open top).
    h_bowl = 0.065
    depth_bowl = 0.048
    faces += create_hollow_dish(
        bm, radius_base=0.065, radius_rim=0.118, inner_radius_rim=0.108,
        inner_radius_base=0.055, height=h_bowl, inner_depth=depth_bowl,
        segments=18, location=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_CLAY, smooth=True
    )
    # Simple flat "salad" disc, sitting a little below the rim and well inside
    # the inner wall so it never pokes out of the bowl.
    z_fill = h_bowl - 0.014
    r_fill = 0.088
    seg = 18
    ring = [bm.verts.new((math.cos(2.0 * math.pi * i / seg) * r_fill,
                          math.sin(2.0 * math.pi * i / seg) * r_fill,
                          z_fill)) for i in range(seg)]
    f_fill = bm.faces.new(ring)
    f_fill.material_index = MAT_INDEX_PLANT
    f_fill.tag = True
    faces.append(f_fill)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_folded_cloth(bm, x, y, z_ground=0.0, ang=0.0):
    """Stack of neatly folded linens, blankets and kitchen towels."""
    faces = []
    # Layer 1: Base folded blue checkered linen towel
    faces += create_beveled_box(
        bm, size=(0.28, 0.22, 0.024),
        location=(0.0, 0.0, 0.012),
        mat_index=MAT_INDEX_CLOTH_LINEN, bevel_amount=0.004
    )
    # Layer 2: White stitched linen fold (slightly rotated)
    faces += create_beveled_box(
        bm, size=(0.26, 0.21, 0.024),
        location=(0.005, 0.002, 0.024 + 0.012),
        rotation=(0.0, 0.0, 0.06),
        mat_index=MAT_INDEX_FABRIC_WHITE, bevel_amount=0.004
    )
    # Layer 3: Warm red fabric fold
    faces += create_beveled_box(
        bm, size=(0.27, 0.20, 0.024),
        location=(-0.004, -0.003, 0.048 + 0.012),
        rotation=(0.0, 0.0, -0.05),
        mat_index=MAT_INDEX_FABRIC_RED, bevel_amount=0.004
    )
    # Layer 4: Top folded stitched cloth
    faces += create_beveled_box(
        bm, size=(0.25, 0.19, 0.022),
        location=(0.002, 0.003, 0.072 + 0.011),
        rotation=(0.0, 0.0, 0.03),
        mat_index=MAT_INDEX_FABRIC_STITCHED, bevel_amount=0.004
    )
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_foodprep_clutter(bm, x, y, z_ground=0.0, ang=0.0):
    """Foodprep cluster for kitchen counters: butcher block chopping board, realistic chef knife, bread, cheese, hollow clay bowl."""
    faces = []
    # 1. Thick solid wooden butcher block / cutting board
    board_t = 0.036
    faces += create_beveled_box(
        bm, size=(0.38, 0.26, board_t),
        location=(0.0, 0.0, board_t * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
    )

    # 2. Authentic kitchen chef's knife resting on the cutting board
    # Blade: forged steel, curved belly, sharp point at tip
    blade_len = 0.15
    blade_h = 0.032
    blade_t = 0.003
    knife_yaw = 0.24
    kx, ky = -0.03, 0.05
    # Steel blade with tapered cutting edge
    faces += create_beveled_box(
        bm, size=(blade_len, blade_h, blade_t),
        location=(kx, ky, board_t + blade_t * 0.5),
        rotation=(0.0, 0.0, knife_yaw),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.001
    )
    # Polished brass bolster collar
    cos_ky, sin_ky = math.cos(knife_yaw), math.sin(knife_yaw)
    bolster_x = kx - (blade_len * 0.5 + 0.005) * cos_ky
    bolster_y = ky - (blade_len * 0.5 + 0.005) * sin_ky
    faces += create_beveled_box(
        bm, size=(0.010, 0.020, 0.012),
        location=(bolster_x, bolster_y, board_t + 0.006),
        rotation=(0.0, 0.0, knife_yaw),
        mat_index=MAT_INDEX_WAX, bevel_amount=0.001
    )
    # Ergonomic wooden handle scales
    handle_len = 0.095
    handle_x = bolster_x - (handle_len * 0.5 + 0.005) * cos_ky
    handle_y = bolster_y - (handle_len * 0.5 + 0.005) * sin_ky
    faces += create_beveled_box(
        bm, size=(handle_len, 0.018, 0.014),
        location=(handle_x, handle_y, board_t + 0.007),
        rotation=(0.0, 0.0, knife_yaw),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.003
    )

    # 3. Creamy cheese wedge resting on the board
    faces += create_cone(
        bm, radius1=0.040, radius2=0.006, height=0.026, segments=5,
        location=(0.085, -0.025, board_t + 0.013), mat_index=MAT_INDEX_WAX
    )

    # 4. Hollow ceramic ingredient / salt bowl with wooden spoon (100% clay)
    bowl_h = 0.034
    bowl_depth = 0.026
    bowl_x, bowl_y = -0.08, -0.06
    faces += create_hollow_dish(
        bm, radius_base=0.034, radius_rim=0.058, inner_radius_rim=0.050,
        inner_radius_base=0.028, height=bowl_h, inner_depth=bowl_depth,
        segments=16, location=(bowl_x, bowl_y, board_t), mat_index=MAT_INDEX_CLAY, smooth=True
    )
    # Wooden tasting spoon resting on the rim dipping into the cavity
    faces += create_beveled_box(
        bm, size=(0.065, 0.010, 0.005),
        location=(bowl_x + 0.018, bowl_y + 0.018, board_t + 0.022),
        rotation=(0.32, -0.28, 0.75),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.001
    )

    # 5. Folded blue/cream checkered linen kitchen towel draped on board edge
    faces += create_beveled_box(
        bm, size=(0.12, 0.16, 0.016),
        location=(0.06, 0.07, board_t + 0.008),
        rotation=(0.0, 0.0, -0.15),
        mat_index=MAT_INDEX_CLOTH_LINEN, bevel_amount=0.003
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_sofa(bm, x, y, z_ground=0.0, ang=0.0, length=1.92, depth=0.84,
               fabric_mat=MAT_INDEX_LEATHER):
    """Luxurious 3-cushion salon sofa / settee with damask upholstery,
    turned wooden feet, twin deep plush cushions, rolled arms, and throw pillows."""
    faces = []
    deck_h = 0.34
    foot_h = 0.080
    foot_r = 0.042
    foot_inset_x = length * 0.5 - 0.10
    foot_inset_y = depth * 0.5 - 0.09

    # 1. Six elegant turned timber bun feet tucked directly under chassis corners & center
    for lx in (-foot_inset_x, 0.0, foot_inset_x):
        for ly in (-foot_inset_y, foot_inset_y):
            faces += create_cylinder(
                bm, radius=foot_r, height=foot_h, segments=12,
                location=(lx, ly, foot_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, smooth=True
            )
            faces += create_cylinder(
                bm, radius=foot_r + 0.005, height=0.010, segments=12,
                location=(lx, ly, foot_h - 0.005),
                mat_index=MAT_INDEX_WOOD, smooth=True
            )

    # 2. Main upholstered base apron (solid chassis wrapping around the bottom)
    apron_h = deck_h - foot_h
    faces += create_beveled_box(
        bm, size=(length - 0.04, depth - 0.04, apron_h),
        location=(0.0, 0.0, foot_h + apron_h * 0.5),
        mat_index=fabric_mat, bevel_amount=0.028
    )

    # 3. Two wide, plush seat cushions
    cushion_thick = 0.14
    cushion_w = (length - 0.30) * 0.5 - 0.015
    cushion_d = depth - 0.16
    for cx in (-cushion_w * 0.5 - 0.01, cushion_w * 0.5 + 0.01):
        faces += create_beveled_box(
            bm, size=(cushion_w, cushion_d, cushion_thick),
            location=(cx, -0.02, deck_h + cushion_thick * 0.5),
            mat_index=fabric_mat, bevel_amount=0.032
        )

    # 4. Left and right rolled scroll armrests
    arm_w = 0.14
    arm_h = 0.25
    arm_cz = deck_h + arm_h * 0.5
    for sgn in (-1.0, 1.0):
        ax = sgn * (length * 0.5 - arm_w * 0.5 - 0.02)
        faces += create_beveled_box(
            bm, size=(arm_w, depth - 0.06, arm_h),
            location=(ax, -0.01, arm_cz),
            mat_index=fabric_mat, bevel_amount=0.025
        )
        faces += create_cylinder(
            bm, radius=arm_w * 0.52, height=depth - 0.05, segments=14,
            location=(ax, -0.01, deck_h + arm_h),
            rotation=(math.pi * 0.5, 0.0, 0.0),
            mat_index=fabric_mat, smooth=True
        )

    # 5. High upholstered backrest with rolled top crest
    back_h = 0.98
    back_span = back_h - deck_h
    back_y = depth * 0.5 - 0.10
    faces += create_beveled_box(
        bm, size=(length - 0.16, 0.15, back_span),
        location=(0.0, back_y, deck_h + back_span * 0.5),
        rotation=(-0.07, 0.0, 0.0),
        mat_index=fabric_mat, bevel_amount=0.030
    )
    faces += create_cylinder(
        bm, radius=0.075, height=length - 0.14, segments=14,
        location=(0.0, back_y + 0.02, back_h),
        rotation=(0.0, math.pi * 0.5, 0.0),
        mat_index=fabric_mat, smooth=True
    )

    # 6. Two plush throw pillows at either arm, leaning back naturally.
    for sgn, p_mat in [(-1.0, MAT_INDEX_FABRIC_RED), (1.0, MAT_INDEX_CLOTH_LINEN)]:
        px = sgn * (length * 0.5 - 0.25)
        faces += create_beveled_box(
            bm, size=(0.28, 0.10, 0.26),
            location=(px, back_y - 0.20, deck_h + cushion_thick + 0.11),
            rotation=(-0.26, 0.0, sgn * 0.10),
            mat_index=p_mat, bevel_amount=0.024
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_armchair(bm, x, y, z_ground=0.0, ang=0.0, width=0.86, depth=0.82,
                   fabric_mat=MAT_INDEX_LEATHER):
    """High-end fireside lounge armchair with continuous damask upholstery,
    turned wooden bun feet, deep plush seat cushion, rolled scroll armrests,
    enveloping winged backrest with rolled crest, and cozy throw pillow."""
    faces = []
    deck_h = 0.34
    foot_h = 0.080
    foot_r = 0.042
    foot_inset_x = width * 0.5 - 0.08
    foot_inset_y = depth * 0.5 - 0.09

    # 1. Four elegant turned timber bun feet tucked directly under corners
    for lx in (-foot_inset_x, foot_inset_x):
        for ly in (-foot_inset_y, foot_inset_y):
            faces += create_cylinder(
                bm, radius=foot_r, height=foot_h, segments=12,
                location=(lx, ly, foot_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, smooth=True
            )
            faces += create_cylinder(
                bm, radius=foot_r + 0.005, height=0.010, segments=12,
                location=(lx, ly, foot_h - 0.005),
                mat_index=MAT_INDEX_WOOD, smooth=True
            )

    # 2. Main upholstered base apron (solid chassis wrapping around the bottom)
    apron_h = deck_h - foot_h
    faces += create_beveled_box(
        bm, size=(width - 0.04, depth - 0.04, apron_h),
        location=(0.0, 0.0, foot_h + apron_h * 0.5),
        mat_index=fabric_mat, bevel_amount=0.028
    )

    # 3. Deep plush upholstered seat cushion
    cushion_thick = 0.14
    cushion_w = width - 0.24
    cushion_d = depth - 0.16
    faces += create_beveled_box(
        bm, size=(cushion_w, cushion_d, cushion_thick),
        location=(0.0, -0.02, deck_h + cushion_thick * 0.5),
        mat_index=fabric_mat, bevel_amount=0.032
    )

    # 4. Left and right rolled scroll armrests
    arm_w = 0.13
    arm_h = 0.25
    arm_cz = deck_h + arm_h * 0.5
    for sgn in (-1.0, 1.0):
        ax = sgn * (width * 0.5 - arm_w * 0.5 - 0.02)
        faces += create_beveled_box(
            bm, size=(arm_w, depth - 0.06, arm_h),
            location=(ax, -0.01, arm_cz),
            mat_index=fabric_mat, bevel_amount=0.025
        )
        faces += create_cylinder(
            bm, radius=arm_w * 0.52, height=depth - 0.05, segments=14,
            location=(ax, -0.01, deck_h + arm_h),
            rotation=(math.pi * 0.5, 0.0, 0.0),
            mat_index=fabric_mat, smooth=True
        )

    # 5. High enveloping winged backrest with rolled top crest
    back_h = 0.98
    back_span = back_h - deck_h
    back_y = depth * 0.5 - 0.10
    faces += create_beveled_box(
        bm, size=(width - 0.12, 0.15, back_span),
        location=(0.0, back_y, deck_h + back_span * 0.5),
        rotation=(-0.07, 0.0, 0.0),
        mat_index=fabric_mat, bevel_amount=0.030
    )
    faces += create_cylinder(
        bm, radius=0.075, height=width - 0.10, segments=14,
        location=(0.0, back_y + 0.02, back_h),
        rotation=(0.0, math.pi * 0.5, 0.0),
        mat_index=fabric_mat, smooth=True
    )
    # Wingback side flares
    for sgn in (-1.0, 1.0):
        wx = sgn * (width * 0.5 - 0.07)
        faces += create_beveled_box(
            bm, size=(0.09, 0.17, back_span * 0.65),
            location=(wx, back_y - 0.08, deck_h + back_span * 0.58),
            rotation=(-0.07, sgn * 0.12, sgn * 0.14),
            mat_index=fabric_mat, bevel_amount=0.022
        )

    # 6. Plush accent throw pillow leaning back in the corner
    faces += create_beveled_box(
        bm, size=(0.28, 0.10, 0.26),
        location=(width * 0.14, back_y - 0.20, deck_h + cushion_thick + 0.11),
        rotation=(-0.26, 0.0, 0.12),
        mat_index=MAT_INDEX_CLOTH_LINEN, bevel_amount=0.024
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


build_sofa_chair = build_armchair


def build_chair(bm, x: float = 0.0, y: float = 0.0, z_ground: float = 0.0,
                ang: float = 0.0, seat_h: float = 0.48, width: float = 0.46,
                depth: float = 0.44, back_h: float = 0.92):
    """Stylized medieval tavern / dining chair with chamfered timber legs,
    lower stretchers, comfortable contoured seat, and curved ladderback rails."""
    faces = []
    leg_thick = 0.045
    leg_inset_x = width * 0.5 - 0.035
    leg_inset_y = depth * 0.5 - 0.035

    # 1. Front legs (from floor to underside of seat)
    for lx in (-leg_inset_x, leg_inset_x):
        faces += create_beveled_box(
            bm, size=(leg_thick, leg_thick, seat_h),
            location=(lx, -leg_inset_y, seat_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )

    # 2. Rear legs & upright back stiles (continuous from floor all the way up to back_h)
    for lx in (-leg_inset_x, leg_inset_x):
        faces += create_beveled_box(
            bm, size=(leg_thick, leg_thick, back_h),
            location=(lx, leg_inset_y, back_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )
        # Decorative finial / chamfer cap atop each back stile
        faces += create_beveled_box(
            bm, size=(leg_thick + 0.012, leg_thick + 0.012, 0.035),
            location=(lx, leg_inset_y, back_h + 0.018),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
        )

    # 3. Lower perimeter stretchers (bracing all four sides)
    str_h = 0.16
    str_thick = 0.024
    # Side stretchers
    faces += create_beveled_box(
        bm, size=(str_thick, depth - 0.07, 0.035),
        location=(-leg_inset_x, 0.0, str_h),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
    )
    faces += create_beveled_box(
        bm, size=(str_thick, depth - 0.07, 0.035),
        location=(leg_inset_x, 0.0, str_h),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
    )
    # Front and rear cross stretchers (staggered slightly in height)
    faces += create_beveled_box(
        bm, size=(width - 0.07, str_thick, 0.035),
        location=(0.0, -leg_inset_y, str_h - 0.03),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
    )
    faces += create_beveled_box(
        bm, size=(width - 0.07, str_thick, 0.035),
        location=(0.0, leg_inset_y, str_h + 0.03),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
    )

    # 4. Seat plank (beveled solid timber slab with apron)
    seat_thick = 0.035
    faces += create_beveled_box(
        bm, size=(width, depth, seat_thick),
        location=(0.0, 0.0, seat_h + seat_thick * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )

    # 5. Padded cloth cushion with tie-downs
    cushion_thick = 0.025
    faces += create_beveled_box(
        bm, size=(width - 0.06, depth - 0.06, cushion_thick),
        location=(0.0, 0.0, seat_h + seat_thick + cushion_thick * 0.5),
        mat_index=MAT_INDEX_CLOTH_LINEN, bevel_amount=0.007
    )

    # 6. Curved ladderback backrest (top crest rail + middle splats)
    splat_w = width - 0.04
    # Top arched crest rail
    faces += create_beveled_box(
        bm, size=(splat_w, 0.026, 0.08),
        location=(0.0, leg_inset_y, back_h - 0.05),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.006
    )
    # Mid-back lumbar rail
    faces += create_beveled_box(
        bm, size=(splat_w, 0.022, 0.05),
        location=(0.0, leg_inset_y, seat_h + 0.18),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
    )
    # Lower lumbar rail
    faces += create_beveled_box(
        bm, size=(splat_w, 0.020, 0.04),
        location=(0.0, leg_inset_y, seat_h + 0.08),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.004
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_stone_pile(bm, x, y, z_ground=0.0, ang=0.0, length=1.8, width=0.95, layers=4):
    """Stacked, roughly squared cut-stone blocks (quarry / stone store)."""
    faces = []
    rng = random.Random(int(abs(x) * 2654435761) ^ int(abs(y) * 40503))
    block_h = 0.17
    for k in range(layers):
        n = max(1, layers - k)
        row_w = width / n
        for j in range(n):
            L = length * (0.78 + 0.30 * rng.random())
            cy = (j - (n - 1) * 0.5) * row_w * 1.06
            faces += create_beveled_box(
                bm, size=(L, row_w * 1.02, block_h),
                location=(0.0, cy, block_h * 0.5 + k * (block_h + 0.006)),
                rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.18),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_log_pile(bm, x, y, z_ground=0.0, ang=0.0, length=2.10, radius=0.17, rows=3):
    """Pyramid of stacked round logs (bulk timber, warehouse / lumbermill)."""
    faces = []
    rng = random.Random(int(abs(x) * 73856093) ^ int(abs(y) * 19349663))
    for row in range(rows):
        count = max(2, rows + 2 - row)
        for i in range(count):
            L = length * (0.84 + 0.32 * rng.random())
            rr = radius * (0.90 + 0.14 * rng.random())
            cz = rr + row * (radius * 1.62)
            cy = (i - (count - 1) * 0.5) * (radius * 2.06)
            faces += create_cylinder(
                bm, radius=rr, height=L, segments=10,
                location=(0.0, cy, cz), rotation=(0.0, math.pi * 0.5, 0.0),
                mat_index=MAT_INDEX_LOG)
            for s in (-1.0, 1.0):
                faces += create_cylinder(
                    bm, radius=rr * 0.98, height=0.012, segments=10,
                    location=(s * (L * 0.5 - 0.006), cy, cz),
                    rotation=(0.0, math.pi * 0.5, 0.0),
                    mat_index=MAT_INDEX_LOG_END)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


def build_plank_pile(bm, x, y, z_ground=0.0, ang=0.0, length=2.0, width=0.28, layers=6):
    """Neatly stacked sawn planks (bulk timber, warehouse / lumbermill)."""
    faces = []
    rng = random.Random(int(abs(x) * 83492791) ^ int(abs(y) * 19349663))
    for k in range(layers):
        for j in range(2):
            L = length * (0.86 + 0.28 * rng.random())
            off = (j - 0.5) * width * 1.06 + (rng.random() - 0.5) * 0.03
            faces += create_beveled_box(
                bm, size=(L, width, 0.055),
                location=(0.0, off, 0.03 + k * 0.058),
                rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.05),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.004)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces
