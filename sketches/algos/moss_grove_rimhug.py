#!/usr/bin/env python3
"""moss_grove_rimhug -- bead-contiguity PROPOSAL B: drop the keep-out.

NOT CHOSEN (2026-07-14: the owner picked A -- exact keep-out + embed +
tapered podetium stalks + golden-angle spread -- now folded into moss_grove
itself); kept as a reference alternative for bead_compare.py. This file
freezes the SHIP-era episode placement (hashed angles, hashed tuft pick)
minus the keep-out, since the base class no longer carries either.

Same problem statement as the chosen treatment (beads detached from the moss
on a low-movement morning because the root-star keep-out exceeded the rim).
B was the minimal fix: DELETE the keep-out. Beads sit where the moss is -- 60% of
the rim (on the crown), or riding their REAL tuft -- and the root star,
which is drawn LAST precisely so it survives on top of the day's growth,
rides over them.

Maximal contiguity, smallest diff -- but it reverses the documented owner
decision that beads keep out of the star (2026-07): a bright warm bead can
now sit directly under the root tips, and the 1 px blue/gray tip dots have
to stay legible against it. Rendered side by side with A so that trade is
visible before anything ports.
"""
import importlib.util
import os

from device import (idiv, imod, hash16, isin, account,
                    COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)
from daybuckets import px, py
from daysoma import zone_color, dominant_zone, ACTIVE
from mossutil import edge, shape_params

_p = os.path.join(os.path.dirname(__file__), "moss_grove.py")
_spec = importlib.util.spec_from_file_location("moss_grove", _p)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CX, CY, NA, INK = mg.CX, mg.CY, mg.NA, mg.INK
BASE_DIV, TUFT_DIV, AMPREF = mg.BASE_DIV, mg.TUFT_DIV, mg.AMPREF
scl = mg.scl


class MossGroveRimhug(mg.MossGrove):

    # parent render() line for line; the episodes block (marked) loses both
    # keep-out clamps, nothing else changes
    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        dz = dominant_zone(rec, ACTIVE)
        if dz < 0:
            dz = dominant_zone(rec)
        dzcol = zone_color(dz) if dz >= 0 else None
        act = rec.act_units

        base = 4 + idiv(act, BASE_DIV)
        if base > 54:
            base = 54
        base = scl(base)

        sp = shape_params(seed)
        s = 100 if base >= AMPREF else idiv(100 * base, AMPREF)
        sp = (sp[0], sp[1], sp[2], sp[3],
              idiv(scl(sp[4]) * s, 100), idiv(scl(sp[5]) * s, 100),
              sp[6], idiv(scl(sp[7]) * s, 100), sp[8])
        ntuft = idiv(act, TUFT_DIV)
        if ntuft > 7:
            ntuft = 7
        tsize = 10 + idiv(act, 240)
        if tsize > 23:
            tsize = 23
        tsize = scl(tsize)

        for i in range(NA):
            ai = imod(idiv(i * 256, NA), 256)
            e = edge(base, ai, sp)
            self.er[i] = e
            self.vx[i] = idiv(e * isin(ai + 64), 127)
            self.vy[i] = idiv(e * isin(ai), 127)
        account(NA * 2)

        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 100)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 60)

        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(self.er[idiv(a * NA, 256)] * (85 + (hj >> 8) % 30), 100)
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            ink = self.draw_tuft(dc, seed, j, tx, ty, tsize, dzcol, ink)

        n = 50 + idiv(act, 12)
        if n > 90:
            n = 90
        for i in range(n):
            if ink <= 0:
                break
            a, rr0, h = mg.place(seed, i, 1, base)
            lim = self.er[idiv(a * NA, 256)]
            rr = idiv(rr0 * lim, base) if base > 0 else 0
            if (h & 1) == 0:
                col = COLOR_DK_GREEN
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        for i in range(0, NA, 2):
            if ink <= 0:
                break
            a = imod(idiv(i * 256, NA), 256)
            e = self.er[i]
            le = 2 + (hash16(seed, i, 9) & 1)
            dc.drawLine(CX + self.vx[i], CY + self.vy[i],
                        px(CX, e + le, a), py(CY, e + le, a))
            ink -= 1

        # >>> episodes: NO keep-out -- beads live on the moss ------------------
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            bead = 4 + idiv(mag, 30)
            if bead > 18:
                bead = 18
            if ntuft > 0:
                t = imod(hash16(seed, e, 41), ntuft)
                hj = hash16(seed, t, 31)
                ta = imod(idiv(t * 256, ntuft) + (hj & 31), 256)
                trr = idiv(self.er[idiv(ta * NA, 256)]
                           * (85 + (hj >> 8) % 30), 100)
                tx = px(CX, trr, ta)
                ty = py(CY, trr, ta)
                he = hash16(seed, e, 42)
                off = idiv(tsize, 2) + (he >> 8) % 3
                a = he & 0xFF
                x = tx + idiv(off * isin(a + 64), 127)
                y = ty + idiv(off * isin(a), 127)
            else:
                a = imod(hash16(seed, e, 42), 256)
                rr = idiv(self.er[idiv(a * NA, 256)] * 3, 5)
                x = px(CX, rr, a)
                y = py(CY, rr, a)
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead + 1)
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 2
        # <<< end episodes ----------------------------------------------------

        self.draw_sleep(dc, rec.sleep_seed, rec.wake_seed, ink)


def build():
    return {"background": COLOR_BLACK, "components": [MossGroveRimhug()]}
