"""Generate and export one FBX for every building preset tier.

Run from the repository root with Blender, for example:
    blender --background --python tools/generate_all_fbx.py

The script intentionally uses the add-on's generator and preset definitions,
so command-line exports stay identical to exports started from the UI.
"""

import json
import os
import re
import sys
import traceback

try:
    import bpy
except ModuleNotFoundError as error:
    if error.name != "bpy":
        raise
    bpy = None

BLENDER_AVAILABLE = bpy is not None


TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

if BLENDER_AVAILABLE:
    from blend_building_creator.generator.building import generate_building
    from blend_building_creator.operators import get_props_dict
    from blend_building_creator.presets import BUILDING_FAMILIES, PRESETS, apply_preset
else:
    generate_building = None
    get_props_dict = None
    BUILDING_FAMILIES = ()
    PRESETS = {}
    apply_preset = None


def ensure_addon_registered():
    """Register the property group required by the procedural generator."""
    import blend_building_creator

    if not hasattr(bpy.types.Scene, "fantasy_building_settings"):
        blend_building_creator.register()


def export_name(family, tier_label):
    """Return the stable Family_Tier FBX basename."""
    family_name = re.sub(r"[^A-Za-z0-9]+", "_", family["name"]).strip("_")
    tier = re.sub(r"[^A-Za-z0-9]+", "", tier_label)
    return f"{family_name}_{tier}"


def jobs_for(category=None, family_id=None, tier=None):
    """Yield valid preset jobs, optionally filtered by category/family/tier."""
    for family in BUILDING_FAMILIES:
        if family_id is not None and family["id"] != family_id:
            continue
        categories = family.get("category", "OTHER")
        if isinstance(categories, str):
            categories = (categories,)
        if category is not None and category not in categories:
            continue
        for tier_label, preset_key, description in family["tiers"]:
            if tier is not None and tier_label != tier:
                continue
            if preset_key in PRESETS:
                yield family, tier_label, preset_key, description


def remove_objects(objects):
    for obj in reversed(list(objects)):
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def export_jobs(jobs, export_dir, keep_buildings=False):
    """Generate and export the supplied jobs. Returns the number exported."""
    ensure_addon_registered()
    export_dir = bpy.path.abspath(export_dir).rstrip("/\\")
    if not export_dir:
        raise ValueError("Export directory cannot be empty")
    os.makedirs(export_dir, exist_ok=True)

    props = bpy.context.scene.fantasy_building_settings
    old_auto = getattr(props, "auto_update", True)
    job_list = list(jobs)
    if not job_list:
        raise ValueError("No matching preset tiers were found")

    exported = 0
    bpy.context.window_manager.progress_begin(0, len(job_list))
    try:
        for index, (family, tier_label, preset_key, _description) in enumerate(job_list):
            basename = export_name(family, tier_label)
            print(f"[{index + 1}/{len(job_list)}] Generating {basename}...")
            mesh = bpy.data.meshes.new(f"{basename}_Mesh")
            root = bpy.data.objects.new(basename, mesh)
            bpy.context.collection.objects.link(root)
            root["is_fantasy_building"] = True
            created = [root]

            try:
                props.auto_update = False
                apply_preset(props, preset_key)
                generate_building(root, props)
                root["building_settings"] = json.dumps(get_props_dict(props))

                # Estate/castle presets can add parented outbuildings.
                for obj in list(bpy.data.objects):
                    if obj is root or obj.parent == root or (
                            obj.get("is_fantasy_building", False)
                            and obj.name.startswith(f"{root.name}_")):
                        if obj not in created:
                            created.append(obj)

                bpy.ops.object.select_all(action="DESELECT")
                for obj in created:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
                bpy.context.view_layer.objects.active = root

                bpy.ops.export_scene.fbx(
                    filepath=os.path.join(export_dir, f"{basename}.fbx"),
                    use_selection=True,
                    object_types={"MESH", "EMPTY", "ARMATURE"},
                    use_mesh_modifiers=True,
                    bake_space_transform=True,
                    mesh_smooth_type="EDGE",
                    add_leaf_bones=False,
                    apply_unit_scale=True,
                )
                filepath = os.path.join(export_dir, f"{basename}.fbx")
                mesh_objects = [obj for obj in created if obj.type == "MESH"]
                vertex_count = sum(len(obj.data.vertices) for obj in mesh_objects)
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                exported += 1
                print(
                    f"[{exported}/{len(job_list)}] Exported {basename}.fbx "
                    f"({file_size_mb:.2f} MB, {len(created)} objects, "
                    f"{vertex_count:,} vertices)"
                )
            finally:
                props.auto_update = old_auto
                if not keep_buildings:
                    remove_objects(created)
                bpy.context.window_manager.progress_update(index + 1)
    finally:
        props.auto_update = old_auto
        bpy.context.window_manager.progress_end()
        bpy.ops.object.select_all(action="DESELECT")

    return exported


def prompt_directory():
    default = bpy.path.abspath("//fbx_exports")
    print(f"\nFBX files will be written to: {default}")
    answer = input(f"Export directory [{default}]: ").strip()
    return answer or default


def run_safely(label, callback):
    """Keep command-line failures visible and save a traceback beside the tool."""
    try:
        if bpy is None:
            raise RuntimeError(
                "This script must be run by Blender, not the regular Python interpreter. "
                "Use: blender --background --python tools\\%s.py" % label
            )
        callback()
    except Exception:
        log_path = os.path.join(TOOLS_DIR, f"{label}_error.log")
        error = traceback.format_exc()
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(error)
        print(f"\nERROR: export failed. Full traceback saved to:\n{log_path}")
        print(error)
        pause_before_exit()
        raise


def pause_before_exit():
    """Keep a double-clicked Windows console open long enough to read errors."""
    if sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    elif os.name == "nt":
        os.system("pause")


def main():
    print("Generating one FBX for every valid T1/T2/T3 preset...")
    export_dir = prompt_directory()
    count = export_jobs(jobs_for(), export_dir)
    print(f"Completed: {count} FBX files exported to {bpy.path.abspath(export_dir)}")


if __name__ == "__main__":
    run_safely("generate_all_fbx", main)
