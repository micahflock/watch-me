#!/bin/bash
# SessionStart hook for Claude Code on the web: report toolchain state in one
# second — it does NOT install anything, so cold sessions start instantly.
#
# Provisioning is lazy instead: scripts/build.sh, test.sh, and sim.sh call
# scripts/ensure-toolchain.sh automatically the first time the SDK is needed
# (it requires GARMIN_USERNAME / GARMIN_PASSWORD from the environment
# settings for the login-gated device files). The container state is cached
# after that first run, so the ~200 MB of downloads happen at most once per
# environment.
set -uo pipefail

# Local sessions manage their own SDK installs; this is web-container-only.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
. scripts/env.sh

echo "== watch-me session =="
if ciq_can_build && [ -x "$CIQ_SDK_HOME/bin/simulator" ]; then
  echo "CIQ toolchain ready (cached container)."
  echo "  SDK:    $CIQ_SDK_HOME"
  echo "  Device: $DEVICE_DIR"
else
  echo "CIQ toolchain not provisioned in this container yet."
  echo "It installs itself on the first scripts/build.sh / test.sh / sim.sh run"
  echo "(via scripts/ensure-toolchain.sh, using GARMIN_USERNAME/GARMIN_PASSWORD"
  echo "from the environment). No action needed."
fi
if [ -z "${GARMIN_USERNAME:-}" ] || [ -z "${GARMIN_PASSWORD:-}" ]; then
  echo "NOTE: GARMIN_USERNAME / GARMIN_PASSWORD are not set — device files"
  echo "      cannot be fetched, so fr735xt builds will not run."
fi
exit 0
