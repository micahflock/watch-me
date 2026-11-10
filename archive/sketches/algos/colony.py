#!/usr/bin/env python3
"""Concept C -- "colony": a stippled mould/lichen colony creeps outward from
the centre, denser where you moved, rougher where HR swung.

  colony radius = accumulated growth (centre -> rim)
  dot colour    = HR zone that minute                  (flag D5)
  dot count     = steps that minute (volume)
  edge scatter  = HR variability roughens the front    (flag D7)
  sparse/grey   = idle / move-bar dormancy             (flag 9 / D12)

Dots are not stored individually: each depositing minute records a compact
event (radius, count, colour, scatter, salt) and render re-derives the dot
positions by hash -- low RAM, deterministic, port-faithful.
"""
from device import (idiv, imod, isin, hash16, zoneIndex, ZONE_COLORS,
                    COLOR_BLACK, COLOR_DK_GRAY)

CX, CY = 107, 90
R0, RMAX = 7, 86
UNIT = 64
BASE = 1
KACT = 6
DOTCAP = 3600


class Colony:
    def __init__(self):
        self.frontq = R0 * UNIT
        self.events = []
        self.prev = None
        self.win = []
        self.total = 0

    def advance(self, snap):
        steps = snap.steps or 0
        if self.prev is None:
            self.prev = steps
        spm = steps - self.prev
        if spm < 0:
            spm = 0
        self.prev = steps
        idle = spm <= 1

        hr = snap.heartRate
        z = zoneIndex(hr)
        self.win.append(hr if hr is not None else 0)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)            # D7

        grow = BASE + idiv(spm, KACT)
        self.frontq += grow
        if self.frontq > RMAX * UNIT:
            self.frontq = RMAX * UNIT
        r = idiv(self.frontq, UNIT)

        n = 1 + idiv(spm, 16)
        if n > 12:
            n = 12
        color = COLOR_DK_GRAY if idle else ZONE_COLORS[z]
        scatter = 2 + idiv(vrange, 4)
        if self.total < DOTCAP:
            salt = imod(hash16(snap.minute or 0, r, n + 1), 4096)
            self.events.append((r, n, color, scatter, salt))
            self.total += n

    def render(self, dc, snap):
        dc.setColor(COLOR_DK_GRAY, COLOR_BLACK)
        dc.drawArc(CX, CY, RMAX + 2, 0, 0, 359)
        for (r, n, color, scatter, salt) in self.events:
            dc.setColor(color, COLOR_BLACK)
            k = 0
            while k < n:
                a = imod(hash16(salt, k, 1), 256)
                rr = r - imod(hash16(salt, k, 2), scatter + 1)
                x = CX + idiv(rr * isin(a + 64), 127)
                y = CY + idiv(rr * isin(a), 127)
                dc.fillCircle(x, y, 1)
                k += 1

    def state_bytes(self):
        return len(self.events) * 6


def build():
    return {"background": COLOR_BLACK, "components": [Colony()]}
