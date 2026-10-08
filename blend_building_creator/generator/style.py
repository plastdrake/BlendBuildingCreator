"""Shared architectural style helpers.

Small, dependency-free helpers used by the accessory builders so the tier
material language is defined in exactly one place (previously duplicated as a
private ``_tier_wall_mat`` in the civic and town-hall modules).
"""

from .materials import MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD, MAT_INDEX_STONE


def is_tier1_wattle_daub(props):
    """Check if a Tier 1 building uses wattle & daub instead of hewn logs."""
    if not props:
        return False
    override = getattr(props, 'wall_material_override', 'AUTO')
    if override == 'WATTLE_DAUB':
        return True
    if override == 'LOGS':
        return False
    tier = getattr(props, 'tier', getattr(props, 'material_tier', 'TIER_3'))
    if tier != 'TIER_1':
        return False
    style = getattr(props, 'tier1_wall_style', 'AUTO')
    if style == 'WATTLE_DAUB':
        return True
    if style == 'LOGS':
        return False
    # AUTO mode: cottages, hovels, farmhouses, bakeries, or odd seeds use wattle & daub
    arch = getattr(props, 'archetype', 'NONE')
    if arch in ('COTTAGE', 'HOVEL', 'FARM', 'BAKERY', 'TAVERN', 'ALCHEMIST'):
        return True
    if arch in ('WOODCUTTER', 'LODGE', 'CABIN', 'HUNTER', 'MINE', 'MILL'):
        return False
    seed = getattr(props, 'seed', 42)
    return (seed % 2 == 1)


def is_tier1_wood_shingles(props):
    """Check if Tier 1 uses shabby wood shingles instead of thatch bundles."""
    return get_effective_roof_material(props) == 'WOOD_SHINGLES'


def get_effective_roof_material(props):
    """Resolve the active roofing material: 'THATCH', 'WOOD_SHINGLES', 'TERRACOTTA', 'SLATE'."""
    if not props:
        return 'TERRACOTTA'
    override = getattr(props, 'roof_material_override', 'AUTO')
    if override != 'AUTO':
        return override
    tier = getattr(props, 'tier', getattr(props, 'material_tier', 'TIER_2'))
    if tier == 'TIER_1':
        t1_roof = getattr(props, 'tier1_roof_style', 'AUTO')
        if t1_roof == 'WOOD_SHINGLES':
            return 'WOOD_SHINGLES'
        if t1_roof == 'THATCH':
            return 'THATCH'
        # AUTO mode: timber-heavy archetypes or odd seeds use wood shingles
        arch = getattr(props, 'archetype', 'NONE')
        if arch in ('WOODCUTTER', 'LODGE', 'CABIN', 'HUNTER', 'MINE', 'MILL', 'BARRACKS', 'TOOLSMITH', 'FURNITURE_MAKER', 'STABLE'):
            return 'WOOD_SHINGLES'
        seed = getattr(props, 'seed', 42)
        if (seed % 3 == 0):
            return 'WOOD_SHINGLES'
        return 'THATCH'
    elif tier == 'TIER_2':
        return 'TERRACOTTA'
    else:
        return 'SLATE'


def get_effective_wall_material(props):
    """Resolve the active wall material: 'AUTO', 'LOGS', 'WATTLE_DAUB', 'WOOD_PLANKS', 'STUCCO', 'STONE'."""
    if not props:
        return 'AUTO'
    override = getattr(props, 'wall_material_override', 'AUTO')
    if override != 'AUTO':
        return override
    tier = getattr(props, 'tier', getattr(props, 'material_tier', 'TIER_2'))
    if tier == 'TIER_1':
        return 'WATTLE_DAUB' if is_tier1_wattle_daub(props) else 'LOGS'
    elif tier == 'TIER_2':
        return 'WOOD_PLANKS'
    else:
        return 'STUCCO'


def tier_wall_mat(tier, props=None):
    """Wall material for satellite volumes (towers, annexes).

    Stone override: solid fortress ashlar masonry.
    Tier 3: dressed ivory stucco/plaster.
    Tier 1 (wattle & daub): wattle & daub plaster.
    Tier 1 (logs) & Tier 2: wooden planks / siding.
    """
    if props:
        eff_wall = get_effective_wall_material(props)
        if eff_wall == 'STONE':
            return MAT_INDEX_STONE
        elif eff_wall in ('WATTLE_DAUB', 'STUCCO'):
            return MAT_INDEX_PLASTER_EXT
        elif eff_wall in ('LOGS', 'WOOD_PLANKS'):
            return MAT_INDEX_WOOD

    if tier == 'TIER_3' or (tier == 'TIER_1' and props and is_tier1_wattle_daub(props)):
        return MAT_INDEX_PLASTER_EXT
    return MAT_INDEX_WOOD

