#!/usr/bin/env python3
"""Concept A -- "sunflower": the day as a phyllotaxis bloom.

Vogel's model: floret i sits at angle i*DIVERGENCE, radius ~ sqrt(i) -- the
sunflower-head packing. Nothing blobby or cellular: the eye reads interlocking
spiral arcs (parastichies), a crisply mathematical-yet-botanical structure.

  head radius + floret count  <- act_units (the head FILLS OUTWARD as you move)
  floret colour               <- the day's HR-zone mix (zone_lut), cool fallback
  petal ring                  <- dominant elevated zone colours the petals; a
                                 rest day grows a cool "moonflower" instead
  episodes                    <- dew berries set INTO the spiral at hashed
                                 floret slots: dark ring + peak-zone fill +
                                 white glint, sized by magnitude
  sleep                       <- the seed disc at the centre: radius = hours,
                                 colour = SLEEP_RAMP quality; each 0-6am wake
                                 pecks a black bite out of the disc rim
  day seed                    <- divergence angle preset + rotation + petal
                                 count: consecutive days give visibly different
                                 spiral families (the fxhash principle)

Integer-only (idiv/imod/hash16/isin); sqrt(i) is maintained INCREMENTALLY in
fixed point across the floret loop (total increments = final k, charged via
account), so there is no per-floret sqrt. Self-bounded by INK.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, account, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_RED, COLOR_DK_RED, COLOR_ORANGE, COLOR_YELLOW,
                    COLOR_GREEN, COLOR_DK_GREEN, COLOR_BLUE, COLOR_DK_BLUE,
                    COLOR_PURPLE, COLOR_PINK)

CX, CY = 107, 108      # art-field centre shared with the shipped face
INK = 380

# divergence presets (1/256 turn): 98 ~ golden angle (sunflower), neighbours
# give distinct spiral families -- each day picks one.
DIVS = [98, 97, 99, 158, 105]

# bright -> dim pairs for petal shading (14-colour palette only)
DIM = {COLOR_RED: COLOR_DK_RED, COLOR_PINK: COLOR_PURPLE,
       COLOR_PURPLE: COLOR_DK_BLUE, COLOR_ORANGE: COLOR_DK_RED,
       COLOR_YELLOW: COLOR_ORANGE, COLOR_GREEN: COLOR_DK_GREEN,
       COLOR_DK_GREEN: COLOR_DK_GRAY, COLOR_BLUE: COLOR_DK_BLUE,
       COLOR_DK_BLUE: COLOR_DK_GRAY}

COOL = [COLOR_DK_BLUE, COLOR_PURPLE]        # floret tint before any HR history


class Sunflower:
    def __init__(self):
        self.rec = DS.DayRecord()
        self._tri = [[0, 0], [0, 0], [0, 0]]

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

        # head radius and floret count grow with total movement (a full head
        # needs a genuinely big day: ~3200 act units)
        rad = 10 + idiv(rec.act_units, 130)
        if rad > 34:
            rad = 34
        n = 14 + idiv(rad * rad, 5)
        if n > 240:
            n = 240
        rot = imod(seed, 256)
        div = DIVS[imod(hash16(seed, 2, 51), 5)]
        # fixed-point sqrt scale: kmax ~ sqrt(n<<8) = rad*sqrt(256/5)/... derived
        # from the same n(rad) law so the newest floret always sits at the rim.
        kmax = 20 + idiv(rad * 229, 32)

        # --- petal ring (drawn first, florets overlap the petal bases) ---
        dz = DS.dominant_zone(rec, DS.ACTIVE)
        if dz < 0:
            dz = DS.dominant_zone(rec, 0)
        pcol = zone_color(dz) if dz >= 0 else COLOR_DK_BLUE
        pdim = DIM.get(pcol, COLOR_DK_GRAY)
        npet = 12 + imod(hash16(seed, 3, 52), 4)
        plen = 6 + idiv(rec.act_units, 320)
        if plen > 16:
            plen = 16
        half = idiv(128, npet)                 # petal half-width from the count
        for p in range(npet):                  # back whorl (dim, offset half a
            if ink <= 0:                       # step -- real sunflowers layer)
                break
            hp = hash16(seed, p, 53)
            a = imod(rot + half + idiv(p * 256, npet) + imod(hp, 5), 256)
            self._petal(dc, a, rad - 3, plen + imod(hp >> 8, 3), half, pdim)
            ink -= 1
        for p in range(npet):                  # front whorl (bright)
            if ink <= 0:
                break
            hp = hash16(seed, p, 58)
            a = imod(rot + idiv(p * 256, npet) + imod(hp, 5), 256)
            self._petal(dc, a, rad - 2, plen - 2 + imod(hp >> 8, 3), half - 1,
                        pcol)
            ink -= 1

        # --- florets: the phyllotaxis spiral, centre -> rim ---
        k = 0                                  # k ~ sqrt(i)<<4 (fixed point)
        for i in range(n):
            if ink <= 0:
                break
            tgt = i << 8
            while (k + 1) * (k + 1) <= tgt:    # total increments over the whole
                k += 1                         # loop = final k (~250), not per-i
                account(1)
            rr = idiv(rad * k, kmax)
            a = imod(rot + i * div, 256)
            h = hash16(seed, i, 54)
            if lut is not None:
                col = zone_color(lut[h & (ZLUT - 1)])
            else:
                col = COOL[h & 1]
            if (h >> 9) % 11 == 0:
                col = COLOR_LT_GRAY            # sparse glints
            dc.setColor(col, COLOR_TRANSPARENT)
            sz = 1 if imod(h >> 5, 3) else 0
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), sz)
            ink -= 1

        # sleep-disc radius (needed as a bead keep-out before it is drawn)
        mins = rec.sleep_seed
        hours = idiv(mins, 60)
        rd = 4 + idiv(hours * 3, 2)
        if rd > 19:
            rd = 19
        if rd > rad - 4:
            rd = rad - 4                       # a young head is mostly bud
        if mins <= 0:
            rd = 0

        # --- episodes: dew berries in the floret band (no per-bead sqrt: a
        # hashed radius between the seed disc and the rim costs O(1) and the
        # heavy-day scrub showed the exact-spiral-slot version tripping the
        # watchdog proxy on its 16 standalone isqrt calls) ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            he = hash16(seed, e, 55)
            mag = rec.emag[e]
            s = 2 + idiv(mag, 22)
            if s > 7:
                s = 7
            rlo = rd + s + 2                   # stay clear of the seed disc
            span = rad - 2 - rlo
            rr = rlo + (imod(he >> 4, span) if span > 0 else 0)
            a = imod(rot + he * div, 256)
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            core = zone_color(rec.epz[e])
            dc.setColor(DIM.get(core, COLOR_DK_GRAY), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s + 1)
            dc.setColor(core, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s)
            if mag >= 40:
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(x - idiv(s, 3), y - idiv(s, 3), 0)
                ink -= 1
            ink -= 2

        # --- sleep: the seed disc at the centre (drawn last, stays on top) ---
        if mins > 0:
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, rd + 1)              # separation ring
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, rd)
            # seed stipple (sunflower heart texture)
            ns = 5 + hours
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
            for j in range(ns):
                if ink <= 0:
                    break
                h = hash16(77, j, 56)
                a = imod(h, 256)
                r2 = imod(h >> 8, rd - 2 if rd > 2 else 1)
                dc.fillCircle(px(CX, r2, a), py(CY, r2, a), 0)
                ink -= 1
            # wakes peck bites out of the disc rim
            for w in range(rec.wake_seed):
                if ink <= 0:
                    break
                hw = hash16(53, w, 57)
                a = imod(idiv(w * 256, rec.wake_seed) + imod(hw, 40), 256)
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillCircle(px(CX, rd, a), py(CY, rd, a), 3)
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(px(CX, rd, a), py(CY, rd, a), 0)
                ink -= 2

    # one convex petal triangle: base chord at radius r0, tip at r0+l
    def _petal(self, dc, a, r0, l, halfw, col):
        t = self._tri
        t[0][0] = px(CX, r0, imod(a - halfw, 256))
        t[0][1] = py(CY, r0, imod(a - halfw, 256))
        t[1][0] = px(CX, r0, imod(a + halfw, 256))
        t[1][1] = py(CY, r0, imod(a + halfw, 256))
        t[2][0] = px(CX, r0 + l, a)
        t[2][1] = py(CY, r0 + l, a)
        dc.setColor(col, COLOR_TRANSPARENT)
        dc.fillPolygon(t)


def build():
    return {"background": COLOR_BLACK, "components": [Sunflower()]}
