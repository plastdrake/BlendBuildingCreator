"""
Renders comprehensive verification images for the new fixes:
1. preview_overhang_soffit.png (under overhang view: solid timber soffit, zero gaps)
2. preview_chimney_fixed.png (chimney cap: perfectly centered, subtle 2-deg tilt)
3. preview_front_steps_grounded.png (entrance steps: solid stone blocks down to Z=0)
4. preview_window_aligned.png (window: casing flush with rough cutout, no wall poke)
5. preview_spiral_3floors.png (3-floor spiral stairs: continuous 360 deg circulation)
6. preview_floor_seam.png (interior floor corner: zero gap line along wall)
"""

import os
import sys
import math
import bpy
from mathutils import Vector

# Clear scene
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import blend_building_creator
try:
    blend_building_creator.register()
except Exception:
    pass

# Lighting setup
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(45))

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.7, 0.75, 0.85, 1.0)
    bg_node.inputs["Strength"].default_value = 1.0

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 24
    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(loc)
    direction = (Vector(target) - cam_obj.location).normalized()
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam_obj
    
    out_path = os.path.join(addon_dir, out_name)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED: {out_name}")
    # Remove camera
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

# Create Tavern building
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="TAVERN")
props = bpy.context.scene.fantasy_building_settings
props.door_angle = 40.0
bpy.ops.building.regenerate()

# 1. View looking up at the cantilever overhang & soffit from below
render_camera_at("CamOverhang", (-2.2, -4.2, 1.2), (-1.8, -2.8, 3.2), "preview_overhang_soffit.png")

# 2. View looking at the chimney cap
render_camera_at("CamChimney", (5.5, 3.5, 11.2), (2.5, 1.2, 9.8), "preview_chimney_fixed.png")

# 3. View looking at front steps from side/ground level
render_camera_at("CamSteps", (2.0, -4.5, 0.4), (0.0, -3.2, 0.5), "preview_front_steps_grounded.png")

# 4. View looking straight at ground-floor window
render_camera_at("CamWindow", (2.0, -4.2, 1.8), (2.0, -2.7, 1.8), "preview_window_aligned.png")

# 5. View looking at interior floor seam along wall
int_light = bpy.data.lights.new(name="FloorLight", type='POINT')
int_light.energy = 80.0
int_light.color = (1.0, 0.9, 0.8)
int_light_obj = bpy.data.objects.new(name="FloorLight", object_data=int_light)
bpy.context.scene.collection.objects.link(int_light_obj)
int_light_obj.location = (0.0, 0.0, 1.5)

render_camera_at("CamFloorSeam", (0.5, -0.5, 1.8), (-2.8, 1.0, 0.72), "preview_floor_seam.png")

# 6. Wizard Tower with 3 floors of spiral stairs
bpy.ops.building.apply_preset(preset_key="WIZARD_TOWER")
props.num_floors = 3
bpy.ops.building.regenerate()

int_light_obj.location = (0.0, 0.0, 4.5)
render_camera_at("CamSpiral", (0.2, -0.8, 4.2), (-1.2, 0.8, 4.0), "preview_spiral_3floors.png")

print("ALL VERIFICATION VIEWS FINISHED!")
