using Toybox.WatchUi as Ui;

// StripGlyphs — blits one cell from a horizontal glyph strip bitmap.
//
// The strip is a single PNG of N equal-width cells (e.g. 7 day-of-week labels)
// pre-quantized OFFLINE to the device's 16-color palette (tools/make-dow-strip.sh).
// There is no <palette> resource element at CIQ 2.4, so quantization must be
// done before import.
//
// Blitting a sub-region: set a clip to the destination cell box and draw the
// whole bitmap shifted left by index*cellW so only the wanted cell lands in the
// clip. (Dc.setClip is API 2.3.)
class StripGlyphs {
    var _bmp;
    var _cellW;
    var _cellH;
    var _count;

    // rezId: a Drawables symbol (e.g. Rez.Drawables.DowStrip). cellW: pixel
    // width of one glyph cell. The strip height is the glyph height.
    function initialize(rezId, cellW) {
        _bmp = Ui.loadResource(rezId);
        _cellW = cellW;
        _cellH = _bmp.getHeight();
        _count = _bmp.getWidth() / cellW;
    }

    function count() { return _count; }
    function cellWidth() { return _cellW; }
    function cellHeight() { return _cellH; }

    // Draw glyph `index` at pixel (x,y).
    function draw(dc, index, x, y) {
        if (index < 0 || index >= _count) { return; }
        dc.setClip(x, y, _cellW, _cellH);
        dc.drawBitmap(x - index * _cellW, y, _bmp);
        dc.clearClip();
    }
}
