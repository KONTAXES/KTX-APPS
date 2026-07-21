# -*- coding: utf-8 -*-
"""Generate static/description/icon.png and banner.png with no external libs.

Dev utility (not loaded by Odoo, not web-served). Pure-Python PNG encoder
(zlib + RGBA) with supersampling for smooth edges. Run to (re)generate assets:

    python3 ktx_claude_ai/doc/gen_assets.py
"""
import math
import os
import struct
import zlib

ASSETS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "static", "description"
)

INDIGO = (79, 70, 229)
VIOLET = (124, 58, 237)
ACCENT = (199, 210, 254)


def write_png(path, w, h, buf):
    def chunk(typ, data):
        return (
            struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(out)


def lerp(a, b, t):
    return a + (b - a) * t


def star_polygon(cx, cy, outer, inner, points=4, rot=0.0):
    verts = []
    for i in range(points * 2):
        ang = rot + math.pi * i / points - math.pi / 2
        r = outer if i % 2 == 0 else inner
        verts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return verts, (min(xs), min(ys), max(xs), max(ys))


def in_poly(x, y, verts, bbox):
    if x < bbox[0] or x > bbox[2] or y < bbox[1] or y > bbox[3]:
        return False
    inside = False
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def in_rounded(x, y, x0, y0, w, h, r):
    if not (x0 <= x <= x0 + w and y0 <= y <= y0 + h):
        return False
    cx = min(max(x, x0 + r), x0 + w - r)
    cy = min(max(y, y0 + r), y0 + h - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def downsample(buf, hw, hh, ss):
    w, h = hw // ss, hh // ss
    out = bytearray(w * h * 4)
    area = ss * ss
    for y in range(h):
        for x in range(w):
            r = g = b = a = 0
            for dy in range(ss):
                row = ((y * ss + dy) * hw + x * ss) * 4
                for dx in range(ss):
                    j = row + dx * 4
                    r += buf[j]; g += buf[j + 1]; b += buf[j + 2]; a += buf[j + 3]
            o = (y * w + x) * 4
            out[o] = r // area
            out[o + 1] = g // area
            out[o + 2] = b // area
            out[o + 3] = a // area
    return out


def render_icon():
    w = h = 140
    ss = 4
    hw, hh = w * ss, h * ss
    buf = bytearray(hw * hh * 4)
    rad = hw * 0.18
    star, sb = star_polygon(hw / 2, hh / 2, hw * 0.31, hw * 0.115, 4)
    star2, sb2 = star_polygon(hw * 0.74, hh * 0.28, hw * 0.085, hw * 0.032, 4)
    for y in range(hh):
        t = y / (hh - 1)
        bg = (
            int(lerp(INDIGO[0], VIOLET[0], t)),
            int(lerp(INDIGO[1], VIOLET[1], t)),
            int(lerp(INDIGO[2], VIOLET[2], t)),
        )
        for x in range(hw):
            i = (y * hw + x) * 4
            if not in_rounded(x, y, 0, 0, hw - 1, hh - 1, rad):
                buf[i:i + 4] = bytes((bg[0], bg[1], bg[2], 0))
                continue
            r, g, b = bg
            if in_poly(x, y, star, sb):
                r, g, b = 255, 255, 255
            elif in_poly(x, y, star2, sb2):
                r, g, b = ACCENT
            buf[i:i + 4] = bytes((r, g, b, 255))
    write_png(os.path.join(ASSETS, "icon.png"), w, h, downsample(buf, hw, hh, ss))


def render_banner():
    w, h = 1200, 340
    ss = 2
    hw, hh = w * ss, h * ss
    buf = bytearray(hw * hh * 4)
    big, bb = star_polygon(hw * 0.82, hh * 0.5, hh * 0.62, hh * 0.24, 4)
    sm, sbb = star_polygon(hw * 0.92, hh * 0.24, hh * 0.12, hh * 0.045, 4)
    bubbles = [
        (hw * 0.06, hh * 0.30, hw * 0.34, hh * 0.14, hh * 0.07),
        (hw * 0.11, hh * 0.54, hw * 0.28, hh * 0.14, hh * 0.07),
    ]
    for y in range(hh):
        for x in range(hw):
            t = x / (hw - 1)
            r = int(lerp(INDIGO[0], VIOLET[0], t))
            g = int(lerp(INDIGO[1], VIOLET[1], t))
            b = int(lerp(INDIGO[2], VIOLET[2], t))
            if in_poly(x, y, big, bb):
                r = min(255, r + 95); g = min(255, g + 95); b = min(255, b + 115)
            elif in_poly(x, y, sm, sbb):
                r = min(255, r + 130); g = min(255, g + 130); b = min(255, b + 150)
            else:
                for bx, by, bw, bh, br in bubbles:
                    if in_rounded(x, y, bx, by, bw, bh, br):
                        r = int(r * 0.76 + 255 * 0.24)
                        g = int(g * 0.76 + 255 * 0.24)
                        b = int(b * 0.76 + 255 * 0.24)
                        break
            o = (y * hw + x) * 4
            buf[o:o + 4] = bytes((r, g, b, 255))
    write_png(os.path.join(ASSETS, "banner.png"), w, h, downsample(buf, hw, hh, ss))


if __name__ == "__main__":
    render_icon()
    print("icon.png OK")
    render_banner()
    print("banner.png OK")
