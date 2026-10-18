#!/usr/bin/env python3
"""readme_figs.py -- the README's pictures of the shipped two-worlds V2 face.

Renders the real sandbox mirror (moss_grove + the twchrome overlay) across
synthetic days into docs/img/:

    anatomy.png      one face, 4x, with callouts naming each element (the
                     only render with the phone-connected ring on)
    day-timeline.png an active day, morning to night
    day-types.png    rest / active / heavy days at the same evening minute
    nights.png       a rested night vs a broken one, read the next morning
    breach.png       the CONTAINMENT BREACH easter egg (heavy day)
    v1-vs-v2.png     two-worlds V1 (BioBloom dish) beside V2 (MossGrove)

    python3 sketches/readme_figs.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import device
import twchrome
from bead_compare import load_algo, mins
from breach_compare import BREACH_ACT
from day import synthetic_day
from north_compare import chrome_state
from twchrome import ChromeDc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "img")
DATE, OFF, DOW = (2026, 10, 15), -7 * 3600, 4

BG = (13, 17, 23)          # GitHub dark canvas -- reads on light pages too
INK = (230, 237, 243)
DIM = (139, 148, 158)


def font(size):
    return ImageFont.load_default(size=size)


def run_day(profile, times, ring=()):
    """Replay a day minute by minute; return {time: face render}. Times in
    `ring` are also rendered phone-connected, under the key time + "+ring"."""
    snaps = synthetic_day(profile=profile)
    grove = load_algo("moss_grove").build()["components"][0]
    want = {mins(t): t for t in times}
    out = {}
    for m in range(max(want) + 1):
        grove.advance(snaps[m])
        if m in want:
            out[want[m]] = face(grove, snaps[m], m)
            if want[m] in ring:
                out[want[m] + "+ring"] = face(grove, snaps[m], m, phone=True)
    return out


def face(grove, snap, t, breach=None, phone=False):
    dc = ChromeDc()
    grove.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.gpsFix = 2
    st.phoneConnected = phone
    st.breach = (grove.rec.act_units >= BREACH_ACT) if breach is None else breach
    for c in twchrome.v2_chrome():
        c.render(dc, st)
    return glass_rgba(dc.img)


def face_v1(dish, snap, t):
    """two-worlds V1: the BioBloom dish under the original chrome (phone-link
    bars, no edge ring, north drawn under the readouts)."""
    dc = ChromeDc()
    dish.render(dc, snap)
    st = chrome_state(DATE, OFF, DOW, t, snap=snap)
    st.phoneConnected = True
    for c in twchrome.v2_chrome(north_last=False):
        if isinstance(c, (twchrome.PhoneRing, twchrome.Breach)):
            continue
        if isinstance(c, twchrome.Uplink):
            c = twchrome.Uplink(gps=False)
        c.render(dc, st)
    return glass_rgba(dc.img)


def glass_rgba(img):
    """The panel only: pixels off the glass become transparent."""
    out = img.convert("RGBA")
    px = out.load()
    for y in range(device.H):
        for x in range(device.W):
            if not twchrome.visible(x, y):
                px[x, y] = (0, 0, 0, 0)
    return out


def up(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def strip(cells, path, k=2, title=None, gap=28):
    """cells = [(img, caption, sub)] side by side on the dark canvas."""
    w = device.W * k
    h = device.H * k
    top = 44 if title else 16
    W = gap + len(cells) * (w + gap)
    H = top + h + 64
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((gap, 14), title, fill=INK, font=font(18))
    for i, (img, cap, sub) in enumerate(cells):
        x = gap + i * (w + gap)
        sheet.paste(up(img, k), (x, top), up(img, k))
        d.text((x + w // 2, top + h + 12), cap, fill=INK, font=font(18),
               anchor="ma")
        if sub:
            d.text((x + w // 2, top + h + 36), sub, fill=DIM, font=font(14),
                   anchor="ma")
    sheet.save(path)


def anatomy(img, path, k=4):
    """Callouts: (label, (x, y) on the 1x face, side)."""
    labels = [
        ("day + date", (95, 17), "L"),
        ("7-segment clock (bitmap strips)", (57, 40), "L"),
        ("effort beads: one per HR episode,\nrings = its peak zones over time", (30, 95), "L"),
        ("silver root star: last night's sleep", (107, 108), "L"),
        ("moss cushion: grows with movement", (60, 138), "L"),
        ("battery: three 33% chunks", (82, 172), "L"),
        ("GPS fix recency bars", (142, 20), "R"),
        ("phone-connected ring", (206, 50), "R"),
        ("dk-blue leading edge + tendrils", (176, 57), "R"),
        ("north marker (sun compass)", (207, 112), "R"),
        ("satellite tufts: grains tinted by\nthe dominant elevated HR zone", (157, 145), "R"),
    ]
    fw, fh = device.W * k, device.H * k
    margin = 420
    W, H = fw + 2 * margin, fh + 80
    sheet = Image.new("RGB", (W, H), BG)
    ox, oy = margin, 40
    big = up(img, k)
    sheet.paste(big, (ox, oy), big)
    d = ImageDraw.Draw(sheet)
    f = font(17)
    left = [l for l in labels if l[2] == "L"]
    right = [l for l in labels if l[2] == "R"]
    for side, group in (("L", left), ("R", right)):
        group = sorted(group, key=lambda l: l[1][1])
        n = len(group)
        for i, (text, (x, y), _) in enumerate(group):
            ty = oy + 20 + i * (fh - 40) // max(1, n - 1)
            px, py = ox + x * k + k // 2, oy + y * k + k // 2
            if side == "L":
                tx = margin - 30
                d.line([(px, py), (tx + 10, ty)], fill=DIM, width=1)
                d.multiline_text((tx, ty), text, fill=INK, font=f,
                                 anchor="rm" if "\n" not in text else "rs",
                                 align="right")
            else:
                tx = ox + fw + 30
                d.line([(px, py), (tx - 10, ty)], fill=DIM, width=1)
                d.multiline_text((tx, ty), text, fill=INK, font=f,
                                 anchor="lm" if "\n" not in text else "ls")
            d.ellipse((px - 4, py - 4, px + 4, py + 4), outline=INK, width=2)
    sheet.save(path)


def main():
    os.makedirs(OUT, exist_ok=True)

    # An active day with a HIIT morning run (day.py "hiit"). The hero image
    # is a simulator capture of the real face, not rendered here.
    act = run_day("hiit", ["6:30", "8:00", "12:30", "17:00", "18:20", "21:45"],
                  ring=("18:20",))
    anatomy(act["18:20+ring"], os.path.join(OUT, "anatomy.png"))

    strip([(act["6:30"], "06:30", "waking: just the sleep roots"),
           (act["8:00"], "08:00", "after a HIIT run"),
           (act["12:30"], "12:30", "mid lunch walk"),
           (act["17:00"], "17:00", "stress spike + a dash for the bus"),
           (act["21:45"], "21:45", "after the gym: the day, complete")],
          os.path.join(OUT, "day-timeline.png"),
          title="One active day, replayed minute by minute")

    rest = run_day("rest", ["21:45"])
    heavy_snaps = synthetic_day(profile="heavy")
    grove = load_algo("moss_grove").build()["components"][0]
    heavy = {}
    for m in range(mins("21:45") + 1):
        grove.advance(heavy_snaps[m])
        if m == mins("21:45"):
            heavy["calm"] = face(grove, heavy_snaps[m], m, breach=False)
            heavy["breach"] = face(grove, heavy_snaps[m], m)
    strip([(rest["21:45"], "rest day", "a small sprig"),
           (act["21:45"], "active day", "a fringed cushion"),
           (heavy["calm"], "heavy day", "a saturated fruiting mass")],
          os.path.join(OUT, "day-types.png"),
          title="Same minute (21:45), three different days")

    rested = run_day("hiit", ["9:00"])["9:00"]
    broken = run_day("hiit_restless", ["9:00"])["9:00"]
    strip([(rested, "slept through", "long, straight silver roots"),
           (broken, "three wake-ups", "snapped roots + white specks")],
          os.path.join(OUT, "nights.png"), k=3,
          title="The night, read at 09:00 the next morning")

    snaps = synthetic_day(profile="hiit")
    dish = load_algo("biobloom").build()["components"][0]
    for m in range(mins("21:45") + 1):
        dish.advance(snaps[m])
    strip([(face_v1(dish, snaps[m], m), "V1: BioBloom", "a slime-mould network"),
           (act["21:45"], "V2: MossGrove", "a moss day-organism")],
          os.path.join(OUT, "v1-vs-v2.png"), k=3,
          title="The same active day at 21:45")

    up(heavy["breach"], 3).save(os.path.join(OUT, "breach.png"))


if __name__ == "__main__":
    main()
