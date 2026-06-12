#!/usr/bin/env bash
# Launch the Connect IQ simulator (headless via Xvfb if no display) and run a
# face on it.
#   scripts/sim.sh <face> [--debug]
#
# Uses ciq_start_sim from env.sh: starts the simulator under xvfb-run with the
# webkit-4.0 compatibility libs (scripts/setup-sim-libs.sh) when present. Each
# invocation restarts the simulator: pushing a PRG onto an already-running sim
# hangs monkeydo with no output (SDK 9.2.0 headless, observed repeatedly).
# App console output (Sys.println / instrumentation) prints to this terminal.
#
# To stop the simulator: pkill -f bin/simulator
set -euo pipefail
. "$(dirname "$0")/env.sh"

FACE="${1:-devface}"
SUFFIX=""
if [ "${2:-}" = "--debug" ]; then SUFFIX="-debug"; fi
PRG="$REPO_ROOT/bin/$FACE$SUFFIX.prg"

[ -f "$PRG" ] || { echo "PRG not found: $PRG. Build it first (scripts/build.sh $FACE ${2:-})." >&2; exit 1; }

echo "Starting a fresh simulator (PRG loads onto a reused sim flake)..."
ciq_start_sim fresh || { echo "Simulator failed to start; see /tmp/ciq_sim.log" >&2; exit 1; }

ciq_sim_env
echo "Loading $PRG onto $DEVICE ... (Ctrl-C detaches; sim keeps running)"
"$MONKEYDO" "$PRG" "$DEVICE"
