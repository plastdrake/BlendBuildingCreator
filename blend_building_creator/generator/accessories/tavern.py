"""
Covered entrance veranda.

A reusable timber veranda porch: deck, two columns, a lintel beam and a pitched
shingle awning. It returns the front-right column's top so a caller can mount a
hanging sign (see ``signage.build_hanging_sign``) without knowing the porch
internals - the sign geometry itself lives in the generic signage module.
"""

import math

from ..mesh_utils import create_beveled_box, create_cylinder
from ..materials import MAT_INDEX_TIMBER, MAT_INDEX_SHINGLES
from ..roof.shingles import map_lean_to_shingle_uvs


def build_tavern_porch(bm, x_min, x_max, front_y, z_ground, door_x=None, seed=42,
                       door_h=2.4, found_h=0.6):
    if door_x is None:
        door_x = (x_min + x_max) * 0.5

    porch_w = 2.8
    porch_d = 1.5
    # The veranda must clear the entrance door (which sits on the foundation), so
    # size its height from the real door top instead of a fixed value.
    porch_h = max(2.55, found_h + door_h + 0.30)
    px_min = door_x - porch_w * 0.5
    px_max = door_x + porch_w * 0.5
    py_front = front_y - porch_d

    deck_h = 0.20
    create_beveled_box(
        bm, size=(porch_w, porch_d, deck_h),
        location=(door_x, (front_y + py_front) * 0.5, z_ground + deck_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
    )
    create_beveled_box(
        bm, size=(porch_w * 0.65, 0.35, deck_h * 0.5),
        location=(door_x, py_front - 0.18, z_ground + deck_h * 0.25),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )

    col_r = 0.09
    col_h = porch_h - deck_h
    col_z = z_ground + deck_h + col_h * 0.5
    for cx in (px_min + col_r, px_max - col_r):
        create_cylinder(
            bm, radius=col_r, height=col_h, segments=12,
            location=(cx, py_front + col_r, col_z),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + deck_h + 0.04),
            mat_index=MAT_INDEX_TIMBER
        )
        create_cylinder(
            bm, radius=col_r * 1.3, height=0.08, segments=12,
            location=(cx, py_front + col_r, z_ground + porch_h - 0.04),
            mat_index=MAT_INDEX_TIMBER
        )

    create_beveled_box(
        bm, size=(porch_w + 0.20, 0.14, 0.16),
        location=(door_x, py_front + col_r, z_ground + porch_h),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )
    awning_pitch = 0.35
    awning_l = math.sqrt(porch_d * porch_d + (porch_d * awning_pitch) ** 2) + 0.25
    awning_mid_y = (front_y + py_front) * 0.5
    awning_mid_z = z_ground + porch_h + (porch_d * awning_pitch) * 0.5 + 0.08
    awning_ang = math.atan2(porch_d * awning_pitch, porch_d)

    # Timber under-deck (also hides the interior of the awning).
    create_beveled_box(
        bm, size=(porch_w + 0.30, awning_l, 0.08),
        location=(door_x, awning_mid_y, awning_mid_z),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )
    # Shingle course on top, remapped so the tiles run and scale exactly like
    # the main roofs instead of the plain box (rotated / mis-scaled) mapping.
    slab_z = awning_mid_z + 0.065
    slab_faces = create_beveled_box(
        bm, size=(porch_w + 0.35, awning_l + 0.04, 0.05),
        location=(door_x, awning_mid_y, slab_z),
        rotation=(awning_ang, 0.0, 0.0),
        mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.006
    )
    map_lean_to_shingle_uvs(bm, slab_faces, (door_x, awning_mid_y, slab_z),
                            (awning_ang, 0.0, 0.0))

    # Cover the exposed slab edges: a fascia on the low eave, raked barge boards
    # down both sides and a flashing where the awning meets the wall.
    cos_a, sin_a = math.cos(awning_ang), math.sin(awning_ang)
    half_l = awning_l * 0.5
    front_y_face = awning_mid_y - half_l * cos_a
    front_z = slab_z - half_l * sin_a
    back_y_face = awning_mid_y + half_l * cos_a
    back_z = slab_z + half_l * sin_a

    create_beveled_box(
        bm, size=(porch_w + 0.55, 0.10, 0.20),
        location=(door_x, front_y_face + 0.02, front_z - 0.02),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010
    )
    for sx in (-1.0, 1.0):
        create_beveled_box(
            bm, size=(0.06, awning_l + 0.12, 0.20),
            location=(door_x + sx * (porch_w * 0.5 + 0.20), awning_mid_y, slab_z - 0.01),
            rotation=(awning_ang, 0.0, 0.0),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    create_beveled_box(
        bm, size=(porch_w + 0.55, 0.12, 0.14),
        location=(door_x, back_y_face - 0.05, back_z + 0.02),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
    )

    post_cx = px_max - col_r
    post_cy = py_front + col_r
    return {
        'post_x': post_cx,
        'post_y': post_cy,
        'sign_z': z_ground + porch_h - 0.15,
        'porch_front_y': py_front,
        'door_x': door_x,
    }
