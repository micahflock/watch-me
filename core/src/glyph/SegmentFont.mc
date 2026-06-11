using Toybox.Graphics as Gfx;

// SegmentFont — parametric 7-segment digit renderer. Pure draw primitives
// (fillPolygon), no font resources.
//
// Segment naming (standard):
//      aaa
//     f   b
//     f   b
//      ggg
//     e   c
//     e   c
//      ddd
// DIGIT_SEGS[d] is a bitmask: bit0=a, bit1=b, ... bit6=g.
//
// Geometry is computed once per parameter tuple via buildSegments(); each
// segment is a polygon (Array of [x,y] points) in a local coordinate box of
// width digitWidth(params) and height `height`. drawDigit translates the
// polygons by (x,y) into a reusable scratch buffer (no per-draw allocation
// beyond the scratch points).
module SegmentFont {

    // a,b,c,d,e,f,g masks for digits 0-9.
    const DIGIT_SEGS = [
        0x3F, // 0: a b c d e f
        0x06, // 1: b c
        0x5B, // 2: a b g e d
        0x4F, // 3: a b g c d
        0x66, // 4: f g b c
        0x6D, // 5: a f g c d
        0x7D, // 6: a f g e c d
        0x07, // 7: a b c
        0x7F, // 8: all
        0x6F  // 9: a b c d f g
    ];

    // Build a params dictionary. All in pixels except slant (px of horizontal
    // shift across full height) and corner (unused placeholder for future
    // rounding; segments are hexagonal chamfers already).
    //   :height, :stroke, :gap (gap between segment ends), :slant
    function makeParams(height, stroke, gap, slant) {
        var width = (height - 2 * stroke) / 2 + stroke; // classic ~1:2 ratio
        return {
            :height => height,
            :stroke => stroke,
            :gap => gap,
            :slant => slant,
            :width => width
        };
    }

    function digitWidth(params) { return params.get(:width); }
    function digitHeight(params) { return params.get(:height); }

    // Build the 7 segment polygons (local coords, top-left origin). Returns an
    // Array[7] of point arrays. Apply slant at build time.
    function buildSegments(params) {
        var H = params.get(:height);
        var W = params.get(:width);
        var t = params.get(:stroke);
        var g = params.get(:gap);
        var s = params.get(:slant);
        var midY = H / 2;

        // Horizontal segment as a chamfered hexagon spanning x in [g, W-g] at a
        // given vertical center, thickness t.
        var segs = new [7];
        // a (top)
        segs[0] = hSeg(g, 0, W - g, t);
        // g (middle)
        segs[6] = hSeg(g, midY - t / 2, W - g, t);
        // d (bottom)
        segs[3] = hSeg(g, H - t, W - g, t);
        // b (upper right)
        segs[1] = vSeg(W - t, g, midY - g, t);
        // c (lower right)
        segs[2] = vSeg(W - t, midY + g, H - g, t);
        // f (upper left)
        segs[5] = vSeg(0, g, midY - g, t);
        // e (lower left)
        segs[4] = vSeg(0, midY + g, H - g, t);

        // Apply slant: shift x by s * (1 - y/H) so the top leans right.
        if (s != 0) {
            for (var i = 0; i < 7; i++) {
                var poly = segs[i];
                for (var p = 0; p < poly.size(); p++) {
                    var pt = poly[p];
                    var shift = (s * (H - pt[1])) / H;
                    poly[p] = [pt[0] + shift, pt[1]];
                }
            }
        }
        return segs;
    }

    // Horizontal hexagonal segment from x0..x1 at top yTop, thickness t.
    function hSeg(x0, yTop, x1, t) {
        var h = t / 2;
        var yc = yTop + h;
        return [
            [x0,      yc],
            [x0 + h,  yTop],
            [x1 - h,  yTop],
            [x1,      yc],
            [x1 - h,  yTop + t],
            [x0 + h,  yTop + t]
        ];
    }

    // Vertical hexagonal segment at left xLeft, from y0..y1, thickness t.
    function vSeg(xLeft, y0, y1, t) {
        var h = t / 2;
        var xc = xLeft + h;
        return [
            [xc,      y0],
            [xLeft + t, y0 + h],
            [xLeft + t, y1 - h],
            [xc,      y1],
            [xLeft,   y1 - h],
            [xLeft,   y0 + h]
        ];
    }

    // Draw one digit (0-9) at pixel (x,y). litColor draws active segments;
    // unlitColor draws inactive "ghost" segments (pass null to skip them).
    function drawDigit(dc, segs, digit, x, y, litColor, unlitColor) {
        if (digit < 0 || digit > 9) { return; }
        var mask = DIGIT_SEGS[digit];
        for (var i = 0; i < 7; i++) {
            var on = ((mask >> i) & 1) != 0;
            if (on) {
                dc.setColor(litColor, Gfx.COLOR_TRANSPARENT);
            } else if (unlitColor != null) {
                dc.setColor(unlitColor, Gfx.COLOR_TRANSPARENT);
            } else {
                continue;
            }
            fillTranslated(dc, segs[i], x, y);
        }
    }

    // fillPolygon with each point translated by (dx,dy). Uses a scratch array
    // sized to the polygon (6 pts) — small, reused per segment.
    function fillTranslated(dc, poly, dx, dy) {
        var n = poly.size();
        var pts = new [n];
        for (var i = 0; i < n; i++) {
            pts[i] = [poly[i][0] + dx, poly[i][1] + dy];
        }
        dc.fillPolygon(pts);
    }
}
