"""
Doorways, windows, and decorative opening accessories for stylized fantasy buildings.
Produces walkthrough-ready doorways with adjustable door leaf angles, deep reveals,
sills, shutters, flower boxes, and iron lanterns.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone
from .materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_DOOR, MAT_INDEX_GLASS,
    MAT_INDEX_IRON, MAT_INDEX_STONE, MAT_INDEX_SHINGLES, MAT_INDEX_WOOD
)

def build_door_assembly(bm, center_x, y_front, z_base, wall_thickness=0.3, door_w=1.0, door_h=2.2, door_angle_deg=45.0, door_shape='AUTO', ground_floor_stone=True):
    """
    Builds the door frame, casing, openable door panel, iron hinges, and ring handle.
    door_angle_deg controls how open the door leaf is (0 = closed, 90 = fully open into interior).
    door_shape: 'AUTO', 'ARCHED', or 'SQUARE'.
    """
    frame_thick = 0.12
    frame_depth = wall_thickness + 0.06
    is_arched = (door_shape == 'ARCHED') or (door_shape == 'AUTO' and ground_floor_stone and door_w < 1.6)
    
    if is_arched:
        R_in = door_w * 0.5
        R_out = R_in + 0.22
        z_spring = z_base + door_h - R_in
        
        # 1. Stone threshold
        create_beveled_box(
            bm,
            size=(door_w + 0.55, frame_depth + 0.08, 0.09),
            location=(center_x, y_front, z_base + 0.045),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.018
        )
        
        # 2. Quoin Stone Jambs (Stacked alternating ashlar blocks)
        jamb_h = max(0.4, z_spring - (z_base + 0.09))
        num_blocks = max(3, int(round(jamb_h / 0.32)))
        block_step = jamb_h / num_blocks
        
        for side_sign in [-1, 1]:
            for b in range(num_blocks):
                bz = z_base + 0.09 + (b + 0.5) * block_step
                bw = 0.24 if (b % 2 == 0) else 0.18
                bx = center_x + side_sign * (R_in + bw * 0.5)
                create_beveled_box(
                    bm,
                    size=(bw, frame_depth + 0.03, block_step - 0.008),
                    location=(bx, y_front, bz),
                    mat_index=MAT_INDEX_STONE,
                    bevel_amount=0.015
                )
                
        # 3. Radial Stone Arch with 7 voussoirs and prominent keystone
        num_v = 7
        for i in range(num_v):
            a0 = i * math.pi / num_v
            a1 = (i + 1) * math.pi / num_v
            is_key = (i == num_v // 2)
            r_out_cur = R_out + (0.05 if is_key else 0.0)
            y_pop = -0.02 if is_key else 0.0
            
            yf_f = y_front - frame_depth * 0.5 + y_pop
            yf_b = y_front + frame_depth * 0.5
            
            v_in0_f  = bm.verts.new(Vector((center_x + R_in * math.cos(a0), yf_f, z_spring + R_in * math.sin(a0))))
            v_in1_f  = bm.verts.new(Vector((center_x + R_in * math.cos(a1), yf_f, z_spring + R_in * math.sin(a1))))
            v_out1_f = bm.verts.new(Vector((center_x + r_out_cur * math.cos(a1), yf_f, z_spring + r_out_cur * math.sin(a1))))
            v_out0_f = bm.verts.new(Vector((center_x + r_out_cur * math.cos(a0), yf_f, z_spring + r_out_cur * math.sin(a0))))
            
            v_in0_b  = bm.verts.new(Vector((center_x + R_in * math.cos(a0), yf_b, z_spring + R_in * math.sin(a0))))
            v_in1_b  = bm.verts.new(Vector((center_x + R_in * math.cos(a1), yf_b, z_spring + R_in * math.sin(a1))))
            v_out1_b = bm.verts.new(Vector((center_x + r_out_cur * math.cos(a1), yf_b, z_spring + r_out_cur * math.sin(a1))))
            v_out0_b = bm.verts.new(Vector((center_x + r_out_cur * math.cos(a0), yf_b, z_spring + r_out_cur * math.sin(a0))))
            
            for f_verts in [
                [v_in0_f, v_out0_f, v_out1_f, v_in1_f],
                [v_in0_b, v_in1_b, v_out1_b, v_out0_b],
                [v_in0_f, v_in1_f, v_in1_b, v_in0_b],
                [v_out0_f, v_out0_b, v_out1_b, v_out1_f],
                [v_in0_f, v_in0_b, v_out0_b, v_out0_f],
                [v_in1_f, v_out1_f, v_out1_b, v_in1_b]
            ]:
                f = bm.faces.new(f_verts)
                f.material_index = MAT_INDEX_STONE
                
        # Inner timber door casing
        create_beveled_box(
            bm, size=(0.06, frame_depth - 0.04, jamb_h),
            location=(center_x - (R_in - 0.03), y_front, z_base + 0.09 + jamb_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(0.06, frame_depth - 0.04, jamb_h),
            location=(center_x + (R_in - 0.03), y_front, z_base + 0.09 + jamb_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
    else:
        # Standard Square Timber Post-and-Lintel Frame
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
    
    # 2. Door Panel (Single or Double Freight Doors)
    if door_w >= 1.6:
        # Double freight cargo doors (left and right opening leaves)
        leaf_w = (door_w - 0.06) * 0.5
        leaf_h = door_h - 0.05
        leaf_t = 0.055
        ang_rad = math.radians(door_angle_deg)
        num_planks = 3
        gap = 0.004
        pw = (leaf_w - (num_planks - 1) * gap) / num_planks
        
        # Left leaf
        hinge_lx = center_x - door_w * 0.5 + 0.02
        hinge_ly = y_front - wall_thickness * 0.2
        rot_l = Euler((0.0, 0.0, ang_rad), 'XYZ').to_matrix().to_4x4()
        
        for k in range(num_planks):
            px = (k + 0.5) * pw + k * gap
            jank = 0.003 * math.sin(k * 2.5 + 1.0)
            pl_loc = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((px, jank, leaf_h * 0.5)))
            create_beveled_box(bm, size=(pw - 0.003, leaf_t, leaf_h), location=pl_loc, rotation=(0.0, 0.0, ang_rad), mat_index=MAT_INDEX_DOOR, bevel_amount=0.007)
        
        # Left leaf horizontal backing battens
        for bf in [0.12, 0.88]:
            bat_loc = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.5, leaf_t * 0.5 + 0.012, leaf_h * bf)))
            create_beveled_box(bm, size=(leaf_w * 0.94, 0.024, 0.11), location=bat_loc, rotation=(0.0, 0.0, ang_rad), mat_index=MAT_INDEX_DOOR, bevel_amount=0.005)
            
        # Right leaf
        hinge_rx = center_x + door_w * 0.5 - 0.02
        hinge_ry = y_front - wall_thickness * 0.2
        rot_r = Euler((0.0, 0.0, -ang_rad), 'XYZ').to_matrix().to_4x4()
        
        for k in range(num_planks):
            px = -((k + 0.5) * pw + k * gap)
            jank = 0.003 * math.sin(k * 2.5 + 2.0)
            pr_loc = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((px, jank, leaf_h * 0.5)))
            create_beveled_box(bm, size=(pw - 0.003, leaf_t, leaf_h), location=pr_loc, rotation=(0.0, 0.0, -ang_rad), mat_index=MAT_INDEX_DOOR, bevel_amount=0.007)
            
        for bf in [0.12, 0.88]:
            bat_loc = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.5, leaf_t * 0.5 + 0.012, leaf_h * bf)))
            create_beveled_box(bm, size=(leaf_w * 0.94, 0.024, 0.11), location=bat_loc, rotation=(0.0, 0.0, -ang_rad), mat_index=MAT_INDEX_DOOR, bevel_amount=0.005)
        
        # Forged iron strap hinges with hammered rivets
        for hz_factor in [0.20, 0.80]:
            # Left leaf strap
            sl_c = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.45, -leaf_t * 0.5 - 0.008, hz_factor * leaf_h)))
            create_beveled_box(bm, size=(leaf_w * 0.75, 0.016, 0.065), location=sl_c, rotation=(0.0, 0.0, ang_rad), mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
            # Rivet studs
            for r_frac in [0.15, 0.50, 0.80]:
                rv_c = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.75 * r_frac, -leaf_t * 0.5 - 0.018, hz_factor * leaf_h)))
                create_cylinder(bm, radius=0.014, height=0.014, segments=6, location=rv_c, rotation=(1.57, 0.0, ang_rad), mat_index=MAT_INDEX_IRON)
            
            # Right leaf strap
            sr_c = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.45, -leaf_t * 0.5 - 0.008, hz_factor * leaf_h)))
            create_beveled_box(bm, size=(leaf_w * 0.75, 0.016, 0.065), location=sr_c, rotation=(0.0, 0.0, -ang_rad), mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
            for r_frac in [0.15, 0.50, 0.80]:
                rv_c = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.75 * r_frac, -leaf_t * 0.5 - 0.018, hz_factor * leaf_h)))
                create_cylinder(bm, radius=0.014, height=0.014, segments=6, location=rv_c, rotation=(1.57, 0.0, -ang_rad), mat_index=MAT_INDEX_IRON)
            
        # Iron ring pull handles with mounting escutcheon
        for leaf_sign, hinge_pt, rot_m in [(-1, Vector((hinge_rx, hinge_ry, z_base + 0.05)), rot_r), (1, Vector((hinge_lx, hinge_ly, z_base + 0.05)), rot_l)]:
            ang_val = ang_rad if leaf_sign == 1 else -ang_rad
            esc_c = hinge_pt + (rot_m @ Vector((leaf_sign * leaf_w * 0.82, -leaf_t * 0.5 - 0.012, leaf_h * 0.48)))
            create_beveled_box(bm, size=(0.08, 0.012, 0.12), location=esc_c, rotation=(0.0, 0.0, ang_val), mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
            rng_c = hinge_pt + (rot_m @ Vector((leaf_sign * leaf_w * 0.82, -leaf_t * 0.5 - 0.035, leaf_h * 0.46)))
            create_cylinder(bm, radius=0.055, height=0.018, segments=12, location=rng_c, rotation=(1.57, 0.0, ang_val), mat_index=MAT_INDEX_IRON)
    else:
        # Single standard walk-in door (genuine multi-plank fantasy construction)
        hinge_x = center_x - door_w * 0.5 + 0.02
        hinge_y = y_front - wall_thickness * 0.2
        
        door_leaf_w = door_w - 0.04
        door_leaf_h = door_h - 0.05
        door_leaf_t = 0.055
        ang_rad = math.radians(door_angle_deg)
        rot_mat = Euler((0.0, 0.0, ang_rad), 'XYZ').to_matrix().to_4x4()
        
        # 4 Physical vertical wooden planks with gaps and subtle handmade depth variation
        num_planks = 4
        gap = 0.005
        pw = (door_leaf_w - (num_planks - 1) * gap) / num_planks
        
        for k in range(num_planks):
            px = (k + 0.5) * pw + k * gap
            if is_arched:
                x_rel = px - door_leaf_w * 0.5
                r_sq = max(0.04, (R_in * 0.96) ** 2 - x_rel * x_rel)
                arch_top = z_spring + math.sqrt(r_sq) - 0.03
                cur_plank_h = max(0.5, arch_top - (z_base + 0.05))
            else:
                cur_plank_h = door_leaf_h
            jank = 0.003 * math.sin(k * 2.8 + 1.2)
            plank_loc = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ Vector((px, jank, cur_plank_h * 0.5)))
            create_beveled_box(
                bm,
                size=(pw - 0.002, door_leaf_t, cur_plank_h),
                location=plank_loc,
                rotation=(0.0, 0.0, ang_rad),
                mat_index=MAT_INDEX_DOOR,
                bevel_amount=0.007
            )
            
        # Horizontal and diagonal Z-battens on door back
        bat_fractions = [0.12, 0.68 if is_arched else 0.88]
        for bf in bat_fractions:
            bat_loc = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ Vector((door_leaf_w * 0.5, door_leaf_t * 0.5 + 0.012, door_leaf_h * bf)))
            create_beveled_box(
                bm,
                size=(door_leaf_w * 0.94, 0.024, 0.11),
                location=bat_loc,
                rotation=(0.0, 0.0, ang_rad),
                mat_index=MAT_INDEX_DOOR,
                bevel_amount=0.005
            )
        
        # Heavy forged iron strap hinges with hammered rivets across planks
        for hz_factor in [0.22, 0.78]:
            strap_len = door_leaf_w * 0.75
            strap_local_c = Vector((strap_len * 0.5, -door_leaf_t * 0.5 - 0.010, hz_factor * door_leaf_h))
            strap_world_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ strap_local_c)
            create_beveled_box(
                bm,
                size=(strap_len, 0.016, 0.065),
                location=strap_world_c,
                rotation=(0.0, 0.0, ang_rad),
                mat_index=MAT_INDEX_IRON,
                bevel_amount=0.004
            )
            # Rivets on strap
            for r_frac in [0.15, 0.45, 0.80]:
                rv_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ Vector((strap_len * r_frac, -door_leaf_t * 0.5 - 0.020, hz_factor * door_leaf_h)))
                create_cylinder(bm, radius=0.014, height=0.014, segments=6, location=rv_c, rotation=(1.57, 0.0, ang_rad), mat_index=MAT_INDEX_IRON)
            
        # Forged iron ring pull handle with escutcheon plate
        handle_local_c = Vector((door_leaf_w * 0.82, -door_leaf_t * 0.5 - 0.012, door_leaf_h * 0.48))
        handle_world_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ handle_local_c)
        create_beveled_box(
            bm, size=(0.08, 0.012, 0.14),
            location=handle_world_c,
            rotation=(0.0, 0.0, ang_rad),
            mat_index=MAT_INDEX_IRON,
            bevel_amount=0.004
        )
        ring_c = Vector((hinge_x, hinge_y, z_base + 0.05)) + (rot_mat @ Vector((door_leaf_w * 0.82, -door_leaf_t * 0.5 - 0.035, door_leaf_h * 0.45)))
        create_cylinder(
            bm,
            radius=0.055,
            height=0.018,
            segments=12,
            location=ring_c,
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

def build_window_assembly(bm, center=(0.0, 0.0, 0.0), size=(0.9, 1.2), wall_thickness=0.25,
                          normal_axis='-Y', has_shutters=True, has_flower_box=False, center_pos=None):
    """
    Builds a complete fantasy window opening fixture:
    casing frame, beveled stone sill, framed louvered shutters, and flower box.
    """
    if center_pos is not None:
        center = center_pos
    cx, cy, cz = center
    win_w, win_h = size
    
    # Rotation angle based on wall orientation (accepts string, float angle in radians, or 2D/3D normal vector)
    if isinstance(normal_axis, (int, float)):
        facing_angle = float(normal_axis)
    elif isinstance(normal_axis, (Vector, tuple, list)):
        nx, ny = normal_axis[0], normal_axis[1]
        facing_angle = math.atan2(nx, -ny)
    elif normal_axis == '-Y':
        facing_angle = 0.0
    elif normal_axis == '+Y':
        facing_angle = math.pi
    elif normal_axis == '-X':
        facing_angle = -math.pi * 0.5
    elif normal_axis == '+X':
        facing_angle = math.pi * 0.5
    else:
        facing_angle = 0.0
        
    rot_mat_4x4 = Euler((0.0, 0.0, facing_angle), 'XYZ').to_matrix().to_4x4()
    tr_mat = Matrix.Translation(Vector((cx, cy, cz))) @ rot_mat_4x4
    
    def to_world(loc, rot=(0.0, 0.0, 0.0)):
        w_loc = tr_mat @ Vector(loc)
        w_rot = (rot_mat_4x4 @ Euler(rot, 'XYZ').to_matrix().to_4x4()).to_euler('XYZ')
        return w_loc, (w_rot.x, w_rot.y, w_rot.z)
        
    # 1. Beveled Stone Window Sill (projecting outward)
    sill_w = win_w + 0.16
    sill_thick = 0.12
    sill_d = wall_thickness + 0.18
    sill_loc, sill_rot = to_world((0.0, -sill_d * 0.5 + wall_thickness * 0.5 - 0.04, -win_h * 0.5 - sill_thick * 0.5))
    create_beveled_box(bm, size=(sill_w, sill_d, sill_thick), location=sill_loc, rotation=sill_rot, mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
    
    # 2. Heavy Timber Exterior Casing Frame
    casing_t = 0.08
    casing_w = 0.11
    jamb_h = win_h + casing_w
    jamb_cz = 0.0
    
    # Left Jamb
    lj_loc, lj_rot = to_world((-win_w * 0.5 - casing_w * 0.5, -wall_thickness * 0.5 - casing_t * 0.5, jamb_cz))
    create_beveled_box(bm, size=(casing_w, casing_t, jamb_h), location=lj_loc, rotation=lj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    
    # Right Jamb
    rj_loc, rj_rot = to_world((win_w * 0.5 + casing_w * 0.5, -wall_thickness * 0.5 - casing_t * 0.5, jamb_cz))
    create_beveled_box(bm, size=(casing_w, casing_t, jamb_h), location=rj_loc, rotation=rj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    
    # Top Header Lintle
    th_loc, th_rot = to_world((0.0, -wall_thickness * 0.5 - casing_t * 0.5, win_h * 0.5 + casing_w * 0.5))
    create_beveled_box(bm, size=(win_w + casing_w * 2.0 + 0.08, casing_t + 0.02, casing_w), location=th_loc, rotation=th_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    
    # 3. Window Pane (Translucent glass) & Muntin Grids
    pane_loc, pane_rot = to_world((0.0, 0.0, 0.0))
    create_box(bm, size=(win_w - 0.02, 0.02, win_h - 0.02), location=pane_loc, rotation=pane_rot, mat_index=MAT_INDEX_GLASS)
    
    # Vertical muntin crossbar
    vm_loc, vm_rot = to_world((0.0, -0.015, 0.0))
    create_box(bm, size=(0.035, 0.035, win_h - 0.04), location=vm_loc, rotation=vm_rot, mat_index=MAT_INDEX_TIMBER)
    
    # Horizontal muntin crossbars
    for mz in [-win_h * 0.22, win_h * 0.22]:
        hm_loc, hm_rot = to_world((0.0, -0.015, mz))
        create_box(bm, size=(win_w - 0.04, 0.035, 0.035), location=hm_loc, rotation=hm_rot, mat_index=MAT_INDEX_TIMBER)
        
    # 4. Authentically Framed Wooden Window Shutters with Louver Slats & Iron Pintle Hinges
    if has_shutters:
        shutter_w = win_w * 0.44
        shutter_h = win_h * 0.94
        shutter_t = 0.035
        open_ang = math.radians(55.0)
        cos_a = math.cos(open_ang)
        sin_a = math.sin(open_ang)
        
        stile_w = 0.045
        inner_w = max(0.10, shutter_w - stile_w * 2.0)
        
        # Left and Right shutters hinged at casing outer edges
        for side in [-1, 1]:
            hx = side * (win_w * 0.5 + 0.01)
            hy = -wall_thickness * 0.5 - 0.02
            
            dx = side * cos_a
            dy = -sin_a
            rot_z = math.atan2(dy, dx)
            
            sx = hx + dx * (shutter_w * 0.5)
            sy = hy + dy * (shutter_w * 0.5)
            
            # Left & Right framing stiles
            for st_side in [-1, 1]:
                st_off = st_side * (shutter_w * 0.5 - stile_w * 0.5)
                # Using local shutter coordinate frame
                st_loc, st_rot = to_world((sx + dx * (st_off / (shutter_w * 0.5)), sy + dy * (st_off / (shutter_w * 0.5)), jamb_cz), rot=(0.0, 0.0, rot_z))
            
            # Shutter base panel
            w_loc, w_rot = to_world((sx, sy, jamb_cz), rot=(0.0, 0.0, rot_z))
            create_beveled_box(
                bm,
                size=(shutter_w, shutter_t, shutter_h),
                location=w_loc,
                rotation=w_rot,
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.007
            )
            
            # Horizontal recessed louver slat grooves (giving realistic multi-slat look)
            num_slats = 5
            slat_spacing = (shutter_h * 0.78) / (num_slats + 1)
            for s_i in range(1, num_slats + 1):
                slat_z = jamb_cz - shutter_h * 0.39 + s_i * slat_spacing
                slat_loc, slat_rot = to_world((sx, sy - 0.010, slat_z), rot=(0.18, 0.0, rot_z))
                create_box(
                    bm,
                    size=(inner_w, 0.015, 0.024),
                    location=slat_loc,
                    rotation=slat_rot,
                    mat_index=MAT_INDEX_WOOD
                )
            
            # Stylized iron hinge straps with pintle pins
            for hz in [-shutter_h * 0.32, shutter_h * 0.32]:
                strap_loc, strap_rot = to_world((sx, sy - 0.012, jamb_cz + hz), rot=(0.0, 0.0, rot_z))
                create_box(
                    bm,
                    size=(shutter_w * 0.75, 0.012, 0.038),
                    location=strap_loc,
                    rotation=strap_rot,
                    mat_index=MAT_INDEX_IRON
                )
                # Wall pintle pin
                pintle_loc, pintle_rot = to_world((hx, hy - 0.008, jamb_cz + hz))
                create_cylinder(bm, radius=0.014, height=0.06, segments=6, location=pintle_loc, mat_index=MAT_INDEX_IRON)
            
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
    Creates an ornate stylized medieval fantasy carriage lantern:
    - Heavy forged iron wall mounting backplate embedded flush in wall plaster.
    - Graceful curved wrought-iron scrollwork bracket arm.
    - Hexagonal carriage lamp cage with vertical ribs, top/bottom collar rings, and glowing core.
    - Pyramidal iron roof cap with top suspension ring and bottom droplet finial.
    """
    cx, cy, cz = location
    
    # 1. Cast-iron wall mounting backplate (firmly embedded in wall surface)
    create_beveled_box(
        bm, size=(0.14, 0.035, 0.38),
        location=(cx, cy + 0.010, cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006
    )
    # Mounting decorative bolt studs
    for bz_off in [-0.14, 0.14]:
        create_cylinder(
            bm, radius=0.014, height=0.015, segments=6,
            location=(cx, cy - 0.010, cz + bz_off),
            rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
        )
    
    # 2. Forged wrought-iron curved scrollwork bracket arm
    arm_len = 0.38
    arm_y = cy - arm_len * 0.5
    # Main horizontal support beam
    create_beveled_box(
        bm, size=(0.032, arm_len, 0.032),
        location=(cx, arm_y, cz + 0.08),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )
    # Diagonal curved forged knee strut underneath
    create_beveled_box(
        bm, size=(0.024, 0.26, 0.024),
        location=(cx, cy - 0.13, cz - 0.01),
        rotation=(-0.785, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.003
    )
    # Decorative scrollwork curl at outer tip
    create_cylinder(
        bm, radius=0.035, height=0.024, segments=10,
        location=(cx, cy - arm_len + 0.02, cz + 0.12),
        rotation=(0.0, 1.57, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    # 3. Lantern suspension point
    ly = cy - arm_len + 0.06
    lz = cz - 0.08
    
    # Top hanging ring / eyelet
    create_cylinder(
        bm, radius=0.035, height=0.016, segments=10,
        location=(cx, ly, lz + 0.19),
        rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    # 4. Pyramidal iron roof cap
    from .mesh_utils import create_cone
    create_cone(
        bm, radius1=0.13, radius2=0.03, height=0.09, segments=6,
        location=(cx, ly, lz + 0.12), mat_index=MAT_INDEX_IRON
    )
    
    # 5. Glowing glass lantern core
    create_cylinder(
        bm, radius=0.092, height=0.20, segments=6,
        location=(cx, ly, lz), mat_index=MAT_INDEX_GLASS
    )
    
    # 6. Hexagonal cage vertical iron ribs & top/bottom collar rings
    for i in range(6):
        ang = (2.0 * math.pi * i) / 6.0
        rx = cx + 0.095 * math.cos(ang)
        ry = ly + 0.095 * math.sin(ang)
        create_box(
            bm, size=(0.016, 0.016, 0.20),
            location=(rx, ry, lz), mat_index=MAT_INDEX_IRON
        )
    # Top and bottom collar rings
    for rz_off in [-0.095, 0.095]:
        create_cylinder(
            bm, radius=0.105, height=0.020, segments=6,
            location=(cx, ly, lz + rz_off), mat_index=MAT_INDEX_IRON
        )
        
    # 7. Hexagonal iron base & bottom droplet finial
    create_cone(
        bm, radius1=0.04, radius2=0.12, height=0.06, segments=6,
        location=(cx, ly, lz - 0.12), mat_index=MAT_INDEX_IRON
    )
    create_cone(
        bm, radius1=0.028, radius2=0.005, height=0.06, segments=6,
        location=(cx, ly, lz - 0.17), mat_index=MAT_INDEX_IRON
    )
