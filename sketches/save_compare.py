#!/usr/bin/env python3
"""save_compare.py — quantify the parametric-skeleton save/load idea.

Runs a REAL simulated day through the shipped biobloom BioBloom, then computes
two save-payload sizes from the SAME live end-of-day dish:

  current     — what BioBloom.save() writes today (every-other skeleton vertex
                + tip, per the compact codec)
  parametric  — store each arm as (a0, L, next, v, np) + a packed colour-band
                list (run-length of the per-vertex colours), NO vertex dump;
                arms are regenerated from a0 by replaying the wiggle walk on load

Only the skeleton section differs; blooms/colony/header are identical, so the
delta isolates exactly the change under consideration. It also renders the
end-of-day dish next to the SAME dish after a parametric save->reload (arms
regenerated with a fixed amp) so the fidelity cost is visible.

    python3 sketches/save_compare.py [--day active|rest] [--seed N]
"""
import argparse
import importlib.util
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import device
from device import idiv, imod, isin, hash16, COLOR_DK_GRAY
from day import synthetic_day


def load_mod(name):
    path = os.path.join(HERE, "algos", name + ".py")
    spec = importlib.util.spec_from_file_location("algo_" + name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bb = load_mod("biobloom")
CX, CY, R0, STEP, UNIT = bb.CX, bb.CY, bb.R0, bb.STEP, bb.UNIT


class Tracked(bb.BioBloom):
    """biobloom BioBloom that also accretes, per arm, the seed angle a0 and a
    run-length colour-band list cb=[(rEnd, colour), ...] — exactly what the
    parametric codec would persist instead of the vertex dump. Live render is
    UNCHANGED (it still uses the cached pts), so in-session visuals are identical
    to the shipped face; only the save model differs."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fil:
            f["a0"] = f["a"]
            f["cb"] = [(R0, f["pts"][0][2])]

    def _grow_fil(self, f, move, vrange, color):
        n0 = len(f["pts"])
        super()._grow_fil(f, move, vrange, color)
        if len(f["pts"]) > n0:
            r_end = R0 + (len(f["pts"]) - 1) * STEP
            if f["cb"] and f["cb"][-1][1] == color:
                f["cb"][-1] = (r_end, color)
            else:
                f["cb"].append((r_end, color))

    def advance(self, snap):
        super().advance(snap)
        for f in self.fil:                 # tag any newly-branched arm
            if "a0" not in f:
                f["a0"] = f["a"]
                f["cb"] = [(R0, f["pts"][0][2])]


# ---- save-payload sizing (slot counts, mirrors BioBloom.save() exactly) ------

def _common_slots(bbm):
    """header + win + bloom + colony slots — identical in both codecs."""
    n = 1 + 20 + 1                              # magic + header/win + nfil
    n += 1                                      # nbloom
    for b in bbm.blooms:
        n += 10 + (len(b["bands"]) + 1) // 2    # 10 scalars + packed bands
    n += 2                                      # colreach, coln
    n += (len(bbm.colony["bands"]) + 1) // 2
    return n


def slots_current(bbm):
    n = _common_slots(bbm)
    for f in bbm.fil:
        np = len(f["pts"])
        n += 5 + np // 2 + 1                     # 5 scalars + every-other + tip
    return n


def slots_parametric(bbm):
    n = _common_slots(bbm)
    for f in bbm.fil:
        n += 5 + (len(f["cb"]) + 1) // 2         # 5 scalars + packed colour bands
    return n


def slots_parametric_nocolor(bbm):
    """Arms carry NO colour at all — coloured at render by the colony LUT
    (HR-zone vs radius), which already exists. Just 5 scalars per arm."""
    n = _common_slots(bbm)
    n += 5 * len(bbm.fil)
    return n


def slots_every_third(bbm):
    """Conservative, NO regeneration: store every 3rd vertex + tip instead of
    every 2nd; rebuild the two in-between by interpolation. Live look unchanged."""
    n = _common_slots(bbm)
    for f in bbm.fil:
        np = len(f["pts"])
        n += 5 + np // 3 + 2
    return n


# ---- parametric reload: regenerate arm vertices from (a0, np, cb) ------------

def _color_at(cb, rr):
    for (r_end, c) in cb:
        if rr <= r_end:
            return c
    return cb[-1][1]


def reconstruct_pts(a0, np, cb, amp=1):
    """Replay the wiggle walk from a0 (the codec drops the vertices), colouring
    each vertex from the band list. amp is fixed (the live walk used a
    HR-variability-driven amp we no longer store — this is the fidelity trade)."""
    pts = []
    a = a0
    for k in range(np):
        rr = R0 + k * STEP
        if k > 0:
            da = idiv(isin(hash16(a, rr, 1) & 255) * amp, 127)
            a = imod(a + da, 256)
        x = CX + idiv(rr * isin(a + 64), 127)
        y = CY + idiv(rr * isin(a), 127)
        pts.append((x, y, _color_at(cb, rr)))
    return a, pts


def _colony_lut(bbm):
    """radius -> colour from the colony bands (mirrors _fill_lut / drawFur)."""
    bands = bbm.colony["bands"]
    lut = [device.COLOR_DK_GRAY] * (bb.CR_MAX + 1)
    if not bands:
        return lut
    bi = 0
    n = len(bands)
    for r in range(bb.CR_MAX + 1):
        while bi < n and bands[bi][1] < r:
            bi += 1
        lut[r] = bands[bi][2] if bi < n else bands[n - 1][2]
    return lut


def reloaded_clone(bbm, amp=1, nocolor=False):
    """A clone with every arm's pts regenerated from (a0, np, cb) — what a
    parametric load() reconstructs. nocolor=True drops the stored colour bands
    and tints arms from the colony radius-LUT instead (the -52% variant)."""
    import copy
    c = copy.deepcopy(bbm)
    lut = _colony_lut(bbm) if nocolor else None
    for f in c.fil:
        cb = [(bb.CR_MAX, None)] if nocolor else f["cb"]
        a_end, pts = reconstruct_pts(f["a0"], len(f["pts"]), cb, amp)
        if nocolor:
            pts = [(x, y, lut[r] if (r := bb.R0 + k * STEP) <= bb.CR_MAX
                    else lut[bb.CR_MAX]) for k, (x, y, _) in enumerate(pts)]
        f["pts"] = pts
        f["a"] = a_end
    return c


def render(bbm, snap, scale=2):
    dc = device.Dc(device.COLOR_BLACK)
    bbm.render(dc, snap)
    return dc.masked().resize((device.W * scale, device.H * scale), Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="active")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "save-compare.png"))
    args = ap.parse_args()

    snaps = synthetic_day(seed=args.seed, profile=args.day)
    bbm = Tracked()

    checkpoints = {13 * 60 + 5: "13:05", 18 * 60 + 20: "18:20",
                   21 * 60 + 45: "21:45", 23 * 60 + 30: "23:30"}
    rows = []
    worst_cur = worst_par = 0
    for t in range(1440):
        bbm.advance(snaps[t])
        cur, par = slots_current(bbm), slots_parametric(bbm)
        worst_cur, worst_par = max(worst_cur, cur), max(worst_par, par)
        if t in checkpoints:
            nv = sum(len(f["pts"]) for f in bbm.fil)
            ncb = sum(len(f["cb"]) for f in bbm.fil)
            rows.append((checkpoints[t], len(bbm.fil), nv, ncb, cur, par))

    print("day=%s seed=%d  (%d arms max)" % (args.day, args.seed, bb.KMAX))
    print("%-7s %4s %6s %6s | %7s %9s %7s" %
          ("time", "arms", "verts", "cbands", "current", "parametric", "saved"))
    for (lab, na, nv, ncb, cur, par) in rows:
        print("%-7s %4d %6d %6d | %5d sl %7d sl %5d%%" %
              (lab, na, nv, ncb, cur, par, round(100 * (cur - par) / cur)))
    print("-" * 60)
    cur = slots_current(bbm)
    print("end-of-day save payload (slots / ~KB / vs current):")
    for lab, fn in (("current (ship)", slots_current),
                    ("parametric +colour bands", slots_parametric),
                    ("every-3rd vertex (no regen)", slots_every_third),
                    ("parametric, NO colour (colony LUT)", slots_parametric_nocolor)):
        v = fn(bbm)
        print("  %-36s %4d sl  ~%.1f KB  -%d%%"
              % (lab, v, v * 5 / 1024, round(100 * (cur - v) / cur)))

    # Fidelity: end-of-day dish vs the same dish after a parametric save->reload,
    # sweeping the regeneration amp to see if the organic wander is recoverable.
    end = snaps[23 * 60 + 30]
    panels = [
        ("original (ship, -0%)", render(bbm, end)),
        ("parametric +colour, amp3 (-19%)",
         render(reloaded_clone(bbm, 3), end)),
        ("parametric NO colour, amp3 (-52%)",
         render(reloaded_clone(bbm, 3, nocolor=True), end)),
    ]
    pw, ph = panels[0][1].size
    pad = 8
    W = len(panels) * pw + (len(panels) + 1) * pad
    H = ph + pad * 2 + 14
    strip = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(strip)
    for i, (lab, img) in enumerate(panels):
        x = pad + i * (pw + pad)
        strip.paste(img, (x, pad))
        d.text((x, pad + ph + 2), lab, fill=(230, 230, 230))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    strip.save(args.out)
    print("fidelity strip -> %s" % args.out)


if __name__ == "__main__":
    main()
