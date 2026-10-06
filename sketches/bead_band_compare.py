#!/usr/bin/env python3
"""bead_band_compare.py -- recorded-workout catch-up + growth-ring beads.

Owner, 2026-10: beads should show HR at points THROUGH an effort (bands, start
at the centre, end at the rim, radius >= 8 px), and must work for workouts
RECORDED in the activity app -- during which the watch face does not run.

Scenario: the synthetic active day's 7:00 run reshaped into a structured
workout (warm-up ramp, tempo, 3 x 3' purple / 2' red intervals, cool-down),
recorded in the activity app: the face is away 7:00-8:04 and returns at 8:05.
HR history (ActivityMonitor.getHeartRateHistory on the watch) is modelled as
a 2-minute sample log, carried forward between samples.

Rows:
  pre-2026-10   gap collapses into one minute at 8:05 (HR then 84: zone 2),
                so the run makes NO bead -- only moss growth
  backfill      gap replayed from HR history (CHUNK min per update), solid
                peak-zone bead
  backfill+rings  ... and the bead drawn as chronological growth rings, each
                band the PEAK zone of its span (owner chose peak over mean,
                2026-10: mean smeared the purple/red intervals into pink)
  face-on+rings reference: the face on screen the whole run (no gap)

    python3 sketches/bead_band_compare.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bead_compare
from bead_compare import OUT, cell, load_algo, mins, render, sheet
from day import synthetic_day

AWAY = (mins("7:00"), mins("8:05"))     # face not running (activity app)
HIST_STEP = 2                           # HR history sample spacing (min)


def workout_hr(m):
    """HR for a structured run starting 7:00, or None outside it."""
    t = m - mins("7:00")
    if t < 0 or t >= 60:
        return None
    if t < 10:                          # warm-up 110 -> 137
        return 110 + t * 3
    if t < 35:                          # tempo, zone 6 (red)
        return 145 + (t % 3) * 2
    if t < 50:                          # 3 x (3' @ 166 purple, 2' @ 140 red)
        return 166 if (t - 35) % 5 < 3 else 140
    return 135 - (t - 50) * 3           # cool-down 135 -> 108


def workout_day():
    snaps = synthetic_day(profile="active")
    for m in range(1440):
        hr = workout_hr(m)
        if hr is not None:
            snaps[m].heartRate = hr
    return snaps


def history(snaps):
    def hist(m):
        return snaps[m - m % HIST_STEP].heartRate
    return hist


def run_day(mod, snaps, at, away, hist):
    spec = mod.build()
    comp = spec["components"][0]
    for t in range(at + 1):
        if away and AWAY[0] <= t < AWAY[1]:
            continue                    # the activity app has the screen
        comp.advance(snaps[t], hist)
    return spec


ROWS = [
    ("pre-2026-10", True, False, False),
    ("backfill", True, True, False),
    ("backfill+rings", True, True, True),
    ("face-on+rings", False, False, True),
]


def main():
    bead_compare.SCALE = 3
    snaps = workout_day()
    heavy = synthetic_day(profile="heavy")
    hist = history(snaps)
    rows = []
    for label, away, use_hist, bands in ROWS:
        mod = load_algo("moss_grove")
        mod.BANDS = bands
        h = hist if use_hist else None
        cells = []
        for at in ["8:06", "8:20", "21:00"]:
            spec = run_day(mod, snaps, mins(at), away, h)
            cells.append(cell(*render(spec, snaps[mins(at)])))
        spec = run_day(mod, heavy, mins("23:30"), False, None)
        cells.append(cell(*render(spec, heavy[mins("23:30")])))
        rows.append((label, cells))
    sheet(rows,
          ["8:06 (catching up)", "8:20 (caught up)", "21:00",
           "HEAVY 23:30"],
          os.path.join(OUT, "bead-band-compare.png"),
          "recorded workout (face away 7:00-8:05) + growth-ring beads")


if __name__ == "__main__":
    main()
