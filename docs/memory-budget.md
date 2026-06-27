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
