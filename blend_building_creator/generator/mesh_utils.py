"""
Geometry and bmesh helper utilities for procedural stylized building generation.
Provides robust primitives, deformations, and UV generation for Blender 5.2.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler
import random

def apply_organic_shading(obj, angle_deg=42.0):
    """
    Smooths the finished building mesh by angle so bevels/cylinders read as soft and
    rounded (organic hand-carved look) while sharp unbeveled corners stay crisp.
    Uses the Blender 4.1+ 'Smooth by Angle' operator, with a flat shade_smooth fallback.
    """
    try:
        prev_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        was_selected = obj.select_get()
        obj.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
        obj.select_set(was_selected)
        bpy.context.view_layer.objects.active = prev_active
    except Exception:
        try:
            for poly in obj.data.polygons:
                poly.use_smooth = True
        except Exception:
            pass

def create_box(bm, size=(1.0, 1.0, 1.0), location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0, is_wall=False, u_offset=0.0, v_offset=0.0):
    """
    Creates an oriented box in bmesh with center or base alignment.
    Returns list of faces.
    """
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    
    verts = [
        Vector((-sx, -sy, -sz)),
        Vector(( sx, -sy, -sz)),
        Vector(( sx,  sy, -sz)),
        Vector((-sx,  sy, -sz)),
        Vector((-sx, -sy,  sz)),
        Vector(( sx, -sy,  sz)),
        Vector(( sx,  sy,  sz)),
        Vector((-sx,  sy,  sz)),
    ]
    
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    
    bm_verts = [bm.verts.new(tr_mat @ v) for v in verts]
    
    face_indices = [
        (0, 1, 2, 3), # Bottom (-Z)
        (4, 7, 6, 5), # Top (+Z)
        (0, 4, 5, 1), # Front (-Y)
        (1, 5, 6, 2), # Right (+X)
        (2, 6, 7, 3), # Back (+Y)
        (3, 7, 4, 0), # Left (-X)
    ]
    
    uv_layer = bm.loops.layers.uv.verify()
    dx, dy, dz = size
    scale = 1.0

    faces = []
    for f_idx, idxs in enumerate(face_indices):
        f = bm.faces.new([bm_verts[i] for i in idxs])
        f.material_index = mat_index
        faces.append(f)
        
        if is_wall:
            # Consistent length & height wall unwrapping for planks & stone:
            # U is ALWAYS along wall length (X, horizontal), offset by u_offset
            # V is ALWAYS along wall height (Z, vertical), offset by v_offset
            su = 0.55
            sv = 0.55
            u0 = u_offset * su
            u1 = (u_offset + dx) * su
            v0 = v_offset * sv
            v1 = (v_offset + dz) * sv
            if f_idx == 2: # Front (-Y, exterior)
                f.loops[0][uv_layer].uv = Vector((u0, v0))
                f.loops[1][uv_layer].uv = Vector((u0, v1))
                f.loops[2][uv_layer].uv = Vector((u1, v1))
                f.loops[3][uv_layer].uv = Vector((u1, v0))
            elif f_idx == 4: # Back (+Y, interior)
                f.loops[0][uv_layer].uv = Vector((u1, v0))
                f.loops[1][uv_layer].uv = Vector((u1, v1))
                f.loops[2][uv_layer].uv = Vector((u0, v1))
                f.loops[3][uv_layer].uv = Vector((u0, v0))
            elif f_idx in (3, 5): # End jambs (+X, -X)
                f.loops[0][uv_layer].uv = Vector((0.0, v0))
                f.loops[1][uv_layer].uv = Vector((0.0, v1))
                f.loops[2][uv_layer].uv = Vector((dy * su, v1))
                f.loops[3][uv_layer].uv = Vector((dy * su, v0))
            else: # Top (1) and Bottom (0)
                f.loops[0][uv_layer].uv = Vector((u0, 0.0))
                f.loops[1][uv_layer].uv = Vector((u1, 0.0))
                f.loops[2][uv_layer].uv = Vector((u1, dy * sv))
                f.loops[3][uv_layer].uv = Vector((u0, dy * sv))
        elif dz >= dx and dz >= dy:
            # Vertical post / column: V along longitudinal Z axis, U around circumference
            for loop_idx, v_idx in enumerate(idxs):
                lv = verts[v_idx]
                if f_idx in (0, 1): # End caps (-Z, +Z)
                    u = (lv.x + sx) * scale
                    v = (lv.y + sy) * scale
                elif f_idx in (2, 4): # Front (-Y), Back (+Y)
                    u = (lv.x + sx) * scale
                    v = (lv.z + sz) * scale
                else: # Right (+X), Left (-X)
                    u = (lv.y + sy) * scale
                    v = (lv.z + sz) * scale
                f.loops[loop_idx][uv_layer].uv = Vector((u, v))
        elif dx >= dy and dx >= dz:
            # Horizontal beam along X: V along longitudinal X axis, U around circumference
            su = scale * 1.2
            sv = scale * 0.40
            for loop_idx, v_idx in enumerate(idxs):
                lv = verts[v_idx]
                if f_idx in (3, 5): # End caps (+X, -X)
                    u = (lv.y + sy) * su
                    v = (lv.z + sz) * su
                elif f_idx in (0, 1): # Bottom (-Z), Top (+Z)
                    u = (lv.y + sy) * su
                    v = (lv.x + sx) * sv
                else: # Front (-Y), Back (+Y)
                    u = (lv.z + sz) * su
                    v = (lv.x + sx) * sv
                f.loops[loop_idx][uv_layer].uv = Vector((u, v))
        else:
            # Horizontal beam along Y: V along longitudinal Y axis, U around circumference
            su = scale * 1.2
            sv = scale * 0.40
            for loop_idx, v_idx in enumerate(idxs):
                lv = verts[v_idx]
                if f_idx in (2, 4): # End caps (-Y, +Y)
                    u = (lv.x + sx) * su
                    v = (lv.z + sz) * su
                elif f_idx in (0, 1): # Bottom (-Z), Top (+Z)
                    u = (lv.x + sx) * su
                    v = (lv.y + sy) * sv
                else: # Right (+X), Left (-X)
                    u = (lv.z + sz) * su
                    v = (lv.y + sy) * sv
                f.loops[loop_idx][uv_layer].uv = Vector((u, v))
        
    return faces

def create_beveled_box(bm, size=(1.0, 1.0, 1.0), location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0, bevel_amount=0.03, bevel_segments=2, is_wall=False, u_offset=0.0, v_offset=0.0):
    """Creates a box and softly rounds its edges for a chunky, hand-carved organic look."""
    faces = create_box(bm, size, location, rotation, mat_index, is_wall=is_wall, u_offset=u_offset, v_offset=v_offset)
    if bevel_amount > 0.001:
        edges = list({e for f in faces for e in f.edges})
        try:
            res = bmesh.ops.bevel(bm, geom=edges, offset=bevel_amount, segments=bevel_segments, profile=0.7, affect='EDGES')
            for f in res.get('faces', []):
                if f.is_valid:
                    f.material_index = mat_index
            faces = [f for f in faces if f.is_valid] + [f for f in res.get('faces', []) if f.is_valid]
        except Exception:
            pass
    return [f for f in faces if f.is_valid]

def create_flared_post(bm, size=(0.28, 0.28, 3.0), location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
                       mat_index=3, flare=0.25, jankiness=0.0, chamfer_top=False):
    """
    Creates a chunky stylized fantasy vertical timber post flared out at the top and bottom,
    with subtle organic jankiness and oriented vertical UV coordinates for handpainted timber grain.
    When chamfer_top is True (e.g. top floor under roof eave), the top is chamfered inward/downward.
    """
    dx, dy, dz = size
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat

    taper_len = min(dz * 0.25, 0.45)
    top_z = dz * 0.5 - (0.08 if chamfer_top else 0.0)
    top_scale = 0.90 if chamfer_top else (1.0 + flare)
    z_slices = [
        -dz * 0.5,
        -dz * 0.5 + taper_len,
        0.0,
        dz * 0.5 - taper_len,
        top_z
    ]
    scales = [
        1.0 + flare,
        1.0,
        1.0,
        1.0,
        top_scale
    ]

    import random
    rng = random.Random(int(abs(location[0]*100 + location[1]*37 + location[2]*19)))

    rings = []
    for s_idx, (z, sc) in enumerate(zip(z_slices, scales)):
        ring = []
        jx = (rng.random() - 0.5) * jankiness * 0.04 if (0 < s_idx < 4) else 0.0
        jy = (rng.random() - 0.5) * jankiness * 0.04 if (0 < s_idx < 4) else 0.0
        for corner_x, corner_y in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
            vx = corner_x * dx * sc + jx
            vy = corner_y * dy * sc + jy
            ring.append(bm.verts.new(tr_mat @ Vector((vx, vy, z))))
        rings.append(ring)

    uv_layer = bm.loops.layers.uv.verify()
    faces = []

    # Bottom cap
    f_bot = bm.faces.new(list(reversed(rings[0])))
    f_bot.material_index = mat_index
    for loop in f_bot.loops:
        local_co = tr_mat.inverted() @ loop.vert.co
        loop[uv_layer].uv = Vector(((local_co.x + dx*0.5), (local_co.y + dy*0.5)))
    faces.append(f_bot)

    # Top cap
    f_top = bm.faces.new(rings[-1])
    f_top.material_index = mat_index
    for loop in f_top.loops:
        local_co = tr_mat.inverted() @ loop.vert.co
        loop[uv_layer].uv = Vector(((local_co.x + dx*0.5), (local_co.y + dy*0.5)))
    faces.append(f_top)

    # Side faces
    for r in range(len(rings) - 1):
        r0 = rings[r]
        r1 = rings[r+1]
        z0 = z_slices[r] + dz * 0.5
        z1 = z_slices[r+1] + dz * 0.5
        for c in range(4):
            nxt = (c + 1) % 4
            f = bm.faces.new([r0[c], r0[nxt], r1[nxt], r1[c]])
            f.material_index = mat_index
            u0 = c * 0.25
            u1 = (c + 1) * 0.25
            v0 = z0 * 1.0
            v1 = z1 * 1.0
            f.loops[0][uv_layer].uv = Vector((u0, v0))
            f.loops[1][uv_layer].uv = Vector((u1, v0))
            f.loops[2][uv_layer].uv = Vector((u1, v1))
            f.loops[3][uv_layer].uv = Vector((u0, v1))
            faces.append(f)

    return faces

def create_cylinder(bm, radius=0.5, height=1.0, segments=8, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0):
    """Creates a stylized faceted cylinder with end caps."""
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    
    half_h = height * 0.5
    bottom_verts = []
    top_verts = []
    
    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        bottom_verts.append(bm.verts.new(tr_mat @ Vector((x, y, -half_h))))
        top_verts.append(bm.verts.new(tr_mat @ Vector((x, y, half_h))))
        
    faces = []
    # Side faces
    for i in range(segments):
        nxt = (i + 1) % segments
        f = bm.faces.new([bottom_verts[i], bottom_verts[nxt], top_verts[nxt], top_verts[i]])
        f.material_index = mat_index
        faces.append(f)
        
    # Caps
    f_bot = bm.faces.new(list(reversed(bottom_verts)))
    f_bot.material_index = mat_index
    faces.append(f_bot)
    
    f_top = bm.faces.new(top_verts)
    f_top.material_index = mat_index
    faces.append(f_top)
    
    return faces

def create_horizontal_cylinder(bm, radius_y=0.12, radius_z=0.12, length=1.0, segments=16,
                               location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
                               mat_index=0, mat_index_cap=10, smooth=True, seam_offset=-1.5707963267948966, uv_offset=0.0,
                               flare_start=0.0, flare_end=0.0):
    """
    Creates a rounded horizontal cylinder oriented along local X with circular end caps.
    Uses smooth-shaded cylindrical sides for authentic organic high-poly timber logs,
    radial UV coordinates on end caps for concentric tree growth rings, and optional flaring at ends.
    """
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    
    half_l = length * 0.5
    scale_start = 1.0 + flare_start
    scale_end = 1.0 + flare_end
    
    start_verts = []
    end_verts = []
    
    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments + seam_offset
        y_base = math.cos(angle)
        z_base = math.sin(angle)
        y_s = radius_y * y_base * scale_start
        z_s = radius_z * z_base * scale_start
        y_e = radius_y * y_base * scale_end
        z_e = radius_z * z_base * scale_end
        start_verts.append(bm.verts.new(tr_mat @ Vector((-half_l, y_s, z_s))))
        end_verts.append(bm.verts.new(tr_mat @ Vector((half_l, y_e, z_e))))
        
    uv_layer = bm.loops.layers.uv.verify()
    faces = []
    
    # Smooth cylindrical side quads (V along log length, U around perimeter)
    for i in range(segments):
        nxt = (i + 1) % segments
        f = bm.faces.new([start_verts[i], start_verts[nxt], end_verts[nxt], end_verts[i]])
        f.material_index = mat_index
        f.smooth = smooth
        
        u0 = i / float(segments)
        u1 = (i + 1) / float(segments)
        v0 = uv_offset
        v1 = length * 1.0 + uv_offset
        f.loops[0][uv_layer].uv = Vector((u0, v0))
        f.loops[1][uv_layer].uv = Vector((u1, v0))
        f.loops[2][uv_layer].uv = Vector((u1, v1))
        f.loops[3][uv_layer].uv = Vector((u0, v1))
        faces.append(f)
        
    cap_mat = mat_index_cap if mat_index_cap is not None else mat_index
    
    inset = 0.014
    import random as _rnd
    # Create inner wood verts inset — chunkier bark 1.5cm inset + irregular outer bark
    start_inner = []
    end_inner = []
    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments + seam_offset
        bark_jitter = (_rnd.Random(i*997).random() - 0.5) * 0.018
        y_base = math.cos(angle) * (0.86 + bark_jitter)
        z_base = math.sin(angle) * (0.86 + bark_jitter)
        y_s = radius_y * y_base * scale_start
        z_s = radius_z * z_base * scale_start
        y_e = radius_y * y_base * scale_end
        z_e = radius_z * z_base * scale_end
        start_inner.append(bm.verts.new(tr_mat @ Vector((-half_l + inset, y_s, z_s))))
        end_inner.append(bm.verts.new(tr_mat @ Vector((half_l - inset, y_e, z_e))))
    # also jitter outer verts slightly for irregular bark edge
    for idx, v in enumerate(start_verts + end_verts):
        ang = (2.0 * math.pi * (idx % segments)) / segments + seam_offset
        j = (_rnd.Random(idx*431).random() - 0.5) * 0.012
        local = tr_mat.inverted() @ v.co
        r = (local.y**2 + local.z**2) **0.5
        if r > 1e-6:
            local.y += local.y / r * j
            local.z += local.z / r * j
            v.co = tr_mat @ local
    # Bark side ring faces between outer and inner at each end
    for i in range(segments):
        nxt = (i + 1) % segments
        # Start end bark ring
        f = bm.faces.new([start_verts[i], start_verts[nxt], start_inner[nxt], start_inner[i]])
        f.material_index = mat_index
        f.smooth = True
        u0 = i / float(segments)
        u1 = (i + 1) / float(segments)
        f.loops[0][uv_layer].uv = Vector((u0, 0.0))
        f.loops[1][uv_layer].uv = Vector((u1, 0.0))
        f.loops[2][uv_layer].uv = Vector((u1, 0.05))
        f.loops[3][uv_layer].uv = Vector((u0, 0.05))
        
        # End bark ring
        f2 = bm.faces.new([end_inner[i], end_inner[nxt], end_verts[nxt], end_verts[i]])
        f2.material_index = mat_index
        f2.smooth = True
        f2.loops[0][uv_layer].uv = Vector((u0, 0.0))
        f2.loops[1][uv_layer].uv = Vector((u1, 0.0))
        f2.loops[2][uv_layer].uv = Vector((u1, 0.05))
        f2.loops[3][uv_layer].uv = Vector((u0, 0.05))
    
    # Flat inner wood caps (recessed) with radial concentric UVs matching log end texture
    rev_inner_start = list(reversed(start_inner))
    f_start = bm.faces.new(rev_inner_start)
    f_start.material_index = cap_mat
    f_start.smooth = False
    eff_ry_s = max(0.001, radius_y * scale_start)
    eff_rz_s = max(0.001, radius_z * scale_start)
    for loop in f_start.loops:
        local_v = tr_mat.inverted() @ loop.vert.co
        u = 0.5 + 0.48 * (local_v.y / eff_ry_s)
        v = 0.5 + 0.48 * (local_v.z / eff_rz_s)
        loop[uv_layer].uv = Vector((u, v))
    faces.append(f_start)
    
    f_end = bm.faces.new(end_inner)
    f_end.material_index = cap_mat
    f_end.smooth = False
    eff_ry_e = max(0.001, radius_y * scale_end)
    eff_rz_e = max(0.001, radius_z * scale_end)
    for loop in f_end.loops:
        local_v = tr_mat.inverted() @ loop.vert.co
        u = 0.5 + 0.48 * (local_v.y / eff_ry_e)
        v = 0.5 + 0.48 * (local_v.z / eff_rz_e)
        loop[uv_layer].uv = Vector((u, v))
    faces.append(f_end)

    # Manual UV seams: bottom-most longitudinal edge + both end circles (5 seams total -> side seam + 2 caps)
    try:
        # side seam (wrap edge at bottom)
        for e in bm.edges:
            if (e.verts[0] in start_verts and e.verts[1] in end_verts) or (e.verts[0] in end_verts and e.verts[1] in start_verts):
                # check if edge is at seam angle (bottom)
                mid = (e.verts[0].co + e.verts[1].co) * 0.5
                local_mid = tr_mat.inverted() @ mid
                ang = math.atan2(local_mid.z, local_mid.y)
                if abs(ang + 1.57079632679) < 0.25:
                    e.seam = True
        # cap perimeters
        for e in bm.edges:
            if (e.verts[0] in start_verts and e.verts[1] in start_verts) or (e.verts[0] in start_inner and e.verts[1] in start_inner):
                e.seam = True
            if (e.verts[0] in end_verts and e.verts[1] in end_verts) or (e.verts[0] in end_inner and e.verts[1] in end_inner):
                e.seam = True
    except: pass
    
    return faces

def create_cone(bm, radius1=0.5, radius2=0.05, height=1.5, segments=8, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0):
    """Creates a cone/frustum for turrets and chimneys."""
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    
    half_h = height * 0.5
    bottom_verts = []
    top_verts = []
    
    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments
        x1 = radius1 * math.cos(angle)
        y1 = radius1 * math.sin(angle)
        x2 = radius2 * math.cos(angle)
        y2 = radius2 * math.sin(angle)
        bottom_verts.append(bm.verts.new(tr_mat @ Vector((x1, y1, -half_h))))
        top_verts.append(bm.verts.new(tr_mat @ Vector((x2, y2, half_h))))
        
    faces = []
    for i in range(segments):
        nxt = (i + 1) % segments
        f = bm.faces.new([bottom_verts[i], bottom_verts[nxt], top_verts[nxt], top_verts[i]])
        f.material_index = mat_index
        faces.append(f)
        
    f_bot = bm.faces.new(list(reversed(bottom_verts)))
    f_bot.material_index = mat_index
    faces.append(f_bot)
    
    if radius2 > 0.001:
        f_top = bm.faces.new(top_verts)
        f_top.material_index = mat_index
        faces.append(f_top)
        
    return faces

def apply_box_uvs(bm, scale=1.0, skip_materials=(3, 5, 8, 9, 10, 11, 12, 13, 14, 15)):
    """Calculates clean cubic / triplanar style UVs for bmesh faces.
    Skips faces whose materials already have specialized local unwraps
    (timber frames, roof shingles, forged iron, wood accessories, log end caps, logs, stairs, railings, window frames, shutters).
    Floor (4), stone (0), plaster (1, 2), cut stone (16), and door fallbacks receive continuous world-space meter-scaled UVs.
    Tagged faces (face.tag == True) are also preserved.
    """
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
        if face.tag:
            continue
        if skip_materials is not None and face.material_index in skip_materials:
            continue
        normal = face.normal
        nx, ny, nz = abs(normal.x), abs(normal.y), abs(normal.z)
        
        for loop in face.loops:
            co = loop.vert.co
            if nz >= nx and nz >= ny:
                # Top / bottom projection (XY)
                u = co.x * scale
                v = co.y * scale
            elif nx >= ny:
                # Left / right projection (YZ)
                u = co.y * scale
                v = co.z * scale
            else:
                # Front / back projection (XZ)
                u = co.x * scale
                v = co.z * scale
            loop[uv_layer].uv = Vector((u, v))

def create_torus_ring(bm, location, rotation=(0.0, 0.0, 0.0), major_radius=0.055, minor_radius=0.011, major_segments=16, minor_segments=8, mat_index=8):
    """Generates a smooth torus ring for door pull rings and fantasy iron hardware."""
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    verts = []
    for i in range(major_segments):
        a = 2.0 * math.pi * i / major_segments
        ca = math.cos(a)
        sa = math.sin(a)
        center = Vector((ca * major_radius, sa * major_radius, 0.0))
        ring = []
        for j in range(minor_segments):
            b = 2.0 * math.pi * j / minor_segments
            cb = math.cos(b)
            sb = math.sin(b)
            off = Vector((ca * cb * minor_radius, sa * cb * minor_radius, sb * minor_radius))
            v = bm.verts.new(tr_mat @ (center + off))
            ring.append(v)
        verts.append(ring)
    faces = []
    for i in range(major_segments):
        ni = (i + 1) % major_segments
        for j in range(minor_segments):
            nj = (j + 1) % minor_segments
            f = bm.faces.new([verts[i][j], verts[ni][j], verts[ni][nj], verts[i][nj]])
            f.material_index = mat_index
            f.smooth = True
            faces.append(f)
    return faces

def create_door_batten(bm, size, location, rotation=(0.0, 0.0, 0.0), mat_index=7, bevel_amount=0.004, bevel_segments=2):
    """
    Creates a horizontal door batten with UVs properly oriented so that wood grain
    flows along the length of the board (rather than across its narrow height).
    Faces are tagged (face.tag = True) so apply_box_uvs will preserve these specialized UVs.
    """
    faces = create_beveled_box(bm, size=size, location=location, rotation=rotation,
                              mat_index=mat_index, bevel_amount=bevel_amount, bevel_segments=bevel_segments)
    uv_layer = bm.loops.layers.uv.verify()
    
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    inv_tr = (Matrix.Translation(Vector(location)) @ rot_mat).inverted()
    
    sx, sy, sz = size
    # Determine which axis is the long board axis (length): typically X for front door, Y for balcony door
    is_x_long = (sx >= sy)
    
    for f in faces:
        f.tag = True
        # Face normal in local coordinates
        local_norm = (rot_mat.to_3x3().inverted() @ f.normal).normalized()
        nx, ny, nz = abs(local_norm.x), abs(local_norm.y), abs(local_norm.z)

        for loop in f.loops:
            lco = inv_tr @ loop.vert.co
            if is_x_long:
                # Board length along X, thickness along Y, height along Z
                if nx >= ny and nx >= nz:
                    # End caps (+X, -X)
                    u = lco.y
                    v = lco.z
                elif nz >= ny:
                    # Top / bottom (+Z, -Z)
                    u = lco.y
                    v = lco.x
                else:
                    # Front / back (+Y, -Y)
                    u = lco.z
                    v = lco.x
            else:
                # Board length along Y, thickness along X, height along Z
                if ny >= nx and ny >= nz:
                    # End caps (+Y, -Y)
                    u = lco.x
                    v = lco.z
                elif nz >= nx:
                    # Top / bottom (+Z, -Z)
                    u = lco.x
                    v = lco.y
                else:
                    # Front / back (+X, -X)
                    u = lco.z
                    v = lco.y
            # Cross-members carry grain across their short axis: rotate the UVs
            # 90 degrees (swap U/V) on every door batten face.
            u, v = v, u
            loop[uv_layer].uv = Vector((u, v))
            
    return faces


def add_wonkiness(bm, z_min, z_max, amount=0.08, seed=0):
    """
    Perturbs vertices based on height and random seed to give
    the iconic whimsical fantasy curvature, handmade lean, and Warcraft-style silhouette.
    """
    if amount <= 0.001:
        return
        
    rng = random.Random(seed + 999)
    lean_x = (rng.random() - 0.5) * amount * 1.5
    lean_y = (rng.random() - 0.5) * amount * 1.5
    sag_dir = (rng.random() - 0.5) * amount
    
    h_span = max(0.1, z_max - z_min)
    
    for v in bm.verts:
        rel_z = max(0.0, min(1.0, (v.co.z - z_min) / h_span))
        # Upper levels lean progressively
        lean_factor = rel_z * rel_z
        v.co.x += lean_x * lean_factor
        v.co.y += lean_y * lean_factor
        
        # Stylized horizontal S-curve / wave
        wave = math.sin(v.co.z * 1.2 + seed) * (amount * 0.45)
        v.co.x += wave
        v.co.y += wave * 0.65
