#!/usr/bin/env python3
"""Moss variant 1 -- "cushion": a solid two-tone moss mound.

Cohesion comes from a FILLED substrate: a lumpy dark-green disc with a smaller
bright-green crown fanned on top, so the patch reads as one cushion of moss
rather than scattered grains. Granular texture (sparse shadow/highlight dots) and
a short fuzzy rim fringe sit ON the solid base for moss feel without breaking it
up. The day's HR mix tints a few surface flecks (per-frame zone LUT); each
elevated-HR EPISODE is a bright peak-zone bead nestled on the cushion. Size grows
with total movement. Time-of-day not encoded; deterministic from the day seed.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from mossutil import edge, fan
from device import (idiv, imod, hash16, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW, COLOR_DK_GRAY)

INK = 320
NA = 30                # rim samples for the filled fans
WARM_Z = 5


class MossCushion:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)
        base = 16 + idiv(rec.act_units, 10)
        if base > 60:
            base = 60

        # --- solid substrate: dark mound + brighter crown (cohesion) ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 100, NA)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 60, NA)

        # --- granular texture on top: shadow + highlight + warm flecks ---
        n = 60 + idiv(rec.act_units, 6)
        if n > 150:
            n = 150
        for i in range(n):
            if ink <= 0:
                break
            a, rr0, h = place(seed, i, 1, base)
            lim = edge(base, a)
            rr = idiv(rr0 * lim, base) if base > 0 else 0
            warm = (lut is not None) and (lut[h & (ZLUT - 1)] >= WARM_Z) \
                and ((h >> 5) & 3) == 0
            if warm:
                col = zone_color(lut[h & (ZLUT - 1)])
            elif (h & 1) == 0:
                col = COLOR_DK_GREEN          # shadow granule
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        # --- fuzzy rim fringe: short hairs at every other rim sample ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        for i in range(0, NA, 2):
            if ink <= 0:
                break
            a = imod(idiv(i * 256, NA), 256)
            e = edge(base, a)
            le = 2 + (hash16(seed, i, 9) & 1)
            dc.drawLine(px(CX, e, a), py(CY, e, a),
                        px(CX, e + le, a), py(CY, e + le, a))
            ink -= 1

        # --- episodes: bright beads nestled on the cushion ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            a = imod(hash16(seed, e, 21), 256)
            rr = idiv(edge(base, a) * 3, 5)
            mag = rec.emag[e]
            bead = 2 + idiv(mag, 16)
            if bead > 4:
                bead = 4
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), bead + 1)   # seat
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), bead)
            ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [MossCushion()]}
