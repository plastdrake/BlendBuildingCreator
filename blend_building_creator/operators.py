"""
Operators for creating, randomizing, applying presets, and finalizing stylized fantasy buildings.
"""

import bpy
import random
from .generator.building import generate_building
from .presets import apply_preset

class BUILDING_OT_create(bpy.types.Operator):
    """Create a new Stylized Fantasy Building in the active scene"""
    bl_idname = "building.create_fantasy_building"
    bl_label = "Create Fantasy Building"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Create a new mesh and object
        mesh = bpy.data.meshes.new(name="Fantasy_Building_Mesh")
        obj = bpy.data.objects.new(name="Fantasy_Building", object_data=mesh)
        
        # Link to current collection
        context.collection.objects.link(obj)
        
        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Tag as building
        obj["is_fantasy_building"] = True
        
        # Generate with current scene settings
        props = context.scene.fantasy_building_settings
        generate_building(obj, props)
        
        self.report({'INFO'}, "Created Stylized Fantasy Building!")
        return {'FINISHED'}

class BUILDING_OT_regenerate(bpy.types.Operator):
    """Regenerate the active fantasy building geometry"""
    bl_idname = "building.regenerate"
    bl_label = "Regenerate"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False)
        
    def execute(self, context):
        obj = context.active_object
        props = context.scene.fantasy_building_settings
        generate_building(obj, props)
        self.report({'INFO'}, "Building regenerated!")
        return {'FINISHED'}

class BUILDING_OT_randomize(bpy.types.Operator):
    """Roll a new random seed and variation for the active fantasy building"""
    bl_idname = "building.randomize_seed"
    bl_label = "Randomize / Re-roll"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False)
        
    def execute(self, context):
        props = context.scene.fantasy_building_settings
        props.seed = random.randint(1, 999999)
        
        # Optionally jitter dimensions slightly for fun variety
        props.wonkiness = random.uniform(0.04, 0.12)
        props.roof_sway = random.uniform(0.20, 0.40)
        
        obj = context.active_object
        generate_building(obj, props)
        self.report({'INFO'}, f"Rolled new building design (Seed: {props.seed})")
        return {'FINISHED'}

class BUILDING_OT_apply_preset(bpy.types.Operator):
    """Apply an architectural style preset to the building"""
    bl_idname = "building.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_key: bpy.props.StringProperty(name="Preset Key", default="TAVERN")
    
    def execute(self, context):
        props = context.scene.fantasy_building_settings
        apply_preset(props, self.preset_key)
        
        obj = context.active_object
        if obj and obj.get("is_fantasy_building", False):
            generate_building(obj, props)
            
        self.report({'INFO'}, f"Applied preset: {self.preset_key}")
        return {'FINISHED'}

class BUILDING_OT_toggle_door(bpy.types.Operator):
    """Toggle the front entrance door between Closed and Open for walk-in exploration"""
    bl_idname = "building.toggle_door"
    bl_label = "Toggle Door Open/Close"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False)
        
    def execute(self, context):
        props = context.scene.fantasy_building_settings
        if props.door_angle > 10.0:
            props.door_angle = 0.0 # Close
        else:
            props.door_angle = 75.0 # Open
            
        obj = context.active_object
        generate_building(obj, props)
        return {'FINISHED'}

class BUILDING_OT_finalize(bpy.types.Operator):
    """Finalize the building mesh into a standard editable mesh (removes generator tag)"""
    bl_idname = "building.finalize_mesh"
    bl_label = "Finalize / Apply Mesh"
    bl_description = "Convert parametric building into a standard editable mesh for sculpting or export"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False)
        
    def execute(self, context):
        obj = context.active_object
        del obj["is_fantasy_building"]
        self.report({'INFO'}, f"Building '{obj.name}' finalized to standard mesh!")
        return {'FINISHED'}
