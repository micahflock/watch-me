using Toybox.Test;
using Toybox.System as Sys;
using Toybox.WatchUi as Ui;

// Unit tests for the shipping face (two-worlds-v2): the chrome's data-binding
// math, the north marker's rim geometry, and the per-layer cost / RAM
// profiles of MossGrove plus the V2 chrome. The MossGrove engine's own tests
// (bands, gap replay, save/load) are in the shared-core suite,
// faces/devface/tests/TestMossGrove.mc.
//
// These run from the face's own debug build under `monkeydo -t`
// (scripts/test.sh two-worlds-v2). That build cannot run AS A FACE (Out Of
// Memory in FieldMaskComponent.initialize, docs/toolchain-notes.md), but the
// unit-test runner gives the app a far larger heap (totalMemory reads ~8 MB,
// not ~60 KB), so the same PRG runs its tests fine.

// A do-nothing Dc: accepts every primitive the components call but rasterizes
// nothing, so timing a render() measures the VM cost (trig, loops, method
// calls) -- which is what the watchdog counts -- not native raster. Mirrors
// the real Dc surface the face uses.
class NoopDc {
    function setColor(a, b) {}
    function clear() {}
    function setClip(a, b, c, d) {}
    function clearClip() {}
    function drawLine(a, b, c, d) {}
    function drawPoint(a, b) {}
    function drawCircle(a, b, c) {}
    function fillRectangle(a, b, c, d) {}
    function fillCircle(a, b, c) {}
    function fillPolygon(p) {}
    function drawText(a, b, c, d, e) {}
    function drawBitmap(a, b, c) {}
    function getWidth() { return 215; }
    function getHeight() { return 180; }
}

// The pinned worst-case record of docs/watchdog-debugging.md: max cushion,
// tufts and texture (act 4200, which also raises the breach banner), 16
// max-size beads with six distinct growth rings each, the last one an open
// episode, and a 10 h root star with a fully broken night. Set directly --
// growing it through advance() would take hours of simulated minutes.
function pinSaturatedGrove(g, day) {
    g._lastDay = day;
    g._seed = 1234;
    g._actUnits = 4200;
    g._activeMin = 600; g._idleMin = 300;
    for (var z = 0; z < 9; z++) { g._zoneMin[z] = 10 + z * 7; }
    g._nepi = 16;
    for (var i = 0; i < 16; i++) {
        g._epz[i] = 8; g._emag[i] = 600;
        g._edur[i] = 768;
        g._eband[i] = 3 | (4 << 4) | (5 << 8) | (6 << 12) | (7 << 16)
                    | (8 << 20) | (7 << 24);
    }
    g._epiOn = true; g._epiIdx = 15;
    g._sleepSeed = 600; g._wakeSeed = 16;
    g._night = 0; g._wakes = 0;
    g._pool = 1300; g._prev = null;
}

function profileSnapshot() {
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;
    snap.hour = 14; snap.minute = 12; snap.second = 0;
    snap.utcOffsetSec = 0; snap.lat = 51.5; snap.lon = -0.12;
    snap.heartRate = 150; snap.steps = 8000; snap.batteryPct = 80;
    snap.dayOfWeek = 1; snap.is24Hour = true; snap.phoneConnected = true;
    snap.gpsFix = 2;
    return snap;
}

// Real per-frame cost of each layer, in microseconds, on the sim. This is the
// metric that matters for the watchdog (it counts VM instructions / method
// calls) and the one the integer art sandbox CANNOT model. Every layer of the
// shipping render list is timed over the pinned saturated record, plus the
// 12-minute gap replay that can share the same onUpdate. Logging only
// (wall-clock is host-dependent, so no hard assertion): read the
// "per-frame us:" line and compare it with the previous run.
(:test)
function testLayerCostProfile(logger) {
    var dc = new NoopDc();
    var N = 120;
    var snap = profileSnapshot();

    GenArt.initSinTable();
    var grove = new MossGrove();
    pinSaturatedGrove(grove, snap.day);
    var mask = new FieldMaskComponent();
    var border = new BorderComponent();
    var ring = new PhoneRingComponent();
    var uplink = new UplinkComponent();
    var battery = new BatteryComponent();
    var readout = new ReadoutComponent(new StripGlyphs(Rez.Drawables.FontDow, 18),
        new StripGlyphs(Rez.Drawables.FontDate, 6));
    var clock = new ClockComponent(new StripGlyphs(Rez.Drawables.FontTime, 18),
        Ui.loadResource(Rez.Drawables.FontColon));
    var breach = new BreachComponent(grove);
    var north = new NorthComponent();

    var t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { grove.render(dc, snap); }
    var tGrove = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { mask.render(dc, snap); }
    var tMask = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { border.render(dc, snap); }
    var tBorder = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) {
        ring.render(dc, snap); uplink.render(dc, snap); battery.render(dc, snap);
        readout.render(dc, snap); clock.render(dc, snap); breach.render(dc, snap);
    }
    var tChrome = Sys.getTimer() - t0;
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) { north.render(dc, snap); }
    var tNorth = Sys.getTimer() - t0;

    // The 12-minute (CHUNK) history replay into the open episode, HR 150.
    // Re-pinned each round (same minutes, same step pool, same open
    // episode); the re-pin itself is ~70 stores, noise against the replay.
    t0 = Sys.getTimer();
    for (var i = 0; i < N; i++) {
        pinSaturatedGrove(grove, snap.day);
        grove._lastMin = 839;
        for (var k = 0; k < grove.CHUNK; k++) { grove._hrBuf[k] = 150; }
        grove.replay(852, 150, grove.CHUNK, true);
    }
    var tReplay = Sys.getTimer() - t0;

    pinSaturatedGrove(grove, snap.day);
    logger.debug("grove: act=" + grove._actUnits + " nepi=" + grove._nepi
        + " sleep=" + grove._sleepSeed + " wakes=" + grove._wakeSeed);
    logger.debug("per-frame us:  grove=" + (tGrove * 1000 / N)
        + "  fieldmask=" + (tMask * 1000 / N)
        + "  border=" + (tBorder * 1000 / N)
        + "  chrome=" + (tChrome * 1000 / N)
        + "  north=" + (tNorth * 1000 / N)
        + "  replay12=" + (tReplay * 1000 / N));
    return true;
}

// Whole-app RAM is sampled per tick by Instrument (getSystemStats().usedMemory),
// but nothing decomposes it per UI component. This is the RAM analog of
// testLayerCostProfile: it allocates each onLayout component in render order
// and records the usedMemory DELTA each one adds. Logging only (GC /
// quantization make absolute bytes host-dependent -- read the deltas, not the
// totals; the total here is the unit-test build's, not the release face's).
//
// Notes on reading the numbers:
//  * MossGrove allocates every array at its cap in initialize(), so
//    "groveFixed" is the whole organism; "groveGrown" is what pinning a
//    saturated record adds on top (expected 0: it only fills existing slots).
//  * The font strips (StripGlyphs) are decoded bitmaps -- pixel data, not
//    Numbers -- measured live here via loadResource. "breachBitmaps" is the
//    three banner bitmaps the face loads on the first breach only.
//  * The shared sine table (GenArt._sin, 256 Numbers) is allocated before the
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
    var dc = new NoopDc(); hold.add(dc);
    var snap0 = profileSnapshot(); hold.add(snap0);

    var a;
    a = ramUsed(); var grove = new MossGrove(); hold.add(grove);
    var groveFixed = ramUsed() - a;
    a = ramUsed(); pinSaturatedGrove(grove, snap0.day);
    var groveGrown = ramUsed() - a;

    a = ramUsed(); var fm = new FieldMaskComponent(); hold.add(fm);
    var fieldmask = ramUsed() - a;
    a = ramUsed(); var bd = new BorderComponent(); hold.add(bd);
    var border = ramUsed() - a;
    a = ramUsed(); var pr = new PhoneRingComponent(); hold.add(pr);
    var ring = ramUsed() - a;
    a = ramUsed(); var up = new UplinkComponent(); hold.add(up);
    var uplink = ramUsed() - a;
    a = ramUsed(); var bt = new BatteryComponent(); hold.add(bt);
    var battery = ramUsed() - a;
    a = ramUsed(); var no = new NorthComponent(); hold.add(no);
    var north = ramUsed() - a;
    a = ramUsed(); var br = new BreachComponent(grove); hold.add(br);
    var breach = ramUsed() - a;
    a = ramUsed(); br.render(dc, snap0);   // act 4200: loads the three bitmaps
    var breachBitmaps = ramUsed() - a;
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
    logger.debug("RAM bytes: groveFixed=" + groveFixed + " groveGrown=" + groveGrown
        + " bitmaps=" + bitmaps + " fieldmask=" + fieldmask + " border=" + border
        + " ring=" + ring + " uplink=" + uplink + " battery=" + battery
        + " north=" + north + " breach=" + breach
        + " breachBitmaps=" + breachBitmaps + " compositor=" + compositor
        + " snapshot=" + snapshot);
    logger.debug("RAM total used=" + total + " of total=" + ramTotal()
        + " (unit-test heap; face limit 65536, ceiling 58982)  hold=" + hold.size());
    return true;
}

(:test)
function testBatteryLevels(logger) {
    // Three chunks draining right-to-left; the last one greys out at 10%
    // (Face.LOW_PCT), not 0. null -> 0 (all grey).
    Test.assert(Face.batteryLevel(null) == 0);
    Test.assert(Face.batteryLevel(0) == 0);
    Test.assert(Face.batteryLevel(5) == 0);
    Test.assert(Face.batteryLevel(10) == 0);
    Test.assert(Face.batteryLevel(10.5) == 1);
    Test.assert(Face.batteryLevel(11) == 1);
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
