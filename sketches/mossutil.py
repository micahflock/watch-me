#!/usr/bin/env python3
"""mossutil -- shared bits for the moss-family cohesion sketches.

The first moss read as confetti because every grain was an independent point.
The cohesion lever is a SOLID substrate: a filled lumpy disc the texture then
sits on, so the patch reads as one organism. A filled disc is also CHEAP -- a
triangle fan is a handful of fillPolygon calls (native raster), far fewer
primitives than the equivalent stipple.

All integer math; fan() and edge() port to Monkey C verbatim (fillPolygon is a
real Toybox.Graphics 1.0 primitive and fills the convex triangles reliably).
"""

from device import idiv, imod, isin
from daybuckets import px, py


# Lumpy patch radius (px) at angle a for a base radius: base + two low
# undulations, so the rim is organic rather than a clean circle.
def edge(base, a):
    return base + idiv(8 * isin(imod(a * 3, 256)), 127) \
                + idiv(4 * isin(imod(a * 5 + 40, 256)), 127)


# Fill a lumpy disc centred at (cx, cy) out to edge(base,a)*scalepct/100, as a
# fan of `na` triangles. Caller sets the colour first. Returns nothing; ~na
# fillPolygon calls + 2*na isin.
def fan(dc, cx, cy, base, scalepct, na):
    e0 = idiv(edge(base, 0) * scalepct, 100)
    x0 = px(cx, e0, 0)
    y0 = py(cy, e0, 0)
    for i in range(1, na + 1):
        a = imod(idiv(i * 256, na), 256)
        e = idiv(edge(base, a) * scalepct, 100)
        x1 = px(cx, e, a)
        y1 = py(cy, e, a)
        dc.fillPolygon([[cx, cy], [x0, y0], [x1, y1]])
        x0 = x1
        y0 = y1
