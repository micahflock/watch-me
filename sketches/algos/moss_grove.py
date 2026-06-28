#!/usr/bin/env python3
"""moss_grove -- the LOCKED two-worlds V2 biometric visualization.

Configuration chosen across the exploration: tuft colour = dominant ELEVATED
zone ("tint"), sleep = spore nucleus drawn ON TOP ("coretop"). Centred 2/5 up
from the bottom (CY=108), like BioBloom, so the artificial overlay (clock, etc.)
rides above the organism.

This file is the PARITY REFERENCE for core/src/genart/MossGrove.mc (the
strataflock.py role): it mirrors the record (daysoma) + render so the .mc ports
mechanically. The day organism, from the heart out:

  sleep nucleus  last night's inferred sleep -- a spore clump at the centre,
                 size = hours, colour = quality (cool rested / warm short),
                 drawn last so it stays visible all day
  cushion        a solid two-tone lumpy mound; radius grows with the day's total
                 movement; per-day shape from the date seed (shape_params)
  tufts          satellite colony clumps straddling the rim, popping in as
                 activity accrues; grains glow the dominant ELEVATED HR zone
  texture        granular green stipple + fuzzy rim fringe
  episodes       elevated-HR events as bright peak-zone fruiting beads on tufts

Time-of-day is intentionally not encoded. Self-bounded by INK; ~12k VM-instr/
frame (half the ~25k watchdog), ~245 B state.
"""

import daysoma as DS
from daysoma import (zone_color, zone_lut, place, dominant_zone, sleep_slot,
                     SLEEP_RAMP, ZLUT, ACTIVE)
from daybuckets import px, py
from mossutil import edge, fan, shape_params
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)

CX = 107
CY = 108               # 2/5 of the 180px height up from the bottom (BioBloom centre)
INK = 340
NA = 30                # rim samples for the cushion fans
BASE_DIV = 60          # act_units -> cushion radius
TUFT_DIV = 600         # act_units -> one more satellite tuft


class MossGrove:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    # last night's sleep: a spore clump at the centre (BioBloom-style scatter)
    def draw_spore(self, dc, mins, ink):
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

    # one colony tuft: solid blob + stipple; grains glow `accent` (dominant zone)
    def draw_tuft(self, dc, seed, j, tx, ty, tsize, accent, ink):
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
            if accent is not None and ((h >> 6) & 3) != 0:
                col = accent                   # most grains glow the exertion colour
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
        sp = shape_params(seed)                # per-day lumpy outline
        dz = dominant_zone(rec, ACTIVE)        # the day's exertion colour
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

        # --- central cushion: dark mound + bright green crown ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 100, NA, sp)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        fan(dc, CX, CY, base, 60, NA, sp)

        # --- satellite tufts straddling the rim ---
        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(edge(base, a, sp) * (85 + (hj >> 8) % 30), 100)
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            ink = self.draw_tuft(dc, seed, j, tx, ty, tsize, dzcol, ink)

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

        # --- sleep nucleus drawn LAST: stays on top of the colony all day ---
        self.draw_spore(dc, rec.sleep_seed, ink)


def build():
    return {"background": COLOR_BLACK, "components": [MossGrove()]}
