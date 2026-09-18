"""Generate the stylized heraldic banner texture (red field, shield + dragon).

Pure standard-library PNG writer + tiny polygon rasterizer so the asset can be
rebuilt without any third-party dependencies:

    python tools/make_banner_texture.py

Writes blend_building_creator/textures/banner_dragon_diffuse.png
"""

import math
import os
import struct
import zlib

SS = 2                      # supersample factor
W = 512                     # final size
S = W * SS                  # render size

_buf = bytearray(S * S * 3)


def _set(x, y, c):
    if 0 <= x < S and 0 <= y < S:
        i = (y * S + x) * 3
        _buf[i] = c[0]
        _buf[i + 1] = c[1]
        _buf[i + 2] = c[2]


def _get(x, y):
    i = (y * S + x) * 3
    return (_buf[i], _buf[i + 1], _buf[i + 2])


def fill_poly(pts, c):
    ys = [p[1] for p in pts]
    ymin = max(0, int(min(ys)))
    ymax = min(S - 1, int(max(ys)) + 1)
    n = len(pts)
    for y in range(ymin, ymax + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                t = (yc - y1) / (y2 - y1)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = int(math.ceil(xs[i] - 0.5))
            xb = int(math.floor(xs[i + 1] - 0.5))
            for x in range(max(0, xa), min(S - 1, xb) + 1):
                _set(x, y, c)


def fill_circle(cx, cy, r, c):
    x0, x1 = int(cx - r - 1), int(cx + r + 1)
    y0, y1 = int(cy - r - 1), int(cy + r + 1)
    r2 = r * r
    for y in range(max(0, y0), min(S - 1, y1) + 1):
        dy = y + 0.5 - cy
        for x in range(max(0, x0), min(S - 1, x1) + 1):
            dx = x + 0.5 - cx
            if dx * dx + dy * dy <= r2:
                _set(x, y, c)


def capsule(x1, y1, x2, y2, r, c):
    d = math.hypot(x2 - x1, y2 - y1)
    steps = max(1, int(d / max(1.0, r * 0.5)))
    for i in range(steps + 1):
        t = i / steps
        fill_circle(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, c)


def px(nx, ny):
    return nx * S, ny * S


def main():
    red_dark = (120, 16, 20)
    red = (176, 32, 34)
    red_hi = (198, 52, 48)
    gold = (232, 196, 104)
    gold_dark = (168, 126, 48)
    cream = (245, 232, 200)

    # --- Cloth field: vertical gradient + subtle weave --------------------
    for y in range(S):
        t = y / (S - 1)
        base = tuple(int(red_dark[i] + (red_hi[i] - red_dark[i]) * (1.0 - abs(t - 0.45) * 1.6)) for i in range(3))
        base = tuple(max(0, min(255, v)) for v in base)
        for x in range(S):
            n = ((x * 7 + y * 13) % 5) - 2
            _set(x, y, tuple(max(0, min(255, base[k] + n * 3)) for k in range(3)))

    # Weave lines.
    for y in range(0, S, 6):
        for x in range(S):
            c = _get(x, y)
            _set(x, y, tuple(max(0, c[k] - 12) for k in range(3)))
    for x in range(0, S, 6):
        for y in range(S):
            c = _get(x, y)
            _set(x, y, tuple(min(255, c[k] + 8) for k in range(3)))

    # --- Gold border frame ------------------------------------------------
    m = int(S * 0.045)
    t = int(S * 0.016)
    fill_poly([(m, m), (S - m, m), (S - m, m + t), (m, m + t)], gold)
    fill_poly([(m, S - m - t), (S - m, S - m - t), (S - m, S - m), (m, S - m)], gold)
    fill_poly([(m, m), (m + t, m), (m + t, S - m), (m, S - m)], gold)
    fill_poly([(S - m - t, m), (S - m, m), (S - m, S - m), (S - m - t, S - m)], gold)

    # --- Shield ------------------------------------------------------------
    cx, cy = 0.5 * S, 0.50 * S
    hw, hh = 0.30 * S, 0.36 * S
    top = cy - hh
    bot = cy + hh
    shoulder = cy + hh * 0.10

    def heater(inset):
        w = hw - inset
        sh = shoulder
        return [
            (cx - w, top + inset), (cx + w, top + inset),
            (cx + w, sh),
            (cx + w * 0.93, cy + hh * 0.52),
            (cx + w * 0.60, cy + hh * 0.80),
            (cx, bot - inset * 1.4),
            (cx - w * 0.60, cy + hh * 0.80),
            (cx - w * 0.93, cy + hh * 0.52),
            (cx - w, sh),
        ]

    fill_poly(heater(0.0), gold_dark)
    fill_poly(heater(t * 1.6), cream)

    # --- Dragon (red heraldic wyvern on the cream shield) -----------------
    g = gold_dark
    dr = red_dark
    # Head facing left, with snout and open lower jaw.
    fill_poly([
        (0.415 * S, 0.660 * S), (0.450 * S, 0.672 * S), (0.470 * S, 0.640 * S),
        (0.448 * S, 0.604 * S), (0.404 * S, 0.596 * S), (0.360 * S, 0.622 * S),
        (0.298 * S, 0.612 * S), (0.352 * S, 0.580 * S), (0.404 * S, 0.576 * S),
    ], dr)
    # Horn + eye.
    fill_poly([(0.450 * S, 0.672 * S), (0.462 * S, 0.716 * S), (0.486 * S, 0.668 * S)], g)
    fill_circle(0.398 * S, 0.636 * S, 0.013 * S, gold)
    # Neck and serpentine body.
    capsule(0.450 * S, 0.600 * S, 0.478 * S, 0.505 * S, 0.034 * S, dr)
    capsule(0.478 * S, 0.505 * S, 0.556 * S, 0.470 * S, 0.040 * S, dr)
    capsule(0.556 * S, 0.470 * S, 0.520 * S, 0.388 * S, 0.032 * S, dr)
    # Tail curling down with a spade tip.
    capsule(0.520 * S, 0.388 * S, 0.600 * S, 0.336 * S, 0.022 * S, dr)
    capsule(0.600 * S, 0.336 * S, 0.636 * S, 0.276 * S, 0.015 * S, dr)
    fill_poly([(0.636 * S, 0.276 * S), (0.664 * S, 0.230 * S),
               (0.676 * S, 0.286 * S), (0.646 * S, 0.296 * S)], g)
    # Raised wing.
    fill_poly([
        (0.480 * S, 0.512 * S), (0.602 * S, 0.432 * S), (0.668 * S, 0.520 * S),
        (0.590 * S, 0.500 * S), (0.566 * S, 0.560 * S),
    ], dr)
    fill_poly([(0.602 * S, 0.470 * S), (0.650 * S, 0.486 * S), (0.640 * S, 0.430 * S)], g)
    # Legs with feet.
    fill_poly([(0.470 * S, 0.442 * S), (0.436 * S, 0.352 * S), (0.470 * S, 0.346 * S),
               (0.486 * S, 0.392 * S)], dr)
    fill_poly([(0.436 * S, 0.352 * S), (0.414 * S, 0.340 * S), (0.470 * S, 0.336 * S)], g)
    fill_poly([(0.540 * S, 0.430 * S), (0.566 * S, 0.342 * S), (0.596 * S, 0.352 * S),
               (0.572 * S, 0.404 * S)], dr)
    fill_poly([(0.566 * S, 0.342 * S), (0.600 * S, 0.332 * S), (0.596 * S, 0.352 * S)], g)

    # --- Downsample (box filter) ------------------------------------------
    out = bytearray(W * W * 3)
    for y in range(W):
        for x in range(W):
            r = gg = b = 0
            for dy in range(SS):
                for dx in range(SS):
                    c = _get(x * SS + dx, y * SS + dy)
                    r += c[0]; gg += c[1]; b += c[2]
            n = SS * SS
            i = (y * W + x) * 3
            out[i] = r // n
            out[i + 1] = gg // n
            out[i + 2] = b // n

    # --- Write PNG --------------------------------------------------------
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    raw = b"".join(b"\x00" + bytes(out[y * W * 3:(y + 1) * W * 3]) for y in range(W))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, W, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "blend_building_creator", "textures", "banner_dragon_diffuse.png")
    with open(path, "wb") as fh:
        fh.write(png)
    print("WROTE", path, len(png), "bytes")


if __name__ == "__main__":
    main()
