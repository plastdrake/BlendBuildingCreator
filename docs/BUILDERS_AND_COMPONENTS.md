# Modular Builders & Architectural Components

BlendBuildingCreator is built on a suite of **specialized modular builders**. Each builder handles a distinct domain of construction (walls, stairs, openings, roofs, furniture) and can be orchestrated independently or composed together.

---

## 1. Footprint & Shape Builders (`shapes.py`, `poly.py`)

Buildings are rooted in parametric polygons that determine wall layouts, interior division, and roof hips.

| Footprint Shape | Module | Description | Typical Use Cases |
| :--- | :--- | :--- | :--- |
| **`RECTANGLE`** | `shapes.py` | Uniform 4-corner box with parametric `width` and `depth`. | Cottages, standard shops, barracks. |
| **`L_SHAPE`** | `shapes.py` | Main block with a perpendicular wing creating an inner corner. | Courtyard houses, taverns, warehouses. |
| **`T_SHAPE`** | `shapes.py` | Central nave with symmetrical or asymmetrical cross-wings. | Town halls, chapels, civic manors. |
| **`U_SHAPE`** | `shapes.py` | Dual parallel wings framing an enclosed front court. | Palatial estates, grand infantry quarters. |
| **`ROUND_TOWER`** | `round_tower.py`, `mage_tower.py` | Multi-segmented cylindrical polygon ($N=8$ to $N=24$) with stepped plinths. | Watchtowers, mage towers, fortress bastions. |

---

## 2. Wall & Framing Builders (`walls.py`, `facade.py`)

### Wall Construction
Walls are constructed with real physical thickness ($0.35\text{m} - 0.85\text{m}$) rather than single-sided planes:
- **Outer Shell**: Ashlar stone, rough fieldstone, horizontal lap siding planks, or heavy peeled logs.
- **Inner Lining**: Interior plaster or wooden wall paneling.
- **Quoins & Corner Trim**: Cut-stone dressed corner blocks or heavy timber corner posts.

### Tudor Half-Timber Framing (`facade.py`)
For timber-framed buildings (Tier 2/3), `facade.py` generates authentic Tudor timber networks:
- **Principal Posts**: Vertical load-bearing timbers at wall corners and floor boundaries.
- **Girts & Bressummers**: Horizontal sill and lintel timbers running the length of the facade.
- **Diagonal Braces**: Angle struts (St. Andrew's cross, arched braces) adding medieval character.
- **Stud Infill**: Closely spaced vertical studs framing door and window apertures cleanly without clipping.

---

## 3. Openings & Framing Builders (`openings.py`)

The openings builder cuts doors and windows into walls, adding interior and exterior surrounds:

### Doorways
- **Stone Arches & Lintels**: Rounded roman arches, pointed gothic arches, or flat heavy timber lintels.
- **Thresholds & Steps**: Grounded stone steps adapting to foundation heights.
- **Door Blades**: Beveled wood plank doors with iron strap hinges, door handles, and animated/parametric open-angle properties (`door_open_angle`).

### Windows & Shutters
- **Recessed Casing**: Framed stone reveals recessed into the wall thickness.
- **Window Mullions & Tracery**: Cross-mullion stone tracery or leaded diamond panes (`MAT_INDEX_GLASS`).
- **Hinged Shutters**: Louvered or board-and-batten wooden shutters positioned open or closed.

---

## 4. Roof & Attic Builders (`generator/roof/`)

Roof systems are partitioned into modular sub-generators:

```
blend_building_creator/generator/roof/
├── gable_roof.py      # Classic double-pitch straight gable roof
├── sway_roof.py       # Fairytale curved sway roof (parabolic flare at eaves)
├── turret_roof.py     # Conical and octagonal witch-hat spires
├── dormer.py          # Gabled, shed, and eyebrow wall dormers
├── attic.py           # Attic floorboards, collar beams, and king posts
├── shingles.py        # 3D overlapping wood shake / slate shingles
├── features.py        # Chimneys, pots, weather vanes, roof hatches
└── valley.py          # Roof intersections and L/T-shape valley flashing
```

### Roof Typologies
1. **Classic Gable**: Straight angled rafters with triangular gable walls at the ends.
2. **Fairytale Sway Roof**: Curved parabolic sag along the ridge and flared kick at the eaves, giving an organic hand-built fantasy look.
3. **Conical Spire**: Steep witch-hat roof tapering to an iron needle finial.
4. **Flat Fighting Deck**: $100\%$ flat stone deck with perimeter corbels, machicolations, and crenellated merlons (strictly used on fortress bastions).

---

## 5. Walk-in Interiors & Stairs (`interior.py`)

BlendBuildingCreator generates authentic interiors on all levels:

```
[Floor Slab] ───────── Cutout for Stairway
     │
     ├─ [Ceiling Joists] ── Structural transverse beams
     │
     └─ [Staircase]
          ├─ Straight Flight with Mid-Level Landing & Railings
          │   OR
          └─ Annular Spiral Stairs with Central Newel Post
```

### Staircase Types
- **Straight Switchback Stairs**: Step risers, treads, stringer beams, mid-flight landing slabs, baluster spindles, and smooth handrails.
- **Spiral Stairs (`build_spiral_staircase`)**: Annular stone or timber wedge steps spiraling $360^\circ$ up a central cylinder, interfacing cleanly with ring floor slabs (`ring_slab`).

---

## 6. Architectural Accessories

Modular accessories break up building silhouettes and add functional asymmetry:

| Component | File | Features |
| :--- | :--- | :--- |
| **Annex Wing** | `accessories/annex.py` | Secondary lean-to or gable side wing extending the primary building. |
| **Mini-Wing Outcrop** | `accessories/mini_wing.py` | Cantilevered upper-floor oriel bays supported on diagonal timber struts. |
| **Balconies** | `accessories/balcony.py` | Cantilevered exterior wooden or stone viewing platforms with railings. |
| **Veranda / Porch** | `accessories/porch.py` | Ground-floor covered timber porch with chamfered pillars and railing. |
| **Cargo Crane** | `accessories/crane.py` | Heavy timber hoist arm with pulley wheel, hanging rope, and iron hook. |
| **Building Scaffold** | `accessories/scaffold.py` | Construction staging poles, lashed timber ledgers, ladders, and plank walkways. |

---

## 7. Furnishings & Dressing Systems

The generator dresses interiors and exteriors with modular thematic props:

### Interior Furniture (`interior_furniture.py`, `furniture.py`)
- **Living Quarters**: Four-poster beds, bunk beds, footlockers, round & banquet tables, high-backed chairs, and benches.
- **Storage**: Oak barrels, supply crates, grain sacks, and wood log piles.
- **Hearths**: Stone fireplaces with mantels, fire grates, and flues.
- **Royal Suite**: 3-tier cut-stone dais, velvet runner, lion-paw throne, fabric canopy, and braziers.
- **Arcane Academy**: Arcane floor circles, alchemy tables, orreries, spellbook pedestals, grand bookshelves, and scrying pools.

### Military Dressing (`military_props.py`)
- **Weapon Racks**: Slotted timber racks with halberds, broadswords, and spears.
- **Training Equipment**: Swivel quintains, straw-filled practice dummies, and archery target butts with painted concentric scoring rings.
- **Armory**: Blacksmith forges with bellows, anvils, quench buckets, and tool tables.

### Hospitality Dressing (`accessories/hospitality.py`, `lighting.py`, `signage.py`)
- Post-mounted iron lanterns, hanging oil lanterns, trade signs with custom silhouettes, water wells with bucket pulleys, and picnic benches.
