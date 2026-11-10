# Archive

Finished experiments: every exploration that led to the shipped face, kept as
a record. **Nothing here is part of the working set.** The build, the tests,
the sandbox (`sketches/`) and `readme_figs.py` do not need this directory; the
only things that reach into it are the project README, which embeds the sheets
from `sketches/out/` to tell the design story, and the name lookup noted below.

- **Frozen.** A script here records a decision that has been made. Don't
  update it to follow the face; start a new experiment in `sketches/` instead.
- **Out of the way.** `/.ignore` keeps content searches out of this tree, and
  `CLAUDE.md` tells Claude not to read it unless asked.
- **Still runnable.** Each script imports `_live.py`, which puts the live
  sandbox on `sys.path`, so it renders against today's device model and
  engine mirrors:

  ```bash
  python3 archive/sketches/bead_compare.py     # rewrites its sheet in archive/sketches/out/
  python3 sketches/scrub.py nebula             # an archived algo, by name
  ```

  Because the scripts replay the *current* `sketches/algos/moss_grove.py`,
  a sheet re-rendered after the engine changes will no longer match the
  committed one. The committed PNG is the record; the script is how it was made.
  (As of the 2026-11 move, every script reproduced its committed sheet exactly.)

The one live dependency: `sketches/harness.py` resolves algo names in
`archive/sketches/algos/` after `sketches/algos/`, purely so the scrub command
above works.

## When an experiment is finished

Work in progress lives in `sketches/` (script) and `sketches/out/` (sheets).
Once the owner has picked an option and it has shipped (or been dropped):

1. `git mv` the script to `archive/sketches/` and its sheets to
   `archive/sketches/out/`.
2. In the script, add `import _live  # noqa: F401` right after its
   `sys.path.insert(0, ...)` line.
3. Add a row to the index below: what was asked, what was decided.

Keep a script in `sketches/` only if the face still needs it to *generate*
something (today: `border_aa_compare.py --emit`, `breach_compare.py --emit`).

## Index

Sheets are in `sketches/out/`, scripts in `sketches/`, algos in
`sketches/algos/` (all relative to this directory). Each script's docstring has
the full story; the project README's "design process" section shows the
highlights in order.

### The organism

| Question | Script / algos | Sheets | Outcome |
|---|---|---|---|
| First concepts on a loose mock (truchet, murmuration, sediment, hybrid) | `genart_sketches.py` | `weathered-truchet`, `murmuration`, `sediment`, `strata-flock` | Hybrid became `faces/strataflock`. Write-up in the appendix below |
| A dish that grows from the centre | algos `chronodish`, `colony`, `bloom` | `*-scrub` | Combined into BioBloom (V1) |
| BioBloom's morning: what to show before any steps | algo `biobloom_morning`, `morning_proto.py`, `scenarios.py` | `morning-730`, `scenarios`, `biobloom_morning-active`, `newday` | Sleep-seeded spore colony shipped in V1 |
| BioBloom's RAM: parametric arms instead of vertex lists | algos `biobloom_parametric`, `biobloom_parametric_coarse`, `save_compare.py`, `verify_persist.py` | `save-compare`, `parametric-vs-ship`, `parametric-coarse-compare`, `biobloom_parametric*-scrub` | Coarse parametric skeleton shipped in V1 |
| V1 RAM by component | `ram_breakdown.py` | `ram-breakdown` | Figure for `docs/memory-budget.md` |
| V2 direction: encode time of day? | algos `dayring`, `dayrays`, `dayspiral` | `day*-active`, `day*-rest` | Dropped: legible, but a chart, not an organism |
| V2 direction: time-agnostic organisms | algos `nebula`, `neurons`, `moss` | `nebula-*`, `neurons-*`, `moss-*` | Moss chosen |
| Making moss read as one body | algos `moss_cushion`, `moss_colony`, `moss_lobes` | `moss_cushion-*`, `moss_colony-*`, `moss_lobes-*` | Cushion + colony hybrid = `moss_grove` |
| Tuft colour and sleep seed for the grove | `grove_base.py`, `grove_explore.py` | `explore-tufts`, `explore-sleep`, `explore-shapes`, `explore-best4`, `explore-coretop` | Tufts tint to the dominant elevated zone; sleep drawn on top |
| Sleep nucleus read as a workout | `sleep_compare.py`, algos `moss_grove_pool`, `moss_grove_lunar` | `sleep-compare-nights`, `sleep-compare-day`, `moss_grove*-restless*` | B, the silver root star (2026-07) |
| Beads floating off the moss, then huddling | `bead_compare.py`, algo `moss_grove_rimhug` | `bead-contiguity-compare` | Exact keep-out + stalks, then golden-angle orbits (2026-07) |
| Beads all the same size | `bead_size_compare.py` | `bead-size-compare` | `1 + isqrt(mag)`, cap 24 (2026-10) |
| Show HR through an effort; recorded workouts | `bead_band_compare.py` | `bead-band-compare` | Equal-area growth rings + HR-history gap replay (2026-10) |
| Ramp runs a zone hot against Garmin's gauge | `zone_color_compare.py` | `zone-color-compare` | "C keep105" (2026-10-18) |
| A line on the moss's leading edge | `rim_compare.py` | `rim-compare*`, `rim-tendrils*`, `rim-wider*` | 1 px dark-blue rim, 5 px tendrils at every vertex (2026-10) |
| Reference renders of the shipped grove | (scrub) | `moss_grove-scrub`, `-active`, `-heavy`, `-rest*`, `strataflock-scrub`, `biobloom-*` | As of the 2026-11 move |

### The chrome

| Question | Script | Sheets | Outcome |
|---|---|---|---|
| North marker leaves the glass near 6 and 12 o'clock | `north_compare.py` | `north-tracks`, `north-compare-*`, `north-clock24`, `north-ondevice` | Track cut flat at the screen edges; marker drawn last (2026-10) |
| A GPS-freshness icon | `gps_dish_compare.py` | `gps-dish-*`, `gps-pip-states` | Satellite dish shipped briefly, then retired (next row) |
| Uplink bars as the GPS indicator | `uplink_gps_compare.py` | `uplink-gps-compare` | Bars show GPS fix in blue / amber / grey; dish removed (2026-10) |
| Phone-connected indicator | `phone_ring_compare.py` | `phone-ring-compare` | A, the 2 px blue ring at the glass edge (2026-10) |
| A grey outline outside the white border | `border_outline_compare.py` | `border-outline-compare`, `-zoom` | Not shipped; anti-aliasing instead |
| Anti-aliasing the white border | `sketches/border_aa_compare.py` (live: it generates the face's tables) | `border-aa-compare`, `-zoom` | "dk+lt ramp" (2026-10) |
| Halftone texture in the chrome | `halftone_compare.py` | `halftone-compare`, `-zoom` | Not shipped |
| CONTAINMENT BREACH banner | `sketches/breach_compare.py` (live: it generates the face's bitmaps) | `breach-compare`, `breach-zoom`, `breach-mid*`, `breach-tall*` | Style B at 12 px (2026-10) |

### Documents

| File | What it is |
|---|---|
| `docs/kickoff-prompt.md` | The prompt that started the software side of the project |
| `docs/claude-design-prompt.md` | Sets Claude Design up as a pixel-accurate fr735xt studio |
| `docs/claude-design-handoff.md` | Exports a finished design as a build spec; V1's chrome was built from it |

## Appendix: the first concept sketches (pre-port)

The original candidate engines, prototyped in Python on a *loose* mock of the
735XT display (separate float math / `ihash`; predates the faithful sandbox
above). Run:

```bash
python3 archive/sketches/genart_sketches.py    # writes archive/sketches/out/*.png
```

Each contact sheet shows 07:50 (mid morning run), 13:05 (after a lunch
walk), 21:45 (full day) of the same simulated day. Captions show primitive
calls per frame (watchdog proxy) and persistent state bytes (RAM proxy).

### 1. Weathered Truchet (`weathered-truchet.png`)

Smith-tile quarter arcs, roughed up three ways: tiles **unlock in shuffled
order** through the day (canvas fills as the day does); a tile's
**subdivision depth** comes from step count in its 48-minute window (active
hours render as fine 9 px filigree, idle hours as fat 36 px arcs); each
minute movement **flips tiles**, recoloring them with the current HR zone,
and untouched tiles cool through LT_GRAY to DK_GRAY. ~10% of subtiles
corrupt into 10 PRINT diagonals or voids.

- Data → form: steps→density, HR→color of fresh tiles, movement→churn rate,
  date→layout seed.
- Cost: ≤ ~960 arcs worst case, typically ~120. State: 120 B.

### 2. Murmuration (`murmuration.png`)

tixy.land's dot lattice, bent out of true. Dots **wake** as cumulative
steps grow; a day-seeded Lissajous **attractor** wanders the screen and
nearby dots swell and take the current HR-zone color; sine-noise
displacement (driven by current movement plus a 45-min decaying "unrest"
trace) warps the lattice; dots that drift close grow DK_GRAY filaments.

- Data → form: cumulative steps→population, HR→flock color+pulse,
  movement→warp amplitude, date→attractor orbit.
- Cost: ~300 primitives. State: 0 B — fully re-derived each frame from
  (seed, minute, biometrics), fxhash-style.

### 3. Sediment (`sediment.png`)

The day as a core sample. Every minute drops grains (more when stepping)
near a cursor that **sweeps left→right with the clock**; movement widens
scatter, stillness stacks towers; columns **topple onto shorter neighbors**
so dunes find an angle of repose. Grain color is the HR zone of that
minute: sleep lays DK_BLUE bedrock, a run deposits an ORANGE seam, the gym
a GREEN ridge. A white grain marks "now". Midnight starts a fresh canvas.

- Data → form: time→x position, steps→deposition rate, HR→strata color,
  movement→scatter width.
- Cost: ~450 fillRects by late evening. State: 54-column RLE, ~900 B.

### 4. Strata + Flock hybrid (`strata-flock.png`)

Sediment is the past, the murmuration is the present. A slower-accreting
strata landscape (chronological left→right) fills the bottom; above the
skyline the flock lives in the sky, colored by the *current* HR zone, with
the attractor confined to the upper half. Dots that drift below the
terrain are buried and not drawn; dots grazing the surface leave a LT_GRAY
speck on the crust — the flock precipitating into sediment.

- Data → form: everything from concepts 2 and 3 combined; the skyline
  itself becomes an input to the flock (terrain culls/landing).
- Cost: ~700 primitives by late evening (sum of both engines — still far
  under budget). State: strata RLE only, ~900 B; flock stateless.

### Ported to a face: `faces/strataflock`

Concept 4 is implemented as a real watch face under `faces/strataflock`
(`StrataField.mc` = strata, `Flock.mc` = murmuration, `GenArt.mc` = shared
integer hash / sine table / HR-zone ramp). All math is integer; the strata
evolves incrementally (≤12 minutes of catch-up per `onUpdate`); the flock is
stateless. Verified in the SDK 9.2.0 simulator on `fr735xt`:

- 6 unit tests pass (`scripts/test.sh strataflock`) — hash determinism, sine
  table, zone mapping, strata conservation/caps/idle-drip/day-rollover.
- Release PRG 21 KB on disk; debug runtime RAM ~39/59 KB (under the 90%
  ceiling, and the debug build carries the test suite).
- Full-day evening frame renders in 12–16 ms with no watchdog trip; cold
  start ~4 ms. (A whole day cannot be replayed in a single `onUpdate` — that
  trips the watchdog — but the real face never does that.)

`sketches/out/strataflock-ondevice.png` is a simulator capture at a synthetic full day
(18:20, post-gym): the flock in the sky with hot dots at the attractor, the
strata mountain below with sleep/run/gym color bands. The "39/59K" text is
the debug memory overlay, stripped in release.

### Porting notes (Monkey C, API 2.4)

- All randomness is `ihash()` (FNV-style integer hash) — deterministic,
  no float, ports directly.
- `math.sin` in concepts 1–2 becomes the existing sine LUT / `MathX`
  (no `Math.floor` etc.).
- Truchet and Sediment evolve **incrementally** (one minute of state per
  `onUpdate`); the sketch replays the whole day only because it renders
  arbitrary snapshots. Murmuration is stateless by construction.
- Primitive counts stay well under the ~25–30k VM-instruction watchdog;
  nothing draws per-pixel.
- Real inputs: `ActivityMonitor.getInfo()` steps, `Activity.getActivityInfo()
  .currentHeartRate` (or `getHeartRateHistory` on 2.4), movement proxied by
  step delta per minute.
