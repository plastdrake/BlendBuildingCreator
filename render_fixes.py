import bpy
import math
import os
import sys
sys.path.insert(0, r"d:\BlendBuildingCreator")
from mathutils import Vector

def setup_render_scene():
    scene = bpy.context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.film_transparent = False
    
    # World lighting
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.08, 0.09, 0.11, 1.0)
        bg.inputs["Strength"].default_value = 1.0
        
    # Sun light
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.5
    sun_data.color = (1.0, 0.95, 0.88)
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(-40))
    
    # Fill light
    fill_data = bpy.data.lights.new(name="Fill", type='SUN')
    fill_data.energy = 1.2
    fill_data.color = (0.7, 0.85, 1.0)
    fill_obj = bpy.data.objects.new(name="Fill", object_data=fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(35), math.radians(-30), math.radians(140))
    
    # Camera
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return scene, cam_obj

def render_to(cam_obj, loc, rot, output_path):
    cam_obj.location = loc
    cam_obj.rotation_euler = rot
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"

# 1. Render Multi-Plank Door & Louvered Shutters & Carriage Lantern
scene, cam = setup_render_scene()
import blend_building_creator
blend_building_creator.register()
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.door_angle = 35.0
props.has_lanterns = True
props.has_shutters = True
bpy.ops.building.regenerate()

render_to(
    cam,
    loc=(0.6, -5.5, 2.2),
    rot=(math.radians(78), 0.0, math.radians(8)),
    output_path=os.path.join(out_dir, "preview_multi_plank_door_detailed.png")
)

# 2. Render Tier 1 Log End Concentric Growth Rings
props.material_tier = 'TIER_1'
bpy.ops.building.regenerate()
render_to(
    cam,
    loc=(3.2, -3.5, 1.2),
    rot=(math.radians(75), 0.0, math.radians(45)),
    output_path=os.path.join(out_dir, "preview_tier1_log_end_rings.png")
)

# 3. Render Windmill Connected via Timber Axle Housing Dormer
bpy.ops.building.apply_preset(preset_key='INDUSTRIAL_WINDMILL')
render_to(
    cam,
    loc=(-3.5, -9.5, 9.5),
    rot=(math.radians(60), 0.0, math.radians(-22)),
    output_path=os.path.join(out_dir, "preview_windmill_connected.png")
)

# 4. Render Blacksmith Lean-to Grounded Stone Workshop
bpy.ops.building.apply_preset(preset_key='BLACKSMITH')
render_to(
    cam,
    loc=(8.5, -3.0, 3.2),
    rot=(math.radians(68), 0.0, math.radians(68)),
    output_path=os.path.join(out_dir, "preview_blacksmith_stone_ground.png")
)

# 5. Render Hoist Beam with Corrected Knee Brace & Forged J-Hook
bpy.ops.building.apply_preset(preset_key='WAREHOUSE')
props.has_hoist_beam = True
bpy.ops.building.regenerate()
render_to(
    cam,
    loc=(-2.0, -8.2, 9.0),
    rot=(math.radians(62), 0.0, math.radians(-15)),
    output_path=os.path.join(out_dir, "preview_hoist_beam_functional_hook.png")
)

# 6. Render Wizard Tower Spiral Staircase Clearance (Top-Down Interior View)
bpy.ops.building.apply_preset(preset_key='WIZARD_TOWER')
# Hide roof temporarily to get a clear downward interior view into the stairwell
obj = bpy.context.active_object
render_to(
    cam,
    loc=(0.0, -0.6, 7.8),
    rot=(math.radians(18), 0.0, 0.0),
    output_path=os.path.join(out_dir, "preview_spiral_stairs_radial_clearance.png")
)
print("All verification renders completed!")
