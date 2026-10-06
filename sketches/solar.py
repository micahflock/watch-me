#!/usr/bin/env python3
"""Line-for-line port of core/src/astro/Solar.mc + SunCompass.mc (+ the MathX
hand-rolls they use) for the sandbox.

Monkey C `Float` is 32-bit and its float literals are Floats, so the default
mode evaluates every operation in numpy float32 (NumPy >= 2 / NEP 50: a Python
float literal is "weak" and adopts the float32 operand's type, exactly like a
Monkey C Float literal). float64=True runs the same code in doubles, to show
the single-precision error is irrelevant at marker scale (< 0.05 deg).

Notable float32 behavior this reproduces: Solar.julianCentury adds the day
fraction to a ~2.46e6 JD held in a Float, whose ulp is 0.25 day, so T (the
slow terms: declination, equation of time) steps every 6 h. The hour angle
uses utcHours directly, so position still tracks the minute.

    python3 sketches/solar.py      # self-check against the TestSolar/TestSunCompass fixtures
"""

import math

import numpy as np

_F = np.float32


def set_float64(on):
    """Switch the whole port between Monkey C float32 (default) and doubles."""
    global _F
    _F = np.float64 if on else np.float32


def F(x):
    return _F(x)


# --------------------------------------------------------------- MathX.mc ----

def mx_floor(x):
    """MathX.floor: truncate (toNumber), step down for negative non-integers."""
    n = int(x)                       # toNumber() truncates toward zero
    f = F(n)
    if x < 0.0 and f != x:
        f -= 1.0
    return f


def mx_fmod(x, m):
    return x - mx_floor(x / m) * m


def mx_clampf(v, lo, hi):
    if v < lo:
        return F(lo)
    if v > hi:
        return F(hi)
    return v


# --------------------------------------------------------------- Solar.mc ----

def _pi():
    return F(math.pi)                # Math.PI


def rad(d):
    return d * _pi() / 180.0


def deg(r):
    return r * 180.0 / _pi()


def _sin(x):
    return np.sin(x)


def _cos(x):
    return np.cos(x)


def _tan(x):
    return np.sin(x) / np.cos(x)


def _tan_sq(x):
    t = _tan(x)
    return t * t


def _abs(x):
    return -x if x < 0.0 else x


def norm360(d):
    v = mx_fmod(d, 360.0)
    if v < 0.0:
        v += 360.0
    return v


def _idiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def julian_day(year, month, day):
    """Solar.julianDay (integer Number result)."""
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    A = _idiv(y, 100)
    B = 2 - A + _idiv(A, 4)
    return (int(mx_floor(F(365.25) * (y + 4716)))
            + int(mx_floor(F(30.6001) * (m + 1)))
            + day + B - 1524)


def julian_century(jd, utc_hours):
    jdt = F(jd) + (utc_hours - 12.0) / 24.0
    return (jdt - 2451545.0) / 36525.0


def position(jd, utc_hours, lat_deg, lon_deg):
    """Solar.position -> (azimuthDeg 0=N 90=E, elevationDeg)."""
    utc_hours = F(utc_hours)
    lat_deg = F(lat_deg)
    lon_deg = F(lon_deg)
    T = julian_century(jd, utc_hours)

    L0 = norm360(280.46646 + T * (36000.76983 + T * 0.0003032))
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    Mr = rad(M)
    C = ((1.914602 - T * (0.004817 + 0.000014 * T)) * _sin(Mr)
         + (0.019993 - 0.000101 * T) * _sin(2.0 * Mr)
         + 0.000289 * _sin(3.0 * Mr))
    true_long = L0 + C
    omega = 125.04 - 1934.136 * T
    lam = true_long - 0.00569 - 0.00478 * _sin(rad(omega))

    eps0 = 23.0 + (26.0 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * _cos(rad(omega))

    lam_r = rad(lam)
    decl_r = np.arcsin(_sin(rad(eps)) * _sin(lam_r))

    y = _tan_sq(rad(eps / 2.0))
    L0r = rad(L0)
    eq_time = 4.0 * deg(
        y * _sin(2.0 * L0r)
        - 2.0 * 0.016708634 * _sin(Mr)
        + 4.0 * 0.016708634 * y * _sin(Mr) * _cos(2.0 * L0r)
        - 0.5 * y * y * _sin(4.0 * L0r)
        - 1.25 * 0.016708634 * 0.016708634 * _sin(2.0 * Mr))

    true_solar_min = mx_fmod(utc_hours * 60.0 + eq_time + 4.0 * lon_deg, 1440.0)
    if true_solar_min / 4.0 < 0.0:
        ha = true_solar_min / 4.0 + 180.0
    else:
        ha = true_solar_min / 4.0 - 180.0
    ha_r = rad(ha)

    lat_r = rad(lat_deg)
    # Math.acos of |x| > 1 is NaN on the watch; only reachable at the exact
    # zenith/nadir, so clamp rather than raise.
    zen_arg = _sin(lat_r) * _sin(decl_r) + _cos(lat_r) * _cos(decl_r) * _cos(ha_r)
    zenith_r = np.arccos(np.clip(zen_arg, -1.0, 1.0))
    elevation = 90.0 - deg(zenith_r)

    az_denom = _cos(lat_r) * _sin(zenith_r)
    if _abs(az_denom) > 0.000001:
        az_r = np.arccos(mx_clampf(
            (_sin(lat_r) * _cos(zenith_r) - _sin(decl_r)) / az_denom, -1.0, 1.0))
        azimuth = deg(az_r)
        if ha > 0.0:
            azimuth = norm360(azimuth + 180.0)
        else:
            azimuth = norm360(540.0 - azimuth)
    else:
        azimuth = F(180.0) if lat_deg > 0.0 else F(0.0)
    return azimuth, elevation


def sun_times(jd, lat_deg, lon_deg):
    """Solar.sunTimes -> (sunriseUtcMin, sunsetUtcMin) or None (polar)."""
    lat_deg = F(lat_deg)
    lon_deg = F(lon_deg)
    T = julian_century(jd, F(12.0))
    L0 = norm360(280.46646 + T * (36000.76983 + T * 0.0003032))
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    Mr = rad(M)
    C = ((1.914602 - T * (0.004817 + 0.000014 * T)) * _sin(Mr)
         + (0.019993 - 0.000101 * T) * _sin(2.0 * Mr)
         + 0.000289 * _sin(3.0 * Mr))
    true_long = L0 + C
    omega = 125.04 - 1934.136 * T
    lam = true_long - 0.00569 - 0.00478 * _sin(rad(omega))
    eps0 = 23.0 + (26.0 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * _cos(rad(omega))
    decl_r = np.arcsin(_sin(rad(eps)) * _sin(rad(lam)))

    y = _tan_sq(rad(eps / 2.0))
    L0r = rad(L0)
    eq_time = 4.0 * deg(
        y * _sin(2.0 * L0r)
        - 2.0 * 0.016708634 * _sin(Mr)
        + 4.0 * 0.016708634 * y * _sin(Mr) * _cos(2.0 * L0r)
        - 0.5 * y * y * _sin(4.0 * L0r)
        - 1.25 * 0.016708634 * 0.016708634 * _sin(2.0 * Mr))

    lat_r = rad(lat_deg)
    cos_h = _cos(rad(F(90.833))) / (_cos(lat_r) * _cos(decl_r)) - _tan(lat_r) * _tan(decl_r)
    if cos_h > 1.0 or cos_h < -1.0:
        return None
    ha_deg = deg(np.arccos(cos_h))
    noon_min = 720.0 - 4.0 * lon_deg - eq_time
    return noon_min - ha_deg * 4.0, noon_min + ha_deg * 4.0


# ----------------------------------------------------------- SunCompass.mc ---

def north_dial(azimuth_deg):
    return norm360(360.0 - azimuth_deg)


def compute(year, month, day, hour, minute, utc_offset_sec, lat_deg, lon_deg):
    """SunCompass.compute -> (northDialDeg, elevationDeg) or None."""
    if None in (year, month, day, hour, minute, lat_deg, lon_deg):
        return None
    off_sec = utc_offset_sec if utc_offset_sec is not None else 0
    jd = julian_day(year, month, day)
    utc_min = F(hour) * 60.0 + minute - off_sec / F(60.0)
    if utc_min < 0.0:
        utc_min += 1440.0
        jd -= 1
    elif utc_min >= 1440.0:
        utc_min -= 1440.0
        jd += 1
    az, el = position(jd, utc_min / 60.0, lat_deg, lon_deg)
    return north_dial(az), el


def sightable(elev):
    """NorthComponent.render's gate: drawn only for elevation in (-0.833, 80)."""
    return -0.833 < elev < 80.0


# ------------------------------------------------------------- self-check ----

def _selfcheck():
    assert julian_day(2000, 1, 1) in (2451544, 2451545)
    jd = julian_day(2026, 3, 20)
    rise, sset = sun_times(jd, 51.48, 0.0)
    assert 330 < rise < 390 and 1070 < sset < 1120, (rise, sset)
    assert sun_times(julian_day(2026, 12, 21), 80.0, 0.0) is None
    az, el = position(julian_day(2026, 6, 21), 12.0, 51.48, 0.0)
    assert 0.0 <= az <= 360.0 and 50.0 < el < 65.0, (az, el)
    d, el = compute(2026, 6, 21, 12, 0, 0, 51.48, 0.0)
    assert abs(d - 180.0) < 8.0 and 50.0 < el < 65.0, (d, el)
    d, el = compute(2026, 6, 21, 12, 0, 36000, -33.87, 151.21)
    assert (d < 20.0 or d > 340.0) and 20.0 < el < 40.0, (d, el)
    via = compute(2026, 6, 21, 0, 30, 7200, 51.48, 0.0)
    az, el = position(julian_day(2026, 6, 20), 22.5, 51.48, 0.0)
    assert abs(via[0] - north_dial(az)) < 0.01 and abs(via[1] - el) < 0.01
    assert compute(2026, 6, 21, 12, 0, 0, None, None) is None
    # float32 vs float64: the single-precision error is far below a pixel.
    worst = 0.0
    for t in range(0, 1440, 7):
        a32 = compute(2026, 10, 6, t // 60, t % 60, -25200, 45.5126, -122.6387)
        set_float64(True)
        a64 = compute(2026, 10, 6, t // 60, t % 60, -25200, 45.5126, -122.6387)
        set_float64(False)
        dd = abs((float(a32[0]) - float(a64[0]) + 180.0) % 360.0 - 180.0)
        worst = max(worst, dd)
    print("solar.py fixtures OK; worst float32-vs-float64 north-dial diff on "
          "2026-10-06 Portland: {:.4f} deg".format(worst))


if __name__ == "__main__":
    _selfcheck()
