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
//   - a sun-compass rose (point 12 at the sun -> red needle = true north)
//   - (:debug) instrumentation overlay at the very bottom
class DevFaceView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _segParams;
    var _segs;

    // Sun-compass rose: radius and center-y (center-x is the screen center).
    const ROSE_R = 24;
    const ROSE_CY = 134;

    function initialize() {
        WatchFace.initialize();
    }

    // Allocate everything ONCE. onLayout has a valid Dc for sizing.
    function onLayout(dc) {
        _state = new Snapshot();

        // Procedural digit metrics tuned to fit 215px wide with HH:MM.
        _segParams = SegmentFont.makeParams(46, 6, 3, 4);
        _segs = SegmentFont.buildSegments(_segParams);

        buildCompositor(dc);
    }

    function buildCompositor(dc) {
        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(new ClockComponent(_segs, _segParams, centerX(dc)), null);
        _compositor.add(new DateComponent(centerX(dc)), null);
        _compositor.add(new SunCompassComponent(centerX(dc), ROSE_CY, ROSE_R), null);
        _compositor.add(new DebugComponent(), null);
    }

    function centerX(dc) { return dc.getWidth() / 2; }

    // Full redraw — once per minute in low power.
    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }
    // onPartialUpdate intentionally omitted: fr735xt has no hardware support.

    function onSettingsChanged() {}
}

// --- Components (duck-typed: each has render(dc, state)) ---------------------

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

class SunCompassComponent {
    var _rose; var _cx; var _cy; var _r;
    function initialize(cx, cy, r) {
        _rose = new CompassRose();
        _cx = cx; _cy = cy; _r = r;
    }
    function render(dc, state) {
        var res = SunCompass.compute(state.year, state.month, state.day,
            state.hour, state.minute, state.utcOffsetSec, state.lat, state.lon);
        if (res == null) {
            _rose.drawUnknown(dc, _cx, _cy, _r); // no location/clock yet
            return;
        }
        // Sightable: above the horizon (same -0.833 disc/refraction limb as
        // sunrise) and below ~80 deg elevation, where azimuth degenerates and
        // a near-zenith sun can't be aimed at anyway.
        var bright = (res[1] > -0.833 && res[1] < 80.0);
        _rose.draw(dc, _cx, _cy, _r, res[0], bright);
    }
}

class DebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc); // no-op in release builds
    }
}
