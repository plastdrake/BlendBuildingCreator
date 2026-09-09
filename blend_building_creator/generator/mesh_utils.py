"""
Geometry and bmesh helper utilities for procedural stylized building generation.
Provides robust primitives, deformations, and UV generation for Blender 5.2.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler
import random

def create_box(bm, size=(1.0, 1.0, 1.0), location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0):
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
        (0, 1, 2, 3), # Bottom
        (4, 7, 6, 5), # Top
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
        
        # Local length-aligned UV unwrapping for wood grain flow along beam
        # Identify major length axis:
        if dz >= dx and dz >= dy:
            # Vertical post / column: V along Z
            if f_idx in (0, 1): # Bottom / Top end caps
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((dx * scale, 0.0))
                f.loops[2][uv_layer].uv = Vector((dx * scale, dy * scale))
                f.loops[3][uv_layer].uv = Vector((0.0, dy * scale))
            elif f_idx == 2: # Front (-Y)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dz * scale))
                f.loops[2][uv_layer].uv = Vector((dx * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((dx * scale, 0.0))
            elif f_idx == 3: # Right (+X)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dz * scale))
                f.loops[2][uv_layer].uv = Vector((dy * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((dy * scale, 0.0))
            elif f_idx == 4: # Back (+Y)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dz * scale))
                f.loops[2][uv_layer].uv = Vector((dx * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((dx * scale, 0.0))
            else: # Left (-X)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dz * scale))
                f.loops[2][uv_layer].uv = Vector((dy * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((dy * scale, 0.0))
        elif dx >= dy:
            # Horizontal beam along X: V along X
            if f_idx in (3, 5): # End caps (+X, -X)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((dy * scale, 0.0))
                f.loops[2][uv_layer].uv = Vector((dy * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((0.0, dz * scale))
            else: # Sides (Bottom, Top, Front, Back)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dx * scale))
                f.loops[2][uv_layer].uv = Vector((dy * scale, dx * scale))
                f.loops[3][uv_layer].uv = Vector((dy * scale, 0.0))
        else:
            # Horizontal beam along Y: V along Y
            if f_idx in (2, 4): # End caps (-Y, +Y)
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((dx * scale, 0.0))
                f.loops[2][uv_layer].uv = Vector((dx * scale, dz * scale))
                f.loops[3][uv_layer].uv = Vector((0.0, dz * scale))
            else: # Sides
                f.loops[0][uv_layer].uv = Vector((0.0, 0.0))
                f.loops[1][uv_layer].uv = Vector((0.0, dy * scale))
                f.loops[2][uv_layer].uv = Vector((dx * scale, dy * scale))
                f.loops[3][uv_layer].uv = Vector((dx * scale, 0.0))
        
    return faces

def create_beveled_box(bm, size=(1.0, 1.0, 1.0), location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), mat_index=0, bevel_amount=0.03):
    """Creates a box and slightly chamfers/bevels its edges for a chunky stylized look."""
    faces = create_box(bm, size, location, rotation, mat_index)
    if bevel_amount > 0.001:
        edges = list({e for f in faces for e in f.edges})
        try:
            res = bmesh.ops.bevel(bm, geom=edges, offset=bevel_amount, segments=1, profile=0.5, affect='EDGES')
            for f in res.get('faces', []):
                f.material_index = mat_index
        except Exception:
            pass
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
                               mat_index=0, mat_index_cap=10, smooth=True):
    """
    Creates a rounded horizontal cylinder oriented along local X with circular end caps.
    Uses smooth-shaded cylindrical sides for authentic organic high-poly timber logs,
    and radial UV coordinates on end caps for concentric tree growth rings.
    """
    rot_mat = Euler(rotation, 'XYZ').to_matrix().to_4x4()
    loc_mat = Matrix.Translation(Vector(location))
    tr_mat = loc_mat @ rot_mat
    
    half_l = length * 0.5
    start_verts = []
    end_verts = []
    
    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments
        y = radius_y * math.cos(angle)
        z = radius_z * math.sin(angle)
        start_verts.append(bm.verts.new(tr_mat @ Vector((-half_l, y, z))))
        end_verts.append(bm.verts.new(tr_mat @ Vector((half_l, y, z))))
        
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
        v0 = 0.0
        v1 = length * 1.0
        f.loops[0][uv_layer].uv = Vector((u0, v0))
        f.loops[1][uv_layer].uv = Vector((u1, v0))
        f.loops[2][uv_layer].uv = Vector((u1, v1))
        f.loops[3][uv_layer].uv = Vector((u0, v1))
        faces.append(f)
        
    cap_mat = mat_index_cap if mat_index_cap is not None else mat_index
    
    # Flat start cap (facing -X) with radial concentric UVs
    rev_start = list(reversed(start_verts))
    f_start = bm.faces.new(rev_start)
    f_start.material_index = cap_mat
    f_start.smooth = False
    for loop in f_start.loops:
        # Compute local angle in cap plane
        local_v = tr_mat.inverted() @ loop.vert.co
        u = 0.5 + 0.48 * (local_v.y / max(0.001, radius_y))
        v = 0.5 + 0.48 * (local_v.z / max(0.001, radius_z))
        loop[uv_layer].uv = Vector((u, v))
    faces.append(f_start)
    
    # Flat end cap (facing +X) with radial concentric UVs
    f_end = bm.faces.new(end_verts)
    f_end.material_index = cap_mat
    f_end.smooth = False
    for loop in f_end.loops:
        local_v = tr_mat.inverted() @ loop.vert.co
        u = 0.5 + 0.48 * (local_v.y / max(0.001, radius_y))
        v = 0.5 + 0.48 * (local_v.z / max(0.001, radius_z))
        loop[uv_layer].uv = Vector((u, v))
    faces.append(f_end)
    
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

def apply_box_uvs(bm, scale=1.0):
    """Calculates clean cubic / triplanar style UVs for bmesh faces."""
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
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
