"""
Doorways, windows, and decorative opening accessories for stylized fantasy buildings.
Produces walkthrough-ready doorways with adjustable door leaf angles, deep reveals,
sills, shutters, flower boxes, and iron lanterns.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder
from .materials import MAT_INDEX_TIMBER, MAT_INDEX_DOOR, MAT_INDEX_GLASS, MAT_INDEX_IRON, MAT_INDEX_STONE, MAT_INDEX_SHINGLES

def build_door_assembly(bm, center_x, y_front, z_base, wall_thickness=0.3, door_w=1.0, door_h=2.2, door_angle_deg=45.0):
    """
    Builds the door frame, casing, openable door panel, iron hinges, and ring handle.
    door_angle_deg controls how open the door leaf is (0 = closed, 90 = fully open into interior).
    """
    frame_thick = 0.12
    frame_depth = wall_thickness + 0.06
    
    # 1. Door Frame Jambs (Left & Right)
    create_beveled_box(
        bm,
        size=(frame_thick, frame_depth, door_h),
        location=(center_x - (door_w * 0.5 + frame_thick * 0.5), y_front, z_base + door_h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    create_beveled_box(
        bm,
        size=(frame_thick, frame_depth, door_h),
        location=(center_x + (door_w * 0.5 + frame_thick * 0.5), y_front, z_base + door_h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    # Lintel (Top header beam)
    create_beveled_box(
        bm,
        size=(door_w + frame_thick * 2.4, frame_depth + 0.04, frame_thick),
        location=(center_x, y_front, z_base + door_h + frame_thick * 0.5),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )
    # Stone threshold
    create_beveled_box(
        bm,
        size=(door_w + frame_thick * 2.0, frame_depth + 0.08, 0.08),
        location=(center_x, y_front, z_base + 0.04),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.015
    )
    
    # 2. Door Panel (Hinged on the left side)
    hinge_x = center_x - door_w * 0.5 + 0.02
    hinge_y = y_front - wall_thickness * 0.2
    
    door_leaf_w = door_w - 0.04
    door_leaf_h = door_h - 0.05
    door_leaf_t = 0.06
    
    # Rotation matrix around the hinge pivot
    ang_rad = math.radians(door_angle_deg)
    # In interior direction (+Y into room)
    rot_mat = Euler((0.0, 0.0, ang_rad), 'XYZ').to_matrix().to_4x4()
    
    # Center of leaf relative to hinge
    leaf_local_center = Vector((door_leaf_w * 0.5, 0.0, door_leaf_h * 0.5))
    rotated_center = rot_mat @ leaf_local_center
    leaf_world_center = Vector((hinge_x, hinge_y, z_base + 0.05)) + rotated_center
    
    create_beveled_box(
        bm,
        size=(door_leaf_w, door_leaf_t, door_leaf_h),
        location=leaf_world_center,
        rotation=(0.0, 0.0, ang_rad),
        mat_index=MAT_INDEX_DOOR,
        bevel_amount=0.01
    )
    
    # Horizontal iron strap hinges (upper and lower)
    for hz_factor in [0.22, 0.78]:
        hz = z_base + 0.05 + door_leaf_h * hz_factor
        strap_len = door_leaf_w * 0.65
        strap_local_c = Vector((strap_len * 0.5, -door_leaf_t * 0.5 - 0.006, hz_factor * door_leaf_h))
        strap_world_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ strap_local_c)
        create_box(
            bm,
            size=(strap_len, 0.012, 0.06),
            location=strap_world_c,
            rotation=(0.0, 0.0, ang_rad),
            mat_index=MAT_INDEX_IRON
        )
        
    # Iron ring handle
    handle_local_c = Vector((door_leaf_w * 0.82, -door_leaf_t * 0.5 - 0.02, door_leaf_h * 0.48))
    handle_world_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ handle_local_c)
    create_cylinder(
        bm,
        radius=0.045,
        height=0.02,
        segments=8,
        location=handle_world_c,
        rotation=(math.pi * 0.5, 0.0, ang_rad),
        mat_index=MAT_INDEX_IRON
    )

def build_front_steps(bm, center_x, y_front, z_base, num_steps=3, step_w=1.6, step_d=0.35, step_h=0.18):
    """
    Creates solid grounded fantasy stone steps leading up to the front door.
    Each step extends solidly down to ground level (Z=0) so no steps float.
    """
    for i in range(num_steps):
        # i=0 is top step just outside door; i=num_steps-1 is bottom step on ground
        cur_w = step_w + (num_steps - 1 - i) * 0.14
        cur_y = y_front - (i + 1) * step_d + step_d * 0.5
        top_z = z_base - i * step_h
        step_total_h = max(0.08, top_z) # extends solidly down to ground level (Z = 0)
        cz = step_total_h * 0.5
        create_beveled_box(
            bm,
            size=(cur_w, step_d + 0.06, step_total_h),
            location=(center_x, cur_y, cz),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.025
        )

def build_window_assembly(bm, center=(0.0, 0.0, 0.0), size=(0.9, 1.2), wall_thickness=0.3,
                          normal_axis='-Y', has_shutters=True, has_flower_box=False):
    """
    Builds a stylized fantasy window with deep timber casing, projecting sills,
    glass pane, muntin crossbars, optional shutters and flower box.
    The casing dimensions fit precisely into the rough wall opening 'size'.
    """
    cx, cy, cz = center
    win_w, win_h = size
    frame_thick = 0.07
    sill_thick = 0.08
    
    # Rotation angle based on wall orientation
    if normal_axis == '-Y':       # Facing Front (-Y exterior)
        facing_angle = 0.0
    elif normal_axis == '+Y':     # Facing Back (+Y exterior)
        facing_angle = math.pi
    elif normal_axis == '-X':     # Facing Left (-X exterior)
        facing_angle = -math.pi * 0.5
    else:                         # '+X' Facing Right (+X exterior)
        facing_angle = math.pi * 0.5

    rot_mat = Euler((0.0, 0.0, facing_angle), 'XYZ').to_matrix().to_4x4()
    base_loc = Vector((cx, cy, cz))
    
    def to_world(loc, rot=(0.0, 0.0, 0.0)):
        w_loc = base_loc + (rot_mat @ Vector(loc))
        w_rot = (rot[0], rot[1], rot[2] + facing_angle)
        return w_loc, w_rot

    # 1. Wooden Casing fits cleanly inside the wall cutout (win_w, win_h)
    casing_depth = wall_thickness + 0.06
    jamb_h = win_h - frame_thick - sill_thick
    jamb_cz = (frame_thick - sill_thick) * 0.5
    
    # Left & Right jambs (sitting flush on the left/right inner edges of the cutout)
    for side in [-1, 1]:
        lx = side * (win_w * 0.5 - frame_thick * 0.5)
        w_loc, w_rot = to_world((lx, 0.0, jamb_cz))
        create_beveled_box(bm, size=(frame_thick, casing_depth, jamb_h), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        
    # Top Lintel (slightly wider than cutout to cap the exterior trim)
    w_loc, w_rot = to_world((0.0, 0.0, win_h * 0.5 - frame_thick * 0.5))
    create_beveled_box(bm, size=(win_w + 0.12, casing_depth + 0.04, frame_thick), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    
    # Bottom Sill (projects outward on exterior side for rain drip)
    sill_depth = casing_depth + 0.10
    w_loc, w_rot = to_world((0.0, -0.03, -win_h * 0.5 + sill_thick * 0.5))
    create_beveled_box(bm, size=(win_w + 0.14, sill_depth, sill_thick), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    
    # 2. Glass Pane
    glass_w = win_w - frame_thick * 2.0 - 0.02
    glass_h = jamb_h - 0.02
    w_loc, w_rot = to_world((0.0, 0.0, jamb_cz))
    create_box(bm, size=(glass_w, 0.02, glass_h), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_GLASS)
    
    # 3. Wooden Muntin Bars (Crossbars in glass)
    w_loc, w_rot = to_world((0.0, 0.0, jamb_cz))
    create_box(bm, size=(glass_w, 0.03, 0.035), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER)
    create_box(bm, size=(0.035, 0.03, glass_h), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER)
    
    # 4. Stylized Wooden Shutters (angled open into space so they never intersect wall timbers)
    if has_shutters:
        shutter_w = win_w * 0.44
        shutter_h = win_h * 0.94
        shutter_t = 0.032
        open_ang = math.radians(52.0)
        cos_a = math.cos(open_ang)
        sin_a = math.sin(open_ang)
        
        # Left and Right shutters hinged at casing outer edges
        for side in [-1, 1]:
            hx = side * (win_w * 0.5 + 0.01)
            hy = -wall_thickness * 0.5 - 0.02
            
            # Vector pointing along the open shutter blade
            dx = side * cos_a
            dy = -sin_a
            rot_z = math.atan2(dy, dx)
            
            sx = hx + dx * (shutter_w * 0.5)
            sy = hy + dy * (shutter_w * 0.5)
            
            w_loc, w_rot = to_world((sx, sy, jamb_cz), rot=(0.0, 0.0, rot_z))
            create_beveled_box(
                bm,
                size=(shutter_w, shutter_t, shutter_h),
                location=w_loc,
                rotation=w_rot,
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.008
            )
            
            # Stylized iron hinge straps on the shutter
            for hz in [-shutter_h * 0.32, shutter_h * 0.32]:
                strap_loc, strap_rot = to_world((sx, sy - side * 0.002, jamb_cz + hz), rot=(0.0, 0.0, rot_z))
                create_box(
                    bm,
                    size=(shutter_w * 0.75, shutter_t + 0.012, 0.035),
                    location=strap_loc,
                    rotation=strap_rot,
                    mat_index=MAT_INDEX_IRON
                )
            
    # 5. Flower Box
    if has_flower_box:
        box_w = win_w + 0.08
        box_d = 0.22
        box_h = 0.18
        sy = -wall_thickness * 0.5 - box_d * 0.5 - 0.04
        sz = -win_h * 0.5 - box_h * 0.5 + sill_thick * 0.3
        w_loc, w_rot = to_world((0.0, sy, sz))
        # Wooden planter box
        create_beveled_box(bm, size=(box_w, box_d, box_h), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        # Foliage inside planter
        w_loc_g, w_rot_g = to_world((0.0, sy, sz + box_h * 0.38))
        create_beveled_box(bm, size=(box_w - 0.04, box_d - 0.04, 0.09), location=w_loc_g, rotation=w_rot_g, mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.015)

def build_iron_lantern(bm, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)):
    """
    Creates a stylized hanging iron lantern bracket with a warm glowing lantern.
    """
    cx, cy, cz = location
    # Bracket arm from wall
    create_box(bm, size=(0.04, 0.35, 0.04), location=(cx, cy - 0.15, cz), mat_index=MAT_INDEX_IRON)
    # Diagonal brace
    create_box(bm, size=(0.03, 0.22, 0.03), location=(cx, cy - 0.10, cz - 0.08), rotation=(-0.78, 0.0, 0.0), mat_index=MAT_INDEX_IRON)
    # Lantern body
    ly = cy - 0.30
    lz = cz - 0.18
    # Glowing glass core
    create_cylinder(bm, radius=0.08, height=0.18, segments=6, location=(cx, ly, lz), mat_index=MAT_INDEX_GLASS)
    # Iron cap & base
    create_cylinder(bm, radius=0.10, height=0.04, segments=6, location=(cx, ly, lz + 0.10), mat_index=MAT_INDEX_IRON)
    create_cylinder(bm, radius=0.10, height=0.04, segments=6, location=(cx, ly, lz - 0.10), mat_index=MAT_INDEX_IRON)
