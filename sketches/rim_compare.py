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

Also writes rim-compare-zoom.png: the 13:05 cell's lower-right rim at 6x.

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

ROWS = [
    ("ship", None, "under"),
    ("blue under", device.COLOR_BLUE, "under"),
    ("dk-blue under", device.COLOR_DK_BLUE, "under"),
    ("blue over", device.COLOR_BLUE, "over"),
    ("blue halo", device.COLOR_BLUE, "halo"),
]
ZOOM_ROWS = ["ship", "blue under", "blue over", "blue halo"]
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


def main():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    rows = []
    for label, col, over in ROWS:
        mod = load_algo("moss_grove")
        mod.RIM = col
        mod.RIM_MODE = over
        cells = []
        for prof, at in COLS:
            grove = mod.build()["components"][0]
            snaps = days[prof]
            t = mins(at)
            for m in range(t + 1):
                grove.advance(snaps[m])
            cells.append(face(grove, snaps[t], t))
        rows.append((label, cells))
    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "rim-compare.png"),
          "two-worlds V2: 1 px blue leading edge on the moss")
    zoom()


def zoom():
    snaps = synthetic_day(profile="active")
    t = mins("13:05")
    x0, y0, x1, y1 = ZOOM_BOX
    crops = []
    for label, col, mode in ROWS:
        if label not in ZOOM_ROWS:
            continue
        mod = load_algo("moss_grove")
        mod.RIM = col
        mod.RIM_MODE = mode
        grove = mod.build()["components"][0]
        for m in range(t + 1):
            grove.advance(snaps[m])
        img, _ = face(grove, snaps[t], t, scale=0)
        crops.append(img.crop(ZOOM_BOX).resize(((x1 - x0) * ZOOM,
                                                (y1 - y0) * ZOOM),
                                               Image.NEAREST))
    sheet([(label, [(c, "")]) for label, c in zip(ZOOM_ROWS, crops)],
          ["active 13:05, lower-right rim, 6x"],
          os.path.join(OUT, "rim-compare-zoom.png"),
          "leading-edge rim, close up")


if __name__ == "__main__":
    main()
