# Kickoff prompt: Connect IQ framework for the Forerunner 735XT

This is the prompt that started the software side of the project in Claude
Code. It came out of an earlier planning conversation with Claude about
feasibility, the software stack, and which sensors a watch face can read.

It is kept exactly as written. A few of its assumptions turned out wrong once
the real device files and the watch itself were in hand: the palette has
**14** colours, not 16; a watch face *can* read the last GPS fix if the
manifest declares the `Positioning` permission; and the memory ceiling ended
up at 90% of the limit rather than 70%. The current facts are in
[`api-2.4-notes.md`](api-2.4-notes.md) and [`memory-budget.md`](memory-budget.md).

---

# Connect IQ watch face framework — Forerunner 735XT

## Goal
Scaffold a reusable Monkey C / Connect IQ project for building watch faces
for the Garmin Forerunner 735XT, including a small framework for algorithmic
/ generative display art. This phase is infrastructure only — make no visual
design decisions. The result should let me spin up multiple face variants
that share one core library.

## Hard constraints (do not violate)
- Target device: forerunner735xt ONLY. Its max Connect IQ API level is 2.4.x.
  Do not use any Toybox API introduced in CIQ 3.0+. Verify every call against
  API level 2.4.
- Display: 215×180, shape "semiround", fixed 16-color palette, no antialiasing.
- Watch faces get one full onUpdate per minute in low-power mode. Design all
  modules around a 1-tick-per-minute cadence. onPartialUpdate (1 Hz seconds)
  is out of scope; just note in docs whether fr735xt supports it.
- Watch faces cannot access GPS, magnetometer, or network/weather at this API
  level. Location comes from user-entered app settings (lat/long properties).
- Memory is tight. Read the actual watch face memory limit for fr735xt from
  the SDK device definition files (e.g. Devices/forerunner735xt/compiler.json)
  and record it in the README. Treat ~70% of it as our working ceiling.

## Environment setup
1. Verify/install: Connect IQ SDK via SDK Manager, fr735xt device files,
   VS Code Monkey C extension, Java runtime if the toolchain needs it.
   Use the newest SDK that still supports fr735xt; record the version.
2. Generate a developer key; store it outside the repo, reference it in
   build config, document its location.
3. Create and document workflows: build .prg → launch simulator → run tests
   → sideload (copy .prg to the watch's /GARMIN/APPS over USB mass storage).
   Wrap in scripts or VS Code tasks where useful.
4. Git repo with sensible .gitignore (keys, bin/, generated artifacts).

## Repo architecture
Structure for multiple faces sharing one core. Prefer shared source paths
via monkey.jungle; evaluate Monkey Barrels and adopt only if frictionless
at this SDK level.
- /core   — shared modules (below)
- /faces/devface — one buildable face used as the integration testbed
- /docs   — README, workflows, device-constraints cheat sheet, module notes

## Core modules
1. Lifecycle scaffold — App + WatchFace View: onUpdate, onEnterSleep /
   onExitSleep, settings-changed hook.
2. Data layer — one state snapshot assembled per onUpdate: clock time + UTC
   offset, date/day-of-week, steps + goal, distance, calories, most recent
   heart rate sample available at this API level, battery %, phone-connected
   bool, lat/long + user properties. Every field nullable; renderers must
   tolerate missing data.
3. Component renderer — lightweight ordered layer list, each component
   implements render(dc, state). Include per-component clip support and a
   keep-out/mask utility so generative layers can be excluded from reserved
   screen regions. Keep it simple; avoid heavy OO.
4. Generative art engine
   - SimEngine interface: init(seed, w, h), step(inputs), render(dc, origin,
     cellSize). Default one step per onUpdate; steps-per-tick configurable.
   - BitGrid: 2D bitfield packed into 32-bit int arrays, double-buffered,
     fast get/set + neighbor count, optional 2-bit per-cell age channel.
   - Reference implementation: Conway's Life with birth/survive rule masks
     as parameters (so rule variants are config, not code).
   - External-input hook: a step may consume data-layer values (e.g. step
     count delta since last tick). Keep generic.
   - Seeded PRNG utility (LCG or xorshift), deterministic from seed.
   - Persistence policy: sim state lives in memory across updates; support
     serialize/restore of minimal state via the object store OR clean
     reseed on restart — policy flag.
5. Procedural glyph renderer — parametric segment-digit module: segment
   geometry computed from (height, stroke width, corner radius, slant, gap);
   digit→segment lookup; lit and unlit render paths; layout helpers for
   digit groups (HH:MM, dates). Draw primitives only, no fonts.
6. Bitmap strip glyphs — loader/blitter for a small fixed glyph set (e.g.
   7 day-of-week labels) from one resource strip; document the asset
   pipeline for producing strips later.
7. Solar math — pure functions: solar azimuth + elevation and sunrise/
   sunset from (lat, long, UTC time), NOAA-style algorithm. No Toybox
   dependencies beyond Math, so it's unit-testable.
8. Instrumentation — build-flag-gated debug overlay + logging: current/peak
   memory (System.getSystemStats), onUpdate duration (System.getTimer),
   sim-console helpers. Document reading memory in the simulator.

## Testing
- Unit tests for pure modules (BitGrid, PRNG, solar math, segment lookup)
  via the Connect IQ test framework if it works at this SDK/API level;
  otherwise a sim-runnable assertion harness.
- devface integration build: procedural digits showing current time, Life
  engine running in a region, instrumentation printing. Function check
  only — zero styling effort.

## Acceptance criteria
- devface builds clean for forerunner735xt at API 2.4 and runs in the sim.
- Peak memory + onUpdate duration logged; memory within the working ceiling
  with Life running on a grid of at least 40×30.
- Pure-math tests pass.
- README covers: tool versions, all four workflows, device-constraint cheat
  sheet (resolution, palette, memory limit as read from device files, update
  model), and a module map.

## Out of scope — do not build
- Any visual design, themes, or palettes beyond debug colors
- onPartialUpdate / seconds
- Settings UI polish, store packaging
- Background services / web requests
