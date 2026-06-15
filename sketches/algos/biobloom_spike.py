#!/usr/bin/env python3
"""biobloom_spike -- node shapes as a BURST OF SPINES (sea-urchin / dendrite)
instead of a stipple cloud. Each bloom fires a fan of gently bowed, sometimes
forking spines outward along its arm, every spine coloured by the HR-zone band
at its tip; the central colony grows a short outward "fur" along the skeleton.
Same growth engine as biobloom.py; only render() is swapped.

Cheap: a spine is two short drawLines (a slight bow reads organic, not a spoke);
the fan's angles/lengths/bow are precomputed ONCE per node and just scaled by the
bloom's reach as it grows -- no per-dot hash16/isin at render time.

Sandbox prototype for evaluating watchdog-safe node shapes; parity with the
shipped face is intentionally NOT maintained.
"""
import importlib.util
import os

from device import idiv, imod, isin, hash16, COLOR_BLACK

_spec = importlib.util.spec_from_file_location(
    "bb_base_spike", os.path.join(os.path.dirname(__file__), "biobloom.py"))
_bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bb)
BioBloom = _bb.BioBloom
CX, CY, R0, TRAIL, UNIT, STEP, BASE = (
    _bb.CX, _bb.CY, _bb.R0, _bb.TRAIL, _bb.UNIT, _bb.STEP, _bb.BASE)


class BioBloomSpike(BioBloom):

    def _draw_bloom(self, dc, b):
        bands = b["bands"]
        if not bands:
            return
        ang, reach, w, salt = b["ang"], b["reach"], b["w"], b["salt"]
        sp = b.get("spikes")
        if sp is None:                                 # fan shape, computed once
            nsp = 6 + imod(hash16(salt, 1, 1), 6)      # 6..11 spines
            sp = []
            for k in range(nsp):
                off = imod(hash16(salt, k, 4), 121) - 60    # +-60/256 ~ +-84 deg
                lf = 90 + imod(hash16(salt, k, 5), 166)     # 90..255 of reach
                bow = imod(hash16(salt, k, 7), 13) - 6      # -6..6 px sideways
                fork = imod(hash16(salt, k, 6), 2) == 0     # ~half branch
                sp.append((off, lf, bow, fork))
            b["spikes"] = sp
        bx, by = b["bx"], b["by"]
        dc.setColor(self._band_color(b, BASE), COLOR_BLACK)
        dc.fillCircle(bx, by, 1 + idiv(w, 8))          # tiny anchor node (1..3px)
        for (off, lf, bow, fork) in sp:
            a2 = imod(ang + off, 256)
            dx, dy = isin(a2 + 64), isin(a2)
            px, py = isin(a2 + 128), isin(a2 + 64)     # perpendicular (bow)
            tip = BASE + idiv((reach - BASE) * lf, 256)
            mr = idiv(tip, 2)
            mx = bx + idiv(mr * dx, 127) + idiv(bow * px, 127)
            my = by + idiv(mr * dy, 127) + idiv(bow * py, 127)
            ex = bx + idiv(tip * dx, 127)
            ey = by + idiv(tip * dy, 127)
            dc.setColor(self._band_color(b, tip), COLOR_BLACK)
            dc.drawLine(bx, by, mx, my)                # bowed spine = 2 segments
            dc.drawLine(mx, my, ex, ey)
            if fork:                                    # branch from the elbow
                a3 = imod(a2 + (24 if (off & 1) == 0 else -24), 256)
                fr = idiv(tip, 3)
                dc.drawLine(mx, my, mx + idiv(fr * isin(a3 + 64), 127),
                            my + idiv(fr * isin(a3), 127))

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
            pts, a = f["pts"], f["a"]
            k = 2
            while k < len(pts):
                rr = R0 + k * STEP
                if rr > lim:
                    break
                if (k % 3) == 0:                        # short outward "fur" spine
                    x, y, _ = pts[k]
                    dc.setColor(self._band_color(col, rr), COLOR_BLACK)
                    a2 = imod(a + k * 13, 256)
                    le = 3 + imod(k, 4)                 # 3..6 px
                    dc.drawLine(x, y, x + idiv(le * isin(a2 + 64), 127),
                                y + idiv(le * isin(a2), 127))
                k += 1


def build():
    return {"background": COLOR_BLACK, "components": [BioBloomSpike()]}
