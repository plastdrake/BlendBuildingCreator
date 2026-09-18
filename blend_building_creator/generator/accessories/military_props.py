"""Reusable military yard props: weapon racks, wall shields, training dummies."""

import math
from ..mesh_utils import create_beveled_box, create_cylinder, create_cone
from ..materials import MAT_INDEX_TIMBER, MAT_INDEX_TIMBER_FRAME, MAT_INDEX_IRON


def build_shield_mount(bm, x, y, z, normal=(0.0, -1.0), r=0.34):
    """A round shield with an iron boss mounted flat on a wall."""
    nx, ny = normal
    ox, oy = x + nx * 0.06, y + ny * 0.06
    if abs(nx) > abs(ny):
        rot = (0.0, 1.5708, 0.0)
    else:
        rot = (1.5708, 0.0, 0.0)
    create_cylinder(bm, radius=r, height=0.07, segments=16,
                    location=(ox, oy, z), rotation=rot, mat_index=MAT_INDEX_TIMBER)
    create_cylinder(bm, radius=r * 0.82, height=0.05, segments=16,
                    location=(ox + nx * 0.03, oy + ny * 0.03, z), rotation=rot,
                    mat_index=MAT_INDEX_TIMBER_FRAME)
    create_cone(bm, radius1=r * 0.30, radius2=0.0, height=0.10, segments=10,
                location=(ox + nx * 0.05, oy + ny * 0.05, z),
                rotation=(1.5708, 0.0, 0.0) if abs(ny) >= abs(nx) else (0.0, 1.5708, 0.0),
                mat_index=MAT_INDEX_IRON)


def build_weapon_rack(bm, x, y, z_ground=0.0, ang=0.0):
    """A-frame rack holding a few leaning spears and an axe."""
    ca, sa = math.cos(ang), math.sin(ang)
    def along(d, z):
        return (x + ca * d, y + sa * d, z)
    # Two uprights + top rail.
    for d in (-0.55, 0.55):
        px, py, _ = along(d, 0.0)
        create_beveled_box(bm, size=(0.12, 0.12, 1.25), location=(px, py, z_ground + 0.62),
                           rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    cx, cy, _ = along(0.0, 0.0)
    create_beveled_box(bm, size=(1.30, 0.14, 0.14), location=(cx, cy, z_ground + 1.18),
                       rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    create_beveled_box(bm, size=(1.30, 0.10, 0.10), location=(cx, cy, z_ground + 0.42),
                       rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.008)
    # Spears leaning across the rack.
    for i, d in enumerate((-0.42, -0.05, 0.34)):
        px, py, _ = along(d, 0.0)
        create_cylinder(bm, radius=0.028, height=2.05, segments=6,
                        location=(px, py, z_ground + 1.0),
                        rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER)
        create_cone(bm, radius1=0.06, radius2=0.0, height=0.20, segments=6,
                    location=(px, py, z_ground + 2.08), mat_index=MAT_INDEX_IRON)


def build_training_dummy(bm, x, y, z_ground=0.0, ang=0.0):
    """A straw practice dummy on a post with a crossbar."""
    create_cylinder(bm, radius=0.09, height=1.7, segments=8,
                    location=(x, y, z_ground + 0.85), mat_index=MAT_INDEX_TIMBER)
    create_beveled_box(bm, size=(1.05, 0.12, 0.12), location=(x, y, z_ground + 1.35),
                       rotation=(0.0, 0.0, ang), mat_index=MAT_INDEX_TIMBER, bevel_amount=0.01)
    # Straw body + head.
    create_cylinder(bm, radius=0.24, height=0.70, segments=10,
                    location=(x, y, z_ground + 1.10), mat_index=MAT_INDEX_TIMBER_FRAME)
    create_cylinder(bm, radius=0.15, height=0.24, segments=10,
                    location=(x, y, z_ground + 1.60), mat_index=MAT_INDEX_TIMBER_FRAME)
    create_beveled_box(bm, size=(0.16, 0.16, 0.20), location=(x, y, z_ground + 1.10),
                       mat_index=MAT_INDEX_IRON, bevel_amount=0.01)


def build_military_props(bm, props, ctx):
    """Scatter a mix of military props along the courtyard-facing front wall."""
    count = max(1, int(getattr(props, 'military_props_count', 3)))
    wall_t = ctx.wall_t
    y_wall = -ctx.base_d * 0.5 - wall_t * 0.5 - 0.10
    door_clear = getattr(props, 'door_width', 1.2) * 0.5 + 1.1
    usable_x0 = -ctx.base_w * 0.5 + 1.4
    usable_x1 = ctx.base_w * 0.5 - 1.4
    if usable_x1 <= usable_x0:
        return
    span = usable_x1 - usable_x0
    for i in range(count):
        frac = (i + 0.5) / count
        px = usable_x0 + span * frac
        # Keep clear of the entrance.
        if abs(px - ctx.main_door_cx) < door_clear:
            px += door_clear
            if px > usable_x1:
                px -= 2.0 * door_clear
        kind = i % 3
        if kind == 0:
            build_weapon_rack(bm, px, y_wall - 0.35, 0.0, ang=0.0)
        elif kind == 1:
            build_training_dummy(bm, px, y_wall - 0.5, 0.0, ang=0.0)
        else:
            build_shield_mount(bm, px, y_wall + 0.02, ctx.found_h + 1.2, normal=(0.0, -1.0))
