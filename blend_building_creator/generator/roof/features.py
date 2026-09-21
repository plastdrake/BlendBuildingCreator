"""
Roof Features: Curved Bargeboards, Spire Turrets, and Fantasy Chimneys.
Extracted from roof generator to adhere to Single Responsibility and GRASP principles.
"""

import math
from mathutils import Vector
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_SHINGLES,
    MAT_INDEX_GLASS, MAT_INDEX_PLASTER_EXT, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_TIMBER_FRAME
)

def build_curved_bargeboards(bm, cx, rx_min, rx_max, y_verge, ez, rz, roof_flare=0.35, segments=4):
    """
    Builds segmented curved bargeboards matching the bell-cast flare of the roof,
    complete with stylized upturned carved finial horns at the eave corners and an apex cap.
    """
    for side in [-1, 1]:
        rx_target = rx_min if side < 0 else rx_max
        for k in range(segments):
            u0 = k / segments
            u1 = (k + 1) / segments
            x0 = cx + side * u0 * abs(rx_target - cx)
            x1 = cx + side * u1 * abs(rx_target - cx)
            drop0 = (1.0 - roof_flare) * u0 + roof_flare * (1.0 - (1.0 - u0) ** 2)
            drop1 = (1.0 - roof_flare) * u1 + roof_flare * (1.0 - (1.0 - u1) ** 2)
            z0 = rz - drop0 * (rz - ez)
            z1 = rz - drop1 * (rz - ez)
            
            mid_x = (x0 + x1) * 0.5
            mid_z = (z0 + z1) * 0.5
            dx = x1 - x0
            dz = z1 - z0
            seg_len = math.sqrt(dx * dx + dz * dz) + 0.03
            seg_ang = math.atan2(dz, dx)
            create_beveled_box(
                bm,
                size=(seg_len, 0.10, 0.16),
                location=(mid_x, y_verge, mid_z),
                rotation=(0.0, -seg_ang, 0.0),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.012
            )
            
    # Apex finial cap
    create_beveled_box(
        bm,
        size=(0.20, 0.12, 0.28),
        location=(cx, y_verge, rz + 0.10),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.015
    )


def build_roof_turret(bm, center_pos, z_base, turret_w=1.3, turret_h=1.9, spire_h=2.4, style='OCTAGONAL', roof_flare=0.35, scale=1.0):
    """
    Builds a magical fairytale belfry/spire turret perched on the roof.
    Features deep timber foundation skirt, diagonal struts on slopes,
    chunky corner posts, arched openings, bracketed cornice, and steep bell-cast spire.
    """
    turret_w *= scale
    turret_h *= scale
    spire_h *= scale
    
    cx, cy = center_pos
    num_sides = 8 if style == 'OCTAGONAL' else 4
    rot_offset = (math.pi / 8.0) if style == 'OCTAGONAL' else (math.pi / 4.0)
    radius = turret_w * 0.5
    
    # 1. Timber Base Collar / Deep Attic-Penetrating Foundation Skirt
    skirt_depth = 1.40 * scale
    collar_top_z = z_base + 0.22 * scale
    collar_bot_z = z_base - skirt_depth
    collar_h = collar_top_z - collar_bot_z
    collar_mid_z = (collar_top_z + collar_bot_z) * 0.5
    
    collar_size = turret_w + 0.28 * scale
    create_beveled_box(
        bm,
        size=(collar_size, collar_size, collar_h),
        location=(cx, cy, collar_mid_z),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.02 * scale
    )
    
    # 1b. Diagonal Timber Support Corbels on Downhill Slope
    if abs(cx) > 0.18:
        down_sign = 1.0 if cx > 0 else -1.0
        for b_offset in [-turret_w * 0.32, turret_w * 0.32]:
            b_bx = cx + down_sign * (turret_w * 0.45)
            b_by = cy + b_offset
            b_len = 0.85 * scale
            create_beveled_box(
                bm,
                size=(0.14 * scale, 0.14 * scale, b_len),
                location=(b_bx, b_by, z_base - 0.25 * scale),
                rotation=(0.0, down_sign * 0.785, 0.0),
                mat_index=MAT_INDEX_TIMBER_FRAME,
                bevel_amount=0.010 * scale
            )
    
    # 2. Turret Body Walls & Chunky Corner Posts
    body_base_z = collar_top_z
    body_h = turret_h - 0.22 * scale
    
    post_angles = [rot_offset + i * (2.0 * math.pi / num_sides) for i in range(num_sides)]
    post_locs = []
    for ang in post_angles:
        px = cx + radius * math.cos(ang)
        py = cy + radius * math.sin(ang)
        post_locs.append((px, py))
        create_beveled_box(
            bm,
            size=(0.14 * scale, 0.14 * scale, body_h),
            location=(px, py, body_base_z + body_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012 * scale
        )
        
    # Facet Walls & Arched Openings between posts
    for i in range(num_sides):
        nxt = (i + 1) % num_sides
        x0, y0 = post_locs[i]
        x1, y1 = post_locs[nxt]
        mid_x = (x0 + x1) * 0.5
        mid_y = (y0 + y1) * 0.5
        facet_w = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        facet_ang = math.atan2(y1 - y0, x1 - x0)
        
        has_opening = (i % 2 == 0) if style == 'OCTAGONAL' else True
        if has_opening:
            parapet_h = body_h * 0.35
            create_beveled_box(
                bm,
                size=(facet_w + 0.02 * scale, 0.09 * scale, parapet_h),
                location=(mid_x, mid_y, body_base_z + parapet_h * 0.5),
                rotation=(0.0, 0.0, facet_ang),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.008 * scale
            )
            open_h = body_h * 0.48
            open_z = body_base_z + parapet_h + open_h * 0.5
            create_box(
                bm,
                size=(facet_w * 0.70, 0.05 * scale, open_h),
                location=(mid_x, mid_y, open_z),
                rotation=(0.0, 0.0, facet_ang),
                mat_index=MAT_INDEX_GLASS
            )
            head_h = body_h - parapet_h - open_h
            create_beveled_box(
                bm,
                size=(facet_w + 0.02 * scale, 0.09 * scale, head_h),
                location=(mid_x, mid_y, body_base_z + body_h - head_h * 0.5),
                rotation=(0.0, 0.0, facet_ang),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.008 * scale
            )
        else:
            create_beveled_box(
                bm,
                size=(facet_w + 0.02 * scale, 0.09 * scale, body_h),
                location=(mid_x, mid_y, body_base_z + body_h * 0.5),
                rotation=(0.0, 0.0, facet_ang),
                mat_index=MAT_INDEX_PLASTER_EXT,
                bevel_amount=0.008 * scale
            )
            
    # 3. Projecting Cornice with Decorative Corbel Brackets
    cornice_z = body_base_z + body_h
    cornice_overhang = 0.20 * scale
    cornice_r = radius + cornice_overhang
    cornice_h = 0.16 * scale
    create_cylinder(
        bm,
        radius=cornice_r,
        height=cornice_h,
        segments=num_sides,
        location=(cx, cy, cornice_z + cornice_h * 0.5),
        rotation=(0.0, 0.0, rot_offset),
        mat_index=MAT_INDEX_TIMBER
    )
    for px, py in post_locs:
        bx = cx + (px - cx) * 1.15
        by = cy + (py - cy) * 1.15
        create_beveled_box(
            bm,
            size=(0.10 * scale, 0.14 * scale, 0.20 * scale),
            location=(bx, by, cornice_z - 0.10 * scale),
            rotation=(0.0, 0.0, math.atan2(by - cy, bx - cx)),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.010 * scale
        )
        
    # 4. Steep Bell-Cast Faceted Spire Roof (Fairytale style)
    spire_base_z = cornice_z + cornice_h
    spire_r = cornice_r + 0.06 * scale
    spire_apex_z = spire_base_z + spire_h
    
    spire_segs = 4
    uv_spire = bm.loops.layers.uv.verify()
    prev_ring = []
    for i in range(num_sides):
        ang = post_angles[i]
        vx = cx + spire_r * math.cos(ang)
        vy = cy + spire_r * math.sin(ang)
        prev_ring.append(bm.verts.new(Vector((vx, vy, spire_base_z))))
        
    for s_step in range(1, spire_segs + 1):
        u = s_step / float(spire_segs)
        flare_factor = (1.0 - roof_flare) * u + roof_flare * (u ** 1.8)
        cur_z = spire_base_z + u * spire_h
        cur_r = spire_r * (1.0 - flare_factor)
        
        if s_step == spire_segs or cur_r < 0.04 * scale:
            v_apex = bm.verts.new(Vector((cx, cy, spire_apex_z)))
            for i in range(num_sides):
                nxt = (i + 1) % num_sides
                f_cap = bm.faces.new([prev_ring[i], prev_ring[nxt], v_apex])
                f_cap.material_index = MAT_INDEX_SHINGLES
                f_cap.smooth = False
                for loop in f_cap.loops:
                    co = loop.vert.co
                    ang2 = math.atan2(co.y - cy, co.x - cx)
                    loop[uv_spire].uv = Vector(((ang2 + math.pi) / (2.0 * math.pi) * 1.0, co.z * 0.32))
            break
        else:
            cur_ring = []
            for i in range(num_sides):
                ang = post_angles[i]
                vx = cx + cur_r * math.cos(ang)
                vy = cy + cur_r * math.sin(ang)
                cur_ring.append(bm.verts.new(Vector((vx, vy, cur_z))))
                
            for i in range(num_sides):
                nxt = (i + 1) % num_sides
                f_side = bm.faces.new([prev_ring[i], prev_ring[nxt], cur_ring[nxt], cur_ring[i]])
                f_side.material_index = MAT_INDEX_SHINGLES
                f_side.smooth = False
                for loop in f_side.loops:
                    co = loop.vert.co
                    ang2 = math.atan2(co.y - cy, co.x - cx)
                    loop[uv_spire].uv = Vector(((ang2 + math.pi) / (2.0 * math.pi) * 1.0, co.z * 0.32))
            prev_ring = cur_ring
            
    # 5. Finial Spire Needle & Iron Ornament at Apex
    needle_h = 0.85 * scale
    create_cylinder(
        bm,
        radius=0.035 * scale,
        height=needle_h,
        segments=8,
        location=(cx, cy, spire_apex_z + needle_h * 0.5),
        mat_index=MAT_INDEX_TIMBER
    )
    create_cylinder(
        bm,
        radius=0.08 * scale,
        height=0.12 * scale,
        segments=10,
        location=(cx, cy, spire_apex_z + needle_h * 0.65),
        mat_index=MAT_INDEX_IRON
    )
    create_cylinder(
        bm,
        radius=0.015 * scale,
        height=0.55 * scale,
        segments=6,
        location=(cx, cy, spire_apex_z + needle_h * 0.82),
        rotation=(0.0, 1.57, 0.0),
        mat_index=MAT_INDEX_IRON
    )


def build_fantasy_chimney(bm, pos_xy, z_start, total_height, width=0.85, depth=0.85, crooked_angle=0.0):
    """
    Builds a stylized fantasy stone chimney with tapered profile, stone cap, and smoke pot.
    """
    cx, cy = pos_xy
    
    # 1. Main stone chimney trunk
    create_beveled_box(
        bm,
        size=(width, depth, total_height),
        location=(cx, cy, z_start + total_height * 0.5),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.03
    )
    # 2. Projecting stone collar trim
    collar_z = z_start + total_height - 0.16
    create_beveled_box(
        bm,
        size=(width + 0.10, depth + 0.10, 0.12),
        location=(cx, cy, collar_z),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.02
    )
    # 3. Overhanging stone cap with subtle tilt for organic handmade feel
    cap_z = z_start + total_height + 0.05
    create_beveled_box(
        bm,
        size=(width + 0.18, depth + 0.18, 0.12),
        location=(cx, cy, cap_z),
        rotation=(0.0, 0.025, 0.0),
        mat_index=MAT_INDEX_STONE,
        bevel_amount=0.025
    )
    # 4. Terracotta/clay smoke pot on top, centered
    create_cone(
        bm,
        radius1=0.20,
        radius2=0.25,
        height=0.42,
        segments=8,
        location=(cx, cy, cap_z + 0.06 + 0.21),
        mat_index=MAT_INDEX_IRON
    )

