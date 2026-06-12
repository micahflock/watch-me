using Toybox.Test;

// Unit tests for SunCompass — the dial inversion (point 12 at the sun, where
// is north?) and the local-time -> UTC plumbing on top of Solar.

(:test)
function testNorthDialInversion(logger) {
    // Sun north -> north at 12; sun east -> north 90 deg to the wearer's left
    // (270 on the dial); sun south (NH noon) -> north behind (180); sun west
    // -> north to the right (90).
    assertCloseSC(SunCompass.northDial(0.0), 0.0, 0.01, logger);
    assertCloseSC(SunCompass.northDial(90.0), 270.0, 0.01, logger);
    assertCloseSC(SunCompass.northDial(180.0), 180.0, 0.01, logger);
    assertCloseSC(SunCompass.northDial(270.0), 90.0, 0.01, logger);
    return true;
}

(:test)
function testSunCompassGreenwichNoon(logger) {
    // Greenwich, summer solstice, noon UTC (offset 0): sun nearly due south,
    // so north reads ~180 on the dial; elevation ~62 deg -> sightable.
    var r = SunCompass.compute(2026, 6, 21, 12, 0, 0, 51.48, 0.0);
    Test.assert(r != null);
    assertCloseSC(r[0], 180.0, 8.0, logger);
    Test.assert(r[1] > 50.0 && r[1] < 65.0);
    return true;
}

(:test)
function testSunCompassSouthernHemisphere(logger) {
    // Sydney (33.87S, 151.21E), June solstice, local noon (UTC+10): the winter
    // sun is due NORTH, so north reads ~0/360 on the dial.
    var r = SunCompass.compute(2026, 6, 21, 12, 0, 36000, -33.87, 151.21);
    Test.assert(r != null);
    var d = r[0];
    Test.assert(d < 20.0 || d > 340.0);
    Test.assert(r[1] > 20.0 && r[1] < 40.0); // low winter sun
    return true;
}

(:test)
function testSunCompassDayRollover(logger) {
    // Local 00:30 at UTC+2 is 22:30 UTC the PREVIOUS day; compute must agree
    // with Solar.position called directly on the previous JD.
    var viaCompute = SunCompass.compute(2026, 6, 21, 0, 30, 7200, 51.48, 0.0);
    var jd = Solar.julianDay(2026, 6, 20);
    var direct = Solar.position(jd, 22.5, 51.48, 0.0);
    Test.assert(viaCompute != null);
    assertCloseSC(viaCompute[0], SunCompass.northDial(direct[0]), 0.01, logger);
    assertCloseSC(viaCompute[1], direct[1], 0.01, logger);

    // Local 23:30 at UTC-2 is 01:30 UTC the NEXT day.
    viaCompute = SunCompass.compute(2026, 6, 21, 23, 30, -7200, 51.48, 0.0);
    direct = Solar.position(Solar.julianDay(2026, 6, 22), 1.5, 51.48, 0.0);
    Test.assert(viaCompute != null);
    assertCloseSC(viaCompute[0], SunCompass.northDial(direct[0]), 0.01, logger);
    return true;
}

(:test)
function testSunCompassMissingInputs(logger) {
    // No location set -> null (renderer falls back to the "?" rose).
    Test.assert(SunCompass.compute(2026, 6, 21, 12, 0, 0, null, null) == null);
    Test.assert(SunCompass.compute(null, null, null, 12, 0, 0, 51.48, 0.0) == null);
    // Null UTC offset is tolerated (treated as 0), not fatal.
    Test.assert(SunCompass.compute(2026, 6, 21, 12, 0, null, 51.48, 0.0) != null);
    return true;
}

function assertCloseSC(actual, expected, tol, logger) {
    var d = actual - expected;
    if (d < 0) { d = -d; }
    if (d > tol) {
        if (logger != null) {
            logger.debug("expected " + expected + " got " + actual + " (tol " + tol + ")");
        }
        Test.assert(false);
    }
}
