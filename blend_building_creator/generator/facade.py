"""
Facade frame helpers.

Every accessory (outcrops, overhangs, balconies, cargo ports, civic landmarks)
needs the same information: where a wall is, which way it faces outward, which
way it runs tangentially, and the Z rotation that aligns logic to that facade.
``FacadeFrame`` packages that once so callers stop re-deriving it.
"""

import math
from typing import NamedTuple

from mathutils import Matrix, Vector


class FacadeFrame(NamedTuple):
    """A wall facade expressed in world space.

    Unpacks as the historical ``(wx, wy, ox, oy, tx, ty, rot_z)`` 7-tuple, but
    also carries the convenience methods used by newer code.
    """

    wall_x: float
    wall_y: float
    out_x: float
    out_y: float
    tan_x: float
    tan_y: float
    rot_z: float

    @property
    def rotation(self) -> Matrix:
        return Matrix.Rotation(self.rot_z, 4, 'Z')

    @property
    def outward(self) -> Vector:
        return Vector((self.out_x, self.out_y, 0.0))

    @property
    def tangent(self) -> Vector:
        return Vector((self.tan_x, self.tan_y, 0.0))

    def to_world(self, local) -> Vector:
        """Map a facade-local point (x = outward, y = along wall, z = up) to world."""
        local_vec = local if isinstance(local, Vector) else Vector(local)
        return Vector((self.wall_x, self.wall_y, 0.0)) + (self.rotation @ local_vec.to_4d()).to_3d()


def get_facade_frame(side, wall_x_min, wall_x_max, wall_y_min, wall_y_max) -> FacadeFrame:
    """Return the :class:`FacadeFrame` for a named wall of an axis-aligned box."""
    if side == 'LEFT':  # -X
        return FacadeFrame(wall_x_min, (wall_y_min + wall_y_max) * 0.5, -1.0, 0.0, 0.0, 1.0, math.pi)
    if side == 'RIGHT':  # +X
        return FacadeFrame(wall_x_max, (wall_y_min + wall_y_max) * 0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
    if side == 'BACK':  # +Y
        return FacadeFrame((wall_x_min + wall_x_max) * 0.5, wall_y_max, 0.0, 1.0, 1.0, 0.0, math.pi * 0.5)
    # FRONT (-Y)
    return FacadeFrame((wall_x_min + wall_x_max) * 0.5, wall_y_min, 0.0, -1.0, 1.0, 0.0, -math.pi * 0.5)
