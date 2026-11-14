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
    create_spiral_rope_coil,
    create_box, create_beveled_box, create_cylinder, create_cone,
    create_torus_ring, create_oriented_beam, transform_faces
)
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON,
    MAT_INDEX_ROPE, MAT_INDEX_FISH,
    MAT_INDEX_BONE, MAT_INDEX_DRIFTWOOD, MAT_INDEX_ROUGH_STONE,
    MAT_INDEX_SILVER, MAT_INDEX_FLOOR, MAT_INDEX_LEATHER, MAT_INDEX_FABRIC_WHITE,
    MAT_INDEX_LANTERN
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
    base = Matrix.Translation((-cx, -cy, -cz))
    M_rot = rot @ s_mat @ base

    if anchor == 'BASE':
        min_post_z = min((M_rot @ Vector(v))[2] for v in verts)
        trans = Matrix.Translation((x, y, z - min_post_z + 0.005))
    else:
        trans = Matrix.Translation((x, y, z))
    M = trans @ M_rot

    uv_layer = bm.loops.layers.uv.verify()
    prop_layer = bm.faces.layers.int.get('bbc_is_prop')
    if prop_layer is None:
        prop_layer = bm.faces.layers.int.new('bbc_is_prop')
    imported_layer = bm.faces.layers.int.get('bbc_imported_asset')
    if imported_layer is None:
        imported_layer = bm.faces.layers.int.new('bbc_imported_asset')
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
        f[prop_layer] = 1
        f[imported_layer] = 1
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
    # Skull impaled at top (scaled up for imposing beast proportions)
    sk_z = height - 0.15 * scale
    faces += _stamp_meshdata(bm, 'hajfin_skull', 0.0, 0.0, sk_z, scale=2.1 * scale, anchor='CENTER', default_mat=MAT_INDEX_BONE)
    # Spike tip protruding out top
    faces += create_cone(bm, radius1=0.10 * scale, radius2=0.02 * scale, height=0.65 * scale, segments=8,
                         location=(0.0, 0.0, sk_z + 0.72 * scale), mat_index=MAT_INDEX_TIMBER)

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


# ---------------------------------------------------------------------------
# 13. Admiralty Ship Anchor (Booty Bay Nautical Feature)
# ---------------------------------------------------------------------------

def _build_rope_tube(bm, points, radius=0.03, sides=8, mat_index=None,
                     u_tiles=1.0, v_per_metre=3.0):
    """Continuous, smooth rope tube through a list of 3D points.

    A single welded tube (instead of a chain of little beam boxes) reads as one
    solid hawser, and getting the UVs right matters: U wraps around the tube
    cross-section while V runs along its length, which is what makes the hemp
    twist sit at the correct scale instead of smearing.
    """
    if mat_index is None:
        mat_index = MAT_INDEX_ROPE
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return
    uv_layer = bm.loops.layers.uv.verify()
    up_ref = Vector((0.0, 0.0, 1.0))
    rings = []
    travelled = 0.0

    for idx, p in enumerate(pts):
        if idx == 0:
            tangent = (pts[1] - pts[0])
        elif idx == len(pts) - 1:
            tangent = (pts[-1] - pts[-2])
        else:
            tangent = (pts[idx + 1] - pts[idx - 1])
        if tangent.length < 1e-6:
            tangent = Vector((0.0, 0.0, 1.0))
        tangent.normalize()

        ref = up_ref if abs(tangent.dot(up_ref)) < 0.95 else Vector((1.0, 0.0, 0.0))
        n1 = tangent.cross(ref).normalized()
        n2 = tangent.cross(n1).normalized()

        if idx > 0:
            travelled += (p - pts[idx - 1]).length

        ring = []
        for k in range(sides):
            ang = 2.0 * math.pi * k / sides
            off = n1 * (math.cos(ang) * radius) + n2 * (math.sin(ang) * radius)
            ring.append(bm.verts.new(p + off))
        rings.append(ring)

    seg_len = 1.0 / max(len(pts) - 1, 1)
    for i in range(len(rings) - 1):
        v0 = (i * seg_len) * (v_per_metre * (pts[-1] - pts[0]).length)
        v1 = ((i + 1) * seg_len) * (v_per_metre * (pts[-1] - pts[0]).length)
        for k in range(sides):
            kn = (k + 1) % sides
            f = bm.faces.new([rings[i][k], rings[i + 1][k], rings[i + 1][kn], rings[i][kn]])
            f.material_index = mat_index
            f.tag = True
            u0 = (k / float(sides)) * u_tiles
            u1 = ((k + 1) / float(sides)) * u_tiles
            f.loops[0][uv_layer].uv = Vector((u0, v0))
            f.loops[1][uv_layer].uv = Vector((u0, v1))
            f.loops[2][uv_layer].uv = Vector((u1, v1))
            f.loops[3][uv_layer].uv = Vector((u1, v0))

    # Simple end caps
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        try:
            f = bm.faces.new(list(reversed(ring)) if flip else list(ring))
            f.material_index = mat_index
            f.tag = True
        except ValueError:
            pass


def build_ship_anchor(bm, x=0.0, y=0.0, z_ground=0.0, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0):
    """
    Beautiful handcrafted Admiralty ship anchor:
    - Central tapered rectangular iron shank with forged eyelet at top
    - Shackle ring passing through the eyelet in the YZ plane
    - Tapered cross-stock with end spheres and mounting collars
    - Solid crown transitioning smoothly into curved forged arms
    - Broad, pointed triangular flukes seamlessly welded to arm ends
    - Authentic nautical hawser rope knotted through the top ring, spiraling
      gracefully down the shank, and pooling in a rope coil at the base.
    """
    rot = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'Y') @ Matrix.Rotation(roll, 4, 'X')
    trans = Matrix.Translation((x, y, z_ground))
    M = trans @ rot @ Matrix.Diagonal((scale, scale, scale, 1.0))
    uv_layer = bm.loops.layers.uv.verify()

    def _uv(faces, texel=0.75):
        """Planar-projected UVs so the forged iron texture tiles correctly on the
        anchor instead of collapsing to a single texel (which read as flat grey)."""
        for f in faces:
            f.normal_update()
            n = f.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            for loop in f.loops:
                c = loop.vert.co
                if az >= ax and az >= ay:
                    u, v = c.x * texel, c.y * texel
                elif ax >= ay:
                    u, v = c.y * texel, c.z * texel
                else:
                    u, v = c.x * texel, c.z * texel
                loop[uv_layer].uv = Vector((u, v))

    def _box(sx, sy, sz, lx, ly, lz, mat):
        v_min = (lx - sx * 0.5, ly - sy * 0.5, lz - sz * 0.5)
        v_max = (lx + sx * 0.5, ly + sy * 0.5, lz + sz * 0.5)
        c = [
            Vector((v_min[0], v_min[1], v_min[2])),
            Vector((v_max[0], v_min[1], v_min[2])),
            Vector((v_max[0], v_max[1], v_min[2])),
            Vector((v_min[0], v_max[1], v_min[2])),
            Vector((v_min[0], v_min[1], v_max[2])),
            Vector((v_max[0], v_min[1], v_max[2])),
            Vector((v_max[0], v_max[1], v_max[2])),
            Vector((v_min[0], v_max[1], v_max[2])),
        ]
        tc = [M @ pt for pt in c]
        verts = [bm.verts.new(pt) for pt in tc]
        faces = [
            bm.faces.new([verts[0], verts[1], verts[2], verts[3]]),
            bm.faces.new([verts[7], verts[6], verts[5], verts[4]]),
            bm.faces.new([verts[0], verts[4], verts[5], verts[1]]),
            bm.faces.new([verts[1], verts[5], verts[6], verts[2]]),
            bm.faces.new([verts[2], verts[6], verts[7], verts[3]]),
            bm.faces.new([verts[3], verts[7], verts[4], verts[0]]),
        ]
        for f in faces:
            f.material_index = mat
            f.tag = True
        _uv(faces)
        return faces

    shank_h = 2.05
    shank_w = 0.18
    shank_d = 0.18

    # 1. Central Iron Shank
    _box(shank_w, shank_d, shank_h, 0.0, 0.0, shank_h * 0.5, MAT_INDEX_IRON)

    # 2. Lower Crown
    crown_h = 0.35
    crown_w = shank_w * 1.5
    crown_d = shank_d * 1.3
    _box(crown_w, crown_d, crown_h, 0.0, 0.0, crown_h * 0.5, MAT_INDEX_IRON)
    create_cylinder(bm, radius=crown_d * 0.65, height=crown_w, segments=8,
                    location=M @ Vector((0.0, 0.0, 0.05)),
                    rotation=(0.0, math.pi * 0.5, 0.0), mat_index=MAT_INDEX_IRON)

    # 3. Curved Arms & Flukes (continuous seamless bridged geometry)
    arm_span = 0.86
    arm_height = 0.92
    num_arm_segs = 8
    arm_r = 0.078

    for sgn_a in (-1.0, 1.0):
        pts = []
        for i in range(num_arm_segs + 1):
            t = i / num_arm_segs
            ang = t * (math.pi * 0.44)
            ax = sgn_a * math.sin(ang) * (arm_span * 1.05)
            az = 0.12 + (1.0 - math.cos(ang)) * arm_height
            pts.append(Vector((ax, 0.0, az)))

        rings = []
        for idx, pt in enumerate(pts):
            if idx == 0:
                tangent = (pts[1] - pts[0]).normalized()
            elif idx == len(pts) - 1:
                tangent = (pts[-1] - pts[-2]).normalized()
            else:
                tangent = (pts[idx + 1] - pts[idx - 1]).normalized()

            normal = Vector((0.0, 1.0, 0.0))
            binormal = tangent.cross(normal).normalized()

            r_scale = 1.0 - 0.20 * (idx / num_arm_segs)
            r_curr = arm_r * r_scale

            ring_verts = []
            for k in range(4):
                ang_r = k * (math.pi * 0.5) + math.pi * 0.25
                cos_a = math.cos(ang_r) * r_curr
                sin_a = math.sin(ang_r) * r_curr
                offset = normal * cos_a + binormal * sin_a
                ring_verts.append(bm.verts.new(M @ (pt + offset)))
            rings.append(ring_verts)

        for i in range(len(rings) - 1):
            r0 = rings[i]
            r1 = rings[i + 1]
            for k in range(4):
                kn = (k + 1) % 4
                f = bm.faces.new([r0[k], r1[k], r1[kn], r0[kn]])
                f.material_index = MAT_INDEX_IRON
                f.tag = True
                _uv([f])

        tip_pt = pts[-1]
        tip_tangent = (pts[-1] - pts[-2]).normalized()
        fluke_len = 0.52
        fluke_w = 0.38

        p_fluke_tip = tip_pt + tip_tangent * fluke_len + Vector((-sgn_a * 0.06, 0.0, 0.0))
        wing_fwd = tip_tangent * (fluke_len * 0.35)
        p_fluke_l = tip_pt + wing_fwd + Vector((0.0, -fluke_w * 0.5, 0.0))
        p_fluke_r = tip_pt + wing_fwd + Vector((0.0, fluke_w * 0.5, 0.0))

        v_ftip = bm.verts.new(M @ p_fluke_tip)
        v_fl = bm.verts.new(M @ p_fluke_l)
        v_fr = bm.verts.new(M @ p_fluke_r)

        r_last = rings[-1]
        for tri in (
            [r_last[0], r_last[1], v_fl],
            [r_last[1], v_ftip, v_fl],
            [r_last[2], r_last[3], v_fr],
            [r_last[3], v_fr, v_ftip],
            [r_last[1], r_last[2], v_ftip],
            [r_last[0], v_fl, r_last[3]],
            [r_last[3], v_fl, v_ftip],
            [r_last[3], v_ftip, v_fr],
        ):
            try:
                f = bm.faces.new(tri)
                f.material_index = MAT_INDEX_IRON
                f.tag = True
                _uv([f])
            except ValueError:
                pass

    # 4. Cross-Stock
    stock_z = shank_h - 0.36
    stock_len = 1.62
    stock_w = 0.13
    stock_d = 0.13
    p_st_a = M @ Vector((0.0, -stock_len * 0.5, stock_z))
    p_st_b = M @ Vector((0.0, stock_len * 0.5, stock_z))
    create_oriented_beam(bm, p_st_a, p_st_b, width=stock_w * scale, depth=stock_d * scale, mat_index=MAT_INDEX_IRON)

    for sgn_s in (-1.0, 1.0):
        ball_pos = M @ Vector((0.0, sgn_s * (stock_len * 0.5 + 0.07), stock_z))
        create_cylinder(bm, radius=0.10 * scale, height=0.14 * scale, segments=8,
                        location=ball_pos, rotation=(math.pi * 0.5, 0.0, 0.0), mat_index=MAT_INDEX_IRON)
        _box(shank_w * 1.35, shank_d * 1.35, 0.14, 0.0, 0.0, stock_z, MAT_INDEX_IRON)

    # 5. Top Eyelet & Shackle Ring
    eye_z = shank_h + 0.08
    _box(shank_w * 1.3, shank_d * 1.2, 0.22, 0.0, 0.0, eye_z - 0.08, MAT_INDEX_IRON)
    create_torus_ring(bm, location=(0.0, 0.0, eye_z + 0.14), rotation=(math.pi * 0.5, 0.0, 0.0),
                      major_radius=0.20 * scale, minor_radius=0.040 * scale,
                      major_segments=16, minor_segments=8, mat_index=MAT_INDEX_IRON,
                      transform_matrix=M)

    # 6. Natural Nautical Hawser Rope spiraling down the shank
    num_rope_turns = 5.0
    rope_z_top = stock_z - 0.12
    rope_z_bot = 0.10
    rope_pts_count = 110
    rope_r = (shank_w * 0.75 + 0.030)

    spiral_pts = []
    for i in range(rope_pts_count + 1):
        t = i / float(rope_pts_count)
        rz = rope_z_top * (1.0 - t) + rope_z_bot * t
        ang = t * (math.pi * 2.0 * num_rope_turns)
        rx = math.cos(ang) * rope_r
        ry = math.sin(ang) * rope_r
        spiral_pts.append(M @ Vector((rx, ry, rz)))

    _build_rope_tube(bm, spiral_pts, radius=0.030 * scale, sides=8,
                     mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=9.0)

    # Loose hawser coiled on the deck at the foot of the anchor
    pool_center = M @ Vector((spiral_pts[-1].x * 0.0 + 0.30 * scale, 0.30 * scale, 0.0))
    create_spiral_rope_coil(
        bm, location=(pool_center.x, pool_center.y, z_ground + 0.012),
        inner_radius=0.075 * scale, outer_radius=0.26 * scale,
        rope_radius=0.030 * scale, turns=2.6, num_steps=72, tube_segments=8,
        mat_index=MAT_INDEX_ROPE,
    )

    return True


# ---------------------------------------------------------------------------
# 14. Salvaged Ship Mast with Crow's Nest & Rigging
# ---------------------------------------------------------------------------

def build_ship_mast_with_crows_nest(bm, x=0.0, y=0.0, z_base=0.0, height=9.5,
                                     mast_radius=0.28, rot_z=0.0,
                                     with_ratlines=True, with_yardarm=True,
                                     with_lantern=True, scale=1.0):
    """
    Salvaged pirate ship mainmast with circular/octagonal crow's nest lookout basket,
    yardarm cross-spar with furled sail canvas bundle, standing rigging shrouds & ratlines,
    iron reinforcement collars, and hanging nautical lantern.
    """
    h = height * scale
    r_bot = mast_radius * scale
    r_top = mast_radius * 0.68 * scale
    M_base = Matrix.Translation((x, y, z_base)) @ Matrix.Rotation(rot_z, 4, 'Z')

    # 1. Main Tapered Timber Mast
    create_cone(bm, radius1=r_bot, radius2=r_top, height=h, segments=10,
                location=M_base @ Vector((0.0, 0.0, h * 0.5)), mat_index=MAT_INDEX_TIMBER)

    # Iron reinforcement bands at intervals
    for r_frac in (0.22, 0.45, 0.68, 0.88):
        bz = h * r_frac
        curr_r = r_bot + (r_top - r_bot) * r_frac
        create_cylinder(bm, radius=curr_r + 0.03 * scale, height=0.14 * scale, segments=10,
                        location=M_base @ Vector((0.0, 0.0, bz)), mat_index=MAT_INDEX_IRON)

    # 2. Topmast Trestletrees & Crow's Nest Platform
    nest_z = h * 0.76
    nest_r = 1.15 * scale  # outer radius of crow's nest (~2.3m diameter)
    nest_h = 1.05 * scale  # basket height

    # Under-floor heavy cross timbers (trestletrees)
    t_len = nest_r * 2.15
    create_box(bm, (t_len, 0.22 * scale, 0.20 * scale),
               M_base @ Vector((0.0, 0.0, nest_z - 0.10 * scale)), mat_index=MAT_INDEX_TIMBER)
    create_box(bm, (0.22 * scale, t_len, 0.20 * scale),
               M_base @ Vector((0.0, 0.0, nest_z - 0.10 * scale)), mat_index=MAT_INDEX_TIMBER)

    # 4 Diagonal knee struts (hounds) supporting platform floor from mast
    strut_bot_z = nest_z - 1.30 * scale
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p_strut_bot = M_base @ Vector((sx * 0.12 * scale, sy * 0.12 * scale, strut_bot_z))
        # Land the strut head inside the trestle beams / floor slab so the brace is
        # visibly carrying the platform instead of stopping just short of it.
        p_strut_top = M_base @ Vector((sx * (nest_r * 0.72), sy * (nest_r * 0.72), nest_z + 0.03 * scale))
        create_oriented_beam(bm, p_strut_bot, p_strut_top, width=0.16 * scale, depth=0.16 * scale, mat_index=MAT_INDEX_TIMBER)

    # Crow's Nest Floor Slab (thick octagonal timber floor)
    create_cylinder(bm, radius=nest_r, height=0.14 * scale, segments=12,
                    location=M_base @ Vector((0.0, 0.0, nest_z + 0.07 * scale)), mat_index=MAT_INDEX_FLOOR)

    # Crow's Nest Basket Balustrade: 12 vertical timber staves
    num_staves = 12
    stave_h = nest_h
    for i in range(num_staves):
        ang = (2.0 * math.pi * i) / num_staves
        cx = math.cos(ang) * (nest_r - 0.08 * scale)
        cy = math.sin(ang) * (nest_r - 0.08 * scale)
        p_stave = M_base @ Vector((cx, cy, nest_z + 0.07 * scale + stave_h * 0.5))
        create_box(bm, (0.16 * scale, 0.08 * scale, stave_h), p_stave, mat_index=MAT_INDEX_TIMBER)

    # Basket Heavy Top Rail Rim (torus)
    create_torus_ring(bm, location=(0.0, 0.0, nest_z + 0.07 * scale + stave_h),
                      major_radius=nest_r - 0.08 * scale, minor_radius=0.065 * scale,
                      major_segments=16, minor_segments=8, mat_index=MAT_INDEX_TIMBER,
                      transform_matrix=M_base)

    # Iron rim bands around outer basket
    create_torus_ring(bm, location=(0.0, 0.0, nest_z + 0.25 * scale),
                      major_radius=nest_r - 0.04 * scale, minor_radius=0.035 * scale,
                      major_segments=16, minor_segments=6, mat_index=MAT_INDEX_IRON,
                      transform_matrix=M_base)
    create_torus_ring(bm, location=(0.0, 0.0, nest_z + stave_h * 0.75),
                      major_radius=nest_r - 0.04 * scale, minor_radius=0.035 * scale,
                      major_segments=16, minor_segments=6, mat_index=MAT_INDEX_IRON,
                      transform_matrix=M_base)

    # 3. Horizontal Yardarm Cross-Spar with Furled Sail Canvas Bundle
    if with_yardarm:
        yard_z = nest_z - 0.40 * scale
        yard_span = 5.2 * scale
        p_yard_l = M_base @ Vector((-yard_span * 0.5, 0.0, yard_z))
        p_yard_r = M_base @ Vector((yard_span * 0.5, 0.0, yard_z))
        create_oriented_beam(bm, p_yard_l, p_yard_r, width=0.20 * scale, depth=0.20 * scale, mat_index=MAT_INDEX_TIMBER)

        # Furled sail bundle of white canvas, slung directly under the yardarm so
        # the lashings grab both the spar and the bundle.
        sail_len = yard_span * 0.84
        sail_r = 0.20 * scale
        sail_z = yard_z - 0.26 * scale
        # Built through M_base so the roll's axis follows the yardarm's yaw, and
        # shaded smooth so the canvas reads as a rounded bundle.
        create_cylinder(bm, radius=sail_r, height=sail_len, segments=18,
                        location=(0.0, 0.0, sail_z),
                        rotation=(0.0, math.pi * 0.5, 0.0),
                        mat_index=MAT_INDEX_FABRIC_WHITE,
                        transform_matrix=M_base, smooth=True)

        # Rope gaskets lashed around BOTH the yardarm and the furled canvas
        gasket_z = (yard_z + sail_z) * 0.5
        gasket_r = math.hypot(0.10 * scale, (yard_z - gasket_z)) + 0.12 * scale
        for sx in (-0.40, -0.24, -0.08, 0.08, 0.24, 0.40):
            create_torus_ring(bm, location=(sx * yard_span, 0.0, gasket_z),
                              rotation=(0.0, math.pi * 0.5, 0.0),
                              major_radius=gasket_r, minor_radius=0.026 * scale,
                              major_segments=14, minor_segments=6,
                              mat_index=MAT_INDEX_ROPE, transform_matrix=M_base)

        # Lift line halyards from yardarm tips to masthead
        mast_truck_p = M_base @ Vector((0.0, 0.0, h - 0.15 * scale))
        _build_rope_tube(bm, [p_yard_l, mast_truck_p], radius=0.022 * scale, sides=6,
                         mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=16.0)
        _build_rope_tube(bm, [p_yard_r, mast_truck_p], radius=0.022 * scale, sides=6,
                         mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=16.0)

        # 4. Hanging Nautical Lantern swinging from yardarm end
        if with_lantern:
            p_lant_hook = M_base @ Vector((yard_span * 0.44, 0.0, yard_z - 0.10 * scale))
            p_lant_drop = M_base @ Vector((yard_span * 0.44, 0.0, yard_z - 0.65 * scale))
            _build_rope_tube(bm, [p_lant_hook, p_lant_drop], radius=0.017 * scale, sides=6,
                             mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=16.0)
            create_box(bm, (0.24 * scale, 0.24 * scale, 0.34 * scale),
                       M_base @ Vector((yard_span * 0.44, 0.0, yard_z - 0.82 * scale)), mat_index=MAT_INDEX_IRON)
            create_box(bm, (0.16 * scale, 0.16 * scale, 0.22 * scale),
                       M_base @ Vector((yard_span * 0.44, 0.0, yard_z - 0.82 * scale)), mat_index=MAT_INDEX_LANTERN)

    # 5. Shrouds and Ratlines (Climbing Rope Ladder)
    if with_ratlines:
        spread_x = 1.35 * scale
        spread_y = 0.55 * scale
        shroud_top_l = M_base @ Vector((-spread_x * 0.4, 0.0, nest_z))
        shroud_top_r = M_base @ Vector((spread_x * 0.4, 0.0, nest_z))
        shroud_bot_l = M_base @ Vector((-spread_x, -spread_y, 0.0))
        shroud_bot_r = M_base @ Vector((spread_x, -spread_y, 0.0))

        _build_rope_tube(bm, [shroud_bot_l, shroud_top_l], radius=0.030 * scale, sides=6,
                         mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=13.0)
        _build_rope_tube(bm, [shroud_bot_r, shroud_top_r], radius=0.030 * scale, sides=6,
                         mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=13.0)

        num_rungs = max(4, int(nest_z / (0.38 * scale)))
        for i in range(1, num_rungs):
            t = i / num_rungs
            p_rung_l = shroud_bot_l.lerp(shroud_top_l, t)
            p_rung_r = shroud_bot_r.lerp(shroud_top_r, t)
            _build_rope_tube(bm, [p_rung_l, p_rung_r], radius=0.019 * scale, sides=6,
                             mat_index=MAT_INDEX_ROPE, u_tiles=1.0, v_per_metre=15.0)

    # 6. Masthead Truck & Finial
    create_cylinder(bm, radius=r_top * 1.3, height=0.18 * scale, segments=10,
                    location=M_base @ Vector((0.0, 0.0, h + 0.09 * scale)), mat_index=MAT_INDEX_TIMBER)
    create_cone(bm, radius1=r_top * 0.9, radius2=0.02 * scale, height=0.45 * scale, segments=8,
                location=M_base @ Vector((0.0, 0.0, h + 0.40 * scale)), mat_index=MAT_INDEX_BONE)

    return True


# ---------------------------------------------------------------------------
# 15. Suspended Catenary Rope Bridge (Booty Bay Walkway)
# ---------------------------------------------------------------------------

def build_suspended_rope_bridge(bm, p0, p1, width=1.35, sag=0.45,
                                plank_spacing=0.28, plank_width=0.22,
                                plank_th=0.08, with_pylons=True,
                                post_height=1.35, mat_planks=MAT_INDEX_FLOOR,
                                mat_rope=MAT_INDEX_ROPE, mat_pylons=MAT_INDEX_TIMBER):
    """
    World of Warcraft / Booty Bay style authentic suspended catenary rope bridge:
    - Sagging catenary curve between endpoints p0 and p1
    - Heavy under-deck dual suspension cables
    - Handcrafted weathered timber walkway planks with organic angle and width jitter
    - Upper rope handrails suspended above deck
    - Vertical rope hanger drops connecting handrails to deck cables
    - Stout bridgehead anchor timber pylons with wrapped rope lashings
    """
    v0 = Vector(p0)
    v1 = Vector(p1)
    span_v = v1 - v0
    L = span_v.length
    if L < 0.6:
        return False

    fwd_h = Vector((span_v.x, span_v.y, 0.0))
    if fwd_h.length < 1e-4:
        right = Vector((1.0, 0.0, 0.0))
    else:
        fwd_norm = fwd_h.normalized()
        right = Vector((-fwd_norm.y, fwd_norm.x, 0.0))

    def _cat_pt(t):
        p_lin = v0.lerp(v1, t)
        sag_z = -4.0 * sag * t * (1.0 - t)
        return p_lin + Vector((0.0, 0.0, sag_z))

    # 1. Main Under-Deck Suspension Ropes (Left and Right)
    cable_r_off = width * 0.44
    cable_z_off = -plank_th * 0.5 - 0.04
    num_cable_segs = max(12, int(L / 0.45))

    for sgn_side in (-1.0, 1.0):
        path = []
        for i in range(num_cable_segs + 1):
            t = i / num_cable_segs
            path.append(_cat_pt(t) + right * (sgn_side * cable_r_off) + Vector((0.0, 0.0, cable_z_off)))
        _build_rope_tube(bm, path, radius=0.038, sides=6, mat_index=mat_rope,
                         u_tiles=1.0, v_per_metre=12.0)

    # 2. Weathered Timber Walkway Planks
    uv_layer_planks = bm.loops.layers.uv.verify()
    num_planks = max(4, int(L / plank_spacing))
    for i in range(num_planks + 1):
        t = i / num_planks
        p_c = _cat_pt(t)

        d_sag_dt = -4.0 * sag * (1.0 - 2.0 * t)
        tan_v = (span_v + Vector((0.0, 0.0, d_sag_dt))).normalized()

        jitter_yaw = ((i * 137.5) % 8.0 - 4.0) * (math.pi / 180.0)
        p_width = width * (0.92 + 0.16 * ((i * 73.1) % 1.0))
        p_len = plank_width * (0.85 + 0.30 * ((i * 41.3) % 1.0))

        cos_j = math.cos(jitter_yaw)
        sin_j = math.sin(jitter_yaw)
        p_right = (right * cos_j + tan_v * sin_j).normalized()
        p_tan = (tan_v * cos_j - right * sin_j).normalized()
        p_up = p_right.cross(p_tan).normalized()

        M_plank = Matrix((
            [p_right.x, p_tan.x, p_up.x, p_c.x],
            [p_right.y, p_tan.y, p_up.y, p_c.y],
            [p_right.z, p_tan.z, p_up.z, p_c.z],
            [0.0,       0.0,     0.0,    1.0  ]
        ))
        plank_faces = create_box(bm, (p_width, p_len, plank_th), (0.0, 0.0, 0.0), mat_index=mat_planks)
        # Map each board to exactly ONE plank band of the deck atlas, and slide it
        # along the atlas per board so no two planks are carbon copies.
        # Sample a small patch out of the middle of the deck atlas: each board gets
        # a single plank face with the grain running along its length, and a
        # per-board U slide keeps them from being carbon copies.
        v_base = 0.44
        v_span = 0.10
        u_off = ((i * 0.37) % 0.72)
        u_len = 0.15
        for f in plank_faces:
            fn = f.normal
            for loop in f.loops:
                lc = loop.vert.co
                if abs(fn.z) > 0.5:
                    u = 0.05 + u_off + (lc.y / p_len + 0.5) * u_len
                    v = v_base + (lc.x / p_width + 0.5) * v_span
                elif abs(fn.x) >= abs(fn.y):
                    u = 0.05 + u_off + (lc.y / p_len + 0.5) * u_len
                    v = v_base + (lc.z / plank_th + 0.5) * v_span
                else:
                    u = 0.05 + u_off + (lc.x / p_width + 0.5) * u_len
                    v = v_base + (lc.z / plank_th + 0.5) * v_span
                loop[uv_layer_planks].uv = Vector((u, v))
        transform_faces(plank_faces, M_plank)

    # 3. Suspended Rope Handrails (running post_height above deck)
    rail_r_off = width * 0.50
    rail_z_off = post_height

    for sgn_side in (-1.0, 1.0):
        path = []
        for i in range(num_cable_segs + 1):
            t = i / num_cable_segs
            path.append(_cat_pt(t) + right * (sgn_side * rail_r_off) + Vector((0.0, 0.0, rail_z_off)))
        _build_rope_tube(bm, path, radius=0.033, sides=6, mat_index=mat_rope,
                         u_tiles=1.0, v_per_metre=12.0)

    # 4. Vertical Rope Hanger Drops
    num_hangers = max(3, int(L / 0.65))
    for i in range(1, num_hangers):
        t = i / num_hangers
        p_base = _cat_pt(t)
        for sgn_side in (-1.0, 1.0):
            p_top = p_base + right * (sgn_side * rail_r_off) + Vector((0.0, 0.0, rail_z_off))
            p_bot = p_base + right * (sgn_side * cable_r_off) + Vector((0.0, 0.0, cable_z_off))
            _build_rope_tube(bm, [p_bot, p_top], radius=0.022, sides=6, mat_index=mat_rope,
                             u_tiles=1.0, v_per_metre=14.0)

    # 5. Stout Bridgehead Anchor Pylons (flanking the walkway entrance, open clearance!)
    if with_pylons:
        pylon_r = 0.16
        for ep in (v0, v1):
            for sgn_side in (-1.0, 1.0):
                # Stand the pylons ON the deck instead of driving them through it
                p_pylon_bot = ep + right * (sgn_side * (width * 0.54)) - Vector((0.0, 0.0, 0.05))
                p_pylon_top = ep + right * (sgn_side * (width * 0.54)) + Vector((0.0, 0.0, post_height + 0.15))
                create_oriented_beam(bm, p_pylon_bot, p_pylon_top, width=pylon_r * 2, depth=pylon_r * 2, mat_index=mat_pylons)
                # Rope lashing coil around top of post
                create_torus_ring(bm, location=ep + right * (sgn_side * (width * 0.54)) + Vector((0.0, 0.0, post_height)),
                                  major_radius=pylon_r + 0.03, minor_radius=0.028, mat_index=mat_rope)
                # Beveled timber post cap
                create_cone(bm, radius1=pylon_r * 1.15, radius2=0.04, height=0.22, segments=8,
                            location=ep + right * (sgn_side * (width * 0.54)) + Vector((0.0, 0.0, post_height + 0.22)),
                            mat_index=mat_pylons)

    return True

