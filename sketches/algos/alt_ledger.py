#!/usr/bin/env python3
"""alt_ledger -- "Ledger": the day as a page of a dot-grid notebook, on WHITE.

Concept (docs/alt-faces.md, round 1). The day is 96 dots, one per quarter
hour, read like text: six rows of four hours (00-04, 04-08, ... 20-24), sixteen
dots a row. Ink is movement: a dot's SIZE is the steps in its quarter hour, so
walks and runs print as runs of fat dots and a desk afternoon as a fine dotted
line. The rest of the page tells the rest:

  dot size         steps that quarter hour (5 sizes)                 [movement]
  dot colour       black; HR-zone colour when HR >= 105 bpm          [effort]
  blue dots        quarter hours asleep (last night, inferred)       [sleep]
  red ring         a wake-up                                         [wake-ups]
  grey dots ahead  the rest of today: pale = daylight, dark = night  [sun trick]
  ring             now
  big number       steps so far; date + moon phase under the time

White shows off the semiround screen (owner, Q24); black ink on paper, the
colour kept for effort and wake-ups only. Rendering is ~100 dots and a dozen
glyph blits -- one of the cheapest faces possible (~2k VM instr).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, account  # noqa: E402

TITLE = "Ledger -- the day as a dot-grid page"
BLURB = ("White face. 96 dots = the day's quarter hours, read like text (rows of 4 h). "
         "Dot size = steps, colour = effort, blue = asleep, red ring = woke up.")
LEGEND = [
    "rows: 00-04, 04-08, 08-12, 12-16, 16-20, 20-24",
    "dot size = steps in that quarter hour",
    "coloured dot = HR >= 105 (zone colour)",
    "blue = asleep, red ring = a wake-up",
    "pale grey ahead = daylight left, dark = night",
    "ring = now;  big number = steps today",
    "moon phase after the date; red tick = north",
]

COLS, ROWS = 16, 6
PX, PY = 11, 12            # dot pitch
GX0 = 107 - (COLS - 1) * PX // 2   # first dot centre x
GY0 = 66                   # first row centre y
SIZE_AT = [30, 150, 500, 1000]     # step thresholds for radius 2..5


class Ledger:
    def __init__(self):
        self.log = K.DayLog()

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes()

    def render(self, dc, s):
        log = self.log
        dc.setColor(K.WHITE, K.WHITE)
        dc.clear()
        # ---- time + date line
        ts = K.time_str(s)
        tw = K.text_w(K.DIG57, ts, 5, 4)
        K.draw_text(dc, K.DIG57, ts, 108 - tw // 2, 6, 5, K.BLACK, 4, "dot")
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        x0 = 103 - dw // 2
        K.draw_text(dc, K.SMALL, ds, x0, 46, 2, K.BLACK, 2)
        K.draw_moon(dc, x0 + dw + 9, 50, 4, K.moon_age(s), K.WHITE, K.BLACK, K.BLACK)
        dc.setColor(K.BLACK, K.TRANSPARENT)
        K.battery_low(dc, s, x0 - 17, 48)

        # ---- the page
        now = (s.hour * 60 + s.minute) if s.hour is not None else 0
        nb = idiv(now, 15)
        st = K.sun_times(s)
        wake_b = set()
        if log.night:
            for w in log.night[3]:
                wake_b.add(idiv(K.day_min(w), 15))
        account(K.NB)
        for b in range(K.NB):
            x = GX0 + (b % COLS) * PX
            y = GY0 + idiv(b, COLS) * PY
            if b > nb:
                bm = b * 15 + 7
                day = st is not None and st[0] <= bm < st[1]
                if day:
                    dc.setColor(K.LT_GRAY, K.TRANSPARENT)
                    dc.fillCircle(x, y, 1)
                else:
                    dc.setColor(K.DK_GRAY, K.TRANSPARENT)
                    dc.fillRectangle(x, y, 1, 1)
                continue
            steps = log.bsteps[b]
            if log.bsleep[b] >= 8 and steps < 30:
                dc.setColor(K.DK_BLUE, K.TRANSPARENT)
                dc.fillCircle(x, y, 2)
            else:
                r = 1
                for t in SIZE_AT:
                    if steps >= t:
                        r += 1
                z = log.bzone[b]
                col = K.HR_RAMP[z] if z >= K.EFFORT else (K.BLACK if r > 1 else K.DK_GRAY)
                dc.setColor(col, K.TRANSPARENT)
                dc.fillCircle(x, y, r)
            if b in wake_b:
                dc.setColor(K.RED, K.TRANSPARENT)
                K.draw_circle(dc, x, y, 4)
            if b == nb:
                dc.setColor(K.BLACK, K.TRANSPARENT)
                K.draw_circle(dc, x, y, 6)

        # ---- steps + sun times
        n = str(log.steps)
        nw = K.text_w(K.DIG57, n, 3, 3)
        K.draw_text(dc, K.DIG57, n, 108 - nw // 2, 137, 3, K.BLACK, 3, "dot")
        if st is not None:
            ss = "%s-%s" % (K.hm12(st[0]), K.hm12(st[1]))
            sw = K.text_w(K.SMALL, ss, 2, 2)
            sx = 108 - (sw + 12) // 2
            dc.setColor(K.YELLOW, K.TRANSPARENT)
            dc.fillCircle(sx + 3, 168, 3)
            K.draw_text(dc, K.SMALL, ss, sx + 11, 164, 2, K.DK_GRAY, 2)
        K.north_tick(dc, s)


def build():
    return {"background": K.WHITE, "components": [Ledger()]}
