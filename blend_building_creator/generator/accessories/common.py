import math
from mathutils import Vector, Euler, Matrix
from .mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone, create_horizontal_cylinder,
    create_torus_ring, create_door_batten
)
from .walls import create_curved_corbel
from .materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_SHINGLES, MAT_INDEX_GLASS,
    MAT_INDEX_TIMBER_FRAME, MAT_INDEX_WOOD, MAT_INDEX_DOOR,
    MAT_INDEX_CUT_STONE, MAT_INDEX_LOG
)

def _get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max):
    """
    Returns (wall_anchor_x, wall_anchor_y, out_dx, out_dy, tan_dx, tan_dy, rot_z)
    for a given facade side.
    """
    if side == 'LEFT': # -X
        return (wall_x_min, (wall_y_min + wall_y_max) * 0.5, -1.0, 0.0, 0.0, 1.0, math.pi)
    elif side == 'RIGHT': # +X
        return (wall_x_max, (wall_y_min + wall_y_max) * 0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
    elif side == 'BACK': # +Y
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_max, 0.0, 1.0, 1.0, 0.0, math.pi * 0.5)
    else: # FRONT (-Y)
        return ((wall_x_min + wall_x_max) * 0.5, wall_y_min, 0.0, -1.0, 1.0, 0.0, -math.pi * 0.5)

def _planar_uv_faces(bm, faces, scale=0.5, axis=None):
    """Force planar world-space UVs on faces by dominant normal axis."""
    _uv = bm.loops.layers.uv.verify()
    if axis is None:
        bm.normal_update()
    for _f in faces:
        if axis is None:
            _n = _f.normal
            _ax = 0 if abs(_n.x) >= abs(_n.y) and abs(_n.x) >= abs(_n.z) else (1 if abs(_n.y) >= abs(_n.z) else 2)
        else:
            _ax = axis
        for _lp in _f.loops:
            _c = _lp.vert.co
            _co = (_c.x, _c.y, _c.z)
            _lp[_uv].uv = (_co[(_ax + 1) % 3] * scale, _co[(_ax + 2) % 3] * scale)
