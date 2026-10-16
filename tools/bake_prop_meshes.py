"""Bake the artist prop FBX files into a Python module.

Run inside Blender (clean context):

    blender --background --python tools/bake_prop_meshes.py

Writes blend_building_creator/generator/accessories/artisan_meshdata.py with
world-space vertices, polygon loops and per-loop UVs for each prop. The
builder then never needs bpy.ops.import_scene.fbx (which fails inside
property-update/depsgraph contexts and silently fell back before).
"""
import bpy
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPS_DIR = os.path.join(ROOT, 'blend_building_creator', 'props')
OUT_PATH = os.path.join(ROOT, 'blend_building_creator', 'generator',
                        'accessories', 'artisan_meshdata.py')

FBX_PROPS = {
    'fish': 'fish.fbx',
    'bread': 'bread.fbx',
    'meat': 'meat.fbx',
    'meat1': 'meat1.fbx',
    'anvil_tool': 'Anvil_Tool.fbx',
    'axe_tool': 'Axe_Tool.fbx',
    'hoe_tool': 'Hoe_Tool.fbx',
    'pickaxe_tool': 'Pickaxe_Tool.fbx',
}

# Canonical material slot indices (mirrors generator/materials.py). The artist
# FBX reference our own material names, so each baked face keeps its slot.
MAT_BY_NAME = {
    'M_Building_Stone': 0, 'M_Building_Plaster': 1, 'M_Building_Timber': 2,
    'M_Building_Floor': 3, 'M_Building_Shingles': 4, 'M_Building_Glass': 5,
    'M_Building_Iron': 6, 'M_Building_Wood': 7, 'M_Building_Cut_Stone': 8,
    'M_Building_Log': 9, 'M_Building_Log_End': 10,
    'M_Building_Plaster_Brick': 11, 'M_Building_Clock_Face': 12,
    'M_Building_Banner': 13, 'M_Building_Target': 14, 'M_Building_Hay': 15,
    'M_Building_Dirt': 16, 'M_Building_Sign': 17, 'M_Building_Rope': 18,
    'LanternEmissive': 19, 'M_Building_Tarp': 20, 'M_Building_Clay': 21,
    'M_Building_Fabric_White': 22, 'M_Building_Fabric_Red': 23,
    'M_Building_Fabric_Stitched': 24, 'M_Building_Leather': 25,
    'M_Building_Book_Paper': 26, 'M_Building_Wax': 27,
    'M_Building_Leather_2': 28, 'M_Building_Leather_3': 29,
    'M_Building_Rug_1': 30, 'M_Building_Rug_2': 31, 'M_Building_Rug_3': 32,
    'M_Building_Plant': 33, 'M_Building_Pumpkin': 34, 'M_Building_Bread': 35,
    'M_Building_Upholstery': 36, 'M_Building_Cloth_Linen': 37,
    'M_Building_Bottle_Glass': 38, 'M_Building_Pumpkin_Stem': 39,
    'M_Building_Open_Book': 40, 'M_Water': 41, 'M_Building_Cliffs': 42,
    'M_Building_Dungeon_Wall': 43, 'M_Building_Dungeon_Floor': 44,
    'M_Building_Dungeon_Beam': 45, 'M_Building_Canvas': 46,
    'M_Building_Fish': 47, 'M_Building_Meat': 48, 'M_Building_Bread_FBX': 49,
    'M_Building_Gold': 50, 'M_Building_Silver': 51,
    'M_Building_Terracotta_Brick': 52,
}


def _canon_index(name):
    """Canonical slot index for an FBX material name (ignores .001 / _T1)."""
    if not name:
        return None
    base = name.split('.')[0]
    if len(base) > 3 and base[-3] == '_' and base[-2] == 'T' and base[-1] in '123':
        base = base[:-3]
    return MAT_BY_NAME.get(base)


def bake_one(path):
    before = set(bpy.data.objects[:])
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]

    verts, polys, poly_mats = [], [], []
    for o in new:
        if o.type != 'MESH':
            continue
        me = o.data
        if not me.vertices or not me.polygons:
            continue
        M = o.matrix_world
        off = len(verts)
        for v in me.vertices:
            verts.append(tuple(round(c, 5) for c in (M @ v.co)))
        uv_data = me.uv_layers[0].data if len(me.uv_layers) else None
        slot_idx = [_canon_index(m.name if m else None) for m in me.materials]
        for poly in me.polygons:
            loops = []
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index + off
                uv = (tuple(round(c, 5) for c in uv_data[li].uv)
                      if uv_data is not None else (0.0, 0.0))
                loops.append((vi, uv))
            polys.append(loops)
            si = (slot_idx[poly.material_index]
                  if poly.material_index < len(slot_idx) else None)
            poly_mats.append(-1 if si is None else si)

    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    if not verts or not polys:
        return None
    has_mats = any(m >= 0 for m in poly_mats)
    return {'verts': verts, 'polys': polys,
            'poly_mats': poly_mats if has_mats else None}


all_data = {}
for key, fname in FBX_PROPS.items():
    p = os.path.join(PROPS_DIR, fname)
    if not os.path.exists(p):
        print('MISSING', p)
        continue
    item = bake_one(p)
    if item:
        all_data[key] = item
        print(f'BAKED {key}: {len(item["verts"])} verts '
              f'{len(item["polys"])} polys '
              f'mats={"yes" if item["poly_mats"] else "no"}')
    else:
        print('EMPTY', key)

lines = [
    '"""Baked artist prop meshes (auto-generated; do not edit by hand).',
    '',
    'Regenerate with:  blender --background --python tools/bake_prop_meshes.py',
    '',
    'Each entry stores world-space vertices and per-loop (vertex_index, uv)',
    'so the builder needs no FBX import at generation time. Optional',
    '"poly_mats" holds a canonical material slot index per polygon (-1 = use',
    'the builder-supplied default).',
    '"""',
    '',
    'PROP_MESHES = {',
]
for key, item in all_data.items():
    lines.append(f'    {key!r}: {{')
    lines.append('        "verts": [')
    for v in item['verts']:
        lines.append(f'            ({v[0]!r}, {v[1]!r}, {v[2]!r}),')
    lines.append('        ],')
    lines.append('        "polys": [')
    for poly in item['polys']:
        loops = ', '.join(f'({vi!r}, ({uv[0]!r}, {uv[1]!r}))'
                          for vi, uv in poly)
        lines.append(f'            [{loops}],')
    lines.append('        ],')
    if item['poly_mats']:
        lines.append('        "poly_mats": [')
        pm = item['poly_mats']
        for i in range(0, len(pm), 24):
            lines.append('            ' + ', '.join(repr(x) for x in pm[i:i + 24]) + ',')
        lines.append('        ],')
    lines.append('    },')
lines.append('}')
lines.append('')

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('WROTE', OUT_PATH)
