#!/usr/bin/env python3
"""Generative-art concept sketches for the fr735xt watch face.

Renders three candidate "biometric algorithmic art" engines on a faithful
mock of the 735XT display (215x180, circle-with-flat-chords mask, the 14
Connect IQ palette colors, no antialiasing) so they can be judged visually
before any Monkey C is written.

Every concept obeys the porting constraints:
  - deterministic integer hash instead of Math.rand()
  - drawing decomposes to arcs / lines / circles / rects only
  - per-frame primitive counts printed (watchdog proxy, ~25-30k VM instr)
  - persistent state kept tiny and printed (RAM proxy)

Usage: python3 sketches/genart_sketches.py [outdir]
"""

import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 215, 180
CX, CY, R = 107.0, 90.0, 107.5     # bezel circle; top/bottom are flat chords
SCALE = 3                          # nearest-neighbor upscale for viewing

# The only 14 colors that exist on this device.
WHITE    = (0xFF, 0xFF, 0xFF)
LT_GRAY  = (0xAA, 0xAA, 0xAA)
DK_GRAY  = (0x55, 0x55, 0x55)
BLACK    = (0x00, 0x00, 0x00)
RED      = (0xFF, 0x00, 0x00)
DK_RED   = (0xAA, 0x00, 0x00)
ORANGE   = (0xFF, 0x55, 0x00)
YELLOW   = (0xFF, 0xAA, 0x00)      # amber on this device
GREEN    = (0x00, 0xFF, 0x00)
DK_GREEN = (0x00, 0xAA, 0x00)
BLUE     = (0x00, 0xAA, 0xFF)
DK_BLUE  = (0x00, 0x00, 0xFF)
PURPLE   = (0xAA, 0x00, 0xFF)
PINK     = (0xFF, 0x00, 0xFF)

# HR-zone -> color ramp used by all three concepts (rest..max)
ZONE_BOUNDS = [65, 90, 105, 125, 145, 160]
ZONE_COLORS = [DK_BLUE, BLUE, DK_GREEN, GREEN, YELLOW, ORANGE, RED]


def zone_color(hr):
    for i, b in enumerate(ZONE_BOUNDS):
        if hr < b:
            return ZONE_COLORS[i]
    return ZONE_COLORS[-1]


def ihash(*args):
    """Deterministic integer hash, trivially portable to Monkey C."""
    h = 0x811C9DC5
    for a in args:
        h ^= (a & 0xFFFFFFFF)
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= h >> 13
    return h


def hrand(n, *args):
    return ihash(*args) % n if n > 0 else 0


class Canvas:
    """dc stand-in that counts primitive calls."""

    def __init__(self):
        self.img = Image.new("RGB", (W, H), BLACK)
        self.d = ImageDraw.Draw(self.img)
        self.calls = 0

    def arc(self, bbox, a0, a1, color, width=1):
        self.d.arc(bbox, a0, a1, fill=color, width=width)
        self.calls += 1

    def line(self, x0, y0, x1, y1, color):
        self.d.line((x0, y0, x1, y1), fill=color)
        self.calls += 1

    def fill_circle(self, x, y, r, color):
        if r <= 0.6:
            self.d.point((x, y), fill=color)
        else:
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=color)
        self.calls += 1

    def fill_rect(self, x, y, w, h, color):
        self.d.rectangle((x, y, x + w - 1, y + h - 1), fill=color)
        self.calls += 1

    def masked(self):
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse((CX - R, CY - R, CX + R, CY + R), fill=255)
        out = Image.new("RGB", (W, H), BLACK)
        out.paste(self.img, (0, 0), mask)
        return out


# ---------------------------------------------------------------- day model

def simulate_day(seed):
    """Per-minute steps, heart rate, movement(0..1) for a plausible day."""
    steps, hr, mov = [], [], []
    for t in range(1440):
        h = t / 60.0
        if h < 6.5:                      s, r, m = 0, 52, 0.02   # sleep
        elif h < 7.0:                    s, r, m = 12, 68, 0.25  # waking
        elif h < 8.0:                    s, r, m = 158, 150, 0.9 # morning run
        elif h < 9.0:                    s, r, m = 18, 84, 0.3   # shower/commute
        elif h < 12.0:                   s, r, m = 3, 62, 0.08   # desk
        elif h < 12.75:                  s, r, m = 105, 96, 0.55 # lunch walk
        elif h < 17.5:                   s, r, m = 4, 64, 0.08   # desk
        elif h < 18.5:                   s, r, m = 45, 138, 0.8  # gym
        elif h < 22.0:                   s, r, m = 9, 74, 0.18   # evening
        else:                            s, r, m = 1, 58, 0.04   # wind-down
        j = hrand(1000, seed, t, 7)
        steps.append(max(0, s + (j % 21) - 10 if s else (1 if j < 30 else 0)))
        hr.append(r + (hrand(13, seed, t, 11)) - 6)
        mov.append(min(1.0, max(0.0, m + ((j % 9) - 4) / 40.0)))
    return steps, hr, mov


# ------------------------------------------------- concept 1: weathered truchet

def truchet_tile(cv, x, y, s, orient, color, width):
    h = s / 2.0
    if orient == 0:
        cv.arc((x - h, y - h, x + h, y + h), 0, 90, color, width)
        cv.arc((x + h, y + h, x + s + h, y + s + h), 180, 270, color, width)
    else:
        cv.arc((x + h, y - h, x + s + h, y + h), 90, 180, color, width)
        cv.arc((x - h, y + h, x + h, y + s + h), 270, 360, color, width)


def render_weathered_truchet(seed, t_now, steps, hr, mov):
    """Smith/Truchet arcs, weathered.

    Tiles unlock in shuffled order through the day; a tile's subdivision
    depth comes from how active its 48-min window was; each minute the
    'wind' (movement) flips tiles, recoloring them with the current HR
    zone; untouched tiles cool to grays.  A few tiles are corrupted into
    10 PRINT diagonals or voids.  State: 30 tiles x 4 small ints.
    """
    S = 36
    cols, rows = 6, 5
    n = cols * rows
    order = sorted(range(n), key=lambda i: ihash(seed, i, 991))
    # persistent per-coarse-tile state, simulated forward minute by minute
    flips = [0] * n     # flip generation (changes sub-orientations)
    color = [DK_GRAY] * n
    age = [9999] * n
    subdiv = [0] * n
    unlocked = []
    for t in range(t_now + 1):
        k = t // 48
        if k < n and (not unlocked or len(unlocked) == k):
            i = order[k]
            unlocked.append(i)
            w = sum(steps[max(0, t - 48):t + 1])
            subdiv[i] = 2 if w > 3000 else (1 if w > 700 else 0)
            color[i], age[i] = zone_color(hr[t]), 0
        nflips = 1 + int(mov[t] * 4)
        for f in range(nflips):
            if unlocked:
                i = unlocked[hrand(len(unlocked), seed, t, f, 17)]
                flips[i] += 1
                color[i], age[i] = zone_color(hr[t]), 0
        for i in unlocked:
            age[i] += 1

    cv = Canvas()
    for i in unlocked:
        c, r = i % cols, i // cols
        x0, y0 = c * S, r * S
        col = color[i] if age[i] < 25 else (LT_GRAY if age[i] < 110 else DK_GRAY)
        lvl = subdiv[i]
        sub = 2 ** lvl
        ss = S // sub
        for sy in range(sub):
            for sx in range(sub):
                hh = ihash(seed, i, sx, sy, flips[i])
                kind = hh % 100
                if kind < 4:
                    continue                          # void
                x, y = x0 + sx * ss, y0 + sy * ss
                if kind < 12:                         # 10 PRINT corruption
                    if hh & 1:
                        cv.line(x, y, x + ss, y + ss, col)
                    else:
                        cv.line(x + ss, y, x, y + ss, col)
                else:
                    truchet_tile(cv, x, y, ss, (hh >> 8) & 1,
                                 col, 3 - lvl)
    state = n * 4
    return cv, state


# ---------------------------------------------------- concept 2: murmuration

def render_murmuration(seed, t_now, steps, hr, mov):
    """tixy's dot grid, deformed.

    A 14x12 dot lattice; dots wake up as cumulative steps grow; a
    day-seeded Lissajous attractor wanders the screen and dots swell near
    it; sine-noise displacement (scaled by movement) bends the lattice out
    of true; dots that drift close grow connecting filaments.
    State: none — fully re-derived from (seed, minute, biometrics).
    """
    gx, gy = 14, 12
    spacing = 15
    x0 = (W - (gx - 1) * spacing) / 2.0
    y0 = (H - (gy - 1) * spacing) / 2.0
    cum = sum(steps[:t_now + 1])
    n = gx * gy
    awake_n = max(14, int(n * min(1.0, cum / 9000.0)))
    wake_rank = sorted(range(n), key=lambda i: ihash(seed, i, 313))
    awake = set(wake_rank[:awake_n])

    t = t_now
    r_hr = hr[t]
    recent = sum(mov[max(0, t - 45):t + 1]) / 46.0   # decaying unrest
    m = max(mov[t], 0.6 * recent)
    f1 = 2 + hrand(3, seed, 1)
    f2 = 3 + hrand(3, seed, 2)
    ax = CX + 62 * math.sin(t * 0.004 * f1 + hrand(7, seed, 3))
    ay = CY + 52 * math.sin(t * 0.0026 * f2 + hrand(7, seed, 4))
    amp = 2.0 + 9.0 * m
    hrn = max(0.0, min(1.0, (r_hr - 50) / 110.0))

    pos = {}
    for i in range(n):
        if i not in awake:
            continue
        ix, iy = i % gx, i // gx
        bx, by = x0 + ix * spacing, y0 + iy * spacing
        dx = amp * (math.sin(ix * 0.9 + t * 0.13) +
                    0.5 * math.sin(iy * 1.7 + t * 0.07))
        dy = amp * (math.sin(iy * 1.1 + t * 0.11 + 2) +
                    0.5 * math.sin(ix * 1.3 + t * 0.05))
        pos[i] = (bx + dx, by + dy)

    cv = Canvas()
    for i, (px, py) in pos.items():          # filaments first, dots on top
        for j in (i + 1, i + gx):
            if j in pos and (i + 1 != j or i % gx != gx - 1):
                qx, qy = pos[j]
                if (px - qx) ** 2 + (py - qy) ** 2 < 13 ** 2:
                    cv.line(px, py, qx, qy, DK_GRAY)
    for i, (px, py) in pos.items():
        d = math.hypot(px - ax, py - ay)
        pulse = hrn * 2.2 * math.sin(t * 0.35 + (i % gx) + (i // gx))
        grain = 0.5 + (hrand(100, seed, i, 47) / 100.0)  # intrinsic size
        rad = (max(0.0, 6.5 - d / 14.0) * (0.5 + hrn) + 0.9 + pulse) * grain
        rad = max(0.4, min(7.0, rad))
        if rad > 4.0:
            col = zone_color(r_hr)
        elif rad > 2.2:
            col = BLUE if hrn > 0.35 else DK_BLUE
        elif rad > 1.2:
            col = DK_BLUE
        else:
            col = DK_GRAY
        cv.fill_circle(px, py, rad, col)
    return cv, 0


# ------------------------------------------------------- concept 3: sediment

def render_sediment(seed, t_now, steps, hr, mov):
    """The day as strata.

    Every minute drops grains (more when stepping) into columns near a
    slowly drifting cursor; movement widens the scatter, stillness builds
    towers; columns topple onto shorter neighbors so dunes find a natural
    angle of repose.  Grain color is the HR zone of that minute, so sleep
    lays dark blue bedrock, a run deposits an orange-red seam.
    State: 54 columns of RLE color bands (~600 B worst case).
    """
    ncols = 54
    colw = 4
    heights = [0] * ncols
    bands = [[] for _ in range(ncols)]       # list of [color, px]
    wobble = 0
    for t in range(t_now + 1):
        wobble += (hrand(3, seed, t, 5) - 1)
        wobble = max(-6, min(6, wobble))
        # cursor sweeps left->right with the day; the screen reads as a
        # chronological core sample (morning strata left, evening right)
        c = 4 + (t * (ncols - 8)) // 1440 + wobble
        c = max(2, min(ncols - 3, c))
        g = 1 + min(7, steps[t] // 25)
        if steps[t] == 0 and mov[t] < 0.06 and t % 4:
            continue                         # sleep drips slowly
        spread = 2 + int(10 * mov[t])
        zc = zone_color(hr[t])
        for k in range(g):
            off = (hrand(spread, seed, t, k, 1) +
                   hrand(spread, seed, t, k, 2) - spread + 1)
            col = max(0, min(ncols - 1, c + off))
            for _ in range(8):               # topple to angle of repose
                lo = col
                if col > 0 and heights[col - 1] < heights[col] - 5:
                    lo = col - 1
                if col < ncols - 1 and heights[col + 1] < heights[lo] - 5:
                    lo = col + 1
                if lo == col:
                    break
                col = lo
            heights[col] += 1
            b = bands[col]
            if b and b[-1][0] == zc:
                b[-1][1] += 1
            else:
                b.append([zc, 1])

    cv = Canvas()
    for i in range(ncols):
        y = H
        for colr, px in bands[i]:
            y -= px
            cv.fill_rect(i * colw, y, colw, px, colr)
        if bands[i]:
            cv.fill_rect(i * colw, y - 1, colw, 1, DK_GRAY)  # crust line
    # white grain marks where "now" is depositing
    cv.fill_rect(c * colw + 1, H - heights[c] - 3, 2, 2, WHITE)
    state = sum(2 + 2 * len(b) for b in bands)
    return cv, state


# ------------------------------------------------------------------- output

CONCEPTS = [
    ("weathered-truchet", render_weathered_truchet),
    ("murmuration", render_murmuration),
    ("sediment", render_sediment),
]
SNAPSHOTS = [(7 * 60 + 50, "07:50 mid-run"),
             (13 * 60 + 5, "13:05 after lunch walk"),
             (21 * 60 + 45, "21:45 full day")]


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "sketches/out"
    os.makedirs(outdir, exist_ok=True)
    seed = 20260612
    steps, hr, mov = simulate_day(seed)
    font = ImageFont.load_default()
    for name, fn in CONCEPTS:
        panels = []
        for t, label in SNAPSHOTS:
            cv, state = fn(seed, t, steps, hr, mov)
            img = cv.masked().resize((W * SCALE, H * SCALE), Image.NEAREST)
            cum = sum(steps[:t + 1])
            cap = "%s | %d steps | HR %d | %d prims | state %dB" % (
                label, cum, hr[t], cv.calls, state)
            panel = Image.new("RGB", (W * SCALE, H * SCALE + 26), BLACK)
            panel.paste(img, (0, 0))
            pd = ImageDraw.Draw(panel)
            pd.text((8, H * SCALE + 6), cap, fill=LT_GRAY, font=font)
            panels.append(panel)
            print("%-20s %-22s prims=%4d  state=%4dB" %
                  (name, label, cv.calls, state))
        sheet = Image.new("RGB",
                          (sum(p.width for p in panels) + 20 * (len(panels) - 1),
                           panels[0].height), BLACK)
        x = 0
        for p in panels:
            sheet.paste(p, (x, 0))
            x += p.width + 20
        path = os.path.join(outdir, name + ".png")
        sheet.save(path)
        print("wrote", path)


if __name__ == "__main__":
    main()
