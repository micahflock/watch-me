using Toybox.Application as App;

// MossState -- persist/restore the MossGrove day record across a watch-face
// reload, mirroring BioState. The record is an accretive day-long summary held
// only in RAM; a memory-tight device can tear the face down when a menu opens,
// and the day cannot be replayed, so it must be saved (onHide) and restored
// (onLayout) through the object store (AppBase getProperty/setProperty -- the
// sanctioned 2.4 path, NOT Application.Storage, which is CIQ 3.0+). The record
// is tiny (a few scalars + zoneMin[9] + episode pairs), so unlike the BioBloom
// dish it persists comfortably; everything is wrapped in try/catch so a store
// failure degrades to a fresh record rather than crashing the face.
module MossState {
    const KEY = "mossGrove";

    function save(grove) {
        if (grove == null) { return; }
        try {
            App.getApp().setProperty(KEY, grove.save());
        } catch (e) {
        }
    }

    function restore(grove) {
        if (grove == null) { return; }
        try {
            grove.load(App.getApp().getProperty(KEY));
        } catch (e) {
        }
    }
}
