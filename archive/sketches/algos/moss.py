#!/usr/bin/env python3
"""Avenue 2 -- "moss": the day as a patch of living moss / lichen.

A cohesive, lumpy ground-cover clump grows from the centre. The more you MOVED,
the wider and denser the bed. The bed is mossy greens (dark green -> green ->
amber) so it always reads as moss, but the day's HR mix tints it: warmer zones
sprinkle in hot flecks (sampled from the per-frame zone LUT). Each elevated-HR
EPISODE fruits a little cluster of bright peak-zone SPORANGIA nestled in the bed,
sized by magnitude -- the day's efforts blooming out of the moss. Soft and
clustered (dense stipple, lumpy rim, only stubby fuzz -- no long spikes), the
opposite of a clean ring. Time-of-day is not encoded; placement is deterministic
from the day seed.

Lumpy boundary = base radius + an isin undulation in the angle. One hash per
grain (place()), O(1) colour via the zone LUT, self-bounded by INK. Verbatim
Monkey C port.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW, COLOR_DK_GRAY)

INK = 340
MOSS = [COLOR_DK_GREEN, COLOR_DK_GREEN, COLOR_DK_GREEN, COLOR_GREEN,
        COLOR_GREEN, COLOR_YELLOW]                 # bed tints (green-dominant)
WARM_Z = 5             # zone >= this can show a hot fleck instead of moss green


# Lumpy patch radius at angle a: base + two low undulations so the rim is organic.
def edge(base, a):
    return base + idiv(8 * isin(imod(a * 3, 256)), 127) \
                + idiv(4 * isin(imod(a * 5 + 40, 256)), 127)


class Moss:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def render(self, dc, snap):
        rec = self.rec
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)
        base = 16 + idiv(rec.act_units, 10)        # bed spread grows with movement
        if base > 60:
            base = 60
        n = 110 + idiv(rec.act_units, 3)           # dense stipple => reads as a bed
        if n > 280:
            n = 280

        # --- the moss bed: dense centre-biased stipple inside the lumpy edge ---
        for i in range(n):
            if ink <= 0:
                break
            # place() spreads over `base`; the per-angle edge then clips/extends so
            # the rim is lumpy. Reuse the same hash for colour + fuzz decisions.
            a, rr0, h = place(seed, i, 1, base)
            lim = edge(base, a)
            rr = idiv(rr0 * lim, base) if base > 0 else 0   # remap into lumpy rim
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            warm = (lut is not None) and (lut[h & (ZLUT - 1)] >= WARM_Z) \
                and ((h >> 5) & 3) == 0
            if warm:
                dc.setColor(zone_color(lut[h & (ZLUT - 1)]), COLOR_TRANSPARENT)
            else:
                dc.setColor(MOSS[(h >> 7) % 6], COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 1)
            ink -= 1
            # a stubby 1-2px fuzz on a few grains (kept short so it stays soft)
            if (h & 7) == 0 and ink > 0:
                le = 1 + ((h >> 3) & 1)
                dc.drawLine(x, y, px(CX, rr + le, a), py(CY, rr + le, a))
                ink -= 1

        # --- episodes: clusters of bright sporangia nestled in the bed ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            a = imod(hash16(seed, e, 21), 256)
            rr = idiv(edge(base, a) * 2, 3)        # rooted in the outer bed
            mag = rec.emag[e]
            bead = 2 + idiv(mag, 16)
            if bead > 4:
                bead = 4
            col = zone_color(rec.epz[e])
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), bead)
            # a couple of smaller buds clustered beside it (no long stalk)
            nb = 1 + idiv(mag, 20)
            if nb > 3:
                nb = 3
            for b in range(nb):
                if ink <= 0:
                    break
                hb = hash16(seed, e * 4 + b, 23)
                aa = imod(a + (hb & 31) - 15, 256)
                rb = rr + 2 + ((hb >> 5) & 5)
                dc.fillCircle(px(CX, rb, aa), py(CY, rb, aa), 1 + (bead >> 2))
                ink -= 1
            ink -= 1


def build():
    return {"background": COLOR_BLACK, "components": [Moss()]}
