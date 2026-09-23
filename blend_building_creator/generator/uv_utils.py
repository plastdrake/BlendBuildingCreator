"""
Shared UV mapping helpers.

Single home for the projection conventions used across every generator so that
walls, shingles and hand-built faces all tile consistently. Keeping these here
(instead of duplicated per accessory) is the DRY counterpart to the geometry
builders in ``mesh_utils``.
"""

from mathutils import Euler, Matrix, Vector

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


def map_beam_uvs(bm, faces, size, location=(0.0, 0.0, 0.0),
                 rotation=(0.0, 0.0, 0.0)):
    """Grain-along-length unwrap for a timber post/beam/pillar box.

    Uses the engine's own convention (wood grain runs along V, V follows the
    box's longest local axis - the same rule ``create_box`` applies to flat
    faces) but writes it onto EVERY face of an already built, possibly beveled
    and arbitrarily rotated box, so the result never depends on bevel-UV
    interpolation. End caps get a planar map of the two short axes; every
    side face gets U across the beam and V along it, so the grain always runs
    down the length of the board.
    """
    uv = bm.loops.layers.uv.verify()
    dx, dy, dz = float(size[0]), float(size[1]), float(size[2])
    if dz >= dx and dz >= dy:
        long_ax = 2
    elif dx >= dy and dx >= dz:
        long_ax = 0
    else:
        long_ax = 1
    if long_ax == 2:
        su = sv = 1.0
        su_end = 1.0
    else:
        su = 1.2
        sv = 0.40
        su_end = 1.2
    eul = rotation if isinstance(rotation, Euler) else Euler(rotation, 'XYZ')
    inv_rot = eul.to_matrix().inverted()
    inv_tr = (Matrix.Translation(Vector(location)) @ eul.to_matrix().to_4x4()).inverted()
    shorts = [a for a in range(3) if a != long_ax]
    bm.normal_update()
    for face in faces:
        ln = inv_rot @ face.normal
        la = (abs(ln.x), abs(ln.y), abs(ln.z))
        dom = 0 if (la[0] >= la[1] and la[0] >= la[2]) else (1 if la[1] >= la[2] else 2)
        face.tag = True
        for loop in face.loops:
            c = inv_tr @ loop.vert.co
            if dom == long_ax:
                loop[uv].uv = (c[shorts[0]] * su_end, c[shorts[1]] * su_end)
            else:
                across = shorts[0] if dom == shorts[1] else shorts[1]
                loop[uv].uv = (c[across] * su, c[long_ax] * sv)


def timber_box(bm, size, location, rotation=(0.0, 0.0, 0.0), mat_index=0,
               bevel_amount=0.012):
    """A ``create_beveled_box`` whose faces are all re-unwrapped afterwards so
    the wood grain provably runs along the beam's length on every face
    (flat faces and bevel strips alike), at any plan rotation.
    """
    from .mesh_utils import create_beveled_box
    faces = create_beveled_box(bm, size=size, location=location,
                               rotation=rotation, mat_index=mat_index,
                               bevel_amount=bevel_amount)
    map_beam_uvs(bm, faces, size=size, location=location, rotation=rotation)
    return faces
