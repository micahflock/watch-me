#!/usr/bin/env python3
"""alt_murmuration -- "Murmuration": today's movement is a flock of starlings,
last night is the birds on the wire.

Concept (docs/alt-faces.md, round 1; the owner liked the original murmuration
sketch, M). Every 60 steps hatches one bird, so the flock grows through the
day -- a morning is a few dozen birds, a big day a cloud that fills the sky.
The flock is ALIVE: its centre, tilt and the travelling fold through it drift
a little every minute, the one thing on the face that moves.

  flock size        steps today (1 bird / 60 steps, cap 300)        [movement]
  warm birds        hatched while HR >= 105 (zone colour)           [effort]
  birds on the wire last night: one per half hour asleep, along a
                    12-hour night ruler (left 21:00 -> right 09:00)  [sleep]
  flying birds      each wake-up lifts the bird at that hour        [wake-ups]
  number            steps today, under the wire
  moon              phase glyph after the date; red tick = north (sun compass)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, imod, hash16, isin, account  # noqa: E402

TITLE = "Murmuration -- your steps as a flock, your night on the wire"
BLURB = ("Black face. Every 60 steps hatches a starling; the flock drifts a little each minute. "
         "Last night's sleep is the row of birds on the wire; a wake-up is a bird in flight.")
LEGEND = [
    "flock = today's steps (1 bird per 60);",
    "  the ribbon grows longer as you move",
    "warm birds = hatched while HR >= 105",
    "wire = 21:00 -> 09:00; 1 bird per half hour asleep",
    "bird in flight above the wire = a wake-up",
    "number = steps today",
    "flock drifts every minute (slow, never jumps)",
    "moon phase after the date; red tick = north",
]

STEPS_PER_BIRD = 60
BMAX = 300
WIRE_X0, WIRE_X1 = 22, 193      # the wire's visible span
NIGHT0 = 60                     # night ruler starts 21:00 (night clock 60)
NIGHT_SPAN = 720                # ... 12 h wide

def wire_y(x):
    """Catenary-ish sag: 148 at the poles, 158 mid-span (integer)."""
    d = x - 107
    return 158 - idiv(10 * d * d, 100 * 100)


class Murmuration:
    def __init__(self):
        self.log = K.DayLog()

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes()

    def render(self, dc, s):
        log = self.log
        t = (s.hour * 60 + s.minute) if s.hour is not None else 0

        # ---- the flock (drawn first; the time sits on top of nothing)
        n = idiv(log.steps, STEPS_PER_BIRD)
        if n > BMAX:
            n = BMAX
        if n > 0:
            self.flock(dc, n, t)

        # ---- the wire + last night's roost
        dc.setColor(K.DK_GRAY, K.TRANSPARENT)
        px, py = WIRE_X0, wire_y(WIRE_X0)
        for x in range(WIRE_X0 + 9, WIRE_X1 + 1, 9):
            y = wire_y(x)
            dc.drawLine(px, py, x, y)
            px, py = x, y
        self.roost(dc)

        # ---- time, date, steps
        ts = K.time_str(s)
        tw = K.text_w(K.DIG57, ts, 5, 4)
        K.draw_text(dc, K.DIG57, ts, 108 - tw // 2, 6, 5, K.WHITE, 4, "dot")
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        x0 = 103 - dw // 2
        K.draw_text(dc, K.SMALL, ds, x0, 46, 2, K.LT_GRAY, 2)
        K.draw_moon(dc, x0 + dw + 9, 50, 4, K.moon_age(s), K.WHITE, K.DK_GRAY)
        K.battery_low(dc, s, x0 - 17, 48)
        ns = str(log.steps)
        nw = K.text_w(K.SMALL, ns, 2, 2)
        K.draw_text(dc, K.SMALL, ns, 108 - nw // 2, 164, 2, K.LT_GRAY, 2)
        K.north_tick(dc, s)

    def flock(self, dc, n, t):
        # The flock is a RIBBON swirling along a slow Lissajous path: bird k
        # sits at u = k / BMAX along it, so the ribbon's LENGTH is the day's
        # steps and the birds stay in hatch order -- an effort's warm birds
        # form one warm stretch, not confetti. The path's phases creep a few
        # 1/256-turns a minute, so the swirl re-forms slowly through the day.
        p1 = idiv(t, 3) + 20
        p2 = idiv(t, 2) + 150
        cum = self.log.cum_steps()
        b = 0
        for k in range(n):
            u = idiv(k * 256, BMAX)                     # 0..255 along the path
            x = 107 + idiv(66 * isin(p1 + idiv(u * 300, 256)), 127)
            y = 101 + idiv(30 * isin(p2 + idiv(u * 470, 256)), 127)
            # thick in the middle of today's ribbon, tapering at both ends
            th = 3 + idiv(12 * isin(idiv(k * 128, n)), 127)
            h = hash16(k, 77, 5)
            x += idiv(((h & 31) - 16) * th, 16)
            y += idiv((((h >> 5) & 31) - 16) * th, 22)
            if y < 58:
                y = 58 + imod(58 - y, 6)                 # keep off the time
            while b < K.NB - 1 and cum[b] < (k + 1) * STEPS_PER_BIRD:
                b += 1
            z = self.log.bzone[b]
            if z >= K.EFFORT:
                col = K.HR_RAMP[z]
            else:
                col = K.WHITE if (h & 0x4000) else K.LT_GRAY
            dc.setColor(col, K.TRANSPARENT)
            if h & 0x0C00:
                dc.fillRectangle(x, y, 2, 2)
            else:
                dc.fillRectangle(x, y, 1, 1)             # a far bird
        account(n + K.NB)

    def roost(self, dc):
        night = self.log.night
        if not night:
            return
        start, end, asleep, wakes = night
        span = end - start
        if span <= 0:
            return
        nb = idiv(asleep + 15, 30)
        lifted = set()
        for w in wakes:
            lifted.add(idiv(w - start, 30))
        for k in range(nb):
            nc = start + k * 30 + 15
            if nc > end:
                nc = end
            x = WIRE_X0 + idiv((nc - NIGHT0) * (WIRE_X1 - WIRE_X0), NIGHT_SPAN)
            y = wire_y(x)
            if k in lifted:
                # a wake-up: the bird is up off the wire, wings in a V
                yy = y - 13
                dc.setColor(K.YELLOW, K.TRANSPARENT)
                dc.drawLine(x - 3, yy - 2, x, yy)
                dc.drawLine(x, yy, x + 3, yy - 2)
                continue
            dc.setColor(K.LT_GRAY, K.TRANSPARENT)
            dc.fillRectangle(x - 1, y - 3, 3, 3)        # body
            dc.fillRectangle(x + 1, y - 4, 1, 1)        # head
            dc.setColor(K.DK_GRAY, K.TRANSPARENT)
            dc.fillRectangle(x - 2, y - 2, 1, 2)        # tail


def build():
    return {"background": K.BLACK, "components": [Murmuration()]}
