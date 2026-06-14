using Toybox.Application as App;
using Toybox.WatchUi as Ui;

// BioBloomApp — entry point for the "living dish" generative biometric face.
class BioBloomApp extends App.AppBase {

    var _view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        DataSource.reloadProperties(self);
        _view = new BioBloomView();
        return [ _view ];
    }

    function onSettingsChanged() {
        DataSource.reloadProperties(self);
        if (_view != null) { _view.onSettingsChanged(); }
        Ui.requestUpdate();
    }
}
