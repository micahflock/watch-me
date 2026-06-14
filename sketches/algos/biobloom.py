#!/usr/bin/env python3
"""Hybrid B+C -- "biobloom": a filament skeleton (B) that only extends when you
move, with LIVING colony blooms (C) that erupt on it at hard-effort episodes
and then creep outward along their arm.

  threads          = grow from centre, length ONLY advances with movement, so a
                     lazy day stays short and an active day reaches outward
  per-thread vigor = some threads outpace others => irregular, uneven envelope
  segment colour   = HR zone that minute               (flag D5)
  branching        = HR trend rising => reaching out    (flag D6)
  wander amplitude = HR variability                     (flag D7)
  frozen threads   = idle / no steps (move-bar)         (flag 9 / D12)
  COLONY BLOOM     = a sustained hard-effort episode (HR in a high zone for
                     >= MINLEN min) plants a colony on a thread that then
                     CREEPS OUTWARD along that arm -- fast while the effort
                     continues, tapering after it ends -- as a teardrop lobe
                     pointing at the rim, coloured by the episode's peak zone.

Activity-driven: the day's shape is the day's exertion. 14-colour palette, one
repaint per minute, no within-minute animation. Daily reset (fresh dish).
"""
from device import (idiv, imod, isin, hash16, zoneIndex, ZONE_COLORS,
                    COLOR_BLACK, COLOR_DK_GRAY)

CX, CY = 107, 90
R0, RMAX = 7, 86
UNIT = 64
KACT = 6            # movement -> growth (smaller => threads grow faster)
STEP = 2            # px of radius per appended vertex
KMAX = 22           # cap on live filaments
SEEDS = 9           # initial threads, spread evenly around the centre

HARD = 4            # zone idx >= HARD is a hard-effort minute (HR >= 125)
MINLEN = 5          # min hard minutes before a colony takes hold
ENERGY_FEED = 48    # creep energy topped up each minute the effort continues
CREEP_DIV = 16      # reach gain per minute = energy / CREEP_DIV
REACH_CAP = 34      # px a colony can creep outward along its arm


class BioBloom:
    def __init__(self):
        self.prev = None
        self.win = []
        self.fil = []
        self.blooms = []
        self.epi_on = False
        self.epi_min = 0
        self.epi_peak = 0
        self.epi_idx = -1            # index of this episode's bloom, or -1
        self.bloom_base = imod(hash16(SEEDS, 17, 3), 256)   # per-day phase
        for i in range(SEEDS):
            a = imod(idiv(i * 256, SEEDS) + imod(hash16(91, i, 5), 16), 256)
            v = 2 + imod(hash16(7, i, 1), 3)
            self.fil.append({"a": a, "L": R0 * UNIT, "next": R0 + STEP, "v": v,
                             "pts": [self._pt(a, R0, COLOR_DK_GRAY)]})

    def _pt(self, a, r, c):
        x = CX + idiv(r * isin(a + 64), 127)
        y = CY + idiv(r * isin(a), 127)
        return (x, y, c)

    def _longish(self, salt):
        # pick one of the longer arms (varied) -- used for thread branching
        order = sorted(range(len(self.fil)),
                       key=lambda j: self.fil[j]["L"], reverse=True)
        k = imod(hash16(salt, len(self.blooms) + 1, 13), max(1, len(order) // 2))
        return self.fil[order[k]]

    def _nearest(self, target):
        # arm whose heading is closest to a target angle, so successive blooms
        # erupt in genuinely different directions around the dish
        best, bd = self.fil[0], 999
        for f in self.fil:
            d = imod(f["a"] - target + 128, 256) - 128
            if d < 0:
                d = -d
            if d < bd:
                bd, best = d, f
        return best

    def _grow_fil(self, f, move, vrange, color):
        f["L"] += idiv(move * f["v"], 3)
        if f["L"] > RMAX * UNIT:
            f["L"] = RMAX * UNIT
        amp = 1 + idiv(vrange, 10)
        while idiv(f["L"], UNIT) >= f["next"] and f["next"] <= RMAX:
            rr = f["next"]
            da = idiv(isin(hash16(f["a"], rr, 1) & 255) * amp, 127)
            f["a"] = imod(f["a"] + da, 256)
            f["pts"].append(self._pt(f["a"], rr, color))
            f["next"] += STEP

    def advance(self, snap):
        steps = snap.steps or 0
        if self.prev is None:
            self.prev = steps
        spm = steps - self.prev
        if spm < 0:
            spm = 0
        self.prev = steps

        hr = snap.heartRate
        zi = zoneIndex(hr)
        cur = hr if hr is not None else 0
        self.win.append(cur)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)
        rising = len(self.win) >= 6 and cur - self.win[0] >= 8

        move = idiv(spm, KACT)
        color = COLOR_DK_GRAY if spm <= 1 else ZONE_COLORS[zi]

        if move > 0:
            nf = len(self.fil)
            i = 0
            while i < nf:
                self._grow_fil(self.fil[i], move, vrange, color)
                i += 1
            if rising and len(self.fil) < KMAX:
                src = self._longish(steps)
                na = imod(src["a"] + 10 + imod(hash16(steps, nf, 9), 22), 256)
                rr = idiv(src["L"], UNIT)
                v = 2 + imod(hash16(steps, nf, 4), 3)
                self.fil.append({"a": na, "L": rr * UNIT, "next": rr + STEP,
                                 "v": v, "pts": [self._pt(na, rr, color)]})

        # ---- hard-effort episode -> living colony bloom ----
        if zi >= HARD:
            if not self.epi_on:
                self.epi_on = True
                self.epi_min = 0
                self.epi_peak = zi
                self.epi_idx = -1
            self.epi_min += 1
            if zi > self.epi_peak:
                self.epi_peak = zi
            if self.epi_min == MINLEN:
                self.epi_idx = self._plant(vrange)
            if self.epi_idx >= 0:
                b = self.blooms[self.epi_idx]
                b["energy"] = ENERGY_FEED            # keep feeding while working
                b["color"] = ZONE_COLORS[self.epi_peak]
        else:
            self.epi_on = False
            self.epi_idx = -1

        self._creep()

    def _plant(self, vrange):
        # spread headings by ~137.5 deg (golden angle = 98/256) per bloom, plus
        # jitter, so the run / gym / etc. colonies fan out around the dish
        target = imod(self.bloom_base + len(self.blooms) * 98
                      + imod(hash16(self.epi_peak, len(self.blooms), 7), 22), 256)
        f = self._nearest(target)
        bx, by, _ = f["pts"][-1]
        self.blooms.append({"bx": bx, "by": by, "ang": f["a"], "reach": 3,
                            "w": 4 + idiv(vrange, 6),
                            "color": ZONE_COLORS[self.epi_peak],
                            "salt": imod(hash16(bx, by, self.epi_peak), 4096),
                            "energy": ENERGY_FEED})
        return len(self.blooms) - 1

    def _creep(self):
        for b in self.blooms:
            if b["energy"] > 0:
                b["reach"] += idiv(b["energy"], CREEP_DIV)
                if b["reach"] > REACH_CAP:
                    b["reach"] = REACH_CAP
                b["energy"] = idiv(b["energy"] * 7, 8)   # taper after episode

    def render(self, dc, snap):
        dc.setColor(COLOR_DK_GRAY, COLOR_BLACK)
        dc.fillCircle(CX, CY, 2)                  # visible seed at the centre
        for f in self.fil:
            pts = f["pts"]
            k = 1
            while k < len(pts):
                x0, y0, _ = pts[k - 1]
                x1, y1, c = pts[k]
                dc.setColor(c, COLOR_BLACK)
                dc.drawLine(x0, y0, x1, y1)
                k += 1
        for b in self.blooms:
            self._draw_bloom(dc, b)

    def _draw_bloom(self, dc, b):
        dc.setColor(b["color"], COLOR_BLACK)
        ang = b["ang"]
        fx, fy = isin(ang + 64), isin(ang)        # outward unit (cos, sin)*127
        px, py = isin(ang + 128), isin(ang + 64)  # perpendicular unit
        reach, w, salt = b["reach"], b["w"], b["salt"]

        # a chain of sub-lobes marching outward and shrinking -> rough, lumpy
        # frontier rather than a smooth teardrop
        nlob = 2 + imod(hash16(salt, 0, 5), 3)    # 2..4 lobes
        lob = []
        j = 0
        while j < nlob:
            lf = idiv((j + 1) * 230, nlob + 1) + imod(hash16(salt, j, 6), 26)
            along = idiv(reach * lf, 256)
            po = imod(hash16(salt, j, 7), 2 * w + 1) - w     # perp wobble
            lx = b["bx"] + idiv(along * fx, 127) + idiv(po * px, 127)
            ly = b["by"] + idiv(along * fy, 127) + idiv(po * py, 127)
            lr = 2 + idiv(w * (nlob - j), nlob)              # outer lobes smaller
            lob.append((lx, ly, lr))
            j += 1

        n = reach * 2 + w * 5
        if n > 150:
            n = 150
        k = 0
        while k < n:
            lx, ly, lr = lob[imod(hash16(salt, k, 3), nlob)]
            rr = imod(hash16(salt, k, 1), lr + 1)
            a2 = imod(hash16(salt, k, 2), 256)
            x = lx + idiv(rr * isin(a2 + 64), 127)
            y = ly + idiv(rr * isin(a2), 127)
            dc.fillCircle(x, y, 1)
            k += 1

    def state_bytes(self):
        return sum(len(f["pts"]) for f in self.fil) * 3 + len(self.blooms) * 12


def build():
    return {"background": COLOR_BLACK, "components": [BioBloom()]}
