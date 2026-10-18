#!/usr/bin/env python3
"""phone_ring_compare.py -- a phone-connected indicator for two-worlds V2
now that the uplink bars show GPS (owner, 2026-10: "a 2x border around the
whole watch face when it's connected"; nothing when disconnected).

Options (columns = connected / disconnected, at 2x):

  A blue ring   a 2 px ring hugging the edge of the glass, BLUE (the old
                connected-bars colour)
  B white ring  the same ring in WHITE (the chrome's line colour)
  C thick field the white field border doubled to 2 px (its path offset
                1 px toward the chrome, as border_outline_compare's Outline)

The ring is drawCircle at r 106 and 105 about (107, 90) and (108, 90) -- the
panel disc is r 107.5 about (107.5, 90), between pixel centres -- plus the
top and bottom two rows of the glass (its flat chords). Six calls, nothing
precomputed. drawCircle rasterization is the one thing only the SDK sim gets
exactly; PIL's ellipse is close enough to judge the look.

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
    def __init__(self, color):
        self.color = color
        self.top = [chord_x(0), chord_x(1)]
        self.bot = [chord_x(178), chord_x(179)]

    def render(self, dc, state):
        if state.phoneConnected is not True:
            return
        dc.setColor(self.color, COLOR_TRANSPARENT)
        for cx in (107, 108):
            dc.drawCircle(cx, 90, 106)
            dc.drawCircle(cx, 90, 105)
        x0, x1 = self.top[0]
        dc.fillRectangle(x0, 0, x1 - x0 + 1, 2)
        x0, x1 = self.bot[0]
        dc.fillRectangle(x0, 178, x1 - x0 + 1, 2)


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
