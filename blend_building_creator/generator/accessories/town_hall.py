"""Town Hall composer: multi-volume sprawling civic composition.

Layers satellite volumes around the engine-built main hall so Tier 2/3 read
like the storybook references instead of a single box:
- side annex: 1-2 storey half-timbered volume with its own perpendicular gable
  roof, surface windows, corner boards and an upper oriel.
- forecourt walls: low stone rampart walls with gate posts stitching tower and
  annex into one courtyard front; the entry ramp leaves through the gate.
- clock-tower arch passage lives in civic.build_clock_tower (arch_passage).
"""

import math
import bmesh
from mathutils import Vector, Matrix
from ..mesh_utils import (
    create_box, create_beveled_box,
)
from ..walls import build_facade_timber
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER,
    MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_FLOOR,
)
from ..roof.gable_roof import build_gable_roof
from ..walls import build_wall_with_opening
from ..openings import build_window_assembly
from ..style import tier_wall_mat
from .mini_wing import build_mini_wing
from .rampart import build_rampart_walk
from .annex import build_side_annex


def _surface_window(bm, x, y, z, w=0.9, h=1.2, facing='front', shutters=True):
    """Window mounted proud of a solid annex wall (no cutout needed)."""
    if facing == 'front':  # -Y
        create_beveled_box(bm, size=(w + 0.24, 0.12, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_box(bm, size=(w, 0.10, h), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.08, 0.12, h), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(w, 0.12, 0.08), location=(x, y - 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(w + 0.34, 0.16, 0.09), location=(x, y - 0.03, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        if shutters:
            for s in (-1.0, 1.0):
                create_box(bm, size=(0.32, 0.05, h + 0.05),
                           location=(x + s * (w * 0.5 + 0.30), y - 0.01, z),
                           mat_index=MAT_INDEX_WOOD)
    elif facing == 'back':  # +Y
        create_beveled_box(bm, size=(w + 0.24, 0.12, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        create_box(bm, size=(w, 0.10, h), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.08, 0.12, h), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(w, 0.12, 0.08), location=(x, y + 0.02, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(w + 0.34, 0.16, 0.09), location=(x, y + 0.03, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    elif facing == 'outer':  # away from main hall: +/-X given by out_sgn
        raise ValueError("use facing='left' or 'right'")
    elif facing in ('left', 'right'):  # -X / +X
        create_beveled_box(bm, size=(0.12, w + 0.24, h + 0.24), location=(x, y, z),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.01)
        sgn = -1.0 if facing == 'left' else 1.0
        create_box(bm, size=(0.10, w, h), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_GLASS)
        create_box(bm, size=(0.12, 0.08, h), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_box(bm, size=(0.12, w, 0.08), location=(x + sgn * 0.02, y, z),
                   mat_index=MAT_INDEX_TIMBER)
        create_beveled_box(bm, size=(0.16, w + 0.34, 0.09),
                           location=(x + sgn * 0.03, y, z - h * 0.5 - 0.10),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
        if shutters:
            for s in (-1.0, 1.0):
                create_box(bm, size=(0.05, 0.32, h + 0.05),
                           location=(x + sgn * 0.01, y + s * (w * 0.5 + 0.30), z),
                           mat_index=MAT_INDEX_WOOD)


def build_town_hall_composer(bm, props, ctx):
    """Compose annex + forecourt around the main hall. Returns annex outer X."""
    tier = ctx.get('tier', 'TIER_3')
    base_hx = ctx['base_hx']
    base_d = ctx['base_d']
    found_h = ctx['found_h']
    floor_h = ctx['floor_h']
    num_floors = ctx['num_floors']
    wing_front = ctx['wing_front']
    door_x = ctx.get('door_x', 0.0)
    seed = ctx.get('seed', 42)

    tower_side = getattr(props, 'clock_tower_side', 'RIGHT')
    t_size = getattr(props, 'clock_tower_size', 3.0)
    has_tower = getattr(props, 'has_clock_tower', False)

    annex_outer = None
    if getattr(props, 'has_side_annex', False):
        a_side = -1.0 if tower_side == 'RIGHT' else 1.0
        a_floors = max(1, min(2, getattr(props, 'annex_floors', 2)))
        a_w = 5.2 if tier != 'TIER_1' else 4.4
        a_d = 4.0 if tier != 'TIER_1' else 3.4
        a_roof = 3.0 if tier == 'TIER_3' else 2.6
        # Annex centered on the side wall so its walk-in portal lines up with
        # the doorway cut into the main hall wall (y = 0).
        cy0 = -a_w * 0.5
        cy1 = a_w * 0.5
        annex_outer = build_side_annex(
            bm, side_sgn=a_side, main_hx=base_hx, main_cy0=cy0, main_cy1=cy1,
            z_ground=0.0, found_h=found_h, floors=a_floors, floor_h=floor_h,
            tier=tier, width=a_w, depth=a_d, roof_h=a_roof,
            plank_direction=getattr(props, 'plank_direction', 'HORIZONTAL'),
            main_bounds_by_floor=ctx.get('floor_wall_bounds', None),
            timber_framing=bool(getattr(props, 'has_timber_framing', True)),
            diagonals=bool(getattr(props, 'timber_diagonals', True)),
        )

    # Forecourt wall stitched between tower and annex (or main corners as fallback)
    if has_tower:
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        t_cx = t_sgn * (base_hx + t_size * 0.5 - 0.7)
        tower_inner = t_cx - t_sgn * t_size * 0.5
    else:
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        tower_inner = t_sgn * base_hx
    if annex_outer is not None:
        x_left = min(tower_inner, annex_outer) + 0.4
        x_right = max(tower_inner, annex_outer) - 0.4
    else:
        x_left, x_right = -base_hx + 0.4, base_hx - 0.4
    # NOTE: the front stone forecourt wall was removed by request - it read as a
    # wall stuck onto the front of the hall. The side rampart below replaces it.

    # Side rampart walk (Tier 3): elevated deck + parapets + descent ramp.
    # The deck starts inside the clock tower and runs back along the side so the
    # tower walk and the rampart read as one continuous elevated walk; the ramp
    # then descends beyond the corner turret along the deck's outer edge.
    if getattr(props, 'has_side_rampart', False):
        r_side = getattr(props, 'rampart_side', 'RIGHT')
        r_sgn = 1.0 if r_side == 'RIGHT' else -1.0
        fl1 = ctx.get('fl1_bounds', None)
        if fl1 is not None:
            r_face = fl1[1] if r_sgn > 0 else fl1[0]
        else:
            r_face = r_sgn * ctx['base_hx']
        base_hy = ctx['base_d'] * 0.5
        t_sgn = 1.0 if tower_side == 'RIGHT' else -1.0
        has_turrets = bool(getattr(props, 'has_corner_turrets', False))
        tr_half = max(1.0, min(2.0, getattr(props, 'corner_turret_size', 1.35)))
        deck_top = found_h + ctx.get('floor_h', 3.0) + 0.11
        ramp_len = deck_top * 1.9 + 1.3
        if has_tower and t_sgn == r_sgn:
            t_cy = wing_front + t_size * 0.5 - 0.25
            # The ramp's foot sits just behind the tower's stepped plinth so it
            # never pokes through the tower wall: you run through the tower gate
            # and straight up the ramp onto the walk.
            t_plinth = t_size * 0.5 + 0.45
            deck_y0 = (t_cy + t_plinth) + 0.10 + ramp_len
        else:
            deck_y0 = -3.0
        if has_turrets:
            # The corner towers sit on the back wall now, so the walk can run
            # all the way to the back corner.
            deck_y1 = base_hy + 0.45
        else:
            deck_y1 = deck_y0 + 7.0
        if deck_y1 - deck_y0 < 5.5:
            deck_y1 = deck_y0 + 5.5
        build_rampart_walk(bm, side_sgn=r_sgn, wall_face_x=r_face,
                           deck_cy=(deck_y0 + deck_y1) * 0.5,
                           deck_len=deck_y1 - deck_y0,
                           deck_top_z=deck_top,
                           width=2.6, tier=tier, ramp_at_back=False,
                           battlements=bool(getattr(props, 'has_battlements', False)),
                           battlement_style=getattr(props, 'battlement_style', 'STONE'))
    return annex_outer
