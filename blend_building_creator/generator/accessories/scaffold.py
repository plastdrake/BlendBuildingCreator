"""Construction scaffold kit (SOLID / DRY).

Builds a timber pole scaffold around the current building so any footprint
reads as "under construction", plus optional staged material piles and a
yard crane. Reuses only generic builders (mesh_utils, crane, furniture,
warehouse) - no duplicated prop code.

Plot contract (from the user):
- SMALL 12x12, MEDIUM 20x20, LARGE 40x40, HUGE 100x100.
- The scaffold never fills the whole plot: ``padding`` metres of walkway are
  left clear around it (default 1.5 m, clamp 0.5-3.0 m).
- AUTO sizes the scaffold to the building itself plus a work margin.
"""

import math
import random

from mathutils import Matrix, Vector
from ..mesh_utils import create_beveled_box, create_box, create_cylinder
from ..materials import (
    MAT_INDEX_TIMBER,
    MAT_INDEX_WOOD,
    MAT_INDEX_ROPE,
    MAT_INDEX_TARP,
    MAT_INDEX_CUT_STONE,
    MAT_INDEX_IRON,
)

PLOT_SIZES = {
    'SMALL': 12.0,
    'MEDIUM': 20.0,
    'LARGE': 40.0,
    'HUGE': 100.0,
}

# Dressing scale per plot (DRY): bigger sites read busier with no extra
# properties to learn. Small sites stay quiet; huge sites get full yards.
LADDER_COUNT = {'AUTO': 1, 'SMALL': 1, 'MEDIUM': 2, 'LARGE': 3, 'HUGE': 4}
PILE_TIER = {'AUTO': 0, 'SMALL': 0, 'MEDIUM': 1, 'LARGE': 2, 'HUGE': 3}

# Pile footprints as (half-x, half-y) for pole threading: poles may stand
# right beside a stack (threaded around stock reads intentional) but never
# inside it. Circles would over-cover long thin piles and eat whole bays.
PILE_FOOTPRINT = {
    'stone': (1.22, 0.48),   # two ashlar courses side by side
    'rubble': (1.30, 1.30),  # scattered off-cuts read blobby
    'timber': (0.20, 0.98),  # plank pile laid along Y
    'barrel': (0.42, 0.42),
    'crate': (0.40, 0.40),
    'iron': (0.38, 0.38),
}


def scaffold_extents(plot_key, padding, bldg_w, bldg_d, props=None):
    """Return (sx, sy) scaffold footprint for the plot, honouring padding.

    Target is ``plot - 2 * padding``. The scaffold always encloses the
    building plus a 1.2 m work margin, but never exceeds ``plot - 0.5`` so
    at least a half-metre walkway survives even on oversized buildings.
    CUSTOM ignores plots/padding and uses the manual width/depth settings.
    """
    if plot_key == 'CUSTOM':
        w = float(getattr(props, 'scaffold_width', 9.0)) if props else 9.0
        d = float(getattr(props, 'scaffold_depth', 9.0)) if props else 9.0
        return min(99.0, max(3.0, w)), min(99.0, max(3.0, d))
    pad = min(3.0, max(0.5, float(padding)))
    if plot_key in PLOT_SIZES:
        plot = PLOT_SIZES[plot_key]
        target = plot - 2.0 * pad
        need_w = float(bldg_w) + 1.2
        need_d = float(bldg_d) + 1.2
        sx = max(target, need_w)
        sy = max(target, need_d)
        cap = plot - 0.5
        return min(sx, cap), min(sy, cap)
    # AUTO: just wrap the building with a work margin.
    return float(bldg_w) + 2.4, float(bldg_d) + 2.4


def scaffold_height(props, auto_h):
    """Pole height: manual Scaffold Height wins, 0 means automatic."""
    try:
        manual = float(getattr(props, 'scaffold_height', 0.0) or 0.0)
    except Exception:
        manual = 0.0
    if manual > 0.05:
        return max(2.5, min(30.0, manual))
    return max(2.5, float(auto_h or 6.0))


def _rng(seed, salt=0):
    return random.Random((int(seed) * 73856093 ^ int(salt * 83492791)) & 0x7FFFFFFF)


def _pole(bm, x, y, h, r=0.06):
    create_cylinder(
        bm, radius=r, height=h, segments=8,
        location=(x, y, h * 0.5),
        mat_index=MAT_INDEX_TIMBER,
    )


def _ledger(bm, x1, y1, x2, y2, z, thick=0.09):
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    ang = math.atan2(dy, dx)
    create_beveled_box(
        bm, size=(length, thick, thick),
        location=((x1 + x2) * 0.5, (y1 + y2) * 0.5, z),
        rotation=(0.0, 0.0, ang),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
    )


def _platform(bm, x0, x1, y0, y1, z, plank_w=0.28):
    w = abs(x1 - x0)
    d = abs(y1 - y0)
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    if w >= d:
        n = max(2, int(round(d / plank_w)))
        for i in range(n):
            py = y0 + (i + 0.5) * d / n
            create_beveled_box(
                bm, size=(w, d / n - 0.02, 0.05),
                location=(cx, py, z),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
            )
    else:
        n = max(2, int(round(w / plank_w)))
        for i in range(n):
            px = x0 + (i + 0.5) * w / n
            create_beveled_box(
                bm, size=(w / n - 0.02, d, 0.05),
                location=(px, cy, z),
                mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
            )


def _diagonal(bm, x1, y1, x2, y2, z0, z1, thick=0.07):
    """Beam between two 3D points (braces, ladder rails).

    Orientation is composed explicitly (yaw about Z, then pitch about Y)
    instead of an XYZ Euler triple: Blender applies the triple's Z rotation
    to the raw X axis first, which silently flattened every beam with a
    Y-run (side braces, ladder rails) into a horizontal floater.
    """
    dx, dy, dz = x2 - x1, y2 - y1, z1 - z0
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return
    horiz = math.hypot(dx, dy)
    yaw = math.atan2(dy, dx)
    pitch = -math.atan2(dz, horiz)
    mat = (Matrix.Translation(Vector(((x1 + x2) * 0.5,
                                        (y1 + y2) * 0.5,
                                        (z0 + z1) * 0.5)))
           @ Matrix.Rotation(yaw, 4, 'Z')
           @ Matrix.Rotation(pitch, 4, 'Y'))
    create_beveled_box(
        bm, size=(length, thick, thick),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006,
        transform_matrix=mat,
    )


def _rope_lashing(bm, x, y, z):
    create_cylinder(
        bm, radius=0.035, height=0.10, segments=8,
        location=(x, y, z),
        mat_index=MAT_INDEX_ROPE,
    )


def _leaning_ladder(bm, x, y_edge, z_landing, width=0.5):
    """Access ladder landing on the walkway platform.

    The rails are aimed straight through the platform's outer edge corner
    (feet planted below grade, tops running ~1 m past as a handhold), so
    contact is guaranteed by construction: the rail line contains the
    corner point. Rungs stay level while the rails lean at ~72 degrees.
    """
    zc = z_landing             # platform top surface
    ye = y_edge                # platform outer edge
    z0 = -0.15                 # feet planted below grade
    run = (zc - z0) / 3.3      # ~72-degree lean to the corner
    yf = ye - run
    L1 = math.hypot(run, zc - z0)
    dy, dz = run / L1, (zc - z0) / L1
    yt = ye + dy * 1.0         # handhold past the corner
    zt = zc + dz * 1.0
    for s in (-1.0, 1.0):
        _diagonal(bm, x + s * width * 0.5, yf,
                  x + s * width * 0.5, yt, z0, zt, thick=0.06)
    z = 0.25
    while z < zt - 0.15:
        f = (z - z0) / (zt - z0)
        ry = yf + (yt - yf) * f
        create_beveled_box(
            bm, size=(width, 0.05, 0.05),
            location=(x, ry, z),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.005,
        )
        z += 0.32


def _tarp_roof(bm, cx, cy, sx, sy, pole_h, lifts, seed=42):
    """Segmented canvas weather roof carried on a real timber support grid.

    Bearer beams sit directly on the pole tops (perimeter rows plus the
    interior pole rows on large sites), rafters cross them every ~2 m, and
    the canvas is laid in ~9 m segments resting on the rafters (stepped a
    hair per bay against shimmer). A batten grid clamps the canvas about
    every 3 m, an eave frame covers all four edges, and perimeter fascia
    boards hide the whole sandwich from outside. Ropes tie each segment
    down to the top lift. Nothing floats: sheets on rafters on bearers
    on poles, edges covered all round.
    """
    rng = _rng(seed, salt=208)
    # Support grid first: bearers on the pole rows, rafters across them.
    for by in _pole_rows(cy, sy, sx):
        create_beveled_box(
            bm, size=(sx, 0.12, 0.14),
            location=(cx, by, pole_h + 0.07),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
        )
    for px in _line_coords(cx - sx * 0.5, cx + sx * 0.5, step=2.0):
        create_beveled_box(
            bm, size=(0.09, sy + 0.2, 0.12),
            location=(px, cy, pole_h + 0.20),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006,
        )
    # Canvas in overlapping segments resting on the rafters. Sheets step
    # down a hair per bay (4 mm: kills coplanar shimmer, invisible as a
    # step) with a slim 0.1 m drip edge past the poles.
    n_seg = max(1, int(round(sx / 9.0)))
    seg_w = sx / n_seg
    z = pole_h + 0.30
    top = lifts[-1]
    for i in range(n_seg):
        seg_cx = cx - sx * 0.5 + (i + 0.5) * seg_w
        zi = z - i * 0.004
        create_box(
            bm, size=(seg_w + 0.2, sy + 0.2, 0.05),
            location=(seg_cx, cy, zi),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.01),
            mat_index=MAT_INDEX_TARP,
        )
        # Seam batten on the windward joint plus two mid-battens: clamping
        # roughly every 3 m so no wide canvas field ever lies naked.
        for bx in (seg_cx - seg_w * 0.5, seg_cx - seg_w * 0.5 + seg_w / 3.0,
                   seg_cx - seg_w * 0.5 + 2.0 * seg_w / 3.0):
            create_beveled_box(
                bm, size=(0.09, sy + 0.2, 0.06),
                location=(bx, cy, zi + 0.05),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005,
            )
        # Rope ties from the segment corners down to the top lift.
        drop = max(0.15, zi - top)
        for qx in (seg_cx - seg_w * 0.5 + 0.15, seg_cx + seg_w * 0.5 - 0.15):
            for qy in (cy - sy * 0.5, cy + sy * 0.5):
                create_cylinder(
                    bm, radius=0.025, height=drop, segments=6,
                    location=(qx, qy, zi - drop * 0.5),
                    mat_index=MAT_INDEX_ROPE,
                )
    # Eave frame: battens exactly along all four canvas edges, on the canvas.
    for ey in (cy - sy * 0.5 - 0.1, cy + sy * 0.5 + 0.1):
        create_beveled_box(
            bm, size=(sx + 0.2, 0.09, 0.06),
            location=(cx, ey, z + 0.05),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005,
        )
    for ex in (cx - sx * 0.5 - 0.1, cx + sx * 0.5 + 0.1):
        create_beveled_box(
            bm, size=(0.09, sy + 0.2, 0.06),
            location=(ex, cy, z + 0.05),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005,
        )
    # Fascia boards around the whole roof edge: they hide the bearer /
    # rafter / canvas sandwich from outside so the roof never reads as
    # layers floating over the poles.
    fz = pole_h + 0.15
    for ey in (cy - sy * 0.5 - 0.1, cy + sy * 0.5 + 0.1):
        create_beveled_box(
            bm, size=(sx + 0.32, 0.06, 0.55),
            location=(cx, ey, fz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
        )
    for ex in (cx - sx * 0.5 - 0.1, cx + sx * 0.5 + 0.1):
        create_beveled_box(
            bm, size=(0.06, sy + 0.2, 0.55),
            location=(ex, cy, fz),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008,
        )


def _line_coords(a0, a1, step=2.0):
    """Evenly spaced coordinates from ``a0`` to ``a1`` (~``step`` apart)."""
    span = a1 - a0
    n = max(2, int(round(span / step)) + 1)
    return [a0 + i * span / (n - 1) for i in range(n)]


def _grid_bays(span):
    """Number of ~6 m bays across ``span`` (capped so huge sites stay bounded)."""
    return min(6, max(1, int(round(span / 6.0))))


def _pole_positions(cx, cy, sx, sy):
    """Every pole coordinate as ``(x, y, interior)``.

    Single source of truth: the frame builds these, and the layout solver
    treats them as fixed obstacles so stockpiles slide between poles instead
    of pile positions deleting poles (which read as floating frames).
    """
    x0, x1 = cx - sx * 0.5, cx + sx * 0.5
    y0, y1 = cy - sy * 0.5, cy + sy * 0.5
    xs = _line_coords(x0, x1)
    ys = _line_coords(y0, y1)
    pos = [(px, py, False) for px in xs for py in (y0, y1)]
    pos += [(px, py, False) for py in ys[1:-1] for px in (x0, x1)]
    x_rows = _pole_rows(cx, sx, sy)
    y_rows = _pole_rows(cy, sy, sx)
    pos += [(px, py, True) for px in x_rows[1:-1] for py in y_rows[1:-1]]
    return pos


def _size_tier(plot_key, sx, sy):
    """Dressing tier from the actual scaffold size (CUSTOM derives its own)."""
    if plot_key in LADDER_COUNT:
        return plot_key
    m = max(float(sx), float(sy))
    if m < 14.0:
        return 'SMALL'
    if m < 30.0:
        return 'MEDIUM'
    if m < 70.0:
        return 'LARGE'
    return 'HUGE'


def _pole_rows(c, s, other):
    """Coordinates of every pole row along one axis: perimeter pair plus interior rows.

    Sites under 12 m across get perimeter poles only; larger sites grow
    interior pole rows on ~6 m bays so the roof grid and long ledgers are
    visibly carried instead of spanning impossible distances.
    """
    if min(s, other) <= 12.0:
        return [c - s * 0.5, c + s * 0.5]
    n = _grid_bays(s)
    return [c - s * 0.5 + i * s / n for i in range(n + 1)]


def build_scaffold_frame(bm, cx, cy, sx, sy, height, levels=2, seed=42,
                         ladders=1, exclude=(), jog=(), keepout=None):
    """Timber pole scaffold rectangle centred on (cx, cy).

    Poles every ~2 m around the perimeter (plus interior rows on sites over
    12 m across), ledgers at each lift, working platforms on the front/back
    faces per lift, diagonal braces on alternating bays and leaning access
    ladders climbing the front face onto the first walkway platform.
    Returns ``(pole_height, lifts)`` so callers can seat the tarp roof.

    ``exclude`` skips poles outright (interior crane masts only: the mast
    visibly replaces them). ``jog`` is a list of ``(x, y, hx, hy)`` stockpile
    footprint rects: a pole inside one slides along its face (then inward)
    instead of vanishing, so the frame stays dense and every ledger/brace
    ties pole to pole. Rects (not circles) so poles can thread right
    beside a long stack without triggering.
    """
    rng = _rng(seed, salt=913)
    height = max(2.5, float(height))
    levels = min(6, max(1, int(levels)))
    x0, x1 = cx - sx * 0.5, cx + sx * 0.5
    y0, y1 = cy - sy * 0.5, cy + sy * 0.5

    def _skipped(px, py):
        for ex, ey, er in exclude:
            if (px - ex) ** 2 + (py - ey) ** 2 < (er + 0.15) ** 2:
                return True
        return False

    def _jog(px, py, tangent, inward):
        """Final pole position: on-grid if clear, else slid around stock.

        Along-face candidates keep the row crisp; inward ones (which also
        respect the tight building rect) dodge piles sitting on the line.
        Clearance is measured to the pile footprint rect, so threading
        beside a stack is allowed and only true overlaps jog.
        Returns None only when fully hemmed (vanishingly rare).
        """
        def _clear(qx, qy):
            if keepout is not None:
                kx0, kx1, ky0, ky1 = keepout
                if kx0 - 0.1 < qx < kx1 + 0.1 and ky0 - 0.1 < qy < ky1 + 0.1:
                    return False
            for ex, ey, hx, hy in jog:
                ox = max(abs(qx - ex) - hx, 0.0)
                oy = max(abs(qy - ey) - hy, 0.0)
                if ox * ox + oy * oy < 0.12 * 0.12:
                    return False
            return True
        if _clear(px, py):
            return (px, py)
        tx, ty = tangent
        ix, iy = inward
        for dx, dy in ((tx * 0.3, ty * 0.3), (tx * -0.3, ty * -0.3),
                       (tx * 0.6, ty * 0.6), (tx * -0.6, ty * -0.6),
                       (tx * 0.9, ty * 0.9), (tx * -0.9, ty * -0.9),
                       (tx * 1.2, ty * 1.2), (tx * -1.2, ty * -1.2),
                       (ix * 0.5, iy * 0.5), (ix * 0.9, iy * 0.9)):
            qx, qy = px + dx, py + dy
            if not (x0 - 1e-6 <= qx <= x1 + 1e-6
                    and y0 - 1e-6 <= qy <= y1 + 1e-6):
                continue
            if _clear(qx, qy):
                return (qx, qy)
        return None

    xs = _line_coords(x0, x1)
    ys = _line_coords(y0, y1)

    # Poles per face row ( jogged around stock, never silently dropped ),
    # plus interior rows. Ledgers/braces below join consecutive ACTUAL
    # poles so every member lands on timber.
    front, back, left, right = [], [], [], []
    corners = []
    for ix, px in enumerate(xs):
        for py, row in ((y0, front), (y1, back)):
            if _skipped(px, py):
                continue
            q = _jog(px, py, (1.0, 0.0), (0.0, -1.0 if py < cy else 1.0))
            if q is None:
                continue
            _pole(bm, q[0], q[1], height, r=0.055 + rng.random() * 0.015)
            row.append(q)
            if (ix == 0 or ix == len(xs) - 1) and (py == y0 or py == y1):
                corners.append(q)
    for py in ys[1:-1]:
        for px, row, inw in ((x0, left, (1.0, 0.0)), (x1, right, (-1.0, 0.0))):
            if _skipped(px, py):
                continue
            q = _jog(px, py, (0.0, 1.0), inw)
            if q is None:
                continue
            _pole(bm, q[0], q[1], height, r=0.055 + rng.random() * 0.015)
            row.append(q)
    for px in _pole_rows(cx, sx, sy)[1:-1]:
        for py in _pole_rows(cy, sy, sx)[1:-1]:
            if _skipped(px, py):
                continue
            q = _jog(px, py, (1.0, 0.0), (0.0, 1.0))
            if q is None:
                continue
            _pole(bm, q[0], q[1], height, r=0.05 + rng.random() * 0.01)

    # Lifts spread from a reachable first lift (~2 m) up to just under the
    # pole tops, so no tall bare cage sticks out above the working level.
    top = height - 0.5
    if levels == 1:
        lifts = [round(min(max(top, 1.9), height - 0.4), 2)]
    else:
        first = 2.0
        lifts = [round(min(max(first + i * (top - first) / (levels - 1), 1.9),
                           height - 0.4), 2)
                 for i in range(levels)]

    for lv in lifts:
        # Ledgers join consecutive ACTUAL poles so kinked rows stay tied.
        for row in (front, back, left, right):
            for (ax, ay), (bx, by) in zip(row[:-1], row[1:]):
                _ledger(bm, ax, ay, bx, by, lv)
        # Platforms on front/back faces (alternate per lift to save polys).
        _platform(bm, x0, x1, y0 - 0.55, y0 + 0.05, lv + 0.06)
        if lifts.index(lv) % 2 == 1:
            _platform(bm, x0, x1, y1 - 0.05, y1 + 0.55, lv + 0.06)
        # Lashings on the (possibly jogged) corner poles.
        for q in corners:
            _rope_lashing(bm, q[0], q[1], lv)

    # Diagonal braces on alternating bays, tied pole to pole.
    for row, flip in ((front, False), (back, True), (left, False)):
        for i, ((ax, ay), (bx, by)) in enumerate(zip(row[:-1], row[1:])):
            if i % 2 == 0:
                if not flip:
                    _diagonal(bm, ax, ay, bx, by, 0.2, lifts[0])
                elif len(lifts) > 1:
                    _diagonal(bm, bx, by, ax, ay, lifts[0], lifts[-1])

    # Leaning access ladders on the front face, rails resting against the
    # walkway platform edge so workers climb straight up onto the first
    # lift. Spread across the face on larger sites.
    n_lad = min(4, max(1, int(ladders)))
    lad_step = min(6.0, sx * 0.18)
    for i in range(n_lad):
        lx = cx + (i - (n_lad - 1) * 0.5) * lad_step
        _leaning_ladder(bm, lx, y0 - 0.55, lifts[0] + 0.09, width=0.5)
    return height, lifts


def _pile_plan(cx, cy, sx, sy, plot_key):
    """Authoritative stockpile layout: one entry per cluster.

    Each entry is ``(kind, x, y, radius, data)``. Single source of truth:
    the builder and the overlap relaxation read this plan, so a cluster can
    never disagree with itself. The base set suits a small site; ``PILE_TIER``
    adds clusters for larger plots. Poles are NOT avoided here: the frame
    jogs standards around stock instead, so the grid stays dense.
    """
    hx, hy = sx * 0.5 - 1.0, sy * 0.5 - 1.0
    tier = PILE_TIER.get(plot_key, 0)
    plan = [
        ('stone', cx - hx, cy + hy, 1.4, (6, 11)),
        ('stone', cx + hx, cy + hy - 1.0, 1.4, (4, 12)),
        ('rubble', cx - hx + 2.2, cy + hy - 0.5, 1.6, (4, 13)),
        ('timber', cx - hx + 0.4, cy - hy + 1.0, 1.1, ()),
        ('barrel', cx + hx - 0.4, cy - hy, 0.6, (0.2,)),
        ('barrel', cx + hx + 0.3, cy - hy + 0.4, 0.6, (-0.1,)),
        ('crate', cx + hx - 0.5, cy - hy + 1.3, 0.75, (0.15, 0.62, 0.55, 'DIAGONAL')),
        ('iron', cx - hx + 1.2, cy - hy + 0.6, 0.5, ()),
    ]
    if tier >= 1:
        # Medium+: second stone course mid-back and timber along the flank.
        plan += [
            ('stone', cx, cy + hy, 1.4, (6, 21)),
            ('timber', cx + hx - 0.4, cy, 1.1, ()),
            ('crate', cx - hx + 0.3, cy - 1.5, 0.75, (-0.2, 0.55, 0.5, 'CROSS')),
        ]
    if tier >= 2:
        # Large+: barrel store on the left flank and rubble up front.
        plan += [
            ('barrel', cx - hx, cy + 0.5, 0.6, (0.5,)),
            ('barrel', cx - hx + 0.7, cy - 0.2, 0.6, (-0.3,)),
            ('rubble', cx + hx - 2.0, cy - hy + 0.5, 1.6, (5, 23)),
            ('crate', cx + hx - 1.4, cy + hy - 0.6, 0.75, (0.3, 0.62, 0.55, 'DIAGONAL')),
        ]
    if tier >= 3:
        # Huge: full working yard - courses on every side, twin timber.
        plan += [
            ('stone', cx - hx, cy - hy + 2.2, 1.4, (6, 31)),
            ('stone', cx + hx, cy - 1.0, 1.4, (5, 32)),
            ('timber', cx - hx * 0.3, cy + hy - 1.5, 1.1, ()),
            ('rubble', cx + 1.5, cy + hy - 2.0, 1.6, (5, 33)),
        ]
        for k, (ox, oy) in enumerate(((0.4, -0.6), (-0.5, 0.2), (1.2, 0.8))):
            plan.append(('crate', cx + hx * 0.2 + ox, cy - hy + 2.0 + oy,
                         0.75, (0.1 * k, 0.58, 0.5, 'DIAGONAL')))
    return plan


def _relax_pile_plan(plan, fixed, cx, cy, sx, sy, keepout, seed):
    """Push overlapping clusters apart (deterministic, seeded).

    ``fixed`` are immovable obstacles (interior crane spots); ``keepout``
    is an optional building rect piles may not enter. Everything stays
    clamped inside the scaffold. Returns resolved ``[(x, y), ...]`` in plan
    order. Small props (barrels/crates/iron) may kiss at 0.8x radii; stone,
    rubble and timber demand full clearance.
    """
    rng = _rng(seed, salt=552)
    pts = [[float(x), float(y)] for (_, x, y, _, _) in plan]
    kinds = [k for (k, _, _, _, _) in plan]
    radii = [float(r) for (_, _, _, r, _) in plan]

    def _factor(ki, kj):
        bulky = ('stone', 'rubble', 'timber')
        if ki in bulky or kj in bulky:
            return 1.0
        return 0.8

    x_lo, x_hi = cx - sx * 0.5 + 0.7, cx + sx * 0.5 - 0.7
    y_lo, y_hi = cy - sy * 0.5 + 0.7, cy + sy * 0.5 - 0.7

    def _clamp(p):
        # Keep-out first, scaffold bounds last: a pile that cannot satisfy
        # both (cramped wrap site) ends inside the keep-out and is dropped
        # by _resolve_piles instead of oscillating forever.
        if keepout is not None:
            kx0, kx1, ky0, ky1 = keepout
            if kx0 < p[0] < kx1 and ky0 < p[1] < ky1:
                dl, dr = p[0] - kx0, kx1 - p[0]
                db, dt = p[1] - ky0, ky1 - p[1]
                m = min(dl, dr, db, dt)
                if m == dl:
                    p[0] = kx0
                elif m == dr:
                    p[0] = kx1
                elif m == db:
                    p[1] = ky0
                else:
                    p[1] = ky1
        p[0] = min(x_hi, max(x_lo, p[0]))
        p[1] = min(y_hi, max(y_lo, p[1]))

    for p in pts:
        _clamp(p)
    for _ in range(30):
        order = list(range(len(pts)))
        rng.shuffle(order)
        for i in order:
            xi, yi = pts[i]
            for j in range(len(pts)):
                if i == j:
                    continue
                dx, dy = xi - pts[j][0], yi - pts[j][1]
                need = (radii[i] + radii[j]) * _factor(kinds[i], kinds[j])
                d2 = dx * dx + dy * dy
                if d2 < need * need and d2 > 1e-9:
                    d = math.sqrt(d2)
                    push = (need - d) * 0.5
                    ux, uy = dx / d, dy / d
                    pts[i][0] += ux * push
                    pts[i][1] += uy * push
                    pts[j][0] -= ux * push
                    pts[j][1] -= uy * push
                    _clamp(pts[i])
                    _clamp(pts[j])
            for fx, fy, fr in fixed:
                dx, dy = xi - fx, yi - fy
                # refresh: pts[i] may have moved above; re-read
                xi, yi = pts[i]
                dx, dy = xi - fx, yi - fy
                need = radii[i] + fr
                d2 = dx * dx + dy * dy
                if d2 < need * need and d2 > 1e-9:
                    d = math.sqrt(d2)
                    pts[i][0] = fx + dx / d * need
                    pts[i][1] = fy + dy / d * need
                    _clamp(pts[i])
                    xi, yi = pts[i]
    return pts


def _resolve_piles(plan, pts, cx, cy, sx, sy, keepout):
    """Filter relaxed piles down to the ones that genuinely fit.

    A pile survives only if its centre is inside the scaffold interior and
    fully clear of the building keep-out (grown by its own radius). On a
    cramped wrap site with no staging room this drops piles instead of
    burying them in walls or poles: fewer honest piles beat clipping ones.
    Returns ``[(kind, x, y, radius, data), ...]``.
    """
    resolved = []
    for (kind, _, _, r, data), (x, y) in zip(plan, pts):
        if abs(x - cx) > sx * 0.5 - 0.7 or abs(y - cy) > sy * 0.5 - 0.7:
            continue
        if keepout is not None:
            kx0, kx1, ky0, ky1 = keepout
            if kx0 - r < x < kx1 + r and ky0 - r < y < ky1 + r:
                continue
        resolved.append((kind, x, y, r, data))
    return resolved


def build_construction_piles(bm, plan, seed=42):
    """Stage stockpiles from a resolved ``_pile_plan`` (positions + entries).

    ``plan`` is ``[(kind, x, y, radius, data), ...]`` with ``(x, y)`` already
    de-overlapped by :func:`_relax_pile_plan`.
    """
    from .furniture import build_crate, build_barrel
    from .quarry import build_cut_block_stack, build_rubble_pile

    rng = _rng(seed, salt=551)
    for kind, x, y, _r, data in plan:
        if kind == 'stone':
            count, salt = data
            build_cut_block_stack(bm, x, y, z_ground=0.0,
                                  count=count, seed=seed + salt)
        elif kind == 'rubble':
            count, salt = data
            build_rubble_pile(bm, x, y, count=count, seed=seed + salt)
        elif kind == 'timber':
            _timber_pile(bm, x, y, rng)
        elif kind == 'barrel':
            (ang,) = data
            build_barrel(bm, x, y, z_ground=0.0, ang=ang)
        elif kind == 'crate':
            ang, size, height, brace = data
            build_crate(bm, x, y, z_ground=0.0, ang=ang,
                        size=size, height=height, brace_style=brace)
        elif kind == 'iron':
            create_cylinder(
                bm, radius=0.30, height=0.5, segments=10,
                location=(x, y, 0.25),
                mat_index=MAT_INDEX_IRON,
            )


def _timber_pile(bm, x, y, rng):
    """One stacked plank pile on the ground (shared by all pile tiers).

    Laid along Y so a corner pile never pokes past the scaffold poles.
    """
    for k in range(5):
        create_beveled_box(
            bm, size=(0.24, 1.8 - k * 0.06, 0.12),
            location=(x, y, 0.12 + k * 0.13),
            rotation=(0.0, 0.0, (rng.random() - 0.5) * 0.06),
            mat_index=MAT_INDEX_WOOD, bevel_amount=0.006,
        )


def _crane_plan(ccx, ccy, sx, sy, plot_key, keepout):
    """Crane spots, preferring inside the scaffold.

    The primary crane stands inside at the back with the stockpiles; LARGE
    adds one interior mate, HUGE two. A spot that would land in the building
    keep-out (cramped wrap site) falls back to the outside yard position so
    no mast is ever buried in a wall. Each spot is ``(x, y, rot, mast, jib)``.
    Spots are resolved before poles go up: stockpiles relax around the masts
    and the frame punches pole holes under them.
    """
    outside = (ccx + sx * 0.5 + 1.5, ccy - sy * 0.5 - 1.0, 0.6, 4.0, 3.4)
    back_y = ccy + sy * 0.5 - 2.2

    def _blocked(x, y, r=1.6):
        if keepout is None:
            return False
        kx0, kx1, ky0, ky1 = keepout
        return kx0 - r < x < kx1 + r and ky0 - r < y < ky1 + r

    tier = _size_tier(plot_key, sx, sy)
    if tier == 'HUGE':
        cands = [(ccx, back_y, 2.6, 5.0, 4.2),
                 (ccx - sx * 0.25, back_y, 2.6, 5.0, 4.2),
                 (ccx + sx * 0.25, back_y, -2.6, 5.0, 4.2)]
    elif tier == 'LARGE':
        cands = [(ccx, back_y, 2.6, 5.0, 4.2),
                 (ccx - sx * 0.25, back_y, 2.6, 5.0, 4.2)]
    else:
        cands = [(ccx, back_y, 0.6, 4.0, 3.4)]
    spots = [c for c in cands if not _blocked(c[0], c[1])]
    if not spots:
        spots = [outside]
    return spots


def _build_site_cranes(bm, spots):
    """Raise every crane in a ``_crane_plan``."""
    from .crane import build_courtyard_crane
    for qx, qy, rot, mast, jib in spots:
        build_courtyard_crane(bm, yard_x=qx, yard_y=qy, z_ground=0.0,
                              mast_height=mast, jib_length=jib,
                              rot_angle=rot)


def _building_keepout(ctx, margin=0.8):
    """Building footprint (main + wings) expanded as a keep-out rect.

    Returns ``(x0, x1, y0, y1)`` in plot space, or ``None`` when there is
    nothing to avoid (empty sites). Stockpiles use the roomy default
    margin; pole jogs use a tight one (the scaffold always clears the
    bare walls, so grid poles never start inside it).
    """
    try:
        bw = float(getattr(ctx, 'base_w', 0.0))
        bd = float(getattr(ctx, 'base_d', 0.0))
        x0, x1 = -bw * 0.5 - margin, bw * 0.5 + margin
        y0, y1 = -bd * 0.5 - margin, bd * 0.5 + margin
        for w in getattr(ctx, 'wings', []) or []:
            b = w.get('base', None)
            if b and len(b) == 4:
                x0, x1 = min(x0, b[0] - margin), max(x1, b[1] + margin)
                y0, y1 = min(y0, b[2] - margin), max(y1, b[3] + margin)
        return (x0, x1, y0, y1)
    except Exception:
        return None


def build_construction_site(bm, props, ctx, tier):
    """Plot-space scaffold composer called from the accessory dispatch.

    Scaffold footprint follows ``construction_plot`` + ``scaffold_padding``
    (walk-around guarantee); height follows the actual building so every
    lift serves a real storey. Tarps, piles and crane are independent
    toggles. Only used in WRAP_BUILDING mode (empty sites go through
    :func:`build_empty_construction_site` instead).
    """
    plot_key = getattr(props, 'construction_plot', 'AUTO')
    padding = getattr(props, 'scaffold_padding', 1.5)
    levels = getattr(props, 'scaffold_levels', 2)
    seed = getattr(ctx, 'seed', 42)

    bldg_w = float(getattr(ctx, 'base_w', 8.0))
    bldg_d = float(getattr(ctx, 'base_d', 8.0))
    # Wings extend the footprint: enclose main + wings so poles clear them.
    try:
        _x0, _x1 = -bldg_w * 0.5, bldg_w * 0.5
        _y0, _y1 = -bldg_d * 0.5, bldg_d * 0.5
        for w in getattr(ctx, 'wings', []) or []:
            b = w.get('base', None)
            if b and len(b) == 4:
                _x0, _x1 = min(_x0, b[0]), max(_x1, b[1])
                _y0, _y1 = min(_y0, b[2]), max(_y1, b[3])
        bldg_w, bldg_d = _x1 - _x0, _y1 - _y0
    except Exception:
        pass
    # Building centre in plot space (after setback translation).
    # ctx does not track the translation, so rebuild it from props.
    setback = float(getattr(props, 'plot_setback', 0.0) or 0.0)
    off_x = float(getattr(props, 'plot_offset_x', 0.0) or 0.0)
    ccx, ccy = off_x, setback

    sx, sy = scaffold_extents(plot_key, padding, bldg_w, bldg_d, props)
    tier = _size_tier(plot_key, sx, sy)

    total_h = float(getattr(ctx, 'total_height', 6.0) or 6.0)
    scaf_h = scaffold_height(props, total_h + 1.0)

    # Layout before lumber: stockpiles relax around the fixed crane masts
    # (poles jog around piles in the frame, so the grid stays dense).
    keepout = _building_keepout(ctx)
    plan = _pile_plan(ccx, ccy, sx, sy, tier)
    want_cranes = bool(getattr(props, 'construction_crane', False))
    spots = _crane_plan(ccx, ccy, sx, sy, plot_key, keepout) if want_cranes else []
    inside = [(qx, qy) for qx, qy, _, _, _ in spots
              if abs(qx - ccx) <= sx * 0.5 and abs(qy - ccy) <= sy * 0.5]
    fixed = [(qx, qy, 1.5) for qx, qy in inside]
    pts = _relax_pile_plan(plan, fixed, ccx, ccy, sx, sy, keepout, seed)
    resolved = _resolve_piles(plan, pts, ccx, ccy, sx, sy, keepout)
    jog = [(x, y, *PILE_FOOTPRINT.get(k, (r, r))) for (k, x, y, r, _) in resolved]
    exclude = [(qx, qy, 1.6) for qx, qy in inside]

    _h, lifts = build_scaffold_frame(bm, ccx, ccy, sx, sy, scaf_h,
                                     levels=levels, seed=seed,
                                     ladders=LADDER_COUNT.get(tier, 1),
                                     exclude=exclude, jog=jog,
                                     keepout=_building_keepout(ctx, margin=0.15))

    if getattr(props, 'scaffold_tarp', True):
        _tarp_roof(bm, ccx, ccy, sx, sy, _h, lifts, seed=seed)

    if getattr(props, 'construction_piles', True):
        build_construction_piles(bm, resolved, seed)

    if want_cranes:
        _build_site_cranes(bm, spots)


def build_empty_construction_site(bm, props, ctx):
    """Scaffold-only site composer: scaffold + piles + crane, nothing else.

    No walls, floors, roof or footing are built. The scaffold footprint
    follows ``construction_plot`` + ``scaffold_padding`` exactly (no need to
    enclose a real building, so no work-margin growth); height follows the
    intended storeys (``num_floors`` x ``floor_height``, roof excluded since
    nothing is roofed yet) so lifts serve the future floors.
    """
    plot_key = getattr(props, 'construction_plot', 'AUTO')
    padding = getattr(props, 'scaffold_padding', 1.5)
    levels = getattr(props, 'scaffold_levels', 2)
    seed = getattr(ctx, 'seed', 42)
    pad = min(3.0, max(0.5, float(padding)))

    setback = float(getattr(props, 'plot_setback', 0.0) or 0.0)
    off_x = float(getattr(props, 'plot_offset_x', 0.0) or 0.0)
    ccx, ccy = off_x, setback

    if plot_key == 'CUSTOM':
        sx, sy = scaffold_extents(plot_key, pad, 0.0, 0.0, props)
    elif plot_key in PLOT_SIZES:
        plot = PLOT_SIZES[plot_key]
        sx = sy = plot - 2.0 * pad
    else:
        # AUTO with no building: scaffold the intended footprint + margin.
        fw = max(3.0, float(getattr(ctx, 'base_w', 6.0)))
        fd = max(3.0, float(getattr(ctx, 'base_d', 6.0)))
        sx, sy = fw + 2.4, fd + 2.4
    tier = _size_tier(plot_key, sx, sy)

    # Intended scaffold height = future wall height + 1 m working top
    # (roof excluded: nothing is roofed yet, so don't build air).
    auto_h = (max(2.5, float(getattr(ctx, 'found_h', 0.0) or 0.0)
              + max(1, int(getattr(ctx, 'num_floors', 1))) * float(getattr(ctx, 'floor_h', 2.8)) + 1.0))
    scaf_h = scaffold_height(props, auto_h)

    # Same plan-first order as the wrap composer, but with no building
    # keep-out: the whole interior is a free working yard.
    plan = _pile_plan(ccx, ccy, sx, sy, tier)
    want_cranes = bool(getattr(props, 'construction_crane', False))
    spots = _crane_plan(ccx, ccy, sx, sy, plot_key, None) if want_cranes else []
    inside = [(qx, qy) for qx, qy, _, _, _ in spots
              if abs(qx - ccx) <= sx * 0.5 and abs(qy - ccy) <= sy * 0.5]
    fixed = [(qx, qy, 1.5) for qx, qy in inside]
    pts = _relax_pile_plan(plan, fixed, ccx, ccy, sx, sy, None, seed)
    resolved = _resolve_piles(plan, pts, ccx, ccy, sx, sy, None)
    jog = [(x, y, *PILE_FOOTPRINT.get(k, (r, r))) for (k, x, y, r, _) in resolved]
    exclude = [(qx, qy, 1.6) for qx, qy in inside]

    _h, lifts = build_scaffold_frame(bm, ccx, ccy, sx, sy, scaf_h,
                                     levels=levels, seed=seed,
                                     ladders=LADDER_COUNT.get(tier, 1),
                                     exclude=exclude, jog=jog,
                                     keepout=None)

    if getattr(props, 'scaffold_tarp', True):
        _tarp_roof(bm, ccx, ccy, sx, sy, _h, lifts, seed=seed)

    if getattr(props, 'construction_piles', True):
        build_construction_piles(bm, resolved, seed)

    if want_cranes:
        _build_site_cranes(bm, spots)
