# Debugging a watchdog trip (fr735xt)

The watch aborts an `onUpdate` that runs too long — **"Watchdog Tripped Error -
Code Executed Too Long."** The limit is an *instruction count* (~25–30k VM
instructions; see `docs/memory-budget.md`), not wall time, and it gives **no
warning** — the face just renders fine for hours, then crashes once the day's record
grows heavy enough. This is the playbook we wish we'd had; it cost four rounds of fixes
to learn (BioBloom render, V1, June 2026). The reproduction below is written
for the shipping face (two-worlds-v2, MossGrove); the cost levers and dead ends
are the BioBloom history they were learned on (BioBloom is retired).

## The blind spot that cost us those rounds

`sketches/device.py`'s watchdog proxy (the `~N VMi` number `scrub.py` prints)
counts `hash16`/`isin` calls and a few inner-loop `ops` — but **not** the
per-vertex / per-spine **method-call overhead** that dominates on-device:
`coordX`, `coordY`, `packPt`, `upx`/`upy`, `setColor`, and the `drawLine`
dispatch itself. Each is an ordinary Monkey C call (call + body + return) and the
real render is *mostly* those. So the proxy happily read **~16k** while the real
frame was at/over the watchdog.

> **Treat the scrub `VMi` number as a loose LOWER BOUND / trend signal, never as
> proof a frame is safe.** Any loop that runs a helper call **per element**
> (per vertex, per spine, per band) is far more expensive on the wrist than the
> proxy shows. The only ground truth is the simulator (below).

## The simulator enforces the watchdog — reproduce the trip on demand

This is the key tool. You can make the worst case crash in the sim, then fix
until it doesn't.

1. **Pin a saturated record directly** at the end of `onLayout`, *after* the
   components are built and after `MossState.restore` (so FieldMask etc.
   allocate against an empty record, as in reality, and the pin is not
   overwritten by a restored save), by setting MossGrove's fields -- do **not**
   loop `advance()` to grow it (a day of `advance()` calls trips `onLayout`'s
   *own* watchdog before you ever render). Set `_lastDay` to the current day so
   the first `onUpdate` does not reset it:

   ```monkeyc
   // TEMP probe at the end of TwoWorldsV2View.onLayout(), removed before commit:
   DataSource.refresh(_state);
   var nm = (_state.hour != null) ? _state.hour * 60 + _state.minute : 720;
   _grove._lastDay = (_state.day != null) ? _state.day : 14;
   _grove._seed = 1234;
   _grove._actUnits = 4200;     // max cushion (3000), tuft size (3120), tuft
                                // count (4200) -- and the breach banner
   _grove._activeMin = 600; _grove._idleMin = 300;
   for (var z = 0; z < 9; z++) { _grove._zoneMin[z] = 10 + z * 7; }
   _grove._nepi = 16;           // EMAX beads, each at the 24 px cap ...
   for (var i = 0; i < 16; i++) {
       _grove._epz[i] = 8; _grove._emag[i] = 600;
       _grove._edur[i] = 768;   // ... with six distinct growth rings (L = 7)
       _grove._eband[i] = 3 | (4 << 4) | (5 << 8) | (6 << 12) | (7 << 16)
                        | (8 << 20) | (7 << 24);
   }
   _grove._epiOn = true; _grove._epiIdx = 15;      // the last one still open
   _grove._sleepSeed = 600; _grove._wakeSeed = 16; // 10 h root star, every root snapped
   _grove._night = 0; _grove._wakes = 0;
   _grove._pool = 1300; _grove._prev = null;       // steps for the replay to spread
   _grove._lastMin = nm - 13;   // worst case: a full CHUNK (12 min) gap replay
                                // in the same onUpdate (nm - 1 = render only)
   DataSource._probe = true;
   ```

   The gap replay only runs when `DataSource.hrMinutes` finds HR history, and
   the sim has none to give, so force it for the probe (also TEMP):

   ```monkeyc
   // core/src/data/DataSource.mc
   var _probe = false;
   function hrMinutes(buf, fromMin, n, state) {
       if (_probe) { for (var q = 0; q < n; q++) { buf[q] = 150; } return true; }
   ```

   HR 150 is zone 6, so all 12 replayed minutes land in the open episode
   (bead 15), whose first minute also takes the slot-merge path in `band()`.
   `pinSaturatedGrove()` in `faces/two-worlds-v2/tests/TestTwoWorldsV2.mc` is
   the same record, kept compiling by the test suite: copy from there if the
   fields have moved.

2. **Build RELEASE, not debug.** The debug build OOMs *running as a face*
   (instrumentation and the test suite on top of the live components blow the
   64 KB), crashing in `FieldMaskComponent.initialize` before you reach render.
   Release is what the user runs anyway. `scripts/build.sh two-worlds-v2`.

3. **Run it and watch the console.** Delete the sim's settings directory first:
   `onHide` saves the pinned record, and a later unpinned run would restore it.

   ```bash
   rm -rf /tmp/com.garmin.connectiq/GARMIN/APPS/SETTINGS
   . scripts/env.sh && ciq_start_sim fresh >/dev/null 2>&1 && ciq_sim_env
   timeout 25 "$MONKEYDO" "$REPO_ROOT/bin/two-worlds-v2.prg" "$DEVICE" 2>&1 \
     | grep -iE "watchdog|Out Of Memory|app crash"
   ```

   A trip prints `Error: Watchdog Tripped Error`. **Empty output = no trip**
   (release stubs `Instrument`, so a healthy run is silent). Fix → rebuild → re-run
   until the saturated worst case is silent. The frame should show a full moss
   with the CONTAINMENT BREACH tape across it; a bare seed means the pin did
   not take. Rebuild the unpinned face afterwards: the probe build overwrites
   `bin/two-worlds-v2.prg`.

## Decode the crash callstack

The crash log (from the wrist or the sim) lists raw PCs:

```
@PC = 0x1000428f      app bytecode  (0x1000_0000 region)
@PC = 0x30000c52      native Gfx / Math call (0x3000_0000 region)
```

Map them with the build's symbol file (`monkeyc` emits it next to the PRG;
builds are deterministic, so a fresh `scripts/build.sh` reproduces the exact
layout of the committed PRG):

```python
import re, bisect
xml = open("bin/two-worlds-v2.prg.debug.xml").read()
ent = sorted((int(p), fn, int(ln), sym) for fn,ln,p,sym in re.findall(
    r'<entry\s+filename="([^"]*)"[^>]*\blineNum="(\d+)"[^>]*\bpc="(\d+)"[^>]*\bsymbol="([^"]*)"', xml))
pcs = [e[0] for e in ent]
for hexpc in ["0x1000428f"]:                       # floor-match each PC
    e = ent[bisect.bisect_right(pcs, int(hexpc,16)) - 1]
    print(hexpc, "->", e[1].rsplit("/",1)[-1] + ":" + str(e[2]), e[3])
```

**The watchdog fires on CUMULATIVE per-`onUpdate` cost, so the callstack shows
the LAST layer that was running when the budget ran out — not necessarily the
expensive one.** Our four trips landed in `regenArm`, `ClockComponent` (layer 8
of 9), `BorderComponent.arc`, and `fillBloomLut` on different runs — all the same
root cause: the total render was too high, and the counter happened to cross in a
different place each time. Don't over-index on the exact frame; measure the split.

## Measure the real per-layer split

`faces/two-worlds-v2/tests/TestTwoWorldsV2.mc` → `testLayerCostProfile` times
each layer of the shipping face in microseconds on the sim with a `NoopDc`
(accepts every primitive, rasterizes nothing — so it measures the VM /
method-call cost the watchdog counts, not native raster), over the same pinned
saturated record as the probe above, plus the 12-minute gap replay. Run
`scripts/test.sh two-worlds-v2` and read the `per-frame us:` debug line.
**Keep this test — it is the regression canary the sandbox cannot be.**
(`testLayerRamProfile`, next to it, is the RAM analog: docs/memory-budget.md.)

What it reads for the shipping face (2026-11, wall-clock, so compare runs on
the same host rather than trusting the absolute figures):

| layer | µs / frame | share |
|---|---:|---:|
| MossGrove render (saturated) | ~9,200 | ~76% |
| Border (7 lines/arcs + 245 anti-aliasing `drawPoint`s) | ~1,000 | ~8% |
| Field mask (188 rects) | ~900 | ~7% |
| 12-minute gap replay (`advance`, not render) | ~600 | ~5% |
| North marker (`SunCompass` + 2 polygons) | ~240 | ~2% |
| Ring, GPS bars, battery, readout, clock, breach | ~160 | ~1% |

**The organism is three quarters of the frame**, as BioBloom was before it
(~92% of V1's, June 2026). The float-heavy fixed layers everyone suspects —
the border's ~90 `Math.sin/cos`, `Solar` — are small; of the chrome only the
border's per-pixel anti-aliasing calls register. Don't chase the chrome; the
organism is the cost.

## Cost levers that worked on BioBloom (ranked by payoff)

The cost is **per-frame recomputation of the dish**. Cut the *number of
per-element operations*, not the data:

1. **Arms as a coarse anchor polyline** — `regenArm` emits only the ~`REGEN_CAP`
   strided anchors, with **no per-vertex linear fill**; the skeleton is those few
   anchor-to-anchor segments. (regen-only cost: 12ms → 3ms.)
2. **Single straight spines** for blooms (was a bowed 2-segment + occasional
   fork): ~3× cheaper per spine.
3. **One color per bloom** (its hottest band = the episode's peak HR zone):
   removes the per-bloom `fillBloomLut` *and* the per-spine `setColor`. This was
   the literal straw — the reproduced trip's PC was inside `fillBloomLut`.

Net: BioBloom render **24.5ms → 11.6ms** (NoopDc proxy), worst-case saturated
`onUpdate` goes from reliably tripping to silent.

The trade is render fidelity: arms coarsen, blooms become single-color straight
fans. The **dish STATE and `save()/load()` are untouched**, so the day's record
and every HR-episode's position/size/zone-color survive — only fine detail
(wiggle, within-bloom gradient, curl/fork) is dropped.

## Measure the MARGIN, not just trip / no-trip (2026-10)

A silent run says the frame fits; it does not say by how much. Append a
calibrated busy loop to `onUpdate` in the pinned-worst-case probe --
`var acc = 0; for (var k = 0; k < N; k++) { acc = (acc + k) & 0x7FFFFFFF; }`,
~8 VM instructions per iteration (docs/memory-budget.md calibration) -- and
bisect N. two-worlds V2, saturated grove + 12-min replay + breach banner:

| build | trips at N | margin |
|---|---|---|
| anti-aliased border OFF | 500 ok, 900 trips | ~4-7k instructions |
| anti-aliased border ON (shipped) | 200 trips | **< ~1.6k** |
| ON, no replay (lastMin = nm - 1) | 200 ok, 500 trips | ~1.6-4k |

Re-measured 2026-11 with the probe above (which pins six full growth rings
per bead, `_edur` 768, a little heavier than the 2026-10 pin), before and
after the dead-code cleanup, same session and host:

| build | trips at N | margin |
|---|---|---|
| before the cleanup (PRG 41,036 B) | 100 ok, 150 trips | ~0.8-1.2k instructions |
| after (PRG 40,380 B) | 100 ok, 150 trips | **~0.8-1.2k**, unchanged |

So the working figure is **about 1k instructions to spare**. The cleanup
removed code that never ran in `onUpdate` (bar three `has` checks in
`DataSource.refresh`), so it freed RAM, not instructions.

The border's 245 static `drawPoint`s cost a few thousand instructions -- the
per-element-call cost again. A banner drawn as ~30 `fillPolygon` stripes
(8 array stores + a call each) tripped this frame outright; as two bitmaps
it does not. Anything added to V2's chrome now needs this margin check.

## Dead ends (BioBloom) — don't repeat these

- **Lowering `INK_MAX` alone shuffles, it doesn't cut.** The ink budget caps
  total *draws*; make one layer cheaper and the budget simply draws more of the
  next (cheap arms → more blooms drawn → identical total). Reduce the actual
  work, or lower the budget enough to shed work — don't rearrange it.
- **The midnight reset is NOT the bug.** A *non*-resetting dish settles
  **cheaper** over days (once arms hit `PMAX`, decimation bites and steady-state
  is light); a resetting dish **re-peaks every active day**. The binding case is
  the daily active-GROWTH peak, which recurs each active day — verified with a
  3-day replay (`sketches/`, multi-day harness). Crashing on day 2 rather than
  coasting is itself evidence the reset fires.
- **Reducing dish caps (`BMAX`/`KMAX`) doesn't fix it.** It only lightens full
  saturation; the trip happens on a *moderate, actively-growing* dish (a few
  hours with a workout), which is below the caps anyway.

## Simulator flakiness (expect it)

- `Unable to connect to simulator` is transient — retry in a short loop
  (`scripts/test.sh` already retries the sim launch; the test *run* may still
  need a second attempt).
- Pipe an interactive `monkeydo`/`xwd` through `head`/`grep` and you may see
  shell exit 144 (SIGPIPE) — harmless; check the captured file, not the exit code.
- A wedged sim clears with `ciq_start_sim fresh` (kills the whole sim/Xvfb stack).

## When a trip lands — checklist

1. Get the crash callstack PCs.
2. `scripts/build.sh <face>` → map the PCs against `bin/<face>.prg.debug.xml`.
3. Reproduce: pin a saturated record, run the **release** PRG in the sim, confirm
   the trip is real and silent-when-fixed.
4. Measure: `testLayerCostProfile` for the true per-layer split.
5. Cut the dominant per-element op count; re-run the pinned sim until the
   worst case (saturated record **+ 12-min `advance()` gap replay**) is silent.
   Then re-run the margin check above.
6. Ground truth is the sim trip/no-trip — **not** the scrub `VMi` number.
