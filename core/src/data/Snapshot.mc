// Snapshot — one frame's worth of device state, assembled per onUpdate.
//
// A plain class with public vars (one allocation, refreshed in place each tick
// to avoid per-minute garbage). EVERY field is nullable; renderers must tolerate
// missing data (e.g. HR unavailable, location unset). DataSource.refresh fills
// it; components only read it.
class Snapshot {
    // Clock
    var hour;          // 0..23 (Number) or null
    var minute;        // 0..59
    var second;        // 0..59 (whole-minute cadence, but available)
    var utcOffsetSec;  // local offset from UTC in seconds
    var is24Hour;      // device clock setting (Boolean); null -> treat as 24h

    // Date
    var year;          // e.g. 2026
    var month;         // 1..12
    var day;           // 1..31
    var dayOfWeek;     // 1=Sunday .. 7=Saturday (Gregorian FORMAT_SHORT)

    // Activity
    var steps;         // Number or null
    var stepGoal;
    var distanceCm;    // hundredths of a metre (ActivityMonitor raw units)
    var calories;      // kcal

    // Physio
    var heartRate;     // most recent bpm sample, or null if none valid

    // System
    var batteryPct;    // 0..100 Float
    var phoneConnected; // Boolean

    // Location. A watch face cannot turn the GPS on, but it can read the fix
    // the system already holds, so lat/lon is the BEST available position: the
    // fix when there is one, the user-entered lat/lng properties otherwise.
    // Renderers that only need a position (the sun/north marker) read lat/lon
    // and ignore the rest; the GPS indicator reads the rest. docs/gps-notes.md.
    var lat;           // Float degrees or null
    var lon;           // Float degrees or null
    var locFromGps;    // Boolean: lat/lon came from a fix, not the properties
    var gpsQuality;    // Position.QUALITY_* (Number), or null if unreadable
    var gpsFixAgeSec;  // seconds since the fix; null when there is no fix, or
                       // when the fix carries no timestamp

    function initialize() {
        clear();
    }

    // Reset all fields to null (called at the top of each refresh so a failed
    // read leaves the field null rather than stale).
    function clear() {
        hour = null; minute = null; second = null; utcOffsetSec = null;
        is24Hour = null;
        year = null; month = null; day = null; dayOfWeek = null;
        steps = null; stepGoal = null; distanceCm = null; calories = null;
        heartRate = null;
        batteryPct = null; phoneConnected = null;
        lat = null; lon = null;
        locFromGps = null; gpsQuality = null; gpsFixAgeSec = null;
    }
}
