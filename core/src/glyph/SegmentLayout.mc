using Toybox.Graphics as Gfx;

// SegmentLayout — positions groups of SegmentFont digits (HH:MM, dates).
// Stateless helpers; the caller owns the built segment polygons.
module SegmentLayout {

    // Draw a two-digit, zero-padded number at (x,y). Returns the x advance.
    function drawTwoDigits(dc, segs, params, value, x, y, lit, unlit) {
        var w = SegmentFont.digitWidth(params);
        var gap = params.get(:stroke); // inter-digit gap = one stroke width
        var d0 = (value / 10) % 10;
        var d1 = value % 10;
        SegmentFont.drawDigit(dc, segs, d0, x, y, lit, unlit);
        SegmentFont.drawDigit(dc, segs, d1, x + w + gap, y, lit, unlit);
        return 2 * w + gap;
    }

    // Draw HH:MM centered horizontally about cx, top at y. Colon is two dots.
    function drawClock(dc, segs, params, cx, y, hour, minute, lit, unlit) {
        var w = SegmentFont.digitWidth(params);
        var gap = params.get(:stroke);
        var colonW = params.get(:stroke) * 2;
        // total width = HH (2w+gap) + colon + MM (2w+gap)
        var total = (2 * w + gap) + colonW + (2 * w + gap) + 2 * gap;
        var x = cx - total / 2;

        x += drawTwoDigits(dc, segs, params, hour, x, y, lit, unlit);
        x += gap;
        drawColon(dc, params, x, y, colonW, lit);
        x += colonW + gap;
        drawTwoDigits(dc, segs, params, minute, x, y, lit, unlit);
    }

    function drawColon(dc, params, x, y, colonW, color) {
        var H = params.get(:height);
        var r = params.get(:stroke) / 2;
        if (r < 2) { r = 2; }
        var cx = x + colonW / 2;
        dc.setColor(color, Gfx.COLOR_TRANSPARENT);
        dc.fillCircle(cx, y + H / 3, r);
        dc.fillCircle(cx, y + 2 * H / 3, r);
    }

    // Total pixel width of an HH:MM group (for centering/keep-out sizing).
    function clockWidth(params) {
        var w = SegmentFont.digitWidth(params);
        var gap = params.get(:stroke);
        var colonW = gap * 2;
        return (2 * w + gap) + colonW + (2 * w + gap) + 2 * gap;
    }
}
