import bpy
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Clear existing objects in scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
blend_building_creator.register()

print("="*60, flush=True)
print("MEASURING TAVERN PRESET BOUNDS", flush=True)
print("="*60, flush=True)

res = bpy.ops.building.create_fantasy_building()
obj = bpy.context.active_object

for preset_key in ['TAVERN_T1', 'TAVERN_T2', 'TAVERN_T3']:
    bpy.ops.building.apply_preset(preset_key=preset_key)
    
    verts = obj.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    
    span_x = max_x - min_x
    span_y = max_y - min_y
    span_z = max_z - min_z
    
    fits_20x20 = (min_x >= -10.0 and max_x <= 10.0 and min_y >= -10.0 and max_y <= 10.0)
    
    print(f"\n--- {preset_key} ---", flush=True)
    print(f"X range: [{min_x:.2f}, {max_x:.2f}] (Span: {span_x:.2f}m)", flush=True)
    print(f"Y range: [{min_y:.2f}, {max_y:.2f}] (Span: {span_y:.2f}m)", flush=True)
    print(f"Z range: [{min_z:.2f}, {max_z:.2f}] (Height: {span_z:.2f}m)", flush=True)
    print(f"Fits in 20m x 20m plot ([-10, 10]): {fits_20x20}", flush=True)
    if not fits_20x20:
        exceeds = []
        if min_x < -10.0: exceeds.append(f"X min by {abs(min_x) - 10.0:.2f}m")
        if max_x > 10.0: exceeds.append(f"X max by {max_x - 10.0:.2f}m")
        if min_y < -10.0: exceeds.append(f"Y min by {abs(min_y) - 10.0:.2f}m")
        if max_y > 10.0: exceeds.append(f"Y max by {max_y - 10.0:.2f}m")
        print(f"EXCEEDS BOUNDS: {', '.join(exceeds)}", flush=True)

print("\nDone measuring.", flush=True)
