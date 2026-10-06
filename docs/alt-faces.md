# Alternate faces: brief and round-1 concepts

A side project to explore watch faces that say much of what two-worlds V2
says, in new visual languages. This doc is the brief, taken from the owner
interview on 2026-10-06, plus the concepts it produced. Everything is
sandbox-only so far. Per CLAUDE.md, nothing gets ported to Monkey C until
the owner signs off on a direction.

```bash
python3 sketches/alt_faces.py                # all concept sheets + overview -> sketches/out/alt/
python3 sketches/alt_faces.py vessel ledger  # just these
python3 sketches/scrub.py alt_vessel         # the usual scrub strip also works
```

## What V2 communicates (the starting point)

V2 shows three kinds of information:

- **Exact readouts:** time and weekday/date.
- **Status lights:** phone link, battery in 3 chunks, GPS-fix freshness, and the
  sun-compass north marker.
- **The day as a moss organism:** movement sets the cushion size and the tufts;
  each effort episode at HR ≥ 105 is a bead; last night's inferred sleep is the
  root star, with each wake-up shown as a white speck.

The organism encodes *what* happened, not *when*.

A bug found during the analysis: V2's north marker rides a 101.7 px circle,
and that circle leaves the screen's flat bottom chord. Around solar noon the
marker is off-screen. In Portland that's about 11:30–14:30 in October and
about 4 h in December. `altkit.rim_point()` follows the visible edge instead,
and every concept here uses it.

## The brief (owner answers, condensed)

**Use.** The owner checks the time all day, and checks the face in the morning
for sleep. They also look while out walking or running, and during the day to
see "how much activity I'm getting". It's mostly for them. It's fine if the face
takes study, and it should look fine in any light without being optimised for it.

**Information contract.** A face should cover at least most of this:

| Must | Nice | Can drop |
|---|---|---|
| time (**not smaller** than V2's), date, **how much I moved** | weekday, battery (only when low), sun/north or another "neat trick", each effort, HR-zone colour, sleep length, **wake-ups**, sunrise/sunset, daylight left, moon phase | phone link, GPS freshness |

- **Priority:** movement > sleep > effort.
- **Effort threshold:** HR ≥ 105 is fine (resting HR is ~48).
- **Sleep:** the owner wears the watch overnight, is in bed ~23:00 and up ~6:00,
  and wake-ups matter.
- **Status lights:** show them only when needed.
- **Milestones:** none, no celebrations.
- **Time-of-day:** only if it fits the design.
- **Memory span:** open.
- **Numbers vs pictures:** "anything that looks good".

**Taste.**

- **Liked:** the earlier nebula (G), colony (F) and murmuration (M) sketches,
  for being "visually interesting".
- **Disliked:**
  - chronodish (A) and dayrays (C) as "ugly";
  - strataflock (K) as "disjointed";
  - V1's biobloom field as "a mess, hard to parse".
- **V2:** the owner likes how functional it is and its organic look. Nothing
  about it bothers them.
- **Avoid:** steampunk, and the classic-watch vibe (roman numerals, gilding).
- **Open:** abstract or literal; metaphors ("go crazy"); portrait, place or
  record; loud or restrained colour.
- **Background:** black blends with the bezel; white would show off the
  semiround screen, which is "kind of neat".
- **Influences:** don't index on any single one.
- **Approach:** start fresh (no V2 parts), and one fixed design per face, with
  no settings.
- **Surprises:** rare special looks are fine ("could be cute").
- **Location:** the owner is in Portland.

## Sandbox kit

- **`sketches/altkit.py`:** the shared pieces.
  - Bitmap fonts: a classic 5×7, a square 5×7, and a 3×5 for small text. One
    blit per glyph, the same as a StripGlyphs strip.
  - Sun position and sunrise/sunset (a port of `Solar.mc`), the sun-compass
    dial, and moon phase.
  - `rim_point()` for the visible edge.
  - The 9-step HR ramp.
  - **`DayLog`**: 96 quarter-hour buckets (steps, peak zone, minutes asleep).
    Episodes merge across dips of ≤ 5 min below 105 bpm, so a brisk walk
    hovering at 105 doesn't split into confetti. Last night's sleep is a
    *session* (start, end, minutes, wake-up times) that spans midnight; asleep
    means HR ≤ 62. About 0.6 KB packed.
  - Owner-like simulated days, replayed over two days so the night is in the
    record: `weekday`, `hike`, `restless` (3 wake-ups, battery low) and `rest`.
- **`sketches/alt_faces.py`:** the review-sheet driver. It renders a weekday
  scrub, the other day types, a legend and the VM proxy for each concept, plus
  a side-by-side overview.
- **`sketches/algos/alt_*.py`:** the concepts, as ordinary sandbox algos.

## Round 1: six concepts (awaiting owner feedback)

| Concept | Face | Movement (must) | Sleep / wake-ups | Effort | Trick | Peak VM proxy |
|---|---|---|---|---|---|---|
| **Ledger** | white | 96 quarter-hour dots in rows of 4 h; dot size = steps; big step count | blue dots; red ring = wake-up | dot in zone colour | grey dots ahead: pale = daylight left; sun times | ~1.1k |
| **Murmuration** | black | a flock, 1 bird per 60 steps, as a swirling ribbon in hatch order that drifts each minute | birds on a 21:00→09:00 wire; a bird in flight = wake-up | warm stretch of the ribbon | moon phase, north tick | ~13.5k |
| **Cascade** | black | 1 fir per 400 steps, planted at the hour earned on a midnight→midnight ridgeline | stars, 1 per 15 min asleep; shooting star = wake-up | round autumn maples | today's real sun-altitude path with the sun at *now*; sunrise/sunset; moon | ~6.6k |
| **Mosaic** | white | the field splits into more panes, 1 cut per 250 steps | blue column (width ~ hours); black crack = wake-up | every other effort cut takes zone colour, the only colour on the face | north tick, moon | ~3.4k |
| **Vessel** | black | giant outlined numerals fill to steps ÷ goal, layered in time order; bubbles past the goal | night bar on a 21→09 ruler; gap + tick = wake-up; duration | warm layer | daylight bar (sunrise→sunset, dot = now) | ~3.3k |
| **Galaxy** | black | tilted 2-arm spiral, 1 star per 70 steps, winding outward in time order | the core (bigger = longer); yellow spark = wake-up | warm stars | moon, north tick | ~12.7k |

Notes for whoever ports a winner:

- **VM proxy.** It is a *lower bound*; see `docs/watchdog-debugging.md`.
  Murmuration and Galaxy draw ~300 per-element primitives, so expect to trim
  the counts (or the per-element math) on the wrist. The other four are cheap.
- **State.** Everything renders from `DayLog` plus the date seed, with no
  stored geometry. Mosaic replays its splits in O(n) each frame.
- **RAM.** Font strips cost decoded-bitmap RAM (V2's fonts were ~4.9 KB).
  Vessel's big numerals are cell-built rectangles, so they cost no bitmap RAM.
- **Workout backfill.** `DayLog` assumes one update per minute. On the watch
  it needs V2's gap backfill (HR history, spread steps) for recorded workouts.
