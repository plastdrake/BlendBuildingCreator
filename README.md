# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.11.3-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
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

**Fortifications** (reusable on any preset/footprint)
- **Palisade** stockade: rough stakes or neat pickets enclosing the compound with a front gate (style, height and offset controls).
- **Stone curtain wall**: ashlar enclosing wall on a battered plinth with a wall-walk, crenellated merlons and a gated gatehouse (height, thickness and offset controls). Supersedes the palisade on the same defensive line.
- **Real arrow slits**: pierced arrow loops (with cut-stone reveals and a crosslet transom) in the bastion towers and curtain walls — genuine through-holes, not surface appliqués.
- **Banner** standards: timber poles with waving cloth banners and a heraldic **Banner colour**.
- **Crenellated battlements**: stone merlons or boxed timber hoarding capping the rampart walk.
- **Military props**: archery targets with painted rings, weapon racks and padded hay-filled training pells arranged along the courtyard walls, plus a wall-mounted shield over the entrance (the target face uses a dedicated ring shader and the pells use a handpainted hay shader).

## What's new in 1.11.3

- **Painted pell bullseye:** the training dummy's paper plate and lashing cords are gone; the ring is now a painted red circle that conforms to the barrel, so it can never read as a detached plate (the paper panel was removed entirely).
- **Heritage banners:** the gable crest is a single flat heraldic banner hanging behind the timber gable framing (was a kite shield), pushed clear of the roof and scaled up. Shields now flank only the main entrance instead of ringing the outer walls.
- **Cleaner gatehouse:** the entrance piers are pulled in and deepened, and the lintel deepened, so the timber frame reaches through the wall without z-fighting the masonry and covers the stone head of the opening.
- **Seamless wall-to-tower plinths:** the corner bastion's cut-stone plinth is a continuous ring and every curtain-wall run tucks its plinth under the tower band, closing the notch of bare masonry where the wall met the tower.
- **Tier 3 rampart walk restored:** the elevated side rampart walk and its long descent ramp are back on the citadel barracks, running between the building and the curtain wall.

## What's new in 1.11.2

- **Square paper target on the pell:** the training dummy's painted bullseye is replaced by a flat square paper scoring target lashed onto the chest with four corner cords and knots. Being a separate proud plate, it can never read as embedded in the hay.
- **Weapon racks moved off windows:** the racks now flank the gate against the front enclosure wall (which has no windows) and face into the courtyard, instead of clipping the wing windows.
- **Roomier barracks (all tiers):** increased the enclosure offset for a clear walkway around the building, shortened the wings and narrowed the courtyard. T1/T2/T3 now measure roughly 27/34/39 m wide and 22/25/32 m deep.
- **Tier 3 curtain wall pushed out:** the wall offset was raised to 5.5 m so the curtain clears the building's corner turrets with a wide walkway, while the compound still fits inside 40x40 m.
- **Square roof turret:** the Tier 3 barracks roof spire turret defaults to the 4-sided **Square Belfry** style.

## What's new in 1.11.1

- **Plot fits 40x40:** the Tier 3 Infantry Barracks footprint was slimmed (33x11.5 m → 29x10.5 m) so the whole compound, curtain wall and corner towers measure under 40x40 m with a roomier drill yard.
- **Curtain-wall corners sealed:** bastion towers straddle the compound boundary (full width across X, half in Y), so the side runs now meet the towers cleanly instead of leaving a gap at the corners.
- **Cleaner gatehouse:** removed the bulky projecting lintel + keystone boss that read as a stray slab above the entrance; replaced with a slim flush lintel band and slimmer piers.
- **Fewer, better-placed shields:** mounted higher (clear of the arrow-slit heads) and spaced much wider by default.
- **Drill-yard layout:** archery targets line one wing wall and training pells the opposite wall, both facing into the courtyard so they face each other; weapon racks stand at the inner ends. New **Weapon Racks / Training Pells / Archery Targets** counts (Tier 3 defaults 2/3/3).
- **Better training pell:** removed the odd metal base brackets, the painted bullseye now sits proud of the barrel (no longer embedded), and the stuffed torso/head use a new handpainted **hay/burlap** material (`M_Building_Hay`, the 16th material slot).
- **Raised banners** so the hanging cloth clears the crenellated parapet, and fixed a crossbar finial spike that pointed 180 degrees the wrong way.

## What's new in 1.11.0

- **Reusable stone curtain wall** (any preset/footprint): a new `curtain_wall` module builds an ashlar enclosure with a battered plinth, a crenellated wall-walk, and a gated gatehouse. It supersedes the palisade on the shared defensive line, so towers, walls, gates, banners and shields all align. New UI toggles for **height**, **thickness** and **offset**.
- **Genuine arrow slits:** bastion towers and the curtain wall now have real through-wall arrow loops (cut with the host-wall opening system and dressed with cut-stone reveals, sill, lintel and a crosslet transom) instead of applied stone/iron "window" blocks.
- **Dedicated archery-target material:** a new procedural `M_Building_Target` shader paints the scoring rings and gold bullseye from radial UVs, so the target face no longer borrows the wall/iron materials. The add-on now generates 15 material slots.
- **Nicer training pell:** the old shield-quintain (whose shield clipped through the arm) is replaced by a padded burlap pell with a painted bullseye, stuffed head, cross arms with rope-wrapped ends, rope bindings and a bracketed round timber base — matching the reference art.
- **Fixes:** palisade stake/post UV stretching (per-face planar mapping so the bark grain no longer smears on the sides); arrow fletching was rotated 180° (now flares toward the archer); removed the mis-rotated shield bolts; and the **gable heraldic crest** now works — the crossed swords lie flat in the gable plane and the crest mounts on a true gable instead of being buried under the eave.
- **Infantry Barracks Tier 3** now reads as a stone-walled fortress: curtain wall + gatehouse + real ramparts replace the wooden palisade.

## What's new in 1.10.0

- **New reusable fortification modules** (any preset, any footprint, via new UI toggles): pointed-stake or picket **palisade** with a front gate, heraldic **banner** standards, **crenellated battlements** (stone merlons or timber hoarding) on the rampart walk, and **military props** (weapon racks, wall shields, training dummies).
- **Banner material:** a new heraldic cloth shader and **Banner colour** picker (the add-on now generates 14 material slots).
- **Infantry Barracks** use the new fortifications across all three tiers; applying a preset no longer inherits a previous building's fortification state.

## What's new in 1.9.2

- **Rampart walks fit better:** the reusable side rampart now spans the full side wall (instead of a fixed 7 m) and the upper door is centred on the walk, so the descent ramp no longer blocks it. The walk is skipped when a wing projects from the same side.
- **Smarter loft hatch placement:** the gable loft hatch scores potential overlaps (rampart, tower, corner turrets, porch, wings, outcrops, balcony, doors) and, when both main gables are obstructed, falls back to a free front/back wing gable for the hatch and ladder.

## What's new in 1.9.1

- **Infantry Barracks fortifications:** Tier 2 and Tier 3 now use the reusable side rampart walk, and the Tier 3 clock tower was removed so the barracks reads as a walled citadel with corner towers and a roof spire.
- **Barracks roof orientation:** the main roof of every barracks tier is now rotated 90 degrees (ridge runs side-to-side).

## What's new in 1.9.0

- **Infantry Barracks overhaul:** all three tiers rebuilt. Tier 1 is a log camp with a stone gate porch, Tier 2 a plank headquarters with oriel outcrops and a gable loft hatch, Tier 3 a fortified citadel with a clock gate-tower, twin corner towers, a roof spire and scattered oriels.
- **Rampart walks are now reusable:** the **Side Rampart** option works on any footprint (U-shaped, L-shaped, rectangular), not just T-shaped town halls.
- **Internal refactor for maintainability:** the 3,600-line orchestrator was split into focused modules (`floors`, `roof/attic`, `roof/details`, `shapes`, `round_tower`, `style`) and the town-hall-only landmark code became reusable `tower`, `rampart` and `porch` modules. Generated geometry is unchanged.

## License

Licensed under [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html), matching the Blender extension manifest.
