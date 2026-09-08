# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**BlendBuildingCreator** is a powerful, procedural 3D building generator add-on for **Blender 5.2 LTS**. Designed specifically for concept artists, environment designers, and game developers looking to create rich, stylized fantasy and medieval architecture in seconds.

Unlike basic facade generators, **BlendBuildingCreator builds full, walkable interiors**—including multi-story switchback or spiral staircases, ceiling beams, framed doorways with opening doors, and timber-decked attics.

---

## ✨ Key Features

### 🏰 Architectural Generation
- **Parametric Dimensions**: Freely customize base width, depth, number of floors, floor heights, and foundation height.
- **Cantilever Overhangs**: Generate historical jettying / cantilever upper floors with solid timber soffit plates and structural corbel brackets.
  - **Overhang Mode**: Toggle between `SECOND_FLOOR_ONLY` (classic medieval style) or `ALL_FLOORS` (gradual outward stepping).
- **Tudor Half-Timber Framing**: Procedural wooden wall posts, girts, and diagonal cross-braces intelligently cut around doors and windows.
- **Whimsical "Wonkiness"**: Add stylized organic tilts, sways, and crooked fantasy deformations with a single slider.

### 🚪 Openings & Entrances
- **Interactive Doors**: Single or double doors with stylized iron strap hinges, door handles, and an interactive **Open Door** slider.
- **Grounded Stone Steps**: Entrance stair steps with solid risers and plinths extending down to ground level ($Z=0$).
- **Framed Windows**: Recessed wooden casing frames, lintels, exterior shutters, flower planter boxes, and glass panes.

### 🏠 Fantasy Roofs & Chimneys
- **Roof Types**: Stylized Sway Roof (with parabolic ridge dips and flared eaves), Classic Gable, or Conical Turrets.
- **Inner Wood Ceiling Decking**: Continuous solid timber sheathing beneath staggered shingles, sealing attics and eaves with zero light leaks.
- **Dormers & Gables**: Add gabled dormer windows protruding from the roof slopes.
- **Crooked Chimneys**: Cobblestone chimney stacks with beveled stone caps, flue liners, and terracotta smoke pots.

### 🪜 Full Walkable Interiors
- **Multi-Story Staircases**:
  - **Straight Switchback Stairs**: Automatically alternates flight directions (front-to-back and back-to-front) with shared floor landings for buildings with 3+ floors.
  - **Spiral Staircases**: Continuous $360^\circ$ circular rotation per floor around a central timber mast.
- **Structural Ceiling Beams**: Wooden joists with automatic trimmer header clearance around stairwells for full headroom.
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
- 🏡 **Cozy Cottage**: 1-story compact cottage with stone foundation and sway roof.
- 🏘️ **Townhouse**: 2-story medieval dwelling with cantilevered upper floor.
- 🧙 **Wizard Tower**: 3-story tall tower with spiral stairs and steep roof.
- 🍺 **Tavern**: Large 2-story building with double entrance doors, fireplace chimney, and front steps.
- 🏹 **Watchtower**: Stone-heavy defensive outpost with straight interior stairs.
- ⚒️ **Blacksmith**: Sturdy workshop featuring stone masonry foundation and wide footprint.

---

## 🚀 Installation

### Option 1: Install Extension (.zip) in Blender 5.2
1. Download `blend_building_creator-1.0.0.zip` (or `blend_building_creator.zip`) from the repository releases.
2. In Blender, navigate to **Edit** > **Preferences** > **Get Extensions**.
3. Click the **Install from Disk...** option (or the dropdown menu in the upper right) and select the `.zip` file.
4. The add-on is now installed and active!

### Option 2: Manual Folder Install
Copy the `blend_building_creator` directory into your Blender 5.2 user extensions folder:
```
%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\blend_building_creator\
```

---

## 🛠️ How to Use

1. In the 3D Viewport, press `N` to open the sidebar.
2. Select the **Building Creator** tab.
3. Click **Create Fantasy Building** to spawn a new building with procedural settings.
4. Experiment with presets (**Cozy Cottage**, **Tavern**, **Wizard Tower**) or customize individual panels:
   - **Dimensions**: Width, Depth, Floors, Cantilever Overhangs, Wonkiness.
   - **Interior & Stairs**: Stair types, railing toggles, ceiling beams.
   - **Openings**: Window density, door angle, shutters, planter boxes.
   - **Roof & Chimney**: Roof style, sway amount, dormers, chimney stack.
   - **Materials**: Toggle procedural node shaders and material assignments.
5. When satisfied, click **Finalize to Mesh** in the N-panel to collapse modifiers and bake into a standard editable Blender mesh.

---

## 📄 License

This project is released under the **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** license.

- **You are free to**: Use, modify, adapt, and build upon this tool for non-commercial projects, personal artwork, student work, and portfolio demonstrations, provided appropriate attribution is given to the author (`plastdrake`).
- **Restrictions**: You may **not** sell this add-on, distribute commercial paid derivatives, or package it for commercial resale.

See [LICENSE](LICENSE) for full legal terms.
