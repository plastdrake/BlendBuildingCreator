"""
Artisan Bakery accessories: master baker's indoor brick hearth oven and artisanal baking props.

Features an authentic indoor brick bake-oven built on a cut-stone masonry plinth with:
- Recessed firewood log storage arch under the hearth
- Curved brick baking dome with beveled masonry surround
- Heavy cast-iron arched oven door with forged strap hinges and sliding latch
- Glowing firebox ember cavity casting cozy interior baking warmth
- Handcrafted wooden baker's peel (bread shovel) leaning against the hearth
- Tied burlap flour sacks and slatted timber bread cooling crates
- Clean exterior: no unsightly exterior blobs cutting through window shutters!
"""

import math
from mathutils import Vector, Matrix, Euler
from ..mesh_utils import (
    create_box, create_beveled_box, create_cylinder, create_cone,
    create_horizontal_cylinder, transform_faces,
)
from ..materials import (
    MAT_INDEX_STONE, MAT_INDEX_TIMBER, MAT_INDEX_IRON,
    MAT_INDEX_WOOD, MAT_INDEX_CUT_STONE, MAT_INDEX_PLASTER_BRICK,
    MAT_INDEX_LANTERN, MAT_INDEX_CLAY, MAT_INDEX_TERRACOTTA,
)


def bakery_oven_wall_side(props, ctx=None):
    """-1 for the left wall, +1 for the right wall: opposite the stair."""
    side = None
    if ctx is not None:
        side = getattr(ctx, 'annex_stair_side', None)
    if not side:
        side = getattr(props, 'stair_placement', 'LEFT')
    return -1.0 if str(side).upper() == 'RIGHT' else 1.0


def bakery_oven_slot(hx, hy, wall_t):
    """Shared bake-oven footprint (relative to the building centre).

    The oven sits on the +X flank wall — opposite the left-hand staircase that
    straight stairs climb — and is centred in depth. Both the oven and the roof
    chimney call this so the flue always rises straight out of the oven.
    """
    oven_x = max(1.2, hx - wall_t - 0.90)
    oven_y = max(-hy + wall_t + 1.10, min(hy - wall_t - 1.10, 0.0))
    return oven_x, oven_y


# Fixed hearth-oven slot shared by the wall, room-planning and furnishing
# phases. The oven body is 1.75m wide (Y) x 1.35m deep (X) with its back
# flush to the +X interior wall and its mouth facing into the room; the
# ground-floor RIGHT facade keeps glazing clear of OVEN_WIN_CLEAR so the
# oven always lands at depth-centre, and no cross-partition may enter
# OVEN_WALL_CLEAR (which also covers the flue rising through the storeys
# above, plus a working apron in front of the mouth for the furnisher).
OVEN_HALF_W = 0.875
OVEN_WIN_CLEAR = 1.50
OVEN_WALL_CLEAR = 1.85


def bakery_oven_rect(hx, wall_t, base_y=0.0):
    """World-space keep-out for the hearth oven: masonry body + landing shelf
    plus a 1m working apron in front of the mouth."""
    base_x = (hx - wall_t) - 1.35 * 0.5
    return (base_x - (1.35 * 0.5 + 0.24 + 1.00), hx - wall_t + 0.05,
            base_y - 1.25, base_y + 1.25)


def _right_window_ys(ctx):
    # Ground-floor RIGHT windows only: the oven stands on the ground storey,
    # so only its own facade glazing constrains the slot (the flue shaft
    # above stands clear of the wall plane).
    ys = []
    wc = getattr(ctx, 'window_centers', None) or {}
    for _wx, wy, _sz in (wc.get(0) or {}).get('RIGHT', []):
        ys.append(wy)
    return ys


def _pick_oven_y(ctx, hy, wall_t, half_w):
    """Pick a Y for the oven along the +X wall that clears every RIGHT-window."""
    lo = -hy + wall_t + half_w
    hi = hy - wall_t - half_w
    if hi < lo or ctx is None:
        return 0.0
    ys = _right_window_ys(ctx)
    # Prefer the rear bakehouse half, not the mid-depth stair landing.
    target = min(hi, max(lo, hy * 0.55))
    if not ys:
        return target

    def clear(v):
        return all(abs(v - wy) > half_w + 0.5 for wy in ys)

    if clear(target):
        return target
    best, best_d = target, 1e9
    steps = max(1, int((hi - lo) / 0.2))
    for i in range(steps + 1):
        v = lo + (hi - lo) * i / steps
        if clear(v) and abs(v - target) < best_d:
            best, best_d = v, abs(v - target)
    return best


def _build_brick_flue(bm, points, half_w, mat_index):
    """One continuous swept brick prism along a polyline."""
    import bmesh
    rings = []
    corners = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
    for (x, y, z) in points:
        rings.append([bm.verts.new((x + cx * half_w, y + cy * half_w, z))
                      for cx, cy in corners])
    new_faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            f = bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
            f.material_index = mat_index
            new_faces.append(f)
    for ring, reverse in ((rings[0], True), (rings[-1], False)):
        verts = list(reversed(ring)) if reverse else ring
        f = bm.faces.new(verts)
        f.material_index = mat_index
        new_faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=new_faces)
    return new_faces


def build_bakery_oven(bm, *args, **kwargs):
    """Builds the authentic indoor master baker's hearth oven and artisanal props.

    Accepts (bm, props, ctx, tier) or legacy (bm, x_min, x_max, y_min, y_max, z_ground).
    """
    ctx = None
    if len(args) >= 3 and hasattr(args[1], 'hx'):
        # Called as build_bakery_oven(bm, props, ctx, tier)
        props, ctx = args[0], args[1]
        tier = args[2] if len(args) > 2 else 'TIER_2'
        hx, hy = ctx.hx, ctx.hy
        z_floor = ctx.found_h
        wall_t = ctx.wall_t
        door_x = ctx.main_door_cx
    else:
        # Legacy positional fallback (bm, x_min, x_max, y_min, y_max, z_ground)
        x_min, x_max = args[0], args[1]
        y_min, y_max = args[2], args[3]
        z_floor = args[4] if len(args) > 4 else 0.45
        hx = (x_max - x_min) * 0.5
        hy = (y_max - y_min) * 0.5
        wall_t = 0.28
        door_x = 0.0
        tier = 'TIER_2'

    # Built in a local frame (mouth toward -Y) then rotated so the back stands
    # against the +X interior wall with the mouth facing into the room, sliding
    # along the wall to clear any RIGHT-window so it never overlaps glazing.
    oven_x, oven_y = 0.0, 0.0
    oven_rot = -math.pi * 0.5
    faces = []

    # -------------------------------------------------------------------------
    # 1. Heavy Cut-Stone Hearth Plinth
    # -------------------------------------------------------------------------
    hearth_w = 1.75
    hearth_d = 1.35
    hearth_h = 0.70
    hearth_z = z_floor + hearth_h * 0.5

    # World placement: back flush against the interior wall opposite the
    # stair, mouth facing into the bakehouse.
    _side = bakery_oven_wall_side(props, ctx)
    base_x = _side * ((hx - wall_t) - hearth_d * 0.5)
    base_y = _pick_oven_y(ctx, hy, wall_t, hearth_w * 0.5 + 0.1)
    oven_rot = -math.pi * 0.5 if _side > 0 else math.pi * 0.5

    faces += create_beveled_box(
        bm, size=(hearth_w, hearth_d, hearth_h),
        location=(oven_x, oven_y, hearth_z),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03
    )

    # -------------------------------------------------------------------------
    # 2. Recessed Firewood Storage Cavity Under Hearth
    # -------------------------------------------------------------------------
    arch_w = 0.85
    arch_d = 0.65
    arch_h = 0.42
    # Shadow back of firewood alcove
    faces += create_beveled_box(
        bm, size=(arch_w, 0.04, arch_h),
        location=(oven_x, oven_y - hearth_d * 0.5 + arch_d + 0.02, z_floor + arch_h * 0.5 + 0.04),
        mat_index=MAT_INDEX_STONE, bevel_amount=0.01
    )

    # -------------------------------------------------------------------------
    # 3. Terracotta Brick Baking Chamber Dome
    # -------------------------------------------------------------------------
    dome_w = 1.55
    dome_d = 1.15
    dome_h = 0.85
    dome_z = z_floor + hearth_h + dome_h * 0.5

    faces += create_beveled_box(
        bm, size=(dome_w, dome_d, dome_h),
        location=(oven_x, oven_y, dome_z),
        mat_index=MAT_INDEX_PLASTER_BRICK, bevel_amount=0.06
    )

    # Stepped upper masonry crown
    faces += create_beveled_box(
        bm, size=(dome_w - 0.20, dome_d - 0.16, 0.20),
        location=(oven_x, oven_y, z_floor + hearth_h + dome_h + 0.08),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03
    )

    # -------------------------------------------------------------------------
    # 4. Arched Cast-Iron Oven Door & Glowing Firebox
    # -------------------------------------------------------------------------
    door_w = 0.65
    door_h = 0.54
    door_y = oven_y - dome_d * 0.5 - 0.02
    door_z = z_floor + hearth_h + 0.05 + door_h * 0.5

    # Arched stone surround trim
    faces += create_beveled_box(
        bm, size=(door_w + 0.18, 0.08, door_h + 0.16),
        location=(oven_x, door_y + 0.02, door_z + 0.04),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.02
    )

    # Heavy cast-iron door
    faces += create_beveled_box(
        bm, size=(door_w, 0.04, door_h),
        location=(oven_x, door_y - 0.01, door_z),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.012
    )

    # Forged horizontal strap hinges across the door
    for hz in (door_z - door_h * 0.28, door_z + door_h * 0.28):
        faces += create_beveled_box(
            bm, size=(door_w * 0.90, 0.02, 0.04),
            location=(oven_x, door_y - 0.035, hz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.005
        )

    # Latch bar and pull handle
    faces += create_beveled_box(
        bm, size=(0.14, 0.03, 0.03),
        location=(oven_x + door_w * 0.28, door_y - 0.045, door_z),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004
    )

    # Rotate the whole oven so its back is flush to the +X wall and the mouth
    # faces into the room.
    oven_mat = (Matrix.Translation(Vector((base_x, base_y, 0.0)))
                @ Matrix.Rotation(oven_rot, 4, 'Z'))
    transform_faces(faces, oven_mat)

    # -------------------------------------------------------------------------
    # 5. One continuous clay-brick flue: a short vertical rise from the oven,
    #    a longer diagonal jog out through the wall (clear of the roof
    #    overhang), then a short vertical stack outside.  The swept prism is a
    #    single connected mesh in terracotta brick rather than stacked stone
    #    boxes, so there are no gaps or intersecting block ends.
    # -------------------------------------------------------------------------
    _roof_ov = float(getattr(props, 'roof_overhang', 0.72) or 0.72)
    _out_off = max(0.82, _roof_ov + 0.20)
    _outer_x = _side * (hx + _out_off)
    _z0 = z_floor + hearth_h + dome_h + 0.08
    _z1 = _z0 + 0.78
    _z2 = _z1 + 0.52
    _z3 = _z2 + 1.18
    _flue_pts = [
        (base_x, base_y, _z0),
        (base_x, base_y, _z1),
        (_outer_x, base_y, _z2),
        (_outer_x, base_y, _z3),
    ]
    _build_brick_flue(bm, _flue_pts, 0.48, MAT_INDEX_TERRACOTTA)
    # A chunky brick cap makes the top read as a finished chimney, not a pipe.
    create_beveled_box(
        bm, size=(1.12, 1.12, 0.17),
        location=(_outer_x, base_y, _z3 + 0.085),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.012)
    create_beveled_box(
        bm, size=(0.90, 0.90, 0.11),
        location=(_outer_x, base_y, _z3 + 0.225),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.008)
    # Dark soot throat inside the crown.
    create_beveled_box(
        bm, size=(0.42, 0.42, 0.055),
        location=(_outer_x, base_y, _z3 + 0.27),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.004)

    return faces
