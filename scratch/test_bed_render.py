import sys, os, math
import bpy
import bmesh
from mathutils import Vector, Matrix

repo_root = r'd:\BlendBuildingCreator'
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

from blend_building_creator.generator.materials import (
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER, MAT_INDEX_FABRIC_WHITE,
    MAT_INDEX_FABRIC_RED, MAT_INDEX_FABRIC_STITCHED,
    setup_building_material_slots, prune_material_slots_for_bmesh
)
from blend_building_creator.generator.mesh_utils import (
    create_beveled_box, apply_box_uvs, apply_organic_shading
)

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
                # Local u, v mapping based on physical dimensions
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


def generate_test_bed(bm, length=2.0, width=1.2):
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
        faces += create_beveled_box(bm, size=(rail_len, 0.06, 0.16),
                                    location=(rail_cx, sy, frame_h),
                                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

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

    return faces

mesh = bpy.data.meshes.new('test_bed_mesh')
obj = bpy.data.objects.new('test_bed', mesh)
bpy.context.scene.collection.objects.link(obj)

bm = bmesh.new()
generate_test_bed(bm)
apply_box_uvs(bm, scale=1.0)
props = bpy.context.scene.fantasy_building_settings
setup_building_material_slots(obj, props)
prune_material_slots_for_bmesh(obj, bm)
bm.to_mesh(obj.data)
bm.free()
obj.data.update()
apply_organic_shading(obj)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (-1.8, -2.5, 1.7)
target = Vector((0.0, 0.0, 0.45))
direction = target - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 4.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(52), math.radians(24), math.radians(38))

fill_data = bpy.data.lights.new("Fill", type='POINT')
fill_data.energy = 220.0
fill_obj = bpy.data.objects.new("Fill", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.location = (1.6, -1.2, 1.9)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640
out_path = os.path.join(repo_root, "scratch", "bed_render_unwrap_test.png")
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("Rendered to:", out_path)
