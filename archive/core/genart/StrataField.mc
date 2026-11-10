using Toybox.Graphics as Gfx;

// StrataField — the day as sediment strata (the "past" layer).
//
// Every minute deposits grains (more when stepping) near a cursor that
// sweeps left->right with the clock, so the screen reads as a chronological
// core sample: dark-blue sleep bedrock at dawn's edge, an orange seam where
// you ran, a green ridge for the evening gym. Movement widens the scatter;
// stillness stacks towers; columns topple onto shorter neighbors until the
// pile finds its angle of repose. Midnight clears the canvas.
//
// State is flat Number arrays (memory ground rules): per column a height,
// a band count, and packed RLE bands (zoneIndex << 12 | lengthPx). Worst
// case 54*14 bands. Evolution is incremental — advance() simulates only the
// minutes since the last tick (capped), never the whole day.
//
// Also owns the shared biometric estimates derived from step deltas
// (movement now + a decaying "unrest" trace) that the Flock reads, and the
// daily seed — so all generative layers agree on the day's identity.
class StrataField {

    const NCOLS = 54;          // 54 columns x 4 px = 216 >= screen width
    const COLW = 4;
    const MAXB = 14;           // RLE bands per column, hard cap
    const HMAX = 132;          // tallest pile, px (keeps sky + clock clear)
    const SCRH = 180;
    const REPOSE = 5;          // height step that triggers toppling

    var _hts;                  // [NCOLS] column heights, px
    var _bcnt;                 // [NCOLS] bands in use
    var _bands;                // [NCOLS*MAXB] packed zoneIdx<<12|len
    var _cursor;
    var _wob;                  // cursor wobble (bounded random walk)
    var _lastMin;              // last simulated minute-of-day
    var _lastSteps;            // last cumulative daily steps, or null
    var _lastDay;              // day-of-month for rollover detection
    var _mov256;               // movement estimate now, 0..256
    var _unrest256;            // decaying activity trace, 0..256 (~1h tau)
    var _daySeed;

    function initialize() {
        _hts = new [NCOLS];
        _bcnt = new [NCOLS];
        _bands = new [NCOLS * MAXB];
        _daySeed = 1;
        reset();
    }

    function reset() {
        for (var i = 0; i < NCOLS; i++) {
            _hts[i] = 0;
            _bcnt[i] = 0;
        }
        _cursor = 4;
        _wob = 0;
        _lastMin = -1;
        _lastSteps = null;
        _lastDay = -1;
        _mov256 = 0;
        _unrest256 = 0;
    }

    function daySeed() { return _daySeed; }
    function mov256() { return _mov256; }
    function unrest256() { return _unrest256; }

    // Terrain surface height (px above screen bottom) under screen x.
    function heightAtX(x) {
        var c = x / COLW;
        if (c < 0) { c = 0; }
        if (c > NCOLS - 1) { c = NCOLS - 1; }
        return _hts[c];
    }

    // Advance the simulation to the Snapshot's minute. Call once per
    // onUpdate, before rendering. Same-minute repaints (1 Hz high power)
    // return immediately.
    function advance(state) {
        if (state.hour == null || state.minute == null) { return; }
        var now = state.hour * 60 + state.minute;
        var day = (state.day != null) ? state.day : 0;
        if (day != _lastDay || now < _lastMin) {
            reset();                       // first tick ever, or midnight
            _lastDay = day;
            _lastMin = now - 1;
            var y = (state.year != null) ? state.year : 0;
            var mo = (state.month != null) ? state.month : 0;
            _daySeed = ((y % 100) * 372 + mo * 31 + day) & 0x3FFF;
        }
        var d = now - _lastMin;
        if (d <= 0) { return; }

        var steps = state.steps;
        var sd = 0;
        if (steps != null && _lastSteps != null && steps > _lastSteps) {
            sd = steps - _lastSteps;
        }
        var spm = sd / d;                  // steps per minute over the gap
        _mov256 = (spm * 256) / 130;       // ~130 spm = flat-out walking/run
        if (_mov256 > 256) { _mov256 = 256; }

        // Unrest decays with a ~1 h time constant and jumps to movement.
        _unrest256 = _unrest256 - (_unrest256 * d) / 60;
        if (_unrest256 < 0) { _unrest256 = 0; }
        if (_mov256 > _unrest256) { _unrest256 = _mov256; }

        var zi = GenArt.zoneIndex(state.heartRate);
        var g = 1 + spm / 35;              // grains per simulated minute
        if (g > 6) { g = 6; }
        var spread = 2 + (_mov256 * 10) / 256;

        // Cap catch-up after gaps (face hidden): the cursor tracks real time
        // anyway, so a long gap just deposits a thinner stretch — same look
        // sleep gets.
        var iters = (d > 12) ? 12 : d;
        for (var k = 0; k < iters; k++) {
            var tt = now - iters + 1 + k;
            _wob += (GenArt.hash16(_daySeed, tt, 5) % 3) - 1;
            if (_wob > 6) { _wob = 6; }
            if (_wob < -6) { _wob = -6; }
            _cursor = 4 + (tt * (NCOLS - 8)) / 1440 + _wob;
            if (_cursor < 2) { _cursor = 2; }
            if (_cursor > NCOLS - 3) { _cursor = NCOLS - 3; }
            if (sd == 0 && (tt & 3) != 0) { continue; }   // idle drips slowly
            for (var gi = 0; gi < g; gi++) {
                var off = (GenArt.hash16(_daySeed + tt, gi, 1) % spread)
                        + (GenArt.hash16(_daySeed + tt, gi, 2) % spread)
                        - spread + 1;
                deposit(_cursor + off, zi);
            }
        }
        _lastMin = now;
        if (steps != null) { _lastSteps = steps; }
    }

    // Drop one grain: topple downhill to the angle of repose, then extend
    // the column's top band (or open a new one).
    function deposit(col, zi) {
        if (col < 0) { col = 0; }
        if (col > NCOLS - 1) { col = NCOLS - 1; }
        for (var i = 0; i < 8; i++) {
            var lo = col;
            if (col > 0 && _hts[col - 1] < _hts[col] - REPOSE) {
                lo = col - 1;
            }
            if (col < NCOLS - 1 && _hts[col + 1] < _hts[lo] - REPOSE) {
                lo = col + 1;
            }
            if (lo == col) { break; }
            col = lo;
        }
        if (_hts[col] >= HMAX) { return; }
        _hts[col] += 1;
        var n = _bcnt[col];
        var base = col * MAXB;
        if (n > 0 && (_bands[base + n - 1] >> 12) == zi) {
            _bands[base + n - 1] += 1;       // extend same-zone band
        } else if (n < MAXB) {
            _bands[base + n] = (zi << 12) | 1;
            _bcnt[col] = n + 1;
        } else {
            _bands[base + n - 1] += 1;       // cap hit: thicken the crust
        }
    }

    // Compositor component contract.
    function render(dc, state) {
        for (var i = 0; i < NCOLS; i++) {
            var n = _bcnt[i];
            if (n == 0) { continue; }
            var x = i * COLW;
            var y = SCRH;
            var base = i * MAXB;
            for (var j = 0; j < n; j++) {
                var e = _bands[base + j];
                var len = e & 0xFFF;
                y -= len;
                dc.setColor(GenArt.ZONE_COLORS[e >> 12], Gfx.COLOR_TRANSPARENT);
                dc.fillRectangle(x, y, COLW, len);
            }
            dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
            dc.fillRectangle(x, y - 1, COLW, 1);              // crust line
        }
        // A white grain marks where "now" is depositing.
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        dc.fillRectangle(_cursor * COLW + 1, SCRH - _hts[_cursor] - 3, 2, 2);
    }
}
