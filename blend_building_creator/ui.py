"""
User Interface Panels in Blender 3D Viewport Sidebar (N-Panel).
Features clean layout, collapsible sections, style presets, and live parameter sliders.
"""

import bpy

class VIEW3D_PT_fantasy_building_main(bpy.types.Panel):
    """Main panel for Stylized Fantasy Building Generator"""
    bl_label = "Fantasy Building Generator"
    bl_idname = "VIEW3D_PT_fantasy_building_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        obj = context.active_object
        is_bldg = obj and obj.get("is_fantasy_building", False)
        
        # Primary Action Buttons
        col = layout.column(align=True)
        if not is_bldg:
            col.scale_y = 1.6
            col.operator("building.create_fantasy_building", text="Create Fantasy Building", icon='HOME')
        else:
            row = col.row(align=True)
            row.scale_y = 1.4
            row.operator("building.randomize_seed", text="Randomize / Re-roll", icon='FILE_REFRESH')
            row.operator("building.regenerate", text="Regenerate", icon='FILE_CACHE')
            
            row2 = col.row(align=True)
            row2.scale_y = 1.2
            row2.operator("building.toggle_door", text="Open / Close Door", icon='RESTRICT_VIEW_OFF')
            row2.operator("building.finalize_mesh", text="Finalize Mesh", icon='CHECKMARK')

        # Style Presets Box
        box_presets = layout.box()
        box_presets.label(text="Architectural Presets", icon='ASSET_MANAGER')
        grid = box_presets.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        
        op = grid.operator("building.apply_preset", text="Cozy Tavern", icon='COMMUNITY')
        op.preset_key = "TAVERN"
        
        op = grid.operator("building.apply_preset", text="Wizard Tower", icon='CONE')
        op.preset_key = "WIZARD_TOWER"
        
        op = grid.operator("building.apply_preset", text="Fairytale Cottage", icon='SNAP_VOLUME')
        op.preset_key = "COTTAGE"
        
        op = grid.operator("building.apply_preset", text="Townhouse", icon='MOD_BUILD')
        op.preset_key = "TOWNHOUSE"

        # Global parameters
        box_global = layout.box()
        box_global.prop(props, "auto_update")
        box_global.prop(props, "seed")
        box_global.prop(props, "wonkiness", slider=True)

class VIEW3D_PT_fantasy_building_dimensions(bpy.types.Panel):
    """Subpanel for building storeys and footprint dimensions"""
    bl_label = "Floors & Dimensions"
    bl_idname = "VIEW3D_PT_fantasy_building_dimensions"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        col = layout.column(align=True)
        col.prop(props, "num_floors")
        col.prop(props, "floor_height")
        col.prop(props, "width")
        col.prop(props, "depth")
        col.prop(props, "wall_thickness")
        
        box_cant = layout.box()
        box_cant.prop(props, "has_cantilever")
        if props.has_cantilever:
            box_cant.prop(props, "overhang_mode")
            box_cant.prop(props, "cantilever_overhang")

        box_found = layout.box()
        box_found.prop(props, "has_foundation")
        if props.has_foundation:
            box_found.prop(props, "foundation_height")
            box_found.prop(props, "ground_floor_stone")
            box_found.prop(props, "has_front_steps")

class VIEW3D_PT_fantasy_building_interior(bpy.types.Panel):
    """Subpanel for walk-in interior settings"""
    bl_label = "Walk-in Interior & Stairs"
    bl_idname = "VIEW3D_PT_fantasy_building_interior"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        box_stairs = layout.box()
        box_stairs.prop(props, "has_stairs")
        if props.has_stairs:
            box_stairs.prop(props, "stair_style")
            box_stairs.prop(props, "stair_width")
            
        layout.prop(props, "has_ceiling_beams")

class VIEW3D_PT_fantasy_building_openings(bpy.types.Panel):
    """Subpanel for doors, windows, and exterior props"""
    bl_label = "Doors & Windows"
    bl_idname = "VIEW3D_PT_fantasy_building_openings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        # Door Box
        box_door = layout.box()
        box_door.prop(props, "has_front_door")
        if props.has_front_door:
            col = box_door.column(align=True)
            col.prop(props, "door_width")
            col.prop(props, "door_height")
            col.prop(props, "door_angle", slider=True)
            col.prop(props, "has_lanterns")
            
        # Windows Box
        box_win = layout.box()
        box_win.prop(props, "has_windows")
        if props.has_windows:
            col = box_win.column(align=True)
            col.prop(props, "window_width")
            col.prop(props, "window_height")
            col.prop(props, "has_shutters")
            col.prop(props, "has_flower_boxes")

        # Timber framing
        box_timber = layout.box()
        box_timber.prop(props, "has_timber_framing")
        if props.has_timber_framing:
            box_timber.prop(props, "timber_diagonals")

class VIEW3D_PT_fantasy_building_roof(bpy.types.Panel):
    """Subpanel for roof, shingles, dormers, and chimney"""
    bl_label = "Roof & Details"
    bl_idname = "VIEW3D_PT_fantasy_building_roof"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        col = layout.column(align=True)
        col.prop(props, "roof_style")
        col.prop(props, "roof_height")
        col.prop(props, "roof_overhang")
        if props.roof_style == 'SWAY':
            col.prop(props, "roof_sway", slider=True)
            
        box_shingles = layout.box()
        box_shingles.prop(props, "has_roof_shingles")
        if props.has_roof_shingles and props.roof_style in ('SWAY', 'GABLE'):
            box_shingles.prop(props, "shingle_rows")
            
        col_det = layout.column(align=True)
        col_det.prop(props, "has_dormers")
        col_det.prop(props, "has_chimney")

class VIEW3D_PT_fantasy_building_materials(bpy.types.Panel):
    """Subpanel for procedural stylized colors and custom material overrides"""
    bl_label = "Materials & Colors"
    bl_idname = "VIEW3D_PT_fantasy_building_materials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        box_colors = layout.box()
        box_colors.label(text="Procedural Stylized Colors", icon='COLOR')
        grid = box_colors.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.prop(props, "color_shingles", text="Shingles")
        grid.prop(props, "color_wall_ext", text="Wall Ext")
        grid.prop(props, "color_wall_int", text="Wall Int")
        grid.prop(props, "color_timber", text="Timber")
        grid.prop(props, "color_stone", text="Stone")
        grid.prop(props, "color_floor", text="Floor")
        grid.prop(props, "color_door", text="Door")
        
        box_glow = layout.box()
        box_glow.label(text="Night Window Glow", icon='LIGHT_SUN')
        box_glow.prop(props, "window_glow_strength", slider=True)
        if props.window_glow_strength > 0.01:
            box_glow.prop(props, "color_window_glow")
            
        box_custom = layout.box()
        box_custom.label(text="Custom Material Overrides", icon='MATERIAL')
        col = box_custom.column(align=True)
        col.prop(props, "custom_shingles")
        col.prop(props, "custom_wall_ext")
        col.prop(props, "custom_wall_int")
        col.prop(props, "custom_timber")
        col.prop(props, "custom_stone")
        col.prop(props, "custom_floor")
        col.prop(props, "custom_door")
        col.prop(props, "custom_glass")
        col.prop(props, "custom_iron")
