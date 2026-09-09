"""
Render verification views for Round 6 user feedback:
1. preview_stair_balusters_aligned.png (close-up matching user Image 1)
2. preview_newel_post_clean.png (close-up matching user Image 2)
3. preview_roof_shingles_symmetric.png (top-down matching user Image 3)
4. preview_portal_walkthrough_clean.png (interior archway matching user Image 4)
"""

import os
import sys
import math
import bpy
from mathutils import Vector

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

# Lighting
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.5
sun_data.color = (1.0, 0.98, 0.94)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(50))

# Stair fill light
stair_light = bpy.data.lights.new(name="StairLight", type='POINT')
stair_light.energy = 350.0
stair_light.color = (1.0, 0.96, 0.90)
stair_light_obj = bpy.data.objects.new(name="StairLight", object_data=stair_light)
bpy.context.scene.collection.objects.link(stair_light_obj)
stair_light_obj.location = (-0.2, -0.6, 2.2)

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
try:
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.8, 0.82, 0.88, 1.0)
        bg_node.inputs["Strength"].default_value = 1.0
except Exception:
    pass

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 720

def render_camera_at(name, loc, target, out_name):
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 32
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
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)

bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings

# --- 1 & 2: STAIR BALUSTERS AND NEWEL POST ---
props.building_shape = 'RECTANGLE'
props.num_floors = 2
props.has_stairs = True
props.stair_style = 'STRAIGHT'
bpy.ops.building.regenerate()

# View matching Image 1: Side view of stair run, stringer beam, and vertical balusters
render_camera_at("CamStairBalusters", (-0.4, 0.2, 1.3), (-1.5, 0.4, 1.6), "preview_stair_balusters_aligned.png")

# View matching Image 2: Extreme close-up of bottom newel post meeting handrail
render_camera_at("CamNewelPost", (-0.9, -0.6, 1.2), (-1.45, -0.65, 0.95), "preview_newel_post_clean.png")

# --- 3: SYMMETRICAL ROOF SHINGLES (matching Image 3) ---
props.roof_style = 'SWAY'
props.has_roof_shingles = True
props.has_chimney = True
bpy.ops.building.regenerate()

# Top-down view looking directly down at the roof ridge from above
render_camera_at("CamTopRoof", (0.0, -1.0, 14.5), (0.0, 0.0, 7.5), "preview_roof_shingles_symmetric.png")

# --- 4: CLEAN INTERIOR PORTAL IN L-SHAPE (matching Image 4) ---
props.building_shape = 'L_SHAPE'
props.wing_side = 'RIGHT'
props.wing_width = 3.2
props.wing_depth = 3.0
props.has_timber_framing = True
props.timber_diagonals = True
bpy.ops.building.regenerate()

# View standing inside the main hall looking directly through the portal into the wing
render_camera_at("CamPortal", (0.5, 1.2, 1.6), (1.5, -3.0, 1.5), "preview_portal_walkthrough_clean.png")

print("ROUND 6 VERIFICATION COMPLETE!")
