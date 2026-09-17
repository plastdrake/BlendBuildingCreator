"""Shared architectural style helpers.

Small, dependency-free helpers used by the accessory builders so the tier
material language is defined in exactly one place (previously duplicated as a
private ``_tier_wall_mat`` in the civic and town-hall modules).
"""

from .materials import MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD


def tier_wall_mat(tier):
    """Wall material for satellite volumes (towers, annexes).

    Matches the engine's wall logic: dressed stucco/plaster on Tier 3, exposed
    planks/logs on Tier 1-2.
    """
    return MAT_INDEX_PLASTER_EXT if tier == 'TIER_3' else MAT_INDEX_WOOD
