"""Reusable gate fixtures.

The gatehouse framing itself lives in :mod:`curtain_wall`; this module owns the
moving parts that dress a gate opening:

- :func:`build_portcullis` - an iron grille gate (bars + rails + side channels)

It is deliberately independent of any footprint so the Knights Manor curtains,
the palisade gate and any future gatehouse can all reuse it.
"""

import math

from ..mesh_utils import create_cylinder, create_cone, create_beveled_box
from ..materials import MAT_INDEX_IRON, MAT_INDEX_TIMBER


def build_portcullis(bm, cx, cy, z_ground=0.0, width=2.6, height=2.9,
                     outward=(0.0, -1.0), raised=0.30):
    """An iron portcullis seated in a gate opening.

    ``outward`` is the horizontal normal of the wall the gate sits in; the
    grille is built in the gate plane. ``raised`` lifts the spiked bottom a
    little off the ground so it reads as a part-raised gate.
    """
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = 0.0, -1.0
    else:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox                      # wall tangent
    ang = math.atan2(ty, tx)

    z0 = z_ground + raised
    z1 = z_ground + height

    # Side guide channels biting into the jambs.
    for s in (-1.0, 1.0):
        px = cx + tx * (s * (width * 0.5 + 0.09))
        py = cy + ty * (s * (width * 0.5 + 0.09))
        create_beveled_box(bm, size=(0.14, 0.22, height + 0.20),
                           location=(px, py, z_ground + (height + 0.20) * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # Vertical bars with spiked feet.
    n_bars = max(3, int(round(width / 0.34)))
    step = width / (n_bars + 1)
    for i in range(1, n_bars + 1):
        u = -width * 0.5 + i * step
        bx = cx + tx * u
        by = cy + ty * u
        create_cylinder(bm, radius=0.045, height=z1 - z0, segments=6,
                        location=(bx, by, (z0 + z1) * 0.5),
                        rotation=(1.5707963, 0.0, ang), mat_index=MAT_INDEX_IRON)
        create_cone(bm, radius1=0.05, radius2=0.0, height=0.16, segments=6,
                    location=(bx, by, z0 - 0.08),
                    rotation=(0.0, math.pi, ang), mat_index=MAT_INDEX_IRON)

    # Horizontal rails across the grille.
    for rz in (z0 + 0.12, (z0 + z1) * 0.5, z1 - 0.14):
        create_beveled_box(bm, size=(width + 0.10, 0.10, 0.10),
                           location=(cx, cy, rz), rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
