import bpy
import math
import os
import sys
from mathutils import Vector, Euler

sys.path.insert(0, r"d:\BlendBuildingCreator")
import blend_building_creator
blend_building_creator.register()

def setup_render_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
        
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    
    world = bpy.data.worlds.new("VerificationWorld")
    scene.world = world
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.75, 0.82, 0.90, 1.0)
        bg.inputs['Strength'].default_value = 0.9
        
    # Sun light
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.5
    sun_data.color = (1.0, 0.96, 0.90)
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = Euler((math.radians(50), math.radians(20), math.radians(-40)), 'XYZ')
    
    # Fill light
    fill_data = bpy.data.lights.new(name="Fill", type='SUN')
    fill_data.energy = 1.5
    fill_data.color = (0.80, 0.88, 1.0)
    fill_obj = bpy.data.objects.new(name="Fill", object_data=fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = Euler((math.radians(45), 0, math.radians(140)), 'XYZ')

    # Interior room point light
    int_light = bpy.data.lights.new(name="IntLight", type='POINT')
    int_light.energy = 300.0
    int_light.color = (1.0, 0.92, 0.82)
    int_obj = bpy.data.objects.new(name="IntLight", object_data=int_light)
    scene.collection.objects.link(int_obj)
    int_obj.location = (0.0, 0.0, 1.8)

    # Camera
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 45
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return cam_obj

def render_view(cam_obj, loc, rot, output_path):
    cam_obj.location = loc
    cam_obj.rotation_euler = rot
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

out_dir = r"C:\Users\Sebastian\.gemini\antigravity-ide\brain\1d5ba5c4-fa5e-48fb-b2f3-d255ee369c46"

# Setup scene
cam = setup_render_scene()

# -------------------------------------------------------------
# SCENE 1: Dormer & Roof Horn verification
# -------------------------------------------------------------
bpy.ops.building.create_fantasy_building()
b_obj = bpy.context.active_object
props = bpy.context.scene.fantasy_building_settings
props.width = 6.0
props.depth = 6.0
props.num_floors = 2
props.has_dormers = True
props.roof_style = 'SWAY'
props.has_roof_shingles = True
bpy.ops.building.regenerate()

# View 1: Dormer front view showing window frame, solid header, spandrel, and cheek walls
render_view(
    cam,
    loc=(-4.8, 1.05, 8.2),
    rot=(math.radians(78), 0, math.radians(-90)),
    output_path=os.path.join(out_dir, "round8_view1_dormer_closeup.png")
)

# View 2: Downhill slope view in front of dormer showing continuous shingle coverage (no hole)
render_view(
    cam,
    loc=(-5.2, -1.2, 9.4),
    rot=(math.radians(68), 0, math.radians(-65)),
    output_path=os.path.join(out_dir, "round8_view2_dormer_roof_slope.png")
)

# View 3: Main roof corner eave showing removed horn (clean bargeboard verge termination)
render_view(
    cam,
    loc=(-5.0, -5.0, 7.2),
    rot=(math.radians(75), 0, math.radians(-45)),
    output_path=os.path.join(out_dir, "round8_view3_roof_corner_nohorn.png")
)

# -------------------------------------------------------------
# SCENE 2: Outcrop mini-wing, Balcony, and Pillared Overhang
# -------------------------------------------------------------
props.has_dormers = False
props.has_stairs = False # Wide open interior for walk-in view
props.has_cantilever = True
props.has_mini_wing = True
props.mini_wing_side = 'LEFT'
props.mini_wing_floor = 'GROUND'
props.mini_wing_width = 2.4
props.mini_wing_depth = 1.6
props.mini_wing_roof = 'LEAN_TO'

props.has_balcony = True
props.balcony_side = 'BACK'
props.balcony_floor = 2
props.balcony_width = 2.4
props.balcony_depth = 1.3

props.has_pillared_overhang = True
props.pillared_overhang_side = 'FRONT'
props.pillared_overhang_depth = 1.8
props.pillared_overhang_pillars = 3

bpy.ops.building.regenerate()

# View 4: Outcrop Mini-Wing exterior full view showing sealed wedge under lean-to roof
render_view(
    cam,
    loc=(-7.5, -3.8, 3.2),
    rot=(math.radians(74), 0, math.radians(-62)),
    output_path=os.path.join(out_dir, "round8_view4_miniwing_exterior.png")
)

# View 5: Pillared overhang & upper-floor jetting with correct planar knee braces
render_view(
    cam,
    loc=(4.2, -7.5, 3.2),
    rot=(math.radians(78), 0, math.radians(28)),
    output_path=os.path.join(out_dir, "round8_view5_pillared_overhang_jetting.png")
)

# View 6: Balcony with correct diagonal corbel struts under joists
render_view(
    cam,
    loc=(2.2, 6.8, 3.6),
    rot=(math.radians(82), 0, math.radians(160)),
    output_path=os.path.join(out_dir, "round8_view6_balcony_corbels_door.png")
)

# View 7: Interior walk-in view through timber archway into mini-wing
render_view(
    cam,
    loc=(-0.8, 0.0, 1.4),
    rot=(math.radians(90), 0, math.radians(-90)),
    output_path=os.path.join(out_dir, "round8_view7_interior_walkin_miniwing.png")
)

# View 8: Balcony doorway head-on view from balcony looking towards house wall
render_view(
    cam,
    loc=(0.0, 5.2, 4.4),
    rot=(math.radians(80), 0, math.radians(180)),
    output_path=os.path.join(out_dir, "round8_view8_balcony_door_closeup.png")
)

print("All 8 verification views rendered successfully!")
