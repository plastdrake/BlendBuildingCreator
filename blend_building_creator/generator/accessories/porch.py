"""Grounded entry porch: stone/timber arch hood over the main door."""

from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME
from ..roof.gable_roof import build_gable_roof


def build_arched_porch(bm, door_x, front_y, z_ground=0.0, z_floor=0.6,
                       half_span=1.5, height=2.9, tier='TIER_3',
                       plank_direction='HORIZONTAL'):
    """Stone entry porch with an angled two-slope roof and NO gable wall.

    Twin stone piers carry an outer beam; above them the real gable-roof builder
    raises two shingled slopes (correct UVs, bell-cast flare, bargeboards and ridge)
    with the gable end walls suppressed so it reads as a porch hood, not a mini house.
    """
    pier_w = 0.28
    outer_y = front_y - 2.05
    pier_y = outer_y + 0.30
    for s in (-1.0, 1.0):
        px = door_x + s * half_span
        # Slim timber entrance posts (no stone piers).
        create_beveled_box(bm, size=(pier_w + 0.12, pier_w + 0.12, 0.30),
                           location=(px, pier_y, z_ground + 0.15),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)
        create_beveled_box(bm, size=(pier_w, pier_w, height),
                           location=(px, pier_y, z_ground + 0.30 + (height - 0.30) * 0.5),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)
        create_beveled_box(bm, size=(pier_w + 0.16, pier_w + 0.16, 0.18),
                           location=(px, pier_y, z_ground + height + 0.09),
                           mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Outer beam carried by the piers (roof rests on it)
    eave_z = z_ground + height + 0.22
    create_beveled_box(bm, size=(half_span * 2.0 + 0.70, 0.20, 0.22),
                       location=(door_x, pier_y, eave_z),
                       mat_index=MAT_INDEX_TIMBER_FRAME, bevel_amount=0.012)
    # Angled two-slope roof, gable end walls suppressed, ridge runs front-to-back
    build_gable_roof(
        bm,
        x_min=door_x - half_span - 0.12,
        x_max=door_x + half_span + 0.12,
        y_min=front_y - 2.30,
        y_max=front_y,
        z_base=eave_z + 0.10,
        roof_height=1.15,
        overhang=0.30,
        wall_thickness=0.16,
        gable_ends=('FRONT', 'BACK'),
        segments_y=3,
        abut_back=True,
        tier=tier,
        plank_direction=plank_direction,
        roof_flare=0.35,
        gable_walls=False,
    )
