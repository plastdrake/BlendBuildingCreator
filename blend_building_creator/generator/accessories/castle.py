"""
Castle Citadel Generator for BlendBuildingCreator.

Procedurally constructs authentic fantasy fortress castle architecture:
1. Four Colossal Cylindrical Corner Drum Towers with stepped cut-stone plinths,
   machicolation galleries, crenellated stone battlements, cross arrow slits,
   and soaring conical witch-hat spire roofs with iron finials and pennant flags.
2. Dominant Central Citadel Keep rising high above the main hall roof ridge,
   crowned with a grand machicolation gallery, 4-dormer conical spire, and royal standard.
3. Corbelled Round Bartizans (Tourelles / Hanging Corner Turrets) on upper wall
   junctions and roof eaves.
4. Royal Portal Portico & Loggia: massive round columns, carved capitals, moulded
   gothic entrance arch, stepped cut-stone approach stairs, and royal balustraded loggia.
5. Wall-Head Machicolation Friezes: continuous carved stone corbel brackets under the eaves.
"""

import math
from mathutils import Vector, Matrix, Euler

from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone
)
from ..uv_utils import apply_roof_shingle_uvs
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_SHINGLES, MAT_INDEX_IRON,
    MAT_INDEX_GLASS, MAT_INDEX_FLOOR
)
from .banner import build_banner_pole


def _build_cross_arrow_slit(bm, cx, cy, cz, normal_angle, radius):
    """Cut-stone cross arrow-slit loophole fixture projecting slightly from the tower shaft."""
    ca, sa = math.cos(normal_angle), math.sin(normal_angle)
    # Wall face position
    fx = cx + radius * ca
    fy = cy + radius * sa
    
    # Outer cut-stone frame
    create_beveled_box(
        bm, size=(0.72, 0.22, 1.45),
        location=(fx + ca * 0.05, fy + sa * 0.05, cz),
        rotation=(0.0, 0.0, normal_angle + math.pi * 0.5),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015
    )
    # Recessed dark iron / stone backing for vertical slit
    create_box(
        bm, size=(0.14, 0.26, 1.15),
        location=(fx + ca * 0.08, fy + sa * 0.08, cz),
        rotation=(0.0, 0.0, normal_angle + math.pi * 0.5),
        mat_index=MAT_INDEX_IRON
    )
    # Horizontal cross bar slit
    create_box(
        bm, size=(0.48, 0.26, 0.14),
        location=(fx + ca * 0.08, fy + sa * 0.08, cz + 0.15),
        rotation=(0.0, 0.0, normal_angle + math.pi * 0.5),
        mat_index=MAT_INDEX_IRON
    )


def _build_gothic_tower_window(bm, cx, cy, cz, normal_angle, radius):
    """Deeply embrasured gothic arched window with cut-stone frame and dark diamond leaded glass."""
    ca, sa = math.cos(normal_angle), math.sin(normal_angle)
    fx = cx + radius * ca
    fy = cy + radius * sa
    ang_z = normal_angle + math.pi * 0.5

    # Molded sill
    create_beveled_box(
        bm, size=(1.10, 0.35, 0.22),
        location=(fx + ca * 0.06, fy + sa * 0.06, cz - 0.95),
        rotation=(0.0, 0.0, ang_z),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    # Cut-stone arch surround
    create_beveled_box(
        bm, size=(1.05, 0.28, 1.85),
        location=(fx + ca * 0.05, fy + sa * 0.05, cz),
        rotation=(0.0, 0.0, ang_z),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    # Recessed leaded glass pane
    create_box(
        bm, size=(0.65, 0.32, 1.45),
        location=(fx + ca * 0.08, fy + sa * 0.08, cz),
        rotation=(0.0, 0.0, ang_z),
        mat_index=MAT_INDEX_GLASS
    )
    # Stone central mullion
    create_box(
        bm, size=(0.10, 0.34, 1.45),
        location=(fx + ca * 0.09, fy + sa * 0.09, cz),
        rotation=(0.0, 0.0, ang_z),
        mat_index=MAT_INDEX_CUT_STONE
    )


def _build_machicolation_gallery(bm, cx, cy, z_base, radius, segments=24, corbel_count=16):
    """
    Carved stone machicolation gallery:
    Projecting stone corbels arrayed radially under an overhanging parapet,
    crowned with crenellated stone battlements (merlons + embrasures).
    """
    gallery_r = radius + 0.65
    corbel_h = 1.10
    
    # 1. Flared transitional ring (conical corbel table)
    create_cone(
        bm, radius1=gallery_r, radius2=radius, height=corbel_h, segments=segments,
        location=(cx, cy, z_base + corbel_h * 0.5),
        rotation=(0.0, math.pi, 0.0), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # 2. Individual heavy stone corbel brackets
    for i in range(corbel_count):
        ang = (2.0 * math.pi * i) / corbel_count
        ca, sa = math.cos(ang), math.sin(ang)
        bracket_r = radius + 0.32
        create_beveled_box(
            bm, size=(0.28, 0.68, corbel_h + 0.15),
            location=(cx + bracket_r * ca, cy + bracket_r * sa, z_base + corbel_h * 0.5),
            rotation=(0.0, 0.0, ang + math.pi * 0.5),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
    
    # 3. Projecting gallery walkway coping slab
    walk_z = z_base + corbel_h
    create_cylinder(
        bm, radius=gallery_r + 0.08, height=0.28, segments=segments,
        location=(cx, cy, walk_z + 0.14), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # 4. Crenellated stone battlement parapet
    parapet_h = 1.15
    parapet_t = 0.30
    parapet_mid_r = gallery_r - parapet_t * 0.5
    merlon_count = corbel_count
    
    # Parapet base solid curb
    curb_h = 0.35
    create_cylinder(
        bm, radius=gallery_r, height=curb_h, segments=segments,
        location=(cx, cy, walk_z + 0.28 + curb_h * 0.5), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # Merlons (alternating teeth)
    merlon_h = parapet_h - curb_h
    for i in range(merlon_count):
        if i % 2 == 0:
            ang = (2.0 * math.pi * i) / merlon_count
            ca, sa = math.cos(ang), math.sin(ang)
            m_width = (2.0 * math.pi * parapet_mid_r / merlon_count) * 0.85
            create_beveled_box(
                bm, size=(m_width, parapet_t, merlon_h),
                location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                          walk_z + 0.28 + curb_h + merlon_h * 0.5),
                rotation=(0.0, 0.0, ang + math.pi * 0.5),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015
            )
            # Merlon pyramidal cap
            create_cone(
                bm, radius1=m_width * 0.55, radius2=0.02, height=0.18, segments=4,
                location=(cx + parapet_mid_r * ca, cy + parapet_mid_r * sa,
                          walk_z + 0.28 + parapet_h + 0.09),
                rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE
            )
            
    return walk_z + 0.28 + parapet_h


def _build_conical_spire(bm, cx, cy, z_base, radius, height, eave_overhang=0.35, segments=28):
    """
    Steep conical witch-hat spire roof with authentic roof shingle UV mapping,
    eave fascia rim, iron needle finial, brass sphere, and pennant flag.
    """
    spire_r = radius + eave_overhang
    half_h = height * 0.5
    
    # Flared eave fascia ring
    create_cylinder(
        bm, radius=spire_r + 0.08, height=0.18, segments=segments,
        location=(cx, cy, z_base + 0.09), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # Conical shingle roof
    roof_faces = create_cone(
        bm, radius1=spire_r, radius2=0.06, height=height, segments=segments,
        location=(cx, cy, z_base + 0.18 + half_h),
        mat_index=MAT_INDEX_SHINGLES
    )
    apply_roof_shingle_uvs(bm, roof_faces)
    
    # Spire apex iron finial
    apex_z = z_base + 0.18 + height
    # Base collar
    create_cylinder(
        bm, radius=0.18, height=0.25, segments=12,
        location=(cx, cy, apex_z + 0.12), mat_index=MAT_INDEX_IRON
    )
    # Polished sphere
    create_cylinder(
        bm, radius=0.16, height=0.22, segments=12,
        location=(cx, cy, apex_z + 0.35), mat_index=MAT_INDEX_CUT_STONE
    )
    # Long needle
    create_cylinder(
        bm, radius=0.035, height=2.20, segments=8,
        location=(cx, cy, apex_z + 0.45 + 1.10), mat_index=MAT_INDEX_IRON
    )
    
    # Heraldic pennant flag flying from needle
    flag_w, flag_h = 1.65, 0.70
    flag_z = apex_z + 1.65
    create_box(
        bm, size=(flag_w, 0.03, flag_h),
        location=(cx + flag_w * 0.5, cy, flag_z),
        mat_index=MAT_INDEX_CUT_STONE  # Heraldic cloth
    )
    # Iron mounting ring
    create_cylinder(
        bm, radius=0.065, height=0.85, segments=8,
        location=(cx, cy, flag_z), mat_index=MAT_INDEX_IRON
    )


def build_castle_drum_tower(bm, cx, cy, z_ground, radius=3.6, shaft_h=23.0, spire_h=10.0,
                            tier='TIER_3', open_angle_range=None, num_floors=4):
    """
    Constructs a monumental cylindrical castle drum tower:
    - Multi-stepped cut-stone foundation plinth
    - Thick ashlar cylindrical shaft with horizontal torus mouldings
    - Multi-tiered arrow-slit loopholes and gothic arched windows
    - Machicolation gallery with crenellated stone battlements
    - Steep conical witch-hat spire roof with needle finial & flag
    """
    # 1. Stepped circular plinth at ground level
    step0_h = 0.50
    step1_h = 0.40
    create_cylinder(
        bm, radius=radius + 0.65, height=step0_h, segments=32,
        location=(cx, cy, z_ground + step0_h * 0.5), mat_index=MAT_INDEX_STONE
    )
    create_cylinder(
        bm, radius=radius + 0.35, height=step1_h, segments=32,
        location=(cx, cy, z_ground + step0_h + step1_h * 0.5), mat_index=MAT_INDEX_CUT_STONE
    )
    shaft_z0 = z_ground + step0_h + step1_h
    actual_shaft_h = shaft_h - (step0_h + step1_h)

    # 2. Cylindrical ashlar stone shaft
    create_cylinder(
        bm, radius=radius, height=actual_shaft_h, segments=32,
        location=(cx, cy, shaft_z0 + actual_shaft_h * 0.5), mat_index=MAT_INDEX_STONE
    )

    # 3. Horizontal decorative torus string courses at floor levels
    floor_step = actual_shaft_h / max(1, num_floors)
    for f in range(1, num_floors):
        fz = shaft_z0 + f * floor_step
        create_cylinder(
            bm, radius=radius + 0.12, height=0.22, segments=32,
            location=(cx, cy, fz), mat_index=MAT_INDEX_CUT_STONE
        )

    # 4. Windows and arrow slits on exposed angles
    angles = [i * (math.pi / 4.0) for i in range(8)]
    if open_angle_range is not None:
        min_a, max_a = open_angle_range
        angles = [a for a in angles if min_a <= a <= max_a]

    for idx, ang in enumerate(angles):
        for f in range(num_floors):
            level_mid = shaft_z0 + (f + 0.5) * floor_step
            if f == 0 or (f + idx) % 2 == 0:
                # Cross arrow slit
                _build_cross_arrow_slit(bm, cx, cy, level_mid, ang, radius)
            else:
                # Gothic arched window
                _build_gothic_tower_window(bm, cx, cy, level_mid, ang, radius)

    # 5. Machicolation Gallery
    gallery_base_z = shaft_z0 + actual_shaft_h - 1.2
    top_z = _build_machicolation_gallery(
        bm, cx, cy, gallery_base_z, radius, segments=32, corbel_count=18
    )

    # 6. Steep Conical Witch-Hat Spire
    _build_conical_spire(
        bm, cx, cy, gallery_base_z + 1.4, radius, spire_h, eave_overhang=0.45, segments=32
    )


def build_castle_central_keep(bm, cx, cy, z_ground, radius=5.2, shaft_h=33.0, spire_h=12.5,
                              num_floors=5):
    """
    Constructs the Colossal Central Citadel Keep (Great Keep / Donjon):
    Soars high above the castle roof ridge, commanding the entire fortress.
    Features massive double-tiered machicolations, multi-storey arched bays,
    and a monumental conical spire crowned with 4 dormer turrets and royal banner.
    """
    # 1. Battered monumental base plinth
    plinth_h = 1.40
    create_cone(
        bm, radius1=radius + 0.90, radius2=radius + 0.15, height=plinth_h, segments=36,
        location=(cx, cy, z_ground + plinth_h * 0.5), mat_index=MAT_INDEX_STONE
    )
    shaft_z0 = z_ground + plinth_h
    actual_shaft_h = shaft_h - plinth_h

    # 2. Main Keep Shaft
    create_cylinder(
        bm, radius=radius, height=actual_shaft_h, segments=36,
        location=(cx, cy, shaft_z0 + actual_shaft_h * 0.5), mat_index=MAT_INDEX_STONE
    )

    # 3. Cut-stone belt courses
    floor_step = actual_shaft_h / max(1, num_floors)
    for f in range(1, num_floors):
        fz = shaft_z0 + f * floor_step
        create_cylinder(
            bm, radius=radius + 0.15, height=0.30, segments=36,
            location=(cx, cy, fz), mat_index=MAT_INDEX_CUT_STONE
        )

    # 4. Loopholes and arched gothic windows around keep
    for ang_idx, ang in enumerate([0.0, math.pi * 0.5, math.pi, math.pi * 1.5]):
        for f in range(1, num_floors):
            level_mid = shaft_z0 + (f + 0.5) * floor_step
            _build_gothic_tower_window(bm, cx, cy, level_mid, ang, radius)

    # 5. Monumental Machicolation Gallery
    gallery_base_z = shaft_z0 + actual_shaft_h - 1.4
    top_z = _build_machicolation_gallery(
        bm, cx, cy, gallery_base_z, radius, segments=36, corbel_count=24
    )

    # 6. Grand Royal Spire
    spire_base = gallery_base_z + 1.6
    spire_faces = create_cone(
        bm, radius1=radius + 0.55, radius2=0.08, height=spire_h, segments=36,
        location=(cx, cy, spire_base + spire_h * 0.5), mat_index=MAT_INDEX_SHINGLES
    )
    apply_roof_shingle_uvs(bm, spire_faces)

    # 7. Four Spire Dormer Turrets
    dormer_r = radius * 0.65
    dormer_h = 2.4
    dormer_w = 1.40
    for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
        ca, sa = math.cos(ang), math.sin(ang)
        dz = spire_base + spire_h * 0.28
        # Dormer body
        create_beveled_box(
            bm, size=(dormer_w, 1.20, dormer_h),
            location=(cx + dormer_r * ca, cy + dormer_r * sa, dz + dormer_h * 0.5),
            rotation=(0.0, 0.0, ang + math.pi * 0.5),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        # Dormer arched louvre
        create_box(
            bm, size=(0.60, 1.25, 1.20),
            location=(cx + (dormer_r + 0.05) * ca, cy + (dormer_r + 0.05) * sa, dz + dormer_h * 0.5),
            rotation=(0.0, 0.0, ang + math.pi * 0.5),
            mat_index=MAT_INDEX_IRON
        )
        # Dormer gable roof
        create_cone(
            bm, radius1=dormer_w * 0.70, radius2=0.02, height=1.35, segments=4,
            location=(cx + dormer_r * ca, cy + dormer_r * sa, dz + dormer_h + 0.68),
            rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_SHINGLES
        )

    # 8. Royal Apex Finial Needle & Silk Banner
    apex_z = spire_base + spire_h
    create_cylinder(
        bm, radius=0.28, height=0.35, segments=16,
        location=(cx, cy, apex_z + 0.17), mat_index=MAT_INDEX_IRON
    )
    create_cylinder(
        bm, radius=0.22, height=0.30, segments=16,
        location=(cx, cy, apex_z + 0.50), mat_index=MAT_INDEX_CUT_STONE
    )
    create_cylinder(
        bm, radius=0.05, height=3.20, segments=8,
        location=(cx, cy, apex_z + 0.65 + 1.60), mat_index=MAT_INDEX_IRON
    )
    # Royal standard
    std_w, std_h = 2.80, 1.20
    std_z = apex_z + 2.20
    create_box(
        bm, size=(std_w, 0.04, std_h),
        location=(cx + std_w * 0.5, cy, std_z), mat_index=MAT_INDEX_CUT_STONE
    )


def build_castle_corbelled_bartizan(bm, cx, cy, z_corbel, radius=1.35, height=4.6, spire_h=4.2):
    """
    Constructs a corbelled hanging corner turret (bartizan / tourelle):
    Projects out from upper wall corners on multi-tiered inverted stone corbel rings.
    """
    # 1. Multi-tiered inverted stone corbel cone
    corbel_h = 1.35
    create_cone(
        bm, radius1=radius + 0.05, radius2=0.15, height=corbel_h, segments=20,
        location=(cx, cy, z_corbel + corbel_h * 0.5), mat_index=MAT_INDEX_CUT_STONE
    )
    # Bottom pendant drop finial
    create_cone(
        bm, radius1=0.18, radius2=0.02, height=0.45, segments=12,
        location=(cx, cy, z_corbel - 0.22), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # 2. Cylindrical turret shaft
    shaft_z0 = z_corbel + corbel_h
    create_cylinder(
        bm, radius=radius, height=height, segments=20,
        location=(cx, cy, shaft_z0 + height * 0.5), mat_index=MAT_INDEX_STONE
    )
    
    # Arrow slits on exposed faces
    for ang in (-math.pi * 0.25, 0.0, math.pi * 0.25):
        _build_cross_arrow_slit(bm, cx, cy, shaft_z0 + height * 0.5, ang, radius)
        
    # 3. Flared cornice & mini battlements
    cornice_z = shaft_z0 + height
    create_cylinder(
        bm, radius=radius + 0.25, height=0.22, segments=20,
        location=(cx, cy, cornice_z + 0.11), mat_index=MAT_INDEX_CUT_STONE
    )
    
    # 4. Steep conical roof
    roof_faces = create_cone(
        bm, radius1=radius + 0.28, radius2=0.03, height=spire_h, segments=20,
        location=(cx, cy, cornice_z + 0.22 + spire_h * 0.5), mat_index=MAT_INDEX_SHINGLES
    )
    apply_roof_shingle_uvs(bm, roof_faces)
    
    # Finial
    apex_z = cornice_z + 0.22 + spire_h
    create_cylinder(
        bm, radius=0.025, height=1.10, segments=6,
        location=(cx, cy, apex_z + 0.55), mat_index=MAT_INDEX_IRON
    )


def build_castle_portal_loggia(bm, cx, cy, z_ground, width=7.2, depth=3.6, height=5.2):
    """
    Constructs the Grand Royal Entrance Portico & Loggia:
    - Monumental twin cylindrical columns with carved Corinthian capitals
    - Deep moulded cut-stone gothic entrance arch
    - Stepped approach stairs descending into the courtyard
    - Royal viewing loggia / terrace with pierced stone balustrade
    """
    col_r = 0.44
    col_spacing = 3.6
    
    # 1. Stepped approach stone staircase
    n_steps = 5
    stair_w = width + 1.2
    for s in range(n_steps):
        sz = (s + 0.5) * 0.18
        s_depth = depth + (n_steps - s) * 0.40
        create_beveled_box(
            bm, size=(stair_w - s * 0.20, s_depth, 0.18),
            location=(cx, cy - s_depth * 0.5, sz),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
        
    # 2. Twin monumental stone columns flanking portal
    for sgn in (-1.0, 1.0):
        px = cx + sgn * (col_spacing * 0.5)
        py = cy - depth * 0.5
        # Column base plinth
        create_beveled_box(
            bm, size=(1.10, 1.10, 0.45),
            location=(px, py, z_ground + 0.225),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03
        )
        # Column shaft
        col_h = height - 1.10
        create_cylinder(
            bm, radius=col_r, height=col_h, segments=24,
            location=(px, py, z_ground + 0.45 + col_h * 0.5),
            mat_index=MAT_INDEX_CUT_STONE
        )
        # Carved capital
        create_beveled_box(
            bm, size=(1.15, 1.15, 0.45),
            location=(px, py, z_ground + 0.45 + col_h + 0.225),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.04
        )
        
    # 3. Arch lintel band and moulded gothic portal arch
    arch_z = z_ground + height - 0.20
    create_beveled_box(
        bm, size=(col_spacing + 1.8, 0.85, 0.65),
        location=(cx, cy - depth * 0.5, arch_z + 0.325),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03
    )
    
    # 4. Upper Royal Loggia Terrace Deck
    deck_z = arch_z + 0.65
    create_beveled_box(
        bm, size=(width + 0.6, depth + 0.4, 0.35),
        location=(cx, cy - depth * 0.25, deck_z + 0.175),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    
    # 5. Cut-stone balustrade around terrace
    bal_h = 1.10
    # Front balustrade run
    create_beveled_box(
        bm, size=(width + 0.6, 0.24, bal_h),
        location=(cx, cy - depth * 0.45, deck_z + 0.35 + bal_h * 0.5),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )
    # Side balustrade runs
    for sgn in (-1.0, 1.0):
        create_beveled_box(
            bm, size=(0.24, depth * 0.7, bal_h),
            location=(cx + sgn * (width * 0.5 + 0.18), cy - depth * 0.10, deck_z + 0.35 + bal_h * 0.5),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
        )
    # Pier finials on front corners
    for sgn in (-1.0, 1.0):
        create_cone(
            bm, radius1=0.24, radius2=0.02, height=0.45, segments=4,
            location=(cx + sgn * (width * 0.5 + 0.18), cy - depth * 0.45, deck_z + 0.35 + bal_h + 0.225),
            rotation=(0.0, 0.0, math.pi * 0.25), mat_index=MAT_INDEX_CUT_STONE
        )


def build_castle_citadel(bm, props, ctx):
    """
    High-level orchestrator: builds the complete castle fortress system for the main building:
    1. Four massive cylindrical corner drum towers with machicolations & witch-hat spires.
    2. Soaring central citadel keep tower rising through the roof.
    3. Four corbelled hanging bartizans on upper wall junctions.
    4. Royal portal portico and stone balustraded loggia.
    """
    tier = getattr(props, 'material_tier', 'TIER_3')
    base_w = ctx.base_w
    base_d = ctx.base_d
    num_floors = ctx.num_floors
    floor_h = ctx.floor_h
    found_h = ctx.found_h
    
    eave_z = found_h + num_floors * floor_h
    total_roof_h = getattr(props, 'roof_height', 5.4)
    ridge_z = eave_z + total_roof_h

    # Wing dimensions for U-shape
    wings = ctx.wings
    wing_d = getattr(props, 'wing_depth', 17.0)
    wing_w = getattr(props, 'wing_width', 10.5)

    # -------------------------------------------------------------------------
    # 1. FOUR MASSIVE CYLINDRICAL CORNER DRUM TOWERS
    # -------------------------------------------------------------------------
    drum_r = 3.8
    drum_shaft_h = eave_z + 3.5
    drum_spire_h = 10.5

    # 1a. Front Wing Tip Drum Towers
    front_tip_y = -base_d * 0.5 - wing_d
    wing_center_x = base_w * 0.5 - wing_w * 0.5
    for sgn in (-1.0, 1.0):
        tx = sgn * wing_center_x
        ty = front_tip_y
        build_castle_drum_tower(
            bm, cx=tx, cy=ty, z_ground=0.0,
            radius=drum_r, shaft_h=drum_shaft_h, spire_h=drum_spire_h,
            tier=tier, num_floors=num_floors
        )

    # 1b. Rear Corner Drum Towers
    rear_corner_x = base_w * 0.5
    rear_corner_y = base_d * 0.5
    for sgn in (-1.0, 1.0):
        tx = sgn * rear_corner_x
        ty = rear_corner_y
        build_castle_drum_tower(
            bm, cx=tx, cy=ty, z_ground=0.0,
            radius=drum_r + 0.2, shaft_h=drum_shaft_h + 1.8, spire_h=drum_spire_h + 1.0,
            tier=tier, num_floors=num_floors
        )

    # -------------------------------------------------------------------------
    # 2. SOARING CENTRAL CITADEL KEEP (GREAT KEEP)
    # -------------------------------------------------------------------------
    keep_r = 5.4
    keep_shaft_h = ridge_z + 8.5  # Soars high above roof ridge!
    keep_spire_h = 12.0
    build_castle_central_keep(
        bm, cx=0.0, cy=1.5, z_ground=0.0,
        radius=keep_r, shaft_h=keep_shaft_h, spire_h=keep_spire_h,
        num_floors=num_floors + 1
    )

    # -------------------------------------------------------------------------
    # 3. CORBELLED HANGING BARTIZANS (TOURELLES)
    # -------------------------------------------------------------------------
    bartizan_z = found_h + (num_floors - 1) * floor_h + 1.2
    # Inner courtyard corners (where wings meet main body)
    inner_corner_x = base_w * 0.5 - wing_w
    inner_corner_y = -base_d * 0.5
    for sgn in (-1.0, 1.0):
        build_castle_corbelled_bartizan(
            bm, cx=sgn * (inner_corner_x - 0.4), cy=inner_corner_y - 0.4,
            z_corbel=bartizan_z, radius=1.35, height=4.5, spire_h=4.2
        )

    # -------------------------------------------------------------------------
    # 4. ROYAL PORTAL PORTICO & STONE LOGGIA
    # -------------------------------------------------------------------------
    portal_y = -base_d * 0.5
    build_castle_portal_loggia(
        bm, cx=0.0, cy=portal_y, z_ground=0.0,
        width=7.5, depth=3.8, height=floor_h + 0.6
    )
