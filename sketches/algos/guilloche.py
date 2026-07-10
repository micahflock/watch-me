#!/usr/bin/env python3
"""Concept F -- "guilloche": the day engine-turned into a watch dial.

Nested hypotrochoid loops -- the rosette-engine engraving on fine watch dials
(Breguet's guilloche), woven here by the day's biometrics instead of a lathe.
Pure mathematics on a device built for telling time; as far from moss as the
palette allows.

  loop count + rosette size <- act_units (the lathe adds a nested pass as
                               movement accrues; a lazy day is two faint
                               traces, a big day a six-deep engraving)
  loop colour               <- the day's HR-zone mix (zone_lut), one draw from
                               the histogram per loop; steel grey fallback
                               before any HR history
  episodes                  <- gems SET into the outer trace where the curve
                               passes: dim ring + peak-zone fill + glint,
                               sized by magnitude
  sleep                     <- the centre medallion: radius = hours slept,
                               colour = SLEEP_RAMP quality; each 0-6am wake
                               nicks a black notch into its edge
  day seed                  <- petal count, pen ratio, phase, rotation: a
                               different engraving pattern every day

Integer-only: each vertex is 4 isin + adds; the y axis is squashed 9/16 so a
full rosette fills the wide art window without cropping. Self-bounded by INK.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_DK_RED, COLOR_DK_BLUE, COLOR_PURPLE)

CX, CY = 107, 108
INK = 400
NSEG = 64              # vertices per loop
SQN, SQD = 9, 16       # vertical squash (inclined dial)
STEEL = [COLOR_DK_GRAY, COLOR_LT_GRAY]

DIM = {0: COLOR_DK_BLUE, 1: COLOR_DK_BLUE, 2: COLOR_DK_BLUE, 3: COLOR_DK_BLUE,
       4: COLOR_DK_RED, 5: COLOR_DK_RED, 6: COLOR_DK_RED, 7: COLOR_PURPLE,
       8: COLOR_PURPLE}


class Guilloche:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    # hypotrochoid vertex at parameter t (1/256 turn), loop scale s (percent)
    def _vx(self, R, d, m, ph, rot, t, s):
        xr = idiv(R * isin(t + rot + 64) + d * isin(m * t + ph + 64), 127)
        yr = idiv(R * isin(t + rot) - d * isin(m * t + ph), 127)
        return (CX + idiv(xr * s, 100),
                CY + idiv(idiv(yr * s, 100) * SQN, SQD))

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)

        h0 = hash16(seed, 1, 101)
        m = 5 + imod(h0, 5)                    # petal order 5..9
        ph = imod(h0 >> 4, 256)
        rot = imod(h0 >> 7, 256)
        R = 34 + idiv(rec.act_units, 110)      # rosette radius grows all day
        if R > 60:
            R = 60
        d = idiv(R * (38 + imod(h0 >> 9, 14)), 100)   # pen offset 38-51%
        nloop = 2 + idiv(rec.act_units, 640)   # nested passes accrue; six deep
        if nloop > 6:                          # only on a genuinely big day
            nloop = 6

        # --- nested engine-turned loops, outermost first ---
        for j in range(nloop):
            if ink <= 0:
                break
            s = 100 - j * 15
            if lut is not None:
                col = zone_color(lut[hash16(seed, j, 102) & (ZLUT - 1)])
            else:
                col = STEEL[j & 1]
            dc.setColor(col, COLOR_TRANSPARENT)
            px0, py0 = self._vx(R, d, m, ph, rot, 0, s)
            for k in range(1, NSEG + 1):
                if ink <= 0:
                    break
                t = idiv(k * 256, NSEG) & 255
                x1, y1 = self._vx(R, d, m, ph, rot, t, s)
                dc.drawLine(px0, py0, x1, y1)
                px0, py0 = x1, y1
                ink -= 1

        # --- episodes: gems set into the outer trace ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            he = hash16(seed, e, 103)
            t = imod(he, 256)
            x, y = self._vx(R, d, m, ph, rot, t, 100)
            mag = rec.emag[e]
            sgem = 2 + idiv(mag, 24)
            if sgem > 6:
                sgem = 6
            zc = rec.epz[e]
            dc.setColor(DIM[zc], COLOR_TRANSPARENT)
            dc.fillCircle(x, y, sgem + 1)
            dc.setColor(zone_color(zc), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, sgem)
            if mag >= 40:
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(x - 1, y - 1, 0)
                ink -= 1
            ink -= 2

        # --- sleep: the centre medallion ---
        mins = rec.sleep_seed
        if mins > 0:
            hours = idiv(mins, 60)
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            rmed = 4 + idiv(hours * 3, 2)
            if rmed > 18:
                rmed = 18
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, rmed + 2)            # clear the engraving
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, rmed)
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.drawArc(CX, CY, rmed + 1, 0, 0, 360)    # polished bezel ring
            ink -= 3
            for w in range(rec.wake_seed):             # notched edge
                if ink <= 0:
                    break
                hw = hash16(53, w, 104)
                a = imod(idiv(w * 256, rec.wake_seed) + imod(hw, 40), 256)
                nx = CX + idiv(rmed * isin(a + 64), 127)
                ny = CY + idiv(rmed * isin(a), 127)
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillCircle(nx, ny, 2)
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(nx, ny, 0)
                ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [Guilloche()]}
