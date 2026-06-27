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

from device import idiv, imod, hash16, account
from daybuckets import hr_zi, HR_RAMP, CX, CY, px, py  # reuse the shared HR ramp

ZLUT = 32              # size of the per-frame zone-colour lookup table

ACTIVE = 4             # zone idx >= this is an elevated-HR minute (HR >= 105)
EMAX = 16             # cap on stored episodes (bright foci)
KACT = 6              # steps/min -> one growth unit (matches BioBloom)
MOM_DIV = 16          # steps/min -> banked-magnitude units during an episode


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
            self.reset()
            self._lastday = day
            self.seed = imod(hash16(day, 17, 3), 4096)

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

        zi = hr_zi(snap.heartRate)
        if zi >= 0:
            self.zone_min[zi] += 1

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


# Build a ZLUT-entry table that maps a uniform draw -> an HR zone weighted by the
# minutes spent in each zone. Built ONCE per frame (not per element): an element's
# colour is then lut[hash & (ZLUT-1)], an O(1) read. This is the LUT discipline
# from docs/watchdog-debugging.md -- a per-element 9-zone scan is the band-scan
# trap that the sandbox proxy cannot see but the wrist feels. Returns None when
# there is no HR history yet (caller falls back to a neutral/cool colour).
def zone_lut(rec):
    tot = rec.hr_total()
    if tot <= 0:
        return None
    account(ZLUT + 9)                     # charge the one-time build to the proxy
    lut = [8] * ZLUT
    for i in range(ZLUT):
        x = idiv(i * tot, ZLUT)
        acc = 0
        for z in range(9):
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
