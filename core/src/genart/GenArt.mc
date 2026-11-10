using Toybox.Math as Math;

// GenArt — shared utilities for the generative layers (integer hash + sine
// table). All integer math:
// the watchdog (~25-30k VM instructions per onUpdate, docs/memory-budget.md)
// is the binding constraint, so the hot paths avoid Float entirely.
module GenArt {

    // Deterministic 16-bit hash (FNV-flavored). The 0x6CD multiplier keeps
    // every intermediate product under 2^28, so 32-bit Number arithmetic
    // never overflows. Returns 0..0x7FFF. Same inputs -> same output, always:
    // the fxhash principle — the artwork is reproducible from its seeds.
    function hash16(a, b, c) {
        var h = 0x5BD1;
        h = ((h ^ (a & 0xFFFF)) * 0x6CD) & 0xFFFF;
        h = h ^ (h >> 7);
        h = ((h ^ (b & 0xFFFF)) * 0x6CD) & 0xFFFF;
        h = h ^ (h >> 7);
        h = ((h ^ (c & 0xFFFF)) * 0x6CD) & 0xFFFF;
        h = h ^ (h >> 7);
        return h & 0x7FFF;
    }

    // 256-entry sine table, value = sin(2*pi*i/256) * 127. Built once in
    // onLayout (256 Math.sin calls are fine there; never per tick).
    var _sin = null;

    function initSinTable() {
        if (_sin != null) { return; }
        _sin = new [256];
        for (var i = 0; i < 256; i++) {
            _sin[i] = (Math.sin(i * 0.02454369) * 127.0).toNumber();
        }
    }

    // p is a phase in 1/256ths of a turn; any Number is accepted (masked).
    function isin(p) {
        return _sin[p & 255];
    }
}
