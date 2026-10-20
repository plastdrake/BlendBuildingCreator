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
from mathutils import Vector
from ..mesh_utils import create_beveled_box, create_cone
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



def build_continuous_curtain_wall_path(
    bm,
    path_pts,
    outward_hint=None,
    ground_z_fn=0.0,
    base_z_list=None,
    top_z=None,
    top_z_list=None,
    height=3.2,
    thickness=0.85,
    walk_width=0.95,
    merlon_h=0.78,
    embed_depth=2.0,
    has_walkway=True,
    has_outer_parapet=True,
    has_inner_parapet=True,
    has_string_course=True,
    has_corbels=True,
    has_piers=True,
    merlon_end_clear=(0.0, 0.0),
    seed=42,
):
    """
    Builds a single continuous curved or straight curtain-wall run with transversal loopcuts along path_pts.
    Eliminates all overlapping segment boxes, hidden internal end-caps, and z-fighting.
    Generates seamless wall body, cut-stone string course, walkable deck, parapet breastwork,
    and evenly spaced crenellated merlons with cut-stone caps.
    """
    clean_pts = []
    for p in path_pts:
        pt = (float(p[0]), float(p[1]))
        if not clean_pts or math.hypot(pt[0] - clean_pts[-1][0], pt[1] - clean_pts[-1][1]) > 0.04:
            clean_pts.append(pt)
    if len(clean_pts) < 2:
        return

    n_pts = len(clean_pts)
    u_cum = [0.0]
    for i in range(1, n_pts):
        d = math.hypot(clean_pts[i][0] - clean_pts[i-1][0], clean_pts[i][1] - clean_pts[i-1][1])
        u_cum.append(u_cum[-1] + d)
    total_len = u_cum[-1]
    if total_len < 0.2:
        return

    # Unit segment vectors
    seg_dirs = []
    for i in range(n_pts - 1):
        dx = clean_pts[i+1][0] - clean_pts[i][0]
        dy = clean_pts[i+1][1] - clean_pts[i][1]
        ln = math.hypot(dx, dy)
        seg_dirs.append((dx / ln, dy / ln))

    # Station tangents
    station_tangents = []
    for i in range(n_pts):
        if i == 0:
            station_tangents.append(seg_dirs[0])
        elif i == n_pts - 1:
            station_tangents.append(seg_dirs[-1])
        else:
            tx = seg_dirs[i-1][0] + seg_dirs[i][0]
            ty = seg_dirs[i-1][1] + seg_dirs[i][1]
            t_len = math.hypot(tx, ty)
            station_tangents.append((tx / t_len, ty / t_len) if t_len > 1e-5 else seg_dirs[i])

    # Outward normals and miter scaling
    station_normals = []
    station_miter = []
    for i in range(n_pts):
        tx, ty = station_tangents[i]
        nx, ny = ty, -tx
        if outward_hint is not None:
            if nx * outward_hint[0] + ny * outward_hint[1] < 0:
                nx, ny = -nx, -ny
        elif i > 0 and (nx * station_normals[-1][0] + ny * station_normals[-1][1] < 0):
            nx, ny = -nx, -ny

        if i == 0 or i == n_pts - 1:
            miter = 1.0
        else:
            cos_theta = seg_dirs[i-1][0] * tx + seg_dirs[i-1][1] * ty
            miter = 1.0 / max(0.707, min(1.0, cos_theta))
        station_normals.append((nx, ny))
        station_miter.append(miter)

    # Station heights
    station_base_z = []
    station_top_z = []
    for i in range(n_pts):
        px, py = clean_pts[i]
        if base_z_list is not None and i < len(base_z_list):
            bz = base_z_list[i]
        elif callable(ground_z_fn):
            gz = ground_z_fn(px, py)
            bz = gz - embed_depth
        elif isinstance(ground_z_fn, (int, float)):
            bz = float(ground_z_fn) - embed_depth
        else:
            bz = 0.0

        if top_z_list is not None and i < len(top_z_list):
            tz = top_z_list[i]
        elif isinstance(top_z, (int, float)):
            tz = float(top_z)
        else:
            tz = bz + embed_depth + height

        station_base_z.append(bz)
        station_top_z.append(tz)

    uv_layer = bm.loops.layers.uv.verify()

    # 1. MAIN WALL BODY (Single continuous extruded ribbon with loopcuts)
    ext_bot, ext_top, int_top, int_bot = [], [], [], []
    for i in range(n_pts):
        px, py = clean_pts[i]
        nx, ny = station_normals[i]
        mit = station_miter[i]
        off_x = nx * mit * (thickness * 0.5)
        off_y = ny * mit * (thickness * 0.5)

        ex, ey = px + off_x, py + off_y
        ix, iy = px - off_x, py - off_y

        bz = station_base_z[i]
        tz = station_top_z[i]

        ext_bot.append(bm.verts.new((ex, ey, bz)))
        ext_top.append(bm.verts.new((ex, ey, tz)))
        int_top.append(bm.verts.new((ix, iy, tz)))
        int_bot.append(bm.verts.new((ix, iy, bz)))

    for i in range(n_pts - 1):
        u0, u1 = u_cum[i], u_cum[i+1]
        bz0, bz1 = station_base_z[i], station_base_z[i+1]
        tz0, tz1 = station_top_z[i], station_top_z[i+1]

        # Exterior face (+N)
        f_ext = bm.faces.new([ext_bot[i], ext_bot[i+1], ext_top[i+1], ext_top[i]])
        f_ext.material_index = MAT_INDEX_STONE
        f_ext.tag = True
        f_ext.loops[0][uv_layer].uv = Vector((u0, bz0))
        f_ext.loops[1][uv_layer].uv = Vector((u1, bz1))
        f_ext.loops[2][uv_layer].uv = Vector((u1, tz1))
        f_ext.loops[3][uv_layer].uv = Vector((u0, tz0))

        # Interior face (-N)
        f_int = bm.faces.new([int_bot[i+1], int_bot[i], int_top[i], int_top[i+1]])
        f_int.material_index = MAT_INDEX_STONE
        f_int.tag = True
        f_int.loops[0][uv_layer].uv = Vector((u1, bz1))
        f_int.loops[1][uv_layer].uv = Vector((u0, bz0))
        f_int.loops[2][uv_layer].uv = Vector((u0, tz0))
        f_int.loops[3][uv_layer].uv = Vector((u1, tz1))

        # Top face (+Z)
        f_top = bm.faces.new([ext_top[i], ext_top[i+1], int_top[i+1], int_top[i]])
        f_top.material_index = MAT_INDEX_STONE

        # Bottom face (-Z)
        f_bot = bm.faces.new([ext_bot[i+1], ext_bot[i], int_bot[i], int_bot[i+1]])
        f_bot.material_index = MAT_INDEX_STONE

    # Start and End caps
    bm.faces.new([ext_bot[0], ext_top[0], int_top[0], int_bot[0]]).material_index = MAT_INDEX_STONE
    bm.faces.new([ext_bot[-1], int_bot[-1], int_top[-1], ext_top[-1]]).material_index = MAT_INDEX_STONE

    # 2. STRING COURSE (Projecting cut-stone coping band at wall top)
    str_h = 0.16
    str_proj = 0.09
    if has_string_course:
        str_eb, str_et, str_it, str_ib = [], [], [], []
        for i in range(n_pts):
            px, py = clean_pts[i]
            nx, ny = station_normals[i]
            mit = station_miter[i]
            ex = px + nx * mit * (thickness * 0.5 + str_proj)
            ey = py + ny * mit * (thickness * 0.5 + str_proj)
            ix = px - nx * mit * (thickness * 0.5 + 0.02)
            iy = py - ny * mit * (thickness * 0.5 + 0.02)

            tz = station_top_z[i]
            str_eb.append(bm.verts.new((ex, ey, tz)))
            str_et.append(bm.verts.new((ex, ey, tz + str_h)))
            str_it.append(bm.verts.new((ix, iy, tz + str_h)))
            str_ib.append(bm.verts.new((ix, iy, tz)))

        for i in range(n_pts - 1):
            bm.faces.new([str_eb[i], str_eb[i+1], str_et[i+1], str_et[i]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([str_et[i], str_et[i+1], str_it[i+1], str_it[i]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([str_ib[i+1], str_ib[i], str_it[i], str_it[i+1]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([str_eb[i+1], str_eb[i], str_ib[i], str_ib[i+1]]).material_index = MAT_INDEX_CUT_STONE

        bm.faces.new([str_eb[0], str_et[0], str_it[0], str_ib[0]]).material_index = MAT_INDEX_CUT_STONE
        bm.faces.new([str_eb[-1], str_ib[-1], str_it[-1], str_et[-1]]).material_index = MAT_INDEX_CUT_STONE

    # 3. MACHICOLATION CORBELS (Spaced along the outer curve)
    if has_corbels and total_len >= 1.6:
        corbel_spacing = 2.4
        n_cb = max(1, int(round(total_len / corbel_spacing)))
        cb_step = total_len / n_cb
        for ci in range(n_cb + 1):
            cu = ci * cb_step
            if cu < 0.35 or cu > total_len - 0.35:
                continue
            span_idx = 0
            while span_idx < n_pts - 2 and u_cum[span_idx + 1] < cu:
                span_idx += 1
            t_span = (cu - u_cum[span_idx]) / max(1e-5, u_cum[span_idx + 1] - u_cum[span_idx])
            t_span = max(0.0, min(1.0, t_span))

            p0 = clean_pts[span_idx]
            p1 = clean_pts[span_idx + 1]
            c_px = p0[0] + (p1[0] - p0[0]) * t_span
            c_py = p0[1] + (p1[1] - p0[1]) * t_span

            tx, ty = seg_dirs[span_idx]
            nx = station_normals[span_idx][0] * (1.0 - t_span) + station_normals[span_idx + 1][0] * t_span
            ny = station_normals[span_idx][1] * (1.0 - t_span) + station_normals[span_idx + 1][1] * t_span
            n_len = math.hypot(nx, ny)
            if n_len > 1e-5:
                nx, ny = nx / n_len, ny / n_len

            cb_x = c_px + nx * (thickness * 0.5 + 0.05)
            cb_y = c_py + ny * (thickness * 0.5 + 0.05)
            c_tz = station_top_z[span_idx] * (1.0 - t_span) + station_top_z[span_idx + 1] * t_span
            ang = math.atan2(ty, tx)

            create_beveled_box(bm, size=(0.24, 0.22, 0.34),
                               location=(cb_x, cb_y, c_tz - 0.12),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 4. WALKWAY DECK (Chemin de ronde on inner side)
    if has_walkway:
        dk_out_top, dk_inn_top, dk_inn_bot, dk_out_bot = [], [], [], []
        deck_th = 0.14
        for i in range(n_pts):
            px, py = clean_pts[i]
            nx, ny = station_normals[i]
            mit = station_miter[i]

            ox = px - nx * mit * (thickness * 0.5 - 0.05)
            oy = py - ny * mit * (thickness * 0.5 - 0.05)
            ix = px - nx * mit * (thickness * 0.5 + walk_width)
            iy = py - ny * mit * (thickness * 0.5 + walk_width)

            tz = station_top_z[i]
            z_top_deck = tz + str_h
            z_bot_deck = z_top_deck - deck_th

            dk_out_top.append(bm.verts.new((ox, oy, z_top_deck)))
            dk_inn_top.append(bm.verts.new((ix, iy, z_top_deck)))
            dk_inn_bot.append(bm.verts.new((ix, iy, z_bot_deck)))
            dk_out_bot.append(bm.verts.new((ox, oy, z_bot_deck)))

        for i in range(n_pts - 1):
            bm.faces.new([dk_out_top[i], dk_out_top[i+1], dk_inn_top[i+1], dk_inn_top[i]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([dk_inn_bot[i], dk_inn_bot[i+1], dk_inn_top[i+1], dk_inn_top[i]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([dk_out_bot[i+1], dk_out_bot[i], dk_inn_bot[i], dk_inn_bot[i+1]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([dk_out_top[i+1], dk_out_top[i], dk_out_bot[i], dk_out_bot[i+1]]).material_index = MAT_INDEX_CUT_STONE

        bm.faces.new([dk_out_top[0], dk_inn_top[0], dk_inn_bot[0], dk_out_bot[0]]).material_index = MAT_INDEX_CUT_STONE
        bm.faces.new([dk_out_top[-1], dk_out_bot[-1], dk_inn_bot[-1], dk_inn_top[-1]]).material_index = MAT_INDEX_CUT_STONE

    # 5. INNER SUPPORT PIERS (Rampart buttresses along bailey)
    if has_piers and has_walkway and total_len >= 2.0:
        pier_spacing = 2.8
        n_piers = max(1, int(round(total_len / pier_spacing)))
        p_step = total_len / n_piers
        for pi in range(n_piers + 1):
            pu = pi * p_step
            if pu < 0.35 or pu > total_len - 0.35:
                continue
            span_idx = 0
            while span_idx < n_pts - 2 and u_cum[span_idx + 1] < pu:
                span_idx += 1
            t_span = (pu - u_cum[span_idx]) / max(1e-5, u_cum[span_idx + 1] - u_cum[span_idx])
            t_span = max(0.0, min(1.0, t_span))

            p0 = clean_pts[span_idx]
            p1 = clean_pts[span_idx + 1]
            c_px = p0[0] + (p1[0] - p0[0]) * t_span
            c_py = p0[1] + (p1[1] - p0[1]) * t_span

            tx, ty = seg_dirs[span_idx]
            nx = station_normals[span_idx][0] * (1.0 - t_span) + station_normals[span_idx + 1][0] * t_span
            ny = station_normals[span_idx][1] * (1.0 - t_span) + station_normals[span_idx + 1][1] * t_span
            n_len = math.hypot(nx, ny)
            if n_len > 1e-5:
                nx, ny = nx / n_len, ny / n_len

            p_lat = -(thickness * 0.5 + walk_width * 0.5 - 0.05)
            px_c = c_px + nx * p_lat
            py_c = c_py + ny * p_lat
            c_tz = station_top_z[span_idx] * (1.0 - t_span) + station_top_z[span_idx + 1] * t_span
            c_bz = station_base_z[span_idx] * (1.0 - t_span) + station_base_z[span_idx + 1] * t_span
            p_h = c_tz - c_bz
            ang = math.atan2(ty, tx)

            create_beveled_box(bm, size=(0.42, walk_width * 0.85, p_h),
                               location=(px_c, py_c, c_bz + p_h * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
            create_beveled_box(bm, size=(0.54, walk_width * 0.90, 0.30),
                               location=(px_c, py_c, c_tz - 0.15),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 6. OUTER PARAPET BREASTWORK & MERLONS (Continuous ribbon + crenels)
    par_t = 0.30
    base_h = 0.38
    mer_h = merlon_h - base_h
    if has_outer_parapet:
        p_eb, p_et, p_it, p_ib = [], [], [], []
        for i in range(n_pts):
            px, py = clean_pts[i]
            nx, ny = station_normals[i]
            mit = station_miter[i]

            ex = px + nx * mit * (thickness * 0.5 + 0.02)
            ey = py + ny * mit * (thickness * 0.5 + 0.02)
            ix = px + nx * mit * (thickness * 0.5 + 0.02 - par_t)
            iy = py + ny * mit * (thickness * 0.5 + 0.02 - par_t)

            z0 = station_top_z[i] + str_h
            z1 = z0 + base_h

            p_eb.append(bm.verts.new((ex, ey, z0)))
            p_et.append(bm.verts.new((ex, ey, z1)))
            p_it.append(bm.verts.new((ix, iy, z1)))
            p_ib.append(bm.verts.new((ix, iy, z0)))

        for i in range(n_pts - 1):
            bm.faces.new([p_eb[i], p_eb[i+1], p_et[i+1], p_et[i]]).material_index = MAT_INDEX_STONE
            bm.faces.new([p_et[i], p_et[i+1], p_it[i+1], p_it[i]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([p_ib[i+1], p_ib[i], p_it[i], p_it[i+1]]).material_index = MAT_INDEX_STONE
            bm.faces.new([p_eb[i+1], p_eb[i], p_ib[i], p_ib[i+1]]).material_index = MAT_INDEX_STONE

        bm.faces.new([p_eb[0], p_et[0], p_it[0], p_ib[0]]).material_index = MAT_INDEX_CUT_STONE
        bm.faces.new([p_eb[-1], p_ib[-1], p_it[-1], p_et[-1]]).material_index = MAT_INDEX_CUT_STONE

        # Merlons spaced along the curve
        merlon_w = 0.55
        crenel_w = 0.50
        pitch = merlon_w + crenel_w
        mc0, mc1 = merlon_end_clear
        eff_len = total_len - (mc0 + mc1)
        if eff_len >= 0.8:
            n_merlons = max(2, int(round(eff_len / pitch)))
            m_step = eff_len / n_merlons
            mw = merlon_w * 0.65
            for mi in range(n_merlons + 1):
                mu = mc0 + mi * m_step
                if mu < mc0 + 0.05 or mu > total_len - mc1 - 0.05:
                    continue
                span_idx = 0
                while span_idx < n_pts - 2 and u_cum[span_idx + 1] < mu:
                    span_idx += 1
                t_span = (mu - u_cum[span_idx]) / max(1e-5, u_cum[span_idx + 1] - u_cum[span_idx])
                t_span = max(0.0, min(1.0, t_span))

                p0 = clean_pts[span_idx]
                p1 = clean_pts[span_idx + 1]
                m_px = p0[0] + (p1[0] - p0[0]) * t_span
                m_py = p0[1] + (p1[1] - p0[1]) * t_span

                tx, ty = seg_dirs[span_idx]
                nx = station_normals[span_idx][0] * (1.0 - t_span) + station_normals[span_idx + 1][0] * t_span
                ny = station_normals[span_idx][1] * (1.0 - t_span) + station_normals[span_idx + 1][1] * t_span
                n_len = math.hypot(nx, ny)
                if n_len > 1e-5:
                    nx, ny = nx / n_len, ny / n_len

                m_lat = thickness * 0.5 + 0.02 - par_t * 0.5
                mx = m_px + nx * m_lat
                my = m_py + ny * m_lat
                m_tz = station_top_z[span_idx] * (1.0 - t_span) + station_top_z[span_idx + 1] * t_span
                z_merlon_base = m_tz + str_h + base_h
                ang = math.atan2(ty, tx)

                create_beveled_box(
                    bm, size=(mw, par_t * 1.06, mer_h),
                    location=(mx, my, z_merlon_base + mer_h * 0.5),
                    rotation=(0.0, 0.0, ang),
                    mat_index=MAT_INDEX_STONE, bevel_amount=0.012
                )
                create_beveled_box(
                    bm, size=(merlon_w * 0.75, par_t * 1.16, 0.10),
                    location=(mx, my, z_merlon_base + mer_h + 0.05),
                    rotation=(0.0, 0.0, ang),
                    mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.008
                )

    # 7. INNER BATTLEMENTS (Bailey edge of walkway)
    if has_inner_parapet and has_walkway and total_len >= 1.2:
        in_p_eb, in_p_et, in_p_it, in_p_ib = [], [], [], []
        in_par_t = 0.28
        in_base_h = 0.35
        in_mer_h = 0.38
        for i in range(n_pts):
            px, py = clean_pts[i]
            nx, ny = station_normals[i]
            mit = station_miter[i]

            ox = px - nx * mit * (thickness * 0.5 + walk_width - in_par_t)
            oy = py - ny * mit * (thickness * 0.5 + walk_width - in_par_t)
            ix = px - nx * mit * (thickness * 0.5 + walk_width)
            iy = py - ny * mit * (thickness * 0.5 + walk_width)

            z0 = station_top_z[i] + str_h
            z1 = z0 + in_base_h

            in_p_eb.append(bm.verts.new((ox, oy, z0)))
            in_p_et.append(bm.verts.new((ox, oy, z1)))
            in_p_it.append(bm.verts.new((ix, iy, z1)))
            in_p_ib.append(bm.verts.new((ix, iy, z0)))

        for i in range(n_pts - 1):
            bm.faces.new([in_p_eb[i+1], in_p_eb[i], in_p_et[i], in_p_et[i+1]]).material_index = MAT_INDEX_STONE
            bm.faces.new([in_p_et[i+1], in_p_et[i], in_p_it[i], in_p_it[i+1]]).material_index = MAT_INDEX_CUT_STONE
            bm.faces.new([in_p_ib[i], in_p_ib[i+1], in_p_it[i+1], in_p_it[i]]).material_index = MAT_INDEX_STONE
            bm.faces.new([in_p_eb[i], in_p_eb[i+1], in_p_ib[i+1], in_p_ib[i]]).material_index = MAT_INDEX_STONE

        bm.faces.new([in_p_eb[0], in_p_ib[0], in_p_it[0], in_p_et[0]]).material_index = MAT_INDEX_CUT_STONE
        bm.faces.new([in_p_eb[-1], in_p_et[-1], in_p_it[-1], in_p_ib[-1]]).material_index = MAT_INDEX_CUT_STONE

        # Inner merlons
        in_merlon_w = 0.52
        in_pitch = 1.10
        n_in_m = max(1, int(round((total_len - 0.8) / in_pitch)))
        in_step = (total_len - 0.8) / max(1, n_in_m)
        in_mw = in_merlon_w * 0.65
        for mi in range(n_in_m + 1):
            mu = 0.40 + mi * in_step
            if mu < 0.40 or mu > total_len - 0.40:
                continue
            span_idx = 0
            while span_idx < n_pts - 2 and u_cum[span_idx + 1] < mu:
                span_idx += 1
            t_span = (mu - u_cum[span_idx]) / max(1e-5, u_cum[span_idx + 1] - u_cum[span_idx])
            t_span = max(0.0, min(1.0, t_span))

            p0 = clean_pts[span_idx]
            p1 = clean_pts[span_idx + 1]
            m_px = p0[0] + (p1[0] - p0[0]) * t_span
            m_py = p0[1] + (p1[1] - p0[1]) * t_span

            tx, ty = seg_dirs[span_idx]
            nx = station_normals[span_idx][0] * (1.0 - t_span) + station_normals[span_idx + 1][0] * t_span
            ny = station_normals[span_idx][1] * (1.0 - t_span) + station_normals[span_idx + 1][1] * t_span
            n_len = math.hypot(nx, ny)
            if n_len > 1e-5:
                nx, ny = nx / n_len, ny / n_len

            m_lat = -(thickness * 0.5 + walk_width - in_par_t * 0.5)
            mx = m_px + nx * m_lat
            my = m_py + ny * m_lat
            m_tz = station_top_z[span_idx] * (1.0 - t_span) + station_top_z[span_idx + 1] * t_span
            z_merlon_base = m_tz + str_h + in_base_h
            ang = math.atan2(ty, tx)

            create_beveled_box(
                bm, size=(in_mw, in_par_t * 1.06, in_mer_h),
                location=(mx, my, z_merlon_base + in_mer_h * 0.5),
                rotation=(0.0, 0.0, ang),
                mat_index=MAT_INDEX_STONE, bevel_amount=0.012
            )
            create_beveled_box(
                bm, size=(in_merlon_w * 0.75, in_par_t * 1.16, 0.10),
                location=(mx, my, z_merlon_base + in_mer_h + 0.05),
                rotation=(0.0, 0.0, ang),
                mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.008
            )


def build_curtain_wall_run(bm, p_start, p_end, outward, ground_z=0.0,
                           height=3.2, thickness=0.55, plinth_h=0.45,
                           walk_width=0.95, merlon_h=0.78,
                           slits=True, slit_spacing=3.0, gate=None,
                           plinth_end=(0.0, 0.0), seed=42,
                           merlon_end_clear=(0.0, 0.0)):
    """Build one straight curtain-wall run between two (x, y) points.

    ``outward`` is the horizontal normal the merlons and arrow slits face.
    ``gate`` is an optional ``{'u0', 'u1', 'h'}`` gate opening: the plinth is
    broken across it, the wall keeps a lintel band above it (via the wall
    builder), and the wall-walk and battlements run straight over the top.

    ``plinth_end`` shifts the plinth in (+) or out (-) at the start/end of the
    run. Where a run buries its head inside a corner bastion the caller pushes
    the plinth a little further in so it laps well under the tower's own plinth
    band rather than stopping flush against it (which read as a notch).

    ``merlon_end_clear`` insets the parapet/merlon strip (only) at the
    start/end of the run so the crenels stop cleanly at a corner post instead
    of piling two perpendicular merlons onto each other.
    """
    x1, y1 = p_start
    x2, y2 = p_end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.2:
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
                            physical_siding=False, seed=seed,
                            inner_mat=MAT_INDEX_STONE)

    # 3. Cut-stone string course at the wall head (full thickness).
    for u0, u1 in walk_spans:
        cx, cy = at((u0 + u1) * 0.5)
        create_beveled_box(bm, size=(u1 - u0, thickness + 0.18, 0.16),
                           location=(cx, cy, walk_top + 0.08),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # 3b. Cut-stone machicolation corbels projecting beneath the string course on the outer face.
    corbel_spacing = 2.4
    for u0, u1 in walk_spans:
        seg_len = u1 - u0
        if seg_len >= 1.6:
            n_cb = max(1, int(round(seg_len / corbel_spacing)))
            step = seg_len / n_cb
            for i in range(n_cb + 1):
                cu = u0 + i * step
                if cu < u0 + 0.35 or cu > u1 - 0.35:
                    continue
                if gate_gap and gate_gap[0] - 0.5 <= cu <= gate_gap[1] + 0.5:
                    continue
                cb_x, cb_y = at(cu, lateral=thickness * 0.5 + 0.05)
                create_beveled_box(bm, size=(0.24, 0.22, 0.34),
                                   location=(cb_x, cb_y, walk_top - 0.12),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # 4. Inner wall-walk deck, seated just behind the parapet.
    for u0, u1 in walk_spans:
        cx_w, cy_w = at((u0 + u1) * 0.5, -(thickness * 0.5 + walk_width * 0.5 - 0.05))
        create_beveled_box(bm, size=(u1 - u0, walk_width, 0.14),
                           location=(cx_w, cy_w, walk_top + 0.16),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

        # 4b. Inner rampart supporting piers & corbel vaults (giving the back of the wall real depth)
        n_piers = max(1, int(round((u1 - u0) / 2.8)))
        p_step = (u1 - u0) / n_piers
        inner_lat = -(thickness * 0.5 + walk_width * 0.5 - 0.05)
        for pi in range(n_piers + 1):
            pu = u0 + pi * p_step
            if pu < u0 + 0.35 or pu > u1 - 0.35:
                continue
            if gate_gap and gate_gap[0] - 0.5 <= pu <= gate_gap[1] + 0.5:
                continue
            px_c, py_c = at(pu, inner_lat)
            create_beveled_box(bm, size=(0.42, walk_width * 0.85, height),
                               location=(px_c, py_c, ground_z + height * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.015)
            create_beveled_box(bm, size=(0.54, walk_width * 0.90, 0.30),
                               location=(px_c, py_c, walk_top - 0.15),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

        # 4c. Inner crenellated battlements ("sticky up bits") along the bailey edge of the walkway.
        # Matching the exterior battlements (stone merlons with cut-stone caps).
        # Leaves open landing breaches where access stairs arrive at the top landing!
        inner_edge_lat = -(thickness * 0.5 + walk_width - 0.05)
        merlon_end = 0.40
        if gate_gap:
            # Leave generous breaches across the gatehouse, gate towers, and stair landings
            breach = gate.get('breach', 3.20)
            g_left = gate_gap[0] - breach
            g_right = gate_gap[1] + breach
            if g_left > u0 + merlon_end + 1.0:
                build_battlement_run(bm, at(u0 + merlon_end, inner_edge_lat),
                                     at(g_left, inner_edge_lat),
                                     walk_top + 0.16, height=0.74, thickness=0.28, style='STONE')
            if u1 - merlon_end > g_right + 1.0:
                build_battlement_run(bm, at(g_right, inner_edge_lat),
                                     at(u1 - merlon_end, inner_edge_lat),
                                     walk_top + 0.16, height=0.74, thickness=0.28, style='STONE')
        else:
            if u1 - u0 > 1.2:
                build_battlement_run(bm, at(u0 + merlon_end, inner_edge_lat),
                                     at(u1 - merlon_end, inner_edge_lat),
                                     walk_top + 0.16, height=0.74, thickness=0.28, style='STONE')

    # 5. Crenellated merlons along the exposed outer edge, optionally
    # stopping short of a corner post so perpendicular parapets never collide.
    par_t = 0.30
    off_out = thickness * 0.5 - par_t * 0.5 + 0.02
    mc0, mc1 = merlon_end_clear
    for u0, u1 in walk_spans:
        if u1 - u0 < 0.8:
            continue
        build_battlement_run(bm, at(u0 + mc0, off_out), at(u1 - mc1, off_out),
                             walk_top + 0.16, height=merlon_h,
                             thickness=par_t, style='STONE')

    # 6. Dress each cut slit with cut-stone reveals.
    for uc in slit_centers:
        cx, cy = at(uc)
        build_arrow_slit(bm, center=(cx, cy, slit_cz), normal_axis=(ox, oy),
                         wall_thickness=thickness, slit_w=slit_w, slit_h=slit_h,
                         has_transom=False)


def _build_corner_post(bm, cx, cy, thickness, walk_top, ground_z=0.0):
    """Dressed cut-stone corner pier where two runs meet without a tower.

    A slightly proud square post swallowing the whole corner joint (plinth,
    body, string course and parapet ends all terminate buried inside it), so
    no coincident faces or doubled merlons remain visible. Capped with a
    wider crown block.
    """
    half = thickness * 0.5 + 0.14
    # Rise to merlon-cap height so the pier reads as the corner merlon,
    # not a stump beside them.
    pier_top = walk_top + 1.20
    pier_h = pier_top - ground_z
    create_beveled_box(bm, size=(half * 2.0, half * 2.0, pier_h),
                       location=(cx, cy, ground_z + pier_h * 0.5),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)
    cap_half = half + 0.10
    create_beveled_box(bm, size=(cap_half * 2.0, cap_half * 2.0, 0.16),
                       location=(cx, cy, pier_top + 0.08),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)


def gate_stair_top_offset(gate_towers):
    """Distance from the gate opening edge to the centre of the wall-walk stair landing."""
    return 0.8 + (2.0 * 1.9 + 0.45 if gate_towers else 0.0)


def build_gatehouse_access_stairs(bm, cx, cy, outward, gap_w, ground_z=0.0,
                                  wall_h=3.2, thickness=0.55, top_off=0.8,
                                  gate_towers=False):
    """Walkable stone stairs on the bailey side of the wall with authentic diagonal railings
    and posts (no bulky solid stone side walls).
    When gate_towers is True, continues from the wall-walk landing directly up to the
    gate tower roof terrace, providing a continuous, fully walkable path with its own landing."""
    from mathutils import Euler
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on < 1e-5:
        ox, oy = 0.0, -1.0
    else:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox
    ang = math.atan2(ty, tx)

    stair_w, run, land_len = 1.65, 0.34, 1.60
    deck_top = ground_z + wall_h + 0.25
    n = max(4, int(math.ceil((deck_top - ground_z) / 0.2)))
    rise = (deck_top - ground_z) / n
    inner_lat = thickness * 0.5 + 1.25
    lat_c = inner_lat + stair_w * 0.5
    outer_rail_lat = inner_lat + stair_w + 0.08
    post_size = 0.14
    rail_h = 0.90

    def at(u, lat):
        # lat grows toward the bailey (opposite of outward)
        return cx + tx * u - ox * lat, cy + ty * u - oy * lat

    for sgn in (-1.0, 1.0):
        u_land = sgn * (gap_w * 0.5 + top_off)
        lat0 = thickness * 0.5 + 0.35
        lat1 = inner_lat + stair_w
        px, py = at(u_land, (lat0 + lat1) * 0.5)

        # 1. Main wall-walk landing block
        create_beveled_box(bm, size=(land_len, lat1 - lat0, deck_top - ground_z),
                           location=(px, py, ground_z + (deck_top - ground_z) * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_STONE, bevel_amount=0.01)

        # Landing outer timber newel posts and horizontal protective rail
        outer_rail_lat_land = lat1 - 0.12
        for post_u in (u_land - sgn * land_len * 0.45, u_land + sgn * land_len * 0.45):
            lx_p, ly_p = at(post_u, outer_rail_lat_land)
            create_beveled_box(bm, size=(post_size, post_size, rail_h + 0.10),
                               location=(lx_p, ly_p, deck_top + (rail_h + 0.10) * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            create_cone(bm, radius1=0.10, radius2=0.0, height=0.08, segments=4,
                        location=(lx_p, ly_p, deck_top + rail_h + 0.14),
                        rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_TIMBER)
        # Landing horizontal handrail and mid-rail
        lx_r, ly_r = at(u_land, outer_rail_lat_land)
        create_beveled_box(bm, size=(land_len + 0.10, 0.12, 0.08),
                           location=(lx_r, ly_r, deck_top + rail_h),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        create_beveled_box(bm, size=(land_len + 0.10, 0.08, 0.06),
                           location=(lx_r, ly_r, deck_top + rail_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

        # 2. Solid stone steps (clean treads without giant monolithic side walls)
        total_flight_len = run * n
        stair_rail_lat = inner_lat + stair_w - 0.12  # Posts mount inside treads, never float in air

        for k in range(n):
            top = deck_top - (k + 1) * rise
            if top <= ground_z + 0.03:
                break
            u = u_land + sgn * (land_len * 0.5 + run * (k + 0.5))
            sx, sy = at(u, lat_c)
            # Riser base block
            create_beveled_box(bm, size=(run + 0.02, stair_w, top - ground_z),
                               location=(sx, sy, ground_z + (top - ground_z) * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.005)
            # Tread nosing stone cap (bottom face lifted 6mm above the riser
            # top so no coplanar faces z-fight)
            create_beveled_box(bm, size=(run + 0.04, stair_w + 0.02, 0.05),
                               location=(sx, sy, top + 0.031),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.005)

        # 3. Authentic diagonal railing with upright timber pillars on the inner edge of treads
        hyp_len = math.hypot(total_flight_len, deck_top - ground_z)

        # Upright newel pillars spaced along the flight, mounted inside the treads
        n_flight_posts = max(3, int(n / 3) + 1)
        for pi in range(n_flight_posts):
            frac = pi / (n_flight_posts - 1)
            pu = u_land + sgn * (land_len * 0.5 + total_flight_len * frac)
            pz = deck_top - (deck_top - ground_z) * frac
            p_pos_x, p_pos_y = at(pu, stair_rail_lat)
            create_beveled_box(bm, size=(post_size, post_size, rail_h + 0.08),
                               location=(p_pos_x, p_pos_y, pz + (rail_h + 0.08) * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            create_cone(bm, radius1=0.10, radius2=0.0, height=0.08, segments=4,
                        location=(p_pos_x, p_pos_y, pz + rail_h + 0.12),
                        rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_TIMBER)

        # Smooth diagonal handrail pitched correctly along the stairs
        mid_u = u_land + sgn * (land_len * 0.5 + total_flight_len * 0.5)
        mid_z = (deck_top + ground_z) * 0.5 + rail_h
        mid_rx, mid_ry = at(mid_u, stair_rail_lat)

        from mathutils import Matrix
        rail_fwd = Vector((sgn * tx * total_flight_len, sgn * ty * total_flight_len, ground_z - deck_top)).normalized()
        rail_lat = Vector((-ox, -oy, 0.0)).normalized()
        rail_up = rail_fwd.cross(rail_lat)
        if rail_up.z < 0.0:
            # Keep the handrail right-side up (local +Z skyward) so the
            # pitched rail never builds upside-down / mirrored.
            rail_up = -rail_up
            rail_lat = -rail_lat
        rail_up = rail_up.normalized()
        rail_lat = rail_up.cross(rail_fwd).normalized()
        rot_handrail = Matrix([rail_fwd, rail_lat, rail_up]).transposed().to_euler('XYZ')

        create_beveled_box(bm, size=(hyp_len + 0.15, 0.12, 0.08),
                           location=(mid_rx, mid_ry, mid_z),
                           rotation=rot_handrail,
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
        create_beveled_box(bm, size=(hyp_len + 0.15, 0.08, 0.06),
                           location=(mid_rx, mid_ry, mid_z - rail_h * 0.5),
                           rotation=rot_handrail,
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

        # 4. Continuation flight climbing from wall-walk landing up to gate tower roof deck
        if gate_towers:
            top_z = ground_z + wall_h + 1.85
            rise_tow = top_z - deck_top  # ~1.60m
            n_tow = 7
            t_rise = rise_tow / n_tow
            t_run = 0.34
            t_w = 1.30
            tow_flight_len = t_run * n_tow
            tow_hyp = math.hypot(tow_flight_len, rise_tow)
            tow_lat_c = inner_lat + t_w * 0.5
            tow_rail_lat = inner_lat + t_w - 0.12  # Mount inside treads

            # The flight climbs from u_land towards the tower along -sgn * tx.
            # Every step is a solid masonry block running all the way down to
            # the ground (same construction as the main flight), so no part of
            # the upper stair can ever hover in the air.
            for ti in range(n_tow):
                tu = u_land - sgn * (land_len * 0.5 + t_run * (ti + 0.5))
                tz = deck_top + (ti + 1) * t_rise
                tx_s, ty_s = at(tu, tow_lat_c)
                # Solid stone undercarriage down to firm ground (never floating)
                step_total_h = tz - ground_z
                create_beveled_box(bm, size=(t_run + 0.02, t_w, step_total_h),
                                   location=(tx_s, ty_s, ground_z + step_total_h * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_STONE, bevel_amount=0.005)
                # Tread nosing stone cap (bottom face lifted 6mm: never coplanar)
                create_beveled_box(bm, size=(t_run + 0.04, t_w + 0.02, 0.05),
                                   location=(tx_s, ty_s, tz + 0.031),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.005)

            # Top landing at tower deck level: solid pier down to firm ground.
            # The pad is lengthened toward the gate tower so it laps over the
            # tower roof deck edge: a continuous walkable step-across with no
            # gap between stair and tower terrace.
            top_land_u = u_land - sgn * (land_len * 0.5 + tow_flight_len + 0.65)
            tl_x, tl_y = at(top_land_u, tow_lat_c - 0.50)
            # Solid landing block
            land_block_h = top_z - ground_z
            create_beveled_box(bm, size=(1.30, t_w + 1.00, land_block_h),
                               location=(tl_x, tl_y, ground_z + land_block_h * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_STONE, bevel_amount=0.01)
            create_beveled_box(bm, size=(1.35, t_w + 1.04, 0.10),
                               location=(tl_x, tl_y, top_z + 0.05),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

            # Top-landing guard railing along the exposed outer edge, continuing
            # the flight handrail line (posts + double rail with pyramid caps)
            land_outer_lat = tow_lat_c - 0.50 + (t_w + 1.00) * 0.5 - 0.06
            for post_du in (-0.60, 0.0, 0.60):
                pl_x, pl_y = at(top_land_u + post_du, land_outer_lat)
                create_beveled_box(bm, size=(post_size, post_size, rail_h + 0.08),
                                   location=(pl_x, pl_y, top_z + (rail_h + 0.08) * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
                create_cone(bm, radius1=0.10, radius2=0.0, height=0.08, segments=4,
                            location=(pl_x, pl_y, top_z + rail_h + 0.12),
                            rotation=(0.0, 0.0, ang + math.pi * 0.25), mat_index=MAT_INDEX_TIMBER)
            rl_x, rl_y = at(top_land_u, land_outer_lat)
            create_beveled_box(bm, size=(1.35, 0.12, 0.08),
                               location=(rl_x, rl_y, top_z + rail_h),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
            create_beveled_box(bm, size=(1.35, 0.08, 0.06),
                               location=(rl_x, rl_y, top_z + rail_h * 0.5),
                               rotation=(0.0, 0.0, ang),
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)

            # Continuation flight railing
            n_tow_posts = 3
            for tpi in range(n_tow_posts):
                t_frac = tpi / (n_tow_posts - 1)
                tpu = u_land - sgn * (land_len * 0.5 + tow_flight_len * t_frac)
                tpz = deck_top + rise_tow * t_frac
                tpx_p, tpy_p = at(tpu, tow_rail_lat)
                create_beveled_box(bm, size=(post_size, post_size, rail_h + 0.08),
                                   location=(tpx_p, tpy_p, tpz + (rail_h + 0.08) * 0.5),
                                   rotation=(0.0, 0.0, ang),
                                   mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012)
            tow_mid_u = u_land - sgn * (land_len * 0.5 + tow_flight_len * 0.5)
            tow_mid_z = (deck_top + top_z) * 0.5 + rail_h
            tow_rx, tow_ry = at(tow_mid_u, tow_rail_lat)

            tow_fwd = Vector((-sgn * tx * tow_flight_len, -sgn * ty * tow_flight_len, rise_tow)).normalized()
            tow_lat_ax = Vector((-ox, -oy, 0.0)).normalized()
            tow_up_ax = tow_fwd.cross(tow_lat_ax)
            if tow_up_ax.z < 0.0:
                # Keep the handrail right-side up so the pitched rail never
                # builds upside-down / mirrored.
                tow_up_ax = -tow_up_ax
                tow_lat_ax = -tow_lat_ax
            tow_up_ax = tow_up_ax.normalized()
            tow_lat_ax = tow_up_ax.cross(tow_fwd).normalized()
            rot_tow_rail = Matrix([tow_fwd, tow_lat_ax, tow_up_ax]).transposed().to_euler('XYZ')

            create_beveled_box(bm, size=(tow_hyp + 0.15, 0.12, 0.08),
                               location=(tow_rx, tow_ry, tow_mid_z),
                               rotation=rot_tow_rail,
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
            create_beveled_box(bm, size=(tow_hyp + 0.15, 0.08, 0.06),
                               location=(tow_rx, tow_ry, tow_mid_z - rail_h * 0.5),
                               rotation=rot_tow_rail,
                               mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)


def build_gate_house(bm, cx, cy, outward, gap_w, ground_z=0.0, thickness=0.55,
                     gate_h=2.7, portcullis=False, drawbridge=False,
                     drawbridge_angle=0.0, gate_towers=False, wall_h=3.2):
    """Cut-stone gatehouse framing the front gate: flanking piers proud of the
    wall, a lintel arch over the opening, stepped coping caps, optional portcullis,
    oak plank drawbridge with chains, flanking D-bastion gate towers, and rampart stairs.
    """
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on > 1e-5:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox            # wall tangent
    ang = math.atan2(ty, tx)
    half_outer = gap_w * 0.5 + 0.22
    push = 0.12
    frame_depth = thickness + 0.40

    for s in (-1.0, 1.0):
        px = cx + tx * (s * half_outer) + ox * push
        py = cy + ty * (s * half_outer) + oy * push
        pier_h = gate_h
        create_beveled_box(bm, size=(0.62, frame_depth, pier_h),
                           location=(px, py, ground_z + pier_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # Deep lintel band across the opening
    create_beveled_box(bm, size=(gap_w + 1.20, frame_depth, 0.32),
                       location=(cx + ox * push, cy + oy * push, ground_z + gate_h + 0.14),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_TIMBER, bevel_amount=0.02)

    # Elevated Defensive Superstructure & Fighting Platform
    # Rises above the flanking curtain wall walkways, giving clear command of the approach.
    platform_z = max(wall_h + 1.25, ground_z + gate_h + 0.85)
    super_h = platform_z - (ground_z + gate_h + 0.28)
    if super_h > 0.05:
        # Solid cut-stone breastwork wall above lintel up to platform floor
        create_beveled_box(bm, size=(gap_w + 1.24, frame_depth, super_h),
                           location=(cx + ox * push, cy + oy * push, ground_z + gate_h + 0.28 + super_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Overhanging machicolated defensive platform / fighting deck
    plat_w = gap_w + 1.80
    plat_depth = frame_depth + 0.50
    plat_push = push + 0.20
    create_beveled_box(bm, size=(plat_w, plat_depth, 0.22),
                       location=(cx + ox * plat_push, cy + oy * plat_push, platform_z + 0.11),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02)

    # Stone corbels supporting the cantilevered fighting platform
    n_corbels = max(3, int(plat_w / 1.10))
    corbel_step = (plat_w - 0.40) / max(1, n_corbels - 1)
    for ci in range(n_corbels):
        cu = -(plat_w - 0.40) * 0.5 + ci * corbel_step
        cpx = cx + tx * cu + ox * (push + 0.22)
        cpy = cy + ty * cu + oy * (push + 0.22)
        create_beveled_box(bm, size=(0.28, 0.45, 0.38),
                           location=(cpx, cpy, platform_z - 0.19),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    # Defensive crenellated battlements atop the elevated platform
    parapet_h = 0.45
    merlon_h = 0.65
    front_edge_push = plat_push + plat_depth * 0.5 - 0.12
    # Base parapet along front
    create_beveled_box(bm, size=(plat_w, 0.24, parapet_h),
                       location=(cx + ox * front_edge_push, cy + oy * front_edge_push, platform_z + 0.22 + parapet_h * 0.5),
                       rotation=(0.0, 0.0, ang),
                       mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)
    # Merlons (crenellations) along the front edge
    n_merlons = max(3, int(plat_w / 1.15))
    merlon_w = 0.52
    m_step = (plat_w - merlon_w) / max(1, n_merlons - 1)
    for mi in range(n_merlons):
        mu = -(plat_w - merlon_w) * 0.5 + mi * m_step
        mpx = cx + tx * mu + ox * front_edge_push
        mpy = cy + ty * mu + oy * front_edge_push
        create_beveled_box(bm, size=(merlon_w, 0.24, merlon_h),
                           location=(mpx, mpy, platform_z + 0.22 + parapet_h + merlon_h * 0.5),
                           rotation=(0.0, 0.0, ang),
                           mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015)

    if gate_towers:
        from .gatehouse import build_flanking_gate_towers
        # Tower-local tangent offset where the continuation-stair top landing
        # laps over the tower deck (must match build_gatehouse_access_stairs):
        # top_land_u - tower_c = top_off - tower_r - 3.98 for either flank.
        _top_off = gate_stair_top_offset(True)
        _rear_mid = _top_off - 1.90 - 3.98
        build_flanking_gate_towers(bm, cx, cy, ground_z, gap_w=gap_w,
                                   wall_h=wall_h, wall_t=thickness, outward=(ox, oy),
                                   rear_door=(_rear_mid, 0.85))

    if portcullis:
        from .gatehouse import build_portcullis
        build_portcullis(bm, cx, cy, ground_z, width=gap_w, height=gate_h,
                         outward=(ox, oy))

    if drawbridge:
        from .gatehouse import build_drawbridge
        fwd_thresh = push + frame_depth * 0.5
        db_w = max(2.2, gap_w - 0.24)
        build_drawbridge(bm, cx, cy, ground_z, width=db_w, length=max(3.8, gate_h * 1.40),
                         outward=(ox, oy), angle_deg=drawbridge_angle, has_chains=True,
                         pier_h=gate_h, wall_t=thickness, fwd_offset=fwd_thresh)

    # Courtyard rampart access stairs flanking the gate
    build_gatehouse_access_stairs(bm, cx, cy, (ox, oy), gap_w, ground_z,
                                  wall_h=wall_h, thickness=thickness,
                                  top_off=gate_stair_top_offset(gate_towers),
                                  gate_towers=gate_towers)


def build_curtain_wall_enclosure(bm, props, ctx, height=None, thickness=None,
                                 offset=None):
    """Enclose the whole compound with a stone curtain wall and front gatehouse.

    Corner towers stand fully inside the enclosure (see
    :func:`bastion.courtyard_tower_centers`), so every run goes corner to
    corner with only the gate opening.
    Returns (x_min, x_max, y_min, y_max, gate_u0_world, gate_u1_world).
    """
    off = offset if offset is not None else fortification_offset(props)
    x_min, x_max, y_min, y_max = compound_bounds(
        ctx, off, fortification_depth_extra(props))
    gate_cx = ctx.main_door_cx
    gate_half = max(1.35, (getattr(props, 'door_width', 1.2) + 1.6) * 0.5)
    g0, g1 = gate_cx - gate_half, gate_cx + gate_half

    H = height if height is not None else getattr(props, 'curtain_wall_height', 4.2)
    T = thickness if thickness is not None else getattr(props, 'curtain_wall_thickness', 0.55)
    gate_h = max(3.5, min(4.4, H * 0.88))

    # Towers ARE the corners: runs stop at the tower faces so the wall
    # terminates into the bastion (its outer faces continue the wall plane).
    if getattr(props, 'has_bastion_towers', False):
        from .bastion import courtyard_tower_rects
        _r = courtyard_tower_rects(props, ctx)
        _fl, _fr = _r[0], _r[1]
        front_x0, front_x1 = _fl[1], _fr[0]
        side_y0 = _fl[3]
        if len(_r) >= 4:
            _br, _bl = _r[2], _r[3]
            back_x0, back_x1 = _bl[1], _br[0]
            side_y1_left, side_y1_right = _bl[2], _br[2]
        else:
            back_x0, back_x1 = x_min, x_max
            side_y1_left = side_y1_right = y_max
    else:
        front_x0, front_x1 = x_min, x_max
        back_x0, back_x1 = x_min, x_max
        side_y0 = y_min
        side_y1_left = side_y1_right = y_max

    # Stone corner piers wherever no bastion swallows the joint (see below).
    _has_bast = getattr(props, 'has_bastion_towers', False)
    _n_bast = int(getattr(props, 'bastion_tower_count', 2)) if _has_bast else 0
    _post_FL = not _has_bast
    _post_FR = not _has_bast
    _post_BL = not (_has_bast and _n_bast >= 4)
    _post_BR = not (_has_bast and _n_bast >= 4)
    _post_clr = T * 0.5 + 0.14 + 0.12

    # Front run with the gate opening.
    build_curtain_wall_run(
        bm, (front_x0, y_min), (front_x1, y_min), (0.0, -1.0), 0.0, H, T,
        gate={'u0': g0 - front_x0, 'u1': g1 - front_x0, 'h': gate_h,
              'breach': gate_stair_top_offset(getattr(props, 'has_gate_towers', False)) + 1.5},
        merlon_end_clear=(
            _post_clr if (_post_FL and front_x0 <= x_min + 0.01) else 0.0,
            _post_clr if (_post_FR and front_x1 >= x_max - 0.01) else 0.0),
        seed=ctx.seed)
    # Back run.
    build_curtain_wall_run(
        bm, (back_x0, y_max), (back_x1, y_max), (0.0, 1.0), 0.0, H, T,
        merlon_end_clear=(
            _post_clr if (_post_BL and back_x0 <= x_min + 0.01) else 0.0,
            _post_clr if (_post_BR and back_x1 >= x_max - 0.01) else 0.0),
        seed=ctx.seed + 1)
    # Left and right runs. Wherever no corner tower swallows the joint,
    # they tuck just inside the front/back runs (half a thickness + a hair)
    # instead of overlapping them full-cube: stacked TxT corner cubes put
    # coincident faces on top of each other, which z-fights.
    _ly0 = side_y0 if _has_bast else y_min + T * 0.5 + 0.02
    _ly1l = side_y1_left if (_has_bast and _n_bast >= 4) else y_max - T * 0.5 - 0.02
    _ly1r = side_y1_right if (_has_bast and _n_bast >= 4) else y_max - T * 0.5 - 0.02
    build_curtain_wall_run(
        bm, (x_min, _ly0), (x_min, _ly1l), (-1.0, 0.0), 0.0, H, T,
        merlon_end_clear=(
            _post_clr if (_post_FL and _ly0 <= y_min + 0.01) else 0.0,
            _post_clr if (_post_BL and _ly1l >= y_max - 0.01) else 0.0),
        seed=ctx.seed + 2)
    build_curtain_wall_run(
        bm, (x_max, _ly0), (x_max, _ly1r), (1.0, 0.0), 0.0, H, T,
        merlon_end_clear=(
            _post_clr if (_post_FR and _ly0 <= y_min + 0.01) else 0.0,
            _post_clr if (_post_BR and _ly1r >= y_max - 0.01) else 0.0),
        seed=ctx.seed + 3)
    for (_do, _px, _py) in ((_post_FL, x_min, y_min),
                            (_post_FR, x_max, y_min),
                            (_post_BL, x_min, y_max),
                            (_post_BR, x_max, y_max)):
        if _do:
            _build_corner_post(bm, _px, _py, T, H, ground_z=0.0)

    # Gatehouse dressing over the front opening.
    build_gate_house(
        bm, gate_cx, y_min, (0.0, -1.0), g1 - g0, 0.0, T,
        gate_h=gate_h, portcullis=getattr(props, 'has_portcullis', False),
        drawbridge=getattr(props, 'has_drawbridge', False),
        drawbridge_angle=getattr(props, 'drawbridge_angle', 22.0),
        gate_towers=getattr(props, 'has_gate_towers', False),
        wall_h=H,
    )

    return (x_min, x_max, y_min, y_max, g0, g1)
