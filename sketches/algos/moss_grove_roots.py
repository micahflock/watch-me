#!/usr/bin/env python3
"""moss_grove_roots -- sleep-nucleus PROPOSAL B for two-worlds V2: the roots.

Same organism as moss_grove (loaded from it; only the sleep drawing differs).
Motivation as in moss_grove_pool: the shipped spore clump renders short nights
in the effort beads' warm-filled-circle vocabulary. Here sleep gets a shape
NOTHING else on the face uses -- thin radiating lines -- plus the night
palette (silver/blue/gray), so it cannot be mistaken for an effort bead.

Last night is the ROOT SYSTEM the day's growth stands on, a silver star
under the heart of the moss:

  hours slept  -> root count and length: a long night is a wide, well-anchored
                  star (6 + hours roots, length grows 3 px/hour)
  wake events  -> the loved white specks stay: each wake SNAPS one root -- it
                  stops short at a white speck (black-ringed, ship-style) --
                  and every wake kinks ALL the roots harder (a rough night is
                  a crooked, broken star)
  quality      -> structural + palette: straight silver roots with deep-blue
                  nodule tips = rested; a gnarled gray tangle = a rough night.
                  No warm hue anywhere.

Cost is line work: (6+hours) roots x 2 segments + a tip nodule each, ~3 hash16
per root -- comparable to the clump it replaces. Radii/lengths are FINAL px
(already scaled), like the episode bead radius.
"""
import importlib.util
import os

from device import (idiv, imod, hash16, isin, COLOR_TRANSPARENT, COLOR_BLACK,
                    COLOR_WHITE, COLOR_LT_GRAY, COLOR_DK_GRAY, COLOR_BLUE,
                    COLOR_DK_BLUE)
from daybuckets import px, py

_p = os.path.join(os.path.dirname(__file__), "moss_grove.py")
_spec = importlib.util.spec_from_file_location("moss_grove", _p)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CX, CY = mg.CX, mg.CY

ROOT_MAX_H = 10      # SLEEP_CAP is 600 min


def root_hours(mins):
    h = idiv(mins, 60)
    if h < 1:
        h = 1
    if h > ROOT_MAX_H:
        h = ROOT_MAX_H
    return h


def root_len(mins):
    return 8 + 3 * root_hours(mins)


class MossGroveRoots(mg.MossGrove):

    # episode keep-out: beads stay clear of the root star's spread. A bead's
    # centre can sit tsize/2+2 inside its tuft radius and reach bead_r further
    # in (see moss_grove_pool); +20 keeps the tips -- the hours signal --
    # legible without pushing small beads to the horizon.
    def spore_reach(self, mins, wakes):
        if mins <= 0:
            return 0
        return root_len(mins) + 20

    def draw_spore(self, dc, mins, wakes, ink):
        if mins <= 0:
            return ink
        hours = root_hours(mins)
        ln = root_len(mins)
        nroots = 6 + hours
        kink = 3 + wakes * 6           # angle jitter at the joints (1/256ths)

        # taproot crown grounding the star
        dc.setColor(COLOR_DK_BLUE, COLOR_TRANSPARENT)
        dc.fillCircle(CX, CY, 3)
        ink -= 1

        for i in range(nroots):
            if ink <= 0:
                break
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
            # each wake snaps one root (evenly spread, distinct while
            # wakes <= nroots): it ends at its joint under the white speck
            snapped = False
            for w in range(wakes):
                if idiv(w * nroots, wakes) == i:
                    snapped = True
                    break
            dc.setColor(COLOR_DK_GRAY if snapped else COLOR_LT_GRAY,
                        COLOR_TRANSPARENT)
            dc.drawLine(x0, y0, xm, ym)
            ink -= 1
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
                ink -= 4
            else:
                xt = px(CX, li, a2)
                yt = py(CY, li, a2)
                dc.drawLine(xm, ym, xt, yt)
                # nodule tip: deep blue when rested, gray on a rough night
                dc.setColor(COLOR_BLUE if wakes == 0 else COLOR_DK_GRAY,
                            COLOR_TRANSPARENT)
                dc.fillCircle(xt, yt, 1)
                ink -= 2
        return ink


def build():
    return {"background": mg.COLOR_BLACK, "components": [MossGroveRoots()]}
