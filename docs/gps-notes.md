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
