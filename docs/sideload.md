# Sideloading onto the watch

The FR735XT mounts as USB mass storage; a watch face is just a `.prg` copied
into place.

1. Build a **release** PRG: `scripts/build.sh devface`
   (debug builds also work but are larger and chattier).
2. Connect the watch over USB. It appears as a `GARMIN` volume
   (on Linux typically auto-mounted under `/media/$USER/GARMIN`).
3. Copy: `cp bin/devface.prg /media/$USER/GARMIN/GARMIN/APPS/`
4. Eject/unmount cleanly, unplug.
5. On the watch: Settings → Watch Face → select the new face.

Notes
- App settings (lat/lng/simSeed/simPersist) are editable via Garmin Connect
  Mobile / Garmin Express for sideloaded apps with bundled settings.
- App logs: create `GARMIN/APPS/LOGS/DEVFACE.TXT` on the watch volume and
  `Sys.println` output (debug builds) is appended there.
- If the face misbehaves on hardware but not in the sim, suspect the watchdog
  (the device budget can be tighter than the simulator's). Reduce
  `ROWS_PER_STEP` first. A watchdog kill reverts the watch to a stock face.
- The signing key (`~/.ciq-keys/`) does not need to match across sideloads,
  but keep using one key per developer identity; store-distributed builds are
  tied to it.
