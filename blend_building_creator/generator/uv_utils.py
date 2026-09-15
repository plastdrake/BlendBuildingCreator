"""
Shared UV mapping helpers.

Single home for the projection conventions used across every generator so that
walls, shingles and hand-built faces all tile consistently. Keeping these here
(instead of duplicated per accessory) is the DRY counterpart to the geometry
builders in ``mesh_utils``.
"""

from mathutils import Matrix, Vector

from .materials import MAT_INDEX_SHINGLES


def map_planar_faces(bm, faces, scale=0.5, axis=None):
    """Force clean planar UVs on faces, using the same V-vertical convention as
    the engine walls: X-facing -> U along Y / V up Z, Y-facing -> U along X / V up
    Z, horizontal -> U along X / V along Y.

    When ``axis`` is None the axis is chosen per face from its own normal so
    mixed face groups (lean-to cheeks, gable triangles) all read right instead
    of collapsing to a sliver.
    """
    uv = bm.loops.layers.uv.verify()
    if axis is None:
        bm.normal_update()
    for face in faces:
        if axis is None:
            n = face.normal
            ax = 0 if abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z) else (1 if abs(n.y) >= abs(n.z) else 2)
        else:
            ax = axis
        face.tag = True
        for loop in face.loops:
            co = loop.vert.co
            if ax == 0:      # X-facing: U along Y, V vertical
                loop[uv].uv = (co.y * scale, co.z * scale)
            elif ax == 1:    # Y-facing: U along X, V vertical
                loop[uv].uv = (co.x * scale, co.z * scale)
            else:            # horizontal: U along X, V along Y
                loop[uv].uv = (co.x * scale, co.y * scale)


def map_local_wall_uv(bm, faces, wx, wy, facade_rot_mat, u_comp=1, v_comp=2, scale=0.55):
    """Assign planar UVs in the facade-local frame to manually built faces
    (outcrop cheeks / gable triangles) so tier 1-2 wood faces are not left with
    default UVs by the global box-UV pass.

    ``u_comp``/``v_comp`` pick the local component (0=x, 1=y, 2=z) for U and V.
    """
    inv_tr = (Matrix.Translation(Vector((wx, wy, 0.0))) @ facade_rot_mat).inverted()
    uv = bm.loops.layers.uv.verify()
    for face in faces:
        face.tag = True
        for loop in face.loops:
            lc = inv_tr @ loop.vert.co
            comp = (lc.x, lc.y, lc.z)
            loop[uv].uv = Vector((comp[u_comp] * scale, comp[v_comp] * scale))


def apply_roof_shingle_uvs(bm, faces, mat_index=MAT_INDEX_SHINGLES, scale=0.32, rot_deg=0):
    """World-aligned shingle UVs for sloped roof faces.

    Matches the engine roof deck exactly: U runs ``scale``/m along the eave and V
    runs ``scale``/m down the slope, decreasing toward the eave, so the tile tips
    always point downward.

    The axes are derived from each face's own normal, and the eave axis is
    canonicalised to a fixed world direction, so every slope (pyramid spires,
    lean-to slabs, gable slopes) receives identically oriented and identically
    scaled shingles no matter how it is positioned or rotated. Near-horizontal
    cap faces are skipped.
    """
    bm.normal_update()
    uv = bm.loops.layers.uv.verify()
    for face in faces:
        if mat_index is not None and face.material_index != mat_index:
            continue
        n = face.normal.copy()
        if n.length < 1e-6:
            continue
        n.normalize()
        # Skip vertical skirts (no slope direction) and near-horizontal caps.
        if abs(n.z) < 0.02:
            continue
        if (n.x * n.x + n.y * n.y) < 0.02:
            continue
        # Steepest-descending direction within the roof plane (points downhill).
        d = Vector((n.z * n.x, n.z * n.y, -(n.x * n.x + n.y * n.y)))
        if d.length < 1e-6:
            continue
        d.normalize()
        # Horizontal eave direction (perpendicular to the aspect, in-plane).
        t = Vector((-n.y, n.x, 0.0))
        if t.length < 1e-6:
            continue
        t.normalize()
        # Canonicalise the eave axis so mirrored slopes - a gable's left and
        # right halves, or the same outcrop on opposite facades - unwrap in the
        # same direction instead of mirroring the shingle pattern.
        if abs(t.x) >= abs(t.y):
            if t.x < 0.0:
                t = -t
        elif t.y < 0.0:
            t = -t
        center = face.calc_center_median()
        face.smooth = False
        face.tag = True
        r = rot_deg % 360
        for loop in face.loops:
            rel = loop.vert.co - center
            u = rel.dot(t) * scale
            v = -rel.dot(d) * scale
            if r == 90:
                u, v = v, -u
            elif r == 180:
                u, v = -u, -v
            elif r == 270:
                u, v = -v, u
            loop[uv].uv = Vector((u, v))
