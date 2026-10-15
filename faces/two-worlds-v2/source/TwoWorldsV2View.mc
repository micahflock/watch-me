using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;
using Toybox.Math as Math;

// TwoWorldsV2View — the "two worlds" V2 face. Identical artificial chrome (7-seg
// clock, day/date readout, phone uplink bars, battery chunks, sun/north marker,
// white border, field mask) over a NEW organic field: the MossGrove day-organism
// (core/src/genart/MossGrove.mc) replacing BioBloom. The grove is centred 2/5 up
// from the bottom (CY=108), the same centre BioBloom used, so the field-mask and
// border geometry are unchanged. The grove record is tiny and always persists,
// so the V1 "containment breach" warning is gone.
//
// Render order (back -> front): grove, field mask, border, uplink, battery,
// readout, gps pip, time, north, debug.
class TwoWorldsV2View extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _grove;       // MossGrove (time-agnostic day organism)
    var _timeStrip;
    var _colon;
    var _dowStrip;
    var _dateStrip;

    function initialize() {
        WatchFace.initialize();
    }

    function onLayout(dc) {
        _state = new Snapshot();
        GenArt.initSinTable();

        _timeStrip = new StripGlyphs(Rez.Drawables.FontTime, 18);
        _colon     = Ui.loadResource(Rez.Drawables.FontColon);
        _dowStrip  = new StripGlyphs(Rez.Drawables.FontDow, 18);
        _dateStrip = new StripGlyphs(Rez.Drawables.FontDate, 6);

        _grove = new MossGrove();
        MossState.restore(_grove);         // re-hydrate the day record after reload

        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(Diag.wrapGrove(_grove), null);   // 1 moss organism (back)
        _compositor.add(new FieldMaskComponent(), null); // 2 confine art to field
        _compositor.add(new BorderComponent(), null);    // 3 white border
        _compositor.add(new UplinkComponent(), null);    // 4 phone bars
        _compositor.add(new BatteryComponent(), null);   // 5 battery chunks
        _compositor.add(new ReadoutComponent(_dowStrip, _dateStrip), null); // 6 day/date
        _compositor.add(new GpsComponent(), null);       // 6b GPS fix recency pip
        _compositor.add(new ClockComponent(_timeStrip, _colon), null);      // 7 time
        _compositor.add(new NorthComponent(), null);     // 8 sun/north marker, over the chrome
        _compositor.add(new DebugComponent(), null);     // (:debug) overlay
        var diag = Diag.component();                     // diag build only
        if (diag != null) { _compositor.add(diag, null); }
    }

    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _grove.advance(_state);            // accrete the day's record
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }

    // Persist the day record so it survives a teardown (menu open).
    function onHide() { MossState.save(_grove); Diag.save(_grove); }

    function onSettingsChanged() {}
}

// --- pure helpers (shared geometry with V1) ----------------------------------

module Face {
    function batteryLevel(pct) {
        if (pct == null) { return 0; }
        var lit = 0;
        for (var k = 1; k <= 3; k++) {
            if (pct > (k - 1) * 33.33) { lit = k; }
        }
        return lit;
    }

    function displayHour(hour24, is24Hour) {
        if (is24Hour != false) { return hour24; }
        var h = hour24 % 12;
        return (h == 0) ? 12 : h;
    }
}

// --- components (duck-typed: each has render(dc, state)) ----------------------
// These mirror the V1 overlay chrome verbatim; the field geometry is unchanged
// because the grove shares BioBloom's centre.

class FieldMaskComponent {
    var _runs;

    function initialize() {
        _runs = [];
        var openA = new [8];
        var openB = new [8];
        var open = openA;
        var nOpen = 0;
        var cx = new [4];
        var cw = new [4];
        var used = new [4];
        for (var y = 0; y < 180; y++) {
            var nCur = scanline(y, cx, cw);
            for (var c = 0; c < nCur; c++) { used[c] = false; }
            var nxt = (open == openA) ? openB : openA;
            var nNext = 0;
            for (var o = 0; o < nOpen; o++) {
                var r = open[o];
                var rx = (r >> 24) & 0xFF;
                var rw = (r >> 16) & 0xFF;
                var hit = -1;
                for (var c = 0; c < nCur; c++) {
                    if (!used[c] && cx[c] == rx && cw[c] == rw) { hit = c; break; }
                }
                if (hit >= 0) {
                    used[hit] = true;
                    nxt[nNext] = r + 1;
                    nNext++;
                } else {
                    _runs.add(r);
                }
            }
            for (var c = 0; c < nCur; c++) {
                if (!used[c]) {
                    nxt[nNext] = (cx[c] << 24) | (cw[c] << 16) | (y << 8) | 1;
                    nNext++;
                }
            }
            open = nxt;
            nOpen = nNext;
        }
        for (var o = 0; o < nOpen; o++) { _runs.add(open[o]); }
    }

    function scanline(y, cx, cw) {
        var dy = y - 90.7;
        var disc = 9177.64 - dy * dy;
        if (disc <= 0.0) { cx[0] = 0; cw[0] = 215; return 1; }
        var hw = Math.sqrt(disc);
        var xl = 107.5 - hw;
        var xr = 107.5 + hw;
        if (y < 62) {
            var xcut;
            if (y < 15) {
                xcut = 166.0;
            } else {
                xcut = 134.0 + 32.0 * (62 - y) / 47.0;
                if (xcut > 166.0) { xcut = 166.0; }
            }
            if (xl < xcut) { xl = xcut; }
            if (xl >= xr) { cx[0] = 0; cw[0] = 215; return 1; }
        }
        if (y >= 163) {
            var t = (y - 163.0) / 9.0;
            var lw = 70.0 - 13.0 * t;
            var rw = 145.0 + 13.0 * t;
            var n = 0;
            var cur = 0.0;
            n = run(cx, cw, n, cur, xl); cur = xl;
            if (lw > cur) { cur = lw; }
            if (rw > cur) { n = run(cx, cw, n, cur, rw); cur = rw; }
            if (xr > cur) { cur = xr; }
            if (cur < 215.0) { n = run(cx, cw, n, cur, 215.0); }
            return n;
        }
        var n = 0;
        n = run(cx, cw, n, 0.0, xl);
        n = run(cx, cw, n, xr, 215.0);
        return n;
    }

    function run(cx, cw, n, x0, x1) {
        var a = (x0 + 0.5).toNumber();
        var b = (x1 + 0.5).toNumber();
        if (a < 0) { a = 0; }
        if (b > 215) { b = 215; }
        if (b > a) { cx[n] = a; cw[n] = b - a; return n + 1; }
        return n;
    }

    function render(dc, state) {
        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
        for (var i = 0; i < _runs.size(); i++) {
            var v = _runs[i];
            dc.fillRectangle((v >> 24) & 0xFF, (v >> 8) & 0xFF,
                (v >> 16) & 0xFF, v & 0xFF);
        }
    }
}

class BorderComponent {
    function render(dc, state) {
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        dc.drawLine(16, 62, 134, 62);
        dc.drawLine(134, 62, 166, 15);
        arc(dc, 107.5, 90.7, 95.8, 37.7, 148.0);
        arc(dc, 107.5, 90.7, 95.8, 212.0, 287.4);
        dc.drawLine(70, 163, 145, 163);
        dc.drawLine(70, 163, 57, 172);
        dc.drawLine(145, 163, 158, 172);
    }

    function arc(dc, cx, cy, r, a0, a1) {
        var n = ((a1 - a0) / 4.0).toNumber();
        if (n < 1) { n = 1; }
        var px = rnd(cx + r * Math.sin(a0 * Math.PI / 180.0));
        var py = rnd(cy - r * Math.cos(a0 * Math.PI / 180.0));
        for (var i = 1; i <= n; i++) {
            var a = a0 + (a1 - a0) * i / n;
            var rad = a * Math.PI / 180.0;
            var x = rnd(cx + r * Math.sin(rad));
            var y = rnd(cy - r * Math.cos(rad));
            dc.drawLine(px, py, x, y);
            px = x;
            py = y;
        }
    }

    function rnd(v) { return (v + 0.5).toNumber(); }
}

class UplinkComponent {
    function render(dc, state) {
        var connected = (state.phoneConnected == true);
        dc.setColor(connected ? Gfx.COLOR_BLUE : Gfx.COLOR_DK_GRAY,
            Gfx.COLOR_TRANSPARENT);
        var x = 128;
        for (var i = 0; i < 5; i++) {
            var w = 29.0 + (4.0 - 29.0) * i / 4.0;
            dc.fillRectangle(x, 12 + i * 9, (w + 0.5).toNumber(), 4);
        }
    }
}

class BatteryComponent {
    function render(dc, state) {
        var level = Face.batteryLevel(state.batteryPct);
        var x0 = 74;
        for (var i = 0; i < 3; i++) {
            dc.setColor(i < level ? Gfx.COLOR_ORANGE : Gfx.COLOR_DK_GRAY,
                Gfx.COLOR_TRANSPARENT);
            dc.fillRectangle(x0 + i * 25, 169, 18, 8);
        }
    }
}

class NorthComponent {
    var _quad;

    function initialize() {
        _quad = [[0, 0], [0, 0], [0, 0], [0, 0]];
    }

    function render(dc, state) {
        var res = SunCompass.compute(state.year, state.month, state.day,
            state.hour, state.minute, state.utcOffsetSec, state.lat, state.lon);
        if (res == null) { return; }
        var elev = res[1];
        if (elev <= -0.833 || elev >= 80.0) { return; }
        draw(dc, res[0]);
    }

    function draw(dc, bearing) {
        var th = bearing * Math.PI / 180.0;
        var rx = Math.sin(th);
        var ry = -Math.cos(th);
        var tx = Math.cos(th);
        var ty = Math.sin(th);
        var r = rimR(ry);
        var cx = 107.5 + r * rx;
        var cy = 90.0 + r * ry;

        dc.setColor(Gfx.COLOR_RED, Gfx.COLOR_TRANSPARENT);
        quad(cx, cy, rx, ry, tx, ty, 5.0, 4.3);
        dc.fillPolygon(_quad);

        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
        quad(cx, cy, rx, ry, tx, ty, 2.0, 1.72);
        dc.fillPolygon(_quad);
    }

    // The r=101.7 rim cut flat at the panel's top/bottom edges so the marker
    // stays on the glass at every bearing (see the V1 NorthComponent).
    function rimR(ry) {
        var r = 101.7;
        if (-ry * r > 84.5) { r = 84.5 / -ry; }        // top edge: centre y 5.5
        else if (ry * r > 82.5) { r = 82.5 / ry; }     // bottom edge: centre y 172.5
        return r;
    }

    function quad(cx, cy, rx, ry, tx, ty, sR, sT) {
        _quad[0][0] = rnd(cx + sR * rx + sT * tx);
        _quad[0][1] = rnd(cy + sR * ry + sT * ty);
        _quad[1][0] = rnd(cx + sR * rx - sT * tx);
        _quad[1][1] = rnd(cy + sR * ry - sT * ty);
        _quad[2][0] = rnd(cx - sR * rx - sT * tx);
        _quad[2][1] = rnd(cy - sR * ry - sT * ty);
        _quad[3][0] = rnd(cx - sR * rx + sT * tx);
        _quad[3][1] = rnd(cy - sR * ry + sT * ty);
    }

    function rnd(v) { return (v + 0.5).toNumber(); }
}

class ReadoutComponent {
    var _dow;
    var _date;

    function initialize(dowStrip, dateStrip) {
        _dow = dowStrip;
        _date = dateStrip;
    }

    function render(dc, state) {
        var y = 11;
        var leftX = 82;
        if (state.dayOfWeek != null && state.dayOfWeek >= 1 && state.dayOfWeek <= 7) {
            _dow.draw(dc, state.dayOfWeek - 1, leftX, y);
        }
        if (state.day != null) {
            var d = state.day;
            var x = leftX + 18 + 4;
            if (d >= 10) {
                _date.draw(dc, (d / 10) % 10, x, y);
                x += 6 + 1;
            }
            _date.draw(dc, d % 10, x, y);
        }
    }
}

// GPS fix recency pip, left of the day-of-week (owner, 2026-10): a small
// target in the chrome's state colours -- blue = a fix within 24 h (like the
// connected uplink), amber = an older fix (or one whose age the face doesn't
// know yet), dark gray hollow ring = no GPS fix ever seen (the north marker is
// then on the lat/lng settings). See DataSource for how recency is inferred.
class GpsComponent {
    function render(dc, state) {
        var g = state.gpsFix;
        var c = Gfx.COLOR_DK_GRAY;
        if (g == 2) { c = Gfx.COLOR_BLUE; }
        else if (g == 1) { c = Gfx.COLOR_YELLOW; }
        dc.setColor(c, Gfx.COLOR_TRANSPARENT);
        dc.drawCircle(75, 16, 4);
        if (g == 1 || g == 2) { dc.fillCircle(75, 16, 1); }
    }
}

class ClockComponent {
    var _digits;
    var _colon;

    function initialize(digits, colon) {
        _digits = digits;
        _colon = colon;
    }

    function render(dc, state) {
        var y = 26;
        if (state.hour != null) {
            var h = Face.displayHour(state.hour, state.is24Hour);
            var tens = (h / 10) % 10;
            if (state.is24Hour != false || tens != 0) {
                _digits.draw(dc, tens, 20, y);
            }
            _digits.draw(dc, h % 10, 43, y);
        }
        dc.drawBitmap(66, y, _colon);
        if (state.minute != null) {
            _digits.draw(dc, (state.minute / 10) % 10, 75, y);
            _digits.draw(dc, state.minute % 10, 98, y);
        }
    }
}

class DebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc);
    }
}
