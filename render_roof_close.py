"""Close roof shingle detail shot."""
import os, bpy, math, sys, mathutils

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.num_floors = 2
bpy.ops.building.regenerate()

sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_data.energy = 3.2
sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(55), math.radians(10), math.radians(30))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.6, 0.72, 0.85, 1.0)
    bg.inputs["Strength"].default_value = 1.0

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 750

cam_data = bpy.data.cameras.new(name="Cam")
cam_data.lens = 60
cam_obj = bpy.data.objects.new(name="Cam", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (5.0, -6.0, 8.0)
direction = mathutils.Vector((0.0, -1.5, 8.2)) - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam_obj

scene.render.filepath = os.path.join(script_dir, "preview_roof_close.png")
bpy.ops.render.render(write_still=True)
print("DONE_ROOF_CLOSE")
