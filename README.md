# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.3.0-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**BlendBuildingCreator** is a procedural 3D building generator add-on for **Blender 5.2 LTS** (compatible with 4.2+). Designed for concept artists, level designers, and game developers creating stylized fantasy, medieval, and rustic architecture in seconds.

Unlike simple facade generators, **BlendBuildingCreator generates full, walkable interiors**—including switchback or spiral staircases with railings, structural floor and ceiling joists, framed walk-in doorways with opening doors, and timber-decked attics with king-post trusses.

---

## ✨ What's New in v1.3.0

- 🪵 **3 Material Progression Tiers**:
  - **Tier 1 (Log / Heavy Timber)**: Rugged horizontal log walls (`ShaderNodeTexWave`), cedar shake shingles, and coarse fieldstone foundations.
  - **Tier 2 (Wood Planks / Weatherboard)**: Horizontal plank siding with saw-band texturing, slate roof tiles, and clean timber frame trim.
  - **Tier 3 (Ashlar Stone / Stucco)**: Dressed medieval stone masonry, bright smooth plaster/stucco, and royal terracotta/slate shingles.
  *(Dimensions remain identical across tiers for seamless modular level upgrades)*.
- 🏛️ **31 One-Click Game Presets** across 5 filterable categories:
  - **Civic & Manor**: Town Hall, Guild Hall, Manor House, Merchant House, Library.
  - **Military & Defense**: Watchtower, Guard Barracks, Armory, Fortified Gatehouse, Archery Range.
  - **Artisan Guilds**: Alchemist Shop, Herbalist Hut, Enchanter Tower, Weaver Cottage, Pottery Workshop.
  - **Industrial & Craft**: Blacksmith Forge, Windmill, Watermill, Brewery, Bakery, Lumber Mill, Tannery.
  - **Commercial & Living**: Fairytale Cottage, Medieval Townhouse, Wizard Tower, Cozy Tavern, Fisherman Hut, Farmer Barn, Miner Shack, Stable.
- 📐 **Compound Footprint Refinements**:
  - **Independent Wing Floors**: Freely configure 1-story workshops or wings on multi-story buildings (`wing_floors < num_floors`).
  - **Flush Roof Abutment**: Lower-floor wing roofs terminate cleanly at the upper facade without cutting into upper rooms.
  - **Solid Wing Ceilings**: Generates solid interior ceilings and exposed joist beams at the wing roofline.
  - **Window Occlusion Avoidance**: Front windows automatically avoid intersecting lower wing roofs.
  - **Soffit & Corbel Masking**: Cantilever brackets and soffit plates cleanly split around intersecting wing roofs.
- 🪜 **Collision-Free Multi-Storey Stairwells**:
  - Automatically eliminates redundant guardrails on intermediate floors in 3+ storey buildings to keep ascending stairways completely clear.
  - Trimmer sill plates intelligently suppress when cantilever overhang is 0 to avoid newel post clipping.

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
