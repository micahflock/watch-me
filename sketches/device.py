#!/usr/bin/env python3
"""Faithful fr735xt device model for the generative-art sandbox.

This is NOT a loose visual mock. It mirrors the real watch closely enough that
an algorithm proven here ports to Monkey C mechanically:

  - hash16 / isin / zoneIndex / the palette are bit-identical to
    core/src/genart/GenArt.mc (same constants, same integer sine LUT).
  - Integer math is the only math: use idiv()/imod() wherever the Monkey C
    writes `a / b` / `a % b` on Numbers. Monkey C truncates toward zero;
    Python's // and % floor toward negative infinity, so on negative operands
    they DISAGREE (e.g. -6200 / 127 is -48 on the watch, -49 with Python //).
    Getting that wrong is exactly the kind of drift this sandbox exists to
    prevent, so the helpers below are the law.
  - Dc exposes only the primitives Toybox.Graphics gives a watch face. Every
    call is counted (watchdog proxy) and every color is snapped to the 14-color
    palette (off-palette use is flagged, never silently rendered as 24-bit).

Porting rule of thumb (Python sandbox -> Monkey C face):
    Gfx.COLOR_RED        -> dev.COLOR_RED          (or `using ... as Gfx`)
    a / b   (ints)       -> idiv(a, b)
    a % b   (ints)       -> imod(a, b)
    hash16/isin/zoneIndex are spelled the same in both.
Everything else is `var`/syntax. If a frame looks right here, it looks right
on the watch (modulo arc/circle rasterization, which only the SDK sim nails;
see CLAUDE.md / sketches/README.md).
"""

import math

from PIL import Image, ImageDraw

# ---------------------------------------------------------------- display ----

W, H = 215, 180
CX, CY, R = 107.0, 90.0, 107.5     # bezel circle; top/bottom read as chords
WATCHDOG = 25000                   # ~25-30k VM instr/onUpdate (docs/memory-budget)

# The only 14 colors that exist on this device, by their Gfx.COLOR_* names.
# COLOR_YELLOW is amber (0xFFAA00) on the 735XT, per CLAUDE.md.
COLOR_WHITE    = 0xFFFFFF
COLOR_LT_GRAY  = 0xAAAAAA
COLOR_DK_GRAY  = 0x555555
COLOR_BLACK    = 0x000000
COLOR_RED      = 0xFF0000
COLOR_DK_RED   = 0xAA0000
COLOR_ORANGE   = 0xFF5500
COLOR_YELLOW   = 0xFFAA00
COLOR_GREEN    = 0x00FF00
COLOR_DK_GREEN = 0x00AA00
COLOR_BLUE     = 0x00AAFF
COLOR_DK_BLUE  = 0x0000FF
COLOR_PURPLE   = 0xAA00FF
COLOR_PINK     = 0xFF00FF
COLOR_TRANSPARENT = -1

PALETTE = [
    COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY, COLOR_BLACK,
    COLOR_RED, COLOR_DK_RED, COLOR_ORANGE, COLOR_YELLOW,
    COLOR_GREEN, COLOR_DK_GREEN, COLOR_BLUE, COLOR_DK_BLUE,
    COLOR_PURPLE, COLOR_PINK,
]

# Direction flags for drawArc, mirroring Gfx.ARC_*.
ARC_CLOCKWISE = 0
ARC_COUNTER_CLOCKWISE = 1


def _rgb(c):
    return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)


def _nearest_palette(c):
    r, g, b = _rgb(c)
    best, bestd = COLOR_BLACK, 1 << 30
    for p in PALETTE:
        pr, pg, pb = _rgb(p)
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bestd:
            best, bestd = p, d
    return best


# --------------------------------------------------- integer-math discipline -

def i32(x):
    """Wrap to signed 32-bit, like a Monkey C Number overflowing."""
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def idiv(a, b):
    """Integer division truncating toward zero (Monkey C `/` on Numbers)."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def imod(a, b):
    """Remainder with the sign of the dividend (Monkey C `%` on Numbers)."""
    return a - idiv(a, b) * b


# ------------------------------------------------- GenArt.mc, ported exactly --

def hash16(a, b, c):
    """Bit-identical to GenArt.hash16 (FNV-flavored 16-bit). Returns 0..0x7FFF."""
    h = 0x5BD1
    h = ((h ^ (a & 0xFFFF)) * 0x6CD) & 0xFFFF
    h = h ^ (h >> 7)
    h = ((h ^ (b & 0xFFFF)) * 0x6CD) & 0xFFFF
    h = h ^ (h >> 7)
    h = ((h ^ (c & 0xFFFF)) * 0x6CD) & 0xFFFF
    h = h ^ (h >> 7)
    return h & 0x7FFF


# 256-entry integer sine LUT, value = (sin(2*pi*i/256) * 127).toNumber().
# toNumber() truncates toward zero; Python int() does too. Same constant
# (0.02454369) as GenArt.mc so the table is identical entry for entry.
_SIN = [int(math.sin(i * 0.02454369) * 127.0) for i in range(256)]


def isin(p):
    """GenArt.isin: phase p in 1/256ths of a turn, returns -127..127."""
    return _SIN[p & 255]


ZONE_BOUNDS = [65, 90, 105, 125, 145, 160]
ZONE_COLORS = [
    COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
    COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_DK_GRAY,  # idx 7 = HR unknown
]


def zoneIndex(hr):
    """GenArt.zoneIndex: HR bpm -> zone color index (7 if hr is None)."""
    if hr is None:
        return 7
    for i in range(6):
        if hr < ZONE_BOUNDS[i]:
            return i
    return 6


# ---------------------------------------------------------- drawing context --

class Dc:
    """Stand-in for the Graphics.Dc handed to render(). Exposes only the
    primitives a watch face actually has, counts every call (watchdog proxy),
    and snaps colors to the 14-color palette."""

    def __init__(self, bg=COLOR_BLACK):
        self.img = Image.new("RGB", (W, H), _rgb(bg))
        self._d = ImageDraw.Draw(self.img)
        self._fg = COLOR_WHITE
        self.calls = 0           # primitive-call count this frame
        self.offpalette = 0      # times a non-palette color was snapped

    def getWidth(self):
        return W

    def getHeight(self):
        return H

    def clear(self):
        self._d.rectangle((0, 0, W, H), fill=_rgb(self._fg))

    def setColor(self, fg, bg):
        self._fg = self._resolve(fg)

    def _resolve(self, c):
        if c == COLOR_TRANSPARENT:
            return c
        if c not in PALETTE:
            self.offpalette += 1
            return _nearest_palette(c)
        return c

    def fillRectangle(self, x, y, w, h):
        self.calls += 1
        x, y, w, h = int(x), int(y), int(w), int(h)
        self._d.rectangle((x, y, x + w - 1, y + h - 1), fill=_rgb(self._fg))

    def drawLine(self, x0, y0, x1, y1):
        self.calls += 1
        self._d.line((int(x0), int(y0), int(x1), int(y1)), fill=_rgb(self._fg))

    def fillCircle(self, x, y, r):
        self.calls += 1
        x, y, r = int(x), int(y), int(r)
        if r <= 0:
            self._d.point((x, y), fill=_rgb(self._fg))
        else:
            self._d.ellipse((x - r, y - r, x + r, y + r), fill=_rgb(self._fg))

    def drawArc(self, x, y, r, direction, deg_start, deg_end):
        # Garmin: degrees CCW from 3 o'clock. PIL: degrees CW from 3 o'clock.
        # Convert by negating and swapping. (Approximate — arc rasterization
        # is the one thing only the SDK sim renders exactly; see module docs.)
        self.calls += 1
        x, y, r = int(x), int(y), int(r)
        if direction == ARC_COUNTER_CLOCKWISE:
            a0, a1 = -deg_end, -deg_start
        else:
            a0, a1 = deg_start, deg_end
        self._d.arc((x - r, y - r, x + r, y + r), a0, a1, fill=_rgb(self._fg))

    def masked(self):
        """Apply the round-bezel mask, returning the visible image."""
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).ellipse((CX - R, CY - R, CX + R, CY + R), fill=255)
        out = Image.new("RGB", (W, H), (0, 0, 0))
        out.paste(self.img, (0, 0), mask)
        return out
