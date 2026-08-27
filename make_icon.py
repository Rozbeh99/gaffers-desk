# -*- coding: utf-8 -*-
"""Draws the app icon at any size, with no image library.

Two consumers:
  * template.html gets the 180px version inlined as a base64 data URI, because
    the artifact's CSP blocks other hosts and this account has no asset store -
    without it iOS puts a shrunken screenshot of the page on the home screen.
  * the hosted site gets real PNG files, which is what a web manifest needs.

A pitch: dark ground, touchline, halfway line, centre circle, in the dashboard's
accent green. Written with zlib and struct rather than pulling in Pillow, since
every other script here is stdlib only.
"""
import base64
import io
import os
import re
import struct
import sys
import zlib

sys.stdout.reconfigure(encoding='utf-8')

GROUND = (10, 18, 15)        # --ground, dark theme
ACCENT = (53, 201, 138)      # --accent, dark theme
TURF = (15, 30, 23)          # --turf-a, dark theme


def _blend(bg, fg, a):
    return tuple(int(round(bg[i] * (1 - a) + fg[i] * a)) for i in range(3))


def render(size):
    """Return the icon as PNG bytes at `size` x `size`."""
    s = float(size)
    stroke = max(2.0, s * 0.017)
    inset = s * 0.122          # the edge iOS rounds away
    radius = s * 0.056
    c = (size - 1) / 2.0
    half = s / 2.0 - inset

    px = [[GROUND] * size for _ in range(size)]

    def cover(dist, edge):
        return max(0.0, min(1.0, (stroke / 2.0 + 0.5) - abs(dist - edge)))

    for y in range(size):
        row = px[y] = list(px[y])
        dy = y - c
        for x in range(size):
            dx = x - c
            rx, ry = abs(dx) - (half - radius), abs(dy) - (half - radius)
            inside = abs(dx) <= half and abs(dy) <= half and (
                not (rx > 0 and ry > 0) or (rx * rx + ry * ry) ** 0.5 <= radius)
            if inside:
                row[x] = TURF

            # touchline, following the rounded corners
            if rx > 0 and ry > 0:
                a = cover((rx * rx + ry * ry) ** 0.5, radius)
            else:
                a = cover(max(abs(dx) - (half - radius), abs(dy) - (half - radius)), radius)

            if inside:
                a = max(a, cover(abs(dx), 0))                      # halfway line
            a = max(a, cover((dx * dx + dy * dy) ** 0.5, half * 0.42))  # centre circle
            if (dx * dx + dy * dy) ** 0.5 < s * 0.022:                  # centre spot
                a = 1.0

            if a > 0:
                row[x] = _blend(row[x], ACCENT, min(a, 1.0))

    raw = b''.join(b'\x00' + bytes(v for p in row for v in p) for row in px)

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data +
                struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def write_files(outdir, sizes=(180, 192, 512)):
    os.makedirs(outdir, exist_ok=True)
    written = []
    for n in sizes:
        path = os.path.join(outdir, f'icon-{n}.png')
        with open(path, 'wb') as f:
            f.write(render(n))
        written.append((n, os.path.getsize(path)))
    return written


def embed_in_template(path='template.html'):
    uri = 'data:image/png;base64,' + base64.b64encode(render(180)).decode('ascii')
    html = io.open(path, encoding='utf-8').read()
    tags = (f'<link rel="apple-touch-icon" href="{uri}">\n'
            f'<link rel="icon" type="image/png" href="{uri}">\n')
    html = re.sub(r'<link rel="apple-touch-icon"[^>]*>\n?', '', html)
    html = re.sub(r'<link rel="icon" type="image/png"[^>]*>\n?', '', html)
    anchor = '<link rel="preconnect" href="https://fonts.googleapis.com">'
    assert anchor in html, 'preconnect anchor missing from template'
    io.open(path, 'w', encoding='utf-8').write(html.replace(anchor, tags + anchor, 1))
    return len(uri)


if __name__ == '__main__':
    with open('icon.png', 'wb') as f:
        f.write(render(180))
    n = embed_in_template()
    print(f"icon.png written; {n:,} chars embedded in template.html")
