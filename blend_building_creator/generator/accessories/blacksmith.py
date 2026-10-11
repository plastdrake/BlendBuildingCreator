import math
from mathutils import Vector
from ..uv_utils import apply_roof_shingle_uvs
from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_SHINGLES,
    MAT_INDEX_PLASTER_BRICK, MAT_INDEX_CUT_STONE, MAT_INDEX_IRON,
    MAT_INDEX_LANTERN, MAT_INDEX_CLAY, MAT_INDEX_WATER,
)


def _brick_faces(bm, cx, cy, cz, w, d, h, mat_brick=MAT_INDEX_CLAY,
                 mat_core=MAT_INDEX_CUT_STONE, brick=0.30, course=0.11,
                 gap=0.014, thick=0.06):
    """Face a rectangular masonry block in staggered brick on all four
    vertical sides.

    The mortar core is inset 3cm on every horizontal axis and 2cm top/bottom,
    while each brick sits proud with its outer face flush to the nominal box
    wall (``thick`` deep). The core surface is therefore never coplanar with a
    brick face -> no z-fighting.
    """
    faces = []
    faces += create_beveled_box(
        bm, size=(max(0.05, w - 0.06), max(0.05, d - 0.06), max(0.05, h - 0.04)),
        location=(cx, cy, cz), mat_index=mat_core, bevel_amount=0.012)

    def _course(run, face_coord, sign, span, height):
        nonlocal faces
        z0 = cz - height * 0.5 + course * 0.5
        rows = max(1, int(round(height / (course + gap))))
        for r in range(rows):
            z = z0 + r * (course + gap)
            if z - course * 0.5 > cz + height * 0.5 + 1e-6:
                break
            off = (brick + gap) * 0.5 if (r % 2) else 0.0
            n = int(span / (brick + gap)) + 2
            for i in range(n):
                s0 = -span * 0.5 + off + i * (brick + gap)
                s1 = s0 + brick
                if s1 <= -span * 0.5 + 1e-6:
                    continue
                if s0 >= span * 0.5 - 1e-6:
                    break
                # Clamp both ends flush with the block face (no ragged ends).
                l0 = max(s0, -span * 0.5)
                l1 = min(s1, span * 0.5)
                seg_len = l1 - l0
                if seg_len < 0.05:
                    continue
                sc = (l0 + l1) * 0.5
                if run == 'X':
                    loc = (cx + sc, face_coord + sign * thick * 0.5, z)
                    size = (seg_len, thick, course)
                else:
                    loc = (face_coord + sign * thick * 0.5, cy + sc, z)
                    size = (thick, seg_len, course)
                faces += create_beveled_box(bm, size=size, location=loc,
                                            mat_index=mat_brick,
                                            bevel_amount=0.005)

    # ±X faces: bricks run along Y.  ±Y faces: bricks run along X.
    _course('Y', cx - w * 0.5, -1.0, d, h)
    _course('Y', cx + w * 0.5, 1.0, d, h)
    _course('X', cy - d * 0.5, -1.0, w, h)
    _course('X', cy + d * 0.5, 1.0, w, h)
    return faces

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
    # Forge hearth under the canopy: a BRICK-BUILT forge with a glowing fire
    # chamber, iron hood and a brick flue rising through the canopy.
    # -------------------------------------------------------------------------
    forge_x = wall_x + 0.90
    forge_y = canopy_cy
    forge_w, forge_d, forge_h = 1.30, 1.05, 0.95
    z_deck = z_ground + 0.12   # top of the stone deck; props rest here
    # Clay-brick masonry body (mortar core inset so nothing is coplanar).
    _brick_faces(bm, forge_x, forge_y, z_deck + forge_h * 0.5,
                 forge_w, forge_d, forge_h, brick=0.30, course=0.12,
                 gap=0.014, thick=0.06)
    # --- Fire opening in the front face (facing the yard, -Y) ---------------
    front_y = forge_y - forge_d * 0.5
    open_cx, open_cz = forge_x, z_deck + 0.40
    open_w, open_h = 0.62, 0.44
    # Dark firebox interior recessed into the body.
    create_beveled_box(
        bm, size=(open_w, 0.34, open_h),
        location=(open_cx, front_y + 0.14, open_cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.010)
    # Glowing coals / burning fuel sitting in the firebox.
    create_beveled_box(
        bm, size=(open_w - 0.10, 0.24, 0.14),
        location=(open_cx, front_y + 0.12, z_deck + 0.24),
        mat_index=MAT_INDEX_LANTERN, bevel_amount=0.010)
    # Clay jambs each side of the mouth.
    for sx in (-(open_w * 0.5 + 0.06), (open_w * 0.5 + 0.06)):
        create_beveled_box(
            bm, size=(0.11, 0.14, open_h + 0.20),
            location=(open_cx + sx, front_y + 0.05, open_cz),
            mat_index=MAT_INDEX_CLAY, bevel_amount=0.010)
    # Clay voussoir arch over the mouth (bricks fanned around the opening).
    _arch_r = open_w * 0.5 + 0.07
    _arch_top = open_cz + open_h * 0.5
    for k in range(5):
        a = math.pi * (0.13 + 0.74 * k / 4.0)
        create_beveled_box(
            bm, size=(0.12, 0.14, 0.11),
            location=(open_cx + _arch_r * math.cos(a),
                      front_y + 0.05,
                      _arch_top + _arch_r * math.sin(a) * 0.70),
            rotation=(0.0, a - math.pi * 0.5, 0.0),
            mat_index=MAT_INDEX_CLAY, bevel_amount=0.008)
    # Hearth sill jutting out in front of the mouth.
    create_beveled_box(
        bm, size=(open_w + 0.34, 0.30, 0.09),
        location=(open_cx, front_y - 0.06, z_deck + 0.10),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
    # Iron hood tapering up from the forge crown.
    create_beveled_box(
        bm, size=(forge_w - 0.10, forge_d - 0.10, 0.16),
        location=(forge_x, forge_y, z_deck + forge_h + 0.08),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012)
    # Clay-brick flue rising through the canopy roof.
    flue_h = canopy_h + 0.40
    _brick_faces(bm, forge_x, forge_y,
                 z_deck + forge_h + 0.16 + flue_h * 0.5,
                 0.52, 0.52, flue_h, brick=0.24, course=0.17,
                 gap=0.014, thick=0.05)
    # Quench barrel beside the forge (water-filled).
    from .furniture import build_barrel
    quench_x = min(wall_x + canopy_w - 0.30, forge_x + 1.15)
    build_barrel(bm, quench_x, canopy_cy - 0.75, z_deck, radius=0.28, height=0.60)
    create_beveled_box(
        bm, size=(0.44, 0.44, 0.02),
        location=(quench_x, canopy_cy - 0.75, z_deck + 0.55),
        mat_index=MAT_INDEX_WATER, bevel_amount=0.006)
    # Fuel: a small stacked log pile resting ON the deck, behind the forge.
    from .interior_furniture import build_log_pile
    build_log_pile(bm, forge_x, forge_y + forge_d * 0.5 + 0.62, z_deck,
                   ang=0.0, length=0.95, radius=0.10, rows=2)
