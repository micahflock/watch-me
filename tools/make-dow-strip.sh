#!/usr/bin/env bash
# Produce a day-of-week glyph strip PNG for StripGlyphs.
#
# Output: faces/devface/resources/drawables/dow_strip.png — 7 equal-width cells
# (SUN..SAT), pre-quantized to the fr735xt 16-color palette. The device has NO
# <palette> resource element at CIQ 2.4 and no dithering hardware, so ALL color
# reduction must happen offline, here.
#
# Requires ImageMagick. Tune CELL_W/CELL_H/FONT to taste; cell width must match
# the cellW passed to StripGlyphs.initialize().
#
# Asset pipeline (general recipe for any strip):
#   1. Render each glyph into a fixed-size cell on a transparent/black canvas.
#   2. +append the cells horizontally into one strip.
#   3. -remap against the device palette so every pixel is palette-exact.
#   4. Reference it from drawables.xml: <bitmap id="..." filename="..."/>
#   5. Load once with Ui.loadResource, blit cells via StripGlyphs.draw.
set -euo pipefail
command -v convert >/dev/null || { echo "ImageMagick 'convert' required" >&2; exit 1; }

OUT="$(dirname "$0")/../faces/devface/resources/drawables/dow_strip.png"
CELL_W=30
CELL_H=14
FONT="${FONT:-DejaVu-Sans-Bold}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# fr735xt palette from Devices/fr735xt/compiler.json (14 entries, 4bpp display).
PAL="$TMP/palette.png"
convert -size 14x1 xc:none \
  -fill '#FFFFFF' -draw 'point 0,0'  -fill '#AAAAAA' -draw 'point 1,0' \
  -fill '#555555' -draw 'point 2,0'  -fill '#000000' -draw 'point 3,0' \
  -fill '#FF0000' -draw 'point 4,0'  -fill '#AA0000' -draw 'point 5,0' \
  -fill '#FF5500' -draw 'point 6,0'  -fill '#FF00FF' -draw 'point 7,0' \
  -fill '#FFAA00' -draw 'point 8,0'  -fill '#AA00FF' -draw 'point 9,0' \
  -fill '#00FF00' -draw 'point 10,0' -fill '#00AA00' -draw 'point 11,0' \
  -fill '#00AAFF' -draw 'point 12,0' -fill '#0000FF' -draw 'point 13,0' \
  "$PAL"

i=0
for d in SUN MON TUE WED THU FRI SAT; do
  convert -size ${CELL_W}x${CELL_H} xc:black -font "$FONT" -pointsize 11 \
    -fill white -gravity center -annotate 0 "$d" "$TMP/$i-$d.png"
  i=$((i+1))
done

convert "$TMP"/0-*.png "$TMP"/1-*.png "$TMP"/2-*.png "$TMP"/3-*.png \
        "$TMP"/4-*.png "$TMP"/5-*.png "$TMP"/6-*.png +append \
        -dither None -remap "$PAL" "PNG8:$OUT"

echo "Wrote $OUT ($((CELL_W*7))x${CELL_H}, cells ${CELL_W}px)"
echo "Enable it in drawables.xml and construct StripGlyphs(Rez.Drawables.DowStrip, $CELL_W)."
