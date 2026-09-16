# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.8.1-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

**BlendBuildingCreator** is a procedural 3D building generator add-on for **Blender 5.2 LTS** (compatible with 4.2+). Designed for concept artists, level designers, and game developers creating stylized modern fantasy, medieval, and rustic architecture in seconds.

Unlike simple facade generators, **BlendBuildingCreator generates full, walkable interiors**—including switchback or spiral staircases with railings, structural floor and ceiling joists, framed walk-in doorways with opening doors, and timber-decked attics with king-post trusses.

---

## ✨ What's New in v1.8.1

- 🏘️ **Outcrops Anywhere on the Building**: `Outcrop Side` gained a **Random (Any Facade)** option, so the mini-wing outcrops scatter around the whole building instead of lining up on one wall — each outcrop picks its own facade and position. Works with the new **Outcrop Count** range (1–6), the **Scatter Outcrops** toggle and **Outcrops On Every Floor** (ground or upper + every storey above, each floor spread independently so they never stack into a column).
- 🚪 **Doors Start Closed**: `Door Open Angle` now defaults to **0°** (as do all shipped presets), and **balcony doors follow the same slider** instead of always hanging ajar.
- 🪟 **Calmer Window Density**: default `Window Density` eased from 0.8 to **0.6**.
- 🧱 **Annex Rebuilt in the Main Hall's Style**: the bay portal gets proper timber jambs + lintel, the annex walls now carry the same per-storey timber framing as the hall (plates, mid rails, diagonals, corner posts), and the old solid belt-course slab that read as a phantom mid-height ceiling is gone — it's now a ring of boards with the storey above serving as the ceiling.
- 🏰 **Cleaner Towers**: removed the stray timber collar ring that crossed the corner turrets mid-height.
- 🔲 **Portal Frames Flush**: mini-wing and annex portal liners are centred on the wall and just a hair deeper, so they line the full reveal instead of stopping halfway and poking out of the outer face.

---

## ✨ What's New in v1.8.0

- 🪜 **New Railing Generator — every guard rebuilt**: a single shared builder (`generator/railing.py`) now drives the rampart walk and its ramp, the entrance ramp, balconies, stairwell guardrails, straight flights and the spiral stair. Each run gets a grounded sill, handrail + wide cap board, mid/lower string rails, chunky capped newel posts with iron pins, balusters with turned collars and diagonal braces — and a **Wonkiness**-style jank so posts and boards sit subtly askew instead of machine-straight. Level **and sloped** runs are supported.
- 🛡️ **Wooden Rampart Walk**: the town-hall rampart is now timber — plank deck on wooden posts (with stone footings) and the detailed railing above, with a matching railing down both sides of the descent ramp.
- 🛠️ **Real Window Cut-outs on Towers**: `build_wall_with_opening` now cuts around **stacked** openings column-by-column, so the turret and clock-tower shafts get genuine holes on every storey instead of windows sunk into solid wall.
- 🏰 **Taller, Cleaner Corner Turrets**: ~30% taller, mounted on the **back wall** (clear of the interior stair), extra windows high up the shaft, no stray cut-stone floor bands, floor decks trimmed inside the shell, and the spire seated flush (no floating roof).
- 🧱 **Thicker Corner Pillars**: main and wing corner posts, mini-wing corner posts and annex corner boards are all beefed up so the stone foundation never pokes through them.
- 🪜 **Neater Interior Joinery**: the Tier 1 log-wall interior core uses the wall UV convention (grain runs along the wall, not across it) and the top stair landing plate no longer z-fights the floor slab.

---

## 🏰 Key Features

### Architectural Footprints & Geometry
- **Parametric Dimensions**: Width, depth, floor count (1 to 5), floor height, and foundation height.
- **Compound Building Shapes**:
  - **Rectangular**: Classic fantasy cottages, townhouses, and barns.
  - **L-Shaped**: Primary hall with intersecting perpendicular wing (left or right side).
  - **T-Shaped**: Symmetrical central projecting cross-wing.
  - **Round Tower**: 8-sided faceted cylindrical tower with spiral stairs and conical turret spire roof.
- **Cantilever Overhangs (Jettying)**: Upper floor projection with solid timber soffit plates and structural corbel brackets (`SECOND_FLOOR_ONLY` or `ALL_FLOORS`).
- **Tudor Half-Timber Framing**: Procedural wooden wall posts, girts, and diagonal cross-braces cut around openings.
- **Whimsical "Wonkiness"**: Stylized organic tilts, sways, and crooked fantasy deformations with a single slider.

### Openings & Entrances
- **Interactive Doors**: Single or double doors with stylized iron strap hinges, handles, and interactive open/close slider.
- **Grounded Stone Steps**: Entrance stair steps with solid risers and plinths extending down to ground level ($Z=0$).
- **Framed Windows**: Recessed wooden casing frames, lintels, exterior shutters, flower planter boxes, and glass panes with adaptive bay spacing and corner clearances.

### Fantasy Roofs & Chimneys
- **Roof Types**: Stylized Fairytale Sway Roof (with parabolic ridge dips and flared eaves), Classic Medieval Gable, or Conical Turret Spire.
- **Inner Wood Ceiling Decking**: Continuous solid 0.12m timber sheathing beneath shingles, eliminating light leaks.
- **Attic Trusses**: Exposed interior king-post truss assemblies with tie beams and king posts.
- **Crooked Chimneys**: Cobblestone chimney stacks with beveled stone caps, flue liners, and terracotta smoke pots.

### Civic Landmarks (Town Halls)
- **Attached Clock Tower**: Hollow shaft with real cut-out windows, stacked proud clock faces, an open belfry with bell and a square shingled spire.
- **Square Corner Turrets**: Tall towers mounted on the **back wall** (clear of the interior stair), tied into the hall with a doorway per storey, cut-out windows all the way up the shaft and a square shingled cap.
- **Elevated Rampart Walk**: Plank deck on wooden posts (stone footings) with a detailed timber guard railing and a descending entrance ramp that starts behind the clock tower's gate.
- **Side Annex & Oriels**: A half-timbered side volume with a cross-gable roof, walk-in portal and a matching mini-wing oriel.

### Full Walkable Interiors
- **Multi-Story Staircases**:
  - **Straight Switchback Stairs**: Alternating flight directions with floor landings for multi-storey buildings.
  - **Spiral Staircases**: Circular $360^\circ$ rotation per floor around a central timber mast.
- **Structural Ceiling Beams**: Wooden joists with automatic trimmer header clearance around stairwells.
- **Spacious Walkthrough Portals**: Full-depth timber archways encasing the wall core between compound wings.

### Railings & Guards
- **One Detail-Complete Builder**: rampart walks, ramps, balconies, stairwell openings, straight flights and the spiral stair all use the same shared railing generator.
- **Hand-Built Look**: grounded sill, handrail + wide cap board, mid/lower string rails, capped newel posts with iron pins, balusters with turned collars and diagonal braces — with a subtle **jank** so nothing reads as perfectly machine-straight.
- **Level & Sloped**: the same call dresses a flat walk and a descending ramp (posts and balusters stay plumb, rails follow the grade).

---

## 🚀 Installation

### Option 1: Install Extension (.zip) in Blender 5.2
1. Download `blend_building_creator.zip` from this repository.
2. In Blender, navigate to **Edit** > **Preferences** > **Get Extensions**.
3. Click the dropdown menu in the upper right and select **Install from Disk...**, then choose `blend_building_creator.zip`.
4. The add-on is now installed and active!

### Option 2: Manual Folder Install
Copy the `blend_building_creator` directory into your Blender 5.2 user extensions folder:
```
%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\blend_building_creator\
```

---

## 🛠️ How to Use

1. In the 3D Viewport, press `N` to open the sidebar.
2. Select the **Fantasy Building** tab.
3. Click **Create Fantasy Building** to spawn a procedural building.
4. Filter presets by category (**Civic**, **Military**, **Artisan**, **Industrial**, **Commercial**) and click any preset button for instant generation.
5. Switch **Material Tier** (**Tier 1: Logs**, **Tier 2: Planks**, **Tier 3: Stone/Stucco**) via the top toggle bar.
6. Fine-tune parameters across the collapsible sub-panels:
   - **Floors & Dimensions**: Width, Depth, Floors, Shapes (Rectangle, L-Shape, T-Shape, Round Tower), Wing Dimensions & Floors, Cantilever Overhangs, Foundation.
   - **Walk-in Interior & Stairs**: Stair types (Straight, Spiral), handrails, ceiling beams.
   - **Openings**: Window spacing, door angle, shutters, flower boxes.
   - **Roof & Chimney**: Roof style (Sway, Gable, Turret), sway curvature, dormers, chimney stack.
   - **Materials**: Toggle procedural node shaders and customize surface colors.
7. Click **Finalize Mesh** to collapse modifiers and bake into a standard editable Blender mesh.

---

## 📄 License
Licensed under [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html), matching
the Blender extension manifest.
