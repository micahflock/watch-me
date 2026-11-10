# Architecture

One shared core, many faces. Faces are thin: a manifest, a jungle, an App, a
View that wires core modules together, and face-specific resources.

The shipping face is `faces/two-worlds-v2`. `devface` and `flashtest` are
tooling. The earlier faces (`two-worlds` V1, `biobloom`, `strataflock`) and
their engines (BioBloom, BioState, StrataField, Flock) are retired to
`archive/` and no longer build; `archive/README.md` names the last commit
where they did.

```
core/src/
  data/    Snapshot.mc      one per-tick state object, all fields nullable
           DataSource.mc    fills the Snapshot from Toybox; caches properties
  render/  Compositor.mc    ordered component list + per-component clips
           CompassRose.mc   sun-compass dial (aim 12 at sun, red needle = N)
  glyph/   SegmentFont.mc   parametric 7-segment digits (fillPolygon)
           SegmentLayout.mc HH:MM / digit-group layout
           StripGlyphs.mc   bitmap-strip blitter (setClip + drawBitmap)
  astro/   MathX.mc         atan2/floor/fmod hand-rolls (2.4-safe)
           Solar.mc         NOAA solar position + sunrise/sunset, pure
           SunCompass.mc    true-north dial angle from sun azimuth, pure
  debug/   Instrument.mc    (:debug) overlay/logging + (:release) stubs
  genart/  GenArt.mc        shared generative utils (integer hash, sine table)
           MossGrove.mc     moss day-organism engine (+ MossState.mc
                            persistence): the shipping engine

faces/two-worlds-v2/         THE FACE: artificial chrome (clock/readout/gauges)
                             over the MossGrove organism, masked to a bordered
                             disc. Self-contained: source, resources (glyph
                             strips, launcher icon, settings, breach bitmaps),
                             the diag readout, and tests/ (chrome logic + the
                             layer cost/RAM profiles)
faces/devface/               integration testbed (zero styling); its tests/ is
                             the shared-core suite (MossGrove's tests included)
                             and compiles all of core/src
faces/flashtest/             sideload smoke test ("FLASH OK" + update counter)
```

## How a face composes (see faces/devface)

- `monkey.jungle` pulls the core in by path — no Monkey Barrels. Barrels were
  evaluated and rejected at this SDK level: extra build step, manifest wiring,
  and module-namespace symbol overhead against a 64 KB budget, for zero gain
  over plain path concatenation.
- **List the core files the face uses, one by one** (see
  `faces/two-worlds-v2/monkey.jungle`). monkeyc does NOT strip unreferenced
  classes, and the whole PRG loads into the 64 KB of face RAM:
  `base.sourcePath = source;../../core/src` shipped every other engine dead
  inside V2 and left it ~1.5 KB from Out Of Memory (docs/memory-budget.md).
  Only devface takes the whole directory, because its test suite covers it.
- `debug.monkey.jungle` additionally appends `tests` to the source path.
  two-worlds-v2's debug PRG is too big to run as a face (Out Of Memory in
  `onLayout`) but runs its tests: under `monkeydo -t` the app gets a heap of
  megabytes, not the 64 KB face limit (docs/toolchain-notes.md).
  Debug vs release is selected by the **`monkeyc -r` flag** (release strips
  `(:debug)` code and keeps `(:release)` stubs). Do NOT use
  `excludeAnnotations` for debug/release — it double-excludes both copies.

## Lifecycle contract

`AppBase.getInitialView` → View. `onLayout` allocates **everything once**
(Snapshot, Compositor, segment polygons); `onUpdate` refreshes the Snapshot in
place and renders — zero per-tick allocation by design. `onSettingsChanged`
(CIQ 2.1+) reloads cached properties and redraws.

## Component contract (duck typing, no base class)

A component is any object with `render(dc, state)`. The Compositor draws them
in order, applying an optional clip rect per component (`Dc.setClip`, API 2.3).
Class metadata costs bytes — there is deliberately no Component superclass.

There is no keep-out mechanism (reserved rects a layer must not paint into):
the face draws the organism full-frame and then paints a `FieldMaskComponent`
over everything outside the field. The Compositor's unused keep-out registry
and `Region.mc` were removed in 2026-11.

## Memory ground rules

- 64 KB watch-face limit (read from the device files); treat **~57.6 KB (90%)**
  as the ceiling. devface sits well under it (see docs/memory-budget.md).
- Prefer flat Number arrays (`[x,y,w,h]`) over objects/Dictionaries in hot or
  numerous data.
