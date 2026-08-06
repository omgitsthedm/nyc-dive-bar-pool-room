#!/usr/bin/env bash
# 112_assemble_film.sh - frames + physics-timed mix -> the shipped film.
#
# Silent h264 from the ONE global frame counter (no concat step), poster from
# the 0:28 settle-wide, then the mix muxed in. Every section 6.5 / 7.4
# acceptance check runs here and a failure stops the script - the film does
# not reach the site unless it passes.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$PWD"
FRAMES="$REPO/renders/film_frames"
AUDIO="$REPO/renders/film_audio/film_mix.wav"
SILENT="$REPO/site/break-film_silent.mp4"
FINAL="$REPO/site/break-film.mp4"
POSTER_PNG="$REPO/renders/film_frames/0672.png"
POSTER="$REPO/site/img/break-film-poster.webp"
FPS=24
EXPECT_FRAMES=720

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
echo "  resolution ${W}x${H}  (require 1920x1080)"
echo "  frame rate $FR       (require 24/1)"
echo "  streams    $VC + $AC (require h264 + aac)"
echo "  size       $MB MB    (require < 60)"

fail=0
awk -v d="$DUR" 'BEGIN{exit !(d>=29.5 && d<=31.0)}' || { echo "  FAIL duration"; fail=1; }
[ "$W" = "1920" ] && [ "$H" = "1080" ] || { echo "  FAIL resolution"; fail=1; }
[ "$FR" = "24/1" ] || { echo "  FAIL frame rate"; fail=1; }
[ "$VC" = "h264" ] || { echo "  FAIL video codec"; fail=1; }
[ "$AC" = "aac" ] || { echo "  FAIL audio codec"; fail=1; }
awk -v b="$BYTES" 'BEGIN{exit !(b < 60*1048576)}' || { echo "  FAIL size"; fail=1; }
[ -f "$POSTER" ] || { echo "  FAIL poster missing"; fail=1; }

echo "=== one frame per shot, checked for black ==="
"$REPO/../.venv/bin/python" - "$FRAMES" <<'PY'
import json, sys, struct, zlib, pathlib
frames = pathlib.Path(sys.argv[1])
cuts = json.load(open(pathlib.Path(frames).parents[1] / "reports" / "film_cut_list.json"))["cuts"]
def meanY(p):
    d = p.read_bytes(); pos = 8; idat = b""
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos+4])[0]; typ = d[pos+4:pos+8]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", d[pos+8:pos+18])
        elif typ == b"IDAT":
            idat += d[pos+8:pos+8+ln]
        pos += 12 + ln
    raw = zlib.decompress(idat); ch = {0:1,2:3,4:2,6:4}[ct]; bpp = ch*(bd//8)
    stride = w*bpp; out = bytearray(); prev = bytearray(stride); i = 0
    for _ in range(h):
        fl = raw[i]; i += 1; line = bytearray(raw[i:i+stride]); i += stride
        for x in range(stride):
            a = line[x-bpp] if x >= bpp else 0
            b = prev[x]; c = prev[x-bpp] if x >= bpp else 0
            if fl == 1: line[x] = (line[x]+a) & 255
            elif fl == 2: line[x] = (line[x]+b) & 255
            elif fl == 3: line[x] = (line[x]+(a+b)//2) & 255
            elif fl == 4:
                pa, pb, pc = abs(b-c), abs(a-c), abs(a+b-2*c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x]+pr) & 255
        out += line; prev = line
    px = bytes(out); t = 0.0; n = 0
    for o in range(0, len(px)-bpp, bpp*53):
        t += 0.2126*px[o] + 0.7152*px[o+1] + 0.0722*px[o+2]; n += 1
    return t/n/255.0
bad = 0
for c in cuts:
    p = frames / ("%04d.png" % c["start"])
    y = meanY(p)
    flag = "" if y > 0.02 else "  <-- BLACK"
    if y <= 0.02: bad += 1
    print("    %04d %-32s meanY=%.4f%s" % (c["start"], c["cam"], y, flag))
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
