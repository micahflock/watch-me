# Memory & execution budget (fr735xt)

## The numbers (measured, June 2026, SDK 9.2.0)

| Quantity | Value | Source |
|---|---|---|
| Watch-face memory limit | **65,536 bytes (64 KB)** | `~/.Garmin/ConnectIQ/Devices/fr735xt/compiler.json` → `appTypes[type=watchFace].memoryLimit` |
| Working ceiling (project policy) | **45,875 bytes (~44.8 KB, 70%)** | `scripts/memcheck.sh` |
| devface runtime, **release** build (40×30 Life + sun compass) | **~29.7 KB** | simulator status bar (Instrument is stubbed in release) |
| devface runtime peak, **debug** build (tests + instrumentation ride along) | **~45 KB** (~40 KB pre-compass, same sim/day) | `Instrument` overlay in sim |
| devface onUpdate duration (sim) | **8–12 ms** (unchanged by the compass) | `Instrument` (System.getTimer deltas) |
| devface release PRG on disk | ~24 KB (+2,064 B for the sun compass) | `ls bin/devface.prg` |
| Watchdog budget per onUpdate | **~25–30k VM instructions** | calibrated busy-loop (below) |

`getSystemStats().totalMemory` inside the app reports ~59-60 KB — the 64 KB
limit minus fixed system overhead. The Instrument overlay prints
`used/total p<peak> <frame>ms` every update.

Note the **debug** build now brushes the 70% policy ceiling (~45-46 KB vs
45,875 B) because the whole unit-test suite is compiled into it. The ceiling
is a release-build policy — release sits at ~30 KB with ample headroom — but
if the debug build ever hits the real 64 KB limit, split the test suite or
trim fixtures.

## Reading memory in the simulator

1. Build debug: `scripts/build.sh devface --debug` (instrumentation compiled in).
2. Run: `scripts/sim.sh devface --debug`. Every onUpdate prints
   `37/59K p37 9ms` (used KB / total KB, peak KB, frame ms) to the console and
   draws the same line at the screen bottom.
3. The simulator GUI also has File > View Memory; in this repo's headless setup
   the console line is the practical channel.
4. Static budget check: `scripts/memcheck.sh devface`.

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
| LifeEngine band: 5 rows × 40 cells, inlined | ~8k |
| Life render: word/nibble-skip scan + run-merged fills | ~4-6k |
| 7-seg clock (4 digits × fillPolygon) + date + overlay | ~3k |
| Sun compass: Solar.position + rose draw (1 sin + 1 cos + ~10 Dc calls) | ~1-2k (frame time measured unchanged at 8–12 ms) |
| **Total** | **~19-21k** — fits with margin |

Growing the grid: stay under budget by lowering `:rowsPerStep` (slower
generations) — render cost scales with live cells and is bounded by run
merging. Measure with the overlay before and after; the watchdog gives no
warning, only crashes.
