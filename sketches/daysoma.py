#!/usr/bin/env python3
"""daysoma -- the TIME-AGNOSTIC day record for the organic two-worlds V2 sketches
(nebula / moss / neurons).

Unlike daybuckets (which pinned each event to its time of day), this keeps only
WHAT happened, not WHEN -- which is all the brief asks for. Three things drive
every organic composition:

  * act_units  -- total movement over the day (sum of per-minute step->growth
                  units). Governs how BIG / DENSE / spread-out the piece is.
  * zone_min[9]-- minutes spent in each HR zone (the 9-step BioBloom ramp).
                  Governs the COLOUR MIX: a calm day skews blue, a hard day
                  skews red/pink. Sampled per element via zone_pick().
  * episodes   -- discrete elevated-HR events (zone >= ACTIVE). Each stores its
                  PEAK zone and a MAGNITUDE (duration + banked movement), so an
                  exercise bout is a big bright focus and an anxiety blip a small
                  one -- exactly BioBloom's bloom semantics, minus the geometry.
                  Capped at EMAX; placement is deterministic from `seed` so the
                  composition is stable frame-to-frame (no jitter) and unique per
                  day (the fxhash principle).

All integer math -> ports to Monkey C verbatim. On-device this is a handful of
scalars + zone_min[9] + EMAX*2 episode Numbers => a few hundred bytes, persisted
like the BioBloom dish. The watchdog, not RAM, is the budget; every renderer
below self-bounds its primitive count with an ink budget.
"""

from device import (idiv, imod, hash16, account,
                    COLOR_DK_RED, COLOR_RED, COLOR_ORANGE, COLOR_YELLOW,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_BLUE, COLOR_DK_BLUE)
from daybuckets import hr_zi, HR_RAMP, CX, CY, px, py  # reuse the shared HR ramp

ZLUT = 32              # size of the per-frame zone-colour lookup table

ACTIVE = 4             # zone idx >= this is an elevated-HR minute (HR >= 105)
EMAX = 16             # cap on stored episodes (bright foci)
KACT = 6              # steps/min -> one growth unit (matches BioBloom)
MOM_DIV = 16          # steps/min -> banked-magnitude units during an episode

# --- sleep inference (ported from BioBloom): no sleep API at 2.4, so sleep is
# overnight quiescence -- night-hour minutes with no movement and a resting HR.
# _night accrues it; at the midnight rollover its total is handed to sleep_seed
# (the value the morning visual reads) and keeps accruing through the early
# morning; the first solid movement freezes the seed and clears the meter.
REST_HR = 72           # HR at/below this counts as resting
IDLE_SPM = 1           # steps/min at/below this is "still"
NIGHT_START = 20       # hour >= this OR <= NIGHT_END is "night"
NIGHT_END = 10
MORNING_END = 11       # up to this hour the seed still tracks the night
WAKE_START = 5         # earliest hour a "got up" movement clears the meter
SLEEP_CAP = 600        # cap the rest meter (~10 h)

# hours-slept ramp: cool = well rested, warm = short night. Indexed by
# (hours - 3), clamped 0..7 (<=3 h .. >=10 h) -- same scheme as BioBloom.
SLEEP_RAMP = [COLOR_DK_RED, COLOR_RED, COLOR_ORANGE, COLOR_YELLOW,
              COLOR_DK_GREEN, COLOR_GREEN, COLOR_BLUE, COLOR_DK_BLUE]


def sleep_slot(mins):
    s = idiv(mins, 60) - 3
    if s < 0:
        s = 0
    if s > 7:
        s = 7
    return s


class DayRecord:
    def __init__(self):
        self.zone_min = [0] * 9
        self.act_units = 0          # total movement growth units
        self.active_min = 0         # minutes with real movement
        self.idle_min = 0           # minutes essentially still
        self.epz = [0] * EMAX       # episode peak zone
        self.emag = [0] * EMAX      # episode magnitude (duration + movement)
        self.nepi = 0
        self.seed = 1
        self._prev = None
        self._epi_on = False
        self._epi_idx = -1
        self._lastday = -1
        # sleep meters live ACROSS the midnight reset (not touched by reset())
        self._night = 0            # live overnight rest meter (minutes)
        self.sleep_seed = 0        # frozen "last night's sleep" the morning reads

    def reset(self):
        for i in range(9):
            self.zone_min[i] = 0
        self.act_units = 0
        self.active_min = 0
        self.idle_min = 0
        for i in range(EMAX):
            self.epz[i] = 0
            self.emag[i] = 0
        self.nepi = 0
        self._prev = None
        self._epi_on = False
        self._epi_idx = -1

    def advance(self, snap):
        if snap.hour is None or snap.minute is None:
            return
        day = snap.day if snap.day is not None else 0
        if day != self._lastday:
            # hand the overnight meter to the new day's seed BEFORE wiping
            self.sleep_seed = self._night
            self.reset()
            self._lastday = day
            # date-driven per-day seed: the art's SHAPE/placement varies day to
            # day (the fxhash principle), independent of the activity data.
            mo = snap.month if snap.month is not None else 1
            yr = snap.year if snap.year is not None else 2026
            self.seed = imod(hash16(day, mo * 32 + (yr & 63), 3), 4096)

        spm = 0
        st = snap.steps
        if st is not None:
            if self._prev is not None and st > self._prev:
                spm = st - self._prev
            self._prev = st
        move = idiv(spm, KACT)
        if move > 0:
            self.act_units += move
            self.active_min += 1
        else:
            self.idle_min += 1

        hr = snap.heartRate
        zi = hr_zi(hr)
        if zi >= 0:
            self.zone_min[zi] += 1

        # --- overnight quiescence -> last night's sleep ---
        hh = snap.hour
        quiescent = (spm <= IDLE_SPM) and (hr is None or hr <= REST_HR)
        is_night = (hh >= NIGHT_START or hh <= NIGHT_END)
        if is_night and quiescent and self._night < SLEEP_CAP:
            self._night += 1
        if hh <= MORNING_END and self._night > self.sleep_seed:
            self.sleep_seed = self._night          # morning seed tracks the night
        if spm >= KACT and WAKE_START <= hh <= MORNING_END and self._night > 0:
            self._night = 0                        # got up -> freeze + clear

        # elevated-HR episode: rising edge opens a new focus; while it stays up we
        # track its peak zone and grow its magnitude (duration + banked movement).
        if zi >= ACTIVE:
            if not self._epi_on:
                self._epi_on = True
                self._epi_idx = self.nepi if self.nepi < EMAX else -1
                if self._epi_idx >= 0:
                    self.epz[self._epi_idx] = zi
                    self.emag[self._epi_idx] = 0
                    self.nepi += 1
            if self._epi_idx >= 0:
                i = self._epi_idx
                if zi > self.epz[i]:
                    self.epz[i] = zi
                self.emag[i] += 1 + idiv(spm, MOM_DIV)
        else:
            self._epi_on = False
            self._epi_idx = -1

    def hr_total(self):
        t = 0
        for z in range(9):
            t += self.zone_min[z]
        return t

    def state_bytes(self):
        # zone_min[9] + EMAX*2 episode Numbers + ~8 scalars, ~5 B each.
        return (9 + EMAX * 2 + 8) * 5


def zone_color(z):
    return HR_RAMP[z] if z >= 0 else None


# The HR zone the day spent the most minutes in, considering only zones >= floor
# (-1 if none). floor=0 is the literal dominant zone; floor=ACTIVE gives the
# dominant ELEVATED zone -- "what kind of exertion characterised the day", which
# is the meaningful, colourful one (the literal dominant is almost always a cool
# rest zone, since most of any day is spent not exercising).
def dominant_zone(rec, floor=0):
    best = -1
    bestn = 0
    for z in range(floor, 9):
        if rec.zone_min[z] > bestn:
            bestn = rec.zone_min[z]
            best = z
    return best


# Build a ZLUT-entry table that maps a uniform draw -> an HR zone weighted by the
# minutes spent in each zone. Built ONCE per frame (not per element): an element's
# colour is then lut[hash & (ZLUT-1)], an O(1) read. This is the LUT discipline
# from docs/watchdog-debugging.md -- a per-element 9-zone scan is the band-scan
# trap that the sandbox proxy cannot see but the wrist feels. Returns None when
# there is no HR history yet (caller falls back to a neutral/cool colour).
def zone_lut(rec, floor=0):
    tot = 0
    for z in range(floor, 9):
        tot += rec.zone_min[z]
    if tot <= 0:
        return None
    account(ZLUT + 9)                     # charge the one-time build to the proxy
    lut = [8] * ZLUT
    for i in range(ZLUT):
        x = idiv(i * tot, ZLUT)
        acc = 0
        for z in range(floor, 9):
            acc += rec.zone_min[z]
            if x < acc:
                lut[i] = z
                break
    return lut


# Scatter placement from a SINGLE hash16: angle from the low 8 bits, radius from
# the high bits with a quadratic centre bias (so the field is dense at the core
# and thins outward). One hash per element instead of three -- hash16 is the
# dominant per-element cost on-device (a real call), so this is the budget lever.
def place(seed, i, k, spread):
    h = hash16(seed, i, k)
    a = h & 0xFF
    if spread <= 0:
        return a, 0, h
    r = imod(h >> 8, spread)
    return a, idiv(r * r, spread), h
