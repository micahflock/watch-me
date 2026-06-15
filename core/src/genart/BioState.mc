using Toybox.Application as App;

// BioState — persist/restore the BioBloom dish across a watch-face reload.
//
// The dish is an accretive day-long simulation held only in RAM; a memory-tight
// device can tear the watch face down when a menu opens, and the simulation
// cannot replay the day, so it would come back blank. The view saves on onHide
// and restores in onLayout, going through the object store (AppBase
// getProperty/setProperty -- the sanctioned 2.4 path, NOT Application.Storage,
// which is CIQ 3.0+). Wrapped in try/catch so a store failure or oversized
// payload degrades to a fresh dish rather than crashing the face.
module BioState {
    const KEY = "bioDish";

    function save(bloom) {
        if (bloom == null) { return; }
        try {
            App.getApp().setProperty(KEY, bloom.save());
        } catch (e) {
        }
    }

    function restore(bloom) {
        if (bloom == null) { return; }
        try {
            bloom.load(App.getApp().getProperty(KEY));
        } catch (e) {
        }
    }
}
