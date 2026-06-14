#!/usr/bin/env python3
"""Hybrid B+C -- "biobloom": a filament skeleton (B) that only extends when you
move, with LIVING blooms (C) that erupt on it during elevated-HR episodes and
record the effort as zone-coloured bands as they grow outward.

  threads          = grow from centre, length ONLY advances with movement, so a
                     lazy day stays short and an active day reaches outward
  per-thread vigor = some threads outpace others => irregular, uneven envelope
  segment colour   = HR zone that minute               (flag D5)
  branching        = HR trend rising => reaching out    (flag D6)
  wander amplitude = HR variability                     (flag D7)
  frozen threads   = idle / no steps (move-bar)         (flag 9 / D12)
  BLOOM            = ANY elevated-HR episode (zone >= ACTIVE) erupts on an arm
                     and grows outward one zone-coloured band per minute while
                     HR stays elevated (initial growth -- pure HR, banded by
                     zone). Meanwhile it banks a MOMENTUM reservoir from the
                     movement effort (steps) during those minutes. When HR
                     drops the initial growth stops, but momentum growth creeps
                     on for as long as that reservoir lasts. So an exercise
                     event (elevated HR + movement) keeps growing into a large
                     colony, while an anxiety/excitement event (elevated HR,
                     little movement) banks almost no momentum and stays a
                     small node -- same colour, very different size.

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

ACTIVE = 3          # zone idx >= ACTIVE is an elevated-HR minute (HR >= 105)
BASE = 2            # px a bloom starts out from its anchor
GROW = 2            # px the frontier advances per elevated minute (one band)
REACH_CAP = 46      # px a bloom can reach outward along its arm
MOM_DIV = 16        # steps/min -> momentum reservoir units (movement effort)
MOM_STEP = 2        # px of momentum growth delivered per minute after HR drops


class BioBloom:
    def __init__(self):
        self.prev = None
        self.win = []
        self.fil = []
        self.blooms = []
        self.epi_on = False
        self.epi_idx = -1            # index of the in-progress episode's bloom
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

        # ---- elevated-HR episode -> a bloom that grows one zone-band per minute
        fed = -1
        if zi >= ACTIVE:
            if not self.epi_on:
                self.epi_on = True
                self.epi_idx = self._seed(zi)        # erupt on the first minute
            b = self.blooms[self.epi_idx]
            w = 3 + idiv(vrange, 8)                   # variability => wider bloom
            if w > 16:
                w = 16
            if w > b["w"]:
                b["w"] = w
            self._band(b, ZONE_COLORS[zi], GROW)      # initial growth, zone colour
            b["mom"] += idiv(spm, MOM_DIV)            # bank movement effort
            if b["mom"] > REACH_CAP:
                b["mom"] = REACH_CAP
            fed = self.epi_idx
        else:
            self.epi_on = False
            self.epi_idx = -1

        self._momentum(fed)

    def _seed(self, zi):
        # spread headings by ~137.5 deg (golden angle = 98/256) per bloom, plus
        # jitter, so successive eruptions fan out around the dish
        target = imod(self.bloom_base + len(self.blooms) * 98
                      + imod(hash16(zi, len(self.blooms), 7), 22), 256)
        f = self._nearest(target)
        bx, by, _ = f["pts"][-1]
        self.blooms.append({"bx": bx, "by": by, "ang": f["a"], "reach": BASE,
                            "w": 3, "bands": [],
                            "salt": imod(hash16(bx, by, zi), 4096),
                            "mom": 0})
        return len(self.blooms) - 1

    def _band(self, b, color, grow):
        # append one outward band, capped at the reach ceiling
        r0 = b["reach"]
        r1 = r0 + grow
        if r1 > REACH_CAP:
            r1 = REACH_CAP
        if r1 > r0:
            b["bands"].append((r0, r1, color))
            b["reach"] = r1

    def _momentum(self, fed):
        # blooms not growing from HR this minute spend their banked movement
        # effort to creep on in the last zone's colour, until the reservoir runs
        # out -- exercise (lots of movement) keeps growing, anxiety does not
        i = 0
        while i < len(self.blooms):
            b = self.blooms[i]
            if i != fed and b["mom"] > 0 and b["reach"] < REACH_CAP and b["bands"]:
                g = MOM_STEP
                if g > b["mom"]:
                    g = b["mom"]
                self._band(b, b["bands"][-1][2], g)
                b["mom"] -= g
            i += 1

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

    def _band_color(self, b, r):
        # colour of the band covering radius r (the zone active when the
        # frontier reached there)
        for band in b["bands"]:
            if r <= band[1]:
                return band[2]
        return b["bands"][-1][2]

    def _draw_bloom(self, dc, b):
        if not b["bands"]:
            return
        ang = b["ang"]
        fx, fy = isin(ang + 64), isin(ang)        # outward unit (cos, sin)*127
        px, py = isin(ang + 128), isin(ang + 64)  # perpendicular unit
        reach, w, salt = b["reach"], b["w"], b["salt"]

        # a chain of sub-lobes marching outward and shrinking -> rough, lumpy
        # frontier; each lobe is coloured by the zone band at its radius, so the
        # colony reads banded from base to rim
        nlob = 2 + imod(hash16(salt, 0, 5), 3)    # 2..4 lobes
        n = reach * 2 + w * 5
        if n > 150:
            n = 150
        per = idiv(n, nlob)
        if per < 4:
            per = 4
        j = 0
        while j < nlob:
            lf = idiv((j + 1) * 230, nlob + 1) + imod(hash16(salt, j, 6), 26)
            along = idiv(reach * lf, 256)
            po = imod(hash16(salt, j, 7), 2 * w + 1) - w     # perp wobble
            lx = b["bx"] + idiv(along * fx, 127) + idiv(po * px, 127)
            ly = b["by"] + idiv(along * fy, 127) + idiv(po * py, 127)
            lr = 2 + idiv(w * (nlob - j), nlob)              # outer lobes smaller
            dc.setColor(self._band_color(b, along), COLOR_BLACK)
            k = 0
            while k < per:
                s = j * 97 + k
                rr = imod(hash16(salt, s, 1), lr + 1)
                a2 = imod(hash16(salt, s, 2), 256)
                x = lx + idiv(rr * isin(a2 + 64), 127)
                y = ly + idiv(rr * isin(a2), 127)
                dc.fillCircle(x, y, 1)
                k += 1
            j += 1

    def state_bytes(self):
        return (sum(len(f["pts"]) for f in self.fil) * 3
                + sum(len(b["bands"]) for b in self.blooms) * 6
                + len(self.blooms) * 8)


def build():
    return {"background": COLOR_BLACK, "components": [BioBloom()]}
