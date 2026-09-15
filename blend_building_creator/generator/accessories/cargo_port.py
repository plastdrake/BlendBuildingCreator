"""
Freight cargo port frame builder.

An open portal in a wing side wall with a timber frame and iron bindings, plus a
full-length loading dock outside so the courtyard crane can lift cargo straight
into the building.
"""

from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_CUT_STONE,
)


def build_cargo_port_frame(bm, face_x, outward_sgn, cy, portal_w, portal_h, z_floor, wall_t,
                           dock_y1=None, dock_y2=None):
    """
    Builds an open freight portal frame (no door leaf) in a wing side wall so the
    courtyard crane can lift cargo straight in:
    - Chunky timber jamb posts proud of the facade with iron binding straps.
    - Heavy timber lintel beam spanning the opening.
    - Wooden threshold strip flush with the interior floor (no step, roll cargo in).
    - Full-length loading dock outside: plank deck flush with the floor, carried on
      longitudinal bearer beams, chunky posts on stone footings, with a dark timber
      fascia skirt so it reads as a dock rather than a table.
    Callers must also cut a matching wall opening (u-span portal_w at cy,
    z_floor to z_floor + portal_h) and keep windows/timber clear of it.
    dock_y1/dock_y2 optionally bound the dock ends along the wall (defaults: a
    short pad around the portal).
    """
    jamb_w = 0.24
    jamb_d = wall_t + 0.26
    jx = face_x + outward_sgn * 0.06
    for s in (-1.0, 1.0):
        jy = cy + s * (portal_w * 0.5 + jamb_w * 0.5)
        create_beveled_box(
            bm, size=(jamb_d, jamb_w, portal_h),
            location=(jx, jy, z_floor + portal_h * 0.5),
            mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014, bevel_segments=2
        )
        for sz in (0.55, portal_h - 0.55):
            create_beveled_box(
                bm, size=(jamb_d + 0.03, jamb_w + 0.03, 0.09),
                location=(jx, jy, z_floor + sz),
                mat_index=MAT_INDEX_IRON, bevel_amount=0.005
            )
    create_beveled_box(
        bm, size=(jamb_d, portal_w + jamb_w * 2.0 + 0.12, 0.30),
        location=(jx, cy, z_floor + portal_h + 0.15),
        mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.014, bevel_segments=2
    )
    # Wooden threshold bridging the wall gap, flush with the interior floor
    floor_top = z_floor + 0.05
    create_beveled_box(
        bm, size=(wall_t + 0.24, portal_w + 0.12, 0.10),
        location=(face_x, cy, floor_top - 0.05),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008
    )
    # Full-length loading dock outside, deck top flush with the floor
    deck_t = 0.14
    deck_top = floor_top
    deck_d = 1.6
    if dock_y1 is None:
        dock_y1 = cy - (portal_w * 0.5 + 0.5)
    if dock_y2 is None:
        dock_y2 = cy + (portal_w * 0.5 + 0.5)
    deck_y1, deck_y2 = min(dock_y1, dock_y2), max(dock_y1, dock_y2)
    deck_len = max(1.0, deck_y2 - deck_y1)
    deck_yc = (deck_y1 + deck_y2) * 0.5
    deck_inner = face_x + outward_sgn * (wall_t * 0.5)
    deck_cx = deck_inner + outward_sgn * (deck_d * 0.5)
    create_beveled_box(
        bm, size=(deck_d, deck_len, deck_t),
        location=(deck_cx, deck_yc, deck_top - deck_t * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.01
    )
    # Longitudinal bearer beams under the deck (inner + outer post lines)
    bearer_h = 0.16
    bearer_z = deck_top - deck_t - bearer_h * 0.5
    post_rows = [deck_inner + outward_sgn * 0.20, deck_inner + outward_sgn * (deck_d - 0.20)]
    for brow in post_rows:
        create_beveled_box(
            bm, size=(0.16, deck_len - 0.10, bearer_h),
            location=(brow, deck_yc, bearer_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Dark fascia skirt around the deck edges (hides the bearer layer)
    fascia_h = 0.30
    fascia_z = deck_top - fascia_h * 0.5 + 0.02
    create_beveled_box(
        bm, size=(0.06, deck_len, fascia_h),
        location=(deck_inner + outward_sgn * (deck_d - 0.03), deck_yc, fascia_z),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    for es in (-1.0, 1.0):
        create_beveled_box(
            bm, size=(deck_d, 0.06, fascia_h),
            location=(deck_cx, deck_yc + es * (deck_len * 0.5 - 0.03), fascia_z),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    # Chunky posts on stone footings, spaced along both bearer lines
    n_posts = max(3, int(deck_len / 1.3) + 1)
    footing_top = 0.18
    post_top = bearer_z - bearer_h * 0.5
    post_h = post_top - footing_top
    if post_h > 0.12:
        for brow in post_rows:
            for k in range(n_posts):
                py = deck_y1 + 0.28 + (deck_len - 0.56) * (k / max(1, n_posts - 1))
                create_beveled_box(
                    bm, size=(0.34, 0.34, footing_top),
                    location=(brow, py, footing_top * 0.5),
                    mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
                )
                create_beveled_box(
                    bm, size=(0.16, 0.16, post_h),
                    location=(brow, py, footing_top + post_h * 0.5),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
                )
