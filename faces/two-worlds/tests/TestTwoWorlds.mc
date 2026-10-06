using Toybox.Test;
using Toybox.System as Sys;
using Toybox.WatchUi as Ui;

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

// Whole-app RAM is sampled per tick by Instrument (getSystemStats().usedMemory),
// but nothing decomposes it per UI component. This is the RAM analog of
// testLayerCostProfile: it allocates each onLayout component in render order and
// records the usedMemory DELTA each one adds, so we get a per-component byte
// breakdown to sit next to the per-layer time profile. Logging only (GC /
// quantization make absolute bytes host-dependent -- read the deltas, not totals).
//
// Notes on reading the numbers:
//  * BioBloom pre-allocates every array at its CAP in initialize(), so its RAM is
//    essentially FIXED -- "bloomFixed" is the whole dish; "bloomGrown" is the extra
//    a full day of accreted state adds on top (expected ~small, the caps bound it).
//  * The font strips (StripGlyphs) are decoded bitmaps -- their cost is pixel data,
//    not Numbers, so they can rival the dish; measured live here via loadResource.
//  * A shared one-time table (GenArt._sin, 256 Numbers) is allocated before the
//    baseline so it does not land on any single component.
function ramUsed() {
    var st = Sys.getSystemStats();
    return (st != null && st has :usedMemory) ? st.usedMemory : 0;
}
function ramTotal() {
    var st = Sys.getSystemStats();
    return (st != null && st has :totalMemory) ? st.totalMemory : 0;
}

(:test)
function testLayerRamProfile(logger) {
    var hold = [];                       // keep every allocation alive (no GC)
    GenArt.initSinTable();               // shared LUT, before the baseline

    var m0 = ramUsed();
    var bloom = new BioBloom(); hold.add(bloom);
    var bloomFixed = ramUsed() - m0;     // dish arrays, all pre-sized to the caps

    // Grow a saturated dish (same schedule as testLayerCostProfile), reusing one
    // Snapshot so the delta is the dish's accreted state, not 1000 GC'd snapshots.
    var s = new Snapshot();
    s.year = 2026; s.month = 6; s.day = 14;
    var cum = 0; var g0 = ramUsed();
    for (var t = 0; t < 1000; t++) {
        s.hour = t / 60; s.minute = t % 60;
        cum += ((t % 7) == 0) ? 130 : 8;
        s.steps = cum; s.heartRate = 95 + (t % 40);
        bloom.advance(s);
    }
    var bloomGrown = ramUsed() - g0;

    var a;
    a = ramUsed(); var fm = new FieldMaskComponent(); hold.add(fm);
    var fieldmask = ramUsed() - a;
    a = ramUsed(); var bd = new BorderComponent(); hold.add(bd);
    var border = ramUsed() - a;
    a = ramUsed(); var up = new UplinkComponent(); hold.add(up);
    var uplink = ramUsed() - a;
    a = ramUsed(); var bt = new BatteryComponent(); hold.add(bt);
    var battery = ramUsed() - a;
    a = ramUsed(); var no = new NorthComponent(); hold.add(no);
    var north = ramUsed() - a;
    a = ramUsed(); var br = new BreachComponent(); hold.add(br);
    var breach = ramUsed() - a;
    a = ramUsed(); var comp = new Compositor(); hold.add(comp);
    var compositor = ramUsed() - a;
    a = ramUsed(); var snap = new Snapshot(); hold.add(snap);
    var snapshot = ramUsed() - a;

    // Bitmap-backed UI: the 7-seg time strip, day/date strips and the colon glyph.
    a = ramUsed();
    var timeStrip = new StripGlyphs(Rez.Drawables.FontTime, 18); hold.add(timeStrip);
    var colon     = Ui.loadResource(Rez.Drawables.FontColon);    hold.add(colon);
    var dowStrip  = new StripGlyphs(Rez.Drawables.FontDow, 18);   hold.add(dowStrip);
    var dateStrip = new StripGlyphs(Rez.Drawables.FontDate, 6);   hold.add(dateStrip);
    var bitmaps = ramUsed() - a;

    var total = ramUsed();
    logger.debug("RAM bytes: bloomFixed=" + bloomFixed + " bloomGrown=" + bloomGrown
        + " bitmaps=" + bitmaps + " fieldmask=" + fieldmask + " border=" + border
        + " uplink=" + uplink + " battery=" + battery + " north=" + north
        + " breach=" + breach + " compositor=" + compositor
        + " snapshot=" + snapshot);
    logger.debug("RAM total used=" + total + " of total=" + ramTotal()
        + " (limit 65536, ceiling 58982)  hold=" + hold.size());
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

// Records the marker's outer quad (the first fillPolygon of a NorthComponent
// draw; the second is the hole) so the rim geometry is checkable without a Dc.
class QuadDc {
    var quad;
    var polys = 0;
    function initialize() { quad = [[0, 0], [0, 0], [0, 0], [0, 0]]; }
    function setColor(a, b) {}
    function fillPolygon(p) {
        if (polys == 0) {
            for (var i = 0; i < 4; i++) { quad[i][0] = p[i][0]; quad[i][1] = p[i][1]; }
        }
        polys++;
    }
}

// The sun/north marker stays on the glass at EVERY bearing. The fr735xt panel
// is the r=107.5 disc about (107.5,90) clipped to 215x180; the old constant
// r=101.7 rim put the marker off it within ~28 deg of 12 and 6 o'clock --
// north sits at 6 around a northern-hemisphere noon, so it vanished for hours
// (corners reached y=-16 / y=197). Every corner as drawn must land on a panel
// row/column and inside the disc (+0.5 px for the vertex rounding).
(:test)
function testNorthMarkerOnGlass(logger) {
    var north = new NorthComponent();
    var dc = new QuadDc();
    for (var b = 0; b < 720; b++) {
        dc.polys = 0;
        north.draw(dc, b * 0.5);
        Test.assert(dc.polys == 2);
        for (var i = 0; i < 4; i++) {
            var x = dc.quad[i][0];
            var y = dc.quad[i][1];
            var dx = x - 107.5;
            var dy = y - 90.0;
            if (x < 0 || x > 214 || y < 0 || y > 179 || dx * dx + dy * dy > 108.0 * 108.0) {
                logger.debug("bearing " + (b * 0.5) + ": corner (" + x + "," + y
                    + ") is off the glass");
                return false;
            }
        }
    }
    // Sides keep the shipped gutter; only 12/6 o'clock flatten to the edges.
    Test.assert(north.rimR(0.0) == 101.7);
    Test.assert(north.rimR(-1.0) == 84.5);
    Test.assert(north.rimR(1.0) == 82.5);
    return true;
}
