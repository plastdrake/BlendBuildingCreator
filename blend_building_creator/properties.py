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
            ('CIVIC', "Civic", "Town halls and civic estates"),
            ('MILITARY', "Military", "Barracks and military quarters"),
            ('INDUSTRIAL', "Industrial", "Warehouses, storage, and lumbermills"),
            ('RESIDENTIAL', "Residential", "Houses, cottages, and town residences"),
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
        min=3.5, max=50.0, default=6.0,
        unit='LENGTH',
        update=on_property_updated
    )
    
    depth: FloatProperty(
        name="Depth",
        description="Building depth (Y axis) in meters",
        min=3.5, max=50.0, default=5.0,
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
            ('U_SHAPE', "U-Shaped", "U-shaped courtyard footprint with dual projecting wings"),
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
        min=2.5, max=30.0, default=3.5,
        unit='LENGTH',
        update=on_property_updated
    )
    
    wing_depth: FloatProperty(
        name="Wing Projection",
        description="Forward or outward projection distance of the wing",
        min=2.0, max=30.0, default=3.0,
        unit='LENGTH',
        update=on_property_updated
    )

    wing_placement: EnumProperty(
        name="Wing Facade",
        description="Wall facade where the wing projects from",
        items=[
            ('FRONT', "Front (-Y)", "Project wing from the front facade"),
            ('BACK', "Back (+Y)", "Project wing from the rear facade"),
            ('LEFT', "Left (-X)", "Project wing from the left facade"),
            ('RIGHT', "Right (+X)", "Project wing from the right facade"),
        ],
        default='FRONT',
        update=on_property_updated
    )
    
    wing_side: EnumProperty(
        name="Wing Side",
        description="Alignment of the L-shaped wing along its wall",
        items=[
            ('RIGHT', "Right / Positive", "Project wing on the right or positive side"),
            ('LEFT', "Left / Negative", "Project wing on the left or negative side"),
        ],
        default='RIGHT',
        update=on_property_updated
    )

    courtyard_width: FloatProperty(
        name="Courtyard Width",
        description="Width of the central open courtyard between dual wings on U-shaped buildings",
        min=2.0, max=30.0, default=3.5,
        unit='LENGTH',
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
        min=0.0, max=0.40, default=0.0,
        update=on_property_updated
    )
    
    building_archetype: EnumProperty(
        name="Building Archetype",
        description="Purpose-built specialized architectural features matching the building's role",
        items=[
            ('AUTO', "Auto (From Preset)", "Use specialized features defined by the selected preset"),
            ('NONE', "None (Standard)", "Standard fantasy building without archetype additions"),
            ('WAREHOUSE', "Warehouse Crane & Cargo", "L-shaped courtyard timber swivel crane and loading bays"),
            ('LUMBERMILL', "Lumbermill Workframe", "Open timber sawmill pavilion with creature treadwheel, saw bench, and log yard"),
            ('BLACKSMITH', "Blacksmith Forge", "Outdoor forge lean-to canopy, stone furnace with chimney, and metal anvil"),
            ('WINDMILL', "Windmill Sails", "4-blade rotating lattice timber windmill rotor on upper facade"),
            ('WATCHTOWER', "Watchtower Parapet", "Machicolated defensive timber hoarding, corbel brackets, and arrow slits"),
            ('TAVERN', "Tavern Porch & Sign", "Covered entrance veranda porch and hanging ornate tavern sign"),
            ('FISHERMAN', "Fisherman Pier & Nets", "Raised timber piling pier stilts and outdoor fish drying net frame"),
            ('BAKERY', "Bakery Bread Oven", "Protruding outdoor curved brick bread oven with chimney flue"),
        ],
        default='AUTO',
        update=on_property_updated
    )

    mill_grade: EnumProperty(
        name="Mill Machinery Grade",
        description="Capability grade of the lumbermill treadwheel sawmill (higher grades add machinery, not footprint)",
        items=[
            ('GRADE_1', "Grade 1: Wheel + Saw Bench", "Compact creature treadwheel driving a single circular saw bench"),
            ('GRADE_2', "Grade 2: Geared + Carriage", "Geared treadwheel with chain drive, rail log carriage, and mini indoor crane"),
            ('GRADE_3', "Grade 3: Line-Shaft Mill", "Great treadwheel with roller infeed table, indoor crane, and full outfeed stacks"),
        ],
        default='GRADE_1',
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

    has_back_door: BoolProperty(
        name="Rear Door",
        description="Walkthrough rear entrance doorway on the back facade",
        default=False,
        update=on_property_updated
    )

    has_side_door: BoolProperty(
        name="Side Door",
        description="Walkthrough secondary entrance doorway on a side facade",
        default=False,
        update=on_property_updated
    )

    side_door_facade: EnumProperty(
        name="Side Door Facade",
        description="Which side wall has the secondary entrance",
        items=[
            ('RIGHT', "Right (+X)", "Right side wall entrance"),
            ('LEFT', "Left (-X)", "Left side wall entrance"),
        ],
        default='RIGHT',
        update=on_property_updated
    )
    
    door_width: FloatProperty(
        name="Door Width",
        description="Width of door opening in meters",
        min=0.8, max=2.4, default=1.05,
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
        description="Angle of door leaf in degrees (0 = closed, 45 = ajar, 90 = wide open). Also drives the balcony doors",
        min=0.0, max=110.0, default=0.0,
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

    window_spacing: FloatProperty(
        name="Window Spacing",
        description="Horizontal spacing between windows. Lower values = more windows, higher values = fewer windows",
        min=1.2, max=4.5, default=2.4,
        unit='LENGTH',
        update=on_property_updated
    )

    window_density: FloatProperty(
        name="Window Density",
        description="Density multiplier for windows (0.5 = sparse, 1.0 = normal, 1.5 = dense)",
        min=0.4, max=2.5, default=0.6,
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

    shutter_state: EnumProperty(
        name="Shutter State",
        description="Control whether window shutters are open, closed, or partially closed",
        items=[
            ('OPEN', "All Open", "All shutters swung wide open"),
            ('CLOSED', "All Closed", "All shutters closed flat over windows"),
            ('PARTIAL', "Selective / Mixed", "Randomly close a percentage of shutters"),
        ],
        default='OPEN',
        update=on_property_updated
    )

    shutter_closed_amount: FloatProperty(
        name="Closed Percentage",
        description="Percentage of shutters that are closed when in Selective mode",
        min=0.0, max=1.0, default=0.5,
        subtype='FACTOR',
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
    
    roof_orientation: EnumProperty(
        name="Roof Orientation",
        description="Orientation of the main roof ridge and gables",
        items=[
            ('FRONT_BACK', 'Front-to-Back (0°)', 'Roof ridge runs front to back with gables facing front and rear'),
            ('LEFT_RIGHT', 'Side-to-Side (90°)', 'Roof ridge runs side to side with gables facing left and right'),
            ('AUTO', 'Auto (Aspect Ratio)', 'Automatically align roof ridge along the building long axis'),
        ],
        default='FRONT_BACK',
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

    wing_roof_scale: FloatProperty(
        name="Wing Roof Height",
        description="Height of a projecting wing's roof as a fraction of the main roof height. Lower values tuck the wing roof under the main roof",
        min=0.4, max=1.4, default=0.88,
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

    dormer_count: IntProperty(
        name="Dormer Count",
        description="Number of dormers on the main roof",
        default=2,
        min=1,
        max=8,
        update=on_property_updated
    )

    dormer_sides: EnumProperty(
        name="Dormer Sides",
        description="Roof slopes to place dormer windows on",
        items=[
            ('BOTH', "Both Slopes", "Distribute dormers across both roof slopes"),
            ('FRONT_LEFT', "Front / Left Slope", "Place dormers only on the front or left slope"),
            ('BACK_RIGHT', "Back / Right Slope", "Place dormers only on the back or right slope"),
        ],
        default='BOTH',
        update=on_property_updated
    )

    has_wing_dormers: BoolProperty(
        name="Wing Dormers",
        description="Place dormer windows on building wing roofs",
        default=True,
        update=on_property_updated
    )

    wing_dormer_count: IntProperty(
        name="Dormers per Wing",
        description="Number of dormers on each wing roof",
        default=1,
        min=1,
        max=4,
        update=on_property_updated
    )

    wing_dormer_sides: EnumProperty(
        name="Wing Dormer Sides",
        description="Wing roof slopes to place dormers on",
        items=[
            ('BOTH', "Both Slopes", "Place dormers on both slopes of the wing roof"),
            ('OUTER', "Outer Slopes Only", "Place dormers on the exterior-facing slopes of each wing"),
            ('INNER', "Inner Slopes Only", "Place dormers on the interior/courtyard-facing slopes of each wing"),
        ],
        default='BOTH',
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

    has_loft_hatch: BoolProperty(
        name="Gable Loft Hatch",
        description="Timber attic hatch door on the gable end with an exterior ladder from the ground (auto picks the clearest gable)",
        default=False,
        update=on_property_updated
    )

    # --- Architectural Outcrops, Balconies & Overhangs ---
    has_mini_wing: BoolProperty(
        name="Mini-Wing Outcrops",
        description="Add small outcrop bay rooms / oriel projections that spread themselves over the free slots on the facades",
        default=False,
        update=on_property_updated
    )

    mini_wing_width: FloatProperty(
        name="Outcrop Width",
        description="Width of the mini wing along the facade wall",
        min=1.4, max=8.0, default=2.2,
        update=on_property_updated
    )

    mini_wing_count: IntProperty(
        name="Outcrop Amount",
        description="Total number of outcrops on the building; they share themselves out over the storeys and open slots (the amount is reduced when there is not enough room)",
        min=1, max=12, default=2,
        update=on_property_updated
        )

    mini_wing_random: BoolProperty(
        name="Scatter Outcrops",
        description="Pick random open slots instead of spacing the outcrops evenly along each facade",
        default=True,
        update=on_property_updated
        )



    mini_wing_depth: FloatProperty(
        name="Outcrop Depth",
        description="Projection distance outward from the facade",
        min=0.9, max=3.2, default=1.6,
        update=on_property_updated
    )

    mini_wing_random_size: BoolProperty(
        name="Use Random Size",
        description="Give every outcrop a random width and depth instead of one fixed size",
        default=False,
        update=on_property_updated
    )

    mini_wing_random_width: FloatProperty(
        name="Random Width Amount",
        description="How far each outcrop's width may stray from the Outcrop Width (plus or minus, clamped to the wall slots)",
        min=0.0, max=2.0, default=0.4,
        unit='LENGTH',
        update=on_property_updated
    )

    mini_wing_random_depth: FloatProperty(
        name="Random Depth Amount",
        description="How far each outcrop's depth may stray from the Outcrop Depth (plus or minus)",
        min=0.0, max=2.0, default=0.3,
        unit='LENGTH',
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

    mini_wing_shingle_rot: EnumProperty(
        name="Outcrop Shingle Rotation",
        description="Rotate the outcrop roof shingle UVs by 0/90/180/270 degrees",
        items=[
            ('0', "0 deg", "No rotation"),
            ('90', "90 deg", "Rotate 90 degrees"),
            ('180', "180 deg", "Rotate 180 degrees"),
            ('270', "270 deg", "Rotate 270 degrees"),
        ],
        default='0',
        update=on_property_updated
    )

    mini_wing_shingle_scale: FloatProperty(
        name="Outcrop Shingle Size",
        description="UV scale for the outcrop roof shingles (matches the main roofs at 0.32; smaller value = bigger tiles)",
        min=0.05, max=0.60, default=0.32,
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

    balcony_mode: EnumProperty(
        name="Balcony Placement",
        description="Choose which floor levels receive balconies",
        items=[
            ('SINGLE', "Single Floor", "Place a balcony on a single specified floor"),
            ('ALL_UPPER', "All Upper Floors", "Place matching balconies on every upper floor"),
            ('CUSTOM', "Custom Levels", "Select individual floor levels for balconies"),
        ],
        default='SINGLE',
        update=on_property_updated
    )

    balcony_floor: IntProperty(
        name="Balcony Floor",
        description="Upper floor index where the balcony is located (2 = second story)",
        min=2, max=6, default=2,
        update=on_property_updated
    )

    balcony_fl2: BoolProperty(
        name="Floor 2 Balcony",
        description="Place balcony on 2nd floor",
        default=True,
        update=on_property_updated
    )

    balcony_fl3: BoolProperty(
        name="Floor 3 Balcony",
        description="Place balcony on 3rd floor",
        default=False,
        update=on_property_updated
    )

    balcony_fl4: BoolProperty(
        name="Floor 4 Balcony",
        description="Place balcony on 4th floor",
        default=False,
        update=on_property_updated
    )

    balcony_fl5: BoolProperty(
        name="Floor 5 Balcony",
        description="Place balcony on 5th floor",
        default=False,
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

    # --- Civic Landmarks: Clock Tower, Turrets, Ramp & Porch ---
    has_clock_tower: BoolProperty(
        name="Clock Tower",
        description="Attached civic clock/belfry tower with 4 dials, belfry and spire",
        default=False,
        update=on_property_updated
    )

    clock_tower_side: EnumProperty(
        name="Tower Side",
        description="Which front corner the clock tower anchors to",
        items=[
            ('RIGHT', "Right (+X)", "Front-right corner tower"),
            ('LEFT', "Left (-X)", "Front-left corner tower"),
        ],
        default='RIGHT',
        update=on_property_updated
    )

    clock_tower_size: FloatProperty(
        name="Tower Size",
        description="Footprint width of the clock tower shaft",
        min=2.4, max=4.0, default=3.0,
        unit='LENGTH',
        update=on_property_updated
    )

    has_corner_turrets: BoolProperty(
        name="Corner Turrets",
        description="Pair of small octagonal turrets on the rear corners",
        default=False,
        update=on_property_updated
    )

    corner_turret_size: FloatProperty(
        name="Turret Size",
        description="Radius of the rear corner turrets",
        min=1.0, max=2.0, default=1.35,
        unit='LENGTH',
        update=on_property_updated
    )

    has_roof_clock_spire: BoolProperty(
        name="Roof Clock Spire",
        description="Small roof-mounted spire turret with clock dials (Tier 1/2 halls)",
        default=False,
        update=on_property_updated
    )

    roof_clock_scale: FloatProperty(
        name="Clock Spire Scale",
        description="Overall scale of the roof clock spire",
        min=0.6, max=1.6, default=0.85,
        update=on_property_updated
    )

    roof_clock_pos_x: FloatProperty(
        name="Clock Slope Position",
        description="Position across roof slope (-1.0 to 1.0)",
        min=-1.0, max=1.0, default=0.0,
        update=on_property_updated
    )

    roof_clock_pos_y: FloatProperty(
        name="Clock Length Position",
        description="Position along roof length (-1.0 to 1.0)",
        min=-1.0, max=1.0, default=-0.20,
        update=on_property_updated
    )

    has_side_rampart: BoolProperty(
        name="Side Rampart",
        description="Elevated side rampart walk with parapets, upper door and descent ramp (Tier 3)",
        default=False,
        update=on_property_updated
    )

    rampart_side: EnumProperty(
        name="Rampart Side",
        description="Building side carrying the elevated rampart walk",
        items=[
            ('RIGHT', "Right (+X)", "Rampart along the right wall"),
            ('LEFT', "Left (-X)", "Rampart along the left wall"),
        ],
        default='RIGHT',
        update=on_property_updated
    )

    has_entry_ramp: BoolProperty(
        name="Entry Ramp",
        description="Gentle sloped accessibility ramp with railings beside the entrance",
        default=False,
        update=on_property_updated
    )

    has_arched_porch: BoolProperty(
        name="Arched Entry Porch",
        description="Stone pier porch with mini gable roof over the main door",
        default=False,
        update=on_property_updated
    )

    # --- Town Hall Composer: multi-volume sprawling civic composition ---
    town_hall_composer: BoolProperty(
        name="Town Hall Composer",
        description="Layer side annex, forecourt walls and tower arch around the main hall for a sprawling storybook mass",
        default=False,
        update=on_property_updated
    )

    has_side_annex: BoolProperty(
        name="Side Annex",
        description="Half-timbered side volume with its own perpendicular gable roof and oriel",
        default=False,
        update=on_property_updated
    )

    annex_floors: IntProperty(
        name="Annex Floors",
        description="Storeys of the side annex volume",
        min=1, max=2, default=2,
        update=on_property_updated
    )

    # --- Fortifications: Palisade, Banners, Battlements, Military Props ---
    has_palisade: BoolProperty(
        name="Palisade Wall",
        description="Pointed stake / picket stockade enclosing the compound with a front gate",
        default=False,
        update=on_property_updated
    )

    palisade_style: EnumProperty(
        name="Palisade Style",
        description="Stake profile of the stockade",
        items=[
            ('STAKES', "Rough Stakes", "Irregular pointed log stakes"),
            ('PICKET', "Neat Picket", "Even tapered pickets with a backing rail"),
        ],
        default='STAKES',
        update=on_property_updated
    )

    palisade_height: FloatProperty(
        name="Palisade Height",
        description="Height of the stockade stakes in meters",
        min=1.4, max=3.2, default=2.3,
        unit='LENGTH',
        update=on_property_updated
    )

    palisade_offset: FloatProperty(
        name="Palisade Offset",
        description="Distance the stockade stands outside the building footprint",
        min=0.8, max=8.0, default=3.0,
        unit='LENGTH',
        update=on_property_updated
    )

    has_banners: BoolProperty(
        name="Banners",
        description="Heraldic standard poles raised at the gate and compound corners",
        default=False,
        update=on_property_updated
    )

    banner_count: IntProperty(
        name="Banner Count",
        description="Number of banner poles to raise",
        min=2, max=10, default=4,
        update=on_property_updated
    )

    has_battlements: BoolProperty(
        name="Crenellated Battlements",
        description="Merlons and crenels capping the rampart walk",
        default=False,
        update=on_property_updated
    )

    battlement_style: EnumProperty(
        name="Battlement Style",
        description="Material of the crenellations",
        items=[
            ('STONE', "Stone Merlons", "Solid masonry merlons with cut-stone coping"),
            ('TIMBER', "Timber Hoarding", "Boxed timber merlons on a plank rail"),
        ],
        default='STONE',
        update=on_property_updated
    )

    has_military_props: BoolProperty(
        name="Military Props",
        description="Weapon racks, wall shields and training dummies in the yard",
        default=False,
        update=on_property_updated
    )

    military_props_count: IntProperty(
        name="Prop Count",
        description="Number of yard props (weapon rack / shield / training dummy) to place",
        min=1, max=8, default=3,
        update=on_property_updated
    )

    military_rack_count: IntProperty(
        name="Weapon Racks",
        description="Number of A-frame weapon racks in the drill yard",
        min=0, max=6, default=2,
        update=on_property_updated
    )

    military_dummy_count: IntProperty(
        name="Training Pells",
        description="Number of padded training pells (dummies) in the drill yard",
        min=0, max=6, default=3,
        update=on_property_updated
    )

    military_target_count: IntProperty(
        name="Archery Targets",
        description="Number of archery targets in the drill yard",
        min=0, max=6, default=3,
        update=on_property_updated
    )

    color_banner: FloatVectorProperty(
        name="Banner Color",
        subtype='COLOR',
        size=4,
        default=(0.55, 0.12, 0.12, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )

    has_mounted_shields: BoolProperty(
        name="Mounted Shields",
        description="Line palisades, rampart walks, or walls with painted fantasy round shields",
        default=False,
        update=on_property_updated
    )

    shield_placement: EnumProperty(
        name="Shield Placement",
        description="Where to mount the round shields",
        items=[
            ('PALISADE', "Palisade Fence", "Mount along the palisade perimeter"),
            ('RAMPART', "Rampart Walk", "Mount along elevated rampart railings"),
            ('ALL', "All Fortifications", "Mount along both palisade fences and rampart walks"),
        ],
        default='ALL',
        update=on_property_updated
    )

    has_gable_crest: BoolProperty(
        name="Gable Heraldic Crest",
        description="Mount an ornamental heraldic heater shield with crossed broadswords on the facade/gable",
        default=False,
        update=on_property_updated
    )

    gable_crest_style: EnumProperty(
        name="Crest Style",
        description="Style of the mounted heraldic crest",
        items=[
            ('CROSSED_SWORDS', "Crossed Swords", "Two crossed broadswords behind a heater shield"),
            ('SHIELD_ONLY', "Shield Plaque", "Ornamental heraldic shield plaque only"),
        ],
        default='CROSSED_SWORDS',
        update=on_property_updated
    )

    gable_crest_scale: FloatProperty(
        name="Crest Scale",
        description="Size multiplier for the mounted gable crest",
        min=0.5, max=2.5, default=1.0,
        update=on_property_updated
    )

    has_bastion_towers: BoolProperty(
        name="Corner Bastion Towers",
        description="Heavy stone bastion towers with battered talus bases at compound corners (Citadel Tier 3)",
        default=False,
        update=on_property_updated
    )

    bastion_tower_count: IntProperty(
        name="Bastion Towers",
        description="Number of corner bastion towers (2 for front corners, 4 for full enclosure)",
        min=2, max=4, default=2,
        update=on_property_updated
    )

    bastion_tower_size: FloatProperty(
        name="Bastion Size",
        description="Square shaft width of the bastion towers in meters",
        min=2.0, max=5.0, default=3.2,
        unit='LENGTH',
        update=on_property_updated
    )

    bastion_tower_height: FloatProperty(
        name="Bastion Height",
        description="Overall height of the bastion towers in meters",
        min=5.0, max=14.0, default=8.2,
        unit='LENGTH',
        update=on_property_updated
    )

    has_curtain_wall: BoolProperty(
        name="Stone Curtain Wall",
        description="Masonry perimeter wall with a rampart walk, crenellated parapet, arrow slits and a gatehouse (used instead of the timber palisade)",
        default=False,
        update=on_property_updated
    )

    curtain_wall_height: FloatProperty(
        name="Curtain Height",
        description="Height of the stone curtain wall in meters",
        min=2.4, max=4.5, default=3.2,
        unit='LENGTH',
        update=on_property_updated
    )

    curtain_wall_thickness: FloatProperty(
        name="Curtain Thickness",
        description="Thickness of the stone curtain wall in meters",
        min=0.35, max=0.90, default=0.55,
        unit='LENGTH',
        update=on_property_updated
    )

    curtain_wall_offset: FloatProperty(
        name="Curtain Offset",
        description="Distance the curtain wall stands outside the building footprint",
        min=1.5, max=8.0, default=3.0,
        unit='LENGTH',
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

    has_exposed_brick: BoolProperty(
        name="Exposed Brick Accents",
        description="Expose terracotta clay brickwork beneath chipped stucco on select wall panels and corners",
        default=True,
        update=on_property_updated
    )

    exposed_brick_frequency: FloatProperty(
        name="Brick Frequency",
        description="Chance/density of stucco wall panels showing exposed terracotta brickwork (0.0 = none, 1.0 = all)",
        min=0.0, max=1.0, default=0.25,
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
    custom_wall_brick: PointerProperty(type=bpy.types.Material, name="Exposed Brick Stucco Mat", update=on_property_updated)
    custom_banner: PointerProperty(type=bpy.types.Material, name="Banner Mat", update=on_property_updated)
