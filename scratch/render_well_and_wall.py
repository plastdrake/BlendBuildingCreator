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

props = bpy.context.scene.fantasy_building_settings

# 1. Render Well Views
mesh = bpy.data.meshes.new('WellMesh')
well_obj = bpy.data.objects.new('WellObj', mesh)
bpy.context.scene.collection.objects.link(well_obj)
create_standalone_prop_mesh(well_obj, props, 'WELL')

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 45
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 4.5
sun_data.color = (1.0, 0.97, 0.92)
sun_obj = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(40))

fill_data = bpy.data.lights.new("Fill", type='POINT')
fill_data.energy = 300.0
fill_obj = bpy.data.objects.new("Fill", fill_data)
bpy.context.scene.collection.objects.link(fill_obj)

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 24
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720

def render_to(loc, target, filename, fill_loc=(0, 0, 1.2)):
    cam_obj.location = loc
    direction = Vector(target) - Vector(loc)
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    fill_obj.location = fill_loc
    out_path = os.path.join(repo_root, "scratch", filename)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print("Rendered:", filename)

# View A: 3/4 Well Overview showing timber pillars from ground up, crank, iron brackets, roof
render_to((1.8, -2.0, 1.6), (0.0, 0.0, 1.0), "well_grounded_posts.png", fill_loc=(1.2, -1.0, 1.5))

# View B: Close-up of the +X post covering the stone cylinder seam
render_to((1.4, -0.6, 0.45), (0.60, 0.0, 0.35), "well_post_seam_close.png", fill_loc=(1.2, -0.4, 0.6))

# View C: Well front elevation
render_to((0.0, -2.6, 1.1), (0.0, 0.0, 0.95), "well_front_elevation.png", fill_loc=(0.0, -1.8, 1.1))

# 2. Render Building Wall to inspect large stone masonry on buildings
for obj in list(bpy.context.scene.objects):
    if obj != cam_obj and obj != sun_obj and obj != fill_obj:
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='TAVERN_T1')

# Position camera for close facade view of the stone lower floor
cam_data.lens = 32
render_to((4.5, -8.0, 2.5), (0.5, -2.0, 1.8), "building_stone_wall_new.png", fill_loc=(3.0, -5.0, 2.5))
print("ALL RENDERS COMPLETED SUCCESSFULLY")
