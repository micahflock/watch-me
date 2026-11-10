using Toybox.Application as App;
using Toybox.WatchUi as Ui;

// TwoWorldsApp — application entry point. Wires the CIQ 2.x lifecycle: initial
// view and settings-changed reload via the object store (getProperty/setProperty;
// NOT Application.Properties, which is CIQ 3.0+). Location (lat/lng) feeds the
// sun-derived true-north marker.
class TwoWorldsApp extends App.AppBase {

    var _view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        DataSource.reloadProperties(self);
        _view = new TwoWorldsView();
        return [ _view ];
    }

    // Fired when settings change in Garmin Connect (since CIQ 2.1). Reload the
    // cached location properties and force a redraw.
    function onSettingsChanged() {
        DataSource.reloadProperties(self);
        if (_view != null) { _view.onSettingsChanged(); }
        Ui.requestUpdate();
    }
}
