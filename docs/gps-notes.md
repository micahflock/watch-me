# GPS / Position on a watch face (fr735xt, CIQ 2.4)

The repo assumed for a year that a watch face on this device cannot see a
position at all (`docs/api-2.4-notes.md`, `Snapshot.mc`: "no GPS at this API
level for watch faces"). That assumption is **too broad**. This note records
what is verified, what is still open, and what each answer would mean.

## Verified against the SDK and the simulator (2026-09)

| Fact | Evidence |
|---|---|
| `Position.getInfo()` is **API Level 1.0.0** | SDK 9.2.0 docs, `Toybox/Position.html` |
| `Position.Info.accuracy` / `.position` / `.when` are all **1.0.0** | `Toybox/Position/Info.html` |
| **Forerunner® 735xt** is in `Position.Info`'s supported-device list | same page |
| `Position.getInfo` is in this device's own API surface | `~/.Garmin/ConnectIQ/Devices/fr735xt/fr735xt.api.debug.xml` |
| A **watch face** requesting `<iq:uses-permission id="Positioning"/>` compiles for `fr735xt` | `scripts/build.sh gpsprobe` — no warning, no error |
| …and runs: `getInfo()` returns an `Info` object, no exception | `scripts/sim.sh gpsprobe` |
| The call is **free** at watch-face cadence: `Sys.getTimer()` delta 0 ms | probe console |

What remains genuinely unavailable to a watch face: `Position.enableLocationEvents()`
(turning the receiver on), sensors, and the network. Only the *read* of whatever
the system already has is on the table — which is exactly what a sun-azimuth
calculation needs.

## What the simulator says, and why it settles nothing

With the simulator's GPS off (its default) the probe reads:

```
acc 0 (QUALITY_NOT_AVAILABLE)   pos null   age 0s   act --
```

That is consistent with **both** of the possibilities that matter:

- the device never hands a watch face a cached fix (feature dead), or
- the *simulator* simply has nothing cached (feature fine on hardware).

Two details worth carrying forward from that reading:

- `info.when` was populated (≈ "now") **even with no fix and a null position**,
  so `when` is only a freshness signal when a position actually exists — never
  test it on its own.
- `Activity.getActivityInfo().currentLocation` is `null` in a watch face, so
  there is no second source to fall back on.

## The permission is not optional, and its absence is not catchable

Calling `Position.getInfo()` from a face whose manifest does not request
Positioning does **not** return null and does **not** throw a catchable
exception. It raises

```
Error: Permission Required
Details: Permission for module 'Toybox.Position' required
```

which is a hard app error: a `try { ... } catch (e) { }` wrapped directly around
the call does not stop it. Verified the expensive way — it took down the whole
devface unit-test run, from inside a try block (`faces/devface/tests/TestDataSource.mc`).

`DataSource` compiles into **every** face via `core/src`, so a bare call there
would kill every face that has not asked for the permission. Hence
`DataSource._gpsEnabled`: the GPS read is OFF by default and a face opts in from
its app startup (`DataSource.enableGps(true)`) **only** if its own manifest
requests Positioning. Today that is `two-worlds-v2` alone. `testGpsDisabledByDefault`
and `testLocationFallsBackToProperties` exist to keep it that way — the latter
passes only if `refresh()` never touches Position on a face that has not opted in.

## The probe (`faces/gpsprobe`, `bin/gpsprobe.prg`)

A standalone sideloadable face — no core library, no properties — that draws
what `Position.getInfo()` returns on the wrist:

```
GPS PROBE
ACC LAST              <- NULL / NONE / LAST / POOR / USABLE / GOOD
45.5126
-122.6387             <- or "no position"
age 3h12m   act --    <- now - info.when, and the Activity fallback
19:19  u8             <- clock + update counter, so a frozen reading is obvious
```

Sideload it (docs/sideload.md), leave it on for a while, and read it **after a
GPS activity** — that is the case the whole plan rests on. Grant the Positioning
permission if the watch prompts.

| Reading | Meaning |
|---|---|
| `ACC NONE`, no position, even hours after a GPS run | The device gives a watch face nothing. A GPS status icon and GPS-derived location are both off the table; `lat`/`lng` properties stay the only source. |
| `ACC LAST` + plausible coordinates | The expected good case. The cached fix is enough for the sun compass (position error of even 100 km costs the azimuth ~1°), and an indicator can honestly show "the watch has a location, this old". |
| `ACC POOR/USABLE/GOOD` | A live receiver while the face is drawn. Not expected outside an activity — if it ever shows, a real "GPS locked" indicator becomes possible. |

## What "show if GPS is connected" can and cannot mean here

The GPS receiver is off whenever a watch face is on screen: it powers up for an
activity, and during an activity the activity screens are showing, not the face.
So a live satellite-lock indicator would be dark permanently — true, and useless.

What an indicator can honestly report is **whether the watch holds a position
fix, and how stale it is** — which is also exactly the thing the sun/north
marker depends on, so one glyph explains the marker's state as a side effect.

That is what shipped in `two-worlds-v2` (owner call, 2026-09): a reticle left of
the day/date readout, dark gray with no fix, amber with a fix older than
`DataSource.GPS_FRESH_SEC`, green with a current one. The `lat`/`lng` properties
deliberately do NOT light it — it reports the GPS, not whether a location is
known from some other source.

## Verifying it without a receiver

The simulator can only ever show the no-fix state, so the states and the
GPS-to-marker path were verified by temporarily planting a fix inside
`readPosition()` (the same temp-probe discipline as docs/watchdog-debugging.md)
and running the release build:

- green reticle, and `SunCompass` fed by the planted coordinates;
- the north marker drawn from a GPS-sourced position — with the caveat that the
  marker rides a circle of radius 101.7 about (107.5, 90) on a 215x180 screen,
  so a dial angle near 6 o'clock puts it off the bottom edge entirely. Pick test
  coordinates whose sun is both UP and not due-south at the simulator's UTC
  clock, or the render looks like a regression when nothing is wrong.
- the simulator's clock is UTC while the face renders 12-hour time: "7:51" on
  screen was 19:51 UTC, which is why a Greenwich fix correctly showed no marker
  (`elev = -15.15`). Read the hour from the console, not the face, when
  reasoning about the sun.
