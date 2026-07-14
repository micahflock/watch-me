#!/usr/bin/env python3
"""bead_compare.py -- comparison sheet for the effort-bead CONTIGUITY fix.

2026-07-13 wrist: on a low-movement morning the effort beads float in black
space, detached from the moss. Cause: the root-star keep-out (root_len + 20
+ scl(6), sized for the worst-case bead) exceeds the morning rim, so the
clamp pushes every bead off the cushion -- and, in the tuft branch, off its
own tuft. Two proposals against ship:

  A  moss_grove_stalks   exact per-bead keep-out + kinked DK_GREEN stalks
                         connecting any still-displaced bead back to the
                         moss (lichen podetia, the root star's segmented
                         language). Star legibility preserved.
  B  moss_grove_rimhug   delete the keep-out; beads sit on the crown / their
                         real tuft and the root star (drawn last) rides on
                         top. Smallest diff, but warm beads under the tips.

Columns: the wrist-photo situation (active day at 6:45 with two small zone-4
episodes injected, the way a stairs-climb morning produces them before any
real activity), the natural active-day morning/midday (the detachment window),
the grown evening (all three should converge -- the fix must self-heal), and
the HEAVY day at 23:30 (saturation: the budget check).

    python3 sketches/bead_compare.py
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

TREATMENTS = [
    ("ship", "moss_grove"),
    ("A  stalks", "moss_grove_stalks"),
    ("B  rim-hug", "moss_grove_rimhug"),
]

ACTIVE_SAMPLES = ["7:15", "7:50", "13:05", "18:20"]


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


def cell(img, work):
    wd = "OK" if work <= device.WATCHDOG else "OVER"
    return (img, "~{} VMi [{}]".format(work, wd))


def sheet(rows, col_labels, path, title):
    fw, fh = rows[0][1][0][0].size
    pad, caph, hdr, lab = 8, 20, 26, 110
    ncol = len(col_labels)
    w = lab + ncol * (fw + pad) + pad
    h = hdr + len(rows) * (fh + caph + pad) + pad
    im = Image.new("RGB", (w, h), (24, 24, 24))
    d = ImageDraw.Draw(im)
    d.text((pad, 6), title, fill=(240, 240, 120))
    for j, cl in enumerate(col_labels):
        d.text((lab + pad + j * (fw + pad), hdr - 14), cl,
               fill=(220, 220, 220))
    y = hdr
    for rl, cells in rows:
        d.text((pad, y + fh // 2), rl, fill=(240, 240, 240))
        for j, (img, cap) in enumerate(cells):
            x = lab + pad + j * (fw + pad)
            im.paste(img, (x, y))
            d.text((x, y + fh + 3), cap, fill=(150, 150, 150))
        y += fh + caph + pad
    im.save(path)
    print(path)


def main():
    photo_at = mins("6:45")
    samples = [mins(s) for s in ACTIVE_SAMPLES]
    heavy_at = mins("23:30")
    rows = []
    for label, algo in TREATMENTS:
        mod = load_algo(algo)
        cells = []

        # -- wrist-photo repro: barely awake, two small zone-4 episodes --
        spec = mod.build()
        comp = spec["components"][0]
        snaps = synthetic_day(profile="active")
        for t in range(photo_at + 1):
            comp.advance(snaps[t])
        rec = comp.rec
        rec.act_units += 550          # a bit of puttering-about growth
        rec.nepi = 2                  # stairs / hurry blips before any workout
        rec.epz[0] = 4
        rec.emag[0] = 5
        rec.epz[1] = 4
        rec.emag[1] = 2
        cells.append(cell(*render(spec, snaps[photo_at])))

        # -- the natural active day (fresh replay, untouched record) --
        spec = mod.build()
        comp = spec["components"][0]
        got = {}
        for t in range(1440):
            comp.advance(snaps[t])
            if t in samples:
                got[t] = render(spec, snaps[t])
        for t in samples:
            cells.append(cell(*got[t]))

        # -- saturation: the heavy day at 23:30 (budget check) --
        spec = mod.build()
        comp = spec["components"][0]
        hsnaps = synthetic_day(profile="heavy")
        for t in range(heavy_at + 1):
            comp.advance(hsnaps[t])
        cells.append(cell(*render(spec, hsnaps[heavy_at])))

        rows.append((label, cells))

    sheet(rows,
          ["6:45 +2 z4 (photo)"] + ACTIVE_SAMPLES + ["HEAVY 23:30"],
          os.path.join(OUT, "bead-contiguity-compare.png"),
          "effort-bead contiguity: ship vs A (stalks) vs B (no keep-out)  --  "
          "active day + heavy saturation")


if __name__ == "__main__":
    main()
