"""
Blender PropertyGroups for Stylized Fantasy Building Generator.
Defines parameters for geometry, floors, walk-in interior, openings, roof, and materials.
"""

import bpy
from bpy.props import (
    IntProperty, FloatProperty, BoolProperty, EnumProperty,
    FloatVectorProperty, PointerProperty, StringProperty
)

def on_property_updated(self, context):
    """Callback when any property is changed in the UI."""
    if not getattr(self, "auto_update", True):
        return
        
    obj = context.active_object
    if obj and obj.get("is_fantasy_building", False):
        from .generator.building import generate_building
        generate_building(obj, self)

def on_tier_updated(self, context):
    """When the user changes material tier, dynamically scale layout, floors, and dimensions."""
    if not getattr(self, "auto_update", True):
        return
        
    tier = getattr(self, "material_tier", "TIER_3")
    # Temporarily prevent recursive regeneration while updating multiple parameters
    self.auto_update = False
    if tier == 'TIER_1':
        self.num_floors = 1
        self.width = 5.2
        self.depth = 6.0
        self.foundation_height = 0.35
        self.has_cantilever = False
        self.ground_floor_stone = False
        self.has_timber_framing = False
    elif tier == 'TIER_2':
        self.num_floors = 2
        self.width = 6.8
        self.depth = 7.8
        self.foundation_height = 0.55
        self.has_cantilever = True
        self.cantilever_overhang = 0.35
        self.ground_floor_stone = False
        self.has_timber_framing = True
    elif tier == 'TIER_3':
        self.num_floors = 3
        self.width = 8.8
        self.depth = 9.8
        self.foundation_height = 0.90
        self.has_cantilever = True
        self.cantilever_overhang = 0.40
        self.ground_floor_stone = True
        self.has_timber_framing = True
    self.auto_update = True
    
    on_property_updated(self, context)

def on_palette_updated(self, context):
    """Applies curated stylized fantasy color palettes inspired by game and animation art."""
    if not getattr(self, "auto_update", True):
        return
        
    palette = getattr(self, "color_palette", "CUSTOM")
    if palette == 'CUSTOM':
        return
        
    self.auto_update = False
    if palette == 'STORMWIND':
        self.color_shingles = (0.12, 0.22, 0.48, 1.0)
        self.color_stone = (0.46, 0.44, 0.42, 1.0)
        self.color_wall_ext = (0.92, 0.86, 0.74, 1.0)
        self.color_wall_int = (0.90, 0.86, 0.80, 1.0)
        self.color_timber_frame = (0.24, 0.14, 0.08, 1.0)
        self.color_timber = (0.34, 0.20, 0.12, 1.0)
        self.color_door = (0.30, 0.18, 0.10, 1.0)
        self.color_floor = (0.42, 0.28, 0.16, 1.0)
    elif palette == 'HEARTHSIDE':
        self.color_shingles = (0.75, 0.38, 0.16, 1.0)
        self.color_stone = (0.38, 0.38, 0.38, 1.0)
        self.color_wall_ext = (0.88, 0.83, 0.73, 1.0)
        self.color_wall_int = (0.92, 0.88, 0.82, 1.0)
        self.color_timber_frame = (0.32, 0.18, 0.09, 1.0)
        self.color_timber = (0.40, 0.24, 0.14, 1.0)
        self.color_door = (0.42, 0.26, 0.15, 1.0)
        self.color_floor = (0.46, 0.30, 0.18, 1.0)
    elif palette == 'MOSS_CEDAR':
        self.color_shingles = (0.22, 0.38, 0.20, 1.0)
        self.color_stone = (0.36, 0.37, 0.35, 1.0)
        self.color_wall_ext = (0.82, 0.79, 0.72, 1.0)
        self.color_wall_int = (0.86, 0.84, 0.78, 1.0)
        self.color_timber_frame = (0.26, 0.20, 0.14, 1.0)
        self.color_timber = (0.32, 0.25, 0.18, 1.0)
        self.color_door = (0.30, 0.22, 0.15, 1.0)
        self.color_floor = (0.38, 0.28, 0.18, 1.0)
    elif palette == 'VINTAGE_SLATE':
        self.color_shingles = (0.32, 0.24, 0.38, 1.0)
        self.color_stone = (0.40, 0.39, 0.38, 1.0)
        self.color_wall_ext = (0.86, 0.82, 0.75, 1.0)
        self.color_wall_int = (0.90, 0.87, 0.82, 1.0)
        self.color_timber_frame = (0.20, 0.12, 0.08, 1.0)
        self.color_timber = (0.28, 0.17, 0.10, 1.0)
        self.color_door = (0.32, 0.18, 0.10, 1.0)
        self.color_floor = (0.36, 0.24, 0.14, 1.0)
    self.auto_update = True
    
    on_property_updated(self, context)

class FantasyBuildingSettings(bpy.types.PropertyGroup):
    auto_update: BoolProperty(
        name="Auto Update",
        description="Automatically regenerate building geometry when parameters change",
        default=True
    )
    
    seed: IntProperty(
        name="Seed",
        description="Random seed for building variation and wonkiness",
        default=42,
        update=on_property_updated
    )
    
    preset_category: EnumProperty(
        name="Preset Category",
        description="Filter architectural presets by category",
        items=[
            ('ALL', "All Presets", "Show all building style presets"),
            ('CIVIC', "Civic & Manor", "Town halls, manors, chapels, and grand inns"),
            ('MILITARY', "Military", "Barracks, archery ranges, and watchtowers"),
            ('ARTISAN', "Artisan Guilds", "Specialized craft shops, bakeries, breweries, and workshops"),
            ('INDUSTRIAL', "Industrial & Craft", "Heavy production, smelteries, mills, and factories"),
            ('COMMERCIAL', "Commercial & Living", "Stores, markets, houses, cottages, and towers"),
        ],
        default='ALL'
    )
    
    # --- Dimensions & Floors ---
    num_floors: IntProperty(
        name="Floors",
        description="Number of walk-in building storeys (1 to 5)",
        min=1, max=5, default=2,
        update=on_property_updated
    )
    
    floor_height: FloatProperty(
        name="Floor Height",
        description="Height per storey in meters",
        min=2.2, max=4.5, default=2.8,
        unit='LENGTH',
        update=on_property_updated
    )
    
    width: FloatProperty(
        name="Width",
        description="Building width (X axis) in meters",
        min=3.5, max=16.0, default=6.0,
        unit='LENGTH',
        update=on_property_updated
    )
    
    depth: FloatProperty(
        name="Depth",
        description="Building depth (Y axis) in meters",
        min=3.5, max=16.0, default=5.0,
        unit='LENGTH',
        update=on_property_updated
    )
    
    building_shape: EnumProperty(
        name="Building Shape",
        description="Overall architectural footprint geometry",
        items=[
            ('RECTANGLE', "Rectangular", "Standard rectangular building footprint"),
            ('L_SHAPE', "L-Shaped", "L-shaped footprint with a perpendicular projecting wing"),
            ('T_SHAPE', "T-Shaped", "T-shaped footprint with a central projecting cross wing"),
            ('ROUND_TOWER', "Round Tower", "Cylindrical / octagonal fantasy tower footprint"),
        ],
        default='RECTANGLE',
        update=on_property_updated
    )
    
    wing_floors: IntProperty(
        name="Wing Floors",
        description="Number of storeys for the projecting wing",
        min=1, max=5, default=1,
        update=on_property_updated
    )
    
    wing_width: FloatProperty(
        name="Wing Width",
        description="Width of the projecting wing",
        min=2.5, max=10.0, default=3.5,
        unit='LENGTH',
        update=on_property_updated
    )
    
    wing_depth: FloatProperty(
        name="Wing Projection",
        description="Forward projection distance of the wing",
        min=2.0, max=10.0, default=3.0,
        unit='LENGTH',
        update=on_property_updated
    )
    
    wing_side: EnumProperty(
        name="Wing Side",
        description="Placement of the L-shaped wing",
        items=[
            ('RIGHT', "Right", "Project wing from right side (+X)"),
            ('LEFT', "Left", "Project wing from left side (-X)"),
        ],
        default='RIGHT',
        update=on_property_updated
    )
    
    wall_thickness: FloatProperty(
        name="Wall Thickness",
        description="Thickness of exterior and interior walls",
        min=0.15, max=0.60, default=0.28,
        unit='LENGTH',
        update=on_property_updated
    )
    
    has_cantilever: BoolProperty(
        name="Upper Floor Overhang",
        description="Cantilever upper floors outward with wooden corbels",
        default=True,
        update=on_property_updated
    )
    
    overhang_mode: EnumProperty(
        name="Overhang Scope",
        description="Choose whether only the 2nd floor overhangs or all floors overhang progressively",
        items=[
            ('SECOND_FLOOR_ONLY', "Second Floor Only", "Only the second floor projects outward; upper floors stay flush with 2nd floor"),
            ('ALL_FLOORS', "Every Floor", "Each successive floor extends outward progressively"),
        ],
        default='SECOND_FLOOR_ONLY',
        update=on_property_updated
    )
    
    cantilever_overhang: FloatProperty(
        name="Overhang Distance",
        description="Distance upper floor extends outward",
        min=0.1, max=0.8, default=0.35,
        unit='LENGTH',
        update=on_property_updated
    )
    
    wonkiness: FloatProperty(
        name="Fantasy Wonkiness",
        description="Whimsical leaning, curvature, and organic asymmetry",
        min=0.0, max=0.40, default=0.08,
        update=on_property_updated
    )
    
    building_archetype: EnumProperty(
        name="Building Archetype",
        description="Purpose-built specialized architectural features matching the building's role",
        items=[
            ('AUTO', "Auto (From Preset)", "Use specialized features defined by the selected preset"),
            ('NONE', "None (Standard)", "Standard fantasy building without archetype additions"),
            ('BLACKSMITH', "Blacksmith Forge", "Outdoor forge lean-to canopy, stone furnace with chimney, and metal anvil"),
            ('WINDMILL', "Windmill Sails", "4-blade rotating lattice timber windmill rotor on upper facade"),
            ('WATCHTOWER', "Watchtower Parapet", "Machicolated defensive timber hoarding, corbel brackets, and arrow slits"),
            ('TAVERN', "Tavern Porch & Sign", "Covered entrance veranda porch and hanging ornate tavern sign"),
            ('FISHERMAN', "Fisherman Pier & Nets", "Raised timber piling pier stilts and outdoor fish drying net frame"),
            ('BAKERY', "Bakery Bread Oven", "Protruding outdoor curved brick bread oven with chimney flue"),
            ('WAREHOUSE', "Warehouse Hoist & Crates", "Front roof hoist beam, cargo hook, double doors, and stacked crates"),
        ],
        default='AUTO',
        update=on_property_updated
    )
    
    # --- Foundation ---
    has_foundation: BoolProperty(
        name="Stone Foundation",
        description="Chunky stone foundation base",
        default=True,
        update=on_property_updated
    )
    
    foundation_height: FloatProperty(
        name="Foundation Height",
        description="Height of cobblestone foundation",
        min=0.2, max=2.0, default=0.6,
        unit='LENGTH',
        update=on_property_updated
    )
    
    ground_floor_stone: BoolProperty(
        name="Stone Ground Floor",
        description="Use cobblestone floor for ground floor (wood for upper floors)",
        default=True,
        update=on_property_updated
    )
    
    has_front_steps: BoolProperty(
        name="Front Steps",
        description="Chunky stone entrance steps leading to front door",
        default=True,
        update=on_property_updated
    )
    
    # --- Interior ---
    has_stairs: BoolProperty(
        name="Staircases",
        description="Generate staircases connecting floor storeys",
        default=True,
        update=on_property_updated
    )
    
    stair_style: EnumProperty(
        name="Stair Style",
        description="Type of staircase connecting floors",
        items=[
            ('STRAIGHT', 'Straight Run', 'Wooden staircase with steps, stringers and handrail'),
            ('SPIRAL', 'Fantasy Spiral', 'Curved spiral staircase around central wooden post')
        ],
        default='STRAIGHT',
        update=on_property_updated
    )
    
    stair_width: FloatProperty(
        name="Stair Width",
        description="Width of interior staircase and floor cutout",
        min=0.7, max=1.5, default=0.95,
        unit='LENGTH',
        update=on_property_updated
    )
    
    has_ceiling_beams: BoolProperty(
        name="Ceiling Beams",
        description="Rustic exposed wooden ceiling beams in rooms",
        default=True,
        update=on_property_updated
    )
    
    # --- Openings & Doors ---
    has_front_door: BoolProperty(
        name="Front Door",
        description="Walkthrough front entrance doorway",
        default=True,
        update=on_property_updated
    )
    
    door_width: FloatProperty(
        name="Door Width",
        description="Width of door opening in meters",
        min=0.8, max=1.6, default=1.05,
        unit='LENGTH',
        update=on_property_updated
    )
    
    door_height: FloatProperty(
        name="Door Height",
        description="Height of door opening in meters",
        min=1.9, max=2.8, default=2.2,
        unit='LENGTH',
        update=on_property_updated
    )
    
    door_angle: FloatProperty(
        name="Door Open Angle",
        description="Angle of door leaf in degrees (0 = closed, 45 = ajar, 90 = wide open)",
        min=0.0, max=110.0, default=40.0,
        update=on_property_updated
    )
    
    door_shape: EnumProperty(
        name="Portal Style",
        description="Architectural design of the entrance doorway",
        items=[
            ('AUTO', "Auto (Stone Arch / Timber)", "Stone arch on stone walls/foundations, square timber on wood walls"),
            ('ARCHED', "Arched Stone Portal", "Iconic fantasy arched stone portal with radial voussoirs and keystone"),
            ('SQUARE', "Square Timber Frame", "Sturdy timber post-and-lintel door frame"),
        ],
        default='AUTO',
        update=on_property_updated
    )
    
    has_windows: BoolProperty(
        name="Windows",
        description="Stylized multi-pane framed windows",
        default=True,
        update=on_property_updated
    )
    
    window_width: FloatProperty(
        name="Window Width",
        description="Width of window openings in meters",
        min=0.6, max=1.4, default=0.85,
        unit='LENGTH',
        update=on_property_updated
    )
    
    window_height: FloatProperty(
        name="Window Height",
        description="Height of window openings in meters",
        min=0.8, max=1.8, default=1.2,
        unit='LENGTH',
        update=on_property_updated
    )
    
    has_shutters: BoolProperty(
        name="Window Shutters",
        description="Wooden exterior shutters on windows",
        default=True,
        update=on_property_updated
    )
    
    has_flower_boxes: BoolProperty(
        name="Flower Boxes",
        description="Flower planter boxes underneath exterior window sills",
        default=False,
        update=on_property_updated
    )
    
    has_lanterns: BoolProperty(
        name="Iron Lanterns",
        description="Stylized glowing iron lanterns mounted beside entrance",
        default=False,
        update=on_property_updated
    )
    
    # --- Timber Framing ---
    has_timber_framing: BoolProperty(
        name="Timber Framing",
        description="Chunky Tudor-style wooden beams on exterior plaster walls",
        default=True,
        update=on_property_updated
    )
    
    timber_diagonals: BoolProperty(
        name="Diagonal Braces",
        description="Diagonal cross braces in timber framing",
        default=True,
        update=on_property_updated
    )
    
    # --- Roof & Chimney ---
    roof_style: EnumProperty(
        name="Roof Style",
        description="Architectural style of the roof",
        items=[
            ('SWAY', 'Fairytale Sway Roof', 'Curved dipping ridge and flared eaves'),
            ('GABLE', 'Steep Medieval Gable', 'Classic high-pitch dramatic gable'),
            ('TURRET', 'Wizard Turret', 'Faceted conical roof with finial spire')
        ],
        default='SWAY',
        update=on_property_updated
    )
    
    roof_height: FloatProperty(
        name="Roof Height",
        description="Height from top floor to roof ridge",
        min=1.8, max=5.5, default=3.2,
        unit='LENGTH',
        update=on_property_updated
    )
    
    roof_overhang: FloatProperty(
        name="Roof Overhang",
        description="Eaves overhang distance beyond walls",
        min=0.2, max=1.0, default=0.45,
        unit='LENGTH',
        update=on_property_updated
    )
    
    roof_sway: FloatProperty(
        name="Sway Curvature",
        description="Depth of curve sag in the roof ridge line",
        min=0.0, max=0.8, default=0.28,
        update=on_property_updated
    )
    
    roof_flare: FloatProperty(
        name="Bell-Cast Flare",
        description="Concave swooping curve flare at the roof eaves",
        min=0.0, max=0.8, default=0.35,
        update=on_property_updated
    )
    
    has_roof_shingles: BoolProperty(
        name="Layered Shingles",
        description="Stylized overlapping 3D roof shingles with whimsical jitter",
        default=True,
        update=on_property_updated
    )
    
    shingle_rows: IntProperty(
        name="Shingle Rows",
        description="Number of shingle tile rows along each roof slope",
        min=3, max=14, default=6,
        update=on_property_updated
    )
    
    has_dormers: BoolProperty(
        name="Roof Dormers",
        description="Protruding dormer windows on roof slope",
        default=True,
        update=on_property_updated
    )

    has_roof_turret: BoolProperty(
        name="Roof Spire Turret",
        description="Fairytale spire dormer tower perched on the roof",
        default=False,
        update=on_property_updated
    )

    roof_turret_style: EnumProperty(
        name="Turret Style",
        description="Architectural shape of the roof spire turret",
        items=[
            ('OCTAGONAL', "Octagonal Spire", "8-sided fairytale fantasy belfry with conical spire"),
            ('SQUARE', "Square Belfry", "4-sided timber belfry with pyramid spire"),
        ],
        default='OCTAGONAL',
        update=on_property_updated
    )

    roof_turret_pos_x: FloatProperty(
        name="Turret Slope Position",
        description="Position across roof slope (-1.0 left slope, 0.0 ridge, 1.0 right slope)",
        min=-1.0, max=1.0, default=0.0,
        update=on_property_updated
    )

    roof_turret_pos_y: FloatProperty(
        name="Turret Length Position",
        description="Position along roof length (-1.0 to 1.0)",
        min=-1.0, max=1.0, default=-0.25,
        update=on_property_updated
    )

    roof_turret_scale: FloatProperty(
        name="Turret Scale",
        description="Overall scale multiplier of the roof spire turret",
        min=0.5, max=2.0, default=1.0,
        update=on_property_updated
    )
    
    has_chimney: BoolProperty(
        name="Stone Chimney",
        description="Stylized crooked stone chimney with cap and pot",
        default=True,
        update=on_property_updated
    )

    chimney_pos_x: FloatProperty(
        name="Chimney X",
        description="Front-back / left-right offset across roof (-1 to 1). Move to avoid dormers/windows",
        min=-1.0, max=1.0, default=0.55,
        update=on_property_updated
    )

    chimney_pos_y: FloatProperty(
        name="Chimney Y",
        description="Along-roof offset (-1 to 1)",
        min=-1.0, max=1.0, default=0.55,
        update=on_property_updated
    )
    
    has_hoist_beam: BoolProperty(
        name="Roof Hoist Beam",
        description="Projecting heavy timber ridge beam with suspended cargo hook / pulley on the front gable",
        default=False,
        update=on_property_updated
    )

    # --- Architectural Outcrops, Balconies & Overhangs ---
    has_mini_wing: BoolProperty(
        name="Mini-Wing Outcrop",
        description="Add a small outcrop bay room / annex projection to the building",
        default=False,
        update=on_property_updated
    )

    mini_wing_side: EnumProperty(
        name="Outcrop Side",
        description="Wall facade where the mini wing is attached",
        items=[
            ('LEFT', "Left (-X)", "Attached to left facade"),
            ('RIGHT', "Right (+X)", "Attached to right facade"),
            ('BACK', "Back (+Y)", "Attached to rear facade"),
            ('FRONT', "Front (-Y)", "Attached to front facade"),
        ],
        default='LEFT',
        update=on_property_updated
    )

    mini_wing_floor: EnumProperty(
        name="Outcrop Level",
        description="Floor level for the mini-wing outcrop",
        items=[
            ('GROUND', "Ground Floor (Grounded)", "Grounded room resting on stone foundation plinth"),
            ('UPPER', "Upper Floor (Oriel)", "Cantilevered upper-floor oriel bay supported by heavy timber corbels"),
        ],
        default='GROUND',
        update=on_property_updated
    )

    mini_wing_width: FloatProperty(
        name="Outcrop Width",
        description="Width of the mini wing along the facade wall",
        min=1.4, max=4.5, default=2.2,
        update=on_property_updated
    )

    mini_wing_depth: FloatProperty(
        name="Outcrop Depth",
        description="Projection distance outward from the facade",
        min=0.9, max=3.2, default=1.6,
        update=on_property_updated
    )

    mini_wing_roof: EnumProperty(
        name="Outcrop Roof",
        description="Roof style of the mini wing",
        items=[
            ('LEAN_TO', "Lean-To Shed", "Sloping shed roof with timber rafters and shingles"),
            ('GABLE', "Mini Gable", "Pitched gable roof with bargeboards and shingles"),
        ],
        default='LEAN_TO',
        update=on_property_updated
    )

    has_balcony: BoolProperty(
        name="Timber Balcony",
        description="Cantilevered wooden balcony on an upper floor with heavy timber brackets and balustrade",
        default=False,
        update=on_property_updated
    )

    balcony_side: EnumProperty(
        name="Balcony Side",
        description="Wall facade where the balcony is situated",
        items=[
            ('FRONT', "Front (-Y)", "Front facade balcony"),
            ('BACK', "Back (+Y)", "Rear facade balcony"),
            ('LEFT', "Left (-X)", "Left facade balcony"),
            ('RIGHT', "Right (+X)", "Right facade balcony"),
        ],
        default='FRONT',
        update=on_property_updated
    )

    balcony_floor: IntProperty(
        name="Balcony Floor",
        description="Upper floor index where the balcony is located (2 = second story)",
        min=2, max=6, default=2,
        update=on_property_updated
    )

    balcony_width: FloatProperty(
        name="Balcony Width",
        description="Width of the cantilevered balcony platform",
        min=1.2, max=4.5, default=2.4,
        update=on_property_updated
    )

    balcony_depth: FloatProperty(
        name="Balcony Depth",
        description="Projection depth of the cantilevered balcony platform",
        min=0.8, max=2.2, default=1.3,
        update=on_property_updated
    )

    has_pillared_overhang: BoolProperty(
        name="Pillared Overhang",
        description="Colonnaded porch or upper floor overhang supported by heavy vertical pillars down to ground",
        default=False,
        update=on_property_updated
    )

    pillared_overhang_side: EnumProperty(
        name="Pillared Facade",
        description="Wall facade where the colonnade/overhang is erected",
        items=[
            ('FRONT', "Front (-Y)", "Front covered portico / entrance colonnade"),
            ('LEFT', "Left (-X)", "Left side covered portico"),
            ('RIGHT', "Right (+X)", "Right side covered portico"),
            ('BACK', "Back (+Y)", "Rear covered portico"),
        ],
        default='FRONT',
        update=on_property_updated
    )

    pillared_overhang_depth: FloatProperty(
        name="Overhang Depth",
        description="Projection distance of the pillared colonnade / overhang",
        min=0.9, max=3.5, default=1.6,
        update=on_property_updated
    )

    pillared_overhang_pillars: IntProperty(
        name="Pillar Count",
        description="Number of vertical pillars along the facade",
        min=2, max=6, default=3,
        update=on_property_updated
    )

    pillared_overhang_style: EnumProperty(
        name="Pillar Style",
        description="Structural style of vertical pillars",
        items=[
            ('TIMBER_STONE', "Timber on Stone Plinth", "Square timber posts resting on stone plinths with 45-deg braces"),
            ('ROUND_POST', "Rustic Log Posts", "Round tree-trunk log columns with stone bases"),
            ('STONE_COLUMN', "Stone Pillars", "Chunky masonry stone columns"),
        ],
        default='TIMBER_STONE',
        update=on_property_updated
    )
    
    # --- Material Tier & Stylized Procedural Shaders ---
    material_tier: EnumProperty(
        name="Material Tier",
        description="Progression tier determining building wall, roof, and trim materials",
        items=[
            ('TIER_1', "Tier 1: Timber & Log", "Heavy dark timber/log walls, cedar shake roof, fieldstone base"),
            ('TIER_2', "Tier 2: Planks & Weatherboard", "Wooden planks siding, slate roof, clean timber frame"),
            ('TIER_3', "Tier 3: Stone & Stucco", "Dressed ashlar stone, bright medieval stucco, terracotta/slate roof"),
        ],
        default='TIER_3',
        update=on_tier_updated
    )
    
    physical_siding: BoolProperty(
        name="Physical 3D Siding",
        description="Generate physical 3D log beams (Tier 1), overlapping lap/batten planks (Tier 2), and chunky stone blocks (Tier 3)",
        default=True,
        update=on_property_updated
    )

    plank_direction: EnumProperty(
        name="Plank Direction",
        description="Orientation of physical wooden plank siding for Tier 2 buildings",
        items=[
            ('HORIZONTAL', "Horizontal", "Classic horizontal overlapping weatherboard lap planks"),
            ('VERTICAL', "Vertical", "Stylized board-and-batten vertical plank siding"),
        ],
        default='HORIZONTAL',
        update=on_property_updated
    )

    plank_jankiness: FloatProperty(
        name="Plank Jankiness",
        description="Handcrafted irregularity, depth pop, and tilt for wooden plank siding",
        min=0.0, max=1.5, default=0.45,
        update=on_property_updated
    )

    stone_block_scale: FloatProperty(
        name="Stone Block Size",
        description="Scale factor for chunky 3D stone blocks / masonry",
        min=0.4, max=2.5, default=1.0,
        update=on_property_updated
    )

    stone_disorder: FloatProperty(
        name="Stone Disorder",
        description="Random depth pop, block tilt, and irregularity for stone walls",
        min=0.0, max=1.5, default=0.45,
        update=on_property_updated
    )

    open_timber_frame: BoolProperty(
        name="Open Timber Frame",
        description="Convert ground walls into open post-and-beam timber bays (ideal for sheds and mills)",
        default=False,
        update=on_property_updated
    )

    split_by_material: BoolProperty(
        name="Split by Material",
        description="Separate building into multiple objects by material — each piece then has its own conformal UV islands (logs, beams, boards all unwrapped in same fiber direction) for easy handpainting",
        default=False,
        update=on_property_updated
    )
    
    color_palette: EnumProperty(
        name="Color Palette",
        description="Curated stylized fantasy color scheme inspired by references",
        items=[
            ('CUSTOM', "Custom Colors", "Use manual color pickers below"),
            ('STORMWIND', "Stormwind (Cobalt & Gold)", "Deep cobalt blue roof, warm sandstone plaster, rich chocolate timber framing"),
            ('HEARTHSIDE', "Hearthside (Amber Terracotta)", "Warm terracotta orange roof, creamy plaster, honey oak timber, charcoal slate"),
            ('MOSS_CEDAR', "Forest Moss (Green & Cedar)", "Forest moss green roof, weathered cedar timber, rustic fieldstone"),
            ('VINTAGE_SLATE', "Vintage Fantasy (Indigo & Cream)", "Deep purple-indigo slate roof, antique plaster, dark walnut timber"),
        ],
        default='CUSTOM',
        update=on_palette_updated
    )
    
    color_stone: FloatVectorProperty(
        name="Stone Color",
        subtype='COLOR',
        size=4,
        default=(0.42, 0.40, 0.38, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_wall_ext: FloatVectorProperty(
        name="Wall Exterior",
        subtype='COLOR',
        size=4,
        default=(0.88, 0.82, 0.73, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_wall_int: FloatVectorProperty(
        name="Wall Interior",
        subtype='COLOR',
        size=4,
        default=(0.92, 0.88, 0.82, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_timber_frame: FloatVectorProperty(
        name="Timber Frame",
        description="Color for external wall structural beams, posts, and diagonal braces",
        subtype='COLOR',
        size=4,
        default=(0.22, 0.13, 0.07, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_timber: FloatVectorProperty(
        name="General Wood",
        description="Color for stairs, railings, window trim, rafters, and fascia",
        subtype='COLOR',
        size=4,
        default=(0.32, 0.20, 0.11, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_floor: FloatVectorProperty(
        name="Floorboards",
        description="Color for interior floorboards",
        subtype='COLOR',
        size=4,
        default=(0.42, 0.28, 0.16, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_shingles: FloatVectorProperty(
        name="Roof Shingles",
        subtype='COLOR',
        size=4,
        default=(0.20, 0.28, 0.45, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_door: FloatVectorProperty(
        name="Door Color",
        subtype='COLOR',
        size=4,
        default=(0.35, 0.21, 0.12, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_log_end: FloatVectorProperty(
        name="Log End Rings",
        description="Color for cut end-caps of horizontal logs showing tree growth rings",
        subtype='COLOR',
        size=4,
        default=(0.48, 0.32, 0.18, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    window_glow_strength: FloatProperty(
        name="Window Glow",
        description="Warm interior emissive light glow for windows at dusk/night",
        min=0.0, max=10.0, default=0.0,
        update=on_property_updated
    )
    
    color_window_glow: FloatVectorProperty(
        name="Glow Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 0.85, 0.45, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    # --- Custom Scene Material Overrides ---
    custom_stone: PointerProperty(type=bpy.types.Material, name="Stone Mat", update=on_property_updated)
    custom_wall_ext: PointerProperty(type=bpy.types.Material, name="Wall Ext Mat", update=on_property_updated)
    custom_wall_int: PointerProperty(type=bpy.types.Material, name="Wall Int Mat", update=on_property_updated)
    custom_timber_frame: PointerProperty(type=bpy.types.Material, name="Timber Frame Mat", update=on_property_updated)
    custom_timber: PointerProperty(type=bpy.types.Material, name="General Wood Mat", update=on_property_updated)
    custom_floor: PointerProperty(type=bpy.types.Material, name="Floor Mat", update=on_property_updated)
    custom_shingles: PointerProperty(type=bpy.types.Material, name="Shingles Mat", update=on_property_updated)
    custom_glass: PointerProperty(type=bpy.types.Material, name="Glass Mat", update=on_property_updated)
    custom_door: PointerProperty(type=bpy.types.Material, name="Door Mat", update=on_property_updated)
    custom_iron: PointerProperty(type=bpy.types.Material, name="Iron Mat", update=on_property_updated)
    custom_log_end: PointerProperty(type=bpy.types.Material, name="Log End Mat", update=on_property_updated)
    custom_log: PointerProperty(type=bpy.types.Material, name="Log Mat", update=on_property_updated)
    custom_stairs: PointerProperty(type=bpy.types.Material, name="Stairs Mat", update=on_property_updated)
    custom_railing: PointerProperty(type=bpy.types.Material, name="Railing Mat", update=on_property_updated)
    custom_window_frame: PointerProperty(type=bpy.types.Material, name="Window Frame Mat", update=on_property_updated)
    custom_shutter: PointerProperty(type=bpy.types.Material, name="Shutter Mat", update=on_property_updated)
