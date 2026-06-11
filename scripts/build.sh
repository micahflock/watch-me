#!/usr/bin/env bash
# Build a face to a .prg.
#   scripts/build.sh <face> [--debug]
#
# <face> is a directory name under faces/ (e.g. devface).
# --debug uses debug.monkey.jungle (includes (:debug) code + tests) and emits
#         <face>-debug.prg; otherwise the release jungle → <face>.prg.
set -euo pipefail
. "$(dirname "$0")/env.sh"

FACE="${1:-devface}"
MODE="release"
if [ "${2:-}" = "--debug" ]; then MODE="debug"; fi

FACE_DIR="$REPO_ROOT/faces/$FACE"
[ -d "$FACE_DIR" ] || { echo "No such face: $FACE_DIR" >&2; exit 1; }

if [ "$MODE" = "debug" ]; then
  JUNGLE="$FACE_DIR/debug.monkey.jungle"
  OUT="$REPO_ROOT/bin/$FACE-debug.prg"
else
  JUNGLE="$FACE_DIR/monkey.jungle"
  OUT="$REPO_ROOT/bin/$FACE.prg"
fi

# Preflight
if [ ! -x "$MONKEYC" ]; then echo "monkeyc not found ($MONKEYC). Run scripts/setup-sdk.sh." >&2; exit 1; fi
if [ ! -f "$CIQ_KEY" ];  then echo "Developer key not found ($CIQ_KEY). Run scripts/gen-key.sh." >&2; exit 1; fi
if [ ! -d "$DEVICE_DIR" ]; then
  echo "Device files for $DEVICE not found ($DEVICE_DIR)." >&2
  echo "Run scripts/setup-sdk.sh with GARMIN_USERNAME/GARMIN_PASSWORD, or supply device files manually." >&2
  exit 1
fi

mkdir -p "$REPO_ROOT/bin"
echo "Building $FACE ($MODE) -> $OUT"
# -r selects a release build: strips (:debug), keeps (:release) stubs.
# Debug build omits -r (keeps (:debug)) and adds --unit-test for the test runner.
EXTRA=""
if [ "$MODE" = "release" ]; then
  EXTRA="-r"
else
  EXTRA="--unit-test"
fi
set -x
"$MONKEYC" -f "$JUNGLE" -d "$DEVICE" -o "$OUT" -y "$CIQ_KEY" -w -l 0 $EXTRA
set +x
echo "OK: $OUT"
