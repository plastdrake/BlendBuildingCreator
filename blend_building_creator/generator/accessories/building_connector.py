"""
Building and Tower Interconnection System.

Provides procedural architectural links, skybridges, gallerias, and tower vestibules
to chain multiple buildings and towers together into unified castle / citadel complexes.

Key Functions:
- build_skybridge_link: Enclosed elevated walkway spanning between two buildings,
  featuring framed portals into both buildings, stone-mullioned windows, a soaring
  underpass arch vault beneath for stairs/path clearance, and a walkable battlement
  or pitched shingle roof.
- build_tower_building_connector: Architectural masonry vestibule and portal link
  connecting a round tower into an adjacent building with framed stone archways and quoins.
- build_curtain_wall_gate_portal: Fortified stone gatehouse with arched opening,
  voussoir ring, iron portcullis, and battlement parapet for plateau rim walls.
- chain_buildings: High-level modular utility for interconnecting multiple buildings in a chain.
"""

import math
from mathutils import Vector, Matrix, Euler

from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR,
    MAT_INDEX_TIMBER, MAT_INDEX_GLASS, MAT_INDEX_SHINGLES,
    MAT_INDEX_IRON, MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD
)
from .battlement import build_battlement_run
from .gatehouse import build_portcullis
from ..openings import build_window_assembly



def carve_pass_through_portal(bm, x_span, y_span, z_span):
    """Cuts through existing geometry in a box [x0, x1] x [y0, y1] x [z0, z1]
    so that doorways / portals are clear of intersecting walls and furniture."""
    import bmesh
    x0, x1 = min(x_span), max(x_span)
    y0, y1 = min(y_span), max(y_span)
    z0, z1 = min(z_span), max(z_span)

    # 1. Bisect any intersecting faces along the box boundary planes
    pad = 0.8
    cand_faces = [f for f in bm.faces if f.is_valid and
                  (x0 - pad <= f.calc_center_median().x <= x1 + pad) and
                  (y0 - pad <= f.calc_center_median().y <= y1 + pad) and
                  (z0 - pad <= f.calc_center_median().z <= z1 + pad)]
    if cand_faces:
        geom = list({v for f in cand_faces for v in f.verts}) + list({e for f in cand_faces for e in f.edges}) + cand_faces
        planes = [
            (Vector((x0, 0, 0)), Vector((1, 0, 0))),
            (Vector((x1, 0, 0)), Vector((1, 0, 0))),
            (Vector((0, y0, 0)), Vector((0, 1, 0))),
            (Vector((0, y1, 0)), Vector((0, 1, 0))),
            (Vector((0, 0, z0)), Vector((0, 0, 1))),
            (Vector((0, 0, z1)), Vector((0, 0, 1))),
        ]
        for pt, norm in planes:
            try:
                res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=pt, plane_no=norm)
                geom = res.get('geom', geom)
            except Exception:
                pass

    # 2. Delete any faces whose centers lie inside the box volume
    to_delete = [f for f in bm.faces if f.is_valid and
                 (x0 + 0.02 <= f.calc_center_median().x <= x1 - 0.02) and
                 (y0 + 0.02 <= f.calc_center_median().y <= y1 - 0.02) and
                 (z0 + 0.02 <= f.calc_center_median().z <= z1 - 0.02)]
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context='FACES')


def build_skybridge_link(
    bm,
    p1,
    p2,
    width=9.0,
    floor_z=18.5,
    ceiling_h=3.6,
    wall_thickness=0.55,
    underpass_clearance=None,
    wall_mat=MAT_INDEX_STONE,
    trim_mat=MAT_INDEX_CUT_STONE,
    deck_mat=MAT_INDEX_FLOOR,
    roof_style='BATTLEMENTS',
    has_windows=True,
    num_windows=2,
    has_portals=True,
    has_underpass_arch=True,
    underpass_spring_z=11.5,
):
    """
    Spans an enclosed architectural skybridge between two building facades at p1 and p2.
    """
    v1 = Vector((p1[0], p1[1], floor_z))
    v2 = Vector((p2[0], p2[1], floor_z))
    span_vec = v2 - v1
    span_len = span_vec.length
    if span_len < 0.5:
        return

    # Orthonormal basis for the link:
    # X_axis along span (from p1 to p2), Y_axis transverse across width, Z_axis vertical
    span_dir = span_vec.normalized()
    z_axis = Vector((0.0, 0.0, 1.0))
    trans_dir = z_axis.cross(span_dir).normalized()  # Perpendicular horizontal direction
    yaw = math.atan2(span_dir.y, span_dir.x)
    center = (v1 + v2) * 0.5

    # 1. FLOOR STRUCTURE & WALKWAY DECK
    deck_thick = 0.38
    slab_z = floor_z - deck_thick * 0.5
    # Heavy stone structural floor slab (embeds cleanly into building walls by 0.35m on each side, eliminating gaps)
    create_beveled_box(
        bm, size=(span_len + 0.70, width, deck_thick),
        location=(center.x, center.y, slab_z),
        rotation=(0.0, 0.0, yaw),
        mat_index=trim_mat, bevel_amount=0.025
    )
    # Interior wooden floorboards / flags
    create_beveled_box(
        bm, size=(span_len + 0.50, width - wall_thickness * 2.0, 0.04),
        location=(center.x, center.y, floor_z + 0.02),
        rotation=(0.0, 0.0, yaw),
        mat_index=deck_mat, bevel_amount=0.005
    )

    # 2. CLEAR UNDERPASS ARCH BENEATH THE SPAN (Clean Corbel Springers, No Skewed Slabs)
    if has_underpass_arch:
        arch_span = span_len
        arch_top_z = floor_z - deck_thick
        pier_thick = 0.85
        pier_h = max(1.0, arch_top_z - underpass_spring_z)
        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            pier_pos = pt - span_dir * (end_sign * pier_thick * 0.5)
            pier_cz = underpass_spring_z + pier_h * 0.5
            create_beveled_box(
                bm, size=(pier_thick, width + 0.30, pier_h),
                location=(pier_pos.x, pier_pos.y, pier_cz),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.03
            )
            # Decorative stepped stone corbel capital
            create_beveled_box(
                bm, size=(pier_thick + 0.20, width + 0.45, 0.32),
                location=(pier_pos.x, pier_pos.y, underpass_spring_z + pier_h - 0.16),
                rotation=(0.0, 0.0, yaw),
                mat_index=trim_mat, bevel_amount=0.03
            )
            # Clean stepped stone corbel brackets springing from piers
            for ci in range(2):
                cb_reach = (ci + 1) * 0.50
                cb_h = 0.30
                cb_pos = pt + span_dir * (end_sign * (pier_thick * 0.5 + cb_reach * 0.5))
                create_beveled_box(
                    bm, size=(cb_reach, width + 0.15, cb_h),
                    location=(cb_pos.x, cb_pos.y, arch_top_z - (ci + 0.5) * cb_h),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.02
                )

    # 3. SIDE WALLS & CUT-THROUGH WINDOWS
    wall_h = ceiling_h
    wall_cz = floor_z + wall_h * 0.5
    for side in (-1.0, 1.0):
        wall_offset = side * (width * 0.5 - wall_thickness * 0.5)
        wall_pos = center + trans_dir * wall_offset

        if not (has_windows and num_windows > 0):
            # Solid wall embedded into facades
            create_beveled_box(
                bm, size=(span_len + 0.70, wall_thickness, wall_h),
                location=(wall_pos.x, wall_pos.y, wall_cz),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )
        else:
            outward_vec = trans_dir * side
            facing_angle = math.atan2(outward_vec.x, -outward_vec.y)

            win_w = 1.10
            win_h = 1.50
            sill_z = floor_z + 0.90
            win_cz = sill_z + win_h * 0.5
            win_top_z = sill_z + win_h

            # Lower spandrel wall beneath sills (extended into facades to eliminate gaps)
            spandrel_h = sill_z - floor_z
            create_beveled_box(
                bm, size=(span_len + 0.70, wall_thickness, spandrel_h),
                location=(wall_pos.x, wall_pos.y, floor_z + spandrel_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )

            # Upper lintel wall above window heads (extended into facades)
            lintel_h = (floor_z + wall_h) - win_top_z
            create_beveled_box(
                bm, size=(span_len + 0.70, wall_thickness, lintel_h),
                location=(wall_pos.x, wall_pos.y, win_top_z + lintel_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )

            # Piers flanking and separating the windows
            step_w = span_len / (num_windows + 1)
            u_prev = -span_len * 0.5 - 0.35
            for wi in range(1, num_windows + 1):
                u_win = -span_len * 0.5 + wi * step_w
                u_win_left = u_win - win_w * 0.5
                pier_w = u_win_left - u_prev
                if pier_w > 0.05:
                    p_center_u = (u_prev + u_win_left) * 0.5
                    p_pos = wall_pos + span_dir * p_center_u
                    create_beveled_box(
                        bm, size=(pier_w, wall_thickness, win_h),
                        location=(p_pos.x, p_pos.y, win_cz),
                        rotation=(0.0, 0.0, yaw),
                        mat_index=wall_mat, bevel_amount=0.02
                    )
                u_prev = u_win + win_w * 0.5

                # Build stylized fantasy window assembly with timber frames and open shutters
                win_pos = wall_pos + span_dir * u_win
                build_window_assembly(
                    bm,
                    center=(win_pos.x, win_pos.y, win_cz),
                    size=(win_w, win_h),
                    wall_thickness=wall_thickness,
                    normal_axis=facing_angle,
                    has_shutters=True,
                    shutters_closed=False
                )

            # Final pier after last window
            u_end = span_len * 0.5 + 0.35
            final_pier_w = u_end - u_prev
            if final_pier_w > 0.05:
                p_center_u = (u_prev + u_end) * 0.5
                p_pos = wall_pos + span_dir * p_center_u
                create_beveled_box(
                    bm, size=(final_pier_w, wall_thickness, win_h),
                    location=(p_pos.x, p_pos.y, win_cz),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=wall_mat, bevel_amount=0.02
                )

    # 4. CEILING & EXPOSED TIMBER BEAMS
    ceil_z = floor_z + wall_h
    ceil_thick = 0.32
    create_beveled_box(
        bm, size=(span_len + 0.70, width, ceil_thick),
        location=(center.x, center.y, ceil_z + ceil_thick * 0.5),
        rotation=(0.0, 0.0, yaw),
        mat_index=trim_mat, bevel_amount=0.02
    )
    # Timber ceiling beams running across width
    n_beams = max(2, int(span_len / 1.6))
    for bi in range(n_beams + 1):
        bu = -span_len * 0.5 + bi * (span_len / n_beams)
        b_pos = center + span_dir * bu
        create_beveled_box(
            bm, size=(0.20, width - wall_thickness * 1.8, 0.22),
            location=(b_pos.x, b_pos.y, ceil_z - 0.11),
            rotation=(0.0, 0.0, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )

    # 5. CONNECTION PORTALS AT BOTH BUILDING INTERFACES
    if has_portals:
        portal_w = 2.00
        portal_h = 2.70
        # Carve pass-through doorways through any existing wall or furniture geometry,
        # reaching 2.6m into adjacent buildings to guarantee a completely walkable passage.
        # The carve starts just above deck level so the bridge deck, boards and flat
        # rugs survive while walls, interior partitions and furniture are cleared.
        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            inward_vec = -end_sign * span_dir
            carve_c = pt + inward_vec * 1.30
            dx = abs(inward_vec.x * 2.8) + abs(trans_dir.x * (portal_w * 0.7))
            dy = abs(inward_vec.y * 2.8) + abs(trans_dir.y * (portal_w * 0.7))
            carve_pass_through_portal(
                bm,
                x_span=(carve_c.x - max(1.3, dx * 0.5), carve_c.x + max(1.3, dx * 0.5)),
                y_span=(carve_c.y - max(1.3, dy * 0.5), carve_c.y + max(1.3, dy * 0.5)),
                z_span=(floor_z + 0.06, floor_z + portal_h + 0.30)
            )

        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            # Stone portal surround frame facing into the building
            p_cz = floor_z + portal_h * 0.5
            p_face_pos = pt - span_dir * (end_sign * 0.08)
            # Arched lintel block
            create_beveled_box(
                bm, size=(0.36, portal_w + 0.60, 0.45),
                location=(p_face_pos.x, p_face_pos.y, floor_z + portal_h + 0.22),
                rotation=(0.0, 0.0, yaw),
                mat_index=trim_mat, bevel_amount=0.03
            )
            # Side jamb piers
            for js in (-1.0, 1.0):
                j_pos = p_face_pos + trans_dir * (js * (portal_w * 0.5 + 0.18))
                create_beveled_box(
                    bm, size=(0.34, 0.38, portal_h + 0.40),
                    location=(j_pos.x, j_pos.y, floor_z + (portal_h + 0.40) * 0.5),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.025
                )

            # Interior lining partition wall inside the bridge covering the connected building's exterior wall
            lining_pos = pt + span_dir * (end_sign * 0.08)
            lining_w = width - wall_thickness * 2.0
            for js in (-1.0, 1.0):
                flank_w = max(0.1, (lining_w - portal_w) * 0.5)
                flank_c = lining_pos + trans_dir * (js * (portal_w * 0.5 + flank_w * 0.5))
                create_beveled_box(
                    bm, size=(0.10, flank_w, portal_h + 0.30),
                    location=(flank_c.x, flank_c.y, floor_z + (portal_h + 0.30) * 0.5),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.01
                )
                # Timber-framed studwork across the lining: jamb posts plus
                # two intermediate studs per flank and a head beam
                for stud_k in range(3):
                    stud_off = portal_w * 0.5 + 0.08 + (flank_w - 0.16) * (stud_k / 2.0)
                    tpost_c = lining_pos + trans_dir * (js * stud_off)
                    create_beveled_box(
                        bm, size=(0.14, 0.16, portal_h + 0.30),
                        location=(tpost_c.x, tpost_c.y, floor_z + (portal_h + 0.30) * 0.5),
                        rotation=(0.0, 0.0, yaw),
                        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
                    )
            # Timber lintel beam covering above doorway
            create_beveled_box(
                bm, size=(0.14, portal_w + 0.20, 0.18),
                location=(lining_pos.x, lining_pos.y, floor_z + portal_h + 0.09),
                rotation=(0.0, 0.0, yaw),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.015
            )

    # 6. ROOF STRUCTURE
    roof_z = ceil_z + ceil_thick
    if roof_style == 'BATTLEMENTS':
        # Walkable stone rampart deck
        deck_pad = 0.25
        deck_cz = roof_z + deck_pad * 0.5
        create_beveled_box(
            bm, size=(span_len + 0.45, width + 0.45, deck_pad),
            location=(center.x, center.y, deck_cz),
            rotation=(0.0, 0.0, yaw),
            mat_index=trim_mat, bevel_amount=0.02
        )
        # Crenellated stone merlon battlements along north and south eaves
        # Inset by 0.45m along span direction so merlons do NOT overlap adjacent roofs/walls
        half_w = (width + 0.45) * 0.5
        for side in (-1.0, 1.0):
            p_a = v1 + span_dir * 0.45 + trans_dir * (side * half_w)
            p_b = v2 - span_dir * 0.45 + trans_dir * (side * half_w)
            build_battlement_run(
                bm, (p_a.x, p_a.y), (p_b.x, p_b.y),
                z_base=roof_z + deck_pad, height=1.05,
                thickness=0.36, style='STONE'
            )
        # Stepped corbel machicolation brackets under the parapet
        n_corbels = max(3, int(span_len / 1.5))
        for ci in range(n_corbels + 1):
            cu = -span_len * 0.5 + ci * (span_len / n_corbels)
            c_center = center + span_dir * cu
            for side in (-1.0, 1.0):
                corb_pos = c_center + trans_dir * (side * (half_w - 0.12))
                create_beveled_box(
                    bm, size=(0.30, 0.38, 0.48),
                    location=(corb_pos.x, corb_pos.y, roof_z - 0.24),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.02
                )
    elif roof_style == 'GABLE':
        # Traditional pitched shingle roof with the ridge running ALONG the
        # span (same proven construction as the covered wooden bridge): slopes
        # shed to the sides, gable ends stop flush at both facades with zero
        # penetration into either building.
        ridge_h = min(width * 0.42, 1.70)
        eave_z = roof_z
        ridge_z = eave_z + ridge_h
        roof_w = width + 0.50
        pitch_len = math.hypot(roof_w * 0.5, ridge_h)
        pitch_ang = math.atan2(ridge_h, roof_w * 0.5)
        for side in (-1.0, 1.0):
            side_pos = center + trans_dir * (side * roof_w * 0.25)
            create_beveled_box(
                bm, size=(span_len + 0.10, pitch_len + 0.15, 0.12),
                location=(side_pos.x, side_pos.y, (eave_z + ridge_z) * 0.5),
                rotation=(side * pitch_ang, 0.0, yaw),
                mat_index=MAT_INDEX_SHINGLES, bevel_amount=0.01
            )
        # Ridge beam capping
        create_beveled_box(
            bm, size=(span_len + 0.12, 0.20, 0.18),
            location=(center.x, center.y, ridge_z + 0.05),
            rotation=(0.0, 0.0, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )
        # Stepped timber gable ends set flush against each building facade
        # (abut: no overhang, no penetration into the buildings)
        n_gsteps = 3
        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            g_c = pt - span_dir * (end_sign * 0.12)
            for gi in range(n_gsteps):
                frac0 = gi / n_gsteps
                frac1 = (gi + 1) / n_gsteps
                gz0 = eave_z + ridge_h * frac0
                gz1 = eave_z + ridge_h * frac1
                gw = roof_w * (1.0 - frac0) - 0.10
                if gw < 0.15:
                    continue
                create_beveled_box(
                    bm, size=(0.18, gw, gz1 - gz0),
                    location=(g_c.x, g_c.y, (gz0 + gz1) * 0.5),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
                )


def build_tower_building_connector(
    bm,
    tower_cx,
    tower_cy,
    tower_r,
    tower_z_base,
    bld_wall_x,
    bld_y_span,
    floor_zs=(8.0, 11.7, 15.4),
    wall_mat=MAT_INDEX_STONE,
    trim_mat=MAT_INDEX_CUT_STONE,
    floor_h=3.7,
    max_vest_z=None,
    hall_step=0.80,
    corridor_y=None,
):
    """
    Constructs an architectural stone vestibule connection uniting a round tower
    with an adjacent building wall, complete with framed entrance portals and quoins.

    Parameters:
        tower_cx, tower_cy (float): Tower center in XY.
        tower_r (float): Tower radius.
        tower_z_base (float): Ground/base elevation of the tower.
        bld_wall_x (float): X-coordinate of the adjoining building wall.
        bld_y_span (tuple): (y_min, y_max) span of the building facade.
        floor_zs (list/tuple): List of floor Z levels where doorways connect.
        max_vest_z (float, optional): Upper cap elevation for vestibule roof so it never exceeds connected building eave.
        hall_step (float): Rise from walk plate to the connected building's floor (stepped dais).
        corridor_y (float, optional): Force the walkway corridor onto this Y plane
            (used where tower and hall footprints barely overlap in Y, so the
            corridor lands inside both instead of in the open between them).
    """
    # Vector from tower center to building wall
    dx = bld_wall_x - tower_cx
    dy = max(bld_y_span[0], min(bld_y_span[1], tower_cy)) - tower_cy
    dist = math.hypot(dx, dy)
    if dist < 0.2:
        return

    # Midpoint of connection
    mid_x = (tower_cx + bld_wall_x) * 0.5
    mid_y = corridor_y if corridor_y is not None else tower_cy + dy * 0.5

    # 1. MASONRY VESTIBULE CONNECTOR WING
    # Spans the gap between the circular tower and the planar house wall
    vest_len = abs(dx) + 0.60
    vest_w = min(4.2, tower_r * 1.3)
    max_z = max(floor_zs) + floor_h
    if max_vest_z is not None:
        max_z = min(max_z, max_vest_z)
    vest_h = max_z - tower_z_base
    vest_cz = tower_z_base + vest_h * 0.5

    create_beveled_box(
        bm, size=(vest_len, vest_w, vest_h),
        location=(mid_x, mid_y, vest_cz),
        mat_index=wall_mat, bevel_amount=0.03
    )

    # 2. FRAMED ENTRANCE PORTALS AT EACH CONNECTING FLOOR
    door_w = 1.65
    door_h = 2.60
    # Carve doorways through existing walls and furniture so passage is 100% walkable
    for fz in floor_zs:
        carve_pass_through_portal(
            bm,
            x_span=(min(tower_cx, bld_wall_x) - 1.2, max(tower_cx, bld_wall_x) + 1.2),
            y_span=(mid_y - door_w * 0.7, mid_y + door_w * 0.7),
            z_span=(fz - 0.05, fz + door_h + 0.20)
        )
    for fz in floor_zs:
        cz = fz + door_h * 0.5
        # Framed stone archway on building side
        door_x = bld_wall_x
        door_y = mid_y
        # Moulded stone lintel
        create_beveled_box(
            bm, size=(0.35, door_w + 0.50, 0.38),
            location=(door_x, door_y, fz + door_h + 0.19),
            mat_index=trim_mat, bevel_amount=0.025
        )
        # Side stone jambs
        for js in (-1.0, 1.0):
            jy = door_y + js * (door_w * 0.5 + 0.14)
            create_beveled_box(
                bm, size=(0.32, 0.28, door_h + 0.35),
                location=(door_x, jy, fz + (door_h + 0.35) * 0.5),
                mat_index=trim_mat, bevel_amount=0.02
            )
        # Interior portal walk plate / step (laid after carving, so it is never
        # eaten): runs from inside the tower, through the vestibule, just into
        # the hall, giving a continuous walkable path across all carve bites.
        # Top at fz+0.10: a finger above tower floor plates (never coplanar).
        plate_len = vest_len + 2.20
        plate_dir = -dx / max(0.5, abs(dx))  # from building wall toward tower
        plate_cx = mid_x + plate_dir * 0.70
        plate_top = fz + 0.10
        create_beveled_box(
            bm, size=(plate_len, door_w - 0.10, 0.12),
            location=(plate_cx, door_y, plate_top - 0.06),
            mat_index=trim_mat, bevel_amount=0.01
        )
        # Access ramp easing the tower-side step down into the tower (a universal
        # adapter: grounded on the tower floor when it sits lower, harmlessly
        # buried when the tower floor sits level or higher).
        create_beveled_box(
            bm, size=(1.50, door_w - 0.20, 0.15),
            location=(plate_cx + plate_dir * (plate_len * 0.5 + 0.55), door_y,
                      plate_top - 0.30),
            rotation=(0.0, plate_dir * 0.40, 0.0),
            mat_index=trim_mat, bevel_amount=0.01
        )
        # Stepped threshold dais rising from the walk plate to the connected
        # building's floor (halls sit ~0.8 above vestibule deck on their stone
        # ground storey; hall_step lowers the rise, e.g. for the chapel).
        # Solid down into the cut floor trench so no tread ever floats.
        hall_dir = -plate_dir
        for si in (1, 2, 3):
            step_top = plate_top + hall_step * si / 3.0
            step_out = 0.25 + (3 - si) * 0.34 + 0.34
            create_beveled_box(
                bm, size=(0.34, door_w - 0.15, step_top - plate_top + 0.32),
                location=(door_x + hall_dir * step_out, door_y,
                          plate_top - 0.32 + (step_top - plate_top + 0.32) * 0.5),
                mat_index=trim_mat, bevel_amount=0.01
            )

    # 3. ASHLAR QUOINS & CORBELS ALONG THE TOWER-BUILDING INTERSECTION
    # Decorative corner stone quoins at the intersection
    quoin_step = 0.85
    n_quoins = max(2, int(vest_h / quoin_step))
    for qi in range(n_quoins):
        qz = tower_z_base + (qi + 0.5) * quoin_step
        q_len = 0.52 if qi % 2 == 0 else 0.36
        for side in (-1.0, 1.0):
            qy = mid_y + side * (vest_w * 0.5 + 0.04)
            create_beveled_box(
                bm, size=(q_len, 0.24, 0.38),
                location=(bld_wall_x - (0.20 if dx < 0 else -0.20), qy, qz),
                mat_index=trim_mat, bevel_amount=0.02
            )

    # 4. COPING / BATTLEMENT CROWN OVER THE VESTIBULE
    create_beveled_box(
        bm, size=(vest_len + 0.30, vest_w + 0.30, 0.28),
        location=(mid_x, mid_y, max_z + 0.14),
        mat_index=trim_mat, bevel_amount=0.03
    )


def build_curtain_wall_gate_portal(
    bm,
    cx,
    cy,
    z_ground,
    outward=(0.0, -1.0),
    gate_w=3.8,
    gate_h=3.6,
    wall_h=4.8,
    thickness=1.2,
    raised_portcullis=True,
    mat_stone=MAT_INDEX_STONE,
    mat_cut_stone=MAT_INDEX_CUT_STONE,
):
    """
    Constructs a monumental fortified stone gatehouse matching the main gate style:
    twin D-bastion flanking gate towers with arrow slits, machicolation corbels, and
    crenellated battlements, with an authentic raised spiked iron portcullis.
    """
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on > 1e-5:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox  # Wall tangent
    ang = math.atan2(ty, tx)

    half_gate = gate_w * 0.5
    tower_rad = 2.10
    tower_height = wall_h + 1.85

    # 1. TWIN FLANKING D-SHAPED BASTION GATE TOWERS (matching main gate style)
    from .gatehouse import build_flanking_gate_towers
    build_flanking_gate_towers(
        bm, cx, cy, z_ground=z_ground, gap_w=gate_w,
        wall_h=wall_h, wall_t=thickness, outward=(ox, oy),
        tower_r=tower_rad, tower_h=tower_height
    )

    # 2. ARCHED GATE LINTEL BAND & VOUSSOIRS SPANNING BETWEEN THE TOWERS
    arch_thick = thickness + 0.40
    lintel_cz = z_ground + gate_h + 0.35
    create_beveled_box(
        bm, size=(gate_w + 0.90, arch_thick, 0.70),
        location=(cx, cy, lintel_cz),
        rotation=(0.0, 0.0, ang),
        mat_index=mat_cut_stone, bevel_amount=0.03
    )

    # 3. FORTIFIED STONE PARAPET & MERLONS ATOP THE CENTRAL GATE ARCH
    parapet_z = z_ground + wall_h
    create_beveled_box(
        bm, size=(gate_w + 1.20, arch_thick + 0.20, 0.25),
        location=(cx, cy, parapet_z + 0.125),
        rotation=(0.0, 0.0, ang),
        mat_index=mat_cut_stone, bevel_amount=0.02
    )
    for f_sign in (-1.0, 1.0):
        m_x0 = cx - tx * (gate_w * 0.5 + 0.40) + ox * (f_sign * arch_thick * 0.5)
        m_y0 = cy - ty * (gate_w * 0.5 + 0.40) + oy * (f_sign * arch_thick * 0.5)
        m_x1 = cx + tx * (gate_w * 0.5 + 0.40) + ox * (f_sign * arch_thick * 0.5)
        m_y1 = cy + ty * (gate_w * 0.5 + 0.40) + oy * (f_sign * arch_thick * 0.5)
        build_battlement_run(
            bm, (m_x0, m_y0), (m_x1, m_y1),
            z_base=parapet_z + 0.25, height=0.95,
            thickness=0.34, style='STONE'
        )

    # 4. AUTHENTIC RAISED IRON PORTCULLIS WITH SPIKED TEETH
    if raised_portcullis:
        build_portcullis(
            bm, cx, cy, z_ground=z_ground,
            width=gate_w - 0.20, height=gate_h - 0.20,
            outward=(ox, oy), raised=gate_h * 0.85
        )


def build_connecting_wing(
    bm,
    cx,
    y_start=5.0,
    y_end=34.0,
    width=6.6,
    z_low=8.0,
    z_high=14.0,
    stair_y_start=16.5,
    stair_y_end=22.5,
    wall_mat=MAT_INDEX_STONE,
    upper_wall_mat=MAT_INDEX_PLASTER_EXT,
    trim_mat=MAT_INDEX_CUT_STONE,
    deck_mat=MAT_INDEX_FLOOR,
    timber_mat=MAT_INDEX_TIMBER,
    roof_mat=MAT_INDEX_SHINGLES,
    has_bridge_door=False,
    bridge_door_y=26.0,
    wall_y_north=None,
    roof_y_end_north=None,
):
    """
    Constructs a stair-stepped connecting wing joining a lower hall (e.g. Great Hall / East Hall)
    at y_start to an upper hall (e.g. Keep / Archive Hall) at y_end across the terrace cliff rise.

    Features:
    - Lower level hall (z_low) and Upper level hall (z_high), both deck-flush with the
      connected buildings' ground floors so every portal opens with no step.
    - Interior stone staircase connecting z_low to z_high over [stair_y_start, stair_y_end].
    - Half-timbered and stone exterior walls with cut-through glazed windows.
    - Gabled shingle roofs stepped to match the elevation rise (flush abutments: roofs
      never penetrate the connected buildings).
    - Framed stone-and-timber portals at both ends (opening into adjacent halls), with
      solid threshold plates bridging the wall passage so the whole route is walkable.
    - Stone arcade piers carried down to bedrock wherever the wing spans the cliff drop.
    - Fitted gallery interior: runner carpets, benches, writing desk, bookshelves and
      standing candlesticks, all kept clear of the walking lanes, portals and doors.
    - Optional bridge doorway on eastern facade for the wooden bridge.

    wall_y_north: Y plane of the upper (north) building's wall. The wing carcass
      embeds past it (no gaps) but decks, roofs and portal frames stop at it.
    roof_y_end_north: where the upper roof terminates (defaults to y_end).
    """
    half_w = width * 0.5
    wall_t = 0.45
    floor_h = 3.7
    # North (upper) building wall plane: decks/roofs/portals stop here while the
    # carcass embeds past it so no gap can open between wing and building.
    wall_n = wall_y_north if wall_y_north is not None else y_end
    roof_n = roof_y_end_north if roof_y_end_north is not None else y_end
    # Walking lanes that must stay clear of furniture: the central gallery lane
    # plus (east wing) the lane from the stair head to the bridge door.
    lane_half = 1.25
    door_lane = (bridge_door_y - 1.35, bridge_door_y + 1.35) if has_bridge_door else None

    # 1. FLOORS & FOUNDATION
    # Lower section floor deck (y_start to stair_y_start)
    len_low = stair_y_start - y_start
    mid_y_low = (y_start + stair_y_start) * 0.5
    create_beveled_box(
        bm, size=(width, len_low, 0.40),
        location=(cx, mid_y_low, z_low - 0.20),
        mat_index=trim_mat, bevel_amount=0.02
    )
    create_beveled_box(
        bm, size=(width - wall_t * 2, len_low, 0.04),
        location=(cx, mid_y_low, z_low + 0.02),
        mat_index=deck_mat, bevel_amount=0.005
    )
    create_beveled_box(
        bm, size=(width + 0.20, len_low, 1.6),
        location=(cx, mid_y_low, z_low - 1.0),
        mat_index=wall_mat, bevel_amount=0.03
    )

    # Upper section floor deck (stair_y_end to the north building wall + 0.15 tuck)
    deck_n = wall_n + 0.15
    len_high = deck_n - stair_y_end
    mid_y_high = (stair_y_end + deck_n) * 0.5
    create_beveled_box(
        bm, size=(width, len_high, 0.40),
        location=(cx, mid_y_high, z_high - 0.20),
        mat_index=trim_mat, bevel_amount=0.02
    )
    create_beveled_box(
        bm, size=(width - wall_t * 2, len_high, 0.04),
        location=(cx, mid_y_high, z_high + 0.02),
        mat_index=deck_mat, bevel_amount=0.005
    )
    create_beveled_box(
        bm, size=(width + 0.20, len_high, 1.6),
        location=(cx, mid_y_high, z_high - 1.0),
        mat_index=wall_mat, bevel_amount=0.03
    )

    # 2. INTERIOR STAIRCASE (Fully walkable climb between z_low and z_high)
    n_steps = 28
    stair_len = stair_y_end - stair_y_start
    stair_h = z_high - z_low
    step_run = stair_len / n_steps
    step_rise = stair_h / n_steps
    stair_w = width - wall_t * 2 - 0.40
    for i in range(n_steps):
        yc = stair_y_start + (i + 0.5) * step_run
        step_top = z_low + (i + 1) * step_rise
        create_beveled_box(
            bm, size=(stair_w, step_run + 0.03, 1.2),
            location=(cx, yc, step_top - 0.60),
            mat_index=wall_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(stair_w + 0.04, step_run + 0.06, 0.08),
            location=(cx, yc, step_top - 0.04),
            mat_index=trim_mat, bevel_amount=0.01
        )
    # Flanking handrails along the stair run
    stair_pitch = math.atan2(stair_h, stair_len)
    stair_hyp = math.hypot(stair_len, stair_h)
    mid_stair_y = (stair_y_start + stair_y_end) * 0.5
    mid_stair_z = (z_low + z_high) * 0.5 + 0.90
    for s_side in (-1.0, 1.0):
        rail_x = cx + s_side * (stair_w * 0.5 - 0.08)
        create_beveled_box(
            bm, size=(0.10, stair_hyp + 0.10, 0.14),
            location=(rail_x, mid_stair_y, mid_stair_z),
            rotation=(stair_pitch, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 3. SIDE WALLS (West and East facades)
    for s_side in (-1.0, 1.0):
        wx = cx + s_side * (half_w - wall_t * 0.5)

        # A. Lower section walls: Ground floor stone + Upper floor stucco
        create_beveled_box(
            bm, size=(wall_t, len_low, floor_h),
            location=(wx, mid_y_low, z_low + floor_h * 0.5),
            mat_index=wall_mat, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(wall_t - 0.04, len_low, floor_h),
            location=(wx, mid_y_low, z_low + floor_h * 1.5),
            mat_index=upper_wall_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(wall_t + 0.08, len_low + 0.10, 0.22),
            location=(wx, mid_y_low, z_low + floor_h),
            mat_index=timber_mat, bevel_amount=0.015
        )

        # Lower section windows
        for wy in (y_start + 3.2, y_start + 7.8):
            wcz = z_low + 1.8
            create_beveled_box(
                bm, size=(wall_t + 0.08, 1.10, 1.60),
                location=(wx, wy, wcz),
                mat_index=MAT_INDEX_GLASS, bevel_amount=0.005
            )
            create_beveled_box(
                bm, size=(wall_t + 0.16, 1.34, 0.18),
                location=(wx, wy, wcz - 0.85),
                mat_index=trim_mat, bevel_amount=0.015
            )
            create_beveled_box(
                bm, size=(wall_t + 0.16, 1.34, 0.22),
                location=(wx, wy, wcz + 0.85),
                mat_index=trim_mat, bevel_amount=0.015
            )

        # B. Stair transition section walls (Raking masonry enclosure)
        create_beveled_box(
            bm, size=(wall_t, stair_len, stair_h + floor_h * 1.6),
            location=(wx, mid_stair_y, (z_low + z_high) * 0.5 + floor_h * 0.8),
            mat_index=wall_mat, bevel_amount=0.02
        )

        # C. Upper section walls: Ground floor stone + Upper floor stucco
        create_beveled_box(
            bm, size=(wall_t, len_high, floor_h),
            location=(wx, mid_y_high, z_high + floor_h * 0.5),
            mat_index=wall_mat, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(wall_t - 0.04, len_high, floor_h),
            location=(wx, mid_y_high, z_high + floor_h * 1.5),
            mat_index=upper_wall_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(wall_t + 0.08, len_high + 0.10, 0.22),
            location=(wx, mid_y_high, z_high + floor_h),
            mat_index=timber_mat, bevel_amount=0.015
        )

        # Upper section windows (or bridge door on east facade)
        for wy in (stair_y_end + 3.0, stair_y_end + 7.5):
            if has_bridge_door and s_side > 0 and abs(wy - bridge_door_y) < 2.0:
                continue
            wcz = z_high + 1.8
            create_beveled_box(
                bm, size=(wall_t + 0.08, 1.10, 1.60),
                location=(wx, wy, wcz),
                mat_index=MAT_INDEX_GLASS, bevel_amount=0.005
            )
            create_beveled_box(
                bm, size=(wall_t + 0.16, 1.34, 0.18),
                location=(wx, wy, wcz - 0.85),
                mat_index=trim_mat, bevel_amount=0.015
            )
            create_beveled_box(
                bm, size=(wall_t + 0.16, 1.34, 0.22),
                location=(wx, wy, wcz + 0.85),
                mat_index=trim_mat, bevel_amount=0.015
            )

        # Bridge door on east facade
        if has_bridge_door and s_side > 0:
            carve_pass_through_portal(
                bm,
                x_span=(wx - wall_t * 0.8, wx + wall_t * 0.8),
                y_span=(bridge_door_y - 1.10, bridge_door_y + 1.10),
                z_span=(z_high, z_high + 2.80)
            )
            create_beveled_box(
                bm, size=(wall_t + 0.20, 2.20, 0.35),
                location=(wx, bridge_door_y, z_high + 2.70),
                mat_index=trim_mat, bevel_amount=0.02
            )
            for j_sign in (-1.0, 1.0):
                create_beveled_box(
                    bm, size=(wall_t + 0.20, 0.32, 2.70),
                    location=(wx, bridge_door_y + j_sign * 1.05, z_high + 1.35),
                    mat_index=trim_mat, bevel_amount=0.02
                )

    # 4. STEPPED GABLE SHINGLE ROOFS (Proper roof builder with flush abutments)
    from ..roof.gable_roof import build_gable_roof
    # Lower section gable roof (abuts South building facade flush with zero overhang)
    build_gable_roof(
        bm,
        x_min=cx - half_w,
        x_max=cx + half_w,
        y_min=y_start,
        y_max=stair_y_start + 0.5,
        z_base=z_low + floor_h * 2.0,
        roof_height=2.6,
        overhang=0.45,
        abut_front=True,  # Flushed to south building wall at y_start
        abut_back=False,
        gable_ends=('BACK',),
        gable_walls=True,
    )

    # Upper section gable roof (abuts North building facade flush with zero overhang)
    build_gable_roof(
        bm,
        x_min=cx - half_w,
        x_max=cx + half_w,
        y_min=stair_y_end - 0.5,
        y_max=roof_n,
        z_base=z_high + floor_h * 2.0,
        roof_height=2.6,
        overhang=0.45,
        abut_front=False,
        abut_back=True,  # Flushed to north building wall, never inside it
        gable_ends=('FRONT',),
        gable_walls=True,
    )

    # Stepped stone parapet gable wall connecting lower and upper roofs at the step
    r_low_eave = z_low + floor_h * 2.0
    r_high_ridge = z_high + floor_h * 2.0 + 2.6
    create_beveled_box(
        bm, size=(width + 0.60, 0.70, (r_high_ridge - r_low_eave) + 0.8),
        location=(cx, stair_y_end, (r_low_eave + r_high_ridge) * 0.5),
        mat_index=trim_mat, bevel_amount=0.03
    )

    # 5. CONNECTION PORTALS AT BOTH BUILDING ENDS (straddling the wall planes,
    # with solid threshold plates so the route is walkable end to end)
    portal_w = 2.00
    portal_h = 2.70

    def _wing_portal(y_wall, z_deck, into_building):
        # Carve the wall + any interior walls/furniture in the doorway corridor
        # (starting just above deck level so decks and flat rugs survive).
        if into_building > 0:
            y_span = (y_wall - 1.2, y_wall + 2.6)
        else:
            y_span = (y_wall - 2.6, y_wall + 1.2)
        carve_pass_through_portal(
            bm,
            x_span=(cx - portal_w * 0.65, cx + portal_w * 0.65),
            y_span=y_span,
            z_span=(z_deck + 0.06, z_deck + portal_h + 0.30)
        )
        # Framed stone portal surround on the wing side of the wall
        create_beveled_box(
            bm, size=(portal_w + 0.60, 0.40, 0.45),
            location=(cx, y_wall, z_deck + portal_h + 0.22),
            mat_index=trim_mat, bevel_amount=0.025
        )
        for js in (-1.0, 1.0):
            create_beveled_box(
                bm, size=(0.35, 0.38, portal_h + 0.35),
                location=(cx + js * (portal_w * 0.5 + 0.18), y_wall, z_deck + (portal_h + 0.35) * 0.5),
                mat_index=trim_mat, bevel_amount=0.02
            )
        # Timber-frame portal: jamb posts + head beam lining the opening
        for js in (-1.0, 1.0):
            create_beveled_box(
                bm, size=(0.16, 0.20, portal_h),
                location=(cx + js * (portal_w * 0.5 - 0.02), y_wall, z_deck + portal_h * 0.5),
                mat_index=timber_mat, bevel_amount=0.015
            )
        create_beveled_box(
            bm, size=(portal_w + 0.16, 0.20, 0.18),
            location=(cx, y_wall, z_deck + portal_h + 0.02),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Solid threshold plate bridging the wall passage (laid after carving)
        if into_building > 0:
            th_y = y_wall + 0.05
        else:
            th_y = y_wall - 0.05
        create_beveled_box(
            bm, size=(portal_w - 0.10, 1.30, 0.10),
            location=(cx, th_y, z_deck + 0.01),
            mat_index=trim_mat, bevel_amount=0.01
        )

    # South portal into Great Hall / East Hall (wall plane at y_start)
    _wing_portal(y_start, z_low, -1)
    # North portal into Keep / Archive Hall (wall plane at wall_n)
    _wing_portal(wall_n, z_high, +1)

    # 6. STONE ARCADE PIERS DOWN TO BEDROCK (the wing spans the cliff drop, so
    # discrete piers carry it wherever the ground falls away beneath the decks)
    from .nasher_site import ground_z as _wing_ground_z
    pier_ys = (y_start + 2.0, (y_start + stair_y_start) * 0.5 + 1.0,
               (stair_y_start + stair_y_end) * 0.5,
               (stair_y_end + deck_n) * 0.5, deck_n - 2.0)
    for py in pier_ys:
        if py < y_start + 0.8 or py > deck_n - 0.8:
            continue
        if py < stair_y_start:
            deck_pro = z_low
        elif py > stair_y_end:
            deck_pro = z_high
        else:
            deck_pro = z_low + (z_high - z_low) * (py - stair_y_start) / max(0.5, stair_y_end - stair_y_start)
        rock = _wing_ground_z(cx - half_w, py)
        for qx in (cx - half_w + 0.6, cx + half_w - 0.6, cx):
            rock_q = min(rock, _wing_ground_z(qx, py))
        pier_top = deck_pro - 0.25
        pier_bot = rock_q - 0.50
        if pier_top - pier_bot < 0.8:
            continue
        create_beveled_box(
            bm, size=(width + 0.50, 0.90, pier_top - pier_bot),
            location=(cx, py, pier_bot + (pier_top - pier_bot) * 0.5),
            mat_index=wall_mat, bevel_amount=0.03
        )
        create_beveled_box(
            bm, size=(width + 0.70, 1.10, 0.30),
            location=(cx, py, pier_top - 0.15),
            mat_index=trim_mat, bevel_amount=0.03
        )

    # 7. FITTED GALLERY INTERIOR (corridor + reading room, all furniture clear
    # of the central walking lane, both portals and the bridge-door lane)
    from .furniture import build_bench
    from .interior_furniture import (
        build_bookshelf_neat, build_chair, build_desk, build_candlestick, build_rug,
    )
    x_west = cx - half_w + 0.85
    x_east = cx + half_w - 0.85

    def _clear_of_lanes(fx, fy, fr=0.55):
        if abs(fx - cx) < lane_half + fr and y_start < fy < deck_n:
            return False
        if door_lane is not None and fx > cx and door_lane[0] - fr < fy < door_lane[1] + fr:
            return False
        return True

    # Lower gallery: runner carpet down the walking lane (flat, walkable)
    run_len = max(2.0, stair_y_start - y_start - 3.0)
    build_rug(bm, cx, y_start + 1.5 + run_len * 0.5, z_ground=z_low + 0.04,
              ang=0.0, width=1.9, length=run_len, rug_style=2, z_floor=z_low + 0.04)
    # Benches along the west wall of the lower gallery
    for by in (y_start + 3.5, y_start + 6.5):
        if by < stair_y_start - 1.2 and _clear_of_lanes(x_west, by, 0.45):
            build_bench(bm, x_west, by, z_ground=z_low + 0.04, ang=math.pi * 0.5, length=1.75)
    # Standing candlesticks flanking the lower gallery (east side)
    for cy_f in (y_start + 4.2, y_start + 7.6):
        if cy_f < stair_y_start - 1.0 and _clear_of_lanes(x_east, cy_f, 0.35):
            build_candlestick(bm, x_east, cy_f, z_ground=z_low + 0.04, ang=0.0)
    # Bookshelf against the west wall halfway up the lower gallery
    shelf_y = (y_start + stair_y_start) * 0.5 + 2.2
    if shelf_y < stair_y_start - 1.4 and _clear_of_lanes(x_west, shelf_y, 0.75):
        build_bookshelf_neat(bm, x_west, shelf_y, z_ground=z_low + 0.04, ang=math.pi * 0.5, width=1.6)

    # Upper reading room: rug, writing desk + chair, bookshelf (west side so the
    # bridge-door lane on the east stays completely clear)
    up_c = (stair_y_end + deck_n) * 0.5
    if deck_n - stair_y_end > 4.5:
        build_rug(bm, cx, up_c, z_ground=z_high + 0.04,
                  ang=0.0, width=2.0, length=min(4.5, deck_n - stair_y_end - 2.5),
                  rug_style=1, z_floor=z_high + 0.04)
        if _clear_of_lanes(x_west, up_c - 0.6, 0.85):
            build_desk(bm, x_west, up_c - 0.6, z_ground=z_high + 0.04, ang=math.pi * 0.5, width=1.4)
            if _clear_of_lanes(x_west + 0.85, up_c - 0.6, 0.4):
                build_chair(bm, x_west + 0.85, up_c - 0.6, z_ground=z_high + 0.04, ang=-math.pi * 0.5)
        if _clear_of_lanes(x_west, up_c + 1.6, 0.75):
            build_bookshelf_neat(bm, x_west, up_c + 1.6, z_ground=z_high + 0.04, ang=math.pi * 0.5, width=1.6)
        if _clear_of_lanes(x_east if not has_bridge_door else cx, up_c + 0.4, 0.45) and not has_bridge_door:
            build_bench(bm, x_east, up_c + 0.4, z_ground=z_high + 0.04, ang=-math.pi * 0.5, length=1.5)
        if _clear_of_lanes(x_east, up_c - 1.6, 0.35):
            build_candlestick(bm, x_east, up_c - 1.6, z_ground=z_high + 0.04, ang=0.0)

    # (North portal is handled by _wing_portal above, at the wall_n plane.)


def build_wooden_bridge(
    bm,
    p_start=(19.8, 26.0),
    p_end=(43.6, 26.0),
    floor_z=14.0,
    width=2.6,
    deck_mat=MAT_INDEX_WOOD,
    timber_mat=MAT_INDEX_TIMBER,
    trim_mat=MAT_INDEX_CUT_STONE,
    roof_mat=MAT_INDEX_SHINGLES,
):
    """
    Constructs a cozy covered wooden trestle bridge spanning between the East Wing
    and the East Bluff Tower across the cliff chasm.

    Features:
    - Vertical braced timber trestle bents anchored in bedrock.
    - Heavy timber longitudinal stringers supporting an oak plank deck.
    - Timber balustrades with diagonal X-braced railings.
    - Cozy gabled shingle canopy roof with king-post trusses.
    - Fully walkable from East Wing to East Bluff Tower.
    """
    from .nasher_site import ground_z
    x0, y0 = p_start
    x1, y1 = p_end
    span_len = math.hypot(x1 - x0, y1 - y0)
    if span_len < 1.0:
        return

    dx = (x1 - x0) / span_len
    dy = (y1 - y0) / span_len
    yaw = math.atan2(dy, dx)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    half_w = width * 0.5

    # 1. TIMBER TRESTLE BENTS (Vertical timber piers rising from cliff rock)
    bent_xs = (x0 + span_len * 0.33, x0 + span_len * 0.67)
    for bx in bent_xs:
        by = y0 + dy * (bx - x0)
        rock_z = ground_z(bx, by)
        bent_h = max(1.5, floor_z - rock_z - 0.25)
        pier_cz = rock_z + bent_h * 0.5
        # Cut-stone pad footings
        for ps in (-1.0, 1.0):
            py = by + ps * (half_w - 0.35)
            create_beveled_box(
                bm, size=(0.65, 0.65, 0.40),
                location=(bx, py, rock_z + 0.20),
                mat_index=trim_mat, bevel_amount=0.03
            )
            create_beveled_box(
                bm, size=(0.28, 0.28, bent_h),
                location=(bx, py, pier_cz),
                mat_index=timber_mat, bevel_amount=0.015
            )
        # Horizontal cross ledger timber
        create_beveled_box(
            bm, size=(0.24, width - 0.20, 0.28),
            location=(bx, by, floor_z - 0.20),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Diagonal X-brace timbers
        create_beveled_box(
            bm, size=(0.14, width - 0.40, 0.16),
            location=(bx, by, pier_cz),
            rotation=(0.35, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(0.14, width - 0.40, 0.16),
            location=(bx, by, pier_cz),
            rotation=(-0.35, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 2. LONGITUDINAL TIMBER STRINGERS UNDER DECK
    for s_side in (-1.0, 0.0, 1.0):
        sy = cy + s_side * (half_w - 0.25)
        create_beveled_box(
            bm, size=(span_len + 0.30, 0.26, 0.36),
            location=(cx, sy, floor_z - 0.18),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.015
        )

    # 3. WOODEN WALKWAY DECK & CURBS
    create_beveled_box(
        bm, size=(span_len, width - 0.10, 0.08),
        location=(cx, cy, floor_z + 0.04),
        rotation=(0.0, 0.0, yaw),
        mat_index=deck_mat, bevel_amount=0.005
    )
    for s_side in (-1.0, 1.0):
        cy_curb = cy + s_side * (half_w - 0.10)
        create_beveled_box(
            bm, size=(span_len + 0.20, 0.18, 0.18),
            location=(cx, cy_curb, floor_z + 0.13),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 4. TIMBER BALUSTRADES & HANDRAILS
    n_posts = max(4, int(span_len / 2.2))
    post_step = span_len / n_posts
    for side in (-1.0, 1.0):
        py = cy + side * (half_w - 0.10)
        create_beveled_box(
            bm, size=(span_len + 0.10, 0.15, 0.12),
            location=(cx, py, floor_z + 1.10),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(span_len + 0.10, 0.10, 0.08),
            location=(cx, py, floor_z + 0.55),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.008
        )
        for pi in range(n_posts + 1):
            px = x0 + pi * post_step
            create_beveled_box(
                bm, size=(0.16, 0.16, 2.70),
                location=(px, py, floor_z + 1.35),
                rotation=(0.0, 0.0, yaw),
                mat_index=timber_mat, bevel_amount=0.01
            )
            if pi < n_posts:
                mid_px = px + post_step * 0.5
                create_beveled_box(
                    bm, size=(post_step * 0.95, 0.06, 0.08),
                    location=(mid_px, py, floor_z + 0.82),
                    rotation=(0.0, 0.28, yaw),
                    mat_index=timber_mat, bevel_amount=0.005
                )
                create_beveled_box(
                    bm, size=(post_step * 0.95, 0.06, 0.08),
                    location=(mid_px, py, floor_z + 0.82),
                    rotation=(0.0, -0.28, yaw),
                    mat_index=timber_mat, bevel_amount=0.005
                )

    # 5. COZY COVERED SHINGLE ROOF CANOPY
    eave_z = floor_z + 2.70
    ridge_z = eave_z + 1.20
    roof_w = width + 0.70
    pitch_len = math.hypot(roof_w * 0.5, ridge_z - eave_z)
    pitch_ang = math.atan2(ridge_z - eave_z, roof_w * 0.5)

    for side in (-1.0, 1.0):
        r_py = cy + side * (roof_w * 0.25)
        create_beveled_box(
            bm, size=(span_len + 0.60, pitch_len, 0.12),
            location=(cx, r_py, (eave_z + ridge_z) * 0.5),
            rotation=(side * pitch_ang, 0.0, yaw),
            mat_index=roof_mat, bevel_amount=0.015
        )
    create_beveled_box(
        bm, size=(span_len + 0.70, 0.20, 0.18),
        location=(cx, cy, ridge_z + 0.05),
        rotation=(0.0, 0.0, yaw),
        mat_index=timber_mat, bevel_amount=0.01
    )
    for pi in range(n_posts + 1):
        px = x0 + pi * post_step
        create_beveled_box(
            bm, size=(0.14, width + 0.10, 0.18),
            location=(px, cy, eave_z),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.01
        )


def chain_buildings(bm, building_nodes, links_spec):
    """
    High-level generator that chains a collection of buildings together using
    skybridges, gallerias, and vestibules according to a topology specification.
    """
    for link in links_spec:
        b1 = building_nodes.get(link['from'])
        b2 = building_nodes.get(link['to'])
        if not b1 or not b2:
            continue
        p1 = (b1['pos'][0], b1['pos'][1])
        p2 = (b2['pos'][0], b2['pos'][1])
        fz = link.get('floor_z', min(b1['pos'][2], b2['pos'][2]) + 7.4)
        build_skybridge_link(
            bm, p1, p2,
            width=link.get('width', 9.0),
            floor_z=fz,
            ceiling_h=link.get('ceiling_h', 3.6),
            roof_style=link.get('roof_style', 'BATTLEMENTS'),
            has_windows=link.get('has_windows', True),
            num_windows=link.get('num_windows', 2),
            has_underpass_arch=link.get('has_underpass_arch', True),
            underpass_spring_z=link.get('underpass_spring_z', fz - 6.0)
        )

