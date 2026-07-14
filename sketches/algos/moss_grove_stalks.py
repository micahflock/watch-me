#!/usr/bin/env python3
"""moss_grove_stalks -- bead-contiguity PROPOSAL A for two-worlds V2.

PROBLEM (2026-07-13 wrist): on a low-movement morning the effort beads float
in black space, detached from the moss. The blanket root-star keep-out
(root_len + 20 + scl(6)) is sized for the WORST bead (max tuft offset + max
bead radius), so at 6-7am -- rim ~15-25 px, keep-out ~55 px -- every bead is
pushed well past the cushion; in the tuft branch it is pushed past its own
tuft (the bead re-derives the tuft position and clamps THAT, while the real
tuft stays straddling the rim). The organism reads as moss + unrelated
confetti until midday movement grows the rim past the keep-out.

TREATMENT (episodes layer only; everything else inherited from moss_grove):

  exact keep-out   each bead keeps out only what IT needs to clear the root
                   star: root_len + its own radius + 3, measured on the
                   bead's RADIAL position (the tuft offset folded onto the
                   radius with one isin), not the blanket worst case.
                   Small morning beads pull 10-20 px back toward the body.
  embed            a bead whose outward tuft offset leaves it tangent-
                   kissing the rim (the 13:05 seam) is pulled inward until
                   it overlaps the mound by 2 px -- as far as the star's
                   keep-out allows.
  stalks           a bead the star still forces off the moss grows a
                   STRAIGHT tapered DK_GREEN stalk from the moss (the rim
                   at its angle, or the REAL tuft it was seeded on) out to
                   the bead -- a lichen podetium: flared where it leaves
                   the moss, waisted mid-run, flaring again under the bead
                   (owner, 2026-07-14: no kink, thicker, thick at each
                   end). The bead's dark ring caps the tip; the tuft blob /
                   rim fringe covers the base.
  spread           bead angles walk a golden sequence (index * 97 & 255 +
                   a per-day phase + small jitter) and tufts are dealt
                   round-robin instead of hashed, so beads stop piling up
                   on one another (owner, 2026-07-14: less overlap).
                   Cheaper than ship -- one hash16 per bead dropped, no
                   new state, no collision pass.

Contiguity self-heals as the day accretes: once the rim overtakes the
keep-out the clamps never fire, no stalks, and the geometry is identical to
ship. Cost: +2 isin per bead; 2 fillPolygon per DISPLACED bead, beads
capped at 16 and mostly attached at saturation.
"""
import importlib.util
import os

from device import (idiv, imod, hash16, isin, account,
                    COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_GREEN, COLOR_GREEN, COLOR_YELLOW)
from daybuckets import px, py
from daysoma import zone_color, dominant_zone, ACTIVE
from mossutil import edge, shape_params

_p = os.path.join(os.path.dirname(__file__), "moss_grove.py")
_spec = importlib.util.spec_from_file_location("moss_grove", _p)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CX, CY, NA, INK = mg.CX, mg.CY, mg.NA, mg.INK
BASE_DIV, TUFT_DIV, AMPREF = mg.BASE_DIV, mg.TUFT_DIV, mg.AMPREF
scl, root_len = mg.scl, mg.root_len


# rounded division, symmetric in sign: plain truncation shaves ~30% off the
# stalk flare on diagonal runs (both perpendicular components round toward
# zero). Ports as (abs + d/2) / d with the sign re-applied.
def rdiv(v, d):
    av = v if v >= 0 else -v
    q = idiv(av + idiv(d, 2), d)
    return q if v >= 0 else -q


class MossGroveStalks(mg.MossGrove):

    # render() is the parent's line for line EXCEPT the episodes block,
    # which is marked >>> ... <<< below. Kept whole (not factored) so this
    # proposal leaves moss_grove.py -- the parity reference -- untouched
    # until the owner picks a treatment.
    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        dz = dominant_zone(rec, ACTIVE)
        if dz < 0:
            dz = dominant_zone(rec)
        dzcol = zone_color(dz) if dz >= 0 else None
        act = rec.act_units

        base = 4 + idiv(act, BASE_DIV)
        if base > 54:
            base = 54
        base = scl(base)

        sp = shape_params(seed)
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

        for i in range(NA):
            ai = imod(idiv(i * 256, NA), 256)
            e = edge(base, ai, sp)
            self.er[i] = e
            self.vx[i] = idiv(e * isin(ai + 64), 127)
            self.vy[i] = idiv(e * isin(ai), 127)
        account(NA * 2)

        dc.setColor(COLOR_DK_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 100)
        dc.setColor(COLOR_GREEN, COLOR_TRANSPARENT)
        self.fan_lut(dc, 60)

        for j in range(ntuft):
            if ink <= 0:
                break
            hj = hash16(seed, j, 31)
            a = imod(idiv(j * 256, ntuft if ntuft else 1) + (hj & 31), 256)
            rr = idiv(self.er[idiv(a * NA, 256)] * (85 + (hj >> 8) % 30), 100)
            tx = px(CX, rr, a)
            ty = py(CY, rr, a)
            ink = self.draw_tuft(dc, seed, j, tx, ty, tsize, dzcol, ink)

        n = 50 + idiv(act, 12)
        if n > 90:
            n = 90
        for i in range(n):
            if ink <= 0:
                break
            a, rr0, h = mg.place(seed, i, 1, base)
            lim = self.er[idiv(a * NA, 256)]
            rr = idiv(rr0 * lim, base) if base > 0 else 0
            if (h & 1) == 0:
                col = COLOR_DK_GREEN
            else:
                col = COLOR_YELLOW if ((h >> 6) & 7) == 0 else COLOR_GREEN
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(px(CX, rr, a), py(CY, rr, a), 1)
            ink -= 1

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

        # >>> episodes: EXACT per-bead keep-out, rim embed, stalks, spread ----
        # rl = the root star's true reach (outermost tip radius). The ship
        # blanket (rl + 20 + scl(6)) priced every bead at the worst case.
        #
        # Bead ANGLES walk a golden sequence (97 ~ 256/phi^2, the golden
        # angle) from a per-day phase instead of independent hashes: any
        # first k beads are near-uniformly spread, so beads stop piling up
        # (owner, 2026-07-14: less overlap). Index-based, so an existing
        # bead never moves when a new episode opens; +-10 hash jitter keeps
        # it from reading mechanical. Tufts are dealt round-robin for the
        # same reason -- and both TOGETHER stay spread: episodes e, e+ntuft
        # share a tuft and their golden offsets differ by ntuft*97 & 255,
        # which is a wide angle for every ntuft in 1..7. Costs LESS than
        # ship (drops the hash16 tuft pick).
        ph = seed & 255
        rl = root_len(rec.sleep_seed) if rec.sleep_seed > 0 else 0
        for e in range(rec.nepi):
            if ink <= 0:
                break
            mag = rec.emag[e]
            bead = 4 + idiv(mag, 30)
            if bead > 18:
                bead = 18
            # the bead's inner edge must clear the outermost root tip by 3
            need = (rl + bead + 3) if rl > 0 else 0
            sx = None                       # stalk anchor when displaced
            sy = 0
            if ntuft > 0:
                t = imod(e, ntuft)          # round-robin, not hash: even load
                hj = hash16(seed, t, 31)
                ta = imod(idiv(t * 256, ntuft) + (hj & 31), 256)
                rim = self.er[idiv(ta * NA, 256)]
                trr0 = idiv(rim * (85 + (hj >> 8) % 30), 100)  # REAL tuft
                he = hash16(seed, e, 42)
                off = idiv(tsize, 2) + (he >> 8) % 3
                a = (ph + e * 97 + (he % 21) - 10) & 255   # golden + jitter
                # polar estimate of the bead centre: the tuft offset split
                # into a radial part (folded onto the radius) and a
                # tangential part (folded onto the ANGLE, 41 ~ 256/2pi) --
                # the rim the bead must touch is the rim at the bead's own
                # angle, not the tuft's (isin masks & 255, negatives fine).
                dr = idiv(off * isin(a - ta + 64), 127)
                tg = idiv(off * isin(a - ta), 127)
                trr = trr0
                rad = trr + dr
                if rad < need:              # star pushes it out
                    trr = need - dr
                    rad = need
                ab = imod(ta + (idiv(tg * 41, rad) if rad > 0 else 0)
                          + 256, 256)
                rimb = self.er[idiv(ab * NA, 256)]
                # required embed depth grows with the bead: a tangent kiss
                # on a fat bead reads detached (black shoulders around a
                # 1 px contact), so bury a third of it
                emb = 3 + idiv(bead, 3)
                if rad - bead > rimb - emb:
                    dt = (rad - bead) - (rimb - emb)  # overshot: pull in as
                    if dt > rad - need:               # far as the star
                        dt = rad - need               # allows
                    if dt > 0:
                        trr -= dt
                        rad -= dt
                    if trr < 2:             # tiny-rim corner: stay put
                        rad += 2 - trr
                        trr = 2
                if rad - bead > rimb - 2:   # not solidly embedded: stalk
                    sx = px(CX, trr0, ta)   # from the REAL tuft it rides
                    sy = py(CY, trr0, ta)   # (the mound occludes the
                                            # stalk's inner run)
                tx = px(CX, trr, ta)
                ty = py(CY, trr, ta)
                x = tx + idiv(off * isin(a + 64), 127)
                y = ty + idiv(off * isin(a), 127)
            else:
                he = hash16(seed, e, 42)
                a = (ph + e * 97 + (he % 21) - 10) & 255   # golden + jitter
                lim = self.er[idiv(a * NA, 256)]
                rr = idiv(lim * 3, 5)
                if rr < need:
                    rr = need
                if rr - bead > lim - 2:     # not solidly on the crown:
                    sx = px(CX, lim - 2, a) # stalk anchored just inside the
                    sy = py(CY, lim - 2, a) # rim, under the fringe
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
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, bead)
            ink -= 2
        # <<< end episodes ----------------------------------------------------

        self.draw_sleep(dc, rec.sleep_seed, rec.wake_seed, ink)


def build():
    return {"background": COLOR_BLACK, "components": [MossGroveStalks()]}
