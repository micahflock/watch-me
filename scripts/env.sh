#!/usr/bin/env bash
# Shared environment for all watch-me build/sim/test scripts.
# Source this: `. scripts/env.sh` (it is sourced, not executed).
#
# Override any of these by exporting them before sourcing, e.g.:
#   CIQ_SDK_HOME=/opt/ciq-sdk . scripts/env.sh

# --- Repo layout -------------------------------------------------------------
# REPO_ROOT = directory containing this scripts/ folder's parent.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT

# --- Target device (the ONLY device this framework targets) ------------------
# SDK device id is "fr735xt" (the marketing name is "Forerunner 735XT"). This id
# must match the manifest product id and the monkeyc -d flag and the device-files
# directory name under ~/.Garmin/ConnectIQ/Devices/.
export DEVICE="fr735xt"

# --- SDK location ------------------------------------------------------------
# The setup-sdk.sh script extracts the SDK under ~/ciq-sdk/sdk by default.
# Order of resolution: explicit CIQ_SDK_HOME env > .sdk-path file > default.
if [ -z "${CIQ_SDK_HOME:-}" ]; then
  if [ -f "$REPO_ROOT/.sdk-path" ]; then
    CIQ_SDK_HOME="$(cat "$REPO_ROOT/.sdk-path")"
  else
    CIQ_SDK_HOME="$HOME/ciq-sdk/sdk"
  fi
fi
export CIQ_SDK_HOME
export MONKEYC="$CIQ_SDK_HOME/bin/monkeyc"
export MONKEYDO="$CIQ_SDK_HOME/bin/monkeydo"
export CONNECTIQ="$CIQ_SDK_HOME/bin/connectiq"

# --- Developer key (kept OUTSIDE the repo) -----------------------------------
export CIQ_KEY_DIR="${CIQ_KEY_DIR:-$HOME/.ciq-keys}"
export CIQ_KEY="$CIQ_KEY_DIR/developer_key.der"

# --- Device files (downloaded by the SDK manager CLI) ------------------------
# The CLI / SDK Manager installs device profiles here.
export CIQ_DEVICES_DIR="${CIQ_DEVICES_DIR:-$HOME/.Garmin/ConnectIQ/Devices}"
export DEVICE_DIR="$CIQ_DEVICES_DIR/$DEVICE"

# --- Simulator compatibility libs (see scripts/setup-sim-libs.sh) ------------
# Legacy webkit2gtk-4.0 stack needed by the Linux simulator on modern distros.
export CIQ_SIM_LIBS="${CIQ_SIM_LIBS:-$HOME/ciq-tools/webkit40-libs}"

# Prepend the compat libs to LD_LIBRARY_PATH if present (no-op otherwise).
ciq_sim_env() {
  if [ -d "$CIQ_SIM_LIBS" ]; then
    export LD_LIBRARY_PATH="$CIQ_SIM_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
}

# --- Convenience: report whether we can do a real build ----------------------
# Sets CIQ_CAN_BUILD=1 when SDK + key + device files are all present.
ciq_can_build() {
  [ -x "$MONKEYC" ] && [ -f "$CIQ_KEY" ] && [ -d "$DEVICE_DIR" ]
}

# Start the simulator under a virtual X display if it is not already running.
# Usage: ciq_start_sim  (logs to /tmp/ciq_sim.log; waits briefly for boot)
ciq_start_sim() {
  if pgrep -f "bin/simulator" >/dev/null 2>&1; then
    return 0
  fi
  command -v xvfb-run >/dev/null || { echo "xvfb-run not installed" >&2; return 1; }
  ciq_sim_env
  ( xvfb-run -a "$CIQ_SDK_HOME/bin/simulator" >/tmp/ciq_sim.log 2>&1 & )
  # Give the sim time to open its IPC socket.
  sleep 10
  pgrep -f "bin/simulator" >/dev/null 2>&1
}
