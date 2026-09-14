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
- App settings (lat/lng) are editable via Garmin Connect Mobile / Garmin
  Express for sideloaded apps with bundled settings.
- App logs: create `GARMIN/APPS/LOGS/DEVFACE.TXT` on the watch volume and
  `Sys.println` output (debug builds) is appended there. The file is named for
  the app, so the GPS probe below logs to `GPSPROBE.TXT`.
- `bin/gpsprobe.prg` is the diagnostic face for "what does `Position.getInfo()`
  return on real hardware?" — it draws the answer on screen, so no log file is
  needed. It is the only face that requests a permission (Positioning); grant it
  if the watch prompts. Read it **after a GPS activity**: that is when a cached
  fix should exist. What each reading means: docs/gps-notes.md.
- If the face misbehaves on hardware but not in the sim, suspect the watchdog
  (the device budget can be tighter than the simulator's). Trim the heaviest
  per-tick work first. A watchdog kill reverts the watch to a stock face.
- The signing key (`~/.ciq-keys/`) does not need to match across sideloads,
  but keep using one key per developer identity; store-distributed builds are
  tied to it.
