#!/usr/bin/env python3
"""biobloom_parametric -- biobloom with a PARAMETRIC skeleton.

Same dish as algos/biobloom.py (same blooms, colony, momentum, HR ramp, daily
growth), but each arm is stored as a handful of scalars instead of a cached
vertex list:

    {a0, a, L, next, v, np, rb}      (no per-vertex "pts")

Vertices are regenerated at RENDER time by replaying the wiggle walk from the
seed angle a0, and the arm is coloured from the colony radius-LUT (the same
HR-zone-vs-radius gradient the fur already uses) instead of a per-vertex colour.

Why this is the version that helps the 64 KB ceiling, not just the save blob:
  * the live `_pt` array (KMAX*PMAX = 820 slots, ~4 KB -- the single biggest
    live allocation) disappears. Regeneration streams one arm at a time into a
    PMAX-slot scratch, so we do NOT just relocate _pt into a frame buffer.
  * save()/load() shrink too: arms persist as scalars, no vertex dump.
  * reload is LOSSLESS: the shape is a smooth curve `head(a0, rb, d)` (a per-arm
    curl + one undulation), a pure function of (a0, rb, np), so regenerating gives
    back exactly the live arm. A smooth heading (vs the old per-anchor random walk)
    is also what makes a COARSELY-regenerated arm still look organic instead of
    jaggedly staggered -- coarsening just samples the same curve at fewer points.

Trade vs biobloom.py: skeleton and fur are drawn together per arm (one walk),
so the global skeleton>blooms>fur ink priority becomes blooms>(skeleton+fur).
On a typical day the ink budget is never exhausted, so it renders the same; the
priority only diverges under extreme load, where it just changes what gets shed.
"""
from device import (idiv, imod, isin, hash16, account,
                    COLOR_BLACK, COLOR_DK_GRAY, COLOR_LT_GRAY,
                    COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
                    COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK,
                    COLOR_PURPLE, COLOR_DK_RED)

HR_BOUNDS = [60, 80, 95, 105, 120, 138, 152, 165]
HR_RAMP = [COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
           COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK, COLOR_PURPLE]


def hr_zi(hr):
    if hr is None:
        return -1
    for i in range(len(HR_BOUNDS)):
        if hr < HR_BOUNDS[i]:
            return i
    return len(HR_BOUNDS)


def hr_color(zi):
    return COLOR_DK_GRAY if zi < 0 else HR_RAMP[zi]


CX, CY = 107, 108
R0, RMAX = 7, 86
UNIT = 64
KACT = 6
STEP = 2
KMAX = 20
SEEDS = 9
BMAX = 16
PMAX = 41                 # max vertices an arm regenerates to (R0..RMAX by STEP)
# Arm SHAPE: a smooth per-arm curl (a circular arc, sign+rate from the seed hash)
# plus TWO undulations (a primary swing + a finer detail harmonic) for a tighter,
# more TEXTURED wiggle. A pure function of (a0, rb, along-arm distance d). The
# heading is smooth in d, so coarse regen samples the SAME curve -- it cannot inject
# the jagged wander the old per-anchor AMP*ws random walk did. The frequencies stay
# low enough that the widest stride on a saturated dish samples them without
# aliasing back into jaggedness. Mirrors BioBloom.mc.
CURL_RATE = 15
CURL_VAR = 9
CURL_DIV = 64
UND1_SW = 9
UND1_FR = 4
UND2_SW = 5
UND2_FR = 7


def head(a0, rb, d):
    """Smooth arm heading at along-arm distance d (px). Both undulations zeroed at
    d==0 so the arm leaves the centre radially (at a0) then twists. Mirrors
    BioBloom.mc."""
    h = hash16(a0, rb, 2)
    rate = CURL_RATE + imod(h, CURL_VAR)
    sign = 1 if (h & 1) else -1
    ph = imod(hash16(a0, 7, 3), 256)
    ph2 = imod(hash16(a0, 11, 5), 256)
    u0 = isin(ph)
    u0b = isin(ph2)
    curl = sign * idiv(rate * d, CURL_DIV)
    und = (idiv(UND1_SW * (isin(imod(d * UND1_FR + ph, 256)) - u0), 127)
           + idiv(UND2_SW * (isin(imod(d * UND2_FR + ph2, 256)) - u0b), 127))
    return imod(a0 + curl + und, 256)

ACTIVE = 4
MOM_MODE = "cooldown"
BASE = 2
GROW = 2
REACH_CAP = 46
MOM_DIV = 16
MOM_STEP = 2

CR_MAX = 78
TRAIL = 10
CMOVE_DIV = 20
MOVE_MIN = 2
IDLE_STEPS = 1
BAR_MAX = 60
BAR_ON = 40
BAR_HI = 50
BAR_CLEAR = 4

INK_MAX = 420            # hard backstop on dc primitives/onUpdate. On-device the
                         # render is dominated by per-vertex/per-spine METHOD CALLS
                         # this sandbox's VM proxy does NOT model, so it under-read
                         # the real cost badly. The dish now self-bounds well under
                         # this (coarse anchor arms + capped spines); the backstop
                         # only catches a pathological frame. Mirrors BioBloom.mc.
SK_CAP = 520             # (unused since arms became anchor polylines; kept for refs)
REGEN_CAP = 96            # bound on total arm vertices walked/frame: the regen
                          # stride widens past this so the per-frame hash16/isin
                          # cost can't grow all day and trip the watchdog (the
                          # draw budget INK_MAX never saw it). Mirrors BioBloom.mc.


class BioBloomParam:
    def __init__(self, mom_mode=MOM_MODE, coarse=False):
        self.mom_mode = mom_mode
        self.coarse = coarse              # regenerate at a dish-size-bounded stride
        self._ws = 2                      # current regen walk stride (set in render)
        self.prev = None
        self.win = []
        self.fil = []
        self.blooms = []
        self.epi_on = False
        self.epi_idx = -1
        self.colony = {"reach": R0, "bands": []}
        self.bar = 0
        self.bloom_base = imod(hash16(SEEDS, 17, 3), 256)
        self._col_lut = [COLOR_BLACK] * (CR_MAX + 1)
        for i in range(SEEDS):
            a = imod(idiv(i * 256, SEEDS) + imod(hash16(91, i, 5), 16), 256)
            v = 2 + imod(hash16(7, i, 1), 3)
            self.fil.append({"a0": a, "a": a, "L": R0 * UNIT, "next": R0 + STEP,
                             "v": v, "np": 1, "rb": R0})

    # ---- arm geometry: regenerate vertices from (a0, rb, np) ------------------

    def _arm_vertices(self, f):
        """Sample the smooth heading curve (head) at every vertex. Returns
        [(x, y, rr), ...]. This is the one allocation per arm per frame -- a
        PMAX-slot scratch in the .mc, reused across arms (NOT a persistent cache)."""
        a0 = f["a0"]
        rb, np = f["rb"], f["np"]
        if self.coarse:
            return self._arm_vertices_coarse(a0, rb, np)
        pts = []
        for k in range(np):
            rr = rb + k * STEP
            a = head(a0, rb, k * STEP)
            pts.append((CX + idiv(rr * isin(a + 64), 127),
                        CY + idiv(rr * isin(a), 127), rr))
        return pts

    def _arm_vertices_coarse(self, a0, rb, np):
        """Emit ONLY the strided anchors (k = 0, ws, 2*ws, ... + the tip), sampling
        the SAME smooth heading curve as the fine version -- NO per-vertex fill, and
        coarsening cannot change the shape (it just samples fewer points on the same
        curve). Mirrors BioBloom.mc regenArm(): per-anchor method-call work (NOT
        modelled by this sandbox's VM proxy) was ~90% of the real on-device frame;
        emitting only anchors cuts it, and the smooth curve made it both prettier and
        cheaper (no per-anchor hash16). self._ws widens with dish size to bound it."""
        ws = self._ws
        pts = []
        k = 0
        while k < np:
            rr = rb + k * STEP
            a = head(a0, rb, k * STEP)
            pts.append((CX + idiv(rr * isin(a + 64), 127),
                        CY + idiv(rr * isin(a), 127), rr))
            k += ws
        if k - ws != np - 1:                      # ensure the tip is the last anchor
            rr = rb + (np - 1) * STEP
            a = head(a0, rb, (np - 1) * STEP)
            pts.append((CX + idiv(rr * isin(a + 64), 127),
                        CY + idiv(rr * isin(a), 127), rr))
        return pts

    def _tip(self, f):
        """Arm tip (x, y) -- the heading curve evaluated at the tip distance. Anchors
        blooms exactly where the rendered skeleton reaches (was f['pts'][-1])."""
        rb, np = f["rb"], f["np"]
        rr = rb + (np - 1) * STEP
        a = head(f["a0"], rb, (np - 1) * STEP)
        return CX + idiv(rr * isin(a + 64), 127), CY + idiv(rr * isin(a), 127)

    def _longish(self, salt):
        order = sorted(range(len(self.fil)),
                       key=lambda j: self.fil[j]["L"], reverse=True)
        k = imod(hash16(salt, len(self.blooms) + 1, 13), max(1, len(order) // 2))
        return self.fil[order[k]]

    def _nearest(self, target):
        best, bd = self.fil[0], 999
        for f in self.fil:
            d = imod(f["a"] - target + 128, 256) - 128
            if d < 0:
                d = -d
            if d < bd:
                bd, best = d, f
        return best

    def _grow_fil(self, f, move):
        f["L"] += idiv(move * f["v"], 3)
        if f["L"] > RMAX * UNIT:
            f["L"] = RMAX * UNIT
        while idiv(f["L"], UNIT) >= f["next"] and f["next"] <= RMAX:
            f["np"] += 1
            f["next"] += STEP
        # _tha is the heading at the current TIP (so blooms/branches/nearest use the
        # point the skeleton actually reaches). The shape is a pure function of d.
        f["a"] = head(f["a0"], f["rb"], (f["np"] - 1) * STEP)

    # ---- per-minute simulation (identical to biobloom.py except _grow_fil) -----

    def advance(self, snap):
        steps = snap.steps or 0
        if self.prev is None:
            self.prev = steps
        spm = steps - self.prev
        if spm < 0:
            spm = 0
        self.prev = steps

        hr = snap.heartRate
        zi = hr_zi(hr)
        cur = hr if hr is not None else 0
        self.win.append(cur)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)
        rising = len(self.win) >= 6 and cur - self.win[0] >= 8

        move = idiv(spm, KACT)

        if move > 0:
            nf = len(self.fil)
            i = 0
            while i < nf:
                self._grow_fil(self.fil[i], move)
                i += 1
            if rising and len(self.fil) < KMAX:
                src = self._longish(steps)
                na = imod(src["a"] + 10 + imod(hash16(steps, nf, 9), 22), 256)
                rr = idiv(src["L"], UNIT)
                v = 2 + imod(hash16(steps, nf, 4), 3)
                self.fil.append({"a0": na, "a": na, "L": rr * UNIT,
                                 "next": rr + STEP, "v": v, "np": 1, "rb": rr})

        fed = -1
        if zi >= ACTIVE:
            if not self.epi_on:
                self.epi_on = True
                self.epi_idx = self._seed(zi)
            if self.epi_idx >= 0:
                b = self.blooms[self.epi_idx]
                w = 3 + idiv(vrange, 8)
                if w > 16:
                    w = 16
                if w > b["w"]:
                    b["w"] = w
                self._band(b, hr_color(zi), GROW)
                if zi > b["hot"]:
                    b["hot"] = zi
                b["mc"] = 0
                b["lastzi"] = zi
                b["mom"] += idiv(spm, MOM_DIV)
                if b["mom"] > REACH_CAP:
                    b["mom"] = REACH_CAP
                b["mom0"] = b["mom"]
                fed = self.epi_idx
        else:
            self.epi_on = False
            self.epi_idx = -1

        self._momentum(fed)
        self._grow_colony(spm, zi)

    def _grow_colony(self, spm, zi):
        col = self.colony
        if spm <= IDLE_STEPS:
            self.bar += 1
            if self.bar > BAR_MAX:
                self.bar = BAR_MAX
        elif spm >= KACT:
            self.bar -= BAR_CLEAR
            if self.bar < 0:
                self.bar = 0
        if spm < MOVE_MIN:
            return
        front = 0
        for f in self.fil:
            l = idiv(f["L"], UNIT)
            if l > front:
                front = l
        front -= TRAIL
        target = col["reach"] + idiv(spm, CMOVE_DIV)
        if target > front:
            target = front
        if target > CR_MAX:
            target = CR_MAX
        if target <= col["reach"]:
            return
        if self.bar >= BAR_ON:
            c = COLOR_DK_GRAY if self.bar >= BAR_HI else COLOR_LT_GRAY
        else:
            c = hr_color(zi)
        col["bands"].append((col["reach"], target, c))
        col["reach"] = target

    def _seed(self, zi):
        if len(self.blooms) >= BMAX:
            return -1
        target = imod(self.bloom_base + len(self.blooms) * 98
                      + imod(hash16(zi, len(self.blooms), 7), 22), 256)
        f = self._nearest(target)
        bx, by = self._tip(f)
        salt = imod(hash16(bx, by, zi), 4096)
        self.blooms.append({"bx": bx, "by": by, "ang": f["a"], "reach": BASE,
                            "w": 3, "bands": [], "salt": salt, "mom": 0,
                            "hot": zi, "mc": 0, "lastzi": zi, "mom0": 0})
        return len(self.blooms) - 1

    def _band(self, b, color, grow):
        r0 = b["reach"]
        r1 = r0 + grow
        if r1 > REACH_CAP:
            r1 = REACH_CAP
        if r1 > r0:
            b["bands"].append((r0, r1, color))
            b["reach"] = r1

    def _mom_color(self, b):
        if self.mom_mode == "cooldown":
            m0 = b["mom0"]
            if m0 <= 0:
                return hr_color(b["lastzi"])
            ci = idiv(b["lastzi"] * b["mom"], m0)
            if ci < 0:
                ci = 0
            if ci > b["lastzi"]:
                ci = b["lastzi"]
            return hr_color(ci)
        return b["bands"][-1][2]

    def _momentum(self, fed):
        i = 0
        while i < len(self.blooms):
            b = self.blooms[i]
            if i != fed and b["mom"] > 0 and b["reach"] < REACH_CAP and b["bands"]:
                g = MOM_STEP
                if g > b["mom"]:
                    g = b["mom"]
                self._band(b, self._mom_color(b), g)
                b["mom"] -= g
                b["mc"] += 1
            i += 1

    # ---- render ---------------------------------------------------------------

    def render(self, dc, snap):
        self._ink = INK_MAX
        if self.colony["bands"]:
            self._fill_lut(self.colony["bands"], CR_MAX, self._col_lut)
        self._draw_arms(dc)                       # skeleton + fur, per arm
        for b in self.blooms:                     # HR-zone blooms (priority kept)
            if self._ink <= 0:
                break
            self._draw_bloom(dc, b)

    def _col_at(self, rr):
        return self._col_lut[rr if rr <= CR_MAX else CR_MAX]

    def _draw_arms(self, dc):
        # Each arm = its coarse anchor polyline + a little per-anchor fur. `ws` is
        # sized from the dish so total anchors stay ~REGEN_CAP, bounding cost.
        totv = 0
        for f in self.fil:
            totv += f["np"]
        self._ws = 2
        if totv > REGEN_CAP:
            self._ws = idiv(totv, REGEN_CAP) + 1
        have_col = bool(self.colony["bands"])
        reach = self.colony["reach"]
        for f in self.fil:
            if f["np"] < 1:
                continue
            pts = self._arm_vertices(f)
            for j in range(1, len(pts)):          # skeleton: anchor to anchor
                if self._ink <= 0:
                    return
                x0, y0, _ = pts[j - 1]
                x1, y1, rr = pts[j]
                dc.setColor(self._col_at(rr) if have_col else COLOR_DK_GRAY,
                            COLOR_BLACK)
                dc.drawLine(x0, y0, x1, y1)
                self._ink -= 1
            if not have_col:
                continue
            lim = idiv(f["L"], UNIT) - TRAIL
            if lim > reach:
                lim = reach
            if lim <= R0:
                continue
            a = f["a"]
            for j in range(1, len(pts)):          # fur: a spine at each anchor
                x, y, rr = pts[j]
                if rr > lim:
                    break                         # anchors are radius-ordered
                if self._ink <= 0:
                    return
                dc.setColor(self._col_at(rr), COLOR_BLACK)
                a2 = imod(a + j * 37, 256)
                le = 3 + imod(j, 4)
                dc.drawLine(x, y, x + idiv(le * isin(a2 + 64), 127),
                            y + idiv(le * isin(a2), 127))
                self._ink -= 1

    def _fill_lut(self, bands, rmax, lut):
        n = len(bands)
        account(rmax + 1 + n)
        bi = 0
        r = 0
        while r <= rmax:
            while bi < n and bands[bi][1] < r:
                bi += 1
            lut[r] = bands[bi][2] if bi < n else bands[n - 1][2]
            r += 1

    def _draw_bloom(self, dc, b):
        if not b["bands"]:
            return
        # ONE colour for the whole bloom: the hottest HR-zone band it reached (the
        # episode's peak). Mirrors BioBloom.mc -- a per-radius colour LUT was built
        # for every bloom every frame, and on the saturated dish that LUT fill was
        # exactly where the watchdog tripped (reproduced in the sim). The bloom's
        # position, size and peak-zone colour are the HR-episode data that matter;
        # the within-bloom cooldown gradient was fine detail. setColor once.
        hot, hot_color = -1, COLOR_DK_GRAY
        for (_r0, _r1, c) in b["bands"]:
            if c in HR_RAMP:
                zi = HR_RAMP.index(c)
                if zi > hot:
                    hot, hot_color = zi, c
        ang, reach, w, salt = b["ang"], b["reach"], b["w"], b["salt"]
        bx, by = b["bx"], b["by"]
        nsp = 4 + imod(hash16(salt, 1, 1), 4)
        dc.setColor(hot_color, COLOR_BLACK)
        dc.fillCircle(bx, by, 1 + idiv(w, 8))
        # Each spine = one straight line from the anchor (1 hash16 + 2 isin + 1 draw).
        for k in range(nsp):
            if self._ink <= 0:
                return
            h1 = hash16(salt, k, 4)
            off = imod(h1, 121) - 60
            lf = 90 + imod(idiv(h1, 121), 166)
            a2 = imod(ang + off, 256)
            tip = BASE + idiv((reach - BASE) * lf, 256)
            ex = bx + idiv(tip * isin(a2 + 64), 127)
            ey = by + idiv(tip * isin(a2), 127)
            dc.drawLine(bx, by, ex, ey)
            self._ink -= 1

    def state_bytes(self):
        # Live RAM proxy. The PARAMETRIC win: arms are 7 scalars each (no vertex
        # list) + ONE PMAX-slot regen scratch, vs the ship's per-vertex _pt.
        return (len(self.fil) * 7 * 5            # 7 Number scalars/arm (~5 B each)
                + PMAX * 5                        # single reused regen scratch
                + sum(len(b["bands"]) for b in self.blooms) * 6
                + len(self.blooms) * 8
                + len(self.colony["bands"]) * 6)


def build():
    return {"background": COLOR_BLACK, "components": [BioBloomParam(MOM_MODE)]}
