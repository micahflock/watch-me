using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;
using Toybox.System as Sys;
using Toybox.Time as Time;
using Toybox.Position as Pos;
using Toybox.Activity as Act;

// GpsProbeView — draws, on the wrist, exactly what Toybox.Position hands a
// WATCH FACE when no activity is running. Everything is on-screen because the
// console does not exist on hardware; the Sys.println calls are for sim runs.
//
// Reading, top to bottom:
//   ACC     Position.getInfo().accuracy as a word. NONE means the device gave
//           this face nothing — no cached fix reaches a watch face, and both
//           the GPS status icon and the GPS-derived sun/north location are off
//           the table. LAST (QUALITY_LAST_KNOWN) is the expected good case: a
//           cached fix from the last GPS activity, which is all the sun compass
//           needs. POOR/USABLE/GOOD would mean a live receiver, which should
//           never appear here (the GPS is off outside activities).
//   lat/lng info.position.toDegrees(), or "no position" when position is null.
//           A watch face can show a fix quality with no coordinates attached,
//           so these are reported separately on purpose.
//   AGE     now - info.when, i.e. how stale the fix is. The sun's azimuth moves
//           ~15 deg/hour but a POSITION hours old is still fine (a few hundred
//           km of error costs a degree or two), so this is about whether `when`
//           means anything at all: the simulator reports "now" with no fix,
//           which would make it useless as a freshness signal.
//   ACT     Activity.getActivityInfo().currentLocation — the second possible
//           source, expected null in a watch face. Reported so a NONE on the
//           Position path doesn't have to be re-probed to rule this out.
//
// CIQ 2.4-safe: no Math, no properties, no bitmaps, integer arithmetic only.
class GpsProbeView extends Ui.WatchFace {

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

        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_BLACK);
        dc.clear();

        dc.setColor(Gfx.COLOR_LT_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 24, Gfx.FONT_XTINY, "GPS PROBE",
            Gfx.TEXT_JUSTIFY_CENTER);

        var info = Pos.getInfo();
        var acc = null;
        var loc = null;
        if (info != null) {
            if (info has :accuracy) { acc = info.accuracy; }
            if (info has :position) { loc = info.position; }
        }

        // --- accuracy: the headline ---
        dc.setColor(accColor(acc), Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 40, Gfx.FONT_MEDIUM, "ACC " + accName(acc),
            Gfx.TEXT_JUSTIFY_CENTER);

        // --- coordinates ---
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        if (loc != null) {
            var d = loc.toDegrees();
            dc.drawText(cx, 72, Gfx.FONT_SMALL, d[0].format("%.4f"),
                Gfx.TEXT_JUSTIFY_CENTER);
            dc.drawText(cx, 92, Gfx.FONT_SMALL, d[1].format("%.4f"),
                Gfx.TEXT_JUSTIFY_CENTER);
            Sys.println("lat " + d[0] + " lng " + d[1]);
        } else {
            dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
            dc.drawText(cx, 82, Gfx.FONT_SMALL, "no position",
                Gfx.TEXT_JUSTIFY_CENTER);
        }

        // --- fix age + the alternate source ---
        dc.setColor(Gfx.COLOR_LT_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 112, Gfx.FONT_XTINY, "age " + fixAge(info)
            + "   act " + actSource(), Gfx.TEXT_JUSTIFY_CENTER);

        // --- clock + update counter: proves the reading above is live ---
        var t = Sys.getClockTime();
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        dc.drawText(cx, 130, Gfx.FONT_SMALL,
            t.hour.format("%02d") + ":" + t.min.format("%02d")
            + "  u" + _updates.format("%d"), Gfx.TEXT_JUSTIFY_CENTER);

        Sys.println("acc " + acc + " pos " + loc + " upd " + _updates);
    }

    // QUALITY_* -> a word that fits the screen. Compared against the constants
    // rather than printed raw so a reading needs no lookup table on the wrist.
    function accName(acc) {
        if (acc == null)                     { return "NULL"; }
        if (acc == Pos.QUALITY_NOT_AVAILABLE) { return "NONE"; }
        if (acc == Pos.QUALITY_LAST_KNOWN)    { return "LAST"; }
        if (acc == Pos.QUALITY_POOR)          { return "POOR"; }
        if (acc == Pos.QUALITY_USABLE)        { return "USABLE"; }
        if (acc == Pos.QUALITY_GOOD)          { return "GOOD"; }
        return "?" + acc.toString();
    }

    function accColor(acc) {
        if (acc == null || acc == Pos.QUALITY_NOT_AVAILABLE) {
            return Gfx.COLOR_DK_GRAY;
        }
        if (acc == Pos.QUALITY_LAST_KNOWN) { return Gfx.COLOR_YELLOW; }
        return Gfx.COLOR_GREEN;
    }

    // Seconds between the fix timestamp and now, as "3h12m" / "45m" / "12s".
    // Both Moments are epoch seconds, so the difference is plain integer math.
    function fixAge(info) {
        if (info == null || !(info has :when) || info.when == null) {
            return "--";
        }
        var now = Time.now();
        if (now == null) { return "--"; }
        var s = now.value() - info.when.value();
        if (s < 0) { return "future"; }
        if (s < 60) { return s.format("%d") + "s"; }
        var m = s / 60;
        if (m < 60) { return m.format("%d") + "m"; }
        var h = m / 60;
        if (h < 24) { return h.format("%d") + "h" + (m % 60).format("%02d") + "m"; }
        return (h / 24).format("%d") + "d" + (h % 24).format("%02d") + "h";
    }

    // The other place a location could come from. Expected "--" in a watch face.
    function actSource() {
        var ai = Act.getActivityInfo();
        if (ai == null) { return "--"; }
        if (!(ai has :currentLocation) || ai.currentLocation == null) {
            return "--";
        }
        return "OK";
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }
}
