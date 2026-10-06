#!/usr/bin/env python3
"""alt_faces.py -- render the alternate-face concepts (sketches/algos/alt_*.py)
for review. Brief and concept notes: docs/alt-faces.md.

    python3 sketches/alt_faces.py                 # every concept + overview
    python3 sketches/alt_faces.py ledger vessel   # just these concept sheets
    python3 sketches/alt_faces.py --overview      # only the side-by-side

Each concept is an ordinary sandbox algo (build() -> components with
advance/render), so `scrub.py alt_<name>` works on it too; this driver adds
what scrub.py can't do: a TWO-day replay (last night's sleep starts the
evening before), the owner-like simulated days in altkit (weekday / hike /
restless / rest), and review sheets with a short legend per concept.

Output: sketches/out/alt/<name>.png (sheet) and sketches/out/alt/overview.png.
"""

import importlib.util
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import altkit as K   # noqa: E402
import device as dev  # noqa: E402

OUT = os.path.join(HERE, "out", "alt")
CONCEPTS = ["ledger", "murmuration", "cascade", "mosaic", "vessel", "galaxy"]

DAY_TIMES = ["6:45", "10:30", "13:30", "18:30", "22:45"]
RANGE = [("hike", "16:00"), ("restless", "7:20"), ("rest", "21:00")]

_FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu"]


def _font(bold, size):
    for d, f in ((_FONT_DIRS[0], "Inter-Bold.otf" if bold else "Inter-Regular.otf"),
                 (_FONT_DIRS[1], "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        p = os.path.join(d, f)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load(name):
    path = os.path.join(HERE, "algos", "alt_" + name + ".py")
    spec = importlib.util.spec_from_file_location("alt_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def render_at(mod, profile, times, scale=2, overrides=None):
    """Replay `profile` (2 days) and render the concept at each local time of
    the second day. Returns [(time, img, vm, calls, off, state)]."""
    spec = mod.build()
    comps = spec["components"]
    want = {_mins(t): t for t in times}
    out = []
    for snap, today in K.day_feed(profile):
        if overrides:
            for k, v in overrides.items():
                setattr(snap, k, v)
        for c in comps:
            if hasattr(c, "advance"):
                c.advance(snap)
        t = snap.hour * 60 + snap.minute
        if today and t in want:
            dc = dev.Dc(spec.get("background", dev.COLOR_BLACK))
            dev.perf_reset()
            for c in comps:
                c.render(dc, snap)
            nh, ns, nops = dev.perf_read()
            vm = (dc.calls * dev.VM_PRIM + nh * dev.VM_HASH16
                  + ns * dev.VM_ISIN + nops * dev.VM_OP)
            sb = sum(c.state_bytes() for c in comps if hasattr(c, "state_bytes"))
            img = dc.masked().resize((K.W * scale, K.H * scale), Image.NEAREST)
            out.append((want[t], img, vm, dc.calls, dc.offpalette, sb))
    return out


def concept_sheet(name, scale=2):
    mod = load(name)
    title = getattr(mod, "TITLE", name)
    blurb = getattr(mod, "BLURB", "")
    legend = getattr(mod, "LEGEND", [])
    fB, fR, fS, fT = _font(True, 19), _font(False, 15), _font(False, 13), _font(True, 26)
    fw, fh = K.W * scale, K.H * scale
    pad, cap = 14, 40
    row1 = render_at(mod, "weekday", DAY_TIMES, scale)
    row2 = []
    for prof, t in RANGE:
        row2 += [(prof,) + r for r in render_at(mod, prof, [t], scale)]
    cols = max(len(row1), len(row2) + 1)
    Wd = pad + cols * (fw + pad)
    Hd = 96 + 2 * (fh + cap + 30) + pad
    sheet = Image.new("RGB", (Wd, Hd), (22, 22, 24))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), title, font=fT, fill=(240, 240, 240))
    d.text((pad, 50), blurb, font=fR, fill=(185, 185, 185))
    y = 84
    d.text((pad, y), "A weekday (bed 23:00, woke once at 3:11, commute + lunch walks, evening run)",
           font=fB, fill=(225, 225, 225))
    y += 28
    peak = 0
    for i, (t, img, vm, calls, off, sb) in enumerate(row1):
        x = pad + i * (fw + pad)
        sheet.paste(img, (x, y))
        peak = max(peak, vm)
        d.text((x + 2, y + fh + 5), "%s   ~%d VMi%s" % (t, vm, "  OFF-PAL %d" % off if off else ""),
               font=fS, fill=(150, 150, 150))
    y += fh + cap
    d.text((pad, y), "Other days", font=fB, fill=(225, 225, 225))
    y += 28
    labels = {"hike": "Saturday hike", "restless": "3 wake-ups, battery 12%", "rest": "lie-in, 5.8k steps"}
    for i, (prof, t, img, vm, calls, off, sb) in enumerate(row2):
        x = pad + i * (fw + pad)
        sheet.paste(img, (x, y))
        peak = max(peak, vm)
        d.text((x + 2, y + fh + 5), "%s %s   ~%d VMi" % (labels.get(prof, prof), t, vm),
               font=fS, fill=(150, 150, 150))
    # legend in the last column of row 2
    lx = pad + len(row2) * (fw + pad)
    ly = y
    d.text((lx, ly), "How to read it", font=fB, fill=(235, 235, 235))
    ly += 28
    for line in legend:
        d.text((lx, ly), line, font=fR, fill=(200, 200, 200))
        ly += 20
    ly += 8
    d.text((lx, ly), "peak ~%d VM-instr/frame (watchdog ~25k)" % peak, font=fS, fill=(140, 140, 140))
    d.text((lx, ly + 18), "state ~%d B" % row1[-1][5], font=fS, fill=(140, 140, 140))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    sheet.save(path)
    return path, peak


def overview(names, times=("7:05", "18:30"), scale=2):
    fB, fR, fT = _font(True, 20), _font(False, 14), _font(True, 26)
    fw, fh = K.W * scale, K.H * scale
    pad = 14
    cols = len(names)
    Wd = pad + cols * (fw + pad)
    Hd = 60 + len(times) * (fh + 30) + 60
    sheet = Image.new("RGB", (Wd, Hd), (22, 22, 24))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), "Alternate faces, round 1: the same weekday at %s" % " and ".join(times),
           font=fT, fill=(240, 240, 240))
    for c, name in enumerate(names):
        mod = load(name)
        frames = render_at(mod, "weekday", list(times), scale)
        x = pad + c * (fw + pad)
        for r, (t, img, vm, calls, off, sb) in enumerate(frames):
            yy = 60 + r * (fh + 30)
            sheet.paste(img, (x, yy))
            d.text((x + 2, yy + fh + 5), t, font=fR, fill=(150, 150, 150))
        d.text((x + 2, 60 + len(times) * (fh + 30)), getattr(mod, "TITLE", name).split(" -- ")[0],
               font=fB, fill=(235, 235, 235))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "overview.png")
    sheet.save(path)
    return path


def main(argv):
    names = [a for a in argv if not a.startswith("--")]
    only_over = "--overview" in argv
    todo = names or CONCEPTS
    if not only_over:
        for n in todo:
            path, peak = concept_sheet(n)
            print("%-12s -> %s  (peak ~%d VMi)" % (n, os.path.relpath(path), peak))
    if only_over or not names:
        avail = [n for n in CONCEPTS if os.path.exists(os.path.join(HERE, "algos", "alt_%s.py" % n))]
        print("overview     ->", os.path.relpath(overview(avail)))


if __name__ == "__main__":
    main(sys.argv[1:])
