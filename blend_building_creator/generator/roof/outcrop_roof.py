"""
Outcrop roof builders.

Small self-contained lean-to and mini-gable roofs for facade projections
(mini-wing outcrops, oriel bays). They live in the roof package so outcrops
reuse the same shingle UV convention as the main roofs instead of hand-rolling
their own, and they take a :class:`~generator.facade.FacadeFrame` so all the
geometry is authored in facade-local coordinates.
"""

import math
from mathutils import Euler, Matrix, Vector

from ..mesh_utils import create_beveled_box
from ..materials import MAT_INDEX_SHINGLES, MAT_INDEX_TIMBER_FRAME
from ..uv_utils import apply_roof_shingle_uvs, map_planar_faces


def _shingle_plane(bm, center, rotation, half_x, half_y, up_offset=0.0,
                   mat_index=MAT_INDEX_SHINGLES):
    """A single flat shingle surface in a local slope frame.

    The roof edges are capped by timber bargeboards, purlins and ridge beams, so
    the visible skin needs no slab thickness - one correctly-wound quad keeps the
    geometry light and gives the shingle unwrap an exact plane to work with.
    """
    basis = Euler(rotation, 'XYZ').to_matrix()
    c = Vector(center)
    corners = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    verts = [bm.verts.new(c + basis @ Vector((lx, ly, up_offset))) for lx, ly in corners]
    face = bm.faces.new(verts)
    face.material_index = mat_index
    return face


def build_lean_to_roof(bm, frame, z_roof, depth, width, avail_h, wall_mat,
                       wall_thick=0.12, shingle_scale=0.32, shingle_rot=0):
    """Sloping shed roof over a facade projection, with sealed side cheeks."""
    half_w = width * 0.5
    roof_pitch = 0.32
    r_rise = min(avail_h, depth * roof_pitch)
    x_back = -0.01
    x_front = depth + 0.16
    roof_len = x_front - x_back
    r_len = math.sqrt(roof_len * roof_len + r_rise * r_rise)
    r_ang = math.atan2(r_rise, roof_len)
    rx_vec = Vector((math.cos(-r_ang), 0.0, math.sin(-r_ang)))
    ry_vec = Vector((0.0, 1.0, 0.0))
    rz_vec = Vector((-math.sin(-r_ang), 0.0, math.cos(-r_ang)))
    local_rot_mat = Matrix((rx_vec, ry_vec, rz_vec)).transposed().to_4x4()
    roof_euler = (frame.rotation @ local_rot_mat).to_euler()

    mid_x = (x_front + x_back) * 0.5
    mid_z = z_roof + r_rise * 0.5 + 0.06
    world_shingle = frame.to_world(Vector((mid_x, 0.0, mid_z)))
    lean_face = _shingle_plane(
        bm, world_shingle, roof_euler, r_len * 0.5, (width + 0.34) * 0.5, up_offset=0.04
    )
    apply_roof_shingle_uvs(bm, [lean_face], scale=shingle_scale, rot_deg=shingle_rot)

    # Front eave purlin beam capping the slab's front edge
    create_beveled_box(
        bm,
        size=(0.10, width + 0.38, 0.14),
        location=frame.to_world(Vector((x_front - 0.04, 0.0, z_roof + 0.04))),
        rotation=roof_euler,
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )

    # Side triangular cheek closure walls & sloping timber bargeboards
    cheek_faces = []
    for s_sign in [-1, 1]:
        create_beveled_box(
            bm,
            size=(r_len + 0.04, 0.08, 0.12),
            location=frame.to_world(Vector((mid_x, (half_w + 0.16) * s_sign, mid_z))),
            rotation=roof_euler,
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )
        # Sloping timber rafter plate atop the side wall
        create_beveled_box(
            bm,
            size=(r_len, wall_thick + 0.02, 0.10),
            location=frame.to_world(Vector((mid_x, (half_w - wall_thick * 0.5) * s_sign, mid_z - 0.06))),
            rotation=roof_euler,
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )
        # Solid triangular cheek prism filling wedge between flat side wall top and sloping rafter
        tri_y_center = (half_w - wall_thick * 0.5) * s_sign
        half_t = wall_thick * 0.5
        v_t_b1 = bm.verts.new(frame.to_world(Vector((0.0, tri_y_center - half_t, z_roof + r_rise))))
        v_b_f1 = bm.verts.new(frame.to_world(Vector((depth, tri_y_center - half_t, z_roof))))
        v_b_b1 = bm.verts.new(frame.to_world(Vector((0.0, tri_y_center - half_t, z_roof))))

        v_t_b2 = bm.verts.new(frame.to_world(Vector((0.0, tri_y_center + half_t, z_roof + r_rise))))
        v_b_f2 = bm.verts.new(frame.to_world(Vector((depth, tri_y_center + half_t, z_roof))))
        v_b_b2 = bm.verts.new(frame.to_world(Vector((0.0, tri_y_center + half_t, z_roof))))

        f1 = bm.faces.new([v_t_b1, v_b_f1, v_b_b1])
        f1.material_index = wall_mat
        f2 = bm.faces.new([v_t_b2, v_b_b2, v_b_f2])
        f2.material_index = wall_mat
        f_slope = bm.faces.new([v_t_b1, v_t_b2, v_b_f2, v_b_f1])
        f_slope.material_index = wall_mat
        f_back = bm.faces.new([v_t_b1, v_b_b1, v_b_b2, v_t_b2])
        f_back.material_index = wall_mat
        cheek_faces.extend([f1, f2, f_slope, f_back])

    if cheek_faces:
        map_planar_faces(bm, cheek_faces, scale=0.55)


def build_outcrop_gable_roof(bm, frame, z_roof, depth, width, avail_h, wall_mat,
                             shingle_scale=0.32, shingle_rot=0):
    """Pitched mini-gable roof over a facade projection (ridge runs outward)."""
    half_w = width * 0.5
    g_roof_h = min(avail_h, 0.58)
    x_back = -0.03
    x_front = depth + 0.16
    roof_len = x_front - x_back
    mid_x = (x_front + x_back) * 0.5
    roof_half_w = half_w + 0.16
    r_pitch_len = math.sqrt(roof_half_w ** 2 + g_roof_h ** 2)
    r_pitch_ang = math.atan2(g_roof_h, roof_half_w)

    # 1. Front Triangular Gable Wall (apex tucked cleanly under roof deck)
    tri_x = depth - 0.04
    tri_half_w = half_w - 0.02
    tri_apex_z = z_roof + g_roof_h - 0.06
    tri_t = 0.08

    v_apex_f = bm.verts.new(frame.to_world(Vector((tri_x, 0.0, tri_apex_z))))
    v_left_f = bm.verts.new(frame.to_world(Vector((tri_x, -tri_half_w, z_roof + 0.02))))
    v_right_f = bm.verts.new(frame.to_world(Vector((tri_x, tri_half_w, z_roof + 0.02))))

    v_apex_b = bm.verts.new(frame.to_world(Vector((tri_x - tri_t, 0.0, tri_apex_z))))
    v_left_b = bm.verts.new(frame.to_world(Vector((tri_x - tri_t, -tri_half_w, z_roof + 0.02))))
    v_right_b = bm.verts.new(frame.to_world(Vector((tri_x - tri_t, tri_half_w, z_roof + 0.02))))

    gable_faces = []
    f_tri_f = bm.faces.new([v_apex_f, v_right_f, v_left_f])
    f_tri_f.material_index = wall_mat
    f_tri_b = bm.faces.new([v_apex_b, v_left_b, v_right_b])
    f_tri_b.material_index = wall_mat
    f_tri_l = bm.faces.new([v_apex_f, v_left_f, v_left_b, v_apex_b])
    f_tri_l.material_index = wall_mat
    f_tri_r = bm.faces.new([v_apex_f, v_apex_b, v_right_b, v_right_f])
    f_tri_r.material_index = wall_mat
    f_tri_bot = bm.faces.new([v_left_f, v_right_f, v_right_b, v_left_b])
    f_tri_bot.material_index = wall_mat
    gable_faces.extend([f_tri_f, f_tri_b, f_tri_l, f_tri_r, f_tri_bot])

    # 2. Horizontal Collar Tie Beam across base of front gable
    create_beveled_box(
        bm,
        size=(0.12, width + 0.08, 0.12),
        location=frame.to_world(Vector((tri_x + 0.02, 0.0, z_roof + 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )

    # 3. Vertical King Post Beam in gable center
    king_h = max(0.18, g_roof_h - 0.16)
    create_beveled_box(
        bm,
        size=(0.10, 0.12, king_h),
        location=frame.to_world(Vector((tri_x + 0.02, 0.0, z_roof + 0.10 + king_h * 0.5))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.008
    )

    # 4. Pitched Roof Slopes (Left & Right) with Parametric Shingle UV Mapping
    slope_thickness = 0.08
    for s_sign in [-1, 1]:
        sx_vec = Vector((1.0, 0.0, 0.0))
        sy_vec = Vector((0.0, math.cos(s_sign * r_pitch_ang), -math.sin(s_sign * r_pitch_ang)))
        sz_vec = Vector((0.0, math.sin(s_sign * r_pitch_ang), math.cos(s_sign * r_pitch_ang)))
        g_rot = (frame.rotation @ Matrix((sx_vec, sy_vec, sz_vec)).transposed().to_4x4()).to_euler()

        world_slope = frame.to_world(Vector((mid_x, (roof_half_w * 0.5) * s_sign, z_roof + g_roof_h * 0.5 + 0.02)))
        slope_face = _shingle_plane(
            bm, world_slope, g_rot, roof_len * 0.5, r_pitch_len * 0.5,
            up_offset=slope_thickness * 0.5
        )
        apply_roof_shingle_uvs(bm, [slope_face], scale=shingle_scale, rot_deg=shingle_rot)

        # 5. Sloping timber bargeboard along front edge of this slope
        create_beveled_box(
            bm,
            size=(0.08, r_pitch_len + 0.04, 0.14),
            location=frame.to_world(Vector((x_front - 0.02, (roof_half_w * 0.5) * s_sign, z_roof + g_roof_h * 0.5 + 0.03))),
            rotation=g_rot,
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.008
        )

        # 5b. Horizontal timber eave fascia beam capping the low edge of this slope
        create_beveled_box(
            bm,
            size=(roof_len + 0.04, 0.10, 0.14),
            location=frame.to_world(Vector((mid_x, s_sign * (roof_half_w - 0.02), z_roof + 0.04))),
            rotation=(0.0, 0.0, frame.rot_z),
            mat_index=MAT_INDEX_TIMBER_FRAME,
            bevel_amount=0.010
        )

    # 6. Horizontal Timber Ridge Cap Beam along ridge line
    create_beveled_box(
        bm,
        size=(roof_len + 0.02, 0.14, 0.12),
        location=frame.to_world(Vector((mid_x, 0.0, z_roof + g_roof_h + 0.04))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.010
    )

    # 7. Apex Finial Cap Block at front ridge peak
    create_beveled_box(
        bm,
        size=(0.12, 0.16, 0.18),
        location=frame.to_world(Vector((x_front + 0.01, 0.0, z_roof + g_roof_h + 0.05))),
        rotation=(0.0, 0.0, frame.rot_z),
        mat_index=MAT_INDEX_TIMBER_FRAME,
        bevel_amount=0.012
    )

    if gable_faces:
        map_planar_faces(bm, gable_faces, scale=0.55)


def build_outcrop_roof(bm, style, frame, z_roof, depth, width, avail_h, wall_mat,
                       wall_thick=0.12, shingle_scale=0.32, shingle_rot=0):
    """Dispatch to the lean-to or gable outcrop roof builder."""
    if style == 'GABLE':
        build_outcrop_gable_roof(
            bm, frame, z_roof, depth, width, avail_h, wall_mat,
            shingle_scale=shingle_scale, shingle_rot=shingle_rot,
        )
    else:
        build_lean_to_roof(
            bm, frame, z_roof, depth, width, avail_h, wall_mat,
            wall_thick=wall_thick, shingle_scale=shingle_scale, shingle_rot=shingle_rot,
        )
