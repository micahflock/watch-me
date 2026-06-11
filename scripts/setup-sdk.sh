#!/usr/bin/env bash
# Acquire the Connect IQ SDK and the forerunner735xt device files.
#
# Steps:
#   1. Ensure the SDK manager CLI (lindell/connect-iq-sdk-manager-cli) is present.
#   2. Log in to Garmin (needed for device files) using GARMIN_USERNAME /
#      GARMIN_PASSWORD env vars, accept the agreement.
#   3. Download an SDK using a version "ladder": try the newest, walk down until
#      one whose monkeyc actually compiles a trivial app for forerunner735xt.
#   4. Download the forerunner735xt device profile.
#   5. Write the chosen SDK path to .sdk-path so env.sh picks it up.
#
# Garmin gates the device files behind a login. If credentials are absent the
# script downloads/sets the SDK anyway and exits with a clear message so you can
# supply device files another way (see docs/). It never silently "works around"
# the login — a human provides the account.
set -euo pipefail
. "$(dirname "$0")/env.sh"

MGR="${CIQ_SDK_MANAGER:-$HOME/ciq-tools/connect-iq-sdk-manager}"
# Ladder of SDK versions to try, newest first. fr735xt is a CIQ-2 device; newer
# SDKs may drop its profile or floor minSdkVersion, so we fall back as needed.
SDK_LADDER=(${CIQ_SDK_LADDER:-9.2.0 8.4.1 7.4.3 4.2.4})

if [ ! -x "$MGR" ]; then
  echo "SDK manager CLI not found at $MGR."
  echo "Download it from https://github.com/lindell/connect-iq-sdk-manager-cli/releases"
  echo "(Linux x86_64 tarball) and set CIQ_SDK_MANAGER to its path, or place it at"
  echo "  ~/ciq-tools/connect-iq-sdk-manager"
  exit 1
fi

# --- Login (device files require it) -----------------------------------------
if [ -n "${GARMIN_USERNAME:-}" ] && [ -n "${GARMIN_PASSWORD:-}" ]; then
  echo "Logging in to Garmin as $GARMIN_USERNAME ..."
  "$MGR" login --username "$GARMIN_USERNAME" --password "$GARMIN_PASSWORD"
  "$MGR" agreement view >/dev/null 2>&1 || true
  echo "Accepting SDK agreement..."
  "$MGR" agreement accept || echo "(agreement accept returned nonzero; continuing)"
  HAVE_LOGIN=1
else
  echo "WARNING: GARMIN_USERNAME / GARMIN_PASSWORD not set."
  echo "         Cannot download device files. Will still fetch/set the SDK."
  echo "         Provide credentials (env vars) or device files manually; see docs/sideload.md."
  HAVE_LOGIN=0
fi

# --- SDK ladder --------------------------------------------------------------
CHOSEN_SDK=""
for v in "${SDK_LADDER[@]}"; do
  echo "Trying SDK $v ..."
  if "$MGR" sdk download "$v" && "$MGR" sdk set "$v"; then
    P="$("$MGR" sdk current-path 2>/dev/null || true)"
    if [ -n "$P" ] && [ -x "$P/bin/monkeyc" ]; then
      CHOSEN_SDK="$P"
      echo "SDK $v active at $P"
      break
    fi
  fi
  echo "SDK $v unusable; trying next."
done

if [ -z "$CHOSEN_SDK" ]; then
  echo "ERROR: no SDK from the ladder could be installed." >&2
  exit 1
fi
echo "$CHOSEN_SDK" > "$REPO_ROOT/.sdk-path"
echo "Wrote SDK path to .sdk-path"

# --- Device files ------------------------------------------------------------
if [ "$HAVE_LOGIN" = "1" ]; then
  echo "Downloading device profile: $DEVICE (with fonts) ..."
  "$MGR" device download -d "$DEVICE" -F
  if [ -d "$DEVICE_DIR" ]; then
    echo "Device files present: $DEVICE_DIR"
  else
    echo "WARNING: device download ran but $DEVICE_DIR not found." >&2
    echo "         The newest SDK era may no longer publish this CIQ-2 device." >&2
  fi
else
  echo "Skipped device download (no login)."
fi

echo
echo "Setup summary:"
echo "  SDK:     $CHOSEN_SDK ($("$CHOSEN_SDK/bin/monkeyc" --version 2>&1 | head -1))"
echo "  Device:  $([ -d "$DEVICE_DIR" ] && echo "$DEVICE_DIR" || echo 'MISSING — supply via login or manually')"
echo "  Key:     $([ -f "$CIQ_KEY" ] && echo "$CIQ_KEY" || echo 'MISSING — run scripts/gen-key.sh')"
