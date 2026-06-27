#!/usr/bin/env python3
"""Moss variant 3 -- "lobes": foliose lichen rosette.

Cohesion comes from a few SOLID overlapping lobes radiating from the centre,
each a tapered chain of filled circles (fat at the hub, thinning outward) so the
patch reads as a leafy lichen rosette rather than scattered grains. A dark-green
lobe with a brighter green inner streak gives it body; a crusty stipple and warm
flecks add texture on top. More movement => more and longer lobes. Each
elevated-HR EPISODE is a bright apothecium (fruiting disc) on a lobe. Time-of-day
not encoded; deterministic from the day seed.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW, COLOR_DK_GRAY)

INK = 320
WARM_Z = 5


# Draw a tapered lobe from the hub outward along angle a: a chain of filled
# circles whose radius shrinks from r_hub to 1 over `length` px. Returns the tip.
def lobe(dc, a, length, r_hub):
    n = idiv(length, 4)
    if n < 2:
        n = 2
    tx, ty = CX, CY
    for k in range(n + 1):
        rr = idiv(k * length, n)
        rad = r_hub - idiv(k * (r_hub - 1), n)
        if rad < 1:
            rad = 1
        tx = px(CX, rr, a)
        ty = py(CY, rr, a)
        dc.fillCircle(tx, ty, rad)
    return tx, ty


class MossLobes:
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
        nlobe = 5 + idiv(rec.act_units, 50)
        if nlobe > 11:
            nlobe = 11
        length = 22 + idiv(rec.act_units, 16)
        if length > 70:
            length = 70
        r_hub = 5 + idiv(rec.act_units, 120)
        if r_hub > 8:
            r_hub = 8

        # --- solid lobes: dark body then a brighter, shorter inner streak ---
        tips_a = []
        tips_len = []
        for j in range(nlobe):
            if ink <= 0:
                break
            hj = hash16(seed, j, 51)
            a = imod(idiv(j * 256, nlobe) + (hj & 15), 256)
            ln = length - (hj >> 4) % 12          # slight per-lobe variation
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            lobe(dc, a, ln, r_hub)
            dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
            lobe(dc, a, idiv(ln * 6, 10), r_hub - 2 if r_hub > 3 else 1)
            ink -= idiv(ln, 4) * 2 + 2
            tips_a.append(a)
            tips_len.append(ln)

        # --- crusty texture + warm flecks scattered over the rosette ---
        n = 40 + idiv(rec.act_units, 9)
        if n > 120:
            n = 120
        for i in range(n):
            if ink <= 0:
                break
            a, rr, h = place(seed, i, 1, length)
            warm = (lut is not None) and (lut[h & (ZLUT - 1)] >= WARM_Z) \
                and ((h >> 5) & 3) == 0
            if warm:
                col = zone_color(lut[h & (ZLUT - 1)])
            elif ((h >> 6) & 7) == 0:
                col = COLOR_YELLOW
            else:
                col = COLOR_DK_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        # --- episodes: bright apothecia (disc + dark rim) on the lobes ---
        nl = len(tips_a)
        if nl == 0:
            return
        for e in range(rec.nepi):
            if ink <= 0:
                break
            j = imod(hash16(seed, e, 61), nl)
            a = tips_a[j]
            rr = idiv(tips_len[j] * (2 + imod(hash16(seed, e, 62), 2)), 4)
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            mag = rec.emag[e]
            disc = 2 + idiv(mag, 18)
            if disc > 4:
                disc = 4
            dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, disc + 1)          # dark rim
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, disc)
            ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [MossLobes()]}
