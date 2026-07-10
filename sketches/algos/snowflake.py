#!/usr/bin/env python3
"""Concept D -- "snowflake": the day crystallises as a six-fold dendrite.

One arm's branchlet pattern is hashed from the date and mirrored six ways --
the literal "no two alike" object, pure crystal geometry (spines, fishbone
branchlets, rime), nothing organic or cellular about it.

  arm length + branchlets   <- act_units (the crystal GROWS OUTWARD all day;
                               a lazy day is a small stellar plate, a big day
                               a full fern-dendrite)
  rime dots along the arms  <- the day's HR-zone mix (zone_lut): a hard day's
                               warmth glows inside the ice; absent before any
                               HR history (clear ice)
  episodes                  <- gems frozen into single arms (symmetry breaks,
                               so they read as events): dim ring + peak-zone
                               fill, sized by magnitude
  sleep                     <- the hexagonal core plate: radius = hours,
                               colour = SLEEP_RAMP quality; each 0-6am wake
                               drives a black CRACK across the plate
  day seed                  <- branchlet spacing/length/angle + rotation: a
                               different crystal every day (fxhash principle)

Integer-only. The arm geometry is computed ONCE into small tables, then
rendered six times through per-arm unit vectors (2 isin per arm), so the
six-fold symmetry costs almost nothing extra. Self-bounded by INK.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from device import (idiv, imod, hash16, isin, account, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_DK_RED, COLOR_DK_BLUE, COLOR_BLUE, COLOR_PURPLE)

CX, CY = 107, 108
INK = 380
NBMAX = 9              # branchlet pairs per arm (table cap)
SQN, SQD = 7, 8        # slight vertical squash so full arms clear the window

DIM = {0: COLOR_DK_BLUE, 1: COLOR_DK_BLUE, 2: COLOR_DK_BLUE, 3: COLOR_DK_BLUE,
       4: COLOR_DK_RED, 5: COLOR_DK_RED, 6: COLOR_DK_RED, 7: COLOR_PURPLE,
       8: COLOR_PURPLE}


class Snowflake:
    def __init__(self):
        self.rec = DS.DayRecord()
        self._bd = [0] * NBMAX      # branchlet base distance along the spine
        self._bl = [0] * NBMAX      # branchlet length
        self._hex = [[0, 0] for _ in range(6)]

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def _pt(self, ux, uy, vx, vy, d, p):
        x = CX + idiv(d * ux + p * vx, 127)
        y = CY + idiv(idiv(d * uy + p * vy, 127) * SQN, SQD)
        return x, y

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)

        h0 = hash16(seed, 1, 81)
        rot = imod(h0, 43)                     # arm 0 anywhere in one sextant
        beta = 38 + imod(h0 >> 6, 8)           # branch angle ~53-64 deg
        arml = 14 + idiv(rec.act_units, 68)    # the crystal grows all day; only
        if arml > 52:                          # a big day reaches full dendrite
            arml = 52

        # branchlet table (shared by all six arms -- the crystal symmetry)
        nb = idiv(arml - 10, 5)
        if nb > NBMAX:
            nb = NBMAX
        for i in range(nb):
            account(1)
            hb = hash16(seed, i, 82)
            self._bd[i] = 9 + idiv(i * (arml - 11), nb if nb > 0 else 1)
            pct = 30 + imod(hb, 46)
            self._bl[i] = 2 + idiv((arml - self._bd[i]) * pct, 100)

        # --- six arms ---
        for k in range(6):
            if ink <= 0:
                break
            ak = imod(rot + idiv(k * 256, 6), 256)
            ux, uy = isin(ak + 64), isin(ak)
            bp, bq = imod(ak + beta, 256), imod(ak - beta, 256)
            pxp, pyp = isin(bp + 64), isin(bp)
            pxm, pym = isin(bq + 64), isin(bq)
            # spine
            x0, y0 = self._pt(ux, uy, 0, 0, 7, 0)
            x1, y1 = self._pt(ux, uy, 0, 0, arml, 0)
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.drawLine(x0, y0, x1, y1)
            ink -= 1
            # fishbone branchlets (mirrored pair per table entry)
            for i in range(nb):
                if ink <= 0:
                    break
                bx, by = self._pt(ux, uy, 0, 0, self._bd[i], 0)
                l = self._bl[i]
                dc.setColor(COLOR_BLUE if (i & 1) else COLOR_LT_GRAY,
                            COLOR_TRANSPARENT)
                dc.drawLine(bx, by, bx + idiv(l * pxp, 127),
                            by + idiv(idiv(l * pyp, 127) * SQN, SQD))
                dc.drawLine(bx, by, bx + idiv(l * pxm, 127),
                            by + idiv(idiv(l * pym, 127) * SQN, SQD))
                ink -= 2
            # arm tip jewel point
            dc.setColor(COLOR_BLUE, COLOR_TRANSPARENT)
            dc.fillCircle(x1, y1, 0)
            ink -= 1

        # --- rime: the day's HR mix as dots frozen along the arms ---
        if lut is not None:
            nr = 12 + idiv(rec.act_units, 70)
            if nr > 48:
                nr = 48
            for i in range(nr):
                if ink <= 0:
                    break
                h = hash16(seed, i, 83)
                ak = imod(rot + idiv(imod(h, 6) * 256, 6), 256)
                ux, uy = isin(ak + 64), isin(ak)
                vx, vy = -uy, ux
                d = 8 + imod(h >> 4, arml - 8 if arml > 8 else 1)
                p = imod(h >> 8, 7) - 3
                x, y = self._pt(ux, uy, vx, vy, d, p)
                dc.setColor(zone_color(lut[h & (ZLUT - 1)]), COLOR_TRANSPARENT)
                dc.fillCircle(x, y, 1 if imod(h >> 6, 3) == 0 else 0)
                ink -= 1

        # core-plate radius (needed as a gem keep-out before it is drawn)
        mins = rec.sleep_seed
        rh = 4 + idiv(mins, 60) * 2
        if rh > 18:
            rh = 18
        if mins <= 0:
            rh = 0

        # --- episodes: gems frozen into single arms ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            he = hash16(seed, e, 84)
            ak = imod(rot + idiv(imod(he, 6) * 256, 6), 256)
            ux, uy = isin(ak + 64), isin(ak)
            mag = rec.emag[e]
            s = 2 + idiv(mag, 24)
            if s > 6:
                s = 6
            dlo = rh + s + 3
            span = arml - dlo - 2
            d = dlo + (imod(he >> 4, span) if span > 0 else 0)
            x, y = self._pt(ux, uy, 0, 0, d, 0)
            zc = rec.epz[e]
            dc.setColor(DIM[zc], COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s + 1)
            dc.setColor(zone_color(zc), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s)
            if mag >= 40:
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(x - 1, y - 1, 0)
                ink -= 1
            ink -= 2

        # --- sleep: hexagonal core plate, cracked by wakes ---
        if mins > 0:
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            hx = self._hex
            for k in range(6):
                a = imod(rot + 21 + idiv(k * 256, 6), 256)
                hx[k][0] = CX + idiv(rh * isin(a + 64), 127)
                hx[k][1] = CY + idiv(idiv(rh * isin(a), 127) * SQN, SQD)
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            dc.fillPolygon(hx)
            ink -= 1
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            for k in range(6):
                nk = imod(k + 1, 6)
                dc.drawLine(hx[k][0], hx[k][1], hx[nk][0], hx[nk][1])
            ink -= 6
            for w in range(rec.wake_seed):     # cracks
                if ink <= 0:
                    break
                hw = hash16(53, w, 85)
                a = imod(idiv(w * 256, rec.wake_seed) + imod(hw, 40), 256)
                mx = CX + idiv(idiv(rh, 2) * isin(a + 64), 127) + imod(hw >> 7, 5) - 2
                my = CY + idiv(idiv(rh, 2) * isin(a), 127) + imod(hw >> 9, 3) - 1
                ex = CX + idiv((rh + 1) * isin(a + 64), 127)
                ey = CY + idiv(idiv((rh + 1) * isin(a), 127) * SQN, SQD)
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.drawLine(CX, CY, mx, my)
                dc.drawLine(mx, my, ex, ey)
                ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [Snowflake()]}
