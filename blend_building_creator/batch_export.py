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


def export_all(output_dir, keep_buildings=False):
    """Register the addon if needed and export every valid preset tier."""
    if not hasattr(bpy.types.Scene, "fantasy_building_settings"):
        register()

    jobs = [
        (family, tier_label, preset_key, description)
        for family in BUILDING_FAMILIES
        for tier_label, preset_key, description in family["tiers"]
        if preset_key in PRESETS
    ]
    count = _export_fbx_jobs(
        bpy.context,
        jobs,
        output_dir,
        keep_buildings=keep_buildings,
    )
    print(f"Completed: {count} FBX files exported to {bpy.path.abspath(output_dir)}")


def export_selected(output_dir, category='ALL', family_id='ALL', tier='ALL',
                    keep_buildings=False):
    """Export a category, preset family, or individual preset tier."""
    if not hasattr(bpy.types.Scene, "fantasy_building_settings"):
        register()

    jobs = [
        (family, tier_label, preset_key, description)
        for family in BUILDING_FAMILIES
        if (category == 'ALL' or category == _export_category_for_family(family))
        and (family_id == 'ALL' or family['id'] == family_id)
        for tier_label, preset_key, description in family['tiers']
        if preset_key in PRESETS
        and (tier == 'ALL' or tier_label == tier)
    ]
    count = _export_fbx_jobs(
        bpy.context,
        jobs,
        output_dir,
        keep_buildings=keep_buildings,
    )
    print(f"Completed: {count} FBX files exported to {bpy.path.abspath(output_dir)}")
