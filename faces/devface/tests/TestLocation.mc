using Toybox.Test;

// Unit tests for DataSource's location resolution: the remembered GPS fix
// (always wins), the lat/lng property fallback, and fix recency
// (0 none / 1 stale / 2 fresh). Drives noteFix/fillLocation directly -- the
// device read (Activity.Info.currentLocation) is not reachable from a test.

function resetLoc(propLat, propLon) {
    DataSource._lat = propLat; DataSource._lon = propLon;
    DataSource._gLat = null; DataSource._gLon = null;
    DataSource._gStamp = 0; DataSource._gDirty = false; DataSource._gSaved = 0;
}

(:test)
function testLocationPropertyFallback(logger) {
    resetLoc(45.5, -122.6);
    var s = new Snapshot();
    DataSource.fillLocation(s, 1000000);
    Test.assert(s.gpsFix == 0);              // no GPS fix ever seen
    Test.assert(s.lat == 45.5 && s.lon == -122.6);
    resetLoc(null, null);
    DataSource.fillLocation(s, 1000000);
    Test.assert(s.gpsFix == 0 && s.lat == null && s.lon == null);
    return true;
}

(:test)
function testLocationGpsWins(logger) {
    resetLoc(45.5, -122.6);
    DataSource.noteFix(51480000, -1000, 1000000);   // Greenwich-ish
    var s = new Snapshot();
    DataSource.fillLocation(s, 1000000);
    Test.assert(s.lat > 51.47 && s.lat < 51.49);
    Test.assert(s.lon < 0.0 && s.lon > -0.002);
    return true;
}

(:test)
function testLocationFirstFixAgeUnknown(logger) {
    // The first fix the face ever sees has an unknown age: stale, not fresh.
    resetLoc(null, null);
    DataSource.noteFix(45512575, -122638737, 1000000);
    Test.assert(DataSource.gpsState(1000000) == 1);
    Test.assert(DataSource._gDirty);
    return true;
}

(:test)
function testLocationFreshThenStale(logger) {
    resetLoc(null, null);
    DataSource.noteFix(45512575, -122638737, 1000000);
    DataSource.noteFix(45512580, -122638737, 2000000);   // a new GPS fix
    Test.assert(DataSource.gpsState(2000000) == 2);
    Test.assert(DataSource.gpsState(2000000 + 86399) == 2);
    Test.assert(DataSource.gpsState(2000000 + 86400) == 1);
    Test.assert(DataSource.gpsState(2000000 - 60) == 1);  // clock moved back
    // the same fix reported again keeps its stamp (no false freshness)
    DataSource.noteFix(45512580, -122638737, 3000000);
    Test.assert(DataSource._gStamp == 2000000);
    return true;
}

(:test)
function testLocationRejectsSentinels(logger) {
    resetLoc(null, null);
    DataSource.noteFix(0, 0, 1000000);                   // (0,0) no-fix
    DataSource.noteFix(180000000, 180000000, 1000000);   // 180/180 no-fix
    DataSource.noteFix(-90000001, 0, 1000000);           // out of range
    Test.assert(DataSource._gLat == null);
    Test.assert(DataSource.gpsState(1000000) == 0);
    return true;
}
