"""
Doorways, windows, and decorative opening accessories for stylized fantasy buildings.
Produces walkthrough-ready doorways with adjustable door leaf angles, deep reveals,
sills, shutters, flower boxes, and iron lanterns.
"""

import bpy
import bmesh
import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, apply_box_uvs,
    create_torus_ring, create_door_batten
)
from .materials import (
    MAT_INDEX_TIMBER, MAT_INDEX_DOOR, MAT_INDEX_GLASS,
    MAT_INDEX_IRON, MAT_INDEX_STONE, MAT_INDEX_SHINGLES, MAT_INDEX_WOOD,
    MAT_INDEX_WINDOW_FRAME, MAT_INDEX_SHUTTER, MAT_INDEX_LOG, MAT_INDEX_STAIRS, MAT_INDEX_RAILING,
    MAT_INDEX_CUT_STONE
)

_create_torus_ring = create_torus_ring

def _create_arched_plank(bm, hinge_x, hinge_y, z_bot, x_left, x_right, z_left, z_right, leaf_t, out_ang, rot_mat, mat_index=MAT_INDEX_DOOR):
    hw = leaf_t * 0.5
    v0 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_left, -hw, 0.0)))
    v1 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_right, -hw, 0.0)))
    v2 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_right, hw, 0.0)))
    v3 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_left, hw, 0.0)))
    hl = z_left - z_bot
    hr = z_right - z_bot
    vt0 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_left, -hw, hl)))
    vt1 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_right, -hw, hr)))
    vt2 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_right, hw, hr)))
    vt3 = Vector((hinge_x, hinge_y, z_bot)) + (rot_mat @ Vector((x_left, hw, hl)))
    bv0 = bm.verts.new(v0)
    bv1 = bm.verts.new(v1)
    bv2 = bm.verts.new(v2)
    bv3 = bm.verts.new(v3)
    tv0 = bm.verts.new(vt0)
    tv1 = bm.verts.new(vt1)
    tv2 = bm.verts.new(vt2)
    tv3 = bm.verts.new(vt3)
    faces = []
    face_vertex_lists = [
        [bv0, bv3, bv2, bv1],  # Bottom (-Z)
        [tv0, tv1, tv2, tv3],  # Top (+Z)
        [bv0, bv1, tv1, tv0],  # Front (-Y)
        [bv1, bv2, tv2, tv1],  # Right (+X)
        [bv2, bv3, tv3, tv2],  # Back (+Y)
        [bv3, bv0, tv0, tv3],  # Left (-X)
    ]
    for fvs in face_vertex_lists:
        f = bm.faces.new(fvs)
        f.material_index = mat_index
        faces.append(f)
    if True:
        try:
            edges=list({e for f in faces for e in f.edges})
            res=bmesh.ops.bevel(bm, geom=edges, offset=0.010, segments=2, profile=0.7, affect='EDGES')
            for f in res.get('faces', []):
                f.material_index=mat_index
        except Exception:
            pass

def build_door_assembly(bm, center_x, y_front, z_base, wall_thickness=0.3, door_w=1.0, door_h=2.2, door_angle_deg=45.0, door_shape='AUTO', ground_floor_stone=True):
    """
    Builds the door frame, casing, openable door panel, iron hinges, and ring handle.
    door_angle_deg controls how open the door leaf is (0 = closed, 90 = fully open outward).
    door_shape: 'AUTO', 'ARCHED', or 'SQUARE'.
    Doors open OUTWARD (toward -Y front) with fantasy ring pull.
    Arched leaf has true continuous arch top, no stairstep.
    """
    frame_thick = 0.12
    frame_depth = wall_thickness + 0.06
    is_arched = (door_shape == 'ARCHED') or (door_shape == 'AUTO' and ground_floor_stone and door_w < 1.6)
    
    if is_arched:
        R_in = door_w * 0.5
        R_out = R_in + 0.22
        z_spring = z_base + door_h - R_in
        
        create_beveled_box(
            bm,
            size=(door_w + 0.55, frame_depth + 0.08, 0.09),
            location=(center_x, y_front, z_base + 0.045),
            mat_index=MAT_INDEX_CUT_STONE,
            bevel_amount=0.018
        )
        
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
                    mat_index=MAT_INDEX_CUT_STONE,
                    bevel_amount=0.015
                )
                
        sp_outer_w = R_in + 0.32
        sp_top_z = z_spring + R_in + 0.25
        num_arc = 6
        
        yf_f = y_front - frame_depth * 0.5 - 0.012
        yf_b = y_front + frame_depth * 0.5 + 0.012
        
        for side_sign in [-1, 1]:
            if side_sign < 0:
                arc_angles = [math.pi - i * (0.5 * math.pi / num_arc) for i in range(num_arc + 1)]
            else:
                arc_angles = [0.5 * math.pi - i * (0.5 * math.pi / num_arc) for i in range(num_arc + 1)]
                
            arc_vf = [bm.verts.new(Vector((center_x + R_in * math.cos(a), yf_f, z_spring + R_in * math.sin(a)))) for a in arc_angles]
            arc_vb = [bm.verts.new(Vector((center_x + R_in * math.cos(a), yf_b, z_spring + R_in * math.sin(a)))) for a in arc_angles]
            
            x_out = center_x + side_sign * sp_outer_w
            x_mid = center_x
            
            v_bot_f = bm.verts.new(Vector((x_out, yf_f, z_spring)))
            v_bot_b = bm.verts.new(Vector((x_out, yf_b, z_spring)))
            v_corn_f = bm.verts.new(Vector((x_out, yf_f, sp_top_z)))
            v_corn_b = bm.verts.new(Vector((x_out, yf_b, sp_top_z)))
            v_top_f = bm.verts.new(Vector((x_mid, yf_f, sp_top_z)))
            v_top_b = bm.verts.new(Vector((x_mid, yf_b, sp_top_z)))
            
            for ai in range(num_arc):
                v_a0_f = arc_vf[ai]
                v_a1_f = arc_vf[ai + 1]
                v_a0_b = arc_vb[ai]
                v_a1_b = arc_vb[ai + 1]
                
                if side_sign < 0:
                    f_f = bm.faces.new([v_a0_f, v_a1_f, v_corn_f])
                    f_b = bm.faces.new([v_a0_b, v_corn_b, v_a1_b])
                    f_s = bm.faces.new([v_a0_f, v_a0_b, v_a1_b, v_a1_f])
                else:
                    f_f = bm.faces.new([v_corn_f, v_a0_f, v_a1_f])
                    f_b = bm.faces.new([v_corn_b, v_a1_b, v_a0_b])
                    f_s = bm.faces.new([v_a1_f, v_a1_b, v_a0_b, v_a0_f])
                f_f.material_index = MAT_INDEX_CUT_STONE
                f_b.material_index = MAT_INDEX_CUT_STONE
                f_s.material_index = MAT_INDEX_CUT_STONE
                
            first_vf = arc_vf[0] if side_sign < 0 else arc_vf[-1]
            first_vb = arc_vb[0] if side_sign < 0 else arc_vb[-1]
            if side_sign < 0:
                f_bot_f = bm.faces.new([v_bot_f, first_vf, v_corn_f])
                f_bot_b = bm.faces.new([v_bot_b, v_corn_b, first_vb])
                f_side = bm.faces.new([v_bot_f, v_corn_f, v_corn_b, v_bot_b])
                f_base = bm.faces.new([v_bot_f, v_bot_b, first_vb, first_vf])
            else:
                f_bot_f = bm.faces.new([first_vf, v_bot_f, v_corn_f])
                f_bot_b = bm.faces.new([first_vb, v_corn_b, v_bot_b])
                f_side = bm.faces.new([v_bot_b, v_corn_b, v_corn_f, v_bot_f])
                f_base = bm.faces.new([first_vf, first_vb, v_bot_b, v_bot_f])
            for f_elem in [f_bot_f, f_bot_b, f_side, f_base]:
                f_elem.material_index = MAT_INDEX_CUT_STONE
                
            apex_vf = arc_vf[-1] if side_sign < 0 else arc_vf[0]
            apex_vb = arc_vb[-1] if side_sign < 0 else arc_vb[0]
            if side_sign < 0:
                f_top_f = bm.faces.new([v_corn_f, apex_vf, v_top_f])
                f_top_b = bm.faces.new([v_corn_b, v_top_b, apex_vb])
                f_top_roof = bm.faces.new([v_corn_f, v_corn_b, v_top_b, v_top_f])
                f_center = bm.faces.new([v_top_f, v_top_b, apex_vb, apex_vf])
            else:
                f_top_f = bm.faces.new([v_corn_f, v_top_f, apex_vf])
                f_top_b = bm.faces.new([v_corn_b, apex_vb, v_top_b])
                f_top_roof = bm.faces.new([v_top_f, v_top_b, v_corn_b, v_corn_f])
                f_center = bm.faces.new([apex_vf, apex_vb, v_top_b, v_top_f])
            for f_elem in [f_top_f, f_top_b, f_top_roof, f_center]:
                f_elem.material_index = MAT_INDEX_CUT_STONE
                
        create_beveled_box(
            bm, size=(door_w + 0.64, frame_depth + 0.04, 0.16),
            location=(center_x, y_front, sp_top_z + 0.08),
            mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015
        )
    else:
        # Full-depth square timber casing spanning through wall from exterior to interior
        timber_frame_d = wall_thickness + 0.22
        yf_timber = y_front + wall_thickness * 0.5 - 0.03
        create_beveled_box(
            bm,
            size=(frame_thick, timber_frame_d, door_h),
            location=(center_x - (door_w * 0.5 + frame_thick * 0.5), yf_timber, z_base + door_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.015
        )
        create_beveled_box(
            bm,
            size=(frame_thick, timber_frame_d, door_h),
            location=(center_x + (door_w * 0.5 + frame_thick * 0.5), yf_timber, z_base + door_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.015
        )
        # Heavy timber lintel/header beam proud of wall (top reaching continuous lintel log at 2.16m)
        head_h = frame_thick + 0.04
        create_beveled_box(
            bm,
            size=(door_w + frame_thick * 2.4, timber_frame_d + 0.04, head_h),
            location=(center_x, yf_timber, z_base + door_h + head_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.016
        )
        # Ground stone sill threshold
        create_beveled_box(
            bm,
            size=(door_w + frame_thick * 2.0, timber_frame_d + 0.08, 0.08),
            location=(center_x, yf_timber, z_base + 0.04),
            mat_index=MAT_INDEX_CUT_STONE,
            bevel_amount=0.015
        )
        # Interior casing frame sticking into room
        in_door_y = y_front + wall_thickness + 0.02
        create_beveled_box(
            bm, size=(frame_thick * 0.85, 0.05, door_h + frame_thick),
            location=(center_x - (door_w * 0.5 + frame_thick * 0.42), in_door_y, z_base + (door_h + frame_thick) * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        create_beveled_box(
            bm, size=(frame_thick * 0.85, 0.05, door_h + frame_thick),
            location=(center_x + (door_w * 0.5 + frame_thick * 0.42), in_door_y, z_base + (door_h + frame_thick) * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
        create_beveled_box(
            bm, size=(door_w + frame_thick * 2.0, 0.05, frame_thick),
            location=(center_x, in_door_y, z_base + door_h + frame_thick * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )
    
    leaf_t = 0.055
    arch_clear = 0.014
    outer_face_y = (y_front - frame_depth * 0.5) if is_arched else (y_front - 0.12)
    hinge_y_out = outer_face_y + 0.033

    if door_w >= 1.6:
        leaf_w = (door_w - 0.06) * 0.5
        # Leaves hang 4cm lower (bottom anchored at the sill, top gap grows).
        leaf_h = door_h - 0.09
        ang_rad = math.radians(door_angle_deg)
        left_ang = -ang_rad
        right_ang = ang_rad
        num_planks = 3
        gap = 0.004
        pw = (leaf_w - (num_planks - 1) * gap) / num_planks
        
        hinge_lx = center_x - door_w * 0.5 + 0.025
        hinge_ly = hinge_y_out
        rot_l = Euler((0.0, 0.0, left_ang), 'XYZ').to_matrix().to_4x4()
        
        for k in range(num_planks):
            px = (k + 0.5) * pw + k * gap
            jank = 0.003 * math.sin(k * 2.5 + 1.0)
            pl_loc = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((px, jank, leaf_h * 0.5)))
            create_beveled_box(bm, size=(pw - 0.003, leaf_t, leaf_h), location=pl_loc, rotation=(0.0, 0.0, left_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.007, bevel_segments=2)
        
        for bf in [0.14, 0.85]:
            bat_loc = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.5, leaf_t * 0.5 + 0.012, leaf_h * bf)))
            create_door_batten(bm, size=(leaf_w * 0.94, 0.024, 0.11), location=bat_loc, rotation=(0.0, 0.0, left_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.005)
            
        hinge_rx = center_x + door_w * 0.5 - 0.025
        hinge_ry = hinge_y_out
        rot_r = Euler((0.0, 0.0, right_ang), 'XYZ').to_matrix().to_4x4()
        
        for k in range(num_planks):
            px = -((k + 0.5) * pw + k * gap)
            jank = 0.003 * math.sin(k * 2.5 + 2.0)
            pr_loc = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((px, jank, leaf_h * 0.5)))
            create_beveled_box(bm, size=(pw - 0.003, leaf_t, leaf_h), location=pr_loc, rotation=(0.0, 0.0, right_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.007, bevel_segments=2)
            
        for bf in [0.14, 0.85]:
            bat_loc = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.5, leaf_t * 0.5 + 0.012, leaf_h * bf)))
            create_door_batten(bm, size=(leaf_w * 0.94, 0.024, 0.11), location=bat_loc, rotation=(0.0, 0.0, right_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.005)
        
        for hz_factor in [0.22, 0.78]:
            out_sy = -leaf_t*0.5 - 0.012
            sl_c = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.42, out_sy, hz_factor * leaf_h)))
            create_beveled_box(bm, size=(leaf_w * 0.80, 0.020, 0.060), location=sl_c, rotation=(0.0, 0.0, left_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.004, bevel_segments=2)
            for r_frac in [0.22, 0.55, 0.82]:
                rv_c = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((leaf_w * 0.80 * (r_frac-0.5), out_sy, hz_factor * leaf_h)))
                create_cylinder(bm, radius=0.010, height=0.026, segments=6, location=rv_c, rotation=(1.57, 0.0, left_ang), mat_index=MAT_INDEX_IRON)
            # hinge barrel exterior
            hb = Vector((hinge_lx, hinge_ly, z_base + 0.05)) + (rot_l @ Vector((0.012, out_sy, hz_factor * leaf_h)))
            create_cylinder(bm, radius=0.024, height=0.16, segments=10, location=hb, rotation=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_IRON)
            
            sr_c = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.42, out_sy, hz_factor * leaf_h)))
            create_beveled_box(bm, size=(leaf_w * 0.80, 0.020, 0.060), location=sr_c, rotation=(0.0, 0.0, right_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.004, bevel_segments=2)
            for r_frac in [0.22, 0.55, 0.82]:
                rv_c = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-leaf_w * 0.80 * (r_frac-0.5), out_sy, hz_factor * leaf_h)))
                create_cylinder(bm, radius=0.010, height=0.026, segments=6, location=rv_c, rotation=(1.57, 0.0, right_ang), mat_index=MAT_INDEX_IRON)
            hb2 = Vector((hinge_rx, hinge_ry, z_base + 0.05)) + (rot_r @ Vector((-0.012, out_sy, hz_factor * leaf_h)))
            create_cylinder(bm, radius=0.022, height=0.14, segments=8, location=hb2, rotation=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_IRON)
            
        for leaf_sign, hinge_pt, rot_m, ang_val in [(-1, Vector((hinge_rx, hinge_ry, z_base + 0.05)), rot_r, right_ang), (1, Vector((hinge_lx, hinge_ly, z_base + 0.05)), rot_l, left_ang)]:
            out_y = -leaf_t*0.5 - 0.010
            esc_c = hinge_pt + (rot_m @ Vector((leaf_sign * leaf_w * 0.80, out_y + 0.005, leaf_h * 0.50)))
            create_beveled_box(bm, size=(0.09, 0.014, 0.14), location=esc_c, rotation=(0.0, 0.0, ang_val), mat_index=MAT_INDEX_IRON, bevel_amount=0.003, bevel_segments=2)
            hang_c = esc_c + (rot_m @ Vector((0.0, 0.006, -0.02)))
            create_beveled_box(bm, size=(0.04, 0.016, 0.04), location=hang_c, rotation=(0.0, 0.0, ang_val), mat_index=MAT_INDEX_IRON, bevel_amount=0.003, bevel_segments=2)
            boss_c = hang_c + (rot_m @ Vector((0.0, 0.010, -0.015)))
            create_cylinder(bm, radius=0.011, height=0.022, segments=8, location=boss_c, rotation=(1.57, 0.0, ang_val), mat_index=MAT_INDEX_IRON)
            ring_c = boss_c + (rot_m @ Vector((0.0, 0.012, -0.045)))
            _create_torus_ring(bm, location=ring_c, rotation=(1.57, 0.0, ang_val), major_radius=0.050, minor_radius=0.009, mat_index=MAT_INDEX_IRON)
            # Matching interior-side ring pull so the door reads as detailed from inside too
            in_y = leaf_t * 0.5 + 0.010
            in_boss_c = hinge_pt + (rot_m @ Vector((leaf_sign * leaf_w * 0.80, in_y, leaf_h * 0.50 - 0.02)))
            create_cylinder(bm, radius=0.011, height=0.022, segments=8, location=in_boss_c, rotation=(1.57, 0.0, ang_val), mat_index=MAT_INDEX_IRON)
            in_ring_c = in_boss_c + (rot_m @ Vector((0.0, -0.012, -0.045)))
            _create_torus_ring(bm, location=in_ring_c, rotation=(1.57, 0.0, ang_val), major_radius=0.050, minor_radius=0.009, mat_index=MAT_INDEX_IRON)
    else:
        door_leaf_w = door_w - 0.03
        door_leaf_t = leaf_t
        ang_rad = math.radians(door_angle_deg)
        out_ang = -ang_rad
        rot_mat = Euler((0.0, 0.0, out_ang), 'XYZ').to_matrix().to_4x4()
        
        z_door_bot = z_base + 0.095
        hinge_x = center_x - door_w * 0.5 + 0.025
        hinge_y = hinge_y_out
        
        num_planks = 7
        gap = 0.0035
        pw = (door_leaf_w - (num_planks - 1) * gap) / num_planks
        
        if is_arched:
            R_door = max(0.10, R_in - arch_clear)
            door_center_local = door_leaf_w * 0.5
            for k in range(num_planks):
                x_l = k * (pw + gap)
                x_r = x_l + pw
                dl = x_l - door_center_local
                dr = x_r - door_center_local
                zl = z_spring + math.sqrt(max(0.0, R_door*R_door - dl*dl)) if abs(dl) < R_door else z_spring
                zr = z_spring + math.sqrt(max(0.0, R_door*R_door - dr*dr)) if abs(dr) < R_door else z_spring
                _create_arched_plank(bm, hinge_x, hinge_y, z_door_bot, x_l, x_r, zl, zr, door_leaf_t, out_ang, rot_mat, MAT_INDEX_DOOR)
        else:
            for k in range(num_planks):
                px = (k + 0.5) * pw + k * gap
                # Square leaves hang 4cm lower (bottom anchored, top gap grows).
                cur_plank_h = door_h - 0.09
                jank = 0.002 * math.sin(k * 2.8 + 1.2)
                plank_loc = Vector((hinge_x, hinge_y, z_door_bot)) + (rot_mat @ Vector((px, jank, cur_plank_h * 0.5)))
                create_beveled_box(bm, size=(pw - 0.002, door_leaf_t, cur_plank_h), location=plank_loc, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.010, bevel_segments=3)

        bat_z_list = [z_door_bot + 0.24, min(z_spring - 0.10, z_door_bot + (door_h - 0.05) * 0.72) if is_arched else (z_door_bot + (door_h - 0.09) * 0.82)]
        for bz in bat_z_list:
            bat_loc = Vector((hinge_x, hinge_y, bz)) + (rot_mat @ Vector((door_leaf_w * 0.5, -door_leaf_t*0.5 - 0.008, 0.0)))
            create_door_batten(bm, size=(door_leaf_w * 0.92, 0.022, 0.10), location=bat_loc, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_DOOR, bevel_amount=0.004, bevel_segments=2)

        strap_len = door_leaf_w * 0.82
        if is_arched:
            strap_z_list = [z_door_bot + 0.30, z_door_bot + (door_h*0.52), min(z_spring - 0.08, z_door_bot + (door_h - 0.05) * 0.72)]
        else:
            strap_z_list = [z_door_bot + 0.28, z_door_bot + (door_h*0.50), z_door_bot + (door_h - 0.09) * 0.78]
        for hz in strap_z_list:
            strap_out_y = -door_leaf_t*0.5 - 0.012
            strap_world_c = Vector((hinge_x, hinge_y, hz)) + (rot_mat @ Vector((strap_len * 0.42, strap_out_y, 0.0)))
            create_beveled_box(bm, size=(strap_len, 0.020, 0.060), location=strap_world_c, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.004, bevel_segments=2)
            for r_frac in [0.22, 0.55, 0.82]:
                rv_c = Vector((hinge_x, hinge_y, hz)) + (rot_mat @ Vector((strap_len * (r_frac-0.5)*0.92, strap_out_y, 0.0)))
                create_cylinder(bm, radius=0.010, height=0.026, segments=6, location=rv_c, rotation=(1.57, 0.0, out_ang), mat_index=MAT_INDEX_IRON)
            # hinge barrel on exterior
            hb = Vector((hinge_x, hinge_y, hz)) + (rot_mat @ Vector((0.012, strap_out_y, 0.0)))
            create_cylinder(bm, radius=0.024, height=0.16, segments=10, location=hb, rotation=(0.0, 0.0, 0.0), mat_index=MAT_INDEX_IRON)

        handle_z = z_door_bot + 0.98
        out_y = -door_leaf_t*0.5 - 0.014
        handle_world_c = Vector((hinge_x, hinge_y, handle_z)) + (rot_mat @ Vector((door_leaf_w * 0.82, out_y, 0.0)))
        create_beveled_box(bm, size=(0.11, 0.016, 0.16), location=handle_world_c, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.005, bevel_segments=3)
        for rx, rz in [(-0.04, -0.06), (0.04, -0.06), (-0.04, 0.06), (0.04, 0.06)]:
            rc = handle_world_c + (rot_mat @ Vector((rx, -0.006, rz)))
            create_cylinder(bm, radius=0.008, height=0.018, segments=5, location=rc, rotation=(1.57, 0.0, out_ang), mat_index=MAT_INDEX_IRON)
        hang_c = Vector((hinge_x, hinge_y, handle_z)) + (rot_mat @ Vector((door_leaf_w * 0.82, out_y - 0.012, -0.055)))
        create_beveled_box(bm, size=(0.08, 0.022, 0.08), location=hang_c, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.004, bevel_segments=2)
        boss_c = hang_c + (rot_mat @ Vector((0.0, -0.012, -0.012)))
        create_cylinder(bm, radius=0.013, height=0.032, segments=8, location=boss_c, rotation=(1.57, 0.0, out_ang), mat_index=MAT_INDEX_IRON)
        ring_c = boss_c + (rot_mat @ Vector((0.0, -0.012, -0.052)))
        _create_torus_ring(bm, location=ring_c, rotation=(1.57, 0.0, out_ang), major_radius=0.060, minor_radius=0.013, major_segments=18, minor_segments=12, mat_index=MAT_INDEX_IRON)

        # Matching interior-side handle plate and ring pull so the door isn't blank from inside
        in_y = door_leaf_t * 0.5 + 0.014
        in_handle_c = Vector((hinge_x, hinge_y, handle_z)) + (rot_mat @ Vector((door_leaf_w * 0.82, in_y, 0.0)))
        create_beveled_box(bm, size=(0.11, 0.016, 0.16), location=in_handle_c, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.005, bevel_segments=3)
        in_hang_c = Vector((hinge_x, hinge_y, handle_z)) + (rot_mat @ Vector((door_leaf_w * 0.82, in_y + 0.012, -0.055)))
        create_beveled_box(bm, size=(0.08, 0.022, 0.08), location=in_hang_c, rotation=(0.0, 0.0, out_ang), mat_index=MAT_INDEX_IRON, bevel_amount=0.004, bevel_segments=2)
        in_boss_c = in_hang_c + (rot_mat @ Vector((0.0, 0.012, -0.012)))
        create_cylinder(bm, radius=0.013, height=0.032, segments=8, location=in_boss_c, rotation=(1.57, 0.0, out_ang), mat_index=MAT_INDEX_IRON)
        in_ring_c = in_boss_c + (rot_mat @ Vector((0.0, 0.012, -0.052)))
        _create_torus_ring(bm, location=in_ring_c, rotation=(1.57, 0.0, out_ang), major_radius=0.060, minor_radius=0.013, major_segments=18, minor_segments=12, mat_index=MAT_INDEX_IRON)

def build_front_steps(bm, center_x, y_front, z_base, num_steps=3, step_w=1.6, step_d=0.35, step_h=0.18):
    """
    Creates solid grounded fantasy stone steps leading up to the front door.
    Each step extends solidly down to ground level (Z=0) so no steps float.
    Steps start in front of the door threshold and lower than z_base so the threshold
    and jamb bases remain cleanly visible above the stairs.
    """
    step_back_y = y_front - 0.22
    for i in range(num_steps):
        cur_w = step_w + (num_steps - 1 - i) * 0.14
        cur_y = step_back_y - (i + 0.5) * step_d
        top_z = z_base - 0.04 - i * step_h
        step_total_h = max(0.08, top_z)
        cz = step_total_h * 0.5
        step_faces = create_beveled_box(
            bm,
            size=(cur_w, step_d + 0.02, step_total_h - 0.005),
            location=(center_x, cur_y, cz),
            mat_index=MAT_INDEX_CUT_STONE,
            bevel_amount=0.025
        )
        uv_layer = bm.loops.layers.uv.verify()
        for f in step_faces:
            nx, ny, nz = abs(f.normal.x), abs(f.normal.y), abs(f.normal.z)
            for loop in f.loops:
                co = loop.vert.co
                if nz >= nx and nz >= ny:
                    u, v = co.x * 0.85, co.y * 0.85
                elif nx >= ny:
                    u, v = co.y * 0.85, co.z * 0.85
                else:
                    u, v = co.x * 0.85, co.z * 0.85
                loop[uv_layer].uv = Vector((u, v))

def build_window_assembly(bm, center=(0.0, 0.0, 0.0), size=(0.9, 1.2), wall_thickness=0.25,
                          normal_axis='-Y', has_shutters=True, has_flower_box=False, center_pos=None):
    """
    Builds a complete fantasy window opening fixture:
    full wall-depth jamb liner sleeve, exterior casing & stone sill,
    interior casing frame & sill stool, framed louvered shutters, and flower box.
    Frames straddle the cutout hole edges cleanly to eliminate coplanar fighting.
    """
    if center_pos is not None:
        center = center_pos
    cx, cy, cz = center
    win_w, win_h = size
    
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

    # 1. Thin reveal lining sleeve sitting flush inside the cutout hole (watertight, zero gaps)
    lining_depth = wall_thickness
    liner_t = 0.020
    # Left and Right reveal liners (flush with opening sides)
    ljl_loc, ljl_rot = to_world((-win_w * 0.5 + liner_t * 0.5, 0.0, 0.0))
    create_beveled_box(bm, size=(liner_t, lining_depth, win_h), location=ljl_loc, rotation=ljl_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    rjl_loc, rjl_rot = to_world((win_w * 0.5 - liner_t * 0.5, 0.0, 0.0))
    create_beveled_box(bm, size=(liner_t, lining_depth, win_h), location=rjl_loc, rotation=rjl_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    # Head and Sill liners (spanning full width, flush with cutout edges)
    thl_loc, thl_rot = to_world((0.0, 0.0, win_h * 0.5 - liner_t * 0.5))
    create_beveled_box(bm, size=(win_w, lining_depth, liner_t), location=thl_loc, rotation=thl_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)
    bsl_loc, bsl_rot = to_world((0.0, 0.0, -win_h * 0.5 + liner_t * 0.5))
    create_beveled_box(bm, size=(win_w, lining_depth, liner_t), location=bsl_loc, rotation=bsl_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.004)

    # 2. Exterior Heavy Timber Sill (proud of log wall, covers cutout gap completely)
    casing_w = 0.12
    # In Tier 1 logs bulge out to ~0.28m, so casing depth must span from wall core past log crest
    casing_t = 0.18
    casing_y = -wall_thickness * 0.5 - casing_t * 0.5 + 0.03

    sill_w = win_w + casing_w * 2.0 + 0.14
    sill_thick = 0.13
    sill_d = wall_thickness * 0.5 + 0.26
    sill_y = -wall_thickness * 0.5 - sill_d * 0.5 + 0.06
    sill_loc, sill_rot = to_world((0.0, sill_y, -win_h * 0.5 - sill_thick * 0.5 + 0.02))
    create_beveled_box(bm, size=(sill_w, sill_d, sill_thick), location=sill_loc, rotation=sill_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015)
    
    # 3. Exterior Heavy Timber Casing Frame: caps cut log ends cleanly and sits proud of wall
    jamb_h = win_h + casing_w * 1.5
    jamb_cz = casing_w * 0.25
    
    lj_loc, lj_rot = to_world((-win_w * 0.5 - casing_w * 0.5 + 0.015, casing_y, jamb_cz))
    create_beveled_box(bm, size=(casing_w, casing_t, jamb_h), location=lj_loc, rotation=lj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    
    rj_loc, rj_rot = to_world((win_w * 0.5 + casing_w * 0.5 - 0.015, casing_y, jamb_cz))
    create_beveled_box(bm, size=(casing_w, casing_t, jamb_h), location=rj_loc, rotation=rj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)
    
    th_h = casing_w + 0.04
    th_loc, th_rot = to_world((0.0, casing_y, win_h * 0.5 + th_h * 0.5 - 0.015))
    create_beveled_box(bm, size=(win_w + casing_w * 2.0 + 0.08, casing_t + 0.02, th_h), location=th_loc, rotation=th_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)

    # 4. Interior Timber Casing Frame & Stool: generously overlaps opening edges to eliminate any interior gaps
    in_casing_t = 0.05
    in_casing_w = 0.10
    in_casing_y = wall_thickness * 0.5 + in_casing_t * 0.5 - 0.01
    
    # Heavy interior lintel/header overlapping wall above by 14cm
    in_th_h = in_casing_w + 0.05
    ith_loc, ith_rot = to_world((0.0, in_casing_y, win_h * 0.5 + in_th_h * 0.5 - 0.015))
    create_beveled_box(bm, size=(win_w + in_casing_w * 2.0 + 0.06, in_casing_t + 0.01, in_th_h), location=ith_loc, rotation=ith_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    # Interior Sill Stool shelf extending into room, resting flush across the opening sill
    ist_loc, ist_rot = to_world((0.0, in_casing_y + 0.025, -win_h * 0.5 + 0.025))
    create_beveled_box(bm, size=(win_w + in_casing_w * 2.0 + 0.08, in_casing_t + 0.06, 0.05), location=ist_loc, rotation=ist_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    
    # Interior side jambs running cleanly from stool shelf up into header (authentic joinery)
    in_jamb_h = win_h + 0.02
    in_jamb_cz = 0.02
    ilj_loc, ilj_rot = to_world((-win_w * 0.5 - in_casing_w * 0.5 + 0.015, in_casing_y, in_jamb_cz))
    create_beveled_box(bm, size=(in_casing_w, in_casing_t, in_jamb_h), location=ilj_loc, rotation=ilj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    
    irj_loc, irj_rot = to_world((win_w * 0.5 + in_casing_w * 0.5 - 0.015, in_casing_y, in_jamb_cz))
    create_beveled_box(bm, size=(in_casing_w, in_casing_t, in_jamb_h), location=irj_loc, rotation=irj_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    
    # Interior Apron trim butted under stool, overlapping wall sill cut completely by 12cm
    in_apron_h = 0.14
    iapron_loc, iapron_rot = to_world((0.0, in_casing_y, -win_h * 0.5 - 0.040))
    create_beveled_box(bm, size=(win_w + in_casing_w * 2.0 + 0.02, in_casing_t + 0.02, in_apron_h), location=iapron_loc, rotation=iapron_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006)
    
    pane_loc, pane_rot = to_world((0.0, 0.002, 0.0))
    create_box(bm, size=(win_w - 0.02, 0.02, win_h - 0.02), location=pane_loc, rotation=pane_rot, mat_index=MAT_INDEX_GLASS)
    
    vm_loc, vm_rot = to_world((0.0, -0.012, 0.0))
    create_box(bm, size=(0.035, 0.035, win_h - 0.04), location=vm_loc, rotation=vm_rot, mat_index=MAT_INDEX_TIMBER)
    
    for mz in [-win_h * 0.22, win_h * 0.22]:
        hm_loc, hm_rot = to_world((0.0, -0.012, mz))
        create_box(bm, size=(win_w - 0.04, 0.035, 0.035), location=hm_loc, rotation=hm_rot, mat_index=MAT_INDEX_TIMBER)
        
    if has_shutters:
        shutter_w = win_w * 0.44
        shutter_h = win_h * 0.94
        shutter_t = 0.035
        open_ang = math.radians(55.0)
        cos_a = math.cos(open_ang)
        sin_a = math.sin(open_ang)
        
        stile_w = 0.045
        inner_w = max(0.10, shutter_w - stile_w * 2.0)
        
        for side in [-1, 1]:
            # Hinge mounted on front face of casing jamb
            hx = side * (win_w * 0.5 + 0.01)
            hy = casing_y - casing_t * 0.5
            
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
                bevel_amount=0.007
            )
            
            for hz in [-shutter_h * 0.32, shutter_h * 0.32]:
                strap_loc, strap_rot = to_world((sx, sy - 0.012, jamb_cz + hz), rot=(0.0, 0.0, rot_z))
                create_box(
                    bm,
                    size=(shutter_w * 0.75, 0.012, 0.038),
                    location=strap_loc,
                    rotation=strap_rot,
                    mat_index=MAT_INDEX_IRON
                )
                pintle_loc, pintle_rot = to_world((hx, hy - 0.008, jamb_cz + hz))
                create_cylinder(bm, radius=0.014, height=0.06, segments=6, location=pintle_loc, mat_index=MAT_INDEX_IRON)
            
    if has_flower_box:
        box_w = win_w + 0.08
        box_d = 0.22
        box_h = 0.18
        sy = -wall_thickness * 0.5 - box_d * 0.5 - 0.04
        sz = -win_h * 0.5 - box_h * 0.5 + sill_thick * 0.3
        w_loc, w_rot = to_world((0.0, sy, sz))
        create_beveled_box(bm, size=(box_w, box_d, box_h), location=w_loc, rotation=w_rot, mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
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
    
    create_beveled_box(
        bm, size=(0.14, 0.035, 0.38),
        location=(cx, cy + 0.010, cz),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006
    )
    for bz_off in [-0.14, 0.14]:
        create_cylinder(
            bm, radius=0.014, height=0.015, segments=6,
            location=(cx, cy - 0.010, cz + bz_off),
            rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
        )
    
    arm_len = 0.38
    arm_y = cy - arm_len * 0.5
    create_beveled_box(
        bm, size=(0.032, arm_len, 0.032),
        location=(cx, arm_y, cz + 0.08),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )
    create_beveled_box(
        bm, size=(0.024, 0.26, 0.024),
        location=(cx, cy - 0.13, cz - 0.01),
        rotation=(-0.785, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.003
    )
    create_cylinder(
        bm, radius=0.035, height=0.024, segments=10,
        location=(cx, cy - arm_len + 0.02, cz + 0.12),
        rotation=(0.0, 1.57, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    ly = cy - arm_len + 0.06
    lz = cz - 0.08
    
    create_cylinder(
        bm, radius=0.035, height=0.016, segments=10,
        location=(cx, ly, lz + 0.19),
        rotation=(1.57, 0.0, 0.0), mat_index=MAT_INDEX_IRON
    )
    
    from .mesh_utils import create_cone
    create_cone(
        bm, radius1=0.13, radius2=0.03, height=0.09, segments=6,
        location=(cx, ly, lz + 0.12), mat_index=MAT_INDEX_IRON
    )
    
    create_cylinder(
        bm, radius=0.092, height=0.20, segments=6,
        location=(cx, ly, lz), mat_index=MAT_INDEX_GLASS
    )
    
    for i in range(6):
        ang = (2.0 * math.pi * i) / 6.0
        rx = cx + 0.095 * math.cos(ang)
        ry = ly + 0.095 * math.sin(ang)
        create_box(
            bm, size=(0.016, 0.016, 0.20),
            location=(rx, ry, lz), mat_index=MAT_INDEX_IRON
        )
    for rz_off in [-0.095, 0.095]:
        create_cylinder(
            bm, radius=0.105, height=0.020, segments=6,
            location=(cx, ly, lz + rz_off), mat_index=MAT_INDEX_IRON
        )
        
    create_cone(
        bm, radius1=0.04, radius2=0.12, height=0.06, segments=6,
        location=(cx, ly, lz - 0.12), mat_index=MAT_INDEX_IRON
    )
    create_cone(
        bm, radius1=0.028, radius2=0.005, height=0.06, segments=6,
        location=(cx, ly, lz - 0.17), mat_index=MAT_INDEX_IRON
    )



