"""
Freight cargo port frame builder.

An open portal with a timber frame and iron bindings, plus a
loading dock outside so the courtyard crane can lift cargo straight
into the building. Supports both ground floor docks and upper floor
platforms with vertical pillars down to the dock below and an upper crane.
"""

import math
from mathutils import Vector
from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_CUT_STONE,
)


def build_cargo_port_frame(bm, face_coord, outward_sgn, portal_center, portal_w, portal_h, z_floor, wall_t,
                           dock_y1=None, dock_y2=None, dock_span1=None, dock_span2=None,
                           axis='X', deck_depth=1.6, is_upper_tier=False, lower_z_floor=None,
                           has_upper_crane=False):
    """
    Builds an open freight portal frame and loading dock.
    
    Supports:
    - axis='X': wall at face_coord (x), outward normal (+X or -X), portal_center along Y.
    - axis='Y': wall at face_coord (y), outward normal (+Y or -Y), portal_center along X.
    
    Zero coplanar battles:
    - Plank deck is inset cleanly inside the timber fascia frame.
    - Wooden threshold is sized to fit snugly between jambs (portal_w - 0.02) and bridges the wall
      thickness (wall_t + 0.04) with its top 7mm proud, eliminating Z-fighting with interior floor and dock.
    - When is_upper_tier=True, builds an upper platform carried by vertical timber pillars extending
      down to lower_z_floor, with an upper swivel crane mounted on the deck.
    """
    # Normalize dock span bounds
    s1 = dock_span1 if dock_span1 is not None else dock_y1
    s2 = dock_span2 if dock_span2 is not None else dock_y2
    if s1 is None:
        s1 = portal_center - (portal_w * 0.5 + 0.6)
    if s2 is None:
        s2 = portal_center + (portal_w * 0.5 + 0.6)
    dock_u1, dock_u2 = min(s1, s2), max(s1, s2)
    deck_len = max(1.2, dock_u2 - dock_u1)
    deck_uc = (dock_u1 + dock_u2) * 0.5

    def _box(size_norm, size_tang, size_z, norm_val, tang_val, z_val, mat_idx, bevel=0.01, segments=1):
        if axis == 'X':
            sx, sy, sz = size_norm, size_tang, size_z
            px, py, pz = norm_val, tang_val, z_val
        else:
            sx, sy, sz = size_tang, size_norm, size_z
            px, py, pz = tang_val, norm_val, z_val
        create_beveled_box(
            bm, size=(sx, sy, sz), location=(px, py, pz),
            mat_index=mat_idx, bevel_amount=bevel, bevel_segments=segments
        )

    # 1. Chunky timber jamb posts proud of the facade with iron binding straps
    # Shifted slightly into the entrance (by 0.035m) so the opening edge is safely embedded inside the jamb
    jamb_w = 0.24
    jamb_d = wall_t + 0.26
    norm_jamb = face_coord + outward_sgn * 0.06

    for s in (-1.0, 1.0):
        ju = portal_center + s * ((portal_w * 0.5 - 0.035) + jamb_w * 0.5)
        _box(jamb_d, jamb_w, portal_h + 0.04, norm_jamb, ju, z_floor + (portal_h + 0.04) * 0.5,
             MAT_INDEX_TIMBER_FRAME, bevel=0.014, segments=2)
        for sz in (0.55, portal_h - 0.55):
            _box(jamb_d + 0.03, jamb_w + 0.03, 0.09, norm_jamb, ju, z_floor + sz,
                 MAT_INDEX_IRON, bevel=0.005)

    # 2. Heavy timber lintel beam spanning the opening
    # Moved slightly downwards (center at z_floor + portal_h + 0.11 instead of 0.15) so it overlaps the top of the wall cutout by 4cm, preventing coplanar Z-fighting with wall headers/plaster
    lintel_h = 0.30
    lintel_len = portal_w + jamb_w * 2.0 + 0.12
    lintel_z = z_floor + portal_h + 0.11
    _box(jamb_d, lintel_len, lintel_h, norm_jamb, portal_center, lintel_z,
         MAT_INDEX_TIMBER_FRAME, bevel=0.014, segments=2)

    # 3. Wooden threshold bridging the wall gap
    # Sized portal_w - 0.02 so it does NOT cut into wall panels, and 7mm proud with bevel to stop coplanar fighting
    floor_top = z_floor + 0.05
    thresh_w = max(0.4, portal_w - 0.02)
    thresh_d = wall_t + 0.04
    _box(thresh_d, thresh_w, 0.10, face_coord, portal_center, floor_top - 0.05 + 0.007,
         MAT_INDEX_WOOD, bevel=0.008)

    deck_inner = face_coord + outward_sgn * (wall_t * 0.5)
    deck_d = deck_depth
    deck_t = 0.13
    deck_top = floor_top

    if not is_upper_tier:
        # Ground Loading Dock
        deck_norm_c = deck_inner + outward_sgn * (deck_d * 0.5)

        # Inset floor plank deck (so it sits cleanly INSIDE the border fascia frame)
        floor_len = deck_len - 0.08
        floor_d = deck_d - 0.07
        floor_norm_c = deck_inner + outward_sgn * (0.03 + floor_d * 0.5)
        _box(floor_d, floor_len, deck_t, floor_norm_c, deck_uc, deck_top - deck_t * 0.5,
             MAT_INDEX_WOOD, bevel=0.008)

        # Longitudinal bearer beams under the deck
        bearer_h = 0.16
        bearer_z = deck_top - deck_t - bearer_h * 0.5
        post_rows = [
            deck_inner + outward_sgn * 0.22,
            deck_inner + outward_sgn * (deck_d - 0.22)
        ]
        for brow in post_rows:
            _box(0.16, deck_len - 0.10, bearer_h, brow, deck_uc, bearer_z,
                 MAT_INDEX_TIMBER, bevel=0.008)

        # Dark timber fascia skirt around the deck edges (acts as neat raised frame)
        fascia_h = 0.30
        fascia_z = deck_top - fascia_h * 0.5 + 0.015
        # Outer fascia
        _box(0.06, deck_len, fascia_h, deck_inner + outward_sgn * (deck_d - 0.03), deck_uc, fascia_z,
             MAT_INDEX_TIMBER, bevel=0.008)
        # End fascias
        for es in (-1.0, 1.0):
            _box(deck_d, 0.06, fascia_h, deck_norm_c, deck_uc + es * (deck_len * 0.5 - 0.03), fascia_z,
                 MAT_INDEX_TIMBER, bevel=0.008)

        # Chunky posts on stone footings along bearer lines
        n_posts = max(3, int(deck_len / 1.3) + 1)
        footing_top = 0.18
        post_top = bearer_z - bearer_h * 0.5
        post_h = post_top - footing_top
        if post_h > 0.10:
            for brow in post_rows:
                for k in range(n_posts):
                    pu = dock_u1 + 0.28 + (deck_len - 0.56) * (k / max(1, n_posts - 1))
                    _box(0.34, 0.34, footing_top, brow, pu, footing_top * 0.5,
                         MAT_INDEX_CUT_STONE, bevel=0.02)
                    _box(0.16, 0.16, post_h, brow, pu, footing_top + post_h * 0.5,
                         MAT_INDEX_TIMBER, bevel=0.01)

    else:
        # Upper Tier Platform (e.g. 2nd floor loft cargo deck)
        # Sized to cover portal and crane area
        upper_len = min(deck_len, 4.4)
        upper_shift = 0.35 if (axis == 'Y' and outward_sgn < 0) else 0.0
        upper_uc = portal_center + upper_shift
        upper_u1 = upper_uc - upper_len * 0.5
        upper_u2 = upper_uc + upper_len * 0.5

        upper_norm_c = deck_inner + outward_sgn * (deck_d * 0.5)

        # Inset upper deck floor planks
        floor_len = upper_len - 0.08
        floor_d = deck_d - 0.07
        floor_norm_c = deck_inner + outward_sgn * (0.03 + floor_d * 0.5)
        _box(floor_d, floor_len, deck_t, floor_norm_c, upper_uc, deck_top - deck_t * 0.5,
             MAT_INDEX_WOOD, bevel=0.008)

        # Bearer beams under upper platform
        bearer_h = 0.16
        bearer_z = deck_top - deck_t - bearer_h * 0.5
        post_rows = [
            deck_inner + outward_sgn * 0.22,
            deck_inner + outward_sgn * (deck_d - 0.22)
        ]
        for brow in post_rows:
            _box(0.18, upper_len - 0.10, bearer_h, brow, upper_uc, bearer_z,
                 MAT_INDEX_TIMBER, bevel=0.008)

        # Fascia skirt frame around upper deck
        fascia_h = 0.28
        fascia_z = deck_top - fascia_h * 0.5 + 0.015
        _box(0.06, upper_len, fascia_h, deck_inner + outward_sgn * (deck_d - 0.03), upper_uc, fascia_z,
             MAT_INDEX_TIMBER, bevel=0.008)
        for es in (-1.0, 1.0):
            _box(deck_d, 0.06, fascia_h, upper_norm_c, upper_uc + es * (upper_len * 0.5 - 0.03), fascia_z,
                 MAT_INDEX_TIMBER, bevel=0.008)

        # Vertical timber pillars going down to the platform below:
        # "pillars going down to the platform below (not as many as the cargo platform below though that would be too many)"
        # Exactly 2 sturdy pillars at the outer corners of the upper platform
        if lower_z_floor is not None:
            lower_dock_top = lower_z_floor + 0.05
            pillar_top = bearer_z - bearer_h * 0.5
            pillar_h = pillar_top - lower_dock_top
            if pillar_h > 0.30:
                pillar_norm = post_rows[1] # outer bearer row
                pillar_us = [upper_u1 + 0.32, upper_u2 - 0.32]
                for pu in pillar_us:
                    # Vertical post
                    _box(0.20, 0.20, pillar_h, pillar_norm, pu, lower_dock_top + pillar_h * 0.5,
                         MAT_INDEX_TIMBER, bevel=0.014)
                    # Iron footing bracket resting on lower deck
                    _box(0.24, 0.24, 0.10, pillar_norm, pu, lower_dock_top + 0.05,
                         MAT_INDEX_IRON, bevel=0.005)
                    # Iron capital strap at top
                    _box(0.24, 0.24, 0.08, pillar_norm, pu, pillar_top - 0.04,
                         MAT_INDEX_IRON, bevel=0.005)
                    # Diagonal knee brace connecting pillar to outer bearer
                    brace_h = min(0.65, pillar_h * 0.4)
                    brace_s = -1.0 if pu > upper_uc else 1.0
                    _box(0.14, 0.14, brace_h, pillar_norm, pu + brace_s * 0.22, pillar_top - brace_h * 0.5,
                         MAT_INDEX_TIMBER, bevel=0.01)

        # Real swivel crane mounted on the 2nd floor platform
        if has_upper_crane:
            from .crane import build_courtyard_crane
            # Moved outwards along platform depth so boom reaches far over the dock
            crane_norm = deck_inner + outward_sgn * (deck_d * 0.65)
            crane_u = upper_uc + (upper_len * 0.22)
            if axis == 'X':
                cx, cy = crane_norm, crane_u
                rot_crane = 0.0 if outward_sgn > 0 else 3.14
            else:
                cx, cy = crane_u, crane_norm
                rot_crane = -1.57 if outward_sgn < 0 else 1.57
            build_courtyard_crane(
                bm, yard_x=cx, yard_y=cy, z_ground=deck_top,
                mast_height=3.0, jib_length=2.5, rot_angle=rot_crane,
                include_stone_pad=False, pad_radius=0.92
            )
