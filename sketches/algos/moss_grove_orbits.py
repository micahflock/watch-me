"""moss_grove_orbits -- bead-overlap PROPOSAL: more orbits, over the sleep.

2026-07-18 wrist: the golden fruit ring reads better than the huddled
tufts, but TWO interleaved orbits (50%/72% of rim) is too few -- a busy day
still lands several beads on each orbit. And the exact keep-out kept every
bead OUTSIDE the root star, wasting the whole inner disc.

TREATMENT (episodes block only; module-level K sweeps the orbit count):
  * K radius bands spanning ORBIT_LO..ORBIT_HI % of the rim (was the two
    fixed 50/72 bands). More bands -> fewer beads share a radius -> the
    golden angles separate them further.
  * NO keep-out floor: inner orbits are ALLOWED over the root star (owner,
    2026-07-18). The star is still drawn LAST, so it rides on top of any
    bead it overlaps -- the sleep read is preserved, the inner disc is used.
  * The podetium stalk is now unreachable (a bead at <= ORBIT_HI% of the
    rim can never float past it) and drops out.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, place, dominant_zone, ZLUT, ACTIVE
from daybuckets import px, py
from mossutil import edge, shape_params
from device import (idiv, imod, hash16, isin, account,
                    COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW, COLOR_WHITE,
                    COLOR_LT_GRAY, COLOR_DK_GRAY, COLOR_BLUE, COLOR_DK_BLUE)

CX = 107
CY = 108               # 2/5 of the 180px height up from the bottom (BioBloom centre)
INK = 260              # was 340 pre-LUT: rebalanced with the grain/texture caps
                       # below so a saturated day draws every layer (incl. the
                       # beads, which the old budget starved) and the release
                       # frame clears the sim watchdog with margin
NA = 30                # rim samples for the cushion fans
BASE_DIV = 60          # act_units -> cushion radius
TUFT_DIV = 600         # act_units -> one more satellite tuft
SCN = 5                # overall size scale = SCN/SCD (= 1.25x), applied to every
SCD = 4                # radial extent: cushion, lumpiness, tufts, beads (the
                       # root star works in final px directly, like the beads)
AMPREF = 40            # base radius (px, scaled) at which outline amps reach 100%

K = 4                  # number of interleaved bead orbits (SWEEP knob)
ORBIT_LO = 34          # innermost orbit, % of rim (over the root star)
ORBIT_HI = 86          # outermost orbit, % of rim (on the dark mound)


def scl(v):
    return idiv(v * SCN, SCD)


# rounded division, symmetric in sign: plain truncation shaves ~30% off the
# stalk flare on diagonal runs (both perpendicular components round toward
# zero). Ports as (abs + d/2) / d with the sign re-applied.
def rdiv(v, d):
    av = v if v >= 0 else -v
    q = idiv(av + idiv(d, 2), d)
    return q if v >= 0 else -q


ROOT_MAX_H = 10        # SLEEP_CAP is 600 min


def root_hours(mins):
    h = idiv(mins, 60)
    if h < 1:
        h = 1
    if h > ROOT_MAX_H:
        h = ROOT_MAX_H
    return h


def root_len(mins):
    return 8 + 3 * root_hours(mins)


class MossGroveOrbits:
    def __init__(self):
        self.rec = DS.DayRecord()
        # per-frame outline LUT (render scratch, allocated once): edge radius
        # and outer-fan vertex offsets at the NA rim angles. See render().
        self.er = [0] * NA
        self.vx = [0] * NA
        self.vy = [0] * NA

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    # last night's sleep: the silver root star under the heart of the moss.
    # wakes = wake-up events 12-6am: each one snaps a root at a white speck
    # (the literal count), kinks every root harder, and grays the tips.
    # Lengths/radii are FINAL px (already scaled), like the episode beads.
    #
    # The star does NOT compete for the shared ink budget: a saturated day
    # spends all 340 ink on tufts/texture/beads and the clump this replaced
    # silently vanished by mid-afternoon -- but the night must stay readable
    # on the heaviest day (it is the layer drawn last precisely to stay on
    # top). Its cost is hard-capped instead: nroots <= 16 and wakes clamped
    # to nroots bound it at ~80 primitives.
    def draw_sleep(self, dc, mins, wakes, ink):
        if mins <= 0:
            return ink
        hours = root_hours(mins)
        ln = root_len(mins)
        nroots = 6 + hours
        if wakes > nroots:             # can't snap more roots than exist
            wakes = nroots
        kink = 3 + wakes * 6           # angle jitter at the joints (1/256ths)

        # each wake snaps one root (evenly spread, distinct while wakes <=
        # nroots); precomputed as a bitmask -- the per-root scan was
        # O(nroots*wakes) divisions for a value that never changes in-frame
        snapmask = 0
        for w in range(wakes):
            snapmask |= 1 << idiv(w * nroots, wakes)

        # taproot crown grounding the star
        dc.setColor(COLOR_DK_BLUE, COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, 3)

        for i in range(nroots):
            h = hash16(87, i, 6)
            a = imod(idiv(i * 256, nroots) + (h % 15), 256)
            li = ln - imod(h >> 8, idiv(ln, 3) + 1)    # per-root length variety
            # joint angles wander +-kink; negatives are fine (isin masks & 255,
            # identically in Monkey C)
            a1 = a + imod(hash16(87, i, 7), 2 * kink + 1) - kink
            a2 = a1 + imod(hash16(87, i, 8), 2 * kink + 1) - kink
            rm = idiv(li * 3, 5)
            x0 = px(CX, 2, a)
            y0 = py(CY, 2, a)
            xm = px(CX, rm, a1)
            ym = py(CY, rm, a1)
            # a snapped root ends at its joint under the white speck
            snapped = ((snapmask >> i) & 1) != 0
            dc.setColor(COLOR_DK_GRAY if snapped else COLOR_LT_GRAY,
                        COLOR_TRANSPARENT)
            dc.drawLine(x0, y0, xm, ym)
            if snapped:
                # ship-style blight speck at the break: white core in a thick
                # black ring, a couple of ragged blobs on its edge
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillCircle(xm, ym, 5)
                for k in range(2):
                    hb = hash16(i + 41, k, 8)
                    ba = idiv(k * 256, 2) + (hb % 40)
                    dc.fillCircle(xm + idiv(6 * isin(ba + 64), 127),
                                  ym + idiv(6 * isin(ba), 127), 1)
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(xm, ym, 2)
            else:
                xt = px(CX, li, a2)
                yt = py(CY, li, a2)
                dc.drawLine(xm, ym, xt, yt)
                # nodule tip: deep blue when rested, gray on a rough night
                dc.setColor(COLOR_BLUE if wakes == 0 else COLOR_DK_GRAY,
                            COLOR_TRANSPARENT)
                dc.fillCircle(xt, yt, 1)
        return ink

    # fill the lumpy disc as a fan of NA triangles from the cached outline
    # offsets, scaled scalepct/100 (100 = the dark mound, 60 = the crown) --
    # no edge()/isin per vertex; see the LUT note in render()
    def fan_lut(self, dc, scalepct):
        tri = [(CX, CY), (0, 0), (0, 0)]   # apex is loop-invariant (mc: _tri)
        x0 = CX + idiv(self.vx[0] * scalepct, 100)
        y0 = CY + idiv(self.vy[0] * scalepct, 100)
        for i in range(1, NA + 1):
            j = imod(i, NA)
            x1 = CX + idiv(self.vx[j] * scalepct, 100)
            y1 = CY + idiv(self.vy[j] * scalepct, 100)
            tri[1] = (x0, y0)
            tri[2] = (x1, y1)
            dc.fillPolygon(tri)
            x0 = x1
            y0 = y1

    # one colony tuft: solid blob + stipple; grains glow `accent` (dominant zone)
    def draw_tuft(self, dc, seed, j, tx, ty, tsize, accent, ink):
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        dc.fillCircle(tx, ty, idiv(tsize, 2))
        ink -= 1
        # grain cap 26 -> 16 (watchdog): 7 tufts x 26 grains was the single
        # heaviest layer at saturation (each grain = hash16 + 2 isin + 2 Dc
        # calls); 16 keeps the stipple read at ~2/3 the op count
        grains = 8 + idiv(tsize, 2)
        if grains > 16:
            grains = 16
        for i in range(grains):
            if ink <= 0:
                break
            a2, rr2, h = place(seed, j * 64 + i, 3, tsize)
            gx = tx + idiv(rr2 * isin(a2 + 64), 127)
            gy = ty + idiv(rr2 * isin(a2), 127)
            col = COLOR_GREEN if (h & 1) else COLOR_DK_GREEN
            if accent is not None and ((h >> 6) & 3) != 0:
                col = accent                   # most grains glow the exertion colour
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(gx, gy, 1)
            ink -= 1
        return ink

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        dz = dominant_zone(rec, ACTIVE)        # the day's exertion colour
        if dz < 0:
            dz = dominant_zone(rec)
        dzcol = zone_color(dz) if dz >= 0 else None
        act = rec.act_units

        base = 4 + idiv(act, BASE_DIV)
        if base > 54:
            base = 54
        base = scl(base)                       # 1.25x overall scale

        sp = shape_params(seed)                # per-day lumpy outline
        # scale the lumpiness amplitudes with the overall size AND with the
        # cushion base (min(1, base/AMPREF)): absolute amps on a small
        # sedentary-day base turned the patch into an angular starfish
        # (2026-07-10 wrist). Per-lobe percents (sp[8]) are ratios; unscaled.
        s = 100 if base >= AMPREF else idiv(100 * base, AMPREF)
        sp = (sp[0], sp[1], sp[2], sp[3],
              idiv(scl(sp[4]) * s, 100), idiv(scl(sp[5]) * s, 100),
              sp[6], idiv(scl(sp[7]) * s, 100), sp[8])
        ntuft = idiv(act, TUFT_DIV)
        if ntuft > 7:
            ntuft = 7
        tsize = 10 + idiv(act, 240)
        if tsize > 23:
            tsize = 23
        tsize = scl(tsize)

        # --- per-frame outline LUT + outer-fan vertex offsets ---
        # edge() costs ~3 isin + per-lobe arithmetic PER CALL and used to be
        # re-evaluated ~240x a frame (both fan passes, every texture dot, the
        # fringe, tufts, beads) -- exactly the per-element method cost the
        # sandbox proxy under-counts (docs/watchdog-debugging.md); the
        # saturated release frame tripped the sim watchdog. Sample the
        # outline ONCE at the NA rim angles; every other consumer reads the
        # LUT (nearest sample -- the outline is smooth, so off-grid consumers
        # only see px-level shifts). vx/vy are the 100% fan vertex offsets,
        # making both fan passes isin-free (the crown is the same offsets
        # scaled 60%).
        for i in range(NA):
            ai = imod(idiv(i * 256, NA), 256)
            e = edge(base, ai, sp)
            self.er[i] = e
            self.vx[i] = idiv(e * isin(ai + 64), 127)
            self.vy[i] = idiv(e * isin(ai), 127)
        account(NA * 2)                    # LUT stores (the isin/edge work is
                                           # already counted per call)

        # --- central cushion: dark mound + bright green crown ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 100)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 60)

        # --- satellite tufts straddling the rim ---
        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(self.er[idiv(a * NA, 256)] * (85 + (hj >> 8) % 30), 100)
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            ink = self.draw_tuft(dc, seed, j, tx, ty, tsize, dzcol, ink)

        # --- granular texture over the cushion ---
        # cap 130 -> 90 (watchdog): with the bigger late-day crown the extra
        # 40 dots added op count, not visible density
        n = 50 + idiv(act, 12)
        if n > 90:
            n = 90
        for i in range(n):
            if ink <= 0:
                break
            a, rr0, h = place(seed, i, 1, base)
            lim = self.er[idiv(a * NA, 256)]
            rr = idiv(rr0 * lim, base) if base > 0 else 0
            if (h & 1) == 0:
                col = COLOR_DK_GREEN
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

        # --- fuzzy rim fringe ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        for i in range(0, NA, 2):
            if ink <= 0:
                break
            a = imod(idiv(i * 256, NA), 256)
            e = self.er[i]
            le = 2 + (hash16(seed, i, 9) & 1)
            dc.drawLine(CX + self.vx[i], CY + self.vy[i],
                        px(CX, e + le, a), py(CY, e + le, a))
            ink -= 1

        # --- episodes: the golden fruit ring (owner, 2026-07) ---
        # Every bead sits on ONE shared ring system; three rules keep it on
        # the moss without covering the root star and without piling onto
        # other beads:
        #   angle     a golden sequence (97 ~ 256/phi^2) from a per-day
        #             phase, +-10 jitter: any first k beads are near-
        #             uniformly spread, and a bead never moves when a new
        #             episode opens. Beads NEVER ride tufts -- the tuft
        #             offset radius (~8-14 px) huddled same-tuft beads no
        #             matter their angles (owner, 2026-07-17 wrist); a bead
        #             whose angle meets a tuft draws in front of it.
        #   radius    parity-staggered 50%/72% of the rim (two interleaved
        #             rings), floored by the exact per-bead keep-out: the
        #             bead's inner edge clears the outermost root tip by 3.
        #   stalk     anything the star forces off the moss grows a straight
        #             tapered podetium from just inside the rim: flared
        #             holdfast, waist 40% up, cup at the bead's edge.
        ph = seed & 255
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            # gentle slope + high cap so long/hard efforts spread out in size
            # (a 90-min session reads clearly bigger than a 15-min one) while the
            # floor stays put. Bead is a final px radius here (already scaled).
            bead = 4 + idiv(mag, 30)
            if bead > 18:
                bead = 18
            he = hash16(seed, e, 42)
            a = (ph + e * 97 + (he % 21) - 10) & 255   # golden + jitter
            lim = self.er[idiv(a * NA, 256)]
            # K interleaved orbits; NO keep-out -- inner orbits ride over the
            # root star (drawn last, so it stays on top). ORBIT_HI < 100 keeps
            # every bead on the mound, so it can never float (no stalk).
            kk = K if K > 1 else 1
            # OUTER-first: bead 0 rides the outermost ring, later beads fill
            # inward. Few beads stay on the visible rim; a busy day fills in
            # over the root star.
            frac = ORBIT_HI - (idiv((ORBIT_HI - ORBIT_LO) * (e % kk), kk - 1)
                               if kk > 1 else 0)
            rr = idiv(lim * frac, 100)
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead + 1)
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 2

        # --- root star drawn LAST: stays on top of the colony all day ---
        self.draw_sleep(dc, rec.sleep_seed, rec.wake_seed, ink)


def build():
    return {"background": COLOR_BLACK, "components": [MossGroveOrbits()]}
