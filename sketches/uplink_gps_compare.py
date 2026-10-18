#!/usr/bin/env python3
"""uplink_gps_compare.py -- the phone uplink bars re-tooled as the GPS fix
indicator; the satellite dish goes (owner, 2026-10).

The five tapered bars at the top right stop tracking the phone connection and
show Snapshot.gpsFix instead:

    2 fresh fix (< 24 h)          BLUE
    1 stale fix (or age unknown)  ORANGE   (owner: "orange"; YELLOW is the
                                            dish's amber, shown as an option)
    0 no fix -> lat/lng fallback  DK_GRAY

Rows: the shipped face (phone bars + dish), the proposal, and the proposal
with the dish's amber instead of orange. Columns: the three GPS states, full
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
from device import (COLOR_BLUE, COLOR_ORANGE, COLOR_YELLOW, COLOR_DK_GRAY,
                    COLOR_TRANSPARENT)
from north_compare import chrome_state
from twchrome import ChromeDc, rnd, F

DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4
STATE_NAME = {2: "fresh fix", 1: "stale fix", 0: "no fix (lat/lng)"}


class GpsUplink:
    """UplinkComponent, coloured by gpsFix instead of phoneConnected."""

    def __init__(self, stale):
        self.stale = stale

    def render(self, dc, state):
        g = state.gpsFix
        c = COLOR_DK_GRAY
        if g == 2:
            c = COLOR_BLUE
        elif g == 1:
            c = self.stale
        dc.setColor(c, COLOR_TRANSPARENT)
        for i in range(5):
            w = F(29.0) + (4.0 - 29.0) * i / 4.0
            dc.fillRectangle(128, 12 + i * 9, rnd(w), 4)


def face(variant, g, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = g
    st.phoneConnected = True
    for c in twchrome.v2_chrome():
        if variant is not None:
            if isinstance(c, twchrome.Gps):
                continue                                  # dish removed
            if isinstance(c, twchrome.Uplink):
                c = GpsUplink(variant)
        c.render(dc, st)
    return twchrome.glass(dc.img)


def main():
    snaps = synthetic_day(profile="active")
    t = mins("13:05")
    grove = load_algo("moss_grove").build()["components"][0]
    for m in range(t + 1):
        grove.advance(snaps[m])

    variants = [("shipped\n(phone bars\n + dish)", None),
                ("proposal\n(GPS bars,\n orange)", COLOR_ORANGE),
                ("option\n(GPS bars,\n amber)", COLOR_YELLOW)]
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
