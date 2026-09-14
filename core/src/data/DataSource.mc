using Toybox.System as Sys;
using Toybox.Time as Time;
using Toybox.Time.Gregorian as Greg;
using Toybox.ActivityMonitor as Act;
using Toybox.Lang as Lang;
using Toybox.Position as Pos;

// DataSource — assembles a Snapshot from Toybox APIs available at CIQ 2.4.
//
// Property reads (location) are SLOW (object store) so they are cached and
// refreshed only via reloadProperties() (startup + onSettingsChanged), never
// per tick. Activity/clock/system reads happen every refresh().
//
// Defensive throughout: every API touch is guarded so a missing capability or a
// null leaves the corresponding Snapshot field null.
module DataSource {

    // Minutes between GPS-cache polls. A watch face cannot turn the receiver
    // on, so the cached fix only changes when an activity ends -- but
    // Position.getInfo() allocates an Info (and toDegrees() an array of
    // Doubles), and onUpdate fires on every wrist raise, not just once a
    // minute. Polling on a WALL-CLOCK cadence keeps that garbage bounded no
    // matter how often the face is drawn.
    const GPS_POLL_MIN = 5;

    // A fix younger than this reads as current (one day: long enough that a
    // morning run still counts by bedtime, short enough that a fix from before
    // a flight does not).
    const GPS_FRESH_SEC = 86400;

    // Cached property values (refreshed on settings change / startup).
    var _lat = null;
    var _lon = null;

    // GPS opt-in. OFF by default, and a face must NOT turn it on unless its
    // manifest requests the Positioning permission, because calling
    // Position.getInfo() without it raises
    //     Error: Permission Required
    //     Details: Permission for module 'Toybox.Position' required
    // which is a hard app error, NOT a catchable Monkey C exception -- a
    // try/catch around the call does not stop it (verified: it took down the
    // devface test run, docs/gps-notes.md). This file compiles into every face
    // via core/src, so the opt-in is what keeps the permission-less ones alive.
    var _gpsEnabled = false;

    // Cached GPS fix (refreshed on the GPS_POLL_MIN cadence, never per tick).
    var _gpsLat = null;
    var _gpsLon = null;
    var _gpsQual = null;
    var _gpsWhen = null;      // Time.Moment of the fix, or null
    var _gpsPollAt = null;    // minute-of-day of the last poll

    // Let this face read the system's position cache. Call it from the app's
    // startup ONLY when the manifest requests Positioning (see _gpsEnabled).
    function enableGps(on) {
        _gpsEnabled = (on == true);
        if (!_gpsEnabled) {
            _gpsLat = null; _gpsLon = null; _gpsQual = null; _gpsWhen = null;
            _gpsPollAt = null;
        }
    }

    // Read app properties into the cache. `app` is the AppBase instance.
    function reloadProperties(app) {
        _lat = readFloatProp(app, "lat");
        _lon = readFloatProp(app, "lng");
    }

    function readFloatProp(app, key) {
        var v = app.getProperty(key);
        if (v == null) { return null; }
        // Treat the 0.0 default as "unset" for location to avoid pinning (0,0).
        if (v instanceof Lang.Float || v instanceof Lang.Number) {
            var f = v.toFloat();
            if (f == 0.0) { return null; }
            return f;
        }
        return null;
    }

    // Fill `snap` in place. Call once per onUpdate.
    function refresh(snap) {
        snap.clear();

        // --- clock + UTC offset ---
        var clock = Sys.getClockTime();
        if (clock != null) {
            snap.hour = clock.hour;
            snap.minute = clock.min;
            snap.second = clock.sec;
            snap.utcOffsetSec = clock.timeZoneOffset;
        }

        // --- date / day of week ---
        var now = Time.now();
        var info = Greg.info(now, Time.FORMAT_SHORT);
        if (info != null) {
            snap.year = info.year;
            snap.month = info.month;
            snap.day = info.day;
            snap.dayOfWeek = info.day_of_week; // 1=Sun..7=Sat
        }

        // --- activity ---
        var am = Act.getInfo();
        if (am != null) {
            if (am has :steps)     { snap.steps = am.steps; }
            if (am has :stepGoal)  { snap.stepGoal = am.stepGoal; }
            if (am has :distance)  { snap.distanceCm = am.distance; }
            if (am has :calories)  { snap.calories = am.calories; }
        }

        // --- heart rate: most recent valid sample from history ---
        snap.heartRate = readHeartRate();

        // --- system: battery + phone ---
        var stats = Sys.getSystemStats();
        if (stats != null && stats has :battery) {
            snap.batteryPct = stats.battery;
        }
        var ds = Sys.getDeviceSettings();
        if (ds != null) {
            if (ds has :phoneConnected) { snap.phoneConnected = ds.phoneConnected; }
            if (ds has :is24Hour)       { snap.is24Hour = ds.is24Hour; }
        }

        // --- location: the GPS fix when the device has one, else the
        //     user-entered properties. The fix wins because it is also
        //     CURRENT: the sun/north marker is wrong by a degree or two per
        //     100 km, so a stale hand-typed home location is the worse input
        //     the moment the wearer travels. docs/gps-notes.md.
        if (_gpsEnabled) {
            var nowMin = (snap.hour != null && snap.minute != null)
                         ? snap.hour * 60 + snap.minute : null;
            if (gpsPollDue(nowMin)) {
                readPosition();
                _gpsPollAt = nowMin;
            }
        }
        snap.gpsQuality = _gpsQual;
        snap.gpsFixAgeSec = fixAgeSec(now);
        if (_gpsLat != null && _gpsLon != null) {
            snap.lat = _gpsLat;
            snap.lon = _gpsLon;
            snap.locFromGps = true;
        } else {
            snap.lat = _lat;
            snap.lon = _lon;
            snap.locFromGps = false;
        }
    }

    // True when the fix cache is stale enough to re-read. Handles the midnight
    // wrap and a null clock (poll once, then wait for a readable clock).
    function gpsPollDue(nowMin) {
        if (_gpsPollAt == null) { return true; }
        if (nowMin == null) { return false; }
        var d = nowMin - _gpsPollAt;
        if (d < 0) { d += 1440; }
        return d >= GPS_POLL_MIN;
    }

    // Read the system's position cache into the fix fields. Only ever reached
    // with _gpsEnabled set (see above) -- the try/catch below is for the
    // ordinary failures (a device without the module, a malformed fix), NOT for
    // a missing permission, which no catch can save.
    function readPosition() {
        _gpsLat = null; _gpsLon = null; _gpsQual = null; _gpsWhen = null;
        if (!(Toybox has :Position)) { return; }
        try {
            var info = Pos.getInfo();
            if (info == null) { return; }
            if (info has :accuracy) { _gpsQual = info.accuracy; }
            if (info has :when)     { _gpsWhen = info.when; }
            if (!(info has :position) || info.position == null) { return; }
            var d = info.position.toDegrees();
            if (d == null || d.size() < 2 || d[0] == null || d[1] == null) {
                return;
            }
            var la = d[0].toFloat();
            var lo = d[1].toFloat();
            // Reject the sentinels: out of range, and the (0,0) "null island"
            // that readFloatProp already treats as unset.
            if (la < -90.0 || la > 90.0 || lo < -180.0 || lo > 180.0) { return; }
            if (la == 0.0 && lo == 0.0) { return; }
            _gpsLat = la;
            _gpsLon = lo;
        } catch (e) {
            _gpsLat = null; _gpsLon = null;
        }
    }

    // Seconds since the fix, or null. Reported only when a POSITION exists:
    // getInfo() fills `when` in even when it has nothing to report (verified
    // on the simulator, docs/gps-notes.md), so the timestamp alone would read
    // as a permanently fresh fix that does not exist.
    function fixAgeSec(now) {
        if (_gpsLat == null || _gpsWhen == null || now == null) { return null; }
        var s = now.value() - _gpsWhen.value();
        if (s < 0) { return 0; }
        return s;
    }

    // Most recent heart-rate sample, or null. getHeartRateHistory is API 1.2.1
    // and the canonical watch-face HR path for this device generation.
    function readHeartRate() {
        if (!(Act has :getHeartRateHistory)) { return null; }
        var it = Act.getHeartRateHistory(1, true); // newest first
        if (it == null) { return null; }
        var sample = it.next();
        if (sample == null) { return null; }
        var hr = sample.heartRate;
        if (hr == null) { return null; }
        if (Act has :INVALID_HR_SAMPLE && hr == Act.INVALID_HR_SAMPLE) {
            return null;
        }
        return hr;
    }
}
