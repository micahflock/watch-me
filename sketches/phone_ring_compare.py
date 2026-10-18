#!/usr/bin/env python3
"""phone_ring_compare.py -- a phone-connected indicator for two-worlds V2
now that the uplink bars show GPS (owner, 2026-10: "a 2x border around the
whole watch face when it's connected"; nothing when disconnected).

Options (columns = connected / disconnected, at 2x):

  A blue ring   a 2 px ring hugging the edge of the glass, BLUE (the old
                connected-bars colour) -- SHIPPED (owner, 2026-10)
  B white ring  the same ring in WHITE (the chrome's line colour)
  C thick field the white field border doubled to 2 px (its path offset
                1 px toward the chrome, as border_outline_compare's Outline)

The ring is drawCircle at r 107 and 106 about (107, 89) and (107, 90) -- the
panel's centre pixel is x 107 (215 wide) and between rows 89 and 90 (180
tall) -- plus the top and bottom two rows of the glass (its flat chords).
Six calls, nothing precomputed. Fitted against the SDK sim (2026-10): its
drawCircle(cx, cy, r) is the midpoint circle (rows cx - r .. cx + r), and
this set covers every glass pixel within 2 px of the edge with no gaps (68
spots go 3 px thick on the diagonals). The first try, about (107|108, 90) at
r 106/105, left a black pixel column at x 0 and drew 3-4 px.
PIL's ellipse here is close enough to judge the look.

    python3 sketches/phone_ring_compare.py
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
from device import COLOR_BLUE, COLOR_WHITE, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc, F
from border_outline_compare import Outline

DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4


def chord_x(y):
    """Glass extent [x0, x1] on row y (disc r 107.5 about (107.5, 90))."""
    dy = y + 0.5 - 90.0
    h = math.sqrt(107.5 ** 2 - dy * dy)
    return int(math.ceil(107.5 - h - 0.5)), int(math.floor(107.5 + h - 0.5))


class Ring:
    """PhoneRingComponent (shipped as option A). The chord rows span the
    glass's widest top/bottom row, chord_x(1) = chord_x(178) = (46, 168);
    the extra corner pixels on rows 0/179 are off the glass."""

    def __init__(self, color):
        self.color = color

    def render(self, dc, state):
        if state.phoneConnected is not True:
            return
        dc.setColor(self.color, COLOR_TRANSPARENT)
        for cy in (89, 90):
            dc.drawCircle(107, cy, 107)
            dc.drawCircle(107, cy, 106)
        dc.fillRectangle(46, 0, 123, 2)
        dc.fillRectangle(46, 178, 123, 2)


class Thick:
    def __init__(self):
        self.o = Outline(COLOR_WHITE)

    def render(self, dc, state):
        if state.phoneConnected is True:
            self.o.render(dc, state)


def face(layer, connected, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 1
    st.phoneConnected = connected
    for c in twchrome.v2_chrome():
        if isinstance(c, twchrome.PhoneRing):
            continue                      # the option under test stands in
        c.render(dc, st)
        if isinstance(c, twchrome.Border):
            layer.render(dc, st)          # over the border, under the readouts
    return twchrome.glass(dc.img)


OPTIONS = [("A blue ring", Ring(COLOR_BLUE)),
           ("B white ring", Ring(COLOR_WHITE)),
           ("C thick field\n  border", Thick())]


def main():
    snaps = synthetic_day(profile="active")
    t = mins("13:05")
    grove = load_algo("moss_grove").build()["components"][0]
    for m in range(t + 1):
        grove.advance(snaps[m])

    rows = []
    for label, layer in OPTIONS:
        cells = []
        for conn in (True, False):
            img = face(layer, conn, grove, snaps[t], t)
            cells.append((img.resize((device.W * 2, device.H * 2),
                                     Image.NEAREST),
                          "connected" if conn else "disconnected"))
        rows.append((label, cells))
    sheet(rows, ["phone connected", "disconnected"],
          os.path.join(OUT, "phone-ring-compare.png"),
          "two-worlds V2: phone-connected indicator")


if __name__ == "__main__":
    main()
