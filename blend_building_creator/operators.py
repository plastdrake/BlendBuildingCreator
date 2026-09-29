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
    
    preset_key: bpy.props.StringProperty(name="Preset Key", default="TOWN_HALL_T1")
    
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


class BUILDING_OT_create_door_blade(bpy.types.Operator):
    """Create a standalone door blade with its hinge and pivot at (0, 0, 0) for Unreal Engine interactive doors"""
    bl_idname = "building.create_door_blade"
    bl_label = "Create Door Blade (Pivot at 0,0)"
    bl_description = "Generate a standalone door blade mesh with pivot and hinge placed at local (0, 0, 0)"
    bl_options = {'REGISTER', 'UNDO'}

    width: bpy.props.FloatProperty(
        name="Width",
        description="Width of the door blade in meters",
        default=1.0,
        min=0.4, max=3.0,
        unit='LENGTH'
    )
    height: bpy.props.FloatProperty(
        name="Height",
        description="Height of the door blade in meters",
        default=2.2,
        min=1.0, max=4.0,
        unit='LENGTH'
    )
    shape: bpy.props.EnumProperty(
        name="Shape",
        description="Profile shape of the door blade",
        items=[
            ('SQUARE', "Square / Rectangular", "Rectangular door blade for square frames"),
            ('ARCHED', "Arched", "Curved arched top door blade for stone arched portals"),
        ],
        default='SQUARE'
    )
    hinge_side: bpy.props.EnumProperty(
        name="Hinge Placement",
        description="Side of the door blade where the hinge and pivot are located",
        items=[
            ('LEFT', "Left Hinge", "Hinge at (0, 0), door blade extends along +X"),
            ('RIGHT', "Right Hinge", "Hinge at (0, 0), door blade extends along -X"),
        ],
        default='LEFT'
    )
    leaf_type: bpy.props.EnumProperty(
        name="Door Type",
        description="Type of door leaf to generate",
        items=[
            ('SINGLE', "Single Door", "Full single door blade with centered arch apex if arched"),
            ('DOUBLE_LEAF', "Double Door Leaf (Half)", "One side of a double door pair; arch rises to apex at meeting stile"),
        ],
        default='SINGLE',
    )
    use_scene_settings: bpy.props.BoolProperty(
        name="Use Panel Settings",
        description="Initialize width, height, shape, and hinge side from current scene settings",
        default=True
    )

    def invoke(self, context, event):
        props = getattr(context.scene, 'fantasy_building_settings', None)
        if props and self.use_scene_settings:
            self.width = getattr(props, 'door_blade_width', 1.0)
            self.height = getattr(props, 'door_blade_height', 2.2)
            self.shape = getattr(props, 'door_blade_shape', 'SQUARE')
            self.hinge_side = getattr(props, 'door_blade_hinge', 'LEFT')
            self.leaf_type = getattr(props, 'door_blade_leaf_type', 'SINGLE')
        return self.execute(context)

    def execute(self, context):
        import bmesh
        from .generator.openings import build_standalone_door_blade
        from .generator.materials import create_stylized_timber, create_stylized_iron
        from .generator.mesh_utils import apply_organic_shading

        props = getattr(context.scene, 'fantasy_building_settings', None)
        if props and self.use_scene_settings:
            if not self.properties.is_property_set("width"):
                self.width = getattr(props, 'door_blade_width', 1.0)
            if not self.properties.is_property_set("height"):
                self.height = getattr(props, 'door_blade_height', 2.2)
            if not self.properties.is_property_set("shape"):
                self.shape = getattr(props, 'door_blade_shape', 'SQUARE')
            if not self.properties.is_property_set("hinge_side"):
                self.hinge_side = getattr(props, 'door_blade_hinge', 'LEFT')
            if not self.properties.is_property_set("leaf_type"):
                self.leaf_type = getattr(props, 'door_blade_leaf_type', 'SINGLE')

        shape_str = self.shape.capitalize()
        type_str = "DoubleLeaf" if self.leaf_type == 'DOUBLE_LEAF' else "Single"
        mesh_name = f"Door_Blade_{shape_str}_{type_str}_{self.hinge_side.capitalize()}_{self.width:.2f}m"
        mesh = bpy.data.meshes.new(name=mesh_name)
        obj = bpy.data.objects.new(name=mesh_name, object_data=mesh)

        # Setup clean 2-material slots (Slot 0: Wood Door, Slot 1: Iron) BEFORE bm.to_mesh
        # so Blender preserves face material indices and never assigns stone.
        clr_tf = getattr(props, 'color_timber_frame', (0.24, 0.14, 0.08, 1.0)) if props else (0.24, 0.14, 0.08, 1.0)
        custom_door = getattr(props, 'custom_door', None) if props else None
        custom_tf = getattr(props, 'custom_timber_frame', None) if props else None
        mat_wood = custom_door or custom_tf or create_stylized_timber("M_Building_Timber", color=clr_tf)

        custom_iron = getattr(props, 'custom_iron', None) if props else None
        mat_iron = custom_iron or create_stylized_iron("M_Building_Iron")

        obj.data.materials.clear()
        obj.data.materials.append(mat_wood)  # Slot 0
        obj.data.materials.append(mat_iron)  # Slot 1

        bm = bmesh.new()
        build_standalone_door_blade(
            bm,
            width=self.width,
            height=self.height,
            thickness=0.055,
            shape=self.shape,
            hinge_side=self.hinge_side,
            door_blade_type=self.leaf_type,
            mat_wood_idx=0,
            mat_iron_idx=1
        )
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        cursor_loc = context.scene.cursor.location
        if cursor_loc.length > 0.05:
            obj.location = cursor_loc.copy()
        else:
            obj.location = (0.0, 0.0, 0.0)

        context.collection.objects.link(obj)

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        apply_organic_shading(obj)

        obj["is_door_blade"] = True
        obj["hinge_side"] = self.hinge_side
        obj["door_shape"] = self.shape
        obj["door_leaf_type"] = self.leaf_type

        self.report({'INFO'}, f"Created '{obj.name}' (Width: {self.width:.2f}m, Hinge & Pivot at 0,0)")
        return {'FINISHED'}


class BUILDING_OT_create_prop(bpy.types.Operator):
    """Create a single furniture/prop piece (same builder as interior furnishing)"""
    bl_idname = "building.create_prop"
    bl_label = "Create Prop"
    bl_description = "Create one catalogue prop as its own object at the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}

    prop_key: bpy.props.StringProperty(name="Prop Key", default="")
    prop_scale: bpy.props.FloatProperty(name="Scale", default=1.0, min=0.25, max=4.0)
    prop_variant: bpy.props.StringProperty(name="Options", default="")

    def execute(self, context):
        from .generator.accessories.prop_registry import PROP_REGISTRY
        from .generator.accessories.standalone import create_standalone_prop_mesh
        sprops = context.scene.fantasy_building_settings
        key = self.prop_key or getattr(sprops, 'standalone_prop', 'CHAIR')
        if key not in PROP_REGISTRY:
            self.report({'ERROR'}, f"Unknown prop: {key}")
            return {'CANCELLED'}
        scale = self.prop_scale or getattr(sprops, 'standalone_prop_scale', 1.0)
        variant = self.prop_variant or getattr(sprops, 'standalone_prop_variant', '')
        spec = PROP_REGISTRY[key]
        mesh = bpy.data.meshes.new(name=f"Prop_{spec.key}")
        obj = bpy.data.objects.new(name=f"Prop_{spec.label.replace(' ', '_')}", object_data=mesh)
        cursor_loc = context.scene.cursor.location
        obj.location = cursor_loc.copy() if cursor_loc.length > 0.05 else (0.0, 0.0, 0.0)
        context.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        create_standalone_prop_mesh(obj, sprops, key, scale=scale, variant=variant)
        obj["is_fantasy_prop"] = True
        obj["prop_key"] = key
        self.report({'INFO'}, f"Created prop '{obj.name}' ({spec.label})")
        return {'FINISHED'}


class BUILDING_OT_create_all_props(bpy.types.Operator):
    """Create every catalogue prop at once, spread on a grid for quick testing"""
    bl_idname = "building.create_all_props"
    bl_label = "Create All Props"
    bl_description = "Spawn one of every catalogue prop on a grid at the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}

    columns: bpy.props.IntProperty(name="Columns", default=7, min=1, max=14)
    spacing: bpy.props.FloatProperty(name="Spacing", default=3.0, min=1.5, max=6.0)

    def execute(self, context):
        from .generator.accessories.prop_registry import list_props
        from .generator.accessories.standalone import create_standalone_prop_mesh
        sprops = context.scene.fantasy_building_settings
        specs = list_props('ALL')
        cursor_loc = context.scene.cursor.location
        base = cursor_loc.copy() if cursor_loc.length > 0.05 else (0.0, 0.0, 0.0)
        try:
            base_x, base_y, base_z = base[0], base[1], base[2]
        except Exception:
            base_x, base_y, base_z = 0.0, 0.0, 0.0
        bpy.ops.object.select_all(action='DESELECT')
        created = []
        for i, spec in enumerate(specs):
            row, col = divmod(i, max(1, self.columns))
            mesh = bpy.data.meshes.new(name=f"Prop_{spec.key}")
            obj = bpy.data.objects.new(
                name=f"Prop_{spec.label.replace(' ', '_')}", object_data=mesh)
            obj.location = (base_x + col * self.spacing,
                            base_y - row * self.spacing, base_z)
            context.collection.objects.link(obj)
            create_standalone_prop_mesh(obj, sprops, spec.key)
            obj["is_fantasy_prop"] = True
            obj["prop_key"] = spec.key
            obj.select_set(True)
            created.append(obj)
        if created:
            context.view_layer.objects.active = created[0]
        self.report({'INFO'}, f"Created {len(created)} test props on a grid")
        return {'FINISHED'}


class BUILDING_OT_furnish_interior(bpy.types.Operator):
    """Furnish the interior of the active building in one click"""
    bl_idname = "building.furnish_interior"
    bl_label = "Furnish Interior Now"
    bl_description = "Enable interior furnishing and regenerate the active building"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get("is_fantasy_building", False)

    def execute(self, context):
        from .generator.building import generate_building
        sprops = context.scene.fantasy_building_settings
        sprops.has_interior_furnishing = True
        generate_building(context.active_object, sprops)
        self.report({'INFO'}, "Interior furnished!")
        return {'FINISHED'}

