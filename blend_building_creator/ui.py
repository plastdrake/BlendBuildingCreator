"""
User Interface Panels in Blender 3D Viewport Sidebar (N-Panel).
Features clean layout, collapsible sections, style presets, and live parameter sliders.
"""

import bpy
import os as _os

from .presets import PRESETS, BUILDING_FAMILIES


def _read_addon_version(default="1.7.10"):
    """Read the version straight from blender_manifest.toml so it stays in sync
    (extensions don't expose bl_info, which broke the panel before)."""
    try:
        with open(_os.path.join(_os.path.dirname(__file__), "blender_manifest.toml"),
                  "r", encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if s.startswith("version"):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return default


ADDON_VERSION = _read_addon_version()

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
        layout.label(text=f"Version {ADDON_VERSION}", icon='INFO')
        
        # Primary Action Buttons
        col = layout.column(align=True)
        col.scale_y = 1.4
        col.operator("building.create_fantasy_building", text="Create New Building", icon='ADD')
        
        row_res = col.row(align=True)
        row_res.scale_y = 1.1
        row_res.operator("building.reset_settings", text="Reset to Defaults", icon='LOOP_BACK')
        if is_bldg and "building_settings" in obj:
            row_res.operator("building.load_settings", text="Load from Active", icon='IMPORT')
            
        if is_bldg:
            row_act = col.row(align=True)
            row_act.scale_y = 1.2
            row_act.operator("building.randomize_seed", text="Randomize", icon='FILE_REFRESH')
            row_act.operator("building.regenerate", text="Regenerate", icon='FILE_CACHE')
            
            row_door = col.row(align=True)
            row_door.scale_y = 1.1
            row_door.operator("building.toggle_door", text="Open / Close Door", icon='RESTRICT_VIEW_OFF')
            row_door.operator("building.finalize_mesh", text="Bake / Finalize", icon='CHECKMARK')

        # Building Archetype & Material Tier
        box_arch = layout.box()
        box_arch.label(text="Architectural Purpose & Archetype", icon='ASSET_MANAGER')
        box_arch.prop(props, "building_archetype", text="")
        if props.building_archetype == 'LUMBERMILL':
            box_arch.prop(props, "mill_grade", text="Mill Grade")
            box_arch.prop(props, "cargo_dock_facade")
            if props.num_floors > 1:
                box_arch.prop(props, "has_upper_cargo_crane")
        elif props.building_archetype == 'WAREHOUSE':
            if props.num_floors > 1:
                box_arch.prop(props, "has_upper_cargo_crane")
        
        box_tier = layout.box()
        box_tier.label(text="Building Material Tier", icon='MATERIAL')
        box_tier.prop(props, "material_tier", expand=True)
        box_tier.prop(props, "physical_siding")

        # Style Presets Box with Category Filter & Tier Selectors
        box_presets = layout.box()
        box_presets.label(text="Purpose-Built Plot Presets", icon='ASSET_MANAGER')
        box_presets.prop(props, "preset_category", text="")
        
        cat_filter = props.preset_category
        for family in BUILDING_FAMILIES:
            if cat_filter == 'ALL' or family.get('category') == cat_filter:
                card = box_presets.box()
                row_head = card.row(align=True)
                row_head.label(text=f"{family['name']} ({family['shape']})", icon=family['icon'])
                row_head.label(text=family['plot'])
                
                row_tiers = card.row(align=True)
                row_tiers.scale_y = 1.15
                for tier_label, preset_key, _desc in family['tiers']:
                    op = row_tiers.operator("building.apply_preset", text=tier_label)
                    op.preset_key = preset_key

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
        col.prop(props, "building_shape")
        if props.building_shape in ('L_SHAPE', 'T_SHAPE', 'U_SHAPE'):
            box_wing = col.box()
            box_wing.label(text="Wing & Courtyard Geometry", icon='MOD_BUILD')
            box_wing.prop(props, "wing_floors")
            box_wing.prop(props, "wing_width")
            box_wing.prop(props, "wing_depth")
            box_wing.prop(props, "wing_placement")
            box_wing.prop(props, "wing_roof_scale")
            if props.building_shape == 'L_SHAPE':
                box_wing.prop(props, "wing_side")
            elif props.building_shape == 'U_SHAPE':
                box_wing.prop(props, "courtyard_width")
                
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
            box_found.prop(props, "foundation_type")
            box_found.prop(props, "foundation_height")
            box_found.prop(props, "ground_floor_stone")
            box_found.prop(props, "has_front_steps")

class VIEW3D_PT_fantasy_building_interior(bpy.types.Panel):
    """Subpanel for walkable interior features: stairs, floors, and ceiling beams"""
    bl_label = "Walk-in Interior & Stairs"
    bl_idname = "VIEW3D_PT_fantasy_building_interior"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        box_stairs = layout.box()
        box_stairs.prop(props, "has_stairs")
        if props.has_stairs:
            col = box_stairs.column(align=True)
            col.prop(props, "stair_style")
            col.prop(props, "stair_width")

        box_int = layout.box()
        box_int.prop(props, "ground_floor_stone")
        box_int.prop(props, "has_ceiling_beams")
        box_int.prop(props, "has_attic_trusses")

class VIEW3D_PT_fantasy_building_openings(bpy.types.Panel):
    """Subpanel for doors, windows, and half-timber styling"""
    bl_label = "Openings & Framing"
    bl_idname = "VIEW3D_PT_fantasy_building_openings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        # Entrances Box
        box_door = layout.box()
        box_door.label(text="Entrances & Doors", icon='MOD_BUILD')
        row = box_door.row(align=True)
        row.prop(props, "has_front_door", text="Front Door")
        row.prop(props, "has_back_door", text="Rear Door")
        row.prop(props, "has_side_door", text="Side Door")
        if props.has_side_door:
            box_door.prop(props, "side_door_facade")
        if props.has_front_door:
            box_door.prop(props, "front_door_offset_x")
        if props.has_front_door or props.has_back_door or props.has_side_door:
            col = box_door.column(align=True)
            col.prop(props, "door_shape")
            col.prop(props, "door_width")
            col.prop(props, "door_height")
            col.prop(props, "include_door_leaves", text="Generate Door Leaves")
            if props.include_door_leaves:
                col.prop(props, "door_angle", slider=True)
        if props.has_side_rampart:
            box_door.prop(props, "rampart_door_width")

        # Standalone Door Blade Box (for Unreal Engine)
        box_ue = box_door.box()
        box_ue.label(text="Unreal Engine Standalone Door Blade", icon='EXPORT')
        box_ue.prop(props, "door_blade_leaf_type", text="Type")
        row_ue = box_ue.row(align=True)
        row_ue.prop(props, "door_blade_width", text="Width")
        row_ue.prop(props, "door_blade_height", text="Height")
        row_ue2 = box_ue.row(align=True)
        row_ue2.prop(props, "door_blade_shape", text="Shape")
        row_ue2.prop(props, "door_blade_hinge", text="Hinge")
        box_ue.operator("building.create_door_blade", text="Create Door Blade (Pivot at 0,0)", icon='SNAP_VERTEX')
            
        # Windows Box
        box_win = layout.box()
        box_win.prop(props, "has_windows")
        if props.has_windows:
            col = box_win.column(align=True)
            col.prop(props, "window_density", slider=True)
            col.prop(props, "window_spacing")
            col.prop(props, "window_width")
            col.prop(props, "window_height")
            col.prop(props, "has_shutters")
            if props.has_shutters:
                sub = col.box()
                sub.prop(props, "shutter_state")
                if props.shutter_state == 'PARTIAL':
                    sub.prop(props, "shutter_closed_amount", slider=True)

        # Timber framing
        box_timber = layout.box()
        box_timber.prop(props, "has_timber_framing")
        if props.has_timber_framing:
            box_timber.prop(props, "timber_diagonals")
            box_timber.prop(props, "open_timber_frame")

        # Stucco & Exposed Brick
        box_stucco = layout.box()
        box_stucco.prop(props, "has_exposed_brick")
        if props.has_exposed_brick:
            box_stucco.prop(props, "exposed_brick_frequency", slider=True)

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
        if props.roof_style != 'NONE':
            if props.roof_style in ('SWAY', 'GABLE'):
                col.prop(props, "roof_orientation")
            col.prop(props, "roof_height")
            col.prop(props, "roof_overhang")
            if props.roof_style == 'SWAY':
                col.prop(props, "roof_sway")
            col.prop(props, "roof_flare")

        # Shingles & Dormers
        box_det = layout.box()
        box_det.prop(props, "has_dormers")
        if props.has_dormers and props.roof_style in ('SWAY', 'GABLE'):
            col_d = box_det.column(align=True)
            col_d.prop(props, "dormer_count")
            col_d.prop(props, "dormer_sides")
            if props.building_shape in ('L_SHAPE', 'T_SHAPE', 'U_SHAPE'):
                col_d.separator()
                col_d.prop(props, "has_wing_dormers")
                if props.has_wing_dormers:
                    col_d.prop(props, "wing_dormer_count")
                    col_d.prop(props, "wing_dormer_sides")

        # Turret and Chimney
        box_acc = layout.box()
        box_acc.prop(props, "has_roof_turret")
        if props.has_roof_turret:
            box_acc.prop(props, "roof_turret_style")
        box_acc.prop(props, "has_roof_clock_spire")
        if props.has_roof_clock_spire:
            col = box_acc.column(align=True)
            col.prop(props, "roof_clock_scale")
            col.prop(props, "roof_clock_pos_x")
            col.prop(props, "roof_clock_pos_y")
        box_acc.prop(props, "has_chimney")

class VIEW3D_PT_fantasy_building_extensions(bpy.types.Panel):
    """Subpanel for mini-wing outcrops, balconies, and pillared colonnades"""
    bl_label = "Wings, Balconies & Overhangs"
    bl_idname = "VIEW3D_PT_fantasy_building_extensions"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        
        # Mini-Wing Outcrops
        box_wing = layout.box()
        box_wing.prop(props, "has_mini_wing")
        if props.has_mini_wing:
            col = box_wing.column(align=True)
            col.prop(props, "mini_wing_count")
            col.prop(props, "mini_wing_random")
            col.separator()
            col.prop(props, "mini_wing_width")
            col.prop(props, "mini_wing_depth")
            col.prop(props, "mini_wing_random_size")
            if props.mini_wing_random_size:
                col.prop(props, "mini_wing_random_width")
                col.prop(props, "mini_wing_random_depth")
            col.prop(props, "mini_wing_roof")
            col.prop(props, "mini_wing_shingle_rot")
            col.prop(props, "mini_wing_shingle_scale")

        # Mage Tower Whimsical Outcrops
        if props.building_archetype == 'MAGE_TOWER' or props.building_shape == 'ROUND_TOWER':
            box_mage = layout.box()
            box_mage.prop(props, "has_mage_outcrops")
            if props.has_mage_outcrops:
                box_mage.prop(props, "mage_outcrop_count")

        # Balcony
        box_balc = layout.box()
        box_balc.prop(props, "has_balcony")
        if props.has_balcony:
            col = box_balc.column(align=True)
            col.prop(props, "balcony_side")
            col.prop(props, "balcony_mode")
            if props.balcony_mode == 'SINGLE':
                col.prop(props, "balcony_floor")
            elif props.balcony_mode == 'CUSTOM':
                row = col.row(align=True)
                row.prop(props, "balcony_fl2", text="Fl 2", toggle=True)
                if props.num_floors >= 3:
                    row.prop(props, "balcony_fl3", text="Fl 3", toggle=True)
                if props.num_floors >= 4:
                    row.prop(props, "balcony_fl4", text="Fl 4", toggle=True)
                if props.num_floors >= 5:
                    row.prop(props, "balcony_fl5", text="Fl 5", toggle=True)
            col.prop(props, "balcony_width")
            col.prop(props, "balcony_depth")
            
        # Gable Loft Hatch and Ladder
        box_loft = layout.box()
        box_loft.prop(props, "has_loft_hatch")

        # Pillared Overhang / Colonnade
        box_over = layout.box()
        box_over.prop(props, "has_pillared_overhang")
        if props.has_pillared_overhang:
            col = box_over.column(align=True)
            col.prop(props, "pillared_overhang_side")
            col.prop(props, "pillared_overhang_depth")
            col.prop(props, "pillared_overhang_pillars")
            col.prop(props, "pillared_overhang_style")

        # Civic Landmarks
        box_civic = layout.box()
        box_civic.label(text="Civic Landmarks", icon='COMMUNITY')
        box_civic.prop(props, "has_clock_tower")
        if props.has_clock_tower:
            col = box_civic.column(align=True)
            col.prop(props, "clock_tower_side")
            col.prop(props, "clock_tower_size")
        box_civic.prop(props, "has_corner_turrets")
        if props.has_corner_turrets:
            box_civic.prop(props, "corner_turret_size")
        box_civic.prop(props, "has_side_rampart")
        if props.has_side_rampart:
            col_ramp = box_civic.column(align=True)
            col_ramp.prop(props, "rampart_side")
            col_ramp.prop(props, "rampart_door_width")
        row_ap = box_civic.row()
        row_ap.enabled = not props.has_veranda
        row_ap.prop(props, "has_arched_porch")
        box_civic.prop(props, "has_entry_ramp")
        box_civic.separator()
        box_civic.prop(props, "has_side_annex")
        if props.has_side_annex:
            col = box_civic.column(align=True)
            col.prop(props, "annex_floors")
            if not props.town_hall_composer:
                col.prop(props, "annex_side")
        box_civic.separator()
        box_civic.prop(props, "town_hall_composer")

        # Hospitality & Outdoor Decor
        box_hosp = layout.box()
        box_hosp.label(text="Hospitality & Yard Props", icon='HOME')
        row_v = box_hosp.row()
        row_v.enabled = not props.has_arched_porch
        row_v.prop(props, "has_veranda")
        box_hosp.prop(props, "has_trade_sign")
        if props.has_trade_sign:
            box_hosp.prop(props, "sign_icon", text="Sign Emblem")
        box_hosp.prop(props, "has_flower_boxes")
        box_hosp.prop(props, "has_outdoor_decor")
        if props.has_outdoor_decor:
            box_hosp.prop(props, "lantern_style")
        box_hosp.prop(props, "has_well")

        # Estate Grounds & Outbuildings
        box_estate = layout.box()
        box_estate.label(text="Estate Grounds & Outbuildings", icon='COMMUNITY')
        row_e = box_estate.row(align=True)
        row_e.prop(props, "has_stable")
        row_e.prop(props, "has_servant_quarters")
        box_estate.prop(props, "has_estate_fountain")
        box_estate.prop(props, "estate_awnings")
        if props.has_stable or props.has_servant_quarters or props.has_estate_fountain:
            col_est = box_estate.column(align=True)
            if props.has_stable:
                col_est.prop(props, "stable_side")
            if props.has_servant_quarters:
                col_est.prop(props, "servant_quarters_side")
            col_est.prop(props, "outbuilding_offset_x")
            col_est.prop(props, "outbuilding_offset_y")
            col_est.prop(props, "plot_setback")

        # Fortifications
        box_fort = layout.box()
        box_fort.label(text="Fortifications", icon='MOD_BUILD')
        box_fort.prop(props, "has_palisade")
        if props.has_palisade:
            col = box_fort.column(align=True)
            col.prop(props, "palisade_style")
            col.prop(props, "palisade_height")
            col.prop(props, "palisade_offset")
        box_fort.prop(props, "has_curtain_wall")
        if props.has_curtain_wall:
            col = box_fort.column(align=True)
            col.prop(props, "curtain_wall_height")
            col.prop(props, "curtain_wall_thickness")
            col.prop(props, "curtain_wall_offset")
        box_fort.prop(props, "has_bastion_towers")
        if props.has_bastion_towers:
            col = box_fort.column(align=True)
            col.prop(props, "bastion_tower_count")
            col.prop(props, "bastion_tower_size")
            col.prop(props, "bastion_tower_height")
        box_fort.prop(props, "has_mounted_shields")
        if props.has_mounted_shields:
            box_fort.prop(props, "shield_placement")
        box_fort.prop(props, "has_battlements")
        if props.has_battlements:
            box_fort.prop(props, "battlement_style")
        box_fort.prop(props, "has_banners")
        if props.has_banners:
            col = box_fort.column(align=True)
            col.prop(props, "banner_count")
            col.prop(props, "color_banner")
        box_fort.prop(props, "has_gable_crest")
        if props.has_gable_crest:
            col = box_fort.column(align=True)
            col.prop(props, "gable_crest_style")
            col.prop(props, "gable_crest_scale")
        box_fort.prop(props, "has_military_props")
        if props.has_military_props:
            box_fort.prop(props, "military_props_count")

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
        
        box_tier = layout.box()
        box_tier.label(text="Material Tier", icon='MATERIAL')
        box_tier.prop(props, "material_tier", expand=True)
        box_tier.prop(props, "physical_siding")
        
        if (props.material_tier == 'TIER_3' or props.ground_floor_stone) and props.physical_siding:
            box_tier.label(text="Stone Masonry Style", icon='SNAP_VOLUME')
            col_st = box_tier.column(align=True)
            col_st.prop(props, "stone_block_scale", slider=True)
            col_st.prop(props, "stone_disorder", slider=True)

        box_uv = layout.box()
        box_uv.label(text="Handpaint UVs", icon='UV')
        box_uv.prop(props, "split_by_material", text="Split by Material (per-piece conformal)")

        box_colors = layout.box()
        box_colors.label(text="Procedural Stylized Colors", icon='COLOR')
        box_colors.prop(props, "color_palette")
        grid = box_colors.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.prop(props, "color_shingles", text="Shingles")
        grid.prop(props, "color_wall_ext", text="Wall Ext")
        grid.prop(props, "color_wall_int", text="Wall Int")
        grid.prop(props, "color_timber_frame", text="Timber Frame")
        grid.prop(props, "color_timber", text="General Wood")
        grid.prop(props, "color_log_end", text="Log Rings")
        grid.prop(props, "color_stone", text="Stone")
        grid.prop(props, "color_floor", text="Floor")
        grid.prop(props, "color_door", text="Door")
        grid.prop(props, "color_banner", text="Banner")
        
        box_glow = layout.box()
        box_glow.label(text="Night Window Glow", icon='LIGHT_SUN')
        box_glow.prop(props, "window_glow_strength", slider=True)
        if props.window_glow_strength > 0.01:
            box_glow.prop(props, "color_window_glow")
            
        box_custom = layout.box()
        box_custom.label(text="Custom Material Overrides", icon='MATERIAL')
        col = box_custom.column(align=True)
        col.prop(props, "custom_shingles", text="Shingles Mat")
        col.prop(props, "custom_wall_ext", text="Wall Ext Mat")
        col.prop(props, "custom_wall_brick", text="Exposed Brick Stucco Mat")
        col.prop(props, "custom_wall_int", text="Wall Int Mat")
        col.prop(props, "custom_timber_frame", text="Timber Frame Mat")
        col.prop(props, "custom_timber", text="General Wood Mat")
        col.prop(props, "custom_log", text="Log Mat")
        col.prop(props, "custom_log_end", text="Log End Mat")
        col.prop(props, "custom_stone", text="Stone Mat")
        col.prop(props, "custom_floor", text="Floor Mat")
        col.prop(props, "custom_door", text="Door Mat")
        col.prop(props, "custom_glass", text="Glass Mat")
        col.prop(props, "custom_iron", text="Iron Mat")
        col.prop(props, "custom_stairs", text="Stairs Mat")
        col.prop(props, "custom_railing", text="Railing Mat")
        col.prop(props, "custom_window_frame", text="Window Frame Mat")
        col.prop(props, "custom_shutter", text="Shutter Mat")
