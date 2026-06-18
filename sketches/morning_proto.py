#!/usr/bin/env python3
"""morning_proto.py -- compare sleep-seeded morning treatments side by side.

scrub.py shows ONE algo across a day; this shows several SEED STYLES x SLEEP
amounts at a fixed morning minute, which is the thing we actually want to judge
here: "what does the centre look like when I glance at it in the morning, having
slept N hours, before I've taken many steps?"

    python3 sketches/morning_proto.py [--at 7:30] [--day rest] [--scale 2]

Rows = seed styles (rings/rosette/spores/bud). Cols = hours slept. Each cell is
the dish at the chosen minute, captioned with the watchdog/RAM proxies so we can
see the morning render stays trivially cheap. Output: sketches/out/morning-<at>.png
"""
import argparse
import importlib.util
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
from day import synthetic_day

_path = os.path.join(os.path.dirname(__file__), "algos", "biobloom_morning.py")
_spec = importlib.util.spec_from_file_location("biobloom_morning", _path)
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)

STYLES = ["rings", "rosette", "spores", "bud"]
SLEEPS = [4, 6, 8]                    # short / ok / long night


def render_cell(style, sleep_h, snaps, upto, scale):
    bloom = bm.BioBloom(bm.MOM_MODE, style, sleep_h)
    for t in range(upto + 1):
        bloom.advance(snaps[t])
    dc = device.Dc(device.COLOR_BLACK)
    device.perf_reset()
    bloom.render(dc, snaps[upto])
    nh, ns, nops = device.perf_read()
    work = (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
            + ns * device.VM_ISIN + nops * device.VM_OP)
    img = dc.masked().resize((device.W * scale, device.H * scale), Image.NEAREST)
    return img, dc.calls, work, bloom.state_bytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", default="7:30")
    ap.add_argument("--day", default="rest")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    h, m = args.at.split(":")
    upto = int(h) * 60 + int(m)
    snaps = synthetic_day(seed=args.seed, profile=args.day)

    cells = {}
    fw = fh = 0
    for style in STYLES:
        for s in SLEEPS:
            img, calls, work, sb = render_cell(style, s, snaps, upto, args.scale)
            cells[(style, s)] = (img, calls, work, sb)
            fw, fh = img.size

    pad, caph, lblw, hdrh = 6, 26, 70, 22
    cols, rows = len(SLEEPS), len(STYLES)
    grid_w = lblw + cols * fw + (cols + 1) * pad
    grid_h = hdrh + rows * (fh + caph) + (rows + 1) * pad
    strip = Image.new("RGB", (grid_w, grid_h), (24, 24, 24))
    draw = ImageDraw.Draw(strip)

    draw.text((pad, 6), "biobloom morning seed  @ {}  ({} day)".format(
        args.at, args.day), fill=(235, 235, 235))
    for ci, s in enumerate(SLEEPS):
        x = lblw + pad + ci * (fw + pad)
        draw.text((x + fw // 2 - 22, hdrh - 14), "{}h sleep".format(s),
                  fill=(200, 200, 200))

    for ri, style in enumerate(STYLES):
        y = hdrh + pad + ri * (fh + caph + pad)
        draw.text((pad, y + fh // 2 - 4), style, fill=(210, 210, 210))
        for ci, s in enumerate(SLEEPS):
            img, calls, work, sb = cells[(style, s)]
            x = lblw + pad + ci * (fw + pad)
            strip.paste(img, (x, y))
            wd = "OK" if work <= device.WATCHDOG else "OVER"
            draw.text((x, y + fh + 3),
                      "{}p ~{}VMi[{}] {}B".format(calls, work, wd, sb),
                      fill=(150, 150, 150))

    out = args.out or os.path.join(os.path.dirname(__file__), "out",
                                   "morning-{}.png".format(args.at.replace(":", "")))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    strip.save(out)
    print("grid {}x{} -> {}".format(rows, cols, out))


if __name__ == "__main__":
    main()
