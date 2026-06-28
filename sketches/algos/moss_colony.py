#!/usr/bin/env python3
"""Moss variant 2 -- "colony": merging dense tufts.

Cohesion comes from CLUMPING instead of even scatter. A handful of colony
centres are placed near the middle; each grows a small SOLID dark-green blob with
a tight, dense, centre-biased stipple of green/amber grains on top. The colonies
overlap, so they merge into one lumpy mass with internal structure -- reads as
moss tufts grown together, not confetti. More movement => more and bigger
colonies. The day's HR mix tints grains (per-frame zone LUT); each elevated-HR
EPISODE fruits a bright peak-zone bead at a colony's edge. Deterministic from the
day seed; time-of-day not encoded.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)

INK = 340
WARM_Z = 5


class MossColony:
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
        nclust = 3 + idiv(rec.act_units, 70)
        if nclust > 8:
            nclust = 8
        csize = 9 + idiv(rec.act_units, 40)        # colony radius
        if csize > 22:
            csize = 22
        grains = 16 + idiv(rec.act_units, 22)      # grains per colony
        if grains > 40:
            grains = 40
        spread = 14 + idiv(rec.act_units, 18)      # how far colonies sit out
        if spread > 44:
            spread = 44

        cxs = []
        cys = []
        for c in range(nclust):
            hc = hash16(seed, c, 31)
            a = hc & 0xFF
            rr = imod(hc >> 8, spread)
            cx = px(CX, rr, a)
            cy = py(CY, rr, a)
            cxs.append(cx)
            cys.append(cy)
            # solid blob base so each colony is cohesive even before stipple
            if ink > 0:
                dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
                dc.fillCircle(cx, cy, idiv(csize, 2))
                ink -= 1
            for i in range(grains):
                if ink <= 0:
                    break
                a2, rr2, h = place(seed, c * 64 + i, 3, csize)
                gx = cx + idiv(rr2 * (isin(a2 + 64)), 127)
                gy = cy + idiv(rr2 * (isin(a2)), 127)
                warm = (lut is not None) and (lut[h & (ZLUT - 1)] >= WARM_Z) \
                    and ((h >> 5) & 3) == 0
                if warm:
                    col = zone_color(lut[h & (ZLUT - 1)])
                elif ((h >> 6) & 7) == 0:
                    col = COLOR_YELLOW
                else:
                    col = COLOR_GREEN if (h & 1) else COLOR_DK_GREEN
                dc.setColor(col, COLOR_TRANSPARENT)
                dc.fillCircle(gx, gy, 1)
                ink -= 1

        # --- episodes: bright fruiting beads at colony edges ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            c = imod(hash16(seed, e, 41), nclust)
            he = hash16(seed, e, 42)
            a = he & 0xFF
            off = idiv(csize, 2) + (he >> 8) % 4
            x = cxs[c] + idiv(off * isin(a + 64), 127)
            y = cys[c] + idiv(off * isin(a), 127)
            mag = rec.emag[e]
            bead = 2 + idiv(mag, 16)
            if bead > 4:
                bead = 4
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 1


def build():
    return {"background": COLOR_BLACK, "components": [MossColony()]}
