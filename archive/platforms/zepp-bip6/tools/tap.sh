#!/usr/bin/env bash
# tap.sh X Y : wake the watch (Enter), then touch screen pixel (X, Y).
# Needs `boot.sh window` and xdotool. The QEMU window has a 25 px menu bar.
set -eu
: "${ZRUN:?}"
here=$(cd "$(dirname -- "$0")" && pwd)
export DISPLAY=:77
python3 -I "$here/mon.py" "$ZRUN/mon.sock" "sendkey ret" "sleep 0.7"
xdotool mousemove "$1" $(( $2 + 25 )) mousedown 1 sleep 0.08 mouseup 1
