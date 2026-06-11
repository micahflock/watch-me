#!/usr/bin/env bash
# Generate a Connect IQ developer signing key.
#
# Connect IQ apps are signed with a 4096-bit RSA key, supplied to monkeyc as a
# PKCS#8 DER file via `-y`. The key is the developer's identity in the Connect
# IQ Store; it must be kept private and is therefore stored OUTSIDE the repo
# (default: ~/.ciq-keys/) and git-ignored.
#
# Re-running this script will NOT overwrite an existing key (your published
# apps are tied to it). Delete the key manually if you truly want a new one.
set -euo pipefail
. "$(dirname "$0")/env.sh"

mkdir -p "$CIQ_KEY_DIR"
chmod 700 "$CIQ_KEY_DIR"

PEM="$CIQ_KEY_DIR/developer_key.pem"

if [ -f "$CIQ_KEY" ]; then
  echo "Key already exists: $CIQ_KEY (leaving it alone)."
  exit 0
fi

echo "Generating 4096-bit RSA developer key..."
openssl genrsa -out "$PEM" 4096
echo "Converting to PKCS#8 DER (the format monkeyc -y expects)..."
openssl pkcs8 -topk8 -inform PEM -outform DER -nocrypt -in "$PEM" -out "$CIQ_KEY"
chmod 600 "$PEM" "$CIQ_KEY"

echo "Done."
echo "  PEM (keep safe): $PEM"
echo "  DER (used by build): $CIQ_KEY"
echo "Both are outside the repo and matched by .gitignore. Never commit them."
