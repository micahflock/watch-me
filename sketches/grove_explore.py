#!/usr/bin/env python3
"""Render the three moss_grove explorations as labelled grids:

  out/explore-tufts.png   tuft-colour modes (tips / tint / histo) over the day
  out/explore-sleep.png   sleep-seed modes (core / crown / dew), morning->day
  out/explore-shapes.png  one mode across several DATES -> day-to-day shape

    python3 sketches/grove_explore.py
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import grove_base
from day import synthetic_day

OUT = os.path.join(os.path.dirname(__file__), "out")
SCALE = 2


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def render(spec, snap):
    dc = device.Dc(spec.get("background", device.COLOR_BLACK))
    for c in spec["components"]:
        if hasattr(c, "render"):
            c.render(dc, snap)
    return dc.masked().resize((device.W * SCALE, device.H * SCALE), Image.NEAREST)


def capture(spec, snaps, sample_minutes):
    """Replay the day, returning {minute: image} for the requested minutes."""
    advancers = [c for c in spec["components"] if hasattr(c, "advance")]
    want = set(sample_minutes)
    out = {}
    for t in range(1440):
        for c in advancers:
            c.advance(snaps[t])
        if t in want:
            out[t] = render(spec, snaps[t])
    return out


def grid(path, rows, col_labels, title):
    """rows = [(row_label, [img, img, ...])]; col_labels aligns with the images."""
    fw, fh = rows[0][1][0].size
    padx, pady = 6, 6
    lblw, hdr, ttl = 92, 18, 22
    ncol = len(col_labels)
    W = lblw + ncol * (fw + padx) + padx
    H = ttl + hdr + len(rows) * (fh + pady) + pady
    img = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(img)
    d.text((padx, 6), title, fill=(240, 240, 120))
    for ci, cl in enumerate(col_labels):
        d.text((lblw + ci * (fw + padx), ttl + 4), cl, fill=(200, 200, 200))
    for ri, (rl, imgs) in enumerate(rows):
        y = ttl + hdr + ri * (fh + pady)
        d.text((padx, y + fh // 2), rl, fill=(170, 220, 170))
        for ci, im in enumerate(imgs):
            img.paste(im, (lblw + ci * (fw + padx), y))
    img.save(path)
    print("->", path)


def explore_tufts():
    times = ["9:30", "16:30", "23:30"]
    tm = [m for m in (mins(s) for s in times)]
    snaps = synthetic_day(profile="active")
    rows = []
    for mode in ["tips", "tint", "histo"]:
        caps = capture(grove_base.make(mode, "none"), snaps, tm)
        rows.append((mode, [caps[t] for t in tm]))
    grid(os.path.join(OUT, "explore-tufts.png"), rows, times,
         "tuft colour -> dominant zone (active day)")


def explore_sleep():
    times = ["6:00", "7:50", "13:05"]
    tm = [m for m in (mins(s) for s in times)]
    snaps = synthetic_day(profile="active")
    rows = []
    for mode in ["core", "crown", "dew"]:
        caps = capture(grove_base.make("tint", mode), snaps, tm)
        rows.append((mode, [caps[t] for t in tm]))
    grid(os.path.join(OUT, "explore-sleep.png"), rows, times,
         "sleep-seed modes (active day; ~6.5 h slept)")


def explore_shapes():
    at = mins("16:30")
    dates = [3, 9, 14, 21, 27, 30]
    imgs = []
    for dd in dates:
        snaps = synthetic_day(profile="active", day=dd)
        caps = capture(grove_base.make("tint", "none"), snaps, [at])
        imgs.append(caps[at])
    grid(os.path.join(OUT, "explore-shapes.png"),
         [("16:30", imgs)], ["d" + str(d) for d in dates],
         "day-to-day cushion shape (same activity, different date seed)")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    explore_tufts()
    explore_sleep()
    explore_shapes()
