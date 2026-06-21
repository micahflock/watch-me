#!/usr/bin/env bash
# Provide the legacy GTK/WebKit libraries the Connect IQ simulator needs on
# modern Linux distros.
#
# Why: the Linux simulator links against libwebkit2gtk-4.0 (the libsoup2-based
# ABI). Ubuntu 24.04+ only ships libwebkit2gtk-4.1 (libsoup3); symlinking 4.1 to
# 4.0 CRASHES with "libsoup2 symbols detected" because both soup generations end
# up in one process. The fix is to fetch the genuine 4.0 packages from Ubuntu
# 22.04 (jammy) and expose them via LD_LIBRARY_PATH — no system changes needed.
#
# Also needed from the distro itself (apt): libsecret-1-0 libusb-1.0-0
# libsoup2.4-1 (jammy-era webkit pulls them in at runtime), plus the
# gst/enchant/manette/wayland/webp set webkit dlopens. x11-apps (xwd) and
# imagemagick (convert) provide the status-bar screenshot path, which is the
# only way to read RAM for a release build (it stubs out the Instrument
# console line) on the headless sim.
#
# Output: $CIQ_SIM_LIBS (default ~/ciq-tools/webkit40-libs). sim.sh/test.sh add
# it to LD_LIBRARY_PATH automatically when it exists.
set -euo pipefail
. "$(dirname "$0")/env.sh"

DEST="${CIQ_SIM_LIBS:-$HOME/ciq-tools/webkit40-libs}"

# Distro packages first (also needed on cached containers where DEST already
# exists). The gst/enchant/manette/wayland/webp set is what the SDK 9.2.0
# simulator dlopens beyond webkit itself (found via ldd "not found" probing).
APT="apt-get"
[ "$(id -u)" != "0" ] && APT="sudo apt-get"
echo "Installing distro runtime deps (best effort)..."
# Refresh the index first: a fresh container ships a stale package list, and
# without this the install 404s on a moved point release (e.g. libegl-mesa0)
# and the whole apt step fails silently, leaving the sim libs missing.
$APT update -qq 2>/dev/null || echo "(apt update failed; continuing with the cached index)"
$APT install -y -qq libsecret-1-0 libusb-1.0-0 libsoup2.4-1 xvfb \
  libwebpmux3 libwebpdemux2 libgstreamer-gl1.0-0 libenchant-2-2 \
  libmanette-0.2-0 libwayland-server0 x11-apps imagemagick 2>/dev/null \
  || echo "(apt install failed or unavailable; continuing — packages may already exist)"

if [ -f "$DEST/libwebkit2gtk-4.0.so.37" ]; then
  echo "Already set up: $DEST"
  exit 0
fi

command -v dpkg-deb >/dev/null || { echo "dpkg-deb required" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

J="http://archive.ubuntu.com/ubuntu/pool/main"
DEBS=(
  "$J/w/webkit2gtk/libwebkit2gtk-4.0-37_2.50.4-0ubuntu0.22.04.1_amd64.deb"
  "$J/w/webkit2gtk/libjavascriptcoregtk-4.0-18_2.50.4-0ubuntu0.22.04.1_amd64.deb"
  "$J/i/icu/libicu70_70.1-2_amd64.deb"
  "$J/w/woff2/libwoff1_1.0.2-2build1_amd64.deb"
)
for u in "${DEBS[@]}"; do
  echo "Fetching $(basename "$u")"
  curl -sfL -O "$u" || { echo "Download failed: $u" >&2; exit 1; }
done

mkdir -p ext
for f in *.deb; do dpkg-deb -x "$f" ext/; done
mkdir -p "$DEST"
cp -a ext/usr/lib/x86_64-linux-gnu/. "$DEST/"

echo "Done. Simulator libs at: $DEST"
echo "sim.sh and test.sh pick this up automatically via CIQ_SIM_LIBS."
