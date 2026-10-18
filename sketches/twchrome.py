#!/usr/bin/env python3
"""twchrome.py -- the two-worlds V2 chrome, transcribed for the sandbox.

A line-for-line port of the overlay components in
faces/two-worlds-v2/source/TwoWorldsV2View.mc (shared verbatim with the V1
face, plus V2's GPS pip) onto the faithful device model, so chrome tweaks
(e.g. the sun/north marker track) iterate here instead of in a PRG:

    FieldMask  static black runs outside the field disc (same merged-rect build)
    Border     the white separation line (chord, slant, rim arcs, battery notch)
    PhoneRing  blue glass-edge ring      Uplink   GPS fix bars
    Battery    three 33% chunks
    Readout    day-of-week + date strips Gps      retired fix-recency dish
    Clock      7-seg HH:MM strips
    North      the hollow red marker on the rim at the sun-compass angle

Float math runs in float32 like the watch (solar.F; NEP 50 keeps a Python
float literal "weak", i.e. a Monkey C Float literal). The glyph strips are the
real resources (faces/two-worlds/resources/drawables), blitted through a clip
exactly like core StripGlyphs.

North takes a `track(rx, ry) -> r` callable: the rim radius along the unit ray
(rx, ry) = (sin th, -cos th). The face ships track_edge -- the r=101.7 gutter
circle cut flat at the panel's top and bottom edges -- and draws the marker
LAST, over the clock/date/battery (owner, 2026-10). track_circle is the
pre-2026-10 constant rim; sketches/north_compare.py compares the two.
"""

import math
import os

from PIL import Image

import device
import solar
from device import (COLOR_BLACK, COLOR_WHITE, COLOR_RED, COLOR_ORANGE,
                    COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_BLUE, COLOR_YELLOW,
                    COLOR_TRANSPARENT)

F = solar.F
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWABLES = os.path.join(REPO, "faces", "two-worlds", "resources", "drawables")


# ------------------------------------------------------ the extra primitives --

class ChromeDc(device.Dc):
    """device.Dc plus the three real Gfx calls the chrome needs:
    drawCircle (GPS pip ring), drawBitmap and setClip/clearClip (StripGlyphs
    blits one strip cell through a clip). The clip applies to drawBitmap
    only -- the chrome never sets one around any other primitive."""

    def __init__(self, bg=COLOR_BLACK):
        super().__init__(bg)
        self._clip = None

    def drawCircle(self, x, y, r):
        self.calls += 1
        x, y, r = int(x), int(y), int(r)
        self._d.ellipse((x - r, y - r, x + r, y + r), outline=device._rgb(self._fg))

    def setClip(self, x, y, w, h):
        self._clip = (int(x), int(y), int(x) + int(w), int(y) + int(h))

    def clearClip(self):
        self._clip = None

    def drawBitmap(self, x, y, bmp):
        self.calls += 1
        x0, y0 = int(x), int(y)
        w, h = bmp.size
        cx0, cy0, cx1, cy1 = self._clip or (0, 0, device.W, device.H)
        ax0, ay0 = max(x0, cx0, 0), max(y0, cy0, 0)
        ax1, ay1 = min(x0 + w, cx1, device.W), min(y0 + h, cy1, device.H)
        if ax1 <= ax0 or ay1 <= ay0:
            return
        crop = bmp.crop((ax0 - x0, ay0 - y0, ax1 - x0, ay1 - y0))
        self.img.paste(crop.convert("RGB"), (ax0, ay0), crop.split()[3])


class StripGlyphs:
    """core/src/glyph/StripGlyphs.mc: one cell of a horizontal glyph strip."""

    def __init__(self, png, cell_w):
        self.bmp = Image.open(os.path.join(DRAWABLES, png)).convert("RGBA")
        self.cell_w = cell_w
        self.cell_h = self.bmp.size[1]
        self.count = self.bmp.size[0] // cell_w

    def draw(self, dc, index, x, y):
        if index < 0 or index >= self.count:
            return
        dc.setClip(x, y, self.cell_w, self.cell_h)
        dc.drawBitmap(x - index * self.cell_w, y, self.bmp)
        dc.clearClip()


def rnd(v):
    return int(v + 0.5)              # (v + 0.5).toNumber()


# ----------------------------------------------------------------- state ------

class ChromeState:
    """The Snapshot fields the chrome reads (core/src/data/Snapshot.mc)."""

    def __init__(self, **kw):
        self.year = self.month = self.day = self.dayOfWeek = None
        self.hour = self.minute = None
        self.utcOffsetSec = None
        self.lat = self.lon = None
        self.batteryPct = None
        self.phoneConnected = None
        self.is24Hour = None
        self.gpsFix = None
        self.steps = self.heartRate = None
        self.second = 0
        for k, v in kw.items():
            setattr(self, k, v)


def battery_level(pct):
    """Face.batteryLevel."""
    if pct is None:
        return 0
    lit = 0
    for k in range(1, 4):
        if pct > (k - 1) * 33.33:
            lit = k
    return lit


def display_hour(hour24, is24):
    """Face.displayHour."""
    if is24 is not False:
        return hour24
    h = hour24 % 12
    return 12 if h == 0 else h


# ------------------------------------------------------------ components -----

class FieldMask:
    """FieldMaskComponent: the static black runs outside the field, built once
    and vertically merged into packed (x<<24 | w<<16 | y<<8 | h) rects."""

    def __init__(self):
        self.runs = []
        openA, openB = [0] * 8, [0] * 8
        open_, n_open = openA, 0
        cx, cw, used = [0] * 4, [0] * 4, [False] * 4
        for y in range(180):
            n_cur = self.scanline(y, cx, cw)
            for c in range(n_cur):
                used[c] = False
            nxt = openB if open_ is openA else openA
            n_next = 0
            for o in range(n_open):
                r = open_[o]
                rx, rw = (r >> 24) & 0xFF, (r >> 16) & 0xFF
                hit = -1
                for c in range(n_cur):
                    if not used[c] and cx[c] == rx and cw[c] == rw:
                        hit = c
                        break
                if hit >= 0:
                    used[hit] = True
                    nxt[n_next] = r + 1
                    n_next += 1
                else:
                    self.runs.append(r)
            for c in range(n_cur):
                if not used[c]:
                    nxt[n_next] = (cx[c] << 24) | (cw[c] << 16) | (y << 8) | 1
                    n_next += 1
            open_, n_open = nxt, n_next
        for o in range(n_open):
            self.runs.append(open_[o])

    def scanline(self, y, cx, cw):
        dy = y - F(90.7)
        disc = 9177.64 - dy * dy
        if disc <= 0.0:
            cx[0], cw[0] = 0, 215
            return 1
        hw = F(math.sqrt(disc))
        xl = 107.5 - hw
        xr = 107.5 + hw
        if y < 62:
            if y < 15:
                xcut = F(166.0)
            else:
                xcut = 134.0 + F(32.0) * (62 - y) / 47.0
                if xcut > 166.0:
                    xcut = F(166.0)
            if xl < xcut:
                xl = xcut
            if xl >= xr:
                cx[0], cw[0] = 0, 215
                return 1
        if y >= 163:
            t = (y - F(163.0)) / 9.0
            lw = 70.0 - 13.0 * t
            rw = 145.0 + 13.0 * t
            n, cur = 0, F(0.0)
            n = self.run(cx, cw, n, cur, xl)
            cur = xl
            if lw > cur:
                cur = lw
            if rw > cur:
                n = self.run(cx, cw, n, cur, rw)
                cur = rw
            if xr > cur:
                cur = xr
            if cur < 215.0:
                n = self.run(cx, cw, n, cur, F(215.0))
            return n
        n = 0
        n = self.run(cx, cw, n, F(0.0), xl)
        n = self.run(cx, cw, n, xr, F(215.0))
        return n

    @staticmethod
    def run(cx, cw, n, x0, x1):
        a, b = rnd(x0), rnd(x1)
        a = max(a, 0)
        b = min(b, 215)
        if b > a:
            cx[n], cw[n] = a, b - a
            return n + 1
        return n

    def render(self, dc, state):
        dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
        for v in self.runs:
            dc.fillRectangle((v >> 24) & 0xFF, (v >> 8) & 0xFF,
                             (v >> 16) & 0xFF, v & 0xFF)


class Border:
    """BorderComponent: chord + slant, rim arcs (r=95.8 about (107.5,90.7))
    broken at the slant and the battery notch, and the notch walls -- then
    the anti-aliasing pixels (2026-10; generated table, see
    sketches/border_aa_compare.py). aa=False draws the bare white line.
    The watch's drawLine puts 5 diagonal steps one pixel over and skips one
    endpoint (border_aa_compare.DEVICE_ONLY / SANDBOX_ONLY); the table is
    built against the device's pixels, so this mirror differs from the
    watch at those 6 spots only."""

    def __init__(self, aa=True):
        self.aa = aa

    def render(self, dc, state):
        self.white(dc)
        if self.aa:
            import border_aa_pixels as px
            for col, pts in ((COLOR_DK_GRAY, px.DK), (COLOR_LT_GRAY, px.LT)):
                dc.setColor(col, COLOR_TRANSPARENT)
                for x, y in pts:
                    dc.fillRectangle(x, y, 1, 1)      # = Dc.drawPoint

    def white(self, dc):
        dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
        dc.drawLine(16, 62, 134, 62)
        dc.drawLine(134, 62, 166, 15)
        self.arc(dc, F(107.5), F(90.7), F(95.8), F(37.7), F(148.0))
        self.arc(dc, F(107.5), F(90.7), F(95.8), F(212.0), F(287.4))
        dc.drawLine(70, 163, 145, 163)
        dc.drawLine(70, 163, 57, 172)
        dc.drawLine(145, 163, 158, 172)

    @staticmethod
    def arc(dc, cx, cy, r, a0, a1):
        pi = F(math.pi)
        n = max(int((a1 - a0) / 4.0), 1)
        px = rnd(cx + r * F(math.sin(a0 * pi / 180.0)))
        py = rnd(cy - r * F(math.cos(a0 * pi / 180.0)))
        for i in range(1, n + 1):
            a = a0 + (a1 - a0) * i / n
            rad = a * pi / 180.0
            x = rnd(cx + r * F(math.sin(rad)))
            y = rnd(cy - r * F(math.cos(rad)))
            dc.drawLine(px, py, x, y)
            px, py = x, y


class Uplink:
    """UplinkComponent. V2 (owner, 2026-10) colours the bars by GPS fix
    recency -- BLUE fresh / YELLOW (amber) stale / DK_GRAY none; gps=False
    is the phone-link colouring V1 (and pre-2026-10 V2) ships."""

    def __init__(self, gps=True):
        self.gps = gps

    def render(self, dc, state):
        if self.gps:
            g = state.gpsFix
            c = COLOR_BLUE if g == 2 else COLOR_YELLOW if g == 1 else COLOR_DK_GRAY
        else:
            c = COLOR_BLUE if state.phoneConnected is True else COLOR_DK_GRAY
        dc.setColor(c, COLOR_TRANSPARENT)
        for i in range(5):
            w = F(29.0) + (4.0 - 29.0) * i / 4.0
            dc.fillRectangle(128, 12 + i * 9, rnd(w), 4)


class PhoneRing:
    """PhoneRingComponent (2026-10): a 2 px BLUE ring round the glass edge
    while the phone is connected (sketches/phone_ring_compare.py A)."""

    def render(self, dc, state):
        if state.phoneConnected is not True:
            return
        dc.setColor(COLOR_BLUE, COLOR_TRANSPARENT)
        for cy in (89, 90):
            dc.drawCircle(107, cy, 107)
            dc.drawCircle(107, cy, 106)
        dc.fillRectangle(46, 0, 123, 2)
        dc.fillRectangle(46, 178, 123, 2)


class Battery:
    def render(self, dc, state):
        level = battery_level(state.batteryPct)
        for i in range(3):
            dc.setColor(COLOR_ORANGE if i < level else COLOR_DK_GRAY, COLOR_TRANSPARENT)
            dc.fillRectangle(74 + i * 25, 169, 18, 8)


TRACK_R = 101.7
TOP_DY = 84.5      # top edge: marker centre y = 90 - 84.5 = 5.5
BOT_DY = 82.5      # bottom edge: marker centre y = 90 + 82.5 = 172.5


def track_circle(rx, ry):
    """Pre-2026-10 track: a constant 101.7 px rim about (107.5, 90). Within
    ~28 deg of 12 and 6 o'clock its centre leaves the 180-row panel."""
    return F(TRACK_R)


def track_edge(rx, ry):
    """NorthComponent.rimR: the r=101.7 rim cut flat at the panel's top and
    bottom edges. Only the radius changes, never the angle, so the marker stays
    on the bearing ray; centre y in [5.5, 172.5] keeps every pixel of it on
    the glass at every bearing (north_compare.py sweeps them)."""
    r = F(TRACK_R)
    if -ry * r > TOP_DY:
        r = TOP_DY / -ry
    elif ry * r > BOT_DY:
        r = BOT_DY / ry
    return r


class North:
    """NorthComponent with a pluggable track. render() is the shipped gate
    (SunCompass, sightable elevation); draw() the shipped quad geometry, with
    the centre (107.5, 90) + track(rx, ry) * (rx, ry)."""

    def __init__(self, track=track_edge):
        self.track = track
        self.quad = [[0, 0], [0, 0], [0, 0], [0, 0]]

    def render(self, dc, state):
        res = solar.compute(state.year, state.month, state.day, state.hour,
                            state.minute, state.utcOffsetSec, state.lat, state.lon)
        if res is None:
            return
        elev = res[1]
        if elev <= -0.833 or elev >= 80.0:
            return
        self.draw(dc, res[0])

    def centre(self, bearing):
        th = F(bearing) * F(math.pi) / 180.0
        rx = F(math.sin(th))
        ry = -F(math.cos(th))
        r = self.track(rx, ry)
        return 107.5 + r * rx, 90.0 + r * ry, rx, ry

    def draw(self, dc, bearing):
        cx, cy, rx, ry = self.centre(bearing)
        tx, ty = -ry, rx               # (cos th, sin th)
        dc.setColor(COLOR_RED, COLOR_TRANSPARENT)
        self.make_quad(cx, cy, rx, ry, tx, ty, F(5.0), F(4.3))
        dc.fillPolygon(self.quad)
        dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
        self.make_quad(cx, cy, rx, ry, tx, ty, F(2.0), F(1.72))
        dc.fillPolygon(self.quad)

    def make_quad(self, cx, cy, rx, ry, tx, ty, sR, sT):
        q = self.quad
        q[0][0] = rnd(cx + sR * rx + sT * tx)
        q[0][1] = rnd(cy + sR * ry + sT * ty)
        q[1][0] = rnd(cx + sR * rx - sT * tx)
        q[1][1] = rnd(cy + sR * ry - sT * ty)
        q[2][0] = rnd(cx - sR * rx - sT * tx)
        q[2][1] = rnd(cy - sR * ry - sT * ty)
        q[3][0] = rnd(cx - sR * rx + sT * tx)
        q[3][1] = rnd(cy - sR * ry + sT * ty)


class Readout:
    def __init__(self, dow, date):
        self.dow, self.date = dow, date

    def render(self, dc, state):
        y, left = 11, 82
        if state.dayOfWeek is not None and 1 <= state.dayOfWeek <= 7:
            self.dow.draw(dc, state.dayOfWeek - 1, left, y)
        if state.day is not None:
            d = state.day
            x = left + 18 + 4
            if d >= 10:
                self.date.draw(dc, (d // 10) % 10, x, y)
                x += 6 + 1
            self.date.draw(dc, d % 10, x, y)


class Gps:
    """The retired GpsComponent (pre-2026-10 V2; v2_chrome(dish=True)):
    the cross-section satellite dish, coloured
    by fix recency, waves none / 1 stale / 2 fresh. See
    sketches/gps_dish_compare.py big(67, 15) for the design rounds."""
    DISH = [(73, 9), (74, 11), (74, 13), (74, 16), (73, 18), (72, 20),
            (70, 21), (68, 22), (65, 22), (63, 22), (61, 21)]
    W1 = [(63, 5), (60, 6), (58, 8), (57, 11)]
    W2 = [(63, 2), (60, 2), (56, 4), (54, 8), (54, 11)]

    def render(self, dc, state):
        g = state.gpsFix
        c = COLOR_DK_GRAY
        if g == 2:
            c = COLOR_BLUE
        elif g == 1:
            c = COLOR_YELLOW
        dc.setColor(c, COLOR_TRANSPARENT)
        dc.fillPolygon(self.DISH)
        dc.drawLine(67, 15, 63, 11)
        dc.fillRectangle(62, 10, 2, 2)
        waves = (self.W1, self.W2) if g == 2 else (self.W1,) if g == 1 else ()
        for w in waves:
            for (x0, y0), (x1, y1) in zip(w, w[1:]):
                dc.drawLine(x0, y0, x1, y1)


class Clock:
    def __init__(self, digits, colon):
        self.digits, self.colon = digits, colon

    def render(self, dc, state):
        y = 26
        if state.hour is not None:
            h = display_hour(state.hour, state.is24Hour)
            tens = (h // 10) % 10
            if state.is24Hour is not False or tens != 0:
                self.digits.draw(dc, tens, 20, y)
            self.digits.draw(dc, h % 10, 43, y)
        dc.drawBitmap(66, y, self.colon)
        if state.minute is not None:
            self.digits.draw(dc, (state.minute // 10) % 10, 75, y)
            self.digits.draw(dc, state.minute % 10, 98, y)


class Breach:
    """BreachComponent (2026-10 easter egg): the CONTAINMENT BREACH tape when
    the day's movement outgrows the dish (state.breach, set by the caller
    from the grove's act_units >= breach_compare.BREACH_ACT). The face draws
    exactly breach_compare.Banner("B", 12); this delegates to it."""

    def __init__(self):
        self._banner = None

    def render(self, dc, state):
        if getattr(state, "breach", None) is not True:
            return
        if self._banner is None:
            import breach_compare
            self._banner = breach_compare.Banner(*breach_compare.SHIPPED)
        self._banner.render(dc, state)


def v2_chrome(north=None, north_last=True, dish=False):
    """The V2 overlay stack in render order (after the grove): field mask,
    border, phone ring, uplink (GPS fix bars), battery, readout, time, breach,
    north.
    north_last=False is the pre-2026-10 order (north under the readout/time);
    dish=True is the pre-2026-10 chrome: phone-link bars plus the GPS dish
    after the readout, no phone ring (the older comparison scripts index
    into it)."""
    colon = Image.open(os.path.join(DRAWABLES, "tw_colon.png")).convert("RGBA")
    north = north if north is not None else North()
    over = ([Readout(StripGlyphs("tw_dow.png", 18), StripGlyphs("tw_date.png", 6))]
            + ([Gps()] if dish else [])
            + [Clock(StripGlyphs("tw_time.png", 18), colon)])
    base = ([FieldMask(), Border()] + ([] if dish else [PhoneRing()])
            + [Uplink(gps=not dish), Battery()])
    return (base + over + [Breach(), north] if north_last
            else base + [north] + over + [Breach()])


# --------------------------------------------------------- display geometry --

def visible(x, y):
    """Is pixel (x, y) on the glass? The fr735xt panel is the disc r=107.5
    about the display centre, clipped to 215x180 (top/bottom are chords)."""
    if x < 0 or x >= device.W or y < 0 or y >= device.H:
        return False
    return (x + 0.5 - 107.5) ** 2 + (y + 0.5 - 90.0) ** 2 <= 107.5 ** 2


def glass(img):
    """Black out the pixels that do not exist on the panel (cf. Dc.masked())."""
    out = img.copy()
    px = out.load()
    for y in range(device.H):
        for x in range(device.W):
            if not visible(x, y):
                px[x, y] = (0, 0, 0)
    return out
