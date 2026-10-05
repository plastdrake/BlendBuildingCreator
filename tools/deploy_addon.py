import os
import re
import shutil
import zipfile

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
appdata = os.environ.get("APPDATA", "")
blender_root = os.path.join(appdata, "Blender Foundation", "Blender")
src_dir = os.path.join(repo_root, "blend_building_creator")

# Bump the extension version on every deploy. Blender keeps already-imported
# extension modules in memory when the version string is unchanged, so a
# same-version file copy can silently keep serving stale Python until a full
# restart. A new version makes the update unambiguous.
_manifest = os.path.join(src_dir, "blender_manifest.toml")
try:
    _text = open(_manifest, "r", encoding="utf-8").read()
    _m = re.search(r'(?m)^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', _text)
    if _m:
        _new = "%s.%s.%d" % (_m.group(1), _m.group(2), int(_m.group(3)) + 1)
        _text = _text[:_m.start()] + 'version = "%s"' % _new + _text[_m.end():]
        open(_manifest, "w", encoding="utf-8").write(_text)
        print("Bumped extension version to %s" % _new)
except Exception as _e:
    print("Version bump skipped:", _e)

targets = [
    os.path.join(blender_root, "5.2", "extensions", "user_default", "blend_building_creator"),
]

# Legacy add-on copies with the same module name conflict with the extension and
# make only one of the two work. Remove them so a single copy is loaded.
legacy_dupes = [
    os.path.join(blender_root, "5.2", "scripts", "addons", "blend_building_creator"),
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
