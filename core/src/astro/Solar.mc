using Toybox.Math as Math;

// Solar — sun position (azimuth/elevation) and sunrise/sunset from
// (lat, lon, UTC date/time). NOAA-style algorithm in single-precision Float.
// Pure: depends only on Toybox.Math (1.0.0 calls) and MathX hand-rolls, so it
// is fully unit-testable. No GPS/clock/Toybox.Time dependency — the caller
// passes time in.
//
// Accuracy: NOAA simplified equations in 32-bit floats land within ~1-2 minutes
// for sunrise/sunset and a fraction of a degree for position — ample for a
// watch face. Tests pin fixtures at +/-3 min.
module Solar {

    // Degrees<->radians using Math.PI (safe).
    function rad(d) { return d * Math.PI / 180.0; }
    function deg(r) { return r * 180.0 / Math.PI; }

    // Julian Day for a Gregorian calendar date at 00:00 UTC (Meeus).
    function julianDay(year, month, day) {
        var y = year;
        var m = month;
        if (m <= 2) { y -= 1; m += 12; }
        var A = y / 100;
        var B = 2 - A + (A / 4);
        return MathX.floor(365.25 * (y + 4716)).toNumber()
             + MathX.floor(30.6001 * (m + 1)).toNumber()
             + day + B - 1524;
    }

    // Julian centuries since J2000 for a JD + fractional day (UTC hours).
    function julianCentury(jd, utcHours) {
        var jdt = jd.toFloat() + (utcHours - 12.0) / 24.0;
        return (jdt - 2451545.0) / 36525.0;
    }

    // Returns [azimuthDeg (0=N, 90=E), elevationDeg]. utcHours is 0..24.
    function position(jd, utcHours, latDeg, lonDeg) {
        var T = julianCentury(jd, utcHours);

        var L0 = norm360(280.46646 + T * (36000.76983 + T * 0.0003032));
        var M = 357.52911 + T * (35999.05029 - 0.0001537 * T);
        var Mr = rad(M);
        var C = (1.914602 - T * (0.004817 + 0.000014 * T)) * sin(Mr)
              + (0.019993 - 0.000101 * T) * sin(2.0 * Mr)
              + 0.000289 * sin(3.0 * Mr);
        var trueLong = L0 + C;
        var omega = 125.04 - 1934.136 * T;
        var lambda = trueLong - 0.00569 - 0.00478 * sin(rad(omega));

        var epsilon0 = 23.0 + (26.0 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60.0) / 60.0;
        var epsilon = epsilon0 + 0.00256 * cos(rad(omega));

        var lambdaR = rad(lambda);
        var declR = Math.asin(sin(rad(epsilon)) * sin(lambdaR));

        // Equation of time (minutes).
        var y = tanSq(rad(epsilon / 2.0));
        var L0r = rad(L0);
        var eqTime = 4.0 * deg(
              y * sin(2.0 * L0r)
            - 2.0 * 0.016708634 * sin(Mr)
            + 4.0 * 0.016708634 * y * sin(Mr) * cos(2.0 * L0r)
            - 0.5 * y * y * sin(4.0 * L0r)
            - 1.25 * 0.016708634 * 0.016708634 * sin(2.0 * Mr));

        // True solar time -> hour angle.
        var trueSolarMin = MathX.fmod(utcHours * 60.0 + eqTime + 4.0 * lonDeg, 1440.0);
        var ha;
        if (trueSolarMin / 4.0 < 0.0) { ha = trueSolarMin / 4.0 + 180.0; }
        else { ha = trueSolarMin / 4.0 - 180.0; }
        var haR = rad(ha);

        var latR = rad(latDeg);
        var zenithR = Math.acos(
            sin(latR) * sin(declR) + cos(latR) * cos(declR) * cos(haR));
        var elevation = 90.0 - deg(zenithR);

        // Azimuth (from North, clockwise).
        var azDenom = cos(latR) * sin(zenithR);
        var azimuth;
        if (abs(azDenom) > 0.000001) {
            var azR = Math.acos(MathX.clampf(
                (sin(latR) * cos(zenithR) - sin(declR)) / azDenom, -1.0, 1.0));
            azimuth = deg(azR);
            if (ha > 0.0) { azimuth = norm360(azimuth + 180.0); }
            else { azimuth = norm360(540.0 - azimuth); }
        } else {
            azimuth = (latDeg > 0.0) ? 180.0 : 0.0;
        }
        return [azimuth, elevation];
    }

    // Returns [sunriseUtcMinutes, sunsetUtcMinutes] for the date, or null if the
    // sun does not rise/set (polar day/night) at that latitude.
    function sunTimes(jd, latDeg, lonDeg) {
        var T = julianCentury(jd, 12.0); // approximate at local noon
        var L0 = norm360(280.46646 + T * (36000.76983 + T * 0.0003032));
        var M = 357.52911 + T * (35999.05029 - 0.0001537 * T);
        var Mr = rad(M);
        var C = (1.914602 - T * (0.004817 + 0.000014 * T)) * sin(Mr)
              + (0.019993 - 0.000101 * T) * sin(2.0 * Mr)
              + 0.000289 * sin(3.0 * Mr);
        var trueLong = L0 + C;
        var omega = 125.04 - 1934.136 * T;
        var lambda = trueLong - 0.00569 - 0.00478 * sin(rad(omega));
        var epsilon0 = 23.0 + (26.0 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60.0) / 60.0;
        var epsilon = epsilon0 + 0.00256 * cos(rad(omega));
        var declR = Math.asin(sin(rad(epsilon)) * sin(rad(lambda)));

        var y = tanSq(rad(epsilon / 2.0));
        var L0r = rad(L0);
        var eqTime = 4.0 * deg(
              y * sin(2.0 * L0r)
            - 2.0 * 0.016708634 * sin(Mr)
            + 4.0 * 0.016708634 * y * sin(Mr) * cos(2.0 * L0r)
            - 0.5 * y * y * sin(4.0 * L0r)
            - 1.25 * 0.016708634 * 0.016708634 * sin(2.0 * Mr));

        var latR = rad(latDeg);
        // Hour angle of sunrise for the standard -0.833 deg solar disc/refraction.
        var cosH = cos(rad(90.833)) / (cos(latR) * cos(declR)) - tanT(latR) * tanT(declR);
        if (cosH > 1.0 || cosH < -1.0) {
            return null; // polar day or night
        }
        var haDeg = deg(Math.acos(cosH));

        var noonMin = 720.0 - 4.0 * lonDeg - eqTime; // solar noon (UTC minutes)
        var sunrise = noonMin - haDeg * 4.0;
        var sunset = noonMin + haDeg * 4.0;
        return [sunrise, sunset];
    }

    // Convert UTC minutes-of-day to local minutes-of-day given UTC offset (sec).
    function toLocalMinutes(utcMin, utcOffsetSec) {
        var m = utcMin + utcOffsetSec / 60.0;
        m = MathX.fmod(m, 1440.0);
        if (m < 0.0) { m += 1440.0; }
        return m;
    }

    // --- small math helpers (kept local to avoid Math.atan2 etc.) ------------
    function sin(x) { return Math.sin(x); }
    function cos(x) { return Math.cos(x); }
    function tanT(x) { return Math.sin(x) / Math.cos(x); }
    function tanSq(x) { var t = tanT(x); return t * t; }
    function abs(x) { return (x < 0.0) ? -x : x; }
    function norm360(d) {
        var v = MathX.fmod(d, 360.0);
        if (v < 0.0) { v += 360.0; }
        return v;
    }
}
