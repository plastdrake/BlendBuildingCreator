import bpy
import bmesh
import math
from mathutils import Vector, Euler

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.images):
        for item in list(col):
            col.remove(item)

def setup_camera(loc, rot):
    cam_data = bpy.data.cameras.new("Cam")
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = loc
    cam_obj.rotation_euler = rot
    bpy.context.scene.camera = cam_obj
    return cam_obj

def setup_lighting():
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.7, 0.75, 0.8, 1.0)
        bg.inputs[1].default_value = 1.0

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 2.5
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    sun_obj.rotation_euler = (math.radians(45), math.radians(20), math.radians(35))
    bpy.context.scene.collection.objects.link(sun_obj)

def render_view(filepath, width=1280, height=720):
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.filepath = filepath
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"Render saved to {filepath}")

def main():
    import sys
    sys.path.insert(0, ".")
    import blend_building_creator
    blend_building_creator.register()

    clear_scene()
    setup_lighting()

    # Create Nasher Castle (Tier 3)
    bpy.ops.building.create_fantasy_building()
    obj = bpy.context.active_object
    props = bpy.context.scene.fantasy_building_settings

    bpy.ops.building.apply_preset(preset_key='NASHERS_MANOR_T3')
    print("Preset NASHERS_MANOR_T3 applied.")

    # 1. View of the Keep Facade showing the Grand Noble Lord's Balcony with draped banners
    # Keep center is at (0.0, 40.0, 14.0). Front wall is at y = 32.0. Balcony is on Floor 4 at z = 30.0.
    cam_target_keep = bpy.data.objects.new("TargetKeep", None)
    cam_target_keep.location = (0.0, 32.0, 30.0)
    bpy.context.scene.collection.objects.link(cam_target_keep)

    cam1 = setup_camera(loc=(0.0, 4.0, 32.0), rot=(0, 0, 0))
    tt1 = cam1.constraints.new(type='TRACK_TO')
    tt1.target = cam_target_keep
    tt1.track_axis = 'TRACK_NEGATIVE_Z'
    tt1.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    bpy.context.scene.camera = cam1
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_nasher_t3_grand_balcony.png")

    # Angled perspective of the Grand Balcony
    cam2 = setup_camera(loc=(-18.0, 12.0, 34.0), rot=(0, 0, 0))
    tt2 = cam2.constraints.new(type='TRACK_TO')
    tt2.target = cam_target_keep
    tt2.track_axis = 'TRACK_NEGATIVE_Z'
    tt2.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    bpy.context.scene.camera = cam2
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_nasher_t3_grand_balcony_angle.png")

    # 2. View of the Castle Gatehouse and flanking wall towers with banners
    # Middle gate is at cx=0.0, cy=-19.5, z_ground approx 3.0m
    cam_target_gate = bpy.data.objects.new("TargetGate", None)
    cam_target_gate.location = (0.0, -19.5, 6.0)
    bpy.context.scene.collection.objects.link(cam_target_gate)

    cam3 = setup_camera(loc=(0.0, -42.0, 10.0), rot=(0, 0, 0))
    tt3 = cam3.constraints.new(type='TRACK_TO')
    tt3.target = cam_target_gate
    tt3.track_axis = 'TRACK_NEGATIVE_Z'
    tt3.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    bpy.context.scene.camera = cam3
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_nasher_t3_gate_banners.png")

if __name__ == '__main__':
    main()
