#!/usr/bin/env python3
"""uplink_gps_compare.py -- the phone uplink bars re-tooled as the GPS fix
indicator; the satellite dish goes (owner, 2026-10).

The five tapered bars at the top right stop tracking the phone connection and
show Snapshot.gpsFix instead:

    2 fresh fix (< 24 h)          BLUE
    1 stale fix (or age unknown)  YELLOW   (amber; owner picked it over
                                            ORANGE, the battery's colour)
    0 no fix -> lat/lng fallback  DK_GRAY

Rows: the pre-2026-10 face (phone bars + dish), the rejected orange option,
and the shipped amber (twchrome's v2_chrome()). Columns: the three GPS states, full
face at 2x (the grove at 13:05 of the active synthetic day behind).

    python3 sketches/uplink_gps_compare.py
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import OUT, load_algo, mins, sheet
from day import synthetic_day
from device import COLOR_ORANGE, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc, rnd, F

DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4
STATE_NAME = {2: "fresh fix", 1: "stale fix", 0: "no fix (lat/lng)"}


class OrangeUplink(twchrome.Uplink):
    """The rejected option: stale in ORANGE (the battery's colour)."""

    def render(self, dc, state):
        if state.gpsFix != 1:
            return super().render(dc, state)
        dc.setColor(COLOR_ORANGE, COLOR_TRANSPARENT)
        for i in range(5):
            w = F(29.0) + (4.0 - 29.0) * i / 4.0
            dc.fillRectangle(128, 12 + i * 9, rnd(w), 4)


def face(variant, g, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = g
    st.phoneConnected = True
    for c in twchrome.v2_chrome(dish=(variant == "old")):
        if variant == "orange" and isinstance(c, twchrome.Uplink):
            c = OrangeUplink()
        c.render(dc, st)
    return twchrome.glass(dc.img)


def main():
    snaps = synthetic_day(profile="active")
    t = mins("13:05")
    grove = load_algo("moss_grove").build()["components"][0]
    for m in range(t + 1):
        grove.advance(snaps[m])

    variants = [("before\n(phone bars\n + dish)", "old"),
                ("rejected\n(GPS bars,\n orange)", "orange"),
                ("SHIPPED\n(GPS bars,\n amber)", "amber")]
    states = (2, 1, 0)
    rows = []
    for label, v in variants:
        cells = []
        for g in states:
            img = face(v, g, grove, snaps[t], t)
            cells.append((img.resize((device.W * 2, device.H * 2),
                                     Image.NEAREST), STATE_NAME[g]))
        rows.append((label, cells))
    sheet(rows, [STATE_NAME[g] for g in states],
          os.path.join(OUT, "uplink-gps-compare.png"),
          "Phone bars -> GPS fix bars (dish removed)")


if __name__ == "__main__":
    main()
