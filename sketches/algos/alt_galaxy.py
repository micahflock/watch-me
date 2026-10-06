#!/usr/bin/env python3
"""alt_galaxy -- "Galaxy": last night is the core, today's steps are the arms.

Concept (docs/alt-faces.md, round 1; the owner liked the nebula sketch, G).
A two-armed spiral galaxy seen at a tilt, so it uses the wide screen. The
night you just had is the glowing core; every 70 steps adds a star at the end
of an arm, so the arms grow outward through the day in the order you moved --
a still morning is a bare core, a big day a galaxy that fills the sky.

  core              last night: one star per 6 min asleep, packed into a
                    bulge that grows with hours slept               [sleep]
  sparks            a yellow spark on the core's edge per wake-up    [wake-ups]
  arms              steps today (1 star / 70 steps, cap 300); they wind out
                    in time order, so the outer stars are the latest [movement]
  warm stars        added while HR >= 105 (zone colour)              [effort]
  slow spin         the whole galaxy turns ~a quarter turn a day
  bottom            steps today; date + moon phase under the time; red tick
                    = north (sun compass)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, imod, hash16, isin, account  # noqa: E402

TITLE = "Galaxy -- last night is the core, today's steps are the arms"
BLURB = ("Black face. A tilted two-armed spiral: the core is last night's sleep (sparks = wake-ups); "
         "every 70 steps adds a star to the arms, winding outward in time order.")
LEGEND = [
    "core = last night: bigger = longer sleep",
    "yellow spark on the core = a wake-up",
    "arms = today's steps (1 star per 70),",
    "  winding outward: outer stars are newest",
    "warm stars = added while HR >= 105",
    "number = steps today",
    "moon phase after the date; red tick = north",
]

CX, CY = 107, 113
STEPS_PER_STAR = 70
SMAX = 300
RMAX = 98                     # arm reach (px, before the tilt)
TILT = 56                     # y scale %, the galaxy seen at an angle
WIND = 330                    # arm winding over the full reach (1/256 turns)
# u^0.75 LUT (u in 0..32 -> 0..127) so early stars aren't all crammed inward
UP = [int(127 * (i / 32.0) ** 0.75 + 0.5) for i in range(33)]


class Galaxy:
    def __init__(self):
        self.log = K.DayLog()

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes()

    def render(self, dc, s):
        log = self.log
        t = (s.hour * 60 + s.minute) if s.hour is not None else 0
        rot = idiv(t, 22)                          # ~quarter turn per day
        seed = (s.day or 1) * 13 + (s.month or 1)
        night = log.night
        rc = 4
        if night:
            rc = 5 + idiv(night[2] * 2, 60)        # core radius: +2 px/hour
            rc = min(rc, 26)

        # ---- arms: star k on arm k%2, at fraction u along it
        n = min(idiv(log.steps, STEPS_PER_STAR), SMAX)
        cum = log.cum_steps()
        b = 0
        for k in range(n):
            m = k >> 1
            arm = k & 1
            ui = idiv(m * 32, SMAX >> 1)
            if ui > 32:
                ui = 32
            u = UP[ui]                              # 0..127
            r = rc + 2 + idiv(u * (RMAX - rc - 2), 127)
            h = hash16(seed, k, 9)
            phi = rot + arm * 128 + idiv(u * WIND, 127)
            # scatter widens outward; ~1 in 6 stars strays into the disc
            spread = 1 + idiv(u * 7, 127)
            if (h & 7) == 0:
                spread = spread * 3
            dr = idiv(((h >> 3) & 31) - 16, 1) * spread
            dp = idiv((((h >> 8) & 31) - 16) * spread, 2)
            rr = r + idiv(dr, 16)
            pp = phi + idiv(dp, 16)
            x = CX + idiv(rr * isin(pp + 64), 127)
            y = CY + idiv(idiv(rr * isin(pp), 127) * TILT, 100)
            while b < K.NB - 1 and cum[b] < (k + 1) * STEPS_PER_STAR:
                b += 1
            z = log.bzone[b]
            if z >= K.EFFORT:
                col = K.HR_RAMP[z]
            else:
                col = K.WHITE if (h >> 13) & 1 else K.LT_GRAY
            dc.setColor(col, K.TRANSPARENT)
            if (h & 0x1F00) == 0x1F00 or k == n - 1:
                dc.fillRectangle(x - 1, y, 3, 1)       # a bright star: a cross
                dc.fillRectangle(x, y - 1, 1, 3)
            elif h & 0x0400:
                dc.fillRectangle(x, y, 2, 2)
            else:
                dc.fillRectangle(x, y, 1, 1)
        account(n + K.NB)

        # ---- core: last night, a packed bulge of cool stars
        if night:
            ncore = min(idiv(night[2], 6), 100)
            for k in range(ncore):
                h = hash16(seed, k, 3)
                a = h & 255
                rr = idiv(rc * (((h >> 8) & 15) + 1), 16)
                rr = idiv(rr * rr, rc)                     # denser in the middle
                x = CX + idiv(rr * isin(a + 64), 127)
                y = CY + idiv(idiv(rr * isin(a), 127) * TILT, 100)
                if rr < idiv(rc, 3):
                    col = K.WHITE
                elif rr < idiv(rc * 2, 3):
                    col = K.BLUE
                else:
                    col = K.DK_BLUE
                dc.setColor(col, K.TRANSPARENT)
                dc.fillRectangle(x, y, 2, 2)
            dc.setColor(K.WHITE, K.TRANSPARENT)
            dc.fillCircle(CX, CY, 2)
            for i, w in enumerate(night[3]):
                a = idiv((w - night[0]) * 256, max(1, night[1] - night[0])) + 32
                x = CX + idiv((rc + 3) * isin(a + 64), 127)
                y = CY + idiv(idiv((rc + 3) * isin(a), 127) * TILT, 100)
                dc.setColor(K.YELLOW, K.TRANSPARENT)
                dc.fillRectangle(x - 2, y, 5, 1)
                dc.fillRectangle(x, y - 2, 1, 5)

        # ---- time, date, steps
        ts = K.time_str(s)
        tw = K.text_w(K.DIG57, ts, 5, 4)
        K.draw_text(dc, K.DIG57, ts, 108 - tw // 2, 6, 5, K.WHITE, 4, "gap")
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        x0 = 103 - dw // 2
        K.draw_text(dc, K.SMALL, ds, x0, 46, 2, K.LT_GRAY, 2)
        K.draw_moon(dc, x0 + dw + 9, 50, 4, K.moon_age(s), K.WHITE, K.DK_GRAY)
        K.battery_low(dc, s, x0 - 17, 48)
        ns = str(log.steps)
        K.draw_text(dc, K.SMALL, ns, 108 - K.text_w(K.SMALL, ns, 2, 2) // 2, 166, 2, K.LT_GRAY, 2)
        K.north_tick(dc, s)


def build():
    return {"background": K.BLACK, "components": [Galaxy()]}
