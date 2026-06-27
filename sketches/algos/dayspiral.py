#!/usr/bin/env python3
"""Option C -- "dayspiral": the day as a coil winding out from the centre.

The balanced middle ground -- legible AND organic. An Archimedean spiral starts
at the centre at midnight and winds outward over the 24 h (TURNS full turns), so
position along the coil = time of day: the hub is morning, the outer end is now.
Each 15-min bucket is one spiral segment COLOURED by its peak HR zone, with a
short outward SPUR whose length = the bucket's activity -- so the coil is a
colour-coded HR timeline and the spurs are the day's movement bristling off it.
Keeps biobloom's "grows from the centre out" feeling while making time readable.

Geometry is parametric (regenerated from the bucket index, like biobloom's arms)
so nothing per-vertex is stored. ~2 primitives per elapsed bucket -> well under
the watchdog. Verbatim port (idiv/imod/isin + drawLine).
"""

import daybuckets as DB
from daybuckets import BUCKETS, CX, CY, px, py, hr_color, act_len
from device import idiv, imod, COLOR_DK_GRAY, COLOR_TRANSPARENT

TURNS = 3              # full turns of the coil across the 24 h
R_START = 6            # hub radius at midnight
R_END = 80            # rim radius at end of day
SPUR = 22             # max activity spur length
DIV = 80              # step-sum -> spur px divisor


def coil_a(b):
    # phase winds TURNS*256 over the whole day; start straight up (192).
    return imod(192 + idiv(b * TURNS * 256, BUCKETS), 256)


def coil_r(b):
    return R_START + idiv(b * (R_END - R_START), BUCKETS)


class DaySpiral:
    def __init__(self):
        self.rec = DB.DayRecord()

    def advance(self, snap):
        self.rec.advance(snap)

    def state_bytes(self):
        return self.rec.state_bytes()

    def render(self, dc, snap):
        rec = self.rec
        if rec.now < 0:
            return
        for b in range(1, rec.now + 1):
            a0, r0 = coil_a(b - 1), coil_r(b - 1)
            a1, r1 = coil_a(b), coil_r(b)
            hr = rec.maxhr[b]
            col = hr_color(hr) if hr > 0 else COLOR_DK_GRAY
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.drawLine(px(CX, r0, a0), py(CY, r0, a0),
                        px(CX, r1, a1), py(CY, r1, a1))   # coil segment
            sp = act_len(rec.steps[b], SPUR, DIV)
            if sp > 0:                                    # activity spur, outward
                dc.drawLine(px(CX, r1, a1), py(CY, r1, a1),
                            px(CX, r1 + sp, a1), py(CY, r1 + sp, a1))


def build():
    from device import COLOR_BLACK
    return {"background": COLOR_BLACK, "components": [DaySpiral()]}
