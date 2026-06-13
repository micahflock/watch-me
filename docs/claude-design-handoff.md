# Claude Design handoff: export a finished face for the build

Companion to `docs/claude-design-prompt.md`. That prompt *builds* the pixel-
accurate design studio; this one is the next step — once a face is designed and
you're happy with it, paste the prompt below into that same Claude Design session
to **export the finished design as a precise build handoff** that maps 1:1 onto
this repo's Monkey C vocabulary, so the face can be re-implemented without
guesswork.

What it is tuned to produce:

- **Custom bitmap fonts as real assets.** This build has no system fonts — all
  text is bitmap strips blitted cell-by-cell (`core/src/glyph/StripGlyphs.mc`).
  The prompt demands the actual glyph-strip PNGs (palette-quantized, glyphs in
  final color) plus a glyph/index map and metrics. Download those PNGs and drop
  them into `faces/<slug>/resources/drawables/`; the strip's 1x pixels are the
  source of truth.
- **The generative-art area as a placeholder.** The green field is a stand-in for
  an algorithmic layer implemented separately (cf. `faces/strataflock`). The
  prompt captures its region bounds, z-order, and the keep-out rects the
  generative layer must avoid — not a literal fill.
- **Data bindings pinned to `Snapshot` field names** (see `core/src/data/`), with
  an explicit missing/null rendering for every field. The sun/north marker binds
  the derived true-north dial angle, which already exists as
  `core/src/astro/SunCompass.mc` + `CompassRose`.

The 14-color palette and provenance are documented in `docs/claude-design-prompt.md`;
the hard device constraints are in `docs/api-2.4-notes.md`. Both are restated
inside the prompt so the export stays buildable.

---

```
I've finished a watch-face design in this session. Don't redesign — EXPORT the
current design as a precise build handoff so an engineer can re-implement it
exactly in old-style Monkey C for a Garmin Forerunner 735XT. ALL text in this
design is a CUSTOM BITMAP font — there are no built-in/system fonts and no
browser fillText. Where the design can't ship on the device, say so and propose
a compliant alternative instead of silently approximating.

Produce these eight sections, in order.

### 1. Face identity
- name: short lowercase slug
- one-sentence concept
- background color (palette name)
- the custom bitmap fonts in use and which elements use each
- the id of the generative-art region (the green area is a STAND-IN placeholder)
- layer list, back to front

### 2. Reference renders
- final face as a 215x180 PNG, semiround mask applied (corners black), at 1x and
  3x (image-rendering: pixelated)
- annotated wireframe: each element's bbox outlined + labeled with id and pixel coords
- palette-check result: confirm every pixel is one of the 14 colors below; fix
  any strays (no antialiased edges) and re-export

### 3. Bitmap font export  <-- the critical deliverable
The glyphs MUST be the real bitmaps you designed, NOT the browser's fillText. If
any text is currently a fillText placeholder, replace it with the actual glyph
bitmaps before exporting. For EACH custom font, deliver:
- A downloadable horizontal glyph-strip PNG at 1x (one image pixel = one device
  pixel), quantized to the 14-color palette, glyphs in their final color, on a
  transparent background (or solid black if transparency isn't available — state
  which). This strip is the build asset I drop into resources.
- Glyph map: the ordered characters in the strip and each one's index. Include
  EVERY glyph needed to render any value of the bound field, not just the on-
  screen sample: the time font needs 0-9 and the colon; the date/label font needs
  0-9, a space, and every letter used by all seven weekday abbreviations
  (SU MO TU WE TH FR SA).
- Metrics: cell height; cell width if fixed (PREFERRED — pad narrow glyphs with
  transparent space), else per-glyph advance widths; inter-glyph tracking (px);
  and exactly how the colon/separator is spaced.
- Sample assembly: the glyph sequence and per-glyph x advances that produce
  "12:34" and the date string, anchored at the documented origin (x,y + justify).

### 4. Generative-art placeholder
The green area is a STAND-IN for a generative layer implemented separately — do
not treat its color or blob shape as final. Specify:
- region id and the bounds it may paint into (e.g. "the full visible disc")
- the keep-out rects it must NOT paint into — one per foreground element sitting
  over it (time, date, phone bars, sun marker, battery chunks), as [x,y,w,h]
- z-order: it draws first/back; foreground draws on top and the generative layer
  avoids the keep-outs
Stub its render as a flat fill in the JS and mark it clearly.

### 5. Render source
The exact render(ctx, state) JS for the FINAL face (foreground/chrome), self-
contained, using ONLY these primitives (each maps 1:1 to a Garmin dc call):
- fillRect(x,y,w,h)                       -> dc.fillRectangle
- fillPolygon([[x,y],...]) convex only    -> dc.fillPolygon
- line(x0,y0,x1,y1) 1px                    -> dc.drawLine
- circle/fillCircle(cx,cy,r)             -> dc.drawCircle / fillCircle
- arc(cx,cy,r,startDeg,endDeg,thickness)  -> drawArc or polygon-fan (see budget)
- bitmapCell(fontId,glyphIndex,x,y)      -> bitmap-strip blit (ALL text goes through this)
Set a named palette color before each non-bitmap op. No gradient, globalAlpha,
shadow, AA, or fillText.

### 6. Known data bindings (use these EXACTLY)
- Phone-connection bars (the blue bar group, upper right): bind phoneConnected.
  Connected (true) -> every bar BLUE; disconnected (false) OR null -> every bar
  DK_GRAY. Bar lengths/positions are fixed design (a signal-bars motif); only the
  color is data-driven, and it's all-or-nothing across the whole group.
- Sun/north marker (the red rotated square on the rim): bind the derived true-
  north dial angle (the sun-compass angle, clockwise from 12 o'clock, computed
  from lat/lon + date/time) — it shows where true north is when 12 o'clock is
  aimed at the sun, and rides the curved rim at that angle. Show it ONLY when the
  sun is sightable (elevation above -0.833 deg and below ~80 deg). When no
  location is set, or the sun isn't sightable, hide it (state the exact hidden
  treatment). Give the rim radius it travels on and the angle->(x,y) formula.
- Battery chunks (the three orange blocks, bottom center): bind batteryPct
  (0-100). Three equal 33% chunks that deplete RIGHT-TO-LEFT — the rightmost chunk
  greys first. Chunk k (k=1 left .. 3 right) is ORANGE when batteryPct >
  (k-1)*33.33, else DK_GRAY: chunk 3 (right) needs >66.66%, chunk 2 (mid)
  >33.33%, chunk 1 (left) >0%. All three orange at 100%, all DK_GRAY at 0%.
  null -> all DK_GRAY.
- Separation lines (the white lines): structural chrome, NOT data-bound; they mark
  the boundary between the generative-art region and the foreground. Give their
  exact endpoints.

### 7. Element table
One row per drawable, back to front:
- id / description
- type: bitmap-text | rect | polygon | line | circle | arc | generative-placeholder
- geometry: bbox [x,y,w,h]; for bitmap-text: font id + anchor (x,y) + justify;
  for arc/marker: center, r, angle, sweep direction, 0-deg reference
- color(s): palette name(s)
- data binding: per section 6, or the Snapshot field + format; and the EXACT
  pixels drawn when that field is null. If decorative, say so.
- clip rect (if any) and whether it registers a keep-out for the generative layer
- cost: approx draw-call count; if it loops over data, the max count

### 8. State & compliance
- Render/describe the face under: 23:59, 00:00, 09:41, everything-null,
  phone disconnected, battery 100/67/50/20/0, step goal exceeded, HR null,
  sun above the horizon vs not sightable, no location set, and each weekday
  (to prove the date font covers all seven abbreviations).
- Confirm: nothing critical outside the visible circle; keep-outs protect every
  foreground element from the generative layer; palette-only; no AA/alpha/
  gradient/shadow; no animation or seconds; draw-call count modest.

==================== TARGET DEVICE — HARD CONSTRAINTS ====================

GEOMETRY. 215x180 px, "semiround". Origin (0,0) top-left, +x right, +y down.
Center pixel (107,90). Visible area = circle radius 107.5 about (107.5,90)
clipped by the rect: left/right round, top/bottom flat chords; the viewport
corners DO NOT EXIST (visible width at the top/bottom row is only ~117 px,
centered). Keep critical content within radius ~100 of center. Outside the disc
is opaque black bezel.

PALETTE. Exactly these 14 colors (-> Gfx.COLOR_* constants); no other color may
ever appear, INCLUDING inside the font strips:
  WHITE #FFFFFF  LT_GRAY #AAAAAA  DK_GRAY #555555  BLACK #000000
  RED #FF0000    DK_RED #AA0000   ORANGE #FF5500    YELLOW #FFAA00 (amber!)
  GREEN #00FF00  DK_GREEN #00AA00 BLUE #00AAFF      DK_BLUE #0000FF
  PURPLE #AA00FF PINK #FF00FF
Transflective MIP screen: black bg + high-contrast fills read best; big
saturated fields look dimmer in real life than on your monitor.

TEXT. No built-in or system fonts exist on this build — ALL text is custom
bitmap strips blitted cell-by-cell (see section 3). Design accordingly.

CADENCE. ONE full redraw per minute. No seconds, no animation, no smooth motion.
Any stepped/generative layer advances exactly one discrete step per minute.

RENDER BUDGET. ~25-30k VM instructions per redraw is the hard ceiling (CPU, not
RAM, binds). Keep total draw calls modest; batch adjacent fills; a thick arc
becomes a polygon-fan (one fillPolygon per wedge) — keep <= ~24 wedges. Flag any
element whose call count scales with data.

DATA — bind to these exact Snapshot field names (ALL nullable):
  hour 0-23, minute 0-59, second 0-59 (present but DO NOT display), utcOffsetSec
  year, month 1-12, day 1-31, dayOfWeek 1=Sun..7=Sat
  steps, stepGoal
  distanceCm  (hundredths of a metre: km = distanceCm/100000)
  calories (kcal)
  heartRate (bpm, frequently null)
  batteryPct (0-100 Float)
  phoneConnected (Boolean)
  lat, lon (Float degrees; null when unset — treat 0,0 as unset)
Derived, NOT stored (computed from lat/lon + date/time): sun azimuth/elevation,
sunrise/sunset, true-north dial angle. The sun/north marker binds the true-north
dial angle.
If your mock-data panel used friendlier names, relabel every binding to the
field names above.
```
