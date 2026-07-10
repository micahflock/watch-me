#!/usr/bin/env python3
"""Concept E -- "aurora": the day as northern lights under a starfield.

Vertical ray curtains hang across the sky along seeded sine paths -- pure
line-work with a luminous hem, nothing cellular. The physics even cooperates:
real aurorae are green when calm and run red/purple when the solar wind is
violent, exactly the HR ramp's story.

  curtain count + ray height <- act_units (a lazy day is one low arc; a big
                                day fills the sky with tall curtains)
  ray colour, in band chunks <- the day's HR-zone mix (zone_lut) sampled in
                                coherent 4-column bands; classic green
                                fallback before any HR history
  episodes                   <- coronal bursts: a radial fan of rays high in
                                the sky, peak-zone colour, sized by magnitude
  sleep                      <- the MOON: radius = hours slept, colour =
                                SLEEP_RAMP quality (a red moon after a short
                                night); each 0-6am wake drags a dark cloud
                                bar across it
  day seed                   <- curtain paths, moon side, star placement --
                                tomorrow's sky is different

Integer-only; self-bounded by INK. Cost is ~2 lines per curtain column.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_RED, COLOR_DK_RED, COLOR_ORANGE, COLOR_YELLOW,
                    COLOR_GREEN, COLOR_DK_GREEN, COLOR_BLUE, COLOR_DK_BLUE,
                    COLOR_PURPLE, COLOR_PINK)

CX, CY = 107, 108
INK = 380
X0, X1, STEP = 26, 190, 4      # curtain columns

# ray body (dim) for each bright hem colour
DIMBODY = {COLOR_DK_BLUE: COLOR_DK_BLUE, COLOR_BLUE: COLOR_DK_BLUE,
           COLOR_DK_GREEN: COLOR_DK_GREEN, COLOR_GREEN: COLOR_DK_GREEN,
           COLOR_YELLOW: COLOR_ORANGE, COLOR_ORANGE: COLOR_DK_RED,
           COLOR_RED: COLOR_DK_RED, COLOR_PINK: COLOR_PURPLE,
           COLOR_PURPLE: COLOR_DK_BLUE}


class Aurora:
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

        # --- starfield ---
        for i in range(26):
            if ink <= 0:
                break
            h = hash16(seed, i, 91)
            x = CX - 84 + imod(h, 169)
            y = 66 + imod(h >> 7, 92)
            dc.setColor(COLOR_LT_GRAY if imod(h >> 5, 6) == 0 else COLOR_DK_GRAY,
                        COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 0)
            ink -= 1

        # --- sleep: the moon (behind the curtains) ---
        mins = rec.sleep_seed
        hm = hash16(seed, 4, 92)
        mside = -1 if (hm & 16) else 1
        mx = CX + mside * (52 + imod(hm, 14))
        my = 74 + imod(hm >> 6, 8)
        mr = 0
        if mins > 0:
            hours = idiv(mins, 60)
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            mr = 3 + hours
            if mr > 13:
                mr = 13
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            dc.fillCircle(mx, my, mr)
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(mx - idiv(mr, 3), my - idiv(mr, 3), idiv(mr, 4))
            ink -= 2
            for w in range(rec.wake_seed):     # clouds across the moon
                if ink <= 0:
                    break
                hw = hash16(53, w, 93)
                cw = mr + 6 + imod(hw, 6)
                cy2 = my - mr + 1 + imod(hw >> 5, 2 * mr - 2 if mr > 1 else 1)
                dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
                dc.fillRectangle(mx - idiv(cw, 2) + imod(hw >> 8, 7) - 3,
                                 cy2, cw, 2)
                ink -= 1

        # --- curtains ---
        nc = 1 + idiv(rec.act_units, 1100)
        if nc > 3:
            nc = 3
        for c in range(nc):
            if ink <= 0:
                break
            hc = hash16(seed, c, 94)
            yb = 98 + c * 18 + imod(hc, 9)             # baseline (front lowest)
            ph1 = imod(hc >> 4, 256)
            ph2 = imod(hc >> 7, 256)
            lb = 10 + idiv(rec.act_units, 110)          # ray height grows all day
            if lb > 34:
                lb = 34
            if c > 0:
                lb = idiv(lb * 3, 4)                    # back curtains shorter
            col = X0
            while col <= X1:
                h = hash16(seed, c * 512 + col, 95)
                y = (yb + idiv(10 * isin(col * 2 + ph1), 127)
                        + idiv(5 * isin(col * 5 + ph2), 127))
                ln = (lb + idiv(idiv(lb, 2) * isin(col * 3 + ph2), 127)
                         + imod(h, 3))
                if ln < 4:
                    ln = 4
                if lut is not None:
                    bright = zone_color(lut[hash16(seed, c * 64 + idiv(col, 16),
                                                   96) & (ZLUT - 1)])
                else:
                    bright = COLOR_GREEN
                body = DIMBODY.get(bright, COLOR_DK_GREEN)
                dc.setColor(body, COLOR_TRANSPARENT)
                dc.drawLine(col, y - ln, col, y - idiv(ln, 4))
                dc.setColor(bright, COLOR_TRANSPARENT)
                dc.drawLine(col, y - idiv(ln, 4), col, y)
                ink -= 2
                if ink <= 0:
                    break
                col += STEP

        # --- episodes: coronal bursts high in the sky (dodging the moon) ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            he = hash16(seed, e, 97)
            x = CX - 74 + imod(he, 149)
            y = 68 + imod(he >> 7, 18)
            if mr > 0 and mside * (x - CX) > 20:
                x = CX - (x - CX)              # keep bursts off the moon's side
            mag = rec.emag[e]
            ln = 3 + idiv(mag, 18)
            if ln > 11:
                ln = 11
            zc = rec.epz[e]
            dc.setColor(zone_color(zc), COLOR_TRANSPARENT)
            for k in range(5):
                a = imod(idiv(k * 256, 5) + imod(he >> 4, 21), 256)
                dc.drawLine(x + idiv(2 * isin(a + 64), 127),
                            y + idiv(2 * isin(a), 127),
                            x + idiv(ln * isin(a + 64), 127),
                            y + idiv(ln * isin(a), 127))
                ink -= 1
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 1 if mag >= 40 else 0)
            ink -= 1


def build():
    return {"background": COLOR_BLACK, "components": [Aurora()]}
