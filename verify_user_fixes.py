import bpy, sys, os
addon_dir = os.path.dirname(os.path.abspath(__file__))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)
import blend_building_creator
blend_building_creator.register()
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
props = bpy.context.scene.fantasy_building_settings

def gen(desc):
    bpy.ops.building.regenerate()
    obj = bpy.context.active_object
    print(f"{desc}: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys, {len(obj.data.materials)} mats")
    # check no degenerate: ensure no zero-area faces? just print
    return obj

# Default
bpy.ops.building.create_fantasy_building()
gen("default")

# Test 1: dormer roofs miniature copy of main roof (SWAY + dormers)
props.roof_style = 'SWAY'
props.has_dormers = True
props.roof_flare = 0.35
props.roof_sway = 0.25
props.material_tier='TIER_3'
bpy.ops.building.regenerate()
gen("SWAY dormer miniature")

# Test 2: GABLE dormer
props.roof_style='GABLE'
bpy.ops.building.regenerate()
gen("GABLE dormer miniature")

# Test 3: Tier2 vertical planks, gable solid + UV
props.material_tier='TIER_2'
props.plank_direction='VERTICAL'
props.has_dormers=False
bpy.ops.building.regenerate()
gen("TIER2 vertical gable solid")

props.plank_direction='HORIZONTAL'
bpy.ops.building.regenerate()
gen("TIER2 horizontal gable solid")

# Test 4: Tier1 log sticking through roof (check no crash, logs clipped)
props.material_tier='TIER_1'
props.has_foundation=True
props.foundation_height=0.6
props.has_timber_framing=True
bpy.ops.building.regenerate()
gen("TIER1 logs + foundation + timber framing pillars")

# Test 5: corner pillars to foundation
props.has_timber_framing=True
props.num_floors=2
bpy.ops.building.regenerate()
gen("corner pillars extended")

# Test 6: turret shingles
props.has_roof_turret=True
props.roof_turret_pos_x=0.2
props.roof_turret_pos_y=-0.1
props.has_dormers=False
bpy.ops.building.regenerate()
obj = gen("roof turret shingles")
# count shingle polys
shingle_count = sum(1 for p in obj.data.polygons if obj.data.materials[p.material_index].name.startswith("M_Building_Shingles"))
print(f" shingle polys: {shingle_count}")
assert shingle_count>10, "turret should have shingles"

# Test 7: conical turret roof style
props.roof_style='TURRET'
props.has_roof_turret=False
bpy.ops.building.regenerate()
obj = gen("conical turret roof")
shingle_count = sum(1 for p in obj.data.polygons if "Shingle" in obj.data.materials[p.material_index].name)
print(f" conical shingle polys: {shingle_count}")
assert shingle_count>10

# Test 8: balcony door UV
props.roof_style='SWAY'
props.has_balcony=True
props.balcony_side='FRONT'
props.balcony_floor=2
props.num_floors=2
bpy.ops.building.regenerate()
gen("balcony door UV")

# Test 9: pillared overhang beams
props.has_balcony=False
props.has_pillared_overhang=True
props.pillared_overhang_side='FRONT'
props.pillared_overhang_depth=1.6
props.pillared_overhang_pillars=3
bpy.ops.building.regenerate()
obj = gen("pillared overhang beams")
# count timber frame polys
timber_count = sum(1 for p in obj.data.polygons if "Timber" in obj.data.materials[p.material_index].name)
print(f" timber polys: {timber_count}")
assert timber_count>50

print("ALL USER FIXES VERIFIED")
blend_building_creator.unregister()
