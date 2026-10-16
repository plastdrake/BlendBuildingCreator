import math
from mathutils import Vector
from ..uv_utils import apply_roof_shingle_uvs
from ..mesh_utils import create_beveled_box, create_cone
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_SHINGLES,
    MAT_INDEX_CUT_STONE, MAT_INDEX_IRON, MAT_INDEX_LANTERN, MAT_INDEX_WATER,
    MAT_INDEX_TERRACOTTA,
)


def build_blacksmith_forge(bm, x_min, x_max, y_min, y_max, z_ground, wall_thickness, seed=42):
    wall_x = x_max
    canopy_w = 2.6
    canopy_d = (y_max - y_min) * 0.75
    canopy_h = 2.45
    canopy_cy = (y_min + y_max) * 0.5
    outer_x = wall_x + canopy_w
    
    deck_thick = 0.12
    create_beveled_box(
        bm, size=(canopy_w + 0.15, canopy_d + 0.20, deck_thick),
        location=(wall_x + canopy_w * 0.5, canopy_cy, z_ground + deck_thick * 0.5),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )
    
    col_w = 0.18
    p1_y = canopy_cy - canopy_d * 0.44
    p2_y = canopy_cy + canopy_d * 0.44
    post_x = outer_x - col_w * 0.5
    pillar_h = canopy_h - 0.20
    
    # Vertical posts and knee braces
    for py in (p1_y, p2_y):
        create_beveled_box(
            bm, size=(0.36, 0.36, 0.20),
            location=(post_x, py, z_ground + 0.10),
            mat_index=MAT_INDEX_STONE, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(col_w, col_w, pillar_h),
            location=(post_x, py, z_ground + 0.20 + pillar_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        sgn = 1.0 if py < canopy_cy else -1.0
        # Longitudinal knee brace along Y to the front plate beam
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(post_x, py + sgn * 0.23, z_ground + canopy_h - 0.23),
            rotation=(-sgn * 0.785, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        # Transverse knee brace along X to the horizontal tie beam
        create_beveled_box(
            bm, size=(0.11, 0.11, 0.65),
            location=(post_x - 0.23, py, z_ground + canopy_h - 0.23),
            rotation=(0.0, -0.785, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.008
        )
        
    # Front longitudinal plate beam along Y connecting the posts
    create_beveled_box(
        bm, size=(col_w, canopy_d + 0.30, 0.18),
        location=(post_x, canopy_cy, z_ground + canopy_h),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
    )
    
    # Transverse tie beams along X connecting the wall to the outer posts (embedded into the wall)
    embed_wall = 0.50
    tie_len = canopy_w + embed_wall
    for py in (p1_y, p2_y):
        create_beveled_box(
            bm, size=(tie_len, col_w, 0.18),
            location=(wall_x + canopy_w * 0.5 - embed_wall * 0.5, py, z_ground + canopy_h),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012
        )
        
    roof_pitch = 0.35
    roof_z_wall = z_ground + canopy_h + canopy_w * roof_pitch
    roof_z_outer = z_ground + canopy_h
    roof_mid_x = (wall_x + outer_x) * 0.5
    roof_mid_z = (roof_z_wall + roof_z_outer) * 0.5 + 0.08
    rafter_l = math.sqrt(canopy_w * canopy_w + (roof_z_wall - roof_z_outer) ** 2) + 0.40
    roof_ang = math.atan2(roof_z_wall - roof_z_outer, canopy_w)
    cos_ang = math.cos(roof_ang)
    sin_ang = math.sin(roof_ang)
    
    # Wall ledger beam supporting rafters against the wall
    create_beveled_box(
        bm, size=(0.28, canopy_d + 0.30, 0.18),
        location=(wall_x, canopy_cy, roof_z_wall - 0.06),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
    )
    
    # Sloping rafters
    for ry in (p1_y, canopy_cy, p2_y):
        create_beveled_box(
            bm, size=(rafter_l, 0.10, 0.14),
            location=(roof_mid_x, ry, roof_mid_z - 0.08),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.010
        )
    
    # Timber under-deck
    create_beveled_box(
        bm, size=(rafter_l, canopy_d + 0.40, 0.08),
        location=(roof_mid_x, canopy_cy, roof_mid_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.010
    )
    
    # Roof shingle layer with matching 0.32 scale and downhill facing UVs
    shingle_l = rafter_l + 0.05
    shingle_w = canopy_d + 0.46
    slab_z = roof_mid_z + 0.06
    shingle_faces = create_beveled_box(
        bm, size=(shingle_l, shingle_w, 0.05),
        location=(roof_mid_x, canopy_cy, slab_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_SHINGLES,
        bevel_amount=0.008
    )
    apply_roof_shingle_uvs(bm, shingle_faces, scale=0.32)
    
    # Timber framing around the roof (fascia board, side bargeboards, wall trim)
    half_l = shingle_l * 0.5
    
    # Front eave fascia board capping the low edge
    front_x = roof_mid_x + half_l * cos_ang + 0.02
    front_z = slab_z - half_l * sin_ang - 0.02
    create_beveled_box(
        bm, size=(0.08, shingle_w + 0.18, 0.18),
        location=(front_x, canopy_cy, front_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.008
    )
    
    # Side sloping bargeboards down both verges
    for s in (-1.0, 1.0):
        y_barge = canopy_cy + s * (shingle_w * 0.5 + 0.035)
        create_beveled_box(
            bm, size=(shingle_l + 0.10, 0.08, 0.16),
            location=(roof_mid_x, y_barge, slab_z - 0.01),
            rotation=(0.0, roof_ang, 0.0),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )
        
    # Top wall trim / flashing where the roof meets the building wall
    back_x = roof_mid_x - half_l * cos_ang - 0.01
    back_z = slab_z + half_l * sin_ang + 0.02
    create_beveled_box(
        bm, size=(0.10, shingle_w + 0.18, 0.14),
        location=(back_x, canopy_cy, back_z),
        rotation=(0.0, roof_ang, 0.0),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.008
    )

    # -------------------------------------------------------------------------
    # Forge hearth under the canopy: a terracotta-brick forge with a glowing
    # fire chamber, iron hood and a brick flue rising through the canopy.
    # -------------------------------------------------------------------------
    forge_x = wall_x + 0.90
    forge_y = canopy_cy
    forge_w, forge_d, forge_h = 1.30, 1.05, 0.95
    z_deck = z_ground + 0.12   # top of the stone deck; props rest here
    # Terracotta-brick forge body (textured box, generous bevel).
    create_beveled_box(
        bm, size=(forge_w, forge_d, forge_h),
        location=(forge_x, forge_y, z_deck + forge_h * 0.5),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.020)
    # --- Fire opening, now on the +X face (facing the open yard / smith) -----
    face_x = forge_x + forge_w * 0.5          # +X face of the body
    open_cy = forge_y
    open_cz = z_deck + 0.40
    open_w, open_h = 0.62, 0.44               # open_w now runs along Y
    # Dark firebox interior recessed into the body.
    create_beveled_box(
        bm, size=(0.34, open_w, open_h),
        location=(face_x - 0.14, open_cy, open_cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010)
    # Glowing coals / burning fuel sitting in the firebox.
    create_beveled_box(
        bm, size=(0.24, open_w - 0.10, 0.14),
        location=(face_x - 0.12, open_cy, z_deck + 0.24),
        mat_index=MAT_INDEX_LANTERN, bevel_amount=0.010)
    # Brick jambs each side of the mouth (now along Y).
    for sy in (-(open_w * 0.5 + 0.06), (open_w * 0.5 + 0.06)):
        create_beveled_box(
            bm, size=(0.14, 0.11, open_h + 0.20),
            location=(face_x + 0.05, open_cy + sy, open_cz),
            mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.010)
    # Brick voussoir arch over the mouth (fanned in the YZ plane).
    _arch_r = open_w * 0.5 + 0.07
    _arch_top = open_cz + open_h * 0.5
    for k in range(5):
        a = math.pi * (0.13 + 0.74 * k / 4.0)
        create_beveled_box(
            bm, size=(0.14, 0.12, 0.11),
            location=(face_x + 0.05,
                      open_cy + _arch_r * math.cos(a),
                      _arch_top + _arch_r * math.sin(a) * 0.70),
            rotation=(a - math.pi * 0.5, 0.0, 0.0),
            mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.008)
    # Stone hearth sill jutting out in front of the mouth (+X).
    create_beveled_box(
        bm, size=(0.30, open_w + 0.34, 0.09),
        location=(face_x + 0.06, open_cy, z_deck + 0.10),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
    # Iron hood tapering up from the forge crown.
    create_beveled_box(
        bm, size=(forge_w - 0.10, forge_d - 0.10, 0.16),
        location=(forge_x, forge_y, z_deck + forge_h + 0.08),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012)
    # Terracotta-brick flue rising through the canopy roof (textured box).
    flue_h = canopy_h + 0.40
    create_beveled_box(
        bm, size=(0.52, 0.52, flue_h),
        location=(forge_x, forge_y, z_deck + forge_h + 0.16 + flue_h * 0.5),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.016)
    # Finish the flue top like the main chimney: collar, overhanging cap, pot.
    flue_top = z_deck + forge_h + 0.16 + flue_h
    create_beveled_box(
        bm, size=(0.62, 0.62, 0.10),
        location=(forge_x, forge_y, flue_top - 0.11),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.020)
    create_beveled_box(
        bm, size=(0.70, 0.70, 0.12),
        location=(forge_x, forge_y, flue_top + 0.01),
        rotation=(0.0, 0.02, 0.0),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.025)
    create_cone(
        bm, radius1=0.19, radius2=0.24, height=0.40, segments=8,
        location=(forge_x, forge_y, flue_top + 0.07 + 0.20),
        mat_index=MAT_INDEX_IRON)
    # Open quench barrel beside the forge: hollow, no lid, water surface.
    from ..mesh_utils import create_hollow_cylinder, create_torus_ring
    quench_x = forge_x + 1.35
    quench_y = forge_y - 1.20
    q_r, q_h = 0.30, 0.62
    create_hollow_cylinder(
        bm, radius=q_r, inner_radius=q_r - 0.035, height=q_h,
        inner_depth=q_h - 0.06, segments=16,
        location=(quench_x, quench_y, z_deck + q_h * 0.5),
        mat_index=MAT_INDEX_WOOD,
        liquid_height=q_h - 0.20, liquid_mat_index=MAT_INDEX_WATER,
        smooth=True)
    for hz in (0.17, 0.45):
        create_torus_ring(
            bm, location=(quench_x, quench_y, z_deck + hz),
            rotation=(0.0, 0.0, 0.0), major_radius=q_r + 0.006,
            minor_radius=0.015, major_segments=16, minor_segments=6,
            mat_index=MAT_INDEX_IRON)
    # Fuel: a small stacked log pile resting ON the deck, behind the forge.
    from .interior_furniture import build_log_pile
    build_log_pile(bm, forge_x, forge_y + forge_d * 0.5 + 0.62, z_deck,
                   ang=0.0, length=0.95, radius=0.10, rows=2)
    # Anvil on the deck beside the fire opening (out of the mouth's +X path).
    try:
        from .artisan_props import build_anvil
        build_anvil(bm, forge_x + 1.05, forge_y + 1.05, z_deck, ang=0.0)
    except Exception:
        pass
