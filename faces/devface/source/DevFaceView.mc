using Toybox.WatchUi as Ui;
using Toybox.Application as App;
using Toybox.Graphics as Gfx;
using Toybox.System as Sys;

// DevFaceView — the integration testbed face. Zero styling effort: it proves the
// whole stack composes and stays within the memory ceiling. Debug colors only.
//
// Layout (215x180 semiround):
//   - procedural 7-segment HH:MM (SegmentFont/Layout) upper-center
//   - day-of-week + DD date line below it (segment digits)
//   - a Conway Life region (>=40x30) filling the lower area, fed by step delta,
//     masked out of the clock's keep-out rect
//   - (:debug) instrumentation overlay at the very bottom
class DevFaceView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _life;
    var _segParams;
    var _segs;
    var _clockKeepOut; // reserved rect [x,y,w,h] the sim won't draw into

    // Life grid geometry (cells). >=40x30 per acceptance criteria.
    const GRID_W = 40;
    const GRID_H = 30;
    const CELL = 3;
    // Spread one generation across several onUpdates so a 40x30 generation stays
    // under the watch-face watchdog. Measured budget (sim, fr735xt profile):
    // ~25-30k VM instructions per onUpdate; a full 1200-cell generation plus a
    // full-grid render does not fit. With 5 rows/step a generation completes
    // every ceil(30/5) = 6 ticks (6 minutes at watch-face cadence).
    const ROWS_PER_STEP = 5;
    // Initial random fill. Life settles to ~5% live anyway, and fewer live
    // cells keep the render scan within the instruction budget.
    const SEED_DENSITY = 15;

    function initialize() {
        WatchFace.initialize();
    }

    // Allocate everything ONCE. onLayout has a valid Dc for sizing.
    function onLayout(dc) {
        _state = new Snapshot();

        // Procedural digit metrics tuned to fit 215px wide with HH:MM.
        _segParams = SegmentFont.makeParams(46, 6, 3, 4);
        _segs = SegmentFont.buildSegments(_segParams);

        // Reserve the top area for the clock so Life doesn't draw under it.
        _clockKeepOut = [0, 0, dc.getWidth(), 86];

        // Generative engine: Life with age ramp, fed by step deltas.
        var app = App.getApp();
        _life = new LifeEngine({
            :w => GRID_W, :h => GRID_H,
            :seed => DataSource.simSeed(),
            :steps => 1,
            :rowsPerStep => ROWS_PER_STEP,
            :age => false, // single colour => maximal horizontal run merging
            :density => SEED_DENSITY
        });
        // Restore persisted state if enabled and present.
        if (DataSource.simPersist()) {
            var saved = app.loadSimState();
            if (saved != null) { _life.applySerialized(saved); }
        }

        buildCompositor(dc);
    }

    function buildCompositor(dc) {
        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        // Order matters: Life first (background), then clock/date on top.
        _compositor.addKeepOut(_clockKeepOut);
        _compositor.add(new LifeComponent(_life, _clockKeepOut,
            centerX(dc) - (GRID_W * CELL) / 2, 90, CELL), null);
        _compositor.add(new ClockComponent(_segs, _segParams, centerX(dc)), null);
        _compositor.add(new DateComponent(centerX(dc)), null);
        _compositor.add(new DebugComponent(), null);
    }

    function centerX(dc) { return dc.getWidth() / 2; }

    // Full redraw — once per minute in low power.
    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);

        // Drive the generative layer from a data-layer signal (external hook).
        var delta = DataSource.stepDelta(_state);
        _life.step({ :stepDelta => delta });
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }
    // onPartialUpdate intentionally omitted: fr735xt has no hardware support.

    function onSettingsChanged() {
        // Reseed if persistence is off and seed changed; cheap to just reseed.
        if (!DataSource.simPersist()) {
            _life.reseed(SEED_DENSITY);
        }
    }

    function serializeSim() {
        return (_life != null) ? _life.serialize() : null;
    }
}

// --- Components (duck-typed: each has render(dc, state)) ---------------------

class LifeComponent {
    var _life; var _keepOut; var _ox; var _oy; var _cell;
    function initialize(life, keepOut, ox, oy, cell) {
        _life = life; _keepOut = keepOut; _ox = ox; _oy = oy; _cell = cell;
    }
    function render(dc, state) {
        _life.renderMasked(dc, _ox, _oy, _cell, _keepOut);
    }
}

class ClockComponent {
    var _segs; var _params; var _cx;
    function initialize(segs, params, cx) { _segs = segs; _params = params; _cx = cx; }
    function render(dc, state) {
        var h = (state.hour != null) ? state.hour : 0;
        var m = (state.minute != null) ? state.minute : 0;
        SegmentLayout.drawClock(dc, _segs, _params, _cx, 18, h, m,
            Gfx.COLOR_WHITE, null);
    }
}

class DateComponent {
    var _cx;
    var _dow = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
    function initialize(cx) { _cx = cx; }
    function render(dc, state) {
        var label = "--";
        if (state.dayOfWeek != null && state.dayOfWeek >= 1 && state.dayOfWeek <= 7) {
            label = _dow[state.dayOfWeek - 1];
        }
        var day = (state.day != null) ? state.day.format("%02d") : "--";
        dc.setColor(Gfx.COLOR_LT_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawText(_cx, 66, Gfx.FONT_SMALL, label + " " + day,
            Gfx.TEXT_JUSTIFY_CENTER);
    }
}

class DebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc); // no-op in release builds
    }
}
