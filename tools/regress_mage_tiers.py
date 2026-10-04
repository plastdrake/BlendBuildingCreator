"""Final regression: all three mage tiers build clean after phases 1-4."""
import bpy
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
from blend_building_creator.presets import apply_preset

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

blend_building_creator.register()
props = bpy.context.scene.fantasy_building_settings

for preset in ('MAGE_TOWER_T1', 'MAGE_TOWER_T2', 'MAGE_TOWER_T3'):
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH' and obj.name.startswith("Fantasy"):
            bpy.data.objects.remove(obj, do_unlink=True)
    apply_preset(props, preset)
    props.has_interior_furnishing = True
    bpy.ops.building.create_fantasy_building()
    obj = bpy.context.active_object
    print(f"REGRESS {preset}: verts={len(obj.data.vertices)} "
          f"dims=({obj.dimensions.x:.1f}, {obj.dimensions.y:.1f}, {obj.dimensions.z:.1f})")
print("REGRESSION COMPLETE")
