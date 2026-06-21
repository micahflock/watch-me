using Toybox.WatchUi as Ui;
using Toybox.Graphics as Gfx;
using Toybox.Math as Math;

// TwoWorldsView — the "two worlds" face (design: docs/claude-design-handoff.md).
//
// A hard-edged ARTIFICIAL layer (7-seg bitmap clock, day/date readout, phone
// uplink bars, battery chunks, sun/north marker) floats over the organic
// NATURAL field: the BioBloom generative engine (core/src/genart) — a movement-
// fed filament dish with a central colony and HR-zone blooms growing the day
// from the centre out. The art draws full-frame, then FieldMaskComponent blacks
// everything outside the field region so it reads as painted only inside the
// disc; the white border traces that same edge.
//
// Render order (back -> front): biobloom, field mask, border, uplink, battery,
// north, readout, time, debug.
class TwoWorldsView extends Ui.WatchFace {

    var _state;
    var _compositor;
    var _bloom;       // BioBloom (movement-fed generative dish)
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

        _bloom = new BioBloom();
        BioState.restore(_bloom);          // re-hydrate the dish after a reload

        _compositor = new Compositor();
        _compositor.setBackground(Gfx.COLOR_BLACK);
        _compositor.add(_bloom, null);                   // 1 biobloom (back)
        _compositor.add(new FieldMaskComponent(), null); // 2 confine art to field
        _compositor.add(new BorderComponent(), null);    // 3 white border
        _compositor.add(new UplinkComponent(), null);    // 4 phone bars
        _compositor.add(new BatteryComponent(), null);   // 5 battery chunks
        _compositor.add(new NorthComponent(), null);     // 6 sun/north marker
        _compositor.add(new ReadoutComponent(_dowStrip, _dateStrip), null); // 7 day/date
        _compositor.add(new ClockComponent(_timeStrip, _colon), null);      // 8 time
        _compositor.add(new BreachComponent(), null);    // 9 over-budget warning
        _compositor.add(new DebugComponent(), null);     // (:debug) overlay
    }

    // Full redraw — once per minute in low power.
    function onUpdate(dc) {
        Instrument.tickStart();
        DataSource.refresh(_state);
        _bloom.advance(_state);            // grow the day's dish
        _compositor.renderAll(dc, _state);
        Instrument.tickEnd();
    }

    function onEnterSleep() {}
    function onExitSleep() { Ui.requestUpdate(); }
    // onPartialUpdate intentionally omitted: fr735xt has no hardware support.

    // The watch face can be torn down when a menu opens; persist the dish so it
    // is restored (not reset to blank) on the next layout.
    function onHide() { BioState.save(_bloom); }

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
// confining the full-frame generative art (the BioBloom dish, drawn before this)
// to the disc. The mask shape is static, so it is decomposed ONCE (in onLayout)
// into a small set of rectangles which render() replays (one fillRectangle each,
// zero per-tick allocation).
//
// Each scanline's black runs (the complement of the field interval(s) within
// [0,215]) are coalesced VERTICALLY: a run with the same x/width as the run
// directly above extends that rectangle's height instead of adding a new one.
// Over the curved disc edge this nearly halves both the stored rect count
// (~362 1px runs -> 188 rects) and the per-frame fillRectangle calls. Runs pack
// as (x << 24) | (w << 16) | (y << 8) | h (each byte 0..215).
//
// Field region (same geometry as BorderComponent): offset disc r=95.8 @
// (107.5,90.7), cut by the chord+slant on top and the battery notch at bottom.
class FieldMaskComponent {
    var _runs; // packed merged rects: (x << 24) | (w << 16) | (y << 8) | h

    function initialize() {
        _runs = [];
        // Open rects still growing downward (ping-pong between two fixed scratch
        // buffers so the build allocates nothing per scanline). A scanline has at
        // most 3 black runs, so only a few rects are ever open at once.
        var openA = new [8];
        var openB = new [8];
        var open = openA;
        var nOpen = 0;
        var cx = new [4];   // this scanline's run x's
        var cw = new [4];   // ... and widths
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
                    nxt[nNext] = r + 1;          // h is the low byte; +1 grows it
                    nNext++;
                } else {
                    _runs.add(r);                // closed -> store
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

    // Fill this scanline's black runs into cx[]/cw[]; returns the run count (0..3).
    function scanline(y, cx, cw) {
        var dy = y - 90.7;
        var disc = 9177.64 - dy * dy; // 95.8^2 - dy^2
        if (disc <= 0.0) { cx[0] = 0; cw[0] = 215; return 1; }
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
            if (xl >= xr) { cx[0] = 0; cw[0] = 215; return 1; }
        }

        // Bottom battery notch (y>=163): field is [xl,lw] and [rw,xr]; black the
        // three gaps around them.
        if (y >= 163) {
            var t = (y - 163.0) / 9.0;
            var lw = 70.0 - 13.0 * t;
            var rw = 145.0 + 13.0 * t;
            var n = 0;
            var cur = 0.0;
            n = run(cx, cw, n, cur, xl); cur = xl;
            if (lw > cur) { cur = lw; }       // skip field run [xl,lw]
            if (rw > cur) { n = run(cx, cw, n, cur, rw); cur = rw; }
            if (xr > cur) { cur = xr; }        // skip field run [rw,xr]
            if (cur < 215.0) { n = run(cx, cw, n, cur, 215.0); }
            return n;
        }

        // Normal scanline: field [xl,xr]; black the two sides.
        var n = 0;
        n = run(cx, cw, n, 0.0, xl);
        n = run(cx, cw, n, xr, 215.0);
        return n;
    }

    // Append the rounded/clamped run [x0,x1) to cx[]/cw[] if non-empty.
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
            // Direct digit math (day is 1..31) -- no toString()/substring(), which
            // allocate Strings every tick.
            var d = state.day;
            var x = leftX + 18 + 4; // after the day sprite + 4px space
            if (d >= 10) {
                _date.draw(dc, (d / 10) % 10, x, y);
                x += 6 + 1;          // digit width + 1px tracking
            }
            _date.draw(dc, d % 10, x, y);
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

// BreachComponent — when the dish outgrows what the persistence layer can store
// (save() OOM'd / the object store rejected it on the last onHide), it can no
// longer survive a reload. Stamp "CONTAINMENT BREACH" across the middle in red.
// Cost is ~nil in the normal case: the flag is read ONCE at layout (object-store
// reads are slow, never per tick) and the draw calls fire only when breached.
class BreachComponent {
    var _breached;

    function initialize() {
        _breached = BioState.breached();
    }

    function render(dc, state) {
        if (!_breached) { return; }
        dc.setColor(Gfx.COLOR_BLACK, Gfx.COLOR_TRANSPARENT);
        dc.fillRectangle(16, 68, 183, 48);          // backing band, for legibility
        dc.setColor(Gfx.COLOR_RED, Gfx.COLOR_TRANSPARENT);
        dc.drawText(107, 70, Gfx.FONT_SMALL, "CONTAINMENT", Gfx.TEXT_JUSTIFY_CENTER);
        dc.drawText(107, 91, Gfx.FONT_SMALL, "BREACH", Gfx.TEXT_JUSTIFY_CENTER);
    }
}

class DebugComponent {
    function initialize() {}
    function render(dc, state) {
        Instrument.overlay(dc); // no-op in release builds
    }
}
