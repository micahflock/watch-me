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
}
