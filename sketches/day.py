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


# Plausible days as (start_hour, steps_per_minute, heart_rate) segments.
# steps here are PER-MINUTE; synthetic_day accumulates them into the cumulative
# count the watch actually reads.

# "active" — a run, a lunch walk, and a gym session (two hard-effort episodes).
_SEG_ACTIVE = [
    (0.0,  0,   52),   # sleep
    (6.5,  12,  68),   # waking
    (7.0,  120, 112),  # morning run -- warm-up      (zone 3)
    (7.083, 150, 132), # building                    (zone 4, ~7:05)
    (7.166, 158, 150), # cruising                     (zone 5, ~7:10)
    (8.0,  18,  84),   # shower / commute
    (9.0,  3,   62),   # desk
    (12.0, 105, 96),   # lunch walk (clears the move-bar)
    (12.75, 0,  64),   # long afternoon meeting -- dead still, move-bar fills up
    (15.0, 6,   134),  # anxiety spike: high HR, almost no movement -> tiny node
    (15.05, 0,  64),   # still sitting -- move-bar stays up
    (16.0, 165, 132),  # dash for the bus: vigorous straight out of a long sit
    (16.05, 5,  72),   # recovered -- same ~3 min, but movement keeps it growing
    (17.5, 45,  138),  # gym
    (18.5, 9,   74),   # evening
    (22.0, 1,   58),   # wind-down
]

# "rest" — a sedentary day: gentle walks only, no hard-effort (high-zone)
# episode, so an activity-driven face should stay small with no blooms.
_SEG_REST = [
    (0.0,  0,   52),   # sleep
    (7.0,  10,  66),   # waking
    (8.0,  20,  78),   # pottering about
    (9.0,  4,   64),   # desk
    (12.0, 60,  100),  # easy lunch stroll (zone 2, not hard)
    (12.5, 3,   66),   # desk
    (17.5, 25,  92),   # gentle evening walk
    (18.5, 6,   72),   # evening
    (22.0, 1,   56),   # wind-down
]

# "heavy" — a deliberately punishing day used to STRESS the render budget: many
# hours of intervals (run/recover sawtooth) so the dish saturates its caps (22
# filament arms, 16 blooms, the colony toward its 96-band ceiling). This is the
# worst case for any per-band render cost; `scrub.py biobloom --day heavy` is the
# scrub that would have flagged the band-scan watchdog trip before the wrist did.
_SEG_HEAVY = [
    (0.0,  0,   50),   # sleep
    (6.5,  20,  70),   # waking
    # ~13 h of alternating hard efforts and active recoveries (each ~20 min):
    (7.0,  150, 150),  (7.33, 60,  110),
    (8.0,  160, 158),  (8.33, 45,  120),
    (9.0,  150, 145),  (9.33, 70,  108),
    (10.0, 165, 160),  (10.33, 50, 118),
    (11.0, 140, 138),  (11.33, 80, 100),
    (12.0, 120, 130),  (12.5,  90, 112),
    (13.0, 160, 152),  (13.33, 40, 122),
    (14.0, 150, 148),  (14.33, 65, 106),
    (15.0, 158, 156),  (15.33, 55, 116),
    (16.0, 145, 140),  (16.33, 75, 104),
    (17.0, 162, 158),  (17.33, 50, 120),
    (18.0, 150, 146),  (18.33, 70, 108),
    (19.0, 140, 136),  (19.33, 60, 100),
    (20.0, 130, 128),  (20.33, 45, 110),
    (21.0, 120, 124),  (21.5,  30, 96),
    (22.0, 5,   72),   # wind-down
]

# "restless" — the active day, but a FRAGMENTED night: three wake-ups between
# 12am and 6am (each a short step burst + HR bump, then back to sleep). Used to
# develop the sleep-quality spore's wake-event treatment. The daytime is the
# active profile so only the night differs.
_SEG_RESTLESS = [
    (0.0,   0,   52),   # sleep
    (1.5,   30,  82), (1.55, 0, 54),   # wake 1 ~1:30 (up ~3 min)
    (3.0,   35,  86), (3.05, 0, 53),   # wake 2 ~3:00
    (4.5,   28,  80), (4.55, 0, 52),   # wake 3 ~4:30
    (6.5,   12,  68),   # waking for the day
    (7.0,   120, 112),  (7.083, 150, 132), (7.166, 158, 150),  # morning run
    (8.0,   18,  84),
    (9.0,   3,   62),
    (12.0,  105, 96),
    (12.75, 0,   64),
    (15.0,  6,   134),
    (15.05, 0,   64),
    (16.0,  165, 132),
    (16.05, 5,   72),
    (17.5,  45,  138),
    (18.5,  9,   74),
    (22.0,  1,   58),
]

_PROFILES = {"active": _SEG_ACTIVE, "rest": _SEG_REST, "heavy": _SEG_HEAVY,
             "restless": _SEG_RESTLESS}


def _segment(h, segs):
    seg = segs[0]
    for s in segs:
        if h >= s[0]:
            seg = s
        else:
            break
    return seg


def synthetic_day(seed=1, year=2026, month=6, day=14, profile="active"):
    """1440 Snapshots, one per minute, for a plausible biometric day.

    `profile` selects the activity shape ("active" or "rest"). Jitter is
    deterministic (hash16) so a given (seed, date) always renders the same
    art — the fxhash principle the real face is built on.
    """
    segs = _PROFILES.get(profile, _SEG_ACTIVE)
    snaps = []
    cum = 0
    for t in range(1440):
        _, spm, hr = _segment(t / 60.0, segs)
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
