# Debugging a watchdog trip (fr735xt)

The watch aborts an `onUpdate` that runs too long — **"Watchdog Tripped Error -
Code Executed Too Long."** The limit is an *instruction count* (~25–30k VM
instructions; see `docs/memory-budget.md`), not wall time, and it gives **no
warning** — the face just renders fine for hours, then crashes once a dish grows
heavy enough. This is the playbook we wish we'd had; it cost four rounds of fixes
to learn (BioBloom render, June 2026).

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

1. **Pin a saturated dish directly** in `onLayout`, *after* the components are
   built (so FieldMask etc. allocate against an empty dish, as in reality), by
   setting the state arrays — do **not** loop `advance()` to grow it (1000
   `advance()` calls trip `onLayout`'s *own* watchdog before you ever render).
   Set `_lastDay` to the current day and freeze steps so the first `onUpdate`
   neither resets nor grows it. Include the momentum fields or `advance()`'s
   `momentum()` dereferences a `null`:

   ```monkeyc
   // TEMP probe at the end of onLayout(), removed before commit:
   _bloom._nfil = 20;
   for (var i = 0; i < 20; i++) {
       _bloom._tha0[i] = (i*23)%256; _bloom._tha[i] = (i*23)%256;
       _bloom._thrb[i] = 7; _bloom._thnp[i] = 41; _bloom._thL[i] = 86*64;
       _bloom._thnext[i] = 88; _bloom._thv[i] = 2;
   }
   _bloom._nbloom = 16;
   for (var i = 0; i < 16; i++) {
       _bloom._blbx[i] = 90+(i%5)*8; _bloom._blby[i] = 70+(i%4)*6;
       _bloom._blang[i] = (i*16)%256; _bloom._blreach[i] = 46;
       _bloom._blw[i] = 10; _bloom._blsalt[i] = i*211; _bloom._blnb[i] = 20;
       _bloom._blmom[i] = 0; _bloom._blmom0[i] = 0; _bloom._bllastzi[i] = 4;
       for (var k = 0; k < 20; k++) { _bloom._blband[i*24+k] = ((k%9)<<8)|(2+k*2); }
   }
   _bloom._coln = 70;
   for (var k = 0; k < 70; k++) { _bloom._colband[k] = ((k%9)<<8)|(7+k); }
   _bloom._colreach = 78;
   DataSource.refresh(_state);
   _bloom._lastDay = (_state.day != null) ? _state.day : 14;
   var nm = (_state.hour != null) ? _state.hour*60+_state.minute : 720;
   _bloom._lastMin = nm - 12;   // worst case: a 12-min advance() catch-up too
   _bloom._lastSteps = 0;       // (use nm+5 / a huge _lastSteps to test render only)
   ```

2. **Build RELEASE, not debug.** The debug build OOMs *running as a face*
   (its unit-test suite + instrumentation on top of the live components blow the
   64 KB), crashing in `FieldMaskComponent.initialize` before you reach render.
   Release is what the user runs anyway. `scripts/build.sh two-worlds`.

3. **Run it and watch the console:**

   ```bash
   . scripts/env.sh && ciq_start_sim fresh >/dev/null 2>&1 && ciq_sim_env
   timeout 14 "$MONKEYDO" "$REPO_ROOT/bin/two-worlds.prg" "$DEVICE" 2>&1 \
     | grep -iE "watchdog|Out Of Memory|app crash"
   ```

   A trip prints `Error: Watchdog Tripped Error`. **Empty output = no trip**
   (release stubs `Instrument`, so a healthy run is silent). Fix → rebuild → re-run
   until the saturated worst case is silent.

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
xml = open("bin/two-worlds.prg.debug.xml").read()
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

`faces/two-worlds/tests/TestTwoWorlds.mc` → `testLayerCostProfile` times each
layer in microseconds on the sim with a `NoopDc` (accepts every primitive,
rasterizes nothing — so it measures the VM / method-call cost the watchdog
counts, not native raster). Run `scripts/test.sh two-worlds` and read the
`per-frame us:` debug line. **Keep this test — it is the regression canary the
sandbox cannot be.**

What it told us: **BioBloom render is ~92% of the frame.** The float-heavy fixed
layers everyone suspects — `BorderComponent` (~90 `Math.sin/cos`), `FieldMask`
(188 rects), `Solar` — sum to ~2k µs, a rounding error. Don't chase them; the
dish is the cost.

## Cost levers that worked (ranked by payoff)

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

## Dead ends — don't repeat these

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
3. Reproduce: pin a saturated dish, run the **release** PRG in the sim, confirm
   the trip is real and silent-when-fixed.
4. Measure: `testLayerCostProfile` for the true per-layer split.
5. Cut the dominant per-element op count; re-run the pinned sim until the
   worst case (saturated dish **+ 12-min `advance()` catch-up**) is silent.
6. Ground truth is the sim trip/no-trip — **not** the scrub `VMi` number.
