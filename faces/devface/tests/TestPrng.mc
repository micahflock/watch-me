using Toybox.Test;
using Toybox.Lang as Lang;

// Unit tests for the Park-Miller PRNG. Run No Evil: (:test) functions return
// true on pass; Test.assert* throw on failure.

(:test)
function testPrngDeterministic(logger) {
    var a = new Prng(12345);
    var b = new Prng(12345);
    for (var i = 0; i < 100; i++) {
        Test.assertEqual(a.next(), b.next());
    }
    return true;
}

(:test)
function testPrngStaysNumber(logger) {
    // Critical: values must never overflow into a boxed Long.
    var p = new Prng(1);
    for (var i = 0; i < 1000; i++) {
        var v = p.next();
        Test.assert(v instanceof Lang.Number);
        Test.assert(v >= 1 && v <= 2147483646);
    }
    return true;
}

(:test)
function testPrngRange(logger) {
    var p = new Prng(99);
    for (var i = 0; i < 500; i++) {
        var r = p.nextInt(40);
        Test.assert(r >= 0 && r < 40);
        var f = p.nextFloat();
        Test.assert(f >= 0.0 && f < 1.0);
    }
    return true;
}

(:test)
function testPrngDiffersBySeed(logger) {
    var a = new Prng(1);
    var b = new Prng(2);
    var differ = false;
    for (var i = 0; i < 10; i++) {
        if (a.next() != b.next()) { differ = true; }
    }
    Test.assert(differ);
    return true;
}
