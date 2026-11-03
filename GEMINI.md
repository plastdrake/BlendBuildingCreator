# AI Guidelines & Development Protocol

## 1. Always Deploy the Add-on After Changes
Whenever any modifications, bug fixes, or additions are made to `blend_building_creator/`:
- **Run the deploy script immediately**:
  ```powershell
  python tools/deploy_addon.py
  ```
- **Why this is critical**:
  - `tools/deploy_addon.py` automatically bumps the version in `blend_building_creator/blender_manifest.toml`. Because Blender caches extension modules in memory when the version string does not change, bumping the version and copying the files ensures that Blender loads the fresh code rather than stale cached Python bytecode.
  - It automatically deploys the updated add-on code directly into the active user extension directories across all installed Blender versions (e.g. 4.3, 4.4, 5.0, 5.1, 5.2).
  - It packages the updated distribution zip archive (`blend_building_creator.zip`).

## 2. Commit and Push at Appropriate Intervals
- **Frequency**:
  - Commit and push to `origin/main` (or the current branch) at appropriate, logical milestone intervals (e.g., after completing a coherent task, fixing a batch of related issues, or finishing a milestone).
  - Do not accumulate large, uncommitted diffs across disparate features without pushing.
- **Pre-commit Checklist**:
  1. Verify code syntax across all modified files using `python -m py_compile <files...>`.
  2. Run `python tools/deploy_addon.py` to bump the manifest version and deploy.
  3. Verify with `git status` and `git diff` that only intended files are staged (no scratch scripts or temporary files).
  4. Commit with a clear, concise, descriptive message detailing the specific features or fixes.
  5. Push immediately to `origin/main` (`git push origin main`).

## 3. Code & Architecture Integrity
- Preserve existing comments, docstrings, and procedural architecture unless explicitly asked to modify or refactor them.
- Ensure all coordinate frames, procedural offsets, materials, and asset placements maintain consistency across building tiers (Tier 1 wood/wattle, Tier 2 timber frame/plaster, Tier 3 stone/citadel).
