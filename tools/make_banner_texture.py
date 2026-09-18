"""Generate the stylized heraldic banner texture with RGBA alpha transparency.

The banner silhouette is a classic swallowtail / heraldic pennant shape.
A stately heater-shield fills the upper 60% of the banner, with a large
gold-outlined wyvern dragon filling nearly the entire shield face.
Outside the silhouette alpha=0 (transparent).

    python tools/make_banner_texture.py
"""

import math, os, struct, zlib

SS = 2          # supersample factor
W  = 512        # output size
S  = W * SS     # render canvas: 1024x1024

_buf = bytearray(S * S * 4)


def _set(x, y, r, g, b, a=255):
    if 0 <= x < S and 0 <= y < S:
        i = (y * S + x) * 4
        _buf[i]   = max(0, min(255, int(r)))
        _buf[i+1] = max(0, min(255, int(g)))
        _buf[i+2] = max(0, min(255, int(b)))
        _buf[i+3] = max(0, min(255, int(a)))


def _get(x, y):
    if 0 <= x < S and 0 <= y < S:
        i = (y * S + x) * 4
        return _buf[i], _buf[i+1], _buf[i+2], _buf[i+3]
    return 0, 0, 0, 0


def fill_circle(cx, cy, r, c, a=255):
    x0, x1 = int(cx - r - 1), int(cx + r + 2)
    y0, y1 = int(cy - r - 1), int(cy + r + 2)
    r2 = r * r
    for y in range(max(0, y0), min(S, y1)):
        dy = y + 0.5 - cy
        for x in range(max(0, x0), min(S, x1)):
            if (x + 0.5 - cx)**2 + dy*dy <= r2:
                _set(x, y, c[0], c[1], c[2], a)


def capsule(x1, y1, x2, y2, r, c, a=255):
    d = math.hypot(x2-x1, y2-y1)
    steps = max(2, int(d / max(0.5, r*0.4)))
    for i in range(steps+1):
        t = i / steps
        fill_circle(x1+(x2-x1)*t, y1+(y2-y1)*t, r, c, a)


def fill_poly(pts, c, a=255):
    ys = [p[1] for p in pts]
    ymin, ymax = max(0, int(min(ys))), min(S-1, int(max(ys))+1)
    n = len(pts)
    for y in range(ymin, ymax+1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i+1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                t = (yc - y1) / (y2 - y1)
                xs.append(x1 + t*(x2-x1))
        xs.sort()
        for i in range(0, len(xs)-1, 2):
            xa = max(0, int(math.ceil(xs[i]-0.5)))
            xb = min(S-1, int(math.floor(xs[i+1]-0.5)))
            for x in range(xa, xb+1):
                _set(x, y, c[0], c[1], c[2], a)


def dist_to_segment(px, py, ax, ay, bx, by):
    abx, aby = bx-ax, by-ay
    ab2 = abx*abx + aby*aby
    if ab2 == 0:
        return math.hypot(px-ax, py-ay)
    t = max(0.0, min(1.0, ((px-ax)*abx + (py-ay)*aby) / ab2))
    return math.hypot(px - (ax + t*abx), py - (ay + t*aby))


def point_in_polygon(px, py, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i+1) % n]
        if (y1 <= py < y2) or (y2 <= py < y1):
            if px < (x2-x1)*(py-y1)/(y2-y1) + x1:
                inside = not inside
    return inside


def main():
    # Palette
    crimson_dk  = (100, 10, 14)
    crimson_hi  = (215, 48, 44)
    gold_shad   = ( 80, 52, 12)
    gold_dk     = (145, 98, 22)
    gold        = (225, 182, 60)
    gold_lt     = (252, 228, 130)
    cream       = (245, 235, 205)
    dr_dk       = ( 90, 12, 16)
    dr          = (160, 24, 28)
    dr_hi       = (210, 55, 45)
    bone        = (220, 205, 170)
    ochre       = (180, 130, 30)

    # 1. Banner silhouette polygon: swallowtail pennant
    top_y      = int(0.02 * S)
    shoulder_y = int(0.75 * S)
    tip_y      = int(0.97 * S)
    lx         = int(0.05 * S)
    rx         = int(0.95 * S)
    mx         = int(0.50 * S)

    banner_poly = [
        (lx, top_y), (rx, top_y), (rx, shoulder_y),
        (mx, tip_y), (lx, shoulder_y),
    ]
    banner_segs = [(banner_poly[i], banner_poly[(i+1) % len(banner_poly)])
                   for i in range(len(banner_poly))]
    t_bord = int(0.040 * S)

    # 2. Cloth field + golden border
    for y in range(top_y - 1, tip_y + 2):
        tv = y / S
        br = int(crimson_dk[0] + (crimson_hi[0] - crimson_dk[0]) * (1.0 - abs(tv - 0.40) * 1.8))
        bg = int(crimson_dk[1] + (crimson_hi[1] - crimson_dk[1]) * (1.0 - abs(tv - 0.40) * 1.8))
        bb = int(crimson_dk[2] + (crimson_hi[2] - crimson_dk[2]) * (1.0 - abs(tv - 0.40) * 1.8))
        for x in range(lx - 1, rx + 2):
            if not point_in_polygon(x + 0.5, y + 0.5, banner_poly):
                continue
            d = min(dist_to_segment(x+0.5, y+0.5, p0[0], p0[1], p1[0], p1[1])
                    for p0, p1 in banner_segs)
            if d < t_bord:
                f = d / t_bord
                if f < 0.06:
                    _set(x, y, gold_shad[0], gold_shad[1], gold_shad[2], 255)
                elif f < 0.22:
                    _set(x, y, gold_lt[0], gold_lt[1], gold_lt[2], 255)
                elif f < 0.68:
                    fac = (f - 0.22) / 0.46
                    col = tuple(int(gold[i]*(1-fac) + gold_dk[i]*fac) for i in range(3))
                    _set(x, y, col[0], col[1], col[2], 255)
                elif f < 0.82:
                    _set(x, y, gold_dk[0], gold_dk[1], gold_dk[2], 255)
                else:
                    _set(x, y, gold_lt[0], gold_lt[1], gold_lt[2], 255)
            else:
                noise = ((x * 7 + y * 13) % 5) - 2
                r2 = max(0, min(255, br + noise * 4))
                g2 = max(0, min(255, bg + noise))
                b2 = max(0, min(255, bb + noise))
                if y % 8 == 0:
                    r2, g2, b2 = max(0, r2-14), max(0, g2-4), max(0, b2-4)
                elif x % 8 == 0:
                    r2, g2, b2 = min(255, r2+10), min(255, g2+3), min(255, b2+3)
                _set(x, y, r2, g2, b2, 255)

    # 3. Heater shield
    scx, scy = 0.50 * S, 0.38 * S
    sw, sh_val = 0.31 * S, 0.34 * S

    def heater(inset):
        iw, ih = sw - inset, sh_val - inset
        top  = scy - ih
        side = scy + ih * 0.08
        return [
            (scx - iw, top),         (scx + iw, top),
            (scx + iw, side),
            (scx + iw*0.88, scy + ih*0.55),
            (scx + iw*0.50, scy + ih*0.88),
            (scx,           scy + ih + inset*0.8),
            (scx - iw*0.50, scy + ih*0.88),
            (scx - iw*0.88, scy + ih*0.55),
            (scx - iw,      side),
        ]

    fill_poly(heater(0.0),        gold_shad)
    fill_poly(heater(0.006 * S),  gold_lt)
    fill_poly(heater(0.013 * S),  gold_dk)
    fill_poly(heater(0.030 * S),  cream)

    # 4. Dragon Wyvern - large heraldic pose: head left, wings spread up, tail right
    def P(fx, fy):
        return (scx + fx * sw * 0.90, scy + fy * sh_val * 0.90)

    # Body core (thick torso)
    capsule(*P(-0.55, -0.35), *P(-0.10, -0.10), 0.055*S, dr)
    capsule(*P(-0.10, -0.10), *P( 0.30,  0.15), 0.060*S, dr_hi)
    capsule(*P( 0.30,  0.15), *P( 0.55,  0.35), 0.050*S, dr)
    # Belly highlight
    capsule(*P(-0.40, -0.20), *P( 0.38,  0.22), 0.022*S, dr_hi)

    # Head & skull
    fill_poly([
        P(-0.72, -0.60), P(-0.42, -0.70), P(-0.28, -0.52),
        P(-0.35, -0.32), P(-0.68, -0.28),
    ], dr)
    fill_poly([
        P(-0.72, -0.60), P(-0.45, -0.72), P(-0.32, -0.55), P(-0.48, -0.44),
    ], dr_hi)
    # Open jaw
    fill_poly([
        P(-0.73, -0.48), P(-0.48, -0.62), P(-0.32, -0.48),
        P(-0.44, -0.26), P(-0.74, -0.30),
    ], dr_dk)
    # Teeth
    for tx in (-0.62, -0.54, -0.46, -0.39):
        fill_poly([
            P(tx-0.03, -0.60), P(tx+0.03, -0.60),
            P(tx+0.02, -0.50), P(tx-0.02, -0.50),
        ], bone)
    # Eye
    fill_circle(*P(-0.56, -0.56), 0.030*S, gold_shad)
    fill_circle(*P(-0.56, -0.56), 0.020*S, gold_lt)
    fill_circle(*P(-0.56, -0.56), 0.009*S, dr_dk)
    # Horns
    fill_poly([P(-0.50, -0.72), P(-0.44, -0.94), P(-0.36, -0.90), P(-0.40, -0.70)], gold_dk)
    fill_poly([P(-0.36, -0.68), P(-0.30, -0.88), P(-0.22, -0.82), P(-0.28, -0.66)], gold_dk)

    # Neck
    capsule(*P(-0.52, -0.35), *P(-0.56, -0.50), 0.040*S, dr)
    for t in (0.25, 0.5, 0.75):
        nx = -0.52 + (-0.56 - -0.52)*t
        ny = -0.35 + (-0.50 - -0.35)*t
        fill_poly([P(nx-0.02, ny-0.04), P(nx+0.02, ny-0.04), P(nx, ny-0.10)], dr_hi)

    # Left wing (spread up-left)
    fill_poly([
        P(-0.20, -0.30), P(-0.62, -0.82), P(-0.82, -0.58),
        P(-0.78, -0.18), P(-0.55, -0.08), P(-0.35, 0.00), P(-0.15, -0.15),
    ], dr)
    fill_poly([
        P(-0.28, -0.25), P(-0.58, -0.70), P(-0.72, -0.52),
        P(-0.68, -0.20), P(-0.48, -0.12), P(-0.22, -0.18),
    ], dr_hi)
    for ef, et in [((-0.62,-0.82),(-0.82,-0.58)),((-0.62,-0.82),(-0.72,-0.20)),((-0.62,-0.82),(-0.55,-0.08))]:
        capsule(*P(*ef), *P(*et), 0.010*S, dr_dk)
    capsule(*P(-0.25,-0.22), *P(-0.55,-0.65), 0.007*S, ochre)
    capsule(*P(-0.25,-0.22), *P(-0.62,-0.40), 0.007*S, ochre)

    # Right wing (spread up-right)
    fill_poly([
        P(0.15,-0.25), P(0.22,-0.78), P(0.55,-0.85),
        P(0.82,-0.55), P(0.80,-0.15), P(0.60,0.05), P(0.35,0.08), P(0.12,-0.12),
    ], dr)
    fill_poly([
        P(0.18,-0.20), P(0.25,-0.68), P(0.52,-0.74),
        P(0.72,-0.50), P(0.70,-0.15), P(0.52,0.02), P(0.28,0.04), P(0.15,-0.10),
    ], dr_hi)
    for ef, et in [((0.22,-0.78),(0.55,-0.85)),((0.22,-0.78),(0.82,-0.35)),((0.22,-0.78),(0.60,0.05))]:
        capsule(*P(*ef), *P(*et), 0.010*S, dr_dk)
    capsule(*P(0.20,-0.18), *P(0.50,-0.60), 0.007*S, ochre)
    capsule(*P(0.20,-0.18), *P(0.65,-0.38), 0.007*S, ochre)

    # Front leg + claws
    capsule(*P(-0.18, 0.10), *P(-0.28, 0.55), 0.032*S, dr)
    capsule(*P(-0.28, 0.55), *P(-0.22, 0.80), 0.025*S, dr)
    for cxo in (-0.34, -0.22, -0.12):
        capsule(*P(-0.22, 0.80), *P(cxo, 0.92), 0.012*S, bone)

    # Back leg + claws
    capsule(*P(0.40, 0.18), *P(0.52, 0.65), 0.038*S, dr)
    capsule(*P(0.52, 0.65), *P(0.48, 0.88), 0.028*S, dr)
    for cxo in (0.38, 0.50, 0.62):
        capsule(*P(0.48, 0.88), *P(cxo, 1.00), 0.013*S, bone)

    # Tail + spade tip
    capsule(*P(0.60, 0.35), *P(0.82, 0.55), 0.025*S, dr)
    capsule(*P(0.82, 0.55), *P(0.92, 0.75), 0.016*S, dr)
    fill_poly([P(0.92,0.75), P(1.00,0.88), P(0.96,0.96), P(0.88,0.88), P(0.84,0.74)], gold_dk)

    # Spine ridge spikes
    for fx, fy in [(-0.35,-0.15),(-0.10,-0.05),(0.15,0.08),(0.38,0.22)]:
        fill_poly([P(fx-0.02, fy), P(fx+0.02, fy), P(fx, fy-0.14)], dr_hi)

    # 5. Downsample (2x2 box filter)
    out = bytearray(W * W * 4)
    for y in range(W):
        for x in range(W):
            R = G = B = A = 0
            for dy in range(SS):
                for dx in range(SS):
                    c = _get(x*SS+dx, y*SS+dy)
                    R += c[0]; G += c[1]; B += c[2]; A += c[3]
            n = SS * SS
            i = (y * W + x) * 4
            out[i] = R//n; out[i+1] = G//n; out[i+2] = B//n; out[i+3] = A//n

    # 6. Write RGBA PNG (color_type=6)
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    raw = b"".join(b"\x00" + bytes(out[y*W*4:(y+1)*W*4]) for y in range(W))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, W, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "blend_building_creator", "textures", "banner_dragon_diffuse.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    print(f"WROTE RGBA  {path}  ({len(png)} bytes)")


if __name__ == "__main__":
    main()

