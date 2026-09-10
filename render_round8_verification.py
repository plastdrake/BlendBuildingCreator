import bpy
import math
import os

addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in bpy.utils.script_paths():
    import sys
    if addon_dir not in sys.path:
        sys.path.insert(0, addon_dir)

import blend_building_creator

# Ensure registered
try:
    blend_building_creator.register()
except Exception:
    pass

output_dir = os.path.join(addon_dir, "renders_round8")
os.makedirs(output_dir, exist_ok=True)

def setup_studio():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # Camera
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.lens = 42
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    
    # Sun light
    sun_data = bpy.data.lights.new("Sun", 'SUN')
    sun_data.energy = 4.0
    sun_data.color = (1.0, 0.95, 0.88)
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    sun_obj.rotation_euler = (math.radians(50), math.radians(15), math.radians(-35))
    bpy.context.scene.collection.objects.link(sun_obj)
    
    # Fill light
    fill_data = bpy.data.lights.new("Fill", 'SUN')
    fill_data.energy = 1.8
    fill_data.color = (0.75, 0.85, 1.0)
    fill_obj = bpy.data.objects.new("Fill", fill_data)
    fill_obj.rotation_euler = (math.radians(35), math.radians(-20), math.radians(145))
    bpy.context.scene.collection.objects.link(fill_obj)
    
    # Render settings
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderSettings') and 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    return cam_obj

def point_camera_at(cam_obj, target_pos):
    import mathutils
    direction = mathutils.Vector(target_pos) - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()

# --- 1. Dormer & Chimney Overview ---
setup_studio()
cam = bpy.context.scene.camera
bpy.ops.building.create_fantasy_building()
props = bpy.context.scene.fantasy_building_settings
props.has_dormers = True
props.has_chimney = True
props.has_roof_turret = False
props.width = 4.8
props.depth = 6.2
props.num_floors = 2
bpy.ops.building.regenerate()

# Position camera to look directly at the right roof slope showing dormer and chimney
cam.location = (7.5, 0.0, 8.5)
point_camera_at(cam, (1.8, 0.0, 7.2))
bpy.context.scene.render.filepath = os.path.join(output_dir, "01_dormer_and_chimney.png")
bpy.ops.render.render(write_still=True)
print("Rendered 01_dormer_and_chimney.png")

# --- 2. Turret on Roof Slope ---
props.has_roof_turret = True
props.roof_turret_pos_x = -0.55 # On left slope
props.roof_turret_pos_y = -0.10
props.roof_turret_scale = 1.0
bpy.ops.building.regenerate()

# Camera viewing the turret perched on the slope with its deep skirt
cam.location = (-6.5, -4.5, 9.5)
point_camera_at(cam, (-1.3, -0.3, 7.5))
bpy.context.scene.render.filepath = os.path.join(output_dir, "02_turret_slope_mounted.png")
bpy.ops.render.render(write_still=True)
print("Rendered 02_turret_slope_mounted.png")

# --- 3. Mini-Wing Outcrop (Ground Bay) ---
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.mini_wing_roof = 'LEAN_TO'
props.mini_wing_width = 2.4
props.mini_wing_depth = 1.6
bpy.ops.building.regenerate()

# Camera framing the left facade showing the entire mini-wing outcrop
cam.location = (-8.2, -4.8, 3.2)
point_camera_at(cam, (-2.4, 0.0, 1.6))
bpy.context.scene.render.filepath = os.path.join(output_dir, "03_mini_wing_ground.png")
bpy.ops.render.render(write_still=True)
print("Rendered 03_mini_wing_ground.png")

# --- 4. Timber Balcony & Pillared Overhang ---
props.has_balcony = True
props.balcony_side = 'FRONT'
props.balcony_floor = 2
props.balcony_width = 2.4
props.balcony_depth = 1.4

props.has_pillared_overhang = True
props.pillared_overhang_side = 'FRONT'
props.pillared_overhang_depth = 1.8
props.pillared_overhang_pillars = 3
props.pillared_overhang_style = 'TIMBER_STONE'
bpy.ops.building.regenerate()

# Camera framing the front facade showing the balcony above and pillared colonnade below
cam.location = (4.5, -9.5, 3.8)
point_camera_at(cam, (0.0, -3.1, 2.5))
bpy.context.scene.render.filepath = os.path.join(output_dir, "04_balcony_and_pillared_overhang.png")
bpy.ops.render.render(write_still=True)
print("Rendered 04_balcony_and_pillared_overhang.png")

# --- 5. Attic Interior View of Dormer Walk-in Alcove ---
# Add an interior light inside the attic
attic_light_data = bpy.data.lights.new("AtticLight", 'POINT')
attic_light_data.energy = 800.0
attic_light_data.color = (1.0, 0.95, 0.85)
attic_light_obj = bpy.data.objects.new("AtticLight", attic_light_data)
attic_light_obj.location = (0.8, -0.8, 6.8)
bpy.context.scene.collection.objects.link(attic_light_obj)

# Position camera inside attic looking outward toward dormer window alcove
cam.location = (0.1, -0.3, 6.1)
point_camera_at(cam, (1.6, -1.24, 6.2))
bpy.context.scene.render.filepath = os.path.join(output_dir, "05_attic_dormer_interior.png")
bpy.ops.render.render(write_still=True)
print("Rendered 05_attic_dormer_interior.png")

print("ALL VERIFICATION RENDERS COMPLETE!")

