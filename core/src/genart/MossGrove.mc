using Toybox.Graphics as Gfx;

// MossGrove -- the two-worlds V2 biometric organism. Line-for-line port of
// sketches/algos/moss_grove.py (the parity reference); the day record is the
// port of sketches/daysoma.py and the cushion outline of sketches/mossutil.py.
//
// The day as a living patch of moss, time-of-day intentionally NOT encoded --
// only WHAT happened, accreted in RAM and persisted across a reload (MossState),
// since the device gives only the current HR sample and cumulative steps per
// tick. From the heart outward:
//   sleep nucleus  last night's inferred sleep (overnight quiescence, as in
//                  BioBloom): a spore clump at the centre, size = hours,
//                  colour = quality (cool rested / warm short). Drawn LAST so it
//                  stays on top of the day's growth all day.
//   cushion        a solid two-tone lumpy mound; radius grows with total
//                  movement; the lumpy OUTLINE varies per day from the date seed.
//   tufts          satellite colony clumps straddling the rim, popping in as
//                  activity accrues; grains glow the dominant ELEVATED HR zone.
//   texture        granular green stipple + a fuzzy rim fringe.
//   episodes       elevated-HR events as bright peak-zone fruiting beads.
//
// All integer math (the watchdog is the binding constraint). A per-frame INK
// budget caps draw work so a maximal day stays bounded; render measures ~12k VM
// instructions/frame in the sandbox (half the ~25k budget), state ~245 B.
class MossGrove {

    const CX = 107;
    const CY = 108;            // centre 2/5 of the screen height up from bottom
    const INK_MAX = 340;
    const NA = 30;             // rim samples for the cushion fans
    const BASE_DIV = 60;       // act units -> cushion radius
    const TUFT_DIV = 600;      // act units -> one more satellite tuft
    const SCN = 5;             // overall size scale = SCN/SCD (= 1.25x), applied
    const SCD = 4;             // to every radial extent

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
    // hours-slept ramp: cool = well rested, warm = short night (index hours-3).
    const SLEEP_RAMP = [
        Gfx.COLOR_DK_RED, Gfx.COLOR_RED, Gfx.COLOR_ORANGE, Gfx.COLOR_YELLOW,
        Gfx.COLOR_DK_GREEN, Gfx.COLOR_GREEN, Gfx.COLOR_BLUE, Gfx.COLOR_DK_BLUE
    ];

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
    var _sp;                   // per-day shape params [p1,p2,f1,f2,am1,am2]
    var _tri;                  // reusable triangle for fillPolygon
    var _ink;

    function initialize() {
        _zoneMin = new [9];
        _epz = new [EMAX];
        _emag = new [EMAX];
        _sp = new [6];
        _tri = [[0, 0], [0, 0], [0, 0]];
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

    function sleepSlot(mins) {
        var s = mins / 60 - 3;
        if (s < 0) { s = 0; }
        if (s > 7) { s = 7; }
        return s;
    }

    function coordX(a, r) { return CX + (r * GenArt.isin(a + 64)) / 127; }
    function coordY(a, r) { return CY + (r * GenArt.isin(a)) / 127; }

    // lumpy cushion radius at angle a (uses per-day _sp set in render)
    function edge(base, a) {
        return base + (_sp[4] * GenArt.isin((a * _sp[2] + _sp[0]) & 255)) / 127
                    + (_sp[5] * GenArt.isin((a * _sp[3] + _sp[1]) & 255)) / 127;
    }

    // fill a lumpy disc out to edge(base,a)*scalepct/100 as a fan of NA triangles
    function fan(dc, base, scalepct) {
        var e0 = (edge(base, 0) * scalepct) / 100;
        var x0 = coordX(0, e0);
        var y0 = coordY(0, e0);
        for (var i = 1; i <= NA; i++) {
            var a = ((i * 256) / NA) & 255;
            var e = (edge(base, a) * scalepct) / 100;
            var x1 = coordX(a, e);
            var y1 = coordY(a, e);
            _tri[0][0] = CX;  _tri[0][1] = CY;
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

        // per-day lumpy outline params (hoisted; edge() reads _sp)
        _sp[0] = GenArt.hash16(seed, 1, 3) % 256;
        _sp[1] = GenArt.hash16(seed, 2, 3) % 256;
        _sp[2] = 2 + GenArt.hash16(seed, 3, 3) % 3;
        _sp[3] = 4 + GenArt.hash16(seed, 4, 3) % 4;
        _sp[4] = scl(7 + GenArt.hash16(seed, 5, 3) % 7);   // amplitudes scale too
        _sp[5] = scl(3 + GenArt.hash16(seed, 6, 3) % 4);

        var dz = dominantZone(ACTIVE);
        if (dz < 0) { dz = dominantZone(0); }
        var dzcol = (dz >= 0) ? HR_RAMP[dz] : -1;
        var act = _actUnits;

        var base = 4 + act / BASE_DIV;
        if (base > 54) { base = 54; }
        base = scl(base);                       // 1.25x overall scale
        var ntuft = act / TUFT_DIV;
        if (ntuft > 7) { ntuft = 7; }
        var tsize = 10 + act / 240;            // larger activity clusters
        if (tsize > 23) { tsize = 23; }
        tsize = scl(tsize);

        // central cushion: dark mound + bright green crown
        dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
        fan(dc, base, 100);
        dc.setColor(Gfx.COLOR_GREEN, Gfx.COLOR_TRANSPARENT);
        fan(dc, base, 60);

        // satellite tufts straddling the rim
        var nt = (ntuft > 0) ? ntuft : 1;
        for (var j = 0; j < ntuft; j++) {
            if (_ink <= 0) { break; }
            var hj = GenArt.hash16(seed, j, 31);
            var a = ((j * 256) / nt + (hj & 31)) % 256;
            var rr = (edge(base, a) * (85 + (hj >> 8) % 30)) / 100;
            drawTuft(dc, seed, j, coordX(a, rr), coordY(a, rr), tsize, dzcol);
        }

        // granular texture over the cushion
        var n = 50 + act / 12;
        if (n > 130) { n = 130; }
        for (var i = 0; i < n; i++) {
            if (_ink <= 0) { break; }
            var h = GenArt.hash16(seed, i, 1);
            var aa = h & 0xFF;
            var r0 = (base > 0) ? ((h >> 8) % base) : 0;
            r0 = (base > 0) ? (r0 * r0) / base : 0;
            var lim = edge(base, aa);
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
            var e = edge(base, a);
            var le = 2 + (GenArt.hash16(seed, i, 9) & 1);
            dc.drawLine(coordX(a, e), coordY(a, e),
                        coordX(a, e + le), coordY(a, e + le));
            _ink -= 1;
        }

        // episodes: bright fruiting beads on tufts (else crown), kept out of the
        // centre so they don't overlap the sleep nucleus.
        var keepout = sporeReach(_sleepSeed, _wakeSeed) + scl(6);
        for (var e = 0; e < _nepi; e++) {
            if (_ink <= 0) { break; }
            var mag = _emag[e];
            // gentle slope + high cap so long/hard efforts spread out in size
            // while the floor stays put. Bead is a final px radius (already scaled).
            var bead = 4 + mag / 30;
            if (bead > 18) { bead = 18; }
            var x; var y;
            if (ntuft > 0) {
                var t = GenArt.hash16(seed, e, 41) % ntuft;
                var hj = GenArt.hash16(seed, t, 31);
                var ta = ((t * 256) / ntuft + (hj & 31)) % 256;
                var trr = (edge(base, ta) * (85 + (hj >> 8) % 30)) / 100;
                if (trr < keepout) { trr = keepout; }
                var tx = coordX(ta, trr);
                var ty = coordY(ta, trr);
                var he = GenArt.hash16(seed, e, 42);
                var off = tsize / 2 + (he >> 8) % 3;
                var a = he & 0xFF;
                x = tx + (off * GenArt.isin(a + 64)) / 127;
                y = ty + (off * GenArt.isin(a)) / 127;
            } else {
                var a = GenArt.hash16(seed, e, 42) % 256;
                var rr = (edge(base, a) * 3) / 5;
                if (rr < keepout) { rr = keepout; }
                x = coordX(a, rr);
                y = coordY(a, rr);
            }
            dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(x, y, bead + 1);
            dc.setColor(zoneColor(_epz[e]), Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(x, y, bead);
            _ink -= 2;
        }

        // sleep nucleus drawn LAST: stays on top of the colony all day
        drawSpore(dc, _sleepSeed, _wakeSeed);
    }

    function drawTuft(dc, seed, j, tx, ty, tsize, accent) {
        dc.setColor(Gfx.COLOR_DK_GREEN, Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(tx, ty, tsize / 2);
        _ink -= 1;
        var grains = 8 + tsize / 2;
        if (grains > 26) { grains = 26; }
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

    // scaled footprint radius of the sleep nucleus (shared by drawSpore and the
    // episode keep-out). -25% overall vs the node spread so it takes up less room
    // while the node dots keep their size.
    function sporeReach(mins, wakes) {
        if (mins <= 0) { return 0; }
        var hours = mins / 60;
        var reach = 6 + 2 * hours;
        if (reach > 28) { reach = 28; }
        reach += 3 * wakes;                           // restless -> wider, looser
        if (reach > 40) { reach = 40; }
        return (scl(reach) * 3) / 4;                  // -25% overall footprint
    }

    // last night's sleep: a spore clump at the centre. wakes = wake-ups 12-6am:
    // each warms the clump a step, loosens its scatter, and adds one white
    // "blight" speck (thick black border, ragged outer edge) orbiting outside.
    function drawSpore(dc, mins, wakes) {
        if (mins <= 0) { return; }
        var hours = mins / 60;
        var slot = sleepSlot(mins) - wakes;          // restless -> warmer
        if (slot < 0) { slot = 0; }
        var reach = sporeReach(mins, wakes);
        var rim = (reach * 2) / 3;
        dc.setColor(SLEEP_RAMP[slot], Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(CX, CY, scl(3));
        var nodes = 7 + hours * 2;
        for (var k = 0; k < nodes; k++) {
            if (_ink <= 0) { break; }
            var h = GenArt.hash16(91, k, 6);
            var a = ((k * 256) / nodes + (h % 36)) % 256;
            var r1 = GenArt.hash16(73, k, 2) % reach;
            var r2 = GenArt.hash16(29, k, 4) % reach;
            var inner = (r1 < r2) ? r1 : r2;
            // more wakes -> less centre-bias (looser): blend min toward the mean
            var rr = 2 + ((wakes == 0) ? inner : (inner + r1 + r2) / 3);
            var ci = slot;
            if (rr >= rim && slot >= 1) { ci = slot - 1; }
            dc.setColor(SLEEP_RAMP[ci], Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(coordX(a, rr), coordY(a, rr), 1 + (h % 3));
            _ink -= 1;
        }
        // one "blight" speck per wake-up, orbiting just outside the clump: a
        // white dot in a THICK black border whose outer edge is roughened by
        // 1-5 half-size blobs sitting tangent on it (disrupted growth).
        if (wakes > 0) {
            var wr = scl(2);
            var br = wr + scl(3);
            var bd = br + scl(1);
            for (var w = 0; w < wakes; w++) {
                if (_ink <= 0) { break; }
                var hw = GenArt.hash16(53, w, 7);
                var wa = ((w * 256) / wakes + (hw % 24)) % 256;
                var wrr = reach + scl(4) + (hw % 4);
                var x = coordX(wa, wrr);
                var y = coordY(wa, wrr);
                dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
                dc.fillCircle(x, y, br);
                var nb = 1 + (GenArt.hash16(w, 5, 9) % 5);
                for (var k2 = 0; k2 < nb; k2++) {
                    var hb = GenArt.hash16(w + 41, k2, 8);
                    var ba = ((k2 * 256) / nb + (hb % 40)) % 256;
                    dc.fillCircle(x + (bd * GenArt.isin(ba + 64)) / 127,
                                  y + (bd * GenArt.isin(ba)) / 127, scl(1));
                }
                dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
                dc.fillCircle(x, y, wr);
                _ink -= (nb + 2);
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
