using Toybox.Application as App;
using Toybox.WatchUi as Ui;

// TwoWorldsV2App — application entry point for the V2 face. Same lifecycle as
// TwoWorldsApp; location (lat/lng) feeds the sun-derived true-north marker.
class TwoWorldsV2App extends App.AppBase {

    var _view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        // This face's manifest requests Positioning, so it -- and only it --
        // may read the system's position cache. See DataSource._gpsEnabled:
        // calling Position without the permission is an uncatchable app error.
        DataSource.enableGps(true);
        DataSource.reloadProperties(self);
        _view = new TwoWorldsV2View();
        return [ _view ];
    }

    function onSettingsChanged() {
        DataSource.reloadProperties(self);
        if (_view != null) { _view.onSettingsChanged(); }
        Ui.requestUpdate();
    }
}
