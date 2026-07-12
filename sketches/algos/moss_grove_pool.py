#!/usr/bin/env python3
"""moss_grove_pool -- sleep-nucleus PROPOSAL A for two-worlds V2: the tarn.

Same organism as moss_grove (loaded from it; only the sleep drawing differs).
The shipped clump renders short/restless nights as warm red/orange filled dots
-- the exact vocabulary of the effort beads (warm filled circles out on the
rim), so at a glance last night reads as a workout (owner, 2026-07). Fix by
giving sleep its own shape grammar AND its own palette region: effort keeps the
warm hues; sleep speaks night-water blues, grays and white.

Last night is a still POOL at the heart of the moss:

  hours slept  -> pool size and RING COUNT: one two-blue concentric ring per
                  hour, tree-ring style, so the night is literally countable
                  (4 h = a small 4-ring puddle, 8 h = a wide calm tarn)
  wake events  -> the loved white specks stay, but each sits in a black BITE
                  carved out of the pool rim (disturbance, not effort), and
                  each wake also clouds one ring DK_GRAY
  quality      -> structural: unbroken blue rings = rested; a small, bitten,
                  clouded pool = a rough night. No warm hue anywhere.

Blues stay unambiguous: episode beads exist only for zones >= ACTIVE, which are
all warm (YELLOW..PURPLE), and nothing else on the face is a concentric ring.
Cheaper than the clump it replaces: nested fillCircle discs, no per-dot hash16.
All radii below are FINAL px (already scaled), like the episode bead radius.
"""
import importlib.util
import os

from device import (idiv, imod, hash16, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_WHITE, COLOR_BLUE, COLOR_DK_BLUE, COLOR_DK_GRAY)
from daybuckets import px, py

_p = os.path.join(os.path.dirname(__file__), "moss_grove.py")
_spec = importlib.util.spec_from_file_location("moss_grove", _p)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CX, CY = mg.CX, mg.CY

CORE_R = 4           # innermost disc radius
RING_W = 3           # one ring's thickness; one ring per hour slept
POOL_MAX_H = 10      # SLEEP_CAP is 600 min


def pool_hours(mins):
    h = idiv(mins, 60)
    if h < 1:
        h = 1
    if h > POOL_MAX_H:
        h = POOL_MAX_H
    return h


class MossGrovePool(mg.MossGrove):

    # episode keep-out: beads stay clear of the pool and its rim specks. The
    # rings are COUNTED, so unlike the ship clump an overlapping bead is data
    # loss. A bead's centre sits up to tsize/2+2 (<=16) inside its tuft radius
    # and reaches bead_r (<=18) further in; the render adds scl(6) back, so
    # +27 here means even the worst-case bead only kisses the outer ring.
    def spore_reach(self, mins, wakes):
        if mins <= 0:
            return 0
        return CORE_R + RING_W * pool_hours(mins) + 27

    def draw_spore(self, dc, mins, wakes, ink):
        if mins <= 0:
            return ink
        hours = pool_hours(mins)
        pr = CORE_R + RING_W * hours

        # each wake clouds one ring gray, spread evenly across the levels so
        # clouded rings never merge into one thick band (alternation survives
        # and the rings stay countable)
        cloudy = 0
        for w in range(wakes):
            cloudy |= 1 << (1 + imod(idiv(w * hours, wakes), hours))

        # nested discs, outermost first: each level leaves a RING_W annulus of
        # its colour behind the next disc; parity alternation = tree rings
        for h in range(hours, 0, -1):
            if (cloudy >> h) & 1:
                col = COLOR_DK_GRAY
            else:
                col = COLOR_DK_BLUE if (h & 1) else COLOR_BLUE
            dc.setColor(col, COLOR_TRANSPARENT)
            dc.fillCircle(CX, CY, CORE_R + RING_W * h)
            ink -= 1
        dc.setColor(COLOR_BLUE if (hours & 1) else COLOR_DK_BLUE,
                    COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, CORE_R)
        ink -= 1

        # each wake: a black bite carved into the rim with the white speck at
        # its mouth (the specks are the piece the owner asked to keep)
        if wakes > 0:
            wr = 2                         # white core (ship speck size)
            br = wr + 3                    # black separation ring
            for w in range(wakes):
                if ink <= 0:
                    break
                hw = hash16(53, w, 7)
                wa = imod(idiv(w * 256, wakes) + (hw % 24), 256)
                depth = idiv(pr * 2, 5)
                if depth < 5:
                    depth = 5
                da = 3 + idiv(200, pr)     # mouth half-width in angle units
                dc.setColor(COLOR_BLACK, COLOR_TRANSPARENT)
                dc.fillPolygon([
                    (px(CX, pr - depth, wa), py(CY, pr - depth, wa)),
                    (px(CX, pr + 2, wa - da), py(CY, pr + 2, wa - da)),
                    (px(CX, pr + 2, wa + da), py(CY, pr + 2, wa + da))])
                dc.fillCircle(px(CX, pr, wa), py(CY, pr, wa), br)
                dc.setColor(COLOR_WHITE, COLOR_TRANSPARENT)
                dc.fillCircle(px(CX, pr, wa), py(CY, pr, wa), wr)
                ink -= 3
        return ink


def build():
    return {"background": mg.COLOR_BLACK, "components": [MossGrovePool()]}
