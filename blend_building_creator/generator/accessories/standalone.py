"""Standalone prop construction adapter (DRY).

Builds a single registry prop into its own Blender object using the exact
same builder the in-building furnishing composer uses. The operator and the
composer therefore can never drift apart: one builder, two contexts.
"""

import bmesh


def create_standalone_prop_mesh(obj, props, prop_key, scale=1.0, variant=''):
    """Fill ``obj.data`` with one prop centred at the local origin.

    ``scale`` uniformly scales the finished mesh. ``variant`` is an optional
    ``key=value`` string (e.g. ``"length=2.2"``) for power users; unknown
    keys are ignored so the UI never breaks.
    """
    from .prop_registry import build_prop
    from ..mesh_utils import apply_box_uvs, apply_organic_shading
    from ..materials import setup_building_material_slots, prune_material_slots_for_bmesh

    extra = _parse_variant(variant)
    bm = bmesh.new()
    try:
        build_prop(bm, prop_key, 0.0, 0.0, 0.0, 0.0, **extra)
        if abs(scale - 1.0) > 1e-6:
            for v in bm.verts:
                v.co *= scale
        apply_box_uvs(bm, scale=1.0)
        setup_building_material_slots(obj, props)
        # Drop every material slot this prop never touches: fewer draw calls.
        prune_material_slots_for_bmesh(obj, bm)
        bm.to_mesh(obj.data)
    finally:
        try:
            bm.free()
        except Exception:
            pass
    try:
        obj.data.update()
    except Exception:
        pass
    apply_organic_shading(obj)


def _parse_variant(text):
    out = {}
    if not text:
        return out
    for chunk in str(text).replace(';', ',').split(','):
        if '=' not in chunk:
            continue
        k, v = chunk.split('=', 1)
        k, v = k.strip(), v.strip()
        if not k:
            continue
        try:
            out[k] = float(v) if '.' in v else int(v)
        except ValueError:
            out[k] = v
    return out
