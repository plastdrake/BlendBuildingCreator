# Developer & Contributor Guide

This guide details how **BlendBuildingCreator** is structured, how to add new features, how properties and UI panels interact, and how to run automated tests and headless renders in Blender 5.2.

---

## 1. Codebase Directory Structure

```
d:\BlendBuildingCreator\
├── blend_building_creator/             # Add-on package root
│   ├── __init__.py                     # Addon register / unregister entry point
│   ├── blender_manifest.toml           # Blender 5.2 extension manifest & version
│   ├── properties.py                   # PropertyGroup definitions & update handlers
│   ├── ui.py                           # 3D Viewport sidebar panels (N-panel)
│   ├── operators.py                    # Blender operators (generate, preset, bake)
│   ├── presets.py                      # Dictionary definitions for all 78 presets
│   ├── textures/                       # Hand-painted diffuse & normal textures
│   └── generator/                      # Procedural geometry engine
│       ├── building.py                 # Master pipeline orchestrator
│       ├── config.py                   # Global constants and material slot tables
│       ├── materials.py                # Shader node generators & slot pruning
│       ├── mesh_utils.py               # Geometric primitive helpers (box, cylinder, cone)
│       ├── uv_utils.py                 # Box UV, planar mapping & fiber alignment
│       ├── shapes.py / poly.py         # Footprint polygon geometry
│       ├── floors.py / walls.py        # Structural slabs, walls & partitions
│       ├── facade.py / openings.py     # Half-timber framing, doors & windows
│       ├── interior.py                 # Slabs, stairs, railings, and corridors
│       ├── roof/                       # Roof styles, attics, dormers, and valleys
│       └── accessories/                # Specialized modular builders & props
│           ├── castle.py               # Fantasy castle generation engine
│           ├── estate.py               # Outbuildings & compound orchestration
│           ├── curtain_wall.py         # Stone walls & rampart walks
│           ├── bastion.py              # D-bastions & arrow loops
│           ├── gatehouse.py            # Portcullis, drawbridge & chains
│           ├── palisade.py             # Timber stockade bailey
│           ├── furniture.py            # Basic props (tables, chairs, barrels)
│           ├── interior_furniture.py   # Specialized furniture (thrones, hearths, beds)
│           └── military_props.py       # Weapon racks, targets, training dummies
├── docs/                               # Comprehensive markdown documentation
├── tools/
│   ├── deploy_addon.py                 # Syncs to %APPDATA% & bumps extension version
│   └── test_addon.py                   # Headless test runner
└── scratch/                            # Verification & render test scripts
```

---

## 2. Properties, UI & Update Loop

### 1. Property Group (`properties.py`)
All building configuration is stored on `bpy.types.Scene.fantasy_building_settings` via `FantasyBuildingSettings(bpy.types.PropertyGroup)`:

```python
has_castle_citadel: BoolProperty(
    name="Castle Citadel Keep & Drum Towers",
    description="Monumental castle fortress orchestrating all modular builders",
    default=False,
    update=on_property_updated
)

castle_tier: EnumProperty(
    name="Castle Progression Tier",
    items=[
        ('TIER_1', "Tier 1: Frontier Stronghold", "Original wooden and rough stone stronghold"),
        ('TIER_2', "Tier 2: Regional Fortress", "Expanded fortress built around the original keep"),
        ('TIER_3', "Tier 3: Fantasy Capital Castle", "Grand sprawling city-fortress with multi-level districts"),
    ],
    default='TIER_3',
    update=on_property_updated
)
```

### 2. Auto-Update Callback (`on_property_updated`)
When any slider or toggle changes in the UI, `on_property_updated` triggers `bpy.ops.building.regenerate()` if `props.auto_update` is enabled.

### 3. UI Panels (`ui.py`)
Panels inherit from `bpy.types.Panel` and register under `space_type='VIEW_3D'`, `region_type='UI'`, and `category="Fantasy Building"`. Related properties are grouped in collapsible sub-panels:
- `VIEW3D_PT_fantasy_building_main`: Create, Regenerate, Preset selection.
- `VIEW3D_PT_fantasy_building_dimensions`: Footprint, width, depth, floors.
- `VIEW3D_PT_fantasy_building_fortifications`: Palisades, curtain walls, and castle citadels.
- `VIEW3D_PT_fantasy_building_estate`: Outbuildings, training yards, compound walls.

---

## 3. How to Add a New Modular Builder

To implement a new architectural component (e.g., an Alchemist Greenhouse):

### Step 1: Create the Generator Function
In `generator/accessories/greenhouse.py`:
```python
import math
from ..mesh_utils import create_box, create_beveled_box
from ..materials import MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_GLASS

def build_greenhouse_wing(bm, cx, cy, z_base, width=8.0, depth=6.0, height=4.5):
    """Constructs a glass-paneled timber greenhouse with planter benches."""
    # Build plinth, timber frame, and glass panes using standard canonical material indices
    ...
```

### Step 2: Register User Properties
In `properties.py`:
```python
has_greenhouse: BoolProperty(
    name="Alchemist Greenhouse",
    default=False,
    update=on_property_updated
)
```

### Step 3: Add to UI
In `ui.py` inside the appropriate panel (e.g. `VIEW3D_PT_fantasy_building_extensions`):
```python
layout.prop(props, "has_greenhouse")
```

### Step 4: Dispatch in Pipeline
In `generator/building.py` inside `build_architectural_accessories`:
```python
if getattr(props, 'has_greenhouse', False):
    from .accessories.greenhouse import build_greenhouse_wing
    build_greenhouse_wing(bm, ...)
```

---

## 4. Blender 5.2 Extension Deployment & Testing

Blender 5.2 executes add-ons directly from the extension directory:
`%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\blend_building_creator`

### Synchronizing Changes
Run the deployment script:
```powershell
python tools/deploy_addon.py
```
This automatically:
1. Bumps the patch version in `blender_manifest.toml`.
2. Copies files into the Blender 5.2 extension directory.
3. Builds an updated `blend_building_creator.zip`.

> [!IMPORTANT]
> **Purging Python Bytecode**: When testing live in Blender, cached `.pyc` files may cause Blender to run stale bytecode. Always purge `__pycache__` directories when modifying code:
> ```powershell
> Get-ChildItem -Path 'blend_building_creator' -Recurse -Filter '*.pyc' | Remove-Item -Force
> ```

---

## 5. Headless CLI Testing & Rendering

To verify generation without launching the Blender GUI, execute headless scripts:

### Running Headless Tests
```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup -b --python-expr "
import sys
sys.path.insert(0, r'd:\BlendBuildingCreator')
import bpy, blend_building_creator
blend_building_creator.register()
from blend_building_creator.presets import apply_preset
from blend_building_creator.generator.building import generate_building

mesh = bpy.data.meshes.new('Test')
obj = bpy.data.objects.new('Test', mesh)
bpy.context.collection.objects.link(obj)

props = bpy.context.scene.fantasy_building_settings
apply_preset(props, 'NASHERS_MANOR_T3')
generate_building(obj, props)
print(f'Vertices: {len(mesh.vertices)}, Polys: {len(mesh.polygons)}')
"
```

### Automated Headless Rendering
Refer to `scratch/render_castle_tiers.py` for headless camera tracking (`TRACK_TO`), sunlight configuration, EEVEE rendering, and artifact output.
