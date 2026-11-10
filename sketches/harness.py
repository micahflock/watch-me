"""harness.py -- the plumbing every sandbox script shares.

One home for what used to be copied from script to script: turning "7:50"
into a minute of the day, loading an algo module, summing the watchdog proxy
for a rendered frame, and laying frames out as a captioned comparison sheet.

    from harness import OUT, load_algo, mins, render, cell, sheet

load_algo() takes a bare name or a path. Names resolve in sketches/algos
first (the mirrors of the engines in core/src/genart) and then in
archive/sketches/algos (retired experiments), so `scrub.py nebula` still
renders an archived algo without it living in the working set.
"""

import importlib.util
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import device

OUT = os.path.join(HERE, "out")
ARCHIVE = os.path.join(REPO, "archive", "sketches")
ALGO_DIRS = [os.path.join(HERE, "algos"), os.path.join(ARCHIVE, "algos")]


def mins(s):
    """"7:50" -> 470."""
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def hm(t):
    """470 -> "07:50"."""
    return "{:02d}:{:02d}".format(t // 60, t % 60)


def algo_path(name):
    """Path of algo `name` (a bare name, or a path to a .py file)."""
    if name.endswith(".py") or os.sep in name:
        if os.path.exists(name):
            return os.path.abspath(name)
        sys.exit("no such algo file: {}".format(name))
    for d in ALGO_DIRS:
        path = os.path.join(d, name + ".py")
        if os.path.exists(path):
            return path
    sys.exit("no such algo: {} (looked in {})".format(
        name, ", ".join(os.path.relpath(d, REPO) for d in ALGO_DIRS)))


def load_algo(name):
    """A FRESH module object per call, so a comparison script can patch one
    copy's constants without touching another's. Archived algos import their
    archived helpers (grove_base), so their directory joins sys.path."""
    path = algo_path(name)
    if path.startswith(ARCHIVE + os.sep) and ARCHIVE not in sys.path:
        sys.path.append(ARCHIVE)
    stem = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location("algo_" + stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build"):
        sys.exit("algo {} must define build()".format(stem))
    return mod


def vm_work(dc):
    """Watchdog proxy for the frame just drawn on `dc`: estimated VM
    INSTRUCTIONS, not a raw primitive count (hash16/isin are real function
    calls and usually dominate; nops is inner-loop / band-scan work -- see
    device.account()). Call device.perf_reset() before rendering. A loose
    LOWER BOUND: docs/watchdog-debugging.md."""
    nh, ns, nops = device.perf_read()
    return (dc.calls * device.VM_PRIM + nh * device.VM_HASH16
            + ns * device.VM_ISIN + nops * device.VM_OP)


def render(spec, snap, scale=2):
    """Render a build() spec for one Snapshot -> (image, work, dc)."""
    dc = device.Dc(spec.get("background", device.COLOR_BLACK))
    device.perf_reset()
    for c in spec["components"]:
        if hasattr(c, "render"):
            c.render(dc, snap)
    work = vm_work(dc)
    img = dc.masked().resize((device.W * scale, device.H * scale),
                             Image.NEAREST)
    return img, work, dc


def cell(img, work):
    """A sheet cell: the image and its watchdog-proxy caption."""
    wd = "OK" if work <= device.WATCHDOG else "OVER"
    return (img, "~{} VMi [{}]".format(work, wd))


def sheet(rows, col_labels, path, title, lab=110):
    """Save a comparison sheet. rows: [(row_label, [(img, caption), ...])];
    `lab` is the width of the row-label gutter."""
    fw, fh = rows[0][1][0][0].size
    pad, caph, hdr = 8, 20, 26
    ncol = len(col_labels)
    w = lab + ncol * (fw + pad) + pad
    h = hdr + len(rows) * (fh + caph + pad) + pad
    im = Image.new("RGB", (w, h), (24, 24, 24))
    d = ImageDraw.Draw(im)
    d.text((pad, 6), title, fill=(240, 240, 120))
    for j, cl in enumerate(col_labels):
        d.text((lab + pad + j * (fw + pad), hdr - 14), cl,
               fill=(220, 220, 220))
    y = hdr
    for rl, cells in rows:
        d.text((pad, y + fh // 2), rl, fill=(240, 240, 240))
        for j, (img, cap) in enumerate(cells):
            x = lab + pad + j * (fw + pad)
            im.paste(img, (x, y))
            d.text((x, y + fh + 3), cap, fill=(150, 150, 150))
        y += fh + caph + pad
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    print(path)
