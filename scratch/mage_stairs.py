import os, sys, math
import bpy
from mathutils import Vector
REPO = r"D:\BlendBuildingCreator"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass
import blend_building_creator
blend_building_creator.register()
for o in list(bpy.context.scene.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.building.create_fantasy_building()
bpy.ops.building.apply_preset(preset_key="MAGE_TOWER_T2")
props = bpy.context.scene.fantasy_building_settings
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
scn.cycles.samples = 24
scn.render.resolution_x = 900
scn.render.resolution_y = 700
w = scn.world or bpy.data.worlds.new("W"); scn.world = w; w.use_nodes = True
w.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.65,0.68,0.75,1)

sun = bpy.data.lights.new("S", 'SUN'); sun.energy = 2.5
so = bpy.data.objects.new("S", sun); scn.collection.objects.link(so)
so.rotation_euler = (math.radians(55), 0, math.radians(30))
pt = bpy.data.lights.new("P", 'POINT'); pt.energy = 300
po = bpy.data.objects.new("P", pt); scn.collection.objects.link(po)
po.location = (0, 0, 2.5)

cam_data = bpy.data.cameras.new("C"); cam_data.lens = 24
cam = bpy.data.objects.new("C", cam_data); scn.collection.objects.link(cam)
scn.camera = cam

z0 = (props.foundation_height if props.has_foundation else 0.5) + 0.14
R = max(3.8, props.width * 0.46)
r_wall_in = R - props.wall_thickness - 0.02
lvl_h = props.floor_height
topz = z0 + lvl_h
target = (r_wall_in * math.cos(math.radians(95.0)),
          r_wall_in * math.sin(math.radians(95.0)), topz - 0.4)
cam.location = Vector((0.0, 0.0, topz - 0.6)) + Vector((-0.6, -1.1, 0.3))
d = Vector(target) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scn.render.filepath = os.path.join(REPO, "scratch", "new_previews", "MAGE_STAIRS_TOP.png")
bpy.ops.render.render(write_still=True)
print("done", flush=True)
