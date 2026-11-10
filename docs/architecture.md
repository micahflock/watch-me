# Architecture

One shared core, many faces. Faces are thin: a manifest, a jungle, an App, a
View that wires core modules together, and face-specific resources.

The shipping face is `faces/two-worlds-v2`. `devface` and `flashtest` are
tooling. `two-worlds` (V1), `biobloom` and `strataflock` are retired faces kept
buildable; their engines are marked below.

```
core/src/
  data/    Snapshot.mc      one per-tick state object, all fields nullable
           DataSource.mc    fills the Snapshot from Toybox; caches properties
  render/  Compositor.mc    ordered component list + per-component clips
           Region.mc        rect helpers for keep-out masking (unreferenced)
           CompassRose.mc   sun-compass dial (aim 12 at sun, red needle = N)
  glyph/   SegmentFont.mc   parametric 7-segment digits (fillPolygon)
           SegmentLayout.mc HH:MM / digit-group layout
           StripGlyphs.mc   bitmap-strip blitter (setClip + drawBitmap)
  astro/   MathX.mc         atan2/floor/fmod hand-rolls (2.4-safe)
           Solar.mc         NOAA solar position + sunrise/sunset, pure
           SunCompass.mc    true-north dial angle from sun azimuth, pure
  debug/   Instrument.mc    (:debug) overlay/logging + (:release) stubs
  genart/  GenArt.mc        shared generative utils (hash, sine table, HR zones)
           MossGrove.mc     moss day-organism engine (+ MossState.mc
                            persistence): the shipping engine
           BioBloom.mc      retired (V1): movement-fed living-dish engine
                            (+ BioState.mc save/load of the day's dish)
           StrataField.mc   retired (strataflock): day-as-sediment simulation
           Flock.mc         retired (strataflock): murmuration in the sky

faces/two-worlds-v2/         THE FACE: artificial chrome (clock/readout/gauges)
                             over the MossGrove organism, masked to a bordered
                             disc. Owns its source, the breach bitmaps and the
                             diag readout; fonts, launcher icon and settings
                             still come from ../two-worlds/resources via the
                             jungle resourcePath
faces/devface/               integration testbed (zero styling); its tests/ is
                             the shared-core suite and compiles all of core/src
faces/flashtest/             sideload smoke test ("FLASH OK" + update counter)
faces/two-worlds/            retired V1: the same chrome over the BioBloom dish.
                             Also home of the layer cost/RAM profiling tests
faces/biobloom/              retired: the BioBloom dish full-screen, no chrome
faces/strataflock/           retired: the first generative face, strata + flock
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

Keep-outs are the inverse of clips: reserved screen rects that components must
not paint into. The Compositor has a registry for them (`addKeepOut` /
`keepOuts`) and `Region.mc` has the rect helpers, but **no face uses either**:
strataflock's Flock is handed its clock keep-out directly, and the two-worlds
faces mask with a FieldMaskComponent. Both are candidates for removal.

## Memory ground rules

- 64 KB watch-face limit (read from the device files); treat **~57.6 KB (90%)**
  as the ceiling. devface sits well under it (see docs/memory-budget.md).
- Prefer flat Number arrays (`[x,y,w,h]`) over objects/Dictionaries in hot or
  numerous data.
