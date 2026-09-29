import sys, os, math
import bpy
from mathutils import Vector

repo_root = r'd:\BlendBuildingCreator'
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

from blend_building_creator.generator.accessories.standalone import create_standalone_prop_mesh

mesh = bpy.data.meshes.new('BedMesh')
obj = bpy.data.objects.new('BedObj', mesh)
bpy.context.scene.collection.objects.link(obj)

props = bpy.context.scene.fantasy_building_settings
create_standalone_prop_mesh(obj, props, 'BED')

# Camera
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (-1.8, -2.5, 1.7)
target = Vector((0.0, 0.0, 0.45))
direction = target - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

# Sun
sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 4.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(52), math.radians(24), math.radians(38))

# Fill light
fill_data = bpy.data.lights.new("Fill", type='POINT')
fill_data.energy = 220.0
fill_obj = bpy.data.objects.new("Fill", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.location = (1.6, -1.2, 1.9)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640
out_path = os.path.join(repo_root, "scratch", "final_bed_render.png")
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("Rendered successfully to:", out_path)
