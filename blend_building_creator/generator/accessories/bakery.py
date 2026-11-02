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
    create_horizontal_cylinder, create_torus_ring, transform_faces,
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
    # Give the swept faces real box-projected UVs so the terracotta brick
    # texture repeats along the flue instead of rendering as one flat colour.
    uv_layer = bm.loops.layers.uv.verify()
    uv_scale = 0.72
    for f in new_faces:
        f.normal_update()
        n = f.normal
        for loop in f.loops:
            p = loop.vert.co
            if abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z):
                u, v = p.y, p.z
            elif abs(n.y) >= abs(n.z):
                u, v = p.x, p.z
            else:
                u, v = p.x, p.y
            loop[uv_layer].uv = (u * uv_scale, v * uv_scale)
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
    # 5. Stylized fantasy flue.
    #
    # The old flue was three plain brick boxes with two flat slabs on top: it
    # read as a brick pillar, not a chimney.  The new stack keeps the same
    # safe path (rise from the oven, diagonal jog clear of the eave, then a
    # short outdoor stack) but dresses it as crafted bakehouse masonry:
    #
    #   * a corbelled cut-stone foot and stone bands on the indoor shaft
    #   * a little iron clean-out door with a ring pull on the room side
    #   * wrought-iron hoops around the brickwork
    #   * a flared corbel crown, cut-stone cap and a flared clay chimney pot
    #   * a hand-forged weathervane with a bagel-ring finial
    # -------------------------------------------------------------------------
    _roof_ov = float(getattr(props, 'roof_overhang', 0.72) or 0.72)
    _out_off = max(0.82, _roof_ov + 0.20)
    _outer_x = _side * (hx + _out_off)
    _z0 = z_floor + hearth_h + dome_h + 0.08
    _z1 = _z0 + 1.00
    _z2 = _z1 + 0.78
    _z3 = _z2 + 1.05
    _body = 1.06
    _half = _body * 0.5
    _ov = 0.22
    # Which way the bakehouse room lies from the flue centre.
    _room_dir = -1.0 if _side > 0 else 1.0

    def _iron_hoop(cx, cy, cz, half, height=0.055, thick=0.045):
        """Four thin forged straps wrapping a square brick shaft."""
        _long = 2.0 * half + 0.05
        create_beveled_box(
            bm, size=(_long, thick, height),
            location=(cx, cy + half, cz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
        create_beveled_box(
            bm, size=(_long, thick, height),
            location=(cx, cy - half, cz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
        create_beveled_box(
            bm, size=(thick, _long, height),
            location=(cx + half, cy, cz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
        create_beveled_box(
            bm, size=(thick, _long, height),
            location=(cx - half, cy, cz),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.006)

    # ---- Indoor shaft: stone foot, brick body, stone band -----------------
    create_beveled_box(
        bm, size=(1.34, 1.34, 0.15),
        location=(base_x, base_y, _z0 + 0.01),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.020)
    create_beveled_box(
        bm, size=(_body, _body, (_z1 - _z0) + _ov * 2.0),
        location=(base_x, base_y, (_z0 + _z1) * 0.5),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.012)
    create_beveled_box(
        bm, size=(1.16, 1.16, 0.10),
        location=(base_x, base_y, _z0 + 0.76),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.014)
    _iron_hoop(base_x, base_y, _z0 + 0.93, _half + 0.012)

    # ---- Little iron clean-out door on the bakehouse face -----------------
    _face = base_x + _room_dir * _half
    create_beveled_box(
        bm, size=(0.05, 0.44, 0.54),
        location=(_face + _room_dir * 0.025, base_y, _z0 + 0.34),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)
    create_beveled_box(
        bm, size=(0.03, 0.30, 0.40),
        location=(_face + _room_dir * 0.055, base_y, _z0 + 0.34),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
    for _strap_z in (_z0 + 0.25, _z0 + 0.43):
        create_beveled_box(
            bm, size=(0.02, 0.26, 0.030),
            location=(_face + _room_dir * 0.073, base_y, _strap_z),
            mat_index=MAT_INDEX_IRON, bevel_amount=0.004)
    create_torus_ring(
        bm, location=(_face + _room_dir * 0.095, base_y + 0.07, _z0 + 0.34),
        rotation=(0.0, math.pi * 0.5, 0.0),
        major_radius=0.032, minor_radius=0.007,
        major_segments=12, minor_segments=6,
        mat_index=MAT_INDEX_IRON)

    # ---- Diagonal jog out through the eave --------------------------------
    create_beveled_box(
        bm, size=(1.22, 1.22, 0.13),
        location=(base_x, base_y, _z1 + 0.02),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.018)
    _dx = _outer_x - base_x
    _dz = _z2 - _z1
    _diag_len = math.hypot(_dx, _dz) + _ov * 2.0
    _diag_ang = -math.atan2(_dz, _dx)
    create_beveled_box(
        bm, size=(_diag_len, _body, _body),
        location=((base_x + _outer_x) * 0.5, base_y, (_z1 + _z2) * 0.5),
        rotation=(0.0, _diag_ang, 0.0),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.012)
    create_beveled_box(
        bm, size=(1.22, 1.22, 0.14),
        location=(_outer_x, base_y, _z2 - 0.01),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.018)

    # ---- Outdoor stack: brick shaft, stone bands, iron hoops --------------
    create_beveled_box(
        bm, size=(_body, _body, (_z3 - _z2) + _ov * 2.0),
        location=(_outer_x, base_y, (_z2 + _z3) * 0.5),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.012)
    create_beveled_box(
        bm, size=(1.16, 1.16, 0.09),
        location=(_outer_x, base_y, _z2 + 0.42),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.012)
    _iron_hoop(_outer_x, base_y, _z2 + 0.68, _half + 0.012)
    _iron_hoop(_outer_x, base_y, _z3 - 0.36, _half + 0.012)

    # ---- Flared corbel crown and cut-stone cap ----------------------------
    create_beveled_box(
        bm, size=(1.18, 1.18, 0.14),
        location=(_outer_x, base_y, _z3 + 0.07),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.012)
    create_beveled_box(
        bm, size=(1.32, 1.32, 0.14),
        location=(_outer_x, base_y, _z3 + 0.20),
        mat_index=MAT_INDEX_TERRACOTTA, bevel_amount=0.014)
    create_beveled_box(
        bm, size=(1.44, 1.44, 0.11),
        location=(_outer_x, base_y, _z3 + 0.32),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.016)
    create_beveled_box(
        bm, size=(1.16, 1.16, 0.07),
        location=(_outer_x, base_y, _z3 + 0.41),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.010)

    # ---- Flared clay chimney pot ------------------------------------------
    _pot_z = _z3 + 0.45
    create_cone(
        bm, radius1=0.25, radius2=0.19, height=0.52, segments=10,
        location=(_outer_x, base_y, _pot_z + 0.26),
        mat_index=MAT_INDEX_CLAY)
    create_cylinder(
        bm, radius=0.28, height=0.08, segments=10,
        location=(_outer_x, base_y, _pot_z + 0.54),
        mat_index=MAT_INDEX_CLAY)
    create_cylinder(
        bm, radius=0.26, height=0.05, segments=10,
        location=(_outer_x, base_y, _pot_z + 0.36),
        mat_index=MAT_INDEX_CLAY)
    # Soot-dark throat inside the pot rim.
    create_cylinder(
        bm, radius=0.205, height=0.035, segments=10,
        location=(_outer_x, base_y, _pot_z + 0.585),
        mat_index=MAT_INDEX_IRON)

    # ---- Hand-forged weathervane with a bagel-ring finial -----------------
    _vane_base = _pot_z + 0.60
    create_cylinder(
        bm, radius=0.022, height=0.82, segments=6,
        location=(_outer_x, base_y, _vane_base + 0.41),
        mat_index=MAT_INDEX_IRON)
    _vane_z = _vane_base + 0.73
    create_beveled_box(
        bm, size=(0.035, 0.88, 0.035),
        location=(_outer_x, base_y, _vane_z),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.005)
    create_cone(
        bm, radius1=0.070, radius2=0.0, height=0.18, segments=4,
        location=(_outer_x, base_y + 0.52, _vane_z),
        rotation=(-math.pi * 0.5, 0.0, 0.0),
        mat_index=MAT_INDEX_IRON)
    create_beveled_box(
        bm, size=(0.024, 0.36, 0.20),
        location=(_outer_x, base_y - 0.22, _vane_z),
        mat_index=MAT_INDEX_IRON, bevel_amount=0.006)
    create_torus_ring(
        bm, location=(_outer_x, base_y, _vane_base + 0.88),
        rotation=(math.pi * 0.5, 0.0, 0.0),
        major_radius=0.095, minor_radius=0.016,
        major_segments=16, minor_segments=6,
        mat_index=MAT_INDEX_IRON)

    return faces
