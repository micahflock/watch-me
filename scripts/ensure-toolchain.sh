#!/usr/bin/env bash
# Provision the full Connect IQ toolchain on demand: SDK manager CLI, Garmin
# agreement+login, SDK (with simulator), fr735xt device files, developer key,
# and the headless-simulator libraries.
#
# Called automatically by build.sh / test.sh / sim.sh when something is
# missing — nobody should need to remember the pipeline. Idempotent: when the
# toolchain is already present it exits immediately, and on Claude Code on the
# web the container state is cached, so the heavy downloads happen at most
# once per environment (on first use, not at session start).
#
# Requires GARMIN_USERNAME / GARMIN_PASSWORD in the environment for the
# login-gated device files (without them the SDK still installs, but builds
# for fr735xt cannot run).
set -uo pipefail
. "$(dirname "$0")/env.sh"

# Re-read the SDK location from .sdk-path (setup-sdk.sh may have just written
# it; the exported CIQ_SDK_HOME in this shell could predate that).
sdk_home() {
  if [ -f "$REPO_ROOT/.sdk-path" ]; then cat "$REPO_ROOT/.sdk-path"; else echo "$CIQ_SDK_HOME"; fi
}

toolchain_ready() {
  local SDK
  SDK="$(sdk_home)"
  [ -x "$SDK/bin/monkeyc" ] && [ -f "$CIQ_KEY" ] && [ -d "$DEVICE_DIR" ] \
    && [ -x "$SDK/bin/simulator" ] \
    && [ -f "$CIQ_SIM_LIBS/libwebkit2gtk-4.0.so.37" ] \
    && ciq_sim_libs_resolve "$SDK/bin/simulator"
}

if toolchain_ready; then
  exit 0
fi

echo "== Provisioning Connect IQ toolchain (first use in this container) =="
"$(dirname "$0")/setup-sdk.sh"      || echo "WARNING: setup-sdk.sh failed." >&2
"$(dirname "$0")/gen-key.sh"        || echo "WARNING: gen-key.sh failed." >&2
"$(dirname "$0")/setup-sim-libs.sh" || echo "WARNING: setup-sim-libs.sh failed." >&2

if toolchain_ready; then
  echo "== Toolchain ready =="
else
  echo "WARNING: toolchain still incomplete — see messages above." >&2
  exit 1
fi
