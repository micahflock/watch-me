#!/usr/bin/env python3
"""breach_compare.py -- the two-worlds V2 "CONTAINMENT BREACH" easter egg
(owner, 2026-10).

When the day's movement outgrows the dish, hazard tape goes across the
middle of the glass: /////CONTAINMENT BREACH////, black and amber (the
palette's COLOR_YELLOW is amber 0xFFAA00 -- there is no lemon yellow).

Trigger: the grove's act_units (the day's movement, steps/min // 6 summed
per minute) >= BREACH_ACT. 4200 is where every growth channel of the moss
has maxed out -- cushion radius caps at 3000, tuft size at 3120, tuft
count (7) at 4200 -- so the organism literally cannot grow any more.
About 25-28k steps; the synthetic active day (22k) never trips it, the
heavy day (82k) trips at 11:30. act_units resets at midnight with the
rest of the day record and survives a reload (MossState), so the banner
does too.

Lettering: the face's own day-of-week font (tw_dow.png, 8 x 10 px, 2 px
strokes) -- O T A M E R H lifted straight from the strip, C N I B drawn to
match. On the watch the text would be ONE small pre-rendered bitmap
(black on transparent), loaded only when the banner first fires; the tape
and stripes are plain fillRectangle / fillPolygon.

Options (rows):
  A tape      amber band, black 45-degree stripes at both ends, black text
              in an amber window -- classic hazard tape
  B inverse   black band, amber stripes + amber text, 1 px amber rules
              top and bottom
  C framed    A with black/amber striped rules above and below the band

    python3 sketches/breach_compare.py
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import OUT, load_algo, mins, sheet
from day import synthetic_day
from device import COLOR_BLACK, COLOR_YELLOW, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc, DRAWABLES

BREACH_ACT = 4200
TEXT = "CONTAINMENT BREACH"
GAP = 1                    # px between letters (the DOW strip uses 2)
SPACE = 4                  # px for the word space

# --- the lettering --------------------------------------------------------

DRAWN = {   # new glyphs in the DOW font's style (8 x 10, 2 px strokes)
    "C": [".#######", "########", "##......", "##......", "##......",
          "##......", "##......", "##......", "########", ".#######"],
    "N": [".######.", "########", "##....##", "##....##", "##....##",
          "##....##", "##....##", "##....##", "##....##", "##....##"],
    "I": ["########", "########", "...##...", "...##...", "...##...",
          "...##...", "...##...", "...##...", "########", "########"],
    "B": ["#######.", "########", "##....##", "##....##", "#######.",
          "#######.", "##....##", "##....##", "########", "#######."],
}


def strip_glyphs():
    """Letters lifted from the shipped day-of-week strip."""
    im = Image.open(os.path.join(DRAWABLES, "tw_dow.png")).convert("RGBA")
    px = im.load()
    out = {}
    for i, pair in enumerate(["SU", "MO", "TU", "WE", "TH", "FR", "SA"]):
        for j, ch in enumerate(pair):
            x0 = i * 18 + j * 10
            out[ch] = ["".join("#" if px[x0 + x, y][3] else "."
                               for x in range(8)) for y in range(10)]
    return out


GLYPHS = strip_glyphs()
GLYPHS.update(DRAWN)


def text_bitmap(color):
    """TEXT as one RGBA bitmap (glyph pixels = color, rest transparent) --
    exactly what would ship as a resource PNG."""
    w = 0
    for i, ch in enumerate(TEXT):
        w += SPACE if ch == " " else 8
        if i < len(TEXT) - 1 and ch != " " and TEXT[i + 1] != " ":
            w += GAP
    img = Image.new("RGBA", (w, 10), (0, 0, 0, 0))
    px = img.load()
    rgb = device._rgb(color) + (255,)
    x = 0
    for i, ch in enumerate(TEXT):
        if ch == " ":
            x += SPACE
            continue
        for y, row in enumerate(GLYPHS[ch]):
            for dx, c in enumerate(row):
                if c == "#":
                    px[x + dx, y] = rgb
        x += 8
        if i < len(TEXT) - 1 and TEXT[i + 1] != " ":
            x += GAP
    return img


# --- the banner -----------------------------------------------------------

Y0, BH = 82, 16            # band rows 82..97: centred on the glass (y = 90)
PITCH, SW = 8, 4           # stripe pitch / width (px)


class Banner:
    def __init__(self, style):
        self.style = style
        fg = COLOR_BLACK if style in ("A", "C") else COLOR_YELLOW
        self.text = text_bitmap(fg)
        self.tx = (device.W - self.text.width) // 2
        self.ty = Y0 + (BH - 10) // 2

    def stripes(self, dc, y0, h, col):
        """45-degree '/' stripes across the full width, rows y0..y0+h-1."""
        dc.setColor(col, COLOR_TRANSPARENT)
        for x in range(-h, device.W + PITCH, PITCH):
            dc.fillPolygon([(x, y0 + h - 1), (x + SW - 1, y0 + h - 1),
                            (x + SW - 1 + h - 1, y0), (x + h - 1, y0)])

    def render(self, dc, state):
        if state.breach is not True:
            return
        bg = COLOR_YELLOW if self.style in ("A", "C") else COLOR_BLACK
        fg = COLOR_BLACK if self.style in ("A", "C") else COLOR_YELLOW
        dc.setColor(bg, COLOR_TRANSPARENT)
        dc.fillRectangle(0, Y0, device.W, BH)
        self.stripes(dc, Y0, BH, fg)
        dc.setColor(bg, COLOR_TRANSPARENT)                 # text window
        dc.fillRectangle(self.tx - 4, Y0, self.text.width + 8, BH)
        dc.drawBitmap(self.tx, self.ty, self.text)
        if self.style == "B":
            dc.setColor(COLOR_YELLOW, COLOR_TRANSPARENT)
            dc.fillRectangle(0, Y0 - 1, device.W, 1)
            dc.fillRectangle(0, Y0 + BH, device.W, 1)
        if self.style == "C":
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
            dc.fillRectangle(0, Y0 - 5, device.W, 4)
            dc.fillRectangle(0, Y0 + BH + 1, device.W, 4)
            self.stripes(dc, Y0 - 5, 4, COLOR_YELLOW)
            self.stripes(dc, Y0 + BH + 1, 4, COLOR_YELLOW)


OPTIONS = [("A tape", Banner("A")), ("B inverse", Banner("B")),
           ("C framed", Banner("C"))]
COLS = [("heavy", "11:29"), ("heavy", "11:31"), ("heavy", "23:30"),
        ("active", "23:30")]
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4


def face(banner, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 1
    st.breach = grove.rec.act_units >= BREACH_ACT
    for c in twchrome.v2_chrome():
        if isinstance(c, twchrome.North):
            banner.render(dc, st)            # over the chrome, under north
        c.render(dc, st)
    return twchrome.glass(dc.img), grove.rec.act_units


def main():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    groves = {}
    for prof, at in COLS:
        t = mins(at)
        g = load_algo("moss_grove").build()["components"][0]
        for m in range(t + 1):
            g.advance(days[prof][m])
        groves[(prof, at)] = (g, days[prof][t], t)

    print("text bitmap {} x {} px".format(*OPTIONS[0][1].text.size))
    rows = []
    for label, banner in OPTIONS:
        cells = []
        for prof, at in COLS:
            g, snap, t = groves[(prof, at)]
            img, act = face(banner, g, snap, t)
            cells.append((img.resize((device.W * 3, device.H * 3),
                                     Image.NEAREST),
                          "act {} ({})".format(act, "BREACH" if act >= BREACH_ACT
                                               else "contained")))
        rows.append((label, cells))
    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "breach-compare.png"),
          "two-worlds V2 easter egg: CONTAINMENT BREACH at act_units >= {}"
          .format(BREACH_ACT))

    # close-up of the banner band alone, 6x, per option
    z = []
    for label, banner in OPTIONS:
        g, snap, t = groves[("heavy", "23:30")]
        img, _ = face(banner, g, snap, t)
        crop = img.crop((0, Y0 - 8, device.W, Y0 + BH + 8))
        z.append((label, [(crop.resize((crop.width * 5, crop.height * 5),
                                        Image.NEAREST), "")]))
    sheet(z, ["banner, 5x"], os.path.join(OUT, "breach-zoom.png"),
          "CONTAINMENT BREACH banner close-up")


if __name__ == "__main__":
    main()
