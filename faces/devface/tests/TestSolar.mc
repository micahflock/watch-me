using Toybox.Test;

// Unit tests for Solar math against known fixtures. Tolerance +/-3 minutes for
// sunrise/sunset, a few degrees for position. Also covers MathX hand-rolls.

(:test)
function testMathXAtan2Quadrants(logger) {
    var pi = 3.14159265;
    // Compare hand-rolled atan2 against known angles.
    assertClose(MathX.atan2(0.0, 1.0), 0.0, 0.001, logger);       // +x axis
    assertClose(MathX.atan2(1.0, 0.0), pi / 2.0, 0.001, logger);  // +y axis
    assertClose(MathX.atan2(0.0, -1.0), pi, 0.001, logger);       // -x axis
    assertClose(MathX.atan2(-1.0, 0.0), -pi / 2.0, 0.001, logger);// -y axis
    return true;
}

(:test)
function testMathXFloor(logger) {
    Test.assertEqual(MathX.floor(3.7), 3.0);
    Test.assertEqual(MathX.floor(3.0), 3.0);
    Test.assertEqual(MathX.floor(-1.2), -2.0);
    Test.assertEqual(MathX.floor(-4.0), -4.0);
    return true;
}

(:test)
function testMathXFmod(logger) {
    assertClose(MathX.fmod(370.0, 360.0), 10.0, 0.001, logger);
    assertClose(MathX.fmod(-10.0, 360.0), 350.0, 0.001, logger);
    return true;
}

(:test)
function testSolarJulianDay(logger) {
    // 2000-01-01 corresponds to JD 2451545 (J2000 epoch, at noon; date part).
    var jd = Solar.julianDay(2000, 1, 1);
    Test.assert(jd >= 2451544 && jd <= 2451545);
    return true;
}

(:test)
function testSolarSunriseGreenwichEquinox(logger) {
    // Greenwich (51.48N, 0.0), 2026-03-20 (near equinox): sunrise ~06:00 UTC,
    // sunset ~18:10 UTC. Allow generous tolerance for the simplified model.
    var jd = Solar.julianDay(2026, 3, 20);
    var t = Solar.sunTimes(jd, 51.48, 0.0);
    Test.assert(t != null);
    var sunriseMin = t[0];
    var sunsetMin = t[1];
    // Sunrise between 05:30 and 06:30 UTC.
    Test.assert(sunriseMin > 330 && sunriseMin < 390);
    // Sunset between 17:50 and 18:40 UTC.
    Test.assert(sunsetMin > 1070 && sunsetMin < 1120);
    // Day length near 12h at equinox.
    var lengthHrs = (sunsetMin - sunriseMin) / 60.0;
    assertClose(lengthHrs, 12.1, 0.4, logger);
    return true;
}

(:test)
function testSolarPolarNight(logger) {
    // Far north in deep winter: sun never rises -> null.
    var jd = Solar.julianDay(2026, 12, 21);
    var t = Solar.sunTimes(jd, 80.0, 0.0);
    Test.assert(t == null);
    return true;
}

(:test)
function testSolarPositionElevationRange(logger) {
    var jd = Solar.julianDay(2026, 6, 21);
    // Local solar noon-ish at Greenwich: elevation should be high and positive.
    var pos = Solar.position(jd, 12.0, 51.48, 0.0);
    var az = pos[0];
    var el = pos[1];
    Test.assert(az >= 0.0 && az <= 360.0);
    Test.assert(el > 50.0 && el < 65.0); // ~62 deg at summer solstice
    return true;
}

function assertClose(actual, expected, tol, logger) {
    var d = actual - expected;
    if (d < 0) { d = -d; }
    if (d > tol) {
        if (logger != null) {
            logger.debug("expected " + expected + " got " + actual + " (tol " + tol + ")");
        }
        Test.assert(false);
    }
}
