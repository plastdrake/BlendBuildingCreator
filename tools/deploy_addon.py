import os
import shutil
import zipfile

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
appdata = os.environ.get("APPDATA", "")
blender_root = os.path.join(appdata, "Blender Foundation", "Blender")
src_dir = os.path.join(repo_root, "blend_building_creator")

targets = [
    os.path.join(blender_root, "5.2", "extensions", "user_default", "blend_building_creator"),
    os.path.join(blender_root, "5.1", "extensions", "user_default", "blend_building_creator"),
    os.path.join(blender_root, "5.0", "extensions", "user_default", "blend_building_creator"),
    os.path.join(blender_root, "4.4", "extensions", "user_default", "blend_building_creator"),
]

# Legacy add-on copies with the same module name conflict with the extension and
# make only one of the two work. Remove them so a single copy is loaded.
legacy_dupes = [
    os.path.join(blender_root, "5.2", "scripts", "addons", "blend_building_creator"),
    os.path.join(blender_root, "5.1", "scripts", "addons", "blend_building_creator"),
    os.path.join(blender_root, "5.0", "scripts", "addons", "blend_building_creator"),
    os.path.join(blender_root, "4.4", "scripts", "addons", "blend_building_creator"),
]

for d in legacy_dupes:
    if os.path.exists(d):
        shutil.rmtree(d)
        print(f"Removed duplicate legacy add-on: {d}")

for t in targets:
    parent = os.path.dirname(t)
    if os.path.exists(parent):
        if os.path.exists(t):
            shutil.rmtree(t)
        shutil.copytree(src_dir, t)
        print(f"Successfully updated: {t}")

zip_path = os.path.join(repo_root, "blend_building_creator.zip")
if os.path.exists(zip_path):
    os.remove(zip_path)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root:
            continue
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, os.path.dirname(src_dir))
            zipf.write(full_path, rel_path)

print(f"Successfully packaged: {zip_path}")
