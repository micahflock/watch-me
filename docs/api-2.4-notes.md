# CIQ API 2.4 gotcha ledger (fr735xt)

The Forerunner 735XT tops out at Connect IQ **2.4.x** (device file reports
2.4.1/2.4.5 depending on part number). Everything in this repo must hold to
that line. This is the list of sharp edges we hit or designed around.

## Hard API limits — never use

| Symbol | Why |
|---|---|
| `import` statement | SDK 4.1+/CIQ 3.2+ syntax. Always `using X as Y;`. |
| `Application.Storage` / `Application.Properties` | CIQ 3.0+/4.0+. Use `AppBase.getProperty/setProperty` (object store). |
| `WatchUi.Layer` | CIQ 3.1+. The Compositor here is plain Monkey C objects. |
| `Toybox.Complications` | CIQ 3.2+. |
| `Toybox.Background` | Background services exist at 2.4 for some app types but are out of scope for this framework; do not add. |
| `Math.atan2`, `Math.floor`, `Math.ceil`, `Math.round` | **Doc trap.** Current API docs annotate them "1.3.0", but they shipped with CIQ 3.0 (the docs were retconned). Runtime `Symbol Not Found` risk on 2.4 firmware. Use `MathX.atan2/floor/fmod`. `sin/cos/tan/asin/acos/atan/sqrt/pow/PI` are genuinely 1.0.0-safe. |
| `<palette>` resource element | CIQ 3.x resource feature. Quantize PNGs offline (tools/make-dow-strip.sh). |

`scripts/test.sh` greps the source (comments stripped) for these and fails the
build if any appear.

## onPartialUpdate

**Not supported on fr735xt.** Partial updates (1 Hz seconds in low power)
require display hardware introduced with the fênix 5 / FR935 generation. The
735XT gets exactly **one full `onUpdate` per minute** in low power. Every
module in /core is designed around that cadence; there is no seconds path.

## The watchdog: the real constraint is CPU, not RAM

Empirically measured in the 9.2.0 simulator against the fr735xt profile (see
`docs/memory-budget.md` for method): an `onUpdate` gets roughly **25-30k VM
instructions** before the watchdog kills the app ("Watchdog Tripped Error -
Code Executed Too Long").

Consequences baked into the framework:

- Heavy per-pixel or per-element work in a hot loop must be inlined and its
  total cost kept inside the budget; spread expensive work across ticks rather
  than doing it all in one `onUpdate`.
- `fillRectangle`/`fillPolygon` calls are not free — batch adjacent fills and
  avoid one draw call per primitive where a region can be merged.

## Number overflow silently promotes to Long

Monkey C `Number` is 32-bit signed. Arithmetic overflow does not wrap — it
promotes to a boxed 8-byte `Long` (slow, allocates). Code that relies on
"32-bit wrap" (xorshift, common LCGs) is therefore unsafe; keep intermediates
within ±2³¹ (e.g. Park-Miller via Schrage's decomposition).

Bitwise ops (`& | ^ >> <<`) are fine; note `>>` sign-extends, so always mask
after shifting (`(word >> b) & 1`), and `1 << 31` is a negative `Number`
(harmless for bit work).

## Misc

- `Dc.setClip/clearClip` are API 2.3.0 → safe here. Used for per-component
  clips and the StripGlyphs blitter.
- `ActivityMonitor.getHeartRateHistory` is API 1.2.1 and the canonical
  watch-face HR source for this device generation. Guard with `has` and treat
  `INVALID_HR_SAMPLE` as null.
- `System.getSystemStats()` has `usedMemory/totalMemory/freeMemory/battery`
  but **no peak-memory field** at any API level — `Instrument` tracks its own
  high-water mark.
- Object store (`getProperty/setProperty`) values must stay small (KB-scale)
  and writes are flash-slow: write only in `onStop`, read only at startup /
  `onSettingsChanged`. Never read properties per tick.
- Watch faces cannot read live GPS/sensors/network at this API level:
  `Toybox.Position` needs the Positioning permission, which a watch face can't
  hold. BUT `Activity.getActivityInfo().currentLocation` (API 1.0, no
  permission) reports the device's **last known position** -- in practice the
  fix from the most recent GPS activity. It has no timestamp, so `DataSource`
  remembers the last fix it saw (object store key `gpsFix`:
  `[latE6, lonE6, stampSec]`) and stamps when it CHANGES; that stamp drives
  `Snapshot.gpsFix` (0 none / 1 stale / 2 fresh < 24 h). GPS always wins; the
  user-entered `lat`/`lng` properties are the fallback. Reject the "no fix"
  sentinels ((0,0), 180/180). `DataSource` calls `toDegrees()` on the untyped
  Location value and never names `Toybox.Position`; it builds and runs with an
  empty `<iq:permissions/>`. The headless sim reports no position (pip reads "none"); only
  the wrist proves the fr735xt keeps its last fix outside an activity.
- The SDK device id is **`fr735xt`** (not "forerunner735xt") — in
  manifest products, `monkeyc -d`, monkeydo, and the device-files directory.
- Old-style Monkey C discipline: untyped `var`s, no `as Number` annotations,
  build with `-l 0` (modern type checker off).
