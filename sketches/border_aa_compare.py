#!/usr/bin/env python3
"""border_aa_compare.py -- anti-alias the two-worlds white field border with
grey pixels (owner, 2026-10).

The panel has no alpha, so anti-aliasing means painting the pixels the IDEAL
line only partly covers in a grey: DK_GRAY (0x555555 ~ 1/3) and, for a
two-level ramp, LT_GRAY (0xAAAAAA ~ 2/3). Coverage of a 1 px-wide line is
taken as c = 1 - d, d = distance from the pixel centre to the ideal path:
the true r = 95.8 circle about (107.5, 90.7) for the rim arcs (not their
4-degree chords) and the true segments for the chord, slant and notch.
White pixels stay white; the exact horizontal edges (chord, notch floor)
get no grey because every neighbour is a whole pixel away.

Pixel centres sit on integer coordinates (drawLine lights the integer points
it passes), matching how BorderComponent rounds its vertices.

The grey pixels never change, so on the watch they are a static list drawn
after the border (fillRectangle 1x1 each, or merged into short runs);
captions give both counts.

    python3 sketches/border_aa_compare.py
"""
import math
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import OUT, load_algo, mins, sheet
from day import synthetic_day
from device import COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc

W, H = device.W, device.H
CX, CY, R = 107.5, 90.7, 95.8
SEGS = [((16, 62), (134, 62)), ((134, 62), (166, 15)),
        ((70, 163), (145, 163)), ((70, 163), (57, 172)),
        ((145, 163), (158, 172))]
ARCS = [(37.7, 148.0), (212.0, 287.4)]     # bearings, 0 = 12 o'clock, CW


def field_mask():
    fm = twchrome.FieldMask()
    inside = [[True] * W for _ in range(H)]
    cx, cw = [0] * 4, [0] * 4
    for y in range(H):
        for c in range(fm.scanline(y, cx, cw)):
            for x in range(cx[c], cx[c] + cw[c]):
                inside[y][x] = False
    return inside


INSIDE = field_mask()


def white_pixels():
    dc = ChromeDc()
    twchrome.Border().render(dc, None)
    px = dc.img.load()
    return {(x, y) for y in range(H) for x in range(W)
            if px[x, y] == (255, 255, 255)}


WHITE = white_pixels()


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def arc_dist(px, py, b0, b1):
    b = math.degrees(math.atan2(px - CX, -(py - CY))) % 360.0
    if b0 <= b <= b1:
        return abs(math.hypot(px - CX, py - CY) - R)
    ends = []
    for e in (b0, b1):
        r = math.radians(e)
        ends.append(math.hypot(px - (CX + R * math.sin(r)),
                               py - (CY - R * math.cos(r))))
    return min(ends)


def coverage():
    """{(x, y): c} for every non-white pixel the ideal path partly covers."""
    out = {}
    for y in range(H):
        for x in range(W):
            if (x, y) in WHITE:
                continue
            d = min([seg_dist(x, y, a, b) for a, b in SEGS]
                    + [arc_dist(x, y, b0, b1) for b0, b1 in ARCS])
            if d < 1.0:
                out[(x, y)] = 1.0 - d
    return out


COV = coverage()


def runs(pixels):
    """Merge pixels into horizontal runs -> number of fillRectangle calls."""
    n = 0
    for x, y in pixels:
        if (x - 1, y) not in pixels:
            n += 1
    return n


class AA:
    """Static grey pixels: DK_GRAY where lo <= c < hi, LT_GRAY where c >= hi
    (hi = None: one level, everything >= lo is DK_GRAY). side: 'both' or
    'chrome' (skip pixels inside the dish, never over the moss)."""

    def __init__(self, lo, hi=None, side="both"):
        self.dk, self.lt = set(), set()
        for (x, y), c in COV.items():
            if side == "chrome" and INSIDE[y][x]:
                continue
            if c < lo:
                continue
            if hi is not None and c >= hi:
                self.lt.add((x, y))
            else:
                self.dk.add((x, y))

    def render(self, dc, state):
        for col, pix in ((COLOR_DK_GRAY, self.dk), (COLOR_LT_GRAY, self.lt)):
            if pix:
                dc.setColor(col, COLOR_TRANSPARENT)
                for x, y in pix:
                    dc.fillRectangle(x, y, 1, 1)

    def caption(self):
        n = len(self.dk) + len(self.lt)
        return "{} px, {} runs".format(n, runs(self.dk) + runs(self.lt))


OPTIONS = [
    ("none", None),
    ("dk, chrome side", AA(0.30, side="chrome")),
    ("dk, both sides", AA(0.30)),
    ("dk, both, light", AA(0.42)),
    ("dk+lt ramp", AA(0.25, 0.55)),
]
COLS = [("active", "7:50"), ("active", "13:05"), ("heavy", "23:30")]
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4
CROPS = [((140, 20, 172, 52), "slant"), ((178, 100, 210, 132), "right rim"),
         ((14, 120, 46, 152), "left rim"), ((140, 150, 172, 176), "notch corner")]
ZOOM = 10


def face(layer, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 1
    for c in twchrome.v2_chrome():
        c.render(dc, st)
        if isinstance(c, twchrome.Border) and layer is not None:
            layer.render(dc, st)               # right after the white
    return twchrome.glass(dc.img)


def main():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    groves = {}
    for prof, at in COLS:
        t = mins(at)
        g = load_algo("moss_grove").build()["components"][0]
        for m in range(t + 1):
            g.advance(days[prof][m])
        groves[(prof, at)] = (g, days[prof][t], t)

    rows, zoom = [], []
    for label, layer in OPTIONS:
        cap = layer.caption() if layer is not None else ""
        if cap:
            print("{:18s} {}".format(label, cap))
        cells = []
        for prof, at in COLS:
            g, snap, t = groves[(prof, at)]
            cells.append((face(layer, g, snap, t)
                          .resize((W * 3, H * 3), Image.NEAREST), cap))
        rows.append((label, cells))
        g, snap, t = groves[("active", "7:50")]
        img = face(layer, g, snap, t)
        zc = []
        for box, _ in CROPS:
            c = img.crop(box)
            zc.append((c.resize((c.width * ZOOM, c.height * ZOOM),
                                Image.NEAREST), ""))
        zoom.append((label, zc))
    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "border-aa-compare.png"),
          "two-worlds V2: grey anti-aliasing on the white border")
    # the crops differ in width; give each its own sheet column by padding
    wmax = max(c[0].width for r in zoom for c in r[1])
    hmax = max(c[0].height for r in zoom for c in r[1])
    padded = []
    for label, cells in zoom:
        pc = []
        for img, cap in cells:
            canvas = Image.new("RGB", (wmax, hmax), (24, 24, 24))
            canvas.paste(img, (0, 0))
            pc.append((canvas, cap))
        padded.append((label, pc))
    sheet(padded, [n for _, n in CROPS],
          os.path.join(OUT, "border-aa-zoom.png"),
          "anti-aliasing close-ups at 7:50 (10x)")


if __name__ == "__main__":
    main()
