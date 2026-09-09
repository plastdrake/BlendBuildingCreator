# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.5.0-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**BlendBuildingCreator** is a procedural 3D building generator add-on for **Blender 5.2 LTS** (compatible with 4.2+). Designed for concept artists, level designers, and game developers creating stylized modern fantasy, medieval, and rustic architecture in seconds.

Unlike simple facade generators, **BlendBuildingCreator generates full, walkable interiors**—including switchback or spiral staircases with railings, structural floor and ceiling joists, framed walk-in doorways with opening doors, and timber-decked attics with king-post trusses.

---

## ✨ What's New in v1.5.0

- 🪵 **Horizontal OR Vertical Plank Siding with Plank Jankiness (Tier 2)**:
  - **Plank Direction**: Toggle between `HORIZONTAL` (classic overlapping weatherboard lap planks) and `VERTICAL` (stylized Scandinavian / fantasy board-and-batten siding with raised battens over seams).
  - **Plank Jankiness**: Control handcrafted board wobble, depth variations, and subtle angular tilts with a dedicated slider.
- 🧱 **Chunky 3D Stylized Stone Blocks with Size & Disorder Controls (Tier 3)**:
  - Generates actual chunky volumetric stone blocks / bricks with staggered running-bond courses, soft stylized bevels, and recessed mortar seams.
  - **Stone Block Size** (`stone_block_scale`): Scales the course height and nominal block dimensions from tight bricks to massive castle ashlar blocks.
  - **Stone Disorder** (`stone_disorder`): Controls random depth protrusion pop, irregular seam lengths, and 3D face tilts for heavy, stylized fantasy masonry.
- 🌲 **Authentic Rounded Logs with Staggered Interlocking Saddle-Notch Corners (Tier 1)**:
  - 12-sided rounded horizontal cylindrical logs with authentic circular end-grain caps.
  - **Saddle-Notch Vertical Staggering**: Perpendicular X and Y walls are automatically vertically staggered by half a log height ($0.5 \times \Delta z$), allowing projecting corner ends to cleanly alternate without intersecting collisions.
- 🏔️ **Gable Wall Material Matching**:
  - Triangular attic walls under gable and sway roof pitches now match the facade material (logs in Tier 1, planks in Tier 2, stone/stucco in Tier 3).
- 🧙 **Wizard Tower Faceted Siding**:
  - Angled facet walls on round towers now receive the selected tier material (logs or planks) with flush-rotated faceted window assemblies.
- 🏚️ **Solid Freight Warehouse with Hoist Beam & Double Cargo Doors**:
  - Solid full-height walls (no open gaps), massive double freight cargo doors (2.2m wide) with dual hinged leaves, and a projecting roof hoist beam with suspended chain and curved iron cargo hook.

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
Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
Free for personal and non-commercial educational use.
