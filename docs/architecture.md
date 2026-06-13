# Architecture

One shared core, many faces. Faces are thin: a manifest, a jungle, an App, a
View that wires core modules together, and face-specific resources.

```
core/src/
  data/    Snapshot.mc      one per-tick state object, all fields nullable
           DataSource.mc    fills the Snapshot from Toybox; caches properties
  render/  Compositor.mc    ordered component list + per-component clips
           Region.mc        rect helpers for clipping and keep-out masking
           CompassRose.mc   sun-compass dial (aim 12 at sun, red needle = N)
  glyph/   SegmentFont.mc   parametric 7-segment digits (fillPolygon)
           SegmentLayout.mc HH:MM / digit-group layout
           StripGlyphs.mc   bitmap-strip blitter (setClip + drawBitmap)
  astro/   MathX.mc         atan2/floor/fmod hand-rolls (2.4-safe)
           Solar.mc         NOAA solar position + sunrise/sunset, pure
           SunCompass.mc    true-north dial angle from sun azimuth, pure
  debug/   Instrument.mc    (:debug) overlay/logging + (:release) stubs
  genart/  GenArt.mc        shared generative utils (hash, sine table, HR zones)
           StrataField.mc   day-as-sediment simulation (the "past" layer)
           Flock.mc         murmuration in the sky (the "present" layer)

faces/devface/               integration testbed (zero styling)
faces/strataflock/           biometric generative art: strata + flock
faces/two-worlds/            artificial chrome (clock/readout/gauges) over the
                             strataflock field, masked to a bordered disc
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
(Snapshot, Compositor, segment polygons); `onUpdate` refreshes the Snapshot in
place and renders — zero per-tick allocation by design. `onSettingsChanged`
(CIQ 2.1+) reloads cached properties and redraws.

## Component contract (duck typing, no base class)

A component is any object with `render(dc, state)`. The Compositor draws them
in order, applying an optional clip rect per component (`Dc.setClip`, API 2.3).
Class metadata costs bytes — there is deliberately no Component superclass.

Keep-outs are the inverse of clips: reserved screen rects that components must
not paint into. A component that supports masking can ask the Compositor for
the registered keep-out rects and skip pixels inside them.

## Memory ground rules

- 64 KB watch-face limit (read from the device files); treat **~45 KB (70%)**
  as the ceiling. devface sits well under it (see docs/memory-budget.md).
- Prefer flat Number arrays (`[x,y,w,h]`) over objects/Dictionaries in hot or
  numerous data.
