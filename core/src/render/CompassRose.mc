using Toybox.Graphics as Gfx;
using Toybox.Math as Math;

// CompassRose — draws the sun-compass dial: a rim with an aiming dot at the
// 12 o'clock mark (point that dot at the sun), a red needle at the true-north
// dial angle (from SunCompass.northDial), and ticks at the other cardinals.
//
// A class (not a module) so the fillPolygon point list is allocated once and
// rewritten in place each render — zero per-tick allocation. Per frame it
// costs ONE sin + ONE cos (the E/S/W directions reuse them by symmetry) plus
// ~10 Dc calls, far below the watchdog noise floor.
//
// All draw calls are genuinely 1.x-era (drawCircle/fillCircle/drawLine/
// fillPolygon/drawText) — none of the Math 3.0 doc-trap symbols.
class CompassRose {
    var _tri; // reusable [[x,y],[x,y],[x,y]] for the needle polygon

    function initialize() {
        _tri = [[0, 0], [0, 0], [0, 0]];
    }

    // northDeg: dial angle of true north, clockwise from 12 (0..360).
    // bright: true when the sun is sightable (above horizon, below ~80 deg
    // elevation); false dims the rose to signal "computed, not usable now".
    function draw(dc, cx, cy, r, northDeg, bright) {
        var a = northDeg * Math.PI / 180.0;
        var s = Math.sin(a);
        var c = Math.cos(a);
        // Dial unit vectors in screen coords (y grows downward):
        // north (s,-c), east (c,s), south (-s,c), west (-c,-s).

        // Rim + aiming dot at 12 (the sun-pointing reference).
        dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawCircle(cx, cy, r);
        dc.setColor(bright ? Gfx.COLOR_YELLOW : Gfx.COLOR_DK_GRAY,
            Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(cx, cy - r, 3);

        // Ticks at dial E/S/W (N gets the needle instead).
        dc.setColor(bright ? Gfx.COLOR_LT_GRAY : Gfx.COLOR_DK_GRAY,
            Gfx.COLOR_TRANSPARENT);
        tick(dc, cx, cy, r, c, s);   // east
        tick(dc, cx, cy, r, -s, c);  // south
        tick(dc, cx, cy, r, -c, -s); // west

        // South tail of the needle.
        dc.drawLine(cx, cy,
            rnd(cx - s * (r - 8)), rnd(cy + c * (r - 8)));

        // North needle: tip just inside the rim, base straddling the center.
        _tri[0][0] = rnd(cx + s * (r - 3));
        _tri[0][1] = rnd(cy - c * (r - 3));
        _tri[1][0] = rnd(cx + c * 4.0 - s * 2.0);
        _tri[1][1] = rnd(cy + s * 4.0 + c * 2.0);
        _tri[2][0] = rnd(cx - c * 4.0 - s * 2.0);
        _tri[2][1] = rnd(cy - s * 4.0 + c * 2.0);
        dc.setColor(bright ? Gfx.COLOR_RED : Gfx.COLOR_DK_GRAY,
            Gfx.COLOR_TRANSPARENT);
        dc.fillPolygon(_tri);
    }

    // Inputs missing (no location set, clock unreadable): rim + "?".
    function drawUnknown(dc, cx, cy, r) {
        dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
        dc.drawCircle(cx, cy, r);
        dc.drawText(cx, cy, Gfx.FONT_XTINY, "?",
            Gfx.TEXT_JUSTIFY_CENTER | Gfx.TEXT_JUSTIFY_VCENTER);
    }

    // Short radial tick from r-5 to r along unit direction (dx,dy).
    function tick(dc, cx, cy, r, dx, dy) {
        dc.drawLine(
            rnd(cx + dx * (r - 5)), rnd(cy + dy * (r - 5)),
            rnd(cx + dx * r), rnd(cy + dy * r));
    }

    // Round positive screen coordinates to Number (all rose points are >= 0).
    function rnd(v) {
        return (v + 0.5).toNumber();
    }
}
