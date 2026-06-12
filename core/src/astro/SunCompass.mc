// SunCompass — true-north direction from sun position, for a device with no
// magnetometer (fr735xt has none; heading exists only inside GPS activities).
//
// Convention: the wearer points the 12 o'clock mark of the watch at the sun
// (the rose draws a sun marker there as the aiming reference). With the sun's
// azimuth A known from (date, time, lat, lon), true north then sits at dial
// angle (360 - A) measured clockwise from 12. Pure math on top of Solar —
// no Toybox dependencies beyond what Solar already uses, fully unit-testable.
module SunCompass {

    // Dial angle of true north (degrees clockwise from the 12 o'clock mark)
    // when 12 o'clock points at the sun. azimuthDeg is 0=N, 90=E.
    function northDial(azimuthDeg) {
        return Solar.norm360(360.0 - azimuthDeg);
    }

    // Full pipeline from Snapshot-shaped inputs (local civil date/time plus the
    // UTC offset, as DataSource fills them). Returns [northDialDeg,
    // elevationDeg], or null when any required input is missing. The caller
    // decides usability from elevation (below the horizon or near the zenith
    // the sun can't be sighted / azimuth is degenerate).
    // Allocates one short-lived 2-element array per call (once per minute).
    function compute(year, month, day, hour, minute, utcOffsetSec, latDeg, lonDeg) {
        if (year == null || month == null || day == null
            || hour == null || minute == null
            || latDeg == null || lonDeg == null) {
            return null;
        }
        var offSec = (utcOffsetSec != null) ? utcOffsetSec : 0;

        // Local civil date/time -> UTC, carrying rollover into the Julian Day
        // (snap's date fields are the LOCAL date; Solar wants UTC).
        var jd = Solar.julianDay(year, month, day);
        var utcMin = hour * 60.0 + minute - offSec / 60.0;
        if (utcMin < 0.0) {
            utcMin += 1440.0;
            jd -= 1;
        } else if (utcMin >= 1440.0) {
            utcMin -= 1440.0;
            jd += 1;
        }

        var pos = Solar.position(jd, utcMin / 60.0, latDeg, lonDeg);
        return [northDial(pos[0]), pos[1]];
    }
}
