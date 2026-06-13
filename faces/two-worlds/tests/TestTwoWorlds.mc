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
