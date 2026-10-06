#!/usr/bin/env python3
"""altkit -- shared kit for the ALTERNATE-FACE concepts (sketches/algos/alt_*.py).

The brief these concepts answer is docs/alt-faces.md (owner interview,
2026-10): faces that carry most of two-worlds V2's information -- time, date,
how much you moved (the must-haves), then sleep (with wake-ups), then effort
episodes, plus a sun/moon "neat trick" and battery only when low -- in a fresh
visual language. Everything here keeps to the faithful-sandbox rules of
device.py: integer math (idiv/imod) on the per-tick paths, real Gfx primitives
only, the 14-colour palette.

What lives here:
  geometry   -- the semiround visible area, and rim_point(): a rim marker that
                stays ON SCREEN at every angle (V2's north marker rides a
                101.7 px circle that leaves the flat bottom chord for hours
                around solar noon -- see docs/alt-faces.md).
  fonts      -- bitmap fonts as tiny string grids: a classic 5x7 and a square
                5x7 digit set, and a 3x5 small font (letters + digits). A face
                blits one glyph per call, exactly like StripGlyphs.draw on the
                watch (a pre-rendered strip PNG); module style (solid / dotted
                / gapped squares) is baked into that strip, so it costs nothing.
  astro      -- NOAA sun position + sunrise/sunset (port of core/src/astro/
                Solar.mc, float like the device), the sun-compass north dial,
                and a moon phase (mean synodic month -- new Monkey C, trivial).
  hr zones   -- V2's 9-step HR ramp (effort = zone >= 4, i.e. >= 105 bpm).
  DayLog     -- the per-minute day record every concept reads: 96 quarter-
                hour buckets (steps, peak HR zone, minutes asleep), effort
                episodes (with a 2-minute merge so a walk hovering at 105 bpm
                doesn't splinter into confetti), and last night's sleep as a
                SESSION (start, end, minutes asleep, wake-up times) that spans
                midnight. ~0.6 KB packed on-device.
  feed       -- owner-like simulated days (bed ~23:00, up ~6:00, walks a lot,
                runs, hikes) and a 2-day replay so last night's sleep -- which
                starts the evening before -- is in the record.
"""

import math

import device as dev
from device import idiv, imod, hash16, isin, account

W, H = 215, 180
CXF, CYF, RB = 107.5, 90.0, 107.5      # bezel circle (device.py)

WHITE, LT_GRAY, DK_GRAY, BLACK = (dev.COLOR_WHITE, dev.COLOR_LT_GRAY,
                                  dev.COLOR_DK_GRAY, dev.COLOR_BLACK)
RED, DK_RED, ORANGE, YELLOW = (dev.COLOR_RED, dev.COLOR_DK_RED,
                               dev.COLOR_ORANGE, dev.COLOR_YELLOW)
GREEN, DK_GREEN, BLUE, DK_BLUE = (dev.COLOR_GREEN, dev.COLOR_DK_GREEN,
                                  dev.COLOR_BLUE, dev.COLOR_DK_BLUE)
PURPLE, PINK = dev.COLOR_PURPLE, dev.COLOR_PINK
TRANSPARENT = dev.COLOR_TRANSPARENT


# ------------------------------------------------------------- geometry ----

def half_width(y):
    """Visible half-width of row y (0 outside the display)."""
    d = RB * RB - (y + 0.5 - CYF) ** 2
    return math.sqrt(d) if d > 0 else 0.0


def rim_point(deg, inset):
    """(x, y) on the VISIBLE screen edge at dial angle `deg` (clockwise from
    12 o'clock), pulled `inset` px toward the centre. The visible area is the
    bezel circle clipped to rows 0..179, so near 12 and 6 o'clock the edge is
    the flat chord, not the circle -- riding the circle (as V2's north marker
    does) puts the marker off-screen there."""
    th = math.radians(deg)
    sx, cy = math.sin(th), -math.cos(th)
    t = RB
    if cy < -1e-6:
        t = min(t, (CYF - 0.0) / -cy)            # top chord, y = 0
    elif cy > 1e-6:
        t = min(t, (H - 1 - CYF) / cy)           # bottom chord, y = 179
    t -= inset
    return int(CXF + t * sx + 0.5), int(CYF + t * cy + 0.5)


# ---------------------------------------------------------------- fonts ----
# One string per row; '#' = ink. Every glyph in a font has the same height.

DIG57 = {   # classic rounded 5x7
    "0": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    ":": [" ", " ", "#", " ", "#", " ", " "],
    " ": ["  ", "  ", "  ", "  ", "  ", "  ", "  "],
}

SQ57 = {    # square geometric 5x7
    "0": ["#####", "#   #", "#   #", "#   #", "#   #", "#   #", "#####"],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "2": ["#####", "    #", "    #", "#####", "#    ", "#    ", "#####"],
    "3": ["#####", "    #", "    #", " ####", "    #", "    #", "#####"],
    "4": ["#   #", "#   #", "#   #", "#####", "    #", "    #", "    #"],
    "5": ["#####", "#    ", "#    ", "#####", "    #", "    #", "#####"],
    "6": ["#####", "#    ", "#    ", "#####", "#   #", "#   #", "#####"],
    "7": ["#####", "    #", "    #", "   # ", "  #  ", "  #  ", "  #  "],
    "8": ["#####", "#   #", "#   #", "#####", "#   #", "#   #", "#####"],
    "9": ["#####", "#   #", "#   #", "#####", "    #", "    #", "#####"],
    ":": [" ", " ", "#", " ", "#", " ", " "],
    " ": ["  ", "  ", "  ", "  ", "  ", "  ", "  "],
}

SMALL = {   # 3x5 (M/N/W wider)
    "A": [" # ", "# #", "###", "# #", "# #"],
    "B": ["## ", "# #", "## ", "# #", "## "],
    "C": [" ##", "#  ", "#  ", "#  ", " ##"],
    "D": ["## ", "# #", "# #", "# #", "## "],
    "E": ["###", "#  ", "## ", "#  ", "###"],
    "F": ["###", "#  ", "## ", "#  ", "#  "],
    "G": [" ##", "#  ", "# #", "# #", " ##"],
    "H": ["# #", "# #", "###", "# #", "# #"],
    "I": ["###", " # ", " # ", " # ", "###"],
    "J": ["  #", "  #", "  #", "# #", " # "],
    "K": ["# #", "# #", "## ", "# #", "# #"],
    "L": ["#  ", "#  ", "#  ", "#  ", "###"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "N": ["#  #", "## #", "# ##", "#  #", "#  #"],
    "O": [" # ", "# #", "# #", "# #", " # "],
    "P": ["## ", "# #", "## ", "#  ", "#  "],
    "R": ["## ", "# #", "## ", "# #", "# #"],
    "S": [" ##", "#  ", " # ", "  #", "## "],
    "T": ["###", " # ", " # ", " # ", " # "],
    "U": ["# #", "# #", "# #", "# #", "###"],
    "V": ["# #", "# #", "# #", "# #", " # "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "Y": ["# #", "# #", " # ", " # ", " # "],
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", " ##", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    ":": [" ", "#", " ", "#", " "],
    ".": [" ", " ", " ", " ", "#"],
    ",": [" ", " ", " ", "#", "#"],
    "-": ["   ", "   ", "###", "   ", "   "],
    "/": ["  #", "  #", " # ", "#  ", "#  "],
    "h": ["#  ", "#  ", "## ", "# #", "# #"],
    "m": ["     ", "     ", "#### ", "# # #", "# # #"],
    " ": ["  ", "  ", "  ", "  ", "  "],
}

WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def glyph_w(font, ch):
    g = font.get(ch)
    return len(g[0]) if g else 0


def text_w(font, s, scale=1, track=1):
    """Pixel width of `s` (glyph cells * scale + `track` px between glyphs)."""
    w = 0
    for i, ch in enumerate(s):
        w += glyph_w(font, ch) * scale
        if i < len(s) - 1:
            w += track
    return w


def font_h(font, scale=1):
    return len(font["0"]) * scale


def draw_text(dc, font, s, x, y, scale, color, track=1, style="solid"):
    """Blit `s` at (x, y). One counted call per glyph (= StripGlyphs.draw on
    the watch: the glyph, in this style and colour, is a cell of a
    pre-rendered strip PNG). style: solid | gap (modules inset 1 px) |
    dot (round modules)."""
    d = dc._d
    rgb = dev._rgb(dc._resolve(color))
    cx = x
    for i, ch in enumerate(s):
        g = font.get(ch)
        if g is None:
            continue
        for r, row in enumerate(g):
            for c, px in enumerate(row):
                if px != "#":
                    continue
                x0 = cx + c * scale
                y0 = y + r * scale
                if style == "solid" or scale == 1:
                    d.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=rgb)
                elif style == "gap":
                    d.rectangle((x0, y0, x0 + scale - 2, y0 + scale - 2), fill=rgb)
                else:  # dot
                    rr = (scale - 1) / 2.0
                    d.ellipse((x0, y0, x0 + 2 * rr, y0 + 2 * rr), fill=rgb)
        dc.calls += 1
        cx += glyph_w(font, ch) * scale + track
    return cx


def time_str(snap, lead_blank=True):
    """'H:MM' (12 h, no leading zero) or 'HH:MM' (24 h), per is24Hour."""
    if snap.hour is None or snap.minute is None:
        return "--:--"
    h = snap.hour
    if getattr(snap, "is24Hour", None) is False:
        h = h % 12
        if h == 0:
            h = 12
        hs = str(h)
    else:
        hs = "%02d" % h
    return "%s:%02d" % (hs, snap.minute)


# ---------------------------------------------------------------- astro ----

def julian_day(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524


def _solar(T):
    L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360.0
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    Mr = math.radians(M)
    C = ((1.914602 - T * (0.004817 + 0.000014 * T)) * math.sin(Mr)
         + (0.019993 - 0.000101 * T) * math.sin(2 * Mr) + 0.000289 * math.sin(3 * Mr))
    om = 125.04 - 1934.136 * T
    lam = L0 + C - 0.00569 - 0.00478 * math.sin(math.radians(om))
    e0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60
    eps = e0 + 0.00256 * math.cos(math.radians(om))
    decl = math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(lam)))
    yv = math.tan(math.radians(eps / 2)) ** 2
    L0r = math.radians(L0)
    eqt = 4 * math.degrees(yv * math.sin(2 * L0r) - 2 * 0.016708634 * math.sin(Mr)
                           + 4 * 0.016708634 * yv * math.sin(Mr) * math.cos(2 * L0r)
                           - 0.5 * yv * yv * math.sin(4 * L0r)
                           - 1.25 * 0.016708634 ** 2 * math.sin(2 * Mr))
    return decl, eqt


def _local_jd_utc(snap):
    """(jd, utcHours) for the snapshot's local civil time."""
    off = getattr(snap, "utcOffsetSec", None) or 0
    jd = julian_day(snap.year, snap.month, snap.day)
    um = snap.hour * 60 + snap.minute - off / 60.0
    if um < 0:
        um += 1440
        jd -= 1
    elif um >= 1440:
        um -= 1440
        jd += 1
    return jd, um / 60.0


def sun_position(snap):
    """(azimuthDeg 0=N clockwise, elevationDeg) or None without a location."""
    lat, lon = getattr(snap, "lat", None), getattr(snap, "lon", None)
    if lat is None or lon is None or snap.year is None or snap.hour is None:
        return None
    jd, uh = _local_jd_utc(snap)
    T = (jd + (uh - 12.0) / 24.0 - 2451545.0) / 36525.0
    decl, eqt = _solar(T)
    tst = (uh * 60 + eqt + 4 * lon) % 1440
    ha = tst / 4 - 180
    latr = math.radians(lat)
    zen = math.acos(max(-1.0, min(1.0, math.sin(latr) * math.sin(decl)
                                  + math.cos(latr) * math.cos(decl) * math.cos(math.radians(ha)))))
    elev = 90 - math.degrees(zen)
    den = math.cos(latr) * math.sin(zen)
    az = math.degrees(math.acos(max(-1.0, min(1.0, (math.sin(latr) * math.cos(zen)
                                                    - math.sin(decl)) / den)))) if abs(den) > 1e-6 else 180.0
    az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    return az, elev


def sun_times(snap):
    """(sunriseMin, sunsetMin) as LOCAL minutes of day, or None (no location
    / polar day or night). Port of Solar.sunTimes + toLocalMinutes."""
    lat, lon = getattr(snap, "lat", None), getattr(snap, "lon", None)
    if lat is None or lon is None or snap.year is None:
        return None
    jd = julian_day(snap.year, snap.month, snap.day)
    T = (jd - 2451545.0) / 36525.0
    decl, eqt = _solar(T)
    latr = math.radians(lat)
    cosH = (math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(decl))
            - math.tan(latr) * math.tan(decl))
    if cosH > 1 or cosH < -1:
        return None
    ha = math.degrees(math.acos(cosH))
    noon = 720 - 4 * lon - eqt
    off = (getattr(snap, "utcOffsetSec", None) or 0) / 60.0
    rise = (noon - ha * 4 + off) % 1440
    sset = (noon + ha * 4 + off) % 1440
    return int(rise + 0.5), int(sset + 0.5)


def north_dial(snap):
    """Sun-compass: dial angle of true north (clockwise from 12) when 12
    o'clock is aimed at the sun, or None when the sun can't be sighted."""
    p = sun_position(snap)
    if p is None:
        return None
    az, el = p
    if el <= -0.833 or el >= 80.0:
        return None
    return (360.0 - az) % 360.0


SYNODIC = 29.530588853


def moon_age(snap):
    """Days since new moon (0..29.53), mean synodic month from the
    2000-01-06 18:14 UTC new moon. Good to ~half a day -- plenty for a glyph."""
    if snap.year is None:
        return None
    jd, uh = _local_jd_utc(snap)
    return ((jd - 0.5 + uh / 24.0) - 2451550.26) % SYNODIC


def draw_moon(dc, cx, cy, r, age, lit=WHITE, dark=DK_GRAY, outline=None):
    """Moon disc in its phase: the dark disc, then the lit part one row at a
    time (2r+1 drawLines), then an optional outline (needed on a white face,
    where a full moon would otherwise vanish). Waxing lights the right limb
    (northern sky)."""
    if age is None:
        return
    k = math.cos(2 * math.pi * age / SYNODIC)
    waxing = age < SYNODIC / 2
    if dark is not None:
        dc.setColor(dark, TRANSPARENT)
        dc.fillCircle(cx, cy, r)
    dc.setColor(lit, TRANSPARENT)
    for dy in range(-r, r + 1):
        rr = math.sqrt(max(0.0, (r + 0.5) ** 2 - dy * dy))
        if waxing:
            x0, x1 = rr * k, rr
        else:
            x0, x1 = -rr, -rr * k
        if x1 - x0 >= 0.5:
            dc.drawLine(int(cx + x0 + 0.5), cy + dy, int(cx + x1 - 0.5), cy + dy)
    if outline is not None:
        dc.setColor(outline, TRANSPARENT)
        draw_circle(dc, cx, cy, r)


def moon_name(age):
    if age is None:
        return ""
    i = int((age / SYNODIC) * 8 + 0.5) % 8
    return ["new", "waxing crescent", "first quarter", "waxing gibbous", "full",
            "waning gibbous", "last quarter", "waning crescent"][i]


# ------------------------------------------------------------- HR zones ----
# V2's 9-step ramp (MossGrove.HR_BOUNDS/HR_RAMP). Effort = zone >= 4 (105 bpm).

HR_BOUNDS = [60, 80, 95, 105, 120, 138, 152, 165]
HR_RAMP = [DK_BLUE, BLUE, DK_GREEN, GREEN, YELLOW, ORANGE, RED, PINK, PURPLE]
EFFORT = 4


def hr_zone(hr):
    if hr is None or hr <= 0:
        return -1
    for i in range(8):
        if hr < HR_BOUNDS[i]:
            return i
    return 8


# ---------------------------------------------------------------- DayLog ----

NB = 96                 # quarter-hour buckets per day
EMAX = 16               # stored effort episodes
WMAX = 8                # stored wake-ups per night
EPI_MERGE = 5           # an episode survives dips below 105 bpm of <= this many min
REST_HR = 62            # asleep needs HR <= this (owner resting ~48 bpm)
IDLE_SPM = 1            # ... and <= this many steps that minute
ONSET = 20              # quiet minutes in the night window that open a session
WAKE_SPM = 6            # steps/min that mark an awakening
END_AWAKE = 20          # awake minutes that end a session at any hour
END_AWAKE_AM = 8        # ... after 05:00
NIGHT_LEN = 840         # night window: 20:00 + 840 min = 10:00


def nclock(m):
    """Minute of day -> minutes since 20:00 (the night clock, 0..1439)."""
    return imod(m - 1200 + 1440, 1440)


def day_min(nc):
    """Night clock -> minute of day."""
    return imod(nc + 1200, 1440)


class DayLog:
    """The per-minute record behind every concept. Integer-only.

    Today (reset at midnight): bsteps/bzone/bsleep per quarter hour, steps,
    episodes [start, dur, peakZone, mag]. Last night (survives midnight):
    `night` = [startNc, endNc, asleepMin, [wakeNc...]] once the morning ends
    the session; `cur` is the session in progress."""

    def __init__(self):
        self.bsteps = [0] * NB
        self.bzone = [-1] * NB
        self.bsleep = [0] * NB
        self.steps = 0
        self.prev = 0
        self.last_day = -1
        self.last_min = -1
        self.now = 0
        self.epi = []
        self.epi_open = False
        self.epi_gap = 0
        self.quiet_run = 0
        self.awake_run = 0
        self.run_woke = False
        self.cur = None
        self.night = None

    def advance(self, s):
        if s.hour is None or s.minute is None:
            return
        now = s.hour * 60 + s.minute
        day = s.day if s.day is not None else 0
        if day != self.last_day:
            self.bsteps = [0] * NB
            self.bzone = [-1] * NB
            self.bsleep = [0] * NB
            self.epi = []
            self.epi_open = False
            self.prev = 0
            self.last_day = day
            self.last_min = now - 1
        elif now == self.last_min:
            return                       # re-render of the same minute
        elif now < self.last_min:
            self.last_min = now          # clock moved back: resync
            return
        self.now = now
        spm = 0
        if s.steps is not None:
            if s.steps >= self.prev:
                spm = s.steps - self.prev
            self.prev = s.steps
            self.steps = s.steps
        hr = s.heartRate
        z = hr_zone(hr)
        b = idiv(now, 15)
        self.bsteps[b] += spm
        if z > self.bzone[b]:
            self.bzone[b] = z
        self._episode(now, spm, z)
        self._sleep(now, spm, hr, b)
        self.last_min = now

    def _episode(self, now, spm, z):
        if z >= EFFORT:
            if not self.epi_open:
                self.epi_open = True
                if len(self.epi) < EMAX:
                    self.epi.append([now, 0, z, 0])
                else:
                    self.epi_open = False
                    return
            e = self.epi[-1]
            e[1] = now - e[0] + 1
            if z > e[2]:
                e[2] = z
            e[3] += 1 + idiv(spm, 16)
            self.epi_gap = 0
        elif self.epi_open:
            self.epi_gap += 1
            if self.epi_gap > EPI_MERGE:
                self.epi_open = False

    def _sleep(self, now, spm, hr, b):
        nc = nclock(now)
        nightwin = nc < NIGHT_LEN
        quiet = spm <= IDLE_SPM and (hr is None or hr <= REST_HR)
        cur = self.cur
        if cur is None:
            if nightwin and quiet:
                self.quiet_run += 1
                if self.quiet_run >= ONSET:
                    self.cur = [nc - ONSET + 1, ONSET, [], False]
                    for k in range(ONSET):          # credit the onset minutes
                        mb = idiv(imod(now - k + 1440, 1440), 15)
                        if now - k >= 0:
                            self.bsleep[mb] += 1
                    self.awake_run = 0
            else:
                self.quiet_run = 0
            return
        if quiet:
            cur[1] += 1
            self.bsleep[b] += 1
            self.awake_run = 0
            self.run_woke = False
            return
        self.awake_run += 1
        if spm >= WAKE_SPM and not self.run_woke:
            if len(cur[2]) < WMAX:
                cur[2].append(nc)
                self.run_woke = True
        am = nc >= 540                               # after 05:00
        if (self.awake_run >= END_AWAKE or not nightwin
                or (am and self.awake_run >= END_AWAKE_AM)):
            if self.run_woke and cur[2]:
                cur[2].pop()                         # the final wake isn't a wake-up
            if cur[1] >= 120:
                self.night = [cur[0], nc - self.awake_run + 1, cur[1], list(cur[2])]
            self.cur = None
            self.quiet_run = 0
            self.awake_run = 0
            self.run_woke = False

    # ---- convenience reads (render side) ----------------------------------

    def cum_steps(self):
        """Cumulative steps at the END of each bucket (render-time scratch)."""
        out = [0] * NB
        c = 0
        for i in range(NB):
            c += self.bsteps[i]
            out[i] = c
        account(NB)
        return out

    def sleep_min(self):
        return self.night[2] if self.night else 0

    def wakes(self):
        return self.night[3] if self.night else []

    def state_bytes(self):
        # packed on-device: 96 x (steps 12b | zone 4b | asleep 4b) Numbers,
        # EMAX x 2 episode Numbers, night 4 + WMAX, a few scalars
        return 96 * 4 + EMAX * 2 * 4 + (4 + WMAX) * 4 + 12 * 4


# ----------------------------------------------------------- shared bits ----

def draw_circle(dc, x, y, r):
    """1-px circle outline = Dc.drawCircle on the watch (device.Dc lacks it)."""
    dc.calls += 1
    dc._d.ellipse((x - r, y - r, x + r, y + r), outline=dev._rgb(dc._fg))


def battery_low(dc, snap, x, y, thresh=20, color=RED):
    """A small battery glyph, drawn ONLY when the charge is at/below
    `thresh` % (owner: status only when needed). 11x6 at (x, y)."""
    p = getattr(snap, "batteryPct", None)
    if p is None or p > thresh:
        return False
    dc.setColor(color, TRANSPARENT)
    dc.drawLine(x, y, x + 9, y)
    dc.drawLine(x, y + 5, x + 9, y + 5)
    dc.drawLine(x, y, x, y + 5)
    dc.drawLine(x + 9, y, x + 9, y + 5)
    dc.fillRectangle(x + 10, y + 2, 1, 2)
    fill = max(1, int(8 * p / 100.0 + 0.5))
    dc.fillRectangle(x + 1, y + 1, fill, 4)
    return True


def north_tick(dc, snap, color=RED, inset=3, size=5):
    """The sun-compass trick, kept on screen at every angle: aim 12 o'clock
    at the sun, the small triangle on the edge points at true north."""
    nd = north_dial(snap)
    if nd is None:
        return None
    tx, ty = rim_point(nd, inset)
    bx, by = rim_point(nd, inset + size + 2)
    th = math.radians(nd)
    px, py = math.cos(th), math.sin(th)
    dc.setColor(color, TRANSPARENT)
    dc.fillPolygon([(tx, ty), (int(bx + px * size * 0.7 + 0.5), int(by + py * size * 0.7 + 0.5)),
                    (int(bx - px * size * 0.7 + 0.5), int(by - py * size * 0.7 + 0.5))])
    return nd


def date_str(snap, fmt="dow day mon"):
    parts = []
    for f in fmt.split():
        if f == "dow" and snap.dayOfWeek:
            parts.append(WEEKDAYS[snap.dayOfWeek - 1])
        elif f == "day" and snap.day:
            parts.append(str(snap.day))
        elif f == "mon" and snap.month:
            parts.append(MONTHS[snap.month - 1])
    return " ".join(parts)


def hm(mins):
    """Minutes -> 'H:MM' (24 h clock style, for sun times)."""
    m = int(mins) % 1440
    return "%d:%02d" % (m // 60, m % 60)


def hm12(mins):
    m = int(mins) % 1440
    h = (m // 60) % 12
    return "%d:%02d" % (12 if h == 0 else h, m % 60)


def dur_str(mins):
    return "%dh%02d" % (mins // 60, mins % 60)


# ----------------------------------------------------------------- feed ----

class Snap:
    """Mirror of core/src/data/Snapshot.mc (every field the concepts read)."""

    def __init__(self):
        self.hour = self.minute = None
        self.second = 0
        self.utcOffsetSec = -7 * 3600
        self.is24Hour = False
        self.year = self.month = self.day = self.dayOfWeek = None
        self.steps = None
        self.stepGoal = 14000          # Garmin auto-goal for someone who walks a lot
        self.distanceCm = None
        self.calories = None
        self.heartRate = None
        self.batteryPct = None
        self.phoneConnected = True
        self.lat, self.lon = 45.512575, -122.638737     # Portland
        self.gpsFix = 2


# (start_hour, steps/min, HR bpm). Owner: in bed ~23:00, up ~6:00, wears the
# watch overnight (resting ~48 bpm), walks a lot, runs and hikes.
SEG = {
    # Tuesday: one wake-up at ~3:10, commute + lunch walks, evening run
    "weekday": [
        (0.0, 0, 49), (3.17, 26, 70), (3.24, 0, 48),
        (6.0, 10, 64), (6.25, 14, 80), (7.4, 8, 74),
        (7.55, 104, 97), (7.85, 10, 78), (8.2, 2, 64),
        (10.5, 88, 86), (10.65, 2, 66),
        (12.15, 112, 103), (12.6, 3, 70),
        (15.0, 40, 84), (15.25, 3, 68),
        (17.25, 104, 96), (17.6, 12, 78),
        (18.1, 150, 128), (18.25, 164, 149), (18.65, 96, 116), (18.8, 18, 84),
        (19.1, 12, 80), (20.5, 1, 61), (22.75, 10, 64), (23.0, 0, 52),
    ],
    # Saturday: unbroken night, a long hike (up hard, down easy), evening stroll
    "hike": [
        (0.0, 0, 50), (7.0, 14, 66), (7.5, 16, 76), (8.5, 2, 70),
        (9.25, 82, 122), (9.75, 78, 134), (10.25, 84, 126), (10.6, 74, 138),
        (10.75, 6, 84), (11.25, 92, 108), (12.5, 40, 92), (13.0, 2, 72),
        (14.0, 16, 78), (18.0, 8, 74), (19.0, 90, 92), (19.35, 5, 66),
        (21.0, 2, 60), (23.4, 0, 52),
    ],
    # Thursday: broken night (3 wake-ups), commute walks only, no run
    "restless": [
        (0.0, 0, 52), (1.33, 30, 78), (1.4, 0, 51), (3.08, 25, 74),
        (3.2, 0, 50), (4.67, 28, 76), (4.74, 0, 50),
        (6.15, 10, 66), (6.4, 14, 82), (7.4, 8, 74),
        (7.55, 102, 95), (7.85, 10, 76), (8.2, 2, 66),
        (12.2, 64, 88), (12.6, 3, 68), (17.25, 102, 95), (17.6, 10, 76),
        (19.1, 12, 80), (20.5, 1, 62), (22.9, 10, 64), (23.2, 0, 53),
    ],
    # Sunday under the weather: long lie-in, pottering only
    "rest": [
        (0.0, 0, 52), (8.5, 10, 66), (9.0, 18, 74), (10.0, 5, 66),
        (13.0, 30, 78), (13.5, 4, 66), (17.0, 22, 76), (17.5, 4, 64),
        (21.5, 2, 60), (22.5, 0, 53),
    ],
}

# The evening BEFORE each day (so last night's sleep starts in the record).
PREV_EVENING = {
    "weekday": [(18.0, 24, 82), (20.5, 3, 61), (22.75, 14, 64), (23.0, 0, 52)],
    "hike": [(18.0, 20, 80), (21.0, 3, 60), (23.3, 12, 64), (23.5, 0, 52)],
    "restless": [(18.0, 22, 80), (20.5, 3, 62), (23.2, 12, 64), (23.5, 0, 53)],
    "rest": [(18.0, 16, 78), (21.0, 3, 60), (22.0, 10, 62), (22.25, 0, 54)],
}

# (year, month, day, dayOfWeek 1=Sun, battery at 00:00, battery at 24:00)
DATES = {
    "weekday": (2026, 10, 6, 3, 71, 58),
    "hike": (2026, 10, 3, 7, 64, 47),
    "restless": (2026, 10, 8, 5, 22, 9),     # battery runs low this day
    "rest": (2026, 10, 25, 1, 88, 80),       # near full moon (Oct 26)
}


def _seg_at(h, segs):
    cur = segs[0]
    for sgm in segs:
        if h >= sgm[0]:
            cur = sgm
        else:
            break
    return cur


def _minutes(segs, seed, t0, t1, salt):
    """Per-minute (spm, hr) for minutes t0..t1-1 of a segment list."""
    out = []
    for t in range(t0, t1):
        _, spm, hr = _seg_at(t / 60.0, segs)
        j = hash16(seed, t, salt)
        if spm:
            step = max(0, spm + idiv((j % 21 - 10) * spm, 60))
        else:
            step = 1 if (j % 1000) < 12 else 0
        hrv = hr + (hash16(seed, t, salt + 4) % 9) - 4
        out.append((step, hrv))
    return out


def day_feed(profile, seed=1):
    """Two-day replay for `profile`: the previous evening (18:00-24:00 of the
    day before) then the whole day. Returns a list of (snap, is_today)."""
    y, mo, d, dow, b0, b1 = DATES[profile]
    feed = []
    # previous evening: same calendar shape, day - 1
    prev = _minutes(PREV_EVENING[profile], seed + 100, 18 * 60, 1440, 31)
    cum = 6000
    for i, (step, hr) in enumerate(prev):
        t = 18 * 60 + i
        cum += step
        s = Snap()
        s.hour, s.minute = t // 60, t % 60
        s.year, s.month, s.day = y, mo, d - 1
        s.dayOfWeek = ((dow - 2) % 7) + 1
        s.steps, s.heartRate = cum, hr
        s.batteryPct = b0 + 3
        feed.append((s, False))
    cum = 0
    mins = _minutes(SEG[profile], seed, 0, 1440, 11)
    for t, (step, hr) in enumerate(mins):
        cum += step
        s = Snap()
        s.hour, s.minute = t // 60, t % 60
        s.year, s.month, s.day, s.dayOfWeek = y, mo, d, dow
        s.steps, s.heartRate = cum, hr
        s.batteryPct = b0 + (b1 - b0) * t / 1440.0
        feed.append((s, True))
    return feed
