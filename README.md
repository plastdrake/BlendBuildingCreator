# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.7.17-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

**BlendBuildingCreator** is a procedural 3D building generator add-on for **Blender 5.2 LTS** (compatible with 4.2+). Designed for concept artists, level designers, and game developers creating stylized modern fantasy, medieval, and rustic architecture in seconds.

Unlike simple facade generators, **BlendBuildingCreator generates full, walkable interiors**—including switchback or spiral staircases with railings, structural floor and ceiling joists, framed walk-in doorways with opening doors, and timber-decked attics with king-post trusses.

---

## ✨ What's New in v1.7.17

- 🕰️ **Civic Landmarks for Town Halls**:
  - **Clock Tower**: ashlar stone lower stage + tier-material upper stage, real cut-out framed windows on a hollow shaft, proud stacked clock faces, and a framed gate opening with timber jambs, lintel and embedded knee braces.
  - **Square Corner Turrets**: tall square towers that rise a full storey above the eaves, sit outside the wall planes (annex-style), connect to the hall through a framed doorway on every storey, and carry cut-out windows plus a square shingled spire.
  - **Rampart Walk**: an elevated stone wall-walk on support pillars that starts at the clock tower and runs along the side; the entrance ramp climbs from behind the tower's gate up onto the deck.
- 🪵 **Tier 1 Interior Planks**: the log-wall interior core now uses planks on every wall, so a wall that happens to receive no windows or doors no longer exposes the shared plaster material on the inside.
- 🏠 **Multi-Outcrop Mini-Wings**: place **1-3** mini-wing outcrops (`Outcrop Count`) spread fit-aware along the chosen facade, with wider outcrops (up to 8 m) split into multiple windows.
- 🪟 **Calmer Facades**: default **Window Density** lowered to `0.8`, wider facade edge margins, corner clearances around turrets, and shorter outcrop corbels so brackets, windows and shutters never collide.
- 🧱 **Consistent Civic Detailing**: the annex and clock tower suppress main-wall windows behind their roofs, and gable crowns follow the resolved roof orientation so rotated-roof gables keep their top log.

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
- **Square Corner Turrets**: Annex-style tall towers tied into the hall with a doorway per storey, cut-out windows and a square shingled cap.
- **Elevated Rampart Walk**: Pillared stone wall-walk with parapets and a descending entrance ramp that starts behind the clock tower's gate.
- **Side Annex & Oriels**: A half-timbered side volume with a cross-gable roof, walk-in portal and a matching mini-wing oriel.

### Full Walkable Interiors
- **Multi-Story Staircases**:
  - **Straight Switchback Stairs**: Alternating flight directions with floor landings for multi-storey buildings.
  - **Spiral Staircases**: Circular $360^\circ$ rotation per floor around a central timber mast.
- **Structural Ceiling Beams**: Wooden joists with automatic trimmer header clearance around stairwells.
- **Spacious Walkthrough Portals**: Full-depth timber archways encasing the wall core between compound wings.

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
