"""Whole-building intelligent interior furnishing composer.

Dresses every room on every walkable floor with functional, collision-aware
furniture layouts. Uses the full prop catalogue (beds with fluffy pillows and
draped quilts, bookshelves with individual books and stacks, desks, wardrobes,
chests, tavern counters, hearths, tables with chairs/stools, chandeliers,
chain lanterns, storage clutter, and cauldrons).

Every placement respects room doorways, stairwells, and wall boundaries using
a 2D collision and clearance tracker (RoomOccupancyTracker).
"""

import math
import random
from typing import Dict, List, Optional, Tuple, Any

from .prop_registry import build_prop, get_spec


class RoomOccupancyTracker:
    """Collision and clearance tracker for interior room layouts."""

    def __init__(self, rx0: float, rx1: float, ry0: float, ry1: float,
                 stair_hole: Optional[Tuple[float, float, float, float]] = None,
                 doorways: Optional[List[Dict[str, Any]]] = None,
                 windows: Optional[List[Tuple[float, float, str]]] = None,
                 chimney: Optional[Tuple[float, float]] = None):
        self.rx0 = rx0
        self.rx1 = rx1
        self.ry0 = ry0
        self.ry1 = ry1
        self.occupied_boxes: List[Tuple[float, float, float, float]] = []

        # 1. Reserve stairwell clearance
        if stair_hole is not None:
            sx0, sx1, sy0, sy1 = stair_hole
            self.occupied_boxes.append((sx0 - 0.45, sx1 + 0.45, sy0 - 0.55, sy1 + 0.55))

        # 2. Reserve walking corridors around all doorways (interior, front, wing, annex)
        if doorways:
            for d in doorways:
                dcx = d.get('x', (rx0 + rx1) * 0.5)
                dcy = d.get('y', (ry0 + ry1) * 0.5)
                axis = d.get('axis', 'X')
                dw = d.get('w', 0.95)
                clr = 0.85  # clear corridor depth
                if axis == 'X':
                    self.occupied_boxes.append((dcx - dw * 0.5 - 0.15, dcx + dw * 0.5 + 0.15,
                                                dcy - clr, dcy + clr))
                else:
                    self.occupied_boxes.append((dcx - clr, dcx + clr,
                                                dcy - dw * 0.5 - 0.15, dcy + dw * 0.5 + 0.15))

        # 3. Reserve window clearance along exterior walls so tall props never block windows
        if windows:
            for wx, wy, facade in windows:
                if facade == 'FRONT':
                    self.occupied_boxes.append((wx - 0.65, wx + 0.65, self.ry0 - 0.15, self.ry0 + 0.60))
                elif facade == 'BACK':
                    self.occupied_boxes.append((wx - 0.65, wx + 0.65, self.ry1 - 0.60, self.ry1 + 0.15))
                elif facade == 'LEFT':
                    self.occupied_boxes.append((self.rx0 - 0.15, self.rx0 + 0.60, wy - 0.65, wy + 0.65))
                elif facade == 'RIGHT':
                    self.occupied_boxes.append((self.rx1 - 0.60, self.rx1 + 0.15, wy - 0.65, wy + 0.65))

        # 4. Reserve stone chimney shaft footprint
        self.chimney_box = None
        if chimney is not None:
            cx, cy = chimney
            if (self.rx0 - 0.6 <= cx <= self.rx1 + 0.6) and (self.ry0 - 0.6 <= cy <= self.ry1 + 0.6):
                self.chimney_box = (cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42)

    def is_free(self, bx0: float, bx1: float, by0: float, by1: float, margin: float = 0.03,
                ignore_chimney: bool = False) -> bool:
        """Returns True if the box [bx0, bx1] x [by0, by1] is inside the room and unblocked."""
        eps = 0.02
        if bx0 < self.rx0 - eps or bx1 > self.rx1 + eps:
            return False
        if by0 < self.ry0 - eps or by1 > self.ry1 + eps:
            return False
        if not ignore_chimney and self.chimney_box is not None:
            cx0, cx1, cy0, cy1 = self.chimney_box
            if not (bx1 + margin < cx0 or bx0 - margin > cx1 or by1 + margin < cy0 or by0 - margin > cy1):
                return False
        for ox0, ox1, oy0, oy1 in self.occupied_boxes:
            if not (bx1 + margin < ox0 or bx0 - margin > ox1 or by1 + margin < oy0 or by0 - margin > oy1):
                return False
        return True

    def occupy(self, bx0: float, bx1: float, by0: float, by1: float):
        """Marks a rectangular area as occupied."""
        self.occupied_boxes.append((bx0, bx1, by0, by1))


def _try_place_hearth(bm, tracker: RoomOccupancyTracker, z_floor: float,
                      chimney_pos: Optional[Tuple[float, float]] = None) -> bool:
    """Places a stone hearth/fireplace, prioritizing direct attachment to the chimney flue."""
    width = 1.60
    depth = 0.55
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    # 1. Try attaching directly to the stone chimney shaft if in/adjacent to room
    if chimney_pos is not None:
        cx, cy = chimney_pos
        if (rx0 - 0.5 <= cx <= rx1 + 0.5) and (ry0 - 0.5 <= cy <= ry1 + 0.5):
            chim_half = 0.38
            candidates = []
            # South face of chimney (firebox faces -Y into room)
            hy_s = cy - chim_half - depth * 0.5 + 0.02
            cand_s = (cx, hy_s, 0.0,
                      (cx - width * 0.5 - 0.15, cx + width * 0.5 + 0.15, hy_s - depth * 0.5 - 0.45, cy - chim_half))
            candidates.append((abs(rcy - hy_s), cand_s))

            # North face of chimney (firebox faces +Y into room)
            hy_n = cy + chim_half + depth * 0.5 - 0.02
            cand_n = (cx, hy_n, math.pi,
                      (cx - width * 0.5 - 0.15, cx + width * 0.5 + 0.15, cy + chim_half, hy_n + depth * 0.5 + 0.45))
            candidates.append((abs(rcy - hy_n), cand_n))

            # East face of chimney (firebox faces +X into room)
            hx_e = cx + chim_half + depth * 0.5 - 0.02
            cand_e = (hx_e, cy, math.pi / 2,
                      (cx + chim_half, hx_e + depth * 0.5 + 0.45, cy - width * 0.5 - 0.15, cy + width * 0.5 + 0.15))
            candidates.append((abs(rcx - hx_e), cand_e))

            # West face of chimney (firebox faces -X into room)
            hx_w = cx - chim_half - depth * 0.5 + 0.02
            cand_w = (hx_w, cy, -math.pi / 2,
                      (hx_w - depth * 0.5 - 0.45, cx - chim_half, cy - width * 0.5 - 0.15, cy + width * 0.5 + 0.15))
            candidates.append((abs(rcx - hx_w), cand_w))

            candidates.sort(key=lambda item: item[0])
            for _, (hx, hy, yaw, b) in candidates:
                if tracker.is_free(b[0], b[1], b[2], b[3], ignore_chimney=True):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    if tracker.chimney_box is not None:
                        tracker.occupy(*tracker.chimney_box)
                    build_prop(bm, 'HEARTH', hx, hy, z_floor, yaw, width=width, height=1.50)
                    return True

    return False


def _try_place_kitchen_stove(bm, tracker: RoomOccupancyTracker, z_floor: float,
                            chimney_pos: Optional[Tuple[float, float]] = None) -> bool:
    """Places a cast-iron kitchen stove directly attached to the chimney flue or along outer wall."""
    width = 0.95
    depth = 0.75
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    if chimney_pos is not None:
        cx, cy = chimney_pos
        if (rx0 - 0.6 <= cx <= rx1 + 0.6) and (ry0 - 0.6 <= cy <= ry1 + 0.6):
            chim_half = 0.40
            candidates = []
            # South face of chimney (faces -Y into room)
            hy_s = cy - chim_half - depth * 0.5 + 0.02
            cand_s = (cx, hy_s, 0.0,
                      (cx - width * 0.5 - 0.10, cx + width * 0.5 + 0.10, hy_s - depth * 0.5 - 0.15, cy - chim_half))
            candidates.append((abs(rcy - hy_s), cand_s))

            # North face of chimney (faces +Y into room)
            hy_n = cy + chim_half + depth * 0.5 - 0.02
            cand_n = (cx, hy_n, math.pi,
                      (cx - width * 0.5 - 0.10, cx + width * 0.5 + 0.10, cy + chim_half, hy_n + depth * 0.5 + 0.15))
            candidates.append((abs(rcy - hy_n), cand_n))

            # East face of chimney (faces +X into room)
            hx_e = cx + chim_half + depth * 0.5 - 0.02
            cand_e = (hx_e, cy, math.pi / 2,
                      (cx + chim_half, hx_e + depth * 0.5 + 0.15, cy - width * 0.5 - 0.10, cy + width * 0.5 + 0.10))
            candidates.append((abs(rcx - hx_e), cand_e))

            # West face of chimney (faces -X into room)
            hx_w = cx - chim_half - depth * 0.5 + 0.02
            cand_w = (hx_w, cy, -math.pi / 2,
                      (hx_w - depth * 0.5 - 0.15, cx - chim_half, cy - width * 0.5 - 0.10, cy + width * 0.5 + 0.10))
            candidates.append((abs(rcx - hx_w), cand_w))

            candidates.sort(key=lambda item: item[0])
            for _, (hx, hy, yaw, b) in candidates:
                if tracker.is_free(b[0], b[1], b[2], b[3], ignore_chimney=True):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    if tracker.chimney_box is not None:
                        tracker.occupy(*tracker.chimney_box)
                    build_prop(bm, 'KITCHEN_STOVE', hx, hy, z_floor, yaw, width=width, depth=depth, height=1.05)
                    return True

    # Fallback: place kitchen stove against an outer perimeter wall
    return _try_place_wall_prop(
        bm, 'KITCHEN_STOVE', width, depth, tracker, z_floor,
        candidate_walls=('EAST', 'NORTH', 'SOUTH', 'WEST')
    )


def _sample_wall_positions(center: float, min_val: float, max_val: float, step: float = 0.30) -> List[float]:
    """Generates candidate test positions along a wall starting from center, fanning outward left and right."""
    if min_val > max_val:
        return []
    clamped = max(min_val, min(max_val, center))
    pts = [clamped]
    d = step
    while True:
        added = False
        p_plus = clamped + d
        if p_plus <= max_val + 1e-4:
            pts.append(p_plus)
            added = True
        p_minus = clamped - d
        if p_minus >= min_val - 1e-4:
            pts.append(p_minus)
            added = True
        if not added:
            break
        d += step
    return pts


def _try_place_wall_prop(bm, key: str, width: float, depth: float,
                         tracker: RoomOccupancyTracker, z_floor: float,
                         candidate_walls=('NORTH', 'SOUTH', 'EAST', 'WEST'),
                         offset_bias: float = 0.0, **params) -> bool:
    """
    Attempts to place a wall-backed prop along one of the candidate walls facing inwards.
    Returns True if successfully placed.
    """
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    for wall in candidate_walls:
        if wall == 'NORTH':
            # Back at +Y, front at -Y -> yaw = 0.0
            cy = ry1 - depth * 0.5 - 0.03
            yaw = 0.0
            min_x = rx0 + width * 0.5 + 0.15
            max_x = rx1 - width * 0.5 - 0.15
            for cx in _sample_wall_positions(rcx + offset_bias, min_x, max_x, step=0.30):
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3]):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return True

        elif wall == 'SOUTH':
            # Back at -Y, front at +Y -> yaw = math.pi
            cy = ry0 + depth * 0.5 + 0.03
            yaw = math.pi
            min_x = rx0 + width * 0.5 + 0.15
            max_x = rx1 - width * 0.5 - 0.15
            for cx in _sample_wall_positions(rcx + offset_bias, min_x, max_x, step=0.30):
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3]):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return True

        elif wall == 'EAST':
            # Back at +X, front at -X -> yaw = -math.pi / 2
            cx = rx1 - depth * 0.5 - 0.03
            yaw = -math.pi / 2
            min_y = ry0 + width * 0.5 + 0.15
            max_y = ry1 - width * 0.5 - 0.15
            for cy in _sample_wall_positions(rcy + offset_bias, min_y, max_y, step=0.30):
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3]):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return True

        elif wall == 'WEST':
            # Back at -X, front at +X -> yaw = math.pi / 2
            cx = rx0 + depth * 0.5 + 0.03
            yaw = math.pi / 2
            min_y = ry0 + width * 0.5 + 0.15
            max_y = ry1 - width * 0.5 - 0.15
            for cy in _sample_wall_positions(rcy + offset_bias, min_y, max_y, step=0.30):
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3]):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return True

    return False


def _try_place_bed(bm, tracker: RoomOccupancyTracker, z_floor: float,
                   length: float = 2.0, width: float = 1.2) -> Optional[Tuple[float, float, float]]:
    """Places a timber bed with headboard against a wall, facing into the room."""
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    # 1. Try West wall (headboard at -X, bed extends +X into room)
    cx = rx0 + length * 0.5 + 0.03
    min_y = ry0 + width * 0.5 + 0.15
    max_y = ry1 - width * 0.5 - 0.15
    for cy in _sample_wall_positions(rcy, min_y, max_y, step=0.25):
        b = (cx - length * 0.5, cx + length * 0.5, cy - width * 0.5, cy + width * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, 0.0, length=length, width=width)
            return (cx, cy, 0.0)

    # 2. Try East wall (headboard at +X, bed extends -X into room)
    cx = rx1 - length * 0.5 - 0.03
    for cy in _sample_wall_positions(rcy, min_y, max_y, step=0.25):
        b = (cx - length * 0.5, cx + length * 0.5, cy - width * 0.5, cy + width * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, math.pi, length=length, width=width)
            return (cx, cy, math.pi)

    # 3. Try North wall (headboard at +Y, bed extends -Y into room)
    cy = ry1 - length * 0.5 - 0.03
    min_x = rx0 + width * 0.5 + 0.15
    max_x = rx1 - width * 0.5 - 0.15
    for cx in _sample_wall_positions(rcx, min_x, max_x, step=0.25):
        b = (cx - width * 0.5, cx + width * 0.5, cy - length * 0.5, cy + length * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, -math.pi / 2, length=length, width=width)
            return (cx, cy, -math.pi / 2)

    # 4. Try South wall (headboard at -Y, bed extends +Y into room)
    cy = ry0 + length * 0.5 + 0.03
    for cx in _sample_wall_positions(rcx, min_x, max_x, step=0.25):
        b = (cx - width * 0.5, cx + width * 0.5, cy - length * 0.5, cy + length * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, math.pi / 2, length=length, width=width)
            return (cx, cy, math.pi / 2)

    return None


def _furnish_bedroom(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float, is_master: bool = False):
    """Furnishes a comfortable bedroom with bed, wardrobe, chest, stool, and lantern."""
    # 1. Bed
    bed_w = 1.30 if is_master else 1.10
    bed_len = 2.05 if is_master else 1.95
    bed_info = _try_place_bed(bm, tracker, z_floor, length=bed_len, width=bed_w)

    # 2. Bedside chest or nightstand stool
    if bed_info is not None:
        bcx, bcy, bang = bed_info
        fwd_x = math.cos(bang)
        fwd_y = math.sin(bang)
        side_x = -math.sin(bang)
        side_y = math.cos(bang)

        # Chest at foot of bed
        fcx = bcx + fwd_x * (bed_len * 0.5 + 0.38)
        fcy = bcy + fwd_y * (bed_len * 0.5 + 0.38)
        cw, cd = 0.85, 0.45
        cbx0 = fcx - (cd * 0.5 if abs(fwd_x) > 0.5 else cw * 0.5)
        cbx1 = fcx + (cd * 0.5 if abs(fwd_x) > 0.5 else cw * 0.5)
        cby0 = fcy - (cw * 0.5 if abs(fwd_x) > 0.5 else cd * 0.5)
        cby1 = fcy + (cw * 0.5 if abs(fwd_x) > 0.5 else cd * 0.5)
        if tracker.is_free(cbx0, cbx1, cby0, cby1):
            tracker.occupy(cbx0, cbx1, cby0, cby1)
            chest_yaw = bang + math.pi / 2
            build_prop(bm, 'CHEST', fcx, fcy, z_floor, chest_yaw, width=cw)

        # Bedside stool for nightstand
        for side_sign in (1.0, -1.0):
            scx = bcx - fwd_x * 0.40 + side_sign * side_x * (bed_w * 0.5 + 0.28)
            scy = bcy - fwd_y * 0.40 + side_sign * side_y * (bed_w * 0.5 + 0.28)
            if tracker.is_free(scx - 0.22, scx + 0.22, scy - 0.22, scy + 0.22):
                tracker.occupy(scx - 0.22, scx + 0.22, scy - 0.22, scy + 0.22)
                build_prop(bm, 'STOOL', scx, scy, z_floor, 0.0)
                break

    # 3. Wardrobe against another wall
    _try_place_wall_prop(bm, 'WARDROBE', 1.20, 0.60, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'SOUTH', 'WEST'))

    # 4. Cozy floor area rug
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    rug_choice = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    rug_w, rug_l = (min(1.50, rw - 0.5), min(2.20, rd - 0.5)) if is_master else (min(1.20, rw - 0.4), min(1.80, rd - 0.4))
    build_prop(bm, rug_choice, rcx, rcy, z_floor, 0.0, width=max(0.8, rug_w), length=max(1.2, rug_l))

    # 5. Optional desk or shelf if room is roomy
    if (rw >= 3.6 or rd >= 3.6) and density >= 0.6:
        if is_master:
            placed_desk = _try_place_wall_prop(bm, 'DESK', 1.30, 0.65, tracker, z_floor,
                                               candidate_walls=('SOUTH', 'EAST', 'NORTH'))
            if placed_desk:
                # Add chair facing desk
                pass
        else:
            _try_place_wall_prop(bm, 'SHELF', 1.20, 0.40, tracker, z_floor,
                                 candidate_walls=('SOUTH', 'NORTH', 'EAST'))

    # 6. Ceiling light
    if is_master and (rw * rd >= 16.0):
        build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.42)
    else:
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_study_library(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                           rng, density: float):
    """Furnishes a scholar's library/study with bookshelves, writing desk, book piles."""
    # 1. Bookshelf
    _try_place_wall_prop(bm, 'BOOKSHELF', 1.25, 0.38, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST', 'SOUTH'))

    # 2. Second bookshelf if space permits
    if density >= 0.5:
        _try_place_wall_prop(bm, 'BOOKSHELF_NEAT', 1.25, 0.38, tracker, z_floor,
                             candidate_walls=('EAST', 'NORTH', 'WEST', 'SOUTH'))

    # 3. Writing Desk with Chair
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    placed_desk = _try_place_wall_prop(bm, 'DESK', 1.40, 0.68, tracker, z_floor,
                                       candidate_walls=('SOUTH', 'EAST', 'WEST'))
    if not placed_desk:
        # Try near center
        if tracker.is_free(rcx - 0.70, rcx + 0.70, rcy - 0.35, rcy + 0.35):
            tracker.occupy(rcx - 0.70, rcx + 0.70, rcy - 0.35, rcy + 0.35)
            build_prop(bm, 'DESK', rcx, rcy, z_floor, 0.0, width=1.35)
            # Chair
            if tracker.is_free(rcx - 0.25, rcx + 0.25, rcy - 0.85, rcy - 0.40):
                tracker.occupy(rcx - 0.25, rcx + 0.25, rcy - 0.85, rcy - 0.40)
                build_prop(bm, 'CHAIR', rcx, rcy - 0.60, z_floor, math.pi)
            # Book pile on desk
            build_prop(bm, 'BOOK_PILE_SMALL', rcx + 0.40, rcy, z_floor + 0.78, 0.3)

    # 4. Large book pile on the floor in a study corner
    if density >= 0.6:
        for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
            for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
                if tracker.is_free(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25):
                    tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
                    build_prop(bm, 'BOOK_PILE_LARGE', cx, cy, z_floor, 0.25)
                    break

    # 5. Storage chest or open shelf
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('WEST', 'SOUTH', 'EAST'))

    # Ceiling lantern
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_tavern_taproom(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                            rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a classic lively tavern common room / taproom."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Bar Counter along back or side walls (guaranteed placement)
    counter_len = min(2.8, max(1.8, rw * 0.42))
    placed_counter = False
    
    cand_north = [
        (rm.bounds[0] + counter_len * 0.5 + 0.40, rm.bounds[3] - 0.72, math.pi),
        (rm.bounds[1] - counter_len * 0.5 - 0.40, rm.bounds[3] - 0.72, math.pi),
        (rcx, rm.bounds[3] - 0.72, math.pi),
    ]
    cand_east = [
        (rm.bounds[1] - 0.72, rcy, -math.pi / 2),
        (rm.bounds[1] - 0.72, rm.bounds[2] + counter_len * 0.5 + 0.40, -math.pi / 2),
    ]
    cand_west = [
        (rm.bounds[0] + 0.72, rcy, math.pi / 2),
        (rm.bounds[0] + 0.72, rm.bounds[3] - counter_len * 0.5 - 0.40, math.pi / 2),
    ]
    for cx, cy, yaw in (cand_north + cand_east + cand_west):
        is_vert = 0.5 < abs(yaw) < 2.5
        cw = 0.80 if is_vert else counter_len + 0.2
        cd = counter_len + 0.2 if is_vert else 0.80
        b = (cx - cw * 0.5, cx + cw * 0.5, cy - cd * 0.5, cy + cd * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'COUNTER', cx, cy, z_floor, yaw, length=counter_len)
            placed_counter = True
            
            # Place 3 stools in front of counter on customer side
            step_st = counter_len / 4.0
            front_dx = math.sin(yaw)
            front_dy = -math.cos(yaw)
            tang_dx = math.cos(yaw)
            tang_dy = math.sin(yaw)
            for i in range(3):
                offset_t = (i - 1.0) * step_st
                sx = cx + front_dx * 0.70 + tang_dx * offset_t
                sy = cy + front_dy * 0.70 + tang_dy * offset_t
                if tracker.rx0 + 0.10 <= sx <= tracker.rx1 - 0.10 and tracker.ry0 + 0.10 <= sy <= tracker.ry1 - 0.10:
                    build_prop(bm, 'STOOL', sx, sy, z_floor, yaw)
            
            # Tableware scatter on counter
            build_prop(bm, 'SCATTER_TABLEWARE', cx + tang_dx * 0.4, cy + tang_dy * 0.4, z_floor + 1.02, yaw)
            # Runner rug in front of counter
            build_prop(bm, 'RUG_CRIMSON', cx + front_dx * 0.75, cy + front_dy * 0.75, z_floor, yaw, width=0.80, length=counter_len + 0.2)
            break

    # 2. Hearth fireplace directly attached to chimney flue or on clear wall
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 3. Dining / Drinking Tables with tableware scatter and 4 chairs per table (placed further back in the room)
    target_tables = 2 if (rw >= 4.2 and rd >= 4.0) else 1
    table_candidates = [
        (-0.15, 0.22),
        (0.15, 0.22),
        (0.0, 0.25),
        (-0.20, 0.10),
        (0.15, 0.05),
    ]
    placed_tables = 0
    first_table_pos = None
    for tox, toy in table_candidates:
        if placed_tables >= target_tables:
            break
        tx = rcx + tox * (rw * 0.45)
        ty = rcy + toy * (rd * 0.45)
        r = 0.55
        if tracker.is_free(tx - 0.88, tx + 0.88, ty - 0.88, ty + 0.88):
            tracker.occupy(tx - 0.92, tx + 0.92, ty - 0.92, ty + 0.92)
            build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=r)
            build_prop(bm, 'SCATTER_TABLEWARE', tx, ty, z_floor + 0.76, 0.0)
            if first_table_pos is None:
                first_table_pos = (tx, ty)
            placed_tables += 1
            # Add 4 wooden chairs around table facing table center (backrests outward)
            num_chairs = 4
            for ci in range(num_chairs):
                ca = ci * (math.pi * 0.5)
                chx = tx + 0.70 * math.cos(ca)
                chy = ty + 0.70 * math.sin(ca)
                # Chair faces inward towards table center (local chair front is -Y)
                build_prop(bm, 'CHAIR', chx, chy, z_floor, ca - math.pi * 0.5, seat_h=0.48)

    # 4. Ale barrel / crate corner clutter
    if density >= 0.5:
        for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
            for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
                if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                    tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                    build_prop(bm, 'BARREL', cx, cy, z_floor, 0.0)
                    break

    # 5. Taproom woven rug framed with dining lounge area
    rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_FOREST', 'RUG_CRIMSON'])
    rug_x, rug_y = first_table_pos if first_table_pos else (rcx, rcy + 0.20)
    build_prop(bm, rug_choice, rug_x, rug_y, z_floor, 0.0, width=min(2.0, rw * 0.45), length=min(2.6, rd * 0.50))

    # 6. Hanging Chandelier at room center
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.46)


def _furnish_kitchen(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a rustic cookhouse / kitchen / pantry with cooking stove, prep table, and supplies."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Cooking Stove (cast-iron) or Hearth (strictly attached to chimney or wall)
    placed_stove = _try_place_kitchen_stove(bm, tracker, z_floor, chimney_pos=chimney_pos)
    if not placed_stove:
        _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Food / Plate Shelf along wall
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST', 'SOUTH'))

    # 3. Food prep table with cauldron and table scatter
    prep_placed = False
    for tx, ty in [(rcx, rcy), (rcx, rm.bounds[2] + 0.85)]:
        if tracker.is_free(tx - 0.6, tx + 0.6, ty - 0.45, ty + 0.45):
            tracker.occupy(tx - 0.6, tx + 0.6, ty - 0.45, ty + 0.45)
            build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, 0.0, length=1.2, width=0.8)
            build_prop(bm, 'CAULDRON', tx + 0.35, ty, z_floor + 0.76, 0.0)
            build_prop(bm, 'SCATTER_TABLEWARE', tx - 0.25, ty, z_floor + 0.76, 0.0)
            prep_placed = True
            break

    # 4. Storage barrels, sacks and crates
    for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
        for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
            if tracker.is_free(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25):
                tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
                prop = 'BARREL' if rng.random() < 0.5 else 'CRATE'
                build_prop(bm, prop, cx, cy, z_floor, 0.0)

    # 5. Ceiling light
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_house_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                        rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a cozy living / dining hall."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Warm stone hearth (attaches to chimney if present)
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Central Dining Table with 4 Chairs
    tw, td = 1.50, 0.90
    if tracker.is_free(rcx - tw * 0.5 - 0.35, rcx + tw * 0.5 + 0.35, rcy - td * 0.5 - 0.35, rcy + td * 0.5 + 0.35):
        tracker.occupy(rcx - tw * 0.5 - 0.35, rcx + tw * 0.5 + 0.35, rcy - td * 0.5 - 0.35, rcy + td * 0.5 + 0.35)
        build_prop(bm, 'INDOOR_TABLE', rcx, rcy, z_floor, 0.0, length=tw, width=td)
        # 4 Chairs around table facing inward towards center (local chair front is -Y)
        chair_positions = [
            (rcx, rcy - (td * 0.5 + 0.30), math.pi),        # South chair facing North towards table
            (rcx, rcy + (td * 0.5 + 0.30), 0.0),            # North chair facing South towards table
            (rcx - (tw * 0.5 + 0.30), rcy, math.pi * 0.5), # West chair facing East towards table
            (rcx + (tw * 0.5 + 0.30), rcy, -math.pi * 0.5), # East chair facing West towards table
        ]
        for chx, chy, chang in chair_positions:
            if tracker.rx0 + 0.10 <= chx <= tracker.rx1 - 0.10 and tracker.ry0 + 0.10 <= chy <= tracker.ry1 - 0.10:
                build_prop(bm, 'CHAIR', chx, chy, z_floor, chang, seat_h=0.48)

    # 3. Wall shelf or cupboard
    _try_place_wall_prop(bm, 'SHELF', 1.30, 0.40, tracker, z_floor,
                         candidate_walls=('SOUTH', 'EAST', 'WEST'))

    # 4. Storage Chest
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('WEST', 'SOUTH', 'EAST'))

    # 5. Hanging Chandelier
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.42)


def _furnish_workshop(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """Furnishes a tradesman's workshop or smithy."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Heavy work desk
    _try_place_wall_prop(bm, 'DESK', 1.40, 0.68, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST'))

    # 2. Storage goods shelf
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))

    # 3. Work crates & barrels
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                p = 'CRATE' if rng.random() < 0.6 else 'BARREL'
                build_prop(bm, p, cx, cy, z_floor, 0.0)

    # 4. Iron chest
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_chapel(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                    rng, density: float):
    """Furnishes a chapel hall with altar counter and seating benches."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Altar Counter along North wall
    _try_place_wall_prop(bm, 'COUNTER', 1.80, 0.60, tracker, z_floor,
                         candidate_walls=('NORTH',), length=1.80)

    # 2. Rows of Benches
    for by in [rcy + 0.3, rcy - 0.7]:
        for sgn in (-1.0, 1.0):
            bx = rcx + sgn * (rw * 0.28)
            blen = min(1.8, rw * 0.35)
            if tracker.is_free(bx - blen * 0.5, bx + blen * 0.5, by - 0.25, by + 0.25):
                tracker.occupy(bx - blen * 0.5, bx + blen * 0.5, by - 0.25, by + 0.25)
                build_prop(bm, 'BENCH', bx, by, z_floor, 0.0, length=blen)

    # 3. Chandelier
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.48)


def _furnish_storage(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float):
    """Furnishes a storage room with shelves, crates, barrels, chests."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    # Crates and barrels in corners
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                p = 'CRATE' if rng.random() < 0.5 else 'BARREL'
                build_prop(bm, p, cx, cy, z_floor, 0.0)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_corridor(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """Furnishes a stair landing / corridor: runner rug, bench or chest, lantern. STRICTLY no bed!"""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Hallway runner rug
    rug_choice = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    rug_w = min(1.20, max(0.8, rw * 0.5))
    rug_l = min(2.40, max(1.2, rd * 0.7))
    if tracker.is_free(rcx - rug_w * 0.5, rcx + rug_w * 0.5, rcy - rug_l * 0.5, rcy + rug_l * 0.5):
        tracker.occupy(rcx - rug_w * 0.5, rcx + rug_w * 0.5, rcy - rug_l * 0.5, rcy + rug_l * 0.5)
        build_prop(bm, rug_choice, rcx, rcy, z_floor, 0.0, width=rug_w, length=rug_l)

    # 2. Bench or chest along clear wall
    _try_place_wall_prop(bm, 'BENCH', 1.40, 0.45, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'), length=1.40)

    # 3. Ceiling chain lantern
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_barracks_dorm(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                           rng, density: float):
    """Furnishes a military dormitory with sturdy soldier beds, footlockers, and a weapon rack."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Beds placed along walls with foot chests
    num_beds = max(2, min(4, int(rw * rd / 8.0)))
    for _ in range(num_beds):
        binfo = _try_place_bed(bm, tracker, z_floor, length=1.95, width=1.05)
        if binfo is not None:
            bcx, bcy, bang = binfo
            fwd_x = math.cos(bang)
            fwd_y = math.sin(bang)
            fcx = bcx + fwd_x * 1.35
            fcy = bcy + fwd_y * 1.35
            if tracker.is_free(fcx - 0.4, fcx + 0.4, fcy - 0.4, fcy + 0.4):
                tracker.occupy(fcx - 0.4, fcx + 0.4, fcy - 0.4, fcy + 0.4)
                build_prop(bm, 'CHEST', fcx, fcy, z_floor, bang + math.pi / 2, width=0.8)

    # 2. Weapon rack along remaining free wall
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST', 'SOUTH'))

    # 3. Ceiling lantern
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_armory(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                    rng, density: float):
    """Furnishes an armory / drill room with weapon racks, training dummies, target butts, and chests."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Weapon racks along walls
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST'))
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'SOUTH', 'WEST'))

    # 2. Heavy iron equipment chests
    _try_place_wall_prop(bm, 'CHEST', 1.00, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    # 3. Training dummy or target in free area
    for dx, dy in [(0.8, 0.0), (-0.8, 0.0), (0.0, 0.8)]:
        tx, ty = rcx + dx, rcy + dy
        if tracker.is_free(tx - 0.4, tx + 0.4, ty - 0.4, ty + 0.4):
            tracker.occupy(tx - 0.4, tx + 0.4, ty - 0.4, ty + 0.4)
            build_prop(bm, 'TRAINING_DUMMY', tx, ty, z_floor, 0.0)
            break

    # 4. Storage crates and barrels
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                build_prop(bm, 'CRATE', cx, cy, z_floor, 0.0)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_shop(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                  rng, density: float):
    """Furnishes an artisan retail storefront / shop with counter, display shelves, and trade crates."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]

    # 1. Storefront counter
    counter_len = min(2.0, rw * 0.45)
    _try_place_wall_prop(bm, 'COUNTER', counter_len, 0.60, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'), length=counter_len)

    # 2. Display shelves on perimeter walls
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('WEST', 'NORTH', 'SOUTH'))

    # 3. Goods crates and merchandise barrels
    for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
        for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
            if tracker.is_free(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25):
                tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
                prop = 'CRATE' if rng.random() < 0.6 else 'BARREL'
                build_prop(bm, prop, cx, cy, z_floor, 0.0)

    # 4. Area rug in customer browse zone
    rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_FOREST'])
    if tracker.is_free(rcx - 0.7, rcx + 0.7, rcy - 1.0, rcy + 1.0):
        tracker.occupy(rcx - 0.7, rcx + 0.7, rcy - 1.0, rcy + 1.0)
        build_prop(bm, rug_choice, rcx, rcy, z_floor, 0.0, width=1.2, length=1.8)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_infirmary(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Furnishes a healer's chapel infirmary / apothecary with medical beds, desk, and potion shelves."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Recovery medical bed
    _try_place_bed(bm, tracker, z_floor, length=1.95, width=1.10)

    # 2. Apothecary desk / preparation table
    _try_place_wall_prop(bm, 'DESK', 1.35, 0.65, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))

    # 3. Medicine / herb shelves
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'SOUTH'))

    # 4. Storage chest
    _try_place_wall_prop(bm, 'CHEST', 0.85, 0.48, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    # 5. Soothing clean royal rug
    if tracker.is_free(rcx - 0.65, rcx + 0.65, rcy - 0.95, rcy + 0.95):
        tracker.occupy(rcx - 0.65, rcx + 0.65, rcy - 0.95, rcy + 0.95)
        build_prop(bm, 'RUG_SAPPHIRE', rcx, rcy, z_floor, 0.0, width=1.2, length=1.8)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _dress_single_room(bm, rm, z_floor: float, z_ceil: float, rng,
                       density: float, style: str, ctx=None):
    """Dresses one functional room using the appropriate layout algorithm."""
    rx0, rx1, ry0, ry1 = rm.bounds
    # Inset room boundaries slightly from structural walls so props never clip into plaster
    inset = 0.15

    # 1. Gather all doorways bordering this room (interior partitions, front doors, wings, annexes)
    all_doorways = list(rm.doorways)
    if ctx is not None:
        fl_doors = getattr(ctx, 'floor_doorways', {}).get(rm.floor_idx, [])
        for d in fl_doors:
            dx, dy = d.get('x', 0.0), d.get('y', 0.0)
            dw = d.get('w', 0.95)
            axis = d.get('axis', 'X')
            if axis == 'X':
                if (dx + dw * 0.5 >= rx0 - 0.20 and dx - dw * 0.5 <= rx1 + 0.20) and (ry0 - 0.55 <= dy <= ry1 + 0.55):
                    if d not in all_doorways:
                        all_doorways.append(d)
            else:
                if (dy + dw * 0.5 >= ry0 - 0.20 and dy - dw * 0.5 <= ry1 + 0.20) and (rx0 - 0.55 <= dx <= rx1 + 0.55):
                    if d not in all_doorways:
                        all_doorways.append(d)

    # 2. Gather all windows bordering this room
    room_windows = []
    if ctx is not None:
        fl_windows = getattr(ctx, 'window_centers', {}).get(rm.floor_idx, {})
        for facade, wlist in fl_windows.items():
            for (wx, wy, wz) in wlist:
                if (rx0 - 0.35 <= wx <= rx1 + 0.35) and (ry0 - 0.35 <= wy <= ry1 + 0.35):
                    room_windows.append((wx, wy, facade))

    # 3. Chimney stone shaft position
    chimney_pos = getattr(ctx, 'chimney_pos', None) if ctx is not None else None

    tracker = RoomOccupancyTracker(
        rx0 + inset, rx1 - inset, ry0 + inset, ry1 - inset,
        stair_hole=rm.stair_hole,
        doorways=all_doorways,
        windows=room_windows,
        chimney=chimney_pos
    )

    role = rm.role
    if role in ('STAIR_LANDING', 'CORRIDOR'):
        _furnish_corridor(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('TAVERN_TAPROOM', 'COMMON'):
        _furnish_tavern_taproom(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_pos)
    elif role in ('KITCHEN', 'PANTRY', 'TENEMENT_KITCHEN'):
        _furnish_kitchen(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_pos)
    elif role in ('MASTER_BED',):
        _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=True)
    elif role in ('BEDROOM', 'GUEST_ROOM', 'LODGE', 'TENEMENT_BEDROOM'):
        _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=False)
    elif role in ('BARRACKS_DORM', 'OFFICER_QUARTERS'):
        _furnish_barracks_dorm(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('ARMORY', 'DRILL_HALL', 'RANGE', 'FLETCHER_WORKSHOP'):
        _furnish_armory(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('STORE',):
        _furnish_shop(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('INFIRMARY', 'APOTHECARY', 'HEALER_QUARTERS'):
        _furnish_infirmary(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('STUDY', 'LIBRARY', 'VESTRY'):
        _furnish_study_library(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('WORKSHOP', 'SMITHY'):
        _furnish_workshop(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('CHAPEL_HALL',):
        _furnish_chapel(bm, rm, tracker, z_floor, z_ceil, rng, density)
    elif role in ('STORAGE', 'CELLAR'):
        _furnish_storage(bm, rm, tracker, z_floor, z_ceil, rng, density)
    else:  # HOUSE_HALL, DINING, PARLOR, default
        _furnish_house_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_pos)


def furnish_building_interior(bm, props, ctx):
    """
    Whole-building interior furnishing composer.
    Dresses every room on every floor with intelligent, collision-free prop layouts.
    """
    if not bool(getattr(props, 'has_interior_furnishing', False)):
        return
    if getattr(ctx, 'shape', 'RECTANGLE') == 'ROUND_TOWER':
        return  # round tower owns its own interior; skip to avoid clipping

    density = float(getattr(props, 'furnishing_density', 1.0))
    if density <= 0.01:
        return
    seed = int(getattr(props, 'seed', 1)) + 917
    style = getattr(props, 'furnishing_style', 'AUTO')

    floor_rooms_dict = getattr(ctx, 'floor_rooms', {})

    for fl in range(ctx.num_floors):
        z_floor = ctx.found_h + fl * ctx.floor_h + 0.05
        z_ceil = z_floor + ctx.floor_h - 0.065
        rng = random.Random(seed + fl * 131)

        rooms = floor_rooms_dict.get(fl, [])
        if not rooms:
            # Fallback single room covering this floor
            bounds = ctx.bounds_for(fl)
            x0, x1, y0, y1 = bounds
            inset = ctx.wall_t * 0.5 + 0.10
            sh = ctx.floor_stair_holes.get(fl) or ctx.floor_stair_holes.get(fl + 1)
            doorways = []
            if fl == 0 and getattr(props, 'has_front_door', True):
                doorways.append({'x': ctx.main_door_cx, 'y': y0, 'axis': 'X', 'w': 1.0})

            # Derive role
            arch = getattr(ctx, 'effective_archetype', 'NONE')
            if arch in ('TAVERN', 'INN'):
                role = 'TAVERN_TAPROOM' if fl == 0 else 'BEDROOM'
            elif arch in ('BLACKSMITH', 'WAREHOUSE', 'LUMBERMILL', 'BAKERY'):
                role = 'WORKSHOP' if fl == 0 else 'LODGE'
            elif arch == 'CHAPEL':
                role = 'CHAPEL_HALL'
            else:
                role = 'HOUSE_HALL' if fl == 0 else 'BEDROOM'

            from ..interior import Room
            fallback_rm = Room(
                id=f"fl{fl}_fallback",
                floor_idx=fl,
                role=role,
                bounds=(x0 + inset, x1 - inset, y0 + inset, y1 - inset),
                doorways=doorways,
                stair_hole=sh
            )
            rooms = [fallback_rm]

        for rm in rooms:
            # Skip rooms that are too tiny to furnish safely
            rw = rm.bounds[1] - rm.bounds[0]
            rd = rm.bounds[3] - rm.bounds[2]
            if rw < 1.6 or rd < 1.6:
                continue
            try:
                _dress_single_room(bm, rm, z_floor, z_ceil, rng, density, style, ctx=ctx)
            except Exception:
                continue
