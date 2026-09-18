"""Reusable stone curtain-wall enclosure with a rampart walk and crenellations.

A masonry perimeter wall (the "curtain") that rings the whole compound:

- battered cut-stone plinth running around the base,
- ashlar wall body with *real* arrow-slit loopholes cut clean through it,
- cut-stone string course at the wall head and a raised inner wall-walk,
- crenellated merlons along the exposed outer edge,
- a cut-stone gatehouse (flanking piers, lintel arch and coping) over the gate.

The curtain wall supersedes the timber palisade on the military presets but is
reusable on any footprint through the Curtain Wall toggle. Placement mirrors the
palisade so the corner bastion towers, walls, gate and banners all share one
defensive line (see :func:`palisade.fortification_offset`).
"""

import math
from ..mesh_utils import create_beveled_box
from ..walls import build_wall_with_opening
from ..openings import build_arrow_slit
from ..materials import MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_TIMBER
from .battlement import build_battlement_run
from .palisade import (
    compound_bounds, fortification_offset, fortification_depth_extra,
)


def _subtract_gaps(total, gaps):
    """Return the (u0, u1) spans of a run left after removing each gap."""
    segs = [(0.0, total)]
    for g0, g1 in (gaps or []):
        c0, c1 = min(g0, g1), max(g0, g1)
        new_segs = []
        for s0, s1 in segs:
            if c1 <= s0 or c0 >= s1:
                new_segs.append((s0, s1))
                continue
            if c0 > s0 + 0.05:
                new_segs.append((s0, c0))
            if c1 < s1 - 0.05:
                new_segs.append((c1, s1))
        segs = new_segs
    return segs


def build_curtain_wall_run(bm, p_start, p_end, outward, ground_z=0.0,
                           height=3.2, thickness=0.55, plinth_h=0.45,
                           walk_width=0.95, merlon_h=0.78,
                           slits=True, slit_spacing=3.0, gate=None,
                           plinth_end=(0.0, 0.0), seed=42):
    """Build one straight curtain-wall run between two (x, y) points.

    ``outward`` is the horizontal normal the merlons and arrow slits face.
    ``gate`` is an optional ``{'u0', 'u1', 'h'}`` gate opening: the plinth is
    broken across it, the wall keeps a lintel band above it (via the wall
    builder), and the wall-walk and battlements run straight over the top.

    ``plinth_end`` shifts the plinth in (+) or out (-) at the start/end of the
    run. Where a run buries its head inside a corner bastion the caller pushes
    the plinth a little further in so it laps well under the tower's own plinth
    band rather than stopping flush against it (which read as a notch).
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.6:
        return
    ux, uy = dx / length, dy / length
    ang = math.atan2(dy, dx)
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = -uy, ux
    else:
        ox, oy = ox / on, oy / on

    def at(u, lateral=0.0):
        return (x1 + ux * u + ox * lateral, y1 + uy * u + oy * lateral)

    walk_top = ground_z + height
    gate_gap = None
    if gate is not None:
        gate_gap = (min(gate['u0'], gate['u1']), max(gate['u0'], gate['u1']))
    plinth_spans = _subtract_gaps(length, [gate_gap] if gate_gap else None)
    if plinth_end and plinth_spans:
        s_trim, e_trim = plinth_end
        spans = list(plinth_spans)
        spans[0] = (spans[0][0] + s_trim, spans[0][1])
        spans[-1] = (spans[-1][0], spans[-1][1] - e_trim)
        plinth_spans = spans
    walk_spans = [(0.0, length)]

    # 1. Battered cut-stone plinth (broken only across the gate).
    for u0, u1 in plinth_spans:
        if u1 - u0 < 0.2:
            continue
        cx, cy = at((u0 + u1) * 0.5)
        create_beveled_box(bm, size=(u1 - u0, thickness + 0.34, plinth_h),
                           location=(cx, cy, ground_z + plinth_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 2. Ashlar wall body carrying the gate lintel band and the arrow slits.
    slit_w, slit_h = 0.18, 0.88
    slit_cz = ground_z + max(plinth_h + 0.40, height * 0.52)
    open_ops = []
    if gate is not None:
        open_ops.append({'u_start': gate_gap[0], 'u_end': gate_gap[1],
                         'z_start': ground_z, 'z_end': ground_z + gate['h']})
    slit_centers = []
    if slits:
        n_slits = max(1, int(length / slit_spacing))
        step = length / n_slits
        for i in range(n_slits):
            uc = (i + 0.5) * step
            if gate_gap and gate_gap[0] - 0.6 <= uc <= gate_gap[1] + 0.6:
                continue
            if uc < 0.9 or uc > length - 0.9:
                continue
            open_ops.append({'u_start': uc - slit_w * 0.5, 'u_end': uc + slit_w * 0.5,
                             'z_start': slit_cz - slit_h * 0.5,
                             'z_end': slit_cz + slit_h * 0.5})
            slit_centers.append(uc)
    build_wall_with_opening(bm, p_start, p_end, ground_z, walk_top, thickness,
                            open_ops, mat_ext=MAT_INDEX_STONE,
                            normal_vec=(ox, oy), tier='TIER_3',
                            physical_siding=False, seed=seed)

    # 3. Cut-stone string course at the wall head (full thickness).
    for u0, u1 in walk_spans:
        cx, cy = at((u0 + u1) * 0.5)
        create_beveled_box(bm, size=(u1 - u0, thickness + 0.18, 0.16),
                           location=(cx, cy, walk_top + 0.08),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 4. Inner wall-walk deck, seated just behind the parapet.
    for u0, u1 in walk_spans:
        cx, cy = at((u0 + u1) * 0.5, -(thickness * 0.5 + walk_width * 0.5 - 0.05))
        create_beveled_box(bm, size=(u1 - u0, walk_width, 0.14),
                           location=(cx, cy, walk_top + 0.16),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 5. Crenellated merlons along the exposed outer edge.
    par_t = 0.30
    off_out = thickness * 0.5 - par_t * 0.5 + 0.02
    for u0, u1 in walk_spans:
        if u1 - u0 < 0.8:
            continue
        build_battlement_run(bm, at(u0, off_out), at(u1, off_out),
                             walk_top + 0.16, height=merlon_h,
                             thickness=par_t, style='STONE')

    # 6. Dress each cut slit with cut-stone reveals.
    for uc in slit_centers:
        cx, cy = at(uc)
        build_arrow_slit(bm, center=(cx, cy, slit_cz), normal_axis=(ox, oy),
                         wall_thickness=thickness, slit_w=slit_w, slit_h=slit_h,
                         has_transom=False)


def build_gate_house(bm, cx, cy, outward, gap_w, ground_z=0.0, thickness=0.55,
                     gate_h=2.7):
    """Cut-stone gatehouse framing the front gate: flanking piers proud of the
    wall, a lintel arch over the opening and stepped coping caps. The wall body
    itself supplies the masonry above the gate; this only dresses the opening."""
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on > 1e-5:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox            # wall tangent
    # Rotate the frame members about the *wall tangent* (not the outward normal)
    # or every box ends up turned 90 degrees across the gate.
    ang = math.atan2(ty, tx)
    # Pull the piers in so their inner faces cover the masonry reveal at the
    # edge of the opening, and keep them low and plain (no cap blocks) so the
    # lintel alone closes the top of the frame.
    half_outer = gap_w * 0.5 + 0.22
    # Push the whole frame proud of the wall face so it is not half-buried in
    # the masonry, and dress it in timber to read as a gate frame.
    push = 0.12
    # Deep members: the frame reaches well through the wall so none of its
    # faces land coplanar with the masonry (which z-fights) and the timber
    # covers the recessed stone reveal of the opening.
    frame_depth = thickness + 0.40

    for s in (-1.0, 1.0):
        px = cx + tx * (s * half_outer) + ox * push
        py = cy + ty * (s * half_outer) + oy * push
        pier_h = gate_h + 0.20
        create_beveled_box(bm, size=(0.62, frame_depth, pier_h),
                           location=(px, py, ground_z + pier_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # Deep lintel band across the opening, seated proud of the wall face and
    # reaching back through the wall so it hides the stone head of the opening.
    create_beveled_box(bm, size=(gap_w + 0.52, frame_depth, 0.32),
                       location=(cx + ox * push, cy + oy * push, ground_z + gate_h + 0.16),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)


def build_curtain_wall_enclosure(bm, props, ctx, height=None, thickness=None,
                                 offset=None):
    """Enclose the whole compound with a stone curtain wall and front gatehouse.

    Corner bastion towers are stitched in by starting every run at the tower
    footprint, mirroring :func:`palisade.build_palisade_enclosure`.
    Returns (x_min, x_max, y_min, y_max, gate_u0_world, gate_u1_world).
    """
    off = offset if offset is not None else fortification_offset(props)
    x_min, x_max, y_min, y_max = compound_bounds(
        ctx, off, fortification_depth_extra(props))
    gate_cx = ctx.main_door_cx
    gate_half = max(1.35, (getattr(props, 'door_width', 1.2) + 1.6) * 0.5)
    g0, g1 = gate_cx - gate_half, gate_cx + gate_half

    has_towers = getattr(props, 'has_bastion_towers', False)
    t_size = getattr(props, 'bastion_tower_size', 3.2) if has_towers else 0.0
    t_half = t_size * 0.5
    has_back = has_towers and getattr(props, 'bastion_tower_count', 2) >= 4
    # Bastion towers straddle the boundary: centred ON the front/back line, they
    # occupy a full t_size across X but only t_half inward in Y. Clear the
    # matching footprint per axis (with a small overlap) so the runs meet the
    # tower walls cleanly instead of leaving a gap at the side corners.
    ov = 0.12
    clear_x_f = (t_size - ov) if has_towers else 0.0
    clear_x_b = (t_size - ov) if has_back else 0.0
    clear_y_f = (t_half - ov) if has_towers else 0.0
    clear_y_b = (t_half - ov) if has_back else 0.0

    H = height if height is not None else getattr(props, 'curtain_wall_height', 3.2)
    T = thickness if thickness is not None else getattr(props, 'curtain_wall_thickness', 0.55)
    gate_h = max(2.2, min(3.0, H - 0.55))

    # Front run with the gate opening.
    front_u0 = x_min + clear_x_f
    # Where a run buries its head inside a bastion footprint, run the plinth a
    # little further in as well so its end face sits well under the tower's own
    # plinth band instead of stopping flush against it (which read as a notch).
    p_ext = 0.12
    pt_f = -p_ext if has_towers else 0.0
    pt_b = -p_ext if has_back else 0.0
    build_curtain_wall_run(
        bm, (front_u0, y_min), (x_max - clear_x_f, y_min), (0.0, -1.0), 0.0, H, T,
        gate={'u0': g0 - front_u0, 'u1': g1 - front_u0, 'h': gate_h},
        plinth_end=(pt_f, pt_f), seed=ctx.seed)
    # Back run.
    build_curtain_wall_run(
        bm, (x_min + clear_x_b, y_max), (x_max - clear_x_b, y_max), (0.0, 1.0), 0.0, H, T,
        plinth_end=(pt_b, pt_b), seed=ctx.seed + 1)
    # Left and right runs, clearing the tower footprints at front and back.
    build_curtain_wall_run(
        bm, (x_min, y_min + clear_y_f), (x_min, y_max - clear_y_b), (-1.0, 0.0), 0.0, H, T,
        plinth_end=(pt_f, pt_b), seed=ctx.seed + 2)
    build_curtain_wall_run(
        bm, (x_max, y_min + clear_y_f), (x_max, y_max - clear_y_b), (1.0, 0.0), 0.0, H, T,
        plinth_end=(pt_f, pt_b), seed=ctx.seed + 3)

    # Gatehouse dressing over the front opening.
    build_gate_house(bm, gate_cx, y_min, (0.0, -1.0), g1 - g0, 0.0, T, gate_h=gate_h)

    return (x_min, x_max, y_min, y_max, g0, g1)
