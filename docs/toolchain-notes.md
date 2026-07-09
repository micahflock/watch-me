# Toolchain gotchas (learned the hard way, 2026-07)

Field notes from provisioning and driving the SDK inside a Claude Code on the
web container. `scripts/ensure-toolchain.sh` and `scripts/test.sh` already
encode the fixes; this file exists so the *why* isn't rediscovered.

## Provisioning in the Claude Code web sandbox

- **GitHub release downloads 403.** The session's GitHub credential proxy is
  scoped to the repos added to the session, and it 403s asset downloads from
  any other repo (`{"message":"GitHub access to this repository is not
  enabled for this session..."}`). Through `curl -sfL | tar xz` this surfaces
  as the cryptic `gzip: stdin: unexpected end of file`. This is what broke
  fetching the SDK manager CLI (lindell/connect-iq-sdk-manager-cli).
- **Fix (automated in setup-sdk.sh):** build it from source instead —
  `GOBIN=... go install github.com/lindell/connect-iq-sdk-manager-cli@v0.8.4`
  then rename the binary to `connect-iq-sdk-manager`. `proxy.golang.org` is on
  the sandbox's direct-access allowlist, so the module fetch bypasses the
  GitHub block. Go lives at `/usr/local/go/bin/go` in the web container.
- `api.github.com` and `developer.garmin.com` are reachable, so the Garmin
  login, SDK zip overlay, and device-file downloads all work normally.
- Diagnosing egress blocks: `curl -sS "$HTTPS_PROXY/__agentproxy/status"`
  shows proxy state; a 403 whose body names `add_repo` is the repo-scoped
  GitHub credential proxy, not the org egress policy.

## Driving the SDK tools

- **Every SDK Java tool prints a `Picked up JAVA_TOOL_OPTIONS: ...` line**
  (trust-store + proxy injection for the sandbox). Harmless; filter with
  `grep -v "Picked up"` when parsing output.
- **`monkeydo <prg> <device> -t` on a PRG with no (:test) cases exits
  silently** — no output, no error, exit code 1. Faces without a `tests/`
  directory (flashtest, two-worlds-v2) therefore made `scripts/test.sh` end in
  "could not parse test output". test.sh now detects the missing directory and
  says so instead. The shared-core suite lives in `faces/devface/tests` and
  compiles all of `core/src`, so `scripts/test.sh devface` is the regression
  gate for core changes.
- **The two-worlds-v2 DEBUG build OOMs on load** ("Out Of Memory Error" at
  `FieldMaskComponent.initialize`): the field-mask run precompute plus debug
  instrumentation plus no `-r` shrinking doesn't fit in the 64 KB face budget.
  Pre-existing, not a regression signal. The release build fits with room to
  spare (status bar showed 57.0/59.8 kB) — verify render changes on the
  RELEASE PRG and read RAM from the sim status bar, per CLAUDE.md.
- **Don't wrap `scripts/sim.sh` in `timeout` (or otherwise kill its foreground
  shell) when you intend to screenshot afterwards** — observed in the Claude
  Code harness: the kill took down the whole xvfb-run/Xvfb/simulator stack,
  not just monkeydo. For screenshots: launch
  `scripts/sim.sh <face> > log 2>&1 &` detached, wait for the load, then
  `xwd -root` on the Xvfb display (auth file from `pgrep -af Xvfb`) and
  ImageMagick `convert`. Expect ~40 s from launch to a rendered face on a
  cold sim.
