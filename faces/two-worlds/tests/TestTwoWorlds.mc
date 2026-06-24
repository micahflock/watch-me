using Toybox.Test;
using Toybox.System as Sys;

// Unit tests for two-worlds face-specific logic. The clock/readout/marker
// geometry is exercised by rendering; the data-binding math is tested here.

// A do-nothing Dc: accepts every primitive the components call but rasterizes
// nothing, so timing a render() measures the VM cost (trig, loops) -- which is
// what the watchdog counts -- not native raster. Mirrors the real Dc surface.
class NoopDc {
    function setColor(a, b) {}
    function clear() {}
    function setClip(a, b, c, d) {}
    function clearClip() {}
    function drawLine(a, b, c, d) {}
    function fillRectangle(a, b, c, d) {}
    function fillCircle(a, b, c) {}
    function fillPolygon(p) {}
    function drawText(a, b, c, d, e) {}
    function drawBitmap(a, b, c) {}
    function getWidth() { return 215; }
    function getHeight() { return 180; }
}

// Real per-frame render cost of each layer, in microseconds, on the sim. This is
// the metric that actually matters for the watchdog (it counts VM instructions /
// method calls), and the one the integer art-sandbox CANNOT model -- a blind spot
// that let BioBloom's per-vertex regeneration grow to ~90% of the frame and trip
// the watchdog on the wrist while the sandbox read a reassuring low number. This
// test grows a heavy dish and logs the cost so that regression is visible here.
// Logging only (wall-clock is host-dependent, so no hard assertion).
(:test)
function testLayerCostProfile(logger) {
    var dc = new NoopDc();
    var N = 120;

    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;
    snap.hour = 14; snap.minute = 12; snap.second = 0;
    snap.utcOffsetSec = 0; snap.lat = 51.5; snap.lon = -0.12;
    snap.heartRate = 90; snap.steps = 8000; snap.batteryPct = 80;
    snap.dayOfWeek = 4; snap.is24Hour = true; snap.phoneConnected = true;

    GenArt.initSinTable();
    var bloom = new BioBloom();             // grow a heavy, bloom-saturated dish
    var cum = 0;
    for (var t = 0; t < 1000; t++) {
        var s = new Snapshot();
        s.year = 2026; s.month = 6; s.day = 14;
        s.hour = t / 60; s.minute = t % 60;
        cum += ((t % 7) == 0) ? 130 : 8;
        s.steps = cum; s.heartRate = 95 + (t % 40);
        bloom.advance(s);
    }
    var border = new BorderComponent();
    var mask = new FieldMaskComponent();
    var north = new NorthComponent();

    var t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { bloom.render(dc, snap); }
    var tBloom = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { mask.render(dc, snap); }
    var tMask = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { border.render(dc, snap); }
    var tBorder = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { north.render(dc, snap); }
    var tNorth = Sys.getTimer() - t0;

    logger.debug("dish: nfil=" + bloom._nfil + " nbloom=" + bloom._nbloom
        + " coln=" + bloom._coln + "  (render prims this dish: see RenderBudget)");
    logger.debug("per-frame us:  bloom=" + (tBloom * 1000 / N)
        + "  fieldmask=" + (tMask * 1000 / N)
        + "  border=" + (tBorder * 1000 / N)
        + "  north=" + (tNorth * 1000 / N));
    return true;
}

(:test)
function testBatteryLevels(logger) {
    // Three 33% chunks, right-to-left drain. null -> 0 (all grey).
    Test.assert(Face.batteryLevel(null) == 0);
    Test.assert(Face.batteryLevel(0) == 0);
    Test.assert(Face.batteryLevel(20) == 1);
    Test.assert(Face.batteryLevel(33) == 1);
    Test.assert(Face.batteryLevel(34) == 2);
    Test.assert(Face.batteryLevel(50) == 2);
    Test.assert(Face.batteryLevel(66) == 2);
    Test.assert(Face.batteryLevel(67) == 3);
    Test.assert(Face.batteryLevel(100) == 3);
    return true;
}

(:test)
function testDisplayHour(logger) {
    // 24h (true or null): pass-through, 0..23.
    Test.assert(Face.displayHour(0, true) == 0);
    Test.assert(Face.displayHour(13, true) == 13);
    Test.assert(Face.displayHour(23, true) == 23);
    Test.assert(Face.displayHour(9, null) == 9);   // null -> 24h
    // 12h (false): 0 -> 12, 12 -> 12, 13 -> 1, 23 -> 11.
    Test.assert(Face.displayHour(0, false) == 12);
    Test.assert(Face.displayHour(1, false) == 1);
    Test.assert(Face.displayHour(11, false) == 11);
    Test.assert(Face.displayHour(12, false) == 12);
    Test.assert(Face.displayHour(13, false) == 1);
    Test.assert(Face.displayHour(23, false) == 11);
    return true;
}
