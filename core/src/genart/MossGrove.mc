using Toybox.Graphics as Gfx;

// MossGrove -- the two-worlds V2 biometric organism. Line-for-line port of
// sketches/algos/moss_grove.py (the parity reference); the day record is the
// port of sketches/daysoma.py and the cushion outline of sketches/mossutil.py.
//
// The day as a living patch of moss, time-of-day intentionally NOT encoded --
// only WHAT happened, accreted in RAM and persisted across a reload (MossState),
// since the device gives only the current HR sample and cumulative steps per
// tick. From the heart outward:
//   root star      last night's inferred sleep (overnight quiescence, as in
//                  BioBloom): the silver root system the day's growth stands
//                  on. Hours = root count/length; each wake event snaps one
//                  root at a white speck and kinks the rest. Sleep speaks only
//                  the night palette (silver/blue/gray/white) -- the warm hues
//                  belong to the effort beads exclusively (the original spore
//                  clump rendered short nights in the beads' red/orange
//                  vocabulary and read as effort at a glance; owner, 2026-07).
//                  Drawn LAST so it stays on top of the day's growth all day.
//   cushion        a solid two-tone lumpy mound; radius grows with total
//                  movement; the lumpy OUTLINE varies per day from the date seed.
//   tufts          satellite colony clumps straddling the rim, popping in as
//                  activity accrues; grains glow the dominant ELEVATED HR zone.
//   texture        granular green stipple + a fuzzy rim fringe.
//   episodes       elevated-HR events as bright peak-zone fruiting beads,
//                  kept CONTIGUOUS with the moss (owner, 2026-07-13 wrist:
//                  beads used to float free on low-movement mornings): exact
//                  per-bead root-star keep-out, embed-into-the-rim pull-in,
//                  and a straight tapered podetium stalk for anything the
//                  star still forces out. Angles walk a golden sequence and
//                  tufts are dealt round-robin so beads don't pile up.
//
// All integer math (the watchdog is the binding constraint). A per-frame INK
// budget caps draw work so a maximal day stays bounded (the root star rides
// OUTSIDE the budget -- see drawSleep); the outline is sampled once per frame
// into _er/_evx/_evy instead of calling edge() per element (the pre-LUT render
// tripped the sim watchdog at saturation, 2026-07). Sandbox proxy ~10k
// VM-instr/frame peak; the saturated release frame is verified silent in the
// sim (docs/watchdog-debugging.md probe). State ~245 B.
class MossGrove {

    const CX = 107;
    const CY = 108;            // centre 2/5 of the screen height up from bottom
    const INK_MAX = 260;       // was 340 pre-LUT: rebalanced with the grain/
                               // texture caps so a saturated day draws every
                               // layer (incl. the beads, which the old budget
                               // starved) and clears the sim watchdog
    const NA = 30;             // rim samples for the cushion fans
    const BASE_DIV = 60;       // act units -> cushion radius
    const TUFT_DIV = 600;      // act units -> one more satellite tuft
    const SCN = 5;             // overall size scale = SCN/SCD (= 1.25x), applied
    const SCD = 4;             // to every radial extent
    const AMPREF = 40;         // base radius (px, scaled) at which the outline
                               // amplitudes reach 100% (see render)

    // Tip lengths must NOT be uniform (owner call, 2026-07): each lobe's
    // amplitude is hashed to 40..170% (switched at the sine zero-crossings so
    // the outline stays continuous) and a frequency-1 "tilt" sinusoid
    // stretches one side of the patch. Together these de-rigidify the 4-lobe
    // cross, so the lobe range is 2..5. The finer ripple stays in {5,7}: 4/6
    // beat against the lobe count, higher primes alias against NA=30 samples.
    const RIPPLE = [5, 7];     // cushion outline: finer ripple

    const ACTIVE = 4;          // zone idx >= this is an elevated-HR minute
    const EMAX = 16;           // cap on stored episodes
    const KACT = 6;            // steps/min -> one growth unit
    const MOM_DIV = 16;        // steps/min -> banked episode magnitude

    // sleep inference (overnight quiescence; persists across the midnight reset)
    const REST_HR = 72;
    const IDLE_SPM = 1;
    const NIGHT_START = 20;
    const NIGHT_END = 10;
    const MORNING_END = 11;
    const WAKE_START = 5;
    const SLEEP_CAP = 600;
    const WAKE_WIN_END = 6;    // wake EVENTS counted only for hours [0, this)
    const WAKE_SPM = 6;        // steps/min burst that marks a wake-up

    // 9-step HR ramp (cool rest -> hot effort), finer than GenArt.ZONE_COLORS.
    const HR_BOUNDS = [60, 80, 95, 105, 120, 138, 152, 165];
    const HR_RAMP = [
        Gfx.COLOR_DK_BLUE, Gfx.COLOR_BLUE, Gfx.COLOR_DK_GREEN, Gfx.COLOR_GREEN,
        Gfx.COLOR_YELLOW, Gfx.COLOR_ORANGE, Gfx.COLOR_RED, Gfx.COLOR_PINK,
        Gfx.COLOR_PURPLE
    ];
    const ROOT_MAX_H = 10;     // root star hour cap (SLEEP_CAP is 600 min)

    // ---- day record (port of daysoma.DayRecord) ------------------------------
    var _zoneMin;              // minutes per HR zone (9)
    var _actUnits; var _activeMin; var _idleMin;
    var _epz; var _emag; var _nepi;          // episodes: peak zone + magnitude
    var _seed;                 // per-DAY shape/placement seed (from the date)
    var _night; var _sleepSeed;              // sleep meters (survive the reset)
    var _wakes; var _wakeSeed; var _awake;   // wake events (0-6am), survive reset
    var _lastDay; var _prev;                 // _prev = last cumulative steps
    var _lastMin;              // minute-of-day last accreted (dup-call guard)
    var _epiOn; var _epiIdx;
    // render scratch (allocated once)
    var _sp;                   // per-day shape params [p1,p2,f1,f2,am1,am2,p3,am3]
    var _lamp;                 // per-lobe amplitude percents (40..170), f1 used
    var _tri;                  // reusable triangle for fillPolygon
    var _quad;                 // reusable trapezoid for the bead stalks
    var _er;                   // per-frame outline LUT: edge radius at NA angles
    var _evx; var _evy;        // ... and the 100% fan vertex offsets
    var _ink;

    function initialize() {
        _zoneMin = new [9];
        _epz = new [EMAX];
        _emag = new [EMAX];
        _sp = new [8];
        _lamp = new [5];
        _tri = [[0, 0], [0, 0], [0, 0]];
        _quad = [[0, 0], [0, 0], [0, 0], [0, 0]];
        _er = new [NA];
        _evx = new [NA];
        _evy = new [NA];
        _night = 0; _sleepSeed = 0;          // survive reset(); init once
        _wakes = 0; _wakeSeed = 0; _awake = false;
        _lastDay = -1; _prev = null;
        reset();
    }

    function reset() {
        for (var i = 0; i < 9; i++) { _zoneMin[i] = 0; }
        _actUnits = 0; _activeMin = 0; _idleMin = 0;
        for (var i = 0; i < EMAX; i++) { _epz[i] = 0; _emag[i] = 0; }
        _nepi = 0;
        _prev = null;
        _lastMin = -1;
        _epiOn = false; _epiIdx = -1;
    }

    // ---- per-minute simulation (port of daysoma.advance) ---------------------

    function advance(state) {
        if (state.hour == null || state.minute == null) { return; }
        var day = (state.day != null) ? state.day : 0;
        var now = state.hour * 60 + state.minute;
        if (day != _lastDay) {
            _sleepSeed = _night;             // hand last night to the new day
            _wakeSeed = _wakes;
            reset();
            _lastDay = day;
            var mo = (state.month != null) ? state.month : 1;
            var yr = (state.year != null) ? state.year : 2026;
            _seed = GenArt.hash16(day, mo * 32 + (yr & 63), 3) % 4096;
            _lastMin = now - 1;              // so this minute accretes exactly once
        } else if (now == _lastMin) {
            return;                          // ALREADY processed this minute --
                                             // onUpdate fires again on every wrist
                                             // raise (onExitSleep); without this guard
                                             // each glance re-counts the minute and
                                             // inflates idle/zone/sleep/episodes.
        } else if (now < _lastMin) {
            _lastMin = now;                  // clock moved back (sync/manual set):
            if (state.steps != null) { _prev = state.steps; }
            return;                          // resync, don't accrete a bogus minute
        }

        var spm = 0;
        var st = state.steps;
        if (st != null) {
            if (_prev != null && st > _prev) { spm = st - _prev; }
            _prev = st;
        }
        var move = spm / KACT;
        if (move > 0) { _actUnits += move; _activeMin += 1; }
        else { _idleMin += 1; }

        var hr = state.heartRate;
        var zi = hrZone(hr);
        if (zi >= 0) { _zoneMin[zi] += 1; }

        // overnight quiescence -> last night's sleep
        var hh = state.hour;
        var quiescent = (spm <= IDLE_SPM) && (hr == null || hr <= REST_HR);
        var isNight = (hh >= NIGHT_START || hh <= NIGHT_END);
        if (isNight && quiescent && _night < SLEEP_CAP) { _night += 1; }
        // wake EVENTS: a movement burst during [0,6) am, debounced to a rising
        // edge so one up-and-about stretch counts once (not per minute).
        if (hh >= 0 && hh < WAKE_WIN_END) {
            if (spm >= WAKE_SPM) {
                if (!_awake) { _wakes += 1; _awake = true; }
            } else if (spm <= IDLE_SPM) {
                _awake = false;
            }
        }
        if (hh <= MORNING_END && _night > _sleepSeed) { _sleepSeed = _night; }
        if (hh <= MORNING_END && _wakes > _wakeSeed) { _wakeSeed = _wakes; }
        if (spm >= KACT && hh >= WAKE_START && hh <= MORNING_END && _night > 0) {
            _night = 0;
            _wakes = 0;
            _awake = false;
        }

        // elevated-HR episode: rising edge opens a focus; track peak + magnitude
        if (zi >= ACTIVE) {
            if (!_epiOn) {
                _epiOn = true;
                _epiIdx = (_nepi < EMAX) ? _nepi : -1;
                if (_epiIdx >= 0) {
                    _epz[_epiIdx] = zi; _emag[_epiIdx] = 0; _nepi += 1;
                }
            }
            if (_epiIdx >= 0) {
                if (zi > _epz[_epiIdx]) { _epz[_epiIdx] = zi; }
                _emag[_epiIdx] += 1 + spm / MOM_DIV;
            }
        } else {
            _epiOn = false; _epiIdx = -1;
        }
        _lastMin = now;
    }

    // ---- helpers -------------------------------------------------------------

    function hrZone(hr) {
        if (hr == null || hr <= 0) { return -1; }
        for (var i = 0; i < 8; i++) {
            if (hr < HR_BOUNDS[i]) { return i; }
        }
        return 8;
    }

    function zoneColor(z) { return (z >= 0) ? HR_RAMP[z] : -1; }

    // dominant zone among zones >= floor (-1 if none)
    function dominantZone(floor) {
        var best = -1; var bestN = 0;
        for (var z = floor; z < 9; z++) {
            if (_zoneMin[z] > bestN) { bestN = _zoneMin[z]; best = z; }
        }
        return best;
    }

    function scl(v) { return v * SCN / SCD; }

    // rounded division, symmetric in sign: plain truncation shaves ~30% off
    // the stalk flare on diagonal runs (both perpendicular components round
    // toward zero)
    function rdiv(v, d) {
        var av = (v >= 0) ? v : -v;
        var q = (av + d / 2) / d;
        return (v >= 0) ? q : -q;
    }

    function rootHours(mins) {
        var h = mins / 60;
        if (h < 1) { h = 1; }
        if (h > ROOT_MAX_H) { h = ROOT_MAX_H; }
        return h;
    }

    function rootLen(mins) { return 8 + 3 * rootHours(mins); }

    function coordX(a, r) { return CX + (r * GenArt.isin(a + 64)) / 127; }
    function coordY(a, r) { return CY + (r * GenArt.isin(a)) / 127; }

    // lumpy cushion radius at angle a (uses per-day _sp/_lamp set in render):
    // per-lobe amplitude + two undulations + the frequency-1 tilt. a is 0..255
    // at every call site, so ph1 is non-negative and / and % behave. Negative
    // excursions are HALVED so the inter-lobe valleys stay shallow and the
    // body reads as one fat cushion, not a starfish (2026-07-10 wrist).
    function edge(base, a) {
        var ph1 = a * _sp[2] + _sp[0];
        var am1 = (_sp[4] * _lamp[(ph1 / 256) % _sp[2]]) / 100;
        var d = (am1 * GenArt.isin(ph1 & 255)) / 127
              + (_sp[5] * GenArt.isin((a * _sp[3] + _sp[1]) & 255)) / 127
              + (_sp[7] * GenArt.isin((a + _sp[6]) & 255)) / 127;
        if (d < 0) { d = d / 2; }
        return base + d;
    }

    // fill the lumpy disc as a fan of NA triangles from the cached outline
    // offsets, scaled scalepct/100 (100 = the dark mound, 60 = the crown) --
    // no edge()/isin per vertex; see the LUT note in render()
    function fanLut(dc, scalepct) {
        _tri[0][0] = CX;  _tri[0][1] = CY;     // apex is loop-invariant
        var x0 = CX + (_evx[0] * scalepct) / 100;
        var y0 = CY + (_evy[0] * scalepct) / 100;
        for (var i = 1; i <= NA; i++) {
            var j = i % NA;
            var x1 = CX + (_evx[j] * scalepct) / 100;
            var y1 = CY + (_evy[j] * scalepct) / 100;
            _tri[1][0] = x0;  _tri[1][1] = y0;
            _tri[2][0] = x1;  _tri[2][1] = y1;
            dc.fillPolygon(_tri);
            x0 = x1; y0 = y1;
        }
    }

    // ---- render (port of moss_grove.py render) -------------------------------

    function render(dc, state) {
        if (_idleMin == 0 && _activeMin == 0) { return; }
        _ink = INK_MAX;
        var seed = _seed;

        var dz = dominantZone(ACTIVE);
        if (dz < 0) { dz = dominantZone(0); }
        var dzcol = (dz >= 0) ? HR_RAMP[dz] : -1;
        var act = _actUnits;

        var base = 4 + act / BASE_DIV;
        if (base > 54) { base = 54; }
        base = scl(base);                       // 1.25x overall scale

        // per-day lumpy outline params (hoisted; edge() reads _sp/_lamp).
        // Amplitudes scale with the overall size AND with the cushion base
        // (min(1, base/AMPREF)): absolute amps on a small sedentary-day base
        // turned the patch into an angular starfish (2026-07-10 wrist).
        var s = (base >= AMPREF) ? 100 : (100 * base) / AMPREF;
        _sp[0] = GenArt.hash16(seed, 1, 3) % 256;
        _sp[1] = GenArt.hash16(seed, 2, 3) % 256;
        _sp[2] = 2 + GenArt.hash16(seed, 3, 3) % 4;        // 2..5 lobes
        _sp[3] = RIPPLE[GenArt.hash16(seed, 4, 3) % 2];
        _sp[4] = (scl(7 + GenArt.hash16(seed, 5, 3) % 7) * s) / 100;
        _sp[5] = (scl(3 + GenArt.hash16(seed, 6, 3) % 4) * s) / 100;
        _sp[6] = GenArt.hash16(seed, 7, 3) % 256;          // tilt phase
        _sp[7] = (scl(4 + GenArt.hash16(seed, 8, 3) % 5) * s) / 100;
        for (var k = 0; k < _sp[2]; k++) {                 // per-lobe amp %
            _lamp[k] = 40 + GenArt.hash16(seed, 16 + k, 5) % 131;
        }
        var ntuft = act / TUFT_DIV;
        if (ntuft > 7) { ntuft = 7; }
        var tsize = 10 + act / 240;            // larger activity clusters
        if (tsize > 23) { tsize = 23; }
        tsize = scl(tsize);

        // per-frame outline LUT + outer-fan vertex offsets: edge() costs ~3
        // isin + per-lobe arithmetic per call and used to be re-evaluated
        // ~240x a frame (both fans, every texture dot, the fringe, tufts,
        // beads) -- the per-element method cost the sandbox proxy
        // under-counts (docs/watchdog-debugging.md); the saturated release
        // frame tripped the sim watchdog. Sample the outline ONCE at the NA
        // rim angles; everything else reads the LUT (nearest sample -- the
        // outline is smooth, off-grid consumers only see px-level shifts).
        for (var i = 0; i < NA; i++) {
            var ai = ((i * 256) / NA) % 256;
            var er0 = edge(base, ai);
            _er[i] = er0;
            _evx[i] = (er0 * GenArt.isin(ai + 64)) / 127;
            _evy[i] = (er0 * GenArt.isin(ai)) / 127;
        }

        // central cushion: dark mound + bright green crown
        dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
        fanLut(dc, 100);
        dc.setColor(Gfx.COLOR_GREEN, Gfx.COLOR_TRANSPARENT);
        fanLut(dc, 60);

        // satellite tufts straddling the rim
        var nt = (ntuft > 0) ? ntuft : 1;
        for (var j = 0; j < ntuft; j++) {
            if (_ink <= 0) { break; }
            var hj = GenArt.hash16(seed, j, 31);
            var a = ((j * 256) / nt + (hj & 31)) % 256;
            var rr = (_er[(a * NA) / 256] * (85 + (hj >> 8) % 30)) / 100;
            drawTuft(dc, seed, j, coordX(a, rr), coordY(a, rr), tsize, dzcol);
        }

        // granular texture over the cushion
        // cap 130 -> 90 (watchdog): with the bigger late-day crown the extra
        // 40 dots added op count, not visible density
        var n = 50 + act / 12;
        if (n > 90) { n = 90; }
        for (var i = 0; i < n; i++) {
            if (_ink <= 0) { break; }
            var h = GenArt.hash16(seed, i, 1);
            var aa = h & 0xFF;
            var r0 = (base > 0) ? ((h >> 8) % base) : 0;
            r0 = (base > 0) ? (r0 * r0) / base : 0;
            var lim = _er[(aa * NA) / 256];
            var rt = (base > 0) ? (r0 * lim) / base : 0;
            var col;
            if ((h & 1) == 0) { col = Gfx.COLOR_DK_GREEN; }
            else { col = (((h >> 6) & 7) == 0) ? Gfx.COLOR_YELLOW : Gfx.COLOR_GREEN; }
            dc.setColor(col, Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(coordX(aa, rt), coordY(aa, rt), 1);
            _ink -= 1;
        }

        // fuzzy rim fringe
        dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
        for (var i = 0; i < NA; i += 2) {
            if (_ink <= 0) { break; }
            var a = ((i * 256) / NA) & 255;
            var e = _er[i];
            var le = 2 + (GenArt.hash16(seed, i, 9) & 1);
            dc.drawLine(CX + _evx[i], CY + _evy[i],
                        coordX(a, e + le), coordY(a, e + le));
            _ink -= 1;
        }

        // episodes: contiguous fruiting beads (owner, 2026-07). Three rules
        // keep every bead ON the moss without covering the root star (the
        // old blanket keep-out, rootLen + 20 + scl(6), floated beads into
        // black space all morning):
        //   keep-out  exact per bead -- inner edge clears the outermost root
        //             tip by 3, measured on the bead's own polar estimate;
        //   embed     an offset that overshoots the rim is pulled back until
        //             a third of the bead is buried (a tangent kiss on a fat
        //             bead reads detached);
        //   stalk     anything the star still forces out grows a straight
        //             tapered podetium from the moss (rim / its REAL tuft):
        //             flared holdfast, waist 40% up, cup at the bead's edge.
        // Angles walk a golden sequence (97 ~ 256/phi^2) from a per-day
        // phase, +-10 jitter, and tufts are dealt round-robin: any first k
        // beads stay near-uniformly spread (less overlap, owner 2026-07-14),
        // and a bead never moves when a new episode opens. Cheaper than the
        // hashed placement it replaced (one hash16 per bead dropped).
        var ph = seed & 255;
        var rl = (_sleepSeed > 0) ? rootLen(_sleepSeed) : 0;
        for (var e = 0; e < _nepi; e++) {
            if (_ink <= 0) { break; }
            var mag = _emag[e];
            // gentle slope + high cap so long/hard efforts spread out in size
            // while the floor stays put. Bead is a final px radius (already scaled).
            var bead = 4 + mag / 30;
            if (bead > 18) { bead = 18; }
            // the bead's inner edge must clear the outermost root tip by 3
            var need = (rl > 0) ? (rl + bead + 3) : 0;
            var stx = null; var sty = 0;    // stalk anchor when displaced
            var x; var y;
            if (ntuft > 0) {
                var t = e % ntuft;          // round-robin, not hash: even load
                var hj = GenArt.hash16(seed, t, 31);
                var ta = ((t * 256) / ntuft + (hj & 31)) % 256;
                var rim = _er[(ta * NA) / 256];
                var trr0 = (rim * (85 + (hj >> 8) % 30)) / 100;  // REAL tuft
                var he = GenArt.hash16(seed, e, 42);
                var off = tsize / 2 + (he >> 8) % 3;
                var a = (ph + e * 97 + (he % 21) - 10) & 255;  // golden + jitter
                // polar estimate of the bead centre: the tuft offset split
                // into a radial part (folded onto the radius) and a
                // tangential part (folded onto the ANGLE, 41 ~ 256/2pi) --
                // the rim the bead must touch is the rim at the bead's own
                // angle, not the tuft's (isin masks & 255, negatives fine).
                var dr = (off * GenArt.isin(a - ta + 64)) / 127;
                var tg = (off * GenArt.isin(a - ta)) / 127;
                var trr = trr0;
                var rad = trr + dr;
                if (rad < need) {           // star pushes it out
                    trr = need - dr;
                    rad = need;
                }
                var da = (rad > 0) ? ((tg * 41) / rad) : 0;
                if (da > 64) { da = 64; }   // tiny-rad guard: keep the angle
                if (da < -64) { da = -64; } // correction (and the LUT index) in range
                var ab = (ta + da + 256) % 256;
                var rimb = _er[(ab * NA) / 256];
                // required embed depth grows with the bead: a tangent kiss
                // on a fat bead reads detached (black shoulders around a
                // 1 px contact), so bury a third of it
                var emb = 3 + bead / 3;
                if (rad - bead > rimb - emb) {
                    var dt = (rad - bead) - (rimb - emb);  // overshot: pull in
                    if (dt > rad - need) { dt = rad - need; }  // as far as the
                    if (dt > 0) {                              // star allows
                        trr -= dt;
                        rad -= dt;
                    }
                    if (trr < 2) {          // tiny-rim corner: stay put
                        rad += 2 - trr;
                        trr = 2;
                    }
                }
                if (rad - bead > rimb - 2) {  // not solidly embedded: stalk
                    stx = coordX(ta, trr0);   // from the REAL tuft it rides
                    sty = coordY(ta, trr0);   // (the mound occludes the
                }                             // stalk's inner run)
                var tx = coordX(ta, trr);
                var ty = coordY(ta, trr);
                x = tx + (off * GenArt.isin(a + 64)) / 127;
                y = ty + (off * GenArt.isin(a)) / 127;
            } else {
                var he = GenArt.hash16(seed, e, 42);
                var a = (ph + e * 97 + (he % 21) - 10) & 255;  // golden + jitter
                var lim = _er[(a * NA) / 256];
                var rr = (lim * 3) / 5;
                if (rr < need) { rr = need; }
                if (rr - bead > lim - 2) {    // not solidly on the crown:
                    stx = coordX(a, lim - 2); // stalk anchored just inside
                    sty = coordY(a, lim - 2); // the rim, under the fringe
                }
                x = coordX(a, rr);
                y = coordY(a, rr);
            }
            if (stx != null) {
                // STRAIGHT tapered stalk (owner, 2026-07-14: no kink, push
                // the flare): a podetium with a visible cup. Wide holdfast
                // where it leaves the moss, waist 40% up, then a flare that
                // ends at the bead's EDGE -- ending at the bead centre hid
                // the tip flare under the dark ring. Two CONVEX trapezoids
                // (fillPolygon is only trusted convex); perpendicular
                // half-widths 5/1/4 from the true stalk direction; ln is the
                // octagonal length approximation (max + min/2), all integer.
                var dx = x - stx;
                var dy = y - sty;
                var adx = (dx >= 0) ? dx : -dx;
                var ady = (dy >= 0) ? dy : -dy;
                var ln = ((adx > ady) ? adx : ady)
                       + ((adx < ady) ? adx : ady) / 2;
                if (ln < 1) { ln = 1; }
                var pb = bead - 2;          // tuck the cup 2 px under the disc
                if (pb > ln - 3) { pb = ln - 3; }
                if (pb < 0) { pb = 0; }
                var ex = x - (dx * pb) / ln;   // cup lip, at the bead's edge
                var ey = y - (dy * pb) / ln;
                var wx = stx + ((ex - stx) * 2) / 5;  // waist 40% up the stalk
                var wy = sty + ((ey - sty) * 2) / 5;
                var bxw = rdiv(-dy * 5, ln);   // holdfast (half-width 5)
                var byw = rdiv(dx * 5, ln);
                var wxw = rdiv(-dy, ln);       // waist (half-width 1) --
                var wyw = rdiv(dx, ln);        // never let it pinch to zero
                if (wxw == 0 && wyw == 0) {
                    if (adx >= ady) { wyw = 1; } else { wxw = 1; }
                }
                var txw = rdiv(-dy * 4, ln);   // cup (half-width 4)
                var tyw = rdiv(dx * 4, ln);
                dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
                _quad[0][0] = stx - bxw;  _quad[0][1] = sty - byw;
                _quad[1][0] = stx + bxw;  _quad[1][1] = sty + byw;
                _quad[2][0] = wx + wxw;   _quad[2][1] = wy + wyw;
                _quad[3][0] = wx - wxw;   _quad[3][1] = wy - wyw;
                dc.fillPolygon(_quad);
                _quad[0][0] = wx - wxw;   _quad[0][1] = wy - wyw;
                _quad[1][0] = wx + wxw;   _quad[1][1] = wy + wyw;
                _quad[2][0] = ex + txw;   _quad[2][1] = ey + tyw;
                _quad[3][0] = ex - txw;   _quad[3][1] = ey - tyw;
                dc.fillPolygon(_quad);
                _ink -= 2;
            }
            dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(x, y, bead + 1);
            dc.setColor(zoneColor(_epz[e]), Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(x, y, bead);
            _ink -= 2;
        }

        // root star drawn LAST: stays on top of the colony all day
        drawSleep(dc, _sleepSeed, _wakeSeed);
    }

    function drawTuft(dc, seed, j, tx, ty, tsize, accent) {
        dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(tx, ty, tsize / 2);
        _ink -= 1;
        // grain cap 26 -> 16 (watchdog): 7 tufts x 26 grains was the single
        // heaviest layer at saturation (each grain = hash16 + 2 isin + 2 Dc
        // calls); 16 keeps the stipple read at ~2/3 the op count
        var grains = 8 + tsize / 2;
        if (grains > 16) { grains = 16; }
        for (var i = 0; i < grains; i++) {
            if (_ink <= 0) { break; }
            var h = GenArt.hash16(seed, j * 64 + i, 3);
            var a2 = h & 0xFF;
            var rr2 = (tsize > 0) ? ((h >> 8) % tsize) : 0;
            rr2 = (tsize > 0) ? (rr2 * rr2) / tsize : 0;
            var gx = tx + (rr2 * GenArt.isin(a2 + 64)) / 127;
            var gy = ty + (rr2 * GenArt.isin(a2)) / 127;
            var col = ((h & 1) != 0) ? Gfx.COLOR_GREEN : Gfx.COLOR_DK_GREEN;
            if (accent != -1 && ((h >> 6) & 3) != 0) { col = accent; }
            dc.setColor(col, Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(gx, gy, 1);
            _ink -= 1;
        }
    }

    // last night's sleep: the silver root star under the heart of the moss.
    // wakes = wake-up events 12-6am: each one snaps a root at a white speck
    // (the literal count), kinks every root harder, and grays the tips.
    // Lengths/radii are FINAL px (already scaled), like the episode beads.
    //
    // The star does NOT compete for the shared ink budget: a saturated day
    // spends all 340 ink on tufts/texture/beads and the clump this replaced
    // silently vanished by mid-afternoon -- but the night must stay readable
    // on the heaviest day (it is the layer drawn last precisely to stay on
    // top). Its cost is hard-capped instead: nroots <= 16 and wakes clamped
    // to nroots bound it at ~80 primitives.
    function drawSleep(dc, mins, wakes) {
        if (mins <= 0) { return; }
        var hours = rootHours(mins);
        var ln = rootLen(mins);
        var nroots = 6 + hours;
        if (wakes > nroots) { wakes = nroots; }  // can't snap more than exist
        var kink = 3 + wakes * 6;      // angle jitter at the joints (1/256ths)

        // each wake snaps one root (evenly spread, distinct while wakes <=
        // nroots); precomputed as a bitmask -- the per-root scan was
        // O(nroots*wakes) divisions for a value that never changes in-frame
        var snapmask = 0;
        for (var w = 0; w < wakes; w++) {
            snapmask = snapmask | (1 << ((w * nroots) / wakes));
        }

        // taproot crown grounding the star
        dc.setColor(Gfx.COLOR_DK_BLUE, Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(CX, CY, 3);

        for (var i = 0; i < nroots; i++) {
            var h = GenArt.hash16(87, i, 6);
            var a = ((i * 256) / nroots + (h % 15)) % 256;
            var li = ln - (h >> 8) % (ln / 3 + 1);     // per-root length variety
            // joint angles wander +-kink; negatives are fine (isin masks & 255)
            var a1 = a + GenArt.hash16(87, i, 7) % (2 * kink + 1) - kink;
            var a2 = a1 + GenArt.hash16(87, i, 8) % (2 * kink + 1) - kink;
            var rm = (li * 3) / 5;
            var x0 = coordX(a, 2);
            var y0 = coordY(a, 2);
            var xm = coordX(a1, rm);
            var ym = coordY(a1, rm);
            // a snapped root ends at its joint under the white speck
            var snapped = ((snapmask >> i) & 1) != 0;
            dc.setColor(snapped ? Gfx.COLOR_DK_GRAY : Gfx.COLOR_LT_GRAY,
                        Gfx.COLOR_TRANSPARENT);
            dc.drawLine(x0, y0, xm, ym);
            if (snapped) {
                // ship-style blight speck at the break: white core in a thick
                // black ring, a couple of ragged blobs on its edge
                dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
                dc.fillCircle(xm, ym, 5);
                for (var k = 0; k < 2; k++) {
                    var hb = GenArt.hash16(i + 41, k, 8);
                    var ba = (k * 256) / 2 + (hb % 40);
                    dc.fillCircle(xm + (6 * GenArt.isin(ba + 64)) / 127,
                                  ym + (6 * GenArt.isin(ba)) / 127, 1);
                }
                dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
                dc.fillCircle(xm, ym, 2);
            } else {
                var xt = coordX(a2, li);
                var yt = coordY(a2, li);
                dc.drawLine(xm, ym, xt, yt);
                // nodule tip: deep blue when rested, gray on a rough night
                dc.setColor((wakes == 0) ? Gfx.COLOR_BLUE : Gfx.COLOR_DK_GRAY,
                            Gfx.COLOR_TRANSPARENT);
                dc.fillCircle(xt, yt, 1);
            }
        }
    }

    // ---- persistence (compact flat Number array) -----------------------------
    // The record is tiny (a few scalars + zoneMin[9] + nepi episode pairs), so a
    // reload restores it exactly. Validated on load: a wrong magic or out-of-range
    // count drops to a blank record rather than half-loading.
    const SAVE_MAGIC = 0x6033F;  // bumped: wake fields added to the layout

    function save() {
        var n = 15 + 9 + _nepi * 2;
        var a = new [n];
        var p = 0;
        a[p] = SAVE_MAGIC; p++;
        a[p] = _lastDay; p++;
        a[p] = (_prev == null) ? -1 : _prev; p++;
        a[p] = _lastMin; p++;
        a[p] = _seed; p++;
        a[p] = _night; p++;
        a[p] = _sleepSeed; p++;
        a[p] = _wakes; p++;
        a[p] = _wakeSeed; p++;
        a[p] = _actUnits; p++;
        a[p] = _activeMin; p++;
        a[p] = _idleMin; p++;
        a[p] = _epiOn ? 1 : 0; p++;
        a[p] = _epiIdx; p++;
        a[p] = _nepi; p++;
        for (var i = 0; i < 9; i++) { a[p] = _zoneMin[i]; p++; }
        for (var i = 0; i < _nepi; i++) { a[p] = _epz[i]; p++; a[p] = _emag[i]; p++; }
        return a;
    }

    function load(a) {
        if (a == null || a.size() < 24 || a[0] != SAVE_MAGIC) { return; }
        var sz = a.size();
        var p = 1;
        _lastDay = a[p]; p++;
        var pv = a[p]; p++; _prev = (pv < 0) ? null : pv;
        _lastMin = a[p]; p++;
        _seed = a[p]; p++;
        _night = a[p]; p++;
        _sleepSeed = a[p]; p++;
        _wakes = a[p]; p++;
        _wakeSeed = a[p]; p++;
        _actUnits = a[p]; p++;
        _activeMin = a[p]; p++;
        _idleMin = a[p]; p++;
        _epiOn = (a[p] != 0); p++;
        _epiIdx = a[p]; p++;
        var ne = a[p]; p++;
        if (ne < 0 || ne > EMAX) { reset(); return; }
        for (var i = 0; i < 9; i++) {
            if (p >= sz) { reset(); return; }
            _zoneMin[i] = a[p]; p++;
        }
        if (p + ne * 2 > sz) { reset(); return; }
        _nepi = ne;
        for (var i = 0; i < _nepi; i++) {
            _epz[i] = a[p]; p++; _emag[i] = a[p]; p++;
        }
    }
}
