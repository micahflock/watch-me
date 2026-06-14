using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;

// BioBloomView — the living-dish biometric art (parity reference:
// sketches/algos/biobloom.py). One full-screen component, the BioBloom dish,
// plus the debug overlay. No clock yet — the dish fills the screen; a small
// time readout is the next step.
class BioBloomView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _bloom;

    function initialize() {
        WatchFace.initialize();
    }

    // Allocate everything ONCE (lifecycle contract; zero per-tick allocation).
    function onLayout(dc) {
        GenArt.initSinTable();
        _state = new Snapshot();
        _bloom = new BioBloom();

        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(_bloom, null);
        _compositor.add(new BioDebugComponent(), null);
    }

    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _bloom.advance(_state);
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }

    function onSettingsChanged() {}
}

// Duck-typed component: prints the (:debug) memory/timing overlay; no-op in
// release builds.
class BioDebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc);
    }
}
