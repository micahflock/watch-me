#!/usr/bin/env python3
"""moss_grove_lunar -- sleep-nucleus PROPOSAL C for two-worlds V2: moon spores.

The MINIMAL fix: geometry identical to the shipped spore clump (same scatter,
same sizes, same wake specks), but the quality ramp never leaves the night
palette. The shipped SLEEP_RAMP walks DK_RED->RED->ORANGE for short nights --
the effort beads' exact hues in the same filled-dot shape, so a bad night reads
as a workout (owner, 2026-07). Effort keeps the warm hues exclusively; sleep
quality becomes moonlight:

  rested       ->  deep blue clump     (DK_BLUE / BLUE)
  ok           ->  pale blue
  short/broken ->  ashen gray clump    (LT_GRAY / DK_GRAY, bleached moss)

Size still encodes hours; wakes still DIM the clump a step, loosen the
scatter, and add the white blight specks, exactly as shipped. Ports as a
one-table swap in MossGrove.mc (SLEEP_RAMP), nothing else.
"""
import importlib.util
import os

from device import (idiv, imod, hash16, COLOR_TRANSPARENT,
                    COLOR_BLUE, COLOR_DK_BLUE, COLOR_LT_GRAY, COLOR_DK_GRAY)
from daybuckets import px, py
from daysoma import sleep_slot

_p = os.path.join(os.path.dirname(__file__), "moss_grove.py")
_spec = importlib.util.spec_from_file_location("moss_grove", _p)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CX, CY = mg.CX, mg.CY
scl = mg.scl

# hours-slept ramp, night palette only: index (hours-3) - wakes as shipped,
# but the "bad" end is ash, not ember. Adjacent steps stay distinguishable
# against both the dark mound and the bright crown.
MOON_RAMP = [COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_LT_GRAY, COLOR_BLUE,
             COLOR_BLUE, COLOR_DK_BLUE, COLOR_DK_BLUE, COLOR_DK_BLUE]


class MossGroveLunar(mg.MossGrove):

    # line-for-line the shipped draw_spore with SLEEP_RAMP -> MOON_RAMP;
    # spore_reach (and so the episode keep-out) is inherited unchanged
    def draw_spore(self, dc, mins, wakes, ink):
        if mins <= 0:
            return ink
        hours = idiv(mins, 60)
        slot = sleep_slot(mins) - wakes        # restless -> dimmer
        if slot < 0:
            slot = 0
        reach = self.spore_reach(mins, wakes)
        rim = idiv(reach * 2, 3)
        dc.setColor(MOON_RAMP[slot], COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, scl(3))
        nodes = 7 + hours * 2
        for k in range(nodes):
            if ink <= 0:
                break
            h = hash16(91, k, 6)
            a = imod(idiv(k * 256, nodes) + (h % 36), 256)
            r1 = imod(hash16(73, k, 2), reach)
            r2 = imod(hash16(29, k, 4), reach)
            inner = r1 if r1 < r2 else r2
            rr = 2 + (inner if wakes == 0 else idiv(inner + r1 + r2, 3))
            ci = slot
            if rr >= rim and slot >= 1:
                ci = slot - 1
            dc.setColor(MOON_RAMP[ci], COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1 + (h % 3))
            ink -= 1
        # wake specks untouched (same code as shipped; it lives inline in
        # draw_spore so overriding the ramp means carrying it along)
        if wakes > 0:
            wr = scl(2)
            br = wr + scl(3)
            for w in range(wakes):
                if ink <= 0:
                    break
                hw = hash16(53, w, 7)
                a = imod(idiv(w * 256, wakes) + (hw % 24), 256)
                rr = reach + scl(4) + (hw % 4)
                x = px(CX, rr, a)
                y = py(CY, rr, a)
                dc.setColor(mg.COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillCircle(x, y, br)
                nb = 1 + (hash16(w, 5, 9) % 5)
                bd = br + scl(1)
                for k in range(nb):
                    hb = hash16(w + 41, k, 8)
                    ba = imod(idiv(k * 256, nb) + (hb % 40), 256)
                    dc.fillCircle(x + idiv(bd * mg.isin(ba + 64), 127),
                                  y + idiv(bd * mg.isin(ba), 127), scl(1))
                dc.setColor(mg.COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(x, y, wr)
                ink -= (nb + 2)
        return ink


def build():
    return {"background": mg.COLOR_BLACK, "components": [MossGroveLunar()]}
