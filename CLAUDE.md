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
scripts/test.sh                     # API-2.4 symbol lint + 16 unit tests in the sim
scripts/sim.sh <face> --debug       # headless sim; console prints "used/totalK p<peak> <ms>"
scripts/memcheck.sh <face>          # memory limit / ceiling / PRG size
```

## Hard constraints (details: docs/api-2.4-notes.md)

- **Never** use `import`, `Application.Storage/Properties`, `WatchUi.Layer`,
  `Toybox.Complications`, `Toybox.Background`, `onPartialUpdate`, or
  `Math.atan2/floor/ceil/round` (doc-trap: annotated 1.3.0, actually CIQ 3.0
  — use `MathX`). `scripts/test.sh` lints for these.
- 64 KB watch-face RAM; project policy ceiling 70% (~44.8 KB) for release
  builds. Watchdog: ~25–30k VM instructions per `onUpdate` — the binding
  constraint. One `onUpdate` per minute; no seconds hand. Measured numbers
  and how to re-measure: docs/memory-budget.md.
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
(docs/sideload.md). `bin/flashtest.prg` and `bin/devface.prg` are tracked in
the repo for direct download. The compass face needs `lat`/`lng` set in the
app settings on the watch, else it shows the "?" rose.
