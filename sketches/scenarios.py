#!/usr/bin/env python3
"""scenarios.py -- render named (day-profile x sleep) scenarios as day strips.

scrub.py hardcodes sleep_h=7; this lets the morning seed vary so we can see a
full day under a specific night's sleep. Each scenario is one row of sample
minutes across the day, captioned like scrub. No Garmin SDK.

    python3 sketches/scenarios.py            # the two default scenarios
"""
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

SAMPLES = ["6:30", "7:50", "13:05", "18:20", "21:45"]
SCALE = 2

# (label, day-profile, sleep_h)
SCENARIOS = [
    ("active day  -  good night (8h)", "active", 8),
    ("sedentary day  -  bad night (4h)", "rest", 4),
]


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def render_row(profile, sleep_h, sample_min):
    bloom = bm.BioBloom(bm.MOM_MODE, "spores", sleep_h)
    snaps = synthetic_day(profile=profile)
    want = set(sample_min)
    frames = []
    for t in range(1440):
        bloom.advance(snaps[t])
        if t in want:
            dc = device.Dc(device.COLOR_BLACK)
            device.perf_reset()
            bloom.render(dc, snaps[t])
            nh, ns, nops = device.perf_read()
            work = (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
                    + ns * device.VM_ISIN + nops * device.VM_OP)
            img = dc.masked().resize(
                (device.W * SCALE, device.H * SCALE), Image.NEAREST)
            frames.append(("{:02d}:{:02d}".format(t // 60, t % 60),
                           img, dc.calls, work, bloom.state_bytes()))
    return frames


def main():
    sample_min = [mins(s) for s in SAMPLES]
    rows = [(lbl, render_row(p, s, sample_min)) for lbl, p, s in SCENARIOS]

    fw, fh = rows[0][1][0][1].size
    pad, caph, hdr = 8, 30, 22
    ncol = len(SAMPLES)
    strip_w = ncol * fw + (ncol + 1) * pad
    strip_h = len(rows) * (hdr + fh + caph + pad) + pad
    strip = Image.new("RGB", (strip_w, strip_h), (24, 24, 24))
    draw = ImageDraw.Draw(strip)

    y = pad
    for label, frames in rows:
        draw.text((pad, y), label, fill=(240, 240, 240))
        y += hdr
        for i, (tlbl, img, calls, work, sb) in enumerate(frames):
            x = pad + i * (fw + pad)
            strip.paste(img, (x, y))
            wd = "OK" if work <= device.WATCHDOG else "OVER"
            draw.text((x, y + fh + 3),
                      "{}  ~{}VMi[{}]".format(tlbl, work, wd), fill=(220, 220, 220))
            draw.text((x, y + fh + 16), "{}p {}B".format(calls, sb),
                      fill=(150, 150, 150))
        y += fh + caph + pad

    out = os.path.join(os.path.dirname(__file__), "out", "scenarios.png")
    strip.save(out)
    print("{} scenarios -> {}".format(len(rows), out))


if __name__ == "__main__":
    main()
