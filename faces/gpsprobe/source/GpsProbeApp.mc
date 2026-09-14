using Toybox.Application as App;

// GpsProbeApp — entry point for the Position probe face. Lifecycle minimum:
// no properties, no persistence, no settings (the probe must not depend on
// anything that could itself explain a blank reading).
class GpsProbeApp extends App.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        return [ new GpsProbeView() ];
    }
}
