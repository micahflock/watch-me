#!/usr/bin/env python3
"""alt_cascade -- "Cascade": a Pacific Northwest ridgeline where your steps
plant a forest, under today's real sun path.

Concept (docs/alt-faces.md, round 1). One time axis for the whole scene: left
edge = midnight, right edge = the next midnight. That single axis lets the
landscape say WHEN without a chart:

  firs              every 400 steps plants a fir at the time you earned it;
                    taller when that quarter hour was brisker   [movement]
  autumn maples     planted while HR >= 105: round, zone colour [effort]
  sun path          today's real sun altitude over the same axis -- the arc
                    rises at sunrise, peaks at solar noon and sets at sunset,
                    its height follows the season; the sun disc is NOW
                    (the dotted arc ahead of it is the daylight left)  [trick]
  stars             last night: one star per quarter hour asleep  [sleep]
  shooting stars    one per wake-up                               [wake-ups]
  moon              tonight's phase, in the upper sky
  numbers           sunrise / steps today / sunset along the bottom

The mountain is a generic Cascade volcano (a nod to the view from Portland),
not a portrait of any one peak.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altkit as K  # noqa: E402
from device import idiv, imod, hash16, isin, account  # noqa: E402

TITLE = "Cascade -- your steps plant a forest under today's sun"
BLURB = ("Black face, one time axis (midnight left -> midnight right). Every 400 steps plants a fir "
         "at the hour you earned it; the sun rides today's real sun path; last night is the stars.")
LEGEND = [
    "x axis = time of day (midnight -> midnight)",
    "firs = steps (1 per 400), planted at that hour;",
    "  taller = brisker",
    "round autumn maples = planted while HR >= 105",
    "arc = today's sun path; disc = the sun now",
    "stars = last night (1 per 15 min asleep)",
    "shooting star = a wake-up",
    "bottom: sunrise / steps today / sunset",
    "moon = tonight's phase",
]

XL, XR = 8, 207            # x of 00:00 and 24:00
HZ = 120                   # horizon (sun path baseline)
SKY_TOP = 60               # stars live between here and the ridges
STEPS_PER_TREE = 400
TMAX = 72


def tx(m):
    return XL + idiv(m * (XR - XL), 1440)


def ridge_mid(x):
    """Mid ridge (DK_GRAY) height at x -- fixed scenery."""
    return 124 - idiv(5 * isin(x * 3 + 40), 127) - idiv(3 * isin(x * 7 + 10), 127)


def ridge_fg(x):
    """Foreground ridge where the forest grows."""
    return 140 - idiv(6 * isin(x * 2 + 170), 127) - idiv(2 * isin(x * 9), 127)


class Cascade:
    def __init__(self):
        self.log = K.DayLog()
        self._path_day = None
        self._path = None

    def advance(self, snap):
        self.log.advance(snap)

    def state_bytes(self):
        return self.log.state_bytes() + 49 * 4

    def sun_path(self, s):
        """Sun altitude every 30 min (49 Numbers), computed once per day."""
        key = (s.year, s.month, s.day)
        if self._path_day != key:
            pts = []
            hh, mm = s.hour, s.minute
            for i in range(49):
                m = min(i * 30, 1439)
                s.hour, s.minute = m // 60, m % 60
                p = K.sun_position(s)
                pts.append(int(p[1] + 0.5) if p else -90)
            s.hour, s.minute = hh, mm
            self._path, self._path_day = pts, key
        return self._path

    def render(self, dc, s):
        log = self.log
        now = (s.hour * 60 + s.minute) if s.hour is not None else 0
        seed = (s.day or 1) * 37 + (s.month or 1)

        # ---- sky: sleep stars + wake-up shooting stars
        if log.night:
            nstar = idiv(log.night[2], 15)
            for k in range(min(nstar, 40)):
                h = hash16(seed, k, 21)
                x = 12 + (h % 190)
                y = SKY_TOP + ((h >> 8) % 44)
                if 34 < x < 182 and y < 58:
                    continue
                if y > 78 and abs(x - 156) < (y - 78):     # behind the volcano
                    continue
                dc.setColor(K.WHITE if (h & 0x6000) == 0 else K.LT_GRAY, K.TRANSPARENT)
                dc.fillRectangle(x, y, 1 + ((h >> 13) & 1), 1)
            for i, w in enumerate(log.night[3]):
                h = hash16(seed, i, 23)
                x = 30 + (h % 150)
                y = SKY_TOP + 4 + ((h >> 8) % 26)
                dc.setColor(K.DK_GRAY, K.TRANSPARENT)
                dc.drawLine(x - 9, y - 4, x - 4, y - 2)
                dc.setColor(K.LT_GRAY, K.TRANSPARENT)
                dc.drawLine(x - 4, y - 2, x, y)
                dc.setColor(K.WHITE, K.TRANSPARENT)
                dc.fillRectangle(x, y, 2, 2)
        # moon, upper left sky
        K.draw_moon(dc, 30, 72, 6, K.moon_age(s), K.LT_GRAY, K.DK_GRAY)

        # ---- today's sun path: dotted arc, sun disc at now
        path = self.sun_path(s)
        kpx = 1.0                                  # px per degree of altitude
        for i in range(48):
            el = path[i]
            if el <= 0:
                continue
            x = tx(i * 30)
            y = HZ - int(el * kpx * 1.15)
            dc.setColor(K.DK_GRAY if i * 30 < now else K.YELLOW, K.TRANSPARENT)
            dc.fillRectangle(x, y, 1, 1)
        sp = K.sun_position(s)
        if sp and sp[1] > -0.8:
            sx, sy = tx(now), HZ - int(sp[1] * kpx * 1.15)
            dc.setColor(K.YELLOW, K.TRANSPARENT)
            dc.fillCircle(sx, sy, 5)

        # ---- the volcano (far): engraved -- every other row -- so the
        # distant peak reads half as loud as the near ridges; snowcap solid
        dc.setColor(K.DK_BLUE, K.TRANSPARENT)
        for y in range(81, 127, 2):
            hw = idiv((y - 80) * 44, 46)
            dc.drawLine(156 - hw, y, 156 + hw, y)
        dc.setColor(K.WHITE, K.TRANSPARENT)
        dc.fillPolygon([(156, 80), (145, 92), (167, 92)])
        dc.setColor(K.BLACK, K.TRANSPARENT)
        for nx in (148, 155, 162):                       # ragged snow line
            dc.fillPolygon([(nx - 3, 93), (nx, 88), (nx + 3, 93)])
        dc.setColor(K.DK_GRAY, K.TRANSPARENT)
        for x in range(0, 215, 8):
            y0, y1 = ridge_mid(x), ridge_mid(x + 8)
            dc.fillPolygon([(x, y0), (x + 8, y1), (x + 8, 180), (x, 180)])
        dc.setColor(K.BLACK, K.TRANSPARENT)
        for x in range(0, 215, 8):
            y0, y1 = ridge_fg(x), ridge_fg(x + 8)
            dc.fillPolygon([(x, y0), (x + 8, y1), (x + 8, 180), (x, 180)])
        dc.setColor(K.DK_GREEN, K.TRANSPARENT)
        for x in range(0, 215, 8):
            dc.drawLine(x, ridge_fg(x), x + 8, ridge_fg(x + 8))

        # ---- the forest: tree k planted when cumulative steps passed k*400
        n = min(idiv(log.steps, STEPS_PER_TREE), TMAX)
        cum = log.cum_steps()
        b = 0
        trees = []
        for k in range(n):
            while b < K.NB - 1 and cum[b] < (k + 1) * STEPS_PER_TREE:
                b += 1
            h = hash16(seed, k, 29)
            x = tx(b * 15 + 7) + (h % 13) - 6
            depth = (h >> 4) % 9                          # 0 = far, 8 = near
            base = ridge_fg(x) + 1 + depth
            ht = 8 + min(14, idiv(log.bsteps[b], 160)) + idiv(depth, 2)
            z = log.bzone[b]
            trees.append((depth, x, base, ht, z, h))
        trees.sort()                                      # far first
        for depth, x, base, ht, z, h in trees:
            if z >= K.EFFORT:
                # effort: a round autumn maple in the zone colour, not a fir
                r = 3 + idiv(ht, 8)
                dc.setColor(K.DK_GRAY, K.TRANSPARENT)
                dc.drawLine(x, base, x, base - ht + r)
                dc.setColor(K.HR_RAMP[z], K.TRANSPARENT)
                dc.fillCircle(x, base - ht + r, r)
                continue
            w = 2 + idiv(ht, 5)
            dc.setColor(K.GREEN if (h & 0x100) else K.DK_GREEN, K.TRANSPARENT)
            dc.fillPolygon([(x, base - ht), (x - w, base), (x + w, base)])
        account(n * 3 + K.NB)

        # ---- time, date, bottom line
        ts = K.time_str(s)
        tw = K.text_w(K.DIG57, ts, 5, 4)
        K.draw_text(dc, K.DIG57, ts, 108 - tw // 2, 6, 5, K.WHITE, 4, "solid")
        ds = K.date_str(s)
        dw = K.text_w(K.SMALL, ds, 2, 2)
        K.draw_text(dc, K.SMALL, ds, 108 - dw // 2, 46, 2, K.LT_GRAY, 2)
        K.battery_low(dc, s, 108 - dw // 2 - 17, 48)
        st = K.sun_times(s)
        if st is not None:
            K.draw_text(dc, K.SMALL, K.hm12(st[0]), 42, 158, 2, K.YELLOW, 2)
            ss = K.hm12(st[1])
            K.draw_text(dc, K.SMALL, ss, 174 - K.text_w(K.SMALL, ss, 2, 2), 158, 2, K.YELLOW, 2)
        ns = str(log.steps)
        K.draw_text(dc, K.SMALL, ns, 108 - K.text_w(K.SMALL, ns, 2, 2) // 2, 158, 2, K.WHITE, 2)


def build():
    return {"background": K.BLACK, "components": [Cascade()]}
