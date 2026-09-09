"""
Operators for creating, randomizing, applying presets, resetting, and finalizing stylized fantasy buildings.
"""

import bpy
import random
import json
from .generator.building import generate_building
from .presets import apply_preset

def get_props_dict(props):
    """Serialize all fantasy building properties into a dictionary."""
    data = {}
    for p in props.bl_rna.properties:
        if p.identifier in ('rna_type', 'name'):
            continue
        try:
            val = getattr(props, p.identifier)
            if hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
                data[p.identifier] = list(val)
            else:
                data[p.identifier] = val
        except Exception:
            pass
    return data

def set_props_from_dict(props, data):
    """Apply dictionary values onto a FantasyBuildingSettings property group."""
    old_auto = getattr(props, 'auto_update', True)
    props.auto_update = False
    for k, v in data.items():
        if k in ('auto_update', 'rna_type', 'name'):
            continue
        if hasattr(props, k):
            try:
                setattr(props, k, v)
            except Exception:
                pass
    props.auto_update = old_auto

def reset_props_to_defaults(props):
    """Reset all properties on a FantasyBuildingSettings instance to their defined default values."""
    old_auto = getattr(props, 'auto_update', True)
    props.auto_update = False
    for p in props.bl_rna.properties:
        if p.identifier in ('rna_type', 'name', 'auto_update'):
            continue
        try:
            props.property_unset(p.identifier)
        except Exception:
            pass
    props.auto_update = old_auto

class BUILDING_OT_create(bpy.types.Operator):
    """Create a new Stylized Fantasy Building in the active scene"""
    bl_idname = "building.create_fantasy_building"
    bl_label = "Create Fantasy Building"
    bl_options = {'REGISTER', 'UNDO'}
    
    reset_to_defaults: bpy.props.BoolProperty(
        name="Reset to Defaults",
        description="Reset properties to clean factory defaults when creating a new building",
        default=False
    )
    
    def execute(self, context):
        props = context.scene.fantasy_building_settings
        if self.reset_to_defaults:
            reset_props_to_defaults(props)
            
        # Create a new mesh and object
        mesh = bpy.data.meshes.new(name="Fantasy_Building_Mesh")
        obj = bpy.data.objects.new(name="Fantasy_Building", object_data=mesh)
        
        # Determine spawn location
        # If 3D cursor is not at (0, 0, 0), spawn at 3D cursor
        cursor_loc = context.scene.cursor.location
        if cursor_loc.length > 0.05:
            obj.location = cursor_loc.copy()
        else:
            # Check existing fantasy buildings to prevent visual overlap
            existing_buildings = [o for o in context.scene.objects if o.get("is_fantasy_building", False)]
            if existing_buildings:
                max_x = max(o.location.x for o in existing_buildings)
                obj.location.x = max_x + props.width + 3.0
                obj.location.y = 0.0
                obj.location.z = 0.0
                
        # Link to current collection
        context.collection.objects.link(obj)
        
        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Tag as building
        obj["is_fantasy_building"] = True
        
        # Generate with current scene settings
        generate_building(obj, props)
        
        # Store settings on object for persistent recall
        try:
            obj["building_settings"] = json.dumps(get_props_dict(props))
        except Exception:
            pass
        
        self.report({'INFO'}, f"Created '{obj.name}' at {obj.location.x:.1f}, {obj.location.y:.1f}, {obj.location.z:.1f}")
        return {'FINISHED'}

class BUILDING_OT_reset(bpy.types.Operator):
    """Reset building generator settings to clean factory defaults"""
    bl_idname = "building.reset_settings"
    bl_label = "Reset to Defaults"
    bl_description = "Reset all building generator settings to default values"
    bl_options = {'REGISTER', 'UNDO'}
    
    regenerate_active: bpy.props.BoolProperty(
        name="Regenerate Active",
        description="Also regenerate the currently active fantasy building with default settings",
        default=True
    )
    
    def execute(self, context):
        props = context.scene.fantasy_building_settings
        reset_props_to_defaults(props)
        
        obj = context.active_object
        if self.regenerate_active and obj and obj.get("is_fantasy_building", False):
            generate_building(obj, props)
            try:
                obj["building_settings"] = json.dumps(get_props_dict(props))
            except Exception:
                pass
            self.report({'INFO'}, "Reset settings to defaults and regenerated active building!")
        else:
            self.report({'INFO'}, "Reset settings to defaults for new building creation!")
        return {'FINISHED'}

class BUILDING_OT_load_settings(bpy.types.Operator):
    """Load generator settings from the active selected building"""
    bl_idname = "building.load_settings"
    bl_label = "Load Settings from Active"
    bl_description = "Restore parameters previously used to generate this specific building"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False) and "building_settings" in obj
        
    def execute(self, context):
        obj = context.active_object
        try:
            data = json.loads(obj["building_settings"])
            props = context.scene.fantasy_building_settings
            set_props_from_dict(props, data)
            self.report({'INFO'}, f"Loaded generator settings from '{obj.name}'")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load settings: {e}")
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
