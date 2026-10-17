using Toybox.System as Sys;
using Toybox.Time as Time;
using Toybox.Time.Gregorian as Greg;
using Toybox.ActivityMonitor as Act;
using Toybox.Activity as Activity;
using Toybox.Position as Position;
using Toybox.Application as App;
using Toybox.Lang as Lang;

// DataSource — assembles a Snapshot from Toybox APIs available at CIQ 2.4.
//
// Property reads (location) are SLOW (object store) so they are cached and
// refreshed only via reloadProperties() (startup + onSettingsChanged), never
// per tick. Activity/clock/system reads happen every refresh().
//
// Defensive throughout: every API touch is guarded so a missing capability or a
// null leaves the corresponding Snapshot field null.
//
// Location: GPS ALWAYS wins, the user-entered lat/lng properties are the
// fallback (owner, 2026-10). Position.getInfo() reports the device's LAST
// KNOWN position -- in practice the fix from the most recent GPS activity --
// without switching GPS on; Activity.Info.currentLocation is the fallback.
// Both need the Positioning permission in the face's manifest: without it
// the fr735xt hands a watch face no position at all (wrist, 2026-10: the pip
// stayed grey after a GPS run; the diag build, with the permission, read the
// fix from both). A fix carries no trusted age, so the face remembers it
// saw (micro-degrees) and WHEN it first saw it change, persisted in the object
// store; recency (Snapshot.gpsFix) derives from that stamp. The remembered fix
// also covers a device that forgets its position (e.g. after a reboot).
module DataSource {

    // Cached property values (refreshed on settings change / startup).
    var _lat = null;
    var _lon = null;

    // Remembered GPS fix (see header). _gStamp 0 = age unknown (first fix the
    // face ever saw, e.g. right after install) -> reads stale, never fresh.
    const GPS_KEY = "gpsFix";
    const GPS_FRESH_SEC = 86400;   // fresh = fix changed within the last 24 h
    const GPS_SAVE_GAP = 600;      // min seconds between object-store writes
    var _gLat = null;              // Number micro-degrees, or null (no fix yet)
    var _gLon = null;
    var _gStamp = 0;               // epoch sec the current fix was first seen
    var _gDirty = false;           // fix changed since the last write
    var _gSaved = 0;               // epoch sec of the last write

    // Read app properties into the cache. `app` is the AppBase instance.
    function reloadProperties(app) {
        _lat = readFloatProp(app, "lat");
        _lon = readFloatProp(app, "lng");
        if (_gLat == null) { loadGps(app); }   // RAM fix is newer than the store
    }

    // Restore the remembered fix [latE6, lonE6, stampSec]; a malformed record
    // is ignored (the next fix the device reports re-seeds it).
    function loadGps(app) {
        try {
            var a = app.getProperty(GPS_KEY);
            if (a instanceof Lang.Array && a.size() == 3
                    && a[0] instanceof Lang.Number && a[1] instanceof Lang.Number
                    && a[2] instanceof Lang.Number) {
                _gLat = a[0]; _gLon = a[1]; _gStamp = a[2];
            }
        } catch (e) {
        }
    }

    // Pick up the device's last known position; a CHANGED fix is stamped with
    // `nowSec` (the first fix ever seen gets stamp 0: its age is unknown).
    // Persists the change, but at most once per GPS_SAVE_GAP: a fix arrives
    // ~once per GPS activity, the gap only bounds flash writes should a device
    // ever report a jittering position outside an activity.
    function readGps(nowSec) {
        try {
            var loc = null;
            var pi = Position.getInfo();
            if (pi != null) { loc = pi.position; }
            if (loc == null) {
                var info = Activity.getActivityInfo();
                if (info != null && info has :currentLocation) {
                    loc = info.currentLocation;
                }
            }
            if (loc != null) {
                var d = loc.toDegrees();
                noteFix((d[0] * 1000000.0).toNumber(),
                        (d[1] * 1000000.0).toNumber(), nowSec);
            }
        } catch (e) {
        }
        if (_gDirty && (nowSec - _gSaved >= GPS_SAVE_GAP || nowSec < _gSaved)) {
            try {
                App.getApp().setProperty(GPS_KEY, [_gLat, _gLon, _gStamp]);
            } catch (e) {
            }
            _gDirty = false;
            _gSaved = nowSec;
        }
    }

    // Remember a reported fix (micro-degrees); a CHANGED valid fix is stamped
    // `nowSec`, except the first fix ever seen, whose age is unknown (stamp 0).
    function noteFix(la, lo, nowSec) {
        if (validFix(la, lo) && (la != _gLat || lo != _gLon)) {
            _gStamp = (_gLat == null) ? 0 : nowSec;
            _gLat = la; _gLon = lo;
            _gDirty = true;
        }
    }

    // Snapshot location: the remembered GPS fix wins, the lat/lng properties
    // are the fallback; gpsFix reports the fix's recency either way.
    function fillLocation(snap, nowSec) {
        snap.gpsFix = gpsState(nowSec);
        if (_gLat != null) {
            snap.lat = _gLat / 1000000.0;
            snap.lon = _gLon / 1000000.0;
        } else {
            snap.lat = _lat;
            snap.lon = _lon;
        }
    }

    // In range and not a "no fix" sentinel ((0,0), or the 180/180 some
    // firmwares report): micro-degrees.
    function validFix(la, lo) {
        if (la > 90000000 || la < -90000000) { return false; }
        if (lo > 180000000 || lo < -180000000) { return false; }
        return !(la == 0 && lo == 0);
    }

    // 0 = no fix ever seen, 1 = stale (older than 24 h or age unknown),
    // 2 = fresh. A clock that moved back before the stamp reads stale.
    function gpsState(nowSec) {
        if (_gLat == null) { return 0; }
        if (_gStamp <= 0) { return 1; }
        var age = nowSec - _gStamp;
        return (age >= 0 && age < GPS_FRESH_SEC) ? 2 : 1;
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

        // --- location: remembered GPS fix wins, property is the fallback ---
        var nowSec = now.value();
        readGps(nowSec);
        fillLocation(snap, nowSec);
    }

    // Per-minute HR for n minutes of TODAY starting at minute-of-day fromMin,
    // into buf[0..n-1], from the device HR history: each minute takes the
    // latest valid sample at or before its end, carried forward (null before
    // the first one). Feeds MossGrove's gap replay -- the face does not run
    // while an activity app records, so a workout arrives as a minute gap.
    // History is read OLDEST-first over a Duration window ending now and the
    // walk stops once the n minutes are filled, so the cost is ~n/(sample
    // spacing) iterator steps. False when there is no history API or no
    // sample in the window at all: the caller then collapses the gap as
    // before. A chunk older than the history reaches (a long ride) is still
    // true, its minutes null (no HR -> no episode).
    function hrMinutes(buf, fromMin, n, state) {
        var any = false;
        try {
            if (Act has :getHeartRateHistory && state.hour != null
                    && state.minute != null) {
                var nowSec = Time.now().value();
                var sec = (state.second != null) ? state.second : 0;
                var t0 = nowSec - (state.hour * 3600 + state.minute * 60 + sec)
                         + fromMin * 60;
                var span = nowSec - t0 + 60;
                if (span < 60) { span = 60; }
                var it = Act.getHeartRateHistory(new Time.Duration(span), false);
                var bad = (Act has :INVALID_HR_SAMPLE) ? Act.INVALID_HR_SAMPLE : 255;
                var cur = null;
                var k = 0;
                var smp = (it != null) ? it.next() : null;
                while (k < n) {
                    if (smp != null && smp.when != null
                            && smp.when.value() < t0 + (k + 1) * 60) {
                        var hr = smp.heartRate;
                        if (hr != null && hr != bad && hr > 0) {
                            cur = hr; any = true;
                        }
                        smp = it.next();
                    } else {
                        buf[k] = cur;
                        k++;
                    }
                }
                if (smp != null) { any = true; }   // history goes on past it
            }
        } catch (e) {
            any = false;
        }
        if (!any) {
            for (var k = 0; k < n; k++) { buf[k] = null; }
        }
        return any;
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
