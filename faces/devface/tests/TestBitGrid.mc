using Toybox.Test;

// Unit tests for BitGrid packing, neighbour counting, double-buffering, age
// channel, and serialize/deserialize.

(:test)
function testBitGridSetGet(logger) {
    var g = new BitGrid(40, 30, false);
    Test.assertEqual(g.get(0, 0), 0);
    g.set(0, 0, 1);
    g.set(39, 29, 1);
    g.set(33, 17, 1);
    Test.assertEqual(g.get(0, 0), 1);
    Test.assertEqual(g.get(39, 29), 1);
    Test.assertEqual(g.get(33, 17), 1);
    Test.assertEqual(g.get(1, 0), 0);
    g.set(0, 0, 0);
    Test.assertEqual(g.get(0, 0), 0);
    return true;
}

(:test)
function testBitGridWordBoundary(logger) {
    // Bits around the 32-cell word boundary must not bleed.
    var g = new BitGrid(64, 4, false);
    g.set(31, 1, 1);
    g.set(32, 1, 1);
    Test.assertEqual(g.get(31, 1), 1);
    Test.assertEqual(g.get(32, 1), 1);
    Test.assertEqual(g.get(30, 1), 0);
    Test.assertEqual(g.get(33, 1), 0);
    return true;
}

(:test)
function testBitGridNeighborWrap(logger) {
    var g = new BitGrid(40, 30, false);
    // Light all 8 neighbours of (0,0) using toroidal wrap.
    g.set(39, 29, 1); g.set(0, 29, 1); g.set(1, 29, 1);
    g.set(39, 0, 1);                    g.set(1, 0, 1);
    g.set(39, 1, 1); g.set(0, 1, 1);  g.set(1, 1, 1);
    Test.assertEqual(g.neighborCount(0, 0), 8);
    return true;
}

(:test)
function testBitGridBlinker(logger) {
    // A Life blinker oscillates; here we just exercise setNext/getNext/swap.
    var g = new BitGrid(40, 30, false);
    g.setNext(5, 5, 1);
    Test.assertEqual(g.get(5, 5), 0);     // current still empty
    Test.assertEqual(g.getNext(5, 5), 1); // next has it
    g.swap();
    Test.assertEqual(g.get(5, 5), 1);     // now current
    Test.assertEqual(g.getNext(5, 5), 0); // back buffer cleared
    return true;
}

(:test)
function testBitGridAge(logger) {
    var g = new BitGrid(40, 30, true);
    Test.assert(g.hasAge());
    g.setAge(10, 10, 3);
    g.setAge(11, 10, 1);
    Test.assertEqual(g.getAge(10, 10), 3);
    Test.assertEqual(g.getAge(11, 10), 1);
    Test.assertEqual(g.getAge(12, 10), 0);
    // 2-bit saturation: only low 2 bits stored.
    g.setAge(10, 10, 7);
    Test.assertEqual(g.getAge(10, 10), 3);
    return true;
}

(:test)
function testBitGridSerialize(logger) {
    var g = new BitGrid(40, 30, false);
    var p = new Prng(7);
    g.randomize(p, 50);
    var snapshot = g.serialize();
    var pop = g.population();

    var g2 = new BitGrid(40, 30, false);
    Test.assert(g2.deserialize(snapshot));
    Test.assertEqual(g2.population(), pop);
    for (var y = 0; y < 30; y++) {
        for (var x = 0; x < 40; x++) {
            Test.assertEqual(g.get(x, y), g2.get(x, y));
        }
    }
    // Wrong-size array is rejected.
    Test.assert(!g2.deserialize([1, 2, 3]));
    return true;
}
