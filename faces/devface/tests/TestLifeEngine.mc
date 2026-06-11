using Toybox.Test;

// LifeEngine correctness tests. The evolve hot path is heavily inlined and the
// generation can be computed in row bands across multiple step() calls, so these
// tests pin classic Conway behaviour both whole-grid and banded.

// Build an engine with an empty grid (density 0) for hand-placed patterns.
function makeEmptyLife(w, h, rowsPerStep) {
    var e = new LifeEngine({
        :w => w, :h => h, :seed => 1,
        :rowsPerStep => rowsPerStep,
        :density => 0
    });
    e.grid.clear();
    return e;
}

// Place a vertical blinker centred at (cx, cy).
function placeBlinker(e, cx, cy) {
    e.grid.set(cx, cy - 1, 1);
    e.grid.set(cx, cy, 1);
    e.grid.set(cx, cy + 1, 1);
}

(:test)
function testLifeBlinkerOscillates(logger) {
    // Whole generation per step (rowsPerStep = h).
    var e = makeEmptyLife(10, 10, 10);
    placeBlinker(e, 5, 5);

    e.step(null); // vertical -> horizontal
    Test.assertEqual(e.grid.get(4, 5), 1);
    Test.assertEqual(e.grid.get(5, 5), 1);
    Test.assertEqual(e.grid.get(6, 5), 1);
    Test.assertEqual(e.grid.get(5, 4), 0);
    Test.assertEqual(e.grid.get(5, 6), 0);
    Test.assertEqual(e.grid.population(), 3);

    e.step(null); // horizontal -> vertical again
    Test.assertEqual(e.grid.get(5, 4), 1);
    Test.assertEqual(e.grid.get(5, 5), 1);
    Test.assertEqual(e.grid.get(5, 6), 1);
    Test.assertEqual(e.grid.population(), 3);
    return true;
}

(:test)
function testLifeBandedMatchesWhole(logger) {
    // The same pattern evolved whole-grid and in 3-row bands must agree once
    // the banded engine completes a full generation.
    var whole = makeEmptyLife(12, 9, 9);  // one step() = one generation
    var banded = makeEmptyLife(12, 9, 3); // one generation = 3 step() calls
    placeBlinker(whole, 6, 4);
    placeBlinker(banded, 6, 4);

    whole.step(null);
    banded.step(null); // rows 0-2
    banded.step(null); // rows 3-5
    banded.step(null); // rows 6-8 -> swap

    for (var y = 0; y < 9; y++) {
        for (var x = 0; x < 12; x++) {
            Test.assertEqual(whole.grid.get(x, y), banded.grid.get(x, y));
        }
    }
    return true;
}

(:test)
function testLifeBlockIsStill(logger) {
    // A 2x2 block is a still life under B3/S23.
    var e = makeEmptyLife(8, 8, 8);
    e.grid.set(3, 3, 1); e.grid.set(4, 3, 1);
    e.grid.set(3, 4, 1); e.grid.set(4, 4, 1);
    e.step(null);
    Test.assertEqual(e.grid.get(3, 3), 1);
    Test.assertEqual(e.grid.get(4, 3), 1);
    Test.assertEqual(e.grid.get(3, 4), 1);
    Test.assertEqual(e.grid.get(4, 4), 1);
    Test.assertEqual(e.grid.population(), 4);
    return true;
}

(:test)
function testLifeRuleMasksAreConfig(logger) {
    // B1/S- (every empty cell with exactly 1 neighbour is born, nothing
    // survives): a single live cell dies but births its 8 neighbours.
    var e = new LifeEngine({
        :w => 8, :h => 8, :seed => 1,
        :birth => (1 << 1), :survive => 0,
        :rowsPerStep => 8, :density => 0
    });
    e.grid.clear();
    e.grid.set(4, 4, 1);
    e.step(null);
    Test.assertEqual(e.grid.get(4, 4), 0); // died (survive mask empty)
    Test.assertEqual(e.grid.get(3, 3), 1); // born (exactly 1 neighbour)
    Test.assertEqual(e.grid.get(5, 5), 1);
    Test.assertEqual(e.grid.population(), 8);
    return true;
}

(:test)
function testLifeSerializeRoundTrip(logger) {
    var e = makeEmptyLife(16, 12, 12);
    placeBlinker(e, 8, 6);
    var saved = e.serialize();

    var e2 = makeEmptyLife(16, 12, 12);
    Test.assert(e2.applySerialized(saved));
    Test.assertEqual(e2.grid.population(), 3);
    Test.assertEqual(e2.grid.get(8, 5), 1);
    Test.assertEqual(e2.grid.get(8, 6), 1);
    Test.assertEqual(e2.grid.get(8, 7), 1);
    return true;
}
