#!/usr/bin/env python3
"""north_compare.py -- keep the two-worlds sun/north marker on the glass.

The shipped NorthComponent rides a constant r=101.7 circle about (107.5, 90),
but the fr735xt panel is semiround: the disc r=107.5 clipped to 215x180, so
the top and bottom are flat chords. Within ~28 deg of 6 o'clock (and of 12)
the marker centre leaves the glass. In the northern hemisphere north sits at
6 o'clock around solar noon (12 aimed at the sun, sun due south), so the marker
vanishes for 1.5-4 h a day exactly when the sun is easiest to sight; southern-
hemisphere users lose it at 12 o'clock instead.

Every candidate keeps the marker ON THE RAY at the true bearing -- only the
radius varies with angle -- so the direction it shows from the dial centre is
exact (a plain y-clamp would bend the bearing by up to ~2.5 deg).

The marker is a rotated 10 x 8.6 RECTANGLE (NorthComponent.quad: +/-5 radial,
+/-4.3 tangential), so off-axis its corners reach ~6.4 px from the centre; the
insets below are set from pixel sweeps, not the nominal 5 px.

  top (both)  slide along the top chord, centre y = 4.5: never touches the
              readout (y >= 11) or uplink (y >= 12); at worst the apex pixel
              is shaved by the glass edge.
  A "membrane bead"  bottom: the battery tab blocks the gutter, so the marker
              steps off the rim onto the tab's white outline (the notch floor
              y=171, the notch wall, the membrane edge), threaded on the wire.
              Lifted 1 px (membrane centre y=162) so no corner ever touches
              the battery chunks (y >= 169).
  B "inner shelf"    bottom: climbs over the notch wall and rests just INSIDE
              the field on the membrane (centre y=156), over the grove.

Separate finding (any track): the leading hour digit of a 24 h clock ("0"
before 10:00) is drawn after the marker and hides up to ~56% of it at
bearings ~292-314 (summer sunrise). Drawing the marker last fixes that; see
north-clock24.png.

Usage:
    python3 sketches/north_compare.py      # report + sketches/out/north-*.png

The tracks are written the way they port: track(rx, ry) -> r on the unit ray
(rx, ry) = (sin th, -cos th); every `a / b` is Float division.
"""

import importlib.util
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import solar
import twchrome
from day import synthetic_day
from twchrome import F, North, ChromeDc, ChromeState, track_circle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ------------------------------------------------------------------ tracks ---
# Distances are from the dial centre O = (107.5, 90).
R_RIM = 101.7              # the shipped gutter circle (white rim r=95.8, bezel 107.5)
TOP_DY = 85.5              # top chord: centre y = 4.5

# A: the battery tab outline from BorderComponent -- membrane edge y=163 over
# x 70..145, walls down to (57,172)/(158,172) -- lifted 1 px.
TAB_DY, TAB_DX = 72.0, 37.5        # membrane: centre y=162 for |dx| <= 37.5
FOOT_DY, FOOT_DX = 81.0, 50.5      # wall foot (158,171); floor y=171 out to the rim
WALL_S = 13.0 / 9.0                # wall slope, dx per dy
K_TAB = TAB_DX / TAB_DY            # |dx|/dy at the membrane corner (bearing 152.5)
K_FOOT = FOOT_DX / FOOT_DY         # ... at the wall foot (148.1)

# B: a shelf just inside the field, reached by a climb parallel to the wall
# from the point where the rim meets the floor y=171 (bearing 142.8).
SHELF_DY = 66.0                    # centre y=156: corners clear the line at y=163
RIM_DX = math.sqrt(R_RIM * R_RIM - FOOT_DY * FOOT_DY)
K_SHELF = (RIM_DX + WALL_S * (SHELF_DY - FOOT_DY)) / SHELF_DY


def track_top(ry, r):
    """Top chord (shared): flatten the rim to centre y = 4.5."""
    if -ry * r > TOP_DY:
        r = TOP_DY / -ry
    return r


def track_membrane(rx, ry):
    """A: rim circle; top chord; the battery tab's white outline."""
    r = F(R_RIM)
    if ry < 0.0:
        return track_top(ry, r)
    if ry * r > FOOT_DY:                       # rim dips below the floor y=171
        k = (rx if rx >= 0.0 else -rx) / ry    # |dx| / dy along the ray
        if k <= K_TAB:
            dy = F(TAB_DY)                                      # membrane edge
        elif k <= K_FOOT:
            dy = (WALL_S * TAB_DY - TAB_DX) / (WALL_S - k)      # notch wall
        else:
            dy = F(FOOT_DY)                                     # notch floor
        r = dy / ry
    return r


def track_shelf(rx, ry):
    """B: rim circle; top chord; a shelf just inside the membrane."""
    r = F(R_RIM)
    if ry < 0.0:
        return track_top(ry, r)
    if ry * r > FOOT_DY:
        k = (rx if rx >= 0.0 else -rx) / ry
        if k <= K_SHELF:
            dy = F(SHELF_DY)
        else:
            dy = (WALL_S * FOOT_DY - RIM_DX) / (WALL_S - k)     # climb
        r = dy / ry
    return r


TRACKS = [
    ("shipped (r=101.7)", track_circle),
    ("A: membrane bead", track_membrane),
    ("B: inner shelf", track_shelf),
]

# ------------------------------------------------------------ scenarios ------
PORTLAND = (45.52, -122.68)
SYDNEY = (-33.8688, 151.2093)
DATES = [  # (y, m, d), utc offset, dayOfWeek (1=Sun)
    ((2026, 6, 14), -25200, 1),
    ((2026, 3, 20), -25200, 6),
    ((2026, 10, 6), -25200, 3),
    ((2026, 12, 21), -28800, 2),
]
STRIP_TIMES = ["10:00", "12:00", "13:00", "14:00", "16:00"]


def hm(t):
    return "{:02d}:{:02d}".format(t // 60, t % 60)


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


# --------------------------------------------------- pixel-level analysis ----

def footprint(north, bearing):
    """(x, y) pixels the marker's outer quad rasterizes to, INCLUDING ones off
    the 215x180 frame (so clipping can be measured): the same integer vertices
    and PIL polygon fill as device.Dc.fillPolygon, translated."""
    cx, cy, rx, ry = north.centre(bearing)
    north.make_quad(cx, cy, rx, ry, -ry, rx, F(5.0), F(4.3))
    pts = [(int(x), int(y)) for x, y in north.quad]
    x0 = min(p[0] for p in pts) - 1
    y0 = min(p[1] for p in pts) - 1
    w = max(p[0] for p in pts) - x0 + 2
    h = max(p[1] for p in pts) - y0 + 2
    im = Image.new("1", (w, h), 0)
    ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in pts], fill=1)
    ys, xs = np.nonzero(np.array(im))
    return {(int(x) + x0, int(y) + y0) for x, y in zip(xs, ys)}


def ink(component, state):
    """Pixels one chrome component paints, rendered alone on a black Dc."""
    dc = ChromeDc()
    component.render(dc, state)
    ys, xs = np.nonzero(np.array(dc.img).any(axis=2))
    return {(int(x), int(y)) for x, y in zip(xs, ys)}


GLASS = {(x, y) for y in range(device.H) for x in range(device.W)
         if twchrome.visible(x, y)}


class Obstacles:
    """Chrome the marker can collide with. Drawn BEFORE it (it paints over
    them): border, uplink, battery. Drawn AFTER it in the shipped order (they
    hide it): readout, gps pip, clock -- the clock with the minute's glyphs."""

    def __init__(self):
        comps = twchrome.v2_chrome()
        self.border = ink(comps[1], ChromeState())
        self.uplink = ink(comps[2], ChromeState(phoneConnected=True))
        self.battery = ink(comps[3], ChromeState(batteryPct=100))
        self.readout = set()
        for dow in range(1, 8):
            for d in (8, 28):
                self.readout |= ink(comps[5], ChromeState(dayOfWeek=dow, day=d))
        self.gps = ink(comps[6], ChromeState(gpsFix=2))
        self._clock_c = comps[7]
        self._clock = {}
        self.clock_any = set()          # every glyph each digit cell can show
        for h in range(24):
            for is24 in (True, False):
                self.clock_any |= self.clock(h, 8, is24)
        for m in range(60):
            self.clock_any |= self.clock(23, m, True)

    def clock(self, hour, minute, is24):
        key = (hour, minute, is24)
        if key not in self._clock:
            self._clock[key] = ink(self._clock_c, ChromeState(
                hour=hour, minute=minute, is24Hour=is24))
        return self._clock[key]


def assess(fp, obs, clock_ink, marker_last=False):
    """-> (visible fraction, px off the glass, px hidden by later chrome,
    px painted over battery/uplink)."""
    n = len(fp)
    on = fp & GLASS
    hidden = set() if marker_last else on & (obs.readout | obs.gps | clock_ink)
    over = on & (obs.battery | obs.uplink)
    return (len(on) - len(hidden)) / n, n - len(on), len(hidden), len(over)


def ranges(bearings, vals, thresh):
    """Contiguous bearing runs where val >= thresh: 'a-b (max N px)'."""
    out, start, prev, peak = [], None, None, 0
    for b, v in zip(bearings, vals):
        if v >= thresh:
            if start is None:
                start, peak = b, 0
            peak = max(peak, v)
        elif start is not None:
            out.append("{:.1f}-{:.1f} ({} px)".format(start, prev, peak))
            start = None
        prev = b
    if start is not None:
        out.append("{:.1f}-{:.1f} ({} px)".format(start, prev, peak))
    return ", ".join(out) if out else "none"


def bearing_sweep(obs):
    print("== per-bearing sweep, 0.1 deg steps (marker footprint ~100 px)")
    bearings = [i / 10.0 for i in range(3600)]
    for name, track in TRACKS:
        north = North(track)
        clip, hid, over = [], [], []
        for b in bearings:
            _, c, h, v = assess(footprint(north, b), obs, obs.clock_any)
            clip.append(c)
            hid.append(h)
            over.append(v)
        print("  " + name)
        print("    off the glass, >= 3 px      : " + ranges(bearings, clip, 3))
        print("    (1-2 px edge shave elsewhere: {:.0f}% of bearings)".format(
            100.0 * sum(1 for c in clip if 0 < c < 3) / len(clip)))
        print("    hidden under readout/pip    : " + ranges(
            bearings, [h if (h and not (285 <= b <= 320)) else 0
                       for b, h in zip(bearings, hid)], 1))
        print("    hidden under clock digits   : " + ranges(
            bearings, [h if 285 <= b <= 320 else 0 for b, h in zip(bearings, hid)], 1)
            + "  <- 24 h leading digit")
        print("    paints over battery/uplink  : " + ranges(bearings, over, 1))


def day_coverage(obs):
    lat, lon = PORTLAND
    print("\n== per-day coverage, Portland {}, {} (sightable = elevation in (-0.833, 80))"
          .format(lat, lon))
    print("   'off' = marker centre off the glass (the issue's measure); '<90%' = under "
          "90% of the marker's pixels visible; 12 h clock")
    head = "   {:<10} {:>5}".format("date", "sight")
    for name, _ in TRACKS:
        head += " | {:<23}".format(name)
    print(head)
    print("   {:<10} {:>5}".format("", "") + " | off  <90%  worst       " * len(TRACKS))
    worst24 = {}
    for (y, m, d), off, _ in DATES:
        sight = []
        for t in range(1440):
            r = solar.compute(y, m, d, t // 60, t % 60, off, lat, lon)
            if solar.sightable(r[1]):
                sight.append((t, float(r[0])))
        row = "   {:04d}-{:02d}-{:02d} {:>5}".format(y, m, d, len(sight))
        for name, track in TRACKS:
            north = North(track)
            gone = low = 0
            worst = (2.0, None)
            low24 = [0, 0]
            for t, b in sight:
                cx, cy, _, _ = north.centre(b)
                if cy < 0.0 or cy > 180.0:
                    gone += 1
                fp = footprint(north, b)
                vis = assess(fp, obs, obs.clock(t // 60, t % 60, False))[0]
                if vis < 0.9:
                    low += 1
                if vis < worst[0]:
                    worst = (vis, t)
                for i, last in enumerate((False, True)):
                    if assess(fp, obs, obs.clock(t // 60, t % 60, True), last)[0] < 0.9:
                        low24[i] += 1
            worst24.setdefault(name, []).append(((y, m, d), low24))
            row += " | {:>3} {:>5}  {:>3.0f}% {}".format(
                gone, low, worst[0] * 100, hm(worst[1]))
        print(row)
    print("   24 h clock, minutes under 90% visible (marker under the clock -> "
          "marker drawn last):")
    for name, rows in worst24.items():
        print("     {:<20} ".format(name) + "  ".join(
            "{:02d}-{:02d}: {}->{}".format(dt[1], dt[2], a, b) for dt, (a, b) in rows))


# --------------------------------------------------------------- figures -----

def load_grove():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algos",
                        "moss_grove.py")
    spec = importlib.util.spec_from_file_location("algo_moss_grove", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()["components"][0]


def chrome_state(date, off, dow, t, where=PORTLAND, snap=None, is24=False):
    y, m, d = date
    return ChromeState(year=y, month=m, day=d, dayOfWeek=dow, hour=t // 60,
                       minute=t % 60, utcOffsetSec=off, lat=where[0], lon=where[1],
                       batteryPct=80, phoneConnected=True, is24Hour=is24, gpsFix=2,
                       steps=snap.steps if snap else None,
                       heartRate=snap.heartRate if snap else None)


def render_face(grove, snap, st, north, marker_last=False):
    dc = ChromeDc()
    if grove is not None:
        grove.render(dc, snap)
    comps = twchrome.v2_chrome(north)
    if marker_last:
        comps = [c for c in comps if c is not north] + [north]
    for c in comps:
        c.render(dc, st)
    return twchrome.glass(dc.img)


def text(draw, xy, s, fill=(230, 230, 230)):
    draw.text(xy, s, fill=fill)


def time_strip(title, date, off, dow, where, obs, tracks=TRACKS, times=STRIP_TIMES,
               scale=2):
    """Rows = tracks, columns = times, the real MossGrove behind the chrome."""
    samples = [mins(s) for s in times]
    groves = {name: load_grove() for name, _ in tracks}
    snaps = synthetic_day(seed=1, year=date[0], month=date[1], day=date[2])
    rows = {name: [] for name, _ in tracks}
    for t in range(1440):
        for g in groves.values():
            g.advance(snaps[t])
        if t not in samples:
            continue
        st = chrome_state(date, off, dow, t, where, snaps[t])
        res = solar.compute(*date, t // 60, t % 60, off, *where)
        for name, track in tracks:
            north = North(track)
            img = render_face(groves[name], snaps[t], st, north)
            if solar.sightable(res[1]):
                vis = assess(footprint(north, float(res[0])), obs,
                             obs.clock(t // 60, t % 60, False))[0]
                cap = "north {:5.1f}  sun el {:4.1f}  marker {:3.0f}% visible".format(
                    float(res[0]), float(res[1]), vis * 100)
            else:
                cap = "sun down -> marker hidden by design"
            rows[name].append((hm(t), img, cap))

    fw, fh = device.W * scale, device.H * scale
    pad, caph, lw = 8, 30, 130
    W = lw + len(samples) * (fw + pad) + pad
    H = 28 + len(tracks) * (fh + caph + pad) + pad
    out = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 8), title)
    for r, (name, _) in enumerate(tracks):
        y = 28 + r * (fh + caph + pad)
        text(draw, (pad, y + fh // 2 - 6), name, (255, 210, 120))
        for c, (lab, img, cap) in enumerate(rows[name]):
            x = lw + c * (fw + pad)
            out.paste(img.resize((fw, fh), Image.NEAREST), (x, y))
            text(draw, (x, y + fh + 3), lab)
            text(draw, (x, y + fh + 16), cap, (160, 160, 160))
    return out


def static_state():
    return ChromeState(year=2026, month=10, day=6, dayOfWeek=3, hour=12, minute=55,
                       batteryPct=80, phoneConnected=True, is24Hour=False, gpsFix=2)


def chrome_with_marker(north, bearing, st):
    dc = ChromeDc()
    for c in twchrome.v2_chrome(north):
        if c is north:
            if bearing is not None:
                north.draw(dc, bearing)
        else:
            c.render(dc, st)
    return dc


def track_maps(obs):
    """Top: each track's whole path -- the marker every 10 deg, its centre path
    in amber. Below: x4 zooms of the battery tab and the readout row at the
    bearings that matter."""
    st = static_state()
    maps = []
    for name, track in TRACKS:
        north = North(track)
        dc = chrome_with_marker(north, None, st)
        for i in range(0, 3600, 2):
            cx, cy, _, _ = north.centre(i / 10.0)
            x, y = int(cx + 0.5), int(cy + 0.5)
            if 0 <= x < device.W and 0 <= y < device.H:
                dc.img.putpixel((x, y), (255, 170, 0))
        for b in range(0, 360, 10):
            north.draw(dc, float(b))
        maps.append((name, twchrome.glass(dc.img)))

    zoom_b = [143.0, 148.0, 152.0, 160.0, 172.0, 180.0]
    zoom_t = [345.0, 0.0, 12.0, 24.0, 31.0]
    crop_b, crop_t, z = (40, 140, 176, 180), (40, 0, 176, 26), 3
    s3 = 3
    fw, fh = device.W * s3, device.H * s3
    bw, bh = (crop_b[2] - crop_b[0]) * z, (crop_b[3] - crop_b[1]) * z
    tw, th = (crop_t[2] - crop_t[0]) * z, (crop_t[3] - crop_t[1]) * z
    pad = 10
    W = max(3 * (fw + pad) + pad, len(zoom_b) * (bw + pad) + pad)
    H = (26 + fh + 22) + (22 + 3 * (bh + 18)) + (22 + 3 * (th + 18)) + pad
    out = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 7), "Each track's whole path: the marker every 10 deg of bearing, "
         "amber = where its centre rides on the glass. All keep the marker ON the "
         "bearing ray, so the direction it shows is exact.")
    for i, (name, img) in enumerate(maps):
        x = pad + i * (fw + pad)
        out.paste(img.resize((fw, fh), Image.NEAREST), (x, 26))
        text(draw, (x, 26 + fh + 4), name, (255, 210, 120))
    y = 26 + fh + 22

    def zrow(y, crop, bearings, w, h, title, post=None):
        text(draw, (pad, y + 4), title)
        y += 22
        for name, track in TRACKS:
            north = North(track)
            for j, b in enumerate(bearings):
                dc = chrome_with_marker(north, b, st)
                if post:
                    post(dc, north)
                g = twchrome.glass(dc.img).crop(crop).resize((w, h), Image.NEAREST)
                x = pad + j * (w + pad)
                out.paste(g, (x, y))
                vis = assess(footprint(north, b), obs, obs.clock_any)[0]
                text(draw, (x, y + h + 2), "{}  {:.0f} deg  {:.0f}% visible".format(
                    name.split(" ")[0].rstrip(":"), b, vis * 100), (170, 170, 170))
            y += h + 18
        return y

    def redraw_top(dc, north):          # readout/pip/clock draw after the marker
        for c in twchrome.v2_chrome(north)[5:]:
            c.render(dc, st)

    y = zrow(y, crop_b, zoom_b, bw, bh, "Battery tab (x3): bearings " + ", ".join(
        "{:.0f}".format(b) for b in zoom_b) + "  -- northern-hemisphere midday")
    zrow(y, crop_t, zoom_t, tw, th, "Readout row (x3): bearings " + ", ".join(
        "{:.0f}".format(b) for b in zoom_t) + "  -- southern-hemisphere midday / "
        "high-latitude summer", redraw_top)
    return out


def clock24_strip(obs, scale=3):
    """24 h clock, Portland Jun 14 sunrise: the leading '0' hides the marker
    (shipped draw order) vs the marker drawn last."""
    date, off, dow = (2026, 6, 14), -25200, 1
    times = ["05:25", "05:40", "06:00", "06:20"]
    crop = (0, 6, 120, 74)
    w, h = (crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale
    pad, lw = 8, 190
    out = Image.new("RGB", (lw + len(times) * (w + pad) + pad, 28 + 2 * (h + 32)),
                    (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 8), "24 h clock, Portland 2026-06-14 sunrise (x3 crop): the "
         "leading hour digit vs the marker -- same on every track")
    north = North(track_membrane)
    for r, (lab, last) in enumerate([("shipped order:\nclock over marker", False),
                                     ("marker drawn last", True)]):
        y = 28 + r * (h + 32)
        text(draw, (pad, y + h // 2 - 10), lab, (255, 210, 120))
        for c, s in enumerate(times):
            t = mins(s)
            st = chrome_state(date, off, dow, t, is24=True)
            img = render_face(None, None, st, north, marker_last=last)
            x = lw + c * (w + pad)
            out.paste(img.crop(crop).resize((w, h), Image.NEAREST), (x, y))
            res = solar.compute(*date, t // 60, t % 60, off, *PORTLAND)
            vis = assess(footprint(north, float(res[0])), obs,
                         obs.clock(t // 60, t % 60, True), last)[0]
            text(draw, (x, y + h + 3), "{}  north {:.0f}  {:.0f}% visible".format(
                s, float(res[0]), vis * 100), (170, 170, 170))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    obs = Obstacles()
    bearing_sweep(obs)
    day_coverage(obs)
    figs = []
    for date, off, dow in DATES:
        if date[1] in (10, 12):
            title = ("Portland {:04d}-{:02d}-{:02d} (UTC{:+d}), two-worlds V2: 12 o'clock "
                     "aimed at the sun, the red marker shows true north".format(
                         *date, off // 3600))
            figs.append(("north-compare-{:02d}{:02d}.png".format(date[1], date[2]),
                         time_strip(title, date, off, dow, PORTLAND, obs)))
    figs.append(("north-compare-sydney.png", time_strip(
        "Sydney 2026-06-21 (UTC+10), winter: the sun is due NORTH at noon, so the "
        "marker rides the TOP chord", (2026, 6, 21), 36000, 1, SYDNEY, obs,
        tracks=TRACKS[:2], times=["09:00", "11:00", "12:00", "13:00", "15:00"])))
    figs.append(("north-tracks.png", track_maps(obs)))
    figs.append(("north-clock24.png", clock24_strip(obs)))
    print()
    for fn, img in figs:
        p = os.path.join(OUT, fn)
        img.save(p)
        print("wrote " + os.path.relpath(p))


if __name__ == "__main__":
    main()
