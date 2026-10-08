# Presets & Compound Estate Systems

This document covers the **78 built-in building presets** in `presets.py` and the **Compound & Estate System** implemented in `generator/accessories/estate.py`.

---

## 1. The 78 Presets System

BlendBuildingCreator provides 26 building families across 3 architectural and material tiers ($26 \times 3 = 78$ presets total).

### Preset Taxonomy

| Category | Families | Description & Default Dimensions |
| :--- | :--- | :--- |
| **Civic** | Town Hall, Noble Manor, Nasher's Manor | Grand civic landmarks, T-shaped assemblies, multi-wing palatial compounds ($40\text{m} \times 40\text{m}$ up to $200\text{m} \times 200\text{m}$). |
| **Military** | Infantry Barracks, Archery Range, Knights Manor, Healers' Chapel, Mage Tower | Fortified quarters, U-shaped barracks, butt fields, round wizard towers with spiral stairs. |
| **Industrial** | Warehouse, Lumbermill | Cargo hoists, open saw pits, timber sheds, loading docks ($20\text{m} \times 20\text{m}$). |
| **Residential** | House 1 Small, House 2 Small, House 1 Medium, House 2 Medium, House 3 Medium | Cottages, fairytale crooked roofs, narrow urban row houses, and L-shaped courtyard residences. |
| **Hospitality** | Tavern, Tavern Long, Inn | Public taprooms, guest boarding rooms, covered verandas, trade signs ($12\text{m} \times 20\text{m}$ to $40\text{m} \times 40\text{m}$). |
| **Artisan** | Bakery, Tailor, Toolsmith, Jeweler, Brewery, Fisher, Furniture Maker, Butcher | Trade workshops with dedicated tools, shop counters, and street-facing displays. |
| **Estate** | Stable & Carriage Barn | Stalls, carriage bays, haylofts, and paddock gates ($16\text{m} \times 12\text{m}$). |

---

## 2. Material Tiers Across Presets

Every family has a `_T1`, `_T2`, and `_T3` preset variant:

```
[Building Family: e.g. TOWN_HALL]
 ├── TOWN_HALL_T1 (Tier 1: Rustic Log & Mud Stone, 1-2 floors, simple gables)
 ├── TOWN_HALL_T2 (Tier 2: Planks & Squared Fieldstone, 2-3 floors, dormers, half-timber)
 └── TOWN_HALL_T3 (Tier 3: Cut Ashlar Stone, Slate Roof, 3-4 floors, clock tower, oriels)
```

Applying a preset executes `apply_preset(props, preset_key)`, updating all scene properties atomically before triggering building generation.

---

## 3. Estate & Compound Composer (`estate.py`)

For large properties (such as Noble Manors and Citadels), `accessories/estate.py` orchestrates surrounding ancillary outbuildings and activity yards.

### Outbuilding Architecture & Recursive Merging
To keep outbuildings identical in construction quality to the main structure, `_merge_generated_building` generates each outbuilding in a temporary isolated Blender scene:
1. Creates a temporary scene and an empty mesh object.
2. Applies the target preset (e.g. `STABLE_T3`, `BARRACKS_T3`, `BLACKSMITH_T3`).
3. Disables recursive flags using `_OUTHOUSE_DISABLED`.
4. Runs `generate_building` in the temporary context.
5. Remaps pruned material slot indices back to the canonical index table using `canonical_slot_index`.
6. Transforms the outbuilding geometry (translation + organic rotation) and joins it into the host building mesh.

### Recursion Prevention (`_OUTHOUSE_DISABLED`)
To prevent outbuildings from recursively spawning their own sub-estates or nested citadels, `_OUTHOUSE_DISABLED` explicitly strips compound properties during outbuilding generation:

```python
_OUTHOUSE_DISABLED = (
    'estate_compound',
    'has_estate_wall',
    'has_estate_stables',
    'has_estate_servants',
    'has_estate_carriage',
    'has_estate_gazebo',
    'has_estate_fountain',
    'has_estate_hedges',
    'has_estate_gatehouse',
    'has_estate_pavilion',
    'has_estate_training',
    'has_castle_citadel',   # Crucial: prevents outbuildings from nesting citadels
)
```

---

## 4. Organic Bailey & Cour d'Honneur Layout

Rather than arranging structures along rigid orthogonal grids, the estate generator uses **organic perimeter placement**:

```
                  [North Curtain Wall & Bastions]
             Stables (-38, 28)       Chapel (38, 28)
                    \                 /
                     \               /
   Blacksmith (-42, 0)   COUR D'HONNEUR   Barracks (42, 0)
                      [Grand Fountain]
                      [Training Yard]
                     /               \
                    /                 \
            Guardhouse (-35, -28)   Steward Lodge (35, -28)
                 [Gatehouse & Drawbridge (0, -45)]
```

- **Open Cour d'Honneur**: Central assembly plaza centered around a multi-tier stone water fountain.
- **Organic Angles**: Outbuildings are angled slightly inward ($12^\circ - 24^\circ$) along the perimeter curtain walls, creating the natural, defensible feel of a medieval bailey.

---

## 5. Military Training Grounds (`build_military_training_grounds`)

An authentic $32\text{m} \times 22\text{m}$ martial training yard arranged along the inner ward:
- **Sparring Ring**: Octagonal post-and-rope ring with raked dirt floor.
- **Archery Butts**: Heavy timber A-frame target stands backed by straw bales, positioned along the long axis for safe shooting practice.
- **Swivel Quintains**: Rotating counter-weighted target arms with padded shield targets and counterweight sandbags.
- **Training Pells**: Vertical heavy oak posts wrapped with rope bands for sword striking practice.
- **Weapon & Armor Racks**: Racks containing wooden practice wasters, bucklers, and halberds.
