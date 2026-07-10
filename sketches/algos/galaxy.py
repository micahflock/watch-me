#!/usr/bin/env python3
"""Concept B -- "galaxy": the day as a tilted spiral galaxy.

Not the old diffuse-scatter nebula: this has STRUCTURE -- two or three stipple
spiral arms wind out of a bright core, seen at an inclination (y squashed 5/8),
which happens to fit the wide art window exactly. Distinctly cosmic, nothing
cellular about it.

  arm length / dot density  <- act_units (the arms WIND OUTWARD as you move)
  arm dot colour            <- the day's HR-zone mix (zone_lut); calm days are
                               blue-violet gas, hard days run hot; sparse
                               LT_GRAY/WHITE foreground stars for sparkle
  episodes                  <- star clusters ON the arms: dim halo + peak-zone
                               core + white centre + diffraction spikes, sized
                               by magnitude
  sleep                     <- the galactic core bulge: size = hours slept,
                               colour = SLEEP_RAMP quality; each 0-6am wake
                               cuts a dark DUST LANE across the bulge
  day seed                  <- arm count (2-3), winding rate, rotation, spin
                               direction -- tomorrow's galaxy is a different one

Integer-only; self-bounded by INK. Fixed background starfield is 22 dots.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_DK_RED, COLOR_DK_BLUE, COLOR_BLUE, COLOR_PURPLE)

CX, CY = 107, 108
INK = 380
SPREAD = 82            # max arm radius (x); y is squashed 5/8 (inclination)
SQN, SQD = 5, 8
COOL = [COLOR_DK_BLUE, COLOR_BLUE, COLOR_PURPLE]

DIMHALO = {0: COLOR_DK_BLUE, 1: COLOR_DK_BLUE, 2: COLOR_DK_BLUE,
           3: COLOR_DK_BLUE, 4: COLOR_DK_RED, 5: COLOR_DK_RED,
           6: COLOR_DK_RED, 7: COLOR_DK_RED, 8: COLOR_DK_RED}


def gx(r, a):
    return CX + idiv(r * isin(a + 64), 127)


def gy(r, a):
    return CY + idiv(idiv(r * isin(a), 127) * SQN, SQD)


class Galaxy:
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

        h0 = hash16(seed, 1, 61)
        na = 2 + (h0 & 1)                      # 2 or 3 arms
        rot = imod(h0 >> 4, 256)
        wind = 3 + imod(h0 >> 8, 2)            # winding rate (1/256 turn / step)
        dirn = 1 if (h0 & 4) else -1
        mcap = idiv(228, na)                   # per-arm dot cap
        m = 8 + idiv(rec.act_units, 42)        # arms wind outward all day; only
        if m > mcap:                           # a big day (~3000 units) fills them
            m = mcap

        # --- background starfield (fixed, faint) ---
        for i in range(22):
            if ink <= 0:
                break
            h = hash16(seed, i, 62)
            x = CX - 84 + imod(h, 169)
            y = CY - 44 + imod(h >> 7, 89)
            dc.setColor(COLOR_LT_GRAY if imod(h >> 5, 5) == 0 else COLOR_DK_GRAY,
                        COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 0)
            ink -= 1

        # --- spiral arms: stipple winding out of the core ---
        for arm in range(na):
            a0 = rot + idiv(arm * 256, na)
            for t in range(m):
                if ink <= 0:
                    break
                h = hash16(seed, arm * 256 + t, 63)
                r = 7 + idiv(t * (SPREAD - 7), mcap)
                a = imod(a0 + dirn * t * wind + imod(h, 5) - 2, 256)
                x = gx(r, a) + imod(h >> 5, 7) - 3
                y = gy(r, a) + imod(h >> 8, 5) - 2
                if lut is not None:
                    col = zone_color(lut[h & (ZLUT - 1)])
                else:
                    col = COOL[imod(h >> 3, 3)]
                if imod(h >> 9, 9) == 0:
                    col = COLOR_LT_GRAY
                if imod(h >> 6, 23) == 0:
                    col = COLOR_WHITE
                dc.setColor(col, COLOR_TRANSPARENT)
                dc.fillCircle(x, y, 1 if imod(h >> 4, 6) == 0 else 0)
                ink -= 1

        # core-bulge radius (needed as a cluster keep-out before it is drawn)
        mins = rec.sleep_seed
        rc = 4 + idiv(mins, 60) * 2
        if rc > 22:
            rc = 22
        if mins <= 0:
            rc = 0

        # --- episodes: star clusters embedded in the arms ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            he = hash16(seed, e, 64)
            arm = imod(he, na)
            t = 4 + imod(he >> 4, m - 4 if m > 4 else 1)
            r = 7 + idiv(t * (SPREAD - 7), mcap)
            mag = rec.emag[e]
            s = 2 + idiv(mag, 22)
            if s > 7:
                s = 7
            if r < rc + s + 5:                 # stay clear of the core bulge
                r = rc + s + 5
            a = imod(rot + idiv(arm * 256, na) + dirn * t * wind, 256)
            x = gx(r, a)
            y = gy(r, a)
            zc = rec.epz[e]
            dc.setColor(DIMHALO[zc], COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s + 2)
            dc.setColor(zone_color(zc), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s)
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 0)
            # short diffraction ticks just outside the disc
            dc.drawLine(x - s - 4, y, x - s - 1, y)
            dc.drawLine(x + s + 1, y, x + s + 4, y)
            dc.drawLine(x, y - s - 3, x, y - s - 1)
            dc.drawLine(x, y + s + 1, x, y + s + 3)
            ink -= 7

        # --- sleep: the core bulge (last; it owns the centre) ---
        if mins > 0:
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            ry = idiv(rc * SQN, SQD)
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, ry + 2)               # clear a halo
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            dc.fillCircle(CX - idiv(rc, 2), CY, idiv(ry * 3, 4))
            dc.fillCircle(CX + idiv(rc, 2), CY, idiv(ry * 3, 4))
            dc.fillCircle(CX, CY, ry)                   # lozenge bulge
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, 1 + idiv(rc, 8))      # hot nucleus
            ink -= 5
            # wakes: dark dust lanes scarring the bulge
            for w in range(rec.wake_seed):
                if ink <= 0:
                    break
                hw = hash16(53, w, 65)
                dy = imod(hw, 2 * ry - 3 if ry > 1 else 1) - (ry - 2)
                tilt = imod(hw >> 6, 5) - 2
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.drawLine(CX - rc - 2, CY + dy - tilt,
                            CX + rc + 2, CY + dy + tilt)
                dc.drawLine(CX - rc - 2, CY + dy - tilt + 1,
                            CX + rc + 2, CY + dy + tilt + 1)
                ink -= 2


def build():
    return {"background": COLOR_BLACK, "components": [Galaxy()]}
