using Toybox.Test;
using Toybox.Time as Time;

// Unit tests for the DataSource location path — the part that decides whether
// the sun/north marker is steered by a GPS fix or by the hand-entered lat/lng
// properties, and what the position-fix indicator is told.
//
// The GPS read itself (Position.getInfo) cannot be tested here, and must not
// be attempted: devface's manifest does not request Positioning, and calling
// Position without it is an uncatchable app error, not a catchable exception
// (docs/gps-notes.md). So these tests run with the GPS opt-in OFF — which
// makes testLocationFallsBackToProperties do double duty: it passes only if
// refresh() never touches Position on a face that has not opted in. It caught
// exactly that regression once already.
//
// What IS tested: the poll cadence, the fix-age arithmetic, and above all the
// FALLBACK, because that is the behaviour every existing face depends on and
// the one a GPS regression would silently break.

(:test)
function testGpsPollCadence(logger) {
    // First call always polls (nothing cached yet), regardless of the clock.
    DataSource._gpsPollAt = null;
    Test.assert(DataSource.gpsPollDue(600));
    Test.assert(DataSource.gpsPollDue(null));

    // Inside the window: no poll. At/after it: poll.
    DataSource._gpsPollAt = 600;
    Test.assert(!DataSource.gpsPollDue(600));
    Test.assert(!DataSource.gpsPollDue(600 + DataSource.GPS_POLL_MIN - 1));
    Test.assert(DataSource.gpsPollDue(600 + DataSource.GPS_POLL_MIN));
    Test.assert(DataSource.gpsPollDue(900));

    // An unreadable clock after a successful poll must not re-poll every tick.
    Test.assert(!DataSource.gpsPollDue(null));
    return true;
}

(:test)
function testGpsPollWrapsMidnight(logger) {
    // Polled at 23:58; at 00:01 the naive difference is -1437 minutes. The wrap
    // must read that as 3 minutes (no poll) and 00:05 as 7 (poll) — otherwise
    // the cadence either stalls until the next evening or fires every tick.
    DataSource._gpsPollAt = 23 * 60 + 58;
    Test.assert(!DataSource.gpsPollDue(1));
    Test.assert(DataSource.gpsPollDue(5));
    return true;
}

(:test)
function testFixAgeNeedsAPosition(logger) {
    var now = Time.now();

    // The trap this guards (docs/gps-notes.md): getInfo() fills `when` in even
    // when it has no fix at all, so a timestamp with no coordinates must report
    // NO age rather than a permanently fresh one.
    DataSource._gpsLat = null;
    DataSource._gpsLon = null;
    DataSource._gpsWhen = now;
    Test.assert(DataSource.fixAgeSec(now) == null);

    // With a position, the age is the plain difference, and a clock that has
    // moved backwards since the fix clamps to 0 rather than going negative.
    DataSource._gpsLat = 45.5;
    DataSource._gpsLon = -122.6;
    DataSource._gpsWhen = now.subtract(new Time.Duration(3600));
    var age = DataSource.fixAgeSec(now);
    Test.assert(age != null && age >= 3599 && age <= 3601);

    DataSource._gpsWhen = now.add(new Time.Duration(120));
    Test.assert(DataSource.fixAgeSec(now) == 0);

    // A fix with no timestamp has an unknown age, not a zero one.
    DataSource._gpsWhen = null;
    Test.assert(DataSource.fixAgeSec(now) == null);

    clearGpsFix();
    return true;
}

(:test)
function testLocationFallsBackToProperties(logger) {
    // No fix -> the snapshot carries the property location and says so. This is
    // the path every face but two-worlds-v2 is on (no Positioning permission),
    // and the one two-worlds-v2 itself uses until the watch has a fix.
    clearGpsFix();
    DataSource._lat = 45.5126;
    DataSource._lon = -122.6387;

    var snap = new Snapshot();
    DataSource.refresh(snap);
    Test.assert(snap.locFromGps == false);
    assertCloseDS(snap.lat, 45.5126, 0.0005, logger);
    assertCloseDS(snap.lon, -122.6387, 0.0005, logger);
    Test.assert(snap.gpsFixAgeSec == null);
    return true;
}

(:test)
function testFixOverridesProperties(logger) {
    // A fix wins over the properties: it is the more CURRENT position, which is
    // what the sun azimuth actually needs once the wearer travels. Simulated by
    // planting the fix the poll would have produced — the poll itself stays off
    // (no permission on this face), so this exercises only the choice.
    DataSource._lat = 45.5126;
    DataSource._lon = -122.6387;
    DataSource._gpsLat = 51.4778;
    DataSource._gpsLon = -0.0015;
    DataSource._gpsWhen = Time.now();
    DataSource._gpsQual = 1;                  // QUALITY_LAST_KNOWN

    var snap = new Snapshot();
    DataSource.refresh(snap);
    Test.assert(snap.locFromGps == true);
    assertCloseDS(snap.lat, 51.4778, 0.0005, logger);
    assertCloseDS(snap.lon, -0.0015, 0.0005, logger);
    Test.assert(snap.gpsQuality == 1);
    Test.assert(snap.gpsFixAgeSec != null && snap.gpsFixAgeSec < 5);

    clearGpsFix();
    DataSource._lat = null;
    DataSource._lon = null;
    return true;
}

(:test)
function testGpsDisabledByDefault(logger) {
    // The opt-in is what keeps every permission-less face alive, so assert it
    // rather than trusting it: nothing in the shared core may switch it on.
    Test.assert(DataSource._gpsEnabled == false);
    return true;
}

// Leave no fix behind: these tests write module state directly, and a leftover
// fix would silently steer whatever test runs next.
function clearGpsFix() {
    DataSource._gpsLat = null;
    DataSource._gpsLon = null;
    DataSource._gpsQual = null;
    DataSource._gpsWhen = null;
    DataSource._gpsPollAt = null;
}

function assertCloseDS(got, want, tol, logger) {
    if (got == null) {
        logger.debug("expected " + want + ", got null");
        Test.assert(false);
    }
    var d = got - want;
    if (d < 0) { d = -d; }
    if (d > tol) {
        logger.debug("expected " + want + " +-" + tol + ", got " + got);
    }
    Test.assert(d <= tol);
}
