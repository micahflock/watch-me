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
    const BREACH = "bioBreach";   // 1 when the last save() could not persist

    function save(bloom) {
        if (bloom == null) { return; }
        var ok = false;
        try {
            App.getApp().setProperty(KEY, bloom.save());
            ok = true;                       // built AND stored the dish
        } catch (e) {
        }
        // Record whether the dish outgrew what we can persist (OOM building the
        // array, or the object store rejecting an oversized payload). This tiny
        // write succeeds even when the big one didn't, and the view surfaces it.
        try {
            App.getApp().setProperty(BREACH, ok ? 0 : 1);
        } catch (e2) {
        }
    }

    function restore(bloom) {
        if (bloom == null) { return; }
        try {
            bloom.load(App.getApp().getProperty(KEY));
        } catch (e) {
        }
    }

    // True if the last save() failed -> the dish could not be contained and will
    // not survive a reload. Read once at layout (object-store reads are slow).
    function breached() {
        try {
            return App.getApp().getProperty(BREACH) == 1;
        } catch (e) {
            return false;
        }
    }
}
