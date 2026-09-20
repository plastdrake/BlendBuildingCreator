# BlendBuildingCreator

[![Blender](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/Version-1.24.0-blue.svg)](https://github.com/plastdrake/BlendBuildingCreator)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

A procedural building generator add-on for **Blender 5.2 LTS** (4.2+). It builds complete stylized fantasy, medieval and rustic buildings in one click — exterior, roof and a full walkable interior — with 36 ready-made presets across three material tiers.

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

There are 36 presets (12 building families in 3 tiers each). Filter them by category in the preset panel.

| Category | Buildings |
| --- | --- |
| Civic | Town Hall (T-shaped, 40x40) |
| Military | Infantry Barracks (U-shaped, 40x40) |
| Industrial | Warehouse (L-shaped, 20x20), Lumbermill (rectangular, 20x20) |
| Residential | House 1 Small (12x12), House 2 Small (fairytale, 12x12), House 1 Medium (20x20), House 2 Medium (narrow, 12x20), House 3 Medium (L-shaped, 20x20 with courtyard) |
| Hospitality | Tavern (pub, 20x20), Tavern Long (narrow pub, 12x20), Inn (accommodation + pub, 40x40) |

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
- **Hospitality dressing** (reusable on any building): covered veranda, hanging textured trade sign, soil-filled window boxes, courtyard well, barrels, crates, sacks, stools, benches, picnic tables, post/hanging lanterns, notice boards and cloth awnings.

**Fortifications** (reusable on any preset/footprint)
- **Palisade** stockade: rough stakes or neat pickets enclosing the compound with a front gate (style, height and offset controls).
- **Stone curtain wall**: ashlar enclosing wall on a battered plinth with a wall-walk, crenellated merlons and a gated gatehouse (height, thickness and offset controls). Supersedes the palisade on the same defensive line.
- **Real arrow slits**: pierced arrow loops (with cut-stone reveals and a crosslet transom) in the bastion towers and curtain walls — genuine through-holes, not surface appliqués.
- **Banner** standards: timber poles with waving cloth banners and a heraldic **Banner colour**.
- **Crenellated battlements**: stone merlons or boxed timber hoarding capping the rampart walk.
- **Military props**: archery targets with painted rings, weapon racks and padded hay-filled training pells arranged along the courtyard walls, plus a wall-mounted shield over the entrance (the target face uses a dedicated ring shader and the pells use a handpainted hay shader).

## What's new in 1.24.0

- **Annex roof joins the main roof.** A full-height side annex now ties its cross-gable roof into the main roof with the same valley rafters the wings use. The deck is extended and notch-cut along the valley to the true apex (where the annex ridge meets the main slope), so the roof surface reaches the connection frame and the annex ridge no longer runs into the attic.
- **Wing lantern at the pillar.** A wing-corner lantern now mounts on the wing's outer side face at the corner post instead of on the windowed front face.
- **Balcony keeps clear of the gable ladder.** Balconies prefer the eave facades (where the loft/gable ladder never goes), so they no longer overlap the ladder to the gable hatch.
- **Wonkiness off.** All building presets now default to zero fantasy wonkiness.
- **Fewer windows.** Facades no longer get a forced window on every short segment, and the effective window spacing is sparser, so buildings read with a sensible number of windows per floor.
- **Dormers and chimney clear the annex.** Main-roof dormers that would land in a full-height annex's roof band are dropped, and the chimney is pushed out of that band, so nothing collides with the annex roof.
- **Natural roof orientation.** Presets no longer inherit a fixed front-to-back ridge: orientation now defaults to Auto, so the ridge always runs along the building's long axis and the gable ends are the short walls.
- **No balcony inside an annex.** Balconies now avoid whichever facade a side annex occupies (not just the town-hall composer's), so a balcony can't end up buried inside the annex.
- **Annex gable texture fixed.** The annex gable wall was textured in the roof's local frame and came out rotated/misaligned against the rest of the building; its UVs are now remapped in world space.
- **Lantern glass is a real light.** The lantern pane uses a dedicated emissive material (a 20th canonical slot), the fake interior candle geometry is gone, and the cage (roof cone included) is now properly UV-unwrapped.
- **Lantern holder off the posts.** Wall lanterns stand a few centimetres further off the wall so the bracket plate no longer sinks into the corner/veranda posts.
- **Door rivets on the strap.** Hinge-strap rivets were laid out from the hinge instead of the strap centre, so the outermost one fell onto the door frame; they now sit on the strap.
- **Flower boxes under the sill.** The trough stands off far enough to clear the projecting timber sill.
- **Sack props no longer crash.** A reuse of the cone helper in the sack builder was missing its import (only surfaced when sacks were generated).

## What's new in 1.23.0

- **Wing lanterns sit on the wall.** The wing-mounted lantern was hanging off the jettied upper-wall plane in mid-air; it now mounts on the wing's ground-storey footprint with the ground-floor skin offset, so it sits flush like the other lantern.
- **Annex sign respects log walls.** The annex gable sign now accounts for a Tier-1 annex being built entirely from logs (bulging skin) versus the flush stone/plank/stucco of other tiers, so it lands at the right depth.
- **Cleaner log annexes.** A log annex's eave (non-gable) walls now drop their top log so it can't poke into the roof overlap, and the logs where the annex meets the main hall no longer saddle-over-run into the main building's interior.

## What's new in 1.22.0

- **Corner posts on every stone base.** Tier-1 log cabins keep their oak corner posts on the stone ground storey too (previously the whole ground-floor frame was skipped on Tier 1). Only the infill/brace timbering stays off the masonry.
- **Signs sit on the right wall again.** Wing gable signs now track the wing's *top* storey bounds, so they no longer bury themselves in a jettied log wall - and the annex gable sign anchors to the annex's true outer face instead of the main hall's (jettied) half-width, so it no longer floats in mid-air.
- **Signs clear their brace.** The board hangs lower on its straps, so the diagonal support sits fully above it instead of crossing the face.
- **Wing-aware lanterns.** When a wing occupies a front corner, the lantern detects it and mounts on the wing's own outer wall instead of burying itself inside the wing block.
- **Tier detection fixed.** Wall props consulted a non-existent "building material" flag that always read as log, pushing signs/lanterns/planters off flush stucco and plank walls; they now key off the real material tier.

## What's new in 1.21.0

- **Tier-2 walls are planks, not planks-on-stucco.** Removed the physical 3D plank siding that was layered over a stucco core (and its now-unused builder). Tier-2 walls are a clean surface textured with the facade-plank material, so the timber frame reads on top of real planks rather than a board shell.
- **Timber corner posts back on stone foundations.** The stone ground storey keeps its oak corner posts again (they were being skipped wholesale with the rest of the ground-floor timbering). Only the infill/brace timbering stays off the stone base.
- **Wall props are floor-aware.** Sign, lanterns and flower boxes use the correct wall thickness per storey, so on a thin stone ground floor they sit dead flush against the wall again instead of floating at the log-crest offset.

## What's new in 1.20.0

- **Signs on every gable.** The trade sign now also hangs on each wing's gable and on the annex's own gable (as well as the main roof gable ends). Where a loft hatch sits low in a gable, the sign is raised near the apex so it clears the hatch instead of hanging in the middle of it.
- **Notice board fixed.** A leftover duplicate placement was overriding the new shape-aware one (so it always ended up in the L-shaped spot). Removed, and the board now clears the jettied upper floor - beside the door against the facade for rectangle/square plans, on the wing wall for L-shaped plans. Its pinned papers now use the clock-face material.
- **Lanterns avoid windows.** Wall lanterns slide along the facade to the clearest spot, so they no longer sit in the middle of a window (or the door).
- **Double doors.** Tavern / Tavern Long / Inn doors are now at least 1.7m wide, so they build as double doors.
- **Plain log annexes.** Tier-1 annexes drop the timber corner posts and the top log on their eave sides (the one that poked through the roof); half-timbered tiers keep their framing.

## What's new in 1.19.0

- **Trade sign now hangs from the roof gables.** Instead of one sign beside the door, a large bracket sign is hung on every exposed gable end of the main roof (front and back for a front-back ridge, left and right for a rotated one). Gable ends already taken by a wing or the side annex are skipped. Buildings whose roof raises no gable (hip roofs) keep the beside-the-door sign as a fallback.

## What's new in 1.18.0

- **Sign + lanterns sit on the wall now.** Both are mounted at a storey-relative height on the facade (the old fixed ~3.5m mount floated above the wall top on single-storey buildings) and their brackets are longer so the board/lantern clears the logs. The trade sign is also bigger.
- **Bucket handle.** Removed the ring from the rope; the bucket now has a proper forged bail handle arcing over the top and the rope runs down through it and is lashed at the apex, so they read as connected.
- **Well clearance.** The well sits further from the building and the hood is more compact, so its roof no longer reaches into the main building's timber framing.
- **Flower boxes restored** to their previous stand-off so they sit under the sill instead of inside it.
- **Smarter yard props:** the bench picks whichever side of the door is free (so it no longer vanishes), and the notice board leans on the wing wall for L-shaped buildings but turns to sit against the facade beside the door for rectangular/square ones.

## What's new in 1.17.0

- **Annex portal:** generic side annexes (taverns/inns/etc.) now open into the main hall with a framed walk-through doorway on every floor the annex spans, matching the Town Hall annex.
- **Wall props actually bolt on:** the trade sign and corner lanterns now mount flush against the wall (log crest aware) and reach far enough out to clear it - no more floating brackets.
- **Well cleaned up:** the well roof's shingle slabs are fixed in place (they were stuck at the world origin, floating inside the building), the fake water table and inner shaft are gone (the lid covers it), and the hood sits down on its posts.
- **Well bucket fixed:** it's raised, now has a solid floor, and the rope runs all the way down to a forged tie-loop set into its rim so the two connect.
- **Tavern entrance tidied:** the bench moves to the wall on the **left** of the door and the notice board to the **right**, angled out toward the street; the notice board's backing no longer pokes through its top/bottom rails.

## What's new in 1.16.0

- **Clear material tiers:** Tier 1 builds stacked rounded **logs**, Tier 2 now builds physical **wood-plank siding** (overlapping weatherboards, or board-and-batten when the plank direction is vertical) instead of smooth stucco, and Tier 3 stays **stucco over an ashlar stone base**. The tiers read as three genuinely different constructions.
- Plank walls cut cleanly around every door/window, with the sealed interior core kept recessed behind the boards so the planks are the visible skin (no plaster poking through).

## What's new in 1.15.0

- **Overhang-aware facade mounting:** the trade sign, corner lanterns, window boxes and the veranda awning now attach to the correct outer face of the storey they sit on (and clear the log bulge), so nothing buries into a jettied wall or shows up inside the interior any more.
- **Veranda anchored to the outer face:** the porch/awning is built off the outermost front wall, so its roof no longer clips into the upper storey or the ceiling.
- **Well off the doorstep:** the well now sits to the **left** of the entrance instead of straight in the dooring line.
- **Rebuilt well:** proper framed gable hood (fascia + raked barge boards) resting directly on the posts - no more floating beams or bare edges - plus a truly **hollow** bucket and a small rope-tie loop on the rim (the rope now ends where it would be knotted, instead of dangling from a big ring).
- **Correct rope UVs:** rope is unwrapped so the strand texture (`rope_diffuse`) runs along the length with a single strand wrapping the circumference, instead of smearing around.
- **Annex matches the walls:** a log (Tier 1) building now gets a plain log annex - no half-timbering over logs.
- **Hay bales removed** entirely (bring your own in-engine) and the notice board is turned ~100° clockwise to sit along the entrance path.

## What's new in 1.14.0

- **Simpler window boxes:** the planters are now plain timber troughs with a soil fill, seated right under the sill — no fake plants, lid or iron brackets; drop your own flowers in-engine.
- **Wall lanterns:** the corner lanterns hang from the facade on forged brackets (no more posts), with a narrower cage, no stray cross-wires, and hook/ring geometry that actually links. The veranda no longer sits in the doorway.
- **Cleaner sign:** removed the loose iron rings/scrolls; the support brace now actually braces the arm, the board sits close to the wall beside the door and angles a few degrees toward the entrance.
- **Round well:** smooth masonry shaft and coping (no block-by-block stones), a fitted lid, a real banded bucket, a proper windlass crank, and a new rope material (19 slots).
- **Reusable side annex:** the Town Hall's half-timbered annex is extracted into a generic `annex` module and is now available on any building (added to the Tavern/Inn tiers).
- **Tavern/Inn tier fix:** restored the Tier 1/2/3 material progression (they had all been flattened to Tier 2) and rotated the Inn's main roof 90° (`LEFT_RIGHT`).
- **Tidier beer garden:** benches moved out of the doorway into the table cluster, and the front balcony is kept clear of the raised veranda.

## What's new in 1.13.0

- **Two taverns + a grand inn:** Hospitality is now three families — **Tavern** (20x20), **Tavern Long** (12x20, narrow) and **Inn** (40x40). Top tiers fill most of their plot with building plus garden/well/props.
- **All doors ship closed** (Door Open Angle 0 in every preset).
- **Higher-quality handmade props** (chunky, slightly wonky, game-ready): lathe-turned **barrels** with staves and three iron hoops, planked **crates** with iron corner straps, braced **stools**, slatted **benches**, heavy A-frame **picnic tables**, hand-forged **post/hanging lanterns** and **sacks**.
- **Textured hanging signs:** a large light-plank sign carrying a handpainted **beer-mug (tavern)** or **bed (inn)** icon decal, hung high on the frontage facing the street.
- **Soil-filled window boxes:** the planters are now proper wooden troughs with iron brackets and a tilable **dirt** fill (no fake foliage) — drop your own flowers in-engine.
- **Veranda roof fixed:** the lean-to now uses the same shingle UV orientation and scale as the main roofs, with fascia/barge/flashing boards covering the exposed slab edges.
- **Two new material slots** (`M_Building_Dirt`, `M_Building_Sign`) for **18** total.
- **Tidier beer-garden layout:** furniture sits in clusters clear of the entrance path instead of blocking the door.

## What's new in 1.12.0

- **New Hospitality category:** tiered **Tavern** (public house) and **Inn** (accommodation + pub) families, each in three tiers, plus a new `INN` archetype.
- **Reusable prop modules:** new generic `furniture`, `lighting`, `garden` and `signage` modules (barrels, crates, sacks, stools, benches, picnic tables, post/hanging lanterns, flower boxes, wells, hay bales, hanging trade signs, notice boards and cloth awnings) usable by any building.
- **Refactor for SOLID/GRASP:** the generic balcony moved out of `tavern.py` into `balcony.py`, the hanging sign moved into `signage.py`, and the veranda porch now returns its post so signage composes onto it. New `hospitality.py` holds only the tavern/inn composition.
- **New UI toggles (any building):** Covered Veranda, Hanging Trade Sign, Window Flower Boxes, Yard Props & Furniture, and Courtyard Well.
- **Window boxes align to real windows:** the wall phase now records window sill centres on the generation context, so flower boxes, awnings, lanterns and baskets can line up with the actual openings.

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
