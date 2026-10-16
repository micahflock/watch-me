#!/usr/bin/env python3
"""border_aa_compare.py -- anti-alias the two-worlds white field border with
grey pixels (owner, 2026-10).

The panel has no alpha, so anti-aliasing means painting the pixels the IDEAL
line only partly covers in a grey: DK_GRAY (0x555555 ~ 1/3) and, for a
two-level ramp, LT_GRAY (0xAAAAAA ~ 2/3). Coverage of a 1 px-wide line is
taken as c = 1 - d, d = distance from the pixel centre to the ideal path:
the true r = 95.8 circle about (107.5, 90.7) for the rim arcs (not their
4-degree chords) and the true segments for the chord, slant and notch.
White pixels stay white; the exact horizontal edges (chord, notch floor)
get no grey because every neighbour is a whole pixel away.

Pixel centres sit on integer coordinates (drawLine lights the integer points
it passes), matching how BorderComponent rounds its vertices.

The grey pixels never change, so on the watch they are a static list drawn
after the border; captions give the pixel and run counts.

SHIPPED (owner, 2026-10): "dk+lt ramp". The other OPTIONS stay here as
alternatives: `--emit` regenerates the face's pixel tables from any of them
-- both the BEGIN/END AA block in faces/two-worlds-v2/.../TwoWorldsV2View.mc
and sketches/border_aa_pixels.py (twchrome.Border's mirror) -- so switching
is one command and a rebuild, and the watch only ever carries one table:

    python3 sketches/border_aa_compare.py                     # the sheets
    python3 sketches/border_aa_compare.py --emit              # SHIPPED
    python3 sketches/border_aa_compare.py --emit "dk, both sides"
"""
import math
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import OUT, load_algo, mins, sheet
from day import synthetic_day
from device import COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_TRANSPARENT
from north_compare import chrome_state
from twchrome import ChromeDc

W, H = device.W, device.H
CX, CY, R = 107.5, 90.7, 95.8
SEGS = [((16, 62), (134, 62)), ((134, 62), (166, 15)),
        ((70, 163), (145, 163)), ((70, 163), (57, 172)),
        ((145, 163), (158, 172))]
ARCS = [(37.7, 148.0), (212.0, 287.4)]     # bearings, 0 = 12 o'clock, CW


def field_mask():
    fm = twchrome.FieldMask()
    inside = [[True] * W for _ in range(H)]
    cx, cw = [0] * 4, [0] * 4
    for y in range(H):
        for c in range(fm.scanline(y, cx, cw)):
            for x in range(cx[c], cx[c] + cw[c]):
                inside[y][x] = False
    return inside


INSIDE = field_mask()


def white_pixels():
    dc = ChromeDc()
    twchrome.Border(aa=False).render(dc, None)
    px = dc.img.load()
    return {(x, y) for y in range(H) for x in range(W)
            if px[x, y] == (255, 255, 255)}


# Where the watch's drawLine rasterizes the border differently from the
# sandbox (measured in the SDK sim, 2026-10: the release PRG with no AA, its
# border pixels diffed against twchrome.Border). Five diagonal steps land one
# pixel over, and the notch wall's last endpoint pixel is not drawn. Without
# this the table painted grey over 4 real white pixels on the watch.
DEVICE_ONLY = {(14, 107), (192, 137), (193, 135), (194, 133), (202, 109)}
SANDBOX_ONLY = {(13, 107), (191, 137), (192, 135), (193, 133), (201, 109),
                (158, 172)}
WHITE = (white_pixels() - SANDBOX_ONLY) | DEVICE_ONLY


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def arc_dist(px, py, b0, b1):
    b = math.degrees(math.atan2(px - CX, -(py - CY))) % 360.0
    if b0 <= b <= b1:
        return abs(math.hypot(px - CX, py - CY) - R)
    ends = []
    for e in (b0, b1):
        r = math.radians(e)
        ends.append(math.hypot(px - (CX + R * math.sin(r)),
                               py - (CY - R * math.cos(r))))
    return min(ends)


def coverage():
    """{(x, y): c} for every non-white pixel the ideal path partly covers."""
    out = {}
    for y in range(H):
        for x in range(W):
            if (x, y) in WHITE:
                continue
            d = min([seg_dist(x, y, a, b) for a, b in SEGS]
                    + [arc_dist(x, y, b0, b1) for b0, b1 in ARCS])
            if d < 1.0:
                out[(x, y)] = 1.0 - d
    return out


COV = coverage()


def runs(pixels):
    """Merge pixels into horizontal runs -> number of fillRectangle calls."""
    n = 0
    for x, y in pixels:
        if (x - 1, y) not in pixels:
            n += 1
    return n


class AA:
    """Static grey pixels: DK_GRAY where lo <= c < hi, LT_GRAY where c >= hi
    (hi = None: one level, everything >= lo is DK_GRAY). side: 'both' or
    'chrome' (skip pixels inside the dish, never over the moss)."""

    def __init__(self, lo, hi=None, side="both"):
        self.dk, self.lt = set(), set()
        for (x, y), c in COV.items():
            if side == "chrome" and INSIDE[y][x]:
                continue
            if c < lo:
                continue
            if hi is not None and c >= hi:
                self.lt.add((x, y))
            else:
                self.dk.add((x, y))

    def render(self, dc, state):
        for col, pix in ((COLOR_DK_GRAY, self.dk), (COLOR_LT_GRAY, self.lt)):
            if pix:
                dc.setColor(col, COLOR_TRANSPARENT)
                for x, y in pix:
                    dc.fillRectangle(x, y, 1, 1)

    def caption(self):
        n = len(self.dk) + len(self.lt)
        return "{} px, {} runs".format(n, runs(self.dk) + runs(self.lt))


OPTIONS = [
    ("none", None),
    ("dk, chrome side", AA(0.30, side="chrome")),
    ("dk, both sides", AA(0.30)),
    ("dk, both, light", AA(0.42)),
    ("dk+lt ramp", AA(0.25, 0.55)),
]
SHIPPED = "dk+lt ramp"
COLS = [("active", "7:50"), ("active", "13:05"), ("heavy", "23:30")]
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4
CROPS = [((140, 20, 172, 52), "slant"), ((178, 100, 210, 132), "right rim"),
         ((14, 120, 46, 152), "left rim"), ((140, 150, 172, 176), "notch corner")]
ZOOM = 10


def face(layer, grove, snap, t):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 1
    for c in twchrome.v2_chrome():
        if isinstance(c, twchrome.Border):
            c = twchrome.Border(aa=False)
        c.render(dc, st)
        if isinstance(c, twchrome.Border) and layer is not None:
            layer.render(dc, st)               # right after the white
    return twchrome.glass(dc.img)


def main():
    days = {p: synthetic_day(profile=p) for p in ("active", "heavy")}
    groves = {}
    for prof, at in COLS:
        t = mins(at)
        g = load_algo("moss_grove").build()["components"][0]
        for m in range(t + 1):
            g.advance(days[prof][m])
        groves[(prof, at)] = (g, days[prof][t], t)

    rows, zoom = [], []
    for label, layer in OPTIONS:
        cap = layer.caption() if layer is not None else ""
        if cap:
            print("{:18s} {}".format(label, cap))
        cells = []
        for prof, at in COLS:
            g, snap, t = groves[(prof, at)]
            cells.append((face(layer, g, snap, t)
                          .resize((W * 3, H * 3), Image.NEAREST), cap))
        rows.append((label, cells))
        g, snap, t = groves[("active", "7:50")]
        img = face(layer, g, snap, t)
        zc = []
        for box, _ in CROPS:
            c = img.crop(box)
            zc.append((c.resize((c.width * ZOOM, c.height * ZOOM),
                                Image.NEAREST), ""))
        zoom.append((label, zc))
    sheet(rows, ["{} {}".format(p, a) for p, a in COLS],
          os.path.join(OUT, "border-aa-compare.png"),
          "two-worlds V2: grey anti-aliasing on the white border")
    # the crops differ in width; give each its own sheet column by padding
    wmax = max(c[0].width for r in zoom for c in r[1])
    hmax = max(c[0].height for r in zoom for c in r[1])
    padded = []
    for label, cells in zoom:
        pc = []
        for img, cap in cells:
            canvas = Image.new("RGB", (wmax, hmax), (24, 24, 24))
            canvas.paste(img, (0, 0))
            pc.append((canvas, cap))
        padded.append((label, pc))
    sheet(padded, [n for _, n in CROPS],
          os.path.join(OUT, "border-aa-zoom.png"),
          "anti-aliasing close-ups at 7:50 (10x)")


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEW = os.path.join(REPO, "faces", "two-worlds-v2", "source",
                    "TwoWorldsV2View.mc")
MIRROR = os.path.join(REPO, "sketches", "border_aa_pixels.py")
BEGIN = "    // BEGIN AA"
END = "    // END AA"


def pack(pixels):
    """Two pixels per 32-bit Number: p = x << 8 | y, v = p0 | p1 << 16
    (as a SIGNED literal -- x up to 214 sets bit 31). Odd counts pad with 0
    = pixel (0, 0), off the glass and never an AA pixel; the renderer skips
    it."""
    ps = [(x << 8) | y for x, y in sorted(pixels, key=lambda p: (p[1], p[0]))]
    if len(ps) % 2:
        ps.append(0)
    out = []
    for i in range(0, len(ps), 2):
        v = ps[i] | (ps[i + 1] << 16)
        if v >= 1 << 31:
            v -= 1 << 32
        out.append(v)
    return out


def mc_array(name, vals):
    lines, cur = [], "    const {} = [".format(name)
    for i, v in enumerate(vals):
        tok = str(v) + (", " if i < len(vals) - 1 else "];")
        if len(cur) + len(tok) > 79:
            lines.append(cur.rstrip())
            cur = "        "
        cur += tok
    lines.append(cur)
    return "\n".join(lines)


def emit(label):
    layer = dict(OPTIONS)[label]
    dk, lt = pack(layer.dk), pack(layer.lt)
    block = "\n".join([
        BEGIN + " -- generated by: python3 sketches/border_aa_compare.py "
        "--emit \"{}\"".format(label),
        "    // {} DK_GRAY + {} LT_GRAY px, 2 per Number (x << 8 | y).".format(
            len(layer.dk), len(layer.lt)),
        mc_array("AA_DK", dk if dk else [0]),
        mc_array("AA_LT", lt if lt else [0]),
        END])
    src = open(VIEW).read()
    i, j = src.index(BEGIN), src.index(END) + len(END)
    open(VIEW, "w").write(src[:i] + block + src[j:])
    with open(MIRROR, "w") as f:
        f.write('"""Generated by sketches/border_aa_compare.py --emit "{}":\n'
                'the anti-aliasing pixels twchrome.Border draws (the mirror of\n'
                'the AA_DK / AA_LT tables in TwoWorldsV2View.mc)."""\n\n'
                .format(label))
        f.write("LABEL = {!r}\n".format(label))
        f.write("DK = {!r}\n".format(sorted(layer.dk, key=lambda p: (p[1], p[0]))))
        f.write("LT = {!r}\n".format(sorted(layer.lt, key=lambda p: (p[1], p[0]))))
    print("emitted {!r}: {} dk + {} lt px -> {} + {} Numbers".format(
        label, len(layer.dk), len(layer.lt), len(dk), len(lt)))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--emit":
        emit(sys.argv[2] if len(sys.argv) > 2 else SHIPPED)
    else:
        main()
