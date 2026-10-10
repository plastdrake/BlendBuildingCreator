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


# Debug switch: when True, a furnishing error is raised instead of skipped.
# Kept False in production so one odd room never aborts a whole building.
_STRICT_FURNISH = False

# Back-of-house roles that stay bare (no rug) in an industrial fit-out.
_UTILITY_ROLES = {'STORAGE', 'CELLAR', 'PANTRY', 'WORKSHOP', 'SMITHY', 'STORE', 'STONE_STORE'}


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
        self.doorways = doorways or []
        self.occupied_boxes: List[Tuple[float, float, float, float]] = []

        # Reserve stairwell clearance (flight below plus its approach so props
        # never block the stairs, not just the bare opening). Kept snug on
        # purpose: the upper guardrail already protects the opening edge, and
        # oversized pads used to starve whole rooms of furniture.
        if stair_hole is not None:
            sx0, sx1, sy0, sy1 = stair_hole
            self.occupied_boxes.append((sx0 - 0.60, sx1 + 0.60, sy0 - 0.90, sy1 + 0.90))

        # 2. Reserve walking corridors around all doorways (interior, front, wing, annex)
        if doorways:
            for d in doorways:
                dcx = d.get('x', (rx0 + rx1) * 0.5)
                dcy = d.get('y', (ry0 + ry1) * 0.5)
                axis = d.get('axis', 'X')
                dw = d.get('w', 0.95)
                is_p = bool(d.get('is_portal', False) or dw >= 1.5)
                clr = 2.40 if is_p else 1.25  # clear walking corridor depth inside room
                w_margin = (dw * 0.5 + 0.50) if is_p else (dw * 0.5 + 0.25)
                if axis == 'X':
                    self.occupied_boxes.append((dcx - w_margin, dcx + w_margin,
                                                dcy - clr, dcy + clr))
                else:
                    self.occupied_boxes.append((dcx - clr, dcx + clr,
                                                dcy - w_margin, dcy + w_margin))

        # 3. Reserve window clearance along exterior walls so tall props never block windows
        self.window_boxes: List[Tuple[float, float, float, float]] = []
        if windows:
            for wx, wy, facade in windows:
                if facade == 'FRONT':
                    self.window_boxes.append((wx - 0.65, wx + 0.65, self.ry0 - 0.15, self.ry0 + 0.60))
                elif facade == 'BACK':
                    self.window_boxes.append((wx - 0.65, wx + 0.65, self.ry1 - 0.60, self.ry1 + 0.15))
                elif facade == 'LEFT':
                    self.window_boxes.append((self.rx0 - 0.15, self.rx0 + 0.60, wy - 0.65, wy + 0.65))
                elif facade == 'RIGHT':
                    self.window_boxes.append((self.rx1 - 0.60, self.rx1 + 0.15, wy - 0.65, wy + 0.65))

        # 4. Reserve stone chimney shaft footprints for any chimney attached to a wall
        self.chimney_boxes: List[Tuple[float, float, float, float]] = []
        if chimney is not None:
            c_list = chimney if isinstance(chimney, list) else [chimney]
            for c in c_list:
                if c is None:
                    continue
                cx, cy = c
                near_wall = min(abs(cx - rx0), abs(cx - rx1), abs(cy - ry0), abs(cy - ry1)) <= 0.65
                if near_wall and (self.rx0 - 0.6 <= cx <= self.rx1 + 0.6) and (self.ry0 - 0.6 <= cy <= self.ry1 + 0.6):
                    self.chimney_boxes.append((cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42))
        self.chimney_box = self.chimney_boxes[0] if self.chimney_boxes else None

    def is_near_door(self, x: float, y: float, radius: float = 1.40) -> bool:
        """Returns True if (x, y) is within clearance distance of any doorway."""
        for d in self.doorways:
            dcx = d.get('x', (self.rx0 + self.rx1) * 0.5)
            dcy = d.get('y', (self.ry0 + self.ry1) * 0.5)
            dw = d.get('w', 0.95)
            is_p = bool(d.get('is_portal', False) or dw >= 1.5)
            r = max(radius, (dw * 0.5 + 0.60) if not is_p else (dw * 0.5 + 1.20))
            if math.hypot(x - dcx, y - dcy) < r:
                return True
        return False

    def is_free(self, bx0: float, bx1: float, by0: float, by1: float, margin: float = 0.03,
                ignore_chimney: bool = False, check_windows: bool = False) -> bool:
        """Returns True if the box [bx0, bx1] x [by0, by1] is inside the room and unblocked."""
        eps = 0.02
        if bx0 < self.rx0 - eps or bx1 > self.rx1 + eps:
            return False
        if by0 < self.ry0 - eps or by1 > self.ry1 + eps:
            return False
        if not ignore_chimney and self.chimney_boxes:
            for cx0, cx1, cy0, cy1 in self.chimney_boxes:
                if not (bx1 + margin < cx0 or bx0 - margin > cx1 or by1 + margin < cy0 or by0 - margin > cy1):
                    return False
        if check_windows and hasattr(self, 'window_boxes') and self.window_boxes:
            for wx0, wx1, wy0, wy1 in self.window_boxes:
                if not (bx1 + margin < wx0 or bx0 - margin > wx1 or by1 + margin < wy0 or by0 - margin > wy1):
                    return False
        for ox0, ox1, oy0, oy1 in self.occupied_boxes:
            if not (bx1 + margin < ox0 or bx0 - margin > ox1 or by1 + margin < oy0 or by0 - margin > oy1):
                return False
        return True

    def occupy(self, bx0: float, bx1: float, by0: float, by1: float):
        """Marks a rectangular area as occupied."""
        self.occupied_boxes.append((bx0, bx1, by0, by1))


def _jit(rng, amount: float) -> float:
    """Signed random offset in metres (0 when no RNG is available)."""
    return rng.uniform(-amount, amount) if rng is not None else 0.0


def _try_place_chair(bm, tracker: RoomOccupancyTracker, cx: float, cy: float,
                     yaw: float, z_floor: float, seat_h: float = 0.48,
                     half: float = 0.30) -> bool:
    """Places one chair only when its footprint is inside the room and clear
    of stairs, doorways, windows and other props. Chairs placed without this
    check used to land inside stairwells and block the climb."""
    if tracker.is_free(cx - half, cx + half, cy - half, cy + half):
        tracker.occupy(cx - half, cx + half, cy - half, cy + half)
        build_prop(bm, 'CHAIR', cx, cy, z_floor, yaw, seat_h=seat_h)
        return True
    return False


def _freest_spot(tracker: RoomOccupancyTracker, rng, step: float = 0.40):
    """Grid-scan for the room point with the most clear space around it.

    Returns (cx, cy, half) where half is the largest free square half-side
    there (doorways, stairwell, chimney and placed props all count as
    blocked). Used for sitting nooks and minimum-dressing fallbacks.
    """
    xs, ys = [], []
    x = tracker.rx0 + 0.30
    while x <= tracker.rx1 - 0.30 + 1e-6:
        xs.append(x)
        x += step
    y = tracker.ry0 + 0.30
    while y <= tracker.ry1 - 0.30 + 1e-6:
        ys.append(y)
        y += step
    if not xs or not ys:
        return None
    pts = [(x, y) for x in xs for y in ys]
    if rng is not None:
        rng.shuffle(pts)
    best = None
    for cx, cy in pts:
        h = 0.0
        while h < 3.00:
            nh = round(h + 0.20, 2)
            if tracker.is_free(cx - nh, cx + nh, cy - nh, cy + nh):
                h = nh
            else:
                break
        if best is None or h > best[2]:
            best = (cx, cy, h)
            if h >= 2.20:
                break
    return best


def _place_nook_set(bm, tracker: RoomOccupancyTracker, cx: float, cy: float,
                    z_floor: float, rng, radius: float = 0.50) -> bool:
    """Round table + two stools facing it. Returns False when they do not fit."""
    if not tracker.is_free(cx - 0.60, cx + 0.60, cy - 0.60, cy + 0.60):
        return False
    tracker.occupy(cx - 0.60, cx + 0.60, cy - 0.60, cy + 0.60)
    build_prop(bm, 'ROUND_TABLE', cx, cy, z_floor, rng.uniform(0.0, 6.28),
               radius=radius)
    for sx, sy in ((cx - 0.90, cy), (cx + 0.90, cy)):
        if tracker.is_free(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25):
            tracker.occupy(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25)
            build_prop(bm, 'STOOL', sx, sy, z_floor, rng.uniform(0.0, 6.28))
    return True


def _ensure_minimum_dressing(bm, tracker: RoomOccupancyTracker, rm,
                             z_floor: float, rng) -> None:
    """Last-resort sitting nook so a living room never reads empty, whatever
    the regular recipe managed to place (e.g. an awkward stairwell eating the
    centre). Skips small rooms: a cupboard-sized room is fine bare."""
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    if rw * rd < 12.0:
        return
    spot = _freest_spot(tracker, rng)
    if spot is None:
        return
    cx, cy, h = spot
    if h >= 0.85:
        _place_nook_set(bm, tracker, cx, cy, z_floor, rng)
    elif h >= 0.55:
        for sx, sy in ((cx - 0.35, cy), (cx + 0.35, cy)):
            if tracker.is_free(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25):
                tracker.occupy(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25)
                build_prop(bm, 'STOOL', sx, sy, z_floor, rng.uniform(0.0, 6.28))


def _sofa_fabric(rng):
    """Random hard-wearing sofa/armchair upholstery (leather or white cloth)."""
    from ..materials import (MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2,
                             MAT_INDEX_FABRIC_STITCHED)
    return rng.choice([MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_FABRIC_STITCHED])


def _try_place_hearth(bm, tracker: RoomOccupancyTracker, z_floor: float,
                      chimney_pos: Optional[Any] = None) -> bool:
    """Places a stone hearth/fireplace, prioritizing direct attachment to the chimney flue."""
    width = 1.60
    depth = 0.55
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    # 1. Try attaching directly to the stone chimney shaft if in/adjacent to room wall
    if chimney_pos is not None:
        c_list = chimney_pos if isinstance(chimney_pos, list) else [chimney_pos]
        for c in c_list:
            if c is None:
                continue
            cx, cy = c
            near_wall = min(abs(cx - rx0), abs(cx - rx1), abs(cy - ry0), abs(cy - ry1)) <= 0.65
            if near_wall and (rx0 - 0.5 <= cx <= rx1 + 0.5) and (ry0 - 0.5 <= cy <= ry1 + 0.5):
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
                        for cb in tracker.chimney_boxes:
                            tracker.occupy(*cb)
                        build_prop(bm, 'HEARTH', hx, hy, z_floor, yaw, width=width, height=1.50)
                        return (hx, hy, yaw)

    return None


def _try_place_kitchen_stove(bm, tracker: RoomOccupancyTracker, z_floor: float,
                            chimney_pos: Optional[Any] = None) -> bool:
    """Places a cast-iron kitchen stove directly attached to the chimney flue or along outer wall."""
    width = 0.95
    depth = 0.75
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    if chimney_pos is not None:
        c_list = chimney_pos if isinstance(chimney_pos, list) else [chimney_pos]
        for c in c_list:
            if c is None:
                continue
            cx, cy = c
            near_wall = min(abs(cx - rx0), abs(cx - rx1), abs(cy - ry0), abs(cy - ry1)) <= 0.65
            if near_wall and (rx0 - 0.6 <= cx <= rx1 + 0.6) and (ry0 - 0.6 <= cy <= ry1 + 0.6):
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
                        for cb in tracker.chimney_boxes:
                            tracker.occupy(*cb)
                        build_prop(bm, 'KITCHEN_STOVE', hx, hy, z_floor, yaw, width=width, depth=depth, height=1.05)
                        return (hx, hy, yaw)

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
                         offset_bias: float = 0.0, check_windows: bool = True, **params) -> Optional[Tuple[float, float, float]]:
    """
    Attempts to place a wall-backed prop along one of the candidate walls facing inwards.
    Returns (cx, cy, yaw) if successfully placed, or None.
    """
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    # Per-prop random nudge so two buildings with the same seed-free layout do
    # not place every cabinet at the exact room centre. Collision checks still
    # run on every sampled candidate, so the nudge can never cause an overlap.
    _rng = getattr(tracker, 'rng', None)
    jit = _rng.uniform(-0.30, 0.30) if _rng is not None else 0.0

    for wall in candidate_walls:
        if wall == 'NORTH':
            # Back at +Y, front at -Y -> yaw = 0.0
            cy = ry1 - depth * 0.5 - 0.03
            yaw = 0.0
            min_x = rx0 + width * 0.5 + 0.15
            max_x = rx1 - width * 0.5 - 0.15
            for cx in _sample_wall_positions(rcx + offset_bias + jit, min_x, max_x, step=0.30):
                if tracker.is_near_door(cx, cy, radius=1.40):
                    continue
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], check_windows=check_windows):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'SOUTH':
            # Back at -Y, front at +Y -> yaw = math.pi
            cy = ry0 + depth * 0.5 + 0.03
            yaw = math.pi
            min_x = rx0 + width * 0.5 + 0.15
            max_x = rx1 - width * 0.5 - 0.15
            for cx in _sample_wall_positions(rcx + offset_bias + jit, min_x, max_x, step=0.30):
                if tracker.is_near_door(cx, cy, radius=1.40):
                    continue
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], check_windows=check_windows):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'EAST':
            # Back at +X, front at -X -> yaw = -math.pi / 2
            cx = rx1 - depth * 0.5 - 0.03
            yaw = -math.pi / 2
            min_y = ry0 + width * 0.5 + 0.15
            max_y = ry1 - width * 0.5 - 0.15
            for cy in _sample_wall_positions(rcy + offset_bias + jit, min_y, max_y, step=0.30):
                if tracker.is_near_door(cx, cy, radius=1.40):
                    continue
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], check_windows=check_windows):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'WEST':
            # Back at -X, front at +X -> yaw = math.pi / 2
            cx = rx0 + depth * 0.5 + 0.03
            yaw = math.pi / 2
            min_y = ry0 + width * 0.5 + 0.15
            max_y = ry1 - width * 0.5 - 0.15
            for cy in _sample_wall_positions(rcy + offset_bias + jit, min_y, max_y, step=0.30):
                if tracker.is_near_door(cx, cy, radius=1.40):
                    continue
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], check_windows=check_windows):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

    return None


def _dress_desk(bm, tracker: RoomOccupancyTracker, cx: float, cy: float, yaw: float,
                z_floor: float, rng, room_center: Optional[Tuple[float, float]] = None):
    """Put a chair at a desk plus a small book pile on the desktop."""
    if room_center:
        fx, fy = room_center[0] - cx, room_center[1] - cy
    else:
        fx, fy = math.sin(yaw), -math.cos(yaw)
    fl = math.hypot(fx, fy) or 1.0
    fx, fy = fx / fl, fy / fl
    ccx, ccy = cx + fx * 0.80, cy + fy * 0.80
    if tracker.is_free(ccx - 0.28, ccx + 0.28, ccy - 0.28, ccy + 0.28):
        tracker.occupy(ccx - 0.28, ccx + 0.28, ccy - 0.28, ccy + 0.28)
        # Chair faces the desk (front toward -(fx, fy)).
        build_prop(bm, 'CHAIR', ccx, ccy, z_floor, math.atan2(-fx, fy), seat_h=0.48)
    bx, by = cx - fy * 0.32, cy + fx * 0.32
    build_prop(bm, 'BOOK_PILE_SMALL', bx, by, z_floor + 0.78, rng.uniform(0.0, 6.28))
    # Small potted plant on the opposite corner of the desk (skipped in industrial/utility rooms)
    if not getattr(tracker, 'no_rugs', False) and rng.random() < 0.60:
        px, py = cx + fy * 0.35, cy - fx * 0.35
        build_prop(bm, 'POTTED_PLANT_SMALL', px, py, z_floor + 0.78, rng.uniform(0.0, 6.28))


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
        if tracker.is_near_door(cx, cy, radius=1.60):
            continue
        b = (cx - length * 0.5, cx + length * 0.5, cy - width * 0.5, cy + width * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, 0.0, length=length, width=width)
            return (cx, cy, 0.0)

    # 2. Try East wall (headboard at +X, bed extends -X into room)
    cx = rx1 - length * 0.5 - 0.03
    for cy in _sample_wall_positions(rcy, min_y, max_y, step=0.25):
        if tracker.is_near_door(cx, cy, radius=1.60):
            continue
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
        if tracker.is_near_door(cx, cy, radius=1.60):
            continue
        b = (cx - width * 0.5, cx + width * 0.5, cy - length * 0.5, cy + length * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, -math.pi / 2, length=length, width=width)
            return (cx, cy, -math.pi / 2)

    # 4. Try South wall (headboard at -Y, bed extends +Y into room)
    cy = ry0 + length * 0.5 + 0.03
    for cx in _sample_wall_positions(rcx, min_x, max_x, step=0.25):
        if tracker.is_near_door(cx, cy, radius=1.60):
            continue
        b = (cx - width * 0.5, cx + width * 0.5, cy - length * 0.5, cy + length * 0.5)
        if tracker.is_free(b[0], b[1], b[2], b[3]):
            tracker.occupy(b[0], b[1], b[2], b[3])
            build_prop(bm, 'BED', cx, cy, z_floor, math.pi / 2, length=length, width=width)
            return (cx, cy, math.pi / 2)

    return None



def _try_place_plant(bm, tracker, z_floor: float, rng,
                     large: bool = True, box: Optional[float] = None) -> bool:
    """Drops a large floor potted plant into whichever free corner/edge is available.

    Only large potted plants are placed directly on the floor. Small potted plants
    belong exclusively on surfaces (tables, desks, shelves, nightstands).
    """
    if not large:
        return False
    key = 'POTTED_PLANT_LARGE'
    if box is None:
        box = 0.34
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    xs = [rx0 + box, rx1 - box]
    ys = [ry0 + box, ry1 - box]
    rng.shuffle(xs)
    rng.shuffle(ys)
    for cx in xs:
        for cy in ys:
            jx = cx + _jit(rng, 0.12)
            jy = cy + _jit(rng, 0.12)
            if tracker.is_free(jx - box, jx + box, jy - box, jy + box):
                tracker.occupy(jx - box, jx + box, jy - box, jy + box)
                build_prop(bm, key, jx, jy, z_floor, rng.uniform(0.0, math.pi * 2.0))
                return True
    return False


def _area_rug_size(rw, rd, coverage=0.82, max_w=4.50, max_l=5.50,
                   min_w=1.60, min_l=2.00, inset=0.25):
    """Standard oversized area rug footprint: covers `coverage` of the room."""
    rug_w = min(max_w, max(min_w, rw * coverage))
    rug_l = min(max_l, max(min_l, rd * coverage))
    rug_w = min(rug_w, max(0.9, rw - inset))
    rug_l = min(rug_l, max(1.2, rd - inset))
    return rug_w, rug_l


def _lay_rug(bm, tracker, rm, rng, key, cx, cy, z_floor, w, l, yaw_max=0.12,
             allow_overlap=True):
    """Lay one rug with organic imperfection and zero clipping/flicker.
    Skipped completely in industrial / utility / quarry bare fit-outs.

    - Slight random yaw so rugs never sit perfectly square (``yaw_max`` rad).
    - Rotated bbox is shrunk to fit inside the room so corners clear walls.
    - Slides/shrinks clear of ``rm.stair_hole`` (there is no floor over it).
    - Each rug in the room gets +6mm height stagger so layered rugs that
      overlap never z-fight on the same plane.
    - With ``allow_overlap=False`` (secondary/accent rugs) the rug is nudged
      to a free spot when it would cover another rug, and skipped entirely
      when the room has no free patch — one room never hoards stacked rugs
      while others go bare.
    Returns the placed rect or None when skipped.
    """
    if getattr(tracker, 'no_rugs', False):
        return None
    yaw = rng.uniform(-yaw_max, yaw_max)
    rx0, rx1, ry0, ry1 = tracker.rx0, tracker.rx1, tracker.ry0, tracker.ry1
    ca, sa = abs(math.cos(yaw)), abs(math.sin(yaw))
    ew, el = w * ca + l * sa, w * sa + l * ca
    avail_w = max(0.6, rx1 - rx0)
    avail_l = max(0.6, ry1 - ry0)
    s = min(1.0, avail_w / max(ew, 1e-3), avail_l / max(el, 1e-3))
    w, l = w * s, l * s
    ew, el = ew * s, el * s

    # Grown-to-fit minimum: tiny rugs read as misplaced bath mats in a room
    # this size, so when there is space, expand toward a proper area rug
    # (never past the free floor or the rotated bbox).
    _min_w, _min_l = 2.00, 2.80
    if avail_w >= _min_w + 0.30 and avail_l >= _min_l + 0.30:
        grow = min((_min_w + 0.30) / max(w, 1e-3), (_min_l + 0.30) / max(l, 1e-3), 1.9)
        if grow > 1.0:
            w, l = w * grow, l * grow
            ew = w * ca + l * sa
            el = w * sa + l * ca
            s2 = min(1.0, avail_w / max(ew, 1e-3), avail_l / max(el, 1e-3))
            w, l = w * s2, l * s2
            ew, el = ew * s2, el * s2

    hole = getattr(rm, 'stair_hole', None)

    def _hits_hole(px, py, pw, pl):
        if hole is None:
            return False
        hx0, hx1 = hole[0] - 0.15, hole[1] + 0.15
        hy0, hy1 = hole[2] - 0.15, hole[3] + 0.15
        return not (px + pw * 0.5 < hx0 or px - pw * 0.5 > hx1 or
                    py + pl * 0.5 < hy0 or py - pl * 0.5 > hy1)

    def _overlap_frac(px, py, pw, pl):
        worst = 0.0
        for ox0, ox1, oy0, oy1 in getattr(tracker, 'rug_rects', []):
            ix = min(px + pw * 0.5, ox1) - max(px - pw * 0.5, ox0)
            iy = min(py + pl * 0.5, oy1) - max(py - pl * 0.5, oy0)
            if ix > 0 and iy > 0:
                worst = max(worst, (ix * iy) / max(pw * pl, 1e-3))
        return worst

    if _hits_hole(cx, cy, ew, el):
        along_y = el >= ew
        lo, hi = (ry0, ry1) if along_y else (rx0, rx1)
        h0, h1 = (hole[2] - 0.15, hole[3] + 0.15) if along_y else (hole[0] - 0.15, hole[1] + 0.15)
        segs = [(a, b) for a, b in ((lo, h0), (h1, hi)) if b - a >= 1.0]
        if segs:
            a, b = max(segs, key=lambda sg: sg[1] - sg[0])
            if along_y:
                l = min(l, b - a)
                el = min(el, b - a)
                cy = a + (b - a) * 0.5
            else:
                w = min(w, b - a)
                ew = min(ew, b - a)
                cx = a + (b - a) * 0.5

    if ew < avail_w:
        cx = min(max(cx, rx0 + ew * 0.5), rx1 - ew * 0.5)
    else:
        cx = (rx0 + rx1) * 0.5
    if el < avail_l:
        cy = min(max(cy, ry0 + el * 0.5), ry1 - el * 0.5)
    else:
        cy = (ry0 + ry1) * 0.5

    if not allow_overlap and _overlap_frac(cx, cy, ew, el) > 0.03:
        placed = False
        for radius in (0.6, 1.2, 1.8, 2.4):
            for k in range(8):
                ang = k * math.pi / 4.0 + rng.uniform(-0.2, 0.2)
                px = min(max(cx + radius * math.cos(ang), rx0 + ew * 0.5), rx1 - ew * 0.5)
                py = min(max(cy + radius * math.sin(ang), ry0 + el * 0.5), ry1 - el * 0.5)
                if _hits_hole(px, py, ew, el):
                    continue
                if _overlap_frac(px, py, ew, el) <= 0.03:
                    cx, cy = px, py
                    placed = True
                    break
            if placed:
                break
        if not placed:
            return None

    lift = 0.006 * getattr(tracker, 'rug_count', 0)
    tracker.rug_count = getattr(tracker, 'rug_count', 0) + 1
    rects = getattr(tracker, 'rug_rects', None)
    if rects is None:
        tracker.rug_rects = rects = []
    rects.append((cx - ew * 0.5, cx + ew * 0.5, cy - el * 0.5, cy + el * 0.5))
    build_prop(bm, key, cx, cy, z_floor + lift, yaw, width=w, length=l)
    return (cx, cy, w, l)


def _try_place_bunk(bm, tracker: RoomOccupancyTracker, z_floor: float,
                    length: float = 2.0, width: float = 1.1,
                    only_wall: Optional[str] = None,
                    wall_gap: float = 0.0) -> Optional[Tuple[float, float, float]]:
    """Places a military bunk bed with headboard end against a wall.

    The climbing ladder overhangs the +Y local side, so the reservation box
    is deeper than the frame and the build is shifted toward the wall.
    ``only_wall`` ('WEST'/'EAST'/'NORTH'/'SOUTH') restricts placement to a
    single wall - used in narrow rooms so bunks line one side and leave a
    clear walking aisle instead of blocking the doorway. ``wall_gap`` widens
    the reserved footprint ALONG THE WALL so neighbouring bunks keep that
    much clear walkable space between them.
    """
    # The climbing ladder is mounted on the frame and overhangs the +Y local
    # side by only ~0.3m, so the reservation box is just a little deeper than
    # the frame - keeping it tight lets a row of bunks line one wall.
    lad_extra = 0.35
    box_w = width + lad_extra + max(0.0, wall_gap)
    shift = lad_extra * 0.5
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    def _wall_allowed(name):
        return only_wall is None or only_wall == name

    min_y = ry0 + box_w * 0.5 + 0.10
    max_y = ry1 - box_w * 0.5 - 0.10
    min_x = rx0 + box_w * 0.5 + 0.10
    max_x = rx1 - box_w * 0.5 - 0.10

    # 1. West wall (head at -X, ladder spilling +Y into the room)
    if _wall_allowed('WEST'):
        cx = rx0 + length * 0.5 + 0.03
        for cy in _sample_wall_positions(rcy, min_y, max_y, step=0.25):
            if tracker.is_free(cx - length * 0.5, cx + length * 0.5, cy - box_w * 0.5, cy + box_w * 0.5):
                tracker.occupy(cx - length * 0.5, cx + length * 0.5, cy - box_w * 0.5, cy + box_w * 0.5)
                build_prop(bm, 'BUNK_BED', cx, cy - shift, z_floor, 0.0, length=length, width=width)
                return (cx, cy - shift, 0.0)

    # 2. East wall (head at +X, ladder spilling -Y into the room)
    if _wall_allowed('EAST'):
        cx = rx1 - length * 0.5 - 0.03
        for cy in _sample_wall_positions(rcy, min_y, max_y, step=0.25):
            if tracker.is_free(cx - length * 0.5, cx + length * 0.5, cy - box_w * 0.5, cy + box_w * 0.5):
                tracker.occupy(cx - length * 0.5, cx + length * 0.5, cy - box_w * 0.5, cy + box_w * 0.5)
                build_prop(bm, 'BUNK_BED', cx, cy + shift, z_floor, math.pi, length=length, width=width)
                return (cx, cy + shift, math.pi)

    # 3. North wall (head at +Y, ladder spilling +X into the room)
    if _wall_allowed('NORTH'):
        cy = ry1 - length * 0.5 - 0.03
        for cx in _sample_wall_positions(rcx, min_x, max_x, step=0.25):
            if tracker.is_free(cx - box_w * 0.5, cx + box_w * 0.5, cy - length * 0.5, cy + length * 0.5):
                tracker.occupy(cx - box_w * 0.5, cx + box_w * 0.5, cy - length * 0.5, cy + length * 0.5)
                build_prop(bm, 'BUNK_BED', cx - shift, cy, z_floor, -math.pi / 2, length=length, width=width)
                return (cx - shift, cy, -math.pi / 2)

    # 4. South wall (head at -Y)
    if _wall_allowed('SOUTH'):
        cy = ry0 + length * 0.5 + 0.03
        for cx in _sample_wall_positions(rcx, min_x, max_x, step=0.25):
            if tracker.is_free(cx - box_w * 0.5, cx + box_w * 0.5, cy - length * 0.5, cy + length * 0.5):
                tracker.occupy(cx - box_w * 0.5, cx + box_w * 0.5, cy - length * 0.5, cy + length * 0.5)
                build_prop(bm, 'BUNK_BED', cx + shift, cy, z_floor, math.pi / 2, length=length, width=width)
                return (cx + shift, cy, math.pi / 2)

    return None


def _furnish_bedroom(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float, is_master: bool = False):
    """Furnishes a comfortable bedroom with bed, wardrobe, chest, stool, and lantern."""
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    narrow_room = min(rw, rd) < 3.4  # too narrow for full bedroom set

    # 1. Bed — scale down for small/narrow tenement rooms
    if narrow_room:
        bed_w = 0.95
        bed_len = 1.90
    elif is_master:
        bed_w = 1.30
        bed_len = 2.05
    else:
        bed_w = 1.10
        bed_len = 1.95
    bed_info = _try_place_bed(bm, tracker, z_floor, length=bed_len, width=bed_w)

    # 2. Bedside chest at foot of bed — only if room is wide enough
    if bed_info is not None and not narrow_room:
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
            # Folded linen stack resting on the foot chest
            build_prop(bm, 'FOLDED_CLOTH', fcx, fcy, z_floor + 0.50, chest_yaw)

        # Bedside stool for nightstand
        for side_sign in (1.0, -1.0):
            scx = bcx - fwd_x * 0.40 + side_sign * side_x * (bed_w * 0.5 + 0.28)
            scy = bcy - fwd_y * 0.40 + side_sign * side_y * (bed_w * 0.5 + 0.28)
            if tracker.is_free(scx - 0.22, scx + 0.22, scy - 0.22, scy + 0.22):
                tracker.occupy(scx - 0.22, scx + 0.22, scy - 0.22, scy + 0.22)
                build_prop(bm, 'STOOL', scx, scy, z_floor, 0.0)
                # Nightstand item: small book pile or candle
                if rng.random() < 0.60:
                    build_prop(bm, 'BOOK_PILE_SMALL', scx, scy, z_floor + 0.48, 0.2)
                else:
                    build_prop(bm, 'POTTED_PLANT_SMALL', scx, scy, z_floor + 0.48, 0.0)
                break

    elif bed_info is not None and narrow_room:
        # In narrow rooms: stool nightstand directly beside bed head
        bcx, bcy, bang = bed_info
        side_x = -math.sin(bang)
        side_y = math.cos(bang)
        for side_sign in (1.0, -1.0):
            scx = bcx + side_sign * side_x * (bed_w * 0.5 + 0.30)
            scy = bcy + side_sign * side_y * (bed_w * 0.5 + 0.30)
            if tracker.is_free(scx - 0.25, scx + 0.25, scy - 0.25, scy + 0.25):
                tracker.occupy(scx - 0.25, scx + 0.25, scy - 0.25, scy + 0.25)
                build_prop(bm, 'STOOL', scx, scy, z_floor, 0.0)
                if rng.random() < 0.50:
                    build_prop(bm, 'BOOK_PILE_SMALL', scx, scy, z_floor + 0.48, 0.2)
                else:
                    build_prop(bm, 'POTTED_PLANT_SMALL', scx, scy, z_floor + 0.48, 0.0)
                break

    # 3. Wardrobe against the wall opposite or beside the bed
    if not narrow_room and min(rw, rd) >= 2.8:
        if rw >= rd:
            wall_order = ('NORTH', 'SOUTH', 'EAST', 'WEST')
        else:
            wall_order = ('EAST', 'WEST', 'NORTH', 'SOUTH')
        _try_place_wall_prop(bm, 'WARDROBE', 1.20, 0.60, tracker, z_floor,
                             candidate_walls=wall_order)

    # 4. Bedroom Bookshelf along wall (cozy reading in bed)
    _try_place_wall_prop(bm, 'BOOKSHELF', 1.20, 0.38, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'))

    # 5. Cozy reading armchair in bedroom corner if space permits
    if not narrow_room and min(rw, rd) >= 3.2:
        for cx in (rm.bounds[0] + 0.65, rm.bounds[1] - 0.65):
            for cy in (rm.bounds[2] + 0.65, rm.bounds[3] - 0.65):
                if tracker.is_free(cx - 0.45, cx + 0.45, cy - 0.45, cy + 0.45):
                    tracker.occupy(cx - 0.45, cx + 0.45, cy - 0.45, cy + 0.45)
                    # Face the room centre, never buried nose-first in the corner.
                    dir_x, dir_y = rcx - cx, rcy - cy
                    yaw = math.atan2(dir_x, -dir_y) if (dir_x or dir_y) else 0.0
                    build_prop(bm, 'ARMCHAIR', cx, cy, z_floor, yaw, fabric_mat=_sofa_fabric(rng))
                    break

    # 6. Floor book pile in bedroom corner
    for cx in (rm.bounds[0] + 0.35, rm.bounds[1] - 0.35):
        for cy in (rm.bounds[2] + 0.35, rm.bounds[3] - 0.35):
            if tracker.is_free(cx - 0.22, cx + 0.22, cy - 0.22, cy + 0.22):
                tracker.occupy(cx - 0.22, cx + 0.22, cy - 0.22, cy + 0.22)
                build_prop(bm, 'BOOK_PILE_LARGE', cx, cy, z_floor, rng.uniform(0, 1.0))
                break

    # 7. Cozy floor area rug alongside and at foot of the bed
    rug_choice = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    rug_w = min(2.40, max(1.20, rw * 0.50))
    rug_l = min(3.20, max(1.60, rd * 0.55))

    if bed_info is not None:
        bcx, bcy, bang = bed_info
        fwd_x = math.cos(bang)
        fwd_y = math.sin(bang)
        rug_cx = bcx + fwd_x * 0.35
        rug_cy = bcy + fwd_y * 0.35
    else:
        rug_cx, rug_cy = rcx, rcy

    _lay_rug(bm, tracker, rm, rng, rug_choice, rug_cx, rug_cy, z_floor, rug_w, rug_l)

    # 7b. Secondary bedroom runner rug so bedroom floor feels warmly dressed
    if (rw >= 3.6 or rd >= 3.6):
        sub_rug = 'RUG_FOREST' if rug_choice != 'RUG_FOREST' else 'RUG_SAPPHIRE'
        _lay_rug(bm, tracker, rm, rng, sub_rug, rcx, rcy, z_floor,
                 min(1.40, rw * 0.35), min(2.60, rd * 0.48), yaw_max=0.04, allow_overlap=False)

    # 8. Writing desk in spacious bedrooms
    if (rw >= 3.6 or rd >= 3.6) and density >= 0.5:
        if is_master:
            _d = _try_place_wall_prop(bm, 'DESK', 1.30, 0.65, tracker, z_floor,
                                      candidate_walls=('SOUTH', 'EAST', 'NORTH'))
            if _d:
                _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))
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

    # 2b. Scholar's lectern (reused mage-tower spellbook pedestal) with open grimoire.
    _try_place_wall_prop(bm, 'SPELLBOOK_PEDESTAL', 0.85, 0.85, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST', 'SOUTH'))

    # 3. Writing Desk with Chair
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    placed_desk = _try_place_wall_prop(bm, 'DESK', 1.40, 0.68, tracker, z_floor,
                                       candidate_walls=('SOUTH', 'EAST', 'WEST'))
    if placed_desk:
        _dress_desk(bm, tracker, placed_desk[0], placed_desk[1], placed_desk[2],
                    z_floor, rng, (rcx, rcy))
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
            if rng.random() < 0.60:
                build_prop(bm, 'POTTED_PLANT_SMALL', rcx - 0.40, rcy, z_floor + 0.78, rng.uniform(0.0, 6.28))

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

    # 6. Scholar's cozy study rug framing desk and reading zone (oversized)
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    rug_w, rug_l = _area_rug_size(rw, rd, coverage=0.82, max_w=4.00, max_l=5.00,
                                  min_w=2.20, min_l=2.80)
    _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', rcx, rcy, z_floor, rug_w, rug_l)

    # 6b. Layered reading-nook runner in roomy studies
    if (rw >= 3.6 or rd >= 3.6) and density >= 0.4:
        run_w = min(1.60, max(1.00, rw * 0.36))
        run_l = min(3.20, max(1.80, rd * 0.46))
        _lay_rug(bm, tracker, rm, rng, 'RUG_SAPPHIRE', rcx, rcy - rd * 0.22, z_floor,
                 run_w, run_l, allow_overlap=False)

    # 7. Ceiling lantern
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
            
            # Tableware scatter on counter at exact counter top height (1.075)
            build_prop(bm, 'SCATTER_TABLEWARE', cx + tang_dx * 0.4, cy + tang_dy * 0.4, z_floor + 1.075, yaw)
            if rng.random() < 0.50:
                build_prop(bm, 'POTTED_PLANT_SMALL', cx - tang_dx * 0.4, cy - tang_dy * 0.4, z_floor + 1.075, rng.uniform(0.0, 6.28))
            # Runner rug in front of counter
            _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', cx + front_dx * 0.75, cy + front_dy * 0.75,
                     z_floor, 0.80, counter_len + 0.2, yaw_max=0.08)
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
        tx = rcx + tox * (rw * 0.45) + _jit(rng, 0.22)
        ty = rcy + toy * (rd * 0.45) + _jit(rng, 0.22)
        r = 0.55
        if tracker.is_free(tx - 0.88, tx + 0.88, ty - 0.88, ty + 0.88):
            build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=r)
            build_prop(bm, 'SCATTER_TABLEWARE', tx, ty, z_floor + 0.775, 0.0)
            if rng.random() < 0.35:
                build_prop(bm, 'POTTED_PLANT_SMALL', tx + 0.25, ty + 0.10, z_floor + 0.775, rng.uniform(0.0, 6.28))
            else:
                build_prop(bm, 'BOTTLE_CLUSTER', tx + 0.25, ty + 0.10, z_floor + 0.775, 0.0)
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
                _try_place_chair(bm, tracker, chx, chy, ca - math.pi * 0.5, z_floor)
            tracker.occupy(tx - 0.92, tx + 0.92, ty - 0.92, ty + 0.92)

    # 4. Ale barrel / crate corner clutter
    if density >= 0.5:
        for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
            for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
                if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                    tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                    build_prop(bm, 'BARREL', cx, cy, z_floor, 0.0)
                    break

    # 5. Taproom woven rugs framed with dining lounge area (oversized)
    rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_FOREST', 'RUG_CRIMSON'])
    rug_x, rug_y = first_table_pos if first_table_pos else (rcx, rcy + 0.20)
    rug_w, rug_l = _area_rug_size(rw, rd, coverage=0.82, max_w=5.40, max_l=6.60,
                                  min_w=3.00, min_l=3.60)
    _lay_rug(bm, tracker, rm, rng, rug_choice, rug_x, rug_y, z_floor, rug_w, rug_l)

    # 5b. Secondary + tertiary seating rugs in roomy taprooms
    if (rw >= 5.0 or rd >= 5.0) and density >= 0.4:
        sub_rug = 'RUG_CRIMSON' if rug_choice != 'RUG_CRIMSON' else 'RUG_SAPPHIRE'
        s_rx = rcx - rw * 0.22 if rug_x >= rcx else rcx + rw * 0.22
        s_ry = rcy - rd * 0.18
        s_w, s_l = _area_rug_size(rw, rd, coverage=0.48, max_w=3.60, max_l=4.60,
                                  min_w=1.80, min_l=2.20)
        _lay_rug(bm, tracker, rm, rng, sub_rug, s_rx, s_ry, z_floor, s_w, s_l,
                 allow_overlap=False)
    if rw >= 6.5 and rd >= 6.0 and density >= 0.6:
        third = 'RUG_FOREST' if rug_choice != 'RUG_FOREST' else 'RUG_SAPPHIRE'
        _lay_rug(bm, tracker, rm, rng, third, rcx, rcy + rd * 0.26, z_floor,
                 min(2.60, rw * 0.40), min(3.20, rd * 0.40), allow_overlap=False)

    # 6. Hanging Chandelier at room center
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.46)


def _table_offset(tx: float, ty: float, off_x: float, off_y: float, yaw: float) -> Tuple[float, float]:
    """Computes world position of a surface item given local table offsets (along length/depth)."""
    c, s = math.cos(yaw), math.sin(yaw)
    return (tx + off_x * c - off_y * s, ty + off_x * s + off_y * c)


def _place_prep_clutter(bm, px: float, py: float, z_table: float, yaw: float, rng):
    """Populates the foodprep table with cutting board, knife, bread, cheese, cauldron, and herb bowl.

    Each item gets its own bay along the table length so nothing overlaps:
    board at the left end, herb/salad bowl in the middle, cauldron at the
    right end (clear of the board and the bowl).
    """
    # 1. Foodprep cutting board with realistic knife, artisan bread, cheese, salt bowl, linen cloth
    clutter_x, clutter_y = _table_offset(px, py, -0.34, 0.0, yaw)
    build_prop(bm, 'FOODPREP_CLUTTER', clutter_x, clutter_y, z_table, yaw)
    # 2. Stove pot / cauldron at the far right end of the table
    pot_x, pot_y = _table_offset(px, py, 0.37, 0.05, yaw)
    build_prop(bm, 'CAULDRON', pot_x, pot_y, z_table, yaw)
    # 3. Potted culinary herb / salad bowl in the middle bay
    if rng.random() < 0.8:
        herb_x, herb_y = _table_offset(px, py, 0.0, -0.07, yaw)
        build_prop(bm, 'POTTED_HERB', herb_x, herb_y, z_table, yaw)


def _try_place_kitchen_workstation(bm, tracker: RoomOccupancyTracker, z_floor: float,
                                   rng, chimney_pos: Optional[Any] = None) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """
    Places an integrated culinary workstation: cast-iron stove and foodprep table
    DIRECTLY NEXT TO EACH OTHER (side-by-side along the same wall or in an L-shaped corner).
    Returns ((sx, sy, syaw), (px, py, pyaw)) if successfully placed, or None.
    """
    sw, sd, sh = 0.95, 0.75, 1.05
    pw, pd = 1.15, 0.65
    z_table = z_floor + 0.775
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx, rcy = (rx0 + rx1) * 0.5, (ry0 + ry1) * 0.5
    rw, rd = rx1 - rx0, ry1 - ry0

    # 1. Check Chimney flue in or adjacent to the room:
    if chimney_pos is not None:
        c_list = chimney_pos if isinstance(chimney_pos, list) else [chimney_pos]
        for c in c_list:
            if c is None:
                continue
            cx, cy = c
            near_wall = min(abs(cx - rx0), abs(cx - rx1), abs(cy - ry0), abs(cy - ry1)) <= 0.65
            if near_wall and (rx0 - 0.6 <= cx <= rx1 + 0.6) and (ry0 - 0.6 <= cy <= ry1 + 0.6):
                chim_half = 0.40
                candidates = []
                # South face of chimney (faces -Y into room)
                hy_s = cy - chim_half - sd * 0.5 + 0.02
                cand_s = (cx, hy_s, 0.0,
                          (cx - sw * 0.5 - 0.10, cx + sw * 0.5 + 0.10, hy_s - sd * 0.5 - 0.15, cy - chim_half))
                candidates.append((abs(rcy - hy_s), cand_s))
                # North face of chimney (faces +Y into room)
                hy_n = cy + chim_half + sd * 0.5 - 0.02
                cand_n = (cx, hy_n, math.pi,
                          (cx - sw * 0.5 - 0.10, cx + sw * 0.5 + 0.10, cy + chim_half, hy_n + sd * 0.5 + 0.15))
                candidates.append((abs(rcy - hy_n), cand_n))
                # East face of chimney (faces +X into room)
                hx_e = cx + chim_half + sd * 0.5 - 0.02
                cand_e = (hx_e, cy, math.pi / 2,
                          (cx + chim_half, hx_e + sd * 0.5 + 0.15, cy - sw * 0.5 - 0.10, cy + sw * 0.5 + 0.10))
                candidates.append((abs(rcx - hx_e), cand_e))
                # West face of chimney (faces -X into room)
                hx_w = cx - chim_half - sd * 0.5 + 0.02
                cand_w = (hx_w, cy, -math.pi / 2,
                          (hx_w - sd * 0.5 - 0.15, cx - chim_half, cy - sw * 0.5 - 0.10, cy + sw * 0.5 + 0.10))
                candidates.append((abs(rcx - hx_w), cand_w))

                candidates.sort(key=lambda item: item[0])
                for _, (hx, hy, yaw, b) in candidates:
                    if tracker.is_free(b[0], b[1], b[2], b[3], ignore_chimney=True, check_windows=True):
                        # Temporarily mark stove occupied to test candidate prep table positions adjacent
                        tracker.occupy(b[0], b[1], b[2], b[3])
                        is_vert = (0.5 < abs(yaw) < 2.5)
                        prep_cand = []
                        if is_vert:
                            wall_x = rx1 - pd * 0.5 - 0.03 if yaw < 0 else rx0 + pd * 0.5 + 0.03
                            dist_y = (sw + pw) * 0.5 + 0.06
                            prep_cand.append((wall_x, hy + dist_y, yaw))
                            prep_cand.append((wall_x, hy - dist_y, yaw))
                            # L-corner on adjoining perpendicular wall
                            if abs(hy - ry1) < 1.4:
                                prep_cand.append((hx - 0.70 if yaw < 0 else hx + 0.70, ry1 - pd * 0.5 - 0.03, 0.0))
                            if abs(hy - ry0) < 1.4:
                                prep_cand.append((hx - 0.70 if yaw < 0 else hx + 0.70, ry0 + pd * 0.5 + 0.03, math.pi))
                        else:
                            wall_y = ry1 - pd * 0.5 - 0.03 if abs(yaw) < 1.0 else ry0 + pd * 0.5 + 0.03
                            dist_x = (sw + pw) * 0.5 + 0.06
                            prep_cand.append((hx + dist_x, wall_y, yaw))
                            prep_cand.append((hx - dist_x, wall_y, yaw))
                            # L-corner on adjoining perpendicular wall
                            if abs(hx - rx1) < 1.4:
                                prep_cand.append((rx1 - pd * 0.5 - 0.03, hy - 0.70 if abs(yaw) < 1.0 else hy + 0.70, -math.pi / 2))
                            if abs(hx - rx0) < 1.4:
                                prep_cand.append((rx0 + pd * 0.5 + 0.03, hy - 0.70 if abs(yaw) < 1.0 else hy + 0.70, math.pi / 2))

                        chosen_prep = None
                        for cpx, cpy, cpyaw in prep_cand:
                            cp_vert = (0.5 < abs(cpyaw) < 2.5)
                            ctw = pd if cp_vert else pw
                            ctd = pw if cp_vert else pd
                            tb = (cpx - ctw * 0.5 - 0.04, cpx + ctw * 0.5 + 0.04,
                                  cpy - ctd * 0.5 - 0.04, cpy + ctd * 0.5 + 0.04)
                            if tracker.is_free(tb[0], tb[1], tb[2], tb[3], check_windows=True):
                                if not any(math.hypot(cpx - d.get('x', rcx), cpy - d.get('y', rcy)) < 1.20 for d in tracker.doorways):
                                    chosen_prep = (cpx, cpy, cpyaw, tb)
                                    break
                        if chosen_prep:
                            for cb in tracker.chimney_boxes:
                                tracker.occupy(*cb)
                            build_prop(bm, 'KITCHEN_STOVE', hx, hy, z_floor, yaw, width=sw, depth=sd, height=sh)
                            px, py, pyaw, ptb = chosen_prep
                            tracker.occupy(ptb[0], ptb[1], ptb[2], ptb[3])
                            build_prop(bm, 'INDOOR_TABLE', px, py, z_floor, pyaw, length=pw, width=pd)
                            _place_prep_clutter(bm, px, py, z_table, pyaw, rng)
                            return ((hx, hy, yaw), (px, py, pyaw))
                        else:
                            tracker.occupied_boxes.pop()

    # 2. Side-by-Side along an Outer Perimeter Wall:
    # Sort candidate walls so walls with 0 doorways come first!
    def _wall_door_count(w_name):
        cnt = 0
        for d in tracker.doorways:
            dx, dy = d.get('x', rcx), d.get('y', rcy)
            if w_name == 'EAST' and abs(dx - rx1) < 0.6: cnt += 1
            elif w_name == 'WEST' and abs(dx - rx0) < 0.6: cnt += 1
            elif w_name == 'NORTH' and abs(dy - ry1) < 0.6: cnt += 1
            elif w_name == 'SOUTH' and abs(dy - ry0) < 0.6: cnt += 1
        return cnt

    wall_order = sorted(['EAST', 'NORTH', 'SOUTH', 'WEST'], key=_wall_door_count)
    tot_len = sw + pw + 0.06

    for wall in wall_order:
        if wall in ('EAST', 'WEST'):
            if rd < tot_len + 0.25:
                continue
            yaw = -math.pi / 2 if wall == 'EAST' else math.pi / 2
            wall_x_stove = rx1 - sd * 0.5 - 0.03 if wall == 'EAST' else rx0 + sd * 0.5 + 0.03
            wall_x_table = rx1 - pd * 0.5 - 0.03 if wall == 'EAST' else rx0 + pd * 0.5 + 0.03
            y_shifts = [rcy, rcy + (rd - tot_len) * 0.22, rcy - (rd - tot_len) * 0.22]
            for cy_cand in y_shifts:
                for swap in (False, True):
                    s_y = cy_cand - (pw + 0.06) * 0.5 if not swap else cy_cand + (pw + 0.06) * 0.5
                    p_y = cy_cand + (sw + 0.06) * 0.5 if not swap else cy_cand - (sw + 0.06) * 0.5
                    sb = (min(wall_x_stove - sd*0.5, wall_x_stove + sd*0.5) - 0.05,
                          max(wall_x_stove - sd*0.5, wall_x_stove + sd*0.5) + 0.05,
                          s_y - sw * 0.5 - 0.04, s_y + sw * 0.5 + 0.04)
                    pb = (min(wall_x_table - pd*0.5, wall_x_table + pd*0.5) - 0.05,
                          max(wall_x_table - pd*0.5, wall_x_table + pd*0.5) + 0.05,
                          p_y - pw * 0.5 - 0.04, p_y + pw * 0.5 + 0.04)
                    if tracker.is_free(sb[0], sb[1], sb[2], sb[3], check_windows=True) and \
                       tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True):
                        if tracker.is_near_door(wall_x_stove, s_y) or tracker.is_near_door(wall_x_table, p_y):
                            continue
                        tracker.occupy(sb[0], sb[1], sb[2], sb[3])
                        tracker.occupy(pb[0], pb[1], pb[2], pb[3])
                        build_prop(bm, 'KITCHEN_STOVE', wall_x_stove, s_y, z_floor, yaw, width=sw, depth=sd, height=sh)
                        build_prop(bm, 'INDOOR_TABLE', wall_x_table, p_y, z_floor, yaw, length=pw, width=pd)
                        _place_prep_clutter(bm, wall_x_table, p_y, z_table, yaw, rng)
                        return ((wall_x_stove, s_y, yaw), (wall_x_table, p_y, yaw))

        else:  # 'NORTH' or 'SOUTH'
            if rw < tot_len + 0.25:
                continue
            yaw = 0.0 if wall == 'NORTH' else math.pi
            wall_y_stove = ry1 - sd * 0.5 - 0.03 if wall == 'NORTH' else ry0 + sd * 0.5 + 0.03
            wall_y_table = ry1 - pd * 0.5 - 0.03 if wall == 'NORTH' else ry0 + pd * 0.5 + 0.03
            x_shifts = [rcx, rcx + (rw - tot_len) * 0.22, rcx - (rw - tot_len) * 0.22]
            for cx_cand in x_shifts:
                for swap in (False, True):
                    s_x = cx_cand - (pw + 0.06) * 0.5 if not swap else cx_cand + (pw + 0.06) * 0.5
                    p_x = cx_cand + (sw + 0.06) * 0.5 if not swap else cx_cand - (sw + 0.06) * 0.5
                    sb = (s_x - sw * 0.5 - 0.04, s_x + sw * 0.5 + 0.04,
                          min(wall_y_stove - sd*0.5, wall_y_stove + sd*0.5) - 0.05,
                          max(wall_y_stove - sd*0.5, wall_y_stove + sd*0.5) + 0.05)
                    pb = (p_x - pw * 0.5 - 0.04, p_x + pw * 0.5 + 0.04,
                          min(wall_y_table - pd*0.5, wall_y_table + pd*0.5) - 0.05,
                          max(wall_y_table - pd*0.5, wall_y_table + pd*0.5) + 0.05)
                    if tracker.is_free(sb[0], sb[1], sb[2], sb[3], check_windows=True) and \
                       tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True):
                        if tracker.is_near_door(s_x, wall_y_stove) or tracker.is_near_door(p_x, wall_y_table):
                            continue
                        tracker.occupy(sb[0], sb[1], sb[2], sb[3])
                        tracker.occupy(pb[0], pb[1], pb[2], pb[3])
                        build_prop(bm, 'KITCHEN_STOVE', s_x, wall_y_stove, z_floor, yaw, width=sw, depth=sd, height=sh)
                        build_prop(bm, 'INDOOR_TABLE', p_x, wall_y_table, z_floor, yaw, length=pw, width=pd)
                        _place_prep_clutter(bm, p_x, wall_y_table, z_table, yaw, rng)
                        return ((s_x, wall_y_stove, yaw), (p_x, wall_y_table, yaw))

    # 3. Corner L-Shape Placement:
    corners = [
        ('EAST', 'NORTH', rx1 - sd*0.5 - 0.03, ry1 - sw*0.5 - 0.12, -math.pi/2,
                          rx1 - sd - pw*0.5 - 0.08, ry1 - pd*0.5 - 0.03, 0.0),
        ('EAST', 'SOUTH', rx1 - sd*0.5 - 0.03, ry0 + sw*0.5 + 0.12, -math.pi/2,
                          rx1 - sd - pw*0.5 - 0.08, ry0 + pd*0.5 + 0.03, math.pi),
        ('WEST', 'NORTH', rx0 + sd*0.5 + 0.03, ry1 - sw*0.5 - 0.12, math.pi/2,
                          rx0 + sd + pw*0.5 + 0.08, ry1 - pd*0.5 - 0.03, 0.0),
        ('WEST', 'SOUTH', rx0 + sd*0.5 + 0.03, ry0 + sw*0.5 + 0.12, math.pi/2,
                          rx0 + sd + pw*0.5 + 0.08, ry0 + pd*0.5 + 0.03, math.pi),
    ]
    for w1, w2, sx, sy, syaw, px, py, pyaw in corners:
        sb = (sx - sd*0.5 - 0.04, sx + sd*0.5 + 0.04, sy - sw*0.5 - 0.04, sy + sw*0.5 + 0.04)
        pb = (px - pw*0.5 - 0.04, px + pw*0.5 + 0.04, py - pd*0.5 - 0.04, py + pd*0.5 + 0.04)
        if tracker.is_free(sb[0], sb[1], sb[2], sb[3], check_windows=True) and \
           tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True):
            if tracker.is_near_door(sx, sy) or tracker.is_near_door(px, py):
                continue
            tracker.occupy(sb[0], sb[1], sb[2], sb[3])
            tracker.occupy(pb[0], pb[1], pb[2], pb[3])
            build_prop(bm, 'KITCHEN_STOVE', sx, sy, z_floor, syaw, width=sw, depth=sd, height=sh)
            build_prop(bm, 'INDOOR_TABLE', px, py, z_floor, pyaw, length=pw, width=pd)
            _place_prep_clutter(bm, px, py, z_table, pyaw, rng)
            return ((sx, sy, syaw), (px, py, pyaw))

    # 4. Fallback: Place stove on any available wall, prep table in room
    placed_stove = _try_place_kitchen_stove(bm, tracker, z_floor, chimney_pos=chimney_pos)
    if placed_stove:
        sx, sy, syaw = placed_stove
        for ang in (0.0, math.pi * 0.5, math.pi, -math.pi * 0.5):
            px = sx + 1.25 * math.cos(ang)
            py = sy + 1.25 * math.sin(ang)
            pb = (px - pw*0.5, px + pw*0.5, py - pd*0.5, py + pd*0.5)
            if tracker.is_free(pb[0], pb[1], pb[2], pb[3]):
                tracker.occupy(pb[0], pb[1], pb[2], pb[3])
                build_prop(bm, 'INDOOR_TABLE', px, py, z_floor, syaw, length=pw, width=pd)
                _place_prep_clutter(bm, px, py, z_table, syaw, rng)
                return (placed_stove, (px, py, syaw))
        return (placed_stove, None)
    return None


def _furnish_kitchen(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float, chimney_pos: Optional[Any] = None,
                     floor_has_dining: bool = False):
    """Furnishes a kitchen with dedicated foodprep & stove workstation side-by-side along the wall,
    shelf neatly placed away on an open wall, and (only when no separate dining/living hall
    exists on this floor) a dining area positioned in the open, spacious opposite area."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    area = rw * rd
    z_table = z_floor + 0.775

    # 1. INTEGRATED COOKING WORKSTATION: Stove & Foodprep Table SIDE-BY-SIDE
    workstation = _try_place_kitchen_workstation(bm, tracker, z_floor, rng, chimney_pos=chimney_pos)
    if workstation:
        placed_stove, prep_table_pos = workstation
    else:
        placed_stove = _try_place_kitchen_stove(bm, tracker, z_floor, chimney_pos=chimney_pos)
        if not placed_stove and rm.role != 'TENEMENT_KITCHEN':
            placed_stove = _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)
        prep_table_pos = None

    station_x = placed_stove[0] if placed_stove else (prep_table_pos[0] if prep_table_pos else rcx)
    station_y = placed_stove[1] if placed_stove else (prep_table_pos[1] if prep_table_pos else rcy)

    # 2. Wall Shelf: Placed along available wall space AWAY from the cooking workstation!
    w_dists = {
        'EAST': abs(station_x - tracker.rx1),
        'WEST': abs(station_x - tracker.rx0),
        'NORTH': abs(station_y - tracker.ry1),
        'SOUTH': abs(station_y - tracker.ry0),
    }
    cooking_wall = min(w_dists, key=w_dists.get)
    shelf_walls = [w for w in ('NORTH', 'SOUTH', 'EAST', 'WEST') if w != cooking_wall]
    _try_place_wall_prop(bm, 'SHELF', 1.25, 0.40, tracker, z_floor,
                         candidate_walls=shelf_walls, check_windows=True)

    # 3. DEDICATED DINING AREA:
    # PLACED IN THE OPEN, SPACIOUS OPPOSITE AREA (CLEAR OF DOORWAYS, NEAR WINDOWS)!
    is_small_kitchen = (area < 15.0 or rw < 3.5 or rd < 3.5)
    dining_table_pos = None

    # Determine opposite half from cooking station
    if abs(station_x - rcx) >= abs(station_y - rcy) * 0.7:
        opp_x = rcx - rw * 0.24 if station_x > rcx else rcx + rw * 0.24
        candidate_points = [
            (opp_x, rcy + rd * 0.22),
            (opp_x, rcy - rd * 0.22),
            (opp_x + (rcx - opp_x) * 0.20, rcy + rd * 0.22),
            (opp_x + (rcx - opp_x) * 0.20, rcy - rd * 0.22),
            (opp_x, rcy),
            (rcx, rcy + rd * 0.22),
            (rcx, rcy - rd * 0.22),
            (rcx, rcy),
        ]
    else:
        opp_y = rcy - rd * 0.24 if station_y > rcy else rcy + rd * 0.24
        candidate_points = [
            (rcx + rw * 0.22, opp_y),
            (rcx - rw * 0.22, opp_y),
            (rcx + rw * 0.22, opp_y + (rcy - opp_y) * 0.20),
            (rcx - rw * 0.22, opp_y + (rcy - opp_y) * 0.20),
            (rcx, opp_y),
            (rcx + rw * 0.22, rcy),
            (rcx - rw * 0.22, rcy),
            (rcx, rcy),
        ]

    def _score_dining_cand(pt):
        tx, ty = pt
        door_dists = [math.hypot(tx - d.get('x', rcx), ty - d.get('y', rcy)) for d in tracker.doorways]
        min_door = min(door_dists) if door_dists else 999.0
        if min_door < 1.25:
            return -9999.0
        score = min_door * 1.5
        score += math.hypot(tx - station_x, ty - station_y) * 2.0
        if hasattr(tracker, 'window_boxes') and tracker.window_boxes:
            win_dists = [math.hypot(tx - (wx0+wx1)*0.5, ty - (wy0+wy1)*0.5) for wx0, wx1, wy0, wy1 in tracker.window_boxes]
            min_win = min(win_dists)
            if min_win < 2.0:
                score += (2.0 - min_win) * 2.0
        margin = min(tx - tracker.rx0, tracker.rx1 - tx, ty - tracker.ry0, tracker.ry1 - ty)
        if margin < 0.65:
            score -= 500.0
        return score

    # Nudge the candidate anchor points so the dining table does not land in the
    # exact same spot in every building of the same size.
    candidate_points = [(tx + _jit(rng, 0.22), ty + _jit(rng, 0.22))
                        for tx, ty in candidate_points]
    candidate_points.sort(key=_score_dining_cand, reverse=True)

    # A separate dining/living hall on this floor already owns the dining set,
    # so the kitchen stays a kitchen and keeps its floor clear for a rug.
    if floor_has_dining:
        candidate_points = []

    if is_small_kitchen:
        tr = 0.48
        for tx, ty in candidate_points:
            if _score_dining_cand((tx, ty)) < -500:
                continue
            if tracker.is_free(tx - 0.72, tx + 0.72, ty - 0.72, ty + 0.72):
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=tr)
                build_prop(bm, 'SCATTER_TABLEWARE', tx, ty, z_table, 0.0)
                for ci, ca in enumerate([0.0, math.pi]):
                    cx = tx + 0.65 * math.cos(ca)
                    cy = ty + 0.65 * math.sin(ca)
                    _try_place_chair(bm, tracker, cx, cy, ca - math.pi * 0.5, z_floor)
                tracker.occupy(tx - 0.72, tx + 0.72, ty - 0.72, ty + 0.72)
                dining_table_pos = (tx, ty)
                break
    else:
        for tx, ty in candidate_points:
            if _score_dining_cand((tx, ty)) < -500:
                continue
            placed = False
            for try_yaw, tw, td in [(0.0, 1.40, 0.85), (math.pi * 0.5, 0.85, 1.40)]:
                if tracker.is_free(tx - tw * 0.5 - 0.32, tx + tw * 0.5 + 0.32,
                                   ty - td * 0.5 - 0.32, ty + td * 0.5 + 0.32):
                    build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, try_yaw, length=1.40, width=0.85)
                    clutter_x, clutter_y = _table_offset(tx, ty, -0.20, 0.0, try_yaw)
                    bottle_x, bottle_y = _table_offset(tx, ty, 0.30, 0.0, try_yaw)
                    build_prop(bm, 'SCATTER_TABLEWARE', clutter_x, clutter_y, z_table, try_yaw)
                    if rng.random() < 0.35:
                        build_prop(bm, 'POTTED_PLANT_SMALL', bottle_x, bottle_y, z_table, rng.uniform(0.0, 6.28))
                    else:
                        build_prop(bm, 'BOTTLE_CLUSTER', bottle_x, bottle_y, z_table, try_yaw)
                    if try_yaw == 0.0:
                        chair_offsets = [
                            (tx, ty - (td * 0.5 + 0.30), math.pi),
                            (tx, ty + (td * 0.5 + 0.30), 0.0),
                            (tx - (tw * 0.5 + 0.28), ty, math.pi * 0.5),
                            (tx + (tw * 0.5 + 0.28), ty, -math.pi * 0.5),
                        ]
                    else:
                        chair_offsets = [
                            (tx - (tw * 0.5 + 0.30), ty, math.pi * 0.5),
                            (tx + (tw * 0.5 + 0.30), ty, -math.pi * 0.5),
                            (tx, ty - (td * 0.5 + 0.28), math.pi),
                            (tx, ty + (td * 0.5 + 0.28), 0.0),
                        ]
                    for chx, chy, chang in chair_offsets:
                        _try_place_chair(bm, tracker, chx, chy, chang, z_floor)
                    tracker.occupy(tx - tw * 0.5 - 0.32, tx + tw * 0.5 + 0.32,
                                   ty - td * 0.5 - 0.32, ty + td * 0.5 + 0.32)
                    dining_table_pos = (tx, ty)
                    placed = True
                    break
            if placed:
                break

    # Fallback dining table if tight (never when a hall already has dining)
    if (not floor_has_dining and dining_table_pos is None
            and tracker.is_free(rcx - 0.60, rcx + 0.60, rcy - 0.60, rcy + 0.60)):
        build_prop(bm, 'ROUND_TABLE', rcx, rcy, z_floor, 0.0, radius=0.48)
        build_prop(bm, 'SCATTER_TABLEWARE', rcx, rcy, z_table, 0.0)
        _try_place_chair(bm, tracker, rcx, rcy - 0.65, math.pi, z_floor)
        _try_place_chair(bm, tracker, rcx, rcy + 0.65, 0.0, z_floor)
        tracker.occupy(rcx - 0.60, rcx + 0.60, rcy - 0.60, rcy + 0.60)
        dining_table_pos = (rcx, rcy)

    # 4. Produce presentation: the pumpkin is displayed ON a kitchen sideboard
    #    (or a crate lid) instead of standing randomly on the floor.
    produce = _try_place_wall_prop(
        bm, 'INDOOR_TABLE', 1.05, 0.90, tracker, z_floor,
        candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'),
        length=1.05)
    if produce is not None:
        pcx, pcy, pyaw = produce
        pp_x, pp_y = _table_offset(pcx, pcy, 0.24, 0.0, pyaw)
        build_prop(bm, 'PUMPKIN', pp_x, pp_y, z_table, rng.uniform(0, math.pi * 2))
        sx_x, sx_y = _table_offset(pcx, pcy, -0.22, 0.02, pyaw)
        build_prop(bm, 'CLAY_POT', sx_x, sx_y, z_table, 0.0, radius=0.16, height=0.38)
    else:
        # Fallback: a crate in the corner with the pumpkin resting on its lid.
        for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
            for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
                if tracker.is_free(cx - 0.30, cx + 0.30, cy - 0.30, cy + 0.30):
                    tracker.occupy(cx - 0.30, cx + 0.30, cy - 0.30, cy + 0.30)
                    build_prop(bm, 'CRATE', cx, cy, z_floor, 0.0)
                    build_prop(bm, 'PUMPKIN', cx, cy, z_floor + 0.58, rng.uniform(0, math.pi * 2))
                    break
            else:
                continue
            break

    # 4b. Food / produce clutter: barrels, sacks and crates in the free corners.
    for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
        for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
            jx = cx + _jit(rng, 0.08)
            jy = cy + _jit(rng, 0.08)
            if tracker.is_free(jx - 0.24, jx + 0.24, jy - 0.24, jy + 0.24):
                tracker.occupy(jx - 0.24, jx + 0.24, jy - 0.24, jy + 0.24)
                prop = rng.choice(['BARREL', 'CRATE', 'SACK'])
                build_prop(bm, prop, jx, jy, z_floor, 0.0)

    # 5. Guaranteed Kitchen Rugs:
    # Dedicated woven rug centered directly under the dining table in the open area!
    k_rug_choice = rng.choice(['RUG_FOREST', 'RUG_CRIMSON'])
    if dining_table_pos is not None:
        tx, ty = dining_table_pos
        rug_w = min(2.50, max(1.45, rw * 0.46))
        rug_l = min(2.80, max(1.65, rd * 0.46))
        _lay_rug(bm, tracker, rm, rng, k_rug_choice, tx, ty, z_floor, rug_w, rug_l, yaw_max=0.03)
    else:
        rug_w = min(1.40, rw * 0.40)
        rug_l = min(2.80, rd * 0.60)
        _lay_rug(bm, tracker, rm, rng, k_rug_choice, rcx, rcy, z_floor, rug_w, rug_l, yaw_max=0.03)

    # Secondary foodprep runner right along the prep table & stove workstation
    if (rw >= 3.8 or rd >= 3.8) and (placed_stove or prep_table_pos):
        sub_rug = 'RUG_CRIMSON' if k_rug_choice != 'RUG_CRIMSON' else 'RUG_FOREST'
        wx = (placed_stove[0] + (prep_table_pos[0] if prep_table_pos else placed_stove[0])) * 0.5
        wy = (placed_stove[1] + (prep_table_pos[1] if prep_table_pos else placed_stove[1])) * 0.5
        run_x = wx + (0.65 if wx < rcx else -0.65) if abs(wx - rcx) > abs(wy - rcy) else wx
        run_y = wy + (0.65 if wy < rcy else -0.65) if abs(wy - rcy) >= abs(wx - rcx) else wy
        _lay_rug(bm, tracker, rm, rng, sub_rug,
                 run_x, run_y, z_floor,
                 min(1.20, rw * 0.35), min(2.20, rd * 0.45), yaw_max=0.01, allow_overlap=False)

    # 6. Ceiling light
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_house_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                        rng, density: float, chimney_pos: Optional[Any] = None):
    """Furnishes a cozy living / dining hall with dining table, plush sofa/armchairs, bookshelves, and plants."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    # 1. Warm stone hearth (attaches to chimney if present)
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Central Dining Table with 4 Chairs and Table Clutter (jittered anchor)
    dtx = rcx + _jit(rng, 0.22)
    dty = rcy + _jit(rng, 0.22)
    tw, td = 1.50, 0.90
    if tracker.is_free(dtx - tw * 0.5 - 0.35, dtx + tw * 0.5 + 0.35, dty - td * 0.5 - 0.35, dty + td * 0.5 + 0.35):
        build_prop(bm, 'INDOOR_TABLE', dtx, dty, z_floor, 0.0, length=tw, width=td)
        build_prop(bm, 'SCATTER_TABLEWARE', dtx - 0.25, dty, z_table, 0.0)
        if rng.random() < 0.45:
            build_prop(bm, 'POTTED_PLANT_SMALL', dtx + 0.35, dty, z_table, rng.uniform(0.0, 6.28))
        else:
            build_prop(bm, 'BOTTLE_CLUSTER', dtx + 0.35, dty, z_table, 0.0)
        # 4 Chairs around table facing inward towards center
        chair_positions = [
            (dtx, dty - (td * 0.5 + 0.30), math.pi),
            (dtx, dty + (td * 0.5 + 0.30), 0.0),
            (dtx - (tw * 0.5 + 0.30), dty, math.pi * 0.5),
            (dtx + (tw * 0.5 + 0.30), dty, -math.pi * 0.5),
        ]
        for chx, chy, chang in chair_positions:
            _try_place_chair(bm, tracker, chx, chy, chang, z_floor)
        tracker.occupy(dtx - tw * 0.5 - 0.35, dtx + tw * 0.5 + 0.35, dty - td * 0.5 - 0.35, dty + td * 0.5 + 0.35)

    # 3. Fireside Lounge / Seating: Plush Sofa or Armchair facing hearth/center
    if rw >= 4.0 or rd >= 4.0:
        sofa_candidates = [
            (rcx, rcy - rd * 0.26, math.pi),
            (rcx, rcy + rd * 0.26, 0.0),
            (rcx - rw * 0.26, rcy, math.pi * 0.5),
            (rcx + rw * 0.26, rcy, -math.pi * 0.5),
        ]
        sofa_placed = False
        lounge = None
        _lounge_fabric = _sofa_fabric(rng)

        # Prefer a proper wall-anchored sofa (back to a free wall, facing in).
        wall_sofa = _try_place_wall_prop(
            bm, 'SOFA', 1.90, 0.92, tracker, z_floor,
            candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'),
            length=1.75, check_windows=False, fabric_mat=_lounge_fabric)
        if wall_sofa is not None:
            lounge = wall_sofa
            sofa_placed = True

        if not sofa_placed:
            for sx, sy, syaw in sofa_candidates:
                if any(math.hypot(sx - d.get('x', rcx), sy - d.get('y', rcy)) < 1.30 for d in tracker.doorways):
                    continue
                if tracker.is_free(sx - 0.95, sx + 0.95, sy - 0.45, sy + 0.45):
                    tracker.occupy(sx - 0.95, sx + 0.95, sy - 0.45, sy + 0.45)
                    build_prop(bm, 'SOFA', sx, sy, z_floor, syaw, length=1.75, depth=0.80,
                               fabric_mat=_lounge_fabric)
                    sofa_placed = True
                    lounge = (sx, sy, syaw)
                    break
        if not sofa_placed:
            wall_chair = _try_place_wall_prop(
                bm, 'ARMCHAIR', 0.90, 0.86, tracker, z_floor,
                candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'),
                check_windows=False, fabric_mat=_sofa_fabric(rng))
            if wall_chair is not None:
                lounge = wall_chair
            else:
                for ax, ay, ayaw in sofa_candidates:
                    if any(math.hypot(ax - d.get('x', rcx), ay - d.get('y', rcy)) < 1.30 for d in tracker.doorways):
                        continue
                    if tracker.is_free(ax - 0.48, ax + 0.48, ay - 0.45, ay + 0.45):
                        tracker.occupy(ax - 0.48, ax + 0.48, ay - 0.45, ay + 0.45)
                        build_prop(bm, 'ARMCHAIR', ax, ay, z_floor, ayaw, fabric_mat=_sofa_fabric(rng))
                        lounge = (ax, ay, ayaw)
                        break

        # Coffee table + a second armchair facing the lounge, so a big room
        # never reads as just a dining table dropped in the middle.
        if lounge is not None:
            lx, ly = lounge[0], lounge[1]
            fx, fy = rcx - lx, rcy - ly
            fl = math.hypot(fx, fy) or 1.0
            fx, fy = fx / fl, fy / fl
            coff = (lx + fx * (1.15 if sofa_placed else 0.95),
                    ly + fy * (1.15 if sofa_placed else 0.95))
            if tracker.is_free(coff[0] - 0.50, coff[0] + 0.50, coff[1] - 0.50, coff[1] + 0.50):
                tracker.occupy(coff[0] - 0.50, coff[0] + 0.50, coff[1] - 0.50, coff[1] + 0.50)
                build_prop(bm, 'ROUND_TABLE', coff[0], coff[1], z_floor, 0.0, radius=0.40)
                build_prop(bm, 'POTTED_PLANT_SMALL', coff[0], coff[1], z_floor + 0.775, rng.uniform(0, 6.28))
            # Second armchair across the coffee table, facing the first seat.
            ax = lx + fx * 2.25
            ay = ly + fy * 2.25
            a_yaw = math.atan2(-fx, fy)
            if tracker.is_free(ax - 0.48, ax + 0.48, ay - 0.45, ay + 0.45):
                tracker.occupy(ax - 0.48, ax + 0.48, ay - 0.45, ay + 0.45)
                build_prop(bm, 'ARMCHAIR', ax, ay, z_floor, a_yaw, fabric_mat=_sofa_fabric(rng))

    # 4. Wall bookshelf and cupboard
    _try_place_wall_prop(bm, 'BOOKSHELF', 1.25, 0.38, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST', 'SOUTH'))
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('WEST', 'SOUTH', 'EAST'))

    # 4b. Large Floor Potted Plant in corner
    _try_place_plant(bm, tracker, z_floor, rng, large=True)

    # 5. Central dining rug, centred exactly under the table + chairs so the
    # group always reads as sitting in the middle of the carpet.
    rug_choice = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    rug_w = min(3.60, max(2.60, rw * 0.70))
    rug_l = min(4.40, max(2.50, rd * 0.62))
    _lay_rug(bm, tracker, rm, rng, rug_choice, dtx, dty, z_floor, rug_w, rug_l)

    # 5b. Secondary hearth / entry runner rug
    if (rw >= 4.0 or rd >= 4.0) and density >= 0.4:
        sub_choice = 'RUG_SAPPHIRE' if rug_choice != 'RUG_SAPPHIRE' else 'RUG_CRIMSON'
        run_w = min(1.80, max(1.10, rw * 0.36))
        run_l = min(3.80, max(2.20, rd * 0.46))
        run_y = rm.bounds[2] + 0.85
        _lay_rug(bm, tracker, rm, rng, sub_choice, rcx, run_y, z_floor, run_w, run_l,
                 allow_overlap=False)

    # 6. Hanging Chandelier
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.42)


def _furnish_great_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                        rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a civic Great Hall / Council Chamber with council table, magistrate chairs, and banners."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Warm stone hearth if chimney exists
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Grand Council Table with Magistrate Chairs (chairs keep clear of
    # stairs, doorways and other props).
    tw = min(3.0, max(1.80, rw * 0.45))
    td = 1.05
    if tracker.is_free(rcx - tw * 0.5 - 0.40, rcx + tw * 0.5 + 0.40, rcy - td * 0.5 - 0.40, rcy + td * 0.5 + 0.40):
        # Seats first, margin reservation last (chairs tuck against the table
        # edge and would self-reject against the margin box).
        build_prop(bm, 'INDOOR_TABLE', rcx, rcy, z_floor, 0.0, length=tw, width=td)
        n_chairs = max(2, int(tw / 0.85))
        chair_step = tw / n_chairs
        for ci in range(n_chairs):
            chx = rcx - tw * 0.5 + (ci + 0.5) * chair_step
            for chy, chang in ((rcy - (td * 0.5 + 0.32), math.pi),
                               (rcy + (td * 0.5 + 0.32), 0.0)):
                if tracker.is_free(chx - 0.30, chx + 0.30, chy - 0.30, chy + 0.30):
                    tracker.occupy(chx - 0.30, chx + 0.30, chy - 0.30, chy + 0.30)
                    build_prop(bm, 'CHAIR', chx, chy, z_floor, chang, seat_h=0.50)
        _ex, _ey, _eyaw = rcx - (tw * 0.5 + 0.38), rcy, math.pi * 0.5
        if tracker.is_free(_ex - 0.30, _ex + 0.30, _ey - 0.30, _ey + 0.30):
            tracker.occupy(_ex - 0.30, _ex + 0.30, _ey - 0.30, _ey + 0.30)
            build_prop(bm, 'CHAIR', _ex, _ey, z_floor, _eyaw, seat_h=0.54)
        tracker.occupy(rcx - tw * 0.5 - 0.40, rcx + tw * 0.5 + 0.40, rcy - td * 0.5 - 0.40, rcy + td * 0.5 + 0.40)

    # 3. Perimeter benches along walls
    _try_place_wall_prop(bm, 'BENCH', 1.60, 0.45, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'EAST', 'WEST'), length=1.60)

    # 4. Storage chests for civic records
    _try_place_wall_prop(bm, 'CHEST', 1.00, 0.55, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'SOUTH'))

    # 5. Grand ceremonial royal aisle carpet runner down the center of the hall
    runner_w = min(3.40, max(2.20, rw * 0.48))
    runner_l = min(12.00, max(5.20, rd * 0.86))
    runner_w = min(runner_w, max(1.4, rw - 0.40))
    runner_l = min(runner_l, max(2.5, rd - 0.40))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor, runner_w, runner_l,
             yaw_max=0.06)

    # 5b. Flanking council chamber carpets (now in most halls, not just very wide ones)
    if rw >= 5.5 and density >= 0.4:
        side_w = min(2.80, max(1.60, rw * 0.30))
        side_l = min(6.50, max(3.40, rd * 0.62))
        for sgn in (-1.0, 1.0):
            fx = rcx + sgn * (rw * 0.28)
            _lay_rug(bm, tracker, rm, rng, 'RUG_SAPPHIRE', fx, rcy, z_floor, side_w, side_l,
                     yaw_max=0.06, allow_overlap=False)

    # 6. Grand Chandelier
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.52)


def _furnish_throne_room(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                         rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Grand Castle Throne Room: 3-tier stepped cut-stone dais, carved royal high throne,
    ceremonial crimson carpet aisle, flanking guard braziers, noble benches, weapon racks
    and magnificent chandeliers."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Warm stone hearth on side wall if chimney exists
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Place Royal Throne on Dais at the head wall (facing away from rear wall)
    throne_y = rm.bounds[3] - 1.45
    throne_x = rcx
    throne_ang = math.pi  # Facing South / toward entrance doors
    if tracker.is_free(throne_x - 1.55, throne_x + 1.55, throne_y - 1.35, throne_y + 1.35):
        tracker.occupy(throne_x - 1.55, throne_x + 1.55, throne_y - 1.35, throne_y + 1.35)
        build_prop(bm, 'ROYAL_THRONE', throne_x, throne_y, z_floor, throne_ang, dais=True)

    # 3. Flanking guard braziers / iron cauldrons on pedestals
    for sgn in (-1.0, 1.0):
        bx = throne_x + sgn * 1.85
        by = throne_y - 0.20
        if tracker.is_free(bx - 0.40, bx + 0.40, by - 0.40, by + 0.40):
            tracker.occupy(bx - 0.40, bx + 0.40, by - 0.40, by + 0.40)
            build_prop(bm, 'CAULDRON', bx, by, z_floor, 0.0)

    # 4. Long ceremonial royal red carpet runner leading down the aisle to the throne dais
    runner_w = min(2.80, max(1.80, rw * 0.38))
    runner_l = min(14.00, max(4.00, rd * 0.78))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy - 0.3, z_floor, runner_w, runner_l,
             yaw_max=0.0)

    # 5. Courtier / noble benches along side walls
    _try_place_wall_prop(bm, 'BENCH', 1.80, 0.50, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST'), length=1.75)
    _try_place_wall_prop(bm, 'BENCH', 1.80, 0.50, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST'), length=1.75)

    # 6. Flanking weapon racks / ceremonial guard halberds
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.20, 0.55, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'SOUTH'))

    # 7. Grand chandeliers overhead
    build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.62)
    if rd >= 7.5:
        build_prop(bm, 'CHANDELIER', rcx, throne_y - 0.60, z_ceil, 0.0, radius=0.52)


def _furnish_banquet_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                          rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Grand manor banquet hall: one long feast table with chairs all around,
    festive tableware, hearth, sideboard and ceremonial rugs."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    # 1. Warm stone hearth if chimney exists
    _try_place_hearth(bm, tracker, z_floor, chimney_pos=chimney_pos)

    # 2. Long feast table along the room's long axis with chairs around all sides.
    along_y = rd >= rw
    if along_y:
        tw, td, yaw = 1.05, min(4.6, max(2.2, rd * 0.62)), math.pi * 0.5
    else:
        tw, td, yaw = min(4.6, max(2.2, rw * 0.62)), 1.05, 0.0
    tx, ty = rcx + _jit(rng, 0.15), rcy + _jit(rng, 0.15)
    hw, hd = (0.55, td * 0.5 + 0.40) if along_y else (tw * 0.5 + 0.40, 0.95)
    if tracker.is_free(tx - hw, tx + hw, ty - hd, ty + hd):
        # Seats are placed BEFORE the table's margin box is reserved: chairs
        # tuck against the table edge, so checking them against the margin
        # would wrongly reject every one of them.
        build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, yaw, length=max(tw, td), width=1.05)
        build_prop(bm, 'SCATTER_TABLEWARE', tx, ty, z_table, yaw)
        if rng.random() < 0.7:
            build_prop(bm, 'BOTTLE_CLUSTER', tx + _jit(rng, 0.3), ty + _jit(rng, 0.3), z_table, yaw)
        # Chairs along both long sides plus both ends. Every chair is
        # collision-checked so none lands in the stairwell, a doorway
        # corridor or another prop.
        def _seat(cx, cy, yaw, h=0.50):
            if tracker.is_free(cx - 0.30, cx + 0.30, cy - 0.30, cy + 0.30):
                tracker.occupy(cx - 0.30, cx + 0.30, cy - 0.30, cy + 0.30)
                build_prop(bm, 'CHAIR', cx, cy, z_floor, yaw, seat_h=h)

        long_len = max(tw, td)
        n_side = max(2, int(long_len / 0.85))
        step = long_len / n_side
        for ci in range(n_side):
            off = -long_len * 0.5 + (ci + 0.5) * step
            if along_y:
                _seat(tx - 0.85, ty + off, math.pi * 0.5)
                _seat(tx + 0.85, ty + off, -math.pi * 0.5)
            else:
                _seat(tx + off, ty - 0.85, math.pi)
                _seat(tx + off, ty + 0.85, 0.0)
        if along_y:
            _seat(tx, ty - (long_len * 0.5 + 0.38), math.pi, h=0.54)
            _seat(tx, ty + (long_len * 0.5 + 0.38), 0.0, h=0.54)
        else:
            _seat(tx - (long_len * 0.5 + 0.38), ty, math.pi * 0.5, h=0.54)
            _seat(tx + (long_len * 0.5 + 0.38), ty, -math.pi * 0.5, h=0.54)
        tracker.occupy(tx - hw, tx + hw, ty - hd, ty + hd)

    # 3. Sideboard with bottles against a free wall.
    sideboard = _try_place_wall_prop(bm, 'INDOOR_TABLE', 1.40, 0.60, tracker, z_floor,
                                     candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'),
                                     length=1.40)
    if sideboard is not None:
        build_prop(bm, 'BOTTLE_CLUSTER', sideboard[0], sideboard[1], z_table, sideboard[2])

    # 4. Perimeter bench + chest.
    _try_place_wall_prop(bm, 'BENCH', 1.60, 0.45, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'EAST', 'WEST'), length=1.60)
    _try_place_wall_prop(bm, 'CHEST', 1.00, 0.55, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'SOUTH'))

    # 5. Ceremonial runner under the feast table.
    run_w = min(3.0, max(1.8, min(rw, rd) * 0.55))
    run_l = min(9.0, max(3.4, max(rw, rd) * 0.80))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', tx, ty, z_floor, run_w, run_l, yaw_max=0.05)

    # 6. Grand chandelier over the table.
    build_prop(bm, 'CHANDELIER', tx, ty, z_ceil, 0.0, radius=0.52)


def _furnish_entrance_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                           rng, density: float, chimney_pos: Optional[Any] = None):
    """Civic entrance lobby: keep the walking axis clear and line the walls
    with couches, benches, a bookcase and plants instead of a central table."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # Runner carpet down the middle of the walking axis (nothing sits on it).
    rug_w = min(2.20, max(1.20, min(rw, rd) * 0.55))
    rug_l = min(5.00, max(2.20, max(rw, rd) * 0.62))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor, rug_w, rug_l,
             yaw_max=0.02)

    # Couches / benches along the side walls, facing into the lobby.
    seats = 0
    for wall in ('EAST', 'WEST', 'NORTH', 'SOUTH'):
        if seats >= 2:
            break
        _d = _try_place_wall_prop(bm, 'SOFA', 1.80, 0.92, tracker, z_floor,
                                  candidate_walls=(wall,), length=1.70,
                                  check_windows=False, fabric_mat=_sofa_fabric(rng))
        if _d is not None:
            seats += 1
    if seats == 0:
        _try_place_wall_prop(bm, 'BENCH', 1.60, 0.45, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'), length=1.6)

    # A pair of armchairs and a bookcase for a proper waiting lobby.
    if min(rw, rd) >= 3.0:
        _try_place_wall_prop(bm, 'ARMCHAIR', 0.90, 0.86, tracker, z_floor,
                             candidate_walls=('NORTH', 'SOUTH', 'EAST', 'WEST'),
                             check_windows=False, fabric_mat=_sofa_fabric(rng))
    _try_place_wall_prop(bm, 'BOOKSHELF', 1.25, 0.38, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'EAST', 'WEST'))
    if min(rw, rd) >= 2.6:
        _try_place_plant(bm, tracker, z_floor, rng, large=True)

    if min(rw, rd) >= 5.0:
        build_prop(bm, 'CHANDELIER', rcx, rcy, z_ceil, 0.0, radius=0.44)
    else:
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_office(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                    rng, density: float):
    """Furnishes an administrative office (Mayor's Office / Clerk Study) with desk, bookcases, and records."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Executive Desk placed facing into the room (chair + book pile)
    desk_w, desk_d = 1.55, 0.80
    _d = _try_place_wall_prop(bm, 'DESK', desk_w, desk_d, tracker, z_floor,
                              candidate_walls=('NORTH', 'WEST', 'EAST'))
    if _d:
        _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))

    # 2. Tall Bookshelves / Archive cupboards
    _try_place_wall_prop(bm, 'BOOKSHELF', 1.30, 0.42, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))

    # 3. File / Record Chest
    _try_place_wall_prop(bm, 'CHEST', 0.95, 0.50, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    # 4. Small visitor table or bench if room allows
    if rw >= 3.6 and rd >= 3.6:
        _try_place_wall_prop(bm, 'BENCH', 1.20, 0.42, tracker, z_floor,
                             candidate_walls=('SOUTH', 'EAST', 'WEST'), length=1.20)

    # 5. Executive ornate office area rugs (oversized + layered)
    rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_CRIMSON'])
    rug_w, rug_l = _area_rug_size(rw, rd, coverage=0.82, max_w=4.20, max_l=5.20,
                                  min_w=2.40, min_l=2.80)
    _lay_rug(bm, tracker, rm, rng, rug_choice, rcx, rcy, z_floor, rug_w, rug_l)

    # 5b. Visitor-side runner so offices get two rugs
    if (rw >= 3.4 or rd >= 3.4) and density >= 0.4:
        sub = 'RUG_FOREST' if rug_choice != 'RUG_FOREST' else 'RUG_CRIMSON'
        _lay_rug(bm, tracker, rm, rng, sub, rcx, rm.bounds[2] + rd * 0.20, z_floor,
                 min(1.60, rw * 0.40), min(3.00, rd * 0.46), allow_overlap=False)

    # 6. Ceiling light
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_industrial_bay(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                            rng, density: float):
    """Bare industrial fit-out: bulk piles, stacked crates, barrels and chests.
    Warehouses store both bulk timber (logs/planks) and dressed cut-stone blocks.
    Lumber mills store heavy log pyramids and sawn plank stacks wherever space allows.
    No rugs, no domestic furniture."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    arch = getattr(tracker, 'archetype', '')
    is_warehouse = (arch == 'WAREHOUSE')
    is_quarry = (arch == 'QUARRY') or rm.role == 'STONE_STORE'
    # Tier-1 open-air warehouse stockpiles carry product only: no shelving,
    # chests or hanging lanterns (there is no ceiling to hang them from).
    bare = bool(getattr(tracker, 'bare_stockpile', False))

    # Select pile types: Warehouse holds BOTH timber and stone blocks!
    # True worst-case footprints (incl. jitter) behind each reserve:
    # - LOG_PILE (length=2.0): ~2.32 x 1.82 -> reserve 2.45 x 2.00.
    # - PLANK_PILE (length=2.0): ~2.28 x 0.64 -> reserve 2.40 x 1.05.
    # - STONE_PILE (length=1.9): ~2.07 x 1.18 -> reserve 2.20 x 1.40.
    if is_quarry:
        pile_keys = ['STONE_PILE', 'STONE_PILE', 'CRATE', 'STONE_PILE']
    elif is_warehouse:
        pile_keys = ['LOG_PILE', 'STONE_PILE', 'PLANK_PILE', 'STONE_PILE', 'LOG_PILE', 'PLANK_PILE', 'CRATE']
    else:
        # Lumber mill and timber workshops: stacked round logs and sawn plank piles
        pile_keys = ['LOG_PILE', 'PLANK_PILE', 'LOG_PILE', 'PLANK_PILE', 'LOG_PILE', 'CRATE']

    max_piles = 5 if max(rw, rd) >= 8.5 else (3 if max(rw, rd) >= 5.0 else 2)
    placed = 0
    candidate_walls = ('NORTH', 'SOUTH', 'EAST', 'WEST')
    for key in pile_keys:
        if placed >= max_piles:
            break
        if key == 'CRATE':
            d = _try_place_wall_prop(bm, 'CRATE', 0.70, 0.70, tracker, z_floor,
                                     candidate_walls=candidate_walls,
                                     size=0.66, check_windows=False)
        elif key == 'STONE_PILE':
            # Same true footprint as the stone store (~2.07 x 1.18 incl.
            # yaw): the old 2.10 x 1.10 box let blocks poke into walls.
            d = _try_place_wall_prop(bm, key, 2.20, 1.40, tracker, z_floor,
                                     candidate_walls=candidate_walls,
                                     length=1.9, check_windows=False)
        elif key == 'LOG_PILE':
            d = _try_place_wall_prop(bm, key, 2.45, 2.00, tracker, z_floor,
                                     candidate_walls=candidate_walls,
                                     length=2.0, check_windows=False)
        else:
            d = _try_place_wall_prop(bm, key, 2.40, 1.05, tracker, z_floor,
                                     candidate_walls=candidate_walls,
                                     length=2.0, check_windows=False)
        if d is not None:
            placed += 1

    # Guaranteed bulk: place big storage piles at free floor spots
    fallback_spots = [
        (rm.bounds[0] + 1.45, rcy),
        (rm.bounds[1] - 1.45, rcy),
        (rcx, rm.bounds[2] + 1.15),
        (rcx, rm.bounds[3] - 1.15),
        (rm.bounds[0] + 1.65, rm.bounds[2] + 1.35),
        (rm.bounds[1] - 1.65, rm.bounds[2] + 1.35),
        (rm.bounds[0] + 1.65, rm.bounds[3] - 1.35),
        (rm.bounds[1] - 1.65, rm.bounds[3] - 1.35),
    ]
    for (fx, fy) in fallback_spots:
        if placed >= max_piles + 1:
            break
        if is_quarry:
            key = 'STONE_PILE'
        elif is_warehouse:
            key = rng.choice(('LOG_PILE', 'STONE_PILE', 'PLANK_PILE'))
        else:
            key = rng.choice(('LOG_PILE', 'PLANK_PILE'))
        # Per-key reserve matching the true built footprint (see above).
        if key == 'LOG_PILE':
            fbx, fby = 1.25, 1.00
        elif key == 'STONE_PILE':
            fbx, fby = 1.15, 0.70
        else:
            fbx, fby = 1.20, 0.55
        bx0, bx1, by0, by1 = fx - fbx, fx + fbx, fy - fby, fy + fby
        if tracker.is_free(bx0, bx1, by0, by1, check_windows=False):
            tracker.occupy(bx0, bx1, by0, by1)
            build_prop(bm, key, fx, fy, z_floor, 0.0, length=2.0)
            placed += 1

    if not bare:
        if is_quarry:
            _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                                 candidate_walls=('SOUTH', 'WEST', 'EAST', 'NORTH'))
        else:
            _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                                 candidate_walls=('NORTH', 'EAST', 'WEST'))

    # Stacked crates, barrels in the free corners.
    for cx in (rm.bounds[0] + 0.55, rm.bounds[1] - 0.55):
        for cy in (rm.bounds[2] + 0.55, rm.bounds[3] - 0.55):
            if not tracker.is_free(cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42):
                continue
            tracker.occupy(cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42)
            what = rng.random()
            if what < 0.5:
                build_prop(bm, 'CRATE', cx, cy, z_floor, 0.0, size=0.60)
                build_prop(bm, 'CRATE', cx, cy, z_floor + 0.60, rng.uniform(0, 6.28), size=0.48)
            else:
                build_prop(bm, 'BARREL', cx, cy, z_floor, rng.uniform(0, 6.28))

    if not bare:
        _try_place_wall_prop(bm, 'CHEST', 1.05, 0.55, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_stone_store(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                         rng, density: float):
    """Heavy industrial stone storage yard & masonry cutting depot fit-out.
    Zero domestic furniture, zero rugs, zero potted plants.
    Cut-stone stacks on timber skids, stone chipping rubble, heavy mason tool benches,
    iron-bound tool chests, equipment shelves, tool crates, water/oil barrels,
    and rafters hung with chain lanterns.
    """
    from .quarry import build_cut_block_stack, build_rubble_pile
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # True worst-case footprints (incl. yaw jitter), so every reserved
    # tracker box below always contains the geometry actually built:
    # - STONE_PILE (length=1.9): ~2.07 x 1.18 -> reserve 2.20 x 1.40.
    # - cut-block stack on skids: ~2.31 x 1.30 -> reserve 2.50 x 1.40.
    # - indoor chipping rubble (spread=0.7): +/-0.80 box incl. chunk radius.
    _RUBBLE_HALF = 0.80

    def _place_foot_rubble(cx, cy, yaw, stack_half_depth, seed):
        """Stone-chipping pile at the foot of a block stack.

        Tries the face of the stack first, then behind it, then each
        flank; the first tracker-free spot is reserved and built with a
        tight indoor scatter. When the bay is full the rubble is skipped
        outright - a missing pile beats one clipping through blocks,
        props or walls.
        """
        fx, fy = math.sin(yaw), -math.cos(yaw)
        px, py = -fy, fx
        for (ox, oy) in ((fx, fy), (-fx, -fy), (px, py), (-px, -py)):
            d = stack_half_depth + _RUBBLE_HALF + 0.08
            rx = cx + ox * d + rng.uniform(-0.10, 0.10)
            ry = cy + oy * d + rng.uniform(-0.10, 0.10)
            if tracker.is_free(rx - _RUBBLE_HALF, rx + _RUBBLE_HALF,
                               ry - _RUBBLE_HALF, ry + _RUBBLE_HALF,
                               check_windows=False):
                tracker.occupy(rx - _RUBBLE_HALF, rx + _RUBBLE_HALF,
                               ry - _RUBBLE_HALF, ry + _RUBBLE_HALF)
                build_rubble_pile(bm, rx, ry, z_ground=z_floor,
                                  count=rng.randint(3, 5), seed=seed,
                                  spread=0.7)
                return True
        return False

    # 1. Large cut-stone block stacks along the walls (quarry product on skids)
    num_stacks = 3 if max(rw, rd) >= 8.5 else (2 if max(rw, rd) >= 4.8 else 1)
    placed_stacks = 0
    candidate_walls = ('NORTH', 'SOUTH', 'EAST', 'WEST')
    for _ in range(num_stacks):
        d = _try_place_wall_prop(bm, 'STONE_PILE', 2.20, 1.40, tracker, z_floor,
                                 candidate_walls=candidate_walls,
                                 length=1.9, check_windows=False)
        if d is not None:
            placed_stacks += 1
            # Scatter stone chippings at the foot of the block stack
            _place_foot_rubble(d[0], d[1], d[2], 0.70,
                               rng.randint(1, 10000))

    # 2. Fill the open storage shelter bay with staged cut-stone block stacks on timber skids
    fill_spots = [
        (rm.bounds[0] + 1.8, rcy),
        (rm.bounds[1] - 1.8, rcy),
        (rcx - rw * 0.22, rm.bounds[2] + 1.3),
        (rcx + rw * 0.22, rm.bounds[2] + 1.3),
        (rcx, rm.bounds[3] - 1.3),
    ]
    for (fx, fy) in fill_spots:
        bx0, bx1 = fx - 1.25, fx + 1.25
        by0, by1 = fy - 0.70, fy + 0.70
        if tracker.is_free(bx0, bx1, by0, by1, check_windows=False):
            tracker.occupy(bx0, bx1, by0, by1)
            build_cut_block_stack(bm, fx, fy, z_ground=z_floor,
                                  count=rng.choice([4, 6, 8]), seed=rng.randint(1, 10000))
            # Face the foot of the stack towards the room centre so the
            # chippings land in the open bay, not inside the wall.
            foot_yaw = 0.0 if fy >= rcy else math.pi
            _place_foot_rubble(fx, fy, foot_yaw, 0.70,
                               rng.randint(1, 10000))
            placed_stacks += 1

    # 2. Heavy masonry workbench / stone dressing station
    _d = _try_place_wall_prop(bm, 'DESK', 1.50, 0.75, tracker, z_floor,
                              candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
    if _d:
        # On top of the workbench: rough cut stone block being dressed
        wx, wy, wyaw = _d
        from ..materials import MAT_INDEX_CUT_STONE
        from ..mesh_utils import create_box
        create_box(bm, size=(0.38, 0.28, 0.22),
                   location=(wx + rng.uniform(-0.15, 0.15), wy + rng.uniform(-0.08, 0.08), z_floor + 0.78 + 0.11),
                   rotation=(0.0, 0.0, rng.uniform(-0.2, 0.2)), mat_index=MAT_INDEX_CUT_STONE)
        # Stool at the workbench
        sx = wx + math.sin(wyaw) * 0.70
        sy = wy - math.cos(wyaw) * 0.70
        if tracker.is_free(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25):
            tracker.occupy(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25)
            build_prop(bm, 'STOOL', sx, sy, z_floor, 0.0)

    # 3. Tool storage shelf (for levels, wedges, measuring squares)
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST', 'SOUTH'))

    # 4. Iron-bound heavy tool chests (wedges, sledges, feathers)
    _try_place_wall_prop(bm, 'CHEST', 1.05, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))
    if max(rw, rd) >= 7.0:
        _try_place_wall_prop(bm, 'CHEST', 0.95, 0.50, tracker, z_floor,
                             candidate_walls=('WEST', 'EAST', 'SOUTH'))

    # 5. Corners: Stacked tool crates and water/oil barrels (for stone cutting)
    for cx in (rm.bounds[0] + 0.55, rm.bounds[1] - 0.55):
        for cy in (rm.bounds[2] + 0.55, rm.bounds[3] - 0.55):
            if not tracker.is_free(cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42):
                continue
            tracker.occupy(cx - 0.42, cx + 0.42, cy - 0.42, cy + 0.42)
            if rng.random() < 0.55:
                # Stacked quarry tool crates
                build_prop(bm, 'CRATE', cx, cy, z_floor, 0.0, size=0.62)
                build_prop(bm, 'CRATE', cx, cy, z_floor + 0.58, rng.uniform(0, 6.28), size=0.48)
            else:
                # Water barrel for lubricating stone saws
                build_prop(bm, 'BARREL', cx, cy, z_floor, rng.uniform(0, 6.28))

    # 6. Industrial chain lanterns suspended from rafters
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)
    if rw >= 8.0:
        build_prop(bm, 'CHAIN_LANTERN', rcx - rw * 0.28, rcy, z_ceil, 0.0)
        build_prop(bm, 'CHAIN_LANTERN', rcx + rw * 0.28, rcy, z_ceil, 0.0)
    elif rd >= 8.0:
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy - rd * 0.28, z_ceil, 0.0)
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy + rd * 0.28, z_ceil, 0.0)


def _furnish_workshop(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """Furnishes a tradesman's workshop or smithy."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Heavy work desk (workbench chair + clutter)
    _d = _try_place_wall_prop(bm, 'DESK', 1.40, 0.68, tracker, z_floor,
                              candidate_walls=('NORTH', 'WEST', 'EAST'))
    if _d:
        _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))

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

    # 5. Work-floor rug is laid by the room decor pass (skipped in bare
    #    industrial workshops), so nothing to do here.

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


# ---------------------------------------------------------------------------
# Dedicated artisan craft workshops. Each trade gets its own production room
# (bakehouse, brewhouse, ...) composed from the prop catalogue, so an
# artisan's ground floor reads as their craft instead of a generic office.
# ---------------------------------------------------------------------------

def _place_craft_table(bm, tracker: RoomOccupancyTracker, z_floor: float, rng,
                       length: float = 1.40, width: float = 0.85):
    """Best-effort work table standing free in the open floor (not wall-backed)."""
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    cands = [(rcx, rcy), (rcx - 0.9, rcy), (rcx + 0.9, rcy),
             (rcx, rcy - 0.9), (rcx, rcy + 0.9),
             (rcx - 0.9, rcy - 0.9), (rcx + 0.9, rcy + 0.9)]
    rng.shuffle(cands)
    for tx, ty in cands:
        tx += _jit(rng, 0.15)
        ty += _jit(rng, 0.15)
        for yaw, tw, td in ((0.0, length, width), (math.pi * 0.5, width, length)):
            if tracker.is_free(tx - tw * 0.5 - 0.30, tx + tw * 0.5 + 0.30,
                               ty - td * 0.5 - 0.30, ty + td * 0.5 + 0.30):
                tracker.occupy(tx - tw * 0.5, tx + tw * 0.5, ty - td * 0.5, ty + td * 0.5)
                build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, yaw,
                           length=length, width=width)
                return (tx, ty, yaw)
    return None


def _place_floor_prop(bm, tracker: RoomOccupancyTracker, z_floor: float, rng,
                      key: str, half_w: float, half_d: float, **params):
    """Best-effort freestanding prop (workstation, rack, block) in the open
    floor. Tries room centre first, then a ring around it, both yaw axes."""
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    cands = [(rcx, rcy), (rcx - 1.1, rcy), (rcx + 1.1, rcy),
             (rcx, rcy - 1.1), (rcx, rcy + 1.1),
             (rcx - 1.1, rcy - 1.1), (rcx + 1.1, rcy + 1.1),
             (rcx - 1.1, rcy + 1.1), (rcx + 1.1, rcy - 1.1)]
    rng.shuffle(cands)
    for cx, cy in cands:
        cx += _jit(rng, 0.15)
        cy += _jit(rng, 0.15)
        for yaw, hw, hd in ((0.0, half_w, half_d), (math.pi * 0.5, half_d, half_w)):
            if tracker.is_free(cx - hw, cx + hw, cy - hd, cy + hd):
                tracker.occupy(cx - hw, cx + hw, cy - hd, cy + hd)
                build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                return (cx, cy, yaw)
    # Fallback: grid-scan for ANY fitting spot so tight rooms still get
    # their workstation instead of staying bare.
    _spot = _freest_spot(tracker, rng)
    if _spot is not None and _spot[2] >= max(half_w, half_d) - 1e-6:
        _sx, _sy = _spot[0], _spot[1]
        tracker.occupy(_sx - half_w, _sx + half_w, _sy - half_d, _sy + half_d)
        build_prop(bm, key, _sx, _sy, z_floor, rng.uniform(0.0, 6.28), **params)
        return (_sx, _sy, 0.0)
    return None


def _place_corner_prop(bm, tracker: RoomOccupancyTracker, z_floor: float, rng,
                       key: str, half_w: float, half_d: float, **params):
    """Freestanding prop tucked into a room corner facing the centre (dress
    forms, floor scales); falls back to open-floor placement."""
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    corners = [
        (tracker.rx0 + half_w + 0.06, tracker.ry0 + half_d + 0.06),
        (tracker.rx1 - half_w - 0.06, tracker.ry0 + half_d + 0.06),
        (tracker.rx0 + half_w + 0.06, tracker.ry1 - half_d - 0.06),
        (tracker.rx1 - half_w - 0.06, tracker.ry1 - half_d - 0.06),
    ]
    rng.shuffle(corners)
    for cx, cy in corners:
        if tracker.is_free(cx - half_w, cx + half_w, cy - half_d, cy + half_d):
            tracker.occupy(cx - half_w, cx + half_w, cy - half_d, cy + half_d)
            yaw = math.atan2(rcy - cy, rcx - cx)
            build_prop(bm, key, cx, cy, z_floor, yaw, **params)
            return (cx, cy, yaw)
    return _place_floor_prop(bm, tracker, z_floor, rng, key,
                             half_w, half_d, **params)


def _dress_craft_table(bm, tx: float, ty: float, yaw: float, z_table: float,
                       rng, goods):
    """Lay trade goods in a row along a work table top (lifted a hair so
    flat goods like fish/meat never z-fight the table surface)."""
    n = len(goods)
    for i, g in enumerate(goods):
        off = (i - (n - 1) * 0.5) * 0.45
        gx, gy = _table_offset(tx, ty, off, 0.0, yaw)
        build_prop(bm, g, gx, gy, z_table + 0.012, rng.uniform(0.0, 6.28))


def _stool_near(bm, tracker: RoomOccupancyTracker, tx: float, ty: float,
                yaw: float, z_floor: float, rng) -> bool:
    """A work stool tucked against a work table, when the floor is clear."""
    for sx, sy in (_table_offset(tx, ty, 0.0, 0.80, yaw),
                   _table_offset(tx, ty, 0.0, -0.80, yaw)):
        if tracker.is_free(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25):
            tracker.occupy(sx - 0.25, sx + 0.25, sy - 0.25, sy + 0.25)
            build_prop(bm, 'STOOL', sx, sy, z_floor, rng.uniform(0.0, 6.28))
            return True
    return False


def _place_goods_row(bm, tracker: RoomOccupancyTracker, z_floor: float, rng,
                     key: str, count: int = 3, box: float = 0.32) -> int:
    """Row of small floor goods (sacks, pots, crates) along the freest wall base."""
    rx0, rx1, ry0, ry1 = tracker.rx0, tracker.rx1, tracker.ry0, tracker.ry1
    spots = []
    for i in range(count):
        f = (i + 1) / (count + 1)
        spots += [(rx0 + (rx1 - rx0) * f, ry1 - box - 0.05),
                  (rx0 + (rx1 - rx0) * f, ry0 + box + 0.05),
                  (rx0 + box + 0.05, ry0 + (ry1 - ry0) * f),
                  (rx1 - box - 0.05, ry0 + (ry1 - ry0) * f)]
    rng.shuffle(spots)
    placed = 0
    for cx, cy in spots:
        if placed >= count:
            break
        if tracker.is_free(cx - box, cx + box, cy - box, cy + box):
            tracker.occupy(cx - box, cx + box, cy - box, cy + box)
            build_prop(bm, key, cx + _jit(rng, 0.08), cy + _jit(rng, 0.08),
                       z_floor, rng.uniform(0.0, 6.28))
            placed += 1
    return placed


def _furnish_bakehouse(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Master baker's bakehouse: kneading tables with dough prep, flour sacks,
    loaf shelves and oven fuel. (The brick hearth oven itself is kit geometry.)"""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    for _ti in range(2 if min(rw, rd) >= 3.4 else 1):
        t = _place_craft_table(bm, tracker, z_floor, rng)
        if t is None:
            break
        if _ti == 0:  # kneading table: proving bowl and fresh loaves
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['DOUGH_BOWL', 'BREAD_LOAF', 'BREAD_LOAF'])
        else:
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['FOODPREP_CLUTTER', 'BREAD_LOAF'])
        _stool_near(bm, tracker, t[0], t[1], t[2], z_floor, rng)

    # Cooling rack laden with loaves along a free wall.
    _try_place_wall_prop(bm, 'BREAD_RACK', 1.50, 0.50, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))

    _place_goods_row(bm, tracker, z_floor, rng, 'SACK', count=4)  # flour
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))  # loaf shelves
    if rng.random() < density:
        _try_place_wall_prop(bm, 'LOG_PILE', 1.60, 0.55, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'),
                             length=1.60, radius=0.15, rows=2)  # oven fuel

    rug_w = min(2.60, max(1.60, rw * 0.55))
    rug_l = min(3.40, max(2.00, rd * 0.55))
    _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', rcx, rcy, z_floor, rug_w, rug_l)
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_brewhouse(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Brewhouse: mash vats along the wall, keg rows, malt sacks and a tasting
    corner. Stays bare underfoot (wet trade)."""
    tracker.no_rugs = True
    tracker.rug_count = 1
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rx0, rx1, ry1 = tracker.rx0, tracker.rx1, tracker.ry1

    # Mash tun in the freest corner, keg rack along a free wall.
    _place_floor_prop(bm, tracker, z_floor, rng, 'MASH_TUN', 0.62, 0.62)
    _try_place_wall_prop(bm, 'KEG_RACK', 1.30, 0.62, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))

    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=2, box=0.40)  # spare kegs
    _place_goods_row(bm, tracker, z_floor, rng, 'SACK', count=3)  # malt
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'SOUTH'))
    _place_floor_prop(bm, tracker, z_floor, rng, 'BOTTLE_CRATE', 0.33, 0.33)
    if rng.random() < density:  # tasting corner: round table, mugs, bottles
        for tx, ty in ((rcx, rcy), (rcx - 1.0, rcy), (rcx + 1.0, rcy)):
            if tracker.is_free(tx - 0.75, tx + 0.75, ty - 0.75, ty + 0.75):
                tracker.occupy(tx - 0.75, tx + 0.75, ty - 0.75, ty + 0.75)
                z_table = z_floor + 0.775
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.55)
                build_prop(bm, 'PEWTER_TANKARD', tx - 0.18, ty, z_table, 0.0)
                build_prop(bm, 'PEWTER_TANKARD', tx + 0.18, ty + 0.10, z_table, 0.0)
                build_prop(bm, 'BOTTLE_CLUSTER', tx, ty - 0.22, z_table, 0.0)
                break
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_butchery(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """Butchery and smokehouse: cleaver blocks, brine barrels, salt sacks and
    smoke fuel. Stays bare underfoot."""
    tracker.no_rugs = True
    tracker.rug_count = 1
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    # Central stump block with cleaver and cuts; a prep table if the block
    # finds no room.
    if _place_floor_prop(bm, tracker, z_floor, rng, 'BUTCHER_BLOCK', 0.38, 0.38) is None:
        t = _place_craft_table(bm, tracker, z_floor, rng)
        if t is not None:
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['MEAT', 'MEAT_SMALL'])
    # A prep table laid with cuts either way.
    t = _place_craft_table(bm, tracker, z_floor, rng)
    if t is not None:
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['MEAT', 'MEAT_SMALL', 'MEAT'])
    # Two hanging meat rails along free walls.
    _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.30, 0.35, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))
    _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.10, 0.35, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
    # More cuts laid out on a second table when space allows.
    t2 = _place_craft_table(bm, tracker, z_floor, rng, length=1.20, width=0.75)
    if t2 is not None:
        _dress_craft_table(bm, t2[0], t2[1], t2[2], z_table, rng,
                           ['MEAT_SMALL', 'MEAT_SMALL', 'FOODPREP_CLUTTER'])

    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=3, box=0.40)  # brine
    _place_goods_row(bm, tracker, z_floor, rng, 'SACK', count=2)  # salt
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))
    if rng.random() < density:
        _try_place_wall_prop(bm, 'LOG_PILE', 1.60, 0.55, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'),
                             length=1.60, radius=0.15, rows=2)  # smoke fuel
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_tailor_atelier(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                            rng, density: float):
    """Tailor's atelier: cutting table with cloth stacks, bolt shelves, garment
    wardrobe and a fitting corner."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    t = _place_craft_table(bm, tracker, z_floor, rng, length=1.60, width=0.90)
    if t is not None:  # cutting table dressed with folded cloth
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['FOLDED_CLOTH', 'FOLDED_CLOTH'])
        _stool_near(bm, tracker, t[0], t[1], t[2], z_floor, rng)

    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))  # cloth bolts
    _try_place_wall_prop(bm, 'WARDROBE', 1.20, 0.55, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'NORTH'))
    # Dress form tucked into a free corner facing the room, bolt bin along
    # a free wall.
    _place_corner_prop(bm, tracker, z_floor, rng, 'DRESS_FORM', 0.30, 0.30)
    _try_place_wall_prop(bm, 'CLOTH_BOLT_BIN', 0.60, 0.48, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'NORTH'))
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    rug_w = min(2.60, max(1.60, rw * 0.55))
    rug_l = min(3.40, max(2.00, rd * 0.55))
    _lay_rug(bm, tracker, rm, rng, 'RUG_SAPPHIRE', rcx, rcy, z_floor, rug_w, rug_l)
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_goldsmith(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Goldsmith's workshop: fine bench with ledger, display shelves and an
    iron-strapped strongbox."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    d = _try_place_wall_prop(bm, 'DESK', 1.40, 0.68, tracker, z_floor,
                             candidate_walls=('NORTH', 'WEST', 'EAST'))
    if d:
        _dress_desk(bm, tracker, d[0], d[1], d[2], z_floor, rng, (rcx, rcy))

    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))  # display
    _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))  # strongbox
    if rng.random() < density:  # gem side table with tray
        for tx, ty in ((rcx, rcy), (rcx - 1.0, rcy), (rcx + 1.0, rcy)):
            if tracker.is_free(tx - 0.60, tx + 0.60, ty - 0.60, ty + 0.60):
                tracker.occupy(tx - 0.60, tx + 0.60, ty - 0.60, ty + 0.60)
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.45)
                build_prop(bm, 'GEM_TRAY', tx, ty, z_floor + 0.775, 0.0)
                break
    # Standing scale in the freest corner, strongbox along a free wall.
    _place_floor_prop(bm, tracker, z_floor, rng, 'BALANCE_SCALE', 0.30, 0.30)
    _try_place_wall_prop(bm, 'STRONGBOX', 0.66, 0.44, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    rug_w = min(2.40, max(1.50, rw * 0.50))
    rug_l = min(3.00, max(1.80, rd * 0.50))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor, rug_w, rug_l)
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_smithy(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                    rng, density: float):
    """Tool smithy: quench barrels, coal pile, stock crates and a tool/product
    rack. (The forge itself is kit geometry.) Stays bare underfoot."""
    tracker.no_rugs = True
    tracker.rug_count = 1
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.20, 0.45, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))  # tool display
    # Anvil and grindstone on the open floor, hanging tool rack on a wall.
    _place_floor_prop(bm, tracker, z_floor, rng, 'ANVIL', 0.55, 0.40)
    _place_floor_prop(bm, tracker, z_floor, rng, 'GRINDSTONE', 0.45, 0.40)
    _try_place_wall_prop(bm, 'TOOL_RACK', 1.20, 0.30, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=2, box=0.40)  # quench
    _try_place_wall_prop(bm, 'LOG_PILE', 1.60, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'),
                         length=1.60, radius=0.15, rows=2)  # coal
    _place_goods_row(bm, tracker, z_floor, rng, 'CRATE', count=2, box=0.36)  # stock
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    if rng.random() < density:
        _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_joinery(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float):
    """Joiner's workshop: workbenches, lumber and plank piles, finished pieces.
    Stays bare underfoot (shavings)."""
    tracker.no_rugs = True
    tracker.rug_count = 1
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # Joiner's bench on the open floor (plain tables if it finds no room),
    # sawbuck in the freest corner.
    if _place_floor_prop(bm, tracker, z_floor, rng, 'JOINER_BENCH', 1.00, 0.65,
                         length=1.70) is None:
        for _ in range(2 if min(rw, rd) >= 3.4 else 1):
            t = _place_craft_table(bm, tracker, z_floor, rng, length=1.60, width=0.90)
            if t is None:
                break
            _stool_near(bm, tracker, t[0], t[1], t[2], z_floor, rng)
    _place_floor_prop(bm, tracker, z_floor, rng, 'SAWBUCK', 0.75, 0.45)

    _try_place_wall_prop(bm, 'PLANK_PILE', 1.80, 0.55, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'),
                         length=1.80, layers=5)  # seasoned boards
    _try_place_wall_prop(bm, 'LOG_PILE', 1.60, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'),
                         length=1.60, radius=0.17, rows=3)  # timber
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    if rng.random() < density:  # finished pieces: chair + chest
        _try_place_wall_prop(bm, 'CHAIR', 0.55, 0.55, tracker, z_floor,
                             candidate_walls=('SOUTH', 'EAST', 'WEST'))
        _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_fishery(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                     rng, density: float):
    """Fishery: gutting tables with the day's catch, fish-box crates, salt
    barrels and tackle shelves. Stays bare underfoot."""
    tracker.no_rugs = True
    tracker.rug_count = 1
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.775

    # Gutting tables laden with the day's catch (lots of fish).
    for _ in range(2 if min(rw, rd) >= 3.4 else 1):
        t = _place_craft_table(bm, tracker, z_floor, rng)
        if t is None:
            # Compact gutting table for the small fishery chambers.
            t = _place_craft_table(bm, tracker, z_floor, rng,
                                   length=0.95, width=0.62)
        if t is None:
            break
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['FISH', 'FISH', 'FOODPREP_CLUTTER'])
    # A third table of sorted catch when there is room.
    t3 = _place_craft_table(bm, tracker, z_floor, rng, length=1.20, width=0.75)
    if t3 is not None:
        _dress_craft_table(bm, t3[0], t3[1], t3[2], z_table, rng,
                           ['FISH', 'FISH', 'FOODPREP_CLUTTER'])
    # Fish boxes: fish kept in slatted crates, never loose on the bare floor.
    for _ci in range(2):
        _place_floor_prop(bm, tracker, z_floor, rng, 'CRATE', 0.30, 0.30)
        _place_goods_row(bm, tracker, z_floor, rng, 'CRATE', count=1, box=0.30)

    # Fish drying rack + hanging fish rail along free walls (fish hang, they
    # do not lie on the floor).
    _try_place_wall_prop(bm, 'FISH_DRYING_RACK', 1.60, 0.80, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))
    _try_place_wall_prop(bm, 'FISH_RAIL', 1.30, 0.35, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
    _place_floor_prop(bm, tracker, z_floor, rng, 'ROPE_COIL', 0.28, 0.28)
    # Curing stringers hung from the beams (two when there is room).
    for _si in range(2):
        _spot = _freest_spot(tracker, rng)
        if _spot is not None and _spot[2] >= 0.20 - 1e-6:
            tracker.occupy(_spot[0] - 0.20, _spot[0] + 0.20,
                           _spot[1] - 0.20, _spot[1] + 0.20)
            build_prop(bm, 'FISH_STRINGER', _spot[0], _spot[1], z_ceil, 0.0)
        else:
            break

    _place_goods_row(bm, tracker, z_floor, rng, 'CRATE', count=3, box=0.36)  # fish boxes
    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=2, box=0.40)  # salt barrels
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))  # tackle
    if rng.random() < density:
        _place_goods_row(bm, tracker, z_floor, rng, 'CLAY_POT', count=2, box=0.30)
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _dress_shop_for_trade(bm, tracker: RoomOccupancyTracker, z_floor: float,
                          rng, arch: str) -> None:
    """Best-effort trade counter dressing in an artisan STORE: the shop shows
    what the workshop below makes."""
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    z_table = z_floor + 0.775
    if arch in ('BLACKSMITH', 'TOOLSMITH'):  # arms/tools display racks
        _try_place_wall_prop(bm, 'WEAPON_RACK', 1.20, 0.45, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
        _try_place_wall_prop(bm, 'TOOL_RACK', 1.00, 0.30, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH'))
    if arch == 'FURNITURE_MAKER':  # showroom pieces
        _try_place_wall_prop(bm, 'CHAIR', 0.55, 0.55, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
        _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
    table_goods = {
        'TAILOR': ['FOLDED_CLOTH', 'FOLDED_CLOTH'],
        'BAKERY': ['BREAD_LOAF', 'BREAD_LOAF', 'DOUGH_BOWL'],
        'BUTCHER': ['MEAT', 'MEAT_SMALL', 'MEAT'],
        'FISHERMAN': ['FISH', 'FISH', 'FISH', 'FOODPREP_CLUTTER'],
        'JEWELER': ['BOTTLE_CLUSTER', 'BOTTLE', 'BOTTLE'],
        'BREWERY': ['PEWTER_TANKARD', 'PEWTER_TANKARD', 'BOTTLE_CLUSTER'],
    }.get(arch)
    # Trade showpieces that do not fit on the table.
    if arch == 'BAKERY':
        _try_place_wall_prop(bm, 'BREAD_RACK', 1.00, 0.50, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
    elif arch == 'BREWERY':
        _place_floor_prop(bm, tracker, z_floor, rng, 'BOTTLE_CRATE', 0.33, 0.33)
    elif arch == 'BUTCHER':
        _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.00, 0.35, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
    elif arch == 'TAILOR':
        _place_corner_prop(bm, tracker, z_floor, rng, 'DRESS_FORM', 0.30, 0.30)
        _try_place_wall_prop(bm, 'CLOTH_BOLT_BIN', 0.60, 0.48, tracker, z_floor,
                             candidate_walls=('WEST', 'EAST', 'NORTH'))
    elif arch == 'JEWELER':
        _lay_out_jeweler_counter(bm, tracker, z_floor, rng)
    # Stepped market display near the entrance, dressed with sale goods.
    _place_market_display(bm, tracker, z_floor, rng, arch)
    if not table_goods:
        return
    is_round = (arch == 'BREWERY')
    for tx, ty in ((rcx, rcy), (rcx - 1.0, rcy), (rcx + 1.0, rcy),
                   (rcx, rcy - 1.0), (rcx, rcy + 1.0)):
        if is_round:
            if tracker.is_free(tx - 0.70, tx + 0.70, ty - 0.70, ty + 0.70):
                tracker.occupy(tx - 0.70, tx + 0.70, ty - 0.70, ty + 0.70)
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.55)
                _dress_craft_table(bm, tx, ty, 0.0, z_table, rng, table_goods)
                return
        else:
            t = _place_craft_table(bm, tracker, z_floor, rng)
            if t is not None:
                _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng, table_goods)
                return


def _lay_out_jeweler_counter(bm, tracker: RoomOccupancyTracker, z_floor: float,
                             rng) -> None:
    """Merchant counter ensemble: gem tray + plant on the counter top, the
    standing scale tucked in the merchant zone behind, strongbox at the end."""
    cc = getattr(tracker, 'shop_counter', None)
    if cc is None:
        _place_corner_prop(bm, tracker, z_floor, rng, 'BALANCE_SCALE', 0.30, 0.30)
        _try_place_wall_prop(bm, 'STRONGBOX', 0.66, 0.44, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
        return
    # Gem tray centre counter, plant at one end.
    build_prop(bm, 'GEM_TRAY', cc['cx'], cc['cy'], cc['top_z'], cc['yaw'])
    _ex = cc['cx'] + math.cos(cc['yaw']) * (cc['length'] * 0.5 - 0.22)
    _ey = cc['cy'] + math.sin(cc['yaw']) * (cc['length'] * 0.5 - 0.22)
    build_prop(bm, 'POTTED_PLANT_SMALL', _ex, _ey, cc['top_z'],
               rng.uniform(0.0, 6.28))
    # Scale behind the counter when there is a merchant zone, else a corner.
    if cc.get('freestanding'):
        _scx = cc['cx'] + cc['mdx'] * 0.62
        _scy = cc['cy'] + cc['mdy'] * 0.62
        if tracker.is_free(_scx - 0.30, _scx + 0.30, _scy - 0.30, _scy + 0.30):
            tracker.occupy(_scx - 0.30, _scx + 0.30, _scy - 0.30, _scy + 0.30)
            build_prop(bm, 'BALANCE_SCALE', _scx, _scy, z_floor,
                       rng.uniform(0.0, 6.28))
        else:
            _place_corner_prop(bm, tracker, z_floor, rng, 'BALANCE_SCALE',
                               0.30, 0.30)
    else:
        _place_corner_prop(bm, tracker, z_floor, rng, 'BALANCE_SCALE',
                           0.30, 0.30)
    _try_place_wall_prop(bm, 'STRONGBOX', 0.66, 0.44, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))


def _place_market_display(bm, tracker: RoomOccupancyTracker, z_floor: float,
                          rng, arch: str) -> None:
    """Stepped three-tier goods display near the shop entrance, dressed with
    the trade's own sale goods. Faces the street door."""
    _tier_goods = {
        'BAKERY': [['BREAD_LOAF', 'BREAD_LOAF'], ['BREAD_LOAF', 'BREAD_LOAF'],
                   ['BREAD_LOAF', 'BREAD_LOAF']],
        'BREWERY': [['BOTTLE', 'BOTTLE'], ['PEWTER_TANKARD', 'PEWTER_TANKARD'],
                    ['BOTTLE_CLUSTER']],
        'BUTCHER': [['MEAT', 'MEAT_SMALL'], ['MEAT_SMALL', 'MEAT'],
                    ['MEAT', 'MEAT']],
        'TAILOR': [['FOLDED_CLOTH', 'FOLDED_CLOTH'],
                   ['FOLDED_CLOTH', 'FOLDED_CLOTH'],
                   ['BOOK_PILE_SMALL', 'FOLDED_CLOTH']],
        'JEWELER': [['FOLDED_CLOTH', 'FOLDED_CLOTH'], ['GEM_TRAY'],
                    ['BOTTLE_CLUSTER']],
        'BLACKSMITH': [['HORSESHOE', 'HORSESHOE'], ['HORSESHOE', 'HORSESHOE'],
                       ['CLAY_POT', 'HORSESHOE']],
        'TOOLSMITH': [['HORSESHOE', 'HORSESHOE'], ['HORSESHOE', 'HORSESHOE'],
                      ['CLAY_POT', 'HORSESHOE']],
        'FURNITURE_MAKER': [['WOODEN_BOWL', 'WOODEN_BOWL'],
                            ['WOODEN_BOWL', 'WOODEN_BOWL'],
                            ['WOODEN_BOWL', 'CLAY_POT']],
        'FISHERMAN': [['FISH', 'FISH'], ['FISH', 'FISH'],
                      ['FISH', 'FISH', 'FISH']],
    }.get(arch)
    if not _tier_goods:
        return
    if getattr(tracker, '_market_display_done', False):
        return
    tracker._market_display_done = True
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    _rx0, _rx1 = tracker.rx0, tracker.rx1
    _ry0, _ry1 = tracker.ry0, tracker.ry1

    def _yaw_away(cx, cy):
        """Face the display away from its nearest wall (back to the wall)."""
        d = {'-Y': cy - _ry0, '+Y': _ry1 - cy,
             '-X': cx - _rx0, '+X': _rx1 - cx}
        w = min(d, key=d.get)
        return {'-Y': 0.0, '+Y': math.pi, '-X': -math.pi * 0.5,
                '+X': math.pi * 0.5}[w]

    def _try_place(hw, hd):
        """Search WALL-hugging spots for a free patch of the given half-size.
        Corners first (ordered by closeness to the staircase so it lands under
        the stairs when it can), then wall midpoints. Never mid-room."""
        _spots = []
        _nf = _ry0 + hd + 0.10
        _nb = _ry1 - hd - 0.10
        _nl = _rx0 + hw + 0.10
        _nr = _rx1 - hw - 0.10
        _spots += [(_nl, _nf), (_nr, _nf), (_nl, _nb), (_nr, _nb)]
        for _f in (0.30, 0.70):
            _py = _ry0 + (_ry1 - _ry0) * _f
            _px = _rx0 + (_rx1 - _rx0) * _f
            _spots += [(_nl, _py), (_nr, _py), (_px, _nf), (_px, _nb)]
        # Order by closeness to the stairwell so the nearest wall nook wins.
        _sw = getattr(tracker, 'stair_hole', None)
        if _sw is not None:
            _sxc = (_sw[0] + _sw[1]) * 0.5
            _syc = (_sw[2] + _sw[3]) * 0.5
            _spots.sort(key=lambda p: (_check(p, hw, hd), 
                                       math.hypot(p[0] - _sxc, p[1] - _syc)))
        for _sx, _sy in _spots:
            _sx += _jit(rng, 0.06)
            _sy += _jit(rng, 0.06)
            if not tracker.is_free(_sx - hw, _sx + hw, _sy - hd, _sy + hd):
                continue
            tracker.occupy(_sx - hw, _sx + hw, _sy - hd, _sy + hd)
            return (_sx, _sy, _yaw_away(_sx, _sy))
        return None

    def _check(p, hw, hd):
        return 0 if tracker.is_free(p[0] - hw, p[0] + hw, p[1] - hd, p[1] + hd) else 1

    # Full-size display first, then a compact one for cramped shops.
    _placed = _try_place(0.85, 0.575)
    _disp_w = 1.50
    if _placed is None:
        _placed = _try_place(0.62, 0.50)
        _disp_w = 1.05
    if _placed is None:
        # No wall-hugging spot big enough: never drop it mid-room. Skip.
        return
    _cx, _cy, _yaw = _placed
    build_prop(bm, 'MARKET_DISPLAY', _cx, _cy, z_floor, _yaw, width=_disp_w)
    # Dress the tiers (mirror the builder: tier tops at local y +0.18/-0.18/
    # -0.54, z 0.50/0.85/1.20; slots at x scale with the display width).
    _cx_off = (_disp_w - 0.08) * 0.23
    _cyaw = _yaw
    _cos, _sin = math.cos(_cyaw), math.sin(_cyaw)
    for (_ly, _lz), _goods in zip(((0.17, 0.50), (-0.16, 0.85), (-0.50, 1.20)),
                                 _tier_goods):
        for _i, _g in enumerate(_goods):
            _lx = (-_cx_off if _i % 2 == 0 else _cx_off) if len(_goods) > 1 else 0.0
            _gx = _cx + _lx * _cos - _ly * _sin
            _gy = _cy + _lx * _sin + _ly * _cos
            build_prop(bm, _g, _gx, _gy, z_floor + _lz + 0.012,
                       _cyaw + rng.uniform(-0.15, 0.15))
    return


def _furnish_chapel(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                    rng, density: float):
    """Furnishes a chapel hall laid out right-to-left: altar counter on the
    EAST wall, congregation benches facing east, and the ceremonial aisle
    runner leading along X up to the altar."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Altar Counter along the East wall (falls back to West)
    placed_altar = _try_place_wall_prop(bm, 'COUNTER', 1.80, 0.60, tracker, z_floor,
                                        candidate_walls=('EAST',), length=1.80)
    if not placed_altar:
        _try_place_wall_prop(bm, 'COUNTER', 1.80, 0.60, tracker, z_floor,
                             candidate_walls=('WEST',), length=1.80)

    # 2. Columns of benches west of the aisle facing east (+X, backrest west).
    for bx in [rcx - rw * 0.05, rcx - rw * 0.30]:
        for sgn in (-1.0, 1.0):
            blen = min(2.2, rd * 0.36)
            by = rcy + sgn * (blen * 0.5 + 0.35)
            if tracker.is_free(bx - 0.25, bx + 0.25, by - blen * 0.5, by + blen * 0.5):
                tracker.occupy(bx - 0.25, bx + 0.25, by - blen * 0.5, by + blen * 0.5)
                build_prop(bm, 'BENCH', bx, by, z_floor, math.pi / 2, length=blen)

    # 2b. Ceremonial aisle runner leading along X up to the altar
    runner_l = min(12.00, max(4.60, rw * 0.86))
    runner_w = min(2.80, max(1.70, rd * 0.42))
    runner_l = min(runner_l, max(2.2, rw - 0.35))
    runner_w = min(runner_w, max(1.2, rd - 0.35))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor, runner_w, runner_l,
             yaw_max=0.06)

    # 2c. Side chapel rugs flanking the aisle to the north and south
    if rd >= 4.5 and density >= 0.4:
        side_l = min(2.20, max(1.30, rd * 0.28))
        side_w = min(5.00, max(2.60, rw * 0.55))
        for sgn in (-1.0, 1.0):
            _lay_rug(bm, tracker, rm, rng, 'RUG_SAPPHIRE', rcx, rcy + sgn * rd * 0.27, z_floor,
                     side_w, side_l, yaw_max=0.06, allow_overlap=False)

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


def _build_stall_divider(bm, x: float, y_back: float, depth: float, z_floor: float, height: float = 1.85):
    """An authentic equestrian stall partition wall.

    Features:
    - Heavy front aisle timber post (with beveled cap) and rear wall post.
    - Solid tongue-and-groove horizontal wooden planks on the lower half (horse bulkhead).
    - Heavy timber bottom sill and mid cap rail.
    - Upper horse-stall safety grille: top timber rail with vertical hand-forged iron bars.
    """
    from ..mesh_utils import create_beveled_box
    from ..materials import MAT_INDEX_TIMBER, MAT_INDEX_WOOD, MAT_INDEX_IRON

    post_s = 0.16
    front_y = y_back - depth + post_s * 0.5
    back_y = y_back - post_s * 0.5
    span = depth - post_s * 2.0
    mid_y = (front_y + back_y) * 0.5

    # 1. Front aisle timber post
    create_beveled_box(
        bm, size=(post_s, post_s, height),
        location=(x, front_y, z_floor + height * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
    # Pyramidal / beveled finial cap on aisle post
    create_beveled_box(
        bm, size=(post_s + 0.04, post_s + 0.04, 0.08),
        location=(x, front_y, z_floor + height + 0.04),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # 2. Back wall timber post
    create_beveled_box(
        bm, size=(post_s - 0.02, post_s - 0.02, height),
        location=(x, back_y, z_floor + height * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # 3. Lower solid wooden bulkhead (tongue-and-groove planks + rails)
    lower_h = 1.15
    # Bottom runner / baseboard
    create_beveled_box(
        bm, size=(0.11, span, 0.09),
        location=(x, mid_y, z_floor + 0.045),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # Solid wooden plank bulkhead
    create_beveled_box(
        bm, size=(0.08, span, lower_h - 0.09),
        location=(x, mid_y, z_floor + 0.09 + (lower_h - 0.09) * 0.5),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.008)
    # Middle cap rail / sill
    create_beveled_box(
        bm, size=(0.13, span, 0.08),
        location=(x, mid_y, z_floor + lower_h + 0.04),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.010)

    # 4. Upper horse-stall safety grille (iron bars)
    top_rail_h = 0.07
    create_beveled_box(
        bm, size=(0.12, span, top_rail_h),
        location=(x, mid_y, z_floor + height - top_rail_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

    bar_bot_z = z_floor + lower_h + 0.08
    bar_top_z = z_floor + height - top_rail_h
    bar_h = bar_top_z - bar_bot_z
    bar_cz = (bar_bot_z + bar_top_z) * 0.5

    n_bars = max(3, int(span / 0.15))
    bar_step = span / (n_bars + 1)
    bar_start_y = back_y - post_s * 0.5 - bar_step
    for b_idx in range(n_bars):
        by = bar_start_y - b_idx * bar_step
        create_beveled_box(
            bm, size=(0.026, 0.026, bar_h),
            location=(x, by, bar_cz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.003)


def _furnish_stable_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                         rng, density: float):
    """Working stable barn: open stall rows, manger troughs and hay storage.

    Strictly no domestic furniture (beds, tables, rugs) and no burlap sacks: stall
    dividers feature solid timber bulkheads and upper iron bars, manger troughs
    have real hollow interior volume heaped with golden straw thatch, tied hay
    bales and scattered hay piles dress the stalls and feed storage. The central
    carriageway (front door axis) is kept clear for horses and carts.
    """
    rx0, rx1, ry0, ry1 = rm.bounds
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5
    # Never a rug or a potted plant in a working stable.
    tracker.no_rugs = True
    tracker.rug_count = 1

    # Stall row along the north wall. Each stall is ~2.2 m wide with an
    # authentic equestrian divider; the middle stays open as the carriageway.
    n_stalls = max(2, min(5, int((rx1 - rx0) / 2.3)))
    stall_w = (rx1 - rx0 - 0.6) / n_stalls
    div_h, div_d = 1.85, 2.30
    for i in range(n_stalls + 1):
        dx = rx0 + 0.30 + i * stall_w
        dz = ry1 - 0.35 - div_d * 0.5
        if tracker.is_free(dx - 0.12, dx + 0.12, dz - div_d * 0.5, dz + div_d * 0.5):
            tracker.occupy(dx - 0.12, dx + 0.12, dz - div_d * 0.5, dz + div_d * 0.5)
            _build_stall_divider(bm, dx, ry1 - 0.35, div_d, z_floor, height=div_h)

    # One hay bale + manger trough + small hay piles per stall at the back wall.
    for i in range(n_stalls):
        sx = rx0 + 0.30 + (i + 0.5) * stall_w
        # Manger trough against the back wall (open hollow volume full of straw).
        tx, ty = sx, ry1 - 0.55
        if tracker.is_free(tx - 0.55, tx + 0.55, ty - 0.30, ty + 0.30):
            tracker.occupy(tx - 0.55, tx + 0.55, ty - 0.30, ty + 0.30)
            build_prop(bm, 'TROUGH', tx, ty, z_floor, 0.0)

        # Hay bale beside the trough (replaces old sacks).
        hx, hy = sx + min(0.65, stall_w * 0.22), ry1 - 1.25
        if tracker.is_free(hx - 0.30, hx + 0.30, hy - 0.30, hy + 0.30):
            tracker.occupy(hx - 0.30, hx + 0.30, hy - 0.30, hy + 0.30)
            build_prop(bm, 'HAY_BALE', hx, hy, z_floor, rng.random() * 0.40)

        # Small piles of loose straw on the stall floor.
        px1 = sx - min(0.35, stall_w * 0.20)
        py1 = ry1 - 1.20
        if tracker.is_free(px1 - 0.25, px1 + 0.25, py1 - 0.25, py1 + 0.25):
            tracker.occupy(px1 - 0.25, px1 + 0.25, py1 - 0.25, py1 + 0.25)
            build_prop(bm, 'HAY_PILE', px1, py1, z_floor, rng.random() * 6.28)

        px2 = sx + min(0.25, stall_w * 0.15)
        py2 = ry1 - 1.95
        if tracker.is_free(px2 - 0.25, px2 + 0.25, py2 - 0.25, py2 + 0.25):
            tracker.occupy(px2 - 0.25, px2 + 0.25, py2 - 0.25, py2 + 0.25)
            build_prop(bm, 'HAY_PILE', px2, py2, z_floor, rng.random() * 6.28)

    # Feed storage down the south side: crates, barrels and hay bales (STRICTLY no sacks).
    n_store = max(2, min(4, int((rx1 - rx0) / 2.8)))
    for i in range(n_store):
        px = rx0 + 0.70 + i * ((rx1 - rx0 - 1.40) / max(1, n_store - 1) if n_store > 1 else 0.0)
        py = ry0 + 0.70
        if not tracker.is_free(px - 0.45, px + 0.45, py - 0.45, py + 0.45):
            continue
        tracker.occupy(px - 0.45, px + 0.45, py - 0.45, py + 0.45)
        pick = rng.random()
        if pick < 0.35:
            build_prop(bm, 'CRATE', px, py, z_floor, 0.0)
            build_prop(bm, 'HAY_BALE', px + 0.05, py + 0.05, z_floor + 0.58, 0.2)
        elif pick < 0.65:
            build_prop(bm, 'BARREL', px, py, z_floor, 0.0)
            build_prop(bm, 'HAY_PILE', px - 0.30, py + 0.25, z_floor, rng.random() * 6.28)
        else:
            build_prop(bm, 'HAY_BALE', px, py, z_floor, rng.random() * 0.5)
            build_prop(bm, 'HAY_PILE', px - 0.32, py + 0.18, z_floor, rng.random() * 6.28)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_corridor(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """Furnishes a stair landing / corridor: runner rug, bench or chest, lantern. STRICTLY no bed!"""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Hallway runner rugs (kept off the stair opening, staggered, slight yaw)
    rug_choice = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    is_vertical = rd >= rw
    if is_vertical:
        rug_w = min(2.40, max(1.20, rw * 0.75))
        rug_w = min(rug_w, max(0.9, rw - 0.25))
        if rd >= 5.5:
            # Place multiple runner rugs along the long corridor
            half_l = min(4.50, max(2.20, rd * 0.38))
            _lay_rug(bm, tracker, rm, rng, rug_choice, rcx, rcy - rd * 0.22, z_floor,
                     rug_w, half_l, yaw_max=0.05)
            sub_choice = 'RUG_CRIMSON' if rug_choice != 'RUG_CRIMSON' else 'RUG_SAPPHIRE'
            _lay_rug(bm, tracker, rm, rng, sub_choice, rcx, rcy + rd * 0.22, z_floor,
                     rug_w, half_l, yaw_max=0.05, allow_overlap=False)
        else:
            rug_l = min(8.00, max(2.60, rd * 0.80))
            rug_l = min(rug_l, max(1.4, rd - 0.30))
            _lay_rug(bm, tracker, rm, rng, rug_choice, rcx, rcy, z_floor, rug_w, rug_l,
                     yaw_max=0.05)
    else:
        rug_l = min(2.40, max(1.20, rd * 0.75))
        rug_l = min(rug_l, max(0.9, rd - 0.25))
        if rw >= 5.5:
            half_w = min(4.50, max(2.20, rw * 0.38))
            _lay_rug(bm, tracker, rm, rng, rug_choice, rcx - rw * 0.22, rcy, z_floor,
                     half_w, rug_l, yaw_max=0.05)
            sub_choice = 'RUG_CRIMSON' if rug_choice != 'RUG_CRIMSON' else 'RUG_SAPPHIRE'
            _lay_rug(bm, tracker, rm, rng, sub_choice, rcx + rw * 0.22, rcy, z_floor,
                     half_w, rug_l, yaw_max=0.05, allow_overlap=False)
        else:
            rug_w = min(8.00, max(2.60, rw * 0.80))
            rug_w = min(rug_w, max(1.4, rw - 0.30))
            _lay_rug(bm, tracker, rm, rng, rug_choice, rcx, rcy, z_floor, rug_w, rug_l,
                     yaw_max=0.05)

    # 2. Bench or chest along clear wall
    _try_place_wall_prop(bm, 'BENCH', 1.40, 0.45, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'WEST', 'EAST'), length=1.40)

    # 2b. Large landings double as sitting nooks so big upper halls never
    # read empty: table + stools at the freest point, plus a shelf.
    if rw * rd >= 20.0 and density >= 0.4:
        _spot = _freest_spot(tracker, rng, step=0.50)
        if _spot is not None:
            _place_nook_set(bm, tracker, _spot[0], _spot[1], z_floor, rng)
        _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('NORTH', 'WEST', 'EAST', 'SOUTH'))

    # 3. Ceiling chain lantern
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_barracks_dorm(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                           rng, density: float):
    """Furnishes a military dormitory: stacked bunk beds with footlockers,
    a weapon rack, and a single austere runner rug. No double beds."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Bunk beds along the long wall, each with a 2 m walkway gap along the
    # wall so the row never reads as solid or blocks the aisle. Footlockers
    # are placed against a clear wall instead of at the bunk's foot (where
    # they used to stand in the middle of the room).
    narrow = min(rw, rd) < 4.2
    if narrow:
        only_wall = 'WEST' if rw <= rd else 'SOUTH'
    else:
        only_wall = None
    num_bunks = max(1, min(4, int(rw * rd / 14.0)))
    for _ in range(num_bunks):
        binfo = _try_place_bunk(bm, tracker, z_floor, length=2.0, width=1.1,
                                only_wall=only_wall, wall_gap=2.0)
        if binfo is None:
            continue

    # 1b. In a genuinely roomy dorm, add a second rank on the facing wall -
    # but ONLY when the room is wide enough to keep a full 2 m aisle between
    # the two rows (each bunk reaches 2 m into the room).
    if (not narrow and min(rw, rd) >= 6.0 and (rw * rd) >= 34.0):
        for _ in range(2):
            binfo = _try_place_bunk(bm, tracker, z_floor, length=2.0, width=1.1,
                                    wall_gap=2.0)
            if binfo is None:
                break

    # Footlockers along a free wall, never in the walkway.
    _try_place_wall_prop(bm, 'CHEST', 0.95, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'NORTH', 'EAST', 'WEST'))

    # 2. Weapon rack along remaining free wall
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'EAST', 'SOUTH'))

    # 3. Single austere dorm runner rug along the walking aisle (kept clear of
    # walls/other rugs; skipped entirely if the dorm is too tight).
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor,
             min(1.60, rw * 0.40), min(3.20, rd * 0.55), yaw_max=0.06,
             allow_overlap=False)

    # 4. Ceiling lantern
    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_mess_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Furnishes a military mess / refectory: long communal tables with bench
    seating both sides, tableware, a supply barrel and one runner rug."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Big central refectory table with chairs around it (plus a second
    # table with benches in wide halls).
    table_spots = [(rcx, rcy, True)]
    if rw >= 5.0:
        table_spots.append((rcx + rw * 0.24 if rw >= 6.5 else rcx - rw * 0.24, rcy, False))
    for tx, ty, is_main in table_spots:
        if is_main:
            tw, td = 2.60, 1.15
            need = 0.55
        else:
            tw, td = 2.00, 1.00
            need = 0.55
        if not tracker.is_free(tx - tw * 0.5 - 0.30, tx + tw * 0.5 + 0.30,
                               ty - td * 0.5 - need, ty + td * 0.5 + need):
            continue
        build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, 0.0, length=tw, width=td)
        build_prop(bm, 'SCATTER_TABLEWARE', tx - 0.45, ty, z_floor + 0.76, 0.0)
        build_prop(bm, 'SCATTER_TABLEWARE', tx + 0.45, ty, z_floor + 0.76, 0.0)
        if is_main:
            # Chairs all around the big table, facing inward.
            for ci in range(6):
                ca = ci * (math.pi * 2.0 / 6.0)
                chx = tx + (tw * 0.5 + 0.32) * math.cos(ca)
                chy = ty + (td * 0.5 + 0.32) * math.sin(ca)
                _try_place_chair(bm, tracker, chx, chy, ca - math.pi * 0.5, z_floor)
        else:
            for sgn in (-1.0, 1.0):
                bx, by = tx, ty + sgn * (td * 0.5 + 0.32)
                if tracker.is_free(bx - tw * 0.45, bx + tw * 0.45, by - 0.25, by + 0.25):
                    tracker.occupy(bx - tw * 0.45, bx + tw * 0.45, by - 0.25, by + 0.25)
                    build_prop(bm, 'BENCH', bx, by, z_floor, 0.0, length=min(tw - 0.2, 2.0))
        tracker.occupy(tx - tw * 0.5 - 0.30, tx + tw * 0.5 + 0.30,
                       ty - td * 0.5 - need, ty + td * 0.5 + need)

    # 2. Supply barrel in a free corner
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                build_prop(bm, 'BARREL', cx, cy, z_floor, 0.0)
                break

    # 3. Big rug under the tables plus a runner down the serving aisle
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor,
             min(4.20, rw * 0.70), min(4.60, rd * 0.70), yaw_max=0.08)
    _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', rcx, rm.bounds[2] + rd * 0.18, z_floor,
             min(1.60, rw * 0.35), min(3.60, rd * 0.50), yaw_max=0.06,
             allow_overlap=False)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_archery_range(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                           rng, density: float, role: str = 'RANGE'):
    """Purpose-fit archery interiors. RANGE: butt at the far end with a clear
    shooting lane, rack and marker. FLETCHER_WORKSHOP: workbench, arrow
    barrels, shelf and bow rack."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    if role == 'FLETCHER_WORKSHOP':
        # Workbench along a wall with stool, arrow-shaft barrels, shelf, rack
        _d = _try_place_wall_prop(bm, 'DESK', 1.60, 0.68, tracker, z_floor,
                                  candidate_walls=('NORTH', 'WEST', 'EAST'))
        if _d:
            _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))
        _try_place_wall_prop(bm, 'STOOL', 0.45, 0.45, tracker, z_floor,
                             candidate_walls=('SOUTH', 'EAST', 'WEST'))
        for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
            for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
                if tracker.is_free(cx - 0.28, cx + 0.28, cy - 0.28, cy + 0.28):
                    tracker.occupy(cx - 0.28, cx + 0.28, cy - 0.28, cy + 0.28)
                    build_prop(bm, 'BARREL', cx, cy, z_floor, 0.0)
                    break
        _try_place_wall_prop(bm, 'SHELF', 1.30, 0.40, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'SOUTH'))
        _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('SOUTH', 'EAST', 'WEST'))
        rw = rm.bounds[1] - rm.bounds[0]
        rd = rm.bounds[3] - rm.bounds[2]
        _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', rcx, rcy, z_floor,
                 min(2.20, rw * 0.50), min(3.00, rd * 0.50), yaw_max=0.10)
        build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)
        return

    # RANGE: straw butt against the far (north) wall facing down the lane.
    # Keep the whole lane (butt + arrow flight + shooting line) walkway-clear.
    lane_x = rcx
    butt_y = rm.bounds[3] - 0.95
    if tracker.is_free(lane_x - 0.55, lane_x + 0.55, butt_y - 0.60, butt_y + 0.60):
        tracker.occupy(lane_x - 0.70, lane_x + 0.70, rm.bounds[2], rm.bounds[3] - 0.30)
        build_prop(bm, 'ARCHERY_TARGET', lane_x, butt_y, z_floor, 0.0)
        # Shooting-line marker rug at the near end of the lane
        _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', lane_x, rm.bounds[2] + 1.05, z_floor,
                 1.30, 1.30, yaw_max=0.05)
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('SOUTH', 'EAST', 'WEST'))
    for cx in (rm.bounds[0] + 0.40, rm.bounds[1] - 0.40):
        for cy in (rm.bounds[2] + 0.40, rm.bounds[3] - 0.40):
            if tracker.is_free(cx - 0.28, cx + 0.28, cy - 0.28, cy + 0.28):
                tracker.occupy(cx - 0.28, cx + 0.28, cy - 0.28, cy + 0.28)
                build_prop(bm, 'BARREL', cx, cy, z_floor, 0.0)
                break
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

    # 3. Training pell pushed into a corner, clear of the drill floor and
    # doorways (never standing in the middle of the room).
    _pell_placed = False
    for _px in (rm.bounds[0] + 0.60, rm.bounds[1] - 0.60):
        if _pell_placed:
            break
        for _py in (rm.bounds[2] + 0.60, rm.bounds[3] - 0.60):
            if tracker.is_free(_px - 0.40, _px + 0.40, _py - 0.40, _py + 0.40):
                tracker.occupy(_px - 0.40, _px + 0.40, _py - 0.40, _py + 0.40)
                build_prop(bm, 'TRAINING_DUMMY', _px, _py, z_floor, 0.0)
                _pell_placed = True
                break

    # 4. Storage crates and barrels
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if tracker.is_free(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3):
                tracker.occupy(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3)
                build_prop(bm, 'CRATE', cx, cy, z_floor, 0.0)

    # 5. Single austere drill-hall runner rug
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor,
             min(1.70, rw * 0.38), min(3.40, rd * 0.52), yaw_max=0.06)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_shop(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                  rng, density: float):
    """Artisan storefront: merchant counter with a working side for the
    seller and a browsing side for customers, display shelves, crates, rug.

    The counter prefers freestanding across the rear (merchant stool and
    side table tucked behind it, rug and displays in front); small shops
    fall back to the classic wall-backed counter. Counter placement is
    stashed on the tracker for the trade dresser (jeweler scale & tray).
    """
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    tracker.shop_counter = None

    # 1. Merchant counter: freestanding across a wall with a working strip
    # behind it, else wall-backed.
    _counter_len = min(2.0, max(1.2, min(rw, rd) * 0.45))
    _placed_counter = None
    # (wall, yaw so the plank front faces the room, merchant dir into wall)
    for _wall, _yaw, _mdx, _mdy in (('NORTH', 0.0, 0.0, 1.0),
                                    ('EAST', -math.pi * 0.5, 1.0, 0.0),
                                    ('WEST', math.pi * 0.5, -1.0, 0.0),
                                    ('SOUTH', math.pi, 0.0, -1.0)):
        _run = rw if _wall in ('NORTH', 'SOUTH') else rd
        _clen = min(2.0, max(1.2, _run * 0.45))
        if _wall == 'NORTH':
            _ccx, _ccy = rcx, tracker.ry1 - 1.05 - 0.30
        elif _wall == 'SOUTH':
            _ccx, _ccy = rcx, tracker.ry0 + 1.05 + 0.30
        elif _wall == 'EAST':
            _ccx, _ccy = tracker.rx1 - 1.05 - 0.30, rcy
        else:
            _ccx, _ccy = tracker.rx0 + 1.05 + 0.30, rcy
        _hw = (_clen * 0.5 + 0.15) if _wall in ('NORTH', 'SOUTH') else 0.45
        _hd = 0.45 if _wall in ('NORTH', 'SOUTH') else (_clen * 0.5 + 0.15)
        if not tracker.is_free(_ccx - _hw, _ccx + _hw, _ccy - _hd, _ccy + _hd):
            continue
        # Merchant stool spot behind the counter.
        _stx, _sty = _ccx + _mdx * 0.72, _ccy + _mdy * 0.72
        if not tracker.is_free(_stx - 0.26, _stx + 0.26, _sty - 0.26, _sty + 0.26):
            continue
        tracker.occupy(_ccx - _hw, _ccx + _hw, _ccy - _hd, _ccy + _hd)
        build_prop(bm, 'COUNTER', _ccx, _ccy, z_floor, _yaw, length=_clen)
        tracker.occupy(_stx - 0.26, _stx + 0.26, _sty - 0.26, _sty + 0.26)
        build_prop(bm, 'STOOL', _stx, _sty, z_floor,
                   math.atan2(-_mdx, -_mdy))
        _placed_counter = {'cx': _ccx, 'cy': _ccy, 'yaw': _yaw,
                           'wall': _wall, 'freestanding': True,
                           'mdx': _mdx, 'mdy': _mdy, 'length': _clen,
                           'top_z': z_floor + 1.075}
        break
    if _placed_counter is None:
        _d_counter = _try_place_wall_prop(bm, 'COUNTER', _counter_len, 0.60, tracker, z_floor,
                                          candidate_walls=('NORTH', 'EAST', 'WEST'), length=_counter_len)
        if _d_counter:
            _placed_counter = {'cx': _d_counter[0], 'cy': _d_counter[1],
                               'yaw': _d_counter[2], 'wall': None,
                               'freestanding': False, 'mdx': 0.0, 'mdy': 0.0,
                               'length': _counter_len, 'top_z': z_floor + 1.075}
    tracker.shop_counter = _placed_counter
    if _placed_counter:
        _cc = _placed_counter
        if tracker.archetype != 'JEWELER':
            # Countertop plant (jeweler gets the gem tray instead).
            build_prop(bm, 'POTTED_PLANT_SMALL', _cc['cx'], _cc['cy'],
                       _cc['top_z'], rng.uniform(0.0, 6.28))

    # 2. Display shelves on perimeter walls
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('WEST', 'NORTH', 'SOUTH'))

    # 3. Goods crates and merchandise barrels — kept OFF the corners so the
    #    wall corners stay free for the trade display (placed next).
    _mid_y = (rm.bounds[2] + rm.bounds[3]) * 0.5
    _mid_x = (rm.bounds[0] + rm.bounds[1]) * 0.5
    for cx, cy in ((rm.bounds[0] + 0.40, _mid_y), (rm.bounds[1] - 0.40, _mid_y),
                   (_mid_x, rm.bounds[2] + 0.40), (_mid_x, rm.bounds[3] - 0.40)):
        if tracker.is_free(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25):
            tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
            prop = 'CRATE' if rng.random() < 0.6 else 'BARREL'
            build_prop(bm, prop, cx, cy, z_floor, 0.0)

    # 4. Area rug in the customer browse zone (in front of a freestanding
    # counter, else room centre; skipped in a bare industrial store).
    if not getattr(tracker, 'no_rugs', False):
        rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_FOREST'])
        rug_w = min(3.00, max(1.80, rw * 0.58))
        rug_l = min(4.20, max(2.40, rd * 0.58))
        rug_w = min(rug_w, max(1.2, rw - 0.40))
        rug_l = min(rug_l, max(1.5, rd - 0.40))
        _rug_cx, _rug_cy = rcx, rcy
        if _placed_counter and _placed_counter.get('freestanding'):
            _rug_cx = _placed_counter['cx'] - _placed_counter['mdx'] * 1.60
            _rug_cy = _placed_counter['cy'] - _placed_counter['mdy'] * 1.60
        _lay_rug(bm, tracker, rm, rng, rug_choice, _rug_cx, _rug_cy, z_floor, rug_w, rug_l)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _furnish_infirmary(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                       rng, density: float):
    """Furnishes a healer's chapel infirmary / apothecary with medical beds, desk, and potion shelves."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5

    # 1. Recovery medical bed
    _try_place_bed(bm, tracker, z_floor, length=1.95, width=1.10)

    # 2. Apothecary desk / preparation table (chair + notes)
    _d = _try_place_wall_prop(bm, 'DESK', 1.35, 0.65, tracker, z_floor,
                              candidate_walls=('EAST', 'NORTH', 'WEST'))
    if _d:
        _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))

    # 3. Medicine / herb shelves
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'SOUTH'))

    # 4. Storage chest
    _try_place_wall_prop(bm, 'CHEST', 0.85, 0.48, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    # 5. Soothing clean royal rug (generous scale)
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    rug_w = min(2.80, max(1.80, rw * 0.58))
    rug_l = min(3.80, max(2.40, rd * 0.58))
    rug_w = min(rug_w, max(1.2, rw - 0.35))
    rug_l = min(rug_l, max(1.5, rd - 0.35))
    _lay_rug(bm, tracker, rm, rng, 'RUG_SAPPHIRE', rcx, rcy, z_floor, rug_w, rug_l)

    build_prop(bm, 'CHAIN_LANTERN', rcx, rcy, z_ceil, 0.0)


def _dress_single_room(bm, rm, z_floor: float, z_ceil: float, rng,
                       density: float, style: str, ctx=None,
                       floor_has_dining: bool = False):
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
        _extras = getattr(ctx, 'extra_doorways', None) or getattr(getattr(ctx, 'props', None), 'extra_doorways', None) or []
        for ed in _extras:
            if ed.get('floor_idx', 0) == rm.floor_idx:
                sax = ed.get('axis', 'Y' if ed.get('facade') in ('LEFT', 'RIGHT') else 'X')
                if sax == 'X':
                    ed_x, ed_y = ed.get('pos', 0.0), (ry1 if ed.get('facade') == 'BACK' else ry0)
                else:
                    ed_x, ed_y = (rx0 if ed.get('facade') == 'LEFT' else rx1), ed.get('pos', 0.0)
                ed_d = {'x': ed_x, 'y': ed_y, 'axis': sax, 'w': ed.get('w', 1.8), 'is_portal': ed.get('is_portal', True)}
                if (rx0 - 0.55 <= ed_x <= rx1 + 0.55) and (ry0 - 0.55 <= ed_y <= ry1 + 0.55):
                    if ed_d not in all_doorways:
                        all_doorways.append(ed_d)

    # 2. Gather all windows bordering this room
    room_windows = []
    if ctx is not None:
        fl_windows = getattr(ctx, 'window_centers', {}).get(rm.floor_idx, {})
        for facade, wlist in fl_windows.items():
            for (wx, wy, wz) in wlist:
                if (rx0 - 0.35 <= wx <= rx1 + 0.35) and (ry0 - 0.35 <= wy <= ry1 + 0.35):
                    room_windows.append((wx, wy, facade))

    # 3. Chimney stone shaft position (supports multiple chimney flues)
    chimney_pos = getattr(ctx, 'chimney_pos', None) if ctx is not None else None
    chimney_positions = getattr(ctx, 'chimney_positions', None) if ctx is not None else None
    if not chimney_positions and chimney_pos:
        chimney_positions = [chimney_pos]
    elif not chimney_positions:
        chimney_positions = []

    # Stairwell footprint for this floor: the room's own hole, else the
    # ceiling slab's hole one storey up (the stairs rising from here). Both
    # are reserved so no prop or display ever sits inside the staircase.
    _stair_well = rm.stair_hole
    if _stair_well is None and ctx is not None:
        _stair_well = (getattr(ctx, 'floor_stair_holes', None) or {}).get(
            rm.floor_idx + 1)
    tracker = RoomOccupancyTracker(
        rx0 + inset, rx1 - inset, ry0 + inset, ry1 - inset,
        stair_hole=_stair_well,
        doorways=all_doorways,
        windows=room_windows,
        chimney=chimney_positions
    )
    tracker.stair_hole = _stair_well
    tracker.rng = rng
    tracker.archetype = getattr(ctx, 'effective_archetype', 'NONE') if ctx is not None else 'NONE'
    if getattr(ctx, 'effective_archetype', 'NONE') == 'BAKERY' and ctx is not None:
        # Hearth-oven masonry keep-out: the ground-floor bakehouse reserves
        # the oven body + work apron, and upper storeys reserve the flue
        # shaft rising through them, so props never intersect the masonry.
        try:
            from .bakery import bakery_oven_rect, _pick_oven_y
            _hx = float(getattr(ctx, 'hx', 0.0))
            _hy = float(getattr(ctx, 'hy', 0.0))
            _wt = float(getattr(ctx, 'wall_t', 0.30))
            _oy = _pick_oven_y(ctx, _hy, _wt, 0.975)
            if rm.floor_idx == 0 and rm.role == 'BAKEHOUSE':
                tracker.occupy(*bakery_oven_rect(_hx, _wt, _oy))
            elif rm.floor_idx > 0:
                _fx = (_hx - _wt) - 1.35 * 0.5
                tracker.occupy(_fx - 0.50, _fx + 0.50, _oy - 0.50, _oy + 0.50)
        except Exception:
            pass
    tracker.bare_stockpile = bool(getattr(ctx, 'bare_stockpile', False)) if ctx is not None else False
    tracker.is_quarry = (tracker.archetype == 'QUARRY')
    tracker.industrial = getattr(ctx, 'industrial', False) or (tracker.archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY'))
    # The treadwheel sawmill stands near the middle of a lumbermill hall and is
    # built as kit geometry (not tracked), so reserve its working area here to
    # keep storage piles and shelves from overlapping the machinery. The box
    # is grade-aware (wheel size, twin benches, gear all grow by tier) and
    # stashed on ctx by the mill kit; fall back to the old fixed box only if
    # the kit never ran.
    # Yard stock (pallets, log ranks, pots, shelter posts) is likewise kit
    # geometry: reserve every recorded footprint on the ground floor so
    # indoor piles never land on yard stock.
    if ctx is not None:
        for _yb in getattr(ctx, 'yard_keepouts', None) or ():
            if rm.floor_idx == 0:
                tracker.occupy(_yb[0], _yb[1], _yb[2], _yb[3])
    if tracker.archetype == 'LUMBERMILL' and rm.floor_idx == 0:
        _mill_box = None
        if ctx is not None:
            _mill_box = getattr(ctx, 'mill_keepout', None)
        if _mill_box is None:
            _mill_box = (-2.8, 3.4, -2.8, 3.8)
        tracker.occupy(_mill_box[0], _mill_box[1], _mill_box[2], _mill_box[3])
    # Back-of-house rooms in an industrial fit-out stay bare (no rug/plant).
    # Open-air stockpiles stay entirely bare: every room is product only.
    _bare = ((getattr(ctx, 'no_utility_rugs', False)
             and rm.role in _UTILITY_ROLES) or tracker.is_quarry)
    if getattr(tracker, 'bare_stockpile', False):
        _bare = True
    tracker.no_rugs = _bare

    role = rm.role
    _occ_before = len(tracker.occupied_boxes)
    try:
        if tracker.bare_stockpile and role in ('STORE', 'WORKSHOP', 'SMITHY', 'STORAGE',
                                               'CELLAR', 'PANTRY', 'STONE_STORE', 'OFFICE',
                                               'CORRIDOR', 'STAIR_LANDING'):
            _furnish_industrial_bay(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('STAIR_LANDING', 'CORRIDOR'):
            _furnish_corridor(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role == 'STONE_STORE' or (tracker.is_quarry and role in ('WORKSHOP', 'STORAGE', 'STORE', 'SMITHY')):
            _furnish_stone_store(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif getattr(tracker, 'industrial', False) and role in ('WORKSHOP', 'SMITHY', 'STORAGE', 'STORE', 'CELLAR', 'PANTRY'):
            _furnish_industrial_bay(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('TAVERN_TAPROOM', 'COMMON'):
            _furnish_tavern_taproom(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('THRONE_ROOM',):
            _furnish_throne_room(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('GREAT_HALL', 'COUNCIL_CHAMBER'):
            _furnish_great_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('BANQUET_HALL',):
            _furnish_banquet_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('ENTRANCE_HALL',):
            _furnish_entrance_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('MAYOR_OFFICE', 'OFFICE'):
            _furnish_office(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('KITCHEN', 'TENEMENT_KITCHEN'):
            _furnish_kitchen(bm, rm, tracker, z_floor, z_ceil, rng, density,
                             chimney_pos=chimney_positions, floor_has_dining=floor_has_dining)
        elif role in ('MASTER_BED', 'OFFICER_QUARTERS'):
            _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=True)
        elif role in ('MESS_HALL',):
            _furnish_mess_hall(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('RANGE', 'FLETCHER_WORKSHOP'):
            _furnish_archery_range(bm, rm, tracker, z_floor, z_ceil, rng, density, role=role)
        elif role in ('BEDROOM', 'GUEST_ROOM', 'LODGE', 'TENEMENT_BEDROOM'):
            _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=False)
        elif role in ('BARRACKS_DORM', 'OFFICER_QUARTERS'):
            _furnish_barracks_dorm(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('ARMORY', 'DRILL_HALL'):
            _furnish_armory(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('STORE',):
            _furnish_shop(bm, rm, tracker, z_floor, z_ceil, rng, density)
            _dress_shop_for_trade(bm, tracker, z_floor, rng, tracker.archetype)
        elif role in ('INFIRMARY', 'APOTHECARY', 'HEALER_QUARTERS'):
            _furnish_infirmary(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('STUDY', 'LIBRARY', 'VESTRY'):
            _furnish_study_library(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('BAKEHOUSE',):
            _furnish_bakehouse(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('BREWHOUSE',):
            _furnish_brewhouse(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('BUTCHERY',):
            _furnish_butchery(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('TAILOR_ATELIER',):
            _furnish_tailor_atelier(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('GOLDSMITH',):
            _furnish_goldsmith(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('JOINERY',):
            _furnish_joinery(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('FISHERY',):
            _furnish_fishery(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('WORKSHOP',):
            _furnish_workshop(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('SMITHY',):
            _furnish_smithy(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('CHAPEL_HALL',):
            _furnish_chapel(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('STORAGE', 'CELLAR', 'PANTRY'):
            _furnish_storage(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('STABLE_HALL',):
            _furnish_stable_hall(bm, rm, tracker, z_floor, z_ceil, rng, density)
        else:  # HOUSE_HALL, DINING, PARLOR, default
            _furnish_house_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
    except Exception:
        if _STRICT_FURNISH:
            raise

    # Minimum-dressing guarantee: a living room the recipe left almost empty
    # (awkward stairwell, door-heavy plan) still gets a sitting nook. Bare
    # industrial fit-outs, walkways and stables are exempt by design.
    if (not _bare and role not in ('STAIR_LANDING', 'CORRIDOR', 'STABLE_HALL')
            and len(tracker.occupied_boxes) - _occ_before < 3):
        try:
            _ensure_minimum_dressing(bm, tracker, rm, z_floor, rng)
        except Exception:
            if _STRICT_FURNISH:
                raise

    # Every room gets at least one rug, except back-of-house rooms in an
    # industrial fit-out (warehouses/lumbermills stay bare).
    if not _bare and getattr(tracker, 'rug_count', 0) == 0:
        rw = (rx1 - rx0) - inset * 2.0
        rd = (ry1 - ry0) - inset * 2.0
        if rw >= 1.0 and rd >= 1.0:
            rug_key = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
            _lay_rug(bm, tracker, rm, rng, rug_key, (rx0 + rx1) * 0.5, (ry0 + ry1) * 0.5,
                     z_floor, min(2.40, max(1.10, rw * 0.55)), min(3.20, max(1.40, rd * 0.55)))

    # Most rooms get a potted planter so the new plant props are actually seen
    # (skipped in bare industrial utility rooms, and never in a working stable).
    rw = rx1 - rx0
    rd = ry1 - ry0
    if role != 'STABLE_HALL' and not _bare and min(rw, rd) >= 2.6 and rng.random() < 0.7:
        _try_place_plant(bm, tracker, z_floor, rng, large=True)


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

    # Resolve the interior program once: industrial fits keep back-of-house
    # rooms (and their rugs) bare unless the user explicitly asks for them.
    try:
        from ..interior import resolve_interior_program
        _program = resolve_interior_program(
            getattr(ctx, 'effective_archetype', 'NONE'),
            getattr(props, 'interior_program', 'AUTO'))
    except Exception:
        _program = getattr(props, 'interior_program', 'AUTO')
    ctx.no_utility_rugs = (
        _program == 'INDUSTRIAL'
        and not bool(getattr(props, 'rug_in_utility_rooms', False)))
    ctx.industrial = (_program == 'INDUSTRIAL')
    # Tier-1 open-air warehouse stockpiles are product-only yards (piles,
    # crates, barrels, awnings): no shelving, chests or hanging lanterns.
    ctx.bare_stockpile = (
        getattr(ctx, 'effective_archetype', '') == 'WAREHOUSE'
        and getattr(props, 'material_tier', 'TIER_1') == 'TIER_1')
    seed = int(getattr(props, 'seed', 1)) + 917
    style = getattr(props, 'furnishing_style', 'AUTO')

    floor_rooms_dict = getattr(ctx, 'floor_rooms', {})

    for fl in range(ctx.num_floors):
        # Match the lowered T1 ground slab (floors.py): quarry / lumbermill
        # open-timber ground floors sit 3 cm lower, so props rest ON the slab
        # instead of floating above it.
        _low_t1 = (fl == 0
                   and getattr(props, 'material_tier', 'TIER_1') == 'TIER_1'
                   and getattr(ctx, 'effective_archetype', '') in ('LUMBERMILL', 'QUARRY'))
        _lift = 0.02 if _low_t1 else 0.05
        if fl == 0 and getattr(ctx, 'bare_stockpile', False):
            # Open-air stockpile: no floor slab, props stand on the dirt.
            _lift = 0.0
        z_floor = ctx.found_h + fl * ctx.floor_h + _lift
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

        # A room on this floor already contains the dining/social set, so the
        # kitchen must not duplicate it. Shared across the whole storey.
        _dining_roles = {'HOUSE_HALL', 'DINING', 'GREAT_HALL', 'BANQUET_HALL', 'TAVERN_TAPROOM',
                         'CHAPEL_HALL', 'MESS_HALL', 'COUNCIL_CHAMBER', 'THRONE_ROOM'}
        floor_has_dining = any(getattr(rm, 'role', None) in _dining_roles for rm in rooms)

        # Designate largest ground-floor room as THRONE_ROOM if requested
        if fl == 0 and (bool(getattr(props, 'has_throne_room', False)) or _program == 'PALACE') and rooms:
            largest_rm = max(rooms, key=lambda r: (r.bounds[1] - r.bounds[0]) * (r.bounds[3] - r.bounds[2]))
            largest_rm.role = 'THRONE_ROOM'
            floor_has_dining = True

        for rm in rooms:
            # Skip rooms that are too tiny to furnish safely
            rw = rm.bounds[1] - rm.bounds[0]
            rd = rm.bounds[3] - rm.bounds[2]
            if rw < 1.3 or rd < 1.3:
                continue
            try:
                _dress_single_room(bm, rm, z_floor, z_ceil, rng, density, style, ctx=ctx,
                                   floor_has_dining=floor_has_dining)
            except Exception:
                continue
