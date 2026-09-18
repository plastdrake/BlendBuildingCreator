"""Reusable gable banner plaque.

A plain flat plane wearing the heraldic banner material, mounted a few
centimetres off a gable face so it tucks behind the timber framing. The old
shield-and-swords cartouche was retired in favour of this simpler banner.
"""

from mathutils import Vector
from ..materials import MAT_INDEX_BANNER


def _basis_from_normal(normal):
    """Build an orthonormal basis (right, up, forward) from a forward normal vector."""
    fn = Vector(normal).normalized()
    if fn.length < 1e-4:
        fn = Vector((0.0, -1.0, 0.0))
    if abs(fn.z) > 0.95:
        up_ref = Vector((0.0, 1.0, 0.0))
    else:
        up_ref = Vector((0.0, 0.0, 1.0))
    right = up_ref.cross(fn).normalized()
    up = fn.cross(right).normalized()
    return right, up, fn


def build_gable_heraldic_crest(bm, location, normal=(0.0, -1.0, 0.0), scale=1.0,
                               style='BANNER'):
    """A flat banner plane mounted on a gable face.

    ``style`` is kept for API compatibility only.
    """
    rx, ry, rz = location
    right, up, fn = _basis_from_normal(normal)

    w = 0.75 * scale
    h = 1.05 * scale
    base = Vector((rx, ry, rz))
    corners = [(-w * 0.5, -h * 0.5), (w * 0.5, -h * 0.5),
               (w * 0.5, h * 0.5), (-w * 0.5, h * 0.5)]
    verts = [bm.verts.new(base + right * x + up * y) for x, y in corners]

    face = bm.faces.new(verts)
    face.material_index = MAT_INDEX_BANNER
    face.tag = True

    uv_layer = bm.loops.layers.uv.verify()
    for loop, uv in zip(face.loops, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]):
        loop[uv_layer].uv = Vector(uv)
