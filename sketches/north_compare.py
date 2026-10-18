#!/usr/bin/env python3
"""north_compare.py -- keep the two-worlds sun/north marker on the glass.

Before (to 2026-10): NorthComponent rode a constant r=101.7 circle about
(107.5, 90), under the readout/date/clock. The fr735xt panel is semiround --
the disc r=107.5 clipped to 215x180, top and bottom flat chords -- so within
~28 deg of 6 (and 12) o'clock the marker centre left the glass. In the
northern hemisphere north sits at 6 o'clock around solar noon (12 aimed at the
sun, sun due south): in Portland the marker vanished 1.5-4 h a day, exactly
when the sun is easiest to sight. Southern-hemisphere users lost it at 12.

After (owner, 2026-10-06): the same rim cut flat at the panel's top and bottom
edges (twchrome.track_edge = NorthComponent.rimR), and the marker drawn LAST,
over the battery chunks and the date/clock it may cross ("it's OK if it
overlaps"). Drawing it last also fixes a 24 h clock's leading "0" hiding up to
~56% of it at summer sunrise (bearings ~292-314). Only the radius varies with
angle, never the angle, so the direction it shows from the dial centre stays
exact (a plain y-clamp would bend it by up to ~2.5 deg).

The marker is a rotated 10 x 8.6 RECTANGLE (NorthComponent.quad: +/-5 radial,
+/-4.3 tangential), so off-axis its corners reach ~6.4 px from the centre; the
edge insets (centre y 5.5 / 172.5) come from pixel sweeps, not the nominal 5.

The proposals this replaced -- A "membrane bead" (ride the battery tab's white
outline) and B "inner shelf" (rest inside the field) -- are in git history
(commit 1b8026e, same file).

Usage:
    python3 sketches/north_compare.py      # report + sketches/out/north-*.png
"""

import importlib.util
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import solar
import twchrome
from day import synthetic_day
from twchrome import F, North, ChromeDc, ChromeState, track_circle, track_edge

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# (label, track, marker drawn last?)
BEFORE = ("before: r=101.7 rim, under the clock", track_circle, False)
AFTER = ("after: rim cut at the screen edges, drawn last", track_edge, True)
VARIANTS = [BEFORE, AFTER]

PORTLAND = (45.5126, -122.6387)
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
    """Chrome the marker can meet: battery/uplink (drawn before it either way)
    and readout, gps pip, clock (drawn after it BEFORE the change -- hiding
    it -- and under it after)."""

    def __init__(self):
        c = twchrome.v2_chrome(north_last=False, dish=True)
        self.battery = ink(c[3], ChromeState(batteryPct=100))
        self.uplink = ink(c[2], ChromeState(phoneConnected=True))
        self.readout = set()
        for dow in range(1, 8):
            for d in (8, 28):
                self.readout |= ink(c[5], ChromeState(dayOfWeek=dow, day=d))
        self.gps = ink(c[6], ChromeState(gpsFix=2))
        self._clock_c = c[7]
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


def visible_fraction(fp, obs, clock_ink, last):
    """Share of the marker's pixels that are on the glass and not painted over
    by chrome drawn after it."""
    on = fp & GLASS
    if not last:
        on -= obs.readout | obs.gps | clock_ink
    return len(on) / len(fp)


def ranges(bearings, vals, thresh=1):
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
    for name, track, last in VARIANTS:
        north = North(track)
        off, hid, bat, txt = [], [], [], []
        for b in bearings:
            fp = footprint(north, b)
            on = fp & GLASS
            off.append(len(fp) - len(on))
            top = on & (obs.readout | obs.gps | obs.clock_any)
            hid.append(0 if last else len(top))
            txt.append(len(top) if last else 0)
            bat.append(len(on & (obs.battery | obs.uplink)))
        print("  " + name)
        print("    off the glass (>= 3 px)    : " + ranges(bearings, off, 3))
        print("    1-2 px edge graze          : {:.0f}% of bearings (the side rim)".format(
            100.0 * sum(1 for v in off if 0 < v < 3) / len(off)))
        if last:
            print("    over readout/pip/clock     : " + ranges(bearings, txt)
                  + "  (accepted)")
        else:
            print("    hidden under readout/clock : " + ranges(bearings, hid))
        print("    over battery/uplink        : " + ranges(bearings, bat)
              + ("  (accepted)" if last else ""))


def day_coverage(obs):
    lat, lon = PORTLAND
    print("\n== per-day coverage, Portland {}, {} (sightable = sun elevation in "
          "(-0.833, 80))".format(lat, lon))
    print("   off = marker centre off the glass (the issue's measure); <90% = under "
          "90% of its pixels visible (12 h / 24 h clock); worst = lowest visible share")
    head = "   {:<10} {:>5}".format("date", "sight")
    for name, _, _ in VARIANTS:
        head += " | {:<33}".format(name.split(":")[0])
    print(head)
    print("   {:<10} {:>5}".format("", "")
          + " | off  <90% 12h/24h  worst          " * len(VARIANTS))
    for (y, m, d), off, _ in DATES:
        sight = []
        for t in range(1440):
            r = solar.compute(y, m, d, t // 60, t % 60, off, lat, lon)
            if solar.sightable(r[1]):
                sight.append((t, float(r[0])))
        row = "   {:04d}-{:02d}-{:02d} {:>5}".format(y, m, d, len(sight))
        for name, track, last in VARIANTS:
            north = North(track)
            gone = low12 = low24 = 0
            worst = (2.0, 0)
            for t, b in sight:
                cx, cy, _, _ = north.centre(b)
                if cy < 0.0 or cy > 180.0:
                    gone += 1
                fp = footprint(north, b)
                v12 = visible_fraction(fp, obs, obs.clock(t // 60, t % 60, False), last)
                v24 = visible_fraction(fp, obs, obs.clock(t // 60, t % 60, True), last)
                low12 += v12 < 0.9
                low24 += v24 < 0.9
                if min(v12, v24) < worst[0]:
                    worst = (min(v12, v24), t)
            row += " | {:>3} {:>5}/{:<5}  {:>3.0f}% @{}   ".format(
                gone, low12, low24, worst[0] * 100, hm(worst[1]))
        print(row)


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


def render_face(grove, snap, st, north, last):
    dc = ChromeDc()
    if grove is not None:
        grove.render(dc, snap)
    for c in twchrome.v2_chrome(north, north_last=last):
        c.render(dc, st)
    return twchrome.glass(dc.img)


def text(draw, xy, s, fill=(230, 230, 230)):
    draw.text(xy, s, fill=fill)


def time_strip(title, date, off, dow, where, obs, times=STRIP_TIMES, scale=2):
    """Rows = before/after, columns = times, the real MossGrove behind."""
    samples = [mins(s) for s in times]
    grove = load_grove()
    snaps = synthetic_day(seed=1, year=date[0], month=date[1], day=date[2])
    rows = {v[0]: [] for v in VARIANTS}
    for t in range(1440):
        grove.advance(snaps[t])
        if t not in samples:
            continue
        st = chrome_state(date, off, dow, t, where, snaps[t])
        res = solar.compute(*date, t // 60, t % 60, off, *where)
        for name, track, last in VARIANTS:
            north = North(track)
            img = render_face(grove, snaps[t], st, north, last)
            if solar.sightable(res[1]):
                vis = visible_fraction(footprint(north, float(res[0])), obs,
                                       obs.clock(t // 60, t % 60, False), last)
                cap = "north {:5.1f}  sun el {:4.1f}  marker {:3.0f}% visible".format(
                    float(res[0]), float(res[1]), vis * 100)
            else:
                cap = "sun down -> marker hidden by design"
            rows[name].append((hm(t), img, cap))

    fw, fh = device.W * scale, device.H * scale
    pad, caph, lw = 8, 30, 150
    W = lw + len(samples) * (fw + pad) + pad
    H = 28 + len(VARIANTS) * (fh + caph + pad) + pad
    out = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 8), title)
    for r, (name, _, _) in enumerate(VARIANTS):
        y = 28 + r * (fh + caph + pad)
        text(draw, (pad, y + fh // 2 - 12), name.replace(": ", ":\n").replace(", ", ",\n"),
             (255, 210, 120))
        for c, (lab, img, cap) in enumerate(rows[name]):
            x = lw + c * (fw + pad)
            out.paste(img.resize((fw, fh), Image.NEAREST), (x, y))
            text(draw, (x, y + fh + 3), lab)
            text(draw, (x, y + fh + 16), cap, (160, 160, 160))
    return out


def static_state():
    return ChromeState(year=2026, month=10, day=6, dayOfWeek=3, hour=12, minute=55,
                       batteryPct=80, phoneConnected=True, is24Hour=False, gpsFix=2)


def chrome_with_markers(north, bearings, st, last):
    """The chrome with the marker drawn at each bearing, in the variant's order."""
    dc = ChromeDc()
    for c in twchrome.v2_chrome(north, north_last=last):
        if c is north:
            for b in bearings:
                north.draw(dc, b)
        else:
            c.render(dc, st)
    return dc


def track_maps(obs):
    """Top: each variant's whole path -- the marker every 10 deg, its centre
    path in amber. Below: x3 zooms of the bottom and top edges."""
    st = static_state()
    s3 = 3
    fw, fh = device.W * s3, device.H * s3
    zoom_b = [144.0, 152.0, 160.0, 170.0, 180.0]
    zoom_t = [345.0, 0.0, 12.0, 24.0, 33.0]
    crop_b, crop_t, z = (40, 138, 176, 180), (40, 0, 176, 26), 3
    bw, bh = (crop_b[2] - crop_b[0]) * z, (crop_b[3] - crop_b[1]) * z
    tw, th = (crop_t[2] - crop_t[0]) * z, (crop_t[3] - crop_t[1]) * z
    pad = 10
    W = max(2 * (fw + pad) + pad, len(zoom_b) * (bw + pad) + pad)
    H = (26 + fh + 22) + 2 * (22 + 2 * (max(bh, th) + 18)) + pad
    out = Image.new("RGB", (W, H), (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 7), "Whole path: the marker every 10 deg of bearing, amber = where "
         "its centre rides on the glass. Only the radius changes, so the direction "
         "from the dial centre stays exact.")
    for i, (name, track, last) in enumerate(VARIANTS):
        north = North(track)
        dc = chrome_with_markers(north, [float(b) for b in range(0, 360, 10)], st, last)
        if not last:   # under the clock: redraw the chrome over the markers
            for c in twchrome.v2_chrome(north, north_last=False, dish=True)[5:]:
                c.render(dc, st)
        for k in range(0, 3600, 2):
            cx, cy, _, _ = north.centre(k / 10.0)
            x, y = int(cx + 0.5), int(cy + 0.5)
            if 0 <= x < device.W and 0 <= y < device.H:
                dc.img.putpixel((x, y), (255, 170, 0))
        x = pad + i * (fw + pad)
        out.paste(twchrome.glass(dc.img).resize((fw, fh), Image.NEAREST), (x, 26))
        text(draw, (x, 26 + fh + 4), name, (255, 210, 120))
    y = 26 + fh + 22

    for title, crop, bearings, w, h in (
            ("Bottom edge (x3): bearings ", crop_b, zoom_b, bw, bh),
            ("Top edge (x3): bearings ", crop_t, zoom_t, tw, th)):
        text(draw, (pad, y + 4), title + ", ".join("{:.0f}".format(b) for b in bearings))
        y += 22
        for name, track, last in VARIANTS:
            north = North(track)
            for j, b in enumerate(bearings):
                dc = chrome_with_markers(north, [b], st, last)
                g = twchrome.glass(dc.img).crop(crop).resize((w, h), Image.NEAREST)
                xx = pad + j * (w + pad)
                out.paste(g, (xx, y))
                vis = visible_fraction(footprint(north, b), obs, obs.clock_any, last)
                text(draw, (xx, y + h + 2), "{}  {:.0f} deg  {:.0f}% visible".format(
                    name.split(":")[0], b, vis * 100), (170, 170, 170))
            y += h + 18
    return out


def clock24_strip(obs, scale=3):
    """24 h clock, Portland Jun 14 sunrise: the leading '0' over the marker
    (before) vs the marker drawn last (after)."""
    date, off, dow = (2026, 6, 14), -25200, 1
    times = ["05:25", "05:40", "06:00", "06:20"]
    crop = (0, 6, 120, 74)
    w, h = (crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale
    pad, lw = 8, 190
    out = Image.new("RGB", (lw + len(times) * (w + pad) + pad, 28 + 2 * (h + 32)),
                    (24, 24, 24))
    draw = ImageDraw.Draw(out)
    text(draw, (pad, 8), "24 h clock, Portland 2026-06-14 sunrise (x3 crop): the "
         "leading hour digit vs the marker")
    for r, (name, track, last) in enumerate(VARIANTS):
        north = North(track)
        y = 28 + r * (h + 32)
        text(draw, (pad, y + h // 2 - 10), name.replace(", ", ",\n"), (255, 210, 120))
        for c, s in enumerate(times):
            t = mins(s)
            st = chrome_state(date, off, dow, t, is24=True)
            img = render_face(None, None, st, north, last)
            x = lw + c * (w + pad)
            out.paste(img.crop(crop).resize((w, h), Image.NEAREST), (x, y))
            res = solar.compute(*date, t // 60, t % 60, off, *PORTLAND)
            vis = visible_fraction(footprint(north, float(res[0])), obs,
                                   obs.clock(t // 60, t % 60, True), last)
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
        "marker rides the TOP edge", (2026, 6, 21), 36000, 1, SYDNEY, obs,
        times=["09:00", "11:00", "12:00", "13:00", "15:00"])))
    figs.append(("north-tracks.png", track_maps(obs)))
    figs.append(("north-clock24.png", clock24_strip(obs)))
    print()
    for fn, img in figs:
        p = os.path.join(OUT, fn)
        img.save(p)
        print("wrote " + os.path.relpath(p))


if __name__ == "__main__":
    main()
