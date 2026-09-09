"""
Stylized Fantasy Building Generator for Blender 5.2.
A procedural building generator featuring complete walk-in interiors,
curved sway roofs, timber framing, and rich stylized shaders.
"""

bl_info = {
    "name": "Stylized Fantasy Building Generator",
    "author": "Stylized 3D Studio",
    "version": (1, 5, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Fantasy Building",
    "description": "Quickly create and iterate stylized fantasy buildings with walk-in interiors and materials",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

import bpy
from .properties import FantasyBuildingSettings
from .operators import (
    BUILDING_OT_create,
    BUILDING_OT_regenerate,
    BUILDING_OT_randomize,
    BUILDING_OT_apply_preset,
    BUILDING_OT_toggle_door,
    BUILDING_OT_finalize,
)
from .ui import (
    VIEW3D_PT_fantasy_building_main,
    VIEW3D_PT_fantasy_building_dimensions,
    VIEW3D_PT_fantasy_building_interior,
    VIEW3D_PT_fantasy_building_openings,
    VIEW3D_PT_fantasy_building_roof,
    VIEW3D_PT_fantasy_building_materials,
)

classes = (
    FantasyBuildingSettings,
    BUILDING_OT_create,
    BUILDING_OT_regenerate,
    BUILDING_OT_randomize,
    BUILDING_OT_apply_preset,
    BUILDING_OT_toggle_door,
    BUILDING_OT_finalize,
    VIEW3D_PT_fantasy_building_main,
    VIEW3D_PT_fantasy_building_dimensions,
    VIEW3D_PT_fantasy_building_interior,
    VIEW3D_PT_fantasy_building_openings,
    VIEW3D_PT_fantasy_building_roof,
    VIEW3D_PT_fantasy_building_materials,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fantasy_building_settings = bpy.props.PointerProperty(type=FantasyBuildingSettings)

def unregister():
    if hasattr(bpy.types.Scene, "fantasy_building_settings"):
        try:
            del bpy.types.Scene.fantasy_building_settings
        except Exception:
            pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

if __name__ == "__main__":
    register()
