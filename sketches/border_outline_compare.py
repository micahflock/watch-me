#!/usr/bin/env python3
"""border_outline_compare.py -- a 1 px grey line along the OUTSIDE of the
two-worlds white field border (owner, 2026-10).

"Outside" = the chrome side: above the chord, up-left of the slant, beyond
the rim arcs, and inside the battery notch. The outline is the BorderComponent
path offset 1 px toward the chrome -- chord y-1, slant x-1, arcs r+1, notch
chord y+1, notch walls 1 px into the notch -- drawn in grey just BEFORE the
white border (so white wins wherever the two touch) and after the field mask.
That is 7 more drawLine paths (~50 calls), no new geometry types: it ports
straight into BorderComponent. Tuned against the reference: arc radius 97.0
(96.8 put 3 grey px INSIDE the field on the left arc -- the 4-degree segment
rounding), slant ending at (165, 14) (166, 13 made a 2x2 blob at the apex).

The check: REFERENCE is the pixel-exact ideal -- every chrome pixel sharing an
edge with a white border pixel -- and each geometric variant reports how many
pixels it MISSES (gaps) and how many it puts INSIDE the field (strays).

    python3 sketches/border_outline_compare.py
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
from device import (COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_WHITE, COLOR_BLACK,
                    COLOR_TRANSPARENT)
from north_compare import chrome_state
from twchrome import ChromeDc, F, rnd

W, H = device.W, device.H
CX, CY, R = F(107.5), F(90.7), F(95.8)


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


def reference():
    """Pixel-exact ideal: chrome pixels sharing an EDGE with the white border
    (4-adjacency; 8-adjacency doubles the line on every diagonal step)."""
    out = set()
    for x, y in WHITE:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if True:
                p = (x + dx, y + dy)
                if (0 <= p[0] < W and 0 <= p[1] < H and p not in WHITE
                        and not INSIDE[p[1]][p[0]]):
                    out.add(p)
    return out


REF = reference()


def arc(dc, r, a0, a1):
    """twchrome.Border.arc at radius r (same 4-degree segmentation)."""
    twchrome.Border.arc(dc, CX, CY, F(r), F(a0), F(a1))


class Outline:
    """The border path offset 1 px toward the chrome (geometric, portable)."""

    def __init__(self, color):
        self.color = color

    def render(self, dc, state):
        dc.setColor(self.color, COLOR_TRANSPARENT)
        dc.drawLine(15, 61, 133, 61)              # chord, 1 px up
        dc.drawLine(133, 61, 165, 14)             # slant, 1 px up-left
        arc(dc, 97.0, 36.5, 148.6)                # rim arcs ~r + 1 (ends
        arc(dc, 97.0, 211.4, 288.2)               #   run to the corners)
        dc.drawLine(71, 164, 144, 164)            # notch floor, 1 px down
        dc.drawLine(71, 164, 58, 173)             # notch walls, 1 px in
        dc.drawLine(144, 164, 157, 173)


class Exact:
    """The reference set itself, as pixels (what a perfect outline is)."""

    def __init__(self, color):
        self.color = color

    def render(self, dc, state):
        dc.setColor(self.color, COLOR_TRANSPARENT)
        for x, y in REF:
            dc.fillRectangle(x, y, 1, 1)


def score(layer):
    dc = ChromeDc()
    layer.render(dc, None)
    twchrome.Border().render(dc, None)            # white on top, as on-device
    px = dc.img.load()
    grey = {(x, y) for y in range(H) for x in range(W)
            if px[x, y] not in ((0, 0, 0), (255, 255, 255))}
    gaps = len(REF - grey)
    strays = sum(1 for x, y in grey if INSIDE[y][x])
    extra = len(grey - REF) - strays
    return gaps, strays, extra, dc.calls


OPTIONS = [
    ("none", None),
    ("dk gray (geom)", Outline(COLOR_DK_GRAY)),
    ("lt gray (geom)", Outline(COLOR_LT_GRAY)),
    ("dk gray (exact)", Exact(COLOR_DK_GRAY)),
]
COLS = [("active", "7:50"), ("active", "13:05"), ("heavy", "23:30")]
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4


def face(layer, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 1
    for i, c in enumerate(twchrome.v2_chrome()):
        if isinstance(c, twchrome.Border) and layer is not None:
            layer.render(dc, st)                   # grey under the white
        c.render(dc, st)
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
        cap = ""
        if layer is not None:
            gaps, strays, extra, calls = score(layer)
            cap = "gaps {} strays {} extra {} | {} calls".format(
                gaps, strays, extra, calls)
            print("{:16s} {}".format(label, cap))
        cells = []
        for prof, at in COLS:
            g, snap, t = groves[(prof, at)]
            cells.append((face(layer, g, snap, t)
                          .resize((W * 3, H * 3), Image.NEAREST), cap))
        rows.append((label, cells))
        g, snap, t = groves[("active", "7:50")]
        img = face(layer, g, snap, t)
        # three close-ups: chord/slant corner, slant top, battery notch
        crops = [img.crop((118, 48, 148, 70)), img.crop((150, 6, 178, 28)),
                 img.crop((140, 150, 170, 176)), img.crop((188, 66, 212, 90))]
        zoom.append((label, [(c.resize((c.width * 8, c.height * 8),
                                        Image.NEAREST), "") for c in crops]))
    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "border-outline-compare.png"),
          "two-worlds V2: 1 px grey line outside the white border")
    sheet(zoom, ["chord/slant corner", "slant top", "notch corner", "right rim"],
          os.path.join(OUT, "border-outline-zoom.png"),
          "grey outline close-ups (8x)")


if __name__ == "__main__":
    main()
