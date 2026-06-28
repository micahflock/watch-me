#!/usr/bin/env python3
"""Option A -- "dayring": the day as a 24-hour clock ring.

Angle = time of day (midnight at top, clockwise). Each elapsed 15-min bucket is
a wedge: COLOUR = the bucket's peak HR zone, and the wedge BULGES OUTWARD with
the bucket's activity (step sum) -- so a calm hour is a thin cool band and a run
is a fat hot lobe at that time of day. The most legible of the three: it reads
straight off as "where in the day were you hot / moving", like a daily HR graph
wrapped onto the dial.

One fillPolygon per elapsed bucket (<=96), zero growing scans -> trivially under
the watchdog. Ports to Monkey C verbatim (idiv/imod/isin + fillPolygon).
"""

import daybuckets as DB
from daybuckets import BUCKETS, CX, CY, bucket_angle, px, py, hr_color, act_len
from device import COLOR_DK_GRAY, COLOR_WHITE, COLOR_TRANSPARENT

R_IN = 40              # ring inner radius
R_BASE = 52            # idle/cool outer radius (the ring's resting thickness)
SPAN = 30              # max additional bulge from activity (R_BASE+SPAN = 82)
DIV = 60               # step-sum -> bulge px divisor (~1800 steps = full bulge)


class DayRing:
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
        for b in range(rec.now + 1):
            a0 = bucket_angle(b)
            a1 = bucket_angle(b + 1)
            rout = R_BASE + act_len(rec.steps[b], SPAN, DIV)
            hr = rec.maxhr[b]
            dc.setColor(hr_color(hr) if hr > 0 else COLOR_DK_GRAY,
                        COLOR_TRANSPARENT)
            dc.fillPolygon([
                [px(CX, R_IN, a0), py(CY, R_IN, a0)],
                [px(CX, rout, a0), py(CY, rout, a0)],
                [px(CX, rout, a1), py(CY, rout, a1)],
                [px(CX, R_IN, a1), py(CY, R_IN, a1)],
            ])
        # Quarter-day tick marks (00/06/12/18) for time orientation.
        dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
        for q in range(4):
            a = bucket_angle(q * BUCKETS // 4)
            dc.drawLine(px(CX, R_IN - 3, a), py(CY, R_IN - 3, a),
                        px(CX, R_IN, a), py(CY, R_IN, a))


def build():
    from device import COLOR_BLACK
    return {"background": COLOR_BLACK, "components": [DayRing()]}
