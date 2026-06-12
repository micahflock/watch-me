#!/usr/bin/env bash
# Build the debug/unit-test PRG and run the Connect IQ unit tests headlessly.
#   scripts/test.sh [face]
#
# Two layers:
#   1. Static lint: grep the source for API-3.0+ symbols that must never appear
#      in a 2.4 project. Fails fast, needs no SDK.
#   2. Run No Evil: build with --unit-test and run via `monkeydo -t`, then parse
#      the output for PASSED/FAILED to set the exit code.
set -uo pipefail
. "$(dirname "$0")/env.sh"

FACE="${1:-devface}"
RC=0

# --- 1. Forbidden-symbol lint (no SDK needed) --------------------------------
echo "== API-2.4 forbidden-symbol lint =="
# These were all introduced in CIQ 3.0+ (or are otherwise off-limits at 2.4) and
# will fail on fr735xt firmware. Comments are stripped before matching so docs
# may freely mention the symbols (e.g. "never use Math.atan2").
FORBIDDEN='Application\.Storage|Application\.Properties|WatchUi\.Layer|Toybox\.Complications|Complications\.|onPartialUpdate|Toybox\.Background|^[[:space:]]*import[[:space:]]|Math\.atan2'
LINT_FAIL=0
while IFS= read -r f; do
  # Strip // line comments, then grep the remainder.
  HITS=$(sed 's://.*$::' "$f" | grep -nE "$FORBIDDEN" || true)
  if [ -n "$HITS" ]; then
    echo "$f:"; echo "$HITS"
    LINT_FAIL=1
  fi
done < <(find "$REPO_ROOT/core/src" "$REPO_ROOT/faces/$FACE/source" -name '*.mc' 2>/dev/null)
if [ "$LINT_FAIL" = "1" ]; then
  echo "FAIL: forbidden CIQ-3.0+ symbol(s) found above." >&2
  RC=1
else
  echo "OK: no forbidden symbols."
fi

# --- 2. Run No Evil unit tests -----------------------------------------------
# Provision the toolchain on demand before deciding whether to skip.
if ! ciq_can_build; then
  ciq_ensure_toolchain || true
fi
if ! ciq_can_build; then
  echo
  echo "SKIP: unit-test run (SDK, key, or device files missing)."
  echo "      Static lint result stands. Run scripts/setup-sdk.sh + gen-key.sh to enable."
  exit $RC
fi

echo
echo "== Building unit-test PRG =="
"$REPO_ROOT/scripts/build.sh" "$FACE" --debug || { echo "Build failed." >&2; exit 1; }

PRG="$REPO_ROOT/bin/$FACE-debug.prg"
echo
echo "== Running unit tests in simulator =="
ciq_start_sim fresh || { echo "Simulator failed to start; see /tmp/ciq_sim.log" >&2; exit 1; }

ciq_sim_env
OUT="$(mktemp)"
timeout 180 "$MONKEYDO" "$PRG" "$DEVICE" -t 2>&1 | tee "$OUT" || true

echo
# Run No Evil prints a final "PASSED (passed=N, ...)" / "FAILED (...)" summary.
if grep -qE "^FAILED" "$OUT"; then
  echo "RESULT: tests FAILED"; RC=1
elif grep -qE "^PASSED" "$OUT"; then
  echo "RESULT: tests PASSED"
else
  echo "RESULT: could not parse test output (see above)"; RC=1
fi
rm -f "$OUT"
exit $RC
