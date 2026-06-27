#!/usr/bin/env python3
"""ram_breakdown -- render the per-component RAM breakdown of the two-worlds face
as a horizontal bar chart (sketches/out/ram-breakdown.png).

The numbers are the measured usedMemory deltas printed by testLayerRamProfile in
faces/two-worlds/tests/TestTwoWorlds.mc (run: scripts/test.sh two-worlds). They are
the bytes each onLayout component adds, so the chart shows the UI's own allocation
footprint -- NOT the whole-app total (which in a debug build also carries the unit
-test suite + runtime). Re-run the test and update COMPONENTS if the dish caps or
the resources change."""
import os
from PIL import Image, ImageDraw, ImageFont

# (label, bytes, note) -- measured by testLayerRamProfile (debug sim, SDK 9.2.0)
COMPONENTS = [
    ("BioBloom dish (arrays @ caps)", 5976, "fixed; bloomGrown=0 over a full day"),
    ("Font bitmaps (time/date/dow/colon)", 4880, "decoded pixel data"),
    ("Field mask (188 merged rects)", 1080, "confines art to the disc"),
    ("Sun / north marker", 320, "_quad polygon"),
    ("Snapshot (device state)", 320, "~21 fields"),
    ("Compositor (render list)", 216, "10 component refs"),
    ("Breach warning", 160, ""),
    ("Uplink (phone bars)", 104, ""),
    ("Border", 96, ""),
    ("Battery", 96, ""),
]
LIMIT = 65536          # device watch-face RAM limit (64 KB)
CEILING = 58982        # project 90% working ceiling (~57.6 KB)

PALETTE = [
    (0x00, 0xAA, 0x00), (0xFF, 0xAA, 0x00), (0x00, 0xAA, 0xFF), (0xAA, 0x00, 0xFF),
    (0xFF, 0x55, 0x00), (0x00, 0xFF, 0x00), (0xFF, 0x00, 0xFF), (0x00, 0x00, 0xFF),
    (0xAA, 0xAA, 0xAA), (0xAA, 0x00, 0x00),
]

W, H = 940, 540
PAD_L, PAD_T = 360, 74
BARMAX = 360          # px for the largest bar
ROWH = 36

total = sum(b for _, b, _ in COMPONENTS)
maxb = max(b for _, b, _ in COMPONENTS)

img = Image.new("RGB", (W, H), (16, 16, 18))
d = ImageDraw.Draw(img)
try:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
except Exception:
    f = fb = fs = ImageFont.load_default()

d.text((24, 22), "two-worlds face -- RAM by UI component (measured)", font=fb, fill=(235, 235, 235))
d.text((24, 44), "onLayout allocation deltas (getSystemStats usedMemory). Total UI alloc = %d B (~%.1f KB)."
        % (total, total / 1024.0), font=fs, fill=(150, 150, 150))

for i, (label, b, note) in enumerate(COMPONENTS):
    y = PAD_T + i * ROWH
    col = PALETTE[i % len(PALETTE)]
    bw = int(BARMAX * b / maxb)
    d.text((PAD_L - 12, y + 1), label, font=f, fill=(225, 225, 225), anchor="ra")
    if note:
        d.text((PAD_L - 12, y + 17), note, font=fs, fill=(120, 120, 120), anchor="ra")
    d.rectangle([PAD_L, y, PAD_L + bw, y + ROWH - 12], fill=col)
    pct = 100.0 * b / total
    d.text((PAD_L + bw + 8, y + 3), "%d B  (%.1f%%)" % (b, pct), font=f, fill=(235, 235, 235))

# footer: UI alloc vs the 64 KB budget
fy = PAD_T + len(COMPONENTS) * ROWH + 24
d.text((24, fy), "UI allocations vs device budget", font=fb, fill=(225, 225, 225))
fy += 26
bar_w = W - 48
d.rectangle([24, fy, 24 + bar_w, fy + 26], outline=(90, 90, 90))
uiw = int(bar_w * total / LIMIT)
d.rectangle([24, fy, 24 + uiw, fy + 26], fill=(0, 140, 70))
cx = 24 + int(bar_w * CEILING / LIMIT)
d.line([cx, fy - 4, cx, fy + 30], fill=(255, 80, 80), width=2)
d.text((cx - 4, fy + 31), "57.6 KB ceiling", font=fs, fill=(255, 120, 120), anchor="ra")
d.text((28, fy + 6), "UI alloc ~%.1f KB  (%.0f%% of 64 KB)" % (total / 1024.0, 100.0 * total / LIMIT),
       font=f, fill=(255, 255, 255))
d.text((24 + bar_w - 4, fy + 31), "64 KB limit", font=fs, fill=(150, 150, 150), anchor="ra")

out = os.path.join(os.path.dirname(__file__), "out", "ram-breakdown.png")
img.save(out)
print("wrote", out, "total UI alloc bytes =", total)
