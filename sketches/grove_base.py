#!/usr/bin/env python3
"""grove_base -- the moss_grove cushion+colony hybrid, parametrized for the
tuft-colour and sleep-seed explorations.

make(tuft_mode, sleep_mode) returns a scrub build() dict.

tuft_mode -- how the satellite tufts take colour from the day's HR:
  'green'  baseline: tufts stay green (the committed moss_grove look)
  'tips'   green body, the OUTER grains tinted by the DOMINANT zone (coloured
           tips, as if the exertion colour rimes the moss)
  'tint'   green body shot through with DOMINANT-zone highlight grains (the
           whole tuft glows with the day's main effort colour)
  'histo'  EACH tuft takes its own zone (sampled from the histogram), so the
           tufts collectively show the spread of zones across the day

sleep_mode -- how last night's inferred sleep (daysoma.sleep_seed) shows:
  'none'   no sleep visual
  'core'   a spore clump at the centre UNDER the cushion, sized by hours slept
           and coloured by sleep quality (cool = rested) -- BioBloom-faithful;
           the day's growth overgrows it
  'crown'  the cushion's bright inner crown is coloured by sleep quality (the
           moss's heart glows by how well you slept) -- always visible, ambient
  'dew'    a ring of sleep-coloured 'dew' beads around the rim at dawn, count by
           hours slept, that the day's tufts grow among

Per-day cushion SHAPE varies via mossutil.shape_params(seed). Self-bounded by
INK; deterministic from the date seed; time-of-day not encoded.
"""

import daysoma as DS
from daysoma import (zone_color, zone_lut, place, dominant_zone, sleep_slot,
                     SLEEP_RAMP, ZLUT, ACTIVE, CX, CY)
from daybuckets import px, py
from mossutil import edge, fan, shape_params
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)

INK = 340
NA = 30
BASE_DIV = 60
TUFT_DIV = 600


class MossGrove:
    def __init__(self, tuft_mode="green", sleep_mode="none"):
        self.tuft_mode = tuft_mode
        self.sleep_mode = sleep_mode
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    # spore clump under the cushion (sleep 'core'); BioBloom-style scatter
    def draw_core(self, dc, mins, ink):
        if mins <= 0:
            return ink
        hours = idiv(mins, 60)
        slot = sleep_slot(mins)
        reach = 6 + 2 * hours
        if reach > 28:
            reach = 28
        rim = idiv(reach * 2, 3)
        dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, 3)
        nodes = 7 + hours * 2
        for k in range(nodes):
            if ink <= 0:
                break
            h = hash16(91, k, 6)
            a = imod(idiv(k * 256, nodes) + (h % 36), 256)
            r1 = imod(hash16(73, k, 2), reach)
            r2 = imod(hash16(29, k, 4), reach)
            rr = 2 + (r1 if r1 < r2 else r2)
            ci = slot
            if rr >= rim and slot >= 1:
                ci = slot - 1
            dc.setColor(SLEEP_RAMP[ci], COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1 + (h % 3))
            ink -= 1
        return ink

    # one colony tuft (solid blob + stipple); accent applies the HR colour
    def tuft(self, dc, seed, j, tx, ty, tsize, accent, tips, ink):
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
            col = COLOR_GREEN if (h & 1) else COLOR_DK_GREEN
            if accent is not None:
                if tips:
                    if rr2 * 5 >= tsize * 3 and ((h >> 6) & 1) == 0:
                        col = accent           # outer grains only -> coloured tips
                elif ((h >> 6) & 3) != 0:
                    col = accent               # most grains -> tuft glows the colour
            elif ((h >> 6) & 7) == 0:
                col = COLOR_YELLOW             # baseline amber highlight
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
        sp = shape_params(seed)               # per-day lumpy outline
        # 'histo' samples each tuft from the ELEVATED-zone spread (what hard zones
        # the day hit); 'tips'/'tint' use the dominant ELEVATED zone. Both fall
        # back to the overall dominant when the day never got the HR up.
        elut = zone_lut(rec, ACTIVE)
        dz = dominant_zone(rec, ACTIVE)
        if dz < 0:
            dz = dominant_zone(rec)
        dzcol = zone_color(dz) if dz >= 0 else None
        act = rec.act_units

        base = 4 + idiv(act, BASE_DIV)
        if base > 54:
            base = 54
        ntuft = idiv(act, TUFT_DIV)
        if ntuft > 7:
            ntuft = 7
        tsize = 7 + idiv(act, 320)
        if tsize > 16:
            tsize = 16

        # --- sleep 'core': spore clump first, under the cushion ---
        if self.sleep_mode == "core":
            ink = self.draw_core(dc, rec.sleep_seed, ink)

        # --- central cushion: dark mound + crown (crown tinted by sleep?) ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 100, NA, sp)
        crown = COLOR_GREEN
        if self.sleep_mode == "crown" and rec.sleep_seed > 0:
            crown = SLEEP_RAMP[sleep_slot(rec.sleep_seed)]
        dc.setColor(crown, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 60, NA, sp)

        # --- satellite tufts straddling the rim ---
        tips = (self.tuft_mode == "tips")
        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(edge(base, a, sp) * (85 + (hj >> 8) % 30), 100)
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            if self.tuft_mode == "green":
                accent = None
            elif self.tuft_mode == "histo":
                accent = zone_color(elut[hj & (ZLUT - 1)]) if elut is not None \
                    else dzcol
            else:                              # 'tips' / 'tint' -> dominant zone
                accent = dzcol
            ink = self.tuft(dc, seed, j, tx, ty, tsize, accent, tips, ink)

        # --- granular texture over the cushion ---
        n = 50 + idiv(act, 12)
        if n > 130:
            n = 130
        for i in range(n):
            if ink <= 0:
                break
            a, rr0, h = place(seed, i, 1, base)
            lim = edge(base, a, sp)
            rr = idiv(rr0 * lim, base) if base > 0 else 0
            if (h & 1) == 0:
                col = COLOR_DK_GREEN
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        # --- sleep 'dew': ring of sleep-coloured beads around the rim ---
        if self.sleep_mode == "dew" and rec.sleep_seed > 0:
            slot = sleep_slot(rec.sleep_seed)
            ndew = 6 + idiv(rec.sleep_seed, 60)
            if ndew > 16:
                ndew = 16
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            for k in range(ndew):
                if ink <= 0:
                    break
                a = imod(idiv(k * 256, ndew) + (hash16(seed, k, 71) & 7), 256)
                e = edge(base, a, sp) + 3
                dc.fillCircle(px(CX, e, a), py(CY, e, a), 1)
                ink -= 1

        # --- fuzzy rim fringe ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        for i in range(0, NA, 2):
            if ink <= 0:
                break
            a = imod(idiv(i * 256, NA), 256)
            e = edge(base, a, sp)
            le = 2 + (hash16(seed, i, 9) & 1)
            dc.drawLine(px(CX, e, a), py(CY, e, a),
                        px(CX, e + le, a), py(CY, e + le, a))
            ink -= 1

        # --- episodes: bright fruiting beads on tufts (else crown) ---
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            bead = 2 + idiv(mag, 16)
            if bead > 4:
                bead = 4
            if ntuft > 0:
                t = imod(hash16(seed, e, 41), ntuft)
                hj = hash16(seed, t, 31)
                ta = imod(idiv(t * 256, ntuft) + (hj & 31), 256)
                trr = idiv(edge(base, ta, sp) * (85 + (hj >> 8) % 30), 100)
                tx = px(CX, trr, ta)
                ty = py(CY, trr, ta)
                he = hash16(seed, e, 42)
                off = idiv(tsize, 2) + (he >> 8) % 3
                a = he & 0xFF
                x = tx + idiv(off * isin(a + 64), 127)
                y = ty + idiv(off * isin(a), 127)
            else:
                a = imod(hash16(seed, e, 42), 256)
                rr = idiv(edge(base, a, sp) * 3, 5)
                x = px(CX, rr, a)
                y = py(CY, rr, a)
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead + 1)
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 2


def make(tuft_mode="green", sleep_mode="none"):
    return {"background": COLOR_BLACK,
            "components": [MossGrove(tuft_mode, sleep_mode)]}
