import sys, os, math
import bpy

repo_root = r'd:\BlendBuildingCreator'
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception as e:
    print("Register exception (may already be registered):", e)

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Generate TAVERN_T1
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key='TAVERN_T1')

props = bpy.context.scene.fantasy_building_settings
props.door_angle = 35.0
bpy.ops.building.regenerate()

# Setup Lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.6, 0.75, 0.9, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings (Cycles CPU)
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 640

# Camera framing front entrance, porch, sign, furniture, lanterns, flower boxes
cam_data = bpy.data.cameras.new(name="FrontCamera")
cam_data.lens = 28
cam_obj = bpy.data.objects.new(name="FrontCamera", object_data=cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (5.5, -9.5, 3.8)
cam_obj.rotation_euler = (math.radians(72), 0, math.radians(30))
bpy.context.scene.camera = cam_obj

out_img = os.path.join(repo_root, "scratch", "tavern_test.png")
bpy.context.scene.render.filepath = out_img
bpy.ops.render.render(write_still=True)
print("TEST RENDER COMPLETE:", out_img)
sys.exit(0)
