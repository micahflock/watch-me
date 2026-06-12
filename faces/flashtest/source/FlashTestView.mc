using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;
using Toybox.System as Sys;

// FlashTestView — visually unmistakable proof that a sideloaded face is the
// one running:
//   - "FLASH OK" banner (green)
//   - HH:MM in the big number font (proves the minute redraw fires)
//   - UPD counter (increments per onUpdate; resets when the app restarts, so a
//     watchdog kill / crash loop shows up as a counter stuck at small values)
//   - battery % (proves getSystemStats works on hardware)
// Everything here is CIQ 1.x/2.x-safe; no Math.*, no properties, no bitmaps.
class FlashTestView extends Ui.WatchFace {

    var _updates;

    function initialize() {
        WatchFace.initialize();
        _updates = 0;
    }

    function onLayout(dc) {
    }

    function onUpdate(dc) {
        _updates += 1;
        var cx = dc.getWidth() / 2;
        var cy = dc.getHeight() / 2;

        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_BLACK);
        dc.clear();

        dc.setColor(Gfx.COLOR_GREEN, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 12, Gfx.FONT_MEDIUM, "FLASH OK",
            Gfx.TEXT_JUSTIFY_CENTER);

        var t = Sys.getClockTime();
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, cy, Gfx.FONT_NUMBER_HOT,
            t.hour.format("%02d") + ":" + t.min.format("%02d"),
            Gfx.TEXT_JUSTIFY_CENTER | Gfx.TEXT_JUSTIFY_VCENTER);

        var batt = "--";
        var stats = Sys.getSystemStats();
        if (stats != null && stats.battery != null) {
            batt = stats.battery.toNumber().format("%d") + "%";
        }
        dc.setColor(Gfx.COLOR_LT_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 142, Gfx.FONT_SMALL,
            "BATT " + batt + "   UPD " + _updates,
            Gfx.TEXT_JUSTIFY_CENTER);
    }

    function onEnterSleep() {
    }

    function onExitSleep() {
        Ui.requestUpdate();
    }
    // onPartialUpdate intentionally omitted: fr735xt has no hardware support.
}
