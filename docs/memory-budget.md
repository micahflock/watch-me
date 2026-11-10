# Memory & execution budget (fr735xt)

## The numbers (measured, June 2026, SDK 9.2.0)

| Quantity | Value | Source |
|---|---|---|
| Watch-face memory limit | **65,536 bytes (64 KB)** | `~/.Garmin/ConnectIQ/Devices/fr735xt/compiler.json` → `appTypes[type=watchFace].memoryLimit` |
| Working ceiling (project policy) | **58,982 bytes (~57.6 KB, 90%)** | `scripts/memcheck.sh` |
| devface release PRG on disk | **31,372 bytes (~31 KB)** (2026-11; it compiles all of `core/src`) | `scripts/memcheck.sh` / `ls bin/devface.prg` |
| devface onUpdate duration (sim) | **8–12 ms** | `Instrument` (System.getTimer deltas) |
| devface release runtime RAM (sim status bar) | **34.7/59.8 kB** (2026-11) | `scripts/sim.sh devface` |
| Watchdog budget per onUpdate | **~25–30k VM instructions** | calibrated busy-loop (below) |

`getSystemStats().totalMemory` inside the app reports ~59-60 KB — the 64 KB
limit minus fixed system overhead. The Instrument overlay prints
`used/total p<peak> <frame>ms` every update.

Runtime RAM: re-read it from the sim after a build — the **release** status bar
(Instrument is stubbed in release) and the **debug** `Instrument` overlay. Both
sit well under the 90% ceiling; the debug build carries the unit-test suite, so
it runs higher than release. If the debug build ever approaches the real 64 KB
limit, split the test suite or trim fixtures.

## Reading memory in the simulator

1. Build debug: `scripts/build.sh devface --debug` (instrumentation compiled in).
2. Run: `scripts/sim.sh devface --debug`. Every onUpdate prints
   `used/totalK p<peak> <ms>` (used KB / total KB, peak KB, frame ms) to the
   console and draws the same line at the screen bottom.
3. The simulator GUI also has File > View Memory; in this repo's headless setup
   the console line is the practical channel.
4. Static budget check: `scripts/memcheck.sh devface`.

## RAM by UI component (measured, two-worlds-v2, 2026-11)

`Instrument` only samples whole-app `usedMemory`. To decompose it,
`faces/two-worlds-v2/tests/TestTwoWorldsV2.mc` → `testLayerRamProfile` is the
RAM analog of `testLayerCostProfile`: it allocates each `onLayout` component in
render order and records the `getSystemStats().usedMemory` **delta** each one
adds. Run `scripts/test.sh two-worlds-v2` and read the `RAM bytes:` debug line.

Measured deltas (SDK 9.2.0, unit-test build in the sim): the face's own
allocation footprint.

| UI component | bytes | % of UI alloc |
|---|---:|---:|
| Font bitmaps (time / date / dow / colon) | 4,672 | 45.6% |
| MossGrove (every array, sized to its caps) | 2,448 | 23.9% |
| Field mask (188 merged rects) | 1,080 | 10.5% |
| Border (the two anti-aliasing tables) | 792 | 7.7% |
| Sun / north marker (`_quad`) | 320 | 3.1% |
| Snapshot (device state) | 296 | 2.9% |
| Compositor (render list + clips) | 176 | 1.7% |
| Breach component | 152 | 1.5% |
| Phone ring | 104 | 1.0% |
| GPS bars | 104 | 1.0% |
| Battery | 96 | 0.9% |
| **Total UI allocation** | **10,240** | **100%** |
| Breach bitmaps, loaded on a breach day only | +2,136 | |

Read the **deltas, not the absolute total**: the test run's `usedMemory`
(~60 KB) is the unit-test build's, with the suite and instrumentation compiled
in and no `-r`, on the test runner's large heap (docs/toolchain-notes.md). It
is not the release figure; that is below.

Two findings worth keeping:

- **The organism does not grow over the day.** MossGrove allocates every array
  at its cap in `initialize()`, so `groveGrown` is **0 B**: a saturated day
  fills existing slots, it never allocates more. RAM is bounded by the caps.
  (BioBloom, V1, had the same property at more than twice the size: 5,976 B.)
- **Font bitmaps are almost twice the organism.** Decoded pixel data, not
  Numbers: the cheapest place to claw back RAM if ever needed is the glyph
  strips, not the generative art.

## Measured release runtime (two-worlds-v2, July 2026)

**`usedMemory` 38,760 B of `totalMemory` 61,256 B** (sim status bar 37.7/59.8 kB)
under a **pinned saturated record** — max cushion/tufts/texture, 16 max-magnitude
beads, 10 h root star with a fully-broken night — i.e. ~22 KB free at the
worst case. PRG on disk 31,436 B.

It did not start that way. The face as first shipped read **59.4 KB used** —
~1.5 KB from the hard limit — and OOM'd in `DataSource.refresh` the moment
anything else was added. The cause: `monkey.jungle` pulled in **all of
`core/src`**, and monkeyc does no dead-code elimination for unreferenced
classes, so V1's entire BioBloom/StrataField/Flock (~21 KB of PRG) shipped
inside V2, dead. The fix is the narrowed per-file `sourcePath` in
`faces/two-worlds-v2/monkey.jungle`. **When adding a face, list the core files
it actually uses — and re-run this measurement** (sim status bar, recipe at
the end of this section).

**Re-measured 2026-10** after the effort-bead growth rings + recorded-workout
HR backfill (MossGrove `_edur/_eband/_hrBuf/_pool`, `DataSource.hrMinutes`):
**43.2/59.8 kB** (sim status bar) under the pinned worst case -- 16 beads with
six distinct bands each, max cushion, 10 h root star, AND a 12-minute
(`CHUNK`) history replay into an open episode in the same `onUpdate`. No
watchdog trip. The probe is the one in docs/watchdog-debugging.md plus
`_edur[i] = 600`, a six-zone `_eband[i]`, `_epiOn = true; _epiIdx = 15`,
`_lastMin = nm - 13`, and `hrMinutes` forced to fill HR 150. (That probe was
BioBloom's then; docs/watchdog-debugging.md now carries the MossGrove one in
full.)

**V2 chrome polish (2026-10), same unpinned sim conditions:** the GPS
satellite-dish icon 43.2 -> 44.8 kB, then the anti-aliased white border
(245 static grey pixels, 123 packed Numbers in `BorderComponent`) 44.8 ->
**47.3/59.8 kB**; PRG 36.3 -> 39.1 KB. Mostly code + const-array literals,
not per-frame allocation. The saturated pinned probe (above) stays silent.
Cheapest claw-back if RAM gets tight: re-emit a smaller AA variant
(`sketches/border_aa_compare.py --emit "dk, chrome side"`, 107 px).

**CONTAINMENT BREACH easter egg (2026-10):** 47.3 -> 48.1 kB on a normal
day (code only; its three bitmaps load on the first breach), **49.9/59.8 kB**
on a breach day with them loaded; PRG 39.1 -> 41.5 KB.

**Dead-code cleanup (2026-11), measured before and after in one session:**
**47.1 -> 46.2/59.8 kB** on the unpinned sim day, 49.6 -> **48.8/59.8 kB**
under the pinned saturated probe (breach bitmaps loaded); PRG 41,036 ->
**40,380 B**. Removed: GenArt's strata/flock HR ramp, the Compositor's
keep-out registry, three unread Snapshot fields and their DataSource reads,
and MossGrove's pre-2026-10 save loader. The watchdog margin did not move
(docs/watchdog-debugging.md). To re-measure: build release, run
`scripts/sim.sh two-worlds-v2` detached, and read the simulator's status bar
from a screenshot (CLAUDE.md, "Simulator gotchas"); release stubs `Instrument`,
so there is no console line.

**Diag build (2026-11, colour-coded readout):** `two-worlds-v2-diag.prg`
44,108 -> 45,164 B; on a readout minute **52.1/59.8 kB** (51.0 before, on a
face minute), **54.7/59.8 kB** under the pinned saturated probe with the
breach bitmaps loaded and a 12-minute replay in the same `onUpdate` -- no
watchdog trip (the moss is skipped on a readout minute). Still under the
57.6 kB ceiling, but the diag build is the tight one: measure before adding
to the readout.

## How the watchdog budget was measured

The simulator (and device) abort an `onUpdate` that executes too long —
the limit is an *instruction count*, not wall time. Calibration: replace
`onUpdate` with `for (var i = 0; i < N; i++) { acc = (acc + i) & 0x7FFFFFFF; }`
and bisect N. Result: N=3000 survives, N=4000 trips → with ~7-9 VM ops per
iteration, roughly 25-30k instructions of headroom. Design hot paths to that
number; `Instrument`'s ms reading is for trend-watching, not the limit itself.

## Budget allocation in devface (approximate)

| Phase | Cost |
|---|---|
| DataSource.refresh (clock/date/activity/HR/system) | ~2k |
| 7-seg clock (4 digits × fillPolygon) + date + overlay | ~3k |
| Sun compass: Solar.position + rose draw (1 sin + 1 cos + ~10 Dc calls) | ~1-2k (frame time measured at 8–12 ms) |
| **Total** | **~6-7k** — comfortably within the watchdog budget |

Adding a heavy generative or per-pixel layer later: keep its per-tick cost
inside the budget by spreading work across ticks, and measure with the overlay
before and after — the watchdog gives no warning, only crashes. When one does
crash, **docs/watchdog-debugging.md** is the playbook: reproduce the trip in the
sim, decode the crash PCs, and measure the real per-layer cost (the Python
sandbox proxy can't see the method-call cost that actually trips it).

## Historical: two-worlds V1 (BioBloom), June to October 2026

V1 is retired (`archive/faces/two-worlds`, engine in `archive/core/genart`);
these are its last measurements, kept for comparison. The test and paths named
here are the archived ones and no longer run in place: `archive/README.md`
names the commit where they did.

### RAM by UI component (V1)

`archive/faces/two-worlds/tests/TestTwoWorlds.mc` → `testLayerRamProfile`, the
test the V2 one was ported from, measured these with `scripts/test.sh two-worlds`.
The chart is rendered by `python3 archive/sketches/ram_breakdown.py` (→ `archive/sketches/out/ram-breakdown.png`).

Measured deltas (SDK 9.2.0, debug sim) — the face's own allocation footprint:

| UI component | bytes | % of UI alloc |
|---|---:|---:|
| BioBloom dish (arrays sized to the caps) | 5,976 | 45.1% |
| Font bitmaps (time / date / dow / colon) | 4,880 | 36.8% |
| Field mask (188 merged rects) | 1,080 | 8.2% |
| Sun / north marker (`_quad`) | 320 | 2.4% |
| Snapshot (device state, ~21 fields) | 320 | 2.4% |
| Compositor (10-ref render list) | 216 | 1.6% |
| Breach warning | 160 | 1.2% |
| Uplink (phone bars) | 104 | 0.8% |
| Border | 96 | 0.7% |
| Battery | 96 | 0.7% |
| **Total UI allocation** | **13,248** | **100%** |

Read the **deltas, not the absolute total** (the debug build also carries the
unit-test suite, so its `usedMemory` ≈ 64 KB is not the release figure). The UI we
allocate is ~12.9 KB (~20% of the 64 KB limit); the rest is the Monkey C runtime /
bytecode working set.

**Measured release runtime (two-worlds, `-r`):** `usedMemory` **55,208 B** of
`totalMemory` **61,256 B** the app is given (≈53.9 / 59.8 KB) — under the 57.6 KB
policy ceiling, with **~6 KB free** to the app ceiling and **~10 KB** to the 64 KB
hard limit. So the ~13 KB of UI data rides on a ~42 KB runtime/bytecode baseline.
The unoptimized build (no `-r`, what `scripts/test.sh` runs) reads ~57/59 KB — `-r`
both lowers used and frees more total, roughly tripling the free headroom (2 → 6
KB). To re-measure: release stubs the `Instrument` overlay, so either read the
sim's memory view, or temporarily have the `(:release)` `Instrument.tickEnd` print
`getSystemStats()` and run `scripts/sim.sh two-worlds` (revert after).

Two findings worth keeping:

- **The dish does not grow over the day.** Every BioBloom array is pre-allocated at
  its cap (`KMAX`/`BMAX`/`BBANDS`/`CBANDS`) in `initialize()`, so `bloomGrown` is
  **0 B** — a full accreted day fills existing slots, it never allocates more. RAM
  is bounded by the caps, full stop.
- **Font bitmaps nearly equal the whole dish** (4,880 vs 5,976 B). Decoded pixel
  data, not Numbers — the cheapest place to claw back RAM if ever needed is the
  font strips, not the generative art.

**V1 narrowed too (2026-10).** V1's `monkey.jungle` still pulled all
of core, so once MossGrove.mc landed, a rebuilt V1 release died "Out Of Memory"
on load in the sim (PRG 57.0 KB; the tracked June PRG predated MossGrove and
still ran). With the same per-file `sourcePath` narrowing (release and debug
jungles) it loads at **46.8/59.8 kB** (sim status bar), PRG 36.4 KB -- below the
June 53.9 KB above, since StrataField/Flock no longer ship dead either.
