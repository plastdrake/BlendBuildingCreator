# Nasher's Manor → Sprawling Castle: Handover

Status: **planning done, no generator code changed yet.** This document lets a local agent
(or you) continue from here. Phases 1-2 below were approved; Phases 3-6 are not started.

## 1. Goal

`NASHERS_MANOR_T1/T2/T3` (in `blend_building_creator/presets.py`) currently give a boring
box-like U-shaped manor plus scattered outbuildings. Target: one **sprawling castle** that
grows across the three tiers (same place, same footprint, more additions + better materials
each tier), with height variation from rock outcrops.

Decisions from the user:
- Site: a plateau that already exists in-game, flat top. Generator adds outcrops/cliffs for height.
  Plot size **320 m x 320 m** (user allows 200-500 m).
- **South = entrance**, reached from the village by a path up a hill in small plateau increments.
- **North-west (-x, +y) = where outcrops stick out.**
- T1 = logs/planks, small, simple. T2 = same buildings + additions + stone/half-timber upgrades.
  T3 = even more additions + full cut stone/slate. Nothing should move between tiers.
- Rotated buildings are fine, but interior/furnishing generators will need to cope.
- Reference images are in `castlereferences/` (castle1-6.jpg).

## 2. What the references show (castle1, castle3, castle5 viewed)

- Many tall, slender round towers with steep conical slate/blue roofs and finials, in varied heights.
- Dense clustering: half-timbered steep-gabled halls, stone lower floors, timber upper floors,
  corbelled/jettied tower tops with timber galleries.
- Crenellated curtain walls stepping up the hill, with a broad stone staircase to the gate.
- Rocky outcrops around the base and the castle sitting on a raised rocky promontory (castle3),
  drawbridge/arched approach, small timber village buildings below.
- Strongly varied skyline; no big plain boxes.

## 3. How the current code works (findings)

- `generator/building.py::_build_castle_citadel_building` (used when `has_castle_citadel` is set) calls
  `accessories/castle.py::build_castle` (T1/T2/T3 builders, hard-coded coordinates), then
  `estate.py::build_estate_outbuildings`, then `dispatch.py::_build_plot_fortifications`
  (bastions, curtain wall, banners).
- **The castle path does NOT use the normal floors/walls/roof pipeline**; the U-shaped manor settings
  in the presets (`width`, `wing_*`, roofs...) mostly feed context only. Castle masses come from
  builders in `castle.py` (keep, ballroom wing, ramparts wing, scholar's wing, chapel, portal, towers).
- `castle.py` layouts: keep at (0,10); T3 west terrace z=7.5 (ballroom/scholar), east terrace z=6.0
  (ramparts), keep crag z=10.5. Tiers 1/2 use different, tiny layouts (palisade/gatehouse at z=0).
- Cliffs: `build_castle_cliff_terraces(bm)` = a few stacked beveled boxes (`MAT_INDEX_CLIFFS`, slot 42).
- Outbuildings: `estate.py::build_estate_outbuildings` places buildings at hard-coded offsets
  (Tier 3 "mini-city" around ±72, ±70) with `rot_z`; `_merge_generated_building` already supports `rot_z`.
- Curtain wall: `curtain_wall.py::build_curtain_wall_enclosure`; extents from preset
  (`curtain_wall_offset_x/y`, `curtain_wall_depth_extra`), gate at `ctx.main_door_cx`, ground_z=0.
- `validate_castle_generation` in `castle.py` raises ValueError if landmark/tower/courtyard/dungeon/
  secret-passage/district counts drop below per-tier minimums and requires an "Ancestral Old Keep"
  landmark. Keep this satisfied (or update it deliberately).
- Helpers: `create_beveled_box`, `create_cylinder`, `create_cone` (mesh_utils), `build_cliff_staircase`,
  `build_walkable_round_tower`, `build_high_skybridge` (castle.py), `poly.py` ring helpers.

## 4. Plan

### Phase 1 - shared site master plan (APPROVED, not started)
- New module e.g. `generator/accessories/nasher_site.py`: single source of truth for the castle layout.
  Named "slots" (position, rotation, footprint, ground height, first tier present). Slots never move
  between tiers; later tiers add slots / upgrade materials.
- Layout south→north-west: gate approach (stepped small plateaus) → outer ward at Z=0 (stables, forge,
  granary, training) → inner ward on raised rock (hall, chapel, barracks) → citadel on the highest NW
  outcrop (keep + spire + towers).
- Provide `ground_z(x, y, tier)` so every builder gets its base Z from terrain instead of constants.
- Refactor `build_castle_tier_1/2/3` to be driven by the site plan, reusing existing component builders.
- Move estate outbuildings from fixed offsets onto ward slots.

### Phase 2 - outcrops / height variation (APPROVED, not started)
- Replace `build_castle_cliff_terraces` with an outcrop builder: irregular rock masses made of nested,
  noise-displaced polygon ledges (deterministic seed, same polygon used for both mesh and `ground_z`
  point-in-polygon query so they agree), battered sides, flat pads for buildings, `MAT_INDEX_CLIFFS`.
- Cluster outcrops NW (outside the curtain wall, roughly x<-75, y>25) incl. one tall pinnacle and edge
  cliffs dropping well below Z=0; a few small rises elsewhere.
- Per-tier outcrop height/scale (T1 small rises ~1-2 m, T2 ~3-6 m, T3 full, e.g. keep crag 10.5 m,
  west terrace 7.5 m, east terrace 6.0 m to keep today's T3 heights, NW great crag ~18 m, pinnacle ~24 m).
- South approach: 3-4 stepped terraces with retaining walls and switchback stairs leading down from the
  plateau's south edge (z negative, outside the user's plateau), plus a cobbled road from the gate to the
  portal. Reuse `build_cliff_staircase`.
- Buildings partially buried in rock look fine; floating ones don't - prefer `ground_z` at anchors and
  let walls/palisades sit at Z=0.
- Update presets: plot "320m x 320m", descriptions; keep `has_cliffs`.

### Phase 3 - massing (not started)
Replace the box manor with a composite of masses (great hall, keep, chapel, linked halls), rotated
footprints (10-35°), many tall conical-roof round towers of varied height (see references),
stepped rooflines, corbelled upper floors, covered bridges/stairs, curtain wall following terrace edges.

### Phase 4 - rotation support (not started)
Audit `interior.py`, `furnishing.py`, `interior_furniture.py`, `mage_furnishing.py`, `furniture.py`,
`floors.py` for axis-aligned assumptions; generate in local space and transform by slot rotation/position
(reuse how `estate._merge_generated_building` handles `rot_z`).

### Phase 5 - tier materials (not started)
T1 logs/planks/wood shingles; T2 stone base + planks/half-timber; T3 cut stone + slate (match other presets).
Keep positions/footprints/door+window layouts identical across tiers for buildings that persist.

### Phase 6 - presets, docs, verification (not started)
Update the three presets, `docs/FORTIFICATIONS_AND_CASTLES.md`, `docs/PRESETS_AND_ESTATES.md`, README.
Render all tiers from the same camera (`scratch/render_*.py`, `scratch/smoke_presets.py`), extend
`tools/test_addon.py` (slots stable across tiers, buildings on valid ground).

## 5. Suggested next steps for the local agent
1. Read this file, `castle.py` (sections 9-16), `estate.py::build_estate_outbuildings`, and
   `presets.py` `NASHERS_MANOR_T1..T3`.
2. Implement `nasher_site.py` with `ground_z` + outcrop mesh builder; call it from
   `build_castle_tier_3_citadel` in place of `build_castle_cliff_terraces`, deriving `z_west/z_ramparts/z_keep`
   from `ground_z`. Render; then back-port T1/T2.
3. Stop for visual review before starting Phase 3.

## 6. Open questions
- Exact gate position relative to the new 320 m plot (existing curtain wall is ~124 m wide with gate on
  the south run; outcrops/approach must not collide with it).
- Whether to keep the Ancestral Old Keep at (0,10) as the lineage anchor (validation requires it).
