# Memory & execution budget (fr735xt)

## The numbers (measured, June 2026, SDK 9.2.0)

| Quantity | Value | Source |
|---|---|---|
| Watch-face memory limit | **65,536 bytes (64 KB)** | `~/.Garmin/ConnectIQ/Devices/fr735xt/compiler.json` → `appTypes[type=watchFace].memoryLimit` |
| Working ceiling (project policy) | **58,982 bytes (~57.6 KB, 90%)** | `scripts/memcheck.sh` |
| devface release PRG on disk | **17,196 bytes (~16 KB)** | `scripts/memcheck.sh` / `ls bin/devface.prg` |
| devface onUpdate duration (sim) | **8–12 ms** | `Instrument` (System.getTimer deltas) |
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

## RAM by UI component (measured, two-worlds)

`Instrument` only samples whole-app `usedMemory`. To decompose it,
`faces/two-worlds/tests/TestTwoWorlds.mc` → `testLayerRamProfile` is the RAM
analog of `testLayerCostProfile`: it allocates each `onLayout` component in render
order and records the `getSystemStats().usedMemory` **delta** each one adds. Run
`scripts/test.sh two-worlds` and read the `RAM bytes:` debug line. Render the chart
with `python3 sketches/ram_breakdown.py` (→ `sketches/out/ram-breakdown.png`).

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
it actually uses — and re-run this measurement** (release `Instrument.tickStart`
print, recipe above).

**Re-measured 2026-10** after the effort-bead growth rings + recorded-workout
HR backfill (MossGrove `_edur/_eband/_hrBuf/_pool`, `DataSource.hrMinutes`):
**43.2/59.8 kB** (sim status bar) under the pinned worst case -- 16 beads with
six distinct bands each, max cushion, 10 h root star, AND a 12-minute
(`CHUNK`) history replay into an open episode in the same `onUpdate`. No
watchdog trip. The probe is the one in docs/watchdog-debugging.md plus
`_edur[i] = 600`, a six-zone `_eband[i]`, `_epiOn = true; _epiIdx = 15`,
`_lastMin = nm - 13`, and `hrMinutes` forced to fill HR 150.

> Note: `faces/two-worlds/monkey.jungle` (V1) still pulls all of core and so now
> carries MossGrove dead; its June figure above (55.2 KB, ~6 KB free) predates
> MossGrove.mc. Unmeasured since; the same narrowing would recover it.

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
