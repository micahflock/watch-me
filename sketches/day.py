#!/usr/bin/env python3
"""Biometric "day" feed for the generative-art sandbox.

Produces the same per-minute Snapshot the watch builds from DataSource
(core/src/data/Snapshot.mc): hour/minute, the calendar fields that seed the
day, cumulative daily steps, and a heart-rate sample. Movement/unrest are NOT
provided here — the watch derives them inside StrataField from the step delta,
so the sandbox does too, keeping the data path identical.

Swap or extend `synthetic_day` to replay a real exported day later; anything
that yields a sequence of Snapshots in minute order works with scrub.py.
"""

from device import hash16


class Snapshot:
    """Mirror of core/src/data/Snapshot.mc (only the fields the art reads)."""

    def __init__(self):
        self.hour = None
        self.minute = None
        self.second = 0
        self.year = None
        self.month = None
        self.day = None
        self.dayOfWeek = None
        self.steps = None        # cumulative daily steps (ActivityMonitor)
        self.heartRate = None    # most recent bpm sample, or None


# A plausible day as (start_hour, steps_per_minute, heart_rate) segments.
# steps here are PER-MINUTE; synthetic_day accumulates them into the cumulative
# count the watch actually reads.
_SEGMENTS = [
    (0.0,  0,   52),   # sleep
    (6.5,  12,  68),   # waking
    (7.0,  158, 150),  # morning run
    (8.0,  18,  84),   # shower / commute
    (9.0,  3,   62),   # desk
    (12.0, 105, 96),   # lunch walk
    (12.75, 4,  64),   # desk
    (17.5, 45,  138),  # gym
    (18.5, 9,   74),   # evening
    (22.0, 1,   58),   # wind-down
]


def _segment(h):
    seg = _SEGMENTS[0]
    for s in _SEGMENTS:
        if h >= s[0]:
            seg = s
        else:
            break
    return seg


def synthetic_day(seed=1, year=2026, month=6, day=14):
    """1440 Snapshots, one per minute, for a plausible biometric day.

    Jitter is deterministic (hash16) so a given (seed, date) always renders the
    same art — the fxhash principle the real face is built on.
    """
    snaps = []
    cum = 0
    for t in range(1440):
        _, spm, hr = _segment(t / 60.0)
        j = hash16(seed, t, 7)
        # per-minute steps with a little noise; idle minutes mostly contribute 0
        if spm:
            step = max(0, spm + (j % 21) - 10)
        else:
            step = 1 if (j % 1000) < 30 else 0
        cum += step

        s = Snapshot()
        s.hour, s.minute = t // 60, t % 60
        s.second = 0
        s.year, s.month, s.day = year, month, day
        s.dayOfWeek = 1 + ((day + 3) % 7)
        s.steps = cum
        s.heartRate = hr + (hash16(seed, t, 11) % 13) - 6
        snaps.append(s)
    return snaps
