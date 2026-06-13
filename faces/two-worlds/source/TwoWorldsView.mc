using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;
using Toybox.Math as Math;

// TwoWorldsView — the "two worlds" face (design: docs/claude-design-handoff.md).
//
// A hard-edged ARTIFICIAL layer (7-seg bitmap clock, day/date readout, phone
// uplink bars, battery chunks, sun/north marker) floats over the organic
// NATURAL field: the shared strataflock generative engine (core/src/genart) —
// StrataField sediment accreting the day from the bottom, a Flock murmuration
// living in the present minute above it. The art draws full-frame, then
// FieldMaskComponent blacks everything outside the field region so it reads as
// painted only inside the disc; the white border traces that same edge.
//
// Render order (back -> front): strata, flock, field mask, border, uplink,
// battery, north, readout, time, debug.
class TwoWorldsView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _field;       // StrataField (generative; also feeds the flock)
    var _flock;       // Flock (stateless murmuration)
    var _timeStrip;   // StripGlyphs: 7-seg digits, 18px cells
    var _colon;       // BitmapResource: the 4px colon glyph
    var _dowStrip;    // StripGlyphs: 2-letter day sprites, 18px cells
    var _dateStrip;   // StripGlyphs: day-of-month digits, 6px cells

    function initialize() {
        WatchFace.initialize();
    }

    // Allocate everything ONCE (lifecycle contract: zero per-tick allocation).
    function onLayout(dc) {
        _state = new Snapshot();
        GenArt.initSinTable();

        _timeStrip = new StripGlyphs(Rez.Drawables.FontTime, 18);
        _colon     = Ui.loadResource(Rez.Drawables.FontColon);
        _dowStrip  = new StripGlyphs(Rez.Drawables.FontDow, 18);
        _dateStrip = new StripGlyphs(Rez.Drawables.FontDate, 6);

        _field = new StrataField();
        _flock = new Flock(_field, null); // keep-out unneeded: the mask + the
                                          // chrome band already sit off-field

        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(_field, null);                   // 1 strata (back)
        _compositor.add(_flock, null);                   // 2 flock
        _compositor.add(new FieldMaskComponent(), null); // 3 confine art to field
        _compositor.add(new BorderComponent(), null);    // 4 white border
        _compositor.add(new UplinkComponent(), null);    // 5 phone bars
        _compositor.add(new BatteryComponent(), null);   // 6 battery chunks
        _compositor.add(new NorthComponent(), null);     // 7 sun/north marker
        _compositor.add(new ReadoutComponent(_dowStrip, _dateStrip), null); // 8 day/date
        _compositor.add(new ClockComponent(_timeStrip, _colon), null);      // 9 time
        _compositor.add(new DebugComponent(), null);     // (:debug) overlay
    }

    // Full redraw — once per minute in low power.
    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _field.advance(_state);            // simulate the day's sediment
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }
    // onPartialUpdate intentionally omitted: fr735xt has no hardware support.

    function onSettingsChanged() {}
}

// --- pure helpers (testable; see tests/TestTwoWorlds.mc) ---------------------

module Face {
    // Lit battery-chunk count from battery percent (0..100). Three 33% chunks,
    // chunk k lit when pct > (k-1)*33.33 -> fills left->right, depletes
    // right->left (rightmost empties first). null pct -> 0 (all grey).
    function batteryLevel(pct) {
        if (pct == null) { return 0; }
        var lit = 0;
        for (var k = 1; k <= 3; k++) {
            if (pct > (k - 1) * 33.33) { lit = k; }
        }
        return lit;
    }

    // Displayed hour from a 0..23 clock hour, honoring the device 24h flag.
    //   24h (true/null) : unchanged, 0..23.
    //   12h (false)     : 1..12 (0 -> 12, 13..23 -> 1..11).
    function displayHour(hour24, is24Hour) {
        if (is24Hour != false) { return hour24; }
        var h = hour24 % 12;
        return (h == 0) ? 12 : h;
    }
}

// --- components (duck-typed: each has render(dc, state)) ---------------------

// FieldMaskComponent — paints BLACK over everything OUTSIDE the field region,
// confining the full-frame generative art (strata + flock, drawn before this)
// to the disc. The mask runs are precomputed once (the field shape is static):
// zero per-tick allocation, just a fillRectangle per black run.
//
// Field region (same geometry as BorderComponent): offset disc r=95.8 @
// (107.5,90.7), cut by the chord+slant on top and the battery notch at the
// bottom. Each scanline's black runs are the complement of the field interval(s)
// within [0,215].
class FieldMaskComponent {
    var _runs; // packed black runs: (x << 16) | (y << 8) | w (each fits a byte)

    function initialize() {
        _runs = [];
        for (var y = 0; y < 180; y++) {
            var dy = y - 90.7;
            var disc = 9177.64 - dy * dy; // 95.8^2 - dy^2
            if (disc <= 0.0) { black(0.0, 215.0, y); continue; }
            var hw = Math.sqrt(disc);
            var xl = 107.5 - hw;
            var xr = 107.5 + hw;

            // Top cut: chord at y=62 (x 16..134) + slant up to (166,15).
            if (y < 62) {
                var xcut;
                if (y < 15) {
                    xcut = 166.0;
                } else {
                    xcut = 134.0 + 32.0 * (62 - y) / 47.0;
                    if (xcut > 166.0) { xcut = 166.0; }
                }
                if (xl < xcut) { xl = xcut; }
                if (xl >= xr) { black(0.0, 215.0, y); continue; }
            }

            // Bottom battery notch (y>=163): field is [xl,lw] and [rw,xr];
            // black the three gaps around them.
            if (y >= 163) {
                var t = (y - 163.0) / 9.0;
                var lw = 70.0 - 13.0 * t;
                var rw = 145.0 + 13.0 * t;
                var cur = 0.0;
                black(cur, xl, y); cur = xl;
                if (lw > cur) { cur = lw; }       // skip field run [xl,lw]
                if (rw > cur) { black(cur, rw, y); cur = rw; }
                if (xr > cur) { cur = xr; }        // skip field run [rw,xr]
                if (cur < 215.0) { black(cur, 215.0, y); }
                continue;
            }

            // Normal scanline: field [xl,xr]; black the two sides.
            black(0.0, xl, y);
            black(xr, 215.0, y);
        }
    }

    function black(x0, x1, y) {
        var a = (x0 + 0.5).toNumber();
        var b = (x1 + 0.5).toNumber();
        if (a < 0) { a = 0; }
        if (b > 215) { b = 215; }
        if (b > a) {
            _runs.add((a << 16) | (y << 8) | (b - a));
        }
    }

    function render(dc, state) {
        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
        for (var i = 0; i < _runs.size(); i++) {
            var v = _runs[i];
            dc.fillRectangle((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF, 1);
        }
    }
}

// BorderComponent — the single white separation line: top chord + slant, the
// offset-circle rim (broken at the slant and the battery notch), and the notch
// walls. Arcs are drawn as short line segments (drawLine is 1.0-safe; avoids
// any drawArc availability question). Bearing convention: 0 deg = 12 o'clock,
// clockwise, x = cx + r*sin, y = cy - r*cos.
class BorderComponent {
    function render(dc, state) {
        dc.setColor(Gfx.COLOR_WHITE, Gfx.COLOR_TRANSPARENT);
        dc.drawLine(16, 62, 134, 62);     // chord
        dc.drawLine(134, 62, 166, 15);    // slant
        arc(dc, 107.5, 90.7, 95.8, 37.7, 148.0);   // slant-top -> right notch
        arc(dc, 107.5, 90.7, 95.8, 212.0, 287.4);  // left notch -> chord-left
        dc.drawLine(70, 163, 145, 163);   // notch top
        dc.drawLine(70, 163, 57, 172);    // notch left wall
        dc.drawLine(145, 163, 158, 172);  // notch right wall
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

// UplinkComponent — phone-connection bars (signal motif). Fixed bar geometry;
// color is the ONLY data-driven thing and it is all-or-nothing across the group:
// connected -> BLUE, disconnected/null -> DK_GRAY. Bars are never hidden.
class UplinkComponent {
    function render(dc, state) {
        var connected = (state.phoneConnected == true);
        dc.setColor(connected ? Gfx.COLOR_BLUE : Gfx.COLOR_DK_GRAY,
            Gfx.COLOR_TRANSPARENT);
        var x = 128;
        for (var i = 0; i < 5; i++) {
            var w = 29.0 + (4.0 - 29.0) * i / 4.0; // 29,23,17,10,4
            dc.fillRectangle(x, 12 + i * 9, (w + 0.5).toNumber(), 4);
        }
    }
}

// BatteryComponent — three 33% chunks centered in the bottom notch. ORANGE when
// lit, DK_GRAY otherwise; lit count from Face.batteryLevel (right-to-left drain).
class BatteryComponent {
    function render(dc, state) {
        var level = Face.batteryLevel(state.batteryPct);
        var x0 = 74; // round(107.5 - (3*18 + 2*7)/2)
        for (var i = 0; i < 3; i++) {
            dc.setColor(i < level ? Gfx.COLOR_ORANGE : Gfx.COLOR_DK_GRAY,
                Gfx.COLOR_TRANSPARENT);
            dc.fillRectangle(x0 + i * 25, 169, 18, 8);
        }
    }
}

// NorthComponent — a hollow red diamond riding the rim at the sun-derived
// true-north dial angle (reuses core SunCompass: point 12 o'clock at the sun,
// the marker shows where true north is). Shown ONLY when the sun is sightable
// (elevation in (-0.833, 80) deg); otherwise nothing is drawn (no location ->
// SunCompass returns null -> hidden). The point list is allocated once and
// rewritten in place each render.
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
        if (elev <= -0.833 || elev >= 80.0) { return; } // not sightable -> hidden
        draw(dc, res[0]);
    }

    function draw(dc, bearing) {
        var th = bearing * Math.PI / 180.0;
        var rx = Math.sin(th);
        var ry = -Math.cos(th);
        var tx = Math.cos(th);
        var ty = Math.sin(th);
        var cx = 107.5 + 101.7 * rx;
        var cy = 90.0 + 101.7 * ry;

        dc.setColor(Gfx.COLOR_RED, Gfx.COLOR_TRANSPARENT);
        quad(cx, cy, rx, ry, tx, ty, 5.0, 4.3);
        dc.fillPolygon(_quad);

        // Punch a hole (40% scale) to read as a hollow diamond.
        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
        quad(cx, cy, rx, ry, tx, ty, 2.0, 1.72);
        dc.fillPolygon(_quad);
    }

    // Diamond: +/- sR along the radial axis (rx,ry), +/- sT along tangential
    // (tx,ty), written into the reusable _quad.
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

// ReadoutComponent — "WE 10": a 2-letter day sprite + day-of-month digits, white.
// Layout reserves a 2-digit date so the day-of-week stays put (left edge fixed
// at x=82 = readoutRight 117 - reserved 35). Day printed as-is (no leading zero).
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
            var s = state.day.toString();
            var x = leftX + 18 + 4; // after the day sprite + 4px space
            for (var i = 0; i < s.length(); i++) {
                _date.draw(dc, s.substring(i, i + 1).toNumber(), x, y);
                x += 6 + 1; // digit width + 1px tracking
            }
        }
    }
}

// ClockComponent — HH:MM in the 7-seg bitmap font, honoring the device clock
// mode (Snapshot.is24Hour). In 24h the hour keeps its leading zero; in 12h the
// hour is 1..12 and a leading zero is blanked (the tens cell stays empty). The
// colon is its own 4px glyph and is always drawn; a null hour/minute leaves
// blank digit cells. Cell advance: digit 18+5, colon 4+5 (matches the handoff).
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
            // 12h: blank the leading zero (the tens cell stays empty).
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
        Instrument.overlay(dc); // no-op in release builds
    }
}
