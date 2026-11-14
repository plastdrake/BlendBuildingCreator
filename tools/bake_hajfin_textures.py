"""Bake the Hajfin procedural shaders down to plain, engine-ready image textures.

The Hajfin material set is authored with stylised node graphs (noise washes,
anti-repetition washes, procedural flaking paint, ...).  Those look great in
Blender but do NOT survive an FBX / glTF export into Unreal or Unity, which only
understand image textures.

This tool renders every Hajfin surface material once onto a flat 0..1 UV plane
and writes the result into ``blend_building_creator/textures/`` as
``<key>_diffuse.png`` plus a matching ``<key>_normal.png``.  The generator then
builds those materials as a single Image Texture -> Base Color (plus a normal
map), which exports cleanly and is trivial to recreate in any engine.

Usage:
    blender --factory-startup --background --python tools/bake_hajfin_textures.py
    blender --factory-startup --background --python tools/bake_hajfin_textures.py -- --size 2048 --only driftwood,shingles

Re-run this whenever a Hajfin shader is tweaked.
"""

import os
import sys
import math
import argparse

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import bpy
import bmesh

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from blend_building_creator.generator import materials as M  # noqa: E402

TEX_DIR = os.path.join(repo_root, "blend_building_creator", "textures")


# ---------------------------------------------------------------------------
# Bake jobs: (key, factory, fallback colour, roughness)
# ---------------------------------------------------------------------------
def _jobs():
    return [
        ("hajfin_driftwood",
         lambda: M._procedural_driftwood("BAKE_Driftwood", color=(0.58, 0.36, 0.20, 1.0)),
         (0.58, 0.36, 0.20, 1.0), 0.82),
        ("hajfin_timber",
         lambda: M._procedural_hajfin_timber("BAKE_Timber", color=(0.15, 0.09, 0.05, 1.0)),
         (0.15, 0.09, 0.05, 1.0), 0.80),
        ("hajfin_bone",
         lambda: M._procedural_bone("BAKE_Bone"),
         (0.84, 0.82, 0.75, 1.0), 0.68),
        ("hajfin_shingles_ivory",
         lambda: M._procedural_bone_shingles("BAKE_Shingles_Ivory", color=(0.86, 0.82, 0.74, 1.0)),
         (0.86, 0.82, 0.74, 1.0), 0.72),
        ("hajfin_shingles_coral",
         lambda: M._procedural_bone_shingles("BAKE_Shingles_Coral", color=(0.72, 0.32, 0.24, 1.0)),
         (0.72, 0.32, 0.24, 1.0), 0.72),
        ("hajfin_deck",
         lambda: M._procedural_hajfin_deck("BAKE_Deck", color=(0.28, 0.28, 0.29, 1.0)),
         (0.28, 0.28, 0.29, 1.0), 0.82),
        ("hajfin_reef_stone",
         lambda: M._procedural_rough_reef_stone("BAKE_ReefStone", color=(0.28, 0.30, 0.32, 1.0)),
         (0.28, 0.30, 0.32, 1.0), 0.92),
        ("hajfin_painted_red",
         lambda: M._procedural_painted_planks("BAKE_PaintedRed",
                                                  color=(0.62, 0.18, 0.13, 1.0),
                                                  paint_coverage=0.74),
         (0.62, 0.18, 0.13, 1.0), 0.78),
        ("hajfin_painted_blue",
         lambda: M._procedural_painted_planks("BAKE_PaintedBlue",
                                                  color=(0.30, 0.38, 0.50, 1.0),
                                                  paint_coverage=0.66),
         (0.30, 0.38, 0.50, 1.0), 0.78),
        ("hajfin_salvaged",
         lambda: M._procedural_salvaged_planks("BAKE_Salvaged"),
         (0.62, 0.52, 0.38, 1.0), 0.84),
    ]


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------
def _clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def _make_plane():
    """A 1x1 quad with a clean 0..1 UV map, centred on the origin."""
    me = bpy.data.meshes.new("BakePlane")
    bm = bmesh.new()
    verts = [bm.verts.new(v) for v in ((-0.5, -0.5, 0.0), (0.5, -0.5, 0.0),
                                       (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0))]
    face = bm.faces.new(verts)
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for loop, uv in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv_layer].uv = uv
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("BakePlane", me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _setup_render(scene, samples=48):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.render.bake.margin = 8
    try:
        scene.render.bake.use_selected_to_active = False
    except Exception:
        pass


def _bake_target_node(mat, image, location=(-1500, -900)):
    """Create + activate an image texture node used as the bake target."""
    tree = mat.node_tree
    for n in tree.nodes:
        n.select = False
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.location = location
    node.select = True
    tree.nodes.active = node
    return node


def _emission_from_base_color(mat):
    """Swap the surface to an Emission fed by the BSDF base colour so that an
    EMIT bake captures exactly the stylised albedo (including all procedural
    washes) with no lighting baked in."""
    tree = mat.node_tree
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if out is None or bsdf is None:
        return False
    base = bsdf.inputs.get("Base Color")
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (600, 400)
    if base is not None and base.is_linked:
        tree.links.new(base.links[0].from_socket, emission.inputs["Color"])
    elif base is not None:
        emission.inputs["Color"].default_value = base.default_value
    emission.inputs["Strength"].default_value = 1.0
    for link in list(out.inputs["Surface"].links):
        tree.links.remove(link)
    tree.links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return True


def _restore_bsdf(mat):
    tree = mat.node_tree
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if out is None or bsdf is None:
        return
    for link in list(out.inputs["Surface"].links):
        tree.links.remove(link)
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def _save_image(image, path):
    image.filepath_raw = path
    image.file_format = 'PNG'
    image.save()
    print("   wrote", path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--only", type=str, default="")
    args = parser.parse_args(argv)

    only = set(s.strip() for s in args.only.split(",") if s.strip())

    _clear_scene()
    scene = bpy.context.scene
    _setup_render(scene)
    os.makedirs(TEX_DIR, exist_ok=True)

    plane = _make_plane()
    bpy.context.view_layer.objects.active = plane
    plane.select_set(True)

    for key, factory, fallback, roughness in _jobs():
        if only and key not in only and not any(key.startswith(o) for o in only):
            continue
        print("=== baking", key)
        try:
            mat = factory()
        except Exception as exc:
            print("   material creation failed:", exc)
            continue

        # Replace any material already on the plane
        plane.data.materials.clear()
        plane.data.materials.append(mat)

        size = args.size
        diffuse = bpy.data.images.new(key + "_diffuse", width=size, height=size, alpha=False)

        # ---- albedo ------------------------------------------------------
        if not _emission_from_base_color(mat):
            print("   no BSDF/output, skipping")
            continue
        _bake_target_node(mat, diffuse)
        bpy.ops.object.bake(type='EMIT')
        _save_image(diffuse, os.path.join(TEX_DIR, key + "_diffuse.png"))

        # ---- normal -------------------------------------------------------
        _restore_bsdf(mat)
        normal = bpy.data.images.new(key + "_normal", width=size, height=size, alpha=False)
        # Non-colour image so the normal data is not gamma-corrected
        normal.colorspace_settings.name = 'Non-Color'
        _bake_target_node(mat, normal)
        try:
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
            _save_image(normal, os.path.join(TEX_DIR, key + "_normal.png"))
        except Exception as exc:
            print("   normal bake skipped:", exc)

    print("Done.")


if __name__ == "__main__":
    main()
