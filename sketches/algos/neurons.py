#!/usr/bin/env python3
"""Avenue 3 -- "neurons": the day as a firing neural network.

A few cell bodies (soma) sit scattered in the dish, each sprouting branching
dendrites. The more you MOVED, the more soma and the longer/bushier the
dendrites -- the network fills out over an active day. Resting tissue is drawn
cool and dim (dark blue/grey); every elevated-HR EPISODE is a glowing SYNAPSE: a
bright peak-zone node with a halo, sized by magnitude, planted at a dendrite tip,
with the dendrite leading to it "firing" in the zone colour. The day's HR mix
also tints a fraction of branches via zone_pick. Web-like and electric -- thin
branches plus bright nodes, the opposite of a solid clump. Time-of-day is not
encoded; the whole network is deterministic from the day seed.

Dendrites are short jagged polylines regenerated from hashes (no per-vertex
state). Self-bounded by INK. Verbatim Monkey C port.
"""

import daysoma as DS
from daysoma import zone_color, zone_lut, ZLUT, CX, CY
from daybuckets import px, py
from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_DK_BLUE, COLOR_DK_GRAY, COLOR_LT_GRAY, COLOR_WHITE,
                    COLOR_DK_RED)

INK = 320
SEG = 4                # segments per dendrite branch


# A jagged branch from (cx-relative angle a, radius r0) outward `length` px, drawn
# as SEG wobbled segments. Returns the tip (x, y) so a synapse can sit on it.
def branch(dc, a, r0, length, wob, salt):
    step = idiv(length, SEG)
    if step < 2:
        step = 2
    r = r0
    aa = a
    x0 = px(CX, r, aa)
    y0 = py(CY, r, aa)
    tipx, tipy = x0, y0
    for k in range(SEG):
        aa = imod(aa + idiv(wob * isin(imod(hash16(salt, k, 3), 256)), 127), 256)
        r += step
        x1 = px(CX, r, aa)
        y1 = py(CY, r, aa)
        dc.drawLine(x0, y0, x1, y1)
        x0, y0 = x1, y1
        tipx, tipy = x1, y1
    return tipx, tipy


class Neurons:
    def __init__(self):
        self.rec = DS.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def render(self, dc, snap):
        rec = self.rec
        ink = INK
        seed = rec.seed
        lut = zone_lut(rec)
        nsoma = 3 + idiv(rec.act_units, 90)
        if nsoma > 7:
            nsoma = 7
        dlen = 14 + idiv(rec.act_units, 30)       # dendrite reach grows with day
        if dlen > 46:
            dlen = 46
        ndend = 3 + idiv(rec.act_units, 120)
        if ndend > 6:
            ndend = 6

        # soma positions (deterministic), kept for axon links + synapse anchoring
        sx = []
        sy = []
        for s in range(nsoma):
            a = imod(hash16(seed, s, 1), 256)
            rr = 12 + imod(hash16(seed, s, 2), 40)
            sx.append(px(CX, rr, a))
            sy.append(py(CY, rr, a))

        # --- faint axon links between consecutive soma (the network) ---
        dc.setColor(COLOR_DK_GRAY, COLOR_TRANSPARENT)
        for s in range(1, nsoma):
            if ink <= 0:
                break
            dc.drawLine(sx[s - 1], sy[s - 1], sx[s], sy[s])
            ink -= 1

        # --- dendrites off each soma; remember tips to hang synapses on ---
        tips_x = []
        tips_y = []
        tips_a = []
        for s in range(nsoma):
            a0 = imod(hash16(seed, s, 1), 256)
            rr0 = 12 + imod(hash16(seed, s, 2), 40)
            for d in range(ndend):
                if ink <= 0:
                    break
                salt = hash16(seed, s * 8 + d, 9)
                a = imod(a0 + d * 47 + imod(salt, 24), 256)
                # most branches resting/cool; some carry the day's HR tint
                z = lut[salt & (ZLUT - 1)] if lut is not None else -1
                if z >= 4 and imod(salt, 3) == 0:
                    dc.setColor(zone_color(z), COLOR_TRANSPARENT)
                else:
                    dc.setColor(COLOR_DK_BLUE, COLOR_TRANSPARENT)
                tx, ty = branch(dc, a, rr0, dlen, 22, salt)
                ink -= SEG
                tips_x.append(tx)
                tips_y.append(ty)
                tips_a.append(a)

        # --- soma bodies on top of their dendrite roots ---
        for s in range(nsoma):
            dc.setColor(COLOR_LT_GRAY, COLOR_TRANSPARENT)
            dc.fillCircle(sx[s], sy[s], 2)

        # --- synapses: episodes as bright haloed nodes on dendrite tips ---
        ntip = len(tips_x)
        if ntip == 0:
            return
        for e in range(rec.nepi):
            if ink <= 0:
                break
            t = imod(hash16(seed, e, 21), ntip)
            x = tips_x[t]
            y = tips_y[t]
            mag = rec.emag[e]
            nr = 2 + idiv(mag, 16)
            if nr > 5:
                nr = 5
            dc.setColor(COLOR_DK_RED if rec.epz[e] >= 6 else COLOR_DK_BLUE,
                        COLOR_TRANSPARENT)
            dc.fillCircle(x, y, nr + 1)            # halo
            dc.setColor(zone_color(rec.epz[e]), COLOR_TRANSPARENT)
            dc.fillCircle(x, y, nr)                # firing node
            dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
            dc.fillCircle(x, y, 0)                 # spark
            ink -= 3


def build():
    return {"background": COLOR_BLACK, "components": [Neurons()]}
