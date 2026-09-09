# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**BlendBuildingCreator** is a powerful, procedural 3D building generator add-on for **Blender 5.2 LTS**. Designed specifically for concept artists, environment designers, and game developers looking to create rich, stylized fantasy and medieval architecture in seconds.

Unlike basic facade generators, **BlendBuildingCreator builds full, walkable interiors**—including multi-story switchback or spiral staircases, ceiling beams, framed doorways with opening doors, and timber-decked attics.

---

## ✨ Key Features

### 🏰 Architectural Footprints & Geometry
- **Parametric Dimensions**: Freely customize base width, depth, number of floors (1 to 5), floor heights, and foundation height.
- **Compound Building Shapes**:
  - **Rectangular**: Classic fantasy dwellings, cottages, and townhouses.
  - **L-Shaped**: Primary hall with an intersecting perpendicular wing (left or right side).
  - **T-Shaped**: Symmetrical central projecting cross-wing.
  - **Round Tower**: 8-sided faceted cylindrical fantasy tower with centered spiral staircase and conical turret spire roof.
- **Independent Wing Floor Count**: Set custom storey heights for projecting wings (e.g. a 1-story tavern/forge annex on a multi-story building).
- **Cantilever Overhangs**: Generate historical jettying / cantilever upper floors with solid timber soffit plates and structural corbel brackets.
  - **Overhang Scope**: Toggle between `SECOND_FLOOR_ONLY` (classic medieval style) or `ALL_FLOORS` (gradual outward stepping).
- **Tudor Half-Timber Framing**: Procedural wooden wall posts, girts, and diagonal cross-braces intelligently cut around doors and windows.
- **Whimsical "Wonkiness"**: Add stylized organic tilts, sways, and crooked fantasy deformations with a single slider.

### 🚪 Openings & Entrances
- **Interactive Doors**: Single or double doors with stylized iron strap hinges, door handles, and an interactive **Open Door** slider.
- **Grounded Stone Steps**: Entrance stair steps with solid risers and plinths extending down to ground level ($Z=0$).
- **Framed Windows**: Recessed wooden casing frames, lintels, exterior shutters, flower planter boxes, and glass panes with adaptive bay spacing and corner clearances.

### 🏠 Fantasy Roofs & Chimneys
- **Roof Types**: Stylized Fairytale Sway Roof (with parabolic ridge dips, segmented sways, and flared eaves), Classic Medieval Gable, or Conical Turret Spire.
- **Inner Wood Ceiling Decking**: Continuous solid 0.12m timber sheathing beneath staggered shingles, sealing attics and eaves with zero light leaks.
- **Intersecting Cross-Gable Roofs**: Seamless compound roof junctions with full sway and wonkiness curvature.
- **Dormers & Gables**: Add gabled dormer windows protruding from the roof slopes.
- **Crooked Chimneys**: Cobblestone chimney stacks with beveled stone caps, flue liners, and terracotta smoke pots.

### 🪜 Full Walkable Interiors
- **Multi-Story Staircases**:
  - **Straight Switchback Stairs**: Automatically alternates flight directions (front-to-back and back-to-front) with shared floor landings for buildings with 3+ floors.
  - **Spiral Staircases**: Continuous $360^\circ$ circular rotation per floor around a central timber mast, with aligned floor openings and safety guardrails.
- **Structural Ceiling Beams**: Wooden joists with automatic trimmer header clearance around stairwells for full headroom.
- **Spacious Walkthrough Portals**: Full-depth timber archways encasing the wall core between compound wings.
- **Upper Floor Guardrails**: Stylized wooden balusters and handrails framing floor openings.
- **Embedded Floor Slabs**: Slabs embedded into the wall core to prevent edge gap seams.

### 🎨 Procedural Shaders & Materials
- Built-in stylized shader node graphs for:
  - Stucco / Rough Plaster Walls
  - Chiseled Stone Foundation & Chimney
  - Weathered Timber Framing & Beams
  - Slate / Terracotta Roof Shingles
  - Wrought Iron Hardware
  - Warm Architectural Glass
  - Wooden Door & Floor Planks
- Pre-configured UV layout (box-projected coordinates).

### ⚡ One-Click Architectural Presets
- 🏡 **Fairytale Cottage**: 1-story compact cottage with terracotta sway roof, flower boxes, stone foundation, and high attic loft.
- 🏘️ **Medieval Townhouse**: 3-story steep gable townhouse with multiple cantilever tiers and rich timber framing.
- 🧙 **Wizard Tower**: 3-story round octagonal tower (`ROUND_TOWER`) with conical turret spire roof, spiral stairs, alchemist glow windows, and crooked chimney.
- 🍺 **Cozy Tavern**: 2-story L-shaped inn with wide footprint, double entrance doors, fireplace chimney, ceiling beams, and lanterns.
- 🏹 **Watchtower**: 4-story defensive outpost featuring heavy stone masonry, cantilever battlement level, and steep roof.
- ⚒️ **Blacksmith**: 2-story L-shaped workshop with a 1-story forge annex (`wing_floors=1`), heavy stone foundation, and forge chimney.

---

## 🚀 Installation

### Option 1: Install Extension (.zip) in Blender 5.2
1. Download `blend_building_creator.zip` from the repository releases.
2. In Blender, navigate to **Edit** > **Preferences** > **Get Extensions**.
3. Click the **Install from Disk...** option (or the dropdown menu in the upper right) and select `blend_building_creator.zip`.
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
3. Click **Create Fantasy Building** to spawn a new building with procedural settings.
4. Experiment with presets (**Cozy Tavern**, **Wizard Tower**, **Blacksmith**, etc.) or customize individual panels:
   - **Floors & Dimensions**: Width, Depth, Floors, Building Shapes (Rectangle, L-Shape, T-Shape, Round Tower), Wing Dimensions & Floors, Cantilever Overhangs, Foundation.
   - **Walk-in Interior & Stairs**: Stair types (Straight, Spiral), railing toggles, ceiling beams.
   - **Openings**: Window density, door angle, shutters, planter boxes.
   - **Roof & Chimney**: Roof style (Sway, Gable, Turret), sway curvature, dormers, chimney stack.
   - **Materials**: Toggle procedural node shaders and customize surface colors.
5. When satisfied, click **Finalize Mesh** in the N-panel to collapse modifiers and bake into a standard editable Blender mesh.

---

## 📄 License

This project is released under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** license.

- **You are free to**: Use, modify, adapt, and build upon this tool for non-commercial projects, personal artwork, student work, and portfolio demonstrations, provided appropriate attribution is given to the author (`plastdrake`).
- **Restrictions**: You may **not** sell this add-on, distribute commercial paid derivatives, or package it for commercial resale.

See [LICENSE](LICENSE) for full legal terms.
