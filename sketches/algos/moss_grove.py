#!/usr/bin/env python3
"""Moss hybrid -- "grove": a growing cushion ringed by colony tufts.

Combines the two strongest moss variants:
  * a central CUSHION (cushion.py) -- a solid two-tone lumpy mound -- for
    cohesion, and
  * satellite COLONY tufts (colony.py) -- dense little clumps that straddle the
    cushion rim so they merge into one organism rather than floating free.

Growth is tuned to span the whole day. act_units on an active day runs ~1300
(after the morning) to ~3400 (by night), so the cushion radius and the NUMBER of
tufts are scaled across that range: a lazy morning is a small bud, tufts pop in
one by one as activity accumulates, and a full active day is a broad cushion
fringed with tufts. A rest day stays a small quiet patch; a heavy day saturates.

Each elevated-HR EPISODE fruits a bright peak-zone bead -- on a tuft if there is
one, else on the cushion crown -- so efforts read as fruiting bodies that build
up over the day. Per-frame zone LUT for colour, self-bounded by INK, deterministic
from the day seed; time-of-day not encoded.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from mossutil import edge, fan
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)

INK = 340
NA = 30                # rim samples for the cushion fans
WARM_Z = 5
BASE_DIV = 60          # act_units -> cushion radius (calibrated to the day range)
TUFT_DIV = 600         # act_units -> one more satellite tuft


class MossGrove:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    # one dense colony tuft centred at (tx,ty); solid blob + stipple on top
    def tuft(self, dc, seed, lut, j, tx, ty, tsize, ink):
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        dc.fillCircle(tx, ty, idiv(tsize, 2))
        ink -= 1
        grains = 8 + idiv(tsize, 2)
        if grains > 26:
            grains = 26
        for i in range(grains):
            if ink <= 0:
                break
            a2, rr2, h = place(seed, j * 64 + i, 3, tsize)
            gx = tx + idiv(rr2 * isin(a2 + 64), 127)
            gy = ty + idiv(rr2 * isin(a2), 127)
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
        return ink

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)
        act = rec.act_units

        base = 4 + idiv(act, BASE_DIV)             # cushion grows across the day
        if base > 54:
            base = 54
        ntuft = idiv(act, TUFT_DIV)                # tufts pop in as activity accrues
        if ntuft > 7:
            ntuft = 7
        tsize = 7 + idiv(act, 320)                 # tufts also fatten a little
        if tsize > 16:
            tsize = 16

        # --- central cushion: solid dark mound + brighter crown ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 100, NA)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 60, NA)

        # --- satellite tufts straddling the rim (deterministic positions) ---
        tx_list = []
        ty_list = []
        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(edge(base, a) * (85 + (hj >> 8) % 30), 100)   # ~0.85..1.15 rim
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            tx_list.append(tx)
            ty_list.append(ty)
            ink = self.tuft(dc, seed, lut, j, tx, ty, tsize, ink)

        # --- granular texture + warm flecks over the cushion ---
        n = 50 + idiv(act, 12)
        if n > 130:
            n = 130
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
                col = COLOR_DK_GREEN
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        # --- fuzzy rim fringe ---
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

        # --- episodes: bright fruiting beads, on a tuft if available ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            bead = 2 + idiv(mag, 16)
            if bead > 4:
                bead = 4
            if len(tx_list) > 0:
                t = imod(hash16(seed, e, 41), len(tx_list))
                he = hash16(seed, e, 42)
                off = idiv(tsize, 2) + (he >> 8) % 3
                a = he & 0xFF
                x = tx_list[t] + idiv(off * isin(a + 64), 127)
                y = ty_list[t] + idiv(off * isin(a), 127)
            else:
                a = imod(hash16(seed, e, 42), 256)
                rr = idiv(edge(base, a) * 3, 5)
                x = px(CX, rr, a)
                y = py(CY, rr, a)
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead + 1)
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [MossGrove()]}
