#!/usr/bin/env python3
"""bead_size_compare.py -- how much effort-bead SIZE variance a day actually shows.

Owner report (2026-09): "the effort beads mostly end up all about the same size
unless I do a particularly long activity" -- asked for the minimum bead size to
drop by 50% to widen the spread.

Bead radius is `BEAD_MIN + mag/BEAD_DIV` clamped to BEAD_MAX, where `mag` is the
episode's banked magnitude (per elevated-HR minute: `1 + steps_per_min/16`). The
floor and the slope pull in different directions:

  ship  BEAD_MIN=4, BEAD_DIV=30   every episode starts at 4 px, so short efforts
                                  (mag < 30) are ALL exactly 4 -- the flatness
  A     BEAD_MIN=2, BEAD_DIV=30   the literal ask: floor halved, slope untouched
  B     BEAD_MIN=2, BEAD_DIV=20   floor halved AND the slope steepened, which is
                                  what actually separates the middle of the range

Rows are treatments, columns are day states. Prints the per-episode radius table
for each column so the numbers behind the pictures are visible.

    python3 sketches/bead_size_compare.py
"""
import importlib.util
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
from day import synthetic_day

OUT = os.path.join(os.path.dirname(__file__), "out")
SCALE = 2

# (label, BEAD_MIN, BEAD_DIV)
TREATMENTS = [
    ("ship  4 + m/30", 4, 30),
    ("A     2 + m/30", 2, 30),
    ("B     2 + m/20", 2, 20),
]

# Injected episode sets (zone, magnitude). The natural synthetic day only banks
# 4 episodes; the owner's complaint is about a day of MANY mixed-length efforts,
# so that case is built explicitly.
#   mag ~ minutes x (1 + spm/16): a 5-min stair climb ~ 20, a 20-min walk ~ 140,
#   a 45-min run ~ 500.
MIXED = [(4, 6), (4, 22), (5, 55), (4, 14), (6, 140), (5, 90), (4, 35)]


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def load_algo(name):
    path = os.path.join(os.path.dirname(__file__), "algos", name + ".py")
    spec = importlib.util.spec_from_file_location("algo_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render(spec, snap):
    dc = device.Dc(spec.get("background", device.COLOR_BLACK))
    device.perf_reset()
    for c in spec["components"]:
        if hasattr(c, "render"):
            c.render(dc, snap)
    nh, ns, nops = device.perf_read()
    work = (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
            + ns * device.VM_ISIN + nops * device.VM_OP)
    img = dc.masked().resize((device.W * SCALE, device.H * SCALE),
                             Image.NEAREST)
    return img, work


def radii(mod, rec):
    out = []
    for i in range(rec.nepi):
        b = mod.BEAD_MIN + rec.emag[i] // mod.BEAD_DIV
        out.append(min(b, mod.BEAD_MAX))
    return out


def run(mod, profile, at, inject=None, grow=0):
    """Advance a fresh grove to `at`, optionally overwrite its episode list."""
    spec = mod.build()
    comp = spec["components"][0]
    snaps = synthetic_day(profile=profile)
    for t in range(at + 1):
        comp.advance(snaps[t])
    rec = comp.rec
    rec.act_units += grow
    if inject is not None:
        rec.nepi = len(inject)
        for i, (z, mg) in enumerate(inject):
            rec.epz[i] = z
            rec.emag[i] = mg
    img, work = render(spec, snaps[at])
    return img, work, radii(mod, rec)


def cell(img, work, rr):
    wd = "OK" if work <= device.WATCHDOG else "OVER"
    return (img, "~{} VMi [{}]".format(work, wd), rr)


def sheet(rows, col_labels, path, title):
    fw, fh = rows[0][1][0][0].size
    pad, caph, hdr, lab = 8, 32, 30, 115
    ncol = len(col_labels)
    w = lab + ncol * (fw + pad) + pad
    h = hdr + len(rows) * (fh + caph + pad) + pad
    im = Image.new("RGB", (w, h), (24, 24, 24))
    d = ImageDraw.Draw(im)
    d.text((pad, 6), title, fill=(240, 240, 120))
    for j, cl in enumerate(col_labels):
        d.text((lab + pad + j * (fw + pad), hdr - 14), cl, fill=(220, 220, 220))
    y = hdr
    for rl, cells in rows:
        d.text((pad, y + fh // 2), rl, fill=(240, 240, 240))
        for j, (img, cap, rr) in enumerate(cells):
            x = lab + pad + j * (fw + pad)
            im.paste(img, (x, y))
            d.text((x, y + fh + 3), cap, fill=(150, 150, 150))
            d.text((x, y + fh + 16), "r=" + ",".join(str(v) for v in rr),
                   fill=(120, 200, 255))
        y += fh + caph + pad
    im.save(path)
    print(path)


COLUMNS = [
    # (label, profile, at, inject, grow)
    ("morning 7:50", "active", mins("7:50"), None, 0),
    ("mixed efforts 18:20", "active", mins("18:20"), MIXED, 0),
    ("natural day 18:20", "active", mins("18:20"), None, 0),
    ("HEAVY 23:30", "heavy", mins("23:30"), None, 0),
]


def main():
    rows = []
    for label, bmin, bdiv in TREATMENTS:
        mod = load_algo("moss_grove")
        mod.BEAD_MIN = bmin
        mod.BEAD_DIV = bdiv
        cells = []
        print("== {} ==".format(label))
        for cl, profile, at, inject, grow in COLUMNS:
            img, work, rr = run(mod, profile, at, inject, grow)
            print("   {:<22} radii {}".format(cl, rr))
            cells.append(cell(img, work, rr))
        rows.append((label, cells))

    sheet(rows, [c[0] for c in COLUMNS],
          os.path.join(OUT, "bead-size-compare.png"),
          "effort-bead size: floor/slope options  --  radius = MIN + mag/DIV,"
          " cap 18")


if __name__ == "__main__":
    main()
