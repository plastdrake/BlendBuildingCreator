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

# Camera positioned low, looking up from beneath the bed
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 38
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (1.9, 0.9, -0.7)
target = Vector((-0.2, 0.0, 0.28))
direction = target - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

# Lights: upward ground fill light to illuminate underside
fill_data = bpy.data.lights.new("UpFill", type='POINT')
fill_data.energy = 320.0
fill_obj = bpy.data.objects.new("UpFill", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.location = (0.2, 0.1, -0.5)

# Sun for ambient environment
sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(30))

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640
out_path = os.path.join(repo_root, "scratch", "bed_underneath_render.png")
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print("Rendered underneath view successfully to:", out_path)
