#!/usr/bin/env python3
"""moss_grove -- the LOCKED two-worlds V2 biometric visualization.

Configuration chosen across the exploration: tuft colour = dominant ELEVATED
zone ("tint"), sleep = root star drawn ON TOP ("coretop", 2026-07: the roots
treatment replaced the original spore clump -- see below). Centred 2/5 up
from the bottom (CY=108), like BioBloom, so the artificial overlay (clock, etc.)
rides above the organism.

This file is the PARITY REFERENCE for core/src/genart/MossGrove.mc (the
strataflock.py role): it mirrors the record (daysoma) + render so the .mc ports
mechanically. The day organism, from the heart out:

  root star      last night's inferred sleep -- the silver ROOT SYSTEM the
                 day's growth stands on, drawn last so it stays visible all
                 day. Hours slept = root count and length; each wake event
                 SNAPS one root at a white speck and kinks the rest, so a
                 rough night is a gnarled, broken star. Sleep speaks only the
                 night palette (silver/blue/gray/white); the warm hues belong
                 to the effort beads exclusively -- the shipped spore clump
                 rendered short nights in the beads' red/orange vocabulary
                 and read as effort at a glance (owner, 2026-07).
  cushion        a solid two-tone lumpy mound; radius grows with the day's total
                 movement; per-day shape from the date seed (shape_params)
  tufts          satellite colony clumps straddling the rim, popping in as
                 activity accrues; grains glow the dominant ELEVATED HR zone
  texture        granular green stipple + fuzzy rim fringe
  episodes       elevated-HR events as bright peak-zone fruiting beads on K
                 interleaved orbits (owner, 2026-07). Beads never ride tufts
                 (the ~8-14 px tuft offset huddled same-tuft beads, 2026-07-17)
                 -- each takes a shared golden-sequence angle and one of K
                 ring radii. The rings are DISPLAY-referenced and grow with the
                 cushion (REACH_MIN -> DISP_R), fill OUTER-first, and carry no
                 keep-out, so inner rings ride OVER the sleep root star while a
                 small morning moss lets outer beads fall past the rim onto a
                 podetium stalk (2026-07-18). On a grown day the reach ~ the
                 rim, so beads land on the moss and the stalks retract.

Time-of-day is intentionally not encoded. Self-bounded by INK (the root star
rides OUTSIDE the budget so the night survives a saturated day -- see
draw_sleep); the outline is sampled once per frame into er/vx/vy instead of
calling edge() per element (the pre-LUT render tripped the sim watchdog at
saturation, 2026-07). Proxy ~10k VM-instr/frame peak, ~245 B state; the
saturated RELEASE frame is verified silent in the sim, which is the ground
truth the proxy is not (docs/watchdog-debugging.md).
"""

import math

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

# effort-bead orbits (owner, 2026-07-18). Beads ride K interleaved rings at
# ORBIT_LO..ORBIT_HI % of a REACH that is DISPLAY-referenced, not rim-relative:
# the reach grows with the cushion from REACH_MIN (smallest morning moss) to
# DISP_R (fully grown), so a lone morning bead sits just off the small moss on
# a podetium stalk instead of at the display edge, and a grown day lands beads
# on the moss. Rings fill OUTER-first; no keep-out, so inner rings ride over
# the sleep root star (drawn last, stays on top).
K = 4                  # number of interleaved bead orbits
DISP_R = 90            # bead reach (px) on a fully grown moss
REACH_MIN = 36         # bead reach (px) on the smallest morning moss
ORBIT_LO = 28          # innermost orbit, % of the reach (over the root star)
ORBIT_HI = 86          # outermost orbit, % of the reach


def scl(v):
    return idiv(v * SCN, SCD)


# rounded division, symmetric in sign: plain truncation shaves ~30% off the
# stalk flare on diagonal runs (both perpendicular components round toward
# zero). Ports as (abs + d/2) / d with the sign re-applied.
BANDS = True           # growth-ring beads (owner, 2026-10); False = solid peak
BAND_MIN = 8           # bead radius (px) from which a bead shows its HR bands
# BAND_SQ[n][j] = round(100 * sqrt((j + 1) / n)): equal-area band radii, %
BAND_SQ = [[], [100], [71, 100], [58, 82, 100], [50, 71, 87, 100],
           [45, 63, 77, 89, 100], [41, 58, 71, 82, 91, 100]]

# Leading-edge rim (owner, 2026-10 -- sandbox only, not ported): a 1 px line
# traced along the cushion outline. RIM = its colour (None = off, the shipped
# look). RIM_MODE:
#   "under"  trace the outline straight after the mound fill (tufts, fringe
#            and beads draw over it); NA drawLines
#   "over"   trace it after tufts/texture/fringe: one unbroken line that
#            crosses the tufts; NA drawLines
#   "halo"   paint the silhouette (mound fan at e+1, each tuft at r+1) in RIM
#            BEFORE the mound, so a 1 px ring survives around the union of
#            mound + tufts; NA fillPolygons + ntuft fillCircles
# Fixed cost, outside the ink budget like the root star, so a saturated day
# keeps it.
RIM = None
RIM_MODE = "under"


def bead_radius(mag):
    """Effort-bead radius (final px, already scaled) from banked magnitude:
    1 + isqrt(mag), cap 24 (owner, 2026-10: steeper on both ends -- under the
    old 4 + mag/30 cap 18 every everyday effort sat on the 4 px floor). sqrt
    spreads the small efforts (stairs 2, a hurry 3, a walk ~8-11) while a
    ~50-min run still reaches the cap. The .mc takes Math.sqrt(mag).toNumber()
    for mag < 529 (= 23^2; exact-squares are exact in float, so it truncates
    the same as isqrt) -- see sketches/bead_size_compare.py."""
    if mag >= 529:
        return 24
    return 1 + math.isqrt(mag)


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


class MossGrove:
    def __init__(self):
        self.rec = DS.DayRecord()
        # per-frame outline LUT (render scratch, allocated once): edge radius
        # and outer-fan vertex offsets at the NA rim angles. See render().
        self.er = [0] * NA
        self.vx = [0] * NA
        self.vy = [0] * NA

    def advance(self, snap, hist=None):
        self.rec.advance(snap, hist)

    # Growth rings (owner, 2026-10): a bead of radius >= BAND_MIN shows its
    # episode's HR course as concentric EQUAL-AREA bands, start at the centre,
    # end at the rim, each band the PEAK zone of its share of the episode's
    # chronological slots (daysoma: eband/edur). Equal area gives every time
    # slice the same ink; the outermost band is the thinnest, so the band
    # count is bead/4 (keeps it >= ~2 px), capped at the slots recorded.
    # Drawn outermost-first as nested discs; a band the same colour as the one
    # outside it is skipped (already painted). Returns ink spent.
    def draw_bands(self, dc, x, y, bead, b, dur):
        lv = (b >> 24) & 15
        ns = ((dur - 1) >> lv) + 1
        nb = idiv(bead, 4)
        if nb > DS.NSLOT:
            nb = DS.NSLOT
        if nb > ns:
            nb = ns
        prev = -1
        spent = 0
        for j in range(nb - 1, -1, -1):
            s0 = idiv(j * ns, nb)
            s1 = idiv((j + 1) * ns, nb)
            z = 0
            for k in range(s0, s1):
                v = (b >> (4 * k)) & 15
                if v > z:
                    z = v
            if z != prev:
                r = bead if j == nb - 1 else idiv(bead * BAND_SQ[nb][j] + 50, 100)
                dc.setColor(zone_color(z), COLOR_TRANSPARENT)
                dc.fillCircle(x, y, r)
                spent += 1
            prev = z
        return spent

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

    # the leading edge: close the cached outline polygon with NA 1 px lines
    def draw_rim(self, dc):
        dc.setColor(RIM, COLOR_TRANSPARENT)
        x0 = CX + self.vx[0]
        y0 = CY + self.vy[0]
        for i in range(1, NA + 1):
            j = imod(i, NA)
            x1 = CX + self.vx[j]
            y1 = CY + self.vy[j]
            dc.drawLine(x0, y0, x1, y1)
            x0 = x1
            y0 = y1

    # the silhouette halo: the mound fan pushed out 1 px plus each tuft disc
    # 1 px larger, all in RIM, under everything (same tuft math as render())
    def draw_halo(self, dc, ntuft, tsize, seed):
        dc.setColor(RIM, COLOR_TRANSPARENT)
        tri = [(CX, CY), (0, 0), (0, 0)]
        a0 = 0
        x0 = px(CX, self.er[0] + 1, a0)
        y0 = py(CY, self.er[0] + 1, a0)
        for i in range(1, NA + 1):
            j = imod(i, NA)
            aj = imod(idiv(j * 256, NA), 256)
            x1 = px(CX, self.er[j] + 1, aj)
            y1 = py(CY, self.er[j] + 1, aj)
            tri[1] = (x0, y0)
            tri[2] = (x1, y1)
            dc.fillPolygon(tri)
            x0 = x1
            y0 = y1
        for j in range(ntuft):
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(self.er[idiv(a * NA, 256)] * (85 + (hj >> 8) % 30), 100)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), idiv(tsize, 2) + 1)

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
        B0 = scl(4)                            # cushion base floor / cap: the
        B1 = scl(54)                           # growth span for the bead reach

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

        if RIM is not None and RIM_MODE == "halo":
            self.draw_halo(dc, ntuft, tsize, seed)

        # --- central cushion: dark mound + bright green crown ---
        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 100)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 60)
        if RIM is not None and RIM_MODE == "under":
            self.draw_rim(dc)

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

        if RIM is not None and RIM_MODE == "over":
            self.draw_rim(dc)

        # --- episodes: the display-referenced orbits (owner, 2026-07) ---
        # Every bead rides one of K interleaved rings; three rules keep them
        # spread, contiguous, and over the sleep:
        #   angle     a golden sequence (97 ~ 256/phi^2) from a per-day
        #             phase, +-10 jitter: any first k beads are near-uniformly
        #             spread, and a bead never moves when a new episode opens.
        #             Beads never ride tufts (the ~8-14 px tuft offset huddled
        #             same-tuft beads, 2026-07-17); a bead whose angle meets a
        #             tuft draws in front of it.
        #   radius    K orbits at ORBIT_LO..ORBIT_HI % of a REACH, OUTER-first
        #             (bead 0 -> outermost). The reach is DISPLAY-referenced
        #             and grows with the cushion (REACH_MIN -> DISP_R), NOT the
        #             rim, so beads aren't flung to the edge on a small moss
        #             (2026-07-18). No keep-out: inner rings ride over the root
        #             star (drawn last, stays on top).
        #   stalk     an outer ring that falls past a small moss's rim grows a
        #             straight tapered podetium from just inside the rim:
        #             flared holdfast, waist 40% up, cup at the bead's edge.
        #             On a grown day the reach ~ the rim, so beads land on the
        #             moss and the stalk never fires.
        ph = seed & 255
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            bead = bead_radius(mag)
            sx = None                       # stalk anchor when displaced
            sy = 0
            he = hash16(seed, e, 42)
            a = (ph + e * 97 + (he % 21) - 10) & 255   # golden + jitter
            lim = self.er[idiv(a * NA, 256)]
            kk = K if K > 1 else 1
            frac = ORBIT_HI - (idiv((ORBIT_HI - ORBIT_LO) * (e % kk), kk - 1)
                               if kk > 1 else 0)
            # reach grows with the cushion: REACH_MIN (base at its scl(4)
            # floor) -> DISP_R (base at its scl(54) cap)
            g = base - B0
            if g < 0:
                g = 0
            reach = REACH_MIN + idiv((DISP_R - REACH_MIN) * g, B1 - B0)
            rr = idiv(reach * frac, 100)
            if rr - bead > lim - 2:         # fell past the rim: stalk it
                sx = px(CX, lim - 2, a)     # anchored just inside the rim,
                sy = py(CY, lim - 2, a)     # under the fringe
            x = px(CX, rr, a)
            y = py(CY, rr, a)
            if sx is not None:
                # STRAIGHT tapered stalk (owner, 2026-07-14: no kink, and
                # push the flare): a podetium with a visible cup. Wide
                # holdfast where it leaves the moss, waist 40% up, then a
                # flare that ends at the bead's EDGE -- ending at the bead
                # centre hid the tip flare under the dark ring. Two CONVEX
                # trapezoids (the on-device fillPolygon is only trusted
                # convex); perpendicular half-widths 5/1/4 from the true
                # stalk direction; ln is the octagonal length approximation
                # (max + min/2, ~12%), all integer.
                dx = x - sx
                dy = y - sy
                adx = dx if dx >= 0 else -dx
                ady = dy if dy >= 0 else -dy
                ln = (adx if adx > ady else ady) \
                    + idiv((adx if adx < ady else ady), 2)
                if ln < 1:
                    ln = 1
                pb = bead - 2               # tuck the cup 2 px under the disc
                if pb > ln - 3:
                    pb = ln - 3
                if pb < 0:
                    pb = 0
                ex = x - idiv(dx * pb, ln)  # cup lip, at the bead's edge
                ey = y - idiv(dy * pb, ln)
                wx = sx + idiv((ex - sx) * 2, 5)   # waist 40% up the stalk
                wy = sy + idiv((ey - sy) * 2, 5)
                bxw = rdiv(-dy * 5, ln)     # holdfast (half-width 5)
                byw = rdiv(dx * 5, ln)
                wxw = rdiv(-dy, ln)         # waist (half-width 1) --
                wyw = rdiv(dx, ln)          # never let it pinch to zero
                if wxw == 0 and wyw == 0:
                    if adx >= ady:
                        wyw = 1
                    else:
                        wxw = 1
                txw = rdiv(-dy * 4, ln)     # cup (half-width 4)
                tyw = rdiv(dx * 4, ln)
                dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
                dc.fillPolygon([(sx - bxw, sy - byw), (sx + bxw, sy + byw),
                                (wx + wxw, wy + wyw), (wx - wxw, wy - wyw)])
                dc.fillPolygon([(wx - wxw, wy - wyw), (wx + wxw, wy + wyw),
                                (ex + txw, ey + tyw), (ex - txw, ey - tyw)])
                ink -= 2
            dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead + 1)
            if BANDS and bead >= BAND_MIN and rec.edur[e] > 0:
                ink -= self.draw_bands(dc, x, y, bead, rec.eband[e],
                                       rec.edur[e])
            else:
                dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
                dc.fillCircle(x, y, bead)
            ink -= 2

        # --- root star drawn LAST: stays on top of the colony all day ---
        self.draw_sleep(dc, rec.sleep_seed, rec.wake_seed, ink)


def build():
    return {"background": COLOR_BLACK, "components": [MossGrove()]}
