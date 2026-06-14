using Toybox.Graphics as Gfx;

// BioBloom — the day as a living dish (ported from sketches/algos/biobloom.py,
// the approved sandbox keeper; that file is the parity reference).
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
// (colorIdx<<8 | rEnd). Colour index 0..7 maps to ZONE_COLORS (7 == DK_GRAY);
// 8 == LT_GRAY (colony idle bands only). Evolution is incremental — advance()
// simulates only the minutes since the last tick (capped) — and resets the dish
// at midnight. All integer math (the watchdog is the binding constraint).
class BioBloom {

    const CX = 107;
    const CY = 108;            // centre at 2/5 of the screen height up from bottom
    const R0 = 7;
    const RMAX = 86;
    const UNIT = 64;
    const KACT = 6;            // movement -> growth (smaller => faster threads)
    const STEP = 2;            // px of radius per appended vertex
    const KMAX = 22;           // cap on live filaments
    const SEEDS = 9;           // initial threads, spread around the centre
    const PMAX = 44;           // vertices per thread (R0..RMAX by STEP + slack)

    const ACTIVE = 3;          // zone idx >= this is an elevated-HR minute
    const BASE = 2;            // px a bloom starts out from its anchor
    const GROW = 2;            // px the bloom frontier advances per minute
    const REACH_CAP = 46;      // px a bloom can reach along its arm
    const MOM_DIV = 16;        // steps/min -> momentum reservoir units
    const MOM_STEP = 2;        // px of momentum growth per minute after HR drops
    const BMAX = 16;           // cap on blooms
    const BBANDS = 28;         // cap on bands per bloom

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
    const CBANDS = 96;         // cap on colony bands
    const LTGREY = 8;          // colour index for COLOR_LT_GRAY (colony idle)

    // threads
    var _tha; var _thL; var _thv; var _thnext; var _thnp; var _nfil;
    var _pt;                   // packed vertices: colorIdx<<16 | x<<8 | y
    // blooms
    var _blbx; var _blby; var _blang; var _blw; var _blsalt; var _blreach;
    var _blmom; var _blnb; var _blband; var _nbloom;   // _blband: ci<<8 | rEnd
    // colony
    var _colreach; var _coln; var _colband;            // _colband: ci<<8 | rEnd
    // episode / inactivity
    var _epiOn; var _epiIdx; var _bar;
    // HR window (last 10 samples, ring)
    var _win; var _winN; var _winHead;
    // lifecycle
    var _lastMin; var _lastSteps; var _lastDay;
    var _bloomBase;
    var _ord;                  // scratch index array for _longish

    function initialize() {
        _tha = new [KMAX]; _thL = new [KMAX]; _thv = new [KMAX];
        _thnext = new [KMAX]; _thnp = new [KMAX];
        _pt = new [KMAX * PMAX];
        _blbx = new [BMAX]; _blby = new [BMAX]; _blang = new [BMAX];
        _blw = new [BMAX]; _blsalt = new [BMAX]; _blreach = new [BMAX];
        _blmom = new [BMAX]; _blnb = new [BMAX];
        _blband = new [BMAX * BBANDS];
        _colband = new [CBANDS];
        _win = new [10];
        _ord = new [KMAX];
        _bloomBase = GenArt.hash16(SEEDS, 17, 3) % 256;
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
        return (ci == LTGREY) ? Gfx.COLOR_LT_GRAY : GenArt.ZONE_COLORS[ci];
    }

    // ---- per-minute simulation ------------------------------------------------

    function advance(state) {
        if (state.hour == null || state.minute == null) { return; }
        var now = state.hour * 60 + state.minute;
        var day = (state.day != null) ? state.day : 0;
        if (day != _lastDay) {
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
        var zi = GenArt.zoneIndex(hr);
        pushWin((hr != null) ? hr : 0);
        var vrange = winRange();
        var rising = winRising();

        var iters = (d > 12) ? 12 : d;
        for (var k = 0; k < iters; k++) {
            stepMinute(spm, zi, vrange, rising, nowSteps);
        }
        _lastMin = now;
        if (steps != null) { _lastSteps = steps; }
    }

    function stepMinute(spm, zi, vrange, rising, salt) {
        var move = spm / KACT;
        var cidx = (spm <= 1) ? 7 : zi;          // 7 == DK_GRAY == ZONE_COLORS[7]

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
                _blmom[_epiIdx] += spm / MOM_DIV;
                if (_blmom[_epiIdx] > REACH_CAP) { _blmom[_epiIdx] = REACH_CAP; }
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
                var last = (_blband[i * BBANDS + _blnb[i] - 1] >> 8) & 0xFF;
                bandBloom(i, last, g);
                _blmom[i] -= g;
            }
        }
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
            cidx = (_bar >= BAR_HI) ? 7 : LTGREY;   // 7 == DK_GRAY
        } else {
            cidx = zi;
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

    function render(dc, state) {
        drawColony(dc);
        for (var i = 0; i < _nfil; i++) {
            var np = _thnp[i];
            var base = i * PMAX;
            for (var k = 1; k < np; k++) {
                var a = _pt[base + k - 1]; var b = _pt[base + k];
                dc.setColor(colorOf(upci(b)), Gfx.COLOR_TRANSPARENT);
                dc.drawLine(upx(a), upy(a), upx(b), upy(b));
            }
        }
        for (var bi = 0; bi < _nbloom; bi++) { drawBloom(dc, bi); }
    }

    function drawColony(dc) {
        if (_coln == 0) { return; }
        dc.setColor(colorOf((_colband[0] >> 8) & 0xFF), Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(CX, CY, R0);
        var reach = _colreach;
        for (var i = 0; i < _nfil; i++) {
            var lim = _thL[i] / UNIT - TRAIL;
            if (lim > reach) { lim = reach; }
            if (lim <= R0) { continue; }
            var np = _thnp[i];
            var base = i * PMAX;
            var bn = 0;                       // colony band pointer (tandem)
            for (var k = 1; k < np; k++) {
                var rr = R0 + k * STEP;
                if (rr > lim) { break; }
                if ((k & 1) == 0) {
                    while (bn < _coln - 1 && rr > (_colband[bn] & 0xFF)) { bn += 1; }
                    dc.setColor(colorOf((_colband[bn] >> 8) & 0xFF),
                        Gfx.COLOR_TRANSPARENT);
                    var v = _pt[base + k];
                    var x = upx(v); var y = upy(v);
                    for (var jj = 0; jj < 2; jj++) {
                        var ox = (GenArt.hash16(_tha[i], k, jj + 3) % (2 * CW + 1)) - CW;
                        var oy = (GenArt.hash16(_tha[i], k, jj + 5) % (2 * CW + 1)) - CW;
                        dc.fillCircle(x + ox, y + oy, 1);
                    }
                }
            }
        }
    }

    function blColor(bi, r) {
        var base = bi * BBANDS; var n = _blnb[bi];
        for (var i = 0; i < n; i++) {
            if (r <= (_blband[base + i] & 0xFF)) {
                return colorOf((_blband[base + i] >> 8) & 0xFF);
            }
        }
        return colorOf((_blband[base + n - 1] >> 8) & 0xFF);
    }

    function drawBloom(dc, bi) {
        if (_blnb[bi] == 0) { return; }
        var ang = _blang[bi];
        var fx = GenArt.isin(ang + 64); var fy = GenArt.isin(ang);
        var px = GenArt.isin(ang + 128); var py = GenArt.isin(ang + 64);
        var reach = _blreach[bi]; var w = _blw[bi]; var salt = _blsalt[bi];
        var nlob = 2 + (GenArt.hash16(salt, 0, 5) % 3);
        var n = reach * 2 + w * 5;
        if (n > 150) { n = 150; }
        var per = n / nlob;
        if (per < 4) { per = 4; }
        for (var j = 0; j < nlob; j++) {
            var lf = ((j + 1) * 230) / (nlob + 1) + (GenArt.hash16(salt, j, 6) % 26);
            var along = (reach * lf) / 256;
            var po = (GenArt.hash16(salt, j, 7) % (2 * w + 1)) - w;
            var lx = _blbx[bi] + (along * fx) / 127 + (po * px) / 127;
            var ly = _blby[bi] + (along * fy) / 127 + (po * py) / 127;
            var lr = 2 + (w * (nlob - j)) / nlob;
            dc.setColor(blColor(bi, along), Gfx.COLOR_TRANSPARENT);
            for (var k = 0; k < per; k++) {
                var s = j * 97 + k;
                var rr = GenArt.hash16(salt, s, 1) % (lr + 1);
                var a2 = GenArt.hash16(salt, s, 2) % 256;
                var x = lx + (rr * GenArt.isin(a2 + 64)) / 127;
                var y = ly + (rr * GenArt.isin(a2)) / 127;
                dc.fillCircle(x, y, 1);
            }
        }
    }
}
