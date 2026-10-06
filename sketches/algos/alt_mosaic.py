#!/usr/bin/env python3
"""alt_mosaic -- "Mosaic": the day as a composition that keeps subdividing,
on WHITE.

Concept (docs/alt-faces.md, round 1; owner: "bold geometry", white face to
show off the semiround screen). The field starts the day as one white pane.
Every 250 steps splits a pane in two (breadth-first, along its longer side at
a hashed 30-70 % cut), so a still morning is a few big blocks and a walking
day a fine mosaic. Black leading falls out of the drawing for free: the
canvas is black and every pane is inset 1 px.

  pane count        steps today (1 split / 250 steps, cap 90)     [movement]
  colour            panes are paper tones (white / greys); a pane cut while
                    HR >= 105 may take its zone colour (every other one) --
                    the ONLY colour on the face, so effort is the accent,
                    never the bulk                                [effort]
  blue column       last night; width = hours asleep              [sleep]
  black cracks      across the blue column, one per wake-up, at the hour
                    of the night it happened (top = bedtime)      [wake-ups]
  number            steps today, in the base pane
  red tick          north (sun compass); moon phase after the date

Cost: the mosaic is a pure function of (steps, quarter-hour buckets, date
seed) replayed in O(n) each frame -- no stored geometry.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, imod, hash16, account  # noqa: E402

TITLE = "Mosaic -- the day keeps subdividing"
BLURB = ("White face. The field splits into more panes as you walk (1 cut per 250 steps); "
         "colour appears only where a cut happened at HR >= 105. Blue column = last night, cracked by wake-ups.")
LEGEND = [
    "more, smaller panes = more steps",
    "  (1 cut per 250 steps)",
    "coloured pane = cut while HR >= 105",
    "  (every other effort cut is coloured)",
    "blue column = last night (width ~ hours)",
    "black crack in it = a wake-up (top = bedtime)",
    "base pane: steps today",
    "moon phase after the date; red tick = north",
]

STEPS_PER_CUT = 250
CMAX = 90
FY0, FY1 = 58, 152          # field rows
BASE_Y = 154                 # base pane (steps) from here down
PAPER = [K.WHITE, K.WHITE, K.WHITE, K.WHITE, K.LT_GRAY, K.WHITE, K.LT_GRAY, K.BLACK]


class Mosaic:
    def __init__(self):
        self.log = K.DayLog()
        # render scratch (allocated once): the split queue, flat [x,y,w,h,col]
        self.q = [0] * ((2 * CMAX + 2) * 5)

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes()

    def render(self, dc, s):
        log = self.log
        seed = (s.day or 1) * 31 + (s.month or 1) * 7
        dc.setColor(K.BLACK, K.BLACK)
        dc.clear()

        # ---- top pane: time + date
        dc.setColor(K.WHITE, K.TRANSPARENT)
        dc.fillRectangle(0, 0, 215, FY0 - 1)
        ts = K.time_str(s)
        tw = K.text_w(K.SQ57, ts, 5, 4)
        K.draw_text(dc, K.SQ57, ts, 108 - tw // 2, 7, 5, K.BLACK, 4, "solid")
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        x0 = 103 - dw // 2
        K.draw_text(dc, K.SMALL, ds, x0, 45, 2, K.BLACK, 2)
        K.draw_moon(dc, x0 + dw + 9, 49, 4, K.moon_age(s), K.WHITE, K.BLACK, K.BLACK)
        K.battery_low(dc, s, x0 - 17, 47)

        # ---- last night: the blue column at the left of the field
        fx0 = 0
        night = log.night
        if night:
            start, end, asleep, wakes = night
            cw = 4 + idiv(asleep * 6, 60)                  # 6 px per hour
            cw = min(cw, 64)
            colx = 14                                       # visible from here
            dc.setColor(K.DK_BLUE, K.TRANSPARENT)
            dc.fillRectangle(0, FY0, colx + cw, FY1 - FY0)
            span = max(1, end - start)
            dc.setColor(K.BLACK, K.TRANSPARENT)
            for w in wakes:
                y = FY0 + idiv((w - start) * (FY1 - FY0), span)
                dc.fillRectangle(0, y - 1, colx + cw, 2)
            fx0 = colx + cw + 1

        # ---- the field: breadth-first splits replayed from the step count
        n = min(idiv(log.steps, STEPS_PER_CUT), CMAX)
        cum = log.cum_steps()
        q = self.q
        q[0], q[1], q[2], q[3], q[4] = fx0, FY0, 215 - fx0, FY1 - FY0, K.WHITE
        tail = 1
        head = 0
        b = 0
        for k in range(n):
            # next splittable pane (too-small panes are skipped, stay leaves)
            while head < tail:
                o = head * 5
                if q[o + 2] >= 12 or q[o + 3] >= 12:
                    break
                q[tail * 5:tail * 5 + 5] = q[o:o + 5]       # carry the leaf
                tail += 1
                head += 1
            if head >= tail:
                break
            o = head * 5
            x, y, w, h, col = q[o:o + 5]
            head += 1
            hh = hash16(seed, k, 13)
            cut = 30 + (hh % 41)                             # 30..70 %
            while b < K.NB - 1 and cum[b] < (k + 1) * STEPS_PER_CUT:
                b += 1
            z = log.bzone[b]
            # effort colours every other cut of an effort stretch -- an accent,
            # not the bulk (a 25-min brisk walk would otherwise paint 12 panes)
            if z >= K.EFFORT and (hh >> 12) & 1:
                ncol = K.HR_RAMP[z]
            else:
                ncol = PAPER[(hh >> 7) & 7]
            if w >= h:
                c = max(6, min(w - 6, idiv(w * cut, 100)))
                a = (x, y, c, h, col)
                bb = (x + c, y, w - c, h, ncol)
            else:
                c = max(6, min(h - 6, idiv(h * cut, 100)))
                a = (x, y, w, c, col)
                bb = (x, y + c, w, h - c, ncol)
            if (hh >> 11) & 1:                               # which side is new
                a, bb = (a[0], a[1], a[2], a[3], bb[4]), (bb[0], bb[1], bb[2], bb[3], a[4])
            q[tail * 5:tail * 5 + 5] = a
            q[tail * 5 + 5:tail * 5 + 10] = bb
            tail += 2
        account(n * 2 + K.NB)
        # leaves = queue[head:tail]
        for i in range(head, tail):
            o = i * 5
            dc.setColor(q[o + 4], K.TRANSPARENT)
            dc.fillRectangle(q[o] + 1, q[o + 1] + 1, q[o + 2] - 2, q[o + 3] - 2)

        # ---- base pane: steps
        dc.setColor(K.WHITE, K.TRANSPARENT)
        dc.fillRectangle(0, BASE_Y, 215, 180 - BASE_Y)
        ns = str(log.steps)
        nw = K.text_w(K.SQ57, ns, 2, 2)
        K.draw_text(dc, K.SQ57, ns, 108 - nw // 2, BASE_Y + 5, 2, K.BLACK, 2, "solid")
        K.north_tick(dc, s)


def build():
    return {"background": K.BLACK, "components": [Mosaic()]}
