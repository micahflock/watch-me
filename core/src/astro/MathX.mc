using Toybox.Math as Math;

// MathX — math helpers that are SAFE on CIQ 2.4 firmware.
//
// Why this exists: the API docs annotate Math.atan2/floor/ceil/round as
// "1.3.0", but the CIQ 3.0 release notes listed them as NEW in 3.0, and the
// doc annotations are known to have been retconned. Calling them on real 2.4
// firmware risks a runtime "Symbol Not Found". So we hand-roll the ones the
// Solar module needs. sin/cos/tan/asin/acos/atan/sqrt/pow and Math.PI are
// genuinely 1.0.0 and safe.
//
// All values are Float (32-bit). fr735xt has no fast Double.
module MathX {

    // Two-argument arctangent. Returns radians in (-PI, PI].
    // Hand-rolled from atan() with quadrant fix-up so we never touch Math.atan2.
    function atan2(y, x) {
        var pi = Math.PI;
        if (x > 0.0) {
            return Math.atan(y / x);
        } else if (x < 0.0) {
            if (y >= 0.0) {
                return Math.atan(y / x) + pi;
            } else {
                return Math.atan(y / x) - pi;
            }
        } else { // x == 0
            if (y > 0.0) {
                return pi / 2.0;
            } else if (y < 0.0) {
                return -pi / 2.0;
            } else {
                return 0.0; // undefined; 0 is a safe convention
            }
        }
    }

    // Largest integer <= x, returned as Float. Avoids Math.floor.
    function floor(x) {
        var n = x.toNumber(); // truncates toward zero
        var f = n.toFloat();
        if (x < 0.0 && f != x) {
            f -= 1.0;
        }
        return f;
    }

    // Floating-point modulo, result has sign of m's interval [0, m).
    function fmod(x, m) {
        return x - floor(x / m) * m;
    }

    // Clamp helper used by several modules.
    function clampf(v, lo, hi) {
        if (v < lo) { return lo; }
        if (v > hi) { return hi; }
        return v;
    }
}
