using Toybox.Application as App;
using Toybox.WatchUi as Ui;

// DevFaceApp — application entry point for the devface integration testbed.
// Wires the CIQ 2.x lifecycle: initial view, settings-changed reload, and
// optional sim-state persistence via the object store (getProperty/setProperty;
// NOT Application.Storage, which is CIQ 3.0+).
class DevFaceApp extends App.AppBase {

    var _view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        DataSource.reloadProperties(self);
        _view = new DevFaceView();
        return [ _view ];
    }

    // Fired when settings change in Garmin Connect (since CIQ 2.1). Reload the
    // cached properties and force a redraw.
    function onSettingsChanged() {
        DataSource.reloadProperties(self);
        if (_view != null) { _view.onSettingsChanged(); }
        Ui.requestUpdate();
    }

    // Persist minimal sim state on stop, if the user enabled it.
    function onStop(state) {
        if (DataSource.simPersist() && _view != null) {
            var s = _view.serializeSim();
            if (s != null) { setProperty("simState", s); }
        }
    }

    // Restore previously persisted sim state (read by the view on layout).
    function loadSimState() {
        return getProperty("simState");
    }
}
