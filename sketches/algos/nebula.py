#!/usr/bin/env python3
"""Avenue 1 -- "nebula": the day as a cloud of interstellar gas.

A diffuse scatter of specks fills the dish; the more you MOVED, the larger and
denser the cloud. Each speck's COLOUR is drawn from the day's HR-zone histogram
(zone_pick), so a calm day glows cool blue/violet and a hard day is shot through
with warm red/pink gas -- the nebula's hue IS your HR mix. Every elevated-HR
EPISODE is a bright STAR: a glowing core (peak-zone colour) haloed by a dimmer
shell, sized by the episode's magnitude, plus a few white pinprick stars for
sparkle. No lines, no geometry -- only scattered points, so it reads as a soft
gaseous field. Time-of-day is not encoded (by design); position is deterministic
from the day seed, so the cloud is stable frame-to-frame and unique per day.

Self-bounded: total fillCircle calls capped by INK so a maximal day cannot
outrun the watchdog. Verbatim Monkey C port (idiv/imod/isin/hash16 + fillCircle).
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, ZLUT, CX, CY
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_DK_BLUE, COLOR_BLUE,
                    COLOR_PURPLE, COLOR_DK_RED)

INK = 320
R = 80                 # max cloud radius
COOL = [COLOR_DK_BLUE, COLOR_BLUE, COLOR_PURPLE]   # gas tint with no HR history


class Nebula:
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
        lut = zone_lut(rec)                       # O(1) per-speck colour, built once
        # cloud size/density grow with the day's total movement
        n = 50 + idiv(rec.act_units, 3)
        if n > 240:
            n = 240
        # spread also grows with activity (a lazy day stays a small puff)
        spread = 26 + idiv(rec.act_units, 12)
        if spread > R:
            spread = R

        # --- diffuse gas: scattered specks, centre-dense (one hash each) ---
        for i in range(n):
            if ink <= 0:
                break
            a, rr, h = place(seed, i, 1, spread)
            if lut is not None:
                col = zone_color(lut[h & (ZLUT - 1)])
            else:
                col = COOL[h % 3]                 # no HR history -> cool gas
            dc.setColor(col, COLOR_TRANSPARENT)
            sz = 2 if (h & 7) == 0 else 1
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), sz)
            ink -= 1

        # --- white pinprick stars (sparse sparkle) ---
        ns = 6 + idiv(n, 30)
        dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
        for i in range(ns):
            if ink <= 0:
                break
            a = imod(hash16(seed, i, 11), 256)
            rr = imod(hash16(seed, i, 12), spread)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 0)
            ink -= 1

        # --- episode stars: haloed glowing cores, sized by magnitude ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            a = imod(hash16(seed, e, 21), 256)
            rr = 10 + imod(hash16(seed, e, 22), spread - 8 if spread > 8 else 1)
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            core = zone_color(rec.epz[e])
            mag = rec.emag[e]
            cr = 2 + idiv(mag, 14)
            if cr > 6:
                cr = 6
            dc.setColor(COLOR_DK_RED if rec.epz[e] >= 6 else COLOR_DK_BLUE,
                        COLOR_TRANSPARENT)
            dc.fillCircle(x, y, cr + 2)            # dim halo shell
            dc.setColor(core, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, cr)                # glowing core
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 1)                 # hot white centre
            ink -= 3


def build():
    return {"background": COLOR_BLACK, "components": [Nebula()]}
