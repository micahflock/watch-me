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
// The readout shows ONE minute in ten (:00, :10, :20 ...; owner, 2026-10);
// the other nine are the normal face. On a readout minute the moss is
// skipped (keeps the watchdog budget for the readout) and the field shows,
// top to bottom (amber labels, white values, state words in colour):
//   a 3-hour HR history sparkline across the widest part of the field (one
//   point per minute, zone colours, gray line = 105 bpm), blue bar under
//   the last replayed gap
//   gap: the day's LONGEST minute gap the grove replayed (a workout):
//        length, when, history Y/N, HR on return
//   e:   the biggest episode: index/count, duration, bead radius, slot
//        level, peak slots (each digit in its zone's colour)
//   fix: DataSource's remembered fix -> pip state, stamp age, lat/lng
//        settings set Y/N, n = valid HR-history samples in the last 3 h
//   P:   Position.getInfo().position    (+ the age of its `when` stamp;
//        ERR if the device refuses the Positioning permission)
//   A:   Activity.Info.currentLocation  (lat,lon + accuracy, or null/-)
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
        return state.minute != null && (state.minute % 10) == 0;
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
    const X0 = 18;
    const YB = 89;             // sparkline base (HR 40); HR 200 at YB - H
    const ROW0 = 91;           // first text row (drawText y)
    const PITCH = 13;
    // Left edge of each text row: the border's curve at that row + 4 px.
    // The rows sit lower and lower on the disc, so they are ordered
    // longest-first (gap, e, fix, P, A) and each starts a little further in.
    const ROWX = [18, 20, 26, 33, 44];
    var _col;
    var _row;
    var _x;
    var _y;

    function initialize() { _col = new [W]; }

    // Layout and colours: sketches "D" in archive/sketches/diag_compare.py
    // (owner, 2026-11). Nothing is blacked out -- the moss is skipped on a
    // readout minute, so the field is already empty and the border stays
    // whole; only a breach banner needs clearing from under the readout.
    function render(dc, state) {
        if (!Diag.page(state)) { return; }
        var g = Diag._g;
        if (g.actUnits() >= 4200) {
            dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_BLACK);
            dc.fillRectangle(14, 79, 188, 22);
        }
        var n = history(state);
        sparkline(dc, g, state);
        _row = 0;
        gapRow(dc, g);
        epRow(dc, g);
        fixRow(dc, state, n);
        locP(dc);
        locA(dc);
    }

    // Start the next row with its amber label.
    function begin(dc, label) {
        _x = ROWX[_row];
        _y = ROW0 + _row * PITCH;
        _row++;
        put(dc, 0, label, Gfx.COLOR_YELLOW);
        _x += 3;
    }

    // Draw `text` in `color`, `gap` px after the previous token.
    function put(dc, gap, text, color) {
        _x += gap;
        dc.setColor(color, Gfx.COLOR_TRANSPARENT);
        dc.drawText(_x, _y, Gfx.FONT_XTINY, text, Gfx.TEXT_JUSTIFY_LEFT);
        _x += dc.getTextWidthInPixels(text, Gfx.FONT_XTINY);
    }

    function fmt(v) { return v.format("%.2f"); }

    function locA(dc) {
        begin(dc, "A");
        try {
            var info = Activity.getActivityInfo();
            if (info == null) { put(dc, 0, "-", Gfx.COLOR_LT_GRAY); return; }
            if (!(info has :currentLocation)) {
                put(dc, 0, "n/a", Gfx.COLOR_LT_GRAY);
                return;
            }
            var loc = info.currentLocation;
            if (loc == null) { put(dc, 0, "null", Gfx.COLOR_LT_GRAY); return; }
            var d = loc.toDegrees();
            var q = (info has :currentLocationAccuracy)
                    ? info.currentLocationAccuracy : "?";
            put(dc, 0, fmt(d[0]) + "," + fmt(d[1]), Gfx.COLOR_WHITE);
            put(dc, 4, "q" + q, Gfx.COLOR_LT_GRAY);
        } catch (e) {
            put(dc, 0, "ERR", Gfx.COLOR_RED);
        }
    }

    function locP(dc) {
        begin(dc, "P");
        try {
            var pi = Position.getInfo();
            if (pi == null) { put(dc, 0, "-", Gfx.COLOR_LT_GRAY); return; }
            if (pi.position == null) {
                put(dc, 0, "null", Gfx.COLOR_LT_GRAY);
                put(dc, 4, "q" + pi.accuracy, Gfx.COLOR_LT_GRAY);
                return;
            }
            var d = pi.position.toDegrees();
            put(dc, 0, fmt(d[0]) + "," + fmt(d[1]), Gfx.COLOR_WHITE);
            put(dc, 4, "q" + pi.accuracy, Gfx.COLOR_LT_GRAY);
            if (pi.when != null) {             // the fix's own timestamp, if any
                put(dc, 4, age((Time.now().value() - pi.when.value()) / 60),
                    Gfx.COLOR_LT_GRAY);
            }
        } catch (e) {
            put(dc, 0, "ERR", Gfx.COLOR_RED);
        }
    }

    function age(m) {
        if (m < 0) { return "-" + age(-m); }
        if (m < 120) { return m + "m"; }
        if (m < 2880) { return (m / 60) + "h"; }
        return (m / 1440) + "d";
    }

    // fix: the pip state in the uplink bars' colours (fresh blue, stale
    // amber; none grey), stamp age, lat/lng settings set Y/N, n = valid
    // HR-history samples in the last 3 h (red if the history read threw).
    function fixRow(dc, state, n) {
        begin(dc, "fix");
        var gf = state.gpsFix;
        if (gf == 2) { put(dc, 0, "fresh", Gfx.COLOR_BLUE); }
        else if (gf == 1) { put(dc, 0, "stale", Gfx.COLOR_YELLOW); }
        else { put(dc, 0, (gf == 0) ? "none" : "?", Gfx.COLOR_LT_GRAY); }
        var a = "st0";
        if (DataSource._gStamp > 0) {
            a = ((Time.now().value() - DataSource._gStamp) / 3600) + "h";
        }
        put(dc, 4, a, Gfx.COLOR_WHITE);
        put(dc, 4, "set", Gfx.COLOR_YELLOW);
        put(dc, 2, (DataSource._lat != null) ? "Y" : "N", Gfx.COLOR_WHITE);
        put(dc, 4, "n", Gfx.COLOR_YELLOW);
        put(dc, 0, n.toString(), (n < 0) ? Gfx.COLOR_RED : Gfx.COLOR_WHITE);
    }

    function gapRow(dc, g) {
        begin(dc, "gap");
        if (g._dAt < 0) { put(dc, 0, "none seen", Gfx.COLOR_LT_GRAY); return; }
        put(dc, 0, g._dGap + "m", Gfx.COLOR_BLUE);
        put(dc, 4, "@" + (g._dAt / 60) + ":" + (g._dAt % 60).format("%02d"),
            Gfx.COLOR_WHITE);
        put(dc, 4, "hist", Gfx.COLOR_YELLOW);
        put(dc, 2, g._dHist ? "Y" : "N",
            g._dHist ? Gfx.COLOR_GREEN : Gfx.COLOR_RED);
        put(dc, 4, "hr", Gfx.COLOR_YELLOW);
        var z = g.hrZone(g._dHr);
        if (z < 0) { put(dc, 0, "-", Gfx.COLOR_LT_GRAY); }
        else { put(dc, 0, g._dHr.toString(), g.zoneColor(z)); }
    }

    // The biggest episode: index/count, duration, bead radius, slot level,
    // then its peak-zone slots, each digit in its zone's colour.
    function epRow(dc, g) {
        begin(dc, "e");
        if (g._nepi == 0) { put(dc, 0, "none", Gfx.COLOR_LT_GRAY); return; }
        var bi = 0;
        for (var i = 1; i < g._nepi; i++) {
            if (g._emag[i] > g._emag[bi]) { bi = i; }
        }
        var mag = g._emag[bi];
        var bead = (mag >= 529) ? 24 : 1 + Math.sqrt(mag).toNumber();
        var b = g._eband[bi];
        var lv = (b >> 24) & 15;
        var d = g._edur[bi];
        put(dc, 0, (bi + 1) + "/" + g._nepi, Gfx.COLOR_WHITE);
        put(dc, 4, d + "m r" + bead + " L" + lv, Gfx.COLOR_WHITE);
        if (d > 0) {
            var ns = ((d - 1) >> lv) + 1;
            var gap = 4;
            for (var k = 0; k < ns && k < 6; k++) {
                var zs = (b >> (4 * k)) & 15;
                put(dc, gap, zs.toString(), g.zoneColor((zs > 8) ? 8 : zs));
                gap = 0;
            }
        }
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
        var x0 = X0;
        var yb = YB;                       // HR 40 at the bottom, 200 at yb-H
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
