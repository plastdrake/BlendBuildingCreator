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
    MAT_INDEX_LANTERN, MAT_INDEX_CLAY,
)


def bakery_oven_slot(hx, hy, wall_t):
    """Shared bake-oven footprint (relative to the building centre).

    The oven sits on the +X flank wall — opposite the left-hand staircase that
    straight stairs climb — and is centred in depth. Both the oven and the roof
    chimney call this so the flue always rises straight out of the oven.
    """
    oven_x = max(1.2, hx - wall_t - 0.90)
    oven_y = max(-hy + wall_t + 1.10, min(hy - wall_t - 1.10, 0.0))
    return oven_x, oven_y


def _right_window_ys(ctx):
    ys = []
    wc = getattr(ctx, 'window_centers', None) or {}
    for facades in wc.values():
        for _wx, wy, _sz in facades.get('RIGHT', []):
            ys.append(wy)
    return ys


def _pick_oven_y(ctx, hy, wall_t, half_w):
    """Pick a Y for the oven along the +X wall that clears every RIGHT-window."""
    lo = -hy + wall_t + half_w
    hi = hy - wall_t - half_w
    if hi < lo or ctx is None:
        return 0.0
    ys = _right_window_ys(ctx)
    if not ys:
        return 0.0

    def clear(v):
        return all(abs(v - wy) > half_w + 0.5 for wy in ys)

    if clear(0.0):
        return 0.0
    best, best_d = 0.0, 1e9
    steps = max(1, int((hi - lo) / 0.2))
    for i in range(steps + 1):
        v = lo + (hi - lo) * i / steps
        if clear(v) and abs(v) < best_d:
            best, best_d = v, abs(v)
    return best


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

    # World placement: back flush against the +X interior wall, mouth facing in.
    base_x = (hx - wall_t) - hearth_d * 0.5
    base_y = _pick_oven_y(ctx, hy, wall_t, hearth_w * 0.5 + 0.1)

    faces += create_beveled_box(
        bm, size=(hearth_w, hearth_d, hearth_h),
        location=(oven_x, oven_y, hearth_z),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.03
    )

    # Decorative stone landing shelf in front of the oven mouth
    faces += create_beveled_box(
        bm, size=(hearth_w + 0.06, 0.24, 0.08),
        location=(oven_x, oven_y - hearth_d * 0.5 - 0.06, z_floor + hearth_h - 0.04),
        mat_index=MAT_INDEX_CUT_STONE, bevel_amount=0.015
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
    # Stack of split firewood logs in the alcove
    for row in range(2):
        lz = z_floor + 0.10 + row * 0.14
        for col in range(3):
            lx = oven_x - 0.26 + col * 0.26
            faces += create_horizontal_cylinder(
                bm, radius_y=0.06, radius_z=0.06, length=0.55, segments=8,
                location=(lx, oven_y - hearth_d * 0.5 + 0.32, lz),
                mat_index=MAT_INDEX_WOOD
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

    # Inner glowing firebox embers behind hearth opening
    faces += create_beveled_box(
        bm, size=(0.50, 0.12, 0.16),
        location=(oven_x, door_y + 0.10, z_floor + hearth_h + 0.10),
        mat_index=MAT_INDEX_LANTERN, bevel_amount=0.02
    )

    # Rotate the whole oven so its back is flush to the +X wall and the mouth
    # faces into the room.
    oven_mat = (Matrix.Translation(Vector((base_x, base_y, 0.0)))
                @ Matrix.Rotation(oven_rot, 4, 'Z'))
    transform_faces(faces, oven_mat)

    # -------------------------------------------------------------------------
    # 5. Dedicated masonry bake-oven flue, rising straight out of the oven crown
    #    through the roof. This is the bakery's only chimney.
    # -------------------------------------------------------------------------
    from ..roof.features import build_fantasy_chimney
    if ctx is not None:
        top_z = (z_floor + ctx.num_floors * ctx.floor_h
                 + getattr(props, 'roof_height', 3.0) + 1.0)
    else:
        top_z = z_floor + 2.8 + 3.0 + 1.0
    build_fantasy_chimney(
        bm, pos_xy=(base_x, base_y), z_start=0.0, total_height=top_z,
        width=0.90, depth=0.90, crooked_angle=-0.02,
    )

    return faces
