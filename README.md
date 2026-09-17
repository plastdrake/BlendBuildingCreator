# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.8.3-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

A procedural building generator add-on for **Blender 5.2 LTS** (4.2+). It builds complete stylized fantasy, medieval and rustic buildings in one click — exterior, roof and a full walkable interior — with 27 ready-made presets across three material tiers.

## Installation

1. Download `blend_building_creator.zip`.
2. In Blender go to **Edit > Preferences > Get Extensions**, open the dropdown (top right), choose **Install from Disk...** and pick the zip.

Or copy the `blend_building_creator` folder into:
`%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\`

## Quick start

1. Press `N` in the 3D Viewport and open the **Fantasy Building** tab.
2. Click **Create Fantasy Building**.
3. Pick a preset, then tune the sub-panels:
   - **Floors & Dimensions** — size, floors, footprint shape, wings, cantilever, foundation.
   - **Walk-in Interior & Stairs** — stairs, railings, ceiling beams.
   - **Openings & Framing** — doors, windows, shutters, timber framing.
   - **Roof & Details** — roof style, dormers, chimney, turret, loft hatch, clock spire.
   - **Wings, Balconies & Overhangs** — outcrops, balconies, pillared overhang, landmarks.
   - **Materials & Colors** — material tier and surface colors.
4. Click **Finalize Mesh** to bake the result into a standard editable mesh.

## Presets

There are 27 presets (9 building families in 3 tiers each). Filter them by category in the preset panel.

| Category | Buildings |
| --- | --- |
| Civic | Town Hall (T-shaped, 40x40) |
| Military | Infantry Barracks (U-shaped, 40x40) |
| Industrial | Warehouse (L-shaped, 20x20), Lumbermill (rectangular, 20x20) |
| Residential | House 1 Small (12x12), House 2 Small (fairytale, 12x12), House 1 Medium (20x20), House 2 Medium (narrow, 12x20), House 3 Medium (L-shaped, 20x20 with courtyard) |

Every building comes in three material tiers: **Tier 1 Logs**, **Tier 2 Planks** and **Tier 3 Stone/Stucco**.

## Features

**Footprints**
- Parametric width, depth, 1-5 floors, floor height and foundation height.
- Shapes: Rectangular, L-Shaped, T-Shaped, U-Shaped and an 8-sided Round Tower.
- Cantilever jettying (second floor only or every floor) with timber corbels and soffits.
- Tudor half-timber framing cut cleanly around every opening.
- Optional "Wonkiness" for a hand-built, crooked look.

**Openings**
- Single and double doors (arched stone or square timber) with iron hinges and a door open/close angle.
- Grounded stone entrance steps.
- Framed windows with recessed casings, sills, glass and open/closed shutters.

**Roofs**
- Fairytale sway roof, classic gable and conical turret spire.
- Solid inner ceiling decking, dormers, chimneys, roof turret, roof clock spire and an optional gable loft hatch.

**Walkable interiors**
- Straight switchback or spiral staircases with generated railings.
- Structural floor slabs and ceiling joists trimmed around stair openings.
- Timber walk-through portals between wings and the main hall.

**Civic landmarks** (Town Hall)
- Attached clock tower, square corner turrets, elevated rampart walk with timber railing, side annex and oriels.

**Accessories**
- Mini-wing outcrops (with optional random width/depth), balconies and a pillared overhang.
- Archetype props: warehouse crane, lumbermill sawmill, blacksmith forge, windmill sails, watchtower parapet, tavern porch, fisherman pier and bakery oven.

## What's new in 1.8.3

- Fixed the wing entrance portal on T-shaped buildings: the redundant wall opening is gone, so the timber frame lines the cut-out with no gaps.
- Fixed mini-wing outcrops blanking the storey above — they no longer remove windows or timber framing on the floor overhead.
- Added outcrop size controls: **Use Random Size** with **Random Width Amount** and **Random Depth Amount**, for varied bays that never overlap.
- Fixed a crash when building a winged watchtower.

## License

Licensed under [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html), matching the Blender extension manifest.
