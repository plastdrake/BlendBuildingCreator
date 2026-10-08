# Fortifications & Fantasy Castle Generation System

This document describes the defensive structures and the procedural **Fantasy Castle Generator** implemented in `generator/accessories/castle.py` and supporting fortification builders (`curtain_wall.py`, `bastion.py`, `gatehouse.py`, `palisade.py`).

---

## 1. Defensive Systems Overview

BlendBuildingCreator provides two layers of defensive systems:
1. **Compound Fortifications**: Configurable boundary defenses applicable to any building preset (palisades, curtain walls, gatehouses, and drawbridges).
2. **Dedicated Castle Citadel Engine**: A high-level procedural orchestrator that generates full fantasy city-fortresses across three evolutionary tiers with continuous architectural lineage.

---

## 2. Core Fortification Builders

### Palisade Stockades (`accessories/palisade.py`)
- **Peeled Log Stakes**: Vertical round timber logs sharpened to defensive points.
- **Support Rails**: Horizontal lashed split-log stringers with iron spikes.
- **Sentry Walkway**: Elevated plank catwalk behind the palisade breastwork.
- **Front Barred Gate**: Heavy wooden double gate with crossbars.

### Stone Curtain Walls (`accessories/curtain_wall.py`)
- **Ashlar Battered Plinth**: Sloped masonry base providing structural stability.
- **Rampart Walk**: Continuous paved stone wall-walk ($1.8\text{m} - 2.4\text{m}$ wide).
- **Inner Arch Vaulting**: Segmental barrel arches and supporting stone pier buttresses under the ramparts.
- **Crenellated Merlons**: Protective battlements with stone coping caps and embrasures.
- **Access Breaches**: Wall-walks leave clear openings at stair landings so sentries never get obstructed.

### Flanking Bastions & Arrow Loops (`accessories/bastion.py`)
- **D-Shaped & Cylindrical Towers**: Projecting forward from the wall line to provide flanking fire along the curtain face.
- **Real Pierced Arrow Slits**: Genuine through-wall apertures (not surface textures) with splayed interior reveals and crosslet transoms.

### Gatehouse, Causeway & Suspension Chains (`accessories/gatehouse.py`)
- **Portcullis**: Vertically hoisted iron grate with downward-pointing spiked feet.
- **Stone Causeway & Ditch**: Grounded threshold platform, inner courtyard ramp, and outer ditch abutments.
- **Parallel Suspension Chains**: Interlocking 3D torus link chains anchored from gatehouse winches to the outer drawbridge deck without criss-crossing.

---

## 3. Fantasy Castle Citadel System (`castle.py`)

### Core Philosophy
1. **Never Monolithic**: Castles are collections of connected, asymmetrical structures with varied rooflines and elevations.
2. **City-Fortress Scale**: Prioritizes verticality, multi-level traversal, distinct districts, and memorable landmarks.
3. **Single Architectural Lineage**: Tiers 1, 2, and 3 represent the **same castle evolving over centuries**. Early structures are preserved and built around rather than replaced.

---

## 4. The 3-Tier Progression Lineage

```
╔═══════════════════════════════════════════════════════════════════════════╗
║ TIER 1: ORIGINAL FRONTIER STRONGHOLD                                      ║
║ - Ancestral Old Keep (14m x 12m) at (0.0, 10.0) [Rough Stone & Timbers]  ║
║ - Frontier Bailey Palisade Enclosure with Stone Well                     ║
║ - Square Timber Lookout Watchtower at (-12.0, 12.0) with Bell            ║
║ - Primitive Peeled Log Gatehouse at (0.0, -8.0)                          ║
║ - Subterranean Provisions Cellar with Holding Pit & Escarpment Exit      ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼ (Lineage Evolution: Preserved & Reinforced)
╔═══════════════════════════════════════════════════════════════════════════╗
║ TIER 2: EXPANDED REGIONAL FORTRESS                                        ║
║ - Ancestral Old Keep at (0.0, 10.0) reinforced with Cut-Stone Ashlar,    ║
║   Battlement Deck, Merlons, Chimney, and Heraldic Standard Banner        ║
║ - Stone Curtain Wall Enclosure replacing palisade                         ║
║ - Twin Bastion Gatehouse with Hoisted Portcullis                         ║
║ - Northwest Stone Watchtower & Southeast Cylindrical Fortress Bastion     ║
║ - Sanctuary Chantry Chapel (Apse, Rose Window, Crypt Trapdoor)           ║
║ - Garrison Barracks & Armory (Bunk Beds, Weapon Racks, Training Yard)    ║
║ - Two Courtyards: Lower Bailey & Upper Inner Ward                        ║
║ - 2-Level Dungeon Complex with 2 Narrative Secret Escape Routes          ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼ (Lineage Evolution: Enclosed as Core of Donjon)
╔═══════════════════════════════════════════════════════════════════════════╗
║ TIER 3: GRAND FANTASY CAPITAL CITADEL                                     ║
║ - Central Mountain Crag: Donjon of the High King rising 58m enclosing     ║
║   the Ancestral Old Keep core at (0.0, 10.0)                             ║
║ - Perched on Stratified Stone Cliff Massifs (MAT_INDEX_CLIFFS, slot 42)  ║
║ - 6 Distinct Districts (Royal, Military, Arcane, Religious, Dungeon, etc)║
║ - Great Royal Ballroom of Thrones (Hammerbeam roof, 3-tier dais, thrones)║
║ - High Fortress Ramparts Wing with 100% flat stone fighting deck         ║
║ - Arcane District: High Scholar's Library & soaring 42m Wizard Spire     ║
║ - Elevated Armored Skybridge of the Stars spanning cliff chasm           ║
║ - Barbican Sun Gate with flared approach stairs & iron portcullis        ║
║ - Grand Chantry of the Silver Flame with crypt descent                   ║
║ - 4-Level Deep Subterranean Dungeon Complex                              ║
║ - 4 Narrative Secret Passages solving physical egress routes             ║
║ - Strict Tower Typology: Spire (witch-hat) vs Battlement (flat deck)     ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## 5. Strict Tower Typology & Hierarchy

The castle engine enforces architectural rules on towers:

### 1. Spire vs. Battlement Rule
- **`SPIRE` Towers** (Wizard Spire, Donjon Bartizans, Northwest Watchtower):
  - Steep conical witch-hat roof with flared eaves.
  - Iron needle finial and waving pennon.
  - **ZERO merlons** (never mix battlements with conical spires).
- **`BATTLEMENTS` Towers** (Southeast Bastion, Northeast Artillery Bastion, Fortress Ramparts):
  - $100\%$ flat walkable stone fighting deck.
  - Machicolations corbels supporting the overhang.
  - Continuous crenellated merlons and stone coping caps.
  - Enclosed companionway stair bulkhead and open-deck tripod signal fire brazier.
  - **ZERO conical roofs**.

### 2. Tower Scale Hierarchy
- **1 Landmark Tower**: The Wizard's Spire of Eldath ($42\text{m}$ tall, $R=4.4\text{m}$).
- **3 Major Towers**: Southeast Bastion, Northeast Bastion, Northwest Spire Watchtower.
- **4 Secondary Towers**: Donjon Keep corner bartizans ($6.5\text{m}$ projection).
- **Minor Turrets**: Wall bartizans, gatehouse kiosks, and bell-cotes.

---

## 6. Subterranean Dungeons & Narrative Secret Routes

### 4-Level Dungeon System (`build_subterranean_citadel_progressive`)
```
Z =  0.0m ─── Ground Level / Barbican Forecourt
               │
Z = -3.5m ─── Level -1: Vaulted Great Wine Cellar
               ├─ Stone groin arches, oak barrel racks, tasting table
               │
Z = -7.0m ─── Level -2: Castle Prison Complex
               ├─ Iron-barred holding cells, wall shackles, guard post
               │
Z = -10.5m ── Level -3: Deep Dungeon & Torture Chamber
               ├─ Iron gibbet cages, torture rack, heavy chains
               │
Z = -14.0m ── Level -4: Ancient Crypts & Forgotten Ruins
               └─ Stone sarcophagi, ruined gothic arches, bedrock tunnel
```

### The 4 Narrative Secret Routes
1. **Ballroom Grand Fireplace $\to$ Dungeon Cells**: Concealed flight behind the double-flue hearth allowing discrete arrests or royal escape.
2. **Vaulted Wine Cellar $\to$ Wizard Spire Base**: Secret spiral corridor ascending directly from cellar provisions to the arcane library.
3. **Donjon Royal Chambers $\to$ Bedrock Escarpment**: Sovereign's emergency mountain tunnel escaping the citadel.
4. **Grand Chantry Chapel $\to$ Ancient Crypts**: Iron sanctuary trapdoor leading down into the forgotten sepulcher.

---

## 7. The Programmatic Final Validation Pass

The generator includes a strict validation gate (`validate_castle_generation` in `castle.py`). If any architectural requirement fails, the generator rejects the mesh and raises an error:

```python
def validate_castle_generation(registry, tier):
    # Asserts:
    # 1. Landmark structures exist (T1: >= 3, T2: >= 6, T3: >= 8)
    # 2. Tower hierarchy holds (Landmark, Major, Secondary, Turrets)
    # 3. Multiple courtyards exist (T1: 1, T2: 2, T3: 3)
    # 4. Dungeon levels generated (T1: 1, T2: 2, T3: 4)
    # 5. Narrative secret routes exist (T1: 1, T2: 2, T3: 4)
    # 6. Districts verified for Tier 3 (>= 5 districts)
    # 7. Interior generation completed (hearths, tables, bunks, arcane props)
    # 8. Ancestral Old Keep lineage verified at (0.0, 10.0)
```
