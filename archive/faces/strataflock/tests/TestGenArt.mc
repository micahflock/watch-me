using Toybox.Test;

// Unit tests for the generative engine: hash determinism, sine table shape,
// zone mapping, and the StrataField simulation invariants (conservation,
// caps, idle drip, day rollover).

(:test)
function testHash16DeterministicAndBounded(logger) {
    Test.assert(GenArt.hash16(12, 34, 56) == GenArt.hash16(12, 34, 56));
    Test.assert(GenArt.hash16(12, 34, 56) != GenArt.hash16(12, 34, 57));
    Test.assert(GenArt.hash16(12, 34, 56) != GenArt.hash16(13, 34, 56));
    // Bounded to 0..0x7FFF, including for negative inputs (masked).
    for (var i = -5; i < 50; i++) {
        var h = GenArt.hash16(i, i * 7, i * 13);
        Test.assert(h >= 0 && h <= 0x7FFF);
    }
    return true;
}

(:test)
function testSinTableQuarters(logger) {
    GenArt.initSinTable();
    Test.assert(GenArt.isin(0) == 0);
    Test.assert(GenArt.isin(64) >= 126);              // sin(pi/2) ~ +127
    var z = GenArt.isin(128);                         // sin(pi) ~ 0
    Test.assert(z >= -1 && z <= 1);
    Test.assert(GenArt.isin(192) <= -126);            // sin(3pi/2) ~ -127
    Test.assert(GenArt.isin(256) == GenArt.isin(0));  // wraps
    Test.assert(GenArt.isin(-64) == GenArt.isin(192)); // negative phase ok
    return true;
}

(:test)
function testZoneIndex(logger) {
    Test.assert(GenArt.zoneIndex(null) == 7);
    Test.assert(GenArt.zoneIndex(40) == 0);
    Test.assert(GenArt.zoneIndex(64) == 0);
    Test.assert(GenArt.zoneIndex(65) == 1);
    Test.assert(GenArt.zoneIndex(104) == 2);
    Test.assert(GenArt.zoneIndex(125) == 4);
    Test.assert(GenArt.zoneIndex(159) == 5);
    Test.assert(GenArt.zoneIndex(200) == 6);
    return true;
}

// Drive a StrataField through fake minutes. Returns the field.
function runStrata(field, snap, fromMin, toMin, stepsPerMin, hr) {
    for (var t = fromMin; t <= toMin; t++) {
        snap.hour = t / 60;
        snap.minute = t % 60;
        snap.steps = (snap.steps == null) ? 0 : snap.steps + stepsPerMin;
        snap.heartRate = hr;
        field.advance(snap);
    }
    return field;
}

(:test)
function testStrataConservationAndCaps(logger) {
    GenArt.initSinTable();
    var f = new StrataField();
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 12;
    // A still hour, then a brisk 30-minute walk.
    runStrata(f, snap, 8 * 60, 9 * 60, 0, 60);
    runStrata(f, snap, 9 * 60 + 1, 9 * 60 + 30, 120, 140);
    var total = 0;
    for (var i = 0; i < f.NCOLS; i++) {
        // Band lengths must sum exactly to the column height (conservation),
        // and stay within the structural caps.
        var sum = 0;
        Test.assert(f._bcnt[i] >= 0 && f._bcnt[i] <= f.MAXB);
        for (var j = 0; j < f._bcnt[i]; j++) {
            sum += f._bands[i * f.MAXB + j] & 0xFFF;
        }
        Test.assert(sum == f._hts[i]);
        Test.assert(f._hts[i] <= f.HMAX);
        total += f._hts[i];
    }
    // The walk must have deposited substantially more than the idle drip.
    if (total < 60) {
        logger.debug("total deposited " + total);
        Test.assert(false);
    }
    // Movement estimate reflects the 120 spm walk.
    Test.assert(f.mov256() > 180);
    Test.assert(f.unrest256() >= f.mov256());
    return true;
}

(:test)
function testStrataIdleDripsSlowerThanWalking(logger) {
    var idle = new StrataField();
    var snap1 = new Snapshot();
    snap1.year = 2026; snap1.month = 6; snap1.day = 12;
    runStrata(idle, snap1, 600, 660, 0, 55);
    var walk = new StrataField();
    var snap2 = new Snapshot();
    snap2.year = 2026; snap2.month = 6; snap2.day = 12;
    runStrata(walk, snap2, 600, 660, 110, 110);
    var ti = 0;
    var tw = 0;
    for (var i = 0; i < idle.NCOLS; i++) {
        ti += idle._hts[i];
        tw += walk._hts[i];
    }
    if (tw <= ti * 3) {
        logger.debug("idle " + ti + " walk " + tw);
        Test.assert(false);
    }
    return true;
}

(:test)
function testStrataDayRolloverResets(logger) {
    var f = new StrataField();
    var snap = new Snapshot();
    snap.year = 2026; snap.month = 6; snap.day = 12;
    runStrata(f, snap, 700, 760, 100, 120);
    var seedBefore = f.daySeed();
    // Midnight: new day-of-month, clock wraps, daily steps reset to 0.
    snap.day = 13;
    snap.steps = null;
    runStrata(f, snap, 0, 2, 0, 55);
    var total = 0;
    for (var i = 0; i < f.NCOLS; i++) {
        total += f._hts[i];
    }
    // Yesterday's mountain (hundreds of grains) is gone; at most the few
    // minutes of fresh drip remain.
    Test.assert(total < 10);
    Test.assert(f.daySeed() != seedBefore);
    // Same-minute repaint must not deposit again (1 Hz high-power case).
    var before = f._hts[f._cursor];
    f.advance(snap);
    Test.assert(f._hts[f._cursor] == before);
    return true;
}
