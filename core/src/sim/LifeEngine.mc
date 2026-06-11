using Toybox.Graphics as Gfx;

// LifeEngine — reference SimEngine implementation: Conway-family cellular
// automata over a BitGrid.
//
// SimEngine contract (duck-typed, enforced by convention, see docs/architecture.md):
//   initialize(opts)                       construct + seed
//   step(inputs)                           advance stepsPerTick generations
//   render(dc, originX, originY, cellSize)  draw live cells
//   serialize() / applySerialized(arr)     minimal-state persistence
//
// Rules are CONFIG, not code: birthMask/surviveMask are bitmasks where bit k
// means "this transition applies when the cell has exactly k live neighbours".
// Classic Conway B3/S23 => birth = 1<<3, survive = (1<<2)|(1<<3).
class LifeEngine {
    var grid;
    var _prng;
    var _birthMask;
    var _surviveMask;
    var stepsPerTick;
    var _useAge;
    var _seed;
    var _rowsPerStep; // rows of one generation computed per step() call
    var _scanRow;     // next row to compute into _nxt (incremental evolve cursor)

    // opts keys (all optional except sizing):
    //   :w, :h            grid dimensions (required)
    //   :seed             PRNG seed (0/null => time-independent default)
    //   :birth, :survive  rule bitmasks (default B3/S23)
    //   :steps            generations advanced per step() call (default 1)
    //   :age              track 2-bit cell age for rendering ramps (default false)
    //   :density          initial random fill % (default 30)
    //   :rowsPerStep      rows evolved per step() (default = h, i.e. a whole
    //                     generation in one tick). Set < h to spread a single
    //                     generation across multiple onUpdates and stay under the
    //                     watch-face watchdog on large grids. A full generation
    //                     then takes ceil(h / rowsPerStep) ticks. While a
    //                     generation is mid-scan, _cur is held fixed and _nxt is
    //                     filled; the buffers swap only when the scan completes,
    //                     so Conway correctness is preserved.
    function initialize(opts) {
        var w = opts.get(:w);
        var h = opts.get(:h);
        _seed = opts.hasKey(:seed) ? opts.get(:seed) : 0;
        _birthMask = opts.hasKey(:birth) ? opts.get(:birth) : (1 << 3);
        _surviveMask = opts.hasKey(:survive) ? opts.get(:survive) : ((1 << 2) | (1 << 3));
        stepsPerTick = opts.hasKey(:steps) ? opts.get(:steps) : 1;
        _useAge = opts.hasKey(:age) ? opts.get(:age) : false;
        _rowsPerStep = opts.hasKey(:rowsPerStep) ? opts.get(:rowsPerStep) : h;
        _scanRow = 0;
        var density = opts.hasKey(:density) ? opts.get(:density) : 30;

        _prng = new Prng(_seed);
        grid = new BitGrid(w, h, _useAge);
        grid.randomize(_prng, density);
    }

    // Reseed to the initial conditions (used when persistence is off).
    function reseed(density) {
        _prng = new Prng(_seed);
        grid.randomize(_prng, density);
        _scanRow = 0;
    }

    // Advance the automaton. `inputs` is a Dictionary; the generic external hook
    // is :stepDelta (e.g. step-count change since last tick) which "rains" that
    // many random live cells into the grid before evolving. Keeps the data-layer
    // coupling generic — any Number-valued signal can drive it.
    //
    // With incremental evolve, one step() computes up to stepsPerTick*rowsPerStep
    // rows; a buffer swap (generation boundary) happens when the scan reaches the
    // bottom. Rain is injected only at a generation boundary so it never mutates
    // _cur mid-scan.
    function step(inputs) {
        var h = grid.h;
        var budget = stepsPerTick * _rowsPerStep;
        for (var done = 0; done < budget; ) {
            if (_scanRow == 0 && inputs != null && inputs.hasKey(:stepDelta)) {
                var d = inputs.get(:stepDelta);
                if (d != null && d > 0) { rain(d > 16 ? 16 : d); }
                inputs = null; // rain once per step() call, at the boundary
            }
            var count = _rowsPerStep;
            if (_scanRow + count > h) { count = h - _scanRow; }
            evolveBand(_scanRow, count);
            _scanRow += count;
            done += count;
            if (_scanRow >= h) {
                grid.swap();
                _scanRow = 0;
            }
        }
    }

    // Inject `count` random live cells into the current generation.
    function rain(count) {
        for (var i = 0; i < count; i++) {
            var x = _prng.nextInt(grid.w);
            var y = _prng.nextInt(grid.h);
            grid.set(x, y, 1);
        }
    }

    // Compute rows [startRow, startRow+count) of the next generation into _nxt.
    // Hot path. Inlined bit reads (no per-cell function calls) and age folded
    // into the single pass — interpreted Monkey C makes function-call overhead
    // the dominant cost, and the watchdog kills a slow onUpdate. We reach into
    // the BitGrid's word arrays directly (Monkey C members are public). The
    // caller (step) swaps buffers only after the final band completes.
    function evolveBand(startRow, count) {
        var w = grid.w;
        var h = grid.h;
        var wpr = grid._wpr;
        var cur = grid._cur;
        var nxt = grid._nxt; // zeroed by the previous swap()
        var bm = _birthMask;
        var sm = _surviveMask;
        var age = _useAge ? grid._age : null;
        var wprAge = grid._wprAge;
        var yEnd = startRow + count;

        for (var y = startRow; y < yEnd; y++) {
            var ym = (y == 0) ? (h - 1) : (y - 1);
            var yp = (y == h - 1) ? 0 : (y + 1);
            var rB = y * wpr;
            var rU = ym * wpr;
            var rD = yp * wpr;
            var rAge = y * wprAge;
            for (var x = 0; x < w; x++) {
                var xm = (x == 0) ? (w - 1) : (x - 1);
                var xp = (x == w - 1) ? 0 : (x + 1);
                var cm = xm >> 5; var bm5 = xm & 31;
                var c0 = x  >> 5; var b0  = x  & 31;
                var cp = xp >> 5; var bp5 = xp & 31;

                var n =
                    ((cur[rU + cm] >> bm5) & 1) +
                    ((cur[rU + c0] >> b0)  & 1) +
                    ((cur[rU + cp] >> bp5) & 1) +
                    ((cur[rB + cm] >> bm5) & 1) +
                    ((cur[rB + cp] >> bp5) & 1) +
                    ((cur[rD + cm] >> bm5) & 1) +
                    ((cur[rD + c0] >> b0)  & 1) +
                    ((cur[rD + cp] >> bp5) & 1);

                var alive = (cur[rB + c0] >> b0) & 1;
                var live = (alive != 0) ? ((sm >> n) & 1) : ((bm >> n) & 1);

                if (live != 0) {
                    // nxt word starts at 0; only need to OR in live bits.
                    nxt[rB + c0] = nxt[rB + c0] | (1 << b0);
                }
                if (age != null) {
                    var ai = rAge + (x >> 4);
                    var ash = (x & 15) << 1;
                    var old = (age[ai] >> ash) & 0x3;
                    var na = (live != 0) ? ((old < 3) ? (old + 1) : 3) : 0;
                    age[ai] = (age[ai] & (~(0x3 << ash))) | (na << ash);
                }
            }
        }
        // No swap here: step() swaps once the whole generation is computed.
    }

    // Render live cells as filled squares. originX/Y is the top-left pixel of
    // cell (0,0); cellSize is the pixel edge. `keepOut`, if non-null, is a flat
    // [x,y,w,h] pixel rect that live cells will not draw into (mask utility).
    function render(dc, originX, originY, cellSize) {
        renderMasked(dc, originX, originY, cellSize, null);
    }

    function renderMasked(dc, originX, originY, cellSize, keepOut) {
        var w = grid.w;
        var h = grid.h;
        var wpr = grid._wpr;
        var cur = grid._cur;
        var age = _useAge ? grid._age : null;
        var wprAge = grid._wprAge;

        // Resolve the keep-out once to an inclusive cell range to skip, instead
        // of testing every live cell against a pixel rect.
        var kc0 = -1; var kr0 = -1; var kc1 = -1; var kr1 = -1;
        if (keepOut != null) {
            var rng = Region.clampCellRange(keepOut, originX, originY, cellSize, w, h);
            if (rng != null) { kc0 = rng[0]; kr0 = rng[1]; kc1 = rng[2]; kr1 = rng[3]; }
        }

        // Draw horizontal RUNS of same-color live cells as single rectangles,
        // skipping empty words (32 cells) and empty nibbles (4 cells) without
        // per-cell work. Two reasons, both watchdog-driven (~25-30k VM
        // instructions per onUpdate on this device class):
        //   - fillRectangle calls are capped, so adjacent live cells merge into
        //     one draw call (runs break on dead cells, colour change, keep-out);
        //   - a naive 1200-iteration per-cell scan alone blows the budget, so
        //     dead space costs ~1 instruction per 32 (or 4) cells instead.
        var lastColor = -1;
        for (var y = 0; y < h; y++) {
            var py = originY + y * cellSize;
            var rB = y * wpr;
            var rAge = y * wprAge;
            var inKeepRow = (y >= kr0 && y <= kr1);
            var runStart = -1;   // x where the current run began (-1 = none)
            var runColor = -1;
            for (var c = 0; c < wpr; c++) {
                var word = cur[rB + c];
                if (word == 0) {
                    // 32 dead cells: flush any run and skip.
                    if (runStart >= 0) {
                        lastColor = flushRun(dc, originX, py, cellSize,
                                             runStart, c << 5, runColor, lastColor);
                        runStart = -1; runColor = -1;
                    }
                    continue;
                }
                var xBase = c << 5;
                var bits = (xBase + 32 <= w) ? 32 : (w - xBase);
                for (var nib = 0; nib < bits; nib += 4) {
                    var nv = (word >> nib) & 0xF;
                    if (nv == 0) {
                        // 4 dead cells: flush and skip.
                        if (runStart >= 0) {
                            lastColor = flushRun(dc, originX, py, cellSize,
                                                 runStart, xBase + nib, runColor, lastColor);
                            runStart = -1; runColor = -1;
                        }
                        continue;
                    }
                    for (var b = 0; b < 4; b++) {
                        var x = xBase + nib + b;
                        var color = -1;
                        if (((nv >> b) & 1) != 0 && x < w &&
                            !(inKeepRow && x >= kc0 && x <= kc1)) {
                            if (age != null) {
                                color = ageColor((age[rAge + (x >> 4)] >> ((x & 15) << 1)) & 0x3);
                            } else {
                                color = Gfx.COLOR_GREEN;
                            }
                        }
                        if (color != runColor) {
                            if (runStart >= 0) {
                                lastColor = flushRun(dc, originX, py, cellSize,
                                                     runStart, x, runColor, lastColor);
                            }
                            runStart = (color >= 0) ? x : -1;
                            runColor = color;
                        }
                    }
                }
            }
            if (runStart >= 0) {
                lastColor = flushRun(dc, originX, py, cellSize,
                                     runStart, w, runColor, lastColor);
            }
        }
    }

    // Emit one merged horizontal run [runStart, xEnd) as a single rectangle.
    // Returns the colour now active on the dc (setColor calls are deduped).
    function flushRun(dc, originX, py, cellSize, runStart, xEnd, runColor, lastColor) {
        if (runColor != lastColor) {
            dc.setColor(runColor, Gfx.COLOR_TRANSPARENT);
            lastColor = runColor;
        }
        dc.fillRectangle(originX + runStart * cellSize, py,
                         (xEnd - runStart) * cellSize, cellSize);
        return lastColor;
    }

    // Map a 2-bit age to a debug color ramp (no design intent — function only).
    function ageColor(age) {
        if (age >= 3) { return Gfx.COLOR_WHITE; }
        if (age == 2) { return Gfx.COLOR_GREEN; }
        if (age == 1) { return Gfx.COLOR_DK_GREEN; }
        return Gfx.COLOR_DK_GRAY;
    }

    // --- persistence ---------------------------------------------------------
    function serialize() { return grid.serialize(); }
    function applySerialized(arr) { return grid.deserialize(arr); }
}
