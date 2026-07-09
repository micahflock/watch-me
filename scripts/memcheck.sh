#!/usr/bin/env bash
# Read the watch-face memory limit for fr735xt from the device's
# compiler.json and report the working ceiling (90%) plus the current PRG size.
#   scripts/memcheck.sh [face]
#
# Note: the PRG on-disk size is the code+resource footprint, NOT runtime RAM.
# Runtime peak memory is measured live by the (:debug) Instrument overlay in the
# simulator. This script reports the static budget; use --debug sim for runtime.
set -euo pipefail
. "$(dirname "$0")/env.sh"

FACE="${1:-devface}"
CJ="$DEVICE_DIR/compiler.json"

if [ ! -f "$CJ" ]; then
  echo "compiler.json not found at $CJ" >&2
  echo "Device files are required to read the real memory limit. Run scripts/setup-sdk.sh." >&2
  exit 1
fi

# The watch-face memory limit lives under the device's memory limits. Field
# names have varied across SDK generations; probe the likely locations.
LIMIT="$(jq -r '
  ( .appTypes[]? | select(.type=="watchface" or .type=="watchFace") | .memoryLimit )
  // ( .memoryLimits.watchface )
  // ( .partNumbers[]?.memoryLimits?.watchface )
  // empty' "$CJ" 2>/dev/null | head -1)"

if [ -z "$LIMIT" ] || [ "$LIMIT" = "null" ]; then
  echo "Could not auto-locate the watch-face memory limit in $CJ."
  echo "Inspect it manually:  jq . '$CJ' | less"
  exit 1
fi

CEIL=$(( LIMIT * 90 / 100 ))
echo "Device:               $DEVICE"
echo "Watch-face mem limit: $LIMIT bytes ($(( LIMIT / 1024 )) KB)"
echo "Working ceiling (90%): $CEIL bytes ($(( CEIL / 1024 )) KB)"

PRG="$REPO_ROOT/bin/$FACE.prg"
if [ -f "$PRG" ]; then
  SZ=$(stat -c%s "$PRG")
  echo "PRG on disk ($FACE):   $SZ bytes ($(( SZ / 1024 )) KB)  [code+resources, not runtime RAM]"
fi
