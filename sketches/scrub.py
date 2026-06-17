#!/usr/bin/env python3
"""scrub.py — render a generative-art algorithm across a simulated day.

    python3 sketches/scrub.py <algo> [--seed N] [--at 7:50,13:05,21:45]
                                     [--scale 2] [--out PATH]

Loads sketches/algos/<algo>.py, replays a synthetic biometric day MINUTE BY
MINUTE (advancing stateful components every minute, exactly as the watch's
once-per-minute onUpdate would), and renders the chosen sample minutes into a
single horizontal strip PNG. Each frame is captioned with the watchdog proxy
(primitive calls vs ~25k budget), the persistent-RAM proxy (state bytes), and
any off-palette color use. No Garmin SDK, no PRG build — iterate at save speed.

Default output: sketches/out/<algo>-scrub.png
"""

import argparse
import importlib.util
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
from day import synthetic_day

DEFAULT_SAMPLES = ["6:30", "7:50", "13:05", "18:20", "21:45", "23:30"]


def load_algo(name):
    path = os.path.join(os.path.dirname(__file__), "algos", name + ".py")
    if not os.path.exists(path):
        sys.exit("no such algo: {} (looked in sketches/algos/)".format(path))
    spec = importlib.util.spec_from_file_location("algo_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build"):
        sys.exit("algo {} must define build()".format(name))
    return mod


def parse_at(s):
    out = []
    for tok in s.split(","):
        h, m = tok.strip().split(":")
        out.append(int(h) * 60 + int(m))
    return out


def render_frame(spec, snap, scale):
    dc = device.Dc(spec.get("background", device.COLOR_BLACK))
    device.perf_reset()
    for c in spec["components"]:
        if hasattr(c, "render"):
            c.render(dc, snap)
    nh, ns, nops = device.perf_read()
    # Watchdog proxy = estimated VM INSTRUCTIONS, not raw primitive count
    # (hash16/isin are real function calls and usually dominate the frame; nops
    # is inner-loop/band-scan work, which dominates instead once a dish accretes
    # many bands -- see device.account()).
    work = (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
            + ns * device.VM_ISIN + nops * device.VM_OP)
    state_bytes = sum(c.state_bytes() for c in spec["components"]
                      if hasattr(c, "state_bytes"))
    img = dc.masked().resize((device.W * scale, device.H * scale), Image.NEAREST)
    return img, dc.calls, work, dc.offpalette, state_bytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("algo")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--day", default="active", help="biometric profile: active | rest")
    ap.add_argument("--at", default=",".join(DEFAULT_SAMPLES))
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    mod = load_algo(args.algo)
    spec = mod.build()
    samples = sorted(set(parse_at(args.at)))
    snaps = synthetic_day(seed=args.seed, profile=args.day)

    advancers = [c for c in spec["components"] if hasattr(c, "advance")]
    frames = []           # (label, img, calls, offpalette, state_bytes)
    sample_set = set(samples)
    for t in range(1440):
        snap = snaps[t]
        for c in advancers:
            c.advance(snap)
        if t in sample_set:
            img, calls, work, off, sb = render_frame(spec, snap, args.scale)
            frames.append(("{:02d}:{:02d}".format(t // 60, t % 60),
                           img, calls, work, off, sb))

    # Compose the strip: frames in a row, a caption bar beneath each.
    fw, fh = frames[0][1].size
    pad, caph = 8, 34
    strip_w = len(frames) * fw + (len(frames) + 1) * pad
    strip_h = fh + caph + 2 * pad
    strip = Image.new("RGB", (strip_w, strip_h), (24, 24, 24))
    draw = ImageDraw.Draw(strip)
    for i, (label, img, calls, work, off, sb) in enumerate(frames):
        x = pad + i * (fw + pad)
        strip.paste(img, (x, pad))
        wd = "OK" if work <= device.WATCHDOG else "OVER"
        l1 = "{}  ~{} VMi [{}]".format(label, work, wd)
        l2 = "{}p {}B".format(calls, sb) + ("  {} off-pal".format(off) if off else "")
        draw.text((x, pad + fh + 4), l1, fill=(230, 230, 230))
        draw.text((x, pad + fh + 18), l2, fill=(150, 150, 150))

    out = args.out or os.path.join(os.path.dirname(__file__), "out",
                                   args.algo + "-scrub.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    strip.save(out)
    peak = max(f[3] for f in frames)
    print("{} frames -> {}".format(len(frames), out))
    print("peak ~{} VM-instr/frame (watchdog ~{}), state {} B".format(
        peak, device.WATCHDOG, frames[-1][5]))


if __name__ == "__main__":
    main()
