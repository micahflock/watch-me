#!/usr/bin/env python3
"""alt_vessel -- "Vessel": the time itself is a glass that fills as you move.

Concept (docs/alt-faces.md, round 1). The numerals are huge (40x70 px) and
drawn as outlines -- empty glass. Steps pour in from the bottom: the water
line is steps / step goal, so a glance at how full the time is answers the
owner's most frequent question ("how much activity am I getting?"). The
liquid is LAYERED in the order the steps happened, like sediment in a jar:
green for ordinary movement, the zone colour for a stretch at HR >= 105.
Past the goal the glass is full and the extra fizzes as bubbles.

  water line        steps / step goal (Garmin's goal)            [movement]
  layers            in time order; warm layer = HR >= 105         [effort]
  night bar         last night on a 21:00 -> 09:00 ruler; gap +
                    tick = a wake-up; duration at the right        [sleep]
  daylight bar      sunrise -> sunset; the dot is now, yellow ahead is the
                    daylight left                                  [trick]
  number            steps today (bottom); date + moon at the top

The digits are cell-built 7-segment shapes (3x5 cells), so the glass is all
fillRectangle/drawLine -- no font bitmap RAM for the big numerals.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, imod, hash16, account  # noqa: E402

TITLE = "Vessel -- the numerals fill up as you move"
BLURB = ("Black face. Giant outlined numerals fill from the bottom as you walk (full = your step goal), "
         "layered in time order; warm layers = HR >= 105. Night bar + daylight bar underneath.")
LEGEND = [
    "water line = steps / step goal",
    "layers bottom -> top = morning -> now",
    "warm layer = moving at HR >= 105",
    "bubbles = past the goal",
    "night bar: 21:00 -> 09:00 ruler; gap = woke up",
    "daylight bar: sunrise -> sunset; dot = now",
    "moon phase after the date; red tick = north",
]

T, C = 10, 20                  # stroke / counter (px): digit 40 x 70
DW, DH = 2 * T + C, 3 * T + 2 * C
DY = 44                        # digit top
COLW = [T, C, T]
ROWH = [T, C, T, C, T]
SEGS = {
    "a": [(0, 0), (0, 1), (0, 2)], "b": [(0, 2), (1, 2), (2, 2)],
    "c": [(2, 2), (3, 2), (4, 2)], "d": [(4, 0), (4, 1), (4, 2)],
    "e": [(2, 0), (3, 0), (4, 0)], "f": [(0, 0), (1, 0), (2, 0)],
    "g": [(2, 0), (2, 1), (2, 2)],
}
DIGSEG = ["abcdef", "bc", "abged", "abgcd", "fgbc", "afgcd", "afgedc", "abc",
          "abcdefg", "abcdfg"]
# lit cells per digit as a 15-bit mask (bit = row*3 + col), built once
MASK = []
for segs in DIGSEG:
    m = 0
    for sg in segs:
        for r, c in SEGS[sg]:
            m |= 1 << (r * 3 + c)
    MASK.append(m)
CX0 = [0, T, T + C]
RY0 = [0, T, T + C, 2 * T + C, 2 * T + 2 * C]

NIGHT0, NIGHT_SPAN = 60, 720   # ruler 21:00 -> 09:00 (night clock)
RX0, RX1 = 34, 160             # ruler x span
RY = 126                       # ruler row
LIQ = K.GREEN


class Vessel:
    def __init__(self):
        self.log = K.DayLog()
        self.layers = [0] * (2 * 24)     # scratch: [height, colour] pairs

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes()

    # ------------------------------------------------------------------
    def build_layers(self, goal):
        """Merge the quarter hours into colour layers (bottom = earliest);
        returns the count. Heights are in px of the DH-tall glass."""
        log = self.log
        L = self.layers
        n = 0
        cur_col = -1
        acc = 0
        total = 0
        for b in range(K.NB):
            st = log.bsteps[b]
            if st <= 0:
                continue
            z = log.bzone[b]
            col = K.HR_RAMP[z] if z >= K.EFFORT else LIQ
            if col != cur_col and acc > 0 and n < 23:
                L[2 * n] = acc
                L[2 * n + 1] = cur_col
                n += 1
                acc = 0
            cur_col = col
            acc += st
            total += st
        if acc > 0:
            L[2 * n] = acc
            L[2 * n + 1] = cur_col
            n += 1
        account(K.NB)
        # steps -> px, capped at the glass height
        y = 0
        for i in range(n):
            h = idiv(L[2 * i] * DH, goal)
            if y + h > DH:
                h = DH - y
            L[2 * i] = h
            y += h
        return n

    def render(self, dc, s):
        log = self.log
        goal = getattr(s, "stepGoal", None) or 10000
        ts = K.time_str(s)
        glyphs = list(ts)
        widths = [(T if g == ":" else DW) for g in glyphs]
        gaps = []
        for i in range(len(glyphs) - 1):
            gaps.append(4 if (glyphs[i] == ":" or glyphs[i + 1] == ":") else 6)
        total = sum(widths) + sum(gaps)
        x = 108 - total // 2
        nl = self.build_layers(goal)
        fill_px = min(DH, idiv(log.steps * DH, goal))
        over = log.steps - goal
        for i, g in enumerate(glyphs):
            if g == ":":
                self.colon(dc, x, nl, fill_px)
            elif g.isdigit():
                self.digit(dc, x, MASK[int(g)], nl, fill_px, over, i)
            x += widths[i] + (gaps[i] if i < len(gaps) else 0)

        # ---- date + moon (top)
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        x0 = 103 - dw // 2
        K.draw_text(dc, K.SMALL, ds, x0, 25, 2, K.LT_GRAY, 2)
        K.draw_moon(dc, x0 + dw + 9, 29, 4, K.moon_age(s), K.WHITE, K.DK_GRAY)
        K.battery_low(dc, s, x0 - 17, 27)

        # ---- night bar
        dc.setColor(K.DK_GRAY, K.TRANSPARENT)
        dc.drawLine(RX0, RY + 2, RX1, RY + 2)
        for hh in (0, 180, 360, 540, 720):          # 21 24 3 6 9
            xx = RX0 + idiv(hh * (RX1 - RX0), NIGHT_SPAN)
            dc.drawLine(xx, RY, xx, RY + 4)
        night = log.night
        if night:
            start, end, asleep, wakes = night
            xa = RX0 + idiv((start - NIGHT0) * (RX1 - RX0), NIGHT_SPAN)
            xb = RX0 + idiv((end - NIGHT0) * (RX1 - RX0), NIGHT_SPAN)
            dc.setColor(K.BLUE, K.TRANSPARENT)
            dc.fillRectangle(xa, RY, max(1, xb - xa), 5)
            for w in wakes:
                xw = RX0 + idiv((w - NIGHT0) * (RX1 - RX0), NIGHT_SPAN)
                dc.setColor(K.BLACK, K.TRANSPARENT)
                dc.fillRectangle(xw - 1, RY, 2, 5)
                dc.setColor(K.YELLOW, K.TRANSPARENT)
                dc.drawLine(xw, RY - 5, xw, RY - 2)
            K.draw_text(dc, K.SMALL, K.dur_str(asleep), RX1 + 6, RY - 2, 2, K.BLUE, 2)

        # ---- daylight bar
        st = K.sun_times(s)
        if st is not None:
            rise, sset = st
            now = s.hour * 60 + s.minute
            by = 146
            a0, a1 = 64, 152
            K.draw_text(dc, K.SMALL, K.hm12(rise), a0 - 6 - K.text_w(K.SMALL, K.hm12(rise), 2, 2),
                        by - 3, 2, K.LT_GRAY, 2)
            K.draw_text(dc, K.SMALL, K.hm12(sset), a1 + 6, by - 3, 2, K.LT_GRAY, 2)
            f = min(max(now - rise, 0), sset - rise)
            xn = a0 + idiv(f * (a1 - a0), max(1, sset - rise))
            if xn > a0:
                dc.setColor(K.DK_GRAY, K.TRANSPARENT)
                dc.fillRectangle(a0, by + 1, xn - a0, 2)
            dc.setColor(K.YELLOW, K.TRANSPARENT)
            if a1 > xn:
                dc.fillRectangle(xn, by + 1, a1 - xn, 2)
            if rise <= now <= sset:
                dc.fillCircle(xn, by + 2, 3)
        # ---- steps
        ns = str(log.steps)
        K.draw_text(dc, K.SMALL, ns, 108 - K.text_w(K.SMALL, ns, 2, 2) // 2, 160, 2, K.WHITE, 2)
        K.north_tick(dc, s)

    # ------------------------------------------------------------------
    def fill_rect(self, dc, x, y, w, h, nl):
        """Paint the cell rect [y, y+h) with the liquid layers it crosses.
        Glass coordinates: layer i spans [DY+DH-top_i, DY+DH-bot_i)."""
        L = self.layers
        bot = DY + DH
        for i in range(nl):
            top = bot - L[2 * i]
            y0 = max(y, top)
            y1 = min(y + h, bot)
            if y1 > y0:
                dc.setColor(L[2 * i + 1], K.TRANSPARENT)
                dc.fillRectangle(x, y0, w, y1 - y0)
            bot = top
            if bot <= y:
                break

    def digit(self, dc, x, mask, nl, fill_px, over, idx):
        wl = DY + DH - fill_px                    # water line (y)
        for r in range(5):
            for c in range(3):
                if not (mask >> (r * 3 + c)) & 1:
                    continue
                cx, cy = x + CX0[c], DY + RY0[r]
                cw, ch = COLW[c], ROWH[r]
                if cy + ch > wl:
                    self.fill_rect(dc, cx, cy, cw, ch, nl)
        if over > 0:                               # fizz: bubbles past the goal
            nb = min(idiv(over, 300), 14)
            dc.setColor(K.WHITE, K.TRANSPARENT)
            for k in range(nb):
                h = hash16(idx, k, 61)
                r = h % 5
                c = (h >> 3) % 3
                if not (mask >> (r * 3 + c)) & 1:
                    continue
                bx = x + CX0[c] + 2 + (h >> 5) % max(1, COLW[c] - 4)
                byy = DY + RY0[r] + 2 + (h >> 9) % max(1, ROWH[r] - 4)
                dc.fillRectangle(bx, byy, 2, 2)
        # the glass: outline of the lit-cell union
        dc.setColor(K.WHITE, K.TRANSPARENT)
        for r in range(5):
            for c in range(3):
                if not (mask >> (r * 3 + c)) & 1:
                    continue
                x0, y0 = x + CX0[c], DY + RY0[r]
                x1, y1 = x0 + COLW[c] - 1, y0 + ROWH[r] - 1
                if r == 0 or not (mask >> ((r - 1) * 3 + c)) & 1:
                    dc.drawLine(x0, y0, x1, y0)
                if r == 4 or not (mask >> ((r + 1) * 3 + c)) & 1:
                    dc.drawLine(x0, y1, x1, y1)
                if c == 0 or not (mask >> (r * 3 + c - 1)) & 1:
                    dc.drawLine(x0, y0, x0, y1)
                if c == 2 or not (mask >> (r * 3 + c + 1)) & 1:
                    dc.drawLine(x1, y0, x1, y1)
        account(15 * 3)

    def colon(self, dc, x, nl, fill_px):
        wl = DY + DH - fill_px
        for cy in (DY + T + 6, DY + 2 * T + C + 6):
            if cy + T > wl:
                self.fill_rect(dc, x, cy, T, T, nl)
            dc.setColor(K.WHITE, K.TRANSPARENT)
            dc.drawLine(x, cy, x + T - 1, cy)
            dc.drawLine(x, cy + T - 1, x + T - 1, cy + T - 1)
            dc.drawLine(x, cy, x, cy + T - 1)
            dc.drawLine(x + T - 1, cy, x + T - 1, cy + T - 1)


def build():
    return {"background": K.BLACK, "components": [Vessel()]}
