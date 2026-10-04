"""Single source of truth for every standalone / furnishable prop (GRASP).

The registry extracts the prop builders that used to live implicitly inside
preset composers (``furniture``, ``lighting``, ``garden``, ``signage``) plus
the new indoor catalogue (``interior_furniture``) into one declarative table.

* ``PropSpec`` — Information Expert: what a prop is, its category and defaults.
* ``PROP_REGISTRY`` — only place that maps key -> builder (OCP: add a prop by
  adding one entry, never by editing dispatch/operators/UI).
* ``build_prop`` — Polymorphism: one call builds any prop by key.

Builders are resolved lazily by module attribute so this module never imports
bpy and stays unit-testable outside Blender.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

# Category -> label, kept small so the UI dropdown stays readable.
PROP_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ('SEATING', "Seating",),
    ('TABLES', "Tables",),
    ('SLEEP', "Sleep",),
    ('STORAGE', "Storage",),
    ('WORK', "Work & Trade",),
    ('KITCHEN', "Kitchen & Hearth",),
    ('LIGHT', "Lighting",),
    ('YARD', "Yard & Garden",),
    ('SIGN', "Signs & Boards",),
    ('ARCANE', "Arcane & Magical",),
)


@dataclass(frozen=True)
class PropSpec:
    """Declarative description of one buildable prop."""
    key: str
    label: str
    category: str
    description: str
    # (module_name_inside_accessories, builder_function_name)
    builder: Tuple[str, str]
    # Default kwargs for build_prop when the caller passes none.
    defaults: Dict[str, Any] = field(default_factory=dict)
    # Approx footprint radius (m) used by the furnishing composer for clearance.
    clearance: float = 0.6


def _spec(key, label, category, desc, module, func, clearance=0.6, **defaults):
    return PropSpec(key=key, label=label, category=category, description=desc,
                    builder=(module, func), defaults=defaults, clearance=clearance)


# NOTE: signatures are all build_*(bm, x, y, z_ground/z_top/z_ceiling, ang, ...).
# The registry records which vertical anchor each builder uses.
PROP_REGISTRY: Dict[str, PropSpec] = {}
for _s in (
    # --- Extracted existing yard / tavern props (were preset-locked) ---
    _spec('BARREL', "Barrel", 'YARD', "Staved ale barrel (upright or lying)",
          'furniture', 'build_barrel', 0.45, radius=0.34, height=0.74),
    _spec('CRATE', "Crate", 'YARD', "Braced shipping crate",
          'furniture', 'build_crate', 0.45, size=0.58),
    _spec('SACK', "Grain Sack", 'YARD', "Tied burlap grain sack",
          'furniture', 'build_sack', 0.35, scale=1.0),
    _spec('CLAY_POT', "Clay Pot", 'YARD', "Earthenware storage jar with lid",
          'furniture', 'build_clay_pot', 0.30, radius=0.22, height=0.48),
    _spec('STOOL', "Stool", 'SEATING', "Three-legged taproom stool",
          'furniture', 'build_stool', 0.35, radius=0.22, height=0.48),
    _spec('BENCH', "Bench", 'SEATING', "Heavy timber bench, optional backrest",
          'furniture', 'build_bench', 1.05, length=1.75),
    _spec('PICNIC_TABLE', "Picnic Table", 'TABLES', "A-frame tavern table + benches",
          'furniture', 'build_picnic_table', 1.35, length=2.05),
    _spec('POST_LANTERN', "Post Lantern", 'LIGHT', "Standing yard lantern post",
          'lighting', 'build_post_lantern', 0.40, height=2.55),
    _spec('HANGING_LANTERN', "Wall Lantern", 'LIGHT', "Bracket lantern (wall-mounted)",
          'lighting', 'build_hanging_lantern', 0.35),
    _spec('CHAIN_LANTERN', "Chain Lantern", 'LIGHT', "Ceiling-hung chain lantern",
          'lighting', 'build_chain_lantern', 0.30),
    _spec('WELL', "Well", 'YARD', "Stone well with windlass and bucket",
          'garden', 'build_well', 1.15, radius=0.66, wall_h=0.62),
    _spec('FLOWER_BOX', "Flower Box", 'YARD', "Soil-filled window planter",
          'garden', 'build_flower_box', 0.55, length=0.95),
    _spec('HANGING_SIGN', "Hanging Sign", 'SIGN', "Bracket trade sign with emblem",
          'signage', 'build_hanging_sign', 0.70),
    _spec('NOTICE_BOARD', "Notice Board", 'SIGN', "Roofed notice board with papers",
          'signage', 'build_notice_board', 0.75, width=1.10, post_h=1.70),
    _spec('AWNING', "Cloth Awning", 'SIGN', "Wall-mounted cloth awning + valance",
          'signage', 'build_awning', 0.90, width=1.45, depth=1.10),
    # --- New indoor catalogue ---
    _spec('BED', "Bed", 'SLEEP', "Timber bed with straw mattress + blanket",
          'interior_furniture', 'build_bed', 1.25, length=2.0, width=1.2),
    _spec('BUNK_BED', "Bunk Bed", 'SLEEP', "Military bunk bed: two dressed berths, safety rail + ladder",
          'interior_furniture', 'build_bunk_bed', 1.45, length=2.0, width=1.1),
    _spec('WEAPON_RACK', "Weapon Rack", 'WORK', "Standing rack of spears, axes and shields",
          'military_props', 'build_weapon_rack', 0.85),
    _spec('TRAINING_DUMMY', "Training Dummy", 'WORK', "Straw sword-practice dummy on a post",
          'military_props', 'build_training_dummy', 0.55),
    _spec('ARCHERY_TARGET', "Archery Target", 'WORK', "Straw target butt on tripod with embedded arrows",
          'military_props', 'build_archery_target', 0.85),
    _spec('CHAIR', "Chair", 'SEATING', "High-back tavern chair",
          'interior_furniture', 'build_chair', 0.35),
    _spec('INDOOR_TABLE', "Dining Table", 'TABLES', "Rectangular indoor table",
          'interior_furniture', 'build_indoor_table', 1.05, length=1.6, width=0.9),
    _spec('ROUND_TABLE', "Round Table", 'TABLES', "Round pedestal table",
          'interior_furniture', 'build_round_table', 0.70, radius=0.55),
    _spec('SHELF', "Shelf", 'STORAGE', "Open goods shelf with jars + cloth",
          'interior_furniture', 'build_shelf', 0.85, width=1.4, height=1.7),
    _spec('WARDROBE', "Wardrobe", 'STORAGE', "Double-door cupboard",
          'interior_furniture', 'build_wardrobe', 0.80, width=1.2, height=1.9),
    _spec('CHEST', "Chest", 'STORAGE', "Low iron-strapped storage chest",
          'interior_furniture', 'build_chest', 0.60, width=0.9),
    _spec('DESK', "Desk", 'WORK', "Writing desk with drawers",
          'interior_furniture', 'build_desk', 0.85, width=1.4),
    _spec('COUNTER', "Bar Counter", 'WORK', "Tavern serving counter",
          'interior_furniture', 'build_counter', 1.45, length=2.4),
    _spec('HEARTH', "Hearth", 'KITCHEN', "Stone fireplace with mantel",
          'interior_furniture', 'build_hearth', 1.10, width=1.6, height=1.5),
    _spec('BOOKSHELF', "Bookshelf", 'STORAGE', "Tall shelf with book rows",
          'interior_furniture', 'build_bookshelf', 0.75, width=1.2, height=1.8),
    _spec('BOOKSHELF_NEAT', "Bookshelf (Ordered)", 'STORAGE', "Ordered bookcase, even runs",
          'interior_furniture', 'build_bookshelf_neat', 0.75, width=1.2, height=1.8),
    _spec('BOOK_SINGLE', "Book (Single)", 'STORAGE', "One book, spine out",
          'interior_furniture', 'build_book_single', 0.20),
    _spec('BOOK_PILE_SMALL', "Book Pile (Small)", 'STORAGE', "Small pile of flat books",
          'interior_furniture', 'build_book_pile_small', 0.30),
    _spec('BOOK_PILE_LARGE', "Book Pile (Large)", 'STORAGE', "Large pile of flat books",
          'interior_furniture', 'build_book_pile_large', 0.40),
    _spec('CAULDRON', "Stove Pot", 'KITCHEN', "Lidded stove pot with top handle",
          'interior_furniture', 'build_cauldron', 0.35),
    _spec('KITCHEN_STOVE', "Kitchen Stove", 'KITCHEN', "Cast-iron cookstove with burners and oven",
          'interior_furniture', 'build_kitchen_stove', 0.85, width=0.95, depth=0.75, height=1.05),
    _spec('CHANDELIER', "Chandelier", 'LIGHT', "Hanging candle-ring chandelier",
          'interior_furniture', 'build_chandelier', 0.60, radius=0.45),
    _spec('RUG_CRIMSON', "Rug (Crimson Ornate)", 'SLEEP', "Ornate woven carpet with medallion and tassels",
          'interior_furniture', 'build_rug', 1.80, width=2.4, length=3.6, rug_style=1),
    _spec('RUG_SAPPHIRE', "Rug (Sapphire Royal)", 'SLEEP', "Royal blue damask carpet with tassels",
          'interior_furniture', 'build_rug', 1.80, width=2.4, length=3.6, rug_style=2),
    _spec('RUG_FOREST', "Rug (Forest Woven)", 'SLEEP', "Sage and terracotta woven geometric carpet with tassels",
          'interior_furniture', 'build_rug', 1.80, width=2.4, length=3.6, rug_style=3),
    _spec('SCATTER_TABLEWARE', "Table Clutter", 'TABLES', "Pewter tankards, ceramic plates, bottles, and candles",
          'interior_furniture', 'build_table_scatter', 0.40),
    _spec('PEWTER_TANKARD', "Pewter Mug", 'TABLES', "Hollow pewter tavern tankard with ear handle",
          'interior_furniture', 'build_pewter_tankard', 0.20),
    _spec('SOFA', "Sofa (Damask)", 'SEATING', "Luxurious 2-3 seater upholstered sofa with brocade damask cushions",
          'interior_furniture', 'build_sofa', 1.10, length=1.80, depth=0.82),
    _spec('ARMCHAIR', "Armchair", 'SEATING', "Plush fireside armchair with damask cushions and rolled arms",
          'interior_furniture', 'build_armchair', 0.65, width=0.86, depth=0.80),
    _spec('BOTTLE', "Glass Bottle", 'TABLES', "Slender glass wine/ale bottle with cork stopper",
          'interior_furniture', 'build_bottle', 0.15),
    _spec('BOTTLE_CLUSTER', "Bottle Cluster", 'TABLES', "Trio of wine, spirits, and potion bottles with corks",
          'interior_furniture', 'build_bottle_cluster', 0.25),
    _spec('PUMPKIN', "Pumpkin", 'KITCHEN', "Segmented orange pumpkin with green stem",
          'interior_furniture', 'build_pumpkin', 0.35, radius=0.20),
    _spec('FOODPREP_CLUTTER', "Foodprep Clutter", 'KITCHEN', "Butcher cutting board, cleaver, bread, cheese, prep bowl",
          'interior_furniture', 'build_foodprep_clutter', 0.40),
    _spec('POTTED_PLANT_SMALL', "Potted Plant (Small)", 'TABLES', "Tabletop terracotta pot with lush green leaves",
          'interior_furniture', 'build_potted_plant_small', 0.25),
    _spec('POTTED_PLANT_LARGE', "Potted Plant (Floor)", 'YARD', "Large ornamental urn with tall indoor ficus/shrub",
          'interior_furniture', 'build_potted_plant_large', 0.65),
    _spec('POTTED_HERB', "Potted Herb Bowl", 'KITCHEN', "Earthenware kitchen bowl with culinary herbs",
          'interior_furniture', 'build_potted_herb', 0.25),
    _spec('FOLDED_CLOTH', "Folded Cloth Stack", 'STORAGE', "Neat stack of folded linens and kitchen towels",
          'interior_furniture', 'build_folded_cloth', 0.30),
    _spec('LOG_PILE', "Log Pile", 'STORAGE', "Stacked round timber logs",
          'interior_furniture', 'build_log_pile', 1.20, length=2.10, radius=0.17, rows=3),
    _spec('PLANK_PILE', "Plank Pile", 'STORAGE', "Stacked sawn planks",
          'interior_furniture', 'build_plank_pile', 1.15, length=2.0, width=0.28, layers=6),
    _spec('STONE_PILE', "Stone Block Stack", 'STORAGE', "Stacked cut-stone blocks",
          'interior_furniture', 'build_stone_pile', 1.10, length=1.8, width=0.95, layers=4),
    _spec('SPELLBOOK_PEDESTAL', "Spellbook Pedestal", 'ARCANE', "Ornate wizard lectern with open grimoire, glowing crystal, and candles",
          'interior_furniture', 'build_spellbook_pedestal', 0.55),
    _spec('ARCANE_ORRERY', "Arcane Orrery", 'ARCANE', "Celestial armillary sphere with gimbaled rings and glowing mana orb",
          'interior_furniture', 'build_arcane_orrery', 0.65),
    _spec('ALCHEMY_STATION', "Alchemy Station", 'ARCANE', "Wizard's distillation workstation with alembic, flasks, and mortar",
          'interior_furniture', 'build_alchemy_station', 1.20, length=2.1, width=0.9),
    _spec('SCRYING_POOL', "Scrying Pool", 'ARCANE', "Carved cut-stone divination basin with glowing magical water",
          'interior_furniture', 'build_scrying_pool', 1.05, radius=0.90),
    _spec('ENCHANTING_TABLE', "Enchanting Table", 'ARCANE', "Arcane altar with levitating crystal focus, runic ring, and tome",
          'interior_furniture', 'build_enchanting_table', 0.95, radius=0.75),
    _spec('MAGIC_CAULDRON', "Ritual Cauldron", 'ARCANE', "Large bubbling iron cauldron with glowing potion, tripod legs, and embers",
          'interior_furniture', 'build_magic_cauldron', 0.70, radius=0.48),
    _spec('MORTAR_AND_PESTLE', "Mortar & Pestle", 'ARCANE', "Cut-stone apothecary mortar with true hollow bowl, herbal mash, and resting pestle",
          'interior_furniture', 'build_mortar_and_pestle', 0.30),
    _spec('GRAND_BOOKCASE', "Grand Arcane Bookcase", 'STORAGE', "Extra-tall 3.2m library bookcase with grimoires, scrolls, and ladder",
          'interior_furniture', 'build_grand_bookcase', 1.30, width=2.4, height=3.2),
    _spec('ARCANE_CIRCLE', "Arcane Summoning Circle", 'ARCANE', "Floor runic sigil with concentric metallic rings, glowing core, and candles",
          'interior_furniture', 'build_arcane_circle', 2.30, radius=2.2),
):
    PROP_REGISTRY[_s.key] = _s


def _resolve(spec: PropSpec) -> Callable:
    import importlib
    mod_name, func_name = spec.builder
    mod = importlib.import_module(f".{mod_name}", package=__package__)
    return getattr(mod, func_name)


def list_props(category: str = 'ALL') -> List[PropSpec]:
    """All specs, optionally filtered by category key."""
    vals = sorted(PROP_REGISTRY.values(), key=lambda s: s.label)
    if category in (None, 'ALL', ''):
        return vals
    return [s for s in vals if s.category == category]


def get_spec(key: str) -> PropSpec:
    return PROP_REGISTRY[key]


def prop_enum_items(category: str = 'ALL'):
    """Blender EnumProperty items callback payload (static list)."""
    return [(s.key, s.label, s.description) for s in list_props(category)]


CEILING_MOUNTED = {'CHAIN_LANTERN', 'CHANDELIER'}


def build_prop(bm, key: str, x: float = 0.0, y: float = 0.0,
               z: float = 0.0, ang: float = 0.0, **params):
    """Build any registered prop into ``bm`` (polymorphic entry point).

    ``z`` is the ground level for floor props, the mount height for wall
    pieces (sign/lantern/awning) or the ceiling anchor for ``CEILING_MOUNTED``
    keys. ``ang`` is the yaw in every case: it is translated to each
    builder's own angle parameter name. Caller params override spec defaults.
    """
    spec = get_spec(key)
    fn = _resolve(spec)
    kwargs = dict(spec.defaults)
    kwargs.update(params or {})
    if key == 'CHAIN_LANTERN':
        kwargs.pop('ang', None)
        return fn(bm, x, y, z_ceiling=z, **kwargs)
    if key == 'CHANDELIER':
        kwargs.pop('z_top', None)
        return fn(bm, x, y, z_top=z, ang=ang, **kwargs)
    if key == 'HANGING_LANTERN':
        kwargs.pop('z_top', None)
        return fn(bm, x, y, z_top=z + 2.1, arm_ang=ang, **kwargs)
    if key == 'HANGING_SIGN':
        kwargs.pop('z_top', None)
        return fn(bm, x, y, z_top=z + 2.6, run_ang=ang, **kwargs)
    if key == 'AWNING':
        kwargs.pop('z_top', None)
        return fn(bm, x, y, z_top=z + 2.4, ang=ang, **kwargs)
    if key == 'FLOWER_BOX':
        kwargs.pop('z_base', None)
        return fn(bm, x, y, z_base=z + 0.8, ang=ang, **kwargs)
    return fn(bm, x, y, z_ground=z, ang=ang, **kwargs)
