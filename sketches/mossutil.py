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

from device import idiv, imod, isin, hash16
from daybuckets import px, py

# Outline of the OLD fixed shape, kept as the default so the earlier moss algos
# render unchanged: (phase1, phase2, freq1, freq2, amp1, amp2). shape_params()
# now returns a longer tuple (+ tilt phase/amp, per-lobe amp percents); edge()
# accepts both.
DEFAULT_SP = (0, 40, 3, 5, 8, 4)


# Per-DAY shape parameters, derived once from the seed and passed into edge()/fan()
# (hoisted so the per-vertex cost is just arithmetic + isin, not hash16 each
# call). Varying phase/frequency/amplitude per day makes the cushion a noticeably
# different lumpy outline every day -- the day-to-day variability lever.
#
# Tip lengths must NOT be uniform (owner call, 2026-07): each lobe's amplitude
# is hashed to 40..170% (switched at the sine zero-crossings, so the outline
# stays continuous) and a frequency-1 "tilt" sinusoid stretches one side of the
# patch. Together these also de-rigidify the 4-lobe cross, so 4 is allowed in
# the lobe range again. f2 stays in {5,7}: 4/6 beat against f1, and higher
# primes alias against the NA=30 rim samples.
def shape_params(seed):
    p1 = imod(hash16(seed, 1, 3), 256)
    p2 = imod(hash16(seed, 2, 3), 256)
    f1 = 2 + imod(hash16(seed, 3, 3), 4)          # 2..5 lobes (broad asymmetry)
    f2 = (5, 7)[imod(hash16(seed, 4, 3), 2)]      # finer ripple
    am1 = 7 + imod(hash16(seed, 5, 3), 7)         # 7..13 (how lumpy)
    am2 = 3 + imod(hash16(seed, 6, 3), 4)         # 3..6
    p3 = imod(hash16(seed, 7, 3), 256)            # tilt phase
    am3 = 4 + imod(hash16(seed, 8, 3), 5)         # 4..8 tilt amplitude
    lamp = tuple(40 + imod(hash16(seed, 16 + k, 5), 131)   # 40..170% per lobe
                 for k in range(f1))
    return (p1, p2, f1, f2, am1, am2, p3, am3, lamp)


# Lumpy patch radius (px) at angle a for a base radius: base + two undulations
# (+ per-lobe amplitude and the frequency-1 tilt when sp carries them).
# Pass a shape_params tuple `sp` for per-day variation; default = the old shape.
def edge(base, a, sp=DEFAULT_SP):
    ph1 = a * sp[2] + sp[0]
    am1 = sp[4]
    if len(sp) > 6:
        am1 = idiv(am1 * sp[8][imod(idiv(ph1, 256), sp[2])], 100)
    e = base + idiv(am1 * isin(imod(ph1, 256)), 127) \
             + idiv(sp[5] * isin(imod(a * sp[3] + sp[1], 256)), 127)
    if len(sp) > 6:
        e += idiv(sp[7] * isin(imod(a + sp[6], 256)), 127)
    return e


# Fill a lumpy disc centred at (cx, cy) out to edge(base,a)*scalepct/100, as a
# fan of `na` triangles. Caller sets the colour first. ~na fillPolygon + 2*na isin.
def fan(dc, cx, cy, base, scalepct, na, sp=DEFAULT_SP):
    e0 = idiv(edge(base, 0, sp) * scalepct, 100)
    x0 = px(cx, e0, 0)
    y0 = py(cy, e0, 0)
    for i in range(1, na + 1):
        a = imod(idiv(i * 256, na), 256)
        e = idiv(edge(base, a, sp) * scalepct, 100)
        x1 = px(cx, e, a)
        y1 = py(cy, e, a)
        dc.fillPolygon([[cx, cy], [x0, y0], [x1, y1]])
        x0 = x1
        y0 = y1
