#!/usr/bin/env python3
"""biobloom_poly -- node shapes as lumpy filled POLYGONS ("lichen / crystal"),
banded in nested colour layers, plus a colony that is a filled amorphous polygon
hugging the arm tips. Definitively "not circles". Same growth engine as
biobloom.py; only render() is swapped.

Cheap by construction: each node has ONE jittered unit outline, computed once
and cached, then drawn as a triangle-fan (each triangle convex, so it ports to
the device's fillPolygon faithfully). No per-dot hash16/isin at render time.

Sandbox prototype for evaluating watchdog-safe node shapes; parity with the
shipped face is intentionally NOT maintained.
"""
import importlib.util
import os

from device import idiv, imod, isin, hash16, COLOR_BLACK

_spec = importlib.util.spec_from_file_location(
    "bb_base_poly", os.path.join(os.path.dirname(__file__), "biobloom.py"))
_bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bb)
BioBloom = _bb.BioBloom
CX, CY, R0, TRAIL, UNIT = _bb.CX, _bb.CY, _bb.R0, _bb.TRAIL, _bb.UNIT

KOUT = 10            # lumpy outline vertices per node


class BioBloomPoly(BioBloom):

    # one jittered unit outline per bloom (dx, dy unit*127, radius factor 72..127),
    # computed once and cached on the bloom -> no per-frame RNG
    def _outline(self, b):
        o = b.get("outline")
        if o is None:
            o = []
            salt = b["salt"]
            for k in range(KOUT):
                a = imod(idiv(k * 256, KOUT)
                         + imod(hash16(salt, k, 2), 22) - 11, 256)
                jf = 72 + imod(hash16(salt, k, 3), 56)
                o.append((isin(a + 64), isin(a), jf))
            b["outline"] = o
        return o

    def _fan(self, dc, cx, cy, rr, outline):
        prev = None
        first = None
        for (dx, dy, jf) in outline:
            vx = cx + idiv(rr * jf * dx, 12700)        # rr * (jf/100) * (d/127)
            vy = cy + idiv(rr * jf * dy, 12700)
            if prev is not None:
                dc.fillPolygon([[cx, cy], [prev[0], prev[1]], [vx, vy]])
            if first is None:
                first = (vx, vy)
            prev = (vx, vy)
        if prev is not None and first is not None:
            dc.fillPolygon([[cx, cy], [prev[0], prev[1]], [first[0], first[1]]])

    def _draw_bloom(self, dc, b):
        bands = b["bands"]
        if not bands:
            return
        ang = b["ang"]
        fx, fy = isin(ang + 64), isin(ang)
        reach, w = b["reach"], b["w"]
        # blob centre sits partway out along the arm so it grows OUTWARD
        cx = b["bx"] + idiv(idiv(reach, 2) * fx, 127)
        cy = b["by"] + idiv(idiv(reach, 2) * fy, 127)
        outline = self._outline(b)
        rad = idiv(reach, 2) + w + 2
        nlayer = 3                                    # rim -> mid -> core bands
        li = 0
        while li < nlayer:
            frac = idiv((nlayer - li) * 100, nlayer)  # 100, 66, 33
            rr = idiv(rad * frac, 100)
            if rr < 2:
                rr = 2
            col = self._band_color(b, idiv(reach * frac, 100))
            dc.setColor(col, COLOR_BLACK)
            self._fan(dc, cx, cy, rr, outline)
            li += 1

    def _draw_colony(self, dc):
        col = self.colony
        bands = col["bands"]
        if not bands:
            return
        arms = sorted(self.fil, key=lambda f: f["a"])  # order around the dish
        n = 5                                           # downsampled colour layers
        layers = []
        i = 0
        while i < n:
            idx = idiv((len(bands) - 1) * (n - 1 - i), n - 1)
            layers.append((bands[idx][1], bands[idx][2]))  # (radius, color)
            i += 1
        for (lr, color) in layers:                      # rim -> core
            dc.setColor(color, COLOR_BLACK)
            prev = None
            first = None
            for f in arms:
                armlim = idiv(f["L"], UNIT) - TRAIL
                rr = lr if armlim >= lr else armlim
                if rr < R0:
                    rr = R0
                vx = CX + idiv(rr * isin(f["a"] + 64), 127)
                vy = CY + idiv(rr * isin(f["a"]), 127)
                if prev is not None:
                    dc.fillPolygon([[CX, CY], [prev[0], prev[1]], [vx, vy]])
                if first is None:
                    first = (vx, vy)
                prev = (vx, vy)
            if prev is not None and first is not None:
                dc.fillPolygon([[CX, CY], [prev[0], prev[1]],
                                [first[0], first[1]]])


def build():
    return {"background": COLOR_BLACK, "components": [BioBloomPoly()]}
