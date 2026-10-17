#!/usr/bin/env python3
"""zone_color_compare.py -- re-colour the HR ramp to match Garmin's zones.

Owner, 2026-10-17 (wrist photo of the HR gauge: 153 bpm = green, "High
Aerobic"): the 9-step HR_RAMP turns hot about a zone early -- a bead at 153
is PINK where the watch says green. Garmin's gauge is gray Z1 / blue Z2 /
green Z3 / orange Z4 / red Z5. Two candidate remaps (no gray anywhere):

  now       the shipped ramp (fixed bpm bounds 60..165)
  A garmin  Garmin's colours per zone, Z1 dark blue instead of gray,
            everything below Z1 purple
  B shifted every colour one zone lower, pink on top:
            Z1 blue, Z2 green, Z3 orange, Z4 red, Z5 pink;
            below Z1 dark blue, sleep (<60) purple

A and B use the default %-of-max zones for an ESTIMATED max HR of 195
(Z1 98 / Z2 117 / Z3 137 / Z4 156 / Z5 176) -- the photo puts 153 near the
top of Z3. On the watch the bounds could come from the user's own zones.
The 9-slot structure is kept (ACTIVE = 4 still means HR >= 105, so the same
minutes make beads); only bounds and colours change.

    python3 sketches/zone_color_compare.py
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bead_compare
import daybuckets
import device as D
from bead_band_compare import workout_day
from bead_compare import OUT, cell, load_algo, mins, render, sheet
from day import synthetic_day

# Garmin %-of-max zone floors for max HR ~195: 50/60/70/80/90 %.
GZ = [98, 117, 137, 156, 176]
# slots: <60 | 60-79 | 80-97 | Z1 lo 98-104 | Z1 hi 105-116 | Z2 | Z3 | Z4 | Z5
G_BOUNDS = [60, 80, GZ[0], 105, GZ[1], GZ[2], GZ[3], GZ[4]]

VARIANTS = [
    ("now", list(daybuckets.HR_BOUNDS), list(daybuckets.HR_RAMP)),
    ("A garmin", G_BOUNDS,
     [D.COLOR_PURPLE, D.COLOR_PURPLE, D.COLOR_PURPLE,
      D.COLOR_DK_BLUE, D.COLOR_DK_BLUE,              # Z1 (gray on Garmin)
      D.COLOR_BLUE, D.COLOR_GREEN, D.COLOR_ORANGE, D.COLOR_RED]),
    ("B shifted", G_BOUNDS,
     [D.COLOR_PURPLE, D.COLOR_DK_BLUE, D.COLOR_DK_BLUE,
      D.COLOR_BLUE, D.COLOR_BLUE,                    # Z1
      D.COLOR_GREEN, D.COLOR_ORANGE, D.COLOR_RED, D.COLOR_PINK]),
]


def apply(bounds, ramp):
    # in place: daysoma / moss_grove imported these very list objects
    daybuckets.HR_BOUNDS[:] = bounds
    daybuckets.HR_RAMP[:] = ramp


def hard_day():
    """The workout day with the intervals pushed into Z5 (180 bpm)."""
    snaps = workout_day()
    for m in range(mins("7:35"), mins("7:50")):
        if (m - mins("7:35")) % 5 < 3:
            snaps[m].heartRate = 180
    return snaps


def run(mod, snaps, at):
    spec = mod.build()
    comp = spec["components"][0]
    for t in range(at + 1):
        comp.advance(snaps[t])
    return spec


def legend(bounds, ramp, size):
    """bpm 40..200 as a colour bar, with the zone floors marked."""
    w, h = size
    im = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(im)
    lo, hi = 40, 200
    x0, x1, y0, y1 = 10, w - 10, h // 2 - 30, h // 2 + 10

    def xof(bpm):
        return x0 + (bpm - lo) * (x1 - x0) // (hi - lo)

    edges = [lo] + list(bounds) + [hi]
    for i, c in enumerate(ramp):
        a, b = max(edges[i], lo), min(edges[i + 1], hi)
        if b > a:
            d.rectangle([xof(a), y0, xof(b) - 1, y1],
                        fill=((c >> 16) & 255, (c >> 8) & 255, c & 255))
    for bpm in bounds:
        d.line([xof(bpm), y1, xof(bpm), y1 + 6], fill=(200, 200, 200))
        d.text((xof(bpm) - 8, y1 + 8 + (12 if bpm in (80, 105, 138, 165, 117, 156) else 0)),
               str(bpm), fill=(200, 200, 200))
    d.line([xof(153), y0 - 10, xof(153), y0 - 2], fill=(255, 255, 255))
    d.text((xof(153) - 30, y0 - 24), "153 (photo)", fill=(255, 255, 255))
    return im


def main():
    bead_compare.SCALE = 3
    days = [("run 8:20", workout_day(), "8:20"),
            ("run 21:00", workout_day(), "21:00"),
            ("hard run 21:00", hard_day(), "21:00"),
            ("HEAVY 23:30", synthetic_day(profile="heavy"), "23:30")]
    rows = []
    for label, bounds, ramp in VARIANTS:
        apply(bounds, ramp)
        mod = load_algo("moss_grove")
        cells = []
        for _, snaps, at in days:
            spec = run(mod, snaps, mins(at))
            cells.append(cell(*render(spec, snaps[mins(at)])))
        size = cells[0][0].size
        cells.append((legend(bounds, ramp, size), "bpm ramp"))
        rows.append((label, cells))
    apply(VARIANTS[0][1], VARIANTS[0][2])
    sheet(rows, [d[0] for d in days] + ["ramp"],
          os.path.join(OUT, "zone-color-compare.png"),
          "HR ramp vs Garmin zones (est. max HR 195: Z1 98 Z2 117 Z3 137 "
          "Z4 156 Z5 176)")


if __name__ == "__main__":
    main()
