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
                 chimney: Optional[Tuple[float, float]] = None,
                 floor_void: Optional[Tuple[float, float, float, float]] = None,
                 clear_zones: Optional[List[Tuple[float, float, float, float]]] = None):
        self.rx0 = rx0
        self.rx1 = rx1
        self.ry0 = ry0
        self.ry1 = ry1
        self.doorways = doorways or []
        self.occupied_boxes: List[Tuple[float, float, float, float]] = []
        self.floor_void = floor_void
        if floor_void is not None:
            vx0, vx1, vy0, vy1 = floor_void
            self.occupied_boxes.append((vx0, vx1, vy0, vy1))
        # Aprons in front of annex walk-throughs (hall side): nothing may stand
        # there, so the way into the annex stays open on every storey.
        for _cz in (clear_zones or []):
            self.occupied_boxes.append(tuple(_cz))

        # Reserve stairwell clearance (flight below plus its approach so props
        # never block the stairs, not just the bare opening). Kept snug on
        # purpose: the upper guardrail already protects the opening edge, and
        # oversized pads used to starve whole rooms of furniture.
        self.stair_box = None
        self.stair_hole_rect = None
        self.stair_is_ceiling = False
        if stair_hole is not None:
            sx0, sx1, sy0, sy1 = stair_hole
            self.stair_hole_rect = (sx0, sx1, sy0, sy1)
            # Snug reservation: the flight opening plus a small working margin.
            # Oversized pads used to swallow whole small rooms (e.g. the 7.5 m
            # fishery cottage), leaving no floor for a bed or kitchen.
            pad_land = 0.45
            pad_side = 0.35
            self.stair_box = (sx0 - pad_side, sx1 + pad_side,
                              sy0 - pad_land, sy1 + pad_land)
            self.occupied_boxes.append(self.stair_box)

            # Stairs in this generator run along Y, so the step-on/off approach
            # belongs at the two Y ends (2x2 m), never on the sides. Picking the
            # sides for a wide switchback well starved the rest of the room.
            self.stair_approach = []
            _axc = (sx0 + sx1) * 0.5
            for _aye in (sy0 - 0.95, sy1 + 0.95):
                _ab = (_axc - 1.0, _axc + 1.0, _aye - 1.0, _aye + 1.0)
                self.stair_approach.append(_ab)
                self.occupied_boxes.append(_ab)

        # 2. Reserve walking corridors around all doorways (interior, front, wing, annex).
        # A stair-landing foot is NOT a doorway corridor: it reserves exactly
        # its 2x2 m approach square so it can never starve a room like a portal
        # corridor (3.2 m deep) would.
        # Only doorways that are explicitly flagged as portals reserve the deep
        # 3.2 m connector corridor. A wide interior partition door is still just
        # a door - reserving 3.2 m for it used to starve small chambers of every
        # single prop, which is why the narrow rooms came out empty.
        if doorways:
            for d in doorways:
                dcx = d.get('x', (rx0 + rx1) * 0.5)
                dcy = d.get('y', (ry0 + ry1) * 0.5)
                if bool(d.get('is_stair_landing', False)):
                    self.occupied_boxes.append((dcx - 1.0, dcx + 1.0,
                                                dcy - 1.0, dcy + 1.0))
                    continue
                axis = d.get('axis', 'X')
                dw = d.get('w', 0.95)
                is_p = bool(d.get('is_portal', False))
                clr = 2.40 if is_p else 1.80  # clear walking corridor depth inside room
                w_margin = (dw * 0.5 + 0.55) if is_p else (dw * 0.5 + 0.30)
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

    def is_near_door(self, x: float, y: float, radius: float = 1.30) -> bool:
        """Returns True if (x, y) is within clearance distance of any doorway."""
        for d in self.doorways:
            dcx = d.get('x', (self.rx0 + self.rx1) * 0.5)
            dcy = d.get('y', (self.ry0 + self.ry1) * 0.5)
            if bool(d.get('is_stair_landing', False)):
                # Stair foot: only the 2x2 approach itself counts, so wall
                # props can still use the nearby walls instead of being pushed
                # into the middle of the room.
                if math.hypot(x - dcx, y - dcy) < max(radius, 1.25):
                    return True
                continue
            dw = d.get('w', 0.95)
            is_p = bool(d.get('is_portal', False))
            axis = d.get('axis', 'X')
            wm = dw * 0.5 + 0.35
            depth_clr = 1.60 if is_p else 1.20
            if axis == 'X':
                if (dcx - wm <= x <= dcx + wm) and (dcy - depth_clr <= y <= dcy + depth_clr):
                    return True
            else:
                if (dcx - depth_clr <= x <= dcx + depth_clr) and (dcy - wm <= y <= dcy + wm):
                    return True
            r = max(radius, 1.60 if is_p else (dw * 0.5 + 0.35))
            if math.hypot(x - dcx, y - dcy) < r:
                return True
        return False

    def is_free(self, bx0: float, bx1: float, by0: float, by1: float, margin: float = 0.03,
                ignore_chimney: bool = False, check_windows: bool = False,
                ignore_stair: bool = False, bounds_slack: float = 0.0) -> bool:
        """Returns True if the box [bx0, bx1] x [by0, by1] is inside the room and unblocked.

        ``ignore_stair`` skips the reserved stairwell box: used only where the
        stair is a ceiling opening (solid floor beneath), so the genuinely
        walkable space under the flight can still take furniture.
        ``bounds_slack`` relaxes only the outer room containment (for pieces
        anchored flush to the real wall, past the plaster safety inset) —
        collision against stairs, doors and other props stays strict."""
        eps = 0.02 + bounds_slack
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
            if ignore_stair and self.stair_box == (ox0, ox1, oy0, oy1):
                continue
            if not (bx1 + margin < ox0 or bx0 - margin > ox1 or by1 + margin < oy0 or by0 - margin > oy1):
                return False
        return True

    def occupy(self, bx0: float, bx1: float, by0: float, by1: float):
        """Marks a rectangular area as occupied."""
        self.occupied_boxes.append((bx0, bx1, by0, by1))


def _jit(rng, amount: float) -> float:
    """Signed random offset in metres (0 when no RNG is available)."""
    return rng.uniform(-amount, amount) if rng is not None else 0.0


# Real footprint depth (metres, measured across the wall) of the props that are
# pushed flush against a wall. Without these the placement used a guessed depth
# and a piece could end up buried in the wall it stands against.
_WALL_PROP_DEPTH = {
    'INDOOR_TABLE': 1.15,
    'ROUND_TABLE': 0.78,
    'BOOKSHELF': 0.36,
    'BOOKSHELF_NEAT': 0.36,
    'SHELF': 0.36,
    'CHEST': 0.68,
    'BENCH': 0.62,
    'DESK': 0.82,
    'COUNTER': 0.72,
    'WARDROBE': 0.70,
    'HEARTH': 0.70,
    'ARMOUR': 0.55,
    'WEAPON_RACK': 0.45,
    'POTTED_PLANT_LARGE': 0.50,
}


def _wall_prop_footprint(key: str, width: float, depth: float, params: Optional[dict] = None):
    """Return the *real* built footprint (along-wall width, across-wall depth).

    ``_try_place_wall_prop`` used to reserve space with the caller's nominal
    size while ``build_prop`` actually builds the prop at its registry default
    size.  A bookshelf therefore occupied 1.25 m of collision space but built
    1.65 m wide, so neighbouring pieces (desk, chest) interpenetrated and the
    overhang poked through side walls.  Resolve the same defaults ``build_prop``
    will use so collision boxes always contain the real geometry.
    """
    try:
        from .prop_registry import PROP_REGISTRY
        spec = PROP_REGISTRY.get(key)
    except Exception:
        spec = None
    if spec is not None:
        merged = dict(spec.defaults)
        merged.update(params or {})
        if 'length' in merged:
            width = max(width, float(merged['length']))
        elif 'width' in merged:
            width = max(width, float(merged['width']))
        if 'depth' in merged:
            depth = max(depth, float(merged['depth']))
        elif 'length' in merged and 'width' in merged:
            # Piles / tables use ``width`` as the across-wall dimension.
            depth = max(depth, float(merged['width']))
    real_depth = _WALL_PROP_DEPTH.get(key)
    if real_depth is not None:
        depth = max(depth, real_depth)
    return width, depth


def _try_place_chair(bm, tracker: RoomOccupancyTracker, cx: float, cy: float,
                     yaw: float, z_floor: float, seat_h: float = 0.62,
                     half: float = 0.35) -> bool:
    """Places one chair only when its footprint is inside the room and clear
    of stairs, doorways, windows and other props. Chairs placed without this
    check used to land inside stairwells and block the climb."""
    if tracker.is_free(cx - half, cx + half, cy - half, cy + half):
        tracker.occupy(cx - half, cx + half, cy - half, cy + half)
        build_prop(bm, 'CHAIR', cx, cy, z_floor, yaw, seat_h=seat_h)
        return True
    return False


def _place_ceiling_light(bm, tracker: Optional[RoomOccupancyTracker], rcx: float, rcy: float,
                         z_ceil: float, prop_name: str = 'CHAIN_LANTERN', **kwargs):
    """Places a ceiling-mounted light fixture safely clear of stairs.
    
    Checks all stair holes across all floors, flight boxes, floor voids, and stair approaches.
    If the requested (rcx, rcy) falls within or close to stairs (where a player climbing stairs
    would bump their head), it nudges the light into the clear walkable room area away from the
    staircase, or omits it if the space is an open stair shaft without clearance.
    """
    if tracker is None:
        return

    lx, ly = rcx, rcy

    def _conflicts_with_stairs(x, y, margin=1.10):
        all_holes = list(getattr(tracker, 'all_stair_holes', []) or [])
        sh = getattr(tracker, 'stair_hole', None) or getattr(tracker, 'stair_hole_rect', None)
        if sh is not None and sh not in all_holes:
            all_holes.append(sh)
        sb = getattr(tracker, 'stair_box', None)
        if sb is not None and sb not in all_holes:
            all_holes.append(sb)

        ctx = getattr(tracker, 'ctx', None)
        if ctx is not None:
            fsh = getattr(ctx, 'floor_stair_holes', {}) or {}
            for h in fsh.values():
                if h is not None and h not in all_holes:
                    all_holes.append(h)
            fsb = getattr(ctx, 'full_stair_box', None)
            if fsb is not None and fsb not in all_holes:
                all_holes.append(fsb)

        for (sx0, sx1, sy0, sy1) in all_holes:
            if (sx0 - margin <= x <= sx1 + margin) and (sy0 - margin <= y <= sy1 + margin):
                return True

        fv = getattr(tracker, 'floor_void', None)
        if fv is not None:
            vx0, vx1, vy0, vy1 = fv
            if (vx0 - margin <= x <= vx1 + margin) and (vy0 - margin <= y <= vy1 + margin):
                return True
        for ab in getattr(tracker, 'stair_approach', []):
            ax0, ax1, ay0, ay1 = ab
            if (ax0 - 0.40 <= x <= ax1 + 0.40) and (ay0 - 0.40 <= y <= ay1 + 0.40):
                return True
        return False

    if _conflicts_with_stairs(lx, ly, margin=1.10):
        rx0, rx1 = tracker.rx0 + 0.50, tracker.rx1 - 0.50
        ry0, ry1 = tracker.ry0 + 0.50, tracker.ry1 - 0.50
        candidates = []
        step = 0.30
        curr_y = ry0
        while curr_y <= ry1:
            curr_x = rx0
            while curr_x <= rx1:
                if not _conflicts_with_stairs(curr_x, curr_y, margin=1.10):
                    d = math.hypot(curr_x - rcx, curr_y - rcy)
                    candidates.append((d, curr_x, curr_y))
                curr_x += step
            curr_y += step

        if candidates:
            candidates.sort(key=lambda c: c[0])
            lx, ly = candidates[0][1], candidates[0][2]
        else:
            return

    build_prop(bm, prop_name, lx, ly, z_ceil, 0.0, **kwargs)



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
    if tracker.is_near_door(cx, cy, radius=1.80):
        return False
    if not tracker.is_free(cx - 0.70, cx + 0.70, cy - 0.70, cy + 0.70):
        return False
    tracker.occupy(cx - 0.70, cx + 0.70, cy - 0.70, cy + 0.70)
    build_prop(bm, 'ROUND_TABLE', cx, cy, z_floor, rng.uniform(0.0, 6.28),
               radius=radius)
    build_prop(bm, 'SCATTER_TABLEWARE', cx, cy, z_floor + 0.992, 0.0)
    for sx, sy in ((cx - 0.90, cy), (cx + 0.90, cy)):
        if (not tracker.is_near_door(sx, sy, radius=1.35) and
                tracker.is_free(sx - 0.28, sx + 0.28, sy - 0.28, sy + 0.28)):
            tracker.occupy(sx - 0.28, sx + 0.28, sy - 0.28, sy + 0.28)
            build_prop(bm, 'STOOL', sx, sy, z_floor, rng.uniform(0.0, 6.28))
    return True


def _ensure_minimum_dressing(bm, tracker: RoomOccupancyTracker, rm,
                             z_floor: float, rng) -> None:
    """Last-resort sitting nook so a spacious living room never reads empty, whatever
    the regular recipe managed to place (e.g. an awkward stairwell eating the
    centre). Skips small or narrow rooms: tight rooms and corridors stay clear for walking."""
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    if rw < 4.2 or rd < 4.2 or rw * rd < 18.0:
        return
    spot = _freest_spot(tracker, rng)
    if spot is None:
        return
    cx, cy, h = spot
    if h >= 1.05 and not tracker.is_near_door(cx, cy, radius=2.00):
        _place_nook_set(bm, tracker, cx, cy, z_floor, rng)


def _sofa_fabric(rng):
    """Random hard-wearing sofa/armchair upholstery (leather or white cloth)."""
    from ..materials import (MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2,
                             MAT_INDEX_FABRIC_STITCHED)
    return rng.choice([MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_FABRIC_STITCHED])

def _try_place_hearth(bm, tracker: RoomOccupancyTracker, z_floor: float,
                      z_ceil: Optional[float] = None,
                      chimney_pos: Optional[Any] = None) -> Optional[Tuple[float, float, float]]:
    """Places a stone hearth/fireplace flush against the wall, extending a stone chimney breast up to ceiling."""
    width = 1.60
    depth = 0.55
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    rbx0, rbx1, rby0, rby1 = getattr(tracker, 'room_bounds', (rx0, rx1, ry0, ry1))

    # 1. Try attaching directly to the stone chimney flue flush against the room wall
    if chimney_pos is not None:
        c_list = chimney_pos if isinstance(chimney_pos, list) else [chimney_pos]
        for c in c_list:
            if c is None:
                continue
            cx, cy = c
            d_north = abs(cy - rby1)
            d_south = abs(cy - rby0)
            d_west = abs(cx - rbx0)
            d_east = abs(cx - rbx1)
            min_d = min(d_north, d_south, d_west, d_east)

            if min_d <= 0.85 and (rbx0 - 0.7 <= cx <= rbx1 + 0.7) and (rby0 - 0.7 <= cy <= rby1 + 0.7):
                breast_w = 1.20
                breast_d = 0.42

                if min_d == d_north:
                    # Flush against North (back) wall, firebox faces South (-Y into room)
                    hx = max(rbx0 + width * 0.5 + 0.15, min(rbx1 - width * 0.5 - 0.15, cx))
                    hy = rby1 - 0.32
                    yaw = 0.0
                    b = (hx - width * 0.5 - 0.12, hx + width * 0.5 + 0.12, hy - depth * 0.5 - 0.45, rby1)
                    breast_pos = (hx, rby1 - breast_d * 0.5)
                    breast_size = (breast_w, breast_d)
                elif min_d == d_south:
                    # Flush against South (front) wall, firebox faces North (+Y into room)
                    hx = max(rbx0 + width * 0.5 + 0.15, min(rbx1 - width * 0.5 - 0.15, cx))
                    hy = rby0 + 0.32
                    yaw = math.pi
                    b = (hx - width * 0.5 - 0.12, hx + width * 0.5 + 0.12, rby0, hy + depth * 0.5 + 0.45)
                    breast_pos = (hx, rby0 + breast_d * 0.5)
                    breast_size = (breast_w, breast_d)
                elif min_d == d_west:
                    # Flush against West wall, firebox faces East (+X into room)
                    hx = rbx0 + 0.32
                    hy = max(rby0 + width * 0.5 + 0.15, min(rby1 - width * 0.5 - 0.15, cy))
                    yaw = math.pi / 2
                    b = (rbx0, hx + depth * 0.5 + 0.45, hy - width * 0.5 - 0.12, hy + width * 0.5 + 0.12)
                    breast_pos = (rbx0 + breast_d * 0.5, hy)
                    breast_size = (breast_d, breast_w)
                else:
                    # Flush against East wall, firebox faces West (-X into room)
                    hx = rbx1 - 0.32
                    hy = max(rby0 + width * 0.5 + 0.15, min(rby1 - width * 0.5 - 0.15, cy))
                    yaw = -math.pi / 2
                    b = (hx - depth * 0.5 - 0.45, rbx1, hy - width * 0.5 - 0.12, hy + width * 0.5 + 0.12)
                    breast_pos = (rbx1 - breast_d * 0.5, hy)
                    breast_size = (breast_d, breast_w)

                if tracker.is_free(b[0], b[1], b[2], b[3], ignore_chimney=True, check_windows=True):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    for cb in tracker.chimney_boxes:
                        tracker.occupy(*cb)
                    build_prop(bm, 'HEARTH', hx, hy, z_floor, yaw, width=width, height=1.50)

                    # Solid stone chimney breast extending from mantel up to ceiling
                    from ..materials import MAT_INDEX_STONE
                    from ..mesh_utils import create_beveled_box
                    ceil_z = z_ceil if z_ceil is not None else (z_floor + 3.20)
                    z_start = z_floor + 1.48
                    z_end = ceil_z + 0.05
                    breast_h = max(0.20, z_end - z_start)
                    cb_x, cb_y = breast_pos
                    cb_w, cb_d = breast_size
                    create_beveled_box(
                        bm,
                        size=(cb_w, cb_d, breast_h),
                        location=(cb_x, cb_y, z_start + breast_h * 0.5),
                        mat_index=MAT_INDEX_STONE,
                        bevel_amount=0.015
                    )
                    return (hx, hy, yaw)

    return None


def _try_place_kitchen_stove(bm, tracker: RoomOccupancyTracker, z_floor: float,
                             z_ceil: Optional[float] = None,
                             chimney_pos: Optional[Any] = None) -> Optional[Tuple[float, float, float]]:
    """Places a cast-iron kitchen stove flush against the wall directly attached to the chimney flue."""
    width = 0.95
    depth = 0.75
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    rbx0, rbx1, rby0, rby1 = getattr(tracker, 'room_bounds', (rx0, rx1, ry0, ry1))

    if chimney_pos is not None:
        c_list = chimney_pos if isinstance(chimney_pos, list) else [chimney_pos]
        for c in c_list:
            if c is None:
                continue
            cx, cy = c
            d_north = abs(cy - rby1)
            d_south = abs(cy - rby0)
            d_west = abs(cx - rbx0)
            d_east = abs(cx - rbx1)
            min_d = min(d_north, d_south, d_west, d_east)

            if min_d <= 0.85 and (rbx0 - 0.7 <= cx <= rbx1 + 0.7) and (rby0 - 0.7 <= cy <= rby1 + 0.7):
                if min_d == d_north:
                    hx = max(rbx0 + width * 0.5 + 0.15, min(rbx1 - width * 0.5 - 0.15, cx))
                    hy = rby1 - depth * 0.5 - 0.02
                    yaw = 0.0
                    b = (hx - width * 0.5 - 0.10, hx + width * 0.5 + 0.10, hy - depth * 0.5 - 0.20, rby1)
                elif min_d == d_south:
                    hx = max(rbx0 + width * 0.5 + 0.15, min(rbx1 - width * 0.5 - 0.15, cx))
                    hy = rby0 + depth * 0.5 + 0.02
                    yaw = math.pi
                    b = (hx - width * 0.5 - 0.10, hx + width * 0.5 + 0.10, rby0, hy + depth * 0.5 + 0.20)
                elif min_d == d_west:
                    hx = rbx0 + depth * 0.5 + 0.02
                    hy = max(rby0 + width * 0.5 + 0.15, min(rby1 - width * 0.5 - 0.15, cy))
                    yaw = math.pi / 2
                    b = (rbx0, hx + depth * 0.5 + 0.20, hy - width * 0.5 - 0.10, hy + width * 0.5 + 0.10)
                else:
                    hx = rbx1 - depth * 0.5 - 0.02
                    hy = max(rby0 + width * 0.5 + 0.15, min(rby1 - width * 0.5 - 0.15, cy))
                    yaw = -math.pi / 2
                    b = (hx - depth * 0.5 - 0.20, rbx1, hy - width * 0.5 - 0.10, hy + width * 0.5 + 0.10)

                if tracker.is_free(b[0], b[1], b[2], b[3], ignore_chimney=True, check_windows=True):
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
                         offset_bias: float = 0.0, check_windows: bool = True,
                         ignore_stair: bool = False, **params) -> Optional[Tuple[float, float, float]]:
    """
    Attempts to place a wall-backed prop along one of the candidate walls facing inwards.
    Returns (cx, cy, yaw) if successfully placed, or None.
    """
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    # Reserve the REAL built footprint: registry defaults + caller params.
    # Using the caller's smaller nominal size let neighbouring props overlap
    # and let the overhang clip through perpendicular walls.
    width, depth = _wall_prop_footprint(key, width, depth, params)
    if key == 'ARMCHAIR':
        width = max(width, 1.10)
        depth = max(depth, 1.02)
    elif key == 'SOFA':
        width = max(width, float(params.get('length', 1.80)))
        depth = max(depth, 1.05)

    if key == 'COUNTER':
        ignore_stair = False

    _rb = getattr(tracker, 'room_bounds', None) or (rx0, rx1, ry0, ry1)
    _wx0, _wx1, _wy0, _wy1 = _rb
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    _rng = getattr(tracker, 'rng', None)
    jit = _rng.uniform(-0.30, 0.30) if _rng is not None else 0.0

    _fvoid = getattr(tracker, 'floor_void', None)

    x_span = rx1 - rx0
    corner_pad_x = min(0.72, max(0.40, (x_span - width) * 0.5 - 0.05)) if x_span > width + 0.80 else 0.40
    y_span = ry1 - ry0
    corner_pad_y = min(0.72, max(0.40, (y_span - width) * 0.5 - 0.05)) if y_span > width + 0.80 else 0.40

    for wall in candidate_walls:
        # Wall props keep a small stand-off from the wall face and the collision
        # test is tightened to match, so a table/shelf can never end up half
        # sunk into the wall it stands against.
        if wall == 'NORTH':
            # Back at +Y, front at -Y -> yaw = 0.0
            cy = _wy1 - depth * 0.5 - 0.04
            yaw = 0.0
            min_x = rx0 + width * 0.5 + corner_pad_x
            max_x = rx1 - width * 0.5 - corner_pad_x
            for cx in _sample_wall_positions(rcx + offset_bias + jit, min_x, max_x, step=0.30):
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if _fvoid is not None:
                    # Enforce solid floor under prop and >= 2.0m clear walking aisle to void
                    if b[2] < _fvoid[3] + 2.00 or not (b[1] <= _fvoid[0] or b[0] >= _fvoid[1] or b[2] >= _fvoid[3]):
                        continue
                if tracker.is_near_door(cx, cy, radius=1.25) or any(tracker.is_near_door(px, py, radius=1.05) for px in (b[0], b[1]) for py in (b[2], b[3])):
                    continue
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=0.12, check_windows=check_windows, ignore_stair=ignore_stair,
                                   bounds_slack=0.10):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'SOUTH':
            # Back at -Y, front at +Y -> yaw = math.pi
            cy = _wy0 + depth * 0.5 + 0.04
            yaw = math.pi
            min_x = rx0 + width * 0.5 + corner_pad_x
            max_x = rx1 - width * 0.5 - corner_pad_x
            for cx in _sample_wall_positions(rcx + offset_bias + jit, min_x, max_x, step=0.30):
                b = (cx - width * 0.5, cx + width * 0.5, cy - depth * 0.5, cy + depth * 0.5)
                if _fvoid is not None:
                    # Enforce solid floor under prop and >= 2.0m clear walking aisle to void
                    if _fvoid[2] - b[3] < 2.00 or not (b[1] <= _fvoid[0] or b[0] >= _fvoid[1] or b[3] <= _fvoid[2]):
                        continue
                if tracker.is_near_door(cx, cy, radius=1.25) or any(tracker.is_near_door(px, py, radius=1.05) for px in (b[0], b[1]) for py in (b[2], b[3])):
                    continue
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=0.12, check_windows=check_windows, ignore_stair=ignore_stair,
                                   bounds_slack=0.10):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'EAST':
            # Back at +X, front at -X -> yaw = -math.pi / 2
            cx = _wx1 - depth * 0.5 - 0.04
            yaw = -math.pi / 2
            min_y = ry0 + width * 0.5 + corner_pad_y
            max_y = ry1 - width * 0.5 - corner_pad_y
            for cy in _sample_wall_positions(rcy + offset_bias + jit, min_y, max_y, step=0.30):
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if _fvoid is not None:
                    # Enforce solid floor under prop and >= 2.0m clear walking aisle to void
                    if b[0] - _fvoid[1] < 2.00 or not (b[3] <= _fvoid[2] or b[2] >= _fvoid[3] or b[0] >= _fvoid[1]):
                        continue
                if tracker.is_near_door(cx, cy, radius=1.25) or any(tracker.is_near_door(px, py, radius=1.05) for px in (b[0], b[1]) for py in (b[2], b[3])):
                    continue
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=0.12, check_windows=check_windows, ignore_stair=ignore_stair,
                                   bounds_slack=0.10):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

        elif wall == 'WEST':
            # Back at -X, front at +X -> yaw = math.pi / 2
            cx = _wx0 + depth * 0.5 + 0.04
            yaw = math.pi / 2
            min_y = ry0 + width * 0.5 + corner_pad_y
            max_y = ry1 - width * 0.5 - corner_pad_y
            for cy in _sample_wall_positions(rcy + offset_bias + jit, min_y, max_y, step=0.30):
                b = (cx - depth * 0.5, cx + depth * 0.5, cy - width * 0.5, cy + width * 0.5)
                if _fvoid is not None:
                    # Enforce solid floor under prop and >= 2.0m clear walking aisle to void
                    if _fvoid[0] - b[1] < 2.00 or not (b[3] <= _fvoid[2] or b[2] >= _fvoid[3] or b[1] <= _fvoid[0]):
                        continue
                if tracker.is_near_door(cx, cy, radius=1.25) or any(tracker.is_near_door(px, py, radius=1.05) for px in (b[0], b[1]) for py in (b[2], b[3])):
                    continue
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=0.12, check_windows=check_windows, ignore_stair=ignore_stair,
                                   bounds_slack=0.10):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, key, cx, cy, z_floor, yaw, **params)
                    return (cx, cy, yaw)

    return None


def _try_place_wall_table_nook(bm, tracker: RoomOccupancyTracker, z_floor: float, rng,
                               candidate_walls=('WEST', 'EAST'),
                               target_pos: Optional[float] = None,
                               table_radius: float = 0.48) -> Optional[Tuple[float, float, str]]:
    """
    Places a cozy courtier/tavern sitting nook flush along a wall:
    a round pedestal table with tableware scatter and 2-3 wooden stools
    tucked neatly against it, keeping room center and aisles completely unobstructed.
    Returns (table_x, table_y, wall_name) if placed, or None.
    """
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    _rb = getattr(tracker, 'room_bounds', None) or (rx0, rx1, ry0, ry1)
    _wx0, _wx1, _wy0, _wy1 = _rb
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5

    tr = table_radius
    wall_dist = tr + 0.16
    nook_depth = wall_dist + tr + 0.55
    half_span = tr + 0.52

    _fvoid = getattr(tracker, 'floor_void', None)

    for wall in candidate_walls:
        if wall == 'WEST':
            tx = _wx0 + wall_dist
            min_y = ry0 + half_span + 0.20
            max_y = ry1 - half_span - 0.20
            center_y = target_pos if target_pos is not None else rcy
            for cy in _sample_wall_positions(center_y, min_y, max_y, step=0.30):
                bx0, bx1 = _wx0 + 0.01, _wx0 + nook_depth
                by0, by1 = cy - half_span, cy + half_span
                if _fvoid is not None:
                    if _fvoid[0] - bx1 < 1.80 or not (by1 <= _fvoid[2] or by0 >= _fvoid[3] or bx1 <= _fvoid[0]):
                        continue
                if tracker.is_near_door(tx, cy, radius=1.60) or any(
                    tracker.is_near_door(px, py, radius=1.20) for px in (bx0, bx1) for py in (by0, by1)
                ):
                    continue
                if tracker.is_free(bx0, bx1, by0, by1, check_windows=False, bounds_slack=0.22):
                    tracker.occupy(bx0, bx1, by0, by1)
                    build_prop(bm, 'ROUND_TABLE', tx, cy, z_floor, rng.uniform(0.0, 6.28), radius=tr)
                    scatter_prop = 'SCATTER_TABLEWARE' if rng.random() < 0.65 else 'BOTTLE_CLUSTER'
                    build_prop(bm, scatter_prop, tx, cy, z_floor + 0.99, 0.0)
                    build_prop(bm, 'STOOL', tx, cy + (tr + 0.28), z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', tx, cy - (tr + 0.28), z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', tx + (tr + 0.25), cy, z_floor, rng.uniform(0.0, 6.28))
                    return (tx, cy, 'WEST')

        elif wall == 'EAST':
            tx = _wx1 - wall_dist
            min_y = ry0 + half_span + 0.20
            max_y = ry1 - half_span - 0.20
            center_y = target_pos if target_pos is not None else rcy
            for cy in _sample_wall_positions(center_y, min_y, max_y, step=0.30):
                bx0, bx1 = _wx1 - nook_depth, _wx1 - 0.01
                by0, by1 = cy - half_span, cy + half_span
                if _fvoid is not None:
                    if bx0 - _fvoid[1] < 1.80 or not (by1 <= _fvoid[2] or by0 >= _fvoid[3] or bx0 >= _fvoid[1]):
                        continue
                if tracker.is_near_door(tx, cy, radius=1.60) or any(
                    tracker.is_near_door(px, py, radius=1.20) for px in (bx0, bx1) for py in (by0, by1)
                ):
                    continue
                if tracker.is_free(bx0, bx1, by0, by1, check_windows=False, bounds_slack=0.22):
                    tracker.occupy(bx0, bx1, by0, by1)
                    build_prop(bm, 'ROUND_TABLE', tx, cy, z_floor, rng.uniform(0.0, 6.28), radius=tr)
                    scatter_prop = 'SCATTER_TABLEWARE' if rng.random() < 0.65 else 'BOTTLE_CLUSTER'
                    build_prop(bm, scatter_prop, tx, cy, z_floor + 0.99, 0.0)
                    build_prop(bm, 'STOOL', tx, cy + (tr + 0.28), z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', tx, cy - (tr + 0.28), z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', tx - (tr + 0.25), cy, z_floor, rng.uniform(0.0, 6.28))
                    return (tx, cy, 'EAST')

        elif wall == 'SOUTH':
            ty = _wy0 + wall_dist
            min_x = rx0 + half_span + 0.20
            max_x = rx1 - half_span - 0.20
            center_x = target_pos if target_pos is not None else rcx
            for cx in _sample_wall_positions(center_x, min_x, max_x, step=0.30):
                bx0, bx1 = cx - half_span, cx + half_span
                by0, by1 = _wy0 + 0.01, _wy0 + nook_depth
                if _fvoid is not None:
                    if _fvoid[2] - by1 < 1.80 or not (bx1 <= _fvoid[0] or bx0 >= _fvoid[1] or by1 <= _fvoid[2]):
                        continue
                if tracker.is_near_door(cx, ty, radius=1.60) or any(
                    tracker.is_near_door(px, py, radius=1.20) for px in (bx0, bx1) for py in (by0, by1)
                ):
                    continue
                if tracker.is_free(bx0, bx1, by0, by1, check_windows=False, bounds_slack=0.22):
                    tracker.occupy(bx0, bx1, by0, by1)
                    build_prop(bm, 'ROUND_TABLE', cx, ty, z_floor, rng.uniform(0.0, 6.28), radius=tr)
                    scatter_prop = 'SCATTER_TABLEWARE' if rng.random() < 0.65 else 'BOTTLE_CLUSTER'
                    build_prop(bm, scatter_prop, cx, ty, z_floor + 0.99, 0.0)
                    build_prop(bm, 'STOOL', cx + (tr + 0.28), ty, z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', cx - (tr + 0.28), ty, z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', cx, ty + (tr + 0.25), z_floor, rng.uniform(0.0, 6.28))
                    return (cx, ty, 'SOUTH')

        elif wall == 'NORTH':
            ty = _wy1 - wall_dist
            min_x = rx0 + half_span + 0.20
            max_x = rx1 - half_span - 0.20
            center_x = target_pos if target_pos is not None else rcx
            for cx in _sample_wall_positions(center_x, min_x, max_x, step=0.30):
                bx0, bx1 = cx - half_span, cx + half_span
                by0, by1 = _wy1 - nook_depth, _wy1 - 0.01
                if _fvoid is not None:
                    if by0 - _fvoid[3] < 1.80 or not (bx1 <= _fvoid[0] or bx0 >= _fvoid[1] or by0 >= _fvoid[3]):
                        continue
                if tracker.is_near_door(cx, ty, radius=1.60) or any(
                    tracker.is_near_door(px, py, radius=1.20) for px in (bx0, bx1) for py in (by0, by1)
                ):
                    continue
                if tracker.is_free(bx0, bx1, by0, by1, check_windows=False, bounds_slack=0.22):
                    tracker.occupy(bx0, bx1, by0, by1)
                    build_prop(bm, 'ROUND_TABLE', cx, ty, z_floor, rng.uniform(0.0, 6.28), radius=tr)
                    scatter_prop = 'SCATTER_TABLEWARE' if rng.random() < 0.65 else 'BOTTLE_CLUSTER'
                    build_prop(bm, scatter_prop, cx, ty, z_floor + 0.99, 0.0)
                    build_prop(bm, 'STOOL', cx + (tr + 0.28), ty, z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', cx - (tr + 0.28), ty, z_floor, rng.uniform(0.0, 6.28))
                    build_prop(bm, 'STOOL', cx, ty - (tr + 0.25), z_floor, rng.uniform(0.0, 6.28))
                    return (cx, ty, 'NORTH')

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
    build_prop(bm, 'BOOK_PILE_SMALL', bx, by, z_floor + 0.98, rng.uniform(0.0, 6.28))
    # Small potted plant on the opposite corner of the desk (skipped in industrial/utility rooms)
    if not getattr(tracker, 'no_rugs', False) and rng.random() < 0.60:
        px, py = cx + fy * 0.35, cy - fx * 0.35
        build_prop(bm, 'POTTED_PLANT_SMALL', px, py, z_floor + 0.98, rng.uniform(0.0, 6.28))


def _try_place_bed(bm, tracker: RoomOccupancyTracker, z_floor: float,
                   length: float = 2.45, width: float = 1.55,
                   ignore_west: bool = False) -> Optional[Tuple[float, float, float]]:
    """Places a timber bed with headboard against a wall, facing into the room."""
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx = (rx0 + rx1) * 0.5
    rcy = (ry0 + ry1) * 0.5
    # Headboard sits flush to the REAL wall (1 cm off the plaster).
    _rb = getattr(tracker, 'room_bounds', None) or (rx0, rx1, ry0, ry1)
    _wx0, _wx1, _wy0, _wy1 = _rb

    y_span = ry1 - ry0
    x_span = rx1 - rx0
    if min(x_span, y_span) < 2.5:
        return None

    # Multi-tier candidate sizes and tolerances so small / cramped rooms
    # are guaranteed to fit a bed rather than abandoning it.
    candidates = [
        (length, width, 1.40, 0.12, 0.16),
        (min(length, 2.15), min(width, 1.25), 1.10, 0.08, 0.18),
        (min(length, 1.95), min(width, 1.05), 0.85, 0.04, 0.20),
        (min(length, 1.80), min(width, 0.95), 0.60, 0.02, 0.22),
    ]

    for cand_l, cand_w, door_rad, free_margin, bounds_slack in candidates:
        bed_pad_y = min(0.60, max(0.12, (y_span - cand_w) * 0.5 - 0.05)) if y_span > cand_w + 0.35 else 0.06
        bed_pad_x = min(0.60, max(0.12, (x_span - cand_w) * 0.5 - 0.05)) if x_span > cand_w + 0.35 else 0.06

        min_y = ry0 + cand_w * 0.5 + bed_pad_y
        max_y = ry1 - cand_w * 0.5 - bed_pad_y
        min_x = rx0 + cand_w * 0.5 + bed_pad_x
        max_x = rx1 - cand_w * 0.5 - bed_pad_x

        y_pts = _sample_wall_positions(rcy, min_y, max_y, step=0.20)
        if not y_pts and y_span >= cand_w + 0.08:
            y_pts = [rcy]

        x_pts = _sample_wall_positions(rcx, min_x, max_x, step=0.20)
        if not x_pts and x_span >= cand_w + 0.08:
            x_pts = [rcx]

        # 1. Try West wall (headboard at -X, bed extends +X into room)
        for dx in (0.0, 0.25, 0.50):
            if ignore_west:
                break
            cx = _wx0 + cand_l * 0.5 + 0.01 + dx
            if cx + cand_l * 0.5 > _wx1 - 0.10:
                break
            for cy in y_pts:
                if tracker.is_near_door(cx, cy, radius=door_rad):
                    continue
                b = (cx - cand_l * 0.5, cx + cand_l * 0.5, cy - cand_w * 0.5, cy + cand_w * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=free_margin, bounds_slack=bounds_slack):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, 'BED', cx, cy, z_floor, 0.0, length=cand_l, width=cand_w)
                    return (cx, cy, 0.0)

        # 2. Try East wall (headboard at +X, bed extends -X into room)
        for dx in (0.0, 0.25, 0.50):
            cx = _wx1 - cand_l * 0.5 - 0.01 - dx
            if cx - cand_l * 0.5 < _wx0 + 0.10:
                break
            for cy in y_pts:
                if tracker.is_near_door(cx, cy, radius=door_rad):
                    continue
                b = (cx - cand_l * 0.5, cx + cand_l * 0.5, cy - cand_w * 0.5, cy + cand_w * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=free_margin, bounds_slack=bounds_slack):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, 'BED', cx, cy, z_floor, math.pi, length=cand_l, width=cand_w)
                    return (cx, cy, math.pi)

        # 3. Try North wall (headboard at +Y, bed extends -Y into room)
        for dy in (0.0, 0.25, 0.50):
            cy = _wy1 - cand_l * 0.5 - 0.01 - dy
            if cy - cand_l * 0.5 < _wy0 + 0.10:
                break
            for cx in x_pts:
                if tracker.is_near_door(cx, cy, radius=door_rad):
                    continue
                b = (cx - cand_w * 0.5, cx + cand_w * 0.5, cy - cand_l * 0.5, cy + cand_l * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=free_margin, bounds_slack=bounds_slack):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, 'BED', cx, cy, z_floor, -math.pi / 2, length=cand_l, width=cand_w)
                    return (cx, cy, -math.pi / 2)

        # 4. Try South wall (headboard at -Y, bed extends +Y into room)
        for dy in (0.0, 0.25, 0.50):
            cy = _wy0 + cand_l * 0.5 + 0.01 + dy
            if cy + cand_l * 0.5 > _wy1 - 0.10:
                break
            for cx in x_pts:
                if tracker.is_near_door(cx, cy, radius=door_rad):
                    continue
                b = (cx - cand_w * 0.5, cx + cand_w * 0.5, cy - cand_l * 0.5, cy + cand_l * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=free_margin, bounds_slack=bounds_slack):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, 'BED', cx, cy, z_floor, math.pi / 2, length=cand_l, width=cand_w)
                    return (cx, cy, math.pi / 2)

    # Hard guarantee fallback: scan interior floor grid for any clear spot
    final_l, final_w = 1.85, 0.95
    for orient, l_val, w_val, yaw in (('X', final_l, final_w, 0.0), ('Y', final_w, final_l, -math.pi / 2)):
        xs = [rx0 + l_val * 0.5 + 0.10 + i * 0.25 for i in range(int(max(1.0, x_span - l_val - 0.20) / 0.25) + 1)]
        ys = [ry0 + w_val * 0.5 + 0.10 + i * 0.25 for i in range(int(max(1.0, y_span - w_val - 0.20) / 0.25) + 1)]
        for cx in xs:
            for cy in ys:
                b = (cx - l_val * 0.5, cx + l_val * 0.5, cy - w_val * 0.5, cy + w_val * 0.5)
                if tracker.is_free(b[0], b[1], b[2], b[3], margin=0.02, bounds_slack=0.25):
                    tracker.occupy(b[0], b[1], b[2], b[3])
                    build_prop(bm, 'BED', cx, cy, z_floor, yaw, length=final_l, width=final_w)
                    return (cx, cy, yaw)

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
        # The urn is ~0.47 m across but the leaf fans reach ~1.0 m. Reserve the
        # foliage radius, not just the pot, so leaves never poke through a
        # doorway or a wall.
        box = 0.55
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    xs = [rx0 + box, rx1 - box]
    ys = [ry0 + box, ry1 - box]
    rng.shuffle(xs)
    rng.shuffle(ys)
    for cx in xs:
        for cy in ys:
            # Jitter towards the room only: never let the foliage cross the wall.
            jx = min(max(cx + _jit(rng, 0.10), rx0 + box), rx1 - box)
            jy = min(max(cy + _jit(rng, 0.10), ry0 + box), ry1 - box)
            # Explicit doorway check: the reserved corridor box alone can be
            # missed by the old tiny 0.34 m pot footprint, parking a planter
            # right in a portal.
            if tracker.is_near_door(jx, jy, radius=box + 0.45):
                continue
            if tracker.is_free(jx - box, jx + box, jy - box, jy + box, margin=0.05):
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

    # Conform bounding box to authentic rug texture aspect ratio (848 x 1264)
    RUG_ASPECT = 1264.0 / 848.0
    _is_y = (l >= w)
    _d_long = l if _is_y else w
    _d_short = w if _is_y else l
    _ratio = _d_long / max(0.01, _d_short)
    if _ratio < 1.7 * RUG_ASPECT:
        if _ratio > RUG_ASPECT:
            _d_long = _d_short * RUG_ASPECT
        else:
            _d_short = _d_long / RUG_ASPECT
        w = _d_short if _is_y else _d_long
        l = _d_long if _is_y else _d_short
        ew = w * ca + l * sa
        el = w * sa + l * ca

    hole = getattr(rm, 'stair_hole', None)
    void_h = getattr(rm, 'floor_void', None) or getattr(tracker, 'floor_void', None)

    # Hard guarantee: rugs must NEVER sit in mid-air over a double-height floor void!
    if void_h is not None:
        vx0, vx1, vy0, vy1 = void_h
        if not (cx + ew * 0.5 < vx0 or cx - ew * 0.5 > vx1 or
                cy + el * 0.5 < vy0 or cy - el * 0.5 > vy1):
            return None

    def _hits_hole(px, py, pw, pl):
        if hole is None:
            return False
        hx0, hx1 = hole[0] - 0.20, hole[1] + 0.20
        hy0, hy1 = hole[2] - 0.20, hole[3] + 0.20
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
        h0, h1 = (hole[2] - 0.20, hole[3] + 0.20) if along_y else (hole[0] - 0.20, hole[1] + 0.20)
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
        else:
            return None

    if ew < avail_w:
        cx = min(max(cx, rx0 + ew * 0.5), rx1 - ew * 0.5)
    else:
        cx = (rx0 + rx1) * 0.5
    if el < avail_l:
        cy = min(max(cy, ry0 + el * 0.5), ry1 - el * 0.5)
    else:
        cy = (ry0 + ry1) * 0.5

    # Hard guarantee: rugs must NEVER cross or overlap a stair opening
    if _hits_hole(cx, cy, ew, el):
        return None

    # Hard guarantee: rugs must NEVER cross or overlap a portal walking corridor
    for d in getattr(tracker, 'doorways', []):
        if d.get('is_portal', False) or d.get('w', 1.0) >= 2.0:
            dcx = d.get('x', (rx0 + rx1) * 0.5)
            dcy = d.get('y', (ry0 + ry1) * 0.5)
            dw = d.get('w', 2.0)
            axis = d.get('axis', 'X')
            wm = dw * 0.5 + 0.85
            clr = 3.20
            if axis == 'X':
                pbox = (dcx - wm, dcx + wm, dcy - clr, dcy + clr)
            else:
                pbox = (dcx - clr, dcx + clr, dcy - wm, dcy + wm)
            if not (cx + ew * 0.5 < pbox[0] or cx - ew * 0.5 > pbox[1] or
                    cy + el * 0.5 < pbox[2] or cy - el * 0.5 > pbox[3]):
                return None

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
    min_dim = min(rw, rd)

    # Hallways, circulation corridors, and narrow passages with multiple doors
    # must NEVER be furnished as bedrooms — dress them cleanly as corridors!
    if min_dim < 2.7 or (min_dim < 3.2 and len(rm.doorways) >= 3):
        _furnish_corridor(bm, rm, tracker, z_floor, z_ceil, rng, density)
        return

    narrow_room = min_dim < 3.4  # too narrow for full bedroom set

    # 1. Bed — scale down for small/narrow tenement rooms
    if narrow_room:
        bed_w = 1.25
        bed_len = 2.25
    elif is_master:
        bed_w = 1.85
        bed_len = 2.65
    else:
        bed_w = 1.55
        bed_len = 2.45
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
        # Chest is 0.85 x 0.65 m; reserving only 0.45 m of depth let it sink
        # into the wall / overlap the next prop.
        cw, cd = 0.85, 0.68
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

    # 5. Writing desk in spacious bedrooms (placed BEFORE optional accent seating)
    if (rw >= 3.6 or rd >= 3.6) and density >= 0.5:
        if is_master:
            _d = _try_place_wall_prop(bm, 'DESK', 1.30, 0.65, tracker, z_floor,
                                      candidate_walls=('SOUTH', 'EAST', 'NORTH'))
            if _d:
                _dress_desk(bm, tracker, _d[0], _d[1], _d[2], z_floor, rng, (rcx, rcy))
        else:
            _try_place_wall_prop(bm, 'SHELF', 1.20, 0.40, tracker, z_floor,
                                 candidate_walls=('SOUTH', 'NORTH', 'EAST'))

    # 6. Cozy reading armchair in bedroom corner if space permits
    if not narrow_room and min(rw, rd) >= 3.0 and (rw * rd) >= 10.0:
        arm_pad = 0.70
        check_r = 0.55
        for cx in (rm.bounds[0] + arm_pad, rm.bounds[1] - arm_pad):
            for cy in (rm.bounds[2] + arm_pad, rm.bounds[3] - arm_pad):
                if not tracker.is_near_door(cx, cy, radius=1.25) and tracker.is_free(
                    cx - check_r, cx + check_r, cy - check_r, cy + check_r, margin=0.10
                ):
                    tracker.occupy(cx - check_r, cx + check_r, cy - check_r, cy + check_r)
                    # Face the room centre, never buried nose-first in the corner.
                    dir_x, dir_y = rcx - cx, rcy - cy
                    yaw = math.atan2(dir_x, -dir_y) if (dir_x or dir_y) else 0.0
                    build_prop(bm, 'ARMCHAIR', cx, cy, z_floor, yaw, fabric_mat=_sofa_fabric(rng))
                    break
            else:
                continue
            break

    # 7. Floor book pile in bedroom corner
    for cx in (rm.bounds[0] + 0.35, rm.bounds[1] - 0.35):
        for cy in (rm.bounds[2] + 0.35, rm.bounds[3] - 0.35):
            if not tracker.is_near_door(cx, cy, radius=1.25) and tracker.is_free(cx - 0.28, cx + 0.28, cy - 0.28, cy + 0.28, margin=0.08):
                tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
                build_prop(bm, 'BOOK_PILE_LARGE', cx, cy, z_floor, rng.uniform(0, 1.0))
                break

    # 8. Cozy floor area rug alongside and at foot of the bed
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

    # 8b. Secondary bedroom runner rug so bedroom floor feels warmly dressed
    if (rw >= 3.6 or rd >= 3.6):
        sub_rug = 'RUG_FOREST' if rug_choice != 'RUG_FOREST' else 'RUG_SAPPHIRE'
        _lay_rug(bm, tracker, rm, rng, sub_rug, rcx, rcy, z_floor,
                 min(1.40, rw * 0.35), min(2.60, rd * 0.48), yaw_max=0.04, allow_overlap=False)

    # 6. Ceiling light
    if is_master and (rw * rd >= 16.0):
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, prop_name='CHANDELIER', radius=0.48)
    else:
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
            build_prop(bm, 'BOOK_PILE_SMALL', rcx + 0.40, rcy, z_floor + 0.98, 0.3)
            if rng.random() < 0.60:
                build_prop(bm, 'POTTED_PLANT_SMALL', rcx - 0.40, rcy, z_floor + 0.98, rng.uniform(0.0, 6.28))

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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _furnish_tavern_taproom(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                            rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a classic lively tavern common room / taproom."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Bar Counter along a clear wall (guaranteed placement).  A big taproom
    # gets a long straight bar with stools along the customer side.  We try each
    # wall at several tangential offsets, clamping the footprint inside the
    # usable room, so the counter is never rejected for overhanging a wall (the
    # old L-return arm pushed the footprint outside the room, so no bar was
    # ever built at all).
    _long_bar = max(rw, rd) >= 7.0
    counter_len = (min(4.6, max(3.2, max(rw, rd) * 0.58)) if _long_bar
                   else min(2.8, max(1.8, rw * 0.42)))
    _n_stools = 5 if _long_bar else 3
    placed_counter = False

    _rx0, _rx1 = tracker.rx0 + 0.05, tracker.rx1 - 0.05
    _ry0, _ry1 = tracker.ry0 + 0.05, tracker.ry1 - 0.05
    _bar_depth = 0.80

    def _try_bar(wall, yaw):
        along_x = wall in ('N', 'S')
        span = (rm.bounds[1] - rm.bounds[0]) if along_x else (rm.bounds[3] - rm.bounds[2])
        cl = min(counter_len, span - 1.0)
        if cl < 1.6:
            return False
        cw = cl if along_x else _bar_depth
        cd = _bar_depth if along_x else cl
        if along_x:
            base, lo, hi = rcx, _rx0 + cw * 0.5, _rx1 - cw * 0.5
        else:
            base, lo, hi = rcy, _ry0 + cd * 0.5, _ry1 - cd * 0.5
        if lo > hi:
            return False
        offs = [0.0, 0.9, -0.9, 1.8, -1.8, (hi - lo) * 0.5, -(hi - lo) * 0.5]
        for off in offs:
            tang = min(hi, max(lo, base + off))
            # Seat the counter far enough off the wall that a server can stand
            # behind it (the wall shelves are mounted above/behind the counter).
            _bar_off = 1.70
            if along_x:
                cx = tang
                cy = (_ry1 - _bar_off) if wall == 'N' else (_ry0 + _bar_off)
            else:
                cy = tang
                cx = (_rx1 - _bar_off) if wall == 'E' else (_rx0 + _bar_off)
            b = (cx - cw * 0.5, cx + cw * 0.5, cy - cd * 0.5, cy + cd * 0.5)
            if not tracker.is_free(*b):
                continue
            if wall == 'N':
                front_dx, front_dy, tang_dx, tang_dy = 0.0, -1.0, 1.0, 0.0
            elif wall == 'S':
                front_dx, front_dy, tang_dx, tang_dy = 0.0, 1.0, 1.0, 0.0
            elif wall == 'E':
                front_dx, front_dy, tang_dx, tang_dy = -1.0, 0.0, 0.0, 1.0
            else:  # W
                front_dx, front_dy, tang_dx, tang_dy = 1.0, 0.0, 0.0, 1.0
            tracker.occupy(*b)
            # Keep the customer side of the bar clear: no dining tables jammed
            # against the stools.
            _ap = 0.20
            _ad = 1.20
            if wall == 'N':
                tracker.occupy(b[0] - _ap, b[1] + _ap, b[2] - _ad, b[3])
            elif wall == 'S':
                tracker.occupy(b[0] - _ap, b[1] + _ap, b[2], b[3] + _ad)
            elif wall == 'E':
                tracker.occupy(b[0] - _ad, b[1], b[2] - _ap, b[3] + _ap)
            else:
                tracker.occupy(b[0], b[1] + _ad, b[2] - _ap, b[3] + _ap)
            # The tracker region is inset from the real wall face; the wall
            # shelves must reach the plaster, so add that inset to the shelf
            # anchor (the counter itself stays where it is).
            if wall == 'N':
                _wall_inset = rm.bounds[3] - _ry1
            elif wall == 'S':
                _wall_inset = _ry0 - rm.bounds[2]
            elif wall == 'E':
                _wall_inset = rm.bounds[1] - _rx1
            else:  # W
                _wall_inset = _rx0 - rm.bounds[0]
            _bb_off = _bar_off + max(0.0, _wall_inset)
            build_prop(bm, 'COUNTER', cx, cy, z_floor, yaw, length=cl,
                       return_length=0.0, back_bar_offset=_bb_off)
            # Stools along the whole customer side of the counter.
            step_st = cl / max(2, _n_stools - 1) * 0.82
            for i in range(_n_stools):
                offset_t = (i - (_n_stools - 1) * 0.5) * step_st
                sx = cx + front_dx * 0.68 + tang_dx * offset_t
                sy = cy + front_dy * 0.68 + tang_dy * offset_t
                if _rx0 + 0.05 <= sx <= _rx1 - 0.05 and _ry0 + 0.05 <= sy <= _ry1 - 0.05:
                    build_prop(bm, 'STOOL', sx, sy, z_floor, yaw, height=0.72)
            # Tableware scatter on counter at exact counter top height (1.235)
            build_prop(bm, 'SCATTER_TABLEWARE', cx + tang_dx * 0.4, cy + tang_dy * 0.4,
                       z_floor + 1.235, yaw)
            if rng.random() < 0.50:
                build_prop(bm, 'POTTED_PLANT_SMALL', cx - tang_dx * 0.4, cy - tang_dy * 0.4,
                           z_floor + 1.235, rng.uniform(0.0, 6.28))
            return True
        return False

    for _wall, _yaw in (('N', 0.0), ('E', -math.pi / 2),
                        ('W', math.pi / 2), ('S', math.pi)):
        if _try_bar(_wall, _yaw):
            placed_counter = True
            break

    # 2. Hearth fireplace directly attached to chimney flue or on clear wall
    _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)

    # 3. Dining / Drinking Tables with chairs.  A narrow taproom should stay
    # pleasantly busy, not become an obstacle course: fewer tables with wider
    # walking lanes between the door, bar and stairs.
    area = rw * rd
    _narrow_tap = (min(rw, rd) < 7.0
                   or max(rw, rd) / max(min(rw, rd), 1.0) > 2.0)
    if _narrow_tap:
        target_tables = max(3, min(6, int(area / 15.0) + 1))
        margin_x = 1.45
        margin_y = 1.45
    else:
        target_tables = max(2, min(8, int(area / 12.0) + 1))
        margin_x = 1.25
        margin_y = 1.25
    ux0 = tracker.rx0 + margin_x
    ux1 = tracker.rx1 - margin_x
    uy0 = tracker.ry0 + margin_y
    uy1 = tracker.ry1 - margin_y
    span_x = max(1.0, ux1 - ux0)
    span_y = max(1.0, uy1 - uy0)

    # Grid columns and rows based on usable floor span
    n_cols = max(2, min(4, int(span_x / 2.3) + 1))
    n_rows = max(2, min(4, int(span_y / 2.3) + 1))

    # Generate grid coordinates across the entire taproom floor
    grid_cands = []
    for c in range(n_cols):
        cx = ux0 + (c + 0.5) * (span_x / n_cols)
        for r in range(n_rows):
            cy = uy0 + (r + 0.5) * (span_y / n_rows)
            grid_cands.append((cx, cy, c, r))

    # Prioritize central / wide spots first, then outward
    grid_cands.sort(key=lambda item: abs(item[0] - rcx) + abs(item[1] - rcy))

    placed_tables = 0
    first_table_pos = None
    z_tab = z_floor + 0.992

    for cx, cy, col, row in grid_cands:
        if placed_tables >= target_tables:
            break
        tx = cx + _jit(rng, 0.18)
        ty = cy + _jit(rng, 0.18)

        # Do not block doorways
        if tracker.is_near_door(tx, ty, radius=1.35):
            continue

        # Alternate between rectangular communal tables and round drinking tables
        use_rect = ((col + row) % 2 == 0) and (span_x >= 4.0 or span_y >= 4.0)
        placed_this = False

        if use_rect:
            # Try rectangular indoor table (communal drinking table)
            tw = min(2.10, max(1.50, span_x / n_cols - 0.50))
            td = 0.90
            yaw = 0.0 if (span_x >= span_y) else (math.pi * 0.5)
            if yaw != 0.0:
                tw, td = td, tw
            hw = tw * 0.5 + 0.40
            hd = td * 0.5 + 0.40
            if tracker.is_free(tx - hw, tx + hw, ty - hd, ty + hd):
                build_prop(bm, 'INDOOR_TABLE', tx, ty, z_floor, yaw, length=max(tw, td), width=min(tw, td))
                build_prop(bm, 'SCATTER_TABLEWARE', tx - 0.35, ty, z_tab, yaw)
                build_prop(bm, 'BOTTLE_CLUSTER', tx + 0.35, ty, z_tab, yaw)
                if rng.random() < 0.40:
                    build_prop(bm, 'PEWTER_TANKARD', tx, ty, z_tab, 0.0)

                # Chairs along both sides plus ends
                if yaw == 0.0:
                    chair_spots = [
                        (tx - 0.45, ty - (td * 0.5 + 0.35), math.pi),
                        (tx + 0.45, ty - (td * 0.5 + 0.35), math.pi),
                        (tx - 0.45, ty + (td * 0.5 + 0.35), 0.0),
                        (tx + 0.45, ty + (td * 0.5 + 0.35), 0.0),
                        (tx - (tw * 0.5 + 0.35), ty, math.pi * 0.5),
                        (tx + (tw * 0.5 + 0.35), ty, -math.pi * 0.5),
                    ]
                else:
                    chair_spots = [
                        (tx - (tw * 0.5 + 0.35), ty - 0.45, math.pi * 0.5),
                        (tx - (tw * 0.5 + 0.35), ty + 0.45, math.pi * 0.5),
                        (tx + (tw * 0.5 + 0.35), ty - 0.45, -math.pi * 0.5),
                        (tx + (tw * 0.5 + 0.35), ty + 0.45, -math.pi * 0.5),
                        (tx, ty - (td * 0.5 + 0.35), math.pi),
                        (tx, ty + (td * 0.5 + 0.35), 0.0),
                    ]
                for chx, chy, chang in chair_spots:
                    _try_place_chair(bm, tracker, chx, chy, chang, z_floor)

                tracker.occupy(tx - hw, tx + hw, ty - hd, ty + hd)
                placed_this = True

        if not placed_this:
            # Try round drinking table
            r = 0.55
            req_r = 0.88
            if tracker.is_free(tx - req_r, tx + req_r, ty - req_r, ty + req_r):
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=r)
                build_prop(bm, 'SCATTER_TABLEWARE', tx, ty, z_tab, 0.0)
                if rng.random() < 0.45:
                    build_prop(bm, 'POTTED_PLANT_SMALL', tx + 0.22, ty + 0.10, z_tab, rng.uniform(0.0, 6.28))
                else:
                    build_prop(bm, 'BOTTLE_CLUSTER', tx + 0.22, ty + 0.10, z_tab, 0.0)

                # 4 wooden chairs around table facing table center (backrests outward)
                for ci in range(4):
                    ca = ci * (math.pi * 0.5)
                    chx = tx + 0.70 * math.cos(ca)
                    chy = ty + 0.70 * math.sin(ca)
                    _try_place_chair(bm, tracker, chx, chy, ca - math.pi * 0.5, z_floor)

                tracker.occupy(tx - 0.90, tx + 0.90, ty - 0.90, ty + 0.90)
                placed_this = True

        if placed_this:
            if first_table_pos is None:
                first_table_pos = (tx, ty)
            placed_tables += 1

    # 4. Ale barrel / crate corner clutter and perimeter seating
    placed_barrels = 0
    for cx in (rm.bounds[0] + 0.45, rm.bounds[1] - 0.45):
        for cy in (rm.bounds[2] + 0.45, rm.bounds[3] - 0.45):
            if placed_barrels >= 3:
                break
            if tracker.is_free(cx - 0.35, cx + 0.35, cy - 0.35, cy + 0.35):
                tracker.occupy(cx - 0.35, cx + 0.35, cy - 0.35, cy + 0.35)
                build_prop(bm, 'BARREL', cx, cy, z_floor, rng.uniform(0.0, 6.28))
                placed_barrels += 1

    # Wall bench along a clear wall
    _try_place_wall_prop(bm, 'BENCH', 1.60, 0.55, tracker, z_floor,
                         candidate_walls=('SOUTH', 'EAST', 'WEST'), length=1.60)

    # 5. Taproom woven rugs framed with dining lounge area (oversized)
    rug_choice = rng.choice(['RUG_SAPPHIRE', 'RUG_FOREST', 'RUG_CRIMSON'])
    rug_x, rug_y = first_table_pos if first_table_pos else (rcx, rcy + 0.20)
    rug_w, rug_l = _area_rug_size(rw, rd, coverage=0.82, max_w=5.40, max_l=6.60,
                                  min_w=3.00, min_l=3.60)
    _lay_rug(bm, tracker, rm, rng, rug_choice, rug_x, rug_y, z_floor, rug_w, rug_l)

    # 5b. Secondary + tertiary seating rugs in roomy taprooms: regular-size
    # area rugs, distinct patterns, spread apart (no tiny bath-mat runners).
    if (rw >= 5.0 or rd >= 5.0) and density >= 0.4:
        sub_rug = 'RUG_CRIMSON' if rug_choice != 'RUG_CRIMSON' else 'RUG_SAPPHIRE'
        s_rx = rcx - rw * 0.28 if rug_x >= rcx else rcx + rw * 0.28
        s_ry = rcy - rd * 0.24
        s_w, s_l = _area_rug_size(rw, rd, coverage=0.46, max_w=3.60, max_l=4.60,
                                  min_w=2.60, min_l=3.40)
        _lay_rug(bm, tracker, rm, rng, sub_rug, s_rx, s_ry, z_floor, s_w, s_l,
                 allow_overlap=False)
    if rw >= 6.5 and rd >= 6.0 and density >= 0.6:
        third = 'RUG_FOREST' if rug_choice != 'RUG_FOREST' else 'RUG_SAPPHIRE'
        _lay_rug(bm, tracker, rm, rng, third,
                 rcx + (rw * 0.24 if rug_x >= rcx else -rw * 0.24),
                 rcy + rd * 0.28, z_floor,
                 min(3.40, max(2.40, rw * 0.32)),
                 min(4.40, max(3.20, rd * 0.30)), allow_overlap=False)

    # 6. Hanging Chandeliers: 2 chandeliers in wide taprooms, 1 central chandelier otherwise
    if rw >= 8.5:
        _place_ceiling_light(bm, tracker, rcx - rw * 0.22, rcy, z_ceil, 'CHANDELIER', radius=0.46)
        _place_ceiling_light(bm, tracker, rcx + rw * 0.22, rcy, z_ceil, 'CHANDELIER', radius=0.46)
    else:
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, 'CHANDELIER', radius=0.46)


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
    z_table = z_floor + 0.992
    rx0, rx1 = tracker.rx0, tracker.rx1
    ry0, ry1 = tracker.ry0, tracker.ry1
    rcx, rcy = (rx0 + rx1) * 0.5, (ry0 + ry1) * 0.5
    rw, rd = rx1 - rx0, ry1 - ry0

    # A real gap between stove and prep table so the table can never sit in
    # front of the stove door/oven.  The old 6 cm gap plus a perpendicular
    # corner placement made the table overlap the stove's working aisle.
    PREP_GAP = 0.22

    def _stove_front_rect(sx, sy, syaw):
        """AABB of the clear aisle directly in front of the stove."""
        fx, fy = math.sin(syaw), -math.cos(syaw)   # stove front direction
        ux, uy = math.cos(syaw), math.sin(syaw)    # along the stove width
        hw = sw * 0.5 + 0.14
        pts = []
        for a in (-hw, hw):
            for d in (sd * 0.5, sd * 0.5 + 0.70):
                pts.append((sx + ux * a + fx * d, sy + uy * a + fy * d))
        return (min(p[0] for p in pts), max(p[0] for p in pts),
                min(p[1] for p in pts), max(p[1] for p in pts))

    def _prep_clear(sx, sy, syaw, tb):
        """True when a prep-table footprint leaves the stove's aisle free."""
        fr = _stove_front_rect(sx, sy, syaw)
        if not (tb[1] <= fr[0] - 0.04 or tb[0] >= fr[1] + 0.04
                or tb[3] <= fr[2] - 0.04 or tb[2] >= fr[3] + 0.04):
            return False
        # ... and keep a small side gap from the stove body as well.
        hx = sw * 0.5 * abs(math.cos(syaw)) + sd * 0.5 * abs(math.sin(syaw)) + 0.06
        hy = sw * 0.5 * abs(math.sin(syaw)) + sd * 0.5 * abs(math.cos(syaw)) + 0.06
        return (tb[1] <= sx - hx or tb[0] >= sx + hx
                or tb[3] <= sy - hy or tb[2] >= sy + hy)

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
                                if not _prep_clear(hx, hy, yaw, tb):
                                    continue
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
    tot_len = sw + pw + PREP_GAP

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
                    s_y = cy_cand - (pw + PREP_GAP) * 0.5 if not swap else cy_cand + (pw + PREP_GAP) * 0.5
                    p_y = cy_cand + (sw + PREP_GAP) * 0.5 if not swap else cy_cand - (sw + PREP_GAP) * 0.5
                    sb = (min(wall_x_stove - sd*0.5, wall_x_stove + sd*0.5) - 0.05,
                          max(wall_x_stove - sd*0.5, wall_x_stove + sd*0.5) + 0.05,
                          s_y - sw * 0.5 - 0.04, s_y + sw * 0.5 + 0.04)
                    pb = (min(wall_x_table - pd*0.5, wall_x_table + pd*0.5) - 0.05,
                          max(wall_x_table - pd*0.5, wall_x_table + pd*0.5) + 0.05,
                          p_y - pw * 0.5 - 0.04, p_y + pw * 0.5 + 0.04)
                    if tracker.is_free(sb[0], sb[1], sb[2], sb[3], check_windows=True) and \
                       tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True) and \
                       _prep_clear(wall_x_stove, s_y, yaw, pb):
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
                    s_x = cx_cand - (pw + PREP_GAP) * 0.5 if not swap else cx_cand + (pw + PREP_GAP) * 0.5
                    p_x = cx_cand + (sw + PREP_GAP) * 0.5 if not swap else cx_cand - (sw + PREP_GAP) * 0.5
                    sb = (s_x - sw * 0.5 - 0.04, s_x + sw * 0.5 + 0.04,
                          min(wall_y_stove - sd*0.5, wall_y_stove + sd*0.5) - 0.05,
                          max(wall_y_stove - sd*0.5, wall_y_stove + sd*0.5) + 0.05)
                    pb = (p_x - pw * 0.5 - 0.04, p_x + pw * 0.5 + 0.04,
                          min(wall_y_table - pd*0.5, wall_y_table + pd*0.5) - 0.05,
                          max(wall_y_table - pd*0.5, wall_y_table + pd*0.5) + 0.05)
                    if tracker.is_free(sb[0], sb[1], sb[2], sb[3], check_windows=True) and \
                       tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True) and \
                       _prep_clear(s_x, wall_y_stove, yaw, pb):
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
           tracker.is_free(pb[0], pb[1], pb[2], pb[3], check_windows=True) and \
           _prep_clear(sx, sy, syaw, pb):
            if tracker.is_near_door(sx, sy) or tracker.is_near_door(px, py):
                continue
            tracker.occupy(sb[0], sb[1], sb[2], sb[3])
            tracker.occupy(pb[0], pb[1], pb[2], pb[3])
            build_prop(bm, 'KITCHEN_STOVE', sx, sy, z_floor, syaw, width=sw, depth=sd, height=sh)
            build_prop(bm, 'INDOOR_TABLE', px, py, z_floor, pyaw, length=pw, width=pd)
            _place_prep_clutter(bm, px, py, z_table, pyaw, rng)
            return ((sx, sy, syaw), (px, py, pyaw))

    # 4. Fallback: Place stove on any available wall, prep table beside it
    placed_stove = _try_place_kitchen_stove(bm, tracker, z_floor, chimney_pos=chimney_pos)
    if placed_stove:
        sx, sy, syaw = placed_stove
        ux, uy = math.cos(syaw), math.sin(syaw)   # along the stove's wall
        dist = sw * 0.5 + pw * 0.5 + PREP_GAP
        # Prefer the side that reads as "left of the stove", then the other
        # side; never the space directly in front of the oven door.
        for sign in (-1.0, 1.0):
            px = sx + sign * dist * ux
            py = sy + sign * dist * uy
            ctw = pd if (0.5 < abs(syaw) < 2.5) else pw
            ctd = pw if (0.5 < abs(syaw) < 2.5) else pd
            pb = (px - ctw * 0.5, px + ctw * 0.5,
                  py - ctd * 0.5, py + ctd * 0.5)
            if tracker.is_free(pb[0], pb[1], pb[2], pb[3]) and \
               _prep_clear(sx, sy, syaw, pb):
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
    z_table = z_floor + 0.992

    # 1. INTEGRATED COOKING WORKSTATION: Stove & Foodprep Table SIDE-BY-SIDE
    workstation = _try_place_kitchen_workstation(bm, tracker, z_floor, rng, chimney_pos=chimney_pos)
    if workstation:
        placed_stove, prep_table_pos = workstation
    else:
        placed_stove = _try_place_kitchen_stove(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)
        if not placed_stove and rm.role != 'TENEMENT_KITCHEN':
            placed_stove = _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _furnish_tenement_parlour(bm, rm, tracker: RoomOccupancyTracker, z_floor: float,
                              z_ceil: float, rng, density: float,
                              chimney_pos: Optional[Any] = None):
    """A light sitting room for the extra walk-through rooms of a big flat.

    Deliberately has no dining table, bookshelf or four-chair set: the flat's
    one living/dining room owns those.  A sofa, coffee table, rug and a corner
    plant keep the room cosy without duplicating the main room's furniture.
    """
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    if rw < 1.2 or rd < 1.2:
        return
    # Soft rug under the seating group, not a second dining set.
    _lay_rug(bm, tracker, rm, rng, rng.choice(['RUG_FOREST', 'RUG_SAPPHIRE']),
             rcx, rcy, z_floor, min(2.60, max(1.30, rw * 0.52)),
             min(2.10, max(1.20, rd * 0.52)), yaw_max=0.04)
    seat = _try_place_wall_prop(
        bm, 'SOFA', 1.90, 0.92, tracker, z_floor,
        candidate_walls=('NORTH', 'SOUTH', 'EAST', 'WEST'),
        length=1.72, check_windows=False)
    if seat is None:
        seat = _try_place_wall_prop(
            bm, 'ARMCHAIR', 0.95, 0.90, tracker, z_floor,
            candidate_walls=('NORTH', 'SOUTH', 'EAST', 'WEST'),
            check_windows=False)
    if seat is not None:
        sx, sy, syaw = seat
        fx, fy = rcx - sx, rcy - sy
        fl = math.hypot(fx, fy) or 1.0
        fx, fy = fx / fl, fy / fl
        tx, ty = sx + fx * 1.15, sy + fy * 1.15
        if (ty - tracker.ry0 > 0.45 and ty < tracker.ry1 - 0.45
                and tx - tracker.rx0 > 0.45 and tx < tracker.rx1 - 0.45
                and not tracker.is_near_door(tx, ty, radius=1.05)
                and tracker.is_free(tx - 0.45, tx + 0.45, ty - 0.45, ty + 0.45, margin=0.08)):
            tracker.occupy(tx - 0.40, tx + 0.40, ty - 0.40, ty + 0.40)
            build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.38)
            build_prop(bm, 'POTTED_PLANT_SMALL', tx, ty, z_floor + 0.99,
                       rng.uniform(0.0, math.pi * 2.0))
    # One corner plant only, never a free-standing planter in the middle.
    _try_place_plant(bm, tracker, z_floor, rng, large=True)
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil,
                         prop_name='CHANDELIER', radius=0.34)


def _furnish_house_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                        rng, density: float, chimney_pos: Optional[Any] = None):
    """Furnishes a cozy living / dining hall with dining table, plush sofa/armchairs, bookshelves, and plants."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.99

    # 1. Warm stone hearth (attaches to chimney if present)
    _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)

    # 2. Central Dining Table with 4 Chairs and Table Clutter (jittered anchor).
    # The table is scaled to the room so a narrow chamber still gets a usable
    # dining set instead of nothing at all: the long side follows the room's
    # long axis and both dimensions shrink to leave room for the chairs.
    usable_w = max(1.20, rw - 0.30)
    usable_d = max(1.20, rd - 0.30)
    if rd >= rw * 1.25:
        table_yaw = math.pi * 0.5
        tw = min(1.15, max(0.80, usable_w - 1.50))   # across the room
        td = min(2.10, max(1.30, usable_d - 1.55))   # along the room
    else:
        table_yaw = 0.0
        tw = min(2.10, max(1.30, usable_w - 1.55))   # along the room
        td = min(1.15, max(0.80, usable_d - 1.50))   # across the room
    dtx = rcx + _jit(rng, 0.22)
    dty = rcy + _jit(rng, 0.22)
    z_table = z_floor + 0.992
    # Try the room centre first, then slide the set along the long axis so a
    # doorway corridor or a stair flight can never starve the room of its
    # dining set entirely.
    if rd >= rw * 1.25:
        _cands = [(dtx, dty), (dtx, dty - rd * 0.24), (dtx, dty + rd * 0.24)]
    else:
        _cands = [(dtx, dty), (dtx - rw * 0.24, dty), (dtx + rw * 0.24, dty)]
    _table_ok = False
    for (cx_t, cy_t) in _cands:
        if tracker.is_free(cx_t - tw * 0.5 - 0.40, cx_t + tw * 0.5 + 0.40,
                           cy_t - td * 0.5 - 0.40, cy_t + td * 0.5 + 0.40):
            dtx, dty = cx_t, cy_t
            _table_ok = True
            break
    if _table_ok:
        build_prop(bm, 'INDOOR_TABLE', dtx, dty, z_floor, table_yaw, length=tw, width=td)
        build_prop(bm, 'SCATTER_TABLEWARE', dtx - 0.35, dty, z_table, table_yaw)
        if rng.random() < 0.45:
            build_prop(bm, 'POTTED_PLANT_SMALL', dtx + 0.45, dty, z_table, rng.uniform(0.0, 6.28))
        else:
            build_prop(bm, 'BOTTLE_CLUSTER', dtx + 0.45, dty, z_table, table_yaw)
        # 4 Chairs around table facing inward towards center
        chair_positions = [
            (dtx, dty - (td * 0.5 + 0.38), math.pi),
            (dtx, dty + (td * 0.5 + 0.38), 0.0),
            (dtx - (tw * 0.5 + 0.38), dty, math.pi * 0.5),
            (dtx + (tw * 0.5 + 0.38), dty, -math.pi * 0.5),
        ]
        for chx, chy, chang in chair_positions:
            _try_place_chair(bm, tracker, chx, chy, chang, z_floor)
        tracker.occupy(dtx - tw * 0.5 - 0.40, dtx + tw * 0.5 + 0.40, dty - td * 0.5 - 0.40, dty + td * 0.5 + 0.40)

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
                    if tracker.is_free(ax - 0.65, ax + 0.65, ay - 0.60, ay + 0.60, margin=0.12):
                        tracker.occupy(ax - 0.60, ax + 0.60, ay - 0.55, ay + 0.55)
                        build_prop(bm, 'ARMCHAIR', ax, ay, z_floor, ayaw, fabric_mat=_sofa_fabric(rng))
                        lounge = (ax, ay, ayaw)
                        break

        # Coffee table + a second armchair facing the lounge, so a living room
        # reads as a cozy, beautifully furnished parlor.
        if lounge is not None and min(rw, rd) >= 3.6:
            lx, ly = lounge[0], lounge[1]
            fx, fy = rcx - lx, rcy - ly
            fl = math.hypot(fx, fy) or 1.0
            fx, fy = fx / fl, fy / fl
            coff = (lx + fx * (1.15 if sofa_placed else 1.00),
                    ly + fy * (1.15 if sofa_placed else 1.00))
            if (not tracker.is_near_door(coff[0], coff[1], radius=1.20) and
                tracker.is_free(coff[0] - 0.45, coff[0] + 0.45, coff[1] - 0.45, coff[1] + 0.45, margin=0.08)):
                tracker.occupy(coff[0] - 0.40, coff[0] + 0.40, coff[1] - 0.40, coff[1] + 0.40)
                build_prop(bm, 'ROUND_TABLE', coff[0], coff[1], z_floor, 0.0, radius=0.38)
                build_prop(bm, 'POTTED_PLANT_SMALL', coff[0], coff[1], z_floor + 0.99, rng.uniform(0, 6.28))
            # Second armchair across the coffee table, facing the first seat.
            ax = lx + fx * 2.10
            ay = ly + fy * 2.10
            a_yaw = math.atan2(-fx, fy)
            if (not tracker.is_near_door(ax, ay, radius=1.20) and
                tracker.is_free(ax - 0.55, ax + 0.55, ay - 0.50, ay + 0.50, margin=0.08)):
                tracker.occupy(ax - 0.50, ax + 0.50, ay - 0.45, ay + 0.45)
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
        run_clear = not any(tracker.is_near_door(rcx, y, radius=1.80) for y in (run_y - run_l * 0.5, run_y, run_y + run_l * 0.5))
        if run_clear:
            _lay_rug(bm, tracker, rm, rng, sub_choice, rcx, run_y, z_floor, run_w, run_l,
                     allow_overlap=False)

    # 6. Hanging Chandelier
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, prop_name='CHANDELIER', radius=0.42)


def _furnish_great_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                        rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Furnishes a civic Great Hall / Council Chamber with council table, magistrate chairs, and banners."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Warm stone hearth if chimney exists
    _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)

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
    _try_place_wall_prop(bm, 'BENCH', 1.60, 0.58, tracker, z_floor,
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, prop_name='CHANDELIER', radius=0.52)


def _wall_clears_doorways(wall_axis, wall_pos, banner_pos, banner_w, doorways, min_margin=0.80):
    """Returns True if a banner at banner_pos along the given wall does not overlap or block any doorway."""
    for dw in (doorways or []):
        dw_axis = str(dw.get('axis', 'X')).upper()
        if dw_axis == str(wall_axis).upper():
            dw_x = dw.get('x', 0.0)
            dw_y = dw.get('y', 0.0)
            dw_w = dw.get('w', 1.2)
            if dw_axis == 'Y':
                if abs(dw_x - wall_pos) < 0.60:
                    if abs(banner_pos - dw_y) < (banner_w * 0.5 + dw_w * 0.5 + min_margin):
                        return False
            else:
                if abs(dw_y - wall_pos) < 0.60:
                    if abs(banner_pos - dw_x) < (banner_w * 0.5 + dw_w * 0.5 + min_margin):
                        return False
    return True


def _furnish_throne_room(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                         rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Grand Castle Throne Room: elevated stepped dais with frontal stairs, royal throne,
    ceremonial crimson carpet aisle, flanking guard braziers, heraldic banners,
    noble benches, weapon racks and magnificent soaring chandeliers."""
    from .banner import build_wall_banner

    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Warm stone hearth on side wall if chimney exists
    _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)

    # 2. Place Royal Throne on elevated Dais at the head wall
    # The artist Throne.fbx has back/banners at Y = +0.8 to +1.0 and red carpet extending forward to Y = -7.4.
    throne_y = rm.bounds[3] - 1.00
    throne_x = rcx
    throne_ang = 0.0  # In local coords, Throne.fbx faces -Y (South) toward entrance doors
    # The throne asset includes the stone dais and red carpet runner extending forward ~7.4m
    tracker.occupy(throne_x - 1.80, throne_x + 1.80, throne_y - 7.50, rm.bounds[3])
    build_prop(bm, 'ROYAL_THRONE', throne_x, throne_y, z_floor, throne_ang, dais=True)

    # 3. Heraldic wall banners along the gallery side walls
    # (Banners MUST NEVER block doorways or passages)
    if rd >= 6.0:
        ban_w = 0.90
        cand_y_list = [rcy - 2.80, rcy + 2.80, rcy - 3.50, rcy + 3.50]
        # West side wall
        for cy in cand_y_list:
            if rm.bounds[2] + 1.0 <= cy <= rm.bounds[3] - 1.0:
                if _wall_clears_doorways('Y', rm.bounds[0], cy, ban_w, rm.doorways, min_margin=0.80):
                    build_wall_banner(bm, rm.bounds[0] + 0.05, cy, z_floor,
                                      ang=0.0, width=ban_w, length=2.20, hang_h=3.20)
                    break
        # East side wall
        for cy in cand_y_list:
            if rm.bounds[2] + 1.0 <= cy <= rm.bounds[3] - 1.0:
                if _wall_clears_doorways('Y', rm.bounds[1], cy, ban_w, rm.doorways, min_margin=0.80):
                    build_wall_banner(bm, rm.bounds[1] - 0.05, cy, z_floor,
                                      ang=math.pi, width=ban_w, length=2.20, hang_h=3.20)
                    break

    # 4. Note: Red carpet runner down the center aisle is already integrated into the new Throne.fbx!
    # (Redundant procedural red carpet and underlying rugs removed as requested)
    tracker.rug_count = 1
    tracker.no_rugs = True

    # 5. Courtier round tables with stools along flanking walls
    # (Placed neatly along the West and East walls, keeping the central aisle 100% open)
    num_table_sets = 4 if rd >= 11.0 else (2 if rd >= 6.5 else 1)
    cand_y_targets = [rcy - rd * 0.28, rcy + rd * 0.28, rcy - rd * 0.38, rcy + rd * 0.38]
    cand_walls = ['WEST', 'EAST']
    placed_tables = 0
    for target_y in cand_y_targets:
        if placed_tables >= num_table_sets:
            break
        wall_order = cand_walls if (placed_tables % 2 == 0) else list(reversed(cand_walls))
        for wall in wall_order:
            res = _try_place_wall_table_nook(bm, tracker, z_floor, rng,
                                             candidate_walls=(wall,),
                                             target_pos=target_y)
            if res is not None:
                placed_tables += 1
                break

    # 7. Courtier / noble benches along side walls
    _try_place_wall_prop(bm, 'BENCH', 1.80, 0.58, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST'), length=1.75)
    _try_place_wall_prop(bm, 'BENCH', 1.80, 0.58, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST'), length=1.75)

    # 8. Flanking weapon racks / ceremonial guard halberds
    _try_place_wall_prop(bm, 'WEAPON_RACK', 1.20, 0.55, tracker, z_floor,
                         candidate_walls=('WEST', 'EAST', 'SOUTH'))

    # 9. Grand chandeliers overhead: centralized above the open mezzanine void
    ch_drop = max(0.0, (z_ceil - z_floor) - 3.40) if (z_ceil - z_floor) > 4.5 else 0.0
    from ..interior import compute_mezzanine_void
    v_rect = compute_mezzanine_void(rm.bounds, min_rim=2.00, doorways=rm.doorways)
    if v_rect is not None:
        vx0, vx1, vy0, vy1 = v_rect
        vcx = (vx0 + vx1) * 0.5
        vcy = (vy0 + vy1) * 0.5
        vd = vy1 - vy0
        spacing = min(2.8, max(1.5, vd * 0.24))
        build_prop(bm, 'CHANDELIER', vcx, vcy - spacing, z_ceil, 0.0, radius=0.60, chain_drop=ch_drop)
        build_prop(bm, 'CHANDELIER', vcx, vcy + spacing, z_ceil, 0.0, radius=0.60, chain_drop=ch_drop)
    else:
        spacing = min(2.8, max(1.5, rd * 0.18))
        c_mid_y = min(rcy, (rm.bounds[2] + throne_y - 4.0) * 0.5)
        build_prop(bm, 'CHANDELIER', rcx, c_mid_y - spacing, z_ceil, 0.0, radius=0.60, chain_drop=ch_drop)
        build_prop(bm, 'CHANDELIER', rcx, c_mid_y + spacing, z_ceil, 0.0, radius=0.60, chain_drop=ch_drop)


def _furnish_mezzanine_gallery(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                               rng, density: float):
    """Walkable upper gallery rim overlooking a double-height hall below.
    All furnishings sit against outer walls; the center void is kept open.
    STRICT WALKABILITY: Every placed prop MUST leave at least 2.0m of clear,
    unobstructed walking aisle between the prop and the gallery void railing.
    Props are NEVER placed if the walkway rim is under 2.55m wide, and NEVER
    placed over the floor void."""
    from .banner import build_wall_banner

    # 1. Heraldic wall banners on perimeter gallery walls (hang high on walls, 100% clear of walkways and doors)
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    all_doorways = list(rm.doorways or []) + list(getattr(tracker, 'doorways', []) or [])
    for sgn in (-1.0, 1.0):
        bx = rcx + sgn * 2.5
        if rm.bounds[0] + 0.6 <= bx <= rm.bounds[1] - 0.6:
            if _wall_clears_doorways('X', rm.bounds[3], bx, 0.85, all_doorways, min_margin=0.80):
                build_wall_banner(bm, bx, rm.bounds[3] - 0.05, z_floor,
                                  ang=-math.pi * 0.5, width=0.85, length=2.00, hang_h=2.40)

    _fvoid = getattr(rm, 'floor_void', None) or getattr(tracker, 'floor_void', None)
    if _fvoid is None:
        return

    vx0, vx1, vy0, vy1 = _fvoid
    rx0, rx1, ry0, ry1 = rm.bounds
    min_walk = 2.00

    # Determine which walls have sufficient rim width to hold furniture while preserving >= 2.0m aisle:
    # Bench depth ~0.45m + 0.10m margin = 0.55m. Rim must be >= 2.55m
    bench_walls = []
    if (ry1 - vy1) >= min_walk + 0.55:
        bench_walls.append('NORTH')
    if (vy0 - ry0) >= min_walk + 0.55:
        bench_walls.append('SOUTH')
    if (rx1 - vx1) >= min_walk + 0.55:
        bench_walls.append('EAST')
    if (vx0 - rx0) >= min_walk + 0.55:
        bench_walls.append('WEST')

    if bench_walls:
        _try_place_wall_prop(bm, 'BENCH', 1.60, 0.58, tracker, z_floor,
                             candidate_walls=tuple(bench_walls), length=1.50)

    # Bookcase / display cabinet requires deeper rim >= 2.65m
    cab_walls = []
    if (ry1 - vy1) >= min_walk + 0.65:
        cab_walls.append('NORTH')
    if (vy0 - ry0) >= min_walk + 0.65:
        cab_walls.append('SOUTH')
    if (rx1 - vx1) >= min_walk + 0.65:
        cab_walls.append('EAST')
    if (vx0 - rx0) >= min_walk + 0.65:
        cab_walls.append('WEST')

    if cab_walls:
        _try_place_wall_prop(bm, 'BOOKCASE_LARGE', 1.20, 0.45, tracker, z_floor,
                             candidate_walls=tuple(cab_walls))


def _furnish_banquet_hall(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                          rng, density: float, chimney_pos: Optional[Tuple[float, float]] = None):
    """Grand manor banquet hall: one long feast table with chairs all around,
    festive tableware, hearth, sideboard and ceremonial rugs."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    ix_lo, ix_hi, iy_lo, iy_hi = rm.bounds
    z_table = z_floor + 0.992

    # 1. Warm stone hearth if chimney exists
    _try_place_hearth(bm, tracker, z_floor, z_ceil=z_ceil, chimney_pos=chimney_pos)

    # 2. Long feast table along the room's long axis with chairs around all sides.
    # The table is sized to the room (a narrow hall gets a shorter board) and
    # slides along the long axis until it finds clear floor, so the banquet
    # hall always ends up with its long table and a full ring of chairs.
    along_y = rd >= rw
    usable_w = max(1.20, rw - 0.30)
    usable_d = max(1.20, rd - 0.30)
    if along_y:
        tw, td, yaw = 1.05, min(4.60, max(1.60, usable_d - 1.40)), math.pi * 0.5
    else:
        tw, td, yaw = min(4.60, max(1.60, usable_w - 1.40)), 1.05, 0.0
    _jit_x = _jit(rng, 0.15)
    _jit_y = _jit(rng, 0.15)
    if along_y:
        _cands = [(rcx + _jit_x, rcy + _jit_y),
                  (rcx + _jit_x, rcy - rd * 0.20),
                  (rcx + _jit_x, rcy + rd * 0.20),
                  (rcx + _jit_x, rcy - rd * 0.34),
                  (rcx + _jit_x, rcy + rd * 0.34)]
    else:
        _cands = [(rcx + _jit_x, rcy + _jit_y),
                  (rcx - rw * 0.20, rcy + _jit_y),
                  (rcx + rw * 0.20, rcy + _jit_y),
                  (rcx - rw * 0.34, rcy + _jit_y),
                  (rcx + rw * 0.34, rcy + _jit_y)]
    hw, hd = (0.55, td * 0.5 + 0.40) if along_y else (tw * 0.5 + 0.40, 0.95)
    tx = ty = None
    for (cx_t, cy_t) in _cands:
        if tracker.is_free(cx_t - hw, cx_t + hw, cy_t - hd, cy_t + hd):
            tx, ty = cx_t, cy_t
            break
    if tx is None:
        tx, ty = rcx, rcy
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
                return
            # Chair blocked by a doorway corridor or other prop: nudge it to find
            # a free spot so the table never reads half-empty.
            for push in (0.18, 0.36, 0.54, 0.72):
                for dx, dy in ((push, 0.0), (-push, 0.0), (0.0, push), (0.0, -push),
                               (push * 0.70, push * 0.70), (-push * 0.70, -push * 0.70)):
                    nx, ny = cx + dx, cy + dy
                    if tracker.is_free(nx - 0.30, nx + 0.30, ny - 0.30, ny + 0.30):
                        tracker.occupy(nx - 0.30, nx + 0.30, ny - 0.30, ny + 0.30)
                        build_prop(bm, 'CHAIR', nx, ny, z_floor, yaw, seat_h=h)
                        return

        def _high_seat(cx, cy, yaw, _ay, _alen, _tx, _ty):
            """A taller chair at the head of the table, nudged clear if busy."""
            for _push in (0.0, 0.26, 0.52, 0.78, 1.04):
                _ox = cx + (_push * (1.0 if yaw >= 0 else -1.0) if not _ay else 0.0)
                _oy = cy + (0.0 if not _ay else (_push * (1.0 if yaw > 0 else -1.0)))
                if tracker.is_free(_ox - 0.34, _ox + 0.34, _oy - 0.34, _oy + 0.34):
                    tracker.occupy(_ox - 0.34, _ox + 0.34, _oy - 0.34, _oy + 0.34)
                    build_prop(bm, 'CHAIR', _ox, _oy, z_floor, yaw, seat_h=0.62)
                    return

        long_len = max(tw, td)
        n_side = max(3, int(long_len / 0.78))
        step = long_len / n_side
        for ci in range(n_side):
            off = -long_len * 0.5 + (ci + 0.5) * step
            if along_y:
                _seat(tx - 0.85, ty + off, math.pi * 0.5)
                _seat(tx + 0.85, ty + off, -math.pi * 0.5)
            else:
                _seat(tx + off, ty - 0.85, math.pi)
                _seat(tx + off, ty + 0.85, 0.0)
        # High seats at both ends of the table. The head of the table gets a
        # taller chair (and is retried further out if the first slot is busy),
        # so the long table always reads as a proper feast with a seat at each
        # end.
        if along_y:
            _high_seat(tx, ty - (long_len * 0.5 + 0.42), math.pi, along_y, long_len, tx, ty)
            _high_seat(tx, ty + (long_len * 0.5 + 0.42), 0.0, along_y, long_len, tx, ty)
        else:
            _high_seat(tx - (long_len * 0.5 + 0.42), ty, math.pi * 0.5, along_y, long_len, tx, ty)
            _high_seat(tx + (long_len * 0.5 + 0.42), ty, -math.pi * 0.5, along_y, long_len, tx, ty)
        tracker.occupy(tx - hw, tx + hw, ty - hd, ty + hd)

        # Feasting clutter spread over the whole board: tankards, platters,
        # bottles and candles down the centre line plus a couple of clusters
        # at the ends, so the table never looks like a bare plank.
        _z_tab = z_table
        for ci in range(n_side):
            off = -long_len * 0.5 + (ci + 0.5) * step
            if along_y:
                build_prop(bm, 'SCATTER_TABLEWARE', tx, ty + off, _z_tab, yaw)
                if ci % 2 == 0:
                    build_prop(bm, 'BOTTLE_CLUSTER', tx + _jit(rng, 0.12), ty + off, _z_tab, yaw)
            else:
                build_prop(bm, 'SCATTER_TABLEWARE', tx + off, ty, _z_tab, yaw)
                if ci % 2 == 0:
                    build_prop(bm, 'BOTTLE_CLUSTER', tx + off, ty + _jit(rng, 0.12), _z_tab, yaw)
        if rng.random() < 0.7:
            build_prop(bm, 'BOTTLE_CLUSTER', tx + _jit(rng, 0.20), ty + _jit(rng, 0.20), _z_tab, yaw)
        if rng.random() < 0.6:
            build_prop(bm, 'POTTED_PLANT_SMALL', tx + _jit(rng, 0.30), ty + _jit(rng, 0.30), _z_tab,
                       rng.uniform(0.0, 6.28))

    # 3. Sideboard with bottles against a free wall.
    sideboard = _try_place_wall_prop(bm, 'INDOOR_TABLE', 1.40, 0.60, tracker, z_floor,
                                     candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'),
                                     length=1.40)
    if sideboard is not None:
        build_prop(bm, 'BOTTLE_CLUSTER', sideboard[0], sideboard[1], z_table, sideboard[2])

    # 4. Perimeter dressing so the walls of the hall are not bare: benches
    #    along both long walls, chests, a bookcase and a couple of standing
    #    urns/plants in the corners.
    for _w in ('WEST', 'EAST', 'SOUTH', 'NORTH'):
        _try_place_wall_prop(bm, 'BENCH', 1.70, 0.58, tracker, z_floor,
                             candidate_walls=(_w,), length=1.70)
    for _w in ('WEST', 'EAST', 'SOUTH', 'NORTH'):
        _try_place_wall_prop(bm, 'CHEST', 1.05, 0.55, tracker, z_floor,
                             candidate_walls=(_w,))
    for _w in ('WEST', 'EAST', 'SOUTH', 'NORTH'):
        _try_place_wall_prop(bm, 'BOOKSHELF', 1.25, 0.38, tracker, z_floor,
                             candidate_walls=(_w,))
    # Corner urns / planters break up the empty wall stretches.
    for _cx, _cy in ((rm.bounds[0] + 0.75, rm.bounds[2] + 0.75),
                     (rm.bounds[1] - 0.75, rm.bounds[2] + 0.75),
                     (rm.bounds[0] + 0.75, rm.bounds[3] - 0.75),
                     (rm.bounds[1] - 0.75, rm.bounds[3] - 0.75)):
        # Reserve the full leaf spread (not just the urn) and keep clear of portals.
        if tracker.is_near_door(_cx, _cy, radius=1.0):
            continue
        if tracker.is_free(_cx - 0.55, _cx + 0.55, _cy - 0.55, _cy + 0.55):
            tracker.occupy(_cx - 0.55, _cx + 0.55, _cy - 0.55, _cy + 0.55)
            build_prop(bm, 'POTTED_PLANT_LARGE', _cx, _cy, z_floor, rng.uniform(0.0, 6.28))

    # 5. Ceremonial runner under the feast table.
    run_w = min(3.0, max(1.8, min(rw, rd) * 0.55))
    run_l = min(9.0, max(3.4, max(rw, rd) * 0.80))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', tx, ty, z_floor, run_w, run_l, yaw_max=0.05)

    # 6. Grand chandelier over the table.
    _place_ceiling_light(bm, tracker, tx, ty, z_ceil, prop_name='CHANDELIER', radius=0.52)


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

    is_military = getattr(tracker, 'archetype', '') in ('KNIGHTS_MANOR', 'BARRACKS', 'INFANTRY_BARRACKS', 'ARMORY')

    if is_military:
        # Military / knight entrance: weapon racks, sturdy benches, equipment chests (never beds)
        _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
        _try_place_wall_prop(bm, 'BENCH', 1.60, 0.58, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'), length=1.6)
        _try_place_wall_prop(bm, 'CHEST', 0.95, 0.55, tracker, z_floor,
                             candidate_walls=('WEST', 'EAST', 'SOUTH', 'NORTH'))
        if min(rw, rd) >= 4.0:
            _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                                 candidate_walls=('WEST', 'EAST', 'SOUTH', 'NORTH'))
    else:
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
            _try_place_wall_prop(bm, 'BENCH', 1.60, 0.58, tracker, z_floor,
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
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, prop_name='CHANDELIER', radius=0.48)
    else:
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
        _try_place_wall_prop(bm, 'BENCH', 1.20, 0.58, tracker, z_floor,
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    is_warehouse = (arch in ('WAREHOUSE', 'BUILDER'))
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
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
                   location=(wx + rng.uniform(-0.15, 0.15), wy + rng.uniform(-0.08, 0.08), z_floor + 0.98 + 0.11),
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)
    if rw >= 8.0:
        _place_ceiling_light(bm, tracker, rcx - rw * 0.28, rcy, z_ceil)
        _place_ceiling_light(bm, tracker, rcx + rw * 0.28, rcy, z_ceil)
    elif rd >= 8.0:
        _place_ceiling_light(bm, tracker, rcx, rcy - rd * 0.28, z_ceil)
        _place_ceiling_light(bm, tracker, rcx, rcy + rd * 0.28, z_ceil)


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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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


# Per-good scale jitter: fish and meat vary the most so a stocked surface
# reads hand-laid, bread only a little.
_GOODS_LENGTH_JITTER = {
    'FISH': (0.80, 1.22),
    'MEAT': (0.84, 1.18),
    'MEAT_SMALL': (0.80, 1.24),
    'BREAD_LOAF': (0.90, 1.10),
}

# Goods that must stay neatly aligned (they stack/lay flush), so they get only
# a whisper of yaw jitter.
_ALIGNED_GOODS = {'RING_TRAY', 'GEM_TRAY'}


def _good_base_length(key: str):
    """Registry default ``length`` for goods that carry one, else None."""
    try:
        from .prop_registry import get_spec
        return get_spec(key).defaults.get('length')
    except Exception:
        return None


def _good_length_param(key: str, rng) -> dict:
    """Params dict adding a randomised ``length`` to goods that support it
    (fish/meat/bread) so merchandise looks varied rather than cloned."""
    jit = _GOODS_LENGTH_JITTER.get(key)
    if not jit:
        return {}
    base = _good_base_length(key)
    if not base:
        return {}
    return {'length': base * rng.uniform(*jit)}


def _dress_craft_table(bm, tx: float, ty: float, yaw: float, z_table: float,
                       rng, goods, span: float = None):
    """Lay trade goods along a work-table top with per-item scale and yaw
    variation (lifted a hair so flat goods never z-fight the surface).

    When ``span`` (the table's usable length) is given, the goods list is
    cycled and packed at ~0.30m so the surface looks fully stocked instead of
    holding a single lonely piece; otherwise a single legacy row at 0.45m."""
    if not goods:
        return
    _maxlen = max((_good_base_length(g) or 0.24) for g in goods)
    if span is None:
        n = len(goods)
        spacing = max(0.45, _maxlen + 0.10)
    else:
        spacing = max(0.30, _maxlen + 0.08)
        n = min(12, max(len(goods), int(max(0.0, span - 0.15) / spacing) + 1))
    seq = [goods[i % len(goods)] for i in range(n)]
    for i, g in enumerate(seq):
        off = (i - (n - 1) * 0.5) * spacing
        gx, gy = _table_offset(tx, ty, off, _jit(rng, 0.06), yaw)
        _gyaw = rng.uniform(-0.08, 0.08) if g in _ALIGNED_GOODS else rng.uniform(0.0, 6.28)
        build_prop(bm, g, gx, gy, z_table + 0.012,
                   _gyaw, **_good_length_param(g, rng))


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
    stair_hole = getattr(tracker, 'stair_hole_rect', None)
    for cx, cy in spots:
        if placed >= count:
            break
        # Never block stair landings — barrels/crates on stairs block egress.
        if stair_hole is not None:
            shx0, shx1, shy0, shy1 = stair_hole
            margin = box + 0.45
            if not (cx + box < shx0 - margin or cx - box > shx1 + margin or
                    cy + box < shy0 - margin or cy - box > shy1 + margin):
                continue
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
    z_table = z_floor + 0.99

    for _ti in range(2 if min(rw, rd) >= 3.4 else 1):
        t = _place_craft_table(bm, tracker, z_floor, rng)
        if t is None:
            break
        if _ti == 0:  # kneading table: fresh loaves
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['BREAD_LOAF', 'BREAD_LOAF', 'BREAD_LOAF'], span=1.15)
        else:
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['FOODPREP_CLUTTER', 'BREAD_LOAF', 'BREAD_LOAF'], span=1.15)
        _stool_near(bm, tracker, t[0], t[1], t[2], z_floor, rng)

    # Cooling rack laden with loaves along a free wall (kept off oven wall).
    _try_place_wall_prop(bm, 'BREAD_RACK', 1.50, 0.50, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'SOUTH'))

    _place_goods_row(bm, tracker, z_floor, rng, 'SACK', count=4)  # flour
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'SOUTH'))  # loaf shelves (clear of oven)
    if rng.random() < density:
        _try_place_wall_prop(bm, 'LOG_PILE', 1.15, 0.95, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'NORTH'),
                             length=1.00, radius=0.11, rows=2)  # oven fuel

    rug_w = min(2.60, max(1.60, rw * 0.55))
    rug_l = min(3.40, max(2.00, rd * 0.55))
    _lay_rug(bm, tracker, rm, rng, 'RUG_FOREST', rcx, rcy, z_floor, rug_w, rug_l)
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
                z_table = z_floor + 0.99
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.55)
                build_prop(bm, 'PEWTER_TANKARD', tx - 0.18, ty, z_table, 0.0)
                build_prop(bm, 'PEWTER_TANKARD', tx + 0.18, ty + 0.10, z_table, 0.0)
                build_prop(bm, 'BOTTLE_CLUSTER', tx, ty - 0.22, z_table, 0.0)
                break
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    z_table = z_floor + 0.99

    # Central stump block with cleaver and cuts; a prep table if the block
    # finds no room.
    if _place_floor_prop(bm, tracker, z_floor, rng, 'BUTCHER_BLOCK', 0.38, 0.38) is None:
        t = _place_craft_table(bm, tracker, z_floor, rng)
        if t is not None:
            _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                               ['MEAT', 'MEAT_SMALL'], span=1.15)
    # A prep table laid with cuts either way.
    t = _place_craft_table(bm, tracker, z_floor, rng)
    if t is not None:
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['MEAT', 'MEAT_SMALL', 'MEAT'], span=1.15)
    # Two hanging meat rails along free walls.
    _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.30, 0.35, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))
    _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.10, 0.35, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
    # More cuts laid out on a second table when space allows.
    t2 = _place_craft_table(bm, tracker, z_floor, rng, length=1.20, width=0.75)
    if t2 is not None:
        _dress_craft_table(bm, t2[0], t2[1], t2[2], z_table, rng,
                           ['MEAT_SMALL', 'MEAT_SMALL', 'FOODPREP_CLUTTER'], span=0.95)

    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=3, box=0.40)  # brine
    _place_goods_row(bm, tracker, z_floor, rng, 'SACK', count=2)  # salt
    _try_place_wall_prop(bm, 'MEAT_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))
    _try_place_wall_prop(bm, 'MEAT_RACK', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('NORTH', 'WEST', 'SOUTH'))
    if rng.random() < density:
        _try_place_wall_prop(bm, 'LOG_PILE', 1.15, 0.95, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'),
                             length=1.00, radius=0.11, rows=2)  # smoke fuel
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _furnish_tailor_atelier(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                            rng, density: float):
    """Tailor's atelier: cutting table with cloth stacks, bolt shelves, garment
    wardrobe and a fitting corner."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]
    z_table = z_floor + 0.99

    t = _place_craft_table(bm, tracker, z_floor, rng, length=1.60, width=0.90)
    if t is not None:  # cutting table dressed with folded cloth
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['FOLDED_CLOTH', 'FOLDED_CLOTH'], span=1.30)
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
                build_prop(bm, 'GEM_TRAY', tx, ty, z_floor + 0.99, 0.0)
                break
    # Standing scale in the freest corner, strongbox along a free wall.
    _place_floor_prop(bm, tracker, z_floor, rng, 'BALANCE_SCALE', 0.30, 0.30)
    _try_place_wall_prop(bm, 'STRONGBOX', 0.66, 0.44, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'))

    rug_w = min(2.40, max(1.50, rw * 0.50))
    rug_l = min(3.00, max(1.80, rd * 0.50))
    _lay_rug(bm, tracker, rm, rng, 'RUG_CRIMSON', rcx, rcy, z_floor, rug_w, rug_l)
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    _try_place_wall_prop(bm, 'LOG_PILE', 1.15, 0.95, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'),
                         length=1.00, radius=0.11, rows=2)  # coal
    _place_goods_row(bm, tracker, z_floor, rng, 'CRATE', count=2, box=0.36)  # stock
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    if rng.random() < density:
        _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    _try_place_wall_prop(bm, 'LOG_PILE', 1.25, 0.95, tracker, z_floor,
                         candidate_walls=('SOUTH', 'WEST', 'EAST'),
                         length=1.10, radius=0.12, rows=2)  # timber
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH'))
    if rng.random() < density:  # finished pieces: chair + chest
        _try_place_wall_prop(bm, 'CHAIR', 0.55, 0.55, tracker, z_floor,
                             candidate_walls=('SOUTH', 'EAST', 'WEST'))
        _try_place_wall_prop(bm, 'CHEST', 0.90, 0.50, tracker, z_floor,
                             candidate_walls=('SOUTH', 'WEST', 'EAST'))
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    z_table = z_floor + 0.99

    # Gutting tables laden with the day's catch (lots of fish).
    for _ in range(2 if min(rw, rd) >= 3.4 else 1):
        t = _place_craft_table(bm, tracker, z_floor, rng)
        _span = 1.15
        if t is None:
            # Compact gutting table for the small fishery chambers.
            t = _place_craft_table(bm, tracker, z_floor, rng,
                                   length=0.95, width=0.62)
            _span = 0.72
        if t is None:
            break
        _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                           ['FISH', 'FISH', 'FOODPREP_CLUTTER'], span=_span)
    # A third table of sorted catch when there is room.
    t3 = _place_craft_table(bm, tracker, z_floor, rng, length=1.20, width=0.75)
    if t3 is not None:
        _dress_craft_table(bm, t3[0], t3[1], t3[2], z_table, rng,
                           ['FISH', 'FISH', 'FOODPREP_CLUTTER'], span=0.95)
    # Hanging fish: rails along the walls and curing stringers from the beams
    # (the catch hangs; it is never left loose on the floor). Replaces the old
    # clutter of crates.
    _try_place_wall_prop(bm, 'FISH_DRYING_RACK', 1.60, 0.80, tracker, z_floor,
                         candidate_walls=('NORTH', 'EAST', 'WEST'))
    _try_place_wall_prop(bm, 'FISH_RAIL', 1.30, 0.35, tracker, z_floor,
                         candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
    _try_place_wall_prop(bm, 'FISH_RAIL', 1.10, 0.35, tracker, z_floor,
                         candidate_walls=('WEST', 'SOUTH', 'EAST', 'NORTH'))
    # Curing stringers hung from the beams (three when there is room).
    for _si in range(3):
        _spot = _freest_spot(tracker, rng)
        if _spot is not None and _spot[2] >= 0.20 - 1e-6:
            tracker.occupy(_spot[0] - 0.20, _spot[0] + 0.20,
                           _spot[1] - 0.20, _spot[1] + 0.20)
            build_prop(bm, 'FISH_STRINGER', _spot[0], _spot[1], z_ceil, 0.0)
        else:
            break

    _place_goods_row(bm, tracker, z_floor, rng, 'BARREL', count=2, box=0.40)  # salt
    _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                         candidate_walls=('EAST', 'NORTH', 'WEST'))  # tackle
    if rng.random() < density:
        _place_goods_row(bm, tracker, z_floor, rng, 'CLAY_POT', count=2, box=0.30)
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _furnish_fisher_cottage(bm, rm, tracker: RoomOccupancyTracker, z_floor: float,
                            z_ceil: float, rng, density: float,
                            chimney_pos=None):
    """Fisherman's combined living floor: bed on the RIGHT, kitchen on the LEFT,
    with no wardrobe/bookcase so the small room stays open."""
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    rw = rm.bounds[1] - rm.bounds[0]
    rd = rm.bounds[3] - rm.bounds[2]

    # 1. Bed against the east (right-hand) wall.
    _try_place_bed(bm, tracker, z_floor,
                   length=min(2.30, max(1.90, rd * 0.48)),
                   width=1.25, ignore_west=True)

    # 2. Kitchen along the west (left-hand) wall - one per household, so only
    # on the first upper storey (the ground floor is the fishery workroom).
    if getattr(rm, 'floor_idx', 1) <= 1:
        _try_place_wall_prop(bm, 'KITCHEN_STOVE', 0.95, 0.75, tracker, z_floor,
                             candidate_walls=('WEST', 'NORTH', 'SOUTH'),
                             height=1.05, check_windows=False)
        _try_place_wall_prop(bm, 'SHELF', 1.20, 0.40, tracker, z_floor,
                             candidate_walls=('WEST', 'NORTH', 'SOUTH'),
                             check_windows=False)
        _t = _place_craft_table(bm, tracker, z_floor, rng, length=1.00, width=0.60)
        if _t is not None:
            _dress_craft_table(bm, _t[0], _t[1], _t[2], z_floor + 0.99, rng,
                               ['FOODPREP_CLUTTER'], span=0.80)

    # 3. Small dining/sitting table with two stools at the clear centre.
    for _tx, _ty in ((rcx + rw * 0.12, rcy + rd * 0.20),
                     (rcx - rw * 0.12, rcy - rd * 0.20),
                     (rcx, rcy)):
        if tracker.is_free(_tx - 0.62, _tx + 0.62, _ty - 0.62, _ty + 0.62):
            tracker.occupy(_tx - 0.62, _tx + 0.62, _ty - 0.62, _ty + 0.62)
            build_prop(bm, 'ROUND_TABLE', _tx, _ty, z_floor, 0.0, radius=0.50)
            for _k in (0, 1):
                _sx = _tx + (0.92 if _k == 0 else -0.92)
                if tracker.is_free(_sx - 0.22, _sx + 0.22, _ty - 0.22, _ty + 0.22):
                    tracker.occupy(_sx - 0.22, _sx + 0.22, _ty - 0.22, _ty + 0.22)
                    build_prop(bm, 'STOOL', _sx, _ty, z_floor, 0.0)
            break

    _rug = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
    _lay_rug(bm, tracker, rm, rng, _rug, rcx, rcy, z_floor,
             min(3.40, max(2.20, rw * 0.55)),
             min(4.20, max(2.80, rd * 0.55)))
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _dress_shop_for_trade(bm, tracker: RoomOccupancyTracker, z_floor: float,
                          rng, arch: str) -> None:
    """Best-effort trade counter dressing in an artisan STORE: the shop shows
    what the workshop below makes."""
    rcx = (tracker.rx0 + tracker.rx1) * 0.5
    rcy = (tracker.ry0 + tracker.ry1) * 0.5
    z_table = z_floor + 0.99
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
        'BAKERY': ['BREAD_LOAF', 'BREAD_LOAF', 'BREAD_LOAF'],
        'BUTCHER': ['MEAT', 'MEAT_SMALL', 'MEAT'],
        'FISHERMAN': ['FISH', 'FISH', 'FISH', 'FOODPREP_CLUTTER'],
        'JEWELER': ['RING_TRAY', 'GEM_TRAY'],
        'BREWERY': ['PEWTER_TANKARD', 'PEWTER_TANKARD', 'BOTTLE_CLUSTER'],
        'HUNTER': ['CLEAVER', 'MEAT', 'MEAT_SMALL'],
    }.get(arch)
    # Trade showpieces that do not fit on the table.
    if arch == 'BAKERY':
        _try_place_wall_prop(bm, 'BREAD_RACK', 1.00, 0.50, tracker, z_floor,
                             candidate_walls=('WEST', 'NORTH', 'EAST'))
    elif arch == 'BREWERY':
        # A case of drinks: prefer the counter, then a wall, then a corner —
        # never randomly on the open floor.
        _cc = getattr(tracker, 'shop_counter', None)
        _done = False
        if _cc is not None:
            _ca, _sa = math.cos(_cc['yaw']), math.sin(_cc['yaw'])
            for _off in (0.42, -0.42, 0.0):
                _bx = _cc['cx'] + _ca * _off
                _by = _cc['cy'] + _sa * _off
                if tracker.is_free(_bx - 0.26, _bx + 0.26, _by - 0.24, _by + 0.24):
                    tracker.occupy(_bx - 0.26, _bx + 0.26, _by - 0.24, _by + 0.24)
                    build_prop(bm, 'BOTTLE_CRATE', _bx, _by, _cc['top_z'], _cc['yaw'])
                    _done = True
                    break
        if not _done:
            _done = _try_place_wall_prop(bm, 'BOTTLE_CRATE', 0.52, 0.52, tracker,
                                         z_floor, candidate_walls=('EAST', 'WEST', 'SOUTH', 'NORTH')) is not None
        if not _done:
            for _cx2, _cy2 in ((rm.bounds[0] + 0.35, rm.bounds[2] + 0.35),
                               (rm.bounds[1] - 0.35, rm.bounds[2] + 0.35),
                               (rm.bounds[0] + 0.35, rm.bounds[3] - 0.35),
                               (rm.bounds[1] - 0.35, rm.bounds[3] - 0.35)):
                if tracker.is_free(_cx2 - 0.28, _cx2 + 0.28, _cy2 - 0.28, _cy2 + 0.28):
                    tracker.occupy(_cx2 - 0.28, _cx2 + 0.28, _cy2 - 0.28, _cy2 + 0.28)
                    build_prop(bm, 'BOTTLE_CRATE', _cx2, _cy2, z_floor,
                               rng.uniform(0.0, 6.28))
                    break
    elif arch == 'BUTCHER':
        _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.00, 0.35, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
    elif arch == 'TAILOR':
        _place_corner_prop(bm, tracker, z_floor, rng, 'DRESS_FORM', 0.30, 0.30)
        _try_place_wall_prop(bm, 'CLOTH_BOLT_BIN', 0.60, 0.48, tracker, z_floor,
                             candidate_walls=('WEST', 'EAST', 'NORTH'))
    elif arch == 'JEWELER':
        _lay_out_jeweler_counter(bm, tracker, z_floor, rng)
    elif arch == 'HUNTER':
        _try_place_wall_prop(bm, 'WEAPON_RACK', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
        # Game cutting block with Cleaver.fbx and fresh meat cuts
        _try_place_wall_prop(bm, 'BUTCHER_BLOCK', 0.85, 0.85, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH', 'SOUTH'))
        # Hanging game cuts on wall rail
        _try_place_wall_prop(bm, 'SAUSAGE_STRING', 1.00, 0.35, tracker, z_floor,
                             candidate_walls=('NORTH', 'EAST', 'WEST'))
    elif arch in ('TOOLSMITH', 'BLACKSMITH'):
        # The artist's smith tools are too large for the stepped display, so
        # they hang on dedicated wall tool racks instead — several around the
        # shop so it reads well stocked.
        for _walls in (('EAST', 'WEST', 'NORTH'),
                       ('WEST', 'NORTH', 'EAST', 'SOUTH'),
                       ('NORTH', 'EAST', 'SOUTH', 'WEST'),
                       ('SOUTH', 'WEST', 'EAST', 'NORTH')):
            _try_place_wall_prop(bm, 'SMITH_TOOL_RACK', 1.25, 0.30, tracker,
                                 z_floor, candidate_walls=_walls,
                                 ignore_stair=True)
    # Stepped market display: normally placed earlier by _furnish_shop (so it
    # wins a good wall nook); this call is a guarded no-op then.
    _place_market_display(bm, tracker, z_floor, rng, arch)
    # The fishmonger's goods live on the display case, not a generic table.
    if not table_goods or arch == 'FISHERMAN':
        return
    is_round = (arch == 'BREWERY')
    for tx, ty in ((rcx, rcy), (rcx - 1.0, rcy), (rcx + 1.0, rcy),
                   (rcx, rcy - 1.0), (rcx, rcy + 1.0)):
        if is_round:
            if tracker.is_free(tx - 0.70, tx + 0.70, ty - 0.70, ty + 0.70):
                tracker.occupy(tx - 0.70, tx + 0.70, ty - 0.70, ty + 0.70)
                build_prop(bm, 'ROUND_TABLE', tx, ty, z_floor, 0.0, radius=0.55)
                _dress_craft_table(bm, tx, ty, 0.0, z_table, rng, table_goods,
                                   span=0.85)
                return
        else:
            t = _place_craft_table(bm, tracker, z_floor, rng)
            if t is not None:
                _dress_craft_table(bm, t[0], t[1], t[2], z_table, rng,
                                   table_goods, span=1.15)
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
    # A neat row of padded trays along the counter, plant at one end.
    _ca, _sa = math.cos(cc['yaw']), math.sin(cc['yaw'])
    for _off, _key in ((-0.34, 'RING_TRAY'), (0.06, 'GEM_TRAY')):
        build_prop(bm, _key, cc['cx'] + _ca * _off, cc['cy'] + _sa * _off,
                   cc['top_z'], cc['yaw'])
    _ex = cc['cx'] + _ca * (cc['length'] * 0.5 - 0.20)
    _ey = cc['cy'] + _sa * (cc['length'] * 0.5 - 0.20)
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
        'BAKERY': [['BREAD_LOAF', 'BREAD_LOAF', 'BREAD_LOAF'],
                   ['BREAD_LOAF', 'BREAD_LOAF', 'BREAD_LOAF'],
                   ['BREAD_LOAF', 'BREAD_LOAF', 'BREAD_LOAF']],
        'BREWERY': [['BOTTLE', 'BOTTLE', 'BOTTLE'],
                    ['PEWTER_TANKARD', 'PEWTER_TANKARD', 'PEWTER_TANKARD'],
                    ['BOTTLE_CLUSTER', 'BOTTLE', 'BOTTLE']],
        'BUTCHER': [['MEAT', 'MEAT_SMALL', 'MEAT'],
                    ['MEAT_SMALL', 'MEAT', 'MEAT_SMALL'],
                    ['MEAT', 'MEAT', 'MEAT_SMALL']],
        'TAILOR': [['FOLDED_CLOTH', 'FOLDED_CLOTH', 'FOLDED_CLOTH'],
                   ['FOLDED_CLOTH', 'FOLDED_CLOTH', 'FOLDED_CLOTH'],
                   ['BOOK_PILE_SMALL', 'FOLDED_CLOTH', 'FOLDED_CLOTH']],
        'JEWELER': [['RING_TRAY'], ['GEM_TRAY'], ['RING_TRAY']],
        # Smith tools are too large for the stepped display; they go on a
        # dedicated SMITH_TOOL_RACK instead (see _dress_shop_for_trade).
        'FURNITURE_MAKER': [['WOODEN_BOWL', 'WOODEN_BOWL', 'WOODEN_BOWL'],
                            ['WOODEN_BOWL', 'WOODEN_BOWL', 'WOODEN_BOWL'],
                            ['WOODEN_BOWL', 'CLAY_POT', 'WOODEN_BOWL']],
        'FISHERMAN': [['FISH', 'FISH', 'FISH'],
                      ['FISH', 'FISH', 'FISH'],
                      ['FISH', 'FISH', 'FISH', 'FISH']],
        'HUNTER': [['TARGET_STRAW_SMALL', 'MEAT', 'TARGET_STRAW_SMALL'],
                   ['MEAT_SMALL', 'CLEAVER', 'MEAT'],
                   ['PEWTER_TANKARD', 'MEAT_SMALL', 'PEWTER_TANKARD']],
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

    # The space under a ceiling stair-hole is walkable (solid floor below), so
    # the display may be tucked there when every clear wall spot is taken.
    _ig = bool(getattr(tracker, 'stair_is_ceiling', False))
    _hole = getattr(tracker, 'stair_hole_rect', None)

    def _clear(x0, x1, y0, y1):
        """Free for the display, strictly never overlapping stairwells or their 2.5m landings."""
        if not tracker.is_free(x0, x1, y0, y1):
            return False
        return True

    def _try_place(hw, hd):
        """Search WALL-hugging spots for a free patch of the given half-size.
        Corners first (ordered by closeness to the staircase so it lands under
        the stairs when it can), then wall midpoints. Never mid-room."""
        _spots = []
        _nf = _ry0 + hd + 0.10
        _nb = _ry1 - hd - 0.10
        _nl = _rx0 + hw + 0.10
        _nr = _rx1 - hw - 0.10
        # Prefer a clear, centred spot on the wall that carries the annex (there
        # is usually free floor there), then the other wall midpoints, then the
        # corners. This keeps the display off a random corner.
        _annex_side = None
        try:
            _by = getattr(getattr(tracker, 'ctx', None), 'annex_by_side', None) or {}
            if _by:
                _annex_side = next(iter(_by))
        except Exception:
            _annex_side = None
        _mids = []
        if _annex_side == 'LEFT':
            _mids += [(_nl, _ry0 + (_ry1 - _ry0) * _f) for _f in (0.50, 0.36, 0.64)]
        elif _annex_side == 'RIGHT':
            _mids += [(_nr, _ry0 + (_ry1 - _ry0) * _f) for _f in (0.50, 0.36, 0.64)]
        elif _annex_side == 'FRONT':
            _mids += [(_rx0 + (_rx1 - _rx0) * _f, _nf) for _f in (0.50, 0.36, 0.64)]
        elif _annex_side == 'BACK':
            _mids += [(_rx0 + (_rx1 - _rx0) * _f, _nb) for _f in (0.50, 0.36, 0.64)]
        for _f in (0.50, 0.32, 0.68):
            _py = _ry0 + (_ry1 - _ry0) * _f
            _px = _rx0 + (_rx1 - _rx0) * _f
            _mids += [(_nl, _py), (_nr, _py), (_px, _nf), (_px, _nb)]
        _spots += _mids
        _spots += [(_nl, _nf), (_nr, _nf), (_nl, _nb), (_nr, _nb)]
        # Stable sort: free spots first, preserving the annex-wall / midpoint
        # priority order above (no more stair-corner bias).
        _spots.sort(key=lambda p: _check(p, hw, hd))
        for _sx, _sy in _spots:
            _sx += _jit(rng, 0.06)
            _sy += _jit(rng, 0.06)
            if not _clear(_sx - hw, _sx + hw, _sy - hd, _sy + hd):
                continue
            tracker.occupy(_sx - hw, _sx + hw, _sy - hd, _sy + hd)
            return (_sx, _sy, _yaw_away(_sx, _sy))
        # Fine scan hugging each wall as a last resort (a staircase or counter
        # can block the coarse corner/midpoint spots in a small shop).
        for _wy in (_nf, _nb):
            _x = _nl
            while _x <= _nr + 1e-6:
                if _clear(_x - hw, _x + hw, _wy - hd, _wy + hd):
                    tracker.occupy(_x - hw, _x + hw, _wy - hd, _wy + hd)
                    return (_x, _wy, _yaw_away(_x, _wy))
                _x += 0.15
        for _wx in (_nl, _nr):
            _y = _nf
            while _y <= _nb + 1e-6:
                if _clear(_wx - hw, _wx + hw, _y - hd, _y + hd):
                    tracker.occupy(_wx - hw, _wx + hw, _y - hd, _y + hd)
                    return (_wx, _y, _yaw_away(_wx, _y))
                _y += 0.15
        return None

    def _check(p, hw, hd):
        return 0 if _clear(p[0] - hw, p[0] + hw, p[1] - hd, p[1] + hd) else 1

    # Full-size display first, then a compact one for cramped shops.
    _placed = _try_place(0.85, 0.575)
    _disp_w = 1.50
    if _placed is None:
        _placed = _try_place(0.62, 0.50)
        _disp_w = 1.05
    if _placed is None:
        # Cramped shop (e.g. a staircase eating every wall): fall back to the
        # freest open patch so the trade display always shows up.
        _sp = _freest_spot(tracker, rng)
        if _sp is not None:
            _sxc, _syc = _sp[0], _sp[1]
            for _hw, _hd, _w in ((0.62, 0.50, 1.05), (0.50, 0.44, 0.92)):
                if _clear(_sxc - _hw, _sxc + _hw, _syc - _hd, _syc + _hd):
                    tracker.occupy(_sxc - _hw, _sxc + _hw, _syc - _hd, _syc + _hd)
                    _placed = (_sxc, _syc, _yaw_away(_sxc, _syc))
                    _disp_w = _w
                    break
    if _placed is None:
        # Guarantee: grid-scan the whole floor (ignoring the stair reserve, the
        # floor is solid beneath a ceiling hole) for any pocket big enough.
        _best = None
        _xs = [tracker.rx0 + 0.55 + i * 0.35
               for i in range(int(max(1.0, tracker.rx1 - tracker.rx0 - 1.10) / 0.35) + 1)]
        _ys = [tracker.ry0 + 0.55 + i * 0.35
               for i in range(int(max(1.0, tracker.ry1 - tracker.ry0 - 1.10) / 0.35) + 1)]
        for _hw, _hd, _w in ((0.46, 0.42, 0.92), (0.38, 0.36, 0.78),
                             (0.31, 0.30, 0.64)):
            for _x in _xs:
                for _y in _ys:
                    if tracker.is_free(_x - _hw, _x + _hw, _y - _hd, _y + _hd,
                                       ignore_stair=True):
                        _best = (_x, _y, _hw, _hd, _w)
                        break
                if _best is not None:
                    break
            if _best is not None:
                break
        if _best is not None:
            _x, _y, _hw, _hd, _w = _best
            tracker.occupy(_x - _hw, _x + _hw, _y - _hd, _y + _hd)
            _placed = (_x, _y, _yaw_away(_x, _y))
            _disp_w = _w
        else:
            # Absolute last resort (an extremely narrow shop): put a compact
            # display at the room centre so the shop is never without one.
            _x = (tracker.rx0 + tracker.rx1) * 0.5
            _y = (tracker.ry0 + tracker.ry1) * 0.5
            tracker.occupy(_x - 0.33, _x + 0.33, _y - 0.31, _y + 0.31)
            _placed = (_x, _y, _yaw_away(_x, _y))
            _disp_w = 0.66
    if _placed is None:
        return
    _cx, _cy, _yaw = _placed
    build_prop(bm, 'MARKET_DISPLAY', _cx, _cy, z_floor, _yaw, width=_disp_w)
    # Dress the tiers (mirror the builder: tier tops at local y +0.17/-0.16/
    # -0.50, z 0.50/0.85/1.20). Items spread across the tier width, scaled to
    # fill it, with per-item scale and yaw jitter so a tier reads fully
    # stocked and hand-laid rather than cloned.
    _cyaw = _yaw
    _cos, _sin = math.cos(_cyaw), math.sin(_cyaw)
    for (_ly, _lz), _base in zip(((0.17, 0.50), (-0.16, 0.85), (-0.50, 1.20)),
                                 _tier_goods):
        # Size the run to the longest piece on the tier so long goods (tools)
        # never overhang the display's sides, then pack it.
        _lens = [(_good_base_length(g) or 0.24) for g in _base]
        _longest = max(_lens) if _lens else 0.24
        _span = max(0.24, _disp_w - _longest - 0.10)
        _max_i = max(2, int(_span / (_longest + 0.06)) + 1)
        _goods = _base[:min(len(_base), _max_i)]
        _m = len(_goods)
        for _i, _g in enumerate(_goods):
            _frac = 0.0 if _m <= 1 else (_i / (_m - 1) - 0.5)
            _lx = _frac * _span + _jit(rng, 0.02)
            _lyj = _ly + _jit(rng, 0.02)
            _gx = _cx + _lx * _cos - _lyj * _sin
            _gy = _cy + _lx * _sin + _lyj * _cos
            # Long merchandise (tools) stays near-aligned so it lies neatly;
            # small goods get the full playful yaw.
            _base_len = _good_base_length(_g) or 0.24
            _yj = 0.10 if (_base_len > 0.45 or _g in _ALIGNED_GOODS) else 0.45
            build_prop(bm, _g, _gx, _gy, z_floor + _lz + 0.012,
                       _cyaw + rng.uniform(-_yj, _yj),
                       **_good_length_param(_g, rng))
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
                                        candidate_walls=('EAST',), length=1.80, back_bar=False)
    if not placed_altar:
        _try_place_wall_prop(bm, 'COUNTER', 1.80, 0.60, tracker, z_floor,
                             candidate_walls=('WEST',), length=1.80, back_bar=False)

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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil, prop_name='CHANDELIER', radius=0.48)


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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _furnish_corridor(bm, rm, tracker: RoomOccupancyTracker, z_floor: float, z_ceil: float,
                      rng, density: float):
    """A stair landing / corridor stays clear: only a ceiling light.

    Corridors are the walking routes between rooms and to the stairs. Rugs,
    benches, chests and shelves here blocked the way, so circulation is kept
    free of floor furniture on purpose.
    """
    rcx = (rm.bounds[0] + rm.bounds[1]) * 0.5
    rcy = (rm.bounds[2] + rm.bounds[3]) * 0.5
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
        build_prop(bm, 'SCATTER_TABLEWARE', tx - 0.45, ty, z_floor + 0.992, 0.0)
        build_prop(bm, 'SCATTER_TABLEWARE', tx + 0.45, ty, z_floor + 0.992, 0.0)
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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
        _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)
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
    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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
    # behind it, else     _counter_len = min(2.0, max(1.2, min(rw, rd) * 0.45))
    _placed_counter = None

    # Determine staircase side so the counter prioritizes the opposite clear wall
    _sw = getattr(tracker, 'stair_hole', None)
    _stair_on_left = True
    if _sw is not None:
        _sxc = (_sw[0] + _sw[1]) * 0.5
        _stair_on_left = (_sxc < (tracker.rx0 + tracker.rx1) * 0.5)

    if _stair_on_left:
        # Stair is on West: prioritize East wall, then North/South, never West near stairs
        _wall_order = (('EAST', -math.pi * 0.5, 1.0, 0.0),
                       ('NORTH', 0.0, 0.0, 1.0),
                       ('SOUTH', math.pi, 0.0, -1.0),
                       ('WEST', math.pi * 0.5, -1.0, 0.0))
    else:
        # Stair is on East: prioritize West wall, then North/South, never East near stairs
        _wall_order = (('WEST', math.pi * 0.5, -1.0, 0.0),
                       ('NORTH', 0.0, 0.0, 1.0),
                       ('SOUTH', math.pi, 0.0, -1.0),
                       ('EAST', -math.pi * 0.5, 1.0, 0.0))

    # Strict stair clearance: counters must NEVER ignore stairs or sit below/under them!
    for _ig in (False,):
        if _placed_counter is not None:
            break
        for _wall, _yaw, _mdx, _mdy in _wall_order:
            _run = rw if _wall in ('NORTH', 'SOUTH') else rd
            _clen = min(2.0, max(1.2, _run * 0.45))
            _hw = (_clen * 0.5 + 0.15) if _wall in ('NORTH', 'SOUTH') else 0.45
            _hd = 0.45 if _wall in ('NORTH', 'SOUTH') else (_clen * 0.5 + 0.15)
            if _wall == 'NORTH':
                _axis, _fixed = 'X', tracker.ry1 - 1.05 - 0.30
                _lo, _hi = tracker.rx0 + _hw + 0.12, tracker.rx1 - _hw - 0.12
            elif _wall == 'SOUTH':
                _axis, _fixed = 'X', tracker.ry0 + 1.05 + 0.30
                _lo, _hi = tracker.rx0 + _hw + 0.12, tracker.rx1 - _hw - 0.12
            elif _wall == 'EAST':
                _axis, _fixed = 'Y', tracker.rx1 - 1.05 - 0.30
                _lo, _hi = tracker.ry0 + _hd + 0.12, tracker.ry1 - _hd - 0.12
            else:
                _axis, _fixed = 'Y', tracker.rx0 + 1.05 + 0.30
                _lo, _hi = tracker.ry0 + _hd + 0.12, tracker.ry1 - _hd - 0.12
            if _hi < _lo - 1e-6:
                continue
            # Sample along the wall so a cramped room still finds a free bay.
            _span = _hi - _lo
            _n = max(1, int(_span / 0.25) + 1)
            for _k in range(_n + 1):
                _t = _lo + _span * (_k / float(_n))
                _ccx, _ccy = (_t, _fixed) if _axis == 'X' else (_fixed, _t)
                if not tracker.is_free(_ccx - _hw, _ccx + _hw, _ccy - _hd, _ccy + _hd,
                                       ignore_stair=_ig):
                    continue
                # Merchant stool spot behind the counter.
                _stx, _sty = _ccx + _mdx * 0.72, _ccy + _mdy * 0.72
                if not tracker.is_free(_stx - 0.26, _stx + 0.26, _sty - 0.26, _sty + 0.26,
                                       ignore_stair=_ig):
                    continue
                tracker.occupy(_ccx - _hw, _ccx + _hw, _ccy - _hd, _ccy + _hd)
                build_prop(bm, 'COUNTER', _ccx, _ccy, z_floor, _yaw, length=_clen,
                           back_bar=False)
                tracker.occupy(_stx - 0.26, _stx + 0.26, _sty - 0.26, _sty + 0.26)
                build_prop(bm, 'STOOL', _stx, _sty, z_floor,
                           math.atan2(-_mdx, -_mdy))
                _placed_counter = {'cx': _ccx, 'cy': _ccy, 'yaw': _yaw,
                                   'wall': _wall, 'freestanding': True,
                                   'mdx': _mdx, 'mdy': _mdy, 'length': _clen,
                                   'top_z': z_floor + 1.235}
                break
            if _placed_counter is not None:
                break
    # Fallback wall counters: still strictly never ignoring stairs
    if _placed_counter is None:
        _cand_walls = [w for w, _, _, _ in _wall_order if (w != 'WEST' if _stair_on_left else w != 'EAST')]
        for _cl in (_counter_len, 1.20, 1.00):
            _d_counter = _try_place_wall_prop(
                bm, 'COUNTER', _cl, 0.60, tracker, z_floor,
                candidate_walls=_cand_walls, length=_cl, back_bar=False, ignore_stair=False)
            if _d_counter:
                _placed_counter = {'cx': _d_counter[0], 'cy': _d_counter[1],
                                   'yaw': _d_counter[2], 'wall': None,
                                   'freestanding': False, 'mdx': 0.0, 'mdy': 0.0,
                                   'length': _cl, 'top_z': z_floor + 1.235}
                break
    if _placed_counter is None:
        # Absolute last resort: a compact freestanding counter at the freest
        # open patch strictly clear of all stairs and doorways.
        _sp = _freest_spot(tracker, rng, step=0.30)
        if _sp is not None and _sp[2] >= 0.45:
            _chw, _chd = min(0.62, _sp[2]), min(0.45, _sp[2])
            if tracker.is_free(_sp[0] - _chw, _sp[0] + _chw, _sp[1] - _chd, _sp[1] + _chd, ignore_stair=False):
                tracker.occupy(_sp[0] - _chw, _sp[0] + _chw, _sp[1] - _chd, _sp[1] + _chd)
                build_prop(bm, 'COUNTER', _sp[0], _sp[1], z_floor, 0.0, length=1.20,
                           back_bar=False)
                _placed_counter = {'cx': _sp[0], 'cy': _sp[1], 'yaw': 0.0,
                                   'wall': None, 'freestanding': True, 'mdx': 0.0,
                                   'mdy': 0.0, 'length': 1.20, 'top_z': z_floor + 1.235}
    tracker.shop_counter = _placed_counter
    if _placed_counter:
        _cc = _placed_counter
        _arch_cc = getattr(tracker, 'archetype', 'NONE')
        if _arch_cc in ('TOOLSMITH', 'BLACKSMITH'):
            # A tool or two laid out on the counter (no plant), spaced so the
            # axe head never lands in the pickaxe handle.
            _ca, _sa = math.cos(_cc['yaw']), math.sin(_cc['yaw'])
            for _off, _key in ((-0.44, 'AXE'), (0.44, 'PICKAXE')):
                build_prop(bm, _key, _cc['cx'] + _ca * _off,
                           _cc['cy'] + _sa * _off, _cc['top_z'],
                           _cc['yaw'])
        elif _arch_cc != 'JEWELER':
            # Countertop plant (jeweler gets the gem tray instead).
            build_prop(bm, 'POTTED_PLANT_SMALL', _cc['cx'], _cc['cy'],
                       _cc['top_z'], rng.uniform(0.0, 6.28))

    # 2. Stepped market display FIRST (before shelves/crates) so it always
    #    wins a good wall nook and never gets blocked out.
    _place_market_display(bm, tracker, z_floor, rng, getattr(tracker, 'archetype', ''))

    # 3. Display shelves on perimeter walls (the fishmonger swaps these for
    #    the trade display case; the butcher swaps them for meat racks).
    _arch0 = getattr(tracker, 'archetype', 'NONE')
    props = getattr(tracker, 'props', None)
    if _arch0 == 'BUTCHER':
        _try_place_wall_prop(bm, 'MEAT_RACK', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('EAST', 'WEST', 'NORTH'))
        _try_place_wall_prop(bm, 'MEAT_RACK', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=('WEST', 'NORTH', 'SOUTH'))
    elif _arch0 not in ('FISHERMAN', 'TOOLSMITH', 'BLACKSMITH'):
        _is_bakery = (_arch0 == 'BAKERY' or bool(getattr(props, 'kit_bakery', False)))
        _swall1 = ('SOUTH', 'NORTH', 'WEST') if _is_bakery else ('EAST', 'SOUTH', 'NORTH')
        _swall2 = ('SOUTH', 'WEST', 'NORTH') if _is_bakery else ('EAST', 'SOUTH', 'WEST', 'NORTH')
        _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=_swall1)
        _try_place_wall_prop(bm, 'SHELF', 1.40, 0.40, tracker, z_floor,
                             candidate_walls=_swall2)

    # 4. Goods crates and merchandise barrels — kept OFF the corners so the
    #    wall corners stay free for the trade display (placed above). The
    #    toolsmith shop keeps its floor clear for the tool racks instead.
    _mid_y = (rm.bounds[2] + rm.bounds[3]) * 0.5
    _mid_x = (rm.bounds[0] + rm.bounds[1]) * 0.5
    if _arch0 == 'FISHERMAN':
        # Fish storage barrels lined up ALONG THE WALLS (never mid-floor).
        _n_placed = 0
        for _walls in (('EAST', 'WEST', 'NORTH', 'SOUTH'),
                       ('WEST', 'EAST', 'SOUTH', 'NORTH'),
                       ('NORTH', 'SOUTH', 'EAST', 'WEST'),
                       ('SOUTH', 'NORTH', 'WEST', 'EAST'),
                       ('EAST', 'NORTH', 'WEST', 'SOUTH'),
                       ('WEST', 'SOUTH', 'EAST', 'NORTH')):
            if _n_placed >= 4:
                break
            if _try_place_wall_prop(bm, 'BARREL', 0.72, 0.72, tracker, z_floor,
                                    candidate_walls=_walls) is not None:
                _n_placed += 1
    elif _arch0 not in ('TOOLSMITH', 'BLACKSMITH'):
        for cx, cy in ((rm.bounds[0] + 0.40, _mid_y), (rm.bounds[1] - 0.40, _mid_y),
                       (_mid_x, rm.bounds[2] + 0.40), (_mid_x, rm.bounds[3] - 0.40)):
            if tracker.is_free(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25):
                tracker.occupy(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25)
                prop = 'CRATE' if rng.random() < 0.6 else 'BARREL'
                build_prop(bm, prop, cx, cy, z_floor, 0.0)

    # 5. Area rug in the customer browse zone (in front of a freestanding
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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


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

    _place_ceiling_light(bm, tracker, rcx, rcy, z_ceil)


def _dress_single_room(bm, rm, z_floor: float, z_ceil: float, rng,
                       density: float, style: str, ctx=None,
                       floor_has_dining: bool = False):
    """Dresses one functional room using the appropriate layout algorithm."""
    rx0, rx1, ry0, ry1 = rm.bounds
    if getattr(rm, 'is_wing', False):
        _wt = float(getattr(ctx, 'wall_t', 0.30) if ctx is not None else 0.30)
        rx0 += _wt
        rx1 -= _wt
        ry0 += _wt
        ry1 -= _wt
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
        _ctx_p = getattr(ctx, 'props', None) if ctx is not None else None
        _extras = (getattr(ctx, 'extra_doorways', None)
                   or (getattr(_ctx_p, 'extra_doorways', None) if _ctx_p is not None else None)
                   or (_ctx_p.get('extra_doorways', None) if hasattr(_ctx_p, 'get') else None)
                   or [])
        for ed in _extras:
            if ed.get('floor_idx', 0) == rm.floor_idx:
                efac = ed.get('facade', '')
                # Only include this extra doorway if the room actually borders this exterior facade!
                if hasattr(rm, 'exterior_facades') and rm.exterior_facades:
                    if efac not in rm.exterior_facades:
                        continue
                sax = ed.get('axis', 'Y' if efac in ('LEFT', 'RIGHT') else 'X')
                if sax == 'X':
                    ed_x, ed_y = ed.get('pos', 0.0), (ry1 if efac == 'BACK' else ry0)
                else:
                    ed_x, ed_y = (rx0 if efac == 'LEFT' else rx1), ed.get('pos', 0.0)
                # Anchor the doorway on the TRUE exterior wall plane, not on the
                # (often inset) room bound. Otherwise the keep-clear corridor in
                # front of a portal is reserved in the wrong place and furniture
                # ends up parked right inside the doorway.
                _fwb = (getattr(ctx, 'floor_wall_bounds', None) or {}).get(
                    rm.floor_idx) if ctx is not None else None
                if _fwb is not None:
                    _wt2 = float(getattr(ctx, 'wall_t', 0.30) or 0.30)
                    if efac == 'RIGHT':
                        ed_x = _fwb[1] - _wt2
                    elif efac == 'LEFT':
                        ed_x = _fwb[0] + _wt2
                    elif efac == 'BACK':
                        ed_y = _fwb[3] - _wt2
                    elif efac == 'FRONT':
                        ed_y = _fwb[2] + _wt2
                ed_d = {'x': ed_x, 'y': ed_y, 'axis': sax, 'w': ed.get('w', 1.8), 'is_portal': ed.get('is_portal', True)}
                # The doorway must lie along this room's wall span.
                if sax == 'X':
                    _along_ok = (rx0 - 0.55 <= ed_x <= rx1 + 0.55)
                else:
                    _along_ok = (ry0 - 0.55 <= ed_y <= ry1 + 0.55)
                if _along_ok:
                    if ed_d not in all_doorways:
                        all_doorways.append(ed_d)
        # Side-annex walk-throughs: reserve the hall-side apron in front of the
        # portal (both directions) so no furniture parks in the way into the annex.
        for _as, _alay in (getattr(ctx, 'annex_by_side', None) or {}).items():
            if rm.floor_idx >= int(getattr(ctx, 'annex_floors', 0) or 0):
                continue
            _apc = _alay.get('portal_cy', 0.0)
            _ax = rx0 if _as == 'LEFT' else rx1
            if not (rx0 - 0.10 <= _ax <= rx1 + 0.10 and ry0 - 0.10 <= _apc <= ry1 + 0.10):
                continue
            _ad = {'x': _ax, 'y': _apc, 'axis': 'Y', 'w': 1.65, 'is_portal': True}
            if _ad not in all_doorways:
                all_doorways.append(_ad)

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

    # Stairwell footprint: the room's own hole, the hole cut in THIS floor's
    # slab (stairs going down), and the hole one storey up (stairs rising).
    # All three are reserved so no prop or light ever sits inside the staircase.
    _stair_well = rm.stair_hole
    if _stair_well is None and ctx is not None:
        _stair_well = (getattr(ctx, 'floor_stair_holes', None) or {}).get(
            rm.floor_idx)
    if _stair_well is None and ctx is not None:
        _stair_well = (getattr(ctx, 'floor_stair_holes', None) or {}).get(
            rm.floor_idx + 1)
    _floor_void = getattr(rm, 'floor_void', None)
    if _floor_void is None and ctx is not None:
        _floor_void = (getattr(ctx, 'floor_voids', None) or {}).get(rm.floor_idx)
    _clear_zones = []
    if ctx is not None:
        for _cz in ((getattr(ctx, 'floor_clear_zones', None) or {}).get(rm.floor_idx) or []):
            _clear_zones.append(_cz)
        # Entrance apron into a side annex.
        for _xs, _xb in (getattr(ctx, 'annex_by_side', None) or {}).items():
            if rm.floor_idx >= int(getattr(ctx, 'annex_floors', 0) or 0):
                continue
            _pc = _xb.get('portal_cy', 0.0)
            _wt = float(getattr(ctx, 'wall_t', 0.30) or 0.30)
            _fw = (getattr(ctx, 'floor_wall_bounds', None) or {}).get(rm.floor_idx)
            if _fw is not None:
                _fx = (_fw[1] - _wt) if _xs == 'RIGHT' else (_fw[0] + _wt)
            else:
                _fx = rx1 if _xs == 'RIGHT' else rx0
            _clear_records = (getattr(ctx, 'annex_clear_rects', None) or [])
            _z = next((tuple(_rec['rect']) for _rec in _clear_records
                       if _rec.get('side') == _xs
                       and rm.floor_idx in (_rec.get('floor_idx') or [])), None)
            if _z is None:
                _half_y = 1.65 * 0.5 + 0.16 + 0.10 + 0.35
                _z = (_fx - 1.30, _fx + 1.30, _pc - _half_y, _pc + _half_y)
            if not (_z[1] <= rx0 or _z[0] >= rx1 or _z[3] <= ry0 or _z[2] >= ry1):
                _clear_zones.append(_z)
    tracker = RoomOccupancyTracker(
        rx0 + inset, rx1 - inset, ry0 + inset, ry1 - inset,
        stair_hole=_stair_well,
        doorways=all_doorways,
        windows=room_windows,
        chimney=chimney_positions,
        floor_void=_floor_void,
        clear_zones=_clear_zones
    )
    # Real (uninset) room bounds: wall-anchored pieces sit flush to these.
    # Prefer the TRUE interior walls for the floor (the room itself may be
    # inset a metre+ off a wall that carries a flight elsewhere); the precise
    # stair/door/prop boxes still reject any slot the flight actually uses.
    tracker.room_bounds = (rx0, rx1, ry0, ry1)
    if ctx is not None and not getattr(rm, 'is_wing', False):
        _fwb = (getattr(ctx, 'floor_wall_bounds', None) or {}).get(
            rm.floor_idx)
        _wt = float(getattr(ctx, 'wall_t', 0.30) or 0.30)
        if _fwb is not None:
            # Only clamp to outer building bounds for exterior perimeter walls;
            # interior partition walls stay strictly at (rx0, rx1, ry0, ry1).
            _wx0 = (_fwb[0] + _wt) if abs(rx0 - (_fwb[0] + _wt)) < 0.6 else rx0
            _wx1 = (_fwb[1] - _wt) if abs(rx1 - (_fwb[1] - _wt)) < 0.6 else rx1
            _wy0 = (_fwb[2] + _wt) if abs(ry0 - (_fwb[2] + _wt)) < 0.6 else ry0
            _wy1 = (_fwb[3] - _wt) if abs(ry1 - (_fwb[3] - _wt)) < 0.6 else ry1
            tracker.room_bounds = (_wx0, _wx1, _wy0, _wy1)
    tracker.stair_hole = _stair_well
    # Turned-stair rooms are pre-inset off the walls that carry a flight, so
    # the generic side pad would double-dip and deny the whole inset wall.
    # Shrink it to a clip margin (the hole ends keep their approach boxes and
    # the room inset already clears the flight body).
    if (ctx is not None and getattr(ctx, 'turn_stair', False)
            and tracker.stair_box is not None and _stair_well is not None):
        try:
            tracker.occupied_boxes.remove(tracker.stair_box)
        except ValueError:
            pass
        _sx0, _sx1, _sy0, _sy1 = _stair_well
        tracker.stair_box = (_sx0 - 0.80, _sx1 + 0.80,
                             _sy0 - 2.20, _sy1 + 2.20)
        tracker.occupied_boxes.append(tracker.stair_box)
    # A ceiling stair-hole (no opening in THIS floor's own slab) sits over a
    # solid floor only above ground floor (on ground floor the stair rises from the slab).
    _own_hole = None
    if ctx is not None:
        _own_hole = (getattr(ctx, 'floor_stair_holes', None) or {}).get(rm.floor_idx)
    tracker.stair_is_ceiling = bool(_stair_well is not None and _own_hole is None and rm.floor_idx > 0)
    # Reserve the full staircase footprint only on storeys with real floor to
    # spare. A switchback well is two lanes wide, but only the arriving lane is
    # actually open in this floor's slab - reserving the whole well on small
    # storeys swallowed the room (the 7.5 m fishery cottage got no furniture).
    _full_stair = getattr(ctx, 'full_stair_box', None)
    if _full_stair is not None:
        fs_x0, fs_x1, fs_y0, fs_y1 = _full_stair
        if not (rx1 < fs_x0 or rx0 > fs_x1 or ry1 < fs_y0 or ry0 > fs_y1):
            _room_area = max((rx1 - rx0) * (ry1 - ry0), 1e-3)
            if _room_area >= 55.0:
                pad_land = 0.35
                pad_side = 0.25
                stair_keepout = (fs_x0 - pad_side, fs_x1 + pad_side,
                                 fs_y0 - pad_land, fs_y1 + pad_land)
                tracker.occupy(*stair_keepout)
                if tracker.stair_box is None:
                    tracker.stair_box = stair_keepout
    tracker.rng = rng
    tracker.ctx = ctx
    tracker.all_stair_holes = []
    if ctx is not None:
        fsh = getattr(ctx, 'floor_stair_holes', {}) or {}
        for h in fsh.values():
            if h is not None and h not in tracker.all_stair_holes:
                tracker.all_stair_holes.append(h)
        fsb = getattr(ctx, 'full_stair_box', None)
        if fsb is not None and fsb not in tracker.all_stair_holes:
            tracker.all_stair_holes.append(fsb)
    if _stair_well is not None and _stair_well not in tracker.all_stair_holes:
        tracker.all_stair_holes.append(_stair_well)
    if tracker.stair_hole_rect is not None and tracker.stair_hole_rect not in tracker.all_stair_holes:
        tracker.all_stair_holes.append(tracker.stair_hole_rect)
    props = getattr(ctx, 'props', None) if ctx is not None else None
    tracker.props = props
    tracker.archetype = getattr(ctx, 'effective_archetype', 'NONE') if ctx is not None else 'NONE'
    _is_bakery_oven = (tracker.archetype == 'BAKERY'
                       or bool(getattr(props, 'kit_bakery', False)))
    if _is_bakery_oven and ctx is not None:
        # Hearth-oven masonry keep-out: the ground-floor reserves
        # the oven body + work apron, and upper storeys reserve the flue
        # shaft rising through them, so props never intersect the masonry.
        try:
            from .bakery import bakery_oven_rect, _pick_oven_y
            _hx = float(getattr(ctx, 'hx', 0.0))
            _hy = float(getattr(ctx, 'hy', 0.0))
            _wt = float(getattr(ctx, 'wall_t', 0.30))
            _oy = _pick_oven_y(ctx, _hy, _wt, 0.975)
            if rm.floor_idx == 0:
                _ov_box = bakery_oven_rect(_hx, _wt, _oy)
                if not (rm.bounds[1] < _ov_box[0] or rm.bounds[0] > _ov_box[1] or
                        rm.bounds[3] < _ov_box[2] or rm.bounds[2] > _ov_box[3]):
                    tracker.occupy(*_ov_box)
            elif rm.floor_idx > 0:
                _fx = (_hx - _wt) - 1.35 * 0.5
                _flue_box = (_fx - 0.70, _fx + 0.70, _oy - 0.70, _oy + 0.70)
                if not (rm.bounds[1] < _flue_box[0] or rm.bounds[0] > _flue_box[1] or
                        rm.bounds[3] < _flue_box[2] or rm.bounds[2] > _flue_box[3]):
                    tracker.occupy(*_flue_box)
        except Exception:
            pass
    tracker.bare_stockpile = bool(getattr(ctx, 'bare_stockpile', False)) if ctx is not None else False
    tracker.is_quarry = (tracker.archetype == 'QUARRY')
    tracker.industrial = getattr(ctx, 'industrial', False) or (tracker.archetype in ('WAREHOUSE', 'LUMBERMILL', 'QUARRY', 'BUILDER'))
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
    if (tracker.archetype == 'LUMBERMILL' or bool(getattr(props, 'kit_lumbermill', False))) and rm.floor_idx == 0:
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
    # Mezzanine Gallery & Floor Void Keep-out: reserve the opening so NO props or rugs clip it
    _fvoid = getattr(rm, 'floor_void', None)
    if not _fvoid and ctx is not None:
        _fvoid = (getattr(ctx, 'floor_voids', {}) or {}).get(rm.floor_idx)
    if _fvoid is not None:
        tracker.occupy(_fvoid[0] - 0.20, _fvoid[1] + 0.20, _fvoid[2] - 0.20, _fvoid[3] + 0.20)
        tracker.floor_void = _fvoid

    if rm.role in ('MEZZANINE_GALLERY', 'UPPER_GALLERY'):
        tracker.no_rugs = True
        tracker.rug_count = 99

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
        elif role in ('MEZZANINE_GALLERY', 'UPPER_GALLERY'):
            _furnish_mezzanine_gallery(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('GREAT_HALL', 'COUNCIL_CHAMBER'):
            _furnish_great_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('BANQUET_HALL',):
            _furnish_banquet_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('ENTRANCE_HALL',):
            _furnish_entrance_hall(bm, rm, tracker, z_floor, z_ceil, rng, density, chimney_pos=chimney_positions)
        elif role in ('MAYOR_OFFICE', 'OFFICE'):
            _furnish_office(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('TENEMENT_PARLOUR', 'PARLOUR'):
            _furnish_tenement_parlour(bm, rm, tracker, z_floor, z_ceil, rng, density,
                                      chimney_pos=chimney_positions)
        elif role in ('KITCHEN', 'TENEMENT_KITCHEN'):
            _furnish_kitchen(bm, rm, tracker, z_floor, z_ceil, rng, density,
                             chimney_pos=chimney_positions,
                             floor_has_dining=(floor_has_dining or role == 'TENEMENT_KITCHEN'))
        elif role in ('MASTER_BED', 'OFFICER_QUARTERS', 'ROYAL_CHAMBER'):
            _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=True)
        elif role in ('MESS_HALL',):
            _furnish_mess_hall(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('RANGE', 'FLETCHER_WORKSHOP'):
            _furnish_archery_range(bm, rm, tracker, z_floor, z_ceil, rng, density, role=role)
        elif role in ('BEDROOM', 'GUEST_ROOM', 'LODGE', 'TENEMENT_BEDROOM'):
            _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, density, is_master=False)
        elif role in ('BARRACKS_DORM', 'OFFICER_QUARTERS'):
            _furnish_barracks_dorm(bm, rm, tracker, z_floor, z_ceil, rng, density)
        elif role in ('COMMON_ROOM', 'DORMITORY'):
            # Cheap shared lodgings: rows of bunk beds, lockers, one long table.
            _furnish_barracks_dorm(bm, rm, tracker, z_floor, z_ceil, rng, density)
            _place_craft_table(bm, tracker, z_floor, rng,
                               length=min(2.60, max(1.40, rw * 0.45)), width=0.90)
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
        elif role in ('COTTAGE', 'LIVING_QUARTERS'):
            # One combined living area per floor. Bed FIRST so it always lands,
            # living after, and a kitchen only on the lowest upper floor -
            # one kitchen per home, not per storey. Density is near-full: the
            # room is big and the recipes anchor to different walls/zones.
            _d = min(1.0, density * 0.8)
            _prev_nr = getattr(tracker, 'no_rugs', False)
            if getattr(tracker, 'archetype', '') == 'FISHERMAN':
                _furnish_fisher_cottage(bm, rm, tracker, z_floor, z_ceil, rng, _d,
                                        chimney_pos=chimney_positions)
            else:
                _furnish_bedroom(bm, rm, tracker, z_floor, z_ceil, rng, _d,
                                 is_master=True)
                tracker.no_rugs = True
                if getattr(rm, 'floor_idx', 1) <= 1:
                    # The hall below owns the single dining set, so the kitchen
                    # stays a kitchen (stove + shelf + produce) instead of adding
                    # a second table that clumps against it.
                    _furnish_kitchen(bm, rm, tracker, z_floor, z_ceil, rng, _d,
                                     chimney_pos=chimney_positions,
                                     floor_has_dining=True)
                _furnish_house_hall(bm, rm, tracker, z_floor, z_ceil, rng, _d,
                                    chimney_pos=chimney_positions)
            tracker.no_rugs = _prev_nr
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
    if (not _bare and role not in ('STAIR_LANDING', 'CORRIDOR', 'STABLE_HALL', 'STORE', 'MEZZANINE_GALLERY', 'UPPER_GALLERY', 'THRONE_ROOM')
            and len(tracker.occupied_boxes) - _occ_before < 3):
        try:
            _ensure_minimum_dressing(bm, tracker, rm, z_floor, rng)
        except Exception:
            if _STRICT_FURNISH:
                raise

    # Every room gets at least one rug, except back-of-house rooms in an
    # industrial fit-out (warehouses/lumbermills stay bare), stables, and
    # circulation (corridors/landings must stay clear). Rugs are regular-size,
    # never tiny mats, and skipped when the floor cannot fit one.
    if (not _bare and role not in ('THRONE_ROOM', 'MEZZANINE_GALLERY', 'UPPER_GALLERY',
                                   'STABLE_HALL', 'CORRIDOR', 'STAIR_LANDING')
            and getattr(tracker, 'rug_count', 0) == 0
            and not getattr(tracker, 'no_rugs', False)):
        rw = (rx1 - rx0) - inset * 2.0
        rd = (ry1 - ry0) - inset * 2.0
        if rw >= 2.2 and rd >= 2.8:
            rug_key = rng.choice(['RUG_CRIMSON', 'RUG_SAPPHIRE', 'RUG_FOREST'])
            _lay_rug(bm, tracker, rm, rng, rug_key, (rx0 + rx1) * 0.5, (ry0 + ry1) * 0.5,
                     z_floor, min(3.20, max(2.20, rw * 0.55)),
                     min(4.20, max(2.80, rd * 0.55)))

    # Most rooms get a potted planter so the new plant props are actually seen
    # (skipped in bare industrial utility rooms, and never in a working stable).
    rw = rx1 - rx0
    rd = ry1 - ry0
    if role not in ('STABLE_HALL', 'MEZZANINE_GALLERY', 'UPPER_GALLERY') and not _bare and min(rw, rd) >= 2.6 and rng.random() < 0.7:
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

    if getattr(ctx, 'effective_archetype', 'NONE') == 'BUILDER' and (getattr(props, 'material_tier', 'TIER_1') == 'TIER_1' or props.roof_style == 'NONE'):
        return

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

    # Hard requirement: every residential home (HOUSE, NONE, AUTO, COTTAGE, MANOR, ARTISAN, TENEMENT)
    # MUST have at least one bedroom (or cottage living/sleeping room) with a bed!
    _arch = getattr(ctx, 'effective_archetype', 'NONE')
    _residential = (_arch in ('NONE', 'HOUSE', 'AUTO', '', 'MANOR', 'COTTAGE', 'TENEMENT',
                              'BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY', 'BUTCHER',
                              'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER', 'HUNTER')
                    or _arch.startswith('ARTISAN'))
    if _residential and floor_rooms_dict:
        _bed_roles = {'MASTER_BED', 'BEDROOM', 'COTTAGE', 'GUEST_ROOM', 'TENEMENT_BEDROOM',
                      'ROYAL_CHAMBER', 'OFFICER_QUARTERS', 'LIVING_QUARTERS'}
        _all_rooms = [rm for fl_rms in floor_rooms_dict.values() for rm in fl_rms]
        if _all_rooms and not any(getattr(rm, 'role', '') in _bed_roles for rm in _all_rooms):
            # No bedroom exists in the whole house! Assign a bedroom to guarantee a bed.
            if ctx.num_floors > 1:
                # Top floor room
                _top_rms = floor_rooms_dict.get(ctx.num_floors - 1, [])
                _target = next((r for r in reversed(_top_rms) if r.role != 'STAIR_LANDING'), None)
                if _target is None and _top_rms:
                    _target = _top_rms[0]
                if _target is not None:
                    _target.role = 'MASTER_BED'
            else:
                # Single-storey house: 1 room -> COTTAGE (bed + hearth + dining), 2+ rooms -> MASTER_BED
                _f0_rms = floor_rooms_dict.get(0, [])
                if len(_f0_rms) == 1:
                    _f0_rms[0].role = 'COTTAGE'
                elif len(_f0_rms) >= 2:
                    _target = next((r for r in reversed(_f0_rms) if r.role != 'HOUSE_HALL'), _f0_rms[-1])
                    _target.role = 'MASTER_BED'

        # Guarantee kitchen for artisans: 1 bedroom then 1 kitchen is highest priority!
        _is_artisan = (_arch in ('BLACKSMITH', 'BAKERY', 'FISHERMAN', 'BREWERY', 'BUTCHER',
                                 'TAILOR', 'TOOLSMITH', 'JEWELER', 'FURNITURE_MAKER', 'HUNTER')
                       or _arch.startswith('ARTISAN'))
        if _is_artisan and _all_rooms:
            _kitchen_roles = {'KITCHEN', 'COTTAGE', 'TENEMENT_KITCHEN'}
            if not any(getattr(rm, 'role', '') in _kitchen_roles for rm in _all_rooms):
                _upper_rms = [r for fl in range(1, ctx.num_floors) for r in floor_rooms_dict.get(fl, []) if r.role != 'STAIR_LANDING']
                # Prefer hall/storage/parlor/guest on lowest upper floor first
                _hall_cand = next((r for r in _upper_rms if r.role in ('HOUSE_HALL', 'STORAGE', 'PANTRY', 'GUEST_ROOM', 'STUDY', 'OFFICE', 'LIBRARY')), None)
                if _hall_cand is not None:
                    _hall_cand.role = 'KITCHEN'
                else:
                    _bed_cands = [r for r in _upper_rms if r.role in ('BEDROOM', 'MASTER_BED')]
                    if len(_bed_cands) >= 2:
                        # Keep the primary bedroom, assign kitchen to the other
                        _bed_cands[-1].role = 'KITCHEN'
                    elif len(_upper_rms) == 1:
                        # Only 1 chamber upstairs: make it a combined living/kitchen/bedroom COTTAGE
                        _upper_rms[0].role = 'COTTAGE'
                    elif not _upper_rms:
                        # Single-storey artisan: check ground floor rooms
                        _f0_rms = floor_rooms_dict.get(0, [])
                        if len(_f0_rms) == 1:
                            _f0_rms[0].role = 'COTTAGE'
                        elif len(_f0_rms) >= 2:
                            _cand = next((r for r in _f0_rms[1:] if r.role in ('HOUSE_HALL', 'STORAGE', 'PANTRY', 'BEDROOM')), None)
                            if _cand is not None:
                                _cand.role = 'KITCHEN'
                            else:
                                _f0_rms[-1].role = 'COTTAGE'

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
            elif arch in ('BLACKSMITH', 'WAREHOUSE', 'LUMBERMILL', 'BAKERY', 'HUNTER', 'BUILDER'):
                role = 'WORKSHOP' if fl == 0 else 'LODGE'
            elif arch == 'CHAPEL':
                role = 'CHAPEL_HALL'
            else:
                if ctx.num_floors == 1:
                    role = 'COTTAGE'
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
            if not any(getattr(r, 'role', '') == 'THRONE_ROOM' for r in rooms):
                largest_rm = max(rooms, key=lambda r: (r.bounds[1] - r.bounds[0]) * (r.bounds[3] - r.bounds[2]))
                largest_rm.role = 'THRONE_ROOM'
            floor_has_dining = True

        for rm in rooms:
            # Skip rooms that are too tiny to furnish safely
            rw = rm.bounds[1] - rm.bounds[0]
            rd = rm.bounds[3] - rm.bounds[2]
            if rw < 1.3 or rd < 1.3:
                continue
            rm_z_ceil = z_ceil
            if rm.role == 'THRONE_ROOM' and bool(getattr(props, 'has_double_height', False)):
                rm_z_ceil = z_floor + ctx.floor_h * 2.0 - 0.065
            try:
                _dress_single_room(bm, rm, z_floor, rm_z_ceil, rng, density, style, ctx=ctx,
                                   floor_has_dining=floor_has_dining)
            except Exception:
                continue
