# CLAUDE.md

Connect IQ watch-face framework for the **Garmin Forerunner 735XT** only
(`fr735xt`, API **2.4 max** — nothing from CIQ 3.0+ compiles or runs).

## Toolchain — do not set it up by hand

`scripts/build.sh`, `scripts/test.sh`, and `scripts/sim.sh` provision the
entire toolchain themselves on first use (`scripts/ensure-toolchain.sh`: SDK
manager CLI → agreement+login → SDK 9.2.0 with simulator → fr735xt device
files → signing key → headless-sim libs). Requirements: `GARMIN_USERNAME` /
`GARMIN_PASSWORD` in the environment. On Claude Code on the web the container
is cached after first use, so warm sessions have everything already.

## Workflows

```bash
scripts/build.sh <face> [--debug]   # release .prg / debug (tests+instrumentation)
scripts/test.sh [face]              # API-2.4 symbol lint + the face's unit tests in the sim (default: devface)
scripts/sim.sh <face> --debug       # headless sim; console prints "used/totalK p<peak> <ms>"
scripts/memcheck.sh <face>          # memory limit / ceiling / PRG size
```

### Generative-art sandbox — iterate without building a PRG

For developing the algorithmic biometric art, work in the Python sandbox
under `sketches/` first; only build/sim a face once an algorithm is a keeper.

```bash
python3 sketches/scrub.py <algo> [--seed N] [--at 7:50,13:05,21:45]
```

Renders `sketches/algos/<algo>.py` across a simulated biometric day into a
captioned strip PNG (`sketches/out/<algo>-scrub.png`) in well under a second —
no SDK, no PRG. Captions show the watchdog proxy (estimated VM instructions vs
~25k), state bytes (RAM proxy), and any off-palette color use. **The proxy is a
loose LOWER BOUND, not proof of safety** — it cannot see the per-element
method-call cost (`coordX`/`packPt`/`setColor`/`drawLine` dispatch) that
dominates on-device, so a frame it calls fine can still trip the watchdog on the
wrist. When a trip happens, the simulator is ground truth: **docs/watchdog-debugging.md**.

- `sketches/device.py` is a **faithful** fr735xt model, not a loose mock:
  `hash16` / `isin` (integer sine LUT) / `zoneIndex` / the 14-color palette
  are bit-identical to `core/src/genart/GenArt.mc`. Use `idiv`/`imod` wherever
  Monkey C writes `a / b` / `a % b` on Numbers — Python's `//`/`%` floor and
  so DISAGREE on negatives (e.g. `-6200 / 127` is `-48` on the watch, `-49`
  with `//`). The `Dc` exposes only real `Gfx` primitives, counts every call,
  and snaps colors to the palette.
- An algo module defines `build() -> {"background", "components": [...]}`;
  each component is the same duck-typed `render(dc, state)` (+ optional
  `advance(state)`, `state_bytes()`) the Compositor draws. scrub replays the
  day minute by minute so stateful engines accrete exactly as on-device.
- Because the primitives match 1:1, a sandbox algo ports to a `.mc` face
  **mechanically** (`Gfx.` → `using`, `idiv(a,b)` → `a / b`, `var`/syntax).
  `sketches/algos/strataflock.py` is the line-for-line port of the shipped
  face, kept as the **parity reference** — if it stops matching
  `sketches/out/strataflock-ondevice.png`, the mirror has drifted from
  `GenArt.mc`/`StrataField.mc`/`Flock.mc` and `device.py` is what to fix.
- Arc/circle rasterization is the one thing only the SDK sim renders exactly,
  so the final fidelity check is still `scripts/build.sh` + `scripts/sim.sh`.
- The older `sketches/genart_sketches.py` is the pre-port concept sketchbook
  (loose float math, separate `ihash`); it predates this faithful harness.

## Hard constraints (details: docs/api-2.4-notes.md)

- **Never** use `import`, `Application.Storage/Properties`, `WatchUi.Layer`,
  `Toybox.Complications`, `Toybox.Background`, `onPartialUpdate`, or
  `Math.atan2/floor/ceil/round` (doc-trap: annotated 1.3.0, actually CIQ 3.0
  — use `MathX`). `scripts/test.sh` lints for these.
- 64 KB watch-face RAM; project policy ceiling 90% (~57.6 KB) for release
  builds. Watchdog: ~25–30k VM instructions per `onUpdate` — the binding
  constraint. One `onUpdate` per minute; no seconds hand. Measured numbers
  and how to re-measure: docs/memory-budget.md.
- **Debugging a watchdog trip / "Code Executed Too Long" crash / render-cost
  regression → read `docs/watchdog-debugging.md` FIRST.** It has the sim
  watchdog reproduction (pin a saturated dish, run the *release* PRG), the
  crash-PC decode against `bin/<face>.prg.debug.xml`, the real per-layer cost
  profile (`testLayerCostProfile`), the cost levers that worked, and the dead
  ends (the sandbox proxy's blind spot, `INK_MAX` shuffling, the midnight-reset
  red herring) — four rounds of lessons so the next trip takes one.
- Display 215×180 semiround, fixed 14-color palette (COLOR_YELLOW is amber
  0xFFAA00). No GPS/sensors in watch faces — location comes from `lat`/`lng`
  app properties.

## Architecture (details: docs/architecture.md)

One shared core (`core/src`), thin faces (`faces/<name>`). Components are
duck-typed `render(dc, state)` objects drawn by the Compositor; allocate
everything in `onLayout`, zero per-tick allocation in `onUpdate`. Old-style
Monkey C: `using` not `import`, untyped vars, build with `-l 0`.

## Simulator gotchas (learned the hard way)

- Loading a PRG onto an already-running simulator hangs monkeydo with no
  output. Always go through the scripts (`ciq_start_sim fresh` restarts the
  whole sim/Xvfb stack and retries; don't bypass it with raw monkeydo).
- App settings persist across loads at
  `/tmp/com.garmin.connectiq/GARMIN/APPS/SETTINGS/` — delete that dir to make
  the sim re-read property defaults (e.g. after changing `properties.xml`).
- Screenshots: `xwd -root` on the Xvfb display (auth file from
  `pgrep -af Xvfb`), then ImageMagick `convert`.
- Release builds stub out `Instrument`; read release RAM from the sim's
  status bar instead of the console line.

## Sideloading

Copy `bin/<face>.prg` to the watch's `/GARMIN/APPS` over USB
(docs/sideload.md). `bin/flashtest.prg`, `bin/devface.prg`,
`bin/two-worlds.prg`, and `bin/two-worlds-v2.prg` are tracked in the repo for
direct download. `devface` needs `lat`/`lng` set in the app settings on the
watch, else it shows the "?" compass rose; `two-worlds` and `two-worlds-v2`
(shared settings) likewise need `lat`/`lng` for their sun/north marker.
