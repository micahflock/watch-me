#!/usr/bin/env python3
"""rim_compare.py -- a 1 px blue line on the moss's leading edge (owner, 2026-10).

Rows (moss_grove.RIM / RIM_MODE):
  ship          no rim (the shipped look)
  blue under    COLOR_BLUE (0x00AAFF) traced on the cushion outline right after
                the mound fill -- tufts, fringe hairs and beads draw over it
  dk-blue under COLOR_DK_BLUE (0x0000FF), same placement
  blue over     COLOR_BLUE drawn after tufts/texture/fringe (before the beads
                and root star): one unbroken line across the tufts
  blue halo     COLOR_BLUE silhouette painted 1 px proud under the mound and
                tufts: the ring follows the outer edge of mound + tufts

Round 2 (rim-tendrils.png): dk-blue under plus 1 x 5 px "phalanges" off
the rim, perpendicular to the local edge -- at all 30 outline vertices, or
at the 15 odd ones (between the dk-green fringe hairs).

Each sheet also gets a -zoom.png: the 13:05 lower-right rim at 6x.

Columns: the active day at 7:50 / 13:05 / 21:00 and the HEAVY day at 23:30
(saturation: the watchdog-proxy check). Each cell is the full V2 face (grove
under the real chrome, on the glass); captions are the grove-only proxy.

    python3 sketches/rim_compare.py
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import OUT, load_algo, mins, sheet
from day import synthetic_day
from north_compare import chrome_state
from twchrome import ChromeDc

SCALE = 3
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4

# (label, RIM, RIM_MODE, TENDRIL_STEP, TENDRIL_OFF)
FIRST = [
    ("ship", None, "under", 0, 0),
    ("blue under", device.COLOR_BLUE, "under", 0, 0),
    ("dk-blue under", device.COLOR_DK_BLUE, "under", 0, 0),
    ("blue over", device.COLOR_BLUE, "over", 0, 0),
    ("blue halo", device.COLOR_BLUE, "halo", 0, 0),
]
# round 2 (owner): dk-blue under + 1x5 px phalanges perpendicular to the edge
TENDRILS = [
    ("ship", None, "under", 0, 0),
    ("dk-blue under", device.COLOR_DK_BLUE, "under", 0, 0),
    ("+tendrils x30", device.COLOR_DK_BLUE, "under", 1, 0),
    ("+tendrils x15", device.COLOR_DK_BLUE, "under", 2, 1),
]

ZOOM_BOX = (95, 95, 200, 175)       # display px: the lower-right rim at 13:05
ZOOM = 6
COLS = [("active", "7:50"), ("active", "13:05"), ("active", "21:00"),
        ("heavy", "23:30")]


def face(grove, snap, t, scale=SCALE):
    dc = ChromeDc()
    device.perf_reset()
    grove.render(dc, snap)
    nh, ns, nops = device.perf_read()
    work = (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
            + ns * device.VM_ISIN + nops * device.VM_OP)
    for c in twchrome.v2_chrome():
        c.render(dc, chrome_state(DATE, OFF, DOW, t, snap=snap))
    img = twchrome.glass(dc.img)
    if scale:
        img = img.resize((device.W * scale, device.H * scale), Image.NEAREST)
    wd = "OK" if work <= device.WATCHDOG else "OVER"
    return img, "grove ~{} VMi [{}]".format(work, wd)


def grove_at(row, snaps, t):
    label, col, mode, step, off = row
    mod = load_algo("moss_grove")
    mod.RIM = col
    mod.RIM_MODE = mode
    mod.TENDRIL_STEP = step
    mod.TENDRIL_OFF = off
    grove = mod.build()["components"][0]
    for m in range(t + 1):
        grove.advance(snaps[m])
    return grove


def compare(rows, name, title, zoom_rows):
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    out = []
    for row in rows:
        cells = []
        for prof, at in COLS:
            t = mins(at)
            g = grove_at(row, days[prof], t)
            cells.append(face(g, days[prof][t], t))
        out.append((row[0], cells))
    sheet(out, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, name + ".png"), title)

    # close-up: the 13:05 lower-right rim at ZOOM x, one column per row
    snaps = days["active"]
    t = mins("13:05")
    x0, y0, x1, y1 = ZOOM_BOX
    cells = []
    for row in rows:
        if row[0] not in zoom_rows:
            continue
        img, _ = face(grove_at(row, snaps, t), snaps[t], t, scale=0)
        cells.append((img.crop(ZOOM_BOX).resize(((x1 - x0) * ZOOM,
                                                 (y1 - y0) * ZOOM),
                                                Image.NEAREST), ""))
    sheet([("13:05 rim 6x", cells)], zoom_rows,
          os.path.join(OUT, name + "-zoom.png"), title + " -- close up")


def main():
    compare(FIRST, "rim-compare",
            "two-worlds V2: 1 px blue leading edge on the moss",
            ["ship", "blue under", "blue over", "blue halo"])
    compare(TENDRILS, "rim-tendrils",
            "two-worlds V2: dk-blue rim + 1x5 px tendrils off the edge",
            [r[0] for r in TENDRILS])


if __name__ == "__main__":
    main()
