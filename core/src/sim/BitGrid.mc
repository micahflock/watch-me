using Toybox.Lang as Lang;

// BitGrid — a 2D bitfield packed into 32-bit Number arrays, double-buffered.
//
// Layout: row-major. Each row uses ceil(w/32) words. Bit b of word
// (row*wpr + (x>>5)) holds cell x = (x>>5)*32 + b. Reads from _cur, writes go
// to _nxt; swap() flips them (and clears the new back buffer).
//
// Bit ops only (& | >> <<), never arithmetic that could overflow a Number.
// Note: 1<<31 is a negative Number in Monkey C; that is fine for bitwise use,
// but every shifted read is masked with &1 because >> sign-extends.
//
// Optional age channel: 2 bits/cell (values 0..3), packed 16 cells/word.
class BitGrid {
    var w;
    var h;
    var _wpr;     // words per row for the bit plane
    var _cur;     // Array<Number> current generation
    var _nxt;     // Array<Number> next generation (write target)
    var _wprAge;  // words per row for the age plane (0 if disabled)
    var _age;     // Array<Number> or null

    function initialize(width, height, withAge) {
        w = width;
        h = height;
        _wpr = (w + 31) >> 5;
        var n = h * _wpr;
        _cur = newZeroed(n);
        _nxt = newZeroed(n);
        if (withAge) {
            _wprAge = (w + 15) >> 4; // 16 cells per 32-bit word (2 bits each)
            _age = newZeroed(h * _wprAge);
        } else {
            _wprAge = 0;
            _age = null;
        }
    }

    function newZeroed(n) {
        var a = new [n];
        for (var i = 0; i < n; i++) { a[i] = 0; }
        return a;
    }

    // --- cell access ---------------------------------------------------------

    // Read current generation. Returns 0 or 1.
    function get(x, y) {
        var word = _cur[y * _wpr + (x >> 5)];
        return (word >> (x & 31)) & 1;
    }

    // Read the next-generation buffer (used during a step before swap).
    function getNext(x, y) {
        var word = _nxt[y * _wpr + (x >> 5)];
        return (word >> (x & 31)) & 1;
    }

    // Set a cell directly in the CURRENT buffer (seeding/randomize).
    function set(x, y, v) {
        var idx = y * _wpr + (x >> 5);
        var bit = 1 << (x & 31);
        if (v != 0) { _cur[idx] = _cur[idx] | bit; }
        else        { _cur[idx] = _cur[idx] & (~bit); }
    }

    // Set a cell in the NEXT buffer (the normal write during step()).
    function setNext(x, y, v) {
        var idx = y * _wpr + (x >> 5);
        var bit = 1 << (x & 31);
        if (v != 0) { _nxt[idx] = _nxt[idx] | bit; }
        else        { _nxt[idx] = _nxt[idx] & (~bit); }
    }

    // 8-neighbour live count of the CURRENT generation, toroidal wrap.
    function neighborCount(x, y) {
        var c = 0;
        var xm = (x == 0)     ? (w - 1) : (x - 1);
        var xp = (x == w - 1) ? 0       : (x + 1);
        var ym = (y == 0)     ? (h - 1) : (y - 1);
        var yp = (y == h - 1) ? 0       : (y + 1);
        c += get(xm, ym); c += get(x, ym); c += get(xp, ym);
        c += get(xm, y);                   c += get(xp, y);
        c += get(xm, yp); c += get(x, yp); c += get(xp, yp);
        return c;
    }

    // --- age channel ---------------------------------------------------------

    function hasAge() { return _age != null; }

    function getAge(x, y) {
        if (_age == null) { return 0; }
        var idx = y * _wprAge + (x >> 4);
        var shift = (x & 15) << 1; // 2 bits per cell
        return (_age[idx] >> shift) & 0x3;
    }

    function setAge(x, y, v) {
        if (_age == null) { return; }
        var idx = y * _wprAge + (x >> 4);
        var shift = (x & 15) << 1;
        var cleared = _age[idx] & (~(0x3 << shift));
        _age[idx] = cleared | ((v & 0x3) << shift);
    }

    // --- generation management ----------------------------------------------

    // Swap buffers: next becomes current, back buffer is zeroed for reuse.
    function swap() {
        var t = _cur; _cur = _nxt; _nxt = t;
        var n = _nxt.size();
        for (var i = 0; i < n; i++) { _nxt[i] = 0; }
    }

    // Zero the current generation (and ages).
    function clear() {
        for (var i = 0; i < _cur.size(); i++) { _cur[i] = 0; }
        if (_age != null) {
            for (var j = 0; j < _age.size(); j++) { _age[j] = 0; }
        }
    }

    // Randomly populate the CURRENT generation at the given density (0..100).
    // Fills whole words at once (a handful of PRNG calls per row) rather than
    // one PRNG draw per cell — the per-cell approach trips the watch-face
    // watchdog on a grid this size. Density is approximated by AND/OR-combining
    // random words (each PRNG bit is ~50%): AND two ~= 25%, AND three ~= 12%,
    // OR two ~= 75%. Bits beyond column w-1 in the last word are masked to 0.
    function randomize(prng, densityPct) {
        var lastBits = w & 31; // valid bits in the final word of a row
        var lastMask = (lastBits == 0) ? -1 : ((1 << lastBits) - 1);
        for (var y = 0; y < h; y++) {
            var base = y * _wpr;
            for (var c = 0; c < _wpr; c++) {
                var word = densityWord(prng, densityPct);
                if (c == _wpr - 1 && lastBits != 0) { word = word & lastMask; }
                _cur[base + c] = word;
            }
        }
        if (_age != null) {
            for (var i = 0; i < _age.size(); i++) { _age[i] = 0; }
        }
    }

    function densityWord(prng, pct) {
        if (pct >= 50) {
            var hi = prng.next();
            if (pct >= 70) { return hi | prng.next(); } // ~75%
            return hi;                                   // ~50%
        }
        var a = prng.next() & prng.next();               // ~25%
        if (pct <= 15) { return a & prng.next(); }       // ~12%
        return a;                                        // ~25% (covers ~16-49%)
    }

    // Count live cells in the current generation (debug/tests).
    function population() {
        var p = 0;
        for (var y = 0; y < h; y++) {
            for (var x = 0; x < w; x++) { p += get(x, y); }
        }
        return p;
    }

    // --- persistence ---------------------------------------------------------
    // serialize/deserialize the bit plane only (ages are cheap to rebuild and
    // omitted to keep object-store writes small).

    function serialize() {
        var n = _cur.size();
        var out = new [n];
        for (var i = 0; i < n; i++) { out[i] = _cur[i]; }
        return out;
    }

    function deserialize(arr) {
        if (arr == null) { return false; }
        if (!(arr instanceof Lang.Array)) { return false; }
        if (arr.size() != _cur.size()) { return false; }
        for (var i = 0; i < arr.size(); i++) { _cur[i] = arr[i]; }
        return true;
    }
}
