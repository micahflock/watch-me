using Toybox.Graphics as Gfx;

// Compositor — an ordered list of components drawn back-to-front every onUpdate.
//
// A "component" is any object with a render(dc, state) method (duck-typed; no
// base class, to keep the symbol/metadata footprint small). Each component may
// have an optional clip rect [x,y,w,h]; when present the Dc is clipped to it
// for that component's render call (Dc.setClip is API 2.3, safe at 2.4).
//
// Keep-out regions are reserved screen areas that background layers should not
// draw into; components that support masking can ask the Compositor for them.
class Compositor {
    var _components; // Array of component objects
    var _clips;      // parallel Array: clip rect [x,y,w,h] or null
    var _keepOuts;   // Array of reserved rects [x,y,w,h]
    var _bg;         // background color

    function initialize() {
        _components = [];
        _clips = [];
        _keepOuts = [];
        _bg = Gfx.COLOR_BLACK;
    }

    function setBackground(color) { _bg = color; }

    // Add a component, optionally clipped to rect [x,y,w,h] (or null).
    function add(component, clip) {
        _components.add(component);
        _clips.add(clip);
    }

    // Register a reserved rect that maskable layers avoid.
    function addKeepOut(rect) { _keepOuts.add(rect); }
    function keepOuts() { return _keepOuts; }

    // Draw the full frame. Called once per onUpdate (per minute in low power).
    function renderAll(dc, state) {
        dc.setColor(_bg, _bg);
        dc.clear();
        for (var i = 0; i < _components.size(); i++) {
            var clip = _clips[i];
            if (clip != null) {
                dc.setClip(clip[0], clip[1], clip[2], clip[3]);
            }
            _components[i].render(dc, state);
            if (clip != null) {
                dc.clearClip();
            }
        }
    }

    function size() { return _components.size(); }
}
