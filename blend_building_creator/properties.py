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
        min=0.0, max=0.30, default=0.08,
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
        description="Angle of door leaf (0 = closed, 45 = ajar, 90 = wide open)",
        min=0.0, max=110.0, default=40.0,
        unit='ROTATION',
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
        default=True,
        update=on_property_updated
    )
    
    has_lanterns: BoolProperty(
        name="Iron Lanterns",
        description="Stylized glowing iron lanterns mounted beside entrance",
        default=True,
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
    
    has_chimney: BoolProperty(
        name="Stone Chimney",
        description="Stylized crooked stone chimney with cap and pot",
        default=True,
        update=on_property_updated
    )
    
    # --- Material Tier & Stylized Procedural Shaders ---
    material_tier: EnumProperty(
        name="Material Tier",
        description="Progression tier determining building wall, roof, and trim materials",
        items=[
            ('TIER_1', "Tier 1: Timber & Log", "Heavy dark timber/log walls, cedar shake roof, fieldstone base"),
            ('TIER_2', "Tier 2: Planks & Weatherboard", "Horizontal wooden planks siding, slate roof, clean timber frame"),
            ('TIER_3', "Tier 3: Stone & Stucco", "Dressed ashlar stone, bright medieval stucco, terracotta/slate roof"),
        ],
        default='TIER_3',
        update=on_property_updated
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
    
    color_timber: FloatVectorProperty(
        name="Timber Beams",
        subtype='COLOR',
        size=4,
        default=(0.28, 0.16, 0.09, 1.0),
        min=0.0, max=1.0,
        update=on_property_updated
    )
    
    color_floor: FloatVectorProperty(
        name="Floorboards",
        subtype='COLOR',
        size=4,
        default=(0.38, 0.24, 0.14, 1.0),
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
        default=(0.32, 0.19, 0.11, 1.0),
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
    custom_timber: PointerProperty(type=bpy.types.Material, name="Timber Mat", update=on_property_updated)
    custom_floor: PointerProperty(type=bpy.types.Material, name="Floor Mat", update=on_property_updated)
    custom_shingles: PointerProperty(type=bpy.types.Material, name="Shingles Mat", update=on_property_updated)
    custom_glass: PointerProperty(type=bpy.types.Material, name="Glass Mat", update=on_property_updated)
    custom_door: PointerProperty(type=bpy.types.Material, name="Door Mat", update=on_property_updated)
    custom_iron: PointerProperty(type=bpy.types.Material, name="Iron Mat", update=on_property_updated)
