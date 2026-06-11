using Toybox.Test;

// Unit tests for the 7-segment digit lookup table and geometry builder.

(:test)
function testSegmentLookupKnownDigits(logger) {
    // Segment masks: bit0=a..bit6=g.
    // 1 lights b,c => 0x06.
    Test.assertEqual(SegmentFont.DIGIT_SEGS[1], 0x06);
    // 8 lights all 7 => 0x7F.
    Test.assertEqual(SegmentFont.DIGIT_SEGS[8], 0x7F);
    // 7 lights a,b,c => 0x07.
    Test.assertEqual(SegmentFont.DIGIT_SEGS[7], 0x07);
    // 0 lights everything except g => 0x3F.
    Test.assertEqual(SegmentFont.DIGIT_SEGS[0], 0x3F);
    return true;
}

(:test)
function testSegmentSegmentCounts(logger) {
    // Population count of lit segments for each digit (well-known values).
    var expected = [6, 2, 5, 5, 4, 5, 6, 3, 7, 6];
    for (var d = 0; d < 10; d++) {
        var mask = SegmentFont.DIGIT_SEGS[d];
        var c = 0;
        for (var i = 0; i < 7; i++) { c += (mask >> i) & 1; }
        Test.assertEqual(c, expected[d]);
    }
    return true;
}

(:test)
function testSegmentBuildGeometry(logger) {
    var params = SegmentFont.makeParams(46, 6, 3, 0);
    var segs = SegmentFont.buildSegments(params);
    Test.assertEqual(segs.size(), 7);
    // Each segment is a hexagon (6 points), each point a 2-element array.
    for (var i = 0; i < 7; i++) {
        Test.assertEqual(segs[i].size(), 6);
        Test.assertEqual(segs[i][0].size(), 2);
    }
    // Width/height accessors are positive and consistent.
    Test.assert(SegmentFont.digitHeight(params) == 46);
    Test.assert(SegmentFont.digitWidth(params) > 0);
    return true;
}

(:test)
function testSegmentSlantShiftsTop(logger) {
    // With slant > 0, the top of a segment shifts right relative to the bottom.
    var straight = SegmentFont.buildSegments(SegmentFont.makeParams(46, 6, 3, 0));
    var slanted = SegmentFont.buildSegments(SegmentFont.makeParams(46, 6, 3, 8));
    // Segment 'a' (top) should move right under slant; segment 'd' (bottom) less so.
    var topStraightX = straight[0][0][0];
    var topSlantX = slanted[0][0][0];
    Test.assert(topSlantX >= topStraightX);
    return true;
}
