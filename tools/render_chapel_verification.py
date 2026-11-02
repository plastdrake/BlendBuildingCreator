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

    # --- 1. Render Estate Chapel (detached outbuilding with chapel archetype) ---
    clear_scene()
    setup_lighting()
    
    bpy.ops.building.create_fantasy_building()
    obj = bpy.context.active_object
    props = bpy.context.scene.fantasy_building_settings
    
    # Configure as the estate chapel (width=10.5, depth=6.5, 1 floor, CHAPEL archetype)
    props.building_shape = 'RECTANGLE'
    props.building_archetype = 'CHAPEL'
    props.num_floors = 1
    props.floor_height = 3.6
    props.width = 10.5
    props.depth = 6.5
    props.wall_thickness = 0.36
    props.has_cantilever = False
    props.has_foundation = True
    props.foundation_type = 'STONE'
    props.foundation_height = 0.75
    props.ground_floor_stone = False
    props.has_ceiling_beams = True
    props.has_stairs = False
    props.has_front_door = True
    props.has_front_steps = False
    props.door_width = 1.60
    props.door_height = 2.70
    props.door_shape = 'ARCHED'
    props.has_windows = True
    props.window_spacing = 2.2
    props.has_shutters = False
    props.has_timber_framing = False
    props.roof_style = 'GABLE'
    props.roof_orientation = 'LEFT_RIGHT'
    props.roof_height = 3.4
    props.roof_overhang = 0.65
    props.has_roof_shingles = True
    props.has_dormers = False
    props.has_chimney = False
    props.has_chapel_kit = True
    props.has_chapel_apse = False
    props.has_chapel_spire = True

    from blend_building_creator.generator.building import generate_building
    generate_building(obj, props)

    # Exterior render showing church spire, gable roof, and no apse
    target = bpy.data.objects.new("Target", None)
    target.location = (0.0, 0.0, 9.0)
    bpy.context.scene.collection.objects.link(target)
    
    cam_ext = setup_camera(loc=(-18.0, -24.0, 14.0), rot=(0, 0, 0))
    tt = cam_ext.constraints.new(type='TRACK_TO')
    tt.target = target
    tt.track_axis = 'TRACK_NEGATIVE_Z'
    tt.up_axis = 'UP_Y'
    bpy.context.view_layer.update()
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_chapel_exterior_spire.png")

    # Interior top-down render showing pews along length, altar, runner rug
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    z_cut = props.foundation_height + props.floor_height - 0.2
    del_faces = [f for f in bm.faces if any(v.co.z > z_cut for v in f.verts)]
    bmesh.ops.delete(bm, geom=del_faces, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    setup_camera(loc=(0.0, 0.0, 16.0), rot=(0, 0, 0))
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_chapel_interior_lengthwise.png")

    # Perspective view inside looking down the aisle toward the chantry altar (+X)
    setup_camera(loc=(-3.5, 0.0, 2.2), rot=(math.radians(82), 0, math.radians(-90)))
    render_view("C:/Users/Sebastian/.gemini/antigravity/brain/98386b09-c2ba-4aa3-b7fc-5db1b7169330/verify_chapel_altar_view.png")

if __name__ == '__main__':
    main()
