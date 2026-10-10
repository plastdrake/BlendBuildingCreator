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
}


def bake_one(path):
    before = set(bpy.data.objects[:])
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    items = []
    for o in new:
        if o.type != 'MESH':
            continue
        me = o.data
        if not me.vertices or not me.polygons:
            continue
        M = o.matrix_world
        verts = [tuple(round(c, 5) for c in (M @ v.co)) for v in me.vertices]
        uv_data = me.uv_layers[0].data if len(me.uv_layers) else None
        polys = []
        for poly in me.polygons:
            loops = []
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv = (tuple(round(c, 5) for c in uv_data[li].uv)
                      if uv_data is not None else (0.0, 0.0))
                loops.append((vi, uv))
            polys.append(loops)
        items.append({'verts': verts, 'polys': polys})
    for o in new:
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
    return items


all_data = {}
for key, fname in FBX_PROPS.items():
    p = os.path.join(PROPS_DIR, fname)
    if not os.path.exists(p):
        print('MISSING', p)
        continue
    items = bake_one(p)
    if items:
        all_data[key] = items[0]
        print(f'BAKED {key}: {len(items[0]["verts"])} verts '
              f'{len(items[0]["polys"])} polys')
    else:
        print('EMPTY', key)

lines = [
    '"""Baked artist prop meshes (auto-generated; do not edit by hand).',
    '',
    'Regenerate with:  blender --background --python tools/bake_prop_meshes.py',
    '',
    'Each entry stores world-space vertices and per-loop (vertex_index, uv)',
    'so the builder needs no FBX import at generation time.',
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
    lines.append('    },')
lines.append('}')
lines.append('')

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('WROTE', OUT_PATH)
