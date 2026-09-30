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
          'interior_furniture', 'build_rug', 1.40, width=1.8, length=2.8, rug_style=1),
    _spec('RUG_SAPPHIRE', "Rug (Sapphire Royal)", 'SLEEP', "Royal blue damask carpet with tassels",
          'interior_furniture', 'build_rug', 1.40, width=1.8, length=2.8, rug_style=2),
    _spec('RUG_FOREST', "Rug (Forest Woven)", 'SLEEP', "Sage and terracotta woven geometric carpet with tassels",
          'interior_furniture', 'build_rug', 1.40, width=1.8, length=2.8, rug_style=3),
    _spec('SCATTER_TABLEWARE', "Table Clutter", 'TABLES', "Pewter tankards, ceramic plates, bottles, and candles",
          'interior_furniture', 'build_table_scatter', 0.40),
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
