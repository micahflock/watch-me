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

// A deliberately punishing day: ~15 h of hard-effort / active-recovery intervals
// that saturate the dish (20 filament arms, 16 blooms, a deep colony) -- the
// worst case for any render cost that scales with accreted state. Recovery HR
// drops below the elevated threshold so each cycle is a distinct episode (a new
// bloom), capping at BMAX; the movement keeps the colony and filaments growing.
function bioFeedHeavyDay(bloom) {
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;
    var cum = 0;
    for (var t = 0; t < 1440; t++) {
        var spm = 0; var hr = 54;
        if (t >= 420 && t < 1320) {                 // 07:00..22:00 intervals
            if ((t % 40) < 20) { spm = 155; hr = 150; }   // hard effort -> bloom
            else { spm = 70; hr = 92; }                   // recovery (ends episode)
        } else if (t >= 390 && t < 420) {
            spm = 20; hr = 70;                      // waking
        }
        var j = GenArt.hash16(1, t, 7);
        var step;
        if (spm != 0) {
            step = spm + (j % 21) - 10;
            if (step < 0) { step = 0; }
        } else {
            step = ((j % 1000) < 30) ? 1 : 0;
        }
        cum += step;
        snap.hour = t / 60;
        snap.minute = t % 60;
        snap.steps = cum;
        snap.heartRate = hr + (GenArt.hash16(1, t, 11) % 13) - 6;
        bloom.advance(snap);
    }
}

// Regression guard for the watchdog crashes: on a saturated dish the render must
// stay BOUNDED. Two earlier bugs slipped past because nothing asserted this --
// (1) the skeleton drew one line per vertex with no budget (~1383 primitives),
// and (2) colColor/blColor scanned the band arrays once per spine (cost grew all
// day toward the 96-band cap). Decimation + one shared ink budget cap the
// primitive count; the per-frame radius->colour LUTs make lookups O(1). This
// test pins the primitive ceiling; the band-scan cost is guarded in the sandbox
// (scrub.py --day heavy, via device.account()).
(:test)
function testBioBloomRenderBudget(logger) {
    GenArt.initSinTable();
    var b = new BioBloom();
    bioFeedHeavyDay(b);
    logger.debug("heavy dish: nbloom=" + b._nbloom + " coln=" + b._coln
        + " nfil=" + b._nfil);

    // The dish must actually be saturated, or the test isn't exercising the
    // worst case it claims to guard.
    Test.assert(b._nbloom == 16);        // BMAX -- bloom cap reached
    Test.assert(b._nfil == 20);          // KMAX -- filament cap reached
    Test.assert(b._coln >= 40);          // colony well into its band budget

    // Render work bounded regardless of dish size: one shared ink budget
    // (INK_MAX = 700) caps skeleton + blooms + fur, plus the colony core and a
    // little spine overshoot. A blown budget (e.g. the old ~1383) fails here.
    var dc = new CountDc();
    b.render(dc, null);
    logger.debug("heavy render prims=" + dc.n);
    Test.assert(dc.n <= 760);
    return true;
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
    Test.assert(b._nfil == 20);      // filaments grew to the KMAX cap

    // The simulation STATE above is bit-identical to the sketch. The render draws
    // each arm as a COARSE ANCHOR POLYLINE (not every vertex) plus per-anchor fur,
    // and each bloom as a small spine fan -- a deliberately light render, because
    // on-device profiling showed the per-vertex/per-spine METHOD-CALL cost (which
    // the integer art-sandbox does NOT model) is ~90% of the frame and was what
    // tripped the watchdog. So assert a budget BAND that confirms the render is
    // active and guards against a blowup; the primitive count is NOT the watchdog
    // metric (that is real VM instructions -- see the layer-cost profile in
    // faces/two-worlds/tests and scripts/sim.sh).
    var dc = new CountDc();
    b.render(dc, null);
    logger.debug("prims=" + dc.n);
    Test.assert(dc.n > 120 && dc.n < 700);
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

(:test)
function testBioBloomClockResync(logger) {
    // A backward clock step WITHIN the same calendar day (sync correction /
    // manual set) must NOT wipe the dish -- only a real day change does.
    GenArt.initSinTable();
    var b = new BioBloom();
    bioFeedActiveDay(b);             // ends at 23:59 on day 14
    Test.assert(b._nbloom == 4);
    Test.assert(b._coln == 52);
    Test.assert(b._nfil == 20);

    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;  // same day
    snap.hour = 8; snap.minute = 0; snap.second = 0;  // clock jumped back to 08:00
    snap.steps = 5000; snap.heartRate = 60;
    b.advance(snap);

    // Dish preserved, not reset back to the 9-filament skeleton.
    logger.debug("after resync: nbloom=" + b._nbloom + " coln=" + b._coln
        + " nfil=" + b._nfil);
    Test.assert(b._nbloom == 4);
    Test.assert(b._coln == 52);
    Test.assert(b._nfil == 20);
    return true;
}

(:test)
function testBioBloomSaveRestore(logger) {
    // A reload (menu opened on a memory-tight device) discards the in-RAM dish.
    // save()/load() through the object store must bring it back bit-identically.
    GenArt.initSinTable();
    var b = new BioBloom();
    bioFeedActiveDay(b);

    var before = new CountDc();
    b.render(before, null);

    var blob = b.save();
    // Object-store budget is "KB-scale"; report the serialized element count so
    // a regression that bloats the payload is visible.
    logger.debug("save size=" + blob.size() + " elements (~" + (blob.size() * 4)
        + " bytes)");
    Test.assert(blob.size() < 1500);     // comfortably KB-scale for the store

    // Fresh instance == a reload; restore and confirm an identical render.
    var r = new BioBloom();
    r.load(blob);
    var after = new CountDc();
    r.render(after, null);

    logger.debug("before=" + before.n + " after=" + after.n);
    Test.assert(after.n == before.n);
    Test.assert(r._nbloom == b._nbloom);
    Test.assert(r._nfil == b._nfil);
    Test.assert(r._coln == b._coln);
    Test.assert(r._colreach == b._colreach);
    Test.assert(r._lastDay == b._lastDay);
    Test.assert(r._lastMin == b._lastMin);
    Test.assert(r._lastSteps == b._lastSteps);

    // And it keeps growing correctly from the restored state (no reset).
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 14;
    snap.hour = 23; snap.minute = 59; snap.second = 0;
    snap.steps = 25000; snap.heartRate = 60;
    r.advance(snap);
    Test.assert(r._nfil == 20);          // still the grown dish, not re-seeded
    return true;
}
