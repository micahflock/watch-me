using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;

// StrataFlockView — biometric algorithmic art (docs in sketches/README.md,
// concept 4). Bottom: StrataField, the day accreting as colored sediment.
// Sky: Flock, a murmuration living in the present minute. A small 7-seg
// clock sits top-center; the flock treats its rect as a keep-out, so the
// time floats in a hole the birds avoid.
//
// Render order matters: strata (back), flock, clock, debug overlay.
class StrataFlockView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _segParams;
    var _segs;
    var _field;

    function initialize() {
        WatchFace.initialize();
    }

    // Allocate everything ONCE (lifecycle contract; zero per-tick allocation).
    function onLayout(dc) {
        GenArt.initSinTable();
        _state = new Snapshot();

        _segParams = SegmentFont.makeParams(30, 4, 2, 3);
        _segs = SegmentFont.buildSegments(_segParams);
        var cx = dc.getWidth() / 2;
        var halfW = SegmentLayout.clockWidth(_segParams) / 2;
        var keep = [cx - halfW - 5, 0, cx + halfW + 5, 46];

        _field = new StrataField();

        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(_field, null);
        _compositor.add(new Flock(_field, keep), null);
        _compositor.add(new SkyClockComponent(_segs, _segParams, cx), null);
        _compositor.add(new ArtDebugComponent(), null);
    }

    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _field.advance(_state);
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }

    function onSettingsChanged() {}
}

// --- Components (duck-typed: each has render(dc, state)) --------------------

class SkyClockComponent {
    var _segs;
    var _params;
    var _cx;
    function initialize(segs, params, cx) {
        _segs = segs;
        _params = params;
        _cx = cx;
    }
    function render(dc, state) {
        var h = (state.hour != null) ? state.hour : 0;
        var m = (state.minute != null) ? state.minute : 0;
        SegmentLayout.drawClock(dc, _segs, _params, _cx, 10, h, m,
            Gfx.COLOR_WHITE, null);
    }
}

class ArtDebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc); // no-op in release builds
    }
}
