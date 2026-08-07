#!/usr/bin/env bash
# 112_assemble_film.sh - frames + physics-timed mix -> the shipped film.
#
# Silent h264 from the ONE global frame counter (no concat step), poster from
# the 0:28 settle-wide, then the mix muxed in. Every section 6.5 / 7.4
# acceptance check runs here and a failure stops the script - the film does
# not reach the site unless it passes.
set -euo pipefail
mkdir -p "$(dirname "$0")/../renders/film_out"

cd "$(dirname "$0")/.."
REPO="$PWD"
FRAMES="$REPO/renders/film_frames"
AUDIO="$REPO/renders/film_audio/film_mix.wav"
SILENT="$REPO/renders/film_out/break-film_silent.mp4"
FINAL="$REPO/site/break-film.mp4"
FINAL_WEBM="$REPO/site/break-film.webm"
POSTER_PNG="$REPO/renders/film_frames/0672.png"
POSTER="$REPO/site/img/break-film-poster.webp"
FPS=24
EXPECT_FRAMES=720
EXPECT_W=1280
EXPECT_H=720

echo "=== preflight ==="
n=$(ls "$FRAMES"/*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -eq "$EXPECT_FRAMES" ] || { echo "FAIL: $n frames, expected $EXPECT_FRAMES"; exit 1; }
[ -f "$AUDIO" ] || { echo "FAIL: no mix at $AUDIO"; exit 1; }
echo "  $n frames, mix present"

echo "=== silent h264 (one pass, global numbering) ==="
ffmpeg -y -loglevel error -framerate $FPS -start_number 0 \
  -i "$FRAMES/%04d.png" -c:v libx264 -crf 18 -pix_fmt yuv420p \
  -movflags +faststart "$SILENT"

echo "=== mux the physics-timed mix ==="
ffmpeg -y -loglevel error -i "$SILENT" -i "$AUDIO" \
  -c:v copy -c:a aac -b:a 192k -shortest \
  -movflags +faststart "$FINAL"

echo "=== VP9 WebM (Chrome/Firefox/Edge take this; Safari falls back to MP4) ==="
# Two-pass VP9: meaningfully smaller than h264 at the same quality, and the
# <source> order in index.html lets each browser pick what it can decode.
ffmpeg -y -loglevel error -i "$SILENT" -i "$AUDIO" \
  -c:v libvpx-vp9 -crf 32 -b:v 0 -row-mt 1 -deadline good -cpu-used 2 \
  -pix_fmt yuv420p -c:a libopus -b:a 128k -shortest "$FINAL_WEBM"

echo "=== poster: the 0:28 settle-wide (frame 672) ==="
[ -f "$POSTER_PNG" ] || { echo "FAIL: frame 0672 missing"; exit 1; }
cwebp -quiet -q 82 -m 6 "$POSTER_PNG" -o "$POSTER"

echo "=== 6.5 acceptance ==="
read -r dur w h fr codecs < <(ffprobe -v error \
  -show_entries format=duration:stream=width,height,avg_frame_rate,codec_name \
  -of csv=p=0 "$FINAL" | tr '\n' ' ' | awk '{print $0}' \
  | sed 's/,/ /g' | awk '{print $NF, $1, $2, $3, $4" "$5}')
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FINAL")
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$FINAL")
H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$FINAL")
FR=$(ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of csv=p=0 "$FINAL")
VC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$FINAL")
AC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$FINAL")
BYTES=$(wc -c < "$FINAL" | tr -d ' ')
MB=$(echo "$BYTES" | awk '{printf "%.1f", $1/1048576}')
echo "  duration   $DUR s   (require 29.5-31.0)"
echo "  resolution ${W}x${H}  (require ${EXPECT_W}x${EXPECT_H})"
echo "  frame rate $FR       (require 24/1)"
echo "  streams    $VC + $AC (require h264 + aac)"
WBYTES=$(wc -c < "$FINAL_WEBM" | tr -d " ")
WMB=$(echo "$WBYTES" | awk '{printf "%.1f", $1/1048576}')
echo "  size       $MB MB    (require < 60)"
echo "  webm       $WMB MB   ($(echo "$BYTES $WBYTES" | awk '{printf "%.0f", (1-$2/$1)*100}')% smaller than the mp4)"

fail=0
awk -v d="$DUR" 'BEGIN{exit !(d>=29.5 && d<=31.0)}' || { echo "  FAIL duration"; fail=1; }
[ "$W" = "$EXPECT_W" ] && [ "$H" = "$EXPECT_H" ] || { echo "  FAIL resolution"; fail=1; }
[ "$FR" = "24/1" ] || { echo "  FAIL frame rate"; fail=1; }
[ "$VC" = "h264" ] || { echo "  FAIL video codec"; fail=1; }
[ "$AC" = "aac" ] || { echo "  FAIL audio codec"; fail=1; }
awk -v b="$BYTES" 'BEGIN{exit !(b < 60*1048576)}' || { echo "  FAIL size"; fail=1; }
[ -f "$POSTER" ] || { echo "  FAIL poster missing"; fail=1; }

echo "=== one frame per shot, checked for black ==="
"$REPO/../.venv/bin/python" - "$FRAMES" <<'PY'
import json, sys, pathlib
frames = pathlib.Path(sys.argv[1])
repo = frames.parents[1]
sys.path.insert(0, str(repo / "scripts"))
# Shared reader. The decoder that used to live inline here assumed 8 bits per
# channel; Blender was writing 16-bit PNGs, so it read the high and low bytes
# of red as red and green and reported confident nonsense - which is how a
# pitch-black film once passed this exact check.
from pngstats import luminance_stats
cuts = json.load(open(repo / "reports" / "film_cut_list.json"))["cuts"]
bad = 0
for c in cuts:
    p = frames / ("%04d.png" % c["start"])
    s = luminance_stats(p, stride_px=53)
    flag = "" if s["mean"] > 0.02 else "  <-- BLACK"
    if s["mean"] <= 0.02:
        bad += 1
    print("    %04d %-32s meanY=%.4f (%d-bit)%s"
          % (c["start"], c["cam"], s["mean"], s["bit_depth"], flag))
print("  black frames: %d" % bad)
sys.exit(1 if bad else 0)
PY
[ $? -eq 0 ] || fail=1

if [ "$fail" -ne 0 ]; then
  echo
  echo "FILM ACCEPTANCE FAILED - not shipping"
  exit 1
fi
echo
echo "FILM ACCEPTED: $MB MB, $DUR s, ${W}x${H} @ $FR, $VC+$AC"
