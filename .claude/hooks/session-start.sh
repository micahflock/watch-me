#!/bin/bash
# SessionStart hook for Claude Code on the web: stand up the full Connect IQ
# toolchain (SDK + fr735xt device files + signing key + simulator libs) so
# builds, unit tests, and the headless simulator work from the first prompt.
#
# The container state is CACHED after this hook completes, so the ~200 MB SDK
# download happens once per environment, not once per session — every step
# below is idempotent and near-instant on a warm container.
#
# Requires GARMIN_USERNAME / GARMIN_PASSWORD in the environment (configure
# them as environment variables in the Claude Code environment settings);
# without them the SDK still installs but the login-gated fr735xt device
# files cannot be fetched, and the hook says so rather than failing.
set -uo pipefail

# Local sessions manage their own SDK installs; this is web-container-only.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
. scripts/env.sh

echo "== watch-me session setup =="

# Fast path: everything present (warm/cached container).
if ciq_can_build && [ -x "$CIQ_SDK_HOME/bin/simulator" ] \
    && [ -f "${CIQ_SIM_LIBS}/libwebkit2gtk-4.0.so.37" ]; then
  echo "Toolchain already present (cached container) — nothing to do."
  echo "  SDK:    $CIQ_SDK_HOME"
  echo "  Device: $DEVICE_DIR"
  exit 0
fi

if [ -z "${GARMIN_USERNAME:-}" ] || [ -z "${GARMIN_PASSWORD:-}" ]; then
  echo "NOTE: GARMIN_USERNAME / GARMIN_PASSWORD not set in this environment."
  echo "      The SDK will install, but the login-gated fr735xt device files"
  echo "      will be missing and builds will not run. Add the credentials as"
  echo "      environment variables in the environment settings."
fi

# 1. SDK manager CLI + agreement/login + SDK + simulator overlay + device files.
#    setup-sdk.sh is idempotent and self-heals a missing simulator binary.
scripts/setup-sdk.sh || echo "WARNING: setup-sdk.sh failed; builds may not work."

# 2. Developer signing key (no-op if one exists; lives outside the repo).
scripts/gen-key.sh || echo "WARNING: gen-key.sh failed."

# 3. Headless-simulator libraries (webkit-4.0 stack + gst/enchant/webp deps).
scripts/setup-sim-libs.sh || echo "WARNING: setup-sim-libs.sh failed; sim may not start."

# Summary.
if ciq_can_build; then
  echo "OK: monkeyc, device files, and signing key ready."
  [ -x "$CIQ_SDK_HOME/bin/simulator" ] && echo "OK: simulator binary present."
else
  echo "WARNING: toolchain incomplete — see messages above."
fi
exit 0
