using Toybox.Graphics as Gfx;

// BioBloom — the day as a living dish. The simulation (threads, blooms, colony,
// momentum) is ported from sketches/algos/biobloom.py, the parity reference for
// dish STATE (the unit tests pin nbloom/coln/nfil to it). The PARAMETRIC
// skeleton — arms stored as scalars and regenerated at render with a coarse
// fixed-amp walk, coloured by the colony LUT — mirrors sketches/algos/
// biobloom_parametric_coarse.py (the reference for the render + save/load). The
// morning sleep-seed colony is ported from sketches/algos/biobloom_morning.py.
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
// State is flat Number arrays. Arms are PARAMETRIC: each is a handful of scalars
// (seed angle a0, head angle, length, next, vertex count np, base radius rb,
// vigor) and its shape is REGENERATED at render time by sampling a smooth heading
// curve (headAngle: a gentle per-arm curl + one undulation, see below) from a0 --
// so the big per-vertex array is gone and a reload is lossless (an arm is a pure
// function of its scalars). Blooms/colony bands are
// one Number each (colorIdx<<8 | rEnd). Colour index 0..8 maps to HR_RAMP (a biobloom-local
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
// DRAW work so a large dish can never outrun the watchdog — the per-dot stipple
// did. The arm regeneration (parametric vertices replayed each frame) is the
// other unbounded cost: it is hash16/isin work the ink budget does not see, so it
// is bounded separately by widening the regen stride past REGEN_CAP (regenArm) --
// and because the heading curve is smooth, that wider stride costs less without
// making the arm uglier (it samples the same curve at fewer points).
class BioBloom {

    const CX = 107;
    const CY = 108;            // centre at 2/5 of the screen height up from bottom
    const R0 = 7;
    const RMAX = 86;
    const UNIT = 64;
    const KACT = 6;            // movement -> growth (smaller => faster threads)
    const STEP = 2;            // px of radius per appended vertex
    // Arm SHAPE (headAngle): an arm is a SMOOTH curve -- a gentle, mostly-constant
    // curvature (a circular arc; sign + tightness from the seed hash) plus one slow
    // undulation, all a pure function of (a0, rb, along-arm distance d). Because the
    // heading is smooth in d, coarsening the regen stride (regenArm) just samples
    // the SAME curve at fewer points -- it can only drop fidelity, never inject the
    // jagged staggered wander the old per-anchor random walk did (it re-rolled a
    // fresh AMP*ws turn at every stride, so a coarse arm was a DIFFERENT, wilder
    // shape than the fine one -- "kinda ugly"). Reads as an organic tendril, and
    // stays regenerable: the arm is still a pure function of its saved scalars.
    const CURL_RATE = 22;      // base curl tightness (heading units per CURL_DIV px)
    const CURL_VAR = 12;       // per-arm spread on the curl rate (seed-hashed)
    const CURL_DIV = 64;       // divisor: rate*d/CURL_DIV = heading turn at distance d
    const UND_SW = 14;         // undulation swing (heading units, 256 == full turn)
    const UND_FR = 3;          // undulation frequency along the arm
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
    const INK_MAX = 420;       // hard backstop on dc primitives per onUpdate. The
                               // real watchdog limits VM INSTRUCTIONS, and on-device
                               // profiling showed BioBloom render is ~92% of the
                               // frame and dominated by per-vertex/per-spine METHOD
                               // CALLS (coordX/packPt/isin/...), which the integer
                               // art-sandbox never modelled -- so its "VM units" badly
                               // under-read the truth and the budget was set far too
                               // high (700, then 560) while the wrist kept tripping.
                               // The dish now self-bounds well under this (coarse
                               // anchor arms + capped spines), so this only catches a
                               // pathological frame; it is not the normal governor.
    const REGEN_CAP = 96;      // total arm ANCHORS emitted per onUpdate. drawArms
                               // widens the walk stride past this so the per-frame
                               // arm cost can't grow with the dish (regenArm emits
                               // only these anchors -- no per-vertex fill).

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

    // threads (parametric: arms are scalars; vertices regenerated at render)
    var _tha0;                 // seed angle (the regeneration root)
    var _tha; var _thL; var _thv; var _thnext; var _thnp; var _nfil;
    var _thrb;                 // base radius (R0 for seeds, fork radius for branches)
    var _scr;                  // per-arm regen scratch: packPt(x, y, rr), reused
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
    var _colLut;               // radius 0..CR_MAX     -> colony colour (arms+fur)

    function initialize() {
        _tha0 = new [KMAX]; _tha = new [KMAX]; _thL = new [KMAX];
        _thnext = new [KMAX]; _thv = new [KMAX]; _thnp = new [KMAX];
        _thrb = new [KMAX];
        _blbx = new [BMAX]; _blby = new [BMAX]; _blang = new [BMAX];
        _blw = new [BMAX]; _blsalt = new [BMAX]; _blreach = new [BMAX];
        _blmom = new [BMAX]; _blnb = new [BMAX];
        _blmom0 = new [BMAX]; _bllastzi = new [BMAX];
        _blband = new [BMAX * BBANDS];
        _colband = new [CBANDS];
        _win = new [10];
        _ord = new [KMAX];
        _scr = new [PMAX];
        _colLut = new [CR_MAX + 1];
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
            _tha0[i] = a; _tha[i] = a; _thL[i] = R0 * UNIT; _thnext[i] = R0 + STEP;
            _thv[i] = v; _thnp[i] = 1; _thrb[i] = R0;
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

    // Smooth arm heading at along-arm distance d (px from the base) for an arm
    // seeded at angle a0, base radius rb. curl = a circular-arc bend (constant
    // curvature, sign + rate from the seed hash); und = one slow undulation,
    // ZEROED at d == 0 so the arm leaves the centre RADIALLY (at a0) and only then
    // curves -- so it reads as a ray that bends, not an off-axis squiggle. Smooth
    // in d, so regenArm can stride coarsely without changing the shape. headFrom is
    // the per-anchor inner form with the per-arm constants hoisted out (regenArm
    // computes them once); headAngle is the convenience form that derives them.
    function headFrom(a0, rate, sign, ph, und0, d) {
        var curl = sign * ((rate * d) / CURL_DIV);
        var und = (UND_SW * (GenArt.isin((d * UND_FR + ph) & 255) - und0)) / 127;
        var a = (a0 + curl + und) % 256;
        if (a < 0) { a += 256; }
        return a;
    }
    function headAngle(a0, rb, d) {
        var h = GenArt.hash16(a0, rb, 2);
        var rate = CURL_RATE + (h % CURL_VAR);
        var sign = ((h & 1) != 0) ? 1 : -1;
        var ph = GenArt.hash16(a0, 7, 3) % 256;
        return headFrom(a0, rate, sign, ph, GenArt.isin(ph), d);
    }

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

        if (move > 0) {
            var nf = _nfil;
            for (var i = 0; i < nf; i++) { growFil(i, move); }
            if (rising && _nfil < KMAX) {
                var src = longish(salt);
                var na = (_tha[src] + 10
                         + (GenArt.hash16(salt, nf, 9) % 22)) % 256;
                var rr = _thL[src] / UNIT;
                var v = 2 + (GenArt.hash16(salt, nf, 4) % 3);
                var j = _nfil;
                _tha0[j] = na; _tha[j] = na; _thL[j] = rr * UNIT;
                _thnext[j] = rr + STEP; _thv[j] = v; _thnp[j] = 1; _thrb[j] = rr;
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

    function growFil(i, move) {
        _thL[i] += (move * _thv[i]) / 3;
        if (_thL[i] > RMAX * UNIT) { _thL[i] = RMAX * UNIT; }
        while (_thL[i] / UNIT >= _thnext[i] && _thnext[i] <= RMAX) {
            if (_thnp[i] < PMAX) { _thnp[i] += 1; }   // cap np to the regen scratch
            _thnext[i] += STEP;
        }
        // The arm shape is a pure function of (a0, rb, d); keep _tha as the heading
        // at the current TIP so the bloom anchor (seedBloom), branch seeding and
        // nearest()/fur use the same point the skeleton actually reaches.
        _tha[i] = headAngle(_tha0[i], _thrb[i], (_thnp[i] - 1) * STEP);
    }

    function seedBloom(zi) {
        if (_nbloom >= BMAX) { return -1; }
        var target = (_bloomBase + _nbloom * 98
                     + (GenArt.hash16(zi, _nbloom, 7) % 22)) % 256;
        var src = nearest(target);
        var rTip = _thrb[src] + (_thnp[src] - 1) * STEP;   // arm tip radius
        var bx = coordX(_tha[src], rTip); var by = coordY(_tha[src], rTip);
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
        if (_coln > 0) { fillColLut(); }     // arms + fur share the colony LUT
        drawArms(dc);                        // skeleton + fur, coloured by the LUT
        for (var bi = 0; bi < _nbloom; bi++) {   // HR-zone blooms (priority)
            if (_ink <= 0) { break; }
            drawBloom(dc, bi);
        }
    }

    // Regenerate arm i as a COARSE ANCHOR POLYLINE into the _scr scratch
    // (packPt(x, y, rr) at _scr[0..n-1]); returns the anchor count n. It samples the
    // arm's SMOOTH heading curve (headFrom) at the strided anchors (k = 0, ws, ...
    // + the tip) -- there is NO per-vertex fill. drawArms then draws the arm as
    // those few anchor-to-anchor segments.
    //
    // Two things keep this cheap AND good-looking:
    //   * The heading is a smooth function of distance (headFrom), so striding by
    //     `ws` samples the SAME curve at fewer points -- coarsening only drops
    //     fidelity, it never injects wander. (The old version re-rolled a fresh
    //     AMP*ws random turn at each stride, so a coarse arm was a DIFFERENT, far
    //     wilder/jagged shape than the fine one -- the "ugly" the curve fixes.)
    //   * The per-arm curl constants (rate/sign/ph/und0) are hoisted out of the
    //     loop, so each anchor costs ~one isin for the undulation plus the two in
    //     coordX/coordY -- it dropped the old per-anchor hash16 entirely, so the
    //     smoother arm is also CHEAPER per anchor.
    // drawArms sizes `ws` from the dish so the total anchors per onUpdate stay
    // ~REGEN_CAP, bounding cost however grown the dish. _scr is reused across arms,
    // so no per-vertex array ever exists; the dish STATE is the day's record and is
    // untouched (the arm is still a pure function of its saved scalars a0, rb, np).
    function regenArm(i, ws) {
        var a0 = _tha0[i];
        var rb = _thrb[i];
        var np = _thnp[i];
        var h = GenArt.hash16(a0, rb, 2);            // per-arm curl constants, hoisted
        var rate = CURL_RATE + (h % CURL_VAR);
        var sign = ((h & 1) != 0) ? 1 : -1;
        var ph = GenArt.hash16(a0, 7, 3) % 256;
        var und0 = GenArt.isin(ph);
        var n = 0;
        var k = 0;
        while (k < np) {
            var d = k * STEP;
            var a = headFrom(a0, rate, sign, ph, und0, d);
            var rr = rb + d;
            _scr[n] = packPt(coordX(a, rr), coordY(a, rr), rr);
            n += 1;
            k += ws;
        }
        if (k - ws != np - 1) {              // ensure the tip is the last anchor
            var dt = (np - 1) * STEP;
            var at = headFrom(a0, rate, sign, ph, und0, dt);
            var rrt = rb + dt;
            _scr[n] = packPt(coordX(at, rrt), coordY(at, rrt), rrt);
            n += 1;
        }
        return n;
    }

    // Draw every arm as its coarse anchor polyline (skeleton) plus a little fur,
    // coloured by the colony radius-LUT. `ws` is sized from the dish so the TOTAL
    // anchors across all arms stay ~REGEN_CAP -- so the per-onUpdate cost is
    // bounded however large the dish grows (the anchor count, not a draw budget,
    // is now the governor). Anchors are radius-ordered (rb..tip), so the fur stops
    // at the colony reach with a break.
    function drawArms(dc) {
        var totv = 0;
        for (var i = 0; i < _nfil; i++) { totv += _thnp[i]; }
        var ws = 2;
        if (totv > REGEN_CAP) { ws = totv / REGEN_CAP + 1; }
        var haveCol = (_coln > 0);
        var reach = _colreach;
        for (var i = 0; i < _nfil; i++) {
            if (_thnp[i] < 1) { continue; }
            var n = regenArm(i, ws);
            for (var j = 1; j < n; j++) {        // skeleton: anchor to anchor
                if (_ink <= 0) { return; }
                var pa = _scr[j - 1]; var pb = _scr[j];
                var rr = upci(pb);
                dc.setColor(haveCol ? _colLut[(rr <= CR_MAX) ? rr : CR_MAX]
                                    : Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
                dc.drawLine(upx(pa), upy(pa), upx(pb), upy(pb));
                _ink -= 1;
            }
            if (!haveCol) { continue; }          // fur needs the colony LUT
            var lim = _thL[i] / UNIT - TRAIL;
            if (lim > reach) { lim = reach; }
            if (lim <= R0) { continue; }
            var ang = _tha[i];
            for (var j = 1; j < n; j++) {         // fur: a spine at each anchor
                var pt = _scr[j];
                var rrf = upci(pt);
                if (rrf > lim) { break; }         // radius-ordered -> stop at reach
                if (_ink <= 0) { return; }
                var x = upx(pt); var y = upy(pt);
                dc.setColor(_colLut[(rrf <= CR_MAX) ? rrf : CR_MAX],
                    Gfx.COLOR_TRANSPARENT);
                var a2 = (ang + j * 37) % 256;
                var le = 3 + (j % 4);
                dc.drawLine(x, y, x + (le * GenArt.isin(a2 + 64)) / 127,
                    y + (le * GenArt.isin(a2)) / 127);
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

    // A bloom = a burst of bowed, sometimes-forking spines fired outward along
    // its arm, each coloured by the HR-zone band at its tip. The fan (angles,
    // lengths, bow, forks) is a cheap deterministic function of the bloom salt,
    // recomputed each frame and just scaled by reach as the bloom grows.
    function drawBloom(dc, bi) {
        var nb = _blnb[bi];
        if (nb == 0) { return; }
        // ONE colour for the whole bloom -- the HOTTEST band it ever reached (the
        // episode's peak HR zone). A per-radius colour LUT (fillBloomLut) was built
        // for EVERY bloom EVERY frame, and on the saturated dish that LUT fill was
        // exactly where the watchdog tripped (reproduced in the sim). A bloom's
        // position, size and peak-zone colour -- the HR-episode data -- are what
        // matter; the within-bloom cooldown gradient was fine detail. setColor once,
        // not per spine.
        var base = bi * BBANDS;
        var hot = 0;
        for (var b = 0; b < nb; b++) {
            var c = (_blband[base + b] >> 8) & 0xFF;
            if (c != DKGREY && c != LTGREY && c > hot) { hot = c; }
        }
        var ang = _blang[bi];
        var reach = _blreach[bi]; var w = _blw[bi]; var salt = _blsalt[bi];
        var bx = _blbx[bi]; var by = _blby[bi];
        var nsp = 4 + (GenArt.hash16(salt, 1, 1) % 4);
        dc.setColor(colorOf(hot), Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(bx, by, 1 + w / 8);            // tiny anchor node (1..3px)
        // Each spine is a single straight line from the anchor (one hash16 for its
        // angle + length, two isin, one drawLine).
        for (var k = 0; k < nsp; k++) {
            if (_ink <= 0) { return; }
            var h1 = GenArt.hash16(salt, k, 4);
            var off = (h1 % 121) - 60;
            var lf = 90 + ((h1 / 121) % 166);
            var a2 = (ang + off) % 256;
            var tip = BASE + ((reach - BASE) * lf) / 256;
            dc.drawLine(bx, by, bx + (tip * GenArt.isin(a2 + 64)) / 127,
                by + (tip * GenArt.isin(a2)) / 127);
            _ink -= 1;
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
    // came back blank after a reload. The parametric arms make the payload tiny:
    //   1. each arm is just 7 scalars (a0, head, L, next, v, np, rb) -- NO vertex
    //      dump, since vertices are regenerated from a0 at render. The reload is
    //      lossless because the regeneration is a pure function of those scalars.
    //   2. bloom/colony bands are still packed two 16-bit values to a Number.
    // load() begins with a version magic and validates every count against its
    // cap, resetting to a blank dish on any mismatch, so an old/corrupt/short
    // payload can never half-load or crash.
    const SAVE_MAGIC = 0x5B103;   // format tag (bumped when the layout changes)

    function save() {
        var n = 1 + 20 + 1;                  // magic + header/win + nfil
        n += _nfil * 7;                      // 7 scalars/arm, no vertex dump
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
        for (var i = 0; i < _nfil; i++) {    // 7 scalars per arm, no vertices
            a[p] = _tha0[i]; p++; a[p] = _tha[i]; p++; a[p] = _thL[i]; p++;
            a[p] = _thnext[i]; p++; a[p] = _thv[i]; p++; a[p] = _thnp[i]; p++;
            a[p] = _thrb[i]; p++;
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
        for (var i = 0; i < _nfil; i++) {    // 7 scalars per arm; vertices regrow
            if (p + 7 > sz) { reset(); return; }
            _tha0[i] = a[p]; p++; _tha[i] = a[p]; p++; _thL[i] = a[p]; p++;
            _thnext[i] = a[p]; p++; _thv[i] = a[p]; p++;
            var np = a[p]; p++;
            if (np < 1 || np > PMAX) { reset(); return; }
            _thnp[i] = np;
            _thrb[i] = a[p]; p++;
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
