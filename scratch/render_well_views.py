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

mesh = bpy.data.meshes.new('WellMesh')
obj = bpy.data.objects.new('WellObj', mesh)
bpy.context.scene.collection.objects.link(obj)

props = bpy.context.scene.fantasy_building_settings
create_standalone_prop_mesh(obj, props, 'WELL')

# Setup camera & lighting
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 4.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(35))

fill_data = bpy.data.lights.new("Fill", type='POINT')
fill_data.energy = 220.0
fill_obj = bpy.data.objects.new("Fill", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

def render_view(loc, target, filename, fill_loc=(0, 0, 1)):
    cam_obj.location = loc
    direction = Vector(target) - Vector(loc)
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    fill_obj.location = fill_loc
    out_path = os.path.join(repo_root, "scratch", filename)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print("Rendered:", filename)

# View 1: Ridge close-up from side (matching user Image 1)
render_view((-1.4, 0.0, 2.15), (-0.6, 0.0, 2.05), "well_ridge_side_after.png", fill_loc=(-1.0, -0.4, 2.2))

# View 2: Roof underside looking up
render_view((-0.2, -0.9, 1.4), (0.0, 0.0, 1.95), "well_underside_after.png", fill_loc=(0.0, 0.0, 1.3))

# View 3: Eave corner
render_view((-0.9, -1.0, 1.8), (-0.6, -0.6, 1.7), "well_corner_after.png", fill_loc=(-0.5, -0.5, 1.9))

# View 4: Well lid and stone base
render_view((0.0, -1.8, 1.1), (0.0, 0.0, 0.65), "well_lid_after.png", fill_loc=(0.0, -1.2, 0.9))
