using Toybox.Graphics as Gfx;

// BioBloom — the day as a living dish (ported from sketches/algos/biobloom.py,
// the approved sandbox keeper; that file is the parity reference). The morning
// sleep-seed colony + skeleton tint are ported from sketches/algos/
// biobloom_morning.py (the parity reference for that feature).
//
// A filament skeleton grows from the centre, extending ONLY when you move, so a
// lazy day stays small and an active day reaches outward. A central MAIN COLONY
// fills in behind the arms (clinging to them, stippled — not concentric), grows
// only while moving, and is banded by the HR zone during that movement, going
// grey/dark grey when it grows while the inactivity meter is up. Every elevated-
// HR episode (zone >= ACTIVE) erupts a BLOOM on an arm: it grows one zone-
// coloured band per minute while HR stays up, and banks a movement-effort
// reservoir that keeps it creeping after HR drops — so an exercise event grows
// large while an anxiety spike (HR up, no movement) stays a small node.
//
// State is flat Number arrays, PACKED to fit the memory budget: each thread
// vertex is one Number (colorIdx<<16 | x<<8 | y), each band one Number
// (colorIdx<<8 | rEnd). Colour index 0..8 maps to HR_RAMP (a biobloom-local
// 9-step HR ramp, finer than the shared GenArt.ZONE_COLORS, so the other faces
// are untouched); 9 == DK_GRAY (idle / unknown HR), 10 == LT_GRAY (colony idle
// bands only). Evolution is incremental — advance()
// simulates only the minutes since the last tick (capped) — and resets the dish
// at midnight. All integer math (the watchdog is the binding constraint).
//
// Render: the skeleton draws as lines, each bloom as a small fan of bowed spines
// (recomputed each frame from the bloom's salt — cheap, no per-spine state)
// fired outward and coloured by the HR zone at the tip, the colony as a short
// spine "fur" stippled along the arms. A per-frame ink budget (INK_MAX) caps the
// spine work so a large dish can never outrun the watchdog — the per-dot stipple
// did.
class BioBloom {

    const CX = 107;
    const CY = 108;            // centre at 2/5 of the screen height up from bottom
    const R0 = 7;
    const RMAX = 86;
    const UNIT = 64;
    const KACT = 6;            // movement -> growth (smaller => faster threads)
    const STEP = 2;            // px of radius per appended vertex
    const KMAX = 20;           // cap on live filaments (trimmed 22->20 for RAM:
                               // shrinks the dish AND the save() transient peak)
    const SEEDS = 9;           // initial threads, spread around the centre
    const PMAX = 41;           // vertices per thread (R0..RMAX by STEP; max ~40)

    const ACTIVE = 4;          // zone idx >= this is an elevated-HR minute (HR>=105)
    const BASE = 2;            // px a bloom starts out from its anchor
    const GROW = 2;            // px the bloom frontier advances per minute
    const REACH_CAP = 46;      // px a bloom can reach along its arm
    const MOM_DIV = 16;        // steps/min -> momentum reservoir units
    const MOM_STEP = 2;        // px of momentum growth per minute after HR drops
    const BMAX = 16;           // cap on blooms
    const BBANDS = 24;         // cap on bands per bloom (reach 2..46 by 2 => ~22)

    const CR_MAX = 78;         // main-colony reach ceiling (px from centre)
    const TRAIL = 10;          // px the colony trails behind the longest arm
    const CMOVE_DIV = 20;      // steps/min -> colony reach growth (px)
    const CW = 3;              // colony thickness scattered around each arm
    const MOVE_MIN = 2;        // steps/min below which the colony does not grow
    const IDLE_STEPS = 1;      // spm <= this is an idle minute (move-bar fills)
    const BAR_MAX = 60;        // inactivity meter ceiling (~minutes)
    const BAR_ON = 40;         // meter >= this is "on" -> growth bands go grey
    const BAR_HI = 50;         // deeper inactivity -> dark grey vs light grey
    const BAR_CLEAR = 4;       // solid movement works the meter down per minute
    const CBANDS = 80;         // cap on colony bands (reach R0..78 => ~71)
    const DKGREY = 9;          // colour index for COLOR_DK_GRAY (idle / unknown HR)
    const LTGREY = 10;         // colour index for COLOR_LT_GRAY (colony idle)
    const INK_MAX = 700;       // total primitives per onUpdate (watchdog backstop)
    const SK_CAP = 520;        // decimate the skeleton above this many segments

    // ---- last night's sleep -> a morning seed colony --------------------------
    // The dish resets at midnight and used to wake up EMPTY (blank centre). It
    // now wakes seeded by last night's sleep: a small "spore" colony at the
    // centre whose size + colour encode hours slept.
    //
    // There is NO sleep API at CIQ 2.4, so sleep is INFERRED as overnight
    // quiescence: a rest meter (_nightAcc) ticks up each night-hour minute with
    // no step advance and a resting HR. It is NOT cleared by the midnight reset --
    // at the day rollover its running total is handed to _sleepSeed (the value the
    // morning colony is drawn from) and it keeps accruing through the early-morning
    // sleep, so by the time you glance at the watch the seed is the whole night.
    // The first solid movement of the morning freezes the seed and clears the
    // meter for the next night. Both survive a watch-face reload via BioState.
    const REST_HR = 72;        // HR at/below this counts as resting (sleep proxy)
    const NIGHT_START = 20;    // hour >= this OR <= NIGHT_END is "night" for resting
    const NIGHT_END = 10;
    const MORNING_END = 11;    // up to this hour the seed still tracks the night
    const WAKE_START = 5;      // earliest hour a "got up" movement clears the meter
    const SLEEP_CAP = 600;     // cap the rest meter (~10 h)
    const SEED_R0 = 6;         // seed-colony core radius at the shortest night
    const SEED_PER_H = 2;      // +px of seed reach per hour slept
    const SEED_RMAX = 30;      // the morning bud stays "small" -- never exceeds this

    // Sleep ramp: cool = well rested, warm = short night. Indexed by (hours - 3),
    // clamped 0..7 (i.e. <=3 h .. >=10 h). The spore clump reads deepest-rest at
    // its centre and cools one step toward the rim.
    const SLEEP_RAMP = [
        Gfx.COLOR_DK_RED, Gfx.COLOR_RED, Gfx.COLOR_ORANGE, Gfx.COLOR_YELLOW,
        Gfx.COLOR_DK_GREEN, Gfx.COLOR_GREEN, Gfx.COLOR_BLUE, Gfx.COLOR_DK_BLUE
    ];

    // Biobloom-local 9-step HR ramp (finer than GenArt's shared 7-step ramp, so
    // strata/flock keep theirs). Cool -> hot: blue family at rest, green for
    // easy, a warm yellow->orange->red run, pink/purple reserved for genuine max
    // efforts (HR >= 152 / 165). hrZone(null) == -1 (never elevated; drawn grey).
    const HR_BOUNDS = [60, 80, 95, 105, 120, 138, 152, 165];
    const HR_RAMP = [
        Gfx.COLOR_DK_BLUE, Gfx.COLOR_BLUE, Gfx.COLOR_DK_GREEN, Gfx.COLOR_GREEN,
        Gfx.COLOR_YELLOW, Gfx.COLOR_ORANGE, Gfx.COLOR_RED, Gfx.COLOR_PINK,
        Gfx.COLOR_PURPLE
    ];

    // threads
    var _tha; var _thL; var _thv; var _thnext; var _thnp; var _nfil;
    var _pt;                   // packed vertices: colorIdx<<16 | x<<8 | y
    // blooms
    var _blbx; var _blby; var _blang; var _blw; var _blsalt; var _blreach;
    var _blmom; var _blnb; var _blband; var _nbloom;   // _blband: ci<<8 | rEnd
    var _blmom0; var _bllastzi;        // cooldown tail: reservoir & zone at HR-drop
    // colony
    var _colreach; var _coln; var _colband;            // _colband: ci<<8 | rEnd
    // episode / inactivity
    var _epiOn; var _epiIdx; var _bar;
    // HR window (last 10 samples, ring)
    var _win; var _winN; var _winHead;
    // lifecycle
    var _lastMin; var _lastSteps; var _lastDay;
    // sleep inference (persist across the midnight reset and across reloads)
    var _nightAcc;             // live overnight rest meter (minutes)
    var _sleepSeed;            // frozen "last night's sleep" the morning seed reads
    var _bloomBase;
    var _ord;                  // scratch index array for _longish
    var _ink;                  // per-frame draw budget (counts down in render)
    // Per-frame radius->colour lookup tables (allocated ONCE in initialize,
    // refilled each render). They turn the band-colour query from an O(bands)
    // scan -- which grew all day toward the band caps and tripped the watchdog
    // late in a long day -- into an O(1) array read, so render cost no longer
    // grows with how many bands the dish has accreted.
    var _colLut;               // radius 0..CR_MAX     -> colony colour
    var _blLut;                // radius 0..REACH_CAP   -> current bloom colour

    function initialize() {
        _tha = new [KMAX]; _thL = new [KMAX]; _thv = new [KMAX];
        _thnext = new [KMAX]; _thnp = new [KMAX];
        _pt = new [KMAX * PMAX];
        _blbx = new [BMAX]; _blby = new [BMAX]; _blang = new [BMAX];
        _blw = new [BMAX]; _blsalt = new [BMAX]; _blreach = new [BMAX];
        _blmom = new [BMAX]; _blnb = new [BMAX];
        _blmom0 = new [BMAX]; _bllastzi = new [BMAX];
        _blband = new [BMAX * BBANDS];
        _colband = new [CBANDS];
        _win = new [10];
        _ord = new [KMAX];
        _colLut = new [CR_MAX + 1];
        _blLut = new [REACH_CAP + 1];
        _bloomBase = GenArt.hash16(SEEDS, 17, 3) % 256;
        // Sleep meters live ACROSS the midnight reset, so they are initialised
        // here (once) and deliberately left untouched by reset().
        _nightAcc = 0; _sleepSeed = 0;
        reset();
    }

    function reset() {
        _nfil = 0;
        for (var i = 0; i < SEEDS; i++) {
            var a = ((i * 256) / SEEDS + (GenArt.hash16(91, i, 5) % 16)) % 256;
            var v = 2 + (GenArt.hash16(7, i, 1) % 3);
            _tha[i] = a; _thL[i] = R0 * UNIT; _thnext[i] = R0 + STEP;
            _thv[i] = v; _thnp[i] = 1;
            _pt[i * PMAX] = packPt(coordX(a, R0), coordY(a, R0), 7); // DK_GRAY
            _nfil++;
        }
        _nbloom = 0;
        _colreach = R0; _coln = 0;
        _epiOn = false; _epiIdx = -1; _bar = 0;
        _winN = 0; _winHead = 0;
        _lastSteps = null;
        _lastMin = -1; _lastDay = -1;
    }

    function coordX(a, r) { return CX + (r * GenArt.isin(a + 64)) / 127; }
    function coordY(a, r) { return CY + (r * GenArt.isin(a)) / 127; }

    function packPt(x, y, ci) { return (ci << 16) | ((x & 0xFF) << 8) | (y & 0xFF); }
    function upx(v) { return (v >> 8) & 0xFF; }
    function upy(v) { return v & 0xFF; }
    function upci(v) { return (v >> 16) & 0xFF; }
    function colorOf(ci) {
        if (ci == DKGREY) { return Gfx.COLOR_DK_GRAY; }
        if (ci == LTGREY) { return Gfx.COLOR_LT_GRAY; }
        return HR_RAMP[ci];
    }

    // hours-slept ramp slot (0..7) for a rest-meter value in minutes.
    function sleepSlot(mins) {
        var si = mins / 60 - 3;
        if (si < 0) { si = 0; }
        if (si > 7) { si = 7; }
        return si;
    }

    // HR bpm -> biobloom zone index 0..8, or -1 if HR is unknown.
    function hrZone(hr) {
        if (hr == null) { return -1; }
        for (var i = 0; i < 8; i++) {
            if (hr < HR_BOUNDS[i]) { return i; }
        }
        return 8;
    }

    // ---- per-minute simulation ------------------------------------------------

    function advance(state) {
        if (state.hour == null || state.minute == null) { return; }
        var now = state.hour * 60 + state.minute;
        var day = (state.day != null) ? state.day : 0;
        if (day != _lastDay) {
            // Hand the overnight rest meter to the new day's morning seed BEFORE
            // wiping the dish (reset() leaves the sleep meters alone), so last
            // night carries across midnight and keeps accruing till you wake.
            _sleepSeed = _nightAcc;
            reset();                 // genuine new calendar day -> fresh dish
            _lastDay = day;
            _lastMin = now - 1;
        } else if (now < _lastMin) {
            // Same day but the clock stepped backward (sync correction / manual
            // set). Don't wipe the day's dish -- just resync to the new time and
            // rebase the step baseline so growth resumes without a spike.
            _lastMin = now;
            if (state.steps != null) { _lastSteps = state.steps; }
            return;
        }
        var d = now - _lastMin;
        if (d <= 0) { return; }

        var steps = state.steps;
        var sd = 0;
        if (steps != null && _lastSteps != null && steps > _lastSteps) {
            sd = steps - _lastSteps;
        }
        var spm = sd / d;
        var nowSteps = (steps != null) ? steps : 0;

        var hr = state.heartRate;
        var zi = hrZone(hr);
        pushWin((hr != null) ? hr : 0);
        var vrange = winRange();
        var rising = winRising();

        // ---- last night's sleep (overnight quiescence) ----
        var hh = state.hour;
        var quiescent = (spm <= IDLE_STEPS) && (hr == null || hr <= REST_HR);
        var isNight = (hh >= NIGHT_START || hh <= NIGHT_END);
        if (isNight && quiescent && _nightAcc < SLEEP_CAP) {
            _nightAcc += d;
            if (_nightAcc > SLEEP_CAP) { _nightAcc = SLEEP_CAP; }
        }
        // In the morning the seed tracks the night so far (monotonic up, so a
        // brief stir doesn't shrink it); the first solid movement freezes it and
        // clears the meter for the coming night.
        if (hh <= MORNING_END && _nightAcc > _sleepSeed) { _sleepSeed = _nightAcc; }
        if (spm >= KACT && hh >= WAKE_START && hh <= MORNING_END && _nightAcc > 0) {
            _nightAcc = 0;
        }

        var iters = (d > 12) ? 12 : d;
        for (var k = 0; k < iters; k++) {
            stepMinute(spm, zi, vrange, rising, nowSteps);
        }
        _lastMin = now;
        if (steps != null) { _lastSteps = steps; }
    }

    function stepMinute(spm, zi, vrange, rising, salt) {
        var move = spm / KACT;
        var cidx = (spm <= 1 || zi < 0) ? DKGREY : zi;   // grey when idle / HR unknown

        if (move > 0) {
            var nf = _nfil;
            for (var i = 0; i < nf; i++) { growFil(i, move, vrange, cidx); }
            if (rising && _nfil < KMAX) {
                var src = longish(salt);
                var na = (_tha[src] + 10
                         + (GenArt.hash16(salt, nf, 9) % 22)) % 256;
                var rr = _thL[src] / UNIT;
                var v = 2 + (GenArt.hash16(salt, nf, 4) % 3);
                var j = _nfil;
                _tha[j] = na; _thL[j] = rr * UNIT; _thnext[j] = rr + STEP;
                _thv[j] = v; _thnp[j] = 1;
                _pt[j * PMAX] = packPt(coordX(na, rr), coordY(na, rr), cidx);
                _nfil++;
            }
        }

        var fed = -1;
        if (zi >= ACTIVE) {
            if (!_epiOn) { _epiOn = true; _epiIdx = seedBloom(zi); }
            if (_epiIdx >= 0) {
                var w = 3 + vrange / 8;
                if (w > 16) { w = 16; }
                if (w > _blw[_epiIdx]) { _blw[_epiIdx] = w; }
                bandBloom(_epiIdx, zi, GROW);    // bloom colour = HR zone index
                _bllastzi[_epiIdx] = zi;         // cooldown tail starts from here
                _blmom[_epiIdx] += spm / MOM_DIV;
                if (_blmom[_epiIdx] > REACH_CAP) { _blmom[_epiIdx] = REACH_CAP; }
                _blmom0[_epiIdx] = _blmom[_epiIdx];   // reservoir at HR-drop
                fed = _epiIdx;
            }
        } else {
            _epiOn = false; _epiIdx = -1;
        }

        momentum(fed);
        growColony(spm, zi);
    }

    function growFil(i, move, vrange, cidx) {
        _thL[i] += (move * _thv[i]) / 3;
        if (_thL[i] > RMAX * UNIT) { _thL[i] = RMAX * UNIT; }
        var amp = 1 + vrange / 10;
        while (_thL[i] / UNIT >= _thnext[i] && _thnext[i] <= RMAX) {
            var rr = _thnext[i];
            var da = (GenArt.isin(GenArt.hash16(_tha[i], rr, 1) & 255) * amp) / 127;
            _tha[i] = (_tha[i] + da) % 256;
            if (_thnp[i] < PMAX) {
                _pt[i * PMAX + _thnp[i]] =
                    packPt(coordX(_tha[i], rr), coordY(_tha[i], rr), cidx);
                _thnp[i] += 1;
            }
            _thnext[i] += STEP;
        }
    }

    function seedBloom(zi) {
        if (_nbloom >= BMAX) { return -1; }
        var target = (_bloomBase + _nbloom * 98
                     + (GenArt.hash16(zi, _nbloom, 7) % 22)) % 256;
        var src = nearest(target);
        var v = _pt[src * PMAX + (_thnp[src] - 1)];
        var bx = upx(v); var by = upy(v);
        var j = _nbloom;
        _blbx[j] = bx; _blby[j] = by; _blang[j] = _tha[src];
        _blreach[j] = BASE; _blw[j] = 3; _blnb[j] = 0; _blmom[j] = 0;
        _blmom0[j] = 0; _bllastzi[j] = zi;
        _blsalt[j] = GenArt.hash16(bx, by, zi) % 4096;
        _nbloom++;
        return j;
    }

    function bandBloom(bi, cidx, grow) {
        var r0 = _blreach[bi];
        var r1 = r0 + grow;
        if (r1 > REACH_CAP) { r1 = REACH_CAP; }
        if (r1 <= r0) { return; }
        var n = _blnb[bi];
        var base = bi * BBANDS;
        if (n < BBANDS) {
            _blband[base + n] = (cidx << 8) | r1; _blnb[bi] = n + 1;
        } else {
            _blband[base + n - 1] = (_blband[base + n - 1] & 0xFF00) | r1;
        }
        _blreach[bi] = r1;
    }

    function momentum(fed) {
        for (var i = 0; i < _nbloom; i++) {
            if (i != fed && _blmom[i] > 0 && _blreach[i] < REACH_CAP
                && _blnb[i] > 0) {
                var g = MOM_STEP;
                if (g > _blmom[i]) { g = _blmom[i]; }
                bandBloom(i, momColor(i), g);
                _blmom[i] -= g;
            }
        }
    }

    // Cooldown tail: start at the last HR zone and cool back DOWN the ramp
    // toward resting (idx 0) in proportion to how much reservoir is left, so the
    // recovery reads as a colour gradient regardless of the tail's length.
    function momColor(i) {
        var m0 = _blmom0[i];
        var lz = _bllastzi[i];
        if (m0 <= 0) { return lz; }
        var ci = (lz * _blmom[i]) / m0;
        if (ci < 0) { ci = 0; }
        if (ci > lz) { ci = lz; }
        return ci;
    }

    function growColony(spm, zi) {
        if (spm <= IDLE_STEPS) {
            _bar += 1;
            if (_bar > BAR_MAX) { _bar = BAR_MAX; }
        } else if (spm >= KACT) {
            _bar -= BAR_CLEAR;
            if (_bar < 0) { _bar = 0; }
        }
        if (spm < MOVE_MIN) { return; }
        var front = 0;
        for (var i = 0; i < _nfil; i++) {
            var l = _thL[i] / UNIT;
            if (l > front) { front = l; }
        }
        front -= TRAIL;
        var target = _colreach + spm / CMOVE_DIV;
        if (target > front) { target = front; }
        if (target > CR_MAX) { target = CR_MAX; }
        if (target <= _colreach) { return; }
        var cidx;
        if (_bar >= BAR_ON) {
            cidx = (_bar >= BAR_HI) ? DKGREY : LTGREY;
        } else {
            cidx = (zi < 0) ? DKGREY : zi;          // grey when HR unknown
        }
        if (_coln < CBANDS) {
            _colband[_coln] = (cidx << 8) | target; _coln += 1;
        } else {
            _colband[_coln - 1] = (_colband[_coln - 1] & 0xFF00) | target;
        }
        _colreach = target;
    }

    // pick one of the longer arms (varied) — for bloom branching
    function longish(salt) {
        var n = _nfil;
        for (var a = 0; a < n; a++) { _ord[a] = a; }
        for (var a = 1; a < n; a++) {
            var key = _ord[a]; var lv = _thL[key]; var b = a - 1;
            while (b >= 0 && _thL[_ord[b]] < lv) { _ord[b + 1] = _ord[b]; b -= 1; }
            _ord[b + 1] = key;
        }
        var half = n / 2;
        if (half < 1) { half = 1; }
        var k = GenArt.hash16(salt, _nbloom + 1, 13) % half;
        return _ord[k];
    }

    // arm whose heading is closest to target, so blooms fan out around the dish
    function nearest(target) {
        var best = 0; var bd = 999;
        for (var i = 0; i < _nfil; i++) {
            var d = ((_tha[i] - target + 128) % 256) - 128;
            if (d < 0) { d = -d; }
            if (d < bd) { bd = d; best = i; }
        }
        return best;
    }

    // ---- HR window ------------------------------------------------------------

    function pushWin(v) {
        if (_winN < 10) {
            _win[(_winHead + _winN) % 10] = v; _winN += 1;
        } else {
            _win[_winHead] = v; _winHead = (_winHead + 1) % 10;
        }
    }
    function winRange() {
        if (_winN == 0) { return 0; }
        var lo = _win[_winHead]; var hi = lo;
        for (var i = 0; i < _winN; i++) {
            var v = _win[(_winHead + i) % 10];
            if (v < lo) { lo = v; }
            if (v > hi) { hi = v; }
        }
        return hi - lo;
    }
    function winRising() {
        if (_winN < 6) { return false; }
        var oldest = _win[_winHead];
        var latest = _win[(_winHead + _winN - 1) % 10];
        return (latest - oldest) >= 8;
    }

    // ---- render ---------------------------------------------------------------

    // Priority order under one shared budget: structure (skeleton) first, then
    // the HR-zone blooms, then the decorative fur (shed first under load). Every
    // pass decrements _ink so a single onUpdate stays bounded no matter how big
    // the dish has grown -- the watchdog is the binding constraint.
    function render(dc, state) {
        _ink = INK_MAX;
        drawSeed(dc);                        // last night's sleep colony (under)
        drawSkeleton(dc);                    // skeleton arms (structural)
        for (var bi = 0; bi < _nbloom; bi++) {   // HR-zone blooms (priority)
            if (_ink <= 0) { break; }
            drawBloom(dc, bi);
        }
        drawFur(dc);                         // colony fur (detail; shed first)
    }

    // Draw every arm, but DECIMATE (draw every `stride`-th vertex) once the
    // skeleton is abnormally large, so a 22-arm dish on a very active day can't
    // outrun the budget drawing one line per vertex. The arm tip is always drawn
    // so each arm still reaches its true length; only the wiggle gets coarser.
    function drawSkeleton(dc) {
        var tot = 0;
        for (var i = 0; i < _nfil; i++) {
            var np = _thnp[i];
            if (np > 1) { tot += np - 1; }
        }
        var stride = 1;
        if (tot > SK_CAP) { stride = tot / SK_CAP + 1; }
        for (var i = 0; i < _nfil; i++) {
            var np = _thnp[i];
            if (np < 2) { continue; }
            var base = i * PMAX;
            var prev = 0;
            var k = stride;
            while (k < np) {
                if (_ink <= 0) { return; }
                var a = _pt[base + prev]; var b = _pt[base + k];
                dc.setColor(colorOf(upci(b)), Gfx.COLOR_TRANSPARENT);
                dc.drawLine(upx(a), upy(a), upx(b), upy(b));
                _ink -= 1;
                prev = k;
                k += stride;
            }
            if (prev != np - 1) {            // always close to the arm tip
                if (_ink <= 0) { return; }
                var a = _pt[base + prev]; var b = _pt[base + np - 1];
                dc.setColor(colorOf(upci(b)), Gfx.COLOR_TRANSPARENT);
                dc.drawLine(upx(a), upy(a), upx(b), upy(b));
                _ink -= 1;
            }
        }
    }

    // Last night's sleep, drawn UNDER the live dish so the day's growth overgrows
    // it. A small "spore" colony: a dense clump of cells packed around the centre,
    // more of them the longer the night, deepest-rest colour in the middle and
    // cooling one ramp step toward the rim. Radius is weighted INWARD (min of two
    // hashes) so it reads as a colony blob, not a sparse sprinkle. Fixed, cheap
    // cost -- no per-day accretion -- and skipped entirely with no sleep data.
    function drawSeed(dc) {
        if (_sleepSeed <= 0) { return; }
        var sh = _sleepSeed / 60;
        var si = sleepSlot(_sleepSeed);
        var reach = SEED_R0 + SEED_PER_H * sh;
        if (reach > SEED_RMAX) { reach = SEED_RMAX; }
        var rim = (reach * 2) / 3;
        dc.setColor(SLEEP_RAMP[si], Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(CX, CY, 3);                    // anchor core
        var nodes = 7 + sh * 3;
        for (var k = 0; k < nodes; k++) {
            if (_ink <= 0) { return; }
            var a = ((k * 256) / nodes + (GenArt.hash16(91, k, 6) % 36)) % 256;
            var r1 = GenArt.hash16(73, k, 2) % reach;
            var r2 = GenArt.hash16(29, k, 4) % reach;
            var rr = 2 + ((r1 < r2) ? r1 : r2);      // bias toward the centre
            var x = CX + (rr * GenArt.isin(a + 64)) / 127;
            var y = CY + (rr * GenArt.isin(a)) / 127;
            var ci = si;
            if (rr >= rim && si >= 1) { ci = si - 1; }
            dc.setColor(SLEEP_RAMP[ci], Gfx.COLOR_TRANSPARENT);
            dc.fillCircle(x, y, 1 + (GenArt.hash16(7, k, 3) % 3));
            _ink -= 1;
        }
    }

    // A short outward "fur" of zone-coloured spines along the arms, out to where
    // the colony has filled. Drawn last so the ink budget sheds fur before blooms.
    function drawFur(dc) {
        if (_coln == 0) { return; }
        fillColLut();                        // O(1) colour lookups in the loop
        var reach = _colreach;
        for (var i = 0; i < _nfil; i++) {
            var lim = _thL[i] / UNIT - TRAIL;
            if (lim > reach) { lim = reach; }
            if (lim <= R0) { continue; }
            var np = _thnp[i];
            var base = i * PMAX;
            var a = _tha[i];
            for (var k = 2; k < np; k++) {
                if (_ink <= 0) { return; }
                var rr = R0 + k * STEP;
                if (rr > lim) { break; }
                if ((k % 3) == 0) {
                    var v = _pt[base + k];
                    var x = upx(v); var y = upy(v);
                    dc.setColor(_colLut[(rr <= CR_MAX) ? rr : CR_MAX],
                        Gfx.COLOR_TRANSPARENT);
                    var a2 = (a + k * 13) % 256;
                    var le = 3 + (k % 4);
                    dc.drawLine(x, y, x + (le * GenArt.isin(a2 + 64)) / 127,
                        y + (le * GenArt.isin(a2)) / 127);
                    _ink -= 1;
                }
            }
        }
    }

    // Fill _colLut[0..CR_MAX] with the colony colour at each radius. Bands are
    // sorted ascending by outer radius (appended as the frontier advances), so a
    // single monotonic sweep fills the whole table -- O(coln + CR_MAX), built
    // once per frame instead of an O(coln) scan per fur spine.
    function fillColLut() {
        var n = _coln;
        var bi = 0;
        for (var r = 0; r <= CR_MAX; r++) {
            while (bi < n && (_colband[bi] & 0xFF) < r) { bi++; }
            var ci = (bi < n) ? ((_colband[bi] >> 8) & 0xFF)
                              : ((_colband[n - 1] >> 8) & 0xFF);
            _colLut[r] = colorOf(ci);
        }
    }

    // Fill _blLut[0..REACH_CAP] with bloom bi's colour at each radius (same sweep).
    function fillBloomLut(bi) {
        var base = bi * BBANDS; var n = _blnb[bi];
        var j = 0;
        for (var r = 0; r <= REACH_CAP; r++) {
            while (j < n && (_blband[base + j] & 0xFF) < r) { j++; }
            var ci = (j < n) ? ((_blband[base + j] >> 8) & 0xFF)
                             : ((_blband[base + n - 1] >> 8) & 0xFF);
            _blLut[r] = colorOf(ci);
        }
    }

    // A bloom = a burst of bowed, sometimes-forking spines fired outward along
    // its arm, each coloured by the HR-zone band at its tip. The fan (angles,
    // lengths, bow, forks) is a cheap deterministic function of the bloom salt,
    // recomputed each frame and just scaled by reach as the bloom grows.
    function drawBloom(dc, bi) {
        if (_blnb[bi] == 0) { return; }
        fillBloomLut(bi);                            // O(1) colour lookups below
        var ang = _blang[bi];
        var reach = _blreach[bi]; var w = _blw[bi]; var salt = _blsalt[bi];
        var bx = _blbx[bi]; var by = _blby[bi];
        var nsp = 6 + (GenArt.hash16(salt, 1, 1) % 6);
        dc.setColor(_blLut[BASE], Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(bx, by, 1 + w / 8);            // tiny anchor node (1..3px)
        for (var k = 0; k < nsp; k++) {
            if (_ink <= 0) { return; }
            var off = (GenArt.hash16(salt, k, 4) % 121) - 60;
            var lf = 90 + (GenArt.hash16(salt, k, 5) % 166);
            var bow = (GenArt.hash16(salt, k, 7) % 13) - 6;
            var fork = (GenArt.hash16(salt, k, 6) % 2) == 0;
            var a2 = (ang + off) % 256;
            var dx = GenArt.isin(a2 + 64); var dy = GenArt.isin(a2);
            var px = GenArt.isin(a2 + 128); var py = GenArt.isin(a2 + 64);
            var tip = BASE + ((reach - BASE) * lf) / 256;
            var mr = tip / 2;
            var mx = bx + (mr * dx) / 127 + (bow * px) / 127;
            var my = by + (mr * dy) / 127 + (bow * py) / 127;
            var ex = bx + (tip * dx) / 127;
            var ey = by + (tip * dy) / 127;
            dc.setColor(_blLut[(tip <= REACH_CAP) ? tip : REACH_CAP],
                Gfx.COLOR_TRANSPARENT);
            dc.drawLine(bx, by, mx, my);             // bowed spine, 2 segments
            dc.drawLine(mx, my, ex, ey);
            _ink -= 2;
            if (fork) {                              // branch at the elbow
                var a3 = (a2 + (((off & 1) == 0) ? 24 : -24)) % 256;
                var fr = tip / 3;
                dc.drawLine(mx, my, mx + (fr * GenArt.isin(a3 + 64)) / 127,
                    my + (fr * GenArt.isin(a3)) / 127);
                _ink -= 1;
            }
        }
    }

    // ---- persistence (compact) -------------------------------------------------
    //
    // The dish is an accretive day-long simulation held only in RAM, so a watch-
    // face reload (e.g. opening a menu) would lose it and it cannot replay the day.
    // Stored as one flat Array of Numbers (the only compact type the 2.4 object
    // store takes -- no ByteArray), each slot costs ~5 bytes, so the naive full
    // dump (~1550 slots, ~7 KB transient) could not coexist with the ~56.5 KB dish
    // inside the watch-face budget: save() silently OOM'd (caught) and the dish
    // came back blank after a reload. This compact form ~halves the payload (and
    // the onHide transient) two ways, with no change to the live dish:
    //   1. store only every OTHER skeleton vertex; rebuild the in-between ones by
    //      midpoint on load (the arm keeps its full vertex count + radius
    //      bookkeeping, just slightly straighter between samples until it grows on)
    //   2. pack the 16-bit bloom/colony bands two to a Number
    // A maxed evening dish may still be too big and fall back to a blank restore
    // (caught) -- acceptable, and no worse than before. load() begins with a
    // version magic and validates every count against its cap, resetting to a
    // blank dish on any mismatch, so an old/corrupt/short payload can never
    // half-load or crash.
    const SAVE_MAGIC = 0x5B102;   // format tag (bumped when the layout changes)

    function save() {
        var n = 1 + 20 + 1;                  // magic + header/win + nfil
        for (var i = 0; i < _nfil; i++) { n += 5 + _thnp[i] / 2 + 1; }
        n += 1;                              // nbloom
        for (var i = 0; i < _nbloom; i++) { n += 10 + (_blnb[i] + 1) / 2; }
        n += 2;                              // colreach, coln
        n += (_coln + 1) / 2;
        var a = new [n];
        var p = 0;
        a[p] = SAVE_MAGIC; p++;
        a[p] = _lastDay; p++;
        a[p] = _lastMin; p++;
        a[p] = (_lastSteps == null) ? -1 : _lastSteps; p++;
        a[p] = _bar; p++;
        a[p] = _epiOn ? 1 : 0; p++;
        a[p] = _epiIdx; p++;
        a[p] = _nightAcc; p++;
        a[p] = _sleepSeed; p++;
        a[p] = _winN; p++;
        a[p] = _winHead; p++;
        for (var i = 0; i < 10; i++) { a[p] = _win[i]; p++; }
        a[p] = _nfil; p++;
        for (var i = 0; i < _nfil; i++) {
            a[p] = _tha[i]; p++; a[p] = _thL[i]; p++; a[p] = _thv[i]; p++;
            a[p] = _thnext[i]; p++;
            var np = _thnp[i];
            a[p] = np; p++;
            var base = i * PMAX;
            for (var k = 0; k < np; k += 2) { a[p] = _pt[base + k]; p++; } // evens
            if ((np & 1) == 0 && np > 0) {                 // tip, when count even
                a[p] = _pt[base + np - 1]; p++;
            }
        }
        a[p] = _nbloom; p++;
        for (var i = 0; i < _nbloom; i++) {
            a[p] = _blbx[i]; p++; a[p] = _blby[i]; p++; a[p] = _blang[i]; p++;
            a[p] = _blw[i]; p++; a[p] = _blsalt[i]; p++; a[p] = _blreach[i]; p++;
            a[p] = _blmom[i]; p++; a[p] = _blnb[i]; p++;
            a[p] = _blmom0[i]; p++; a[p] = _bllastzi[i]; p++;
            var bb = i * BBANDS; var nb = _blnb[i];
            for (var k = 0; k < nb; k += 2) {
                var w = _blband[bb + k] & 0xFFFF;
                if (k + 1 < nb) { w = w | ((_blband[bb + k + 1] & 0xFFFF) << 16); }
                a[p] = w; p++;
            }
        }
        a[p] = _colreach; p++; a[p] = _coln; p++;
        for (var k = 0; k < _coln; k += 2) {
            var w = _colband[k] & 0xFFFF;
            if (k + 1 < _coln) { w = w | ((_colband[k + 1] & 0xFFFF) << 16); }
            a[p] = w; p++;
        }
        return a;
    }

    // Restore state written by save(). Defensive throughout: a wrong magic, any
    // out-of-range count, or a short array drops back to a freshly reset (blank)
    // dish rather than half-loading. Caller wraps the read in try/catch too.
    function load(a) {
        if (a == null || a.size() < 22 || a[0] != SAVE_MAGIC) { return; }
        var sz = a.size();
        var p = 1;                           // a[0] is the magic
        _lastDay = a[p]; p++;
        _lastMin = a[p]; p++;
        var ls = a[p]; p++; _lastSteps = (ls < 0) ? null : ls;
        _bar = a[p]; p++;
        _epiOn = (a[p] != 0); p++;
        _epiIdx = a[p]; p++;
        _nightAcc = a[p]; p++;
        _sleepSeed = a[p]; p++;
        _winN = a[p]; p++;
        _winHead = a[p]; p++;
        for (var i = 0; i < 10; i++) { _win[i] = a[p]; p++; }
        var nfil = a[p]; p++;
        if (nfil < 0 || nfil > KMAX) { reset(); return; }
        _nfil = nfil;
        for (var i = 0; i < _nfil; i++) {
            if (p + 5 > sz) { reset(); return; }
            _tha[i] = a[p]; p++; _thL[i] = a[p]; p++; _thv[i] = a[p]; p++;
            _thnext[i] = a[p]; p++;
            var np = a[p]; p++;
            if (np < 1 || np > PMAX || p + np / 2 + 1 > sz) { reset(); return; }
            _thnp[i] = np;
            var base = i * PMAX;
            for (var k = 0; k < np; k += 2) { _pt[base + k] = a[p]; p++; }
            if ((np & 1) == 0) { _pt[base + np - 1] = a[p]; p++; }    // tip
            for (var k = 1; k < np; k += 2) {                        // rebuild odds
                if (k == np - 1) { continue; }       // tip already placed (np even)
                var v0 = _pt[base + k - 1]; var v1 = _pt[base + k + 1];
                _pt[base + k] = packPt((upx(v0) + upx(v1)) / 2,
                                       (upy(v0) + upy(v1)) / 2, upci(v1));
            }
        }
        if (p >= sz) { reset(); return; }
        var nbloom = a[p]; p++;
        if (nbloom < 0 || nbloom > BMAX) { reset(); return; }
        _nbloom = nbloom;
        for (var i = 0; i < _nbloom; i++) {
            if (p + 10 > sz) { reset(); return; }
            _blbx[i] = a[p]; p++; _blby[i] = a[p]; p++; _blang[i] = a[p]; p++;
            _blw[i] = a[p]; p++; _blsalt[i] = a[p]; p++; _blreach[i] = a[p]; p++;
            _blmom[i] = a[p]; p++;
            var nb = a[p]; p++;
            _blmom0[i] = a[p]; p++; _bllastzi[i] = a[p]; p++;
            if (nb < 0 || nb > BBANDS || p + (nb + 1) / 2 > sz) { reset(); return; }
            _blnb[i] = nb;
            var bb = i * BBANDS;
            for (var k = 0; k < nb; k += 2) {
                var w = a[p]; p++;
                _blband[bb + k] = w & 0xFFFF;
                if (k + 1 < nb) { _blband[bb + k + 1] = (w >> 16) & 0xFFFF; }
            }
        }
        if (p + 2 > sz) { reset(); return; }
        _colreach = a[p]; p++;
        var coln = a[p]; p++;
        if (coln < 0 || coln > CBANDS || p + (coln + 1) / 2 > sz) { reset(); return; }
        _coln = coln;
        for (var k = 0; k < _coln; k += 2) {
            var w = a[p]; p++;
            _colband[k] = w & 0xFFFF;
            if (k + 1 < _coln) { _colband[k + 1] = (w >> 16) & 0xFFFF; }
        }
    }
}
