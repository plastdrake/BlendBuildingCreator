"""
Mini-wing outcrop builder.

A small annex / oriel projection attached to a facade. This module owns only
the outcrop's own body (foundation or corbels, floor and ceiling, post-and-panel
walls) and composes the shared builders for everything it has in common with the
main hall:

- :func:`~generator.openings.build_window_assembly` for the leaded window,
- :func:`~generator.roof.outcrop_roof.build_outcrop_roof` for the shingled roof,
- :mod:`generator.facade` / :mod:`generator.uv_utils` for placement and UVs.
"""

import math
from mathutils import Matrix, Vector

from ..mesh_utils import create_beveled_box
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_PLASTER_EXT, MAT_INDEX_TIMBER_FRAME,
    MAT_INDEX_WOOD,
)
from ..facade import get_facade_frame
from ..uv_utils import map_local_wall_uv
from ..roof.outcrop_roof import build_outcrop_roof


def build_mini_wing(bm, side, floor_mode, wall_x_min, wall_x_max, wall_y_min, wall_y_max,
                    z_base, width=2.2, depth=1.6, height=2.6, roof_style='LEAN_TO', tier='TIER_3',
                    floor_h=2.8, lower_bounds=None,
                    win_w=None, win_h=None, shingle_scale=0.32, shingle_rot=0):
    """
    Builds a small outcrop bay room / annex projection:
    - GROUND: rests on grounded stone foundation plinth.
    - UPPER: cantilevered oriel bay with heavy diagonal timber corbel brackets.
    - Features timber corner posts, leaded glass window, and dedicated shingled roof.
    """
    height = max(2.20, min(height, floor_h * 0.82))
    frame = get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max)
    facade_rot_mat = frame.rotation

    half_w = width * 0.5

    # 1. Foundation or Console Corbels
    if floor_mode == 'GROUND':
        found_depth = depth + 0.15
        found_width = width + 0.20
        # Foundation extends all the way down to ground level (z=0)
        found_h = max(0.30, z_base)
        create_beveled_box(
            bm,
            size=(found_depth, found_width, found_h),
            location=frame.to_world(Vector((depth * 0.5 + 0.05, 0.0, found_h * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )
    else:  # UPPER floor oriel bay
        # Heavy diagonal console brackets springing from the wall BELOW the oriel
        # (accounting for any jetty / pillared offset) up to the oriel underside,
        # so the feet always land on real wall instead of floating in mid-air.
        if lower_bounds is not None:
            lower = get_facade_frame(side, lower_bounds[0], lower_bounds[1], lower_bounds[2], lower_bounds[3])
            inset = max(0.0, (frame.wall_x - lower.wall_x) * frame.out_x + (frame.wall_y - lower.wall_y) * frame.out_y)
        else:
            inset = 0.0
        foot_x = -inset - 0.10
        head_x = depth * 0.72
        foot_z = z_base - 0.95
        head_z = z_base - 0.04
        dxc = head_x - foot_x
        dzc = head_z - foot_z
        diag_len = math.sqrt(dxc * dxc + dzc * dzc)
        diag_ang = math.atan2(dzc, dxc)
        corbel_euler = (facade_rot_mat @ Matrix.Rotation(-diag_ang, 4, 'Y')).to_euler()
        bracket_spacing = width * 0.36
        for b_sign in [-1.0, 0.0, 1.0]:
            loc_c = Vector(((foot_x + head_x) * 0.5, b_sign * bracket_spacing, (foot_z + head_z) * 0.5))
            create_beveled_box(
                bm,
                size=(diag_len, 0.16, 0.18),
                location=frame.to_world(loc_c),
                rotation=corbel_euler,
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.012
            )

    # 2. Walk-in Interior Wooden Floor & Ceiling Planks
    # Continuous level walk-in floor
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=frame.to_world(Vector((depth * 0.50, 0.0, z_base + 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Walk-in threshold floor board bridging through the house wall cutout
    mw_portal_w = min(1.30, width - 0.45)
    create_beveled_box(
        bm,
        size=(0.28, mw_portal_w - 0.06, 0.058),
        location=frame.to_world(Vector((-0.12, 0.0, z_base + 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )
    # Interior ceiling planks
    create_beveled_box(
        bm,
        size=(depth + 0.04, width - 0.04, 0.06),
        location=frame.to_world(Vector((depth * 0.50, 0.0, z_base + height - 0.03))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.008
    )

    # 3. Hollow Walls: Front Wall & Side Walls (Leaving Rear Open into Main Room)
    wall_mat = MAT_INDEX_WOOD if tier in ('TIER_1', 'TIER_2') else MAT_INDEX_PLASTER_EXT
    col_w = 0.16
    wall_thick = 0.12

    # Collected wall faces so they can be unwrapped at the engine's wall scale
    # (U along the wall run, V vertical) instead of the generic box unwrap.
    wall_side_faces = []
    wall_front_faces = []

    # 3a. Two Side Walls (Left and Right) - framed between timber corner posts
    for s_sign in [-1, 1]:
        wall_side_faces.extend(create_beveled_box(
            bm,
            size=(depth + 0.02, wall_thick, height),
            location=frame.to_world(Vector((depth * 0.50 + 0.01, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=wall_mat,
            bevel_amount=0.010
        ))
        # Wall-anchor timber trim flat at house wall junction
        create_beveled_box(
            bm,
            size=(0.08, col_w, height + 0.04),
            location=frame.to_world(Vector((0.04, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )
        # Outer corner post - thickened + outset 1.8cm to break coplanar
        create_beveled_box(
            bm,
            size=(0.18, 0.18, height + 0.06),
            location=frame.to_world(Vector((depth - col_w * 0.5 + 0.018, (half_w - col_w * 0.5) * s_sign, z_base + height * 0.5))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.014
        )
        # Heavy horizontal timber sill beam along side wall base (hides interior floor)
        create_beveled_box(
            bm,
            size=(depth + 0.06, col_w + 0.02, 0.18),
            location=frame.to_world(Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + 0.04))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.012
        )
        # Horizontal timber top plate beam along side wall top (under roof rafter / cheek)
        create_beveled_box(
            bm,
            size=(depth + 0.04, col_w, 0.12),
            location=frame.to_world(Vector((depth * 0.50, (half_w - col_w * 0.5) * s_sign, z_base + height - 0.04))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    # 3b. Outer Front Wall with Window Cutout.
    # Cap the oriel glazing to the hall's own window size so the outcrop never
    # reads as having a bigger window than the rest of the building.
    win_w = min(width * 0.52, win_w if win_w else 0.95)
    win_h = min(height * 0.46, win_h if win_h else 1.15)
    win_z = z_base + height * 0.52
    win_bot_z = win_z - win_h * 0.5
    win_top_z = win_z + win_h * 0.5

    # Outer front wall center
    f_wall_x = depth - wall_thick * 0.5
    # Front spandrel below window
    spand_h = win_bot_z - z_base
    wall_front_faces.extend(create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, spand_h),
        location=frame.to_world(Vector((f_wall_x, 0.0, z_base + spand_h * 0.5))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=wall_mat,
        bevel_amount=0.010
    ))
    # Front side jambs flanking window
    jamb_w = (width - col_w * 2.0 - win_w) * 0.5 + 0.02
    for s_sign in [-1, 1]:
        wall_front_faces.extend(create_beveled_box(
            bm,
            size=(wall_thick, jamb_w, win_h + 0.04),
            location=frame.to_world(Vector((f_wall_x, (win_w * 0.5 + jamb_w * 0.5 - 0.01) * s_sign, win_z))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=wall_mat,
            bevel_amount=0.008
        ))
    # Front header above window
    head_h = (z_base + height) - win_top_z
    wall_front_faces.extend(create_beveled_box(
        bm,
        size=(wall_thick, width - col_w * 1.5, head_h),
        location=frame.to_world(Vector((f_wall_x, 0.0, win_top_z + head_h * 0.5))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=wall_mat,
        bevel_amount=0.008
    ))
    # Engine-consistent wall UVs: side runs get U along the depth (local X),
    # front runs get U along the width (local Y); both use V vertical at 0.55/m.
    map_local_wall_uv(bm, wall_side_faces, frame.wall_x, frame.wall_y, facade_rot_mat,
                      u_comp=0, v_comp=2, scale=0.55)
    map_local_wall_uv(bm, wall_front_faces, frame.wall_x, frame.wall_y, facade_rot_mat,
                      u_comp=1, v_comp=2, scale=0.55)

    # Heavy horizontal timber sill plate across front wall base (hides interior floor)
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.18),
        location=frame.to_world(Vector((depth - col_w * 0.5 + 0.015, 0.0, z_base + 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )
    # Outer top horizontal header beam across front wall top
    create_beveled_box(
        bm,
        size=(col_w + 0.04, width + 0.08, 0.14),
        location=frame.to_world(Vector((depth - col_w * 0.5 + 0.01, 0.0, z_base + height - 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    # 4. Window assembly - reuses the main building's window construction
    # (reveal lining, exterior casing & stone sill, interior casing, glass panes)
    # so the outcrop matches every other window on the hall.
    from ..openings import build_window_assembly
    normal = (facade_rot_mat @ Vector((1.0, 0.0, 0.0)).to_4d()).to_3d()
    window_center = frame.to_world(Vector((f_wall_x, 0.0, win_z)))
    build_window_assembly(
        bm,
        center=(window_center.x, window_center.y, window_center.z),
        size=(win_w, win_h),
        wall_thickness=wall_thick,
        normal_axis=(normal.x, normal.y),
        has_shutters=True,
    )

    # 5. Dedicated shingled roof (shared outcrop roof builder)
    build_outcrop_roof(
        bm, roof_style, frame,
        z_roof=z_base + height, depth=depth, width=width,
        avail_h=max(0.35, floor_h - height - 0.08), wall_mat=wall_mat,
        wall_thick=wall_thick, shingle_scale=shingle_scale, shingle_rot=shingle_rot,
    )
