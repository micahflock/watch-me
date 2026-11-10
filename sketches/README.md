# The sandbox

A faithful Python model of the fr735xt, for iterating on the face without the
Garmin SDK. A render takes under a second; a PRG build and sim cycle takes
minutes.

```bash
python3 sketches/scrub.py <algo> [--seed N] [--day rest|heavy|...] [--at 7:50,13:05,21:45]
```

`scrub.py` replays a synthetic biometric day minute by minute through
`sketches/algos/<algo>.py` and writes a captioned strip to
`sketches/out/<algo>-scrub.png`. Captions show the watchdog proxy (estimated VM
instructions against ~25k), state bytes (a RAM proxy) and any off-palette colour.

**The proxy is a loose lower bound, not proof of safety.** It cannot see the
per-element method-call cost that dominates on the watch
(`docs/watchdog-debugging.md`); the simulator is ground truth.

## What is here

| File | Role |
|---|---|
| `device.py` | The device model. `hash16`, `isin`, `zoneIndex` and the 14-colour palette are bit-identical to `core/src/genart/GenArt.mc`. `Dc` exposes only real `Gfx` primitives, counts every call and snaps colours to the palette |
| `day.py` | The per-minute `Snapshot` feed (steps, HR, time), mirroring what `DataSource` builds. Profiles: `active`, `rest`, `heavy`, `restless`, `hiit`, `hiit_restless` |
| `harness.py` | Shared plumbing: `load_algo`, `mins`, the watchdog-proxy sum, comparison-sheet layout. New scripts import from here rather than copying |
| `scrub.py` | One algo across a day (above) |
| `algos/moss_grove.py` | **Parity reference for `core/src/genart/MossGrove.mc`**, the shipping engine; checked against `out/moss_grove-ondevice.png` |
| `daysoma.py`, `daybuckets.py`, `mossutil.py` | What `moss_grove` is built on: the time-agnostic day record, polar helpers and the HR ramp, the lumpy-cushion outline. `MossGrove.mc` ports all three |
| `algos/biobloom.py` | State mirror of `BioBloom.mc` (V1). `readme_figs.py` uses it for the V1-vs-V2 figure |
| `algos/strataflock.py` | Line-for-line port of `StrataField.mc` + `Flock.mc`; checked against `out/strataflock-ondevice.png` |
| `twchrome.py` | The two-worlds V2 chrome (field mask, border, phone ring, GPS bars, battery, readout, clock, breach, north marker), a line-for-line port of `TwoWorldsV2View.mc`, blitting the real glyph strips |
| `solar.py` | float32 port of `Solar.mc` / `SunCompass.mc` / `MathX.mc`. `python3 sketches/solar.py` checks it against the Monkey C test fixtures |
| `border_aa_compare.py` | Generates the border's anti-aliasing tables: `--emit` rewrites the `BEGIN AA`/`END AA` block in `TwoWorldsV2View.mc` and `border_aa_pixels.py` |
| `breach_compare.py` | Generates the CONTAINMENT BREACH bitmaps (`--emit`) and owns `Banner`, which `twchrome.Breach` draws |
| `readme_figs.py`, `sim_hero.py` | Render the project README's figures into `docs/img/` |

An algo module defines `build() -> {"background", "components": [...]}`. Each
component is the same duck-typed `render(dc, state)` (plus optional
`advance(state)` and `state_bytes()`) that the Compositor draws on the watch.

## Porting rules

- Use `idiv(a, b)` / `imod(a, b)` wherever Monkey C writes `a / b` / `a % b` on
  Numbers. Monkey C truncates toward zero; Python's `//` and `%` floor, so they
  disagree on negatives (`-6200 / 127` is `-48` on the watch, `-49` with `//`).
- Because the primitives match one to one, a sandbox algo ports to `.mc`
  mechanically: `Gfx.` constants, `idiv(a, b)` → `a / b`, `var` and syntax.
- If a mirror stops matching its `*-ondevice.png` capture, the mirror has
  drifted from the Monkey C and `device.py` (or the mirror) is what to fix.
- Arc and circle rasterisation is the one thing only the SDK simulator renders
  exactly, so the last fidelity check is still `scripts/build.sh` +
  `scripts/sim.sh`.

## Experiments

A new idea starts here: an algo in `algos/`, or a comparison script built on
`harness.py` and `twchrome.py` that writes its sheet to `out/`. Show the sheet,
wait for a decision. Once the decision has shipped, the script and its sheets
move to `archive/` (steps in `archive/README.md`), so this directory stays the
working set: the model, the mirrors of what is on the wrist, and whatever is
in flight.

Every earlier experiment is indexed in `archive/README.md`.
