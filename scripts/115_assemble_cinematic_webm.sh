#!/usr/bin/env bash
# 115_assemble_cinematic_webm.sh - frames + mix -> VP9 WebM and H.264 MP4.
#
# Order matters and is enforced: the frames are validated, THEN grained, THEN
# encoded. Nothing reaches site/ that has not been through 118.
#
# Grain is applied by streaming the sequence through filmgrain.py between two
# ffmpeg processes into a lossless intermediate. The intermediate exists
# because VP9 two-pass has to read the input twice and graining twice would
# be wasteful; it is deleted at the end unless --keep-master.
#
# Everything heavy lives under the scratch root. Only the four delivered
# files are written into the repo.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
SCRATCH="${SCRATCH:-/private/tmp/pool-room-cinematic-webm}"
WORKSPACE="$(cd "$REPO/.." && pwd -P)"
POOL_ROOM_PYTHON="${POOL_ROOM_PYTHON:-$WORKSPACE/.venv/bin/python}"

FRAMES="$SCRATCH/frames"
AUDIO="$SCRATCH/audio/film_mix.wav"
ENC="$SCRATCH/encode"
MASTER="$ENC/grained_master.mkv"
WEBM="$REPO/site/break-film.webm"
MP4="$REPO/site/break-film.mp4"
POSTER="$REPO/site/img/break-film-poster.webp"

W=1280
H=720
FPS=24
EXPECT_FRAMES=720
CRF_VP9="${CRF_VP9:-27}"
CRF_X264=19
POSTER_FRAME="${POSTER_FRAME:-712}"
KEEP_MASTER=0
[ "${1:-}" = "--keep-master" ] && KEEP_MASTER=1

SHA="$("$POOL_ROOM_PYTHON" -c "import json;print(json.load(open('$REPO/assets/data/shots/break_film.json'))['trajectory_sha256'])")"
mkdir -p "$ENC" "$(dirname "$POSTER")"

echo "=== 1. frame sequence gate ==="
"$POOL_ROOM_PYTHON" "$REPO/scripts/118_validate_frame_sequence.py" \
  --frames "$FRAMES" --manifest "$SCRATCH/tests/shot-manifest.json" \
  --report "$SCRATCH/tests/frame-sequence.json"

n=$(ls "$FRAMES"/[0-9][0-9][0-9][0-9].png 2>/dev/null | wc -l | tr -d ' ')
[ "$n" = "$EXPECT_FRAMES" ] || { echo "FAIL: $n frames, expected $EXPECT_FRAMES"; exit 1; }
[ -f "$AUDIO" ] || { echo "FAIL: missing $AUDIO"; exit 1; }

echo
echo "=== 2. film grain after denoise -> lossless master ==="
# rgb24 both ways so the grain is applied before any chroma subsampling; the
# 4:2:0 conversion happens once, in the deliverable encodes.
ffmpeg -y -loglevel error -framerate $FPS -start_number 0 \
  -i "$FRAMES/%04d.png" -f rawvideo -pix_fmt rgb24 - \
| "$POOL_ROOM_PYTHON" "$REPO/scripts/filmgrain.py" --width $W --height $H --sha "$SHA" \
    --stats "$SCRATCH/tests/grain-stats.json" \
| ffmpeg -y -loglevel error -f rawvideo -pix_fmt rgb24 -s ${W}x${H} \
    -framerate $FPS -i - -c:v ffv1 -level 3 -g 1 "$MASTER"
echo "  master: $(du -h "$MASTER" | cut -f1)"

echo
echo "=== 3. VP9 two-pass + Opus (primary) ==="
PASSLOG="$ENC/vp9pass"
ffmpeg -y -loglevel error -i "$MASTER" \
  -c:v libvpx-vp9 -b:v 0 -crf $CRF_VP9 -row-mt 1 -tile-columns 2 \
  -frame-parallel 0 -threads 8 -speed 4 -g 240 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -pass 1 -passlogfile "$PASSLOG" -an -f null /dev/null
ffmpeg -y -loglevel error -i "$MASTER" -i "$AUDIO" \
  -c:v libvpx-vp9 -b:v 0 -crf $CRF_VP9 -row-mt 1 -tile-columns 2 \
  -frame-parallel 0 -threads 8 -speed 1 -g 240 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -pass 2 -passlogfile "$PASSLOG" \
  -c:a libopus -b:a 128k -ac 2 -shortest "$WEBM"

echo "=== 4. H.264 + AAC (fallback) ==="
ffmpeg -y -loglevel error -i "$MASTER" -i "$AUDIO" \
  -c:v libx264 -crf $CRF_X264 -preset slow -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -c:a aac -b:a 160k -ac 2 -shortest -movflags +faststart "$MP4"

echo
echo "=== 5. poster from the grained master, frame $POSTER_FRAME ==="
ffmpeg -y -loglevel error -i "$MASTER" \
  -vf "select=eq(n\,$POSTER_FRAME)" -vsync 0 -frames:v 1 \
  "$ENC/poster.png"
cwebp -quiet -q 86 -m 6 "$ENC/poster.png" -o "$POSTER"

echo
echo "=== 6. codec QA ==="
probe() {
  ffprobe -v error -select_streams "$2" \
    -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels \
    -of default=nw=1:nk=0 "$1"
}
fail=0
for f in "$WEBM" "$MP4"; do
  echo "--- $(basename "$f") ($(du -h "$f" | cut -f1)) ---"
  probe "$f" v:0
  probe "$f" a:0
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  nb=$(ffprobe -v error -select_streams v:0 -count_frames \
       -show_entries stream=nb_read_frames -of csv=p=0 "$f")
  echo "duration=$d  frames=$nb"
  awk -v d="$d" 'BEGIN{exit !(d>=29.9 && d<=30.1)}' \
    || { echo "  FAIL duration $d"; fail=1; }
  [ "$nb" = "$EXPECT_FRAMES" ] || { echo "  FAIL frame count $nb"; fail=1; }
done

VC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$WEBM")
AC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$WEBM")
[ "$VC" = "vp9" ]   || { echo "FAIL webm video codec: $VC"; fail=1; }
[ "$AC" = "opus" ]  || { echo "FAIL webm audio codec: $AC"; fail=1; }
MVC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$MP4")
MAC=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$MP4")
[ "$MVC" = "h264" ] || { echo "FAIL mp4 video codec: $MVC"; fail=1; }
[ "$MAC" = "aac" ]  || { echo "FAIL mp4 audio codec: $MAC"; fail=1; }

# faststart: the moov atom has to be in the first 64 KB or the browser waits
if head -c 65536 "$MP4" | grep -qa moov; then
  echo "mp4 faststart: moov in the first 64 KB  OK"
else
  echo "FAIL mp4 faststart: moov not near the head"; fail=1
fi

[ $KEEP_MASTER -eq 1 ] || rm -f "$MASTER"
rm -f "$PASSLOG"-*.log

echo
[ $fail -eq 0 ] || { echo "ASSEMBLY FAILED"; exit 1; }
echo "ASSEMBLED OK"
echo "  $WEBM"
echo "  $MP4"
echo "  $POSTER"
