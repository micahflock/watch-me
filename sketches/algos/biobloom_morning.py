#!/usr/bin/env python3
"""biobloom_morning -- biobloom with a SLEEP-SEEDED morning colony.

Same dish as biobloom.py, but it does NOT wake up empty. The watch face resets
the dish at midnight; by the time you actually look at it in the morning (few
steps yet), the centre is filled by a small starting colony whose SIZE and
COLOUR encode last night's sleep. The arms seeded at the centre are tinted by
that same sleep reading instead of the old flat grey, so a quiet morning reads
as a small, calm, coloured bud rather than empty space + grey twigs.

Data note (fr735xt / CIQ 2.4): there is NO sleep API at this level. "Last
night's sleep" is INFERRED on-device as overnight quiescence -- a rest meter
that ticks up each night-hour minute with no step advance and a resting HR --
persisted across the midnight reset via BioState (the same getProperty path the
dish already uses) and topped up by the early-morning quiet minutes before you
wake. In this sandbox that single number is the `sleep_h` knob so we can compare
looks; the inference is an implementation detail to settle once a look is picked.

SEED_STYLE picks the morning treatment (all sleep-coloured):
  "rings"   -- concentric tree-rings, one ring per ~hour slept, cool(rested)
               core out to warm(short) -- quantity reads as BOTH size and how
               far up the restful ramp it climbs
  "rosette" -- a small floret: a filled core with a ring of short petals,
               petal count and radius growing with sleep
  "spores"  -- a little scatter colony of seed nodes, count growing with sleep,
               deeper near the centre (reads as "a small colony")
  "bud"     -- understated: one soft sleep-coloured node + halo, arms tinted

Hybrid B+C -- "biobloom": a filament skeleton (B) that only extends when you
move, with LIVING blooms (C) that erupt on it during elevated-HR episodes and
record the effort as zone-coloured bands as they grow outward.

  threads          = grow from centre, length ONLY advances with movement, so a
                     lazy day stays short and an active day reaches outward
  per-thread vigor = some threads outpace others => irregular, uneven envelope
  segment colour   = HR zone that minute               (flag D5)
  branching        = HR trend rising => reaching out    (flag D6)
  wander amplitude = HR variability                     (flag D7)
  frozen threads   = idle / no steps (move-bar)         (flag 9 / D12)
  MAIN COLONY      = a mass at the centre that grows ALL DAY but only while
                     moving, trailing the skeleton (the arms grow first, it
                     fills in behind them) and clinging to it -- stippled along
                     the arms, not concentric, so it stays amorphous. Its final
                     size tracks the day's overall movement; each band is
                     coloured by the HR zone during the movement that grew it,
                     EXCEPT bands grown while the inactivity meter is up, which
                     are grey / dark grey.
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
from device import (idiv, imod, isin, hash16, account,
                    COLOR_BLACK, COLOR_DK_GRAY, COLOR_LT_GRAY,
                    COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
                    COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK,
                    COLOR_PURPLE, COLOR_DK_RED)

# ---- finer HR ramp (biobloom-local) ----------------------------------------
# The shared GenArt.ZONE_COLORS is a 7-step ramp used by strata/flock; biobloom
# carries its own 9-step ramp so elevated HR reads with more granularity without
# touching the other faces. Cool -> hot: blue family for rest, green for easy,
# then a warm run yellow -> orange -> red -> pink -> purple for the hard end, so
# the 105-135 band (which used to all be one green) now spreads across several
# colours. hr_zi(None) == -1 (never elevated; drawn dark grey).
HR_BOUNDS = [60, 80, 95, 105, 120, 138, 152, 165]
HR_RAMP = [COLOR_DK_BLUE, COLOR_BLUE, COLOR_DK_GREEN, COLOR_GREEN,
           COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PINK, COLOR_PURPLE]


def hr_zi(hr):
    if hr is None:
        return -1
    for i in range(len(HR_BOUNDS)):
        if hr < HR_BOUNDS[i]:
            return i
    return len(HR_BOUNDS)            # 8 == PURPLE (HR >= 165)


def hr_color(zi):
    return COLOR_DK_GRAY if zi < 0 else HR_RAMP[zi]


# ---- sleep ramp (last night's sleep -> colour) -----------------------------
# Cool = well rested, warm = short night. Index by hours slept (clamped). The
# seed styles read a SLICE of this ramp from the centre outward, so a longer
# night both reaches a deeper-rest colour AND grows physically larger -- the
# quantity is legible two ways at once. DK tints are the dim, "still asleep"
# versions used to colour the seeded skeleton instead of the old flat grey.
SLEEP_RAMP = [COLOR_DK_RED, COLOR_RED, COLOR_ORANGE, COLOR_YELLOW,
              COLOR_DK_GREEN, COLOR_GREEN, COLOR_BLUE, COLOR_DK_BLUE]
#               <=3h         4h         5h           6h
#               7h           8h         9h           >=10h  (one step per hour)
# dim tints: a dark member of the same warm/cool family as the ramp slot, never
# grey (grey morning twigs are the exact thing we're replacing).
SLEEP_DIM = [COLOR_DK_RED, COLOR_DK_RED, COLOR_DK_RED, COLOR_DK_RED,
             COLOR_DK_GREEN, COLOR_DK_GREEN, COLOR_DK_BLUE, COLOR_DK_BLUE]


def sleep_idx(sleep_h):
    i = sleep_h - 3
    if i < 0:
        i = 0
    if i > len(SLEEP_RAMP) - 1:
        i = len(SLEEP_RAMP) - 1
    return i


def sleep_color(sleep_h):
    return SLEEP_RAMP[sleep_idx(sleep_h)]


def sleep_dim(sleep_h):
    return SLEEP_DIM[sleep_idx(sleep_h)]


# Seed-colony geometry. Kept deliberately SMALL (the user wants a small colony,
# not a full dish) -- the day's activity still grows the real colony out past it.
SEED_STYLE = "spores"  # rings | rosette | spores | bud
SEED_R0 = 6            # core radius at the shortest night
SEED_PER_H = 2         # +px of seed reach per hour slept
SEED_RMAX = 30         # the morning bud never exceeds this (stays "small")

CX, CY = 107, 108     # centre at 2/5 of the screen height up from the bottom
R0, RMAX = 7, 86
UNIT = 64
KACT = 6            # movement -> growth (smaller => threads grow faster)
STEP = 2            # px of radius per appended vertex
KMAX = 22           # cap on live filaments
SEEDS = 9           # initial threads, spread evenly around the centre
BMAX = 16           # cap on live blooms (parity with BioBloom.mc)

ACTIVE = 4          # zone idx >= ACTIVE is an elevated-HR minute (HR >= 105)

# How banked-movement "momentum" creep (the growth that continues after HR has
# dropped) is coloured. The HR-driven bands are always the zone ramp; this only
# governs the after-glow tail. Options compared in the sandbox:
#   "inherit"  -- reuse the last HR-zone colour (original behaviour)
#   "ember"    -- cool the tail hot -> dark-red -> dark-grey (spent fuel / ash)
#   "violet"   -- a single dedicated PURPLE, a bold banked-effort halo
#   "neutral"  -- a quiet light-grey, so the bright HR bands pop
#   "cooldown" -- start at the last HR colour, then cool back DOWN the HR ramp
#                 (orange -> yellow -> green -> blue) to resting as the banked
#                 reservoir is spent: the recovery told as a colour gradient
MOM_MODE = "cooldown"
BASE = 2            # px a bloom starts out from its anchor
GROW = 2            # px the frontier advances per elevated minute (one band)
REACH_CAP = 46      # px a bloom can reach outward along its arm
MOM_DIV = 16        # steps/min -> momentum reservoir units (movement effort)
MOM_STEP = 2        # px of momentum growth delivered per minute after HR drops

# the main colony at the centre -- grows all day, only while moving, banded by
# HR zone (grey while the inactivity meter is up), clinging to the skeleton and
# trailing behind its arms
CR_MAX = 78         # main-colony reach ceiling (px from centre)
TRAIL = 10          # px the colony stays behind the longest arm tip
CMOVE_DIV = 20      # steps/min -> colony reach growth (px)
CW = 3              # colony thickness scattered around each arm
MOVE_MIN = 2        # steps/min below which the colony does not grow at all
IDLE_STEPS = 1      # spm <= this is an idle minute (move-bar fills)
BAR_MAX = 60        # inactivity meter ceiling (~minutes)
BAR_ON = 40         # meter at/above this is "on" -> growth bands go grey
BAR_HI = 50         # deeper inactivity -> dark grey instead of light grey
BAR_CLEAR = 4       # solid movement works the meter back down per minute
                    # (slow, so the onset of activity after a long idle -- e.g.
                    # the first run minutes out of sleep -- grows grey first)

# Per-frame draw budget shared across ALL passes (skeleton, blooms, fur) so the
# whole onUpdate is bounded regardless of how big the dish grows -- the watchdog
# (~25-30k VM instr) is the binding constraint and a very active day can grow
# 22 long arms. INK_MAX caps the total; SK_CAP additionally DECIMATES the
# skeleton (draw every Nth vertex) once it exceeds that many segments, so all
# arms still appear (just slightly coarser) instead of the skeleton eating the
# whole budget. A typical day stays under both, so it renders identically.
INK_MAX = 700       # total primitives per onUpdate (watchdog backstop, see .mc)
SK_CAP = 520        # decimate the skeleton above this many segments


class BioBloom:
    def __init__(self, mom_mode=MOM_MODE, seed_style=SEED_STYLE, sleep_h=7):
        self.mom_mode = mom_mode
        self.seed_style = seed_style
        self.sleep_h = sleep_h
        self.prev = None
        self.win = []
        self.fil = []
        self.blooms = []
        self.epi_on = False
        self.epi_idx = -1            # index of the in-progress episode's bloom
        self.colony = {"reach": R0, "bands": []}   # central main colony
        self.bar = 0                 # inactivity meter (Garmin-style move bar)
        self.bloom_base = imod(hash16(SEEDS, 17, 3), 256)   # per-day phase
        # Per-frame radius->colour lookup tables (allocated ONCE; refilled each
        # render). They turn the band-colour query from an O(bands) scan -- which
        # grew all day toward the 96-band cap and tripped the watchdog -- into an
        # O(1) array read, so render cost no longer grows with the day's length.
        self._col_lut = [COLOR_BLACK] * (CR_MAX + 1)
        self._bl_lut = [COLOR_BLACK] * (REACH_CAP + 1)
        # Seed the skeleton's first vertex with a DIM sleep tint instead of the
        # flat grey -- so a barely-grown morning arm reads as a calm coloured
        # twig, not a dead grey one.
        seed_tint = sleep_dim(self.sleep_h)
        for i in range(SEEDS):
            a = imod(idiv(i * 256, SEEDS) + imod(hash16(91, i, 5), 16), 256)
            v = 2 + imod(hash16(7, i, 1), 3)
            self.fil.append({"a": a, "L": R0 * UNIT, "next": R0 + STEP, "v": v,
                             "pts": [self._pt(a, R0, seed_tint)]})
        # The starting colony from last night's sleep (size + colour). reach is
        # how far the bud fills from centre; rings remembers the per-hour ramp
        # slices so "rings"/"rosette" can draw a cool->warm gradient outward.
        self.seed_reach = SEED_R0 + SEED_PER_H * self.sleep_h
        if self.seed_reach > SEED_RMAX:
            self.seed_reach = SEED_RMAX
        self.seed_si = sleep_idx(self.sleep_h)         # ramp slot for this night

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
        zi = hr_zi(hr)
        cur = hr if hr is not None else 0
        self.win.append(cur)
        if len(self.win) > 10:
            self.win.pop(0)
        vrange = max(self.win) - min(self.win)
        rising = len(self.win) >= 6 and cur - self.win[0] >= 8

        move = idiv(spm, KACT)
        color = COLOR_DK_GRAY if spm <= 1 else hr_color(zi)

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
            if self.epi_idx >= 0:                    # -1 once BMAX blooms exist
                b = self.blooms[self.epi_idx]
                w = 3 + idiv(vrange, 8)               # variability => wider bloom
                if w > 16:
                    w = 16
                if w > b["w"]:
                    b["w"] = w
                self._band(b, hr_color(zi), GROW)     # initial growth, zone colour
                if zi > b["hot"]:
                    b["hot"] = zi                     # peak zone, for ember tail
                b["mc"] = 0                           # reset ember tail on re-feed
                b["lastzi"] = zi                      # tail starts from this zone
                b["mom"] += idiv(spm, MOM_DIV)        # bank movement effort
                if b["mom"] > REACH_CAP:
                    b["mom"] = REACH_CAP
                b["mom0"] = b["mom"]                  # reservoir at HR-drop, cooldown
                fed = self.epi_idx
        else:
            self.epi_on = False
            self.epi_idx = -1

        self._momentum(fed)
        self._grow_colony(spm, zi)

    def _grow_colony(self, spm, zi):
        # the main colony trails the skeleton (which already grew this minute),
        # advances only while moving, and is banded by the HR zone at the time
        # -- or grey/dark grey if it grows while the inactivity meter is up
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
            return                                    # only grows when moving
        front = 0
        for f in self.fil:
            l = idiv(f["L"], UNIT)
            if l > front:
                front = l
        front -= TRAIL                                # stay behind the longest arm
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
        # spread headings by ~137.5 deg (golden angle = 98/256) per bloom, plus
        # jitter, so successive eruptions fan out around the dish
        if len(self.blooms) >= BMAX:
            return -1                                # at cap: episode grows nothing
        target = imod(self.bloom_base + len(self.blooms) * 98
                      + imod(hash16(zi, len(self.blooms), 7), 22), 256)
        f = self._nearest(target)
        bx, by, _ = f["pts"][-1]
        salt = imod(hash16(bx, by, zi), 4096)
        self.blooms.append({"bx": bx, "by": by, "ang": f["a"], "reach": BASE,
                            "w": 3, "bands": [], "salt": salt, "mom": 0,
                            "hot": zi, "mc": 0, "lastzi": zi, "mom0": 0})
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

    def _mom_color(self, b):
        # colour of a momentum (post-HR) creep band, per self.mom_mode
        if self.mom_mode == "violet":
            return COLOR_PURPLE
        if self.mom_mode == "neutral":
            return COLOR_LT_GRAY
        if self.mom_mode == "ember":
            # cool the tail as the reservoir is spent: a couple of bands in the
            # peak HR colour, then dark red, then dark grey ash
            if b["mc"] < 2:
                return hr_color(b["hot"])
            if b["mc"] < 4:
                return COLOR_DK_RED
            return COLOR_DK_GRAY
        if self.mom_mode == "cooldown":
            # start at the last HR colour and cool back DOWN the ramp toward
            # resting (idx 0) in proportion to how much reservoir is left, so
            # the recovery reads as a colour gradient regardless of tail length
            m0 = b["mom0"]
            if m0 <= 0:
                return hr_color(b["lastzi"])
            ci = idiv(b["lastzi"] * b["mom"], m0)
            if ci < 0:
                ci = 0
            if ci > b["lastzi"]:
                ci = b["lastzi"]
            return hr_color(ci)
        return b["bands"][-1][2]                       # "inherit"

    def _momentum(self, fed):
        # blooms not growing from HR this minute spend their banked movement
        # effort to creep on, until the reservoir runs out -- exercise (lots of
        # movement) keeps growing, anxiety does not. The creep colour is the
        # after-glow tail governed by self.mom_mode.
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

    def render(self, dc, snap):
        # Priority order under one shared budget: structure (skeleton) first, then
        # the HR-zone blooms, then the decorative fur (shed first under load).
        self._ink = INK_MAX
        self._draw_seed(dc)                       # last night's sleep bud (under)
        self._draw_skeleton(dc)                   # skeleton arms (structural)
        for b in self.blooms:                     # HR-zone blooms (priority)
            if self._ink <= 0:
                break
            self._draw_bloom(dc, b)
        self._draw_fur(dc)                        # colony fur (detail; shed first)

    def _draw_skeleton(self, dc):
        # Draw every arm, but DECIMATE (draw every `stride`-th vertex) once the
        # skeleton is abnormally large, so a 22-arm dish can't outrun the budget.
        # The tip of each arm is always drawn so it reaches its true length.
        tot = 0
        for f in self.fil:
            n = len(f["pts"])
            if n > 1:
                tot += n - 1
        stride = 1
        if tot > SK_CAP:
            stride = idiv(tot, SK_CAP) + 1
        for f in self.fil:
            pts = f["pts"]
            n = len(pts)
            if n < 2:
                continue
            prev = 0
            k = stride
            while k < n:
                if self._ink <= 0:
                    return
                x0, y0, _ = pts[prev]
                x1, y1, c = pts[k]
                dc.setColor(c, COLOR_BLACK)
                dc.drawLine(x0, y0, x1, y1)
                self._ink -= 1
                prev = k
                k += stride
            if prev != n - 1:                     # always close to the arm tip
                if self._ink <= 0:
                    return
                x0, y0, _ = pts[prev]
                x1, y1, c = pts[n - 1]
                dc.setColor(c, COLOR_BLACK)
                dc.drawLine(x0, y0, x1, y1)
                self._ink -= 1

    def _draw_seed(self, dc):
        # Last night's sleep, drawn UNDER the live dish so the day's growth
        # overgrows it. Size + colour both encode hours slept. Cheap: a handful
        # of primitives, no per-day accretion -- a fixed morning cost.
        reach = self.seed_reach
        si = self.seed_si
        style = self.seed_style
        if style == "rings":
            # concentric tree-rings: centre = the night's rest colour, each ring
            # outward steps DOWN the ramp toward the short-night warm end. More
            # sleep -> more rings AND a deeper-rest core.
            rings = si + 2
            k = rings
            while k >= 1:                          # outer first (painter's)
                r = idiv(reach * k, rings)
                ci = si - (rings - k)
                if ci < 0:
                    ci = 0
                dc.setColor(SLEEP_RAMP[ci], COLOR_BLACK)
                dc.fillCircle(CX, CY, r)
                k -= 1
        elif style == "rosette":
            # a small floret: filled core in the night's colour, ringed by short
            # petals; petal count + reach grow with sleep.
            dc.setColor(sleep_color(self.sleep_h), COLOR_BLACK)
            dc.fillCircle(CX, CY, idiv(reach, 2))
            npet = 5 + self.sleep_h
            dim = sleep_dim(self.sleep_h)
            k = 0
            while k < npet:
                a = imod(idiv(k * 256, npet) + imod(hash16(91, k, 5), 12), 256)
                rin = idiv(reach, 2)
                rout = reach
                dc.setColor(dim if (k & 1) else sleep_color(self.sleep_h),
                            COLOR_BLACK)
                dc.drawLine(CX + idiv(rin * isin(a + 64), 127),
                            CY + idiv(rin * isin(a), 127),
                            CX + idiv(rout * isin(a + 64), 127),
                            CY + idiv(rout * isin(a), 127))
                k += 1
        elif style == "spores":
            # a little scatter colony -- a dense clump of cells packed around the
            # centre, more of them the longer the night, deepest-rest colour in
            # the middle and cooling out one ramp step toward the rim. Radius is
            # weighted INWARD (two hashes, min) so it reads as a colony blob, not
            # a sparse sprinkle, and a filled core anchors the middle.
            dc.setColor(SLEEP_RAMP[si], COLOR_BLACK)
            dc.fillCircle(CX, CY, 3)                   # anchor core
            nodes = 7 + self.sleep_h * 3
            k = 0
            while k < nodes:
                a = imod(idiv(k * 256, nodes) + imod(hash16(91, k, 6), 36), 256)
                r1 = imod(hash16(73, k, 2), reach)
                r2 = imod(hash16(29, k, 4), reach)
                rr = 2 + (r1 if r1 < r2 else r2)       # bias toward the centre
                x = CX + idiv(rr * isin(a + 64), 127)
                y = CY + idiv(rr * isin(a), 127)
                ci = si if rr < idiv(reach * 2, 3) else (si - 1 if si >= 1 else 0)
                dc.setColor(SLEEP_RAMP[ci], COLOR_BLACK)
                dc.fillCircle(x, y, 1 + imod(hash16(7, k, 3), 3))
                k += 1
        else:  # "bud" -- understated: halo + node
            dc.setColor(sleep_dim(self.sleep_h), COLOR_BLACK)
            dc.fillCircle(CX, CY, reach)
            dc.setColor(sleep_color(self.sleep_h), COLOR_BLACK)
            dc.fillCircle(CX, CY, idiv(reach, 2))

    def _draw_fur(self, dc):
        # a short outward "fur" of zone-coloured spines stippled along the arms
        # out to where the colony has filled -- drawn last so the ink budget
        # sheds fur, not blooms, under extreme load
        col = self.colony
        if not col["bands"]:
            return
        self._fill_lut(col["bands"], CR_MAX, self._col_lut)   # O(1) lookups below
        reach = col["reach"]
        for f in self.fil:
            lim = idiv(f["L"], UNIT) - TRAIL
            if lim > reach:
                lim = reach
            if lim <= R0:
                continue
            pts, a = f["pts"], f["a"]
            k = 2
            while k < len(pts):
                if self._ink <= 0:
                    return
                rr = R0 + k * STEP
                if rr > lim:
                    break
                if imod(k, 3) == 0:
                    x, y, _ = pts[k]
                    dc.setColor(self._col_lut[rr if rr <= CR_MAX else CR_MAX],
                                COLOR_BLACK)
                    a2 = imod(a + k * 13, 256)
                    le = 3 + imod(k, 4)            # 3..6 px
                    dc.drawLine(x, y, x + idiv(le * isin(a2 + 64), 127),
                                y + idiv(le * isin(a2), 127))
                    self._ink -= 1
                k += 1

    def _fill_lut(self, bands, rmax, lut):
        # lut[r] = colour of the band covering radius r, for r in 0..rmax. Bands
        # are sorted ascending by their outer radius (appended as the frontier
        # advances), so one monotonic sweep fills the whole table. O(bands+rmax).
        n = len(bands)
        account(rmax + 1 + n)        # charge the sweep (sandbox proxy; no .mc line)
        bi = 0
        r = 0
        while r <= rmax:
            while bi < n and bands[bi][1] < r:
                bi += 1
            lut[r] = bands[bi][2] if bi < n else bands[n - 1][2]
            r += 1

    def _draw_bloom(self, dc, b):
        # a burst of bowed, sometimes-forking spines fired outward along the arm,
        # each coloured by the HR-zone band at its tip; the fan is precomputed
        # (b["spikes"]) and just scaled by reach as the bloom grows
        if not b["bands"]:
            return
        self._fill_lut(b["bands"], REACH_CAP, self._bl_lut)   # O(1) lookups below
        ang, reach, w, salt = b["ang"], b["reach"], b["w"], b["salt"]
        bx, by = b["bx"], b["by"]
        nsp = 6 + imod(hash16(salt, 1, 1), 6)     # 6..11 spines
        dc.setColor(self._bl_lut[BASE], COLOR_BLACK)
        dc.fillCircle(bx, by, 1 + idiv(w, 8))     # tiny anchor node (1..3px)
        for k in range(nsp):
            if self._ink <= 0:
                return
            off = imod(hash16(salt, k, 4), 121) - 60   # +-60/256 ~ +-84 deg
            lf = 90 + imod(hash16(salt, k, 5), 166)    # 90..255 of reach
            bow = imod(hash16(salt, k, 7), 13) - 6     # -6..6 px sideways
            fork = imod(hash16(salt, k, 6), 2) == 0    # ~half branch
            a2 = imod(ang + off, 256)
            dx, dy = isin(a2 + 64), isin(a2)
            px, py = isin(a2 + 128), isin(a2 + 64)         # perpendicular (bow)
            tip = BASE + idiv((reach - BASE) * lf, 256)
            mr = idiv(tip, 2)
            mx = bx + idiv(mr * dx, 127) + idiv(bow * px, 127)
            my = by + idiv(mr * dy, 127) + idiv(bow * py, 127)
            ex = bx + idiv(tip * dx, 127)
            ey = by + idiv(tip * dy, 127)
            dc.setColor(self._bl_lut[tip if tip <= REACH_CAP else REACH_CAP],
                        COLOR_BLACK)
            dc.drawLine(bx, by, mx, my)                    # bowed spine, 2 segs
            dc.drawLine(mx, my, ex, ey)
            self._ink -= 2
            if fork:                                       # branch at the elbow
                a3 = imod(a2 + (24 if (off & 1) == 0 else -24), 256)
                fr = idiv(tip, 3)
                dc.drawLine(mx, my, mx + idiv(fr * isin(a3 + 64), 127),
                            my + idiv(fr * isin(a3), 127))
                self._ink -= 1

    def state_bytes(self):
        return (sum(len(f["pts"]) for f in self.fil) * 3
                + sum(len(b["bands"]) for b in self.blooms) * 6
                + len(self.blooms) * 8
                + len(self.colony["bands"]) * 6)


def build():
    return {"background": COLOR_BLACK,
            "components": [BioBloom(MOM_MODE, SEED_STYLE, 7)]}
