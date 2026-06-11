// Region — rectangle helpers for clipping and keep-out masking.
// Rects are flat 4-element Arrays [x, y, w, h] in pixels (cheaper than objects).
module Region {

    // True if rects a and b overlap.
    function intersects(a, b) {
        return !(a[0] + a[2] <= b[0] ||
                 b[0] + b[2] <= a[0] ||
                 a[1] + a[3] <= b[1] ||
                 b[1] + b[3] <= a[1]);
    }

    // True if rect `r` fully contains the pixel box (px,py,pw,ph).
    function rectContains(r, px, py, pw, ph) {
        return px >= r[0] && py >= r[1] &&
               (px + pw) <= (r[0] + r[2]) &&
               (py + ph) <= (r[1] + r[3]);
    }

    // True if the pixel box (px,py,pw,ph) overlaps rect `r` at all.
    function rectOverlaps(r, px, py, pw, ph) {
        return !(px + pw <= r[0] ||
                 r[0] + r[2] <= px ||
                 py + ph <= r[1] ||
                 r[1] + r[3] <= py);
    }

    // Convert a pixel keep-out rect into an inclusive cell-index range for a
    // grid whose cell (0,0) starts at (originX,originY) with the given cellSize.
    // Returns flat [c0, r0, c1, r1]; a sim renderer can skip cells inside it.
    // If the keep-out does not touch the grid, returns null.
    function clampCellRange(keepOut, originX, originY, cellSize, cols, rows) {
        var c0 = (keepOut[0] - originX) / cellSize;
        var r0 = (keepOut[1] - originY) / cellSize;
        var c1 = (keepOut[0] + keepOut[2] - originX) / cellSize;
        var r1 = (keepOut[1] + keepOut[3] - originY) / cellSize;
        if (c1 < 0 || r1 < 0 || c0 > cols - 1 || r0 > rows - 1) {
            return null;
        }
        if (c0 < 0) { c0 = 0; }
        if (r0 < 0) { r0 = 0; }
        if (c1 > cols - 1) { c1 = cols - 1; }
        if (r1 > rows - 1) { r1 = rows - 1; }
        return [c0, r0, c1, r1];
    }
}
