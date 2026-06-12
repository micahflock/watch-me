using Toybox.System as Sys;
using Toybox.Time as Time;
using Toybox.Time.Gregorian as Greg;
using Toybox.ActivityMonitor as Act;
using Toybox.Lang as Lang;

// DataSource — assembles a Snapshot from Toybox APIs available at CIQ 2.4.
//
// Property reads (location) are SLOW (object store) so they are cached and
// refreshed only via reloadProperties() (startup + onSettingsChanged), never
// per tick. Activity/clock/system reads happen every refresh().
//
// Defensive throughout: every API touch is guarded so a missing capability or a
// null leaves the corresponding Snapshot field null.
module DataSource {

    // Cached property values (refreshed on settings change / startup).
    var _lat = null;
    var _lon = null;

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
        if (ds != null && ds has :phoneConnected) {
            snap.phoneConnected = ds.phoneConnected;
        }

        // --- location (cached property) ---
        snap.lat = _lat;
        snap.lon = _lon;
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
