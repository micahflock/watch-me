using Toybox.Test;

// Unit tests for two-worlds face-specific logic. The clock/readout/marker
// geometry is exercised by rendering; the data-binding math is tested here.

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
