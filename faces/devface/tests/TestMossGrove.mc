using Toybox.Test;

// Unit tests for MossGrove's day record: the recorded-workout gap replay
// (HR history -> per-minute accretion, CHUNK per call) and the chronological
// peak-zone episode bands. Expected values come from the parity reference,
// sketches/daysoma.py (same inputs through DayRecord.advance / _band).

(:test)
function testMossBandPeakMerge(logger) {
    // 20 min: zone 4 x5, 6 x10, 8 x5 -> 4-min slots (L=2) of PEAK zone
    // [4, 6, 6, 8, 8] = 0x2088664 | (2 << 24) packed, as daysoma packs it.
    var g = new MossGrove();
    for (var m = 0; m < 20; m++) {
        g.band(0, (m < 5) ? 4 : ((m < 15) ? 6 : 8));
    }
    Test.assert(g._edur[0] == 20);
    Test.assert(g._eband[0] == 34113124);
    return true;
}

(:test)
function testMossReplayFromHistory(logger) {
    // Face away 7:00..8:04 (a recorded run), back at 8:05 with HR 84: the
    // first call replays 7:00..7:11 from history (HR 150, zone 6), spreading
    // the gap's 1300 steps evenly over the 66 minutes still owed.
    var g = new MossGrove();
    g._lastMin = 419;
    g._pool = 1300;
    for (var k = 0; k < g.CHUNK; k++) { g._hrBuf[k] = 150; }
    g.replay(485, 84, g.CHUNK, true);
    Test.assert(g._lastMin == 431);
    Test.assert(g._pool == 1072);
    Test.assert(g._nepi == 1);
    Test.assert(g._epz[0] == 6);
    Test.assert(g._emag[0] == 24);
    Test.assert(g._edur[0] == 12);
    Test.assert(g._eband[0] == 23488102);
    Test.assert(g._actUnits == 36);
    return true;
}

(:test)
function testMossReplayWithoutHistoryCollapses(logger) {
    // No history: the gap collapses into the one minute 8:05, scored at the
    // HR on return (84, not elevated) -- the pre-2026-10 behaviour.
    var g = new MossGrove();
    g._lastMin = 419;
    g._pool = 1300;
    g.replay(485, 84, g.CHUNK, false);
    Test.assert(g._lastMin == 485);
    Test.assert(g._pool == 0);
    Test.assert(g._nepi == 0);
    Test.assert(g._actUnits == 216);
    return true;
}

(:test)
function testMossSaveLoadKeepsBands(logger) {
    var g = new MossGrove();
    g._lastMin = 419;
    g._pool = 1300;
    for (var k = 0; k < g.CHUNK; k++) { g._hrBuf[k] = 150; }
    g.replay(485, 84, g.CHUNK, true);
    var h = new MossGrove();
    h.load(g.save());
    Test.assert(h._lastMin == 431 && h._pool == 1072 && h._nepi == 1);
    Test.assert(h._edur[0] == 12 && h._eband[0] == 23488102);
    Test.assert(h._emag[0] == 24 && h._epz[0] == 6);
    return true;
}

(:test)
function testMossLoadsPreBandSave(logger) {
    // A pre-2026-10 record (magic 0x6033F, no pool, [zone, mag] episodes)
    // still loads after the upgrade; its beads have no bands (draw solid).
    var a = [0x6033F, 14, 5000, 600, 77, 0, 420, 0, 1, 2400, 300, 400,
             0, -1, 2,
             0, 0, 10, 20, 30, 40, 5, 3, 1,
             6, 330, 4, 12];
    var g = new MossGrove();
    g.load(a);
    Test.assert(g._lastMin == 600 && g._actUnits == 2400 && g._pool == 0);
    Test.assert(g._nepi == 2);
    Test.assert(g._epz[0] == 6 && g._emag[0] == 330 && g._edur[0] == 0);
    Test.assert(g._epz[1] == 4 && g._emag[1] == 12 && g._eband[1] == 0);
    return true;
}
