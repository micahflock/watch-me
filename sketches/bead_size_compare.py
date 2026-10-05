#!/usr/bin/env python3
"""bead_size_compare.py -- effort-bead SIZE curves, side by side.

Owner, 2026-10: beads mostly end up the same size unless an activity is
particularly long -- every episode under ~30 magnitude sits on the 4 px floor.
Ask: steepen the curve on both ends (smaller than today's minimum, larger than
today's maximum). Each row swaps moss_grove.bead_radius for a candidate curve;
placement, colours and everything else are the shipped treatment.

    python3 sketches/bead_size_compare.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bead_compare import OUT, cell, load_algo, mins, render, sheet
from day import synthetic_day
from device import idiv


def old(mag):                       # pre-2026-10: 4 + mag/30, cap 18
    b = 4 + idiv(mag, 30)
    return 18 if b > 18 else b


def sqrt_curve(mag):                # 1 + isqrt(mag), cap 24
    b = 1 + math.isqrt(mag)
    return 24 if b > 24 else b


def linear_steep(mag):              # 2 + mag/20, cap 24
    b = 2 + idiv(mag, 20)
    return 24 if b > 24 else b


CURVES = [
    ("old 4+m/30 cap18", old),
    ("A (ship) 1+sqrt(m) cap24", sqrt_curve),
    ("B 2+m/20 cap24", linear_steep),
]

# an everyday afternoon: stairs, a hurry, a stressful call, a walk, a ride
EVERYDAY = [(4, 3), (4, 8), (5, 15), (4, 30), (5, 60), (6, 120)]
# a big day: a 90-min run among small efforts
BIGDAY = [(8, 950), (4, 5), (5, 40), (4, 12), (6, 200), (4, 22)]


def injected(mod, snaps, at, eps):
    spec = mod.build()
    comp = spec["components"][0]
    for t in range(at + 1):
        comp.advance(snaps[t])
    rec = comp.rec
    rec.nepi = len(eps)
    for i, (z, m) in enumerate(eps):
        rec.epz[i] = z
        rec.emag[i] = m
    return cell(*render(spec, snaps[at]))


def natural(mod, snaps, at):
    spec = mod.build()
    comp = spec["components"][0]
    for t in range(at + 1):
        comp.advance(snaps[t])
    return cell(*render(spec, snaps[at]))


def main():
    active = synthetic_day(profile="active")
    rest = synthetic_day(profile="rest")
    heavy = synthetic_day(profile="heavy")
    rows = []
    for label, fn in CURVES:
        mod = load_algo("moss_grove")
        mod.bead_radius = fn
        rows.append((label, [
            injected(mod, active, mins("16:05"), EVERYDAY),
            injected(mod, active, mins("19:30"), BIGDAY),
            natural(mod, rest, mins("21:00")),
            natural(mod, active, mins("21:00")),
            natural(mod, heavy, mins("23:30")),
        ]))
    sheet(rows,
          ["everyday m3..120", "big day 90' run", "rest day",
           "active day", "HEAVY 23:30"],
          os.path.join(OUT, "bead-size-compare.png"),
          "effort-bead size curves (radius px from magnitude)")


if __name__ == "__main__":
    main()
