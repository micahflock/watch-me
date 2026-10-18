#!/usr/bin/env python3
"""sim_hero.py -- turn a Garmin simulator screenshot into the README hero.

    python3 sketches/sim_hero.py <root.png> [out.png]

<root.png> is a full-screen capture of the headless simulator (`xwd -root` on
its Xvfb display, then `convert root.xwd root.png`; CLAUDE.md "Simulator
gotchas"). This crops the watch out of the sim window, cuts off both straps,
and makes the white skin background transparent: a flood fill from the image
edges (so the face's own white pixels stay opaque) plus a soft alpha on the
anti-aliased case edge, so the watch sits cleanly on light or dark pages. The
result is upscaled 2x with nearest-neighbour so the face's pixels stay sharp.

The README hero (docs/img/hero-sim.png) was captured with a temporary probe
in TwoWorldsV2View.onLayout that loads the sandbox "hiit" day at 18:20 (the
same record readme_figs.py draws) into MossGrove via load(), and pins
gpsFix = 2 / phoneConnected = false in onUpdate. The probe is not committed.
"""
import sys
from collections import deque

from PIL import Image

# The fr735xt skin inside the SDK 9.2.0 sim window at its default size.
WATCH = (1, 26, 393, 612)      # sim canvas: x0, y0, x1, y1 on the root capture
KEEP_Y = (152, 452)            # watch head (lugs to lugs), canvas-relative rows
BG_LUM = 232                   # brighter than this and edge-connected = skin bg
CASE = (26, 26, 28)            # the case's near-black, for the edge blend


def lum(p):
    return (299 * p[0] + 587 * p[1] + 114 * p[2]) // 1000


def main(src, dst):
    img = Image.open(src).convert("RGB").crop(WATCH)
    img = img.crop((0, KEEP_Y[0], img.width, KEEP_Y[1]))
    w, h = img.size
    px = img.load()

    # Background: near-white pixels connected to the image border.
    bg = [[False] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        q.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        q.extend([(0, y), (w - 1, y)])
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or bg[y][x] or lum(px[x, y]) <= BG_LUM:
            continue
        bg[y][x] = True
        q.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    out = Image.new("RGBA", (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if bg[y][x]:
                op[x, y] = (0, 0, 0, 0)
                continue
            near = any(0 <= x + dx < w and 0 <= y + dy < h and bg[y + dy][x + dx]
                       for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2))
            if near:
                # an anti-aliased blend of the dark case over white: undo it
                a = (255 - lum((r, g, b))) * 255 // (255 - lum(CASE))
                op[x, y] = CASE + (max(0, min(255, a)),)
            else:
                op[x, y] = (r, g, b, 255)

    out.resize((w * 2, h * 2), Image.NEAREST).save(dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "docs/img/hero-sim.png")
