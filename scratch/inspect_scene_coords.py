import bpy
import json

bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='INFANTRY_BARRACKS_T3')

obj = bpy.context.active_object
print("Active object:", obj.name if obj else "None")
if obj:
    print("Object location:", obj.location)
    props = bpy.context.scene.fantasy_building_settings
    print(f"Props: width={props.width}, depth={props.depth}, shape={props.shape}")
    print(f"palisade={props.has_palisade}, offset={props.palisade_offset}")
    print(f"military_props={props.has_military_props}, count={props.military_props_count}")
    print(f"bastion_towers={props.has_bastion_towers}, count={props.bastion_tower_count}")
    print("Mesh vert count:", len(obj.data.vertices))
