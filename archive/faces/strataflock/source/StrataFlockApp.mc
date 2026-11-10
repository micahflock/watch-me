using Toybox.Application as App;
using Toybox.WatchUi as Ui;

// StrataFlockApp — entry point for the strata+flock generative face.
class StrataFlockApp extends App.AppBase {

    var _view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        DataSource.reloadProperties(self);
        _view = new StrataFlockView();
        return [ _view ];
    }

    function onSettingsChanged() {
        DataSource.reloadProperties(self);
        if (_view != null) { _view.onSettingsChanged(); }
        Ui.requestUpdate();
    }
}
