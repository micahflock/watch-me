#!/usr/bin/env python3
"""sleep_compare.py -- comparison sheets for the sleep-nucleus treatments.

The original moss_grove sleep clump rendered short/restless nights in the
effort beads' vocabulary (warm filled circles), so a bad night read as a
workout. Of the three proposals, the owner picked B (the silver root star,
2026-07), which now IS moss_grove's sleep treatment; the pool and lunar
alternatives are kept as reference algos. This renders the shipped treatment
against them two ways:

  out/sleep-compare-nights.png   rows = treatments, cols = four nights
                                 (rested/ok/short/broken), all at 18:20 of the
                                 ACTIVE day -- beads, tufts and accent grains
                                 all present, so the sleep-vs-effort
                                 disambiguation is the thing on trial.
  out/sleep-compare-day.png      rows = treatments, cols = times across the
                                 RESTLESS day (natural ~6 h + 3 wakes) -- how
                                 each treatment lives with the organism from
                                 dawn to night.

Nights are set by overriding rec.sleep_seed / rec.wake_seed after replaying
the day (both are read only at render time, so this is a pure view change --
same trick scenarios.py uses via BioBloom's sleep_h).

    python3 sketches/sleep_compare.py
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
    ("ship (B roots)", "moss_grove"),
    ("A  pool: 1 ring/hour", "moss_grove_pool"),
    ("C  lunar clump", "moss_grove_lunar"),
]

# (label, sleep minutes, wake events)
NIGHTS = [
    ("rested 9h", 540, 0),
    ("ok 6.5h", 390, 0),
    ("short 4h", 240, 0),
    ("broken 6h +3 wakes", 360, 3),
]

DAY_SAMPLES = ["6:30", "7:50", "13:05", "21:45"]


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


def sheet(rows, col_labels, path, title):
    """rows: list of (row_label, [(img, caption), ...])."""
    fw, fh = rows[0][1][0][0].size
    pad, caph, hdr, lab = 8, 20, 26, 150
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


def nights_sheet():
    at = mins("18:20")
    snaps = synthetic_day(profile="active")
    rows = []
    for label, algo in TREATMENTS:
        spec = load_algo(algo).build()
        comp = spec["components"][0]
        for t in range(at + 1):
            comp.advance(snaps[t])
        rec = comp.rec
        cells = []
        for nl, smin, wk in NIGHTS:
            rec.sleep_seed = smin
            rec.wake_seed = wk
            img, work = render(spec, snaps[at])
            wd = "OK" if work <= device.WATCHDOG else "OVER"
            cells.append((img, "~{} VMi [{}]".format(work, wd)))
        rows.append((label, cells))
    sheet(rows, [n[0] for n in NIGHTS],
          os.path.join(OUT, "sleep-compare-nights.png"),
          "sleep treatments x nights  --  active day @ 18:20 "
          "(red + magenta effort beads on the rim)")


def day_sheet():
    samples = [mins(s) for s in DAY_SAMPLES]
    want = set(samples)
    rows = []
    for label, algo in TREATMENTS:
        spec = load_algo(algo).build()
        comp = spec["components"][0]
        snaps = synthetic_day(profile="restless")
        got = {}
        for t in range(1440):
            comp.advance(snaps[t])
            if t in want:
                got[t] = render(spec, snaps[t])
        cells = []
        for t in samples:
            img, work = got[t]
            wd = "OK" if work <= device.WATCHDOG else "OVER"
            cells.append((img, "~{} VMi [{}]".format(work, wd)))
        rows.append((label, cells))
    sheet(rows, DAY_SAMPLES,
          os.path.join(OUT, "sleep-compare-day.png"),
          "sleep treatments across the RESTLESS day (~6 h slept, 3 wakes)")


if __name__ == "__main__":
    nights_sheet()
    day_sheet()
