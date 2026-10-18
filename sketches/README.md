# Generative-art sandbox & concept sketches

## Iterating on algorithms: the faithful sandbox

To develop the biometric art, iterate in the Python sandbox — no Garmin SDK,
no PRG build, sub-second renders:

```bash
python3 sketches/scrub.py <algo> [--seed N] [--at 7:50,13:05,21:45]
```

It renders `sketches/algos/<algo>.py` across a simulated biometric day into a
captioned strip in `sketches/out/<algo>-scrub.png`. The pieces:

- **`device.py`** — a *faithful* fr735xt model. `hash16`, `isin` (integer sine
  LUT), `zoneIndex`, and the 14-color palette are bit-identical to
  `core/src/genart/GenArt.mc`; `idiv`/`imod` reproduce Monkey C's
  truncate-toward-zero integer math (Python's `//`/`%` floor and disagree on
  negatives). `Dc` exposes only real `Gfx` primitives, counts every call
  (watchdog proxy), and snaps colors to the palette.
- **`day.py`** — the per-minute `Snapshot` feed (steps, HR, time), mirroring
  what `DataSource` builds on the watch. Swap it to replay a real day.
- **`algos/<name>.py`** — `build() -> {"background", "components": [...]}`;
  each component is a duck-typed `render(dc, state)` (+ optional
  `advance(state)`, `state_bytes()`), the same contract the Compositor draws.
- **`algos/strataflock.py`** — a line-for-line port of the shipped face, kept
  as the **parity reference**: prove the mirror by checking its scrub against
  `strataflock-ondevice.png`. Later engines follow the same pattern:
  `algos/biobloom.py` mirrors the BioBloom dish (`faces/biobloom`,
  `faces/two-worlds`) and `algos/moss_grove.py` mirrors the MossGrove organism
  (`faces/two-worlds-v2`, checked against `moss_grove-ondevice.png`). The other
  top-level scripts here (`daybuckets`/`daysoma`/`mossutil`/`grove_*`/
  `morning_proto`/`scenarios`/`save_compare`/`verify_persist`/`ram_breakdown`)
  are exploration and measurement harnesses for those engines — each has a
  docstring saying what it renders.
- **Chrome: `twchrome.py` / `solar.py` / `north_compare.py`** — the two-worlds
  V2 overlay (field mask, border, GPS-fix uplink bars, battery, sun/north
  marker, readout, 7-seg clock blitted from the real glyph strips) transcribed onto the
  device model, plus a float32 port of `Solar.mc`/`SunCompass.mc`
  (`python3 sketches/solar.py` self-checks it against the Monkey C fixtures).
  `north_compare.py` sweeps the north-marker track over every bearing and over
  real days (Portland, Sydney) and renders the candidate tracks — the chrome
  counterpart of `scrub.py`.
- **`readme_figs.py`** — renders the project README's pictures of the shipped
  face (hero, annotated anatomy, day timeline, day types, nights, breach,
  V1 vs V2) into `docs/img/` from the same moss_grove + chrome mirrors.

Because the primitives match 1:1, a winning sandbox algo ports to a `.mc` face
mechanically. Arc/circle rasterization is the one thing only the SDK sim nails,
so the final check is still `scripts/build.sh` + `scripts/sim.sh`.

## Concept sketches (pre-port)

The original candidate engines, prototyped in Python on a *loose* mock of the
735XT display (separate float math / `ihash`; predates the faithful sandbox
above). Run:

```bash
python3 sketches/genart_sketches.py    # writes sketches/out/*.png
```

Each contact sheet shows 07:50 (mid morning run), 13:05 (after a lunch
walk), 21:45 (full day) of the same simulated day. Captions show primitive
calls per frame (watchdog proxy) and persistent state bytes (RAM proxy).

## 1. Weathered Truchet (`weathered-truchet.png`)

Smith-tile quarter arcs, roughed up three ways: tiles **unlock in shuffled
order** through the day (canvas fills as the day does); a tile's
**subdivision depth** comes from step count in its 48-minute window (active
hours render as fine 9 px filigree, idle hours as fat 36 px arcs); each
minute movement **flips tiles**, recoloring them with the current HR zone,
and untouched tiles cool through LT_GRAY to DK_GRAY. ~10% of subtiles
corrupt into 10 PRINT diagonals or voids.

- Data → form: steps→density, HR→color of fresh tiles, movement→churn rate,
  date→layout seed.
- Cost: ≤ ~960 arcs worst case, typically ~120. State: 120 B.

## 2. Murmuration (`murmuration.png`)

tixy.land's dot lattice, bent out of true. Dots **wake** as cumulative
steps grow; a day-seeded Lissajous **attractor** wanders the screen and
nearby dots swell and take the current HR-zone color; sine-noise
displacement (driven by current movement plus a 45-min decaying "unrest"
trace) warps the lattice; dots that drift close grow DK_GRAY filaments.

- Data → form: cumulative steps→population, HR→flock color+pulse,
  movement→warp amplitude, date→attractor orbit.
- Cost: ~300 primitives. State: 0 B — fully re-derived each frame from
  (seed, minute, biometrics), fxhash-style.

## 3. Sediment (`sediment.png`)

The day as a core sample. Every minute drops grains (more when stepping)
near a cursor that **sweeps left→right with the clock**; movement widens
scatter, stillness stacks towers; columns **topple onto shorter neighbors**
so dunes find an angle of repose. Grain color is the HR zone of that
minute: sleep lays DK_BLUE bedrock, a run deposits an ORANGE seam, the gym
a GREEN ridge. A white grain marks "now". Midnight starts a fresh canvas.

- Data → form: time→x position, steps→deposition rate, HR→strata color,
  movement→scatter width.
- Cost: ~450 fillRects by late evening. State: 54-column RLE, ~900 B.

## 4. Strata + Flock hybrid (`strata-flock.png`)

Sediment is the past, the murmuration is the present. A slower-accreting
strata landscape (chronological left→right) fills the bottom; above the
skyline the flock lives in the sky, colored by the *current* HR zone, with
the attractor confined to the upper half. Dots that drift below the
terrain are buried and not drawn; dots grazing the surface leave a LT_GRAY
speck on the crust — the flock precipitating into sediment.

- Data → form: everything from concepts 2 and 3 combined; the skyline
  itself becomes an input to the flock (terrain culls/landing).
- Cost: ~700 primitives by late evening (sum of both engines — still far
  under budget). State: strata RLE only, ~900 B; flock stateless.

## Ported to a face: `faces/strataflock`

Concept 4 is implemented as a real watch face under `faces/strataflock`
(`StrataField.mc` = strata, `Flock.mc` = murmuration, `GenArt.mc` = shared
integer hash / sine table / HR-zone ramp). All math is integer; the strata
evolves incrementally (≤12 minutes of catch-up per `onUpdate`); the flock is
stateless. Verified in the SDK 9.2.0 simulator on `fr735xt`:

- 6 unit tests pass (`scripts/test.sh strataflock`) — hash determinism, sine
  table, zone mapping, strata conservation/caps/idle-drip/day-rollover.
- Release PRG 21 KB on disk; debug runtime RAM ~39/59 KB (under the 90%
  ceiling, and the debug build carries the test suite).
- Full-day evening frame renders in 12–16 ms with no watchdog trip; cold
  start ~4 ms. (A whole day cannot be replayed in a single `onUpdate` — that
  trips the watchdog — but the real face never does that.)

`strataflock-ondevice.png` is a simulator capture at a synthetic full day
(18:20, post-gym): the flock in the sky with hot dots at the attractor, the
strata mountain below with sleep/run/gym color bands. The "39/59K" text is
the debug memory overlay, stripped in release.

## Porting notes (Monkey C, API 2.4)

- All randomness is `ihash()` (FNV-style integer hash) — deterministic,
  no float, ports directly.
- `math.sin` in concepts 1–2 becomes the existing sine LUT / `MathX`
  (no `Math.floor` etc.).
- Truchet and Sediment evolve **incrementally** (one minute of state per
  `onUpdate`); the sketch replays the whole day only because it renders
  arbitrary snapshots. Murmuration is stateless by construction.
- Primitive counts stay well under the ~25–30k VM-instruction watchdog;
  nothing draws per-pixel.
- Real inputs: `ActivityMonitor.getInfo()` steps, `Activity.getActivityInfo()
  .currentHeartRate` (or `getHeartRateHistory` on 2.4), movement proxied by
  step delta per minute.
