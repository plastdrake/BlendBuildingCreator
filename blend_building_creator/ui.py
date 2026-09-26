"""Clean N-Panel UI for the Fantasy Building Generator.

Layout principles (DRY / GRASP):
- One panel = one concern. The old "Wings, Balconies & Overhangs" mega-panel
  (extensions + civic + hospitality + estate + fortifications) is split into
  focused panels below so nothing hides in a "weird category".
- The main panel only creates/manages buildings; everything parametric lives
  in a dedicated sub-panel.
- Preset browser filters by category and shows one compact card per family.
- Purpose kits (previously locked inside presets) get their own panel with
  explicit toggles that work on ANY footprint.
"""

import bpy
import os as _os

from .presets import PRESETS, BUILDING_FAMILIES


def _read_addon_version(default="1.7.10"):
    """Read the version straight from blender_manifest.toml so it stays in sync."""
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


# ---------------------------------------------------------------------------
# 1. Create & Manage (actions only)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_main(bpy.types.Panel):
    """Main panel: create / manage the active building."""
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

        box = layout.box()
        box.label(text="Live Update", icon='FILE_REFRESH')
        box.prop(props, "auto_update")
        box.prop(props, "seed")
        box.prop(props, "wonkiness", slider=True)


# ---------------------------------------------------------------------------
# 2. Presets (browser)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_presets(bpy.types.Panel):
    """Purpose-built starting points. Presets only set defaults - every part stays editable."""
    bl_label = "Presets"
    bl_idname = "VIEW3D_PT_fantasy_building_presets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings
        layout.prop(props, "preset_category", text="Category")
        cat_filter = props.preset_category
        for family in BUILDING_FAMILIES:
            if cat_filter != 'ALL' and family.get('category') != cat_filter:
                continue
            card = layout.box()
            head = card.row(align=True)
            head.label(text=f"{family['name']}", icon=family.get('icon', 'HOME'))
            head.label(text=f"{family.get('plot', '')} | {family.get('shape', '')}")
            row = card.row(align=True)
            row.scale_y = 1.15
            for tier_label, preset_key, desc in family['tiers']:
                op = row.operator("building.apply_preset", text=tier_label)
                op.preset_key = preset_key


# ---------------------------------------------------------------------------
# 3. Structure (footprint + floors + foundation)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_dimensions(bpy.types.Panel):
    """Footprint, storeys and foundation."""
    bl_label = "Structure: Floors & Footprint"
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
            box = col.box()
            box.label(text="Wing & Courtyard", icon='MOD_BUILD')
            box.prop(props, "wing_floors")
            box.prop(props, "wing_width")
            box.prop(props, "wing_depth")
            box.prop(props, "wing_placement")
            box.prop(props, "wing_roof_scale")
            if props.building_shape == 'L_SHAPE':
                box.prop(props, "wing_side")
            elif props.building_shape == 'U_SHAPE':
                box.prop(props, "courtyard_width")

        col.separator()
        col.prop(props, "num_floors")
        col.prop(props, "floor_height")
        col.prop(props, "width")
        col.prop(props, "depth")
        col.prop(props, "wall_thickness")

        box_c = layout.box()
        box_c.prop(props, "has_cantilever")
        if props.has_cantilever:
            box_c.prop(props, "overhang_mode")
            box_c.prop(props, "cantilever_overhang")

        box_f = layout.box()
        box_f.label(text="Foundation", icon='SNAP_VOLUME')
        box_f.prop(props, "has_foundation")
        if props.has_foundation:
            box_f.prop(props, "foundation_type")
            box_f.prop(props, "foundation_height")
            box_f.prop(props, "ground_floor_stone")
            box_f.prop(props, "has_front_steps")


# ---------------------------------------------------------------------------
# 4. Purpose kits (modular: any kit on any building, no preset needed)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_kits(bpy.types.Panel):
    """Modular purpose kits. Combine freely - e.g. bakery oven + windmill sails."""
    bl_label = "Purpose Kits (Modular)"
    bl_idname = "VIEW3D_PT_fantasy_building_kits"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        box = layout.box()
        box.label(text="Archetype Shortcut", icon='ASSET_MANAGER')
        box.prop(props, "building_archetype", text="")
        if props.building_archetype == 'LUMBERMILL' or props.kit_lumbermill:
            box.prop(props, "mill_grade", text="Mill Grade")
        if (props.building_archetype in ('LUMBERMILL', 'WAREHOUSE')
                or props.kit_lumbermill or props.kit_warehouse):
            box.prop(props, "cargo_dock_facade")
            if props.num_floors > 1:
                box.prop(props, "has_upper_cargo_crane")

        box_craft = layout.box()
        box_craft.label(text="Craft & Industry", icon='TOOL_SETTINGS')
        col = box_craft.column(align=True)
        col.prop(props, "kit_blacksmith")
        col.prop(props, "kit_bakery")
        col.prop(props, "kit_warehouse")
        col.prop(props, "kit_lumbermill")
        col.prop(props, "kit_fisherman")
        col.prop(props, "kit_windmill")
        col.prop(props, "kit_quarry")

        box_civic = layout.box()
        box_civic.label(text="Community & Defense", icon='COMMUNITY')
        col2 = box_civic.column(align=True)
        col2.prop(props, "kit_chapel")
        col2.prop(props, "kit_archery")
        col2.prop(props, "kit_tournament")
        col2.prop(props, "kit_stable")
        col2.prop(props, "kit_watchtower")


# ---------------------------------------------------------------------------
# 5. Interior
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_interior(bpy.types.Panel):
    """Walkable interior: stairs, beams, trusses."""
    bl_label = "Interior & Stairs"
    bl_idname = "VIEW3D_PT_fantasy_building_interior"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        box = layout.box()
        box.prop(props, "has_stairs")
        if props.has_stairs:
            box.prop(props, "stair_style")
            box.prop(props, "stair_width")

        box2 = layout.box()
        box2.prop(props, "ground_floor_stone")
        box2.prop(props, "has_ceiling_beams")
        box2.prop(props, "has_attic_trusses")


# ---------------------------------------------------------------------------
# 6. Openings
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_openings(bpy.types.Panel):
    """Doors, windows, shutters, timber framing."""
    bl_label = "Openings & Framing"
    bl_idname = "VIEW3D_PT_fantasy_building_openings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        box_d = layout.box()
        box_d.label(text="Doors", icon='MOD_BUILD')
        row = box_d.row(align=True)
        row.prop(props, "has_front_door", text="Front")
        row.prop(props, "has_back_door", text="Rear")
        row.prop(props, "has_side_door", text="Side")
        if props.has_side_door:
            box_d.prop(props, "side_door_facade")
        if props.has_front_door:
            box_d.prop(props, "front_door_offset_x")
        if props.has_front_door or props.has_back_door or props.has_side_door:
            col = box_d.column(align=True)
            col.prop(props, "door_shape")
            col.prop(props, "door_width")
            col.prop(props, "door_height")
            col.prop(props, "include_door_leaves", text="Door Leaves")
            if props.include_door_leaves:
                col.prop(props, "door_angle", slider=True)
        if props.has_side_rampart:
            box_d.prop(props, "rampart_door_width")

        box_ue = box_d.box()
        box_ue.label(text="Unreal Door Blade Export", icon='EXPORT')
        box_ue.prop(props, "door_blade_leaf_type", text="Type")
        r1 = box_ue.row(align=True)
        r1.prop(props, "door_blade_width", text="Width")
        r1.prop(props, "door_blade_height", text="Height")
        r2 = box_ue.row(align=True)
        r2.prop(props, "door_blade_shape", text="Shape")
        r2.prop(props, "door_blade_hinge", text="Hinge")
        box_ue.operator("building.create_door_blade", text="Create Door Blade", icon='SNAP_VERTEX')

        box_w = layout.box()
        box_w.label(text="Windows", icon='UV')
        box_w.prop(props, "has_windows")
        if props.has_windows:
            col = box_w.column(align=True)
            col.prop(props, "window_density", slider=True)
            col.prop(props, "window_spacing")
            col.prop(props, "window_width")
            col.prop(props, "window_height")
            col.prop(props, "has_shutters")
            if props.has_shutters:
                col.prop(props, "shutter_state")
                if props.shutter_state == 'PARTIAL':
                    col.prop(props, "shutter_closed_amount", slider=True)

        box_t = layout.box()
        box_t.label(text="Timber & Brick", icon='MATERIAL')
        box_t.prop(props, "has_timber_framing")
        if props.has_timber_framing:
            box_t.prop(props, "timber_diagonals")
            box_t.prop(props, "open_timber_frame")
        box_t.prop(props, "has_exposed_brick")
        if props.has_exposed_brick:
            box_t.prop(props, "exposed_brick_frequency", slider=True)


# ---------------------------------------------------------------------------
# 7. Roof
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_roof(bpy.types.Panel):
    """Roof style, dormers, turret, chimney."""
    bl_label = "Roof & Chimney"
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

        box = layout.box()
        box.prop(props, "has_dormers")
        if props.has_dormers and props.roof_style in ('SWAY', 'GABLE'):
            box.prop(props, "dormer_count")
            box.prop(props, "dormer_sides")
            if props.building_shape in ('L_SHAPE', 'T_SHAPE', 'U_SHAPE'):
                box.prop(props, "has_wing_dormers")
                if props.has_wing_dormers:
                    box.prop(props, "wing_dormer_count")
                    box.prop(props, "wing_dormer_sides")

        box2 = layout.box()
        box2.prop(props, "has_roof_turret")
        if props.has_roof_turret:
            box2.prop(props, "roof_turret_style")
        box2.prop(props, "has_roof_clock_spire")
        if props.has_roof_clock_spire:
            box2.prop(props, "roof_clock_scale")
            box2.prop(props, "roof_clock_pos_x")
            box2.prop(props, "roof_clock_pos_y")
        box2.prop(props, "has_chimney")


# ---------------------------------------------------------------------------
# 8. Extensions (outcrops, balconies, overhangs, loft)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_extensions(bpy.types.Panel):
    """Small attached volumes: outcrops, balconies, colonnades, loft hatch."""
    bl_label = "Extensions: Outcrops & Balconies"
    bl_idname = "VIEW3D_PT_fantasy_building_extensions"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        box = layout.box()
        box.prop(props, "has_mini_wing")
        if props.has_mini_wing:
            col = box.column(align=True)
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

        if props.building_archetype == 'MAGE_TOWER' or props.building_shape == 'ROUND_TOWER':
            box_m = layout.box()
            box_m.prop(props, "has_mage_outcrops")
            if props.has_mage_outcrops:
                box_m.prop(props, "mage_outcrop_count")

        box_b = layout.box()
        box_b.prop(props, "has_balcony")
        if props.has_balcony:
            col = box_b.column(align=True)
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

        box_l = layout.box()
        box_l.prop(props, "has_loft_hatch")

        box_o = layout.box()
        box_o.prop(props, "has_pillared_overhang")
        if props.has_pillared_overhang:
            col = box_o.column(align=True)
            col.prop(props, "pillared_overhang_side")
            col.prop(props, "pillared_overhang_depth")
            col.prop(props, "pillared_overhang_pillars")
            col.prop(props, "pillared_overhang_style")


# ---------------------------------------------------------------------------
# 9. Civic landmarks & annex
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_civic(bpy.types.Panel):
    """Clock towers, turrets, ramparts, porches, annexes."""
    bl_label = "Civic: Towers & Annex"
    bl_idname = "VIEW3D_PT_fantasy_building_civic"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        layout.prop(props, "has_clock_tower")
        if props.has_clock_tower:
            layout.prop(props, "clock_tower_side")
            layout.prop(props, "clock_tower_size")
        layout.prop(props, "has_corner_turrets")
        if props.has_corner_turrets:
            layout.prop(props, "corner_turret_size")
        layout.prop(props, "has_side_rampart")
        if props.has_side_rampart:
            layout.prop(props, "rampart_side")
            layout.prop(props, "rampart_door_width")
        row_ap = layout.row()
        row_ap.enabled = not props.has_veranda
        row_ap.prop(props, "has_arched_porch")
        layout.prop(props, "has_entry_ramp")
        layout.separator()
        layout.prop(props, "has_side_annex")
        if props.has_side_annex:
            layout.prop(props, "annex_floors")
            if not props.town_hall_composer:
                layout.prop(props, "annex_side")
        layout.separator()
        layout.prop(props, "town_hall_composer")


# ---------------------------------------------------------------------------
# 10. Hospitality & yard
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_hospitality(bpy.types.Panel):
    """Veranda, signs, planters, furniture, wells."""
    bl_label = "Hospitality & Yard"
    bl_idname = "VIEW3D_PT_fantasy_building_hospitality"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        row_v = layout.row()
        row_v.enabled = not props.has_arched_porch
        row_v.prop(props, "has_veranda")
        layout.prop(props, "has_trade_sign")
        if props.has_trade_sign:
            layout.prop(props, "sign_icon", text="Emblem")
        layout.prop(props, "has_flower_boxes")
        layout.prop(props, "has_outdoor_decor")
        if props.has_outdoor_decor:
            layout.prop(props, "lantern_style")
        layout.prop(props, "has_well")


# ---------------------------------------------------------------------------
# 11. Fortifications
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_fortifications(bpy.types.Panel):
    """Palisades, curtain walls, bastions, banners, drill props."""
    bl_label = "Fortifications"
    bl_idname = "VIEW3D_PT_fantasy_building_fortifications"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        layout.prop(props, "has_palisade")
        if props.has_palisade:
            layout.prop(props, "palisade_style")
            layout.prop(props, "palisade_height")
            layout.prop(props, "palisade_offset")
        layout.prop(props, "has_curtain_wall")
        if props.has_curtain_wall:
            layout.prop(props, "curtain_wall_height")
            layout.prop(props, "curtain_wall_thickness")
            layout.prop(props, "curtain_wall_offset")
        layout.prop(props, "has_bastion_towers")
        if props.has_bastion_towers:
            layout.prop(props, "bastion_tower_count")
            layout.prop(props, "bastion_tower_size")
            layout.prop(props, "bastion_tower_height")
        layout.prop(props, "has_mounted_shields")
        if props.has_mounted_shields:
            layout.prop(props, "shield_placement")
        layout.prop(props, "has_battlements")
        if props.has_battlements:
            layout.prop(props, "battlement_style")
        layout.prop(props, "has_banners")
        if props.has_banners:
            layout.prop(props, "banner_count")
            layout.prop(props, "color_banner")
        layout.prop(props, "has_gable_crest")
        if props.has_gable_crest:
            layout.prop(props, "gable_crest_style")
            layout.prop(props, "gable_crest_scale")
        layout.prop(props, "has_military_props")
        if props.has_military_props:
            layout.prop(props, "military_props_count")


# ---------------------------------------------------------------------------
# 12. Estate grounds
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_estate(bpy.types.Panel):
    """Detached outbuildings, fountain, awnings, plot offsets."""
    bl_label = "Estate Grounds"
    bl_idname = "VIEW3D_PT_fantasy_building_estate"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        row = layout.row(align=True)
        row.prop(props, "has_stable")
        row.prop(props, "has_servant_quarters")
        layout.prop(props, "has_estate_fountain")
        layout.prop(props, "estate_awnings")
        if props.has_stable or props.has_servant_quarters or props.has_estate_fountain:
            col = layout.column(align=True)
            if props.has_stable:
                col.prop(props, "stable_side")
            if props.has_servant_quarters:
                col.prop(props, "servant_quarters_side")
            col.prop(props, "outbuilding_offset_x")
            col.prop(props, "outbuilding_offset_y")
            col.prop(props, "plot_setback")


# ---------------------------------------------------------------------------
# 13. Construction (NEW: scaffold / under construction)
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_construction(bpy.types.Panel):
    """Scaffold shell + yard dressing so any building reads as under construction."""
    bl_label = "Construction Scaffold"
    bl_idname = "VIEW3D_PT_fantasy_building_construction"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fantasy Building"
    bl_parent_id = "VIEW3D_PT_fantasy_building_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.fantasy_building_settings

        layout.prop(props, "has_construction")
        if not props.has_construction:
            layout.label(text="Enable for scaffold presets below.", icon='INFO')
            return
        layout.prop(props, "construction_mode", text="")
        if props.construction_mode == 'EMPTY_SITE':
            layout.label(text="No walls/roof built. Width/Depth/Floors", icon='OUTLINER_OB_EMPTY')
            layout.label(text="set the future building size.")
        box = layout.box()
        box.label(text="Plot & Walkway", icon='MOD_BUILD')
        box.prop(props, "construction_plot")
        if props.construction_plot == 'CUSTOM':
            row = box.row(align=True)
            row.prop(props, "scaffold_width", text="Width")
            row.prop(props, "scaffold_depth", text="Depth")
        else:
            box.prop(props, "scaffold_padding", slider=True)
        box.prop(props, "scaffold_levels")
        box.prop(props, "scaffold_height", text="Height (0 = Auto)")
        box = layout.box()
        box.label(text="Site Dressing", icon='HOME')
        box.prop(props, "scaffold_tarp")
        box.prop(props, "construction_piles")
        box.prop(props, "construction_crane")


# ---------------------------------------------------------------------------
# 14. Materials
# ---------------------------------------------------------------------------

class VIEW3D_PT_fantasy_building_materials(bpy.types.Panel):
    """Material tier, masonry, colors, glow, overrides."""
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

        box_t = layout.box()
        box_t.label(text="Material Tier", icon='MATERIAL')
        box_t.prop(props, "material_tier", expand=True)
        box_t.prop(props, "physical_siding")

        if (props.material_tier == 'TIER_3' or props.ground_floor_stone) and props.physical_siding:
            box_t.label(text="Stone Masonry Style", icon='SNAP_VOLUME')
            col = box_t.column(align=True)
            col.prop(props, "stone_block_scale", slider=True)
            col.prop(props, "stone_disorder", slider=True)

        box_uv = layout.box()
        box_uv.label(text="Handpaint UVs", icon='UV')
        box_uv.prop(props, "split_by_material", text="Split by Material")

        box_c = layout.box()
        box_c.label(text="Procedural Colors", icon='COLOR')
        box_c.prop(props, "color_palette")
        grid = box_c.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
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

        box_g = layout.box()
        box_g.label(text="Night Window Glow", icon='LIGHT_SUN')
        box_g.prop(props, "window_glow_strength", slider=True)
        if props.window_glow_strength > 0.01:
            box_g.prop(props, "color_window_glow")

        box_x = layout.box()
        box_x.label(text="Custom Material Overrides", icon='MATERIAL')
        col = box_x.column(align=True)
        col.prop(props, "custom_shingles", text="Shingles Mat")
        col.prop(props, "custom_wall_ext", text="Wall Ext Mat")
        col.prop(props, "custom_wall_brick", text="Exposed Brick Mat")
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
