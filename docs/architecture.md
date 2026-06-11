# Architecture

One shared core, many faces. Faces are thin: a manifest, a jungle, an App, a
View that wires core modules together, and face-specific resources.

```
core/src/
  data/    Snapshot.mc      one per-tick state object, all fields nullable
           DataSource.mc    fills the Snapshot from Toybox; caches properties
  render/  Compositor.mc    ordered component list + per-component clips
           Region.mc        rect helpers + keep-out → cell-range mapping
  sim/     Prng.mc          Park-Miller (Schrage), overflow-safe, seedable
           BitGrid.mc       packed 2D bitfield, double-buffered, 2-bit age
           LifeEngine.mc    reference SimEngine: Conway-family CA, banded
  glyph/   SegmentFont.mc   parametric 7-segment digits (fillPolygon)
           SegmentLayout.mc HH:MM / digit-group layout
           StripGlyphs.mc   bitmap-strip blitter (setClip + drawBitmap)
  astro/   MathX.mc         atan2/floor/fmod hand-rolls (2.4-safe)
           Solar.mc         NOAA solar position + sunrise/sunset, pure
  debug/   Instrument.mc    (:debug) overlay/logging + (:release) stubs

faces/devface/               integration testbed (zero styling)
```

## How a face composes (see faces/devface)

- `monkey.jungle` pulls the core in by path:
  `base.sourcePath = source;../../core/src` — no Monkey Barrels. Barrels were
  evaluated and rejected at this SDK level: extra build step, manifest wiring,
  and module-namespace symbol overhead against a 64 KB budget, for zero gain
  over plain path concatenation (dead code is stripped either way).
- `debug.monkey.jungle` additionally appends `tests` to the source path.
  Debug vs release is selected by the **`monkeyc -r` flag** (release strips
  `(:debug)` code and keeps `(:release)` stubs). Do NOT use
  `excludeAnnotations` for debug/release — it double-excludes both copies.

## Lifecycle contract

`AppBase.getInitialView` → View. `onLayout` allocates **everything once**
(Snapshot, Compositor, engines, segment polygons); `onUpdate` refreshes the
Snapshot in place, advances the sim, and renders — zero per-tick allocation by
design. `onSettingsChanged` (CIQ 2.1+) reloads cached properties and reseeds
or redraws. `onStop` optionally persists sim state.

## Component contract (duck typing, no base class)

A component is any object with `render(dc, state)`. The Compositor draws them
in order, applying an optional clip rect per component (`Dc.setClip`, API 2.3).
Class metadata costs bytes — there is deliberately no Component superclass.

Keep-outs are the inverse of clips: reserved screen rects that generative
layers must not paint. `Region.clampCellRange` converts a keep-out into an
inclusive cell-index range so sim renderers skip masked cells instead of
overdrawing.

## SimEngine contract (duck typing)

```
initialize(opts)                     construct + seed
step(inputs)                         advance; inputs is a Dictionary or null
render(dc, originX, originY, cell)   draw current state
serialize() / applySerialized(arr)   minimal-state persistence
```

- One `step()` per `onUpdate` is the default cadence (1/minute).
- `:rowsPerStep` spreads a generation across ticks for watchdog headroom
  (see docs/api-2.4-notes.md). Buffers swap only at generation boundaries.
- External-input hook: `step({:stepDelta => n})` — devface feeds the
  step-count delta, which "rains" up to 16 live cells per tick. Any
  Number-valued signal works; keep the keys generic.
- Persistence policy: `simPersist` property. true → `serialize()` written to
  the object store in `onStop`, restored in `onLayout`; false → deterministic
  reseed from `simSeed` on every restart.

## Memory ground rules

- 64 KB watch-face limit (read from the device files); treat **~45 KB (70%)**
  as the ceiling. devface peaks at ~37 KB with a 40×30 Life running.
- BitGrid cost: 40×30 double-buffered ≈ 0.7 KB; with the 2-bit age plane
  ≈ 1.1 KB. RAM is never the Life bottleneck — instruction count is.
- Prefer flat Number arrays (`[x,y,w,h]`) over objects/Dictionaries in hot or
  numerous data.
