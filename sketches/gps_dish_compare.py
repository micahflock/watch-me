#!/usr/bin/env python3
"""gps_dish_compare.py -- GPS-freshness icon options: the "cross-section"
satellite dish (owner, 2026-10).

The shipped GpsComponent is a 9 px ring at (75, 16) left of the day-of-week:
DK_GRAY = no fix, YELLOW = stale fix (> 24 h), BLUE = fresh (< 24 h), with a
centre dot when there is a fix (Snapshot.gpsFix 0/1/2). Each option here keeps
that colour code and adds the dish motif; most also double-encode freshness in
the signal (fresh = two marks, stale = one, none = bare gray dish) so the
state reads at a glance even without colour.

Icons use only drawLine / fillCircle / fillRectangle / fillPolygon (convex)
with explicit integer points -- no drawArc, whose rasterization only the SDK
sim gets right (the chrome Border draws its arcs as lines for the same
reason) -- so they port mechanically and render the same on the watch. The
box must end at x <= 80 (the day-of-week starts at 82) and y <= 23 (the clock
digits start at 26).

  current     the shipped ring + dot
  A tilted    a filled half-disc dish facing up-right (the emoji pose),
              centre arm to a 2x2 feed, plinth, waves (1 stale / 2 fresh)
  B truss     A with the cross-section feed truss: struts from both rims
              to the feed instead of the centre arm
  C telescope an upright filled bowl (radio-telescope pose), mast to the
              feed, waves stacked above
  D rays      C with the textbook diagram's incoming rays falling into the
              bowl and reflecting to the feed (a GPS only receives),
              1 ray stale / 2 fresh
  E mini      a small A in the current pip's ~9 x 9 box; colour only

Earlier passes (2026-10): LINE-ART dishes do not survive 15 px -- a thin
parabola read as a hockey stick / anchor, a focus dot on a diagonal arm as
an arrowhead, and a 2 px shell + strut truss as a blob or an onion. Only
the filled (convex fillPolygon) dish read as a dish, so every option here
is built on it.

    python3 sketches/gps_dish_compare.py
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
from device import (COLOR_BLUE, COLOR_YELLOW, COLOR_DK_GRAY,
                    COLOR_TRANSPARENT)
from north_compare import chrome_state
from twchrome import ChromeDc

STATE_COLOR = {0: COLOR_DK_GRAY, 1: COLOR_YELLOW, 2: COLOR_BLUE}
STATE_NAME = {0: "no fix", 1: "stale", 2: "fresh"}


def arc_pts(cx, cy, r, a0, a1, n):
    """Integer polyline approximating an arc (math degrees, y up)."""
    out = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append((round(cx + r * math.cos(a)), round(cy - r * math.sin(a))))
    return out


def poly(dc, ox, oy, pts):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dc.drawLine(ox + x0, oy + y0, ox + x1, oy + y1)


# Each design: draw(dc, g) with g = gpsFix; ox/oy = box origin on screen.

class Current:
    calls = 0

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.drawCircle(75, 16, 4)
        if g in (1, 2):
            dc.fillCircle(75, 16, 1)


def dish_geom(vx, vy, phi, R, f, feed_v, n=8):
    """A parabola cross-section v = u^2 / 4f about vertex (vx, vy), its axis at
    math angle phi (90 = facing up, 45 = up-right). Returns (curve points,
    rim ends, feed point, axis unit)."""
    a = math.radians(phi)
    ax, ay = math.cos(a), -math.sin(a)        # axis (screen coords)
    rx, ry = math.sin(a), math.cos(a)         # rim direction (perpendicular)

    def at(u, v):
        return (vx + u * rx + v * ax, vy + u * ry + v * ay)

    pts = []
    for i in range(n + 1):
        u = -R + 2 * R * i / n
        x, y = at(u, u * u / (4 * f))
        p = (round(x), round(y))
        if not pts or pts[-1] != p:
            pts.append(p)
    rim = (pts[0], pts[-1])
    fx, fy = at(0, feed_v)
    return pts, rim, (round(fx), round(fy)), (ax, ay)


def lines(dc, pts):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dc.drawLine(x0, y0, x1, y1)


def thick(dc, pts, axis):
    """The dish shell 2 px thick: the curve plus a copy 1 px behind it."""
    lines(dc, pts)
    bx, by = -axis[0], -axis[1]
    lines(dc, [(round(x + bx), round(y + by)) for x, y in pts])


def wave(cx, cy, r, a0, a1, n):
    return arc_pts(cx, cy, r, a0, a1, n)


def waves(dc, fx, fy, g, a0, a1, r1=3, r2=5):
    """Freshness in the signal: 1 wave stale, 2 fresh."""
    if g >= 1:
        lines(dc, arc_pts(fx, fy, r1, a0, a1, 3))
    if g >= 2:
        lines(dc, arc_pts(fx, fy, r2, a0, a1, 4))


TILT_DISC = arc_pts(69, 17, 5, 135, 315, 6)   # down-left half; faces up-right
BOWL = [(round(72 + 6 * math.cos(math.radians(t))),
         round(18 + 4 * math.sin(math.radians(t)))) for t in range(0, 181, 30)]


class Tilted:
    """A: filled half-disc dish facing up-right (the emoji pose), centre arm
    to a 2x2 feed, plinth, waves."""

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(TILT_DISC)
        dc.drawLine(69, 17, 74, 12)
        dc.fillRectangle(74, 11, 2, 2)
        dc.fillRectangle(65, 22, 5, 1)
        waves(dc, 75, 12, g, 100, -10)


class Truss:
    """B: the same dish with the cross-section feed truss -- struts from both
    rims to the feed instead of a centre arm."""

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(TILT_DISC)
        dc.drawLine(TILT_DISC[0][0], TILT_DISC[0][1], 75, 12)
        dc.drawLine(TILT_DISC[-1][0], TILT_DISC[-1][1], 75, 12)
        dc.fillRectangle(74, 11, 2, 2)
        dc.fillRectangle(65, 22, 5, 1)
        waves(dc, 75, 12, g, 100, -10)


class Telescope:
    """C: an upright filled bowl (radio-telescope pose), mast to the feed,
    waves stacked above."""

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(BOWL)
        dc.drawLine(72, 18, 72, 13)
        dc.fillRectangle(71, 12, 3, 1)
        waves(dc, 72, 12, g, 40, 140)


class Rays:
    """D: the upright bowl with the textbook diagram's incoming rays -- they
    fall parallel into the bowl and reflect to the feed (a GPS only
    receives). 1 ray stale / 2 fresh."""

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(BOWL)
        dc.drawLine(72, 18, 72, 13)
        dc.fillRectangle(71, 12, 3, 1)
        if g >= 1:
            dc.drawLine(77, 7, 77, 16)
            dc.drawLine(77, 16, 74, 13)
        if g >= 2:
            dc.drawLine(67, 7, 67, 16)
            dc.drawLine(67, 16, 70, 13)


class Minimal:
    """E: a mini tilted dish in the old pip's ~9 x 9 box; colour only."""
    DISC = arc_pts(73, 18, 4, 135, 315, 5)

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(self.DISC)
        dc.drawLine(73, 18, 77, 14)
        dc.fillRectangle(77, 13, 2, 2)


# --- round 3 (owner, 2026-10-16): face LEFT, shift left off the date (right
# edge x <= 77, 5 px clear of the day-of-week at 82), bigger (r = 6) with a
# neater post + foot, waves away from the date. Amber stale is the common
# state, so it leads the sheet and the 1x strip.

def half_disc(cx, cy, r, back_deg):
    """Convex half-disc dish: the back bulges toward back_deg (math degrees)."""
    return arc_pts(cx, cy, r, back_deg - 90, back_deg + 90, 8)


class LeftTilt:
    """A/B facing up-left (A mirrored): back bulges down-right."""

    def __init__(self, truss):
        self.truss = truss
        self.disc = half_disc(70, 15, 6, 315)
        self.feed = (65, 10) if truss else (66, 11)

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(self.disc)
        fx, fy = self.feed
        if self.truss:
            for x, y in (self.disc[0], self.disc[-1]):
                dc.drawLine(x, y, fx, fy)                 # rim struts
        else:
            dc.drawLine(70, 15, fx, fy)                   # centre arm
        dc.fillRectangle(fx - 1, fy - 1, 2, 2)            # feed horn
        dc.fillRectangle(72, 21, 2, 2)                    # neck
        dc.fillRectangle(69, 23, 8, 1)                    # foot
        waves(dc, fx - 1, fy - 1, g, 80, 190, 4, 6)   # 1 px of air off the feed


class LeftLevel:
    """A/B facing straight left (radar pose): back bulges right, chord
    vertical; the truss variant is the textbook cross-section triangle."""

    def __init__(self, truss):
        self.truss = truss
        self.disc = half_disc(71, 15, 6, 0)
        self.feed = (63, 15) if truss else (64, 15)

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(self.disc)
        fx, fy = self.feed
        if self.truss:
            for x, y in (self.disc[0], self.disc[-1]):
                dc.drawLine(x, y, fx, fy)
        else:
            dc.drawLine(71, 15, fx, fy)
        dc.fillRectangle(fx - 1, fy - 1, 2, 2)
        dc.fillRectangle(74, 21, 2, 2)
        dc.fillRectangle(71, 23, 7, 1)
        waves(dc, fx - 1, fy, g, 135, 225, 4, 6)


LEFT_DESIGNS = [("current ring", Current()),
                ("A up-left", LeftTilt(False)), ("B up-left", LeftTilt(True)),
                ("A left", LeftLevel(False)), ("B left", LeftLevel(True))]


DESIGNS = [("current ring", Current()), ("A tilted", Tilted()),
           ("B truss", Truss()), ("C telescope", Telescope()),
           ("D rays", Rays()), ("E mini", Minimal())]

CROP = (36, 0, 116, 27)          # the icon + the day-of-week, for context
ZOOM = 9
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4


class IconChrome:
    """Stands in for twchrome.Gps in the V2 stack."""

    def __init__(self, design):
        self.design = design

    def render(self, dc, state):
        self.design.draw(dc, state.gpsFix)


def face(design, g, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = g
    for c in twchrome.v2_chrome():
        if isinstance(c, twchrome.Gps):
            c = IconChrome(design)
        c.render(dc, st)
    return twchrome.glass(dc.img)


# --- round 4 (owner, 2026-10-16): A up-left chosen. Flatter dish (a half-
# ELLIPSE: rim half-width 6, depth `depth` < 6), a shorter arm (3 diagonal
# steps instead of 4), no neck/foot; re-centred on the day-of-week's mid-line.

def half_ellipse(cx, cy, a, b, n=8):
    """Convex half-ellipse dish facing up-left: rim half-width a along the
    (1,-1) diagonal, depth b toward the back (down-right)."""
    k = 1 / math.sqrt(2)
    pts = []
    for i in range(n + 1):
        t = math.pi * i / n
        u, v = a * math.cos(t), b * math.sin(t)       # rim, back
        p = (round(cx + (u + v) * k), round(cy + (-u + v) * k))
        if not pts or pts[-1] != p:
            pts.append(p)
    return pts


class FlatDish:
    """A up-left, flatter, shorter arm, no mount. Round 5 scales it: rim
    half-width a, depth b, arm steps, wave radii, feed horn size, n ellipse
    samples (re-checked convex + nub-free per size)."""

    def __init__(self, depth, arm=3, cx=71, cy=15, a=6, wr=(4, 6), feed=2,
                 n=8):
        self.cx, self.cy = cx, cy
        self.disc = half_ellipse(cx, cy, a, depth, n)
        self.feed = (cx - arm, cy - arm)
        self.wr, self.fs = wr, feed

    def draw(self, dc, g):
        dc.setColor(STATE_COLOR[g], COLOR_TRANSPARENT)
        dc.fillPolygon(self.disc)
        fx, fy = self.feed
        dc.drawLine(self.cx, self.cy, fx, fy)             # arm
        dc.fillRectangle(fx - 1, fy - 1, self.fs, self.fs)  # feed horn
        waves(dc, fx - 1, fy - 1, g, 80, 190, self.wr[0], self.wr[1])


FLAT_DESIGNS = [("round 3 A", LeftTilt(False)),
                ("flatter (5/6)", FlatDish(5)),
                ("flatter (4/6)", FlatDish(4)),
                ("flatter (3/6)", FlatDish(3))]


# --- round 5 (owner, 2026-10-16): depth 5/6 chosen; scale up ~1.33x for
# more curve resolution (rim half-width 8, depth 6.7, arm 4, waves r 5/8,
# ellipse sampled at 10 -- convex, nub-free) and try positions along the
# top of the clock: at the date / nudged left / over the colon / over the
# hour. All on the glass, bottom <= 24 (clock digits at 26).

def big(cx, cy):
    return FlatDish(6.7, arm=4, cx=cx, cy=cy, a=8, wr=(5, 8), feed=2, n=10)


BIG_DESIGNS = [("round 4 (5/6)", FlatDish(5)),
               ("big @ date", big(70, 15)),
               ("big, nudged left", big(66, 15)),
               ("big, over colon", big(61, 16)),
               ("big, over hour", big(55, 16))]


def compare(designs, name, title, states, ctx_state):
    snaps = synthetic_day(profile="active")
    t = mins("13:05")
    grove = load_algo("moss_grove").build()["components"][0]
    for m in range(t + 1):
        grove.advance(snaps[m])

    rows = []
    for label, d in designs:
        cells = []
        for g in states:
            img = face(d, g, grove, snaps[t], t).crop(CROP)
            w, h = img.size
            cells.append((img.resize((w * ZOOM, h * ZOOM), Image.NEAREST),
                          STATE_NAME[g]))
        full = face(d, ctx_state, grove, snaps[t], t)
        cells.append((full.resize((device.W * 2, device.H * 2), Image.NEAREST)
                      .crop((0, 0, device.W * 2, (CROP[3] - CROP[1]) * ZOOM)),
                      STATE_NAME[ctx_state] + ", on the face (2x, top)"))
        rows.append((label, cells))
    heads = {0: "no fix (gray)", 1: "stale (amber, most common)",
             2: "fresh (blue)"}
    sheet(rows, [heads[g] for g in states] + ["in context"],
          os.path.join(OUT, name + ".png"), title)

    # actual size: the top of the face at 1x per design
    strip = Image.new("RGB", (device.W * len(designs) + 8 * (len(designs) - 1),
                              device.H), (24, 24, 24))
    for i, (_, d) in enumerate(designs):
        strip.paste(face(d, ctx_state, grove, snaps[t], t),
                    (i * (device.W + 8), 0))
    strip.save(os.path.join(OUT, name + "-1x.png"))
    print(os.path.join(OUT, name + "-1x.png"))


def main():
    compare(DESIGNS, "gps-dish-compare",
            "GPS fix icon: cross-section satellite dish options",
            (0, 1, 2), 2)
    compare(LEFT_DESIGNS, "gps-dish-left",
            "GPS fix icon round 3: facing left, clear of the date",
            (1, 2, 0), 1)
    compare(BIG_DESIGNS, "gps-dish-big",
            "GPS fix icon round 5: depth 5/6, scaled up, placement",
            (1, 2, 0), 1)
    compare(FLAT_DESIGNS, "gps-dish-flat",
            "GPS fix icon round 4: A up-left, flatter, shorter arm, no mount",
            (1, 2, 0), 1)


if __name__ == "__main__":
    main()
