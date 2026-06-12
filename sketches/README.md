# Generative-art concept sketches

Three candidate engines for a biometric algorithmic-art face, prototyped in
Python on a faithful mock of the 735XT display (215×180, bezel mask, the 14
palette colors, no antialiasing, primitive-only drawing). Run:

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
