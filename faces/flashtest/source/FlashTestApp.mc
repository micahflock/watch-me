using Toybox.Application as App;

// FlashTestApp — entry point for the sideload-verification face. Nothing but
// the lifecycle minimum: no properties, no persistence, no settings handling.
class FlashTestApp extends App.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        return [ new FlashTestView() ];
    }
}
