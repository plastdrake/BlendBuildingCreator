import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Euler

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.images):
        for item in list(col):
            col.remove(item)

def setup_camera(loc, rot=(0,0,0)):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 28
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
        bg.inputs[0].default_value = (0.75, 0.8, 0.85, 1.0)
        bg.inputs[1].default_value = 1.0

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 2.8
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    sun_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(35))
    bpy.context.scene.collection.objects.link(sun_obj)

def render_view(filepath, width=960, height=540):
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.filepath = filepath
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"Render saved to {filepath}", flush=True)

def main():
    sys.path.insert(0, ".")
    import blend_building_creator
    blend_building_creator.register()

    clear_scene()
    setup_lighting()

    # Fast EEVEE settings
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except Exception:
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except Exception:
            pass
    if hasattr(scene, 'eevee'):
        for attr in ('taa_render_samples', 'max_samples', 'sampling_render'):
            try:
                setattr(scene.eevee, attr, 16)
            except Exception:
                pass

    # Create Nasher Castle (Tier 3) directly with preset settings
    props = scene.fantasy_building_settings
    from blend_building_creator.presets import apply_preset
    apply_preset(props, 'NASHERS_MANOR_T3')
    bpy.ops.building.create_fantasy_building()
    print("Preset NASHERS_MANOR_T3 created.", flush=True)

    brain_dir = "C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330"

    # View 1: Middle Gate close-up framed to capture full towers with banners
    # Middle gate is at cx=0.0, cy=-19.5, z_ground approx 3.0m, tower_h approx 7.5m -> top at ~10.5m
    target_mid = bpy.data.objects.new("TargetMid", None)
    target_mid.location = (0.0, -19.5, 8.5)
    bpy.context.scene.collection.objects.link(target_mid)

    cam2 = setup_camera(loc=(0.0, -36.0, 11.5))
    tt2 = cam2.constraints.new(type='TRACK_TO')
    tt2.target = target_mid
    tt2.track_axis = 'TRACK_NEGATIVE_Z'
    tt2.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    bpy.context.scene.camera = cam2
    render_view(os.path.join(brain_dir, "verify_gate_banners_fixed_mid_gate.png"))

    print("ALL GATE BANNER VERIFICATION RENDERS COMPLETE!", flush=True)

if __name__ == '__main__':
    main()
