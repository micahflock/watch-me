#!/usr/bin/env python3
"""strataflock — the shipped face, ported into the sandbox as the PARITY
REFERENCE. Every line is a mechanical translation of core/src/genart/
StrataField.mc + Flock.mc: Gfx.* -> device constants, `a / b` -> idiv(a, b),
`a % b` -> imod/Python % (operands here are non-negative hashes). If the
sandbox ever stops looking like strataflock-ondevice.png, the mirror has
drifted from the watch and device.py is the thing to fix.

Algorithm contract (what scrub.py expects from an algo module):
    build() -> {"background": <color>, "components": [c0, c1, ...]}
Each component is duck-typed exactly like a Compositor component:
    .render(dc, state)            required — draw the frame
    .advance(state)    optional   — evolve persistent state (once per minute)
    .state_bytes()     optional   — persistent RAM proxy for the budget readout
scrub.py replays the day minute by minute (advance every minute, render at the
sample minutes) so stateful engines build up exactly as they do on-device.
"""

from device import (
    hash16, isin, zoneIndex, idiv, ZONE_COLORS,
    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
    COLOR_BLUE, COLOR_DK_BLUE, COLOR_TRANSPARENT,
)


class StrataField:
    """Port of StrataField.mc — the day as sediment strata (the past layer)."""

    NCOLS = 54
    COLW = 4
    MAXB = 14
    HMAX = 132
    SCRH = 180
    REPOSE = 5

    def __init__(self):
        self._hts = [0] * self.NCOLS
        self._bcnt = [0] * self.NCOLS
        self._bands = [0] * (self.NCOLS * self.MAXB)
        self._daySeed = 1
        self.reset()

    def reset(self):
        for i in range(self.NCOLS):
            self._hts[i] = 0
            self._bcnt[i] = 0
        self._cursor = 4
        self._wob = 0
        self._lastMin = -1
        self._lastSteps = None
        self._lastDay = -1
        self._mov256 = 0
        self._unrest256 = 0

    def daySeed(self):
        return self._daySeed

    def mov256(self):
        return self._mov256

    def unrest256(self):
        return self._unrest256

    def heightAtX(self, x):
        c = idiv(x, self.COLW)
        if c < 0:
            c = 0
        if c > self.NCOLS - 1:
            c = self.NCOLS - 1
        return self._hts[c]

    def advance(self, state):
        if state.hour is None or state.minute is None:
            return
        now = state.hour * 60 + state.minute
        day = state.day if state.day is not None else 0
        if day != self._lastDay or now < self._lastMin:
            self.reset()                       # first tick ever, or midnight
            self._lastDay = day
            self._lastMin = now - 1
            y = state.year if state.year is not None else 0
            mo = state.month if state.month is not None else 0
            self._daySeed = ((y % 100) * 372 + mo * 31 + day) & 0x3FFF
        d = now - self._lastMin
        if d <= 0:
            return

        steps = state.steps
        sd = 0
        if steps is not None and self._lastSteps is not None and steps > self._lastSteps:
            sd = steps - self._lastSteps
        spm = idiv(sd, d)
        self._mov256 = idiv(spm * 256, 130)
        if self._mov256 > 256:
            self._mov256 = 256

        self._unrest256 = self._unrest256 - idiv(self._unrest256 * d, 60)
        if self._unrest256 < 0:
            self._unrest256 = 0
        if self._mov256 > self._unrest256:
            self._unrest256 = self._mov256

        zi = zoneIndex(state.heartRate)
        g = 1 + idiv(spm, 35)
        if g > 6:
            g = 6
        spread = 2 + idiv(self._mov256 * 10, 256)

        iters = 12 if d > 12 else d
        for k in range(iters):
            tt = now - iters + 1 + k
            self._wob += (hash16(self._daySeed, tt, 5) % 3) - 1
            if self._wob > 6:
                self._wob = 6
            if self._wob < -6:
                self._wob = -6
            self._cursor = 4 + idiv(tt * (self.NCOLS - 8), 1440) + self._wob
            if self._cursor < 2:
                self._cursor = 2
            if self._cursor > self.NCOLS - 3:
                self._cursor = self.NCOLS - 3
            if sd == 0 and (tt & 3) != 0:
                continue                       # idle drips slowly
            for gi in range(g):
                off = (hash16(self._daySeed + tt, gi, 1) % spread) \
                    + (hash16(self._daySeed + tt, gi, 2) % spread) \
                    - spread + 1
                self.deposit(self._cursor + off, zi)
        self._lastMin = now
        if steps is not None:
            self._lastSteps = steps

    def deposit(self, col, zi):
        if col < 0:
            col = 0
        if col > self.NCOLS - 1:
            col = self.NCOLS - 1
        for _ in range(8):
            lo = col
            if col > 0 and self._hts[col - 1] < self._hts[col] - self.REPOSE:
                lo = col - 1
            if col < self.NCOLS - 1 and self._hts[col + 1] < self._hts[lo] - self.REPOSE:
                lo = col + 1
            if lo == col:
                break
            col = lo
        if self._hts[col] >= self.HMAX:
            return
        self._hts[col] += 1
        n = self._bcnt[col]
        base = col * self.MAXB
        if n > 0 and (self._bands[base + n - 1] >> 12) == zi:
            self._bands[base + n - 1] += 1     # extend same-zone band
        elif n < self.MAXB:
            self._bands[base + n] = (zi << 12) | 1
            self._bcnt[col] = n + 1
        else:
            self._bands[base + n - 1] += 1     # cap hit: thicken the crust

    def render(self, dc, state):
        for i in range(self.NCOLS):
            n = self._bcnt[i]
            if n == 0:
                continue
            x = i * self.COLW
            y = self.SCRH
            base = i * self.MAXB
            for j in range(n):
                e = self._bands[base + j]
                length = e & 0xFFF
                y -= length
                dc.setColor(ZONE_COLORS[e >> 12], COLOR_TRANSPARENT)
                dc.fillRectangle(x, y, self.COLW, length)
            dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
            dc.fillRectangle(x, y - 1, self.COLW, 1)          # crust line
        dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
        dc.fillRectangle(self._cursor * self.COLW + 1,
                         self.SCRH - self._hts[self._cursor] - 3, 2, 2)

    def state_bytes(self):
        # RAM proxy: heights + band counts (1 B each) + packed bands in use
        # (2 B each). Mirrors the README's "strata RLE ~900 B" figure.
        used = sum(self._bcnt)
        return self.NCOLS * 2 + used * 2


class Flock:
    """Port of Flock.mc — the murmuration in the sky (the present layer)."""

    GX = 12
    GY = 9
    X0 = 14
    SX = 17
    Y0 = 16
    SY = 16

    def __init__(self, field, keep):
        self._field = field
        self._keep = keep
        n = self.GX * self.GY
        self._px = [0] * n
        self._py = [0] * n
        self._viz = [False] * n

    def render(self, dc, state):
        t = 0
        if state.hour is not None and state.minute is not None:
            t = state.hour * 60 + state.minute
        seed = self._field.daySeed()
        hr = state.heartRate if state.heartRate is not None else 55
        steps = state.steps if state.steps is not None else 0

        hrn256 = idiv((hr - 50) * 256, 110)
        if hrn256 < 0:
            hrn256 = 0
        if hrn256 > 256:
            hrn256 = 256

        eff = self._field.mov256()
        ur = idiv(self._field.unrest256() * 3, 5)
        if ur > eff:
            eff = ur
        amp16 = 32 + idiv(144 * eff, 256)

        f1 = 2 + (hash16(seed, 1, 0) % 3)
        f2 = 3 + (hash16(seed, 2, 0) % 3)
        ax = 107 + idiv(62 * isin(hash16(seed, 3, 0) + idiv(t * f1 * 256, 1560)), 127)
        ay = 28 + idiv(34 * isin(hash16(seed, 4, 0) + idiv(t * f2 * 256, 2400)), 127)

        cs = 9000 if steps > 9000 else steps
        thresh = 100 + idiv(924 * cs, 9000)

        n = self.GX * self.GY
        for i in range(n):
            self._viz[i] = False
            if (hash16(seed, i, 313) & 1023) >= thresh:
                continue
            ix = i % self.GX
            iy = idiv(i, self.GX)
            w = 2 * isin(ix * 37 + idiv(t * 53, 10)) + isin(iy * 69 + idiv(t * 29, 10))
            x = self.X0 + ix * self.SX + idiv(amp16 * w, 6096)
            w = 2 * isin(iy * 45 + idiv(t * 45, 10) + 81) + isin(ix * 53 + t * 2)
            y = self.Y0 + iy * self.SY + idiv(amp16 * w, 6096)

            surf = 180 - self._field.heightAtX(x)
            if y > surf - 3:
                if y < surf + 6:               # grazing: settles into the crust
                    dc.setColor(COLOR_LT_GRAY, COLOR_TRANSPARENT)
                    dc.fillRectangle(x, surf - 2, 1, 1)
                continue                       # deeper: buried, not drawn
            if self._keep is not None and x > self._keep[0] and x < self._keep[2] \
                    and y < self._keep[3]:
                continue                       # the clock displaces the flock
            self._px[i] = x
            self._py[i] = y
            self._viz[i] = True

        dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
        for i in range(n):
            if not self._viz[i]:
                continue
            if (i % self.GX) < self.GX - 1 and self._viz[i + 1]:
                self.filament(dc, i, i + 1)
            if i + self.GX < n and self._viz[i + self.GX]:
                self.filament(dc, i, i + self.GX)

        for i in range(n):
            if not self._viz[i]:
                continue
            x = self._px[i]
            y = self._py[i]
            adx = x - ax
            if adx < 0:
                adx = -adx
            ady = y - ay
            if ady < 0:
                ady = -ady
            dist = adx + idiv(ady * 2, 5) if adx > ady else ady + idiv(adx * 2, 5)
            base16 = 96 - idiv(dist * 16, 14)
            if base16 < 0:
                base16 = 0
            pulse16 = idiv(hrn256 * isin(t * 14 + ((i % self.GX) + idiv(i, self.GX)) * 41), 1016)
            grain = 128 + (hash16(seed, i, 47) & 255)
            rad16 = idiv((idiv(base16 * (128 + hrn256), 256) + 14 + pulse16) * grain, 256)
            if rad16 > 96:
                rad16 = 96
            if rad16 > 58:
                col = ZONE_COLORS[zoneIndex(state.heartRate)]
            elif rad16 > 35:
                col = COLOR_BLUE if hrn256 > 90 else COLOR_DK_BLUE
            elif rad16 > 19:
                col = COLOR_DK_BLUE
            else:
                col = COLOR_DK_GRAY
            dc.setColor(col, COLOR_TRANSPARENT)
            r = idiv(rad16, 16)
            if r < 1:
                dc.fillRectangle(x, y, 1, 1)
            else:
                dc.fillCircle(x, y, r)

    def filament(self, dc, i, j):
        dx = self._px[i] - self._px[j]
        dy = self._py[i] - self._py[j]
        if dx * dx + dy * dy < 169:            # within 13 px
            dc.drawLine(self._px[i], self._py[i], self._px[j], self._py[j])


def build():
    field = StrataField()
    # Clock keep-out, approximated (the real face derives it from the segment
    # font width; ~70 px wide, top 46 px). The flock avoids this hole.
    keep = [107 - 35, 0, 107 + 35, 46]
    return {"background": COLOR_BLACK, "components": [field, Flock(field, keep)]}
