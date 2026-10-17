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

+40% (owner, 2026-10, "stretch 40% in Z" read as vertical): breach-tall*.png.
Not a resample -- the letters are redrawn at 8 x 14 (TALL) and the tape /
rails / stripes re-proportioned; see Banner.

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


def rows(*spec):
    """(pattern, count) runs -> glyph rows."""
    out = []
    for pat, n in spec:
        out += [pat] * n
    return out


# 40% taller (owner, 2026-10): every letter REDRAWN at 8 x 14, not scaled --
# a 1.4x resample of 10 rows doubles some rows and not others, so strokes go
# uneven. Here strokes stay 2 px in both directions, crossbars sit on the
# same centred rows 6-7, and the extra height goes into the stems.
TALL = {
    "C": rows((".#######", 1), ("########", 1), ("##......", 10),
              ("########", 1), (".#######", 1)),
    "O": rows((".######.", 1), ("########", 1), ("##....##", 10),
              ("########", 1), (".######.", 1)),
    "N": rows((".######.", 1), ("########", 1), ("##....##", 12)),
    "T": rows(("########", 2), ("...##...", 12)),
    "A": rows((".######.", 1), ("########", 1), ("##....##", 4),
              ("########", 2), ("##....##", 6)),
    "I": rows(("########", 2), ("...##...", 10), ("########", 2)),
    "M": rows((".######.", 1), ("########", 2), ("##.##.##", 6),
              ("##....##", 5)),
    "E": rows(("#######.", 2), ("##......", 4), ("#####...", 2),
              ("##......", 4), ("#######.", 2)),
    "B": rows(("#######.", 1), ("########", 1), ("##....##", 4),
              ("#######.", 2), ("##....##", 4), ("########", 1),
              ("#######.", 1)),
    "R": rows(("#######.", 1), ("########", 1), ("##....##", 4),
              ("#######.", 1), ("######..", 1), ("##.###..", 1),
              ("##..###.", 2), ("##...###", 2), ("##....##", 1)),
    "H": rows(("##....##", 6), ("########", 2), ("##....##", 6)),
}
assert all(len(g) == 14 and all(len(r) == 8 for r in g)
           for g in TALL.values()), "tall glyphs must be 8 x 14"


def text_bitmap(color, glyphs=None):
    """TEXT as one RGBA bitmap (glyph pixels = color, rest transparent) --
    exactly what would ship as a resource PNG."""
    glyphs = glyphs or GLYPHS
    gh = len(glyphs["C"])
    w = 0
    for i, ch in enumerate(TEXT):
        w += SPACE if ch == " " else 8
        if i < len(TEXT) - 1 and ch != " " and TEXT[i + 1] != " ":
            w += GAP
    img = Image.new("RGBA", (w, gh), (0, 0, 0, 0))
    px = img.load()
    rgb = device._rgb(color) + (255,)
    x = 0
    for i, ch in enumerate(TEXT):
        if ch == " ":
            x += SPACE
            continue
        for y, row in enumerate(glyphs[ch]):
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
    """tall=False: the 10 px original (band 16, rails 4, 45-degree stripes).
    tall=True: the 40%-taller redraw -- 14 px letters, band 22 (16 x 1.4),
    rails 6 (4 x 1.4, rounded), still centred on y = 90. The stripes keep
    their horizontal rhythm (width 4, pitch 8, run 15) -- a vertical stretch
    changes no x -- so they just steepen (45 -> ~55 degrees) and each end of
    the tape keeps the same stripe count."""

    def __init__(self, style, tall=False):
        self.style = style
        fg = COLOR_BLACK if style in ("A", "C") else COLOR_YELLOW
        self.text = text_bitmap(fg, TALL if tall else None)
        self.bh = 22 if tall else BH
        self.rail = 6 if tall else 4
        self.y0 = 90 - self.bh // 2
        self.run = BH - 1                   # stripe x-run, shared by both
        self.tx = (device.W - self.text.width) // 2
        self.ty = self.y0 + (self.bh - self.text.height) // 2

    def stripes(self, dc, y0, h, col, run=None):
        """'/' stripes across the full width, rows y0..y0+h-1, rising `run`
        px over the band (run = h - 1 is 45 degrees)."""
        run = h - 1 if run is None else run
        dc.setColor(col, COLOR_TRANSPARENT)
        for x in range(-run, device.W + PITCH, PITCH):
            dc.fillPolygon([(x, y0 + h - 1), (x + SW - 1, y0 + h - 1),
                            (x + SW - 1 + run, y0), (x + run, y0)])

    def render(self, dc, state):
        if state.breach is not True:
            return
        Y0, BH = self.y0, self.bh
        bg = COLOR_YELLOW if self.style in ("A", "C") else COLOR_BLACK
        fg = COLOR_BLACK if self.style in ("A", "C") else COLOR_YELLOW
        dc.setColor(bg, COLOR_TRANSPARENT)
        dc.fillRectangle(0, Y0, device.W, BH)
        self.stripes(dc, Y0, BH, fg, self.run)
        dc.setColor(bg, COLOR_TRANSPARENT)                 # text window
        dc.fillRectangle(self.tx - 4, Y0, self.text.width + 8, BH)
        dc.drawBitmap(self.tx, self.ty, self.text)
        if self.style == "B":
            dc.setColor(COLOR_YELLOW, COLOR_TRANSPARENT)
            dc.fillRectangle(0, Y0 - 1, device.W, 1)
            dc.fillRectangle(0, Y0 + BH, device.W, 1)
        if self.style == "C":
            r = self.rail
            dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)   # rail + 1 px seam
            dc.fillRectangle(0, Y0 - r - 1, device.W, r + 1)
            dc.fillRectangle(0, Y0 + BH, device.W, r + 1)
            self.stripes(dc, Y0 - r - 1, r, COLOR_YELLOW)
            self.stripes(dc, Y0 + BH + 1, r, COLOR_YELLOW)


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


TALL_OPTIONS = [("A tape", Banner("A")), ("A tape +40%", Banner("A", True)),
                ("B inverse +40%", Banner("B", True)),
                ("C framed +40%", Banner("C", True))]


def tall_sheets():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    cols = [("heavy", "11:31"), ("heavy", "23:30")]
    groves = {}
    for prof, at in cols:
        t = mins(at)
        g = load_algo("moss_grove").build()["components"][0]
        for m in range(t + 1):
            g.advance(days[prof][m])
        groves[(prof, at)] = (g, days[prof][t], t)
    rows_, z = [], []
    for label, banner in TALL_OPTIONS:
        cells = []
        for prof, at in cols:
            g, snap, t = groves[(prof, at)]
            img, _ = face(banner, g, snap, t)
            cells.append((img.resize((device.W * 3, device.H * 3),
                                     Image.NEAREST), ""))
        rows_.append((label, cells))
        g, snap, t = groves[("heavy", "23:30")]
        img, _ = face(banner, g, snap, t)
        crop = img.crop((0, 66, device.W, 114))
        z.append((label, [(crop.resize((crop.width * 5, crop.height * 5),
                                        Image.NEAREST), "")]))
    sheet(rows_, ["{} {}".format(p, a) for p, a in cols],
          os.path.join(OUT, "breach-tall.png"),
          "CONTAINMENT BREACH, 40% taller (letters redrawn at 8x14)")
    sheet(z, ["banner, 5x"], os.path.join(OUT, "breach-tall-zoom.png"),
          "CONTAINMENT BREACH +40%: original vs redrawn")


if __name__ == "__main__":
    main()
    tall_sheets()
