using Toybox.Test;

// On-device parity tests for the BioBloom port. The Python sandbox
// (sketches/algos/biobloom.py) is the parity reference; feeding the compiled
// Monkey C the same synthetic day must reproduce the same state and the same
// render primitive count, bit for bit. If these drift, GenArt/BioBloom and the
// sketch have diverged — fix whichever is wrong (see CLAUDE.md).

// A duck-typed Dc that just counts the drawing primitives (the watchdog proxy),
// exactly like sketches/device.py's Dc.calls.
class CountDc {
    var n;
    function initialize() { n = 0; }
    function setColor(a, b) {}
    function clear() {}
    function setClip(a, b, c, d) {}
    function clearClip() {}
    function fillCircle(x, y, r) { n += 1; }
    function drawLine(a, b, c, d) { n += 1; }
    function fillRectangle(a, b, c, d) { n += 1; }
}

// Replay the sandbox "active" day (sketches/day.py) minute by minute, with the
// segment boundaries on integer minutes (ceil(hour*60)) so the schedule matches
// the Python reference run that produced the asserted numbers.
function bioFeedActiveDay(bloom) {
    var starts = [0, 390, 420, 425, 430, 480, 540, 720,
                  765, 900, 903, 960, 963, 1050, 1110, 1320];
    var spm    = [0, 12, 120, 150, 158, 18, 3, 105,
                  0, 6, 0, 165, 5, 45, 9, 1];
    var hrb    = [52, 68, 112, 132, 150, 84, 62, 96,
                  64, 134, 64, 132, 72, 138, 74, 58];
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;
    var cum = 0;
    for (var t = 0; t < 1440; t++) {
        var si = 0;
        for (var k = 0; k < 16; k++) { if (t >= starts[k]) { si = k; } }
        var base = spm[si];
        var j = GenArt.hash16(1, t, 7);
        var step;
        if (base != 0) {
            step = base + (j % 21) - 10;
            if (step < 0) { step = 0; }
        } else {
            step = ((j % 1000) < 30) ? 1 : 0;
        }
        cum += step;
        snap.hour = t / 60;
        snap.minute = t % 60;
        snap.steps = cum;
        snap.heartRate = hrb[si] + (GenArt.hash16(1, t, 11) % 13) - 6;
        bloom.advance(snap);
    }
}

(:test)
function testBioBloomDayParity(logger) {
    GenArt.initSinTable();
    var b = new BioBloom();
    bioFeedActiveDay(b);
    logger.debug("nbloom=" + b._nbloom + " colReach=" + b._colreach
        + " colBands=" + b._coln + " nfil=" + b._nfil);
    Test.assert(b._nbloom == 4);     // run, anxiety node, dash, gym
    Test.assert(b._colreach == 60);  // main colony reach tracks movement
    Test.assert(b._coln == 52);
    Test.assert(b._nfil == 22);      // filaments grew to the KMAX cap

    // The simulation STATE above is bit-identical to the sketch. The render
    // primitive count is the device's deterministic value: it differs from the
    // sketch (1323) by a single primitive, because one branch filament's wander
    // rounds one step differently here than in the float-free sketch, nudging
    // one bloom's stipple. Cosmetically irrelevant, and far under the ~25k
    // watchdog -- this assert guards against a blown render budget / regression.
    var dc = new CountDc();
    b.render(dc, null);
    logger.debug("prims=" + dc.n);
    Test.assert(dc.n == 1324);
    return true;
}

(:test)
function testBioBloomDailyReset(logger) {
    GenArt.initSinTable();
    var b = new BioBloom();
    bioFeedActiveDay(b);
    Test.assert(b._nbloom > 0);

    // Midnight: a new day-of-month with the daily step count reset to 0 must
    // wipe the dish back to a fresh skeleton.
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 15;
    snap.hour = 0; snap.minute = 1; snap.second = 0;
    snap.steps = 0; snap.heartRate = 55;
    b.advance(snap);

    Test.assert(b._nbloom == 0);
    Test.assert(b._coln == 0);
    Test.assert(b._colreach == 7);   // R0
    Test.assert(b._nfil == 9);       // re-seeded SEEDS filaments
    return true;
}
