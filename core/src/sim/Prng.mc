// Prng — deterministic seeded pseudo-random generator.
//
// Algorithm: Park-Miller "MINSTD" (multiplier 16807, modulus 2^31-1) evaluated
// with Schrage's decomposition. Why not xorshift/a naive LCG? In Monkey C a
// Number is 32-bit signed and arithmetic overflow SILENTLY promotes to a boxed
// Long (slow, allocates), which corrupts the intended 32-bit-wrap semantics.
// Schrage's method keeps every intermediate within +/-2^31 using only plain
// Number arithmetic, so state never leaves Number.
//
// State is one Number in [1, 2^31-2]. Deterministic for a given seed.
class Prng {
    var _s;

    function initialize(seed) {
        // Avoid the fixed point at 0; pick a nonzero seed deterministically.
        if (seed == null || seed == 0) {
            _s = 0x12345;
        } else {
            var v = seed & 0x7FFFFFFF; // force nonnegative, stay in Number range
            _s = (v == 0) ? 0x12345 : v;
        }
    }

    // Next raw value in [1, 2147483646]. Stays a Number (asserted in tests).
    function next() {
        // m = 2147483647, a = 16807, q = m/a = 127773, r = m%a = 2836
        var hi = _s / 127773;
        var lo = _s % 127773;
        _s = 16807 * lo - 2836 * hi;
        if (_s <= 0) {
            _s += 0x7FFFFFFF; // 2147483647
        }
        return _s;
    }

    // Integer in [0, n). n must be > 0.
    function nextInt(n) {
        return next() % n;
    }

    // Float in [0, 1).
    function nextFloat() {
        return next().toFloat() / 2147483647.0;
    }

    // True with the given percentage probability (0..100).
    function chance(pct) {
        return nextInt(100) < pct;
    }

    // Expose/restore state (used by persistence and tests).
    function getState() { return _s; }
    function setState(s) { _s = (s == 0) ? 0x12345 : (s & 0x7FFFFFFF); }
}
