# Development guide

The build, test and sideload details behind the [project README](../README.md).

A Monkey C / Connect IQ framework for building watch faces for the **Garmin
Forerunner 735XT** (SDK device id `fr735xt`). Multiple faces share one core
library; `faces/devface` is the always-buildable integration testbed
(deliberately unstyled — debug colors only).

## Tool versions (verified)

| Tool | Version | Notes |
|---|---|---|
| Connect IQ SDK | **9.2.0** (2026-06-09) | newest SDK; still compiles & simulates API 2.4 / fr735xt |
| SDK manager CLI | [lindell/connect-iq-sdk-manager-cli](https://github.com/lindell/connect-iq-sdk-manager-cli) v0.8.4 | headless SDK + device-file downloads (Garmin login required) |
| Java | OpenJDK 21 | required by monkeyc |
| fr735xt device files | CIQ 2.4.1/2.4.5 part numbers | `~/.Garmin/ConnectIQ/Devices/fr735xt/` |
| Xvfb + webkit2gtk-4.0 compat libs | see `scripts/setup-sim-libs.sh` | simulator on modern/headless Linux |

VS Code users: install the official "Monkey C" extension and point it at the
same SDK; this repo's scripts do not depend on it.

## Device constraints cheat sheet (fr735xt)

| Constraint | Value |
|---|---|
| Max Connect IQ API | **2.4.x** — nothing from CIQ 3.0+ compiles or runs (see `api-2.4-notes.md`) |
| Display | **215×180**, semiround, MIP, **4 bpp** (16-color class; device palette lists 14 colors), no antialiasing |
| Watch-face memory limit | **65,536 bytes** (read from `Devices/fr735xt/compiler.json`); project ceiling **90% ≈ 57.6 KB** |
| Update model | **one full `onUpdate` per minute** in low power; `onPartialUpdate` (1 Hz seconds) is **not supported** on this device |
| Execution watchdog | ~25–30k VM instructions per `onUpdate` (measured) — the binding constraint for per-tick work |
| Sensors/network in a watch face | no live GPS; with the `Positioning` permission `Position.getInfo()` gives the last known fix, else the user-entered `lat`/`lng` properties (see `docs/api-2.4-notes.md`) |

## Setup (one-time)

The toolchain provisions itself **on demand**: `build.sh` / `test.sh` /
`sim.sh` call `scripts/ensure-toolchain.sh` the first time the SDK is missing
(it needs `GARMIN_USERNAME` / `GARMIN_PASSWORD` in the environment for the
login-gated device files). On Claude Code on the web the container state is
cached after that first run, so the ~200 MB download happens at most once per
environment — and the SessionStart hook just reports toolchain status without
delaying startup.

Manual setup (local machines, or to pre-warm a container explicitly):

```bash
# 1. SDK + device files (device files need a Garmin account):
GARMIN_USERNAME=you@example.com GARMIN_PASSWORD=... scripts/setup-sdk.sh
# 2. Developer signing key (stored OUTSIDE the repo, in ~/.ciq-keys/):
scripts/gen-key.sh
# 3. Linux-only, for the simulator on distros without libwebkit2gtk-4.0:
scripts/setup-sim-libs.sh
```

## The four workflows

```bash
scripts/build.sh devface             # → bin/devface.prg          (release: -r, debug code stripped)
scripts/build.sh devface --debug     # → bin/devface-debug.prg    (instrumentation + unit tests)

scripts/sim.sh devface --debug       # headless-capable simulator; console shows
                                     # "used/totalK p<peak> <ms>" every update

scripts/test.sh [face]               # API-2.4 symbol lint + Run No Evil unit
                                     # tests in the sim (default face: devface);
                                     # exit code = pass/fail

# Sideload: copy bin/devface.prg to the watch's /GARMIN/APPS over USB.
# Full steps: docs/sideload.md
```

`scripts/memcheck.sh devface` prints the memory limit as read from the device
files, the 90% ceiling, and the current PRG size.

## Module map

```
core/src/data/    Snapshot, DataSource   per-tick state (all fields nullable)
core/src/render/  Compositor, Region,    ordered components, clips, keep-outs;
                  CompassRose            sun-compass dial renderer
core/src/glyph/   SegmentFont/Layout,    parametric 7-segment digits;
                  StripGlyphs            bitmap-strip blitter
core/src/astro/   MathX, Solar,          2.4-safe math; NOAA sun position +
                  SunCompass             sunrise/sunset; true-north-from-sun
                                         dial math (all pure, unit-tested)
core/src/debug/   Instrument             (:debug) overlay/logging, (:release) stubs
core/src/genart/  GenArt, StrataField,   biometric generative-art engines +
                  Flock, BioBloom/-State, shared hash/sine/zone utils and
                  MossGrove/-State       object-store persistence
faces/            flashtest, devface,    see docs/architecture.md for what each
                  strataflock, biobloom, face is; devface is the always-buildable
                  two-worlds, -v2        integration testbed
docs/             architecture, api-2.4-notes, memory-budget,
                  watchdog-debugging, sideload, claude-design-prompt/-handoff
sketches/         Python sandbox         faithful fr735xt model for iterating on
                                         generative art without a PRG build
tools/            make-dow-strip.sh      offline 16-color glyph-strip pipeline
```

Adding a face: copy `faces/devface`, change the manifest `id` and app name,
keep `base.sourcePath = source;../../core/src` in its jungles, and build with
`scripts/build.sh <name>`.

## Measured status (acceptance)

- devface builds clean for fr735xt at API 2.4 (SDK 9.2.0) and runs in the sim.
- devface's 16 unit tests pass (segment lookup, MathX, Solar fixtures,
  SunCompass dial/rollover). The other faces carry their own suites — run
  `scripts/test.sh <face>`.
- Release PRG on disk ≈ **16 KB** (`scripts/memcheck.sh`); runtime RAM sits
  well under the 57.6 KB ceiling (re-read from the sim — release status bar /
  debug overlay); onUpdate ≈ **8–12 ms**, no watchdog trips. Details in
  `docs/memory-budget.md`.
