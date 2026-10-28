#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the KENOZ launcher PNG icons (no external dependencies)."""
import math
import os
import struct
import zlib

BG_TOP = (23, 61, 99)
BG_BOTTOM = (11, 26, 42)
GOLD = (200, 166, 75)
GOLD_LIGHT = (232, 205, 138)

SS = 3  # supersampling


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def inside_rounded(x, y, size, radius):
    r = radius
    if x < r and y < r:
        return (x - r) ** 2 + (y - r) ** 2 <= r * r
    if x > size - r and y < r:
        return (x - (size - r)) ** 2 + (y - r) ** 2 <= r * r
    if x < r and y > size - r:
        return (x - r) ** 2 + (y - (size - r)) ** 2 <= r * r
    if x > size - r and y > size - r:
        return (x - (size - r)) ** 2 + (y - (size - r)) ** 2 <= r * r
    return True


def shade(px, py, size):
    """Colour of one sample point (float coords) or None for transparent."""
    if not inside_rounded(px, py, size, size * 0.22):
        return None
    t = py / size
    base = lerp(BG_TOP, BG_BOTTOM, t)
    # soft radial highlight behind the cross
    dx = (px - size * 0.5) / size
    dy = (py - size * 0.42) / size
    d = math.sqrt(dx * dx + dy * dy)
    glow = max(0.0, 1.0 - d * 2.1) ** 2 * 0.30
    base = lerp(base, (200, 166, 75), glow)

    cx = size * 0.5
    cy = size * 0.5
    arm_w = size * 0.135          # half width of the cross bars
    v_top, v_bot = size * 0.20, size * 0.80
    h_top, h_bot = size * 0.365, size * 0.505   # horizontal bar band
    vx0, vx1 = cx - arm_w, cx + arm_w

    if (vx0 <= px <= vx1 and v_top <= py <= v_bot) or \
       (size * 0.225 <= px <= size * 0.775 and h_top <= py <= h_bot):
        t = (py - v_top) / max(1e-6, (v_bot - v_top))
        return lerp(GOLD_LIGHT, GOLD, min(1.0, max(0.0, t)))
    return base


def render(size):
    out = bytearray()
    radius = size * 0.22
    for y in range(size):
        out.append(0)  # filter type 0
        for x in range(size):
            r = g = b = a = 0
            for sy in range(SS):
                for sx in range(SS):
                    px = x + (sx + 0.5) / SS
                    py = y + (sy + 0.5) / SS
                    c = shade(px, py, size)
                    if c:
                        r += c[0]; g += c[1]; b += c[2]; a += 255
            n = SS * SS
            if a:
                out += bytes((r // n, g // n, b // n, a // n))
            else:
                out += b'\x00\x00\x00\x00'
    return bytes(out)


def png(size, path):
    raw = render(size)
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png_data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
                chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png_data)
    return len(png_data)


def main():
    root = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'res')
    sizes = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
    for dpi, size in sizes.items():
        folder = os.path.join(root, 'mipmap-' + dpi)
        os.makedirs(folder, exist_ok=True)
        n = png(size, os.path.join(folder, 'ic_launcher.png'))
        png(size, os.path.join(folder, 'ic_launcher_round.png'))
        print(f'{dpi}: {size}x{size} ({n} bytes)')


if __name__ == '__main__':
    main()
