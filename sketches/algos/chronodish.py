#!/usr/bin/env python3
"""Concept A -- "chronograph dish": concentric effort-coloured bands accrete
from a grey sleep-core at the centre out to the rim over the day. Looking
straight down into the dish; the day is read radially.

  radius      = accumulated growth (centre = midnight, rim = late night)
  band colour = HR zone that minute                    (flag D5)
  band width  = minutes spent at that effort (duration/volume)
  grey band   = idle / move-bar dormancy               (flag 9 / D12)
  band jitter = HR variability widens growth slightly  (flag D7)

No within-minute animation: each once-a-minute onUpdate repaints the disc one
band thicker than before. 14-colour palette only.
"""
from device import (idiv, zoneIndex, ZONE_COLORS,
                    COLOR_BLACK, COLOR_DK_GRAY)

CX, CY = 107, 90
R0, RMAX = 6, 86
UNIT = 64            # fixed-point: radius carried in 1/64 px
BASE = 1            # baseline growth (units/min) -- a still day still fills partway
KACT = 6            # larger => activity widens bands less
IDLE_MIN = 12       # minutes of stillness before a grey dormancy band forms


class ChronoDish:
    def __init__(self):
        self.frontq = R0 * UNIT
        self.col = [None] * (RMAX + 1)
        self.prev = None
        self.idle = 0
        self.win = []

    def advance(self, snap):
        steps = snap.steps or 0
        if self.prev is None:
            self.prev = steps
        spm = steps - self.prev
        if spm < 0:
            spm = 0
        self.prev = steps

        if spm <= 1:
            self.idle += 1
        else:
            self.idle = 0

        hr = snap.heartRate
        z = zoneIndex(hr)
        self.win.append(hr if hr is not None else 0)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)        # D7

        grow = BASE + idiv(spm, KACT)
        if grow > 900:
            grow = 900
        oldr = idiv(self.frontq, UNIT)
        self.frontq += grow
        if self.frontq > RMAX * UNIT:
            self.frontq = RMAX * UNIT
        newr = idiv(self.frontq, UNIT)

        color = COLOR_DK_GRAY if self.idle >= IDLE_MIN else ZONE_COLORS[z]
        r = oldr + 1
        while r <= newr:
            if 0 <= r <= RMAX:
                self.col[r] = color
            r += 1

    def render(self, dc, snap):
        dc.setColor(COLOR_DK_GRAY, COLOR_BLACK)
        dc.drawArc(CX, CY, RMAX + 2, 0, 0, 359)       # faint dish rim
        front = idiv(self.frontq, UNIT)
        r = front
        while r >= R0:                                # outer -> inner solid discs
            c = self.col[r]
            if c is not None:
                dc.setColor(c, COLOR_BLACK)
                dc.fillCircle(CX, CY, r)
            r -= 1

    def state_bytes(self):
        return RMAX + 1                               # 1 palette byte per radius


def build():
    return {"background": COLOR_BLACK, "components": [ChronoDish()]}
