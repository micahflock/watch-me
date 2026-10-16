#!/usr/bin/env python3
"""halftone_compare.py -- halftone texture options for two-worlds V2 (owner, 2026-10).

Halftone is the native idiom of a 14-colour MIP panel: tone by DOT SIZE on a
45-degree lattice, never by blending. Every option here is a static dot field
(positions + sizes depend only on the fixed chrome geometry), so on the watch
it can be baked once in onLayout or shipped as a bitmap -- the per-frame cost
is the blit, not the geometry. Captions give the dot count; drawn per-dot
from a packed array that is roughly 10-15 VM instructions per dot.

Dot sizes on the device model: 1 = single px (fillRectangle 1x1),
2 = plus (fillCircle r=1), 3 = disc (fillCircle r=2).

Options (rows):
  none            the shipped face
  dish: vignette  agar-plate edge -- DK_GRAY dots grow toward the dish wall,
                  under the moss (the moss covers them as it grows)
  dish: screen    a uniform fine 1 px screen tone over the whole dish
  dish: raking    light from the top-left: dots grow toward the lower right
  chrome: plate   the chrome (outside the dish) as a printed plate: uniform
                  1 px DK_GRAY tone behind the clock, bars and battery
  chrome: bevel   a halftone shadow band hugging the OUTSIDE of the white
                  border, dots shrinking away from it: the chrome looks raised,
                  the dish recessed
  both: bevel+vig the bevel plus the dish vignette (shadow on both sides of
                  the glass wall)
  chrome: blue    the plate tone in DK_BLUE (picks up the moss rim)

    python3 sketches/halftone_compare.py
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
from device import COLOR_DK_GRAY, COLOR_DK_BLUE, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc

SCALE = 3
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4
FCX, FCY, FR = 107.5, 90.7, 95.8        # the dish rim circle (Border.arc)
W, H = device.W, device.H


# ---------------------------------------------------------------- geometry --

def field_mask():
    """inside[y][x]: True on the dish (not under a FieldMask run)."""
    fm = twchrome.FieldMask()
    inside = [[True] * W for _ in range(H)]
    cx, cw = [0] * 4, [0] * 4
    for y in range(H):
        n = fm.scanline(y, cx, cw)
        for c in range(n):
            for x in range(cx[c], cx[c] + cw[c]):
                inside[y][x] = False
    return inside


INSIDE = field_mask()


def on_glass(x, y):
    return twchrome.visible(x, y)


def dist_to(x, y, want, rmax):
    """Distance from (x, y) to the nearest pixel whose INSIDE == want."""
    best = rmax + 1
    for dy in range(-rmax, rmax + 1):
        yy = y + dy
        if yy < 0 or yy >= H:
            continue
        for dx in range(-rmax, rmax + 1):
            xx = x + dx
            if 0 <= xx < W and INSIDE[yy][xx] == want:
                d = math.hypot(dx, dy)
                if d < best:
                    best = d
    return best


def lattice(pitch):
    """45-degree halftone lattice: rows pitch/2 apart, alternate rows shifted
    half a pitch."""
    s = pitch // 2
    for k in range(H // s + 1):
        y = k * s
        if y >= H:
            break
        x0 = (pitch // 2) if (k & 1) else 0
        for x in range(x0, W, pitch):
            yield x, y


def size_for(t, cap=3):
    """tone 0..1 -> dot size 0 (none) .. cap (3 = disc). On the 6 px lattice
    (18 px per dot cell) a 1 px dot is ~6% ink, a plus ~28%, a disc ~100% --
    discs merge into a solid band, so the soft options cap at the plus."""
    if t < 0.15:
        return 0
    if cap == 2:
        return 1 if t < 0.55 else 2
    if t < 0.40:
        return 1
    if t < 0.70:
        return 2
    return 3


# ------------------------------------------------------------- dot fields --

def dots_dish_vignette():
    out = []
    for x, y in lattice(6):
        if not INSIDE[y][x]:
            continue
        r = math.hypot(x - FCX, y - FCY) / FR    # 0 centre .. 1 the wall
        out.append((x, y, size_for((r - 0.68) / 0.32, cap=2)))
    return out


def dots_dish_screen():
    return [(x, y, 1) for x, y in lattice(4) if INSIDE[y][x]]


def dots_dish_raking():
    out = []
    for x, y in lattice(6):
        if not INSIDE[y][x]:
            continue
        # tone along the top-left -> bottom-right diagonal of the dish
        u = ((x - FCX) + (y - FCY)) / (FR * 1.414)   # -1 .. 1
        out.append((x, y, size_for((u - 0.15) / 0.85, cap=2)))
    return out


def dots_chrome_plate():
    return [(x, y, 1) for x, y in lattice(4)
            if not INSIDE[y][x] and on_glass(x, y)]


def dots_chrome_bevel():
    out = []
    for x, y in lattice(6):
        if INSIDE[y][x] or not on_glass(x, y):
            continue
        d = dist_to(x, y, True, 12)               # px out from the dish
        if d <= 2.5:
            continue                              # keep the white line clean
        out.append((x, y, size_for(1.0 - (d - 3) / 9.0, cap=2)))
    return out


class Halftone:
    """A static dot field drawn in one colour (duck-typed component)."""

    def __init__(self, dots, color=COLOR_DK_GRAY):
        self.dots = [d for d in dots if d[2] > 0]
        self.color = color

    def render(self, dc, state):
        dc.setColor(self.color, COLOR_TRANSPARENT)
        for x, y, s in self.dots:
            if s == 1:
                dc.fillRectangle(x, y, 1, 1)
            else:
                dc.fillCircle(x, y, s - 1)


# (label, dish layer or None, chrome layer or None)
OPTIONS = [
    ("none", None, None),
    ("dish: vignette", Halftone(dots_dish_vignette()), None),
    ("dish: screen", Halftone(dots_dish_screen()), None),
    ("dish: raking", Halftone(dots_dish_raking()), None),
    ("chrome: plate", None, Halftone(dots_chrome_plate())),
    ("chrome: bevel", None, Halftone(dots_chrome_bevel())),
    ("both: bevel+vig", Halftone(dots_dish_vignette()),
     Halftone(dots_chrome_bevel())),
    ("chrome: blue", None, Halftone(dots_chrome_plate(), COLOR_DK_BLUE)),
]
COLS = [("active", "7:50"), ("active", "13:05"), ("heavy", "23:30")]
ZOOM = 4


def face(dish, chrome, grove, snap, t):
    dc = ChromeDc()
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    if dish is not None:
        dish.render(dc, st)
    grove.render(dc, snap)
    layers = twchrome.v2_chrome()
    for i, c in enumerate(layers):
        c.render(dc, st)
        if i == 0 and chrome is not None:     # right after the field mask,
            chrome.render(dc, st)             # under the border + readouts
    return twchrome.glass(dc.img)


def grove_at(snaps, t):
    g = load_algo("moss_grove").build()["components"][0]
    for m in range(t + 1):
        g.advance(snaps[m])
    return g


def main():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    groves = {}
    for prof, at in COLS:
        t = mins(at)
        groves[(prof, at)] = (grove_at(days[prof], t), days[prof][t], t)

    rows = []
    zooms = []
    for label, dish, chrome in OPTIONS:
        n = sum(len(l.dots) for l in (dish, chrome) if l is not None)
        cells = []
        for prof, at in COLS:
            g, snap, t = groves[(prof, at)]
            img = face(dish, chrome, g, snap, t)
            cells.append((img.resize((W * SCALE, H * SCALE), Image.NEAREST),
                          "{} dots".format(n)))
        rows.append((label, cells))
        g, snap, t = groves[("active", "7:50")]
        zooms.append((face(dish, chrome, g, snap, t)
                      .resize((W * ZOOM, H * ZOOM), Image.NEAREST), label))

    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "halftone-compare.png"),
          "two-worlds V2: halftone texture options (dish / chrome)")
    # close-ups: the 7:50 face (most dish showing) at 4x, two per row
    zr = []
    for i in range(0, len(zooms), 2):
        pair = zooms[i:i + 2]
        zr.append((" / ".join(l for _, l in pair),
                   [(img, l) for img, l in pair]))
    sheet(zr, ["", ""], os.path.join(OUT, "halftone-compare-zoom.png"),
          "halftone options at 7:50, 4x")


if __name__ == "__main__":
    main()
