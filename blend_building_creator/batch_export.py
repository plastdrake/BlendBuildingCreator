"""Background entry point for the complete FBX preset batch export."""

import bpy

from . import register
from .operators import _export_fbx_jobs
from .presets import BUILDING_FAMILIES, PRESETS


def _export_category_for_family(family):
    if family.get("id") == "KNIGHTS_MANOR":
        return "MILITARY"
    if family.get("id") == "SCAFFOLD":
        return "CONSTRUCTION_BUILDINGS"
    if family.get("id") == "SCAFFOLD_EMPTY":
        return "CONSTRUCTION"
    category = family.get("category", "OTHER")
    if isinstance(category, (list, tuple, set)):
        return next(iter(category), "OTHER")
    return category


def _nasher_jobs_last(jobs):
    """Keep the expensive castle jobs at the end of a complete batch."""
    return sorted(jobs, key=lambda job: job[0].get("id") == "NASHERS_MANOR")


def _family_faction(family):
    return family.get("faction", "HUMAN")


def _jobs_for_scope(category='ALL', family_id='ALL', tier='ALL', faction='ALL'):
    """Build the export job list for a faction / category / family / tier scope."""
    return [
        (family, tier_label, preset_key, description)
        for family in BUILDING_FAMILIES
        if (faction == 'ALL' or faction == _family_faction(family))
        and (category == 'ALL' or category == _export_category_for_family(family))
        and (family_id == 'ALL' or family['id'] == family_id)
        for tier_label, preset_key, description in family['tiers']
        if preset_key in PRESETS
        and (tier == 'ALL' or tier_label == tier)
    ]


def export_all(output_dir, keep_buildings=False, faction='ALL'):
    """Register the addon if needed and export every valid preset tier.

    ``faction`` limits the batch to a single faction ('HUMAN', 'HAJFIN', ...); the
    default 'ALL' exports every faction.
    """
    if not hasattr(bpy.types.Scene, "fantasy_building_settings"):
        register()

    jobs = _jobs_for_scope(faction=faction)
    count = _export_fbx_jobs(
        bpy.context,
        _nasher_jobs_last(jobs),
        output_dir,
        keep_buildings=keep_buildings,
    )
    print(f"Completed: {count} FBX files exported to {bpy.path.abspath(output_dir)} ({faction} faction scope)")


def export_selected(output_dir, category='ALL', family_id='ALL', tier='ALL',
                    keep_buildings=False, faction='ALL'):
    """Export a faction, category, preset family, or individual preset tier."""
    if not hasattr(bpy.types.Scene, "fantasy_building_settings"):
        register()

    jobs = _jobs_for_scope(category=category, family_id=family_id, tier=tier,
                           faction=faction)
    count = _export_fbx_jobs(
        bpy.context,
        jobs,
        output_dir,
        keep_buildings=keep_buildings,
    )
    print(f"Completed: {count} FBX files exported to {bpy.path.abspath(output_dir)}")
