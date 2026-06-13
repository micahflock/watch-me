using Toybox.Graphics as Gfx;

// Flock — the murmuration in the sky (the "present" layer).
//
// A 12x9 dot lattice bent out of true: dots wake as the day's steps
// accumulate; a day-seeded Lissajous attractor wanders the upper sky and
// nearby dots swell, taking the current HR-zone color; sine-noise warps the
// lattice with amplitude from movement now plus the decaying unrest trace;
// dots that drift within reach grow DK_GRAY filaments. Dots below the
// strata surface are buried; ones grazing it settle as LT_GRAY specks —
// the flock precipitating into sediment.
//
// Stateless by construction (fxhash principle): every frame is re-derived
// from (daySeed, minute, biometrics) + the terrain. The only allocations
// are per-dot scratch arrays, reused every frame. All math is integer;
// lengths in 1/16 px where sub-pixel resolution matters; distance to the
// attractor uses an octagonal approximation (no sqrt).
class Flock {

    const GX = 12;
    const GY = 9;
    const X0 = 14;
    const SX = 17;
    const Y0 = 16;
    const SY = 16;

    var _field;        // StrataField: terrain heights, movement, day seed
    var _keep;         // clock keep-out [x0, y0, x1, y1] or null
    var _px;           // per-dot scratch: warped x
    var _py;           //                  warped y
    var _viz;          //                  visible this frame

    function initialize(field, keep) {
        _field = field;
        _keep = keep;
        var n = GX * GY;
        _px = new [n];
        _py = new [n];
        _viz = new [n];
    }

    function render(dc, state) {
        var t = 0;
        if (state.hour != null && state.minute != null) {
            t = state.hour * 60 + state.minute;
        }
        var seed = _field.daySeed();
        var hr = (state.heartRate != null) ? state.heartRate : 55;
        var steps = (state.steps != null) ? state.steps : 0;

        var hrn256 = ((hr - 50) * 256) / 110;        // HR heat, 0..256
        if (hrn256 < 0) { hrn256 = 0; }
        if (hrn256 > 256) { hrn256 = 256; }

        var eff = _field.mov256();                   // warp drive
        var ur = (_field.unrest256() * 3) / 5;
        if (ur > eff) { eff = ur; }
        var amp16 = 32 + (144 * eff) / 256;          // 2..11 px, in 1/16 px

        // Day-seeded attractor orbit, confined to the sky band.
        var f1 = 2 + (GenArt.hash16(seed, 1, 0) % 3);
        var f2 = 3 + (GenArt.hash16(seed, 2, 0) % 3);
        var ax = 107 + (62 * GenArt.isin(GenArt.hash16(seed, 3, 0)
            + (t * f1 * 256) / 1560)) / 127;
        var ay = 28 + (34 * GenArt.isin(GenArt.hash16(seed, 4, 0)
            + (t * f2 * 256) / 2400)) / 127;

        // Wake threshold: per-dot hash under it = awake. Monotonic in steps,
        // so dots only ever join the flock as the day accumulates.
        var cs = (steps > 9000) ? 9000 : steps;
        var thresh = 100 + (924 * cs) / 9000;        // of 1024

        var n = GX * GY;
        var i;
        for (i = 0; i < n; i++) {
            _viz[i] = false;
            if ((GenArt.hash16(seed, i, 313) & 1023) >= thresh) { continue; }
            var ix = i % GX;
            var iy = i / GX;
            // Lattice warp: two incommensurate sines per axis (phases in
            // 1/256 turn) so the deformation never repeats visibly.
            var w = 2 * GenArt.isin(ix * 37 + (t * 53) / 10)
                  + GenArt.isin(iy * 69 + (t * 29) / 10);
            var x = X0 + ix * SX + (amp16 * w) / 6096;
            w = 2 * GenArt.isin(iy * 45 + (t * 45) / 10 + 81)
              + GenArt.isin(ix * 53 + t * 2);
            var y = Y0 + iy * SY + (amp16 * w) / 6096;

            var surf = 180 - _field.heightAtX(x);
            if (y > surf - 3) {
                if (y < surf + 6) {       // grazing: settles into the crust
                    dc.setColor(Gfx.COLOR_LT_GRAY, Gfx.COLOR_TRANSPARENT);
                    dc.fillRectangle(x, surf - 2, 1, 1);
                }
                continue;                 // deeper: buried, not drawn
            }
            if (_keep != null && x > _keep[0] && x < _keep[2]
                && y < _keep[3]) {
                continue;                 // the clock displaces the flock
            }
            _px[i] = x;
            _py[i] = y;
            _viz[i] = true;
        }

        // Filaments between lattice neighbors that drifted close.
        dc.setColor(Gfx.COLOR_DK_GRAY, Gfx.COLOR_TRANSPARENT);
        for (i = 0; i < n; i++) {
            if (!_viz[i]) { continue; }
            if ((i % GX) < GX - 1 && _viz[i + 1]) { filament(dc, i, i + 1); }
            if (i + GX < n && _viz[i + GX]) { filament(dc, i, i + GX); }
        }

        // Dots, sized by attractor distance, HR heat, pulse, and grain.
        for (i = 0; i < n; i++) {
            if (!_viz[i]) { continue; }
            var x = _px[i];
            var y = _py[i];
            var adx = x - ax;
            if (adx < 0) { adx = -adx; }
            var ady = y - ay;
            if (ady < 0) { ady = -ady; }
            var dist = (adx > ady) ? adx + (ady * 2) / 5
                                   : ady + (adx * 2) / 5;   // octagonal norm
            var base16 = 96 - (dist * 16) / 14;             // 6px at center
            if (base16 < 0) { base16 = 0; }
            var pulse16 = (hrn256 * GenArt.isin(t * 14
                + ((i % GX) + (i / GX)) * 41)) / 1016;      // +/- 2px
            var grain = 128 + (GenArt.hash16(seed, i, 47) & 255);
            var rad16 = (((base16 * (128 + hrn256)) / 256) + 14 + pulse16)
                * grain / 256;
            if (rad16 > 96) { rad16 = 96; }
            var col;
            if (rad16 > 58) {
                col = GenArt.ZONE_COLORS[GenArt.zoneIndex(state.heartRate)];
            } else if (rad16 > 35) {
                col = (hrn256 > 90) ? Gfx.COLOR_BLUE : Gfx.COLOR_DK_BLUE;
            } else if (rad16 > 19) {
                col = Gfx.COLOR_DK_BLUE;
            } else {
                col = Gfx.COLOR_DK_GRAY;
            }
            dc.setColor(col, Gfx.COLOR_TRANSPARENT);
            var r = rad16 / 16;
            if (r < 1) {
                dc.fillRectangle(x, y, 1, 1);
            } else {
                dc.fillCircle(x, y, r);
            }
        }
    }

    function filament(dc, i, j) {
        var dx = _px[i] - _px[j];
        var dy = _py[i] - _py[j];
        if (dx * dx + dy * dy < 169) {               // within 13 px
            dc.drawLine(_px[i], _py[i], _px[j], _py[j]);
        }
    }
}
