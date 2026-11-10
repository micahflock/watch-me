#!/usr/bin/env python3
"""Option B -- "dayrays": the day as a radial histogram / sundial.

Angle = time of day (midnight at top, clockwise). Each elapsed 15-min bucket is
a RAY from the centre: LENGTH = the bucket's activity (step sum), COLOUR = its
peak HR zone. A still hour is a short cool stub near the hub; a run is a long
hot spoke pointing at the time it happened. Reads as a daily activity bar chart
bent around the dial, with HR carried by colour.

One drawLine per elapsed bucket (<=96) -> far under the watchdog. Verbatim port
(idiv/imod/isin + drawLine).
"""

import daybuckets as DB
from daybuckets import BUCKETS, CX, CY, bucket_angle, px, py, hr_color, act_len
from device import COLOR_DK_GRAY, COLOR_DK_BLUE, COLOR_TRANSPARENT

R0 = 8                 # hub radius (rays start here)
SPAN = 74              # max ray length beyond the hub (R0+SPAN = 82)
DIV = 26               # step-sum -> length px divisor (~1900 steps = full ray)
STUB = 4               # idle-bucket stub so the elapsed day always reads round


class DayRays:
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
        # faint hub so the centre reads as the origin of the day
        dc.setColor(COLOR_DK_BLUE, COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, 2)
        for b in range(rec.now + 1):
            a = bucket_angle(b)
            ln = act_len(rec.steps[b], SPAN, DIV)
            if ln < STUB:
                ln = STUB
            hr = rec.maxhr[b]
            dc.setColor(hr_color(hr) if hr > 0 else COLOR_DK_GRAY,
                        COLOR_TRANSPARENT)
            dc.drawLine(px(CX, R0, a), py(CY, R0, a),
                        px(CX, R0 + ln, a), py(CY, R0 + ln, a))


def build():
    from device import COLOR_BLACK
    return {"background": COLOR_BLACK, "components": [DayRays()]}
