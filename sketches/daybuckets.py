#!/usr/bin/env python3
"""daybuckets — the shared day-record for the two-worlds V2 biometric sketches.

The device never hands us HR-over-the-day; DataSource gives only the CURRENT hr
sample and the CUMULATIVE step count each onUpdate (core/src/data/Snapshot.mc).
So, exactly like BioBloom, V2 has to accrete its own day record in RAM and (on
the real face) persist it via the object store across a reload.

The cheap, legible store is a fixed array of time buckets: BUCKETS slots, each
BUCKET_MIN minutes wide, indexed by time-of-day. Per bucket we keep the PEAK HR
of the bucket (peak reads the day's efforts better than an average) and the STEP
SUM (the bucket's activity). That is ~2 Numbers/bucket; on-device each bucket
packs to a single Number (maxHr<<8 | actLevel), so the whole day is well under
1 KB and trivially persistable -- RAM is not the constraint here, the watchdog
is, and every viz below draws ONE primitive per elapsed bucket.

A bucket is "elapsed" once the clock has reached it, so the whole day so far is
drawn (idle buckets included, as short/cool marks) -- that is what makes it read
as a timeline rather than only the active spans.

This module is pure integer math (idiv/imod) so it ports to Monkey C verbatim;
the 9-step HR ramp mirrors BioBloom's (finer than the shared GenArt ramp).
"""

from device import (idiv, imod, isin, COLOR_DK_GRAY,
                    COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
                    COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK,
                    COLOR_PURPLE)

BUCKETS = 96           # 24 h / 96 = 15-min buckets (3.75 deg each on a ring)
BUCKET_MIN = 15
CX, CY = 107, 90       # bezel centre (sandbox renders standalone, no overlays)

# MossGrove's 9-step HR ramp (mirrors MossGrove.mc HR_BOUNDS/HR_RAMP): cool at
# rest -> hot for hard efforts, the hot end on Garmin's zones (Z1 amber x2,
# Z2 orange, Z3 red, Z4 pink, Z5 purple; owner 2026-10, "C keep105" in
# zone_color_compare.py). BioBloom keeps the older ramp (algos/biobloom.py).
HR_BOUNDS = [60, 80, 98, 105, 117, 137, 156, 176]
HR_RAMP = [COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_YELLOW,
           COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK, COLOR_PURPLE]


def hr_zi(hr):
    if hr is None or hr <= 0:
        return -1
    for i in range(len(HR_BOUNDS)):
        if hr < HR_BOUNDS[i]:
            return i
    return len(HR_BOUNDS)        # 8 == PURPLE (HR >= 176, Z5)


def hr_color(hr):
    zi = hr_zi(hr)
    return COLOR_DK_GRAY if zi < 0 else HR_RAMP[zi]


class DayRecord:
    """Per-minute accretor shared by every V2 sketch. advance(snap) each minute;
    read maxhr[]/steps[] and `now` (the highest elapsed bucket) at render."""

    def __init__(self):
        self.maxhr = [0] * BUCKETS      # peak HR seen in the bucket (0 = no data)
        self.steps = [0] * BUCKETS      # step delta summed into the bucket
        self.now = -1                   # highest elapsed bucket (-1 before any)
        self._prev = None               # previous cumulative step count
        self._lastday = -1

    def reset(self):
        for i in range(BUCKETS):
            self.maxhr[i] = 0
            self.steps[i] = 0
        self.now = -1
        self._prev = None

    def advance(self, snap):
        if snap.hour is None or snap.minute is None:
            return
        day = snap.day if snap.day is not None else 0
        if day != self._lastday:
            self.reset()
            self._lastday = day
        t = snap.hour * 60 + snap.minute
        b = idiv(t, BUCKET_MIN)
        if b >= BUCKETS:
            b = BUCKETS - 1
        if b > self.now:
            self.now = b
        st = snap.steps
        if st is not None:
            if self._prev is not None and st > self._prev:
                self.steps[b] += st - self._prev
            self._prev = st
        hr = snap.heartRate
        if hr is not None and hr > self.maxhr[b]:
            self.maxhr[b] = hr

    def state_bytes(self):
        # On-device this is one packed Number/bucket (maxHr<<8 | actLevel) plus a
        # few scalars; the sandbox keeps two arrays for clarity, so report the
        # device figure: ~BUCKETS Numbers (~5 B each) + persistence overhead.
        return BUCKETS * 5


# Angle (1/256ths of a turn, GenArt convention) for a bucket: midnight at the
# top (12 o'clock), clockwise through the day -- 6 o'clock-of-day to the right,
# noon at the bottom, evening on the left. a=192 is straight up; +phase walks CW.
def bucket_angle(b):
    return imod(192 + idiv(b * 256, BUCKETS), 256)


def px(cx, r, a):
    return cx + idiv(r * isin(a + 64), 127)


def py(cy, r, a):
    return cy + idiv(r * isin(a), 127)


# Activity magnitude (px) for a bucket's step sum, clamped to `span`. A 15-min
# bucket runs ~0 (still) to ~2200 (hard run); DIV maps that onto the radial span.
def act_len(stepsum, span, div):
    v = idiv(stepsum, div)
    if v > span:
        v = span
    return v
