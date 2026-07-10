#!/usr/bin/env python3
"""Concept C -- "windtree": the day as a wind-swept tree.

A deterministic branching tree (iterative, fixed-size queue -- no recursion)
grows from a root point: bark-grey limbs fork by hashed angles, and the whole
crown leans with a per-day wind. Line-work, not blobs: closer to a Lichtenberg
figure or a Japanese ink pine than to anything cellular.

  segments grown            <- act_units (the tree literally grows as you move;
                               a lazy day is a sapling, a big day a full crown)
  leaves at the branch tips <- the day's HR-zone mix (zone_lut); before any HR
                               history the tree stands bare (winter tree)
  episodes                  <- fruit hung on hashed tips: dim ring + peak-zone
                               fill + glint, sized by magnitude
  sleep                     <- the pool at the roots: width = hours slept,
                               colour = SLEEP_RAMP quality; each 0-6am wake
                               drops a white stone into the pool
  day seed                  <- wind direction/strength, fork angles, fork
                               pattern: no two days grow the same tree

Integer-only; the BFS queue is a fixed array pair (ports to Monkey C as-is).
Self-bounded by INK; queue work is charged via account().
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, sleep_slot, SLEEP_RAMP, ZLUT
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, account, COLOR_TRANSPARENT,
                    COLOR_BLACK, COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY,
                    COLOR_DK_RED, COLOR_PURPLE, COLOR_DK_BLUE)

CX = 107
BASEY = 148            # trunk root; crown grows upward from here
INK = 380
QCAP = 72              # BFS queue capacity (fixed arrays on-device)
TCAP = 48              # tip-position store for leaves/fruit
DMAX = 6

DIM = {0: COLOR_DK_BLUE, 1: COLOR_DK_BLUE, 2: COLOR_DK_BLUE, 3: COLOR_DK_BLUE,
       4: COLOR_DK_RED, 5: COLOR_DK_RED, 6: COLOR_DK_RED, 7: COLOR_PURPLE,
       8: COLOR_PURPLE}


class WindTree:
    def __init__(self):
        self.rec = DS.DayRecord()
        # fixed BFS queue: x, y, angle(1/256), len, depth, id
        self._q = [[0] * 6 for _ in range(QCAP)]
        self._tx = [0] * TCAP
        self._ty = [0] * TCAP
        self._tri = [[0, 0], [0, 0], [0, 0]]

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def render(self, dc, snap):
        rec = self.rec
        if rec.idle_min == 0 and rec.active_min == 0:
            return
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)

        h0 = hash16(seed, 1, 71)
        lean = imod(h0, 13) - 6                # per-day wind lean (angle bias)
        gust = 1 + imod(h0 >> 5, 3)            # extra lean per generation
        nseg = 8 + idiv(rec.act_units, 26)     # growth budget: a full crown
        if nseg > 140:                         # needs a genuinely big day
            nseg = 140
        tlen = 15 + idiv(rec.act_units, 400)
        if tlen > 23:
            tlen = 23

        # --- sleep pool at the roots (behind the trunk) ---
        mins = rec.sleep_seed
        if mins > 0:
            hours = idiv(mins, 60)
            slot = sleep_slot(mins) - rec.wake_seed
            if slot < 0:
                slot = 0
            rx = 8 + hours * 3
            if rx > 38:
                rx = 38
            ry = 3 + idiv(hours, 2)
            if ry > 8:
                ry = 8
            dc.setColor(SLEEP_RAMP[slot], COLOR_TRANSPARENT)
            self._pool(dc, CX, BASEY + 6, rx, ry)
            ink -= 10
            for w in range(rec.wake_seed):     # wake stones in the pool
                if ink <= 0:
                    break
                hw = hash16(53, w, 72)
                sx = CX - rx + 4 + imod(hw, 2 * rx - 8 if rx > 4 else 1)
                sy = BASEY + 4 + imod(hw >> 7, 5)
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillCircle(sx, sy, 2)
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(sx, sy, 0)
                ink -= 2

        # --- grow the tree: BFS with a fixed ring of branch tips ---
        q = self._q
        q[0][0] = CX
        q[0][1] = BASEY
        q[0][2] = 192 + lean                  # 192 = straight up
        q[0][3] = tlen
        q[0][4] = 0
        q[0][5] = 1
        head, tail, drawn, ntip = 0, 1, 0, 0
        while head < tail and drawn < nseg and ink > 0:
            account(2)
            x, y, a, l, d, nid = q[imod(head, QCAP)]
            head += 1
            am = imod(a, 256)
            nx = x + idiv(l * isin(am + 64), 127)
            ny = y + idiv(l * isin(am), 127)
            dc.setColor(COLOR_LT_GRAY if d < 2 else COLOR_DK_GRAY,
                        COLOR_TRANSPARENT)
            dc.drawLine(x, y, nx, ny)
            if d == 0:                         # thicken the trunk and boughs
                dc.drawLine(x - 1, y, nx - 1, ny)
                dc.drawLine(x + 1, y, nx + 1, ny)
                ink -= 2
            elif d == 1:
                dc.drawLine(x + 1, y, nx + 1, ny)
                ink -= 1
            drawn += 1
            ink -= 1
            h = hash16(seed, nid, 73)
            kids = 2 if d < DMAX else 0
            if kids and d >= 2 and imod(h, 5) == 0:
                kids = 1                       # occasional single continuation
            nl = idiv(l * 7, 10)
            if nl < 4 or kids == 0 or tail - head >= QCAP - 2:
                if ntip < TCAP:                # store as a leafy tip
                    self._tx[ntip] = nx
                    self._ty[ntip] = ny
                    ntip += 1
                continue
            spr = 15 + imod(h >> 4, 20)
            for c in range(kids):
                slot_i = imod(tail, QCAP)
                q[slot_i][0] = nx
                q[slot_i][1] = ny
                q[slot_i][2] = a + (spr if c == 0 else -spr) + gust
                q[slot_i][3] = nl + imod(h >> (6 + c), 3)
                q[slot_i][4] = d + 1
                q[slot_i][5] = nid * 2 + c
                tail += 1
        # any branch still queued when the growth budget ran out is also a tip
        while head < tail and ntip < TCAP:
            account(1)
            e = q[imod(head, QCAP)]
            head += 1
            self._tx[ntip] = e[0]
            self._ty[ntip] = e[1]
            ntip += 1

        # --- leaves: zone-mix dots clustered on the tips ---
        if lut is not None and ntip > 0:
            nl = ntip * 3
            if nl > 120:
                nl = 120
            for i in range(nl):
                if ink <= 0:
                    break
                h = hash16(seed, i, 74)
                ti = imod(i, ntip)
                col = zone_color(lut[h & (ZLUT - 1)])
                dc.setColor(col, COLOR_TRANSPARENT)
                dc.fillCircle(self._tx[ti] + imod(h, 9) - 4,
                              self._ty[ti] + imod(h >> 7, 9) - 4,
                              1 if imod(h >> 4, 2) == 0 else 0)
                ink -= 1

        # --- episodes: fruit hung on hashed tips ---
        for e in range(rec.nepi):
            if ink <= 0 or ntip == 0:
                break
            he = hash16(seed, e, 75)
            ti = imod(he, ntip)
            x = self._tx[ti] + imod(he >> 6, 5) - 2
            y = self._ty[ti] + 3
            mag = rec.emag[e]
            s = 2 + idiv(mag, 30)
            scap = 3 + idiv(nseg, 45)          # fruit scales with the tree
            if scap > 6:
                scap = 6
            if s > scap:
                s = scap
            zc = rec.epz[e]
            dc.setColor(DIM[zc], COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s + 1)
            dc.setColor(zone_color(zc), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, s)
            if mag >= 40:
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(x - 1, y - 1, 0)
                ink -= 1
            ink -= 2

    # filled ellipse as a fan of convex triangles (fillPolygon-safe)
    def _pool(self, dc, cx, cy, rx, ry):
        t = self._tri
        n = 10
        x0 = cx + rx
        y0 = cy
        for i in range(1, n + 1):
            a = imod(idiv(i * 256, n), 256)
            x1 = cx + idiv(rx * isin(a + 64), 127)
            y1 = cy + idiv(ry * isin(a), 127)
            t[0][0] = cx
            t[0][1] = cy
            t[1][0] = x0
            t[1][1] = y0
            t[2][0] = x1
            t[2][1] = y1
            dc.fillPolygon(t)
            x0, y0 = x1, y1


def build():
    return {"background": COLOR_BLACK, "components": [WindTree()]}
