"""
table_ensemble.py - Reusable dining table, chairs, and tableware arrangement module.

Ensures:
- Chairs are correctly rotated to face the table on all sides and ends.
- Chairs maintain proper clearance from table edges and bottom stretchers/beams (never locked in).
- Tableware scatter (plates, bottle clusters, tankards) are positioned at spaced intervals with zero overlapping.
- Seamless integration with RoomOccupancyTracker, rugs, and chandeliers.
"""

import math
from typing import Optional, Dict, Any, Tuple
from .interior_furniture import (
    build_indoor_table, build_chair, build_table_scatter,
    build_bottle_cluster, build_pewter_tankard
)

def build_dining_table_ensemble(
    bm,
    cx: float,
    cy: float,
    z_floor: float,
    z_ceil: Optional[float] = None,
    length: float = 2.80,
    width: float = 1.15,
    yaw: float = 0.0,
    rng: Optional[Any] = None,
    head_chairs: bool = False,
    tableware: bool = True,
    rug: bool = True,
    chandelier: bool = True,
    tracker: Optional[Any] = None,
    chair_h: float = 0.50
) -> Dict[str, Any]:
    """Builds a complete dining table ensemble with properly aligned chairs,

    non-overlapping tableware, and optional rug and overhead chandelier.
    """
    from .furnishing import build_prop

    # 1. Place the Table
    build_prop(bm, 'INDOOR_TABLE', cx, cy, z_floor, yaw, length=length, width=width)
    z_table = z_floor + 0.992

    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)

    def _to_world(lx: float, ly: float) -> Tuple[float, float]:
        return (cx + lx * cos_y - ly * sin_y, cy + lx * sin_y + ly * cos_y)

    # 2. Chairs Along Both Sides
    # In table-local space: table runs along X [-length/2, +length/2], width is along Y [-width/2, +width/2].
    # Chair has depth ~0.56 (half-depth 0.28). In chair local space, front is at -Y, back is at +Y.
    # To place chair outside the tabletop (width/2) and safely clear of the bottom stretcher (width/2 - 0.10):
    # Stand-off from tabletop edge = 0.10m.
    # Center distance from table centerline: width * 0.5 + 0.28 (half-depth) + 0.10 = width * 0.5 + 0.38
    chair_y_dist = width * 0.5 + 0.38

    # Lateral chair distribution
    n_side = max(1, min(6, int((length - 0.50) / 0.75)))
    spacing = (length - 0.70) / max(1, n_side - 1) if n_side > 1 else 0.0

    placed_chairs = 0
    # Side 1 (local +Y, "North" side): chair must face -Y (towards table). Chair local rot = 0.0. World rot = yaw.
    # Side 2 (local -Y, "South" side): chair must face +Y (towards table). Chair local rot = pi. World rot = yaw + pi.
    side_configs = [
        (+chair_y_dist, 0.0),
        (-chair_y_dist, math.pi),
    ]

    for ly_chair, local_rot in side_configs:
        world_chair_yaw = yaw + local_rot
        for i in range(n_side):
            lx_chair = -0.5 * (length - 0.70) + i * spacing if n_side > 1 else 0.0
            wx, wy = _to_world(lx_chair, ly_chair)
            
            can_place = True
            if tracker is not None:
                if not tracker.is_free(wx - 0.26, wx + 0.26, wy - 0.26, wy + 0.26):
                    can_place = False
            
            if can_place:
                if tracker is not None:
                    tracker.occupy(wx - 0.26, wx + 0.26, wy - 0.26, wy + 0.26)
                build_prop(bm, 'CHAIR', wx, wy, z_floor, world_chair_yaw, seat_h=chair_h)
                placed_chairs += 1

    # Head Chairs (at the ends of the table, if requested)
    if head_chairs and length >= 1.80:
        head_x_dist = length * 0.5 + 0.40
        end_configs = [
            (+head_x_dist, -math.pi * 0.5),
            (-head_x_dist, +math.pi * 0.5),
        ]
        for lx_end, local_rot in end_configs:
            wx, wy = _to_world(lx_end, 0.0)
            world_chair_yaw = yaw + local_rot
            can_place = True
            if tracker is not None:
                if not tracker.is_free(wx - 0.28, wx + 0.28, wy - 0.28, wy + 0.28):
                    can_place = False
            if can_place:
                if tracker is not None:
                    tracker.occupy(wx - 0.28, wx + 0.28, wy - 0.28, wy + 0.28)
                build_prop(bm, 'CHAIR', wx, wy, z_floor, world_chair_yaw, seat_h=chair_h + 0.04)
                placed_chairs += 1

    # 3. Non-Overlapping Tableware Scatter
    if tableware:
        usable_span = max(0.40, length - 0.60)
        num_slots = max(1, min(5, int(usable_span / 0.70)))
        slot_step = usable_span / num_slots
        
        for k in range(num_slots):
            lx_slot = -usable_span * 0.5 + (k + 0.5) * slot_step
            item_type = k % 2
            wx, wy = _to_world(lx_slot, 0.0)
            
            if item_type == 0:
                build_prop(bm, 'SCATTER_TABLEWARE', wx, wy, z_table, yaw)
            else:
                build_prop(bm, 'BOTTLE_CLUSTER', wx, wy, z_table, yaw)

    # 4. Area Rug Under the Ensemble
    if rug:
        rug_len = length + 0.80
        rug_wid = width + 1.25
        if tracker is not None:
            tracker.rug_count = getattr(tracker, 'rug_count', 0) + 1
        build_prop(bm, 'RUG_CRIMSON', cx, cy, z_floor + 0.005, yaw,
                   length=rug_len, width=rug_wid)

    # 5. Overhead Hanging Chandelier
    if chandelier and z_ceil is not None and (z_ceil - z_floor) >= 2.5:
        build_prop(bm, 'CHANDELIER', cx, cy, z_ceil - 0.15, 0.0)

    # 6. Reserve Table Bounding Box in Tracker
    if tracker is not None:
        hw = (length * 0.5 + 0.15) if abs(cos_y) > 0.5 else (width * 0.5 + 0.15)
        hd = (width * 0.5 + 0.15) if abs(cos_y) > 0.5 else (length * 0.5 + 0.15)
        tracker.occupy(cx - hw, cx + hw, cy - hd, cy + hd)

    return {
        'cx': cx, 'cy': cy, 'length': length, 'width': width,
        'yaw': yaw, 'placed_chairs': placed_chairs
    }


def try_place_dining_ensemble(
    bm,
    tracker,
    rm,
    z_floor: float,
    z_ceil: Optional[float] = None,
    rng: Optional[Any] = None,
    min_len: float = 2.20,
    max_len: float = 4.20,
    head_chairs: bool = False,
    table_width: float = 1.15
) -> Optional[Dict[str, Any]]:
    """Automatically searches the room bounds to find the best orientation and location

    for a dining table ensemble, avoiding walls, doors, and stairs.
    """
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    preferred_along_y = (rd >= rw)
    orientations = [
        (preferred_along_y, math.pi * 0.5 if preferred_along_y else 0.0),
        (not preferred_along_y, 0.0 if preferred_along_y else math.pi * 0.5)
    ]

    candidate_lengths = [max_len, 3.60, 3.00, 2.60, min_len]
    candidate_lengths = sorted(list({round(min(l, max(rw, rd) * 0.65), 2) for l in candidate_lengths if l >= min_len}), reverse=True)

    # Generate grid search points sorted by distance to room center
    step = 0.40
    xs = []
    x_cur = rm.bounds[0] + 1.20
    while x_cur <= rm.bounds[1] - 1.20:
        xs.append(x_cur)
        x_cur += step
    ys = []
    y_cur = rm.bounds[2] + 1.20
    while y_cur <= rm.bounds[3] - 1.20:
        ys.append(y_cur)
        y_cur += step

    grid = [(x, y) for x in xs for y in ys]
    grid.sort(key=lambda p: (p[0] - rcx)**2 + (p[1] - rcy)**2)

    for along_y, yaw in orientations:
        for t_len in candidate_lengths:
            if along_y:
                hw = table_width * 0.5 + 0.66
                hd = t_len * 0.5 + (0.42 if head_chairs else 0.20)
            else:
                hw = t_len * 0.5 + (0.42 if head_chairs else 0.20)
                hd = table_width * 0.5 + 0.66

            for cx_t, cy_t in grid:
                if tracker.is_free(cx_t - hw, cx_t + hw, cy_t - hd, cy_t + hd):
                    return build_dining_table_ensemble(
                        bm, cx=cx_t, cy=cy_t, z_floor=z_floor, z_ceil=z_ceil,
                        length=t_len, width=table_width, yaw=yaw, rng=rng,
                        head_chairs=head_chairs, tracker=tracker
                    )
    return None
