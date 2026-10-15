using Toybox.Graphics as Gfx;
using Toybox.Activity as Activity;
using Toybox.ActivityMonitor as Act;
using Toybox.Position as Position;
using Toybox.Time as Time;
using Toybox.Application as App;
using Toybox.Math as Math;

// Diag -- the two-worlds-v2 on-wrist diagnostic readout (diag build only:
// scripts/build.sh two-worlds-v2 --diag -> bin/two-worlds-v2-diag.prg). Same
// app id as the face, so it reads the face's real saved record; sideload it
// IN PLACE of two-worlds-v2.prg, swap back when done.
//
// Even minutes: the normal face. Odd minutes: the moss is skipped (keeps the
// watchdog budget for the readout) and the field shows
//   A:  Activity.Info.currentLocation  (lat,lon + accuracy, or null/-)
//   P:  Position.getInfo().position    (needs the diag manifest's
//       Positioning permission; ERR if the device refuses it)
//   fix: DataSource's remembered fix -> pip state, stamp age, lat/lng
//        settings set Y/N, n = valid HR-history samples in the last 3 h
//   gap: the last minute gap the grove replayed: length, history Y/N,
//        when, HR on return
//   e:  the biggest episode: duration, bead radius, slot level, peak slots
//   a 3-hour HR history sparkline (one column per minute, zone colours,
//   gray line = 105 bpm), blue tick under the last replayed gap.
module Diag {
    const KEY = "diagGap";
    var _g = null;

    function wrapGrove(grove) {
        _g = grove;
        try {                                   // last gap survives a reload
            var a = App.getApp().getProperty(KEY);
            if (a instanceof Toybox.Lang.Array && a.size() == 4) {
                grove._dGap = a[0]; grove._dHist = (a[1] == 1);
                grove._dAt = a[2]; grove._dHr = (a[3] < 0) ? null : a[3];
            }
        } catch (e) {
        }
        return new DiagGrove(grove);
    }

    function component() { return new DiagComponent(); }

    function save(grove) {
        try {
            App.getApp().setProperty(KEY, [grove._dGap, grove._dHist ? 1 : 0,
                grove._dAt, (grove._dHr == null) ? -1 : grove._dHr]);
        } catch (e) {
        }
    }

    function page(state) {
        return state.minute != null && (state.minute % 2) == 1;
    }
}

class DiagGrove {
    var _g;
    function initialize(g) { _g = g; }
    function render(dc, state) {
        if (!Diag.page(state)) { _g.render(dc, state); }
    }
}

class DiagComponent {
    const W = 180;             // sparkline columns = minutes of history
    const H = 22;              // sparkline height (px) for HR 40..200
    var _col;

    function initialize() { _col = new [W]; }

    function render(dc, state) {
        if (!Diag.page(state)) { return; }
        var g = Diag._g;
        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_BLACK);
        dc.fillRectangle(14, 63, 188, 102);
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        var f = Gfx.FONT_XTINY;
        var lh = dc.getFontHeight(f) - 2;
        var n = history(state);
        var y = 63;
        dc.drawText(18, y, f, "A:" + locA(), Gfx.TEXT_JUSTIFY_LEFT);
        y += lh;
        dc.drawText(18, y, f, "P:" + locP(), Gfx.TEXT_JUSTIFY_LEFT);
        y += lh;
        dc.drawText(18, y, f, fixLine(state) + " n" + n, Gfx.TEXT_JUSTIFY_LEFT);
        y += lh;
        dc.drawText(18, y, f, gapLine(g), Gfx.TEXT_JUSTIFY_LEFT);
        y += lh;
        dc.drawText(18, y, f, epLine(g), Gfx.TEXT_JUSTIFY_LEFT);
        sparkline(dc, g, state);
    }

    function fmt(v) { return v.format("%.2f"); }

    function locA() {
        try {
            var info = Activity.getActivityInfo();
            if (info == null) { return "-"; }
            if (!(info has :currentLocation)) { return "n/a"; }
            var loc = info.currentLocation;
            if (loc == null) { return "null"; }
            var d = loc.toDegrees();
            var q = (info has :currentLocationAccuracy)
                    ? info.currentLocationAccuracy : "?";
            return fmt(d[0]) + "," + fmt(d[1]) + " q" + q;
        } catch (e) {
            return "ERR";
        }
    }

    function locP() {
        try {
            var pi = Position.getInfo();
            if (pi == null) { return "-"; }
            if (pi.position == null) { return "null q" + pi.accuracy; }
            var d = pi.position.toDegrees();
            return fmt(d[0]) + "," + fmt(d[1]) + " q" + pi.accuracy;
        } catch (e) {
            return "ERR";
        }
    }

    function fixLine(state) {
        var s = ["none", "stale", "fresh"];
        var st = (state.gpsFix != null) ? s[state.gpsFix] : "?";
        var age = "st0";
        if (DataSource._gStamp > 0) {
            age = ((Time.now().value() - DataSource._gStamp) / 3600) + "h";
        }
        return "fix:" + st + " " + age + " set:"
            + ((DataSource._lat != null) ? "Y" : "N");
    }

    function gapLine(g) {
        if (g._dAt < 0) { return "gap: none seen"; }
        return "gap:" + g._dGap + "m hist:" + (g._dHist ? "Y" : "N")
            + " @" + (g._dAt / 60) + ":" + (g._dAt % 60).format("%02d")
            + " hr" + ((g._dHr == null) ? "-" : g._dHr.toString());
    }

    function epLine(g) {
        if (g._nepi == 0) { return "e: none"; }
        var bi = 0;
        for (var i = 1; i < g._nepi; i++) {
            if (g._emag[i] > g._emag[bi]) { bi = i; }
        }
        var mag = g._emag[bi];
        var bead = (mag >= 529) ? 24 : 1 + Math.sqrt(mag).toNumber();
        var b = g._eband[bi];
        var lv = (b >> 24) & 15;
        var d = g._edur[bi];
        var sl = "";
        if (d > 0) {
            var ns = ((d - 1) >> lv) + 1;
            for (var k = 0; k < ns; k++) { sl += ((b >> (4 * k)) & 15).toString(); }
        }
        return "e" + (bi + 1) + "/" + g._nepi + " d" + d + " r" + bead
            + " L" + lv + " [" + sl + "]";
    }

    // Fill _col with the max HR per minute over the last W minutes; returns
    // the valid sample count (-1 if the history read threw).
    function history(state) {
        for (var i = 0; i < W; i++) { _col[i] = 0; }
        var n = 0;
        try {
            var nowSec = Time.now().value();
            var it = Act.getHeartRateHistory(new Time.Duration(W * 60), false);
            var smp = (it != null) ? it.next() : null;
            var guard = 0;
            while (smp != null && guard < 400) {
                guard++;
                var hr = smp.heartRate;
                if (smp.when != null && hr != null && hr > 0 && hr < 255) {
                    var age = (nowSec - smp.when.value()) / 60;
                    n++;
                    var x = W - 1 - age;
                    if (x >= 0 && x < W && hr > _col[x]) { _col[x] = hr; }
                }
                smp = it.next();
            }
        } catch (e) {
            return -1;
        }
        return n;
    }

    function sparkline(dc, g, state) {
        var x0 = 18;
        var yb = 158;                      // HR 40 at the bottom, 200 at yb-H
        dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
        var y105 = yb - ((105 - 40) * H) / 160;
        dc.drawLine(x0, y105, x0 + W, y105);
        var last = -2;
        for (var i = 0; i < W; i++) {
            var hr = _col[i];
            if (hr <= 0) { continue; }
            var z = g.hrZone(hr);
            if (z != last) {
                dc.setColor(g.zoneColor(z), Gfx.COLOR_TRANSPARENT);
                last = z;
            }
            var yy = yb - ((hr - 40) * H) / 160;
            if (yy < yb - H) { yy = yb - H; }
            dc.drawPoint(x0 + i, yy);
        }
        // the last replayed gap, as a blue bar under the minutes it covered
        if (g._dAt >= 0 && state.hour != null) {
            var now = state.hour * 60 + state.minute;
            var a = W - 1 - (now - (g._dAt - g._dGap));
            var b = W - 1 - (now - g._dAt);
            if (a < 0) { a = 0; }
            if (b >= 0 && a < W) {
                dc.setColor(Gfx.COLOR_BLUE, Gfx.COLOR_TRANSPARENT);
                dc.fillRectangle(x0 + a, yb + 2, b - a + 1, 2);
            }
        }
    }
}
