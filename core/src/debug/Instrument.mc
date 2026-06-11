using Toybox.System as Sys;
using Toybox.Graphics as Gfx;

// Instrument — build-flag-gated debug overlay + logging.
//
// Two definitions of the SAME module symbol exist:
//   - the (:debug) version below does real work,
//   - the (:release) version is zero-cost stubs,
// and the active jungle's excludeAnnotations strips one. Because the stubs share
// the call signatures, call sites never need their own guards.
//
// There is NO peak-memory field in System.getSystemStats at any API level, so we
// track the high-water mark ourselves by sampling usedMemory each tick.

(:debug)
module Instrument {
    var _peakUsed = 0;
    var _frameMs = 0;
    var _tickStartMs = 0;

    function tickStart() {
        _tickStartMs = Sys.getTimer();
    }

    function tickEnd() {
        _frameMs = Sys.getTimer() - _tickStartMs;
        sample();
    }

    function sample() {
        var st = Sys.getSystemStats();
        if (st != null && st has :usedMemory && st.usedMemory > _peakUsed) {
            _peakUsed = st.usedMemory;
        }
    }

    function peakUsed() { return _peakUsed; }
    function frameMs() { return _frameMs; }

    // Draw a one-line overlay at the bottom: used/total KB, peak KB, frame ms.
    function overlay(dc) {
        var st = Sys.getSystemStats();
        var used = (st != null && st has :usedMemory) ? st.usedMemory : 0;
        var total = (st != null && st has :totalMemory) ? st.totalMemory : 0;
        var msg = (used / 1024) + "/" + (total / 1024) + "K p" +
                  (_peakUsed / 1024) + " " + _frameMs + "ms";
        dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawText(dc.getWidth() / 2, dc.getHeight() - 18,
                    Gfx.FONT_XTINY, msg, Gfx.TEXT_JUSTIFY_CENTER);
        log(msg);
    }

    function log(msg) {
        Sys.println(msg);
    }
}

(:release)
module Instrument {
    function tickStart() {}
    function tickEnd() {}
    function sample() {}
    function peakUsed() { return 0; }
    function frameMs() { return 0; }
    function overlay(dc) {}
    function log(msg) {}
}
