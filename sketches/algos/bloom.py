#!/usr/bin/env python3
"""Concept B -- "filament bloom": wandering radial threads grow from the
centre outward and branch when effort is climbing. Neuron / mycelium feel
without being literal.

  thread length    = accumulated growth (centre -> rim over the day)
  segment colour   = HR zone that minute               (flag D5)
  branching/count  = HR trend rising => reaching out    (flag D6)
  wander amplitude = HR variability                     (flag D7)
  growth stalls    = idle / move-bar dormancy           (flag 9 / D12)
"""
from device import (idiv, imod, isin, hash16, zoneIndex, ZONE_COLORS,
                    COLOR_BLACK, COLOR_DK_GRAY)

CX, CY = 107, 90
R0, RMAX = 7, 86
UNIT = 64
BASE = 1
KACT = 6
STEP = 2            # px of radius per appended vertex
KMAX = 28           # cap on live filaments
SEEDS = 10          # initial filaments, spread evenly around the centre


class Bloom:
    def __init__(self):
        self.frontq = R0 * UNIT
        self.next = R0 + STEP
        self.prev = None
        self.win = []
        self.fil = []
        for i in range(SEEDS):
            a = imod(idiv(i * 256, SEEDS) + imod(hash16(91, i, 5), 18), 256)
            self.fil.append({"a": a, "pts": [self._pt(a, R0, COLOR_DK_GRAY)]})

    def _pt(self, a, r, c):
        x = CX + idiv(r * isin(a + 64), 127)
        y = CY + idiv(r * isin(a), 127)
        return (x, y, c)

    def advance(self, snap):
        steps = snap.steps or 0
        if self.prev is None:
            self.prev = steps
        spm = steps - self.prev
        if spm < 0:
            spm = 0
        self.prev = steps

        hr = snap.heartRate
        z = zoneIndex(hr)
        cur = hr if hr is not None else 0
        self.win.append(cur)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)                 # D7
        rising = len(self.win) >= 6 and cur - self.win[0] >= 8  # D6

        grow = BASE + idiv(spm, KACT)
        self.frontq += grow
        if self.frontq > RMAX * UNIT:
            self.frontq = RMAX * UNIT
        r = idiv(self.frontq, UNIT)
        color = COLOR_DK_GRAY if spm <= 1 else ZONE_COLORS[z]

        while r >= self.next and self.next <= RMAX:
            rr = self.next
            amp = 1 + idiv(vrange, 10)
            nf = len(self.fil)
            i = 0
            while i < nf:
                f = self.fil[i]
                da = idiv(isin(hash16(i, rr, 1) & 255) * amp, 127)
                f["a"] = imod(f["a"] + da, 256)
                f["pts"].append(self._pt(f["a"], rr, color))
                i += 1
            if rising and len(self.fil) < KMAX:
                src = self.fil[imod(hash16(rr, nf, 2), nf)]
                na = imod(src["a"] + 12 + imod(hash16(rr, 3, 9), 24), 256)
                self.fil.append({"a": na, "pts": [self._pt(na, rr, color)]})
            self.next += STEP

    def render(self, dc, snap):
        dc.setColor(COLOR_DK_GRAY, COLOR_BLACK)
        dc.drawArc(CX, CY, RMAX + 2, 0, 0, 359)
        for f in self.fil:
            pts = f["pts"]
            k = 1
            while k < len(pts):
                x0, y0, _ = pts[k - 1]
                x1, y1, c = pts[k]
                dc.setColor(c, COLOR_BLACK)
                dc.drawLine(x0, y0, x1, y1)
                k += 1

    def state_bytes(self):
        return sum(len(f["pts"]) for f in self.fil) * 3


def build():
    return {"background": COLOR_BLACK, "components": [Bloom()]}
