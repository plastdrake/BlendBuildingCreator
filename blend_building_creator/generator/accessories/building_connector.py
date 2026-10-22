"""
Building and Tower Interconnection System.

Provides procedural architectural links, skybridges, gallerias, and tower vestibules
to chain multiple buildings and towers together into unified castle / citadel complexes.

Key Functions:
- build_skybridge_link: Enclosed elevated walkway spanning between two buildings,
  featuring framed portals into both buildings, stone-mullioned windows, a soaring
  underpass arch vault beneath for stairs/path clearance, and a walkable battlement
  or pitched shingle roof.
- build_tower_building_connector: Architectural masonry vestibule and portal link
  connecting a round tower into an adjacent building with framed stone archways and quoins.
- build_curtain_wall_gate_portal: Fortified stone gatehouse with arched opening,
  voussoir ring, iron portcullis, and battlement parapet for plateau rim walls.
- chain_buildings: High-level modular utility for interconnecting multiple buildings in a chain.
"""

import math
from mathutils import Vector, Matrix, Euler

from ..mesh_utils import create_box, create_beveled_box, create_cylinder, create_cone
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_FLOOR,
    MAT_INDEX_TIMBER, MAT_INDEX_GLASS, MAT_INDEX_SHINGLES,
    MAT_INDEX_IRON, MAT_INDEX_PLASTER_EXT, MAT_INDEX_WOOD,
    MAT_INDEX_CLAY, MAT_INDEX_PUMPKIN, MAT_INDEX_RUG_1, MAT_INDEX_RUG_2,
    MAT_INDEX_RUG_3, MAT_INDEX_PLANT, MAT_INDEX_BREAD, MAT_INDEX_UPHOLSTERY,
    MAT_INDEX_CLOTH_LINEN, MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_FABRIC_WHITE,
    MAT_INDEX_FABRIC_RED, MAT_INDEX_FABRIC_STITCHED, MAT_INDEX_LEATHER,
    MAT_INDEX_LEATHER_2, MAT_INDEX_LEATHER_3, MAT_INDEX_BOOK_PAPER,
    MAT_INDEX_WAX, MAT_INDEX_PUMPKIN_STEM, MAT_INDEX_LANTERN,
    MAT_INDEX_HAY, MAT_INDEX_ROPE, MAT_INDEX_TARP,
    MAT_INDEX_OPEN_BOOK, MAT_INDEX_LOG, MAT_INDEX_PLASTER_INT,
    MAT_INDEX_CLIFFS, MAT_INDEX_DIRT
)
from .battlement import build_battlement_run
from .gatehouse import build_portcullis
from ..openings import build_window_assembly



def _merge_sub_bmesh(dst_bm, src_bm, transform_mat=None):
    """Transforms and merges geometry from src_bm into dst_bm preserving UVs and materials."""
    import bmesh
    if transform_mat is not None:
        bmesh.ops.transform(src_bm, matrix=transform_mat, verts=src_bm.verts)
    src_uv = src_bm.loops.layers.uv.verify()
    dst_uv = dst_bm.loops.layers.uv.verify()
    v_map = {}
    for v in src_bm.verts:
        v_map[v] = dst_bm.verts.new(v.co)
    for f in src_bm.faces:
        nf = dst_bm.faces.new([v_map[v] for v in f.verts])
        nf.material_index = f.material_index
        for loop, nloop in zip(f.loops, nf.loops):
            nloop[dst_uv].uv = loop[src_uv].uv


PROP_ONLY_MATERIALS = {
    MAT_INDEX_LEATHER, MAT_INDEX_LEATHER_2, MAT_INDEX_LEATHER_3,
    MAT_INDEX_BOOK_PAPER, MAT_INDEX_OPEN_BOOK, MAT_INDEX_WAX,
    MAT_INDEX_LANTERN, MAT_INDEX_RUG_1, MAT_INDEX_RUG_2, MAT_INDEX_RUG_3,
    MAT_INDEX_UPHOLSTERY, MAT_INDEX_CLOTH_LINEN, MAT_INDEX_FABRIC_WHITE,
    MAT_INDEX_FABRIC_RED, MAT_INDEX_FABRIC_STITCHED, MAT_INDEX_BOTTLE_GLASS,
    MAT_INDEX_CLAY, MAT_INDEX_PLANT, MAT_INDEX_BREAD, MAT_INDEX_PUMPKIN,
    MAT_INDEX_PUMPKIN_STEM, MAT_INDEX_HAY, MAT_INDEX_ROPE, MAT_INDEX_TARP
}

PROP_ALLOWED_MATERIALS = PROP_ONLY_MATERIALS | {MAT_INDEX_WOOD, MAT_INDEX_IRON, MAT_INDEX_TIMBER}

NON_PROP_MATERIALS = {
    MAT_INDEX_FLOOR, MAT_INDEX_STONE, MAT_INDEX_CUT_STONE,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_SHINGLES,
    MAT_INDEX_CLIFFS, MAT_INDEX_DIRT, MAT_INDEX_LOG
}

# Materials that make up the BUILDING itself (walls, cladding, rock). Used by
# the portal carver: it may cut these away to open a passage, but it must never
# touch a floor slab (that punched holes in the floors) and never slice props.
CARVE_STRUCTURAL_MATERIALS = {
    MAT_INDEX_STONE, MAT_INDEX_CUT_STONE,
    MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_SHINGLES,
    MAT_INDEX_CLIFFS, MAT_INDEX_DIRT, MAT_INDEX_LOG,
    MAT_INDEX_TIMBER, MAT_INDEX_WOOD,
}


def purge_props_in_volume(bm, x_span, y_span, z_span, max_prop_area=2.5):
    """
    Finds any props (furniture, kitchen items, dishes, rugs, decorations, clutter)
    whose geometry touches or overlaps the given box, and cleanly deletes the
    ENTIRE connected prop mesh component and adjacent detached pieces (bun feet,
    cushions, armrests, pillows, pots, books, lantern glow) without slicing or leaving
    stumps behind.
    Structural architectural elements (walls, corner pillars, timber wall framing,
    window assemblies, roofs, foundations, floors) are strictly protected.

    A prop is always removed WHOLE or not at all: the connected component is
    grown across every prop-material face (including large ones such as a
    table top or a mattress), so a table can never lose its legs and keep its
    board. Components that belong to the architecture (too big, or physically
    touching stone/plaster/floor) are left alone.
    """
    x0, x1 = min(x_span), max(x_span)
    y0, y1 = min(y_span), max(y_span)
    z0, z1 = min(z_span), max(z_span)

    # 1. Identify seed candidate faces strictly within [x0, x1] x [y0, y1] x [z0, z1]
    candidate_faces = []
    for f in bm.faces:
        if not f.is_valid:
            continue
        if f.material_index in NON_PROP_MATERIALS:
            continue
        if f.material_index not in PROP_ALLOWED_MATERIALS:
            continue
        c = f.calc_center_median()
        if (x0 <= c.x <= x1) and (y0 <= c.y <= y1) and (z0 <= c.z <= z1):
            candidate_faces.append(f)

    if not candidate_faces:
        return

    # 2. Group candidate faces into full connected components and validate they are genuine props
    visited = set()
    components_to_purge = []

    for f in candidate_faces:
        if f in visited or not f.is_valid:
            continue
        comp = [f]
        visited.add(f)
        q = [f]
        touches_non_prop = False

        while q:
            curr = q.pop()
            for e in curr.edges:
                for nxt in e.link_faces:
                    if not nxt.is_valid:
                        continue
                    if nxt.material_index in NON_PROP_MATERIALS:
                        touches_non_prop = True
                        continue
                    if nxt.material_index not in PROP_ALLOWED_MATERIALS:
                        continue
                    # Grow across EVERY prop face (large ones included) so the
                    # prop is always removed as one whole piece.
                    if nxt not in visited:
                        visited.add(nxt)
                        comp.append(nxt)
                        q.append(nxt)

        if touches_non_prop:
            # Component is physically connected to stone/plaster/floor/shingles -> Structural architecture!
            continue

        # Check component bounding dimensions
        verts = set(v for cf in comp for v in cf.verts)
        sz = max(v.co.z for v in verts) - min(v.co.z for v in verts)
        sx = max(v.co.x for v in verts) - min(v.co.x for v in verts)
        sy = max(v.co.y for v in verts) - min(v.co.y for v in verts)

        # Pillars, wall studs, framing, or siding wall runs are tall (sz >= 2.90) or broad (sx/sy >= 3.80)
        if sz >= 2.90 or sx >= 3.80 or sy >= 3.80:
            continue

        components_to_purge.append(comp)

    if not components_to_purge:
        return

    prop_faces = set(f for comp in components_to_purge for f in comp)

    # 3. Single tight cluster sweep: pick up small disjoint pieces that belong to
    # an already purged prop (bun feet, cushions, jars, plants) but NEVER widen the
    # search volume. The old 3-round sweep grew the box by 1.4 m every round and
    # stripped whole buildings of their furniture.
    p_x0 = min(v.co.x for pf in prop_faces for v in pf.verts) - 0.35
    p_x1 = max(v.co.x for pf in prop_faces for v in pf.verts) + 0.35
    p_y0 = min(v.co.y for pf in prop_faces for v in pf.verts) - 0.35
    p_y1 = max(v.co.y for pf in prop_faces for v in pf.verts) + 0.35
    p_z0 = min(v.co.z for pf in prop_faces for v in pf.verts) - 0.25
    p_z1 = max(v.co.z for pf in prop_faces for v in pf.verts) + 0.60

    extra_seeds = []
    for f in bm.faces:
        if not f.is_valid or f in visited:
            continue
        if f.material_index in NON_PROP_MATERIALS or f.material_index not in PROP_ALLOWED_MATERIALS:
            continue
        c = f.calc_center_median()
        if (p_x0 <= c.x <= p_x1) and (p_y0 <= c.y <= p_y1) and (p_z0 <= c.z <= p_z1):
            extra_seeds.append(f)

    for f in extra_seeds:
        if f in visited or not f.is_valid:
            continue
        comp = [f]
        visited.add(f)
        q = [f]
        touches_non_prop = False
        while q:
            curr = q.pop()
            for e in curr.edges:
                for nxt in e.link_faces:
                    if not nxt.is_valid:
                        continue
                    if nxt.material_index in NON_PROP_MATERIALS:
                        touches_non_prop = True
                        continue
                    if nxt.material_index not in PROP_ALLOWED_MATERIALS:
                        continue
                    if nxt not in visited:
                        visited.add(nxt)
                        comp.append(nxt)
                        q.append(nxt)
        if touches_non_prop:
            continue
        verts = set(v for cf in comp for v in cf.verts)
        sz = max(v.co.z for v in verts) - min(v.co.z for v in verts)
        sx = max(v.co.x for v in verts) - min(v.co.x for v in verts)
        sy = max(v.co.y for v in verts) - min(v.co.y for v in verts)
        if sz >= 2.90 or sx >= 3.80 or sy >= 3.80:
            continue
        for cf in comp:
            prop_faces.add(cf)

    # Cascade-delete nearby parts of the same prop. Parts of the same prop
    # (e.g. table legs and tabletop, shelf boards and side panels) are often
    # separate bmesh components with no shared edges. If any part sits in the
    # purge volume, the whole prop should go - otherwise we leave "half-loaded"
    # furniture (floating tabletops, headless shelves, etc.).
    #
    # Implemented as a single-pass worklist flood-fill instead of repeatedly
    # rescanning the whole bmesh: each candidate face is indexed once by its
    # vertices, and we only expand from faces just marked for deletion. Each
    # face enters the purge set at most once, so the cascade is linear in the
    # number of prop faces rather than quadratic in the whole mesh. This matters
    # on large citadels such as Nasher's Manor, where purge_props_in_volume is
    # run 8+ times during a single generation.
    CASCADE_DIST = 0.05
    if prop_faces:
        # Index candidate faces by grid cell, split into two tiers:
        #   * PROP_ONLY_MATERIALS (fabrics, upholstery, leather, books, rugs):
        #     cascade freely - these never appear in architecture, so we can
        #     safely pull in detached cushions/pillows/mattress parts.
        #   * Shared materials (WOOD, TIMBER, IRON): only index faces inside
        #     the ORIGINAL purge volume. This catches prop parts clipped by the
        #     portal/doorway without letting the cascade wander into a nearby
        #     wall plank or beam and punch a hole in the architecture.
        cand_grid = {}
        shared_grid = {}

        def _cell(c):
            return (int(c.x / CASCADE_DIST), int(c.y / CASCADE_DIST), int(c.z / CASCADE_DIST))

        def _in_volume(c):
            return x0 <= c.x <= x1 and y0 <= c.y <= y1 and z0 <= c.z <= z1

        for f in bm.faces:
            if not f.is_valid or f in prop_faces:
                continue
            if f.material_index in NON_PROP_MATERIALS or f.material_index not in PROP_ALLOWED_MATERIALS:
                continue
            if f.calc_area() > max_prop_area:
                continue
            for v in f.verts:
                cell = _cell(v.co)
                if f.material_index in PROP_ONLY_MATERIALS:
                    cand_grid.setdefault(cell, []).append(f)
                else:
                    # Shared material: only consider if inside the purge volume
                    if _in_volume(v.co):
                        shared_grid.setdefault(cell, []).append(f)

        # Worklist flood-fill: expand from faces just marked for deletion,
        # discovering detached parts of the same prop (legs, tabletop, cushions).
        worklist = list(prop_faces)
        while worklist:
            f = worklist.pop()
            for v in f.verts:
                c = v.co
                gx, gy, gz = _cell(c)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            cell = (gx + dx, gy + dy, gz + dz)
                            # Prop-exclusive materials: cascade freely by proximity.
                            for nf in cand_grid.get(cell, ()):
                                if nf in prop_faces:
                                    continue
                                if not any(
                                    abs(nv.co.x - c.x) <= CASCADE_DIST
                                    and abs(nv.co.y - c.y) <= CASCADE_DIST
                                    and abs(nv.co.z - c.z) <= CASCADE_DIST
                                    for nv in nf.verts
                                ):
                                    continue
                                prop_faces.add(nf)
                                worklist.append(nf)
                            # Shared materials: only cascade into faces that lie
                            # inside the original purge volume, so architecture
                            # outside the volume (wall planks, beams) is spared.
                            for nf in shared_grid.get(cell, ()):
                                if nf in prop_faces:
                                    continue
                                if not _in_volume(nf.calc_center_median()):
                                    continue
                                if not any(
                                    abs(nv.co.x - c.x) <= CASCADE_DIST
                                    and abs(nv.co.y - c.y) <= CASCADE_DIST
                                    and abs(nv.co.z - c.z) <= CASCADE_DIST
                                    for nv in nf.verts
                                ):
                                    continue
                                prop_faces.add(nf)
                                worklist.append(nf)
    if prop_faces:
        import bmesh
        bmesh.ops.delete(bm, geom=list(prop_faces), context='FACES')
        loose_edges = [e for e in bm.edges if not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        orphan_verts = [v for v in bm.verts if not v.link_faces and not v.link_edges]
        if orphan_verts:
            bmesh.ops.delete(bm, geom=orphan_verts, context='VERTS')


def clean_orphan_floating_props(bm):
    """
    Detects and deletes any small elevated prop clutter items (pots, cups, folded cloth,
    succulents/plants, jars, loose plates, bottles) that have become detached or left floating
    in mid-air (min_z >= 0.35) without any solid supporting structure (table, shelf, desk,
    bench, floor, or ground) within 0.14m beneath them.
    Uses spatial grid indexing for fast sub-second execution on large castle meshes.
    """
    import bmesh
    from ..materials import (
        MAT_INDEX_PLANT, MAT_INDEX_CLAY, MAT_INDEX_FABRIC_WHITE,
        MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_GLASS
    )

    PROP_CLUTTER_MATS = {
        MAT_INDEX_PLANT, MAT_INDEX_CLAY, MAT_INDEX_FABRIC_WHITE,
        MAT_INDEX_BOTTLE_GLASS, MAT_INDEX_GLASS
    }

    # Pre-index solid upward-facing surfaces into 0.5m spatial grid.
    # Plant foliage is indexed too: a tall planter's upper leaves sit far above
    # its pot and would otherwise look like unsupported floating clutter and
    # get deleted, which stripped the plants down to a bare stalk.
    grid = {}
    for f in bm.faces:
        if not f.is_valid:
            continue
        if f.material_index in PROP_CLUTTER_MATS and f.material_index != MAT_INDEX_PLANT:
            continue
        if f.normal.z < 0.35:
            continue
        c = f.calc_center_median()
        gx, gy = int(c.x * 2.0), int(c.y * 2.0)
        grid.setdefault((gx, gy), []).append(c.z)

    visited = set()
    floating_components = []

    for f in bm.faces:
        if not f.is_valid or f in visited:
            continue
        if f.material_index not in PROP_CLUTTER_MATS:
            continue
        if f.calc_area() > 0.8:
            continue

        comp = [f]
        visited.add(f)
        q = [f]
        pure_clutter = True

        while q:
            curr = q.pop()
            for e in curr.edges:
                for nxt in e.link_faces:
                    if not nxt.is_valid:
                        continue
                    if nxt.material_index not in PROP_CLUTTER_MATS:
                        pure_clutter = False
                        break
                    if nxt not in visited:
                        visited.add(nxt)
                        comp.append(nxt)
                        q.append(nxt)
                if not pure_clutter:
                    break
            if not pure_clutter:
                break

        if not pure_clutter:
            continue

        verts = [v for cf in comp for v in cf.verts]
        min_z = min(v.co.z for v in verts)
        max_z = max(v.co.z for v in verts)
        min_x = min(v.co.x for v in verts)
        max_x = max(v.co.x for v in verts)
        min_y = min(v.co.y for v in verts)
        max_y = max(v.co.y for v in verts)

        # Clutter sitting directly on ground or lowest floor is legit
        if min_z < 0.35:
            continue
        # Clutter items are compact. Foliage is allowed to be much bigger: a
        # whole plant is a single leaf cluster and must never be culled just
        # because it is wide.
        if f.material_index == MAT_INDEX_PLANT:
            if (max_z - min_z > 2.60) or (max_x - min_x > 2.20) or (max_y - min_y > 2.20):
                continue
        else:
            if (max_z - min_z > 1.2) or (max_x - min_x > 1.0) or (max_y - min_y > 1.0):
                continue

        # Check neighbor grid cells for supporting solid face beneath
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        cgx, cgy = int(cx * 2.0), int(cy * 2.0)
        has_support = False
        z_lo = min_z - 0.16
        z_hi = min_z + 0.04

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                zs = grid.get((cgx + dx, cgy + dy))
                if zs:
                    for sz in zs:
                        if z_lo <= sz <= z_hi:
                            has_support = True
                            break
                if has_support:
                    break
            if has_support:
                break

        if not has_support:
            floating_components.append(comp)

    faces_to_del = [f for comp in floating_components for f in comp if f.is_valid]
    if faces_to_del:
        bmesh.ops.delete(bm, geom=faces_to_del, context='FACES')
        loose_edges = [e for e in bm.edges if not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        orphan_verts = [v for v in bm.verts if not v.link_faces and not v.link_edges]
        if orphan_verts:
            bmesh.ops.delete(bm, geom=orphan_verts, context='VERTS')


def carve_pass_through_portal(bm, x_span, y_span, z_span):
    """Cuts through existing structural geometry in a box [x0, x1] x [y0, y1] x [z0, z1]
    so that doorways / portals are clear of intersecting walls.
    Removes whole props first so furniture is never sliced or booleaned through."""
    purge_props_in_volume(bm, x_span, y_span, z_span)

    import bmesh
    x0, x1 = min(x_span), max(x_span)
    y0, y1 = min(y_span), max(y_span)
    z0, z1 = min(z_span), max(z_span)

    pad = 0.8
    def _face_overlaps_box(f):
        xs = [v.co.x for v in f.verts]
        ys = [v.co.y for v in f.verts]
        zs = [v.co.z for v in f.verts]
        return not (max(xs) < x0 - pad or min(xs) > x1 + pad or
                    max(ys) < y0 - pad or min(ys) > y1 + pad or
                    max(zs) < z0 - pad or min(zs) > z1 + pad)

    # Only bisect non-prop structural materials (stone, plaster, walls).
    # Floors are NEVER cut - that used to punch holes in the floor slabs.
    cand_faces = [f for f in bm.faces if f.is_valid
                  and f.material_index in CARVE_STRUCTURAL_MATERIALS
                  and _face_overlaps_box(f)]
    if cand_faces:
        geom = list({v for f in cand_faces for v in f.verts}) + list({e for f in cand_faces for e in f.edges}) + cand_faces
        planes = [
            (Vector((x0, 0, 0)), Vector((1, 0, 0))),
            (Vector((x1, 0, 0)), Vector((1, 0, 0))),
            (Vector((0, y0, 0)), Vector((0, 1, 0))),
            (Vector((0, y1, 0)), Vector((0, 1, 0))),
            (Vector((0, 0, z0)), Vector((0, 0, 1))),
            (Vector((0, 0, z1)), Vector((0, 0, 1))),
        ]
        for pt, norm in planes:
            try:
                res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=pt, plane_no=norm)
                geom = res.get('geom', geom)
            except Exception:
                pass

    to_delete = [f for f in bm.faces if f.is_valid
                 and f.material_index in CARVE_STRUCTURAL_MATERIALS
                 and (x0 + 0.02 <= f.calc_center_median().x <= x1 - 0.02) and
                 (y0 + 0.02 <= f.calc_center_median().y <= y1 - 0.02) and
                 (z0 + 0.02 <= f.calc_center_median().z <= z1 - 0.02)]
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context='FACES')
        loose_edges = [e for e in bm.edges if not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        orphan_verts = [v for v in bm.verts if not v.link_faces and not v.link_edges]
        if orphan_verts:
            bmesh.ops.delete(bm, geom=orphan_verts, context='VERTS')


def build_portal_casing(
    bm,
    center,
    span_dir,
    trans_dir,
    yaw,
    cut_w,
    cut_h,
    cut_base_z,
    wall_t,
    floor_top_z,
    jamb_w=0.16,
    casing_d=0.030,
    side_overlap=0.03,
    head_overlap=0.04,
    frame_offset=0.0,
    threshold_lift=0.0,
    mat=MAT_INDEX_TIMBER,
    threshold_mat=None,
):
    """Build a timber portal casing that straddles a wall opening.

    The casing is centred on the wall plane and is ``wall_t + 2 * casing_d``
    deep, so it sits halfway inside the room and halfway inside the
    connector/corridor and only stands a few centimetres proud of each wall
    face - exactly like a real door casing instead of a free standing frame.

    The jamb posts overlap the cut edges of the wall opening and the head beam
    covers the cut head, so no raw cut masonry is ever visible around the
    frame. ``cut_w`` / ``cut_h`` describe the opening that was cut in the wall;
    the resulting clear passage is marginally smaller than that cut.

    ``frame_offset`` slides the whole casing along the span direction (positive
    = deeper into the connector) and ``threshold_lift`` raises the threshold
    plate by that many metres.

    Only three pieces are produced per portal (two posts + head beam) plus one
    optional flush threshold plate - no duplicate architraves, no oversized
    floating lintel, no second threshold.
    """
    # A frame that is pushed deeper into the connector also grows deeper, so it
    # keeps lining the wall reveal instead of leaving raw masonry exposed.
    frame_t = wall_t + casing_d * 2.0 + max(0.0, frame_offset)
    # Head beam underside sits just below the cut head so it always covers it.
    head_z = cut_base_z + cut_h - head_overlap
    # Posts overlap the cut edges of the opening.
    post_off = cut_w * 0.5 - side_overlap + jamb_w * 0.5
    frame_c = center + span_dir * frame_offset
    # The threshold always stays on the wall plane (it covers the floor seam).
    thresh_c = center

    # A. Two jamb posts straddling the cut edges of the opening. They stop
    #    exactly UNDER the head beam so the beam rests on the posts and the
    #    two never intersect or overlap.
    for side in (-1.0, 1.0):
        p = frame_c + trans_dir * (side * post_off)
        create_beveled_box(
            bm, size=(frame_t, jamb_w, head_z - floor_top_z),
            location=(p.x, p.y, (floor_top_z + head_z) * 0.5),
            rotation=(0.0, 0.0, yaw),
            mat_index=mat, bevel_amount=0.010
        )

    # B. Head beam resting squarely on top of the posts, covering the cut head
    head_w = cut_w - side_overlap * 2.0 + jamb_w * 2.0
    create_beveled_box(
        bm, size=(frame_t, head_w, jamb_w),
        location=(frame_c.x, frame_c.y, head_z + jamb_w * 0.5),
        rotation=(0.0, 0.0, yaw),
        mat_index=mat, bevel_amount=0.010
    )

    # C. Single flush threshold plate covering the floor seam under the casing
    if threshold_mat is not None:
        create_beveled_box(
            bm, size=(frame_t, head_w, 0.035),
            location=(thresh_c.x, thresh_c.y, floor_top_z + threshold_lift - 0.0175),
            rotation=(0.0, 0.0, yaw),
            mat_index=threshold_mat, bevel_amount=0.004
        )


def build_skybridge_link(
    bm,
    p1,
    p2,
    width=9.0,
    floor_z=18.5,
    ceiling_h=3.6,
    wall_thickness=0.55,
    underpass_clearance=None,
    wall_mat=MAT_INDEX_STONE,
    trim_mat=MAT_INDEX_CUT_STONE,
    deck_mat=MAT_INDEX_FLOOR,
    roof_style='BATTLEMENTS',
    has_windows=True,
    num_windows=2,
    has_portals=True,
    has_underpass_arch=True,
    underpass_spring_z=11.5,
    portal_width=2.20,
    portal_height=3.20,
    host_wall_thickness=0.38,
    skybridge_frame_offset=0.40,
    skybridge_threshold_lift=0.02,
):
    """
    Spans an enclosed architectural skybridge between two building facades at p1 and p2.

    ``p1``/``p2`` are the wall CENTRES of the two host facades. The portal
    casings are built centred on those wall planes so each frame sits half in
    the hall and half in the bridge, covering the cut-out left in the wall.
    """
    v1 = Vector((p1[0], p1[1], floor_z))
    v2 = Vector((p2[0], p2[1], floor_z))
    span_vec = v2 - v1
    span_len = span_vec.length
    if span_len < 0.5:
        return

    # Orthonormal basis for the link:
    # X_axis along span (from p1 to p2), Y_axis transverse across width, Z_axis vertical
    span_dir = span_vec.normalized()
    z_axis = Vector((0.0, 0.0, 1.0))
    trans_dir = z_axis.cross(span_dir).normalized()  # Perpendicular horizontal direction
    yaw = math.atan2(span_dir.y, span_dir.x)
    center = (v1 + v2) * 0.5

    # Exterior clear span between building facades: facades sit 0.19m outward from the wall centers (p1/p2).
    # All heavy structural stone slabs (floor slab, ceiling slab, roof rampart deck) and side walls must stop
    # flush at the exterior facade (ext_span_len) so they NEVER penetrate the 0.38m walls into rooms above or below.
    ext_span_len = max(0.5, span_len - 0.44)

    # 1. FLOOR STRUCTURE & WALKWAY DECK
    deck_thick = 0.38
    # Heavy stone structural floor slab stops flush at exterior facade (ext_span_len)
    create_beveled_box(
        bm, size=(ext_span_len, width, deck_thick - 0.06),
        location=(center.x, center.y, floor_z + 0.05 - deck_thick + (deck_thick - 0.06) * 0.5),
        rotation=(0.0, 0.0, yaw),
        mat_index=trim_mat, bevel_amount=0.025
    )
    # Interior wooden floorboards RAISED 5 CM (top surface at floor_z + 0.05, perfectly flush with room floors)
    create_beveled_box(
        bm, size=(span_len, width - wall_thickness * 2.0, 0.06),
        location=(center.x, center.y, floor_z + 0.02),
        rotation=(0.0, 0.0, yaw),
        mat_index=deck_mat, bevel_amount=0.005
    )

    # 2. UNDERPASS CLEARANCE BENEATH THE SPAN
    # Kept clean and open without stepped stone corbels embedded in walls

    # 3. SIDE WALLS & CUT-THROUGH WINDOWS
    wall_h = ceiling_h
    wall_cz = floor_z + wall_h * 0.5
    for side in (-1.0, 1.0):
        wall_offset = side * (width * 0.5 - wall_thickness * 0.5)
        wall_pos = center + trans_dir * wall_offset

        if not (has_windows and num_windows > 0):
            # Solid wall stopping flush at facades
            create_beveled_box(
                bm, size=(ext_span_len, wall_thickness, wall_h),
                location=(wall_pos.x, wall_pos.y, wall_cz),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )
        else:
            outward_vec = trans_dir * side
            facing_angle = math.atan2(outward_vec.x, -outward_vec.y)

            win_w = 1.10
            win_h = 1.50
            sill_z = floor_z + 0.90
            win_cz = sill_z + win_h * 0.5
            win_top_z = sill_z + win_h

            # Lower spandrel wall beneath sills (stops flush at facades)
            spandrel_top_z = sill_z - 0.14
            spandrel_h = spandrel_top_z - floor_z
            create_beveled_box(
                bm, size=(ext_span_len, wall_thickness, spandrel_h),
                location=(wall_pos.x, wall_pos.y, floor_z + spandrel_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )

            # Upper lintel wall above window heads (stops flush at facades)
            lintel_bot_z = win_top_z + 0.17
            lintel_h = (floor_z + wall_h) - lintel_bot_z
            create_beveled_box(
                bm, size=(ext_span_len, wall_thickness, lintel_h),
                location=(wall_pos.x, wall_pos.y, lintel_bot_z + lintel_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=wall_mat, bevel_amount=0.02
            )

            # Piers flanking and separating the windows
            pier_h = lintel_bot_z - spandrel_top_z
            pier_cz = (lintel_bot_z + spandrel_top_z) * 0.5
            step_w = ext_span_len / (num_windows + 1)
            u_prev = -ext_span_len * 0.5
            for wi in range(1, num_windows + 1):
                u_win = -ext_span_len * 0.5 + wi * step_w
                u_win_left = u_win - win_w * 0.5
                pier_w = u_win_left - u_prev
                if pier_w > 0.05:
                    p_center_u = (u_prev + u_win_left) * 0.5
                    p_pos = wall_pos + span_dir * p_center_u
                    create_beveled_box(
                        bm, size=(pier_w, wall_thickness, pier_h),
                        location=(p_pos.x, p_pos.y, pier_cz),
                        rotation=(0.0, 0.0, yaw),
                        mat_index=wall_mat, bevel_amount=0.02
                    )
                u_prev = u_win + win_w * 0.5

                # Dressed cut-stone masonry sill slab under window aperture
                win_pos = wall_pos + span_dir * u_win
                create_beveled_box(
                    bm, size=(win_w + 0.30, wall_thickness + 0.06, 0.14),
                    location=(win_pos.x, win_pos.y, spandrel_top_z + 0.07),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.02
                )

                # Dressed cut-stone masonry lintel block above window aperture
                create_beveled_box(
                    bm, size=(win_w + 0.34, wall_thickness + 0.06, 0.17),
                    location=(win_pos.x, win_pos.y, win_top_z + 0.085),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.02
                )

                # Build stylized fantasy window assembly with timber frames and open shutters
                build_window_assembly(
                    bm,
                    center=(win_pos.x, win_pos.y, win_cz),
                    size=(win_w, win_h),
                    wall_thickness=wall_thickness,
                    normal_axis=facing_angle,
                    has_shutters=True,
                    shutters_closed=False
                )

            # Final pier after last window
            u_end = ext_span_len * 0.5
            final_pier_w = u_end - u_prev
            if final_pier_w > 0.05:
                p_center_u = (u_prev + u_end) * 0.5
                p_pos = wall_pos + span_dir * p_center_u
                create_beveled_box(
                    bm, size=(final_pier_w, wall_thickness, pier_h),
                    location=(p_pos.x, p_pos.y, pier_cz),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=wall_mat, bevel_amount=0.02
                )

    # 4. CEILING & EXPOSED TIMBER BEAMS
    ceil_z = floor_z + wall_h
    ceil_thick = 0.32
    # Heavy stone structural ceiling slab stops flush at exterior facade (ext_span_len)
    create_beveled_box(
        bm, size=(ext_span_len, width, ceil_thick),
        location=(center.x, center.y, ceil_z + ceil_thick * 0.5),
        rotation=(0.0, 0.0, yaw),
        mat_index=trim_mat, bevel_amount=0.02
    )
    # Timber ceiling beams running across width (strictly internal between facades)
    n_beams = max(2, int(ext_span_len / 1.6))
    for bi in range(1, n_beams):
        bu = -ext_span_len * 0.5 + bi * (ext_span_len / n_beams)
        b_pos = center + span_dir * bu
        create_beveled_box(
            bm, size=(0.20, width - wall_thickness * 1.8, 0.22),
            location=(b_pos.x, b_pos.y, ceil_z - 0.11),
            rotation=(0.0, 0.0, yaw),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01
        )

    # 5. CONNECTION PORTALS AT BOTH BUILDING INTERFACES
    if has_portals:
        # The host walls cut an opening of (door size + reveal margin); the
        # casing is sized to cover that cut exactly.
        portal_margin = 0.02
        cut_w = portal_width + portal_margin * 2.0
        cut_h = portal_height + portal_margin
        floor_top_z = floor_z + 0.05  # walking surface of the bridge deck

        # 1. Cleanly purge interior props in doorway corridor (strictly inside room)
        corridor_half_w = portal_width * 0.5 + 0.15
        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            into_bld_vec = end_sign * span_dir
            # Interior corridor starts 0.45m inside the room (safely past exterior wall)
            # and extends 1.80m into the room
            c_start = pt + into_bld_vec * 0.45
            c_end = pt + into_bld_vec * 2.25
            x0 = min(c_start.x, c_end.x) - abs(trans_dir.x) * corridor_half_w
            x1 = max(c_start.x, c_end.x) + abs(trans_dir.x) * corridor_half_w
            y0 = min(c_start.y, c_end.y) - abs(trans_dir.y) * corridor_half_w
            y1 = max(c_start.y, c_end.y) + abs(trans_dir.y) * corridor_half_w
            purge_props_in_volume(
                bm,
                x_span=(x0, x1),
                y_span=(y0, y1),
                z_span=(floor_z + 0.04, floor_z + portal_height - 0.05)
            )

        for end_sign, pt in ((-1.0, v1), (1.0, v2)):
            # Purge raw cut stone / plaster wall faces in the doorway portal aperture
            portal_half_w = cut_w * 0.5 + 0.10
            aperture_faces = [
                f for f in bm.faces if f.is_valid
                and (abs((f.calc_center_median() - pt).dot(span_dir)) <= 0.35)
                and (abs((f.calc_center_median() - pt).dot(trans_dir)) <= portal_half_w)
                and (floor_z - 0.25 <= f.calc_center_median().z <= floor_z + cut_h)
                and f.material_index in (MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_CLIFFS, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER)
            ]
            if aperture_faces:
                import bmesh
                bmesh.ops.delete(bm, geom=aperture_faces, context='FACES')

            # Single casing centred on the wall plane: it straddles the wall
            # thickness (half in the hall, half in the bridge), overlaps the cut
            # edges of the opening and leaves no redundant trim pieces.
            # The skybridge frame sits 40 cm deeper inside the bridge so it
            # never crowds the hall, and its threshold is raised 2 cm.
            # The offset always points INTO the bridge (towards its centre),
            # never out into the room it connects to.
            build_portal_casing(
                bm,
                center=pt,
                span_dir=span_dir * (-end_sign),
                trans_dir=trans_dir,
                yaw=yaw,
                cut_w=cut_w,
                cut_h=cut_h,
                cut_base_z=floor_z,
                wall_t=host_wall_thickness,
                floor_top_z=floor_top_z,
                frame_offset=skybridge_frame_offset,
                threshold_lift=skybridge_threshold_lift,
                mat=MAT_INDEX_TIMBER,
                threshold_mat=deck_mat,
            )


    # 6. ROOF STRUCTURE
    roof_z = ceil_z + ceil_thick
    if roof_style == 'BATTLEMENTS':
        # Walkable stone rampart deck stops flush at exterior facades (ext_span_len) with zero roof penetration
        deck_pad = 0.25
        deck_cz = roof_z + deck_pad * 0.5
        create_beveled_box(
            bm, size=(ext_span_len, width + 0.45, deck_pad),
            location=(center.x, center.y, deck_cz),
            rotation=(0.0, 0.0, yaw),
            mat_index=trim_mat, bevel_amount=0.02
        )
        # Crenellated stone merlon battlements along north and south eaves
        # Inset by 0.55m along span direction so merlons do NOT overlap adjacent roofs/walls
        half_w = (width + 0.45) * 0.5
        for side in (-1.0, 1.0):
            p_a = v1 + span_dir * 0.55 + trans_dir * (side * half_w)
            p_b = v2 - span_dir * 0.55 + trans_dir * (side * half_w)
            build_battlement_run(
                bm, (p_a.x, p_a.y), (p_b.x, p_b.y),
                z_base=roof_z + deck_pad, height=1.05,
                thickness=0.36, style='STONE'
            )
        # Stepped corbel machicolation brackets under the parapet (strictly within span between walls)
        n_corbels = max(3, int(ext_span_len / 1.5))
        for ci in range(1, n_corbels):
            cu = -ext_span_len * 0.5 + ci * (ext_span_len / n_corbels)
            c_center = center + span_dir * cu
            for side in (-1.0, 1.0):
                corb_pos = c_center + trans_dir * (side * (half_w - 0.12))
                create_beveled_box(
                    bm, size=(0.30, 0.38, 0.48),
                    location=(corb_pos.x, corb_pos.y, roof_z - 0.24),
                    rotation=(0.0, 0.0, yaw),
                    mat_index=trim_mat, bevel_amount=0.02
                )
    elif roof_style == 'GABLE':
        from ..roof.gable_roof import build_gable_roof
        import bmesh
        roof_bm = bmesh.new()
        ridge_h = min(width * 0.42, 1.70)
        roof_w = width + 0.35
        build_gable_roof(
            roof_bm,
            x_min=-roof_w * 0.5,
            x_max=roof_w * 0.5,
            y_min=-ext_span_len * 0.5,
            y_max=ext_span_len * 0.5,
            z_base=0.0,
            roof_height=ridge_h,
            overhang=0.20,
            abut_front=True,
            abut_back=True,
            gable_ends=(),
            gable_walls=False,
        )
        # Coordinate transform: local Y is along span, local X is transverse, local Z is vertical
        tr_mat = Matrix((
            (trans_dir.x, span_dir.x, 0.0, center.x),
            (trans_dir.y, span_dir.y, 0.0, center.y),
            (0.0,         0.0,        1.0, roof_z),
            (0.0,         0.0,        0.0, 1.0)
        ))
        _merge_sub_bmesh(bm, roof_bm, tr_mat)
        roof_bm.free()


def build_tower_building_connector(
    bm,
    tower_cx,
    tower_cy,
    tower_r,
    tower_z_base,
    bld_wall_x,
    bld_y_span,
    floor_zs=(8.0, 11.7, 15.4),
    wall_mat=MAT_INDEX_STONE,
    trim_mat=MAT_INDEX_CUT_STONE,
    floor_h=3.7,
    max_vest_z=None,
    hall_step=0.80,
    corridor_y=None,
    bld_floor_z=14.45,
    bld_wall_t=0.36,
):
    """
    Constructs an architectural stone vestibule connection uniting a round tower
    with an adjacent building wall, complete with framed entrance portals and quoins.
    Features:
    - 2 clean wooden transition steps bridging the elevation difference between
      the building floor (Chapel 14.45) and the tower floor (Wizard's Spire 14.00).
    - Snug doorway casing overlapping the round tower wall cut with zero oversized holes.
    - Every wall, the ceiling and the floor run all the way up to the INSIDE
      face of the host building's wall, so no gap (and therefore no visible
      backface) can ever open between the connector and the room.
    - Deep foundation plinth well below wooden floors ensuring zero coplanar z-fighting.
    """
    # Vector from tower center to building wall
    dx = bld_wall_x - tower_cx
    dy = max(bld_y_span[0], min(bld_y_span[1], tower_cy)) - tower_cy
    dist = math.hypot(dx, dy)
    if dist < 0.2:
        return

    # Midpoint of connection
    mid_x = (tower_cx + bld_wall_x) * 0.5
    mid_y = corridor_y if corridor_y is not None else tower_cy + dy * 0.5

    door_w = 1.40
    door_h = 2.60
    wall_t = 0.40
    walk_w = 1.50

    # Direction from tower to building
    tower_dir = 1.0 if dx > 0 else -1.0
    x_tower_outer = tower_cx + tower_dir * tower_r
    x_tower_inner = tower_cx + tower_dir * (tower_r - 0.75)

    # The INSIDE face of the host building's wall. The connector has to reach
    # all the way to it (and a touch past it) - stopping at the wall centre
    # left a 0.18 m slot that showed the wall's backface.
    bld_inner_x = bld_wall_x + tower_dir * (bld_wall_t * 0.5 + 0.02)

    # Vestibule span: stops strictly flush at bld_wall_x with zero penetration into building interior
    x_start = x_tower_outer - tower_dir * 0.05
    x_end = bld_wall_x
    gap_x0 = min(x_start, x_end)
    gap_x1 = max(x_start, x_end)
    gap_len = max(0.2, gap_x1 - gap_x0)
    gap_cx = (gap_x0 + gap_x1) * 0.5

    max_z = max(floor_zs) + floor_h
    if max_vest_z is not None:
        max_z = min(max_z, max_vest_z)
    vest_h = max_z - tower_z_base

    fz_tower = min(floor_zs)

    # Walkway span strictly between tower exterior wall and building exterior wall
    x_walk_0 = min(x_tower_outer, bld_wall_x)
    x_walk_1 = max(x_tower_outer, bld_wall_x)
    walk_span = max(0.2, x_walk_1 - x_walk_0)
    walk_mid_x = (x_walk_0 + x_walk_1) * 0.5

    # 1. Carve pass-through portal strictly through the BUILDING wall (NOT the round tower wall)
    # The round tower doorway is already cleanly open with zero faces below 2.6m; bisecting it creates open holes.
    bld_carve_x0 = min(bld_wall_x - tower_dir * 0.10, bld_wall_x + tower_dir * 0.45)
    bld_carve_x1 = max(bld_wall_x - tower_dir * 0.10, bld_wall_x + tower_dir * 0.45)
    carve_w = 2.10

    # Purge any residual wall, stone, plaster or timber faces inside the portal volume across full 2.10m aperture
    p_x0 = min(x_walk_0 + 0.02, bld_carve_x0)
    p_x1 = max(x_walk_1 - 0.02, bld_carve_x1)

    # The whole walkway is cleared of furniture FIRST (and as whole pieces), so the
    # structural purge below can never leave a half-built table or a bed frame
    # without its mattress behind.
    purge_props_in_volume(
        bm,
        x_span=(p_x0 - 0.30, p_x1 + 0.30),
        y_span=(mid_y - carve_w * 0.5 - 0.30, mid_y + carve_w * 0.5 + 0.30),
        z_span=(bld_floor_z - 0.10, max_z + 0.50)
    )

    carve_pass_through_portal(
        bm,
        x_span=(bld_carve_x0, bld_carve_x1),
        y_span=(mid_y - carve_w * 0.5 + 0.02, mid_y + carve_w * 0.5 - 0.02),
        z_span=(bld_floor_z + 0.02, bld_floor_z + 2.86)
    )

    walkway_interior_purge = [
        f for f in bm.faces if f.is_valid
        and (p_x0 <= f.calc_center_median().x <= p_x1)
        and (mid_y - carve_w * 0.5 <= f.calc_center_median().y <= mid_y + carve_w * 0.5)
        and (bld_floor_z + 0.04 <= f.calc_center_median().z <= bld_floor_z + 2.88)
        and f.material_index in (
            MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_CLIFFS,
            MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT,
            MAT_INDEX_TIMBER, MAT_INDEX_WOOD
        )
    ]
    if walkway_interior_purge:
        import bmesh
        bmesh.ops.delete(bm, geom=walkway_interior_purge, context='FACES')

    # 2. Solid foundation plinth extending continuously underneath the walkway span (ZERO HOLES, ZERO GAP)
    plinth_x0 = min(x_tower_outer - tower_dir * 0.08, bld_inner_x)
    plinth_x1 = max(x_tower_outer - tower_dir * 0.08, bld_inner_x)
    plinth_len = plinth_x1 - plinth_x0
    plinth_cx = (plinth_x0 + plinth_x1) * 0.5
    plinth_top = bld_floor_z - 0.03
    plinth_h = plinth_top - tower_z_base
    if plinth_h > 0.05:
        create_beveled_box(
            bm, size=(plinth_len, walk_w + wall_t * 2.0, plinth_h),
            location=(plinth_cx, mid_y, tower_z_base + plinth_h * 0.5),
            mat_index=wall_mat, bevel_amount=0.03
        )

    # 3. Clean, continuous wooden floor deck spanning completely from Tower interior to Building interior
    # Level and flat with zero steps, holes, or elevation bumps
    fl_x0 = min(x_tower_inner - tower_dir * 0.04, bld_wall_x + tower_dir * 0.30)
    fl_x1 = max(x_tower_inner - tower_dir * 0.04, bld_wall_x + tower_dir * 0.30)
    fl_len = fl_x1 - fl_x0
    fl_cx = (fl_x0 + fl_x1) * 0.5
    create_beveled_box(
        bm, size=(fl_len, walk_w, 0.10),
        location=(fl_cx, mid_y, bld_floor_z + 0.02),
        mat_index=MAT_INDEX_FLOOR, bevel_amount=0.005
    )

    # 4. Flanking exterior masonry side walls. They run all the way to the
    #    INSIDE face of the building wall (plus 2 cm of overlap) so there is
    #    no slot between the connector and the room showing a backface.
    w_span_start = min(x_tower_outer - tower_dir * 0.08, bld_inner_x)
    w_span_end = max(x_tower_outer - tower_dir * 0.08, bld_inner_x)
    w_len = w_span_end - w_span_start
    w_cx = (w_span_start + w_span_end) * 0.5
    side_h = max_z - plinth_top

    for s_side in (-1.0, 1.0):
        wy = mid_y + s_side * (walk_w * 0.5 + wall_t * 0.5)
        create_beveled_box(
            bm, size=(w_len, wall_t, side_h),
            location=(w_cx, wy, plinth_top + side_h * 0.5),
            mat_index=wall_mat, bevel_amount=0.02
        )

    # 5. Clean wooden ceiling with timber tie joists, running to the inside
    #    face of the building wall so nothing shows through above the frame.
    ceil_z = bld_floor_z + door_h + 0.05
    ceil_x0 = min(x_tower_outer, bld_inner_x)
    ceil_x1 = max(x_tower_outer, bld_inner_x)
    create_beveled_box(
        bm, size=(ceil_x1 - ceil_x0, walk_w + 0.04, 0.08),
        location=((ceil_x0 + ceil_x1) * 0.5, mid_y, ceil_z),
        mat_index=MAT_INDEX_WOOD, bevel_amount=0.005
    )
    for bi_u in (-0.32, 0.0, 0.32):
        bx = (ceil_x0 + ceil_x1) * 0.5 + bi_u * (ceil_x1 - ceil_x0)
        create_beveled_box(
            bm, size=(0.18, walk_w + 0.10, 0.16),
            location=(bx, mid_y, ceil_z - 0.08),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008
        )

    # 6. Clean, unified timber portal encasements (NO redundant nested frames)
    # Lintel beams rest SQUARELY ON TOP of pillars (zero overlap!)
    # Architrave casings sit flat against wall surfaces (never jutting deep into rooms)
    door_eff_w = 1.70
    jamb_w = 0.28
    lintel_w = door_eff_w + jamb_w * 2.0  # 2.26m wide (covers the 2.04m wall cut)
    lintel_h = 0.24
    casing_d = 0.035
    casing_w = 0.12
    post_bot = bld_floor_z + 0.015
    post_top = bld_floor_z + 0.015 + door_h
    jh = post_top - post_bot

    # --- A. BUILDING PORTAL (Chapel / Armory wall interface) ---
    # The casing spans the FULL thickness of the building wall (plus 3 cm of
    # overlap on each side), so it laps over the cut edge and no backface of
    # the wall can be seen around the frame.
    bld_wall_depth = bld_wall_t + 0.06
    into_conn = -tower_dir
    into_bld = tower_dir
    bld_wall_cx = bld_wall_x

    # Threshold plate flush with the floor, running from the outer face of the
    # building wall right through to the room's floor edge: no gap in the
    # floor where the connector meets the room.
    create_beveled_box(
        bm, size=(bld_wall_t + 0.16, lintel_w, 0.038),
        location=(bld_wall_x + into_bld * 0.04, mid_y, bld_floor_z + 0.015),
        mat_index=MAT_INDEX_FLOOR, bevel_amount=0.005
    )

    # Left & Right timber jamb pillars through the wall aperture
    for js in (-1.0, 1.0):
        jy = mid_y + js * (door_eff_w * 0.5 + jamb_w * 0.5)
        create_beveled_box(
            bm, size=(bld_wall_depth, jamb_w, jh),
            location=(bld_wall_cx, jy, (post_bot + post_top) * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    # Overhead lintel beam resting SQUARELY on top of the two pillars
    create_beveled_box(
        bm, size=(bld_wall_depth, lintel_w, lintel_h),
        location=(bld_wall_cx, mid_y, post_top + lintel_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )

    # Architrave casing trims: the room-facing casing sits flat against the
    # INSIDE face of the room wall (not buried inside it), the connector-facing
    # casing sits at the outer end of the jamb inside the connector corridor.
    for trim_x in (
        bld_inner_x + into_bld * (casing_d * 0.5),
        bld_wall_x + into_conn * (bld_wall_depth * 0.5 + casing_d * 0.5)
    ):
        for js in (-1.0, 1.0):
            jy = mid_y + js * (door_eff_w * 0.5 + jamb_w * 0.5)
            create_beveled_box(
                bm, size=(casing_d, jamb_w + 0.04, jh),
                location=(trim_x, jy, (post_bot + post_top) * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
            )
        create_beveled_box(
            bm, size=(casing_d, lintel_w + 0.08, lintel_h),
            location=(trim_x, mid_y, post_top + lintel_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )

    # --- B. TOWER PORTAL (Round tower wall interface) ---
    # The round tower's own wall cut is 1.55 m wide (door 1.45 + reveal). The
    # casing has to fill that cut EXACTLY, otherwise the tower's stone shows
    # through the frame on both sides (the "stone poking through the frame"
    # artefact). clear 1.15 + 2 x 0.20 jamb = 1.55 outer.
    tower_door_w = 1.15
    tower_jamb_w = 0.20
    tower_lintel_w = tower_door_w + tower_jamb_w * 2.0
    tw_depth = max(0.85, abs(x_tower_outer - x_tower_inner) + 0.10)
    tw_cx = (x_tower_inner + x_tower_outer) * 0.5

    # Threshold plate flush with floor through round tower wall
    create_beveled_box(
        bm, size=(tw_depth + 0.08, tower_lintel_w, 0.038),
        location=(tw_cx, mid_y, bld_floor_z + 0.015),
        mat_index=MAT_INDEX_FLOOR, bevel_amount=0.005
    )

    # Left & Right timber jamb pillars through the round tower wall
    for js in (-1.0, 1.0):
        jy = mid_y + js * (tower_door_w * 0.5 + tower_jamb_w * 0.5)
        create_beveled_box(
            bm, size=(tw_depth, tower_jamb_w, jh),
            location=(tw_cx, jy, (post_bot + post_top) * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
        )

    # Overhead lintel beam resting SQUARELY on top of the pillars through the tower wall
    create_beveled_box(
        bm, size=(tw_depth, tower_lintel_w, lintel_h),
        location=(tw_cx, mid_y, post_top + lintel_h * 0.5),
        mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
    )

    # Architrave casing trims on BOTH tower room face and vestibule corridor face (dual casing)
    for face_sgn in (-1.0, 1.0):
        casing_x = tw_cx - face_sgn * tower_dir * (tw_depth * 0.5 + casing_d * 0.5)
        for js in (-1.0, 1.0):
            jy = mid_y + js * (tower_door_w * 0.5 + tower_jamb_w * 0.5)
            create_beveled_box(
                bm, size=(casing_d, tower_jamb_w + 0.04, jh),
                location=(casing_x, jy, (post_bot + post_top) * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
            )
        create_beveled_box(
            bm, size=(casing_d, tower_lintel_w + 0.08, lintel_h),
            location=(casing_x, mid_y, post_top + lintel_h * 0.5),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.005
        )

    # 7. Exterior stone coping capping the connector walls
    create_beveled_box(
        bm, size=(w_len + 0.10, walk_w + wall_t * 2.0 + 0.15, 0.24),
        location=(w_cx, mid_y, max_z + 0.12),
        mat_index=trim_mat, bevel_amount=0.03
    )


def build_curtain_wall_gate_portal(
    bm,
    cx,
    cy,
    z_ground,
    outward=(0.0, -1.0),
    gate_w=4.40,
    gate_h=4.00,
    wall_h=4.8,
    thickness=1.2,
    raised_portcullis=True,
    tower_h=None,
    mat_stone=MAT_INDEX_STONE,
    mat_cut_stone=MAT_INDEX_CUT_STONE,
):
    """
    Constructs a monumental fortified stone gatehouse matching the main gate style:
    twin D-bastion flanking gate towers with arrow slits, machicolation corbels, and
    crenellated battlements, with an authentic raised spiked iron portcullis.
    """
    ox, oy = outward
    on = math.hypot(ox, oy)
    if on > 1e-5:
        ox, oy = ox / on, oy / on
    tx, ty = -oy, ox  # Wall tangent
    ang = math.atan2(ty, tx)

    gate_h = max(4.0, float(gate_h))
    half_gate = gate_w * 0.5
    tower_rad = 2.10
    arch_thick = thickness + 0.40
    lintel_cz = z_ground + gate_h + 0.35
    lintel_top = lintel_cz + 0.35
    # The portcullis grille hangs with its spikes just inside the opening so it
    # is always visible, and the housing above the lintel is tall enough to
    # swallow the rest of the grille.
    pc_h = gate_h - 0.20
    pc_raised = gate_h - 0.35
    pc_top = max(pc_raised + 0.85, pc_h + 1.20)
    gate_deck_z = max(z_ground + wall_h, lintel_top + 0.40, z_ground + pc_top + 0.30)
    tower_height = tower_h if tower_h is not None else max(wall_h + 2.8, (gate_deck_z - z_ground) + 1.8)

    # 1. TWIN FLANKING D-SHAPED BASTION GATE TOWERS (matching main gate style)
    from .gatehouse import build_flanking_gate_towers
    build_flanking_gate_towers(
        bm, cx, cy, z_ground=z_ground, gap_w=gate_w,
        wall_h=wall_h, wall_t=thickness, outward=(ox, oy),
        tower_r=tower_rad, tower_h=tower_height
    )

    # 2. ARCHED GATE LINTEL BAND & VOUSSOIRS SPANNING BETWEEN THE TOWERS.
    #    Same masonry as the curtain wall so the portcullis housing does not
    #    read as a different (cut stone) block glued onto the gate.
    create_beveled_box(
        bm, size=(gate_w + 0.90, arch_thick, 0.70),
        location=(cx, cy, lintel_cz),
        rotation=(0.0, 0.0, ang),
        mat_index=mat_stone, bevel_amount=0.03
    )

    # Solid curtain wall fill above the portcullis lintel up to the parapet deck.
    # Dressed in the same masonry as the wall so all three gates match.
    wall_fill_h = gate_deck_z - lintel_top
    if wall_fill_h > 0.05:
        create_beveled_box(
            bm, size=(gate_w + 0.90, arch_thick, wall_fill_h),
            location=(cx, cy, lintel_top + wall_fill_h * 0.5),
            rotation=(0.0, 0.0, ang),
            mat_index=mat_stone, bevel_amount=0.02
        )

    # 3. FORTIFIED STONE PARAPET & MERLONS ATOP THE CENTRAL GATE ARCH
    create_beveled_box(
        bm, size=(gate_w + 1.20, arch_thick + 0.20, 0.25),
        location=(cx, cy, gate_deck_z + 0.125),
        rotation=(0.0, 0.0, ang),
        mat_index=mat_cut_stone, bevel_amount=0.02
    )
    for f_sign in (-1.0, 1.0):
        m_x0 = cx - tx * (gate_w * 0.5 + 0.40) + ox * (f_sign * arch_thick * 0.5)
        m_y0 = cy - ty * (gate_w * 0.5 + 0.40) + oy * (f_sign * arch_thick * 0.5)
        m_x1 = cx + tx * (gate_w * 0.5 + 0.40) + ox * (f_sign * arch_thick * 0.5)
        m_y1 = cy + ty * (gate_w * 0.5 + 0.40) + oy * (f_sign * arch_thick * 0.5)
        build_battlement_run(
            bm, (m_x0, m_y0), (m_x1, m_y1),
            z_base=gate_deck_z + 0.25, height=0.95,
            thickness=0.34, style='STONE'
        )

    # 4. AUTHENTIC RAISED IRON PORTCULLIS WITH SPIKED TEETH (generous 3.8m+ headroom clearance)
    if raised_portcullis:
        build_portcullis(
            bm, cx, cy, z_ground=z_ground,
            width=gate_w - 0.20, height=pc_h,
            outward=(ox, oy), raised=pc_raised
        )


def build_connecting_wing(
    bm,
    cx,
    y_start=5.0,
    y_end=34.0,
    width=6.6,
    z_low=8.0,
    z_high=14.0,
    stair_y_start=16.5,
    stair_y_end=22.5,
    wall_mat=MAT_INDEX_STONE,
    upper_wall_mat=MAT_INDEX_PLASTER_EXT,
    trim_mat=MAT_INDEX_CUT_STONE,
    deck_mat=MAT_INDEX_FLOOR,
    timber_mat=MAT_INDEX_TIMBER,
    roof_mat=MAT_INDEX_SHINGLES,
    has_bridge_door=False,
    bridge_door_y=26.0,
    wall_y_north=None,
    roof_y_end_north=None,
    include_door_leaves: bool = False,
):
    """
    Constructs a stair-stepped connecting wing joining a lower hall (e.g. Great Hall / East Hall)
    at y_start to an upper hall (e.g. Keep / Archive Hall) at y_end across the terrace cliff rise.

    Features:
    - Lower level hall (z_low) and Upper level hall (z_high), both deck-flush with the
      connected buildings' ground floors so every portal opens with no step.
    - Interior stone staircase connecting z_low to z_high over [stair_y_start, stair_y_end].
    - Half-timbered and stone exterior walls with cut-through glazed windows.
    - Gabled shingle roofs stepped to match the elevation rise (flush abutments: roofs
      never penetrate the connected buildings).
    - Framed stone-and-timber portals at both ends (opening into adjacent halls), with
      solid threshold plates bridging the wall passage so the whole route is walkable.
    - Stone arcade piers carried down to bedrock wherever the wing spans the cliff drop.
    - Fitted gallery interior: runner carpets, benches, writing desk, bookshelves and
      standing candlesticks, all kept clear of the walking lanes, portals and doors.
    - Optional bridge doorway on eastern facade for the wooden bridge.

    wall_y_north: Y plane of the upper (north) building's wall. The wing carcass
      embeds past it (no gaps) but decks, roofs and portal frames stop at it.
    roof_y_end_north: where the upper roof terminates (defaults to y_end).
    """
    half_w = width * 0.5
    wall_t = 0.45
    floor_h = 3.7
    # North (upper) building wall plane: decks/roofs/portals stop here while the
    # carcass embeds past it so no gap can open between wing and building.
    wall_n = wall_y_north if wall_y_north is not None else y_end
    roof_n = roof_y_end_north if roof_y_end_north is not None else y_end
    deck_n = wall_n + 0.15
    # Walking lanes that must stay clear of furniture: the central gallery lane
    # plus (east wing) the lane from the stair head to the bridge door.
    lane_half = 1.25
    door_lane = (bridge_door_y - 1.35, bridge_door_y + 1.35) if has_bridge_door else None

    # 0. CARVE INTERIOR WALKWAY (Guarantees zero rock or terrain clipping inside corridor)
    # Full interior width clearance extending down past the foundation slab (z - 0.35)
    int_carve_w = width - wall_t * 2.0 + 0.10
    carve_pass_through_portal(
        bm,
        x_span=(cx - int_carve_w * 0.5, cx + int_carve_w * 0.5),
        y_span=(y_start - 0.10, stair_y_start + 0.20),
        z_span=(z_low - 0.35, z_low + 3.80)
    )
    carve_pass_through_portal(
        bm,
        x_span=(cx - int_carve_w * 0.5, cx + int_carve_w * 0.5),
        y_span=(stair_y_start - 0.20, stair_y_end + 0.20),
        z_span=(z_low - 0.35, z_high + 3.80)
    )
    carve_pass_through_portal(
        bm,
        x_span=(cx - int_carve_w * 0.5, cx + int_carve_w * 0.5),
        y_span=(stair_y_end - 0.20, wall_n + 0.15),
        z_span=(z_high - 0.35, z_high + 3.80)
    )

    # Purge any residual cliff / terrain faces protruding into the room corridor volume
    remnant_cliff = [
        f for f in bm.faces if f.is_valid and
        f.material_index in (MAT_INDEX_CLIFFS, MAT_INDEX_DIRT) and
        (cx - int_carve_w * 0.5 <= f.calc_center_median().x <= cx + int_carve_w * 0.5) and
        (y_start - 0.15 <= f.calc_center_median().y <= wall_n + 0.15) and
        (z_low - 0.35 <= f.calc_center_median().z <= z_high + 3.80)
    ]
    if remnant_cliff:
        import bmesh
        bmesh.ops.delete(bm, geom=remnant_cliff, context='FACES')

    # 1. FLOORS & FOUNDATION
    # Lower section floor deck (y_start to stair_y_start)
    len_low = stair_y_start - y_start
    mid_y_low = (y_start + stair_y_start) * 0.5
    # Subfloor slab tucked 5cm into walls on each side (width - wall_t * 2 + 0.10)
    int_deck_w = width - wall_t * 2.0 + 0.10
    create_beveled_box(
        bm, size=(int_deck_w, len_low, 0.40),
        location=(cx, mid_y_low, z_low - 0.22),
        mat_index=trim_mat, bevel_amount=0.02
    )
    create_beveled_box(
        bm, size=(width - wall_t * 2, len_low, 0.04),
        location=(cx, mid_y_low, z_low + 0.02),
        mat_index=deck_mat, bevel_amount=0.005
    )
    create_beveled_box(
        bm, size=(int_deck_w, len_low, 1.2),
        location=(cx, mid_y_low, z_low - 0.60),
        mat_index=wall_mat, bevel_amount=0.02
    )

    # Upper section floor deck (stair_y_end to the north building wall + 0.15 tuck)
    deck_n = wall_n + 0.15
    len_high = deck_n - stair_y_end
    mid_y_high = (stair_y_end + deck_n) * 0.5
    create_beveled_box(
        bm, size=(int_deck_w, len_high, 0.40),
        location=(cx, mid_y_high, z_high - 0.22),
        mat_index=trim_mat, bevel_amount=0.02
    )
    create_beveled_box(
        bm, size=(width - wall_t * 2, len_high, 0.04),
        location=(cx, mid_y_high, z_high + 0.02),
        mat_index=deck_mat, bevel_amount=0.005
    )
    create_beveled_box(
        bm, size=(int_deck_w, len_high, 1.2),
        location=(cx, mid_y_high, z_high - 0.60),
        mat_index=wall_mat, bevel_amount=0.02
    )

    # 2. INTERIOR STAIRCASE (Fully walkable climb between z_low and z_high).
    # Clean non-coplanar steps: solid sloped waist carriage slab underneath,
    # separate vertical stone riser blocks, and cut-stone treads resting on top.
    n_steps = 30
    stair_len = stair_y_end - stair_y_start
    stair_h = z_high - z_low
    step_run = stair_len / n_steps
    step_rise = stair_h / n_steps
    stair_w = width - wall_t * 2 - 0.06
    stair_pitch = math.atan2(stair_h, stair_len)
    stair_hyp = math.hypot(stair_len, stair_h)

    # Solid sloped waist carriage slab underneath the whole stair flight
    create_beveled_box(
        bm, size=(stair_w, stair_hyp + 0.10, 0.35),
        location=(cx, (stair_y_start + stair_y_end) * 0.5,
                  (z_low + z_high) * 0.5 - 0.20),
        rotation=(stair_pitch, 0.0, 0.0),
        mat_index=wall_mat, bevel_amount=0.02
    )

    tread_t = 0.05
    for i in range(n_steps):
        yc = stair_y_start + (i + 0.5) * step_run
        step_top = z_low + (i + 1) * step_rise
        riser_h = step_rise - tread_t + 0.02
        # Vertical stone riser block (top face at step_top - tread_t: zero coplanar overlap)
        create_beveled_box(
            bm, size=(stair_w, 0.12, riser_h),
            location=(cx, stair_y_start + i * step_run + 0.06,
                      step_top - tread_t - riser_h * 0.5),
            mat_index=wall_mat, bevel_amount=0.008
        )
        # Cut-stone tread slab resting cleanly on top of the riser
        create_beveled_box(
            bm, size=(stair_w + 0.04, step_run + 0.04, tread_t),
            location=(cx, yc + 0.015, step_top - tread_t * 0.5),
            mat_index=trim_mat, bevel_amount=0.008
        )
    # Solid side stringers closing the stair edges (no see-through slots)
    for s_side in (-1.0, 1.0):
        str_x = cx + s_side * (stair_w * 0.5 + 0.02)
        create_beveled_box(
            bm, size=(0.10, stair_len + 0.10, stair_h + 1.30),
            location=(str_x, (stair_y_start + stair_y_end) * 0.5,
                      (z_low + z_high) * 0.5 - 0.55),
            mat_index=timber_mat, bevel_amount=0.01
        )
    # Flanking handrails along the stair run
    mid_stair_y = (stair_y_start + stair_y_end) * 0.5
    mid_stair_z = (z_low + z_high) * 0.5 + 0.90
    for s_side in (-1.0, 1.0):
        rail_x = cx + s_side * (stair_w * 0.5 - 0.08)
        create_beveled_box(
            bm, size=(0.10, stair_hyp + 0.10, 0.14),
            location=(rail_x, mid_stair_y, mid_stair_z),
            rotation=(stair_pitch, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 3. SIDE WALLS (West and East facades) with authentic Tudor half-timber framing
    from ..openings import build_window_assembly, build_door_assembly

    len_upper = deck_n - stair_y_start
    mid_y_upper = (stair_y_start + deck_n) * 0.5
    found_drop = 1.0
    h_upper_stone = (z_high + floor_h) - (z_low - found_drop)
    mid_z_upper_stone = (z_low - found_drop) + h_upper_stone * 0.5

    for s_side in (-1.0, 1.0):
        wx = cx + s_side * (half_w - wall_t * 0.5)

        # A. Lower section walls: Ground floor stone + Upper floor stucco
        h_low_stone = floor_h + found_drop
        mid_z_low_stone = (z_low - found_drop) + h_low_stone * 0.5
        create_beveled_box(
            bm, size=(wall_t, len_low, h_low_stone),
            location=(wx, mid_y_low, mid_z_low_stone),
            mat_index=wall_mat, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(wall_t - 0.04, len_low, floor_h),
            location=(wx, mid_y_low, z_low + floor_h * 1.5),
            mat_index=upper_wall_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(wall_t + 0.08, len_low, 0.22),
            location=(wx, mid_y_low, z_low + floor_h),
            mat_index=timber_mat, bevel_amount=0.015
        )

        # Lower section windows: real carved openings with framed assemblies
        for wy in (y_start + 3.2, y_start + 7.8):
            wcz = z_low + 1.8
            carve_pass_through_portal(
                bm,
                x_span=(wx - wall_t * 0.8, wx + wall_t * 0.8),
                y_span=(wy - 0.65, wy + 0.65),
                z_span=(wcz - 0.90, wcz + 0.90)
            )
            build_window_assembly(
                bm,
                center=(wx, wy, wcz),
                size=(1.10, 1.60),
                wall_thickness=wall_t,
                normal_axis=s_side * math.pi * 0.5,
                has_shutters=True,
                shutters_closed=False
            )

        # B & C. Upper section walls (from stair_y_start to deck_n):
        # Continuous stone base/ground story below z_high + floor_h,
        # and stucco upper story up to z_high + floor_h * 2.0 (flush with roof eave, NO penetration)
        create_beveled_box(
            bm, size=(wall_t, len_upper, h_upper_stone),
            location=(wx, mid_y_upper, mid_z_upper_stone),
            mat_index=wall_mat, bevel_amount=0.02
        )
        create_beveled_box(
            bm, size=(wall_t - 0.04, len_upper, floor_h),
            location=(wx, mid_y_upper, z_high + floor_h * 1.5),
            mat_index=upper_wall_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(wall_t + 0.08, len_upper, 0.22),
            location=(wx, mid_y_upper, z_high + floor_h),
            mat_index=timber_mat, bevel_amount=0.015
        )

        # Tudor half-timber framing over the stucco upper walls
        def _add_timber_framing(y0, y1, z_bot, z_top):
            span_y = y1 - y0
            if span_y < 0.5:
                return
            t_beam_w = 0.18
            t_beam_d = 0.10
            ext_x = wx + s_side * (wall_t * 0.5 + t_beam_d * 0.20)
            # Top plate beam (under eave)
            create_beveled_box(
                bm, size=(t_beam_d, span_y, t_beam_w),
                location=(ext_x, (y0 + y1) * 0.5, z_top - t_beam_w * 0.5 - 0.02),
                mat_index=timber_mat, bevel_amount=0.012
            )
            # Corner / end posts
            for py in (y0 + 0.10, y1 - 0.10):
                create_beveled_box(
                    bm, size=(t_beam_d, t_beam_w, z_top - z_bot),
                    location=(ext_x, py, (z_bot + z_top) * 0.5),
                    mat_index=timber_mat, bevel_amount=0.012
                )
            # Intermediate vertical studs spaced ~2.2m
            n_bays = max(1, int(round(span_y / 2.2)))
            bay_len = span_y / n_bays
            for bi in range(1, n_bays):
                sy = y0 + bi * bay_len
                create_beveled_box(
                    bm, size=(t_beam_d, t_beam_w, z_top - z_bot),
                    location=(ext_x, sy, (z_bot + z_top) * 0.5),
                    mat_index=timber_mat, bevel_amount=0.012
                )
            # Diagonal knee braces in each bay
            stud_h = z_top - z_bot - t_beam_w * 2.0
            mid_z = (z_bot + z_top) * 0.5
            for bi in range(n_bays):
                by0 = y0 + bi * bay_len
                by1 = by0 + bay_len
                brace_l = math.hypot(bay_len - 0.22, stud_h * 0.70)
                brace_ang = math.atan2(stud_h * 0.70, bay_len - 0.22)
                sign_d = 1.0 if bi % 2 == 0 else -1.0
                create_beveled_box(
                    bm, size=(t_beam_d * 0.80, brace_l, t_beam_w * 0.75),
                    location=(ext_x, (by0 + by1) * 0.5, mid_z),
                    rotation=(sign_d * brace_ang, 0.0, 0.0),
                    mat_index=timber_mat, bevel_amount=0.01
                )

        # Apply timber framing to both upper stucco sections
        _add_timber_framing(y_start, stair_y_start, z_low + floor_h, z_low + floor_h * 2.0)
        _add_timber_framing(stair_y_start, deck_n, z_high + floor_h, z_high + floor_h * 2.0)

        # Upper section windows: carved openings with framed assemblies
        for wy in (stair_y_end + 3.0, stair_y_end + 7.5):
            if wy > wall_n - 2.0:
                continue
            if has_bridge_door and s_side > 0 and abs(wy - bridge_door_y) < 2.0:
                continue
            wcz = z_high + 1.8
            carve_pass_through_portal(
                bm,
                x_span=(wx - wall_t * 0.8, wx + wall_t * 0.8),
                y_span=(wy - 0.65, wy + 0.65),
                z_span=(wcz - 0.90, wcz + 0.90)
            )
            build_window_assembly(
                bm,
                center=(wx, wy, wcz),
                size=(1.10, 1.60),
                wall_thickness=wall_t,
                normal_axis=s_side * math.pi * 0.5,
                has_shutters=True,
                shutters_closed=False
            )

        # Bridge door on east facade (reusing authentic arched build_door_assembly)
        if has_bridge_door and s_side > 0:
            door_w = 1.30
            door_h = 2.40
            carve_pass_through_portal(
                bm,
                x_span=(wx - wall_t * 0.9, wx + wall_t * 0.9),
                y_span=(bridge_door_y - door_w * 0.65, bridge_door_y + door_w * 0.65),
                z_span=(z_high - 0.15, z_high + door_h + 0.25)
            )
            build_door_assembly(
                bm,
                center_x=wx,
                y_front=bridge_door_y,
                z_base=z_high,
                wall_thickness=wall_t,
                door_w=door_w,
                door_h=door_h,
                door_angle_deg=80.0,
                door_shape='ARCHED',
                ground_floor_stone=True,
                normal_axis='+X',
                include_leaf=include_door_leaves
            )

    # Interior lining partitions covering the bare stone inside the passage:
    # plaster panels with timber studwork, split around windows and doors.
    def _line_section(s_side, y0, y1, z_deck, exclusions=()):
        spans = [(y0, y1)]
        for ex0, ex1 in exclusions:
            nxt = []
            for s0, s1 in spans:
                if ex1 <= s0 or ex0 >= s1:
                    nxt.append((s0, s1))
                    continue
                if ex0 - s0 >= 0.30:
                    nxt.append((s0, ex0))
                if s1 - ex1 >= 0.30:
                    nxt.append((ex1, s1))
            spans = nxt
        lx = cx + s_side * (half_w - wall_t - 0.04)
        for s0, s1 in spans:
            create_beveled_box(
                bm, size=(0.08, s1 - s0, 2.60),
                location=(lx, (s0 + s1) * 0.5, z_deck + 1.30),
                mat_index=MAT_INDEX_PLASTER_EXT, bevel_amount=0.008
            )
            for ex in (s0 + 0.10, s1 - 0.10):
                create_beveled_box(
                    bm, size=(0.12, 0.16, 2.60),
                    location=(lx, ex, z_deck + 1.30),
                    mat_index=timber_mat, bevel_amount=0.012
                )
        create_beveled_box(
            bm, size=(0.12, y1 - y0, 0.16),
            location=(lx, (y0 + y1) * 0.5, z_deck + 2.62),
            mat_index=timber_mat, bevel_amount=0.012
        )

    for s_side in (-1.0, 1.0):
        _line_section(s_side, y_start + 0.3, stair_y_start - 0.3, z_low,
                      [(y_start + 3.2 - 0.85, y_start + 3.2 + 0.85),
                       (y_start + 7.8 - 0.85, y_start + 7.8 + 0.85)])
        _up_ex = [(stair_y_end + 3.0 - 0.85, stair_y_end + 3.0 + 0.85),
                  (stair_y_end + 7.5 - 0.85, stair_y_end + 7.5 + 0.85)]
        if has_bridge_door and s_side > 0:
            _up_ex.append((bridge_door_y - 1.30, bridge_door_y + 1.30))
        _line_section(s_side, stair_y_end + 0.3, deck_n - 0.3, z_high, _up_ex)
    # 3.5 INTERIOR FINISHED TIMBER CEILING & EXPOSED CROSS-BEAMS
    # Fully seals the walkable corridor so no roof trusses, shingles, or exterior
    # geometry are visible from inside the connector wing.
    ceil_h = 3.35
    ceil_thick = 0.08
    beam_w = 0.18
    beam_h = 0.22
    int_w = width - wall_t * 2.0 - 0.04

    # A. Lower section ceiling
    create_beveled_box(
        bm, size=(int_w, len_low, ceil_thick),
        location=(cx, mid_y_low, z_low + ceil_h),
        mat_index=deck_mat, bevel_amount=0.01
    )
    n_beams_low = max(2, int(len_low / 1.8))
    for bi in range(1, n_beams_low):
        by = y_start + bi * (len_low / n_beams_low)
        create_beveled_box(
            bm, size=(int_w + 0.06, beam_w, beam_h),
            location=(cx, by, z_low + ceil_h - beam_h * 0.5),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # B. Stair section sloped ceiling
    stair_pitch = math.atan2(stair_h, stair_len)
    stair_hyp = math.hypot(stair_len, stair_h)
    create_beveled_box(
        bm, size=(int_w, stair_hyp, ceil_thick),
        location=(cx, mid_stair_y, mid_stair_z - 0.90 + ceil_h),
        rotation=(stair_pitch, 0.0, 0.0),
        mat_index=deck_mat, bevel_amount=0.01
    )
    n_beams_stair = max(2, int(stair_len / 1.8))
    for bi in range(1, n_beams_stair):
        by = stair_y_start + bi * (stair_len / n_beams_stair)
        bz = z_low + (by - stair_y_start) / stair_len * stair_h + ceil_h - beam_h * 0.5
        create_beveled_box(
            bm, size=(int_w + 0.06, beam_w, beam_h),
            location=(cx, by, bz),
            rotation=(stair_pitch, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # C. Upper section ceiling
    create_beveled_box(
        bm, size=(int_w, len_high, ceil_thick),
        location=(cx, mid_y_high, z_high + ceil_h),
        mat_index=deck_mat, bevel_amount=0.01
    )
    n_beams_high = max(2, int(len_high / 1.8))
    for bi in range(1, n_beams_high):
        by = stair_y_end + bi * (len_high / n_beams_high)
        create_beveled_box(
            bm, size=(int_w + 0.06, beam_w, beam_h),
            location=(cx, by, z_high + ceil_h - beam_h * 0.5),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 4. STEPPED GABLE SHINGLE ROOFS (proper roof builder, flush abutments).
    # Both roofs terminate strictly at stair_y_start with flush abutments,
    # preventing either roof from protruding into the interior or the other roof.
    from ..roof.gable_roof import build_gable_roof
    # Lower section gable roof (abuts South building facade and step wall flush)
    build_gable_roof(
        bm,
        x_min=cx - half_w,
        x_max=cx + half_w,
        y_min=y_start,
        y_max=stair_y_start,
        z_base=z_low + floor_h * 2.0,
        roof_height=2.6,
        overhang=0.45,
        abut_front=True,  # Flushed to south building wall at y_start
        abut_back=True,   # Flushed to step-closing wall at stair_y_start
        gable_ends=(),
        gable_walls=False,
    )

    # Upper section gable roof (runs over the stair zone with exposed south gable and abuts North facade flush)
    build_gable_roof(
        bm,
        x_min=cx - half_w,
        x_max=cx + half_w,
        y_min=stair_y_start,
        y_max=roof_n,
        z_base=z_high + floor_h * 2.0,
        roof_height=2.6,
        overhang=0.45,
        wall_thickness=wall_t,
        abut_front=False,  # Exposed gable end facing south with overhang and bargeboards
        abut_back=True,    # Flushed to north building wall, never inside it
        gable_ends=('FRONT',),
        gable_walls=True,
        tier='TIER_3',
    )

    # Step-closing transverse wall at stair_y_start between the lower roof and upper roof:
    # Completely seals from below the lower roof eave up to the upper roof eave.
    # Tucked strictly between the side walls (trans_w) and starting at stair_y_start
    # so it never creates coplanar faces or penetrates through the exterior side facades.
    _step_lo = z_low + floor_h * 2.0 - 0.20
    _step_hi = z_high + floor_h * 2.0
    _div_z = z_high + floor_h
    step_thick = 0.35
    step_y = stair_y_start + step_thick * 0.5  # front face flush at stair_y_start
    trans_w = width - wall_t * 2.0 + 0.10  # tucked 5cm into side walls, 40cm inside exterior face

    # Lower stone portion
    if _div_z > _step_lo:
        create_beveled_box(
            bm, size=(trans_w, step_thick, _div_z - _step_lo),
            location=(cx, step_y, (_step_lo + _div_z) * 0.5),
            mat_index=wall_mat, bevel_amount=0.02
        )
    # Upper stucco portion matching the upper story
    if _step_hi > _div_z:
        create_beveled_box(
            bm, size=(trans_w - 0.04, step_thick - 0.02, _step_hi - _div_z),
            location=(cx, step_y, (_div_z + _step_hi) * 0.5),
            mat_index=upper_wall_mat, bevel_amount=0.015
        )
        # Timber beam at the story transition (flush on south face)
        t_beam_d = 0.12
        create_beveled_box(
            bm, size=(trans_w + 0.04, t_beam_d, 0.22),
            location=(cx, stair_y_start - t_beam_d * 0.5 + 0.01, _div_z),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Vertical timber studs on this south-facing upper wall (spaced evenly within interior span)
        for fx in (cx - 1.40, cx, cx + 1.40):
            create_beveled_box(
                bm, size=(0.18, t_beam_d, _step_hi - _div_z),
                location=(fx, stair_y_start - t_beam_d * 0.5 + 0.01, (_div_z + _step_hi) * 0.5),
                mat_index=timber_mat, bevel_amount=0.012
            )

    # 5. CONNECTION PORTALS AT BOTH BUILDING ENDS (straddling the wall planes,
    # with timber encasement and wood plank threshold so only wood is visible)
    portal_w = 2.25
    portal_h = 2.85

    def _wing_portal(y_wall, z_deck, into_building):
        # Carve strictly the doorway opening through the wall (not wide trenches).
        # Starting z_span at z_deck + 0.08 guarantees it NEVER cuts the floor slab (+0.05).
        # Keeping y_span strictly within the wall aperture (+/- 0.30m) prevents slicing into rooms.
        y_span = (y_wall - 0.32, y_wall + 0.32)
        if into_building > 0:
            yf0, yf1 = y_wall - 0.30, y_wall + 3.80
        else:
            yf0, yf1 = y_wall - 3.80, y_wall + 0.30
        # Purge any furniture within 3.5m walking clearance inside the connected room cleanly
        xf0, xf1 = cx - 3.2, cx + 3.2
        zf0, zf1 = z_deck - 0.08, z_deck + 3.30
        purge_props_in_volume(bm, (xf0, xf1), (yf0, yf1), (zf0, zf1))

        carve_pass_through_portal(
            bm,
            x_span=(cx - portal_w * 0.50 - 0.02, cx + portal_w * 0.50 + 0.02),
            y_span=y_span,
            z_span=(z_deck + 0.08, z_deck + portal_h + 0.25)
        )
        # Purge any residual foundation stone faces strictly below floor level inside the wall slot
        thresh_stone = [
            f for f in bm.faces if f.is_valid and
            f.material_index in (MAT_INDEX_STONE, MAT_INDEX_CUT_STONE) and
            (cx - portal_w * 0.5 - 0.05 <= f.calc_center_median().x <= cx + portal_w * 0.5 + 0.05) and
            (abs(f.calc_center_median().y - y_wall) <= 0.25) and
            (z_deck - 0.20 <= f.calc_center_median().z <= z_deck + 0.01)
        ]
        if thresh_stone:
            import bmesh
            bmesh.ops.delete(bm, geom=thresh_stone, context='FACES')

        # Solid beveled oak threshold plate bridging the floor opening into the wing corridor
        jamb_w = 0.24
        jamb_t = 0.58
        th_w = portal_w + jamb_w * 2.0 + 0.12
        th_d = 0.70
        th_h = 0.038
        wing_dir = -into_building
        # Room interior wall surface plane (0.19m offset from wall centerline y_wall)
        wall_face_room = y_wall + into_building * 0.19
        jamb_cy = wall_face_room + wing_dir * (jamb_t * 0.5)
        th_cy = wall_face_room + wing_dir * (th_d * 0.5 - 0.04)

        create_beveled_box(
            bm, size=(th_w, th_d, th_h),
            location=(cx, th_cy, z_deck + 0.05 + th_h * 0.5),
            mat_index=deck_mat, bevel_amount=0.008
        )
        # Solid timber jambs covering the cut wall edges into the connector wing
        for js in (-1.0, 1.0):
            create_beveled_box(
                bm, size=(jamb_w, jamb_t, portal_h),
                location=(cx + js * (portal_w * 0.5 + jamb_w * 0.5), jamb_cy, z_deck + 0.05 + portal_h * 0.5),
                mat_index=timber_mat, bevel_amount=0.015
            )
        # Solid timber lintel beam spanning across top
        lintel_w = portal_w + jamb_w * 2.0 + 0.20
        lintel_h = 0.34
        create_beveled_box(
            bm, size=(lintel_w, jamb_t, lintel_h),
            location=(cx, jamb_cy, z_deck + 0.05 + portal_h + lintel_h * 0.5),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Timber architrave trim casings: room-facing casing sits flat against room wall;
        # wing-facing casing sits at inner end of the jamb inside connector corridor
        casing_d = 0.04
        trim_w = 0.26
        for trim_y in (
            wall_face_room + into_building * (casing_d * 0.5),
            wall_face_room + wing_dir * (jamb_t + casing_d * 0.5)
        ):
            for js in (-1.0, 1.0):
                create_beveled_box(
                    bm, size=(trim_w, casing_d, portal_h + 0.12),
                    location=(cx + js * (portal_w * 0.5 + trim_w * 0.5), trim_y, z_deck + 0.05 + (portal_h + 0.12) * 0.5),
                    mat_index=timber_mat, bevel_amount=0.005
                )
            create_beveled_box(
                bm, size=(lintel_w + 0.24, casing_d + 0.01, lintel_h + 0.04),
                location=(cx, trim_y, z_deck + 0.05 + portal_h + (lintel_h + 0.04) * 0.5),
                mat_index=timber_mat, bevel_amount=0.005
            )

    # South portal into Great Hall / East Hall (wall plane at y_start)
    _wing_portal(y_start, z_low, -1)
    # North portal into Keep / Archive Hall (wall plane at wall_n)
    _wing_portal(wall_n, z_high, +1)

    # 6. FITTED GALLERY INTERIOR (corridor + reading room, all furniture clear
    # of the central walking lane, both portals and the bridge-door lane)
    from .furniture import build_bench
    from .interior_furniture import (
        build_bookshelf_neat, build_chair, build_desk, build_rug,
    )
    x_west = cx - half_w + 0.85
    x_east = cx + half_w - 0.85

    def _clear_of_lanes(fx, fy, fr=0.55):
        if abs(fx - cx) < lane_half + fr and y_start < fy < deck_n:
            return False
        if door_lane is not None and fx > cx and door_lane[0] - fr < fy < door_lane[1] + fr:
            return False
        return True

    # Lower gallery: runner carpet down the walking lane (flat, walkable)
    run_len = max(2.0, stair_y_start - y_start - 3.0)
    build_rug(bm, cx, y_start + 1.5 + run_len * 0.5, z_ground=z_low + 0.04,
              ang=0.0, width=1.9, length=run_len, rug_style=2, z_floor=z_low + 0.04)
    # Bookshelf against the west wall halfway up the lower gallery
    shelf_y = (y_start + stair_y_start) * 0.5 + 2.2
    has_shelf = shelf_y < stair_y_start - 1.4 and _clear_of_lanes(x_west, shelf_y, 0.75)
    if has_shelf:
        build_bookshelf_neat(bm, x_west, shelf_y, z_ground=z_low + 0.04, ang=math.pi * 0.5, width=1.6)
    # Benches along the west wall of the lower gallery (strictly avoiding the bookcase space)
    for by in (y_start + 3.5, y_start + 6.5):
        if by < stair_y_start - 1.2 and _clear_of_lanes(x_west, by, 0.45):
            if has_shelf and abs(by - shelf_y) < 1.8:
                continue
            build_bench(bm, x_west, by, z_ground=z_low + 0.04, ang=math.pi * 0.5, length=1.75)

    # Upper reading room: rug, writing desk + chair, bookshelf (west side so the
    # bridge-door lane on the east stays completely clear)
    up_c = (stair_y_end + deck_n) * 0.5
    if deck_n - stair_y_end > 4.5:
        build_rug(bm, cx, up_c, z_ground=z_high + 0.04,
                  ang=0.0, width=2.0, length=min(4.5, deck_n - stair_y_end - 2.5),
                  rug_style=1, z_floor=z_high + 0.04)
        if _clear_of_lanes(x_west, up_c - 0.6, 0.85):
            build_desk(bm, x_west, up_c - 0.6, z_ground=z_high + 0.04, ang=math.pi * 0.5, width=1.4)
            if _clear_of_lanes(x_west + 0.85, up_c - 0.6, 0.4):
                build_chair(bm, x_west + 0.85, up_c - 0.6, z_ground=z_high + 0.04, ang=-math.pi * 0.5)
        if _clear_of_lanes(x_west, up_c + 1.6, 0.75):
            build_bookshelf_neat(bm, x_west, up_c + 1.6, z_ground=z_high + 0.04, ang=math.pi * 0.5, width=1.6)
        if _clear_of_lanes(x_east if not has_bridge_door else cx, up_c + 0.4, 0.45) and not has_bridge_door:
            build_bench(bm, x_east, up_c + 0.4, z_ground=z_high + 0.04, ang=-math.pi * 0.5, length=1.5)

    # (North portal is handled by _wing_portal above, at the wall_n plane.)
    clean_orphan_floating_props(bm)


def build_wooden_bridge(
    bm,
    p_start=(19.8, 26.0),
    p_end=(43.6, 26.0),
    floor_z=14.86,
    width=2.6,
    deck_mat=MAT_INDEX_WOOD,
    timber_mat=MAT_INDEX_TIMBER,
    trim_mat=MAT_INDEX_CUT_STONE,
    roof_mat=MAT_INDEX_SHINGLES,
):
    """
    Constructs an open-timbered trestle bridge spanning between the East Wing
    and the East Bluff Tower across the cliff chasm.

    Features:
    - Vertical braced timber trestle bents anchored in bedrock.
    - Heavy timber longitudinal stringers supporting an oak plank deck.
    - Varied timber balustrades (X-brace bays alternate with baluster bays),
      lantern king posts and hanging lanterns.
    - Timber entry arch portals at both ends.
    - Fully walkable from East Wing to East Bluff Tower.
    """
    from .nasher_site import ground_z
    x0, y0 = p_start
    x1, y1 = p_end
    span_len = math.hypot(x1 - x0, y1 - y0)
    if span_len < 1.0:
        return

    dx = (x1 - x0) / span_len
    dy = (y1 - y0) / span_len
    yaw = math.atan2(dy, dx)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    half_w = width * 0.5

    # 1. TIMBER TRESTLE BENTS (Vertical timber piers rising from cliff rock)
    bent_xs = (x0 + span_len * 0.33, x0 + span_len * 0.67)
    for bx in bent_xs:
        by = y0 + dy * (bx - x0)
        rock_z = ground_z(bx, by)
        bent_h = max(1.5, floor_z - rock_z - 0.25)
        pier_cz = rock_z + bent_h * 0.5
        # Cut-stone pad footings
        for ps in (-1.0, 1.0):
            py = by + ps * (half_w - 0.35)
            create_beveled_box(
                bm, size=(0.65, 0.65, 0.40),
                location=(bx, py, rock_z + 0.20),
                mat_index=trim_mat, bevel_amount=0.03
            )
            create_beveled_box(
                bm, size=(0.28, 0.28, bent_h),
                location=(bx, py, pier_cz),
                mat_index=timber_mat, bevel_amount=0.015
            )
        # Horizontal cross ledger timber
        create_beveled_box(
            bm, size=(0.24, width - 0.20, 0.28),
            location=(bx, by, floor_z - 0.20),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Diagonal X-brace timbers
        create_beveled_box(
            bm, size=(0.14, width - 0.40, 0.16),
            location=(bx, by, pier_cz),
            rotation=(0.35, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(0.14, width - 0.40, 0.16),
            location=(bx, by, pier_cz),
            rotation=(-0.35, 0.0, 0.0),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 2. LONGITUDINAL TIMBER STRINGERS UNDER DECK
    for s_side in (-1.0, 0.0, 1.0):
        sy = cy + s_side * (half_w - 0.25)
        create_beveled_box(
            bm, size=(span_len + 0.30, 0.26, 0.36),
            location=(cx, sy, floor_z - 0.18),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.015
        )

    # 3. WOODEN WALKWAY DECK & CURBS
    create_beveled_box(
        bm, size=(span_len, width - 0.10, 0.08),
        location=(cx, cy, floor_z + 0.04),
        rotation=(0.0, 0.0, yaw),
        mat_index=deck_mat, bevel_amount=0.005
    )
    for s_side in (-1.0, 1.0):
        cy_curb = cy + s_side * (half_w - 0.10)
        create_beveled_box(
            bm, size=(span_len + 0.20, 0.18, 0.18),
            location=(cx, cy_curb, floor_z + 0.13),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.01
        )

    # 4. TIMBER BALUSTRADES & HANDRAILS (varied bays: X-brace alternates with
    # vertical balusters; every third post rises as a lantern king post)
    n_posts = max(4, int(span_len / 2.2))
    post_step = span_len / n_posts
    for side in (-1.0, 1.0):
        py = cy + side * (half_w - 0.10)
        create_beveled_box(
            bm, size=(span_len + 0.10, 0.15, 0.12),
            location=(cx, py, floor_z + 1.10),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.01
        )
        create_beveled_box(
            bm, size=(span_len + 0.10, 0.10, 0.08),
            location=(cx, py, floor_z + 0.55),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.008
        )
        for pi in range(n_posts + 1):
            px = x0 + pi * post_step
            is_king = (pi % 3 == 0)
            post_h = 2.30 if is_king else 1.15
            create_beveled_box(
                bm, size=(0.16, 0.16, post_h),
                location=(px, py, floor_z + post_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=timber_mat, bevel_amount=0.01
            )
            if pi < n_posts:
                mid_px = px + post_step * 0.5
                if pi % 2 == 0:
                    create_beveled_box(
                        bm, size=(post_step * 0.95, 0.06, 0.08),
                        location=(mid_px, py, floor_z + 0.82),
                        rotation=(0.0, 0.28, yaw),
                        mat_index=timber_mat, bevel_amount=0.005
                    )
                    create_beveled_box(
                        bm, size=(post_step * 0.95, 0.06, 0.08),
                        location=(mid_px, py, floor_z + 0.82),
                        rotation=(0.0, -0.28, yaw),
                        mat_index=timber_mat, bevel_amount=0.005
                    )
                else:
                    for bi in range(3):
                        bx = px + post_step * (0.25 + 0.25 * bi)
                        create_beveled_box(
                            bm, size=(0.07, 0.07, 0.95),
                            location=(bx, py, floor_z + 0.62),
                            rotation=(0.0, 0.0, yaw),
                            mat_index=timber_mat, bevel_amount=0.005
                        )

    # 5. TIMBER PORTAL ARCHES AT BRIDGE HEADS & TERMINAL NEWEL POSTS
    for end_sign, ex in ((-1.0, x0), (1.0, x1)):
        ey = y0 + dy * (ex - x0)
        # Framed portal archway integrating into tower / building entrance
        arch_post_h = 2.70
        for side in (-1.0, 1.0):
            gy = ey + side * (half_w - 0.10)
            create_beveled_box(
                bm, size=(0.22, 0.22, arch_post_h),
                location=(ex, gy, floor_z + arch_post_h * 0.5),
                rotation=(0.0, 0.0, yaw),
                mat_index=timber_mat, bevel_amount=0.015
            )
        # Overhead timber lintel beam
        create_beveled_box(
            bm, size=(0.24, width, 0.26),
            location=(ex, ey, floor_z + arch_post_h - 0.13),
            rotation=(0.0, 0.0, yaw),
            mat_index=timber_mat, bevel_amount=0.015
        )
        # Corner knee braces
        brace_len = 0.55
        for side in (-1.0, 1.0):
            by = ey + side * (half_w - 0.35)
            bz = floor_z + arch_post_h - 0.35
            create_beveled_box(
                bm, size=(0.12, brace_len, 0.12),
                location=(ex, by, bz),
                rotation=(side * 0.785, 0.0, yaw),
                mat_index=timber_mat, bevel_amount=0.01
            )
        # Solid oak transition threshold board
        create_beveled_box(
            bm, size=(0.55, width - 0.20, 0.038),
            location=(ex + dx * end_sign * 0.15, ey, floor_z + 0.05),
            rotation=(0.0, 0.0, yaw),
            mat_index=deck_mat, bevel_amount=0.005
        )

        # Terminal newel posts just inside the bridge deck
        for side in (-1.0, 1.0):
            gx = ex - dx * end_sign * 0.40
            gy = ey + side * (half_w - 0.10)
            create_beveled_box(
                bm, size=(0.18, 0.18, 1.25),
                location=(gx, gy, floor_z + 0.62),
                rotation=(0.0, 0.0, yaw),
                mat_index=timber_mat, bevel_amount=0.015
            )

    # Lanterns on alternating king posts (reusing authentic lighting.py build_hanging_lantern)
    from .lighting import build_hanging_lantern
    for side in (-1.0, 1.0):
        py = cy + side * (half_w - 0.10)
        for pi in range(1, n_posts):
            # Only place lanterns where tall king posts (post_h = 2.30m) exist (pi % 3 == 0)
            if pi % 3 != 0:
                continue
            # Alternate sides between successive king posts
            side_for_pi = -1.0 if (pi // 3) % 2 == 0 else 1.0
            if side != side_for_pi:
                continue
            px = x0 + pi * post_step
            # Arm points inward across the bridge towards the walkway
            arm_yaw = yaw + (math.pi * 0.5 if side < 0 else -math.pi * 0.5)
            build_hanging_lantern(
                bm,
                x=px,
                y=py,
                z_top=floor_z + 2.05,
                arm_ang=arm_yaw,
                arm_len=0.32,
                scale=0.90
            )

    # (No roof canopy: open sky above the walkway by design.)


def chain_buildings(bm, building_nodes, links_spec):
    """
    High-level generator that chains a collection of buildings together using
    skybridges, gallerias, and vestibules according to a topology specification.
    """
    for link in links_spec:
        b1 = building_nodes.get(link['from'])
        b2 = building_nodes.get(link['to'])
        if not b1 or not b2:
            continue
        p1 = (b1['pos'][0], b1['pos'][1])
        p2 = (b2['pos'][0], b2['pos'][1])
        fz = link.get('floor_z', min(b1['pos'][2], b2['pos'][2]) + 7.4)
        build_skybridge_link(
            bm, p1, p2,
            width=link.get('width', 9.0),
            floor_z=fz,
            ceiling_h=link.get('ceiling_h', 3.6),
            roof_style=link.get('roof_style', 'BATTLEMENTS'),
            has_windows=link.get('has_windows', True),
            num_windows=link.get('num_windows', 2),
            has_underpass_arch=link.get('has_underpass_arch', True),
            underpass_spring_z=link.get('underpass_spring_z', fz - 6.0)
        )


def build_chapel_connector(
    bm,
    p_chapel=(-14.4, 43.8),
    p_keep=(-12.0, 43.8),
    width=2.90,
    floor_z=14.86,
    chapel_floor_z=14.45,
    ceiling_h=3.30,
    tier=2
):
    """
    Clean, simple enclosed ground-level corridor connecting Keep and Chapel.
    Features:
    - Positioned at y=43.8 (+3.8m in Keep local space) well clear of Keep interior stairs.
    - 100% all-wood construction (wooden floors, vertical plank walls, timber beams,
      timber jambs/head beams, wood threshold plates, and solid end walls above
      the doorframes so zero stone or missing wall is visible).
    - Door casings straddle each host wall (half in the room, half in the
      corridor) and cover the cut-out left in the wall, so no raw masonry edge
      or daylight gap is ever visible around a frame.
    - Clean prop removal that clears out conflicting furniture without slicing or booleaning.
    - Solid gable end wall and header panels sealing the space above the head
      beams up to the roof.
    """
    x_chapel = float(p_chapel[0])
    x_keep = float(p_keep[0])
    cy = float((p_chapel[1] + p_keep[1]) * 0.5)
    cx = (x_chapel + x_keep) * 0.5
    dx = abs(x_keep - x_chapel)

    portal_w = 2.20
    portal_h = 2.85
    # The host walls cut an opening of (door size + reveal margin); the casing
    # is sized to cover that cut exactly.
    portal_margin = 0.02
    cut_w = portal_w + portal_margin * 2.0
    cut_h = portal_h + portal_margin
    jamb_w = 0.16
    casing_d = 0.030
    keep_wall_t = 0.38      # Keep exterior wall thickness
    chapel_wall_t = 0.36   # Chapel / Armory exterior wall thickness

    # 1. Cleanly remove any conflicting props in the immediate doorway walking threshold
    # in both Keep and Chapel WITHOUT touching structural walls, ceilings, lanterns, or partition walls.
    purge_props_in_volume(
        bm,
        x_span=(x_keep - 0.10, x_keep + 1.20),
        y_span=(cy - 1.15, cy + 1.15),
        z_span=(floor_z + 0.04, floor_z + 2.40)
    )
    purge_props_in_volume(
        bm,
        x_span=(x_chapel - 1.20, x_chapel + 0.10),
        y_span=(cy - 1.15, cy + 1.15),
        z_span=(chapel_floor_z + 0.04, chapel_floor_z + 2.40)
    )

    # 2. Purge residual exterior wall/timber and foundation stone faces inside the doorway passage volume
    # (strictly within the cut opening itself - the wall above the cut head and
    # beside the cut edges is left untouched so it can close the frame):
    keep_aperture = [
        f for f in bm.faces if f.is_valid
        and (x_keep - 0.22 <= f.calc_center_median().x <= x_keep + 0.22)
        and (cy - 1.25 <= f.calc_center_median().y <= cy + 1.25)
        and (floor_z - 0.05 <= f.calc_center_median().z <= floor_z + cut_h)
        and f.material_index in (MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_CLIFFS, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER)
    ]
    if keep_aperture:
        import bmesh
        bmesh.ops.delete(bm, geom=keep_aperture, context='FACES')

    chapel_aperture = [
        f for f in bm.faces if f.is_valid
        and (x_chapel - 0.22 <= f.calc_center_median().x <= x_chapel + 0.22)
        and (cy - 1.25 <= f.calc_center_median().y <= cy + 1.25)
        and (chapel_floor_z - 0.05 <= f.calc_center_median().z <= chapel_floor_z + cut_h)
        and f.material_index in (MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_CLIFFS, MAT_INDEX_PLASTER_EXT, MAT_INDEX_PLASTER_INT, MAT_INDEX_TIMBER)
    ]
    if chapel_aperture:
        import bmesh
        bmesh.ops.delete(bm, geom=chapel_aperture, context='FACES')

    # 3. Solid foundation plinth strictly beneath the floor deck (safe clearance, zero z-fighting)
    found_z0 = 13.40
    found_z1 = 14.15
    found_h = found_z1 - found_z0
    if found_h > 0.05:
        create_beveled_box(
            bm,
            size=(dx, width, found_h),
            location=(cx, cy, found_z0 + found_h * 0.5),
            mat_index=MAT_INDEX_STONE,
            bevel_amount=0.02
        )

    # 4. Clean all-wood floor deck bridging Keep and Chapel (100% flat and level, zero steps)
    deck_w = portal_w + 0.24  # 2.44m wide (comfortably fits within corridor width)
    if abs(floor_z - chapel_floor_z) < 0.08:
        create_beveled_box(
            bm,
            size=(dx + 0.24, deck_w, 0.10),
            location=(cx, cy, floor_z - 0.03),
            mat_index=MAT_INDEX_FLOOR,
            bevel_amount=0.005
        )
    else:
        lx1 = 1.15
        # Keep deck
        create_beveled_box(
            bm,
            size=(lx1, deck_w, 0.10),
            location=(x_keep - lx1 * 0.5, cy, floor_z - 0.03),
            mat_index=MAT_INDEX_FLOOR,
            bevel_amount=0.005
        )
        # Intermediate step
        lx2 = 0.55
        create_beveled_box(
            bm,
            size=(lx2, deck_w, 0.10),
            location=(x_keep - lx1 - lx2 * 0.5, cy, 14.65 - 0.03),
            mat_index=MAT_INDEX_FLOOR,
            bevel_amount=0.005
        )
        # Vertical timber riser at step 1
        create_beveled_box(
            bm,
            size=(0.04, deck_w, 0.21),
            location=(x_keep - lx1, cy, 14.65 + 0.21 * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.005
        )
        # Lower step (flush with Chapel floor)
        lx3 = dx - lx1 - lx2
        create_beveled_box(
            bm,
            size=(lx3, deck_w, 0.10),
            location=(x_chapel + lx3 * 0.5, cy, chapel_floor_z - 0.03),
            mat_index=MAT_INDEX_FLOOR,
            bevel_amount=0.005
        )
        # Vertical timber riser at step 2
        create_beveled_box(
            bm,
            size=(0.04, deck_w, 0.20),
            location=(x_chapel + lx3, cy, chapel_floor_z + 0.20 * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.005
        )

    # The smooth wood plank threshold plate under each doorway is built with
    # the portal casing further down (one single flush plate per portal).

    # 5. Dual-layer side walls (North and South):
    # Exterior: White exterior plaster (MAT_INDEX_PLASTER_EXT) with authentic half-timber framing (MAT_INDEX_TIMBER)
    # Interior: Vertical interior wood planks (MAT_INDEX_WOOD) with top ceiling wall tie beam
    wall_t = (width - deck_w) * 0.5
    wall_t_int = 0.10
    wall_t_ext = max(0.08, wall_t - wall_t_int)
    top_z = floor_z + ceiling_h
    wall_h = top_z - found_z1

    for side in (-1.0, 1.0):
        # Interior wood plank wall facing the corridor
        wy_int = cy + side * (deck_w * 0.5 + wall_t_int * 0.5)
        create_beveled_box(
            bm,
            size=(dx, wall_t_int, wall_h),
            location=(cx, wy_int, found_z1 + wall_h * 0.5),
            mat_index=MAT_INDEX_WOOD,
            bevel_amount=0.01
        )
        # Top interior ceiling crown / tie beam
        create_beveled_box(
            bm,
            size=(dx + 0.02, 0.06, 0.16),
            location=(cx, wy_int - side * (wall_t_int * 0.5 - 0.03), top_z - 0.08),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.005
        )

        # Exterior plaster wall facing outside (alley / courtyard)
        wy_ext = cy + side * (deck_w * 0.5 + wall_t_int + wall_t_ext * 0.5)
        create_beveled_box(
            bm,
            size=(dx, wall_t_ext, wall_h),
            location=(cx, wy_ext, found_z1 + wall_h * 0.5),
            mat_index=MAT_INDEX_PLASTER_EXT,
            bevel_amount=0.01
        )

        # Exterior timber framing on the outer face
        y_ext_face = cy + side * (deck_w * 0.5 + wall_t_int + wall_t_ext)
        t_thick = 0.06
        # Sill beam above stone foundation
        create_beveled_box(
            bm,
            size=(dx, t_thick, 0.14),
            location=(cx, y_ext_face - side * (t_thick * 0.5 - 0.01), found_z1 + 0.07),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
        # Eaves plate beam under roof overhang
        create_beveled_box(
            bm,
            size=(dx, t_thick, 0.14),
            location=(cx, y_ext_face - side * (t_thick * 0.5 - 0.01), top_z - 0.07),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
        # Corner timber posts at Chapel end and Keep end
        create_beveled_box(
            bm,
            size=(0.14, t_thick, wall_h),
            location=(min(x_chapel, x_keep) + 0.07, y_ext_face - side * (t_thick * 0.5 - 0.01), found_z1 + wall_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
        create_beveled_box(
            bm,
            size=(0.14, t_thick, wall_h),
            location=(max(x_chapel, x_keep) - 0.07, y_ext_face - side * (t_thick * 0.5 - 0.01), found_z1 + wall_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )
        # Intermediate vertical timber post
        create_beveled_box(
            bm,
            size=(0.12, t_thick, wall_h),
            location=(cx, y_ext_face - side * (t_thick * 0.5 - 0.01), found_z1 + wall_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )

    # 6. Clean flat wooden ceiling with timber tie joists
    ceil_z = top_z - 0.04
    create_beveled_box(
        bm,
        size=(dx + 0.04, deck_w, 0.08),
        location=(cx, cy, ceil_z - 0.04),
        mat_index=MAT_INDEX_WOOD,
        bevel_amount=0.005
    )
    for bx in (cx - 0.60, cx, cx + 0.60):
        create_beveled_box(
            bm,
            size=(0.18, deck_w + 0.08, 0.16),
            location=(bx, cy, ceil_z - 0.11),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )

    # 7. Simple pitched gable shingle roof (stops strictly flush at building walls)
    roof_ridge_z = top_z + 1.15
    roof_len = dx
    roof_span = width + 0.60
    create_beveled_box(
        bm,
        size=(roof_len, 0.18, 0.22),
        location=(cx, cy, roof_ridge_z + 0.02),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.01
    )
    half_span = roof_span * 0.5
    slope_len = math.sqrt(half_span * half_span + 1.15 * 1.15)
    pitch_ang = math.atan2(1.15, half_span)
    for sign in (-1.0, 1.0):
        ry = cy + sign * half_span * 0.5
        rz = top_z + 1.15 * 0.5
        rot_mat = Matrix.Translation(Vector((cx, ry, rz))) @ Matrix.Rotation(-sign * pitch_ang, 4, 'X')
        import bmesh
        sub_bm = bmesh.new()
        create_beveled_box(
            sub_bm,
            size=(roof_len, slope_len, 0.10),
            location=(0.0, 0.0, 0.0),
            mat_index=MAT_INDEX_SHINGLES,
            bevel_amount=0.01
        )
        # Properly unwrap shingle UVs matching main building roof orientation and scale:
        # U runs along the horizontal ridge length (scale 0.32 tiles/m)
        # V runs down the pitch slope from ridge to eave (scale 0.32 tiles/m)
        sub_bm.normal_update()
        sub_uv = sub_bm.loops.layers.uv.verify()
        for f in sub_bm.faces:
            n = f.normal
            if n.z > 0.5:
                f.material_index = MAT_INDEX_SHINGLES
                for loop in f.loops:
                    p = loop.vert.co
                    u = (p.x + roof_len * 0.5) * 0.32
                    s_dist = (p.y + slope_len * 0.5) if sign > 0 else (slope_len * 0.5 - p.y)
                    v = -s_dist * 0.32
                    loop[sub_uv].uv = Vector((u, v))
            elif n.z < -0.5:
                f.material_index = MAT_INDEX_TIMBER
                for loop in f.loops:
                    p = loop.vert.co
                    loop[sub_uv].uv = Vector(((p.x + roof_len * 0.5) * 0.40, (p.y + slope_len * 0.5) * 0.40))
            else:
                f.material_index = MAT_INDEX_TIMBER
                for loop in f.loops:
                    p = loop.vert.co
                    loop[sub_uv].uv = Vector((p.x * 0.40, p.z * 0.40))

        _merge_sub_bmesh(bm, sub_bm, rot_mat)
        sub_bm.free()

    for sign in (-1.0, 1.0):
        ey = cy + sign * half_span
        create_beveled_box(
            bm,
            size=(roof_len, 0.08, 0.18),
            location=(cx, ey, top_z + 0.02),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.01
        )

    # 8. Single unified timber portal encasements straddling each host wall.
    # The casing is centred on the wall plane (half in the room, half in the
    # connector), overlaps the cut edges of the opening and adds no redundant
    # duplicate trim pieces.
    for x_end, base_fz, wall_t in ((x_keep, floor_z, keep_wall_t),
                                   (x_chapel, chapel_floor_z, chapel_wall_t)):
        floor_top_z = base_fz + 0.065
        # Wall plane of this end (x_end is the wall centre).
        build_portal_casing(
            bm,
            center=Vector((x_end, cy, 0.0)),
            span_dir=Vector((1.0, 0.0, 0.0)),
            trans_dir=Vector((0.0, 1.0, 0.0)),
            yaw=0.0,
            cut_w=cut_w,
            cut_h=cut_h,
            cut_base_z=base_fz,
            wall_t=wall_t,
            floor_top_z=floor_top_z,
            jamb_w=jamb_w,
            casing_d=casing_d,
            mat=MAT_INDEX_TIMBER,
            threshold_mat=MAT_INDEX_FLOOR,
        )

        # The host wall above the cut-out already closes the head of the
        # opening, so no extra header panel is needed here.



def build_archive_hall_portal(
    bm,
    x_wall: float = 12.0,
    cy: float = 40.0,
    z_floor: float = 14.86,
    portal_w: float = 2.40,
    portal_h: float = 2.85,
    floor_h: float = 3.70,
):
    """
    Seamless integrated grand interior portal connecting Keep to Archive Hall.
    1. Prunes Archive Hall roof eaves/overhangs penetrating into Keep (x < 11.98, z > 14.50).
    2. Completely purges ALL exterior wall artifacts (cobblestone quoins, exterior siding,
       diagonal braces, stone blocks, corbels, exterior plaster) along the shared party wall zone
       on Floor 0 (x in [11.35, 12.65], y in [34.60, 45.40], z in [z_floor + 0.04, z_floor + floor_h + 0.05]).
    3. Clears any blocking faces within the portal aperture volume.
    4. Purges any conflicting props within the portal threshold.
    5. Constructs authentic, majestic interior door casing matching other castle chambers:
       - Smooth flush wooden threshold / floorboard plate in MAT_INDEX_FLOOR (zero stone!).
       - Timber jamb pilasters in MAT_INDEX_TIMBER running down to the wood floor (no stone plinths!).
       - Classic overhead lintel casing in MAT_INDEX_TIMBER.
       - Decorative architrave mouldings on both Keep and Archive Hall sides in MAT_INDEX_TIMBER.
       - Vertical wood plank header wall panel in MAT_INDEX_WOOD above the lintel up to the ceiling.
    6. Lines the shared party wall flanking the portal on both Keep and Archive Hall sides
       with authentic finished interior vertical wood planking (MAT_INDEX_WOOD), baseboard trims,
       and ceiling crown mouldings in MAT_INDEX_TIMBER (no white plaster, no exterior timber beams).
    7. Cleanly caps the inside corners at y=34.85 and y=45.15 with full-height interior corner
       timber pilasters, ensuring zero gaps or exposed corner seams.
    """
    import bmesh

    # 1. Cleanly purge duplicate exterior wall faces, corner posts, and foundation blocks along the shared party wall
    party_wall_faces = [
        f for f in bm.faces if f.is_valid
        and (11.60 <= f.calc_center_median().x <= 12.40)
        and (34.85 <= f.calc_center_median().y <= 45.15)
        and all(34.85 <= v.co.y <= 45.15 for v in f.verts)
        and (13.50 <= f.calc_center_median().z <= 26.50)
        and f.material_index in (
            MAT_INDEX_STONE, MAT_INDEX_CUT_STONE, MAT_INDEX_PLASTER_EXT,
            MAT_INDEX_TIMBER
        )
    ]
    if party_wall_faces:
        bmesh.ops.delete(bm, geom=party_wall_faces, context='FACES')

    # Note: Archive Hall roof properly abuts Keep exterior east wall at x=12.0
    # via roof_abut_left=True, without penetrating Keep interior. Keep's own roof
    # deck runs to x=12.0 and must not be purged.

    # 2. Clear any stray faces within the exact portal aperture opening volume
    hw = portal_w * 0.5
    aperture_faces = [
        f for f in bm.faces if f.is_valid
        and (11.45 <= f.calc_center_median().x <= 12.55)
        and (cy - hw - 0.06 <= f.calc_center_median().y <= cy + hw + 0.06)
        and (z_floor + 0.01 <= f.calc_center_median().z <= z_floor + portal_h + 0.08)
    ]
    if aperture_faces:
        bmesh.ops.delete(bm, geom=aperture_faces, context='FACES')

    # Purge any conflicting props in the doorway threshold
    purge_props_in_volume(
        bm,
        x_span=(10.8, 13.2),
        y_span=(cy - hw - 0.35, cy + hw + 0.35),
        z_span=(z_floor + 0.02, z_floor + portal_h + 0.20)
    )

    # 3. Seamless raised wooden threshold plank bridging the room joint (zero coplanar conflicts)
    th_step = 0.086  # Raised by 5 cm to prevent coplanar conflicts
    th_embed = 0.020
    th_thick = th_step + th_embed
    create_beveled_box(
        bm,
        size=(0.86, portal_w + 0.10, th_thick),
        location=(x_wall, cy, z_floor + 0.05 + th_step * 0.5 - th_embed * 0.5),
        mat_index=MAT_INDEX_FLOOR,
        bevel_amount=0.005
    )

    # 4. Smooth timber jamb lining across the party wall thickness (resting flush on wood floor)
    jamb_t = 0.82  # Spans from Keep inner face (11.62) to Archive inner face (12.38)
    jamb_w = 0.10  # Jamb width
    for sgn in (-1.0, 1.0):
        jy = cy + sgn * (hw + jamb_w * 0.5)
        create_beveled_box(
            bm,
            size=(jamb_t, jamb_w, portal_h),
            location=(x_wall, jy, z_floor + portal_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.012
        )

    # 5. Overhead timber soffit / lintel beam spanning the opening
    create_beveled_box(
        bm,
        size=(jamb_t, portal_w + jamb_w * 2.0, 0.14),
        location=(x_wall, cy, z_floor + portal_h + 0.07),
        mat_index=MAT_INDEX_TIMBER,
        bevel_amount=0.012
    )

    # 6. Classic interior door architraves in MAT_INDEX_TIMBER matching interior room doors
    # Placed flush against the true inner wall faces: Keep at 11.62, Archive Hall at 12.38
    casing_d = 0.05
    casing_w = 0.10
    head_h = 0.14
    for fx_wall in (11.61, 12.39):
        for sgn in (-1.0, 1.0):
            ty = cy + sgn * (hw + casing_w * 0.5)
            create_beveled_box(
                bm,
                size=(casing_d, casing_w, portal_h + 0.02),
                location=(fx_wall, ty, z_floor + (portal_h + 0.02) * 0.5),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.006
            )
        # Architrave header casing
        head_w = portal_w + casing_w * 2.0 + 0.06
        create_beveled_box(
            bm,
            size=(casing_d + 0.02, head_w, head_h),
            location=(fx_wall, cy, z_floor + portal_h + head_h * 0.5),
            mat_index=MAT_INDEX_TIMBER,
            bevel_amount=0.008
        )

    # 7. Header fill panel sealing above the lintel up to ceiling slab
    header_bot = z_floor + portal_h + 0.14
    header_top = z_floor + floor_h
    header_h = header_top - header_bot
    if header_h > 0.02:
        header_cz = (header_bot + header_top) * 0.5
        header_w = portal_w + casing_w * 2.0
        for fx_wall in (11.61, 12.39):
            create_box(
                bm,
                size=(0.03, header_w, header_h),
                location=(fx_wall, cy, header_cz),
                mat_index=MAT_INDEX_WOOD,
                is_wall=True
            )
            create_beveled_box(
                bm,
                size=(casing_d + 0.01, header_w + 0.08, 0.08),
                location=(fx_wall, cy, header_top - 0.04),
                mat_index=MAT_INDEX_TIMBER,
                bevel_amount=0.008
            )

    # 8. Finished interior vertical wood planking lining the party wall flanking the portal on Floor 0
    # South flank: [35.05, cy - hw], North flank: [cy + hw, 44.95]
    flanks = [
        (35.05, cy - hw - 0.02),
        (cy + hw + 0.02, 44.95),
    ]
    for y0, y1 in flanks:
        flank_len = y1 - y0
        if flank_len < 0.2:
            continue
        flank_my = (y0 + y1) * 0.5

        # Keep side interior wall panel & trims (inner face facing -X into Keep)
        create_box(
            bm, size=(0.04, flank_len, floor_h),
            location=(11.64, flank_my, z_floor + floor_h * 0.5),
            mat_index=MAT_INDEX_WOOD, is_wall=True
        )
        create_beveled_box(
            bm, size=(0.06, flank_len, 0.16),
            location=(11.63, flank_my, z_floor + 0.08),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )
        create_beveled_box(
            bm, size=(0.06, flank_len, 0.12),
            location=(11.63, flank_my, z_floor + floor_h - 0.06),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )

        # Archive Hall side interior wall panel & trims (inner face facing +X into Archive Hall)
        create_box(
            bm, size=(0.04, flank_len, floor_h),
            location=(12.36, flank_my, z_floor + floor_h * 0.5),
            mat_index=MAT_INDEX_WOOD, is_wall=True
        )
        create_beveled_box(
            bm, size=(0.06, flank_len, 0.16),
            location=(12.37, flank_my, z_floor + 0.08),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )
        create_beveled_box(
            bm, size=(0.06, flank_len, 0.12),
            location=(12.37, flank_my, z_floor + floor_h - 0.06),
            mat_index=MAT_INDEX_TIMBER, bevel_amount=0.006
        )

    # 9. Corner pilasters sealing the inside corners where Archive Hall front/back walls meet party wall
    for fx_corner in (11.63, 12.37):
        for cy_corner in (35.05, 44.95):
            create_beveled_box(
                bm, size=(0.14, 0.14, floor_h),
                location=(fx_corner, cy_corner, z_floor + floor_h * 0.5),
                mat_index=MAT_INDEX_TIMBER, bevel_amount=0.012
            )


def build_throne_room_mezzanine(
    bm,
    x_span: tuple = (-5.6, 0.75),
    y_span: tuple = (-5.8, 5.8),
    z_floor: float = 18.56,
    z_high_ceil: float = 22.20,
    keep_cx: float = 0.0,
    keep_cy: float = 40.0,
    build_balustrade: bool = False,
):
    """
    Deprecated: Vaulted tie-trusses across the Throne Room ceiling are superseded
    by the global ceiling beams (build_ceiling_beams) in MAT_INDEX_TIMBER with grain along length.
    """
    pass




