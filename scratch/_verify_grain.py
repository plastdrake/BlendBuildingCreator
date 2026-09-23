"""Verify timber_box UVs: V (grain) must run along each beam's long axis.

Builds sample posts/beams/rafters through the real timber_box helper in a
headless bmesh, then checks every side face: UV-V must correlate (>0.9) with
position along the beam's world long axis. End caps are skipped.
"""
import math
import sys

import bpy  # noqa: F401  (ensures mathutils availability context)
from mathutils import Euler, Matrix, Vector
import bmesh

REPO = r"D:\BlendBuildingCreator"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from blend_building_creator.generator.uv_utils import timber_box

CASES = [
    ("post", (0.24, 0.24, 2.66), (0.0, 0.0, 0.7)),
    ("x-beam", (2.60, 0.20, 0.14), (0.0, 0.0, 0.7)),
    ("y-beam", (0.20, 2.60, 0.14), (0.0, 0.0, -1.1)),
    ("yawed-post", (0.24, 0.24, 2.66), (0.0, 0.0, 2.3)),
    ("rafter", (2.30, 0.14, 0.10), (0.0, -0.5, 1.2)),
    ("leaf", (0.08, 1.16, 2.56), (0.0, 0.0, 0.3)),
    ("jamb", (0.48, 0.22, 2.82), (0.0, 0.0, -0.6)),
    ("header", (0.48, 1.74, 0.22), (0.0, 0.0, 1.9)),
]


def longest_axis(size):
    dx, dy, dz = size
    if dz >= dx and dz >= dy:
        return 2
    if dx >= dy and dx >= dz:
        return 0
    return 1


def corr(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx < 1e-12 or vy < 1e-12:
        return 0.0
    return cov / math.sqrt(vx * vy)


def main():
    bad = 0
    for name, size, rot in CASES:
        bm = bmesh.new()
        loc = Vector((10.0, -3.0, 1.0))
        faces = timber_box(bm, size=size, location=loc, rotation=rot,
                           mat_index=3, bevel_amount=0.012)
        bm.normal_update()
        uv = bm.loops.layers.uv.verify()
        lax = longest_axis(size)
        eul = Euler(rot, 'XYZ')
        # world long axis directly:
        basis = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))][lax]
        world_long = eul.to_matrix() @ basis
        worst = 1.0
        n_side = 0
        for f in faces:
            if abs(f.normal.dot(world_long)) > math.cos(math.radians(45)):
                continue  # end cap
            pts = [lp.vert.co for lp in f.loops]
            s = [p.dot(world_long) for p in pts]
            v = [lp[uv].uv[1] for lp in f.loops]
            c = abs(corr(s, v))
            worst = min(worst, c)
            n_side += 1
            if c < 0.9:
                bad += 1
                print(f"  {name}: face corr={c:.3f} (normal={tuple(round(x,2) for x in f.normal)})")
        print(f"{name:12s} side_faces={n_side:3d} worst_corr={worst:.4f}")
        bm.free()
    print("GRAIN:", "OK" if bad == 0 else f"FAILED ({bad} faces)")


if __name__ == "__main__":
    main()
