# CLAUDE.md

Connect IQ watch faces for the **Garmin Forerunner 735XT** only
(`fr735xt`, API **2.4 max** — nothing from CIQ 3.0+ compiles or runs).

## What is live, and what to leave alone

- **The face on the wrist is `faces/two-worlds-v2`**: the MossGrove organism
  (`core/src/genart/MossGrove.mc`) under the two-worlds chrome
  (`TwoWorldsV2View.mc`). "The face" means this one unless told otherwise.
- `faces/devface` is the unstyled testbed and holds the shared-core unit
  tests; `faces/flashtest` is the sideload smoke test.
- `sketches/` is the Python sandbox: the device model plus mirrors of the
  engine and chrome (`sketches/README.md`).
- **Retired but still in place:** `faces/two-worlds` (V1), `faces/biobloom`,
  `faces/strataflock`, and their engines `BioBloom`/`BioState`/`StrataField`/
  `Flock` in `core/src/genart`. Don't read or change them unless the task is
  about them. Two things still hang off V1: V2 takes its fonts, launcher icon
  and settings from `faces/two-worlds/resources` (jungle `resourcePath`), and
  the layer cost/RAM profiling tests live in `faces/two-worlds/tests`.
- **`archive/` is finished experiments. Don't read, search or edit it unless
  the owner asks about a past experiment** — then start at
  `archive/README.md`, the index. `/.ignore` keeps Grep out of it by default.

## Toolchain — do not set it up by hand

`scripts/build.sh`, `scripts/test.sh`, and `scripts/sim.sh` provision the
entire toolchain themselves on first use (`scripts/ensure-toolchain.sh`).
Requirements: `GARMIN_USERNAME` / `GARMIN_PASSWORD` in the environment;
without them nothing builds, so say so rather than guessing at build results.
On Claude Code on the web the container is cached after first use. If a cold
provision or an SDK tool misbehaves (403/truncated download, monkeydo exiting
silently, debug-build OOM), read **docs/toolchain-notes.md** FIRST.

## Workflows

```bash
scripts/build.sh <face> [--debug]   # release .prg / debug (tests+instrumentation)
scripts/test.sh [face]              # API-2.4 symbol lint + the face's unit tests in the sim (default: devface)
scripts/sim.sh <face> --debug       # headless sim; console prints "used/totalK p<peak> <ms>"
scripts/memcheck.sh <face>          # memory limit / ceiling / PRG size
scripts/build.sh two-worlds-v2 --diag  # on-wrist diagnostic readout (release build)
python3 sketches/scrub.py <algo>    # sandbox: one algo across a simulated day, no SDK
```

**Wrist-only behaviour → the diag build.** `bin/two-worlds-v2-diag.prg` has the
face's app id (sideload it IN PLACE of `two-worlds-v2.prg`) and swaps the moss
for a readout one minute in ten (:00, :10, ...): GPS from both position APIs,
the remembered fix, the last replayed gap, the biggest bead's slots, and a
3-hour HR-history sparkline (`faces/two-worlds-v2/diag/`; the release build
compiles `release/DiagStub.mc` instead).

After a change to the face, rebuild and commit the tracked PRGs
(`bin/two-worlds-v2.prg` and `-diag.prg`) so the repo's download matches the
source.

### Visual changes go through the sandbox first

**Required first step for any new or changed display (organism or chrome):**
prototype it in the Python sandbox and iterate there BEFORE writing any
Monkey C or touching the Garmin SDK. Do not skip this even for "simple" ideas.

**STOP after the sandbox and confirm.** Show the renders (scrub strip and/or
before/after comparison sheet) and wait for explicit approval before porting
anything to Monkey C or building a PRG — the owner usually wants to iterate on
the sandbox output first. This applies to tweaks of the existing face, not
just new displays. Only after sign-off: port, build, sim, update `bin/`.

- New work starts in `sketches/` on `harness.py` (don't copy helpers between
  scripts). When its decision has shipped, move the script and sheets to
  `archive/` and add an index row (`archive/README.md`).
- Port with `idiv`/`imod` wherever Monkey C writes `a / b` / `a % b` on
  Numbers: Python's `//` and `%` floor, so they DISAGREE on negatives.
- The scrub caption's VM-instruction figure is a **loose LOWER BOUND, not
  proof of safety** — it cannot see per-element method-call cost. The
  simulator is ground truth: **docs/watchdog-debugging.md**.
- Everything else (the mirrors, parity references, generators):
  `sketches/README.md`.

## Hard constraints (details: docs/api-2.4-notes.md)

- **Never** use `import`, `Application.Storage/Properties`, `WatchUi.Layer`,
  `Toybox.Complications`, `Toybox.Background`, `onPartialUpdate`, or
  `Math.atan2/floor/ceil/round` (doc-trap: annotated 1.3.0, actually CIQ 3.0
  — use `MathX`). `scripts/test.sh` lints for these.
- 64 KB watch-face RAM; project policy ceiling 90% (~57.6 KB) for release
  builds. Watchdog: ~25–30k VM instructions per `onUpdate` — the binding
  constraint, and V2's saturated frame measured **under ~1.6k to spare**
  (2026-10): anything added to the face needs the margin check in
  docs/watchdog-debugging.md.
  One `onUpdate` per minute; no seconds hand. Numbers: docs/memory-budget.md.
- **monkeyc does not strip unreferenced classes.** A face's jungle lists the
  core files it uses, one by one; pulling in all of `core/src` has twice
  pushed a face out of memory.
- **Debugging a watchdog trip / "Code Executed Too Long" crash / render-cost
  regression → read `docs/watchdog-debugging.md` FIRST.** It has the sim
  reproduction (pin a saturated record, run the *release* PRG), the crash-PC
  decode, the per-layer cost profile, the levers that worked and the dead ends.
- Display 215×180 semiround, fixed 14-color palette (COLOR_YELLOW is amber
  0xFFAA00). No live GPS in watch faces, but with the **`Positioning`
  permission in the manifest** `Position.getInfo()` (and
  `Activity.Info.currentLocation`) give the device's last known fix — without
  the permission the fr735xt returns NO position at all (wrist, 2026-10).
  Every face that compiles `core/src/data` must declare `Positioning`.

## Architecture (details: docs/architecture.md)

One shared core (`core/src`), thin faces (`faces/<name>`). Components are
duck-typed `render(dc, state)` objects drawn by the Compositor; allocate
everything in `onLayout`, zero per-tick allocation in `onUpdate`. Old-style
Monkey C: `using` not `import`, untyped vars, build with `-l 0`.

## Simulator gotchas (more: docs/toolchain-notes.md)

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
- The two-worlds-v2 DEBUG build runs out of memory as a face; verify render
  changes on the RELEASE PRG.
- `scripts/test.sh <face>` only runs tests for faces with a `tests/` dir;
  `monkeydo -t` with no (:test) cases exits silently. Killing a foreground
  `sim.sh` run (e.g. wrapping it in `timeout`) can take the whole Xvfb/sim
  stack down — launch it detached (`... & disown`) before screenshotting.

## Sideloading

Copy `bin/<face>.prg` to the watch's `/GARMIN/APPS` over USB
(docs/sideload.md). The tracked PRGs are `two-worlds-v2`, `two-worlds-v2-diag`,
`two-worlds`, `devface` and `flashtest`. The two-worlds faces (shared settings)
need a location for the sun/north marker: a GPS fix from any GPS activity, or
`lat`/`lng` set in the app settings. The tracked `devface` PRG predates the
GPS fix (2026-10) and reads only `lat`/`lng` until rebuilt.
