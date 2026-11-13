"""
Dedicated props for the Hajfin Shark-Pirate faction.

Features stylized, fantasy-overexaggerated nautical and tribal pirate props:
- Whale rib archways & rafters
- Menacing shark jaw totems
- Scrimshaw bone trading counter
- Heavy whaling harpoon weapon rack
- Chieftain's driftwood throne
- Grog casks & rum barrels cluster
- Fish drying & net hanging rack
- Stylized dorsal fin rooftop crest
"""

import math
from mathutils import Matrix, Vector

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
    create_torus_ring, transform_faces
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON,
    MAT_INDEX_ROPE, MAT_INDEX_FISH,
    MAT_INDEX_BONE, MAT_INDEX_DRIFTWOOD, MAT_INDEX_ROUGH_STONE,
    MAT_INDEX_SILVER
)


def _place(x, y, z_ground=0.0, ang=0.0):
    return Matrix.Translation((x, y, z_ground)) @ Matrix.Rotation(ang, 4, 'Z')


def _stamp_meshdata(bm, key, x=0.0, y=0.0, z=0.0, scale=1.0, yaw=0.0, pitch=0.0, roll=0.0,
                    anchor='BASE', default_mat=MAT_INDEX_BONE):
    """Stamps an artist-crafted baked prop mesh into the bmesh preserving all material slots and UVs."""
    from .artisan_meshdata import PROP_MESHES
    it = PROP_MESHES.get(key)
    if not it:
        return []

    verts = it['verts']
    polys = it['polys']
    poly_mats = it.get('poly_mats')
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    cz = min(zs) if anchor == 'BASE' else (min(zs) + max(zs)) * 0.5

    rot = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y') @ Matrix.Rotation(roll, 4, 'X')
    s_mat = Matrix.Diagonal((scale, scale, scale, 1.0))
    trans = Matrix.Translation((x, y, z))
    base = Matrix.Translation((-cx, -cy, -cz))
    M = trans @ rot @ s_mat @ base

    uv_layer = bm.loops.layers.uv.verify()
    used = set(vi for poly in polys for vi, _ in poly)
    remap = {i: bm.verts.new(M @ Vector(verts[i])) for i in used}

    new_faces = []
    seen = set()
    for pi, poly in enumerate(polys):
        idx = [vi for vi, _ in poly]
        key_f = tuple(sorted(idx))
        if key_f in seen:
            continue
        seen.add(key_f)
        f = bm.faces.new([remap[i] for i in idx])
        _slot = poly_mats[pi] if poly_mats and pi < len(poly_mats) and poly_mats[pi] >= 0 else default_mat
        f.material_index = _slot
        f.smooth = True
        f.tag = True  # Protect atlas UVs
        uv_map = {vi: uv for vi, uv in poly}
        for loop in f.loops:
            for i in idx:
                if remap[i] == loop.vert:
                    loop[uv_layer].uv = uv_map[i]
                    break
        new_faces.append(f)
    return new_faces


# ---------------------------------------------------------------------------
# 1. Whale Rib Archway
# ---------------------------------------------------------------------------

def build_whale_rib_arch(bm, x, y, z_ground=0.0, ang=0.0, width=2.4, height=3.2):
    """
    Curved whale rib archway. Two massive tapering ivory ribs meet at the apex,
    anchored in rough reef stone plinths and bound at the peak with heavy hemp rope.
    """
    faces = []
    half_w = width * 0.5
    
    # 1. Rough reef stone anchor bases at bottom
    for sgn in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(0.48, 0.48, 0.32),
            location=(sgn * half_w, 0.0, 0.16),
            mat_index=MAT_INDEX_ROUGH_STONE, bevel_amount=0.04
        )
    
    # 2. Segmented curved ribs (approximated with segmented tapering bone boxes)
    n_segs = 6
    for sgn in (-1.0, 1.0):
        curr_x = sgn * half_w
        curr_z = 0.32
        for i in range(n_segs):
            t0 = i / float(n_segs)
            t1 = (i + 1) / float(n_segs)
            # Quadratic curve toward apex at x=0, z=height
            next_x = sgn * half_w * (1.0 - t1)**1.4
            next_z = 0.32 + (height - 0.32) * math.sin(t1 * math.pi * 0.5)
            
            mid_x = (curr_x + next_x) * 0.5
            mid_z = (curr_z + next_z) * 0.5
            dx = next_x - curr_x
            dz = next_z - curr_z
            seg_len = math.sqrt(dx * dx + dz * dz)
            rot_y = math.atan2(dx, dz)
            
            thick = 0.26 * (1.0 - 0.55 * t0)
            faces += create_beveled_box(
                bm, size=(thick, thick * 0.85, seg_len + 0.03),
                location=(mid_x, 0.0, mid_z),
                rotation=(0.0, rot_y, 0.0),
                mat_index=MAT_INDEX_BONE, bevel_amount=0.02
            )
            curr_x, curr_z = next_x, next_z
            
    # 3. Heavy rope binding at the apex
    faces += create_cylinder(
        bm, radius=0.18, height=0.36, segments=12,
        location=(0.0, 0.0, height - 0.08),
        rotation=(0.0, math.pi * 0.5, 0.0),
        mat_index=MAT_INDEX_ROPE
    )
    # Hanging rope cord ends
    faces += create_cylinder(
        bm, radius=0.04, height=0.45, segments=8,
        location=(0.08, 0.0, height - 0.32),
        mat_index=MAT_INDEX_ROPE
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 2. Shark Jaw Totem
# ---------------------------------------------------------------------------

def build_shark_jaw_totem(bm, x, y, z_ground=0.0, ang=0.0, height=2.6):
    """
    Towering crooked driftwood pole wrapped with rope, crowned with a massive
    stylized shark jaw with jagged triangular ivory teeth.
    """
    faces = []
    
    # 1. Base stone anchor cairn
    faces += create_beveled_box(
        bm, size=(0.55, 0.55, 0.35),
        location=(0.0, 0.0, 0.175),
        mat_index=MAT_INDEX_ROUGH_STONE, bevel_amount=0.05
    )
    
    # 2. Crooked driftwood pole (2 segments slightly tilted)
    pole_h1 = 1.2
    faces += create_cylinder(
        bm, radius=0.13, height=pole_h1, segments=10,
        location=(0.0, 0.0, pole_h1 * 0.5 + 0.25),
        rotation=(0.04, -0.06, 0.0),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    pole_h2 = height - 1.2 - 0.25
    faces += create_cylinder(
        bm, radius=0.11, height=pole_h2, segments=10,
        location=(-0.04, 0.03, 1.2 + pole_h2 * 0.5),
        rotation=(-0.05, 0.08, 0.0),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    
    # 3. Rope wrap collars around pole
    for rz in (0.6, 1.3, 1.85):
        faces += create_torus_ring(
            bm, location=(-0.02, 0.01, rz),
            major_radius=0.14, minor_radius=0.03,
            mat_index=MAT_INDEX_ROPE
        )
    
    # 4. Mounted Gaping Shark Jaw at top
    jaw_cz = height - 0.30
    jaw_w = 0.70
    jaw_h = 0.55
    
    # Upper jaw curve (horseshoe arch of bone segments)
    n_pts = 7
    jaw_pts = []
    for i in range(n_pts):
        th = math.pi * i / (n_pts - 1)
        jx = math.cos(th) * jaw_w * 0.5
        jz = math.sin(th) * jaw_h * 0.5
        jaw_pts.append((jx, jz))
        
    for i in range(n_pts - 1):
        p0 = jaw_pts[i]
        p1 = jaw_pts[i + 1]
        mx = (p0[0] + p1[0]) * 0.5
        mz = (p0[1] + p1[1]) * 0.5 + jaw_cz
        dx = p1[0] - p0[0]
        dz = p1[1] - p0[1]
        slen = math.sqrt(dx * dx + dz * dz)
        ry = math.atan2(dx, dz)
        faces += create_beveled_box(
            bm, size=(0.10, 0.12, slen + 0.02),
            location=(mx, -0.08, mz),
            rotation=(0.0, ry, 0.0),
            mat_index=MAT_INDEX_BONE, bevel_amount=0.015
        )
        
        # Triangular shark teeth pointing inward along the jaw rim
        tooth_dir = -1.0 if mx >= 0 else 1.0
        faces += create_cone(
            bm, radius1=0.035, radius2=0.002, height=0.08, segments=5,
            location=(mx, -0.08, mz - 0.03),
            rotation=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_BONE
        )
    
    # Lower jaw curve
    for i in range(n_pts - 1):
        p0 = jaw_pts[i]
        p1 = jaw_pts[i + 1]
        mx = (p0[0] + p1[0]) * 0.5
        mz = jaw_cz - (p0[1] + p1[1]) * 0.5
        dx = p1[0] - p0[0]
        dz = -(p1[1] - p0[1])
        slen = math.sqrt(dx * dx + dz * dz)
        ry = math.atan2(dx, dz)
        faces += create_beveled_box(
            bm, size=(0.09, 0.11, slen + 0.02),
            location=(mx, -0.08, mz),
            rotation=(0.0, ry, 0.0),
            mat_index=MAT_INDEX_BONE, bevel_amount=0.015
        )
        # Upward pointing teeth
        faces += create_cone(
            bm, radius1=0.032, radius2=0.002, height=0.075, segments=5,
            location=(mx, -0.08, mz + 0.03),
            rotation=(math.pi, 0.0, 0.0),
            mat_index=MAT_INDEX_BONE
        )

    # 5. Hanging bone vertebrae charm beneath the jaw
    faces += create_cylinder(
        bm, radius=0.02, height=0.35, segments=6,
        location=(0.0, -0.08, jaw_cz - jaw_h * 0.5 - 0.20),
        mat_index=MAT_INDEX_ROPE
    )
    for vz in (jaw_cz - jaw_h * 0.5 - 0.12, jaw_cz - jaw_h * 0.5 - 0.25, jaw_cz - jaw_h * 0.5 - 0.38):
        faces += create_cylinder(
            bm, radius=0.06, height=0.07, segments=8,
            location=(0.0, -0.08, vz),
            mat_index=MAT_INDEX_BONE
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 3. Scrimshaw Bone Trading Counter
# ---------------------------------------------------------------------------

def build_scrimshaw_bone_counter(bm, x, y, z_ground=0.0, ang=0.0, width=2.2, depth=0.8, height=0.92):
    """
    Pirate bone trader's workbench / shop counter:
    Heavy driftwood frame with stacked whale vertebrae pillars,
    a thick ivory bone slab tabletop, bone trinket boxes, and an embedded cleaver.
    """
    faces = []
    
    # 1. Four heavy driftwood corner legs
    leg_sz = 0.14
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            lx = sx * (width * 0.5 - leg_sz * 0.5)
            ly = sy * (depth * 0.5 - leg_sz * 0.5)
            faces += create_beveled_box(
                bm, size=(leg_sz, leg_sz, height - 0.08),
                location=(lx, ly, (height - 0.08) * 0.5),
                mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.015
            )
            
    # 2. Central support pillars made of stacked bone vertebrae
    for sx in (-0.45, 0.45):
        cx = sx * (width * 0.5)
        for vz in (0.22, 0.44, 0.66):
            faces += create_cylinder(
                bm, radius=0.11, height=0.16, segments=10,
                location=(cx, 0.0, vz),
                mat_index=MAT_INDEX_BONE
            )

    # 3. Bottom driftwood foot rails
    faces += create_beveled_box(
        bm, size=(width - leg_sz, 0.08, 0.08),
        location=(0.0, -depth * 0.5 + leg_sz * 0.5, 0.12),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.01
    )
    faces += create_beveled_box(
        bm, size=(width - leg_sz, 0.08, 0.08),
        location=(0.0, depth * 0.5 - leg_sz * 0.5, 0.12),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.01
    )

    # 4. Heavy bone slab countertop (two thick ivory boards with seam)
    top_t = 0.08
    top_z = height - top_t * 0.5
    for sy in (-1.0, 1.0):
        by = sy * (depth * 0.25)
        faces += create_beveled_box(
            bm, size=(width + 0.12, depth * 0.48, top_t),
            location=(0.0, by, top_z),
            mat_index=MAT_INDEX_BONE, bevel_amount=0.018
        )

    # 5. Goods on the counter:
    # A. Stack of carved scrimshaw whale teeth
    faces += create_cone(
        bm, radius1=0.05, radius2=0.005, height=0.18, segments=8,
        location=(-0.55, 0.10, height + 0.09),
        rotation=(0.1, 0.0, 0.4),
        mat_index=MAT_INDEX_BONE
    )
    faces += create_cone(
        bm, radius1=0.045, radius2=0.005, height=0.16, segments=8,
        location=(-0.45, 0.12, height + 0.08),
        rotation=(-0.1, 0.1, -0.3),
        mat_index=MAT_INDEX_BONE
    )
    # B. Iron coin dish / barter bowl
    faces += create_cylinder(
        bm, radius=0.12, height=0.04, segments=12,
        location=(0.20, 0.08, height + 0.02),
        mat_index=MAT_INDEX_IRON
    )
    # C. Heavy cleaver stuck into the driftwood rail
    faces += create_beveled_box(
        bm, size=(0.16, 0.02, 0.12),
        location=(0.65, 0.05, height + 0.06),
        rotation=(0.0, 0.15, 0.0),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.003
    )
    faces += create_cylinder(
        bm, radius=0.022, height=0.14, segments=8,
        location=(0.65, 0.05, height + 0.18),
        rotation=(0.0, 0.15, 0.0),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    # D. Prized sea-monster beast skull displayed on the bone counter
    faces += _stamp_meshdata(bm, 'hajfin_skull', x=-0.12, y=0.04, z=height, scale=0.88, yaw=0.35, anchor='BASE')

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 4. Whaling Harpoon Rack
# ---------------------------------------------------------------------------

def build_harpoon_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.6, height=1.75):
    """
    A-frame driftwood rack holding 3 heavy barbed pirate whaling harpoons
    with wicked iron heads and coiled rope lanyards.
    """
    faces = []
    
    # 1. Two A-frame driftwood sides
    for sgn in (-1.0, 1.0):
        sx = sgn * (width * 0.5 - 0.08)
        # Front strut
        faces += create_beveled_box(
            bm, size=(0.10, 0.09, height),
            location=(sx, -0.22, height * 0.5),
            rotation=(0.25, 0.0, 0.0),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.012
        )
        # Back strut
        faces += create_beveled_box(
            bm, size=(0.10, 0.09, height),
            location=(sx, 0.22, height * 0.5),
            rotation=(-0.25, 0.0, 0.0),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.012
        )
        # Cross brace
        faces += create_beveled_box(
            bm, size=(0.08, 0.48, 0.07),
            location=(sx, 0.0, 0.45),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.01
        )
        
    # 2. Horizontal support stretcher rails with pegs
    for hz in (0.75, 1.15, 1.50):
        faces += create_beveled_box(
            bm, size=(width, 0.08, 0.07),
            location=(0.0, -0.06, hz),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.01
        )
        # Peg rests
        for sx in (-0.45, 0.45):
            faces += create_cylinder(
                bm, radius=0.02, height=0.16, segments=8,
                location=(sx, -0.12, hz + 0.02),
                rotation=(math.pi * 0.5, 0.0, 0.0),
                mat_index=MAT_INDEX_DRIFTWOOD
            )

    # 3. Three Barbed Whaling Harpoons on the rack
    for idx, hz in enumerate((0.79, 1.19, 1.54)):
        tilt = (0.05 if idx % 2 else -0.04)
        harp_len = width * 1.25
        # Wood shaft
        faces += create_cylinder(
            bm, radius=0.024, height=harp_len, segments=8,
            location=(0.0, -0.14, hz + 0.03),
            rotation=(0.0, math.pi * 0.5 + tilt, 0.0),
            mat_index=MAT_INDEX_DRIFTWOOD
        )
        # Barbed iron harpoon head at right side
        head_x = harp_len * 0.5 + 0.10
        faces += create_cone(
            bm, radius1=0.045, radius2=0.002, height=0.22, segments=6,
            location=(head_x, -0.14, hz + 0.03),
            rotation=(0.0, -math.pi * 0.5, 0.0),
            mat_index=MAT_INDEX_IRON
        )
        # Cruel barb flanges
        faces += create_beveled_box(
            bm, size=(0.08, 0.012, 0.06),
            location=(head_x - 0.08, -0.14, hz + 0.05),
            rotation=(0.0, -0.5, 0.0),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.002
        )
        # Coiled rope lanyard near head socket
        faces += create_cylinder(
            bm, radius=0.042, height=0.14, segments=8,
            location=(head_x - 0.18, -0.14, hz + 0.03),
            rotation=(0.0, math.pi * 0.5, 0.0),
            mat_index=MAT_INDEX_ROPE
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 5. Chieftain's Driftwood Throne
# ---------------------------------------------------------------------------

def build_chieftain_driftwood_throne(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """
    Grand pirate chieftain throne:
    Anchored on rough reef basalt, wide weathered driftwood seat,
    flaring dorsal-fin backrest crowned with curved whale ribs.
    """
    faces = []
    
    # 1. Rough reef rock dais
    faces += create_beveled_box(
        bm, size=(1.50 * scale, 1.40 * scale, 0.28 * scale),
        location=(0.0, 0.0, 0.14 * scale),
        mat_index=MAT_INDEX_ROUGH_STONE, bevel_amount=0.05 * scale
    )
    
    # 2. Heavy throne base box
    seat_z = (0.28 + 0.42) * scale
    faces += create_beveled_box(
        bm, size=(1.10 * scale, 0.90 * scale, 0.42 * scale),
        location=(0.0, 0.0, 0.28 * scale + 0.21 * scale),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.03 * scale
    )
    
    # 3. Flaring throne backrest (vertical driftwood planks splayed outward like a fin)
    n_back = 5
    for i in range(n_back):
        t = (i - 2) / 2.0  # -1.0 to 1.0
        bx = t * 0.38 * scale
        b_h = (1.50 - abs(t) * 0.35) * scale  # tallest in center like a dorsal fin
        faces += create_beveled_box(
            bm, size=(0.18 * scale, 0.08 * scale, b_h),
            location=(bx, 0.38 * scale, seat_z + b_h * 0.5),
            rotation=(-0.14, t * 0.12, 0.0),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.015 * scale
        )
        
    # 4. Flanking curved whale rib horns at back corners
    for sgn in (-1.0, 1.0):
        faces += create_cylinder(
            bm, radius=0.07 * scale, height=1.3 * scale, segments=8,
            location=(sgn * 0.52 * scale, 0.34 * scale, seat_z + 0.65 * scale),
            rotation=(-0.18, sgn * 0.32, 0.0),
            mat_index=MAT_INDEX_BONE
        )

    # 5. Armrests with bone caps
    for sgn in (-1.0, 1.0):
        ax = sgn * 0.50 * scale
        # Timber arm support
        faces += create_beveled_box(
            bm, size=(0.12 * scale, 0.65 * scale, 0.28 * scale),
            location=(ax, -0.05 * scale, seat_z + 0.14 * scale),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.015 * scale
        )
        # Carved ivory bone armrest cap
        faces += create_beveled_box(
            bm, size=(0.14 * scale, 0.70 * scale, 0.05 * scale),
            location=(ax, -0.05 * scale, seat_z + 0.30 * scale),
            mat_index=MAT_INDEX_BONE, bevel_amount=0.012 * scale
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 6. Pirate Grog Barrels Cluster
# ---------------------------------------------------------------------------

def build_pirate_grog_barrels(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """
    Cluster of 3 grog casks on a weathered timber pallet:
    Two standing casks with iron hoops and one on its side with a brass spigot tap.
    Uses the artist's authentic Barrel.fbx mesh.
    """
    faces = []
    
    # 1. Weathered pallet platform
    faces += create_beveled_box(
        bm, size=(1.30 * scale, 1.10 * scale, 0.10 * scale),
        location=(0.0, 0.0, 0.05 * scale),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.015 * scale
    )

    from .artisan_meshdata import PROP_MESHES
    if 'hajfin_barrel' in PROP_MESHES:
        faces += _stamp_meshdata(bm, 'hajfin_barrel', -0.25 * scale, -0.15 * scale, 0.10 * scale,
                                 scale=0.58 * scale, yaw=0.4, default_mat=MAT_INDEX_DRIFTWOOD)
        faces += _stamp_meshdata(bm, 'hajfin_barrel', 0.32 * scale, -0.18 * scale, 0.10 * scale,
                                 scale=0.50 * scale, yaw=1.3, default_mat=MAT_INDEX_DRIFTWOOD)
        faces += _stamp_meshdata(bm, 'hajfin_barrel', 0.02 * scale, 0.24 * scale, 0.10 * scale,
                                 scale=0.48 * scale, yaw=0.2, pitch=math.pi * 0.5, anchor='BASE', default_mat=MAT_INDEX_DRIFTWOOD)
        # Wedge chocks underneath
        for sgn in (-1.0, 1.0):
            faces += create_beveled_box(
                bm, size=(0.10 * scale, 0.16 * scale, 0.08 * scale),
                location=(sgn * 0.18 * scale, 0.24 * scale, 0.14 * scale),
                mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.008 * scale
            )
        # Iron tap spigot in barrel face
        b3_h = 1.28 * 0.48 * scale
        b3_cz = 0.10 * scale + (1.38 * 0.48 * scale) * 0.5
        tap_x = 0.02 * scale + math.cos(0.2) * (b3_h * 0.5 + 0.04 * scale)
        tap_y = 0.24 * scale + math.sin(0.2) * (b3_h * 0.5 + 0.04 * scale)
        faces += create_cylinder(
            bm, radius=0.018 * scale, height=0.10 * scale, segments=8,
            location=(tap_x, tap_y, b3_cz),
            rotation=(0.0, math.pi * 0.5, 0.2),
            mat_index=MAT_INDEX_IRON
        )
        faces += create_cylinder(
            bm, radius=0.014 * scale, height=0.08 * scale, segments=8,
            location=(tap_x + 0.02 * scale, tap_y, b3_cz - 0.04 * scale),
            mat_index=MAT_INDEX_IRON
        )
        transform_faces(faces, _place(x, y, z_ground, ang))
        return faces

    # Fallback procedural barrels if artist mesh unavailable
    # 2. Barrel 1 (Large upright grog cask)
    b1_r = 0.34 * scale
    b1_h = 0.78 * scale
    faces += create_cylinder(
        bm, radius=b1_r, height=b1_h, segments=12,
        location=(-0.25 * scale, -0.15 * scale, 0.10 * scale + b1_h * 0.5),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    for hz in (0.22 * scale, 0.45 * scale, 0.75 * scale):
        faces += create_torus_ring(
            bm, location=(-0.25 * scale, -0.15 * scale, 0.10 * scale + hz),
            major_radius=b1_r + 0.01 * scale, minor_radius=0.016 * scale,
            mat_index=MAT_INDEX_IRON
        )
        
    # 3. Barrel 2 (Medium upright rum cask)
    b2_r = 0.28 * scale
    b2_h = 0.65 * scale
    faces += create_cylinder(
        bm, radius=b2_r, height=b2_h, segments=12,
        location=(0.32 * scale, -0.18 * scale, 0.10 * scale + b2_h * 0.5),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    for hz in (0.18 * scale, 0.40 * scale, 0.60 * scale):
        faces += create_torus_ring(
            bm, location=(0.32 * scale, -0.18 * scale, 0.10 * scale + hz),
            major_radius=b2_r + 0.01 * scale, minor_radius=0.015 * scale,
            mat_index=MAT_INDEX_IRON
        )

    # 4. Barrel 3 (Tilted on side with tap spigot)
    b3_r = 0.25 * scale
    b3_h = 0.62 * scale
    b3_cz = 0.10 * scale + b3_r + 0.04 * scale
    faces += create_cylinder(
        bm, radius=b3_r, height=b3_h, segments=12,
        location=(0.02 * scale, 0.24 * scale, b3_cz),
        rotation=(0.0, math.pi * 0.5, 0.2),
        mat_index=MAT_INDEX_DRIFTWOOD
    )
    # Wedge chocks underneath
    for sgn in (-1.0, 1.0):
        faces += create_beveled_box(
            bm, size=(0.10 * scale, 0.16 * scale, 0.08 * scale),
            location=(sgn * 0.18 * scale, 0.24 * scale, 0.14 * scale),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.008 * scale
        )
    # Iron tap spigot in barrel face
    tap_x = 0.02 * scale + math.cos(0.2) * (b3_h * 0.5 + 0.05 * scale)
    tap_y = 0.24 * scale + math.sin(0.2) * (b3_h * 0.5 + 0.05 * scale)
    faces += create_cylinder(
        bm, radius=0.018 * scale, height=0.10 * scale, segments=8,
        location=(tap_x, tap_y, b3_cz),
        rotation=(0.0, math.pi * 0.5, 0.2),
        mat_index=MAT_INDEX_IRON
    )
    faces += create_cylinder(
        bm, radius=0.014 * scale, height=0.08 * scale, segments=8,
        location=(tap_x + 0.02 * scale, tap_y, b3_cz - 0.04 * scale),
        mat_index=MAT_INDEX_IRON
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 7. Fish Drying & Net Rack
# ---------------------------------------------------------------------------

def build_fish_hanging_rack(bm, x, y, z_ground=0.0, ang=0.0, width=1.8, height=1.65):
    """
    Two weathered driftwood poles with a crossbar, draped with hemp netting
    and strings of hung dried fish.
    """
    faces = []
    
    # 1. Two upright poles
    half_w = width * 0.5
    for sgn in (-1.0, 1.0):
        px = sgn * half_w
        faces += create_cylinder(
            bm, radius=0.08, height=height, segments=8,
            location=(px, 0.0, height * 0.5),
            mat_index=MAT_INDEX_DRIFTWOOD
        )
        # Base rock anchor
        faces += create_beveled_box(
            bm, size=(0.32, 0.32, 0.20),
            location=(px, 0.0, 0.10),
            mat_index=MAT_INDEX_ROUGH_STONE, bevel_amount=0.03
        )
        
    # 2. Horizontal crossbeam
    faces += create_beveled_box(
        bm, size=(width + 0.25, 0.10, 0.09),
        location=(0.0, 0.0, height - 0.08),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.012
    )
    
    # 3. Rope lashings at joints
    for sgn in (-1.0, 1.0):
        faces += create_torus_ring(
            bm, location=(sgn * half_w, 0.0, height - 0.08),
            major_radius=0.10, minor_radius=0.025,
            mat_index=MAT_INDEX_ROPE
        )

    # 4. Hung fish strings (4 hung fish along crossbar)
    fish_xs = [-0.55, -0.20, 0.20, 0.55]
    for fx in fish_xs:
        # Hanging string
        faces += create_cylinder(
            bm, radius=0.012, height=0.35, segments=6,
            location=(fx, 0.0, height - 0.25),
            mat_index=MAT_INDEX_ROPE
        )
        # Stylized fish body
        faces += create_cylinder(
            bm, radius=0.07, height=0.38, segments=8,
            location=(fx, 0.0, height - 0.55),
            rotation=(0.0, 0.0, 0.1),
            mat_index=MAT_INDEX_FISH
        )
        # Fish tail fin
        faces += create_cone(
            bm, radius1=0.08, radius2=0.01, height=0.14, segments=4,
            location=(fx, 0.0, height - 0.78),
            mat_index=MAT_INDEX_FISH
        )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 8. Dorsal Fin Crest (Rooftop / Prow ornament)
# ---------------------------------------------------------------------------

def build_dorsal_fin_crest(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """
    Overexaggerated shark dorsal fin crest:
    Swept-back curved fin ornament with notched serrations, iron bolt plates,
    and carved scrimshaw ivory tooth trim.
    """
    faces = []
    
    # Fin base mounting plate
    faces += create_beveled_box(
        bm, size=(0.35 * scale, 0.90 * scale, 0.12 * scale),
        location=(0.0, 0.0, 0.06 * scale),
        mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.015 * scale
    )
    
    # Swept-back fin profile (segmented curved boxes)
    fin_h = 1.30 * scale
    n_segs = 5
    for i in range(n_segs):
        t0 = i / float(n_segs)
        t1 = (i + 1) / float(n_segs)
        sy0 = (t0**1.3) * 0.45 * scale
        sy1 = (t1**1.3) * 0.45 * scale
        sz0 = 0.12 * scale + t0 * fin_h
        sz1 = 0.12 * scale + t1 * fin_h
        
        thick = (0.16 * (1.0 - t0 * 0.75)) * scale
        len_y = (0.75 * (1.0 - t0 * 0.65)) * scale
        faces += create_beveled_box(
            bm, size=(thick, len_y, (fin_h / n_segs) + 0.04 * scale),
            location=(0.0, (sy0 + sy1) * 0.5 - 0.05 * scale, (sz0 + sz1) * 0.5),
            mat_index=MAT_INDEX_DRIFTWOOD, bevel_amount=0.012 * scale
        )
        
    # Bone tooth spikes along the trailing edge
    for i in range(3):
        tz = (0.45 + i * 0.32) * scale
        faces += create_cone(
            bm, radius1=0.035 * scale, radius2=0.005 * scale, height=0.14 * scale, segments=6,
            location=(0.0, 0.28 * scale + i * 0.08 * scale, tz),
            rotation=(0.4, 0.0, 0.0),
            mat_index=MAT_INDEX_BONE
        )
        
    # Iron rivet band around base
    faces += create_beveled_box(
        bm, size=(0.22 * scale, 0.85 * scale, 0.06 * scale),
        location=(0.0, 0.0, 0.14 * scale),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.005 * scale
    )

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 9. Individual Hajfin Cask / Barrel
# ---------------------------------------------------------------------------

def build_single_hajfin_barrel(bm, x, y, z_ground=0.0, ang=0.0, scale=0.55):
    """
    Handcrafted authentic Hajfin timber & iron grog barrel from artist's Barrel.fbx.
    """
    faces = _stamp_meshdata(bm, 'hajfin_barrel', 0.0, 0.0, 0.0, scale=scale, default_mat=MAT_INDEX_DRIFTWOOD)
    if not faces:
        # Fallback procedural
        h = 0.72 * (scale / 0.55)
        r = 0.32 * (scale / 0.55)
        faces += create_cylinder(bm, radius=r, height=h, segments=12, location=(0.0, 0.0, h * 0.5), mat_index=MAT_INDEX_DRIFTWOOD)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 10. Sea-Monster Beast Skull Prop
# ---------------------------------------------------------------------------

def build_hajfin_beast_skull_prop(bm, x, y, z_ground=0.0, ang=0.0, scale=1.0):
    """
    Menacing carved Hajfin shark / sea monster skull with jagged jaws from artist's Skull.fbx.
    """
    faces = _stamp_meshdata(bm, 'hajfin_skull', 0.0, 0.0, 0.0, scale=scale, anchor='BASE', default_mat=MAT_INDEX_BONE)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 11. Beast Skull Totem Post
# ---------------------------------------------------------------------------

def build_skull_totem_post(bm, x, y, z_ground=0.0, ang=0.0, height=2.8, scale=1.0):
    """
    Tribal carved timber post impaled with a massive sea-monster beast skull.
    """
    faces = []
    post_r = 0.16 * scale
    faces += create_cylinder(bm, radius=post_r, height=height, segments=8,
                             location=(0.0, 0.0, height * 0.5), mat_index=MAT_INDEX_TIMBER)
    # Rope coils
    for rz in (0.6 * scale, 1.2 * scale, height * 0.65):
        faces += create_cylinder(bm, radius=post_r + 0.035 * scale, height=0.15 * scale, segments=10,
                                 location=(0.0, 0.0, rz), mat_index=MAT_INDEX_ROPE)
    # Cross arms
    faces += create_box(bm, (0.75 * scale, 0.12 * scale, 0.14 * scale),
                        (0.0, 0.0, height * 0.65), mat_index=MAT_INDEX_TIMBER)
    # Skull impaled at top
    sk_z = height - 0.08 * scale
    faces += _stamp_meshdata(bm, 'hajfin_skull', 0.0, 0.0, sk_z, scale=1.05 * scale, anchor='CENTER', default_mat=MAT_INDEX_BONE)
    # Spike tip protruding out top
    faces += create_cone(bm, radius1=0.08 * scale, radius2=0.02 * scale, height=0.48 * scale, segments=8,
                         location=(0.0, 0.0, sk_z + 0.32 * scale), mat_index=MAT_INDEX_TIMBER)

    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces


# ---------------------------------------------------------------------------
# 12. Heavy Timber Cargo Crate
# ---------------------------------------------------------------------------

def build_single_hajfin_crate(bm, x, y, z_ground=0.0, ang=0.0, scale=0.75):
    """
    Weathered heavy timber cargo crate with iron/timber framing from artist's Crate.fbx.
    """
    faces = _stamp_meshdata(bm, 'hajfin_crate', 0.0, 0.0, 0.0, scale=scale, anchor='BASE', default_mat=MAT_INDEX_DRIFTWOOD)
    if not faces:
        sz = 1.20 * scale
        faces = create_box(bm, (sz, sz, sz), (0.0, 0.0, sz * 0.5), mat_index=MAT_INDEX_TIMBER)
    transform_faces(faces, _place(x, y, z_ground, ang))
    return faces
