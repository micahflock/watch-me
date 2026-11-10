using Toybox.Test;

// Unit tests for the shared generative utilities (core/src/genart/GenArt.mc):
// hash determinism and the sine table's shape. Moved here from the retired
// strataflock suite (archive/faces/strataflock/tests/TestGenArt.mc).

(:test)
function testHash16DeterministicAndBounded(logger) {
    Test.assert(GenArt.hash16(12, 34, 56) == GenArt.hash16(12, 34, 56));
    Test.assert(GenArt.hash16(12, 34, 56) != GenArt.hash16(12, 34, 57));
    Test.assert(GenArt.hash16(12, 34, 56) != GenArt.hash16(13, 34, 56));
    // Bounded to 0..0x7FFF, including for negative inputs (masked).
    for (var i = -5; i < 50; i++) {
        var h = GenArt.hash16(i, i * 7, i * 13);
        Test.assert(h >= 0 && h <= 0x7FFF);
    }
    return true;
}

(:test)
function testSinTableQuarters(logger) {
    GenArt.initSinTable();
    Test.assert(GenArt.isin(0) == 0);
    Test.assert(GenArt.isin(64) >= 126);              // sin(pi/2) ~ +127
    var z = GenArt.isin(128);                         // sin(pi) ~ 0
    Test.assert(z >= -1 && z <= 1);
    Test.assert(GenArt.isin(192) <= -126);            // sin(3pi/2) ~ -127
    Test.assert(GenArt.isin(256) == GenArt.isin(0));  // wraps
    Test.assert(GenArt.isin(-64) == GenArt.isin(192)); // negative phase ok
    return true;
}
