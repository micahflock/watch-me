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
  echo "SDK manager CLI not found at $MGR — fetching v0.8.4 from GitHub..."
  mkdir -p "$(dirname "$MGR")"
  curl -sfL "https://github.com/lindell/connect-iq-sdk-manager-cli/releases/download/v0.8.4/connect-iq-sdk-manager-cli_0.8.4_Linux_x86_64.tar.gz" \
    | tar xz -C "$(dirname "$MGR")" connect-iq-sdk-manager
  [ -x "$MGR" ] || { echo "ERROR: could not install the SDK manager CLI." >&2; exit 1; }
fi

# --- Login (device files require it) -----------------------------------------
# NOTE: the CLI requires the agreement to be accepted BEFORE login succeeds
# (login errors with "agreement is not accepted" otherwise), so accept first.
if [ -n "${GARMIN_USERNAME:-}" ] && [ -n "${GARMIN_PASSWORD:-}" ]; then
  echo "Accepting SDK agreement..."
  "$MGR" agreement accept || echo "(agreement accept returned nonzero; continuing)"
  echo "Logging in to Garmin as $GARMIN_USERNAME ..."
  "$MGR" login --username "$GARMIN_USERNAME" --password "$GARMIN_PASSWORD"
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

# --- Simulator binary --------------------------------------------------------
# The SDK manager CLI's download omits bin/simulator (verified with v0.8.4 /
# SDK 9.2.0). The official zip — same version stamp as the SDK directory name —
# contains it; overlay the zip onto the installed SDK when it's missing.
if [ ! -x "$CHOSEN_SDK/bin/simulator" ]; then
  STAMP="$(basename "$CHOSEN_SDK")"
  URL="https://developer.garmin.com/downloads/connect-iq/sdks/${STAMP}.zip"
  echo "Simulator missing from CLI download; overlaying official zip:"
  echo "  $URL"
  TMPZ="$(mktemp /tmp/ciq-sdk-XXXXXX.zip)"
  if curl -sfL -o "$TMPZ" "$URL" && unzip -oq "$TMPZ" -d "$CHOSEN_SDK"; then
    echo "Simulator installed: $CHOSEN_SDK/bin/simulator"
  else
    echo "WARNING: could not fetch the official SDK zip; builds work, sim won't." >&2
  fi
  rm -f "$TMPZ"
fi

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
