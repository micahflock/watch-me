#!/usr/bin/env python3
"""biobloom_lobe -- node shapes as a few OVERLAPPING jittered discs ("soft
coral") instead of a per-dot stipple cloud. Same growth engine as biobloom.py
(skeleton / colony / blooms grow identically); only render() is swapped. The
overlapping circles of varied radius give a bumpy, non-circular silhouette at a
fraction of the cost -- a handful of fillCircle per node, almost no RNG.

This is a sandbox prototype for evaluating cheaper, watchdog-safe node shapes;
parity with the shipped face is intentionally NOT maintained.
"""
import importlib.util
import os

from device import idiv, imod, isin, hash16, COLOR_BLACK

_spec = importlib.util.spec_from_file_location(
    "bb_base_lobe", os.path.join(os.path.dirname(__file__), "biobloom.py"))
_bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bb)
BioBloom = _bb.BioBloom
CX, CY, R0, TRAIL, UNIT, CW, STEP = (
    _bb.CX, _bb.CY, _bb.R0, _bb.TRAIL, _bb.UNIT, _bb.CW, _bb.STEP)


class BioBloomLobe(BioBloom):

    def _draw_bloom(self, dc, b):
        bands = b["bands"]
        if not bands:
            return
        ang = b["ang"]
        fx, fy = isin(ang + 64), isin(ang)
        px, py = isin(ang + 128), isin(ang + 64)
        reach, w, salt = b["reach"], b["w"], b["salt"]
        nlob = 3 + imod(hash16(salt, 0, 5), 3)        # 3..5 overlapping lobes
        j = 0
        while j < nlob:
            lf = idiv((j + 1) * 230, nlob + 1) + imod(hash16(salt, j, 6), 26)
            along = idiv(reach * lf, 256)
            po = imod(hash16(salt, j, 7), 2 * w + 1) - w
            lx = b["bx"] + idiv(along * fx, 127) + idiv(po * px, 127)
            ly = b["by"] + idiv(along * fy, 127) + idiv(po * py, 127)
            lr = 2 + idiv(w * (nlob - j), nlob)        # outer lobes smaller
            dc.setColor(self._band_color(b, along), COLOR_BLACK)
            dc.fillCircle(lx, ly, lr)
            # two smaller satellite bumps -> lumpy, non-circular edge
            k = 0
            while k < 2:
                ox = imod(hash16(salt, j * 5 + k, 8), 2 * lr + 1) - lr
                oy = imod(hash16(salt, j * 5 + k, 9), 2 * lr + 1) - lr
                dc.fillCircle(lx + ox, ly + oy, 1 + idiv(lr, 2))
                k += 1
            j += 1

    def _draw_colony(self, dc):
        col = self.colony
        if not col["bands"]:
            return
        dc.setColor(col["bands"][0][2], COLOR_BLACK)
        dc.fillCircle(CX, CY, R0 + 1)
        reach = col["reach"]
        for f in self.fil:
            lim = idiv(f["L"], UNIT) - TRAIL
            if lim > reach:
                lim = reach
            if lim <= R0:
                continue
            pts = f["pts"]
            k = 2
            while k < len(pts):
                rr = R0 + k * STEP
                if rr > lim:
                    break
                if (k % 4) == 0:                       # sparser than stipple
                    x, y, _ = pts[k]
                    dc.setColor(self._band_color(col, rr), COLOR_BLACK)
                    dc.fillCircle(x, y, CW)            # one blob vs two dots
                k += 1


def build():
    return {"background": COLOR_BLACK, "components": [BioBloomLobe()]}
