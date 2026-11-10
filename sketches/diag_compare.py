#!/usr/bin/env python3
"""diag_compare.py -- a cooler on-wrist diagnostic readout (owner, 2026-11).

The diag build (faces/two-worlds-v2/diag/Diag.mc) swaps the moss for a
readout one minute in ten. Today that readout is five lines of white system
text on a black rectangle that bites pieces out of the white border, over a
22 px HR sparkline that runs off both sides of the field. Same data, three
treatments:

    A  current     the shipped readout, transcribed from Diag.mc
    B  HUD         the HR history promoted to a scope across the widest part
                   of the field (zone-coloured columns, 105 bpm rule, 30 min
                   ticks, the replayed gap as a blue bracket); the five
                   lines tightened to a 13 px pitch below it, hugging the
                   curve of the border and re-ordered longest-first so each
                   fits its row of the disc (gap, e, fix, P, A: the day's
                   record under the scope it annotates, GPS below), amber
                   labels / white values, state
                   words in the colour the chrome already uses for them
                   (fresh blue, stale amber, none grey, ERR red). No black
                   rectangle: the border stays whole.
    C  instruments B, with the numbers that are really pictures drawn as
                   pictures: GPS quality as a 4-bar meter, the fix state as
                   a filled plate, the biggest episode as its actual bead
                   (growth rings) and its slots as zone-colour swatches.

Each over two records: a morning after a recorded run (every field live) and
a fresh install in the simulator (every field empty).

Text is Toybox FONT_XTINY, which on the fr735xt is Roboto 12 Bold. The
sandbox stands in Liberation Sans Bold 12 (same advance to the pixel on the
sim's "fix:none st0 set:Y n157": 130 px), so line LENGTHS are trustworthy and
letter SHAPES are approximate; the simulator is the check after sign-off.

    python3 sketches/diag_compare.py        # -> sketches/out/diag-compare.png
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device
import twchrome
from device import (COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_BLUE, COLOR_YELLOW, COLOR_RED, COLOR_GREEN,
                    COLOR_DK_GREEN, COLOR_TRANSPARENT, idiv)
from daybuckets import HR_RAMP, hr_zi
from harness import OUT
from twchrome import ChromeDc, chrome_state

FONT = ImageFont.truetype(
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 12)
FONT_H = 19            # dc.getFontHeight(FONT_XTINY) on the fr735xt sim
GLYPH_DY = 4           # glyph box top inside the 19 px line box


class TextDc(ChromeDc):
    """ChromeDc plus drawText / getTextWidthInPixels / drawPoint, 1-bit text
    (the panel has no anti-aliasing)."""

    def drawText(self, x, y, font, text, justify):
        self.calls += 1
        self._d.fontmode = "1"
        self._d.text((int(x), int(y) + GLYPH_DY), text, font=FONT,
                     fill=device._rgb(self._fg))

    def getTextWidthInPixels(self, text, font):
        return int(FONT.getlength(text) + 0.5)

    def getFontHeight(self, font):
        return FONT_H

    def drawPoint(self, x, y):
        self.calls += 1
        if 0 <= x < device.W and 0 <= y < device.H:
            self.img.putpixel((int(x), int(y)), device._rgb(self._fg))


# ----------------------------------------------------------------- the data --

class Rec:
    """What the readout reads, already reduced to values: the two position
    APIs, DataSource's remembered fix, the grove's longest gap and biggest
    episode, and 180 minutes of HR history (0 = no sample that minute)."""


def after_run():
    r = Rec()
    r.name = "after a recorded run"
    r.now = 9 * 60 + 40
    r.a = (45.52, -122.68, 4)             # lat, lon, accuracy
    r.p = (45.52, -122.68, 4, 62)         # ... + age of `when` in minutes
    r.fix = 2; r.fix_h = 1; r.set = True
    r.gap = (47, True, 8 * 60 + 39, 96)   # minutes, history?, at, HR on return
    r.epi = (2, 5, 47, 24, 3, [4, 6, 6, 8, 7, 6])   # idx, n, dur, bead, L, slots
    col = []
    for i in range(180):
        t = r.now - 179 + i
        if 7 * 60 + 52 <= t <= 8 * 60 + 39:           # the run
            k = t - (7 * 60 + 52)
            hr = 118 + min(k * 4, 40) + (14 if 20 <= k < 30 else 0) \
                + (device.hash16(i, 3, 9) % 7)
            if k > 40:
                hr -= (k - 40) * 5
        elif t < 7 * 60 + 5:
            hr = 52 + device.hash16(i, 1, 9) % 6      # asleep
            if device.hash16(i, 2, 9) % 5 == 0:
                hr = 0                                # sparse overnight samples
        else:
            hr = 66 + device.hash16(i, 1, 9) % 16
        col.append(hr)
    r.col = col
    r.n = sum(1 for h in col if h > 0)
    r.breach = False
    return r


def fresh_sim():
    r = Rec()
    r.name = "fresh install, simulator"
    r.now = 22 * 60 + 38
    r.a = None
    r.p = (None, None, 0, None)
    r.fix = 0; r.fix_h = None; r.set = True
    r.gap = None
    r.epi = None
    r.col = [70 + device.hash16(i, 5, 9) % 9 if i > 22 else 0
             for i in range(180)]
    r.n = 157
    r.breach = False
    return r


def fmt(v):
    return "{:.2f}".format(v)


def age(m):
    if m < 0:
        return "-" + age(-m)
    if m < 120:
        return "{}m".format(m)
    if m < 2880:
        return "{}h".format(m // 60)
    return "{}d".format(m // 1440)


FIX_WORD = ["none", "stale", "fresh"]
FIX_COL = [COLOR_DK_GRAY, COLOR_YELLOW, COLOR_BLUE]   # as the uplink bars


# --------------------------------------------------------------- A: current --

class Current:
    W = 180
    H = 22

    def render(self, dc, r):
        dc.setColor(COLOR_BLACK, COLOR_BLACK)
        dc.fillRectangle(14, 63, 188, 102)
        dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
        lh = dc.getFontHeight(0) - 2
        y = 63
        for line in self.lines(r):
            dc.drawText(18, y, 0, line, 0)
            y += lh
        self.sparkline(dc, r)

    def lines(self, r):
        a = "null" if r.a is None else "{},{} q{}".format(
            fmt(r.a[0]), fmt(r.a[1]), r.a[2])
        if r.p[0] is None:
            p = "null q{}".format(r.p[2])
        else:
            p = "{},{} q{} {}".format(fmt(r.p[0]), fmt(r.p[1]), r.p[2],
                                      age(r.p[3]))
        fx = "fix:{} {} set:{} n{}".format(
            FIX_WORD[r.fix], "st0" if r.fix_h is None else "{}h".format(r.fix_h),
            "Y" if r.set else "N", r.n)
        if r.gap is None:
            gp = "gap: none seen"
        else:
            gp = "gap:{}m hist:{} @{}:{:02d} hr{}".format(
                r.gap[0], "Y" if r.gap[1] else "N", r.gap[2] // 60,
                r.gap[2] % 60, r.gap[3])
        if r.epi is None:
            ep = "e: none"
        else:
            ep = "e{}/{} d{} r{} L{} [{}]".format(
                r.epi[0], r.epi[1], r.epi[2], r.epi[3], r.epi[4],
                "".join(str(s) for s in r.epi[5]))
        return ["A:" + a, "P:" + p, fx, gp, ep]

    def sparkline(self, dc, r):
        x0, yb, H, W = 18, 158, self.H, self.W
        dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
        y105 = yb - idiv((105 - 40) * H, 160)
        dc.drawLine(x0, y105, x0 + W, y105)
        for i in range(W):
            hr = r.col[i]
            if hr <= 0:
                continue
            dc.setColor(HR_RAMP[hr_zi(hr)], COLOR_TRANSPARENT)
            yy = yb - idiv((hr - 40) * H, 160)
            if yy < yb - H:
                yy = yb - H
            dc.drawPoint(x0 + i, yy)
        if r.gap is not None:
            a = W - 1 - (r.now - (r.gap[2] - r.gap[0]))
            b = W - 1 - (r.now - r.gap[2])
            if a < 0:
                a = 0
            if b >= 0 and a < W:
                dc.setColor(COLOR_BLUE, COLOR_TRANSPARENT)
                dc.fillRectangle(x0 + a, yb + 2, b - a + 1, 2)


# ------------------------------------------------------------------- B: HUD --

class Hud:
    """Scope across the top of the field, five colour-coded rows under it."""
    W = 180                    # scope columns = minutes of history
    X0 = 18
    YT = 67                    # scope top row (HR 200)
    SH = 24                    # scope height: HR 40 at YT + SH
    ROW0 = 91                  # first text row (drawText y)
    PITCH = 13
    # usable span of each row: the border's curve at the row's glyph rows,
    # 4 px clear (rows sit lower and lower on the disc, so each starts a
    # little further in). Longest rows go highest: gap, e, fix, P, A.
    ROWX = [18, 20, 26, 33, 44]
    ROWR = [198, 195, 189, 182, 171]
    instruments = False

    def render(self, dc, r):
        if r.breach:           # only the banner needs clearing; border stays
            dc.setColor(COLOR_BLACK, COLOR_BLACK)
            dc.fillRectangle(14, 79, 188, 22)
        self.scope(dc, r)
        self.row = 0
        self.over = []
        self.gap(dc, r)
        self.epi(dc, r)
        self.fix(dc, r)
        self.gps(dc, "P", r.p if r.p[0] is not None else None, r.p)
        self.gps(dc, "A", r.a, None)
        self.end()
        if self.over:
            print("  OVERFLOW", type(self).__name__, r.name, self.over)

    # -- scope ---------------------------------------------------------------

    def scope(self, dc, r):
        x0, yt, sh, W = self.X0, self.YT, self.SH, self.W
        yb = yt + sh
        # corner brackets + 30-minute ticks along the base
        dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
        dc.drawLine(x0 - 2, yt, x0 - 2, yb + 1)
        dc.drawLine(x0 - 2, yt, x0 + 2, yt)
        dc.drawLine(x0 + W + 1, yt, x0 + W + 1, yb + 1)
        dc.drawLine(x0 + W - 3, yt, x0 + W + 1, yt)
        for k in range(0, 7):
            x = x0 + W - 1 - k * 30
            if x < x0:
                x = x0
            dc.drawLine(x, yb + 1, x, yb + 4)
        # history: one column per minute, filled to the base, zone colour
        last = -2
        for i in range(W):
            hr = r.col[i]
            if hr <= 0:
                continue
            z = hr_zi(hr)
            if z != last:
                dc.setColor(HR_RAMP[z], COLOR_TRANSPARENT)
                last = z
            yy = yb - idiv((hr - 40) * sh, 160)
            if yy < yt:
                yy = yt
            dc.drawLine(x0 + i, yy, x0 + i, yb)
        # the 105 bpm rule (ACTIVE threshold), dashed, over the columns
        y105 = yb - idiv((105 - 40) * sh, 160)
        dc.setColor(COLOR_LT_GRAY, COLOR_TRANSPARENT)
        for x in range(x0, x0 + W, 6):
            dc.drawLine(x, y105, x + 2, y105)
        # the replayed gap: a blue bracket under the minutes it covered
        if r.gap is not None:
            a = W - 1 - (r.now - (r.gap[2] - r.gap[0]))
            b = W - 1 - (r.now - r.gap[2])
            if a < 0:
                a = 0
            if b >= 0 and a < W:
                dc.setColor(COLOR_BLUE, COLOR_TRANSPARENT)
                dc.fillRectangle(x0 + a, yb + 2, b - a + 1, 2)
                dc.fillRectangle(x0 + a, yb - 1, 1, 3)
                dc.fillRectangle(x0 + b, yb - 1, 1, 3)

    # -- rows ----------------------------------------------------------------

    def end(self):
        if self.row and self.x > self.ROWR[self.row - 1]:
            self.over.append((self.row - 1, self.x - self.ROWR[self.row - 1]))

    def begin(self, dc, label):
        self.end()
        self.x = self.ROWX[self.row]
        self.y = self.ROW0 + self.row * self.PITCH
        self.row += 1
        self.put(dc, label, COLOR_YELLOW)
        self.x += 3

    def put(self, dc, text, color):
        dc.setColor(color, COLOR_TRANSPARENT)
        dc.drawText(self.x, self.y, 0, text, 0)
        self.x += dc.getTextWidthInPixels(text, 0)

    def gps(self, dc, label, loc, raw):
        self.begin(dc, label)
        if loc is None:
            self.put(dc, "null", COLOR_LT_GRAY)
            q = raw[2] if raw is not None else None
        else:
            self.put(dc, "{},{}".format(fmt(loc[0]), fmt(loc[1])), COLOR_WHITE)
            q = loc[2]
        if q is not None:
            self.quality(dc, q)
        if loc is not None and len(loc) > 3 and loc[3] is not None:
            self.x += 4
            self.put(dc, age(loc[3]), COLOR_LT_GRAY)

    def quality(self, dc, q):
        self.x += 4
        self.put(dc, "q{}".format(q), COLOR_LT_GRAY)

    def fix(self, dc, r):
        self.begin(dc, "fix")
        self.state(dc, r)
        self.x += 4
        self.put(dc, "st0" if r.fix_h is None else "{}h".format(r.fix_h),
                 COLOR_WHITE)
        self.x += 4
        self.put(dc, "set", COLOR_YELLOW)
        self.x += 2
        self.put(dc, "Y" if r.set else "N", COLOR_WHITE)
        self.x += 4
        self.put(dc, "n", COLOR_YELLOW)
        self.put(dc, str(r.n), COLOR_RED if r.n < 0 else COLOR_WHITE)

    def state(self, dc, r):
        self.put(dc, FIX_WORD[r.fix], FIX_COL[r.fix] if r.fix else COLOR_LT_GRAY)

    def gap(self, dc, r):
        self.begin(dc, "gap")
        if r.gap is None:
            self.put(dc, "none seen", COLOR_LT_GRAY)
            return
        self.put(dc, "{}m".format(r.gap[0]), COLOR_BLUE)
        self.x += 4
        self.put(dc, "@{}:{:02d}".format(r.gap[2] // 60, r.gap[2] % 60),
                 COLOR_WHITE)
        self.x += 4
        self.put(dc, "hist", COLOR_YELLOW)
        self.x += 2
        self.put(dc, "Y" if r.gap[1] else "N",
                 COLOR_GREEN if r.gap[1] else COLOR_RED)
        self.x += 4
        self.put(dc, "hr", COLOR_YELLOW)
        if r.gap[3] is None:
            self.put(dc, "-", COLOR_LT_GRAY)
        else:
            self.put(dc, str(r.gap[3]), HR_RAMP[hr_zi(r.gap[3])])

    def epi(self, dc, r):
        self.begin(dc, "e")
        if r.epi is None:
            self.put(dc, "none", COLOR_LT_GRAY)
            return
        idx, n, dur, bead, lv, slots = r.epi
        self.put(dc, "{}/{}".format(idx, n), COLOR_WHITE)
        self.x += 4
        self.put(dc, "{}m r{} L{}".format(dur, bead, lv), COLOR_WHITE)
        self.x += 4
        self.slots(dc, slots, bead)

    def slots(self, dc, slots, bead):
        for s in slots:
            self.put(dc, str(s), HR_RAMP[s])


# ----------------------------------------------------------- C: instruments --

class Instruments(Hud):
    instruments = True

    def quality(self, dc, q):
        """Position quality 0..4 as a 4-bar meter (QUALITY_NOT_AVAILABLE 0,
        LAST_KNOWN 1, POOR 2, USABLE 3, GOOD 4)."""
        self.x += 5
        col = COLOR_BLUE if q >= 3 else COLOR_YELLOW
        for k in range(4):
            h = 3 + 2 * k
            dc.setColor(col if k < q else COLOR_DK_GRAY, COLOR_TRANSPARENT)
            dc.fillRectangle(self.x + k * 4, self.y + 15 - h, 3, h)
        self.x += 16

    def state(self, dc, r):
        """The fix state as a filled plate in the uplink bars' colour."""
        word = FIX_WORD[r.fix].upper()
        w = dc.getTextWidthInPixels(word, 0)
        dc.setColor(FIX_COL[r.fix], COLOR_TRANSPARENT)
        dc.fillRectangle(self.x, self.y + 5, w + 6, 11)
        dc.setColor(COLOR_BLACK if r.fix else COLOR_WHITE, COLOR_TRANSPARENT)
        dc.drawText(self.x + 3, self.y, 0, word, 0)
        self.x += w + 6

    def slots(self, dc, slots, bead):
        """The episode's peak-zone slots as swatches (start at the left), then
        the bead itself at 1/3 scale with the same equal-area rings."""
        for s in slots:
            dc.setColor(HR_RAMP[s], COLOR_TRANSPARENT)
            dc.fillRectangle(self.x, self.y + 6, 5, 9)
            self.x += 6
        self.x += 8
        cx, cy, rr = self.x, self.y + 10, 7
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        dc.fillCircle(cx, cy, rr + 1)
        nb = 3                                   # 3 rings at this size
        ns = len(slots)
        for j in range(nb - 1, -1, -1):
            z = max(slots[idiv(j * ns, nb):idiv((j + 1) * ns, nb)])
            dc.setColor(HR_RAMP[z], COLOR_TRANSPARENT)
            dc.fillCircle(cx, cy, [4, 6, 7][j])


# -------------------------------------------------------------------- sheet --

DATE = (2026, 11, 10)
OFF = -8 * 3600


def frame(readout, r):
    dc = TextDc()
    st = chrome_state(DATE, OFF, 3, r.now)
    st.gpsFix = r.fix
    st.phoneConnected = True
    st.breach = r.breach
    for c in twchrome.v2_chrome():
        c.render(dc, st)
    readout.render(dc, r)
    return twchrome.glass(dc.img), dc.calls


def main():
    k = 3
    recs = [after_run(), fresh_sim()]
    opts = [("A  current", Current()), ("B  HUD", Hud()),
            ("C  instruments", Instruments())]
    pad, lab, hdr, cap = 14, 0, 44, 22
    fw, fh = device.W * k, device.H * k
    W = pad + len(opts) * (fw + pad)
    H = hdr + len(recs) * (fh + cap + pad) + pad
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    big = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    small = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    for j, (name, _) in enumerate(opts):
        d.text((pad + j * (fw + pad), 14), name, font=big, fill=(240, 240, 120))
    y = hdr
    for r in recs:
        for j, (name, ro) in enumerate(opts):
            img, calls = frame(ro, r)
            x = pad + j * (fw + pad)
            sheet.paste(img.resize((fw, fh), Image.NEAREST), (x, y))
            d.text((x, y + fh + 4), "{}  ({} Dc calls)".format(r.name, calls),
                   font=small, fill=(170, 170, 170))
        y += fh + cap + pad
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "diag-compare.png")
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
