# Claude Design prompt: FR735XT watch-face studio

Paste the prompt below into a new Claude Design session to get a pixel-accurate,
iterable watch-face design environment for this repo's target device. It encodes
the hard device constraints (see `docs/api-2.4-notes.md` and the README) so the
mockups stay buildable in Monkey C.

Palette provenance: the 14 colors are the standard Connect IQ color-constant
set, with each hex value confirmed against the official
[Toybox.Graphics docs](https://developer.garmin.com/connect-iq/api-docs/Toybox/Graphics.html)
(14 constants besides `COLOR_TRANSPARENT`, matching the 14-entry palette this
README cites from `compiler.json`). Note `COLOR_YELLOW` is `0xFFAA00` (amber) —
true yellow `0xFFFF00` is not available on this device class. The gated device
file itself (`~/.Garmin/ConnectIQ/Devices/fr735xt/compiler.json`) is still worth
a one-time diff after SDK setup, but a mismatch is unlikely.

---

I want to design watch faces for a **Garmin Forerunner 735XT** and preview them
pixel-accurately before implementing them in Monkey C. Build me an interactive
single-page design studio that simulates the device screen faithfully; we'll
then iterate on face designs inside it.

## Device facts — hard constraints, never violate

**Screen geometry.** 215×180 logical pixels, "semiround": the visible area is a
circle of radius 107.5 px centered at (107.5, 90), clipped by the 215×180
viewport — so the left/right edges are round and the top/bottom edges are flat
chords ~117 px wide. Everything outside the circle is opaque black bezel.

**Color.** Fixed 14-color palette. No other color may ever appear on screen:

| Name | Hex | | Name | Hex |
|---|---|---|---|---|
| WHITE | `#FFFFFF` | | GREEN | `#00FF00` |
| LT_GRAY | `#AAAAAA` | | DK_GREEN | `#00AA00` |
| DK_GRAY | `#555555` | | BLUE | `#00AAFF` |
| BLACK | `#000000` | | DK_BLUE | `#0000FF` |
| RED | `#FF0000` | | PURPLE | `#AA00FF` |
| DK_RED | `#AA0000` | | PINK | `#FF00FF` |
| ORANGE | `#FF5500` | | YELLOW | `#FFAA00` |

- No antialiasing, no alpha blending, no gradients, no shadows. Every pixel is
  exactly one palette color.
- It's a transflective MIP display: black backgrounds with high-contrast fills
  look best; large saturated color fields read dimmer in real life than on an
  emissive screen.

**Drawing primitives.** Designs must decompose to what the firmware can draw:
filled rectangles, filled convex polygons, 1-px lines, circles/arcs, and text in
a few built-in bitmap fonts. My framework also has a parametric **7-segment
digit renderer** (size/thickness/slant adjustable) — prefer that style for the
time. No custom vector fonts; any fancy lettering must be plausible as a small
pre-rendered bitmap strip.

**Update cadence.** ONE full redraw per minute. No seconds display, no
animation. Any stepped or animated layer advances one discrete step per minute.

**Data available per frame** (every field can be null — design a graceful
missing state for each): hour/minute, date (day, month, day-of-week), steps +
step goal, distance, calories, heart rate (recent sample, frequently null),
battery %, phone-connected flag, and sunrise/sunset times computed from a
user-set lat/lng.

## What to build

A single self-contained HTML artifact:

1. **Device frame.** A `<canvas>` at exactly 215×180, integer-scaled (default
   3×, zoom control 1–5×) with `image-rendering: pixelated`, the semiround mask
   applied, set in a simple dark watch-body surround.
2. **Palette enforcement.** All drawing goes through a tiny helper that only
   accepts the 14 named colors. After every render, read the canvas pixels back
   and show a pass/fail badge; list any off-palette color found (antialiased
   edges from arcs/text are the usual culprit — draw with smoothing disabled
   and snap to whole pixels).
3. **Mock data panel.** Controls for time, date, steps, HR (including
   "no data"), battery, phone connected — plus one-click stress presets:
   23:59, 00:00, 09:41, everything-null, battery 5%, step goal exceeded.
4. **Faces as plug-ins.** Each design is one JS object with
   `render(ctx, state)` so we can add variants without touching the harness.
   Show a thumbnail gallery of all variants; clicking one loads it into the
   main preview.
5. **Three distinct starting variants:**
   - **A — sun compass:** bold 7-segment HH:MM in the upper center, a small
     day-of-week + date line under it, and a sun-compass rose filling the lower
     region (point 12 at the sun; the red needle reads true north), with a
     sunrise/sunset readout beside it. The clock area is a rectangular keep-out
     the rose never paints into.
   - **B — data-dense:** time plus a steps-progress arc hugging the circular
     edge, HR and battery readouts placed inside the safe circle.
   - **C — minimal:** mostly black, white time, one accent color, nothing else.
6. **Layout discipline.** Keep critical content inside the circle (corners of
   the 215×180 rect don't exist); reserve "keep-out" rectangles for text over
   busy background layers rather than overdrawing.

## How we'll iterate

After the first version I'll request changes like "variant A with an orange age
ramp on the cells", "move the date below the time", "night palette". With every
change, keep the palette checker green and never introduce animation,
gradients, or antialiased edges — if a design needs those, it can't ship on
this device, so propose a compliant alternative instead.
